"""r102 统一化测试:量子=第三过渡配方(希儿线无特例通道)。

出处:被测模块本体;纯持有态单一源被 test_cw_quantum_hoard 引用(防断链保留)
(2026-08-31 测试瘦身批考证补记)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_transition import FRAMEWORKS, pick_framework


class _BC:
    def __init__(self, char_id):
        self.char_id = char_id


def test_three_frameworks():
    assert FRAMEWORKS == ('仙舟', '列车', '量子'), '三框架注册'


def test_quantum_selected_by_ownership():
    """纯量子持有 → 量子配方(希儿线无特判,靠框架计数)。"""
    fw = pick_framework([_BC(n) for n in ('希儿', '缇宝', '符玄')], [])
    assert fw == '量子'


def test_quantum_portal_bias():
    """量子契约 portal → +3 偏置(空板也选量子)。"""
    assert pick_framework([], [], portal='量子同频契约') == '量子'


# test_quantum_not_early_without_cards 已迁出:「彩虹时代 portal 空板返 ''」
# 由 test_cw_portal_bias.py test_portal_unrelated_no_bias 辖定,「早期持有计数
# 选仙舟」迁入同文件 test_early_cards_count_selects_framework,本文件不重复。


def test_recipe_quantum_registered():
    from sr_od.application.currency_war.kernel.cw_recipe import recipe_comp
    rc = recipe_comp('量子')
    assert rc is not None and rc.name == '过渡·量子配方'
    assert rc.form_tiers == {'量子同频': 3, '贝洛伯格': 2}
    assert '希儿' in rc.core_chars


# (test_decision_target_no_walkin_branch 已删:量子双轨返配方 =
#  分支面(test_cw_deploy_ops::test_decision_target_dual_track_returns_recipe,
#  同一生产分支的仙舟面)+ 注册表面(本文件 test_recipe_quantum_registered)
#  的合取——生产 decision_target 对框架无特判分支(统一 _RECIPES.get),
#  量子变体零独立判别力。「双轨期只有配方/终局两分支」语义由生产
#  cw_recipe.decision_target docstring 承载。)
