"""W3 锁:journal 唯一账读面(判读/哨兵/运行时切新账 + 删旧读面)。

正本 = docs/develop/currency_war/game_state/r5-migration-plan.md §2 W3
(验证判据:旧读面零引用 grep 锁 / 旧档案 v11+ 装配回归锁(缺流键容忍)/
在线收口接线 / 安灯 receipts 读面 / 寿命契约段粒度清理)。

前置波:W1 常开化(d873ff90f)、W2 局终域(8294d0bdb)、删除波 1(9 流写入端
退役,3d4461438)。
"""
from __future__ import annotations

import json
from pathlib import Path

from sr_od.application.currency_war.kernel.cw_state_journal import (
    JOURNAL_RETENTION_DAYS,
    enforce_journal_retention,
)
from sr_od.application.currency_war.telemetry import cli as _cli
from sr_od.application.currency_war.telemetry import match_archive as arch
from sr_od.application.currency_war.telemetry import query as q
from sr_od.application.currency_war.telemetry.journal_query import (
    read_journal_stats,
)

# ============================================================ ① 旧读面零引用 grep 锁

#: 生产读面旧流文件名封闭集(收编 9 流;保留流 op_journal/cw4_counters/
#: defect_ledger/board_state_archive 与 sim 自写账本同名文件不在集内)。
_W3_RETIRED_STREAM_FILES: tuple[str, ...] = (
    'decisions.jsonl', 'outcomes.jsonl', 'exogenous.jsonl',
    'spend_ledger.jsonl', 'shop_snapshots.jsonl', 'exec_events.jsonl',
    'invest_cards.jsonl', 'obs_conflicts.jsonl', 'runs.jsonl',
)

#: 豁免面(书面申报,零读语义):
#: - telemetry/schema.py:旧流行 schema 类(docstring/字段注释;sim 自写
#:   账本同 schema,归 W6 sim 切统一容器批统一处置);
#: - telemetry/recorder.py / telemetry/state.py / sim/ledger_hooks.py /
#:   run_state.py / cw_loop.py / cw_screen_prep.py / sim 侧:墓碑注释与
#:   退役申报文本(历史指向,非活读);
#: - sim/cw_delta_pool_gen.py / sim/pool.py / data/cw_delta_pool_data.py:
#:   Δ池语料面(读 sim 侧重建格式,语料源切 journal 归 W6);
#: - sim/engine_p1.py / sim/cw_replay.py / sim/runner.py / sim/cw_sim_invest.py:
#:   sim 引擎自写账本(活写活读,W6 切统一容器);
#: - telemetry/cw_replay_reader.py / cw_divergence_stats.py / tools/:
#:   存量语料只读考古面(候裁 6,retirement.md §7-#7 口径)。
_W3_GREP_WHITELIST_FILES: frozenset[str] = frozenset({
    'schema.py', 'recorder.py', 'state.py', 'ledger_hooks.py',
    'run_state.py', 'cw_loop.py', 'cw_screen_prep.py',
    'cw_delta_pool_gen.py', 'pool.py', 'cw_delta_pool_data.py',
    'engine_p1.py', 'cw_replay.py', 'runner.py', 'cw_sim_invest.py',
    'cw_replay_reader.py', 'cw_divergence_stats.py', 'cw_node_validate.py',
    'cw_telemetry_exit.py', 'cli.py',
})


def _iter_cw_py() -> list[Path]:
    root = (Path(__file__).resolve().parents[4] / 'src'
            / 'sr_od' / 'application' / 'currency_war')
    return sorted(p for p in root.rglob('*.py') if p.name != '__init__.py')


def test_w3_retired_stream_zero_live_read_face() -> None:
    """生产读面旧流文件名零活引用(删除面 = 判读 CLI/journal 之外的读口)。

    判据:命中文件 ∈ 豁免清单(墓碑注释/schema 类/sim 活账本/考古面,
    逐项书面申报);豁免清单外的命中 = 旧读面复活,红。
    query.py 在豁免清单外——它只余纯函数单一源,不得出现旧流文件名。
    """
    bad: list[str] = []
    for p in _iter_cw_py():
        if p.name in _W3_GREP_WHITELIST_FILES:
            continue
        text = p.read_text(encoding='utf-8', errors='replace')
        for stream in _W3_RETIRED_STREAM_FILES:
            if stream in text:
                bad.append(f'{p.name}:{stream}')
    assert not bad, f'旧流文件名活引用(零引用 grep 锁): {bad}'


def test_w3_query_module_is_pure_function_layer() -> None:
    """query.py 收缩为纯函数单一源:旧视图族/旧流 helper 封闭删除。"""
    deleted = ('query_rounds', 'query_supply', 'query_anomalies', 'query_hp',
               'query_economy', 'query_gold_flow', 'query_tiers',
               'query_plan_vs_exec', 'query_spend_ledger', 'query_exogenous',
               'query_exec_events', 'query_invest_cards',
               'query_obs_conflicts', '_shop_plan_rows', '_spend_unit_row',
               '_read_conflict_gold_delta', 'resolve_unit_gold_close',
               'check_strategy_live_streak', 'strategy_round_live',
               '_list_runs', '_load_decisions_rounds')
    kept = ('read_jsonl', 'HP_CONF_TRUSTED', '_outcome_hp_trusted',
            'plan_gold_flow', 'classify_spend_unit')
    for name in deleted:
        assert not hasattr(q, name), f'{name} 应已随 W3 删除(防复活)'
    for name in kept:
        assert hasattr(q, name), f'{name} 纯函数单一源缺失(活消费方断供)'


def test_w3_cli_has_single_journal_source() -> None:
    """--source 双读面拆除:journal 为 query 唯一读面;checks 子命令退役。"""
    assert not hasattr(_cli, '_journal_source'), \
        '双读面分发器应已折叠为唯一读面'
    assert hasattr(_cli, '_query_source'), '唯一读面入口在'
    assert frozenset(
        {'rounds', 'gold', 'hp', 'events', 'snapshot', 'final', 'all'}) == _cli._JOURNAL_VIEWS
    import inspect
    src = inspect.getsource(_cli._cli_main)
    assert "--source" not in src, '--source 参数应已删除'
    assert "'query', 'assemble'" in src, 'checks 子命令应已退役'


def test_w3_ledger_hooks_is_noop_stub() -> None:
    """ledger_hooks 收缩为 no-op 桩模块:读侧检查族封闭删除。"""
    from sr_od.application.currency_war.sim import ledger_hooks as lh
    for name in ('run_checks_on_replay', 'merge_round_rows',
                 'check_summary_write_path_coverage',
                 'run_production_segment_checks'):
        assert not hasattr(lh, name), f'{name} 应已随 W3 删除'
    assert hasattr(lh, 'recover_dangling_run_summaries'), \
        'no-op 桩保留(防外部残留调用炸栈)'


def test_w3_archive_slice_files_journal_plus_op_journal_only() -> None:
    """_SLICE_FILES 旧流键拆除:切片 = op_journal + 新账两项。"""
    assert arch._SLICE_FILES == ('op_journal.jsonl', 'state/journal.jsonl')


# ============================================================ ② 装配回归锁(缺流键容忍)

def test_w3_assign_games_journals_segments(tmp_path: Path) -> None:
    """归局骨架三源:journal 实机段(唯一活账)可归局;sim/测试段不采信。"""
    jp = tmp_path / 'state' / 'journal.jsonl'
    jp.parent.mkdir(parents=True)
    rows = [
        {'v': 1, 'ts': '2026-09-11T10:00:00', 'run_id': 'run_20260911_100000',
         'row': 'write', 'field': 'node', 'after': {'plane': 1, 'round_num': 1},
         'state': {'values': {'node': {'plane': 1, 'round_num': 1}}},
         'sig': {'family': 'obs', 'actor': 'X', 'mode': 'read'},
         'note': '', 'evidence_refs': []},
        {'v': 2, 'ts': '2026-09-11T10:01:00', 'run_id': 'fake_sim_seg',
         'row': 'write', 'field': 'gold', 'after': 5,
         'state': {'values': {}}, 'sig': {'family': 'obs', 'actor': 'X',
                                          'mode': 'read'},
         'note': '', 'evidence_refs': []},
        {'v': 3, 'ts': '2026-09-11T11:00:00', 'run_id': 'run_20260911_110000',
         'row': 'write', 'field': 'node', 'after': {'plane': 1, 'round_num': 1},
         'state': {'values': {'node': {'plane': 1, 'round_num': 1}}},
         'sig': {'family': 'obs', 'actor': 'X', 'mode': 'read'},
         'note': '', 'evidence_refs': []},
    ]
    with jp.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    games = arch.assign_games(tmp_path)
    segs = [s for g in games for s in g['segments']]
    assert 'run_20260911_100000' in segs and 'run_20260911_110000' in segs, \
        'journal 实机段应入归局骨架'
    assert 'fake_sim_seg' not in segs, 'sim/测试段形态不采信(_JOURNAL_RUN_ID_RE)'


def test_w3_build_archive_tolerates_missing_retired_streams(tmp_path: Path) -> None:
    """缺流键容忍(宽容契约既有):旧流全缺 + 仅 journal 的目录装配不炸,
    rounds 面宽容退化空(深判读候 journal 侧重建,W3 申报)。"""
    jp = tmp_path / 'state' / 'journal.jsonl'
    jp.parent.mkdir(parents=True)
    jp.write_text(json.dumps({
        'v': 1, 'ts': '2026-09-11T10:00:00', 'run_id': 'run_20260911_100000',
        'row': 'write', 'field': 'node', 'after': {'plane': 1, 'round_num': 1},
        'state': {'values': {'node': {'plane': 1, 'round_num': 1},
                             'hp': 70, 'gold': 30}},
        'sig': {'family': 'obs', 'actor': 'X', 'mode': 'read'},
        'note': '', 'evidence_refs': []}, ensure_ascii=False) + '\n',
        encoding='utf-8')
    games = arch.assign_games(tmp_path)
    assert games and games[0]['segments'] == ['run_20260911_100000']
    a = arch.build_archive(tmp_path, games[0])
    assert a['rounds'] == [], '旧流切片拆除后 rounds 宽容退化(申报面)'
    assert a['segments'][0]['run_id'] == 'run_20260911_100000'


# ============================================================ ③ 在线收口接线

def test_w3_online_match_final_wiring_exists() -> None:
    """cw_loop 在线收口两点接 match_final 写口(W2 落地审 §⑤ 遗留义务;
    哨兵 runs 断流探测的唯一收口证据源——不接线则实机永落 match_final,
    哨兵 RUNS-GAP 误报)。"""
    import inspect

    from sr_od.application.currency_war.operations import cw_loop
    loop_src = inspect.getsource(cw_loop)
    assert 'resolve_final_type' in loop_src and 'write_match_final' in loop_src
    # 两收口点接线:3c 回大厅(note=online:lobby_return)+ W75 兜底(
    # online:w75_stopped/abandoned)
    assert "note='online:lobby_return'" in loop_src
    assert "note=('online:w75_stopped'" in loop_src


def test_w3_resolve_final_type_judgment_order() -> None:
    """在线判定面判定序锁(停止>败局>plane==3 精确值>开局失败 None>abnormal;
    与收口语义同源,假 win 守卫同口径)。"""
    from sr_od.application.currency_war.obs.cw_observation import (
        resolve_final_type,
    )
    assert resolve_final_type(stop_requested=True, saw_defeat=False,
                              plane_reached=3) == 'stopped'
    assert resolve_final_type(stop_requested=False, saw_defeat=True,
                              plane_reached=1) == 'loss'
    assert resolve_final_type(stop_requested=False, saw_defeat=False,
                              plane_reached=3) == 'win'
    assert resolve_final_type(stop_requested=False, saw_defeat=False,
                              plane_reached=2, rounds_played=True) == 'abnormal'
    assert resolve_final_type(stop_requested=False, saw_defeat=False,
                              plane_reached=1, rounds_played=False) is None


def test_w3_write_match_final_idempotent() -> None:
    """写前查重 G12(终局防重挂局终域行):同段二写 no-op 返 False。"""
    from sr_od.application.currency_war.kernel.cw_board_state import (
        BS_SCHEMA_VERSION,
        BoardState,
        write_match_final,
    )
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert write_match_final(bs, final_type='loss', plane=1) is True
    assert write_match_final(bs, final_type='loss', plane=1) is False


# ============================================================ ④ 安灯 receipts 读面(T-255)

def test_w3_andon_reads_outcome_facts_not_files(monkeypatch, tmp_path) -> None:
    """安灯执行事实改内存直读 BuyCardsOutcome:旧三流文件读面零调用
    (spend_ledger/decisions/obs_conflicts 读数缺失 → facts 缺席不判)。
    判定链单一源 = classify_spend_unit(W494 语义;边界豁免防误停保留)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        CwScreenPrep,
    )
    prep = CwScreenPrep.__new__(CwScreenPrep)
    prep._unit_facts = None
    prep._unit_meta = {'seq': 1, 'plane': 1, 'round': 1}
    prep._exec_fail_hook_fired = False
    # facts 缺席 → 不判(不读任何文件,不炸)
    prep._exec_fail_hook_check(prep._unit_meta, 'closed')
    assert prep._exec_fail_hook_fired is False
    # BuyCardsOutcome 一手事实:发射了花费动作但金没动 → not_effective 停机;
    # plan_truncated 豁免(ADR-0456 防误停)结构性保留
    from types import SimpleNamespace

    from sr_od.application.currency_war.kernel.cw_state import BuyCard, ShopCard
    outcome = SimpleNamespace(
        visit_actions=[BuyCard(card=ShopCard(x=0, name='某卡', cost=3))],
        gold_open=30, plan_truncated=False, refresh_attempted=False,
        refresh_board_changed=None)
    monkeypatch.setattr(
        'sr_od.application.currency_war.telemetry.state.current_run_id',
        lambda: 'run_w3_andon')
    prep._unit_facts = {'outcome': outcome, 'gold_close': 30}
    fired: list[str] = []
    monkeypatch.setattr(
        'sr_od.application.currency_war.run_state.write_exec_fail_flag',
        lambda path, **kw: fired.append(kw) or 'flag')
    monkeypatch.setattr(CwScreenPrep, 'save_screenshot', lambda self, prefix: None)
    class _RC:
        def __init__(self) -> None:
            self.stopped = None
        def stop_running(self, reason: str) -> None:
            self.stopped = reason
    rc = _RC()
    prep.ctx = SimpleNamespace(run_context=rc)
    prep._exec_fail_hook_check(prep._unit_meta, 'closed')
    assert rc.stopped == 'hook:exec_fail_mismatch', \
        '发射了花费动作+金差≈0 = not_effective(安灯不停 = 判据断线)'
    # 截断豁免:同形态 + plan_truncated → 不停
    outcome2 = SimpleNamespace(
        visit_actions=[], gold_open=30, plan_truncated=True,
        refresh_attempted=False, refresh_board_changed=None)
    prep._exec_fail_hook_fired = False
    prep._unit_facts = {'outcome': outcome2, 'gold_close': 30}
    rc2 = _RC()
    prep.ctx = SimpleNamespace(run_context=rc2)
    prep._exec_fail_hook_check(prep._unit_meta, 'closed')
    assert rc2.stopped is None, 'plan_truncated 豁免失效 = 误停回归'


def test_w3_outcome_exports_visit_actions() -> None:
    """BuyCardsOutcome 一手执行事实导出(visit_actions 字段在;索引定义
    注释在场 = 单一判据来源)。"""
    import dataclasses

    from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
        BuyCardsOutcome,
    )
    names = {f.name for f in dataclasses.fields(BuyCardsOutcome)}
    assert 'visit_actions' in names
    assert 'spend_executed' in names and 'plan_truncated' in names
    src = inspect_source(BuyCardsOutcome)
    assert '发射序' in src, 'visit_actions 索引坐标系定义注释在场'


def inspect_source(obj) -> str:
    import inspect
    return inspect.getsource(obj)


# ============================================================ ⑤ 寿命契约(R5 W3 装配端)

def _mk_journal(tmp_path: Path, segs: list[tuple[str, str, int]]) -> Path:
    jp = tmp_path / 'state' / 'journal.jsonl'
    jp.parent.mkdir(parents=True, exist_ok=True)
    with jp.open('w', encoding='utf-8') as f:
        for rid, ts, n in segs:
            for i in range(n):
                f.write(json.dumps({
                    'v': i + 1, 'ts': ts, 'run_id': rid, 'row': 'write',
                    'field': 'gold', 'after': 1, 'state': {},
                    'sig': {'family': 'obs', 'actor': 'X', 'mode': 'read'},
                    'note': '', 'evidence_refs': []}, ensure_ascii=False)
                    + '\n')
    return jp


def test_w3_retention_segment_granularity(tmp_path: Path) -> None:
    """滚动清理以 run 段为整体单元:过期段整段淘汰,窗口内段与活跃段保留;
    坏行原样保留(宽容契约,清理面不判定);幂等二跑零增量。"""
    from datetime import datetime, timedelta
    now = datetime.now()
    jp = _mk_journal(tmp_path, [
        ('run_old', (now - timedelta(days=60)).isoformat(timespec='seconds'), 3),
        ('run_mid', (now - timedelta(days=10)).isoformat(timespec='seconds'), 2),
        ('run_new', (now - timedelta(days=1)).isoformat(timespec='seconds'), 1),
    ])
    with jp.open('a', encoding='utf-8') as f:
        f.write('{bad half line\n')
    r1 = enforce_journal_retention(jp, now=now)
    assert r1 == {'checked': 3, 'retired': ['run_old'], 'rows_dropped': 3}
    kept_rows = [json.loads(ln) for ln in
                 jp.read_text(encoding='utf-8').strip().splitlines()
                 if not ln.startswith('{bad')]
    assert {r['run_id'] for r in kept_rows} == {'run_mid', 'run_new'}
    assert 'version' not in kept_rows[0]   # 段内版本序完整(整段淘汰不切半段)
    r2 = enforce_journal_retention(jp, now=now)
    assert r2['retired'] == [], '幂等:二跑零增量'


def test_w3_retention_manifest_archived_out(tmp_path: Path) -> None:
    """archived_out 显影:被淘汰段逐段一行 manifest(判读者钉解析失败时
    辨「清理 vs 丢数据」;journal 同目录)。"""
    from datetime import datetime, timedelta

    from sr_od.application.currency_war.kernel.cw_state_journal import (
        RETIREMENT_MANIFEST_NAME,
    )
    now = datetime.now()
    jp = _mk_journal(tmp_path, [
        ('run_gone', (now - timedelta(days=90)).isoformat(timespec='seconds'), 2),
        ('run_keep', (now - timedelta(days=1)).isoformat(timespec='seconds'), 1),
    ])
    enforce_journal_retention(jp, now=now)
    man = [json.loads(ln) for ln in
           (tmp_path / 'state' / RETIREMENT_MANIFEST_NAME)
           .read_text(encoding='utf-8').strip().splitlines()]
    assert len(man) == 1
    assert man[0]['run_id'] == 'run_gone' and man[0]['archived_out'] is True
    assert man[0]['rows'] == 2 and man[0]['last_ts'].startswith(
        (now - timedelta(days=90)).strftime('%Y-%m-%dT'))


def test_w3_retention_active_segment_never_cleaned(tmp_path: Path) -> None:
    """活跃段(段末行最新)永不清理:400 天后仍保留(可能与进程内缓冲/
    下一局续写交叠)。"""
    from datetime import datetime, timedelta
    now = datetime.now()
    jp = _mk_journal(tmp_path, [
        ('run_a', (now - timedelta(days=400)).isoformat(timespec='seconds'), 2),
        ('run_b', (now - timedelta(days=400)).isoformat(timespec='seconds'), 2),
    ])
    r = enforce_journal_retention(jp, now=now + timedelta(days=400))
    assert r['retired'] == ['run_a'], '活跃段(run_b,段末行最新)被保留'


def test_w3_retention_default_window_constant() -> None:
    """保留窗 = 跨期语料窗(缺省常量;清理策略随真实数据积累定,无观察窗
    计时——直迁口径,r5-migration-plan.md §4-5)。"""
    assert JOURNAL_RETENTION_DAYS == 30


def test_w3_retention_missing_file_noop(tmp_path: Path) -> None:
    """journal 缺席 = 零清理不炸(诚实缺失,装配面不受清理面波及)。"""
    r = enforce_journal_retention(tmp_path / 'nope' / 'journal.jsonl')
    assert r == {'checked': 0, 'retired': [], 'rows_dropped': 0}


# ============================================================ ⑥ journal 宽容读回归

def test_w3_journal_read_tolerates_truncated_tail(tmp_path: Path) -> None:
    """宽容消费契约(装配器同源 read_journal_stats):半行/坏行逐行跳过,
    合法行照读(同流两读法两契约曾致装配端崩,R3.1 落地审 F1)。"""
    jp = tmp_path / 'state' / 'journal.jsonl'
    jp.parent.mkdir(parents=True)
    jp.write_text(
        json.dumps({'v': 1, 'ts': '2026-09-11T10:00:00',
                    'run_id': 'run_x', 'row': 'write', 'field': 'gold',
                    'after': 1, 'state': {},
                    'sig': {'family': 'obs', 'actor': 'X', 'mode': 'read'},
                    'note': '', 'evidence_refs': []}, ensure_ascii=False)
        + '\n{"v": 2, "ts": "2026-09-11T10:0',   # 物理截断尾(合法形态)
        encoding='utf-8')
    rows, stats = read_journal_stats(tmp_path)
    assert len(rows) == 1 and stats.total_skipped >= 1
