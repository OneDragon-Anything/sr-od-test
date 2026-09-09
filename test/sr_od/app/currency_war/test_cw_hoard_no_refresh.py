"""r110 回归:预囤期金闲置行为锁(不加专用刷新;散件 ts=0 仍为 0)。

出处:被其他测试文件引用(防断链保留,需后续人工归并)(2026-08-31 测试瘦身批考证补记)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_transition import transition_score


def test_scatter_ts_zero_hoard():
    """预囤模式散件恒 0 分(r106/r107b 语义不变)。"""
    assert transition_score('万敌', '夜之半神', '') == 0.0
    assert transition_score('远坂凛', '?', '') == 0.0
