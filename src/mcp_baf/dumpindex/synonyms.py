"""Двуязычные BSL-синонимы для полнотекстового поиска.

Порт dump/analyzer.go (buildSynonymMap) из Go-версии: ~50 пар ключевых слов
языка + пары имён встроенных функций платформы (из пакета mcp_baf.bsl).
"""

from __future__ import annotations

from functools import lru_cache

from mcp_baf.bsl import BUILTIN_FUNCTIONS

# Ключевые слова языка BSL (рус. <-> англ.), в нижнем регистре.
KEYWORD_PAIRS = {
    "процедура": "procedure",
    "конецпроцедуры": "endprocedure",
    "функция": "function",
    "конецфункции": "endfunction",
    "если": "if",
    "тогда": "then",
    "иначе": "else",
    "иначеесли": "elsif",
    "конецесли": "endif",
    "для": "for",
    "каждого": "each",
    "из": "in",
    "по": "to",
    "цикл": "do",
    "пока": "while",
    "конеццикла": "enddo",
    "возврат": "return",
    "попытка": "try",
    "исключение": "except",
    "конецпопытки": "endtry",
    "новый": "new",
    "перем": "var",
    "экспорт": "export",
    "знач": "val",
    "не": "not",
    "и": "and",
    "или": "or",
    "истина": "true",
    "ложь": "false",
    "неопределено": "undefined",
    "выбрать": "select",
    "где": "where",
    "как": "as",
    "левое": "left",
    "внутреннее": "inner",
    "соединение": "join",
    "сгруппировать": "group",
    "упорядочить": "order",
    "имеющие": "having",
    "различные": "distinct",
    "объединить": "union",
    "выразить": "cast",
    "количество": "count",
    "сумма": "sum",
    "максимум": "max",
    "минимум": "min",
    "среднее": "avg",
    "добавитьобработчик": "addhandler",
    "вызватьисключение": "raise",
    "выполнить": "execute",
    "перейти": "goto",
    "продолжить": "continue",
    "прервать": "break",
}


@lru_cache(maxsize=1)
def build_synonym_map() -> dict[str, str]:
    """Двунаправленная карта синонимов BSL (в нижнем регистре)."""
    m: dict[str, str] = {}

    for ru, en in KEYWORD_PAIRS.items():
        if ru == en:
            continue
        m[ru] = en
        m[en] = ru

    # Встроенные функции платформы. Пара пропускается целиком, если любой
    # из ключей уже занят — иначе двунаправленные цепочки ломаются, когда
    # ключевое слово и функция делят одно английское имя.
    for fn in BUILTIN_FUNCTIONS:
        ru = fn["name"].lower()
        en = fn["name_en"].lower()
        if not ru or not en or ru == en:
            continue
        if ru in m or en in m:
            continue
        m[ru] = en
        m[en] = ru

    return m
