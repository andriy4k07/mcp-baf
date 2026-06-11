"""Общие помощники для MCP-инструментов."""

from __future__ import annotations

from typing import Any


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
