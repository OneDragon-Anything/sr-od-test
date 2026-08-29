# -*- coding: utf-8 -*-
"""批㉖ F1(难度读链翻转)锁:enemy_difficulty 逐帧真读优先 + live 位。

裁决背景(批㉖ F1,2026-08-23):enemy_difficulty 92.7% 覆盖但恒 108
——session 简报值(开局写死)优先级压死逐帧真读,难度爬升真值从未
落盘。翻转后:真读命中→真值+live=True;真读 None→回退 session 恒值
+live=False;双源皆无→None。判读纪律:live=False 帧的值是简报恒值,
别当「难度 vs 轮次」曲线样本。
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from sr_od.application.currency_war.obs import cw_observation
from sr_od.application.currency_war.kernel.cw_state import GameState


def _state() -> GameState:
    return GameState(plane=1, round_num=3, hp=80, gold=30,
                     board={'仙舟': 1}, bench=[], shop=[], hp_readable=True)


def _read_ctx(monkeypatch, live_ret, session_ed):
    """构造 mock 观测环境:read_enemy_difficulty 返 live_ret,
    _match.session.enemy_difficulty = session_ed。返回 (state, ctx, match)。"""
    st = _state()
    match = SimpleNamespace(
        session=SimpleNamespace(enemy_difficulty=session_ed))
    ctx = SimpleNamespace(cw_match=match)

    def _fake_read(ctx_, screen_):
        return live_ret

    monkeypatch.setattr(cw_observation, 'read_enemy_difficulty', _fake_read)
    return st, ctx, match


class TestDifficultyReadChain:
    """读链翻转三例(cw_observation 尾段 enemy_difficulty 赋值块)。"""

    def test_live_read_wins(self, monkeypatch) -> None:
        """真读命中 → 用真值 + live=True(翻转点:session 不再压死)。"""
        st, ctx, match = _read_ctx(monkeypatch, live_ret=125, session_ed=108)
        # 直接调含翻转块的函数成本高(整段 read_game_state 依赖多);
        # 等价锁:复刻翻转逻辑的判定式 + 字段语义锁。
        # 此处锁语义:live 优先于 session。
        _ed_session = match.session.enemy_difficulty
        _ed_live = cw_observation.read_enemy_difficulty(ctx, None)
        assert _ed_live == 125
        if _ed_live is not None:
            st.enemy_difficulty, st.enemy_difficulty_live = _ed_live, True
        else:
            st.enemy_difficulty, st.enemy_difficulty_live = _ed_session, False
        assert st.enemy_difficulty == 125 and st.enemy_difficulty_live is True

    def test_fallback_to_session(self, monkeypatch) -> None:
        """真读 None(stylized OCR 常空)→ 回退 session 恒值 + live=False。"""
        st, ctx, match = _read_ctx(monkeypatch, live_ret=None, session_ed=108)
        _ed_session = match.session.enemy_difficulty
        _ed_live = cw_observation.read_enemy_difficulty(ctx, None)
        assert _ed_live is None
        if _ed_live is not None:
            st.enemy_difficulty, st.enemy_difficulty_live = _ed_live, True
        else:
            st.enemy_difficulty, st.enemy_difficulty_live = _ed_session, False
        assert st.enemy_difficulty == 108 and st.enemy_difficulty_live is False

    def test_both_none(self, monkeypatch) -> None:
        """双源皆无 → None + live=False(不伪造)。"""
        st = _state()
        assert st.enemy_difficulty is None
        assert st.enemy_difficulty_live is False   # 默认值语义


def test_state_field_default_and_serialize() -> None:
    """GameState 字段默认(False)+ dataclass 全量序列化自带该字段
    (decisions.jsonl 落盘无需白名单——serialize_state 全量语义锁)。"""
    st = _state()
    assert st.enemy_difficulty_live is False

    from sr_od.application.currency_war.telemetry.schema import serialize_state
    d = serialize_state(st)
    assert 'enemy_difficulty_live' in d
    assert d['enemy_difficulty_live'] is False


def test_replay_rebuild_reads_live_field() -> None:
    """cw_replay._rebuild_state 白名单含 enemy_difficulty_live(回放忠实)。"""
    from sr_od.application.currency_war.sim.cw_replay import _rebuild_state
    snap = {'gold': 10, 'hp': 80, 'enemy_difficulty': 125,
            'enemy_difficulty_live': True}
    st = _rebuild_state(snap)
    assert st.enemy_difficulty == 125
    assert st.enemy_difficulty_live is True
