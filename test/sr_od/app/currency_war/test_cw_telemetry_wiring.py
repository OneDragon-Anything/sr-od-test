"""test_cw_telemetry_wiring 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_strategy_planner.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。

删除波 1(用户 2026-09-10 直迁裁定)重写:①decisions 行披露键面(record_
decision)退役——session 字段与 ExecState 正式字段面保留;②观察冲突证据
归宿改 journal obs_event 行(旧文件写入退役);③简报局间缓冲退役——
record_exogenous 出口恒 no-op 桩。存档读端兼容面(②c)保留。
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel import cw_observe, cw_state_journal
from sr_od.application.currency_war.kernel.cw_board_state import board_state_of
from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of

# 分包期 6:恢复兜底族(DESIGN §4.4 hooks 行)归 sim/ledger_hooks,
# telstate.start_run 经该模块属性查找调用 → 桩点随生产引用址重钉
from sr_od.application.currency_war.strategies.impl.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.telemetry import recorder
from sr_od.application.currency_war.telemetry import state as telstate


def _setup_recorder(monkeypatch, tmp_path: Path, run_id: str = 'w603t') -> None:
    """recorder/run_id 指向 tmp_path(测试纪律:不写真实 .debug/)。"""
    monkeypatch.setattr(telstate, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(telstate, '_CURRENT_RUN_ID', run_id)
    monkeypatch.setattr(telstate, '_CURRENT_DIFFICULTY', 'A8')
    monkeypatch.setattr(telstate, '_RUN_CLOSED', False)
    # 缺陷台账复现计数/L0 副作用链隔离(W505 同款)
    monkeypatch.setattr(telstate, '_defect_seen', {})
    monkeypatch.setattr(telstate, '_defect_seen_run', '')
    monkeypatch.setattr(telstate, '_L0_ANDON_HANDLER', lambda payload: True)
    monkeypatch.setattr(telstate, '_L0_ANDON_FIRED_RUNS', set())
    # 分包期 4:obs_conflict 的 run_id 归属键读 kernel.cw_telemetry_exit 钩子位,
    # provider 钉回本模块 current_run_id(随 _CURRENT_RUN_ID 桩值走)
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    monkeypatch.setattr(cw_telemetry_exit, '_run_id_provider',
                        telstate.current_run_id)


def _rows(tmp_path: Path, name) -> list[dict]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


# ===== ① 披露键进 decisions 遥测行(退役重写)=====

def _fake_match(counters: tuple[int, int] = (2, 1),
                ledger: object | None = None):
    """fake ctx.cw_match 容器(session 带披露键)。"""
    sess = StrategySession()
    state_of(sess).v3_blood_budget_rejects = counters[0]
    state_of(sess).v3_blood_budget_refresh_rejects = counters[1]
    exec_state_of(sess).xp_expect_ledger = ledger
    return SimpleNamespace(session=sess)


def test_disclosure_writer_retired_session_fields_survive(
        tmp_path: Path, monkeypatch) -> None:
    """锁①(删除波 1 重写):decisions 行披露键写入端退役;承载语义的
    session 字段(血预算拒因计数)与 ExecState 正式字段(经验账本)照常
    存续——消费切换批按 strategy_state_of/exec_state_of 读面重接。"""
    _setup_recorder(monkeypatch, tmp_path)
    from sr_od.application.currency_war.telemetry.recorder import (
        TelemetryRecorder,
    )
    assert not hasattr(TelemetryRecorder, 'record_decision'), \
        '决策行写入方法应已退役(防半删)'
    m = _fake_match((2, 1))
    sess = m.session
    assert state_of(sess).v3_blood_budget_rejects == 2
    assert state_of(sess).v3_blood_budget_refresh_rejects == 1
    assert exec_state_of(sess).xp_expect_ledger is None


# ===== ② 观察冲突证据行(删除波 1:归宿 = journal obs_event)=====

@pytest.fixture()
def _journal(tmp_path: Path, monkeypatch):
    """装一份指到 tmp 的账本(行落盘可断言;teardown 复位模块全局)。"""
    j = cw_state_journal.install_state_telemetry(
        tmp_path / 'state' / 'journal.jsonl', flush_every=1,
        run_id_provider=telstate.current_run_id)
    yield j
    cw_state_journal.reset_state_telemetry()


def test_obs_conflict_row_lands_in_journal_with_run_id(
        tmp_path: Path, monkeypatch, _journal) -> None:
    """锁②a(重写):冲突证据行进账本(obs_event)带 run_id(取 current_
    run_id;调用方零改动);旧流文件零新增。"""
    _setup_recorder(monkeypatch, tmp_path, run_id='run_w603x')
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    bs = board_state_of(SimpleNamespace())
    monkeypatch.setattr(cw_telemetry_exit, '_obs_event_board_provider',
                        lambda: bs)
    cw_observe.obs_conflict('gold_delta', 45, 20, None,
                            verdict='测试', source='w603')
    rows = [r for r in _rows(tmp_path, Path('state') / 'journal.jsonl')
            if r.get('row') == 'obs_event']
    assert len(rows) == 1
    r = rows[0]
    assert r['run_id'] == 'run_w603x'
    assert r['field'] == 'gold_delta'
    assert r['verdict'] == '测试'
    assert not (tmp_path / 'obs_conflicts.jsonl').exists(), \
        '旧流文件零新增(写入端已退役)'


def test_obs_conflict_no_row_outside_run(tmp_path: Path, monkeypatch,
                                         _journal) -> None:
    """锁②b(重写):局外冲突(run_id 空)账本拒写假行(§3.2.3);零文件产出。"""
    _setup_recorder(monkeypatch, tmp_path, run_id='')
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    bs = board_state_of(SimpleNamespace())
    monkeypatch.setattr(cw_telemetry_exit, '_obs_event_board_provider',
                        lambda: bs)
    cw_observe.obs_conflict('level', 4, 5, None, verdict='测试')
    assert [r for r in _rows(tmp_path, Path('state') / 'journal.jsonl')
            if r.get('row') == 'obs_event'] == []
    assert not (tmp_path / 'obs_conflicts.jsonl').exists()


# [退役墓碑,W3] test_query_obs_conflicts_filters_by_run_id 随 query_obs_conflicts 旧视图退役(W3);obs_conflicts 写面收编 journal obs_event(删除波 1)后,冲突读数走 journal_query.view_events。git 历史可复活。
# ===== ③ 简报行 run_id 归属(删除波 1:局间缓冲与直写面整体退役)=====

def test_record_exogenous_exit_stub_is_total_noop(tmp_path: Path,
                                                  monkeypatch) -> None:
    """锁③(重写):kernel 出口 record_exogenous = 退役 no-op 桩——任何
    kind(简报/局外事件族)任何 run 态都零落盘、零缓冲(旧局间缓冲槽
    _PENDING_BRIEFING_ROWS 已删)。锚的候裁归宿见 retirement.md §5-7。"""
    _setup_recorder(monkeypatch, tmp_path, run_id='')
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    assert not hasattr(telstate, '_PENDING_BRIEFING_ROWS'), \
        '简报局间缓冲槽应已随删除波 1 退役(防半删)'
    cw_telemetry_exit.record_exogenous(0, 'briefing', detail='affixes=[甲]')
    cw_telemetry_exit.record_exogenous(3, 'briefing', detail='plane2')
    cw_telemetry_exit.record_exogenous(0, 'node_enter', detail='局外弹窗')
    assert _rows(tmp_path, 'exogenous.jsonl') == [], \
        'exogenous 出口恒 no-op(旧流写入端退役)'


# ===== ②c 存档读端兼容面(保留)=====

def _archive_read_face_placeholder() -> None:
    """(原②c 读端锁 = query 对冻结存量档案的视图契约,由 gold_flow_
    channel/telemetry_archive 各读面测承;此占位防误删本节说明。)"""
    return None
