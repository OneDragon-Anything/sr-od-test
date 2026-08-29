# -*- coding: utf-8 -*-
"""r288 配方底线仲裁测试(局23/24:锁线列车吃板挤仙舟)。"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_line_defs import (
    RECIPE_FACTIONS,
)


def test_recipe_guards_importable() -> None:
    """deploy_bench 消费配方单源(r271)。"""
    from sr_od.application.currency_war.operations.prep import (
        deploy_bench,
    )
    assert deploy_bench._RECIPE is RECIPE_FACTIONS


def test_deploy_tracks_faction_counts() -> None:
    """r288 状态源:_deployed_fac 初始化逻辑(离线可测部分:
    CHARACTERS 查阵营并计数)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    cnt: dict[str, int] = {}
    for name in ('三月七', '姬子·启行', '星期日'):
        ch = CHARACTERS.get(name)
        assert ch is not None, name
        for f in ch.factions or ():
            cnt[f] = cnt.get(f, 0) + 1
    # 局24 r4 实况:三月七+姬子+星期日 = 列车 3 档(挤掉仙舟的元凶)
    assert cnt.get('列车同行') == 3
    assert cnt.get('仙舟', 0) == 0


def test_arbitration_rule_semantics() -> None:
    """仲裁语义:仙舟<3 时列车封顶 2(纯逻辑,无 IO)。"""
    def allow(train_now: int, xz_now: int, card_fac: str) -> bool:
        if card_fac == '列车同行' and train_now >= 2 and xz_now < 3:
            return False
        return True

    # 局24 场景:列车2+仙舟1,第 3 张列车(星期日)→ 拒
    assert not allow(2, 1, '列车同行')
    # 仙舟已 3 → 列车放行(基础线满足,渐进段自由)
    assert allow(2, 3, '列车同行')
    # 列车 <2 → 放行(2 列车是配方渐进段)
    assert allow(1, 0, '列车同行')
    # 非列车件不受此门
    assert allow(2, 1, '仙舟')
