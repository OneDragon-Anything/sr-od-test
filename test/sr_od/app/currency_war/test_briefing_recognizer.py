"""货币战争简报画面 recognizer(BriefingRecognizer)单元测试。

无简报 fixture 截图,故用 **mock 各 reader** 测组合逻辑:验证 recognizer 正确组装 dict、且**只**复用
纯读 reader(``read_affixes`` / ``read_bosses``,纯 OCR + 正则),不复用语义要 click 的 ``read_affix_effect``
(并发安全 / 纯读观察,见 spec §6)。真实 OCR 集成待 fixture 采到后补。
"""
from unittest.mock import MagicMock

import sr_od.application.currency_war.recognizers.briefing_recognizer as mod
from sr_od.application.currency_war.kernel.cw_obs_core import BRIEFING_SCREEN
from sr_od.application.currency_war.recognizers.briefing_recognizer import (
    BriefingRecognizer,
)


def test_screen_name_matches_briefing() -> None:
    """recognizer 注册的 screen_name = '货币战争-简报'(与 screen_info 一致)。"""
    assert BriefingRecognizer.screen_name == BRIEFING_SCREEN == '货币战争-简报'


def test_recognize_composes_pure_reads(monkeypatch) -> None:
    """recognize 组合纯 reader → dict(affixes / bosses 字段齐全)。"""
    monkeypatch.setattr(mod, 'read_affixes', lambda ctx, screen: ['第二位面强化6', '前后台熄火'])
    monkeypatch.setattr(mod, 'read_bosses', lambda ctx, screen: ['增熵能源集团', '火线动力机甲', '银甲武装公司'])

    out = BriefingRecognizer().recognize(MagicMock(), MagicMock(), MagicMock())
    assert out == {
        'affixes': ['第二位面强化6', '前后台熄火'],
        'bosses': ['增熵能源集团', '火线动力机甲', '银甲武装公司'],
    }


def test_recognize_empty_when_unreadable(monkeypatch) -> None:
    """读不到 → 空 list(不伪造;词缀 / boss 缺 area 或 OCR 无果都返 [])。"""
    monkeypatch.setattr(mod, 'read_affixes', lambda ctx, screen: [])
    monkeypatch.setattr(mod, 'read_bosses', lambda ctx, screen: [])

    out = BriefingRecognizer().recognize(MagicMock(), MagicMock(), MagicMock())
    assert out == {'affixes': [], 'bosses': []}


def test_does_not_import_click_based_reader() -> None:
    """纯读观察:模块不导入语义要 click 的 read_affix_effect(recognizer 不 click)。"""
    assert not hasattr(mod, 'read_affix_effect'), 'recognizer 不得复用需先 click 的 read_affix_effect'
