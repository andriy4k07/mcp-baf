"""get_form_structure: отказ dump-обогащения виден в ответе, а не только в логе."""

import asyncio

import httpx
import pytest
from mcp.server.mcpserver import MCPServer

from mcp_baf_audit import AuditLog
from mcp_baf.client import OneCClient
from mcp_baf.config import Config
from mcp_baf.tools import form


def test_dump_rejection_reported_in_output(tmp_path):
    dump = tmp_path / "dump"
    xml = dump / "Catalogs" / "Тест" / "Forms" / "ФормаЭлемента" / "Ext" / "Form.xml"
    xml.parent.mkdir(parents=True)
    xml.write_text('<!DOCTYPE Form [<!ENTITY a "x">]><Form/>', encoding="utf-8")

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"name": "ФормаЭлемента", "title": "Тест"})
    )
    audit = AuditLog(str(tmp_path / "audit"))
    client = OneCClient(Config(base_url="http://test"), transport, audit=audit)
    mcp = MCPServer("test")
    form.register(mcp, client, audit, dump_dir=str(dump))

    async def scenario():
        result = await mcp.call_tool("get_form_structure", {
            "object_type": "Catalog", "object_name": "Тест",
        })
        await client.aclose()
        return result

    text = asyncio.run(scenario()).content[0].text
    assert "ФормаЭлемента" in text
    assert "Структура из dump недоступна" in text and "DTD" in text


FORM_XML = """<Form xmlns="http://v8.1c.ru/8.3/xcf/logform" xmlns:v8="http://v8.1c.ru/8.1/data/core">
  <Title><v8:item><v8:lang>ru</v8:lang><v8:content>{title}</v8:content></v8:item></Title>
  <ChildItems><InputField name="{field}" id="1"><DataPath>Объект.{field}</DataPath></InputField></ChildItems>
</Form>"""


@pytest.mark.parametrize("form_name, http_name, header, field, other", [
    # Явно заданная форма: шапка и элементы из неё, а не из основной формы HTTP.
    ("ФормаСписку", "ФормаДокумента", "ФормаСписку", "ПолеСписка", "ПолеДокумента"),
    # Без form_name берётся первая по алфавиту форма dump — шапка должна совпасть с ней.
    ("", "ФормаСписку", "ФормаДокумента", "ПолеДокумента", "ПолеСписка"),
])
def test_header_and_elements_describe_the_same_form(tmp_path, form_name, http_name, header, field, other):
    dump = tmp_path / "dump"
    for name, title, field_name in (
        ("ФормаДокумента", "Документ", "ПолеДокумента"),
        ("ФормаСписку", "Список", "ПолеСписка"),
    ):
        xml = dump / "Documents" / "Тест" / "Forms" / name / "Ext" / "Form.xml"
        xml.parent.mkdir(parents=True)
        xml.write_text(FORM_XML.format(title=title, field=field_name), encoding="utf-8")

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"name": http_name, "title": "HTTP синоним"})
    )
    audit = AuditLog(str(tmp_path / "audit"))
    client = OneCClient(Config(base_url="http://test"), transport, audit=audit)
    mcp = MCPServer("test")
    form.register(mcp, client, audit, dump_dir=str(dump))

    async def scenario():
        args = {"object_type": "Document", "object_name": "Тест"}
        if form_name:
            args["form_name"] = form_name
        result = await mcp.call_tool("get_form_structure", args)
        await client.aclose()
        return result

    text = asyncio.run(scenario()).content[0].text
    assert f"# Форма: {header}\n" in text
    assert "**Заголовок:** " + ("Список" if header == "ФормаСписку" else "Документ") in text
    assert field in text and other not in text
