# -*- coding: utf-8 -*-
"""观测硬依赖键面锁(W793 后继批;W802 REPORT §观测硬依赖边界声明)。

三键落 sim 账本后的回归网:
- ``state.bench_full_flag``:满栏旗标(消费 = 锁#10 D1 弱序量产对账,
  生产读端 merge_round_rows.sim.bench_full_skipped_buys);
- ``state.board_next_tier``:各阵营下档阈值(消费 = Δp_tier 档位分解
  标定批,registry.realization_delta_p_tier 标定前置);
- ``sim.alloc_frame``/``sim.alloc_active_any``:ADR-0474 分配器帧位
  (消费 = 锁#11 D2 接管可观测性;此前 session.v3_alloc_frame 无任何
  落盘消费面,D2 接管只能金账反推)。

锁防锁纪律:检查器 bidirectional(坏必报/好必过);引擎侧真实性用
「非恒值分布」断言(键恒 False/恒 None = 写端断线,对偶门防恒触发)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_factions import FACTIONS
from sr_od.application.currency_war.sim.checks import ledger, runner
from sr_od.application.currency_war.sim.engine_p1 import (
    _board_next_tier_of,
    simulate_p1,
)
from sr_od.application.currency_war.sim.runner import simulate_p1_batch

_SEEDS = (0, 7, 42)


# ---------- 检查器 bidirectional(锁防锁) ----------

def _good_row() -> dict:
    return {
        'plane': 1, 'round_num': 3,
        'state': {'bench_full_flag': False, 'board_next_tier': {'仙舟': 3},
                  'p1_downgrade_active': False,
                  'refresh_probs': {2: 0.5, 3: 0.3}},
        'sim': {'alloc_frame': {'active': False, 'reason': 'out_of_scope'},
                'alloc_active_any': False},
    }


def test_observation_keys_check_bad_rows_report() -> None:
    """坏账本必报:缺键/类型错/域非法/自洽破,五形态各报一条。"""
    import copy
    base = _good_row()
    cases: list[tuple[str, dict]] = []
    r = copy.deepcopy(base)
    del r['state']['bench_full_flag']
    cases.append(('缺bench_full_flag', r))
    r = copy.deepcopy(base)
    r['state']['bench_full_flag'] = None
    cases.append(('flag为None', r))
    r = copy.deepcopy(base)
    r['state']['board_next_tier'] = {'仙舟': 99}
    cases.append(('下档越域', r))
    r = copy.deepcopy(base)
    r['sim']['alloc_frame'] = {'active': True, 'domain': '???'}
    cases.append(('分配域非法', r))
    r = copy.deepcopy(base)
    del r['sim']['alloc_frame']
    r['sim']['alloc_active_any'] = True
    cases.append(('OR聚合但帧位缺', r))
    r = copy.deepcopy(base)
    del r['state']['p1_downgrade_active']
    cases.append(('缺降格触发面', r))
    r = copy.deepcopy(base)
    del r['state']['refresh_probs']
    cases.append(('缺轮岗概率条', r))
    for label, row in cases:
        v = ledger.check_observation_keys_live([row])
        assert v, f'{label}: 坏行未报=检查静默失效'
    # P2 行不辖(键族只承诺 P1 段)
    p2 = copy.deepcopy(base)
    p2['plane'] = 2
    assert not ledger.check_observation_keys_live([p2])


def test_observation_keys_check_good_row_passes() -> None:
    """好账本必过(防误报);active 帧位(接管态)同样过。"""
    assert not ledger.check_observation_keys_live([_good_row()])
    takeover = _good_row()
    takeover['sim']['alloc_frame'] = {
        'active': True, 'domain': 'death', 'reason': 'pipeline_spent',
        'gold': 30}
    takeover['sim']['alloc_active_any'] = True
    assert not ledger.check_observation_keys_live([takeover])


def test_observation_keys_check_registered() -> None:
    """哨兵入批检注册表(随批自动扫,不入=死检查)。"""
    assert 'observation_keys_live' in runner._BATCH_CHECKS


# ---------- 引擎侧真实性(值语义 + 非恒值分布) ----------

@pytest.mark.parametrize('seed', _SEEDS)
def test_obs_keys_shape_on_real_game(seed: int) -> None:
    """真局每行 P1 账本:三键齐且形状合法;检查器对真局零违规。"""
    res = simulate_p1(seed, pool='fallback')
    p1 = [r for r in res.ledger if (r.get('plane') or 1) == 1]
    assert p1, 'P1 账本为空'
    for row in p1:
        st = row['state']
        assert isinstance(st['bench_full_flag'], bool)
        assert isinstance(st['p1_downgrade_active'], bool)
        rp = st['refresh_probs']
        assert rp is None or isinstance(rp, dict)
        bnt = st['board_next_tier']
        assert isinstance(bnt, dict)
        for f, v in bnt.items():
            assert v in FACTIONS[f].tiers, f'{f} 下档 {v} 不在注册表 tier 表'
            assert v >= 2
        assert row['sim']['alloc_active_any'] is False or \
            row['sim']['alloc_frame'] is not None
    assert not ledger.check_observation_keys_live(p1)


def test_board_next_tier_helper_semantics() -> None:
    """单源推导式:取 >count 的最小 tier,无更高档不计(与生产 obs
    computed 支同一式)。阵营取注册表实键(不点名,防表键漂移)。"""
    fname = next(iter(FACTIONS))
    tiers = FACTIONS[fname].tiers
    mid = tiers[len(tiers) // 2]
    below = mid - 1
    assert _board_next_tier_of({fname: below}) == {fname: mid}
    # 已达最高档 → 不计(键省略)
    top = max(tiers)
    assert _board_next_tier_of({fname: top}) == {}
    # 注册表外阵营(理论上不出现)→ 安全省略
    assert _board_next_tier_of({'不存在阵营': 1}) == {}


def test_bench_full_flag_and_alloc_frame_not_degenerate() -> None:
    """对偶门(防恒值):真局里旗标必须亮过、帧位必须非 None 过——
    恒 False/恒 None = 写端断线(分配器默认开,每段 decide_prep 都
    写 session.v3_alloc_frame,prep 轮帧位恒应非 None)。"""
    rows = [r for seed in range(20) for r in simulate_p1(
        seed, pool='fallback').ledger if (r.get('plane') or 1) == 1]
    assert len(rows) >= 20 * 5, '局数行数异常'
    assert any(r['state']['bench_full_flag'] for r in rows), \
        'bench_full_flag 全批恒 False = 写端断线或键永亮不了'
    with_frame = [r for r in rows if r['sim']['alloc_frame'] is not None]
    assert len(with_frame) >= len(rows) // 2, \
        'alloc_frame 覆盖过稀 = 决策段帧位采集断线'
    known_domains = {'stop_window', 'death'}
    for r in with_frame:
        af = r['sim']['alloc_frame']
        assert isinstance(af, dict) and 'active' in af
        if af.get('active'):
            assert af.get('domain') in known_domains
    # 20 局量级下停手窗/死亡域接管应出现过(分配器默认开;
    # 过 0 = 接管面退化,锁#11 验收无样本)
    assert any(r['sim']['alloc_active_any'] for r in rows), \
        '全批零接管帧 = alloc_active_any 写端断线'


def test_batch_check_reports_observation_keys_zero_violation() -> None:
    """批检链路闭合:observation_keys_live 随批自动扫且真批零违规。"""
    rep = simulate_p1_batch(5, pool='fallback', ledger=False, checks=True)
    ck = rep['checks_violations']['observation_keys_live']
    assert ck['violations'] == 0, f"games={ck.get('games')}"


def test_sess_active_env_disclosed() -> None:
    """投资环境名入账本(invest 注入写;空串=未注入机制性缺省)。"""
    from sr_od.application.currency_war.sim.cw_sim_invest import (
        SimInvestProfile,
    )
    prof = SimInvestProfile(active_env='昼之半神概念股', picks=())
    r = simulate_p1(0, pool='fallback', invest=prof)
    assert r.ledger, '账本为空'
    assert all(row.get('sess_active_env') == '昼之半神概念股'
               for row in r.ledger)
    r_plain = simulate_p1(0, pool='fallback')
    assert all(row.get('sess_active_env') == ''
               for row in r_plain.ledger)


def test_write_batch_ledger_carries_new_keys() -> None:
    """落盘链闭合:新键经 write_batch_ledger 落 jsonl 后可读回(判读
    CLI 消费面;向后兼容——旧账本无新键不炸)。"""
    import json
    import tempfile
    from pathlib import Path

    from sr_od.application.currency_war.sim.runner import write_batch_ledger
    results = [simulate_p1(s, pool='fallback') for s in (0, 7)]
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        write_batch_ledger(results, out)
        manifest = json.loads((out / 'manifest.json').read_text('utf-8'))
        assert manifest['rounds_rows'] == sum(len(r.ledger) for r in results)
        lines = (out / 'decisions.jsonl').read_text('utf-8').splitlines()
        assert lines
        row = json.loads(lines[0])
        assert isinstance(row['state']['bench_full_flag'], bool)
        assert isinstance(row['state']['board_next_tier'], dict)
        assert 'alloc_frame' in row['sim']
        assert 'sess_active_env' in row
