from collections.abc import Callable
from typing import Any


class SymbolTable:
    _table: dict[str, Callable]

    def __init__(self):
        self._table = {}

    def register(self, name: str, func: Callable):
        if name in self._table:
            raise NameError(f"符号{name}已存在")
        self._table[name] = func

    def call(self, name: str, *args, **kw) -> Any:
        return self._table[name](*args, **kw)
