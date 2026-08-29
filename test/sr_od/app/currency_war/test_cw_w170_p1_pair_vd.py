# -*- coding: utf-8 -*-
"""W170/ADR-0369 P1 体系对缺件找牌通道单帧锁(候选 b 落地)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 开窗正例:①锁局 level_plan 窗外帧(goal=level_up)pair 缺件账接管,
  分值 = jump(e_cur) − E₁×刷价 逐位对拍(E₁=当前等级刷 1 张缺件的期望
  刷新数,概率表原语本地复算);配方锁局(phase=unlocked, p1_pair 帧,
  core 恒空)同式;
- ② 金 50/51/52 拒([3] 预算前提=一次刷+买入后仍 ≥ 满息地板,P5⑤ 回归):
  51/52 金帧无一合格缺件对象 → None;
- ③ P1 无窗帧不刷:无对帧(pair 空)逐位回 W166;不缺件帧(对成员全
  持有)→ None;
- ④ A/B 通道:vd_p1_pair_enabled=False 逐位回 W166(窗外恒 None);
- ⑤ P2 逐位回归:同帧 plane=2 时 pair 通道不辖(P2 分支预算硬界语义
  不变);
- ⑥ roll/stable 窗内取大:core 与 pair 两本找件总账并存时取 max。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_economy import _resolve_level_goal
from sr_od.application.currency_war.cw_intention import IntentionState
from sr_od.application.currency_war.data.cw_shop_odds import (
    DISTINCT_CARDS_PER_COST,
    POOL_COPIES_PER_CARD,
    expected_refreshes,
    refresh_prob,
)
from sr_od.application.currency_war.cw_state import BenchChar, GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.ev import (
    cross_plane_remaining_nodes,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    _engines_formed,
    vd_refresh_score,
)
from sr_od.application.currency_war.cw_intention import _pair_members

_REG = DEFAULT_REGISTRY
_PAIR = ('仙舟', '列车同行')


def _locked_sess(pair=_PAIR) -> StrategySession:
    """①锁局形态:locked comp + transition_pair 副方向(W166 契约)。"""
    s = StrategySession()
    s.v3_intention = IntentionState(
        phase='locked', locked_comp='DOT队',
        transition_pair=tuple(pair))
    s.target_comp = get_comp('DOT队')
    s.v3_mode = 'economy'
    return s


def _unlocked_sess(pair=_PAIR) -> StrategySession:
    """配方锁局形态:phase=unlocked + p1_pair(W145 契约,core 恒空)。"""
    s = StrategySession()
    s.v3_intention = IntentionState(phase='unlocked',
                                    p1_pair=tuple(pair))
    return s


def _p1_state(level: int, gold: int, r: int, *,
              bench: list[BenchChar] | None = None) -> GameState:
    return GameState(
        plane=1, round_num=r, gold=gold, level=level, hp=80,
        shop_refresh_cost=2,
        deployed=[BenchChar(slot=9 + i, char_id=f'杂件{i}',
                            faction='公司', star=1)
                  for i in range(4)],
        bench=bench or [], shop=[], node_type='battle')


def _e1(level: int, cost: int) -> float:
    """E₁ 本地复算(概率表原语,禁从被测函数借值)。"""
    p = refresh_prob(level, cost)
    assert p > 0
    return expected_refreshes(
        p, DISTINCT_CARDS_PER_COST.get(cost, 13),
        POOL_COPIES_PER_CARD.get(cost, 9), 0, 1, 0)


def _jump(e_cur: int, st: GameState) -> float:
    """下一档引擎跳变金值本地复算(与 engine_jump_gold 同式,registry
    单一源;ADR-0424 起战斗项=条件掉血拟合×战斗数骨架缺省)。"""
    from sr_od.application.currency_war.decision_v2.scoring import (
        p1_battle_loss_est,
    )
    drung = _REG.rung_value.get(e_cur + 1, 0.0) - _REG.rung_value.get(e_cur, 0.0)
    dwin = (_REG.h3_win_rate.get(e_cur + 1, 0.0)
            - _REG.h3_win_rate.get(e_cur, 0.0))
    return (drung * cross_plane_remaining_nodes(st)
            + dwin * p1_battle_loss_est(st, _REG, rung=e_cur + 1)
            * _REG.hp_to_gold * _REG.battles_left_est)


# --- ① 开窗正例 -----------------------------------------------------------------


def test_qlock_window_frame_pair_account() -> None:
    """①①锁局窗外帧(DOT队 lv5=level_up,core 让位):pair 缺件账接管。
    金 53 → 合格缺件=1费档(阈值 50+2+1=53;2费档 54 不可负担),
    全部 1费缺件同 E → 分值逐位 = jump(e_cur) − E₁(5,1)×2。"""
    st = _p1_state(5, 53, 5)
    s = _locked_sess()
    # 前置:该帧 goal 确为 level_up(core 通道窗外让位,W154 ⑤ 同帧判据)
    goal = _resolve_level_goal(st, s.target_comp)
    assert goal is not None and goal.action == 'level_up'
    vd = vd_refresh_score(st, s, _REG)
    e_cur = _engines_formed(st, _REG)
    assert e_cur < 2, '前置:板面未成型'
    expected = _jump(e_cur, st) - _e1(5, 1) * 2
    assert vd is not None and vd > 0, vd
    assert abs(vd - expected) < 1e-6, (vd, expected)


def test_recipe_lock_p1_pair_frame_fires() -> None:
    """①配方锁局帧(phase=unlocked,p1_pair;core 恒空→旧版恒 None):
    pair 通道评估,金 53 lv4 → jump − E₁(4,1)×2 逐位。"""
    st = _p1_state(4, 53, 4)
    vd = vd_refresh_score(st, _unlocked_sess(), _REG)
    e_cur = _engines_formed(st, _REG)
    expected = _jump(e_cur, st) - _e1(4, 1) * 2
    assert vd is not None and vd > 0, vd
    assert abs(vd - expected) < 1e-6, (vd, expected)


# --- ② 金 50/51/52 拒([3] 预算前提;P5⑤ 回归)-----------------------------------


def test_gold_51_52_refused() -> None:
    """②金 51/52:最便宜缺件(1费)阈值=53 → 无一合格对象 → None
    (一次刷+买入后仍 ≥ interest_floor 的单次口径;找牌预算不破息)。"""
    for gold in (50, 51, 52):
        st = _p1_state(5, gold, 5)
        assert vd_refresh_score(st, _locked_sess(), _REG) is None, gold


# --- ③ P1 无窗帧不刷 -------------------------------------------------------------


def test_no_pair_frame_returns_none() -> None:
    """③无对帧(pair 空):①锁局窗外逐位回 W166(恒 None)。"""
    st = _p1_state(5, 53, 5)
    s = _locked_sess(pair=())
    assert vd_refresh_score(st, s, _REG) is None


def test_no_missing_member_frame_returns_none() -> None:
    """③不缺件帧(对成员全持有,bench 放置)→ 找件对象消失 → None。"""
    members = sorted(_pair_members(_PAIR))
    bench = [BenchChar(slot=i, char_id=n, faction='公司', star=1)
             for i, n in enumerate(members)]
    st = _p1_state(5, 90, 5, bench=bench)
    assert vd_refresh_score(st, _locked_sess(), _REG) is None


# --- ④ A/B 通道 ------------------------------------------------------------------


def test_ab_switch_back_to_w166() -> None:
    """④vd_p1_pair_enabled=False → ①锁局窗外帧逐位回 W166(恒 None)。"""
    reg_off = dataclasses.replace(_REG, vd_p1_pair_enabled=False)
    st = _p1_state(5, 53, 5)
    assert vd_refresh_score(st, _locked_sess(), reg_off) is None
    # 配方锁局帧(core 恒空)开关关同样回 None
    assert vd_refresh_score(st, _unlocked_sess(), reg_off) is None


# --- ⑤ P2 逐位回归 ---------------------------------------------------------------


def test_p2_branch_untouched_by_pair_channel() -> None:
    """⑤P2 帧(W154 ③ run15 姬子案:列车同行 lv6 姬子·启行 j=1 金 108,
    DP rb=6 窗开但批口径刷金 134.8 > 98 → 预算硬界拒):即便
    transition_pair 非空,pair 通道不辖(plane≠1)→ 仍 None
    (P2 分支逐位不动)。"""
    from sr_od.application.currency_war.decision_v2.posture import Posture
    from sr_od.application.currency_war.decision_v2.ev import RoundPosture
    s = StrategySession()
    s.v3_intention = IntentionState(
        phase='locked', locked_comp='列车同行',
        transition_pair=_PAIR)
    s.target_comp = get_comp('列车同行')
    s.v3_dp_posture = RoundPosture(
        (2, 1), Posture(save=False, level_up=True, refresh_budget=6))
    st = GameState(
        plane=2, round_num=1, gold=108, level=6, hp=69,
        shop_refresh_cost=5,
        deployed=[BenchChar(slot=9 + i, char_id=f'杂件{i}',
                            faction='公司', star=1)
                  for i in range(4)],
        bench=[BenchChar(slot=0, char_id='姬子·启行',
                         faction='公司', star=1)],
        shop=[], node_type='battle')
    assert vd_refresh_score(st, s, _REG) is None


# --- ⑥ roll/stable 窗内取大 -------------------------------------------------------


def test_roll_window_max_of_core_and_pair() -> None:
    """⑥窗内帧(DOT队 lv8=roll,core 有账)pair 并存取大:
    金 53 → pair 合格对象=1费档;core=卡芙卡 j=2 批口径账;
    V=max(core, pair) 逐位对拍。"""
    st = _p1_state(8, 53, 8,
                   bench=[BenchChar(slot=0, char_id='卡芙卡',
                                    faction='公司', star=1),
                          BenchChar(slot=1, char_id='卡芙卡',
                                    faction='公司', star=1)])
    s = _locked_sess()
    goal = _resolve_level_goal(st, s.target_comp)
    assert goal is None or goal.action != 'level_up', '前置:窗内帧'
    vd = vd_refresh_score(st, s, _REG)
    # core 账(2★ 批口径,P1 骨架式本地复算)
    from sr_od.application.currency_war.data.cw_shop_odds import (
        expected_refreshes_for_card,
    )
    e_core = expected_refreshes_for_card(8, 2, target_star=2, owned=2)
    core_v = _jump(1, st) - e_core * 2
    e_cur = _engines_formed(st, _REG)
    pair_v = _jump(e_cur, st) - _e1(8, 1) * 2
    assert vd is not None
    assert abs(vd - max(core_v, pair_v)) < 1e-6, (vd, core_v, pair_v)
