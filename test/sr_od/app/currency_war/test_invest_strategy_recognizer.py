"""货币战争投资策略画面 recognizer(InvestStrategyRecognizer)单元测试。

无 fixture 截图,故用 **mock** ``_area_rect`` / ``_ocr`` 测组合逻辑:验证 recognizer 正确解析 3 选 1
策略名、读不到返 [](不硬塞)。真实 OCR 集成待 fixture 采到后补。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from unittest.mock import MagicMock

import sr_od.application.currency_war.obs.recognizers.invest_strategy_recognizer as mod
from sr_od.application.currency_war.obs.recognizers.invest_strategy_recognizer import (
    InvestStrategyRecognizer,
)


def test_screen_name_matches_invest_strategy() -> None:
    """recognizer 注册的 screen_name = '货币战争-投资策略'(与 screen_info 一致)。"""
    assert InvestStrategyRecognizer.screen_name == '货币战争-投资策略'


def _mock_ocr(monkeypatch, names: list[str]) -> None:
    monkeypatch.setattr(mod, '_area_rect', lambda ctx, name, screen_name=None: MagicMock())
    monkeypatch.setattr(mod, '_ocr', lambda ctx, screen, rect: [MagicMock(data=n) for n in names])


def test_recognize_parses_three_strategies(monkeypatch) -> None:
    """3 张策略卡 → strategies 名列表(滤数字/符号噪声)。"""
    _mock_ocr(monkeypatch, ['乱成一锅粥', '盗用身份', '远见'])

    out = InvestStrategyRecognizer().recognize(MagicMock(), MagicMock(), MagicMock())
    assert out == {'strategies': ['乱成一锅粥', '盗用身份', '远见']}


def test_recognize_filters_short_noise(monkeypatch) -> None:
    """滤单字噪声 / 纯数字(只留 2-10 字中文)。"""
    _mock_ocr(monkeypatch, ['团队力量·金', '1', '啊'])

    out = InvestStrategyRecognizer().recognize(MagicMock(), MagicMock(), MagicMock())
    assert out == {'strategies': ['团队力量·金']}   # '1'(纯数字) '啊'(单字)被滤


def test_recognize_empty_when_unreadable(monkeypatch) -> None:
    """读不到(area 缺 / OCR 无果)→ 空 list(不伪造)。"""
    monkeypatch.setattr(mod, '_area_rect', lambda ctx, name, screen_name=None: None)
    monkeypatch.setattr(mod, '_ocr', lambda ctx, screen, rect: [])

    out = InvestStrategyRecognizer().recognize(MagicMock(), MagicMock(), MagicMock())
    assert out == {'strategies': []}
