"""货币战争 入口画面检测测试(fixture-based)。

TDD 实例(2026-08-04):锁 A8 修复(``StartCurrencyWarMatch`` 先点"返回最高职级"切最高难度)的
**检测前提** —— A5 子态 fixture 有"返回最高职级"、A8 子态(最高)没有。改 op / fixture / OCR 后重跑,
确保检测不回归。(op 节点的完整行为测试需序列 fixture harness,待补。)
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from cv2.typing import MatLike

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils

if TYPE_CHECKING:
    from test.conftest import SrTestContext


def _has_text(ctx: SrTestContext, screen: MatLike, kw: str) -> bool:
    """全屏 OCR,判断关键词是否出现(子串,容 OCR 分词差异)。"""
    texts = [m.data for m in
             ctx.ocr_service.get_ocr_result_list(image=screen, rect=Rect(0, 0, 1920, 1080))]
    return any(kw in t for t in texts)


def test_difficulty_confirm_a5_has_return_max(test_context, test_image_dir: Path) -> None:
    """A5 子态(默认,未在最高):"返回最高职级" 在 → op 应先点它切 A8。"""
    screen = cv2_utils.read_image(str(test_image_dir / 'currency_war_difficulty_confirm_a5.png'))
    assert _has_text(test_context, screen, '返回最高职级'), 'A5 子态应有"返回最高职级"按钮'
    assert _has_text(test_context, screen, '开始对局')


def test_difficulty_confirm_a8_no_return_max(test_context, test_image_dir: Path) -> None:
    """A8 子态(最高):"返回最高职级" 不在 → op 直接"开始对局"。"""
    screen = cv2_utils.read_image(str(test_image_dir / 'currency_war_difficulty_confirm_a8.png'))
    assert not _has_text(test_context, screen, '返回最高职级'), 'A8 子态不应有"返回最高职级"'
    assert _has_text(test_context, screen, '开始对局')
    assert _has_text(test_context, screen, 'A8'), '应识别为 A8 子态'
