"""统一 state 账本判读读面锁(R3-1 消费方迁移第一批·离线工具族)。

设计正本 = ``.debug/temp/currency_war/流程侧遥测-设计v3.3.md`` §3.3/§3.6.2
(判读 CLI 行:新视图族按行读 + 行间差分、零重放;档案行:装配器 v12+ 切片
含 journal;并存期旧视图只读保留至 M5)。锁面四组 =
- 新读能力锁:自足快照行(fixture 构造,与写端 kernel/cw_board_state
  ``_swap``/``note_obs_event`` 行键同形)→ 读回断言(读/清单/取值口/视图);
- 宽容性锁:缺细节字段行、坏 JSON 行、非 dict 行、缺文件——不炸、给显式
  「缺失」形态(宽容读取契约,见 telemetry/journal_query 模块 docstring);
- 档案切片锁:state/journal.jsonl 入切片(v12 装配器),按 run 过滤、物化
  还原相对路径、旧档案版本检查自动重装配补键;
- CLI 读面锁:--source journal 视图族/--recent 概览/--match 切片读/配对
  校验拒绝/缺账提示。

测试隔离:全部输入 = tmp_path 合成行,零真实 .debug 触碰;不装影子面
(kernel 写端零调用),本文件只测读面。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from sr_od.application.currency_war.telemetry import cli as tel_cli
from sr_od.application.currency_war.telemetry import journal_query as jq
from sr_od.application.currency_war.telemetry import match_archive as arch

# ============================================================ 行夹具
# 行键面 = 写端 _swap/note_obs_event 落盘形态(test_cw_state_journal 锁过的
# 行 schema);此处手工构造,读面测试不依赖 kernel 写端。


def _vals(**kw) -> dict:
    """快照 values 面快捷构造(node 用三键 NodeKey 序列化形态)。"""
    return kw


def _node(plane: int, rnd: int, kind: str = 'prep') -> dict:
    return {'plane': plane, 'round_num': rnd, 'kind': kind}


def _wrow(v: int, ts: str, run_id: str, field: str = 'gold', after=None,
          values: dict | None = None) -> dict:
    """行型 1(write)。values=None 时不注入快照 values 面 = 走 after 回退形态。"""
    return {'v': v, 'ts': ts, 'run_id': run_id, 'row': 'write',
            'field': field, 'after': after, 'same_value': False,
            'state': {'schema_version': 1, 'values': values or {}, 'prov': {},
                      'pending_expected': [], 'effects': [],
                      'frame_obs': 'full', 'write_seq': v,
                      'node_hist_ord': None, 'bs_schema': {}},
            'sig': {'family': 'obs', 'actor': 'cw_observation', 'screen': None,
                    'mode': 'read', 'quality': {}, 'group_id': None},
            'note': '', 'evidence_refs': []}


def _erow(v: int, ts: str, run_id: str, event: str, field: str,
          observed, verdict: str = '') -> dict:
    """行型 2(obs_event;写端不落 after/same_value 键,行键面同形)。"""
    row = _wrow(v, ts, run_id)
    for k in ('after', 'same_value'):
        row.pop(k)
    row.update({'row': 'obs_event', 'event': event, 'field': field,
                'observed': observed, 'verdict': verdict, 'obs_phase': 'prep'})
    return row


def _write_journal(rd: Path, rows: list[dict]) -> None:
    p = rd / 'state' / 'journal.jsonl'
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def _write_jsonl(rd: Path, name: str, rows: list[dict]) -> None:
    rd.mkdir(parents=True, exist_ok=True)
    with (rd / name).open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


# ============================================================ 新读能力锁


def test_read_journal_self_contained_roundtrip(tmp_path: Path) -> None:
    """自足行写盘 → 读回:行序保文件序(= 版本序),run 清单首现序,
    核心取值口(v/ts/row/sig/state)逐位可读。"""
    rows = [
        _wrow(1, '2026-08-30T09:48:20', 'run_a', 'gold', 40,
              _vals(gold=40, node=_node(1, 1))),
        _wrow(2, '2026-08-30T09:49:10', 'run_a', 'gold', 41,
              _vals(gold=41, node=_node(1, 1))),
        _wrow(1, '2026-08-30T10:00:00', 'run_b', 'hp', 60,
              _vals(hp=60)),
    ]
    _write_journal(tmp_path, rows)
    got = jq.read_journal(tmp_path)
    assert [r['v'] for r in got] == [1, 2, 1], '跨 run 各段版本各自连续'
    assert jq.journal_runs(got) == ['run_a', 'run_b'], 'run 清单 = 行首现序'
    assert [r['v'] for r in jq.rows_of(got, 'run_a')] == [1, 2]
    r = got[0]
    assert (jq.row_v(r), jq.row_ts(r), jq.row_kind(r)) == \
        (1, '2026-08-30T09:48:20', 'write')
    assert jq.row_sig(r)['actor'] == 'cw_observation'
    assert jq.state_values(r)['gold'] == 40
    assert jq.node_key_of(r) == (1, 1)
    assert jq.node_ordinal_of(r) == 1, 'ord = (plane-1)*9+round(基 1)'


def test_field_value_snapshot_first_with_after_fallback() -> None:
    """取值口:快照 values 优先(两行型统一);快照缺字段回退 write 行
    after(裁剪行形态);两处皆缺 = (False, None) 不猜。"""
    full = _wrow(1, 't1', 'r', 'gold', 40, _vals(gold=40))
    assert jq.field_value(full, 'gold') == (True, 40)
    trimmed = _wrow(2, 't2', 'r', 'gold', 25, values=None)
    trimmed['state'] = {}   # 快照面被裁剪
    assert jq.field_value(trimmed, 'gold') == (True, 25), '回退 after'
    bare = {'v': 1, 'ts': 't', 'run_id': 'r'}
    assert jq.field_value(bare, 'gold') == (False, None)
    # after=None 是合法正式值(leave_screen 离屏清空写 None):快照 values
    # 不收 None 字段 → 走 after 回退,(True, None)=「有值且为 None」,
    # 与「字段缺失」(False, None) 分辨——判读可区分离屏与未写入。
    off = _wrow(3, 't3', 'r', 'shop', None, values={})
    assert jq.field_value(off, 'shop') == (True, None)
    # obs_event 行的 field 指观察对象且无 after 键——不误回退
    ev = _erow(2, 't', 'r', 'arbitrate', 'gold', {'old': 1, 'new': 2})
    assert jq.field_value(ev, 'gold') == (False, None)


def test_gold_hp_chain_diff_and_run_boundary(tmp_path: Path) -> None:
    """金/hp 链 = 行间差分:只列变化行;跨 run 段界链重开(不跨段算 Δ)。"""
    rows = [
        _wrow(1, 't1', 'run_a', 'gold', 40, _vals(gold=40)),
        _wrow(2, 't2', 'run_a', 'gold', 41, _vals(gold=41)),
        _wrow(3, 't3', 'run_a', 'gold', 41, _vals(gold=41)),   # same_value 重读
        _wrow(4, 't4', 'run_a', 'hp', 60, _vals(gold=41, hp=60)),
        _wrow(5, 't5', 'run_a', 'hp', 52, _vals(gold=41, hp=52)),
        _wrow(1, 'u1', 'run_b', 'gold', 90, _vals(gold=90)),
    ]
    gold = jq.view_gold(rows, 'run_a')
    assert 'gold=40 (首值)' in gold[1]
    assert '40→41 (Δ+1)' in gold[2]
    assert len(gold) == 3, '同值重读行不出链'
    hp = jq.view_hp(rows, 'run_a')
    assert 'hp=60 (首值)' in hp[1] and '60→52 (Δ-8)' in hp[2]
    cross = jq.view_gold(rows)   # 不滤 run:段界处重开
    assert any('gold=90 (首值)' in ln for ln in cross), \
        'run_b 首行按首值显影,禁与 run_a 末值连线算 Δ'


def test_view_rounds_segments_by_node_key() -> None:
    """逐轮表按节点分段:段界 = 快照 node 键;段内 hp/gold 首末差分;
    node 缺行归「未定节点段」(开局链,不猜节点身份)。"""
    rows = [
        _wrow(1, 't1', 'r', 'gold', 20, _vals(gold=20)),
        _wrow(2, 't2', 'r', 'node', _node(1, 1),
              _vals(gold=20, hp=60, node=_node(1, 1))),
        _wrow(3, 't3', 'r', 'gold', 26, _vals(gold=26, hp=60,
                                              node=_node(1, 1))),
        _wrow(4, 't4', 'r', 'hp', 52, _vals(gold=26, hp=52,
                                            node=_node(1, 2))),
    ]
    lines = jq.view_rounds(rows, 'r')
    assert lines[0].startswith('[逐轮表]')
    assert any('未定节点段' in ln and '行=1' in ln for ln in lines)
    seg1 = next(ln for ln in lines if ln.strip().startswith('P1r1'))
    assert '行=2' in seg1 and 'hp 60' in seg1 and 'gold 20→26' in seg1
    seg2 = next(ln for ln in lines if ln.strip().startswith('P1r2'))
    assert '行=1' in seg2 and 'hp 52' in seg2 and 'kind=prep' in seg2


def test_view_events_and_snapshot() -> None:
    """行型 2 显影(obs_event 列表,write 行不入)+ 末行快照摘要;
    obs_event 行内嵌当时完整 state(写端语义),末行快照按行内快照直读。"""
    carried = _vals(gold=40, hp=100, level=3, node=_node(1, 1))
    rows = [
        _wrow(1, 't1', 'r', 'gold', 40, carried),
        _erow(2, 't2', 'r', 'arbitrate', 'level', {'old': 3, 'new': 213},
              verdict='保旧-单调守卫'),
        _erow(3, 't3', 'r', 'miss', 'shop', None),   # observed 键在场值 None
    ]
    # 行型 2 行内嵌当时 state(与写端 note_obs_event 同形)
    rows[1]['state']['values'] = dict(carried)
    rows[2]['state']['values'] = dict(carried)
    ev = jq.view_events(rows, 'r')
    assert len(ev) == 3, '头行 + 两条 obs_event(write 行不入)'
    assert 'event=arbitrate' in ev[1] and 'observed={"old": 3, "new": 213}' in ev[1]
    assert 'verdict=保旧-单调守卫' in ev[1]
    assert 'observed=null' in ev[2], 'observed 键在场值 None = null 显影' \
        '(键缺位的「(缺)」显影归截断行锁)'
    snap = jq.view_snapshot(rows, 'r')
    assert 'hp=100' in snap[1] and 'gold=40' in snap[1] and 'level=3' in snap[1]
    assert 'P1r1(prep)' in snap[1]
    assert jq.view_snapshot([], 'r')[-1] == '  (无行)'


# ============================================================ 宽容性锁


def test_lenient_missing_file_and_bad_lines(tmp_path: Path) -> None:
    """宽容契约:文件缺 = [];坏 JSON 行/非 dict 行/空行跳过,好行照读。"""
    assert jq.read_journal(tmp_path / 'nope') == []
    p = tmp_path / 'state' / 'journal.jsonl'
    p.parent.mkdir(parents=True)
    good = _wrow(1, 't1', 'r', 'gold', 40, _vals(gold=40))
    with p.open('w', encoding='utf-8') as f:
        f.write('{"v": 1, "ts": "截断行...\n')          # 崩溃截断尾形态
        f.write('\n')
        f.write('not-json-at-all\n')
        f.write('[1, 2, 3]\n')                            # 合法 JSON 非 dict
        f.write('"just a string"\n')
        f.write(json.dumps(good, ensure_ascii=False) + '\n')
    got = jq.read_journal(tmp_path)
    assert got == [good]


def test_views_tolerate_severely_truncated_rows() -> None:
    """只剩核心字段的行(run_id/row)过全视图:不炸,给显式缺失形态;
    无 run_id 的行按 run 过滤语义排除(过 run 滤网 = 全集视图仍可见)。"""
    rows = [{'run_id': 'r'}, {'run_id': 'r', 'row': 'obs_event'},
            {'run_id': 'other', 'row': 'obs_event', 'event': 'miss'},
            {'run_id': 'r', 'ts': 't', 'v': 1, 'row': 'write'}]
    for view in (jq.view_rounds, jq.view_gold, jq.view_hp,
                 jq.view_events, jq.view_snapshot):
        lines = view(rows, 'r')          # 不抛即过;缺失以 '?'/(缺) 显影
        assert isinstance(lines, list) and lines
    assert any('无 gold 读数行' in ln for ln in jq.view_gold(rows, 'r')), \
        '零读数给显式提示,不静默空表'
    ev = jq.view_events(rows, 'r')
    assert '(缺)' in ev[-1] and 'event=miss' not in ''.join(ev), \
        'run 滤网排除他 run 行;本 run 截断行给显式缺失形态'
    assert any('event=miss' in ln
               for ln in jq.view_events(rows)), '全集视图仍可见他 run 行'


def test_lenient_accessors_on_bare_rows() -> None:
    """取值口对裸行:row_v=None/row_sig={}/state_values={}——缺位显式,不猜。"""
    bare = {'run_id': 'r'}
    assert jq.row_v(bare) is None
    assert jq.row_ts(bare) == ''
    assert jq.row_kind(bare) == ''
    assert jq.row_sig(bare) == {}
    assert jq.state_values(bare) == {}
    assert jq.node_key_of(bare) is None
    assert jq.node_ordinal_of(bare) is None


# ============================================================ 档案切片锁


def _dec(run_id: str, plane: int, rnd: int, ts: str) -> dict:
    return {'schema_version': 1, 'run_id': run_id, 'plane': plane,
            'round_num': rnd, 'ts': ts, 'gold': 10, 'gold_readable': True,
            'hp': 100, 'hp_readable': False, 'strategy_id': 'decision_v2',
            'actions': [], 'state': {}}


def _out(run_id: str, plane: int, rnd: int, ts: str, hp_after: int) -> dict:
    return {'schema_version': 1, 'run_id': run_id, 'plane': plane,
            'round_num': rnd, 'ts': ts, 'node_type': '普通战斗',
            'hp_after': hp_after, 'hp_confidence': 1.0, 'killed': False,
            'board_before': {}, 'bench_count': 0, 'source': ''}


def _mk_replay(rd: Path, journal_rows: list[dict] | None = None) -> str:
    """最小单局 replay 根(段 run_20260830_094811 起于 p1r1)+ 可选新账。"""
    _write_jsonl(rd, 'decisions.jsonl',
                 [_dec('run_20260830_094811', 1, 1, '2026-08-30T09:48:11')])
    _write_jsonl(rd, 'outcomes.jsonl',
                 [_out('run_20260830_094811', 1, 1, '2026-08-30T09:49:00', 60)])
    _write_jsonl(rd, 'runs.jsonl',
                 [{'run_id': 'run_20260830_094811',
                   'ts': '2026-08-30T10:09:38', 'result': 'loss',
                   'plane_reached': 1, 'rounds_survived': 1, 'final_hp': 60,
                   'difficulty': 'A8'}])
    if journal_rows is not None:
        _write_journal(rd, journal_rows)
    return 'g_20260830_094811'


_JOURNAL_ROWS = [
    _wrow(1, '2026-08-30T09:48:20', 'run_20260830_094811', 'gold', 40,
          _vals(gold=40, node=_node(1, 1))),
    _wrow(2, '2026-08-30T09:49:30', 'run_20260830_094811', 'gold', 38,
          _vals(gold=38, hp=60, node=_node(1, 1))),
    _wrow(1, '2026-08-30T23:00:00', 'run_other_game', 'gold', 5,
          _vals(gold=5)),
]


def test_archive_slices_journal_by_run_and_materialize_roundtrip(
        tmp_path: Path) -> None:
    """v12 装配器:state/journal.jsonl 入切片并按 run 过滤(他局行不串档);
    物化按同名相对路径还原,新账读面可直读切片。"""
    rd = tmp_path / 'replay'
    _mk_replay(rd, _JOURNAL_ROWS)
    a = arch.build_archive(rd, arch.assign_games(rd)[0])
    assert a['schema_version'] == arch.SCHEMA_VERSION
    sliced = a['slices']['state/journal.jsonl']
    assert [r['v'] for r in sliced] == [1, 2], '按段 run 过滤,他局行不入'
    tmp_root = tmp_path / 'slice_out'
    arch.materialize_slice(a, tmp_root)
    assert (tmp_root / 'state' / 'journal.jsonl').exists(), \
        '相对路径切片物化(v12 形态,父目录自动建)'
    assert jq.read_journal(tmp_root) == sliced


def test_archive_journal_absent_slice_empty(tmp_path: Path) -> None:
    """影子未开(无新账文件)= 空切片:装配不炸,读侧可区分「未开」与「无行」。"""
    rd = tmp_path / 'replay'
    _mk_replay(rd)
    a = arch.build_archive(rd, arch.assign_games(rd)[0])
    assert a['slices']['state/journal.jsonl'] == []
    tmp_root = tmp_path / 'out'
    arch.materialize_slice(a, tmp_root)
    assert not (tmp_root / 'state' / 'journal.jsonl').exists() or \
        jq.read_journal(tmp_root) == []


def test_v11_archive_auto_rebuild_adds_journal_slice(tmp_path: Path) -> None:
    """旧档案(v11,无新账切片键)经 load_archive 版本检查自动重装配补键,
    原子写回升级到当前版本(版本迁移读端,w943 P2-4 机制沿用)。"""
    rd = tmp_path / 'replay'
    game_id = _mk_replay(rd, _JOURNAL_ROWS)
    stale = arch.build_archive(rd, arch.assign_games(rd)[0])
    stale['schema_version'] = arch.SCHEMA_VERSION - 1
    stale['slices'].pop('state/journal.jsonl', None)
    p = arch.archive_path(rd, game_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8') as f:
        json.dump(stale, f, ensure_ascii=False)
    got = arch.load_archive(rd, game_id)
    assert got is not None
    assert got['schema_version'] == arch.SCHEMA_VERSION
    assert len(got['slices']['state/journal.jsonl']) == 2, '重装配补新账切片'
    with p.open('r', encoding='utf-8') as f:
        on_disk = json.load(f)
    assert on_disk['schema_version'] == arch.SCHEMA_VERSION, '原子写回已升级'


# ============================================================ CLI 读面锁


def _run_cli(monkeypatch, argv: list[str]) -> None:
    monkeypatch.setattr(sys, 'argv', ['cw_telemetry', *argv])
    tel_cli._cli_main()


def test_cli_journal_source_full_views(tmp_path: Path,
                                       monkeypatch,
                                       capsys) -> None:
    """--source journal 视图族:逐轮表/金账/hp 链/快照全族输出。"""
    rd = tmp_path / 'replay'
    _mk_replay(rd, _JOURNAL_ROWS)
    _run_cli(monkeypatch, ['query', '--source', 'journal', '--view', 'all',
                           '--run', 'run_20260830_094811',
                           '--replay-dir', str(rd)])
    out = capsys.readouterr().out
    assert '[逐轮表]' in out and 'P1r1' in out
    assert '[gold 链]' in out and '40→38' in out, '行间差分显影'
    assert '[hp 链]' in out and 'hp=60 (首值)' in out
    assert '[快照]' in out
    assert '[obs_event]' in out, '无事件给显式空提示'


def test_cli_journal_source_default_run_is_last(tmp_path: Path,
                                                monkeypatch,
                                                capsys) -> None:
    """缺省 run = 账内末 run(首现序末位),与旧读面「缺省=最近一局」同语义。"""
    rd = tmp_path / 'replay'
    _mk_replay(rd, _JOURNAL_ROWS)
    _run_cli(monkeypatch, ['query', '--source', 'journal', '--view', 'snapshot',
                           '--replay-dir', str(rd)])
    out = capsys.readouterr().out
    assert 'run_other_game' in out, '末 run 缺省选择'
    assert 'run_20260830_094811' not in out


def test_cli_journal_source_recent_overview(tmp_path: Path,
                                            monkeypatch,
                                            capsys) -> None:
    """--recent 概览:逐 run 一行(行数/节点/末快照读数)。"""
    rd = tmp_path / 'replay'
    _mk_replay(rd, _JOURNAL_ROWS)
    _run_cli(monkeypatch, ['query', '--source', 'journal', '--recent', '5',
                           '--replay-dir', str(rd)])
    out = capsys.readouterr().out
    assert 'run_20260830_094811: 行=2' in out
    assert 'run_other_game: 行=1' in out, '逐 run 一行概览'
    assert '节点=P1r1' in out and 'gold=38' in out


def test_cli_journal_source_missing_ledger_hint(tmp_path: Path,
                                                monkeypatch,
                                                capsys) -> None:
    """新账缺席(影子缺省关常态):提示行不炸,不回落旧流视图。"""
    rd = tmp_path / 'replay'
    _mk_replay(rd)
    _run_cli(monkeypatch, ['query', '--source', 'journal',
                           '--replay-dir', str(rd)])
    out = capsys.readouterr().out
    assert '无统一 state 新账' in out
    assert '[rounds]' not in out, '禁静默回落旧视图(读面选择必须显式)'


def test_cli_journal_truncated_lines_still_render(tmp_path: Path,
                                                  monkeypatch,
                                                  capsys) -> None:
    """宽容性(CLI 面):账内混坏行 → 读面跳坏行照常出视图。"""
    rd = tmp_path / 'replay'
    _mk_replay(rd, _JOURNAL_ROWS[:2])
    p = rd / 'state' / 'journal.jsonl'
    with p.open('a', encoding='utf-8') as f:
        f.write('{"v": 3, "ts": "截断\n')
    _run_cli(monkeypatch, ['query', '--source', 'journal', '--view', 'gold',
                           '--replay-dir', str(rd)])
    out = capsys.readouterr().out
    assert '40→38' in out and '[gold 链]' in out


def test_cli_match_journal_from_archive_slice(tmp_path: Path,
                                              monkeypatch,
                                              capsys) -> None:
    """--match + 新账:档案切片(v12)物化后走同一新账读面(单一源)。"""
    rd = tmp_path / 'replay'
    game_id = _mk_replay(rd, _JOURNAL_ROWS)
    arch.assemble_game(rd, game_id)
    _run_cli(monkeypatch, ['query', '--source', 'journal', '--view', 'gold',
                           '--match', game_id, '--replay-dir', str(rd)])
    out = capsys.readouterr().out
    assert game_id in out and '新账视图' in out
    assert '40→38' in out


def test_cli_source_view_pairing_rejected(tmp_path: Path,
                                          monkeypatch) -> None:
    """读面配对校验:新账视图配旧源/旧视图配新账源/checks 配新账源 = 显式拒绝
    (静默回落 = 判读人以为在读新账实际在读旧流)。"""
    rd = tmp_path / 'replay'
    _mk_replay(rd, _JOURNAL_ROWS)
    for argv in (['query', '--view', 'gold', '--replay-dir', str(rd)],
                 ['query', '--source', 'journal', '--view', 'economy',
                  '--replay-dir', str(rd)],
                 ['checks', '--source', 'journal', '--replay-dir', str(rd)]):
        with pytest.raises(SystemExit):
            _run_cli(monkeypatch, argv)


def test_cli_default_old_path_unchanged(tmp_path: Path,
                                        monkeypatch,
                                        capsys) -> None:
    """缺省(--source old)路径零变化:目录只有新账、无旧流时按旧口径报
    无数据(旧读面不看新账——并存期两读面互不越界)。"""
    rd = tmp_path / 'replay'
    _write_journal(rd, _JOURNAL_ROWS)
    _run_cli(monkeypatch, ['query', '--replay-dir', str(rd)])
    assert capsys.readouterr().out.strip() == '(无 replay 数据)'
