"""分包期 4:telemetry 上行出口钩子位(kernel/cw_telemetry_exit)契约锁。

DESIGN §3.3-④ 三类出口(落账/安灯/run_id 归属键)统一钩子化的行为面:
①缺省关:未注入时 current_run_id=''、落账 no-op、安灯出口未装;
②注入:install_exit_hooks 逐槽接线后出口转发真实现;
③安灯执行器与出口槽的伴随语义:出口未装 → 停线仍执行、不落 flag(缺省关,
生产武装点=CurrencyWarApp.__init__ 与 set_l0_andon_handler 同点)。
全部零真实落盘(monkeypatch 槽位自动还原)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_observe, cw_telemetry_exit
from sr_od.application.currency_war.telemetry import cw_telemetry


class _FakeRunContext:
    def __init__(self):
        self.reasons: list[str] = []

    def stop_running(self, reason: str = '') -> None:
        self.reasons.append(reason)


def test_exit_default_off(monkeypatch):
    """缺省关:七槽全 None → run_id 空串、三类落账 no-op、安灯出口未装。"""
    _clear_slots(monkeypatch)
    assert cw_telemetry_exit.current_run_id() == ''
    cw_telemetry_exit.record_defect('gold', 'k', 'e', 'o')          # no-op 不抛
    cw_telemetry_exit.record_exogenous(1, 'probe')
    cw_telemetry_exit.bypass_obs_conflict_to_defect({'field': 'gold'})
    cw_telemetry_exit.record_exec_event('r', 0, 'V2Shadow', 's', 'e')
    assert cw_telemetry_exit.andon_exit_installed() is False


def test_exit_install_wires_all_slots(monkeypatch):
    """install_exit_hooks 逐槽接线:run_id provider 与落账出口转发真实现。"""
    _clear_slots(monkeypatch)
    seen: list[tuple[tuple, dict]] = []

    def _fake_defect(*a, **k):
        seen.append((a, k))

    cw_telemetry_exit.install_exit_hooks(
        run_id_provider=lambda: 'run_probe',
        record_defect=_fake_defect,
        record_exogenous=lambda *a, **k: None,
        bypass_obs_conflict_to_defect=lambda rec: None,
        record_exec_event=lambda *a, **k: None,
        l0_andon_flag_path=cw_telemetry.l0_andon_flag_path,
        write_l0_andon_flag=cw_telemetry.write_l0_andon_flag)
    assert cw_telemetry_exit.current_run_id() == 'run_probe'
    cw_telemetry_exit.record_defect('gold', 'k', 'e', 'o', plane=1, round_num=2,
                                    verdict='v', confidence=0.5)
    assert len(seen) == 1
    _args, kwargs = seen[0]
    # 出口逐参关键字转发:捕获行按形参名断言
    assert kwargs['surface'] == 'gold' and kwargs['kind'] == 'k'
    assert kwargs['expected'] == 'e' and kwargs['observed'] == 'o'
    assert kwargs['plane'] == 1 and kwargs['round_num'] == 2
    assert kwargs['verdict'] == 'v' and kwargs['confidence'] == 0.5


def test_andon_executor_without_exit_stops_but_no_flag(monkeypatch, tmp_path):
    """出口未装 → 停线三要素仍执行(停线是主哨兵),不触达 flag 路径。"""
    _clear_slots(monkeypatch)
    ctx = SimpleNamespace(controller=None, run_context=_FakeRunContext())
    monkeypatch.setattr(cw_observe, '_save_andon_frame', lambda c, p: '')
    ok = cw_observe.stop_for_l0_andon(
        {'run_id': 'run_x', 'surface': 'gold', 'kind': 'k',
         'expected': 'e', 'observed': 'o', 'plane': 1, 'round_num': 1,
         'refs': [], 'shot': None}, ctx=ctx)
    assert ok is True
    assert ctx.run_context.reasons == ['hook:cw_l0_andon']
    assert not (tmp_path / 'l0_andon_hook.flag').exists()


def _clear_slots(monkeypatch) -> None:
    """七槽全清(缺省关基线;monkeypatch 自动还原)。"""
    for name in ('_run_id_provider', '_record_defect', '_record_exogenous',
                 '_bypass_obs_conflict_to_defect', '_record_exec_event',
                 '_l0_andon_flag_path', '_write_l0_andon_flag'):
        monkeypatch.setattr(cw_telemetry_exit, name, None)
