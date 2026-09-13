"""部署判定与表现追踪合同（kernel 判策第四层:谁上场、连败怎么看）。

被测模块:``kernel/cw_deploy_logic.py``(部署围栏纯函数——发射方与执行方
共用同一份语义,禁第二套)、``kernel/cw_performance.py``(观测反馈)。

合同面(从源码推导,断言经行为探针校准):
- §1 has_deployable 单一源谓词(发射×执行契约;bench=1 合法稳态的
  空计划防环语义);
- §2 围栏辅助纯函数(cap 余量/阵容档完成);
- §3 表现追踪(掉血趋势/连败判定的空态与成立态)。

边界挂账(不锁,待源码重推):``is_run_dead`` 死路判定的完整真值表
(需 next_node_type+tracker 状态组合,初探 40 血+连败仍 False,
边界条件未摸全);SIFT 未识别 fail-open 的辖场(满席无协同场景实测
False,与 docstring「恒 True」口径出入,疑 fail-open 辖非满席)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    cap_roomy_of,
    has_deployable,
    tier_completes,
)
from sr_od.application.currency_war.kernel.cw_performance import (
    PerformanceTracker,
    RoundOutcome,
)
from sr_od.application.currency_war.kernel.cw_vocab import BenchChar


def _bc(cid: str, fac: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=cid, faction=fac, star=star)


# ============================================================ §1 单一源谓词

def test_has_deployable_empty_seat_with_stock() -> None:
    """有空席 ∧ bench 有货 → 可部署(发射方据此发射 RunDeploy)。"""
    bench = [_bc('希儿', '仙舟')]
    assert has_deployable(bench, set(), {}, {}, 6) is True


def test_has_deployable_full_seat_no_synergy_false() -> None:
    """满席 ∧ bench 件无目标协同/围栏放行理由 → False(bench=1 是
    合法稳态,发射方不发射空计划——run 20260904 局 11 零推进环防复发)。"""
    assert has_deployable([], {'a', 'b', 'c', 'd', 'e', 'f'},
                          {'仙舟': 6}, {'仙舟': 6}, 6) is False


def test_has_deployable_symmetric_with_reasoned() -> None:
    """发射×执行契约:has_deployable == has_deployable_reasoned 判空半
    (单一源同函数路径,禁第二套围栏语义)。"""
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        has_deployable_reasoned,
    )
    bench = [_bc('希儿', '仙舟')]
    args = (bench, set(), {}, {}, 6)
    assert has_deployable(*args) == has_deployable_reasoned(*args)[0]


# ============================================================ §2 围栏辅助

def test_cap_roomy_boundary() -> None:
    """cap 余量:前空+后空 ≥ 必上场数 = roomy(边界取等成立)。"""
    assert cap_roomy_of(2, 2, 3) is True
    assert cap_roomy_of(2, 2, 4) is False, '边界:恰好相等才 roomy'


def test_tier_completes_counts_bond_threshold() -> None:
    """阵容档完成数:同阵营在场人数过档 → 完成档数(仙舟 2 命 = 1 档)。"""
    assert tier_completes(['仙舟'], {'仙舟': 2, '联盟': 1}) == 1
    assert tier_completes(['仙舟'], {'联盟': 2}) == 0


# ============================================================ §3 表现追踪

def test_tracker_empty_state_honest_none() -> None:
    """空追踪器:趋势 = None(诚实缺失,非 0),连败 = False。"""
    t = PerformanceTracker()
    assert t.recent_hp_loss_trend() is None
    assert t.is_losing_streak() is False


def test_tracker_loss_trend_and_streak() -> None:
    """连败形态:三连败掉血 10/20/30 → 趋势 +25/轮(上行=恶化),
    连败判定 True;单胜样不存在该形态。"""
    t = PerformanceTracker()
    t.record(RoundOutcome(round_num=1, plane=1, node_type='battle',
                          comp_tag='', hp_after=90, match_result='win'))
    t.record(RoundOutcome(round_num=2, plane=1, node_type='battle',
                          comp_tag='', hp_after=70, match_result='loss'))
    t.record(RoundOutcome(round_num=3, plane=1, node_type='battle',
                          comp_tag='', hp_after=40, match_result='loss'))
    assert t.recent_hp_loss_trend() == 25.0
    assert t.is_losing_streak() is True


def test_tracker_healthy_streak_negative_case() -> None:
    """健康形态(连胜/低掉血) → 连败 False(窗口语义对照)。"""
    t = PerformanceTracker()
    t.record(RoundOutcome(round_num=1, plane=1, node_type='battle',
                          comp_tag='', hp_after=95, match_result='win'))
    assert t.is_losing_streak() is False
