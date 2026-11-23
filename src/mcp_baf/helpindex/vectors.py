"""Опциональный векторный кэш страниц справки платформы (issue #170).

Embed/rerank-клиент НЕ дублируем: `embed_texts`, `rerank_scores` и `endpoint`
переиспользуются из `mcp_baf.dumpindex.vectors` (тот же OpenAI-совместимый
/v1/embeddings и реранкер Qwen3). Нumpy нужен только при включённом
--embed-url, поэтому импортируется лениво в `_np`.

- чанк = одна страница (.hbk): заголовок + текст, обрезанный по бюджету
  эмбеддера (`CHUNK_CHAR_BUDGET`); длинная страница не режется на куски —
  усечённого префикса хватает для семантического ранжирования;
- кэш — отдельный SQLite-файл рядом с БД helpindex (НЕ vectors.db dumpindex):
  page_id -> sha256(модель + текст чанка) -> нормированный float16-вектор;
  при изменении текста страницы хэш меняется и вектор пересчитывается,
  пропавшие страницы удаляются из кэша;
- матрица нормированных векторов держится в RAM, поиск — косинус matrix @ q.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor

from mcp_baf.dumpindex.vectors import (
    CHUNK_CHAR_BUDGET,
    EMBED_BATCH,
    EMBED_WORKERS,
    embed_texts,
    endpoint,
    rerank_scores,
)

# Реэкспорт клиента из dumpindex (второй embed/rerank-клиент запрещён): их зовёт
# HelpIndex._search_hybrid через этот namespace и патчат офлайн-тесты.
__all__ = ["CHUNK_CHAR_BUDGET", "EMBED_BATCH", "EMBED_WORKERS", "HelpVectorStore", "embed_texts",
           "endpoint", "page_chunk", "rerank_scores"]

logger = logging.getLogger("mcp_baf.helpindex.vectors")

# Версия схемы векторного кэша; при её подъёме старые векторы сбрасываются.
CACHE_SCHEMA_VERSION = 1


def _np():
    try:
        import numpy
    except ImportError as exc:
        raise RuntimeError(
            "vector search needs numpy: pip install mcp-baf[rag]"
        ) from exc
    return numpy


def page_chunk(title: str, content: str) -> str:
    """Одна страница = один чанк: заголовок + текст в бюджете эмбеддера."""
    return f"{title}\n{content}"[:CHUNK_CHAR_BUDGET]


class HelpVectorStore:
    """Векторы страниц справки: SQLite-кэш + float16-матрица в RAM.

    Построение запускается из фонового потока HelpIndex; ошибка ловится в
    self.error (сервер не валится, режимы vector/hybrid деградируют).
    """

    def __init__(self, embed_url: str, embed_model: str, db_path: str) -> None:
        self._np = _np()  # fail fast при старте, а не при первом запросе
        self._url = endpoint(embed_url, "/v1/embeddings")
        self._model = embed_model
        self._db_path = db_path or ":memory:"
        self.ready = threading.Event()
        self.error: Exception | None = None
        self.done = 0
        self.total = 0
        self._sources: list[str] = []
        self._sections: list[str] = []
        self._matrix = None

    def _key(self, text: str) -> str:
        return hashlib.sha256((self._model + "\0" + text).encode("utf-8")).hexdigest()

    def build(self, batches: Iterable[list[tuple]], should_stop: Callable[[], bool]) -> None:
        """batches: списки (source, section, text). Ошибка -> self.error."""
        try:
            self._build(batches, should_stop)
        except Exception as exc:  # noqa: BLE001 — не валим сервер: режимы деградируют к BM25
            logger.error("Help vector index build failed: %s", exc)
            self.error = exc

    def _build(self, batches, should_stop) -> None:
        np = self._np
        db = sqlite3.connect(self._db_path, timeout=30, check_same_thread=False)
        try:
            db.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT) WITHOUT ROWID")
            # Ключ — source страницы (<file>.hbk::<путь внутри>): он стабилен между
            # пересборками helpindex (в отличие от id строк pages) и меняется с контентом.
            db.execute("CREATE TABLE IF NOT EXISTS vec(source TEXT PRIMARY KEY, section TEXT, h TEXT, v BLOB)")
            row = db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
            if row and row[0] != str(CACHE_SCHEMA_VERSION):
                db.execute("DELETE FROM vec")
            db.execute("INSERT OR REPLACE INTO meta VALUES ('schema', ?)", (str(CACHE_SCHEMA_VERSION),))
            db.commit()
            stored = dict(db.execute("SELECT source, h FROM vec"))

            pages: list[tuple[str, str, str]] = []  # (source, section, хэш чанка)
            new_texts: dict[str, str] = {}  # хэш -> текст только нового/изменённого
            pending = 0
            for batch in batches:
                if should_stop():
                    return
                for source, section, text in batch:
                    h = self._key(text)
                    pages.append((source, section, h))
                    if stored.get(source) != h:
                        pending += 1
                        new_texts.setdefault(h, text)
            self.total = len(pages)
            self.done = self.total - pending  # прогресс: страницы с готовым вектором

            def flush():
                """Готовые векторы сразу в кэш: прерванная сборка возобновляется."""
                rows = [(source, section, h, blobs[h])
                        for source, section, h in pages if h in blobs]
                db.executemany("INSERT OR REPLACE INTO vec(source, section, h, v) VALUES (?,?,?,?)", rows)
                db.commit()

            blobs: dict[str, bytes] = {}
            todo = list(new_texts.items())
            # Пачки в несколько потоков, как VectorIndex.dumpindex: полный каталог
            # справки (~47k страниц) собирается минуты, а не часы.
            with ThreadPoolExecutor(EMBED_WORKERS) as pool:
                for off in range(0, len(todo), EMBED_BATCH * EMBED_WORKERS):
                    if should_stop():
                        return
                    parts = [todo[o:o + EMBED_BATCH]
                             for o in range(off, min(off + EMBED_BATCH * EMBED_WORKERS, len(todo)), EMBED_BATCH)]
                    results = pool.map(
                        lambda p: embed_texts(self._url, self._model, [t for _, t in p]), parts
                    )
                    for part, vecs in zip(parts, results):
                        for (h, _), vector in zip(part, vecs):
                            blobs[h] = self._pack(vector)
                    flush()
                    self.done = self.total - pending + min(off + EMBED_BATCH * EMBED_WORKERS, len(todo))

            # Не менявшиеся страницы: их векторы уже лежат в кэше под тем же хэшем.
            missing = sorted({h for _, _, h in pages if h not in blobs})
            for off in range(0, len(missing), 500):
                part = missing[off:off + 500]
                blobs.update(db.execute(
                    f"SELECT h, v FROM vec WHERE h IN ({','.join('?' * len(part))})", part
                ))
            # Пропавшие страницы (переиндексация сократила pages) чистим.
            live = {source for source, _, _ in pages}
            db.executemany("DELETE FROM vec WHERE source = ?",
                           [(source,) for (source,) in db.execute("SELECT source FROM vec") if source not in live])
            db.commit()

            self._sources = [source for source, _, _ in pages]
            self._sections = [section for _, section, _ in pages]
            self._matrix = (
                np.stack([np.frombuffer(blobs[h], dtype=np.float16) for _, _, h in pages])
                if pages else np.zeros((0, 1), dtype=np.float16)
            )
            self.ready.set()
            logger.info("Help vector index ready: %d pages", len(pages))
        finally:
            db.close()

    def _pack(self, vector: list[float]) -> bytes:
        np = self._np
        v = np.asarray(vector, dtype=np.float32)
        norm = float(np.linalg.norm(v)) or 1.0
        return (v / norm).astype(np.float16).tobytes()

    def search(self, query: str, k: int, section: str = "") -> list[tuple[str, float]]:
        """Топ-k (source, косинус) по смыслу; пустой section — без фильтра."""
        np = self._np
        q = np.asarray(embed_texts(self._url, self._model, [query])[0], dtype=np.float32)
        q = (q / (np.linalg.norm(q) or 1.0)).astype(np.float16)
        scores = (self._matrix @ q).astype(np.float32)
        if section:
            keep = np.fromiter((s == section for s in self._sections), dtype=bool, count=len(self._sections))
            scores[~keep] = -np.inf
        k = min(k, len(scores))
        if k <= 0:
            return []
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [(self._sources[i], float(scores[i])) for i in top if scores[i] > -np.inf]
