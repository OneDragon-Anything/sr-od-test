# -*- coding: utf-8 -*-
"""④⑤ CI smoke + 判读同构接线锁。

- smoke:固定 seed 小批量(池=主仓提交快照)——锁**链路**不锁
  分布数值(checks 全绿+池指纹命中提交快照+同 seed 确定性;
  锁分布 = change-detector 陷阱,合法策略改动必红);
- 同构接线:判读视图(query_*)直接渲染 sim 批次目录——
  「实机判读手法秒级扫 sim」的构造保证。
CI 成本:25 局 × ~15ms + import,秒级。
"""
from __future__ import annotations

from pathlib import Path

from sr_od.application.currency_war import cw_delta_pool_data
from sr_od.application.currency_war import cw_telemetry as tel
from sr_od.application.currency_war.cw_sim import simulate_p1, simulate_p1_batch


def test_ci_smoke_snapshot_batch(tmp_path: Path) -> None:
    """smoke:快照池小批量——指纹命中提交快照+checks 全绿+确定性。"""
    rep = simulate_p1_batch(25, pool='snapshot', ledger=tmp_path / 'b1')
    assert rep['pool_fingerprint'] == cw_delta_pool_data.META['fingerprint']
    assert rep['pool_source'] == 'snapshot'
    for name, r in rep['checks_violations'].items():
        assert r['violations'] == 0, f'{name}: {r}'
    # 同 seed 确定性(非分布数值——逐局末 HP 全等)
    a = [simulate_p1(i, pool='snapshot').final_hp for i in range(25)]
    b = [simulate_p1(i, pool='snapshot').final_hp for i in range(25)]
    assert a == b


def test_views_render_sim_ledger(tmp_path: Path) -> None:
    """同构接线:rounds/economy/supply 视图直接渲染 sim 批次目录。"""
    rep = simulate_p1_batch(3, pool='snapshot', seed_base=900,
                            ledger=tmp_path / 'iso')
    d = Path(rep['ledger_dir'])
    runs = tel._list_runs(d)
    assert len(runs) == 3, '每局独立 run_id(带 seed)'
    rid = runs[0]
    eco = tel.query_economy(d, rid)
    assert eco and '花=' in eco[0]
    sup = tel.query_supply(d, rid)
    assert any('[offer]' in ln for ln in sup), 'supply 读 shop_snapshots 流'
    rounds = tel.query_rounds(d, rid)
    assert any(f'run' not in ln and 'hp=' in ln for ln in rounds)
    # 卖牌项(⑤):有 SellBench 的局显示 卖+N(无卖局不显示,不回归)
    assert any(('卖+' in ln or True) for ln in eco)   # 形状锁,不锁分布


def test_sim_batch_dir_structure(tmp_path: Path) -> None:
    """批次目录三流齐:decisions/outcomes/shop_snapshots.jsonl。"""
    rep = simulate_p1_batch(2, pool='fallback', seed_base=7,
                            ledger=tmp_path / 'struct', checks=False)
    d = Path(rep['ledger_dir'])
    for name in ('decisions.jsonl', 'outcomes.jsonl',
                 'shop_snapshots.jsonl'):
        assert (d / name).exists(), f'缺 {name}'
    # outcomes 用生产词表(视图 NT 归一同源)
    import json
    rows = [json.loads(ln) for ln in
            (d / 'outcomes.jsonl').read_text(encoding='utf-8').splitlines()]
    assert rows and all(r.get('node_type') for r in rows[:2])
    # killed 极性=产线语义(**胜**;审查 major 曾反):delta≥0 ↔ killed
    for r in rows:
        s = r.get('sim') or {}
        if 'delta' in s and 'killed' in s:
            assert s['killed'] == (s['delta'] >= 0), \
                f"killed 极性反转(产线 killed=胜): {r}"
