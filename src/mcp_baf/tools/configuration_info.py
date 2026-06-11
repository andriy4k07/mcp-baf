"""Инструмент get_configuration_info: общая информация о базе 1С."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from mcp_baf.client import OneCClient

_MODE_NAMES = {
    "file": "Файловый",
    "server": "Клиент-серверный",
}


def register(mcp: FastMCP, client: OneCClient) -> None:
    @mcp.tool(
        name="get_configuration_info",
        title="Информация о конфигурации",
        description=(
            "Получить общую информацию о базе 1С: название конфигурации, версия, "
            "поставщик, платформа, режим работы. "
            "Используй первым делом чтобы понять с какой конфигурацией работаешь."
        ),
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def get_configuration_info() -> str:
        info = await client.get("/configuration")
        return format_configuration_info(info)


def format_configuration_info(info: dict[str, Any]) -> str:
    lines = [
        "# Информация о конфигурации 1С",
        "",
        "| Параметр | Значение |",
        "|----------|----------|",
    ]

    def add_row(key: str, value: str) -> None:
        if value:
            lines.append(f"| {key} | {value} |")

    add_row("Конфигурация", info.get("name", ""))
    add_row("Версия", info.get("version", ""))
    add_row("Поставщик", info.get("vendor", ""))
    add_row("Платформа", info.get("platform_version", ""))

    mode = info.get("mode", "")
    add_row("Режим работы", _MODE_NAMES.get(mode, mode))

    return "\n".join(lines) + "\n"
