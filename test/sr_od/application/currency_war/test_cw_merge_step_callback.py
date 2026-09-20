"""_merge_bench 步回调锁(logic-rand-sampling 迭代 3.1;design §2.2 #1)。

锁面 = 采样链逐步写的机械基础:
- on_step 每完成一级合并调用一次(连锁两级 = 2 次);
- 回调时列表已落定该级终态(升星/置 None/装备继承全部生效);
- 缺省 None = 现行为(既有消费者零改动,投影直锁回归)。

合成规则本体 = merge_mechanics(既有投影直锁钉住),本文件不重锁规则,
只锁回调机制。

载体 = benchchar-retirement P1 容器原生形状(§2.3);回调机制断言
逐位不变(载体迁移,非语义变更)。
"""
from __future__ import annotations

from copy import deepcopy

from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_merge_simulate import (
    _merge_bench,
)


def _char(slot: int, star: int, char_id: str = '阿格莱雅') -> BenchSlot:
    return BenchSlot(kind='unit', unit=Unit(char_id=char_id, star=star,
                                            slot=slot))


def _snapshot(bench: list[BenchSlot | None]) -> list[tuple[str, int] | None]:
    """列表值快照(防别名:回调后列表继续被改,快照才留得住每级终态)。"""
    return [None if b is None else (b.unit.char_id, b.unit.star)
            for b in bench]


def test_on_step_fires_once_per_merge_level() -> None:
    """连锁两级(3×1★→2★,再 2★×3→3★)= on_step 恰 2 次。"""
    bench = [_char(1, 1), _char(2, 1), _char(3, 1),
             _char(4, 2), _char(5, 2)]
    steps: list[list[tuple[str, int] | None]] = []
    _merge_bench(bench, None, on_step=lambda: steps.append(_snapshot(bench)))
    assert len(steps) == 2, f'连锁两级 = 回调 2 次,实得 {len(steps)}'
    assert bench and bench[0] is not None and bench[0].unit.star == 3, \
        '终态 = 3★ 载体'


def test_on_step_sees_post_step_state() -> None:
    """回调时列表已落定该级终态:第一级后 3×1★ 已消费(置 None)、
    载体升 2★——调用侧此刻落容器即该级完成后的世界。"""
    bench = [_char(1, 1), _char(2, 1), _char(3, 1)]
    steps: list[list[tuple[str, int] | None]] = []
    _merge_bench(bench, None, on_step=lambda: steps.append(_snapshot(bench)))
    assert len(steps) == 1
    seen = steps[0]
    upgraded = [s for s in seen if s is not None]
    assert upgraded == [('阿格莱雅', 2)], \
        f'回调所见 = 该级终态(载体 2★,素材已置 None),实得 {seen}'


def test_on_step_dual_domain_level_fires_once() -> None:
    """载体在场上的一级合并(bench 素材 + deployed 载体同级变更):
    on_step 恰 1 次,两域列表在回调时均已落定——调用侧按受影响域
    各落一行(design §2.2 #1 写入契约)。"""
    bench = [_char(1, 1)]
    deployed = [Unit(char_id='阿格莱雅', star=1, slot=1),
                Unit(char_id='阿格莱雅', star=1, slot=2)]
    calls: list[tuple[list, list]] = []
    _merge_bench(bench, deployed,
                 on_step=lambda: calls.append((deepcopy(bench),
                                               deepcopy(deployed))))
    assert len(calls) == 1, '一级合并 = 回调 1 次'
    b_snap, d_snap = calls[0]
    assert b_snap[0] is None, 'bench 侧素材已置 None'
    upgraded = [d for d in d_snap if d is not None and d.star == 2]
    assert len(upgraded) == 1, 'deployed 侧载体已升 2★'


def test_on_step_none_default_unchanged() -> None:
    """缺省 None = 现行为:合并照常发生、无回调副作用(既有消费者
    零改动回归腿)。"""
    bench = [_char(1, 1), _char(2, 1), _char(3, 1)]
    _merge_bench(bench, None)
    upgraded = [b for b in bench if b is not None]
    assert len(upgraded) == 1 and upgraded[0].unit.star == 2, '缺省行为不变'
