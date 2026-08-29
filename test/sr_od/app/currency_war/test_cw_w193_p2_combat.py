"""ADR-0377(W193)P2 战斗存活层参数化校准族锁(案 a 结算层 + 案 b 臂)。

锁面:
- 参数族:p2_win_p 公式(clip/β·form/γ·drift)/分段掉血带路由/
  p2_combat_delta 分布域;
- 结算层接入:calibrated 批 P2 战斗行带 p2_win_p 且 Δ 落带;
  calibrated=False 逐位回 legacy(Δ池 plane=2 优先 + 恒值回退档);
  P1 段两臂逐位零漂移;
- 事件金双臂:rng 流同耗(P1 段逐位同),P2 段 income.event 归零;
- 案 b 臂(simulate_p2_replay_entry):共享循环体(账本 plane=2、
  节点序列、进场态继承、ts 从 1 起);
- headline 扩展键 + 检查器(带锚/胜率锚,含变异涌现锁);
- headline 观测派生(金带走量/价格带笔数/意向切换/lv 到达轮)。
n 取断言成立最小值(README 纪律 7);结构性断言用 fallback,
结算链路用 snapshot。
"""
from __future__ import annotations

import logging
import random

from sr_od.application.currency_war import cw_sim
from sr_od.application.currency_war.cw_sim import P2ReplayEntry
from sr_od.application.currency_war.cw_sim_checks import (
    check_p2_loss_band_anchor,
    check_p2_win_rate_band,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.data.cw_battle_tables import P2CombatCalib
from sr_od.application.currency_war.kernel import cw_battle_calib as _calib

logging.disable(logging.CRITICAL)


def _st(engines: int = 0, level: int = 6) -> GameState:
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 2, level, 50, 60
    st.deployed = [BenchChar(slot=i + 1, char_id=f'c{i}',
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
    rng = random.Random(0)
    for _ in range(20):
        d, wp = cw_sim.p2_combat_delta(_st(), 'boss', 7, rng, c)
        assert d == 2 and wp == 1.0
    c0 = P2CombatCalib(p0=0.0)       # 恒负臂
    for node, rn, band in (('battle', 1, c0.band_battle_r1),
                           ('battle', 4, c0.band_battle_late),
                           ('boss', 7, c0.band_boss)):
        for _ in range(60):
            d, wp = cw_sim.p2_combat_delta(_st(), node, rn, rng, c0)
            assert wp == 0.0
            assert -band[1] <= d <= -band[0]


# ---------- 结算层接入(planes=2) ----------

def test_calibrated_settlement_in_sim() -> None:
    """calibrated 批:P2 战斗行带 p2_win_p,Δ∈{win_delta}∪负带。"""
    r = cw_sim.simulate_p1(7, pool='snapshot', planes=2)
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
    r_off = cw_sim.simulate_p1(7, pool='snapshot', planes=2, p2_combat=off)
    r_on = cw_sim.simulate_p1(7, pool='snapshot', planes=2)
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
    r0 = cw_sim.simulate_p1(3, pool='snapshot', planes=2, p2_combat=zero)
    r1 = cw_sim.simulate_p1(3, pool='snapshot', planes=2)
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
    r = cw_sim.simulate_p2_replay_entry(e, 11, pool='snapshot')
    assert r.p2_entered and r.p2_combat_calibrated
    p2 = [row for row in r.ledger if (row.get('plane') or 1) == 2]
    assert p2 and all(row['plane'] == 2 for row in r.ledger)
    assert p2[0]['ts'] == 1                    # 无 P1 段,ts 从 1 起
    assert [row['sim']['node'] for row in p2] == \
        list(cw_sim.P2_NODE_SEQUENCE)[:len(p2)]
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
        cw_sim.simulate_p1(0, pool='fallback', invest=True, _p2_entry=e)
    except ValueError as ex:
        assert '案 b' in str(ex)
    else:
        raise AssertionError('invest+_p2_entry 应显式 raise')


# ---------- headline 扩展 + 检查器 ----------

def test_batch_headline_extension_keys() -> None:
    """批报告 P2 判读扩展键在位(形状锁,不锁分布数值)。"""
    rep = cw_sim.simulate_p1_batch(10, pool='snapshot', planes=2,
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


def test_result_observation_derivation() -> None:
    """单局观测派生:价格带笔数/意向切换/lv 到达轮由账本 P2 行派生。"""
    e = P2ReplayEntry(hp=80, gold=100, level=5, board={'仙舟': 3})
    r = cw_sim.simulate_p2_replay_entry(e, 42, pool='snapshot')
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
    """胜率锚:聚合胜率带外涌现(样本 ≥20 才判)/uncalibrated 跳过。"""
    def row(w: bool) -> dict:
        return {'plane': 2, 'round_num': 1, 'sim': {
            'node': 'battle', 'p2_win_p': 0.1,
            'delta': 2 if w else -16}}
    hot = [[row(True)] * 30]
    rep = check_p2_win_rate_band(
        hot, report={'p2_combat_calibrated': True})
    assert rep['violations'] == 1 and rep['win_rate'] == 1.0
    cold = [[row(False)] * 25]
    assert check_p2_win_rate_band(
        cold, report={'p2_combat_calibrated': True})['violations'] == 0
    few = [[row(True)] * 5]          # 样本贫困:只披露不判
    assert check_p2_win_rate_band(
        few, report={'p2_combat_calibrated': True})['violations'] == 0
    assert check_p2_win_rate_band(
        hot, report={'p2_combat_calibrated': False})['violations'] == 0


def test_mutation_probe_settlement_bypass(monkeypatch) -> None:
    """变异探针锁(检查非空转):结算层被换成 legacy 常数带(15-17)
    而批仍报 calibrated → 带锚违规必须涌现(防御「校准层被绕过」
    回归——正是本检查的存在理由)。"""
    def _broken(st, node, round_num, rng, calib):
        return (-50, 0.11)   # 全带外(最宽带 hi=28)
    monkeypatch.setattr(cw_sim, 'p2_combat_delta', _broken)
    rep = cw_sim.simulate_p1_batch(8, pool='snapshot', planes=2,
                                   ledger=False, seed_base=100)
    cv = rep['checks_violations']['p2_loss_band_anchor']
    assert cv['violations'] > 0, '变异(结算绕过参数族)未涌现违规'


def test_mutation_probe_win_rate_explosion(monkeypatch) -> None:
    """变异探针锁:胜率模型失控(clip 被绕过)→ 胜率锚违规涌现。"""
    def _broken(st, node, round_num, rng, calib):
        return (2, 0.9)
    monkeypatch.setattr(cw_sim, 'p2_combat_delta', _broken)
    rep = cw_sim.simulate_p1_batch(8, pool='snapshot', planes=2,
                                   ledger=False, seed_base=100)
    cv = rep['checks_violations']['p2_win_rate_band']
    assert cv['violations'] > 0, '变异(胜率失控)未涌现违规'


# ---------- 敏感性入口 ----------

def test_sensitivity_report_shape() -> None:
    """敏感性扫描入口:网格形状 + 判读 headline 键(n 取最小)。"""
    rep = cw_sim.simulate_p2_sensitivity(
        3, pool='snapshot', betas=(0.0, 0.04), gammas=(0.0, 0.02),
        event_gold_arms=('p1',))
    assert rep['n'] == 3 and len(rep['grid']) == 4
    for cell in rep['grid']:
        for k in ('event_gold', 'beta', 'gamma', 'avg_p2_rounds',
                  'p2_win_rate', 'p2_hp0_rate', 'avg_p2_gold_carried',
                  'avg_final_hp'):
            assert k in cell
    assert rep['pool_fingerprint']
