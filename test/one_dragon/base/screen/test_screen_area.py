"""ScreenArea 字段归一回归(2026-08-29 实证:手编 yml 遗留 ``lcs_percent: null``。

null 绕过构造默认值(默认仅缺参生效)直传 None → 运行时 ``find_by_lcs`` 用它乘
``len(source)`` 抛 ``unsupported operand type(s) for *: 'int' and 'NoneType'``,
单条坏 area 拖垮整个 analyze。修法 = ScreenArea 构造归一 + 数据清洗;本测试锁构造归一。
"""
from one_dragon.base.screen.screen_area import ScreenArea


def test_lcs_percent_none_normalized() -> None:
    """显式 None 归一为默认 0.5(不崩、不透传)。"""
    area = ScreenArea(area_name='a', lcs_percent=None)
    assert area.lcs_percent == 0.5


def test_lcs_percent_explicit_value_kept() -> None:
    """显式合法值保留(归一只针对 None,不改写 0.7 等收紧阈值)。"""
    area = ScreenArea(area_name='a', lcs_percent=0.7)
    assert area.lcs_percent == 0.7
