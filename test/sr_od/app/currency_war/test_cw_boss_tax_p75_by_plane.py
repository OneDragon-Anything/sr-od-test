"""boss 税 p75 位面锚(boss_tax_p75_by_plane)结构预埋锁。

结构预埋不激活:plane 1 = 现值逐位零漂移;plane 2 槽位存在但默认值
=现值(P2 sim 观测真值只进注释,扰动未评估前不换数)。
锁:plane1 零漂移 / plane2 槽位存在(值=现值 + 注释真值锚)/
旧标量不复活锁。
(原 FLIP 末窗投影臂取数锁已随 ADR-0426 增补 D 删除;C1 投影安全带
消费点锁已随 c1_directed_spend 开关族删除——旧方案清退批,清查报告
OLD_MIX_AUDIT §1.3。无消费者标量 boss_tax_p75 同批删除,by_plane
保留为结构预埋锚(锚组 boss_tax_anchor_group 仍是 sim 标定接口)。)
"""

from dataclasses import fields

from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)

# 当前生效值(P2 换数前两键必须同值)
_CURRENT_VALUE = 34.0
# sim 侧位面观测真值(cw_coarse_battle 标定 manifest hp_events_by_plane:
# P2 boss n=90 均损 −21.63 vs P1 −19.54)——只作注释锚,不做断言值


def test_plane1_value_zero_drift() -> None:
    """plane1 零漂移锁:现值逐位一致。"""
    assert DEFAULT_REGISTRY.boss_tax_p75_by_plane[1] == _CURRENT_VALUE


def test_plane2_slot_exists_same_value() -> None:
    """plane2 槽位存在锁:槽位在、默认值仍=现值(未激活)。"""
    assert set(DEFAULT_REGISTRY.boss_tax_p75_by_plane) == {1, 2}
    assert DEFAULT_REGISTRY.boss_tax_p75_by_plane[2] == _CURRENT_VALUE


def test_boss_tax_scalar_not_resurrected() -> None:
    """无消费者标量不复活锁:boss_tax_p75 已随旧方案清退批删除
    (清查报告 OLD_MIX_AUDIT §1.3);by_plane 是唯一取值口。"""
    names = {f.name for f in fields(DecisionV2Registry)}
    assert 'boss_tax_p75' not in names
    assert not hasattr(DEFAULT_REGISTRY, 'boss_tax_p75')
