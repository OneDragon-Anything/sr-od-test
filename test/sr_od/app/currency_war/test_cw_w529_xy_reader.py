# -*- coding: utf-8 -*-
"""W529 x/y(上场数/上限)读数器重写锁:位置感知解析 + 语义约束验证器。

设计出处:``cw_observation._read_deploy_paddle`` docstring + 58 帧 fixture 离线对拍
(``.debug/temp/currency_war/w529_xy_reader_impl/``,真值=VLM 逐帧亲读;批报告属易失
产物,语义出处以代码 docstring 为准)。旧解析层两个死穴:斜杠被 OCR 读成数字
('717'=7/7)时整串正则全崩;左侧人形图标并入 X('10/3'=0/3)。
"""
from pathlib import Path

import pytest

from test.conftest import SrTestContext
from sr_od.application.currency_war.cw_observation import (
    _read_deploy_paddle,
    _resolve_paddle_digits,
    _validate_paddle_xy,
    read_deploy_cap,
)

_FIX_DIR = Path(__file__).resolve().parents[4] / 'screens' / '货币战争-备战'


# ===== 约束验证器真值表(玩法先验:x≤y;1≤y≤13;y≥level) =====
def test_validate_paddle_xy_truth_table() -> None:
    """合法域内采,域外拒;level 未提供跳过 y≥level 条。"""
    assert _validate_paddle_xy(0, 3, None)
    assert _validate_paddle_xy(9, 10, 10)
    assert _validate_paddle_xy(13, 13, None)        # 绝对板面上界 13(前台4+后台9)
    assert not _validate_paddle_xy(4, 3, None)      # x>y 不可能(deployed>cap)
    assert not _validate_paddle_xy(0, 14, None)     # y 超 13(OCR 结构性误读上界)
    assert not _validate_paddle_xy(0, 0, None)      # y≥1(cap 至少为等级≥1)
    assert not _validate_paddle_xy(0, 3, 5)         # y<level(cap=level+宝钻,只增不减)
    assert _validate_paddle_xy(0, 5, 5)             # level 边界相等合法


# ===== 解析核心真值表(对齐 + 歧义裁决,纯构造不依赖 OCR) =====
def test_resolve_direct_alignment() -> None:
    """文本数字数==字形数且含斜杠 → 直接对齐。"""
    assert _resolve_paddle_digits('44', 2, 1, None, True)[:2] == (4, 4)
    assert _resolve_paddle_digits('1213', 4, 2, None, True)[:2] == (12, 13)


def test_resolve_icon_prefix_drop() -> None:
    """文本多 1 数字(图标/空心字形幻影前缀 '1')→ 去首对齐:'10/3'=0/3、'188'=8/8。"""
    assert _resolve_paddle_digits('103', 2, 1, None, True)[:2] == (0, 3)
    assert _resolve_paddle_digits('188', 2, 1, None, True)[:2] == (8, 8)
    assert _resolve_paddle_digits('1811', 3, 1, None, True)[:2] == (8, 11)


def test_resolve_slash_read_as_digit_prefers_direct() -> None:
    """斜杠被读成数字('717'=7/7):一级两候选歧义拒;二级 direct 候选唯一 → 采。"""
    # 一级:文本无斜杠,去首(1/7)与去斜杠位(7/7)双候选 → 拒
    x, y, cands = _resolve_paddle_digits('717', 2, 1, None, text_has_slash=False)
    assert (x, y) == (None, None)
    assert {(a, b) for a, b, _ in cands} == {(1, 7), (7, 7)}
    # 二级(抹图标重 OCR 读回斜杠):direct 唯一 → 采 7/7
    assert _resolve_paddle_digits('77', 2, 1, None, True)[:2] == (7, 7)


def test_resolve_ambiguous_split_rejected() -> None:
    """多候选全满足约束(如 '317' 无斜杠无二级)→ 歧义拒 None,不猜。"""
    x, y, cands = _resolve_paddle_digits('317', 2, 1, None, text_has_slash=False)
    assert (x, y) == (None, None)
    assert len({(a, b) for a, b, _ in cands}) == 2


def test_resolve_level_constraint_filters() -> None:
    """y<level 候选被滤:'103' 在 level=4 下唯一候选 0/3(y=3<4)被拒 → None。"""
    assert _resolve_paddle_digits('103', 2, 1, 4, True)[:2] == (None, None)
    assert _resolve_paddle_digits('103', 2, 1, 3, True)[:2] == (0, 3)   # level=3 边界内采


# ===== 真帧终态锁(fixture 驱动,模型不可用 → skip) =====
_EXPECTS = {
    'r1_idle_stop.webp': (0, 3),                # 图标前缀 '10/3' 变异(W287 同款)
    'shop_closed_a8_start.webp': (0, 3),        # 同上,编排者锚点
    '后排8槽-满级局.webp': (9, 10),             # 锚点;raw 'i9/10'
    '后排8槽-P3局.webp': (8, 11),               # raw '18/11'
    '后排8槽-全位验证.webp': (8, 8),             # raw '18/8'
    '后排8槽-双宝钻局.webp': (8, 9),             # 双宝钻 cap=level+2 实拍
    '攻略已应用.webp': (7, 7),                   # 斜杠读成数字 raw '717'(旧层死穴①)
    'char_detail.webp': (1, 6),
    'shop_closed.webp': (3, 4),
    'shop_closed_lowhp.webp': (6, 7),
    '补给节点.webp': (4, 4),                     # 补给面板帧 paddle 仍显示(VLM 亲读)
    'deployed_2star.webp': (4, 4),              # 干净直读基线
    'shop_open.png': (None, None),              # 菜单 overlay 遮挡 → None(不猜)
}


def _make_real_ocr_ctx(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> list:
    """真 OCR service 注入 + obs_conflict 收集器(防测试写真实 .debug 证据)。"""
    from one_dragon.base.matcher.ocr.ocr_service import OcrService
    from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
    import sr_od.application.currency_war.cw_observation as obs_mod
    try:
        matcher = OnnxOcrMatcher()
        if not matcher.init_model(download_by_github=False, download_by_gitee=True):
            pytest.skip('OCR 模型不可用')
    except Exception:
        pytest.skip('OCR 模型不可用')
    monkeypatch.setattr(test_context, 'ocr_service', OcrService(ocr_matcher=matcher))
    conflicts: list = []
    monkeypatch.setattr(obs_mod, 'obs_conflict',
                        lambda *a, **k: conflicts.append((a, k)))
    return conflicts


def test_read_deploy_paddle_real_fixtures(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """58 帧对拍代表集的终态锁:解析层对「图标前缀/斜杠读成数字/遮挡」全部读对。"""
    from one_dragon.utils import cv2_utils
    if not all((_FIX_DIR / n).exists() for n in _EXPECTS):
        pytest.skip('fixture 缺失')
    _make_real_ocr_ctx(test_context, monkeypatch)
    for name, expect in _EXPECTS.items():
        img = cv2_utils.read_image(str(_FIX_DIR / name))
        assert _read_deploy_paddle(test_context, img) == expect, f'{name} 应读 {expect}'


def test_read_deploy_cap_level_constraint_on_real_frame(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """level 参与解析层约束:cap 3/4 帧传 level=8(y<level)→ None 拒;level=3 → 4。"""
    from one_dragon.utils import cv2_utils
    p = _FIX_DIR / 'shop_closed.webp'
    if not p.exists():
        pytest.skip('fixture 缺失')
    _make_real_ocr_ctx(test_context, monkeypatch)
    img = cv2_utils.read_image(str(p))
    assert read_deploy_cap(test_context, img, level=3) == 4
    assert read_deploy_cap(test_context, img, level=8) is None


def test_covered_frame_leaves_conflict_evidence(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """双级均解析失败(overlay 遮 Y)→ (None, None) 且 obs_conflict 留证。"""
    from one_dragon.utils import cv2_utils
    p = _FIX_DIR / 'equip_detail_synth_target.webp'
    if not p.exists():
        pytest.skip('fixture 缺失')
    conflicts = _make_real_ocr_ctx(test_context, monkeypatch)
    img = cv2_utils.read_image(str(p))
    assert _read_deploy_paddle(test_context, img) == (None, None)
    assert len(conflicts) >= 1, '解析失败帧应留证(零重帧原则:不重截,只留证)'
