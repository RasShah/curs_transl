"""Source coordinates and user-facing diagnostics, with no tracebacks."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    line: int
    column: int


@dataclass(frozen=True)
class Source:
    text: str
    filename: str = "<input>"


class TranslationError(Exception):
    def __init__(self, source: Source, position: Position, stage: str,
                 code: str, message: str):
        self.source = source
        self.position = position
        self.stage = stage
        self.code = code
        self.message = message
        super().__init__(message)

    def __str__(self):
        p = self.position
        heading = (f"{self.source.filename}:{p.line}:{p.column}: "
                   f"{self.stage} [{self.code}]: {self.message}")
        lines = self.source.text.split("\n")
        if 1 <= p.line <= len(lines):
            # Very long input lines must not create enormous diagnostic output.
            line = lines[p.line - 1].rstrip("\r").replace("\t", " ")
            start = max(0, p.column - 61)
            excerpt = line[start:start + 140]
            prefix = "…" if start else ""
            return f"{heading}\n  {prefix}{excerpt}\n  {' ' * (p.column - 1 - start + len(prefix))}^"
        return heading


def fail(source, position, stage, code, message):
    raise TranslationError(source, position, stage, code, message)
