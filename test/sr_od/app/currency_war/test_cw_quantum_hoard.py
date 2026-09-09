"""量子框架的平局先验锁(量子2 vs 仙舟2 → 仙舟)。

出处:被测模块本体——现行基建锁(量子囤货;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_transition import pick_framework


class BC:
    def __init__(self, n):
        self.char_id = n


def test_xianzhou_beats_quantum_tie():
    """量子2 vs 仙舟2 平局 → 仙舟(dict 序主流先验,r102 审计③)。

    平局先验的载体:pick_framework 计数 dict 由 FRAMEWORKS 序生成,
    max 取首个最大 → 平局归 FRAMEWORKS 首位仙舟(cw_transition 注:
    主流先验 32% vs 29%,有意为之)。FRAMEWORKS 序的单一源锁 =
    test_cw_quantum_recipe::test_three_frameworks(元组序)。
    (原 test_quantum_hoard_boot_boundary 已删:量子 1.5 启动边界与
    test_cw_scenario_gen::test_inv_boot_gate_semantics[量子] 同输入同断言,
    后者超集(兼锁纯 shop 半权不启动),等价取一,单一源 = scenario_gen
    不变量族(三框架参数化)。)"""
    bench = [BC('希儿'), BC('缇宝'), BC('藿藿'), BC('丹恒·饮月')]
    assert pick_framework(bench, []) == '仙舟'
