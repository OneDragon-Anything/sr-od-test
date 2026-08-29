"""血预算停手·终止分支(P1「止损转支出」)锁(设计 W659 v2 §2/§3/§5.2;
ADR-0469)。

锁面(设计 §5.2 新增锁):
- S0 闭式对拍单帧锁(§5.2-4,本锁是 S0 公式正确性的唯一承载面——
  R4:检查器禁复算 S0,公式缺陷必须在 L1 被抓):K 空/单场穿透/
  两场穿透/双节点链四用例对拍闭式值(锁推导不锁分布);
- 终止帧三断言一体(§5.2-1):refresh_blocked=False ∧ downgrade
  inactive ∧ levelup_blocked 仍 True(防「释放扩散」回归,FM-3);
- 非终止帧零漂移(§5.2-2):hp=40 强板 K=∅ → 三门行为逐位不变;
- 不可信 hp 帧 fail-closed(§5.2-3);
- 当轮转化双门(v2 R2):bench 空槽 ∧(deploy 空位 ∨ 1★ 垫底件)
  才放行,板满全 ≥2★ 帧维持停付;
- 滞回单帧锁(§5.2-6):位面内 S0 跨 ε 抖动 → 终止位只置位一次;
  位面切换清零;P2 硬门零辖域(R6);
- 一致性检查器锁(§5.2-5):非终止位帧刷新违规/终止位帧账本错位
  两构造反例各命中一次,豁免帧不出事件。

判据出处:设计 W659 v2(EV 对比式反解 ε=0.03、S0 上界口径、金零值
引理、位面内触发闩 R7、双门 R2、硬门 R6);账本位=R4 决策位记账。
"""
from __future__ import annotations

import dataclasses
import logging

import pytest

from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.sim.cw_sim_checks import (
    seg_check_p1_blood_budget_refresh,
    seg_terminal_release_ledger,
)
from sr_od.application.currency_war.decision_v2.discipline import (
    blood_budget_levelup_blocked,
    blood_budget_refresh_blocked,
    p1_directed_downgrade_active,
    terminal_release,
    terminal_release_bit,
    terminal_round_conversion_open,
    terminal_survival_upper_bound,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

logging.disable(logging.CRITICAL)

#: 闭式对拍基准值(=registry.streak_floor_win_rate 注入表直读,本表
#: 是 p_i 单一源;此处只做乘法,禁复制数值——漂移由表本身锁辖)


def _p1_state(hp: int = 10, round_num: int = 7, node: str = 'battle',
              gold: int = 120) -> GameState:
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 1, 6, gold, hp
    st.round_num = round_num
    st.node_type = node
    return st


def _sess(table: list[str] | None = None) -> StrategySession:
    s = StrategySession()
    s.plane_node_table = table if table is not None else ['battle'] * 9
    return s


def _board(state: GameState, names: list[str], star: int = 1) -> GameState:
    state.deployed = [BenchChar(slot=i + 1, char_id=n, faction='仙舟',
                                star=star)
                      for i, n in enumerate(names)]
    return state


# ---------- §5.2-4:S0 闭式对拍(公式正确性唯一承载面) ----------

def test_s0_empty_chain_is_one() -> None:
    """K=∅ → S0=1(hp=40 > 全档 L,无「一败即死」场;设计 §2.3 行进带
    上沿用例)——不触发语义的数学承载。"""
    s0 = terminal_survival_upper_bound(_p1_state(hp=40), _sess(),
                                       DEFAULT_REGISTRY)
    assert s0 == pytest.approx(1.0)


def test_s0_single_boss_penetration() -> None:
    """单场穿透:hp=10、末轮仅剩 boss → K={boss},S0=p_boss(rung0)=0.077
    (table[8:9];r9 单场构造避开 ALL IN 语义只用于 S0 纯函数)。"""
    sess = _sess(['battle'] * 8 + ['boss'])
    s0 = terminal_survival_upper_bound(_p1_state(hp=10, round_num=9), sess,
                                       DEFAULT_REGISTRY)
    assert s0 == pytest.approx(
        DEFAULT_REGISTRY.streak_floor_win_rate['boss'][0])


def test_s0_double_battle_chain() -> None:
    """两场穿透:hp=10、剩 2 场普通战斗(rung0)→ S0=0.009²(设计 §2.3
    弱板两链用例)。"""
    sess = _sess(['battle'] * 7 + ['battle', 'battle'])
    s0 = terminal_survival_upper_bound(_p1_state(hp=10, round_num=8), sess,
                                       DEFAULT_REGISTRY)
    wr = DEFAULT_REGISTRY.streak_floor_win_rate['battle'][0]
    assert s0 == pytest.approx(wr * wr)


def test_s0_encounter_boss_chain_rung1() -> None:
    """双节点链(rung1,遭遇+boss 双穿透):S0=p_enc(rung1)×p_boss(rung1)
    ——非同质链逐节点取各自 p_i 的闭式对拍。"""
    sess = _sess(['battle'] * 7 + ['encounter', 'boss'])
    st = _board(_p1_state(hp=10, round_num=8), ['艾丝妲', '椒丘'])
    s0 = terminal_survival_upper_bound(st, sess, DEFAULT_REGISTRY)
    wr = DEFAULT_REGISTRY.streak_floor_win_rate
    assert s0 == pytest.approx(wr['encounter'][1] * wr['boss'][1])


# ---------- §5.2-1:终止帧三断言一体(防释放扩散,FM-3) ----------

def test_terminal_frame_three_assertions() -> None:
    """行进带终止帧(hp=26 ∈ boss 单链域,rung1)→ refresh_blocked=False
    ∧ downgrade inactive;升级门该帧本就线外(hp>11)——停升级门不受
    终止豁免影响的深终止帧用例见下(hp=10)。"""
    sess = _sess(['battle'] * 7 + ['encounter', 'boss'])
    st = _board(_p1_state(hp=26, round_num=8), ['艾丝妲', '椒丘'])
    assert terminal_release(st, sess, DEFAULT_REGISTRY)
    assert not blood_budget_refresh_blocked(st, sess, DEFAULT_REGISTRY)
    assert not p1_directed_downgrade_active(st, DEFAULT_REGISTRY,
                                            session=sess)


def test_deep_terminal_frame_levelup_still_blocked() -> None:
    """深终止帧(hp=10,弱板,K≥2)三断言一体(设计 §5.2-1):refresh_
    blocked=False ∧ downgrade inactive ∧ **levelup_blocked 仍 True**
    (hp=10≤P1 线 11;停升级门不在终止豁免辖内——P21 数学:濒死升级
    EV=−C−I 严格为负,与金是否零价值无关;FM-3 释放扩散回归锚)。"""
    sess = _sess()
    st = _p1_state(hp=10)
    assert terminal_release(st, sess, DEFAULT_REGISTRY)
    assert not p1_directed_downgrade_active(st, DEFAULT_REGISTRY,
                                            session=sess)
    assert blood_budget_levelup_blocked(st, sess, DEFAULT_REGISTRY)


# ---------- §5.2-2:非终止帧零漂移 ----------

def test_nonterminal_frame_unchanged() -> None:
    """hp=40 强板(rung2,encounter L=19.79/boss L=26.71 均 <40 → K=∅)
    三门与现状逐位一致:刷新停付在、降格在、升级门不辖(线外)。"""
    sess = _sess(['battle'] * 7 + ['encounter', 'boss'])
    st = _board(_p1_state(hp=40, round_num=8),
                ['艾丝妲', '椒丘', '三月七', '姬子'])
    assert not terminal_release(st, sess, DEFAULT_REGISTRY)
    assert blood_budget_refresh_blocked(st, sess, DEFAULT_REGISTRY)
    assert p1_directed_downgrade_active(st, DEFAULT_REGISTRY, session=sess)
    assert not blood_budget_levelup_blocked(st, sess, DEFAULT_REGISTRY)


# ---------- §5.2-3:不可信 hp 帧 fail-closed ----------

def test_untrusted_hp_fail_closed() -> None:
    """幽灵帧((False,False),镜像 hp_decision_trusted)→ 终止分支不
    触发,血预算带帧停付照旧(误放代价 > 误拦;设计 §2.1)。帧取
    hp=26 行进带 boss 单链域 + 双门开——若误判可信,该帧本应释放。"""
    sess = _sess(['battle'] * 7 + ['encounter', 'boss'])
    st = _board(_p1_state(hp=26, round_num=8), ['艾丝妲', '椒丘'])
    st.hp_readable = False
    st.hp_trusted = False
    assert not terminal_release(st, sess, DEFAULT_REGISTRY)
    assert blood_budget_refresh_blocked(st, sess, DEFAULT_REGISTRY)
    assert p1_directed_downgrade_active(st, DEFAULT_REGISTRY, session=sess)


# ---------- 当轮转化双门(v2 R2) ----------

def test_conversion_dual_gate_matrix() -> None:
    """双门四象限:bench 空槽 ∧(deploy 空位 ∨ 1★ 垫底)才开;
    bench 满 / 板满全 2★ 关(板满帧不进释放辖域,维持停付)。"""
    reg = DEFAULT_REGISTRY
    empty_bench = _p1_state()
    assert terminal_round_conversion_open(empty_bench, reg)  # deploy 空位
    full_1star = _board(_p1_state(), ['a', 'b', 'c', 'd', 'e', 'f'], star=1)
    assert terminal_round_conversion_open(full_1star, reg)   # 1★ 垫底可换
    full_2star = _board(_p1_state(), ['a', 'b', 'c', 'd', 'e', 'f'], star=2)
    assert not terminal_round_conversion_open(full_2star, reg)
    bench_full = _board(_p1_state(), ['a', 'b', 'c', 'd', 'e', 'f'])
    bench_full.bench = [BenchChar(slot=i + 1, char_id=f'x{i}')
                        for i in range(BENCH_CAPACITY)]
    assert not terminal_round_conversion_open(bench_full, reg)


def test_dual_gate_holds_refresh_in_band() -> None:
    """血预算带帧(hp=26>应急线,rung1 boss 单链)双门关 → 刷新停付
    保持;双门开 → 终止豁免放行。关臂板面=满 6 人全 2★(rung1 由
    持续伤害对贡献,星级只影响垫底判据不影响引擎计数)。"""
    sess = _sess(['battle'] * 7 + ['encounter', 'boss'])
    reg = DEFAULT_REGISTRY
    open_st = _board(_p1_state(hp=26, round_num=8), ['艾丝妲', '椒丘'])
    assert terminal_release(open_st, sess, reg)
    assert not blood_budget_refresh_blocked(open_st, sess, reg)
    closed_st = _board(_p1_state(hp=26, round_num=8),
                       ['艾丝妲', '椒丘', 'x1', 'x2', 'x3', 'x4'], star=2)
    assert terminal_release(closed_st, sess, reg)   # 谓词闩置位(触发域)
    assert blood_budget_refresh_blocked(closed_st, sess, reg)  # 双门关


# ---------- §5.2-6:滞回闩 + P2 硬门 ----------

def test_plane_latch_hysteresis_and_reset() -> None:
    """同位面 S0 跨 ε 抖动:hp=25 单 boss 链 rach1 触发(0.027≤ε)→
    闩置位;升板 rung2(S0=0.187>ε)同位面仍释放(不回退);切 P2 清零
    (P2 硬门恒 False,R6);回 P1 非 triggering 帧不再释放。"""
    sess = _sess(['battle'] * 7 + ['encounter', 'boss'])
    reg = DEFAULT_REGISTRY
    weak = _board(_p1_state(hp=25, round_num=8), ['艾丝妲', '椒丘'])
    assert terminal_release(weak, sess, reg)
    strong = _board(_p1_state(hp=25, round_num=8),
                    ['艾丝妲', '椒丘', '三月七', '姬子'])
    assert terminal_survival_upper_bound(strong, sess, reg) > 0.03
    assert terminal_release(strong, sess, reg)   # 闩:邻域抖动不回退(R7)
    # 位面切换语义 = 闩按位面键控:P1 闩不辖 P2 帧;P2 帧被硬门(R6)
    # 恒拒且不置闩(位面 2 读位恒假)——不消费 P2 参数的第二判定源被
    # 门死。P1→P2 单向推进下「清零」即旧位面闩失效。
    p2 = _p1_state(hp=1, round_num=2)
    p2.plane = 2
    assert not terminal_release(p2, sess, reg)
    assert not terminal_release_bit(sess, 2)
    assert terminal_release_bit(sess, 1)   # P1 闩原样(只辖本位面)


def test_p2_hard_gate_zero_scope() -> None:
    """P2 帧(含极低 hp)恒不触发(R6:防不消费 P2 参数的第二判定源);
    开关 off=零辖域(两态注入面)。"""
    sess = _sess()
    st = _p1_state(hp=1, round_num=2)
    st.plane = 2
    assert not terminal_release(st, sess, DEFAULT_REGISTRY)
    reg_off = dataclasses.replace(DEFAULT_REGISTRY,
                                  terminal_release_enabled=False)
    assert not terminal_release(_p1_state(hp=9), sess, reg_off)


def test_terminal_release_bit_single_source() -> None:
    """账本决策位单一址:闩位与 terminal_release_bit(plane) 逐位一致;
    异位面读位=假。"""
    sess = _sess()
    assert not terminal_release_bit(sess, 1)
    assert terminal_release(_p1_state(hp=9), sess, DEFAULT_REGISTRY)
    assert terminal_release_bit(sess, 1)
    assert not terminal_release_bit(sess, 2)


# ---------- §5.2-5:一致性检查器两构造反例 ----------

def _ledger_row(rn: int, *, terminal: bool, refreshes: int = 0,
                rejects: int = 0, bench_n: int = 0,
                deployed: list[dict] | None = None) -> dict:
    return {
        'plane': 1, 'round_num': rn, 'hp': 30,
        'terminal_release': terminal,
        'sim': {'node': 'battle', 'blood_budget_refresh_rejects': rejects},
        'actions': ([{'__type__': 'RefreshShop', 'cost': 2}] * refreshes),
        'state': {'bench': [{'char_id': f'x{i}'} for i in range(bench_n)],
                  'cap': 6, 'deployed': deployed or []},
    }


def test_seg_refresh_uses_ledger_bit() -> None:
    """非终止位帧刷新 → 违规事件;终止位帧刷新 → 豁免不出(R4:检查器
    只验位,不复算 S0)。"""
    rows = [
        _ledger_row(6, terminal=False),
        _ledger_row(7, terminal=False, refreshes=1),   # 违规
        _ledger_row(8, terminal=True, refreshes=1),    # 终止豁免辖内
        _ledger_row(9, terminal=True, refreshes=0),
    ]
    ev = seg_check_p1_blood_budget_refresh(rows)
    assert [e['round_num'] for e in ev] == [7]


def test_seg_terminal_ledger_mismatch_both_directions() -> None:
    """一致性检查器:①终止位帧 + 刷新拒付 + 双门按行内快照可开 →
    账本错位事件;②双门关(板满全 2★)同构造 → 不出(合法辖内拒付);
    ③拒付=0 帧 → 不出。"""
    rows = [
        # 双门开(bench 空 ∧ deploy 空位)+ 位真 + 拒付 → 矛盾
        _ledger_row(7, terminal=True, rejects=1),
        # 双门关(板满全 2★)+ 位真 + 拒付 → 合法辖内拒付
        _ledger_row(8, terminal=True, rejects=2,
                    deployed=[{'star': 2}] * 6),
        # 位真无拒付 → 不出
        _ledger_row(9, terminal=True),
    ]
    ev = seg_terminal_release_ledger(rows)
    assert [e['round_num'] for e in ev] == [7]
    # bench 满同样构成双门关
    rows_bench_full = [
        _ledger_row(7, terminal=True, rejects=1, bench_n=BENCH_CAPACITY),
    ]
    assert seg_terminal_release_ledger(rows_bench_full) == []


# ---------- sim 账本披露键(单局冒烟,不锁分布) ----------

def test_sim_ledger_discloses_terminal_bit() -> None:
    """账本行 'terminal_release' 键存在(R4 记账面数据源;单局冒烟,
    pool='fallback' 免快照依赖)。"""
    from sr_od.application.currency_war.sim import cw_sim
    r = cw_sim.simulate_p1(0, pool='fallback', planes=2)
    assert r.ledger
    for row in r.ledger:
        assert 'terminal_release' in row
        assert isinstance(row['terminal_release'], bool)
