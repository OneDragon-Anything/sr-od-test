"""r102 统一化测试:量子=第三过渡配方(希儿线无特例通道)。

出处:被其他测试文件引用(防断链保留,需后续人工归并)(2026-08-31 测试瘦身批考证补记)。"""
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


def test_quantum_not_early_without_cards():
    """早期无量子件 → 不选量子(3费出得晚,计数起不来,自然走仙舟/列车)。"""
    assert pick_framework([], [], portal='彩虹时代') == ''
    assert pick_framework([_BC('藿藿'), _BC('丹恒·饮月')], []) == '仙舟'


def test_recipe_quantum_registered():
    from sr_od.application.currency_war.kernel.cw_recipe import recipe_comp
    rc = recipe_comp('量子')
    assert rc is not None and rc.name == '过渡·量子配方'
    assert rc.form_tiers == {'量子同频': 3, '贝洛伯格': 2}
    assert '希儿' in rc.core_chars


def test_decision_target_no_walkin_branch():
    """decision_target 双轨期只有配方/终局两分支(walkin 已删)。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    from sr_od.application.currency_war.kernel.cw_recipe import decision_target
    from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState

    class _Sess:
        transition_framework = '量子'
        target_comp = next(c for c in COMP_LIBRARY if c.name == '希儿量子')

    st = GameState(round_num=3, plane=1, dual_track_phase=True)
    st.bench = [BenchChar(slot=1, char_id='希儿', faction='?', star=1, position_pref='back')]
    got = decision_target(_Sess(), st)
    assert got.name == '过渡·量子配方', '双轨期量子框架 → 配方伪 comp(不是终局)'
