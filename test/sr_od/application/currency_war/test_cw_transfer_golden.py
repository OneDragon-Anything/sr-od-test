"""T-185 金样锁(v2 转移函数路径唯一锁面;迁移对照到期注记见下)。

原对拍平移前 simulate 捕获的容器终态快照;2026-09-15 严格瘦身:
- 6 案(buy_place_simple / buy_merge3_on_bench / buy_fullbench_mergebuy /
  buy_fullbench_reject / sellbench_stale_reject / refresh_gold_leg)删——
  同场景被 shop_projection M1「活对活等价锁」覆盖(活 simulate 现役,
  覆盖面 ≥ 冻结快照对照);
- 残留 5 案(sellbench_apply_equips / selldeployed_apply /
  selldeployed_stale_reject / swapdeploy_apply / swapdeploy_idx_reject)=
  SellDeployed / SwapDeploy / 装备回收 v2 族 + LogicOutcome 出参契约的
  **唯一锁面**,转正前暂留快照对照。
- **到期条件**:改写为对活 simulate 的等价锁后,删除快照对照半与本
  fixture(生成器指针 .debug/temp/t185_capture_golden2.py 不入 git,
  fixture 视为不可再生的一次性捕获;JSON 内 comptx 两案所属动作类已
  退役,为不可达死数据,随到期一并删)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    apply_shop_action_logic,
    board_state_of,
    restore_state_snapshot,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    SellBench,
    SellDeployed,
    SwapDeploy,
)

FIXTURE = Path(__file__).parent / 't185_golden_fixture.json'
# 贵加载只算一次:92KB 金样文件整读一轮,11→5 案共用(原逐例整读已删)。
_FX = json.loads(FIXTURE.read_text(encoding='utf-8'))
_SIG = ChannelSig(family='logic_action', actor='MandateV1Strategy',
                  mode='compute')


def _norm(v):
    """空态归一化:期望快照经喂入口换算对空域有损(空表不写=None),
    转移函数写真值空态——两者语义等价,归一后比。"""
    if v is None:
        return None
    if isinstance(v, dict):
        if not v:
            return None
        if v.get('cards') == [] and 'refresh_probs' in v:
            return None
        return {k: _norm(x) for k, x in v.items()}
    if isinstance(v, list):
        return None if not v else [_norm(x) for x in v]
    return v


def _build_action(a: dict):
    t = a.pop('__type__')
    return {'SellBench': SellBench, 'SellDeployed': SellDeployed,
            'SwapDeploy': SwapDeploy}[t](**a)


@pytest.mark.parametrize('case_name', [
    'sellbench_apply_equips', 'selldeployed_apply',
    'selldeployed_stale_reject', 'swapdeploy_apply',
    'swapdeploy_idx_reject',
])
def test_cw_transfer_golden(case_name: str) -> None:
    case = next(c for c in _FX['cases'] if c['name'] == case_name)
    action = _build_action(dict(case['action']))
    bs = board_state_of(None)
    restore_state_snapshot(bs, case['initial'])
    out = apply_shop_action_logic(bs, action, executed=None,
                                  produced_by='MandateV1Strategy', sig=_SIG)
    got = _norm(bs.full_state_snapshot()['values'])
    exp = _norm(case['expected']['values'])
    diff_keys = sorted(k for k in set(got) | set(exp) if got.get(k) != exp.get(k))
    assert not diff_keys, f'容器终态域分歧: {diff_keys}'
    assert out.applied == case['sim_applied'], (
        f'applied {out.applied} != {case["sim_applied"]}')
    if case['sim_reason']:
        assert out.reason == case['sim_reason']

