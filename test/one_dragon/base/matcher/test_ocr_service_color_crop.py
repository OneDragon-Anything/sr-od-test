"""color_range 裁剪化路径锁(纯性能改造,对外语义不变)。

语义锁(2026-09-03):
- 裁剪坐标映射回全图坐标系(margin 扩边 + crop_image 越界钳制);
- rect 70% 过滤行为不变;
- 缓存 key 三态:同帧同区命中 / 同帧异区 miss / 异帧 miss;
- 无 color_range 的全图路径跨 rect 复用保持不变;
- crop_first 路径先裁后滤(纯性能,收到的图 = 恰好 rect 大小,无 margin)。
"""
import numpy as np
import pytest

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from one_dragon.base.matcher.ocr.ocr_matcher import OcrMatcher
from one_dragon.base.matcher.ocr.ocr_service import _COLOR_CROP_MARGIN, OcrService

CR = [[0, 0, 0], [255, 255, 255]]   # 广谱范围:白底图 inRange 后全保留


class _RecordingMatcher(OcrMatcher):
    """记录每次 ocr 收到的图尺寸;固定在收图坐标 (20,20)-(60,36) 返回 token 'T'。"""

    def __init__(self):
        super().__init__()
        self.shapes: list[tuple[int, int]] = []   # (h, w)

    def ocr(self, image, threshold: float = 0, merge_line_distance: float = -1):
        self.shapes.append((image.shape[0], image.shape[1]))
        return [OcrMatchResult(c=1.0, x=20, y=20, w=40, h=16, data='T')]


def _make_service() -> tuple[OcrService, _RecordingMatcher]:
    matcher = _RecordingMatcher()
    return OcrService(ocr_matcher=matcher), matcher


def _make_image(h: int = 300, w: int = 400) -> np.ndarray:
    return np.full((h, w, 3), 200, dtype=np.uint8)


def test_color_crop_maps_result_to_full_image_coords() -> None:
    """裁剪路径:小图 OCR 结果坐标 + 裁剪原点 = 全图坐标(margin 扩边参与钳制)。"""
    svc, matcher = _make_service()
    screen = _make_image()
    rect = Rect(100, 100, 180, 140)
    results = svc.get_ocr_result_list(image=screen, rect=rect, color_range=CR)
    # 收到的图 = rect + margin(2*15),未越界不钳制;rect 80x40 + 30 = 110x70
    assert matcher.shapes == [(40 + 2 * _COLOR_CROP_MARGIN, 80 + 2 * _COLOR_CROP_MARGIN)]
    # token 在收图坐标 (20,20,60,36) → 全图 (105,105,145,121),完全落在 rect 内保留
    assert len(results) == 1
    assert (results[0].center.x, results[0].center.y) == (125, 113)
    assert results[0].data == 'T'


def test_color_crop_rect_filter_unchanged() -> None:
    """rect 70% 过滤语义不变:映射后与 rect 重叠不足的结果仍被滤掉。"""
    svc, matcher = _make_service()
    screen = _make_image()
    # rect 右移 15:crop 原点 (200,200),token 映射到 (220,220,260,236) center (240,228)
    # 在 rect(215,215,275,255) 内 → 保留。再取一个仅边缘搭接的 rect 验证过滤。
    rect_keep = Rect(215, 215, 275, 255)
    results = svc.get_ocr_result_list(image=screen, rect=rect_keep, color_range=CR)
    assert len(results) == 1 and results[0].data == 'T'
    # rect 仅覆盖 token 左上角一小块(<70%):rect(225,225,235,235) 与 token
    # (220,220,260,236) 交 10x10=100,base=640 → 15% < 70% → 过滤
    rect_drop = Rect(225, 225, 235, 235)
    svc.clear_cache()
    results = svc.get_ocr_result_list(image=screen, rect=rect_drop, color_range=CR)
    assert results == []


@pytest.mark.parametrize('rect_b,same_frame,expect_ocr_cnt', [
    (Rect(100, 100, 180, 140), True, 1),    # 同帧同区同 color_range → 命中缓存
    (Rect(200, 200, 260, 240), True, 2),    # 同帧异区 → miss(裁剪路径按 rect 分条,防误命中)
    (Rect(100, 100, 180, 140), False, 2),   # 异帧(新数组新 id)→ miss
], ids=['same-frame-same-rect-hit', 'same-frame-other-rect-miss', 'other-frame-miss'])
def test_cache_key_states(rect_b: Rect, same_frame: bool, expect_ocr_cnt: int) -> None:
    """缓存 key 三态参数化:同帧同区命中;同帧异区 / 异帧 miss。"""
    svc, matcher = _make_service()
    screen = _make_image()
    svc.get_ocr_result_list(image=screen, rect=Rect(100, 100, 180, 140), color_range=CR)
    svc.get_ocr_result_list(
        image=screen if same_frame else _make_image(), rect=rect_b, color_range=CR)
    assert len(matcher.shapes) == expect_ocr_cnt


@pytest.mark.parametrize('color_range', [None, CR], ids=['no-cr', 'with-cr'])
def test_full_path_ocr_once_and_reuse(color_range: list | None) -> None:
    """无 rect 全图路径参数化(color_range 有 / 无):同帧全图 OCR 一次,收图恒为整帧,
    后续调用复用缓存。无 CR 时再叠加一个 rect 过滤调用,验证跨 rect 复用不变。"""
    svc, matcher = _make_service()
    screen = _make_image()
    svc.get_ocr_result_list(image=screen, rect=None, color_range=color_range)
    svc.get_ocr_result_list(image=screen, rect=None, color_range=color_range)
    if color_range is None:
        svc.get_ocr_result_list(image=screen, rect=Rect(100, 100, 180, 140), color_range=None)
    assert matcher.shapes == [(300, 400)]   # 全图只识别一次(整帧收图),其余调用走缓存


def test_crop_first_receives_exact_rect_no_margin() -> None:
    """crop_first 路径:先裁后滤(纯性能),收图=恰好 rect 大小,无 margin 扩边。"""
    svc, matcher = _make_service()
    screen = _make_image()
    rect = Rect(100, 100, 180, 140)
    svc.get_ocr_result_list(image=screen, rect=rect, color_range=CR, crop_first=True)
    assert matcher.shapes == [(40, 80)]
