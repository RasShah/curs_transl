"""A handwritten UTF-8-aware lexer. Input is never evaluated as Python."""
import math
import re
from dataclasses import dataclass
from .diagnostics import Position, Source, fail
from .limits import MAX_NUMBER_LENGTH, MAX_TOKENS

NUMBER = re.compile(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
WORD = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
CELL = re.compile(r"(\$?)([A-Za-z]+)(\$?)([1-9][0-9]*)\Z")


@dataclass(frozen=True)
class Token:
    kind: str
    value: object
    pos: Position


class Lexer:
    def __init__(self, source: Source):
        self.source = source
        self.text = source.text.replace("\r\n", "\n").replace("\r", "\n")
        self.index = 0
        self.line = 1
        self.column = 1

    def advance(self, count=1):
        fragment = self.text[self.index:self.index + count]
        self.index += count
        if "\n" in fragment:
            self.line += fragment.count("\n")
            self.column = len(fragment.rsplit("\n", 1)[1]) + 1
        else:
            self.column += len(fragment)

    def error(self, pos, code, message):
        fail(self.source, pos, "лексическая ошибка", code, message)

    def string(self, pos):
        quote = self.text[self.index]
        self.advance()
        result = []
        escapes = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'"}
        while self.index < len(self.text):
            char = self.text[self.index]
            if char == quote:
                self.advance()
                return "".join(result)
            if ord(char) < 32:
                self.error(pos, "E_STRING", "Незакрытая строка или управляющий символ в строке.")
            if char == "\\":
                escape_pos = Position(self.line, self.column)
                self.advance()
                if self.index >= len(self.text):
                    self.error(pos, "E_STRING", "Строка не закрыта кавычкой.")
                char = self.text[self.index]
                if char not in escapes:
                    self.error(escape_pos, "E_ESCAPE", f"Неизвестная escape-последовательность \\{char}.")
                result.append(escapes[char])
            else:
                result.append(char)
            self.advance()
        self.error(pos, "E_STRING", "Строка не закрыта кавычкой.")

    def tokens(self):
        result = []
        while self.index < len(self.text):
            char = self.text[self.index]
            pos = Position(self.line, self.column)
            if char in " \t\n\f":
                self.advance()
                continue
            if char == "#" or self.text.startswith("//", self.index):
                end = self.text.find("\n", self.index)
                self.advance((len(self.text) if end < 0 else end) - self.index)
                continue
            if self.text.startswith("/*", self.index):
                end = self.text.find("*/", self.index + 2)
                if end < 0:
                    self.error(pos, "E_COMMENT", "Многострочный комментарий не закрыт символами */.")
                self.advance(end + 2 - self.index)
                continue
            if char in "\"'":
                token = Token("STRING", self.string(pos), pos)
            elif char in "0123456789" or (char == "." and self.index + 1 < len(self.text)
                                          and self.text[self.index + 1] in "0123456789"):
                match = NUMBER.match(self.text, self.index)
                spelling = match.group()
                self.advance(len(spelling))
                if self.index < len(self.text) and (self.text[self.index].isascii()
                        and (self.text[self.index].isalnum() or self.text[self.index] in "_.$")):
                    self.error(pos, "E_NUMBER", "Некорректная запись числа; используйте десятичную форму, например 1.5e-2.")
                if len(spelling) > MAX_NUMBER_LENGTH:
                    self.error(pos, "E_NUMBER", f"Числовой литерал длиннее {MAX_NUMBER_LENGTH} символов.")
                value = float(spelling) if any(c in spelling for c in ".eE") else int(spelling)
                if isinstance(value, float) and not math.isfinite(value):
                    self.error(pos, "E_NUMBER", "Числовой литерал выходит за диапазон float64.")
                mantissa = spelling.lower().split("e")[0]
                if value == 0 and any(c in "123456789" for c in mantissa):
                    self.error(pos, "E_NUMBER", "Ненулевой числовой литерал слишком мал для float64.")
                token = Token("NUMBER", value, pos)
            elif char.isascii() and (char.isalpha() or char in "_$"):
                match = WORD.match(self.text, self.index)
                word = match.group()
                self.advance(len(word))
                upper = word.upper()
                if upper in ("FILL", "EXPORT", "TRUE", "FALSE"):
                    token = Token(upper, upper, pos)
                elif CELL.fullmatch(word):
                    token = Token("CELL", upper, pos)
                elif "$" in word or re.fullmatch(r"[A-Za-z]+[0-9]+", word):
                    self.error(pos, "E_CELL", f"Недопустимый адрес {word!r}; пример адреса: A1 или $A$1.")
                else:
                    token = Token("IDENT", upper, pos)
            else:
                pair = self.text[self.index:self.index + 2]
                if pair in ("==", "!=", "<=", ">="):
                    token = Token(pair, pair, pos)
                    self.advance(2)
                elif char in "+-*/%()=:;,<>":
                    token = Token(char, char, pos)
                    self.advance()
                else:
                    self.error(pos, "E_CHARACTER", f"Недопустимый символ {char!r}.")
            result.append(token)
            if len(result) > MAX_TOKENS:
                self.error(pos, "E_LIMIT", f"Превышен предел {MAX_TOKENS} токенов.")
        result.append(Token("EOF", None, Position(self.line, self.column)))
        return result
