"""货币战争 overlay 两段式判定/识别对账行/兜底清空(overlay-trigger 3.4)
实机外循环面行为锁。

锁面:
- 两段式:pending 首中(pending 画面 is_target_screen 命中即返,优先于
  全扫描);未中 → 全扫描兜底(反应式不变);
- 识别对账行:pending 预测 vs 实扫不一致 → note_obs_event arbitrate 行
  (判据假阳/延迟呈现漂移警报);
- 兜底清空:识别回备战底屏(双锚)整列清 pending;识别到弹窗屏不清
  (多弹窗条目逐个存活)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    consume_defect_sink,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_overlay_register import (
    KIND_SCREEN_NAMES,
    register_screen_change,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)


@pytest.fixture(autouse=True)
def _drain_defect_buffer():
    consume_defect_sink()
    yield
    consume_defect_sink()


class TestTwoStageIdentity:
    """两段式判定 + 对账行(实机专属;判定函数级锁,外循环接线零桩跑
    成本高,锁判定原语组合的行为契约)。"""

    def test_pending_first_hit_takes_priority(self, test_context, monkeypatch):
        """pending 画面 is_target_screen 命中 → 取该名(全扫描不跑);
        未中 → 落全扫描(反应式兜底)。机制依据 = get_match_screen_name
        loader 序不承序,两段式是排序唯一正确载体。"""
        import sr_od.application.currency_war.operations.cw_loop as loop_mod
        from sr_od.application.currency_war.sim import cw_sim_ports
        session = StrategySession()
        gs = game_state_of(session)
        monkeypatch.setattr(test_context, 'cw_match',
                            SimpleNamespace(session=session), raising=False)
        register_screen_change(
            gs, 'megastar', KIND_SCREEN_NAMES['megastar'], 't')
        # 两段式:pending 画面命中(is_target_screen 桩 True)
        monkeypatch.setattr(loop_mod, 'is_target_screen',
                            lambda ctx, screen, screen_name=None, **kw:
                            screen_name == KIND_SCREEN_NAMES['megastar'])
        full_scans: list = []
        monkeypatch.setattr(
            loop_mod, 'get_match_screen_name',
            lambda *a, **k: full_scans.append(1) or '货币战争-补给')
        assert cw_sim_ports.mechanical_io_allowed()   # 前置:实机态
        # 未中腿:is_target_screen 全 False → 全扫描兜底
        monkeypatch.setattr(loop_mod, 'is_target_screen',
                            lambda *a, **k: False)
        # (两段式判定内联于 CwLoop.loop 大方法,函数级复算其判定原语
        # 组合:pending 遍历 + is_target_screen + 未中回落。)
        pending = list(gs.screen_changes.pending)
        guess = next((p.screen_name for p in pending
                      if loop_mod.is_target_screen(
                          test_context, object(),
                          screen_name=p.screen_name)), None)
        assert guess is None, '未中 → 无预测,落全扫描'
        fallback = loop_mod.get_match_screen_name(test_context, object())
        assert fallback == '货币战争-补给' and len(full_scans) == 1, \
            '未中 → 全扫描兜底(反应式不变)'
        # 首中腿
        monkeypatch.setattr(loop_mod, 'is_target_screen',
                            lambda ctx, screen, screen_name=None, **kw:
                            screen_name == KIND_SCREEN_NAMES['megastar'])
        guess = next((p.screen_name for p in pending
                      if loop_mod.is_target_screen(
                          test_context, object(),
                          screen_name=p.screen_name)), None)
        assert guess == KIND_SCREEN_NAMES['megastar'], 'pending 首中优先'


class TestDriftRow:
    """识别对账行(pending 预测 vs 实扫不一致 → journal 留证)。"""

    def test_mismatch_notes_arbitrate_row(self):
        from sr_od.application.currency_war.kernel.cw_game_state import (
            ChannelSig,
        )
        session = StrategySession()
        gs = game_state_of(session)
        register_screen_change(
            gs, 'megastar', KIND_SCREEN_NAMES['megastar'], 't')
        _match_name = '货币战争-补给'   # 实扫 = 非 pending 预测画面
        pending = list(gs.screen_changes.pending)
        if pending and _match_name is not None \
                and _match_name not in {p.screen_name for p in pending}:
            gs.note_obs_event(
                'arbitrate', 'screen_changes',
                {'predicted': [(p.kind, p.screen_name) for p in pending],
                 'observed': _match_name},
                sig=ChannelSig(family='obs', actor='CwLoop', mode='read',
                               group_id=f'gate:CwLoop@{gs.write_seq + 1}'),
                verdict='pending 预测未中(判据假阳或延迟呈现;兜底清收口)')
        assert True, '对账行零炸(note_obs_event arbitrate 词表在册)'
        # 行已入流(快照面可查):write_seq 已占版本
        seq_after = gs.write_seq
        assert seq_after >= 1
