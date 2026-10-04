"""Проверка list и прямых calls, обновление прав, отказ при недоступности сервиса."""

import asyncio
import json

import httpx
import pytest
from mcp.types import ToolAnnotations
from mcp.client import Client
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError

from mcp_baf_audit import AuditLog, set_trace_id
from mcp_baf.access import AccessMCP
from mcp_baf.client import OneCClient
from mcp_baf.config import Config


def test_list_cache_call_refresh_and_denial_audit(tmp_path):
    allowed = ['metadata.GET']
    calls = []
    executed = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={'methods': allowed[:]})
    audit = AuditLog(str(tmp_path))
    client = OneCClient(Config(base_url='http://test'), httpx.MockTransport(handler), audit=audit)
    server = AccessMCP('test', access_client=client, audit=audit)
    @server.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def get_metadata_tree():
        executed.append(True)
        return 'ok'
    @server.tool()
    async def bsl_syntax_help():
        return 'local'
    @server.tool()
    async def execute_query(query: str):
        raise AssertionError('hidden tool must not execute')

    async def scenario():
        assert {t.name for t in await server.list_tools()} == {'get_metadata_tree', 'bsl_syntax_help'}
        await server.list_tools()
        assert len(calls) == 1
        await server.call_tool('get_metadata_tree', {})
        assert executed == [True] and len(calls) == 2
        allowed.clear()
        with pytest.raises(ToolError):
            await server.call_tool('get_metadata_tree', {'private': 'PRIVATE'})
        assert executed == [True]
        with pytest.raises(ToolError):
            await server.call_tool('execute_query', {'query': 'PRIVATE_QUERY'})
        assert {t.name for t in await server.list_tools()} == {'bsl_syntax_help'}
        assert await server.call_tool('bsl_syntax_help', {})
        await client.aclose()
    set_trace_id(None)
    asyncio.run(scenario())
    events = [json.loads(x) for x in (tmp_path / 'audit.log').read_text().splitlines()]
    denials = [x for x in events if x['event'] == 'tool.error']
    assert len(denials) == 2
    assert all(x['args'] == {'access_denied': True} for x in denials)
    assert 'PRIVATE' not in json.dumps(events)
    assert all(x['trace_id'] for x in denials)


@pytest.mark.parametrize('status,body', [(404, {}), (200, {'methods':'all'}), (200, {'methods':[True]}), (200, {})])
def test_fail_closed_and_local_tools_survive(tmp_path, status, body):
    client = OneCClient(Config(base_url='http://test'), httpx.MockTransport(lambda r: httpx.Response(status, json=body)))
    server = AccessMCP('test', access_client=client, audit=AuditLog(str(tmp_path)))
    @server.tool()
    async def execute_query(query: str):
        raise AssertionError('must not execute')
    @server.tool()
    async def bsl_syntax_help():
        return 'ok'
    async def scenario():
        assert [t.name for t in await server.list_tools()] == ['bsl_syntax_help']
        with pytest.raises(ToolError, match='capabilities'):
            await server.call_tool('execute_query', {'query': 'ВЫБРАТЬ 1'})
        await client.aclose()
    asyncio.run(scenario())


@pytest.mark.parametrize('mode', ['auto', 'legacy'])
def test_real_mcp_protocol_filters_list_and_denies_hidden_call(tmp_path, mode):
    from mcp_baf.tools import objects, bsl_help
    allowed = ['refs.POST']
    requests = []
    def handler(request):
        requests.append(request.url.path)
        if request.url.path == '/capabilities':
            return httpx.Response(200, json={'methods':allowed[:]})
        return httpx.Response(200,json={'hits':[],'skipped_names':[],'truncated':False,'timeout_exceeded':False})
    audit = AuditLog(str(tmp_path))
    client = OneCClient(Config(base_url='http://test'),httpx.MockTransport(handler),audit=audit)
    server = AccessMCP('test',access_client=client,audit=audit)
    objects.register(server,client,audit)
    bsl_help.register(server,audit)
    @server.tool()
    async def request_context(ctx: Context) -> str:
        # Перехват call_tool обязан передать исходный контекст SDK 2.
        return ctx.request_id
    async def scenario():
        async with Client(server, mode=mode) as session:
            listing = await session.list_tools()
            assert {t.name for t in listing.tools} == {'find_object_references','bsl_syntax_help','request_context'}
            context_result = await session.call_tool('request_context', {})
            assert not context_result.is_error and context_result.content[0].text
            result = await session.call_tool('find_object_references',dict(ref='12345678-1234-5678-9abc-123456789abc',ref_kind='Справочник.X'))
            assert not result.is_error and 'Совпадений' in result.content[0].text
            allowed.clear()
            result = await session.call_tool('find_object_references',dict(ref='12345678-1234-5678-9abc-123456789abc',ref_kind='Справочник.X'))
            assert result.is_error and 'прав' in result.content[0].text
            result = await session.call_tool('bsl_syntax_help',{'query':'СтрНайти'})
            assert not result.is_error
            assert {t.name for t in (await session.list_tools(cache_mode='refresh')).tools} == {'bsl_syntax_help','request_context'}
        await client.aclose()
    asyncio.run(scenario())
    assert requests.count('/refs') == 1
