"""Public compilation pipeline. It neither executes formulas nor writes files."""
from dataclasses import dataclass
from .codegen import generate
from .diagnostics import Position, Source, fail
from .limits import MAX_SOURCE_BYTES
from .parser import Parser
from .semantic import Analyzer, Analysis
from .nodes import Program


@dataclass
class Compilation:
    source: Source
    program: Program
    analysis: Analysis
    python: str


def compile_text(text, filename="<input>", *, source_path=None):
    source = Source(text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n"), filename)
    if len(text.encode("utf-8")) > MAX_SOURCE_BYTES:
        fail(source, Position(1, 1), "ошибка входных данных", "E_LIMIT", "Исходный файл больше 16 МиБ.")
    program = Parser(source).parse()
    analysis = Analyzer(source).analyze(program)
    return Compilation(source, program, analysis, generate(source, analysis, source_path))
