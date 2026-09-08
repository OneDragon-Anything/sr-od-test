"""保真度对拍基线锁(T-120 sim 重设计 批 1 验收③的测试内半边)。

出处 = T-120 方案 v2(``.debug/temp/currency_war/t120_sim_redesign/
方案.md``,**易失产物**)§5-5「环境保真度 = 新 sim 唯一质量指标」+
§6.2 批 1 验收③;锚 = Δ池快照指纹 460e6031e2f4ae06(T-119 提交触发
再生后的当前真值锚;前值 a0722904dea13294 为 ADR-0582 时代历史)。
ADR 落点待 T-120 退役批分配,后续批回填编号。

**分工申报**:本文件锁「假局产出的事实流自洽 + 对拍件可用」;假局 vs
实机近期局的分布带对比 = 离线 runner(``.debug/temp/currency_war/
t120_sim_redesign/保真度基线/`` 产物,批报告类、不入 git),不进测试网
——实机档案是本地易失产物,读它当断言锚违测试纪律 19。sim-design
§4.2 权威源序(live 实测 > 代码注册表 > sim 自身)在 runner 内承载;
本测试内半边只锁注册表/常量可推导的守恒面(纪律 9:期望值单一源现算)。

锁的语义(单测三面共享同一种子批:批次确定性(同 seed 同剧本逐位
复现,test_cw_fake_p1_segment 验收①)使逐测各跑一遍 = 同值重算,
按纪律 11「昂贵计算同次运行内只算一次」收为一批):

- **环境守恒锁**:全程任意轮「期初金 − 花销账 + 卖入 = 期末金」严格
  成立(花销账 = spend_executed,卖入 = 状态机口径;simulate 的金
  转移是唯一金源,账目漂移 = sink 账本位或环境规则破缺);
- **轨迹域锁**:金轨迹非负、hp 轨迹在 [0, HP_UPPER_BOUND](ADR-0287
  上界)且开局 = OPENING_HP_BASE(初值表先验,ADR-0559);
- **对拍件形状锁**:基线统计件(逐轮金/hp 中位与 p90)对种子批产出
  完整形状——离线 runner 消费的同一 helper,红 = 对拍件断线。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fixtures.cw_fake_game.fake_match import (
    DEFAULT_OPENING_HP,
    HP_UPPER_BOUND,
)
from fixtures.cw_harness import (
    FakeP1Result,
    bands_from_trajectories,
    fake_p1_run,
)

from test.conftest import SrTestContext
from test.harness.fixture_controller import enter_running_state, reset_running_state

#: 剧本 = P1 全段 9 节点采样序(sample_node_sequence 真码形态的代表;
#: 显式固定保确定性,替代采样)——保真度批 n≥40 的全量规格归离线
#: runner(sim-design §4.2 复测规格),测试内 n = 守恒锁成立的最小值
#: (纪律 12):3 seed × 5 节点已覆盖四类节点与胜负两态。
_SEEDS: tuple[int, ...] = (11, 23, 57)
_SCRIPT: list[str] = ['battle', 'reward', 'battle', 'supply', 'boss']
_INITIAL_GOLD: int = 30


def _run_batch(test_context: SrTestContext,
               monkeypatch: pytest.MonkeyPatch,
               tmp_path: Path) -> list[FakeP1Result]:
    """种子批驱动(同一 fixture 会话内共享 ctx;逐局隔离档案根)。"""
    results: list[FakeP1Result] = []
    enter_running_state(test_context)
    try:
        for i, seed in enumerate(_SEEDS):
            with fake_p1_run(test_context, monkeypatch, tmp_path, seed,
                             node_sequence=_SCRIPT,
                             initial_gold=_INITIAL_GOLD,
                             archive_dir_name=f'fidelity_{seed}_{i}') as run:
                results.append(run.run_p1())
    finally:
        reset_running_state(test_context, test_context.cw_match)
    return results


def test_fidelity_baseline_conservation_domains_bands(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """单批三面:①金恒等式(卖入双源同判);②轨迹域与开局先验;
    ③对拍件(bands)形状。各面判据与红时语义见模块头「锁的语义」。"""
    batch = _run_batch(test_context, monkeypatch, tmp_path)
    # —— ①金恒等式:任意轮 期末金 = 期初金 − spend_executed + 卖入 ——
    # 卖入双源同判:ledger 账(sink 落 BuyCardsOutcome.total_sell_income,
    # 来源 = ExecResult.income 执行点真值)必须等于状态机金账差分
    # (spend − (期初 − 期末))——两源不一致 = sink 账本位与游戏真值分叉。
    for res in batch:
        for r in sorted(res.rounds):
            row = res.rounds[r]
            open_gold = row['gold_open']
            close_gold = row['gold_close']
            spent = row['spend_executed']
            if open_gold is None:
                continue
            sold_by_ledger = row['total_sell_income']
            sold_by_truth = spent - (open_gold - close_gold)
            assert sold_by_truth >= 0, (
                f'seed={res.seed} r{r}:金凭空减少(期初 {open_gold} → '
                f'期末 {close_gold},花销账 {spent})')
            assert sold_by_ledger == sold_by_truth, (
                f'seed={res.seed} r{r}:卖入双源分叉(ledger='
                f'{sold_by_ledger},状态机差分={sold_by_truth})')
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
