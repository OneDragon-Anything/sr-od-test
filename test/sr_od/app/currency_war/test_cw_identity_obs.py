"""货币战争 视觉身份观测测试(cw_identity_obs)。

- 纯单元:``resolve_char_name``(avatar_id → 规范名)。
- 集成:``identify_slots`` / ``read_deployed_chars`` 对实机 fixture(``deployed_p1r9.webp``)
  → 前排 4 角色身份。证明 ``character_avatar`` 脸近景库对备战半身立绘可匹配(D-75)。
"""
from __future__ import annotations

import inspect

import pytest

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils, file_utils
from sr_od.application.currency_war.currency_war_char_id import load_avatar_templates
from sr_od.application.currency_war.cw_identity_obs import (
    identify_slots,
    read_deployed_chars,
    read_star,
    resolve_char_name,
)
from sr_od.context.sr_context import SrContext
from test.conftest import SrTestContext

# character_avatar 脸库在主仓 assets/(sr_od 所在 repo 根;同 conftest.application_plugin_dirs 定位法)
_REPO_ROOT = file_utils.find_src_dir(inspect.getfile(SrContext)).parent
_AVATAR_DIR = _REPO_ROOT / 'assets' / 'template' / 'character_avatar'


def test_resolve_char_name_basic() -> None:
    """avatar_id(主游英文 id)→ 货币战争规范名(直接命中 roster)。"""
    assert resolve_char_name('pela') == '佩拉'
    assert resolve_char_name('herta') == '黑塔'
    assert resolve_char_name('saber') == 'Saber'
    assert resolve_char_name('huohuo') == '藿藿'


def test_resolve_char_name_unknown() -> None:
    """avatar_id 不在主游角色表 → None。"""
    assert resolve_char_name('nonexistent_xyz') is None


@pytest.fixture(scope='module')
def avatar_templates():
    """加载 character_avatar 脸库(预计算 SIFT 关键点/描述子);模块内复用。"""
    return load_avatar_templates(_AVATAR_DIR)


def test_identify_deployed_front_row(test_context: SrTestContext, avatar_templates) -> None:
    """identify_slots:实机 fixture(deployed_p1r9)前排 4 槽 → [佩拉,黑塔,Saber,藿藿]。

    硬编码 yml rect(ground truth);D-75 证脸库可匹配备战半身立绘(4/4 强命中)。后排空(VLM 计数
    幻觉,实际无后排部署)→ 不在该断言内。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_p1r9'):
        pytest.skip('fixture deployed_p1r9.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_p1r9')
    front = [(i, Rect(*r)) for i, r in enumerate([
        [677, 329, 810, 467], [823, 329, 951, 467],
        [969, 329, 1097, 467], [1109, 329, 1241, 467]], start=1)]
    chars = identify_slots(screen, avatar_templates, front, 'front')
    assert [c.char_id for c in chars] == ['佩拉', '黑塔', 'Saber', '藿藿']
    assert all(c.position_pref == 'front' for c in chars)


def test_read_deployed_chars_via_ctx(test_context: SrTestContext, avatar_templates) -> None:
    """read_deployed_chars:经 ctx.screen_info 取槽位 rect → 前排 4 角色身份(集成,验 screen_info 接线)。

    与 ``test_identify_deployed_front_row`` 互补:前者硬编码 rect 测纯 CV 核心,本测经 ctx screen_loader
    取 rect(= ``_ctx_slots``),验 screen_info area 名(前排-1..4 / 后排-1..6)接线正确。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_p1r9'):
        pytest.skip('fixture deployed_p1r9.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_p1r9')
    chars = read_deployed_chars(test_context, screen, avatar_templates)
    front = [c.char_id for c in chars if c.position_pref == 'front']
    assert front == ['佩拉', '黑塔', 'Saber', '藿藿']
    # 后排空(fixture 该态无后排部署;VLM 曾幻觉"1 个后排",实为空)
    assert [c for c in chars if c.position_pref == 'back'] == []


def test_read_star_front_row_1star(test_context: SrTestContext) -> None:
    """read_star:deployed_p1r9 前排 4 槽(佩拉/黑塔/Saber/藿藿,早期 round → 1 星)→ read_star 都=1。

    金星计数(立绘底部金色**四角星** ✦,ADR-0114 TM 法)。1星各槽稳读 1;
    2星见 ``test_read_star_2star_positions``(各位置覆盖)。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_p1r9'):
        pytest.skip('fixture deployed_p1r9.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_p1r9')
    # 前排-1..4 rect(同 test_identify_deployed_front_row ground truth)= 采 star_front_1..4 的槽位
    front_rects = [Rect(*r) for r in [
        [677, 329, 810, 467], [823, 329, 951, 467],
        [969, 329, 1097, 467], [1109, 329, 1241, 467]]]
    for r in front_rects:
        assert read_star(screen[r.y1:r.y2, r.x1:r.x2]) == 1, f'前排槽 {r} 应为 1 星(1 个金星)'


def test_read_star_2star_positions(test_context: SrTestContext) -> None:
    """read_star TM:deployed_2star(3 个 2星 + 1星对照)→ 前排-3/后排-3/备战栏-4 读 2,备战栏-1 读 1。

    ADR-0114(2026-08-13):TM + V>150 滤暗金衣服 + thresh 0.50。**前排-3** = 衣服淹没 case(暗金衣服
    V80-150,V>150 滤);**后排-3** = 第2星 val0.511(thresh 0.50 解,原 0.55 漏);备战栏-4 = 2星紧贴。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_2star'):
        pytest.skip('fixture deployed_2star.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_2star')
    assert read_star(screen[329:467, 969:1097]) == 2, '前排-3 应为 2 星(衣服淹没 case,V>150 解)'
    assert read_star(screen[600:739, 823:953]) == 2, '后排-3 应为 2 星(thresh 0.50:第2星 val0.511)'
    assert read_star(screen[845:979, 757:869]) == 2, '备战栏-4 应为 2 星(紧贴 TM 分离)'
    assert read_star(screen[845:979, 382:495]) == 1, '备战栏-1 应为 1 星(对照,不回归)'


def test_read_star_2star_all_slots_multifixture(test_context: SrTestContext) -> None:
    """read_star:**全 19 槽 2★ 读 2**(3 个 2★ 角色同时布阵,多 fixture 覆盖各槽)。

    用 DragCwChar op 把飞霄/万敌/椒丘(均 2★)同时布到 3 个不同槽 → 一张 fixture 验 3 个 2★ 槽。
    跨多 fixture 覆盖前排 1-4 / 后排 1-6 / 备战 1-9 全部 2★(各槽 read_star=2,thresh 0.45,ADR-0114/0116)。
    缺 fixture 的项跳过(采到后自动恢复)。配合 ``test_read_star_edge_slots_2star``(边槽)+ 本测(中段/跨排)
    = 2★ 全槽覆盖。
    """
    # (fixture, [(槽位, [x1,y1,x2,y2]), ...]) —— 每 fixture 3 个 2★ 同时在阵
    cases: list[tuple[str, list[tuple[str, list[int]]]]] = [
        ('deployed_2star_3rows',    [('前排-4', [1109, 329, 1241, 467]), ('后排-6', [1245, 600, 1386, 739]), ('备战栏-3', [632, 844, 743, 978])]),
        ('deployed_2star_3rows_b',  [('前排-2', [823, 329, 951, 467]),  ('后排-4', [967, 600, 1097, 739]), ('备战栏-5', [882, 846, 995, 980])]),
        ('deployed_2star_3rows_c',  [('后排-2', [679, 600, 814, 739]),  ('后排-4', [967, 600, 1097, 739]), ('备战栏-6', [1004, 847, 1118, 978])]),
        ('deployed_2star_bench7',   [('备战栏-7', [1132, 846, 1244, 977])]),
        ('deployed_2star_bench8',   [('备战栏-8', [1256, 845, 1368, 979])]),
        ('deployed_2star_bench2',   [('备战栏-2', [507, 844, 620, 978])]),
    ]
    ran = False
    for fx, slots in cases:
        if not test_context.has_screen('货币战争-备战', fx):
            continue
        ran = True
        screen = test_context.load_screen('货币战争-备战', fx)
        for label, (x1, y1, x2, y2) in slots:
            assert read_star(screen[y1:y2, x1:x2]) == 2, f'{fx} {label} 应为 2★'
    if not ran:
        pytest.skip('multi-fixture 未采(2★ 全槽覆盖用)')


def test_read_star_all_rows_2star_full(test_context: SrTestContext) -> None:
    """read_star:deployed_2star_full → 前排/后排/备战栏**三行各覆盖 1★+2★**(各位置广覆盖)。

    单 fixture 同时含三行 × {1,2} 星(ground truth = 实机 analyze extras 双证):前排-3 花火 1★ /
    前排-4 万敌 2★;后排-1 三月七 1★ / 后排-3 椒丘 2★;备战栏 多 1★ + 备战-4 飞霄 2★ + 备战-8 万敌 1★
    (万敌同名异星:2★ 上阵 vs 1★ 备战,证 read_star 看立绘金星非角色身份)。与 ``test_read_star_2star_positions``
    (deployed_2star,各行的**最难单 case**:衣服淹没/thresh/紧贴)互补:本测广覆盖各行多槽位,证 read_star
    对**不同 crop 尺寸**(前排 133×138 / 后排 141×139 / 备战 113×134)的 1★(单星)与 2★(双星)均准。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_2star_full'):
        pytest.skip('fixture deployed_2star_full.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_2star_full')
    # 前排(crop 133×138):1★ + 2★
    assert read_star(screen[329:467, 969:1097]) == 1, '前排-3 花火 1★'
    assert read_star(screen[329:467, 1109:1241]) == 2, '前排-4 万敌 2★'
    # 后排(crop 141×139):1★ + 2★
    assert read_star(screen[600:739, 534:675]) == 1, '后排-1 三月七 1★'
    assert read_star(screen[600:739, 823:953]) == 2, '后排-3 椒丘 2★'
    # 备战栏(crop 113×134):多 1★ + 2★ + 同名异星对照
    assert read_star(screen[845:979, 382:495]) == 1, '备战-1 艾丝妲 1★'
    assert read_star(screen[844:978, 507:620]) == 1, '备战-2 黑塔 1★'
    assert read_star(screen[844:978, 632:743]) == 1, '备战-3 艾丝妲 1★'
    assert read_star(screen[845:979, 757:869]) == 2, '备战-4 飞霄 2★'
    assert read_star(screen[846:980, 882:995]) == 1, '备战-5 阿格莱雅 1★'
    assert read_star(screen[847:978, 1004:1118]) == 1, '备战-6 赛飞儿 1★'
    assert read_star(screen[846:977, 1132:1244]) == 1, '备战-7 乱破 1★'
    assert read_star(screen[845:979, 1256:1368]) == 1, '备战-8 万敌 1★(同名异星对照,非 2★)'


def test_read_star_bench9_edge_2star(test_context: SrTestContext) -> None:
    """read_star:deployed_2star_bench9 → 备战-9 飞霄 2★ 读 2(**边槽 circ 边界 case,ADR-0115**)。

    备战-9(最右槽)把飞霄两颗金星之一渲染得偏高 → 该金星 circ 落到 0.34(原 circ>0.35 阈下)被误拒
    → 旧代码读 1(假阴)。``_STAR_CIRC_MIN`` 放宽到 0.25 后读回 2。同 fixture 后排-3 椒丘 / 后排-5 万敌
    亦 2★(对照,非边槽不受影响)。这是「备战每个槽位都要覆盖」发现的边槽回归 —— 锁回归测试。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_2star_bench9'):
        pytest.skip('fixture deployed_2star_bench9.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_2star_bench9')
    assert read_star(screen[600:739, 823:953]) == 2, '后排-3 椒丘 2★(对照)'
    assert read_star(screen[600:739, 1106:1241]) == 2, '后排-5 万敌 2★(对照)'
    assert read_star(screen[844:980, 1379:1493]) == 2, '备战-9 飞霄 2★(边槽 circ 边界,ADR-0115 解)'


def test_read_star_edge_slots_2star(test_context: SrTestContext) -> None:
    """read_star:**各排边槽** 2★ 读 2(左右边槽 + 不同角色;用 DragCwChar op 拖到边槽采的 fixture)。

    覆盖 ADR-0115 后的边槽鲁棒性(不同角色 / 不同排的左右边槽):
    - 备战-1(飞霄,最**左**槽)← deployed_2star_bench1(对照 deployed_2star_bench9 最右槽)
    - 前排-1(万敌,左槽)/ 前排-4(万敌,右槽)← deployed_2star_front1 / front4(前排 2★ 边槽)
    每排左右边槽 + 中心(deployed_2star_full)+ 备战-9 bug 槽 → 各排边槽 2★ 全覆盖。
    """
    # 备战-1 左边槽(飞霄 2★)
    if test_context.has_screen('货币战争-备战', 'deployed_2star_bench1'):
        s = test_context.load_screen('货币战争-备战', 'deployed_2star_bench1')
        assert read_star(s[845:979, 382:495]) == 2, '备战-1 飞霄 2★(左边槽)'
    # 前排-1 左槽 + 前排-4 右槽(万敌 2★,跨排 deployed→deployed 拖到)
    if test_context.has_screen('货币战争-备战', 'deployed_2star_front1'):
        s = test_context.load_screen('货币战争-备战', 'deployed_2star_front1')
        assert read_star(s[329:467, 677:810]) == 2, '前排-1 万敌 2★(左槽)'
    if test_context.has_screen('货币战争-备战', 'deployed_2star_front4'):
        s = test_context.load_screen('货币战争-备战', 'deployed_2star_front4')
        assert read_star(s[329:467, 1109:1241]) == 2, '前排-4 万敌 2★(右槽)'
    # 后排-1 左槽(椒丘)/ 后排-6 右槽(椒丘,**边槽第2星 TM 偏低 bug,ADR-0116**)
    if test_context.has_screen('货币战争-备战', 'deployed_2star_back1'):
        s = test_context.load_screen('货币战争-备战', 'deployed_2star_back1')
        assert read_star(s[600:739, 534:675]) == 2, '后排-1 椒丘 2★(左槽)'
    if test_context.has_screen('货币战争-备战', 'deployed_2star_back6'):
        s = test_context.load_screen('货币战争-备战', 'deployed_2star_back6')
        assert read_star(s[600:739, 1245:1386]) == 2, '后排-6 椒丘 2★(右槽,第2星 TM val~0.45-0.50,ADR-0116 thresh 0.45 解)'


# character_cw_portrait 立绘库(主仓 assets/,71 角色 <name>/raw.png)
_PORTRAIT_DIR = _REPO_ROOT / 'assets' / 'template' / 'character_cw_portrait'


def test_read_star_portrait_library_no_false_positive() -> None:
    """read_star:立绘库 71 张 → **全部读 1(无 >1 误判)**,即 ADR-0114/0115「立绘库 0/71」回归守卫。

    **立绘库无星级 UI 金星**(是 SIFT 身份模板 ``<name>/raw.png`` 半身立绘艺术,非游戏截图)—— 但立绘本身
    带金色衣服 / 装饰:实测 58/71 全图有金像素、5/71 底部带金块 TM≥thresh 触发计数路径(Momojie 被
    aspect 拒 / 千冶·刃 单金块过形状算 1 / 余 TM 低不计数)。因**没有任何立绘含 ≥2 个过形状的金块**,
    read_star 全读 1(≥1 fallback:角色必有星,read_star 设计上不返 0)。

    故本测守的是**「装饰误判成多星」**(false positive:>1),**不**测真金星计数(真星在 ``deployed_*``
    fixture 测)。改 read_star 阈值(area/aspect/circ/V/thresh/region)后,若衣服装饰被数成 2+ 星 → 本测
    挡住。0/71 不靠 circ(area+aspect+V>150+TM 已挡死),故本测也间接证 circ 放宽(ADR-0115)安全。
    """
    portraits = sorted(_PORTRAIT_DIR.glob('*/raw.png'))
    if not portraits:
        pytest.skip(f'立绘库目录无模板:{_PORTRAIT_DIR}')
    violators: list[str] = []
    for p in portraits:
        img = cv2_utils.read_image(str(p))
        if img is None:
            violators.append(f'{p.parent.name}(读图失败)')
            continue
        n = read_star(img)
        if n != 1:
            violators.append(f'{p.parent.name}={n}')
    assert not violators, f'立绘库 read_star 误判(应全 1):{violators}'
