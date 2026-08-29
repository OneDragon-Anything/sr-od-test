"""W614 迁移批 0:sim 保真 P0 三补的单测(G1 装备记账/G2 上阵代理/G3 xp_per_refresh)。

蓝图出处:.debug/temp/currency_war/w613_strategy_refactor/BLUEPRINT.md §5
(批 0 前置件;临时文件,语义已固化进 cw_sim 注释与本测试)。

覆盖:
- 零漂移锚:不含新效果(默认 invest=False)的局行为投影 digest 逐位不变;
- G3:付费刷新产经验(淘金客 +2;数值源单一面 = cw_investments.STRATEGY_EFFECTS
  overlay,overlay 值变更 sim 跟随;免费刷不计),off 臂恒 0;
- G1:装备事件计数 + 逐轮未穿滞留/生锈暴露(min(10,n),词条语义
  cw_comps.RUST_AFFIX_NAME)+ 穿戴后滞留清零 + P1 出口滞留件数;
- G2:配方件躺 bench 轮数与上阵战力贡献代理的账本一致性。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace as _dc_replace

import pytest

from sr_od.application.currency_war import cw_sim as cw_sim_mod
from sr_od.application.currency_war.cw_effect_inventory import EffectSpec
from sr_od.application.currency_war.cw_investments import (
    STRATEGY_EFFECTS,
    EconomyEffect,
)
from sr_od.application.currency_war.cw_sim import simulate_p1
from sr_od.application.currency_war.cw_sim_invest import SimInvestProfile

# 零漂移锚:seeds 0..5(pool='snapshot'),行为投影 = 每轮
# (plane, round_num, gold, hp, level, actions(类型, reason, result))
# + 局级 (dir_round, final_hp, level, refreshes)。改 G1-G3 前抓取
# (2026-09-01);20 seed 全量锚见 w614_sim_fidelity/baseline_digest.md
# (digest 93989ec7…,与改前逐位一致已验证)。
# 批 3 重锚(2026-09-03):预算收权换核(W615 查表核替换 DP 姿态供给)
# 是行为批,digest c13c365b… = 最终基线(批 2 末 93ca26cc… 起的行为位移
# 由 w633 A/B 判据管辖,本锚此后继续做「 unintended drift 」哨兵)。
# 中间值 60aa8ced… 为 R3 驱逐度量修正前的过渡锚(作废,记档防二次踩)。
_ZERO_DRIFT_DIGEST_6 = (
    'c13c365ba768740da063287d954f502c26068146ccfd5f2fcefcebdf73f01094')


def _behavior_projection(results) -> str:
    proj = []
    for seed, r in enumerate(results):
        rows = []
        for row in r.ledger:
            acts = tuple(
                (a.get('__type__', ''), str(a.get('reason', '')),
                 str(a.get('result', '')))
                for a in row.get('actions') or [])
            rows.append((row.get('plane'), row.get('round_num'),
                         row.get('gold'), row.get('hp'),
                         (row.get('state') or {}).get('level'), acts))
        proj.append((seed, r.dir_round, r.final_hp, r.level,
                     r.refreshes, tuple(rows)))
    blob = json.dumps(proj, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def _p1_rows(result):
    return [row for row in result.ledger if (row.get('plane') or 1) == 1]


class TestZeroDriftAnchor:
    """零漂移锚:不含新效果的局合成结果逐位不变(迁移批 0 纪律)。"""

    def test_default_path_behavior_digest_unchanged(self):
        results = [simulate_p1(s, pool='snapshot') for s in range(6)]
        assert _behavior_projection(results) == _ZERO_DRIFT_DIGEST_6

    def test_default_path_new_fields_neutral(self):
        """默认路径(无投资注入)下新记账出口应全为零/中性值。"""
        r = simulate_p1(11, pool='snapshot')
        assert r.refresh_xp_total == 0
        assert all((row.get('sim') or {}).get('refresh_xp', 0) == 0
                   for row in r.ledger)


class TestG3XpPerRefresh:
    """G3:xp_per_refresh 合成器接入(付费刷新产经验;免费刷不计)。"""

    def test_overlay_source_single_source(self):
        """数值源单一面 = STRATEGY_EFFECTS overlay(非 STRATEGY_ECONOMY 聚合)。"""
        spec = STRATEGY_EFFECTS['淘金客']
        assert isinstance(spec, EffectSpec)
        assert isinstance(spec.payload, EconomyEffect)
        # 淘金客官方文本:每次消耗金币刷新 +2 经验;overlay 供值,sim 跟随
        assert spec.payload.xp_per_refresh == 2
        assert spec.pending is False   # 定谳条目直供数值,不走保守支

    def test_overlay_value_change_follows(self, monkeypatch):
        """源断言:overlay 值变更 sim 跟随(改 overlay,注册表聚合面不动)。"""
        spec = STRATEGY_EFFECTS['淘金客']
        patched = dict(STRATEGY_EFFECTS)
        patched['淘金客'] = _dc_replace(
            spec, payload=_dc_replace(spec.payload, xp_per_refresh=7))
        monkeypatch.setattr(cw_sim_mod, 'STRATEGY_EFFECTS', patched)
        prof = SimInvestProfile(active_env='',
                                picks=((1, 1, '淘金客'),))
        r = simulate_p1(0, pool='snapshot', invest=prof)
        assert r.refreshes > 0
        assert r.refresh_xp_total == 7 * r.refreshes

    def test_paid_refresh_grants_xp_on_arm(self):
        prof = SimInvestProfile(active_env='',
                                picks=((1, 1, '淘金客'),))
        for seed in (0, 3):
            r = simulate_p1(seed, pool='snapshot', invest=prof)
            # 淘金客不带免费刷额度 → 全部刷新都是付费刷 → 严格 2×刷新数
            assert r.refreshes > 0
            assert r.refresh_xp_total == 2 * r.refreshes
            # 经验真到 xp_progress 消费面:有 xp 入账的局,level 轨迹合法
            assert r.level >= 3

    def test_off_arm_no_xp(self):
        prof = SimInvestProfile(active_env='',
                                picks=((1, 1, '魔丸'),))
        for seed in (0, 3):
            r = simulate_p1(seed, pool='snapshot', invest=prof)
            assert r.refreshes > 0
            assert r.refresh_xp_total == 0

    def test_ledger_round_disclosure(self):
        prof = SimInvestProfile(active_env='',
                                picks=((1, 1, '淘金客'),))
        r = simulate_p1(0, pool='snapshot', invest=prof)
        round_xp = sum((row.get('sim') or {}).get('refresh_xp', 0)
                       for row in r.ledger)
        assert round_xp == r.refresh_xp_total


_SEED_CACHE: dict[int, object] = {}


def _seeded_result(seed: int):
    """同 seed 的单局结果同次运行只算一次(昂贵计算共享)。"""
    if seed not in _SEED_CACHE:
        _SEED_CACHE[seed] = simulate_p1(seed, pool='snapshot')
    return _SEED_CACHE[seed]


class TestG1EquipAccounting:
    """G1:装备事件落账(发放/穿戴/合成计数 + 滞留/生锈出口)。"""

    def test_event_counters_consistent(self):
        r = _seeded_result(7)
        assert r.equip_grants >= 1      # 供给/奖励节点必有发放
        assert r.equip_wears >= 0
        assert r.equip_syntheses >= 0
        # 发放 ≥ 穿戴 + 合成耗件之外的余量方向:持有量(末态)有界
        owned = _p1_rows(r)[-1]['state']['owned_equips']
        assert len(owned) <= r.equip_grants + r.equip_syntheses

    def test_rust_units_formula_and_exit(self):
        r = _seeded_result(7)
        rows = _p1_rows(r)
        for row in rows:
            sim = row['sim']
            assert sim['rust_units'] == min(10, sim['unworn_equips'])
            assert sim['unworn_equips'] == \
                len(row['state']['owned_equips'])
        # P1 出口滞留件数 = 末轮未穿件数;峰值 = 逐轮生锈暴露最大值
        assert r.p1_unworn_exit == rows[-1]['sim']['unworn_equips']
        assert r.p1_rust_units_peak == max(
            row['sim']['rust_units'] for row in rows)

    def test_wear_clears_stagnation(self):
        """穿戴后滞留清零:某轮穿上的件,同轮 owned 池里不再出现。"""
        r = _seeded_result(7)
        hit = False
        for row in _p1_rows(r):
            equipped = [e['equip'] for e in
                        (row['state'].get('equipped') or [])]
            if not equipped:
                continue
            owned = row['state']['owned_equips']
            for name in equipped:
                if name not in owned:
                    hit = True
        assert hit, '语料内未找到可验证的穿戴轮(采样缺陷,需换 seed)'

    def test_worn_total_field(self):
        r = _seeded_result(7)
        for row in _p1_rows(r):
            worn = sum(len(d.get('equips') or [])
                       for d in row['state'].get('deployed') or [])
            worn += sum(len(b.get('equips') or [])
                        for b in row['state'].get('bench') or [])
            assert row['sim']['worn_equips_total'] == worn


class TestG2DeployProxy:
    """G2:上阵代理记账(配方件躺 bench 轮数 + 战力贡献代理)。"""

    def test_bench_recipe_rounds_aggregate(self):
        r = _seeded_result(7)
        rows = _p1_rows(r)
        assert r.p1_bench_recipe_piece_rounds == sum(
            (row.get('sim') or {}).get('bench_recipe_pieces', 0)
            for row in rows)

    def test_deployed_power_aggregate(self):
        r = _seeded_result(7)
        rows = _p1_rows(r)
        values = [(row.get('sim') or {}).get('deployed_power', 0)
                  for row in rows]
        assert all(v >= 0 for v in values)
        assert r.p1_deployed_power_avg == pytest.approx(
            sum(values) / len(values), abs=0.011)

    def test_deployed_power_semantics(self):
        """代理语义锁:deployed_power = Σ(star + core∈target 计 1)。

        target 集不可从账本逐轮复原(部署块读 session 现读),此处锁
        下界:场上有人时 power ≥ 上阵人数(每人 star≥1 贡献)。
        """
        r = _seeded_result(7)
        for row in _p1_rows(r):
            n = len(row['state'].get('deployed') or [])
            assert row['sim']['deployed_power'] >= n
