"""screen_utils 识别层 debug 日志烟囱测试。

出处: docs/develop/one_dragon/changes/op-runtime-debug-log/design.md §2.1 A/B/I 组。
锁三条约定:
① 行为零变化: find_area 命中/未命中返回值与既有 FindAreaResultEnum 一致;
② B1a 详情行在匹配循环处触发, 含 <画面.区域> 上下文与 OCR 原文/目标文本/
   lcs 值/阈值(或模板 conf/阈值); 旧调用方式(不传 screen_name)日志退化为
   裸区域名;
③ I 组 update_current_screen_name 仅 source 非 None 且画面变化时打
   画面状态 行, source=None 的既有调用静默。
全部 mock ctx 服务层, 零真实识别与点击。
"""
import logging
from unittest.mock import MagicMock

import numpy as np
import pytest

import one_dragon.base.screen.screen_utils as su
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_info import ScreenInfo
from one_dragon.base.screen.screen_loader import ScreenContext
from one_dragon.base.screen.screen_utils import (
    FindAreaResultEnum,
    OcrClickResultEnum,
    find_and_click_area,
    find_area,
    find_area_binary,
    find_area_in_screen,
    get_match_screen_name,
)


def _ocr(data: str) -> OcrMatchResult:
    return OcrMatchResult(c=0.95, x=300, y=800, w=200, h=80, data=data)


def _text_area() -> ScreenArea:
    return ScreenArea(area_name='战斗按钮', pc_rect=Rect(300, 800, 500, 880),
                      text='战斗', lcs_percent=0.5)


def _template_area() -> ScreenArea:
    return ScreenArea(area_name='邮箱图标', pc_rect=Rect(1700, 40, 1760, 100),
                      template_id='mail', template_sub_dir='menu',
                      template_match_threshold=0.7)


def _screen_info(name: str) -> ScreenInfo:
    return ScreenInfo({'screen_id': name, 'screen_name': name, 'app_id': '',
                       'area_list': []})


@pytest.mark.parametrize('ocr_text,expect_hit', [
    ('战斗', True),
    ('设置', False),
], ids=['hit', 'miss'])
def test_find_area_text_hit_and_miss(caplog, ocr_text: str, expect_hit: bool) -> None:
    """文本区命中/未命中: 返回值 TRUE/FALSE 不变; B1a 详情行带 画面.区域 与
    OCR 原文/目标文本/lcs 值/阈值, B1 结果行随之命中/未命中。"""
    ctx = MagicMock()
    ctx.screen_loader.get_area.return_value = _text_area()
    ctx.ocr_service.get_ocr_result_list.return_value = [_ocr(ocr_text)]
    with caplog.at_level(logging.DEBUG, logger='OneDragon'):
        result = find_area(ctx, MagicMock(), '主界面', '战斗按钮')

    expect_result = FindAreaResultEnum.TRUE if expect_hit else FindAreaResultEnum.FALSE
    assert result == expect_result
    # '战斗' vs '战斗' lcs=1.00, '设置' vs '战斗' lcs=0.00 —— 阈值恒 0.50
    messages = [r.message for r in caplog.records]
    assert f'find_area 主界面.战斗按钮: OCR"{ocr_text}" vs "战斗" lcs={1.0 if expect_hit else 0.0:.2f}/0.50 → {"命中" if expect_hit else "未命中"}' in messages
    assert f'find_area 主界面.战斗按钮: {"命中" if expect_hit else "未命中"}' in messages


def test_find_area_in_screen_without_screen_name_degrades(caplog) -> None:
    """旧调用方式(不传 screen_name): 返回 TRUE 不变, 日志退化为裸区域名。"""
    ctx = MagicMock()
    ctx.ocr_service.get_ocr_result_list.return_value = [_ocr('战斗')]
    with caplog.at_level(logging.DEBUG, logger='OneDragon'):
        result = find_area_in_screen(ctx, MagicMock(), _text_area())

    assert result == FindAreaResultEnum.TRUE
    messages = [r.message for r in caplog.records]
    assert 'find_area 战斗按钮: OCR"战斗" vs "战斗" lcs=1.00/0.50 → 命中' in messages
    assert all('主界面.战斗按钮' not in m for m in messages)


@pytest.mark.parametrize('matched,expect_conf', [
    (True, '0.92'),
    (False, '-'),
], ids=['hit', 'miss'])
def test_find_area_binary_template(caplog, matched: bool, expect_conf: str) -> None:
    """binary 模板分支: B1a 格式与主路径完全一致(不加 binary 前缀); 未命中时
    原始 conf 已被底层过滤, 打 '-'。screen 用真 ndarray(to_binary 真跑)。"""
    ctx = MagicMock()
    ctx.screen_loader.get_area.return_value = _template_area()
    mrl = MagicMock()
    mrl.max = MagicMock(confidence=0.92) if matched else None
    ctx.tm.crop_and_match_template_binary.return_value = mrl
    screen = np.zeros((10, 10, 3), dtype=np.uint8)
    with caplog.at_level(logging.DEBUG, logger='OneDragon'):
        result = find_area_binary(ctx, screen, '主界面', '邮箱图标')

    expect_result = FindAreaResultEnum.TRUE if matched else FindAreaResultEnum.FALSE
    assert result == expect_result
    messages = [r.message for r in caplog.records]
    assert f'find_area 主界面.邮箱图标: 模板mail conf={expect_conf}/0.70 → {"命中" if matched else "未命中"}' in messages
    assert f'find_area 主界面.邮箱图标: {"命中" if matched else "未命中"}' in messages


def test_find_and_click_area_click_log(caplog) -> None:
    """B2: 文本命中点击出口 → 点击行带 画面.区域/坐标/pc_alt/结果; 返回 SUCCESS。"""
    ctx = MagicMock()
    ctx.screen_loader.get_area.return_value = _text_area()
    ctx.ocr_service.get_ocr_result_list.return_value = [_ocr('战斗')]
    ctx.controller.click.return_value = True
    with caplog.at_level(logging.DEBUG, logger='OneDragon'):
        result = find_and_click_area(ctx, MagicMock(), '主界面', '战斗按钮')

    assert result == OcrClickResultEnum.OCR_CLICK_SUCCESS
    messages = [r.message for r in caplog.records]
    assert '点击 主界面.战斗按钮 @ (400,840) pc_alt=F → 成功' in messages


def test_find_and_click_area_not_found_log(caplog) -> None:
    """B2: 文本未命中 → 未命中(不点击) 行, 返回 OCR_CLICK_NOT_FOUND, 不点击。"""
    ctx = MagicMock()
    ctx.screen_loader.get_area.return_value = _text_area()
    ctx.ocr_service.get_ocr_result_list.return_value = [_ocr('设置')]
    with caplog.at_level(logging.DEBUG, logger='OneDragon'):
        result = find_and_click_area(ctx, MagicMock(), '主界面', '战斗按钮')

    assert result == OcrClickResultEnum.OCR_CLICK_NOT_FOUND
    ctx.controller.click.assert_not_called()
    messages = [r.message for r in caplog.records]
    assert 'find_area 主界面.战斗按钮: 未命中(不点击)' in messages


def test_get_match_screen_name_none_logs_tried(monkeypatch, caplog) -> None:
    """A1/A2: 限定列表全未中 → 返回 None; 结果行带判定数, 追加行带判定序前 10。"""
    monkeypatch.setattr(su, 'is_target_screen', lambda *a, **k: False)
    ctx = MagicMock()
    ctx.screen_loader.screen_info_list = [_screen_info('画面A'), _screen_info('画面B')]
    with caplog.at_level(logging.DEBUG, logger='OneDragon'):
        result = get_match_screen_name(ctx, MagicMock(),
                                       screen_name_list=['画面A', '画面B'])

    assert result is None
    messages = [r.message for r in caplog.records]
    assert any(m.startswith('画面判定: None (判定 2, ') for m in messages)
    assert '画面判定: None (试过 [画面A, 画面B] 全未中)' in messages


def test_get_match_screen_name_hit_stops_early(monkeypatch, caplog) -> None:
    """A1 口径: 限定列表第 1 个命中 → 判定数=1(后续画面未判定不计), 返回该画面。"""
    calls: list[str] = []

    def fake_is_target_screen(ctx, screen, screen_name=None, screen_info=None, crop_first=False) -> bool:
        calls.append(screen_info.screen_name)
        return screen_info.screen_name == '画面A'

    monkeypatch.setattr(su, 'is_target_screen', fake_is_target_screen)
    ctx = MagicMock()
    ctx.screen_loader.screen_info_list = [_screen_info('画面A'), _screen_info('画面B')]
    with caplog.at_level(logging.DEBUG, logger='OneDragon'):
        result = get_match_screen_name(ctx, MagicMock(),
                                       screen_name_list=['画面A', '画面B'])

    assert result == '画面A'
    assert calls == ['画面A']   # 提前命中后画面B未判定
    messages = [r.message for r in caplog.records]
    assert any(m.startswith('画面判定: 画面A (判定 1, ') for m in messages)


def test_update_current_screen_name_source_logging(caplog) -> None:
    """I 组: source 非 None 且画面变化才打 画面状态 行; source=None 静默、
    旧值==新值不打; 状态转移行为(last/current 轮换)不变。"""
    sc = ScreenContext()
    with caplog.at_level(logging.DEBUG, logger='OneDragon'):
        sc.update_current_screen_name('主界面', source='判定')   # None→主界面, 打
        sc.update_current_screen_name('主界面', source='判定')   # 旧==新, 不打
        sc.update_current_screen_name('菜单')                    # source=None, 不打

    assert [r.message for r in caplog.records] == ['画面状态: None→主界面 (来源: 判定)']
    assert sc.last_screen_name == '主界面'
    assert sc.current_screen_name == '菜单'
