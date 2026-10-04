"""Базовый рекурсивный парсер BSL: конструкции управления и выражения.

Это собственная реализация для отдельных фрагментов, не полный компилятор
платформы. Директивы препроцессора проверяются структурно без вычисления ветвей.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mcp_baf.bsl_native.lexer import Diagnostic, Token


@dataclass
class Node:
    kind: str
    token: Token
    children: list[Node] = field(default_factory=list)
    declarations: list[Token] = field(default_factory=list)
    reads: list[Token] = field(default_factory=list)


class ParseFailure(Exception):
    def __init__(self, token, message):
        self.diagnostic = Diagnostic('ParseError', message, token.line, token.column, 'error')


class Parser:
    PRECEDENCE = {'or': 1, 'and': 2, '=': 3, '<>': 3, '<': 3, '>': 3, '<=': 3, '>=': 3,
                  '+': 4, '-': 4, '*': 5, '/': 5, '%': 5}

    def __init__(self, tokens):
        # Директивы не разбираются, но ветвь препроцессора может не попасть в
        # сборку: оператор сразу после директивы не считаем недостижимым.
        self.tokens, self.after_directive, directive = [], set(), False
        for token in tokens:
            if token.kind == 'directive':
                directive = True
            elif token.kind not in {'comment', 'annotation'}:
                if directive:
                    self.after_directive.add(token.start)
                directive = False
                self.tokens.append(token)
        self.offset = 0
        self.depth = 0
        self.method = ''
        self.loops = 0
        self.diagnostics = []
        # Изменения отступа на границах конструкций для безопасного форматера.
        self.indent_events = []
        # Строки, с которых начинаются операторы: остальные — продолжения.
        self.statement_lines = set()

    @property
    def current(self):
        return self.tokens[self.offset]

    def take(self, kind=None):
        token = self.current
        if kind and token.kind != kind:
            raise ParseFailure(token, f'Ожидается {kind}; найдено {token.kind}')
        if token.kind != 'eof':
            self.offset += 1
        return token

    def accept(self, kind):
        if self.current.kind == kind:
            return self.take()
        return None

    def error(self, token, message, code='ParseError', level='error'):
        self.diagnostics.append(Diagnostic(code, message, token.line, token.column, level))

    def open_indent(self, token):
        self.indent_events.append((token.line, 1))

    def close_indent(self, token):
        self.indent_events.append((token.line, -1))

    def parse(self):
        module = self.body({'eof'}, top=True)
        self.take('eof')
        return module

    def body(self, stop, top=False):
        self.depth += 1
        if self.depth > 100:
            raise ParseFailure(self.current, 'Превышена глубина вложенности (100)')
        nodes = []
        terminated = False
        try:
            while self.current.kind not in stop:
                if self.current.kind == 'eof':
                    raise ParseFailure(self.current, 'Незакрытая конструкция BSL')
                if self.accept(';'):
                    continue
                if self.current.start in self.after_directive:
                    terminated = False
                self.statement_lines.add(self.current.line)
                node = self.statement(top)
                if terminated and node.kind != 'label':
                    self.error(node.token, 'Оператор после безусловного перехода недоступен', 'UnreachableCode', 'warning')
                if node.kind == 'label':
                    terminated = False
                elif node.kind in {'return', 'raise', 'break', 'continue', 'goto'}:
                    terminated = True
                nodes.append(node)
                if not self.accept(';') and node.kind not in {'procedure', 'function', 'label'} and self.current.kind not in stop:
                    raise ParseFailure(self.current, 'Между операторами ожидается ;')
            return nodes
        finally:
            self.depth -= 1

    def statement(self, top):
        token = self.current
        kind = token.kind
        if kind in {'async', 'procedure', 'function'}:
            if not top:
                raise ParseFailure(token, 'Объявление метода внутри блока не поддерживается')
            return self.parse_method()
        if kind == 'var':
            self.take()
            names = [self.take('identifier')]
            while self.accept(','):
                names.append(self.take('identifier'))
            self.accept('export')
            return Node('var', token, declarations=names)
        if kind == 'if':
            self.take()
            reads = self.expression().reads
            self.open_indent(self.take('then'))
            children = [Node('branch', token, self.body({'elsif','else','endif'}))]
            while self.current.kind == 'elsif':
                branch = self.take()
                self.close_indent(branch)
                reads += self.expression().reads
                self.open_indent(self.take('then'))
                children.append(Node('branch', branch, self.body({'elsif','else','endif'})))
            if self.current.kind == 'else':
                branch = self.take()
                self.close_indent(branch)
                self.open_indent(branch)
                children.append(Node('branch', branch, self.body({'endif'})))
            self.close_indent(self.take('endif'))
            return Node('if', token, children, reads=reads)
        if kind in {'while', 'for'}:
            self.take()
            if kind == 'while':
                reads = self.expression().reads
            elif self.accept('each'):
                self.take('identifier')
                self.take('in')
                reads = self.expression().reads
            else:
                self.take('identifier')
                self.take('=')
                reads = self.expression().reads
                self.take('to')
                reads += self.expression().reads
            self.open_indent(self.take('do'))
            self.loops += 1
            try:
                children = self.body({'enddo'})
            finally:
                self.loops -= 1
            self.close_indent(self.take('enddo'))
            return Node(kind, token, children, reads=reads)
        if kind == 'try':
            self.open_indent(self.take())
            children = self.body({'except'})
            exception = self.take('except')
            self.close_indent(exception)
            self.open_indent(exception)
            handler = self.body({'endtry'})
            self.close_indent(self.take('endtry'))
            if not handler:
                self.error(exception, 'Пустой обработчик исключения скрывает ошибку', 'EmptyExcept', 'warning')
            return Node('try', token, children + [Node('except', exception, handler)])
        if kind in {'return','raise','break','continue','goto','execute','addhandler','removehandler'}:
            self.take()
            reads = []
            if kind == 'return' and not self.method:
                self.error(token, 'Возврат допустим только внутри метода')
            if kind in {'break','continue'} and not self.loops:
                self.error(token, 'Оператор допустим только внутри цикла')
            if kind == 'goto':
                self.take('~')
                self.take('identifier')
            elif kind in {'addhandler','removehandler'}:
                reads = self.expression().reads
                self.take(',')
                reads += self.expression().reads
            elif kind == 'execute':
                reads = self.expression().reads
            elif kind == 'return':
                if self.current.kind not in {';','endprocedure','endfunction','endif','elsif','else','enddo','except','endtry','eof'}:
                    reads = self.expression().reads
                    if self.method != 'function':
                        self.error(token, 'Процедура не может возвращать значение')
            elif kind == 'raise' and self.current.kind not in {';','endprocedure','endfunction','endif','enddo','endtry','eof'}:
                reads = self.expression().reads
            return Node(kind, token, reads=reads)
        if kind == '~':
            self.take()
            self.take('identifier')
            self.take(':')
            return Node('label', token)
        expression = self.expression(4)  # = здесь отделяет присваивание от выражения справа.
        if self.accept('='):
            if expression.kind not in {'identifier','member','index'}:
                raise ParseFailure(token, 'Слева от присваивания ожидается переменная или поле')
            reads = [] if expression.kind == 'identifier' else expression.reads
            reads += self.expression().reads
            return Node('assignment', token, reads=reads)
        if expression.kind != 'call' and expression.token.kind != 'await':
            raise ParseFailure(token, 'Ожидается присваивание или вызов метода')
        return Node('call', token, reads=expression.reads)

    def parse_method(self):
        token = self.current
        self.accept('async')
        kind = self.take().kind
        if kind not in {'procedure','function'}:
            raise ParseFailure(token, 'После Асинх ожидается процедура или функция')
        self.take('identifier')
        self.take('(')
        parameters = []
        if self.current.kind != ')':
            while True:
                self.accept('val')
                parameters.append(self.take('identifier'))
                if self.accept('='):
                    self.expression()
                if not self.accept(','):
                    break
        header_end = self.take(')')
        if export := self.accept('export'):
            header_end = export
        self.open_indent(header_end)
        seen = set()
        for name in parameters:
            key = name.text.casefold()
            if key in seen:
                self.error(name, 'Повторное имя параметра', 'DuplicateParameter')
            seen.add(key)
        self.method = kind
        try:
            children = self.body({'end'+kind})
        finally:
            self.method = ''
        self.close_indent(self.take('end'+kind))
        return Node(kind, token, children, declarations=parameters)

    def expression(self, minimum=0):
        self.depth += 1
        if self.depth > 100:
            raise ParseFailure(self.current, 'Превышена глубина выражения (100)')
        try:
            token = self.take()
            if token.kind in {'not','+','-','await'}:
                node = Node('unary', token, reads=self.expression(6).reads)
            elif token.kind == 'new':
                if self.current.kind == '(':
                    reads = self.arguments()
                else:
                    self.take('identifier')
                    reads = self.arguments() if self.current.kind == '(' else []
                node = Node('new', token, reads=reads)
            elif token.kind == '?':
                node = Node('conditional', token, reads=self.arguments())
            elif token.kind == '(':
                node = self.expression()
                self.take(')')
                node = Node('group', token, reads=node.reads)
            elif token.kind == 'identifier':
                node = Node('identifier', token, reads=[token])
            elif token.kind in {'number','string','date','true','false','undefined','null'}:
                node = Node('literal', token)
                # Соседние строковые литералы платформа склеивает в один.
                while token.kind == 'string' and self.accept('string'):
                    pass
            else:
                raise ParseFailure(token, f'Ожидается выражение; найдено {token.kind}')
            while True:
                if self.accept('.'):
                    # Имена свойств/методов могут совпадать с ключевыми словами.
                    member = self.take()
                    if not (member.text.isidentifier()):
                        raise ParseFailure(member, 'Ожидается имя свойства или метода')
                    node = Node('member', node.token, reads=node.reads)
                elif self.current.kind == '(':
                    reads = self.arguments()
                    # Простое имя вызываемого метода не является чтением локальной переменной.
                    node = Node('call', node.token, reads=([] if node.kind == 'identifier' else node.reads) + reads)
                elif self.accept('['):
                    reads = self.expression().reads
                    self.take(']')
                    node = Node('index', node.token, reads=node.reads + reads)
                elif self.current.kind in self.PRECEDENCE and self.PRECEDENCE[self.current.kind] >= minimum:
                    operator = self.take()
                    right = self.expression(self.PRECEDENCE[operator.kind]+1)
                    node.reads.extend(right.reads)
                    node = Node('binary', operator, reads=node.reads)
                else:
                    return node
        finally:
            self.depth -= 1

    def arguments(self):
        self.take('(')
        reads = []
        while self.current.kind != ')':
            if self.current.kind == 'eof':
                raise ParseFailure(self.current, 'Незакрытый список аргументов')
            if self.current.kind != ',':
                reads += self.expression().reads
                if self.current.kind == ')':
                    break
            self.take(',')
        self.take(')')
        return reads
