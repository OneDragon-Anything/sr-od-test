"""r106 预囤测试(蒙特卡洛结论的代码级锁)。

本文件自持三面:纯 shop 拒启动(1.0 边界)、预囤模式框架件档位分、
滞后不翻转;启动门「持有1+在售1=1.5 → 启动」等价面由
test_scenario_gen::test_inv_boot_gate_semantics 三框架参数化族承载
(原 test_boot_gate_1p5 与其列车腿同输入同断言,2026-09-09 等价取一删除)。
"""
from sr_od.application.currency_war.kernel.cw_transition import pick_framework, transition_score


class BC:
    def __init__(self, n):
        self.char_id = n


class Card:
    def __init__(self, n):
        self.name = n


def test_boot_pure_shop_still_blocked():
    """纯 shop(1.0)仍不够——防噪声启动。

    与 test_scenario_gen::test_inv_boot_gate_semantics 纯 shop 面(1 张
    carry=0.5)部分重叠双留:本测输入两张 carry 在售=1.0,是生产点名的
    启动门边界(cw_transition.pick_framework docstring「纯 shop 1.0 仍
    不够格防噪声」)——门值降到 ≤1.0 时唯本测红。framework_boot 同输入
    断言已并入此处(README 纪律 8)。"""
    assert pick_framework([], [], [Card('三月七'), Card('姬子·启行')]) == ''


def test_hoard_score_framework_undefined():
    """预囤:framework='' 时框架件仍有档位分(carry 1.0)。"""
    s = transition_score('三月七', '列车同行', '')
    assert s >= 1.0, f'预囤模式 carry 应有档位分,实得 {s}'


# (原 test_hoard_score_scatter_zero 散件 0 分断言已并入
#  test_hoard_no_refresh::test_scatter_ts_zero_hoard(同事实更全:万敌+
#  远坂凛 双载体);滞后不翻转语义单一源 = 本文件 test_hysteresis_unchanged
#  (framework_boot 同断言已并入此处);原 test_boot_gate_1p5 列车启动腿
#  已并入 test_scenario_gen::test_inv_boot_gate_semantics。
#  README 纪律 8:重复构成删并理由。)


def test_hysteresis_unchanged():
    """滞后语义回归:现任列车持有 3,shop 仙舟 2 在售(2.5 vs 3.0)不翻转。

    独家面 = 挑战者框架仅 shop 半权噪声(持有权 0)翻不动现任
    (cw_transition.pick_framework 滞后分支:挑战者持有权领先 ≥1 才换)。"""
    bench = [BC('三月七'), BC('姬子·启行'), BC('姬子·启行')]
    fw = pick_framework(bench, [], [Card('藿藿'), Card('卡芙卡')], current='列车')
    assert fw == '列车'
