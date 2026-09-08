"""test_cw_data_registry 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- chars: test_cw_chars.py
- enemy_data: test_cw_enemy_data.py
- equipment: test_cw_equipment.py
- core_count_for: test_cw_core_count_for.py
- tome_template: test_cw_tome_template.py
- back_layout: test_cw_back_layout.py
- test_star3_positions: test_star3_positions.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
(瘦身批 F12:原 7 文件拼接疤痕——4 套仓根常量/3 处 sys.path.insert/
5 个 pytest 别名/3 个 Rect 别名——收敛为本头部一套;手工 path 注入已由
主仓 pyproject `[tool.pytest.ini_options] pythonpath = ["src"]` 取代。)
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils
from sr_od.application.currency_war.data.cw_chars import (
    CHARACTER_ROSTER,
    CHARACTERS,
    Character,
    chars_by_cost,
    chars_by_faction,
    get_char,
)
from sr_od.application.currency_war.data.cw_factions import FACTIONS
from test.conftest import SrTestContext

_REPO_ROOT = Path(__file__).resolve().parents[5]   # 仓库根(StarRailOneDragon)
_TEST_ROOT = Path(__file__).resolve().parents[4]   # 测试仓根(sr-od-test)
FIXTURES = _TEST_ROOT / 'screens' / '货币战争-备战'  # 备战屏 fixture 目录(原 _SCREEN_DIR/FIXTURES 两套合一)

# ==================== chars ====================
def test_registry_complete_all_costs() -> None:
    """注册表覆盖全费用 1-5;每条费用非空。"""
    for cost in range(1, 6):
        assert len(chars_by_cost(cost)) > 0, f"{cost}费应有角色"
    # 总数合理(V4.4 ~70+,开拓者按命途合并性别)
    assert len(CHARACTERS) > 60


def test_roster_derived_from_registry() -> None:
    """CHARACTER_ROSTER 是从 CHARACTERS 派生的规范名集合(单一真相源)。"""
    assert frozenset(CHARACTERS.keys()) == CHARACTER_ROSTER


def test_canonical_names_no_nicknames() -> None:
    """规范名集合禁粉丝缩写:Archer 在,红A 不在。"""
    assert "Archer" in CHARACTER_ROSTER
    assert "红A" not in CHARACTER_ROSTER
    assert "瓦尔特" in CHARACTER_ROSTER
    assert "杨叔" not in CHARACTER_ROSTER


def test_get_char_fields() -> None:
    """get_char 取 Character 字段:Archer 5费/前台/命运圣杯/战技点/独立魔术师。"""
    archer = get_char("Archer")
    assert archer is not None
    assert archer.cost == 5
    assert archer.position == "front"
    assert "命运圣杯" in archer.factions
    assert "战技点" in archer.flows
    assert archer.independent == "魔术师"
    assert get_char("不存在角色") is None, "未知名 → None"


def test_position_pref() -> None:
    """Character.position_pref:前台→front、后台→back、前后台(flex)→back。"""
    assert get_char("流萤").position_pref() == "front"      # 前台
    assert get_char("三月七").position_pref() == "back"     # 后台
    assert get_char("远坂凛").position_pref() == "back"     # 前后台→back 默认


def test_chars_by_faction() -> None:
    """chars_by_faction:仙舟含青雀;含流派(燃血含刃)。"""
    仙舟 = [c.name for c in chars_by_faction("仙舟")]
    assert "青雀" in 仙舟
    燃血 = [c.name for c in chars_by_faction("燃血")]
    assert "刃" in 燃血
    assert "万敌" in 燃血


def test_chars_by_cost_count() -> None:
    """费用分布(2026-08-15 勘误后):娜塔莎 1→3、爻光 2→1、罗刹 5→4(广场 config rarity+bwiki 双源)。

    旧断言 3费=13 来自 D牌期望表 77124902 实测点 v=13 —— 该实测点统计口径含娜塔莎错录 1 费,
    勘误后 3费=14。D牌期望表若重校,按新分布回归。
    """
    assert len(chars_by_cost(3)) == 14
    assert len(chars_by_cost(1)) == 20   # 19 + 停云(plaza 补录,专家顾问)
    assert len(chars_by_cost(5)) == 9    # 10 - 罗刹(5→4)
    # 勘误个体(广场 config rarity 权威值)
    assert CHARACTERS["娜塔莎"].cost == 3
    assert CHARACTERS["爻光"].cost == 1
    assert CHARACTERS["罗刹"].cost == 4
    # 停云补录(plaza id=1202,1费后台,仙舟+能量)
    assert CHARACTERS["停云"].cost == 1
    assert CHARACTERS["停云"].position == "back"
    assert "仙舟" in CHARACTERS["停云"].factions


def test_faction_members_cross_module() -> None:
    """FactionInfo.members() 跨模块从 CHARACTERS 反查(派生关系,非硬编码)。"""
    仙舟_info = FACTIONS["仙舟"]
    members = 仙舟_info.members()
    assert "青雀" in members
    assert len(members) > 0


def test_character_is_frozen() -> None:
    """Character 是 frozen dataclass(注册表条目不可变,防误改)。"""
    c = get_char("青雀")
    assert isinstance(c, Character)
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.cost = 9   # frozen → FrozenInstanceError


# ---- plaza 官方接口对拍守卫 ----
# plaza 数据层 cw_chars_data.py 已删(2026-09 治理审计:零消费,生成器改对拍器);
# 本守卫把「注册表 vs 官方接口」的对拍从纯口头升级为接线测试:抽查条目冻结自 plaza
# config API V4.4(与 tools/cw/gen_plaza_chars.py 数据源同源),全量遍历 8 条比
# cost/position/traits。全量对拍跑 `uv run python tools/cw/gen_plaza_chars.py`。
_PLAZA_SAMPLE_POOL = (  # (plaza_id, 规范名, cost, 站位, traits);站位/费用=官方字段值
    ("1001", "三月七", 1, "Back", ("列车同行", "护盾")),
    ("1014", "Saber", 3, "Common", ("命运圣杯", "能量")),
    ("1202", "停云", 1, "Back", ("仙舟", "能量")),
    ("1304", "砂金", 2, "Front", ("公司", "追击", "护盾")),
    ("1408", "白厄", 3, "Front", ("救世主",)),
    ("1501", "火花", 4, "Front", ("星间旅人", "战技点", "欢愉")),
    ("15061", "银狼LV.999", 3, "Front", ("星核猎手", "欢愉", "头号玩家")),
    ("8009", "开拓者·欢愉", 4, "Back", ("列车同行", "能量", "欢愉")),
)
_PLAZA_POSITION = {"Front": "front", "Back": "back", "Common": "flex"}


def test_plaza_official_snapshot_guard() -> None:
    """全量遍历 8 条 plaza 冻结条目,断言 cost/position/traits 与 CHARACTERS 一致
    (条目池小且纯内存比对,采样无收益只留盲区——瘦身批 F6 由固定种子抽 5 改全量)。"""
    for pid, name, cost, pos, traits in _PLAZA_SAMPLE_POOL:
        ch = CHARACTERS[name]
        assert ch.cost == cost, f"{pid} {name}: cost {ch.cost} != plaza {cost}"
        assert ch.position == _PLAZA_POSITION[pos], f"{pid} {name}: position {ch.position} != plaza {pos}"
        reg_traits = set(ch.factions) | set(ch.flows) | ({ch.independent} if ch.independent else set())
        assert reg_traits == set(traits), f"{pid} {name}: traits {sorted(reg_traits)} != plaza {sorted(traits)}"


# ==================== enemy_data ====================


from sr_od.application.currency_war.data.cw_enemy_data import (
    boss_tags,
    matchup,
    normalize_boss_name,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    boss_fit,
    get_comp,
)


def test_nickname_normalization():
    assert normalize_boss_name('剧目') == '造梦兄弟影业'
    assert normalize_boss_name('蕉研组') == '造梦互动娱乐'
    assert normalize_boss_name('造梦兄弟影业') == '造梦兄弟影业'   # 已规范原样
    assert normalize_boss_name('火线动力机甲') == '火线动力机甲'


def test_boss_fit_seam_now_hits():
    """接缝接通实证:希儿量子 countered=[剧目,蕉研组] vs plane_bosses 含 造梦兄弟影业 → 命中降分
    (旧:俗称 vs 规范名永命中不了,task#73 遗留)。非命中 boss → 真实中性 0.5 的
    同分支同值锁在 test_cw_comps.py test_boss_fit_aya_tv,不在此双锁(瘦身批 F9)。"""
    seele = get_comp('希儿量子')
    hit = boss_fit(seele, ['造梦兄弟影业', '铁盾安保集团', '猎星资本'])
    assert hit is not None and hit < 0.5


def test_matchup_structure_layer():
    """结构层:治疗队打 削治疗 boss(火线动力机甲)→ 克制降分 + reasons 可解释;
    群攻队打召唤 boss(银甲)→ 利好升分。"""
    s1, r1 = matchup(['治疗', '治疗护盾'], ['火线动力机甲'])
    assert s1 < 0.5 and any('克' in x for x in r1)
    s2, r2 = matchup(['群攻'], ['银甲武装公司'])
    assert s2 > 0.5 and any('利' in x for x in r2)
    s3, r3 = matchup([], [])
    assert s3 == 0.5 and r3 == []


def test_boss_fit_mechanics_fallback():
    """无 countered_by_bosses 但有 mechanic_attributes 的 comp → 结构层兜底
    (20 boss 里 16 个无 countered 数据的 comp 不再恒 None)。"""
    comp = next(c for c in COMP_LIBRARY
                if not c.countered_by_bosses and c.mechanic_attributes)
    v = boss_fit(comp, ['火线动力机甲'])
    assert v is not None and 0.0 <= v <= 1.0


def test_boss_tags_roundtrip():
    canon, tags = boss_tags(['剧目', '电视机'])
    assert '造梦兄弟影业' in canon
    assert 'share_hp' in tags          # 剧目 → 共享血量
    assert 'speed_lock' not in tags    # 电视机已定位造梦互动娱乐(2026-08-17),tag 挂钩退役


# ==================== equipment ====================

from sr_od.application.currency_war.obs.cw_equipment import (  # noqa: E402
    EQUIPMENTS,
    Equipment,
    _owned_order_anomaly,
    get_equip,
    load_equip_tm_grays,
    read_equipped_below,
)
from sr_od.application.currency_war.obs.cw_identity_obs import (  # noqa: E402
    avatar_to_below,
)

_EQUIP_DIR = _REPO_ROOT / 'assets' / 'template' / 'currency_war' / 'equip_legacy'


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


# ===== owned 栏行内跳格检测(2026-08-18 治本:换行误报修复) =====

def test_owned_order_row_wrap_not_anomaly() -> None:
    """换行跳变 ≠ 跳格(live 2026-08-18 10:45/10:47 实锤回归):row1 两件 +
    row2 两件,行尾→行首 x 大跳(220 vs 行内 78)是正常布局 —— 旧欧氏全局中位
    每逢跨行必误报;新行内判定放行。"""
    # live 10:47 实测坐标形态:row1(冶金炉 1785,163 / 拆装扳手 1836,172),
    # row2 两件(cy ~260+,x 1836/1785 同列)
    pts = [(1785, 163), (1836, 172), (1836, 261), (1785, 268)]
    assert _owned_order_anomaly(pts) is None


def test_owned_order_real_gap_in_row_detected() -> None:
    """行内真跳格检出:同行 4 个 x,中段空一格(51×2=102 > 1.8×51)→ 报。"""
    xs = (1836, 1785, 1734, 1632)   # 第三→第四间距 102,中位 51
    pts = [(x, 170) for x in xs]
    anomaly = _owned_order_anomaly(pts)
    assert anomaly is not None and '跳格' in anomaly


def test_owned_order_too_few_or_dense_none() -> None:
    """<4 点不判;单行 2 点不判(首行独立布局常见);满行连续 → None。"""
    assert _owned_order_anomaly([(1, 1), (2, 2), (3, 3)]) is None
    assert _owned_order_anomaly([(1785, 163), (1836, 172)]) is None
    dense = [(1836, 170), (1785, 172), (1734, 169), (1683, 171)]   # 连续无跳
    assert _owned_order_anomaly(dense) is None
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
    from sr_od.application.currency_war.operations.cw_op.cw_op_equip_all import (
        CwOpEquipAll,
        _below_icon_diff,
    )
    if not test_context.has_screen('货币战争-备战', 'equipped_front1_feixiao_0'):
        pytest.skip('fixture equipped_front1_feixiao_0/1/2/3 未采')
    states = [test_context.load_screen('货币战争-备战', f'equipped_front1_feixiao_{i}') for i in range(4)]
    avatar_x = CwOpEquipAll.FRONT_AVATAR_FALLBACK[0].x    # front-1 avatar x=743(坐标单一源整改:主源=screen_info 前排-N 派生,常量为兜底)
    thr = CwOpEquipAll.BELOW_DIFF_THRESHOLD              # 8.0
    for i in range(3):                                # 连续态(加 icon)→ diff >> 阈值
        d = _below_icon_diff(states[i], states[i + 1], avatar_x,
                             CwOpEquipAll.BELOW_ICON_Y, CwOpEquipAll.BX_HALF, CwOpEquipAll.BY_HALF)
        assert d > thr, f'{i}→{i + 1} 加 icon 应 diff > {thr},实际 {d:.1f}'
    # 同态 → ~0(无变化)
    assert _below_icon_diff(states[0], states[0], avatar_x,
                            CwOpEquipAll.BELOW_ICON_Y, CwOpEquipAll.BX_HALF, CwOpEquipAll.BY_HALF) < thr


def test_empty_slots_skips_occupied() -> None:
    """equip_all P0-2 占位检测(``_empty_slots``):已穿槽跳过,只返空槽(1-based)。

    ``read_row_equipped`` 返 ``{slot_idx: [装备名]}``(1-based);槽不在 dict = 空。
    全空 → 全槽;部分已穿 → 跳过;全已穿 → 空(op 应停)。
    修原 bug:``target=FRONT_AVATARS[equipped]`` 按已穿计数索引 → 已穿槽被覆盖。
    """
    from sr_od.application.currency_war.operations.cw_op.cw_op_equip_all import (
        _empty_slots,
    )
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

    from sr_od.application.currency_war.obs.cw_equipment import _select_equipped_layout
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
    from sr_od.application.currency_war.operations.cw_op.cw_op_equip_all import (
        _prioritize_wearable,
    )
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


# ==================== core_count_for ====================

from sr_od.application.currency_war.kernel.cw_line_defs import core_count_for


def test_bridge_target_counts_pool_core() -> None:
    """桥 id → 桥池 fixed+core 在场数(W126/ADR-0350:hunt3/dot_belog
    已封存删除——hunt3 路由退缺省;存活桥照常计数)。"""
    names = {'飞霄', '椒丘'}
    # hunt3 已删:未知桥 id 走缺省路由(飞霄/椒丘 ∉ 三人组 → 0)
    assert core_count_for('hunt3', names) == 0
    assert core_count_for('xianzhou_dot', {'爻光', '藿藿'}) == 2   # fixed+core
    assert core_count_for('xianzhou_dot', {'爻光', '姬子·启行'}) == 1  # 非核心不计


def test_p2_bridge_routed() -> None:
    """P2 桥(train4_shield3)也走路由(不在 P1 池;曾静默退三人组)。"""
    assert core_count_for('train4_shield3', {'三月七'}) >= 1


def test_bridge_field_name_is_real() -> None:
    """桥字段存在性(审查#3:getattr 链死防御掩盖改名;直接属性
    访问,改名即刻 AttributeError)。"""
    from sr_od.application.currency_war.kernel.cw_bridge_pool import (
        BRIDGE_POOL,
        BRIDGE_POOL_P2,
    )
    for combo in (*BRIDGE_POOL, *BRIDGE_POOL_P2):
        assert combo.bridge_id   # 属性访问:字段改名此处即炸


def test_line_bridge_id_no_overlap() -> None:
    """桥 id 唯一性(旧线库已删;桥 id 与 COMP/角色名不撞即可)。"""
    from sr_od.application.currency_war.kernel.cw_bridge_pool import (
        BRIDGE_POOL,
        BRIDGE_POOL_P2,
    )
    bridge_ids = {c.bridge_id
                  for c in (*BRIDGE_POOL, *BRIDGE_POOL_P2)}
    assert len(bridge_ids) == len((*BRIDGE_POOL, *BRIDGE_POOL_P2)), \
        '桥 id 重复(core_count_for 路由歧义)'


def test_empty_and_unknown_fallback_trio() -> None:
    """空 target → 三人组缺省;未知 target 不 crash 退缺省。"""
    assert core_count_for('', {'爻光', '藿藿', '丹恒·饮月'}) == 3
    assert core_count_for('nonexistent', {'藿藿'}) == 1


# (test_sim_ledger_core_count_semantics 已按瘦身批 F11 归位 sim 主题文件
#  test_cw_sim_suite.py 的 sim_ledger_checks 节——机制错位,此处不再收留。)


# ==================== tome_template ====================

from sr_od.application.currency_war.obs import cw_identity_obs as cio  # noqa: E402

# 备战栏-1..9 pc_rect(assets/game_data/screen_info/currency_war_battle_prep.yml;
# 与 cw_identity_obs._ctx_slots 同一坐标系的离线硬编码,同 find_supply_boxes 分层约定)
SLOTS = [
    Rect(382, 845, 495, 979), Rect(507, 844, 620, 978), Rect(632, 844, 743, 978),
    Rect(757, 845, 869, 979), Rect(882, 846, 995, 980), Rect(1004, 847, 1118, 978),
    Rect(1132, 846, 1244, 977), Rect(1256, 845, 1368, 979), Rect(1379, 844, 1493, 980),
]
_IDX = list(enumerate(SLOTS, 1))

_FRAME_GOLD = FIXTURES / 'shop_closed_lowhp.webp'      # slot1/7 金卡典籍 + slot4/9 银箱
_FRAME_FULL = FIXTURES / 'reward_spheres_5.webp'        # slot1 银箱,备战 9/9 满


def _slots(screen: np.ndarray) -> list[tuple[int, Rect]]:
    """1080p 整帧校验 + 带槽号 rect 对(防 fixture 尺寸漂移静默错位)。"""
    assert screen.shape[:2] == (1080, 1920), f'真值帧应为 1080p,实得 {screen.shape}'
    return _IDX


@pytest.fixture(scope='module')
def gold_frame() -> np.ndarray:
    img = cv2_utils.read_image(str(_FRAME_GOLD))
    assert img is not None, f'真值帧缺失:{_FRAME_GOLD}'
    return img


@pytest.fixture(scope='module')
def full_frame() -> np.ndarray:
    img = cv2_utils.read_image(str(_FRAME_FULL))
    assert img is not None, f'真值帧缺失:{_FRAME_FULL}'
    return img


def test_gold_card_slots_hit_tomes(gold_frame) -> None:
    """slot1/slot7 金票券卡必须被 find_tomes 命中(旧模板在 slot7 被 shape 守卫
    判盲 → 箱模板低分接走 → 误判为箱)。"""
    tomes = cio.find_tomes(gold_frame, _slots(gold_frame))
    tome_slots = {idx for idx, _ in tomes}
    assert {1, 7} <= tome_slots, f'金卡典籍槽应命中,实得 {sorted(tome_slots)}'


def test_silver_box_slots_not_tomes(gold_frame) -> None:
    """银箱槽(slot4/9)互斥判定必须走箱:箱命中且不被认成典籍。"""
    boxes = cio.find_supply_boxes(gold_frame, _slots(gold_frame))
    tomes = cio.find_tomes(gold_frame, _slots(gold_frame))
    box_slots = {idx for idx, _ in boxes}
    tome_slots = {idx for idx, _ in tomes}
    assert {4, 9} <= box_slots, f'银箱槽应报箱,实得 {sorted(box_slots)}'
    assert not ({4, 9} & tome_slots), f'银箱槽不得判典籍,实得 {sorted(tome_slots)}'


def test_full_bench_box_frame_unregressed(full_frame) -> None:
    """备战满帧(9/9)的箱格判定不得回归:slot1 银箱仍报箱、不判典籍。"""
    boxes = cio.find_supply_boxes(full_frame, _slots(full_frame))
    tomes = cio.find_tomes(full_frame, _slots(full_frame))
    assert 1 in {idx for idx, _ in boxes}, '满帧 slot1 银箱应报箱'
    assert 1 not in {idx for idx, _ in tomes}, '满帧 slot1 银箱不得判典籍'


def test_templates_fit_smallest_slot_crop() -> None:
    """shape 容差锁:supply 目录全部模板必须不大于最小槽裁片(宽 111 x 高 131),
    否则该槽被 shape 守卫跳过 = 对此物品判盲(典籍旧模板 113x134 的病根)。"""
    tpl_dir = _REPO_ROOT / 'assets' / 'template' / 'currency_war' / 'supply'
    for p in tpl_dir.glob('*.png'):
        img = cv2_utils.read_image(str(p))
        assert img is not None, f'模板读取失败:{p.name}'
        h, w = img.shape[:2]
        assert w <= 111 and h <= 131, \
            f'{p.name} 尺寸 {w}x{h} 超过最小槽裁片 111x131,shape 守卫会判盲部分槽'


def test_shape_guard_skip_is_visible(monkeypatch) -> None:
    """守卫观测锁:裁片小于模板时跳过,但记数必须递增(不再静默)。"""
    monkeypatch.setattr(cio, '_tome_gray', None)
    monkeypatch.setattr(cio, '_tome_loaded', False)
    before = cio._shape_guard_skip_count
    # 槽 rect 5x5 < 任何 supply 模板 → 全部走守卫跳过
    out = cio.find_tomes(np.full((20, 20, 3), 200, dtype=np.uint8),
                         [(1, Rect(0, 0, 5, 5))])
    assert out == []
    assert cio._shape_guard_skip_count > before, '守卫跳过必须记数可见'
# ==================== back_layout ====================

from sr_od.application.currency_war.obs.currency_war_char_id import (  # noqa: E402
    identify_character,
    load_avatar_templates,
)
from sr_od.application.currency_war.obs.cw_identity_obs import (  # noqa: E402
    identify_slots,
)

TPL_DIR = _REPO_ROOT / 'assets/template/currency_war/portrait_plaza'
# 8 格档槽位中心(狸猫局交互实拍;ADR-0281 真值布局)
_C8 = (464, 606, 748, 889, 1031, 1174, 1316, 1458)


def _slots8():
    return [(i, Rect(x - 71, 600, x + 71, 739)) for i, x in enumerate(_C8, 1)]


@pytest.fixture(scope='module')
def templates():
    return load_avatar_templates(TPL_DIR)


@pytest.fixture(scope='module')
def frame():
    return cv2_utils.read_image(str(FIXTURES / '后排8槽-狸猫局.webp'))


@pytest.fixture(scope='module')
def tanuki_ids(frame, templates):
    """狸猫局位1/2/7/8 识别结果(name, inliers)模块内单载。

    强度/定名/兄弟互斥三个锚定测消费同一帧同一批裁剪——识别只算一次,
    断言面各自独立(合并战役:同输入只算一次,禁各测重跑识别)。"""
    out = {}
    for slot, cx in ((1, 464), (2, 606), (7, 1316), (8, 1458)):
        crop = frame[600:740, cx - 71:cx + 71]
        out[slot] = identify_character(crop, templates)
    return out


# ===== 1. 8 格档识别(含旧 9/10/11 触发帧回归到 8 格档) =====

def test_tanuki_templates_in_library(templates):
    """狸小虎(蓝,弟弟)/狸小龙(红,哥哥)建档且在库。"""
    assert '狸小虎' in templates
    assert '狸小龙' in templates


def test_slot8_identification(tanuki_ids):
    """8 槽布局逐槽识别:位1 藿藿/位2 爻光/位7 狸小虎/位8 狸小龙(交互实锤锚)。"""
    for slot in (1, 2, 7, 8):
        name, inliers = tanuki_ids[slot]
        assert inliers and inliers > 15, f'位{slot} 识别强度不足: {name},{inliers}'


def test_slot8_expected_names(tanuki_ids):
    """锚点定名:位1=藿藿,位7=狸小虎,位8=狸小龙(详情面板交互实锤,2026-08-19)。"""
    want_map = {1: '藿藿', 7: '狸小虎', 8: '狸小龙'}
    for slot, want in want_map.items():
        name, inliers = tanuki_ids[slot]
        assert name == want, f'位{slot} 应为 {want},实识别 {name}({inliers})'
    # (瘦身批 F2:原 test_tanuki_no_cross_match(蓝/红狸猫互不误认)断言面
    #  = 本表 7/8 两项的严格子集,已并入此锁,不再单测。)


def test_slot8_empty_slots_no_false_positive(frame, templates):
    """空槽位3-6 不得出假识别(用户终局事实:位3-6 空)。"""
    slots = [(i, Rect(x - 71, 600, x + 71, 739))
             for i, x in ((3, 748), (4, 889), (5, 1031), (6, 1174))]
    out = identify_slots(frame, templates, slots, 'back')
    assert not out, f'空槽出假识别: {[(c.slot, c.char_id) for c in out]}'


def test_slot8_all_positions_identified(templates):
    """全位验证 fixture(用户实机逐位拖拽,2026-08-19):位1-8 逐一识别。"""
    frame2 = cv2_utils.read_image(str(FIXTURES / '后排8槽-全位验证.webp'))
    got = {c.slot: c.char_id for c in identify_slots(frame2, templates, _slots8(), 'back')}
    assert got == {1: '藿藿', 2: '爻光', 6: '开拓者·欢愉', 7: '狸小虎', 8: '狸小龙'}, got


def test_trailblazer_joy_template_strength(templates):
    """开拓者·欢愉 现场模板(r76 治本:plaza 烘焙版 6 inliers → 现场版 138)。"""
    frame2 = cv2_utils.read_image(str(FIXTURES / '后排8槽-全位验证.webp'))
    crop = frame2[600:740, 1174 - 71:1174 + 71]   # 位6(全位验证帧开拓者在位6)
    name, inliers = identify_character(crop, templates)
    assert name == '开拓者·欢愉' and inliers > 30, f'{name},{inliers}'


def test_yinzhi_trial_template(templates):
    """银枝试用版模板(r82 治本;最低强度锁:模板在库即可)。"""
    assert '银枝' in templates


# ===== 旧 9/10/11 档触发帧 → 按 8 格档锁(ADR-0281 核心证据;F7 参数化合一) =====

@pytest.mark.parametrize('fn, want', [
    ('后排8槽-双宝钻局.webp', {1: '藿藿', 2: '爻光', 6: '开拓者·欢愉',
                               7: '狸小虎', 8: '狸小龙'}),   # cap9/lv7
    ('后排8槽-满级局.webp', {1: '爻光', 2: '三月七', 3: '藿藿', 6: '开拓者·欢愉',
                             7: '狸小虎', 8: '狸小龙'}),      # cap10/lv8
    ('后排8槽-P3局.webp', {3: '藿藿', 6: '开拓者·欢愉',
                           7: '狸小虎', 8: '狸小龙'}),         # cap11/lv8
])
def test_cap_frame_is_8grid(templates, fn, want):
    """旧 9/10/11 档触发帧按 8 格档识别(旧「9/10/11 槽」档全是幻影)。

    旧 9 槽格点前 8 格与 8 格档完全同位(464..1458)——即旧「9 槽实证」的
    全部命中本就落在 8 格布局内,第 9 格(1600)是背景(空槽签名终判);
    三触发帧狸猫恒在 1316/1458(=8 格档位7/8,恒最右模型)——与「7/9/10/11
    全是幻影」双源交叉实证(cap 与布局无关)。
    """
    fix = cv2_utils.read_image(str(FIXTURES / fn))
    got = {c.slot: c.char_id for c in identify_slots(fix, templates, _slots8(), 'back')}
    assert got == want, got


# ===== 2/3. cap 差公式路由 + 幻影档不存在 =====

def test_cap_diff_routing():
    """ADR-0385 口述公式「后台格数 = 6+(cap−level)」路由:
    diff0→6 / diff1→7(已建档,2026-08-26 佩佩局实锤)/ diff≥2→8;
    diff<0(读错族)按 0;diff>2(域外)按 2。level 单独不参与。"""
    from sr_od.application.currency_war.obs.cw_back_layout import (
        _LAYOUT_PREFIX,
        back_slots_from_cap_diff,
        fallback_back_slots,
    )
    # 三真值档(7 = 佩佩局交互实锤建档;9/10/11 仍是循环论证幻影,已删)
    assert set(_LAYOUT_PREFIX) == {6, 7, 8}
    assert _LAYOUT_PREFIX[6] == '后排'
    assert _LAYOUT_PREFIX[7] == '后排7槽'
    assert _LAYOUT_PREFIX[8] == '后排8槽'
    for n in (9, 10, 11, 12):
        assert n not in _LAYOUT_PREFIX
    # 公式路由
    assert back_slots_from_cap_diff(0) == 6
    assert back_slots_from_cap_diff(1) == 7    # 7 格已建档 → 直读(佩佩局锚)
    assert back_slots_from_cap_diff(2) == 8
    assert back_slots_from_cap_diff(3) == 8    # 域外按 2(cap10/lv8、cap11/lv8 局同 8 格)
    assert back_slots_from_cap_diff(-1) == 6   # cap<level 读错族按 0
    slots = fallback_back_slots()
    assert len(slots) == 6 and slots[0][0] == 1


def test_phantom_layouts_absent_from_yml():
    """yml(源 + merged)无 后排9/10/11槽 幻影 area(ADR-0281 清除,源与派生
    层同步)。**后排7槽 不在幻影清单**:7 格=钻石+1 局真值档(口述公式),
    实锤建档后合法存在(_LAYOUT_PREFIX 是否已登记 7 由 test_cap_diff_routing
    的 _LAYOUT_PREFIX 断言辖,不在此双锁)。"""
    for rel in ('assets/game_data/screen_info/currency_war_battle_prep.yml',
                'assets/game_data/screen_info/_od_merged.yml'):
        txt = (_REPO_ROOT / rel).read_text(encoding='utf-8')
        for pfx in ('后排9槽', '后排10槽', '后排11槽'):
            assert pfx not in txt, f'{rel} 残留幻影档 {pfx}'
        assert '后排8槽-1' in txt and '后排-1' in txt, f'{rel} 缺 6/8 真值档'


# ===== 4. select_back_layout 选档入口 + 7 格待采留证 =====

@pytest.fixture()
def _layout_fresh(monkeypatch, tmp_path):
    """布局选档家族共享桩前导(F8:原 17 处复制 monkeypatch 前导收敛于此,
    以此为范,防桩面漂移):
    ①模块级全局复位——未知态计数器/通道冲突节流表/选档日志(测试纪律 4:
    生产路径含模块级全局时 setup 一并桩化),用例结束再清一次防泄漏;
    ②冲突日志重定向 tmp_path + 截图采集桩(测试纪律 2:不写真实 .debug/;
    附带修好原 test_unknown_freeze 未桩 journal 直写生产路径的卫生缺口)。
    yield 出 journal 路径,留证断言直接读它。"""
    import sr_od.application.currency_war.kernel.cw_observe as cobs
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    journal = tmp_path / 'obs.jsonl'
    cbl.reset_layout_unknown_state()
    monkeypatch.setattr(cobs, '_CONFLICT_JOURNAL', journal)
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cbl, '_channel_conflict_ts', {})
    monkeypatch.setattr(cbl, '_last_sel_log', None)
    yield journal
    cbl.reset_layout_unknown_state()


def test_select_back_layout_formula(_layout_fresh, monkeypatch, frame):
    """选档单一入口·公式通道(cv 通道 stub 掉隔离;双通道对账见下方专项锁):
    cap/level 两读数按口述公式合流;读不到 → 6(失败安全侧)。

    run 26 反向锚:lv8 无召唤物(cap=level)→ 恒 6 格(旧模型按 level≥7 选 8 格
    = 崩坏根因①);lv7 cap9(狸猫局)→ 8 格。
    """
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_identity_obs as cio
    import sr_od.application.currency_war.obs.cw_observation as cwo
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 8)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: 8)
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: None)   # CV 不可判 → 公式
    assert cbl.select_back_layout(None, frame) == (6, '后排')      # run 26 形态:lv8 cap8
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: 10)
    assert cbl.select_back_layout(None, frame) == (8, '后排8槽')   # diff2 → 8
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 7)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: 9)
    assert cbl.select_back_layout(None, frame) == (8, '后排8槽')   # 狸猫局 lv7 cap9
    # diff==1(钻石+1):7 格已建档(佩佩局实锤)→ 直读 7 格
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: 8)
    assert cbl.select_back_layout(None, frame) == (7, '后排7槽')
    # 件③:7 格留证机器已废(存在性=钻石+1 由公式回答;坐标档已建档钩子静默)
    # 读不到 cap → diff 按 0 → 6(失败安全侧;别按扩展档跑)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: None)
    assert cbl.select_back_layout(None, frame) == (6, '后排')


# ===== 4b. CV 通道 + 双通道对账(ADR-0385 口述双通道指令,追加) =====

def test_cv_channel_grid_counts(templates):   # noqa: ARG001  复用模块级模板加载惰性
    """CV 通道实测格数:占用态门三态探针(布局档对账批;真 fixture 全量标定)。

    判据 = 每探针「整窗+两半窗」std 三段形态:none(整窗 <6)/ 擦线不可判
    (整窗 ∈[6,12) → None 退公式)/ full(整窗 ≥12 ∧ 半窗对称比 <2.5)/
    slice(整窗 ≥12 ∧ 对称比 ≥2.5);组合 (full,full)→8 /
    (slice,slice)→7 / (none,none)→6 / 混合→None 退公式。
    标定数字见 ``_PROBE_*`` 常量块注释。

    8 格帧(狸猫/全位验证/cap9/cap10,两端整格 50.7-65.6,对称比 1.0-1.2)→ 8;
    **P3 局(cap11)左 1 空槽暗框 = 整格存在证据**(整窗 38.8、对称比 1.0)
    → 8(旧整窗判据落不可判带退公式;占用态门消解旧不可判带,运行值不变
    仍 8 格);
    6 格帧(shop_closed/a8_start/prep_1-6/deployed_p1r9/r1_idle_stop)→ 6;
    「后排6槽-P2开局局」→ **6**(旧「7 槽」观察实为 6 格幻影,W535 按实格数
    改名);
    **真 7 格帧(佩佩局×2 + deployed_r9_7grid 停机哨兵帧)→ 7**(slice,
    slice:不对称比 5.3-30.8 双双过分界;旧整窗判据落不可判带 → None 退
    公式——占用态门把 ADR-0390 勘误案从「公式兜底」升级为「探针直读」)。
    非 1080p 小帧 → None(越界守卫)。

    run 26 崩坏现场帧(后排6槽-run26崩坏现场.png,编排者 VLM+右端位置双重
    确认 = 标准 6 格正样本)→ 6:事故形态的直接回归锚。
    """
    import numpy as np

    from sr_od.application.currency_war.obs.cw_back_layout import cv_back_slots
    for fn, want in (
            ('后排8槽-狸猫局.webp', 8), ('后排8槽-全位验证.webp', 8),
            ('后排8槽-双宝钻局.webp', 8), ('后排8槽-满级局.webp', 8),
            ('后排8槽-P3局.webp', 8),   # 空 1 槽暗框=整格存在(占用态门消解旧不可判带)
            ('后排7槽-佩佩局.png', 7),          # slice,slice:两端切片签名 → 直读 7
            ('后排7槽-佩佩局-拖测后.png', 7),   # 同上(拖测后帧)
            ('deployed_r9_7grid.webp', 7),      # slice,slice(不对称比 5.3/28.8)→ 直读 7
            ('后排6槽-P2开局局.webp', 6), ('shop_closed.webp', 6),
            ('shop_closed_a8_start.webp', 6), ('prep_1-6_all_positions.webp', 6),
            ('deployed_p1r9.webp', 6), ('r1_idle_stop.webp', 6),
            ('后排6槽-run26崩坏现场.png', 6)):
        img = cv2_utils.read_image(str(FIXTURES / fn))
        got = cv_back_slots(img)
        assert got == want, f'{fn}: CV 实测 {got} ≠ 期望 {want}'
    assert cv_back_slots(np.zeros((600, 900, 3), dtype=np.uint8)) is None


def test_reconcile_channels_agree(_layout_fresh, monkeypatch, frame):
    """对账·一致 → 公式值,无 back_layout_channel_conflict 留证。"""
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_identity_obs as cio
    import sr_od.application.currency_war.obs.cw_observation as cwo
    journal = _layout_fresh
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 7)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: 9)
    # 狸猫局真帧:公式 diff2 → 8,CV 实测 8 → 一致用公式值
    assert cbl.select_back_layout(None, frame) == (8, '后排8槽')
    assert not journal.exists() or 'back_layout_channel_conflict' not in \
        journal.read_text(encoding='utf-8')


def test_reconcile_channels_disagree_cv_wins(_layout_fresh, monkeypatch, frame):
    """对账·不一致 → **CV 实测值** + obs_conflict 留证带两值(画面事实>推导)。

    场景=run 26 事故族的反向:公式说 6(两个 OCR 读数错成 cap=level)但画面
    实为 8 格(狸猫真帧)→ 采 CV 的 8(不误按 6 格丢读扩展带)+ 留证
    old=6(公式)/new=8(CV)供判读查 reader。
    """
    import json as _json

    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_identity_obs as cio
    import sr_od.application.currency_war.obs.cw_observation as cwo
    journal = _layout_fresh
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 8)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: 8)   # 公式:6
    assert cbl.select_back_layout(None, frame) == (8, '后排8槽')      # CV 8 优先
    assert journal.exists(), '不一致未留证'
    rec = _json.loads(journal.read_text(encoding='utf-8')
                      .strip().splitlines()[-1])
    assert rec['field'] == 'back_layout_channel_conflict'
    assert rec['old'] == 6 and rec['new'] == 8   # 两值齐报(公式/CV)


def test_reconcile_cv_none_formula_fallback(_layout_fresh, monkeypatch, frame):
    """CV 不可判(锚缺失/越界/特效遮挡)→ 退公式值(公式=CV 失效的兜底)。"""
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_identity_obs as cio
    import sr_od.application.currency_war.obs.cw_observation as cwo
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 8)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: 10)
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: None)
    assert cbl.select_back_layout(None, frame) == (8, '后排8槽')
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: 8)
    assert cbl.select_back_layout(None, frame) == (6, '后排')


def test_read_deployed_chars_formula_driven(
        test_context, templates, _layout_fresh, monkeypatch, frame):
    """read_deployed_chars 布局选档经 select_back_layout(双通道合流)。

    狸猫局 fixture + monkeypatch cap:diff2(与 CV 一致)→ 8 格档读到位7/8 狸猫;
    同帧 diff0 + CV stub 一致(6)→ 6 格档:最右扩展格(1458 狸小龙)不再被读
    (6 格基线右界 1315,恰含 1316 狸小虎——两档共享 604-1316 段,差异只在
    两端扩展格)。
    """
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_identity_obs as cio
    import sr_od.application.currency_war.obs.cw_observation as cwo
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: 9)
    out8 = cio.read_deployed_chars(test_context, frame, templates, level=7)
    got8 = {c.char_id for c in out8 if c.position_pref == 'back'}
    assert {'狸小虎', '狸小龙'} <= got8
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: 8)
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: 6)   # 两通道一致 6
    out6 = cio.read_deployed_chars(test_context, frame, templates, level=8)
    got6 = {c.char_id for c in out6}
    assert '狸小龙' not in got6   # 1458 扩展格在 6 格基线外


# ===== 5. 系统单位恒最右布局自检 =====

def test_system_unit_layout_check_ok(_layout_fresh, monkeypatch, frame, templates):
    """对档(8 格档,狸猫在位7/8)→ 无 layout_mismatch 留证。"""
    import sr_od.application.currency_war.obs.cw_identity_obs as cio
    journal = _layout_fresh
    monkeypatch.setattr(cio, '_sysunit_conflict_ts', {})
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    chars = [BenchChar(slot=7, char_id='狸小虎'), BenchChar(slot=8, char_id='狸小龙')]
    cio.check_system_unit_layout(frame, chars, _slots8(), templates, source='test')
    assert not journal.exists() or 'layout_mismatch_by_system_unit' not in journal.read_text(encoding='utf-8')


def test_system_unit_layout_check_mismatch(_layout_fresh, monkeypatch, frame, templates):
    """错档(狸猫实测 x≈1316/1458 vs 所选档右格 1174)→ layout_mismatch_by_system_unit 留证。"""
    import sr_od.application.currency_war.obs.cw_identity_obs as cio
    journal = _layout_fresh
    monkeypatch.setattr(cio, '_sysunit_conflict_ts', {})
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    # 模拟「6 格截短档」(右格 1174):狸猫实测 1316/1458 与右格差 ≥142px > 40 → 冲突
    slots6 = [(i, Rect(x - 71, 600, x + 71, 739)) for i, x in enumerate(_C8[:6], 1)]
    chars = [BenchChar(slot=6, char_id='狸小虎'), BenchChar(slot=7, char_id='狸小龙')]
    cio.check_system_unit_layout(frame, chars, slots6, templates, source='test')
    assert journal.exists(), '错档未留证'
    rec = json.loads(journal.read_text(encoding='utf-8').strip().splitlines()[-1])
    assert rec['field'] == 'layout_mismatch_by_system_unit'
    assert rec['char_id'] in ('狸小虎', '狸小龙')


# ===== 6. deploy 剔除系统单位 =====

def test_deploy_excludes_system_units():
    """ADR-0281 件4:重排候选剔除系统单位(cost==0 不可拖);普通角色/未知保留。"""
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        exclude_system_units,
    )
    chars = [
        BenchChar(slot=1, char_id='藿藿'),
        BenchChar(slot=7, char_id='狸小虎'),
        BenchChar(slot=8, char_id='狸小龙'),
        BenchChar(slot=2, char_id=''),          # SIFT 未识别:保留(旧行为)
    ]
    out = exclude_system_units(chars)
    assert [c.char_id for c in out] == ['藿藿', '']



# ===== 6b. 布局留证采集钩子(ADR-0385 决策 12:停机钩子降级废弃)=====
# run 27 停机事故实证:货币战争备战实时倒计时,停 bot ≠ 停游戏——hook 停机后
# 画面自行推进到首领战败结算(14:09 停 → 14:16 结算),「停机保画面待采集」
# 对实时制游戏是虚假承诺。降级:n_raw=7 → obs_conflict 留证+去重截图不停机;
# 7 格坐标由 CV 持续留证 + 人工在场经 MCP 交互采集。

def test_layout_hook_no_stop_only_evidence(
        test_context, templates, _layout_fresh, monkeypatch, frame):
    """降级锁(7 格建档后语义):n_raw 未建档(用 9 模拟未来新档,
    CV 三读稳定)→ **不停机**,落 back_layout_unarchived_grid 留证(带公式/
    CV/防抖序列),无 flag 文件;真实 7 格(diff==1)已建档 → 见
    test_layout_hook_silent_on_archived。"""
    import json as _json

    import sr_od.application.currency_war.kernel.cw_obs_core as core
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_identity_obs as cio
    import sr_od.application.currency_war.obs.cw_observation as cwo
    ctx = test_context

    class _FakeRunCtx:
        stopped = False
        stop_calls: list[str] = []

        def stop_running(self, reason: str = ''):
            self.stopped = True
            self.stop_calls.append(reason)

    monkeypatch.setattr(ctx, 'run_context', _FakeRunCtx())
    monkeypatch.setattr(core, 'is_prep_like_frame', lambda c, s: True)
    monkeypatch.setattr(cio, '_session_level', lambda c: 8)
    # 公式 8(lv8 cap10 diff2)且 CV 三读稳定 9(防抖过)→ n_raw=9 未建档
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda c, s, level=None: 10)
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda s: 9)
    monkeypatch.setattr(ctx, 'screenshot', lambda: frame, raising=False)
    out = cio.read_deployed_chars(ctx, frame, templates, level=8)
    assert isinstance(out, list) and out                    # 读板照常不抛
    assert not ctx.run_context.stopped and not ctx.run_context.stop_calls, \
        'W209i:未建档档不得停机(实时制游戏停 bot 不停游戏,run 27 实证)'
    journal = _layout_fresh
    assert journal.exists(), '降级后必须留证'
    rec = _json.loads(journal.read_text(encoding='utf-8').strip().splitlines()[-1])
    assert rec['field'] == 'back_layout_unarchived_grid'
    assert rec['old'] == 9 and rec['cv_readings'] == [9, 9, 9]
    assert '不停机' in rec['verdict']                        # 如实声明画面可能推进
    assert not (journal.parent / '.debug/temp/currency_war/back_layout_stop_hook.flag').exists(), \
        '停机 flag 机制已废弃不得回流'


def test_layout_hook_silent_on_archived(
        test_context, templates, _layout_fresh, monkeypatch, frame):
    """6/8/7 已建档(含超集运行态、对账一致态与 7 格直读态)→ 无留证无副作用。

    2026-08-26 佩佩局 7 格建档后,(8,9,7) = diff1 直读 7 的真值态,必须
    静默(旧「7 未建档刷留证」行为已废,证据垃圾)。"""
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_identity_obs as cio
    import sr_od.application.currency_war.obs.cw_observation as cwo
    ctx = test_context
    # 6 格(run 26 形态)/ 8 格(狸猫局形态)/ 7 格(佩佩局直读)都不留证
    for lv, cap, cv in ((8, 8, 6), (7, 9, 8), (8, 9, 7)):
        monkeypatch.setattr(cio, '_session_level', lambda c, _lv=lv: _lv)
        monkeypatch.setattr(cwo, 'read_deploy_cap', lambda c, s, level=None, _cap=cap: _cap)
        monkeypatch.setattr(cbl, 'cv_back_slots', lambda s, _cv=cv: _cv)
        cio.read_deployed_chars(ctx, frame, templates, level=lv)
    # 只辖本测对象(未建档留证钩子);check_system_unit_layout 在 (8,9,7) 态
    # 对 8 格狸猫帧按 7 格选档正确报 layout_mismatch(自检职责,另锁辖)
    journal = _layout_fresh
    if journal.exists():
        txt = journal.read_text(encoding='utf-8')
        assert 'back_layout_unarchived_grid' not in txt, \
            '已建档档位(6/7/8)不得落未建档留证'


def test_layout_hook_no_stop_machinery_in_src():
    """源码级锁:read_deployed_chars 不得再调 stop_running/写停机 flag
    (停机钩子整段废弃,回流即红)。"""
    import inspect

    from sr_od.application.currency_war.obs import cw_identity_obs
    src = inspect.getsource(cw_identity_obs.read_deployed_chars)
    assert 'stop_running' not in src and 'back_layout_stop_hook.flag' not in src, \
        '停机机制已废弃(ADR-0385 决策 12);采集走留证+人工经 MCP'


def test_pending_7slots_machinery_removed():
    """件②:旧「lv6=7 格待采」留证机器已清理(存在性由公式回答=钻石+1,
    与等级无关;缺的只是坐标档,归停机钩子管)。"""
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    assert not hasattr(cbl, 'note_7slots_pending')
    assert not hasattr(cbl, '_pending_note_ts')
    assert not hasattr(cbl, '_PENDING_7SLOT_LEVELS')


# ===== 6c. CV 新格数防抖重读(ADR-0385 决策 11;run 27 停机事故) =====
# 事故:特效/粒子瞬态把 1458 位单帧 std 顶到 6.5(阈值 6.0 擦线,真槽 ≥10.5/
# 背景 ≤2.9 之间无人带)→ CV 假阳 7 → 停机。修:新格数读数(≠公式 且 ∉{6,8})
# 单帧不行动——重读 2 次三次一致才采 CV;任一不一致 = 瞬态自愈退公式+留证。

class _FakeCtx:
    """重读帧源:queue 依次回放,耗尽 = 最后一帧(生产=ctx.screenshot 现截)。"""

    def __init__(self, frames):
        self._frames = list(frames)
        self.shots = 0

    def screenshot(self):
        self.shots += 1
        return self._frames[min(self.shots - 1, len(self._frames) - 1)]


def test_cv_transient_falls_back_to_formula(_layout_fresh, monkeypatch, frame):
    """run 27 事故形态(以未建档 9 模拟新格数瞬态):首读假阳 9,重读回到
    真值 6(序列 [9,6,6])→ 退公式 8,不停机;瞬态留证 obs_conflict。

    (7 格已建档:CV 稳定 7 = 合法档直读,不经防抖;瞬态 7 误读的代价仅是
    多读一个空扩展窗(超集语义,无动作损失),run 27 型停机事故不再可能。)"""

    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_identity_obs as cio
    import sr_od.application.currency_war.obs.cw_observation as cwo
    # 6 格真帧(shop_closed)×2 作重读帧
    frame6 = cv2_utils.read_image(str(FIXTURES / 'shop_closed.webp'))
    fctx = _FakeCtx([frame6, frame6])
    journal = _layout_fresh
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 8)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: 10)  # 公式 8
    # 序列 stub:首帧(入参 frame)假阳 9,重读帧(真 6 格 fixture)= 6
    real_cv = cbl.cv_back_slots

    def _seq_cv(scr):
        if scr is frame:
            return 9
        return real_cv(scr)   # 重读帧=真 6 格帧
    monkeypatch.setattr(cbl, 'cv_back_slots', _seq_cv)
    r = cbl.resolve_back_slots(fctx, frame, level=8, cap=10)
    assert r['n'] == 8 and r['n_raw'] == 8      # 瞬态自愈 → 公式值
    assert r['cv_readings'] == [9, 6, 6]        # 序列留档
    assert journal.exists() and 'back_layout_cv_transient' in \
        journal.read_text(encoding='utf-8')     # 瞬态留证
    assert fctx.shots == 2                      # 重读恰好 2 次


def test_cv_stable_new_grid_confirmed(_layout_fresh, monkeypatch, frame):
    """稳定未建档新格数(以 9 模拟):三读一致 [9,9,9] → 采 CV 值
    (n_raw=9 触发留证钩子采集流程,防抖不拦真信号;运行值退 8 超集)。"""
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_identity_obs as cio
    import sr_od.application.currency_war.obs.cw_observation as cwo
    fctx = _FakeCtx([frame, frame])   # 重读帧同 frame(stub 全 9)
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 8)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: 10)  # 公式 8
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: 9)          # 三读全 9
    r = cbl.resolve_back_slots(fctx, frame, level=8, cap=10)
    assert r['n_raw'] == 9 and r['n'] == 8      # 采 CV 9 → 运行 8 超集(未建档)
    assert r['cv_readings'] == [9, 9, 9]
    assert fctx.shots == 2


def test_cv_reread_mismatch_logged_no_action(_layout_fresh, monkeypatch, frame):
    """重读帧间不一致(如 [9,9,6],未建档 9 模拟)= 瞬态 → 退公式 + 序列留证
    (obs_conflict 带 cv_readings 上下文),不采 CV。"""

    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_identity_obs as cio
    import sr_od.application.currency_war.obs.cw_observation as cwo
    frame6 = cv2_utils.read_image(str(FIXTURES / 'shop_closed.webp'))
    fctx = _FakeCtx([frame, frame6])   # 重读 1=frame(9),重读 2=frame6(6)
    journal = _layout_fresh
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 8)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: 10)
    real_cv = cbl.cv_back_slots

    def _seq_cv(scr):
        if scr is frame6:
            return real_cv(scr)       # 6
        return 9
    monkeypatch.setattr(cbl, 'cv_back_slots', _seq_cv)
    r = cbl.resolve_back_slots(fctx, frame, level=8, cap=10)
    assert r['n'] == 8 and r['n_raw'] == 8       # 不一致 → 公式值
    assert r['cv_readings'] == [9, 9, 6]
    assert journal.exists() and 'back_layout_cv_transient' in \
        journal.read_text(encoding='utf-8')


# ===== 6d. cap 通道防抖接线(ADR-0395;run 27 型 = 读数瞬态直驱行动) =====
# 高危点:resolve_back_slots 的 cap 直读(未显式传 cap 时)进 diff → 公式通道
# 选档;deploy_bench 板满门 cap 直读(→ 留 bench 战力真空,低读贵方向)。
# 修:两处消费点改走 read_deploy_cap_debounced(ADR-0286 域防抖:域外重读
# 一帧,仍域外 → None → 失读兜底链)。run 27 实证同型:瞬态单帧读数不行动。

class _CapFakeCtx:
    """cap 重读帧源(debounced 经 ctx.controller.screenshot 现截)。"""

    def __init__(self) -> None:
        self.controller = type('C', (), {'screenshot': staticmethod(lambda: object())})()


def _patch_cap_reader(monkeypatch, seq):
    calls = {'n': 0}

    def _fake(ctx, scr, level=None):
        i = min(calls['n'], len(seq) - 1)
        calls['n'] += 1
        return seq[i]
    import sr_od.application.currency_war.obs.cw_observation as cwo
    monkeypatch.setattr(cwo, 'read_deploy_cap', _fake)
    return calls


def test_cap_transient_in_formula_channel_debounced(_layout_fresh, monkeypatch):
    """run 27 型(格数类):cap 首读瞬态 3(域外,lv6),重读回真值 8(宝钻×2)
    → 采重读值 → 公式 6+(8−6)=8 格;若无防抖 diff=−5 → 6 格错档。"""
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    calls = _patch_cap_reader(monkeypatch, [3, 8])
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: None)  # CV 不可判
    r = cbl.resolve_back_slots(_CapFakeCtx(), object(), level=6, cap=None)
    assert calls['n'] == 2, '域外首读应触发重读'
    assert r['cap'] == 8 and r['formula_raw'] == 8
    assert r['n'] == 8 and r['prefix'] == '后排8槽'


def test_cap_still_domain_rejected_falls_baseline(_layout_fresh, monkeypatch):
    """cap<level 两帧一致([3,3],lv6)→ 防抖采信 cap=3(不再恒拒:d2daffd6
    后下向同走双帧一致通道,level 先验疑毒化,见 _debounce_cap 注/ADR-0420
    判据镜像)→ diff=−3、d=0 仍退 6 格基线(负 diff 不加格,失败安全侧不变)
    + deploy_cap_domain 采信留证。瞬态单帧([3,8] 型)仍由上一锁覆盖。"""
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_observation as cwo
    calls = _patch_cap_reader(monkeypatch, [3, 3])
    conflicts = []
    monkeypatch.setattr(cwo, 'obs_conflict',
                        lambda *a, **k: conflicts.append((a, k)))
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: None)
    r = cbl.resolve_back_slots(_CapFakeCtx(), object(), level=6, cap=None)
    assert calls['n'] == 2 and len(conflicts) == 1
    assert '采信' in str(conflicts[-1][1]), 'cap<level 双帧一致采信须留证'
    assert r['cap'] == 3 and r['diff'] == -3
    assert r['n'] == 6 and r['prefix'] == '后排'


def test_deploy_bench_gate_no_raw_cap_read():
    """源码墓碑(ADR-0395):deploy_bench 板满门禁裸 read_deploy_cap( 直调——
    cap 必须经域防抖读(域外重读一帧,run 27 型瞬态读数不得直驱行动)。
    墓碑 = 否定式 + 退役背书(README 第 8 条合法形态);肯定式在场锁已按
    混合锁拆解删除。接线行为面(生产真调 debounced)由
    test_cw_p4r_deploy_battle_chain.py 的桩驱动断言辖(stub
    read_deploy_cap_debounced 后 notes 分键必含 deploy_cap_gate)。"""
    src = (_REPO_ROOT / 'src/sr_od/application/currency_war/operations/cw_op'
           / 'cw_op_deploy.py').read_text(encoding='utf-8')
    assert 'read_deploy_cap(self.ctx' not in src, \
        '板满门 cap 必须经域防抖读(ADR-0395),不得裸直读'


# ===== 7. 佩佩局真 7 格板面识别(2026-08-26 用户口述真值;ADR-0389/0390) =====
# 识别层三件:①现场变体模板(raw_board.png,真窗口采——错位残片变体会致
# live_only 假阴,万敌@s2 丢读实证后全量重采);②佩佩入库(roster cost=0
# + raw.png);③相邻幽灵去重 + 部署排门槛 15。
# 几何(ADR-0390):7 格=整排居中重排 中心 534..1386(旧记 604..1458 错位
# +71px 已勘误;错位时代的「假阳带/弱命中/幽灵」全族伪象随真窗口消失)。

_C7 = (534, 676, 818, 960, 1102, 1244, 1386)   # 居中重排(ADR-0390;排中心恒 960)


def _slots7():
    return [(i, Rect(x - 71, 600, x + 71, 739)) for i, x in enumerate(_C7, 1)]


def test_pepe_board_truth_current(templates):
    """佩佩局当前帧(用户口述真值):1=万敌/3=乱破/5=卡芙卡/7=佩佩,
    2/4/6 空。**生产参数**(min15+live_only);真窗口下空槽全库 0 假阳、
    残影幽灵自然消失(错位窗口时代的伪象,ADR-0390 勘误)。"""
    fix = cv2_utils.read_image(str(FIXTURES / '后排7槽-佩佩局-拖测后.png'))
    got = {c.slot: c.char_id for c in identify_slots(
        fix, templates, _slots7(), 'back', min_inliers=15, live_only=True,
        center_gate=True)}
    assert got == {1: '万敌', 3: '乱破', 5: '卡芙卡', 7: '佩佩'}, got


def test_pepe_board_truth_golden(templates):
    """佩佩局拖测前帧(用户口述真值):1=卡芙卡/3=万敌/5=爻光/7=佩佩。"""
    fix = cv2_utils.read_image(str(FIXTURES / '后排7槽-佩佩局.png'))
    got = {c.slot: c.char_id for c in identify_slots(
        fix, templates, _slots7(), 'back', min_inliers=15, live_only=True,
        center_gate=True)}
    assert got == {1: '卡芙卡', 3: '万敌', 5: '爻光', 7: '佩佩'}, got


def test_pepe_board_coverage_s246(templates):
    """7 格全覆盖锁(用户交办「拖动角色到后台246 覆盖测试」,2026-08-26):
    万敌 534→676→960→1244 逐位拖测三帧,2/4/6 各读对万敌(真中心拾取,
    板内→空位可拖实证;ADR-0390)。"""
    for fn, slot in (('后排7槽-佩佩局-覆盖s2.png', 2),
                     ('后排7槽-佩佩局-覆盖s4.png', 4),
                     ('后排7槽-佩佩局-覆盖s6.png', 6)):
        fix = cv2_utils.read_image(str(FIXTURES / fn))
        got = {c.slot: c.char_id for c in identify_slots(
            fix, templates, _slots7(), 'back', min_inliers=15, live_only=True,
            center_gate=True)}
        assert got.get(slot) == '万敌', f'{fn}: s{slot} 应为万敌,实得 {got}'
        assert got.get(3) == '风堇' and got.get(5) == '艾丝妲' \
            and got.get(7) == '佩佩', f'{fn}: 基准位漂移 {got}'


def test_true_grid_empty_slots_zero_baseline(templates):
    """真窗口空槽零假阳锁(ADR-0390 勘误后):全库对空槽(2/4/6)最高内点
    应为 0(错位时代的 11-26 假阳带=邻卡残影伪影,已消)。"""
    fix = cv2_utils.read_image(str(FIXTURES / '后排7槽-佩佩局-拖测后.png'))
    for cx in (676, 960, 1244):
        crop = fix[600:739, cx - 71:cx + 71]
        _, inliers = identify_character(crop, templates, min_inliers=1)
        assert inliers == 0, f'空槽@{cx} 出非零本底 {inliers}(假阳带回流)'


def test_pepe_roster_and_template(templates):
    """佩佩建档三面:立绘模板在库;roster cost=0(系统召唤单位);deploy
    候选剔除(不可拖,同狸猫对)。"""
    assert '佩佩' in templates
    from sr_od.application.currency_war.data.cw_chars import get_char
    ch = get_char('佩佩')
    assert ch is not None and ch.cost == 0
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        exclude_system_units,
    )
    out = exclude_system_units([BenchChar(slot=7, char_id='佩佩'),
                                BenchChar(slot=1, char_id='万敌')])
    assert [c.char_id for c in out] == ['万敌']


def test_live_board_variants_in_library(templates):
    """现场变体入库(raw_board.png → 键 名#k):万敌/卡芙卡/乱破/爻光四件,
    棋盘站立小人识别的治本通道(run20 商店卡同机制)。"""
    for name in ('万敌', '卡芙卡', '乱破', '爻光'):
        keys = [k for k in templates if k.split('#')[0] == name]
        assert any('#' in k for k in keys), f'{name} 缺现场变体(raw_board.png)'


def test_read_level_xp_backinference(test_context, monkeypatch):
    """等级漏读 → 经验条反推真级(2026-08-26 佩佩局实弹修复):

    OCR 漏读 Lv.3 小字 → 旧 _expected_level(P1,R1) 兜底 4 → cap−level=0
    → 后排选 6 格档 → **佩佩@slot7 窗口未被枚举丢读**。修:漏读时
    read_xp_progress 的 xp_to_next 经 XP_TO_NEXT_LEVEL 倒查("0/4"→lv3),
    仍读不到才退期望曲线。"""
    import sr_od.application.currency_war.obs.cw_observation as cwo
    img = cv2_utils.read_image(str(FIXTURES / '后排7槽-佩佩局-拖测后.png'))
    # 等级区漏读(直读单一源 = read_level_raw_opt,patch 该缝)
    monkeypatch.setattr(cwo, 'read_level_raw_opt', lambda ctx, scr, level=None: None)
    got = cwo.read_level(test_context, img, 1, 1)
    assert got == 3, f'经验条反推应为 lv3(0/4),实得 {got}'
    # 经验条也漏(全黑)→ 退期望曲线(旧行为)
    monkeypatch.setattr(cwo, 'read_xp_progress', lambda ctx, scr, **kw: None)
    assert cwo.read_level(test_context, img, 1, 1) == cwo._expected_level(1, 1)


# ==================== test_star3_positions ====================

from sr_od.application.currency_war.kernel.cw_obs_core import _area_rect  # noqa: E402
from sr_od.application.currency_war.obs.cw_identity_obs import read_star  # noqa: E402

_SLOTS = [f'前排-{i}' for i in range(1, 5)] + [f'后排-{i}' for i in range(1, 7)] \
    + [f'备战栏-{i}' for i in range(1, 10)]
_FIX_DIR = _TEST_ROOT / 'screens' / 'star3_slots'


def _load_truth() -> dict[str, dict[str, int]] | None:
    p = _FIX_DIR / 'truth.json'
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding='utf-8'))


# (瘦身批 F1:原层1 test_star3_all_positions_read_3(19 张 fixture 目标位读 3)
#  是下层 test_star3_full_frame_truth 的严格真子集——同批 fixture、truth.json
#  含目标位真值(前排-1=3 等),层2 全 19 槽断言面 + 密度门完整辖定,已删,
#  省 19 次 webp 解码 + 19 次 read_star 的每全量重复支付。)


def test_star3_full_frame_truth(test_context: SrTestContext) -> None:
    """层2(全帧校验):每张 fixture 全部 19 槽位与真值表一致(361 校验点)。

    真值 = 采集时同帧其余槽位的真实星级(2星占位角色/1星/空槽 fallback=1)。
    防 read_star 在非 3 星槽上的回归(此前只测过目标位)。
    """
    sr_ctx = test_context
    truth = _load_truth()
    if truth is None:
        pytest.skip('truth.json 缺(先跑 star3_truth_gen.py)')
    fixes = sorted(_FIX_DIR.glob('*.webp'))
    assert fixes, 'star3_slots/ fixture 缺'
    rects = {s: _area_rect(sr_ctx, s, '货币战争-备战') for s in _SLOTS}
    checked = 0
    for fix in fixes:
        row = truth.get(fix.stem)
        assert row is not None, f'{fix.stem} 不在 truth.json'
        img = cv2_utils.read_image(str(fix))
        for slot, expected in row.items():
            rect = rects.get(slot)
            assert rect is not None, f'{slot} area 缺'
            got = read_star(img[rect.y1:rect.y2, rect.x1:rect.x2])
            assert got == expected, (
                f'{fix.stem}/{slot}: 真值 {expected} 实得 {got}(read_star 回归)')
            checked += 1
    assert checked >= 19 * 15, f'校验点异常少: {checked}(应≈361)'


# ===== 布局档对账·占用一致性仲裁(第四次停机批:deployed 身份残缺定谳)=====
# 事故:真板 7 格(公式 7 正确)但 CV 端点探针把「7 格档端点被占」读成
# 8 格 → 旧规采 CV → 8 格 rect 裁切错位 → SIFT 漏认 4/6 后排 → 换阵卖出
# 候选集残缺死锁。仲裁判别器 = paddle X − 前排占用 = 后排期望人数。

_BACK7_SCREEN = '货币战争-备战'
_BACK7_FIXTURE = 'deployed_r9_7grid'   # 停机哨兵帧入仓(真板 7/7:前台1+后排6)


def test_occupancy_arbitration_recovers_7grid(test_context, _layout_fresh, monkeypatch):
    """哨兵帧锁(15 号稿批 B 升级后语义):真板 7 格帧 → 选档 7 格。

    机制升级说明(锁语义重推,意图不变=「本帧必须按 7 格档运行」):
    点修批(占用一致性仲裁)依赖 paddle 读数;批 B 占用态门后本帧 CV 探针
    判 (slice, full) 混合形态 → 保守不可判 → 退公式值 7(diff=1,已建档,
    直读)。公式通道输入有 cap/level 防抖背书,哨兵帧由公式通道正确收口;
    佩佩局真 7 格帧的探针直读见 test_cv_channel_grid_counts(slice,slice→7)。"""
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    if not test_context.has_screen(_BACK7_SCREEN, _BACK7_FIXTURE):
        pytest.skip('fixture 缺:deployed_r9_7grid.webp')
    img = test_context.load_screen(_BACK7_SCREEN, _BACK7_FIXTURE)
    r = cbl.resolve_back_slots(test_context, img, level=6, cap=7)
    assert r['n'] == 7 and r['prefix'] == '后排7槽', r


def test_occupancy_arbitration_paddle_missing_formula_fallback(
        test_context, _layout_fresh, monkeypatch):
    """声明边界锁(批 B 信号②退化梯):paddle 失读 → 信号③弃权 →
    信号②结构证据梯:cv<formula(门后 CV 低读为下界,端点切片/失明非
    「无格」证据)→ 不否决有防抖背书的公式,采公式 7(旧点修批此帧
    n=8 是未门控 CV 误读;门后 CV 不再给出错误高读)。"""
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_observation as cwo
    if not test_context.has_screen(_BACK7_SCREEN, _BACK7_FIXTURE):
        pytest.skip('fixture 缺:deployed_r9_7grid.webp')
    img = test_context.load_screen(_BACK7_SCREEN, _BACK7_FIXTURE)
    monkeypatch.setattr(cwo, 'read_deployed_count', lambda ctx, scr: None)
    r = cbl.resolve_back_slots(test_context, img, level=6, cap=7)
    assert r['arb_n'] is None and r['n'] == 7, r


def test_signal2_ladder_cv_higher_wins_without_paddle(
        test_context, _layout_fresh, monkeypatch):
    """信号②退化梯·反向:cv>formula(两端整格存在 = (full,full) 结构证据)
    ∧ paddle 失读 → 采 CV 高档。桩面隔离(真帧 cv 通道独立于桩)。"""
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_observation as cwo
    img = object()   # cv 全桩,帧不参与
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda s: 8)
    monkeypatch.setattr(cwo, 'read_deployed_count', lambda c, s: None)
    r = cbl.resolve_back_slots(test_context, img, level=6, cap=6)
    assert r['arb_n'] is None and r['n'] == 8 and r['prefix'] == '后排8槽', r


def test_signal2_ladder_cv_lower_formula_wins_without_paddle(
        test_context, _layout_fresh, monkeypatch):
    """信号②退化梯·下界不否决:cv<formula(端点切片/失明非「无格」证据)
    ∧ paddle 失读 → 采公式(有 cap/level 防抖背书的一侧)。"""
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    import sr_od.application.currency_war.obs.cw_observation as cwo
    img = object()
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda s: 6)
    monkeypatch.setattr(cwo, 'read_deployed_count', lambda c, s: None)
    r = cbl.resolve_back_slots(test_context, img, level=6, cap=7)
    assert r['arb_n'] == 7 and r['n'] == 7 and r['prefix'] == '后排7槽', r


def test_deployed_identity_7grid_per_slot(test_context, templates):
    """逐槽身份锁(7 格档):定谳「档位漂移裁切错位」非「2★ 模板缺」——
    7 格档 rect 下 6 后排全认出,含 2★ 合成体藿藿(star=2 由金星计数独立
    读取,立绘模板与 1★ 同源即认)。槽 5 真空。"""
    from sr_od.application.currency_war.obs.cw_back_layout import (
        back_row_slot_rects_ctx,
    )
    from sr_od.application.currency_war.obs.cw_identity_obs import identify_slots
    if not test_context.has_screen(_BACK7_SCREEN, _BACK7_FIXTURE):
        pytest.skip('fixture 缺:deployed_r9_7grid.webp')
    img = test_context.load_screen(_BACK7_SCREEN, _BACK7_FIXTURE)
    slots = back_row_slot_rects_ctx(test_context, '后排7槽')
    chars = identify_slots(img, templates, slots, 'back',
                           min_inliers=15, live_only=True, center_gate=True)
    got = {c.slot: (c.char_id, c.star) for c in chars}
    assert got == {1: ('爻光', 1), 2: ('藿藿', 2), 3: ('星期日', 1),
                   4: ('黑塔', 1), 6: ('停云', 1), 7: ('忘归人', 1)}, got


def test_deployed_chars_7grid_full_recovery(test_context, templates, monkeypatch):
    """验收判据锁:留证帧 read_deployed_chars 认出数回到 7/7(前台 1 +
    后排 6),身份与真板一致——旧 8 格档口径此帧只认 3。"""
    import sr_od.application.currency_war.obs.cw_identity_obs as cio
    if not test_context.has_screen(_BACK7_SCREEN, _BACK7_FIXTURE):
        pytest.skip('fixture 缺:deployed_r9_7grid.webp')
    img = test_context.load_screen(_BACK7_SCREEN, _BACK7_FIXTURE)
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 6)
    import sr_od.application.currency_war.obs.cw_observation as cwo
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr, level=None: 7)
    chars = cio.read_deployed_chars(test_context, img, templates)
    assert len(chars) == 7, f'应 7/7,实得 {sorted(c.char_id for c in chars)}'
    assert {c.char_id for c in chars} == {
        '丹恒·饮月', '爻光', '藿藿', '星期日', '黑塔', '停云', '忘归人'}


# ===== 探针占用态门·C1 边界锁(落地审修订:半窗判据/擦线带分离)=====

def _mk_probe_frame(l_std: float, r_std: float) -> np.ndarray:
    """构 y 带探针窗合成帧:窗内左半/std=l_std、右半/std=r_std 的高斯噪声
    (y 带 600:739 全宽;探针只读窗内,其余填零)。三通道写**同一噪声**
    ——RGB→GRAY 是通道加权求和,各通道独立噪声会互相抵消使灰度 std 缩水
    (~0.67×),同噪写入保证合成 std==target。"""
    import numpy as _np
    frame = _np.zeros((1080, 1920, 3), dtype=_np.uint8)
    band = frame[600:739]

    def _fill(x1: int, x2: int, target: float) -> None:
        w = x2 - x1
        noise = _np.random.default_rng(42).normal(128, target, (139, w, 1))
        band[:, x1:x2] = _np.clip(noise, 0, 255).astype(_np.uint8)

    _fill(300, 464, l_std)
    _fill(464, 628, r_std)
    return frame


def test_probe_state_ambiguous_band_returns_none_conservative():
    """C1 边界①:整窗擦线(∈[6,12),如背景纹理帧 双半窗 std≈5)→ 不可判
    None 保守退公式——擦线态不再被强判 none/full(等价恢复旧 12 下界
    不可判带语义)。"""
    from sr_od.application.currency_war.obs.cw_back_layout import _probe_state
    # 双半窗 std≈5 → 整窗≈5 <6 → none 语义;此处锁擦线带:整窗≈8-9
    frame = _mk_probe_frame(8.0, 9.0)          # 整窗≈8.5 ∈ [6,12)
    assert _probe_state(frame, 464) is None
    frame2 = _mk_probe_frame(6.5, 10.5)        # 整窗≈8.6,不对称但落擦线带
    assert _probe_state(frame2, 464) is None


def test_probe_state_slice_never_misjudged_full():
    """C1 边界②:切片帧(不对称比 ≥2.5)恒判 slice 不得误 full——
    单半窗低 std(0.5-5)∧ 另半窗高 std(≥12)的强不对称形态,
    端点占用高估(切片→full→误 8)不可复现。"""
    from sr_od.application.currency_war.obs.cw_back_layout import (
        _PROBE_SLICE,
        _probe_state,
    )
    for l_std, r_std in ((3.0, 40.0), (5.0, 30.0), (2.0, 45.0), (40.0, 3.0),
                         (11.3, 60.1), (61.5, 2.1)):   # 后三项=真帧实测形态
        frame = _mk_probe_frame(l_std, r_std)
        got = _probe_state(frame, 464)
        assert got == _PROBE_SLICE, f'(l={l_std},r={r_std}) → {got} ≠ slice'


def test_probe_state_symmetric_full_and_flat_none():
    """对称高纹理(8 格整格形态,对称比 <2.5)→ full;纯平背景(6 格)
    → none;整窗高但极端不对称 → slice(与 full 的分界=对称比 2.5,
    8 格实测上限 1.2 / 7 格切片下限 5.3 的对数中点)。"""
    from sr_od.application.currency_war.obs.cw_back_layout import (
        _PROBE_FULL,
        _PROBE_NONE,
        _PROBE_SLICE,
        _probe_state,
    )
    assert _probe_state(_mk_probe_frame(45.0, 55.0), 464) == _PROBE_FULL
    assert _probe_state(_mk_probe_frame(2.0, 2.5), 464) == _PROBE_NONE
    assert _probe_state(_mk_probe_frame(10.0, 40.0), 464) == _PROBE_SLICE


# ==================== 15 号稿批 C 残余三件:公式净化 + 布局未知态(T-7) ====================
# 出处:docs/develop/currency_war/strategy-docs/
#       15_observation_multisource_arbitration.md §3.2①/§3.2④/§6 T-7/T-8
# (_layout_fresh 共享桩前导已上移至「select_back_layout 选档入口」节头,全家族共用。)


def test_formula_abstains_on_untrusted_level(_layout_fresh, monkeypatch):
    """§3.2① 公式输入净化:level_trusted=False(derived/启发式 level)→
    公式通道弃权(cap/level 齐备也不算 diff),n_raw 依 CV 单源;CV 也不可
    判 → 双弃权进未知态。「diff=0 退 6 档」的缺省化复发被本门封死。"""
    from sr_od.application.currency_war.obs import cw_back_layout as cbl
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: 7)
    r = cbl.resolve_back_slots(None, object(), level=8, cap=10,
                               level_trusted=False)
    assert r['formula_n'] is None and r['diff'] is None   # 公式弃权
    assert r['n_raw'] == 7 and r['n'] == 7                # CV 单源实测
    assert r['unknown'] is False


def test_level_trusted_none_keeps_legacy_behavior(_layout_fresh, monkeypatch):
    """§3.2① 三态之 None=未声明 → 零行为变更:diff=0 退 6 档基线
    (cap==level),formula 字段照旧产出。"""
    from sr_od.application.currency_war.obs import cw_back_layout as cbl
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: None)
    r = cbl.resolve_back_slots(None, object(), level=8, cap=8)
    assert r['diff'] == 0 and r['formula_n'] == 6 and r['n'] == 6
    assert r['unknown'] is False


def test_probe_residual_asymmetric_noise_absorbed():
    """§3.2② 残余形态裁决锁(证据裁决式):单端强不对称噪声(半窗纯平 +
    半窗强噪声 = 假 slice 形态)被**结构性吸收**——单端假 slice 与另端
    none 组合成未覆盖形态 → cv_back_slots 返 None 退公式。假 7 需两端同时
    slice = 两端都有的强结构证据,合成噪声单端形态不构成;三读防抖
    (§3.2② N=3)无须为此残余引入。"""
    from sr_od.application.currency_war.obs.cw_back_layout import (
        _PROBE_NONE,
        _PROBE_SLICE,
        _probe_state,
        cv_back_slots,
    )
    frame = _mk_probe_frame(2.0, 45.0)   # 左探针窗 = 极端切片形态
    assert _probe_state(frame, 464) == _PROBE_SLICE
    assert _probe_state(frame, 1458) == _PROBE_NONE   # 右端纯背景
    assert cv_back_slots(frame) is None   # 混合形态 → 不可判退公式


def test_unknown_single_frame_skip_with_jsonl_evidence(_layout_fresh,
                                                       monkeypatch):
    """T-7 单帧未知:双弃权 → n=None/prefix=''/unknown=True/frozen=False;
    每帧 JSONL 留证(obs_conflict 行 + back_layout_unknown 分键经
    cw_telemetry_exit 出口,缺省关→显式接桩)。"""
    from sr_od.application.currency_war.kernel import cw_telemetry_exit as exit_mod
    from sr_od.application.currency_war.obs import cw_back_layout as cbl
    defects: list[dict] = []
    monkeypatch.setattr(exit_mod, '_record_defect',
                        lambda **kw: defects.append(kw))
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: None)
    r = cbl.resolve_back_slots(None, object(), level=8, cap=10,
                               level_trusted=False)
    assert r['n'] is None and r['prefix'] == ''
    assert r['unknown'] is True and r['frozen'] is False
    assert r['unknown_streak'] == 1
    # obs_conflict JSONL 证据行(p = _layout_fresh 提供的 tmp journal 路径)
    p = _layout_fresh
    assert p.exists() and 'back_layout_unknown' in p.read_text(encoding='utf-8')
    # defects 分键(出口桩;kind 单一源=kernel.cw_telemetry_exit 常量)
    assert len(defects) == 1
    assert defects[0]['kind'] == exit_mod.DEFECT_KIND_BACK_LAYOUT_UNKNOWN


def test_unknown_freeze_after_three_known_frame_unfreezes(_layout_fresh,
                                                          monkeypatch):
    """T-7 连续 3 未知 → frozen=True(写类冻结止损,B3:N=3 与防抖同源);
    任一已知帧(公式/CV 干净裁决)→ 计数清零=解冻。"""
    from sr_od.application.currency_war.obs import cw_back_layout as cbl
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: None)
    for i in range(1, 4):
        r = cbl.resolve_back_slots(None, object(), level=8, cap=10,
                                   level_trusted=False)
        assert r['unknown'] is True
        assert r['frozen'] is (i >= cbl.UNKNOWN_FREEZE_FRAMES)
        assert r['unknown_streak'] == i
    # 干净裁决解冻:CV 恢复可判(CV 单源,公式仍弃权)
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: 6)
    r = cbl.resolve_back_slots(None, object(), level=8, cap=10,
                               level_trusted=False)
    assert r['unknown'] is False and r['n'] == 6
    assert cbl.back_layout_unknown_streak() == 0


def test_t7_read_side_single_frame_unknown_skips_back(_layout_fresh,
                                                      monkeypatch):
    """T-7 读面·单帧未知:read_deployed_chars 只读前排(identify_slots 仅
    front 一次调用);冻结帧 → 读类退 6 档基线继续读(back 按基线 6 槽)。"""
    from sr_od.application.currency_war.obs import cw_back_layout as cbl
    from sr_od.application.currency_war.obs import cw_identity_obs as cio
    calls: list[tuple[str, int]] = []

    def _fake_identify(screen, templates, slots, row, **kw):
        calls.append((row, len(slots)))
        return []
    monkeypatch.setattr(cio, 'identify_slots', _fake_identify)
    monkeypatch.setattr(cio, '_ctx_slots',
                        lambda ctx, prefix, count:
                        [(i, object()) for i in range(1, count + 1)])
    monkeypatch.setattr(cio, 'check_system_unit_layout', lambda *a, **k: None)
    monkeypatch.setattr(cbl, 'resolve_back_slots',
                        lambda ctx, scr, level=None, cap=None,
                        level_trusted=None: {
                            'unknown': True, 'frozen': False,
                            'n_raw': None, 'prefix': '', 'n': None,
                            'cv_n': None, 'cv_readings': None,
                            'cap': None, 'level': None, 'diff': None})
    ctx = object()
    cio.read_deployed_chars(ctx, object(), object())
    assert calls == [('front', 4)], f'单帧未知应只读前排,实得 {calls}'
    # 冻结帧:读类退 6 档基线
    calls.clear()

    def _frozen(ctx, scr, level=None, cap=None, level_trusted=None):
        return {'unknown': True, 'frozen': True, 'n_raw': None,
                'prefix': '', 'n': None, 'cv_n': None,
                'cv_readings': None, 'cap': None, 'level': None,
                'diff': None}
    monkeypatch.setattr(cbl, 'resolve_back_slots', _frozen)
    cio.read_deployed_chars(ctx, object(), object())
    assert [c for c in calls if c[0] == 'back'] == [( 'back', 6 )]


def test_t7_write_side_back_row_centers_unknown_empty(_layout_fresh,
                                                      monkeypatch):
    """T-7 写面·后排部署跳过:布局未知态(select_back_layout 返 (None,''))
    → _back_row_centers 返 [](后排部署无坐标可拖);可信位随调用透传。"""
    from sr_od.application.currency_war.obs import cw_back_layout as cbl
    from sr_od.application.currency_war.operations.cw_op import cw_op_deploy as db
    calls: list[tuple[object, ...]] = []

    def _fake_sel(ctx, scr, level=None, cap=None, level_trusted=None):
        calls.append((level, level_trusted))
        return None, ''
    monkeypatch.setattr(cbl, 'select_back_layout', _fake_sel)
    op = type('_Op', (db.CwOpDeploy,), {
        '__init__': lambda self: None,
        'last_screenshot': property(lambda self: object()),
    })()
    op.ctx = SimpleNamespace()   # 无 session → _level_trusted = None(未声明)
    assert op._back_row_centers() == []
    assert calls == [(None, None)]


def test_t7_write_side_reconcile_frozen_on_unknown(_layout_fresh,
                                                   monkeypatch):
    """T-7 写面·tracked 后排写入停:未知史在案(streak≥1)→
    _reconcile_tracking 整表对账跳过(screenshot 不被调 = 读链未进;
    防整表采新把 back 缺读写空 tracked);计数清零后恢复放行。"""
    from sr_od.application.currency_war.obs import cw_back_layout as cbl
    from sr_od.application.currency_war.operations.cw_op import cw_op_deploy as db
    op = type('_Op', (db.CwOpDeploy,), {
        '__init__': lambda self: None,
        'screenshot': lambda self: (_ for _ in ()).throw(
            AssertionError('冻结帧不得进入读链')),
    })()
    op.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=SimpleNamespace()))
    monkeypatch.setattr(cbl, '_unknown_streak', 1)
    op._reconcile_tracking(object())   # 不抛 = 门生效(screenshot 桩会炸)
    monkeypatch.setattr(cbl, '_unknown_streak', 0)
    with pytest.raises(AssertionError):
        op._reconcile_tracking(object())   # 已知帧:门放行,进入读链


def test_t8_level_single_source_readable_gate():
    """T-8(15 号稿 §6):合一后单一源 ``cw_identity_obs._session_level``——
    last_state.level_readable=False 时 state.level **不参与取大**
    (锁合一后输出语义;夹具=state 毒化值 8 vs 单调链 6)。"""
    from sr_od.application.currency_war.obs.cw_identity_obs import (
        _level_trusted,
        _session_level,
    )
    st = SimpleNamespace(level=8, level_readable=False)
    sess = SimpleNamespace(last_level_obs=6, last_state=st)
    ctx = SimpleNamespace(cw_match=SimpleNamespace(session=sess))
    assert _session_level(ctx) == 6
    assert _level_trusted(ctx) is False
    st.level_readable = True
    assert _session_level(ctx) == 8
    assert _level_trusted(ctx) is True
