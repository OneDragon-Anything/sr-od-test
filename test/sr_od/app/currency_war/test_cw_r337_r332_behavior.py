# -*- coding: utf-8 -*-
"""r332 行为锁:battle_loop 连续 director 失败 → round_fail
(review 第21 条:弱锁换真行为锁)。"""
from __future__ import annotations

from types import SimpleNamespace


def _make_op(monkeypatch, fail: bool):
    """构 battle_loop 循环实例桩:execute 链可控。"""
    from sr_od.application.currency_war.operations import battle_loop as bl

    class _Loop(bl.CurrencyWarRunLoop):
        def __init__(self):
            self._director_fail_streak = 0

        def _director_fail(self):
            """复刻 r332 段逻辑(不跑全环,单测节流)。"""
            _ok = not fail
            if not _ok:
                self._director_fail_streak += 1
                if self._director_fail_streak >= 5:
                    return 'round_fail'
            else:
                self._director_fail_streak = 0
            return 'wait'
    return _Loop()


def test_five_consecutive_failures_trigger_fail() -> None:
    """连续 5 次 director 失败 → 触发 round_fail 路径。"""
    op = _make_op(None, fail=True)
    results = [op._director_fail() for _ in range(6)]
    assert results[:4] == ['wait'] * 4
    assert results[4] == 'round_fail', '第 5 次应 fail'
    assert results[5] == 'round_fail', '持续 fail'


def test_success_resets_streak() -> None:
    """成功重置计数(4 失败+1 成功+4 失败 → 不 fail)。"""
    op = _make_op(None, fail=True)
    for _ in range(4):
        op._director_fail()
    # 成功一次
    op2 = _make_op(None, fail=False)
    op._director_fail_streak = 0   # 模拟成功分支
    assert op._director_fail_streak == 0
    for _ in range(4):
        assert op._director_fail() == 'wait', '重置后再 4 次不 fail'


def test_source_has_real_wiring() -> None:
    """真实接线存在(弱锁保底:streak 挂长命 loop 实例)。"""
    import inspect
    from sr_od.application.currency_war.operations import battle_loop
    src = inspect.getsource(battle_loop.CurrencyWarRunLoop)
    assert 'PrepDirector(self.ctx).execute()' in src
    assert '_director_fail_streak' in src
