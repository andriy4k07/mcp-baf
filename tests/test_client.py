"""Тесты аудита HTTP-вызовов 1С: ровно одно событие one_c.http на запрос."""

import asyncio
import json

import httpx

from mcp_baf_audit import AuditLog, set_trace_id
from mcp_baf.client import OneCClient, OneCError
from mcp_baf.config import Config


def _events(tmp_path):
    lines = (tmp_path / "audit.log").read_text("utf-8").splitlines()
    return [json.loads(line) for line in lines]


def _client(tmp_path, handler):
    audit = AuditLog(str(tmp_path))
    config = Config(base_url="http://test/hs/mcp-baf", cache_dir=str(tmp_path))
    return OneCClient(config, transport=httpx.MockTransport(handler), audit=audit)


def test_one_c_http_logged_on_success(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    set_trace_id(None)
    client = _client(tmp_path, handler)
    asyncio.run(client.post("/query", {"query": "ВЫБРАТЬ 1"}))
    asyncio.run(client.aclose())

    http = [e for e in _events(tmp_path) if e["event"] == "one_c.http"]
    assert len(http) == 1  # ровно одно событие на запрос
    e = http[0]
    assert e["ok"] is True
    assert e["status"] == 200
    assert e["payload"]["method"] == "POST"
    assert e["payload"]["endpoint"] == "/query"
    assert isinstance(e["payload"]["response_bytes"], int)
    assert isinstance(e["duration_ms"], int)
    # тело запроса/ответа не логируется
    assert "ВЫБРАТЬ" not in json.dumps(e, ensure_ascii=False)


def test_one_c_http_logged_on_error(tmp_path):
    def handler(request):
        return httpx.Response(500, text="boom")

    set_trace_id(None)
    client = _client(tmp_path, handler)
    try:
        asyncio.run(client.get("/version"))
    except OneCError:
        pass
    asyncio.run(client.aclose())

    http = [e for e in _events(tmp_path) if e["event"] == "one_c.http"]
    assert len(http) == 1
    e = http[0]
    assert e["ok"] is False
    assert e["level"] == "error"
    assert e["status"] == 500
    assert e["error"]


def test_one_c_http_inherits_tool_trace_id(tmp_path):
    """one_c.http наследует trace_id, выставленный traced_text для инструмента."""
    from mcp_baf.tools.common import traced_text

    def handler(request):
        return httpx.Response(200, json={"ok": True})

    audit = AuditLog(str(tmp_path))
    config = Config(base_url="http://test/hs/mcp-baf", cache_dir=str(tmp_path))
    client = OneCClient(config, transport=httpx.MockTransport(handler), audit=audit)

    async def scenario():
        async def run():
            await client.post("/query", {"query": "ВЫБРАТЬ 1"})
            return "ok"

        await traced_text(audit, "execute_query", run, args={})
        await client.aclose()

    set_trace_id(None)
    asyncio.run(scenario())

    events = _events(tmp_path)
    http = next(e for e in events if e["event"] == "one_c.http")
    call = next(e for e in events if e["event"] == "tool.call")
    assert http["trace_id"] == call["trace_id"]  # единая операция
    assert http["trace_id"]  # не null
