"""Инструмент bsl_syntax_help: справочник встроенных функций языка 1С.

Работает локально по данным mcp_baf.bsl — HTTP-запросов к 1С не делает.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_baf import bsl


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="bsl_syntax_help",
        title="Справочник функций языка 1С",
        description=(
            "Справка по 180 встроенным функциям, методам типов и объектным паттернам "
            "языка 1С (BSL): строки, числа, даты, коллекции, файлы, HTTP, XML/JSON, "
            "Base64, двоичные данные, транзакции, система, методы "
            "ТаблицаЗначений/Массив/Структура/Соответствие/Запрос, справочники, "
            "документы, регистры сведений, системные перечисления. "
            "Используй когда нужно узнать синтаксис, параметры или пример использования "
            "функции/метода платформы 1С:Предприятие. Параметр: query, название функции "
            "на русском или английском. "
            "Вызывай перед написанием кода на BSL для уточнения сигнатуры и параметров функции."
        ),
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    def bsl_syntax_help(
        query: Annotated[str, Field(description=(
            "Название функции на русском или английском, например СтрНайти или StrFind"
        ))],
    ) -> str:
        results = bsl.search(query)

        if not results:
            return f'Функция "{query}" не найдена в справочнике BSL.'

        return format_functions(results)


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
