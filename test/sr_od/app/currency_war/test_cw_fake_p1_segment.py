"""假局 P1 全段跑通锁(T-120 sim 重设计 批 1 验收①的载体)。

出处 = T-120 方案 v2(``.debug/temp/currency_war/t120_sim_redesign/
方案.md``,**易失产物**)§6.2 批 1 行「真 op(run_buy_waves 单动作循环)
跑通假局 P1 全段」+ 验收①「同 seed+同剧本逐位复现」;ADR 落点待
T-120 退役批分配,后续批回填编号。

锁的语义(测试纪律 7 自检):

- **全段跑通锁** = 端口改道后的生产链路在假环境端到端可达:入口观察
  经观察源端口(状态机真值)、决策 = 真策略器冷建(mandate_v1)、动作
  执行经执行器端口(sink 落状态机 + 账本位随动)、遥测全链落生产
  schema 到假局档案根。红 = 改道断线/策略器对假局态崩/档案根装配断。
- **确定性锁** = 同 seed + 同剧本两次全程驱动,轨迹逐位相等(重放契约
  的假局半边;红 = 随机流串扰或环境规则引入不可复现分支)。
- **账本位锁** = sink 的 ledger/tracked 随动与游戏真值对得上:金账
  严格恒等式(任意轮 期末金 = 期初金 − spend_executed + 卖入,卖入
  双源同判:ledger 账 == 状态机金账差分)与动作账自洽。红 = sink
  账本位漂移(批 1 新引入面的在环检测器)。(2026-09-09 合并批:原
  同文件 test_sink_ledger_matches_game_truth 单侧不等式弱锁按
  DEBTS.md D65 处置删除——本文件现由金恒等式强锁为正主,原
  test_cw_fidelity_baseline.py 整件并入承载。)(T-22 定谳重推:
  恒等式辖域按「商店窗 vs 备战域」拆分,正主 = 本文件两常设检查卡
  test_fake_ledger_zero_tolerance_gold_attribution(备战域逐动作
  归属,零容忍)+ test_fake_ledger_window_plan_vs_executed_zero_
  tolerance(商店窗 plan账vs实扣,零容忍;T-22 时点的真漏账
  xfail 在册钉已随 T-76 根因修复摘除,现为零容忍正锁),
  保真基线面①只保金非负底线——定谳记录 = .debug/progress/
  2026-09-11-cw-clear-run/reports/T-22-r1.md 与 T-76-r1.md。)
- **journal 写端隔离锁** = 假局 journal 行落假局根、live 根零新行
  (T-129/T-130 混流注记的机器可判形)。
- **保真基线锁**(原 test_cw_fidelity_baseline 批 1 验收③,2026-09-09
  并入):种子批三面——金恒等式(见账本位锁)/轨迹域(hp ∈
  [0, HP_UPPER_BOUND]、金非负、开局 = OPENING_HP_BASE 先验)/
  对拍件形状(bands 统计件完整产出,离线 runner 消费的同一 helper)。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fixtures.cw_fake_game.fake_match import (
    DEFAULT_OPENING_HP,
    HP_UPPER_BOUND,
    FakeMatch,
)
from fixtures.cw_harness import (
    FakeP1Result,
    bands_from_trajectories,
    fake_p1_run,
)

from test.conftest import SrTestContext
from test.harness.fixture_controller import enter_running_state, reset_running_state

#: P1 全段剧本(5 节点代表段:战斗/奖励/战斗/补给/boss——覆盖收入四
#: 分量分支与结算两态;非 9 节点全量:批量预算归保真度批,sim-testing
#: 边界。更小的 n 与更大的 n 在「跑通+确定性」断言上等价,测试纪律 12)
_SCRIPT: list[str] = ['battle', 'reward', 'battle', 'supply', 'boss']

_SEED: int = 20260908


def test_fake_p1_full_segment_end_to_end(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """P1 全段跑通:5 节点全程收工 + 档案四流齐 + 行内容为生产 schema。

    判据逐条:
    ① run_buy_waves 每轮收工(outcome 在案,无 round_fail);
    ② decisions/outcomes/runs/shop_snapshots/op_journal 五流落假局根;
    ③ decisions 行带 run_id 且含动作序列(策略器决策经生产写点落盘);
    ④ outcomes 行 node_type 与剧本一致(结算遥测同产线,方案 §4-4);
    ⑤ journal action 行在环(单动作回执链;写端隔离 = 行落假局根,
       live 根零触由根槽结构性保证,测试不读真实 live 根——纪律 19)。
    """
    enter_running_state(test_context)
    try:
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=_SCRIPT, initial_gold=30) as run:
            result = run.run_p1()
        root = tmp_path / 'fake_p1'
        # ① 全程收工 + 轨迹形状
        assert set(result.rounds) == set(range(1, len(_SCRIPT) + 1))
        assert [result.rounds[r]['node'] for r in sorted(result.rounds)] \
            == _SCRIPT
        # ② 档案流面(删除波 1 重写):旧流四件(decisions/outcomes/runs/
        # shop_snapshots)写入端退役 → 零文件;保留流 op_journal 照旧落档
        for stream in ('decisions.jsonl', 'outcomes.jsonl', 'runs.jsonl',
                       'shop_snapshots.jsonl'):
            assert not (root / stream).exists(), \
                f'旧流写入端已退役却仍有产出:{stream}'
        assert (root / 'op_journal.jsonl').exists(), '保留流 op_journal 缺档'
        # ③ prep 动作序列 = run.prep_audit(执行缝在环内存账;原 decisions
        # 行动作序列随写入端退役,审计账为行为面唯一载体)
        assert run.prep_audit, 'prep 审计为空(执行缝未在环)'
        assert any(e['applied'] for e in run.prep_audit), (
            'prep 动作序列全未落地(单动作循环未消费任何动作——改道/决策断线)')
        # ④ 结算域与剧本对齐(假局结算内存账 = 生产 schema 载体)
        settlements = [(result.rounds[r]['settlement'] is not None)
                       for r in sorted(result.rounds)]
        assert settlements == [True] * len(_SCRIPT), (
            '假局结算真值缺位(settle_battle 链断)')
        # ⑤ journal 行落假局根且 kind=action 行存在(单动作回执链在环)
        j_rows = [json.loads(x) for x in
                  (root / 'op_journal.jsonl').read_text(
                      encoding='utf-8').splitlines() if x.strip()]
        assert any(r.get('kind') == 'action' for r in j_rows), (
            'journal 无 action 行(op_journal 回执位未入环)')
        # ⑥ 缺陷流零桩伪影(落地审 M2 回归断言):bench 落位对拍行在
        # 槽键差分桩下与生产计数语义对齐,清洁执行恒零行——行出现 =
        # 桩语义再漂移(而非环境真缺陷,假环境执行失败面结构性为零)
        _assert_no_pixel_diff_artifacts(root)
    finally:
        reset_running_state(test_context, test_context.cw_match)


def _assert_no_pixel_diff_artifacts(root: Path) -> None:
    """M2 回归:假局档案 defect 流零 bench pixel-diff invariant 行。

    语义(修后口径):bench 落位 audit 的输入域 = 真实像素帧,假环境
    结构性不存在 → harness 对该族行做结构性豁免(如实无数据,方案
    §4-6①;落地审 M2 备选路线)。本锁辖**豁免不被拆除**:行出现 =
    豁免过滤被移除且审计通道复活——即「缺陷流如实无数据」申报破缺。"""
    defect_file = root / 'defect_ledger.jsonl'
    if not defect_file.exists():
        return
    rows = [json.loads(x) for x in
            defect_file.read_text(encoding='utf-8').splitlines() if x.strip()]
    artifacts = [r for r in rows
                 if r.get('reader_source') == 'bench_buy_pixel_diff'
                 and r.get('kind') == 'invariant_break']
    assert not artifacts, (
        f'缺陷流出现 bench 落位行 {len(artifacts)} 行'
        f'(结构性豁免被拆除/破缺):'
        f'{[r.get("expected") for r in artifacts[:3]]}')


def test_fake_p1_same_seed_bitwise_replay(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """验收①:同 seed + 同剧本两次全程驱动 → 轮轨迹逐位相等(金/账/
    结算/锚)。档案 ts 流不比对(时间戳域),轨迹真值域全比对。"""
    enter_running_state(test_context)
    try:
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=_SCRIPT, initial_gold=30,
                         archive_dir_name='run_a') as run:
            t1 = run.run_p1()
            audit1 = list(run.prep_audit)
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=_SCRIPT, initial_gold=30,
                         archive_dir_name='run_b') as run:
            t2 = run.run_p1()
            audit2 = list(run.prep_audit)
    finally:
        reset_running_state(test_context, test_context.cw_match)

    def _trace(res) -> list:
        rows = []
        for r in sorted(res.rounds):
            row = res.rounds[r]
            rows.append({
                'node': row['node'], 'income': row['income'],
                'gold_after_income': row['gold_after_income'],
                'gold_open': row['gold_open'],
                'gold_close': row['gold_close'],
                'total_buy': row['total_buy'],
                'total_level': row['total_level'],
                'total_refresh': row['total_refresh'],
                'total_sell': row['total_sell'],
                'spend_executed': row['spend_executed'],
                'settlement': (None if row['settlement'] is None else
                               (row['settlement'].node,
                                row['settlement'].delta,
                                row['settlement'].hp_after)),
            })
        return rows

    assert _trace(t1) == _trace(t2), '同 seed 假局轨迹逐位不等(确定性破缺)'

    # L-5 增强(删除波 1 重写):prep 动作身份序列(actions 名+落地位)
    # 两局逐位相等——「同计数不同身份」盲区封死(原 decisions 行 actions
    # 身份序列随写入端退役,审计账为身份载体)。
    def _actions_identity(audit) -> list:
        return [(e['action'], e['applied']) for e in audit]

    assert (_actions_identity(audit1) == _actions_identity(audit2)), (
        'prep 动作身份序列两局不等(同 seed 身份盲区破缺)')


# (2026-09-09 合并批:原 test_sink_ledger_matches_game_truth 按 DEBTS.md
#  D65 处置整测删除——单侧不等式 `_delta <= spent + 1`(+1 容差、不读
#  ledger 账、仅终局 gold≥0)是下方 test_fidelity_baseline_conservation_
#  domains_bands 面①双源严格恒等式的真子集(簇V 批逐对亲读两处断言面
#  证实),强锁为正主,期间无双留覆盖缺口。)


#: 保真基线批种子(原 test_cw_fidelity_baseline 迁入):显式固定保确定性,
#: 测试内 n = 守恒锁成立的最小值(纪律 12):3 seed × 5 节点已覆盖四类
#: 节点与胜负两态;保真度批 n≥40 的全量规格归离线 runner(sim-design
#: §4.2 复测规格),不进测试网。
_SEEDS: tuple[int, ...] = (11, 23, 57)


def _run_fidelity_batch(test_context: SrTestContext,
                        monkeypatch: pytest.MonkeyPatch,
                        tmp_path: Path) -> list[FakeP1Result]:
    """种子批驱动(同一 fixture 会话内共享 ctx;逐局隔离档案根)。"""
    results: list[FakeP1Result] = []
    enter_running_state(test_context)
    try:
        for i, seed in enumerate(_SEEDS):
            with fake_p1_run(test_context, monkeypatch, tmp_path, seed,
                             node_sequence=_SCRIPT,
                             initial_gold=30,
                             archive_dir_name=f'fidelity_{seed}_{i}') as run:
                results.append(run.run_p1())
    finally:
        reset_running_state(test_context, test_context.cw_match)
    return results


def test_fidelity_baseline_conservation_domains_bands(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """保真基线单批三面(原 test_cw_fidelity_baseline 整件并入,批 1
    验收③):①金恒等式(卖入双源同判,本文件账本位锁的正主);②轨迹
    域与开局先验;③对拍件(bands)形状。各面判据与红时语义见文件头。

    出处 = T-120 方案 v2(``.debug/temp/currency_war/t120_sim_redesign/
    方案.md``,**易失产物**)§5-5「环境保真度 = 新 sim 唯一质量指标」;
    分工申报随迁:假局 vs 实机近期局的分布带对比 = 离线 runner(批报告
    类、不入 git),不进测试网——实机档案是本地易失产物,读它当断言锚
    违测试纪律 19;本测只锁注册表/常量可推导的守恒面(纪律 9:期望值
    单一源现算)。种子批共享同一种子集,与上文确定性锁(验收①)同值域,
    逐测各跑一遍 = 同值重算,按纪律 11 收为一批。"""
    batch = _run_fidelity_batch(test_context, monkeypatch, tmp_path)
    # —— ①金恒等式(T-22 定谳重推辖域):商店窗恒等式归账本位检查卡
    # (test_fake_ledger_window_plan_vs_executed_zero_tolerance,窗口行
    # 恒等零容忍正锁;原「期末金 = 期初金 − spend_executed +
    # 卖入」按轮测量把关店后的备战域金动错并进窗口辖域——备战域金动
    # 现由备战域卡逐动作归属管辖,本面只保金非负底线)。
    # 卖入双源同判语义随迁窗口行(卖入账 == 状态机金账差分)。
    for res in batch:
        for r in sorted(res.rounds):
            row = res.rounds[r]
            close_gold = row['gold_close']
            assert close_gold >= 0
        # —— ②轨迹域:hp ∈ [0, HP_UPPER_BOUND];金轨迹恒非负;
        # 首轮结算前 hp = 开局先验(初值表,非真读——语义 = 环境初值)。
        for hp in res.hp_trajectory:
            assert 0 <= hp <= HP_UPPER_BOUND
        assert all(g >= 0 for g in res.gold_trajectory)
        assert res.rounds[1]['settlement'] is not None
        first = res.rounds[1]['settlement']
        assert first.hp_after == max(0, DEFAULT_OPENING_HP + first.delta)
    # —— ③对拍件形状:逐轮金/hp 的 (中位, p90) 带对种子批完整产出——
    # 离线 runner 消费的同一统计 helper(单一源 = fixtures.cw_harness.
    # bands_from_trajectories)。
    bands = bands_from_trajectories(
        [res.trajectory() for res in batch])
    assert set(bands) == set(range(1, len(_SCRIPT) + 1))
    for band in bands.values():
        assert set(band) == {'gold', 'hp'}
        for metric in ('gold', 'hp'):
            med, p90 = band[metric]
            assert med is not None and p90 is not None
            assert med <= p90


def _run_ledger_audit_batch(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> list[tuple[Any, FakeP1Result]]:
    """检查卡批驱动(保真基线批同种子同剧本;保留 run 对象供审计账)。"""
    runs: list[tuple[Any, FakeP1Result]] = []
    enter_running_state(test_context)
    try:
        for i, seed in enumerate(_SEEDS):
            with fake_p1_run(test_context, monkeypatch, tmp_path, seed,
                             node_sequence=_SCRIPT, initial_gold=30,
                             archive_dir_name=f'ledger_{seed}_{i}') as run:
                runs.append((run, run.run_p1()))
    finally:
        reset_running_state(test_context, test_context.cw_match)
    return runs


def test_fake_ledger_zero_tolerance_gold_attribution(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """T-22 常设检查卡·备战域金归属(零容忍,在册即红)。

    定谳口径(定谳记录 = .debug/progress/2026-09-11-cw-clear-run/
    reports/T-22-r1.md;权威 = game_state/fields.md §3.2.9/§3.2.11/
    §3.3.4 + ADR-0561 申报表 #5/#7 + ADR-0632;实扣规则单一源 =
    kernel ``cw_state.simulate`` 金差):执行账(spend_executed/total_*)
    = 计划口径账(Σ动作申报价),非金差观测账;假环境内合法差形态
    枚举 = ∅(无免费刷新通道/无 OCR 兜底/名册全注册表真值)→ 容忍
    恒 0,任何非零残差 = 真漏账。

    本测辖**备战域**(商店窗 plan-vs-实扣面见下方商店窗零容忍卡):
    ①逐动作归属:每审计行金差 == 归属值(prep 动作 = 执行点回执
      levelup_spent/球金/卖出 income;其余 = 0)——红 = 回执通道漏记
      或无主金动;
    ②相位闭合:gold_after_income→gold_close 全差 == Σ审计行金差
      ——红 = 审计链外无主金动(检查卡盲窗回潮);
    ③跨轮收入腿:上轮期末金 +Σincome == 本轮期初金(结算/推进零金动;
      invest 注入局 instant_gold 归选卡时点金,本卡辖无注入批)。
    原「open_gold is None 跳过」盲窗(prep 域金动不设防)由①②闭合
    ——删除波 1 报告 §五「升级连发成本差」显影位的立卡处置(prep 域
    pa.LevelUp 点击环 −Σxp_click_cost 现有归属可判,实判全绿)。
    """
    runs = _run_ledger_audit_batch(test_context, monkeypatch, tmp_path)
    violations: list[str] = []
    for run, res in runs:
        audit_by_round: dict[Any, list[dict]] = {}
        for e in run.prep_audit:
            audit_by_round.setdefault(e.get('round'), []).append(e)
        prev_close: int | None = 30   # initial_gold(批驱动同参)
        for r in sorted(res.rounds):
            row = res.rounds[r]
            moves = [e for e in audit_by_round.get(r, [])
                     if e['action'] != 'ShopVisit(env)']
            if not moves:
                violations.append(
                    f'seed={res.seed} r{r}: 审计行缺位(轮戳断线——'
                    '相位金动脱离账本位)')
                prev_close = row['gold_close']
                continue
            # ① 逐动作金归属(零容忍;商店窗行归商店窗零容忍卡辖)
            for e in moves:
                delta = e['post']['gold'] - e['pre']['gold']
                ch = e.get('gold_channel')
                if ch is None or delta != ch:
                    violations.append(
                        f"seed={res.seed} r{r}: {e['action']}"
                        f"(applied={e['applied']}) 金差 {delta} vs "
                        f'归属 {ch}')
            # ② 相位闭合(审计链外无主金动;全行含商店窗行——窗口行
            # 金差本身在审计链内,其 plan-vs-实扣残差归商店窗零容忍卡辖)
            phase_net = sum(e['post']['gold'] - e['pre']['gold']
                            for e in audit_by_round.get(r, []))
            truth_net = row['gold_close'] - row['gold_after_income']
            if truth_net != phase_net:
                violations.append(
                    f'seed={res.seed} r{r}: 备战相位存在无审计金动 '
                    f'{truth_net - phase_net}(审计账覆盖缺口)')
            # ③ 跨轮收入腿
            if prev_close is not None:
                leg = row['gold_after_income'] - prev_close
                if leg != sum((row['income'] or {}).values()):
                    violations.append(
                        f'seed={res.seed} r{r}: 收入腿分叉(金跳 {leg} '
                        f"vs 收入账 Σ{sum((row['income'] or {}).values())}"
                        ')')
            prev_close = row['gold_close']
    assert not violations, (
        'T-22 账本位零容忍检查卡红(备战域金归属残差逐条:'
        '定谳=假环境合法差集∅,非零即真漏账):\n' + '\n'.join(violations))


def test_fake_ledger_window_plan_vs_executed_zero_tolerance(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """T-22 常设检查卡·商店窗 plan账 vs 实扣(零容忍正锁;T-76 摘钉)。

    判据(定谳终态语义):每商店窗审计行 金差真值 == Σ窗内 outcome
    卖入 − Σ实扣申报——容忍 0(合法差形态枚举 = ∅,见备战域卡 docstring)。
    开窗无 outcome(窗内账丢)= 同罪判红。

    T-22 时点的红曾以 xfail(strict) 在册钉(定谳记录 = T-22-r1 报告
    §一.3);T-76 根因定谳摘钉转正锁:残差机制 = harness 捕获壳
    (``FakeP1Run._install_prep_patches`` 的 rbw 透传捕获)每轮
    run_prep_phase 重复安装、把上一轮捕获壳当原函数再包一层,一次物理
    run_buy_waves 执行的 outcome 被追加轮次号次,窗切片 Σspend = 轮次
    号×真值——production rbw 聚合与逐动作 sink 记账经探针定谳恒等,
    分叉不在生产层(逐窗残差 ×轮次 指纹全行成立 + 捕获链调用栈取证,
    定谳记录 = T-76-r1 报告)。修法 = 安装幂等闸(harness 单点)。
    红语义:窗口恒等破坏 = 真漏账(生产聚合/逐动作 sink/窗口配对切片
    三面任一分叉),零容忍禁回 xfail 吞新形态。
    """
    runs = _run_ledger_audit_batch(test_context, monkeypatch, tmp_path)
    violations: list[str] = []
    for run, res in runs:
        for e in run.prep_audit:
            if e['action'] != 'ShopVisit(env)':
                continue
            delta = e['post']['gold'] - e['pre']['gold']
            ch = e.get('gold_channel')
            if ch is None:
                violations.append(
                    f"seed={res.seed} r{e.get('round')}: 商店窗无 outcome "
                    f'账(窗金差真值 {delta}——花金账丢)')
            elif delta != ch:
                violations.append(
                    f"seed={res.seed} r{e.get('round')}: 商店窗 plan账"
                    f'vs实扣差 {delta - ch}(窗 spend='
                    f"{e['window_spend']} sold={e['window_sold']}"
                    f' 金差真值={delta})')
    assert not violations, (
        '商店窗 plan账vs实扣残差逐条(零容忍判据):\n' + '\n'.join(violations))


def test_fake_match_rules_streak_and_income() -> None:
    """回合规则单元锚(收入分解与连胜迁移的单一源推导,测试纪律 9):
    期望值全部从 kernel 常量表现算,零手抄分布值。"""
    from fixtures.cw_fake_game import rules

    from sr_od.application.currency_war.kernel.cw_economy import (
        LOSS_GOLD_BY_NODE,
        reward_base_gold,
        streak_gold,
    )

    m = FakeMatch(seed=7, node_sequence=['battle', 'battle', 'reward'])
    st = m.state
    st.gold = 100
    # 利息单一源现算:min(帽, 100//10)
    from sr_od.application.currency_war.kernel.cw_economy import interest
    inc = rules.income_for_round(st, m._rng_grant, None, False)
    # base = 平面感知键单一源(T-64 切源:原恒 BASE_INCOME=5 是 round
    # 单键同族第二值源,非奖励节点落 r1/r2 时与权威键分叉——battle@r1
    # 权威值 3;与 T-21 引擎侧校准同款)
    assert inc['base'] == reward_base_gold(st.plane, st.round_num)
    assert inc['interest'] == interest(100)
    assert inc['streak'] == streak_gold(0)
    # 败轮金:连胜归 0 + 上一战斗轮败 → LOSS_GOLD_BY_NODE[prev]
    st.streak = -1   # 连败态(带符号口径)
    inc2 = rules.income_for_round(st, m._rng_grant, 'battle', True)
    assert inc2['streak'] == LOSS_GOLD_BY_NODE['battle']
    # 胜态迁移:delta>0 → 正值域 +1;败态:负值域 −1;奖励轮不动
    st.streak = 2
    assert rules.settle_streak(st, 5, 'battle') == (3, False)
    st.streak = 2
    assert rules.settle_streak(st, -9, 'battle') == (-1, True)
    st.streak = 4
    assert rules.settle_streak(st, -3, 'reward') == (4, False)


def test_income_event_component_stays_zero() -> None:
    """收入事件金分量恒 0 登记门(防残差闸回潮;保真校准裁定,出处 =
    ``.debug/temp/currency_war/t120_sim_redesign/保真度校准.md``)。

    机制真值 = 结算金币明细弹窗三分量全集(基础+利息+连胜,
    docs/game/currency_war/research/economy.md §11)——无「事件金」
    第四分量;奖励球金是备战期收球动作(prep 编排域,假环境观察面
    spheres 结构性为零,归批 2)。引擎 ``EVENT_GOLD_BY_ROUND`` 是
    ADR-0447 残差补偿闸(该表 docstring 明文「策略面修复后不得以此表
    回填」),非节点事件金真值。

    锁红时该登记的语义:有人把事件金分量接回非机制真值源(残差闸
    回潮),或批 2 球金建模提前走了旧表——处理 = 按球真值另行建模,
    禁回指残差表(错误信息已指名,非裸 assert)。"""
    from fixtures.cw_fake_game import rules

    m = FakeMatch(seed=7, node_sequence=['battle', 'reward', 'supply'])
    st = m.state
    st.gold = 100
    st.streak = 3
    for node, rn in (('battle', 3), ('reward', 8), ('supply', 5)):
        st.node_type = node
        st.round_num = rn
        inc = rules.income_for_round(st, m._rng_grant, None, False)
        assert 'event' in inc, '收入分解缺 event 键(账本口径面变)'
        assert inc['event'] == 0, (
            f'{node} 轮事件金非 0(残差闸回潮/球金未按真值建模):'
            f'{inc["event"]}——处理 = 按球真值另行建模,禁回指 '
            f'EVENT_GOLD_BY_ROUND 残差闸')


def test_fake_income_base_plane_aware_no_single_key_hazard() -> None:
    """假环境收入 base = 平面感知键单一源回归锁(T-64 切源,T-21 引擎
    侧同款收口)。

    被禁形态 = 奖励轮按 round_num 单键直查注册表(fields.md §4.2
    奖励轮行明文禁用):P2r1/P3r1 会误返 3——本锁钉 P2r1/P3r1=5、
    P1 r1/r2 成对 3/4、非奖励轮同款键;期望值经 kernel reward_base_gold
    现算(纪律 9),末尾注册表锚自检区分「注册表值变了」还是「切源
    回退了」。"""
    from fixtures.cw_fake_game import rules

    from sr_od.application.currency_war.kernel.cw_economy import (
        reward_base_gold,
    )

    m = FakeMatch(seed=31, node_sequence=['reward'])
    st = m.state
    for plane, rn in ((2, 1), (3, 1), (1, 1), (1, 2), (1, 8)):
        st.plane = plane
        st.round_num = rn
        st.node_type = 'reward'
        inc = rules.income_for_round(st, m._rng_grant, None, False)
        assert inc['base'] == reward_base_gold(plane, rn), \
            (plane, rn, '假环境 base 未走平面感知键单一源')
    # 非奖励轮同款键(恒 BASE_INCOME 第二值源形态禁回潮)
    st.plane, st.round_num, st.node_type = 1, 1, 'battle'
    assert rules.income_for_round(
        st, m._rng_grant, None, False)['base'] == reward_base_gold(1, 1)
    # 注册表锚自检(hazard 值锚:P2r1/P3r1=5 是单键直查会失真的点)
    assert reward_base_gold(2, 1) == 5, 'P2r1 注册表锚漂移'
    assert reward_base_gold(3, 1) == 5, 'P3r1 注册表锚漂移'
    assert (reward_base_gold(1, 1), reward_base_gold(1, 2)) == (3, 4), \
        'P1 r1/r2 注册表锚漂移'


class TestPrepEntryObserveViaPorts:
    """备战入口 heavy 观察改道锁(方案 §2.3 表消费点;批 1 改道清单)。

    红 = 端口分支断线(observe 没走端口/装配半部 session 写点缺席)。
    """

    def test_heavy_observe_reads_ports_and_writes_session(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from fixtures.cw_fake_game.fake_ports import (
            FakeActionSink,
            FakeCwObserver,
        )

        from sr_od.application.currency_war import cw_game_ports
        from sr_od.application.currency_war.kernel.cw_state import (
            BenchChar,
        )
        from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
            CwScreenPrep,
        )

        m = FakeMatch(seed=5, node_sequence=['battle'])
        m.state.gold = 66
        m.state.hp = 55
        # 假局 bench 真值:2 个占用 + 7 空(heavy 字段填充的判据面)
        m.state.bench = [BenchChar(slot=1, char_id='希儿', faction='?'),
                         BenchChar(slot=2, char_id='景元', faction='?')]
        m.state.deployed = []
        # session 写点断言的载体(装配半部消费 ctx.cw_match)
        from sr_od.application.currency_war.strategies.impl.cw_strategy import (
            CurrencyWarMatch,
            StrategySession,
        )
        monkeypatch.setattr(test_context, 'cw_match',
                            CurrencyWarMatch(None, StrategySession()))
        cw_game_ports.install_game_ports(FakeCwObserver(m),
                                         FakeActionSink(m))
        try:
            prep = CwScreenPrep(test_context)
            monkeypatch.setattr(prep, 'screenshot',
                                lambda: None)   # 端口路径零读屏,帧不应被消费
            obs = prep._observe(heavy=True)
            # 端口真值直出(非读屏桩):金/hp/bench 身份来自状态机
            assert obs.state is not None
            assert obs.state.gold == 66 and obs.state.hp == 55
            assert [b.char_id for b in obs.bench_chars] == ['希儿', '景元']
            assert obs.free_bench_slots == 7
            assert obs.state.deploy_cap == obs.state.level   # cap=level 真值规则
            # 装配半部 session 写点(与读屏路径同语义)
            session = test_context.cw_match.session
            assert session.last_state is obs.state
            assert session.prep_obs_frame is obs
            # 观察留痕(读屏次数语义保留):入口观察留痕在案
            assert any(e.method == 'observe_prep'
                       for e in m.observation_log)
        finally:
            cw_game_ports.uninstall_game_ports()

    def test_visit_open_shop_drives_fake_round(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """M1 补锁:visit_open_shop 假局全链(方案批 1 行第二入口形)。

        驱动面 = 入口观察(端口)→ run_buy_waves(端口)→ close_shop
        点击壳(区域原语桩,壳逻辑真跑)→ finalize_buy_phase(三处
        gold 读喂假局真值)→ 节点探针。判据:
        ①访问成功收尾;②关店规则已落(画面身份回备战);③金账守恒
        (期末金非负且不低于期初−花销+卖入 − 容差;原关店金收口槽为删除波 1
        退役的暂存面,守恒断言改锚状态机期末值);④缺陷流零 bench 桩伪影
        (M2 共用断言)。
        """
        from fixtures.cw_fake_game.fake_match import PHASE_PREP

        enter_running_state(test_context)
        try:
            with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                             node_sequence=['battle'], initial_gold=30,
                             archive_dir_name='visit') as run:
                ok, detail, info = run.run_visit(monkeypatch, tmp_path)
            assert ok, f'visit_open_shop 未成功收尾:{detail!r}'
            assert info['phase'] == PHASE_PREP, (
                f'关店规则未落(画面身份={info["phase"]})')
            # 金账守恒:期末金非负(visit 账无断链)
            assert run.match.state.gold >= 0, (
                f'visit 后状态机金为负(账断链):{run.match.state.gold}')
            _assert_no_pixel_diff_artifacts(tmp_path / 'visit')
        finally:
            reset_running_state(test_context, test_context.cw_match)
