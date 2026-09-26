"""部署恒 held 锁(占槽物品防线)。

锁面 = 占位件(kind ∈ tome/bookcard/supply_box)候选在部署围栏中恒
held、拒因 'item_slot',先于一切围栏/cap 判定被剔除——防部署装配点
把占槽物品当角色上场。benchchar-retirement P4:防线改容器槽位 kind
口,锁载体 = 容器占席条目(BenchSlot),断言零改。
(P3 锁载体迁移:select_deployments 随落位决策权归策略迁
mandate_v1/deploy_plan,断言零改。)
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import BenchSlot, Unit
from sr_od.application.currency_war.strategies.impl.mandate_v1.deploy_plan import (
    select_deployments,
)


def _unit_slot(slot: int, char_id: str, star: int = 1) -> BenchSlot:
    """占席单位槽(``slot`` 参数保留签名兼容,位置 = 列表下标)。"""
    return BenchSlot(kind='unit', unit=Unit(char_id=char_id, star=star))


def test_item_slot_candidate_held_with_item_slot_reason() -> None:
    """占位件候选:不上场、进留置、拒因 item_slot。"""
    bench = [_unit_slot(1, '甲'),
             BenchSlot(kind='supply_box', unit=None)]
    reasons: dict[int, str] = {}
    up, rest = select_deployments(
        bench, deployed_cids=set(), deployed_fac={}, board={}, cap=10,
        reasons_out=reasons)
    assert 1 not in up, '占槽物品永不进上场集'
    assert 1 in rest, '占槽物品恒留置(常驻占席)'
    assert reasons.get(1) == 'item_slot', \
        f'拒因 = item_slot,实得 {reasons.get(1)!r}'


def test_normal_candidate_not_blocked_by_item_slot_line() -> None:
    """普通候选不受占槽物品防线误伤(防线只剔占位件候选)。"""
    bench = [_unit_slot(1, '甲'),
             BenchSlot(kind='supply_box', unit=None)]
    reasons: dict[int, str] = {}
    up, rest = select_deployments(
        bench, deployed_cids=set(), deployed_fac={}, board={}, cap=10,
        reasons_out=reasons)
    assert 0 in up, '普通候选照常上场'
    assert reasons.get(0) != 'item_slot', '普通候选不背 item_slot 拒因'
