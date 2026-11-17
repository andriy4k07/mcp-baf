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
from mcp_baf.tools.query_hints import access_checker, advise_query, error_hints, format_advice


def register(mcp: MCPServer, client: OneCClient, audit: AuditWriter) -> None:
    hint_cache: dict[str, Any] = {}
    can = access_checker(mcp)

    @mcp.tool(
        name="validate_query",
        title="Проверка синтаксиса запроса",
        description=(
            "Проверить синтаксис запроса 1С без выполнения — найдёт ошибки "
            "в ВЫБРАТЬ/SELECT. Всегда вызывай перед execute_query. "
            "Проверяется синтаксис и допустимость типа запроса (только чтение); "
            "как правило находит несуществующие таблицы и поля и подсказывает близкие имена."
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
            text = format_validate_result(result)
            if not result.get("valid"):
                hint = await error_hints(
                    client, hint_cache, query, " ".join(map(str, result.get("errors") or [])), can
                )
                if hint:
                    text += "\n" + hint + "\n"
            # Советник ничего не блокирует и не обращается к 1С.
            advice = format_advice(advise_query(query))
            return text + ("\n" + advice if advice else "")

        return await traced_text(
            audit, "validate_query", run, args={"query": audit_text(query)}
        )


def format_validate_result(r: dict[str, Any]) -> str:
    if r.get("valid"):
        return (
            "## Результат проверки\n\n✅ Запрос корректен.\n\n"
            "> Проверен синтаксис и тип запроса (чтение); полную проверку "
            "даёт только execute_query.\n"
        )

    lines = ["## Результат проверки", "", "❌ Запрос содержит ошибки:", ""]
    for error in r.get("errors") or []:
        if error == "not_select":
            lines.append("- not_select: разрешены только запросы ВЫБРАТЬ/SELECT")
        else:
            lines.append(f"- {error}")
    return "\n".join(lines) + "\n"
