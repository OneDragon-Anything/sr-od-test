"""r105 开局死锁修正测试(局29 波次回归)。

出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_transition import pick_framework


class BC:
    def __init__(self, n):
        self.char_id = n


class Card:
    def __init__(self, n):
        self.name = n


def test_boot_from_shop_half_weight():
    """r105 核心:持有 1 + 在售 2 = 2.0 ≥ 2 → 框架启动(死锁破)。"""
    fw = pick_framework([BC('三月七')], [], [Card('姬子·启行'), Card('姬子·启行'), Card('万敌')])
    assert fw == '列车', f'1持有+2在售应启动列车,实得 {fw!r}'


# (原 test_boot_pure_shop_two / test_hysteresis_survives_shop_noise /
#  test_quantum_portal_boot_unchanged 已并入同族单一源:
#  纯 shop 拒 + 滞后不翻转 → test_hoard_boot 同输入同断言逐字重复;
#  量子 portal → test_quantum_recipe::test_quantum_portal_bias。
#  重复构成删并理由(README 纪律 8)。)
