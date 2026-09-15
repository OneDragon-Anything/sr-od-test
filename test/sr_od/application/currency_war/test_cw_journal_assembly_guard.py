"""journal 流水装配兜底 + 收口落盘锁(T-258;W3 欠账修复的行为契约)。

锁三件:

1. ``ensure_journal_assembly`` 幂等兜底:未装配 → 按缺省根补装(测试进程
   经 conftest ``_isolate_state_journal`` 重定向 = tmp,证明测试零真实账面
   写入);已装配 → 现役实例原样保留(兜底口不顶掉测试/生产自管装配)。
2. run 领取单点接线:``ensure_run_started`` 必经兜底口——重置后首领取即
   装配(生产装配契约 = app 装配段显式 + run 领取兜底,journal.md §7)。
3. 收口落盘:``close_run`` 在批量 flush 阈值之前把缓冲行落盘——批量阈值
   之间收口时档案装配读盘漏局终行的实证形态(g_20260915_070645 档案缺
   ``endgame.match_final``;行随进程终止永失)。

背景实证:2026-09-14 18:56 起 8 连局零 state 行零档案(op 直跑 CwLoop 未经
app 装配段,sink 缺席行按「诚实缺失」静默不落;深检 run_20260915_054718.md
§0)。修法正本 = kernel ``ensure_journal_assembly`` docstring。
"""
from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel.cw_state_journal import (
    ensure_journal_assembly,
    flush_pending,
    install_state_telemetry,
    reset_state_telemetry,
    state_journal_instance,
)
from sr_od.application.currency_war.telemetry.state import (
    close_run,
    current_run_id,
    ensure_run_started,
    reset_run_state,
    start_run,
)


@pytest.fixture
def _reset_run_cluster() -> None:
    """run 态簇前后复位(telemetry.state 模块全局;防跨测试残留)。"""
    reset_run_state()
    yield
    reset_run_state()


def test_ensure_assembly_installs_at_default_root_when_absent(
        tmp_path: Path) -> None:
    """未装配时兜底口按缺省根补装(测试进程 = conftest 重定向的 tmp 根)。"""
    reset_state_telemetry()
    assert state_journal_instance() is None
    ensure_journal_assembly(current_run_id)
    journal = state_journal_instance()
    assert journal is not None
    # conftest 把缺省根缝重定向到本测试的 tmp_path——兜底装配落 tmp,
    # 证明「自动装真实现」在测试进程不触真实账面(测试纪律 2)。
    assert journal.path == tmp_path / 'state' / 'journal.jsonl'


def test_ensure_assembly_preserves_armed_instance(tmp_path: Path) -> None:
    """已装配时兜底口零成本直过(现役实例原样保留,不 reset 不顶掉)。"""
    reset_state_telemetry()
    mine = install_state_telemetry(tmp_path / 'mine' / 'journal.jsonl')
    ensure_journal_assembly(current_run_id)
    assert state_journal_instance() is mine


def test_ensure_run_started_wires_assembly_fallback(
        _reset_run_cluster: None) -> None:
    """run 领取单点接线:重置后首领取即装配(生产 4 调用点共同必经口)。"""
    reset_state_telemetry()
    assert state_journal_instance() is None
    ensure_run_started(match=object(), difficulty='A8')
    assert state_journal_instance() is not None
    assert current_run_id() != ''


def test_close_run_flushes_buffered_rows_before_threshold(
        tmp_path: Path, _reset_run_cluster: None) -> None:
    """收口落盘:批量阈值内的缓冲行随 close_run 落盘(装配读盘不漏局终行)。"""
    jpath = tmp_path / 'journal.jsonl'
    install_state_telemetry(jpath)
    rid = start_run()
    journal = state_journal_instance()
    assert journal is not None
    journal.append({'run_id': rid, 'v': 1, 'row': 'write', 'field': 'gold'})
    assert not jpath.exists()   # 仍在内存缓冲(阈值 64 未到)
    close_run(result='loss', plane_reached=2, rounds_survived=7,
              final_hp=0, notes='auto')
    lines = jpath.read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1
    assert state_journal_instance() is not None   # 收口 flush ≠ 拆装配


def test_flush_pending_without_instance_is_zero() -> None:
    """无装配实例时 flush_pending 恒 0(收口单点在未武装进程零副作用)。"""
    reset_state_telemetry()
    assert flush_pending() == 0
