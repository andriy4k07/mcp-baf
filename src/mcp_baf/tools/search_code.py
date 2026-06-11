"""Инструмент search_code: полнотекстовый поиск по коду модулей конфигурации."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_baf.dumpindex import DumpIndex, Match, SearchParams
from mcp_baf.tools.common import clamp_limit

DEFAULT_SEARCH_LIMIT = 50
MAX_SEARCH_LIMIT = 500


def register(mcp: FastMCP, index: DumpIndex) -> None:
    @mcp.tool(
        name="search_code",
        title="Поиск по коду модулей",
        description=(
            "Полнотекстовый поиск по коду всех модулей конфигурации 1С. "
            "Поддерживает три режима: smart (полнотекстовый с ранжированием BM25, "
            "по умолчанию), regex (регулярные выражения), exact (точная подстрока). "
            "Фильтрация по типу метаданных (category) и типу модуля (module). "
            "BSL-синонимы: поиск по английским именам находит русские и наоборот "
            "(StrFind -> СтрНайти, Procedure -> Процедура). "
            "Работает по локальной выгрузке конфигурации (DumpConfigToFiles). "
            "Режим smart (по умолчанию) для поиска по смыслу, regex для точных паттернов. "
            "Фильтруй по category и module для сужения результатов."
        ),
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def search_code(
        query: Annotated[str, Field(description=(
            "Поисковый запрос. В режиме smart — слова для полнотекстового поиска. "
            "В режиме regex — регулярное выражение (Python re). "
            "В режиме exact — точная подстрока (регистронезависимо)."
        ))],
        limit: Annotated[int, Field(description=(
            "Максимальное количество результатов "
            f"(по умолчанию {DEFAULT_SEARCH_LIMIT}, максимум {MAX_SEARCH_LIMIT})"
        ))] = 0,
        category: Annotated[str, Field(description=(
            "Фильтр по типу метаданных: Документ, Справочник, ОбщийМодуль, Обработка, "
            "Отчет, РегистрСведений, РегистрНакопления и т.д. Значение чувствительно "
            "к регистру (например, 'Документ', не 'документ')."
        ))] = "",
        module: Annotated[str, Field(description=(
            "Фильтр по типу модуля: МодульОбъекта, МодульМенеджера, МодульФормы, "
            "МодульНабораЗаписей, МодульКоманды, Модуль. Значение чувствительно "
            "к регистру (например, 'МодульОбъекта', не 'модульобъекта')."
        ))] = "",
        mode: Annotated[Literal["smart", "regex", "exact"], Field(description=(
            "Режим поиска. smart — полнотекстовый с BM25-ранжированием и поддержкой "
            "BSL-синонимов (по умолчанию). regex — регулярное выражение. "
            "exact — точная подстрока."
        ))] = "smart",
    ) -> str:
        if not query:
            raise ValueError("query is required")

        params = SearchParams(
            query=query,
            category=category,
            module=module,
            mode=mode,
            limit=clamp_limit(limit, DEFAULT_SEARCH_LIMIT, MAX_SEARCH_LIMIT),
        )
        # Поиск ходит в SQLite и сканирует строки — уводим из event loop.
        matches, total = await asyncio.to_thread(index.search, params)

        if total == 0 and index.module_count() == 0:
            return (
                "Индекс пуст: в директории --dump не найдено .bsl файлов. "
                "Проверьте путь к выгрузке конфигурации."
            )

        return format_search_result(matches, total, query, mode)


def format_search_result(
    matches: list[Match], total: int, query: str, mode: str
) -> str:
    lines = [f'## Результаты поиска "{query}" ({total} совпадений)', ""]

    if not matches:
        lines.append("Ничего не найдено.")
        return "\n".join(lines) + "\n"

    for m in matches:
        if mode == "smart" and m.score > 0:
            lines.append(f"### {m.module} (строка {m.line}, score: {m.score:.3f})")
        else:
            lines.append(f"### {m.module} (строка {m.line})")
        lines.append("```bsl")
        lines.append(m.context)
        lines.append("```")
        lines.append("")

    if total > len(matches):
        lines.append(
            f"> Показано {len(matches)} из {total} совпадений. "
            "Уточните поиск или увеличьте limit."
        )

    return "\n".join(lines) + "\n"
