"""Тесты справочника встроенных функций BSL и инструмента bsl_syntax_help."""

import asyncio

import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from mcp_baf import bsl
from mcp_baf.tools import bsl_help
from mcp_baf.tools.bsl_help import format_functions


def test_data_complete():
    assert len(bsl.BUILTIN_FUNCTIONS) == 180
    for fn in bsl.BUILTIN_FUNCTIONS:
        assert fn["name"] and fn["name_en"], fn
        assert fn["description"] and fn["syntax"], fn["name"]


def test_search_russian():
    results = bsl.search("СтрНайти")
    assert [f["name"] for f in results] == ["СтрНайти"]
    assert results[0]["name_en"] == "StrFind"


def test_search_english_case_insensitive():
    results = bsl.search("strfind")
    assert [f["name"] for f in results] == ["СтрНайти"]


def test_search_substring_multiple():
    # Подстрока "Стр" встречается во многих функциях (СтрНайти, СтрДлина, ...).
    results = bsl.search("Стр")
    names = [f["name"] for f in results]
    assert "СтрНайти" in names
    assert "СтрДлина" in names
    assert len(results) > 5


def test_search_not_found():
    assert bsl.search("НетТакойФункции123") == []


def test_format_functions():
    text = format_functions(bsl.search("СтрДлина"))
    assert text.startswith("## СтрДлина / StrLen")
    assert "**Синтаксис:** `СтрДлина(<Строка>)`" in text
    assert "```bsl" in text


def test_format_multiple_separated():
    text = format_functions(bsl.search("Стр")[:2])
    assert "\n---\n" in text


def _call_help(query):
    mcp = MCPServer("t")
    bsl_help.register(mcp, _Audit())
    return asyncio.run(mcp.call_tool("bsl_syntax_help", {"query": query})).content[0].text


class _Audit:
    def write(self, *a, **k):
        pass


def test_syntax_help_rejects_short_query():
    for q in ("", " ", "с"):
        with pytest.raises(ToolError, match="минимум"):
            _call_help(q)


def test_syntax_help_caps_results():
    total = len(bsl.search("Стр"))
    assert total > bsl_help.MAX_FUNCTIONS
    text = _call_help("Стр")
    assert text.count("**Синтаксис:**") == bsl_help.MAX_FUNCTIONS
    assert f"из {total}" in text
