"""Локальная справка платформы: HBK → SQLite FTS5, без внешних сервисов."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import threading
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

from mcp_baf.dumpindex.cache import user_cache_dir
from mcp_baf.dumpindex.synonyms import build_synonym_map
from mcp_baf.helpindex.hbk import read_pages

SECTIONS = ("functions", "types", "operators", "vtables", "skd")
SCHEMA_VERSION = 1


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.title = []
        self.in_title = False
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "title":
            self.in_title = True
        if tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "pre"}:
            self.text.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.in_title = False
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "pre"}:
            self.text.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)
            if self.in_title:
                self.title.append(data)


def parse_page(html: str, path: str) -> tuple[str, str, str, str]:
    parser = PageParser()
    parser.feed(html)
    content = "\n".join(x.strip() for x in "".join(parser.text).splitlines() if x.strip())
    title = " ".join(parser.title).strip() or (content.splitlines() or [Path(path).stem])[0]
    # Сохраняем обе языковые формы из заголовка; имена методов с типом не сокращаем.
    aliases = " ".join(re.findall(r"[^\W\d]\w*(?:\.\w+)*", title, re.UNICODE))
    hints = (path + " " + title).lower()
    if any(x in hints for x in ("virtualtable", "virtual_table", "виртуальн", "остатки", "обороты")):
        section = "vtables"
    elif any(x in hints for x in ("datacomposition", "скд", "компоновк")):
        section = "skd"
    elif any(x in hints for x in ("operator", "оператор")):
        section = "operators"
    elif any(x in hints for x in ("function", "global", "функци", "глобальн")):
        section = "functions"
    else:
        section = "types"
    return title, aliases, section, content


def normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


class HelpIndex:
    def __init__(self, help_dir: str, cache_dir: str = "", reindex: bool = False):
        self.root = Path(help_dir).expanduser().resolve()
        digest = hashlib.sha256(str(self.root).encode()).hexdigest()[:16]
        base = Path(cache_dir) if cache_dir else Path(user_cache_dir()) / "mcp-baf"
        self.database = base / f"help-{digest}.sqlite"
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._connection = None
        self.error: Exception | None = None
        self._thread = threading.Thread(target=self._build, args=(reindex,), daemon=True)
        self._thread.start()

    def wait_ready(self, timeout=None):
        return self._ready.wait(timeout)

    def _build(self, reindex):
        temporary = None
        connection = None
        try:
            if not self.root.is_dir():
                raise ValueError("Каталог --help-dir не найден")
            files = sorted(self.root.rglob("*.hbk"))
            if not files:
                raise ValueError("В --help-dir нет файлов .hbk")
            manifest = json.dumps([SCHEMA_VERSION, [(str(f.relative_to(self.root)), f.stat().st_mtime_ns, f.stat().st_size) for f in files]])
            self.database.parent.mkdir(parents=True, exist_ok=True)
            if self.database.exists() and not reindex:
                try:
                    connection = sqlite3.connect(self.database, check_same_thread=False)
                    state = connection.execute("SELECT value FROM state").fetchone()
                    if connection.execute("PRAGMA quick_check").fetchone()[0] == "ok" and state == (manifest,):
                        pages = connection.execute("SELECT count(*) FROM pages").fetchone()[0]
                        indexed = connection.execute("SELECT count(*) FROM search").fetchone()[0]
                        if not pages or pages != indexed:
                            raise sqlite3.DatabaseError("Incomplete help cache")
                        with self._lock:
                            self._connection = connection
                        connection = None
                        return
                except sqlite3.DatabaseError:
                    pass
                finally:
                    if connection is not None:
                        connection.close()
                        connection = None
            descriptor, temporary = tempfile.mkstemp(prefix="help-build-", suffix=".sqlite", dir=self.database.parent)
            os.close(descriptor)
            connection = sqlite3.connect(temporary)
            connection.execute("CREATE TABLE state(value TEXT)")
            connection.execute("INSERT INTO state VALUES (?)", (manifest,))
            connection.execute("CREATE TABLE pages(id INTEGER PRIMARY KEY, title TEXT, aliases TEXT, section TEXT, content TEXT, source TEXT, version TEXT, name_key TEXT)")
            connection.execute("CREATE VIRTUAL TABLE search USING fts5(title, aliases, content)")
            count = 0
            for file in files:
                version = next((p for p in file.parts if re.fullmatch(r"8\.\d+(?:\.\d+){0,2}", p)), "не указана")
                for path, html in read_pages(file):
                    if self._stop.is_set():
                        return
                    title, aliases, section, content = parse_page(html, path)
                    if not content:
                        continue
                    source = f"{file.relative_to(self.root).as_posix()}::{path}"
                    cursor = connection.execute("INSERT INTO pages(title,aliases,section,content,source,version,name_key) VALUES (?,?,?,?,?,?,?)", (title, normalize(aliases), section, content, source, version, normalize(title)))
                    connection.execute("INSERT INTO search(rowid,title,aliases,content) VALUES (?,?,?,?)", (cursor.lastrowid, title, aliases, content))
                    count += 1
            if not count:
                raise ValueError("HBK не содержит страниц справки")
            connection.commit()
            connection.close()
            connection = None
            os.replace(temporary, self.database)
            temporary = None
            with self._lock:
                self._connection = sqlite3.connect(self.database, check_same_thread=False)
        except Exception as exc:
            self.error = exc
        finally:
            if connection is not None:
                connection.close()
            if temporary:
                Path(temporary).unlink(missing_ok=True)
            self._ready.set()

    def _check(self):
        if self.error:
            raise RuntimeError(f"Справка недоступна: {self.error}")
        if not self._ready.is_set():
            raise RuntimeError("Индекс справки строится; повторите запрос позже")
        if self._connection is None:
            raise RuntimeError("Индекс справки закрыт")

    def search(self, query: str, limit=10, section="") -> list[dict]:
        if section and section not in SECTIONS:
            raise ValueError("section: " + ", ".join(SECTIONS))
        tokens = re.findall(r"\w+", normalize(query))
        if not tokens:
            raise ValueError("query должен содержать название или слова для поиска")
        synonyms = build_synonym_map()
        expression = " AND ".join('("' + t + '" OR "' + synonyms[t] + '")' if t in synonyms else '"' + t + '"' for t in tokens)
        with self._lock:
            self._check()
            cursor = self._connection.execute(
                "SELECT p.*, bm25(search, 10, 6, 1) AS score FROM search JOIN pages p ON p.id=search.rowid WHERE search MATCH ? AND (?='' OR p.section=?) ORDER BY (p.name_key=?) DESC, score, p.source LIMIT ?",
                (expression, section, section, normalize(query), limit),
            )
            names = [d[0] for d in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]

    def get(self, name: str, source: str = "") -> list[dict]:
        with self._lock:
            self._check()
            cursor = self._connection.execute("SELECT * FROM pages WHERE (name_key=? OR instr(' ' || aliases || ' ', ' ' || ? || ' ')>0) AND (?='' OR source=?) ORDER BY source LIMIT 20", (normalize(name), normalize(name), source, source))
            names = [d[0] for d in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]

    def close(self):
        self._stop.set()
        self._thread.join()
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
