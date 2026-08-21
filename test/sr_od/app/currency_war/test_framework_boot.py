"""r105 开局死锁修正测试(局29 波次回归)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.cw_transition import pick_framework


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


def test_boot_pure_shop_two():
    """纯在售 2 张(0.5×2=1.0)不够——防纯 shop 噪声启动。"""
    fw = pick_framework([], [], [Card('三月七'), Card('姬子·启行')])
    assert fw == '', '纯在售 1.0 权不应启动(需合并 ≥2)'


def test_match29_r2_would_boot():
    """局29 r2 波重放:三月七在售 + 下一轮 r3 姬子×2 → r3 即启动(旧逻辑 r4 才启动)。"""
    fw3 = pick_framework([BC('三月七')], [], [Card('姬子·启行'), Card('姬子·启行')])
    assert fw3 == '列车', 'r3 持有三月七+在售姬子×2 应启动列车'


def test_hysteresis_survives_shop_noise():
    """滞后仍稳:现任列车(持有3),shop 仙舟 2 张在售 → 不翻转。"""
    bench = [BC('三月七'), BC('姬子·启行'), BC('姬子·启行')]
    fw = pick_framework(bench, [], [Card('藿藿'), Card('卡芙卡')], current='列车')
    assert fw == '列车', 'shop 半权噪声不得翻转现任'


def test_quantum_portal_boot_unchanged():
    """量子 portal 偏置路径回归(修正不改变)。"""
    assert pick_framework([], [], portal='量子同频契约') == '量子'
