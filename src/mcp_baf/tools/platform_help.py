"""Поиск справки в локальном индексе HBK."""

import asyncio
from typing import Annotated, Literal

from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_baf.tools.common import traced_text


def card(page, *, full=False):
    content = page["content"] if full else page["content"][:1200]
    return f"## {page['title']}\n\nРаздел: {page['section']}; версия источника: {page['version']}\nИсточник: `{page['source']}`\n\n{content}"


def register(mcp, index, audit):
    @mcp.tool(description="Поиск по локальной .hbk-справке платформы (SQLite BM25). section: пусто, functions, types, operators, vtables, skd. Раздел определяется эвристически по заголовку/пути; при отсутствии результатов повторите без фильтра. Версия источника не гарантирует совместимость с подключённой базой.", annotations=ToolAnnotations(read_only_hint=True))
    async def search_platform_help(query: str, limit: Annotated[int, Field(ge=1, le=50)] = 10, section: Literal["", "functions", "types", "operators", "vtables", "skd"] = "") -> str:
        async def run():
            pages = await asyncio.to_thread(index.search, query, limit, section)
            return "\n\n---\n\n".join(card(p) for p in pages) or "В локальной справке ничего не найдено."
        return await traced_text(audit, "search_platform_help", run, args={"query": query, "limit": limit, "section": section})

    @mcp.tool(description="Точная карточка элемента платформы по имени из search_platform_help, включая сигнатуры и примеры из HBK. Неоднозначное имя возвращает список кандидатов; неизвестное — ближайшие результаты поиска.", annotations=ToolAnnotations(read_only_hint=True))
    async def get_platform_element(name: str, source: str = "") -> str:
        async def run():
            if not name.strip():
                raise ValueError("name обязателен")
            pages = await asyncio.to_thread(index.get, name, source)
            if len(pages) == 1:
                return card(pages[0], full=True)
            if pages:
                return "Имя неоднозначно; уточните полный заголовок и source из списка:\n\n" + "\n".join(f"- {p['title']} ({p['source']})" for p in pages)
            candidates = await asyncio.to_thread(index.search, name, 5)
            return "Элемент не найден. Ближайшие результаты:\n\n" + "\n".join(p['title'] for p in candidates)
        return await traced_text(audit, "get_platform_element", run, args={"name": name, "source": source})
