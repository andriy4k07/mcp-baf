"""Контрактні фікси B12: дати/пагінація /query, підказки статусів, режим ІБ, форма."""

import asyncio
import json
import typing

import httpx
import pytest

from mcp_baf_audit import AuditLog
from mcp_baf.client import OneCClient, OneCError
from mcp_baf.config import Config
from mcp_baf.tools import configuration_info, form, query
from mcp_baf.tools.common import format_cell


def setup(tmp_path, result=None):
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=result or {"columns": ["A"], "rows": [[1]]})

    audit = AuditLog(str(tmp_path))
    client = OneCClient(
        Config(base_url="http://test"), httpx.MockTransport(handler), audit=audit
    )
    tools = {}

    class FakeMCP:
        def tool(self, **kwargs):
            return lambda f: tools.setdefault(f.__name__, f)

    query.register(FakeMCP(), client, audit, False)
    return tools, client, requests


def call(tools, client, **kwargs):
    async def scenario():
        try:
            return await tools["execute_query"](**kwargs)
        finally:
            await client.aclose()

    return asyncio.run(scenario())


# ── /query: дати й NULL ──────────────────────────────────────


def test_null_is_rendered_as_empty_cell_not_blank_string():
    # 1С віддає JSON null (раніше — ""): обидва рендеряться порожньою клітинкою,
    # але контракт JSON тепер честний і закріплений BSL-гардом.
    assert format_cell(None) == ""


def test_iso_dates_from_extension_pass_through_unchanged(tmp_path):
    iso = "1979-12-31T00:00:00"
    tools, client, _ = setup(tmp_path, {"columns": ["Дата"], "rows": [[iso], [None]]})
    text = call(tools, client, query="ВЫБРАТЬ 1")
    assert iso in text
    assert "31.12.1979" not in text


def test_parameters_are_sent_as_is(tmp_path):
    # Часова зона нормалізується в 1С; Python не переписує значення параметрів.
    tools, client, requests = setup(tmp_path)
    call(tools, client, query="ВЫБРАТЬ 1", parameters={"ДатаНачала": "2026-03-01T00:00:00Z"})
    assert requests[0]["parameters"] == {"ДатаНачала": "2026-03-01T00:00:00Z"}


# ── /query: чесна пагінація ─────────────────────────────────


def test_header_reports_count_and_total_separately():
    out = query.format_query_result(
        {"columns": ["A"], "rows": [[1], [2]], "count": 2, "total": 12}, offset=4
    )
    assert "записей: 2" in out
    assert "всего: 12" in out


def test_truncated_page_has_unknown_total():
    out = query.format_query_result(
        {"columns": ["A"], "rows": [[1], [2]], "count": 2, "truncated": True}, offset=0
    )
    assert "всего: неизвестно" in out


def test_total_is_not_page_size():
    # Регресія: total = розмір сторінки читався як «всього рядків».
    out = query.format_query_result(
        {"columns": ["A"], "rows": [[1]], "count": 1, "total": 1}, offset=0
    )
    assert "всего: 1" in out


def test_offset_above_cap_is_rejected_by_schema(tmp_path):
    tools, _, _ = setup(tmp_path)
    hints = typing.get_type_hints(tools["execute_query"], include_extras=True)
    field = hints["offset"].__metadata__[0]
    # pydantic тримає обмеження у FieldInfo.metadata (Le/Ge), не в атрибутах.
    assert any(getattr(m, "le", None) == query.MAX_QUERY_OFFSET for m in field.metadata)
    assert query.MAX_QUERY_OFFSET == 10000


# ── статуси → підказка ──────────────────────────────────────


def _client_for_status(status):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={"error": "x"}))
    return OneCClient(Config(base_url="http://test"), transport)


@pytest.mark.parametrize("status,fragment", [
    (400, "проверьте аргументы"),
    (403, "нет прав"),
    (404, "не найдены"),
    (500, "внутренний сбой"),
])
def test_status_maps_to_actionable_hint(status, fragment):
    client = _client_for_status(status)

    async def scenario():
        try:
            await client.post("/query", {"query": "ВЫБРАТЬ 1"})
        finally:
            await client.aclose()

    with pytest.raises(OneCError) as excinfo:
        asyncio.run(scenario())
    message = str(excinfo.value)
    assert f"status {status}" in message
    assert fragment in message


def test_unknown_status_has_no_hint():
    client = _client_for_status(418)

    async def scenario():
        try:
            await client.post("/query", {"query": "ВЫБРАТЬ 1"})
        finally:
            await client.aclose()

    with pytest.raises(OneCError) as excinfo:
        asyncio.run(scenario())
    message = str(excinfo.value)
    assert message.startswith("1C returned status 418")
    assert "проверьте" not in message and "нет прав" not in message


# ── /configuration: режим ───────────────────────────────────


def test_configuration_unknown_mode_is_shown():
    out = configuration_info.format_configuration_info({"name": "БАЗА", "mode": "unknown"})
    assert "| Режим работы | Не удалось определить |" in out


def test_configuration_empty_mode_row_is_skipped():
    out = configuration_info.format_configuration_info({"name": "БАЗА", "mode": ""})
    assert "Режим работы" not in out


# ── /form: недоступний склад ────────────────────────────────


def test_form_marks_unavailable_elements():
    out = form.format_form_structure(
        {"name": "ФормаДок", "elements": [], "elements_available": False}
    )
    assert "недоступен" in out
    assert "пустой список не значит" in out


def test_form_with_available_empty_elements_has_no_warning():
    out = form.format_form_structure(
        {"name": "ФормаДок", "elements": [], "elements_available": True}
    )
    assert "недоступен" not in out


def test_dump_merge_clears_unavailable_flags():
    data = {
        "name": "ФормаДок",
        "elements": [],
        "elements_available": False,
        "elements_reason": "нет доступа",
    }
    dump = {"name": "ФормаДок", "title": "", "elements": [], "commands": [], "handlers": []}
    form.merge_dump_into_form(data, dump)
    assert data["elements_available"] is True
    assert "elements_reason" not in data
