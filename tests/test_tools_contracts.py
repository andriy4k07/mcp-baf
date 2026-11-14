"""Контракты инструментов: валидация URL-сегментов, filter, лимит вывода, экранирование."""

import asyncio
import json
from urllib.parse import unquote

import httpx
import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from mcp_baf_audit import AuditLog
from mcp_baf.client import OneCClient
from mcp_baf.config import Config
from mcp_baf.dumpindex.modulenames import METADATA_TYPES, OBJECT_TYPE_TO_DUMP_DIR
from mcp_baf.tools import (
    configuration_info, eventlog, form, metadata, object_structure, objects,
    validate_query,
)
from mcp_baf.tools.common import MAX_TOOL_OUTPUT_CHARS, truncate_output

GUID = "12345678-1234-5678-9abc-123456789abc"
KIND = "Справочник.Контрагенты"
LINK = "e1cib/data/" + KIND + "?ref=9abc123456789abc5678123412345678"


def setup(tmp_path, module, result, **kwargs):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=result)

    audit = AuditLog(str(tmp_path))
    client = OneCClient(Config(base_url="http://test"), httpx.MockTransport(handler), audit=audit)
    server = MCPServer("test")
    module.register(server, client, audit, **kwargs)
    return server, client, requests


def call(server, name, **arguments):
    return asyncio.run(server.call_tool(name, arguments)).content[0].text


BAD_NAMES = ["Валюты/../Admin", "Валюты?x=1", "Валюты\n", "Валюты X", "Валюты.Х", "", "1Валюты"]


@pytest.mark.parametrize("arguments", [
    *[dict(object_type="Catalog", object_name=name) for name in BAD_NAMES],
    dict(object_type="Evil", object_name="Валюты"),
    dict(object_type="Catalog;DELETE", object_name="Валюты"),
    dict(object_type="catalog", object_name="Валюты"),
])
def test_form_rejects_bad_url_segments(tmp_path, arguments):
    server, client, requests = setup(tmp_path, form, {"name": "Форма"})
    with pytest.raises(ToolError):
        call(server, "get_form_structure", **arguments)
    assert requests == []
    asyncio.run(client.aclose())


@pytest.mark.parametrize("arguments", [
    *[dict(object_type="Catalog", object_name=name) for name in BAD_NAMES],
    dict(object_type="Evil", object_name="Валюты"),
    dict(object_type="Catalog/../Admin", object_name="Валюты"),
])
def test_object_structure_rejects_bad_url_segments(tmp_path, arguments):
    server, client, requests = setup(tmp_path, object_structure, {"name": "Валюты"})
    with pytest.raises(ToolError):
        call(server, "get_object_structure", **arguments)
    assert requests == []
    asyncio.run(client.aclose())


def test_object_structure_empty_args_are_audited(tmp_path):
    server, client, requests = setup(tmp_path, object_structure, {"name": "Валюты"})
    with pytest.raises(ToolError, match="required"):
        call(server, "get_object_structure", object_type="", object_name="")
    assert requests == []
    events = [json.loads(x) for x in (tmp_path / "audit.log").read_text("utf-8").splitlines()]
    assert events[-1]["event"] == "tool.error" and events[-1]["tool"] == "get_object_structure"
    asyncio.run(client.aclose())


def test_object_type_error_lists_allowed_values(tmp_path):
    server, client, _ = setup(tmp_path, object_structure, {})
    with pytest.raises(ToolError) as excinfo:
        call(server, "get_object_structure", object_type="Evil", object_name="Валюты")
    message = str(excinfo.value)
    assert "Catalog" in message and "Document" in message
    asyncio.run(client.aclose())


@pytest.mark.parametrize("module,path", [
    (form, "/form"),
    (object_structure, "/object"),
])
def test_valid_name_is_percent_encoded_in_url(tmp_path, module, path):
    server, client, requests = setup(tmp_path, module, {"name": "Валюты"})
    call(server, "get_form_structure" if module is form else "get_object_structure",
         object_type="Catalog", object_name="Валюты")
    raw = requests[0].url.raw_path.decode("ascii")
    assert unquote(raw).endswith(f"{path}/Catalog/Валюты")
    # Не-ASCII имя уходит в URL закодированным, а не сырым.
    assert "%" in raw
    asyncio.run(client.aclose())


def test_all_whitelisted_types_are_dump_types():
    for object_type in (singular for singular, _, _ in METADATA_TYPES):
        assert object_type in OBJECT_TYPE_TO_DUMP_DIR
    # Constant — единственный тип из METADATA_TYPES, которого не было в BSL-мапе:
    # /object/Constant/<Имя> отвечал 404 на существующую константу.
    assert "Constant" in OBJECT_TYPE_TO_DUMP_DIR


def test_constant_type_is_sent_to_object_endpoint(tmp_path):
    server, client, requests = setup(tmp_path, object_structure, {"name": "ОрганизацияНаименование"})
    call(server, "get_object_structure", object_type="Constant", object_name="ОрганизацияНаименование")
    assert unquote(requests[0].url.raw_path.decode("ascii")).endswith(
        "/object/Constant/ОрганизацияНаименование"
    )
    asyncio.run(client.aclose())


def test_constant_type_is_rendered():
    from mcp_baf.tools.object_structure import format_object_structure

    text = format_object_structure({
        "name": "Курс", "synonym": "Курс", "type": "Число",
        "type_names": ["Число"], "precision": 15, "scale": 2, "attributes": [],
    })
    assert "## Тип константы" in text and "Число (точность 15, масштаб 2)" in text


def test_form_name_is_sent_as_query_param(tmp_path):
    server, client, requests = setup(tmp_path, form, {"name": "ФормаСписку"})
    call(server, "get_form_structure", object_type="Document", object_name="Продажа",
         form_name="ФормаСписку")
    url = requests[0].url
    assert url.params["form"] == "ФормаСписку"
    asyncio.run(client.aclose())


def test_form_without_form_name_has_no_form_query(tmp_path):
    server, client, requests = setup(tmp_path, form, {"name": "ФормаДокумента"})
    call(server, "get_form_structure", object_type="Document", object_name="Продажа")
    assert "form" not in requests[0].url.params
    asyncio.run(client.aclose())


@pytest.mark.parametrize("query", [
    "УДАЛИТЬ ИЗ Справочник.Валюты ГДЕ Ссылка = &С",
    "INSERT INTO x VALUES (1)",
    "ВЫБРАТЬСЯ ИЗ Справочник.Валюты",
])
def test_validate_query_applies_select_guard(tmp_path, query):
    server, client, requests = setup(tmp_path, validate_query, {"valid": True, "errors": []})
    with pytest.raises(ToolError, match="SELECT"):
        call(server, "validate_query", query=query)
    assert requests == []
    asyncio.run(client.aclose())


def test_validate_query_accepts_select_with_leading_comment(tmp_path):
    server, client, requests = setup(tmp_path, validate_query, {"valid": True, "errors": []})
    text = call(server, "validate_query", query="// остатки\nВЫБРАТЬ 1 КАК А")
    assert "корректен" in text
    assert len(requests) == 1
    asyncio.run(client.aclose())


def test_validate_query_reports_not_select_code_from_1c():
    text = validate_query.format_validate_result({"valid": False, "errors": ["not_select"]})
    assert "not_select" in text and "ВЫБРАТЬ/SELECT" in text


def test_metadata_filter_is_sent_as_query_param(tmp_path):
    server, client, requests = setup(
        tmp_path, metadata, {"Документы": ["Продажа"], "Справочники": ["Валюты"]}
    )
    call(server, "get_metadata_tree", filter="Документы")
    assert requests[0].url.params["filter"] == "Документы"
    asyncio.run(client.aclose())


def test_metadata_full_tree_is_cached_between_calls(tmp_path):
    server, client, requests = setup(tmp_path, metadata, {"Справочники": ["Валюты"]})
    call(server, "get_metadata_tree")
    call(server, "get_metadata_tree")
    # Обход 26 коллекций не повторяется на каждый обзорный вызов.
    assert len(requests) == 1
    asyncio.run(client.aclose())


def test_eventlog_filtered_empty_is_explained():
    text = eventlog.format_event_log(
        {"events": [], "total": 0, "found": 50, "truncated": True, "filtered_empty": True}
    )
    assert "Записей не найдено" in text
    assert "системный шум" in text and "exclude_system" in text


def test_capabilities_failure_reason_is_preserved(tmp_path):
    from mcp_baf.access import AccessMCP

    audit = AuditLog(str(tmp_path))
    client = OneCClient(
        Config(base_url="http://test"),
        httpx.MockTransport(lambda request: httpx.Response(
            403, json={"error": "Проверка прав недоступна", "reason": "method_use_denied"}
        )),
        audit=audit,
    )
    server = AccessMCP("test", access_client=client, audit=audit)
    asyncio.run(server.list_tools())
    assert "method_use_denied" in server._access_error
    events = [json.loads(x) for x in (tmp_path / "audit.log").read_text("utf-8").splitlines()]
    denials = [e for e in events if e["event"] == "access.capabilities_unavailable"]
    assert denials and denials[0]["reason_code"] == "method_use_denied"
    asyncio.run(client.aclose())


def test_metadata_unknown_filter_is_explicit_error(tmp_path):
    server, client, requests = setup(
        tmp_path, metadata, {"Документы": ["Продажа"], "Справочники": ["Валюты"]}
    )
    with pytest.raises(ToolError) as excinfo:
        call(server, "get_metadata_tree", filter="Справочник")
    message = str(excinfo.value)
    assert "не найден" in message
    assert "Документы" in message and "Справочники" in message
    assert len(requests) == 1
    asyncio.run(client.aclose())


def test_metadata_known_filter_returns_only_that_category(tmp_path):
    server, client, _ = setup(
        tmp_path, metadata, {"Документы": ["Продажа"], "Справочники": ["Валюты"]}
    )
    text = call(server, "get_metadata_tree", filter="Документы")
    assert "Продажа" in text and "Валюты" not in text
    asyncio.run(client.aclose())


def test_metadata_tree_output_is_limited(tmp_path):
    names = [f"Объект{i:05d}" for i in range(12000)]
    server, client, _ = setup(tmp_path, metadata, {"Документы": names})
    text = call(server, "get_metadata_tree", filter="Документы")
    assert len(text) <= MAX_TOOL_OUTPUT_CHARS + 400
    assert "усечён" in text and "Объект11999" not in text
    asyncio.run(client.aclose())


def test_truncate_output_keeps_whole_lines():
    text = ("строка\n" * 20000)
    out = truncate_output(text, limit=1000)
    assert len(out) < 1200
    assert out.startswith("строка\n")
    assert "усечён" in out
    assert truncate_output("short", limit=1000) == "short"


def test_configuration_info_cells_are_escaped(tmp_path):
    server, client, _ = setup(tmp_path, configuration_info, {
        "name": "База|Тест", "version": "1.0\n2.0", "vendor": "Фирма",
        "platform_version": "8.3", "mode": "file",
    })
    text = call(server, "get_configuration_info")
    assert "| База\\|Тест |" in text
    assert "| 1.0 2.0 |" in text
    assert "1.0\n2.0" not in text
    asyncio.run(client.aclose())


def test_references_without_found_in_meta_does_not_crash():
    text = objects.format_references({"hits": [{"path": "Товары.Контрагент", "match_kind": "x"}]})
    assert "(без метаданных)" in text


def test_object_link_missing_kind_is_contract_error(tmp_path):
    server, client, _ = setup(tmp_path, objects, {
        "found": True, "presentation": "x", "link": LINK, "ref": GUID,
    })
    with pytest.raises(ToolError, match="обязательного поля kind"):
        call(server, "get_object_link", mode="make", ref=GUID, kind=KIND)
    asyncio.run(client.aclose())


def test_metadata_rights_missing_fields_do_not_crash(tmp_path):
    server, client, _ = setup(tmp_path, objects, {"rights": [{"allowed": True}], "notes": []})
    text = call(server, "get_metadata_rights", metadata_object="Документ.Продажа")
    assert "|  |  | да |" in text
    asyncio.run(client.aclose())
