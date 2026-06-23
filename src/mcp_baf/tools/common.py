"""Общие помощники для MCP-инструментов."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from mcp_baf_audit import AuditWriter, get_trace_id, new_trace_id, set_trace_id


async def traced_text(
    audit: AuditWriter,
    tool: str,
    call: Callable[[], Awaitable[str]],
    *,
    args: dict[str, Any] | None = None,
) -> str:
    """Выполняет инструмент со сквозным аудитом и возвращает его текст как есть.

    Аналог mcp_baf_audit.traced, но для инструментов mcp-baf, которые
    возвращают готовый markdown, а не dict: текст НЕ оборачивается в JSON.
    Каждый вызов оставляет событие tool.call (tool, args, ok, duration_ms)
    либо tool.error с текстом исключения.

    trace_id фиксируется в начале (унаследованный из contextvar или новый,
    никогда не null) и записывается в события инструмента; вложенные события
    того же контекста (one_c.http из клиента) наследуют его через contextvar.
    Сбой аудита не ломает инструмент.
    """
    trace_id = get_trace_id() or new_trace_id()
    set_trace_id(trace_id)

    start = time.monotonic()
    try:
        result = await call()
    except Exception as exc:
        audit.write(
            "tool_error",
            level="error", trace_id=trace_id,
            tool=tool, args=args or {}, error=str(exc),
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        raise

    audit.write(
        "tool_call",
        trace_id=trace_id,
        tool=tool, args=args or {}, ok=True,
        duration_ms=int((time.monotonic() - start) * 1000),
    )
    return result


def clamp_limit(value: int, default: int, maximum: int) -> int:
    """Нормализует пользовательский limit к диапазону [default, maximum]."""
    if value <= 0:
        return default
    return min(value, maximum)


def escape_pipe(s: str) -> str:
    """Экранирует вертикальную черту, чтобы не ломать markdown-таблицы."""
    return s.replace("|", "\\|")


def format_cell(v: Any) -> str:
    """Преобразует значение ячейки JSON-ответа в строку для markdown-таблицы."""
    if v is None:
        return ""
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, float):
        s = str(int(v)) if v == int(v) else f"{v:f}".rstrip("0").rstrip(".")
    elif isinstance(v, str):
        s = v
    else:
        s = str(v)
    return escape_pipe(s)
