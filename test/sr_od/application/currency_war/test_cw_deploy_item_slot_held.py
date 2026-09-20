"""部署恒 held 锁(占槽物品防线)。

锁面 = is_item_slot 候选在部署围栏中恒 held、拒因 'item_slot',
先于一切围栏/cap 判定被剔除——防部署装配点把占槽物品当角色上场。
benchchar-retirement 迭代将本防线改 kind 口,本锁为改口前回归网。
(P3 锁载体迁移:select_deployments 随落位决策权归策略迁
mandate_v1/deploy_plan,断言零改。)
"""
from __future__ import annotations

from sr_od.application.currency_war.strategies.impl.mandate_v1.deploy_plan import (
    select_deployments,
)
from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar


def test_item_slot_candidate_held_with_item_slot_reason() -> None:
    """is_item_slot 候选:不上场、进留置、拒因 item_slot。"""
    bench = [BenchChar(slot=1, char_id='甲', star=1),
             BenchChar(slot=2, char_id='', star=1, is_item_slot=True)]
    reasons: dict[int, str] = {}
    up, rest = select_deployments(
        bench, deployed_cids=set(), deployed_fac={}, board={}, cap=10,
        reasons_out=reasons)
    assert 1 not in up, '占槽物品永不进上场集'
    assert 1 in rest, '占槽物品恒留置(常驻占席)'
    assert reasons.get(1) == 'item_slot', \
        f'拒因 = item_slot,实得 {reasons.get(1)!r}'


def test_normal_candidate_not_blocked_by_item_slot_line() -> None:
    """普通候选不受占槽物品防线误伤(防线只剔 is_item_slot 候选)。"""
    bench = [BenchChar(slot=1, char_id='甲', star=1),
             BenchChar(slot=2, char_id='', star=1, is_item_slot=True)]
    reasons: dict[int, str] = {}
    up, rest = select_deployments(
        bench, deployed_cids=set(), deployed_fac={}, board={}, cap=10,
        reasons_out=reasons)
    assert 0 in up, '普通候选照常上场'
    assert reasons.get(0) != 'item_slot', '普通候选不背 item_slot 拒因'
