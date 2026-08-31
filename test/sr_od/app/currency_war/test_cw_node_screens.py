# -*- coding: utf-8 -*-
"""test_cw_node_screens 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
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
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== node_reader ====================

from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from sr_od.application.currency_war.obs import cw_node_reader
from sr_od.application.currency_war.obs.cw_node_reader import  classify_node_row, load_node_type_templates
from sr_od.application.currency_war.obs.cw_observation import _MIN_CLEAN_CIRCLES

# SR 仓 assets(cw_node_reader.py 在 src/sr_od/application/currency_war/obs/ → parents[5] = 仓根)
_ASSETS = Path(cw_node_reader.__file__).resolve().parents[5] / 'assets' / 'game_data' / 'cw_node_types'
_FIXTURE = Path(__file__).parent / 'cw_node_row_clean.png'


def test_load_node_type_templates() -> None:
    """节点类型模板全加载(battle/supply/encounter/reward + encounter_v2 变体聚合同 key)。"""
    tpls = load_node_type_templates(_ASSETS)
    assert set(tpls.keys()) == {'battle', 'supply', 'encounter', 'reward'}
    assert len(tpls['encounter']) == 2   # encounter + encounter_v2(r86 三叉箭头变体)


def test_classify_clean_node_row() -> None:
    """clean 节点行 fixture(1-1 备战,8 槽)→ 8 槽 + 1 当前/7 未来 + 未来 Hu 匹配 4 类型 + cy 已存。

    ⚠️ 通道对齐(review P1,2026-08-16):classify_node_row 语义 = **RGB**(框架截图链 BGRA2RGB);
    fixture 经 imdecode 读到 BGR → 测试先翻 RGB 再传(与生产 live 同侧)。
    """
    tpls = load_node_type_templates(_ASSETS)
    img_bgr = cv2.imdecode(np.fromfile(str(_FIXTURE), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img_bgr is not None
    img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)   # 生产语义:RGB
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
    tpls = load_node_type_templates(_ASSETS)
    blank = np.zeros((100, 200, 3), dtype=np.uint8)                # 纯黑空白,无圆
    slots = classify_node_row(blank, tpls)
    assert len(slots) < _MIN_CLEAN_CIRCLES                         # 门条件成立 → 上层返 None 跳过坏帧


# ==================== node_type_gate ====================

import sys
from pathlib import Path as _node_type_gate_Path

sys.path.insert(0, str(_node_type_gate_Path(__file__).resolve().parents[5] / 'src'))

from sr_od.application.currency_war.obs.cw_observation import  _BOSS_MIN_ROUND, _NODE_LABEL_X_TOL, gate_node_type


def test_boss_round_gate_rejects_upcoming_boss_label():
    """2-7 实证:round=7 读到「首领」(即将到来的 boss 节点标签)→ None。
    r80 审计 a 收紧:round=8 同样拒(boss=第 9 轮;人身意外险+补给后 ≥10,取 9 下限)。"""
    assert gate_node_type('boss', 7) is None
    assert gate_node_type('boss', 8) is None   # 收紧:与 boss 相邻的前置轮,标签更早出现
    assert gate_node_type('boss', 1) is None
    assert gate_node_type('boss', None) is None   # 轮次读不到 → 不信 boss


def test_boss_round_gate_passes_real_boss_round():
    """真 boss 轮(位面最后节点 = 第 9 轮)→ 放行。"""
    assert gate_node_type('boss', 9) == 'boss'
    assert _BOSS_MIN_ROUND == 9


def test_label_position_gate_rejects_mismatch():
    """标签 x=1341(即将到来的 boss 节点)vs 当前槽 cx≈900 → 错位 > 容差 → None。"""
    assert abs(1341 - 900) > _NODE_LABEL_X_TOL   # 实证数据确超容差
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


# ==================== node_obs ====================

from types import SimpleNamespace

from sr_od.application.currency_war.obs.cw_node_obs import read_encounter_options


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


def test_read_megastar_options_parses_candidates() -> None:
    """D-95:巨星候选「盛会之星一X先生/女士!」→ MegastarOption(char_id=X),按 x 左→右 idx。

    baseline cw_megastar OCR(2026-08-07):花火(左 822)+ 星期日(右 1061)。容错半角叹号。
    """
    from sr_od.application.currency_war.obs.cw_node_obs import read_megastar_options

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
    from sr_od.application.currency_war.obs.cw_node_obs import read_megastar_options

    assert read_megastar_options(_FakeCtx({}), None) == []


# ==================== node_boss ====================

from collections import Counter as _node_boss_Counter
from pathlib import Path as _node_boss_Path

import cv2 as _node_boss_cv2
import numpy as _node_boss_np

from sr_od.application.currency_war.obs import cw_node_reader as _node_boss_cw_node_reader
from sr_od.application.currency_war.obs.cw_node_reader import  classify_node_row as _node_boss_classify_node_row, load_boss_templates, load_node_type_templates as _node_boss_load_node_type_templates

# _node_boss_cw_node_reader.py 在 src/sr_od/application/currency_war/obs/(期 2 obs 桶归位)→ parents[5] = 仓根
_node_boss_ASSETS = _node_boss_Path(_node_boss_cw_node_reader.__file__).resolve().parents[5] / 'assets'
_NODE_TPL_DIR = _node_boss_ASSETS / 'game_data' / 'cw_node_types'
_BOSS_TPL_DIR = _node_boss_ASSETS / 'template' / 'currency_war' / 'boss_avatar'
_node_boss_FIXTURE = _node_boss_Path(__file__).parent / 'cw_node_row_boss.png'


def _load_fixture_rgb():
    img_bgr = _node_boss_cv2.imdecode(_node_boss_np.fromfile(str(_node_boss_FIXTURE), dtype=_node_boss_np.uint8), _node_boss_cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 缺失: {_FIXTURE}'
    return _node_boss_cv2.cvtColor(img_bgr, _node_boss_cv2.COLOR_BGR2RGB)   # 生产语义:RGB


def test_boss_templates_full_load() -> None:
    """boss 头像库 20 件全加载,命名 = BOSS_MECHANICS 规范名(20/20 对齐)。"""
    from sr_od.application.currency_war.data.cw_enemy_data import BOSS_MECHANICS
    bt = load_boss_templates(_BOSS_TPL_DIR)
    assert set(bt.keys()) == set(BOSS_MECHANICS.keys()), \
        f'模板库与注册表不对齐: {set(bt.keys()) ^ set(BOSS_MECHANICS.keys())}'


def test_boss_slot_recognized_on_live_frame() -> None:
    """实机帧(1-1 备战,9 槽):最右槽 SIFT 命中 巨鹿生物制药(佩佩局
    简报真值 plane_bosses[0] 同源互证);boss 槽 Hu 类型被覆盖(None)。"""
    tpls = _node_boss_load_node_type_templates(_NODE_TPL_DIR)
    bt = load_boss_templates(_BOSS_TPL_DIR)
    slots = _node_boss_classify_node_row(_load_fixture_rgb(), tpls, boss_templates=bt)
    assert len(slots) == 9, f'9 槽(含 boss),得 {len(slots)}'
    boss_slot = slots[-1]
    assert boss_slot.boss == '巨鹿生物制药', \
        f'boss 应巨鹿生物制药(简报真值),得 {boss_slot.boss}'
    assert boss_slot.node_type is None, 'boss 槽 Hu 符号类型应被覆盖(头像圆撞 encounter 实锺)'


def test_boss_dynamic_slot_position() -> None:
    """boss=最右槽位置判(动态):把 fixture 裁掉最左一节点(模拟 invest-env
    增删节点变 8 槽),boss 槽仍在最右且识别不变——不锁槽号。"""
    tpls = _node_boss_load_node_type_templates(_NODE_TPL_DIR)
    bt = load_boss_templates(_BOSS_TPL_DIR)
    img = _load_fixture_rgb()
    trimmed = img[:, 96:]   # 去掉最左节点(~96px 槽距)
    slots = _node_boss_classify_node_row(trimmed, tpls, boss_templates=bt)
    assert len(slots) == 8, f'裁后 8 槽,得 {len(slots)}'
    assert slots[-1].boss == '巨鹿生物制药', '槽位变化后 boss 仍应命中(位置判不锁号)'


def test_no_boss_templates_graceful() -> None:
    """boss 模板缺载(目录空/未传)→ 最右槽走 Hu 普通判型,不崩。"""
    tpls = _node_boss_load_node_type_templates(_NODE_TPL_DIR)
    slots = _node_boss_classify_node_row(_load_fixture_rgb(), tpls, boss_templates=None)
    assert all(s.boss is None for s in slots), '无 boss 库时 boss 字段恒 None'


def test_upcoming_types_unchanged() -> None:
    """普通节点 Hu 判型不受 boss 分支影响(同帧类型分布锁;新带右界扩宽后
    idx7 reward 与 idx1 reward 分布一致)。"""
    tpls = _node_boss_load_node_type_templates(_NODE_TPL_DIR)
    bt = load_boss_templates(_BOSS_TPL_DIR)
    slots = _node_boss_classify_node_row(_load_fixture_rgb(), tpls, boss_templates=bt)
    upcoming = [s.node_type for s in slots[:-1] if s.state == 'upcoming']
    assert _node_boss_Counter(upcoming) == {'battle': 3, 'supply': 1, 'reward': 2, 'encounter': 1}
    assert next(s for s in slots if s.state == 'current').idx == 0


# ===== 位面详情节点带(区域-节点条@货币战争-位面详情,2026-08-26 用户权威坐标) =====

_PD_FIXTURE = _node_boss_Path(__file__).parent / 'cw_plane_detail_nodes.png'


def _load_pd_fixture_rgb():
    img_bgr = _node_boss_cv2.imdecode(_node_boss_np.fromfile(str(_PD_FIXTURE), dtype=_node_boss_np.uint8), _node_boss_cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 缺失: {_PD_FIXTURE}'
    return _node_boss_cv2.cvtColor(img_bgr, _node_boss_cv2.COLOR_BGR2RGB)


def test_plane_detail_band_recognition() -> None:
    """位面详情节点带(9 圆):boss SIFT 巨鹿生物制药(与备战条同源互证)。

    带内语义与备战条不同:位面详情无高亮当前槽 S 峰 → 无 current 锚时
    HSV 单特征把节点判 past(低饱和预览态)→ 非 boss 槽不进 Hu(node_type
    全 None)。锁这个真实语义(boss 识别不依赖判态/类型,恒走位置判+SIFT)。
    """
    tpls = _node_boss_load_node_type_templates(_NODE_TPL_DIR)
    bt = load_boss_templates(_BOSS_TPL_DIR)
    slots = _node_boss_classify_node_row(_load_pd_fixture_rgb(), tpls, boss_templates=bt)
    assert len(slots) == 9
    assert slots[-1].boss == '巨鹿生物制药', \
        f'位面详情带 boss 应巨鹿生物制药,得 {slots[-1].boss}'
    # 无 current 锚(罕见)兜底路径下非 boss 槽全 past → 不进 Hu
    assert all(s.node_type is None for s in slots[:-1])


def test_plane_detail_band_read_fn() -> None:
    """read_plane_detail_nodes 生产入口:yml 带(区域-节点条@位面详情屏)
    → 9 槽 + boss 巨鹿生物制药(端到端,含模板懒加载)。"""
    import pytest
    from sr_od.application.currency_war.obs import cw_observation
    from sr_od.context.sr_context import SrContext
    from one_dragon.utils import cv2_utils

    ctx = SrContext()
    ctx.screen_loader.reload(from_separated_files=True)
    # 模板缓存清零验懒加载路径(全局缓存可能被本文件其它测试预热)
    cw_observation._NODE_TYPE_TEMPLATES = None
    cw_observation._BOSS_TEMPLATES = None
    img = cv2_utils.read_image(str(_node_boss_Path('.debug/sr_od_mcp/screenshot/'
                                        'screenshot_20260826_190830_854104.png')))
    # 全帧(函数自己按 yml 裁带)
    slots = cw_observation.read_plane_detail_nodes(ctx, img)
    assert slots is not None and len(slots) == 9
    assert slots[-1].boss == '巨鹿生物制药'


# ==================== node_validate ====================

import pytest

from sr_od.application.currency_war.tools.cw_node_validate import  P1_NODE_TEMPLATE, validate_p1_node_sequence, validate_p2_node_sequence


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


# ==================== bookcard_handler ====================

import sys as _bookcard_handler_sys
from pathlib import Path as _bookcard_handler_Path

_REPO = _bookcard_handler_Path(__file__).resolve().parents[5]
_bookcard_handler_sys.path.insert(0, str(_REPO / 'src'))

import numpy as _bookcard_handler_np  # noqa: E402

from one_dragon.base.geometry.rectangle import Rect  # noqa: E402
from sr_od.application.currency_war.operations.handlers.handle_bookcard import (  # noqa: E402
    choose_expert_index,
)

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

_SLOTS = [Rect(382, 845, 495, 979), Rect(507, 844, 620, 978)]


def test_bookcard_template_loadable() -> None:
    """模板文件在位且可加载(灰度非 None);换名/移动路径即红。"""
    from sr_od.application.currency_war.obs import cw_identity_obs as cio
    assert cio._get_bookcard_gray() is not None


def test_find_bookcards_hits_pasted_template() -> None:
    """灰度 TM 自检:模板贴进槽位画布 → find_bookcards 命中该槽(检测链通路)。"""
    from sr_od.application.currency_war.obs import cw_identity_obs as cio
    tm = cio._get_bookcard_gray()
    assert tm is not None
    canvas = _bookcard_handler_np.full((1080, 1920, 3), 40, dtype=_bookcard_handler_np.uint8)
    rect = _SLOTS[1]
    h, w = tm.shape[:2]
    x = rect.x1 + (rect.x2 - rect.x1 - w) // 2
    y = rect.y1 + (rect.y2 - rect.y1 - h) // 2
    canvas[y:y + h, x:x + w, :] = tm[:, :, None]   # 灰度贴 3 通道画布(find_bookcards 内部自转灰度)
    hits = cio.find_bookcards(canvas, list(enumerate(_SLOTS, 1)))
    assert [i for i, _ in hits] == [2], f'slot2 应命中,实得 {[i for i, _ in hits]}'


# ===== ③④ 注册与接线锁 =====


def test_invite_screen_registered_as_upper() -> None:
    """邀请函弹窗进 UPPER_SCREENS:弹窗在场 = 非备战帧(环不在弹窗上做备战动作)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    assert '货币战争-备战-专家邀请函' in cw_obs_core.UPPER_SCREENS


def test_bookcard_handler_wired() -> None:
    """停机钩子 → 自动处理链接线:battle_loop 引用 HandleBookcard,
    prep_director 弹窗 bail 清单含 bookcard 标签。"""
    import inspect

    from sr_od.application.currency_war import prep_director
    from sr_od.application.currency_war.kernel.cw_overlay_registry import  derive_decision
    from sr_od.application.currency_war.operations import battle_loop
    assert 'HandleBookcard' in inspect.getsource(battle_loop)
    # bail 扫描单一源已收拢至 registry(B 面切换):成员判定改为派生集三元组
    assert ('货币战争-备战-专家邀请函', '标识-专家邀请函', 'bookcard') in {
        (s.screen_name, s.anchor_area, s.bail_tag) for s in derive_decision()}


# ==================== test_reward_sphere ====================

import pytest as _test_reward_sphere_pytest

from one_dragon.base.geometry.rectangle import Rect as _test_reward_sphere_Rect
from sr_od.application.currency_war.obs.cw_identity_obs import find_reward_spheres

if True:  # test_context fixture 类型
    from test.conftest import SrTestContext

SCREEN = '货币战争-备战'
PANEL = _test_reward_sphere_Rect(1257, 140, 1662, 493)  # 区域-奖励(ground truth)


def _count(hits: list[tuple[str, object, int]], color: str) -> int:
    return sum(1 for c, _p, _r in hits if c == color)


def test_reward_spheres_8(test_context: SrTestContext) -> None:
    """8 球态:1 金 + 5 蓝 + 2 灰(VLM 逐球 ground truth 吻合)。"""
    if not test_context.has_screen(SCREEN, 'reward_spheres_8'):
        _test_reward_sphere_pytest.skip('fixture 缺:reward_spheres_8.webp')
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
        _test_reward_sphere_pytest.skip('fixture 缺:reward_spheres_5.webp')
    img = test_context.load_screen(SCREEN, 'reward_spheres_5')
    hits = find_reward_spheres(img, PANEL)
    assert len(hits) == 5 and _count(hits, 'blue') == 3 and _count(hits, 'gray') == 2, (
        f'应 3蓝2灰,实得 {[(c, p.x, p.y) for c, p, r in hits]}'
    )


def test_reward_spheres_4(test_context: SrTestContext) -> None:
    """收 4 球后 4 球态:0 金 + 2 蓝 + 2 灰。"""
    if not test_context.has_screen(SCREEN, 'reward_spheres_4'):
        _test_reward_sphere_pytest.skip('fixture 缺:reward_spheres_4.webp')
    img = test_context.load_screen(SCREEN, 'reward_spheres_4')
    hits = find_reward_spheres(img, PANEL)
    assert len(hits) == 4 and _count(hits, 'blue') == 2 and _count(hits, 'gray') == 2


def test_reward_spheres_empty_no_false_positive(test_context: SrTestContext) -> None:
    """空面板(球收完)0 误报(背景点阵/按钮不触发圆检测)。"""
    if not test_context.has_screen(SCREEN, 'reward_panel_empty'):
        _test_reward_sphere_pytest.skip('fixture 缺:reward_panel_empty.webp')
    img = test_context.load_screen(SCREEN, 'reward_panel_empty')
    assert find_reward_spheres(img, PANEL) == []


# ==================== test_supply_box ====================

import cv2 as _test_supply_box_cv2
import numpy as _test_supply_box_np
import pytest as _test_supply_box_pytest

from one_dragon.base.geometry.rectangle import Rect as _test_supply_box_Rect
from sr_od.application.currency_war.obs.cw_identity_obs import find_supply_boxes

# 实机截图(1-9 备战,槽1=补给箱,槽2-9=角色;2026-08-14 采集)
_SHOT = r'.debug/sr_od_mcp/screenshot/screenshot_20260814_164308_173490.png'
# 拖箱槽1→槽2 后(箱在槽2 且带选中光效,TM 0.65 档回归用;2026-08-14 采集)
_SHOT_DRAG = r'.debug/sr_od_mcp/screenshot/screenshot_20260814_165941_733433.png'
_BENCH_RECTS = [  # screen_info 备战栏-1..9 pc_rect(ground truth)
    [382, 845, 495, 979], [507, 844, 620, 978], [632, 844, 743, 978],
    [757, 845, 869, 979], [882, 846, 995, 980], [1004, 847, 1118, 978],
    [1132, 846, 1244, 977], [1256, 845, 1368, 979], [1379, 844, 1493, 980],
]


def _slots() -> list[tuple[int, _test_supply_box_Rect]]:
    return [(i, _test_supply_box_Rect(*r)) for i, r in enumerate(_BENCH_RECTS, start=1)]


def _load(path: str) -> _test_supply_box_np.ndarray:
    img = _test_supply_box_cv2.imdecode(_test_supply_box_np.fromfile(path, _test_supply_box_np.uint8), _test_supply_box_cv2.IMREAD_COLOR)
    if img is None:
        _test_supply_box_pytest.skip(f'实机截图 fixture 缺: {path}')
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
    rng = _test_supply_box_np.random.default_rng(7)
    blank = _test_supply_box_np.full((1080, 1920, 3), 40, dtype=_test_supply_box_np.uint8)
    blank += rng.integers(0, 8, blank.shape, dtype=_test_supply_box_np.uint8)  # 低方差噪声
    assert find_supply_boxes(blank, _slots()) == []


def test_supply_box_threshold_margin() -> None:
    """分离度:箱槽 val 应超阈值,角色槽远低于(防阈值贴边脆断)。"""
    from sr_od.application.currency_war.obs.cw_identity_obs import  _SUPPLY_BOX_TM_THR, _get_supply_box_gray
    tm = _get_supply_box_gray()
    if tm is None:
        _test_supply_box_pytest.skip('补给箱模板缺(assets/template/currency_war/supply/补给箱.png)')
    gray = _test_supply_box_cv2.cvtColor(_load(_SHOT), _test_supply_box_cv2.COLOR_BGR2GRAY)
    box_val, char_max = 0.0, 0.0
    for i, r in enumerate(_BENCH_RECTS, start=1):
        crop = gray[r[1]:r[3], r[0]:r[2]]
        _, mx, _, _ = _test_supply_box_cv2.minMaxLoc(_test_supply_box_cv2.matchTemplate(crop, tm, _test_supply_box_cv2.TM_CCOEFF_NORMED))
        if i == 1:
            box_val = mx
        else:
            char_max = max(char_max, mx)
    assert box_val >= _SUPPLY_BOX_TM_THR + 0.15, f'箱槽 val={box_val:.3f} 应超阈值 +0.15 余量'
    assert char_max <= _SUPPLY_BOX_TM_THR - 0.3, f'角色槽 max={char_max:.3f} 应低于阈值 -0.3 余量'


# ==================== w595_trial_reveal_card ====================

from pathlib import Path as _w595_trial_reveal_card_Path

import numpy as _w595_trial_reveal_card_np

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect as _w595_trial_reveal_card_Rect
from one_dragon.utils.cv2_utils import read_image

TEST_DIR = _w595_trial_reveal_card_Path(__file__).parents[4]
SCREENS = TEST_DIR / 'screens' / '货币战争-备战'

# screen_info「货币战争-备战.备战栏-1..9」pc_rect(1080p;与 yml 同步,离线硬编码约定)
_BENCH_SLOTS: list[tuple[int, _w595_trial_reveal_card_Rect]] = [
    (1, _w595_trial_reveal_card_Rect(382, 845, 495, 979)),
    (2, _w595_trial_reveal_card_Rect(507, 844, 620, 978)),
    (3, _w595_trial_reveal_card_Rect(632, 844, 743, 978)),
    (4, _w595_trial_reveal_card_Rect(757, 845, 869, 979)),
    (5, _w595_trial_reveal_card_Rect(882, 846, 995, 980)),
    (6, _w595_trial_reveal_card_Rect(1004, 847, 1118, 978)),
    (7, _w595_trial_reveal_card_Rect(1132, 846, 1244, 977)),
    (8, _w595_trial_reveal_card_Rect(1256, 845, 1368, 979)),
    (9, _w595_trial_reveal_card_Rect(1379, 844, 1493, 980)),
]

_POS_FIXTURE = SCREENS / 'trial_reveal_w595.webp'


def _w595_trial_reveal_card_load(name: str):
    img = read_image(str(SCREENS / name))
    assert img is not None, f'fixture 缺失:{name}'
    return img


def test_positive_frame_slot3_hit() -> None:
    """正样本帧(建档帧 slot3 发光卡)→ 双通道命中 slot3,且不误报其他槽。"""
    from sr_od.application.currency_war.obs.cw_identity_obs import find_trial_reveal_cards

    screen = _w595_trial_reveal_card_load(_POS_FIXTURE.name)
    hits = find_trial_reveal_cards(screen, _BENCH_SLOTS)
    hit_slots = [i for i, _p in hits]
    assert 3 in hit_slots


def test_negative_frames_no_false_positive() -> None:
    """既有备战 fixture(角色/箱/球/商店等)全槽零误报(双通道负样本分离度锁)。"""
    from sr_od.application.currency_war.obs.cw_identity_obs import find_trial_reveal_cards

    for name in ('r1_idle_stop.webp', 'shop_closed.webp',
                 'deployed_2star_bench1.webp', 'reward_spheres_8.webp'):
        screen = _w595_trial_reveal_card_load(name)
        hits = find_trial_reveal_cards(screen, _BENCH_SLOTS)
        assert hits == [], f'{name} 误报:{hits}'


def test_tm_channel_separation() -> None:
    """TM 通道单通道独立命中正样本(阈值 0.5 的余量锁:正 ≥0.9 / 负 ≤0.26 标定)。"""
    import cv2

    from sr_od.application.currency_war.obs.cw_identity_obs import  _TRIAL_REVEAL_TM_THR, _get_trial_reveal_gray

    tm = _get_trial_reveal_gray()
    assert tm is not None, '模板缺失:assets/template/currency_war/supply/试用角色揭示卡.png'
    pos = _w595_trial_reveal_card_load(_POS_FIXTURE.name)
    rect = _BENCH_SLOTS[2][1]
    crop = cv2.cvtColor(pos[rect.y1:rect.y2, rect.x1:rect.x2], cv2.COLOR_RGB2GRAY)
    val = cv2.minMaxLoc(cv2.matchTemplate(crop, tm, cv2.TM_CCOEFF_NORMED))[1]
    assert val >= max(0.9, _TRIAL_REVEAL_TM_THR), f'正样本 TM 掉到 {val:.3f}(发光帧模板失配?)'


# ===== summon 兜底豁免链(钩子层,mock 依赖;同 ADR-0263 测试手法) =====

_SLOT6 = _w595_trial_reveal_card_Rect(1004, 847, 1118, 978)


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
    from sr_od.application.currency_war.obs import currency_war_cv, cw_identity_obs
    from sr_od.application.currency_war.kernel import cw_obs_core, cw_observe
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
    screen = _w595_trial_reveal_card_np.zeros((200, 300, 3), dtype=_w595_trial_reveal_card_np.uint8)
    cw_identity_obs.read_bench_chars(ctx, screen, None)
    assert ctx.run_context.stops == []
    assert shots == []
    assert not (tmp_path / '.debug/temp/currency_war/summon_stop_hook.flag').exists()


def test_battle_loop_reveal_wiring_present() -> None:
    """行为接线锁:battle_loop 备战分支的揭示清场在场(防误删后退回停机/漏增益)。"""
    import inspect

    from sr_od.application.currency_war.operations import battle_loop

    src = inspect.getsource(battle_loop)
    assert 'find_trial_reveal_cards' in src, 'battle_loop 试用揭示卡清场接线被移除'


# ==================== w219_boss_collect_channel ====================

import inspect


def test_briefing_bosses_copied_into_session() -> None:
    """锁①(改写):简报位面序真值 copy 进 session(接线在 loop __init__)。"""
    from sr_od.application.currency_war.operations import battle_loop

    src = inspect.getsource(battle_loop.CurrencyWarRunLoop)
    assert '_session.briefing_bosses = list(self.ctx.cw_briefing_bosses)' in src, (
        '简报真值→session copy 接线消失(boss_fit 失去开局输入,ADR-0397 勘误节)'
    )
    # ctx 简报槽无「取走清空」消费:槽保留作实采对账源;跨局残留由
    # HandleBriefing 每局重读覆写/读空清 None 兜住(该行为有专锁)。
    assert 'self.ctx.cw_briefing_bosses = None' not in src


def test_briefing_read_side_cleans_and_overwrites() -> None:
    """锁②(新):读侧 LCS 清洗接线 + 每局覆写/读空清 None(防跨局残留成假真值)。"""
    from sr_od.application.currency_war.operations.handlers import handle_briefing

    src = inspect.getsource(handle_briefing)
    assert 'clean_boss_names_by_lcs' in src, '简报读数未过 LCS 清洗(简称/形变直进 boss_fit)'
    assert 'self.ctx.cw_briefing_bosses = clean_boss_names_by_lcs(_bosses) if _bosses else None' in src, (
        '读侧覆写/清 None 兜底消失(跨局残留会被 loop copy 成假真值)'
    )


def test_collect_plane_intel_is_takeover_refill_channel() -> None:
    """锁③(语义更新):CollectPlaneIntel 实采写入端在(接管重采/读空兜底)。"""
    from sr_od.application.currency_war.operations import battle_loop

    src = inspect.getsource(battle_loop.CurrencyWarRunLoop)
    assert '_sess.briefing_bosses = _names' in src, (
        'CollectPlaneIntel 实采接线消失(接管场景失去重采通道)'
    )
    # 触发条件仍含「session.briefing_bosses 空」:开局局简报读得时 session 已由
    # __init__ 填(不重复采),接管局/读空时兜底——条件消失=简报信任被绕过。
    assert "not getattr(self.ctx.cw_match.session, 'briefing_bosses', None)" in src
    assert 'CollectPlaneIntel(self.ctx)' in src


def test_reconcile_wiring_in_both_collect_paths() -> None:
    """锁④(新):对账网接线在两条实采完成路径上都在(loop 内联块 + takeover 写回)。"""
    from sr_od.application.currency_war.operations import battle_loop
    from sr_od.application.currency_war.operations.entry import  takeover_collect_plane_intel

    assert 'reconcile_briefing_vs_plane_intel(' in inspect.getsource(battle_loop.CurrencyWarRunLoop), (
        'loop 内联实采块缺对账接线'
    )
    assert 'reconcile_briefing_vs_plane_intel(' in inspect.getsource(
        takeover_collect_plane_intel.TakeoverCollectPlaneIntel.write_back), (
        'takeover 写回缺对账接线'
    )


def test_session_collected_bosses_flow_to_state_plane_bosses() -> None:
    """锁⑤(原锁③保留;default 栈退役批重钉):session.briefing_bosses
    (位面序真值)→ state.plane_bosses。注入点已从 default update_target
    平移到观测层(cw_observation.read_game_state,对 session 透传无条件注入)
    ——重钉为源级锁,防注入链再断。"""
    import inspect

    from sr_od.application.currency_war.obs import cw_observation
    src = inspect.getsource(cw_observation)
    assert "state.plane_bosses = list(_sess.briefing_bosses)" in src, (
        '观测层注入点丢失:session.briefing_bosses 真值不再流向 state.plane_bosses'
    )


# ==================== w221_boss_locate_emblem ====================

import inspect as _w221_boss_locate_emblem_inspect
from pathlib import Path as _w221_boss_locate_emblem_Path
from typing import TYPE_CHECKING

import cv2 as _w221_boss_locate_emblem_cv2
import numpy as _w221_boss_locate_emblem_np

from one_dragon.utils import cv2_utils
from sr_od.application.currency_war.obs.cw_node_reader import  classify_node_row as _w221_boss_locate_emblem_classify_node_row, load_boss_templates as _w221_boss_locate_emblem_load_boss_templates, load_node_type_templates as _w221_boss_locate_emblem_load_node_type_templates

if TYPE_CHECKING:
    from test.conftest import SrTestContext

_w221_boss_locate_emblem_FIXTURE = _w221_boss_locate_emblem_Path(__file__).parent / 'cw_plane_detail_emblem_full.png'
_w221_boss_locate_emblem_ASSETS = _w221_boss_locate_emblem_Path(cv2_utils.__file__).resolve().parents[3] / 'assets'   # 仓根 assets
_w221_boss_locate_emblem_NODE_TPL_DIR = _w221_boss_locate_emblem_ASSETS / 'game_data' / 'cw_node_types'
_w221_boss_locate_emblem_BOSS_TPL_DIR = _w221_boss_locate_emblem_ASSETS / 'template' / 'currency_war' / 'boss_avatar'
#位面详情节点带(与 screen_info「货币战争-位面详情/区域-节点条」一致;yml 单一源,测试兜底)
_PD_BAND_RECT = (385, 514, 1596, 661)


def _w221_boss_locate_emblem_load_fixture_rgb() -> _w221_boss_locate_emblem_np.ndarray:
    img_bgr = _w221_boss_locate_emblem_cv2.imdecode(_w221_boss_locate_emblem_np.fromfile(str(_w221_boss_locate_emblem_FIXTURE), dtype=_w221_boss_locate_emblem_np.uint8), _w221_boss_locate_emblem_cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 缺失: {_FIXTURE}'
    return _w221_boss_locate_emblem_cv2.cvtColor(img_bgr, _w221_boss_locate_emblem_cv2.COLOR_BGR2RGB)   # 生产语义:RGB


def test_emblem_band_zero_false_positive() -> None:
    """锁①:run30 徽章态带内 9 圆逐圆 SIFT 全拒(零假阳;身份缺失≠识别误报)。"""
    tpls = _w221_boss_locate_emblem_load_node_type_templates(_w221_boss_locate_emblem_NODE_TPL_DIR)
    bt = _w221_boss_locate_emblem_load_boss_templates(_w221_boss_locate_emblem_BOSS_TPL_DIR)
    assert len(bt) == 20, f'boss 模板库应 20 件(缺库会让全拒断言空过),得 {len(bt)}'
    img = _w221_boss_locate_emblem_load_fixture_rgb()
    x1, y1, x2, y2 = _PD_BAND_RECT
    slots = _w221_boss_locate_emblem_classify_node_row(img[y1:y2, x1:x2], tpls, boss_templates=bt)
    assert len(slots) == 9, f'run30 位面1 带 9 圆,得 {len(slots)}'
    assert all(s.boss is None for s in slots), (
        f'徽章态带内不应有 boss 命中(得 {[s.boss for s in slots]})——假阳比缺数据危险'
    )


def test_emblem_detail_label_reads_boss(test_context: SrTestContext) -> None:
    """锁②:run30 帧详情条类型名 OCR 含「首领」(真实 OCR;定位验证锚)。"""
    from sr_od.application.currency_war.kernel.cw_obs_core import _area_rect
    from sr_od.application.currency_war.obs.cw_observation import read_detail_node_type_label

    if _area_rect(test_context, '文本-节点类型名', '货币战争-位面详情') is None:
        test_context.screen_loader.reload(from_separated_files=True)
    label = read_detail_node_type_label(test_context, _w221_boss_locate_emblem_load_fixture_rgb())
    assert label is not None, '详情条类型名应可 OCR(锚缺失会让徽章态分流失效)'
    assert '首领' in label.replace(' ', ''), (
        f'点最右圆后详情条应显示首领节点类型,得 {label!r}(位置先验失效信号)'
    )


def test_conclude_plane_boss_matrix() -> None:
    """锁③:分流矩阵——头像态 record / 徽章态 skip(不 retry)/ 标签异常 retry。"""
    from sr_od.application.currency_war.operations.handlers.collect_plane_intel import  conclude_plane_boss

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


def test_battle_loop_preserves_none_positions() -> None:
    """锁④:实采写 session 保位(None 不滤)——滤 None 会让后续位面名字左移错序
    (ADR-0397 修的「按序消费错位面」同病;旧形态 `[n for n in ... if n]` 禁回潮)。"""
    from sr_od.application.currency_war.operations import battle_loop

    src = _w221_boss_locate_emblem_inspect.getsource(battle_loop.CurrencyWarRunLoop)
    assert '[n for n in self.ctx.cw_plane_bosses if n]' not in src, (
        '实采列表滤 None 回潮(徽章态位面 None 被丢→位面错序)'
    )
    assert '_names = list(self.ctx.cw_plane_bosses)' in src, '实采应保位写 3 槽(None 原样)'


def test_boss_fit_tolerates_none_entries() -> None:
    """锁④伴生:boss_fit 跳过 None 项(保位列表下游);全 None → None(无信息,
    与空表同形,动态权重剔除)——不得把 None 传进 normalize_boss_name 崩溃。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY, boss_fit

    comp = COMP_LIBRARY[0]
    assert boss_fit(comp, [None, None, None]) is None
    full = boss_fit(comp, ['巨鹿生物制药', '增熵能源集团', '绘师家族产业'])
    holed = boss_fit(comp, [None, '增熵能源集团', '绘师家族产业'])
    assert full == holed, 'None 位应被跳过而非改变其余 boss 的判定'


# ==================== briefing_plane_order ====================

def test_lcs_clean_maps_abbreviations_to_canonical() -> None:
    """简称(简报卡名常见形态)归一到规范公司名;已是规范名原样返回。"""
    from sr_od.application.currency_war.obs.cw_briefing_obs import clean_boss_names_by_lcs

    out = clean_boss_names_by_lcs(['造梦互动', '深穹智械', '巨鹿生物制药'])
    assert out == ['造梦互动娱乐', '深穹智械科技', '巨鹿生物制药'], (
        f'LCS 归一结果不符预期:{out}'
    )


def test_lcs_clean_unmatched_passes_through_in_order() -> None:
    """归一不过阈值的读数原名透传(不硬猜),顺序原样保留(位面序不被打乱)。"""
    from sr_od.application.currency_war.obs.cw_briefing_obs import clean_boss_names_by_lcs

    out = clean_boss_names_by_lcs(['XYZ', '绘师家族产业', '火线动力机甲'])
    assert out == ['XYZ', '绘师家族产业', '火线动力机甲'], f'透传/顺序被破坏:{out}'


def test_reconcile_pairs_mismatch_detectable() -> None:
    """逐位面配对:一致 True / 不可判 None / 不一致 False 三态齐全。"""
    from sr_od.application.currency_war.obs.cw_briefing_obs import briefing_reconcile_pairs

    pairs = briefing_reconcile_pairs(
        ['造梦互动', None, '完全不同'],
        ['造梦互动娱乐', None, '绘师家族产业'])
    assert [(p['plane'], p['match']) for p in pairs] == [(1, True), (2, None), (3, False)], (
        f'配对三态不符:{pairs}'
    )


def test_reconcile_pairs_no_briefing_all_undecidable() -> None:
    """简报未读得(None)→ 全部不可判,不产生伪不一致。"""
    from sr_od.application.currency_war.obs.cw_briefing_obs import briefing_reconcile_pairs

    pairs = briefing_reconcile_pairs(None, ['巨鹿生物制药', None, '绘师家族产业'])
    assert all(p['match'] is None for p in pairs), f'简报空读不应产生判定:{pairs}'


def test_reconcile_gate_default_on_and_persisted() -> None:
    """门控默认开(验证期积累配对证据),且 save() 持久化(yml 可关)。

    持久化走静态锁(inspect save 源码)——不真调 save(),避免测试写真实 config 目录。
    """
    import inspect

    from sr_od.application.currency_war.currency_war_config import CurrencyWarConfig

    cfg = CurrencyWarConfig()
    assert cfg.briefing_reconcile is True, '对账开关应默认开(验证期)'
    assert "'briefing_reconcile'" in inspect.getsource(CurrencyWarConfig.save), (
        '对账开关未持久化(yml 关不掉)'
    )
