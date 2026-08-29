"""行为锁:L0 安灯停线「缺省关 + 显式接通」契约 + 会话守卫运行残留复位。

背景(w505 全集假红实证):安灯执行器槽曾有「缺省惰性调 cw_observe 停线」
设计——gc 扫描全进程定位 ctx,在测试进程命中 session 级 test_context →
写真实仓根 flag + run_context.last_run_result 停机位,monkeypatch 不辖此
副作用 → 后续一切 execute() 撞 W209j 刹车(单跑必过/全集必挂)。

三条锁:
1. 缺省 handler=None = 不停线(只记台账):cw_observe 停线实现挂 canary,
   触发 L0 判级不得触达;台账 severity 照记(L0_andon);
2. 生产武装点在场:CurrencyWarApp.__init__ 显式 set_l0_andon_handler;
   且 _fire_l0_andon 源码不含惰性 import(防改回);
3. conftest 运行残留守卫:测试遗留 run_context.last_run_result → 下一
   测试看到已复位 None(跨测试序:污染测试在前,哨兵测试在后)。
"""
from __future__ import annotations

from pathlib import Path
from sr_od.application.currency_war.telemetry import defects, recorder

_L0 = 'sr_od.application.currency_war.telemetry.defects'
from sr_od.application.currency_war.telemetry import defects as ct, state


def _setup_isolated_l0(tmp_path: Path, monkeypatch) -> Path:
    """台账指向 tmp + 安灯槽/闩锁/复现账隔离(与 w505 _setup_recorder 同链)。"""

    monkeypatch.setattr(state, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(state, '_CURRENT_RUN_ID', 'l0iso')
    monkeypatch.setattr(state, '_defect_seen', {})
    monkeypatch.setattr(state, '_defect_seen_run', '')
    monkeypatch.setattr(state, '_L0_ANDON_FIRED_RUNS', set())
    return tmp_path


def test_default_handler_off_is_noop(tmp_path: Path, monkeypatch) -> None:
    """锁1:缺省(Handler=None)触发 L0 → 台账照记 L0_andon,游戏侧停线实现
    不得被触达(canary 挂在 cw_observe,被调即炸)。"""
    from sr_od.application.currency_war.kernel import cw_observe

    d = _setup_isolated_l0(tmp_path, monkeypatch)
    monkeypatch.setattr(state, '_L0_ANDON_HANDLER', None)   # 缺省态显式钉住

    def _canary(payload: dict) -> bool:
        raise AssertionError('缺省关态下停线实现被触达(惰性接线回归?)')

    monkeypatch.setattr(cw_observe, 'stop_for_l0_andon', _canary)

    for _ in range(2):   # 同特征第 2 次 = 复现 → 判级 L0
        defects.record_defect('gold', 'perception_conflict',
                         'gold_delta: 45', '20', gap=-25.0, gap_large=True)

    rows = [__import__('json').loads(ln) for ln in
            (d / 'defect_ledger.jsonl').read_text(encoding='utf-8').splitlines()
            if ln.strip()]
    assert [r['severity'] for r in rows] == ['L1_alert', 'L0_andon']


def test_no_lazy_wiring_in_fire_and_app_arms_handler() -> None:
    """锁2:_fire_l0_andon 源码不含惰性 import(防改回);生产武装点
    (CurrencyWarApp.__init__ 显式 set_l0_andon_handler)在场。"""
    import inspect

    from sr_od.application.currency_war.currency_war_app import CurrencyWarApp

    assert 'stop_for_l0_andon' not in inspect.getsource(defects._fire_l0_andon), (
        '_fire_l0_andon 禁止惰性接真实现(缺省必须关,武装点在 app)')
    assert 'set_l0_andon_handler' in inspect.getsource(CurrencyWarApp.__init__), (
        'CurrencyWarApp.__init__ 缺 L0 安灯显式武装(生产停线将静默失效)')


def test_a_run_leftover_pollution_is_written(test_context) -> None:
    """锁3-前半:人为遗留运行停机位(模拟 w505 型污染;conftest 守卫在
    teardown 复位)。本测试断言写入成立,清洗效果由下一个测试钉住。"""
    test_context.run_context.last_run_result = object()
    assert test_context.run_context.last_run_result is not None


def test_b_run_leftover_is_reset_by_guard(test_context) -> None:
    """锁3-后半:上一测试遗留的停机位必须已被 conftest 守卫复位为 None
    ——守卫失效时本测试红(全集假红的结构性防线,不许静默退化)。"""
    assert test_context.run_context.last_run_result is None, (
        'conftest 运行残留守卫失效:last_run_result 跨测试泄漏'
        '(后续 execute() 将撞 W209j 刹车)')

