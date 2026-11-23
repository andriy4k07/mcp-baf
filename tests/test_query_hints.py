"""Подсказки «возможно, вы имели в виду» и советник по тексту запроса."""

import asyncio

import httpx
import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from mcp_baf_audit import AuditLog
from mcp_baf.client import OneCClient
from mcp_baf.config import Config
from mcp_baf.tools import query, validate_query
from mcp_baf.tools.query_hints import advise_query, parse_missing

TREE = {"Справочники": ["Номенклатура", "Контрагенты"], "Документы": ["РеализацияТоваров"]}
OBJ = {"attributes": [{"name": "Артикул"}], "tabularParts": []}


def setup(tmp_path, module, query_response, server=None):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path == "/metadata":
            return httpx.Response(200, json=TREE)
        if request.url.path.startswith("/object/"):
            return httpx.Response(200, json=OBJ)
        return query_response

    audit = AuditLog(str(tmp_path))
    client = OneCClient(Config(base_url="http://test"), httpx.MockTransport(handler), audit=audit)
    server = server or MCPServer("test")
    module.register(server, client, audit)
    return server, client, paths


def call(server, client, name, **args):
    async def go():
        try:
            return (await server.call_tool(name, args)).content[0].text
        finally:
            await client.aclose()
    return asyncio.run(go())


@pytest.mark.parametrize("text,expected", [
    ('Таблица не найдена "Справочник.Номенклатуре"', [("table", "Справочник.Номенклатуре")]),
    ("Таблицю не знайдено: Справочник.Номенклатуре", [("table", "Справочник.Номенклатуре")]),
    ('Поле не найдено "Т.Артикулл"', [("field", "Т.Артикулл")]),
    ("Поле не знайдено Артикулл", [("field", "Артикулл")]),
    ('Поле "Артикулл" не найдено', [("field", "Артикулл")]),
    # Реальные тексты validate_query с живой базы (uk).
    ('{(1, 30)}: Таблицю не знайдено "Справочник.Номенклатуре"\nВЫБРАТЬ ПЕРВЫЕ 1 Н.Ссылка ИЗ <<?>>Справочник.Номенклатуре КАК Н',
     [("table", "Справочник.Номенклатуре")]),
    ('{(1, 20)}: Поле не знайдено "Н.Артикулл"\nВЫБРАТЬ ПЕРВЫЕ 1 Н.<<?>>Артикулл ИЗ Справочник.Номенклатура КАК Н',
     [("field", "Н.Артикулл")]),
    ("что-то совсем другое", []),
])
def test_parse_missing(text, expected):
    assert parse_missing(text) == expected


REAL_TABLE = ('{(1, 30)}: Таблицю не знайдено "Справочник.Номенклатуре"\n'
              "ВЫБРАТЬ ПЕРВЫЕ 1 Н.Ссылка ИЗ <<?>>Справочник.Номенклатуре КАК Н")
REAL_FIELD = ('{(1, 20)}: Поле не знайдено "Н.Артикулл"\n'
              "ВЫБРАТЬ ПЕРВЫЕ 1 Н.<<?>>Артикулл ИЗ Справочник.Номенклатура КАК Н")


def test_validate_query_table_hint(tmp_path):
    server, client, paths = setup(tmp_path, validate_query, httpx.Response(
        200, json={"valid": False, "errors": [REAL_TABLE]}))
    text = call(server, client, "validate_query",
                query="ВЫБРАТЬ ПЕРВЫЕ 1 Н.Ссылка ИЗ Справочник.Номенклатуре КАК Н")
    assert "`Справочник.Номенклатура`" in text and "/metadata" in paths


def test_validate_query_field_hint_resolves_alias(tmp_path):
    server, client, paths = setup(tmp_path, validate_query, httpx.Response(
        200, json={"valid": False, "errors": [REAL_FIELD]}))
    text = call(server, client, "validate_query",
                query="ВЫБРАТЬ ПЕРВЫЕ 1 Н.Артикулл ИЗ Справочник.Номенклатура КАК Н")
    assert "`Артикул`" in text
    assert any(p.startswith("/object/Catalog/") for p in paths)


def test_execute_query_generic_error_points_to_validate(tmp_path):
    server, client, paths = setup(tmp_path, query, httpx.Response(
        400, text='{"error":"query execution failed","error_code":"query_error"}'))
    with pytest.raises(ToolError, match="validate_query"):
        call(server, client, "execute_query", query="ВЫБРАТЬ 1")
    assert paths == ["/query"]


def test_hint_skipped_without_access(tmp_path):
    class Denied(MCPServer):
        async def has_method(self, method):
            return False

    server, client, paths = setup(
        tmp_path, validate_query,
        httpx.Response(200, json={"valid": False, "errors": [REAL_TABLE]}),
        server=Denied("test"),
    )
    text = call(server, client, "validate_query", query="ВЫБРАТЬ 1 ИЗ Справочник.Номенклатуре")
    assert "Возможно" not in text
    assert paths == ["/validate-query"]


def test_validate_query_shows_advice_for_valid_query(tmp_path):
    server, client, _ = setup(
        tmp_path, validate_query, httpx.Response(200, json={"valid": True, "errors": []})
    )
    text = call(server, client, "validate_query", query=(
        "ВЫБРАТЬ О.Остаток ИЗ РегистрНакопления.Товары.Остатки(&Д) КАК О ГДЕ О.Склад = &С"
    ))
    assert "корректен" in text and "## Рекомендации" in text and "О.Склад" in text


@pytest.mark.parametrize("q", [
    "ВЫБРАТЬ О.Остаток ИЗ РегистрНакопления.Товары.Остатки(&Д, Склад = &С) КАК О ГДЕ О.Склад = &С",
    "ВЫБРАТЬ О.Остаток ИЗ РегистрНакопления.Товары.Остатки(&Д) КАК О ГДЕ О.Период = &П",
    "ВЫБРАТЬ О.Остаток ИЗ РегистрНакопления.Товары.Остатки(КОНЕЦПЕРИОДА(&Д, ДЕНЬ), Склад = &С) КАК О",
    "ВЫБРАТЬ 1 ИЗ Справочник.А ГДЕ Наименование ПОДОБНО \"А%\"",
    "ВЫБРАТЬ 1 // ОБЪЕДИНИТЬ\nИЗ Справочник.А",
    "ВЫБРАТЬ 1 ОБЪЕДИНИТЬ ВСЕ ВЫБРАТЬ 2",
])
def test_advisor_no_false_positives(q):
    assert advise_query(q) == []


def test_advisor_union_and_leading_percent():
    tips = advise_query('ВЫБРАТЬ 1 ОБЪЕДИНИТЬ ВЫБРАТЬ 2 ИЗ Справочник.А ГДЕ Наименование ПОДОБНО "%а"')
    assert len(tips) == 2


# Issue #162 (вслед за bsl-parser PR #437): табличные части справочников/документов,
# названные как виртуальные таблицы (Остатки/Обороты/ОстаткиИОбороты/СрезПоследних),
# — обычные таблицы. Правило советника точное: виртуальная таблица возможна только
# как суффикс вызова от регистра (РегистрНакопления|Сведений|Бухгалтерии) со скобкой
# параметров, поэтому ни одна из этих форм не должна давать «ГДЕ виртуальной таблицы».
_TS_NAMED_LIKE_VT = [
    # ТЧ справочника «Остатки» (фикстура issue: Справочник.Партии.Остатки).
    "ВЫБРАТЬ Т.Поле ИЗ Справочник.Партии.Остатки КАК Т",
    "ВЫБРАТЬ Т.Поле ИЗ Справочник.Партии.Остатки КАК Т ГДЕ Т.Склад = &С",
    # ТЧ документа «Обороты» и «ОстаткиИОбороты».
    "ВЫБРАТЬ О.Сумма ИЗ Документ.Реализация.Обороты КАК О ГДЕ О.Контрагент = &К",
    "ВЫБРАТЬ Т.Поле ИЗ Документ.ОтчетКомиссии.ОстаткиИОбороты КАК Т ГДЕ Т.Склад = &С",
    # Соединение, где ТЧ с виртуальным именем стоит слева.
    "ВЫБРАТЬ Т.Поле ИЗ Справочник.Партии.Остатки КАК Т ЛЕВОЕ СОЕДИНЕНИЕ "
    "Справочник.Номенклатура КАК Н ПО Т.Номенклатура = Н.Ссылка ГДЕ Т.Склад = &С",
    # ТЧ «СрезПоследних» под справочником — тоже не виртуальная таблица.
    "ВЫБРАТЬ Т.Поле ИЗ Справочник.Партии.СрезПоследних КАК Т ГДЕ Т.Склад = &С",
    # Даже «вызов с параметрами» от справочника не делает источник виртуальным:
    # суффикс виртуальной таблицы привязан к типу-регистру, а не к имени.
    "ВЫБРАТЬ Т.Поле ИЗ Справочник.Партии.Остатки(&Д) КАК Т ГДЕ Т.Склад = &С",
    # Английский синтаксис: псевдонимы виртуальных имён не поддерживаются,
    # и тем более ТЧ каталога/документа не может стать виртуальной таблицей.
    "SELECT T.Field FROM Catalog.Goods.Balances AS T WHERE T.Warehouse = &W",
    "SELECT T.Amt FROM Document.Sale.Turnovers AS T WHERE T.Partner = &P",
    # Обычное имя ТЧ — остаётся обычной таблицей (ничего не подсказываем).
    "ВЫБРАТЬ Т.Поле ИЗ Справочник.Партии.Состав КАК Т ГДЕ Т.Склад = &С",
]


@pytest.mark.parametrize("q", _TS_NAMED_LIKE_VT)
def test_advisor_tabular_section_named_like_virtual_table_is_plain_table(q):
    assert advise_query(q) == []


def test_advisor_virtual_table_with_parameters_still_virtual():
    """Настоящий вызов виртуальной таблицы от регистра по-прежнему классифицируется виртуальным."""
    tips = advise_query(
        "ВЫБРАТЬ С.Цена ИЗ РегистрСведений.Цены.СрезПоследних(&Д) КАК С ГДЕ С.Номенклатура = &Н"
    )
    assert len(tips) == 1 and "СрезПоследних" in tips[0] and "С.Номенклатура" in tips[0]


def test_validate_query_tabular_section_suffix_trimmed_for_hint(tmp_path):
    """(#162) Ошибочное имя ТЧ «Остаткы» не мешает подсказке: сравниваем Тип.Имя объекта."""
    tree = {"Справочники": ["Партии", "Номенклатура"], "Документы": []}
    audit = AuditLog(str(tmp_path))
    client = OneCClient(
        Config(base_url="http://test"),
        httpx.MockTransport(lambda request: httpx.Response(
            200, json={"valid": False, "errors": ['Таблицю не знайдено "Справочник.Партии.Остаткы"']}
        ) if request.url.path == "/validate-query" else httpx.Response(200, json=tree)),
        audit=audit,
    )
    server = MCPServer("test")
    validate_query.register(server, client, audit)
    text = call(server, client, "validate_query",
                query="ВЫБРАТЬ Т.Поле ИЗ Справочник.Партии.Остаткы КАК Т")
    assert "`Справочник.Партии`" in text
