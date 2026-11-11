"""Собственные базовые проверки и консервативный форматер BSL на Python.

Никаких внешних процессов, чтения исходников с диска или записи кода.
Проверки фрагмента не заменяют компилятор платформы и полный language server.
"""

from __future__ import annotations

import re

from mcp_baf.bsl_native.lexer import Diagnostic, lex
from mcp_baf.bsl_native.parser import ParseFailure, Parser

MAX_SOURCE_BYTES = 2 * 1024 * 1024
DIAGNOSTIC_CODES = frozenset({
    'ParseError', 'DuplicateParameter', 'DuplicateVariable',
    'UnusedLocalVariable', 'UnreachableCode', 'EmptyExcept',
    'TrailingWhitespace', 'LineLength',
    'ReservedDeclarationName', 'LatinAndCyrillicSymbolInWord',
})

# Курований перелік імен, які лексер BSL приймає як ідентифікатор, але компілятор
# 1С 8.3.27 відхиляє в оголошенні Функция/Процедура («Ожидается имя функции»):
# лише імена, задокументовані як методи глобального контекста цільової версії
# платформи. Правило з опису 1c-syntax/bsl-language-server#4904 (поведінка, не
# код — LGPL): не чіпати всі підряд збіги з іменами вбудованих методів без
# перевірки правил компілятора — у переліку (рівень 'error') залишаються тільки
# імена, достовірно підтверджені компілятором/документацією платформи; все
# інше з переліку вибивається. Тому тут немає ЗакрытьФорму (форма закривається
# через Форма.Закрыть(), ім'я легітимне для власного коду), ЗакрытьЗначение,
# голого Представления (метод об'єкта метаданих, не глобальний), ШаблонСтроки
# (справжній глобальний метод — СтрШаблон/StrTemplate) і Evaluate (англійська
# назва глобального Вычислить — Eval).
RESERVED_DECLARATION_NAMES = frozenset({
    name.casefold() for name in (
        'Найти', 'Find', 'Вычислить', 'Eval',
        'СтрШаблон', 'StrTemplate',
        'ЗагрузитьЗначение', 'LoadValue', 'СохранитьЗначение', 'SaveValue',
        'ПоместитьВоВременноеХранилище', 'PutToTempStorage',
        'ПолучитьИзВременногоХранилища', 'GetFromTempStorage',
        'УдалитьИзВременногоХранилища', 'DeleteFromTempStorage',
        'ОткрытьФорму', 'OpenForm', 'ОткрытьЗначение', 'OpenValue',
        'Формат', 'Format',
        'Абс', 'Abs', 'Эксп', 'Exp', 'Лог', 'Log', 'Лог10', 'Log10',
        'Квадрат', 'Sqr', 'Корень', 'Sqrt', 'Степень', 'Pow',
        'Син', 'Sin', 'Кос', 'Cos', 'Тан', 'Tan',
    )
})

# Подтверждено компилятором (#54: «Ожидается имя функции») — уровень error.
# Остальные имена выше не проверены на платформе — уровень warning; их нужно
# подтвердить на живой платформе, прежде чем повышать до error.
CONFIRMED_RESERVED_NAMES = frozenset({'найти', 'find'})

# Аналог LatinAndCyrillicSymbolInWord з 1c-syntax/bsl-language-server#4900
# (поведінка, не код — LGPL). Звичайні змішані імена (ОтправитьВPDF, ЭтоLinuxКлиент)
# не є помилкою: ловимо лише омогліфи — послідовність літер одного алфавіту, що
# ПОВНІСТЮ складається з літер, візуально ідентичних літерам іншого алфавіту, і
# впритул межує з послідовністю іншого алфавіту (ПриCоздании з латинською C).
_LATIN_LOOKALIKES = frozenset('ABCEHKMOPTXacepxyiI')
_CYRILLIC_LOOKALIKES = frozenset('АВСЕНКМОРТХасеорхуіІ')
_SCRIPT_RUN = re.compile(r'[A-Za-z]+|[\u0400-\u04FF]+')


def _is_mixed_script(name):
    runs = list(_SCRIPT_RUN.finditer(name))
    for i, run in enumerate(runs):
        text = run.group()
        latin = text[0] < '\u0400'
        if not set(text) <= (_LATIN_LOOKALIKES if latin else _CYRILLIC_LOOKALIKES):
            continue
        # Аббревиатуры (COM, HTTP, C14N) целиком из омоглифов — не ошибка.
        if (len(text) > 1 and text.isupper()) or name[run.end():run.end() + 1].isdigit() \
                or name[max(run.start() - 1, 0):run.start()].isdigit():
            continue
        # Соседняя последовательность другого алфавита должна примыкать вплотную.
        # Предлог В между аббревиатурами (XMLВXDTO) — не омоглиф.
        near = [other.group() for other in runs[max(i - 1, 0):i + 2]
                if other is not run and (other.end() == run.start() or other.start() == run.end())]
        if near and not (not latin and any(len(w) > 1 and w.isupper() for w in near)):
            return True
    return False


def _directives(tokens):
    """Проверяет пары директив, не пытаясь вычислять условия препроцессора."""
    diagnostics, stack = [], []
    names = {
        'если': 'if', 'if': 'if', 'иначеесли': 'elsif', 'elsif': 'elsif',
        'иначе': 'else', 'else': 'else', 'конецесли': 'endif', 'endif': 'endif',
        'область': 'region', 'region': 'region',
        'конецобласти': 'endregion', 'endregion': 'endregion',
    }
    for token in tokens:
        if token.kind != 'directive':
            continue
        word = re.match(r'#\s*(\w+)', token.text)
        kind = names.get(word[1].casefold()) if word else None
        if kind in {'if', 'region'}:
            stack.append([kind, token, False])
        elif kind in {'else', 'elsif'}:
            if not stack or stack[-1][0] != 'if' or stack[-1][2]:
                diagnostics.append(Diagnostic('ParseError', 'Директива ветви без соответствующего #Если', token.line, token.column, 'error'))
            elif kind == 'else':
                stack[-1][2] = True
        elif kind in {'endif', 'endregion'}:
            expected = 'if' if kind == 'endif' else 'region'
            if not stack or stack[-1][0] != expected:
                diagnostics.append(Diagnostic('ParseError', 'Несогласованная закрывающая директива', token.line, token.column, 'error'))
            else:
                stack.pop()
    for _, token, _ in stack:
        diagnostics.append(Diagnostic('ParseError', 'Незакрытая директива препроцессора', token.line, token.column, 'error'))
    return diagnostics


# Метод _semantic уже покладається на обчислений прапорець `conditional`
# (див. придушення DuplicateVariable): код у гілкових директивах може не
# компілюватися. Те саме правило застосовуємо до ReservedDeclarationName, але
# точніше — за рядками: компілятор 1С гарантовано не компілює гілки з хибним
# літеральним умовою, а непередбачувані умови (Сервер, Клиент...) можуть
# виключити код із збірки. Тож оголошення в таких рядках не чіпаємо, тоді як
# гілки з істинним літеральним умовою лишаються під перевіркою.
PREPROCESSOR_TRUE_WORDS = frozenset({'истина', 'true'})
PREPROCESSOR_FALSE_WORDS = frozenset({'ложь', 'false'})


def _branch_state(condition_text):
    condition = condition_text.strip().rstrip('.').casefold()
    condition = re.sub(r'\s+(?:тогда|then)$', '', condition).strip()
    if condition in PREPROCESSOR_TRUE_WORDS:
        return 'active'
    if condition in PREPROCESSOR_FALSE_WORDS:
        return 'dead'
    return 'unknown'


def _preprocessor_dead_lines(tokens):
    """Рядки, які компілятор не компілює достовірно або ймовірно (dead/unknown)."""
    dead_lines, stack = set(), []
    for token in tokens:
        if token.kind == 'eof':
            continue
        if token.kind != 'directive':
            if any(block['state'] != 'active' for block in stack):
                dead_lines.add(token.line)
            continue
        match = re.match(r'#\s*(\w+)(.*)', token.text, re.I)
        if not match:
            continue
        word = match[1].casefold()
        if word in {'если', 'if'}:
            state = _branch_state(match[2])
            stack.append({'state': state, 'states': [state]})
        elif word in {'иначеесли', 'elsif'} and stack:
            # Перша достовірно істинна гілка робить наступні мертвими.
            state = 'dead' if 'active' in stack[-1]['states'] else _branch_state(match[2])
            stack[-1]['states'].append(state)
            stack[-1]['state'] = state
        elif word in {'иначе', 'else'} and stack:
            if 'active' in stack[-1]['states']:
                state = 'dead'
            elif 'unknown' in stack[-1]['states']:
                state = 'unknown'
            else:
                state = 'active'
            stack[-1]['states'].append(state)
            stack[-1]['state'] = state
        elif word in {'конецесли', 'endif'} and stack:
            stack.pop()
    return dead_lines


def _walk(nodes):
    for node in nodes:
        yield node
        yield from _walk(node.children)


def _semantic(nodes, conditional, dynamic_eval, dead_lines):
    diagnostics = []
    for method in (node for node in nodes if node.kind in {'procedure', 'function'}):
        # Виклики на кшталт Массив.Найти() — вузли member/call, сюди не доходять:
        # перевіряється лише іменник оголошення, а не будь-який токен імені.
        # Гілки препроцесора, які компілятор не компілює, придушаються за
        # рядками (той самий підхід, що й `conditional` нижче).
        if (method.name is not None and method.name.text.casefold() in RESERVED_DECLARATION_NAMES
                and method.name.line not in dead_lines):
            diagnostics.append(Diagnostic(
                'ReservedDeclarationName',
                'Имя объявления зарезервировано встроенным методом платформы и будет отклонено компилятором',
                method.name.line, method.name.column,
                'error' if method.name.text.casefold() in CONFIRMED_RESERVED_NAMES else 'warning'))
        if method.name is not None and _is_mixed_script(method.name.text):
            diagnostics.append(Diagnostic(
                'LatinAndCyrillicSymbolInWord',
                'Омоглиф: латинская и кириллическая буквы одинакового вида в одном слове',
                method.name.line, method.name.column))
        seen = {name.text.casefold() for name in method.declarations}
        local_names = []
        body = list(_walk(method.children))
        reads = {name.text.casefold() for node in body for name in node.reads}
        # Динамический код и невычисленные ветви делают анализ чтения ненадёжным.
        dynamic = conditional or dynamic_eval or any(node.kind == 'execute' for node in body)
        for node in body:
            for name in node.declarations:
                key = name.text.casefold()
                if key in seen and not conditional:
                    diagnostics.append(Diagnostic('DuplicateVariable', 'Повторное объявление локальной переменной', name.line, name.column, 'error'))
                seen.add(key)
                local_names.append(name)
        if not dynamic:
            for name in local_names:
                if name.text.casefold() not in reads:
                    diagnostics.append(Diagnostic('UnusedLocalVariable', 'Объявленная локальная переменная не читается', name.line, name.column))
    return diagnostics


def _inspect(source):
    if not source.strip():
        raise ValueError('src должен содержать текст BSL, а не пустую строку')
    if len(source.encode('utf-8')) > MAX_SOURCE_BYTES:
        raise ValueError('src превышает лимит 2 MiB')
    tokens, diagnostics = lex(source)
    diagnostics.extend(_directives(tokens))
    parser = Parser(tokens)
    if not any(d.level == 'error' for d in diagnostics):
        try:
            nodes = parser.parse()
        except ParseFailure as exc:
            diagnostics.append(exc.diagnostic)
        except RecursionError:
            token = parser.current
            diagnostics.append(Diagnostic('ParseError', 'Превышена допустимая вложенность BSL', token.line, token.column, 'error'))
        else:
            conditional = any(t.kind == 'directive' and re.match(r'#\s*(если|if)\b', t.text, re.I) for t in tokens)
            dynamic_eval = any(t.kind == 'identifier' and t.text.casefold() in {'вычислить', 'eval'} for t in tokens)
            diagnostics.extend(_semantic(nodes, conditional, dynamic_eval, _preprocessor_dead_lines(tokens)))
        diagnostics.extend(parser.diagnostics)
    # Строковые литералы, включая продолжения, должны сохраняться побайтно.
    protected = set()
    for token in tokens:
        if token.kind == 'string':
            protected.update(range(token.line, token.line + token.text.count('\n') + 1))
    # Строки считаем как лексер — только по LF; splitlines режет ещё и по \f, \x85.
    for number, line in enumerate(source.split('\n'), 1):
        line = line.removesuffix('\r')
        if number not in protected and line.rstrip(' \t') != line:
            diagnostics.append(Diagnostic('TrailingWhitespace', 'Пробелы в конце строки', number, len(line.rstrip(' \t')) + 1, 'information'))
        if len(line) > 120:
            diagnostics.append(Diagnostic('LineLength', 'Длина строки превышает 120 символов', number, 121, 'information'))
    diagnostics.sort(key=lambda d: (d.line, d.column, d.code))
    return tokens, parser, diagnostics


def analyze(source: str) -> list[dict]:
    return [diagnostic.as_dict() for diagnostic in _inspect(source)[2]]


def format_source(source: str) -> str:
    tokens, parser, diagnostics = _inspect(source)
    # Отказываем только при ошибках синтаксиса: дубли имён отступам не мешают.
    if errors := [d for d in diagnostics if d.code == 'ParseError']:
        first = errors[0]
        raise ValueError(f'Форматирование недоступно: {first.code} в {first.line}:{first.column}. Проверьте синтаксис и поддерживаемые конструкции')
    # Форматируем только отступы/концевые пробелы. Не меняем регистр,
    # расстояния между токенами, комментарии и содержимое литералов.
    preserved_lines, continuation_lines = set(), set()
    first_tokens = {}
    for token in tokens:
        if token.kind == 'eof':
            continue
        first_tokens.setdefault(token.line, token)
        if token.kind == 'string' and '\n' in token.text:
            continuation_lines.update(range(token.line + 1, token.line + token.text.count('\n') + 1))
            preserved_lines.update(range(token.line, token.line + token.text.count('\n') + 1))
        if token.kind in {'comment', 'directive', 'annotation'}:
            preserved_lines.add(token.line)
    events = {}
    for line, change in parser.indent_events:
        events[line] = events.get(line, 0) + change
    closers = {'endprocedure', 'endfunction', 'endif', 'elsif', 'else', 'enddo', 'except', 'endtry'}
    result, depth = [], 0
    for number, raw in enumerate(re.findall(r'[^\n]*\n|[^\n]+', source), 1):
        # Сохраняем исходный стиль LF/CRLF и отсутствие финального LF.
        ending = '\r\n' if raw.endswith('\r\n') else '\n' if raw.endswith('\n') else ''
        line = raw[:-len(ending)] if ending else raw
        first = first_tokens.get(number)
        indent = max(0, depth - (1 if first and first.kind in closers else 0))
        # Продолжение многострочного оператора — на уровень глубже его начала.
        if first and first.kind not in closers | {'comment', 'directive', 'annotation'} and number not in parser.statement_lines:
            indent = depth + 1
        if number not in continuation_lines:
            line = line.lstrip(' \t')
            if number not in preserved_lines:
                line = line.rstrip(' \t')
            if line:
                line = '    ' * indent + line
        result.append(line + ending)
        depth = max(0, depth + events.get(number, 0))
    formatted = ''.join(result)
    updated, errors = lex(formatted)
    signature = lambda values: [(t.kind, t.text) for t in values if t.kind != 'eof']
    if errors or signature(updated) != signature(tokens):
        raise RuntimeError('Форматер не смог сохранить токены исходного текста')
    return formatted

