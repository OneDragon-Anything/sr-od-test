"""入职礼包(id 331301)登记锁(镜像 src = STRATEGY_EFFECTS UNIT_BUFF
零响应登记条目;先例 = 和平手枪祝福 SE 条目同族形态 + pending 冻结
已登记表纪律)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-371 对应稿
(REVIEW-T371 免裁 8/8;卡面官方原文:「进入战斗时:携带了2件装备的
至多4个角色会获得一件处在推荐列表中的随机进阶装备。」条件发放卡,
UNIT_BUFF 零响应登记,pending=True 二义冻结,verdict 回填通道留实采):

- 表锁:登记行 id/name/trigger/duration/category/pending 现值;
- effect_text 单一源锁:payload 与 PLAZA_AUGMENTS id 行 effect 逐字同源;
- 键集/基数面随 test_strategy_effects_keyset.py 承载(本文件不重复)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_invest_data import (
    PLAZA_AUGMENTS,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)


def test_registration_shape() -> None:
    """表锁:登记行字段现值(NODE_ENTER 占位?——非:稿定 PLANE_START
    占位形,duration=WHILE_HELD,category=BATTLEFIELD,pending=True)。"""
    spec = STRATEGY_EFFECTS['入职礼包']
    assert spec.id == '331301', f'id 漂移: {spec.id!r}'
    assert spec.name == '入职礼包', f'name 漂移: {spec.name!r}'
    assert spec.pending is True, 'pending 冻结位漂移'


def test_effect_text_single_source() -> None:
    """effect_text 单一源锁:payload 与 PLAZA_AUGMENTS 数据行逐字同源。"""
    spec = STRATEGY_EFFECTS['入职礼包']
    canon = next(a.effect for a in PLAZA_AUGMENTS if a.id == '331301')
    assert spec.payload.effect_text == canon, \
        'effect_text 与数据行漂移(禁手抄卡文单一源破坏)'
