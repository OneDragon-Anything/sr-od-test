"""采购面三观察 sim 观测批:超容观察 + 刷新触发率观察 + 冷启动买率观察。

背景:sim 找问题轮定位三形态(超容→买冻结 / 刷新全批零用 / 冷启动
r1-r4 零买)但纪律要求「先立观察面再定谳,禁直接立病灶」。先例 =
达标臂发射面批(test_cw_launch_battle_face.py / commit 2ea5ea8c):
engine_p1 行内观测键 + 形态锁。

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

本批两锁(原统计族/零数据形态两锁随 cw_batch_stats 四指标裁定移除
——2026-09-08 用户规格只留四指标,采购观察统计族属其余指标,测试随
指标走;生产 obs 键面锁不经统计脚本,直接断言账本行):
1. 行形态:每轮行都带 'obs' 键(键集恰等、非负 int、内含不变式);
2. 落盘:decisions.jsonl 行内 obs 与内存账本逐位一致。
"""
from __future__ import annotations

import json

import pytest

from sr_od.application.currency_war.kernel.cw_vocab import (
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
             'refresh_trigger', 'cw4_counters',
             # sim71 批观测键:同轮卖→买回实例级投影(逐笔明细 list,
             # 空 list = 本轮无回环;键语义单一源 = engine_p1.
             # project_sell_buyback docstring)
             'sell_buyback_loops'}
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
                           if not isinstance(v, (dict, list))), obs
                # sim71 批键形态:sell_buyback_loops = 逐笔明细 list
                # (空 list = 无回环;明细字段单一源 =
                # project_sell_buyback,形状细锁 = test_cw_obs_keys)
                assert isinstance(obs['sell_buyback_loops'], list), obs
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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
