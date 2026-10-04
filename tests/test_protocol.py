"""Контракты SDK 2: схемы, все prompts, ошибки и реальный stdio-процесс."""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_baf import __version__
from mcp_baf.access import TOOL_METHODS
from mcp_baf.client import OneCClient
from mcp_baf.config import Config
from mcp_baf.server import EXPECTED_EXTENSION_VERSION, create_server


@pytest.mark.parametrize('mode', ['auto', 'legacy'])
@pytest.mark.parametrize('local_options', [False, True])
def test_tool_schemas_prompts_and_expected_errors(tmp_path, monkeypatch, mode, local_options, caplog):
    def handler(request):
        if request.url.path == '/version':
            return httpx.Response(200, json={'version': EXPECTED_EXTENSION_VERSION})
        if request.url.path == '/capabilities':
            return httpx.Response(200, json={'methods': list(TOOL_METHODS.values())})
        return httpx.Response(403, json={'error': 'Нет прав на чтение объекта'})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr('mcp_baf.server.OneCClient', lambda config, **kw: OneCClient(config, transport, **kw))
    config = Config(base_url='http://test', cache_dir=str(tmp_path))
    if local_options:
        dump = tmp_path / 'dump'
        dump.mkdir()
        (dump / 'Module.bsl').write_text('Сообщить(1);', encoding='utf-8')
        config.dump_dir = str(dump)
        config.help_dir = str(Path(__file__).parent / 'testdata')
    server = create_server(config)

    async def scenario():
        async with Client(server, mode=mode) as client:
            tools = (await client.list_tools()).tools
            assert len(tools) == (16 if local_options else 13)
            for tool in tools:
                assert tool.input_schema['type'] == 'object'
                assert tool.annotations.read_only_hint
                # Имена Python snake_case, wire-формат MCP остаётся camelCase.
                wire = tool.model_dump(by_alias=True, exclude_none=True)
                assert wire['inputSchema']['type'] == 'object'
                assert wire['annotations']['readOnlyHint'] is True
                assert 'title' not in tool.input_schema

            prompts = (await client.list_prompts()).prompts
            assert len(prompts) == 11
            for prompt in prompts:
                args = {arg.name: 'ТЕСТ' for arg in prompt.arguments or []}
                result = await client.get_prompt(prompt.name, args)
                assert len(result.messages) == 1
                assert result.messages[0].role == 'user'
                assert result.messages[0].content.text

            result = await client.call_tool('get_object_link', {'mode': 'make', 'ref': 'invalid', 'kind': 'Справочник.X'})
            assert result.is_error and 'GUID' in result.content[0].text
            result = await client.call_tool('get_object_link', {
                'mode': 'make', 'ref': '12345678-1234-5678-9abc-123456789abc', 'kind': 'Справочник.X',
            })
            assert result.is_error and 'Нет прав на чтение объекта' in result.content[0].text
            result = await client.call_tool('bsl_format', {'src': 'Если Истина Тогда'})
            assert result.is_error and 'Форматирование недоступно' in result.content[0].text

    asyncio.run(scenario())
    assert not [record for record in caplog.records if record.levelname == 'ERROR']


@pytest.mark.parametrize('mode', ['auto', 'legacy'])
def test_stdio_process_without_database(tmp_path, mode):
    # Закрытый loopback-порт: тест не требует базы, сети или учётных данных.
    params = StdioServerParameters(
        command=sys.executable,
        args=['-m', 'mcp_baf', '--base', 'http://127.0.0.1:1', '--user', '', '--pass', '', '--cache-dir', str(tmp_path)],
    )

    async def scenario():
        with (tmp_path / 'stderr.log').open('w+', encoding='utf-8') as stderr:
            async with Client(stdio_client(params, errlog=stderr), mode=mode, read_timeout_seconds=10) as client:
                assert client.server_info.name == 'mcp-baf'
                assert client.server_info.version == __version__
                assert {t.name for t in (await client.list_tools()).tools} == {'bsl_syntax_help', 'bsl_analyze', 'bsl_format'}
                assert len((await client.list_prompts()).prompts) == 11
                result = await client.call_tool('bsl_format', {'src': 'Процедура Тест()\nСообщить(1);\nКонецПроцедуры'})
                assert not result.is_error and '    Сообщить(1);' in result.content[0].text
                result = await client.call_tool('execute_query', {'query': 'PRIVATE_QUERY'})
                assert result.is_error and 'capabilities' in result.content[0].text
            stderr.seek(0)
            assert stderr.read() == ''

    asyncio.run(scenario())
    events = [json.loads(line) for line in (tmp_path / 'audit.log').read_text().splitlines()]
    assert {'server.start', 'server.stop', 'tool.call', 'tool.error'} <= {event['event'] for event in events}
    assert 'PRIVATE_QUERY' not in json.dumps(events)
