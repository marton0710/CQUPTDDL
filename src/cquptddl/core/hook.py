from collections import defaultdict
from collections.abc import Callable, Coroutine
from logging import INFO, getLogger
from typing import NamedTuple

from . import task

_logger = getLogger(__name__)
_logger.setLevel(INFO)


class HookEntry(NamedTuple):
    func: Callable[..., Coroutine]
    background: bool
    """是否后台运行（非阻塞）"""
    fatal: bool
    """
    失败时是否阻断hook点的后续执行
    **不可与`background`同时为`True`**
    """


_hook_table = defaultdict[str, list[HookEntry]](list)
"""
hook表
key: hook名称
value: hook函数列表
    每一项为：记录元组
例如：
```python
{
    "auth.before_delete_user": [
        HookEntry(cquptddl.service.meetschedule.event_handlers.on_delete_user, False, True)
    ]
}
```
"""


def register(
    name: str,
    func: Callable[..., Coroutine],
    *,
    background: bool = False,
    fatal: bool = False,
    index: int = 99,
):
    if background and fatal:
        raise ValueError(f"后台运行的钩子 {name} ({func}) 不能阻断执行")
    _hook_table[name].insert(index, HookEntry(func, background, fatal))


def on[F: Callable[..., Coroutine]](
    name: str, *, background: bool = False, fatal: bool = False, index: int = 99
) -> Callable[[F], F]:
    def wrapper(f: F) -> F:
        register(name, f, background=background, fatal=fatal, index=index)
        return f

    return wrapper


async def trigger(name: str, *args, **kw):
    for func, background, fatal in _hook_table.get(name, ()):
        _logger.debug("正在调用名为%s的钩子%s", name, func)
        coro = func(*args, **kw)
        if background:
            task.background(coro)
        else:
            try:
                await coro
            except Exception as e:
                _logger.error("调用名为%s的钩子%s时发生异常", name, func, exc_info=e)
                if fatal:
                    raise


# class Hook[**P]:
#     name: str

#     def __init__(self, name: str):
#         self.name = name

#     def on[R: Coroutine](
#         self, *, background: bool = False, fatal: bool = False, index: int = 99
#     ) -> Callable[[Callable[P, R]], Callable[P, R]]:
#         def wrapper(f: Callable[P, R]) -> Callable[P, R]:
#             register(self.name, f, background=background, fatal=fatal, index=index)
#             return f

#         return wrapper

#     def __call__(self, *args: P.args, **kw: P.kwargs):
#         return trigger(self.name, *args, **kw)

#     def __repr__(self) -> str:
#         return f"<Hook {self.name}>"
