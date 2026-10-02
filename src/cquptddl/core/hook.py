from collections import defaultdict
from collections.abc import Callable, Coroutine
from logging import INFO, getLogger

from . import task

_logger = getLogger(__name__)
_logger.setLevel(INFO)

_hook_table = defaultdict[str, list[tuple[Callable[..., Coroutine], bool]]](list)
"""
hook表
key: hook名称
value: hook函数列表
    每一项为：记录元组
        [0] 为`Callable`
            需满足：返回一个`Coroutine`，即该函数是一个异步函数
        [1] 为是否后台运行（非阻塞）
例如：
```python
{
    "auth.before_delete_user": [
        (<cquptddl.service.meetschedule.event_handlers.on_delete_user>, False)
    ]
}
```
"""


def register(
    name: str,
    func: Callable[..., Coroutine],
    *,
    background: bool = False,
    index: int = 99,
):
    _hook_table[name].insert(index, (func, background))


def on[F: Callable[..., Coroutine]](
    name: str, *, background: bool = False, index: int = 99
) -> Callable[[F], F]:
    def wrapper(f: F) -> F:
        register(name, f, background=background, index=index)
        return f

    return wrapper


async def trigger(name: str, *args, **kw):
    for func, background in _hook_table.get(name, ()):
        _logger.debug("正在调用名为%s的钩子%s", name, func)
        coro = func(*args, **kw)
        if background:
            task.background(coro)
        else:
            try:
                await coro
            except Exception as e:
                _logger.error("调用名为%s的钩子%s时发生异常", name, func, exc_info=e)
                continue
