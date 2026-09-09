"""test_cw_shop_refresh_price 主题锁(ADR-0622 刷新钮标价现场识别通道)。

通道 = 商店开态「刷新」圆钮标价现场 OCR(reader ``cw_shop_refresh_obs.
read_shop_refresh_price``),shop_refresh_cost 字段的写端权威(设计文档
BoardState §3.3.6;识别失败=None 禁兜底;免费帧不写,None≠标价 0)。
退役通道的锁不在本文件:面板徽标旁证 = test_cw_obs_gates(ADR-0456);
「金币差倒推」已随 ADR-0622 退役(无锁,墓碑在 cw_shop_refresh_obs 模块头)。
"""
from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.rectangle import Rect
from sr_od.application.currency_war.obs.cw_shop_refresh_obs import (
    _parse_price_digit,
    read_shop_refresh_price,
)
from test.conftest import SrTestContext

# 归档帧(测试仓 screens/,1920×1080 原生;价格行跨帧像素稳定,离线对拍读数恒 2)
_SHOP_SCREEN_DIR = '货币战争-备战-开商店'
_SHOP_FRAMES = ('shop_open', 'shop_open_preview_star', '已锁定', '未锁定', '免战叠加态')
_PRICE_RECT = Rect(1584, 513, 1664, 558)   # = screen_info「文本-刷新价格」建档值


def _fake_ctx(ocr_results: list,
              ocr_fn: Callable[..., list] | None = None) -> SimpleNamespace:
    """带「文本-刷新价格」area 的假 ctx(screen_loader+ocr_service)。

    ocr_results 走 screen=None 透传约定(mock ocr_service 不承载像素,
    同 test_cw_invest_refresh._FakeCtx);传 ocr_fn 时以函数为准
    (两级管线回退等需按调用次序变化的场景)。
    """
    area = SimpleNamespace(area_name='文本-刷新价格', pc_rect=_PRICE_RECT)
    si = SimpleNamespace(area_list=[area])
    if ocr_fn is None:
        ocr_fn = lambda **kw: ocr_results  # noqa: E731
    return SimpleNamespace(
        screen_loader=SimpleNamespace(get_screen=lambda name: si),
        ocr_service=SimpleNamespace(get_ocr_result_list=ocr_fn),
    )


def _ocr_item(data: str) -> SimpleNamespace:
    return SimpleNamespace(data=data)


# ===== 解析纯函数层(规则修复矩阵;金字形渲染在册误读=图标并入前缀) =====

def test_parse_single_digit_normal() -> None:
    """一位标价直读:基价 2 / 长线利好降价后 1 / 上界 9 全收。"""
    assert _parse_price_digit(['2']) == 2
    assert _parse_price_digit(['1']) == 1
    assert _parse_price_digit(['9']) == 9


def test_parse_icon_merged_prefix() -> None:
    """金币图标并入数字态('G2'/'G0',G=图标;徽标 reader 同构实证
    cw_observation._parse_coin_fee_digit):数字位照常解出,纯图标 'GO'
    经 O→0 产出 0 落免费域拒信 → None(不得读成 0)。"""
    assert _parse_price_digit(['G2']) == 2
    assert _parse_price_digit(['GO']) is None
    assert _parse_price_digit(['G0']) is None


def test_parse_icon_split_scans_past_invalid() -> None:
    """图标与数字被拆成两条('GO'+'2'):首条产出 0 越界须继续扫下一条
    (首条定生死会丢真值);前条无数字('免费')同理。"""
    assert _parse_price_digit(['GO', '2']) == 2
    assert _parse_price_digit(['免费', '2']) == 2


def test_parse_zero_is_never_a_price() -> None:
    """免费帧语义锁(ADR-0622/§3.3.6:免费帧不写,None≠标价 0):
    OCR 产出 0(真 0 渲染或图标 O 形变)一律 None,禁读成 0。"""
    assert _parse_price_digit(['0']) is None


def test_parse_out_of_range_or_empty_is_none() -> None:
    """越界(两位数无在册证据,坏读不截位)/无数字/空 → None(禁兜底改值)。"""
    assert _parse_price_digit(['12']) is None
    assert _parse_price_digit(['99']) is None
    assert _parse_price_digit(['免费']) is None
    assert _parse_price_digit(['']) is None
    assert _parse_price_digit([]) is None


# ===== reader 全链(mock ocr;screen=None 透传约定) =====

def test_reader_baseline_reads_price() -> None:
    """全链:area 解析→放大 OCR→解析;正常读数 2。"""
    assert read_shop_refresh_price(_fake_ctx([_ocr_item('2')]), None) == 2


def test_reader_two_level_fallback_on_empty_first_level() -> None:
    """两级管线:第一级(3x 放大)读空 → 第二级(OTSU)重试出值;
    只调一级不消费第二级 = 接线断裂。"""
    calls = {'n': 0}

    def by_call(**kw: object) -> list:
        calls['n'] += 1
        return [] if calls['n'] == 1 else [_ocr_item('3')]

    assert read_shop_refresh_price(_fake_ctx([], ocr_fn=by_call), None) == 3
    assert calls['n'] == 2, '第一级空后必须实调第二级(重试接线在位)'


def test_reader_none_when_area_missing_and_ocr_untouched() -> None:
    """area 缺失(screen_info 未建档/屏缺)→ None,且绝不触 OCR
    (无坐标就无读数;rect=None 防线)。"""
    def _boom(**kw: object) -> list:
        raise AssertionError('area 缺失时不得调用 OCR')

    ctx = SimpleNamespace(
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        ocr_service=SimpleNamespace(get_ocr_result_list=_boom),
    )
    assert read_shop_refresh_price(ctx, None) is None


def test_reader_none_when_both_levels_empty() -> None:
    """两级全空(免费帧/非商店帧/OCR 漏)→ None,不回退基价常量
    (ADR-0622:识别失败=None,禁兜底改值)。"""
    assert read_shop_refresh_price(_fake_ctx([]), None) is None


def test_reader_none_when_ocr_says_free() -> None:
    """免费帧渲染('免费'文本,无数字)→ None ≠ 0。"""
    assert read_shop_refresh_price(_fake_ctx([_ocr_item('免费')]), None) is None


# ===== 真帧锁(归档帧 × 项目真 OCR;模型/fixture 缺 → skip,同 obs_gates 先例) =====

def test_read_price_real_shop_fixtures(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """真实商店开态归档帧锁:5 张帧标价恒读 2(基价局)。

    出处:ADR-0622(现场识别写端)+ 设计文档 §3.3.6;帧=测试仓归档
    ``screens/货币战争-备战-开商店/``(原生 1080p,价格行跨帧像素稳定,
    建档批离线对拍同读)。模型不可用 / fixture 缺失 → skip。
    """
    from pathlib import Path

    from one_dragon.base.matcher.ocr.ocr_service import OcrService
    from one_dragon.utils import cv2_utils

    fix_dir = Path(__file__).resolve().parents[4] / 'screens' / _SHOP_SCREEN_DIR
    frames = [fix_dir / f'{name}.webp' for name in _SHOP_FRAMES]
    if not all(p.exists() for p in frames):
        pytest.skip('fixture 缺失')
    try:
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
        matcher = OnnxOcrMatcher()
        if not matcher.init_model(download_by_github=False, download_by_gitee=True):
            pytest.skip('OCR 模型不可用')
    except Exception:
        pytest.skip('OCR 模型不可用')
    monkeypatch.setattr(test_context, 'ocr_service', OcrService(ocr_matcher=matcher))
    for p in frames:
        img = cv2_utils.read_image(str(p))
        got = read_shop_refresh_price(test_context, img)
        assert got == 2, f'{p.name} 标价应读 2(基价),实读 {got}'
