"""r106 预囤测试(蒙特卡洛结论的代码级锁)。

出处:被其他测试文件引用(防断链保留,需后续人工归并)(2026-08-31 测试瘦身批考证补记)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_transition import pick_framework, transition_score


class BC:
    def __init__(self, n):
        self.char_id = n


class Card:
    def __init__(self, n):
        self.name = n


def test_boot_gate_1p5():
    """r106 启动门 1.5:持有 1 + 在售 1(1.0+0.5) → 启动。"""
    fw = pick_framework([BC('三月七')], [], [Card('姬子·启行')])
    assert fw == '列车'


def test_boot_pure_shop_still_blocked():
    """纯 shop(1.0)仍不够——防噪声启动(启动门族单一源:framework_boot
    同断言已并入此处)。"""
    assert pick_framework([], [], [Card('三月七'), Card('姬子·启行')]) == ''


def test_hoard_score_framework_undefined():
    """预囤:framework='' 时框架件仍有档位分(carry 1.0)。"""
    s = transition_score('三月七', '列车同行', '')
    assert s >= 1.0, f'预囤模式 carry 应有档位分,实得 {s}'


# (原 test_hoard_score_scatter_zero 散件 0 分断言已并入
#  test_hoard_no_refresh::test_scatter_ts_zero_hoard(同事实更全:万敌+
#  远坂凛 双载体);滞后不翻转语义单一源 = 本文件 test_hysteresis_unchanged
#  (framework_boot 同断言已并入此处)。README 纪律 8:重复构成删并理由。)


def test_hysteresis_unchanged():
    """滞后语义回归:现任列车持有 3,shop 仙舟 2 在售(2.5 vs 3.0)不翻转。"""
    bench = [BC('三月七'), BC('姬子·启行'), BC('姬子·启行')]
    fw = pick_framework(bench, [], [Card('藿藿'), Card('卡芙卡')], current='列车')
    assert fw == '列车'
