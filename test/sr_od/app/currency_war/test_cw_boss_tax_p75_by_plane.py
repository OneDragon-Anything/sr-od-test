"""boss 税 p75 位面锚结构残留(boss_tax_p75_by_plane)。

值面已由 test_cw_adr0293_calibration 面册逐值辖死(登记门:
_EXPECTED_FIELDS['boss_tax_p75_by_plane'],增删改键值=红且点名字段)
——本文件原「plane1 零漂移 / plane2 槽位存在」两测同事实,
2026-09-03 瘦身批删除,墓碑锁暂留本文件(Wave2 归并入 adr0293 墓碑组)。
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


def test_boss_tax_scalar_not_resurrected() -> None:
    """无消费者标量不复活锁:boss_tax_p75 已随旧方案清退批删除
    (清查报告 OLD_MIX_AUDIT §1.3);by_plane 是唯一取值口。"""
    names = {f.name for f in fields(DecisionV2Registry)}
    assert 'boss_tax_p75' not in names
    assert not hasattr(DEFAULT_REGISTRY, 'boss_tax_p75')
