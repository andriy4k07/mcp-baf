"""Маскирование ПДн в ответах MCP-инструментов.

`--mask-pii` должен закрывать все каналы, через которые ПДн попадают к
агенту: строки execute_query, журнал регистрации, структуру форм и
найденный код. Раньше маскирование жило только в execute_query, поэтому
телефон или email из журнала/кода уходили наружу в открытом виде.

Два механизма:
  * по имени колонки (`PII_COLUMN_MARKERS`) — для табличных результатов,
    где значения не отличить от обычных данных;
  * по значению (`PII_VALUE_RE`) — телефоны и email в свободном тексте.
Токен стабилен внутри процесса (соль на процесс), но не подбирается по
словарю и не даёт восстановить исходное значение.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Callable
from typing import Any

# Подстроки имён колонок с персональными данными (сравнение без регистра).
# shortcut: ПІБ у полі Наименование (фізособи-контрагенти) не маскується —
# лише за назвою колонки; розширити, якщо агент виводить Наименование фізосіб
PII_COLUMN_MARKERS = tuple(m.lower() for m in (
    "ФИО", "ПІБ", "ИНН", "ІПН", "РНОКПП", "КодПоДРФО", "ДатаРождения",
    "ДатаНародження", "Телефон", "Email", "ЭлектроннаяПочта", "Паспорт",
    "ДокументУдостоверяющий", "Адрес",
))
# Украинские телефоны (+380XXXXXXXXX, 0XXXXXXXXX с пробелами/дефисами/
# скобками) и email.
_EMAIL_RE = r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
_PHONE_RE = r"(?<!\d)(?:\+?38[\s-]*)?\(?0[\s-]*\d[\s-]*\d\)?(?:[\s-]*\d){7}(?!\d)"
PII_VALUE_RE = re.compile(_PHONE_RE + "|" + _EMAIL_RE)

# Идентификатороподобный токен: цифры/латиница/дефис, внутри есть хотя бы
# одна латинская буква — GUID, артикул, VIN, e1cib-ссылка, BSL-идентификатор.
# 10-значний цифровой прогон внутри такого токена — часть кода, а не телефон:
# ROCTUP/1c-mcp-toolkit#44 (анонимайзер съедал навигационный ref как IBAN).
# Email идёт ПЕРВЫМ в альтернативе: "abc-def@x.com" остаётся почтой.
# Сознательный компромисс: "tel-0671234567" не маскируется — в 1С-контексте
# телефоны живут в кириллическом/пунктуационном обрамлении, латиница в
# токене означает идентификатор.
_IDENT_RE = r"(?<![0-9a-zA-Z-])[0-9a-zA-Z-]*[a-zA-Z][0-9a-zA-Z-]*(?![0-9a-zA-Z-])"
PII_TEXT_RE = re.compile(
    r"(?P<email>" + _EMAIL_RE + r")|(?P<ident>" + _IDENT_RE + r")|(?P<phone>" + _PHONE_RE + r")"
)
# Соль случайная на процесс: токены стабильны внутри сессии, но не
# подбираются по словарю.
_PII_SALT = secrets.token_hex(16)


def pii_token(value: Any) -> str:
    """Стабильный в пределах процесса токен вместо значения."""
    digest = hashlib.sha256((_PII_SALT + str(value)).encode()).hexdigest()
    return f"PII:{digest[:8]}"


def scrub_pii_text(text: str, repl: Callable[[str], str]) -> str:
    """Заменяет телефон/email на repl(match), идентификатороподобные токены
    (GUID, артикулы, e1cib-ссылки) оставляет нетронутыми."""
    return PII_TEXT_RE.sub(
        lambda m: m.group() if m.group("ident") else repl(m.group()),
        text,
    )


def mask_pii_value(value: Any) -> Any:
    """Маскирует значение: непустые строки — по regex, остальное как есть."""
    if isinstance(value, str) and value:
        return scrub_pii_text(value, pii_token)
    return value


def mask_pii_text(value: Any) -> str:
    """Маскирует свободный текст (None -> пустая строка) по regex ПДн.

    Используется каналами без табличной структуры: журнал регистрации,
    структура формы, найденный код.
    """
    if value is None:
        return ""
    return scrub_pii_text(str(value), pii_token)


def mask_pii_result(r: dict[str, Any]) -> dict[str, Any]:
    """Маскирует ПДн в строках результата: по имени колонки и по regex."""
    columns = r.get("columns") or []
    sensitive = [
        any(m in str(c).rsplit(".", 1)[-1].lower() for m in PII_COLUMN_MARKERS)
        for c in columns
    ]

    def mask(i: int, v: Any) -> Any:
        if v is None or v == "":
            return v
        if i < len(sensitive) and sensitive[i]:
            return pii_token(v)
        return mask_pii_value(v)

    rows = r.get("rows")
    if rows is None:
        rows = []
    # Молчаливый пропуск маскирования — утечка ПДн: контракт должен падать явно.
    if not isinstance(rows, list) or any(not isinstance(row, list) for row in rows):
        raise ValueError(
            "execute_query: ответ 1С содержит rows не в виде списка списков — "
            "маскирование ПДн невозможно. Отключите --mask-pii или проверьте "
            "контракт расширения (/query)."
        )
    masked = [[mask(i, v) for i, v in enumerate(row)] for row in rows]
    return {**r, "rows": masked}
