"""EquipRelicOp(替换遗器)定位与流程测试(与 test_equip_light_cone 同构)。

测试层级声明:落格投票定位直测(fixture = 实机遗器替换界面截图,部位筛选
已锁头部,死水深潜的先驱头部件在第一行);算法住 grid_template_locate 公共
模块(光锥 op 已锁算法本体,此处锁遗器 4 列网格几何与部件图模板);节点
流程为打桩流程测试(同光锥版,交互链本体生产实机摸底覆盖)。

锁的内容(出处 src/sr_od/operations/equip_relic.py):
- 件名反查:PIECE_TO_SET 表外件名构造期显式失败;表内解析出套装与部位;
- 4 列网格几何:列中心 = 列表区 x1 + 首列偏移 + 间距 × i(实测误差 ≤1px);
- fixture 定位:死水头部部件图命中第一行(两张同套装件,任一列均满足意图)。
"""

from __future__ import annotations

from pathlib import Path

import cv2
import pytest

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils
from sr_od.operations.equip_relic import (
    EquipRelicOp,
    _filter_candidates,
    _relic_col_centers,
)
from sr_od.operations.grid_template_locate import (
    load_template_gray,
    locate_cells_by_votes,
)
from test.conftest import SrTestContext

_FIXTURE_DIR = Path(__file__).parent / 'equip_relic'
_LIST_AREA: Rect = Rect(33, 195, 536, 960)


class _NoWindowEquipRelic(EquipRelicOp):
    """真实构造路径;测试无游戏窗口,跳过窗口前置链(同 test_farm_material)。"""

    def __init__(self, ctx: SrTestContext, piece_name: str) -> None:
        EquipRelicOp.__init__(self, ctx, piece_name=piece_name)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


def test_construction_guard(test_context: SrTestContext) -> None:
    """件名守卫:表外件名构造期显式失败;表内解析出套装与部位。"""
    with pytest.raises(ValueError, match='不在常量表'):
        _NoWindowEquipRelic(test_context, piece_name='不存在的遗器件名')

    op = _NoWindowEquipRelic(test_context, piece_name='先驱的绝热围壳')
    assert op.set_name == '死水深潜的先驱'
    assert op.pos == 1  # 头部


def test_grid_geometry() -> None:
    """4 列网格几何:列中心与实机卡位误差 ≤2px(99/222/345/468;列距 123px
    为亮度剖面实测列中心 99/224/346/469 的标定,旧 110px 标定累计偏 40px
    曾致右侧列角标裁窗全部落空)。"""
    centers = _relic_col_centers(_LIST_AREA)
    assert centers == pytest.approx([99, 222, 345, 468], abs=2)


def test_locate_on_fixture() -> None:
    """实机 fixture 定位(全量清单):第一行两张死水头副本**每件各占一格**——
    同套装多副本全部识别,不丢件(选哪件由调用方基于清单决策)。"""
    template = load_template_gray('assets/game_data/relic_icons/死水深潜的先驱_先驱的绝热围壳.webp')
    assert template is not None

    screen = cv2_utils.read_image(str(_FIXTURE_DIR / 'replace_head_row0.webp'))
    gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
    cells = locate_cells_by_votes(gray, template, _LIST_AREA, _relic_col_centers(_LIST_AREA))
    assert len(cells) >= 2, f'两张同套装副本应各自入清单,实际 {len(cells)} 格'
    col_centers = _relic_col_centers(_LIST_AREA)
    for cell, _votes in cells:
        assert 195 <= cell.y <= 360, f'应落在第一行带,实际 {cell.y}'
        assert any(abs(cell.x - c) <= 12 for c in col_centers), f'应吸附到某列中心,实际 {cell.x}'
    # 两格吸附到不同列(对应两张不同的卡)
    assert cells[0][0].x != cells[1][0].x, '两件副本应位于不同列'


def test_filter_candidates_allow_take_over() -> None:
    """allow_take_over 候选语义(纯函数):False 只取无主件;True 被穿着件入选
    且无主件稳定排前;两模式都排除弹框取消过的格(死循环防线)。"""
    matched = [
        {'cell': [100, 200, 200, 300], 'owner': '停云'},
        {'cell': [250, 200, 350, 300], 'owner': None},
        {'cell': [400, 200, 500, 300], 'owner': '星期日'},
        {'cell': [100, 380, 200, 480], 'owner': None},
    ]
    rob = {(400, 200)}

    # False(默认不抢):只留无主件,被穿着件与弹框格全部出局
    kept = _filter_candidates(matched, allow_take_over=False, rob_cells=rob)
    assert [it['cell'] for it in kept] == [[250, 200, 350, 300], [100, 380, 200, 480]]

    # True(交换语义):被穿着件入选但无主件排前;弹框格仍出局
    kept = _filter_candidates(matched, allow_take_over=True, rob_cells=rob)
    assert [it['owner'] for it in kept] == [None, None, '停云']

    # True 且全部被弹框取消过:候选为空(不无限重试同格)
    assert _filter_candidates(matched, allow_take_over=True,
                              rob_cells={(100, 200), (250, 200), (400, 200), (100, 380)}) == []
