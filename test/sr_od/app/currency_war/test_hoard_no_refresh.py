"""r110 回归:预囤期金闲置行为锁(不加专用刷新;散件 ts=0 仍为 0)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.cw_transition import transition_score


def test_scatter_ts_zero_hoard():
    """预囤模式散件恒 0 分(r106/r107b 语义不变)。"""
    assert transition_score('万敌', '夜之半神', '') == 0.0
    assert transition_score('远坂凛', '?', '') == 0.0


def test_framework_defined_scatter_still_buyable_via_gates():
    """框架已定时散件分不来自 transition_score(走 stash/压缩门)——语义锁。"""
    assert transition_score('万敌', '夜之半神', '仙舟') == 0.0
