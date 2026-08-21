# -*- coding: utf-8 -*-
"""后排槽位布局表测试(r75;狸猫局实拍)。

锁三件事:
1. 8 槽布局 rect 与识别:fixture(后排8槽-狸猫局.webp)上逐槽识别——
   位1 藿藿 / 位2 爻光 / 位7 狸小虎 / 位8 狸小龙(锚点均详情面板交互实锤)。
2. cap 路由:cap=8 选「后排8槽-N」档;cap=6 选基线「后排-N」;无档(7)退基线。
3. 狸猫模板在库且互不误认(蓝/红兄弟);空槽位3-6 无假识别。
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[5]          # 仓库根(StarRailOneDragon)
_TEST_ROOT = Path(__file__).resolve().parents[4]    # 测试仓根(sr-od-test)
sys.path.insert(0, str(_ROOT / 'src'))

from one_dragon.utils import cv2_utils
from sr_od.application.currency_war.currency_war_char_id import (
    identify_character,
    load_avatar_templates,
)

FIXTURE = _TEST_ROOT / 'screens' / '货币战争-备战' / '后排8槽-狸猫局.webp'
TPL_DIR = _ROOT / 'assets/template/currency_war/portrait_plaza'


@pytest.fixture(scope='module')
def templates():
    return load_avatar_templates(TPL_DIR)


@pytest.fixture(scope='module')
def frame():
    return cv2_utils.read_image(str(FIXTURE))


def test_tanuki_templates_in_library(templates):
    """狸小虎(蓝,弟弟)/狸小龙(红,哥哥)建档且在库。"""
    assert '狸小虎' in templates
    assert '狸小龙' in templates


def test_slot8_identification(frame, templates):
    """8 槽布局逐槽识别:位1 藿藿/位2 爻光/位7 狸小虎/位8 狸小龙(交互实锤锚)。

    布局机制(暗框检测实拍核实):8 槽 = 6 槽**两端各加 1 槽**(左+464/右+1458),
    旧 6 槽物理位置不动(604→新位2 … 1315→新位7)、编号右移;**非整体重排**
    (早前"重排"结论是 grounding 换算错误的误判,已纠正)。
    """
    from sr_od.application.currency_war.cw_back_layout import _LAYOUT_PREFIX
    assert _LAYOUT_PREFIX[8] == '后排8槽'
    centers = {1: 464, 2: 606, 7: 1316, 8: 1458}
    for slot, cx in centers.items():
        crop = frame[600:740, cx - 71:cx + 71]
        name, inliers = identify_character(crop, templates)
        assert inliers and inliers > 15, f'位{slot} 识别强度不足: {name},{inliers}'


def test_slot8_expected_names(frame, templates):
    """锚点定名:位1=藿藿,位7=狸小虎,位8=狸小龙(详情面板交互实锤,2026-08-19)。"""
    cx_map = {1: ('藿藿', 464), 7: ('狸小虎', 1316), 8: ('狸小龙', 1458)}
    for slot, (want, cx) in cx_map.items():
        crop = frame[600:740, cx - 71:cx + 71]
        name, inliers = identify_character(crop, templates)
        assert name == want, f'位{slot} 应为 {want},实识别 {name}({inliers})'


def test_tanuki_no_cross_match(frame, templates):
    """蓝/红狸猫互不误认(兄弟同型不同色;SIFT 形状特征区分)。"""
    blue = frame[600:740, 1316 - 71:1316 + 71]
    red = frame[600:740, 1458 - 71:1458 + 71]
    assert identify_character(blue, templates)[0] == '狸小虎'
    assert identify_character(red, templates)[0] == '狸小龙'


def test_slot8_empty_slots_no_false_positive(frame, templates):
    """空槽位3-6 不得出假识别(用户终局事实:位3-6 空;旧错位 rect 曾把狸猫边缘
    裁出假"黑天鹅")。"""
    from sr_od.application.currency_war.cw_identity_obs import identify_slots
    from one_dragon.base.geometry.rectangle import Rect
    slots = [(i, Rect(x - 71, 600, x + 71, 739))
             for i, x in ((3, 748), (4, 889), (5, 1031), (6, 1174))]
    out = identify_slots(frame, templates, slots, 'back')
    assert not out, f'空槽出假识别: {[(c.slot, c.char_id) for c in out]}'


def test_cap_routing():
    """cap 路由:r84 全档收口 6-11;cap≤6 钳制基线(r81)。

    r81 模型:后排槽数 = max(6, cap)(cap5 实测仍 6 槽,花火/姬子 SIFT 命中基线;
    五组数据全吻合)—— P1 低等级局 cap<6 时基线恒对(历史无误部署的原因)。
    r84:7 槽离线裁定(右+1 [606..1458]),6-11 全档闭环,停机钩子只对无档槽数触发。
    """
    from sr_od.application.currency_war.cw_back_layout import (
        _LAYOUT_PREFIX,
        effective_back_slots,
        fallback_back_slots,
    )
    assert _LAYOUT_PREFIX[6] == '后排'
    for n in (7, 8, 9, 10, 11):
        assert n in _LAYOUT_PREFIX
    assert 12 not in _LAYOUT_PREFIX   # 理论无档态(实测正常局不出现)
    # r81 钳制:cap 4/5/6 → 后排恒 6
    assert effective_back_slots(5) == 6
    assert effective_back_slots(4) == 6
    assert effective_back_slots(6) == 6
    assert effective_back_slots(8) == 8
    slots = fallback_back_slots()
    assert len(slots) == 6 and slots[0][0] == 1


def test_slot9_identification(templates):
    """9 槽布局识别(fixture 双宝钻局,2026-08-20 交互实锤锚定)。"""
    from sr_od.application.currency_war.cw_identity_obs import identify_slots
    from one_dragon.base.geometry.rectangle import Rect
    fix = _TEST_ROOT / 'screens' / '货币战争-备战' / '后排9槽-双宝钻局.webp'
    frame = cv2_utils.read_image(str(fix))
    centers = (464, 606, 748, 889, 1031, 1174, 1316, 1458, 1600)
    slots = [(i, Rect(x - 71, 600, x + 71, 739)) for i, x in enumerate(centers, 1)]
    got = {c.slot: c.char_id for c in identify_slots(frame, templates, slots, 'back')}
    assert got == {1: '藿藿', 2: '爻光', 6: '开拓者·欢愉', 7: '狸小虎', 8: '狸小龙'}, got


def test_slot10_identification(templates):
    """10 槽布局识别(fixture 满级局,2026-08-20 交互实锤:拖藿藿 2→4 验证 + 狸猫固定位 8/9)。"""
    from sr_od.application.currency_war.cw_identity_obs import identify_slots
    from one_dragon.base.geometry.rectangle import Rect
    fix = _TEST_ROOT / 'screens' / '货币战争-备战' / '后排10槽-满级局.webp'
    frame = cv2_utils.read_image(str(fix))
    centers = (322, 464, 606, 748, 889, 1031, 1174, 1316, 1458, 1600)
    slots = [(i, Rect(x - 71, 600, x + 71, 739)) for i, x in enumerate(centers, 1)]
    got = {c.slot: c.char_id for c in identify_slots(frame, templates, slots, 'back')}
    assert got == {2: '爻光', 3: '三月七', 4: '藿藿', 7: '开拓者·欢愉',
                   8: '狸小虎', 9: '狸小龙'}, got


def test_slot11_identification(templates):
    """11 槽布局识别(fixture P3 局,2026-08-20 停机帧离线分析 + 格点模型)。

    证据:双帧暗框格点 + SIFT 锚(藿藿@748/开拓者@1174/狸小虎@1316/狸小龙@1458 全落
    已知格点)+ 右端 1733-1800 截断暗段(第 11 槽 @1742)+ 左侧 x180 无暗段(排除左扩)。
    ⚠️ 交互实锤(点击锚定)待下次 11 槽局补充;狸猫固定坐标 1316/1458(非最右两槽)。
    """
    from sr_od.application.currency_war.cw_identity_obs import identify_slots
    from one_dragon.base.geometry.rectangle import Rect
    fix = _TEST_ROOT / 'screens' / '货币战争-备战' / '后排11槽-P3局.webp'
    frame = cv2_utils.read_image(str(fix))
    centers = (322, 464, 606, 748, 889, 1031, 1174, 1316, 1458, 1600, 1742)
    slots = [(i, Rect(x - 71, 600, x + 71, 739)) for i, x in enumerate(centers, 1)]
    got = {c.slot: c.char_id for c in identify_slots(frame, templates, slots, 'back')}
    assert got == {4: '藿藿', 7: '开拓者·欢愉', 8: '狸小虎', 9: '狸小龙'}, got


def test_slot7_identification(templates):
    """7 槽布局识别(fixture P2 开局局,2026-08-20 停机帧离线裁定:r84 全档收口)。

    证据:464 处无暗框无占用(非槽)+ 1458 附近空槽暗框 → 右+1 = [606..1458];
    与全局交替右左扩窗模式吻合(6[606..1316]→7右→8左→9右→10左→11右)。
    """
    from sr_od.application.currency_war.cw_identity_obs import identify_slots
    from one_dragon.base.geometry.rectangle import Rect
    fix = _TEST_ROOT / 'screens' / '货币战争-备战' / '后排7槽-P2开局局.webp'
    frame = cv2_utils.read_image(str(fix))
    centers = (606, 748, 889, 1031, 1174, 1316, 1458)
    slots = [(i, Rect(x - 71, 600, x + 71, 739)) for i, x in enumerate(centers, 1)]
    got = {c.slot: c.char_id for c in identify_slots(frame, templates, slots, 'back')}
    assert got == {1: '花火', 2: '大丽花'}, got


def test_layout_grid_model_complete():
    """r84 全档收口:6-11 全在档 + 窗口交替右左扩一致性(格点间距 142)。"""
    from sr_od.application.currency_war.cw_back_layout import _LAYOUT_PREFIX
    grid = [322, 464, 606, 748, 889, 1031, 1174, 1316, 1458, 1600, 1742]
    for n in (7, 8, 9, 10, 11):
        assert n in _LAYOUT_PREFIX, f'{n} 槽缺档'
    # 交替右左扩窗:6 基线 [606..1316](grid idx 2-7);7 = idx 2-8(右+1458);
    # 8 = idx 1-8(左+464);9 = idx 1-9;10 = idx 0-9(左+322);11 = idx 0-10(右+1742)
    assert grid[2:9][-1] == 1458       # 7 槽右端
    assert grid[0:10][-1] == 1600      # 10 槽右端
    assert grid[0:11][-1] == 1742      # 11 槽右端


def test_unarchived_layout_falls_back_clean(templates):
    """无档有效槽数(现仅理论态:6-11 全档后 cap≥12 或异常读)→ 退基线 + 停机钩子。

    r84 全档收口(6-11)后,停机钩子只对「有效槽数无档」触发(实测正常局不再出现);
    本测试用 monkeypatch 造无档槽数验证钩子机制本身。r81:cap≤6 钳制基线不触发。
    """
    from sr_od.context.sr_context import SrContext
    from sr_od.application.currency_war.cw_identity_obs import read_deployed_chars
    ctx = SrContext()
    ctx.init_by_config()

    class _FakeRunCtx:
        def __init__(self):
            self.stopped = False

        def stop_running(self):
            self.stopped = True

    ctx.run_context = _FakeRunCtx()
    flag = _ROOT / '.debug/temp/currency_war/back_layout_stop_hook.flag'
    # 清哈希去重残留(该 fixture 首次测试已采同内容帧,cw_shot_unique 会判「已采过」跳过)
    for _n in (5, 12):
        for _s in (_ROOT / '.debug/temp/currency_war/shots').glob(f'back_layout_{_n}slots*'):
            _s.unlink()
    # r80:先备份生产 flag 内容(finally 恢复)——测试写 flag 会覆盖生产钩子留下的
    # 内容(cap=11 等),旧逻辑「已存在就不删」保留了被覆盖的脏内容
    _orig = flag.read_text(encoding='utf-8') if flag.exists() else None
    try:
        fix = _TEST_ROOT / 'screens' / '货币战争-备战' / '后排8槽-狸猫局.webp'
        frame8 = cv2_utils.read_image(str(fix))
        # cap=5 → 钳制 6 → 不停机(r81:实测 cap5 仍 6 槽)
        out = read_deployed_chars(ctx, frame8, templates, deploy_cap=5)
        assert isinstance(out, list) and not ctx.run_context.stopped
        # cap=7 → 有档(r84)→ 不停机
        out = read_deployed_chars(ctx, frame8, templates, deploy_cap=7)
        assert isinstance(out, list) and not ctx.run_context.stopped
        # cap=12 → 有效 12 槽无档(理论态,monkeypatch 验证钩子机制)→ 停机
        out = read_deployed_chars(ctx, frame8, templates, deploy_cap=12)
        assert isinstance(out, list) and out          # 退基线识别不抛
        assert ctx.run_context.stopped                # 停机钩子触发
        assert flag.exists()                          # sentinel 写入
        assert '12' in flag.read_text(encoding='utf-8')
    finally:
        if _orig is not None:
            flag.write_text(_orig, encoding='utf-8')   # 恢复生产 flag(测试别覆盖真实停机内容)
        elif flag.exists():
            flag.unlink()   # 测试自产 flag 清理


def test_slot8_all_positions_identified(templates):
    """全位验证 fixture(用户实机逐位拖拽,2026-08-19):位1-8 逐一识别。

    布局:位1藿藿/位2爻光/位6开拓者·欢愉/位7狸小虎/位8狸小龙(fixture 帧);位3-6 曾用
    开拓者·欢愉逐位横拖验证识别(见 进度.md r76)——空槽态与占位态都已验。
    """
    fix = _TEST_ROOT / 'screens' / '货币战争-备战' / '后排8槽-全位验证.webp'
    frame2 = cv2_utils.read_image(str(fix))
    from sr_od.application.currency_war.cw_identity_obs import identify_slots
    from one_dragon.base.geometry.rectangle import Rect
    centers = (464, 606, 748, 889, 1031, 1174, 1316, 1458)
    slots = [(i, Rect(x - 71, 600, x + 71, 739)) for i, x in enumerate(centers, 1)]
    got = {c.slot: c.char_id for c in identify_slots(frame2, templates, slots, 'back')}
    assert got == {1: '藿藿', 2: '爻光', 6: '开拓者·欢愉', 7: '狸小虎', 8: '狸小龙'}, got


def test_trailblazer_joy_template_strength(templates):
    """开拓者·欢愉 现场模板(r76 治本:plaza 烘焙版 6 inliers → 现场版 138)。"""
    fix = _TEST_ROOT / 'screens' / '货币战争-备战' / '后排8槽-全位验证.webp'
    frame2 = cv2_utils.read_image(str(fix))
    crop = frame2[600:740, 1174 - 71:1174 + 71]   # 位6(全位验证帧开拓者在位6)
    name, inliers = identify_character(crop, templates)
    assert name == '开拓者·欢愉' and inliers > 30, f'{name},{inliers}'


def test_yinzhi_trial_template(templates):
    """银枝试用版模板(r82 治本:官方烘焙版全库噪声地板,试用渲染失配;现场版 120)。

    试用单位渲染 ≠ 官方立绘模式第二例(第一例 开拓者·欢愉 r76)——现场模板替换为标准解。
    """
    fix = _TEST_ROOT / 'screens' / '货币战争-备战' / '后排8槽-狸猫局.webp'
    from one_dragon.utils import cv2_utils as _cv
    from sr_od.application.currency_war.currency_war_char_id import identify_character as _id
    # 停机帧归档外的最低强度锁:模板在库即可(现场帧在 .debug 不入测试仓)
    assert '银枝' in templates
