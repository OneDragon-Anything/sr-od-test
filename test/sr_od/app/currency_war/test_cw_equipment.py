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


def test_read_equipped_back_multi_positions(test_context: SrTestContext, equip_grays) -> None:
    """后排多 cx(2/3/5)多件数(3/1/1):avatar_to_below 后排各 cx 通用(一张图多角色)。

    drag 多前排角色到后排同图:后排-2(cx747 飞霄3件)/后排-3(cx888 减益星徽)/后排-5(cx1174 治疗星徽)。
    与 test_read_equipped_back_feixiao_3(后排-1/4)合证后排 1-5 各 cx 通用(D-49)。
    """
    if not test_context.has_screen('货币战争-备战', 'equipped_back_235'):
        pytest.skip('fixture equipped_back_235 未采')
    screen = test_context.load_screen('货币战争-备战', 'equipped_back_235')
    below = [
        (2, avatar_to_below(Rect(679, 600, 814, 739))),   # 后排-2 cx747
        (3, avatar_to_below(Rect(823, 600, 953, 739))),   # 后排-3 cx888
        (5, avatar_to_below(Rect(1106, 600, 1241, 739))),  # 后排-5 cx1174
    ]
    out = read_equipped_below(screen, equip_grays, below)
    assert set(out.get(2, [])) == _GT_FEIXIAO_3
    assert set(out.get(3, [])) == {'减益星徽'}
    assert set(out.get(5, [])) == {'治疗星徽'}


def test_read_equipped_back6_feixiao_3(test_context: SrTestContext, equip_grays) -> None:
    """后排-6(cx1316 最右)飞霄3件:read_equipped_below = {光能电池,步步生花,武器大师}。

    D-51(已修):icon 尺寸随位置变(梯形视角:前排~32px/后排最右~34px)。武器大师后排-6 best scale=0.35
    val0.601,step 0.03 漏 0.35(0.36=0.481)致漏检;scales 加 0.35 后全中。非裁切/遮挡(pi+用户确认无遮挡)。
    """
    if not test_context.has_screen('货币战争-备战', 'equipped_back6_feixiao_3'):
        pytest.skip('fixture equipped_back6_feixiao_3 未采')
    screen = test_context.load_screen('货币战争-备战', 'equipped_back6_feixiao_3')
    out = read_equipped_below(screen, equip_grays, [(6, avatar_to_below(Rect(1245, 600, 1386, 739)))])
    assert set(out.get(6, [])) == _GT_FEIXIAO_3


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


def test_below_icon_diff_detects_equip(test_context: SrTestContext) -> None:
    """equip_all CV-diff 验穿(D-56):飞霄 0→1→2→3 件连续态 below-icon diff >> 阈值,同态 ~0。

    ``equip_all._below_icon_diff``(R19 avatar-slot CV-diff,替 count-verify)验 drag 是否落地穿。
    fixture ``equipped_front1_feixiao_0/1/2/3``(front-1 飞霄 0→3 件顺序态):加 icon 的连续态
    diff 应远 > ``BELOW_DIFF_THRESHOLD``(8.0),同态 ~0。offline 验证验穿逻辑可靠(剩 live drag 待游戏条件)。
    """
    from sr_od.application.currency_war.operations.prep.equip_all import (
        EquipAll,
        _below_icon_diff,
    )
    if not test_context.has_screen('货币战争-备战', 'equipped_front1_feixiao_0'):
        pytest.skip('fixture equipped_front1_feixiao_0/1/2/3 未采')
    states = [test_context.load_screen('货币战争-备战', f'equipped_front1_feixiao_{i}') for i in range(4)]
    avatar_x = EquipAll.FRONT_AVATARS[0].x           # front-1 avatar x=743
    thr = EquipAll.BELOW_DIFF_THRESHOLD              # 8.0
    for i in range(3):                                # 连续态(加 icon)→ diff >> 阈值
        d = _below_icon_diff(states[i], states[i + 1], avatar_x,
                             EquipAll.BELOW_ICON_Y, EquipAll.BX_HALF, EquipAll.BY_HALF)
        assert d > thr, f'{i}→{i + 1} 加 icon 应 diff > {thr},实际 {d:.1f}'
    # 同态 → ~0(无变化)
    assert _below_icon_diff(states[0], states[0], avatar_x,
                            EquipAll.BELOW_ICON_Y, EquipAll.BX_HALF, EquipAll.BY_HALF) < thr


def test_empty_slots_skips_occupied() -> None:
    """equip_all P0-2 占位检测(``_empty_slots``):已穿槽跳过,只返空槽(1-based)。

    ``read_row_equipped`` 返 ``{slot_idx: [装备名]}``(1-based);槽不在 dict = 空。
    全空 → 全槽;部分已穿 → 跳过;全已穿 → 空(op 应停)。
    修原 bug:``target=FRONT_AVATARS[equipped]`` 按已穿计数索引 → 已穿槽被覆盖。
    """
    from sr_od.application.currency_war.operations.prep.equip_all import _empty_slots
    assert _empty_slots({}, 4) == [1, 2, 3, 4]                            # 全空 → 全槽
    assert _empty_slots({1: ['x']}, 4) == [2, 3, 4]                       # slot1 已穿 → 跳过
    assert _empty_slots({1: ['x'], 3: ['y']}, 4) == [2, 4]                # 多个已穿 → 跳过对应
    assert _empty_slots({1: ['x'], 2: ['y'], 3: ['z'], 4: ['w']}, 4) == []  # 全已穿 → 空(停)


def test_select_layout_no_complete_returns_empty() -> None:
    """D-61: 无完整1/2/3件布局(单件落非合法候选)→ 返 [](不返 fallback 候选,防空槽误匹配)。

    完美投影仪 val0.62 单件落 +21 候选(2件布局右位,缺 -21)= 无完整布局 → 误检,返空。
    修前返 fallback ``[完美投影仪]``(D-61 实测 front_equips 假阳);修后返 ``[]``。
    另验合法 1件{0} 仍返该件(修不破坏合法路径)。
    """
    import numpy as np
    from sr_od.application.currency_war.cw_equipment import _select_equipped_layout
    dummy = np.zeros((100, 200, 3), dtype=np.uint8)
    rect = Rect(0, 0, 200, 100)
    cx = 100
    # 单件落 +21(非合法 1件{0}/2件{±21}完整)→ 无完整布局 → 返 [](D-61 修)
    assert _select_equipped_layout([('完美投影仪', 0.62, cx + 21)], cx, 2, dummy, rect) == []
    # 合法 1件落 0 → 返 [该件](修不破坏合法路径)
    assert _select_equipped_layout([('和平手枪', 0.80, cx)], cx, 1, dummy, rect) == ['和平手枪']


def test_prioritize_wearable_comp_driven() -> None:
    """equip_all comp 驱动穿戴(ADR-0101):``_prioritize_wearable`` 按 target_comp.key_equips 优先,
    替 naive ``wearable[0]``(read_equips 返回第一个)。无 target / 无 key_equips → 原序(等价旧行为)。
    key_equips 含重复(阿雅需 2 反重力皮靴)→ 按 multiplicity 消费(命中的重复件也优先,但不超额)。
    """
    from sr_od.application.currency_war.operations.prep.equip_all import _prioritize_wearable
    # wearable = [(name, (cx, cy)), ...](read_equips 命中顺序)
    w = [('光速螺旋桨', (1800, 900)), ('反重力皮靴', (1850, 900)), ('火力风暴潮', (1700, 900))]
    # 无 target / 无 key_equips → 原序(等价旧行为)
    assert _prioritize_wearable(w, None) == w
    assert _prioritize_wearable(w, []) == w
    # target key_equips = [反重力皮靴×2](阿雅)→ 命中件优先在前
    out = _prioritize_wearable(w, ['反重力皮靴', '反重力皮靴'])
    names = [n for n, _ in out]
    assert names[0] == '反重力皮靴', 'key_equip 件应排第一'
    assert set(names[1:]) == {'光速螺旋桨', '火力风暴潮'}, '其余件在后'
    # 无命中 → 原序
    assert _prioritize_wearable(w, ['以牙还牙甲']) == w
    # multiplicity:key_equips 2 反重力皮靴,wearable 也有 2 → 都优先(前 2 位)
    w2 = [('光速螺旋桨', (1, 1)), ('反重力皮靴', (2, 2)), ('火力风暴潮', (3, 3)), ('反重力皮靴', (4, 4))]
    out2 = _prioritize_wearable(w2, ['反重力皮靴', '反重力皮靴'])
    assert [n for n, _ in out2][:2] == ['反重力皮靴', '反重力皮靴'], '重复 key_equip 按 multiplicity 都优先'
    # multiplicity 不超额:key_equips 1 反重力皮靴,wearable 2 → 只消费 1(第二个回原序)
    out3 = _prioritize_wearable(w2, ['反重力皮靴'])
    names3 = [n for n, _ in out3]
    assert names3[0] == '反重力皮靴', '1 multiplicity → 第一个优先'
    assert names3[1] != '反重力皮靴', '第二个不超额优先(回原序)'
    assert names3[-1] == '反重力皮靴'  # 第二个落回 rest(原 wearable 顺序)
