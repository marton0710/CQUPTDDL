from collections.abc import Callable
from typing import Any

from . import db, task  # noqa: F401
from .config import config
from .factory import get_client, get_session
from .symbol import SymbolTable

__all__ = ["call", "config", "export", "factory", "get_client", "get_session", "task"]
_symbol_table = SymbolTable()


def export(name: str, func: Callable):
    _symbol_table.register(name, func)


def call(name: str, *args, **kw) -> Any:
    return _symbol_table.call(name, *args, **kw)


def get_current_user_cookie():
    return {
        "route": "36c256fc918f0bb5b2115e9adfc1816b",
        "JSESSIONID": "657F53C1A29698F90DE325463C1E3791",
        "CASTGC": "TGT-291372-BhBVbXyfikVGMP4G2N-70YzYU1ypy-f9ret2N63YDlunlRfveeovDeNsVlfmFjz2OE8null_main",
        "happyVoyage": "4KRY3KVzWbslCYAGrGtRCWvo8mANaqsqpOBIJmH6rcDBTXawwTUcVY98EquMaFCb7c6k41R1CmdXnPHbchnsBoWAY7CSDUxd/7JJwjt+DrL9vzJGon6srzhtTLZpBGt+S77KNLfZ/JrEey/TCopcCkGI7OLVfvOUoG2gEjjYZvI=",
        "platformMultilingual": "zh_CN",
    }
    return {
        "route": "bca4c666c8d521e78cedf949592f469e",
        "JSESSIONID": "3BF55C8D06F0284ECD55F273CE3E093C",
        "CASTGC": "TGT-317821-2xhuEE3Sx5IsRSUmeVlCMtJTrqgqvV9Zj-FqtCCB75gJJxjC04q-EoJzS-NlwGR-vKwnull_main",
        "happyVoyage": "4vsPjxKTwoJuBuKZWC1DuMl+q26/mNH3sSxvr768mjpgrmFbwKEAP+lttYn/zUVNGICTAkn/JQrQcUulkm9G7p6suHXQvyIzZEVRiKk05qV6/QK41U1aonrSuULwL9evk0O10s1y0mcPDpCqBuVbSYCLlutttpQvP55lecEDgfc=",
        "platformMultilingual": "zh_CN",
    }


export("auth.get_current_user_cookie", get_current_user_cookie)
