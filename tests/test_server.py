"""Тесты состава MCP-сервера и аудита жизненного цикла."""

import asyncio
import json

from mcp_baf.config import Config
from mcp_baf.server import create_server

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
}


def test_registered_tools(tmp_path):
    server = create_server(
        Config(base_url="http://test/hs/mcp-baf", cache_dir=str(tmp_path))
    )
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == EXPECTED_TOOLS


def test_lifespan_writes_server_start_stop(tmp_path):
    server = create_server(
        Config(base_url="http://test/hs/mcp-baf", cache_dir=str(tmp_path))
    )

    async def exercise_lifespan():
        async with server._mcp_server.lifespan(server._mcp_server):
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
