# -*- coding: utf-8 -*-
"""W154/ADR-0361 P2 段 V_D 修法单帧锁(P11 成本侧/P12 收益侧/DP 窗授权)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 窗判据:P2 等级窗二分改消费 DP refresh_budget 授权(升级与 D 并行,
  「升级+D6」姿态下窗开;refresh_budget=0 仍让位;DP 异常保守回退
  level_plan 门;vd_p2_enabled=False 回 W153 前行为);
- ② 正例:2费@lv6 j=1/j=2 帧(run16/17 真帧形态)翻正 + 分值=P11/P12
  公式逐位对拍(benefit^P2 − C_dec);
- ③ 负例(run15 姬子案):3费@lv6 j=0/j=1 帧预算硬界拒(spend > g−
  boss_floor);组件断言「仅修收益侧仍负」(benefit^P2 < 批口径面值
  spend)——锁「不是无脑放开」;
- ④ battles_left_p2 推导:plane_node_table 槽序表数剩余战斗节点;
  表缺失退 registry 缺省;
- ⑤ P1 分支逐位不动:同帧 plane=1 时 DP 窗不消费(仍 level_plan 互斥)、
  收益/成本仍 P1 骨架(P1 sim 零漂移回归门的单帧侧);
- ⑥ 四局真帧回放对照:14 个 P2 shop 帧的逐帧判定(W152 断点解陧行为
  变化清单:6 帧翻正/8 帧仍拒)。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_horizon import NODES_PER_PLANE
from sr_od.application.currency_war.cw_horizon import Posture
from sr_od.application.currency_war.cw_intention import IntentionState
from sr_od.application.currency_war.cw_shop_odds import (
    expected_refreshes_for_card,
)
from sr_od.application.currency_war.cw_state import BenchChar, GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2 import ev as ev_mod
from sr_od.application.currency_war.decision_v2.ev import (
    RoundPosture,
    battles_left_p2,
    cross_plane_remaining_nodes,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    vd_refresh_score,
)

_REG = DEFAULT_REGISTRY
#: P2 实测刷价(W152 四局:进 P2 后 shop_refresh_cost=5)
REFRESH_COST_P2 = 5


def _locked_sess(comp: str) -> StrategySession:
    s = StrategySession()
    s.v3_intention = IntentionState(phase='locked', locked_comp=comp)
    s.target_comp = get_comp(comp)
    s.v3_mode = 'economy'
    return s


def _dp_sess(comp: str, plane: int, r: int, rb: int,
             table: list[str] | None = None) -> StrategySession:
    """带轮缓存 DP 姿态(refresh_budget=rb)的锁定 session(确定性注入)。"""
    s = _locked_sess(comp)
    s.v3_dp_posture = RoundPosture(
        (plane, r), Posture(save=False, level_up=rb == 0 or True,
                            refresh_budget=rb))
    if table is not None:
        s.plane_node_table = table
    return s


def _p2_state(level: int, copies: list[str], gold: int, r: int, *,
              hp: int = 69, plane: int = 2,
              node: str = 'battle') -> GameState:
    return GameState(
        plane=plane, round_num=r, gold=gold, level=level, hp=hp,
        shop_refresh_cost=REFRESH_COST_P2,
        deployed=[BenchChar(slot=9 + i, char_id=f'杂件{i}',
                            faction='公司', star=1)
                  for i in range(4)],
        bench=[BenchChar(slot=i, char_id=n, faction='公司', star=1)
               for i, n in enumerate(copies)],
        shop=[], node_type=node)


def _benefit_p2(st: GameState, reg=_REG, bl: float | None = None) -> float:
    """P12 收益侧公式对拍值(测试本地复算,禁从被测函数借值)。"""
    drung = reg.rung_value[2] - reg.rung_value[1]
    dwin = reg.h3_win_rate[2] - reg.h3_win_rate[1]
    r = cross_plane_remaining_nodes(st)
    if bl is None:
        bl = reg.battles_left_est
    return drung * r + dwin * reg.vd_p2_loss * reg.hp_to_gold * bl


def _c_dec(gold: int, spend: float, st: GameState, reg=_REG) -> float:
    """P11 决策成本公式对拍值(封顶息口径 Δinterest)。"""
    d_int = (min(gold // 10, reg.interest_cap)
             - min(int(gold - spend) // 10, reg.interest_cap))
    return (max(0, d_int)
            * min(cross_plane_remaining_nodes(st),
                  reg.vd_p2_recovery_rounds)
            + reg.vd_p2_liquidity_rho * spend)


# --- ① 窗判据:DP refresh_budget 授权消费 -------------------------------------


def test_p2_window_consumes_dp_budget() -> None:
    """①P2 帧等级窗二分改消费 DP refresh_budget:列车同行@lv6
    (level_plan 说 level_up,W152 断点②形态)在「升级+D6」姿态下
    窗开(评分继续,预算硬界/EV 裁决);refresh_budget=0(纯存/纯升)
    仍让位。"""
    # 姬子·启行 3费 j=2、金 100:预算硬界内 → 窗开后应为正分
    st = _p2_state(6, ['姬子·启行', '姬子·启行'], 100, 1)
    s6 = _dp_sess('列车同行', 2, 1, rb=6)
    vd = vd_refresh_score(st, s6, _REG)
    assert vd is not None and vd > 0, vd
    # 对照:DP 无 D 预算 → 让位(旧「让一拍」语义保留在授权层)
    s0 = _dp_sess('列车同行', 2, 1, rb=0)
    assert vd_refresh_score(st, s0, _REG) is None


def test_p2_window_dp_fallback_level_plan(monkeypatch) -> None:
    """①DP 查询异常(姿态 None)→ 保守回退 level_plan 门:goal=level_up
    仍拒(对局不停,保守侧)。"""
    st = _p2_state(6, ['卡芙卡', '卡芙卡'], 100, 1)
    monkeypatch.setattr(ev_mod, 'round_posture',
                        lambda *a, **k: None)
    s = _locked_sess('DOT队')
    assert vd_refresh_score(st, s, _REG) is None, \
        'DP 异常回退必须走 level_plan 门(DOT队 lv6=level_up→拒)'


def test_p2_ab_switch_back_to_w153(monkeypatch) -> None:
    """①A/B 通道:vd_p2_enabled=False → 回 W153 前行为(窗=level_plan
    互斥,批口径面值 EV——同帧必拒)。"""
    reg_off = dataclasses.replace(_REG, vd_p2_enabled=False)
    st = _p2_state(6, ['卡芙卡', '卡芙卡'], 100, 1)
    s = _dp_sess('DOT队', 2, 1, rb=6)
    assert vd_refresh_score(st, s, reg_off) is None, \
        '开关关=DOT队 lv6 level_plan 互斥逐位回 W153'


# --- ② 正例:2费@lv6 j=1/j=2 翻正帧(P12 收益侧 × P11 成本侧)---------------


def test_p2_positive_2cost_j2_frame() -> None:
    """②run16 r1 真帧形态(卡芙卡 2费@lv6 j=2,金 80,刷价 5):
    V_D = benefit^P2 − C_dec 逐位对拍(金 80 花 42.3 穿 50 → Δinterest
    =2 档 × min(R,2.31);存活分量按 loss_p2=16 × bl=5 缺省)。"""
    st = _p2_state(6, ['卡芙卡', '卡芙卡'], 80, 1)   # R=18
    s = _dp_sess('DOT队', 2, 1, rb=6)
    vd = vd_refresh_score(st, s, _REG)
    assert vd is not None and vd > 0, vd
    e = expected_refreshes_for_card(6, 2, target_star=2, owned=2)
    spend = e * REFRESH_COST_P2
    expected = _benefit_p2(st) - _c_dec(80, spend, st)
    assert abs(vd - expected) < 1e-6, (vd, expected)


def test_p2_positive_2cost_j1_pure_overflow() -> None:
    """②j=1 帧(2费@lv6 E=16.2 × 5 = 81 刷金;金 140 纯溢余段):
    g−s=59≥50 → Δinterest=0、ρ=0 → C_dec=0(P11 下界),V_D=benefit^P2
    ——纯溢余段的「溢余即花」([17] 主条)形态。"""
    st = _p2_state(6, ['卡芙卡'], 140, 2)            # R=17
    s = _dp_sess('DOT队', 2, 2, rb=6)
    vd = vd_refresh_score(st, s, _REG)
    assert vd is not None and vd > 0, vd
    assert abs(vd - _benefit_p2(st)) < 1e-6, (vd, _benefit_p2(st))


def test_p2_battles_left_from_state_feeds_benefit() -> None:
    """②battles_left_p2(state 推导)进收益:同帧注入槽序表
    (r3 起 6 个战斗节点)vs 无表缺省 5,分值差=Δdwin×loss×hp_gold×1。"""
    table = ['reward', 'reward', 'battle', 'battle', 'supply',
             'battle', 'encounter', 'boss', 'battle']
    st = _p2_state(6, ['卡芙卡', '卡芙卡'], 100, 3)   # R=16
    s_tab = _dp_sess('DOT队', 2, 3, rb=6, table=table)
    s_def = _dp_sess('DOT队', 2, 3, rb=6)
    vd_tab = vd_refresh_score(st, s_tab, _REG)
    vd_def = vd_refresh_score(st, s_def, _REG)
    assert vd_tab is not None and vd_def is not None
    dwin = _REG.h3_win_rate[2] - _REG.h3_win_rate[1]
    assert abs((vd_tab - vd_def)
               - dwin * _REG.vd_p2_loss * _REG.hp_to_gold * 1) < 1e-6


# --- ③ 负例:run15 姬子案(锁「不是无脑放开」)-------------------------------


def test_p2_negative_3cost_j1_budget_bound() -> None:
    """③run15 姬子·启行 3费@lv6 j=1(金 108,批口径刷金 134.8):
    预算硬界(spend > g − boss_floor=98)→ None——高费远未齐不硬 D
    (P5 边界语义保留,约束移授权层,P11 推论);组件断言:仅修收益侧
    (benefit^P2 vs 批口径面值 spend)仍负——D 的放开由成本侧口径+
    预算界共同辖,非无条件。"""
    st = _p2_state(6, ['姬子·启行'], 108, 1)          # R=18
    s = _dp_sess('列车同行', 2, 1, rb=6)
    assert vd_refresh_score(st, s, _REG) is None
    e = expected_refreshes_for_card(6, 3, target_star=2, owned=1)
    spend = e * REFRESH_COST_P2
    assert spend > st.gold - _REG.boss_floor, '前置:预算硬界触发'
    assert _benefit_p2(st) < spend, \
        '仅修收益侧(run15 案)仍负——收益侧不是无脑放开'


def test_p2_negative_2cost_j1_run18_budget_bound() -> None:
    """③run18 帧形态(绯英 2费@lv6 j=1,金 88,批口径刷金 81):
    81 > 88−10 → 预算硬界拒(W152 唯一窗开帧的 EV 负拒,修法后由
    预算界辖,仍拒)。"""
    st = _p2_state(6, ['绯英'], 88, 1)
    s = _dp_sess('绯英欢愉', 2, 1, rb=6)
    assert vd_refresh_score(st, s, _REG) is None


# --- ④ battles_left_p2 推导 ---------------------------------------------------


def test_battles_left_p2_table_derivation() -> None:
    """④槽序表推导:从当前轮起数非战斗 token(reward/supply)之外的
    剩余槽;表缺失/空 → registry 缺省(保守侧)。"""
    table = ['reward', 'reward', 'battle', 'battle', 'supply',
             'battle', 'encounter', 'boss', 'battle']
    st = GameState(plane=2, round_num=3, gold=100, level=6, hp=69)
    s = StrategySession()
    s.plane_node_table = table
    # r3 起剩余:battle,battle,supply,battle,encounter,boss,battle → 6
    assert battles_left_p2(st, s, _REG) == 6.0
    # 表空 → 缺省
    assert battles_left_p2(st, StrategySession(), _REG) \
        == _REG.battles_left_est
    # 表长于位面:越界槽不数
    s.plane_node_table = table + ['battle', 'battle']
    assert battles_left_p2(st, s, _REG) == 6.0


# --- ⑤ P1 分支逐位不动 -------------------------------------------------------


def test_p1_branch_bitwise_unchanged() -> None:
    """⑤P1 帧(同形态 plane=1):DP 窗不消费(「升级+D6」姿态下仍走
    level_plan 互斥——DOT队 lv5=level_up → None),收益/成本=P1 骨架
    (roll 窗帧分值=benefit_P1 − E×刷价,与 W126 锁①同式)。"""
    # P1 lv5 goal=level_up:即便 DP 给 D6 预算也拒(窗=P1 互斥语义)
    st5 = _p2_state(5, ['卡芙卡', '卡芙卡'], 60, 5, plane=1)
    st5.shop_refresh_cost = 2
    s5 = _dp_sess('DOT队', 1, 5, rb=6)
    assert vd_refresh_score(st5, s5, _REG) is None, \
        'P1 窗二分逐位不动(DP 授权只在 P2 消费)'
    # P1 roll 窗帧(lv8):P1 骨架公式逐位对拍
    st8 = _p2_state(8, ['卡芙卡', '卡芙卡'], 100, 8, plane=1)
    st8.shop_refresh_cost = 2
    s8 = _dp_sess('DOT队', 1, 8, rb=6)
    vd8 = vd_refresh_score(st8, s8, _REG)
    assert vd8 is not None and vd8 > 0, vd8
    e8 = expected_refreshes_for_card(8, 2, target_star=2, owned=2)
    drung = _REG.rung_value[2] - _REG.rung_value[1]
    dwin = _REG.h3_win_rate[2] - _REG.h3_win_rate[1]
    expected = (drung * cross_plane_remaining_nodes(st8)
                + dwin * _REG.expected_battle_loss * _REG.hp_to_gold
                * _REG.battles_left_est - e8 * 2)
    assert abs(vd8 - expected) < 1e-6, (vd8, expected)


# --- ⑥ 四局真帧回放对照(行为变化清单)---------------------------------------


def test_four_run_replay_verdicts() -> None:
    """⑥W152 四局 14 个 P2 shop 帧的修法后判定(回放对拍,帧数据=
    decisions.jsonl 真值;DP 姿态按遥测实测注入 refresh_budget=6,
    P3 帧遥测=纯升 rb=0):6 帧翻正(run16 r1/r2/r4、run17 r1/r2/r4)、
    8 帧仍拒(run15×3 预算硬界 / run16 r5 预算硬界 / run16 r6/r7 核心
    已 2★ / run16 P3r1 核心已 2★+rb0 / run18 r1 预算硬界)。"""
    cases = [
        # (comp, core_copies, gold, lv, plane, r, rb, 期望)
        ('列车同行', ['姬子·启行'], 108, 6, 2, 1, 6, None),
        ('列车同行', ['姬子·启行'], 119, 6, 2, 2, 6, None),
        ('列车同行', ['姬子·启行'], 124, 6, 2, 4, 6, None),
        ('DOT队', ['卡芙卡', '卡芙卡'], 80, 6, 2, 1, 6, 'pos'),
        ('DOT队', ['卡芙卡', '卡芙卡'], 96, 6, 2, 2, 6, 'pos'),
        ('DOT队', ['卡芙卡', '卡芙卡'], 100, 6, 2, 4, 6, 'pos'),
        ('DOT队', ['卡芙卡'], 111, 7, 2, 5, 6, None),
        ('DOT队', ['卡芙卡*2star'], 119, 7, 2, 6, 6, None),
        ('DOT队', ['卡芙卡*2star'], 137, 7, 2, 7, 6, None),
        ('DOT队', ['卡芙卡*2star'], 160, 7, 3, 1, 0, None),
        ('DOT队', ['卡芙卡', '卡芙卡'], 85, 6, 2, 1, 6, 'pos'),
        ('DOT队', ['卡芙卡', '卡芙卡'], 100, 6, 2, 2, 6, 'pos'),
        ('DOT队', ['卡芙卡', '卡芙卡'], 105, 6, 2, 4, 6, 'pos'),
        ('绯英欢愉', ['绯英'], 88, 6, 2, 1, 6, None),
    ]
    for comp, copies, gold, lv, plane, r, rb, exp in cases:
        star2 = [c for c in copies if c.endswith('*2star')]
        held = ([BenchChar(slot=i, char_id=c.removesuffix('*2star'),
                           faction='公司', star=2) for i, c in
                 enumerate(star2)]
                + [BenchChar(slot=8 - i, char_id=c, faction='公司', star=1)
                   for i, c in enumerate(c for c in copies
                                         if not c.endswith('*2star'))])
        st = GameState(
            plane=plane, round_num=r, gold=gold, level=lv, hp=69,
            shop_refresh_cost=REFRESH_COST_P2,
            deployed=[BenchChar(slot=9 + i, char_id=f'杂件{i}',
                                faction='公司', star=1)
                      for i in range(4)],
            bench=held, shop=[], node_type='battle')
        s = _dp_sess(comp, plane, r, rb=rb)
        vd = vd_refresh_score(st, s, _REG)
        if exp is None:
            assert vd is None, (comp, r, vd)
        else:
            assert vd is not None and vd > 0, (comp, r, vd)
    # 位面常量前置核对(帧构造依赖)
    assert NODES_PER_PLANE == 9
