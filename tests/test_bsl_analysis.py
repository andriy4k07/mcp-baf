"""Синтаксис, безопасное форматирование и приватность Python-анализатора."""

import asyncio
from pathlib import Path

import pytest
from mcp.server.mcpserver import MCPServer

from mcp_baf_audit import AuditLog
from mcp_baf.bsl_native import NativeBSLAnalyzer, analyze, format_source
from mcp_baf.bsl_native.lexer import lex
from mcp_baf.tools import bsl_analysis


def codes(src):
    return {item['code'] for item in analyze(src)}


@pytest.mark.parametrize('src', [
    'Процедура Тест(Знач Имя = "", Массив = Неопределено) Экспорт\nСообщить(Имя);\nКонецПроцедуры',
    'Function F(A) Export\nIf Not A = Undefined Then Return New Array(); Else Return ?(A > 0, A, 0); EndIf;\nEndFunction',
    'Для Каждого Элемент Из Коллекция Цикл\nЕсли Элемент = Null Тогда Продолжить; КонецЕсли;\nКонецЦикла;',
    'Для Номер = 1 По 10 Цикл Пока Истина Цикл Прервать; КонецЦикла; КонецЦикла;',
    'Попытка\nДанные.Поле[0] = Новый Структура("Имя", "Если КонецЕсли");\nИсключение\nВызватьИсключение;\nКонецПопытки;',
    'Асинх Процедура Тест()\nРезультат = Ждать ПолучитьАсинх();\nКонецПроцедуры',
    'Процедура Тест()\n~Метка:\nДата = \'20261004\';\nЕсли Истина Тогда Перейти ~Метка; КонецЕсли;\nКонецПроцедуры',
    '&НаСервере\n#Область Тест\nПроцедура Тест()\n// Если Попытка\nСообщить("Он сказал ""Да""");\nКонецПроцедуры\n#КонецОбласти',
    'Процедура Тест()\nТекст = "Если\n    |КонецЕсли";\nСообщить(Текст);\nКонецПроцедуры',
    'ДобавитьОбработчик Объект.Событие, Обработчики.Метод;\nУдалитьОбработчик Объект.Событие, Обработчики.Метод;',
    'А = Новый("Структура", "Ключ", 1); Метод(, А,);',
])
def test_supported_syntax(src):
    assert 'ParseError' not in codes(src)


@pytest.mark.parametrize('src', [
    'Если Истина Тогда\nСообщить(1);',
    'Процедура Тест()\nКонецФункции',
    'Сообщить((1);',
    'А = "нет закрытия;',
    'А = "начало\nбез продолжения";',
    "А = '2026';",
    'Прервать;',
    'Возврат 1;',
    'Процедура Тест() Возврат 1; КонецПроцедуры',
    'Попытка А = 1; КонецПопытки;',
    'А = 1 Б = 2;',
    '#Иначе\nА = 1;',
    '#Если Сервер Тогда\nА = 1;',
    '#Область Тест\n#КонецЕсли',
    '#If Server Then\n#Else\n#ElsIf Client Then\n#EndIf',
])
def test_errors_are_reported_and_format_refuses(src):
    assert 'ParseError' in codes(src)
    with pytest.raises(ValueError, match='Форматирование недоступно'):
        format_source(src)


def test_local_scopes_and_non_code_words():
    src = '''Процедура Первый(А)
Перем НеЧитается, Используется;
НеЧитается = 1;
Используется = 2;
Объект.НеЧитается = "НеЧитается";
// НеЧитается
Сообщить(Используется);
КонецПроцедуры
Процедура Второй()
Перем НеЧитается;
Сообщить(НеЧитается);
КонецПроцедуры'''
    results = analyze(src)
    assert [(d['line'], d['column']) for d in results if d['code'] == 'UnusedLocalVariable'] == [(2, 7)]


def test_duplicate_names_casefold_and_flow():
    src = '''Процедура Тест(А, а)
Перем Б, б, А;
Попытка Сообщить(А); Исключение КонецПопытки;
Возврат;
Сообщить(А);
КонецПроцедуры'''
    assert {'DuplicateParameter', 'DuplicateVariable', 'EmptyExcept', 'UnreachableCode'} <= codes(src)


@pytest.mark.parametrize('statement', [
    'Выполнить("Сообщить(А)");', 'Результат = Вычислить("А");',
    '#Если Сервер Тогда\nСообщить(1);\n#Иначе\nСообщить(2);\n#КонецЕсли',
])
def test_uncertain_dynamic_reads_do_not_report_unused(statement):
    assert 'UnusedLocalVariable' not in codes(f'Процедура Тест()\nПерем А;\n{statement}\nКонецПроцедуры')


def test_formatter_indent_tokens_literals_crlf_and_idempotence():
    src = '''Процедура Тест()
Если Истина Тогда
Текст = "Первая  
  |КонецЕсли  
  |";
  // Комментарий с пробелами  
Сообщить(Текст);  
ИначеЕсли Ложь Тогда
Попытка
Сообщить("""" );
Исключение
Сообщить(ОписаниеОшибки());
КонецПопытки;
Иначе
Сообщить(1);
КонецЕсли;
КонецПроцедуры'''.replace('\n', '\r\n')
    formatted = format_source(src)
    assert '\r\n        Текст' in formatted
    assert '\r\n    ИначеЕсли' in formatted
    assert '\r\n            Сообщить' in formatted
    assert '\r\n        // Комментарий с пробелами  \r\n' in formatted
    assert '\r\n  |КонецЕсли  \r\n  |";' in formatted
    assert '\r\n        Сообщить(Текст);\r\n' in formatted
    assert not formatted.endswith('\n')
    assert format_source(formatted) == formatted
    assert [(t.kind, t.text) for t in lex(src)[0]] == [(t.kind, t.text) for t in lex(formatted)[0]]


def test_one_line_block_does_not_outdent_following_statement():
    formatted = format_source('Процедура Тест()\nЕсли Истина Тогда Сообщить(1); КонецЕсли;\nСообщить(2);\nКонецПроцедуры\n')
    assert '\n    Сообщить(2);\n' in formatted


def test_information_diagnostics_and_limits():
    result = analyze('А = 1;  \n// ' + 'х' * 121)
    assert {d['code'] for d in result} == {'TrailingWhitespace', 'LineLength'}
    assert {d['level'] for d in result} == {'information'}
    for src in ('', ' ' * (2 * 1024 * 1024) + 'А=1;'):
        with pytest.raises(ValueError):
            analyze(src)
    assert 'ParseError' in codes('А = ' + '(' * 120 + '1' + ')' * 120 + ';')


def test_analyzer_accepts_own_extension():
    path = Path(__file__).parents[1] / 'src/mcp_baf/extension_src/HTTPServices/MCPService/Ext/Module.bsl'
    assert not [d for d in analyze(path.read_text()) if d['level'] == 'error']


def test_tools_filters_limits_privacy_and_no_source_file_changes(tmp_path):
    src = 'Процедура PRIVATE_CODE()\nПерем А, Б;\nВозврат;\nСообщить(1);\nКонецПроцедуры'
    original = tmp_path / 'Module.bsl'
    original.write_text(src)
    timestamp = original.stat().st_mtime_ns
    server = MCPServer('test')
    bsl_analysis.register(server, NativeBSLAnalyzer(), AuditLog(str(tmp_path)))
    async def scenario():
        result = (await server.call_tool('bsl_analyze', dict(src=src, levels=['warning'], diagnostic_codes=['UnusedLocalVariable'], limit=1))).content[0].text
        assert 'Показаны первые 1' in result and 'UnreachableCode' not in result
        formatted = (await server.call_tool('bsl_format', dict(src=src + '\n// ```'))).content[0].text
        assert formatted.startswith('````bsl')
    asyncio.run(scenario())
    assert 'PRIVATE_CODE' not in (tmp_path / 'audit.log').read_text()
    assert original.read_text() == src and original.stat().st_mtime_ns == timestamp
