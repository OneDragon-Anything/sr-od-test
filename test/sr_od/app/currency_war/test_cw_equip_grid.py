"""W546 装备区逐格识别回归锁(格几何 / 逐格分类 / 数量 / 幸运星)。

设计出处:装备区识别从全域 SIFT 升级为「实测网格几何(75px 等距三列/两列)+ 逐格 TM 分类」,
对拍基线 = W540 真值(171 格,28 帧;基线召回 62%)。锁语义:
- 召回/身份/零误检/数量 四指标由 fixture 帧代表锁(全量 28 帧对拍在开发批
  ``.debug/temp/currency_war/w546_equip_upgrade/gate.py``,测试只锁代表性断面防回归);
- 幸运星 0/7 是旧 SIFT 路径的系统性失败,逐格分类下必须命中(锁存在性:该失败是本重构目标);
- 非干净备战不识别(硬不变量):画面状态判定在外层建档识别(角色详情/装备详情/
  装备浮窗各有独立建档、盖备战 id_mark),识别器纯识别、无画面守卫。
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / 'src'))

from sr_od.application.currency_war.obs.cw_equipment import (  # noqa: E402  # noqa: E402
    EquipCell,
    _detect_zone_dy,
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


class TestFillOrder:
    """栏内填充序剪枝(用户口述·权威,知识档 equipment_mechanics.md §5):
    row1 消耗品右→左;装备区右列自上而下、再左列;首空即停。"""

    def test_fill_order_slots_sequence(self) -> None:
        from sr_od.application.currency_war.obs.cw_equipment import _fill_order_slots
        tool_slots, equip_slots = _fill_order_slots(0)
        # row1 消耗品带:右→左(x 降序),col 2→1→0
        assert [s[2] for s in tool_slots] == [1843, 1768, 1693]
        assert [s[1] for s in tool_slots] == [2, 1, 0]
        # 装备区:右列(col2)自上而下 6 格 → 左列(col1)自上而下 6 格
        assert len(equip_slots) == 12
        assert [s[1] for s in equip_slots] == [2] * 6 + [1] * 6            # 列右→左
        assert [s[0] for s in equip_slots[:6]] == [1, 2, 3, 4, 5, 6]       # 右列上→下
        assert [s[0] for s in equip_slots[6:]] == [1, 2, 3, 4, 5, 6]       # 左列上→下

    def test_prune_stops_at_first_empty(self) -> None:
        """合成剪枝锁:遮挡左列(涂黑)后,右列满格照常识别、左列首空即停——
        结果 = 只含右列占用格(剪枝后不产出左列空格槽位)。"""
        rgb = _load_frame('后排8槽-满级局')
        if rgb is None:
            pytest.skip('存档截图缺失:后排8槽-满级局')
        masked = rgb.copy()
        masked[:, :1770] = 0   # 涂黑左列(col1 x1768 左侧)→ 左列全空
        cells = read_equip_grid(masked, _templates())
        assert all(c.col == 2 or c.row == 0 for c in cells if c.name is not None)
        # 满级局左列有占用格(真值 12 = 右列 6 + 左列 6),涂黑后左列首空即停
        occupied = [c for c in cells if c.name is not None]
        assert all(not (c.row >= 1 and c.col == 1) for c in occupied)


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


class TestTwoStateZoneDy:
    """两态候选档(「装备追踪中」标签位移几何)替代全档扫描的行为锁。

    实测事实(存档帧逐帧对拍):装备区垂直位移只有两态——无标签 δ=0、有标签 δ≈24;
    旧 14 档扫描在无标签帧给出的 -8/-4/8/20 等是 TM 平移不变性造成的分数平台噪声值。
    对齐自验判据 = 占用格峰心垂直偏移中位(分数不能作判据:错位 28px 帧部分重叠格仍
    0.93+,实测「攻略已应用」δ=0 档);自验失败落到下一档,两档皆败才全档扫描兜底。
    """

    def _bomb_scan(self, *_a, **_kw) -> int:
        raise AssertionError('兜底全档扫描不应触发(候选档内应解决;若红 = 对齐自验判据失效,性能优化被静默击穿)')

    def test_label_free_frame_first_candidate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """无标签帧:δ=0 首档即对齐 → 不触兜底,12 格真值不回归。"""
        rgb = _load_frame('后排8槽-满级局')
        if rgb is None:
            pytest.skip('存档截图缺失:后排8槽-满级局')
        monkeypatch.setattr(
            'sr_od.application.currency_war.obs.cw_equipment._detect_zone_dy', self._bomb_scan)
        cells = read_equip_grid(rgb, _templates())
        occupied = [c for c in cells if c.name is not None]
        assert len(occupied) == 12           # 与 TestGridClassificationFixtures 同源真值

    def test_labeled_frame_second_candidate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """有标签帧:δ=0 档峰心自验失败 → δ=24 档返回,9 格真值(row1 材料带 + 尾行)不丢。"""
        rgb = _load_frame('攻略已应用')
        if rgb is None:
            pytest.skip('存档截图缺失:攻略已应用')
        monkeypatch.setattr(
            'sr_od.application.currency_war.obs.cw_equipment._detect_zone_dy', self._bomb_scan)
        cells = read_equip_grid(rgb, _templates())
        got = {(c.row, c.col, c.name) for c in cells if c.name is not None}
        # 真值 = 旧全档扫描 δ=28 输出(两态批对拍一致);row1 两格与 5/6 行恰是
        # 错位档(δ=0)会因图标出窗丢失的格子——本锁钉住「第二档找回它们」
        assert got == {(0, 1, '冶金炉'), (0, 2, '拆装扳手'), (1, 1, '轮滑鞋'), (1, 2, '幸运星'),
                       (2, 2, '量产型装甲'), (3, 2, '量产型装甲'), (4, 2, '量产型装甲'),
                       (5, 2, '折叠小刀'), (6, 2, '和平手枪')}

    def test_fallback_scan_on_unknown_layout(self, monkeypatch: pytest.MonkeyPatch,
                                             caplog: pytest.LogCaptureFixture) -> None:
        """未知第三位移态 → 兜底扫描找回 + [cw!] 留痕。

        样本 = 合成帧(真实帧内容整体下移 12px):落在两档候选 ±8 对齐容忍域之外,
        必触发兜底;兜底扫描(4px 步进含 12)应选回 δ=12 并完整识别。不用被面板
        遮挡的存档帧作样本——那种帧在识别层入口就被整帧拒绝,到不了兜底。
        """
        rgb = _load_frame('后排8槽-满级局')
        if rgb is None:
            pytest.skip('存档截图缺失:后排8槽-满级局')
        shifted = np.vstack([np.zeros((12, rgb.shape[1], 3), np.uint8), rgb[:-12]])
        scan_calls: list[int] = []
        real_scan = _detect_zone_dy

        def _spy(screen, scaled) -> int:  # noqa: ANN001 (测试桩签名同被桩函数)
            dy = real_scan(screen, scaled)
            scan_calls.append(dy)
            return dy

        monkeypatch.setattr(
            'sr_od.application.currency_war.obs.cw_equipment._detect_zone_dy', _spy)
        with caplog.at_level(logging.INFO):
            cells = read_equip_grid(shifted, _templates())
        # 不锁兜底选中的 δ 值:TM 平移不变性使相邻档(±4px)总分构成平台,选档抖动
        # ±4px 是固有性质;裁片 ±20px 容忍内识别结果无损(实测 δ=8 与 δ=12 输出全同),
        # 故锁「触发一次 + 结果与原帧一致」这个行为本质
        assert len(scan_calls) == 1          # 兜底恰触发一次
        baseline = read_equip_grid(rgb, _templates())
        got = {(c.row, c.col, c.name) for c in cells if c.name is not None}
        want = {(c.row, c.col, c.name) for c in baseline if c.name is not None}
        assert got == want                   # 兜底后识别结果与原帧一致
        assert 'dy_fallback' in caplog.text  # [cw!] 留痕:未知布局态从日志第一时间暴露


class _ReplayCountOcr:
    """数量 OCR 回放桩:按裁片内容哈希查 fixture,返回真引擎录制原文;未命中 = 失读(空结果)。

    哈希键控保证语义不变:read_equip_count 的区域裁剪/变体管线任何改动使裁片内容变
    → 未命中 → 失读,与真引擎面对错裁片的行为一致——锁的仍是数量判读逻辑,非 OCR 引擎。
    """

    def __init__(self, table: dict[str, list[str]]) -> None:
        self._table = table

    def get_ocr_result_list(self, image, **_kw) -> list:
        key = hashlib.md5(np.ascontiguousarray(image).tobytes()).hexdigest()
        return [SimpleNamespace(data=text) for text in self._table.get(key, [])]


_COUNT_OCR_FIXTURE = Path(__file__).parent / 'fixtures' / 'w546_count_ocr_fixture.json'


def _count_fixture() -> dict:
    """数量锁识别结果 fixture:帧 → {cell: [cx, cy](真 read_equip_grid TM 峰心), ocr: {裁片哈希: [原文]}}。"""
    return json.loads(_COUNT_OCR_FIXTURE.read_text(encoding='utf-8'))


class TestEquipCount:

    def test_count_digits_and_infinity(self) -> None:
        """数量锁:代表帧 row1 数字(4 档)与 ∞ 各至少一例读对;失读返 None 不硬判。

        识别结果 fixture 解耦(原 20.3s 慢项治本;profile 实测主因 = read_equip_grid
        逐帧 TM 全库分类 ~7s/帧 × 两帧 + OCR 引擎装载推理,非判读逻辑本身):
        格心 = 真 read_equip_grid 的 TM 峰心一次性提取入库,OCR = 真引擎逐裁片录制
        原文按内容哈希回放;read_equip_count 全判读管线在真帧上原样执行。
        fixture 再生方式见同目录 fixtures/README.md。
        """
        fx = _count_fixture()
        # 攻略已应用 row1:拆装扳手×4(真值,格心 x=1847;col 1768 处实为 冶金炉——
        # 旧 case 列锚 1768 使数字支路长期静默跳过,本次按帧实况复活该支路);
        # shop_closed:精密拆装扳手 ∞
        cases = [('攻略已应用', '拆装扳手', 1847, '4'), ('shop_closed', '精密拆装扳手', 1843, '∞')]
        ran = 0
        for frame, eq_name, col_x, expect in cases:
            entry = fx.get(frame)
            rgb = _load_frame(frame) if entry is not None else None
            if entry is None or rgb is None:
                continue
            cx, cy = entry['cell']
            assert abs(cx - col_x) <= 40, f'{frame} 格心 ({cx},{cy}) 不在 case 声明列 {col_x} ±40 内(锚定漂移)'
            ran += 1
            ctx = SimpleNamespace(ocr_service=_ReplayCountOcr(entry['ocr']))
            count = read_equip_count(ctx, rgb, cx, cy)
            assert count == expect, f'{frame} {eq_name} 数量: expect={expect} got={count}'
        assert ran == len(cases), f'代表帧缺失,数量锁仅执行 {ran}/{len(cases)} 例(数字与 ∞ 两支路都必须实跑)'
