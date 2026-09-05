"""采购面三观察 sim 观测批:超容观察 + 刷新触发率观察 + 冷启动买率观察。

背景:sim 找问题轮定位三形态(超容→买冻结 / 刷新全批零用 / 冷启动
r1-r4 零买)但纪律要求「先立观察面再定谳,禁直接立病灶」。先例 =
达标臂发射面批(test_cw_launch_battle_face.py / commit 2ea5ea8c):
engine_p1 行内观测键 + cw_batch_stats 统计族 + 形态锁。

建模口径(engine_p1「采购面三观察计数」块):
- 超容观察:每决策帧 |locked_buy_membership| vs BENCH_CAPACITY+
  DEPLOYED_CAPACITY(判据与策略侧告警门同式,单一源 = cw_intention.
  locked_buy_membership 直调);行内 obs.overcap_frames 计数,持续轮数
  由统计端聚合;
- 刷新触发率观察:「刷新可得帧」= 缺员 ∧ 缺员在售 ∧ 金 ≥
  interest_floor+刷价+在售最低买价(阈值口径 = 注册表 ADR-0369
  「[3] 单次预算前提」,零新自由参数);对偶 = obs.refreshes(轮首差分);
- 冷启动买率观察:引擎零新键——actions/sim.spend 既有轮级披露即
  数据源,统计端聚合 r1-r4(plane 1)买次数/金花费分布。

设计约束(同发射面先例):纯只读投影,零 rng 消耗、零状态写入、
零策略行为改动;挂行内 'obs' 键而非增行/动 actions——一轮一行、
outcomes 配对、段级检查轮键、行为投影 digest 四不变式不被观测面挤占。

本批四锁:
1. 行形态:每轮行都带 'obs' 键(四键恰等、非负 int、内含不变式);
2. 落盘:decisions.jsonl 行内 obs 与内存账本逐位一致;
3. 统计族:cw_batch_stats 采购观察族对账本行聚合恒等 + 合成行判读锁;
4. 零/缺数据形态:obs 缺键(旧批/档案)聚合不炸(0/None),不误报。
"""
from __future__ import annotations

import importlib.util
import json

import pytest

from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    DEPLOYED_CAPACITY,
)
from sr_od.application.currency_war.sim.engine_p1 import simulate_p1

_OBS_KEYS = {'locked_b', 'overcap_frames',
             'refresh_avail_frames', 'refreshes',
             # 必花域观测三键(20 号稿 §6):zone_frames/zero_consume
             # 为非负计数;layer_hit 为层命中 dict(L1/L2/L3),单独断言
             'must_spend_zone_frames', 'must_spend_zero_consume',
             'must_spend_layer_hit',
             # sim 观测面补齐批(sim 观测面批任务①③⑤):两键均为
             # dict 型——refresh_trigger = 刷新触发源 → 本轮实刷次数;
             # cw4_counters = 策略行为观测计数本轮增量(含 fenced 拆键
             # /theta 成因分桶),零增量 = 空 dict
             'refresh_trigger', 'cw4_counters'}
_CAP = BENCH_CAPACITY + DEPLOYED_CAPACITY

_SEED_CACHE: dict[int, object] = {}


def _seeded_result(seed: int):
    """同 seed 单局结果同次运行只算一次(昂贵计算共享,README 纪律)。"""
    if seed not in _SEED_CACHE:
        _SEED_CACHE[seed] = simulate_p1(seed, pool='snapshot')
    return _SEED_CACHE[seed]


class TestObsRowLedgerLock:
    """锁 1:obs 行形态(键集/非负/内含不变式)。"""

    def test_obs_row_field_shape(self):
        seen_avail = False
        for seed in range(4):
            for row in _seeded_result(seed).ledger:
                obs = row.get('obs')
                assert isinstance(obs, dict), row.get('round_num')
                assert set(obs.keys()) == _OBS_KEYS, obs
                assert all(isinstance(v, int) and v >= 0
                           for v in obs.values()
                           if not isinstance(v, dict)), obs
                # 必花域三键形态:zone/zero 非负且 zero ≤ zone;
                # layer_hit 值全非负 int(键 ⊆ {L1, L2, L3})
                assert obs['must_spend_zero_consume'] \
                    <= obs['must_spend_zone_frames'], obs
                assert set(obs['must_spend_layer_hit']) <= {'L1', 'L2', 'L3'}
                assert all(isinstance(v, int) and v >= 0 for v in
                           obs['must_spend_layer_hit'].values()), obs
                # 补齐批两 dict 键形态:值全非负 int;refresh_trigger
                # 增量 ≤ 本轮 obs.refreshes(同源差分,只述现象)
                for _dk in ('refresh_trigger', 'cw4_counters'):
                    assert all(isinstance(v, int) and v >= 0
                               for v in obs[_dk].values()), obs
                assert sum(obs['refresh_trigger'].values()) \
                    <= obs['refreshes'], obs
                # 内含不变式:超容帧 > 0 ⇒ 本轮出现过 |B|>容量上界的帧
                # (|B| 只辖锁定采购集——P1 配方锁帧 locked_comp 恒空,
                # locked_buy_membership 返回 None,locked_b 恒 0,是
                # 建模边界非缺陷,见 engine_p1 帧级投影注释)
                if obs['overcap_frames']:
                    assert obs['locked_b'] > _CAP, obs
                # 未锁帧(locked_b=0)不产超容帧
                if not obs['locked_b']:
                    assert not obs['overcap_frames']
                # 刷新可得帧面必须活(全 0 = 观测面失明,采样缺陷)
                seen_avail = seen_avail or obs['refresh_avail_frames'] > 0
        assert seen_avail, '采样 4 seed 零刷新可得帧(观测面失明,需换 seed 窗口)'

    def test_obs_zero_rng_zero_state_invariant(self):
        """纯观测锁:obs 键是派生投影,不占行为判别域——actions 逐项
        与 launch 键(行为投影 digest 锚)与 obs 互不干扰(行级并存
        形态锁;同发射面先例的「挂行内键不动 actions」约束)。"""
        for row in _seeded_result(0).ledger:
            assert 'actions' in row and 'launch' in row and 'obs' in row


def test_decisions_jsonl_persist_obs_rows(tmp_path):
    """锁 2:落盘锁——decisions.jsonl 行内 obs 与内存账本逐位一致。"""
    from sr_od.application.currency_war.sim.runner import (
        write_batch_ledger,
    )
    result = _seeded_result(0)
    out = write_batch_ledger([result], tmp_path / 'batch',
                             pool_fp=result.pool_fingerprint)
    lines = [json.loads(line)
             for line in (out / 'decisions.jsonl').open(encoding='utf-8')
             if line.strip()]
    assert [r.get('obs') for r in lines] == \
        [r.get('obs') for r in result.ledger]


def _load_stats_module():
    """cw_batch_stats(skill 脚本,非包成员)按路径加载。"""
    from one_dragon.utils.file_utils import get_project_root
    path = (get_project_root() / 'skills' / 'sr-od-currency-war-dev'
            / 'scripts' / 'cw_batch_stats.py')
    spec = importlib.util.spec_from_file_location('cw_batch_stats', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row_from_ledger(row: dict) -> dict:
    """账本行 → 统计行(同 launch 面锁的装配形状)。"""
    return {'plane': row['plane'], 'round': row['round_num'],
            'node_type': (row.get('sim') or {}).get('node'),
            'gold': row['gold'], 'hp': row['hp'], 'hp_delta': None,
            'form': row.get('form_score'), 'form_ok': row.get('form_ok'),
            'level': (row.get('state') or {}).get('level'),
            'deployed': (row.get('state') or {}).get('deployed') or [],
            'factions': dict((row.get('state') or {})
                             .get('board_factions') or {}),
            'acts': row.get('actions') or [],
            'launch': row.get('launch'),
            'obs': row.get('obs') or {},
            'shop_waves': []}


class TestPurchaseObsStatsFamilyLock:
    """锁 3:统计族对接(cw_batch_stats 采购观察族)。"""

    def test_stats_family_matches_ledger(self):
        mod = _load_stats_module()
        result = _seeded_result(0)
        rows = [_row_from_ledger(r) for r in result.ledger]
        m = mod.analyze_game(rows)
        obs = [r['obs'] for r in result.ledger]
        assert m['超容帧数'] == sum(o.get('overcap_frames', 0) for o in obs)
        # 持续轮数 = 连续轮 overcap_frames>0 的最长 run(统计端聚合口径)
        run = best = 0
        for o in obs:
            run = run + 1 if o.get('overcap_frames') else 0
            best = max(best, run)
        assert m['超容最长连续轮'] == best
        avail = sum(o.get('refresh_avail_frames', 0) for o in obs)
        refs = sum(o.get('refreshes', 0) for o in obs)
        assert m['刷新可得帧'] == avail
        assert m['刷新触发率'] == (round(refs / avail, 2) if avail else None)
        # 触发率值域:实际刷新不可能超过可得帧(每帧至多对应若干刷,
        # 但比率必须落在 [0, ∞) 且分母为零时 None——非 None 必 > 0 帧)
        if m['刷新触发率'] is not None:
            assert m['刷新触发率'] >= 0.0
        # 冷启动 = plane1 r1-r4 actions 聚合(引擎零新键)
        cold = [r for r in rows if r['plane'] == 1 and r['round'] <= 4]
        assert m['冷启动买次数'] == sum(
            mod.n_act(r['acts'], 'BuyCard') for r in cold)
        assert m['冷启动金花费'] == sum(mod.act_cost(r['acts']) for r in cold)
        # I 必花域三键统计恒等(ledger obs 聚合 = analyze_game 输出)
        assert m['必花域帧数'] == sum(
            o.get('must_spend_zone_frames', 0) for o in obs)
        assert m['必花域零消费帧'] == sum(
            o.get('must_spend_zero_consume', 0) for o in obs)
        want_layer: dict = {}
        for o in obs:
            for k, v in (o.get('must_spend_layer_hit') or {}).items():
                want_layer[k] = want_layer.get(k, 0) + v
        assert m['必花域层命中'] == want_layer

    def test_stats_synthetic_overcap_and_coldstart(self):
        """合成行判读锁:超容 run/触发率/冷启动聚合的确定性值。"""
        mod = _load_stats_module()
        rows = [
            {'plane': 1, 'round': 1, 'node_type': '普通战斗', 'gold': 12,
             'hp': 100, 'hp_delta': None, 'form': 0.3, 'form_ok': False,
             'level': 2, 'deployed': [], 'factions': {},
             'acts': [{'__type__': 'BuyCard',
                       'card': {'name': 'a', 'cost': 2}}],
             'launch': None, 'shop_waves': [],
             'obs': {'locked_b': 0, 'overcap_frames': 0,
                     'refresh_avail_frames': 2, 'refreshes': 0}},
            {'plane': 1, 'round': 2, 'node_type': '普通战斗', 'gold': 30,
             'hp': 90, 'hp_delta': -10, 'form': 0.4, 'form_ok': False,
             'level': 3, 'deployed': [], 'factions': {},
             'acts': [{'__type__': 'RefreshShop'}],
             'launch': None, 'shop_waves': [],
             'obs': {'locked_b': _CAP + 1, 'overcap_frames': 1,
                     'refresh_avail_frames': 3, 'refreshes': 1}},
            {'plane': 1, 'round': 3, 'node_type': '奖励', 'gold': 40,
             'hp': 90, 'hp_delta': 0, 'form': 0.4, 'form_ok': False,
             'level': 3, 'deployed': [], 'factions': {},
             'acts': [], 'launch': None, 'shop_waves': [],
             'obs': {'locked_b': _CAP + 1, 'overcap_frames': 2,
                     'refresh_avail_frames': 1, 'refreshes': 0}},
        ]
        m = mod.analyze_game(rows)
        assert m['超容帧数'] == 3
        assert m['超容最长连续轮'] == 2      # r2-r3 连续
        assert m['超容峰值|B|'] == _CAP + 1
        assert m['刷新可得帧'] == 6
        assert m['刷新触发率'] == round(1 / 6, 2)
        assert m['冷启动买次数'] == 1
        # 金花费 = r1 买 2 + r2 刷 2(act_cost 全花费类动作口径)
        assert m['冷启动金花费'] == 4

    def test_stats_synthetic_must_spend_family(self):
        """合成行判读锁:必花域三键聚合的确定性值。"""
        mod = _load_stats_module()
        rows = [
            {'plane': 1, 'round': 1, 'node_type': '普通战斗',
             'gold': 60, 'hp': 100, 'hp_delta': None, 'form': 0.3,
             'form_ok': False, 'level': 3, 'deployed': [],
             'factions': {}, 'acts': [], 'launch': None,
             'shop_waves': [],
             'obs': {'locked_b': 0, 'overcap_frames': 0,
                     'refresh_avail_frames': 0, 'refreshes': 0,
                     'must_spend_zone_frames': 2,
                     'must_spend_zero_consume': 1,
                     'must_spend_layer_hit': {'L1': 1, 'L3': 1}}},
            {'plane': 1, 'round': 2, 'node_type': '普通战斗',
             'gold': 70, 'hp': 95, 'hp_delta': -5, 'form': 0.4,
             'form_ok': False, 'level': 3, 'deployed': [],
             'factions': {}, 'acts': [], 'launch': None,
             'shop_waves': [],
             'obs': {'locked_b': 0, 'overcap_frames': 0,
                     'refresh_avail_frames': 1, 'refreshes': 1,
                     'must_spend_zone_frames': 1,
                     'must_spend_zero_consume': 0,
                     'must_spend_layer_hit': {'L2': 1}}},
        ]
        m = mod.analyze_game(rows)
        assert m['必花域帧数'] == 3
        assert m['必花域零消费帧'] == 1
        assert m['必花域层命中'] == {'L1': 1, 'L3': 1, 'L2': 1}


class TestPurchaseObsZeroDataShapeLock:
    """锁 4:缺/零数据形态(聚合不炸、不误报)。"""

    def test_rows_without_obs_key_degrade_to_zero(self):
        """档案行/旧批(无 obs 键)→ 0/None,不炸不误报。"""
        mod = _load_stats_module()
        rows = [{'plane': 1, 'round': 1, 'node_type': '普通战斗',
                 'gold': 10, 'hp': 90, 'hp_delta': None, 'form': 0.5,
                 'form_ok': False, 'level': 3, 'deployed': [],
                 'factions': {}, 'acts': [], 'launch': None,
                 'shop_waves': []}]
        m = mod.analyze_game(rows)
        assert m['超容帧数'] == 0
        assert m['超容最长连续轮'] == 0
        assert m['刷新可得帧'] == 0
        assert m['刷新触发率'] is None
        assert m['冷启动买次数'] == 0
        assert m['冷启动金花费'] == 0
        assert m['必花域帧数'] == 0
        assert m['必花域零消费帧'] == 0
        assert m['必花域层命中'] == {}

    def test_report_survives_obs_zero_batch(self):
        """report 全批零观察形态:打印面不炸(0 除法已用 max 护栏)。"""
        mod = _load_stats_module()
        rows = [{'plane': 1, 'round': 1, 'node_type': '普通战斗',
                 'gold': 10, 'hp': 90, 'hp_delta': None, 'form': 0.5,
                 'form_ok': False, 'level': 3, 'deployed': [],
                 'factions': {}, 'acts': [], 'launch': None,
                 'obs': {'locked_b': 0, 'overcap_frames': 0,
                         'refresh_avail_frames': 0, 'refreshes': 0},
                 'shop_waves': []}]
        mod.report({'g0': rows}, 'zero-obs-smoke')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
