"""货币战争 装备(cw_equipment)测试。

- 纯逻辑:Equipment/EQUIPMENTS/get_equip 字段。
- fixture:``read_equipped_below``(穿戴装备 TM)对实机 fixture → icon 固定 ~32px 不随装备数变,
  1/2/3件 + 跨位置(前排/后排)识别一致(D-49)。
"""
from __future__ import annotations

import inspect

import pytest
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import file_utils
from sr_od.application.currency_war.cw_equipment import (
    EQUIPMENTS,
    Equipment,
    get_equip,
    load_equip_tm_grays,
    read_equipped_below,
)
from sr_od.application.currency_war.cw_identity_obs import avatar_to_below
from sr_od.context.sr_context import SrContext
from test.conftest import SrTestContext

_REPO_ROOT = file_utils.find_src_dir(inspect.getfile(SrContext)).parent
_EQUIP_DIR = _REPO_ROOT / 'assets' / 'template' / 'cw_equip'


def test_key_equips_present() -> None:
    """策略相关 key 装备齐:反重力皮靴/以牙还牙甲/冷笑话引擎 等。"""
    for name in ("反重力皮靴", "以牙还牙甲", "冷笑话引擎", "火力风暴潮", "高周波电锯", "光速螺旋桨"):
        assert name in EQUIPMENTS, f"key 装备 {name} 应在注册表"


def test_stacking_flag() -> None:
    """stacking 标志:反重力皮靴/火力风暴潮/冷笑话引擎 可叠加;高周波电锯/以牙还牙甲 不可。"""
    assert get_equip("反重力皮靴").stacking, "反重力皮靴可叠加(鞋修×2)"
    assert get_equip("火力风暴潮").stacking
    assert get_equip("冷笑话引擎").stacking
    assert not get_equip("高周波电锯").stacking
    assert not get_equip("以牙还牙甲").stacking


def test_get_equip_fields() -> None:
    """get_equip 取 Equipment 字段;未知名→None。"""
    e = get_equip("追击星徽")
    assert isinstance(e, Equipment)
    assert e.category == "星徽"
    assert get_equip("不存在装备") is None


# ===== read_equipped_below(穿戴装备 TM)fixture 测试 =====
# icon 固定 ~32px(98px×scale0.33),不随装备数变(D-49);half_w=70 覆盖3件横排跨度。
_GT_FEIXIAO_3 = {'光能电池', '步步生花', '武器大师'}  # 飞霄3件(D-49 CV 验全中)
_GT_FEIXIAO_2 = {'步步生花', '折叠小刀'}  # 飞霄2件(轮滑鞋+生命之花合成步步生花)
_FRONT1 = Rect(677, 329, 810, 467)  # screen_info 前排-1 avatar rect
_BACK1 = Rect(534, 600, 675, 739)   # screen_info 后排-1 avatar rect


@pytest.fixture(scope='module')
def equip_grays():
    """98px TM 模板(全装备);模块内复用。"""
    return load_equip_tm_grays(_EQUIP_DIR)


def test_read_equipped_front_feixiao_3(test_context: SrTestContext, equip_grays) -> None:
    """飞霄前排-1(3件态):read_equipped_below = {光能电池,步步生花,武器大师}。

    D-49 核心:icon 固定 ~32px,3件全中(0.745-0.802@scale0.33),推翻 D-48「3件分辨率墙」。
    half_w=70 覆盖3件横排(cx±43),55 会切边缘 icon(步步生花漏)。
    """
    if not test_context.has_screen('货币战争-备战', 'equipped_front1_feixiao_3'):
        pytest.skip('fixture equipped_front1_feixiao_3 未采')
    screen = test_context.load_screen('货币战争-备战', 'equipped_front1_feixiao_3')
    out = read_equipped_below(screen, equip_grays, [(1, avatar_to_below(_FRONT1))])
    assert set(out.get(1, [])) == _GT_FEIXIAO_3


def test_read_equipped_front_feixiao_2(test_context: SrTestContext, equip_grays) -> None:
    """飞霄前排-1(2件态):read_equipped_below = {步步生花,折叠小刀}。"""
    if not test_context.has_screen('货币战争-备战', 'equipped_front1_feixiao_2'):
        pytest.skip('fixture equipped_front1_feixiao_2 未采')
    screen = test_context.load_screen('货币战争-备战', 'equipped_front1_feixiao_2')
    out = read_equipped_below(screen, equip_grays, [(1, avatar_to_below(_FRONT1))])
    assert set(out.get(1, [])) == _GT_FEIXIAO_2


def test_read_equipped_back_feixiao_2(test_context: SrTestContext, equip_grays) -> None:
    """飞霄后排-1(2件态,从前排拖来):read_equipped_below = {步步生花,折叠小刀}(跨位置一致)。

    验证穿戴装备 icon 随角色位置移动,识别跨前排/后排一致(用户核心需求:不同位置识别一致)。
    """
    if not test_context.has_screen('货币战争-备战', 'equipped_back1_feixiao_2'):
        pytest.skip('fixture equipped_back1_feixiao_2 未采')
    screen = test_context.load_screen('货币战争-备战', 'equipped_back1_feixiao_2')
    out = read_equipped_below(screen, equip_grays, [(1, avatar_to_below(_BACK1))])
    assert set(out.get(1, [])) == _GT_FEIXIAO_2


@pytest.mark.parametrize('fixture, rect', [
    ('equipped_back1_feixiao_3', _BACK1),                       # 后排-1 cx604
    ('equipped_back4_feixiao_3', Rect(967, 600, 1097, 739)),     # 后排-4 cx1032(跨度证)
])
def test_read_equipped_back_feixiao_3(test_context: SrTestContext, equip_grays, fixture, rect) -> None:
    """飞霄后排(3件,drag 换位):read_equipped_below = {光能电池,步步生花,武器大师}。

    参数化后排-1(cx604)+ 后排-4(cx1032):证 half_w 后排跨 cx 通用 + dy=14 跨排通用(D-49)。
    CW 备战屏支持 drag 角色换位(前排↔后排、后排内),装备跟随角色。
    """
    if not test_context.has_screen('货币战争-备战', fixture):
        pytest.skip(f'fixture {fixture} 未采')
    screen = test_context.load_screen('货币战争-备战', fixture)
    out = read_equipped_below(screen, equip_grays, [(1, avatar_to_below(rect))])
    assert set(out.get(1, [])) == _GT_FEIXIAO_3


def test_read_equipped_front_feixiao_1(test_context: SrTestContext, equip_grays) -> None:
    """飞霄前排-1(1件态,步步生花):read_equipped_below = {步步生花}。

    1件 icon 居中(cx);验证 1/2/3件 icon 固定 ~32px,识别一致(D-49)。
    """
    if not test_context.has_screen('货币战争-备战', 'equipped_front1_feixiao_1'):
        pytest.skip('fixture equipped_front1_feixiao_1 未采')
    screen = test_context.load_screen('货币战争-备战', 'equipped_front1_feixiao_1')
    out = read_equipped_below(screen, equip_grays, [(1, avatar_to_below(_FRONT1))])
    assert set(out.get(1, [])) == {'步步生花'}


def test_read_equipped_front_feixiao_0(test_context: SrTestContext, equip_grays) -> None:
    """飞霄前排-1(0件/裸装):read_equipped_below = 空(无假阳性)。

    验证空装备槽 below-avatar 无 icon → 不误识别(防 VLM 误判空槽有装备;D-38/D-45 教训:以 CV 为准)。
    """
    if not test_context.has_screen('货币战争-备战', 'equipped_front1_feixiao_0'):
        pytest.skip('fixture equipped_front1_feixiao_0 未采')
    screen = test_context.load_screen('货币战争-备战', 'equipped_front1_feixiao_0')
    out = read_equipped_below(screen, equip_grays, [(1, avatar_to_below(_FRONT1))])
    assert out.get(1, []) == []  # 裸装:无装备 icon,不误识别


# ===== 各位置通用性(D-49:cx 各异的 below 区都准;空位置无假阳性)=====
# 备战 1-6 全位置 fixture(前排4 + 后排6 + 备战5)
_SLOTS_ALL = [
    ('前排-1', 1, Rect(677, 329, 810, 467)),
    ('前排-2', 2, Rect(823, 329, 951, 467)),
    ('前排-3', 3, Rect(969, 329, 1097, 467)),
    ('前排-4', 4, Rect(1109, 329, 1241, 467)),
    ('后排-1', 5, Rect(534, 600, 675, 739)),
    ('后排-2', 6, Rect(679, 600, 814, 739)),
    ('后排-3', 7, Rect(823, 600, 953, 739)),
    ('后排-4', 8, Rect(967, 600, 1097, 739)),
    ('后排-5', 9, Rect(1106, 600, 1241, 739)),
    ('后排-6', 10, Rect(1245, 600, 1386, 739)),
    ('备战栏-1', 11, Rect(382, 845, 495, 979)),
    ('备战栏-2', 12, Rect(507, 844, 620, 978)),
    ('备战栏-3', 13, Rect(632, 844, 743, 978)),
    ('备战栏-4', 14, Rect(757, 845, 869, 979)),
    ('备战栏-5', 15, Rect(882, 846, 995, 980)),
]


def test_read_equipped_front_all_positions(test_context: SrTestContext, equip_grays) -> None:
    """前排1-4 各位置(cx 743/887/1033/1175 各异):avatar_to_below half_w 横向通用。

    备战1-6 fixture:前排-1(3件 光能电池+步步生花+武器大师)/前排-2(空)/前排-3(减益星徽)/前排-4(治疗星徽)。
    验证不同 cx 的 below 区都覆盖 icon(D-49:icon 固定 32px,half_w=70 覆盖3件横排)。
    """
    if not test_context.has_screen('货币战争-备战', 'prep_1-6_all_positions'):
        pytest.skip('fixture prep_1-6_all_positions 未采')
    screen = test_context.load_screen('货币战争-备战', 'prep_1-6_all_positions')
    below = [(idx, avatar_to_below(r)) for _, idx, r in _SLOTS_ALL[:4]]
    out = read_equipped_below(screen, equip_grays, below)
    assert set(out.get(1, [])) == _GT_FEIXIAO_3
    assert out.get(2, []) == []
    assert set(out.get(3, [])) == {'减益星徽'}
    assert set(out.get(4, [])) == {'治疗星徽'}


def test_read_equipped_no_false_positive_empty_positions(test_context: SrTestContext, equip_grays) -> None:
    """后排(空占位)+ 备战栏(未上阵角色,无 below icon):无假阳性。

    CW 机制:装备只显示在舞台已 deploy 角色脚下;备战栏角色不显示装备 icon(pi 确认)。
    故后排(当前无角色)+ 备战栏(5角色无icon)read_equipped_below 全空,不误识别。
    """
    if not test_context.has_screen('货币战争-备战', 'prep_1-6_all_positions'):
        pytest.skip('fixture prep_1-6_all_positions 未采')
    screen = test_context.load_screen('货币战争-备战', 'prep_1-6_all_positions')
    below = [(idx, avatar_to_below(r)) for _, idx, r in _SLOTS_ALL[4:]]  # 后排6 + 备战5
    out = read_equipped_below(screen, equip_grays, below)
    assert not out, f"空位置应无假阳性,实际命中 {out}"
