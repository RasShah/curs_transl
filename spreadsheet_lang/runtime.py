"""Standalone runtime copied verbatim into each generated Python program."""
import csv
import math
import os
import sys
import tempfile
from pathlib import Path


class _TableFailure(Exception):
    def __init__(self, line, column, message):
        self.line, self.column, self.message = line, column, message
        super().__init__(message)


def _checked(value, line, column):
    if isinstance(value, float) and not math.isfinite(value):
        raise _TableFailure(line, column, "Числовое переполнение или нечисловой результат.")
    if type(value) is int and value.bit_length() > 4096:
        raise _TableFailure(line, column, "Целое число превышает предел 4096 бит.")
    if isinstance(value, str) and len(value) > 16 * 1024 * 1024:
        raise _TableFailure(line, column, "Длина строки превышает 16 МиБ символов.")
    return value


def _binary(op, left, right, line, column):
    try:
        if op == "+": result = left + right
        elif op == "-": result = left - right
        elif op == "*": result = left * right
        elif op == "/": result = left / right
        elif op == "%": result = left % right
        elif op == "==": result = left == right
        elif op == "!=": result = left != right
        elif op == "<": result = left < right
        elif op == "<=": result = left <= right
        elif op == ">": result = left > right
        elif op == ">=": result = left >= right
        else: raise AssertionError(op)
        return _checked(result, line, column)
    except ZeroDivisionError:
        raise _TableFailure(line, column, "Деление или остаток от деления на ноль.") from None
    except (OverflowError, ValueError):
        raise _TableFailure(line, column, "Числовое переполнение.") from None


def _unary(op, value, line, column):
    return _checked(-value if op == "-" else +value, line, column)


def _aggregate(name, values, line, column):
    try:
        if name == "SUM": result = sum(values)
        elif name == "AVG": result = sum(values) / len(values)
        elif name == "MIN": result = min(values)
        elif name == "MAX": result = max(values)
        else: raise AssertionError(name)
        return _checked(result, line, column)
    except (OverflowError, ValueError):
        raise _TableFailure(line, column, "Переполнение при вычислении " + name + ".") from None


def _cell(name, line, column, operation):
    try:
        return _checked(operation(), line, column)
    except _TableFailure as exc:
        raise _TableFailure(exc.line, exc.column, f"Ячейка {name}: {exc.message}") from None
    except MemoryError:
        raise _TableFailure(line, column, f"Недостаточно памяти для ячейки {name}.") from None


def _csv_value(value):
    if type(value) is bool:
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e16:
        return str(int(value))
    return str(value)


def _column_name(column):
    result = ""
    while column:
        column, digit = divmod(column - 1, 26)
        result = chr(65 + digit) + result
    return result


def _write_csv(cells, rows, columns, filename, line, column, source_path):
    # An export path is relative to the generated program, regardless of cwd.
    destination = Path(filename)
    if not destination.is_absolute():
        destination = Path(__file__).resolve().parent / destination
    temporary = None
    try:
        protected = [Path(__file__), Path(source_path)] if source_path else [Path(__file__)]
        for path in protected:
            if (destination.resolve() == path.resolve() or
                    (destination.exists() and path.exists() and os.path.samefile(destination, path))):
                raise _TableFailure(line, column, "CSV-файл не может заменять исходную или сгенерированную программу.")
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                dir=destination.parent, prefix=".tablescript-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.writer(stream, delimiter=",", lineterminator="\n")
            for row in range(1, rows + 1):
                writer.writerow([_csv_value(cells[f"{_column_name(col)}{row}"])
                    if f"{_column_name(col)}{row}" in cells else ""
                    for col in range(1, columns + 1)])
        os.replace(temporary, destination)
        return destination
    except (OSError, ValueError) as exc:
        raise _TableFailure(line, column, f"Не удалось сохранить CSV {filename!r}: {exc}.") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _configure_streams():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
