"""CW 遥测按局档案域测试面(状态流水装配收尾 + 跨档去重 + 重装配保真 +
局终行写口/判定/下游识别)。

四节归并自原四个主题文件(测试函数名全量保留,原文件已删):

1. journal 流水装配兜底 + 收尾落盘(原 test_cw_journal_assembly_guard.py;
   背景实证:2026-09-14 18:56 起 8 连局零 state 行零档案,深检
   run_20260915_054718.md §0;修法权威版本 = kernel ``ensure_journal_assembly``
   docstring + ``cw_game_state.game_state_of`` 建立路径注释);
2. 跨档段去重守卫(原 test_cw_match_archive_dedup.py;口径单一源 =
   telemetry-reading.md「决策独有段(零结算段)按段首 ts 归前局」+
   模块 docstring 归局骨架节);
3. 重装配保真(原 test_cw_match_archive_reassembly.py;背景 = 真实双档
   重放实证的「重装配无益有损」);
4. 局终域 match_final(原 test_cw_match_final.py;权威版本引用 = retirement.md
   §2 / §3.6.1 / §3.6.2,设计引用 = 流程侧遥测权威版本 §3.2.3 行型 2 / 表 3-3)。

测试隔离:journal sink / run_id provider / 监听槽均为模块级全局——fixture
统一安装/复位;测试零真实副作用(流水落 tmp_path)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel import cw_game_state as gs_mod
from sr_od.application.currency_war.kernel import cw_state_journal as journal_mod
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    MATCH_FINAL_FIELD,
    GameState,
    game_state_of,
    observe_node_anchor,
    set_match_final_listener,
    write_match_final,
)

# ---- W1 sig 铺满 helper(测试写入口签名必填,ADR-0634;actor 已登记)----
from sr_od.application.currency_war.kernel.cw_game_state import (  # noqa: E402
    ChannelSig as _ChannelSig,
)
from sr_od.application.currency_war.kernel.cw_state_journal import (
    ensure_journal_assembly,
    flush_pending,
    install_state_telemetry,
    reset_state_telemetry,
    state_journal_instance,
)
from sr_od.application.currency_war.obs.cw_observation import (
    detect_match_final,
    resolve_final_type,
    runs_result_to_final_type,
)
from sr_od.application.currency_war.telemetry import match_archive as ma
from sr_od.application.currency_war.telemetry import state as tel_state
from sr_od.application.currency_war.telemetry.state import (
    close_run,
    current_run_id,
    ensure_run_started,
    reset_run_state,
    start_run,
)

# ============================================================
# 1. journal 流水装配兜底 + 收尾落盘
# ============================================================


@pytest.fixture
def _reset_run_cluster() -> None:
    """run 态簇前后复位(telemetry.state 模块全局;防跨测试残留)。"""
    reset_run_state()
    yield
    reset_run_state()


def test_ensure_assembly_installs_at_default_root_when_absent(
        tmp_path: Path) -> None:
    """兜底口双分支:未装配 → 按缺省根补装(测试进程 = conftest 重定向的
    tmp 根);已装配 → 现役实例零成本直过(不 reset 不顶掉,兜底口禁顶掉
    测试/生产自管装配)。"""
    reset_state_telemetry()
    assert state_journal_instance() is None
    ensure_journal_assembly(current_run_id)
    journal = state_journal_instance()
    assert journal is not None
    # conftest 把缺省根缝重定向到本测试的 tmp_path——兜底装配落 tmp,
    # 证明「自动装真实现」在测试进程不触真实账面(测试纪律 2)。
    assert journal.path == tmp_path / 'state' / 'journal.jsonl'
    # 已装配分支:现役实例原样保留
    mine = install_state_telemetry(tmp_path / 'mine' / 'journal.jsonl')
    ensure_journal_assembly(current_run_id)
    assert state_journal_instance() is mine


def test_game_state_establish_wires_assembly() -> None:
    """正主单例建立路径接入调用:game_state_of 局状态容器建立注入 run_id_provider
    即装配(重定向原「run 领取单点接入调用」测试;精化令 2026-09-15:触发
    只钉该建立点,GameState 构造器零装配逻辑;行为等价 = 未初始化状态容器首写
    前装配已发生)。"""
    reset_state_telemetry()
    assert state_journal_instance() is None
    game_state_of(object(), run_id_provider=current_run_id)
    assert state_journal_instance() is not None


def test_draft_birth_and_run_claim_do_not_wire_assembly(
        _reset_run_cluster: None) -> None:
    """装配边界三支(分层归属 + 精化令):草稿状态容器直构(GameState
    构造器零装配逻辑)/ 一次性空载体 / 缺省单例建立(sim/测试口径)均不
    装配;run 领取层 ``ensure_run_started`` 只铸 run,不辖装配。"""
    reset_state_telemetry()
    assert state_journal_instance() is None
    GameState(schema_version=GAME_STATE_SCHEMA_VERSION)   # 草稿状态容器直构:结构性不触发
    game_state_of(None)   # 一次性空载体(局外):不装配
    game_state_of(object())   # 缺省 provider=None 单例建立:不装配
    assert state_journal_instance() is None
    ensure_run_started(match=object(), difficulty='A8')
    assert current_run_id() != ''   # run 领取职责不变(ADR-0588 三分支)
    assert state_journal_instance() is None   # 领取层不辖装配


def test_close_run_flushes_buffered_rows_before_threshold(
        tmp_path: Path, _reset_run_cluster: None) -> None:
    """收尾落盘:批量阈值内的缓冲行随 close_run 落盘(装配读盘不漏局终行);
    无装配实例时 flush_pending 恒 0(收尾单点在未武装进程零副作用)。"""
    # 未武装进程:flush 零副作用(先于装配,隔离面)
    reset_state_telemetry()
    assert flush_pending() == 0
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
    assert state_journal_instance() is not None   # 收尾 flush ≠ 拆装配


# ============================================================
# 2. 跨档段去重守卫(match_archive 跨档归属收敛 + 核验)
# ============================================================

_G_A = 'g_20260908_100000'
_G_C = 'g_20260909_080000'
_G_D = 'g_20260908_090000'
_R_A = 'run_20260908_100000'
_R_B = 'run_20260908_120000'
_R_C = 'run_20260909_080000'
_R_D = 'run_20260908_090000'


def _row(rid: str, ts: str, plane: int, round_num: int) -> dict:
    """最小 journal write 行:行型核心字段 + 节点键(段首帧判据消费面)。"""
    return {
        'v': 1, 'ts': ts, 'run_id': rid, 'row': 'write',
        'field': 'hp', 'after': 48,
        'state': {'values': {'node': {'plane': plane, 'round_num': round_num,
                                      'kind': 'prep'},
                             'hp': 48, 'gold': 10}},
    }


def _write_journal(rd: Path, rows: list[dict]) -> None:
    p = rd / 'state' / 'journal.jsonl'
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def _write_archive(md: Path, gid: str, seg_rids: list[str],
                   slice_rows: dict[str, list[dict]]) -> None:
    """伪造旧口径存量档案(守卫/核验的最小消费面:game_id+segments+slices)。"""
    md.mkdir(parents=True, exist_ok=True)
    payload = {
        'schema_version': 11,
        'game_id': gid,
        'segments': [{'run_id': rid} for rid in seg_rids],
        'slices': slice_rows,
    }
    (md / f'match_{gid}.json').write_text(
        json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def _read_archive(md: Path, gid: str) -> dict:
    return json.loads((md / f'match_{gid}.json').read_text(encoding='utf-8'))


def _seg_rids(archive: dict) -> list[str]:
    return [s.get('run_id') for s in archive.get('segments') or []]


def _journal_rows(rd: Path) -> list[dict]:
    # A 局 (1,1) 新局;B 续段 (2,6) 段首 ts 落 A 后、C 前 → 归前局 A;
    # C (1,1) 新局(后继新局 = 曾夺段的旧 bug 形态对勒面)
    return [
        _row(_R_A, '2026-09-08T10:00:00', 1, 1),
        _row(_R_A, '2026-09-08T10:05:00', 1, 2),
        _row(_R_B, '2026-09-08T12:00:00', 2, 6),
        _row(_R_B, '2026-09-08T12:01:00', 2, 6),
        _row(_R_C, '2026-09-09T08:00:00', 1, 1),
    ]


def _seed_wrong_archive(md: Path, gid: str, seg_rids: list[str],
                        b_rows: list[dict]) -> None:
    """伪造旧口径错误档案:段集持 B(本档段行在前,续段切片在后)。"""
    own = {'g_20260909_080000': _R_C, 'g_20260908_090000': _R_D}[gid]
    own_rows = [_row(own, '2026-09-08T09:00:00' if own == _R_D
                     else '2026-09-09T08:00:00', 1, 1)]
    _write_archive(md, gid, seg_rids,
                   {'state/journal.jsonl': own_rows + b_rows})


def test_assemble_converges_double_counted_segment(tmp_path: Path):
    """装配收尾守卫收敛双计段:正确归属档案持有、错误档案摘除、核验归零;
    错误档案按当前口径整体重装配收敛(段集摘除续段,重装配路径不产生
    剪枝记录——「不产剪枝记录」分支原属 rebuild 测试,并入)。"""
    rd = tmp_path / 'live'
    md = ma.matches_dir(rd)
    b_rows = [_row(_R_B, '2026-09-08T12:00:00', 2, 6),
              _row(_R_B, '2026-09-08T12:01:00', 2, 6)]
    _write_journal(rd, _journal_rows(rd))
    _seed_wrong_archive(md, _G_C, [_R_C, _R_B], b_rows)
    # 仅错误档案持有时(归属档案尚未入档),单档案不构成双计,核验不误报
    assert ma.find_cross_archive_segment_dups(rd) == []

    assert ma.assemble_game(rd, _G_A) is not None
    # A 档案(正确归属)持有 B 全部行;C 档案切片行级无同段重复
    a_rows = [r for rows in _read_archive(md, _G_A).get('slices', {}).values()
              for r in rows]
    assert {json.dumps(r, sort_keys=True) for r in b_rows} <= {
        json.dumps(r, sort_keys=True) for r in a_rows}
    for rows in _read_archive(md, _G_C).get('slices', {}).values():
        assert all(r.get('run_id') != _R_B for r in rows)
    assert ma.find_cross_archive_segment_dups(rd) == []
    # 收敛形态(并入分支):C 档段集摘除 B(按当前口径只剩本局段),且
    # 整体重装配路径不产生剪枝记录(pruned_segments 仅定向剪枝路径暴露)
    arch_c = _read_archive(md, _G_C)
    assert _seg_rids(arch_c) == [_R_C]
    assert 'pruned_segments' not in arch_c


def test_prune_converges_archive_with_lost_source(tmp_path: Path):
    """源流失的错误档案定向剪枝:摘段+切片,显示记录,孤本条目禁动。"""
    rd = tmp_path / 'live'
    md = ma.matches_dir(rd)
    _write_journal(rd, _journal_rows(rd))
    _seed_wrong_archive(md, _G_D, [_R_D, _R_B],
                        [_row(_R_B, '2026-09-08T12:00:00', 2, 6)])

    assert ma.assemble_game(rd, _G_A) is not None
    arch_d = _read_archive(md, _G_D)
    # D 无源流(不在分组):B 归属 A → 剪枝;D 段自身为唯一存档,禁动
    assert _seg_rids(arch_d) == [_R_D]
    for rows in arch_d.get('slices', {}).values():
        assert all(r.get('run_id') != _R_B for r in rows)
    pruned = arch_d.get('pruned_segments')
    assert pruned == [{'run_id': _R_B, 'owned_by': _G_A,
                       'reason': ma._PRUNE_REASON}]


def test_orphan_double_archive_still_reported(tmp_path: Path):
    """守卫收敛不了的孤立双档(同段源流失)由核验暴露,不静默。"""
    rd = tmp_path / 'live'
    md = ma.matches_dir(rd)
    # journal 无 B 行(源流失):两档案各持 B,守卫无归属判据可依 → 不动
    _write_journal(rd, [_row(_R_A, '2026-09-08T10:00:00', 1, 1)])
    b_row = [_row(_R_B, '2026-09-08T12:00:00', 2, 6)]
    _seed_wrong_archive(md, _G_C, [_R_C, _R_B], b_row)
    _seed_wrong_archive(md, _G_D, [_R_D, _R_B], b_row)

    assert ma.assemble_game(rd, _G_A) is not None
    dups = ma.find_cross_archive_segment_dups(rd)
    # archives 按档案文件名序(守卫无归属判据可依的孤立形态,纯显示)
    assert dups == [{'run_id': _R_B, 'archives': [_G_D, _G_C]}]


def test_assemble_pending_converges_below_watermark(tmp_path: Path):
    """水位线以下的双计档案经 assemble_pending 收尾守卫收敛(生产病灶形态)。"""
    rd = tmp_path / 'live'
    md = ma.matches_dir(rd)
    _write_journal(rd, _journal_rows(rd))
    _seed_wrong_archive(md, _G_C, [_R_C, _R_B],
                        [_row(_R_B, '2026-09-08T12:00:00', 2, 6)])

    done = ma.assemble_pending(rd)   # 首跑落水位线,不装存量局;守卫仍收敛
    assert done == []
    assert _seg_rids(_read_archive(md, _G_C)) == [_R_C]

    # 幂等:重复触发守卫不重复剪枝/重装配
    ma.assemble_pending(rd)
    assert _seg_rids(_read_archive(md, _G_C)) == [_R_C]
    assert ma.find_cross_archive_segment_dups(rd) == []


# ============================================================
# 3. 重装配保真(match_archive 派生输入回源流补读)
# ============================================================

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
    """最小 journal write 行(段首帧判据消费面,与 dedup 测试面同型)。"""
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
             actions=[{'__type__': 'CwActionSellDeployedParam', 'deployed_idx': 0,
                       'income': 3}]),
        _dec(_RA, '2026-09-08T10:00:30', 1, 1, hp=100, gold=8,
             deployed=[_dep('Archer', 1, 'front', 2)],
             actions=[{'__type__': 'CwActionStartBattleParam'}]),
        _dec(_RA, '2026-09-08T10:01:00', 1, 2, hp=80, gold=12,
             deployed=[_dep('Archer', 1, 'front', 2), _dep('Lancer', 1, 'back', 1)],
             actions=[{'__type__': 'CwActionStartBattleParam'}], level=2),
        _dec(_RB, '2026-09-08T12:00:00', 2, 3, hp=60, gold=20,
             deployed=[_dep('Archer', 1, 'front', 2), _dep('Miku', 2, 'back', 2)],
             actions=[], level=2),
        _dec(_RB, '2026-09-08T12:01:00', 2, 3, hp=60, gold=15,
             deployed=[_dep('Archer', 1, 'front', 2)],
             actions=[{'__type__': 'CwActionStartBattleParam'}], level=2),
        _dec(_RO, '2026-09-09T08:00:00', 1, 1, hp=100, gold=5,
             deployed=[_dep('Saber', 1, 'front', 1)],
             actions=[{'__type__': 'CwActionStartBattleParam'}]),
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
    """装配主路径保真:切片契约单键(state 新账),派生列从旧流源文件完整重建。"""
    rd = tmp_path / 'live'
    _seed_legacy_dir(rd)

    arch = ma.assemble_game(rd, _GID)
    assert arch is not None
    # 切片契约不回填:单键,旧流键不重入档案载荷
    assert set(arch['slices'].keys()) == {'state/journal.jsonl'}
    # 逐轮表:3 轮,结算真值链/动作合并/快照/收尾全在
    rounds = arch['rounds']
    assert [(r['plane'], r['round']) for r in rounds] == [(1, 1), (1, 2), (2, 3)]
    assert [(r['hp'], r['hp_source'], r['hp_delta']) for r in rounds] == \
        [(80, 'settlement', None), (60, 'settlement', -20),
         (10, 'settlement', -50)]
    assert rounds[0]['gold'] == 8 and rounds[0]['n_decision_frames'] == 2
    assert rounds[0]['action_counts'] == {'CwActionStartBattleParam': 1, 'CwActionSellDeployedParam': 1}
    assert rounds[0]['shop_snapshots'] and rounds[0]['outcome']['hp_after'] == 80
    assert [r['terminal_closure'] for r in rounds] == \
        ['start_battle', 'start_battle', 'start_battle']
    # 败场节点:v9 步进链(两结算分支)+ 终局分支(result=loss 兜底)
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
    # hp 事件显示 / 离场(段内相邻帧差分:卖出命中 + 无动作消失)
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

    生产病灶触发形态:存量 v11 档案直读时触发
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
    assert set(arch['slices'].keys()) == {'state/journal.jsonl'}


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


# ============================================================
# 4. 局终域 match_final(写口 / 监听 / 判定 / 下游识别)
# ============================================================


def _lsig() -> _ChannelSig:
    """渠道②签名(logic_action 族;逻辑写入/confirm)。"""
    return _ChannelSig(family='logic_action', actor='TestSigWriter',
                       mode='compute')


@pytest.fixture()
def journal(tmp_path):
    """装一份指到 tmp 的状态流水(影子面武装;teardown 复位模块全局)。"""
    j = install_state_telemetry(tmp_path / 'state' / 'journal.jsonl',
                                run_id_provider=tel_state.current_run_id)
    yield j
    reset_state_telemetry()


@pytest.fixture()
def run_id(monkeypatch):
    """桩一个 run 归属(行内 run_id 键;teardown 由 monkeypatch 自动还原)。"""
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 'run_test_final')
    return 'run_test_final'


@pytest.fixture(autouse=True)
def _no_listener():
    """监听槽复位(模块级全局;防跨测试残留)。"""
    set_match_final_listener(None)
    yield
    set_match_final_listener(None)


def _rows() -> list[dict]:
    j = journal_mod.state_journal_instance()
    assert j is not None, '本用例须先装 journal(fixture journal)'
    return list(j.rows)


def _final_rows() -> list[dict]:
    return [r for r in _rows() if r.get('field') == MATCH_FINAL_FIELD]


# (收尾整删)原 test_match_final_domain_registered 删:单行「域键在场」断言,经核
#  判读/档案消费面无人读 gs_schema['match_final'] 键——write 系测试红时
#  同故障,子集断言不留。)
# (收尾整删)原 test_match_final_closed_vocab「终局类型词表封闭集」:
#  集外炸错分支并入下方原子行测试(常量字面断言不留);原
#  test_match_final_version_stamps「版本戳」:载荷戳分支并入原子行测试,
#  解析器等值对拍半(kernel 复刻 vs telemetry 单一源双实现等值)随该测试退役
#  ——src 侧 cw_game_state.py 常量段注释仍指针本文件对拍,收尾申报见报告。
# 原 test_write_match_final_default_duration_segment_level「duration_s
# 缺省 = 段级自算」删:缺省时长 = time.monotonic 差值 ≥0,语言自带保证面,
# 显式传值直通半由原子行测试 duration_s=1234.5 断言承担。


def test_write_match_final_one_atomic_row(journal, run_id,
                                          monkeypatch) -> None:
    """同版本原子:一次调用恰一行,载荷(类型/版本 id/快照/时长/版本戳)
    一次装配(行头 v 与 at_version 恒等);渠道签名 = logic_hook/MatchClose;
    终局类型词表封闭(集外显式炸错,禁自由串);版本戳取模块级常量填充
    (monkeypatch 常量即见即断言,常量与取值单一源 telemetry/version_stamp
    的等值对拍面随退役测试申报)。红 = 拆行/签名漂移/集外放行/戳断供。"""
    monkeypatch.setattr(gs_mod, '_CODE_COMMIT', 't244commit')
    monkeypatch.setattr(gs_mod, '_REGISTRY_FINGERPRINT', 't244finger')
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    # 集外终局类型 = 显式炸错(封闭词表)
    with pytest.raises(ValueError):
        write_match_final(gs, final_type='completed')
    gs.write_logic(gs.hp, 48, produced_by='test', sig=_lsig())
    assert write_match_final(gs, final_type='loss', plane=2, round_num=6,
                             level=7, hp=48, gold=53, streak=-1,
                             node_kind='boss', duration_s=1234.5) is True
    rows = _final_rows()
    assert len(rows) == 1, '一次终局写口调用 = 恰一行(同版本原子)'
    row = rows[0]
    assert row['row'] == 'write' and row['run_id'] == run_id
    assert row['sig']['family'] == 'logic_hook'
    assert row['sig']['actor'] == 'MatchClose'
    after = row['after']
    assert after['final_type'] == 'loss'
    assert after['at_version'] == row['v'], '时点版本 id = 本行自身版本 id'
    assert after['plane'] == 2 and after['round_num'] == 6
    assert after['hp'] == 48 and after['gold'] == 53 and after['level'] == 7
    assert after['streak'] == -1 and after['node_kind'] == 'boss'
    assert after['duration_s'] == 1234.5
    assert after['backfilled'] is False
    assert after['code_commit'] == 't244commit', '版本戳随行落账(常量填充)'
    assert after['registry_fingerprint'] == 't244finger', '注册表指纹随行落账'
    # 行行自足:终局快照随行内嵌 state 自带(来源注记面在档)
    vals = row['state']['values']
    assert vals['hp'] == 48, '行内 state = 终局账面(快照行自带)'


def test_write_match_final_segment_idempotent(journal, run_id) -> None:
    """段内幂等(G12 终局防重写前查重并入):本段已有终局行 → 第二次调用
    no-op 返 False,不产第二行。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert write_match_final(gs, final_type='win', plane=3, round_num=9) is True
    n_before = len(_rows())
    assert write_match_final(gs, final_type='loss', plane=3, round_num=9) is False
    assert len(_rows()) == n_before, '幂等跳过零新行'
    assert gs.match_final.value.final_type == 'win', '首行不被覆盖'


def test_abnormal_backfill_note_recovered_version_allocated(journal, run_id) -> None:
    """异常终局补写(G8):backfilled=True → 版本 id 照常分配 + 行载荷
    backfilled 位 + 行注记缺省 recovered 显示(判读可辨真伪)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    v_before = gs.write_seq
    assert write_match_final(gs, final_type='abnormal', plane=1, round_num=3,
                             backfilled=True) is True
    row = _final_rows()[0]
    assert row['v'] == v_before + 1, '补写行版本 id 照常分配'
    assert row['after']['final_type'] == 'abnormal'
    assert row['after']['backfilled'] is True
    assert row['note'] == 'recovered', '补写行 note=recovered 显示'


def test_match_final_listener_fires_on_row_only(journal, run_id) -> None:
    """复盘触发器调用点(武装+局内态):监听缺省关;写口受理成功即触发
    (幂等跳过不触发);事件携带 run_id/终局类型/版本;监听异常不毒化终局
    流转。未武装/局外两态的触发真值 = 下一个测试。"""
    fired: list[dict] = []
    set_match_final_listener(fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert write_match_final(gs, final_type='win', plane=3, round_num=9) is True
    assert len(fired) == 1
    assert fired[0]['run_id'] == run_id
    assert fired[0]['final_type'] == 'win'
    assert fired[0]['version'] == _final_rows()[0]['v']
    assert write_match_final(gs, final_type='loss') is False
    assert len(fired) == 1, '幂等跳过不触发'

    def _boom(info: dict) -> None:
        raise RuntimeError('listener boom')

    set_match_final_listener(_boom)
    bs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert write_match_final(bs2, final_type='loss') is True, \
        '监听异常不毒化终局流转'


def test_match_final_listener_fires_unarmed_and_offmatch(tmp_path) -> None:
    """触发真值两态(申报勘误钉住的测试):未武装(无 sink)/局外(供给槽返空)
    行均不落而监听照触发,事件 run_id=''——消费方(复盘触发接入调用)按此
    自滤,禁按「落行才触发」旧申报消费。"""
    fired: list[dict] = []
    set_match_final_listener(fired.append)
    # 态①未武装:sink 缺席 → 版本照耗、Field 照写、零落盘,事件照发
    reset_state_telemetry()
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert write_match_final(gs, final_type='win') is True
    assert len(fired) == 1
    assert fired[0]['run_id'] == ''
    assert fired[0]['final_type'] == 'win'
    # 态②局外:武装但供给槽返空 → 行被局外门拒落,事件照发(run_id='')
    j = install_state_telemetry(tmp_path / 'state' / 'journal.jsonl',
                                run_id_provider=lambda: '')
    try:
        bs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        assert write_match_final(bs2, final_type='loss') is True
        assert len(fired) == 2
        assert fired[1]['run_id'] == ''
        rows = [r for r in j.rows if r.get('field') == MATCH_FINAL_FIELD]
        assert rows == [], '未武装/局外两态行均不落盘'
    finally:
        reset_state_telemetry()


# (收尾整删)原 test_obs_event_vocab_closed_set「obs_event 事件词表封闭
#  集(硬约束 2)」删:常量字面断言 + 炸错分支 = 事实源在 cw_vocab 词表定义,
#  集外炸错由 pytest.raises 形态与封闭集测试同构面承担不成立——如实申报:
#  note_obs_event 集外炸错行为现无独立测试,词表漂移归 kernel 既有测试与
#  review 面(覆盖缺口随收尾申报)。


def test_g10_retrograde_obs_event_evidence(journal, run_id) -> None:
    """G10 倒退留证(锚定口径,
    切换后写端 = observe_node_anchor):读数 < 现值 → 零状态变更(字段不动)
    + obs_event 留证(event=arbitrate,actor = 锚定宿主登记名,占版本)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    observe_node_anchor(gs, (1, 5), trigger_screen='货币战争-备战',
                        actor='TestAnchor')
    assert gs.node_pos.value == (1, 5)
    n_before = len(_rows())
    observe_node_anchor(gs, (1, 4), trigger_screen='货币战争-备战',
                        actor='TestAnchor')
    assert gs.node_pos.value == (1, 5), '倒退免疫:字段不动(R3 规则三)'
    evs = [r for r in _rows()[n_before:] if r['row'] == 'obs_event']
    assert len(evs) == 1, '倒退丢弃 obs_event 留证(占版本零状态变更)'
    ev = evs[0]
    assert ev['event'] == 'arbitrate'
    assert ev['field'] == 'node_pos'
    assert ev['observed'] == {'reading': '1-4', 'current': '1-5'}
    assert ev['sig']['actor'] == 'TestAnchor'
    assert '倒退' in ev['verdict']


def test_resolve_final_type_priority_ladder() -> None:
    """在线判定序 = 主动停止 > 失败 > 通关(plane==3 精确值,假 win 守卫
    同口径);未打轮 = None(开局失败形态非终局);其余真实结束 = abnormal。"""
    assert resolve_final_type(stop_requested=True, saw_defeat=True,
                              plane_reached=3) == 'stopped'
    assert resolve_final_type(stop_requested=False, saw_defeat=True,
                              plane_reached=3) == 'loss'
    assert resolve_final_type(stop_requested=False, saw_defeat=False,
                              plane_reached=3) == 'win'
    assert resolve_final_type(stop_requested=False, saw_defeat=False,
                              plane_reached=1, rounds_played=False) is None
    assert resolve_final_type(stop_requested=False, saw_defeat=False,
                              plane_reached=1) == 'abnormal'
    # plane=8(OCR 难度泄漏形态)≠ 通关:假 win 守卫同口径,禁 >=
    assert resolve_final_type(stop_requested=False, saw_defeat=False,
                              plane_reached=8) == 'abnormal'


def test_runs_result_mapping_covers_archive_values() -> None:
    """runs result 词表并入映射:win/loss/stopped 直映;非完结值(含
    abandoned/completed/空)= abnormal——与档案装配器完结判定同界。"""
    assert runs_result_to_final_type('win') == 'win'
    assert runs_result_to_final_type('loss') == 'loss'
    assert runs_result_to_final_type('stopped') == 'stopped'
    assert runs_result_to_final_type('abandoned') == 'abnormal'
    assert runs_result_to_final_type('completed') == 'abnormal'
    assert runs_result_to_final_type('') == 'abnormal'


def test_detect_match_final_evidence_ladder() -> None:
    """证据阶梯:journal 已收尾 → None(幂等);runs_summary 行 → 并入映射;
    terminal_closure 结算行 → 收尾行映射;全缺 → abnormal(补写形态判据)。"""
    assert detect_match_final(run_id='r', journal_final={'v': 1}) is None
    d = detect_match_final(
        run_id='r',
        runs_summary={'result': 'loss', 'plane_reached': 2,
                      'rounds_survived': 6, 'final_hp': 48,
                      'ts': '2026-09-10T10:00:00'})
    assert (d.final_type, d.plane, d.round_num, d.hp) == ('loss', 2, 6, 48)
    assert d.evidence == 'runs_summary'
    d2 = detect_match_final(
        run_id='r',
        outcome_rows=[{'source': 'terminal_closure', 'match_result': 'stopped',
                       'plane': 2, 'round_num': 6, 'ts': 't'}])
    assert (d2.final_type, d2.plane, d2.round_num) == ('stopped', 2, 6)
    assert d2.evidence == 'terminal_closure'
    d3 = detect_match_final(run_id='r', outcome_rows=[
        {'source': '', 'killed': False}])   # 非收尾行不入阶梯 3
    assert d3.final_type == 'abnormal'
    assert d3.evidence == 'no_close_evidence'


def _journal_line(v: int, run: str, final_type: str, *, note: str = '') -> str:
    payload = {'final_type': final_type, 'at_version': v, 'plane': 3,
               'round_num': 9, 'node_kind': None, 'level': 9, 'hp': 10,
               'gold': 77, 'streak': 5, 'duration_s': 600.0,
               'backfilled': bool(note)}
    row = {'v': v, 'ts': '2026-09-10T10:00:00', 'run_id': run, 'row': 'write',
           'field': MATCH_FINAL_FIELD, 'after': payload, 'same_value': False,
           'state': {'values': {}}, 'sig': {'family': 'logic_hook',
                                            'actor': 'MatchClose'},
           'note': note, 'evidence_refs': []}
    return json.dumps(row, ensure_ascii=False)


def test_extract_match_final_rows_recognition() -> None:
    """识别判据封闭:write ∧ field=match_final ∧ run_id 非空;同 run 多行取
    v 最大;obs_event 行/他字段行不误收。"""
    rows = [
        {'row': 'write', 'field': 'gold', 'run_id': 'r1', 'v': 1},
        {'row': 'write', 'field': MATCH_FINAL_FIELD, 'run_id': 'r1', 'v': 2,
         'after': {'final_type': 'loss'}},
        {'row': 'obs_event', 'field': MATCH_FINAL_FIELD, 'run_id': 'r1',
         'v': 3, 'event': 'arbitrate'},
        {'row': 'write', 'field': MATCH_FINAL_FIELD, 'run_id': '', 'v': 4},
        {'row': 'write', 'field': MATCH_FINAL_FIELD, 'run_id': 'r2', 'v': 5,
         'after': {'final_type': 'win'}},
        {'row': 'write', 'field': MATCH_FINAL_FIELD, 'run_id': 'r1', 'v': 6,
         'after': {'final_type': 'win'}},
    ]
    out = ma.extract_match_final_rows(rows)
    assert set(out) == {'r1', 'r2'}
    assert out['r1']['v'] == 6, '同 run 多行取 v 最大'
    assert out['r2']['v'] == 5
    assert ma.extract_match_final_rows(None) == {}


# (收尾整删)原 test_view_match_final_reading「判读 CLI 读面(view_
#  match_final 暴露/无行提示)」删:CLI 输出文案测试(「type=」「补写」等
#  字样断言)= 展示层快照,红时答不出哪个消费行为坏了;判读读数面由
#  match_final_rows 行取数(原 view 测试内同函数断言)与下游档案测试承担。


def test_build_archive_endgame_match_final(tmp_path, monkeypatch) -> None:
    """档案端到端(假环境):新账局终行在档 → endgame.match_final 装配;
    无局终行 → None 键(旧档案/影子未开形态)。加法键零 bump 申报测试。"""
    rd = tmp_path / 'replay'
    (rd / 'state').mkdir(parents=True)
    for name in ('decisions.jsonl', 'outcomes.jsonl', 'runs.jsonl'):
        (rd / name).write_text('', encoding='utf-8')
    j = rd / 'state' / 'journal.jsonl'
    j.write_text(_journal_line(3, 'run_x', 'loss') + '\n', encoding='utf-8')
    game = {'game_id': 'g_test', 'segments': ['run_x'],
            'start_ts': '2026-09-10T10:00:00', 'end_ts': '2026-09-10T10:10:00'}
    a = ma.build_archive(rd, game)
    mf = a['endgame']['match_final']
    assert mf is not None
    assert mf['run_id'] == 'run_x'
    assert mf['final']['final_type'] == 'loss'
    assert mf['v'] == 3
    # 无局终行形态
    j.write_text('', encoding='utf-8')
    a2 = ma.build_archive(rd, game)
    assert a2['endgame']['match_final'] is None
    assert a2['schema_version'] == ma.SCHEMA_VERSION


def test_match_final_payload_carries_cw4_aggregate(journal, run_id) -> None:
    """载荷聚合测试:write_match_final(cw4_counters=…) → 载荷原样落账;
    写口浅拷贝(传入状态容器后写不串账)。None = 无策略载体诚实缺省;聚合键
    进 journal 局终行 after 载荷,行行自足可读(判读直接读行,零重放;
    原 cw4_aggregate_in_journal_row 行可见性分支并入)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    counters = {'shop_churn_pair_buy': 3, 'launch_frame_idle_gold': 120}
    assert write_match_final(gs, final_type='loss',
                             cw4_counters=counters) is True
    payload = gs.match_final.value
    assert payload.cw4_counters == counters, '聚合随局终行落账'
    assert payload.cw4_counters is not counters, '载荷持快照副本非状态容器引用'
    counters['shop_churn_pair_buy'] = 99
    assert payload.cw4_counters['shop_churn_pair_buy'] == 3, '后写不串'
    # 行可见性分支(并入):journal 局终行 after 携带聚合键(快照态,不受
    # 后写串改)
    rows = _final_rows()
    assert rows and rows[0]['after']['cw4_counters'] == {
        'shop_churn_pair_buy': 3, 'launch_frame_idle_gold': 120}, (
        '聚合进 journal 局终行(局终级全键聚合可见性载体,行行自足)')
    # None 形态(无 session/历史段补写无源)
    bs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert write_match_final(bs2, final_type='abnormal',
                             backfilled=True) is True
    assert bs2.match_final.value.cw4_counters is None, (
        '无载体 = None 诚实缺省(与零计数空 dict 可辨)')
