"""按局存档(cw match archive)单元测试。

覆盖:game_id 跨段继承分组 / hp 真值链可信位 / 装配产物与原子写 /
水位线(旧数据不回填)/ 切片物化视图与源目录同源(--match ≡ --run)。
数据全部合成在 tmp_path,零真实 .debug 副作用。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, 'src')

from sr_od.application.currency_war.telemetry import match_archive as arch


def _write_jsonl(d: Path, name: str, rows: list[dict]) -> None:
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
def replay(tmp_path: Path) -> Path:
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


def test_assign_games_cross_segment_inheritance(replay: Path):
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


def test_archive_hp_truth_chain(replay: Path):
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


def test_frame_hp_fallback_marks_untrusted(replay: Path):
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


def test_assemble_game_writes_index_and_no_tmp(replay: Path):
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


def test_assemble_abandoned_marked(replay: Path):
    """末段无 runs 摘要 = abandoned(ADR-0235 口径:中断局也装配)。"""
    runs_p = replay / 'runs.jsonl'
    rows = [json.loads(l) for l in runs_p.open(encoding='utf-8') if l.strip()]
    _write_jsonl(replay, 'runs.jsonl', [r for r in rows
                                        if r.get('run_id') != 'run_20260830_110000'])
    a = arch.assemble_game(replay, 'g_20260830_110000')
    assert a['endgame']['abandoned'] is True
    assert a['endgame']['result'] == 'abandoned'


def test_assemble_pending_watermark_no_backfill(replay: Path):
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


def test_materialized_slice_views_equal_source(replay: Path):
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

def test_rounds_decision_detail_and_bench_equips(replay: Path):
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


def _rewrite_runs(replay: Path, mutate) -> None:
    runs_p = replay / 'runs.jsonl'
    rows = [json.loads(ln) for ln in runs_p.open(encoding='utf-8') if ln.strip()]
    _write_jsonl(replay, 'runs.jsonl', mutate(rows))


def test_strategy_version_stamp_propagates(replay: Path):
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


def test_strategy_version_none_for_legacy(replay: Path):
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
    from sr_od.application.currency_war.telemetry.schema import (
        terminal_state_summary,
    )
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


def test_rounds_terminal_vs_decision_frame_divergence(replay: Path):
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
    assert a['schema_version'] == arch.SCHEMA_VERSION == 4
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


def test_rounds_terminal_none_for_outcome_only_round(replay: Path):
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


# ===== v4 返修(w943 审计 P2-4 版本迁移读端 / P2-5 收口类型)=====

def _read_archive_file(replay: Path, game_id: str) -> dict:
    with (replay / 'matches' / f'match_{game_id}.json') \
            .open('r', encoding='utf-8') as f:
        return json.load(f)


def test_load_archive_auto_rebuilds_stale_version(replay: Path):
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
        replay: Path):
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
