"""ScreenArea 字段归一回归(2026-08-29 实证:手编 yml 遗留 ``lcs_percent: null``。

null 绕过构造默认值(默认仅缺参生效)直传 None → 运行时 ``find_by_lcs`` 用它乘
``len(source)`` 抛 ``unsupported operand type(s) for *: 'int' and 'NoneType'``,
单条坏 area 拖垮整个 analyze。修法 = ScreenArea 构造归一 + 数据清洗;本测试锁构造归一。

pc_alt 继承契约(2026-11-15 实证:MCP upsert_screen_area 重建区域对象,构造默认
False 覆盖了加载时从画面抄来的 True,锁光标画面点击落空、op 原地循环):
pc_alt 唯一设计面是画面级,区域上的值是运行时副本 —— 加载时抄一份,
挂接(upsert_area)时重抄一份,框架各处只读区域值。
"""
import pytest

from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_info import ScreenInfo


@pytest.mark.parametrize('lcs_percent,expect', [
    (None, 0.5),   # 显式 None 归一为默认 0.5(不崩、不透传)
    (0.7, 0.7),    # 显式合法值保留(归一只针对 None,不改写收紧阈值)
], ids=['none-normalized', 'explicit-kept'])
def test_lcs_percent_normalization_contract(lcs_percent: float | None, expect: float) -> None:
    """构造归一契约两面:显式 None 归一为默认;显式合法值原样保留。"""
    area = ScreenArea(area_name='a', lcs_percent=lcs_percent)
    assert area.lcs_percent == expect


def _screen(name: str, pc_alt: bool) -> ScreenInfo:
    data = {'screen_id': name, 'screen_name': name, 'app_id': '', 'pc_alt': pc_alt,
            'area_list': [{'area_name': 'a', 'pc_rect': [0, 0, 10, 10]}]}
    return ScreenInfo(data)


@pytest.mark.parametrize('screen_pc_alt', [True, False], ids=['locked', 'free'])
def test_loaded_area_inherits_screen_pc_alt(screen_pc_alt: bool) -> None:
    """加载契约:区域上的 pc_alt 固定从画面读取,两面一致。"""
    screen = _screen('画面', screen_pc_alt)
    assert screen.area_list[0].pc_alt is screen_pc_alt


def test_upsert_area_stamps_screen_pc_alt() -> None:
    """挂接契约:外部构造的区域对象(构造默认 False)经 upsert_area 挂进画面,
    必须重抄画面级 pc_alt —— MCP 更新区域后内存副本与画面脱节的回归锁。"""
    screen = _screen('锁光标画面', True)
    incoming = ScreenArea(area_name='背包图标')
    assert incoming.pc_alt is False  # 前置:外部构造默认 False

    screen.upsert_area(incoming)
    assert incoming.pc_alt is True
