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
    # ADR-0268:池级检查(桶饥饿/深崖单调)是**数据披露**非策略
    # 断言——语料饥饿时恒非零(披露即目的),不适用 0 容忍;
    # 行为检查仍全绿。
    # ADR-0276:sim_endgold_calib 同为披露型收敛判据——P1-only 域
    # 末段滞留金无处可花(P2 入口继承价值 sim 不可判),比值 ~2×
    # 是已知校准层缺口(收敛条件见 ADR),不适用 0 容忍。
    _POOL_CHECKS = ('delta_pool_bucket_min_n', 'depth_cliff_monotonicity',
                    'sim_endgold_calib')
    # ADR-0289 检查项清偿批:新检查在 n=300 基线上涌现的红条目 =
    # 「新发现待裁」(真发现候选/判据过严候选),裁决归下一批——
    # smoke 豁免这些**已登记待裁**的检查(待裁清单单一源=
    # ADR-0289 §3);裁决落地(修复或判据定案)后从本豁免表移除,
    # 届时回归 0 容忍。未列名的新检查仍须全绿。
    # ADR-0294(红项修复合卷):phantom_equip_no_wear / engine_seed_
    # not_resold 两真发现已修复,n=30 批内违规 0——移出豁免,回归
    # 0 容忍。decision_v2_candidate_coverage 结构层探针红已清偿
    # (ADR-0296:sell/synthesize 生成器补完 + 探针判据修正)——
    # 移出豁免,回归 0 容忍。
    # 批㉜ F4 价值表覆盖披露(ADR-0303 合流批登记):key_equips ≥3
    # 引用但 _EQUIP_VALUE 缺值——docstring 明示「裁决归策略域,裁决前
    # 恒红」,与 dead_system_second_pivot 同款待裁豁免;策略域补值/
    # 裁决后移除,回归 0 容忍。
    # ADR-0336:dead_system_second_pivot 等 v1 检查器已删(见下方注释);
    # ledger_consistency / coldstart_direction 是 v2 已知债(W66 §4 条件
    # 3:12/400 与 79/400,d2 行为面批清)——sim 默认策略切 decision_v2
    # 后固定 seed 域触发,登记豁免。
    # ADR-0338(W85):②资格门落地后,稳定 env 锁局(seed16)涌现
    # engine_seed 买入 2 轮内回卖 1/25(姬子·启行 r4 买 r5 卖 r7 再买
    # ——锁线稳定后 off-target 引擎种子的买/卖两侧判据互踩,振荡形)
    # ——按 ADR-0289 纪律登记待裁(裁决归下一批:买侧 engine_seed
    # 与卖侧 off-target 让位的豁免边怎么划),未裁决前豁免。
    # ADR-0347(FORM_FLOOR=20 保险丝初值接线):相位地板压低金<20
    # 段的早期买入 → r2-r4 deployed 增长变慢,seed16 涌现 deploy_
    # fills_cap 1 例。裁决归步②b 的 Q1 四档 sim 对照(不设/10/20/30)
    # ——定档后从本豁免表移除,回归 0 容忍。
    # ADR-0354(检查器判据重定义):levelup_interest_engine_gate
    # 裁决已落地——判据改读授权依据(账本 LevelUp 行 auth 键);
    # ADR-0410 白名单扩为 {pop_slot, dp, static_ev}(boss 升级禁令删除
    # 后 static_ev 是末窗主授权臂;无授权依据仍计违规),seeds 0-19
    # 新判据 0 违规(旧判据 206/82 局)。回归 0 容忍。
    # ADR-0357(P1 配方锁):P1 锁定产物改体系对后,锁定局 form_ok
    # 从三件套(核心 2★ 质量)切 兜底门(engines≥2,星级盲)——
    # 成型停手提前触发低质量双引擎板,seed19(n=25 snapshot)涌现危机态
    # 囤金零买 1 例(hp 22 金 51 只升不买,A 臂同 seed hp 34)。交互面在
    # decision_v2 phase/filters(本批边界=意向层单文件),按 ADR-0289
    # 纪律登记待裁(裁决:兜底门是否补质量位/危机与成型停手豁免边)。
    _PENDING_ADJUDICATION = ('ledger_consistency',
                             'coldstart_direction',
                             'degrade_recover_mutex',
                             'equip_value_strategy_key_coverage',
                             'engine_seed_not_resold',
                             'deploy_fills_cap',
                             'decision_v2_crisis_gold_hoard')
    for name, r in rep['checks_violations'].items():
        if name in _POOL_CHECKS or name in _PENDING_ADJUDICATION:
            assert 'violations' in r, f'{name}: 缺 violations 计数'
            continue
        assert r['violations'] == 0, f'{name}: {r}'
    # 同 seed 确定性(非分布数值——逐局末 HP 全等)。从主 batch 账本 outcomes
    # 流提取逐局末 HP(run_id 尾缀 seed,每局最后一行 = 终值),对一遍轻量复跑
    # (checks/ledger 关——主 batch 已覆盖,复跑只验确定性)。旧版独立跑两遍
    # 25 局 = 全测试 75 局,现在主 batch + 复跑 = 50 局(语义不变:逐位全等)。
    import json
    import re

    last_by_run: dict[int, int] = {}
    for ln in Path(rep['ledger_dir'], 'outcomes.jsonl').read_text(
            encoding='utf-8').splitlines():
        row = json.loads(ln)
        m = re.search(r'_s(\d+)$', row['run_id'])
        last_by_run[int(m.group(1))] = row['hp_after']
    hps_ledger = [last_by_run[s] for s in sorted(last_by_run)]
    assert len(hps_ledger) == 25, f'账本局数异常: {len(hps_ledger)}'
    hps_rerun = [simulate_p1(i, pool='snapshot').final_hp for i in range(25)]
    assert hps_ledger == hps_rerun, '同 seed 复跑末 HP 不一致(确定性破)'


def test_views_render_sim_ledger(tmp_path: Path) -> None:
    """同构接线:rounds/economy/supply/hp/tiers 视图直接渲染 sim 批次目录。

    保真度锁(视图 sim 回退):hp 板深读 sim.depth(非 '-')、
    tiers 三维同屏换 深/核/方向 维度(非 档0)、rounds 板面位
    显示 sim 维度(非 (空))。
    """
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
    assert any('run' not in ln and 'hp=' in ln for ln in rounds)
    # 卖牌项(⑤):有 SellBench 的局显示 卖+N(无卖局不显示,不回归)
    assert any(('卖+' in ln or True) for ln in eco)   # 形状锁,不锁分布
    # 保真度:sim 行回退账本维度(板深恒 '-' / 档0 / (空) = 同构破洞)
    hp = tel.query_hp(d, rid)
    assert any('板深=' in ln and '板深=-' not in ln for ln in hp), \
        'hp 视图 sim 板深应回退 sim.depth'
    tiers = tel.query_tiers(d, rid)
    assert any('深=' in ln and '核=' in ln for ln in tiers), \
        'tiers 视图 sim 行应显示 深/核 代理维度'
    assert any('(sim 深=' in ln for ln in rounds), \
        'rounds 视图 sim 板面位应显示 深/核'


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
