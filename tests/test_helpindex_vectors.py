"""Векторні та гібридні режими search_platform_help (issue #170): офлайн-кейси з моками.

Справжніх сетейых вызовов здесь нет: embed_texts/rerank_scores подменяются
monkeypatch до того, как HelpVectorStore/HelpIndex успеют их дёрнуть.
"""

import sqlite3
import threading
import time

import pytest
from test_helpindex import FIXTURE, make_hbk

import mcp_baf.dumpindex.vectors as dv
import mcp_baf.helpindex.vectors as hv
from mcp_baf.helpindex import HelpIndex

# Vector/hybrid search needs numpy (the [rag] extra); CI runs without it,
# so the whole module skips cleanly instead of failing (same guard as
# tests/test_vectors.py).
pytest.importorskip(
    "numpy", reason="vector search needs the [rag] extra: pip install mcp-baf[rag]"
)

EMBED = "http://embed.invalid/v1"
RERANK = "http://rerank.invalid/v1"
# Заголовки страниц tests/testdata/platform.hbk — на них строим фейковый эмбеддер.
TITLES = ["Запрос", "КонструкторЗапроса", "HTTPСоединение", "СтрНайти", "Для", "Остатки"]


def fake_embed(url, model, texts):
    """Детерминированный эмбеддер: one-hot по вхождению заголовка страницы в текст."""
    return [[1.0 if t0 in t else 0.0 for t0 in TITLES] for t in texts]


def create_index_with(tmp_path, **kwargs):
    root = tmp_path / "8.3.14"
    root.mkdir(exist_ok=True)
    (root / "platform.hbk").write_bytes(FIXTURE.read_bytes())
    index = HelpIndex(str(root), str(tmp_path / "cache"), **kwargs)
    assert index.wait_ready(5)
    assert index.error is None
    return index, root


def page_count(index):
    with sqlite3.connect(index.database) as connection:
        return connection.execute("SELECT count(*) FROM pages").fetchone()[0]


def vector_db(tmp_path):
    files = list((tmp_path / "cache").glob("help-vectors-*"))
    assert len(files) == 1
    return files[0]


def vector_rows(db_path):
    with sqlite3.connect(db_path) as connection:
        return connection.execute("SELECT count(*) FROM vec").fetchone()[0]


def block_network(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("bm25 mode must not touch the network")
    monkeypatch.setattr(hv, "embed_texts", boom)
    monkeypatch.setattr(hv, "rerank_scores", boom)
    monkeypatch.setattr(dv, "embed_texts", boom)
    monkeypatch.setattr(dv, "rerank_scores", boom)


def test_default_bm25_makes_no_network_calls(tmp_path, monkeypatch):
    # Без --embed-url векторного шара нет вовсе, а bm25 не дёргает embed/rerank.
    block_network(monkeypatch)
    index, _ = create_index_with(tmp_path)
    try:
        assert index.has_vectors() is False
        assert index.wait_vectors(1) is False
        assert index.search("Запрос")[0]["title"] == "Запрос"
        assert index.search("СтрНайти", mode="bm25")[0]["title"].startswith("СтрНайти")
    finally:
        index.close()
    assert not list((tmp_path / "cache").glob("help-vectors-*"))


def test_mode_validation(tmp_path, monkeypatch):
    block_network(monkeypatch)
    index, _ = create_index_with(tmp_path)
    try:
        with pytest.raises(ValueError, match="bm25, vector, hybrid"):
            index.search("Запрос", mode="smart")
        with pytest.raises(ValueError, match="bm25, vector, hybrid"):
            index.search_with_note("Запрос", mode="hybridh")
    finally:
        index.close()


def test_hybrid_without_reranker_degrades_to_bm25_with_note(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("reranker is not configured: must not be called")
    monkeypatch.setattr(hv, "rerank_scores", boom)
    index, _ = create_index_with(tmp_path)  # ни embed, ни rerank
    try:
        assert index.has_vectors() is False
        rows, note = index.search_with_note("Запрос", mode="hybrid")
        assert [r["title"] for r in rows] == [r["title"] for r in index.search("Запрос")]
        assert "векторный индекс недоступен" in note and "реранкер" in note
    finally:
        index.close()


def test_hybrid_dead_reranker_falls_back_to_bm25_with_note(tmp_path, monkeypatch):
    def dead(url, model, query, docs):
        raise ConnectionError("connection refused")
    monkeypatch.setattr(hv, "rerank_scores", dead)
    index, _ = create_index_with(tmp_path, rerank_url=RERANK)
    try:
        rows, note = index.search_with_note("Запрос", mode="hybrid")
        assert [r["title"] for r in rows] == [r["title"] for r in index.search("Запрос")]
        assert "векторный индекс недоступен" in note and "connection refused" in note
    finally:
        index.close()


def test_hybrid_reranks_bm25_candidates(tmp_path, monkeypatch):
    seen = {}
    def scoring(url, model, query, docs):
        seen["docs"] = docs
        return [float(i) for i in range(len(docs))]  # инвертирует порядок BM25
    monkeypatch.setattr(hv, "rerank_scores", scoring)
    index, _ = create_index_with(tmp_path, rerank_url=RERANK)
    try:
        bm25 = index.search("Запрос", limit=50)
        rows, note = index.search_with_note("Запрос", limit=2, mode="hybrid")
        assert note == ""
        assert len(rows) == 2
        assert rows[0]["title"] == bm25[len(bm25) - 1]["title"]  # реранкер перевернул выдачу
        assert rows[0]["score"] > rows[1]["score"]
        assert len(seen["docs"]) == len(bm25)  # кандидатов не больше HYBRID_CANDIDATES
        assert all(d.startswith(c["title"]) for d, c in zip(seen["docs"], bm25))
    finally:
        index.close()


def test_dead_embed_server_build_error_and_vector_message(tmp_path, monkeypatch):
    def dead(url, model, texts):
        raise ConnectionError("embed down")
    monkeypatch.setattr(hv, "embed_texts", dead)
    index, _ = create_index_with(tmp_path, embed_url=EMBED)
    try:
        assert index.has_vectors() is True
        assert index.wait_vectors(10) is False
        assert index._vectors.error is not None
        with pytest.raises(RuntimeError, match="векторный индекс недоступен"):
            index.search("Запрос", mode="vector")
        # bm25 по-прежнему работает без сети
        assert index.search("Запрос")[0]["title"] == "Запрос"
    finally:
        index.close()


def test_vector_cache_builds_reuses_and_rebuilds(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(hv, "embed_texts", lambda url, model, texts: (calls.extend(texts), fake_embed(url, model, texts))[1])
    index, root = create_index_with(tmp_path, embed_url=EMBED)
    try:
        assert index.wait_vectors(10) is True
        assert index._vectors.error is None
        assert page_count(index) == vector_rows(vector_db(tmp_path))
        assert len(calls) == page_count(index)  # на холодную сборку эмбедится каждая страница
    finally:
        index.close()

    # Повторное открытие: кэш векторов переиспользуется без единого вызова эмбеддера.
    def must_not_embed(url, model, texts):
        raise AssertionError("cached vectors must be reused")
    monkeypatch.setattr(hv, "embed_texts", must_not_embed)
    cached = create_index_with(tmp_path, embed_url=EMBED)[0]
    try:
        assert cached.wait_vectors(10) is True
        assert cached._vectors.error is None
    finally:
        cached.close()

    # Новая страница в .hbk: доэмбедится только она, остальные — из кэша.
    calls2 = []
    monkeypatch.setattr(hv, "embed_texts", lambda url, model, texts: (calls2.extend(texts), fake_embed(url, model, texts))[1])
    (root / "extra.hbk").write_bytes(make_hbk(
        {"functions/number.html": "<title>Число (Number)</title><p>Синтаксис: Число(Значение)</p>"}))
    updated = create_index_with(tmp_path, embed_url=EMBED)[0]
    try:
        assert updated.wait_vectors(10) is True
        assert updated.search("Number")
        assert len(calls2) == 1 and "Число" in calls2[0]
        assert vector_rows(vector_db(tmp_path)) == page_count(updated)
    finally:
        updated.close()


def test_vector_mode_semantic_search_and_section_filter(tmp_path, monkeypatch):
    monkeypatch.setattr(hv, "embed_texts", fake_embed)
    index, _ = create_index_with(tmp_path, embed_url=EMBED)
    try:
        assert index.wait_vectors(10) is True
        rows, note = index.search_with_note("HTTPСоединение", mode="vector")
        assert note == ""
        assert rows[0]["title"].startswith("HTTPСоединение")
        assert rows[0]["score"] > 0
        # Фильтр раздела работает и в векторном режиме: «Остатки» из types в functions не пустят.
        rows, _ = index.search_with_note("Остатки", mode="vector", section="functions")
        assert rows and all(r["section"] == "functions" for r in rows)
        assert rows[0]["title"].startswith("СтрНайти")  # единственный functions-вектор
        # Запрос с пустыми токенами валидируется и в векторном режиме.
        with pytest.raises(ValueError):
            index.search("   ", mode="vector")
    finally:
        index.close()


def test_vector_mode_dead_embedder_after_build_reports_cleanly(tmp_path, monkeypatch):
    monkeypatch.setattr(hv, "embed_texts", fake_embed)
    index, _ = create_index_with(tmp_path, embed_url=EMBED)
    try:
        assert index.wait_vectors(10) is True

        def dead(url, model, texts):  # эмбеддер лёг уже после сборки индекса
            raise ConnectionError("embed down")
        monkeypatch.setattr(hv, "embed_texts", dead)
        with pytest.raises(RuntimeError, match="векторный индекс недоступен"):
            index.search("Запрос", mode="vector")
    finally:
        index.close()


# ---------------------------------------------------------------------------
# Покрыття гепів, знайдених ревью (rev01 пункт 2 + korrectnist E): cold-build
# fallback, ре-ембед зміненої сторінки, чистка видалених, MCP-схема, секційна
# валідація у vector та порядок текстів помилок сумісний з main.
# ---------------------------------------------------------------------------


def vector_sources(db_path):
    with sqlite3.connect(db_path) as connection:
        return {row[0] for row in connection.execute("SELECT source FROM vec")}


def test_vector_mode_during_cold_build_degrades_to_bm25_with_note(tmp_path, monkeypatch):
    # (a) Поки cold build стоїть на першій пачці: vector видає BM25 + примітку, не помилку.
    gate = threading.Event()

    def slow_embed(url, model, texts):
        assert gate.wait(10), "embed mock wedged: test bug"
        return fake_embed(url, model, texts)

    monkeypatch.setattr(hv, "embed_texts", slow_embed)
    index, _ = create_index_with(tmp_path, embed_url=EMBED)
    try:
        deadline = time.monotonic() + 10  # дочекатись, доки потік-будівник перелічить сторінки
        while index._vectors.total == 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert index._vectors.total > 0
        assert not index._vectors.ready.is_set() and index._vectors.error is None
        rows, note = index.search_with_note("Запрос", mode="vector")
        assert [r["title"] for r in rows] == [r["title"] for r in index.search("Запрос")]
        assert "векторный индекс строится" in note and "BM25" in note
    finally:
        gate.set()
        index.close()


def test_changed_page_text_reembeds_only_that_page(tmp_path, monkeypatch):
    # (b) Правка тексту наявної .hbk-сторінки: sha256-ключ змінюється -> ре-ембед РІВНО її.
    from mcp_baf.helpindex.hbk import read_pages

    calls = []
    monkeypatch.setattr(hv, "embed_texts", lambda url, model, texts: (calls.extend(texts), fake_embed(url, model, texts))[1])
    index, root = create_index_with(tmp_path, embed_url=EMBED)
    try:
        assert index.wait_vectors(10) is True
        assert len(calls) == page_count(index)
    finally:
        index.close()

    pages = dict(read_pages(FIXTURE))
    victim = next(path for path, html in pages.items() if "СтрНайти" in html)
    pages[victim] = pages[victim].replace("СтрНайти", "СтрНайтиОновлена")
    (root / "platform.hbk").write_bytes(make_hbk(pages))
    n = page_count(index)
    # Створюємо HelpIndex напряму: create_index_with перезаписав би файл вихідним FIXTURE.
    reopened = HelpIndex(str(root), str(tmp_path / "cache"), embed_url=EMBED)
    try:
        assert reopened.wait_ready(5) and reopened.error is None
        assert reopened.wait_vectors(10) is True
        assert page_count(reopened) == n
        assert len(calls) == n + 1  # +1: пере-ембеджено лише відредатовану сторінку
        assert "СтрНайтиОновлена" in calls[-1]
        assert vector_rows(vector_db(tmp_path)) == n
    finally:
        reopened.close()


def test_deleted_page_purges_vector_cache_row(tmp_path, monkeypatch):
    # (c) Сторінка зникла з .hbk -> її рядок випаровується з векторного кешу.
    monkeypatch.setattr(hv, "embed_texts", fake_embed)
    index, root = create_index_with(tmp_path, embed_url=EMBED)
    try:
        assert index.wait_vectors(10) is True
    finally:
        index.close()
    (root / "extra.hbk").write_bytes(make_hbk(
        {"functions/number.html": "<title>Число (Number)</title><p>Синтаксис: Число(Значение)</p>"}))
    index = create_index_with(tmp_path, embed_url=EMBED)[0]
    try:
        assert index.wait_vectors(10) is True
        assert vector_rows(vector_db(tmp_path)) == page_count(index)
        assert any(s.startswith("extra.hbk::") for s in vector_sources(vector_db(tmp_path)))
    finally:
        index.close()
    (root / "extra.hbk").unlink()
    index = create_index_with(tmp_path, embed_url=EMBED)[0]
    try:
        assert index.wait_vectors(10) is True
        assert vector_rows(vector_db(tmp_path)) == page_count(index)
        assert not any(s.startswith("extra.hbk::") for s in vector_sources(vector_db(tmp_path)))
    finally:
        index.close()


def test_mcp_schema_mode_enum_and_default(tmp_path):
    # (d) MCP-контракт: обидва тули несуть enum + default bm25, mode не обов'язковий.
    import asyncio

    from mcp.server.mcpserver import MCPServer

    from mcp_baf.config import Config
    from mcp_baf.server import create_server

    server = create_server(Config(base_url="http://test", cache_dir=str(tmp_path), help_dir=str(tmp_path)))
    tools = asyncio.run(MCPServer.list_tools(server))
    seen = set()
    for tool in tools:
        if tool.name not in ("search_platform_help", "get_platform_element"):
            continue
        seen.add(tool.name)
        props = tool.input_schema["properties"]
        assert props["mode"]["enum"] == ["bm25", "vector", "hybrid"]
        assert props["mode"]["default"] == "bm25"
        assert "mode" not in (tool.input_schema.get("required") or [])
    assert seen == {"search_platform_help", "get_platform_element"}


def test_vector_mode_rejects_invalid_section(tmp_path, monkeypatch):
    # (e) vector/hybrid з недійсним section: ValueError, а не мовчазні [] від -inf-фільтра.
    monkeypatch.setattr(hv, "embed_texts", fake_embed)
    index, _ = create_index_with(tmp_path, embed_url=EMBED)
    try:
        assert index.wait_vectors(10) is True  # вектори готові: старий шлях повертав [] без помилки
        with pytest.raises(ValueError, match="section: functions, types, operators, vtables, skd"):
            index.search("Запрос", mode="vector", section="bogus")
        with pytest.raises(ValueError, match="section:"):
            index.search("Запрос", mode="hybrid", section="bogus")
    finally:
        index.close()


def test_error_text_compatibility_section_before_query(tmp_path, monkeypatch):
    # (f) Сумісність тексту/порядку помилок з main: mode -> section -> query.
    block_network(monkeypatch)
    index, _ = create_index_with(tmp_path)
    try:
        with pytest.raises(ValueError, match="mode: bm25, vector, hybrid"):
            index.search("   ", 5, "bogus", mode="smart")  # mode перший
        with pytest.raises(ValueError, match="section: functions, types, operators, vtables, skd"):
            index.search("   ", 5, "bogus")  # два невалідних: section перший (як у main)
        with pytest.raises(ValueError, match="query должен"):
            index.search("   ", 5, "")
        with pytest.raises(ValueError, match="query должен"):
            index.search_with_note("   ", 5, "", mode="vector")  # валідатор і до диспетчера vector
    finally:
        index.close()
