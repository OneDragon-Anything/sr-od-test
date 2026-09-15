"""ScreenArea 字段归一回归(2026-08-29 实证:手编 yml 遗留 ``lcs_percent: null``。

null 绕过构造默认值(默认仅缺参生效)直传 None → 运行时 ``find_by_lcs`` 用它乘
``len(source)`` 抛 ``unsupported operand type(s) for *: 'int' and 'NoneType'``,
单条坏 area 拖垮整个 analyze。修法 = ScreenArea 构造归一 + 数据清洗;本测试锁构造归一。
"""
import pytest

from one_dragon.base.screen.screen_area import ScreenArea


@pytest.mark.parametrize('lcs_percent,expect', [
    (None, 0.5),   # 显式 None 归一为默认 0.5(不崩、不透传)
    (0.7, 0.7),    # 显式合法值保留(归一只针对 None,不改写收紧阈值)
], ids=['none-normalized', 'explicit-kept'])
def test_lcs_percent_normalization_contract(lcs_percent: float | None, expect: float) -> None:
    """构造归一契约两面:显式 None 归一为默认;显式合法值原样保留。"""
    area = ScreenArea(area_name='a', lcs_percent=lcs_percent)
    assert area.lcs_percent == expect
