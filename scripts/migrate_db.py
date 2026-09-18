"""一次性数据迁移：把 homework 主键从旧规则改为新规则。

旧规则：``uuid5(NS, user_id + platform + course_name + title)``
新规则：``uuid5(NS, user_id + platform + platform_custom)``
        其中 platform_custom 由各平台给出（学习通 ``key``、学在重邮 ``item["id"]``、
        雨课堂 ``str(item["id"])``）。

做法（见 AGENTS.md §4）：对每个 (user, platform) 拉一次作业，按新旧两套规则各算一次
主键，把库里命中的旧主键**原地改名**为新主键，并同步改 meetscheduleentry.id；
本次没拉到的作业直接删掉。不做任何远端 Meet API 调用。

保证：
- **不插入**任何 homework 行（因此 homework 行数 = 迁移前 - 删除数 是可校验的不变量）；
- meetscheduleentry 行数迁移前后不变（只改 id 和 status）；
- 每个 (user, platform) 一个事务；接口异常时整段跳过，不碰数据库；
- 可重复执行（已迁移的作业会命中"已是最新"分支）。

用法（**必须在容器内跑**，宿主机 .env 指向 sqlite）：

    python /migrate_db.py --dry-run            # 只看配对结果，不写库
    python /migrate_db.py --yes                # 正式执行

stdout 是 JSONL（每 (user, platform) 一行 + 最后一行 summary），日志走 stderr。
"""

import argparse
import asyncio
import json
import logging
import re
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.model.db import Homework, PlatformInfo, User
from cquptddl.model.db.homework import UUID_NAMESPACE_HOMEWORK_ID
from cquptddl.model.db.meetschedule_tracked_event import (
    MeetscheduleEntry,
    MeetscheduleEntryStatus,
)
from cquptddl.model.schema.platform import PlatformEnum
from cquptddl.service.platform.fetch import fetch_homework

_logger = logging.getLogger("migrate_db")
_logger.setLevel(logging.INFO)

_TIMEOUT_PATCHED = False


# ── 工具 ─────────────────────────────────────────────────────────────────


def _h32(value: UUID) -> str:
    """统一成 MySQL CHAR(32) 的表示：无连字符小写。"""
    return value.hex


def _legacy_id(uid: str, platform: PlatformEnum, course_name: str, title: str) -> UUID:
    """旧规则主键。迁移专用，不要在生产代码里使用。"""
    return uuid.uuid5(
        UUID_NAMESPACE_HOMEWORK_ID, uid + platform.value + course_name + title
    )


def _mask_db_url(url: str) -> str:
    return re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", url)


def _url_key(platform: PlatformEnum, url: str | None) -> str | None:
    """把作业链接归一化成跨时间稳定的配对键。

    不能直接用整条 url：学习通的 url 带 ``enc=`` 签名参数，会轮换。
    解析失败返回 None（表示这条行失去 url 兜底，只能靠主键法配对）。
    """
    from urllib.parse import parse_qs, urlparse

    if not url:
        return None
    try:
        parsed = urlparse(url)
        if platform is PlatformEnum.CHAOXING:
            # .../intoexamorwork?taskrefId=..&courseId=..&classId=..&enc=..
            # 实测 key == f"{taskrefId}-{classId}"
            query = parse_qs(parsed.query)
            return f"chaoxing:{query['taskrefId'][0]}-{query['classId'][0]}"
        if platform is PlatformEnum.XZCY:
            # http://lms.tc.cqupt.edu.cn/course/{course_id}/learning-activity#/{hmw_id}?view=scores
            course_id = parsed.path.rstrip("/").rsplit("/", 1)[-1]
            hmw_id = parsed.fragment.lstrip("/").split("?", 1)[0]
            return f"xzcy:{course_id}:{hmw_id}"
        if platform is PlatformEnum.YUKETANG:
            # https://changjiang.yuketang.cn/v2/web/exam/{classroom_id}/{hmw_id}
            parts = parsed.path.strip("/").split("/")
            if len(parts) < 2:
                return None
            return f"yuketang:{parts[-2]}:{parts[-1]}"
    except Exception:  # noqa: BLE001
        return None
    return None


def _install_timeout_patch(timeout: float) -> None:
    """给平台代码用的 httpx client 注入更长的超时。

    平台实现一律在**调用时**通过 ``core.factory.get_client(...)`` 取 client
    （``core.factory`` 是模块对象，属性是调用时查找），所以替换这个属性对
    chaoxing / xzcy / yuketang / platform.auth 同时生效。

    httpx 默认超时只有 5 秒，对校园 LMS 偏短；假超时会让整个 (user, platform)
    被跳过，从而留下一批未迁移的旧主键行。

    注意：CQUPT_IDS 平台的 relogin 走 fuckids 自带的 client，不受此 patch 影响。
    """
    global _TIMEOUT_PATCHED
    if _TIMEOUT_PATCHED:
        return

    original = core.factory.get_client

    @asynccontextmanager
    async def patched(**kw):
        kw.setdefault("timeout", timeout)
        async with original(**kw) as client:
            yield client

    core.factory.get_client = patched
    _TIMEOUT_PATCHED = True


def _emit(record: dict, report: Path | None = None) -> None:
    line = json.dumps(record, ensure_ascii=False)
    print(line, flush=True)
    if report is not None:
        with report.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


# ── 配对 ─────────────────────────────────────────────────────────────────


async def _plan(session: AsyncSession, uid: str, platform: PlatformEnum) -> dict:
    """拉一次作业并算出改名 / 删除两组动作。只读，不写库。"""
    user = await session.get_one(User, uid)
    items = list(await fetch_homework(session, user, platform, check_cooldown=False))

    rows: dict[UUID, str | None] = {}
    stmt = (
        select(Homework)
        .where(Homework.user_id == uid)  # ty: ignore[invalid-argument-type]
        .where(Homework.platform == platform)  # ty: ignore[invalid-argument-type]
    )
    for homework in (await session.execute(stmt)).scalars():
        rows[homework.id] = homework.url

    new_ids = {item.id for item in items}
    key_to_rows: dict[str, list[UUID]] = defaultdict(list)
    for homework_id, url in rows.items():
        key = _url_key(platform, url)
        if key is not None:
            key_to_rows[key].append(homework_id)
    # 同一个 url 键命中多行 = 旧规则碰撞留下的重复行（一条旧主键 + 一条新主键）。
    # 这是预期现象（迁移会把旧主键那条删掉），所以只汇总计数，不逐条刷屏。
    duplicated_keys = {k: v for k, v in key_to_rows.items() if len(v) > 1}
    if duplicated_keys:
        _logger.info(
            "用户%s 平台%s 有 %s 组 url 重复行（旧规则碰撞的残留），示例 %s",
            uid,
            platform.value,
            len(duplicated_keys),
            [_h32(c) for c in next(iter(duplicated_keys.values()))],
        )

    pairs: dict[UUID, UUID] = {}
    consumed: set[UUID] = set()
    already: list[UUID] = []
    collisions: list[UUID] = []
    unmatched: list[UUID] = []
    url_fallback = 0

    for item in items:
        legacy = _legacy_id(uid, platform, item.course_name, item.title)
        has_legacy = legacy in rows and legacy not in consumed
        has_new = item.id in rows

        # 撞主键（理论上只有哈希碰撞）：删旧行，不合并 done（用户已确认）
        if has_legacy and has_new:
            collisions.append(legacy)
            consumed.add(legacy)
            already.append(item.id)
            continue
        if has_legacy:
            pairs[legacy] = item.id
            consumed.add(legacy)
            continue
        # 已经是最新主键（重跑时全部命中这里，这是幂等性的来源）
        if has_new:
            already.append(item.id)
            consumed.add(item.id)
            continue
        # url 兜底：作业被老师改过名时主键法会配不上
        key = _url_key(platform, item.url)
        hit = None
        if key is not None:
            for candidate in key_to_rows.get(key, ()):
                if candidate not in consumed:
                    hit = candidate
                    break
        if hit is not None:
            pairs[hit] = item.id
            consumed.add(hit)
            url_fallback += 1
            continue
        # 新作业，或旧规则碰撞的败者：不处理，交给上线后的一次 refresh
        # （它会插入并 emit HomeworkRefreshedEvent，从而正常建 entry + 推送）
        unmatched.append(item.id)

    # 防御：万一两条不同旧行配到同一个新主键，只保留第一条
    seen_new: set[UUID] = set()
    for old in list(pairs):
        new = pairs[old]
        if new in seen_new:
            _logger.error("新主键 %s 被多行争用，放弃旧行 %s", _h32(new), _h32(old))
            del pairs[old]
            continue
        seen_new.add(new)

    to_delete = [hid for hid in rows if hid not in new_ids and hid not in pairs]

    return {
        "pairs": pairs,
        "to_delete": to_delete,
        "already": already,
        "collisions": collisions,
        "unmatched": unmatched,
        "url_fallback": url_fallback,
        "rows": len(rows),
        "items": len(items),
    }


async def _apply(session: AsyncSession, plan: dict) -> None:
    """改名 + 删除。顺序固定：先子表 meetscheduleentry，再父表 homework。"""
    for old, new in plan["pairs"].items():
        await session.execute(
            update(MeetscheduleEntry)
            .where(MeetscheduleEntry.id == old)  # ty: ignore[invalid-argument-type]
            .values(id=new)
        )
        await session.execute(
            update(Homework)
            .where(Homework.id == old)  # ty: ignore[invalid-argument-type]
            .values(id=new)
        )

    to_delete: list[UUID] = plan["to_delete"]
    if not to_delete:
        return
    # 不直接删 entry：置成 pending-delete，交给新代码的 DELETE 阶段
    # （refresh_task._delete_user）去删远端 Meet 事件 + 本地行。
    # 这样迁移脚本完全不碰 Meet API，也堵住了 PENDING_UPDATE 条目被判
    # PERMANENT 时"只删本地、留下日历孤儿事件"的那条路径。
    await session.execute(
        update(MeetscheduleEntry)
        .where(MeetscheduleEntry.id.in_(to_delete))  # ty: ignore[unresolved-attribute]
        .values(status=MeetscheduleEntryStatus.PENDING_DELETE)
    )
    await session.execute(
        delete(Homework).where(Homework.id.in_(to_delete))  # ty: ignore[unresolved-attribute]
    )


async def _migrate_one(uid: str, platform: PlatformEnum, dry_run: bool) -> dict:
    record: dict = {
        "uid": uid,
        "platform": platform.value,
        "dry_run": dry_run,
        "status": "ok",
        "error": None,
        "renamed": [],
        "deleted": [],
        "collisions": [],
        "unmatched": [],
        "already": 0,
        "url_fallback": 0,
        "rows": 0,
        "items": 0,
    }
    try:
        async with core.get_session() as session:
            plan = await _plan(session, uid, platform)
            if not dry_run:
                await _apply(session, plan)
            else:
                # dry-run 保证零写入：relogin 可能刷新过 PlatformInfo.cookies，
                # 这里回滚掉（随后 depends_session 的 commit 在干净会话上是空操作）。
                await session.rollback()
    except Exception as e:  # noqa: BLE001
        record["status"] = "skipped"
        record["error"] = f"{type(e).__name__}: {e}"
        _logger.warning(
            "用户%s 平台%s 迁移跳过：%s", uid, platform.value, record["error"]
        )
        return record

    record.update(
        renamed=[[_h32(o), _h32(n)] for o, n in plan["pairs"].items()],
        deleted=[_h32(i) for i in plan["to_delete"]],
        collisions=[_h32(i) for i in plan["collisions"]],
        unmatched=[_h32(i) for i in plan["unmatched"]],
        already=len(plan["already"]),
        url_fallback=plan["url_fallback"],
        rows=plan["rows"],
        items=plan["items"],
    )
    _logger.info(
        "用户%s 平台%s：%s 行 / %s 作业 → 改名%s 删除%s 已最新%s 未匹配%s url兜底%s",
        uid,
        platform.value,
        record["rows"],
        record["items"],
        len(record["renamed"]),
        len(record["deleted"]),
        record["already"],
        len(record["unmatched"]),
        record["url_fallback"],
    )
    return record


# ── 编排 ─────────────────────────────────────────────────────────────────


async def _counts(session: AsyncSession) -> dict:
    return {
        "homework": (
            await session.execute(select(func.count()).select_from(Homework))
        ).scalar_one(),
        "meetscheduleentry": (
            await session.execute(select(func.count()).select_from(MeetscheduleEntry))
        ).scalar_one(),
    }


async def _collect_targets(
    session: AsyncSession, only_user: str | None, limit: int | None
) -> list[tuple[str, PlatformEnum]]:
    stmt = select(PlatformInfo).order_by(PlatformInfo.user_id, PlatformInfo.platform)
    if only_user:
        stmt = stmt.where(PlatformInfo.user_id == only_user)  # ty: ignore[invalid-argument-type]
    infos = (await session.execute(stmt)).scalars().all()
    targets = [(info.user_id, PlatformEnum(info.platform)) for info in infos]
    if limit is not None:
        targets = targets[:limit]
    return targets


async def _orphan_entries(session: AsyncSession) -> int:
    """作业已不存在、但状态不是 pending-delete 的 entry 数。期望 0。

    这是本次迁移最重要的自检：任何这种 entry 都会变成用户 Meet 日历里
    删不掉的孤儿事件。
    """
    stmt = (
        select(func.count())
        .select_from(MeetscheduleEntry)
        .outerjoin(Homework, MeetscheduleEntry.id == Homework.id)  # ty: ignore[invalid-argument-type]
        .where(Homework.id.is_(None))  # ty: ignore[unresolved-attribute]
        # 期望 0：非 pending-delete 的孤儿 entry = 用户日历里删不掉的事件
        .where(
            MeetscheduleEntry.status != MeetscheduleEntryStatus.PENDING_DELETE  # ty: ignore[invalid-argument-type]
        )
    )
    return (await session.execute(stmt)).scalar_one()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="作业主键一次性迁移")
    parser.add_argument(
        "--dry-run", action="store_true", help="只配对不写库（dry-run 不需要 --yes）"
    )
    parser.add_argument("--yes", action="store_true", help="确认执行写操作")
    parser.add_argument("--timeout", type=float, default=30.0, help="平台接口超时秒数")
    parser.add_argument("--only-user", default=None, help="只处理指定统一认证码")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 个目标")
    parser.add_argument(
        "--report", type=Path, default=None, help="同时把 JSONL 追加到该文件"
    )
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    if not args.dry_run and not args.yes:
        _logger.error("写操作需要 --yes（dry-run 用 --dry-run）")
        return 2

    _install_timeout_patch(args.timeout)
    # 我们不调用 service.init()，所以要手动补上它在非 DEBUG 下做的这件事：
    # 学习通的"未知收件箱"日志会把整条通知 JSON 打出来，迁移时是纯噪音
    # （而且会让解析失败变得完全无声，与生产行为一致）。
    logging.getLogger(
        "cquptddl.service.platform.chaoxing:unknown-inbox"
    ).disabled = True
    _logger.info("目标数据库：%s", _mask_db_url(core.config.DATABASE_URL))
    _logger.info(
        "模式：%s | 平台超时：%ss", "dry-run" if args.dry_run else "写", args.timeout
    )
    _logger.info("开始时间：%s", datetime.now().isoformat(timespec="seconds"))  # noqa: DTZ005

    async with core.get_session() as session:
        before = await _counts(session)
        targets = await _collect_targets(session, args.only_user, args.limit)
        orphans_before = await _orphan_entries(session)
    _logger.info("迁移前：%s，待处理目标 %s 个", before, len(targets))
    if orphans_before:
        _logger.warning(
            "迁移前就存在 %s 条非 pending-delete 的孤儿 entry", orphans_before
        )

    records = []
    for uid, platform in targets:
        record = await _migrate_one(uid, platform, args.dry_run)
        records.append(record)
        _emit(record, args.report)

    async with core.get_session() as session:
        after = await _counts(session)
        orphans_after = await _orphan_entries(session)

    rename_map: dict[str, str] = {}
    deleted: list[str] = []
    collisions: list[str] = []
    unmatched: list[str] = []
    skipped = []
    for record in records:
        for old, new in record["renamed"]:
            rename_map[old] = new
        deleted.extend(record["deleted"])
        collisions.extend(record["collisions"])
        unmatched.extend(record["unmatched"])
        if record["status"] != "ok":
            skipped.append(
                {
                    "uid": record["uid"],
                    "platform": record["platform"],
                    "error": record["error"],
                }
            )

    summary = {
        "__summary__": True,
        "dry_run": args.dry_run,
        "map": rename_map,
        "deleted": deleted,
        "collisions": collisions,
        "unmatched": unmatched,
        "skipped": skipped,
        "counts": {"before": before, "after": after},
        "orphan_entries_not_pending_delete": orphans_after,
    }
    _emit(summary, args.report)

    _logger.info(
        "迁移%s：homework %s→%s（删除%s），meetscheduleentry %s→%s，"
        "改名%s 碰撞%s 未匹配%s 跳过%s 孤儿entry%s",
        "演练完成" if args.dry_run else "完成",
        before["homework"],
        after["homework"],
        len(deleted),
        before["meetscheduleentry"],
        after["meetscheduleentry"],
        len(rename_map),
        len(collisions),
        len(unmatched),
        len(skipped),
        orphans_after,
    )

    if not args.dry_run:
        expected = before["homework"] - len(deleted)
        if after["homework"] != expected:
            _logger.error(
                "不变量失败：homework 行数 %s != 迁移前 %s - 删除 %s = %s",
                after["homework"],
                before["homework"],
                len(deleted),
                expected,
            )
            return 1
        if after["meetscheduleentry"] != before["meetscheduleentry"]:
            _logger.error(
                "不变量失败：meetscheduleentry 行数 %s→%s 发生变化",
                before["meetscheduleentry"],
                after["meetscheduleentry"],
            )
            return 1
        if orphans_after > orphans_before:
            _logger.error(
                "不变量失败：非 pending-delete 的孤儿 entry 从 %s 涨到 %s "
                "（说明有作业被删但 entry 没置 pending-delete）",
                orphans_before,
                orphans_after,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
