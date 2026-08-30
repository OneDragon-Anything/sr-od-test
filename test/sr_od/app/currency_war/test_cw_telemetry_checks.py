"""决策项 1 锁:生产遥测接 checks(栈判别+coldstart 适配)。"""
from __future__ import annotations

import json
from pathlib import Path


def _write_replay(d: Path, runs: list[dict]) -> None:
    """runs=[{run_id, strategy_id, plane, round, actions}] → 两流 jsonl。"""
    d.mkdir(parents=True, exist_ok=True)
    with (d / 'decisions.jsonl').open('w', encoding='utf-8') as f:
        for r in runs:
            f.write(json.dumps({
                'run_id': r['run_id'], 'plane': r.get('plane', 1),
                'round_num': r['round'], 'ts': str(r['round']),
                'strategy_id': r.get('strategy_id', ''),
                'target_comp': r.get('target_comp', ''),
                'gold': 10, 'state': {},
                'actions': r['actions'],
            }, ensure_ascii=False) + '\n')
    with (d / 'outcomes.jsonl').open('w', encoding='utf-8') as f:
        for r in runs:
            f.write(json.dumps({
                'run_id': r['run_id'], 'plane': 1,
                'round_num': r['round'], 'node_type': '普通战斗',
                'hp_after': 80,
            }, ensure_ascii=False) + '\n')
    # ADR-0273:真实语料每局有 runs.jsonl summary 行——fixture 同步补,
    # 否则 coverage 检查(summary_write_path_coverage)对合成语料恒 ⚠。
    with (d / 'runs.jsonl').open('w', encoding='utf-8') as f:
        for r in runs:
            f.write(json.dumps({
                'run_id': r['run_id'], 'result': 'loss', 'plane_reached': 1,
            }, ensure_ascii=False) + '\n')


def _buy(name: str, reason: str) -> dict:
    return {'__type__': 'BuyCard', 'card': {'name': name, 'cost': 1},
            'reason': reason}


def test_default_stack_skipped(tmp_path: Path) -> None:
    """default 栈(cw_plan,reason='plan')跳过 coldstart(不辖 r368)。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_replay(tmp_path, [{
        'run_id': 'run_t1', 'strategy_id': 'default', 'round': 1,
        'actions': [_buy('翡翠', 'plan')],   # plan 开局买=生产 default 合法
    }])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert '跳过' in out and '⚠' not in out


def test_v2_stack_violation_detected(tmp_path: Path) -> None:
    """v2 栈违规(开局轮 reason=off=局49 形态)被检出+run_id 溯源。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_replay(tmp_path, [{
        'run_id': 'run_t2', 'strategy_id': 'line_v2', 'round': 1,
        'actions': [_buy('翡翠', 'off')],
    }])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'run_t2' in out and '⚠ 1 条' in out and '翡翠' in out


def test_stack_inferred_from_reason_vocab(tmp_path: Path) -> None:
    """strategy_id 缺失时按开局 reason 词表判栈(v2 词→v2 栈跑检查)。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_replay(tmp_path, [{
        'run_id': 'run_t3', 'strategy_id': '', 'round': 2,
        'actions': [_buy('丹恒·饮月', 'bridge_seed')],   # v2 词表=合法
    }])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'run_t3' in out and '✓ 无违规' in out


def _write_multirow_replay(d: Path) -> None:
    """开局轮多行(模拟生产 5-6 行/轮):pre-refresh 波+post-refresh 波。"""
    d.mkdir(parents=True, exist_ok=True)
    with (d / 'decisions.jsonl').open('w', encoding='utf-8') as f:
        # 行1(pre-refresh):违规买(off)+刷——2 actions,会被
        # max-actions reducer 输给行 2(3 actions 干净行)
        f.write(json.dumps({
            'run_id': 'run_t4', 'plane': 1, 'round_num': 1, 'ts': '1',
            'strategy_id': 'line_v2', 'target_comp': '', 'gold': 5,
            'state': {}, 'actions': [_buy('翡翠', 'off'),
                                     {'__type__': 'RefreshShop', 'cost': 2}],
        }, ensure_ascii=False) + '\n')
        f.write(json.dumps({
            'run_id': 'run_t4', 'plane': 1, 'round_num': 1, 'ts': '2',
            'strategy_id': 'line_v2', 'target_comp': '', 'gold': 3,
            'state': {}, 'actions': [_buy('椒丘', 'bridge_seed'),
                                     _buy('飞霄', 'bridge_seed'),
                                     _buy('灵砂', 'bridge_seed')],
        }, ensure_ascii=False) + '\n')
    with (d / 'outcomes.jsonl').open('w', encoding='utf-8') as f:
        f.write(json.dumps({'run_id': 'run_t4', 'plane': 1,
                            'round_num': 1, 'node_type': '普通战斗',
                            'hp_after': 80}, ensure_ascii=False) + '\n')
    with (d / 'runs.jsonl').open('w', encoding='utf-8') as f:
        f.write(json.dumps({'run_id': 'run_t4', 'result': 'loss',
                            'plane_reached': 1}, ensure_ascii=False) + '\n')


def test_multiline_round_not_lossy(tmp_path: Path) -> None:
    """审查#3:开局轮逐行全检——pre-refresh 波的违规不被大行挤掉。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_multirow_replay(tmp_path)
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'run_t4' in out and '⚠' in out and '翡翠' in out, \
        '违规买牌在 2-action 行被 3-action 干净行挤掉 = 有损投影漏报'


def test_untagged_buys_report_indeterminable(tmp_path: Path) -> None:
    """审查#2:开局买 reason 缺失 → ⊘ 无法判(非伪 ✓)。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_replay(tmp_path, [{
        'run_id': 'run_t5', 'strategy_id': 'line_v2', 'round': 1,
        'actions': [{'__type__': 'BuyCard',
                     'card': {'name': '某卡', 'cost': 1}}],   # 无 reason 键
    }])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'run_t5' in out and '⊘ 无法判' in out and '1 笔' in out


def test_unknown_strategy_id_skipped(tmp_path: Path) -> None:
    """审查#5:非空未知 sid(未来新栈)显式跳过,不盲跑误报。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_replay(tmp_path, [{
        'run_id': 'run_t6', 'strategy_id': 'some_future_strategy',
        'round': 1, 'actions': [_buy('翡翠', 'pair')],
    }])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'run_t6' in out and '未知栈' in out and '跳过' in out


def test_decision_v2_stack_runs_coldstart(tmp_path: Path) -> None:
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

def _write_p2_replay(d: Path, p2_rounds: list[dict]) -> None:
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
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    with (d / 'outcomes.jsonl').open('w', encoding='utf-8') as f:
        f.write(json.dumps({'run_id': 'run_t8', 'plane': 2,
                            'round_num': 9, 'node_type': '普通战斗',
                            'hp_after': 0}, ensure_ascii=False) + '\n')
    with (d / 'runs.jsonl').open('w', encoding='utf-8') as f:
        f.write(json.dumps({'run_id': 'run_t8', 'result': 'loss',
                            'plane_reached': 2}, ensure_ascii=False) + '\n')


def test_p2_bleed_gold_stack_wired(tmp_path: Path) -> None:
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


def test_p2_bleed_gold_stack_healthy_not_fired(tmp_path: Path) -> None:
    """对偶门:血线稳定(hp 不掉)的 P2 攒息不报(防恒触发)。"""

    from sr_od.application.currency_war.sim.ledger_hooks import run_checks_on_replay
    _write_p2_replay(tmp_path, [
        {'round': 4, 'gold': 62, 'hp': 80},
        {'round': 5, 'gold': 76, 'hp': 80},
    ])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'seg_p2_bleed_gold_stack' not in out, \
        '血线稳定的 P2 攒息被报 = 恒触发误报'


def test_production_round_merge_multi_frame(tmp_path: Path) -> None:
    """多帧/轮合并:金取首帧(决策时点),花费跨帧并集——首帧 62+
    后续帧零买不算「溢余未泄」误报(全帧有买则不报)。"""

    from sr_od.application.currency_war.sim.ledger_hooks import (
        merge_round_rows,
    )
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
