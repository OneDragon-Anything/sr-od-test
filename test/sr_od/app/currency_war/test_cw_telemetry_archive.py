# -*- coding: utf-8 -*-
"""test_cw_telemetry_archive 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- effect_ledger: test_cw_effect_ledger.py
- match_archive: test_cw_match_archive.py
- performance: test_cw_performance.py
- telemetry_checks: test_cw_telemetry_checks.py
- test_telemetry_extra_sig: test_telemetry_extra_sig.py
- test_telemetry_replay: test_telemetry_replay.py
- w527_node_ledger: test_cw_w527_node_ledger.py
- test_equips_telemetry: test_equips_telemetry.py
- divergence_stats: test_cw_divergence_stats.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== effect_ledger ====================

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.kernel.cw_effect_ledger import (  # noqa: E402
    AggregateEffect,
    build_env_ledger,
    build_ledger,
    interest_with,
    level_cost_with,
    node_income_with,
)


def test_case_spy_xp_discount() -> None:
    """算例 1 商业间谍(单击 4→3):升级成本全线 −25%。"""
    led = build_ledger([AggregateEffect('商业间谍', 'xp_click_delta', -1.0)])
    assert level_cost_with(30, led) == 90.0        # 30 击 × 3
    assert level_cost_with(30, build_ledger([])) == 120.0   # 基线 4


def test_case_longtermism_timing() -> None:
    """算例 2 长期主义:日程时点价值——gold 43 时下节点 +7 跨 50 息档(摊平分给不出)。"""
    led = build_ledger([AggregateEffect('长期主义', 'next_nodes', 7.0, remaining_nodes=3)])
    # gold 43 + 节点收入(5+7)= 55 ≥ 50 → 跨息档;无日程时 43+5=48 < 50 不跨
    assert node_income_with(0, 5.0, 0.0, led) == 12.0
    assert 43 + node_income_with(0, 5.0, 0.0, led) >= 50
    assert 43 + node_income_with(0, 5.0, 0.0, build_ledger([])) < 50
    # 日程只在余期内
    assert led.calendar_at(5) == 0.0


def test_case_buyout_cap_zero() -> None:
    """算例 3 买断制(cap 0):interest 恒 0 → 攒金无意义(现状活矛盾:为不付息的钱守 50)。"""
    led = build_ledger([AggregateEffect('买断制', 'interest_cap', 0.0)])
    assert interest_with(80, led) == 0
    assert interest_with(80, build_ledger([])) == 5   # 基线息
    # 息上调
    led10 = build_ledger([AggregateEffect('利息上调', 'interest_cap', 10.0)])
    assert interest_with(120, led10) == 10


def test_win_reward_multiplier() -> None:
    """伟大征服 ×3:连胜金乘子进收入(现状 DP 照 ×1 算)。"""
    led = build_ledger([AggregateEffect('伟大征服', 'win_mult', 3.0)])
    assert node_income_with(0, 5.0, 2.0, led) == 5.0 + 6.0   # streak 2×3
    assert node_income_with(0, 5.0, 2.0, build_ledger([])) == 7.0


def test_boss_node_calendar() -> None:
    """特战资金 boss+7:boss 位日程(粗锚 8/17/26)。"""
    led = build_ledger([AggregateEffect('特战资金', 'boss_node', 7.0)])
    assert led.calendar_at(8) == 7.0 and led.calendar_at(0) == 0.0


def test_ledger_buysell_wiring_semantics_retained() -> None:
    """批 3 DP 退役后的台账语义残留锁:台账构建/效果解析通道保留
    (消费面=cw_economy 经济效果;原 DP 值函数注入断言随 DP 模块
    退役删除——锁面重推出处=BLUEPRINT §3 DP 处置,git prior art)。"""
    from sr_od.application.currency_war.kernel.cw_effect_ledger import  build_ledger, effects_from_strategies
    led = build_ledger(effects_from_strategies(['买断制']))
    assert led.mutations.interest_cap == 0   # 买断制:息帽 0(台账仍承载经济效果)

def test_v1_overlay_routes() -> None:
    """v1 全量扫描补的路由:采购专员 surprise_every / 淘金客 xp_per_refresh /
    买断制 xp_per_node / 免费午餐 burst。"""
    led = build_ledger([
        AggregateEffect('采购专员·彩', 'surprise_every', 5),
        AggregateEffect('淘金客', 'xp_per_refresh', 2.0),
        AggregateEffect('买断制', 'xp_per_node', 4.0),
        AggregateEffect('免费午餐', 'free_refresh_burst', 11),
    ])
    m = led.mutations
    assert m.refresh_surprise_every == 5
    assert m.xp_per_refresh == 2.0
    assert m.xp_per_node == 4.0
    assert m.free_refresh_burst == 11


def test_env_ledger_plane_start_gold() -> None:
    """环境侧扩展(ADR-0144 缺口首补):增发货币 → 位面首节点日程;
    长线利好 → 刷新价突变(30 刷后 1 金,与 38 号跨线投资联动)。"""
    led = build_env_ledger(['增发货币', '长线利好'])
    assert led.calendar_at(0) == 6.0       # P1 首节点
    assert led.mutations.refresh_discount_at == 30
    assert led.mutations.refresh_price_after == 1
    # 未覆盖环境 = 空台账 = 现状行为
    empty = build_env_ledger(['火药味'])
    assert empty.calendar == {} and empty.mutations.refresh_discount_at == 0


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
    assert a['schema_version'] == arch.SCHEMA_VERSION == 5
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

from sr_od.application.currency_war.kernel.cw_comps import ScoreContext, get_comp
from sr_od.application.currency_war.kernel.cw_performance import  PerformanceTracker, RoundOutcome, comp_viability, is_run_dead
from sr_od.application.currency_war.kernel.cw_state import GameState


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


# —— perf_for_comp 映射 ——


def test_perf_for_comp_mapping() -> None:
    """trend=None→None;trend=0→1.0;trend=HP_LOSS_FULL→0。"""
    t = PerformanceTracker()
    assert t.perf_for_comp("A") is None, "冷启动 → None"
    # trend=0(不掉血)→ perf=1.0
    t.record(_performance_out(1, 100, comp="A"))
    t.record(_performance_out(2, 100, comp="A"))
    assert t.perf_for_comp("A") == _performance_pytest.approx(1.0, abs=1e-6), "不掉血 → perf=1.0"
    # 每回合掉 HP_LOSS_FULL → trend=HP_LOSS_FULL → perf≈0(用独立 tracker 避免上面 0-delta 稀释)
    t2 = PerformanceTracker()
    t2.record(_performance_out(1, 100, comp="A"))
    t2.record(_performance_out(2, 70, comp="A"))
    t2.record(_performance_out(3, 40, comp="A"))
    perf = t2.perf_for_comp("A")
    assert perf is not None
    assert perf < 0.2, "每回合掉 HP_LOSS_FULL → perf 趋 0"


# —— comp_viability: obs None→纯先验;rounds_seen 增→obs_weight 升 ——


def test_comp_viability_cold_start_pure_prior() -> None:
    """tracker 空(obs None)→ comp_viability = 纯先验(无观测项)。"""
    阿雅 = get_comp("昼神阿雅")
    state = GameState(board={"昼之半神": 4})
    ctx = ScoreContext(mechanics=set())
    t = PerformanceTracker()
    v = comp_viability(阿雅, state, ctx, t)
    assert v > 0.0
    assert v <= 1.0
    # 纯先验(ADR-0107 动态归一:equip/mech 无数据返 None → 剔除,权重重分配给 form/star):
    # = 0.40*form(1.0) / (0.40+0.15) = 0.40/0.55 ≈ 0.727(star=0 无核心持有,仍进加权但贡献 0)
    assert v == _performance_pytest.approx(0.727, abs=1e-2), "冷启动纯先验(动态归一,无 equip/mech 数据)"


def test_comp_viability_observation_blends() -> None:
    """rounds_seen 多 + 掉血大 → comp_viability 低于纯先验(观测拉低)。"""
    阿雅 = get_comp("昼神阿雅")
    state = GameState(board={"昼之半神": 4})
    ctx = ScoreContext(mechanics=set())
    cold = comp_viability(阿雅, state, ctx, PerformanceTracker())
    # 灌 6 回合稳定大掉血观测(阿雅,window 内每回合掉 20 不撞底:trend=20 → perf≈0.33)
    t = PerformanceTracker()
    for r, hp in enumerate([100, 80, 60, 40, 20, 0], start=1):
        t.record(_performance_out(r, hp, comp="昼神阿雅"))
    warm = comp_viability(阿雅, state, ctx, t)
    assert warm < cold, "观测到大掉血 → viability 低于纯先验"


def test_star_achievement_scales_with_core_star() -> None:
    """star_achievement:核心角色 star 升 → 达成度高(1星=0 / 2星=0.5 / 3星=1.0;review HIGH-1)。"""
    from sr_od.application.currency_war.kernel.cw_performance import star_achievement
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    飞霄 = get_comp("追击飞霄")
    core = 飞霄.core_chars[0]
    s1 = GameState(bench=[BenchChar(slot=0, char_id=core, faction='追击', star=1)])
    assert star_achievement(飞霄, s1) == _performance_pytest.approx(0.0, abs=1e-6)
    s2 = GameState(bench=[BenchChar(slot=0, char_id=core, faction='追击', star=2)])
    assert star_achievement(飞霄, s2) == _performance_pytest.approx(0.5, abs=1e-6)
    s3 = GameState(bench=[BenchChar(slot=0, char_id=core, faction='追击', star=3)])
    assert star_achievement(飞霄, s3) == _performance_pytest.approx(1.0, abs=1e-6)
    assert star_achievement(飞霄, GameState()) == 0.0   # 无核心持有 → 0


# —— is_run_dead 三门 ——


def test_is_run_dead_three_gates() -> None:
    """死局 = HP低 + trend高 + 锁不住血节点;缺一门 → False;冷启动 → False。"""
    # 造 trend>15:o1(100)→o2(80) 掉 20
    def _tracker() -> PerformanceTracker:
        t = PerformanceTracker()
        t.record(_performance_out(1, 100))
        t.record(_performance_out(2, 80))
        return t
    t = _tracker()
    danger_boss = GameState(hp=10)          # hp<DEAD_HP(20)
    assert is_run_dead(danger_boss, t, "boss"), "hp低+trend高+boss → 死"
    assert not is_run_dead(danger_boss, t, "普通战斗"), "普通关可能锁血 → 不死"
    safe_hp = GameState(hp=80)              # hp 不低
    assert not is_run_dead(safe_hp, t, "boss"), "hp 不低 → 不死"
    # 冷启动(trend None)→ 不死
    assert not is_run_dead(danger_boss, PerformanceTracker(), "boss"), "冷启动 trend None → 不死"


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


# —— RoundOutcome 字段完整性(telemetry 用)——


def test_round_outcome_dual_sided_fields() -> None:
    """RoundOutcome 双侧字段(自身 + 敌方)完整;敌方 None 表不可观测。"""
    o = RoundOutcome(round_num=1, plane=1, node_type="boss", comp_tag="c",
                     hp_after=80, hp_confidence=0.9, enemy_hp_after=None,
                     damage_dealt=None, killed=True)
    assert o.hp_after == 80
    assert o.killed
    assert o.enemy_hp_after is None


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


def test_recorder_method_and_helper_signatures_align():
    """便捷函数签名 ⊇ recorder 方法签名(防再漂移)。"""
    import inspect

    from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder
    helper_params = set(inspect.signature(t.record_decision).parameters)
    method_params = set(inspect.signature(
        TelemetryRecorder.record_decision).parameters) - {'self', 'run_id', 'difficulty'}
    missing = method_params - helper_params
    assert not missing, f'便捷函数缺参数 {missing}——与方法签名对齐防再犯'


# ==================== test_telemetry_replay ====================

import json as _test_telemetry_replay_json
import sys as _test_telemetry_replay_sys
from pathlib import Path as _test_telemetry_replay_Path

import pytest as _test_telemetry_replay_pytest

_test_telemetry_replay_sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_deploy_seat import _should_deploy, deploy_legal
from sr_od.application.currency_war.kernel.cw_recipe import decision_target
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState as _test_telemetry_replay_GameState, ShopCard
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.kernel.cw_transition import  FRAMEWORKS, TRANSITION_PACK, pick_framework

JSONL = (_test_telemetry_replay_Path(__file__).resolve().parents[5] / '.debug' / 'temp'
         / 'currency_war' / 'replay' / 'decisions.jsonl')


def _rows():
    if not JSONL.exists():
        _test_telemetry_replay_pytest.skip('遥测 decisions.jsonl 不存在(本机 .debug)')
    return [_test_telemetry_replay_json.loads(l) for l in JSONL.open(encoding='utf-8') if l.strip()]


def _to_bench(lst):
    return [BenchChar(slot=c.get('slot', 0), char_id=c['char_id'],
                      faction=c.get('faction', '?'), star=c.get('star', 1),
                      position_pref=c.get('position_pref', 'back'))
            for c in (lst or []) if isinstance(c, dict) and c.get('char_id')]


def _to_shop(lst):
    return [ShopCard(x=0, name=c['name'], faction=c.get('faction', '?'),
                     cost=c.get('cost', 1))
            for c in (lst or []) if isinstance(c, dict) and c.get('name')]


def _dual_snapshots_with_fw_bench(rows):
    """双轨 + bench 含框架 carry/partial 的快照(抽样限流)。"""
    out = []
    for d in rows[::13]:   # 抽样(整库 1.3 万条,抽样 ~1000 条秒级)
        st = d.get('state') or {}
        if not st.get('dual_track_phase'):
            continue
        bench = _to_bench(st.get('bench'))
        if not any(TRANSITION_PACK.get(c.char_id, ('',))[0] in FRAMEWORKS
                   and TRANSITION_PACK[c.char_id][1] != 'drop' for c in bench):
            continue
        out.append((d, bench))
    return out


def test_replay_decision_target_recipe_for_fw_bench():
    """① 双轨快照(bench 有框架件)→ decision_target 必返配方(r120 回归)。"""
    snaps = _dual_snapshots_with_fw_bench(_rows())
    assert snaps, '历史库应有双轨+框架件快照(r121 基线 303 条)'
    for d, _bench in snaps[:200]:
        sess = StrategySession()
        sess.transition_framework = '仙舟'   # 框架件在 bench → 至少可设仙舟口径
        st = d.get('state') or {}
        gs = _test_telemetry_replay_GameState(round_num=d.get('round_num') or 1,
                       plane=d.get('plane') or 1, dual_track_phase=True)
        gs.board = st.get('board') or {}
        dt = decision_target(sess, gs)
        assert dt is not None and '配方' in dt.name, \
            f'{d.get("run_id")} p{d.get("plane")}r{d.get("round_num")} 应返配方伪 comp'


def test_replay_should_deploy_fw_carry():
    """② 框架 carry/partial 双轨 deploy 应 True(拒因只许同名守卫)。"""
    for d in _rows()[::13]:
        st = d.get('state') or {}
        if not st.get('dual_track_phase'):
            continue
        gs = _test_telemetry_replay_GameState(round_num=d.get('round_num') or 1,
                       plane=d.get('plane') or 1, dual_track_phase=True)
        gs.level = st.get('level') or 3
        gs.bench = _to_bench(st.get('bench'))
        gs.deployed = _to_bench(st.get('deployed'))
        dep_names = {c.char_id for c in gs.deployed if c.char_id}
        for c in gs.bench:
            ent = TRANSITION_PACK.get(c.char_id)
            if not ent or ent[0] not in FRAMEWORKS or ent[1] == 'drop':
                continue
            if _should_deploy(c, gs, None):
                continue
            assert not deploy_legal(c, dep_names), \
                f'{c.char_id} 被拒但非同名守卫(p{gs.plane}r{gs.round_num})——回归!'


def test_replay_framework_flip_rate_guard():
    """③ fresh-read 相邻横跳率护栏(全量相邻序列,基线 7.5%,阈值 12%)。

    ⚠️ 不抽样——抽样破坏相邻性(每 N 取 1 让「相邻」跨 N 条,横跳率机械
    膨胀:实测 ::7 采样子集 13.9% vs 全量 7.5%)。
    """
    rows = _rows()
    seq = []
    for d in sorted(rows, key=lambda r: (r.get('run_id'), r.get('ts') or '')):
        st = d.get('state') or {}
        seq.append((d.get('run_id'),
                    pick_framework(_to_bench(st.get('bench')),
                                   _to_bench(st.get('deployed')),
                                   _to_shop(st.get('shop')))))
    flips = sum(1 for i in range(1, len(seq))
                if seq[i][0] == seq[i - 1][0] and seq[i][1] != seq[i - 1][1])
    rate = flips / max(1, len(seq))
    assert rate < 0.12, f'fresh-read 横跳率 {rate:.1%} 超护栏(基线 7.5%)'


# ==================== w527_node_ledger ====================

from pathlib import Path as _w527_node_ledger_Path
from types import SimpleNamespace

import pytest as _w527_node_ledger_pytest

_ROOT = _w527_node_ledger_Path(__file__).resolve().parents[5]          # 仓库根(StarRailOneDragon)
_TEST_ROOT = _w527_node_ledger_Path(__file__).resolve().parents[4]     # 测试仓根(sr-od-test)

from sr_od.application.currency_war.kernel.cw_state import  fill_boss_by_position, get_node_ledger, ledger_node_type, ledger_update_plane
from sr_od.application.currency_war.obs import cw_node_reader, cw_observation
from sr_od.application.currency_war.telemetry import state as cw_telemetry
from sr_od.application.currency_war.obs.cw_node_reader import  classify_node_row, current_slot_hu_type, load_node_type_templates
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


def test_fixture_current_hu_vote_documented(row_frames) -> None:
    """票C(高亮 Hu)跨 4 帧行为落对拍:有效命中(≤CUR_HU_DIST_HIT)时记录。

    高亮态 Hu 距离对渲染态敏感(w527 对拍:4 帧中命中票 0/4 与真值一致),
    **不锁类型正确性** —— 只锁「返回 (type|None, dist) 契约 + 命中门」;
    该票的噪声正是「查表优先 + ≥2 票才落账」阈值设计的实证依据。
    """
    from sr_od.application.currency_war.obs.cw_node_reader import CUR_HU_DIST_HIT
    hits = 0
    for name, gt in _GT.items():
        row = row_frames[name]
        slots = classify_node_row(row, _TPLS)
        cur = slots[gt['current']]
        t, d = current_slot_hu_type(row, cur, _TPLS)
        assert d >= 0
        if t is not None:
            assert d <= CUR_HU_DIST_HIT
            hits += 1
    # 对拍表数字化:4 帧中票C 弃权/命中的分布(命中不保证类型对,见 docstring)
    assert 0 <= hits <= len(_GT)


def test_read_plane_detail_difficulty_truth(test_context) -> None:
    """敌人难度参考读法真值对拍:位面详情全屏 fixture,真值 = VLM 亲读 108
    (w527 批;底部明文「敌人难度 108」)。"""
    from one_dragon.utils import cv2_utils
    from sr_od.application.currency_war.obs.cw_observation import  read_plane_detail_difficulty
    img = cv2_utils.read_image(
        str(_TEST_ROOT / 'screens' / '货币战争-位面详情' / '位面详情全屏.png'))
    assert read_plane_detail_difficulty(test_context, img) == 108


# ==================== test_equips_telemetry ====================

import sys as _test_equips_telemetry_sys

_test_equips_telemetry_sys.path.insert(0, 'src')


def test_read_row_equipped_import_path():
    """r132 的 import 路径必须可解析(防运行时才炸)。"""
    from sr_od.application.currency_war.obs.cw_identity_obs import read_row_equipped
    assert callable(read_row_equipped)


def test_deploy_equips_snapshot_method_exists():
    """CwOpDeploy._snapshot_equips_into_tracking 在位(r132 采集钩子)。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import CwOpDeploy
    assert hasattr(CwOpDeploy, '_snapshot_equips_into_tracking')


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
