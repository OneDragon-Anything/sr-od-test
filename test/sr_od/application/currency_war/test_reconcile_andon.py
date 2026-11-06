"""统一观察对账安灯·装配闭包测试( §2.4;
2026-09-16 框架化:处置壳 = stop_running 一行,截图归框架,flag/一次性标志位退役)。

闭包工厂 = currency_war_app._build_reconcile_andon(ctx);kernel 槽缺省关的
零副作用面由 test_mismatch_policy.py 校验,本文件只校验生产闭包行为面。
零真实 IO:不触控制器,框架截图由 stop_running 形参表达。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war import currency_war_app as app_mod
from sr_od.application.currency_war.kernel.cw_mismatch_policy import (
    fire_reconcile_andon,
    set_reconcile_andon_hook,
)

_ROW = {'ts': '2026-09-16T12:00:00', 'field': 'gold', 'expected': 17,
        'actual': 19, 'observed_evidence': None, 'screen': '货币战争-备战',
        'actor': 'cw_observation', 'group_id': None,
        'logic_evidence': 'proj_sell_refund'}


class _Rc:
    """run_context 桩:记录 stop 调用(签名随框架含 save_screenshot)。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def stop_running(self, reason: str = '',
                     save_screenshot: bool = False) -> None:
        self.calls.append({'reason': reason,
                           'save_screenshot': save_screenshot})


def test_andon_mismatch_stops_with_framework_evidence(monkeypatch, caplog):
    """真失配 → stop_running(reason, save_screenshot=True) 一行处置:
    截图留证委托框架,日志带失配字段与两值。"""
    rc = _Rc()
    set_reconcile_andon_hook(
        app_mod._build_reconcile_andon(SimpleNamespace(run_context=rc)))
    try:
        with caplog.at_level('WARNING'):
            fire_reconcile_andon(dict(_ROW))
    finally:
        set_reconcile_andon_hook(None)
    assert rc.calls == [{'reason': 'hook:reconcile_mismatch',
                         'save_screenshot': True}]
    assert '[stop]' not in caplog.text, '[stop] 行归框架层,闭包只发原因日志'
    assert 'gold' in caplog.text and '17' in caplog.text \
        and '19' in caplog.text, '闭包日志带失配字段与两值'


def test_andon_no_latch_repeat_fires_stop_again():
    """无每局一次性标志位:重复触发照发 stop——幂等收口与截图防重由框架
    stop_running(幂等 + was_live 门)保证,闭包不自维护状态。"""
    rc = _Rc()
    set_reconcile_andon_hook(
        app_mod._build_reconcile_andon(SimpleNamespace(run_context=rc)))
    try:
        fire_reconcile_andon(dict(_ROW))
        fire_reconcile_andon(dict(_ROW))
    finally:
        set_reconcile_andon_hook(None)
    assert len(rc.calls) == 2
    assert all(c['reason'] == 'hook:reconcile_mismatch'
               and c['save_screenshot'] for c in rc.calls)
