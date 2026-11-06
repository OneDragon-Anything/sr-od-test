"""consume_uses_up_to 批量递减 helper 测试(cw_effect_inventory 分目录
镜像;宿主 test_effect_inventory.py 濒行数线,uses 语义新锁落本镜像
目录,沿 T-62 批拆目录先例)。

测试面依据 = 迭代设计 designs/T-188-jiangben-zengxiao.md §2.2-1/§4
(锁 2/锁 6 保守端)+ 八裁决点默认案。语义钉死:
- 种子(锁 2):条目 duration_uses=6 → register_strategy 播种
  remaining_uses=6(uses 维度与 duration 类别独立,免战牌首例机制);
- 返回值 = min(n, 递减前余量);部分免费 = 免余量张、余张照付;
- 归零移除 = 批量扣减后单次移除(条目离场 first() 返 None);
- 保守端 = 未登记/非次数类 → 0 零动作(consume_use 同纪律)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    ActiveEffectInventory,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)

_CARD = '降本增效'
_SPEC_ID = '202301'


def test_register_seeds_six_uses() -> None:
    """锁 2(uses 种子锁):登记降本增效条目 → remaining_uses==6 播种,
    remaining_nodes 保持 None(uses 与 N_NODES 双轨互不污染,免战牌种子
    锁镜像形态)。"""
    inv = ActiveEffectInventory()
    e = inv.register_strategy(STRATEGY_EFFECTS[_CARD], acquired_key=(1, 5))
    assert e.remaining_uses == 6 and e.remaining_nodes is None


def test_consume_uses_up_to_partial_then_exhaust() -> None:
    """按张计真值:uses=6 买 4 → 返 4、余 2;再买 4 → 返 2(免余量张)、
    余 0 归零移除(条目离场);再买 → 返 0 零动作(未登记保守端,
    消费端按全价扣 = uses 耗尽恢复收费)。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS[_CARD], acquired_key=(1, 5))
    assert inv.consume_uses_up_to(_SPEC_ID, 4) == 4, 'min(4, 6) = 4'
    assert inv.first(_SPEC_ID).remaining_uses == 2, '余 2(按张递减)'
    assert inv.consume_uses_up_to(_SPEC_ID, 4) == 2, \
        '部分免费:免余量 2 张(min(4, 2))'
    assert inv.first(_SPEC_ID) is None, '归零移除(用尽 = 效果离场)'
    assert inv.consume_uses_up_to(_SPEC_ID, 4) == 0, '耗尽后返 0 零动作'


def test_consume_uses_up_to_zero_n_no_action() -> None:
    """n<=0 零动作:余量不动、条目不散(扣 0 张 = 无购买覆盖面)。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS[_CARD], acquired_key=(1, 5))
    assert inv.consume_uses_up_to(_SPEC_ID, 0) == 0
    assert inv.first(_SPEC_ID).remaining_uses == 6, '余量不动'


def test_consume_uses_up_to_unregistered_and_non_use_spec() -> None:
    """锁 6 保守端:未登记条目 → 0;非次数类条目(躺平,remaining_nodes
    载体)→ 0 零动作(递减调用点与登记调用点解耦,登记面缺位的局不炸执行
    链,consume_use 同纪律)。"""
    inv = ActiveEffectInventory()
    assert inv.consume_uses_up_to(_SPEC_ID, 3) == 0, '未登记 → 0'
    inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_key=(1, 5))
    assert inv.consume_uses_up_to('102001', 3) == 0, '非次数类 → 0'
    assert inv.first('102001').remaining_nodes == 3, '余期轨道零扰动'
