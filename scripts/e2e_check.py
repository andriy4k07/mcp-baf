"""Ручная e2e-проверка: запускает сервер по stdio и вызывает все инструменты.

Использование (mock-1c должен слушать на :8080):
    python scripts/e2e_check.py
"""

import asyncio
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CALLS = [
    ("get_configuration_info", {}),
    ("get_metadata_tree", {}),
    ("get_metadata_tree", {"filter": "Справочники"}),
    ("get_object_structure", {"object_type": "Catalog", "object_name": "Контрагенты"}),
    ("validate_query", {"query": "ВЫБРАТЬ * ИЗ Справочник.Контрагенты"}),
    (
        "execute_query",
        {"query": "ВЫБРАТЬ Наименование ИЗ Справочник.Контрагенты", "limit": 5},
    ),
    # Форма обогащается элементами/командами/обработчиками из dump (Form.xml).
    ("get_form_structure", {"object_type": "Catalog", "object_name": "Номенклатура"}),
    ("get_event_log", {"limit": 3}),
    ("search_code", {"query": "StrFind"}),
    ("search_code", {"query": "Процедура \\w+\\(", "mode": "regex", "category": "Документ"}),
    ("search_code", {"query": "стрнайти", "mode": "exact"}),
    ("bsl_syntax_help", {"query": "StrFind"}),
]

FORM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Form xmlns="http://v8.1c.ru/8.3/xcf/logform" xmlns:v8="http://v8.1c.ru/8.1/data/core" version="2.18">
  <Title>
    <v8:item><v8:lang>ru</v8:lang><v8:content>Номенклатура (тест)</v8:content></v8:item>
  </Title>
  <Events>
    <Event name="OnOpen">ПриОткрытии</Event>
  </Events>
  <ChildItems>
    <InputField name="Наименование" id="1">
      <DataPath>Объект.Наименование</DataPath>
      <Events>
        <Event name="OnChange">НаименованиеПриИзменении</Event>
      </Events>
    </InputField>
  </ChildItems>
  <Commands>
    <Command name="Записать" id="1"><Action>ЗаписатьВыполнить</Action></Command>
  </Commands>
</Form>"""


def make_dump(root: Path) -> None:
    """Создаёт миниатюрную dump-выгрузку для проверки search_code и форм."""
    files = {
        "Catalogs/Номенклатура/Ext/ObjectModule.bsl": (
            "Процедура ПередЗаписью()\n"
            '    Позиция = СтрНайти(Наименование, "тест");\n'
            "КонецПроцедуры\n"
        ),
        "Documents/Реализация/Ext/ObjectModule.bsl": (
            "Процедура ОбработкаПроведения()\n"
            "    // проведение документа\n"
            "КонецПроцедуры\n"
        ),
        "Catalogs/Номенклатура/Forms/ФормаЭлемента/Ext/Form.xml": FORM_XML,
    }
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8-sig")


async def main() -> None:
    dump_dir = Path(tempfile.mkdtemp(prefix="mcp1c-dump-"))
    cache_dir = Path(tempfile.mkdtemp(prefix="mcp1c-cache-"))
    make_dump(dump_dir)

    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m", "mcp_baf",
            "--base", "http://localhost:8080/mcp",
            "--dump", str(dump_dir),
            "--cache-dir", str(cache_dir),
        ],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("tools:", [t.name for t in tools.tools])

            prompts = await session.list_prompts()
            print("prompts:", [p.name for p in prompts.prompts])

            prompt = await session.get_prompt(
                "review_module",
                {"object_type": "Catalog", "object_name": "Номенклатура"},
            )
            text = prompt.messages[0].content.text
            print("\n=== prompt review_module ===")
            print(text[:200], "...")

            failed = False
            for name, args in CALLS:
                result = await session.call_tool(name, args)
                status = "ERROR" if result.isError else "ok"
                failed = failed or result.isError
                print(f"\n=== {name} {args} [{status}] ===")
                print(result.content[0].text)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
