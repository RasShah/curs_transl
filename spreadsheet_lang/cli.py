"""Command line interface and atomic output publication."""
import argparse
import os
import sys
import tempfile
from pathlib import Path
from . import __version__
from .compiler import compile_text
from .diagnostics import Position, Source, TranslationError
from .limits import MAX_SOURCE_BYTES


class Arguments(argparse.ArgumentParser):
    def error(self, message):
        self.print_help(sys.stderr)
        self.exit(2, f"\nОшибка параметров: {message}\n")


def configure_streams():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def atomic_write(path, text):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                dir=path.parent, prefix=".tablescript-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    configure_streams()
    parser = Arguments(prog="translator", description="TableScript: транслятор языка электронных таблиц в Python.")
    parser.add_argument("input", help="исходный файл UTF-8 с расширением .tbl")
    parser.add_argument("-o", "--output", required=True, help="имя создаваемой Python-программы")
    parser.add_argument("--show-order", action="store_true", help="показать порядок вычисления ячеек")
    parser.add_argument("--version", action="version", version=f"TableScript {__version__}")
    args = parser.parse_args(argv)
    incoming, outgoing = Path(args.input), Path(args.output)
    try:
        if (incoming.resolve() == outgoing.resolve() or
                (incoming.exists() and outgoing.exists() and os.path.samefile(incoming, outgoing))):
            raise OSError("Входной и выходной файлы должны быть различными.")
        with incoming.open("rb") as stream:
            raw = stream.read(MAX_SOURCE_BYTES + 1)
        if len(raw) > MAX_SOURCE_BYTES:
            raise OSError("Исходный файл больше 16 МиБ.")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            prefix = (raw[:exc.start].decode("utf-8", errors="replace").removeprefix("\ufeff")
                      .replace("\r\n", "\n").replace("\r", "\n"))
            position = Position(prefix.count("\n") + 1, len(prefix.rsplit("\n", 1)[-1]) + 1)
            decoded = (raw.decode("utf-8", errors="replace").removeprefix("\ufeff")
                       .replace("\r\n", "\n").replace("\r", "\n"))
            raise TranslationError(Source(decoded, str(incoming)),
                                   position, "ошибка кодировки", "E_ENCODING",
                                   "Входной файл должен быть сохранён в UTF-8.") from None
        compilation = compile_text(text, str(incoming), source_path=str(incoming.resolve()))
        atomic_write(outgoing, compilation.python)
        print(f"Создано: {outgoing}; ячеек: {len(compilation.analysis.definitions)}.")
        if args.show_order:
            print("Порядок: " + " -> ".join(compilation.analysis.order))
        return 0
    except TranslationError as exc:
        print(exc, file=sys.stderr)
        return 1
    except (OSError, ValueError, MemoryError) as exc:
        print(f"translator: ошибка файлов или ресурсов: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
