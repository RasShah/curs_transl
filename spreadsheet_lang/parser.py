"""Recursive descent parser matching grammar/table.g."""
from .diagnostics import Source, fail
from .lexer import CELL, Lexer
from .limits import MAX_EXPR_DEPTH
from .nodes import (Assignment, Binary, Call, Export, Fill, Literal, Program,
                    Range, Reference, Unary)

COMPARISONS = ("==", "!=", "<", "<=", ">", ">=")


class Parser:
    def __init__(self, source: Source):
        self.source = source
        self.tokens = Lexer(source).tokens()
        self.index = 0
        self.nesting = 0
        self.depths = {}

    @property
    def current(self):
        return self.tokens[self.index]

    def error(self, token, message, code="E_SYNTAX"):
        fail(self.source, token.pos, "синтаксическая ошибка", code, message)

    def accept(self, kind):
        if self.current.kind == kind:
            token = self.current
            self.index += 1
            return token
        return None

    def expect(self, kind, label=None):
        token = self.accept(kind)
        if token is None:
            found = "конец файла" if self.current.kind == "EOF" else repr(self.current.value)
            self.error(self.current, f"Ожидалось {label or repr(kind)}, получено {found}.")
        return token

    def node(self, node, *operands):
        depth = 1 + max((self.depths[id(x)] for x in operands), default=0)
        if depth > MAX_EXPR_DEPTH:
            fail(self.source, node.pos, "синтаксическая ошибка", "E_LIMIT",
                 f"Глубина выражения превышает {MAX_EXPR_DEPTH} уровней.")
        self.depths[id(node)] = depth
        return node

    def reference(self):
        token = self.expect("CELL", "адрес ячейки")
        match = CELL.fullmatch(token.value)
        a_col, letters, a_row, row = match.groups()
        # Reject absurd coordinates without converting an unbounded integer.
        if len(letters) > 4 or len(row) > 6:
            self.error(token, "Адрес ячейки выходит за допустимые границы таблицы.", "E_ADDRESS")
        column = 0
        for letter in letters:
            column = column * 26 + ord(letter) - 64
        return self.node(Reference(column, int(row), bool(a_col), bool(a_row), token.pos))

    def range(self):
        start = self.reference()
        self.expect(":")
        end = self.reference()
        return self.node(Range(start, end, start.pos))

    def parse(self):
        statements = []
        while self.current.kind != "EOF":
            token = self.current
            if self.accept("FILL"):
                target = self.range()
                self.expect("=")
                expression = self.expression()
                statements.append(Fill(target, expression, token.pos))
            elif self.accept("EXPORT"):
                path = self.expect("STRING", "строка с именем CSV-файла")
                statements.append(Export(path.value, path.pos))
            else:
                target = self.reference()
                self.expect("=")
                expression = self.expression()
                statements.append(Assignment(target, expression, target.pos))
            self.expect(";", "точка с запятой ';' после команды")
        return Program(tuple(statements))

    def expression(self):
        self.nesting += 1
        if self.nesting > MAX_EXPR_DEPTH:
            self.error(self.current, f"Вложенность выражения превышает {MAX_EXPR_DEPTH} уровней.", "E_LIMIT")
        try:
            return self.comparison()
        finally:
            self.nesting -= 1

    def comparison(self):
        left = self.additive()
        if self.current.kind in COMPARISONS:
            token = self.current
            self.index += 1
            right = self.additive()
            left = self.node(Binary(token.kind, left, right, token.pos), left, right)
            if self.current.kind in COMPARISONS:
                self.error(self.current, "Цепочки сравнений не поддерживаются; используйте вложенный IF.")
        return left

    def additive(self):
        left = self.multiplicative()
        while self.current.kind in ("+", "-"):
            token = self.current
            self.index += 1
            right = self.multiplicative()
            left = self.node(Binary(token.kind, left, right, token.pos), left, right)
        return left

    def multiplicative(self):
        left = self.unary()
        while self.current.kind in ("*", "/", "%"):
            token = self.current
            self.index += 1
            right = self.unary()
            left = self.node(Binary(token.kind, left, right, token.pos), left, right)
        return left

    def unary(self):
        signs = []
        while self.current.kind in ("+", "-"):
            signs.append(self.current)
            self.index += 1
            if len(signs) > MAX_EXPR_DEPTH:
                self.error(signs[-1], "Слишком много вложенных унарных знаков.", "E_LIMIT")
        operand = self.primary()
        for token in reversed(signs):
            operand = self.node(Unary(token.kind, operand, token.pos), operand)
        return operand

    def primary(self):
        token = self.current
        if token.kind in ("NUMBER", "STRING", "TRUE", "FALSE"):
            self.index += 1
            value = token.value if token.kind in ("NUMBER", "STRING") else token.kind == "TRUE"
            return self.node(Literal(value, token.pos))
        if token.kind == "CELL":
            start = self.reference()
            if self.accept(":"):
                end = self.reference()
                return self.node(Range(start, end, start.pos))
            return start
        if self.accept("("):
            expression = self.expression()
            self.expect(")")
            return expression
        if self.accept("IDENT"):
            self.expect("(", "'(' после имени функции")
            arguments = []
            if self.current.kind != ")":
                arguments.append(self.expression())
                while self.accept(","):
                    arguments.append(self.expression())
            self.expect(")")
            return self.node(Call(token.value, tuple(arguments), token.pos), *arguments)
        self.error(token, "Ожидалось число, строка, true/false, ячейка, вызов функции или выражение в скобках.")
