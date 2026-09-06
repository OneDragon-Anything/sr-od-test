# -*- coding: utf-8 -*-
"""test_cw_telemetry_archive 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- effect_ledger: test_cw_effect_ledger.py
- match_archive: test_cw_match_archive.py
- performance: test_cw_performance.py
- telemetry_checks: test_cw_telemetry_checks.py
- test_telemetry_extra_sig: test_telemetry_extra_sig.py
  (test_telemetry_replay 段已删,2026-09-03 攻击排查:读本机 .debug 语料
   不可复现;①双轨配方语义由 test_cw_deploy_ops.py::test_decision_target_
   dual_track_returns_recipe 合成锁承载,③翻转率守卫为本地审计性质)
- w527_node_ledger: test_cw_w527_node_ledger.py
- test_equips_telemetry: test_equips_telemetry.py
- divergence_stats: test_cw_divergence_stats.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import state_of


# ==================== match_archive ====================

import json
import sys as _match_archive_sys
from pathlib import Path as _match_archive_Path

import pytest

_match_archive_sys.path.insert(0, 'src')

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


def _out(run_id, plane, rnd, ts, hp_after, conf=1.0, node_type='普通战斗'):
    return {'schema_version': 1, 'run_id': run_id, 'plane': plane,
            'round_num': rnd, 'ts': ts, 'node_type': node_type,
            'hp_after': hp_after, 'hp_confidence': conf, 'killed': False,
            'board_before': {}, 'bench_count': 0}


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


def test_archive_hp_truth_chain(replay: _match_archive_Path):
    """hp 真值链:结算屏(conf≥0.9)优先;备帧 hp=100 不可信不冒充真值。"""
    a = arch.build_archive(replay, arch.assign_games(replay)[0])
    by_key = {(r['plane'], r['round']): r for r in a['rounds']}
    r11 = by_key[(1, 1)]
    assert r11['hp'] == 60 and r11['hp_source'] == 'settlement'
    assert r11['hp_trusted'] is True
    # 掉血轮列表(败场节点)= hp 链上 delta<0 的轮(p1r9: 52→18)
    assert any(n['plane'] == 1 and n['round'] == 9 and n['delta'] == -34
               for n in a['loss_nodes'])
    # 只有无结算行的轮才落备帧兜底(本 fixture 全有结算行)
    assert all(r['hp_source'] == 'settlement' for r in a['rounds'])


def test_frame_hp_fallback_marks_untrusted(replay: _match_archive_Path):
    """无结算行的轮 → 备帧兜底,且 hp_readable=False 必标不可信。"""
    games = arch.assign_games(replay)
    # run_C 只造 decisions(删 outcome 行模拟读不到结算)
    out_p = replay / 'outcomes.jsonl'
    rows = [json.loads(l) for l in out_p.open(encoding='utf-8') if l.strip()]
    rows = [r for r in rows if r.get('run_id') != 'run_20260830_110000']
    _write_jsonl(replay, 'outcomes.jsonl', rows)
    a = arch.build_archive(replay, games[1])
    r = a['rounds'][0]
    assert r['hp'] == 100 and r['hp_source'] == 'frame'
    assert r['hp_trusted'] is False


def test_assemble_game_writes_index_and_no_tmp(replay: _match_archive_Path):
    """装配产物:match_*.json + index.jsonl 一行一局;无 .tmp 残留(原子写)。"""
    a = arch.assemble_game(replay, 'g_20260830_094811')
    assert a is not None and len(a['rounds']) == 4
    assert a['endgame']['result'] == 'loss'          # 末段 loss = 全局结果
    assert a['endgame']['abandoned'] is False
    assert a['opening']['chosen_env'] == ['增发货币']
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
    """旧数据不回填:首调只落水位线;之后只装水位线后的新局。"""
    assert arch.assemble_pending(replay) == []
    assert not (replay / 'matches').exists() or not list(
        (replay / 'matches').glob('match_*.json'))
    # 新局落库(晚于水位线)→ 下一触发只装它
    _write_jsonl(replay, 'decisions.jsonl', (
        [json.loads(l) for l in (replay / 'decisions.jsonl')
         .open(encoding='utf-8') if l.strip()]
        + [_dec('run_20260830_120000', 1, 1, '2026-08-30T12:00:00')]))
    _write_jsonl(replay, 'outcomes.jsonl', (
        [json.loads(l) for l in (replay / 'outcomes.jsonl')
         .open(encoding='utf-8') if l.strip()]
        + [_out('run_20260830_120000', 1, 1, '2026-08-30T12:01:00', 70)]))
    done = arch.assemble_pending(replay)
    assert done == ['g_20260830_120000']


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
    assert any((r['plane'], r['round']) == (1, 2) for r in got['rounds'])
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


def test_resume_reconciliation_columns(replay: _match_archive_Path):
    """恢复态对账列(v6③):续局段的恢复帧读数 vs 前段末帧账面逐字段
    对账;readable=False 的恢复读数对齐判 None(不可判,不猜)。

    复刻 2026-09-05 夜第八局实证:恢复帧 hp/gold 与停机前账面对不上,
    判读需此列显影才免手工翻流对账;装配器不裁真值。
    """
    dec_p = replay / 'decisions.jsonl'
    rows = [json.loads(ln) for ln in dec_p.open(encoding='utf-8') if ln.strip()]
    for r in rows:
        # 前段(run_A)末帧 p1r2:hp 不可信帧默认形态(hp=100, readable=False)
        if r.get('run_id') == 'run_20260830_094811' and r.get('round_num') == 2:
            r['gold'], r['gold_readable'] = 55, True
        # 续段(run_B)恢复帧 p1r9:hp 可信但与档案账面对不上(29→18 形态)
        if (r.get('run_id') == 'run_20260830_101513'
                and r.get('round_num') == 9):
            r['hp'], r['hp_readable'] = 18, True
            r['gold'], r['gold_readable'] = 68, True
    _write_jsonl(replay, 'decisions.jsonl', rows)
    a = arch.build_archive(replay, arch.assign_games(replay)[0])
    rec = a['resume_reconciliation']
    assert len(rec) == 1                                 # 单续局段一条
    e = rec[0]
    assert e['run_id'] == 'run_20260830_101513'
    assert e['resume_frame'] == {'plane': 1, 'round_num': 9}
    assert e['resume_ts'] == '2026-08-30T10:17:16'
    assert e['prev_final_ts'] == '2026-08-30T09:50:00'   # 前段末帧(run_A p1r2)
    # hp:恢复帧 18(可信)vs 前段末帧 100(帧值)→ 不对齐,显影
    assert e['hp'] == {'resume': 18, 'prev_final': 100, 'aligned': False}
    # gold:68 vs 55 → 不对齐
    assert e['gold'] == {'resume': 68, 'prev_final': 55, 'aligned': False}
    # level:两侧帧 state.level 均为默认 3 → 对齐(与 hp/gold 同构三键)
    assert e['level'] == {'resume': 3, 'prev_final': 3, 'aligned': True}
    # 单段独立局:无恢复事件 → 空列表
    a2 = arch.build_archive(replay, arch.assign_games(replay)[1])
    assert a2['resume_reconciliation'] == []
    # 恢复帧 hp 不可信(readable=False)→ aligned=None 不可判,不猜;
    # level 两侧不等(恢复帧 7 vs 前段 3)→ aligned=False
    rows2 = []
    for r in rows:
        if (r.get('run_id') == 'run_20260830_101513'
                and r.get('round_num') == 9):
            r = dict(r, hp_readable=False)
            r['state'] = {**r['state'], 'level': 7}
        rows2.append(r)
    _write_jsonl(replay, 'decisions.jsonl', rows2)
    a3 = arch.build_archive(replay, arch.assign_games(replay)[0])
    rec3 = a3['resume_reconciliation'][0]
    assert rec3['hp']['aligned'] is None
    assert rec3['level'] == {'resume': 7, 'prev_final': 3, 'aligned': False}


def test_resume_reconciliation_outcome_fallback(replay: _match_archive_Path):
    """恢复帧兜底(M2):续局段零决策帧(采集缺口形态)→ 最早结算行
    兜底,hp_after/hp_confidence 归一为帧 hp/hp_readable 口径;结算行
    不采金/等级 → 对应字段 aligned=None(诚实缺省,不猜)。"""
    dec_p = replay / 'decisions.jsonl'
    rows = [json.loads(ln) for ln in dec_p.open(encoding='utf-8') if ln.strip()]
    # 清掉续段(run_B)全部决策帧,只留结算行(p1r9 hp18 conf=1.0)
    _write_jsonl(replay, 'decisions.jsonl',
                 [r for r in rows if r.get('run_id') != 'run_20260830_101513'])
    a = arch.build_archive(replay, arch.assign_games(replay)[0])
    rec = a['resume_reconciliation']
    assert len(rec) == 1
    e = rec[0]
    assert e['run_id'] == 'run_20260830_101513'
    assert e['resume_frame'] == {'plane': 1, 'round_num': 9}
    assert e['resume_ts'] == '2026-08-30T10:20:00'       # 结算行 ts
    assert e['hp'] == {'resume': 18, 'prev_final': 100, 'aligned': False}
    assert e['gold'] == {'resume': None, 'prev_final': 10, 'aligned': None}
    assert e['level']['aligned'] is None                 # 结算行无 level
    # 低置信结算行(conf<0.9)→ hp 不可信 → aligned=None(与帧口径同判)
    out_p = replay / 'outcomes.jsonl'
    outs = [json.loads(ln) for ln in out_p.open(encoding='utf-8') if ln.strip()]
    _write_jsonl(replay, 'outcomes.jsonl', [
        dict(o, hp_confidence=0.5) if (o.get('run_id') == 'run_20260830_101513')
        else o for o in outs])
    a2 = arch.build_archive(replay, arch.assign_games(replay)[0])
    assert a2['resume_reconciliation'][0]['hp']['aligned'] is None


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


def test_materialized_slice_views_equal_source(replay: _match_archive_Path):
    """--match 视图同源:切片物化后 query_* 输出与源目录逐字节一致。"""
    from sr_od.application.currency_war.telemetry import query as q
    a = arch.assemble_game(replay, 'g_20260830_094811')
    slice_dir = arch.materialize_slice(a, replay / '_slice_tmp')
    for seg in ('run_20260830_094811', 'run_20260830_101513'):
        for view in (q.query_rounds, q.query_supply, q.query_anomalies,
                     q.query_hp, q.query_economy):
            assert view(slice_dir, seg) == view(replay, seg), \
                f'{view.__name__}@{seg}: 档案切片视图与源目录不一致'
    import shutil
    shutil.rmtree(slice_dir)


# ===== 二期补齐批:决策明细显形 / 策略版本戳 =====

def test_rounds_decision_detail_and_bench_equips(replay: _match_archive_Path):
    """二期①③⑤:逐轮表显形决策明细(v3_intention/candidate_scores/
    eval_breakdown/dp_posture)与备战席逐张/装备栏 owned;无明细字段 = None。"""
    # 给 p1r9 帧(段 B)补明细字段与 bench/equips 快照
    dec_p = replay / 'decisions.jsonl'
    rows = [json.loads(ln) for ln in dec_p.open(encoding='utf-8') if ln.strip()]
    for r in rows:
        if r.get('run_id') == 'run_20260830_101513' and r.get('round_num') == 9:
            r['v3_intention'] = {'primary': '甲'}
            r['candidate_scores'] = {'甲': 1.5}
            r['eval_breakdown'] = {'form': 0.4}
            r['dp_posture'] = '存息'
            r['state']['bench'] = [{'name': '椒丘', 'star': 1}, None]
            r['state']['equips'] = {'递归': 1}
    _write_jsonl(replay, 'decisions.jsonl', rows)
    a = arch.build_archive(replay, arch.assign_games(replay)[0])
    by_key = {(r['plane'], r['round']): r for r in a['rounds']}
    d = by_key[(1, 9)]['decision_detail']
    assert d['v3_intention'] == {'primary': '甲'}
    assert d['candidate_scores'] == {'甲': 1.5}
    assert d['eval_breakdown'] == {'form': 0.4}
    assert d['dp_posture'] == '存息'
    assert by_key[(1, 9)]['bench'] == [{'name': '椒丘', 'star': 1}, None]
    assert by_key[(1, 9)]['equips'] == {'递归': 1}
    # 无明细字段的帧 → 明细键全 None(不炸);有帧轮 detail 非 None
    assert by_key[(1, 1)]['decision_detail'] is not None
    assert by_key[(1, 1)]['decision_detail']['v3_intention'] is None


def _rewrite_runs(replay: _match_archive_Path, mutate) -> None:
    runs_p = replay / 'runs.jsonl'
    rows = [json.loads(ln) for ln in runs_p.open(encoding='utf-8') if ln.strip()]
    _write_jsonl(replay, 'runs.jsonl', mutate(rows))


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
    本锁钉键名与计数语义,分布数值不锁(测试纪律 #4)。"""
    from sr_od.application.currency_war.telemetry.schema import  terminal_state_summary
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


def test_rounds_terminal_vs_decision_frame_divergence(replay: _match_archive_Path):
    """端到端:同轮「决策帧列」与「终态列」并列且可分歧——决策帧取
    actions 最多帧(执行前),终态取最晚帧(执行后);复刻 w936 误读形态
    (决策帧 4/6 → 执行后 6/6)并断言两列不同。"""
    dec_p = replay / 'decisions.jsonl'
    rows = [json.loads(ln) for ln in dec_p.open(encoding='utf-8') if ln.strip()]
    # 给段 B p1r9 造三帧:①决策帧(actions 最多,dep=1 无装备)→
    # ②执行步进帧 → ③终态帧(最晚 ts,dep=3 已穿 2 件 + owned 1)
    rows.append({**_dec('run_20260830_101513', 1, 9, '2026-08-30T10:17:16',
                        actions=[{'__type__': 'BuyCard', 'card': {'name': '甲'}},
                                 {'__type__': 'BuyCard', 'card': {'name': '乙'}}]),
                 'state': {'node_type': '普通战斗', 'level': 3,
                           'hp_trusted': None, 'board': {},
                           'deployed': [{'name': '甲', 'equips': []}],
                           'bench': [], 'equips': []}})
    rows.append({**_dec('run_20260830_101513', 1, 9, '2026-08-30T10:18:00'),
                 'state': {'node_type': '普通战斗', 'level': 3,
                           'hp_trusted': None, 'board': {},
                           'deployed': [{'name': '甲', 'equips': []},
                                        {'name': '乙', 'equips': []}],
                           'bench': [], 'equips': []}})
    rows.append({**_dec('run_20260830_101513', 1, 9, '2026-08-30T10:19:30'),
                 'state': {'node_type': '普通战斗', 'level': 3,
                           'hp_trusted': None, 'board': {},
                           'deployed': [{'name': '甲', 'equips': ['火力风暴潮']},
                                        {'name': '乙', 'equips': []},
                                        {'name': '丙', 'equips': ['高周波电锯']}],
                           'bench': [None, {'name': '丁'}],
                           'equips': ['折叠小刀']}})
    _write_jsonl(replay, 'decisions.jsonl', rows)
    a = arch.build_archive(replay, arch.assign_games(replay)[0])
    # v7 起 schema 版本单一源在 SCHEMA_VERSION,不再钉字面值
    # (行为观测计数落盘批:v6→v7 加法字段,历史版本语义见源注释链)
    assert a['schema_version'] == arch.SCHEMA_VERSION
    r9 = next(r for r in a['rounds']
              if (r['plane'], r['round']) == (1, 9))
    # 决策帧列 = ①(actions 最多、ts 并列取晚)= 执行前板面
    assert len(r9['deployed']) == 1
    # 终态列 = ③(最晚帧)= 执行后板面,且与决策帧列可见分歧
    assert r9['terminal'] == {'deployed_count': 3, 'bench_count': 1,
                              'equips_worn': 2, 'equips_owned': 1}
    assert r9['terminal_ts'] == '2026-08-30T10:19:30'
    assert r9['terminal_source'] == 'last_decision_frame'
    assert r9['n_decision_frames'] == 4   # fixture 基帧 + ①②③(全帧计数口径)
    assert r9['terminal']['deployed_count'] != len(r9['deployed'])
    # 收口类型(w943 P2-5):③帧 actions=[] 不含出战 → mid_prep
    #(异常出口形态:terminal 滞后一个动作,判读降权)
    assert r9['terminal_closure'] == 'mid_prep'
    # 出战收口形态:末帧 actions 含 StartBattle → start_battle
    #(该帧观察 = 全部备战动作执行后的定型帧,terminal 可信)
    rows.append({**_dec('run_20260830_101513', 1, 9, '2026-08-30T10:19:40',
                        actions=[{'__type__': 'StartBattle'}]),
                 'state': {'node_type': '普通战斗', 'level': 4,
                           'hp_trusted': None, 'board': {},
                           'deployed': [{'name': '甲', 'equips': ['火力风暴潮']},
                                        {'name': '乙', 'equips': []},
                                        {'name': '丙', 'equips': ['高周波电锯']}],
                           'bench': [None, {'name': '丁'}],
                           'equips': ['折叠小刀']}})
    _write_jsonl(replay, 'decisions.jsonl', rows)
    r9c = next(r for r in arch.build_archive(
        replay, arch.assign_games(replay)[0])['rounds']
        if (r['plane'], r['round']) == (1, 9))
    assert r9c['terminal_closure'] == 'start_battle'
    assert r9c['terminal'] == r9['terminal']
    # 同 ts 并列:流内后见者胜(执行步进密集形态;ts 与当前最晚帧并列)
    rows.append({**_dec('run_20260830_101513', 1, 9, '2026-08-30T10:19:40'),
                 'state': {'node_type': '普通战斗', 'level': 4,
                           'hp_trusted': None, 'board': {},
                           'deployed': [], 'bench': [], 'equips': []}})
    _write_jsonl(replay, 'decisions.jsonl', rows)
    r9b = next(r for r in arch.build_archive(
        replay, arch.assign_games(replay)[0])['rounds']
        if (r['plane'], r['round']) == (1, 9))
    assert r9b['terminal'] == {'deployed_count': 0, 'bench_count': 0,
                               'equips_worn': 0, 'equips_owned': 0}


def test_rounds_terminal_none_for_outcome_only_round(replay: _match_archive_Path):
    """旧数据/仅结算行轮:无决策迹帧 → terminal=None、source='none'
    (读端容忍口径,不炸不猜)。"""
    out_p = replay / 'outcomes.jsonl'
    rows = [json.loads(ln) for ln in out_p.open(encoding='utf-8') if ln.strip()]
    # run_C 加一条 p1r2 结算行,但不造任何 p1r2 决策帧
    rows.append(_out('run_20260830_110000', 1, 2, '2026-08-30T11:02:00', 66))
    _write_jsonl(replay, 'outcomes.jsonl', rows)
    a = arch.build_archive(replay, arch.assign_games(replay)[1])
    r2 = next(r for r in a['rounds'] if (r['plane'], r['round']) == (1, 2))
    assert r2['terminal'] is None
    assert r2['terminal_ts'] is None
    assert r2['terminal_source'] == 'none'
    assert r2['terminal_closure'] is None
    assert r2['n_decision_frames'] == 0   # 零决策行缺口可见化


def test_supply_round_has_decision_frame(replay: _match_archive_Path):
    """补给轮 n_decision_frames 锁(run_supply_node 写入端,w941 判定移交):
    选卡确认后 record_decision 一帧(extra.phase='supply_pick')→ 补给轮
    不再结构性零决策行。锁的是「补给轮有帧」这一采集面,帧内容(合成
    快照、actions=[])非备战决策语义,读端按 outcome.source='synthetic_supply'
    分型。"""
    out_p = replay / 'outcomes.jsonl'
    dec_p = replay / 'decisions.jsonl'
    out_rows = [json.loads(ln) for ln in out_p.open(encoding='utf-8') if ln.strip()]
    # run_C p1r2 = 补给轮:合成结算行(source='synthetic_supply',boss 节点
    # 补给形态)+ 对应的一帧选卡确认后快照(phase='supply_pick')
    out_rows.append({**_out('run_20260830_110000', 1, 2, '2026-08-30T11:02:00',
                            45, node_type='boss'),
                     'source': 'synthetic_supply'})
    _write_jsonl(replay, 'outcomes.jsonl', out_rows)
    dec_rows = [json.loads(ln) for ln in dec_p.open(encoding='utf-8') if ln.strip()]
    dec_rows.append({**_dec('run_20260830_110000', 1, 2, '2026-08-30T11:01:50'),
                     'phase': 'supply_pick'})
    _write_jsonl(replay, 'decisions.jsonl', dec_rows)
    a = arch.build_archive(replay, arch.assign_games(replay)[1])
    r2 = next(r for r in a['rounds'] if (r['plane'], r['round']) == (1, 2))
    assert r2['n_decision_frames'] == 1   # 补给轮 n>=1(写入端补帧后)
    assert r2['terminal_source'] == 'last_decision_frame'


# ===== v5(M2 遥测增强批 ③:endgame.final_snapshot 局级终局快照列)=====

def test_endgame_final_snapshot(replay: _match_archive_Path):
    """终局快照列 = 全局最晚决策迹帧的阵容/金/等级(装配端派生,纯读)。

    g_A 跨两段,全局最晚帧 = run_B p2r1(10:25:00);fixture 默认
    state 为 level=3/deployed=[]/gold=10(取自 _dec)。
    """
    a = arch.build_archive(replay, arch.assign_games(replay)[0])
    fs = a['endgame']['final_snapshot']
    assert fs is not None
    assert fs['ts'] == '2026-08-30T10:25:00'   # 全局最晚(晚于段 A 各帧)
    assert fs['source'] == 'last_decision_frame'
    assert fs['level'] == 3 and fs['gold'] == 10
    assert fs['gold_readable'] is True
    assert fs['deployed'] == [] and fs['bench'] is None
    assert fs['terminal'] == {'deployed_count': 0, 'bench_count': 0,
                              'equips_worn': 0, 'equips_owned': 0}
    # 单段独立局同样有终局快照
    a2 = arch.build_archive(replay, arch.assign_games(replay)[1])
    fs2 = a2['endgame']['final_snapshot']
    assert fs2 is not None and fs2['ts'] == '2026-08-30T11:00:00'


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
    import os
    p = replay / 'matches' / f'match_{game_id}.json'
    with p.open('w', encoding='utf-8') as f:
        json.dump(stale, f, ensure_ascii=False)
    # 读端:默认自动迁移 → 版本写回 + terminal 族键补齐
    got = arch.load_archive(replay, game_id)
    assert got['schema_version'] == arch.SCHEMA_VERSION
    assert all(r['terminal_closure'] in ('start_battle', 'mid_prep')
               for r in got['rounds'])
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
    assert 'terminal_closure' not in got2['rounds'][0]


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


# ==================== performance ====================

import pytest as _performance_pytest

from sr_od.application.currency_war.kernel.cw_performance import  PerformanceTracker, RoundOutcome


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
    """is_losing_streak:trend > HP_LOSS_FULL*0.6(=18)→ True;低掉血 → False;冷启动 → False。"""
    # 每回合掉 20(普通关 normalized=20)> 18 → streak
    t_streak = PerformanceTracker()
    t_streak.record(_performance_out(1, 100))
    t_streak.record(_performance_out(2, 80))
    assert t_streak.is_losing_streak(), "trend=20>18 → 连败"
    # 小掉血(normalized=5)< 18 → 非 streak
    t_ok = PerformanceTracker()
    t_ok.record(_performance_out(1, 100))
    t_ok.record(_performance_out(2, 95))
    assert not t_ok.is_losing_streak(), "trend=5<18 → 非连败"
    # 冷启动(样本不足 trend=None)→ False
    assert not PerformanceTracker().is_losing_streak(), "冷启动 → False"


# ==================== telemetry_checks ====================

import json as _telemetry_checks_json
from pathlib import Path as _telemetry_checks_Path


def _write_replay(d: _telemetry_checks_Path, runs: list[dict]) -> None:
    """runs=[{run_id, strategy_id, plane, round, actions}] → 两流 jsonl。"""
    d.mkdir(parents=True, exist_ok=True)
    with (d / 'decisions.jsonl').open('w', encoding='utf-8') as f:
        for r in runs:
            f.write(_telemetry_checks_json.dumps({
                'run_id': r['run_id'], 'plane': r.get('plane', 1),
                'round_num': r['round'], 'ts': str(r['round']),
                'strategy_id': r.get('strategy_id', ''),
                'target_comp': r.get('target_comp', ''),
                'gold': 10, 'state': {},
                'actions': r['actions'],
            }, ensure_ascii=False) + '\n')
    with (d / 'outcomes.jsonl').open('w', encoding='utf-8') as f:
        for r in runs:
            f.write(_telemetry_checks_json.dumps({
                'run_id': r['run_id'], 'plane': 1,
                'round_num': r['round'], 'node_type': '普通战斗',
                'hp_after': 80,
            }, ensure_ascii=False) + '\n')
    # ADR-0273:真实语料每局有 runs.jsonl summary 行——fixture 同步补,
    # 否则 coverage 检查(summary_write_path_coverage)对合成语料恒 ⚠。
    with (d / 'runs.jsonl').open('w', encoding='utf-8') as f:
        for r in runs:
            f.write(_telemetry_checks_json.dumps({
                'run_id': r['run_id'], 'result': 'loss', 'plane_reached': 1,
            }, ensure_ascii=False) + '\n')


def _buy(name: str, reason: str) -> dict:
    return {'__type__': 'BuyCard', 'card': {'name': name, 'cost': 1},
            'reason': reason}


def test_default_stack_skipped(tmp_path: _telemetry_checks_Path) -> None:
    """default 栈(cw_plan,reason='plan')跳过 coldstart(不辖 r368)。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_replay(tmp_path, [{
        'run_id': 'run_t1', 'strategy_id': 'default', 'round': 1,
        'actions': [_buy('翡翠', 'plan')],   # plan 开局买=生产 default 合法
    }])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert '跳过' in out and '⚠' not in out


def test_v2_stack_violation_detected(tmp_path: _telemetry_checks_Path) -> None:
    """v2 栈违规(开局轮 reason=off=局49 形态)被检出+run_id 溯源。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_replay(tmp_path, [{
        'run_id': 'run_t2', 'strategy_id': 'line_v2', 'round': 1,
        'actions': [_buy('翡翠', 'off')],
    }])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'run_t2' in out and '⚠ 1 条' in out and '翡翠' in out


def test_stack_inferred_from_reason_vocab(tmp_path: _telemetry_checks_Path) -> None:
    """strategy_id 缺失时按开局 reason 词表判栈(v2 词→v2 栈跑检查)。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_replay(tmp_path, [{
        'run_id': 'run_t3', 'strategy_id': '', 'round': 2,
        'actions': [_buy('丹恒·饮月', 'bridge_seed')],   # v2 词表=合法
    }])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'run_t3' in out and '✓ 无违规' in out


def _write_multirow_replay(d: _telemetry_checks_Path) -> None:
    """开局轮多行(模拟生产 5-6 行/轮):pre-refresh 波+post-refresh 波。"""
    d.mkdir(parents=True, exist_ok=True)
    with (d / 'decisions.jsonl').open('w', encoding='utf-8') as f:
        # 行1(pre-refresh):违规买(off)+刷——2 actions,会被
        # max-actions reducer 输给行 2(3 actions 干净行)
        f.write(_telemetry_checks_json.dumps({
            'run_id': 'run_t4', 'plane': 1, 'round_num': 1, 'ts': '1',
            'strategy_id': 'line_v2', 'target_comp': '', 'gold': 5,
            'state': {}, 'actions': [_buy('翡翠', 'off'),
                                     {'__type__': 'RefreshShop', 'cost': 2}],
        }, ensure_ascii=False) + '\n')
        f.write(_telemetry_checks_json.dumps({
            'run_id': 'run_t4', 'plane': 1, 'round_num': 1, 'ts': '2',
            'strategy_id': 'line_v2', 'target_comp': '', 'gold': 3,
            'state': {}, 'actions': [_buy('椒丘', 'bridge_seed'),
                                     _buy('飞霄', 'bridge_seed'),
                                     _buy('灵砂', 'bridge_seed')],
        }, ensure_ascii=False) + '\n')
    with (d / 'outcomes.jsonl').open('w', encoding='utf-8') as f:
        f.write(_telemetry_checks_json.dumps({'run_id': 'run_t4', 'plane': 1,
                            'round_num': 1, 'node_type': '普通战斗',
                            'hp_after': 80}, ensure_ascii=False) + '\n')
    with (d / 'runs.jsonl').open('w', encoding='utf-8') as f:
        f.write(_telemetry_checks_json.dumps({'run_id': 'run_t4', 'result': 'loss',
                            'plane_reached': 1}, ensure_ascii=False) + '\n')


def test_multiline_round_not_lossy(tmp_path: _telemetry_checks_Path) -> None:
    """审查#3:开局轮逐行全检——pre-refresh 波的违规不被大行挤掉。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_multirow_replay(tmp_path)
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'run_t4' in out and '⚠' in out and '翡翠' in out, \
        '违规买牌在 2-action 行被 3-action 干净行挤掉 = 有损投影漏报'


def test_untagged_buys_report_indeterminable(tmp_path: _telemetry_checks_Path) -> None:
    """审查#2:开局买 reason 缺失 → ⊘ 无法判(非伪 ✓)。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_replay(tmp_path, [{
        'run_id': 'run_t5', 'strategy_id': 'line_v2', 'round': 1,
        'actions': [{'__type__': 'BuyCard',
                     'card': {'name': '某卡', 'cost': 1}}],   # 无 reason 键
    }])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'run_t5' in out and '⊘ 无法判' in out and '1 笔' in out


def test_unknown_strategy_id_skipped(tmp_path: _telemetry_checks_Path) -> None:
    """审查#5:非空未知 sid(未来新栈)显式跳过,不盲跑误报。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_replay(tmp_path, [{
        'run_id': 'run_t6', 'strategy_id': 'some_future_strategy',
        'round': 1, 'actions': [_buy('翡翠', 'pair')],
    }])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'run_t6' in out and '未知栈' in out and '跳过' in out


def test_decision_v2_stack_runs_coldstart(tmp_path: _telemetry_checks_Path) -> None:
    """decision_v2 判 v2 栈(reason 词表/coldstart 检查集同辖;旧
    line_v2 随 ADR-0336 删,判栈保留历史字符串)——检查必须跑且报
    违规,不得按「未知栈」跳过(注册桥观察局判读链锁)。样本:off 买
    (翡翠,局49 败坏形态)必报 ⚠;engine_seed 买(v2 合法放行词,
    ADR-0260)不误报。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_replay(tmp_path, [{
        'run_id': 'run_t7', 'strategy_id': 'decision_v2', 'round': 1,
        'actions': [_buy('翡翠', 'off'),
                    _buy('丹恒·饮月', 'engine_seed')],
    }])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'run_t7' in out and '⚠ 1 条' in out and '翡翠' in out, \
        'decision_v2 局 coldstart 必须跑且 off 败坏买被检出'
    assert '未知栈' not in out, 'decision_v2 须判 v2 栈,不得按未知栈跳过'


# --- 段级检查生产接线(ADR-0479:多帧/轮合并适配 + [17] 族覆盖) ---

def _write_p2_replay(d: _telemetry_checks_Path, p2_rounds: list[dict]) -> None:
    """写一局带 P2 轮的合成 replay。p2_rounds=[{round, gold, hp, spent}]。

    每轮两帧(镜像生产:wrapper 帧 RunBuyPhase + 决策帧),gold/hp 取
    首帧口径(record_decision 决策时点)。
    """
    d.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = [{
        'run_id': 'run_t8', 'plane': 1, 'round_num': 1, 'ts': '1',
        'strategy_id': 'decision_v2', 'target_comp': '', 'gold': 5,
        'hp': 100, 'state': {},
        'actions': [_buy('丹恒·饮月', 'engine_seed')],
    }]
    ts = 10
    for r in p2_rounds:
        # 帧1:wrapper 帧(无花费动作);帧2:决策帧(按 spent 带/不带买)
        for is_decision in (False, True):
            actions: list[dict] = []
            if not is_decision:
                actions = [{'__type__': 'RunBuyPhase'}]
            elif r.get('spent'):
                actions = [{'__type__': 'BuyCard',
                            'card': {'name': '某件', 'cost': 2},
                            'reason': 'p2_core'}]
            rows.append({
                'run_id': 'run_t8', 'plane': 2,
                'round_num': r['round'], 'ts': str(ts),
                'strategy_id': 'decision_v2', 'target_comp': '希儿量子',
                'gold': r['gold'], 'hp': r['hp'],
                'state': {'node_type': 'battle'},
                'actions': actions,
            })
            ts += 1
    with (d / 'decisions.jsonl').open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(_telemetry_checks_json.dumps(r, ensure_ascii=False) + '\n')
    with (d / 'outcomes.jsonl').open('w', encoding='utf-8') as f:
        f.write(_telemetry_checks_json.dumps({'run_id': 'run_t8', 'plane': 2,
                            'round_num': 9, 'node_type': '普通战斗',
                            'hp_after': 0}, ensure_ascii=False) + '\n')
    with (d / 'runs.jsonl').open('w', encoding='utf-8') as f:
        f.write(_telemetry_checks_json.dumps({'run_id': 'run_t8', 'result': 'loss',
                            'plane_reached': 2}, ensure_ascii=False) + '\n')


def test_p2_bleed_gold_stack_wired(tmp_path: _telemetry_checks_Path) -> None:
    """接线验收锚(跨局复盘立案A):P2 血降段金堆积在
    run_checks_on_replay 报红——修前生产栈只跑 coldstart 零标红。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_p2_replay(tmp_path, [
        {'round': 2, 'gold': 50, 'hp': 49},
        {'round': 4, 'gold': 62, 'hp': 31},
        {'round': 5, 'gold': 76, 'hp': 10},
    ])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'seg_p2_bleed_gold_stack' in out and '⚠' in out, \
        'P2 带血堆金段级检查未在生产 checks 路径报红=接线失败'
    assert 'p2r5' in out, '事件须带轮定位'


def test_p2_bleed_gold_stack_healthy_not_fired(tmp_path: _telemetry_checks_Path) -> None:
    """对偶门:血线稳定(hp 不掉)的 P2 攒息不报(防恒触发)。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_p2_replay(tmp_path, [
        {'round': 4, 'gold': 62, 'hp': 80},
        {'round': 5, 'gold': 76, 'hp': 80},
    ])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'seg_p2_bleed_gold_stack' not in out, \
        '血线稳定的 P2 攒息被报 = 恒触发误报'


def test_production_round_merge_multi_frame(tmp_path: _telemetry_checks_Path) -> None:
    """多帧/轮合并:金取首帧(决策时点),花费跨帧并集——首帧 62+
    后续帧零买不算「溢余未泄」误报(全帧有买则不报)。"""

    from sr_od.application.currency_war.sim.ledger_hooks import  merge_round_rows
    frames = [
        {'run_id': 'r', 'plane': 2, 'round_num': 1, 'ts': '1',
         'gold': 62, 'hp': 31, 'gold_readable': True,
         'state': {'board': {'仙舟': 3}, 'deployed': [], 'bench': []},
         'actions': [], 'formed_stop': False},
        {'run_id': 'r', 'plane': 2, 'round_num': 1, 'ts': '2',
         'gold': 58, 'hp': 31, 'gold_readable': True,
         'state': {},
         'actions': [{'__type__': 'BuyCard',
                      'card': {'name': '希儿', 'cost': 4},
                      'reason': 'p2_core'}], 'formed_stop': False},
    ]
    merged = merge_round_rows(frames)
    assert len(merged) == 1
    m = merged[0]
    assert m['gold'] == 62, '金须取首帧(决策时点),非末帧(花销后)'
    assert any(a['__type__'] == 'BuyCard' for a in m['actions']), \
        '花费动作须跨帧并集'
    assert m['state']['board_factions'] == {'仙舟': 3}, \
        'engines 代理须吃生产 state.board 同构映射'


# ==================== test_telemetry_extra_sig ====================

import sys as _test_telemetry_extra_sig_sys

_test_telemetry_extra_sig_sys.path.insert(0, 'src')

from sr_od.application.currency_war.telemetry import recorder as t
from sr_od.application.currency_war.kernel.cw_state import GameState as _test_telemetry_extra_sig_GameState


def test_record_decision_accepts_extra():
    """shop.py 的调用形态(带 extra=sess_*)不再 TypeError。

    局30 实证:r101 加 session 快照时 shop.py 传 extra=,但模块级便捷函数
    签名没有该参数 → 买牌 op 每轮 TypeError → 金 3→110 全程闲置,整局报废。
    """
    st = _test_telemetry_extra_sig_GameState(gold=5)
    t.record_decision(st, 'x', {}, {}, [],
                      extra={'sess_framework': '仙舟', 'sess_dual_track': True})
    # 不 start_run → early return,不落盘;到这里 = 签名对齐,不再 TypeError


# (2026-09-03 瘦身批:test_recorder_method_and_helper_signatures_align 与
#  test_deploy_equips_snapshot_method_exists 删除——inspect 签名对齐/hasattr
#  在场锁属实现形状(纪律 8),无行为面增量。)


# ==================== w527_node_ledger ====================

from pathlib import Path as _w527_node_ledger_Path
from types import SimpleNamespace

import pytest as _w527_node_ledger_pytest

_ROOT = _w527_node_ledger_Path(__file__).resolve().parents[5]          # 仓库根(StarRailOneDragon)
_TEST_ROOT = _w527_node_ledger_Path(__file__).resolve().parents[4]     # 测试仓根(sr-od-test)

from sr_od.application.currency_war.kernel.cw_state import  fill_boss_by_position, get_node_ledger, ledger_node_type, ledger_update_plane
from sr_od.application.currency_war.obs import cw_node_reader, cw_observation
from sr_od.application.currency_war.telemetry import state as cw_telemetry
from sr_od.application.currency_war.obs.cw_node_reader import  classify_node_row, load_node_type_templates
from sr_od.application.currency_war.obs.cw_observation import  node_vote_verdict

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

_TPLS = load_node_type_templates(_ASSETS)

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
def row_frames() -> dict:
    from one_dragon.utils import cv2_utils
    out = {}
    for name in _GT:
        img = cv2_utils.read_image(str(_FIXTURES / name))   # RGB
        x0, y0, x1, y1 = _CROP
        out[name] = img[y0:y1, x0:x1]
    return out


@_w527_node_ledger_pytest.mark.parametrize('name', list(_GT.keys()))
def test_fixture_truth_crosscheck(row_frames, name: str) -> None:
    """真值对拍:槽数 / 当前槽位 / past 数 / 序列位置推断 / 已锁识别位。"""
    gt = _GT[name]
    row = row_frames[name]
    # boss SIFT 模板与生产同源(read_node_sequence 恒传)→ boss 槽命中时
    # classify 覆 node_type=None(台账写点回填 'boss' 的前提)。
    boss_tpls = cw_node_reader.load_boss_templates(
        _ROOT / 'assets' / 'template' / 'currency_war' / 'boss_avatar')
    slots = classify_node_row(row, _TPLS, boss_templates=boss_tpls or None)
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
    from sr_od.application.currency_war.obs.cw_observation import  read_plane_detail_difficulty
    img = cv2_utils.read_image(
        str(_TEST_ROOT / 'screens' / '货币战争-位面详情' / '位面详情全屏.png'))
    assert read_plane_detail_difficulty(test_context, img) == 108


# ==================== divergence_stats ====================

import sys as _divergence_stats_sys
from pathlib import Path as _divergence_stats_Path

_divergence_stats_REPO = _divergence_stats_Path(__file__).resolve().parents[4]
_divergence_stats_sys.path.insert(0, str(_divergence_stats_REPO / 'src'))

import json as _divergence_stats_json  # noqa: E402

from sr_od.application.currency_war.telemetry.cw_divergence_stats import divergence_stats  # noqa: E402


def test_divergence_stats(tmp_path: _divergence_stats_Path) -> None:
    """close_call 计数/dp_modes 聚合/run 过滤。"""
    rows = [
        {'run_id': 'r1', 'round_num': 1, 'candidate_scores': {'a': 1.0, 'b': 0.95}, 'strategy_id': 'decision_v2', 'dp_posture': '升级'},
        {'run_id': 'r1', 'round_num': 2, 'candidate_scores': {'a': 1.0, 'b': 0.5}, 'strategy_id': 'decision_v2', 'dp_posture': 'adaptive'},
        {'run_id': 'r2', 'round_num': 1, 'candidate_scores': {}, 'strategy_id': 'decision_v2', 'dp_posture': ''},
    ]
    d = tmp_path / 'decisions.jsonl'
    d.write_text('\n'.join(_divergence_stats_json.dumps(r) for r in rows), encoding='utf-8')
    st = divergence_stats(tmp_path)
    assert st['decisions_total'] == 3
    assert st['with_candidates'] == 2
    assert st['close_calls'] == 1          # r1 round1 gap 0.05
    assert st['per_run'] == {'r1': [1]}
    assert st['dp_modes'] == {'升级': 1, 'adaptive': 1}
    assert st['with_dp_posture'] == 2      # 空串 tag 不计
    # run 过滤
    st2 = divergence_stats(tmp_path, run_id='r2')
    assert st2['decisions_total'] == 1 and st2['close_calls'] == 0


def test_divergence_missing_file(tmp_path: _divergence_stats_Path) -> None:
    """文件缺 → 零值不炸。"""
    st = divergence_stats(tmp_path)
    assert st['decisions_total'] == 0


# ==================== 补给轮「0买0升」豁免(query.query_anomalies) ====================
# 复盘跨局 3 次误报(g_20260831_082322 候选#6 / g_20260831_101653 候选#6 复发):
# 补给节点无商店消费面,空过合法,不应计入「钱变不成板」。
# 机制出处 = docs/game/currency_war/research/economy.md「奖励/补给节点不花钱」。

from sr_od.application.currency_war.telemetry.query import query_anomalies as _qa


def _abn_dec(node_type: str) -> dict:
    """金 42 / 0 买 0 升 的决策行(踩 ABN_GOLD=40 门,动作面全空)。"""
    return _dec('run_supply_fix', 1, 5, '2026-08-31T10:00:00', gold=42,
                state={'node_type': node_type, 'level': 3,
                       'hp_trusted': None, 'board': {}, 'deployed': []})


def test_supply_round_zero_spend_not_flagged(tmp_path) -> None:
    """误报场景:补给轮金42 0买0升 → 不产异常(跨局 3 次误报的回归断言)。"""
    _write_jsonl(tmp_path, 'decisions.jsonl', [_abn_dec('supply')])
    assert _qa(tmp_path, 'run_supply_fix') == []


def test_battle_round_zero_spend_still_flagged(tmp_path) -> None:
    """真违规守卫:普通战斗轮同形态(金42 0买0升)仍产异常——守卫未被移除。"""
    _write_jsonl(tmp_path, 'decisions.jsonl', [_abn_dec('普通战斗')])
    abn = _qa(tmp_path, 'run_supply_fix')
    assert len(abn) == 1 and '0买0升' in abn[0] and 'p1r5' in abn[0]


def test_supply_round_real_violation_still_flagged(tmp_path) -> None:
    """补给轮真违规(plan_error)不受豁免影响——豁免只辖「0买0升」一条。"""
    d = _abn_dec('supply')
    d['eval_breakdown'] = {'plan_error': 'boom'}
    _write_jsonl(tmp_path, 'decisions.jsonl', [d])
    abn = _qa(tmp_path, 'run_supply_fix')
    assert len(abn) == 1 and 'plan_error' in abn[0]


def test_missing_node_type_zero_spend_still_flagged(tmp_path) -> None:
    """缺 node_type(旧数据)→ 从严兜底仍查消费,豁免不扩大。"""
    d = _abn_dec('')
    d['state']['node_type'] = None
    _write_jsonl(tmp_path, 'decisions.jsonl', [d])
    abn = _qa(tmp_path, 'run_supply_fix')
    assert len(abn) == 1 and '0买0升' in abn[0]

# ==================== cw4_counters 落盘(行为观测计数批,v7)====================

def _freeze_archive_now(monkeypatch: pytest.MonkeyPatch, iso: str) -> None:
    """把 match_archive 写端时钟冻结到 fixture 时间窗内(写行 ts 参与归局)。"""
    import datetime as _dt
    frozen = _dt.datetime.fromisoformat(iso)

    class _FrozenDT(_dt.datetime):
        @classmethod
        def now(cls) -> _dt.datetime:
            return frozen

    monkeypatch.setattr(arch, 'datetime', _FrozenDT)


def test_cw4_counters_snapshot_into_archive(
        replay: _match_archive_Path,
        monkeypatch: pytest.MonkeyPatch):
    """触发计数局 → 局终快照经 cw4_counters.jsonl 归局,档案顶层含键值。

    归局时间窗契约:写行 ts 落在 g_A 的 [start_ts, end_ts] 闭区间内
    (生产时序 = cw_loop 局终先落计数再写 runs summary)。
    """
    _freeze_archive_now(monkeypatch, '2026-08-30T10:31:30')   # g_A 窗内
    arch.record_cw4_counters_snapshot(replay, {
        'shop_churn_pair_buy': 3, 'shop_hoard_over_capacity': 1,
        'm2_retry_exhausted': 0})
    a = arch.build_archive(replay, arch.assign_games(replay)[0])
    assert a['cw4_counters'] == {
        'shop_churn_pair_buy': 3, 'shop_hoard_over_capacity': 1,
        'm2_retry_exhausted': 0}
    # 时间窗隔离:无关局(g_C)不受 g_A 计数行污染
    a_c = arch.build_archive(replay, arch.assign_games(replay)[1])
    assert a_c['cw4_counters'] is None


def test_cw4_counters_zero_count_and_missing_distinct(
        replay: _match_archive_Path,
        monkeypatch: pytest.MonkeyPatch):
    """形态三分锁:None=无计数流(数据缺失)≠ {}=真实零计数;窗外行不归局。"""
    # g_C:落空快照(零计数局形态)→ 档案字段 = {}(在窗、非 None)
    _freeze_archive_now(monkeypatch, '2026-08-30T11:09:59')   # g_C 窗内
    got = arch.record_cw4_counters_snapshot(replay, None)
    assert got == {}
    a_c = arch.build_archive(replay, arch.assign_games(replay)[1])
    assert a_c['cw4_counters'] == {}
    # g_A:无任何计数行 → None(数据缺失,判读可区分)
    a = arch.build_archive(replay, arch.assign_games(replay)[0])
    assert a['cw4_counters'] is None
    # 完全无计数流文件:不炸,恒 None
    (replay / arch.COUNTERS_FILE).unlink()
    a2 = arch.build_archive(replay, arch.assign_games(replay)[1])
    assert a2['cw4_counters'] is None
    # 防御性容忍:窗外晚行(掉窗形态)不归 g_C
    _write_jsonl(replay, arch.COUNTERS_FILE, [
        {'ts': '2026-08-30T12:00:00', 'counters': {'x': 1}}])
    a3 = arch.build_archive(replay, arch.assign_games(replay)[1])
    assert a3['cw4_counters'] is None


def test_cw4_counters_from_match_extracts_session(
        replay: _match_archive_Path,
        monkeypatch: pytest.MonkeyPatch):
    """match 载体提取:state_of(session).cw4_counters 全量落盘;无 session/无计数
    → 空快照(default 栈形态,不炸)。"""
    from types import SimpleNamespace as _NS
    _freeze_archive_now(monkeypatch, '2026-08-30T10:31:30')
    # 策略器状态迁 MandateState:cw4_counters 经 state_of 附着(桩同效)
    m = _NS(session=_NS())
    state_of(m.session).cw4_counters = {'shop_drought_reset_on_buy': 2}
    got = arch.record_cw4_counters_from_match(replay, m)
    assert got == {'shop_drought_reset_on_buy': 2}
    # session 无 cw4_counters 属性 → 空快照
    got2 = arch.record_cw4_counters_from_match(replay, _NS(session=_NS()))
    assert got2 == {}
    rows = [json.loads(ln) for ln in
            (replay / arch.COUNTERS_FILE).open(encoding='utf-8')]
    assert rows[0]['counters'] == {'shop_drought_reset_on_buy': 2}
    assert rows[1]['counters'] == {}


def test_cw_loop_counters_snapshot_wiring(
        tmp_path: _match_archive_Path,
        monkeypatch: pytest.MonkeyPatch):
    """cw_loop 收口接线锁:局终助手把 ctx.cw_match.session 的计数快照
    落进 replay 流;无 match → 不写文件;写端失败不抛(best-effort)。"""
    # noqa: 本文件为机械拼接合并文件,函数内多处局部 import 属既有形态,
    # 逐处与既有风格一致(不新增违规类别,仅与全文件同型)。
    from types import SimpleNamespace as _NS  # noqa: I001
    from sr_od.application.currency_war.operations import cw_loop as loop_mod  # noqa: I001
    from sr_od.application.currency_war.telemetry import state as _tel_state  # noqa: I001

    class _StubRecorder:
        def __init__(self, d: _match_archive_Path) -> None:
            self.replay_dir = d

    monkeypatch.setattr(_tel_state, 'get_recorder',
                        lambda: _StubRecorder(tmp_path))
    op = loop_mod.CwLoop.__new__(loop_mod.CwLoop)

    # 有 match + 计数 → 落盘含键值(cw4_counters 经 state_of 附着,桩同效)
    _sess = _NS()
    state_of(_sess).cw4_counters = {'shop_churn_pair_buy': 1}
    op.ctx = _NS(cw_match=_NS(session=_sess))
    op._record_cw4_counters_snapshot()
    rows = [json.loads(ln) for ln in
            (tmp_path / arch.COUNTERS_FILE).open(encoding='utf-8')]
    assert rows == [{'ts': rows[0]['ts'],
                     'counters': {'shop_churn_pair_buy': 1}}]
    # 无 match(对局已清理)→ 不再追加
    n_before = len(rows)
    op.ctx = _NS(cw_match=None)
    op._record_cw4_counters_snapshot()
    rows2 = [json.loads(ln) for ln in
             (tmp_path / arch.COUNTERS_FILE).open(encoding='utf-8')]
    assert len(rows2) == n_before
    # 写端失败 → 吞异常不抛(best-effort 契约)
    op.ctx = _NS(cw_match=_NS(session=_NS(cw4_counters={'k': 1})))
    monkeypatch.setattr(arch, 'record_cw4_counters_from_match',
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('x')))
    op._record_cw4_counters_snapshot()   # 不抛即过
