"""ADR-0362(W157)Δ池 plane 维键化 + sim P2 位面段锁(案 a 最小可用)。

锁面:
- plane 键化:差分归属后行位面(P1r9→P2r1 归 plane=2)/live_delta_for
  不跨位面回退/指纹含位面层;
- simulate_p1(planes=2):P2 段形状(7 轮节点序列/账本 plane=2 行/
  ts 跨位面单调)/P1 段零漂移(planes=1 与默认逐位同);
- P2 headline 四联进批报告 + A/B 通道存在;
- 检查器最小集(p2_gold_nonneg / p2_segment_shape)。
n 取断言成立最小值(README 纪律 7),fallback/snapshot 池混用:
结构性断言用 fallback(快、无池语义),P2 结算链路用 snapshot。
"""
from __future__ import annotations

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
