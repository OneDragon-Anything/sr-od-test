"""货币战争结算画面 recognizer(SettlementRecognizer)单元测试。

无结算 fixture 截图,故用 **mock** ``parse_settlement_hp`` + ``ctx.ocr_service`` 测组合逻辑:验证 recognizer
正确组装 dict、失败屏 hp→0、非失败读不到→None(不硬塞),且**只**复用纯函数 ``parse_settlement_hp``、
不复用需 session 的 ``read_round_outcome``。真实 OCR 集成待 fixture 采到后补。
"""
from unittest.mock import MagicMock

import sr_od.application.currency_war.recognizers.settlement_recognizer as mod
from sr_od.application.currency_war.recognizers.settlement_recognizer import (
    SettlementRecognizer,
)


def _ctx_with_ocr(ocr_texts: list[str]) -> MagicMock:
    """构造 mock ctx:ocr_service.get_ocr_result_list 返回给定文本(data 字段)。"""
    ctx = MagicMock()
    ctx.ocr_service.get_ocr_result_list.return_value = [MagicMock(data=t) for t in ocr_texts]
    return ctx


def test_screen_name_matches_settlement() -> None:
    """recognizer 注册的 screen_name = '货币战争-结算'(与 screen_info 一致)。"""
    assert SettlementRecognizer.screen_name == '货币战争-结算'


def test_recognize_parses_hp(monkeypatch) -> None:
    """非失败屏:parse_settlement_hp 读到 71 → hp_after=71, is_failed=False。"""
    monkeypatch.setattr(mod, 'parse_settlement_hp', lambda texts: 71)
    ctx = _ctx_with_ocr(['挑战结束', '小队生命值71', '继续挑战'])

    out = SettlementRecognizer().recognize(ctx, MagicMock(), MagicMock())
    assert out == {'hp_after': 71, 'is_failed': False}


def test_recognize_failed_screen_hp_zero(monkeypatch) -> None:
    """失败屏(「挑战失败」):parse_settlement_hp 读不到 → hp_after=0(团灭 ground truth)。"""
    monkeypatch.setattr(mod, 'parse_settlement_hp', lambda texts: None)
    ctx = _ctx_with_ocr(['挑战失败', '继续挑战'])

    out = SettlementRecognizer().recognize(ctx, MagicMock(), MagicMock())
    assert out == {'hp_after': 0, 'is_failed': True}


def test_recognize_hp_none_when_unreadable(monkeypatch) -> None:
    """非失败屏 parse_settlement_hp 读不到 → hp_after=None(不硬塞)。"""
    monkeypatch.setattr(mod, 'parse_settlement_hp', lambda texts: None)
    ctx = _ctx_with_ocr(['挑战结束', '继续挑战'])

    out = SettlementRecognizer().recognize(ctx, MagicMock(), MagicMock())
    assert out == {'hp_after': None, 'is_failed': False}


def test_does_not_import_session_based_reader() -> None:
    """并发安全:模块不导入需 plane/round(从 session)的 read_round_outcome。"""
    assert not hasattr(mod, 'read_round_outcome'), '不得复用需 session plane/round 的 read_round_outcome'
