"""Происхождение колонок текста запроса 1С для маскирования ПДн (issue #127).

Консервативный разбор ВЫБРАТЬ/SELECT (ru+en): для каждой колонки итогового
результата собирает имена исходных полей, из которых она получена — через
псевдонимы, выражения, вложенные подзапросы в ИЗ, ОБЪЕДИНИТЬ и временные
таблицы пакета (ПОМЕСТИТЬ). Модуль только собирает имена (нижний регистр);
решение «это ПДн» принимает `pii`. Любая неожиданность — `None`: вызывающий
код остаётся на прежнем поведении, маскирования меньше не становится.
Литералы и комментарии пропускаются, `&Параметры` не считаются полями.
"""

from __future__ import annotations

import re

MAX_TOKENS = 20000   # потолок работы: длиннее — отказ (None), не разбор
MAX_DEPTH = 30       # вложенность подзапросов

# Литерал ("" — экранирование), комментарий, параметр, слово, знак.
_TOKEN_RE = re.compile(r'"(?:[^"]|"")*"?|//[^\n]*|&\w+|\w+|\S')
_WORD_RE = re.compile(r"\w+")

_SELECT = frozenset({"выбрать", "select"})
_UNION = frozenset({"объединить", "union"})
_FROM = frozenset({"из", "from"})
_INTO = frozenset({"поместить", "into"})
_AS = frozenset({"как", "as"})
_JOIN = frozenset({"соединение", "join"})
_TAIL = frozenset({
    "где", "where", "сгруппировать", "group", "имеющие", "having",
    "упорядочить", "order", "итоги", "totals", "для", "for",
})
# Что обрывает список полей / источников на нулевом уровне скобок.
_FIELDS_STOP = _FROM | _INTO | _TAIL | _UNION
_FROM_STOP = _TAIL | _UNION
_NOT_ALIAS = _FROM_STOP | _JOIN | {
    "по", "on", "левое", "правое", "внутреннее", "полное", "внешнее",
    "left", "right", "inner", "full", "outer",
}

Cols = list[tuple[str | None, frozenset[str]]]  # (имя, источники) в порядке колонок


class _Bail(Exception):
    """Разбор невозможен — вызывающий откатывается на прежнее поведение."""


def column_sources(query: str) -> list[frozenset[str]] | None:
    """Источники каждой колонки итогового результата пакета или None."""
    try:
        return _Parser(query).run()
    except (_Bail, IndexError, RecursionError):
        return None


class _Parser:
    def __init__(self, query: str) -> None:
        toks = [t for t in _TOKEN_RE.findall(query) if not t.startswith("//")]
        if len(toks) > MAX_TOKENS:
            raise _Bail
        self.t = toks
        self.low = [t.lower() for t in toks]
        self.match: dict[int, int] = {}
        stack: list[int] = []
        for i, t in enumerate(toks):
            if t == "(":
                stack.append(i)
            elif t == ")":
                if not stack:
                    raise _Bail
                self.match[stack.pop()] = i
        if stack:
            raise _Bail
        self.temps: dict[str, Cols] = {}

    def run(self) -> list[frozenset[str]] | None:
        n, start = len(self.t), 0
        result = None
        while start < n:
            end = start
            while end < n and self.t[end] != ";":
                end = self.match[end] + 1 if self.t[end] == "(" else end + 1
            if end > start:  # пустые statement между `;` пропускаем
                result = None
                if self.low[start] in _SELECT:
                    cols, into = self._statement(start, end, 0)
                    if into:
                        self.temps[into] = cols
                    else:
                        result = [s for _, s in cols]
            start = end + 1
        return result

    def _statement(self, i: int, end: int, depth: int) -> tuple[Cols, str]:
        """SELECT {UNION [ALL] SELECT}: колонка i = объединение источников i."""
        if depth > MAX_DEPTH:
            raise _Bail
        merged: Cols | None = None
        into = ""
        while True:
            cols, sel_into, i = self._select(i, end, depth)
            into = into or sel_into
            if merged is None:
                merged = cols
            elif len(cols) != len(merged):
                raise _Bail
            else:
                merged = [(n, a | b) for (n, a), (_, b) in zip(merged, cols)]
            if i >= end or self.low[i] not in _UNION:
                return merged, into
            i += 1
            if self.low[i] in ("все", "all"):
                i += 1
            if self.low[i] not in _SELECT:
                raise _Bail

    def _skip(self, i: int) -> int:
        return self.match[i] + 1 if self.t[i] == "(" else i + 1

    def _select(self, i: int, end: int, depth: int) -> tuple[Cols, str, int]:
        low = self.low
        i += 1
        while low[i] in ("разрешенные", "различные", "allowed", "distinct"):
            i += 1
        if low[i] in ("первые", "top"):
            i += 2
        items, begin = [], i
        while i < end and low[i] not in _FIELDS_STOP:
            if self.t[i] == ",":
                items.append((begin, i))
                begin = i + 1
            i = self._skip(i)
        items.append((begin, i))
        into = ""
        if i < end and low[i] in _INTO:
            into = low[i + 1]
            i += 2
            while i < end and low[i] not in _FROM and low[i] not in _FROM_STOP:
                i = self._skip(i)
        scope: dict[str, Cols | None] = {}
        if i < end and low[i] in _FROM:
            i = self._sources(i + 1, end, scope, depth)
        while i < end and low[i] not in _UNION:  # хвост: ГДЕ/СГРУППИРОВАТЬ/...
            i = self._skip(i)
        cols: Cols = []
        for a, b in items:
            cols.extend(self._field(a, b, scope))
        return cols, into, i

    def _alias(self, i: int, end: int) -> tuple[str, int]:
        if i < end and self.low[i] in _AS:
            return self.low[i + 1], i + 2
        if i < end and _WORD_RE.fullmatch(self.t[i]) and self.low[i] not in _NOT_ALIAS:
            return self.low[i], i + 1
        return "", i

    def _sources(self, i: int, end: int, scope: dict, depth: int) -> int:
        """Источники ИЗ: подзапросы и временные таблицы получают колонки."""
        t, low = self.t, self.low
        expecting = True
        while i < end and low[i] not in _FROM_STOP:
            if not expecting:
                expecting = t[i] == "," or low[i] in _JOIN
                i = self._skip(i)
            elif t[i] == "(":
                close = self.match[i]
                cols = None
                if low[i + 1] in _SELECT:
                    cols = self._statement(i + 1, close, depth + 1)[0]
                alias, i = self._alias(close + 1, end)
                if alias:
                    scope[alias] = cols
                expecting = False
            else:
                segs = [low[i]]
                i += 1
                while i + 1 < end and t[i] == "." and _WORD_RE.fullmatch(t[i + 1]):
                    segs.append(low[i + 1])
                    i += 2
                if i < end and t[i] == "(":  # параметры виртуальной таблицы
                    i = self.match[i] + 1
                alias, i = self._alias(i, end)
                scope[alias or segs[-1]] = self.temps.get(segs[0]) if len(segs) == 1 else None
                expecting = False
        return i

    def _field(self, a: int, b: int, scope: dict) -> Cols:
        t, low = self.t, self.low
        if t[a:b] == ["*"] or (b - a == 3 and t[a + 1:b] == [".", "*"]):
            srcs = [low[a]] if b - a == 3 else list(scope)
            if any(scope.get(s) is None for s in srcs):
                raise _Bail  # звёздочка по обычной таблице: состав колонок неизвестен
            return [c for s in srcs for c in scope[s]]
        name = None
        if b - a >= 3 and low[b - 2] in _AS and _WORD_RE.fullmatch(t[b - 1]):
            name, b = low[b - 1], b - 2
        words = self._resolve(a, b, scope)
        if name is None and re.fullmatch(r"\w+(\.\w+)*", "".join(t[a:b])):
            name = low[b - 1]  # неявное имя — последний сегмент пути
        return [(name, frozenset(words))]

    def _resolve(self, a: int, b: int, scope: dict) -> set[str]:
        t, low = self.t, self.low
        out: set[str] = set()
        i = a
        while i < b:
            if not _WORD_RE.fullmatch(t[i]):
                i += 1
                continue
            segs = [low[i]]
            i += 1
            while i + 1 < b and t[i] == "." and _WORD_RE.fullmatch(t[i + 1]):
                segs.append(low[i + 1])
                i += 2
            known = scope.get(segs[0])
            if len(segs) > 1 and known is not None:
                hit = [s for n, s in known if n == segs[1]]
                if hit:  # поле подзапроса/временной таблицы -> его источники
                    out.update(*hit, segs[2:])
                    continue
            elif len(segs) == 1:
                for cols in scope.values():
                    out.update(*(s for n, s in cols or () if n == segs[0]))
            out.update(segs)
        return out
