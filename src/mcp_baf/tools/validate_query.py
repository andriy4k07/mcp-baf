"""Инструмент validate_query: проверка синтаксиса запроса без выполнения."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_baf_audit import AuditWriter
from mcp_baf.client import OneCClient
from mcp_baf.tools.common import traced_text


def register(mcp: FastMCP, client: OneCClient, audit: AuditWriter) -> None:
    @mcp.tool(
        name="validate_query",
        title="Проверка синтаксиса запроса",
        description=(
            "Проверить синтаксис запроса 1С без выполнения — найдёт ошибки "
            "в ВЫБРАТЬ/SELECT. Всегда вызывай перед execute_query."
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

        async def run() -> str:
            result = await client.post("/validate-query", {"query": query})
            return format_validate_result(result)

        return await traced_text(
            audit, "validate_query", run, args={"query": query}
        )


def format_validate_result(r: dict[str, Any]) -> str:
    if r.get("valid"):
        return "## Результат проверки\n\n✅ Запрос корректен.\n"

    lines = ["## Результат проверки", "", "❌ Запрос содержит ошибки:", ""]
    for error in r.get("errors") or []:
        lines.append(f"- {error}")
    return "\n".join(lines) + "\n"
