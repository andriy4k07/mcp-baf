"""Собственный лексер BSL: двуязычные ключевые слова, строки и комментарии."""

from __future__ import annotations

from dataclasses import dataclass
import re


KEYWORDS = {}
for english, russian in (
    ('procedure', 'процедура'), ('function', 'функция'),
    ('endprocedure', 'конецпроцедуры'), ('endfunction', 'конецфункции'),
    ('var', 'перем'), ('val', 'знач'), ('export', 'экспорт'),
    ('if', 'если'), ('then', 'тогда'), ('elsif', 'иначеесли'),
    ('else', 'иначе'), ('endif', 'конецесли'), ('for', 'для'),
    ('each', 'каждого'), ('in', 'из'), ('to', 'по'), ('do', 'цикл'),
    ('enddo', 'конеццикла'), ('while', 'пока'), ('try', 'попытка'),
    ('except', 'исключение'), ('endtry', 'конецпопытки'),
    ('return', 'возврат'), ('break', 'прервать'), ('continue', 'продолжить'),
    ('raise', 'вызватьисключение'), ('execute', 'выполнить'), ('goto', 'перейти'),
    ('new', 'новый'), ('not', 'не'), ('and', 'и'), ('or', 'или'),
    ('true', 'истина'), ('false', 'ложь'), ('undefined', 'неопределено'),
    ('null', 'null'), ('async', 'асинх'), ('await', 'ждать'),
    ('addhandler', 'добавитьобработчик'), ('removehandler', 'удалитьобработчик'),
):
    KEYWORDS[english] = english
    KEYWORDS[russian] = english

IDENTIFIER = re.compile(r'[^\W\d]\w*', re.UNICODE)
NUMBER = re.compile(r'\d+(?:\.\d+)?')


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    start: int
    end: int
    line: int
    column: int


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    line: int
    column: int
    level: str = 'warning'

    def as_dict(self):
        return vars(self)


def lex(source: str) -> tuple[list[Token], list[Diagnostic]]:
    tokens = []
    diagnostics = []
    offset, line, column = 0, 1, 1
    while offset < len(source):
        start, token_line, token_column = offset, line, column
        char = source[offset]
        if char in ' \t\r\n\ufeff':
            end = offset + 1
            kind = None
        elif source.startswith('//', offset):
            end = source.find('\n', offset)
            end = len(source) if end < 0 else end
            kind = 'comment'
        elif char in '#&' and not source[source.rfind('\n', 0, offset) + 1:offset].strip(' \t\r\ufeff'):
            end = source.find('\n', offset)
            end = len(source) if end < 0 else end
            kind = 'directive' if char == '#' else 'annotation'
        elif char == '"':
            end = offset + 1
            closed = False
            while end < len(source):
                if source[end] == '"':
                    if source.startswith('""', end):
                        end += 2
                        continue
                    end += 1
                    closed = True
                    break
                if source[end] == '\n':
                    # Продолжение строки BSL начинается с | после отступа; между
                    # продолжениями платформа допускает пустые строки и комментарии.
                    next_line = end + 1
                    while True:
                        while next_line < len(source) and source[next_line] in ' \t\r':
                            next_line += 1
                        if next_line < len(source) and (source[next_line] == '\n' or source.startswith('//', next_line)):
                            next_line = source.find('\n', next_line) + 1 or len(source)
                            continue
                        break
                    if next_line >= len(source) or source[next_line] != '|':
                        break
                    end = next_line
                end += 1
            kind = 'string'
            if not closed:
                diagnostics.append(Diagnostic('ParseError', 'Незакрытая строка или отсутствует | продолжения', line, column, 'error'))
        elif char == "'":
            end = source.find("'", offset + 1)
            newline = source.find('\n', offset + 1)
            if end < 0 or (newline >= 0 and newline < end):
                end = newline if newline >= 0 else len(source)
                diagnostics.append(Diagnostic('ParseError', 'Незакрытый литерал даты', line, column, 'error'))
            else:
                end += 1
                if len(re.sub(r'\D', '', source[start:end])) not in {8, 12, 14}:
                    diagnostics.append(Diagnostic('ParseError', 'Литерал даты должен содержать 8, 12 или 14 цифр', line, column, 'error'))
            kind = 'date'
        elif match := IDENTIFIER.match(source, offset):
            end = match.end()
            kind = KEYWORDS.get(match.group().casefold(), 'identifier')
        elif match := NUMBER.match(source, offset):
            end = match.end()
            kind = 'number'
        elif source[offset:offset + 2] in {'<>', '<=', '>='}:
            end, kind = offset + 2, source[offset:offset + 2]
        elif char in '()+-*/%=<>[],.;?:~':
            end, kind = offset + 1, char
        else:
            end, kind = offset + 1, 'invalid'
            diagnostics.append(Diagnostic('ParseError', 'Неподдерживаемый символ BSL', line, column, 'error'))
        text = source[start:end]
        if kind:
            tokens.append(Token(kind, text, start, end, token_line, token_column))
        newline_count = text.count('\n')
        if newline_count:
            line += newline_count
            column = len(text.rsplit('\n', 1)[-1]) + 1
        else:
            column += len(text)
        offset = end
    tokens.append(Token('eof', '', len(source), len(source), line, column))
    return tokens, diagnostics
