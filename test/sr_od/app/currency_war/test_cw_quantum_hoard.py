"""量子框架选择/注册主题锁:FRAMEWORKS 注册序 + pick_framework 量子行为面
+ 量子配方注册(量子=第三过渡配方)。

由 test_cw_quantum_recipe 并入本文件(2026-09-09 微件归并批;断言面逐条搬移
零删并,报告 = .debug/temp/cw_test_slim_audit/reports/_cluster_MRG2.md)。
预囤/启动门/滞后面归 test_cw_hoard(同窗合并批落点,原 test_cw_hoard_boot)。
出处:被测模块本体——cw_transition.py 模块头(plaza 784 篇实证;玩法理解
单一源 = docs/game/gameplay/currency_war.md「玩法策略模型」)+ cw_recipe.py
(量子=第三过渡配方统一化,r102 用户定调;设计总览
docs/develop/currency_war/strategy/README.md)。

已并出/迁出面(单一源指针,防重复长回):
- 启动门 1.5 等价面(持有1+在售1)→ test_cw_scenario_gen::
  test_inv_boot_gate_semantics 三框架参数化族;
- 量子早期特判/无关 portal 空板 → test_cw_portal_bias
  (test_early_cards_count_selects_framework / test_portal_unrelated_no_bias);
- decision_target 量子特判分支不立锁(合取面 = deploy_ops 仙舟面 + 本文件
  注册面,生产 cw_recipe.decision_target docstring 承载语义);
- 纯 shop 拒启动/预囤档位分/滞后不翻转/预囤散件 0 分 → test_cw_hoard;
- 阵营兜底口径 → test_cw_faction_fallback。
"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_recipe import recipe_comp
from sr_od.application.currency_war.kernel.cw_transition import (
    FRAMEWORKS,
    pick_framework,
)


class _BC:
    def __init__(self, char_id):
        self.char_id = char_id


# ===== 框架注册与序(pick_framework 计数 dict 序/平局先验的载体) =====

def test_three_frameworks():
    assert FRAMEWORKS == ('仙舟', '列车', '量子'), '三框架注册'


def test_quantum_selected_by_ownership():
    """纯量子持有 → 量子配方(希儿线无特判,靠框架计数)。"""
    fw = pick_framework([_BC(n) for n in ('希儿', '缇宝', '符玄')], [])
    assert fw == '量子'


def test_quantum_portal_bias():
    """量子契约 portal → +3 偏置(空板也选量子)。"""
    assert pick_framework([], [], portal='量子同频契约') == '量子'


def test_xianzhou_beats_quantum_tie():
    """量子2 vs 仙舟2 平局 → 仙舟(dict 序主流先验,r102 审计③)。

    平局先验的载体:pick_framework 计数 dict 由 FRAMEWORKS 序生成,
    max 取首个最大 → 平局归 FRAMEWORKS 首位仙舟(cw_transition 注:
    主流先验 32% vs 29%,有意为之)。FRAMEWORKS 序的单一源锁 =
    本文件 test_three_frameworks(元组序)。"""
    bench = [_BC('希儿'), _BC('缇宝'), _BC('藿藿'), _BC('丹恒·饮月')]
    assert pick_framework(bench, []) == '仙舟'


# ===== 量子配方注册面(r102 统一化:希儿线无特例通道) =====

def test_recipe_quantum_registered():
    rc = recipe_comp('量子')
    assert rc is not None and rc.name == '过渡·量子配方'
    assert rc.form_tiers == {'量子同频': 3, '贝洛伯格': 2}
    assert '希儿' in rc.core_chars
