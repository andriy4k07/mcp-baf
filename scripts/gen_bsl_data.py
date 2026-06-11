"""Генерирует mcp_baf/bsl/_functions_data.py из bsl/functions.go (Go-версия).

Извлекает полные записи справочника встроенных функций 1С (имя, описание,
синтаксис, параметры, возвращаемый тип, пример), чтобы Python-версия
использовала те же данные, что и Go: bsl_syntax_help и BSL-синонимы
полнотекстового поиска.

Запуск (путь к functions.go Go-версии — аргументом; по умолчанию
ожидается монорепозиторий с Go-кодом на два уровня выше):
    python scripts/gen_bsl_data.py [путь/к/bsl/functions.go]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEFAULT_SOURCE = Path(__file__).resolve().parents[2] / "bsl" / "functions.go"
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
TARGET = (
    Path(__file__).resolve().parents[1]
    / "src" / "mcp_baf" / "bsl" / "_functions_data.py"
)

# Поле структуры Go: Name: "..." или Example: `...` (raw-строка).
FIELD_RE = re.compile(r'(\w+):\s+("(?:[^"\\]|\\.)*"|`[^`]*`)\s*,')

FIELDS = {
    "Name": "name",
    "NameEn": "name_en",
    "Description": "description",
    "Syntax": "syntax",
    "Parameters": "parameters",
    "ReturnType": "return_type",
    "Example": "example",
}

GO_ESCAPES = {'\\"': '"', "\\\\": "\\", "\\n": "\n", "\\t": "\t", "\\r": "\r"}


def unquote_go(literal: str) -> str:
    if literal.startswith("`"):
        return literal[1:-1]  # raw-строка, без экранирования
    value = literal[1:-1]
    return re.sub(
        r'\\["\\ntr]', lambda m: GO_ESCAPES[m.group(0)], value
    )


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")

    functions: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for m in FIELD_RE.finditer(text):
        go_field, literal = m.group(1), m.group(2)
        key = FIELDS.get(go_field)
        if key is None:
            continue
        # Каждая запись начинается с Name — встретив его, закрываем предыдущую.
        if key == "name" and current:
            functions.append(current)
            current = {}
        current[key] = unquote_go(literal)
    if current:
        functions.append(current)

    if not functions:
        raise SystemExit(f"no Function entries found in {SOURCE}")

    lines = [
        '"""Справочник встроенных функций 1С (порт bsl/functions.go).',
        "",
        "Файл сгенерирован скриптом scripts/gen_bsl_data.py из bsl/functions.go.",
        "Не редактируйте вручную.",
        '"""',
        "",
        "BUILTIN_FUNCTIONS = [",
    ]
    for fn in functions:
        lines.append("    {")
        for key in FIELDS.values():
            lines.append(f"        {key!r}: {fn.get(key, '')!r},")
        lines.append("    },")
    lines.append("]")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"written {len(functions)} functions to {TARGET}")


if __name__ == "__main__":
    main()
