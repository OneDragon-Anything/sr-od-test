"""后排槽位布局表测试(W209/ADR-0385 双通道对账勘误后重写,2026-08-26,
含同日件③停机钩子重构)。

锁六件事:
1. 8 格档识别:狸猫局/全位验证/双宝钻局(cap9!)/满级局(cap10!)/P3局(cap11!)
   —— 旧 9/10/11 档三帧**实为同一个 8 格布局**(393-1529 带,空槽签名终判),
   全部按 8 格档锁(口述公式自洽:cap9/10/11 的 lv7/8 局 diff≥2 全落 8 格)。
2. 双通道公式路由(ADR-0385 口述「后台格数 = 6+(cap−level)」):
   diff 0 → 6 / diff≥2 → 8 / diff==1(7 格未建档)→ 保守 8 格超集运行;
   **level 单独不再参与选档**(run 26 lv8 无召唤物局恒 6 格 = 崩坏根因①反向锚)。
3. 幻影档不存在:_LAYOUT_PREFIX 只含 {6,8};yml(源+merged)无 后排7/9/10/11槽 area。
4. 布局停机钩子(件③):对账原始格数 n_raw 无档(=7,钻石+1 局)→ 停机+flag
   引导现场采集 7 格真值;6/8 已建档 → 永不触发。旧「lv6=7 格待采」留证机器
   (back_7slots_pending/note_pending_7slots)已随公式答案作废清理
   (7 格存在性=钻石+1,与等级无关;缺的只是坐标档,归钩子管)。
5. 系统单位恒最右布局自检(layout_mismatch_by_system_unit):对/错档两态
   (ADR-0385 保留作选档的交叉验证网)。
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
    diff0→6 / diff1→7(已建档,2026-08-26 佩佩局实锤)/ diff≥2→8;
    diff<0(读错族)按 0;diff>2(域外)按 2。level 单独不参与。"""
    from sr_od.application.currency_war.cw_back_layout import (
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
        txt = (_ROOT / rel).read_text(encoding='utf-8')
        for pfx in ('后排9槽', '后排10槽', '后排11槽'):
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
    # diff==1(钻石+1):7 格已建档(佩佩局实锤)→ 直读 7 格
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: 8)
    assert cbl.select_back_layout(None, frame) == (7, '后排7槽')
    # 件③:7 格留证机器已废(存在性=钻石+1 由公式回答;坐标档已建档钩子静默)
    # 读不到 cap → diff 按 0 → 6(失败安全侧;别按扩展档跑)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: None)
    assert cbl.select_back_layout(None, frame) == (6, '后排')


# ===== 4b. CV 通道 + 双通道对账(ADR-0385 口述双通道指令,W209 追加) =====

def test_cv_channel_grid_counts(templates):   # noqa: ARG001  复用模块级模板加载惰性
    """CV 通道实测格数:槽位存在性 std 签名(真 fixture 全量标定)。

    8 格帧(狸猫/全位验证/cap9/cap10,左端 std 62.5-65.6 清晰带)→ 8;
    **P3 局(cap11)左1 空槽 std 38.8 落不可判带 [12,48] → None 退公式**;
    6 格帧(shop_closed/a8_start/prep_1-6/deployed_p1r9/r1_idle_stop)→ 6;
    「后排7槽-P2开局局」→ **6**(旧「7 槽」观察实为 6 格幻影);**真 7 格帧
    (佩佩局,居中重排 534..1386)左端 464 探针=真 s1 左半覆盖 std 26-44
    落不可判带 → None 退公式 diff=1→7**(ADR-0390 勘误:非「羁绊面板渗入」;
    7/8 的区分靠 cap 差公式+等级经验条反推)。非 1080p 小帧 → None(越界守卫)。

    run 26 崩坏现场帧(后排6格-run26崩坏现场.png,编排者 VLM+右端位置双重
    确认 = 标准 6 格正样本)→ 6:事故形态的直接回归锚。
    """
    import numpy as np
    from sr_od.application.currency_war.cw_back_layout import cv_back_slots
    for fn, want in (
            ('后排8槽-狸猫局.webp', 8), ('后排8槽-全位验证.webp', 8),
            ('后排9槽-双宝钻局.webp', 8), ('后排10槽-满级局.webp', 8),
            ('后排11槽-P3局.webp', None),   # 左1 空槽 38.8 ∈ 不可判带 → 退公式
            ('后排7槽-佩佩局.png', None),       # 渗入 26.2 ∈ 不可判带 → 退公式 diff1→7
            ('后排7槽-佩佩局-拖测后.png', None),  # 渗入 40.2 ∈ 不可判带 → 退公式 diff1→7
            ('后排7槽-P2开局局.webp', 6), ('shop_closed.webp', 6),
            ('shop_closed_a8_start.webp', 6), ('prep_1-6_all_positions.webp', 6),
            ('deployed_p1r9.webp', 6), ('r1_idle_stop.webp', 6),
            ('后排6格-run26崩坏现场.png', 6)):
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



# ===== 6b. 布局留证采集钩子(W209i/ADR-0385 决策 12:停机钩子降级废弃)=====
# run 27 停机事故实证:货币战争备战实时倒计时,停 bot ≠ 停游戏——hook 停机后
# 画面自行推进到首领战败结算(14:09 停 → 14:16 结算),「停机保画面待采集」
# 对实时制游戏是虚假承诺。降级:n_raw=7 → obs_conflict 留证+去重截图不停机;
# 7 格坐标由 CV 持续留证 + 人工在场经 MCP 交互采集。

def test_layout_hook_no_stop_only_evidence(
        test_context, templates, monkeypatch, tmp_path, frame):
    """W209i 降级锁(7 格建档后语义):n_raw 未建档(用 9 模拟未来新档,
    CV 三读稳定)→ **不停机**,落 back_layout_unarchived_grid 留证(带公式/
    CV/防抖序列),无 flag 文件;真实 7 格(diff==1)已建档 → 见
    test_layout_hook_silent_on_archived。"""
    import json as _json
    import sr_od.application.currency_war.cw_back_layout as cbl
    import sr_od.application.currency_war.cw_identity_obs as cio
    import sr_od.application.currency_war.cw_obs_core as core
    import sr_od.application.currency_war.cw_observation as cwo
    import sr_od.application.currency_war.cw_observe as cobs
    ctx = test_context

    class _FakeRunCtx:
        stopped = False
        stop_calls: list[str] = []

        def stop_running(self, reason: str = ''):
            self.stopped = True
            self.stop_calls.append(reason)

    monkeypatch.setattr(ctx, 'run_context', _FakeRunCtx())
    monkeypatch.setattr(core, 'is_prep_like_frame', lambda c, s: True)
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cobs, '_CONFLICT_JOURNAL', tmp_path / 'obs.jsonl')
    monkeypatch.setattr(cbl, '_channel_conflict_ts', {})
    monkeypatch.setattr(cbl, '_last_sel_log', None)
    monkeypatch.setattr(cio, '_session_level', lambda c: 8)
    # 公式 8(lv8 cap10 diff2)且 CV 三读稳定 9(防抖过)→ n_raw=9 未建档
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda c, s: 10)
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda s: 9)
    monkeypatch.setattr(ctx, 'screenshot', lambda: frame, raising=False)
    out = cio.read_deployed_chars(ctx, frame, templates, level=8)
    assert isinstance(out, list) and out                    # 读板照常不抛
    assert not ctx.run_context.stopped and not ctx.run_context.stop_calls, \
        'W209i:未建档档不得停机(实时制游戏停 bot 不停游戏,run 27 实证)'
    journal = tmp_path / 'obs.jsonl'
    assert journal.exists(), '降级后必须留证'
    rec = _json.loads(journal.read_text(encoding='utf-8').strip().splitlines()[-1])
    assert rec['field'] == 'back_layout_unarchived_grid'
    assert rec['old'] == 9 and rec['cv_readings'] == [9, 9, 9]
    assert '不停机' in rec['verdict']                        # 如实声明画面可能推进
    assert not (tmp_path / '.debug/temp/currency_war/back_layout_stop_hook.flag').exists(), \
        '停机 flag 机制已废弃不得回流'


def test_layout_hook_silent_on_archived(
        test_context, templates, monkeypatch, tmp_path, frame):
    """6/8/7 已建档(含超集运行态、对账一致态与 7 格直读态)→ 无留证无副作用。

    2026-08-26 佩佩局 7 格建档后,(8,9,7) = diff1 直读 7 的真值态,必须
    静默(旧「7 未建档刷留证」行为已废,证据垃圾)。"""
    import sr_od.application.currency_war.cw_back_layout as cbl
    import sr_od.application.currency_war.cw_identity_obs as cio
    import sr_od.application.currency_war.cw_observation as cwo
    import sr_od.application.currency_war.cw_observe as cobs
    ctx = test_context
    monkeypatch.setattr(cobs, '_CONFLICT_JOURNAL', tmp_path / 'obs.jsonl')
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cbl, '_channel_conflict_ts', {})
    monkeypatch.setattr(cbl, '_last_sel_log', None)
    # 6 格(run 26 形态)/ 8 格(狸猫局形态)/ 7 格(佩佩局直读)都不留证
    for lv, cap, cv in ((8, 8, 6), (7, 9, 8), (8, 9, 7)):
        monkeypatch.setattr(cio, '_session_level', lambda c, _lv=lv: _lv)
        monkeypatch.setattr(cwo, 'read_deploy_cap', lambda c, s, _cap=cap: _cap)
        monkeypatch.setattr(cbl, 'cv_back_slots', lambda s, _cv=cv: _cv)
        cio.read_deployed_chars(ctx, frame, templates, level=lv)
    # 只辖本测对象(未建档留证钩子);check_system_unit_layout 在 (8,9,7) 态
    # 对 8 格狸猫帧按 7 格选档正确报 layout_mismatch(自检职责,另锁辖)
    if (tmp_path / 'obs.jsonl').exists():
        txt = (tmp_path / 'obs.jsonl').read_text(encoding='utf-8')
        assert 'back_layout_unarchived_grid' not in txt, \
            '已建档档位(6/7/8)不得落未建档留证'


def test_layout_hook_no_stop_machinery_in_src():
    """W209i 源码级锁:read_deployed_chars 不得再调 stop_running/写停机 flag
    (停机钩子整段废弃,回流即红)。"""
    import inspect
    from sr_od.application.currency_war import cw_identity_obs
    src = inspect.getsource(cw_identity_obs.read_deployed_chars)
    assert 'stop_running' not in src and 'back_layout_stop_hook.flag' not in src, \
        '停机机制已废弃(ADR-0385 决策 12);采集走留证+人工经 MCP'


def test_pending_7slots_machinery_removed():
    """件②:旧「lv6=7 格待采」留证机器已清理(存在性由公式回答=钻石+1,
    与等级无关;缺的只是坐标档,归停机钩子管)。"""
    import sr_od.application.currency_war.cw_back_layout as cbl
    assert not hasattr(cbl, 'note_7slots_pending')
    assert not hasattr(cbl, '_pending_note_ts')
    assert not hasattr(cbl, '_PENDING_7SLOT_LEVELS')


# ===== 6c. CV 新格数防抖重读(W209h,ADR-0385 决策 11;run 27 停机事故) =====
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


def test_cv_transient_falls_back_to_formula(tmp_path, monkeypatch, frame):
    """run 27 事故形态(以未建档 9 模拟新格数瞬态):首读假阳 9,重读回到
    真值 6(序列 [9,6,6])→ 退公式 8,不停机;瞬态留证 obs_conflict。

    (7 格已建档:CV 稳定 7 = 合法档直读,不经防抖;瞬态 7 误读的代价仅是
    多读一个空扩展窗(超集语义,无动作损失),run 27 型停机事故不再可能。)"""
    import json as _json
    import sr_od.application.currency_war.cw_back_layout as cbl
    import sr_od.application.currency_war.cw_identity_obs as cio
    import sr_od.application.currency_war.cw_observation as cwo
    import sr_od.application.currency_war.cw_observe as cobs
    # 6 格真帧(shop_closed)×2 作重读帧
    frame6 = cv2_utils.read_image(str(FIXTURES / 'shop_closed.webp'))
    fctx = _FakeCtx([frame6, frame6])
    journal = tmp_path / 'obs.jsonl'
    monkeypatch.setattr(cobs, '_CONFLICT_JOURNAL', journal)
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cbl, '_channel_conflict_ts', {})
    monkeypatch.setattr(cbl, '_last_sel_log', None)
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 8)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: 10)  # 公式 8
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


def test_cv_stable_new_grid_confirmed(tmp_path, monkeypatch, frame):
    """稳定未建档新格数(以 9 模拟):三读一致 [9,9,9] → 采 CV 值
    (n_raw=9 触发留证钩子采集流程,防抖不拦真信号;运行值退 8 超集)。"""
    import sr_od.application.currency_war.cw_back_layout as cbl
    import sr_od.application.currency_war.cw_identity_obs as cio
    import sr_od.application.currency_war.cw_observation as cwo
    import sr_od.application.currency_war.cw_observe as cobs
    fctx = _FakeCtx([frame, frame])   # 重读帧同 frame(stub 全 9)
    monkeypatch.setattr(cobs, '_CONFLICT_JOURNAL', tmp_path / 'obs.jsonl')
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cbl, '_channel_conflict_ts', {})
    monkeypatch.setattr(cbl, '_last_sel_log', None)
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 8)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: 10)  # 公式 8
    monkeypatch.setattr(cbl, 'cv_back_slots', lambda scr: 9)          # 三读全 9
    r = cbl.resolve_back_slots(fctx, frame, level=8, cap=10)
    assert r['n_raw'] == 9 and r['n'] == 8      # 采 CV 9 → 运行 8 超集(未建档)
    assert r['cv_readings'] == [9, 9, 9]
    assert fctx.shots == 2


def test_cv_reread_mismatch_logged_no_action(tmp_path, monkeypatch, frame):
    """重读帧间不一致(如 [9,9,6],未建档 9 模拟)= 瞬态 → 退公式 + 序列留证
    (obs_conflict 带 cv_readings 上下文),不采 CV。"""
    import json as _json
    import sr_od.application.currency_war.cw_back_layout as cbl
    import sr_od.application.currency_war.cw_identity_obs as cio
    import sr_od.application.currency_war.cw_observation as cwo
    import sr_od.application.currency_war.cw_observe as cobs
    frame6 = cv2_utils.read_image(str(FIXTURES / 'shop_closed.webp'))
    fctx = _FakeCtx([frame, frame6])   # 重读 1=frame(9),重读 2=frame6(6)
    journal = tmp_path / 'obs.jsonl'
    monkeypatch.setattr(cobs, '_CONFLICT_JOURNAL', journal)
    monkeypatch.setattr(cobs, 'cw_shot_unique', lambda img, label: f'{label}.png')
    monkeypatch.setattr(cbl, '_channel_conflict_ts', {})
    monkeypatch.setattr(cbl, '_last_sel_log', None)
    monkeypatch.setattr(cio, '_session_level', lambda ctx: 8)
    monkeypatch.setattr(cwo, 'read_deploy_cap', lambda ctx, scr: 10)
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
        fix, templates, _slots7(), 'back', min_inliers=15, live_only=True)}
    assert got == {1: '万敌', 3: '乱破', 5: '卡芙卡', 7: '佩佩'}, got


def test_pepe_board_truth_golden(templates):
    """佩佩局拖测前帧(用户口述真值):1=卡芙卡/3=万敌/5=爻光/7=佩佩。"""
    fix = cv2_utils.read_image(str(FIXTURES / '后排7槽-佩佩局.png'))
    got = {c.slot: c.char_id for c in identify_slots(
        fix, templates, _slots7(), 'back', min_inliers=15, live_only=True)}
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
            fix, templates, _slots7(), 'back', min_inliers=15, live_only=True)}
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
    from sr_od.application.currency_war.cw_chars import get_char
    ch = get_char('佩佩')
    assert ch is not None and ch.cost == 0
    from sr_od.application.currency_war.cw_state import BenchChar
    from sr_od.application.currency_war.operations.prep.deploy_bench import (
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
    import sr_od.application.currency_war.cw_observation as cwo
    from sr_od.application.currency_war.cw_obs_core import _area_rect
    img = cv2_utils.read_image(str(FIXTURES / '后排7槽-佩佩局-拖测后.png'))
    _lv_rect = _area_rect(test_context, '文本-等级')
    _real_ocr = cwo._ocr
    monkeypatch.setattr(
        cwo, '_ocr',
        lambda ctx, scr, rect: [] if rect == _lv_rect else _real_ocr(ctx, scr, rect),
    )                                                                  # 仅等级区漏读
    got = cwo.read_level(test_context, img, 1, 1)
    assert got == 3, f'经验条反推应为 lv3(0/4),实得 {got}'
    # 经验条也漏(全黑)→ 退期望曲线(旧行为)
    monkeypatch.setattr(cwo, 'read_xp_progress', lambda ctx, scr: None)
    assert cwo.read_level(test_context, img, 1, 1) == cwo._expected_level(1, 1)
