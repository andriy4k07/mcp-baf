"""Опциональный векторный индекс кода (гибридный поиск BM25 + embeddings).

Включается только при заданном --embed-url; иначе модуль не импортируется
и numpy не нужен. Код и запросы уходят на указанный сервер эмбеддингов
(OpenAI-совместимый /v1/embeddings) и, если задан --rerank-url, на реранкер.

Модуль — также единственный дом общих примитивов векторной слойки
(chunk_key/pack_vector/embed_in_batches/top_k_by_cosine): их потребляют и
VectorIndex (чанки BSL), и helpindex.HelpVectorStore (страницы .hbk). Держать
вторую копию в helpindex запрещено — кэши тихо разойдутся.

- чанк = один метод BSL (с комментариями над ним); модуль без методов — один
  «головной» чанк; код вне методов пропускается;
- кэш — отдельный SQLite-файл рядом с index.db: sha256(модель + текст чанка)
  -> нормированный float16-вектор; пересчитываются только новые чанки;
- матрица векторов держится в RAM, поиск — косинус через matrix @ query.
"""

from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import NamedTuple

import httpx

logger = logging.getLogger("mcp_baf.dumpindex.vectors")

# Лимит эмбеддера — 2048 токенов; ~3000 символов обычно влезают, редкие
# плотные чанки сжимаются повтором с усечением (см. embed_texts).
CHUNK_CHAR_BUDGET = 3000
EMBED_BATCH = 64
EMBED_WORKERS = 4
EMBED_TIMEOUT = 120.0
RERANK_TIMEOUT = 60.0
RRF_K = 60
# shortcut: шаблон жёстко под Qwen3-Reranker; для другого --rerank-model — сделать шаблон настраиваемым.
RERANK_TASK = "Given a question about business logic, retrieve the 1C:Enterprise BSL method that implements it"
RERANK_PREFIX = (
    "<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and "
    'the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
)
RERANK_SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"

_START_RE = re.compile(r"^\s*(процедура|функция|procedure|function)\s", re.IGNORECASE)
_END_RE = re.compile(
    r"^\s*(конецпроцедуры|конецфункции|endprocedure|endfunction)\b", re.IGNORECASE
)


class Chunk(NamedTuple):
    doc_id: int
    module: str
    category: str
    module_type: str
    start: int  # первая строка чанка (с 1), включая комментарии над методом
    end: int


def chunk_module(name: str, content: str) -> list[tuple[int, int, str]]:
    """Режет модуль на методы: [(start_line, end_line, text)], строки с 1."""
    lines = content.split("\n")

    def make(start: int, end: int) -> tuple[int, int, str]:
        body = "\n".join(lines[start - 1:end])
        return start, end, f"{name}\n{body}"[:CHUNK_CHAR_BUDGET]

    chunks = []
    i, n = 0, len(lines)
    while i < n:
        if not _START_RE.match(lines[i]):
            i += 1
            continue
        begin = i
        while begin > 0 and lines[begin - 1].lstrip().startswith(("//", "&")):
            begin -= 1
        j = i
        while j < n and not _END_RE.match(lines[j]):
            j += 1
        chunks.append(make(begin + 1, min(j + 1, n)))
        i = j + 1
    if not chunks and content.strip():
        chunks.append(make(1, n))
    return chunks


def endpoint(url: str, path: str) -> str:
    """Принимает и базовый адрес сервера, и полный endpoint: дописывает path, если его нет."""
    url = url.rstrip("/")
    return url if url.endswith(path.rsplit("/", 1)[-1]) else url + path


def _post(url: str, payload: dict, timeout: float) -> dict:
    # Connection: close — как в client.py; сервер не держит наши соединения.
    resp = httpx.post(url, json=payload, headers={"Connection": "close"}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def embed_texts(url: str, model: str, texts: list[str]) -> list[list[float]]:
    try:
        return _embed(url, model, texts)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 400:
            raise
        # 400 = какой-то вход длиннее контекста модели: режем по одному и усекаем.
        return [_embed_truncating(url, model, t) for t in texts]


def _embed_truncating(url: str, model: str, text: str) -> list[float]:
    while True:
        try:
            return _embed(url, model, [text])[0]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 400 or len(text) <= 200:
                raise
            text = text[: len(text) // 2]


def _embed(url: str, model: str, texts: list[str]) -> list[list[float]]:
    data = _post(url, {"model": model, "input": texts}, EMBED_TIMEOUT)["data"]
    data.sort(key=lambda d: d["index"])
    if len(data) != len(texts):
        raise RuntimeError(f"embedder returned {len(data)} vectors for {len(texts)} inputs")
    return [d["embedding"] for d in data]


def rerank_scores(url: str, model: str, query: str, docs: list[str]) -> list[float]:
    # Qwen3-Reranker (seq-cls в vLLM) обучен на своём шаблоне; без него оценки размыты и порядок хуже RRF.
    query = RERANK_PREFIX + "<Instruct>: " + RERANK_TASK + "\n<Query>: " + query + "\n"
    docs = ["<Document>: " + d + RERANK_SUFFIX for d in docs]
    results = _post(endpoint(url, "/v1/rerank"), {"model": model, "query": query, "documents": docs}, RERANK_TIMEOUT)["results"]
    scores = [0.0] * len(docs)
    for r in results:
        scores[r["index"]] = float(r["relevance_score"])
    return scores


def rrf_fuse(rankings: Iterable[list], k: int = RRF_K) -> list[tuple[object, float]]:
    """Reciprocal Rank Fusion: ключи из нескольких ранжирований -> [(ключ, score)] по убыванию."""
    scores: dict = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda kv: -kv[1])


def _np(feature: str = "hybrid"):
    try:
        import numpy
    except ImportError as exc:
        raise RuntimeError(
            f"{feature} search needs numpy: pip install mcp-baf[rag]"
        ) from exc
    return numpy


# ---------------------------------------------------------------------------
# Общие примитивы векторной слойки. Их потребляют VectorIndex (чанки BSL) и
# helpindex.HelpVectorStore (страницы .hbk): одинаковый ключ кэша, одинаковое
# пакование float16, один драйвер пачкового эмбеддинга и один top-k по косинусу.
# ---------------------------------------------------------------------------

def chunk_key(model: str, text: str) -> str:
    """Ключ кэша чанка: sha256(модель + \\0 + текст)."""
    return hashlib.sha256((model + "\0" + text).encode("utf-8")).hexdigest()


def pack_vector(np, vector: list[float]) -> bytes:
    """Нормированный float16-blob: float32 -> /||v|| -> float16."""
    v = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(v)) or 1.0
    return (v / norm).astype(np.float16).tobytes()


def embed_in_batches(url: str, model: str, todo: list[tuple],
                     on_batch: Callable[[list[tuple]], None],
                     should_stop: Callable[[], bool] | None = None,
                     embed: Callable[[str, str, list[str]], list[list[float]]] | None = None) -> bool:
    """Эмбедит пары (ключ, текст) пачками EMBED_BATCH в EMBED_WORKERS потоков.

    on_batch получает [(ключ, float16-blob)] на каждую пачку: вызывающий коммитит
    в свой кэш на лету, поэтому прерванная сборка возобновляется с того же места.
    embed — инъекция клиента (helpindex передаёт свой ре-экспорт, чтобы офлайн-
    тесты патчили hv.embed_texts); по умолчанию — embed_texts этого модуля.
    Возвращает False, если should_stop остановил цикл (готовое — уже в кэше).
    """
    embed = embed_texts if embed is None else embed
    np = _np()
    with ThreadPoolExecutor(EMBED_WORKERS) as pool:
        for off in range(0, len(todo), EMBED_BATCH * EMBED_WORKERS):
            if should_stop is not None and should_stop():
                return False
            parts = [todo[o:o + EMBED_BATCH]
                     for o in range(off, min(off + EMBED_BATCH * EMBED_WORKERS, len(todo)), EMBED_BATCH)]
            results = pool.map(lambda p: embed(url, model, [t for _, t in p]), parts)
            for part, vecs in zip(parts, results):
                on_batch([(k, pack_vector(np, v)) for (k, _), v in zip(part, vecs)])
    return True


def top_k_by_cosine(np, embed, url: str, model: str, matrix, query: str, k: int,
                    mask=None) -> list[tuple[int, float]]:
    """Топ-k по косинусу: эмбеддинг запроса -> matrix @ q -> argpartition/argsort.

    mask — булев фильтр строк матрицы (section/category/module): выключенные
    становятся -inf и выпадают из выдачи. Возвращает [(индекс строки, косинус)]
    по убыванию скора; пустой список при k<=0 или пустой матрице.
    """
    q = np.asarray(embed(url, model, [query])[0], dtype=np.float32)
    q = (q / (np.linalg.norm(q) or 1.0)).astype(np.float16)
    scores = (matrix @ q).astype(np.float32)
    if mask is not None:
        scores[~mask] = -np.inf
    k = min(k, len(scores))
    if k <= 0:
        return []
    top = np.argpartition(-scores, k - 1)[:k]
    top = top[np.argsort(-scores[top])]
    return [(int(i), float(scores[i])) for i in top if scores[i] > -np.inf]


class VectorIndex:
    def __init__(self, embed_url: str, embed_model: str, db_path: str) -> None:
        self._np = _np()  # fail fast при старте, а не при первом запросе
        self._url = endpoint(embed_url, "/v1/embeddings")
        self._model = embed_model
        self._db_path = db_path or ":memory:"
        self.ready = threading.Event()
        self.error: Exception | None = None
        self.done = 0
        self.total = 0
        self.chunks: list[Chunk] = []
        self._matrix = None
        # имя модуля -> [(start, end, индекс чанка)] для привязки строки BM25 к методу
        self._by_name: dict[str, list[tuple[int, int, int]]] = {}

    def _key(self, text: str) -> str:
        return chunk_key(self._model, text)

    def build(self, batches: Iterable[list[tuple]], should_stop: Callable[[], bool]) -> None:
        """batches: списки (doc_id, name, category, module_type, content). Ошибка -> self.error."""
        try:
            self._build(batches, should_stop)
        except Exception as exc:  # noqa: BLE001 — не валим сервер, hybrid деградирует до BM25
            logger.error("Vector index build failed: %s", exc)
            self.error = exc

    def _build(self, batches, should_stop) -> None:
        np = self._np
        db = sqlite3.connect(self._db_path, timeout=30, check_same_thread=False)
        try:
            db.execute("CREATE TABLE IF NOT EXISTS vec(h TEXT PRIMARY KEY, v BLOB) WITHOUT ROWID")
            chunks: list[Chunk] = []
            keys: list[str] = []
            texts: dict[str, str] = {}  # ключ -> текст, только чего нет в кэше
            for batch in batches:
                if should_stop():
                    return
                pending: dict[str, str] = {}
                for doc_id, name, cat, mod, content in batch:
                    for start, end, text in chunk_module(name, content):
                        chunks.append(Chunk(doc_id, name, cat, mod, start, end))
                        k = self._key(text)
                        keys.append(k)
                        pending[k] = text
                have = self._cached(db, list(pending))
                texts.update((k, t) for k, t in pending.items() if k not in have)
            self.total = len(chunks)
            self.done = self.total - len(texts)  # прогресс: чанки, уже имеющие вектор

            def on_batch(rows):
                db.executemany("INSERT OR REPLACE INTO vec VALUES (?, ?)", rows)
                db.commit()  # каждая пачка сразу в кэш: прерванная сборка возобновляется
                self.done += len(rows)

            if not embed_in_batches(self._url, self._model, list(texts.items()), on_batch, should_stop):
                return

            # Матрица в порядке чанков; заодно чистим устаревшие строки кэша.
            vecs = {}
            uniq = list(set(keys))
            for off in range(0, len(uniq), 500):
                vecs.update(self._cached(db, uniq[off:off + 500]))
            # shortcut: матрица float16 целиком в RAM (~150 МБ на 72k чанков),
            # при выгрузках сильно больше — перейти на ANN-индекс (hnswlib/faiss).
            self._matrix = (
                np.stack([np.frombuffer(vecs[k], dtype=np.float16) for k in keys])
                if keys else np.zeros((0, 1), dtype=np.float16)
            )
            live = set(keys)
            stale = [(h,) for (h,) in db.execute("SELECT h FROM vec") if h not in live]
            db.executemany("DELETE FROM vec WHERE h = ?", stale)
            db.commit()
            self.chunks = chunks
            for i, c in enumerate(chunks):
                self._by_name.setdefault(c.module, []).append((c.start, c.end, i))
            self.ready.set()
            logger.info("Vector index ready: %d chunks", len(chunks))
        finally:
            db.close()

    @staticmethod
    def _cached(db: sqlite3.Connection, keys: list[str]) -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        for off in range(0, len(keys), 500):
            part = keys[off:off + 500]
            out.update(db.execute(
                "SELECT h, v FROM vec WHERE h IN (%s)" % ",".join("?" * len(part)), part
            ))
        return out

    def chunk_at(self, module: str, line: int) -> int | None:
        """Индекс чанка-метода, содержащего строку модуля; None — строка вне методов."""
        for start, end, i in self._by_name.get(module, ()):
            if start <= line <= end:
                return i
        return None

    def search(self, query: str, k: int, category: str = "", module: str = "") -> list[int]:
        """Индексы топ-k чанков по косинусной близости (с фильтрами category/module)."""
        mask = None
        if category or module:
            mask = self._np.fromiter(
                ((not category or c.category == category) and (not module or c.module_type == module)
                 for c in self.chunks),
                dtype=bool, count=len(self.chunks),
            )
        return [i for i, _ in top_k_by_cosine(self._np, embed_texts, self._url, self._model,
                                              self._matrix, query, k, mask)]
