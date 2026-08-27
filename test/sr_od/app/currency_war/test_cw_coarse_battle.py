"""粗参数两态战斗模型锁(cw_coarse_battle)。

设计单一源 = 粗参数胜负感知模型设计(冻结语料 417 条战斗差分拟合;
机器版数字 = 拟合产物 fit_results.json two_state_model /
win_rate_table_injected)。本文件锁:

1. 胜率表交付口径 = Beta 收缩注入值(逐单元对拍拟合产物);
2. 先验份额帽(≤25%)/等效样本帽(≤12)硬顶;
3. 两态采样行为(胜 +2 / 败态直方采样 + rung 均值匹配 + 地板);
4. boss 钳制条件化(hp_before≤35 门 + 区间内钳制率,>35 不钳);
5. 难度乘子:默认关闭(A8),开关置位后按 1.052^(Δ难度) 生效;
6. 引擎开关双模式(coarse 默认 / delta 对照臂),reward/supply 两
   模式下均仍走 Δ池(实现批裁决保留)。

纪律:单点行为用脚本化 rng 桩(确定性,不锁频率分布);批量模拟
只跑 1 局冒烟(契约锁不锁分布数值)。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war import cw_coarse_battle as cb
from sr_od.application.currency_war import cw_sim

# 拟合产物交付口径(逐单元;粗模型参数的机器可读真值,
# 来源 = 冻结语料拟合,禁与其它口径混写)
_DELIVERY_WIN_P: dict[str, dict[int, float]] = {
    'battle': {0: 0.009, 1: 0.356, 2: 0.315, 3: 0.292},
    'encounter': {0: 0.038, 1: 0.026, 2: 0.264, 3: 0.275},
    'boss': {0: 0.077, 1: 0.027, 2: 0.187, 3: 0.238},
}


class _ScriptRng:
    """脚本化 rng 桩:random() 返回定值;choices 返回定值档。"""

    def __init__(self, uniform: float, pick: int) -> None:
        self._uniform = uniform
        self._pick = pick

    def random(self) -> float:
        return self._uniform

    def choices(self, vals, weights=None, k: int = 1):  # type: ignore[no-untyped-def]
        return [self._pick]


def test_win_p_table_matches_delivery() -> None:
    """胜率表逐单元 = 拟合产物交付口径(含 Beta 收缩注入值)。"""
    for node, rows in _DELIVERY_WIN_P.items():
        for rung, p in rows.items():
            assert cb.injected_win_p(node, rung) == pytest.approx(p)


def test_rung01_cells_not_injected() -> None:
    """rung0/1 单元遥测样本充足,不注入(份额 0,值 = p_data)。"""
    for node, cell in cb._WIN_TABLE.items():
        for rung in (0, 1):
            n, p_data = cell[rung]
            assert cb.prior_share(node, rung) == 0.0
            assert cb.injected_win_p(node, rung) == p_data
            assert n > 0


def test_prior_share_hard_caps() -> None:
    """先验份额恒 ≤25%、等效样本恒 ≤12(裸收缩口径禁止)。"""
    for node in cb._WIN_TABLE:
        for rung in (2, 3):
            share = cb.prior_share(node, rung)
            assert 0.0 < share <= cb.PLAZA_SHARE_MAX + 1e-12
            n = cb._WIN_TABLE[node][rung][0]
            alpha = share * n / (1 - share)
            assert alpha <= cb.ALPHA_CAP + 1e-9
    # 值锁两例(份额帽在薄/厚单元的两个端型):
    assert cb.prior_share('battle', 2) == pytest.approx(0.203, abs=1e-3)
    assert cb.prior_share('battle', 3) == pytest.approx(0.25, abs=1e-9)


def test_win_state_plus2() -> None:
    """胜态:均匀抽样 < P(win) → delta = +2(封顶,池语料主型)。"""
    assert cb.sample_battle_delta(
        'battle', 1, 80, _ScriptRng(0.1, 13)) == cb.WIN_CAP


def test_loss_mean_match_and_floor() -> None:
    """败态:battle 直方采样 + rung 均值匹配取整;hp 地板 = max(1,·)。"""
    # rung0:13 + (11.32 − 0 − 11.07) = 13.25 → 13
    assert cb.sample_battle_delta(
        'battle', 0, 100, _ScriptRng(0.99, 13)) == -13
    # rung3:13 + (11.32 − 1.11 − 11.07) = 12.14 → 12(rung 梯度生效)
    assert cb.sample_battle_delta(
        'battle', 3, 100, _ScriptRng(0.99, 13)) == -12
    # 地板:伤害越过 HP → hp_after 落吸收态 1
    assert cb.sample_battle_delta(
        'battle', 0, 5, _ScriptRng(0.99, 88)) == -(5 - 1)
    # 直方支持域:采样结果必落在合法区间(固定种子扫 200 次)
    rng = random.Random(20260901)
    for _ in range(200):
        r = cb.sample_battle_delta('encounter', 1, 200, rng)
        assert r <= -1 or r == cb.WIN_CAP  # 败态伤害 / 胜态回血两态


def test_boss_clamp_conditional_on_hp_before() -> None:
    """boss 钳制按 hp_before 条件化:≤35 门 + 区间内 0.929;>35 不钳。"""
    # ≤35 且区间内抽中钳制 → 归吸收态(不经伤害直方/乘子)
    assert cb.sample_battle_delta(
        'boss', 1, 30, _ScriptRng(0.1, 36)) == -(30 - 1)
    # ≤35 但区间内抽中不钳 → 直方采样 + 地板兜底(结构性双路径)
    assert cb.sample_battle_delta(
        'boss', 1, 20, _ScriptRng(0.999, 14)) == -(20 - 6)
    # >35:钳制分支结构性不可达(即使钳制抽签必中)——0.929 只辖低 HP
    # (uniform 0.5 = 败态且 >35 门直接跳过钳制分支)
    assert cb.sample_battle_delta(
        'boss', 1, 40, _ScriptRng(0.5, 36)) == -36


def test_difficulty_multiplier_off_by_default() -> None:
    """难度乘子未核先验默认关闭:difficulty 取值不影响采样结果。"""
    rng_a = random.Random(7)
    rng_b = random.Random(7)
    for _ in range(50):
        a = cb.sample_battle_delta('boss', 2, 60, rng_a, difficulty=200)
        b = cb.sample_battle_delta('boss', 2, 60, rng_b, difficulty=None)
        assert a == b


def test_difficulty_multiplier_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """开关置位后:伤害按 1.052^(Δ难度) 缩放(A8 基准 108 不缩放)。"""
    monkeypatch.setattr(cb, 'DIFFICULTY_MULT_ENABLED', True)
    base = cb.sample_battle_delta(
        'boss', 1, 60, _ScriptRng(0.99, 36), difficulty=108)
    assert base == -36
    up = cb.sample_battle_delta(
        'boss', 1, 60, _ScriptRng(0.99, 36), difficulty=109)
    assert up == -round(36 * 1.052 ** 1)


def test_engine_switch_dual_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """引擎开关:coarse 走粗模型;delta 臂走 Δ池;reward/supply 恒 Δ池。"""
    coarse_calls: list[str] = []
    monkeypatch.setattr(
        cb, 'sample_battle_delta',
        lambda node, rung, hp, rng, **kw: coarse_calls.append(node) or 0)
    pool_calls: list[str] = []
    _orig_ldf = cw_sim.live_delta_for

    def _spy_ldf(node: str, key: int, rng, **kw):  # type: ignore[no-untyped-def]
        pool_calls.append(node)
        return _orig_ldf(node, key, rng, **kw)

    monkeypatch.setattr(cw_sim, 'live_delta_for', _spy_ldf)

    monkeypatch.setattr(cb, 'BATTLE_ENGINE_MODE', 'coarse')
    r1 = cw_sim.simulate_p1(0, pool='snapshot')
    assert coarse_calls, 'coarse 默认:战斗类节点必走粗模型'
    assert not (set(coarse_calls) & {'reward', 'supply'})
    assert {'reward', 'supply'} <= set(pool_calls), 'reward/supply 仍走 Δ池'

    monkeypatch.setattr(cb, 'BATTLE_ENGINE_MODE', 'delta')
    coarse_calls.clear()
    pool_calls.clear()
    r2 = cw_sim.simulate_p1(0, pool='snapshot')
    assert not coarse_calls, 'delta 对照臂:粗模型不被消费'
    assert 'battle' in pool_calls, 'delta 臂:战斗类节点回 Δ池经验分布'
    assert r1.seed == r2.seed


def test_coarse_game_smoke_snapshot_fingerprint() -> None:
    """冒烟:coarse 模式整局可跑、hp 轨迹合法、池指纹照常随局携带
    (reward/supply 池消费与基准对拍依赖指纹披露)。"""
    r = cw_sim.simulate_p1(1, pool='snapshot')
    assert r.hp_trail
    assert all(0 <= h <= 100 for h in r.hp_trail)
    assert r.pool_fingerprint == cw_sim.pool_fingerprint(
        cw_sim.resolve_pool('snapshot')[0])
