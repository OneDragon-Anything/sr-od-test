"""货币战争 节点行类型识别 reader 测试(``cw_node_reader`` 纯 CV 核心)。

验证 ``classify_node_row`` 在 clean 节点行 fixture 上的识别(8 槽 + 三态 + Hu 匹配 4 类型)+
clean 帧门条件(非节点行 → 圆数 < ``_MIN_CLEAN_CIRCLES``)。**回归网**:锁定 reader 行为(阈值 /
模板 / Hu 变更会触发断言)。纯 CV(无 ctx/OCR);fixture = ``cw_node_row_clean.png``(1-1 备战节点行
裁图,8 槽,live-verified 同源)。门本身(``read_node_sequence`` len 检查)是 trivial 包装,这里验
门条件(classify 在非节点行的圆数);``read_node_sequence`` 的 OCR 当前节点覆盖另需 ctx,不在此测。
"""
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from sr_od.application.currency_war import cw_node_reader
from sr_od.application.currency_war.cw_node_reader import (
    classify_node_row,
    load_node_type_templates,
)
from sr_od.application.currency_war.cw_observation import _MIN_CLEAN_CIRCLES

# SR 仓 assets(cw_node_reader.py 在 src/sr_od/application/currency_war/ → parents[4] = 仓根)
_ASSETS = Path(cw_node_reader.__file__).resolve().parents[4] / 'assets' / 'game_data' / 'cw_node_types'
_FIXTURE = Path(__file__).parent / 'cw_node_row_clean.png'


def test_load_node_type_templates() -> None:
    """4 节点类型模板全加载(battle/supply/encounter/reward)。"""
    tpls = load_node_type_templates(_ASSETS)
    assert set(tpls.keys()) == {'battle', 'supply', 'encounter', 'reward'}


def test_classify_clean_node_row() -> None:
    """clean 节点行 fixture(1-1 备战,8 槽)→ 8 槽 + 1 当前/7 未来 + 未来 Hu 匹配 4 类型 + cy 已存。"""
    tpls = load_node_type_templates(_ASSETS)
    img = cv2.imdecode(np.fromfile(str(_FIXTURE), dtype=np.uint8), cv2.IMREAD_COLOR)
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
    # 未来类型分布(回归值:1-1 round1 未来 7 节点 = battle×4 / supply×1 / encounter×1 / reward×1)
    assert Counter(upcoming_types) == {'battle': 4, 'supply': 1, 'encounter': 1, 'reward': 1}
    # cy 已存(非 0,圆心 y 在行内 —— Task 2 采集图标定位依赖)
    assert all(s.cy > 0 for s in slots)


def test_gate_condition_non_node_row() -> None:
    """非节点行(空白小图)→ HoughCircles 检不出圆 → n < _MIN_CLEAN_CIRCLES(read_node_sequence 返 None 的门条件)。"""
    tpls = load_node_type_templates(_ASSETS)
    blank = np.zeros((100, 200, 3), dtype=np.uint8)                # 纯黑空白,无圆
    slots = classify_node_row(blank, tpls)
    assert len(slots) < _MIN_CLEAN_CIRCLES                         # 门条件成立 → 上层返 None 跳过坏帧
