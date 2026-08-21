"""r126 核心 件豁免息档门测试(单件期望推导的规则编码)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.cw_plan import _compress_release


def test_core_exempt_from_interest_gate():
    """核心件买断恒优(期望等待 22金 >> 息损 1-2金)——豁免息档门。"""
    # 金 41 买 3 费核心(41→38 息档 4→3):散件拒,核心放行
    assert _compress_release(3, 41, set(), is_core=True) is True
    assert _compress_release(3, 41, set(), is_core=False) is False


def test_scatter_keeps_interest_gate():
    """散件照旧保息(金 41 买任何费 → 息档 4→3 降档 → 拒;
    金 42 买 2 费(42→40,档 4 保留)→ 放)。"""
    assert _compress_release(2, 41, set()) is False   # 41→39 档降
    assert _compress_release(3, 41, set()) is False
    assert _compress_release(2, 42, set()) is True    # 42→40 档 4 保留


def test_cheap_core_also_fine():
    """便宜核心件走原门也放(不回归)。"""
    assert _compress_release(2, 41, set(), is_core=True) is True
