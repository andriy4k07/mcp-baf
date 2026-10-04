"""Тесты состава MCP-сервера и аудита жизненного цикла."""

import asyncio
import json
import httpx
from mcp.client import Client
from mcp.server.mcpserver import MCPServer

from mcp_baf.config import Config
from mcp_baf.server import create_server
from mcp_baf.client import OneCClient
from mcp_baf.access import TOOL_METHODS

# Без --dump search_code не регистрируется (нет индекса выгрузки).
EXPECTED_TOOLS = {
    "get_metadata_tree",
    "get_object_structure",
    "execute_query",
    "validate_query",
    "get_event_log",
    "get_form_structure",
    "get_configuration_info",
    "bsl_syntax_help",
    "find_object_references",
    "get_object_link",
    "get_metadata_rights",
    "bsl_analyze",
    "bsl_format",
}


def test_registered_tools(tmp_path, monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"methods": list(TOOL_METHODS.values())}))
    monkeypatch.setattr("mcp_baf.server.OneCClient", lambda config, **kw: OneCClient(config, transport, **kw))
    server = create_server(
        Config(base_url="http://test/hs/mcp-baf", cache_dir=str(tmp_path))
    )
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == EXPECTED_TOOLS
    assert all(t.annotations.read_only_hint for t in tools)
    asyncio.run(server.access_client.aclose())


def test_optional_tools_and_unavailable_database(tmp_path):
    server = create_server(Config(base_url="http://test", cache_dir=str(tmp_path),
                                  help_dir=str(tmp_path)))
    # Все опции регистрируют локальные инструменты, независимо от их готовности.
    tools = asyncio.run(MCPServer.list_tools(server))
    assert {t.name for t in tools} == EXPECTED_TOOLS | {
        "search_platform_help", "get_platform_element",
    }
    async def close():
        async with Client(server):
            pass
    asyncio.run(close())


def test_lifespan_writes_server_start_stop(tmp_path):
    server = create_server(
        Config(base_url="http://test/hs/mcp-baf", cache_dir=str(tmp_path))
    )

    async def exercise_lifespan():
        async with Client(server):
            pass

    asyncio.run(exercise_lifespan())

    events = [
        json.loads(line)
        for line in (tmp_path / "audit.log").read_text("utf-8").splitlines()
    ]
    names = [e["event"] for e in events]
    assert "server.start" in names
    assert "server.stop" in names

    start = next(e for e in events if e["event"] == "server.start")
    assert start["service"] == "mcp-baf"
    assert start["base_url"] == "http://test/hs/mcp-baf"
    # Пароль в аудит не попадает.
    assert "password" not in start


def test_every_tool_is_classified_as_http_or_local(tmp_path):
    # Инструмент вне TOOL_METHODS считается локальным и не проверяет права:
    # новый HTTP-инструмент обязан попасть в карту, а не сюда по умолчанию.
    local = {"bsl_syntax_help", "bsl_analyze", "bsl_format", "search_code",
             "search_platform_help", "get_platform_element"}
    server = create_server(Config(base_url="http://test", cache_dir=str(tmp_path),
                                  help_dir=str(tmp_path), dump_dir=str(tmp_path)))
    names = {t.name for t in asyncio.run(MCPServer.list_tools(server))}
    assert names == set(TOOL_METHODS) | local
    assert not set(TOOL_METHODS) & local
    async def close():
        async with Client(server):
            pass
    asyncio.run(close())
