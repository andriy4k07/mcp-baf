"""Тесты гибридного поиска: чанкер, кэш векторов, RRF, реранкер (без сети)."""

import time

import httpx
import pytest

from mcp_baf.dumpindex import DumpIndex, SearchParams, vectors as vx

np = pytest.importorskip("numpy")

MODULE = (
    "// Считает себестоимость\n"
    "&НаСервере\n"
    "Функция Себестоимость(Номенклатура)\n"
    "    Возврат 1;\n"
    "КонецФункции\n"
    "\n"
    "Процедура ПередЗаписью()\n"
    "    Проверка = 2;\n"
    "КонецПроцедуры\n"
    "Перем Х;\n"
)


def fake_embed(texts):
    """Детерминированный «эмбеддинг»: слова про себестоимость -> ось 0, остальное -> ось 1."""
    return [[1.0, 0.0, 0.0] if "ебестоимость" in t else [0.0, 1.0, 0.0] for t in texts]


@pytest.fixture
def calls(monkeypatch):
    log = {"embed": [], "rerank": 0, "fail_rerank": False}

    def post(url, payload, timeout):
        if url.endswith("/embeddings"):
            log["embed"].append(list(payload["input"]))
            return {"data": [{"index": i, "embedding": v}
                             for i, v in enumerate(fake_embed(payload["input"]))]}
        log["rerank"] += 1
        if log["fail_rerank"]:
            raise httpx.ConnectError("down")
        docs = payload["documents"]
        return {"results": [{"index": i, "relevance_score": 1.0 if "ебестоимость" in d else 0.0} for i, d in enumerate(docs)]}

    monkeypatch.setattr(vx, "_post", post)
    return log


def test_chunker_methods_comments_and_headless():
    chunks = vx.chunk_module("М", MODULE)
    assert [(s, e) for s, e, _ in chunks] == [(1, 5), (7, 9)]  # комментарий и &директива внутри чанка
    assert chunks[0][2].startswith("М\n// Считает")
    # модуль без методов -> один головной чанк; пустой -> ничего
    assert len(vx.chunk_module("М", "Перем А;\nПерем Б;")) == 1
    assert vx.chunk_module("М", "  \n") == []
    assert len(vx.chunk_module("М", "Процедура П()\n" + "x" * 9000 + "\nEndProcedure")[0][2]) == vx.CHUNK_CHAR_BUDGET


def test_rrf_fuse_prefers_items_in_both_rankings():
    fused = vx.rrf_fuse([["a", "b", "c"], ["c", "d", "a"]])
    assert [k for k, _ in fused][:2] == ["a", "c"]
    assert fused[0][1] == pytest.approx(1 / 61 + 1 / 63)


def make_index(tmp_path, **kw):
    path = tmp_path / "dump" / "CommonModules" / "Расчёты" / "Ext" / "Module.bsl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(MODULE, encoding="utf-8")
    return DumpIndex(str(tmp_path / "dump"), cache_dir=str(tmp_path / "cache"),
                     embed_url="http://x/v1/embeddings", **kw)


def test_incremental_cache_embeds_only_new_chunks(tmp_path, calls):
    ix = make_index(tmp_path)
    assert ix.wait_ready(30) and ix.wait_vectors(30)
    assert sum(map(len, calls["embed"])) == 2
    ix.close()
    calls["embed"].clear()
    ix = make_index(tmp_path)  # тёплый старт: всё из кэша
    assert ix.wait_vectors(30)
    assert calls["embed"] == []
    ix.close()


def test_hybrid_fuses_and_reranker_fallback(tmp_path, calls):
    ix = make_index(tmp_path, rerank_url="http://x/v1/rerank")
    assert ix.wait_vectors(30)
    ms, _ = ix.search(SearchParams("себестоимость", mode="hybrid", limit=5))
    assert ms[0].line == 1  # реранкер поставил метод себестоимости первым
    assert calls["rerank"] == 1
    calls["fail_rerank"] = True
    ms2, _ = ix.search(SearchParams("себестоимость", mode="hybrid", limit=5))
    assert ms2 and ms2[0].module == ms[0].module  # откат на RRF без ошибки
    ix.close()


def test_hybrid_while_vectors_building(tmp_path, calls, monkeypatch):
    import threading
    gate = threading.Event()
    orig = vx._post
    monkeypatch.setattr(vx, "_post", lambda *a: (gate.wait(10), orig(*a))[1])
    ix = make_index(tmp_path)
    assert ix.wait_ready(30)
    ms, _ = ix.search(SearchParams("себестоимость", mode="hybrid", limit=5))
    assert ms.note.startswith("векторный индекс строится")
    gate.set()
    assert ix.wait_vectors(30)
    ix.close()


def test_mode_absent_from_schema_without_embed_url():
    from mcp.server.mcpserver import MCPServer
    from mcp_baf.tools import search_code

    class Fake:
        def __init__(self, v):
            self.v = v

        def has_vectors(self):
            return self.v

    def modes(v):
        mcp = MCPServer("t")
        search_code.register(mcp, Fake(v), audit=None)
        tool = mcp._tool_manager.get_tool("search_code") if hasattr(mcp, "_tool_manager") else None
        return str(tool.parameters)

    assert "hybrid" not in modes(False)
    assert "hybrid" in modes(True)


def test_endpoint_accepts_base_or_full_url():
    assert vx.endpoint("http://h:8001", "/v1/embeddings") == "http://h:8001/v1/embeddings"
    assert vx.endpoint("http://h:8001/v1/embeddings/", "/v1/embeddings") == "http://h:8001/v1/embeddings"
    assert vx.endpoint("http://h:8002/", "/v1/rerank") == "http://h:8002/v1/rerank"


def test_rerank_uses_qwen3_template(monkeypatch):
    sent = {}

    def fake(url, payload, timeout):
        sent.update(payload)
        return {"results": [{"index": 0, "relevance_score": 0.9}]}

    monkeypatch.setattr(vx, "_post", fake)
    assert vx.rerank_scores("http://h", "m", "q", ["код"]) == [0.9]
    assert sent["query"].startswith("<|im_start|>system") and sent["query"].endswith("<Query>: q\n")
    assert sent["documents"][0].startswith("<Document>: код") and sent["documents"][0].endswith("</think>\n\n")


def test_wait_vectors_returns_early_on_build_error(tmp_path, monkeypatch):
    def down(url, payload, timeout):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(vx, "_post", down)
    index = make_index(tmp_path)
    try:
        start = time.monotonic()
        assert index.wait_vectors(30) is False
        assert time.monotonic() - start < 10
        matches, _ = index.search(SearchParams("Себестоимость", mode="hybrid"))
        assert "недоступен" in matches.note
    finally:
        index.close()
