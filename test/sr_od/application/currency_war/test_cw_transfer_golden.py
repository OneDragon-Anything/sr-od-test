"""T-185 金样锁:单一转移函数逐案对拍平移前 simulate 捕获的容器终态。

金样 fixture 由 `.debug/temp/t185_capture_golden2.py` 生成器产出(平移前
`cw_vocab.simulate` 真值捕获,锚 commit 见 fixture meta);锁体按六键 schema
逐案:restore_state_snapshot 播种一次性容器 → apply_shop_action_logic
(executed=None,理想执行路径)→ 全域 values 与期望快照对拍 + LogicOutcome
applied/reason 对照。分歧语义(双向):转移函数回归或 fixture 过期都红。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopActionExecuted,
    apply_shop_action_logic,
    board_state_of,
    restore_state_snapshot,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BuyCard,
    RefreshShop,
    SellBench,
    SellDeployed,
    SwapDeploy,
)

FIXTURE = Path(__file__).parent / 't185_golden_fixture.json'
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
    if t == 'BuyCard':
        from sr_od.application.currency_war.kernel.cw_game_state import ShopCard
        c = a['card']
        a['card'] = ShopCard(name=c['name'], faction=c['faction'],
                             cost=c['cost'], star=c['star'],
                             cost_source=c.get('cost_source', 'roster'))
        return BuyCard(**a)

    return {'SellBench': SellBench, 'SellDeployed': SellDeployed,
            'SwapDeploy': SwapDeploy, 'RefreshShop': RefreshShop}[t](**a)


@pytest.mark.parametrize('case_name', [
    'buy_place_simple', 'buy_merge3_on_bench', 'buy_fullbench_mergebuy',
    'buy_fullbench_reject', 'sellbench_apply_equips',
    'sellbench_stale_reject', 'selldeployed_apply',
    'selldeployed_stale_reject', 'swapdeploy_apply',
    'swapdeploy_idx_reject',
    'refresh_gold_leg',
])
def test_cw_transfer_golden(case_name: str) -> None:
    fx = json.loads(FIXTURE.read_text(encoding='utf-8'))
    case = next(c for c in fx['cases'] if c['name'] == case_name)
    action = _build_action(dict(case['action']))
    bs = board_state_of(None)
    restore_state_snapshot(bs, case['initial'])
    executed = None
    if case['action']['__type__'] == 'RefreshShop':
        executed = ShopActionExecuted(refresh_paid=int(case['action']['cost']))
    out = apply_shop_action_logic(bs, action, executed=executed,
                                  produced_by='MandateV1Strategy', sig=_SIG)
    got = _norm(bs.full_state_snapshot()['values'])
    exp = _norm(case['expected']['values'])
    diff_keys = sorted(k for k in set(got) | set(exp) if got.get(k) != exp.get(k))
    assert not diff_keys, f'容器终态域分歧: {diff_keys}'
    assert out.applied == case['sim_applied'], (
        f'applied {out.applied} != {case["sim_applied"]}')
    if case['sim_reason']:
        assert out.reason == case['sim_reason']

