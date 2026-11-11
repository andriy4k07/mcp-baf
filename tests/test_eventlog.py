"""Тесты маскирования ПДн в журнале регистрации (get_event_log)."""

import asyncio

import httpx

from mcp_baf_audit import AuditLog
from mcp_baf.client import OneCClient
from mcp_baf.config import Config
from mcp_baf.tools import eventlog
from mcp_baf.tools.common import MAX_TOOL_OUTPUT_CHARS
from mcp_baf.tools.eventlog import format_event_log

EVENTS = {
    "events": [
        {
            "date": "2026-03-01T10:00:00",
            "level": "Информация",
            "event": "Изменение объекта",
            "user": "Иванов",
            "computer": "PC-01",
            "metadata": "Справочник.Контрагенты",
            "data": "Телефон клиента +380 50 123-45-67",
            "comment": "письмо на client@example.com",
            "transaction": "00000001",
        },
    ],
    "total": 1,
}


def test_event_log_without_masking_keeps_contacts():
    out = format_event_log(EVENTS)
    assert "123-45-67" in out and "client@example.com" in out


def test_event_log_masks_phone_and_email():
    out = format_event_log(EVENTS, mask_pii=True)
    assert "123-45-67" not in out
    assert "client@example.com" not in out
    assert out.count("PII:") == 2
    # имена полей и служебные значения не искажены
    assert "Пользователь: Иванов" in out
    assert "Справочник.Контрагенты" in out
    assert "00000001" in out


def test_event_log_masking_empty_result():
    out = format_event_log({"events": [], "total": 0}, mask_pii=True)
    assert "Записей не найдено." in out


def test_event_log_tool_output_is_limited(tmp_path):
    events = [{"date": "2026-03-01", "level": "Ошибка", "event": "E",
               "user": "U", "comment": "с" * 3000} for _ in range(300)]
    audit = AuditLog(str(tmp_path))
    client = OneCClient(
        Config(base_url="http://test"),
        httpx.MockTransport(lambda r: httpx.Response(200, json={"events": events, "found": 300})),
        audit=audit,
    )
    tools = {}

    class FakeMCP:
        def tool(self, **kwargs):
            return lambda f: tools.setdefault(f.__name__, f)

    eventlog.register(FakeMCP(), client, audit)

    async def scenario():
        try:
            return await tools["get_event_log"](limit=300)
        finally:
            await client.aclose()

    text = asyncio.run(scenario())
    assert len(text) <= MAX_TOOL_OUTPUT_CHARS + 400
    assert "усечён" in text
