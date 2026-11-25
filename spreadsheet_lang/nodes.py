"""Immutable abstract syntax tree. Every node retains its source position."""
from __future__ import annotations
from dataclasses import dataclass
from .diagnostics import Position


@dataclass(frozen=True)
class Literal:
    value: int | float | str | bool
    pos: Position


def column_name(column: int) -> str:
    result = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        result = chr(65 + remainder) + result
    return result


@dataclass(frozen=True)
class Reference:
    column: int
    row: int
    absolute_column: bool
    absolute_row: bool
    pos: Position

    @property
    def name(self):
        return f"{column_name(self.column)}{self.row}"

    @property
    def spelling(self):
        return (f"{'$' if self.absolute_column else ''}{column_name(self.column)}"
                f"{'$' if self.absolute_row else ''}{self.row}")


@dataclass(frozen=True)
class Range:
    start: Reference
    end: Reference
    pos: Position


@dataclass(frozen=True)
class Unary:
    operator: str
    operand: Expr
    pos: Position


@dataclass(frozen=True)
class Binary:
    operator: str
    left: Expr
    right: Expr
    pos: Position


@dataclass(frozen=True)
class Call:
    name: str
    arguments: tuple[Expr, ...]
    pos: Position


Expr = Literal | Reference | Range | Unary | Binary | Call


@dataclass(frozen=True)
class Assignment:
    target: Reference
    expression: Expr
    pos: Position


@dataclass(frozen=True)
class Fill:
    target: Range
    expression: Expr
    pos: Position


@dataclass(frozen=True)
class Export:
    path: str
    pos: Position


@dataclass(frozen=True)
class Program:
    statements: tuple[Assignment | Fill | Export, ...]


def children(expression: Expr):
    if isinstance(expression, Unary):
        return (expression.operand,)
    if isinstance(expression, Binary):
        return (expression.left, expression.right)
    if isinstance(expression, Call):
        return expression.arguments
    return ()


def walk(expression: Expr):
    stack = [expression]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(children(node)))
