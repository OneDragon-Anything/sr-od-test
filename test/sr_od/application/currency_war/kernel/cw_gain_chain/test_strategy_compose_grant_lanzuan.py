"""蓝钻闪耀(id 231301)组合登记行+延时表行双注册面锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '蓝钻闪耀' 组合行(具名蓝钻×延时
入队)+ kernel/cw_investments.py STRATEGY_DELAYED_GRANTS '蓝钻闪耀' 行
(id 231301/3 节点/定名简易武装箱);按被测方法拆目录规范落位,先例 =
同目录 test_strategy_compose_grant_hongzuan.py 红钻闪耀)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-245 对应稿
§4 锁面修正形(REVIEW-T245 免裁 8/8;卡面官方原文:「获得1个【蓝钻】。
进入3个节点后，获得【简易武装箱】」;蓝钻 ∉ 精密金面判据映射 gate 恒
None,获得零级联 ∉ EQUIP_ACQUIRE_CONSEQUENCES):

- 组合行单一源:两条效果条目组合行在册(泛化表零本卡键负断言防回退撞键);
- 延时表行直测:id 231301/delay_nodes=3/item 定名简易武装箱/item_category
  占位(定名道具形,非类别池形)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_effects import (
    _STRATEGY_RANDOM_EQUIP_GRANTS,
    PICK_INVEST_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_DELAYED_GRANTS,
)

_CARD = '蓝钻闪耀'


def test_lanzuan_compose_row_single_source() -> None:
    """组合行单一源:两条效果条目组合行在册(具名×入队组合,红钻同形姊妹);
    泛化表零本卡键(防回退撞键形态负断言);延时表行直测(id/nodes/
    定名道具)。"""
    assert _CARD in PICK_INVEST_EFFECTS, '组合行在册'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '泛化表零本卡键(撞键形态禁回退)'
    g = STRATEGY_DELAYED_GRANTS[_CARD]
    assert g.id == '231301', 'id 对拍'
    assert g.delay_nodes == 3, '3 节点(卡文直读)'
    assert g.item == '简易武装箱', '定名道具直填形'
    assert g.item_category == '', '类别池占位(定名形,非类别池)'
