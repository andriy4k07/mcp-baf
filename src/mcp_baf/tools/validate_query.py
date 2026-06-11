"""Инструмент validate_query: проверка синтаксиса запроса без выполнения."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_baf.client import OneCClient


def register(mcp: FastMCP, client: OneCClient) -> None:
    @mcp.tool(
        name="validate_query",
        title="Проверка синтаксиса запроса",
        description=(
            "Проверить синтаксис запроса 1С без выполнения, найдёт ошибки в ВЫБРАТЬ/SELECT. "
            "Используй перед execute_query чтобы валидировать запрос. "
            "Всегда вызывай перед execute_query для проверки синтаксиса."
        ),
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def validate_query(
        query: Annotated[str, Field(
            description="Текст запроса на языке запросов 1С для проверки"
        )],
    ) -> str:
        if not query:
            raise ValueError("query is required")

        result = await client.post("/validate-query", {"query": query})
        return format_validate_result(result)


def format_validate_result(r: dict[str, Any]) -> str:
    if r.get("valid"):
        return "## Результат проверки\n\n✅ Запрос корректен.\n"

    lines = ["## Результат проверки", "", "❌ Запрос содержит ошибки:", ""]
    for error in r.get("errors") or []:
        lines.append(f"- {error}")
    return "\n".join(lines) + "\n"
