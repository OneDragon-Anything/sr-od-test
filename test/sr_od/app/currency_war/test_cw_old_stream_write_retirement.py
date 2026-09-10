"""旧流写入端退役锁(删除波 1;用户 2026-09-10 直迁裁定)。

裁定口径:不用影子开关/影子期,新账本 journal 无条件常开后,旧 12 流中
「策略源收编 9 流」的写入端直接删除(处置表单一源 =
docs/develop/currency_war/game_state/retirement.md §2)。禁碰面 =
保留 2 流(defect_ledger/op_journal)+ 逐 key 审计流(cw4_counters)
+ 清点补遗流(board_state_archive)+ journal 写路径本体 + 旧档案只读
判读面(query/cli/match_archive 读旧档)。

锁面 =
- 结构删净锁:9 流 writer 符号在 telemetry.recorder 上不存在;src 生产树
  无写入调用点/流文件名残留(防半删:writer 删了调用点留着 = 死代码);
- 行为零产出锁:模拟流(run 生命周期 + BoardState 写入 + obs_conflict
  收编面 + run 收口)跑完,旧 9 流文件零新增;journal 照常产出
  (write 行 + obs_event 行,run 归属一致);
- 常开锁:state_journal 影子开关已销案(config 无此字段,app 装配段
  无条件武装 + obs_event 收编制 provider 已注册)。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war import currency_war_app as cw_app_mod
from sr_od.application.currency_war import currency_war_config as cw_cfg_mod
from sr_od.application.currency_war.kernel import cw_state_journal
from sr_od.application.currency_war.kernel.cw_board_state import (
    board_state_of,
)


# ---- W1 sig 铺满 helper(测试写入口签名必填,ADR-0634;actor 已登记)----
from sr_od.application.currency_war.kernel.cw_board_state import (  # noqa: E402
    ChannelSig as _ChannelSig,
    register_sig_actors as _register_sig_actors,
)

_register_sig_actors('TestSigWriter')


def _sig() -> "_ChannelSig":
    """渠道①签名(obs 族;观察/沿用/先验/离屏/观察事件)。"""
    return _ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _lsig() -> "_ChannelSig":
    """渠道②签名(logic_action 族;逻辑写入/confirm)。"""
    return _ChannelSig(family='logic_action', actor='TestSigWriter',
                       mode='compute')


def _hsig() -> "_ChannelSig":
    """渠道③签名(logic_hook 族;relay 中继)。"""
    return _ChannelSig(family='logic_hook', actor='TestSigWriter',
                       mode='compute')
from sr_od.application.currency_war.kernel.cw_observe import obs_conflict
from sr_od.application.currency_war.telemetry import state as tel_state

#: 收编 9 流的旧流文件名(本批写入端退役对象;retirement.md §2 处置表)。
_OLD_STREAM_FILES: tuple[str, ...] = (
    'decisions.jsonl', 'outcomes.jsonl', 'exogenous.jsonl',
    'spend_ledger.jsonl', 'shop_snapshots.jsonl', 'exec_events.jsonl',
    'invest_cards.jsonl', 'obs_conflicts.jsonl', 'runs.jsonl',
)

#: 随旧流写入端退役的 writer 符号(telemetry.recorder 模块面)。
_RETIRED_RECORDER_SYMBOLS: tuple[str, ...] = (
    'record_decision', 'record_outcome', 'record_exogenous',
    'record_event_choice', 'record_sell_income', 'record_modality_gold',
    'record_spend_unit', 'record_invest_cards', 'record_shop_snapshot',
)

#: TelemetryRecorder 类面上退役的方法(保留面 = record_defect/_append/
#: _path/replay_dir 根槽载体)。
_RETIRED_RECORDER_METHODS: tuple[str, ...] = (
    'record_decision', 'record_outcome', 'record_run_summary',
    'record_exec_event', 'record_exogenous', 'record_spend_unit',
)

#: writer 符号/流文件名的只读豁免面(旧档案判读/装配/缺陷 refs/读侧检查;
#: 这些面读旧档案但零写入)。相对 src/sr_od/application/currency_war。
#: 三处书面豁免(逐条申报):kernel/cw_telemetry_exit.py = record_exogenous
#: no-op 桩(护在飞挂起面调用方,恒零产出);kernel/cw_anchor.py = 未入库
#: 在飞文件(T-221 挂起面禁碰,经出口桩上行);strategies/impl/mandate_v1/
#: encounter.py = mandate 本体(禁碰,仅 docstring 提及)。
_READ_FACE_WHITELIST: frozenset[str] = frozenset({
    'telemetry/query.py', 'telemetry/cli.py', 'telemetry/match_archive.py',
    'telemetry/journal_query.py', 'telemetry/schema.py',
    'telemetry/defects.py', 'telemetry/undo_evidence.py',
    'telemetry/cw_replay_reader.py', 'telemetry/cw_match_recorder.py',
    'telemetry/cw_win_features.py', 'telemetry/cw_win_model.py',
    'telemetry/cw_divergence_stats.py', 'telemetry/version_stamp.py',
    'telemetry/op_journal.py', 'sim/ledger_hooks.py',
    'kernel/cw_telemetry_exit.py', 'kernel/cw_anchor.py',
    'strategies/impl/mandate_v1/encounter.py',
    # sim 批账本/语料/离线检查面:批目录同名 jsonl = 独立语料写入
    # (sim runner 自有账本,非 live 旧流),迁移归 M4(sim runner 经统一
    # 写入口落 journal);本锁辖 live 流程侧写入端。
    'sim/runner.py', 'sim/pool.py', 'sim/cw_delta_pool_gen.py',
    'sim/cw_replay.py', 'sim/cw_sim_invest.py', 'sim/checks/ledger.py',
    'sim/checks/pool.py', 'data/cw_delta_pool_data.py',
    'tools/cw_node_validate.py',
})

#: 生产树扫描正则:退役 writer 调用残留。
_CALL_SITE_RE: re.Pattern = re.compile(
    r'record_(?:decision|outcome|run_summary|exec_event|exogenous'
    r'|event_choice|sell_income|modality_gold|spend_unit|invest_cards'
    r'|shop_snapshot)\b')
#: 生产树扫描正则:旧流文件名字面量(写入面残留)。
_STREAM_NAME_RE: re.Pattern = re.compile(
    r'(?:decisions|outcomes|exogenous|spend_ledger|shop_snapshots'
    r'|exec_events|invest_cards|obs_conflicts|runs)\.jsonl')

_SRC_ROOT: Path = (Path(__file__).resolve().parents[5] / 'src' / 'sr_od'
                   / 'application' / 'currency_war')


@pytest.fixture()
def _retire_isolation():
    """run 态/recorder 根槽/journal 槽三面隔离(模块槽进程全局,teardown 复位)。"""
    tel_state.reset_run_state()
    yield
    tel_state.reset_run_state()
    tel_state.set_recorder_replay_dir(None)
    cw_state_journal.reset_state_telemetry()
    cw_telemetry_exit_reset_obs_provider()


def cw_telemetry_exit_reset_obs_provider() -> None:
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    cw_telemetry_exit.set_obs_event_board_provider(None)


# ============================================================ 结构删净锁


def test_retired_writer_symbols_absent_from_recorder() -> None:
    """9 流 writer 符号自 recorder 模块/类面删除(删代码非停写)。"""
    from sr_od.application.currency_war.telemetry import recorder
    for sym in _RETIRED_RECORDER_SYMBOLS:
        assert not hasattr(recorder, sym), \
            f'recorder.{sym} 应已随退役删除(防半删)'
    for m in _RETIRED_RECORDER_METHODS:
        assert not hasattr(recorder.TelemetryRecorder, m), \
            f'TelemetryRecorder.{m} 应已随退役删除(防半删)'
    # 保留面在位:缺陷台账(保留专用流)写入与 sim 共用 expected 快照 helper。
    assert hasattr(recorder.TelemetryRecorder, 'record_defect')
    assert hasattr(recorder, 'snapshot_expected_paths')


def test_no_retired_writer_call_sites_in_production_tree() -> None:
    """src 生产树无退役 writer 调用点/旧流文件名残留(只读豁免面除外)。"""
    violations: list[str] = []
    for py in sorted(_SRC_ROOT.rglob('*.py')):
        rel = py.relative_to(_SRC_ROOT).as_posix()
        if rel in _READ_FACE_WHITELIST:
            continue
        text = py.read_text(encoding='utf-8')
        for i, line in enumerate(text.splitlines(), 1):
            if _CALL_SITE_RE.search(line):
                violations.append(f'{rel}:{i} 调用残留: {line.strip()[:120]}')
            elif _STREAM_NAME_RE.search(line):
                violations.append(f'{rel}:{i} 流名残留: {line.strip()[:120]}')
    assert violations == [], '旧流写入面残留(防半删):\n' + '\n'.join(violations)


# ============================================================ 行为零产出 + journal 照常锁


def test_simulated_flow_zero_old_stream_output_and_journal_produces(
        tmp_path) -> None:
    """模拟流(run 生命周期+BoardState 写入+obs_conflict 收编+run 收口)后:
    旧 9 流文件零新增;journal 照常产出(write+obs_event,归属一致)。"""
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    from sr_od.application.currency_war.kernel.cw_board_state import (
        BS_SCHEMA_VERSION,
        BoardState,
    )

    tel_state.set_recorder_replay_dir(tmp_path)
    journal = cw_state_journal.install_state_telemetry(
        tmp_path / 'state' / 'journal.jsonl', flush_every=1,
        run_id_provider=tel_state.current_run_id)
    # 收编制 provider(生产在 app 装配段注册;测试同形接通)
    match = SimpleNamespace(session=SimpleNamespace())
    cw_telemetry_exit.set_obs_event_board_provider(
        lambda: board_state_of(match.session))
    rid = tel_state.ensure_run_started(match, 'mandate_v1')
    assert rid, 'run 生命周期照常(run_id 供给 journal 归属)'
    # BoardState 照常写入(journal write 行)
    bs = board_state_of(match.session)
    assert isinstance(bs, BoardState)
    bs.schema_version = BS_SCHEMA_VERSION
    bs.observe(bs.gold, 20, sig=_sig())
    # obs_conflict 收编面:证据进 journal 行型 2,旧流零写入
    obs_conflict('gold', 20, 21, verdict='锁面', source='retire_lock')
    # run 收口(收口位;runs 流零写入)
    tel_state.close_run(result='stopped', plane_reached=1,
                        rounds_survived=1, final_hp=10)
    journal.flush()
    for name in _OLD_STREAM_FILES:
        assert not (tmp_path / name).exists(), \
            f'旧流 {name} 不得新增(写入端已退役,模拟流零产出)'
    jpath = tmp_path / 'state' / 'journal.jsonl'
    rows = [json.loads(line) for line in
            jpath.read_text(encoding='utf-8').splitlines() if line.strip()]
    kinds = {r.get('row') for r in rows}
    assert {'write', 'obs_event'} <= kinds, \
        f'journal 照常产出(write+obs_event),实得 {kinds}'
    assert all(r.get('run_id') == rid for r in rows), 'journal 行归属一致'
    ev = [r for r in rows if r.get('row') == 'obs_event'][-1]
    assert ev['field'] == 'gold' and ev['verdict'] == '锁面', \
        'obs_event 行携带原 obs_conflict 证据语义'


# ============================================================ journal 无条件常开锁


def test_state_journal_flag_abolished_and_assembly_unconditional() -> None:
    """state_journal 影子开关销案:config 面无字段;app 装配段无条件武装
    并注册 obs_event 收编制 provider(无 flag 分支)。"""
    cfg_src = Path(cw_cfg_mod.__file__).read_text(encoding='utf-8')
    assert 'state_journal' not in cfg_src, \
        'state_journal 开关应已随直迁裁定销案(无影子开关)'
    app_src = Path(cw_app_mod.__file__).read_text(encoding='utf-8')
    assert 'install_state_telemetry' in app_src, '装配段保留 journal 武装'
    assert '.state_journal' not in app_src, '装配段不得再有开关分支'
    assert 'set_obs_event_board_provider' in app_src, \
        '装配段注册 obs_event 收编制 provider'
