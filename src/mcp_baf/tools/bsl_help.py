"""Инструмент bsl_syntax_help: справочник встроенных функций языка 1С.

Работает локально по данным mcp_baf.bsl — HTTP-запросов к 1С не делает.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_baf_audit import AuditWriter
from mcp_baf import bsl
from mcp_baf.tools.common import traced_text


def register(mcp: FastMCP, audit: AuditWriter) -> None:
    @mcp.tool(
        name="bsl_syntax_help",
        title="Справочник функций языка 1С",
        description=(
            "Справка по 180 встроенным функциям, методам типов и объектным паттернам "
            "языка 1С (BSL): строки, числа, даты, коллекции, файлы, HTTP, XML/JSON, "
            "Base64, двоичные данные, транзакции, система, методы "
            "ТаблицаЗначений/Массив/Структура/Соответствие/Запрос, справочники, "
            "документы, регистры сведений, системные перечисления. "
            "Вызывай перед написанием кода на BSL, когда нужно узнать "
            "сигнатуру, параметры или пример использования функции/метода "
            "платформы 1С:Предприятие."
        ),
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def bsl_syntax_help(
        query: Annotated[str, Field(description=(
            "Название функции на русском или английском, например СтрНайти или StrFind"
        ))],
    ) -> str:
        async def run() -> str:
            results = bsl.search(query)
            if not results:
                return f'Функция "{query}" не найдена в справочнике BSL.'
            return format_functions(results)

        return await traced_text(
            audit, "bsl_syntax_help", run, args={"query": query}
        )


def format_functions(functions: list[dict[str, str]]) -> str:
    blocks = []
    for fn in functions:
        blocks.append(
            f"## {fn['name']} / {fn['name_en']}\n"
            "\n"
            f"**Описание:** {fn['description']}\n"
            "\n"
            f"**Синтаксис:** `{fn['syntax']}`\n"
            "\n"
            f"**Параметры:** {fn['parameters']}\n"
            "\n"
            f"**Возвращает:** {fn['return_type']}\n"
            "\n"
            f"**Пример:**\n```bsl\n{fn['example']}\n```\n"
        )
    return "\n---\n\n".join(blocks)
