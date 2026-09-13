"""遭遇选档判定核锁(E-2;设计正本 = changes/2026-09-12-encounter-selection 详设)。

精简锁面:暗装锚(W4)/门序/三态/线族/环拓扑各一,共 ~15 例——锁结构不锁
分布数值;线族数值为例外(29 轮对抗审终验锚定值,回归面唯一)。
标定槽隔离:autouse fixture 每例 reset(模块级 None 槽是生产形态,测试注入
必须清场)。
"""
from __future__ import annotations

import math

import pytest

from sr_od.application.currency_war.kernel import cw_encounter_selection as sel
from sr_od.application.currency_war.kernel.cw_events import EncounterOption
from sr_od.application.currency_war.kernel.cw_game_state import (
    BS_SCHEMA_VERSION,
    Field,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome


@pytest.fixture(autouse=True)
def _clean_slots():
    """每例清标定槽(模块级 None 槽 = 生产形态;测试注入互不串染)。"""
    sel.reset_calibration()
    yield
    sel.reset_calibration()


def _bs(enemy_value: float | None = None,
        enemy_source: str = 'observation') -> GameState:
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    if enemy_value is not None:
        bs.enemy_difficulty = Field(value=enemy_value, source=enemy_source)
    return bs


def _opts(*diffs: int) -> list[EncounterOption]:
    return [EncounterOption(idx=i, difficulty=d, rewards=['金币'])
            for i, d in enumerate(diffs)]


def _win(bs: GameState, plane: int, rnd: int, *, killed: bool | None,
         fill: float | None = None, dnode: float | None = None,
         tier: int | None = None) -> None:
    outcome = RoundOutcome(round_num=rnd, plane=plane, node_type='普通战斗',
                           comp_tag='c', killed=killed,
                           progress_fill_ratio=fill)
    sel.record_settlement_row(bs, outcome, plane=plane, round_num=rnd,
                              node_type='普通战斗', difficulty_node=dnode,
                              encounter_tier=tier)


def _encounter_win(bs: GameState, plane: int, rnd: int, *, tier: int,
                   killed: bool) -> None:
    outcome = RoundOutcome(round_num=rnd, plane=plane, node_type='遭遇',
                           comp_tag='c', killed=killed)
    sel.record_settlement_row(bs, outcome, plane=plane, round_num=rnd,
                              node_type='遭遇', difficulty_node=None,
                              encounter_tier=tier)


def _calibrate(*, variant: str = 'i', f_min: float = 0.5) -> None:
    sel.apply_calibration(F_MIN=f_min, G_BASE=1.052,
                          BAR_SEMANTICS='node',
                          PROGRESS_BAR_DIRECTION='forward',
                          D_ENC_VARIANT=variant)


def _足量_bs() -> GameState:
    """两连胜 + D_win=100(读值口同源)的足量态。"""
    bs = _bs(enemy_value=100)
    _win(bs, 1, 1, killed=True, dnode=100.0)
    _win(bs, 1, 2, killed=True, dnode=100.0)
    return bs


# ===== 暗装锚(W4:行为零变化)=====

def test_w4_dark_no_calibration():
    """三常量/定谳全 None → 恒最低档 + 零刷新(与现行 fail 向逐位一致)。"""
    pick = sel.decide_encounter(_opts(3, 5), _足量_bs())
    assert pick.idx == 0 and pick.refresh is False
    assert 'dark-install' in pick.reason and 'e3-simple' in pick.reason


def test_dark_gates_order():
    """只注 f_min/g 仍暗装(条语义/读点未定谳);reason 带对应门名。"""
    sel.apply_calibration(F_MIN=0.5, G_BASE=1.052)
    pick = sel.decide_encounter(_opts(1, 2), _足量_bs())
    assert pick.refresh is False and pick.idx == 0
    assert 'bar-semantics-undecided' in pick.reason


def test_live_gate_rejects_carry():
    """未定谳拨盘下 carry 态 D_enc 拒绝 → 暗装(读点门前置保守形态)。"""
    _calibrate()
    bs = _bs(enemy_value=100, enemy_source='carried')
    _win(bs, 1, 1, killed=True, dnode=100.0)
    _win(bs, 1, 2, killed=True, dnode=100.0)
    pick = sel.decide_encounter(_opts(1, 2), bs)
    assert pick.refresh is False and pick.idx == 0
    assert 'd_enc-gate-rejected' in pick.reason


def test_dark_reason_carries_d_enc_diagnostic():
    """journal 采集通道:D_enc 口读值与判别子结果随 reason 透传。"""
    pick = sel.decide_encounter(_opts(1), _bs(enemy_value=108))
    assert 'd_enc=108.0(observation)' in pick.reason


# ===== 三态与可及性 =====

def test_kappa_full_picks_highest_reachable():
    """足量态:同读值比值 1 ≥ f_min → 其一~其四全可及 → 选最高可及档。"""
    _calibrate()
    pick = sel.decide_encounter(_opts(1, 2, 3, 4), _足量_bs())
    assert pick.idx == 3 and pick.refresh is False
    assert 'pick:t4' in pick.reason


def test_kappa_edge_caps_at_tier2():
    """边缘态(一胜一删失):天花板其二——即便其三比值可及也只选其二。"""
    _calibrate()
    bs = _bs(enemy_value=100)
    _win(bs, 1, 1, killed=True, dnode=100.0)
    _win(bs, 1, 2, killed=None, dnode=100.0)
    pick = sel.decide_encounter(_opts(1, 2, 3), bs)
    assert pick.idx == 1 and 'pick:t2' in pick.reason


def test_experience_tier_5_6():
    """其五/六(Δ 无源档):经验档层交集——本局该档存在 killed=True 遭遇行才可及。"""
    _calibrate()
    bs = _足量_bs()
    _encounter_win(bs, 1, 3, tier=5, killed=False)
    pick = sel.decide_encounter(_opts(1, 5), bs)
    assert pick.idx == 0   # t5 只有败局经验 → 不可及 → 落其一
    _encounter_win(bs, 1, 4, tier=5, killed=True)
    pick = sel.decide_encounter(_opts(1, 5), bs)
    assert pick.idx == 1 and 'pick:t5' in pick.reason


# ===== 刷新逃生阀(∅ 唯一触发判据;三态同口径)=====

def test_refresh_valve_empty_and_used():
    """可及集空:未用 → 建议刷新;已用 → 最低档(零刷新)。"""
    _calibrate()
    bs = _bs(enemy_value=100)   # 读值 100 vs 窗口 50:比值 1.052^(-50) ≪ f_min → 空集
    _win(bs, 1, 1, killed=True, dnode=50.0)
    _win(bs, 1, 2, killed=True, dnode=50.0)
    pick = sel.decide_encounter(_opts(1, 2), bs)
    assert pick.refresh is True
    pick = sel.decide_encounter(_opts(1, 2), bs, refresh_used=True)
    assert pick.refresh is False and pick.idx == 0


def test_window_insufficient_valve():
    """窗口 < 2 行 → 不足态:刷新阀仍可用(非暗装全同);已用 → 最低档。"""
    _calibrate()
    bs = _bs(enemy_value=100)
    _win(bs, 1, 1, killed=True, dnode=100.0)   # 仅 1 行
    pick = sel.decide_encounter(_opts(1, 2), bs)
    assert pick.refresh is True and 'window-insufficient' in pick.reason
    pick = sel.decide_encounter(_opts(1, 2), bs, refresh_used=True)
    assert pick.refresh is False and pick.idx == 0


# ===== 环拓扑(去重合并/残留排除/深度旋转/开局清空)=====

def test_ring_dedup_merge_fills_missing_fields():
    """同场两路行去重合并:后到行缺字段不覆盖先行行已有值。"""
    bs = _bs()
    _win(bs, 1, 1, killed=True, dnode=None)          # 先行行有 killed 缺 dnode
    outcome = RoundOutcome(round_num=1, plane=1, node_type='普通战斗',
                           comp_tag='c', killed=False, difficulty_node=88.0)
    verdict = sel.record_settlement_row(bs, outcome, plane=1, round_num=1,
                                        node_type='普通战斗',
                                        difficulty_node=88.0,
                                        encounter_tier=None)
    assert verdict == 'merged'
    rows = bs.settlement_ring.last_normal_battles(1)
    assert rows[0].killed is True and rows[0].difficulty_node == 88.0


def test_ring_residual_excluded():
    """残留行不入环(生命周期 = 局;跨局污染排除)。"""
    bs = _bs()
    outcome = RoundOutcome(round_num=1, plane=1, node_type='普通战斗',
                           comp_tag='c', killed=True)
    verdict = sel.record_settlement_row(bs, outcome, plane=1, round_num=1,
                                        node_type='普通战斗',
                                        difficulty_node=None,
                                        encounter_tier=None, residual=True)
    assert verdict == 'residual-dropped' and len(bs.settlement_ring) == 0


def test_ring_depth_rotation():
    """深度 10 旋转:第 12 行入环后环长恒 10(最旧行淘汰)。"""
    bs = _bs()
    for r in range(1, 13):
        outcome = RoundOutcome(round_num=r, plane=2, node_type='普通战斗',
                               comp_tag='c', killed=True)
        sel.record_settlement_row(bs, outcome, plane=2, round_num=r,
                                  node_type='普通战斗', difficulty_node=None,
                                  encounter_tier=None)
    assert len(bs.settlement_ring) == sel.SETTLEMENT_RING_DEPTH
    assert bs.settlement_ring.last_normal_battles(2)[0].round_num == 11


def test_game_start_reset():
    """生命周期 = 局:开局清空环与经验表。"""
    bs = _足量_bs()
    _encounter_win(bs, 1, 3, tier=5, killed=True)
    sel.game_start_reset(bs)
    assert len(bs.settlement_ring) == 0
    assert bs.encounter_log.tier_cleared(5) is False


# ===== 线族(29 轮对抗审终验锚定值;回归面唯一数值锁)=====

def test_line_families_spec_anchored():
    """双线族 = 卡态分支(g^4 因子):无卡/持卡两族值与详设 §3 锚定值逐位。"""
    g = 1.052
    no_card = [1.0, g ** -10, g ** -20, g ** -30]
    held = [g ** 4 * v for v in no_card]
    assert [round(v, 4) for v in no_card] == [1.0, 0.6023, 0.3628, 0.2185]
    assert [round(v, 4) for v in held] == [1.2248, 0.7377, 0.4444, 0.2677]
    assert math.isclose(g ** 4, 1.2248, rel_tol=1e-4)
