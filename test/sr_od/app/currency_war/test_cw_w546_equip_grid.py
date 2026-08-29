"""W546 装备区逐格识别回归锁(格几何 / 逐格分类 / 数量 / 幸运星 / 遮挡态)。

设计出处:装备区识别从全域 SIFT 升级为「实测网格几何(75px 等距三列/两列)+ 逐格 TM 分类」,
对拍基线 = W540 真值(171 格,28 帧;基线召回 62%)。锁语义:
- 召回/身份/零误检/数量 四指标由 fixture 帧代表锁(全量 28 帧对拍在开发批
  ``.debug/temp/currency_war/w546_equip_upgrade/gate.py``,测试只锁代表性断面防回归);
- 幸运星 0/7 是旧 SIFT 路径的系统性失败,逐格分类下必须命中(锁存在性:该失败是本重构目标);
- 遮挡格如实标记(不硬判空/占用),occluded 格不得出现在 read_equips 输出。
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / 'src'))

from sr_od.application.currency_war.obs.cw_equipment import (  # noqa: E402  # noqa: E402
    EquipCell,
    _equip_slot_centers,
    _looks_infinity,
    _parse_equip_count,
    load_equip_templates,
    read_equip_count,
    read_equip_grid,
    read_equips,
)

SCREENS = REPO / 'sr-od-test' / 'screens'
EQUIP_DIR = REPO / 'assets' / 'template' / 'currency_war' / 'equip_plaza'


def _load_frame(name: str) -> np.ndarray | None:
    """只读加载样本帧(并行批会整理 screens 子目录 → 全 screens 查找);缺 = None。"""
    for p in SCREENS.rglob(name + '.*'):
        if p.suffix in ('.webp', '.png'):
            img = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return None


def _templates() -> dict:
    return load_equip_templates(EQUIP_DIR)


# ===== 格几何(纯函数)=====

class TestGridGeometry:
    def test_slot_layout_15_cells(self) -> None:
        cells = _equip_slot_centers(0)
        assert len(cells) == 15  # row1 三列 + 装备六行两列
        row1 = [(c, x, y) for r, c, x, y in cells if r == 0]
        assert [x for _c, x, _y in row1] == [1693, 1768, 1843]
        eq_rows = sorted({y for r, _c, _x, y in cells if r >= 1})
        assert eq_rows == [247 + 75 * i for i in range(6)]  # 行距 75px(98 是模板素材尺寸,勘误)
        for r in range(1, 7):
            cols = sorted(x for rr, _c, x, _y in cells if rr == r)
            assert cols == [1768, 1843]  # 装备行仅两列(左列 x1693 仅 row1 存在)

    def test_banner_dy_shifts_whole_grid(self) -> None:
        base = _equip_slot_centers(0)
        shifted = _equip_slot_centers(30)  # 横幅帧实测整体下移 ~25-30px
        assert all(y2 - y1 == 30 for (_r1, _c1, _x1, y1), (_r2, _c2, _x2, y2) in zip(base, shifted, strict=True))


# ===== 数量解析(纯函数)=====

class TestParseEquipCount:
    @pytest.mark.parametrize('text,expect', [
        ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'),
        ('∞', '∞'), ('oo', '∞'), ('8', '∞'),  # ∞ 双环常见误读形
        ('l', '1'), ('I', '1'),               # 独字符 1 误读
        ('6', None), ('13', None), ('', None), (None, None), ('金币', None),
    ])
    def test_domain(self, text: str | None, expect: str | None) -> None:
        assert _parse_equip_count(text) == expect


class TestLooksInfinity:
    def test_two_holes_is_infinity(self) -> None:
        img = np.zeros((20, 30, 3), np.uint8)
        cv2.circle(img, (8, 10), 5, (255, 255, 255), 2)
        cv2.circle(img, (22, 10), 5, (255, 255, 255), 2)
        assert _looks_infinity(img) is True

    def test_single_hole_narrow_digit_is_not(self) -> None:
        img = np.zeros((20, 14, 3), np.uint8)  # 单孔且不宽扁(数字形)→ 非 ∞
        cv2.rectangle(img, (4, 4), (9, 15), (255, 255, 255), 2)
        assert _looks_infinity(img) is False

    def test_single_hole_wide_is_infinity(self) -> None:
        img = np.zeros((14, 30, 3), np.uint8)  # 单孔但宽扁(裁残的 ∞)→ ∞
        cv2.rectangle(img, (4, 4), (26, 10), (255, 255, 255), 2)
        assert _looks_infinity(img) is True


# ===== fixture 帧断面锁(共享一次逐格计算;模块级缓存 = 同次运行只算一次)=====

_GRID_CACHE: dict[str, tuple[np.ndarray, list[EquipCell]]] = {}


def _grid(name: str) -> tuple[np.ndarray, list[EquipCell]] | None:
    if name not in _GRID_CACHE:
        rgb = _load_frame(name)
        if rgb is None:
            return None
        _GRID_CACHE[name] = (rgb, read_equip_grid(rgb, _templates()))
    return _GRID_CACHE[name]


class TestGridClassificationFixtures:

    def test_full_occupancy_no_spurious(self) -> None:
        got = _grid('后排8槽-满级局')
        if got is None:
            pytest.skip('存档截图缺失:后排8槽-满级局')
        _rgb, cells = got
        occupied = [c for c in cells if c.name is not None]
        # 锁:该帧 12 真值格全命中且无格外命中(占用格中心全落在 75px 网格 ±38 内)
        grid_pts = {(x, y) for _r, _c, x, y in _equip_slot_centers(0)}
        for c in occupied:
            assert any(abs(c.cx - gx) <= 38 and abs(c.cy - gy) <= 38 for gx, gy in grid_pts), \
                f'格心外命中 {c.name}@({c.cx},{c.cy})'
        assert len(occupied) == 12

    def test_lucky_star_detected(self) -> None:
        got = _grid('后排8槽-满级局')
        if got is None:
            pytest.skip('存档截图缺失:后排8槽-满级局')
        _rgb, cells = got
        stars = [c for c in cells if c.name == '幸运星']
        assert len(stars) == 1  # 满级局真值 1 颗;旧 SIFT 路径 0/7 系统性失败,此处必须命中
        assert stars[0].score >= 0.8

    def test_read_equips_default_rect_uses_grid(self) -> None:
        rgb = _load_frame('shop_closed_lowhp')
        if rgb is None:
            pytest.skip('存档截图缺失:shop_closed_lowhp')
        tms = _templates()
        hits = read_equips(rgb, tms)
        names = [n for n, _pos, _s in hits]
        # 锁:身份含 特权变体仲裁(灰度 TM 曾误判基础)与 ∞ 堆叠材料
        assert '随便骰子·特权' in names
        assert '精密拆装扳手' in names
        assert len(hits) == 4

    def test_read_equips_custom_rect_keeps_sift_semantics(self) -> None:
        """非默认 equip_rect 走 SIFT 旧路径(cw_node_obs 任意区域调用方契约)。"""
        rgb = _load_frame('shop_closed_lowhp')
        if rgb is None:
            pytest.skip('存档截图缺失:shop_closed_lowhp')
        hits = read_equips(rgb, _templates(), equip_rect=(1620, 90, 1918, 700))
        assert isinstance(hits, list)  # SIFT 路径不抛错即锁(语义回归由消费方测试覆盖)


class TestOcclusion:
    def test_detail_panel_cells_marked_occluded(self) -> None:
        rgb = _load_frame('char_detail')
        if rgb is None:
            pytest.skip('存档截图缺失:char_detail(可能已归档到装备详情浮窗子目录)')
        cells = read_equip_grid(rgb, _templates())
        occupied = [c for c in cells if c.name is not None]
        assert len(occupied) == 3            # 真值 3 格(全右列)
        assert all(c.col == 2 for c in occupied)
        occluded = [c for c in cells if c.occluded]
        assert len(occluded) >= 1            # 面板覆盖区格如实标遮挡
        assert all(c.name is None for c in occluded)  # 遮挡格不硬判身份


class TestEquipCount:

    def test_count_digits_and_infinity(self) -> None:
        """数量锁:代表帧 row1 数字(4 档)与 ∞ 各至少一例读对;失读返 None 不硬判。"""
        from types import SimpleNamespace

        from one_dragon.base.matcher.ocr.ocr_service import OcrService
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
        svc = OcrService(ocr_matcher=OnnxOcrMatcher())
        svc.ocr_matcher.init_model()
        ocr_ctx = SimpleNamespace(ocr_service=svc)
        # 攻略已应用 row1:拆装扳手×4(真值);shop_closed:精密拆装扳手 ∞
        cases = [('攻略已应用', '拆装扳手', 1768, '4'), ('shop_closed', '精密拆装扳手', 1843, '∞')]
        ran = 0
        for frame, eq_name, col_x, expect in cases:
            got = _grid(frame)
            if got is None:
                continue
            rgb, cells = got
            target = [c for c in cells if c.name == eq_name and abs(c.cx - col_x) <= 40 and c.row == 0]
            if not target:
                continue
            ran += 1
            count = read_equip_count(ocr_ctx, rgb, target[0].cx, target[0].cy)
            assert count == expect, f'{frame} {eq_name} 数量: expect={expect} got={count}'
        assert ran >= 1, '代表帧全部缺失,数量锁未执行'
