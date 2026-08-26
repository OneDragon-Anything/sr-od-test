"""后排槽位布局表测试(W209/ADR-0385 cap 差公式勘误后重写,2026-08-26)。

锁六件事:
1. 8 格档识别:狸猫局/全位验证/双宝钻局(cap9!)/满级局(cap10!)/P3局(cap11!)
   —— 旧 9/10/11 档三帧**实为同一个 8 格布局**(393-1529 带,空槽签名终判),
   全部按 8 格档锁(口述公式自洽:cap9/10/11 的 lv7/8 局 diff≥2 全落 8 格)。
2. cap 差公式路由(ADR-0385 口述「后台格数 = 6+(cap−level)」):
   diff 0 → 6 / diff≥2 → 8 / diff==1(7 格未建档)→ 保守 8 格超集 + 留证;
   **level 单独不再参与选档**(run 26 lv8 无召唤物局恒 6 格 = 崩坏根因①反向锚)。
3. 幻影档不存在:_LAYOUT_PREFIX 只含 {6,8};yml(源+merged)无 后排7/9/10/11槽 area。
4. 7 格待采留证(back_7slots_pending,口述公式 diff==1 态)。
5. 系统单位恒最右布局自检(layout_mismatch_by_system_unit):对/错档两态
   (ADR-0385 保留作公式选档的交叉验证网)。
6. deploy 剔除系统单位(exclude_system_units)+ off-target 卖出熔断
   (run 26 崩坏根因②,W209/ADR-0386,见 test_cw_w209_offtarget_sell_guard)。
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
from sr_od.application.currency_war.currency_war_char_id import (
    identify_character,
    load_avatar_templates,
)
from sr_od.application.currency_war.cw_identity_obs import (
    identify_slots,
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


# ===== 2/3. cap 差公式路由 + 幻影档不存在 =====

def test_cap_diff_routing():
    """W209/ADR-0385 口述公式「后台格数 = 6+(cap−level)」路由:
    diff0→6 / diff≥2→8 / diff==1(7 格未建档)→保守 8 格超集;
    diff<0(读错族)按 0;diff>2(域外)按 2。level 单独不参与。"""
    from sr_od.application.currency_war.cw_back_layout import (
        _LAYOUT_PREFIX,
        back_slots_from_cap_diff,
        fallback_back_slots,
    )
    # 幻影档不存在(7/9/10/11 是循环论证产物,已删;7 待 diff==1 局实拍补档)
    assert set(_LAYOUT_PREFIX) == {6, 8}
    assert _LAYOUT_PREFIX[6] == '后排'
    assert _LAYOUT_PREFIX[8] == '后排8槽'
    for n in (7, 9, 10, 11, 12):
        assert n not in _LAYOUT_PREFIX
    # 公式路由
    assert back_slots_from_cap_diff(0) == 6
    assert back_slots_from_cap_diff(1) == 8    # 7 格未建档 → 8 格超集
    assert back_slots_from_cap_diff(2) == 8
    assert back_slots_from_cap_diff(3) == 8    # 域外按 2(cap10/lv8、cap11/lv8 局同 8 格)
    assert back_slots_from_cap_diff(-1) == 6   # cap<level 读错族按 0
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


# ===== 4. select_back_layout 选档入口 + 7 格待采留证 =====

def test_select_back_layout_formula(tmp_path, monkeypatch, frame):
    """选档单一入口·公式通道(cv 通道 stub 掉隔离;双通道对账见下方专项锁):
    cap/level 两读数按口述公式合流;读不到 → 6(失败安全侧)。

    run 26 反向锚:lv8 无召唤物(cap=level)→ 恒 6 格(旧模型按 level≥7 选 8 格
    = 崩坏根因①);lv7 cap9(狸猫局)→ 8 格。
    """
    import sr_od.application.currency_war.cw_back_layout as cbl
    import sr_od.application.currency_war.cw_identity_obs as cio
    import sr_od.application.currency_war.cw_observation as cwo
    import sr_od.application.currency_war.cw_observe as cobs
    journal = tmp_path / 'obs.jsonl'
    monkeypatch.setattr(cobs, '_CONFLICT_JOURNAL', journal)
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cbl, '_pending_note_ts', {})
    monkeypatch.setattr(cbl, '_channel_conflict_ts', {})
    monkeypatch.setattr(cbl, '_last_sel_log', None)
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 8)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: 8)
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: None)   # CV 不可判 → 公式
    assert cbl.select_back_layout(None, frame) == (6, '后排')      # run 26 形态:lv8 cap8
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: 10)
    assert cbl.select_back_layout(None, frame) == (8, '后排8槽')   # diff2 → 8
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 7)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: 9)
    assert cbl.select_back_layout(None, frame) == (8, '后排8槽')   # 狸猫局 lv7 cap9
    # diff==1(钻石+1):7 格未建档 → 8 格超集 + back_7slots_pending 留证
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: 8)
    assert cbl.select_back_layout(None, frame) == (8, '后排8槽')
    assert journal.exists() and 'back_7slots_pending' in journal.read_text(encoding='utf-8')
    # 读不到 cap → diff 按 0 → 6(失败安全侧;别按扩展档跑)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: None)
    assert cbl.select_back_layout(None, frame) == (6, '后排')


# ===== 4b. CV 通道 + 双通道对账(ADR-0385 口述双通道指令,W209 追加) =====

def test_cv_channel_grid_counts(templates):   # noqa: ARG001  复用模块级模板加载惰性
    """CV 通道实测格数:槽位存在性 std 签名(真 fixture 全量标定)。

    8 格帧(狸猫局/全位验证/cap9/10/11)→ 8;6 格帧(shop_closed/a8_start/
    prep_1-6/deployed_p1r9/r1_idle_stop)→ 6;「后排7槽-P2开局局」→ **6**
    (旧「7 槽」观察经 CV 复核两端扩展位均为背景 = 同属幻影,实为 6 格——
    公式通道自洽的又一实证);非 1080p 小帧 → None(越界守卫)。
    """
    import numpy as np
    from sr_od.application.currency_war.cw_back_layout import cv_back_slots
    for fn, want in (
            ('后排8槽-狸猫局.webp', 8), ('后排8槽-全位验证.webp', 8),
            ('后排9槽-双宝钻局.webp', 8), ('后排10槽-满级局.webp', 8),
            ('后排11槽-P3局.webp', 8),
            ('后排7槽-P2开局局.webp', 6), ('shop_closed.webp', 6),
            ('shop_closed_a8_start.webp', 6), ('prep_1-6_all_positions.webp', 6),
            ('deployed_p1r9.webp', 6), ('r1_idle_stop.webp', 6)):
        img = cv2_utils.read_image(str(FIXTURES / fn))
        got = cv_back_slots(img)
        assert got == want, f'{fn}: CV 实测 {got} ≠ 期望 {want}'
    assert cv_back_slots(np.zeros((600, 900, 3), dtype=np.uint8)) is None


def test_reconcile_channels_agree(tmp_path, monkeypatch, frame):
    """对账·一致 → 公式值,无 back_layout_channel_conflict 留证。"""
    import sr_od.application.currency_war.cw_back_layout as cbl
    import sr_od.application.currency_war.cw_identity_obs as cio
    import sr_od.application.currency_war.cw_observation as cwo
    import sr_od.application.currency_war.cw_observe as cobs
    journal = tmp_path / 'obs.jsonl'
    monkeypatch.setattr(cobs, '_CONFLICT_JOURNAL', journal)
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cbl, '_pending_note_ts', {})
    monkeypatch.setattr(cbl, '_channel_conflict_ts', {})
    monkeypatch.setattr(cbl, '_last_sel_log', None)
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 7)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: 9)
    # 狸猫局真帧:公式 diff2 → 8,CV 实测 8 → 一致用公式值
    assert cbl.select_back_layout(None, frame) == (8, '后排8槽')
    assert not journal.exists() or 'back_layout_channel_conflict' not in \
        journal.read_text(encoding='utf-8')


def test_reconcile_channels_disagree_cv_wins(tmp_path, monkeypatch, frame):
    """对账·不一致 → **CV 实测值** + obs_conflict 留证带两值(画面事实>推导)。

    场景=run 26 事故族的反向:公式说 6(两个 OCR 读数错成 cap=level)但画面
    实为 8 格(狸猫真帧)→ 采 CV 的 8(不误按 6 格丢读扩展带)+ 留证
    old=6(公式)/new=8(CV)供判读查 reader。
    """
    import json as _json
    import sr_od.application.currency_war.cw_back_layout as cbl
    import sr_od.application.currency_war.cw_identity_obs as cio
    import sr_od.application.currency_war.cw_observation as cwo
    import sr_od.application.currency_war.cw_observe as cobs
    journal = tmp_path / 'obs.jsonl'
    monkeypatch.setattr(cobs, '_CONFLICT_JOURNAL', journal)
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cbl, '_pending_note_ts', {})
    monkeypatch.setattr(cbl, '_channel_conflict_ts', {})
    monkeypatch.setattr(cbl, '_last_sel_log', None)
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 8)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: 8)   # 公式:6
    assert cbl.select_back_layout(None, frame) == (8, '后排8槽')      # CV 8 优先
    assert journal.exists(), '不一致未留证'
    rec = _json.loads(journal.read_text(encoding='utf-8')
                      .strip().splitlines()[-1])
    assert rec['field'] == 'back_layout_channel_conflict'
    assert rec['old'] == 6 and rec['new'] == 8   # 两值齐报(公式/CV)


def test_reconcile_cv_none_formula_fallback(tmp_path, monkeypatch, frame):
    """CV 不可判(锚缺失/越界/特效遮挡)→ 退公式值(公式=CV 失效的兜底)。"""
    import sr_od.application.currency_war.cw_back_layout as cbl
    import sr_od.application.currency_war.cw_identity_obs as cio
    import sr_od.application.currency_war.cw_observation as cwo
    monkeypatch.setattr(cbl, '_pending_note_ts', {})
    monkeypatch.setattr(cbl, '_channel_conflict_ts', {})
    monkeypatch.setattr(cbl, '_last_sel_log', None)
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 8)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: 10)
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: None)
    assert cbl.select_back_layout(None, frame) == (8, '后排8槽')
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: 8)
    assert cbl.select_back_layout(None, frame) == (6, '后排')


def test_read_deployed_chars_formula_driven(
        test_context, templates, monkeypatch, tmp_path, frame):
    """read_deployed_chars 布局选档经 select_back_layout(双通道合流)。

    狸猫局 fixture + monkeypatch cap:diff2(与 CV 一致)→ 8 格档读到位7/8 狸猫;
    同帧 diff0 + CV stub 一致(6)→ 6 格档:最右扩展格(1458 狸小龙)不再被读
    (6 格基线右界 1315,恰含 1316 狸小虎——两档共享 604-1316 段,差异只在
    两端扩展格)。
    """
    import sr_od.application.currency_war.cw_back_layout as cbl
    import sr_od.application.currency_war.cw_identity_obs as cio
    import sr_od.application.currency_war.cw_observation as cwo
    import sr_od.application.currency_war.cw_observe as cobs
    monkeypatch.setattr(cobs, '_CONFLICT_JOURNAL', tmp_path / 'obs.jsonl')
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cbl, '_pending_note_ts', {})
    monkeypatch.setattr(cbl, '_channel_conflict_ts', {})
    monkeypatch.setattr(cbl, '_last_sel_log', None)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: 9)
    out8 = cio.read_deployed_chars(test_context, frame, templates, level=7)
    got8 = {c.char_id for c in out8 if c.position_pref == 'back'}
    assert {'狸小虎', '狸小龙'} <= got8
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: 8)
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: 6)   # 两通道一致 6
    out6 = cio.read_deployed_chars(test_context, frame, templates, level=8)
    got6 = {c.char_id for c in out6}
    assert '狸小龙' not in got6   # 1458 扩展格在 6 格基线外


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



# ===== 旧布局停机钩子已删(W209/ADR-0385)=====
# 旧钩子停机条件「level 对应档无档」随 level 驱动模型作废:公式选档恒落
# 6/8 已建档档(7 格未建档走 8 格超集 + obs_conflict 留证,不停机);
# 补档窗口守卫改由 note_7slots_pending 采集指引承载(见 test_select_back_layout_formula)。
