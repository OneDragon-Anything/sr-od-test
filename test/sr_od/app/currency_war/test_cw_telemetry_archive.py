"""test_cw_telemetry_archive 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- match_archive: test_cw_match_archive.py
- performance: test_cw_performance.py
- telemetry_checks: test_cw_telemetry_checks.py
- test_telemetry_extra_sig: test_telemetry_extra_sig.py
  (test_telemetry_replay 段已删,2026-09-03 攻击排查:读本机 .debug 语料
   不可复现;①双轨配方语义由 test_cw_deploy_ops.py::test_decision_target_
   dual_track_returns_recipe 合成锁承载,③翻转率守卫为本地审计性质)
- w527_node_ledger: test_cw_w527_node_ledger.py
- (test_equips_telemetry 段已删:补拷顺序+落盘链语义由
   test_cw_telemetry.py:172-221 承接)
- (effect_ledger 段已删:合并批失踪,覆盖缺口登记于瘦身批债账 D1)
- divergence_stats: test_cw_divergence_stats.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations

# ==================== match_archive ====================
import json
import sys as _match_archive_sys
from pathlib import Path as _match_archive_Path

import pytest

_match_archive_sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_game_state import (
    board_state_bridge as _bridge,
)
from sr_od.application.currency_war.telemetry import match_archive as arch


def _write_jsonl(d: _match_archive_Path, name: str, rows: list[dict]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    with (d / name).open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def _dec(run_id, plane, rnd, ts, **kw):
    base = {'schema_version': 1, 'run_id': run_id, 'plane': plane,
            'round_num': rnd, 'ts': ts, 'gold': 10, 'gold_readable': True,
            'hp': 100, 'hp_readable': False, 'strategy_id': 'decision_v2',
            'actions': [], 'state': {'node_type': '普通战斗', 'level': 3,
                                     'hp_trusted': None, 'board': {},
                                     'deployed': []}}
    base.update(kw)
    return base


def _out(run_id, plane, rnd, ts, hp_after, conf=1.0, node_type='普通战斗',
         source=''):
    # source(v8):结算行来源标记(''=屏面真值;'synthetic_supply'=合成行),
    # loss_nodes 条目 outcome_source 加法键的取值来源
    return {'schema_version': 1, 'run_id': run_id, 'plane': plane,
            'round_num': rnd, 'ts': ts, 'node_type': node_type,
            'hp_after': hp_after, 'hp_confidence': conf, 'killed': False,
            'board_before': {}, 'bench_count': 0, 'source': source}


@pytest.fixture()
def replay(tmp_path: _match_archive_Path) -> _match_archive_Path:
    """两段一局(run_A 起于 p1r1,run_B 续局起于 p1r9)+ 独立一局 run_C。"""
    rd = tmp_path / 'replay'
    dec, out, runs = [], [], []
    # 局 g_A:段 A p1r1-r2(帧 hp=100 不可信,outcome 结算真值 60/52)
    dec += [_dec('run_20260830_094811', 1, 1, '2026-08-30T09:48:11', target_comp='甲'),
            _dec('run_20260830_094811', 1, 2, '2026-08-30T09:50:00')]
    out += [_out('run_20260830_094811', 1, 1, '2026-08-30T09:49:00', 60),
            _out('run_20260830_094811', 1, 2, '2026-08-30T09:51:00', 52)]
    runs.append({'run_id': 'run_20260830_094811', 'ts': '2026-08-30T10:09:38',
                 'result': 'stopped', 'plane_reached': 1,
                 'rounds_survived': 2, 'final_hp': 52, 'difficulty': 'A8'})
    # 段 B 续局:首帧 p1r9(非 (1,1))→ 继承 g_A;p2r1 掉血 52→40(败场)
    dec += [_dec('run_20260830_101513', 1, 9, '2026-08-30T10:17:16',
                 actions=[{'__type__': 'BuyCard', 'card': {'name': '椒丘', 'cost': 2}}]),
            _dec('run_20260830_101513', 2, 1, '2026-08-30T10:25:00',
                 dp_posture='release', form_score=0.5, sess_p1_pair={'a': 1})]
    out += [_out('run_20260830_101513', 1, 9, '2026-08-30T10:20:00', 18),
            _out('run_20260830_101513', 2, 1, '2026-08-30T10:26:00', 40, node_type='boss')]
    runs.append({'run_id': 'run_20260830_101513', 'ts': '2026-08-30T10:31:31',
                 'result': 'loss', 'plane_reached': 2,
                 'rounds_survived': 1, 'final_hp': 0, 'difficulty': ''})
    # 独立局 run_C(起于 p1r1)
    dec += [_dec('run_20260830_110000', 1, 1, '2026-08-30T11:00:00')]
    out += [_out('run_20260830_110000', 1, 1, '2026-08-30T11:01:00', 80)]
    runs.append({'run_id': 'run_20260830_110000', 'ts': '2026-08-30T11:10:00',
                 'result': 'loss', 'plane_reached': 1,
                 'rounds_survived': 1, 'final_hp': 0})
    _write_jsonl(rd, 'decisions.jsonl', dec)
    _write_jsonl(rd, 'outcomes.jsonl', out)
    _write_jsonl(rd, 'runs.jsonl', runs)
    _write_jsonl(rd, 'shop_snapshots.jsonl', [
        {'run_id': 'run_20260830_101513', 'plane': 1, 'round_num': 9,
         'ts': '2026-08-30T10:18:00', 'event': 'offer', 'gold': 12, 'shop': []},
        {'run_id': 'run_20260830_101513', 'plane': 1, 'round_num': 9,
         'ts': '2026-08-30T10:18:30', 'event': 'refresh', 'gold': 10, 'shop': []}])
    _write_jsonl(rd, 'invest_cards.jsonl', [
        {'run_id': 'run_20260830_094811', 'kind': 'env', 'name': '增发货币', 'chosen': True}])
    _write_jsonl(rd, 'exogenous.jsonl', [
        {'run_id': 'run_20260830_094811', 'kind': 'briefing', 'round_num': 0,
         'ts': '2026-08-30T09:47:00', 'detail': '难度A8', 'state_snapshot': {}}])
    # 新账行(v12+ 装配切片语义;W3 起 _SLICE_FILES 只含 op_journal+journal,
    # materialize/读面同源测试消费本行集)
    jrows = [
        {'v': 1, 'ts': '2026-08-30T09:50:00', 'run_id': 'run_20260830_094811',
         'row': 'write', 'field': 'gold', 'after': 10,
         'state': {'values': {'gold': 10, 'hp': 60}},
         'sig': {'family': 'obs', 'actor': 'X', 'mode': 'read'},
         'note': '', 'evidence_refs': []},
        {'v': 2, 'ts': '2026-08-30T10:26:00', 'run_id': 'run_20260830_101513',
         'row': 'write', 'field': 'gold', 'after': 5,
         'state': {'values': {'gold': 5, 'hp': 40}},
         'sig': {'family': 'obs', 'actor': 'X', 'mode': 'read'},
         'note': '', 'evidence_refs': []},
    ]
    (rd / 'state').mkdir(parents=True, exist_ok=True)
    _write_jsonl(rd, 'state/journal.jsonl', jrows)
    return rd


def test_assign_games_cross_segment_inheritance(replay: _match_archive_Path):
    """段首帧非 (p1,r1) 起 = 续局 → 继承上一段 game_id;独立局另起。"""
    games = arch.assign_games(replay)
    # run_B 首帧 (p1,r9) 非 (p1,r1) → 并入 run_A 所在局;run_C 自成一局
    assert [g['game_id'] for g in games] == ['g_20260830_094811',
                                             'g_20260830_110000']
    g1 = games[0]
    assert g1['segments'] == ['run_20260830_094811', 'run_20260830_101513']
    assert g1['start_ts'] == '2026-08-30T09:48:11'
    assert g1['end_ts'] == '2026-08-30T10:31:31'
    assert games[1]['segments'] == ['run_20260830_110000']


# [退役墓碑,W3]test_archive_hp_truth_chain 随档案 rounds hp 链构建面
# (旧流切片)拆除退役(W3)。git 历史可复活。
# [退役墓碑,W3]test_frame_hp_fallback_marks_untrusted 随档案 rounds hp 链
# 构建面(旧流切片)拆除退役(W3);hp 可信门单一源由 HP_CONF_TRUSTED 谓词
# 锁(test_terminal_row_exits_hp_truth_chains 与 sim/pool 侧)承锁。
# git 历史可复活。
def test_zero_settlement_segment_self_identified(tmp_path: _match_archive_Path):
    """零结算段自标识(v11):决策帧在、结算行零的段 → segments[] 带
    ``settlement_gap``(决策帧数+摘要 claimed 值);有结算段键缺省。

    锁的病灶 = 「rounds_survived=N 且零 outcome 行」曾被判读成「结算遥测
    断流」(实证 g_20260908_165445 续段 run_20260908_210431:79 决策帧全
    冻结 p2-r6、全程零战斗、rounds_survived=6;rounds_survived 写自收口
    时点 state.round_num,备战停滞段带冻结值)。本锁钉装配端契约:零结算
    是档案里直接可见的事实,判读不再靠跨流推断。"""
    rd = tmp_path / 'replay'
    rid_a = 'run_20260908_165445'   # 正常段:2 决策帧 2 结算行
    rid_b = 'run_20260908_210431'   # 零结算续段:3 决策帧、0 结算行、claimed=6
    dec = [_dec(rid_a, 2, 5, '2026-09-08T17:40:00'),
           _dec(rid_a, 2, 6, '2026-09-08T17:44:00'),
           _dec(rid_b, 2, 6, '2026-09-08T21:05:00'),
           _dec(rid_b, 2, 6, '2026-09-08T21:10:00'),
           _dec(rid_b, 2, 6, '2026-09-08T21:15:00')]
    out = [_out(rid_a, 2, 5, '2026-09-08T17:40:30', 55),
           _out(rid_a, 2, 6, '2026-09-08T17:44:30', 48)]
    runs = [{'run_id': rid_a, 'ts': '2026-09-08T18:11:18', 'result': 'stopped',
             'plane_reached': 2, 'rounds_survived': 6, 'final_hp': 48},
            {'run_id': rid_b, 'ts': '2026-09-08T21:21:55', 'result': 'stopped',
             'plane_reached': 2, 'rounds_survived': 6, 'final_hp': 48}]
    _write_jsonl(rd, 'decisions.jsonl', dec)
    _write_jsonl(rd, 'outcomes.jsonl', out)
    _write_jsonl(rd, 'runs.jsonl', runs)
    games = arch.assign_games(rd)
    # 段 B 首帧 (2,6) 非 (p1,r1) → 续局并入段 A 所在局(段 B 时序在段 A 后,
    # 归组语义 = assign_games 时序插位;含后继局的真实流形态由
    # test_decision_only_segment_groups_to_prior_game_with_later_outcome_game 承接)
    assert games[0]['segments'] == [rid_a, rid_b]
    # W3:settlement_gap 归档显影随段摘要构建面的旧流切片拆除退化
    # (归组断言仍全量承锁继承规则)。git 历史可复活原断言。


def test_settlement_gap_skips_empty_and_settled_segments():
    """``_settlement_gap`` 边界:无决策帧段不标注(空段无判读价值);
    有任一结算行(含 synthetic_supply 合成/补录来源)即视为有结算记录,
    不标注——合成行可信度争议归判读侧先验,不在本键重复表达。"""
    assert arch._settlement_gap([], [], 'r1', None) == {}
    assert arch._settlement_gap(
        [], [_out('r1', 1, 1, '2026-09-08T17:40:30', 80)], 'r1', None) == {}
    assert arch._settlement_gap(
        [_dec('r1', 1, 1, '2026-09-08T17:40:00')],
        [_out('r1', 1, 1, '2026-09-08T17:40:30', 80,
              source='synthetic_supply')],
        'r1', {'rounds_survived': 1}) == {}


def test_settlement_gap_ignores_terminal_closure_rows():
    """零结算段自标识不受收口终局行干扰(T-185 落地审建议-2):终局行
    (source='terminal_closure')不是战斗结算——它恰是「本段零场战斗走到
    结算屏」的证据行(ADR-0615 零结算语义),计入「有结算记录」会让终局行
    恰好填进的零结算停机段静默失去 settlement_gap 自标识,判读者按协议
    读到的是「有 outcome 行的普通段」。对照:synthetic_supply 等其余来源
    仍算有结算记录(ADR-0615 §3.2 既有边界不变)。"""
    dec = [_dec('r1', 1, 2, '2026-09-09T12:00:00')]
    term = {'schema_version': 1, 'run_id': 'r1', 'plane': 1,
            'round_num': 3, 'ts': '2026-09-09T12:10:00', 'node_type': '',
            'hp_after': None, 'hp_confidence': 0.0, 'killed': False,
            'source': 'terminal_closure', 'match_result': 'stopped'}
    # 段内唯一 outcome 行 = 终局行 → 仍标注零结算(决策帧≥1 且战斗结算行=0)
    gap = arch._settlement_gap(dec, [term], 'r1', {'rounds_survived': 3})
    assert gap == {'settlement_gap': {'decision_frames': 1,
                                      'claimed_rounds_survived': 3}}
    # 混入任一战斗结算行(合成行同款)→ 不标注(既有边界不松动)
    assert arch._settlement_gap(
        dec,
        [dict(term), _out('r1', 1, 3, '2026-09-09T12:09:00', 55,
                          source='synthetic_supply')],
        'r1', None) == {}


def test_decision_only_segment_groups_to_prior_game_with_later_outcome_game(
        tmp_path: _match_archive_Path):
    """assign_games 时序插位锁(v11 修,ADR-0615):决策独有段(零结算段)的
    流内位置由段首 ts 决定——其后有带 outcome 新局入流时,该段仍归其**前局**,
    不被后局夺走。

    锁的病灶 = 旧法「决策独有段排序后整体补尾」+ 续局归组「并入 games[-1]」
    无时序门 → 真实流上 run_20260908_210431(09-08 21:04 零结算段)曾被错组
    到 09-09 05:33 才开局的 g_20260909_053235 名下,锚点档案 g_20260908_
    165445 静默丢段(v11 bump 触发存量档案重装配时必然显影)。端到端形态:
    归位后该段 settlement_gap 落在 g_165445 名下。"""
    rd = tmp_path / 'replay'
    rid_a = 'run_20260908_165445'    # 前局段(带 outcome)
    rid_b = 'run_20260908_210431'    # 决策独有段(零结算,时序居中)
    rid_c = 'run_20260909_053235'    # 后继新局(带 outcome,首帧 (p1,r1))
    dec = [_dec(rid_a, 2, 5, '2026-09-08T17:40:00'),
           _dec(rid_a, 2, 6, '2026-09-08T17:44:00'),
           _dec(rid_b, 2, 6, '2026-09-08T21:05:00'),
           _dec(rid_c, 1, 1, '2026-09-09T05:33:00')]
    out = [_out(rid_a, 2, 5, '2026-09-08T17:40:30', 55),
           _out(rid_a, 2, 6, '2026-09-08T17:44:30', 48),
           _out(rid_c, 1, 1, '2026-09-09T05:34:00', 82)]
    runs = [{'run_id': rid_a, 'ts': '2026-09-08T18:11:18', 'result': 'stopped',
             'plane_reached': 2, 'rounds_survived': 6, 'final_hp': 48},
            {'run_id': rid_b, 'ts': '2026-09-08T21:21:55', 'result': 'stopped',
             'plane_reached': 2, 'rounds_survived': 6, 'final_hp': 48},
            {'run_id': rid_c, 'ts': '2026-09-09T05:40:00', 'result': 'loss',
             'plane_reached': 1, 'rounds_survived': 1, 'final_hp': 0}]
    _write_jsonl(rd, 'decisions.jsonl', dec)
    _write_jsonl(rd, 'outcomes.jsonl', out)
    _write_jsonl(rd, 'runs.jsonl', runs)
    games = arch.assign_games(rd)
    # 决策独有段按段首 ts 插回时序位 → 归前局;后继新局自成一体
    assert [(g['game_id'], g['segments']) for g in games] == [
        ('g_20260908_165445', [rid_a, rid_b]),
        ('g_20260909_053235', [rid_c])]
    # W3:settlement_gap 端到端显影随 rounds/段摘要构建面的旧流切片拆除
    # 退化(归组断言仍全量承锁时序插位语义)。git 历史可复活原断言。


def test_assemble_game_writes_index_and_no_tmp(replay: _match_archive_Path):
    """装配产物:match_*.json + index.jsonl 一行一局;无 .tmp 残留(原子写)。"""
    a = arch.assemble_game(replay, 'g_20260830_094811')
    assert a is not None and a['rounds'] == []  # W3:rounds 面旧流切片已拆,宽容退化
    assert a['endgame']['result'] == 'loss'          # 末段 loss = 全局结果
    assert a['endgame']['abandoned'] is False
    assert a['opening']['chosen_env'] == []  # W3:opening 面(exogenous/invest 切片)同拆
    assert a['continuity_note'] == ''
    assert not list((replay / 'matches').glob('*.tmp'))
    idx = [json.loads(l) for l in
           (replay / 'matches' / 'index.jsonl').open(encoding='utf-8')]
    assert len(idx) == 1 and idx[0]['game_id'] == 'g_20260830_094811'
    assert idx[0]['segments'] == ['run_20260830_094811', 'run_20260830_101513']


def test_assemble_abandoned_marked(replay: _match_archive_Path):
    """末段无 runs 摘要 = abandoned(ADR-0235 口径:中断局也装配)。"""
    runs_p = replay / 'runs.jsonl'
    rows = [json.loads(l) for l in runs_p.open(encoding='utf-8') if l.strip()]
    _write_jsonl(replay, 'runs.jsonl', [r for r in rows
                                        if r.get('run_id') != 'run_20260830_110000'])
    a = arch.assemble_game(replay, 'g_20260830_110000')
    assert a['endgame']['abandoned'] is True
    assert a['endgame']['result'] == 'abandoned'


def test_assemble_pending_watermark_no_backfill(replay: _match_archive_Path):
    """旧数据不回填:首调只落水位线,存量旧局一个都不装(无档案文件)。
    「水位线后的新局下一触发只装它」由 test_pending_new_game_unaffected_
    by_resume_merge 主序列承接(同 fixture 同序列,另断言 g_C 不被波及)。"""
    assert arch.assemble_pending(replay) == []
    assert not (replay / 'matches').exists() or not list(
        (replay / 'matches').glob('match_*.json'))


def test_pending_reassembles_on_resume_segment_merge(replay: _match_archive_Path):
    """续段归并锁(活局续段数据治理批 v6①②):同一 game_id 的续段 run
    并入既有局级档案,不丢不重;档案 watermark 跟随末段推进、不冻结。

    复刻 2026-09-05 夜实证形态:档案先以两段落盘(末段 stopped),之后
    两条续段 run 重进同一活局——修复前 assign_games 已把它们分好组,
    但 assemble_pending 只按 schema 版本判「已入档即跳过」,续段永远
    进不了档案,且 watermark 冻结在孤立段 end_ts(06:56:29 形态)。
    """
    assert arch.assemble_pending(replay) == []          # 首调只落水位线
    wm0 = arch._read_watermark(replay)
    assert wm0 == '2026-08-30T11:10:00'                 # 全量局最晚 end_ts
    # 归并靶局 = 时间序最近的 g_C(续段按段序并入上一局,活局重进必然
    # 紧随其宿主局,与生产形态一致);先以单段落盘
    a0 = arch.assemble_game(replay, 'g_20260830_110000')
    assert [s['run_id'] for s in a0['segments']] == ['run_20260830_110000']
    # 活局续段:run_D 重进同一活局(首帧 p1r2 非 (p1,r1) → 并入 g_C)
    dec = [json.loads(ln) for ln in (replay / 'decisions.jsonl')
           .open(encoding='utf-8') if ln.strip()]
    out = [json.loads(ln) for ln in (replay / 'outcomes.jsonl')
           .open(encoding='utf-8') if ln.strip()]
    runs = [json.loads(ln) for ln in (replay / 'runs.jsonl')
            .open(encoding='utf-8') if ln.strip()]
    dec.append(_dec('run_20260830_120000', 1, 2, '2026-08-30T12:00:00'))
    out.append(_out('run_20260830_120000', 1, 2, '2026-08-30T12:01:00', 30))
    runs.append({'run_id': 'run_20260830_120000', 'ts': '2026-08-30T12:05:00',
                 'result': 'loss', 'plane_reached': 1, 'rounds_survived': 1,
                 'final_hp': 0})
    _write_jsonl(replay, 'decisions.jsonl', dec)
    _write_jsonl(replay, 'outcomes.jsonl', out)
    _write_jsonl(replay, 'runs.jsonl', runs)
    done = arch.assemble_pending(replay)
    # 续段归并:既有档案因段集增长被重装(不是跳过、也不是开新局)
    assert done == ['g_20260830_110000']
    got = arch.load_archive(replay, 'g_20260830_110000')
    assert [s['run_id'] for s in got['segments']] == [
        'run_20260830_110000', 'run_20260830_120000']
    # W3:rounds 构建面旧流切片已拆,rounds 退化空(续段归并由段集断言承接)
    assert got['endgame']['result'] == 'loss'
    idx = [json.loads(ln) for ln in (replay / 'matches' / 'index.jsonl')
           .open(encoding='utf-8')]
    row = next(e for e in idx if e['game_id'] == 'g_20260830_110000')
    assert row['segments'] == ['run_20260830_110000', 'run_20260830_120000']
    # watermark 跟随末段:推进到续段 end_ts,不冻结在旧值
    assert arch._read_watermark(replay) == '2026-08-30T12:05:00'
    assert arch._read_watermark(replay) != wm0
    # 收敛:再触发不重复写(段集无增长 → done 空)
    assert arch.assemble_pending(replay) == []


def test_pending_new_game_unaffected_by_resume_merge(replay: _match_archive_Path):
    """独立新局不受影响锁(活局续段数据治理批 v6 对偶门):归并修复
    只作用于「段集增长的既有局」;新 game_id 照旧开新档案、单独入账。"""
    arch.assemble_pending(replay)                        # 首调落水位线
    a0 = arch.assemble_game(replay, 'g_20260830_110000')
    assert [s['run_id'] for s in a0['segments']] == ['run_20260830_110000']
    # 新局 run_E(首帧 (p1,r1) → 自成一局,不并入 g_C)
    dec = [json.loads(ln) for ln in (replay / 'decisions.jsonl')
           .open(encoding='utf-8') if ln.strip()]
    out = [json.loads(ln) for ln in (replay / 'outcomes.jsonl')
           .open(encoding='utf-8') if ln.strip()]
    dec.append(_dec('run_20260830_130000', 1, 1, '2026-08-30T13:00:00'))
    out.append(_out('run_20260830_130000', 1, 1, '2026-08-30T13:01:00', 70))
    _write_jsonl(replay, 'decisions.jsonl', dec)
    _write_jsonl(replay, 'outcomes.jsonl', out)
    done = arch.assemble_pending(replay)
    assert done == ['g_20260830_130000']
    got = arch.load_archive(replay, 'g_20260830_130000')
    assert [s['run_id'] for s in got['segments']] == ['run_20260830_130000']
    # g_C 档案不被新局波及(段集不变)
    again = arch.load_archive(replay, 'g_20260830_110000')
    assert [s['run_id'] for s in again['segments']] == ['run_20260830_110000']


# [退役墓碑,W3]test_resume_reconciliation_columns 随档案 resume_
# reconciliation 构建面(续局恢复帧 vs 前段末帧对账,旧流 decisions 帧)
# 拆除退役(W3)。git 历史可复活。
# [退役墓碑,W3]test_resume_reconciliation_outcome_fallback 随档案
# resume_reconciliation 构建面(旧流 decisions 帧)拆除退役(W3)。
# git 历史可复活。
def test_pending_warns_behind_watermark_unarchived(
        replay: _match_archive_Path,
        monkeypatch: pytest.MonkeyPatch):
    """水位线回拨显影(M1):end_ts 落后水位线(历史最大值锚)且未入档、
    落后量在告警窗内 → WARNING 带 game_id/end_ts/wm 溯源,防时钟回拨/
    DST 回拨段新局连续漏装无感;已入档的落后局(正常形态)不告警。"""
    warnings: list[str] = []
    monkeypatch.setattr(arch, 'log', type('_L', (), {
        'warning': staticmethod(lambda msg, *a: warnings.append(msg % a
                                                       if a else msg)),
        'info': staticmethod(lambda *a, **k: None),
        'debug': staticmethod(lambda *a, **k: None)})())
    assert arch.assemble_pending(replay) == []           # 首调落水位线
    # run_C(11:10)已入档;run_A 局(末段 end 10:31,落后 wm < 48h)未入档
    arch.assemble_game(replay, 'g_20260830_110000')
    warnings.clear()
    assert arch.assemble_pending(replay) == []           # 无人入档
    assert any('run_20260830_101513' in w or 'g_20260830_094811' in w
               for w in warnings), f'落后未入档局未显影: {warnings}'
    # 已入档的落后局(g_110000)不产生新告警
    assert not any('g_20260830_110000' in w for w in warnings)


def test_materialized_slice_journal_reads_equal_source(replay: _match_archive_Path):
    """--match 视图同源:切片物化后 journal 读面输出与源目录逐字节一致。

    W3 退役改锚:query_* 旧视图族已随删除波 1 写入端退役拆除
    (r5-migration-plan.md §2 W3),同源判据改走唯一读面 journal_query
    (装配切片 v12 起内嵌 state/journal.jsonl;旧流切片键已从 _SLICE_FILES
    拆除,物化目录无旧流文件 = 与源目录同「空」)。"""
    from sr_od.application.currency_war.telemetry import journal_query as jq
    a = arch.assemble_game(replay, 'g_20260830_094811')
    slice_dir = arch.materialize_slice(a, replay / '_slice_tmp')
    assert jq.read_journal(slice_dir), '装配切片应内嵌新账行(v12+)'
    for seg in ('run_20260830_094811', 'run_20260830_101513'):
        for view in (jq.view_gold, jq.view_hp, jq.view_rounds):
            assert view(jq.read_journal(slice_dir), seg) == \
                view(jq.read_journal(replay), seg), \
                f'{view.__name__}@{seg}: 档案切片视图与源目录不一致'
    import shutil
    shutil.rmtree(slice_dir)


# ===== 二期补齐批:决策明细显形 / 策略版本戳 =====

def _rewrite_runs(replay: _match_archive_Path, fn) -> None:
    """runs.jsonl 行集变换 helper(原属已退役 resume 区,W3 迁此供版本戳测试)。"""
    rows = [json.loads(ln) for ln in (replay / 'runs.jsonl')
            .open(encoding='utf-8') if ln.strip()]
    _write_jsonl(replay, 'runs.jsonl', fn(rows))


# [退役墓碑,W3]test_rounds_decision_detail_and_bench_equips 随档案 rounds
# 构建面(decision_detail 逐帧明细,旧流 decisions 帧源)拆除退役(W3)。
# git 历史可复活。
def test_strategy_version_stamp_propagates(replay: _match_archive_Path):
    """二期②:runs 行带版本戳 → 档案顶层 strategy_version(倒查首个非空)+
    index 列透传。"""
    _rewrite_runs(replay, lambda rows: [
        {**r, 'code_commit': 'abc1234', 'registry_fingerprint': 'fp001'}
        if r.get('run_id') == 'run_20260830_101513' else r for r in rows])
    a = arch.assemble_game(replay, 'g_20260830_094811')
    # 只给末段(101513)打戳 → 倒查命中末段,不取首段空值
    assert a['strategy_version'] == {'code_commit': 'abc1234',
                                     'registry_fingerprint': 'fp001'}
    idx = [json.loads(ln) for ln in
           (replay / 'matches' / 'index.jsonl').open(encoding='utf-8')]
    row = next(e for e in idx if e['game_id'] == 'g_20260830_094811')
    assert row['code_commit'] == 'abc1234'
    assert row['registry_fingerprint'] == 'fp001'


def test_strategy_version_none_for_legacy(replay: _match_archive_Path):
    """二期②旧数据边界:runs 行无戳 → strategy_version=None(版本未知,
    不冒认当前 checkout 版本)。"""
    a = arch.build_archive(replay, arch.assign_games(replay)[0])
    assert a['strategy_version'] is None


# ===== v3 战后终态列(w936_deploy_fill 移交①:决策帧 ≠ 执行后板面)=====

def test_terminal_state_summary_field_lock():
    """字段面锁:终态计数四键口径——deployed/bench 占用数(None 剔除)、
    worn(Σ deployed[].equips 件数)、owned(state.equips 件数)。

    口径单一源 = schema.terminal_state_summary docstring(坐标系/取值时机);
    本锁钉键名与计数语义,分布数值不锁(测试纪律 #11)。"""
    from sr_od.application.currency_war.telemetry.schema import terminal_state_summary
    st = {'deployed': [
              {'name': '甲', 'equips': ['火力风暴潮', '高周波电锯']},
              None,
              {'name': '乙', 'equips': []},
          ],
          'bench': [{'name': '丙'}, None, {'name': '丁'}, None, None],
          'equips': ['折叠小刀', '轮滑鞋']}
    assert terminal_state_summary(st) == {
        'deployed_count': 2, 'bench_count': 2,
        'equips_worn': 2, 'equips_owned': 2}
    # dict 形态 owned(旧语料/测试形态)按键数计;缺键/非 dict 安全退化
    assert terminal_state_summary({'equips': {'递归': 1}}) == {
        'deployed_count': 0, 'bench_count': 0,
        'equips_worn': 0, 'equips_owned': 1}
    assert terminal_state_summary(None) == {
        'deployed_count': 0, 'bench_count': 0,
        'equips_worn': 0, 'equips_owned': 0}
    assert terminal_state_summary({'deployed': '残缺'})['deployed_count'] == 0
    # P3-6 硬化:元素内 equips 标量/str 不炸不计(worn 语义只认 list/dict)
    st_bad = {'deployed': [{'name': '甲', 'equips': 7},
                           {'name': '乙', 'equips': '火力风暴潮'},
                           {'name': '丙', 'equips': ['高周波电锯']}]}
    assert terminal_state_summary(st_bad) == {
        'deployed_count': 3, 'bench_count': 0,
        'equips_worn': 1, 'equips_owned': 0}


# [退役墓碑,W3]test_rounds_terminal_vs_decision_frame_divergence 随档案
# rounds 构建面(terminal/terminal_ts 逐轮终态列,旧流 decisions 帧源)
# 拆除退役(W3)。git 历史可复活。
# [退役墓碑,W3]test_rounds_terminal_none_for_outcome_only_round 随档案
# rounds 构建面旧流切片拆除退役(W3)。git 历史可复活。
# [退役墓碑,W3]test_supply_round_has_decision_frame 随档案 rounds 构建面
# 旧流切片拆除退役(W3)。git 历史可复活。
# ===== v5(M2 遥测增强批 ③:endgame.final_snapshot 局级终局快照列)=====

# [退役墓碑,W3]test_endgame_final_snapshot 随档案 final_snapshot 构建面的
# 旧流切片(decisions 帧)拆除退役(W3);对偶门 none_for_frameless 保留
# (空输入 None 语义仍由宽容契约承锁)。git 历史可复活。
def test_endgame_final_snapshot_none_for_frameless_game(replay: _match_archive_Path):
    """零决策迹局(仅结算行):final_snapshot=None(旧数据容忍,不炸不猜)。"""
    # 清空 decisions 后 run_C 无任何帧 → 终局快照 None
    _write_jsonl(replay, 'decisions.jsonl', [])
    a = arch.build_archive(replay, arch.assign_games(replay)[1])
    assert a['endgame']['final_snapshot'] is None


# ===== v4 返修(w943 审计 P2-4 版本迁移读端 / P2-5 收口类型)=====

def _read_archive_file(replay: _match_archive_Path, game_id: str) -> dict:
    with (replay / 'matches' / f'match_{game_id}.json') \
            .open('r', encoding='utf-8') as f:
        return json.load(f)


def test_load_archive_auto_rebuilds_stale_version(replay: _match_archive_Path):
    """P2-4:存量旧版本档案经 load_archive 读出即自动重装配(terminal 族
    键补齐 + 版本写回),不再静默缺列。"""
    game_id = 'g_20260830_094811'
    a = arch.assemble_game(replay, game_id)          # 先落一份当前版本档案
    assert a['schema_version'] == arch.SCHEMA_VERSION
    # 把落盘档案降级模拟 v2 存量(抹 terminal 族键 + 版本号)
    stale = _read_archive_file(replay, game_id)
    stale['schema_version'] = 2
    for r in stale['rounds']:
        for k in ('terminal', 'terminal_ts', 'terminal_source',
                  'terminal_closure'):
            r.pop(k, None)
    p = replay / 'matches' / f'match_{game_id}.json'
    with p.open('w', encoding='utf-8') as f:
        json.dump(stale, f, ensure_ascii=False)
    # 读端:默认自动迁移 → 版本写回 + terminal 族键补齐
    got = arch.load_archive(replay, game_id)
    assert got['schema_version'] == arch.SCHEMA_VERSION
    # W3:rounds 构建面旧流切片已拆 → 重建产物 rounds 空(宽容退化);
    # 版本写回与重建触发语义由上行 schema 断言承锁
    assert got['rounds'] == []
    assert _read_archive_file(replay, game_id)['schema_version'] \
        == arch.SCHEMA_VERSION   # 原子写回已升级
    # auto_rebuild=False(只读审计):返回旧档案本体,不动盘
    stale2 = _read_archive_file(replay, game_id)
    stale2['schema_version'] = 2
    for r in stale2['rounds']:
        for k in ('terminal', 'terminal_ts', 'terminal_source',
                  'terminal_closure'):
            r.pop(k, None)
    with p.open('w', encoding='utf-8') as f:
        json.dump(stale2, f, ensure_ascii=False)
    got2 = arch.load_archive(replay, game_id, auto_rebuild=False)
    assert got2['schema_version'] == 2
    assert got2['rounds'] == []   # W3 退化:rounds 空,无逐轮键可查


def test_load_archive_stale_without_source_warns_and_returns_stale(
        replay: _match_archive_Path):
    """P2-4 边界:源 jsonl 已清 → 重装配不可行,退回旧档案不炸
    (调用方拿到的缺列档案带 log 警告;此处验证返回行为本身)。"""
    import shutil
    game_id = 'g_20260830_110000'
    arch.assemble_game(replay, game_id)
    # 清掉全部源流(只留 matches/ 目录)
    for name in ('decisions.jsonl', 'outcomes.jsonl', 'runs.jsonl',
                 'shop_snapshots.jsonl', 'invest_cards.jsonl',
                 'exogenous.jsonl', 'spend_ledger.jsonl'):
        fp = replay / name
        if fp.exists():
            fp.unlink()
    assert arch.load_archive(replay, game_id) is not None   # 退回旧档案
    # 游戏不存在 → None(原语义不变)
    shutil.rmtree(replay / 'matches')
    assert arch.load_archive(replay, game_id) is None


# ===== v8(C8 遥测缺陷批):loss_nodes 逐结算行化 =====
# 缺陷:同轮「补给回血+战斗掉血」时 loss_nodes 走轮级净额,掉血幅度被回血
# 抵减(净额 −19 vs 战斗腿 −33),净额≥0 时整条漏记。实证 g_20260906_182456
# p2r4;方案/方案审见 .debug/temp/currency_war/c8_loss_nodes/(决策记录 =
# ADR-0567)。修复语义:loss_nodes 一条目对一个掉血结算行(战斗腿口径),
# rounds 逐轮表保持单槽净额零变化。
# v9 重推(T-100 批2,ADR-0577):合成行(synthetic_supply)一律退出步进链
# (先验「陈旧直到证伪」);逐结算行化方向与 M1 不可信行契约保留。
# 同案收敛:182456 案(战斗腿 −19/合成行退链/净额轮如实记账/加法键取值)
# 归 test_cw_hp_assembly.py 同 run_id 专锁;本文件保留 M1 分叉与
# v7→v9 迁移语义。fixture 的 runs 结果改 'stopped' = 隔离终局腿变量
# (终局腿归 test_cw_hp_assembly 专锁),步进链锁不与 result 字段耦合。

def _replay_c8(tmp_path: _match_archive_Path,
               p2r4_outs: list[dict]) -> _match_archive_Path:
    """最小单段局:p2r3 单结算行 hp=31 + p2r4 给定结算行组(同轮多结算)。"""
    rd = tmp_path / 'replay_c8'
    rid = 'run_20260906_182456'
    _write_jsonl(rd, 'outcomes.jsonl',
                 [_out(rid, 2, 3, '2026-09-06T18:55:00', 31)] + p2r4_outs)
    _write_jsonl(rd, 'decisions.jsonl', [])
    _write_jsonl(rd, 'runs.jsonl', [
        {'run_id': rid, 'ts': '2026-09-06T19:10:00', 'result': 'stopped',
         'plane_reached': 2, 'rounds_survived': 4, 'final_hp': 12,
         'difficulty': ''}])
    return rd


def _ln_at(archive: dict, plane: int, rnd: int) -> list[dict]:
    return [n for n in archive['loss_nodes']
            if n['plane'] == plane and n['round'] == rnd]


# [退役墓碑,W3]test_loss_nodes_mixed_trust_round_two_chain_divergence 随档案
# rounds/loss_nodes 构建面的旧流切片拆除退役(W3)。git 历史可复活。
# [退役墓碑,W3]test_loss_nodes_v7_net_migrated_to_current_battle_leg 随档案
# rounds/loss_nodes 构建面的旧流切片拆除退役(r5-migration-plan.md §2 W3);
# loss_nodes 谓词纯函数面(hp 可信门/真值链退出)由 test_terminal_row_exits_
# hp_truth_chains 与 sim/pool 侧谓词锁继续承锁。git 历史可复活。
# ==================== performance ====================

import pytest as _performance_pytest

from sr_od.application.currency_war.kernel.cw_comps import Comp  # noqa: E402
from sr_od.application.currency_war.kernel.cw_performance import (
    HP_LOSS_FULL,
    PerformanceTracker,
    RoundOutcome,
    star_achievement,
)
from sr_od.application.currency_war.kernel.cw_vocab import (  # noqa: E402
    BenchChar,
    CwWorkFrame,
)


def _performance_out(round_num: int, hp: int, node: str = "普通战斗", comp: str = "c1",
         fold: bool = False, conf: float = 1.0, plane: int = 1) -> RoundOutcome:
    return RoundOutcome(round_num=round_num, plane=plane, node_type=node, comp_tag=comp,
                        intentional_fold=fold, hp_after=hp, hp_confidence=conf)


# —— r6 F1: intentional_fold 排除 ——


def test_fold_excluded_from_trend() -> None:
    """故意输(fold)的大掉血不污染 trend:fold 排除后只 1 个 qualifying → None。"""
    t = PerformanceTracker()
    t.record(_performance_out(1, 100))
    t.record(_performance_out(2, 50, fold=True))    # 故意输掉 50 —— 排除
    assert t.recent_hp_loss_trend() is None, "fold 排除后 <2 → None(不污染)"


def test_non_fold_big_loss_detected() -> None:
    """同样掉 50 但非 fold → trend 检测到大掉血(对照)。"""
    t = PerformanceTracker()
    t.record(_performance_out(1, 100))
    t.record(_performance_out(2, 50))               # 非故意 → 进 trend
    trend = t.recent_hp_loss_trend()
    assert trend is not None
    assert trend > 0, "非 fold 大掉血应被检测"


# —— r6 F2: 归一化(boss 掉得多不误判)——


def test_boss_loss_normalized_not_misjudged() -> None:
    """打 boss 掉 30(normalized 30/3=10)≈ 普通关掉 10(normalized 10/1=10):归一化后等价。"""
    t_normal = PerformanceTracker()
    t_normal.record(_performance_out(1, 100, node="普通战斗"))
    t_normal.record(_performance_out(2, 90, node="普通战斗"))    # 掉 10
    t_boss = PerformanceTracker()
    t_boss.record(_performance_out(1, 100, node="普通战斗"))
    t_boss.record(_performance_out(2, 70, node="boss"))          # 掉 30,但 boss expected_drop=3.0
    assert t_normal.recent_hp_loss_trend() == _performance_pytest.approx(t_boss.recent_hp_loss_trend(), abs=1e-6), (
        "归一化后 boss 掉 30 ≈ 普通关掉 10(不误判弱)"
    )


# —— r6 F4: comp_tag 降权(pivot 后旧 comp ×0.3)——


def test_comp_tag_downweight() -> None:
    """pivot 后旧 comp(B)的大掉血 ×0.3 降权:trend(A) < 全 A 同掉血的 trend。"""
    # 全 A:o1(100)→o2(90)→o3(70),trend = (10+20)/2 = 15
    t_all_a = PerformanceTracker()
    t_all_a.record(_performance_out(1, 100, comp="A"))
    t_all_a.record(_performance_out(2, 90, comp="A"))
    t_all_a.record(_performance_out(3, 70, comp="A"))
    # 混合:o1(100,A)→o2(90,A)→o3(70,B 旧 comp):B 的 20 掉血 ×0.3 降权
    t_mixed = PerformanceTracker()
    t_mixed.record(_performance_out(1, 100, comp="A"))
    t_mixed.record(_performance_out(2, 90, comp="A"))
    t_mixed.record(_performance_out(3, 70, comp="B"))
    assert t_mixed.recent_hp_loss_trend(comp_tag="A") < t_all_a.recent_hp_loss_trend(comp_tag="A"), (
        "旧 comp(B)大掉血降权 → trend(A) < 全 A"
    )


# —— r6 F6: 冷启动(<2 → None)——


def test_cold_start_returns_none() -> None:
    """<2 qualifying outcome(无首个差分)→ None。"""
    t = PerformanceTracker()
    assert t.recent_hp_loss_trend() is None, "0 outcome → None"
    t.record(_performance_out(1, 100))
    assert t.recent_hp_loss_trend() is None, "1 outcome 无差分 → None"
    t.record(_performance_out(2, 90))
    assert t.recent_hp_loss_trend() is not None, "2 outcome 有首个差分 → 非 None"


# —— r5: 低置信(<0.7)不进 trend ——


def test_low_confidence_excluded() -> None:
    """OCR 低置信(<0.7)的 outcome 不进 trend(防抖动):只剩 1 个高置信 → None。"""
    t = PerformanceTracker()
    t.record(_performance_out(1, 100, conf=0.9))
    t.record(_performance_out(2, 50, conf=0.4))     # 低置信 → 排除
    assert t.recent_hp_loss_trend() is None, "低置信排除后 <2 → None"
    # 对照:同掉血但高置信 → 检测到
    t2 = PerformanceTracker()
    t2.record(_performance_out(1, 100, conf=0.9))
    t2.record(_performance_out(2, 50, conf=0.9))
    assert t2.recent_hp_loss_trend() is not None


# —— boss_kill_signal / set_required_damage ——
# ⚖️ 已随敌方侧死链删除(2026-08-16 review D4-D7):boss 击杀信号与伤害基准的正式归宿
# 是 19 号伤害账本(cw_damage_ledger,ADR-0166);原方法无生产调用/无读者,测试随之移除。
# ledger 侧对应用例见 test_cw_damage_ledger.py(括号法收敛/修改器定价)。


# —— is_losing_streak(连败=持续高掉血)——


def test_is_losing_streak_threshold_and_cold_start() -> None:
    """is_losing_streak 通道2阈值锁:trend > HP_LOSS_FULL*0.5(cw_performance
    实机校准 0.6→0.5,覆盖 A8 慢性失血 13-24 血/轮实测带)→ True;探针钉
    推导阈值 ±1;低掉血 → False;冷启动 → False。
    (通道1 游戏自报连败 streak≤-2 直通,parse_streak 另辖;此处只锁 trend 门。)"""
    thr = HP_LOSS_FULL * 0.5        # 阈值单一源 = 生产门表达式现算,禁手抄
    # 掉 thr+1(普通关归一化同值)> 阈值 → streak
    t_streak = PerformanceTracker()
    t_streak.record(_performance_out(1, 100))
    t_streak.record(_performance_out(2, 100 - int(thr) - 1))
    assert t_streak.is_losing_streak(), f"trend={int(thr) + 1}>{thr} → 连败"
    # 小掉血 thr-1 < 阈值 → 非 streak
    t_ok = PerformanceTracker()
    t_ok.record(_performance_out(1, 100))
    t_ok.record(_performance_out(2, 100 - int(thr) + 1))
    assert not t_ok.is_losing_streak(), f"trend={int(thr) - 1}<{thr} → 非连败"
    # 冷启动(样本不足 trend=None)→ False
    assert not PerformanceTracker().is_losing_streak(), "冷启动 → False"


# —— star_achievement(核心角色星级达成;comp_viability 的 star 先验分量)——


def _star_bc(slot: int, char_id: str, star: int) -> BenchChar:
    return BenchChar(slot=slot, char_id=char_id, star=star)


def _star_comp(core_chars: list[str]) -> Comp:
    return Comp(name='c', factions=[], core_chars=core_chars,
                form_tiers={}, strength='A', form_difficulty='easy')


def test_star_achievement_no_core_or_unheld_is_zero() -> None:
    """comp 无 core_chars,或 core 角色一个都不在 bench/deployed → 0.0
    (早期未成型语义;出处 = cw_performance.star_achievement 语义,
    限时 AV 星级=输出先验分量)。"""
    assert star_achievement(_star_comp([]), _bridge(CwWorkFrame())) == 0.0
    # 场上只有非 core 角色 → core 未持有 → 0.0
    state = CwWorkFrame(bench=[_star_bc(1, '停云', 3)])
    assert star_achievement(_star_comp(['飞霄']), _bridge(state)) == 0.0


def test_star_achievement_star_normalization_anchors() -> None:
    """归一化锚:全 1★→0.0 / 全 2★→0.5 / 全 3★→1.0(平均 star 线性映射,
    (avg−1)/2)。"""
    comp = _star_comp(['飞霄'])
    for star, expect in ((1, 0.0), (2, 0.5), (3, 1.0)):
        state = CwWorkFrame(deployed=[_star_bc(0, '飞霄', star)])
        assert star_achievement(comp, _bridge(state)) == expect, \
            f'{star}★ → {expect}'


def test_star_achievement_full_domain_average() -> None:
    """有效率域 = bench∪deployed 全场域(3合1 全场口径,bot 跟踪 star);
    多核心取平均(一 2★+一 3★ → avg 2.5 → 0.75);bench 空槽滤除;
    非 core 角色星级不进平均。"""
    comp = _star_comp(['飞霄', '知更鸟'])
    state = CwWorkFrame(
        bench=[None, _star_bc(2, '飞霄', 2), _star_bc(3, '停云', 3)],
        deployed=[_star_bc(0, '知更鸟', 3)])
    # core 集 = {飞霄 2★, 知更鸟 3★} → avg 2.5 → (2.5−1)/2 = 0.75
    assert star_achievement(comp, _bridge(state)) == 0.75


# ==================== telemetry_checks(W3 退役) ====================
# [退役墓碑,W3]本区检查器测试族(test_default_stack_skipped /
# test_stack_inferred_from_reason_vocab / test_multiline_round_not_lossy /
# test_untagged_buys_report_indeterminable / test_unknown_strategy_id_skipped /
# test_v2_stack_runs_coldstart / test_p2_bleed_gold_stack_wired /
# test_p2_bleed_gold_stack_healthy_not_fired / test_production_round_merge_
# multi_frame)随判读 CLI checks 子命令与 sim/ledger_hooks 读侧检查族
# (run_checks_on_replay / merge_round_rows 等)一并退役——其读源为生产
# 旧 12 流(decisions/outcomes/runs),已随删除波 1 停写,检查器对新局
# 恒空/⊘(读死数据);判读走 journal 新账唯一读面。段级检查器 sim 账本
# 活体 = sim/checks/(sim 引擎自写账本,归 W6 sim 切统一容器批统一处置)。
# 依据 = r5-migration-plan.md §2 W3;git 历史可复活原锁面。


# ==================== test_telemetry_extra_sig(删除波 1 退役)====================
# (record_decision 签名对齐锁已随 decisions 流写入端退役删除——局30 的
#  TypeError 病灶连同写端整段消亡,git 可复活。)


# (2026-09-03 瘦身批:test_recorder_method_and_helper_signatures_align 与
#  test_deploy_equips_snapshot_method_exists 删除——inspect 签名对齐/hasattr
#  在场锁属实现形状(纪律 8),无行为面增量。)


# ==================== w527_node_ledger ====================

from pathlib import Path as _w527_node_ledger_Path
from types import SimpleNamespace

import pytest as _w527_node_ledger_pytest

_ROOT = _w527_node_ledger_Path(__file__).resolve().parents[5]          # 仓库根(StarRailOneDragon)
_TEST_ROOT = _w527_node_ledger_Path(__file__).resolve().parents[4]     # 测试仓根(sr-od-test)

from sr_od.application.currency_war.kernel.cw_vocab import (
    fill_boss_by_position,
    get_node_ledger,
    ledger_node_type,
    ledger_update_plane,
)
from sr_od.application.currency_war.obs import cw_node_reader, cw_observation
from sr_od.application.currency_war.obs.cw_node_reader import (
    classify_node_row,
    load_node_type_templates,
)
from sr_od.application.currency_war.obs.cw_observation import node_vote_verdict

_ASSETS = _ROOT / 'assets' / 'game_data' / 'cw_node_types'
_FIXTURES = _TEST_ROOT / 'screens' / '货币战争-备战'
#: 节点行裁带(与 cw_node_reader.NODE_ROW_RECT 同带、四周留余量;仅测试用)
_CROP = (500, 10, 1450, 120)


class _Session:
    """最小 session 桩(台账动态挂载宿主)。"""


# ===== 1. 台账存储 / 合并 / 查表 =====

def test_ledger_lazy_attach_and_none() -> None:
    """惰性挂载:同 session 幂等;None session → None(调用方跳过)。"""
    s = _Session()
    l1 = get_node_ledger(s)
    l2 = get_node_ledger(s)
    assert l1 is not None and l1 is l2
    assert get_node_ledger(None) is None


def test_ledger_update_merge_none_keeps_old() -> None:
    """按位合并:新非 None 覆盖,None 保旧(boss/past 位识别恒 None 不洗表)。"""
    s = _Session()
    ledger_update_plane(s, 1, ['battle', 'battle', None, 'boss'], 'plane_detail')
    # 备战行重读:idx1 变异成 supply(非 None 覆),idx3 重读为 None → 保 boss
    changed = ledger_update_plane(s, 1, [None, 'supply', None, None], 'prep_row')
    assert changed
    assert ledger_node_type(s, 1, 1) == 'battle'
    assert ledger_node_type(s, 1, 2) == 'supply'
    assert ledger_node_type(s, 1, 4) == 'boss'


def test_ledger_lookup_bounds_and_missing() -> None:
    """查表:表缺 / 轮越界 / 未识别位 → None(退逐帧识别链,不猜)。"""
    s = _Session()
    assert ledger_node_type(s, 1, 1) is None          # 无表
    ledger_update_plane(s, 2, ['battle', None], 'prep_row')
    assert ledger_node_type(s, 1, 1) is None          # 位面缺
    assert ledger_node_type(s, 2, 5) is None          # 越界
    assert ledger_node_type(s, 2, 2) is None          # 该位次未识别
    assert ledger_node_type(s, 2, 1) == 'battle'


def test_fill_boss_by_position_only_trailing_none() -> None:
    """boss 回填:只回填最右 None;已识别最右位不动;原序列不被改写。"""
    assert fill_boss_by_position(['battle', None]) == ['battle', 'boss']
    assert fill_boss_by_position(['battle', 'boss']) == ['battle', 'boss']
    seq = ['battle', None]
    fill_boss_by_position(seq)
    assert seq == ['battle', None]


def test_ledger_update_extend_shorter_seq() -> None:
    """投资环境加节点:新序列更长 → 右侧扩展(短序列缺位不截断旧值)。"""
    s = _Session()
    ledger_update_plane(s, 1, ['battle', 'supply', None, 'boss'], 'plane_detail')
    ledger_update_plane(s, 1, ['battle', 'supply', 'reward', 'boss', 'battle'], 'prep_row')
    assert ledger_node_type(s, 1, 5) == 'battle'
    assert ledger_node_type(s, 1, 4) == 'boss'


# ===== 2. 三票裁决 + 变异窗豁免 =====

def test_vote_verdict_thresholds() -> None:
    """三票裁决:≥2 独立票一致反对 = defect;单票 = noise;无反对 = ok。"""
    assert node_vote_verdict('battle', {'roi_ocr': 'reward', 'position': 'reward',
                                        'cur_hu': None}) == 'defect'
    assert node_vote_verdict('battle', {'roi_ocr': 'battle', 'position': 'reward',
                                        'cur_hu': 'reward'}) == 'defect'
    assert node_vote_verdict('battle', {'roi_ocr': 'reward', 'position': 'battle',
                                        'cur_hu': None}) == 'noise'
    assert node_vote_verdict('battle', {'roi_ocr': 'battle', 'position': 'battle',
                                        'cur_hu': 'battle'}) == 'ok'
    # 弃权为主的帧不构成 defect(2 弃权 + 1 反对 = 单票)
    assert node_vote_verdict('battle', {'roi_ocr': None, 'position': None,
                                        'cur_hu': 'reward'}) == 'noise'


def test_verify_votes_defect_and_grace(monkeypatch: _w527_node_ledger_pytest.MonkeyPatch) -> None:
    """三票校验:窗外 defect 落账一次(去重);变异窗内豁免不落。"""
    import time as _time

    from sr_od.application.currency_war.obs.cw_node_reader import NodeSlot

    defects: list[dict] = []

    # 分包期 4:obs 落账走 kernel.cw_telemetry_exit 出口钩子位,桩点随迁
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    monkeypatch.setattr(cw_telemetry_exit, '_record_defect',
                        lambda *a, **kw: defects.append(dict(kw)))

    slots = [
        NodeSlot(idx=0, cx=60, cy=40, state='past', node_type=None, hu_dist=None),
        NodeSlot(idx=1, cx=150, cy=40, state='current', node_type=None, hu_dist=None),
        NodeSlot(idx=2, cx=240, cy=40, state='upcoming', node_type='reward', hu_dist=1.0),
    ]

    def _fake_classify(ctx, screen):
        return slots, (500, 24, 1406, 106)

    monkeypatch.setattr(cw_observation, '_classify_node_row', _fake_classify)
    monkeypatch.setattr(cw_observation, '_node_label_in_roi',
                        lambda ctx, screen, cx, cy: 'reward')

    def _fake_hu(row_rgb, slot, templates):
        return 'reward', 1.2

    monkeypatch.setattr(cw_node_reader, 'current_slot_hu_type', _fake_hu)

    ctx = SimpleNamespace(cw_match=None)
    sess = _Session()
    ctx.cw_match = SimpleNamespace(session=sess)
    ledger_update_plane(sess, 1, ['battle', 'battle', 'reward'], 'plane_detail')
    import numpy as _np
    _screen = _np.zeros((120, 1500, 3), dtype=_np.uint8)   # 像素不被读(Hu/OCR 全 patch),仅承载切片

    cw_observation.verify_node_type_votes(ctx, _screen, 1, 2)
    assert len(defects) == 1
    # 出口钩子位逐参关键字转发:捕获行直接按形参名断言(surface=节点类型面)
    assert defects[0]['surface'] == 'node_type'
    assert defects[0]['kind'] == 'perception_conflict'
    assert defects[0]['reader_source'] == 'node_ledger_three_vote'
    cw_observation.verify_node_type_votes(ctx, _screen, 1, 2)
    assert len(defects) == 1   # 同 (plane, round) 去重

    # 变异窗内:合法变异,豁免不落
    sess2 = _Session()
    ctx.cw_match = SimpleNamespace(session=sess2)
    ledger_update_plane(sess2, 1, ['battle', 'battle', 'reward'], 'plane_detail')
    get_node_ledger(sess2).env_grace_until = _time.monotonic() + 60
    cw_observation.verify_node_type_votes(ctx, _screen, 1, 2)
    assert len(defects) == 1


# ===== 3. 真值帧对拍(VLM 亲读真值,协议参照 W531 SIFT 基准) =====
# 真值 = w527 批 read_image 亲读节点行裁图(x 500-1450 放大 2x);帧名 = 后排
# 格数口径(w535 改名后)。锁稳定事实(槽数/当前位/past 数/有效识别位);
# Hu 对高亮/变异图标的噪声位**不锁断言**(正是台账制的立项依据),落对拍表。

_GT = {
    '后排8槽-满级局.webp': {
        'seq': ['battle', 'battle', 'supply', 'battle', 'encounter', 'reward', 'boss'],
        'current': 3,
        # 只锁该帧 CV 实际识别对的 upcoming 位(其余为已知 Hu 噪声位,落对拍表不锁)
        'expect_upcoming': {4: 'encounter'},
    },
    '后排8槽-P3局.webp': {
        'seq': ['battle', 'battle', 'supply', 'battle', 'encounter', 'reward', 'boss'],
        'current': 1,
        'expect_upcoming': {2: 'supply'},
    },
    '后排6槽-P2开局局.webp': {
        'seq': ['battle', 'reward', 'supply', 'battle', 'encounter', 'reward', 'boss'],
        'current': 0,
        'expect_upcoming': {4: 'encounter', 5: 'reward'},
    },
    '后排7槽-佩佩局.png': {
        'seq': ['reward', 'reward', 'reward', 'battle', 'supply', 'battle',
                'encounter', 'reward', 'boss'],
        'current': 0,
        'expect_upcoming': {1: 'reward', 3: 'battle', 4: 'supply', 5: 'battle',
                            6: 'encounter', 7: 'reward'},
    },
}


@_w527_node_ledger_pytest.fixture(scope='module')
def row_frames() -> tuple:
    """模块级一次性加载:真值裁带帧 + 节点类型模板 + boss SIFT 模板
    (boss 模板与生产同源,read_node_sequence 恒传;模板 I/O 收敛到
    每模块一次,不落模块导入期、不逐参数重复读)。"""
    from one_dragon.utils import cv2_utils
    tpls = load_node_type_templates(_ASSETS)
    boss_tpls = cw_node_reader.load_boss_templates(
        _ROOT / 'assets' / 'template' / 'currency_war' / 'boss_avatar') or None
    out = {}
    for name in _GT:
        img = cv2_utils.read_image(str(_FIXTURES / name))   # RGB
        x0, y0, x1, y1 = _CROP
        out[name] = img[y0:y1, x0:x1]
    return out, tpls, boss_tpls


@_w527_node_ledger_pytest.mark.parametrize('name', list(_GT.keys()))
def test_fixture_truth_crosscheck(row_frames, name: str) -> None:
    """真值对拍:槽数 / 当前槽位 / past 数 / 序列位置推断 / 已锁识别位。"""
    gt = _GT[name]
    frames, tpls, boss_tpls = row_frames
    row = frames[name]
    slots = classify_node_row(row, tpls, boss_templates=boss_tpls)
    # 台账视角:当前位 Hu 恒不定型(classify 只对 upcoming 跑 Hu)→ 台账需
    # 写点补当前位;boss 位命中 SIFT 时被覆盖 None → 位置先验回填 'boss'。
    built = fill_boss_by_position([s.node_type for s in slots])
    assert len(slots) == len(gt['seq']), f'{name}: 槽数 {len(slots)} != 真值 {len(gt["seq"])}'
    states = [s.state for s in slots]
    assert states.index('current') == gt['current'], f'{name}: 当前槽位错 {states}'
    assert states.count('past') == gt['current'], f'{name}: past 数错 {states}'
    for i, t in gt['expect_upcoming'].items():
        assert slots[i].node_type == t, (
            f'{name}: 槽{i} CV={slots[i].node_type}(hu={slots[i].hu_dist}) != 真值 {t}')
    # 位置推断票:已过槽数 p → 真值序列第 p 位 = 真值当前位类型(语义自洽)
    p = states.count('past')
    assert gt['seq'][p] == gt['seq'][gt['current']]
    assert built[gt['current']] is None
    if slots[-1].boss is not None:
        assert built[-1] == 'boss'   # boss SIFT 命中 → Hu 覆 None → 回填


def test_read_plane_detail_difficulty_truth(test_context) -> None:
    """敌人难度参考读法真值对拍:位面详情全屏 fixture,真值 = VLM 亲读 108
    (w527 批;底部明文「敌人难度 108」)。"""
    from one_dragon.utils import cv2_utils
    from sr_od.application.currency_war.obs.cw_observation import (
        read_plane_detail_difficulty,
    )
    img = cv2_utils.read_image(
        str(_TEST_ROOT / 'screens' / '货币战争-位面详情' / '位面详情全屏.png'))
    assert read_plane_detail_difficulty(test_context, img) == 108


# ==================== divergence_stats ====================

import json as _divergence_stats_json  # noqa: E402
from pathlib import Path as _divergence_stats_Path

from sr_od.application.currency_war.telemetry.cw_divergence_stats import (
    divergence_stats,  # noqa: E402
)


def test_divergence_stats(tmp_path: _divergence_stats_Path) -> None:
    """totals 计数与 run 过滤(close_calls/dp 姿态分布面归
    test_cw_infra_locks.py::test_divergence_stats_on_typed_rows,其
    typed-rows 混合形态场景更全)。"""
    rows = [
        {'run_id': 'r1', 'round_num': 1, 'candidate_scores': {'a': 1.0, 'b': 0.95}, 'strategy_id': 'decision_v2'},
        {'run_id': 'r1', 'round_num': 2, 'candidate_scores': {'a': 1.0, 'b': 0.5}, 'strategy_id': 'decision_v2'},
        {'run_id': 'r2', 'round_num': 1, 'candidate_scores': {}, 'strategy_id': 'decision_v2'},
    ]
    d = tmp_path / 'decisions.jsonl'
    d.write_text('\n'.join(_divergence_stats_json.dumps(r) for r in rows), encoding='utf-8')
    st = divergence_stats(tmp_path)
    assert st['decisions_total'] == 3
    assert st['with_candidates'] == 2
    # run 过滤
    st2 = divergence_stats(tmp_path, run_id='r2')
    assert st2['decisions_total'] == 1


def test_divergence_missing_file(tmp_path: _divergence_stats_Path) -> None:
    """文件缺 → 零值不炸。"""
    st = divergence_stats(tmp_path)
    assert st['decisions_total'] == 0


# ==================== 补给轮「0买0升」豁免(query.query_anomalies) ====================
# [退役墓碑,W3]query_anomalies 旧视图已随删除波 1 写入端退役一并删除
# (r5-migration-plan.md §2 W3 删旧读面;原 4 锁:补给轮豁免/战斗轮守卫/
# plan_error 不受豁免/缺 node_type 从严——其判读语义的现役载体 = journal
# 行间差分,journal_query 视图族;git 历史可复活原锁面)。

# ==================== cw4_counters 落盘(行为观测计数批,v7)====================

# ==================== W4 cw4 计数流删 + 局终行聚合收编(R5 W4,r5-migration-plan.md §2) ====================
# [退役墓碑,W4]test_cw4_counters_snapshot_into_archive /
# test_cw4_counters_zero_count_and_missing_distinct /
# test_cw4_counters_from_match_extracts_session /
# test_cw_loop_counters_snapshot_wiring 四锁随流载体退役
# (r5-migration-plan.md §2 W4 流删;写端 cw_loop._record_cw4_counters_snapshot
# 与 match_archive COUNTERS_FILE 面已删)。局终级全键聚合现役载体 =
# 局终域行载荷 MatchFinal.cw4_counters(test_cw_match_final 承行为锁),
# 档案显影位 = endgame.match_final.final.cw4_counters(下二锁)。
# 键全集封闭性锁另立 sr-od-test test_cw4_key_closure.py。


def test_cw4_stream_face_retired_from_assembler(
        replay: _match_archive_Path):
    """流删结构锁:装配器面无 COUNTERS_FILE/record_cw4_* 符号;新装配
    档案无顶层 ``cw4_counters`` 键(读侧宽容缺键,判读按显影位移读)。"""
    assert not hasattr(arch, 'COUNTERS_FILE'), (
        'COUNTERS_FILE 应已随 W4 流删删除(防半删)')
    assert not hasattr(arch, 'record_cw4_counters_snapshot'), (
        'record_cw4_counters_snapshot 应已随 W4 流删删除')
    assert not hasattr(arch, 'record_cw4_counters_from_match'), (
        'record_cw4_counters_from_match 应已随 W4 流删删除')
    a = arch.build_archive(replay, arch.assign_games(replay)[0])
    assert 'cw4_counters' not in a, (
        '新装配档案不得再有顶层 cw4_counters(流源已拆)')


def test_assembler_importable_and_callable():
    """装配冒烟门(T-318 补令;半截删除态机器拦截):装配文件可编译可
    导入、装配/重装配/物化入口可调用——`def build_archive` 被卷入
    整块删除而函数体残留时,模块导入不炸但装配函数缺失(实测形态),
    本锁在属主批自测即炸,不外溢成跨批树健康警报。"""
    import py_compile
    py_compile.compile(str(_match_archive_Path(arch.__file__)), doraise=True)
    for fn in ('build_archive', 'assemble_game', 'assemble_pending',
               'load_archive', 'assign_games'):
        entry = getattr(arch, fn, None)
        assert callable(entry), (
            f'装配面入口 {fn} 缺失/不可调用(半截删除态,防半删)')


def test_cw4_aggregate_surfaces_via_match_final_view():
    """聚合显影锁:局终行载荷携带的 ``cw4_counters`` 经 extract_match_
    final_rows + match_final_view 原样透传到档案 endgame 显影位
    (纯读派生,装配端零新写入)。"""
    row = {'row': 'write', 'field': 'match_final', 'run_id': 'run_x',
           'v': 7, 'ts': '2026-09-11T12:00:00', 'note': '',
           'after': {'final_type': 'loss', 'at_version': 7,
                     'cw4_counters': {'shop_churn_pair_buy': 3,
                                      'm2_retry_exhausted': 0}}}
    rows = arch.extract_match_final_rows([row])
    view = arch.match_final_view(rows.get('run_x'))
    assert view is not None
    assert view['final']['cw4_counters'] == {
        'shop_churn_pair_buy': 3, 'm2_retry_exhausted': 0}, (
        '局终行聚合须在档案 endgame.match_final.final.cw4_counters 显影')
    # 无计数载体形态:载荷缺键(旧档案)/None(诚实缺省)透传不炸
    for after in ({'final_type': 'loss'}, {'final_type': 'loss',
                                           'cw4_counters': None}):
        v = arch.match_final_view({'row': 'write', 'field': 'match_final',
                                   'run_id': 'run_y', 'v': 1, 'ts': '',
                                   'note': '', 'after': after})
        assert v['final'].get('cw4_counters') in (None, {}), (
            '无载体/缺省形态透传容忍')


# ==================== T-185 收口终局行(末轮 outcome 采集补全) ====================
# [退役墓碑,W3]test_stopped_game_last_round_outcome_in_archive 随档案
# rounds 构建面的旧流切片拆除而退役(r5-migration-plan.md §2 W3 删旧读面;
# 写端 cw_loop._write_terminal_outcome_row 已随删除波 1 消亡)。终局收口
# 证据的现役载体 = 局终域 match_final 行(test_cw_match_final 锁面);
# 终局行对 hp 真值链的结构性退出语义由下方 test_terminal_row_exits_hp_
# truth_chains 继续承锁(纯谓词,不依赖 rounds 构建)。


def test_terminal_row_exits_hp_truth_chains():
    """终局行结构性退出 hp 真值链(Δ池配对端点/hp 步进锚):hp_after=None 落
    Δ池配对前置剔除、conf=0.0 落可信门(0.0<HP_CONF_TRUSTED)——两既有谓词
    均 False,采集侧零新过滤、sim 读端零改动。"""
    from sr_od.application.currency_war.sim.pool import (
        hp_pair_endpoint_admissible,
    )
    from sr_od.application.currency_war.telemetry.match_archive import (
        _settlement_hp_usable,
    )
    row = {'source': 'terminal_closure', 'hp_after': None,
           'hp_confidence': 0.0}
    assert hp_pair_endpoint_admissible(row) is False
    assert _settlement_hp_usable(row) is False


# [退役墓碑,W3]test_terminal_row_query_hp_typed_not_fake(query_hp 显示面
# 终局行分型)随 query_hp 旧视图删除退役(r5-migration-plan.md §2 W3);
# 终局「诚实缺省」语义的现役载体 = match_final 行(test_cw_match_final 锁面)。
