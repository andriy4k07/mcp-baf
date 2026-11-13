"""Инструмент get_metadata_tree: объекты конфигурации по категориям."""

from __future__ import annotations

import time
from typing import Annotated, Any
from urllib.parse import quote

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_baf_audit import AuditWriter
from mcp_baf.client import OneCClient, OneCError
from mcp_baf.tools.common import traced_text, truncate_output

# Все известные категории метаданных 1С в порядке отображения:
# (ключ JSON-ответа 1С, отображаемое название).
METADATA_CATEGORIES = [
    ("Справочники", "Справочники"),
    ("Документы", "Документы"),
    ("Перечисления", "Перечисления"),
    ("Обработки", "Обработки"),
    ("Отчеты", "Отчёты"),
    ("РегистрыСведений", "Регистры сведений"),
    ("РегистрыНакопления", "Регистры накопления"),
    ("РегистрыБухгалтерии", "Регистры бухгалтерии"),
    ("РегистрыРасчета", "Регистры расчёта"),
    ("ПланыСчетов", "Планы счетов"),
    ("ПланыВидовХарактеристик", "Планы видов характеристик"),
    ("ПланыВидовРасчета", "Планы видов расчёта"),
    ("ПланыОбмена", "Планы обмена"),
    ("БизнесПроцессы", "Бизнес-процессы"),
    ("Задачи", "Задачи"),
    ("ЖурналыДокументов", "Журналы документов"),
    ("Константы", "Константы"),
    ("ОбщиеМодули", "Общие модули"),
    ("ОбщиеФормы", "Общие формы"),
    ("ОбщиеКоманды", "Общие команды"),
    ("ОбщиеМакеты", "Общие макеты"),
    ("Роли", "Роли"),
    ("Подсистемы", "Подсистемы"),
    ("РегулярныеЗадания", "Регулярные задания"),
    ("ВебСервисы", "Веб-сервисы"),
    ("HTTPСервисы", "HTTP-сервисы"),
]

# Суффиксы автогенерируемых объектов, которые отфильтровываются как шум.
NOISE_SUFFIXES = ("ПрисоединенныеФайлы", "ПрисоединённыеФайлы")

# Кэш полного дерева метаданных: обход 26 коллекций — самый тяжёлый «обзорный»
# вызов, а метаданные меняются редко. TTL короткий, чтобы после изменения
# конфигурации агент быстро увидел актуальный состав.
TREE_CACHE_TTL_SEC = 30.0


def register(mcp: MCPServer, client: OneCClient, audit: AuditWriter) -> None:
    # Кэш на экземпляр сервера: общий для всех вызовов инструмента.
    cache: dict[str, Any] = {}

    @mcp.tool(
        name="get_metadata_tree",
        title="Дерево метаданных конфигурации",
        description=(
            "Список всех объектов конфигурации 1С по категориям: справочники, документы, "
            "регистры, перечисления, обработки и т.д. "
            "Без фильтра: сводка (категории и количество), с filter: полный перечень объектов категории. "
            "Используй когда нужно узнать какие объекты есть в базе. "
            "Вызывай первым при работе с незнакомой конфигурацией. "
            "Имена объектов из результата используются в get_object_structure и в запросах."
        ),
        annotations=ToolAnnotations(read_only_hint=True),
    )
    async def get_metadata_tree(
        filter: Annotated[str, Field(description=(
            "Категория метаданных для фильтрации: Справочники, Документы, Перечисления, "
            "Обработки, Отчеты, РегистрыСведений, РегистрыНакопления, ОбщиеМодули и др. "
            "Если не указан — возвращаются все категории."
        ))] = "",
    ) -> str:
        async def run() -> str:
            tree = await load_tree(client, cache, filter)
            filter_noise(tree)

            if filter:
                # Неизвестный filter — ошибка контракта, а не пустой документ:
                # молчаливый пустой ответ агент принимает за «объектов нет».
                if filter not in tree:
                    allowed = ", ".join(sorted(tree)) or "нет данных"
                    raise ValueError(
                        f"filter {filter!r} не найден. Допустимые значения: {allowed}"
                    )
                return truncate_output(format_metadata_tree({filter: tree[filter]}))

            # Без фильтра — только названия категорий и количество объектов.
            return truncate_output(format_metadata_summary(tree))

        return await traced_text(
            audit, "get_metadata_tree", run, args={"filter": filter}
        )


async def load_tree(
    client: OneCClient, cache: dict[str, Any], filter: str
) -> dict[str, list[str]]:
    """Дерево метаданных: одна коллекция при filter, иначе кэшированный полный обход.

    filter уходит query-параметром в 1С, чтобы сервер не перебирал все 26
    коллекций. Неизвестная категория даёт 400 от 1С — превращаем её в ту же
    ошибку контракта со списком допустимых значений, что и локальная проверка.
    """
    if filter:
        try:
            return await client.get(f"/metadata?filter={quote(filter, safe='')}")
        except OneCError as exc:
            if "filter" in str(exc):
                allowed = ", ".join(sorted(key for key, _ in METADATA_CATEGORIES))
                raise ValueError(
                    f"filter {filter!r} не найден. Допустимые значения: {allowed}"
                ) from exc
            raise

    now = time.monotonic()
    if cache.get("tree") is None or now >= cache.get("expires", 0.0):
        cache["tree"] = await client.get("/metadata")
        cache["expires"] = now + TREE_CACHE_TTL_SEC
    # filter_noise заменяет списки целиком, поэтому копии верхнего уровня хватает.
    return dict(cache["tree"])


def _is_noise(name: str) -> bool:
    return name.endswith(NOISE_SUFFIXES)


def filter_noise(tree: dict[str, list[str]]) -> None:
    """Убирает автогенерируемые объекты из дерева метаданных."""
    for key, items in tree.items():
        tree[key] = [name for name in items if not _is_noise(name)]


def format_metadata_tree(tree: dict[str, list[str]]) -> str:
    """Полный перечень объектов. Известные категории идут первыми в
    стабильном порядке, неизвестные добавляются в конец (forward compatibility)."""
    lines = ["# Метаданные конфигурации 1С", ""]

    rendered = set()
    for key, title in METADATA_CATEGORIES:
        if key not in tree:
            continue
        rendered.add(key)
        if tree[key]:
            _write_section(lines, title, tree[key])

    for key in sorted(k for k in tree if k not in rendered):
        if tree[key]:
            _write_section(lines, key, tree[key])

    return "\n".join(lines) + "\n"


def format_metadata_summary(tree: dict[str, list[str]]) -> str:
    """Компактная сводка: названия категорий и количество объектов."""
    lines = [
        "# Метаданные конфигурации 1С (сводка)",
        "",
        "Для получения списка объектов вызови get_metadata_tree с параметром filter.",
        "",
    ]

    known = set()
    for key, title in METADATA_CATEGORIES:
        known.add(key)
        if tree.get(key):
            lines.append(f'- **{title}** ({len(tree[key])}) — filter="{key}"')

    for key in sorted(k for k in tree if k not in known and tree[k]):
        lines.append(f'- **{key}** ({len(tree[key])}) — filter="{key}"')

    return "\n".join(lines) + "\n"


def _write_section(lines: list[str], title: str, items: list[str]) -> None:
    lines.append(f"## {title}")
    lines.extend(f"- {name}" for name in items)
    lines.append("")
