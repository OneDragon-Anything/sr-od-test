"""sim 投资 offer 引擎(M11/M02)回归锁(sim 后端规则件)。

锁面 = U07 固定日程(P1r3/P2r2/P3r2 + 联席决策 2-6 额外槽)/U07③ 候选
结构(品质→池取样、offer 内去重、全程不重复)/U08 环境 offer 同构
3 选 1/品质分布显式常量占位。选卡入账腿 = kernel 获得链(锁面迁
test_cw_sim_backend.py,注入核随退役删除);品质覆写名单常量位 =
kernel cw_investments。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_ENVS,
    INVESTMENT_STRATEGIES,
    QUALITY_REWRITE_ENV_NAMES,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    INVEST_OFFER_SCHEDULE,
    JOINT_DECISION_ENV_NAME,
    OFFER_CANDIDATES,
    QUALITY_DISTRIBUTION,
    offer_slots,
    quality_rewrite_hit,
    sample_env_offer,
    sample_strategy_offer,
)


def _gs() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


# ============================================================ 固定日程(U07①)

def test_offer_schedule_fixed_slots_u07() -> None:
    """U07①:固定轮次 P1r3/P2r2/P3r2 各一次;日程外轮无槽。"""
    assert INVEST_OFFER_SCHEDULE == ((1, 3), (2, 2), (3, 2))
    for plane, rnd in INVEST_OFFER_SCHEDULE:
        assert offer_slots(plane, rnd, None)
    for plane, rnd in ((1, 1), (1, 2), (1, 4), (2, 1), (2, 3), (2, 5)):
        assert not offer_slots(plane, rnd, None), (plane, rnd)


def test_joint_decision_extra_slot_env_gated() -> None:
    """联席决策(id122)→ 2-6 额外策略槽;环境不在场无额外槽。"""
    assert not offer_slots(2, 6, None), '无环境时 2-6 无槽'
    assert not offer_slots(2, 6, '轮岗'), '非联席决策环境无额外槽'
    assert offer_slots(2, 6, JOINT_DECISION_ENV_NAME), '联席决策 2-6 额外槽'


# ============================================================ 候选生成(U07③)

def test_strategy_offer_shape_and_lifelong_dedup() -> None:
    """候选 = 3 张、互不重名、全在注册表;排除集(全程去重)同规则
    排除旧选项——刷新重掷不再出已出名(U07③)。"""
    rng = random.Random(20260915)
    excluded: set[str] = set()
    seen: list[str] = []
    for _ in range(40):
        picks = sample_strategy_offer(rng, excluded)
        assert len(picks) == OFFER_CANDIDATES
        assert len(set(picks)) == OFFER_CANDIDATES, 'offer 内去重'
        for name in picks:
            assert name in INVESTMENT_STRATEGIES
            assert name not in excluded, '全程不重复(已出选项不再入 offer)'
            excluded.add(name)
        seen.extend(picks)
    assert len(set(seen)) == len(seen)


def test_strategy_offer_quality_distribution_uniform_placeholder() -> None:
    """品质掷点占位 = 三档均匀(显式常量,候实机回填):n=900 候选下
    各档频率锁 1/3±6σ 宽带(σ=sqrt(p(1-p)/n),禁卡边)。

    统计面用逐 offer 独立排除集(只锁 offer 内去重):全程去重累计
    集会在 ~111 个 offer 处吃光 335 张注册表 → 采样不足死等;品质掷点
    分布与排除集大小无关,独立集不影响本锁面(全程去重另测)。
    """
    rng = random.Random(77)
    counts = {'银': 0, '金': 0, '棱彩': 0}
    n = 0
    while n < 900:
        picks = sample_strategy_offer(rng, ())
        assert len(picks) == OFFER_CANDIDATES
        for name in picks:
            counts[INVESTMENT_STRATEGIES[name].rarity] += 1
            n += 1
    for quality, count in counts.items():
        p = count / n
        sigma = (1.0 / 3.0 * 2.0 / 3.0 / n) ** 0.5
        assert abs(p - 1.0 / 3.0) < 6 * sigma, (quality, p)


def test_strategy_offer_quality_pool_respected() -> None:
    """候选按品质池取样:采样出的候选其品质由 QUALITY_DISTRIBUTION
    掷出——大量样本下三档池都有产出(池映射不为空档)。"""
    rng = random.Random(9001)
    excluded: set[str] = set()
    qualities = {q for q, _ in QUALITY_DISTRIBUTION}
    hit: set[str] = set()
    for _ in range(30):
        picks = sample_strategy_offer(rng, excluded)
        hit.update(INVESTMENT_STRATEGIES[name].rarity for name in picks)
        excluded.update(picks)
    assert hit == qualities, '三档品质池均可达(均匀占位下不应有恒缺席档)'


# ============================================================ 环境 offer(U08)

def test_env_offer_shape_and_registry_membership() -> None:
    """U08:环境 offer = 3 张占位、互不重名、全在环境注册表;排除集
    生效(同构去重)。"""
    rng = random.Random(4242)
    excluded: set[str] = set()
    for _ in range(20):
        picks = sample_env_offer(rng, excluded)
        assert len(picks) == OFFER_CANDIDATES
        assert len(set(picks)) == OFFER_CANDIDATES
        for name in picks:
            assert name in INVESTMENT_ENVS
            assert name not in excluded
        excluded.update(picks)
    # 排除集吃光剩余池 → 如实少发(防御边界,占位池 83 张实际不可达)
    tiny = sample_env_offer(random.Random(1), set(INVESTMENT_ENVS))
    assert tiny == ()


# ============================================================ 披露判据

def test_quality_rewrite_envs_flagged_not_modeled() -> None:
    """品质覆写族(彩虹/黄金/白银时代等)首版不建模:命中判据为真,
    供后端按 QUALITY_REWRITE_ENVS_PENDING 披露;普通环境不误报;
    名单常量位 = kernel(游戏事实单一源)。"""
    assert quality_rewrite_hit('彩虹时代')
    assert quality_rewrite_hit('头彩')
    assert not quality_rewrite_hit('轮岗')
    assert not quality_rewrite_hit(None)
    assert '彩虹时代' in QUALITY_REWRITE_ENV_NAMES
