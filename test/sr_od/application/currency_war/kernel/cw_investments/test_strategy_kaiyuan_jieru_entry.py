"""开源节流 overlay 条目登记锁(镜像 src = kernel/cw_investments.py 的
STRATEGY_EFFECTS['开源节流'];登记型新锁落拆目录新文件,命名随
test_strategy_*_entry 家族)。

测试面依据 = 迭代设计 designs/T-295-kaiyuan-jieru.md §2.5/§4 锁 6 +
REVIEW-T295 §3.3 裁决点 4(声明性条目加,兼顶满载体宿主):
- payload is STRATEGY_ECONOMY['开源节流'](同一实例单一源,本金充裕
  :969 同构);
- id = '300101'(与数据行 plaza id 双匹配,漂移由 _validate_strategy_
  effects import 即炸承担,本锁只锁显式值供对账);
- 触发/时长/类别形:NODE_ENTER / WHILE_HELD / ECONOMY(条件判定族,
  与存款回报同形);duties 全空(无计数器/无预知/无姿态消费面);
- 注册行帽腿已登记:interest_cap_override = 9(引擎通道选卡即活)+
  instant_gold = 10(选卡金腿缺口族级,登记值零动)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    DurationKind,
    DutyFlags,
    EffectKind,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
)

_CARD = '开源节流'


def test_kaiyuan_entry_payload_same_instance_and_shape() -> None:
    """条目五元组 + payload 同一实例(锁 6):载体宿主已登记是顶满捕获/
    消费的结构性前提(条目缺位 = 载体零落点)。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.payload is STRATEGY_ECONOMY[_CARD], 'payload 引同一实例'
    assert spec.id == '300101'
    assert spec.trigger is TriggerKind.NODE_ENTER
    assert spec.duration is DurationKind.WHILE_HELD
    assert spec.category is EffectKind.ECONOMY
    assert spec.duties == DutyFlags(), 'duties 全空'
    assert spec.pending is False


def test_kaiyuan_registry_row_cap_leg_in_place() -> None:
    """注册行帽腿(锁 6 伴生):interest_cap_override = 9 帽腿引擎通道
    已登记(选卡即活,本批零改动面)+ instant_gold = 10 登记值零动
    (选卡金发放写端缺口 = 族级待办,非本批辖域)。"""
    eff = STRATEGY_ECONOMY[_CARD]
    assert eff.interest_cap_override == 9
    assert eff.instant_gold == 10
