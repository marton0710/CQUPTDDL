"""Meet课程表后台同步任务 —— 统一阶段模型。

设计要点：
* 把「远程结果」与「本地该做什么」拆开：远程只汇报 ``RemoteResult``，
  本地落库动作由唯一一份迁移表 ``_transition`` 决定。
* 每个阶段不再用异常（``_MeetscheduleBatchActionFailed``）搬运"部分失败"，
  而是统一产出 ``list[ItemOutcome]``，由唯一落库器 ``_apply_outcomes`` 执行。
* 创建事件成功后回填 ``meet_event_id``（修"事件 id 永不回填"的断链）。
* 清理永远无法镜像的条目（作业已删除 / 无 deadline），避免无限重试。
* Meet api-key 无效（401）/权限不足（403）：检测到的用户在本窗口末尾统一自动解绑，
  期间从阶段循环中剔除，不再对其发无效请求。
* 回拉阶段发现本地作业已不存在 → 置 PENDING_DELETE，交给删除阶段清理远端镜像。
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum
from itertools import batched
from logging import INFO, getLogger
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from meetschedule_sdk import (
    AsyncMeetSchedule,
    EventInput,
    EventPatch,
    EventType,
    TimeMode,
)
from meetschedule_sdk.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    UnprocessableEntityError,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from cquptddl import core
from cquptddl.model.db import Homework
from cquptddl.model.db.meetschedule_config import MeetscheduleConfig
from cquptddl.model.db.meetschedule_tracked_event import (
    MeetscheduleEntry,
)
from cquptddl.model.db.meetschedule_tracked_event import (
    MeetscheduleEntryStatus as _Status,
)

from . import limiter

_logger = getLogger(__name__)
_logger.setLevel(INFO)

# 状态别名，方便下面的迁移表读起来像自然语言。
PENDING = _Status.PENDING
PENDING_UPDATE = _Status.PENDING_UPDATE
PENDING_DELETE = _Status.PENDING_DELETE
SUCCESS = _Status.SUCCESS


# ── 1. 领域类型 ────────────────────────────────────────────────────────────


class RemoteResult(StrEnum):
    """远程 API 对某一次操作的真实结局（外部世界的唯一原始信号）。"""

    OK = "ok"  # 远程已办成（push 还会带新 event_id）
    MISSING = "missing"  # 远端对象不存在 / 已被删除（404）
    PERMANENT = "permanent"  # 永久失败，重试无意义（422 / 409）
    TRANSIENT = "transient"  # 临时失败（网络 / 限流 429），值得退避重试


class Phase(StrEnum):
    """四个阶段 = 四种本地状态的"车道名"。给迁移表提供解释上下文。"""

    PUSH = "push"  # 起点 PENDING：新建远端事件
    UPDATE = "update"  # 起点 PENDING_UPDATE：同步 done
    DELETE = "delete"  # 起点 PENDING_DELETE：删远端事件 + 删本地行
    PULL = "pull"  # 起点 SUCCESS：把远端真实 done 回写本地


# 每个阶段处理的本地状态（也是该阶段产物的归属集合）。
_PHASE_SOURCE_STATUS: dict[Phase, _Status] = {
    Phase.PUSH: PENDING,
    Phase.UPDATE: PENDING_UPDATE,
    Phase.DELETE: PENDING_DELETE,
    Phase.PULL: SUCCESS,
}


@dataclass(frozen=True)
class ItemOutcome:
    """一条作业在某阶段产生的处理结果（跨层交付物）。

    携带"远程结局 + 附带数据"，但不包含任何"本地该怎么办"的判断——
    那是迁移表 ``_transition`` 的职责。
    """

    homework_id: UUID  # 主语：关于哪条作业（== MeetscheduleEntry.id）
    result: RemoteResult  # 谓语：远程结局
    event_id: str | None = None  # push 成功时带回的远端事件 id
    done: bool | None = None  # pull 成功时带回的真实完成态（None=无需回写）


@dataclass
class LocalOp:
    """本地待执行的一小步动作（缺省字段 = 不处理）。"""

    delete: bool = False  # 删除这条 MeetscheduleEntry 跟踪
    new_status: _Status | None = None  # 跳去某个状态；None=保持现状（下轮重试）
    store_event_id: bool = False  # 把 ItemOutcome.event_id 回填到 meet_event_id
    patch_done: bool = False  # 把 ItemOutcome.done 回写 homework.done


# ── 2. 入口与编排 ──────────────────────────────────────────────────────────


async def _job():
    """唯一的定时任务：按四个起点状态分组，依次跑通 push → update → delete → pull。

    分组在 mutate 任何 entry 之前就完成（快照），保证后跑的阶段不受前面
    阶段改状态的影响。全程用一个 ``core.get_session()``，退出时统一 commit。

    本窗口内检测到 401/403 需要解绑的用户收集进 ``to_unbind``：一旦加入即从
    后续阶段剔除（不再对其打无效请求），等所有阶段跑完后统一本地解绑——
    避免在阶段循环中间删数据而污染快照分区。
    """
    async with core.get_session() as session:
        rows = (await session.execute(select(MeetscheduleEntry))).scalars().all()
        partitions = {
            phase: [e for e in rows if e.status == _PHASE_SOURCE_STATUS[phase]]
            for phase in Phase
        }

        to_unbind: set[str] = set()

        for phase in Phase:
            entries = partitions[phase]
            if not entries:
                continue
            async with _log_and_suppress(info=f"阶段 {phase.value} 处理时发生异常"):
                await _run_phase(session, phase, entries, to_unbind)

        for user_id in to_unbind:
            await _unbind_user_local(session, user_id)


# ── 3. 阶段骨架：分组 → 跑远程 → 落库 ─────────────────────────────────────


async def _run_phase(
    session: AsyncSession,
    phase: Phase,
    entries: list[MeetscheduleEntry],
    to_unbind: set[str],
):
    """一个阶段的总编排：本阶段涉及的作业一起查出，按用户分组，跑远程，最后统一落库。"""
    entries_by_id = {e.id: e for e in entries}
    homework_by_id = await _load_homeworks(session, entries)
    runner = _PHASE_RUNNERS[phase]

    outcomes: list[ItemOutcome] = []
    for user_id, group in _group_by_user(entries).items():
        outcomes += await _run_user(
            session,
            user_id,
            group,
            phase,
            runner,
            homework_by_id,
            to_unbind,
        )

    await _apply_outcomes(session, phase, outcomes, entries_by_id, homework_by_id)


async def _run_user(
    session: AsyncSession,
    user_id: str,
    group: list[MeetscheduleEntry],
    phase: Phase,
    runner: Callable,
    homework_by_id: dict[UUID, Homework],
    to_unbind: set[str],
) -> list[ItemOutcome]:
    """给一个用户开独立 client + meet，跑该阶段的真实远程逻辑。

    - 本窗口内已判定需解绑的用户（在 ``to_unbind`` 里）直接跳过——这是
      "剔除循环"，不再对其打无效请求。
    - 401/403 无法靠重试恢复 → 只把用户加入 ``to_unbind``（本轮末尾统一解绑），
      不在阶段循环中间删数据。
    - 其余异常（网络/限流等临时性错误）整体标 TRANSIENT 重试，不逐条误删。
    """
    if user_id in to_unbind:
        return []

    config = await session.get(MeetscheduleConfig, user_id)
    if config is None:
        # 配置已不存在（解绑残留等）→ 没有远端可达，这些跟踪条目作废。
        _logger.warning("用户%s没有Meet配置，清理其%d条跟踪", user_id, len(group))
        for e in group:
            await session.delete(e)
        return []

    try:
        async with (
            core.factory.get_client() as client,
            AsyncMeetSchedule(config.api_key, client=client) as meet,
        ):
            return await runner(meet, config, group, homework_by_id)
    except UnauthorizedError as exc:
        # api-key 无效（401）→ 本轮末自动解绑，避免每轮重试。
        _logger.error(
            "用户%s的Meet api-key 无效（401），本轮末将自动解绑", user_id, exc_info=exc
        )
        to_unbind.add(user_id)
        return []
    except ForbiddenError as exc:
        # 权限不足（403）同样无法靠重试解决 → 本轮末自动解绑。
        _logger.error(
            "用户%s的Meet api-key 权限不足（403），本轮末将自动解绑",
            user_id,
            exc_info=exc,
        )
        to_unbind.add(user_id)
        return []
    except Exception as exc:
        _logger.error(
            "处理用户%s的%s阶段时发生异常", user_id, phase.value, exc_info=exc
        )

    return [ItemOutcome(e.id, RemoteResult.TRANSIENT) for e in group]


async def _unbind_user_local(session: AsyncSession, user_id: str):
    """对单个用户执行本地解绑：删掉其全部跟踪条目与配置。

    只在 ``_job`` 末尾、四阶段全部跑完后调用，避免在阶段循环中删数据。
    （key 已不可用，远端事件无法访问，故只做本地清理。）
    """
    rows = (
        (
            await session.execute(
                select(MeetscheduleEntry).where(MeetscheduleEntry.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    for e in rows:
        await session.delete(e)

    config = await session.get(MeetscheduleConfig, user_id)
    if config is not None:
        await session.delete(config)

    _logger.warning("用户%s已自动解绑Meet，清理%d条跟踪", user_id, len(rows))


def _group_by_user(
    entries: list[MeetscheduleEntry],
) -> dict[str, list[MeetscheduleEntry]]:
    grouped: dict[str, list[MeetscheduleEntry]] = defaultdict(list)
    for e in entries:
        grouped[e.user_id].append(e)
    return grouped


async def _load_homeworks(
    session: AsyncSession, entries: list[MeetscheduleEntry]
) -> dict[UUID, Homework]:
    if not entries:
        return {}
    ids = [e.id for e in entries]
    rows = (
        (
            await session.execute(select(Homework).where(Homework.id.in_(ids)))  # ty: ignore[unresolved-attribute]
        )
        .scalars()
        .all()
    )
    return {h.id: h for h in rows}


# ── 4. 状态裁决（唯一迁移表）与唯一落库器 ────────────────────────────────


def _transition(phase: Phase, result: RemoteResult) -> LocalOp:
    """把「在哪个阶段、撞到哪种远程结局」翻译成本地动作。

    这是全模块唯一的本地状态迁移真值表。改同步规则只改这里。
    """
    if phase is Phase.PUSH:  # 起点 PENDING
        if result is RemoteResult.OK:
            return LocalOp(new_status=SUCCESS, store_event_id=True)
        if result is RemoteResult.TRANSIENT:
            return LocalOp()  # 保持 PENDING 重试
        return LocalOp(delete=True)  # MISSING/PERMANENT → 删跟踪

    if phase is Phase.UPDATE:  # 起点 PENDING_UPDATE
        if result is RemoteResult.OK:
            return LocalOp(new_status=SUCCESS)
        if result is RemoteResult.TRANSIENT:
            return LocalOp()  # 保持 PENDING_UPDATE 重试
        if result is RemoteResult.MISSING:
            return LocalOp(new_status=PENDING)  # 远端事件没了 → 回推重建
        return LocalOp(delete=True)  # PERMANENT → 删跟踪

    if phase is Phase.DELETE:  # 起点 PENDING_DELETE
        if result in (RemoteResult.OK, RemoteResult.MISSING):
            return LocalOp(delete=True)  # 已删/不存在都算完成
        return LocalOp()  # TRANSIENT/PERMANENT → 保持 PENDING_DELETE

    # PULL                                       # 起点 SUCCESS
    if result is RemoteResult.OK:
        return LocalOp(new_status=SUCCESS, patch_done=True)
    if result is RemoteResult.MISSING:
        return LocalOp(new_status=PENDING)  # 远端没了 → 重建
    return LocalOp()  # TRANSIENT → 保持 SUCCESS，下轮再拉


async def _apply_outcomes(
    session: AsyncSession,
    phase: Phase,
    outcomes: list[ItemOutcome],
    entries_by_id: dict[UUID, MeetscheduleEntry],
    homework_by_id: dict[UUID, Homework],
):
    """把一条条 outcome 经迁移表落到 session 里的 ORM 对象上。

    统一在 ``core.get_session()`` 退出时 commit；不在此处单独提交。
    """
    for oc in outcomes:
        op = _transition(phase, oc.result)
        entry = entries_by_id.get(oc.homework_id)
        if entry is None:
            continue
        if op.store_event_id and oc.event_id:
            entry.meet_event_id = oc.event_id
        if op.patch_done and oc.done is not None:
            h = homework_by_id.get(oc.homework_id)
            if h is not None:
                h.done = oc.done
        if op.delete:
            await session.delete(entry)
        elif op.new_status is not None and op.new_status is not entry.status:
            entry.status = op.new_status


# ── 5. 各阶段远程实现 ─────────────────────────────────────────────────────


async def _push_user(
    meet: AsyncMeetSchedule,
    config: MeetscheduleConfig,
    group: list[MeetscheduleEntry],
    homework_by_id: dict[UUID, Homework],
) -> list[ItemOutcome]:
    """推送（起点 PENDING）：为尚未镜像的作业在 Meet 上创建事件。"""
    async with limiter.acquire(meet):
        courses = await meet.courses.get_all(config.schedule_id)
    course_id_by_name = {c.name: c.id for c in courses}

    bundle: list[tuple[UUID, EventInput]] = []
    outcomes: list[ItemOutcome] = []
    for e in group:
        h = homework_by_id.get(e.id)
        if h is None or h.deadline is None:
            # 作业已不存在 / 无截止时间（构造不出 due_only 事件）→ 无法镜像，删跟踪。
            outcomes.append(ItemOutcome(e.id, RemoteResult.PERMANENT))
            continue
        bundle.append(
            (
                e.id,
                EventInput(
                    schedule_id=config.schedule_id,
                    type=EventType.HOMEWORK,
                    title=h.title,
                    time_mode=TimeMode.DUE_ONLY,
                    end_at=h.deadline.isoformat(),
                    linked_course_id=course_id_by_name.get(h.course_name),
                    note=h.platform,
                    done=h.done,
                ),
            )
        )

    for batch in batched(bundle, 100):
        outcomes += await _push_batch(meet, config.schedule_id, batch)
    return outcomes


async def _push_batch(
    meet: AsyncMeetSchedule, schedule_id: str, batch: Sequence[tuple[UUID, EventInput]]
) -> list[ItemOutcome]:
    """批量创建；整批被拒（422/409）时降级为逐条创建，逐条区分成败。"""
    try:
        async with limiter.acquire(meet):
            events = await meet.events.create_batch(
                schedule_id, [i for _, i in batch], allow_duplicate_title=True
            )
    except (UnprocessableEntityError, ConflictError) as exc:
        _logger.debug("批量创建触发%s，降级为逐条创建", type(exc).__name__)
        return await _push_singly(meet, batch)
    except UnauthorizedError, ForbiddenError:
        raise
    except Exception as exc:
        _logger.error("批量创建作业时发生异常", exc_info=exc)
        return [ItemOutcome(hid, RemoteResult.TRANSIENT) for hid, _ in batch]

    if len(events) != len(batch):
        # 响应数量与请求不一致：状态不可信，保守整批重试，避免重复创建。
        _logger.error(
            "批量创建响应数量不一致：%s != %s，整批标记重试", len(events), len(batch)
        )
        return [ItemOutcome(hid, RemoteResult.TRANSIENT) for hid, _ in batch]

    return [
        ItemOutcome(hid, RemoteResult.OK, event_id=ev.id)
        for (hid, _), ev in zip(batch, events, strict=True)
    ]


async def _push_singly(
    meet: AsyncMeetSchedule, batch: Iterable[tuple[UUID, EventInput]]
) -> list[ItemOutcome]:
    """逐条创建：422/409=永久失败，其余异常=临时失败。"""
    outcomes: list[ItemOutcome] = []
    for hid, ev_input in batch:
        async with limiter.acquire(meet):
            try:
                ev = await meet.events.create(ev_input, allow_duplicate_title=True)
            except (UnprocessableEntityError, ConflictError) as exc:
                _logger.warning("创建作业%s永久失败: %s", hid, exc)
                outcomes.append(ItemOutcome(hid, RemoteResult.PERMANENT))
                continue
            except UnauthorizedError, ForbiddenError:
                raise
            except Exception as exc:
                _logger.error("创建作业%s发生异常", hid, exc_info=exc)
                outcomes.append(ItemOutcome(hid, RemoteResult.TRANSIENT))
                continue
        outcomes.append(ItemOutcome(hid, RemoteResult.OK, event_id=ev.id))
    return outcomes


async def _update_user(
    meet: AsyncMeetSchedule,
    config: MeetscheduleConfig,
    group: list[MeetscheduleEntry],
    homework_by_id: dict[UUID, Homework],
) -> list[ItemOutcome]:
    """更新（起点 PENDING_UPDATE）：把本地 done 推到已镜像的远端事件。"""
    outcomes: list[ItemOutcome] = []
    for e in group:
        h = homework_by_id.get(e.id)
        if h is None:
            outcomes.append(ItemOutcome(e.id, RemoteResult.PERMANENT))
            continue
        if e.meet_event_id is None:
            # 本地没有远端事件 id → 无镜像可同步 → 回推重建（走 push）。
            outcomes.append(ItemOutcome(e.id, RemoteResult.MISSING))
            continue
        async with limiter.acquire(meet):
            try:
                await meet.events.update(e.meet_event_id, EventPatch(done=h.done))
            except NotFoundError as exc:
                _logger.warning("更新作业%s：远端事件已不存在", e.id, exc_info=exc)
                outcomes.append(ItemOutcome(e.id, RemoteResult.MISSING))
                continue
            except UnauthorizedError, ForbiddenError:
                raise
            except Exception as exc:
                _logger.error("更新作业%s发生异常", e.id, exc_info=exc)
                outcomes.append(ItemOutcome(e.id, RemoteResult.TRANSIENT))
                continue
        outcomes.append(ItemOutcome(e.id, RemoteResult.OK))
    return outcomes


async def _delete_user(
    meet: AsyncMeetSchedule,
    config: MeetscheduleConfig,
    group: list[MeetscheduleEntry],
    homework_by_id: dict[UUID, Homework],
) -> list[ItemOutcome]:
    """删除（起点 PENDING_DELETE）：删远端事件，随后删本地跟踪行。"""
    outcomes: list[ItemOutcome] = []
    for batch in batched(group, 100):
        event_ids = [e.meet_event_id for e in batch if e.meet_event_id]
        idless = [e for e in batch if not e.meet_event_id]
        # 本地没有远端 id 的条目无需远端删除，直接删本地行。
        outcomes += [ItemOutcome(e.id, RemoteResult.OK) for e in idless]
        if not event_ids:
            continue
        async with limiter.acquire(meet):
            try:
                await meet.events.delete_batch(event_ids)
            except UnauthorizedError, ForbiddenError:
                raise
            except Exception as exc:
                _logger.error("删除作业发生异常", exc_info=exc)
                outcomes += [
                    ItemOutcome(e.id, RemoteResult.TRANSIENT)
                    for e in batch
                    if e.meet_event_id
                ]
                continue
        # delete_batch 对"不存在的 id"只返回 not_found_ids，不视为失败 → 全部算完成。
        outcomes += [
            ItemOutcome(e.id, RemoteResult.OK) for e in batch if e.meet_event_id
        ]
    return outcomes


async def _pull_user(
    meet: AsyncMeetSchedule,
    config: MeetscheduleConfig,
    group: list[MeetscheduleEntry],
    homework_by_id: dict[UUID, Homework],
) -> list[ItemOutcome]:
    """回拉（起点 SUCCESS）：把远端真实 done 回写本地 homework。

    本地作业已不存在的 SUCCESS 条目属于"悬挂镜像"：其远端事件也应一并清除，
    故置为 PENDING_DELETE，交给删除阶段删远端事件并清理本地跟踪。
    """
    outcomes: list[ItemOutcome] = []

    # 本地作业不存在 → 置 PENDING_DELETE。这是"本地前置条件"而非远端结果，
    # 不强行塞进 RemoteResult 词汇表；与 _run_user 里对"无配置"条目的直接清理同理。
    dangling = [e for e in group if e.id not in homework_by_id]
    for e in dangling:
        _logger.warning(
            "回拉作业%s：本地作业已不存在，置 PENDING_DELETE 以清理远端镜像", e.id
        )
        e.status = PENDING_DELETE

    # 仅回拉"本地作业仍存在"的条目。
    for batch in batched((e for e in group if e.id in homework_by_id), 100):
        valid = [(e.id, e.meet_event_id) for e in batch if e.meet_event_id]
        if not valid:
            # 有本地作业但无远端 id → 从未成功镜像，回归 PENDING 重建。
            continue
        try:
            async with limiter.acquire(meet):
                events = await meet.events.get_by_ids([evid for _, evid in valid])
        except UnauthorizedError, ForbiddenError:
            raise
        except Exception as exc:
            _logger.error("回拉作业时发生异常", exc_info=exc)
            outcomes += [ItemOutcome(e.id, RemoteResult.TRANSIENT) for e in batch]
            continue
        event_by_id = {ev.id: ev for ev in events}
        for eid, evid in valid:
            ev = event_by_id.get(evid)
            if ev is None:
                # 远端事件已不存在 → 回退到推送重建。
                _logger.warning("回拉作业%s：远端事件%s已不存在", eid, evid)
                outcomes.append(ItemOutcome(eid, RemoteResult.MISSING))
                continue
            h = homework_by_id[eid]  # 必在（外层已按本地作业存在过滤）
            if ev.done != h.done:
                outcomes.append(ItemOutcome(eid, RemoteResult.OK, done=ev.done))
            else:
                outcomes.append(ItemOutcome(eid, RemoteResult.OK))
    return outcomes


# 阶段 → 远程实现 的注册表。运行期（_run_phase）才会取值，定义在此处安全。
_PHASE_RUNNERS: dict[Phase, Callable] = {
    Phase.PUSH: _push_user,
    Phase.UPDATE: _update_user,
    Phase.DELETE: _delete_user,
    Phase.PULL: _pull_user,
}


# ── 6. 通用小工具 ─────────────────────────────────────────────────────────


@asynccontextmanager
async def _log_and_suppress(
    exc: type[BaseException] = Exception, info: str = "发生异常", *info_args
):
    try:
        yield
    except exc as e:
        _logger.error(info, *info_args, exc_info=e)


# ── 7. 调度对象与生命周期 ────────────────────────────────────────────────


scheduler = AsyncIOScheduler()
scheduler.add_job(
    _job,
    IntervalTrigger(seconds=core.config.meetschedule_sync_interval),
)


def start_refresh():
    scheduler.start()


def shutdown_refresh():
    scheduler.shutdown()
