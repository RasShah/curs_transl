"""Fill expansion, dependency graph, iterative cycle detection and type inference."""
from dataclasses import dataclass, replace
from .diagnostics import Position, fail
from .limits import (MAX_CELLS, MAX_COLUMNS, MAX_CSV_FIELDS, MAX_DEPENDENCIES,
                     MAX_EXPANDED_REFERENCES, MAX_ROWS)
from .nodes import (Assignment, Binary, Call, Export, Fill, Literal, Range,
                    Reference, Unary, column_name, walk)

NUMBER, STRING, BOOLEAN, RANGE = "number", "string", "boolean", "range"
TYPE_LABEL = {NUMBER: "число", STRING: "строка", BOOLEAN: "логическое значение", RANGE: "диапазон"}
AGGREGATES = ("SUM", "AVG", "MIN", "MAX")


def addresses(area):
    """Yield canonical addresses in row-major order; bounds checked beforehand."""
    for row in range(area.start.row, area.end.row + 1):
        for column in range(area.start.column, area.end.column + 1):
            yield f"{column_name(column)}{row}"


@dataclass
class Analysis:
    definitions: dict
    dependencies: dict
    order: tuple
    types: dict
    export: Export
    rows: int
    columns: int


class Analyzer:
    def __init__(self, source):
        self.source = source
        self.definitions = {}
        self.types = {}

    def error(self, node, code, message):
        fail(self.source, node.pos, "семантическая ошибка", code, message)

    def check_reference(self, ref, target=False):
        if not (1 <= ref.column <= MAX_COLUMNS and 1 <= ref.row <= MAX_ROWS):
            self.error(ref, "E_ADDRESS", f"Адрес {ref.spelling} выходит за границы: "
                       f"столбцы A…{column_name(MAX_COLUMNS)}, строки 1…{MAX_ROWS}.")
        if target and (ref.absolute_column or ref.absolute_row):
            self.error(ref, "E_TARGET", "В адресе определяемой ячейки и цели fill нельзя использовать '$'.")

    def check_range(self, area, target=False):
        self.check_reference(area.start, target)
        self.check_reference(area.end, target)
        if area.start.column > area.end.column or area.start.row > area.end.row:
            self.error(area, "E_RANGE", "Начало диапазона должно быть левее и выше его конца.")
        size = ((area.end.column - area.start.column + 1) *
                (area.end.row - area.start.row + 1))
        if size > MAX_CELLS:
            self.error(area, "E_LIMIT", f"В диапазоне больше {MAX_CELLS} ячеек.")

    def shifted(self, node, dx, dy):
        if isinstance(node, Reference):
            shifted = replace(node,
                column=node.column if node.absolute_column else node.column + dx,
                row=node.row if node.absolute_row else node.row + dy)
            self.check_reference(shifted)
            return shifted
        if isinstance(node, Range):
            result = replace(node, start=self.shifted(node.start, dx, dy),
                             end=self.shifted(node.end, dx, dy))
            self.check_range(result)
            return result
        if isinstance(node, Unary):
            return replace(node, operand=self.shifted(node.operand, dx, dy))
        if isinstance(node, Binary):
            return replace(node, left=self.shifted(node.left, dx, dy),
                           right=self.shifted(node.right, dx, dy))
        if isinstance(node, Call):
            return replace(node, arguments=tuple(self.shifted(a, dx, dy) for a in node.arguments))
        return node

    def define(self, assignment):
        ref = assignment.target
        self.check_reference(ref, target=True)
        if ref.name in self.definitions:
            old = self.definitions[ref.name].pos
            self.error(ref, "E_DUPLICATE", f"Ячейка {ref.name} определена повторно; "
                       f"первое определение: строка {old.line}, позиция {old.column}.")
        if len(self.definitions) >= MAX_CELLS:
            self.error(ref, "E_LIMIT", f"Количество ячеек превышает {MAX_CELLS}.")
        self.definitions[ref.name] = assignment

    def expand(self, program):
        exports = []
        for statement in program.statements:
            if isinstance(statement, Export):
                exports.append(statement)
            elif isinstance(statement, Assignment):
                self.define(statement)
            elif isinstance(statement, Fill):
                area = statement.target
                self.check_range(area, target=True)
                for row in range(area.start.row, area.end.row + 1):
                    for column in range(area.start.column, area.end.column + 1):
                        ref = Reference(column, row, False, False, area.pos)
                        expression = self.shifted(statement.expression,
                                                  column - area.start.column,
                                                  row - area.start.row)
                        self.define(Assignment(ref, expression, statement.pos))
        if not exports:
            fail(self.source, Position(1, 1), "семантическая ошибка", "E_EXPORT",
                 'Требуется одна команда export "result.csv";.')
        if len(exports) > 1:
            self.error(exports[1], "E_EXPORT", "Допускается ровно одна команда export.")
        export = exports[0]
        if not export.path.strip() or any(c in export.path for c in "\x00\r\n"):
            self.error(export, "E_EXPORT", "Имя CSV-файла не должно быть пустым или содержать NUL и переводы строк.")
        if not self.definitions:
            self.error(export, "E_EMPTY", "Таблица должна содержать хотя бы одну определённую ячейку.")
        rows = max(a.target.row for a in self.definitions.values())
        columns = max(a.target.column for a in self.definitions.values())
        if rows * columns > MAX_CSV_FIELDS:
            self.error(export, "E_LIMIT", f"Прямоугольник CSV содержит больше {MAX_CSV_FIELDS} полей.")
        return export, rows, columns

    def graph(self):
        graph = {}
        edge_count = 0
        expanded_count = 0
        for name, assignment in self.definitions.items():
            edges = {}
            for node in walk(assignment.expression):
                if isinstance(node, Reference):
                    self.check_reference(node)
                    targets = (node.name,)
                elif isinstance(node, Range):
                    self.check_range(node)
                    targets = addresses(node)
                else:
                    continue
                for target in targets:
                    expanded_count += 1
                    if expanded_count > MAX_EXPANDED_REFERENCES:
                        self.error(node, "E_LIMIT", f"После раскрытия диапазонов больше {MAX_EXPANDED_REFERENCES} обращений к ячейкам.")
                    if target not in self.definitions:
                        self.error(node, "E_UNDEFINED", f"Формула {name} обращается к неопределённой ячейке {target}.")
                    if target not in edges:
                        edge_count += 1
                        if edge_count > MAX_DEPENDENCIES:
                            self.error(node, "E_LIMIT", f"Граф содержит больше {MAX_DEPENDENCIES} зависимостей.")
                        edges[target] = node.pos
            graph[name] = edges
        return graph

    def topological_order(self, graph):
        # Iterative DFS avoids recursion limits on long chains of cells.
        state = {}
        order = []
        for root in graph:
            if state.get(root) == 2:
                continue
            path = [root]
            active = {root: 0}
            state[root] = 1
            stack = [(root, iter(graph[root]))]
            while stack:
                current, pending = stack[-1]
                dependency = next(pending, None)
                if dependency is None:
                    stack.pop()
                    path.pop()
                    del active[current]
                    state[current] = 2
                    order.append(current)
                elif state.get(dependency) == 1:
                    cycle = path[active[dependency]:] + [dependency]
                    shown = cycle if len(cycle) <= 15 else cycle[:7] + ["…"] + cycle[-7:]
                    fail(self.source, graph[current][dependency], "семантическая ошибка", "E_CYCLE",
                         "Циклическая ссылка: " + " -> ".join(shown) + ".")
                elif state.get(dependency) != 2:
                    state[dependency] = 1
                    active[dependency] = len(path)
                    path.append(dependency)
                    stack.append((dependency, iter(graph[dependency])))
        return tuple(order)

    def infer(self, node):
        if isinstance(node, Literal):
            return BOOLEAN if isinstance(node.value, bool) else STRING if isinstance(node.value, str) else NUMBER
        if isinstance(node, Reference):
            return self.types[node.name]
        if isinstance(node, Range):
            return RANGE
        if isinstance(node, Unary):
            operand_type = self.infer(node.operand)
            if operand_type != NUMBER:
                self.error(node, "E_TYPE", f"Унарный '{node.operator}' требует число, получено: {TYPE_LABEL[operand_type]}.")
            return NUMBER
        if isinstance(node, Binary):
            left, right = self.infer(node.left), self.infer(node.right)
            op = node.operator
            valid = False
            if op == "+" and left == right == STRING:
                return STRING
            if op in ("+", "-", "*", "/", "%"):
                valid = left == right == NUMBER
                result = NUMBER
            else:
                valid = left == right and left in (NUMBER, STRING, BOOLEAN)
                if op in ("<", "<=", ">", ">="):
                    valid = valid and left != BOOLEAN
                result = BOOLEAN
            if not valid:
                self.error(node, "E_TYPE", f"Оператор '{op}' несовместим с типами "
                           f"{TYPE_LABEL[left]} и {TYPE_LABEL[right]}.")
            return result
        if isinstance(node, Call):
            if node.name not in (*AGGREGATES, "IF"):
                self.error(node, "E_FUNCTION", f"Неизвестная функция {node.name}; допустимы SUM, AVG, MIN, MAX, IF.")
            if node.name == "IF":
                if len(node.arguments) != 3:
                    self.error(node, "E_ARITY", "IF принимает ровно 3 аргумента: условие, значение при true, значение при false.")
                condition, yes, no = (self.infer(x) for x in node.arguments)
                if condition != BOOLEAN:
                    self.error(node.arguments[0], "E_TYPE", "Первый аргумент IF должен иметь логический тип.")
                if yes != no or yes == RANGE:
                    self.error(node, "E_TYPE", "Ветви IF должны иметь одинаковый скалярный тип.")
                return yes
            if not node.arguments:
                self.error(node, "E_ARITY", f"{node.name} требует хотя бы один числовой аргумент или диапазон.")
            for argument in node.arguments:
                kind = self.infer(argument)
                if kind == RANGE:
                    if any(self.types[name] != NUMBER for name in addresses(argument)):
                        self.error(argument, "E_TYPE", f"Все ячейки диапазона в {node.name} должны быть числовыми.")
                elif kind != NUMBER:
                    self.error(argument, "E_TYPE", f"{node.name} принимает только числа и числовые диапазоны.")
            return NUMBER
        raise AssertionError(f"Unsupported AST node: {type(node)}")

    def analyze(self, program):
        export, rows, columns = self.expand(program)
        graph = self.graph()
        order = self.topological_order(graph)
        for name in order:
            assignment = self.definitions[name]
            kind = self.infer(assignment.expression)
            if kind == RANGE:
                self.error(assignment.expression, "E_TYPE", "Нельзя присвоить диапазон ячейке; передайте его в SUM, AVG, MIN или MAX.")
            self.types[name] = kind
        return Analysis(self.definitions, graph, order, self.types, export, rows, columns)
