"""test_cw_node_screens 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;断言面保持原语义):
- node_reader: test_cw_node_reader.py
- node_type_gate: test_cw_node_type_gate.py
- node_obs: test_cw_node_obs.py
- node_boss: test_cw_node_boss.py
- node_validate: test_cw_node_validate.py
- bookcard_handler: test_cw_bookcard_handler.py
- test_reward_sphere: test_reward_sphere.py
- test_supply_box: test_supply_box.py
- w595_trial_reveal_card: test_cw_w595_trial_reveal_card.py
- w219_boss_collect_channel: test_cw_w219_boss_collect_channel.py
- w221_boss_locate_emblem: test_cw_w221_boss_locate_emblem.py
- briefing_plane_order: test_cw_briefing_plane_order.py
同符号的多套来源前缀别名与重复夹具(备战栏槽位表/资产路径/读图 helper)
已收敛为文件头单一定义;合并期「冲突改名前缀」不再存在。
"""
from __future__ import annotations

import inspect
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import cv2
import numpy as np
import pytest

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.cv2_utils import read_image

from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_prep_actions import ClickSpheres
from sr_od.application.currency_war.obs.cw_identity_obs import (
    _get_bookcard_gray,
    find_bookcards,
    find_reward_spheres,
    find_supply_boxes,
    find_trial_reveal_cards,
    read_reward_spheres,
)
from sr_od.application.currency_war.obs.cw_node_obs import (
    read_encounter_options,
    read_encounter_refresh_count,
    read_megastar_options,
)
from sr_od.application.currency_war.obs.cw_node_reader import (
    classify_node_row,
    load_boss_templates,
    load_node_type_templates,
)
from sr_od.application.currency_war.obs.cw_observation import (
    _MIN_CLEAN_CIRCLES,
    gate_node_type,
    read_detail_node_type_label,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_expert_invite import (
    choose_expert_index,
)
from sr_od.application.currency_war.tools.cw_node_validate import (
    P1_NODE_TEMPLATE,
    validate_p1_node_sequence,
    validate_p2_node_sequence,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext

# ==================== 共享夹具(合并段统一) ====================

# 仓根(本文件位于 <仓根>/sr-od-test/test/sr_od/app/currency_war/ → parents[5] = 仓根)
_REPO_ROOT = Path(__file__).resolve().parents[5]
TEST_DIR = Path(__file__).resolve().parents[4]   # sr-od-test 根(screens 存档帧基点)
SCREENS = TEST_DIR / 'screens' / '货币战争-备战'
_NODE_TPL_DIR = _REPO_ROOT / 'assets' / 'game_data' / 'cw_node_types'
_BOSS_TPL_DIR = _REPO_ROOT / 'assets' / 'template' / 'currency_war' / 'boss_avatar'

# screen_info「货币战争-备战.备战栏-1..9」pc_rect(1080p;与 yml 同步,离线硬编码约定;
# 纯 CV 测试不持 ctx,读不到 screen_info,按仓内 data_registry 同款约定离线硬编码)
_BENCH_SLOTS: list[tuple[int, Rect]] = [
    (1, Rect(382, 845, 495, 979)),
    (2, Rect(507, 844, 620, 978)),
    (3, Rect(632, 844, 743, 978)),
    (4, Rect(757, 845, 869, 979)),
    (5, Rect(882, 846, 995, 980)),
    (6, Rect(1004, 847, 1118, 978)),
    (7, Rect(1132, 846, 1244, 977)),
    (8, Rect(1256, 845, 1368, 979)),
    (9, Rect(1379, 844, 1493, 980)),
]


def _imdecode_rgb(path) -> np.ndarray | None:
    """imdecode(BGR)→ RGB(生产语义:框架截图链 BGRA2RGB,live 是 RGB;
    fixture 经 imdecode 读到 BGR,进 classify/read 链前须翻到同侧)。"""
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    return None if img is None else cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


# ==================== node_reader(节点行类型识别) ====================

_CLEAN_ROW_FIXTURE = Path(__file__).parent / 'cw_node_row_clean.png'


def test_load_node_type_templates() -> None:
    """节点类型模板全加载(battle/supply/encounter/reward + encounter_v2 变体聚合同 key)。"""
    tpls = load_node_type_templates(_NODE_TPL_DIR)
    assert set(tpls.keys()) == {'battle', 'supply', 'encounter', 'reward'}
    assert len(tpls['encounter']) == 2   # encounter + encounter_v2(r86 三叉箭头变体)


def test_classify_clean_node_row() -> None:
    """clean 节点行 fixture(1-1 备战,8 槽)→ 8 槽 + 1 当前/7 未来 + 未来 Hu 匹配 4 类型 + cy 已存。

    ⚠️ 通道对齐(review P1,2026-08-16):classify_node_row 语义 = **RGB**(框架截图链 BGRA2RGB);
    fixture 经 imdecode 读到 BGR → 测试先翻 RGB 再传(与生产 live 同侧)。
    """
    tpls = load_node_type_templates(_NODE_TPL_DIR)
    img = _imdecode_rgb(_CLEAN_ROW_FIXTURE)
    assert img is not None
    slots = classify_node_row(img, tpls)
    assert len(slots) == 8                                          # 基础 8 槽全检出
    states = [s.state for s in slots]
    assert states.count('current') == 1                            # round 1 → idx0 当前
    assert states.count('upcoming') == 7                           # 未来 7 个
    # 当前槽 type=None(classify 不定当前;上层 read_node_sequence 用 OCR 覆盖)
    assert next(s for s in slots if s.state == 'current').node_type is None
    # 未来槽全匹配到已知类型(Hu 最近邻,非 None)
    upcoming_types = [s.node_type for s in slots if s.state == 'upcoming']
    assert all(t is not None for t in upcoming_types)
    # 未来类型分布(r86 更新:encounter_v2 深蓝圆底三叉箭头变体入模板后,原判 supply
    # 的 idx7 改判 encounter dist3.18 < 对 supply 的距离 —— 变体聚合 min 吸收;
    # 186 张积压采样实锤该变体,自模板回归 184/186)。
    assert Counter(upcoming_types) == {'battle': 3, 'supply': 1, 'reward': 1, 'encounter': 2}
    # cy 已存(非 0,圆心 y 在行内 —— Task 2 采集图标定位依赖)
    assert all(s.cy > 0 for s in slots)


def test_gate_condition_non_node_row() -> None:
    """非节点行(空白小图)→ HoughCircles 检不出圆 → n < _MIN_CLEAN_CIRCLES(read_node_sequence 返 None 的门条件)。"""
    tpls = load_node_type_templates(_NODE_TPL_DIR)
    blank = np.zeros((100, 200, 3), dtype=np.uint8)                # 纯黑空白,无圆
    slots = classify_node_row(blank, tpls)
    assert len(slots) < _MIN_CLEAN_CIRCLES                         # 门条件成立 → 上层返 None 跳过坏帧


# ==================== node_type_gate(节点类型语义门) ====================


def test_boss_round_gate_rejects_upcoming_boss_label():
    """2-7 实证:round=7 读到「首领」(即将到来的 boss 节点标签)→ None。
    r80 审计 a 收紧:round=8 同样拒(boss=第 9 轮;人身意外险+补给后 ≥10,取 9 下限)。"""
    assert gate_node_type('boss', 7) is None
    assert gate_node_type('boss', 8) is None   # 收紧:与 boss 相邻的前置轮,标签更早出现
    assert gate_node_type('boss', 1) is None
    assert gate_node_type('boss', None) is None   # 轮次读不到 → 不信 boss


def test_boss_round_gate_passes_real_boss_round():
    """真 boss 轮(位面最后节点 = 第 9 轮)→ 放行(轮次门只拒未到 boss 轮的标签)。"""
    assert gate_node_type('boss', 9) == 'boss'


def test_label_position_gate_rejects_mismatch():
    """标签 x=1341(即将到来的 boss 节点)vs 当前槽 cx≈900 → 错位 > 容差 → None。"""
    assert gate_node_type('boss', 9, label_x=1341, current_cx=900) is None


def test_label_position_gate_passes_aligned():
    """标签在当前节点下方(对齐)→ 放行。"""
    assert gate_node_type('supply', 3, label_x=905, current_cx=900) == 'supply'
    assert gate_node_type('boss', 9, label_x=1340, current_cx=1310) == 'boss'


def test_non_boss_types_unaffected_by_round_gate():
    """非 boss 类型(补给/遭遇等)无轮次语义约束 → 只受位置门。"""
    assert gate_node_type('supply', 2) == 'supply'
    assert gate_node_type('encounter', 1) == 'encounter'


def test_none_passthrough():
    """None → None(无标签不造数据)。"""
    assert gate_node_type(None, 9) is None
    assert gate_node_type(None, None) is None


# ==================== node_obs(节点 overlay 选项读取) ====================


def _ocr_map(items: list[tuple[str, int, int]]) -> dict:
    """构造 mock ocr_map:text → {max: {center: {x,y}}}。"""
    return {
        t: SimpleNamespace(max=SimpleNamespace(center=SimpleNamespace(x=cx, y=cy)))
        for t, cx, cy in items
    }


class _FakeCtx:
    def __init__(self, m: dict) -> None:
        self.ocr_service = SimpleNamespace(
            get_ocr_result_map=lambda **kw: m,
        )


def test_read_encounter_options_baseline_layout() -> None:
    """baseline 实测 OCR(2026-08-07):左卡=其一(「一」漏读→「遭遇其」)、右卡=其四 + 各自奖励。"""
    m = _ocr_map([
        ('遭遇其', 655, 389),        # 左卡(其一,「一」笔画细被漏 → 无数字)
        ('遭遇其四', 1251, 389),     # 右卡(其四)
        ('奖励预览', 655, 580),
        ('奖励预览', 1251, 580),
        ('金币', 640, 646),          # 左奖励
        ('随机4费角色', 1263, 647),  # 右奖励
        ('2', 601, 672),             # 数量(<2 字,过滤)
        ('3', 1187, 672),
        ('选择', 1081, 898),
    ])
    opts = read_encounter_options(_FakeCtx(m), None)
    assert len(opts) == 2
    assert opts[0].idx == 0 and opts[0].difficulty == 1 and opts[0].rewards == ['金币']
    assert opts[1].idx == 1 and opts[1].difficulty == 4 and opts[1].rewards == ['随机4费角色']


def test_read_encounter_options_no_cards_returns_empty() -> None:
    """无「遭遇其X」标题(非遭遇屏)→ [](handler 退默认 idx0)。"""
    opts = read_encounter_options(_FakeCtx({}), None)
    assert opts == []


def test_read_encounter_options_ignores_zaojie_node_label() -> None:
    """「遭遇节点」(屏标题)不含「其」→ 不误当卡。"""
    m = _ocr_map([('遭遇节点', 960, 96), ('选择', 1081, 898)])
    assert read_encounter_options(_FakeCtx(m), None) == []


def test_read_encounter_options_reward_assigned_by_nearest_x() -> None:
    """奖励按 x 就近归卡(左卡奖励归左、右归右),不按行索引。"""
    m = _ocr_map([
        ('遭遇其二', 400, 389),
        ('遭遇其五', 1200, 389),
        ('奖励预览', 400, 580),
        ('奖励预览', 1200, 580),
        ('装备', 410, 646),
        ('晶矿', 1190, 646),
    ])
    opts = read_encounter_options(_FakeCtx(m), None)
    assert opts[0].difficulty == 2 and opts[0].rewards == ['装备']
    assert opts[1].difficulty == 5 and opts[1].rewards == ['晶矿']


# —— read_encounter_refresh_count(dd-004 分支刷新执行链 reader)——


def test_read_encounter_refresh_count_baseline() -> None:
    """归档帧形态:「剩余次数：1」(全角冒号)→ (1, 文本中心);「选择」等他行不误判。"""
    m = _ocr_map([
        ('遭遇其一', 655, 389),
        ('剩余次数：1', 784, 900),
        ('选择', 1081, 898),
    ])
    assert read_encounter_refresh_count(_FakeCtx(m), None) == (1, (784, 900))


def test_read_encounter_refresh_count_halfwidth_colon_and_zero() -> None:
    """半角冒号 OCR 变体也认;0 次如实返回(无次数的判定归调用方)。"""
    m = _ocr_map([('剩余次数:2', 780, 900)])
    assert read_encounter_refresh_count(_FakeCtx(m), None) == (2, (780, 900))
    m0 = _ocr_map([('剩余次数：0', 784, 900)])
    assert read_encounter_refresh_count(_FakeCtx(m0), None) == (0, (784, 900))


def test_read_encounter_refresh_count_missing_returns_none() -> None:
    """读不到(未激活分支刷新布局/非遭遇屏/OCR 漏)→ None(handler 按无刷新处理)。"""
    m = _ocr_map([('选择', 1081, 898), ('遭遇其一', 655, 389)])
    assert read_encounter_refresh_count(_FakeCtx(m), None) is None
    assert read_encounter_refresh_count(_FakeCtx({}), None) is None


def test_read_megastar_options_parses_candidates() -> None:
    """D-95:巨星候选「盛会之星一X先生/女士!」→ MegastarOption(char_id=X),按 x 左→右 idx。

    baseline cw_megastar OCR(2026-08-07):花火(左 822)+ 星期日(右 1061)。容错半角叹号。
    """
    m = _ocr_map([
        ('盛会之星一花火女士！', 822, 333),    # 左(全角 !)
        ('盛会之星一星期日先生!', 1061, 334),   # 右(半角 !)
        ('请选择1名角色成为巨星', 935, 124),
        ('确认选择', 1441, 549),
    ])
    opts = read_megastar_options(_FakeCtx(m), None)
    assert len(opts) == 2
    assert opts[0].idx == 0 and opts[0].char_id == '花火'
    assert opts[1].idx == 1 and opts[1].char_id == '星期日'


def test_read_megastar_options_no_candidates_empty() -> None:
    """非巨星屏(无「盛会之星一X」候选)→ [](handler 退默认 idx0)。"""
    assert read_megastar_options(_FakeCtx({}), None) == []


# ==================== node_boss(boss 槽 SIFT) ====================

_BOSS_ROW_FIXTURE = Path(__file__).parent / 'cw_node_row_boss.png'


def _load_fixture_rgb() -> np.ndarray:
    img = _imdecode_rgb(_BOSS_ROW_FIXTURE)
    assert img is not None, f'fixture 缺失: {_BOSS_ROW_FIXTURE}'
    return img


def test_boss_templates_full_load() -> None:
    """boss 头像库 20 件全加载,命名 = BOSS_MECHANICS 规范名(20/20 对齐)。"""
    from sr_od.application.currency_war.data.cw_enemy_data import BOSS_MECHANICS
    bt = load_boss_templates(_BOSS_TPL_DIR)
    assert set(bt.keys()) == set(BOSS_MECHANICS.keys()), \
        f'模板库与注册表不对齐: {set(bt.keys()) ^ set(BOSS_MECHANICS.keys())}'


def test_boss_slot_recognized_on_live_frame() -> None:
    """实机帧(1-1 备战,9 槽):最右槽 SIFT 命中 巨鹿生物制药(佩佩局
    简报真值 plane_bosses[0] 同源互证);boss 槽 Hu 类型被覆盖(None)。"""
    tpls = load_node_type_templates(_NODE_TPL_DIR)
    bt = load_boss_templates(_BOSS_TPL_DIR)
    slots = classify_node_row(_load_fixture_rgb(), tpls, boss_templates=bt)
    assert len(slots) == 9, f'9 槽(含 boss),得 {len(slots)}'
    boss_slot = slots[-1]
    assert boss_slot.boss == '巨鹿生物制药', \
        f'boss 应巨鹿生物制药(简报真值),得 {boss_slot.boss}'
    assert boss_slot.node_type is None, 'boss 槽 Hu 符号类型应被覆盖(头像圆撞 encounter 实锺)'


def test_boss_dynamic_slot_position() -> None:
    """boss=最右槽位置判(动态):把 fixture 裁掉最左一节点(模拟 invest-env
    增删节点变 8 槽),boss 槽仍在最右且识别不变——不锁槽号。"""
    tpls = load_node_type_templates(_NODE_TPL_DIR)
    bt = load_boss_templates(_BOSS_TPL_DIR)
    img = _load_fixture_rgb()
    trimmed = img[:, 96:]   # 去掉最左节点(~96px 槽距)
    slots = classify_node_row(trimmed, tpls, boss_templates=bt)
    assert len(slots) == 8, f'裁后 8 槽,得 {len(slots)}'
    assert slots[-1].boss == '巨鹿生物制药', '槽位变化后 boss 仍应命中(位置判不锁号)'


def test_no_boss_templates_graceful() -> None:
    """boss 模板缺载(目录空/未传)→ 最右槽走 Hu 普通判型,不崩。"""
    tpls = load_node_type_templates(_NODE_TPL_DIR)
    slots = classify_node_row(_load_fixture_rgb(), tpls, boss_templates=None)
    assert all(s.boss is None for s in slots), '无 boss 库时 boss 字段恒 None'


def test_upcoming_types_unchanged() -> None:
    """普通节点 Hu 判型不受 boss 分支影响(同帧类型分布锁;新带右界扩宽后
    idx7 reward 与 idx1 reward 分布一致)。"""
    tpls = load_node_type_templates(_NODE_TPL_DIR)
    bt = load_boss_templates(_BOSS_TPL_DIR)
    slots = classify_node_row(_load_fixture_rgb(), tpls, boss_templates=bt)
    upcoming = [s.node_type for s in slots[:-1] if s.state == 'upcoming']
    assert Counter(upcoming) == {'battle': 3, 'supply': 1, 'reward': 2, 'encounter': 1}
    assert next(s for s in slots if s.state == 'current').idx == 0


# ===== 位面详情节点带(区域-节点条@货币战争-位面详情,2026-08-26 用户权威坐标) =====

_PD_NODES_FIXTURE = Path(__file__).parent / 'cw_plane_detail_nodes.png'


def _load_pd_fixture_rgb() -> np.ndarray:
    img = _imdecode_rgb(_PD_NODES_FIXTURE)
    assert img is not None, f'fixture 缺失: {_PD_NODES_FIXTURE}'
    return img


def test_plane_detail_band_recognition() -> None:
    """位面详情节点带(9 圆):boss SIFT 巨鹿生物制药(与备战条同源互证)。

    带内语义与备战条不同:位面详情无高亮当前槽 S 峰 → 无 current 锚时
    HSV 单特征把节点判 past(低饱和预览态)→ 非 boss 槽不进 Hu(node_type
    全 None)。锁这个真实语义(boss 识别不依赖判态/类型,恒走位置判+SIFT)。
    """
    tpls = load_node_type_templates(_NODE_TPL_DIR)
    bt = load_boss_templates(_BOSS_TPL_DIR)
    slots = classify_node_row(_load_pd_fixture_rgb(), tpls, boss_templates=bt)
    assert len(slots) == 9
    assert slots[-1].boss == '巨鹿生物制药', \
        f'位面详情带 boss 应巨鹿生物制药,得 {slots[-1].boss}'
    # 无 current 锚(罕见)兜底路径下非 boss 槽全 past → 不进 Hu
    assert all(s.node_type is None for s in slots[:-1])


# ==================== node_validate(位面节点序列校验器) ====================


def _row(rn: int, nt: str, **kw) -> dict:
    d = {'run_id': 'run_test', 'round_num': rn, 'node_type': nt}
    d.update(kw)
    return d


def test_normal_full_run_passes() -> None:
    """正常局(众数模板,缺 r5 已知系统性缺失)全过、零脏行。"""
    rounds_present = [1, 2, 3, 4, 6, 7, 8, 9]   # r5 补给缺行是已知缺陷②,不在场不判
    rows = [_row(r, P1_NODE_TEMPLATE[r - 1]) for r in rounds_present]
    assert validate_p1_node_sequence(rows) == []


def test_variant_slot_deviation_downgraded() -> None:
    """变异槽(slot3/5/6 → r4/r6/r7)偏离标 variant_slot(非 template_mismatch)。"""
    dirty = validate_p1_node_sequence([
        _row(6, '遭遇'),    # r6 众数=普通战斗,slot5=变异位
    ])
    assert len(dirty) == 1
    assert dirty[0]['reason'] == 'variant_slot'
    assert dirty[0]['expected'] == '普通战斗'


def test_fixed_slot_mismatch_flagged() -> None:
    """固定槽偏离(如接管伪行 r1=普通战斗)标 template_mismatch。"""
    dirty = validate_p1_node_sequence([
        _row(1, '普通战斗'), _row(2, '奖励'),
    ])
    assert len(dirty) == 1
    assert dirty[0]['round_num'] == 1
    assert dirty[0]['reason'] == 'template_mismatch'
    assert dirty[0]['expected'] == '奖励'


def test_special_env_evidence_exonerates() -> None:
    """带特殊环境证据字段(invest-env 改节点/实读真值)的偏离不标脏。"""
    assert validate_p1_node_sequence([_row(1, '遭遇', special_env_evidence='人身意外险+补给')]) == []
    assert validate_p1_node_sequence([_row(4, '遭遇', node_source='live_read')]) == []


def test_plane_node_table_is_authority() -> None:
    """传开局帧实读槽序 → 以它为该局期望(变异位概念失效)。"""
    table = ['奖励', '奖励', '普通战斗', '遭遇', '补给', '补给', '遭遇', '奖励', 'boss']
    rows = [_row(4, '遭遇'), _row(6, '补给'), _row(1, '奖励')]
    assert validate_p1_node_sequence(rows, plane_node_table=table) == []
    # 与实读表冲突才算脏(原因不再降级 variant_slot)
    dirty = validate_p1_node_sequence([_row(4, '普通战斗')], plane_node_table=table)
    assert dirty == [{'run_id': 'run_test', 'round_num': 4, 'node_type': '普通战斗',
                      'expected': '遭遇', 'reason': 'template_mismatch'}]


def test_out_of_range_and_missing_field() -> None:
    """越界轮与缺字段行分别标 round_out_of_range / missing_field。"""
    dirty = validate_p1_node_sequence([
        _row(10, '奖励'), _row(0, '奖励'),
        {'run_id': 'run_test'},          # 缺 round_num/node_type
        _row('x', '奖励'),               # round_num 非数
    ])
    reasons = sorted(d['reason'] for d in dirty)
    assert reasons == ['missing_field', 'missing_field',
                       'round_out_of_range', 'round_out_of_range']


def test_takeover_fake_rows_caught_corpus_regression() -> None:
    """语料实锤回归:两异常局的接管伪行(P1r1 战斗/遭遇,真值 r6/r7)被捕获。"""
    rows = [
        _row(1, '普通战斗', run_id='run_20260823_151050'),
        _row(1, '遭遇', run_id='run_20260823_151913'),
    ]
    dirty = validate_p1_node_sequence(rows)
    assert len(dirty) == 2
    assert all(d['reason'] == 'template_mismatch' for d in dirty)
    assert {d['run_id'] for d in dirty} == {
        'run_20260823_151050', 'run_20260823_151913'}


def test_p2_interface_reserved() -> None:
    """P2 校验留接口:模板证据不足,显式 NotImplementedError 防误用。"""
    with pytest.raises(NotImplementedError):
        validate_p2_node_sequence([])


# ==================== bookcard_handler(书册卡处理链) ====================

# ===== ① 默认策略判据 =====


def test_policy_dominant_faction_match() -> None:
    """主力阵营同线优先:board 仙舟3(最大)→ 选仙舟卡(实机首例 2026-08-30 背书)。"""
    bonds = ['贝洛伯格', '星核猎手', '星核猎手', '仙舟']
    board = {'仙舟': 3, '持续伤害': 2, '击破': 1}
    assert choose_expert_index(bonds, board) == 3


def test_policy_secondary_faction_match() -> None:
    """无主力同线 → 退而选任一在场阵营同线的卡(凑档边际仍正)。"""
    bonds = ['贝洛伯格', '星核猎手', None, '仙舟']
    board = {'星核猎手': 1, '追击': 2}   # 主力=追击,无卡同线;星核猎手在场
    assert choose_expert_index(bonds, board) == 1


def test_policy_no_match_cash_fallback() -> None:
    """全无同线 → -1(现金为王经济兜底,不引入板外新阵营)。"""
    assert choose_expert_index(['贝洛伯格', '星核猎手'], {'仙舟': 3}) == -1


def test_policy_empty_board_cash_fallback() -> None:
    """board 空(读数失败)→ -1:选卡无依据时经济兜底优于盲选。"""
    assert choose_expert_index(['仙舟'], {}) == -1
    assert choose_expert_index([], {'仙舟': 3}) == -1


def test_policy_tie_deterministic() -> None:
    """并列最大计数取名字序首个(确定性,防跨轮抖动)。"""
    bonds = ['仙舟', '狼狩', None, None]
    board = {'仙舟': 2, '狼狩': 2}
    assert choose_expert_index(bonds, board) == 0   # sorted 后「仙舟」<「狼狩」


# ===== ② 书册卡模板在位判定 =====

_SLOTS = [r for _, r in _BENCH_SLOTS[:2]]   # 探针槽位 = 备战栏槽1-2(复用单一夹具)


def test_bookcard_template_loadable() -> None:
    """模板文件在位且可加载(灰度非 None);换名/移动路径即红。"""
    assert _get_bookcard_gray() is not None


def test_find_bookcards_hits_pasted_template() -> None:
    """灰度 TM 自检:模板贴进槽位画布 → find_bookcards 命中该槽(检测链通路)。"""
    tm = _get_bookcard_gray()
    assert tm is not None
    canvas = np.full((1080, 1920, 3), 40, dtype=np.uint8)
    rect = _SLOTS[1]
    h, w = tm.shape[:2]
    x = rect.x1 + (rect.x2 - rect.x1 - w) // 2
    y = rect.y1 + (rect.y2 - rect.y1 - h) // 2
    canvas[y:y + h, x:x + w, :] = tm[:, :, None]   # 灰度贴 3 通道画布(find_bookcards 内部自转灰度)
    hits = find_bookcards(canvas, list(enumerate(_SLOTS, 1)))
    assert [i for i, _ in hits] == [2], f'slot2 应命中,实得 {[i for i, _ in hits]}'


# ===== ③④ 注册与接线锁 =====


def test_invite_screen_registered_as_upper() -> None:
    """邀请函弹窗进 UPPER_SCREENS:弹窗在场 = 非备战帧(环不在弹窗上做备战动作)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    assert '货币战争-备战-专家邀请函' in cw_obs_core.UPPER_SCREENS


def test_bookcard_handler_wired() -> None:
    """停机钩子 → 自动处理链接线(失守事故 = 2026-08-30 bookcard_confirm 停机钩子
    退役后由本链接管,接线脱落即退回停机):cw_loop 引用 CwScreenExpertInvite,
    bail 扫描单一源已收拢至 registry(B 面切换):成员判定改为派生集三元组。"""
    from sr_od.application.currency_war.kernel.cw_overlay_registry import (
        derive_decision,
    )
    from sr_od.application.currency_war.operations import cw_loop
    assert 'CwScreenExpertInvite' in inspect.getsource(cw_loop)
    assert ('货币战争-备战-专家邀请函', '标识-专家邀请函', 'bookcard') in {
        (s.screen_name, s.anchor_area, s.bail_tag) for s in derive_decision()}


# ==================== test_reward_sphere(奖励球识别 + 防幻检) ====================

SCREEN = '货币战争-备战'
PANEL = Rect(1257, 140, 1662, 493)  # 区域-奖励(ground truth)


def _count(hits: list[tuple[str, object, int]], color: str) -> int:
    return sum(1 for c, _p, _r in hits if c == color)


def test_reward_spheres_8(test_context: SrTestContext) -> None:
    """8 球态:1 金 + 5 蓝 + 2 灰(VLM 逐球 ground truth 吻合)。"""
    if not test_context.has_screen(SCREEN, 'reward_spheres_8'):
        pytest.skip('fixture 缺:reward_spheres_8.webp')
    img = test_context.load_screen(SCREEN, 'reward_spheres_8')
    hits = find_reward_spheres(img, PANEL)
    assert len(hits) == 8, f'应 8 球,实得 {[(c, p.x, p.y) for c, p, r in hits]}'
    assert _count(hits, 'gold') == 1 and _count(hits, 'blue') == 5 and _count(hits, 'gray') == 2
    # 金球位置 ground truth(1333,184)±15
    gold = [p for c, p, r in hits if c == 'gold'][0]
    assert abs(gold.x - 1333) <= 15 and abs(gold.y - 184) <= 15


def test_reward_spheres_5(test_context: SrTestContext) -> None:
    """收 3 球后 5 球态:0 金 + 3 蓝 + 2 灰。"""
    if not test_context.has_screen(SCREEN, 'reward_spheres_5'):
        pytest.skip('fixture 缺:reward_spheres_5.webp')
    img = test_context.load_screen(SCREEN, 'reward_spheres_5')
    hits = find_reward_spheres(img, PANEL)
    assert len(hits) == 5 and _count(hits, 'blue') == 3 and _count(hits, 'gray') == 2, (
        f'应 3蓝2灰,实得 {[(c, p.x, p.y) for c, p, r in hits]}'
    )


def test_reward_spheres_4(test_context: SrTestContext) -> None:
    """收 4 球后 4 球态:0 金 + 2 蓝 + 2 灰。"""
    if not test_context.has_screen(SCREEN, 'reward_spheres_4'):
        pytest.skip('fixture 缺:reward_spheres_4.webp')
    img = test_context.load_screen(SCREEN, 'reward_spheres_4')
    hits = find_reward_spheres(img, PANEL)
    assert len(hits) == 4 and _count(hits, 'blue') == 2 and _count(hits, 'gray') == 2


def test_reward_spheres_empty_no_false_positive(test_context: SrTestContext) -> None:
    """空面板(球收完)0 误报(背景点阵/按钮不触发圆检测)。"""
    if not test_context.has_screen(SCREEN, 'reward_panel_empty'):
        pytest.skip('fixture 缺:reward_panel_empty.webp')
    img = test_context.load_screen(SCREEN, 'reward_panel_empty')
    assert find_reward_spheres(img, PANEL) == []


# ==================== 奖励域幻检交叉验证(防幻检批)====================
# 事故:奖励面板 ×12 礼盒蝴蝶结/扣饰被 Hough 幻检为 2 球 → 点击零消失 →
# ClickSpheres 同签名死循环至 DD-030 停机。三道修:纹理/亮度/半径门
# (本节)+ 两帧持存 + 点击后零消失黑名单。

def test_reward_giftbox_phantom_excluded(test_context: SrTestContext) -> None:
    """礼盒帧锁(停机哨兵帧入仓 fixture):×12 礼盒帧旧代码幻检 2 球
    (blue r56 + gray r15,即蝴蝶结/扣饰圆形)→ 新代码纹理/亮度门淘汰,
    返回 0 球;真球 fixture 计数不回退(由上方 4/5/8 球锁并行看守)。"""
    if not test_context.has_screen(SCREEN, 'reward_giftbox_phantom'):
        pytest.skip('fixture 缺:reward_giftbox_phantom.webp')
    img = test_context.load_screen(SCREEN, 'reward_giftbox_phantom')
    hits = find_reward_spheres(img, PANEL)
    assert hits == [], f'礼盒帧不得报球(幻检),实得 {[(c, p.x, p.y, r) for c, p, r in hits]}'


def test_filter_persistent_spheres_two_frame() -> None:
    """两帧持存真值表(纯函数):同位置同半径两帧 → 采信;仅单帧出现的
    瞬态假圆 → 淘汰;prev=None(首帧)→ 原样采信;半径容差内浮动不误杀。"""
    from sr_od.application.currency_war.obs.cw_identity_obs import (
        filter_persistent_spheres,
    )
    stable = ('blue', Point(1400, 300), 33)
    transient = ('gray', Point(1500, 200), 15)
    prev = [stable]
    cur = [stable, ('blue', Point(1402, 301), 35), transient]
    # 同帧近重复(位置/半径在容差内)= 同一球的抖动形态,不应双计:
    # 持存验证按「cur 中能找到 prev 匹配」逐条判,容差内两条都保留
    # (点球侧 minDist=35 已保证单帧不双检;此处只验持存语义)。
    out = filter_persistent_spheres(cur, prev)
    assert transient not in out, '单帧瞬态假圆必须被持存验证淘汰'
    assert out, '持存真球不得被误杀'
    assert filter_persistent_spheres(cur, None) == cur, '首帧无历史 → 原样采信'


def test_read_reward_spheres_phantom_blacklist_filter(
        test_context: SrTestContext, monkeypatch) -> None:
    """读侧黑名单过滤:点击后零消失登记的幻球坐标 → 后续 read 不再返回
    (ClickSpheres 由此获得「放弃该目标」出口,禁无限循环)。"""
    if not test_context.has_screen(SCREEN, 'reward_spheres_4'):
        pytest.skip('fixture 缺:reward_spheres_4.webp')
    img = test_context.load_screen(SCREEN, 'reward_spheres_4')
    base = find_reward_spheres(img, PANEL)
    assert len(base) == 4
    sess = type('S', (), {})()
    sess.reward_sphere_phantom_points = [base[0][1]]
    ctx = type('C', (), {'cw_match': type('M', (), {'session': sess})()})()
    monkeypatch.setattr(
        'sr_od.application.currency_war.obs.cw_identity_obs._area_rect',
        lambda *a, **k: PANEL)
    out = read_reward_spheres(ctx, img)
    assert len(out) == 3, f'黑名单坐标应被读侧过滤,实得 {[(c, p.x, p.y) for c, p, r in out]}'
    assert all(p != base[0][1] for _c, p, _r in out)


def test_click_spheres_zero_disappear_blacklists_phantom(monkeypatch) -> None:
    """点击后零消失 → 幻球登记(会话黑名单 + 分键),detail 携带黑名单痕迹;
    席满(无空位)时不拉黑(席满点不动 = 真球保留的既有裁定语义)。"""
    import sr_od.application.currency_war.prep_actions as pa

    sphere = ('blue', Point(1400, 300), 33)
    reads = {'n': 0}

    def _fake_read(ctx, screen, prev=None):
        reads['n'] += 1
        return [sphere]   # 点击前后恒在 = 零消失形态

    monkeypatch.setattr(pa, 'read_reward_spheres', _fake_read)
    monkeypatch.setattr(pa, 'read_supply_boxes', lambda ctx, screen: [])
    monkeypatch.setattr(pa.time, 'sleep', lambda s: None)
    # 备战席有空位(拉黑前置通过)
    monkeypatch.setattr(pa, 'row_area_centers', lambda ctx, prefix: [Point(400, 900)])
    import sr_od.application.currency_war.obs.currency_war_cv as cvmod
    monkeypatch.setattr(cvmod, 'slot_occupied', lambda scr, x, y: False)

    clicks = {'n': 0}

    class _Ctrl:
        def mouse_move(self, p): pass
        def click(self, p): clicks['n'] += 1

    class _Sess:
        last_state = None
        reward_sphere_phantom_points = None

    class _Op:
        def screenshot(self): return object()
        def park_cursor(self, **k): pass

    ex = pa.PrepActionExecutor.__new__(pa.PrepActionExecutor)
    ex._op = _Op()
    ex._ctx = type('C', (), {'controller': _Ctrl(),
                             'cw_match': SimpleNamespace(session=_Sess())})()
    ok, detail = ex._click_spheres(ClickSpheres(max_k=3))
    assert ok is False                       # 零消失 = 未推进
    assert clicks['n'] == 1
    assert '幻球' in detail and '黑名单' in detail
    pts = ex._ctx.cw_match.session.reward_sphere_phantom_points
    assert pts and abs(pts[0].x - 1400) <= 18 and abs(pts[0].y - 300) <= 18, \
        f'幻球坐标必须入会话黑名单,实得 {pts}'


# ==================== test_supply_box(补给箱识别) ====================

# 实机截图(1-9 备战,槽1=补给箱,槽2-9=角色;2026-08-14 采集)
_SHOT = r'.debug/sr_od_mcp/screenshot/screenshot_20260814_164308_173490.png'
# 拖箱槽1→槽2 后(箱在槽2 且带选中光效,TM 0.65 档回归用;2026-08-14 采集)
_SHOT_DRAG = r'.debug/sr_od_mcp/screenshot/screenshot_20260814_165941_733433.png'


def _slots() -> list[tuple[int, Rect]]:
    return list(_BENCH_SLOTS)


def _load(path: str) -> np.ndarray:
    """实机截图 → BGR 原样(find_supply_boxes 历史基线在 BGR 侧,内部自转灰度;
    本段不走 _imdecode_rgb —— 通道翻转改变 TM 彩色得分,不许动)。"""
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        pytest.skip(f'实机截图 fixture 缺: {path}')
    return img


def test_supply_box_hit_real_screenshot() -> None:
    """实机:槽1 箱子命中,槽2-9(角色)不误报。"""
    hits = find_supply_boxes(_load(_SHOT), _slots())
    assert [idx for idx, _p in hits] == [1], f'应只在槽1 命中,实得 {hits}'
    cx, cy = hits[0][1].x, hits[0][1].y
    assert abs(cx - 438) <= 3 and abs(cy - 912) <= 3, f'开启 center 应≈(438,912),实得 ({cx},{cy})'


def test_supply_box_after_drag_selected_glow() -> None:
    """拖动后(槽2 + 选中光效)仍命中:阈值 0.6 覆盖光效降分(~0.65)。"""
    hits = find_supply_boxes(_load(_SHOT_DRAG), _slots())
    assert [idx for idx, _p in hits] == [2], f'拖后应只在槽2 命中(光效态),实得 {hits}'


def test_supply_box_no_false_positive_on_empty() -> None:
    """合成空槽(纯色 + 噪声)不命中(防 placeholder 误报)。"""
    rng = np.random.default_rng(7)
    blank = np.full((1080, 1920, 3), 40, dtype=np.uint8)
    blank += rng.integers(0, 8, blank.shape, dtype=np.uint8)  # 低方差噪声
    assert find_supply_boxes(blank, _slots()) == []


def test_supply_box_threshold_margin() -> None:
    """分离度:箱槽 val 应超阈值,角色槽远低于(防阈值贴边脆断)。"""
    from sr_od.application.currency_war.obs.cw_identity_obs import (
        _SUPPLY_BOX_TM_THR,
        _get_supply_box_gray,
    )
    tm = _get_supply_box_gray()
    if tm is None:
        pytest.skip('补给箱模板缺(assets/template/currency_war/supply/补给箱.png)')
    gray = cv2.cvtColor(_load(_SHOT), cv2.COLOR_BGR2GRAY)
    box_val, char_max = 0.0, 0.0
    for i, r in _BENCH_SLOTS:
        crop = gray[r.y1:r.y2, r.x1:r.x2]
        _, mx, _, _ = cv2.minMaxLoc(cv2.matchTemplate(crop, tm, cv2.TM_CCOEFF_NORMED))
        if i == 1:
            box_val = mx
        else:
            char_max = max(char_max, mx)
    assert box_val >= _SUPPLY_BOX_TM_THR + 0.15, f'箱槽 val={box_val:.3f} 应超阈值 +0.15 余量'
    assert char_max <= _SUPPLY_BOX_TM_THR - 0.3, f'角色槽 max={char_max:.3f} 应低于阈值 -0.3 余量'


# ==================== w595_trial_reveal_card(试用角色揭示卡) ====================

_POS_FIXTURE = SCREENS / 'trial_reveal_w595.webp'


def _load_screen_fixture(name: str):
    img = read_image(str(SCREENS / name))
    assert img is not None, f'fixture 缺失:{name}'
    return img


def test_positive_frame_slot3_hit() -> None:
    """正样本帧(建档帧 slot3 发光卡)→ 双通道命中 slot3,且不误报其他槽。"""
    screen = _load_screen_fixture(_POS_FIXTURE.name)
    hits = find_trial_reveal_cards(screen, _BENCH_SLOTS)
    assert [i for i, _p in hits] == [3], f'应只命中 slot3,实得 {[i for i, _p in hits]}'


def test_negative_frames_no_false_positive() -> None:
    """既有备战 fixture(角色/箱/球/商店等)全槽零误报(双通道负样本分离度锁)。"""
    for name in ('r1_idle_stop.webp', 'shop_closed.webp',
                 'deployed_2star_bench1.webp', 'reward_spheres_8.webp'):
        screen = _load_screen_fixture(name)
        hits = find_trial_reveal_cards(screen, _BENCH_SLOTS)
        assert hits == [], f'{name} 误报:{hits}'


def test_tm_channel_separation() -> None:
    """TM 通道单通道独立命中正样本(阈值 0.5 的余量锁:正 ≥0.9 / 负 ≤0.26 标定)。"""
    from sr_od.application.currency_war.obs.cw_identity_obs import (
        _TRIAL_REVEAL_TM_THR,
        _get_trial_reveal_gray,
    )

    tm = _get_trial_reveal_gray()
    assert tm is not None, '模板缺失:assets/template/currency_war/supply/试用角色揭示卡.png'
    pos = _load_screen_fixture(_POS_FIXTURE.name)
    rect = _BENCH_SLOTS[2][1]
    crop = cv2.cvtColor(pos[rect.y1:rect.y2, rect.x1:rect.x2], cv2.COLOR_RGB2GRAY)
    val = cv2.minMaxLoc(cv2.matchTemplate(crop, tm, cv2.TM_CCOEFF_NORMED))[1]
    assert val >= max(0.9, _TRIAL_REVEAL_TM_THR), f'正样本 TM 掉到 {val:.3f}(发光帧模板失配?)'


# ===== summon 兜底豁免链(钩子层,mock 依赖;同 ADR-0263 测试手法) =====

_SLOT6 = _BENCH_SLOTS[5][1]


class _FakeRunContext:
    def __init__(self) -> None:
        self.stops: list[str] = []

    def stop_running(self, reason: str = '') -> None:
        self.stops.append(reason)


class _FakeOcrService:
    def get_ocr_result_list(self, **kwargs):   # noqa: ANN003 ARG003 兼容签名
        return []


class _HookCtx:
    def __init__(self) -> None:
        self.ocr_service = _FakeOcrService()
        self.run_context = _FakeRunContext()


def test_summon_hook_skips_trial_reveal_card(monkeypatch, tmp_path) -> None:
    """发光卡形态:slot 占用 + SIFT 不识别,但 find_trial_reveal_cards 命中
    → 归已知物品,不停机不采证(免费增益不再触发停机)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core, cw_observe
    from sr_od.application.currency_war.obs import currency_war_cv, cw_identity_obs
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.debug/temp/currency_war').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cw_identity_obs, 'identify_slots', lambda *a, **k: [])
    monkeypatch.setattr(cw_identity_obs, '_ctx_slots',
                        lambda ctx, prefix, count: [(6, _SLOT6)])
    monkeypatch.setattr(cw_identity_obs, 'find_supply_boxes', lambda screen, slots: [])
    monkeypatch.setattr(cw_identity_obs, 'find_tomes', lambda screen, slots: [])
    monkeypatch.setattr(cw_identity_obs, 'find_bookcards', lambda screen, slots: [])
    # 豁免源:揭示卡在 slot6 命中(接线锁——摘掉 _obj_slots 豁免行本测即红)
    monkeypatch.setattr(cw_identity_obs, 'find_trial_reveal_cards',
                        lambda screen, slots: [(6, Point(1061, 912))])
    monkeypatch.setattr(cw_identity_obs, '_area_rect',
                        lambda ctx, name, screen_name=None: None)
    monkeypatch.setattr(cw_obs_core, 'is_prep_like_frame', lambda ctx, screen: True)
    monkeypatch.setattr(currency_war_cv, 'slot_occupied', lambda screen, x, y: True)
    shots: list[str] = []
    monkeypatch.setattr(cw_observe, 'cw_shot_unique',
                        lambda screen, prefix: shots.append(prefix) or f'{prefix}.png')

    ctx = _HookCtx()
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    cw_identity_obs.read_bench_chars(ctx, screen, None)
    assert ctx.run_context.stops == []
    assert shots == []
    assert not (tmp_path / '.debug/temp/currency_war/summon_stop_hook.flag').exists()


def test_cw_loop_reveal_wiring_present() -> None:
    """行为接线锁:cw_loop 备战分支的揭示清场在场(防误删后退回停机/漏增益)。"""
    from sr_od.application.currency_war.operations import cw_loop

    src = inspect.getsource(cw_loop)
    assert 'find_trial_reveal_cards' in src, 'cw_loop 试用揭示卡清场接线被移除'


# ==================== w219_boss_collect_channel(简报/接管采集通道) ====================


def test_briefing_bosses_written_into_session() -> None:
    """否定墓碑(W971 P3 退役背书):cw_loop 的 ctx 信箱吸收段已退役。

    W971 P3(ctx 信箱退役,01-opening §1)后,简报唯一写点 =
    CwScreenBriefing 直写 session(行为侧由简报节点测试覆盖);
    本锁只钉退役语义:信箱 copy 接线消失是设计意图,禁回流。
    """
    from sr_od.application.currency_war.operations import cw_loop

    loop_src = inspect.getsource(cw_loop.CwLoop)
    assert 'self._absorb_ctx_mailbox' not in loop_src, 'ctx 信箱吸收段应已退役(W971 P3)'
    assert 'self.ctx.cw_briefing_bosses = None' not in loop_src


def test_briefing_read_side_cleans_and_overwrites() -> None:
    """锁②(改写,W971 P3b):读侧 LCS 清洗接线(防简称/形变直进 boss_fit)。"""
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_briefing

    src = inspect.getsource(cw_screen_briefing)
    assert 'clean_boss_names_by_lcs' in src, '简报读数未过 LCS 清洗(简称/形变直进 boss_fit)'


def test_plane_intel_takeover_refill_channel(test_context, monkeypatch) -> None:
    """行为锁(替代旧 3 条源码字面锁「session.briefing_bosses = _names /
    getattr 判空 / CwScreenPlaneIntel(self.ctx, start_plane=...)」):接管重采
    通道经真实入口 ``CwScreenPrep._takeover_collect_if_needed`` 验证——
    ①session 简报真值空时触发采集,备战帧现读位面作为 ``start_plane`` 传入
    子 op(2026-09-03 时序修正语义);②子 op 落中转池的实采以**保位写**
    (None 原样占槽,ADR-0398)载入 session.briefing_bosses,中转池取走清空;
    ③session.briefing_bosses 已有真值 → 不重复采(简报信任不被绕过)。
    失守场景 = 接管局失去重采通道(start_plane 不传/实采不落 session/空真值
    门失效反复重采)时本锁红;子 op 内部识别逻辑归其自身测试,不在此辖。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_plane_intel,
        cw_screen_prep,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        CwScreenPrep,
    )
    from test.harness.fixture_controller import fast_sleep

    start_planes: list[int] = []

    class _StubIntel:
        """位面详情子 op 桩:记录 start_plane;中转池由下方预置夹具承载
        (生产从 ctx.cw_plane_bosses 取走→session,桩不重复写池)。"""

        def __init__(self, ctx, start_plane: int = 0) -> None:
            start_planes.append(start_plane)

        def execute(self):
            return SimpleNamespace(success=True, status='stub')

    monkeypatch.setattr(cw_screen_plane_intel, 'CwScreenPlaneIntel', _StubIntel)
    monkeypatch.setattr(cw_screen_prep, 'read_node_sequence',
                        lambda ctx, screen: [SimpleNamespace()])
    monkeypatch.setattr(cw_screen_prep, 'read_phase_round',
                        lambda ctx, screen: (2, 3))
    monkeypatch.setattr(test_context, 'cw_plane_bosses',
                        ['巨鹿生物制药', None, '绘师家族产业'], raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_affixes', ['词缀甲'],
                        raising=False)

    d = CwScreenPrep(test_context)
    with fast_sleep():
        session = SimpleNamespace()
        res = d._takeover_collect_if_needed(SimpleNamespace(), session)
    assert start_planes == [2], (
        f'start_plane 须取备战帧现读位面传入子 op:{start_planes!r}')
    assert res is not None, '空真值门应触发采集并交回外循环'
    assert session.briefing_bosses == ['巨鹿生物制药', None, '绘师家族产业'], (
        f'实采须保位载入 session(None 原样占槽):{session.briefing_bosses!r}')
    assert getattr(exec_state_of(session), 'cw_takeover_collect_done', False) is True
    assert test_context.cw_plane_bosses is None \
        and test_context.cw_plane_affixes is None, '中转池须取走清空(防跨局泄漏)'

    # 简报真值已在 → 跳过门,不再采(开局局简报读得时不重复采)
    with fast_sleep():
        res_skip = d._takeover_collect_if_needed(
            SimpleNamespace(), SimpleNamespace(briefing_bosses=['已有真值']))
    assert res_skip is None and start_planes == [2], (
        'session.briefing_bosses 非空时不得重复采集(简报信任被绕过)')


def test_reconcile_wiring_in_collect_paths() -> None:
    """锁④(改写,W971 P3b 接管补采迁 cw_screen_prep):对账网接线在
    takeover 写回路径上仍在;director 补采块触发门 = 简报真值空(无简报
    读数可对账,对账自然缺省),写回接线不因块迁移丢失。"""
    from sr_od.application.currency_war.operations.cw_entry import (
        cw_entry_plane_intel,
    )

    assert 'reconcile_briefing_vs_plane_intel(' in inspect.getsource(
        cw_entry_plane_intel.CwEntryPlaneIntel.write_back), (
        'takeover 写回缺对账接线'
    )


def test_session_collected_bosses_flow_to_state_plane_bosses(monkeypatch) -> None:
    """行为锁(替代旧全句源码锁「state.plane_bosses = list(_sess.briefing_
    bosses) in src」;default 栈退役批重钉):session 填真值 → 走
    read_game_state 真链(观察层注入点,对 session 透传无条件注入)→
    state.plane_bosses 收到同序列(保位,None 原样)。失守场景 = 注入链再断
    (session 真值不再流向决策 state)时本锁红;空真值时不覆盖缺省(负面)。"""
    from sr_od.application.currency_war.obs import cw_observation as obs
    from sr_od.application.currency_war.obs.cw_observation import (
        PHASE_PREP_SHOP_OPEN,
    )
    # reader 桩面镜像 test_cw_obs_chain 同名手法:识别族全桩,零真 OCR
    _stubs = {
        'read_gold_settled': 55, 'read_phase_round': (2, 3), 'read_node_type': None,
        'read_xp_progress': (0, 6), 'read_level_raw_opt': 5, 'read_level_up_cost': 4,
        '_board_pairs': ({}, False), 'read_shop_cards': [], 'read_refresh_probs': None,
        'read_bench_full': None,
    }
    for _n, _v in _stubs.items():
        # _v 经关键字默认参绑定进 lambda(防 B023 循环变量晚绑定)
        monkeypatch.setattr(obs, _n,
                            (lambda _v: lambda *a, _v=_v, **kw: _v)(_v))

    session = SimpleNamespace(
        briefing_bosses=['巨鹿生物制药', None, '绘师家族产业'],
        briefing_affixes=None,
        active_strategies=[],
        last_level_obs=0,
        last_hp_real=None,
        last_streak=0,
        tracked_deployed=None,
    )
    ctx = SimpleNamespace(cw_match=SimpleNamespace(session=session))
    state = obs.read_game_state(ctx, None, phase=PHASE_PREP_SHOP_OPEN)
    assert state.plane_bosses == ['巨鹿生物制药', None, '绘师家族产业'], (
        f'session.briefing_bosses 须流入 state.plane_bosses(保位):'
        f'{state.plane_bosses!r}')

    # 负面:session 真值空 → 不覆盖 GameState 缺省(注入只在非空时)
    empty_ctx = SimpleNamespace(
        cw_match=SimpleNamespace(session=SimpleNamespace(
            briefing_bosses=None, briefing_affixes=None,
            active_strategies=[], last_level_obs=0, last_hp_real=None,
            last_streak=0, tracked_deployed=None)))
    state2 = obs.read_game_state(empty_ctx, None, phase=PHASE_PREP_SHOP_OPEN)
    assert not state2.plane_bosses, (
        f'空真值不得注入:{state2.plane_bosses!r}')


# ==================== w221_boss_locate_emblem(徽章态分流) ====================

_EMBLEM_FIXTURE = Path(__file__).parent / 'cw_plane_detail_emblem_full.png'
# 位面详情节点带(与 screen_info「货币战争-位面详情/区域-节点条」一致;yml 单一源,测试兜底)
_PD_BAND_RECT = (385, 514, 1596, 661)


def _load_emblem_fixture_rgb() -> np.ndarray:
    img = _imdecode_rgb(_EMBLEM_FIXTURE)
    assert img is not None, f'fixture 缺失: {_EMBLEM_FIXTURE}'
    return img


def test_emblem_band_zero_false_positive() -> None:
    """锁①:run30 徽章态带内 9 圆逐圆 SIFT 全拒(零假阳;身份缺失≠识别误报)。"""
    tpls = load_node_type_templates(_NODE_TPL_DIR)
    bt = load_boss_templates(_BOSS_TPL_DIR)
    assert len(bt) == 20, f'boss 模板库应 20 件(缺库会让全拒断言空过),得 {len(bt)}'
    img = _load_emblem_fixture_rgb()
    x1, y1, x2, y2 = _PD_BAND_RECT
    slots = classify_node_row(img[y1:y2, x1:x2], tpls, boss_templates=bt)
    assert len(slots) == 9, f'run30 位面1 带 9 圆,得 {len(slots)}'
    assert all(s.boss is None for s in slots), (
        f'徽章态带内不应有 boss 命中(得 {[s.boss for s in slots]})——假阳比缺数据危险'
    )


def test_emblem_detail_label_reads_boss(test_context: SrTestContext) -> None:
    """锁②:run30 帧详情条类型名 OCR 含「首领」(真实 OCR;定位验证锚)。"""
    from sr_od.application.currency_war.kernel.cw_obs_core import _area_rect

    if _area_rect(test_context, '文本-节点类型名', '货币战争-位面详情') is None:
        test_context.screen_loader.reload(from_separated_files=True)
    label = read_detail_node_type_label(test_context, _load_emblem_fixture_rgb())
    assert label is not None, '详情条类型名应可 OCR(锚缺失会让徽章态分流失效)'
    assert '首领' in label.replace(' ', ''), (
        f'点最右圆后详情条应显示首领节点类型,得 {label!r}(位置先验失效信号)'
    )


def test_conclude_plane_boss_matrix() -> None:
    """锁③:分流矩阵——头像态 record / 徽章态 skip(不 retry)/ 标签异常 retry。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_intel import (
        conclude_plane_boss,
    )

    # 头像态(run29 型):标签=首领 + SIFT 命中 → 记录真值
    assert conclude_plane_boss('首领节点', '深穹智械科技') == ('record', '深穹智械科技')
    # 徽章态(run30 型):标签=首领 + SIFT 未命中 → 记 None 跳过(**不得 retry 空转**)
    assert conclude_plane_boss('首领节点', None) == ('skip', None)
    assert conclude_plane_boss('首 领 节 点', None) == ('skip', None)   # OCR 空格容错
    # 标签未读出(过渡帧/OCR 失败)→ retry 等下帧(不得当徽章态误跳)
    act, _ = conclude_plane_boss(None, None)
    assert act == 'retry'
    act, _ = conclude_plane_boss('', '巨鹿生物制药')
    assert act == 'retry'
    # 点到的非首领节点(节点带误读/布局变)→ retry 兜底
    act, _ = conclude_plane_boss('奖励节点', None)
    assert act == 'retry'


def test_cw_loop_preserves_none_positions() -> None:
    """否定墓碑(W221/ADR-0397 退役背书):实采列表滤 None 回潮禁令——滤 None
    会让后续位面名字左移错序(「按序消费错位面」同病),旧形态
    ``[n for n in ... if n]`` 禁回流。

    W971 P3b:实采接线随接管补采迁 cw_screen_prep(单轮化后挂
    _takeover_collect_if_needed),锁随迁;保位写(None 原样 3 槽)的行为面
    由 test_plane_intel_takeover_refill_channel 经真实入口锁,此处只钉墓碑。
    """
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep

    src = inspect.getsource(cw_screen_prep.CwScreenPrep._takeover_collect_if_needed)
    assert '[n for n in self.ctx.cw_plane_bosses if n]' not in src, (
        '实采列表滤 None 回潮(徽章态位面 None 被丢→位面错序)'
    )


def test_boss_fit_tolerates_none_entries() -> None:
    """锁④伴生:boss_fit 跳过 None 项(保位列表下游);全 None → None(无信息,
    与空表同形,动态权重剔除)——不得把 None 传进 normalize_boss_name 崩溃。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY, boss_fit

    comp = COMP_LIBRARY[0]
    assert boss_fit(comp, [None, None, None]) is None
    full = boss_fit(comp, ['巨鹿生物制药', '增熵能源集团', '绘师家族产业'])
    holed = boss_fit(comp, [None, '增熵能源集团', '绘师家族产业'])
    assert full == holed, 'None 位应被跳过而非改变其余 boss 的判定'


# ==================== briefing_plane_order(简报位面序对账) ====================


def test_lcs_clean_maps_abbreviations_to_canonical() -> None:
    """简称(简报卡名常见形态)归一到规范公司名;已是规范名原样返回。"""
    from sr_od.application.currency_war.obs.cw_briefing_obs import (
        clean_boss_names_by_lcs,
    )

    out = clean_boss_names_by_lcs(['造梦互动', '深穹智械', '巨鹿生物制药'])
    assert out == ['造梦互动娱乐', '深穹智械科技', '巨鹿生物制药'], (
        f'LCS 归一结果不符预期:{out}'
    )


def test_lcs_clean_unmatched_passes_through_in_order() -> None:
    """归一不过阈值的读数原名透传(不硬猜),顺序原样保留(位面序不被打乱)。"""
    from sr_od.application.currency_war.obs.cw_briefing_obs import (
        clean_boss_names_by_lcs,
    )

    out = clean_boss_names_by_lcs(['XYZ', '绘师家族产业', '火线动力机甲'])
    assert out == ['XYZ', '绘师家族产业', '火线动力机甲'], f'透传/顺序被破坏:{out}'


def test_reconcile_pairs_mismatch_detectable() -> None:
    """逐位面配对:一致 True / 不可判 None / 不一致 False 三态齐全。"""
    from sr_od.application.currency_war.obs.cw_briefing_obs import (
        briefing_reconcile_pairs,
    )

    pairs = briefing_reconcile_pairs(
        ['造梦互动', None, '完全不同'],
        ['造梦互动娱乐', None, '绘师家族产业'])
    assert [(p['plane'], p['match']) for p in pairs] == [(1, True), (2, None), (3, False)], (
        f'配对三态不符:{pairs}'
    )


def test_reconcile_pairs_no_briefing_all_undecidable() -> None:
    """简报未读得(None)→ 全部不可判,不产生伪不一致。"""
    from sr_od.application.currency_war.obs.cw_briefing_obs import (
        briefing_reconcile_pairs,
    )

    pairs = briefing_reconcile_pairs(None, ['巨鹿生物制药', None, '绘师家族产业'])
    assert all(p['match'] is None for p in pairs), f'简报空读不应产生判定:{pairs}'


def test_reconcile_gate_default_on_and_persisted() -> None:
    """门控默认开(验证期积累配对证据),且 save() 持久化(yml 可关)。

    持久化走静态锁(inspect save 源码)——不真调 save(),避免测试写真实 config 目录。
    save() 漏字段的失守事故有先例(max_rounds/code_hash_gate 均曾漏 → GUI 保存静默抹掉
    yml 手写值,见 currency_war_config.save 内注释),本锁钉 briefing_reconcile 不重蹈。
    """
    from sr_od.application.currency_war.currency_war_config import CurrencyWarConfig

    cfg = CurrencyWarConfig()
    assert cfg.briefing_reconcile is True, '对账开关应默认开(验证期)'
    assert "'briefing_reconcile'" in inspect.getsource(CurrencyWarConfig.save), (
        '对账开关未持久化(yml 关不掉)'
    )
