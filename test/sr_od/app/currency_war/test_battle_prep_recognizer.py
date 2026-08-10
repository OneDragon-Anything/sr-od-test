"""货币战争备战画面 recognizer(BattlePrepRecognizer)单元测试。

无备战 fixture 截图,故用 **mock 各 reader** 测组合逻辑:验证 recognizer 正确组装 dict、
phase 走纯读(``_read_phase_round_pure``)、且**不**复用带可变状态的 ``read_phase_round`` /
``read_game_state``(并发安全,见 spec §6)。真实 OCR 集成待 fixture 采到后补。
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import sr_od.application.currency_war.recognizers.battle_prep_recognizer as mod
from sr_od.application.currency_war.cw_obs_core import SCREEN_NAME
from sr_od.application.currency_war.recognizers.battle_prep_recognizer import (
    BattlePrepRecognizer,
)


def test_screen_name_matches_battle_prep() -> None:
    """recognizer 注册的 screen_name = '货币战争-备战'(与 screen_info 一致)。"""
    assert BattlePrepRecognizer.screen_name == SCREEN_NAME == '货币战争-备战'


def test_recognize_composes_pure_reads(monkeypatch) -> None:
    """recognize 组合各纯 reader → dict(gold/phase/hp/streak/deploy/board 字段齐全)。"""
    monkeypatch.setattr(mod, 'read_gold', lambda ctx, screen: 42)
    monkeypatch.setattr(mod, '_read_phase_round_pure', lambda ctx, screen: (2, 5))
    monkeypatch.setattr(mod, 'read_hp', lambda ctx, screen: 80)
    monkeypatch.setattr(mod, 'read_streak', lambda ctx, screen: 3)
    monkeypatch.setattr(mod, 'read_deployed_count', lambda ctx, screen: 4)
    monkeypatch.setattr(mod, 'read_deploy_cap', lambda ctx, screen: 5)
    monkeypatch.setattr(mod, 'read_board', lambda ctx, screen: {'仙舟': 2, '猎犬': 1})
    monkeypatch.setattr(mod, 'read_level', lambda ctx, screen, p, r: 5)
    # 角色识别 reader mock 空(角色识别单测见下;避免 MagicMock screen 进 SIFT 崩)
    monkeypatch.setattr(mod, 'read_deployed_chars', lambda ctx, screen, templates: [])
    monkeypatch.setattr(mod, 'read_bench_chars', lambda ctx, screen, templates: [])
    # 装备识别 mock 跳过(ensure 返 None → front/back/bench_equips None;装备识别 fixture 测见 test_cw_equipment)
    monkeypatch.setattr(mod, 'ensure_equip_tm_templates', lambda ctx: None)

    out = BattlePrepRecognizer().recognize(MagicMock(), MagicMock(), MagicMock())
    assert out == {
        'gold': 42, 'phase': (2, 5), 'hp': 80, 'streak': 3,
        'deploy_count': 4, 'deploy_cap': 5, 'level': 5, 'board': {'仙舟': 2, '猎犬': 1},
        'front_line': None, 'back_line': None, 'bench': None,
        'front_equips': None, 'back_equips': None, 'bench_equips': None,
    }


def test_recognize_phase_none_when_unreadable(monkeypatch) -> None:
    """phase 纯读读不到 → None(不伪造 (1,1));其余字段仍产出。"""
    monkeypatch.setattr(mod, 'read_gold', lambda ctx, screen: 0)
    monkeypatch.setattr(mod, '_read_phase_round_pure', lambda ctx, screen: None)
    monkeypatch.setattr(mod, 'read_hp', lambda ctx, screen: 100)
    monkeypatch.setattr(mod, 'read_streak', lambda ctx, screen: None)
    monkeypatch.setattr(mod, 'read_deployed_count', lambda ctx, screen: None)
    monkeypatch.setattr(mod, 'read_deploy_cap', lambda ctx, screen: None)
    monkeypatch.setattr(mod, 'read_board', lambda ctx, screen: {})
    monkeypatch.setattr(mod, 'read_deployed_chars', lambda ctx, screen, templates: [])
    monkeypatch.setattr(mod, 'read_bench_chars', lambda ctx, screen, templates: [])
    monkeypatch.setattr(mod, 'ensure_equip_tm_templates', lambda ctx: None)

    out = BattlePrepRecognizer().recognize(MagicMock(), MagicMock(), MagicMock())
    assert out['phase'] is None
    assert out['gold'] == 0
    assert out['front_line'] is None


def test_does_not_import_stateful_readers() -> None:
    """并发安全:模块不导入写全局的 read_phase_round、不导入读写 session 的 read_game_state。"""
    assert not hasattr(mod, 'read_phase_round'), '不得复用写 _last_phase_round 全局的 read_phase_round'
    assert not hasattr(mod, 'read_game_state'), '不得复用读写 cw_match.session 的 read_game_state'


def test_read_phase_round_pure_parses_dash(monkeypatch) -> None:
    """纯 phase 读:OCR "2-4" → (2, 4)。"""
    monkeypatch.setattr(mod, '_area_rect', lambda ctx, name: MagicMock())
    monkeypatch.setattr(mod, '_ocr', lambda ctx, screen, rect: [MagicMock(data='2-4')])
    assert mod._read_phase_round_pure(MagicMock(), MagicMock()) == (2, 4)


def test_read_phase_round_pure_none_on_garbage(monkeypatch) -> None:
    """纯 phase 读:OCR 无数字 → None(不兜底、不写全局)。"""
    monkeypatch.setattr(mod, '_area_rect', lambda ctx, name: MagicMock())
    monkeypatch.setattr(mod, '_ocr', lambda ctx, screen, rect: [MagicMock(data='乱七八糟无数字')])
    assert mod._read_phase_round_pure(MagicMock(), MagicMock()) is None


def _char(char_id: str, position_pref: str) -> SimpleNamespace:
    """轻量 mock BenchChar(recognize 只用 char_id + position_pref)。"""
    return SimpleNamespace(char_id=char_id, position_pref=position_pref)


def test_recognize_identifies_chars(monkeypatch) -> None:
    """templates 已加载 + SIFT 识别 → front_line / back_line / bench 产角色名。"""
    monkeypatch.setattr(mod, 'read_gold', lambda ctx, screen: 0)
    monkeypatch.setattr(mod, '_read_phase_round_pure', lambda ctx, screen: None)
    monkeypatch.setattr(mod, 'read_hp', lambda ctx, screen: 100)
    monkeypatch.setattr(mod, 'read_streak', lambda ctx, screen: None)
    monkeypatch.setattr(mod, 'read_deployed_count', lambda ctx, screen: None)
    monkeypatch.setattr(mod, 'read_deploy_cap', lambda ctx, screen: None)
    monkeypatch.setattr(mod, 'read_board', lambda ctx, screen: {})
    monkeypatch.setattr(mod, 'read_deployed_chars', lambda ctx, screen, templates: [
        _char('藿藿', 'front'), _char('希儿', 'back'),
    ])
    monkeypatch.setattr(mod, 'read_bench_chars', lambda ctx, screen, templates: [_char('飞霄', 'back')])
    monkeypatch.setattr(mod, 'ensure_equip_tm_templates', lambda ctx: None)

    out = BattlePrepRecognizer().recognize(MagicMock(), MagicMock(), MagicMock())
    assert out['front_line'] == ['藿藿']
    assert out['back_line'] == ['希儿']
    assert out['bench'] == ['飞霄']


def test_recognize_no_chars_when_templates_none(monkeypatch) -> None:
    """templates 未加载(None)→ 不产角色(三字段 None;不自己 load,纯读原则)。"""
    monkeypatch.setattr(mod, 'read_gold', lambda ctx, screen: 0)
    monkeypatch.setattr(mod, '_read_phase_round_pure', lambda ctx, screen: None)
    monkeypatch.setattr(mod, 'read_hp', lambda ctx, screen: 100)
    monkeypatch.setattr(mod, 'read_streak', lambda ctx, screen: None)
    monkeypatch.setattr(mod, 'read_deployed_count', lambda ctx, screen: None)
    monkeypatch.setattr(mod, 'read_deploy_cap', lambda ctx, screen: None)
    monkeypatch.setattr(mod, 'read_board', lambda ctx, screen: {})
    monkeypatch.setattr(mod, 'read_deployed_chars', lambda *a, **k: [])   # 不该被调(templates None 跳过)
    monkeypatch.setattr(mod, 'read_bench_chars', lambda *a, **k: [])
    monkeypatch.setattr(mod, 'ensure_equip_tm_templates', lambda ctx: None)

    ctx = MagicMock()
    ctx.cw_portrait_templates = None   # 模拟 bot 未加载立绘库
    out = BattlePrepRecognizer().recognize(ctx, MagicMock(), MagicMock())
    assert out['front_line'] is None
    assert out['back_line'] is None
    assert out['bench'] is None
    assert out['front_equips'] is None  # ensure mock None → 装备识别跳过
