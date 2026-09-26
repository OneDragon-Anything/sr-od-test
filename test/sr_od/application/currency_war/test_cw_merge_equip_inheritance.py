"""merge 装备继承载体锁。

锁面 = 合并语义的装备继承腿:同名同星 3 合 1,素材装备全部继承到载体
(场上载体优先;bench 载体 = 自己的装备在前、素材装备按扫描序拼接)。
语义源 = merge_mechanics;重写容器形状时本锁为不变量哨兵。

载体 = benchchar-retirement P1 容器原生形状(§2.3:bench = BenchSlot |
None / deployed = Unit | None);语义断言逐位不变(载体迁移,非语义
变更)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_merge_simulate import (
    _merge_bench,
)


def _char(slot: int, star: int, char_id: str = '阿格莱雅',
          equips: list[str] | None = None) -> BenchSlot:
    return BenchSlot(kind='unit', unit=Unit(char_id=char_id, star=star,
                                            equips=list(equips or [])))


def test_bench_merge_inherits_material_equips_to_carrier() -> None:
    """bench 内 3 合 1:素材装备按扫描序继承到载体,素材槽清空。"""
    bench = [_char(1, 1, equips=['a']),
             _char(2, 1, equips=['b']),
             _char(3, 1)]
    _merge_bench(bench, None)
    carrier = bench[0]
    assert carrier is not None and carrier.unit.star == 2, '载体升 2★'
    assert carrier.unit.equips == ['a', 'b'], \
        f'素材装备继承到载体,实得 {carrier.unit.equips}'
    assert bench[1] is None and bench[2] is None, '素材槽清空'


def test_merge_keeps_carrier_own_equips_before_inherited() -> None:
    """载体自有装备保留在前,素材装备追加在后(顺序契约)。"""
    bench = [_char(1, 1, equips=['x']),
             _char(2, 1, equips=['a']),
             _char(3, 1, equips=['b'])]
    _merge_bench(bench, None)
    assert bench[0].unit.equips == ['x', 'a', 'b'], \
        f'自有在前/继承在后,实得 {bench[0].unit.equips}'


def test_deployed_carrier_inherits_bench_material_equips() -> None:
    """载体在场上:bench 素材装备继承到场上载体,素材槽清空、
    载体升星(装备跟人走,不掉落在 bench)。"""
    bench = [_char(1, 1, equips=['a']),
             _char(2, 1, equips=['b'])]
    deployed = [Unit(char_id='阿格莱雅', star=1, equips=['x'])]
    _merge_bench(bench, deployed)
    carrier = deployed[0]
    assert carrier is not None and carrier.star == 2, '场上载体升 2★'
    assert carrier.equips == ['x', 'a', 'b'], \
        f'载体自有 + bench 素材装备,实得 {carrier.equips}'
    assert bench[0] is None and bench[1] is None, 'bench 素材槽清空'
