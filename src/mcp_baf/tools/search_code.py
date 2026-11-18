"""Инструмент search_code: полнотекстовый поиск по коду модулей конфигурации."""

import asyncio
import re
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_baf_audit import AuditWriter
from mcp_baf.dumpindex import DumpIndex, Match, SearchParams, Usage
from mcp_baf.pii import MASKING_NOTE, audit_text, mask_pii_text
from mcp_baf.tools.common import clamp_limit, traced_text

DEFAULT_SEARCH_LIMIT = 50
MAX_SEARCH_LIMIT = 500
MAX_USAGE_LINES = 10  # номеров строк на модуль в режиме usages


def register(mcp: MCPServer, index: DumpIndex, audit: AuditWriter,
             mask_pii: bool = False) -> None:
    # hybrid появляется в схеме только при включённых эмбеддингах (--embed-url).
    has_vectors = index is not None and index.has_vectors()
    modes = Literal["smart", "regex", "exact", "usages", "hybrid"] if has_vectors \
        else Literal["smart", "regex", "exact", "usages"]
    hybrid_help = (
        " hybrid — BM25 + векторный поиск по смыслу (RRF, при --rerank-url с реранкером): "
        "запрос можно формулировать естественным языком; результаты — методы."
    ) if has_vectors else ""

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
            "Режим usages — обратные зависимости: query вида Тип.Имя "
            "(РегистрНакопления.ТоварыНаСкладах, AccumulationRegisters.Имя) возвращает "
            "модули и схемы компоновки данных (СКД, модуль СхемаКомпоновкиДанных; строки "
            "считаются в тексте запросов схемы), ссылающиеся на объект, со строками и числом ссылок. "
            "Работает по локальной выгрузке конфигурации (DumpConfigToFiles). "
            "Фильтруй по category и module для сужения результатов." + hybrid_help + " " + MASKING_NOTE
        ),
        annotations=ToolAnnotations(read_only_hint=True),
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
            "Отчет, РегистрСведений, РегистрНакопления, HTTPСервис, WebСервис и т.д. Значение чувствительно "
            "к регистру (например, 'Документ', не 'документ')."
        ))] = "",
        module: Annotated[str, Field(description=(
            "Фильтр по типу модуля: МодульОбъекта, МодульМенеджера, МодульФормы, "
            "МодульНабораЗаписей, МодульКоманды, Модуль. Значение чувствительно "
            "к регистру (например, 'МодульОбъекта', не 'модульобъекта')."
        ))] = "",
        mode: Annotated[modes, Field(description=(
            "Режим поиска. smart — полнотекстовый с BM25-ранжированием и поддержкой "
            "BSL-синонимов (по умолчанию). regex — регулярное выражение. "
            "exact — точная подстрока. usages — кто ссылается на объект Тип.Имя "
            "(модули и СКД; ru/en, ед./мн.ч. типа)." + hybrid_help
        ))] = "smart",
    ) -> str:
        effective_limit = clamp_limit(
            limit, DEFAULT_SEARCH_LIMIT, MAX_SEARCH_LIMIT
        )

        async def run() -> str:
            if not query:
                raise ValueError("query is required")
            if mode == "usages":
                found, modules, hits = await asyncio.to_thread(
                    index.find_usages, query, effective_limit, category, module
                )
                return format_usages(found, modules, hits, query)
            params = SearchParams(
                query=query,
                category=category,
                module=module,
                mode=mode,
                limit=effective_limit,
            )
            # Поиск ходит в SQLite и сканирует строки — уводим из event loop.
            matches, total = await asyncio.to_thread(index.search, params)

            if total == 0 and index.module_count() == 0:
                return (
                    "Индекс пуст: в директории --dump не найдено .bsl файлов. "
                    "Проверьте путь к выгрузке конфигурации."
                )

            return format_search_result(
                matches, total, query, mode, mask_pii=mask_pii,
                truncated=getattr(matches, "truncated", False),
                note=getattr(matches, "note", ""),
            )

        return await traced_text(
            audit, "search_code", run,
            args={
                "query": audit_text(query),
                "mode": mode,
                "category": category,
                "module": module,
                "limit": effective_limit,
            },
        )


def format_usages(usages: list[Usage], modules: int, hits: int, query: str) -> str:
    """Сгруппированный список модулей/СКД со строками и числом ссылок."""
    lines = [f'## Использования "{query}": {modules} модулей, {hits} ссылок', ""]
    if not usages:
        lines.append("Ссылок не найдено.")
    for u in usages:
        shown = ", ".join(map(str, u.lines[:MAX_USAGE_LINES]))
        more = f" и ещё {len(u.lines) - MAX_USAGE_LINES}" if len(u.lines) > MAX_USAGE_LINES else ""
        lines.append(f"- {u.module} — {len(u.lines)} (строки {shown}{more})")
    if modules > len(usages):
        lines.append(f"\n> Показано {len(usages)} из {modules} модулей. Увеличьте limit.")
    return "\n".join(lines) + "\n"


def format_search_result(
    matches: list[Match], total: int, query: str, mode: str,
    mask_pii: bool = False, truncated: bool = False, note: str = "",
) -> str:
    """Форматирует результаты поиска; при mask_pii код маскируется по regex.

    В коде модулей встречаются литералы с телефонами и email (шаблоны писем,
    реквизиты контрагентов), поэтому при --mask-pii они заменяются токенами.
    """
    def text(value: str) -> str:
        return mask_pii_text(value) if mask_pii else value

    lines = [f'## Результаты поиска "{text(query)}" ({total} совпадений)', ""]

    hybrid_note, note = note, (
        "> Поиск прерван по бюджету времени: результаты неполные, "
        "уточните запрос (category/module) или шаблон."
    )
    if not matches:
        lines.append("Ничего не найдено." if not truncated else note)
        return "\n".join(lines) + "\n"

    for m in matches:
        if mode in ("smart", "hybrid") and m.score > 0:
            lines.append(f"### {m.module} (строка {m.line}, score: {m.score:.3f})")
        else:
            lines.append(f"### {m.module} (строка {m.line})")
        context = text(m.context)
        longest_run = max((run.end() - run.start() for run in re.finditer(r"`+", context)), default=0)
        fence = "`" * max(3, longest_run + 1)
        lines.extend((f"{fence}bsl", context, fence))
        lines.append("")

    if truncated:
        lines.append(note)
    if hybrid_note:
        lines.append(f"> {hybrid_note}")
    if total > len(matches):
        lines.append(
            f"> Показано {len(matches)} из {total} совпадений. "
            "Уточните поиск или увеличьте limit."
        )

    return "\n".join(lines) + "\n"
