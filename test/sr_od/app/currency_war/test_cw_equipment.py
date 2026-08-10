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
