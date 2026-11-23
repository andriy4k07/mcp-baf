"""Опциональный векторный кэш страниц справки платформы (issue #170).

Embed/rerank-клиент и общие примитивы НЕ дублируем: `embed_texts`,
`rerank_scores`, `endpoint`, а также `chunk_key`, `embed_in_batches` и
`top_k_by_cosine` переиспользуются из `mcp_baf.dumpindex.vectors` (тот же
OpenAI-совместимый /v1/embeddings и реранкер Qwen3). Нumpy нужен только при
включённом --embed-url, поэтому импортируется лениво в `_np`.

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

import logging
import sqlite3
import threading
from collections.abc import Callable, Iterable

from mcp_baf.dumpindex.vectors import (
    CHUNK_CHAR_BUDGET,
    EMBED_BATCH,
    EMBED_WORKERS,
    _np as load_numpy,
    chunk_key,
    embed_in_batches,
    embed_texts,
    endpoint,
    rerank_scores,
    top_k_by_cosine,
)

# Реэкспорт клиента из dumpindex (второй embed/rerank-клиент запрещён): их зовёт
# HelpIndex._search_hybrid через этот namespace и патчат офлайн-тесты.
__all__ = ["CHUNK_CHAR_BUDGET", "EMBED_BATCH", "EMBED_WORKERS", "HelpVectorStore", "embed_texts",
           "endpoint", "page_chunk", "rerank_scores"]

logger = logging.getLogger("mcp_baf.helpindex.vectors")

# Версия схемы векторного кэша; при её подъёме старые векторы сбрасываются.
CACHE_SCHEMA_VERSION = 1

# Явная ошибка остановленной сборки: wait_vectors не висит до таймаута (опрашивает
# error), а примітка режимів не бреше «індекс строится» на мёртвой побудові.
STOPPED_ERROR = "побудова зупинена"


def _np():
    """Ленивый numpy с сообщением про vector-режим (примітив спільний з dumpindex)."""
    return load_numpy("vector")


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
        return chunk_key(self._model, text)

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
                    self.error = RuntimeError(STOPPED_ERROR)
                    return
                for source, section, text in batch:
                    h = self._key(text)
                    pages.append((source, section, h))
                    if stored.get(source) != h:
                        pending += 1
                        new_texts.setdefault(h, text)
            self.total = len(pages)
            self.done = self.total - pending  # прогресс: страницы с готовым вектором

            blobs: dict[str, bytes] = {}

            def flush():
                """Готовые векторы сразу в кэш: прерванная сборка возобновляется."""
                rows = [(source, section, h, blobs[h])
                        for source, section, h in pages if h in blobs]
                db.executemany("INSERT OR REPLACE INTO vec(source, section, h, v) VALUES (?,?,?,?)", rows)
                db.commit()

            def on_batch(rows: list[tuple[str, bytes]]) -> None:
                for h, blob in rows:
                    blobs[h] = blob
                flush()
                self.done += len(rows)

            # Пачки в несколько потоков — спільний драйвер dumpindex: полный каталог
            # справки (~47k страниц) собирается минуты, а не часы. embed_texts берём
            # зі свого namespace, щоб офлайн-тести могли його підміняти.
            if not embed_in_batches(self._url, self._model, list(new_texts.items()),
                                    on_batch, should_stop, embed_texts):
                self.error = RuntimeError(STOPPED_ERROR)
                return

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

    def search(self, query: str, k: int, section: str = "") -> list[tuple[str, float]]:
        """Топ-k (source, косинус) по смыслу; пустой section — без фильтра."""
        mask = None
        if section:
            mask = self._np.fromiter((s == section for s in self._sections),
                                     dtype=bool, count=len(self._sections))
        hits = top_k_by_cosine(self._np, embed_texts, self._url, self._model,
                               self._matrix, query, k, mask)
        return [(self._sources[i], score) for i, score in hits]
