"""Синтаксис, безопасное форматирование и приватность Python-анализатора."""

import asyncio
import json
from pathlib import Path

import pytest
from mcp.server.mcpserver import MCPServer

from mcp_baf_audit import AuditLog
from mcp_baf.bsl_native import analyze, format_source
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


# Сценарії 1c-syntax/bsl-language-server#4904 (поведінка, не код).
def test_reserved_declaration_name_reports_error_on_declaration():
    src = 'Функция Найти(Значение) Экспорт\nВозврат Значение;\nКонецФункции'
    hits = [d for d in analyze(src) if d['code'] == 'ReservedDeclarationName']
    assert [(d['line'], d['column'], d['level']) for d in hits] == [(1, 9, 'error')]
    assert codes('Function Find(Value) Export\nReturn Value;\nEndFunction') >= {'ReservedDeclarationName'}


@pytest.mark.parametrize('src', [
    # Контролі з #4904: компілятор ці імена/виклики приймає.
    'Функция ПолучитьЗначение(Значение) Экспорт\nВозврат Значение;\nКонецФункции',
    'Функция ИндексВМассиве(Массив, Значение) Экспорт\nВозврат Массив.Найти(Значение);\nКонецФункции',
    'Процедура Тест()\nСправочники.НайтиПоКоду("00000001");\nСтроки = ТаблицаЗначений.НайтиСтроки(Новый Структура("Ключ", 1));\nКонецПроцедуры',
    # Виклик за іменем не є оголошенням: діагностика чіпає лише Функция/Процедура.
    'Процедура Тест()\nРезультат = Найти(1);\nКонецПроцедуры',
    # Префікс/похідне від зарезервованого імені — звичайне ім'я.
    'Функция НайтиПоШаблону(Шаблон) Экспорт\nВозврат Шаблон;\nКонецФункции',
])
def test_reserved_declaration_name_has_no_false_positives(src):
    assert 'ReservedDeclarationName' not in codes(src)


@pytest.mark.parametrize('src', [
    # Рев'ю #54: ці імена вибито з переліку — вони НЕ методи глобального
    # контекста, тому їхні оголошення компілятор приймає (помилкового 'error'
    # бути не повинно).
    'Процедура ЗакрытьФорму()\nКонецПроцедуры',
    'Procedure CloseForm()\nEndProcedure',
    'Процедура ЗакрытьЗначение()\nКонецПроцедуры',
    'Procedure CloseValue()\nEndProcedure',
    'Функция Представление(Объект) Экспорт\nВозврат "x";\nКонецФункции',
    'Function Present(Object) Export\nReturn "x";\nEndFunction',
    # Справжній глобальний метод — СтрШаблон; ШаблонСтроки — звичайне ім'я.
    'Функция ШаблонСтроки(Шаблон) Экспорт\nВозврат Шаблон;\nКонецФункции',
    # Англійська назва глобального Вычислить — Eval, не Evaluate.
    'Function Evaluate(Code) Export\nReturn 1;\nEndFunction',
])
def test_reserved_declaration_name_allows_names_outside_global_context(src):
    assert 'ReservedDeclarationName' not in codes(src)


@pytest.mark.parametrize('src', [
    # Регресія з рев'ю #54: справжні глобальні методи та їхні англомовні
    # алиаси мають чіпатися (раніше СтрШаблон/Eval проходили повз перелік).
    'Функция СтрШаблон(Шаблон) Экспорт\nВозврат Шаблон;\nКонецФункции',
    'Function StrTemplate(Template) Export\nReturn Template;\nEndFunction',
    'Function Eval(Code) Export\nReturn 1;\nEndFunction',
    'Функция Вычислить(Выражение) Экспорт\nВозврат 1;\nКонецФункции',
    'Процедура ОткрытьФорму(ИмяФормы)\nКонецПроцедуры',
])
def test_reserved_declaration_name_flags_true_globals_and_aliases(src):
    assert 'ReservedDeclarationName' in codes(src)


@pytest.mark.parametrize('src', [
    # Гілка з хибним літеральним умовою не компілюється 1С-компілятором —
    # діагностика в ній хибнопозитивна (прецедент: придушення DuplicateVariable
    # за прапорцем `conditional`).
    '#Если Ложь Тогда\nФункция Найти()\nКонецФункции\n#КонецЕсли',
    '#If False Then\nFunction Find()\nEndFunction\n#EndIf',
    # Мертва гілка після достовірно істинної.
    '#Если Истина Тогда\nА = 1;\n#Иначе\nФункция Найти()\nКонецФункции\n#КонецЕсли',
    # Неперевірне умовою компілятора — консервативно придушаємо (гілка може не
    # потрапити в збірку).
    '#Если Сервер Тогда\nФункция Найти()\nКонецФункции\n#КонецЕсли',
])
def test_reserved_declaration_name_suppressed_in_non_compiled_branch(src):
    assert 'ReservedDeclarationName' not in codes(src)


@pytest.mark.parametrize('src', [
    # Істинне літеральне умовою: компілятор точно компілює гілку — чіпаємо.
    '#Если Истина Тогда\nФункция Найти()\nКонецФункции\n#КонецЕсли',
    '#If True Then\nFunction Find()\nEndFunction\n#EndIf',
    # Жива гілка #Иначе після хибної — теж компілюється.
    '#Если Ложь Тогда\nА = 1;\n#Иначе\nФункция Найти()\nКонецФункции\n#КонецЕсли',
])
def test_reserved_declaration_name_reported_in_compiled_branch(src):
    assert 'ReservedDeclarationName' in codes(src)


def test_reserved_declaration_name_outside_branches_even_with_dead_siblings():
    # Хибна гілка поруч не приглушає перевірку поза препроцесором.
    src = ('#Если Ложь Тогда\nБ = 1;\n#КонецЕсли\nПроцедура Тест()\nКонецПроцедуры\n'
           'Функция Найти()\nКонецФункции')
    hits = [d for d in analyze(src) if d['code'] == 'ReservedDeclarationName']
    assert [(d['line'], d['column']) for d in hits] == [(6, 9)]


# Сценарії 1c-syntax/bsl-language-server#4900 (поведінка, не код).
def test_latin_cyrillic_mixed_declaration_name_is_reported():
    src = 'Процедура ПриCоздании()\nКонецПроцедуры'  # латинская C
    hits = [d for d in analyze(src) if d['code'] == 'LatinAndCyrillicSymbolInWord']
    assert [(d['line'], d['column'], d['level']) for d in hits] == [(1, 11, 'warning')]


def test_latin_lowercase_o_homoglyph_is_reported():
    src = 'Процедура Прoдажи()\nКонецПроцедуры'  # латинская o
    hits = [d for d in analyze(src) if d['code'] == 'LatinAndCyrillicSymbolInWord']
    assert len(hits) == 1


@pytest.mark.parametrize('src', [
    # Обычные смешанные имена с аббревиатурами и латинскими словами (#54).
    'Процедура ПреобразоватьЗначениеXML()\nКонецПроцедуры',
    'Процедура ОтправитьВPDF()\nКонецПроцедуры',
    'Функция ЭтоLinuxКлиент()\nВозврат Истина;\nКонецФункции',
    'Функция ЧтениеJSONВСтруктуру()\nВозврат 1;\nКонецФункции',
    'Функция ПолучитьGETЗапрос()\nВозврат 1;\nКонецФункции',
    'Функция ВызватьHTTPМетод()\nВозврат 1;\nКонецФункции',
    'Функция КонвертироватьИзJSONВXML()\nВозврат 1;\nКонецФункции',
    'Функция ПолучитьCOMКлассы()\nВозврат 1;\nКонецФункции',
    'Процедура Подписание_ПослеВыполненияC14N_Ошибка()\nКонецПроцедуры',
    'Процедура АвтоупаковкаЗаказовWBПриИзменении(Элемент)\nКонецПроцедуры',
    # Односкриптные имена — не смешивание.
    'Процедура ОбработкаТоваров()\nКонецПроцедуры',
    'Procedure HandleGoods()\nEndProcedure',
    # Диагностика проверяет имена объявлений, а не присваивания переменных.
    'Процедура Тест()\nWBТовар = 1;\nСообщить(WBТовар);\nКонецПроцедуры',
])
def test_latin_cyrillic_has_no_false_positives(src):
    assert 'LatinAndCyrillicSymbolInWord' not in codes(src)


def test_latin_homoglyph_inside_cyrillic_word_is_reported():
    assert 'LatinAndCyrillicSymbolInWord' in codes('Функция CформироватьТекст()\nВозврат 1;\nКонецФункции')
    assert 'LatinAndCyrillicSymbolInWord' in codes('Процедура ЗагрузитьCУчетом()\nКонецПроцедуры')


def test_unconfirmed_reserved_name_is_warning_confirmed_is_error():
    level = lambda src: [d['level'] for d in analyze(src) if d['code'] == 'ReservedDeclarationName']
    assert level('Функция Найти()\nКонецФункции') == ['error']
    assert level('Функция СтрШаблон()\nКонецФункции') == ['warning']


# Текущее поведение: Не/NOT-условия не вычисляются — ветка считается невычислимой
# и подавляет ReservedDeclarationName (консервативно, как #Если Сервер).
@pytest.mark.parametrize('cond', ['Не Ложь', 'НЕ Истина', 'Not False'])
def test_negated_literal_preprocessor_condition_is_treated_as_unknown(cond):
    src = f'#Если {cond} Тогда\nФункция Найти()\nКонецФункции\n#КонецЕсли'
    assert 'ReservedDeclarationName' not in codes(src)


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
    bsl_analysis.register(server, AuditLog(str(tmp_path)))
    async def scenario():
        result = (await server.call_tool('bsl_analyze', dict(src=src, levels=['warning'], diagnostic_codes=['UnusedLocalVariable'], limit=1))).content[0].text
        assert 'Показаны первые 1' in result and 'UnreachableCode' not in result
        formatted = (await server.call_tool('bsl_format', dict(src=src + '\n// ```'))).content[0].text
        assert formatted.startswith('````bsl')
    asyncio.run(scenario())
    assert 'PRIVATE_CODE' not in (tmp_path / 'audit.log').read_text()
    assert original.read_text() == src and original.stat().st_mtime_ns == timestamp


def test_audit_has_char_count_not_code_and_stays_small(tmp_path):
    # Аудит несёт только длину в символах: src не кодируется в байтовый буфер
    # ради подсчёта и сам код в журнал не попадает.
    src = 'Процедура PRIVATE_CODE()\nПерем А, Б;\nВозврат;\nКонецПроцедуры'
    server = MCPServer('test')
    bsl_analysis.register(server, AuditLog(str(tmp_path)))

    async def scenario():
        await server.call_tool('bsl_analyze', dict(src=src))
        await server.call_tool('bsl_format', dict(src=src))

    asyncio.run(scenario())
    events = [json.loads(line) for line in (tmp_path / 'audit.log').read_text('utf-8').splitlines()]
    calls = [e for e in events if e['event'] == 'tool.call']
    assert {e['tool'] for e in calls} == {'bsl_analyze', 'bsl_format'}
    for event in calls:
        assert event['args']['src_chars'] == len(src)
        assert 'src' not in event['args'] and 'src_bytes' not in event['args']
        assert 'PRIVATE_CODE' not in json.dumps(event, ensure_ascii=False)
        assert len(json.dumps(event, ensure_ascii=False)) < 1024


@pytest.mark.parametrize('src', [
    '﻿#Область Х\nПроцедура А()\nКонецПроцедуры\n#КонецОбласти\n',
    '﻿&НаСервере\nПроцедура А()\nКонецПроцедуры\n',
    'Процедура А()\nТ = "a"\n"b";\nСообщить(НСтр("ru=\'%1\'"\n"en=\'%1\'"));\nКонецПроцедуры',
    "Процедура А()\nД = '0001-01-01';\nД = '2026.10.04 10:00:00';\nКонецПроцедуры",
    'Процедура А()\nТ = "ВЫБРАТЬ\n\n// пояснение\n|1";\nКонецПроцедуры',
    'Асинх Процедура А()\nЖдать Б();\nКонецПроцедуры',
    'Процедура А()\n' + '// c\n' * 120_000 + 'КонецПроцедуры',
], ids=['bom-region', 'bom-annotation', 'adjacent-strings', 'dates', 'string-gap', 'await', 'many-comments'])
def test_real_module_syntax_is_accepted_and_formatted(src):
    # Конструкции из выгрузок типовых конфигураций, дававшие ложный ParseError.
    assert 'ParseError' not in codes(src)
    assert format_source(format_source(src)) == format_source(src)


def test_preprocessor_branch_does_not_make_code_unreachable():
    src = 'Процедура А()\n#Если Сервер Тогда\nВозврат;\n#КонецЕсли\nБ = 1;\nКонецПроцедуры'
    assert 'UnreachableCode' not in codes(src)
    assert 'UnreachableCode' in codes('Процедура А()\nВозврат;\nБ = 1;\nКонецПроцедуры')


def test_format_keeps_working_on_duplicates_and_odd_line_breaks():
    # Дубли имён — не синтаксис; \f и \x85 не являются переводом строки BSL.
    assert format_source('Процедура А(Б, Б)\nВ = 1;\nКонецПроцедуры') == 'Процедура А(Б, Б)\n    В = 1;\nКонецПроцедуры'
    src = 'Процедура А()\n// a\x0cb\x85c\nЕсли Б Тогда\nВ = 1;\nКонецЕсли;\nКонецПроцедуры\n'
    assert format_source(src) == 'Процедура А()\n    // a\x0cb\x85c\n    Если Б Тогда\n        В = 1;\n    КонецЕсли;\nКонецПроцедуры\n'


def test_format_indents_statement_continuations():
    src = 'Процедура А()\nЕсли Б И\nВ Тогда\nВызов(Г,\nД);\nКонецЕсли;\nКонецПроцедуры'
    assert format_source(src) == (
        'Процедура А()\n    Если Б И\n        В Тогда\n        Вызов(Г,\n            Д);\n    КонецЕсли;\nКонецПроцедуры'
    )


def test_lexer_hash_not_at_line_start_is_linear():
    """#65: `#`/`&` не в начале строки не должны давать квадратичный разбор."""
    import time

    from mcp_baf.bsl_native.lexer import lex

    start = time.monotonic()
    tokens, _ = lex("x" + "#" * 200_000)
    assert time.monotonic() - start < 2
    assert len(tokens) == 200_002


@pytest.mark.parametrize('raise_word,if_,then,elsif,else_,endif', [
    ('ВызватьИсключение', 'Если', 'Тогда', 'ИначеЕсли', 'Иначе', 'КонецЕсли'),
    ('Raise', 'If', 'Then', 'ElsIf', 'Else', 'EndIf'),
])
def test_bare_raise_before_block_terminators(raise_word, if_, then, elsif, else_, endif):
    for follower in (else_, f'{elsif} Б {then}\nВ();\n{else_}', ):
        src = f'Процедура П()\n{if_} А {then}\n{raise_word}\n{follower}\nБ();\n{endif};\nКонецПроцедуры'
        assert 'ParseError' not in codes(src), src
        assert format_source(format_source(src)) == format_source(src)


def test_bare_raise_before_except_and_end_of_method():
    for src in ('Попытка\nВызватьИсключение\nИсключение\nКонецПопытки;', 'Try\nRaise\nExcept\nСообщить(1);\nEndTry;',
                'Процедура П()\nВызватьИсключение\nКонецПроцедуры', 'Function F()\nRaise\nEndFunction'):
        assert 'ParseError' not in codes(src), src


@pytest.mark.parametrize('src', [
    'Перем А;\nЕсли А Тогда\n Возврат;\nКонецЕсли;',
    'Var A;\nIf A Then\n Return;\nEndIf;',
    'Процедура П()\nКонецПроцедуры\nВозврат;',
])
def test_module_level_return_without_value_is_accepted(src):
    assert not {'ParseError', 'UnreachableCode'} & set(codes(src))
    assert format_source(format_source(src)) == format_source(src)


def test_module_level_return_with_value_is_still_an_error():
    assert 'ParseError' in codes('Возврат 1;')


@pytest.mark.parametrize('src', [
    '#Если Сервер Тогда\nПроцедура П(А)\n#Иначе\nПроцедура П(А, Б)\n#КонецЕсли\nСообщить(А);\nКонецПроцедуры',
    '#If Server Then\nFunction F(A) Export\n#ElsIf Client Then\nFunction F(A, B) Export\n#Else\nAsync Function F()\n#EndIf\nReturn A;\nEndFunction',
])
def test_method_headers_duplicated_across_preprocessor_branches(src):
    assert 'ParseError' not in codes(src)
    formatted = format_source(src)
    assert format_source(formatted) == formatted
    assert [(t.kind, t.text) for t in lex(src)[0]] == [(t.kind, t.text) for t in lex(formatted)[0]]


def test_nested_method_without_directive_is_still_an_error():
    assert 'ParseError' in codes('Процедура А()\nПроцедура Б()\nКонецПроцедуры\nКонецПроцедуры')


def test_alternative_header_keeps_reserved_name_suppression_and_parameter_check():
    src = '#Если Сервер Тогда\nПроцедура Найти()\n#Иначе\nПроцедура Другая(А, а)\n#КонецЕсли\nКонецПроцедуры'
    assert 'ReservedDeclarationName' not in codes(src)
    assert 'DuplicateParameter' in codes(src)


def test_nbsp_and_form_feed_are_whitespace_and_preserved():
    src = 'Процедура П()\n\xa0\xa0Сообщить(1);\xa0\n\fСообщить(2);\n\xa0#Если Истина Тогда\nА = 1;\n#КонецЕсли\nКонецПроцедуры'
    assert 'ParseError' not in codes(src)
    formatted = format_source(src)
    assert formatted.count('\xa0') == src.count('\xa0') and formatted.count('\f') == 1
    assert format_source(formatted) == formatted
    assert 'ParseError' in codes('А = 1 ​;')
