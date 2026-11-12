"""Инструмент bsl_syntax_help: справочник встроенных функций языка 1С.

Работает локально по данным mcp_baf.bsl — HTTP-запросов к 1С не делает.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_baf_audit import AuditWriter
from mcp_baf import bsl
from mcp_baf.pii import audit_text
from mcp_baf.tools.common import traced_text, truncate_output

# Слишком короткий запрос («с») совпал бы почти со всем справочником.
MIN_QUERY_CHARS = 2
MAX_FUNCTIONS = 10


def register(mcp: MCPServer, audit: AuditWriter) -> None:
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
        annotations=ToolAnnotations(read_only_hint=True),
    )
    async def bsl_syntax_help(
        query: Annotated[str, Field(description=(
            "Название функции на русском или английском, например СтрНайти или StrFind"
        ))],
    ) -> str:
        async def run() -> str:
            q = query.strip()
            if len(q) < MIN_QUERY_CHARS:
                raise ValueError(
                    f"query: нужно минимум {MIN_QUERY_CHARS} символа — название функции "
                    "или его часть, например СтрНайти"
                )
            results = bsl.search(q)
            if not results:
                return f'Функция "{q}" не найдена в справочнике BSL.'
            text = format_functions(results[:MAX_FUNCTIONS])
            if len(results) > MAX_FUNCTIONS:
                text += (
                    f"\n\n> Показано {MAX_FUNCTIONS} из {len(results)} совпавших функций "
                    f"(ещё {len(results) - MAX_FUNCTIONS}) — уточните название."
                )
            return truncate_output(text)

        return await traced_text(
            audit, "bsl_syntax_help", run, args={"query": audit_text(query)}
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
