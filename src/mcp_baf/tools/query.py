"""Инструмент execute_query: выполнение запроса 1С (только чтение)."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_baf.client import OneCClient
from mcp_baf.tools.common import clamp_limit, escape_pipe, format_cell

DEFAULT_QUERY_LIMIT = 100
MAX_QUERY_LIMIT = 1000


def register(mcp: FastMCP, client: OneCClient) -> None:
    @mcp.tool(
        name="execute_query",
        title="Выполнить запрос к данным",
        description=(
            "Выполнить запрос на языке 1С (ВЫБРАТЬ/SELECT) и получить данные из базы: "
            "список элементов справочника, документы за период, остатки, обороты, сведения из регистров. "
            "Используй когда нужно найти, посчитать или вывести конкретные данные. Поддерживает параметры через &Имя. "
            "Имена таблиц: Справочник.X, Документ.X, РегистрНакопления.X, РегистрСведений.X (единственное число, НЕ Справочники/Документы). "
            "Перечисления НЕ являются таблицами: используй ЗНАЧЕНИЕ(Перечисление.Имя.Значение) в WHERE/CASE. "
            "Виртуальные таблицы регистров: РегистрНакопления.X.Остатки(&Период), .Обороты(&НачалоПериода, &КонецПериода), "
            "РегистрСведений.X.СрезПоследних(&Период). "
            "Перед выполнением вызови validate_query для проверки синтаксиса. "
            "Имена полей бери из get_object_structure."
        ),
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def execute_query(
        query: Annotated[str, Field(description=(
            "Текст запроса на языке запросов 1С. Только ВЫБРАТЬ/SELECT. "
            "Параметры указывай через &ИмяПараметра."
        ))],
        limit: Annotated[int, Field(description=(
            "Максимальное количество строк результата "
            f"(по умолчанию {DEFAULT_QUERY_LIMIT}, максимум {MAX_QUERY_LIMIT})"
        ))] = 0,
        parameters: Annotated[dict[str, Any] | None, Field(description=(
            "Параметры запроса в виде пар ключ-значение. Ключ — имя параметра без амперсанда. "
            'Пример: {"Контрагент": "ООО Ромашка", "ДатаНачала": "2026-01-01"}'
        ))] = None,
    ) -> str:
        if not query:
            raise ValueError("query is required")

        # Клиентская проверка «только чтение» (подсказка для LLM).
        # Серверное расширение 1С само гарантирует read-only выполнение.
        prefix = query.strip()[:30].upper()
        if not prefix.startswith("ВЫБРАТЬ") and not prefix.startswith("SELECT"):
            raise ValueError("только SELECT/ВЫБРАТЬ запросы разрешены")

        body: dict[str, Any] = {
            "query": query,
            "limit": clamp_limit(limit, DEFAULT_QUERY_LIMIT, MAX_QUERY_LIMIT),
        }
        if parameters:
            body["parameters"] = parameters

        result = await client.post("/query", body)
        return format_query_result(result)


def format_query_result(r: dict[str, Any]) -> str:
    """Форматирует результат запроса как markdown-таблицу."""
    lines = [f"## Результат запроса ({r.get('total', 0)} записей)", ""]

    columns = r.get("columns") or []
    rows = r.get("rows") or []
    if not columns or not rows:
        lines.append("Нет данных.")
        return "\n".join(lines) + "\n"

    lines.append("| " + " | ".join(escape_pipe(c) for c in columns) + " |")
    lines.append("|" + "---|" * len(columns))
    for row in rows:
        lines.append("| " + " | ".join(format_cell(cell) for cell in row) + " |")

    if r.get("truncated"):
        lines.append("")
        lines.append(
            "> Результат усечён. Показаны первые записи. "
            "Используйте параметр `limit` для увеличения."
        )

    return "\n".join(lines) + "\n"
