# -*- coding: utf-8 -*-
"""test_cw_plane_p2 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w154_p2_vd: test_cw_w154_p2_vd.py
- w157_p2_segment: test_cw_w157_p2_segment.py
- w167_plane_rounds: test_cw_w167_plane_rounds.py
- w193_p2_combat: test_cw_w193_p2_combat.py
- w194_p2_multihit: test_cw_w194_p2_multihit.py
- w370_p2_loss_recalib: test_cw_w370_p2_loss_recalib.py
- w413_p2_two_state_injection: test_cw_w413_p2_two_state_injection.py
- p2_survival_band: test_cw_p2_survival_band.py
- w857_plane_intel_skip: test_cw_w857_plane_intel_skip.py
- w901_plane_intel_static_conclude: test_cw_w901_plane_intel_static_conclude.py
- w314_plane_intel_wait_clean: test_cw_w314_plane_intel_wait_clean.py
- w575_plane_detail_recovery: test_cw_w575_plane_detail_recovery.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== w154_p2_vd ====================

import dataclasses

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_plane_table import NODES_PER_PLANE
from sr_od.application.currency_war.decision.decision_v2.posture import Posture
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.data.cw_shop_odds import  expected_refreshes_for_card
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2 import ev as ev_mod
from sr_od.application.currency_war.decision.decision_v2.ev import  RoundPosture, battles_left_p2, cross_plane_remaining_nodes
from sr_od.application.currency_war.kernel.cw_registry import  DEFAULT_REGISTRY
from sr_od.application.currency_war.decision.decision_v2.scoring import  vd_refresh_score

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


# --- ① 窗判据:刷新预算授权消费(批 3 预算函数口径,W623 D2)---------------------


def test_p2_window_consumes_dp_budget() -> None:
    """①P2 帧等级窗二分消费刷新预算:列车同行@lv6(锁定核心 3 费峰值
    级 7>6 → 排程,R*=息线+升级费)。金 100:溢余>0 → 预算>0 → 窗开
    (评分继续,预算硬界/EV 裁决);金 55(g<R*,储备段合法 0 帧)→
    让位。批 3 重推:供给=确定性预算核(schedule_upgrade/refresh_ev_budget
    单一址),注入式 posture 退役——「>0 即授权」即预算函数口径。"""
    # 姬子·启行 3费 j=2、金 100:预算硬界内 → 窗开后应为正分
    st = _p2_state(6, ['姬子·启行', '姬子·启行'], 100, 1)
    s = _locked_sess('列车同行')
    vd = vd_refresh_score(st, s, _REG)
    assert vd is not None and vd > 0, vd
    # 对照:储备段预算=0 → 让位(旧「让一拍」语义保留在授权层)
    st0 = _p2_state(6, ['姬子·启行', '姬子·启行'], 55, 1)
    assert vd_refresh_score(st0, s, _REG) is None


def test_p2_window_dp_fallback_level_plan(monkeypatch) -> None:
    """(批 3 退役)原「DP 查询异常(None)→ 保守回退 level_plan 门」:
    确定性预算核在任意帧恒有定义,None 形状消灭(W623 D0 供给权交接);
    保守回退语义由『预算 0 → 让位』承接(上一锁对照臂)。"""
    from sr_od.application.currency_war.kernel.cw_economy import  refresh_ev_budget
    from sr_od.application.currency_war.decision.decision_v2.scoring import  vd_refresh_score as _impl
    st = _p2_state(6, ['卡芙卡', '卡芙卡'], 100, 1)
    s = _locked_sess('DOT队')
    # DOT队 lv6 level_plan 说 level_up:预算 0(合法 0 帧注入,消费门
    # 判据直测)下仍让位
    import sr_od.application.currency_war.kernel.cw_economy as ec
    monkeypatch.setattr(ec, 'refresh_ev_budget', lambda *a, **k: 0)
    assert _impl(st, s, _REG) is None, \
        '预算 0(合法 0 帧)必须走 level_plan 门(DOT队 lv6=level_up→拒)'


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
    # ADR-0425:P1 收益侧战斗项=条件掉血拟合(成型后档 rung=2)
    # ×战斗数(裸 session 无槽序表 → 骨架缺省)
    from sr_od.application.currency_war.decision.decision_v2.scoring import  p1_battle_loss_est
    expected = (drung * cross_plane_remaining_nodes(st8)
                + dwin * p1_battle_loss_est(st8, _REG, rung=2)
                * _REG.hp_to_gold * _REG.battles_left_est - e8 * 2)
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


# ==================== w157_p2_segment ====================

import json
import logging
import random
from pathlib import Path

import pytest

from sr_od.application.currency_war.data import cw_battle_tables as _tables
from sr_od.application.currency_war.kernel import cw_battle_calib
from sr_od.application.currency_war.sim import engine_p1 as cw_sim
from sr_od.application.currency_war.sim import pool as sim_pool
from sr_od.application.currency_war.sim.checks import runner


@pytest.fixture(autouse=True)
def _quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 logging.disable 是全局态:pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(prev)



# ---------- Δ池 plane 键化 ----------

def test_pool_from_replay_assigns_delta_to_later_plane(tmp_path: Path) -> None:
    """跨位面差分(P1r9→P2r1)归属 plane=2——W156 污染形态修法本体。"""
    def _dec(rn: int, plane: int) -> str:
        return json.dumps({
            'run_id': 'r1', 'plane': plane, 'round_num': rn,
            'state': {'board': {'仙舟': 3}, 'deployed': []}},
            ensure_ascii=False)

    (tmp_path / 'decisions.jsonl').write_text('\n'.join([
        _dec(9, 1), _dec(1, 2),
    ]) + '\n', encoding='utf-8')

    def _out(rn: int, plane: int, nt: str, hp: int) -> str:
        return json.dumps({
            'run_id': 'r1', 'plane': plane, 'round_num': rn,
            'node_type': nt, 'hp_after': hp, 'board_before': {}},
            ensure_ascii=False)

    # P1r9 boss hp60 → P2r1 battle hp42:Δ=-18 归 plane=2(后行位面)
    (tmp_path / 'outcomes.jsonl').write_text('\n'.join([
        _out(9, 1, 'boss', 60),
        _out(1, 2, '普通战斗', 42),
    ]) + '\n', encoding='utf-8')

    pool, _ = sim_pool._pool_from_replay(tmp_path)
    # P2r1 是 battle(rung 桶 = board_before{} 的 0);不挂 plane=1
    assert pool['battle'].get(2) and not pool['battle'].get(1, {}).get(0)
    assert pool['battle'][2][0] == [-18]


def test_live_delta_no_cross_plane_fallback() -> None:
    """plane≥2 缺桶不跨位面借 P1 样本(口径混桶防线)。"""
    pool = {'battle': {1: {0: [-11] * 6}}}   # 只有 P1 桶
    assert sim_pool.live_delta_for('battle', 0, random.Random(0),
                                 pool_map=pool, plane=2) is None
    # 同池 plane=1 正常采样
    assert sim_pool.live_delta_for('battle', 0, random.Random(0),
                                 pool_map=pool, plane=1) in [-11] * 6


def test_fingerprint_covers_plane_layer() -> None:
    """指纹含位面层:同桶样本不同位面 → 不同指纹(池语义可区分)。"""
    a = {'battle': {1: {0: [-11]}}}
    b = {'battle': {2: {0: [-11]}}}
    assert sim_pool.pool_fingerprint(a) != sim_pool.pool_fingerprint(b)


def test_plane_view_is_p1_projection() -> None:
    """plane_view:单位面投影(plane=1 锚定检查的口径单一源)。"""
    pool = {'battle': {1: {0: [-11]}, 2: {0: [-16]}},
            'boss': {1: {9: [-20]}}}
    v = sim_pool.plane_view(pool)
    assert v == {'battle': {0: [-11]}, 'boss': {9: [-20]}}
    assert sim_pool.plane_view(pool, 2) == {'battle': {0: [-16]},
                                          'boss': {}}


# ---------- simulate_p1(planes=2)段形状 ----------

def test_planes_rejects_p3() -> None:
    """planes=3+(P3)显式拒绝(语料零样本,案 c 缓)。"""
    try:
        cw_sim.simulate_p1(0, pool='fallback', planes=3)
    except ValueError as e:
        assert 'planes' in str(e)
    else:
        raise AssertionError('planes=3 应显式 raise')


def test_planes2_segment_shape(tmp_path: Path) -> None:
    """P2 段形状:7 轮 P2_NODE_SEQUENCE、账本 plane=2 行、ts 单调。"""
    r = cw_sim.simulate_p1(0, pool='snapshot', planes=2)
    p1 = [row for row in r.ledger if row['plane'] == 1]
    p2 = [row for row in r.ledger if row['plane'] == 2]
    assert len(p1) == 9 or p1[-1]['hp'] <= 0   # P1 段死=不进 P2
    if r.p2_entered:
        assert [row['sim']['node'] for row in p2] == \
            list(cw_sim.P2_NODE_SEQUENCE)[:len(p2)]
        assert [row['round_num'] for row in p2] == \
            list(range(1, len(p2) + 1))
        assert p2[0]['ts'] == len(p1) + 1       # ts 跨位面单调续接
        # 进场继承:P2r1 行前 hp == P1 末行 hp(继承块的直接证据)
        # (账本行 hp=结算后;结算前 = P1 末行 hp,由 p2 段首行
        #  hp_after - delta 回推)
        assert r.p2_entered and 1 <= len(p2) <= cw_sim.P2_ROUNDS
    else:
        assert p1[-1]['hp'] <= 0


def test_p2_observation_fields_consistent() -> None:
    """SimResult P2 观测与账本/plane 一致(p2_rounds=plane2 行数)。"""
    for seed in (0, 3, 7):
        r = cw_sim.simulate_p1(seed, pool='snapshot', planes=2)
        n_p2 = sum(1 for row in r.ledger if row['plane'] == 2)
        assert r.p2_rounds == n_p2
        assert r.p2_entered == (n_p2 > 0)
        assert r.p2_hp0 == (r.p2_entered and r.final_hp <= 0)
        if r.p2_combat_total:
            assert 0 <= r.p2_combat_wins <= r.p2_combat_total


def test_p1_default_equals_planes1() -> None:
    """planes 缺省 ≡ planes=1(默认路径零漂移;同 seed 逐位同)。"""
    a = cw_sim.simulate_p1(5, pool='fallback')
    b = cw_sim.simulate_p1(5, pool='fallback', planes=1)
    assert a.final_hp == b.final_hp
    assert a.hp_trail == b.hp_trail
    assert a.ledger == b.ledger


def test_p2_battle_fallback_band() -> None:
    """P2 battle 回退档:败=掉血带 15-17(负样本域)/胜=WIN_DELTAS。"""
    rng = random.Random(0)
    losses, wins = [], 0
    for _ in range(400):
        d = cw_battle_calib.node_delta('battle', 11, 3, rng, plane=2)
        if d <= -15:                # 败带样本
            losses.append(d)
        else:                       # 胜(WIN_DELTAS ∈ {2,2,0,-4})
            wins += 1
            assert d in _tables.WIN_DELTAS
    assert losses and all(-17 <= d <= -15 for d in losses)
    # 0.11 胜率:400 样本期望 ~44,二项带宽宽松断言
    assert 15 <= wins <= 90
    # P1 分支不受影响:胜率口径不同(0.29),同 rng 序下分布应不同
    rng2 = random.Random(0)
    w1 = sum(1 for _ in range(400)
             if cw_battle_calib.node_delta('battle', 3, 3, rng2, plane=1) > 0)
    assert w1 != 44 or wins != 44   # 只防「两分支恒等」的结构回归


def test_p2_node_sequence_matches_corpus() -> None:
    """P2 节点序列 = 16 局 outcomes 拼版(battle/battle/supply/battle/
    encounter/reward/boss)。"""
    assert cw_sim.P2_NODE_SEQUENCE == (
        'battle', 'battle', 'supply', 'battle',
        'encounter', 'reward', 'boss')
    assert cw_sim.P2_ROUNDS == len(cw_sim.P2_NODE_SEQUENCE) == 7


# ---------- P2 headline + 检查器 ----------

def test_batch_p2_headline_quartet() -> None:
    """批报告 P2 headline 四联键在位(不锁分布数值,形状锁)。"""
    rep = runner.simulate_p1_batch(10, pool='snapshot', planes=2,
                                   ledger=False)
    for k in ('p2_entered_rate', 'avg_p2_rounds', 'p2_win_rate',
              'p2_hp0_rate', 'avg_p2_refreshes'):
        assert k in rep, f'P2 headline 缺键: {k}'
    assert 0.0 <= rep['p2_entered_rate'] <= 1.0
    cv = rep['checks_violations']
    assert 'p2_gold_nonneg' in cv and 'p2_segment_shape' in cv
    assert cv['p2_gold_nonneg']['violations'] == 0
    assert cv['p2_segment_shape']['violations'] == 0


def test_batch_p1_metrics_scoped_to_plane1() -> None:
    """planes=2 批的 P1 锚定指标只算 plane=1 行(辖域切片;
    planes=1 与 planes=2 的 P1 段同 seed 应同 hp_events)。"""
    r1 = cw_sim.simulate_p1(0, pool='snapshot', planes=1)
    r2 = cw_sim.simulate_p1(0, pool='snapshot', planes=2)
    p1_ev2 = [e for e in r2.hp_events if e[0] <= 9]
    assert p1_ev2 == r1.hp_events   # P1 段 RNG 序不变 → 事件逐位同


def test_check_p2_gold_nonneg_unit() -> None:

    from sr_od.application.currency_war.sim.checks.calib import check_p2_gold_nonneg
    bad = [[{'plane': 2, 'round_num': 3, 'gold': -1}]]
    rep = check_p2_gold_nonneg(bad)
    assert rep['violations'] == 1 and rep['games'] == [0]
    ok = [[{'plane': 1, 'round_num': 3, 'gold': -1}]]   # P1 行不辖
    assert check_p2_gold_nonneg(ok)['violations'] == 0
    assert check_p2_gold_nonneg([[]])['violations'] == 0


def test_check_p2_segment_shape_unit() -> None:

    from sr_od.application.currency_war.sim.checks.calib import check_p2_segment_shape
    good = [[{'ts': 1, 'plane': 1, 'round_num': 1},
             {'ts': 10, 'plane': 2, 'round_num': 1}]]
    assert check_p2_segment_shape(good)['violations'] == 0
    bad_ts = [[{'ts': 2, 'plane': 1, 'round_num': 1},
               {'ts': 2, 'plane': 2, 'round_num': 1}]]
    assert check_p2_segment_shape(bad_ts)['violations'] >= 1
    bad_rn = [[{'ts': 1, 'plane': 2, 'round_num': 9}]]
    assert check_p2_segment_shape(bad_rn)['violations'] >= 1
    bad_pl = [[{'ts': 1, 'plane': 3, 'round_num': 1}]]
    assert check_p2_segment_shape(bad_pl)['violations'] >= 1


def test_simulate_p2_ab_report_shape() -> None:
    """simulate_p2_ab 报告形状:双臂 headline 四联 + D 方向对拍键。"""
    rep = runner.simulate_p2_ab(10, pool='snapshot', seed_base=0)
    for arm in ('headline_on', 'headline_off'):
        for k in ('p2_entered_rate', 'avg_p2_rounds', 'p2_win_rate',
                  'p2_hp0_rate', 'total_p2_refreshes'):
            assert k in rep[arm]
    rd = rep['refresh_direction']
    assert rd['on_gt_off'] + rd['off_gt_on'] + rd['tie'] == rep['n']
    assert rep['headline_on']['p2_entered_rate'] == \
        rep['headline_off']['p2_entered_rate']   # P1 段两臂零漂移


from sr_od.application.currency_war.sim import runner


# ==================== w167_plane_rounds ====================

from sr_od.application.currency_war.kernel.cw_evolution import  EvolutionState, evolution_step
from sr_od.application.currency_war.kernel.cw_plane_table import (    NODES_PER_PLANE as _w167_plane_rounds_NODES_PER_PLANE,
    nodes_of_plane,
    schedule_of as _w167_schedule_of,
)
from sr_od.application.currency_war.kernel.cw_intention import plane_remaining_nodes
from sr_od.application.currency_war.kernel.cw_state import CompTransaction, GameState as _w167_plane_rounds_GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w167_plane_rounds_StrategySession
from sr_od.application.currency_war.decision.decision_v2.discipline import  _hard_node, plane_last_battle
from sr_od.application.currency_war.decision.decision_v2.ev import battles_left_p2 as _w167_plane_rounds_battles_left_p2
from sr_od.application.currency_war.kernel.cw_registry import  DEFAULT_REGISTRY as _w167_plane_rounds_DEFAULT_REGISTRY

_P2_TABLE = ['battle', 'battle', 'supply', 'battle',
             'encounter', 'reward', 'boss']       # W157 16 局拼版(7 槽)
_P1_TABLE = ['reward'] * 2 + ['battle'] * 4 + ['encounter', 'battle', 'boss']


def _sess(table: list[str] | None) -> _w167_plane_rounds_StrategySession:
    s = _w167_plane_rounds_StrategySession()
    if table is not None:
        s.plane_node_table = list(table)
    return s


# ---------- ① 单一源 ----------

def test_nodes_of_plane_table_lengths():
    assert nodes_of_plane(_sess(_P2_TABLE)) == 7
    assert nodes_of_plane(_sess(_P1_TABLE)) == 9
    # P3 首局进表即自适应(口径断层修复的前向性:不写死 7)
    assert nodes_of_plane(_sess(_P1_TABLE[:-1])) == 8


def test_nodes_of_plane_fallback_when_table_missing():
    # 裸 session / None → 回退 P1 先验(零漂移的结构面)
    assert nodes_of_plane(_sess(None)) == _w167_plane_rounds_NODES_PER_PLANE == 9
    assert nodes_of_plane(None) == 9


def test_schedule_of_fallback_priors_per_plane():
    """schedule_of 未揭晓位面的回退先验逐面锁(统一取语料分布上端 9,R46-1 端点纪律对称化)。

    真值不可判 ⇒ 回退取上端而非众数:horizon 低估通道(fallback 低于真值时
    Δ息流̂/Φ̂ 下偏进不可逆卖面)被端点上界构造性闭合。锁存在性:
    若回退端点被改回众数 7,horizon 低估通道复出即红。
    """
    # 全未揭晓(P1 期首帧前/裸 session):三面统一回退上端 9
    assert _w167_schedule_of(_sess(None)) == (9, 9, 9)
    assert _w167_schedule_of(None) == (9, 9, 9)
    # 部分揭晓:已揭晓位面用 session 表真值,未揭晓位面用逐面先验
    s = _sess(None)
    s.plane_lengths_seen = [9]
    assert _w167_schedule_of(s) == (9, 9, 9)
    s.plane_lengths_seen = [9, 7]
    # 已揭晓面用 session 表真值(P2=7 系本局实测,非回退):回退先验只辖未揭晓面
    assert _w167_schedule_of(s) == (9, 7, 9)
    # P3 进表自适应优先于先验
    s.plane_lengths_seen = [9, 7, 8]
    assert _w167_schedule_of(s) == (9, 7, 8)
    # 脏表守卫:越界值夹 [1, 9]
    s.plane_lengths_seen = [99, 0, 5]
    assert _w167_schedule_of(s) == (9, 1, 5)


# ---------- ② 冻结窗 ----------

def _freeze_frame(plane: int, r: int, table: list[str] | None) -> _w167_plane_rounds_GameState:
    """DOT2 单引擎帧(拆板事务可发射;test_cw_evolution 同构造法)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_line_defs import _CORE_TRIO
    from sr_od.application.currency_war.kernel.cw_state import BenchChar, _recount_board

    def _c(name: str, faction: str) -> BenchChar:
        return BenchChar(slot=0, char_id=name, faction=faction,
                         position_pref=CHARACTERS[name].position_pref())

    st = _w167_plane_rounds_GameState()
    st.plane = plane
    st.round_num = r
    st.gold = 20
    st.level = 8
    st.deployed = [_c(n, '持续伤害') for n in ('桑博', '艾丝妲', '卡芙卡')]
    st.bench = [_c(n, '仙舟') for n in sorted(_CORE_TRIO)]
    st.board = _recount_board(st.deployed)
    return st


def test_final_freeze_p2_r6_now_blocks_dismantle():
    """主修复:P2(表=7)r6 起冻结拆板——旧按 NODES_PER_PLANE=9 判,
    P2 冻结窗是空集(W165 #3 实证)。"""
    sess = _sess(_P2_TABLE)
    st = _freeze_frame(2, 6, _P2_TABLE)
    actions = evolution_step(st, sess, EvolutionState())
    assert not any(isinstance(a, CompTransaction) for a in actions)
    # P2 r5(末窗前)不受辖
    st5 = _freeze_frame(2, 5, _P2_TABLE)
    a5 = evolution_step(st5, sess, EvolutionState())
    assert any(isinstance(a, CompTransaction) for a in a5)


def test_final_freeze_p1_r7_r8_unchanged():
    """P1 逐位回归:表缺(session 未写表,= sim P1 段/开局首帧前)与
    9 槽表两路,r7 不辖 / r8 辖——与旧常量口径逐位同。"""
    for table in (None, _P1_TABLE):
        sess = _sess(table)
        st7 = _freeze_frame(1, 7, table)
        assert any(isinstance(a, CompTransaction)
                   for a in evolution_step(st7, sess, EvolutionState()))
        st8 = _freeze_frame(1, 8, table)
        assert not any(isinstance(a, CompTransaction)
                       for a in evolution_step(st8, sess, EvolutionState()))


# ---------- ③ plane_last_battle / ④ _hard_node ----------

def _node_state(plane: int, r: int, node: str) -> _w167_plane_rounds_GameState:
    st = _w167_plane_rounds_GameState()
    st.plane = plane
    st.round_num = r
    st.node_type = node
    return st


def test_plane_last_battle_p2_boss_at_r7():
    sess2 = _sess(_P2_TABLE)
    assert plane_last_battle(_node_state(2, 7, 'boss'), sess2) is True
    assert plane_last_battle(_node_state(2, 6, 'battle'), sess2) is False
    # P1:表缺与 9 槽表同判(r9 boss 位面末;r8 boss 非位面末——P1 boss@r9)
    for table in (None, _P1_TABLE):
        s = _sess(table)
        assert plane_last_battle(_node_state(1, 9, 'boss'), s) is True
        assert plane_last_battle(_node_state(1, 8, 'boss'), s) is False


def test_hard_node_p2_window_opens_two_rounds_earlier():
    """P2(表=7)remaining≤3 → r5 起战斗节点入窗(旧按 9 需 r7)。"""
    sess2 = _sess(_P2_TABLE)
    assert _hard_node(_node_state(2, 4, 'battle'), sess2) is True   # 7-4=3
    assert _hard_node(_node_state(2, 3, 'battle'), sess2) is False
    for table in (None, _P1_TABLE):
        s = _sess(table)
        assert _hard_node(_node_state(1, 6, 'battle'), s) is True
        assert _hard_node(_node_state(1, 5, 'battle'), s) is False


# ---------- ⑤ final_fence 轮门 ----------

def test_final_fence_p2_last_round_gate():
    """P2 末轮(r7)+boss 窗 → line_opportunistic 非目标件拒(final_fence)。

    直接锁轮门谓词(与 scoring._off_lock_verdict 内联条件同式):
    state.round_num >= nodes_of_plane(session) ∧ boss_window_active。
    """
    from sr_od.application.currency_war.decision.decision_v2.discipline import  boss_window_active
    sess2 = _sess(_P2_TABLE)
    sess2.node_type_current = 'boss'
    reg = _w167_plane_rounds_DEFAULT_REGISTRY
    st = _node_state(2, 7, 'boss')
    assert st.round_num >= nodes_of_plane(sess2)
    assert boss_window_active(st, sess2, reg)
    # r6 非末轮:轮门关(boss 窗开着也不辖——fence 只辖末轮)
    st6 = _node_state(2, 6, 'boss')
    assert not (st6.round_num >= nodes_of_plane(sess2))


# ---------- ⑥ plane_remaining_nodes ----------

def test_plane_remaining_nodes_p2_truth_and_legacy_signature():
    st = _node_state(2, 6, 'battle')
    assert plane_remaining_nodes(st, _sess(_P2_TABLE)) == 2   # 7-6+1
    # 裸调用(旧签名/兼容):回退 P1 先验
    assert plane_remaining_nodes(st) == _w167_plane_rounds_NODES_PER_PLANE - 6 + 1  # = 4
    assert plane_remaining_nodes(_node_state(1, 1, 'battle')) == 9


# ---------- ⑦ _w167_plane_rounds_battles_left_p2 切片 ----------

def test_battles_left_p2_slice_by_table_length():
    reg = _w167_plane_rounds_DEFAULT_REGISTRY
    sess = _sess(_P2_TABLE)
    # r6(r_idx=5):[battle? no——slot6='reward' 除外] → slot5 encounter +
    # slot6 reward 之外…… 表[5:] = ['encounter','reward'] → 1 战斗
    assert _w167_plane_rounds_battles_left_p2(_node_state(2, 6, 'battle'), sess, reg) == 1.0
    assert _w167_plane_rounds_battles_left_p2(_node_state(2, 7, 'boss'), sess, reg) == 1.0
    # r1:全表 battle/battle/supply/battle/encounter/reward/boss → 5 战斗
    assert _w167_plane_rounds_battles_left_p2(_node_state(2, 1, 'battle'), sess, reg) == 5.0
    # 表缺失 → registry 缺省(P1 骨架)
    assert _w167_plane_rounds_battles_left_p2(_node_state(2, 1, 'battle'), _sess(None),
                           reg) == float(reg.battles_left_est)
    # 超长脏表守卫(W154 越界槽不数,ADR-0366 保留):7 槽表 + 脏尾 5 槽,
    # 切片按 _w167_plane_rounds_NODES_PER_PLANE=9 封顶 → 前 9 槽内 5+2=7 战斗,第 10+ 槽不数
    dirty = _sess(list(_P2_TABLE) + ['battle'] * 5)   # 12 槽=脏表
    assert _w167_plane_rounds_battles_left_p2(_node_state(2, 1, 'battle'), dirty,
                           reg) == 7.0


# ==================== w193_p2_combat ====================

import logging as _w193_p2_combat_logging
import random as _w193_p2_combat_random

import pytest as _w193_p2_combat_pytest

from sr_od.application.currency_war.data.cw_battle_tables import P2CombatCalib
from sr_od.application.currency_war.kernel import cw_battle_calib as _w193_p2_combat_cw_battle_calib
from sr_od.application.currency_war.kernel import cw_battle_calib as _calib
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w193_p2_combat_BenchChar, GameState as _w193_p2_combat_GameState
from sr_od.application.currency_war.sim import engine_p1 as _w193_p2_combat_cw_sim
from sr_od.application.currency_war.sim import runner as sim_runner
from sr_od.application.currency_war.sim.checks import calib as _cw_checks
from sr_od.application.currency_war.sim.checks.calib import  check_p2_loss_band_anchor, check_p2_win_rate_band
from sr_od.application.currency_war.sim.engine_p2 import P2ReplayEntry


@_w193_p2_combat_pytest.fixture(autouse=True)
def _w193_p2_combat_quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 logging.disable 是全局态:pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = _w193_p2_combat_logging.root.manager.disable
    _w193_p2_combat_logging.disable(_w193_p2_combat_logging.CRITICAL)
    yield
    _w193_p2_combat_logging.disable(prev)



def _st(engines: int = 0, level: int = 6) -> _w193_p2_combat_GameState:
    st = _w193_p2_combat_GameState()
    st.plane, st.level, st.gold, st.hp = 2, level, 50, 60
    st.deployed = [_w193_p2_combat_BenchChar(slot=i + 1, char_id=f'c{i}',
                             faction='仙舟') for i in range(engines)]
    return st


# ---------- 参数族 ----------

def test_p2_win_p_formula_and_clip() -> None:
    """win_p = clip(p0 + β·form − γ·drift):form/漂移方向 + clip 边界。"""
    calib = P2CombatCalib()          # p0=.11 β=.04 γ=.02 w=.25 base=6
    # form = engines(_settle_rung 口径)+ 0.25*(level-6);相对断言
    # (engines 绝对值由 tier 决定,formula 锁只锁折算项)
    for st in (_st(0, 6), _st(3, 6), _st(0, 8)):
        expect = _calib._settle_rung(st) + 0.25 * (st.level - 6)
        assert abs(_calib.p2_form_key(st, calib) - expect) < 1e-9
    # 绝对锚:仙舟×3(达成仙舟体系,tier 3)→ engines=1,level 折算 0
    assert abs(_calib.p2_form_key(_st(3, 6), calib) - 1.0) < 1e-9
    # r1 drift=0;β 正向(form 1 → +0.04)
    assert abs(_calib.p2_win_p(_st(3, 6), 'battle', 1, calib) - 0.15) < 1e-9
    # 漂移:r4 drift=3 → −0.06
    assert abs(_calib.p2_win_p(_st(3, 6), 'battle', 4, calib) - 0.09) < 1e-9
    # clip 上界:β 大注入不越 0.5
    big = P2CombatCalib(beta=1.0)
    assert _calib.p2_win_p(_st(3, 10), 'battle', 1, big) == big.win_p_clip[1]
    # clip 下界:γ 大注入不为负
    neg = P2CombatCalib(gamma=1.0)
    assert _calib.p2_win_p(_st(0, 5), 'boss', 7, neg) == neg.win_p_clip[0]


def test_p2_loss_band_routing() -> None:
    """分段带路由:battle r1/r2-r3/r4+ 分段;encounter/boss 独立带。"""
    c = P2CombatCalib()
    assert _calib.p2_loss_band('battle', 1, c) == c.band_battle_r1
    assert _calib.p2_loss_band('battle', 2, c) == c.band_battle_early
    assert _calib.p2_loss_band('battle', 3, c) == c.band_battle_early
    assert _calib.p2_loss_band('battle', 4, c) == c.band_battle_late
    assert _calib.p2_loss_band('encounter', 5, c) == c.band_encounter
    assert _calib.p2_loss_band('boss', 7, c) == c.band_boss


def test_p2_combat_delta_distribution() -> None:
    """结算分布域:胜=win_delta 恒值/负=带内均匀(各段独立采样)。"""
    c = P2CombatCalib(p0=1.0, gamma=0.0,
                      win_p_clip=(0.0, 1.0))   # 恒胜臂(无漂移)
    rng = _w193_p2_combat_random.Random(0)
    for _ in range(20):
        d, wp = _w193_p2_combat_cw_battle_calib.p2_combat_delta(_st(), 'boss', 7, rng, c)
        assert d == 2 and wp == 1.0
    c0 = P2CombatCalib(p0=0.0)       # 恒负臂
    for node, rn, band in (('battle', 1, c0.band_battle_r1),
                           ('battle', 4, c0.band_battle_late),
                           ('boss', 7, c0.band_boss)):
        for _ in range(60):
            d, wp = _w193_p2_combat_cw_battle_calib.p2_combat_delta(_st(), node, rn, rng, c0)
            assert wp == 0.0
            assert -band[1] <= d <= -band[0]


# ---------- 结算层接入(planes=2) ----------

def test_calibrated_settlement_in_sim() -> None:
    """calibrated 批:P2 战斗行带 p2_win_p,Δ∈{win_delta}∪负带。"""
    r = engine_p1.simulate_p1(7, pool='snapshot', planes=2)
    assert r.p2_combat_calibrated
    p2 = [row for row in r.ledger if row['plane'] == 2]
    combat = [row for row in p2
              if row['sim']['node'] in ('battle', 'encounter', 'boss')]
    assert combat, 'seed 7 应有 P2 战斗行'
    for row in combat:
        s = row['sim']
        assert s['p2_win_p'] is not None
        lo, hi = _calib.p2_loss_band(s['node'], row['round_num'],
                                     P2CombatCalib())
        assert s['delta'] == P2CombatCalib().win_delta \
            or -hi <= s['delta'] <= -lo


def test_flag_off_returns_legacy_byte_identical() -> None:
    """calibrated=False:P2 结算逐位回 legacy(p2_win_p=None,
    Δ池 plane=2 优先路径),P1 段与 on 臂逐位零漂移。"""
    off = P2CombatCalib(calibrated=False)
    r_off = engine_p1.simulate_p1(7, pool='snapshot', planes=2, p2_combat=off)
    r_on = engine_p1.simulate_p1(7, pool='snapshot', planes=2)
    assert not r_off.p2_combat_calibrated
    for row in r_off.ledger:
        if row['plane'] == 2:
            assert row['sim']['p2_win_p'] is None
    # P1 段零漂移(两臂 rng 序在 P1 段相同;稳定字段投影——
    # v3_intention.tracks 活引用见 test_event_gold_dual_arm_paired)
    proj = lambda r: [  # noqa: E731
        (x['ts'], x['hp'], x['gold'], x['actions'], x['sim']['delta'])
        for x in r.ledger if x['plane'] == 1]
    assert proj(r_off) == proj(r_on)
    assert [e for e in r_off.hp_events if e[0] <= 9] == \
        [e for e in r_on.hp_events if e[0] <= 9]


def test_event_gold_dual_arm_paired() -> None:
    """事件金双臂:zero 臂 P2 段 income.event=0,P1 段两臂逐位同
    (rng 同耗——双臂同 seed 配对可比,W186 §3 K3)。P1 对比用稳定
    字段投影(v3_intention.tracks 是活引用,P2 段会原地改 P1 行)。"""
    zero = P2CombatCalib(event_gold='zero')
    r0 = engine_p1.simulate_p1(3, pool='snapshot', planes=2, p2_combat=zero)
    r1 = engine_p1.simulate_p1(3, pool='snapshot', planes=2)
    proj = lambda r: [  # noqa: E731
        (x['ts'], x['hp'], x['gold'], x['actions'],
         x['sim']['delta'], x['sim']['income'])
        for x in r.ledger if x['plane'] == 1]
    assert proj(r0) == proj(r1)
    for row in r0.ledger:
        if row['plane'] == 2:
            assert row['sim']['income']['event'] == 0


# ---------- 案 b 臂 ----------

def test_replay_entry_shared_loop_and_inheritance() -> None:
    """案 b 臂:共享 simulate_p1 循环体(账本 plane=2/ts 从 1 起/
    节点序列=P2_NODE_SEQUENCE)+ 进场态继承(hp/gold/board/deployed)。"""
    e = P2ReplayEntry(
        hp=52, gold=40, level=6, board={'仙舟': 3},
        bench=[{'char_id': '三月七', 'faction': '列车同行'}],
        deployed=[{'char_id': '丹恒·饮月', 'faction': '仙舟',
                   'star': 2, 'equips': ['星徽']}],
        equips=['卡带'], xp=3, xp_progress=(3, 4), streak=1,
        locked_comp='列车同行')
    r = engine_p2.simulate_p2_replay_entry(e, 11, pool='snapshot')
    assert r.p2_entered and r.p2_combat_calibrated
    p2 = [row for row in r.ledger if (row.get('plane') or 1) == 2]
    assert p2 and all(row['plane'] == 2 for row in r.ledger)
    assert p2[0]['ts'] == 1                    # 无 P1 段,ts 从 1 起
    assert [row['sim']['node'] for row in p2] == \
        list(engine_p1.P2_NODE_SEQUENCE)[:len(p2)]
    assert r.p2_rounds == len(p2)
    # 进场继承:首行结算前 hp = entry.hp(行 hp 为结算后,由 Δ 回推)
    assert 0 <= p2[0]['hp'] - 52 - p2[0]['sim']['delta'] <= 2 \
        or p2[0]['hp'] <= 52    # 死局钳制兜底
    st0 = e.build_state()
    assert st0.hp == 52 and st0.gold == 40 and st0.plane == 2
    _first = next(d for d in st0.deployed if d is not None)   # ADR-0392 槽位表
    assert _first.star == 2 and _first.equips == ['星徽']
    assert st0.bench[0] is not None and st0.bench[1] is None  # 9 槽 pad


def test_replay_entry_rejects_invest() -> None:
    """案 b 臂不支持 invest 注入(显式拒绝,防语义混叠)。"""
    e = P2ReplayEntry(hp=50, gold=30, level=6)
    try:
        engine_p1.simulate_p1(0, pool='fallback', invest=True, _p2_entry=e)
    except ValueError as ex:
        assert '案 b' in str(ex)
    else:
        raise AssertionError('invest+_p2_entry 应显式 raise')


# ---------- headline 扩展 + 检查器 ----------

def test_batch_headline_extension_keys() -> None:
    """批报告 P2 判读扩展键在位(形状锁,不锁分布数值)。"""
    rep = sim_runner.simulate_p1_batch(10, pool='snapshot', planes=2,
                                   ledger=False)
    for k in ('p2_combat_calibrated', 'avg_p2_gold_carried',
              'p2_carry_buys', 'avg_p2_carry_buys', 'p2_switch_rate',
              'avg_p2_first_switch_round', 'p2_lv7_reach_rate',
              'p2_calib'):
        assert k in rep, f'缺键: {k}'
    assert rep['p2_combat_calibrated'] is True
    assert set(rep['p2_carry_buys']) == {'1-2', '3', '4-5'}
    cv = rep['checks_violations']
    for k in ('p2_loss_band_anchor', 'p2_win_rate_band'):
        assert k in cv and cv[k]['violations'] == 0, (k, cv.get(k))
    # 本测试 n=10(~40 行)<P2_WIN_RATE_MIN_JUDGE_ROWS:胜率带锚在此
    # 口径只披露不判(violations 恒 0),判读面由单元测试+变异探针辖


def test_result_observation_derivation() -> None:
    """单局观测派生:价格带笔数/意向切换/lv 到达轮由账本 P2 行派生。"""
    e = P2ReplayEntry(hp=80, gold=100, level=5, board={'仙舟': 3})
    r = engine_p2.simulate_p2_replay_entry(e, 42, pool='snapshot')
    p2 = [row for row in r.ledger if row['plane'] == 2]
    buys = sum(r.p2_buys_by_cost.values())
    ledger_buys = sum(1 for row in p2 for a in row['actions']
                      if a.get('__type__') == 'BuyCard')
    assert buys == ledger_buys
    lv6 = next((row['round_num'] for row in p2
                if (row['state'].get('level') or 0) >= 6), None)
    assert r.p2_lv6_round == lv6
    if r.p2_hp0:
        assert r.p2_gold_carried == p2[-1]['gold']
    else:
        assert r.p2_gold_carried is None


def test_check_p2_loss_band_anchor_unit() -> None:
    """带锚检查:带外 Δ 涌现 / 胜=win_delta / uncalibrated 跳过。"""
    bands = {'battle_r1': [14, 28], 'battle_early': [4, 16],
             'battle_late': [15, 25], 'encounter': [9, 18],
             'boss': [21, 26]}
    report = {'p2_combat_calibrated': True,
              'p2_calib': {'bands': bands, 'win_delta': 2}}
    bad = [[{'plane': 2, 'round_num': 1,
             'sim': {'node': 'battle', 'delta': -50, 'p2_win_p': 0.1}}]]
    rep = check_p2_loss_band_anchor(bad, report=report)
    assert rep['violations'] == 1
    ok = [[{'plane': 2, 'round_num': 1,
            'sim': {'node': 'battle', 'delta': 2, 'p2_win_p': 0.1}},
           {'plane': 2, 'round_num': 2,
            'sim': {'node': 'battle', 'delta': -10, 'p2_win_p': 0.1}}]]
    assert check_p2_loss_band_anchor(ok, report=report)['violations'] == 0
    # uncalibrated 批恒绿跳过;reward 行不辖
    assert check_p2_loss_band_anchor(
        bad, report={'p2_combat_calibrated': False})['violations'] == 0
    reward = [[{'plane': 2, 'round_num': 3,
                'sim': {'node': 'supply', 'delta': 2, 'p2_win_p': None}}]]
    assert check_p2_loss_band_anchor(
        reward, report=report)['violations'] == 0


def test_check_p2_win_rate_band_unit() -> None:
    """胜率锚:聚合胜率带外涌现(样本 ≥P2_WIN_RATE_MIN_JUDGE_ROWS 才判,
    小样本只披露不判)/uncalibrated 跳过。"""
    def row(w: bool) -> dict:
        return {'plane': 2, 'round_num': 1, 'sim': {
            'node': 'battle', 'p2_win_p': 0.1,
            'delta': 2 if w else -16}}
    hot = [[row(True)] * 120]
    rep = check_p2_win_rate_band(
        hot, report={'p2_combat_calibrated': True})
    assert rep['violations'] == 1 and rep['win_rate'] == 1.0
    # 判读门槛临界定:行数差 1 即「只披露不判」(violations 恒 0)——
    # n=10 局批(~40 行)σ≈0.085,判读只挂大样本窗
    edge = [[row(True)] * (_cw_checks.P2_WIN_RATE_MIN_JUDGE_ROWS - 1)]
    rep_edge = check_p2_win_rate_band(
        edge, report={'p2_combat_calibrated': True})
    assert rep_edge['violations'] == 0 and rep_edge['win_rate'] == 1.0
    cold = [[row(False)] * 105]
    assert check_p2_win_rate_band(
        cold, report={'p2_combat_calibrated': True})['violations'] == 0
    assert check_p2_win_rate_band(
        hot, report={'p2_combat_calibrated': False})['violations'] == 0


def test_mutation_probe_settlement_bypass(monkeypatch) -> None:
    """变异探针锁(检查非空转):结算层被换成 legacy 常数带(15-17)
    而批仍报 calibrated → 带锚违规必须涌现(防御「校准层被绕过」
    回归——正是本检查的存在理由)。"""
    def _broken(st, node, round_num, rng, calib):
        return (-50, 0.11)   # 全带外(最宽带 hi=28)
    monkeypatch.setattr(_w193_p2_combat_cw_sim, 'p2_combat_delta', _broken)
    rep = sim_runner.simulate_p1_batch(8, pool='snapshot', planes=2,
                                   ledger=False, seed_base=100)
    cv = rep['checks_violations']['p2_loss_band_anchor']
    assert cv['violations'] > 0, '变异(结算绕过参数族)未涌现违规'


def test_mutation_probe_win_rate_explosion(monkeypatch) -> None:
    """变异探针锁:胜率模型失控(clip 被绕过)→ 胜率锚违规涌现。
    批取 n=30(~120 战斗行)以过 P2_WIN_RATE_MIN_JUDGE_ROWS 判读门槛
    (门槛以下只披露不判,变异不会涌现)。"""
    def _broken(st, node, round_num, rng, calib):
        return (2, 0.9)
    monkeypatch.setattr(_w193_p2_combat_cw_sim, 'p2_combat_delta', _broken)
    rep = sim_runner.simulate_p1_batch(30, pool='snapshot', planes=2,
                                   ledger=False, seed_base=100)
    cv = rep['checks_violations']['p2_win_rate_band']
    assert cv['violations'] > 0, '变异(胜率失控)未涌现违规'


# ---------- 敏感性入口 ----------

def test_sensitivity_report_shape() -> None:
    """敏感性扫描入口:网格形状 + 判读 headline 键(n 取最小)。"""
    rep = sim_runner.simulate_p2_sensitivity(
        3, pool='snapshot', betas=(0.0, 0.04), gammas=(0.0, 0.02),
        event_gold_arms=('p1',))
    assert rep['n'] == 3 and len(rep['grid']) == 4
    for cell in rep['grid']:
        for k in ('event_gold', 'beta', 'gamma', 'avg_p2_rounds',
                  'p2_win_rate', 'p2_hp0_rate', 'avg_p2_gold_carried',
                  'avg_final_hp'):
            assert k in cell
    assert rep['pool_fingerprint']


# 文件尾 import(既有模式):engine 模块以模块属性形态被 monkeypatch 锁
# 按址引用,置于文件尾不影响语义(测试不依赖其导入时点)
from sr_od.application.currency_war.sim import engine_p1, engine_p2  # noqa: E402


# ==================== w194_p2_multihit ====================

import dataclasses as _w194_p2_multihit_dataclasses
import json as _w194_p2_multihit_json
import logging as _w194_p2_multihit_logging

import pytest as _w194_p2_multihit_pytest

from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w194_p2_multihit_StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import  ArbiterResult, _steady_levelup_pass, arbitrate
from sr_od.application.currency_war.decision.decision_v2.remediation import  steady_state_levelup_group
from sr_od.application.currency_war.kernel.cw_intention import  IntentionState as _w194_p2_multihit_IntentionState, LineTrack, serialize_intention
from sr_od.application.currency_war.kernel.cw_registry import  DEFAULT_REGISTRY as _w194_p2_multihit_DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w194_p2_multihit_BenchChar, GameState as _w194_p2_multihit_GameState


@_w194_p2_multihit_pytest.fixture(autouse=True)
def _w194_p2_multihit_quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 logging.disable 是全局态:pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = _w194_p2_multihit_logging.root.manager.disable
    _w194_p2_multihit_logging.disable(_w194_p2_multihit_logging.CRITICAL)
    yield
    _w194_p2_multihit_logging.disable(prev)


# 注入「press 通道关」注册表:press 通道已正式开臂(commit cb7688d4,
# press_channel_enabled 默认 True),同档/1费买改由 press_floor_exempt
# 前置臂授权。本文件锁的是 P2 核心首件门自身的辖域与轮计数,注入关臂
# 隔离该前置臂。
_REG_NO_PRESS = _w194_p2_multihit_dataclasses.replace(_w194_p2_multihit_DEFAULT_REGISTRY,
                                    press_channel_enabled=False)

_ENGINE = '希儿'          # engine_char_names 成员(_target_names 恒含)
_NON_TARGET = '散件'       # 注册表外名(不在目标集)


def _steady_state(level: int = 6, xp: int = 16, gold: int = 108,
                  node: str = 'battle') -> _w194_p2_multihit_GameState:
    """[33] 稳态帧:cap=level 满员 + bench 躺方向件(run15 P2 型)。"""
    st = _w194_p2_multihit_GameState()
    st.plane, st.level, st.gold, st.hp = 2, level, gold, 60
    st.node_type = node
    st.deployed = [_w194_p2_multihit_BenchChar(slot=i + 1, char_id=f'c{i}', faction='仙舟')
                   for i in range(level)]
    st.bench[0] = _w194_p2_multihit_BenchChar(slot=1, char_id=_ENGINE, faction='量子')
    st.xp_progress = (xp, {6: 40, 7: 52}.get(level, 40))
    return st


# ---------- 稳态多击组:构造判据 ----------

def test_steady_group_emits_clicks_to_next_level() -> None:
    """稳态帧:lv6 xp16/40 → 余 24 XP = 6 击,auth_basis 非空。"""
    sess = _w194_p2_multihit_StrategySession()
    acts = steady_state_levelup_group(
        _steady_state().copy(), _steady_state(), sess, _w194_p2_multihit_DEFAULT_REGISTRY)
    assert len(acts) == 6
    assert all(a.cost == 4 and a.auth_basis == 'pop_slot' for a in acts)


def test_steady_group_guards() -> None:
    """五路挡:flag off / P1 不辖 / cap 未满 / bench 无方向件
    / 已跨级。

    (旧「boss 轮不发」断言随 W255/ADR-0410 过期:boss 升级禁令删除,
    稳态组在 boss 轮改由 EV 总账裁决——boss 帧放行面见 test_cw_w255 锁
    与 ADR-0410 ②;其余守卫语义不变。)"""
    sess = _w194_p2_multihit_StrategySession()
    st = _steady_state()
    reg_off = _w194_p2_multihit_dataclasses.replace(_w194_p2_multihit_DEFAULT_REGISTRY,
                                  levelup_multihit_enabled=False)
    assert steady_state_levelup_group(
        st.copy(), st, sess, reg_off) == []          # flag off 回 W193 后
    p1 = _steady_state()
    p1.plane = 1
    assert steady_state_levelup_group(
        p1.copy(), p1, sess, _w194_p2_multihit_DEFAULT_REGISTRY) == []  # P1 不辖(辙回:
    # 全位面泛化 n=300 引入 never2 9→10 回归;P1 已有补偿臂覆盖)
    not_full = _steady_state()
    not_full.deployed = not_full.deployed[:-1]
    assert steady_state_levelup_group(
        not_full.copy(), not_full, sess, _w194_p2_multihit_DEFAULT_REGISTRY) == []  # [32](b)
    no_dir = _steady_state()
    no_dir.bench[0] = _w194_p2_multihit_BenchChar(slot=1, char_id=_NON_TARGET, faction='?')
    assert steady_state_levelup_group(
        no_dir.copy(), no_dir, sess, _w194_p2_multihit_DEFAULT_REGISTRY) == []
    crossed = _steady_state(xp=40)
    assert steady_state_levelup_group(
        crossed.copy(), crossed, sess, _w194_p2_multihit_DEFAULT_REGISTRY) == []


def test_steady_group_ev_affordability_gate() -> None:
    """EV 总账拒:金 < n×总价(可负担性 after<0)→ 整组不发。"""
    sess = _w194_p2_multihit_StrategySession()
    st = _steady_state(gold=20)      # 6 击 24 金 → after=-4
    assert steady_state_levelup_group(
        st.copy(), st, sess, _w194_p2_multihit_DEFAULT_REGISTRY) == []


# ---------- 稳态多击组:arbiter 趟 ----------

def test_steady_pass_inserts_group_and_round_key() -> None:
    """arbiter 趟:组进 actions + 轮键置位(二次调用 no-op)+
    working 推进(金扣 24)。"""
    sess = _w194_p2_multihit_StrategySession()
    st = _steady_state()
    res = ArbiterResult()
    wk = _steady_levelup_pass(st.copy(), st, sess, _w194_p2_multihit_DEFAULT_REGISTRY, res)
    assert len(res.actions) == 6
    assert sess.v2_steady_lv_used
    assert wk.gold == st.gold - 24
    res2 = ArbiterResult()
    wk2 = _steady_levelup_pass(wk.copy(), st, sess, _w194_p2_multihit_DEFAULT_REGISTRY, res2)
    assert res2.actions == [] and wk2.gold == wk.gold   # 轮键单组


def test_steady_pass_transactional_abandon() -> None:
    """事务性重验失败整组放弃:FORM 地板 20 下第 4 击(金 23→19
    <20)→ 放弃计数 + 无动作 + working 不动。"""
    sess = _w194_p2_multihit_StrategySession()
    st = _steady_state(gold=35)       # 6 击 24 金:前 3 击过,第 4 击破地板
    res = ArbiterResult()
    wk = _steady_levelup_pass(st.copy(), st, sess, _w194_p2_multihit_DEFAULT_REGISTRY, res)
    assert res.actions == []
    assert sess.v3_steady_lv_abandoned == 1
    assert wk.gold == st.gold


def test_steady_pass_inserts_before_refresh() -> None:
    """插入位:组插在已采纳 RefreshShop 之前(旧店段语义)。"""
    from sr_od.application.currency_war.kernel.cw_state import RefreshShop
    sess = _w194_p2_multihit_StrategySession()
    st = _steady_state()
    res = ArbiterResult()
    res.actions = [RefreshShop(cost=2)]
    _steady_levelup_pass(st.copy(), st, sess, _w194_p2_multihit_DEFAULT_REGISTRY, res)
    assert type(res.actions[0]).__name__ == 'LevelUp'
    assert type(res.actions[-1]).__name__ == 'RefreshShop'


def test_arbitrate_end_to_end_steady_group() -> None:
    """arbitrate 空候选直调:稳态组仍发(不依赖拒绝事件——Catch-22
    根治的构造性证明)。"""
    sess = _w194_p2_multihit_StrategySession()
    st = _steady_state()
    res = arbitrate([], st, sess, _w194_p2_multihit_DEFAULT_REGISTRY)
    lv = [a for a in res.actions if type(a).__name__ == 'LevelUp']
    assert len(lv) == 6


# ---------- tracks 活引用深拷贝 ----------

def test_serialize_intention_tracks_snapshot() -> None:
    """快照语义:serialize 后原地改 LineTrack/增删键,已落账 dict 不变。"""
    ist = _w194_p2_multihit_IntentionState(phase='locked', locked_comp='x',
                         p1_pair=('仙舟', '列车同行'))
    ist.tracks['dot'] = LineTrack(miss_count=1, frozen_rounds=2)
    snap = serialize_intention(ist)
    # 深拷贝防线:后续原地改写不污染
    ist.tracks['dot'].miss_count = 99
    ist.tracks['dot'].frozen_rounds = 99
    ist.tracks['new'] = LineTrack()
    assert snap['tracks'] == {'dot': {'miss_count': 1, 'frozen_rounds': 2}}
    # tuple 字段不可变:类型不漂移(快照=原值)
    assert snap['p1_pair'] == ('仙舟', '列车同行')


def test_serialize_intention_json_safe() -> None:
    """tracks 值为纯 dict(JSON 可序列化——旧版 LineTrack 裸引用
    会让 json.dumps 抛 TypeError)。"""
    ist = _w194_p2_multihit_IntentionState()
    ist.tracks['dot'] = LineTrack(miss_count=3)
    _w194_p2_multihit_json.dumps(serialize_intention(ist))   # 不抛即过


def test_sim_p1_rows_tracks_unpolluted() -> None:
    """sim 集成:planes=2 单局,P1 行 v3_intention 全 JSON 可序列化
    且 tracks 为快照(修复前=活引用,P2 段原地改写污染 P1 行)。"""
    from sr_od.application.currency_war.sim import engine_p1 as cw_sim
    r = cw_sim.simulate_p1(3, pool='fallback', planes=2)
    p1_rows = [row for row in r.ledger if row.get('plane', 1) == 1]
    assert p1_rows
    for row in p1_rows:
        ist = row['v3_intention']
        if ist is None:
            continue
        _w194_p2_multihit_json.dumps(ist)
        for track in (ist.get('tracks') or {}).values():
            assert isinstance(track, dict)   # 非 LineTrack 活引用


# ---------- 件3:P2 核心件首件同息档买入门(W183 方向②)----------

def _p2_sess(core: str = '姬子·启行') -> StrategySession:
    s = _w194_p2_multihit_StrategySession()
    s.v3_mode = 'economy'
    s.v2_round_key = (2, 3)
    s.v2_round_p2_core = 0
    s.v3_core_names = {core}
    return s


def _w194_p2_multihit_p2_state(gold: int = 8, level: int = 6) -> _w194_p2_multihit_GameState:
    """P2 穷轮帧(W194 探针形态:HOARD 金<50,核心 3费在店)。"""
    st = _steady_state(level=level, gold=gold)
    st.bench[0] = None
    return st


def _core_cand(name: str = '姬子·启行', cost: int = 3) -> object:
    from sr_od.application.currency_war.decision.decision_v2.candidates import  Candidate
    from sr_od.application.currency_war.kernel.cw_state import BuyCard, ShopCard
    return Candidate(
        action=BuyCard(ShopCard(name=name, faction='列车同行',
                                cost=cost, x=0, star=1), reason=''),
        tag='line_carry', source='shop')


def test_p2_core_firstpiece_exempt_passes() -> None:
    """主锁:P2 金 8 买 3费核心首件 → 同息档(8→5)放行 + auth trace。"""
    from sr_od.application.currency_war.decision.decision_v2.arbiter import  _p2_core_firstpiece_exempt as ex
    sess = _p2_sess()
    st = _w194_p2_multihit_p2_state(gold=8)
    auth: dict = {}
    assert ex(_core_cand(), st.copy(), st, sess, _w194_p2_multihit_DEFAULT_REGISTRY, auth)
    assert 'p2_core' in auth


def test_p2_core_firstpiece_guards() -> None:
    """六路挡:P1 / 非核心 / 已持有(working)/ 跨息档 / flag off /
    单轮上限耗尽 / boss 轮。"""
    from sr_od.application.currency_war.decision.decision_v2.arbiter import  _p2_core_firstpiece_exempt as ex
    sess = _p2_sess()
    st = _w194_p2_multihit_p2_state(gold=8)
    p1 = _w194_p2_multihit_p2_state(gold=8)
    p1.plane = 1
    assert not ex(_core_cand(), p1.copy(), p1, sess, _w194_p2_multihit_DEFAULT_REGISTRY)
    assert not ex(_core_cand('散件'), st.copy(), st, sess,
                  _w194_p2_multihit_DEFAULT_REGISTRY)
    owned = st.copy()
    owned.bench[0] = _w194_p2_multihit_BenchChar(slot=1, char_id='姬子·启行',
                               faction='列车同行')
    assert not ex(_core_cand(), owned, st, sess, _w194_p2_multihit_DEFAULT_REGISTRY)
    assert not ex(_core_cand(cost=5), _w194_p2_multihit_p2_state(gold=12).copy(),
                  _w194_p2_multihit_p2_state(gold=12), sess, _w194_p2_multihit_DEFAULT_REGISTRY)  # 12→7 跨档
    reg_off = _w194_p2_multihit_dataclasses.replace(_w194_p2_multihit_DEFAULT_REGISTRY,
                                  p2_core_firstpiece_enabled=False)
    assert not ex(_core_cand(), st.copy(), st, sess, reg_off)
    capped = _p2_sess()
    capped.v2_round_p2_core = 1
    assert not ex(_core_cand(), st.copy(), st, capped, _w194_p2_multihit_DEFAULT_REGISTRY)
    boss = _w194_p2_multihit_p2_state(gold=8)
    boss.node_type = 'boss'
    assert not ex(_core_cand(), boss.copy(), boss, sess, _w194_p2_multihit_DEFAULT_REGISTRY)


def test_p2_core_firstpiece_arbitrate_counter() -> None:
    """端到端:arbitrate 采纳后 session.v2_round_p2_core 计数(单轮上限
    数据源)+ 第二笔同轮拒。"""
    sess = _p2_sess()
    st = _w194_p2_multihit_p2_state(gold=8)
    st.shop = []
    cand = _core_cand()
    scored = [(cand, 5.0, {})]
    res = arbitrate(scored, st, sess, _REG_NO_PRESS)
    assert len(res.actions) == 1
    assert sess.v2_round_p2_core == 1
    # 同轮第二笔(跨档外的同档帧也拒——上限耗尽)
    res2 = arbitrate([(cand, 5.0, {})], st, sess, _REG_NO_PRESS)
    assert res2.actions == []


# ==================== w370_p2_loss_recalib ====================

import dataclasses as _w370_p2_loss_recalib_dataclasses

import pytest as _w370_p2_loss_recalib_pytest

from sr_od.application.currency_war.kernel import cw_plane_table
from sr_od.application.currency_war.kernel.cw_registry import  DEFAULT_REGISTRY as _w370_p2_loss_recalib_DEFAULT_REGISTRY

# 标定值单一源(cw_sim_checks 同值消费禁令:本文件只锁值,不做第二份推导)
_VD_P2_LOSS_CALIB = 20.05    # w354_p2_loss_calib.json p2|normal mean(条件伤害)
_W375_COND = {'normal': 12.77, 'encounter': 13.33,
              'boss': 15.50, 'reward': 0.0}


def test_vd_p2_loss_calibrated_value() -> None:
    """①scoring 侧重校值锁。"""
    assert _w370_p2_loss_recalib_DEFAULT_REGISTRY.vd_p2_loss == _VD_P2_LOSS_CALIB


def test_w375_tables_injected() -> None:
    """②两表值锁(无条件期望/条件败面各归其消费面;版本锚 v1)。"""
    assert _w370_p2_loss_recalib_DEFAULT_REGISTRY.p2_node_loss_table == {
        'normal': 10.16, 'encounter': 12.00,
        'boss': 15.50, 'reward': 0.0}
    assert _w370_p2_loss_recalib_DEFAULT_REGISTRY.p2_cond_loss_table == _W375_COND
    assert _w370_p2_loss_recalib_DEFAULT_REGISTRY.p2_loss_calib_version == 1


def test_two_state_pwin_interpolation() -> None:
    """③板强→胜率映射形态:锚点逐位=表值、分段线性、b>2 钳 rung2
    (与 p_win 表 k3 折叠同口径;单一源=cw_plane_table.p_win_p2)。"""
    assert cw_plane_table.p_win_p2(0.0) == _w370_p2_loss_recalib_DEFAULT_REGISTRY.p_win_p2_by_rung[0]
    assert cw_plane_table.p_win_p2(1.0) == _w370_p2_loss_recalib_DEFAULT_REGISTRY.p_win_p2_by_rung[1]
    assert cw_plane_table.p_win_p2(2.0) == _w370_p2_loss_recalib_DEFAULT_REGISTRY.p_win_p2_by_rung[2]
    assert cw_plane_table.p_win_p2(2.9) == cw_plane_table.p_win_p2(2.0), \
        'b>2 钳 rung2'
    mid = cw_plane_table.p_win_p2(1.5)
    expect = 0.5 * (_w370_p2_loss_recalib_DEFAULT_REGISTRY.p_win_p2_by_rung[1]
                    + _w370_p2_loss_recalib_DEFAULT_REGISTRY.p_win_p2_by_rung[2])
    assert mid == _w370_p2_loss_recalib_pytest.approx(expect)


def test_threshold_shares_calibration_with_pwin(monkeypatch) -> None:
    """④阈值层与胜率侧同标定源(双源合一不变量):_loss_dist P2 μ 的条件
    档同用 registry.p2_cond_loss_table——注入自定义条件档,阈值层 μ
    与 (1−p)·注入值闭环位移(改动标定面两处同步,防回植本地乘数)。"""
    from sr_od.application.currency_war.kernel import cw_registry as reg_mod
    from sr_od.application.currency_war.kernel.cw_first_passage import _loss_dist
    reg = _w370_p2_loss_recalib_dataclasses.replace(
        reg_mod.DEFAULT_REGISTRY, p2_cond_loss_table={
            'normal': 5.0, 'encounter': 5.0, 'boss': 5.0, 'reward': 0.0})
    monkeypatch.setattr(reg_mod, 'DEFAULT_REGISTRY', reg)
    mu = _loss_dist(2, 2)[1][0]
    assert mu == _w370_p2_loss_recalib_pytest.approx(
        (1.0 - cw_plane_table.p_win_p2(2)) * 5.0, abs=1e-9)


def test_p2_loss_scale_constant_retired() -> None:
    """⑤确定性折中常量退役锁:旧 P2_LOSS_SCALE=6.0 在存活模块
    (标定表/胜率映射/registry)不复存在(见 ADR-0440)。"""
    assert not hasattr(cw_plane_table, 'P2_LOSS_SCALE')
    assert not hasattr(_w370_p2_loss_recalib_DEFAULT_REGISTRY, 'P2_LOSS_SCALE')


# ==================== (w413_p2_two_state_injection 已随 C4 开关族删除) ====================
# (两态注入/零漂移/消费/rung 坐标锁段已随 rounds_two_state_enabled 开关族
#  删除——旧方案清退批,清查报告 OLD_MIX_AUDIT §1.3;p_win_p2_by_rung 表
#  保留(阈值层 cw_plane_table.p_win_p2 消费),结构锁由 adr0293 面册承载。)
# ==================== p2_survival_band ====================

from sr_od.application.currency_war.kernel.cw_state import GameState as _p2_survival_band_GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _p2_survival_band_StrategySession
from sr_od.application.currency_war.decision.decision_v2.filters import  _deploy_free, _deploy_free_after_merge, _refreshable_names
from sr_od.application.currency_war.kernel.cw_registry import  DEFAULT_REGISTRY as _p2_survival_band_DEFAULT_REGISTRY

#: P2 满表投影夹具(economy.md §10.2 模板,boss@末槽)
_p2_survival_band_P2_FULL_TABLE = ['battle', 'battle', 'encounter', 'reward',
                 'encounter', 'reward', 'boss']


def _dying_state(**kw) -> _p2_survival_band_GameState:
    """P2 帧夹具:plane=2、r3、hp 可读(C4 投影/守卫锁共用底座)。"""
    base = {
        'plane': 2, 'round_num': 3, 'gold': 30, 'level': 5,
        'hp': 20, 'hp_readable': True,
        'board': {}, 'deployed': [], 'bench': [], 'shop': [],
    }
    base.update(kw)
    return _p2_survival_band_GameState(**base)


def _tabled_session(round_num: int = 1,
                    table: list[str] | None = None) -> _p2_survival_band_StrategySession:
    sess = _p2_survival_band_StrategySession()
    sess.plane_node_table = list(table or _p2_survival_band_P2_FULL_TABLE)
    sess.plane_node_table_plane = 2
    sess.round_num = round_num
    return sess


# --- 定谳清理卫生锁:C3 删除面不复存在 + 共享面健在 ---------------------------


def test_c3_symbols_removed_from_registry() -> None:
    """C3 定谳清理(ADR-0426 增补节):总开关与 C3 专属字段不再存在于
    registry——死概念不留「开关还在」的错误信号。"""
    assert not hasattr(_p2_survival_band_DEFAULT_REGISTRY, 'dying_band_account_enabled')
    assert not hasattr(_p2_survival_band_DEFAULT_REGISTRY, 'dying_band_high_cost_floor')
    assert hasattr(_p2_survival_band_DEFAULT_REGISTRY, 'directed_refresh_high_cost_floor')



def test_shared_face_helpers_alive_for_c1() -> None:
    """C1 判据共享面健在锁:部署空位/合成后空位/刷新名集/hp 可信位
    守卫四组符号仍在且可执行(C1 仍处演进中,清理批只删 C3 专属)。"""
    from sr_od.application.currency_war.decision.decision_v2.posture_release import  hp_decision_trusted
    st = _dying_state()
    sess = _p2_survival_band_StrategySession()
    assert _deploy_free(st) == st.max_units()
    assert isinstance(_refreshable_names(st, sess, _p2_survival_band_DEFAULT_REGISTRY),
                      frozenset) and _refreshable_names(st, sess,
                                                        _p2_survival_band_DEFAULT_REGISTRY)
    assert hp_decision_trusted(st) is True
    # 合成后空位完备式:板上 2 份同名 1★ + 买入合成 → 净腾 1 位
    from sr_od.application.currency_war.kernel.cw_state import BenchChar, ShopCard
    card = ShopCard(name='件甲', faction='仙舟罗浮', cost=1, x=0, star=1)
    st2 = _dying_state(
        deployed=[BenchChar(slot=i, char_id='件甲', faction='仙舟罗浮',
                            star=1, position_pref='front')
                  for i in range(st.max_units())])
    from sr_od.application.currency_war.decision.decision_v2.candidates import  Candidate
    from sr_od.application.currency_war.kernel.cw_state import BuyCard
    merge_c = Candidate(action=BuyCard(card, reason=''), tag='bridge_core',
                        source='shop', merge=True)
    assert _deploy_free_after_merge(merge_c, st2) == 1


# --- (C4:存活轮数门锁段已随 C4 开关族删除——旧方案清退批,清查报告
#     OLD_MIX_AUDIT §1.3;rounds_alive/survival_gate 同批删。)
# ==================== w857_plane_intel_skip ====================

def test_decide_plane_skip_truth_table() -> None:
    """skip 判据真值表(2026-09-03 用户裁决改写:起始位面裁剪,取代旧
    「session 位面+台账缺值降级补采」语义——已通过位面变暗不重采)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_intel import  decide_plane_skip

    # 过去位面(位面号 < start_plane)→ 跳过
    skip, note = decide_plane_skip(1, 2)
    assert skip is True
    assert '跳过' in note
    skip, _ = decide_plane_skip(2, 3)
    assert skip is True
    # 当前位面 → 采集;未来位面 → 采集
    assert decide_plane_skip(2, 2) == (False, '')
    assert decide_plane_skip(3, 2) == (False, '')
    # 起始位面无真值(None/0)→ 不跳,全采回退(备战识别失败保底)
    assert decide_plane_skip(1, None) == (False, '')
    assert decide_plane_skip(1, 0) == (False, '')


def test_collect_loop_has_skip_filter_and_per_plane_logs() -> None:
    """采集循环接线锁:skip 过滤被调用 + 逐位面「采集/跳过/耗时」日志落地
    (观测缺口补齐:用户观察到的停留必须能从日志诊断)。"""
    import inspect

    from sr_od.application.currency_war.operations.cw_screen import cw_screen_plane_intel

    src = inspect.getsource(cw_screen_plane_intel.CwScreenPlaneIntel)
    assert 'decide_plane_skip(' in src, '采集循环未接 skip 判据'
    assert '跳过(已通过位面)' in src, '采集循环缺跳过日志(观测缺口)'
    assert '采集完成(耗时' in src, '采集循环缺逐位面耗时日志(观测缺口)'
    assert '_session_plane' in src, '采集循环缺会话位面真值读取'
    # 跳过位面不进 _detail_seqs → close_and_report 不覆写其台账值(保留语义)
    assert 'self._detail_seqs[self._cur_plane + 1]' in src, (
        '详情条序列写入点漂移,跳过位面「不覆写」契约失去载体')


def test_observation_docstring_annotates_dimmed_state() -> None:
    """读法注释锁:位面详情节点条读法须标注「过去位面变暗渲染识别退化」
    (防止后续改动把变暗态当识别 bug 误修,而非 skip 语义覆盖)。"""
    import inspect

    from sr_od.application.currency_war.obs import cw_observation

    doc = inspect.getdoc(cw_observation.read_plane_detail_nodes) or ''
    assert '变暗' in doc, '节点条读法缺过去位面变暗态注释'


# --------------------------------------------------------------------------- #
# clean 等待门静止帧提前放弃(2026-08-30 哨兵 20:22:36 实证治理)
# --------------------------------------------------------------------------- #
# 实证链:P2 采集点位面 1(变暗灰态)→ read 恒 None → 门把 None 一律归因
# 「切卡动画中」硬等 90s 后放弃——采集从未通过此门(设计=新局 P1 一次性
# 补采,却在 P2 反复出现即此慢性失败的漂移结果)。治本:门加帧稳定性信号
# ——连续 2 帧零变化=静止渲染态(等不会变 clean)→ 提前放弃;
# 真动画帧间必有变化 → 原超上限路径保持不动(w314 锁①/②锁该路)。


def test_gate_fails_fast_on_static_frames() -> None:
    """静止帧提前放弃:连续 2 帧零变化 → round_fail,不等 90s 上限。"""
    import numpy as np

    from test.harness.fixture_controller import fast_sleep

    img = np.zeros((108, 192, 3), dtype=np.uint8)   # 静止帧(两轮同图)
    op = _bare_op()
    op.last_screenshot = img

    with fast_sleep():
        r1 = op._nonclean_read_gate('切卡动画中')
        assert '间隔重读' in str(r1.status), (
            f'第 1 帧(尚无前帧可比)应走间隔重读,得 {r1.status!r}')
        r2 = op._nonclean_read_gate('切卡动画中')
    assert r2.is_fail, f'连续 2 帧零变化应提前放弃,得 {r2.status!r}'
    assert '静止' in str(r2.status), f'失败应声明静止帧根因,得 {r2.status!r}'
    assert '动画' in str(r2.status), f'失败应声明非动画(与 90s 超限相区分),得 {r2.status!r}'


def test_gate_keeps_waiting_on_changing_frames() -> None:
    """帧在变(真动画)→ 不触发静止提前放弃,仍走间隔重读/超上限路径。"""
    import numpy as np

    from test.harness.fixture_controller import fast_sleep

    img_a = np.zeros((108, 192, 3), dtype=np.uint8)
    img_b = np.full((108, 192, 3), 200, dtype=np.uint8)   # 与 a 差异显著
    op = _bare_op()

    with fast_sleep():
        op.last_screenshot = img_a
        r1 = op._nonclean_read_gate('切卡动画中')
        assert '间隔重读' in str(r1.status), f'第 1 帧应间隔重读,得 {r1.status!r}'
        op.last_screenshot = img_b
        r2 = op._nonclean_read_gate('切卡动画中')
    assert '间隔重读' in str(r2.status), f'帧间有变化(真动画)不应提前放弃,得 {r2.status!r}'


def test_frames_identical_tolerance() -> None:
    """帧差判定:同图=零变化;显著差异图=有变化(容忍压缩噪声的容差语义)。"""
    import numpy as np

    from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_intel import  _frames_identical

    a = np.zeros((54, 96), dtype=np.uint8)
    assert _frames_identical(a, a.copy()) is True
    assert _frames_identical(a, a + 1) is True          # 噪声级差异容忍
    b = np.full((54, 96), 180, dtype=np.uint8)
    assert _frames_identical(a, b) is False             # 显著差异=动画


def _bare_op():
    """免 fixture 构造最小 op(仅测门方法:跳过 SrOperation 重初始化)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_intel import  CwScreenPlaneIntel

    op = CwScreenPlaneIntel.__new__(CwScreenPlaneIntel)
    op._nonclean_wait_start = None
    op._gate_prev_thumb = None
    op._gate_static_streak = 0
    op._best_effort_close_detail = lambda: None   # 单测不触真实截图/点击
    return op


# ==================== w901_plane_intel_static_conclude ====================

from pathlib import Path as _w901_plane_intel_static_conclude_Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import cv2
import numpy as np

from test.harness.fixture_controller import  FixtureController, WatchdogOperationMixin, enter_running_state, fast_sleep, reset_running_state

if TYPE_CHECKING:
    from test.conftest import SrTestContext

_PD = '货币战争-位面详情'
_PREP = '货币战争-备战'
_TITLE = '标识-位面详情标题'


def _make_op(test_context: SrTestContext, monkeypatch) -> tuple:
    """构造被测 op(fixture 控制器注入),返回 (op, fixture_controller)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_intel import  CwScreenPlaneIntel

    class _Watched(WatchdogOperationMixin, CwScreenPlaneIntel):
        pass

    op = _Watched(test_context)
    op.watchdog_max_rounds = 300
    fc = FixtureController(test_context)
    fc.set_phases([{'frame': (_PREP, 'shop_closed')}])
    monkeypatch.setattr(test_context, 'controller', fc)
    return op, fc


def _detect(op) -> SimpleNamespace:
    """画面判定替身:采集期(cur_plane<3)恒「在位面详情」;三位面齐后首次
    调用仍 True(让采集节点走到 round_success),其后 False(关闭节点判定
    详情 id_mark 消失=真转移)。"""
    if op._cur_plane < 3:
        op._w901_done_seen = False
        return SimpleNamespace(is_success=True)
    if not getattr(op, '_w901_done_seen', False):
        op._w901_done_seen = True
        return SimpleNamespace(is_success=True)
    return SimpleNamespace(is_success=False)


def _load_detail_frame() -> np.ndarray:
    """位面详情存档帧(RGB;真实 OCR id_mark 可命中,w314 锁③同款帧源)。"""
    p = (_w901_plane_intel_static_conclude_Path(__file__).parents[4] / 'screens' / _PD
         / '位面详情-点节点直开.png')
    img_bgr = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 缺失: {p}'
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)   # 生产语义:RGB


# --------------------------------------------------------------------------- #
# 锁①:详情侧节点条读不出 → **直接**位面级结论(记 None,推进下一位面),
#      不整场失败、不经等待门间隔重试(2026-09-03 用户裁决改写:已通过节点
#      变暗=正常态,重试等待是浪费——第六局接管实证重试烧 7s 后才放弃)
# --------------------------------------------------------------------------- #


def test_static_concludes_plane_and_advances(test_context: SrTestContext,
                                             monkeypatch) -> None:
    """锁①:详情侧读不出 → 单次调用即 round_wait 推进,该位面记 None;
    op 不失败,等待账重置(下一位面从零起算);全程无间隔重试等待。"""

    op, _fc = _make_op(test_context, monkeypatch)
    # 确在位面详情(守卫通过):monkeypatch 画面判定命中
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda *a, **k: SimpleNamespace(is_success=True))
    img = np.zeros((108, 192, 3), dtype=np.uint8)
    op.last_screenshot = img
    op.screenshot = lambda: img

    with fast_sleep():
        r = op._conclude_plane_unreadable('节点条读不出(已通过节点变暗为正常态)')

    assert not r.is_fail, f'读不出应位面级结论而非整场失败,得 {r.status!r}'
    assert op._cur_plane == 1, f'应推进到下一位面(0基=1),得 {op._cur_plane}'
    assert op._plane_bosses[0] is None, '该位面应记 None(情报不可得)'
    assert '不可得' in str(r.status), f'状态应声明位面级结论,得 {r.status!r}'
    # 等待账已重置:下一位面的非clean等待从零起算
    assert op._nonclean_wait_start is None, '位面结论后等待账应重置'


# --------------------------------------------------------------------------- #
# 锁②:读不出但不在位面详情(详情没开成)→ 维持 op 级失败 + 尽力关详情
# --------------------------------------------------------------------------- #


def test_static_not_in_detail_fails_op(test_context: SrTestContext,
                                       monkeypatch) -> None:
    """锁②:守卫——位面级结论仅在确在位面详情时成立;不在详情(详情未开成/
    被弹回)维持 op 级失败,留给调用方在后续稳定帧重试(防 conclude 吞掉
    「半开备战帧点不开详情」场景)。"""

    op, fc = _make_op(test_context, monkeypatch)
    # 守卫判定:不在位面详情
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda *a, **k: SimpleNamespace(is_success=False))
    img = np.zeros((108, 192, 3), dtype=np.uint8)
    op.last_screenshot = img
    op.screenshot = lambda: img

    with fast_sleep():
        r = op._conclude_plane_unreadable('节点条读不出')

    assert r.is_fail, f'不在详情应维持 op 级失败,得 {r.status!r}'
    assert '放弃采集' in str(r.status), f'应声明放弃采集,得 {r.status!r}'
    assert op._cur_plane == 0, '失败路径不得推进位面'
    # 失败前尽力关详情(op 出口契约);本场景判定不在详情 → 零点击
    assert fc.recorded_clicks == [], '不在详情时不应产生点击'


# (锁③「动画帧到达→间隔重读不结论」已随 2026-09-03 用户裁决删除:详情侧
#  读不出不再区分动画/静止,一律直接位面级结论——该路径不经等待门。)


# --------------------------------------------------------------------------- #
# 锁④:循环级——位面1静止不可得 + 位面2/3 clean → 采集成功 [None, b2, b3]
# --------------------------------------------------------------------------- #


def test_loop_partial_static_then_clean_succeeds(test_context: SrTestContext,
                                                 monkeypatch) -> None:
    """锁④(clean 帧到达 + 部分静止混合场景):位面1 详情条静止读不出 →
    位面级结论;位面2/3 clean → 正常采集;op 最终 success 且结果保位
    [None, b2, b3](None 丢弃会左移错位,保位语义=ADR-0398)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    from sr_od.application.currency_war.obs import cw_observation as cwo

    op, _fc = _make_op(test_context, monkeypatch)
    # 画面判定:采集期(cur_plane<3)恒"在位面详情"(跳过备战入口,直入采集
    # 循环;位面结论守卫亦通过);关闭节点期(_cur_plane>=3)=详情已关
    # (id_mark 消失=真转移)→ close_and_report 走成功写回。
    monkeypatch.setattr(
        op, 'round_by_find_area',
        lambda *a, **k: _detect(op))
    # 帧恒静止(同一存档帧):位面1 两轮同图触发位面结论;后续位面 reader
    # 直接给出槽位,不进等待门
    img = _load_detail_frame()
    op.last_screenshot = img

    def _shot() -> np.ndarray:
        op.last_screenshot = img
        return img

    monkeypatch.setattr(op, 'screenshot', _shot)
    # area → 固定矩形(卡区/节点条/大图标坐标单一源走 area;测试桩化)
    monkeypatch.setattr(
        cw_obs_core, '_area_rect',
        lambda ctx, name, screen: SimpleNamespace(x1=0, y1=0, x2=100, y2=100))
    # 详情条读法按位面:位面1 恒读不出(静止结论路径);位面2/3 clean
    # (以 op._cur_plane 为键,与调用次数无关)
    slot = SimpleNamespace(node_type='battle', state='current', cx=50, cy=50)

    def _fake_detail_nodes(ctx, screen):
        return None if op._cur_plane == 0 else [slot]

    monkeypatch.setattr(cwo, 'read_plane_detail_nodes', _fake_detail_nodes)
    monkeypatch.setattr(cwo, 'read_phase_round',
                        lambda ctx, screen: None)   # 无 session 真值 → 不跳过
    from sr_od.application.currency_war.obs import cw_briefing_obs as cbo
    monkeypatch.setattr(cbo, 'read_detail_affixes', lambda ctx, screen: [])
    monkeypatch.setattr(
        cwo, 'read_detail_node_type_label', lambda ctx, screen: '首领')
    # boss 大图标 SIFT:按位面命名(断言保位)
    monkeypatch.setattr(op, '_read_boss_big_icon',
                        lambda: f'boss{op._cur_plane + 1}')
    enter_running_state(test_context)
    try:
        with fast_sleep():
            res = op.execute()
    finally:
        reset_running_state(test_context, op)

    assert res.success, f'部分静止不可得不应导致整场失败,得 {res.status!r}'
    bosses = getattr(op.ctx, 'cw_plane_bosses', None)
    assert bosses == [None, 'boss2', 'boss3'], (
        f'结果应保位 [None, boss2, boss3],得 {bosses}')


# ==================== w314_plane_intel_wait_clean ====================

from types import SimpleNamespace as _w314_plane_intel_wait_clean_SimpleNamespace
from typing import TYPE_CHECKING as _w314_plane_intel_wait_clean_TYPE_CHECKING

from one_dragon.base.operation.operation_base import OperationResult
from test.harness.fixture_controller import  FixtureController as _w314_plane_intel_wait_clean_FixtureController, WatchdogOperationMixin as _w314_plane_intel_wait_clean_WatchdogOperationMixin, enter_running_state as _w314_plane_intel_wait_clean_enter_running_state, fast_sleep as _w314_plane_intel_wait_clean_fast_sleep, reset_running_state as _w314_plane_intel_wait_clean_reset_running_state

if _w314_plane_intel_wait_clean_TYPE_CHECKING:
    from test.conftest import SrTestContext

_w314_plane_intel_wait_clean_PREP = '货币战争-备战'


def _w314_plane_intel_wait_clean_make_op(test_context: SrTestContext, monkeypatch, phases: list[dict],
             watchdog_max_rounds: int = 300):
    """构造被测 op(fixture 控制器注入 + 看门狗),返回 (op, fixture_controller)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_intel import  CwScreenPlaneIntel

    class _Watched(_w314_plane_intel_wait_clean_WatchdogOperationMixin, CwScreenPlaneIntel):
        pass

    op = _Watched(test_context)
    op.watchdog_max_rounds = watchdog_max_rounds
    fc = _w314_plane_intel_wait_clean_FixtureController(test_context)
    fc.set_phases(phases)
    monkeypatch.setattr(test_context, 'controller', fc)
    return op, fc


class _FakeClock:
    """cpi 模块级 ``time`` 替身:sleep 记录并推近 fake 墙钟(monotonic)。"""

    def __init__(self, advance_per_sleep: float = 10.0):
        self.t: float = 0.0
        self.sleeps: list[float] = []
        self.advance_per_sleep: float = advance_per_sleep

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += self.advance_per_sleep


def _patch_node_reader(monkeypatch, outcomes: list) -> list[int]:
    """替身 read_node_sequence:按 ``outcomes`` 逐次返回(耗尽后恒 None)。

    返回调用计数列表(经闭包记录,断言「第几次读才点击」用)。
    """
    from sr_od.application.currency_war.obs import cw_observation as cwo

    calls: list[int] = []

    def _fake_read(ctx, screen):
        calls.append(len(calls) + 1)
        if len(calls) <= len(outcomes):
            return outcomes[len(calls) - 1]
        return None

    monkeypatch.setattr(cwo, 'read_node_sequence', _fake_read)
    return calls


def _exec(op) -> OperationResult:
    with _w314_plane_intel_wait_clean_fast_sleep():
        return op.execute()


# --------------------------------------------------------------------------- #
# 锁①:短窗内非clean不弃 + 间隔重读 + 超上限才失败
# --------------------------------------------------------------------------- #


def test_nonclean_waits_until_cap_then_fails(test_context: SrTestContext,
                                             monkeypatch) -> None:
    """锁①:备战节点条持续非clean → 不在短窗失败;间隔重读;超宽上限才 round_fail。

    2026-08-30 语义更新:等待门新增静止帧提前放弃(连续帧零变化=非动画)。
    本锁验证的是**真动画**路径(帧间有变化 → 等到上限),故替身帧差判定恒
    「有变化」;静止帧提前放弃的锁在 test_cw_w857_plane_intel_skip。
    """
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_plane_intel as cpi_mod

    # 恒非clean(read_node_sequence 恒 None),fake 墙钟每次 sleep 推进 10s
    _patch_node_reader(monkeypatch, [])
    # fixture 帧逐轮相同(静止)——替身帧差判定为「有变化」模拟真动画
    monkeypatch.setattr(cpi_mod, '_frames_identical', lambda a, b: False)
    clock = _FakeClock(advance_per_sleep=10.0)
    monkeypatch.setattr(cpi_mod, 'time', clock)

    op, fc = _w314_plane_intel_wait_clean_make_op(test_context, monkeypatch,
                      [{'frame': (_w314_plane_intel_wait_clean_PREP, 'shop_closed')}])
    _w314_plane_intel_wait_clean_enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        _w314_plane_intel_wait_clean_reset_running_state(test_context, op)

    assert not res.success, f'持续非clean终应失败,得 {res.status!r}'
    assert '放弃采集' in str(res.status) and '超' in str(res.status), (
        f'失败应声明「非clean持续超上限放弃」,得 {res.status!r}')
    # 间隔重读:每次重读前有 sleep(间隔值),且至少覆盖旧 3 连读窗(短窗内不弃)
    assert len(clock.sleeps) >= 3, f'短窗内不应放弃(应 ≥3 次重读),得 {len(clock.sleeps)}'
    assert all(s == cpi_mod._NODE_BAR_READ_INTERVAL_S for s in clock.sleeps), (
        f'重读间隔应恒为 {cpi_mod._NODE_BAR_READ_INTERVAL_S}s,得 {clock.sleeps}')
    # 宽上限兜底:墙钟计时超 _NODE_BAR_WAIT_CAP_S 才失败(sleep 推进时钟 ≥ 上限)
    assert clock.t >= cpi_mod._NODE_BAR_WAIT_CAP_S, (
        f'应在超上限({cpi_mod._NODE_BAR_WAIT_CAP_S}s)后才失败,得墙钟 {clock.t}s')
    # 等待期零点击(非clean帧点了也白点,交互无效)
    assert fc.recorded_clicks == [], '非clean等待期不应产生点击'


# --------------------------------------------------------------------------- #
# 锁③:超上限放弃采集前,尽力关位面详情(出口契约=回备战屏)
# --------------------------------------------------------------------------- #


def test_give_up_closes_detail_overlay(test_context: SrTestContext,
                                       monkeypatch) -> None:
    """锁③:在位面详情帧上门超限放弃 → round_fail 前须先点关闭键
    (2026-08-30 判读:放弃采集时详情屏滞留画面,主循环当时无对应分支
    → 未识别兜底自停)。备战帧场景(详情未开)不得产生点击(锁①同款)。"""
    from pathlib import Path

    import cv2
    import numpy as np

    from sr_od.application.currency_war.operations.cw_screen import cw_screen_plane_intel as cpi_mod

    # 现帧 = 位面详情存档帧(真实 OCR:id_mark 命中,w280 锁⑦同款帧源)
    p = (Path(__file__).parents[4] / 'screens' / '货币战争-位面详情'
         / '位面详情-点节点直开.png')
    img_bgr = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 缺失: {p}'
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)   # 生产语义:RGB

    op, fc = _w314_plane_intel_wait_clean_make_op(test_context, monkeypatch,
                      [{'frame': (_w314_plane_intel_wait_clean_PREP, 'shop_closed')}])
    monkeypatch.setattr(op, 'screenshot', lambda: img_rgb)
    clock = _FakeClock(advance_per_sleep=10.0)
    monkeypatch.setattr(cpi_mod, 'time', clock)
    # 等待账预置为已超限 → 首次进门即放弃
    op._nonclean_wait_start = clock.monotonic() - (cpi_mod._NODE_BAR_WAIT_CAP_S + 1.0)

    res = op._nonclean_read_gate('切卡动画中')

    assert res.is_fail, f'超限应失败,得 {res.status!r}'
    assert '放弃采集' in str(res.status), f'应声明放弃采集,得 {res.status!r}'
    assert len(fc.recorded_clicks) == 1, (
        f'放弃前应恰好点一次关闭键,得 {len(fc.recorded_clicks)} 次')
    assert 1.5 in clock.sleeps, f'关闭键点击后应有 1.5s 等待,得 {clock.sleeps}'


# --------------------------------------------------------------------------- #
# 锁②:动画窗过后读到 clean → 恢复采集(点击节点图标开详情)
# --------------------------------------------------------------------------- #


def test_recovers_after_clean_frame(test_context: SrTestContext,
                                    monkeypatch) -> None:
    """锁②:前 3 次非clean → 第 4 次读出 clean → 立即恢复:点节点条内图标,不失败。"""
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_plane_intel as cpi_mod

    clean_slot = _w314_plane_intel_wait_clean_SimpleNamespace(state='current', cx=100, cy=100)
    calls = _patch_node_reader(monkeypatch, [None, None, None, [clean_slot]])
    # 场景=真动画窗(帧间有变化);替身帧差判定恒「有变化」防静止提前放弃
    # (静止帧路径归 test_cw_w857_plane_intel_skip)
    monkeypatch.setattr(cpi_mod, '_frames_identical', lambda a, b: False)
    clock = _FakeClock(advance_per_sleep=10.0)
    monkeypatch.setattr(cpi_mod, 'time', clock)

    # click 落「区域-节点条」内 → 剧本推进到下一帧(同备战帧;之后恒非clean,
    # 由看门狗收口——本锁只验证「clean 后恢复点击」)
    op, fc = _w314_plane_intel_wait_clean_make_op(
        test_context, monkeypatch,
        [{'frame': (_w314_plane_intel_wait_clean_PREP, 'shop_closed'),
          'exit': ('on_click_in', _w314_plane_intel_wait_clean_PREP, '区域-节点条')},
         {'frame': (_w314_plane_intel_wait_clean_PREP, 'shop_closed')}],
        watchdog_max_rounds=25)
    _w314_plane_intel_wait_clean_enter_running_state(test_context)
    try:
        _exec(op)
    finally:
        _w314_plane_intel_wait_clean_reset_running_state(test_context, op)

    # 前 3 次非clean未点击(短窗内不弃也不乱点),第 4 次 clean 才点击恢复
    assert fc.recorded_clicks, 'clean 帧后应点击节点图标开位面详情'
    assert len(calls) >= 4, f'点击前应经历 3 次非clean重读,得读数次数 {calls}'
    # 等待期走的是间隔重读(sleep 间隔;clean 后点击的开屏等待也走此时钟,
    # 2026-09-03 起开屏等待=用户定值 _DETAIL_OPEN_WAIT_S=3.0)
    assert clock.sleeps.count(cpi_mod._NODE_BAR_READ_INTERVAL_S) >= 3, (
        f'非clean重读应有 ≥3 次间隔 sleep({cpi_mod._NODE_BAR_READ_INTERVAL_S}s),得 {clock.sleeps}')
    assert all(s in (cpi_mod._NODE_BAR_READ_INTERVAL_S,
                     cpi_mod._DETAIL_OPEN_WAIT_S) for s in clock.sleeps), (
        f'不应出现忙连读(只允许重读间隔与点击后等待),得 {clock.sleeps}')


# ==================== w575_plane_detail_recovery ====================

def test_loop_has_plane_detail_overlay_branch() -> None:
    """主循环 0 系名单含位面详情分支:标题识别 + 关闭键点击,且先于恢复局
    锁定分支(overlay 先消化,不污染其后的商店探针/出战判读)。"""
    import inspect

    from sr_od.application.currency_war.operations import cw_loop

    src = inspect.getsource(cw_loop.CwLoop)
    assert '标识-位面详情标题' in src, '主循环缺位面详情 overlay 识别分支'
    assert "'货币战争-位面详情', '按钮-关闭位面详情'" in src, (
        '位面详情分支应点关闭键(按钮-关闭位面详情)')
    i_branch = src.index('0a4. 位面详情 overlay')
    i_resume = src.index('恢复局锁定确认')
    assert i_branch < i_resume, (
        '位面详情分支必须先于恢复局锁定分支(overlay 先消化再走 in-match 逻辑)')


def test_collect_fail_paths_close_detail() -> None:
    """采集 op 两失败退出路径(非clean 超限放弃/位面卡缺失)都应先调
    _best_effort_close_detail(出口契约=回备战屏)。"""
    import inspect

    from sr_od.application.currency_war.operations.cw_screen import cw_screen_plane_intel

    src = inspect.getsource(cw_screen_plane_intel.CwScreenPlaneIntel)
    assert src.count('_best_effort_close_detail()') >= 2, (
        '放弃采集与位面卡缺失两条失败路径都应先尽力关详情')

# —— 换核隔离桶(2026-09-03 测试分层批)——
# 本文件属 legacy_baseline 桶:锁的是旧决策核(decision_v2)内部行为语义,
# 随旧核退役而消亡;默认全量与快速集均不跑,仅基线冻结审计/A-B 开跑前
# 两时点单独跑。口径见 sr-od-test/README.md「测试纪律 · legacy 桶」。
import pytest

pytestmark = pytest.mark.legacy_baseline
