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
   模式下均仍走 Δ池(实现批裁决保留);
7. 位面维(P1 先行形态):P1 层 = 冻结语料拟合现值逐位(零漂移锁);
   P2 层 = 显式别名指向 P1(别名锁);校准结构版本披露锁。

纪律:单点行为用脚本化 rng 桩(确定性,不锁频率分布);批量模拟
只跑 1 局冒烟(契约锁不锁分布数值)。
"""
from __future__ import annotations

import json
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


# 位面维前 = 冻结语料拟合交付值(位面化 P1 层零漂移锁的逐位真值;
# 与上方 _DELIVERY_WIN_P 同源:冻结语料 417 条战斗差分拟合产物)
_DELIVERY_LOSS_HIST: dict[str, dict[int, int]] = {
    'battle': {-64: 1, -43: 1, -42: 1, 1: 7, 3: 3, 4: 9, 5: 10, 6: 5,
               7: 2, 8: 19, 9: 11, 10: 6, 11: 18, 12: 6, 13: 74, 14: 1,
               15: 9, 17: 3, 18: 3, 19: 4, 20: 2, 21: 4, 23: 2, 46: 1,
               84: 1, 88: 1},
    'encounter': {4: 1, 5: 1, 6: 4, 7: 1, 8: 4, 9: 7, 10: 10, 15: 1,
                  17: 1, 18: 1, 22: 1, 24: 11, 26: 7, 28: 15, 45: 2,
                  83: 2},
    'boss': {3: 1, 11: 2, 12: 1, 13: 2, 14: 4, 30: 1, 32: 5, 34: 11,
             36: 8},
}
_DELIVERY_LOSS_FIT: dict[str, tuple[float, float, float]] = {
    'battle': (11.32, -0.37, 11.07),
    'encounter': (24.32, -4.53, 20.71),
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
    for node, planes in cb._WIN_TABLE.items():
        for rung in (0, 1):
            n, p_data = planes[1][rung]
            assert cb.prior_share(node, rung) == 0.0
            assert cb.injected_win_p(node, rung) == p_data
            assert n > 0


def test_prior_share_hard_caps() -> None:
    """先验份额恒 ≤25%、等效样本恒 ≤12(裸收缩口径禁止)。"""
    for node in cb._WIN_TABLE:
        for rung in (2, 3):
            share = cb.prior_share(node, rung)
            assert 0.0 < share <= cb.PLAZA_SHARE_MAX + 1e-12
            n = cb._WIN_TABLE[node][1][rung][0]
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


# ===== 位面维(P1 先行)锁:结构见 test_cw_w405_planarize 说明 =====


def test_p1_layer_zero_drift_literals() -> None:
    """P1 层零漂移锁:三表 plane 1 逐位 = 冻结语料拟合交付值。

    位面化只加结构不改数:P1 层是 W346 一阶矩门 + W377 剂量曲线
    三方一致的载体,任何 P1 数值变动必须走显式重校准批(禁止顺手调)。
    """
    for node, hist in _DELIVERY_LOSS_HIST.items():
        assert cb._LOSS_HIST[node][1] == hist
    for node, fit in _DELIVERY_LOSS_FIT.items():
        assert cb._LOSS_FIT[node][1] == fit
    for node, rungs in _DELIVERY_WIN_P.items():
        for rung, p in rungs.items():
            assert cb.injected_win_p(node, rung, plane=1) == \
                pytest.approx(p)


def test_p2_alias_lock() -> None:
    """P2 别名锁:别名表显式指向 plane 1,取表回同一对象(不拷贝)。

    P2 未采样,别名即「已知偏差」的机器可读声明(W357 regate:
    boss +4.57 hp / 钳制率 −38.81 pp / encounter 钳制率 −6.19 pp
    为继承的现状,非本结构引入);未来 P2 语料换表只动 plane 2 槽位。
    """
    assert set(cb._P2_ALIAS) == {'battle', 'encounter', 'boss'}
    for node, aliased in cb._P2_ALIAS.items():
        assert aliased == 1
        assert cb._node_table(cb._LOSS_HIST, node, 2) \
            is cb._LOSS_HIST[node][1]
        assert cb._node_table(cb._WIN_TABLE, node, 2) \
            is cb._WIN_TABLE[node][1]
    # _LOSS_FIT 无 boss 条目(斜率 CI 含 0 退常数,不做均值匹配),
    # 别名断言只辖 battle/encounter
    for node in ('battle', 'encounter'):
        assert cb._node_table(cb._LOSS_FIT, node, 2) \
            is cb._LOSS_FIT[node][1]
    # 钳制参数:P2 别名同值
    assert cb._boss_clamp_params(2) == cb._boss_clamp_params(1) \
        == (cb.BOSS_CLAMP_HP_CUT, cb.BOSS_CLAMP_P_LOW)
    # 未声明位面(如 3)按别名链落到 plane 1,不 KeyError
    assert cb._node_table(cb._LOSS_HIST, 'boss', 3) is cb._LOSS_HIST['boss'][1]
    # 行为面:同 seed 下 plane=2 与 plane=1 采样逐位一致
    for node in ('battle', 'encounter', 'boss'):
        rng_a = random.Random(11)
        rng_b = random.Random(11)
        for _ in range(30):
            a = cb.sample_battle_delta(node, 2, 60, rng_a, plane=1)
            b = cb.sample_battle_delta(node, 2, 60, rng_b, plane=2)
            assert a == b
        assert cb.injected_win_p(node, 2, plane=2) \
            == cb.injected_win_p(node, 2, plane=1)
        assert cb.prior_share(node, 2, plane=2) \
            == cb.prior_share(node, 2, plane=1)


def test_default_plane_keeps_signature_compatible() -> None:
    """旧调用面零漂移:不传 plane 的三函数全部等价于 plane=1。"""
    rng_a = random.Random(23)
    rng_b = random.Random(23)
    for node in ('battle', 'encounter', 'boss'):
        for rung in range(4):
            assert cb.injected_win_p(node, rung) \
                == cb.injected_win_p(node, rung, plane=1)
            assert cb.prior_share(node, rung) \
                == cb.prior_share(node, rung, plane=1)
        for _ in range(20):
            a = cb.sample_battle_delta(node, 1, 70, rng_a)
            b = cb.sample_battle_delta(node, 1, 70, rng_b, plane=1)
            assert a == b


def test_coarse_calib_version_disclosed_in_ledger_manifest(
        monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """版本披露锁:COARSE_CALIB_VERSION=2 且进 sim 台账 manifest。

    DESIGN §验证:局终指纹核对锚——防止「结构改了、披露没跟上」的
    跨版本对比污染;回归批脚本头部按本常量断言版本号。
    """
    assert cb.COARSE_CALIB_VERSION == 2
    r = cw_sim.simulate_p1(1, pool='snapshot')
    out = cw_sim.write_batch_ledger([r], tmp_path / 'batch')
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['coarse_calib_version'] == cb.COARSE_CALIB_VERSION
