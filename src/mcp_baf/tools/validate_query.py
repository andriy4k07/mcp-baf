"""Инструмент validate_query: проверка синтаксиса запроса без выполнения."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_baf_audit import AuditWriter
from mcp_baf.client import OneCClient
from mcp_baf.pii import audit_text
from mcp_baf.tools.common import traced_text
from mcp_baf.tools.query import query_keyword


def register(mcp: MCPServer, client: OneCClient, audit: AuditWriter) -> None:
    @mcp.tool(
        name="validate_query",
        title="Проверка синтаксиса запроса",
        description=(
            "Проверить синтаксис запроса 1С без выполнения — найдёт ошибки "
            "в ВЫБРАТЬ/SELECT. Всегда вызывай перед execute_query. "
            "Проверяется синтаксис и допустимость типа запроса (только чтение); "
            "существование таблиц и полей гарантирует только execute_query."
        ),
        annotations=ToolAnnotations(read_only_hint=True),
    )
    async def validate_query(
        query: Annotated[str, Field(
            description="Текст запроса на языке запросов 1С для проверки"
        )],
    ) -> str:
        async def run() -> str:
            if not query:
                raise ValueError("query is required")
            # Тот же SELECT-гард, что в execute_query: иначе проверка подтверждает
            # запрос, который исполнение отклонит («✅» на УДАЛИТЬ/INSERT).
            if query_keyword(query) not in {"ВЫБРАТЬ", "SELECT"}:
                raise ValueError("только SELECT/ВЫБРАТЬ запросы разрешены")
            result = await client.post("/validate-query", {"query": query})
            return format_validate_result(result)

        return await traced_text(
            audit, "validate_query", run, args={"query": audit_text(query)}
        )


def format_validate_result(r: dict[str, Any]) -> str:
    if r.get("valid"):
        return (
            "## Результат проверки\n\n✅ Запрос корректен.\n\n"
            "> Проверен только синтаксис и тип запроса (чтение). Существование "
            "таблиц и полей подтверждает лишь execute_query.\n"
        )

    lines = ["## Результат проверки", "", "❌ Запрос содержит ошибки:", ""]
    for error in r.get("errors") or []:
        if error == "not_select":
            lines.append("- not_select: разрешены только запросы ВЫБРАТЬ/SELECT")
        else:
            lines.append(f"- {error}")
    return "\n".join(lines) + "\n"
