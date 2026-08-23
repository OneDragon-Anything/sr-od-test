# -*- coding: utf-8 -*-
"""后排槽位布局表测试(ADR-0281 布局模型重审后重写,2026-08-23)。

锁六件事:
1. 8 格档识别:狸猫局/全位验证/双宝钻局(cap9!)/满级局(cap10!)/P3局(cap11!)
   —— 旧 9/10/11 档三帧**实为同一个 8 格布局**(393-1529 带,空槽签名终判),
   全部按 8 格档锁(新模型最强证据:cap9/10/11 局狸猫恒在 1316/1458)。
2. level 路由:lv3/5→6 / lv7、lv8→8 / lv6→保守 6+待采;cap 与布局无关。
3. 幻影档不存在:_LAYOUT_PREFIX 只含 {6,8};yml(源+merged)无 后排7/9/10/11槽 area。
4. lv6 待采留证(back_7slots_pending)。
5. 系统单位恒最右布局自检(layout_mismatch_by_system_unit):对/错档两态。
6. deploy 剔除系统单位(exclude_system_units)。
"""
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[5]          # 仓库根(StarRailOneDragon)
_TEST_ROOT = Path(__file__).resolve().parents[4]    # 测试仓根(sr-od-test)
sys.path.insert(0, str(_ROOT / 'src'))

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils
from sr_od.application.currency_war.cw_identity_obs import (
    check_system_unit_layout,
    identify_slots,
)
from sr_od.application.currency_war.currency_war_char_id import (
    identify_character,
    load_avatar_templates,
)

FIXTURES = _TEST_ROOT / 'screens' / '货币战争-备战'
TPL_DIR = _ROOT / 'assets/template/currency_war/portrait_plaza'
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


# ===== 1. 8 格档识别(含旧 9/10/11 触发帧回归到 8 格档) =====

def test_tanuki_templates_in_library(templates):
    """狸小虎(蓝,弟弟)/狸小龙(红,哥哥)建档且在库。"""
    assert '狸小虎' in templates
    assert '狸小龙' in templates


def test_slot8_identification(frame, templates):
    """8 槽布局逐槽识别:位1 藿藿/位2 爻光/位7 狸小虎/位8 狸小龙(交互实锤锚)。"""
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


# ===== 旧 9/10/11 档触发帧 → 按 8 格档锁(ADR-0281 核心证据) =====

def test_cap9_frame_is_8grid(templates):
    """双宝钻局(cap9/lv7)帧按 8 格档识别(旧「9槽」档是幻影)。

    旧 9 槽格点前 8 格与 8 格档完全同位(464..1458)——即旧「9 槽实证」的
    全部命中本就落在 8 格布局内,第 9 格(1600)是背景(空槽签名终判)。
    """
    fix = cv2_utils.read_image(str(FIXTURES / '后排9槽-双宝钻局.webp'))
    got = {c.slot: c.char_id for c in identify_slots(fix, templates, _slots8(), 'back')}
    assert got == {1: '藿藿', 2: '爻光', 6: '开拓者·欢愉', 7: '狸小虎', 8: '狸小龙'}, got


def test_cap10_frame_is_8grid(templates):
    """满级局(cap10/lv8)帧按 8 格档识别(旧「10槽」档是幻影)。"""
    fix = cv2_utils.read_image(str(FIXTURES / '后排10槽-满级局.webp'))
    got = {c.slot: c.char_id for c in identify_slots(fix, templates, _slots8(), 'back')}
    assert got == {1: '爻光', 2: '三月七', 3: '藿藿', 6: '开拓者·欢愉',
                   7: '狸小虎', 8: '狸小龙'}, got


def test_cap11_frame_is_8grid(templates):
    """P3 局(cap11/lv8)帧按 8 格档识别(旧「11槽」档是幻影)。

    三触发帧狸猫恒在 1316/1458(=8 格档位7/8,恒最右模型)——与「7/9/10/11
    全是幻影」双源交叉实证(cap 与布局无关)。
    """
    fix = cv2_utils.read_image(str(FIXTURES / '后排11槽-P3局.webp'))
    got = {c.slot: c.char_id for c in identify_slots(fix, templates, _slots8(), 'back')}
    assert got == {3: '藿藿', 6: '开拓者·欢愉', 7: '狸小虎', 8: '狸小龙'}, got


# ===== 2/3. level 路由 + 幻影档不存在 =====

def test_level_routing():
    """ADR-0281:后排槽数 level 驱动 —— lv≤5→6 / lv≥7→8 / lv6→保守 6(待采)。

    cap(宝钻叠加)与布局无关:两帧同 lv7 cap8/9 同为 8 格实证。
    """
    from sr_od.application.currency_war.cw_back_layout import (
        _LAYOUT_PREFIX,
        _PENDING_7SLOT_LEVELS,
        effective_back_slots,
        fallback_back_slots,
    )
    # 幻影档不存在(7/9/10/11 是循环论证产物,已删)
    assert set(_LAYOUT_PREFIX) == {6, 8}
    assert _LAYOUT_PREFIX[6] == '后排'
    assert _LAYOUT_PREFIX[8] == '后排8槽'
    for n in (7, 9, 10, 11, 12):
        assert n not in _LAYOUT_PREFIX
    # level 路由
    assert effective_back_slots(3) == 6
    assert effective_back_slots(4) == 6
    assert effective_back_slots(5) == 6
    assert effective_back_slots(6) == 6       # 7 格存在性待采 → 保守 6
    assert effective_back_slots(7) == 8
    assert effective_back_slots(8) == 8
    assert _PENDING_7SLOT_LEVELS == frozenset({6})
    slots = fallback_back_slots()
    assert len(slots) == 6 and slots[0][0] == 1


def test_phantom_layouts_absent_from_yml():
    """yml(源 + merged)不再有 后排7/9/10/11槽 area(幻影档清除,源与派生层同步)。"""
    for rel in ('assets/game_data/screen_info/currency_war_battle_prep.yml',
                'assets/game_data/screen_info/_od_merged.yml'):
        txt = (_ROOT / rel).read_text(encoding='utf-8')
        for pfx in ('后排7槽', '后排9槽', '后排10槽', '后排11槽'):
            assert pfx not in txt, f'{rel} 残留幻影档 {pfx}'
        assert '后排8槽-1' in txt and '后排-1' in txt, f'{rel} 缺 6/8 真值档'


# ===== 4. lv6 待采留证 =====

def test_lv6_pending_note(tmp_path, monkeypatch, frame):
    """lv6 → note_pending_7slots 留证 back_7slots_pending(节流;非 lv6 不触发)。"""
    import sr_od.application.currency_war.cw_back_layout as cbl
    import sr_od.application.currency_war.cw_observe as cobs
    monkeypatch.setattr(cobs, '_CONFLICT_JOURNAL', tmp_path / 'obs.jsonl')
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cbl, '_pending_note_ts', {})
    cbl.note_pending_7slots(frame, 6, 'test')
    lines = (tmp_path / 'obs.jsonl').read_text(encoding='utf-8').strip().splitlines()
    assert lines and json.loads(lines[-1])['field'] == 'back_7slots_pending'
    # 非 lv6 不触发
    cbl.note_pending_7slots(frame, 7, 'test')
    assert len((tmp_path / 'obs.jsonl').read_text(encoding='utf-8').strip().splitlines()) == 1


# ===== 5. 系统单位恒最右布局自检 =====

def test_system_unit_layout_check_ok(tmp_path, monkeypatch, frame, templates):
    """对档(8 格档,狸猫在位7/8)→ 无 layout_mismatch 留证。"""
    import sr_od.application.currency_war.cw_identity_obs as cio
    import sr_od.application.currency_war.cw_observe as cobs
    journal = tmp_path / 'obs.jsonl'
    monkeypatch.setattr(cobs, '_CONFLICT_JOURNAL', journal)
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cio, '_sysunit_conflict_ts', {})
    from sr_od.application.currency_war.cw_state import BenchChar
    chars = [BenchChar(slot=7, char_id='狸小虎'), BenchChar(slot=8, char_id='狸小龙')]
    cio.check_system_unit_layout(frame, chars, _slots8(), templates, source='test')
    assert not journal.exists() or 'layout_mismatch_by_system_unit' not in journal.read_text(encoding='utf-8')


def test_system_unit_layout_check_mismatch(tmp_path, monkeypatch, frame, templates):
    """错档(狸猫实测 x≈1316/1458 vs 所选档右格 1174)→ layout_mismatch_by_system_unit 留证。"""
    import sr_od.application.currency_war.cw_identity_obs as cio
    import sr_od.application.currency_war.cw_observe as cobs
    journal = tmp_path / 'obs.jsonl'
    monkeypatch.setattr(cobs, '_CONFLICT_JOURNAL', journal)
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cio, '_sysunit_conflict_ts', {})
    from sr_od.application.currency_war.cw_state import BenchChar
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
    from sr_od.application.currency_war.cw_state import BenchChar
    from sr_od.application.currency_war.operations.prep.deploy_bench import (
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


# ===== 停机钩子机制(level 对应档无档;现 6/8 都有档,模拟补档窗口态) =====

def test_layout_hook_fires_only_when_level_profile_missing(
        test_context, templates, monkeypatch, tmp_path):
    """ADR-0281:停机条件 = level 对应档无档(正常 6/8 都有档 → 永不触发);
    monkeypatch 摘掉 8 档模拟「补档窗口」验证钩子机制本身。lv6 走留证不停机。

    ⚠️ run_context 替换必须走 monkeypatch(自动还原;session 级 ctx 裸赋值污染
    后续测试,实锤见旧版注释)。
    """
    import sr_od.application.currency_war.cw_back_layout as cbl
    import sr_od.application.currency_war.cw_identity_obs as cio
    import sr_od.application.currency_war.cw_obs_core as core
    import sr_od.application.currency_war.cw_observe as cobs
    ctx = test_context

    class _FakeRunCtx:
        def __init__(self):
            self.stopped = False
            self.stop_source = ''

        def stop_running(self, reason: str = ''):
            self.stopped = True
            self.stop_source = reason

    monkeypatch.setattr(ctx, 'run_context', _FakeRunCtx())
    monkeypatch.setattr(core, 'is_prep_like_frame', lambda c, s: True)
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cobs, '_CONFLICT_JOURNAL', tmp_path / 'obs.jsonl')
    monkeypatch.setattr(cio, '_sysunit_conflict_ts', {})
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.debug/temp/currency_war').mkdir(parents=True, exist_ok=True)
    frame8 = cv2_utils.read_image(str(FIXTURES / '后排8槽-狸猫局.webp'))

    # 正常态:lv5/lv7 都有档 → 不停机
    cio.read_deployed_chars(ctx, frame8, templates, level=5)
    assert not ctx.run_context.stopped
    cio.read_deployed_chars(ctx, frame8, templates, level=7)
    assert not ctx.run_context.stopped
    # lv6 → 留证不停机(保守 6 格跑)
    cio.read_deployed_chars(ctx, frame8, templates, level=6)
    assert not ctx.run_context.stopped
    assert 'back_7slots_pending' in (tmp_path / 'obs.jsonl').read_text(encoding='utf-8')
    # 补档窗口态(8 档被摘)→ lv7 停机 + flag
    monkeypatch.setattr(cbl, '_LAYOUT_PREFIX', {6: '后排'})
    out = cio.read_deployed_chars(ctx, frame8, templates, level=7)
    assert isinstance(out, list) and out          # 退基线识别不抛
    assert ctx.run_context.stopped                # level 对应档无档 → 停机
    assert (tmp_path / '.debug/temp/currency_war/back_layout_stop_hook.flag').exists()
