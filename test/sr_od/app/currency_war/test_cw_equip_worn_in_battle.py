"""r393 检查项锁:equip_worn_in_battle 语义(战斗轮 owned 非空连续
2 轮零穿着;开局/无 deployed/全穿不报)。合成账本双向锁。"""
from __future__ import annotations

from sr_od.application.currency_war.sim.checks.ledger import check_equip_worn_in_battle


def _row(rn: int, node: str, owned: list, equipped: list,
         deployed: list | None = None) -> dict:
    dep = deployed if deployed is not None else [{'char_id': 'x'}]
    return {
        'plane': 1, 'round_num': rn,
        'state': {'owned_equips': owned, 'equipped': equipped,
                  'deployed': dep},
        'sim': {'node': node},
    }


def test_persistent_unworn_reported() -> None:
    """战斗轮 owned 有货连续 2 轮零穿着 → 报(r388 过矫指纹)。

    r405(ADR-0265)修订:owned 原用 轮滑鞋(合成保留组件,P1
    现不入「owned 非空」判定)——换非组件名保持原语义。"""
    rows = [_row(5, 'battle', ['蓄能帆'], []),
            _row(6, 'battle', ['蓄能帆'], [])]
    assert check_equip_worn_in_battle(rows)


def test_all_reserved_components_not_reported() -> None:
    """r405(ADR-0265):owned 全是合成保留组件 → equipped 空合法
    (组件待合成,不算白板挨打)。"""
    rows = [_row(5, 'battle', ['轮滑鞋', '光能电池'], []),
            _row(6, 'battle', ['轮滑鞋', '光能电池'], [])]
    assert not check_equip_worn_in_battle(rows)


def test_worn_not_reported() -> None:
    """穿了 → 不报。"""
    rows = [_row(5, 'battle', [], [{'char': 'x', 'equip': '轮滑鞋'}]),
            _row(6, 'battle', [], [])]
    assert not check_equip_worn_in_battle(rows)


def test_opening_not_reported() -> None:
    """r1-r2(开局 hold 语义)不报。"""
    rows = [_row(1, 'battle', ['轮滑鞋'], []),
            _row(2, 'battle', ['轮滑鞋'], [])]
    assert not check_equip_worn_in_battle(rows)


def test_no_deployed_not_reported() -> None:
    """没人上场 → 不报。"""
    rows = [_row(5, 'battle', ['轮滑鞋'], [], deployed=[]),
            _row(6, 'battle', ['轮滑鞋'], [], deployed=[])]
    assert not check_equip_worn_in_battle(rows)
