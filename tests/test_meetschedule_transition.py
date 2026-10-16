"""``_transition`` 迁移真值表的行为规格。

PUSH / UPDATE / DELETE / PULL 四个阶段 × OK / MISSING / PERMANENT / TRANSIENT
四种远端结局 = 16 种组合，全部在这里钉死。

本文件只断言「远端结局 → 本地动作」这一层，不碰数据库、不碰 Meet SDK：
``_transition`` 是纯函数，给定 (Phase, RemoteResult) 就必须得到确定的 LocalOp。
同步规则若被改动，这里会先炸，而不是等线上同步错乱。
"""

import pytest

from cquptddl.service.meetschedule.refresh_task import (
    _PHASE_SOURCE_STATUS,
    PENDING,
    PENDING_DELETE,
    PENDING_UPDATE,
    SUCCESS,
    LocalOp,
    Phase,
    RemoteResult,
    _transition,
)

# (阶段, 远端结局, 期望动作)
TRUTH_TABLE = [
    # PUSH：起点 PENDING，为尚未镜像的作业新建远端事件
    (Phase.PUSH, RemoteResult.OK, LocalOp(new_status=SUCCESS, store_event_id=True)),
    (Phase.PUSH, RemoteResult.MISSING, LocalOp(delete=True)),
    (Phase.PUSH, RemoteResult.PERMANENT, LocalOp(delete=True)),
    (Phase.PUSH, RemoteResult.TRANSIENT, LocalOp()),
    # UPDATE：起点 PENDING_UPDATE，把本地 done 推到已镜像的事件
    (Phase.UPDATE, RemoteResult.OK, LocalOp(new_status=SUCCESS)),
    (Phase.UPDATE, RemoteResult.MISSING, LocalOp(new_status=PENDING)),
    (Phase.UPDATE, RemoteResult.PERMANENT, LocalOp(delete=True)),
    (Phase.UPDATE, RemoteResult.TRANSIENT, LocalOp()),
    # DELETE：起点 PENDING_DELETE，删远端事件并清理本地跟踪
    (Phase.DELETE, RemoteResult.OK, LocalOp(delete=True)),
    (Phase.DELETE, RemoteResult.MISSING, LocalOp(delete=True)),
    (Phase.DELETE, RemoteResult.PERMANENT, LocalOp()),
    (Phase.DELETE, RemoteResult.TRANSIENT, LocalOp()),
    # PULL：起点 SUCCESS，把远端真实 done 回写本地
    (Phase.PULL, RemoteResult.OK, LocalOp(new_status=SUCCESS, patch_done=True)),
    (Phase.PULL, RemoteResult.MISSING, LocalOp(new_status=PENDING)),
    (Phase.PULL, RemoteResult.PERMANENT, LocalOp()),
    (Phase.PULL, RemoteResult.TRANSIENT, LocalOp()),
]


@pytest.mark.parametrize(
    ("phase", "result", "expected"),
    TRUTH_TABLE,
    ids=[f"{p.value}-{r.value}" for p, r, _ in TRUTH_TABLE],
)
def test_transition_truth_table(phase: Phase, result: RemoteResult, expected: LocalOp):
    assert _transition(phase, result) == expected


def test_truth_table_covers_every_combination():
    """4 阶段 × 4 结局一条不漏；新增阶段或结局时这条会先报错"""
    covered = {(p, r) for p, r, _ in TRUTH_TABLE}
    assert covered == {(p, r) for p in Phase for r in RemoteResult}
    assert len(TRUTH_TABLE) == len(Phase) * len(RemoteResult)


def test_phase_source_status_is_one_to_one():
    """每个阶段只从唯一一个本地状态起步，且四个状态刚好用满、不重叠"""
    assert set(_PHASE_SOURCE_STATUS) == set(Phase)
    assert set(_PHASE_SOURCE_STATUS.values()) == {
        PENDING,
        PENDING_UPDATE,
        PENDING_DELETE,
        SUCCESS,
    }


@pytest.mark.parametrize("phase", list(Phase), ids=lambda p: p.value)
def test_transient_never_touches_local_state(phase: Phase):
    """临时失败（网络/限流）必须原样留着下轮重试：不删跟踪、不改状态、不回写"""
    assert _transition(phase, RemoteResult.TRANSIENT) == LocalOp()


@pytest.mark.parametrize("result", list(RemoteResult), ids=lambda r: r.value)
def test_pull_never_deletes_tracking(result: RemoteResult):
    """回拉只回写 done 或回退重建；删远端事件是 DELETE 阶段的职责"""
    assert _transition(Phase.PULL, result).delete is False


def test_push_success_must_store_remote_event_id():
    """PUSH 成功必须回填 meet_event_id，否则 UPDATE/DELETE 永远够不到远端事件"""
    assert _transition(Phase.PUSH, RemoteResult.OK).store_event_id is True


@pytest.mark.parametrize(
    "phase", [Phase.PUSH, Phase.UPDATE, Phase.DELETE], ids=lambda p: p.value
)
def test_only_pull_patches_done(phase: Phase):
    """done 只能由 PULL 回写；其余阶段成功也不许碰本地完成状态"""
    assert _transition(phase, RemoteResult.OK).patch_done is False


def test_default_local_op_is_keep_and_retry():
    """缺省动作 = 什么都不做（保持现状，等下一轮），字段默认值本身就是契约"""
    op = LocalOp()
    assert not op.delete
    assert op.new_status is None
    assert not op.store_event_id
    assert not op.patch_done
