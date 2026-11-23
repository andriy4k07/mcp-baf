"""Локальная справка платформы: HBK → SQLite FTS5, без внешних сервисов."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import struct
import tempfile
import threading
import time
import unicodedata
import zipfile
import zlib
from html.parser import HTMLParser
from pathlib import Path

from mcp_baf.dumpindex.cache import remove_stale, user_cache_dir
from mcp_baf.dumpindex.synonyms import build_synonym_map
from mcp_baf.helpindex.hbk import read_pages

SECTIONS = ("functions", "types", "operators", "vtables", "skd")
SCHEMA_VERSION = 3
BLOCK_TAGS = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "table", "ul", "ol", "dt", "dd"}
# Сегменты пути, после которых страница описывает член типа, а не сам тип.
MEMBER_SEGMENTS = {"methods", "properties", "events", "ctors", "formparams", "fields", "params"}
TYPE_TITLE = re.compile(r"(\w+) \((\w+)\)")
# Части CamelCase-имени: СтрНайти → Стр, Найти; HTTPСоединение → HTTP, Соединение.
NAME_PARTS = re.compile(r"[A-ZА-ЯЁІЇЄҐ]+(?![a-zа-яёіїєґ])|[A-ZА-ЯЁІЇЄҐ][a-zа-яёіїєґ\d]+")

logger = logging.getLogger(__name__)

# Сколько секунд close() ждёт поток-строитель справки.
CLOSE_JOIN_TIMEOUT = 10.0
# Временные файлы сборки старше часа — сироты после SIGKILL/OOM.
STALE_BUILD_AGE = 3600.0
# Режимы search(): bm25 — чистый FTS (без сети), vector/hybrid — с векторным шаром.
SEARCH_MODES = ("bm25", "vector", "hybrid")
# hybrid: сколько BM25-кандидатов уходит в реранкер (как HYBRID_TOP в dumpindex).
HYBRID_CANDIDATES = 40
# Сколько страниц за одно взятие блокировки читает поток-строитель векторов.
VECTOR_SCAN_BATCH = 200


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
        if tag == "br" or tag in BLOCK_TAGS:
            self.text.append("\n")
        elif tag in {"td", "th"}:
            # Ячейки таблиц параметров не должны склеиваться в одно слово.
            self.text.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.in_title = False
        if tag in BLOCK_TAGS:
            self.text.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)
            if self.in_title:
                self.title.append(data)


def parse_page(html: str, path: str) -> tuple[str, str, str, str]:
    parser = PageParser()
    # BOM перед <html> в реальных HBK иначе становится «заголовком» страницы.
    parser.feed(html.lstrip("\ufeff"))
    content = "\n".join(x.strip() for x in "".join(parser.text).splitlines() if x.strip())
    title = " ".join(parser.title).strip() or (content.splitlines() or [Path(path).stem])[0]
    # Сохраняем обе языковые формы из заголовка; имена методов с типом не сокращаем.
    aliases = " ".join(re.findall(r"[^\W\d]\w*(?:\.\w+)*", title, re.UNICODE))
    hints = (path + " " + title).lower()
    if any(x in hints for x in ("virtualtable", "virtual_table", "виртуальн")):
        section = "vtables"
    elif any(x in hints for x in ("datacomposition", "компоновк")) or re.search(r"\bскд\b", hints):
        section = "skd"
    elif any(x in hints for x in ("operator", "оператор")):
        section = "operators"
    elif any(x in hints for x in ("function", "global", "глобальн")) or re.search(r"\bфункци[яий]\b", hints):
        section = "functions"
    else:
        section = "types"
    return title, aliases, section, content


def normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


class HelpIndex:
    def __init__(self, help_dir: str, cache_dir: str = "", reindex: bool = False,
                 embed_url: str = "", rerank_url: str = "",
                 embed_model: str = "qwen3-embedding", rerank_model: str = "qwen3-reranker"):
        self.root = Path(help_dir).expanduser().resolve()
        digest = hashlib.sha256(str(self.root).encode()).hexdigest()[:16]
        base = Path(cache_dir) if cache_dir else Path(user_cache_dir()) / "mcp-baf"
        self.database = base / f"help-{digest}.sqlite"
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._connection = None
        self.error: Exception | None = None
        self._type_names = None
        self._rerank_url = rerank_url
        self._rerank_model = rerank_model
        # Векторный шар — только при явном --embed-url: без него bm25 не дёргает сеть.
        self._vectors = None
        self._vector_thread = None
        if embed_url:
            from mcp_baf.helpindex.vectors import (
                HelpVectorStore,  # numpy нужен только здесь
            )

            # Отдельный SQLite рядом с кэшем helpindex (не vectors.db dumpindex).
            self._vectors = HelpVectorStore(embed_url, embed_model,
                                            str(base / f"help-vectors-{digest}.sqlite"))
            self._vector_thread = threading.Thread(
                target=self._build_vectors, name="help-vector-build", daemon=True
            )
            self._vector_thread.start()
        self._thread = threading.Thread(target=self._build, args=(reindex,), daemon=True)
        self._thread.start()

    def wait_ready(self, timeout=None):
        return self._ready.wait(timeout)

    def has_vectors(self) -> bool:
        """Включён ли векторный шар (--embed-url)."""
        return self._vectors is not None

    def wait_vectors(self, timeout: float | None = None) -> bool:
        """Ждёт готовности векторов; False — выключен, ошибка сборки или таймаут."""
        vi = self._vectors
        if vi is None:
            return False
        deadline = None if timeout is None else time.monotonic() + timeout
        # ready ставится только при успехе: ошибку сборки ловим опросом, а не ждём таймаут.
        while not vi.ready.wait(1.0):
            if vi.error is not None or (deadline is not None and time.monotonic() >= deadline):
                return False
        return True

    def _build_vectors(self):
        """Векторы строятся после готовности FTS: читают pages пачками (паттерн dumpindex)."""
        from mcp_baf.helpindex.vectors import (
            page_chunk,  # лениво: numpy/httpx только при векторе
        )

        while not self._ready.wait(1.0):
            if self._stop.is_set() or self.error is not None:
                return

        def batches():
            last = ""
            while not self._stop.is_set():
                with self._lock:
                    if self._connection is None:
                        return
                    rows = self._connection.execute(
                        "SELECT source, section, title, content FROM pages WHERE source > ? ORDER BY source LIMIT ?",
                        (last, VECTOR_SCAN_BATCH),
                    ).fetchall()
                if not rows:
                    return
                last = rows[-1][0]
                yield [(source, section, page_chunk(title, content)) for source, section, title, content in rows]

        self._vectors.build(batches(), lambda: self._stop.is_set())

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
            remove_stale(str(self.database.parent / "help-build-"), STALE_BUILD_AGE)
            descriptor, temporary = tempfile.mkstemp(prefix="help-build-", suffix=".sqlite", dir=self.database.parent)
            os.close(descriptor)
            connection = sqlite3.connect(temporary)
            connection.execute("CREATE TABLE state(value TEXT)")
            connection.execute("INSERT INTO state VALUES (?)", (manifest,))
            connection.execute("CREATE TABLE pages(id INTEGER PRIMARY KEY, title TEXT, aliases TEXT, section TEXT, content TEXT, source TEXT, version TEXT, name_key TEXT)")
            connection.execute("CREATE VIRTUAL TABLE search USING fts5(title, aliases, content)")
            count = 0
            broken = None
            for file in files:
                version = next((p for p in file.parts if re.fullmatch(r"8\.\d+(?:\.\d+){0,2}", p)), "не указана")
                name = file.relative_to(self.root).as_posix()
                try:
                    for path, html in read_pages(file):
                        if self._stop.is_set():
                            return
                        title, aliases, section, content = parse_page(html, path)
                        if not content:
                            continue
                        cursor = connection.execute("INSERT INTO pages(title,aliases,section,content,source,version,name_key) VALUES (?,?,?,?,?,?,?)", (title, normalize(aliases), section, content, f"{name}::{path}", version, normalize(title)))
                        parts = " ".join(NAME_PARTS.findall(title))
                        connection.execute("INSERT INTO search(rowid,title,aliases,content) VALUES (?,?,?,?)", (cursor.lastrowid, title, f"{aliases} {parts}", content))
                        count += 1
                except (ValueError, zipfile.BadZipFile, struct.error, zlib.error, EOFError, NotImplementedError, RuntimeError) as exc:
                    # Один повреждённый файл не отключает справку остальных.
                    logger.warning("HBK пропущен: %s: %s", name, exc)
                    broken = broken or ValueError(f"{name}: {exc}")
            if not count:
                raise broken or ValueError("HBK не содержит страниц справки")
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

    def _tokens(self, query: str) -> list[str]:
        tokens = re.findall(r"\w+", normalize(query))
        if not tokens:
            raise ValueError("query должен содержать название или слова для поиска")
        return tokens

    def search(self, query: str, limit=10, section="", mode="bm25") -> list[dict]:
        """Страницы справки; mode: bm25 (по умолчанию, без сети), vector, hybrid."""
        rows, _ = self.search_with_note(query, limit, section, mode)
        return rows

    def search_with_note(self, query: str, limit=10, section="", mode="bm25") -> tuple[list[dict], str]:
        """Как search(), но вторым значением — текстовое примечание о деградации ('' если всё ок)."""
        if mode not in SEARCH_MODES:
            raise ValueError("mode: " + ", ".join(SEARCH_MODES))
        self._tokens(query)  # один и тот же валидатор запроса для всех режимов
        if mode == "hybrid":
            return self._search_hybrid(query, limit, section)
        if mode == "vector":
            return self._search_vector(query, limit, section)
        return self._search_bm25(query, limit, section), ""

    def _search_bm25(self, query: str, limit=10, section="") -> list[dict]:
        if section and section not in SECTIONS:
            raise ValueError("section: " + ", ".join(SECTIONS))
        tokens = self._tokens(query)
        synonyms = build_synonym_map()
        # Префиксный поиск: по началу имени и по частям CamelCase из aliases.
        terms = ['("' + t + '"* OR "' + synonyms[t] + '"*)' if t in synonyms else '"' + t + '"*' for t in tokens]
        with self._lock:
            self._check()
            # Фраза обычным языком редко совпадает целиком: тогда хватит любого слова.
            for joiner in (" AND ", " OR ")[:len(terms)]:
                cursor = self._connection.execute(
                    "SELECT p.*, bm25(search, 10, 6, 1) AS score FROM search JOIN pages p ON p.id=search.rowid WHERE search MATCH ? AND (?='' OR p.section=?) ORDER BY (p.name_key=?) DESC, score, p.source LIMIT ?",
                    (joiner.join(terms), section, section, normalize(query), limit),
                )
                names = [d[0] for d in cursor.description]
                if rows := [dict(zip(names, row)) for row in cursor.fetchall()]:
                    return rows
            return []

    def _search_vector(self, query: str, limit: int, section: str) -> tuple[list[dict], str]:
        """Чистый семантический поиск по косинусу; при недоступности — понятное сообщение."""
        vi = self._vectors
        if vi is None:
            raise ValueError("vector mode is disabled: start with --embed-url")
        if vi.error is not None:
            raise RuntimeError(f"векторный индекс недоступен: {vi.error}")
        if not vi.ready.is_set():
            # Ещё строится: не валим запрос, а отдаём BM25 с честным примечанием.
            return self._search_bm25(query, limit, section), (
                f"векторный индекс строится: {vi.done}/{vi.total}; показан только BM25"
            )
        try:
            hits = vi.search(query, limit, section)
        except Exception as exc:  # эмбеддер умер после сборки: деградация вместо падения
            raise RuntimeError(f"векторный индекс недоступен: {exc}") from exc
        rows = []
        with self._lock:
            self._check()
            for source, score in hits:
                cursor = self._connection.execute("SELECT * FROM pages WHERE source=?", (source,))
                names = [d[0] for d in cursor.description]
                if row := cursor.fetchone():
                    rows.append(dict(zip(names, row), score=score))
        return rows, ""

    def _search_hybrid(self, query: str, limit: int, section: str) -> tuple[list[dict], str]:
        """BM25-кандидаты (top HYBRID_CANDIDATES) -> rerank_scores -> top limit."""
        candidates = self._search_bm25(query, max(limit, HYBRID_CANDIDATES), section)
        if not candidates:
            return [], ""
        if not self._rerank_url:
            return candidates[:limit], (
                "векторный индекс недоступен: реранкер не настроен (запустите с --rerank-url); показан только BM25"
            )
        from mcp_baf.dumpindex.vectors import CHUNK_CHAR_BUDGET
        from mcp_baf.helpindex import (
            vectors as help_vectors,  # лениво: тот же клиент, что у dumpindex
        )
        docs = [f"{c['title']}\n{c['content']}"[:CHUNK_CHAR_BUDGET] for c in candidates]
        try:
            scores = help_vectors.rerank_scores(self._rerank_url, self._rerank_model, query, docs)
        except Exception as exc:  # noqa: BLE001 — реранкер лёг: отдаём BM25 с примечанием, без падения
            return candidates[:limit], f"векторный индекс недоступен: {exc}; показан только BM25"
        ranked = [dict(c, score=s) for c, s in sorted(zip(candidates, scores), key=lambda cs: -cs[1])]
        return ranked[:limit], ""

    def get(self, name: str, source: str = "") -> list[dict]:
        with self._lock:
            self._check()
            cursor = self._connection.execute("SELECT * FROM pages WHERE (name_key=? OR instr(' ' || aliases || ' ', ' ' || ? || ' ')>0) AND (?='' OR source=?) ORDER BY source LIMIT 20", (normalize(name), normalize(name), source, source))
            names = [d[0] for d in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]

    def type_names(self) -> frozenset:
        """Имена типов контекста (ru и en, casefold); пусто, пока индекс не готов."""
        if not self._ready.is_set() or self.error or self._connection is None:
            return frozenset()
        with self._lock:
            if self._type_names is None and self._connection is not None:
                names = set()
                for source, title in self._connection.execute("SELECT source, title FROM pages WHERE source LIKE '%::objects/%'"):
                    parts = source.split("::", 1)[1].split("/")
                    if (len(parts) > 2 and not MEMBER_SEGMENTS & set(parts) and parts[1] != "Global context"
                            and not re.fullmatch(r"catalog\d+\.html", parts[-1])):
                        # «ОбъектМетаданных: Форма (MetadataObject: Form)» — тип назван до двоеточия.
                        names |= {normalize(n) for m in TYPE_TITLE.findall(title) for n in m}
                        names |= {normalize(n) for n in re.findall(r"(?:^|\()(\w+):", title)}
                self._type_names = frozenset(names)
            return self._type_names or frozenset()

    def close(self):
        self._stop.set()
        self._thread.join(timeout=CLOSE_JOIN_TIMEOUT)
        if self._vector_thread is not None:
            self._vector_thread.join(timeout=CLOSE_JOIN_TIMEOUT)
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
