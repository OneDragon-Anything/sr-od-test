# -*- coding: utf-8 -*-
"""test_cw_r363_audit_p0 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_legacy_audit.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。"""
from __future__ import annotations



from types import SimpleNamespace as _r363_audit_p0_SimpleNamespace

from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.operations.cw_loop import CwLoop
from sr_od.application.currency_war.telemetry.query import read_jsonl
from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder


def test_normalize_node_type_vocab() -> None:
    """三源词汇统一:英文 token/OCR 中文/旧兜底 → EXPECTED_DROP 键域中文。

    (W971 05-battle §1 P4:词汇 normalizer 随结算链收编进 CwScreenBattleWait。)
    """
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait import (
        CwScreenBattleWait,
    )
    n = CwScreenBattleWait._normalize_node_type
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


# ===== W75(ADR-0335):stop 路径 runs summary 收口(治本 r363 死码) =====
# (2026-09-03 瘦身批:test_table_written_on_first_frame 删除——测试体自建
#  slots 自己排序断言自己,零生产代码触达(纪律 10)。)

def _make_stop_loop(*, summary_written: bool = False,
                    last_outcome_hp: int | None = 30,
                    rounds_done: int = 3,
                    stopped: bool = True,
                    plane: int = 2, round_num: int = 7, hp: int = 100,
                    hp_readable: bool = False) -> CwLoop:
    """构造 loop 桩(bypass __init__):喂 _write_terminal_summary_if_needed 依赖面。

    last_state.hp=100 + hp_readable=False = 死局兜底污染面(ADR-0282 语义),
    收口应取 outcome 真值(_last_outcome_hp)而非 100。
    """
    from sr_od.application.currency_war.operations import cw_loop as bl

    class _Loop(bl.CwLoop):
        def __init__(self):  # noqa: D107 桩:bypass SrOperation.__init__
            self._summary_written = summary_written
            # (W971 05-battle §1 P4:hp/轮计数真值源收编进 SettlementState,
            #  收口经 self._settle 读——桩同形。)
            self._settle = _r363_audit_p0_SimpleNamespace(
                last_outcome_hp=last_outcome_hp, rounds_done=rounds_done)
            self.ctx = _r363_audit_p0_SimpleNamespace(
                cw_match=_r363_audit_p0_SimpleNamespace(
                    session=_r363_audit_p0_SimpleNamespace(
                        last_state=GameState(plane=plane, round_num=round_num,
                                             hp=hp, hp_readable=hp_readable),
                    ),
                ),
                run_context=_r363_audit_p0_SimpleNamespace(is_context_stop=stopped),
            )

    return _Loop()


def test_stop_path_writes_stopped_summary(monkeypatch, tmp_path) -> None:
    """stop 收口:构造 run 上下文 → stop → runs 行存在且 result='stopped'。"""
    import sr_od.application.currency_war.telemetry.state as tel
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
    import sr_od.application.currency_war.telemetry.state as tel
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


def test_zero_outcome_but_observed_writes_row(monkeypatch, tmp_path) -> None:
    """P4R4 假局守卫语义修正:零 outcome 但观察过对局态 = **真局** → 必写
    终局行(run_20260903_004418 超时 fail / run_20260903_204908 stop 两实例
    runs 缺行根因:部署死循环阶段零结算行被旧守卫当假局吞掉)。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_zeroutcome_1')
    op = _make_stop_loop(last_outcome_hp=None, rounds_done=0,
                         stopped=False, plane=1, round_num=2, hp=100)
    op._write_terminal_summary_if_needed()
    rows = read_jsonl(tmp_path / 'runs.jsonl')
    assert len(rows) == 1
    assert rows[0]['result'] == 'abandoned'
    assert rows[0]['plane_reached'] == 1 and rows[0]['rounds_survived'] == 2
    assert op._summary_written


def test_stop_summary_skips_true_fake_run(monkeypatch, tmp_path) -> None:
    """真·假局守卫(P4R4 新语义):从未观察到对局态(last_state 缺失)
    且零 outcome = 开局即失败 → 不写假 summary(镜像 3c 污染分母防线)。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_ghost_1')
    from sr_od.application.currency_war.operations import cw_loop as bl

    class _GhostLoop(bl.CwLoop):
        def __init__(self):  # noqa: D107 桩:bypass __init__
            self._summary_written = False
            self._settle = _r363_audit_p0_SimpleNamespace(
                last_outcome_hp=None, rounds_done=0)
            self.ctx = _r363_audit_p0_SimpleNamespace(
                cw_match=_r363_audit_p0_SimpleNamespace(session=None),
                run_context=_r363_audit_p0_SimpleNamespace(is_context_stop=True),
            )

    op = _GhostLoop()
    op._write_terminal_summary_if_needed()
    assert read_jsonl(tmp_path / 'runs.jsonl') == []


def test_stop_summary_no_duplicate_on_second_call(monkeypatch, tmp_path) -> None:
    """幂等:同实例二次调用(收口重入/守护)不重复写行。"""
    import sr_od.application.currency_war.telemetry.state as tel
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

    from sr_od.application.currency_war.operations import cw_loop
    src = inspect.getsource(cw_loop.CwLoop.after_operation_done)
    assert '_write_terminal_summary_if_needed()' in src


def test_terminal_summary_triggers_archive_assemble() -> None:
    """弱锁(P4R4):补写收口连带按局存档装配——非正常终局的 runs 行
    此前没有装配机会 → 对局档案缺该局(run_20260903_004418 实证)。"""
    import inspect

    from sr_od.application.currency_war.operations import cw_loop
    src = inspect.getsource(cw_loop.CwLoop._write_terminal_summary_if_needed)
    assert 'assemble_pending' in src
