"""TableScript: a statically checked spreadsheet language compiler."""

__version__ = "1.0.0"


def compile_text(text: str, filename: str = "<input>"):
    """Return a Compilation with AST, dependencies, types and Python source."""
    from .compiler import compile_text as compile_impl
    return compile_impl(text, filename)
