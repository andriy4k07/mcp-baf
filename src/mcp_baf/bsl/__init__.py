"""Справочник встроенных функций языка 1С (BSL).

Порт пакета bsl из Go-версии. Данные генерируются из bsl/functions.go
скриптом scripts/gen_bsl_data.py.
"""

from __future__ import annotations

from mcp_baf.bsl._functions_data import BUILTIN_FUNCTIONS

__all__ = ["BUILTIN_FUNCTIONS", "search"]

# Индекс для регистронезависимого поиска: (имя в н.р., англ. имя в н.р., запись).
_SEARCH_INDEX = [
    (fn["name"].lower(), fn["name_en"].lower(), fn) for fn in BUILTIN_FUNCTIONS
]


def search(query: str) -> list[dict[str, str]]:
    """Ищет функции по имени (русскому или английскому), без учёта регистра."""
    q = query.lower()
    return [fn for name, name_en, fn in _SEARCH_INDEX if q in name or q in name_en]
