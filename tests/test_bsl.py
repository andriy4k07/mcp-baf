"""Тесты справочника встроенных функций BSL и инструмента bsl_syntax_help."""

from mcp_baf import bsl
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
