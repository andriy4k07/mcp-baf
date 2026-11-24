"""Поиск справки в локальном индексе HBK."""

import asyncio
from typing import Annotated, Literal

from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_baf.pii import audit_text
from mcp_baf.tools.common import traced_text, truncate_output


def card(page, *, full=False):
    content = page["content"] if full else page["content"][:1200]
    return f"## {page['title']}\n\nРаздел: {page['section']}; версия источника: {page['version']}\nИсточник: `{page['source']}`\n\n{content}"


def register(mcp, index, audit):
    # vector/hybrid появляются в схеме только при включённых эмбеддингах (--embed-url), как в search_code.
    has_vectors = index.has_vectors()
    modes = Literal["bm25", "vector", "hybrid"] if has_vectors else Literal["bm25"]
    modes_help = (
        " Режимы: bm25 (по умолчанию, без внешних сервисов), vector (семантический косинус),"
        " hybrid (BM25 + векторы через RRF, при --rerank-url — с реранкером); пока векторы строятся"
        " или эмбеддер недоступен, hybrid показывает BM25 с примечанием."
    ) if has_vectors else ""

    @mcp.tool(description="Поиск по локальной .hbk-справке платформы (SQLite BM25). section: пусто, functions, types, operators, vtables, skd." + modes_help + " Раздел определяется эвристически по заголовку/пути; при отсутствии результатов повторите без фильтра. Версия источника не гарантирует совместимость с подключённой базой.", annotations=ToolAnnotations(read_only_hint=True))
    async def search_platform_help(query: str, limit: Annotated[int, Field(ge=1, le=50)] = 10, section: Literal["", "functions", "types", "operators", "vtables", "skd"] = "", mode: modes = "bm25") -> str:
        async def run():
            pages, note = await asyncio.to_thread(index.search_with_note, query, limit, section, mode)
            text = "\n\n---\n\n".join(card(p) for p in pages) or "В локальной справке ничего не найдено."
            if note:
                text += f"\n\n> {note}"
            return text
        return await traced_text(audit, "search_platform_help", run, args={"query": audit_text(query), "limit": limit, "section": section, "mode": mode})

    @mcp.tool(description="Точная карточка элемента платформы по имени из search_platform_help, включая сигнатуры и примеры из HBK. Неоднозначное имя возвращает список кандидатов; неизвестное — ближайшие результаты поиска" + (" (mode задаёт режим этого поиска)." if has_vectors else "."), annotations=ToolAnnotations(read_only_hint=True))
    async def get_platform_element(name: str, source: str = "", mode: modes = "bm25") -> str:
        async def run():
            if not name.strip():
                raise ValueError("name обязателен")
            pages = await asyncio.to_thread(index.get, name, source)
            if len(pages) == 1:
                return truncate_output(card(pages[0], full=True))
            if pages:
                return "Имя неоднозначно; уточните полный заголовок и source из списка:\n\n" + "\n".join(f"- {p['title']} ({p['source']})" for p in pages)
            candidates, note = await asyncio.to_thread(index.search_with_note, name, 5, "", mode)
            if not candidates:
                return "Элемент не найден, похожих заголовков в локальной справке нет."
            text = "Элемент не найден. Ближайшие результаты:\n\n" + "\n".join(f"- {p['title']}" for p in candidates)
            if note:
                # Примечание о деградации не глотаем: рендерим, как в search_platform_help.
                text += f"\n\n> {note}"
            return text
        return await traced_text(audit, "get_platform_element", run, args={"name": name, "source": source, "mode": mode})
