# -*- coding: utf-8 -*-
"""r387 锁测:配方围栏只在 cap 紧张时拦散牌(富余=填空)。

出处:docs/develop/currency_war/decisions/0251-deploy-fence-cap-roomy.md(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

from sr_od.application.currency_war.operations.prep.deploy_bench import (
    _cap_roomy_of,
)


def test_roomy_vacancy_more_than_must_up() -> None:
    """vacancy 6 > 必上 2(1 target+1 对)→ 富余,散牌放行填空。"""
    assert _cap_roomy_of(front_empty=3, back_empty=3, must_up=2) is True


def testtight_vacancy_le_must_up() -> None:
    """vacancy 2 ≤ 必上 3 → 紧张,配方围栏生效(散牌留 bench)。"""
    assert _cap_roomy_of(front_empty=1, back_empty=1, must_up=3) is False


def test_boundary_equal() -> None:
    """vacancy == must_up → 紧张(恰好够必上件,无富余)。"""
    assert _cap_roomy_of(front_empty=2, back_empty=1, must_up=3) is False
