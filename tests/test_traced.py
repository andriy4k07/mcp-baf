"""Тесты сквозного аудита вызовов инструментов (tools.common.traced_text).

В отличие от mcp_baf_audit.traced, инструменты mcp-baf возвращают готовый
markdown, поэтому traced_text не оборачивает результат в JSON — он отдаётся
как есть, а в audit.log пишется каноническое событие tool.call/tool.error.
"""

import asyncio
import json

import pytest

from mcp_baf_audit import AuditLog
from mcp_baf.tools.common import traced_text


def last_event(tmp_path):
    lines = (tmp_path / "audit.log").read_text("utf-8").splitlines()
    return json.loads(lines[-1])


def test_traced_text_returns_markdown_unchanged(tmp_path):
    audit = AuditLog(str(tmp_path))

    async def call():
        return "# Заголовок\n\n- пункт\n"

    out = asyncio.run(traced_text(
        audit, "get_metadata_tree", call, args={"filter": "Справочники"}
    ))
    # Текст не оборачивается в JSON — отдаётся как есть.
    assert out == "# Заголовок\n\n- пункт\n"

    event = last_event(tmp_path)
    assert event["event"] == "tool.call"
    assert event["tool"] == "get_metadata_tree"
    assert event["args"] == {"filter": "Справочники"}
    assert event["ok"] is True
    assert isinstance(event["duration_ms"], int)
    # trace_id фиксируется и не null (контракт v2)
    assert event["trace_id"]


def test_traced_text_logs_tool_error_on_exception(tmp_path):
    audit = AuditLog(str(tmp_path))

    async def call():
        raise RuntimeError("1C недоступна")

    with pytest.raises(RuntimeError):
        asyncio.run(traced_text(
            audit, "execute_query", call, args={"limit": 10}
        ))

    event = last_event(tmp_path)
    assert event["event"] == "tool.error"
    assert event["tool"] == "execute_query"
    assert event["level"] == "error"
    assert "1C недоступна" in event["error"]
    assert "duration_ms" in event


def test_traced_text_redacts_secret_args(tmp_path):
    audit = AuditLog(str(tmp_path))

    async def call():
        return "ok"

    asyncio.run(traced_text(
        audit, "execute_query", call,
        args={"query": "ВЫБРАТЬ 1", "password": "hunter2"},
    ))

    event = last_event(tmp_path)
    assert event["args"]["query"] == "ВЫБРАТЬ 1"
    assert event["args"]["password"] == "***"
