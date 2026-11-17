"""Подсказки к запросам: «возможно, вы имели в виду» по ошибке 1С и советник без вызова 1С.

Обе части необязательные и никогда не ломают инструмент: любой сбой даёт пустой текст.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import quote

from mcp_baf.client import OneCClient
from mcp_baf.dumpindex.modulenames import METADATA_TYPES
from mcp_baf.tools.metadata import filter_noise, load_tree

# Может ли пользователь звать HTTP-метод (см. access.TOOL_METHODS); без AccessMCP — всегда да.
CanCall = Callable[[str], Awaitable[bool]]

# Русский префикс таблицы запроса -> английский тип для /object.
_PREFIX_TO_TYPE = {ru: en for en, _, ru in METADATA_TYPES}
_PREFIX_LOWER = {ru.lower(): ru for ru in _PREFIX_TO_TYPE}
# Ключ дерева метаданных -> префикс таблицы запроса.
_TREE_TO_PREFIX = {
    "Справочники": "Справочник", "Документы": "Документ", "Перечисления": "Перечисление",
    "РегистрыСведений": "РегистрСведений", "РегистрыНакопления": "РегистрНакопления",
    "РегистрыБухгалтерии": "РегистрБухгалтерии", "РегистрыРасчета": "РегистрРасчета",
    "ПланыСчетов": "ПланСчетов", "ПланыВидовХарактеристик": "ПланВидовХарактеристик",
    "ПланыВидовРасчета": "ПланВидовРасчета", "ПланыОбмена": "ПланОбмена",
    "БизнесПроцессы": "БизнесПроцесс", "Задачи": "Задача", "Константы": "Константа",
}
_STANDARD_FIELDS = [
    "Ссылка", "Код", "Наименование", "Дата", "Номер", "ПометкаУдаления", "Проведен",
    "Родитель", "Владелец", "Период", "Регистратор", "Активность", "ВидДвижения",
    "НомерСтроки",
]

# Сообщения платформы ru/uk: «Таблица не найдена "X"», «Поле не знайдено X»,
# «Поле "X" не найдено». Паттерн терпимый: не совпало — подсказки просто нет.
_MISSING = r"не\s+(?:найден\w*|знайден\w*)"
_QUOTE = r"[\"'«“]"
_ERR_RES = [
    re.compile(rf"(Таблиц\w*|Пол[ея]\w*)\s+{_MISSING}\s*[:\-]?\s*{_QUOTE}?([\w.]+)", re.I),
    re.compile(rf"(Таблиц\w*|Пол[ея]\w*)\s+{_QUOTE}([\w.]+){_QUOTE}\s+{_MISSING}", re.I),
]
_TABLE_REF_RE = re.compile(
    r"\b(" + "|".join(sorted(_PREFIX_TO_TYPE, key=len, reverse=True)) + r")\.(\w+)", re.I
)
_ALIAS_RE = re.compile(
    r"\b(" + "|".join(sorted(_PREFIX_TO_TYPE, key=len, reverse=True)) + r")\.(\w+)\s+(?:КАК\s+)?(\w+)", re.I
)
_NOT_ALIAS = {"ГДЕ", "ЛЕВОЕ", "ПРАВОЕ", "ВНУТРЕННЕЕ", "ПОЛНОЕ", "СОЕДИНЕНИЕ", "СГРУППИРОВАТЬ",
              "УПОРЯДОЧИТЬ", "ОБЪЕДИНИТЬ", "ИТОГИ", "ИЗ"}
_MAX_ITEMS = 3


def access_checker(mcp: Any) -> CanCall:
    """Проверка права на метод через AccessMCP.has_method (в тестах без него — разрешено)."""
    check = getattr(mcp, "has_method", None)

    async def can(method: str) -> bool:
        return True if check is None else await check(method)

    return can


def parse_missing(error_text: str) -> list[tuple[str, str]]:
    """[(«table»|«field», имя)] из текста ошибки; поле остаётся как есть («Н.Артикулл»)."""
    found: list[tuple[str, str]] = []
    for rx in _ERR_RES:
        for kind, name in rx.findall(error_text):
            is_table = kind.lower().startswith("таблиц")
            item = ("table" if is_table else "field", name)
            if item not in found:
                found.append(item)
    return found[:_MAX_ITEMS]


def _close(name: str, options: list[str]) -> list[str]:
    low = {o.lower(): o for o in options}
    return [low[m] for m in difflib.get_close_matches(name.lower(), list(low), 3, 0.6)]


async def error_hints(
    client: OneCClient, cache: dict[str, Any], query: str, error_text: str, can: CanCall
) -> str:
    """Markdown-блок «Возможно, вы имели в виду» или пустая строка."""
    try:
        missing = parse_missing(error_text)
        tables = [n for k, n in missing if k == "table"]
        fields = [n for k, n in missing if k == "field"]
        lines: list[str] = []

        if tables and await can("metadata.GET"):
            tree = dict(await load_tree(client, cache, ""))
            filter_noise(tree)
            full = [f"{_TREE_TO_PREFIX[k]}.{n}" for k, v in tree.items()
                    if k in _TREE_TO_PREFIX for n in v]
            for name in tables:
                # Виртуальную таблицу (X.Остатки) отбрасываем: сравниваем Тип.Имя.
                key = ".".join(name.split(".")[:2])
                if (c := _close(key, full)):
                    lines.append(f"- таблица `{name}`: " + ", ".join(f"`{x}`" for x in c))

        if fields and await can("object.GET"):
            aliases = {a.lower(): (_PREFIX_LOWER[p.lower()], n)
                       for p, n, a in _ALIAS_RE.findall(query) if a.upper() not in _NOT_ALIAS}
            objs = list(dict.fromkeys(
                (_PREFIX_LOWER[p.lower()], n) for p, n in _TABLE_REF_RE.findall(query)
            ))
            for field in fields:
                qualifier, _, name = field.rpartition(".")
                # «Н.Артикулл»: поле ищем только среди реквизитов объекта этого алиаса.
                scope = [aliases[qualifier.lower()]] if qualifier.lower() in aliases else objs
                names = list(_STANDARD_FIELDS)
                for prefix, obj_name in scope[:_MAX_ITEMS]:
                    obj = await client.get(
                        f"/object/{quote(_PREFIX_TO_TYPE[prefix], safe='')}/{quote(obj_name, safe='')}"
                    )
                    for key in ("dimensions", "resources", "attributes"):
                        names += [a.get("name", "") for a in obj.get(key) or []]
                    for tp in obj.get("tabularParts") or []:
                        names.append(tp.get("name", ""))
                        names += [a.get("name", "") for a in tp.get("attributes") or []]
                if (c := _close(name, sorted({n for n in names if n}))):
                    lines.append(f"- поле `{field}`: " + ", ".join(f"`{x}`" for x in c))

        if not lines:
            return ""
        return "Возможно, вы имели в виду:\n" + "\n".join(lines)
    except Exception:  # noqa: BLE001 — подсказка необязательна, ошибка 1С важнее
        return ""


# --- Советник: чистый Python, без обращения к 1С ---

_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_STRING_RE = re.compile(r"\"(?:[^\"]|\"\")*\"")
_VT_RE = re.compile(
    r"Регистр(?:Накопления|Сведений|Бухгалтерии)\.\w+\."
    r"(Остатки|Обороты|ОстаткиИОбороты|СрезПоследних|СрезПервых)\s*\(", re.I
)
_SKIP_WHERE_FIELDS = {"период", "регистратор", "моментвремени", "активность"}


def _args_count(text: str, start: int) -> tuple[int, int]:
    """(число аргументов, позиция после закрывающей скобки) для скобки, открытой перед start."""
    depth, commas, i = 1, 0, start
    while i < len(text) and depth:
        c = text[i]
        depth += (c == "(") - (c == ")")
        commas += c == "," and depth == 1
        i += 1
    return (commas + 1 if text[start:i - 1].strip() else 0), i


def advise_query(query: str) -> list[str]:
    """Консервативные рекомендации по тексту запроса; пустой список — ничего не найдено."""
    no_comments = _COMMENT_RE.sub(" ", query)
    text = _STRING_RE.sub('""', no_comments)  # литералы не должны давать ложных срабатываний
    tips: list[str] = []

    for m in _VT_RE.finditer(text):
        args, end = _args_count(text, m.end())
        # Условие — 2-й параметр Остатки/Срез*, 4-й у Обороты*.
        if args >= (4 if m.group(1).lower() in {"обороты", "остаткииобороты"} else 2):
            continue
        alias = re.match(r"\s*(?:КАК\s+)?(\w+)", text[end:], re.I)
        where = re.search(r"\bГДЕ\b", text[end:], re.I)
        if not alias or not where or alias.group(1).upper() in _NOT_ALIAS:
            continue
        conds = re.finditer(
            rf"\b{re.escape(alias.group(1))}\.(\w+)\s*(?:=|<>|В\s*\(|В\s+ИЕРАРХИИ)",
            text[end + where.end():], re.I,
        )
        field = next((c.group(1) for c in conds if c.group(1).lower() not in _SKIP_WHERE_FIELDS), None)
        if field:
            tips.append(
                f"Отбор по `{alias.group(1)}.{field}` стоит в ГДЕ виртуальной таблицы "
                f"`.{m.group(1)}`: передайте условие параметром таблицы, иначе 1С сначала "
                "считает всё и лишь потом отфильтрует."
            )

    if re.search(r"\bОБЪЕДИНИТЬ\b(?!\s+ВСЕ\b)|\bUNION\b(?!\s+ALL\b)", text, re.I):
        tips.append("`ОБЪЕДИНИТЬ` без `ВСЕ` убирает дубликаты (дороже и может схлопнуть строки); "
                    "если дубликаты допустимы, используйте `ОБЪЕДИНИТЬ ВСЕ`.")
    if re.search(r"\b(?:ПОДОБНО|LIKE)\s*\"%", no_comments, re.I):
        tips.append("`ПОДОБНО \"%...\"` с ведущим `%` не использует индекс и читает всю таблицу.")
    return tips


def format_advice(tips: list[str]) -> str:
    return "" if not tips else "## Рекомендации\n\n" + "\n".join(f"- {t}" for t in tips) + "\n"
