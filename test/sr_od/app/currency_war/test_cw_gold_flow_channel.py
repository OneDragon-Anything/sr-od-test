"""模态期金去向对账通道回归锁(kind='modality_gold' + query_gold_flow 视图)。

覆盖三面(改动任一侧必过本锁):
1. 记录端 record_modality_gold:exogenous 行落账、choice 载荷键面、
   OCR miss(gold_before/after=None)时 delta=None 诚实缺省;
2. 查询端 query_gold_flow:模态逐笔显形、未解释残差 = economy 同口径
   收入 − Σ可信模态笔、非 0 标 ⚠;与 query_economy「收」格严格同源;
3. 装配端 D1 收口:assemble_pending 对 schema 过期的存量档案重装配
   (防「修复只救读端,直读 JSON 的消费端永久吃到欠列档案」);v6 起
   跳过条件加严为「版本最新 ∧ 段集清单吻合」,续段归并即重装。

测试纪律:全部写 tmp_path,禁触真实 .debug(recorder 单例经 monkeypatch
桩化——模块级 _telstate 是全局,按测试纪律 #1 整链桩化)。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, 'src')

from sr_od.application.currency_war.telemetry import match_archive as arch
from sr_od.application.currency_war.telemetry import query as q
from sr_od.application.currency_war.telemetry import recorder as rec

# ===== fixtures =====

def _write_jsonl(d: Path, name: str, rows: list[dict]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    with (d / name).open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def _dec(run_id: str, plane: int, rnd: int, ts: str, gold: int,
         actions: list[dict] | None = None,
         level_up_cost: int | None = None) -> dict:
    """最小 decisions 行(state.level_up_cost 进 state,与生产序列化同构)。"""
    return {'run_id': run_id, 'plane': plane, 'round_num': rnd, 'ts': ts,
            'gold': gold, 'gold_readable': True, 'strategy_id': 'decision_v2',
            'actions': actions or [],
            'state': {'level_up_cost': level_up_cost}}


def _exo(run_id: str, kind: str, rnd: int, ts: str,
         choice: dict | None = None) -> dict:
    return {'run_id': run_id, 'kind': kind, 'round_num': rnd, 'ts': ts,
            'detail': '', 'state_snapshot': {}, 'choice': choice or {}}


@pytest.fixture()
def replay(tmp_path: Path) -> Path:
    """两轮一局:r1 金 5→10(收 5 = 模态 +3 金球 + 未解释 2);r2 金 10→20。"""
    rd = tmp_path / 'replay'
    _write_jsonl(rd, 'decisions.jsonl', [
        _dec('run_g1', 1, 1, '2026-09-06T10:00:00', 5),
        _dec('run_g1', 1, 2, '2026-09-06T10:05:00', 10,
             actions=[{'__type__': 'BuyCard', 'card': {'name': '甲', 'cost': 2}}]),
        _dec('run_g1', 1, 3, '2026-09-06T10:10:00', 20),
    ])
    _write_jsonl(rd, 'outcomes.jsonl', [
        {'run_id': 'run_g1', 'plane': 1, 'round_num': 1, 'hp_after': 90},
    ])
    _write_jsonl(rd, 'runs.jsonl', [
        {'run_id': 'run_g1', 'result': 'loss', 'plane_reached': 1},
    ])
    _write_jsonl(rd, 'exogenous.jsonl', [
        _exo('run_g1', 'modality_gold', 2, '2026-09-06T10:03:00',
             {'node': 'spheres', 'plane': 1, 'gold_before': 7,
              'gold_after': 10, 'gold_delta': 3}),
        # 干扰行:别局的 modality 行不得串账
        _exo('run_other', 'modality_gold', 2, '2026-09-06T10:03:00',
             {'node': 'spheres', 'plane': 1, 'gold_before': 0,
              'gold_after': 99, 'gold_delta': 99}),
    ])
    return rd


# ===== 1. 记录端 =====

def test_record_modality_gold_writes_row(tmp_path: Path,
                                         monkeypatch: pytest.MonkeyPatch):
    """模块级入口落 exogenous 行:kind/choice 键面锁(delta 符号 = 后−前)。"""
    tmp_rec = rec.TelemetryRecorder(tmp_path, enabled=True)
    monkeypatch.setattr(rec._telstate, '_CURRENT_RUN_ID', 'run_x')
    monkeypatch.setattr(rec._telstate, 'get_recorder', lambda: tmp_rec)
    rec.record_modality_gold('spheres', 2, 5, 30, 33)
    rows = [json.loads(ln) for ln in
            (tmp_path / 'exogenous.jsonl').open(encoding='utf-8') if ln.strip()]
    assert len(rows) == 1
    r = rows[0]
    assert r['kind'] == 'modality_gold'
    assert r['run_id'] == 'run_x' and r['round_num'] == 5
    ch = r['choice']
    assert ch['node'] == 'spheres' and ch['plane'] == 2
    assert ch['gold_before'] == 30 and ch['gold_after'] == 33
    assert ch['gold_delta'] == 3


def test_record_modality_gold_miss_is_honest_none(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """OCR miss(gold 传 None)→ delta=None 诚实缺省,不冒认真值。"""
    tmp_rec = rec.TelemetryRecorder(tmp_path, enabled=True)
    monkeypatch.setattr(rec._telstate, '_CURRENT_RUN_ID', 'run_x')
    monkeypatch.setattr(rec._telstate, 'get_recorder', lambda: tmp_rec)
    rec.record_modality_gold('spheres', 1, 1, None, 12)
    r = [json.loads(ln) for ln in
         (tmp_path / 'exogenous.jsonl').open(encoding='utf-8') if ln.strip()][0]
    assert r['choice']['gold_delta'] is None


def test_record_modality_gold_noop_outside_run(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """局外(run_id 空)no-op——与 record_exogenous 同门控,不产孤儿行。"""
    monkeypatch.setattr(rec._telstate, '_CURRENT_RUN_ID', '')
    rec.record_modality_gold('spheres', 1, 1, 0, 5)   # 不落盘即过
    assert not (tmp_path / 'exogenous.jsonl').exists()


# ===== 2. 查询端 =====

def test_gold_flow_lists_entries_and_unexplained(replay: Path):
    """模态逐笔显形 + 未解释残差 = 收入 − Σ可信模态笔,非 0 标 ⚠。

    r2:金 5→10,买 2(花=2)→ 收=7;模态 +3 → 未解释=4 → ⚠。
    r3:金 10→20,花 0 → 收=10;无模态行 → 无未解释格。
    """
    lines = q.query_gold_flow(replay, 'run_g1')
    text = '\n'.join(lines)
    assert 'p1r2' in text and '模态[spheres+3]' in text
    assert '未解释=4' in text and '⚠' in text
    r3 = [ln for ln in lines if ln.strip().startswith('p1r3')]
    assert r3 and '花=0' in r3[0] and '收=10' in r3[0]
    assert '⚠' not in r3[0]


def test_gold_flow_income_same_source_as_economy(replay: Path):
    """口径同源锁:goldflow 的「收」逐轮等于 economy 视图的「收」格。"""
    eco = q.query_economy(replay, 'run_g1')
    flow = q.query_gold_flow(replay, 'run_g1')

    def _income(lines: list[str]) -> dict[str, str]:
        out = {}
        for ln in lines:
            s = ln.strip()
            key = s.split(' ')[0]
            for tok in s.split(' '):
                if tok.startswith('收='):
                    out[key] = tok[len('收='):]
        return out
    assert _income(flow) == _income(eco)


def test_gold_flow_zero_modality_rows_tolerated(replay: Path):
    """零 modality 行(旧数据/sim 局)→ 仅 economy 同构行,不炸不报错。"""
    _write_jsonl(replay, 'exogenous.jsonl', [])
    lines = q.query_gold_flow(replay, 'run_g1')
    assert lines and all('模态' not in ln for ln in lines)


def test_gold_flow_untrusted_delta_excluded_from_sum(replay: Path):
    """delta=None(miss)笔只显形 '?' 不进 Σ;未解释按可信笔计。"""
    _write_jsonl(replay, 'exogenous.jsonl', [
        _exo('run_g1', 'modality_gold', 2, '2026-09-06T10:03:00',
             {'node': 'spheres', 'plane': 1, 'gold_before': None,
              'gold_after': 10, 'gold_delta': None}),
    ])
    text = '\n'.join(q.query_gold_flow(replay, 'run_g1'))
    assert '模态[spheres?]' in text      # miss 笔显形为 ?
    # 全 miss 笔 → Σ 未知 → 不出「未解释」数(诚实缺省,不拿 0 冒充对平)
    assert '未解释' not in text


def test_gold_flow_flags_negative_residual_without_entries(replay: Path):
    """⚠未挂钩:无模态行的负收入残差显影(第9局悬案「金 33→0」形态)。

    r2 金 10→4 花 0 → 收=-6 且无逐笔 → ⚠未挂钩;
    对照正收入轮(不标)。"""
    rd = replay.parent / 'replay_neg'
    _write_jsonl(rd, 'decisions.jsonl', [
        _dec('run_neg', 1, 1, '2026-09-06T11:00:00', 10),
        _dec('run_neg', 1, 2, '2026-09-06T11:05:00', 4),
        _dec('run_neg', 1, 3, '2026-09-06T11:10:00', 9),
    ])
    _write_jsonl(rd, 'outcomes.jsonl', [])
    _write_jsonl(rd, 'exogenous.jsonl', [])
    text = '\n'.join(q.query_gold_flow(rd, 'run_neg'))
    assert 'p1r2' in text and '收=-6' in text and '⚠未挂钩' in text
    assert '⚠' not in text.split('p1r3')[1]   # 正收入轮不标


# ===== 3. 装配端 D1 收口 =====

def test_assemble_pending_rebuilds_stale_schema(replay: Path):
    """schema 过期的存量档案经 assemble_pending 重装配(D1 收口:
    装配端修复落地前的 v1 档案欠列动作合并,读端 auto_rebuild 救不了
    直读 JSON 的消费端;写入端随水位线推进自愈一次)。

    形态:game_g1 先落档 + 水位线;新局 game_g2(晚于水位线)已有一个
    手工写的 v1 旧档案 → 触发时走「已入档但 schema 过期 → 重装」分支。
    """
    assert arch.assemble_pending(replay) == []   # 首调:落水位线(g1.end_ts)
    # 新局落库(晚于水位线)
    rows = [json.loads(ln) for ln in (replay / 'decisions.jsonl')
            .open(encoding='utf-8') if ln.strip()]
    _write_jsonl(replay, 'decisions.jsonl', rows + [
        _dec('run_20260906_120000', 1, 1, '2026-09-06T12:00:00', 8)])
    outs = [json.loads(ln) for ln in (replay / 'outcomes.jsonl')
            .open(encoding='utf-8') if ln.strip()]
    _write_jsonl(replay, 'outcomes.jsonl', outs + [
        {'run_id': 'run_20260906_120000', 'plane': 1, 'round_num': 1,
         'hp_after': 70}])
    # 手工写一份 v1 旧档案(直读 JSON 消费端会吃到欠列形态)
    g2 = 'g_20260906_120000'
    p2 = replay / 'matches' / f'match_{g2}.json'
    with p2.open('w', encoding='utf-8') as f:
        json.dump({'schema_version': 1, 'game_id': g2, 'rounds': []},
                  f, ensure_ascii=False)
    done = arch.assemble_pending(replay)
    assert done == [g2]
    got = json.loads(p2.open(encoding='utf-8').read())
    assert got['schema_version'] == arch.SCHEMA_VERSION
    assert got['rounds']   # 重装后非空壳


def test_assemble_pending_skips_current_schema(replay: Path):
    """对偶门(v6 活局续段治理批重推导):版本最新 ≠ 无条件跳过——
    跳过条件 = 版本最新 **∧ 段集清单与本轮分组吻合**(防续段归并后
    永远进不了档案);段集有增长 / 清单缺失 → 重装。

    三形态:①已入档+版本最新+段集无增长 → 跳过(防每次触发全量重装);
    ②段集有增长(续段并入)→ 重装且不丢段;③手写档案缺 segments 键
    (= 无法证明覆盖的退化形态)→ 保守重装。
    """
    assert arch.assemble_pending(replay) == []   # 首调:落水位线
    # 形态①:窗口内新局 + 最新版档案且段集清单吻合 → 跳过
    rows = [json.loads(ln) for ln in (replay / 'decisions.jsonl')
            .open(encoding='utf-8') if ln.strip()]
    new_run = 'run_20260906_130000'
    _write_jsonl(replay, 'decisions.jsonl', rows + [
        _dec(new_run, 1, 1, '2026-09-06T13:00:00', 8)])
    g2 = 'g_20260906_130000'
    p = replay / 'matches' / f'match_{g2}.json'
    with p.open('w', encoding='utf-8') as f:
        json.dump({'schema_version': arch.SCHEMA_VERSION, 'game_id': g2,
                   'segments': [{'run_id': new_run}], 'rounds': []},
                  f, ensure_ascii=False)
    assert arch.assemble_pending(replay) == []
    # 形态②:续段并入该局(首帧非 (p1,r1))→ 段集增长 → 重装
    resumed = 'run_20260906_140000'
    dec = [json.loads(ln) for ln in (replay / 'decisions.jsonl')
           .open(encoding='utf-8') if ln.strip()]
    _write_jsonl(replay, 'decisions.jsonl', dec + [
        _dec(resumed, 1, 5, '2026-09-06T14:00:00', 6)])
    done = arch.assemble_pending(replay)
    assert done == [g2]
    got = json.loads(p.open(encoding='utf-8').read())
    assert [s['run_id'] for s in got['segments']] == [new_run, resumed]
    assert got['rounds']   # 重装为全量派生,非手写空壳
    # 收敛:段集无增长后再触发不重复写
    assert arch.assemble_pending(replay) == []
    # 形态③:缺 segments 键的手写档案(旧锁 fixture 形态)→ 无法证明
    # 覆盖 → 保守重装(语义变更点:v5 无条件跳过已被取代)
    rows = [json.loads(ln) for ln in (replay / 'decisions.jsonl')
            .open(encoding='utf-8') if ln.strip()]
    late_run = 'run_20260906_150000'
    _write_jsonl(replay, 'decisions.jsonl', rows + [
        _dec(late_run, 1, 1, '2026-09-06T15:00:00', 8)])
    g3 = 'g_20260906_150000'
    p3 = replay / 'matches' / f'match_{g3}.json'
    with p3.open('w', encoding='utf-8') as f:
        json.dump({'schema_version': arch.SCHEMA_VERSION, 'game_id': g3,
                   'rounds': []}, f, ensure_ascii=False)
    assert arch.assemble_pending(replay) == [g3]
    got3 = json.loads(p3.open(encoding='utf-8').read())
    assert [s['run_id'] for s in got3['segments']] == [late_run]
