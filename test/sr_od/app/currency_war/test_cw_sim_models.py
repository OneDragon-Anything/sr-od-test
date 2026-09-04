# -*- coding: utf-8 -*-
"""test_cw_sim_models 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- sim_checks_repay: test_cw_sim_checks_repay.py
- w174_engine_completion: test_cw_w174_engine_completion.py
- w213_sim_supply_two_step: test_cw_w213_sim_supply_two_step.py
- coarse_battle: test_cw_coarse_battle.py
- first_passage: test_cw_first_passage.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== sim_checks_repay ====================

from sr_od.application.currency_war.sim.checks import calib, corpus, ledger, pool, runner, runtime
def _row(rn: int = 1, gold: int = 10, bench: list | None = None,
         deployed: list | None = None, cap: int = 4,
         actions: list | None = None, target_comp: str = '',
         sim: dict | None = None, level: int = 3,
         equipped: list | None = None) -> dict:
    return {
        'plane': 1, 'round_num': rn, 'gold': gold, 'hp': 50,
        'target_comp': target_comp,
        'state': {
            'board': {}, 'level': level,
            'bench': bench if bench is not None else [],
            'deployed': deployed if deployed is not None else [],
            'cap': cap,
            'equipped': equipped if equipped is not None else [],
            'owned_equips': [],
        },
        'actions': actions or [],
        'sim': sim if sim is not None else {
            'node': 'battle', 'delta': -5, 'gold_before': gold,
            'income': {'base': 5}, 'spend': {'buys': {}, 'levelup': 0,
                                             'refresh': 0},
            'shop_waves': [], 'merges': 0,
        },
    }


# --- 账本不变量类(批⑮/⑰/⑧) --------------------------------------

def test_gold_nonneg_bidirectional() -> None:
    bad = [_row(gold=-1)]
    assert ledger.check_gold_nonneg_invariant(bad), '负金未报=静默失效'
    good = [_row(gold=0), _row(gold=5)]
    assert not ledger.check_gold_nonneg_invariant(good)


def test_bench_capacity_bidirectional() -> None:
    bench10 = [{'char_id': f'c{i}', 'faction': 'x'} for i in range(10)]
    assert ledger.check_bench_capacity_invariant(
        [_row(bench=bench10)]), 'bench>9 未报'
    bench9 = bench10[:9]
    assert not ledger.check_bench_capacity_invariant([_row(bench=bench9)])


def test_deployed_schema_filter_bidirectional() -> None:
    bad = [_row(bench=[{'char_id': '', 'faction': 'x'}])]
    assert ledger.check_deployed_schema_filter(bad), '空 char_id 未报'
    bad2 = [_row(deployed=[{'char_id': 'a', 'faction': 'x'},
                           {'char_id': '', 'faction': 'x'}])]
    assert ledger.check_deployed_schema_filter(bad2)
    good = [_row(bench=[{'char_id': 'a', 'faction': 'x'}],
                 deployed=[{'char_id': 'b', 'faction': 'x'}])]
    assert not ledger.check_deployed_schema_filter(good)


# --- 动作语义类(自由批/批⑳) ----------------------------------------

def test_engine_seed_not_resold_bidirectional() -> None:
    buy = [{'__type__': 'BuyCard',
            'card': {'name': '青雀', 'cost': 1},
            'reason': 'engine_seed'}]
    bad = [
        _row(rn=3, actions=buy),
        _row(rn=4, actions=[{'__type__': 'SellBench', 'name': '青雀'}]),
    ]
    assert pool.check_engine_seed_not_resold(bad), '跨轮即卖未报'
    # 好:≥3 轮后卖(合成消化窗外)
    ok_late = [
        _row(rn=3, actions=buy),
        _row(rn=6, actions=[{'__type__': 'SellBench', 'name': '青雀'}]),
    ]
    assert not pool.check_engine_seed_not_resold(ok_late)
    # 好:同轮收集 ≥2,冗余让位(ADR-0276 同族豁免)
    ok_collect = [
        _row(rn=3, actions=buy + [
            {'__type__': 'BuyCard', 'card': {'name': '青雀', 'cost': 1},
             'reason': 'engine_seed'}]),
        _row(rn=4, actions=[{'__type__': 'SellBench', 'name': '青雀'}]),
    ]
    assert not pool.check_engine_seed_not_resold(ok_collect)


def test_buys_at_full_bench_bidirectional() -> None:
    bench9 = [{'char_id': f'c{i}', 'faction': 'x'} for i in range(9)]
    buy = [{'__type__': 'BuyCard', 'card': {'name': 'a', 'cost': 1},
            'reason': 'line'}]
    bad = [
        _row(rn=1, bench=bench9, sim={'node': 'battle', 'merges': 0,
                                       'shop_waves': []}),
        _row(rn=2, bench=bench9, actions=buy,
             sim={'node': 'battle', 'merges': 0, 'shop_waves': []}),
    ]
    assert ledger.check_buys_at_full_bench(bad), '满仓买未报'
    good = [
        _row(rn=1, bench=bench9,
             sim={'node': 'battle', 'merges': 0, 'shop_waves': []}),
        _row(rn=2, bench=bench9,
             actions=[{'__type__': 'SellBench', 'name': 'c0'}] + buy,
             sim={'node': 'battle', 'merges': 0, 'shop_waves': []}),
    ]
    assert not ledger.check_buys_at_full_bench(good)


def test_oscillation_xp_cap_bidirectional() -> None:
    osc = [{'__type__': 'BuyCard', 'card': {'name': 'a', 'cost': 1},
            'reason': 'line'},
           {'__type__': 'SellBench', 'name': 'a'}]
    bad = [_row(rn=1, level=9, actions=osc,
                sim={'node': 'battle', 'shop_waves': []})]
    # lv9 need=84,4 XP < 30% → 不报;lv5 need=20 → 4>6? 否。
    # 用两次振荡(8 XP)对 lv5(need 20,30%=6)报
    osc2 = osc + [
        {'__type__': 'BuyCard', 'card': {'name': 'b', 'cost': 1},
         'reason': 'line'},
        {'__type__': 'SellBench', 'name': 'b'},
    ]
    bad = [_row(rn=1, level=5, actions=osc2,
                sim={'node': 'battle', 'shop_waves': []})]
    assert ledger.check_oscillation_xp_cap(bad), '白拿 XP 超限未报'
    good = [_row(rn=1, level=9, actions=osc2,
                 sim={'node': 'battle', 'shop_waves': []})]
    assert not ledger.check_oscillation_xp_cap(good)


def test_levelup_flat4_lock_bidirectional() -> None:
    bad = [_row(actions=[{'__type__': 'LevelUp', 'cost': 4}],
                sim={'node': 'battle', 'merges': 0, 'shop_waves': [],
                     'spend': {'buys': {}, 'levelup': 6, 'refresh': 0}})]
    assert ledger.check_levelup_flat4_ledger_lock(bad), 'flat4 偏离未报'
    good = [_row(actions=[{'__type__': 'LevelUp', 'cost': 4}],
                 sim={'node': 'battle', 'merges': 0, 'shop_waves': [],
                      'spend': {'buys': {}, 'levelup': 4, 'refresh': 0}})]
    assert not ledger.check_levelup_flat4_ledger_lock(good)


# --- 注册表类(批⑲) --------------------------------------------------

def test_phantom_equip_no_wear_bidirectional() -> None:
    bad = [_row(equipped=[{'char': 'x', 'equip': '钻石(幻影)'}])]
    assert ledger.check_phantom_equip_no_wear(bad), '幻影装备未报'
    real = next(iter(
        __import__(
            'sr_od.application.currency_war.data.cw_equipment_data',
            fromlist=['EQUIPMENT_ROSTER']).EQUIPMENT_ROSTER))
    good = [_row(equipped=[{'char': 'x', 'equip': real}])]
    assert not ledger.check_phantom_equip_no_wear(good)


# --- 线/供给类(成型批) ----------------------------------------------
# (v1 线库语义检查器——no_future_carry_sold / carry_on_shelf_responded /
# dead_system_second_pivot / bond_fallback / carry_gate / protect_set /
# carry_gate_outcome / recipe_refresh——随 ADR-0336 删除,双向锁同步删;
# degrade_recover_mutex 是通用 target 切换检查,保留)

def test_degrade_recover_mutex_bidirectional() -> None:
    a, b = 'lineA', 'lineB'
    bad = [_row(rn=1, target_comp=a), _row(rn=2, target_comp=b),
           _row(rn=3, target_comp=b), _row(rn=4, target_comp=a)]
    assert ledger.check_degrade_recover_mutex(bad), '切线回锁 relapse 未报'
    good = [_row(rn=1, target_comp=a), _row(rn=2, target_comp=b),
            _row(rn=6, target_comp=a)]   # >3 轮回锁不辖
    assert not ledger.check_degrade_recover_mutex(good)


# --- 批级聚合类(批⑫/批④) -------------------------------------------

def test_endgold_residue_channel_probe() -> None:
    sim = {'node': 'battle', 'merges': 0,
           'shop_waves': [{'gold': 30,
                           'cards': [{'name': 'a', 'cost': 1,
                                      'faction': 'x'}]}]}
    rows = [_row(rn=7, gold=30, sim=dict(sim))]
    r = runtime.check_endgold_residue_channel_probe([rows])
    assert r['has_card_room_no_buy'] == 1, '有牌有位不买通道未归因'
    bench9 = [{'char_id': f'c{i}', 'faction': 'x'} for i in range(9)]
    r2 = runtime.check_endgold_residue_channel_probe(
        [[_row(rn=7, gold=30, bench=bench9, sim=dict(sim))]])
    assert r2['bench_full'] == 1


def test_shop_cost_conformance_bidirectional() -> None:
    # 坏:lv9(level 表 p4=0.30)零 4 费供给,200+ 抽全 1 费
    waves = [{'gold': 50,
              'cards': [{'name': f'c{i}', 'cost': 1, 'faction': 'x'}
                        for i in range(5)]} for _ in range(45)]
    sim = {'node': 'battle', 'merges': 0, 'shop_waves': waves}
    bad = [_row(rn=9, level=9, sim=dict(sim))]
    r = runtime.check_shop_cost_conformance([bad])
    assert r['violations'] >= 1, 'lv9 4费零供给未报'
    # 好:lv3 全 1 费(REFRESH_PROB lv3={1:1.0})
    r2 = runtime.check_shop_cost_conformance(
        [[_row(rn=3, level=3, sim=dict(sim))]])
    assert r2['violations'] == 0


# --- 语料级(批⑬/批⑧) -----------------------------------------------

def test_attach_run_detector_bidirectional() -> None:
    bad = [{'run_id': 'r1', 'plane': 1, 'round_num': 5}]
    assert runtime.check_attach_run_detector(bad), '接管段未标'
    good = [{'run_id': 'r2', 'plane': 1, 'round_num': 1},
            {'run_id': 'r2', 'plane': 1, 'round_num': 2}]
    assert not runtime.check_attach_run_detector(good)


def test_hp_monotonic_sentinel_bidirectional() -> None:
    bad = [{'run_id': 'r1', 'hp_after': 70},
           {'run_id': 'r1', 'hp_after': 100}]
    assert runtime.check_hp_monotonic_sentinel(bad), 'hp 上升未报'
    good = [{'run_id': 'r1', 'hp_after': 70},
            {'run_id': 'r1', 'hp_after': 60}]
    assert not runtime.check_hp_monotonic_sentinel(good)


def test_plane_reached_consistency_bidirectional() -> None:
    bad_summary = {'run_id': 'r1', 'plane_reached': 3}
    outcomes = [{'run_id': 'r1', 'plane': 2}]
    assert runtime.check_plane_reached_consistency(
        bad_summary, outcomes), 'summary/outcomes 不一致未报'
    ok = {'run_id': 'r1', 'plane_reached': 2}
    assert not runtime.check_plane_reached_consistency(ok, outcomes)


# --- 条件披露类(批⑲/批㉓) -------------------------------------------

def test_conditional_disclosures_skip_and_fire() -> None:
    # 依赖未接线 → 披露跳过不判
    r = runtime.check_supply_agent_semantics([[_row()]])
    assert r['violations'] == 0 and '依赖未接线' in r['note']
    # 依赖在(sim.supply)→ 计数披露
    row = _row(sim={'node': 'battle', 'shop_waves': [], 'merges': 0,
                    'supply': {'pick_reason': 'x'}})
    r2 = runtime.check_supply_agent_semantics([[row]])
    assert r2['games_with_supply_ledger'] == 1
    # briefing:字段不在 → 休眠标;在 → 计数
    r3 = runtime.check_briefing_pipeline_liveness([[_row()]])
    assert '休眠' in r3['note']
    row2 = _row(sim={'node': 'battle', 'shop_waves': [], 'merges': 0,
                     'comp_score_calls': 7})
    r4 = runtime.check_briefing_pipeline_liveness([[row2]])
    assert r4['comp_score_calls'] == 7


# --- 锚登记/工具(批⑭/批⑯/批⑤) -------------------------------------

def test_anchor_seed_portability_and_lowchannel() -> None:
    """锚登记对照检查(语义锁:rep 从当前锚登记派生,随换锚自动跟)。

    ADR-0306 换锚(886f8a39)暴露原硬编码 066c4185 值锁=锁旧锚
    副作用;本锁语义=「登记锚在位时,同指纹同指标报告判 match +
    drift 全零」;失配检测能力由负例锁(不属于任何登记段的指纹
    → 不判 match)。
    """
    reg = calib.ANCHOR_REGISTRY_N300
    rep = {'pool_fingerprint': reg['pool_fingerprint_prefix'] + 'xx',
           **{k: v for k, v in reg['metrics'].items()
              if isinstance(v, (int, float))}}
    r = corpus.check_anchor_seed_portability_n600(rep)
    assert r['n300_fp_match'] and r['violations'] == 0
    assert all(d == 0 for d in r['n300_drift'].values())
    assert 's300_n600_drift' in r
    bad = dict(rep, pool_fingerprint='deadbeef00000000xx')
    rb = corpus.check_anchor_seed_portability_n600(bad)
    assert not rb['n300_fp_match']
    r2 = corpus.check_anchor_lowchannel_registry({})
    assert r2['registry_in_place']


def test_anchor_segment_noise_band() -> None:
    ra = {'hp_ge_60': 0.05, 'avg_final_hp': 29.0,
          'pool_fingerprint': 'fp'}
    rb = {'hp_ge_60': 0.055, 'avg_final_hp': 33.0,
          'pool_fingerprint': 'fp'}
    r = corpus.check_anchor_segment_noise_band(ra, rb)
    assert r['marks']['hp_ge_60']['in_band']   # 0.005 ≤ 0.02
    assert not r['marks']['avg_final_hp']['in_band']   # 4.0 > 1.6


def test_adr0266_ab_guard() -> None:
    r = corpus.check_adr0266_ab_guard(-1.0, -1.0)
    assert r['adr0266_closure_shape']
    assert not corpus.check_adr0266_ab_guard(1.0, -1.0)['adr0266_closure_shape']


def test_rare_metric_min_n() -> None:
    r = corpus.check_rare_metric_min_n({'engines2': (0.24, 300),
                                     'trio3': (0.02, 12)}, min_n=60)
    assert r['undetermined'] == ['trio3']


def test_new_checks_in_batch_set() -> None:
    """清偿批逐局锁进批量集(sim 批次自动扫;ADR-0289)。
    (v1 线库语义检查器随 ADR-0336 删除;degrade_recover_mutex 保留)"""
    for name in ('gold_nonneg', 'bench_capacity',
                 'deployed_schema_filter', 'engine_seed_not_resold',
                 'buys_at_full_bench', 'oscillation_xp_cap',
                 'levelup_flat4_lock', 'phantom_equip_no_wear',
                 'degrade_recover_mutex'):
        assert name in runner._BATCH_CHECKS, name


def test_batch_level_entrypoint_runs_all() -> None:
    """批级聚合入口:空账本也全键返回(依赖断裂不静默)。"""
    r = runner.run_batch_level_checks([[]], report={'n': 0},
                                   pool_map={})
    for k in ('late_deploy_full', 'mc_faction_calib',
              'calibration_dead_knob_disclosure',
              'encounter_rung_sample_budget',
              'anchor_seed_portability_n600',
              'anchor_lowchannel_registry'):
        assert k in r, k



# ==================== w174_engine_completion ====================

import re

import pytest

from sr_od.application.currency_war.kernel import cw_evolution as cw_evolution_mod
from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_evolution import (
    EvolutionState,
    evolution_step,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState

from sr_od.application.currency_war.kernel.cw_battle_calib import _board_factions_of
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    CompTransaction,
    GameState,
    _recount_board,
    simulate,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import StrategySession


def _char(name: str, star: int = 1, row: str = 'back') -> BenchChar:
    c = CHARACTERS[name]
    return BenchChar(slot=0, char_id=name,
                     faction=(c.factions or ['?'])[0],
                     position_pref=row, star=star)


def _sess(pair: tuple[str, ...]) -> StrategySession:
    """p1_pair 配方锁定帧的 session(v3_intention 挂体系对)。"""
    sess = StrategySession()
    sess.v3_intention = IntentionState(p1_pair=pair)
    return sess


# run42 型(run42 复盘:手握 4 种列车件只上 1):deployed 7 件全为
# 非引擎散件(无 仙舟/持续伤害/列车同行 羁绊),cap 满;bench 4 件列车。
_B_FILLER = ('银枝', '刃', '镜流', '布洛妮娅', '阮·梅', '娜塔莎', '翡翠')
_B_TRAIN = ('丹恒·饮月', '姬子·启行', '姬子', '星期日')


def _state(bench=(), deployed=(), level: int = 7,
           round_num: int = 4) -> GameState:
    st = GameState()
    st.plane = 1
    st.round_num = round_num
    st.level = level
    st.gold = 30
    st.bench = list(bench)
    # 排位平衡:前 3 后 4(front_max=4/back_max=6,守终态排不变量)
    st.deployed = [(_char(n, row='front') if i < 3 else _char(n))
                   for i, n in enumerate(deployed)]
    st.board = _recount_board(st.deployed)
    return st


def _t42_frame() -> GameState:
    """列车 owned 4 ≥2 ∧ 上场 0;deployed 7 件非引擎散件占满 cap。"""
    return _state(bench=[_char(n) for n in _B_TRAIN],
                  deployed=_B_FILLER)


def _completion_txs(actions: list) -> list[CompTransaction]:
    return [a for a in actions if isinstance(a, CompTransaction)
            and 'engine_complete' in (a.reason or '')]


def test_completion_tx_deploys_owned_engine_members():
    """①缺口帧:cap 满局手握≥门槛体系件 → 补完事务换上场(run42 型)。"""
    st = _t42_frame()
    sess = _sess(('列车同行', '仙舟'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert len(txs) == 1
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    # 列车同行 on-board 达门槛(≥2):拥有已够 → 上场补完
    assert _board_factions_of(out.deployed).get('列车同行', 0) >= 2


def test_completion_protects_engine_and_pair_pieces():
    """②保护序:undeploy 只吃非保护散件——pair/引擎贡献件不下场
   (deployed 掺一件仙舟引擎件符玄,保护集辖,不被换下)。"""
    st = _state(bench=[_char(n) for n in _B_TRAIN],
                deployed=(*_B_FILLER[:6], '符玄'))
    sess = _sess(('列车同行', '仙舟'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert txs, '缺口仍在(列车 owned≥2 上场 0)应发补完事务'
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied'
    # 仙舟引擎件(符玄)不被换下;下的全是非保护散件
    assert '符玄' in {d.char_id for d in out.deployed if d is not None}   # ADR-0392
    downed = {st.deployed[i].char_id for i in (txs[0].undeploy or [])}
    assert downed <= set(_B_FILLER)


def test_completion_no_gap_no_tx():
    """③无缺口不发射:owned≥tier∧已上场够 / owned<tier → 无补完事务
   (获取问题不辖——本批边界,归 早期买入门)。"""
    # 已成帧:仙舟 3 上场 + 列车 2 上场 → 无缺口
    st = _state(
        deployed=('丹恒·饮月', '符玄', '藿藿', '姬子·启行', '姬子'),
        bench=(_char('桑博'), _char('卡芙卡')), level=5)
    sess = _sess(('仙舟', '列车同行'))
    assert not _completion_txs(evolution_step(st, sess, EvolutionState()))
    # owned<tier:仙舟仅 1 件在手
    st2 = _state(deployed=('姬子·启行', '姬子'), bench=(_char('藿藿'),),
                 level=5)
    sess2 = _sess(('仙舟', '列车同行'))
    assert not _completion_txs(evolution_step(st2, sess2, EvolutionState()))


def test_completion_flag_off_restores_baseline():
    """④A/B 通道:engine_completion=False 回 后行为(同帧无补完
   事务);对照组(开)同帧有——差异即本批行为面。"""
    st = _t42_frame()
    sess = _sess(('列车同行', '仙舟'))
    actions_off = evolution_step(st, sess, EvolutionState(),
                                 engine_completion=False)
    assert not _completion_txs(actions_off)
    assert _completion_txs(evolution_step(st, sess, EvolutionState()))


def test_completion_final_window_exemption():
    """⑤末窗豁免:r8(cap 满,undeploy 非空)补完事务照发——净效果
   pair on-board 不减∧引擎数不减;ADR-0363 件2「防丢」语义不辖补上。"""
    st = _t42_frame()
    st.round_num = 8   # P1 位面末窗(nodes_of_plane=9 → 剩 ≤1 轮)
    sess = _sess(('列车同行', '仙舟'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert txs, '末窗补完(换下散件换上体系件)应豁免冻结'
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied'


def test_completion_frozen_on_encounter_node():
    """⑤b 遭遇/boss 冻结轮不启动补完(与既有演进纪律一致)。"""
    st = _t42_frame()
    st.node_type = 'boss'
    sess = _sess(('列车同行', '仙舟'))
    assert not _completion_txs(evolution_step(st, sess, EvolutionState()))


def test_completion_seeie_system_single_card():
    """⑥希儿系单卡判据:希儿在手未上场 → 补完事务上希儿(档=1)。"""
    st = _state(bench=(_char('希儿'), _char('姬子·启行')),
                deployed=_B_FILLER)
    sess = _sess(('希儿系', '列车同行'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert txs and '希儿系' in txs[0].reason
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied'
    assert '希儿' in {d.char_id for d in out.deployed if d is not None}   # ADR-0392


def test_completion_bench_overflow_sells_unprotected():
    """⑦bench 容量不足:undeploy 落位溢出 → 卖最弱非保护 bench 件腾位
   (保护件不受卖;卖的全是散件)。"""
    st = _t42_frame()
    # bench 塞满 9 槽:4 列车件 + 5 散件(非保护)
    filler = ('银枝', '刃', '镜流', '布洛妮娅', '娜塔莎')
    st.bench = [_char(n) for n in _B_TRAIN + filler]
    sess = _sess(('列车同行', '仙舟'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert txs, 'bench 满仍应有腾位补完(卖散件腾 bench)'
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    # 卖的全是非保护散件;列车件(保护)绝不被卖
    sold = {st.bench[i].char_id for i, src in (txs[0].sell or [])
            if src == 'bench'}
    assert sold <= set(filler)
    assert _board_factions_of(out.deployed).get('列车同行', 0) >= 2


class _LogRecorder:
    """记录 log.info 调用(观测行格式锁用;不触发真实日志链路)。"""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def info(self, msg: str, *args: object) -> None:
        self.lines.append(msg % args if args else msg)


def test_engine_complete_log_undeploy_roster(monkeypatch: pytest.MonkeyPatch):
    """⑧W228 观测行格式锁:engine-complete 行 undeploy 追加下场名单
    (角色名 list;空则 [])——判读问题⑥,补完保护锚点(-3)
    需名单级可核。零行为改动:仅锁日志行格式。"""
    rec = _LogRecorder()
    monkeypatch.setattr(cw_evolution_mod, 'log', rec)
    # 有下场件帧(cap 满):undeployed=[角色名,...],名单与 tx 索引一致
    st = _t42_frame()
    txs = _completion_txs(evolution_step(st, _sess(('列车同行', '仙舟')),
                                         EvolutionState()))
    assert txs
    line = next(x for x in rec.lines if 'engine-complete' in x)
    expect_names = [st.deployed[i].char_id
                    for i in (txs[0].undeploy or [])]
    assert f'undeployed={expect_names}' in line, line
    assert re.search(r'undeploy=\d+', line), line  # 计数仍在
    # 无下场件帧(cap 未满,纯 deploy 补完):名单为空 → undeployed=[]
    # (列车 owned 4 ≥ tier ∧ 上场 0 缺口;deployed 仅 2 散件有 room,
    # 补完不需换下任何人)
    st2 = _state(bench=[_char(n) for n in _B_TRAIN],
                 deployed=_B_FILLER[:2])
    txs2 = _completion_txs(evolution_step(st2, _sess(('列车同行', '仙舟')),
                                          EvolutionState()))
    assert txs2 and not (txs2[0].undeploy or []), txs2
    line2 = [x for x in rec.lines if 'engine-complete' in x][-1]
    assert 'undeployed=[]' in line2, line2


# ==================== w213_sim_supply_two_step ====================

from sr_od.application.currency_war.kernel import cw_events

from sr_od.application.currency_war.sim.engine_p1 import simulate_p1


def test_sim_supply_two_step_scoring_branch_reachable(
        monkeypatch) -> None:
    """① 评分分支(refresh_used=True)在 sim 可达——修复前恒 False。"""
    calls: list[dict] = []
    orig = cw_events.decide_supply

    def spy(options, state, target_comp, config, refresh_used=False):
        calls.append({'refresh_used': refresh_used,
                      'n_opts': len(options)})
        return orig(options, state, target_comp, config, refresh_used)

    monkeypatch.setattr(cw_events, 'decide_supply', spy)
    for seed in range(12):
        simulate_p1(seed, planes=2, pool='fallback')
        if any(c['refresh_used'] for c in calls):
            break
    assert any(c['refresh_used'] for c in calls), (
        'decide_supply 评分分支(refresh_used=True)在 sim 从未执行'
        '——「恒 idx0」伪影回归(ADR-0394)')


def test_sim_supply_reroll_chain_and_once_per_game(monkeypatch) -> None:
    """②③ 两步链形态 + session 级只刷一次。"""
    # 显式命中种子集(纪律 12 续:实测探底后固化,非命中种子不再付运行成本)。
    # 探针记录(2026-09-03,seed 0-11 逐局 spy 实测):9/12 出现两步链;
    # 取三形态代表——0=[F,T,T] 立即重掷 / 4=[F,F,T] 迟重掷 / 8=[F,F,T,T] 双掷。
    # 引擎改动若位移 RNG 消费致列表失准 → 本测试红,重跑探针更新列表(同校准锚责)。
    _REROLL_SEEDS = (0, 4, 8)
    # 每局的调用轨迹(seed → refresh_used 序列)
    traces: list[list[bool]] = []
    cur: list[bool] = []
    orig = cw_events.decide_supply

    def spy(options, state, target_comp, config, refresh_used=False):
        pick = orig(options, state, target_comp, config, refresh_used)
        cur.append(refresh_used)
        return pick

    monkeypatch.setattr(cw_events, 'decide_supply', spy)
    for seed in _REROLL_SEEDS:
        cur = []
        simulate_p1(seed, planes=2, pool='fallback')
        if cur:
            traces.append(cur)
    assert traces, '显式种子集全空轨迹(引擎 RNG 消费位移?)——重跑探针更新 _REROLL_SEEDS'
    # ② 两步链:某局出现 False…True 序列(首调触发刷新 → 重掷后评分)
    assert any(
        any(not t[i] and t[i + 1] for i in range(len(t) - 1))
        for t in traces), (
        f'无「首掷→重掷评分」两步链(修复前形态): {traces}')
    # ③ session 级一次:refresh_used=True 的调用只出现在轨迹尾部连续段
    #    (首掷 False 若干次 + 至多一段末尾 True)——更严的等价判据:
    #    True 出现后不再出现 False(标志置位后单调)
    for t in traces:
        seen_true = False
        for flag in t:
            if flag:
                seen_true = True
            assert not (seen_true and not flag), (
                f'refresh_used 标志回退(session 级一次被破坏): {t}')


def test_sim_p1_key_hit_metric_pipe() -> None:
    """④ key 命中度量管道:hits ≤ total,同 seed 可复现。"""
    a = simulate_p1(3, planes=2, pool='fallback')
    b = simulate_p1(3, planes=2, pool='fallback')
    assert 0 <= a.p1_key_hit_hits <= a.p1_key_hit_total
    assert (a.p1_key_hit_hits, a.p1_key_hit_total) == (
        b.p1_key_hit_hits, b.p1_key_hit_total), '同 seed 度量不可复现'


# ==================== coarse_battle ====================

import json
import random

import pytest as _coarse_battle_pytest

from sr_od.application.currency_war.kernel import cw_coarse_battle as cb
from sr_od.application.currency_war.sim import engine_p1 as cw_sim
from sr_od.application.currency_war.sim import pool as _coarse_battle_pool
from sr_od.application.currency_war.sim.checks import runner as _coarse_battle_runner
# 拟合产物交付口径(逐单元;粗模型参数的机器可读真值,
# 来源 = 冻结语料拟合,禁与其它口径混写)
_DELIVERY_WIN_P: dict[str, dict[int, float]] = {
    'battle': {0: 0.009, 1: 0.356, 2: 0.315, 3: 0.292},
    'encounter': {0: 0.038, 1: 0.026, 2: 0.264, 3: 0.275},
    'boss': {0: 0.077, 1: 0.027, 2: 0.187, 3: 0.238},
}


# 位面维前 = 拟合交付值(F6 语料治理批重记:伪影档剔除后口径;
# 原值含结算瞬时 hp=0 伪读数拆出的 ±40 量级假档——对局档案真值
# 语料 tools/cw/proofs/p15/(P1 n=290)未删失最大单轮 |Δ|=36)
_DELIVERY_LOSS_HIST: dict[str, dict[int, int]] = {
    'battle': {1: 7, 3: 3, 4: 9, 5: 10, 6: 5, 7: 2, 8: 19, 9: 11,
               10: 6, 11: 18, 12: 6, 13: 74, 14: 1, 15: 9, 17: 3,
               18: 3, 19: 4, 20: 2, 21: 4, 23: 2},
    'encounter': {4: 1, 5: 1, 6: 4, 7: 1, 8: 4, 9: 7, 10: 10, 15: 1,
                  17: 1, 18: 1, 22: 1, 24: 11, 26: 7, 28: 15},
    'boss': {3: 1, 11: 2, 12: 1, 13: 2, 14: 4, 30: 1, 32: 5, 34: 11,
             36: 8},
}
# _LOSS_FIT 重拟合交付口径(dd-012:对局档案真值语料
# tools/cw/proofs/p15/ corpus_battle_loss.jsonl 逐行最小二乘,
# P1 非删失败局行 battle n=82 / encounter n=66;原值系已灭且污染
# 的 w324 语料回归值,锁改理由 = 拟合依据语料不得再为已灭污染源)
_DELIVERY_LOSS_FIT: dict[str, tuple[float, float, float]] = {
    'battle': (11.48, -4.21, 10.45),
    'encounter': (15.06, -3.27, 12.18),
}


class _ScriptRng:
    """脚本化 rng 桩:random() 返回定值;choices 返回定值档。"""

    def __init__(self, uniform: float, pick: int) -> None:
        self._uniform = uniform
        self._pick = pick

    def random(self) -> float:
        return self._uniform

    def choices(self, vals, weights=None, k: int = 1):  # type: ignore[no-untyped-def]
        return [self._pick]


def test_win_p_table_matches_delivery() -> None:
    """胜率表逐单元 = 拟合产物交付口径(含 Beta 收缩注入值)。"""
    for node, rows in _DELIVERY_WIN_P.items():
        for rung, p in rows.items():
            assert cb.injected_win_p(node, rung) == _coarse_battle_pytest.approx(p)


def test_rung01_cells_not_injected() -> None:
    """rung0/1 单元遥测样本充足,不注入(份额 0,值 = p_data)。"""
    for node, planes in cb._WIN_TABLE.items():
        for rung in (0, 1):
            n, p_data = planes[1][rung]
            assert cb.prior_share(node, rung) == 0.0
            assert cb.injected_win_p(node, rung) == p_data
            assert n > 0


def test_prior_share_hard_caps() -> None:
    """先验份额恒 ≤25%、等效样本恒 ≤12(裸收缩口径禁止)。"""
    for node in cb._WIN_TABLE:
        for rung in (2, 3):
            share = cb.prior_share(node, rung)
            assert 0.0 < share <= cb.PLAZA_SHARE_MAX + 1e-12
            n = cb._WIN_TABLE[node][1][rung][0]
            alpha = share * n / (1 - share)
            assert alpha <= cb.ALPHA_CAP + 1e-9
    # 值锁两例(份额帽在薄/厚单元的两个端型):
    assert cb.prior_share('battle', 2) == _coarse_battle_pytest.approx(0.203, abs=1e-3)
    assert cb.prior_share('battle', 3) == _coarse_battle_pytest.approx(0.25, abs=1e-9)


def test_win_state_plus2() -> None:
    """胜态:均匀抽样 < P(win) → delta = +2(封顶,池语料主型)。"""
    assert cb.sample_battle_delta(
        'battle', 1, 80, _ScriptRng(0.1, 13)) == cb.WIN_CAP


def test_loss_mean_match_and_floor() -> None:
    """败态:battle 直方采样 + rung 均值匹配取整;hp 地板 = max(1,·)。"""
    # rung0:13 + (11.48 − 0 − 10.45) = 14.03 → 14(dd-012 重拟合口径)
    assert cb.sample_battle_delta(
        'battle', 0, 100, _ScriptRng(0.99, 13)) == -14
    # rung3:13 + (11.48 − 12.63 − 10.45) = 1.4 → 1(取整后落伤害地板;
    # rung 梯度方向仍向下,但该档已被地板吸收)
    assert cb.sample_battle_delta(
        'battle', 3, 100, _ScriptRng(0.99, 13)) == -1
    # 地板:伤害越过 HP → hp_after 落吸收态 1(取真值支持域内上限档
    # 36——F6 剔档后直方无 84/88,原取值 = 伪影档)
    assert cb.sample_battle_delta(
        'battle', 0, 5, _ScriptRng(0.99, 36)) == -(5 - 1)
    # 直方支持域:采样结果必落在合法区间(固定种子扫 200 次)
    rng = random.Random(20260901)
    for _ in range(200):
        r = cb.sample_battle_delta('encounter', 1, 200, rng)
        assert r <= -1 or r == cb.WIN_CAP  # 败态伤害 / 胜态回血两态


def test_boss_clamp_conditional_on_hp_before() -> None:
    """boss 钳制按 hp_before 条件化:≤35 门 + 区间内 0.929;>35 不钳。"""
    # ≤35 且区间内抽中钳制 → 归吸收态(不经伤害直方/乘子)
    assert cb.sample_battle_delta(
        'boss', 1, 30, _ScriptRng(0.1, 36)) == -(30 - 1)
    # ≤35 但区间内抽中不钳 → 直方采样 + 地板兜底(结构性双路径)
    assert cb.sample_battle_delta(
        'boss', 1, 20, _ScriptRng(0.999, 14)) == -(20 - 6)
    # >35:钳制分支结构性不可达(即使钳制抽签必中)——0.929 只辖低 HP
    # (uniform 0.5 = 败态且 >35 门直接跳过钳制分支)
    assert cb.sample_battle_delta(
        'boss', 1, 40, _ScriptRng(0.5, 36)) == -36


def test_difficulty_multiplier_off_by_default() -> None:
    """难度乘子未核先验默认关闭:difficulty 取值不影响采样结果。"""
    rng_a = random.Random(7)
    rng_b = random.Random(7)
    for _ in range(50):
        a = cb.sample_battle_delta('boss', 2, 60, rng_a, difficulty=200)
        b = cb.sample_battle_delta('boss', 2, 60, rng_b, difficulty=None)
        assert a == b


def test_difficulty_multiplier_enabled(monkeypatch: _coarse_battle_pytest.MonkeyPatch) -> None:
    """开关置位后:伤害按 1.052^(Δ难度) 缩放(A8 基准 108 不缩放)。"""
    monkeypatch.setattr(cb, 'DIFFICULTY_MULT_ENABLED', True)
    base = cb.sample_battle_delta(
        'boss', 1, 60, _ScriptRng(0.99, 36), difficulty=108)
    assert base == -36
    up = cb.sample_battle_delta(
        'boss', 1, 60, _ScriptRng(0.99, 36), difficulty=109)
    assert up == -round(36 * 1.052 ** 1)


def test_engine_switch_dual_mode(monkeypatch: _coarse_battle_pytest.MonkeyPatch) -> None:
    """引擎开关:coarse 走粗模型;delta 臂走 Δ池;reward/supply 恒 Δ池。"""
    coarse_calls: list[str] = []
    monkeypatch.setattr(
        cb, 'sample_battle_delta',
        lambda node, rung, hp, rng, **kw: coarse_calls.append(node) or 0)
    pool_calls: list[str] = []
    _orig_ldf = _coarse_battle_pool.live_delta_for

    def _spy_ldf(node: str, key: int, rng, **kw):  # type: ignore[no-untyped-def]
        pool_calls.append(node)
        return _orig_ldf(node, key, rng, **kw)

    monkeypatch.setattr(cw_sim, 'live_delta_for', _spy_ldf)

    monkeypatch.setattr(cb, 'BATTLE_ENGINE_MODE', 'coarse')
    r1 = cw_sim.simulate_p1(0, pool='snapshot')
    assert coarse_calls, 'coarse 默认:战斗类节点必走粗模型'
    assert not (set(coarse_calls) & {'reward', 'supply'})
    assert {'reward', 'supply'} <= set(pool_calls), 'reward/supply 仍走 Δ池'

    monkeypatch.setattr(cb, 'BATTLE_ENGINE_MODE', 'delta')
    coarse_calls.clear()
    pool_calls.clear()
    r2 = cw_sim.simulate_p1(0, pool='snapshot')
    assert not coarse_calls, 'delta 对照臂:粗模型不被消费'
    assert 'battle' in pool_calls, 'delta 臂:战斗类节点回 Δ池经验分布'
    assert r1.seed == r2.seed


def test_coarse_game_smoke_snapshot_fingerprint() -> None:
    """冒烟:coarse 模式整局可跑、hp 轨迹合法、池指纹照常随局携带
    (reward/supply 池消费与基准对拍依赖指纹披露)。"""
    r = cw_sim.simulate_p1(1, pool='snapshot')
    assert r.hp_trail
    assert all(0 <= h <= 100 for h in r.hp_trail)
    # 局指纹 = 池指纹 + 装备发放结构版本位(供给重校准起)
    assert r.pool_fingerprint == (
        _coarse_battle_pool.pool_fingerprint(_coarse_battle_pool.resolve_pool('snapshot')[0])
        + f'+eqg{cw_sim.EQUIP_GRANT_CALIB_VERSION}')


# ===== 位面维(P1 先行)锁:结构见 test_cw_w405_planarize 说明 =====


def test_p1_layer_zero_drift_literals() -> None:
    """P1 层逐位 = 拟合交付值(现口径 = F6 语料治理后)。

    位面化只加结构不改数:P1 层是 W346 一阶矩门 + W377 剂量曲线
    三方一致的载体,任何 P1 数值变动必须走显式重校准批(禁止顺手调)
    ——F6 语料治理批即该显式批:剔除结算瞬时 hp=0 伪影档(battle
    {±42,±43,−64,+46,+84,+88}/encounter {+45,+83};真值上限锚=
    tools/cw/proofs/p15/ 对局档案语料 P1 未删失最大单轮 |Δ|=36)。
    """
    for node, hist in _DELIVERY_LOSS_HIST.items():
        assert cb._LOSS_HIST[node][1] == hist
    for node, fit in _DELIVERY_LOSS_FIT.items():
        assert cb._LOSS_FIT[node][1] == fit
    for node, rungs in _DELIVERY_WIN_P.items():
        for rung, p in rungs.items():
            assert cb.injected_win_p(node, rung, plane=1) == \
                _coarse_battle_pytest.approx(p)


def test_p2_alias_lock() -> None:
    """P2 别名锁:别名表显式指向 plane 1,取表回同一对象(不拷贝)。

    P2 未采样,别名即「已知偏差」的机器可读声明(W357 regate:
    boss +4.57 hp / 钳制率 −38.81 pp / encounter 钳制率 −6.19 pp
    为继承的现状,非本结构引入);未来 P2 语料换表只动 plane 2 槽位。
    """
    assert set(cb._P2_ALIAS) == {'battle', 'encounter', 'boss'}
    for node, aliased in cb._P2_ALIAS.items():
        assert aliased == 1
        assert cb._node_table(cb._LOSS_HIST, node, 2) \
            is cb._LOSS_HIST[node][1]
        assert cb._node_table(cb._WIN_TABLE, node, 2) \
            is cb._WIN_TABLE[node][1]
    # _LOSS_FIT 无 boss 条目(斜率 CI 含 0 退常数,不做均值匹配),
    # 别名断言只辖 battle/encounter
    for node in ('battle', 'encounter'):
        assert cb._node_table(cb._LOSS_FIT, node, 2) \
            is cb._LOSS_FIT[node][1]
    # 钳制参数:P2 别名同值
    assert cb._boss_clamp_params(2) == cb._boss_clamp_params(1) \
        == (cb.BOSS_CLAMP_HP_CUT, cb.BOSS_CLAMP_P_LOW)
    # 未声明位面(如 3)按别名链落到 plane 1,不 KeyError
    assert cb._node_table(cb._LOSS_HIST, 'boss', 3) is cb._LOSS_HIST['boss'][1]
    # 行为面:同 seed 下 plane=2 与 plane=1 采样逐位一致
    for node in ('battle', 'encounter', 'boss'):
        rng_a = random.Random(11)
        rng_b = random.Random(11)
        for _ in range(30):
            a = cb.sample_battle_delta(node, 2, 60, rng_a, plane=1)
            b = cb.sample_battle_delta(node, 2, 60, rng_b, plane=2)
            assert a == b
        assert cb.injected_win_p(node, 2, plane=2) \
            == cb.injected_win_p(node, 2, plane=1)
        assert cb.prior_share(node, 2, plane=2) \
            == cb.prior_share(node, 2, plane=1)


def test_default_plane_keeps_signature_compatible() -> None:
    """旧调用面零漂移:不传 plane 的三函数全部等价于 plane=1。"""
    rng_a = random.Random(23)
    rng_b = random.Random(23)
    for node in ('battle', 'encounter', 'boss'):
        for rung in range(4):
            assert cb.injected_win_p(node, rung) \
                == cb.injected_win_p(node, rung, plane=1)
            assert cb.prior_share(node, rung) \
                == cb.prior_share(node, rung, plane=1)
        for _ in range(20):
            a = cb.sample_battle_delta(node, 1, 70, rng_a)
            b = cb.sample_battle_delta(node, 1, 70, rng_b, plane=1)
            assert a == b


def test_coarse_calib_version_disclosed_in_ledger_manifest(
        monkeypatch: _coarse_battle_pytest.MonkeyPatch, tmp_path) -> None:
    """版本披露锁:COARSE_CALIB_VERSION=4 且进 sim 台账 manifest。

    DESIGN §验证:局终指纹核对锚——防止「结构改了、披露没跟上」的
    跨版本对比污染;回归批脚本头部按本常量断言版本号。
    2→3 = F6 语料治理(P1 败局直方剔伪影档,pooled_mean 重算);
    3→4 = dd-012 重拟合(P1 _LOSS_FIT 改对局档案真值语料回归值)。
    """
    assert cb.COARSE_CALIB_VERSION == 4
    r = cw_sim.simulate_p1(1, pool='snapshot')
    out = _coarse_battle_runner.write_batch_ledger([r], tmp_path / 'batch')
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['coarse_calib_version'] == cb.COARSE_CALIB_VERSION


from sr_od.application.currency_war.sim import runner as _coarse_battle_runner


# ==================== first_passage ====================

import math

from sr_od.application.currency_war.kernel.cw_first_passage import (
    _loss_dist,
    first_passage_win,
    hp_floor,
    plane_hp_ratio,
    p_win_lambda,
    posture_guidance,
    risk_posture,
)


def test_k1_gamblers_ruin_flip():
    """K1 核心:同均值异方差两线,选择随 hp 翻转(教学校验例)。

    线 A(低方差,板强 3):μ≈0.8 → hp=25 剩 2 节点必活。
    线 B(高方差,板强 0):μ≈14,CV 0.5 → 掉血离散大,hp=15 剩 2 节点均值必死但右尾存活。
    """
    # HP=25 剩 2 节点:A 必活,B 有死亡尾
    pa = first_passage_win(3, 25, 2)
    pb = first_passage_win(0, 25, 2)
    assert pa > pb
    # HP=15 剩 2 节点:A(强板)仍高;弱板 B 的 P(win) 仍有右尾 > 0(首达语义:不是期望判死)
    pb15 = first_passage_win(0, 15, 2)
    assert 0.0 < pb15 < 0.5


def test_first_passage_monotone():
    """P(win) 对 hp 单调不减;nodes_left 越多越难。"""
    for hp in (10, 30, 60):
        assert first_passage_win(2, hp, 5) >= first_passage_win(2, hp - 1, 5)
    assert first_passage_win(2, 40, 9) <= first_passage_win(2, 40, 2)


def test_lambda_peak_shape():
    """λ_hp 峰形断言(18 号主张二):远离屏障≈0 → 临界带峰 → 漂移深处回落。

    弱板(μ=14)剩 9 节点:均值耗血 126 → hp=200(远离)λ 小;hp≈120-140(P(win) 0.4-0.85
    临界带)λ 峰;hp=60(均值路径深处,P(win)≈0)λ 回落为 0。
    (弱板长程下「必死边缘」的 hp 绝对值高 —— 漂移 14/节点把屏障推到 ~130;三区律的区
    边界由 (μ, hp, nodes) 联合解出,正是「手写 hp 阈值」要被替代的证据。)
    """
    lam_far = p_win_lambda(0, 200, 9)
    lam_peak = max(p_win_lambda(0, h, 9) for h in range(115, 145, 5))
    lam_deep = p_win_lambda(0, 60, 9)
    assert lam_peak > lam_far       # 峰 > 远离屏障区
    assert lam_peak > lam_deep      # 峰 > 漂移深处(P(win)≈0 区,±1 血无差)


def test_three_zones():
    """三区律:强板高血=盈余;中血=临界;弱板低血长程=必死边缘。"""
    assert risk_posture(3, 90, 3) in ('盈余', '临界')
    assert risk_posture(0, 10, 9) == '必死边缘'
    assert posture_guidance('必死边缘').startswith('方差追求')
    assert posture_guidance('临界').startswith('方差回避')


def test_degenerate_cases():
    assert first_passage_win(3, 100, 0) == 1.0   # 无节点剩 = 活
    assert first_passage_win(3, 0, 1) == 0.0     # 无血 = 死


# —— v1(ADR-0176):位面条件化 + hp_floor 反解 + 位面乘子模型导出 ——


def test_plane_scales_loss():
    """位面难度进掉血分布(W443 合一后 μ 方向由标定决定,非单调先验):
    - tier≥1:P2 严劣于 P1(μ_P2(tier)=(1−p(rung))·L_cond_mix > P1 先验 μ
      tier1 7.0 / tier2 2.5)→ P(win) 单调不升(浮点容差 1e-9);
    - tier0 显式例外:P1 先验 μ0=14(弱板粗锚)高于 P2 标定 μ0≈13.2
      ——P2 无条件期望不含「每战全损」悲观注入,方向反转是标定事实,
      本锁固化防回退到「P2 恒更凶」的旧先验。
    (P3 别名 P2:非单调断言对 plane=3 同值成立。)"""
    for tier in (1, 2):
        for hp in (20, 40, 60):
            p1 = first_passage_win(tier, hp, 6, plane=1)
            p2 = first_passage_win(tier, hp, 6, plane=2)
            p3 = first_passage_win(tier, hp, 6, plane=3)
            assert p1 + 1e-9 >= p2 >= p3 - 1e-9, (
                f"tier={tier} hp={hp}: P1≥P2≥P3 违反({p1:.4f}/{p2:.4f}/{p3:.4f})")
    # tier0 反转例外(P3=P2 别名逐位)
    mu1 = _loss_dist(0, 1)[1][0]
    mu2 = _loss_dist(0, 2)[1][0]
    mu3 = _loss_dist(0, 3)[1][0]
    assert mu1 > mu2, f"P1 弱板先验 μ={mu1} 应高于 P2 标定 μ={mu2}"
    assert mu2 == mu3, "P3 别名 P2(标定域声明)"


def test_hp_floor_definition():
    """hp_floor = 最小 hp 使 P(win) ≥ target;单调、且该 hp-1 处不达 target(有解时)。"""
    for (tier, nodes, target) in ((1, 8, 0.6), (2, 4, 0.7), (3, 6, 0.6)):
        fl = hp_floor(tier, nodes, target)
        assert first_passage_win(tier, fl, nodes) >= target, f"floor {fl} 未达 target"
        if 1 < fl < 100:
            assert first_passage_win(tier, fl - 1, nodes) < target, f"floor {fl} 非最小"
    # 强板短程:低血即可达标 → 地板低
    assert hp_floor(3, 2, 0.6) <= 10
    # 弱板长程:hp_cap 内无解 → 返回 cap(模型如实说「无底可保」,决策侧由 ratio 接管)
    assert hp_floor(0, 9, 0.9) == 100


def test_plane_hp_ratio_semantics():
    """位面乘子语义(W443 两态标定合一后的现语义;旧 0176 v1 主张
    「弱板长程 > 强板短程」随 PLANE_LOSS_SCALE 退役——新标定下强板
    P1 分支 μ 极小(0.8)而 P2 μ 由胜率通道给出(≈4.6),比值天然顶
    2.0 夹界,方向反转是标定事实非退化):

    - 弱板长程:ratio > 1(该更早保血);
    - 强板短程:顶 2.0 夹界(P1 分母极小,P2 标定 μ 相对大);
    - 夹界:任意 (tier, nodes) ratio ∈ [1.0, 2.0];
    - P3 别名 P2(标定域声明)逐位相等;
    - 弱板长程扩展 cap:真实血上限内两原均无解时 ratio 仍正确(≠1 假性退化)。
    """
    r2_weak = plane_hp_ratio(1, 9, target_pwin=0.6, plane=2)
    r3_weak = plane_hp_ratio(1, 9, target_pwin=0.6, plane=3)
    assert r2_weak > 1.0, "弱板长程 P2 应上浮"
    assert r2_weak == r3_weak, "P3 别名 P2 → 乘子逐位相等"
    r2_strong = plane_hp_ratio(3, 2, target_pwin=0.6, plane=2)
    assert r2_strong == 2.0, "强板短程顶夹界(P1 分支 μ=0.8 vs P2 标定)"
    for tier in (0, 1, 2, 3):
        for nodes in (2, 6, 9, 18):
            for plane in (2, 3):
                r = plane_hp_ratio(tier, nodes, target_pwin=0.6, plane=plane)
                assert 1.0 <= r <= 2.0, f"ratio 夹界违反:tier={tier} n={nodes} p={plane} → {r}"
    # 扩展 cap:tier0 长程真实 cap 内两原无解,ratio 仍反映位面标定(不退化 1.0)
    r0 = plane_hp_ratio(0, 18, target_pwin=0.6, plane=2)
    assert r0 >= 1.0