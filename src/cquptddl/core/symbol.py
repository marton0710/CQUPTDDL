from collections.abc import Callable
from typing import Any

_symbol_table: dict[str, Callable] = {}


def export(name: str, func: Callable):
    if name in _symbol_table:
        raise NameError(f"符号{name}已存在")
    _symbol_table[name] = func


def call(name: str, *args, **kw) -> Any:
    return _symbol_table[name](*args, **kw)
