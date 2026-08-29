# -*- coding: utf-8 -*-
"""ADR-0289 检查项清偿批:新检查器双向锁(锁防锁)。

每类至少一条双向:构造违规必报(防静默失效)/好样本必过(防
误报)。真实 sim 批次的分布级行为不在此锁(锁分布数值 =
change-detector 陷阱)。
"""
from __future__ import annotations

from sr_od.application.currency_war import cw_sim_checks as chk


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
    assert chk.check_gold_nonneg_invariant(bad), '负金未报=静默失效'
    good = [_row(gold=0), _row(gold=5)]
    assert not chk.check_gold_nonneg_invariant(good)


def test_bench_capacity_bidirectional() -> None:
    bench10 = [{'char_id': f'c{i}', 'faction': 'x'} for i in range(10)]
    assert chk.check_bench_capacity_invariant(
        [_row(bench=bench10)]), 'bench>9 未报'
    bench9 = bench10[:9]
    assert not chk.check_bench_capacity_invariant([_row(bench=bench9)])


def test_deployed_schema_filter_bidirectional() -> None:
    bad = [_row(bench=[{'char_id': '', 'faction': 'x'}])]
    assert chk.check_deployed_schema_filter(bad), '空 char_id 未报'
    bad2 = [_row(deployed=[{'char_id': 'a', 'faction': 'x'},
                           {'char_id': '', 'faction': 'x'}])]
    assert chk.check_deployed_schema_filter(bad2)
    good = [_row(bench=[{'char_id': 'a', 'faction': 'x'}],
                 deployed=[{'char_id': 'b', 'faction': 'x'}])]
    assert not chk.check_deployed_schema_filter(good)


# --- 动作语义类(自由批/批⑳) ----------------------------------------

def test_engine_seed_not_resold_bidirectional() -> None:
    buy = [{'__type__': 'BuyCard',
            'card': {'name': '青雀', 'cost': 1},
            'reason': 'engine_seed'}]
    bad = [
        _row(rn=3, actions=buy),
        _row(rn=4, actions=[{'__type__': 'SellBench', 'name': '青雀'}]),
    ]
    assert chk.check_engine_seed_not_resold(bad), '跨轮即卖未报'
    # 好:≥3 轮后卖(合成消化窗外)
    ok_late = [
        _row(rn=3, actions=buy),
        _row(rn=6, actions=[{'__type__': 'SellBench', 'name': '青雀'}]),
    ]
    assert not chk.check_engine_seed_not_resold(ok_late)
    # 好:同轮收集 ≥2,冗余让位(ADR-0276 同族豁免)
    ok_collect = [
        _row(rn=3, actions=buy + [
            {'__type__': 'BuyCard', 'card': {'name': '青雀', 'cost': 1},
             'reason': 'engine_seed'}]),
        _row(rn=4, actions=[{'__type__': 'SellBench', 'name': '青雀'}]),
    ]
    assert not chk.check_engine_seed_not_resold(ok_collect)


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
    assert chk.check_buys_at_full_bench(bad), '满仓买未报'
    good = [
        _row(rn=1, bench=bench9,
             sim={'node': 'battle', 'merges': 0, 'shop_waves': []}),
        _row(rn=2, bench=bench9,
             actions=[{'__type__': 'SellBench', 'name': 'c0'}] + buy,
             sim={'node': 'battle', 'merges': 0, 'shop_waves': []}),
    ]
    assert not chk.check_buys_at_full_bench(good)


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
    assert chk.check_oscillation_xp_cap(bad), '白拿 XP 超限未报'
    good = [_row(rn=1, level=9, actions=osc2,
                 sim={'node': 'battle', 'shop_waves': []})]
    assert not chk.check_oscillation_xp_cap(good)


def test_levelup_flat4_lock_bidirectional() -> None:
    bad = [_row(actions=[{'__type__': 'LevelUp', 'cost': 4}],
                sim={'node': 'battle', 'merges': 0, 'shop_waves': [],
                     'spend': {'buys': {}, 'levelup': 6, 'refresh': 0}})]
    assert chk.check_levelup_flat4_ledger_lock(bad), 'flat4 偏离未报'
    good = [_row(actions=[{'__type__': 'LevelUp', 'cost': 4}],
                 sim={'node': 'battle', 'merges': 0, 'shop_waves': [],
                      'spend': {'buys': {}, 'levelup': 4, 'refresh': 0}})]
    assert not chk.check_levelup_flat4_ledger_lock(good)


# --- 注册表类(批⑲) --------------------------------------------------

def test_phantom_equip_no_wear_bidirectional() -> None:
    bad = [_row(equipped=[{'char': 'x', 'equip': '钻石(幻影)'}])]
    assert chk.check_phantom_equip_no_wear(bad), '幻影装备未报'
    real = next(iter(
        __import__(
            'sr_od.application.currency_war.data.cw_equipment_data',
            fromlist=['EQUIPMENT_ROSTER']).EQUIPMENT_ROSTER))
    good = [_row(equipped=[{'char': 'x', 'equip': real}])]
    assert not chk.check_phantom_equip_no_wear(good)


# --- 线/供给类(成型批) ----------------------------------------------
# (v1 线库语义检查器——no_future_carry_sold / carry_on_shelf_responded /
# dead_system_second_pivot / bond_fallback / carry_gate / protect_set /
# carry_gate_outcome / recipe_refresh——随 ADR-0336 删除,双向锁同步删;
# degrade_recover_mutex 是通用 target 切换检查,保留)

def test_degrade_recover_mutex_bidirectional() -> None:
    a, b = 'lineA', 'lineB'
    bad = [_row(rn=1, target_comp=a), _row(rn=2, target_comp=b),
           _row(rn=3, target_comp=b), _row(rn=4, target_comp=a)]
    assert chk.check_degrade_recover_mutex(bad), '切线回锁 relapse 未报'
    good = [_row(rn=1, target_comp=a), _row(rn=2, target_comp=b),
            _row(rn=6, target_comp=a)]   # >3 轮回锁不辖
    assert not chk.check_degrade_recover_mutex(good)


# --- 批级聚合类(批⑫/批④) -------------------------------------------

def test_endgold_residue_channel_probe() -> None:
    sim = {'node': 'battle', 'merges': 0,
           'shop_waves': [{'gold': 30,
                           'cards': [{'name': 'a', 'cost': 1,
                                      'faction': 'x'}]}]}
    rows = [_row(rn=7, gold=30, sim=dict(sim))]
    r = chk.check_endgold_residue_channel_probe([rows])
    assert r['has_card_room_no_buy'] == 1, '有牌有位不买通道未归因'
    bench9 = [{'char_id': f'c{i}', 'faction': 'x'} for i in range(9)]
    r2 = chk.check_endgold_residue_channel_probe(
        [[_row(rn=7, gold=30, bench=bench9, sim=dict(sim))]])
    assert r2['bench_full'] == 1


def test_shop_cost_conformance_bidirectional() -> None:
    # 坏:lv9(level 表 p4=0.30)零 4 费供给,200+ 抽全 1 费
    waves = [{'gold': 50,
              'cards': [{'name': f'c{i}', 'cost': 1, 'faction': 'x'}
                        for i in range(5)]} for _ in range(45)]
    sim = {'node': 'battle', 'merges': 0, 'shop_waves': waves}
    bad = [_row(rn=9, level=9, sim=dict(sim))]
    r = chk.check_shop_cost_conformance([bad])
    assert r['violations'] >= 1, 'lv9 4费零供给未报'
    # 好:lv3 全 1 费(REFRESH_PROB lv3={1:1.0})
    r2 = chk.check_shop_cost_conformance(
        [[_row(rn=3, level=3, sim=dict(sim))]])
    assert r2['violations'] == 0


# --- 语料级(批⑬/批⑧) -----------------------------------------------

def test_attach_run_detector_bidirectional() -> None:
    bad = [{'run_id': 'r1', 'plane': 1, 'round_num': 5}]
    assert chk.check_attach_run_detector(bad), '接管段未标'
    good = [{'run_id': 'r2', 'plane': 1, 'round_num': 1},
            {'run_id': 'r2', 'plane': 1, 'round_num': 2}]
    assert not chk.check_attach_run_detector(good)


def test_hp_monotonic_sentinel_bidirectional() -> None:
    bad = [{'run_id': 'r1', 'hp_after': 70},
           {'run_id': 'r1', 'hp_after': 100}]
    assert chk.check_hp_monotonic_sentinel(bad), 'hp 上升未报'
    good = [{'run_id': 'r1', 'hp_after': 70},
            {'run_id': 'r1', 'hp_after': 60}]
    assert not chk.check_hp_monotonic_sentinel(good)


def test_plane_reached_consistency_bidirectional() -> None:
    bad_summary = {'run_id': 'r1', 'plane_reached': 3}
    outcomes = [{'run_id': 'r1', 'plane': 2}]
    assert chk.check_plane_reached_consistency(
        bad_summary, outcomes), 'summary/outcomes 不一致未报'
    ok = {'run_id': 'r1', 'plane_reached': 2}
    assert not chk.check_plane_reached_consistency(ok, outcomes)


# --- 条件披露类(批⑲/批㉓) -------------------------------------------

def test_conditional_disclosures_skip_and_fire() -> None:
    # 依赖未接线 → 披露跳过不判
    r = chk.check_supply_agent_semantics([[_row()]])
    assert r['violations'] == 0 and '依赖未接线' in r['note']
    # 依赖在(sim.supply)→ 计数披露
    row = _row(sim={'node': 'battle', 'shop_waves': [], 'merges': 0,
                    'supply': {'pick_reason': 'x'}})
    r2 = chk.check_supply_agent_semantics([[row]])
    assert r2['games_with_supply_ledger'] == 1
    # briefing:字段不在 → 休眠标;在 → 计数
    r3 = chk.check_briefing_pipeline_liveness([[_row()]])
    assert '休眠' in r3['note']
    row2 = _row(sim={'node': 'battle', 'shop_waves': [], 'merges': 0,
                     'comp_score_calls': 7})
    r4 = chk.check_briefing_pipeline_liveness([[row2]])
    assert r4['comp_score_calls'] == 7


# --- 锚登记/工具(批⑭/批⑯/批⑤) -------------------------------------

def test_anchor_seed_portability_and_lowchannel() -> None:
    """锚登记对照检查(语义锁:rep 从当前锚登记派生,随换锚自动跟)。

    ADR-0306 换锚(886f8a39)暴露原硬编码 066c4185 值锁=锁旧锚
    副作用;本锁语义=「登记锚在位时,同指纹同指标报告判 match +
    drift 全零」;失配检测能力由负例锁(不属于任何登记段的指纹
    → 不判 match)。
    """
    reg = chk.ANCHOR_REGISTRY_N300
    rep = {'pool_fingerprint': reg['pool_fingerprint_prefix'] + 'xx',
           **{k: v for k, v in reg['metrics'].items()
              if isinstance(v, (int, float))}}
    r = chk.check_anchor_seed_portability_n600(rep)
    assert r['n300_fp_match'] and r['violations'] == 0
    assert all(d == 0 for d in r['n300_drift'].values())
    assert 's300_n600_drift' in r
    bad = dict(rep, pool_fingerprint='deadbeef00000000xx')
    rb = chk.check_anchor_seed_portability_n600(bad)
    assert not rb['n300_fp_match']
    r2 = chk.check_anchor_lowchannel_registry({})
    assert r2['registry_in_place']


def test_anchor_segment_noise_band() -> None:
    ra = {'hp_ge_60': 0.05, 'avg_final_hp': 29.0,
          'pool_fingerprint': 'fp'}
    rb = {'hp_ge_60': 0.055, 'avg_final_hp': 33.0,
          'pool_fingerprint': 'fp'}
    r = chk.check_anchor_segment_noise_band(ra, rb)
    assert r['marks']['hp_ge_60']['in_band']   # 0.005 ≤ 0.02
    assert not r['marks']['avg_final_hp']['in_band']   # 4.0 > 1.6


def test_adr0266_ab_guard() -> None:
    r = chk.check_adr0266_ab_guard(-1.0, -1.0)
    assert r['adr0266_closure_shape']
    assert not chk.check_adr0266_ab_guard(1.0, -1.0)['adr0266_closure_shape']


def test_rare_metric_min_n() -> None:
    r = chk.check_rare_metric_min_n({'engines2': (0.24, 300),
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
        assert name in chk._BATCH_CHECKS, name


def test_batch_level_entrypoint_runs_all() -> None:
    """批级聚合入口:空账本也全键返回(依赖断裂不静默)。"""
    r = chk.run_batch_level_checks([[]], report={'n': 0},
                                   pool_map={})
    for k in ('late_deploy_full', 'mc_faction_calib',
              'calibration_dead_knob_disclosure',
              'encounter_rung_sample_budget',
              'anchor_seed_portability_n600',
              'anchor_lowchannel_registry'):
        assert k in r, k
