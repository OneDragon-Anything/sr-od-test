"""T1a 轮首收入 kernel 单一源函数族锁(ADR-0623;统一观察架构 §7-T1/T2/§7.1)。

覆盖:①reward_base_gold 平面感知键(P2r1/P3r1 单键误返 3 hazard 回归)
②loss_compensation_base 玩家裁定口径值域(待玩家确认,ADR-0623 §3)
③round_start_income 四分支派发与分量(supply 连胜不动/reward 连胜×倍率/
败补连胜取 0/combat 连胜×倍率)④win_reward_mult 施于连胜分量含奖励轮
⑤利息分量(cap resolved 归一 + flat 修饰)⑥net_income 处置等价性锁
(委托改造后消费域逐位不变,ADR-0623 §决策2)⑦round_base_income 薄别名。

锁的出处:GameState 设计 §4.2 轮首收入行(正本语义)/economy.md §10.1
(真值源)/ADR-0623 §决策1-2。既有语义锁 test_cw_statefn::
test_net_income_schedule 的三个值点在本文件以等价性锁复述,两处同改。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_economy import (
    DEFAULT_INTEREST_CAP,
    LOSS_GOLD_BY_NODE,
    REWARD_BASE_GOLD_BY_ROUND,
    LostNodeRef,
    RoundStartIncome,
    loss_compensation_base,
    net_income,
    reward_base_gold,
    round_base_income,
    round_start_income,
    streak_gold,
)

# --- ① 平面感知键(GameState §4.2 奖励轮行;economy.md §10.1 直读定谳) ---

def test_reward_base_gold_p1_round_table() -> None:
    """P1 键 = REWARD_BASE_GOLD_BY_ROUND {1:3,2:4},其余轮 5(注册表同源)。"""
    assert reward_base_gold(1, 1) == 3
    assert reward_base_gold(1, 2) == 4
    for r in range(3, 10):
        assert reward_base_gold(1, r) == 5, f'P1 r{r}'


def test_reward_base_gold_plane_aware_no_hazard() -> None:
    """hazard 回归锁:P2r1/P3r1 必须取 5,禁 round 单键误返 3(§7-T1)。"""
    assert reward_base_gold(2, 1) == 5
    assert reward_base_gold(3, 1) == 5
    assert reward_base_gold(2, 5) == 5
    assert reward_base_gold(3, 7) == 5


def test_reward_base_gold_reads_registry_tables() -> None:
    """键真值只读注册表:改表必先改 REWARD_BASE_GOLD_BY_ROUND/BASE_INCOME。"""
    assert reward_base_gold(1, 1) == REWARD_BASE_GOLD_BY_ROUND[1]
    assert reward_base_gold(1, 2) == REWARD_BASE_GOLD_BY_ROUND[2]


# --- ② 败补基项(玩家裁定口径;ADR-0623 §3 待玩家确认) ---

def test_loss_compensation_base_player_ruling_domain() -> None:
    """记账口径值域:平面感知键与奖励轮同款,round_num=被败轮节点。

    败 P1r9 后 P2r1 补发按 P1r9 口径=5(跨位面取键语义,§4.2 败轮行)。
    待玩家确认申报:类型表 LOSS_GOLD_BY_NODE 为竞争口径,判别数据不足
    (ADR-0623 §3)——若玩家确认类型表,本锁与 ① 同批改写。
    """
    assert loss_compensation_base(1, 3, 'battle') == 5
    assert loss_compensation_base(1, 9, 'boss') == 5
    assert loss_compensation_base(2, 1, 'encounter') == 5
    assert loss_compensation_base(1, 1, 'battle') == 3
    assert loss_compensation_base(1, 2, 'encounter') == 4


# --- ③④ round_start_income 四分支与 win_reward_mult ---

def test_round_start_income_supply_branch_streak_frozen() -> None:
    """补给轮:base+息,连胜不动(ADR-0439 决策 2),mult 不生效。"""
    inc = round_start_income(1, 5, 'supply', 30, 4, win_reward_mult=3.0)
    assert inc.branch == 'supply'
    assert inc.base == 5
    assert inc.interest == 3
    assert inc.streak == 0
    assert inc.total == inc.base + inc.interest + inc.streak


def test_round_start_income_reward_branch_streak_with_mult() -> None:
    """奖励轮:base 平面感知 + 连胜照发×倍率(§4.1 含奖励轮)。"""
    inc = round_start_income(2, 1, 'reward', 0, 0)
    assert (inc.branch, inc.base, inc.streak) == ('reward', 5, 1)
    mult3 = round_start_income(2, 1, 'reward', 0, 3, win_reward_mult=3.0)
    assert (mult3.base, mult3.streak) == (5, streak_gold(3) * 3)


def test_round_start_income_loss_comp_branch() -> None:
    """败补:基项取被败节点平面键 + 连胜取 0(mult 不生效,§4.2)。"""
    inc = round_start_income(2, 1, 'battle', 8, 0,
                             lost_node=LostNodeRef(1, 9, 'boss'),
                             win_reward_mult=3.0)
    assert inc.branch == 'loss_comp'
    assert inc.base == loss_compensation_base(1, 9, 'boss')
    assert inc.interest == 0   # g=8 < 10 → 息 0
    assert inc.streak == 0


def test_round_start_income_combat_branch() -> None:
    """常规战斗胜轮:base+连胜×倍率+息。"""
    inc = round_start_income(1, 6, 'battle', 25, 5)
    assert inc.branch == 'combat'
    assert inc.base == 5
    assert inc.streak == streak_gold(5)
    assert inc.interest == 2


def test_round_start_income_branch_priority_matches_engine() -> None:
    """派发序=引擎 elif 序(supply→reward→败补→常规,§4.2 行选择优先级):
    奖励/补给节点即使带败态也走各自行,不发 LOSS_GOLD。"""
    lost = LostNodeRef(1, 3, 'battle')
    assert round_start_income(1, 4, 'reward', 0, 0,
                              lost_node=lost).branch == 'reward'
    assert round_start_income(1, 4, 'supply', 0, 0,
                              lost_node=lost).branch == 'supply'


def test_round_start_income_returns_typed_record() -> None:
    """返回类型化分解账(RoundStartIncome),as_dict 投影键面稳定。"""
    inc = round_start_income(1, 3, 'battle', 0, 2)
    assert isinstance(inc, RoundStartIncome)
    assert inc.as_dict() == {'branch': 'combat', 'base': 5, 'interest': 0,
                             'streak': 2, 'total': 7}


# --- ⑤ 利息分量(cap resolved 归一 + flat) ---

def test_round_start_income_interest_cap_resolved() -> None:
    """息帽经 interest_cap_resolved 归一:None→缺省 5;0 是有效覆写
    (买断制禁真值折叠);flat 与 cap 无关逐项相加。"""
    assert round_start_income(1, 5, 'battle', 100, 0).interest \
        == DEFAULT_INTEREST_CAP
    assert round_start_income(1, 5, 'battle', 100, 0,
                              interest_cap=10).interest == 10
    assert round_start_income(1, 5, 'battle', 100, 0,
                              interest_cap=0).interest == 0
    flat = round_start_income(1, 5, 'battle', 0, 0, interest_flat=2)
    assert flat.interest == 2


# --- ⑥ net_income 处置等价性锁(ADR-0623 §决策2) ---

@pytest.mark.parametrize('round_num', range(1, 10))
@pytest.mark.parametrize('streak_pre', range(0, 8))
@pytest.mark.parametrize('lost_node_type',
                         [None, 'battle', 'encounter', 'boss'])
def test_net_income_equivalence_full_domain(round_num: int, streak_pre: int,
                                            lost_node_type: str | None) -> None:
    """等价性锁:委托改造后与改造前公式在消费域逐位相等。

    参考实现=改造前语义(round 单键查表 + streak_gold + LOSS_GOLD_BY_NODE;
    ADR-0623 §决策2 申报「消费点数值逐位不变」);既有语义值点
    (1,0)=4/(5,3,'battle')=9/(3,6)=9 另见 test_cw_statefn::test_net_income_schedule,
    两处同改(同值锁,非双源——本锁钉等价性,彼锁钉语义出处)。
    """
    expected = (REWARD_BASE_GOLD_BY_ROUND.get(round_num, 5)
                + streak_gold(streak_pre)
                + (LOSS_GOLD_BY_NODE.get(lost_node_type, 0)
                   if lost_node_type is not None else 0))
    assert net_income(round_num, streak_pre, lost_node_type) == expected


def test_net_income_declared_semantic_points() -> None:
    """消费域代表点(与 mandate_v1 shop/encounter/loss_exact 前置同值域):
    六处消费全部传 streak_pre=0/lost=None,此三点为实际落值面。"""
    assert net_income(1, 0) == 4
    assert net_income(2, 0) == 5
    assert net_income(9, 0) == 6


# --- ⑦ round_base_income 薄别名 ---

@pytest.mark.parametrize('round_num', list(range(1, 13)))
def test_round_base_income_is_p1_projection(round_num: int) -> None:
    """薄别名等价:round_base_income(r) == reward_base_gold(1, r)
    (ADR-0623 §决策2:实现单一源归 reward_base_gold,本函数只承载
    「P1 键当全平面规划曲线」的申报语义)。"""
    assert round_base_income(round_num) == reward_base_gold(1, round_num)
