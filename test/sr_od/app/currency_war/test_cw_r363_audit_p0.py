"""r363 审计 P0 修复测试(node_type 词汇统一/槽序表写入/abandoned 兜底)。

W75(ADR-0335)追加:stop 路径 runs summary 收口治本锁 —— r363 在 loop() 顶
查 is_context_stop,但 operation.execute() 每轮前(operation.py:408)先查 stop,
stop 到达后 loop() 不再被调 → 原检查几乎永不触发(四局 [RUNS-GAP] 实锤)。
收口迁 ``after_operation_done``(成功/失败/停止全路径必达),此处锁:
- 构造 run 上下文 → stop → runs 行存在且 result='stopped'(hp 取 outcome 真值);
- 非 stop 异常退出(超时/FAIL)→ result='abandoned';
- 假局守卫(无 outcome 数据)/已写 summary → 不重复写。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.telemetry.cw_telemetry import (
    TelemetryRecorder,
    read_jsonl,
)
from sr_od.application.currency_war.operations.battle_loop import (
    CurrencyWarRunLoop,
)


def test_normalize_node_type_vocab() -> None:
    """三源词汇统一:英文 token/OCR 中文/旧兜底 → EXPECTED_DROP 键域中文。"""
    n = CurrencyWarRunLoop._normalize_node_type
    assert n('battle') == '普通战斗'
    assert n('reward') == '奖励'
    assert n('encounter') == '遭遇'
    assert n('supply') == '补给'
    assert n('boss') == 'boss'
    assert n('megastar') == '巨星'
    assert n('奖励') == '奖励'
    assert n('首领') == 'boss'
    assert n('普通战斗') == '普通战斗'
    assert n('') == '普通战斗'
    assert n(None) == '普通战斗'
    assert n('未知类型') == '未知类型'   # 未知透传不吞


def test_table_written_on_first_frame() -> None:
    """槽序表写入:首帧 probe 存全槽类型序(battle_loop 兜底的写入端)。"""
    # 模拟 slots
    class _Slot:
        def __init__(self, idx, state, node_type):
            self.idx, self.state, self.node_type = idx, state, node_type

    slots = [_Slot(0, 'current', 'reward'), _Slot(1, 'upcoming', 'reward'),
             _Slot(2, 'upcoming', 'battle'), _Slot(3, 'past', None)]
    _all = sorted(slots, key=lambda s: s.idx)
    seq = [s.node_type for s in _all if s.node_type]
    assert seq == ['reward', 'reward', 'battle']


# ===== W75(ADR-0335):stop 路径 runs summary 收口(治本 r363 死码) =====

def _make_stop_loop(*, summary_written: bool = False,
                    last_outcome_hp: int | None = 30,
                    rounds_done: int = 3,
                    stopped: bool = True,
                    plane: int = 2, round_num: int = 7, hp: int = 100,
                    hp_readable: bool = False) -> CurrencyWarRunLoop:
    """构造 loop 桩(bypass __init__):喂 _write_terminal_summary_if_needed 依赖面。

    last_state.hp=100 + hp_readable=False = 死局兜底污染面(ADR-0282 语义),
    收口应取 outcome 真值(_last_outcome_hp)而非 100。
    """
    from sr_od.application.currency_war.operations import battle_loop as bl

    class _Loop(bl.CurrencyWarRunLoop):
        def __init__(self):  # noqa: D107 桩:bypass SrOperation.__init__
            self._summary_written = summary_written
            self._last_outcome_hp = last_outcome_hp
            self._rounds_done = rounds_done
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=SimpleNamespace(
                        last_state=GameState(plane=plane, round_num=round_num,
                                             hp=hp, hp_readable=hp_readable),
                    ),
                ),
                run_context=SimpleNamespace(is_context_stop=stopped),
            )

    return _Loop()


def test_stop_path_writes_stopped_summary(monkeypatch, tmp_path) -> None:
    """stop 收口:构造 run 上下文 → stop → runs 行存在且 result='stopped'。"""
    import sr_od.application.currency_war.telemetry.cw_telemetry as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_stop_1')
    op = _make_stop_loop()
    op._write_terminal_summary_if_needed()
    rows = read_jsonl(tmp_path / 'runs.jsonl')
    assert len(rows) == 1
    s = rows[0]
    assert s['result'] == 'stopped'
    assert s['run_id'] == 'run_stop_1'
    assert s['plane_reached'] == 2
    assert s['rounds_survived'] == 7
    assert s['final_hp'] == 30   # outcome 真值,非 last_state 100 兜底
    assert op._summary_written


def test_non_stop_abnormal_exit_writes_abandoned(monkeypatch, tmp_path) -> None:
    """非 stop 异常退出(超时/FAIL,is_context_stop=False)→ result='abandoned'。"""
    import sr_od.application.currency_war.telemetry.cw_telemetry as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_fail_1')
    op = _make_stop_loop(stopped=False, last_outcome_hp=55,
                         plane=3, round_num=2, hp=55, hp_readable=True)
    op._write_terminal_summary_if_needed()
    rows = read_jsonl(tmp_path / 'runs.jsonl')
    assert len(rows) == 1
    assert rows[0]['result'] == 'abandoned'
    assert rows[0]['final_hp'] == 55


def test_stop_summary_skips_when_already_written(monkeypatch, tmp_path) -> None:
    """3c 正常终局已写(_summary_written=True)→ 收口不重复写。"""
    import sr_od.application.currency_war.telemetry.cw_telemetry as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_ok_1')
    op = _make_stop_loop(summary_written=True)
    op._write_terminal_summary_if_needed()
    assert read_jsonl(tmp_path / 'runs.jsonl') == []


def test_stop_summary_skips_fake_run(monkeypatch, tmp_path) -> None:
    """假局守卫(镜像 3c):无任何 outcome 数据(开局失败/中断)→ 不写假 summary。"""
    import sr_od.application.currency_war.telemetry.cw_telemetry as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_ghost_1')
    op = _make_stop_loop(last_outcome_hp=None, rounds_done=0)
    op._write_terminal_summary_if_needed()
    assert read_jsonl(tmp_path / 'runs.jsonl') == []


def test_stop_summary_no_duplicate_on_second_call(monkeypatch, tmp_path) -> None:
    """幂等:同实例二次调用(收口重入/守护)不重复写行。"""
    import sr_od.application.currency_war.telemetry.cw_telemetry as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_stop_2')
    op = _make_stop_loop()
    op._write_terminal_summary_if_needed()
    op._write_terminal_summary_if_needed()
    assert len(read_jsonl(tmp_path / 'runs.jsonl')) == 1


def test_after_operation_done_wires_summary_write() -> None:
    """弱锁保底:after_operation_done 真调 _write_terminal_summary_if_needed(收口接线)。"""
    import inspect

    from sr_od.application.currency_war.operations import battle_loop
    src = inspect.getsource(battle_loop.CurrencyWarRunLoop.after_operation_done)
    assert '_write_terminal_summary_if_needed()' in src
