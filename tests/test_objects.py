"""Контракты read-only инструментов: валидация, форматирование, аудит."""

import asyncio
import json

import httpx
import pytest
from mcp.server.mcpserver import MCPServer

from mcp_baf_audit import AuditLog, set_trace_id
from mcp_baf.client import OneCClient
from mcp_baf.config import Config
from mcp_baf.tools import objects

GUID = '12345678-1234-5678-9abc-123456789abc'
KIND = 'Справочник.Контрагенты'
LINK = 'e1cib/data/' + KIND + '?ref=9abc123456789abc5678123412345678'


def setup_tools(tmp_path, result, status=200):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(status, json=result)
    audit = AuditLog(str(tmp_path))
    client = OneCClient(Config(base_url='http://test'), httpx.MockTransport(handler), audit=audit)
    server = MCPServer('test')
    objects.register(server, client, audit)
    return server, client, requests


def call(server, name, **arguments):
    return asyncio.run(server.call_tool(name, arguments)).content[0].text


def events(tmp_path):
    return [json.loads(line) for line in (tmp_path / 'audit.log').read_text().splitlines()]


def test_references_body_grouping_and_privacy(tmp_path):
    set_trace_id(None)
    server, client, requests = setup_tools(tmp_path, dict(
        hits=[dict(found_in_meta='Документ.Продажа', found_in_object='PRIVATE_RESULT', path='Товары.Контрагент', match_kind='tabular_section')],
        timeout_exceeded=True, truncated=False, skipped_names=[dict(name='Справочник.X', reason='Нет прав')],
    ))
    text = call(server, 'find_object_references', ref=GUID, ref_kind=KIND)
    assert 'Документ.Продажа (1)' in text
    assert 'Поиск неполный' in text and 'Нет прав' in text
    assert requests[0].url.path == '/refs'
    body = json.loads(requests[0].content)
    assert body == dict(ref=GUID, ref_kind=KIND, scope=objects.DEFAULT_SCOPE, limit_hits=200, limit_per_meta=20, timeout_budget_sec=30)
    audit = events(tmp_path)
    assert 'PRIVATE_RESULT' not in json.dumps(audit)
    assert len([e for e in audit if e['event'] == 'one_c.http']) == 1
    http = next(e for e in audit if e['event'] == 'one_c.http')
    tool = next(e for e in audit if e['event'] == 'tool.call')
    assert http['trace_id'] == tool['trace_id']
    asyncio.run(client.aclose())


@pytest.mark.parametrize('arguments', [
    dict(ref='not-a-guid', ref_kind=KIND),
    dict(ref=GUID, ref_kind='Документ.X;УДАЛИТЬ'),
    dict(ref=GUID, ref_kind='РегистрСведений.X'),
    dict(ref=GUID, ref_kind='Перечисление.X'),
    dict(ref=GUID, ref_kind=KIND, scope=[]),
    dict(ref=GUID, ref_kind=KIND, scope=['unknown']),
    dict(ref=GUID, ref_kind=KIND, limit_hits=1001),
    dict(ref=GUID, ref_kind=KIND, limit_per_meta=0),
    dict(ref=GUID, ref_kind=KIND, timeout_budget_sec=121),
])
def test_references_invalid_input_no_http(tmp_path, arguments):
    server, client, requests = setup_tools(tmp_path, {})
    with pytest.raises(Exception):
        call(server, 'find_object_references', **arguments)
    assert requests == []
    asyncio.run(client.aclose())


def test_link_roundtrip_and_escaped_presentation(tmp_path):
    server, client, requests = setup_tools(tmp_path, dict(found=True, kind=KIND, ref=GUID, presentation='[PRIVATE_NAME]', link=LINK))
    text = call(server, 'get_object_link', mode='make', ref=GUID, kind=KIND)
    assert '[\\[PRIVATE_NAME\\]](' in text and GUID in text
    assert objects.parse_link(LINK) == (KIND, GUID)
    assert objects.parse_link('https://host/base/#' + LINK) == (KIND, GUID)
    call(server, 'get_object_link', mode='resolve', link=LINK)
    assert json.loads(requests[-1].content) == dict(mode='resolve', ref=GUID, kind=KIND)
    assert 'PRIVATE_NAME' not in json.dumps(events(tmp_path))
    asyncio.run(client.aclose())


@pytest.mark.parametrize('link', [
    'javascript:alert(1)', 'https://host/path', LINK + '&ref=other',
    LINK + '&index=1', LINK.replace('Контрагенты', 'X;DELETE'),
    'e1cib/data/Документ.X?ref=00000000000000000000000000000000',
])
def test_bogus_link_rejected(link):
    with pytest.raises(ValueError):
        objects.parse_link(link)


def test_missing_object_and_service_error(tmp_path):
    server, client, _ = setup_tools(tmp_path, dict(found=False))
    assert 'не найден' in call(server, 'get_object_link', mode='make', ref=GUID, kind=KIND)
    asyncio.run(client.aclose())
    server, client, _ = setup_tools(tmp_path, dict(error='Нет прав'), status=403)
    with pytest.raises(Exception, match='Нет прав'):
        call(server, 'get_object_link', mode='make', ref=GUID, kind=KIND)
    asyncio.run(client.aclose())


def test_rights_unavailable_is_not_false(tmp_path):
    server, client, requests = setup_tools(tmp_path, dict(
        rights=[dict(right='Чтение', subject='Test', allowed=None)],
        notes=['Проверка за ролью недоступна'],
    ))
    text = call(server, 'get_metadata_rights', metadata_object='Документ.Продажа', roles=['Test'])
    assert 'проверка недоступна' in text and 'RLS' in text
    assert '| нет |' not in text
    assert json.loads(requests[0].content)['roles'] == ['Test']
    asyncio.run(client.aclose())


def test_rights_admin_refusal_no_false_table(tmp_path):
    server, client, _ = setup_tools(tmp_path, dict(error='Требует административных прав'), status=403)
    with pytest.raises(Exception, match='административных'):
        call(server, 'get_metadata_rights', metadata_object='Документ.Продажа', user_name='Other')
    asyncio.run(client.aclose())
