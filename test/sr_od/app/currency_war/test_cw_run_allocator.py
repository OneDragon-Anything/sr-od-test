"""cw_run_allocator(05 号跨局分配层 v0)测试:Thompson/先验封顶/分级奖励/salvage(ADR-0170)。"""
import random

from sr_od.application.currency_war.cw_run_allocator import (
    PRIOR_CAP,
    StrategyArm,
    ThompsonAllocator,
)


def _alloc(seed=0):
    return ThompsonAllocator.from_plaza(
        {'列车同行': 0.5, '万敌': 0.2, '量子': 0.1, '仙舟': 0.08}, seed=seed)


def test_prior_cap_survivorship_bias():
    """plaza 先验封顶:伪计数 ≤ PRIOR_CAP(幸存者偏差只配弱先验)。"""
    alloc = _alloc()
    for a in alloc.arms.values():
        assert a.alpha + a.beta <= PRIOR_CAP + 1e-6


def test_thompson_select_respects_forbid_and_forced():
    """方向盘:forbid 过滤;forced(成就/handoff)豁免。"""
    alloc = _alloc(seed=1)
    assert alloc.select(forbidden={'列车同行', '万敌', '量子', '仙舟'}) is None
    for _ in range(20):
        k = alloc.select(forbidden={'列车同行'})
        assert k != '列车同行'
    assert alloc.select(forced='仙舟') == '仙舟'


def test_update_moves_posterior():
    """更新:连赢 → 均值上升;adherence 加权(半途而废的局贡献打折)。"""
    alloc = _alloc()
    m0 = alloc.arms['万敌'].mean
    for _ in range(10):
        alloc.update('万敌', 1.0)
    assert alloc.arms['万敌'].mean > m0
    # 遵从度 0.3 的局:alpha 增量 = 0.3(浮点容差)
    a_before = alloc.arms['量子'].alpha
    alloc.update('量子', 1.0, adherence=0.3)
    assert abs(alloc.arms['量子'].alpha - a_before - 0.3) < 1e-6


def test_graded_reward_variance_reduction():
    """分级奖励:输局按进度给分(到达 P3 输 > P1 输);win=1。"""
    alloc = _alloc()
    assert alloc.reward_graded(True, 3) == 1.0
    r_p3 = alloc.reward_graded(False, plane_reached=3)
    r_p1 = alloc.reward_graded(False, plane_reached=1)
    assert 0 < r_p1 < r_p3 < 0.5


def test_salvage_triggers_on_dead_runs_only():
    """必死局回收:P(win)≥ε 不触发;<ε 触发并选方差最大臂 + 审计留证。"""
    alloc = _alloc(seed=2)
    assert alloc.dead_run_salvage(0.30) is None      # 还有救
    # 拉开方差:列车加自家样本(方差收窄),量子保持宽
    for _ in range(15):
        alloc.update('列车同行', 1.0)
    k = alloc.dead_run_salvage(0.02)
    assert k is not None and k != '列车同行'          # 选宽方差臂(量子/仙舟/万敌)
    assert len(alloc.salvage_log) == 1
    assert alloc.salvage_log[0]['p_win'] == 0.02


def test_convergence_to_best_arm():
    """机制 sanity:后验集中后 Thompson 自动退化为总选最优(层自己关自己)。"""
    alloc = _alloc(seed=3)
    # 合成环境:列车真胜率 0.8,其他 0.3
    env = {'列车同行': 0.8, '万敌': 0.3, '量子': 0.3, '仙舟': 0.3}
    rng = random.Random(99)
    for _ in range(120):
        k = alloc.select()
        won = rng.random() < env[k]
        alloc.update(k, alloc.reward_graded(won, 3 if won else 2))
    # 后 30 局绝大多数应选列车
    picks = [alloc.select() for _ in range(30)]
    assert picks.count('列车同行') >= 25
    assert alloc.arms['列车同行'].mean > 0.6
