"""CW 按局档案重装配保真锁面(match_archive 派生输入回源流补读)。

出处 = telemetry/match_archive.py ``_load_derived_inputs``;背景 =
T-242 真实双档重放实证的「重装配无益有损」:v12 起切片契约只含
op_journal + state/journal 两文件,而 rounds/loss_nodes/departures 等
派生列的输入吃旧流键——任何重装配(load_archive 版本迁移 / 段集增长 /
跨档守卫整体重装配)都会把派生列全量清空,此前只能靠一次性脚本按装配端
真函数重建。锁四件事:
1. 旧流源文件在档时,装配主路径(assemble_game)产出派生列完整的档案,
   数值与手工按真函数从切片行集算得的一致(本轮 fixture 为手工推演的
   期望值,非同函数二次计算);
2. 派生输入切片优先级:切片在档且非空的键透传不回源;缺键回源流并按
   段集过滤(他局行不漏入);
3. 源流已清 → 重装配诚实退化为空派生列(不炸、不猜测);
4. load_archive 版本迁移读端路径同样保真(生产病灶触发形态)。
"""

from __future__ import annotations

import json
from pathlib import Path

from sr_od.application.currency_war.telemetry import match_archive as ma

_RA = 'run_20260908_100000'
_RB = 'run_20260908_120000'
_RO = 'run_20260909_080000'
_GID = 'g_20260908_100000'


def _dep(char: str, star: int, row: str, slot: int) -> dict:
    return {'char_id': char, 'star': star, 'position_pref': row, 'slot': slot}


def _dec(rid: str, ts: str, plane: int, rnd: int, *, hp: int, gold: int,
         deployed: list[dict], actions: list[dict], level: int = 1) -> dict:
    return {'run_id': rid, 'ts': ts, 'plane': plane, 'round_num': rnd,
            'hp': hp, 'hp_readable': True, 'gold': gold, 'gold_readable': True,
            'strategy_id': 'decision_v2',
            'state': {'level': level, 'deployed': deployed, 'bench': [],
                      'board': [], 'node_type': 'prep'},
            'actions': actions}


def _outcome(rid: str, ts: str, plane: int, rnd: int, hp_after: int) -> dict:
    return {'run_id': rid, 'ts': ts, 'plane': plane, 'round_num': rnd,
            'node_type': 'battle', 'hp_after': hp_after,
            'hp_confidence': 0.98, 'source': ''}


def _journal_row(rid: str, ts: str, plane: int, rnd: int) -> dict:
    """最小 journal write 行(段首帧判据消费面,与 dedup 锁面同型)。"""
    return {'v': 1, 'ts': ts, 'run_id': rid, 'row': 'write', 'field': 'hp',
            'after': 48,
            'state': {'values': {'node': {'plane': plane, 'round_num': rnd,
                                          'kind': 'prep'},
                                 'hp': 48, 'gold': 10}}}


def _write_jsonl(rd: Path, name: str, rows: list[dict]) -> None:
    p = rd / name
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def _seed_legacy_dir(rd: Path) -> None:
    """旧流时代的 replay 目录:两段一局 + 他局各一,旧流文件全在档。

    A 局两段:RA 从 (1,1) 起,RB 续段从 (2,3) 起(段界重锚/恢复态对账
    消费面);RO 为后开他局(段过滤防漏入的对照面)。
    """
    _write_jsonl(rd, 'decisions.jsonl', [
        _dec(_RA, '2026-09-08T10:00:00', 1, 1, hp=100, gold=10,
             deployed=[_dep('Saber', 1, 'front', 1), _dep('Archer', 1, 'front', 2)],
             actions=[{'__type__': 'SellDeployed', 'deployed_idx': 0,
                       'income': 3}]),
        _dec(_RA, '2026-09-08T10:00:30', 1, 1, hp=100, gold=8,
             deployed=[_dep('Archer', 1, 'front', 2)],
             actions=[{'__type__': 'StartBattle'}]),
        _dec(_RA, '2026-09-08T10:01:00', 1, 2, hp=80, gold=12,
             deployed=[_dep('Archer', 1, 'front', 2), _dep('Lancer', 1, 'back', 1)],
             actions=[{'__type__': 'StartBattle'}], level=2),
        _dec(_RB, '2026-09-08T12:00:00', 2, 3, hp=60, gold=20,
             deployed=[_dep('Archer', 1, 'front', 2), _dep('Miku', 2, 'back', 2)],
             actions=[], level=2),
        _dec(_RB, '2026-09-08T12:01:00', 2, 3, hp=60, gold=15,
             deployed=[_dep('Archer', 1, 'front', 2)],
             actions=[{'__type__': 'StartBattle'}], level=2),
        _dec(_RO, '2026-09-09T08:00:00', 1, 1, hp=100, gold=5,
             deployed=[_dep('Saber', 1, 'front', 1)],
             actions=[{'__type__': 'StartBattle'}]),
    ])
    _write_jsonl(rd, 'outcomes.jsonl', [
        _outcome(_RA, '2026-09-08T10:00:45', 1, 1, 80),
        _outcome(_RA, '2026-09-08T10:01:30', 1, 2, 60),
        _outcome(_RB, '2026-09-08T12:02:00', 2, 3, 10),
        _outcome(_RO, '2026-09-09T08:00:30', 1, 1, 90),
    ])
    _write_jsonl(rd, 'shop_snapshots.jsonl', [
        {'run_id': _RA, 'ts': '2026-09-08T10:00:10', 'plane': 1,
         'round_num': 1, 'offers': []},
    ])
    _write_jsonl(rd, 'exogenous.jsonl', [
        {'run_id': _RA, 'ts': '2026-09-08T09:59:00', 'kind': 'briefing',
         'difficulty': 'V4'},
        {'run_id': _RA, 'ts': '2026-09-08T10:00:20', 'kind': 'hp_pay',
         'choice': {'plane': 1, 'round_num': 1, 'currency': 'hp',
                    'hp_delta': -10, 'mode': 'blood_buy', 'clicks': 1,
                    'basis': 'test'}},
    ])
    _write_jsonl(rd, 'invest_cards.jsonl', [
        {'run_id': _RA, 'ts': '2026-09-08T09:59:10', 'kind': 'env',
         'name': '环境A', 'chosen': True},
        {'run_id': _RA, 'ts': '2026-09-08T09:59:20', 'kind': 'strategy',
         'name': '策略A', 'chosen': False},
    ])
    _write_jsonl(rd, 'runs.jsonl', [
        {'run_id': _RA, 'result': 'loss', 'rounds_survived': 3,
         'plane_reached': 2, 'final_hp': 10, 'difficulty': 'V4',
         'code_commit': 'c0ffee', 'registry_fingerprint': 'rf1'},
        {'run_id': _RB, 'result': 'loss', 'rounds_survived': 3,
         'plane_reached': 2, 'final_hp': 10, 'difficulty': 'V4'},
        {'run_id': _RO, 'result': 'win', 'rounds_survived': 2,
         'plane_reached': 1, 'final_hp': 90, 'difficulty': 'V2'},
    ])
    _write_jsonl(rd, 'state/journal.jsonl', [
        _journal_row(_RA, '2026-09-08T10:00:00', 1, 1),
        _journal_row(_RB, '2026-09-08T12:00:00', 2, 3),
        _journal_row(_RO, '2026-09-09T08:00:00', 1, 1),
    ])


def test_assemble_rebuilds_derived_columns_from_legacy_streams(tmp_path: Path):
    """装配主路径保真:切片契约两文件,派生列从旧流源文件完整重建。"""
    rd = tmp_path / 'live'
    _seed_legacy_dir(rd)

    arch = ma.assemble_game(rd, _GID)
    assert arch is not None
    # 切片契约不回填:v12 两文件,旧流键不重入档案载荷
    assert set(arch['slices'].keys()) == {'op_journal.jsonl',
                                          'state/journal.jsonl'}
    # 逐轮表:3 轮,结算真值链/动作合并/快照/收口全在
    rounds = arch['rounds']
    assert [(r['plane'], r['round']) for r in rounds] == [(1, 1), (1, 2), (2, 3)]
    assert [(r['hp'], r['hp_source'], r['hp_delta']) for r in rounds] == \
        [(80, 'settlement', None), (60, 'settlement', -20),
         (10, 'settlement', -50)]
    assert rounds[0]['gold'] == 8 and rounds[0]['n_decision_frames'] == 2
    assert rounds[0]['action_counts'] == {'StartBattle': 1, 'SellDeployed': 1}
    assert rounds[0]['shop_snapshots'] and rounds[0]['outcome']['hp_after'] == 80
    assert [r['terminal_closure'] for r in rounds] == \
        ['start_battle', 'start_battle', 'start_battle']
    # 败场节点:v9 步进链(两结算腿)+ 终局腿(result=loss 兜底)
    assert arch['loss_nodes'] == [
        {'plane': 1, 'round': 2, 'node_type': 'battle', 'hp': 60,
         'delta': -20, 'hp_source': 'settlement', 'outcome_source': '',
         'ts': '2026-09-08T10:01:30'},
        {'plane': 2, 'round': 3, 'node_type': 'battle', 'hp': 10,
         'delta': -50, 'hp_source': 'settlement', 'outcome_source': '',
         'ts': '2026-09-08T12:02:00'},
        {'plane': 2, 'round': 3, 'node_type': 'battle', 'hp': 0,
         'delta': -10, 'hp_source': 'endgame_final',
         'outcome_source': 'runs.final_hp', 'ts': None}]
    # hp 事件显影 / 离场(段内相邻帧差分:卖出命中 + 无动作消失)
    assert arch['hp_events'] == [
        {'run_id': _RA, 'ts': '2026-09-08T10:00:20', 'plane': 1, 'round': 1,
         'currency': 'hp', 'hp_delta': -10, 'mode': 'blood_buy', 'clicks': 1,
         'basis': 'test'}]
    assert arch['departures'] == [
        {'run_id': _RA, 'plane': 1, 'round': 1, 'ts': '2026-09-08T10:00:00',
         'char': 'Saber', 'star': 1, 'count': 1, 'channel': 'sell_recorded',
         'same_window_arrivals': []},
        {'run_id': _RB, 'plane': 2, 'round': 3, 'ts': '2026-09-08T12:00:00',
         'char': 'Miku', 'star': 2, 'count': 1, 'channel': 'unexplained',
         'same_window_arrivals': []}]
    # 恢复态对账:RB 恢复帧 vs RA 末帧(段界重锚差为 0,无扩展键)
    assert arch['resume_reconciliation'] == [
        {'run_id': _RB, 'resume_ts': '2026-09-08T12:00:00',
         'prev_final_ts': '2026-09-08T10:01:00',
         'resume_frame': {'plane': 2, 'round_num': 3},
         'hp': {'resume': 60, 'prev_final': 80, 'aligned': False},
         'gold': {'resume': 20, 'prev_final': 12, 'aligned': False},
         'level': {'resume': 2, 'prev_final': 2, 'aligned': True}}]
    # 开局面 / 终局快照 / 段首帧
    assert arch['opening']['briefing_rows'] and arch['opening']['chosen_env'] == ['环境A']
    assert arch['opening']['chosen_strategies'] == []
    assert arch['endgame']['final_snapshot']['ts'] == '2026-09-08T12:01:00'
    assert arch['endgame']['final_snapshot']['closure'] == 'start_battle'
    assert [s['first_frame'] for s in arch['segments']] == [(1, 1), (2, 3)]
    # 他局行不漏入(段过滤):RO 的 (1,1) 结算行若漏入,rounds[0] 会取到它
    assert rounds[0]['hp'] == 80
    assert all(d['run_id'] != _RO for d in arch['departures'])


def test_load_archive_migration_rebuilds_derived_columns(tmp_path: Path):
    """版本迁移读端路径保真:陈旧档案经 load_archive 自动重装配补齐派生列。

    生产病灶触发形态(T-242 实证):存量 v11 档案直读时触发
    assemble_game 重装配,修复后派生列应完整而非全空。
    """
    rd = tmp_path / 'live'
    md = ma.matches_dir(rd)
    _seed_legacy_dir(rd)
    md.mkdir(parents=True, exist_ok=True)
    (md / f'match_{_GID}.json').write_text(json.dumps({
        'schema_version': 11, 'game_id': _GID,
        'segments': [{'run_id': _RA}, {'run_id': _RB}],
    }, ensure_ascii=False), encoding='utf-8')

    arch = ma.load_archive(rd, _GID)
    assert arch is not None
    assert arch['schema_version'] == ma.SCHEMA_VERSION
    assert [(r['hp'], r['hp_delta']) for r in arch['rounds']] == \
        [(80, None), (60, -20), (10, -50)]
    assert len(arch['loss_nodes']) == 3
    assert len(arch['departures']) == 2


def test_reassembly_degrades_honestly_without_streams(tmp_path: Path):
    """源流已清 → 重装配诚实退化:派生列空列表,不炸不猜测,切片契约不变。"""
    rd = tmp_path / 'live'
    _seed_legacy_dir(rd)
    for name in ma._DERIVED_INPUT_FILES:
        (rd / name).unlink()

    arch = ma.assemble_game(rd, _GID)
    assert arch is not None
    assert arch['rounds'] == []
    assert arch['loss_nodes'] == []
    assert arch['departures'] == []
    assert arch['hp_events'] == []
    assert arch['resume_reconciliation'] == []
    assert arch['opening']['briefing_rows'] == []
    assert set(arch['slices'].keys()) == {'op_journal.jsonl',
                                          'state/journal.jsonl'}


def test_derived_inputs_slice_precedence(tmp_path: Path):
    """输入供给优先级:切片在档非空键透传不回源;缺键回源流按段过滤。"""
    rd = tmp_path
    sent = [{'run_id': 'run_x', 'ts': 't1'}]
    got = ma._load_derived_inputs(rd, {'run_x'}, {'decisions.jsonl': sent})
    assert got['decisions.jsonl'] == sent

    _write_jsonl(rd, 'outcomes.jsonl', [
        {'run_id': 'run_x', 'hp_after': 1},
        {'run_id': 'run_y', 'hp_after': 2},
    ])
    got = ma._load_derived_inputs(rd, {'run_x'}, {})
    assert [r['run_id'] for r in got['outcomes.jsonl']] == ['run_x']
