"""Собственные базовые проверки и консервативный форматер BSL на Python.

Никаких внешних процессов, чтения исходников с диска или записи кода.
Проверки фрагмента не заменяют компилятор платформы и полный language server.
"""

from __future__ import annotations

import asyncio
import re

from mcp_baf.bsl_native.lexer import Diagnostic, lex
from mcp_baf.bsl_native.parser import ParseFailure, Parser

MAX_SOURCE_BYTES = 2 * 1024 * 1024
DIAGNOSTIC_CODES = frozenset({
    'ParseError', 'DuplicateParameter', 'DuplicateVariable',
    'UnusedLocalVariable', 'UnreachableCode', 'EmptyExcept',
    'TrailingWhitespace', 'LineLength',
})


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


def _walk(nodes):
    for node in nodes:
        yield node
        yield from _walk(node.children)


def _semantic(nodes, conditional, dynamic_eval):
    diagnostics = []
    for method in (node for node in nodes if node.kind in {'procedure', 'function'}):
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
            diagnostics.extend(_semantic(nodes, conditional, dynamic_eval))
        diagnostics.extend(parser.diagnostics)
    # Строковые литералы, включая продолжения, должны сохраняться побайтно.
    protected = set()
    for token in tokens:
        if token.kind == 'string':
            protected.update(range(token.line, token.line + token.text.count('\n') + 1))
    for number, line in enumerate(source.splitlines(), 1):
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
    if errors := [d for d in diagnostics if d.level == 'error']:
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
    for number, raw in enumerate(source.splitlines(keepends=True), 1):
        # splitlines оставляет исходный стиль LF/CRLF и отсутствие финального LF.
        match = re.search(r'(\r?\n|\r)$', raw)
        ending = match[0] if match else ''
        line = raw[:-len(ending)] if ending else raw
        first = first_tokens.get(number)
        indent = max(0, depth - (1 if first and first.kind in closers else 0))
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


class NativeBSLAnalyzer:
    async def execute(self, src: str, formatting: bool = False):
        return await asyncio.to_thread(format_source if formatting else analyze, src)
