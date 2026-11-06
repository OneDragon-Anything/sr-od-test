"""回收计划+(id 230702)组合登记行+延时表行双注册面锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '回收计划+' 组合行(随机进阶×延时
入队)+ kernel/cw_investments.py STRATEGY_DELAYED_GRANTS '回收计划+' 行
(id 230702/4 节点/类别池简易);按被测方法拆目录规范落位,先例 = 同目录
test_strategy_compose_grant_huishou.py 回收计划)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-238 对应稿
§4 锁面修正版(REVIEW-T238 无需用户决定 5/5;卡面官方原文:「获得1件进阶装备,
并在4个节点后获得1件随机简易装备」;判读申报制随 T-237 在案口径):

- 组合行单一源:两条效果条目组合行已登记(泛化表零本卡键负断言防回退撞键);
- 延时表行直测:id 230702/delay_nodes=4/item_category 简易/item 占位。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_effects import (
    _STRATEGY_RANDOM_EQUIP_GRANTS,
    PICK_INVEST_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_DELAYED_GRANTS,
)

_CARD = '回收计划+'


def test_huishou_plus_compose_row_single_source() -> None:
    """组合行单一源:两条效果条目组合行已登记(随机进阶×延时入队);泛化表零本卡键
    (防回退撞键形态负断言);延时表行直测(id/nodes/类别池)。"""
    assert _CARD in PICK_INVEST_EFFECTS, '组合行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '泛化表零本卡键(撞键形态禁回退)'
    g = STRATEGY_DELAYED_GRANTS[_CARD]
    assert g.id == '230702', 'id 对拍'
    assert g.delay_nodes == 4, '4 节点(卡文直读,姊妹 5 节点差分)'
    assert g.item_category == '简易', '类别池第 2 例'
    assert g.item == '', 'item 占位(类别池形)'
