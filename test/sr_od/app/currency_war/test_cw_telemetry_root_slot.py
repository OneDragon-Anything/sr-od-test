"""遥测根装配槽锁(T-120 批 1;F4 落盘根槽 + T-129/T-130 journal 根槽)。

出处 = T-120 方案 v2(``.debug/temp/currency_war/t120_sim_redesign/
方案.md``,**易失产物**)§4-2「落盘根装配槽」+ §2.5/§7.1 telemetry/
state.py 行(F4 方案审修正);journal 根槽 = T-129 严查报告「sim 与
live 共写同一 journal 文件的 run_id 过滤设计」注记的批 1 承接(T-130
任务行④),机制裁决 = 写端根隔离(见 op_journal.set_journal_dir 注)。
ADR 落点待 T-120 退役批分配,后续批回填编号。

锁的语义:

- **缺省 None = 生产路径**(方案 §3.2 装配纪律的槽版):两槽缺省时
  recorder 根 = kernel/cw_observe.DEFAULT_REPLAY_DIR、journal 路径 =
  模块常量(其 parent = LIVE_DIR,既有根布局锁 test_cw_infra_locks
  同判)。红 = 生产缺省路径被槽改动劫持。
- **接通/复位语义**:接指新根后 recorder 重建(内存累积按根隔离)、
  journal 现算路径改指;复位后两根回生产缺省。红 = 槽半程(改根不
  重建/复位失灵)。
- **写端隔离实证**:journal 槽接指 tmp 根时,op 行落 tmp 根——
  「假局 journal 行不进 live 流」的机器可判形(不读真实 live 根,
  纪律 19;live 侧由既有根布局锁与槽缺省锁合辖)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel.cw_observe import (
    DEFAULT_REPLAY_DIR,
    LIVE_DIR,
)
from sr_od.application.currency_war.telemetry import op_journal
from sr_od.application.currency_war.telemetry import state as tel_state


@pytest.fixture(autouse=True)
def _slots_isolated():
    """两槽都是进程全局态——teardown 强制复位(测试纪律 4:隔离整条
    副作用链;残留会把后续测试的遥测写去假局根/继续改指 tmp)。"""
    yield
    tel_state.set_recorder_replay_dir(None)
    op_journal.set_journal_dir(None)


class TestRecorderRootSlot:
    """recorder 落盘根槽(F4;install_obs_ports 槽模式的遥测侧同构)。"""

    def test_default_none_keeps_production_root(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """缺省 None = 生产路径:get_recorder 惰性构造指向缺省根
        (DEFAULT_REPLAY_DIR = telemetry/live)。"""
        monkeypatch.setattr(tel_state, '_RECORDER', None)   # 不触真实单例
        tel_state.set_recorder_replay_dir(None)
        assert tel_state.get_recorder().replay_dir == DEFAULT_REPLAY_DIR

    def test_slot_redirects_and_rebuilds_singleton(
            self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """接通新根 → 单例按新根重建(内存累积随根隔离,不复用旧实例);
        复位 → 回生产缺省。"""
        monkeypatch.setattr(tel_state, '_RECORDER', None)
        tel_state.set_recorder_replay_dir(tmp_path)
        rec = tel_state.get_recorder()
        assert rec.replay_dir == tmp_path
        # 重建语义:换根后 get_recorder 不得返回旧根实例
        other = tmp_path / 'other'
        tel_state.set_recorder_replay_dir(other)
        rec2 = tel_state.get_recorder()
        assert rec2 is not rec and rec2.replay_dir == other

    def test_reset_returns_to_production_root(
            self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(tel_state, '_RECORDER', None)
        tel_state.set_recorder_replay_dir(tmp_path)
        tel_state.set_recorder_replay_dir(None)
        assert tel_state.get_recorder().replay_dir == DEFAULT_REPLAY_DIR


class TestJournalRootSlot:
    """journal 根槽(T-129/T-130 混流注记落地;写端根隔离机制)。"""

    def test_default_none_keeps_production_path(self) -> None:
        """缺省 = 模块常量缝(_JOURNAL,既有测试的落盘重定向缝保持
        活读;其 parent = LIVE_DIR 与根布局锁同判)。"""
        op_journal.set_journal_dir(None)
        assert op_journal._journal_path() is op_journal._JOURNAL
        assert op_journal._JOURNAL.parent == LIVE_DIR

    def test_slot_redirects_write_side(self, tmp_path: Path,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
        """接指 tmp 根 → op 行落 tmp 根(写端隔离实证;run_id 键不变,
        读端过滤能力不受影响的载体)。"""
        op_journal.set_journal_dir(tmp_path)
        monkeypatch.setattr(op_journal, 'current_run_id',
                            lambda: 'run_jslot')
        token = op_journal.record_op_enter('货币战争-测试op', 1, 1,
                                           obs={'probe': True})
        assert token is not None
        out = tmp_path / 'op_journal.jsonl'
        assert out.exists(), 'journal 行未落接通的根槽'
        import json
        row = json.loads(out.read_text(encoding='utf-8').splitlines()[0])
        assert row['run_id'] == 'run_jslot'
        assert row['kind'] == 'op' and row['event'] == 'enter'

    def test_reset_falls_back_to_constant_seam(self, tmp_path: Path) -> None:
        """复位后回落常量缝:monkeypatch ``_JOURNAL`` 的既有重定向手法
        (test_cw_op_journal/test_cw_dispatch_wrapper 同款)在槽复位态
        下继续生效——两缝叠加不互相遮蔽。"""
        op_journal.set_journal_dir(tmp_path / 'a')
        op_journal.set_journal_dir(None)
        assert op_journal._journal_path() is op_journal._JOURNAL

    def test_exit_row_via_slot_pairing(self, tmp_path: Path,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
        """enter/exit 成对行经槽落同一根(token 配对语义不受改根影响)。"""
        op_journal.set_journal_dir(tmp_path)
        monkeypatch.setattr(op_journal, 'current_run_id',
                            lambda: 'run_jpair')
        token = op_journal.record_op_enter('货币战争-测试op', 1, 2)
        op_journal.record_op_exit(token, outcome='ok', detail='收工')
        lines = (tmp_path / 'op_journal.jsonl').read_text(
            encoding='utf-8').splitlines()
        assert len(lines) == 2
        events = [json.loads(x)['event'] for x in lines]
        assert events == ['enter', 'exit']
