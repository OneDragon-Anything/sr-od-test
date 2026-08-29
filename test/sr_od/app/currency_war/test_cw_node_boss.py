# -*- coding: utf-8 -*-
"""boss 节点识别锁(2026-08-26 佩佩局实锺;用户权威带 544,24,1406,106)。

背景:旧 NODE_ROW_RECT 右界 1280 把 boss 圆(~x1354,r22)截在带外 → 生产
从未检出过 boss 节点。本批:带扩到含 boss(yml 单一源「区域-节点条」)、
NodeSlot.boss 字段、最右槽 SIFT 对拍 boss_avatar 20 模板(图鉴全彩模板
vs 节点红框小图跨渲染态,TM 五版实证不可行;SIFT 局部特征,实锺巨鹿
生物制药 5:1 断层)。**动态槽位**:boss=最右槽,不锁槽号(invest-env 增
删节点不破坏识别)。

fixture = cw_node_row_boss.png(1-1 备战节点条裁图,9 槽:1 当前奖励 +
7 未来 + 最右 boss 巨鹿生物制药;live-verified,与 read_node_sequence
同带同源)。
"""
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from sr_od.application.currency_war.obs import cw_node_reader
from sr_od.application.currency_war.obs.cw_node_reader import (
    classify_node_row,
    load_boss_templates,
    load_node_type_templates,
)

# cw_node_reader.py 在 src/sr_od/application/currency_war/obs/(期 2 obs 桶归位)→ parents[5] = 仓根
_ASSETS = Path(cw_node_reader.__file__).resolve().parents[5] / 'assets'
_NODE_TPL_DIR = _ASSETS / 'game_data' / 'cw_node_types'
_BOSS_TPL_DIR = _ASSETS / 'template' / 'currency_war' / 'boss_avatar'
_FIXTURE = Path(__file__).parent / 'cw_node_row_boss.png'


def _load_fixture_rgb():
    img_bgr = cv2.imdecode(np.fromfile(str(_FIXTURE), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 缺失: {_FIXTURE}'
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)   # 生产语义:RGB


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

_PD_FIXTURE = Path(__file__).parent / 'cw_plane_detail_nodes.png'


def _load_pd_fixture_rgb():
    img_bgr = cv2.imdecode(np.fromfile(str(_PD_FIXTURE), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 缺失: {_PD_FIXTURE}'
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


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
    img = cv2_utils.read_image(str(Path('.debug/sr_od_mcp/screenshot/'
                                        'screenshot_20260826_190830_854104.png')))
    # 全帧(函数自己按 yml 裁带)
    slots = cw_observation.read_plane_detail_nodes(ctx, img)
    assert slots is not None and len(slots) == 9
    assert slots[-1].boss == '巨鹿生物制药'
