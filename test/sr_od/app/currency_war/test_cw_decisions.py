"""货币战争 策略决策(评估函数 + 贪心)测试 —— 纯逻辑,不依赖游戏/百科数据。

验证 cw_decisions 的架构正确性:eval 单调性、plan 守硬门(gold≥0 / bench-full 必破)、
事件白名单、boss 克制。用 mock config(types.SimpleNamespace)避免 config 文件 IO。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_decisions import (
    decide_boss_priority,
    decide_event,
    economy_score,
    plan,
    synergy_score,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    LevelUp,
    SellBench,
    ShopCard,
)
from test import SrTestBase


def _cfg(**overrides) -> SimpleNamespace:
    """mock CurrencyWarConfig(纯属性,evaluate/plan 用 getattr 读)。"""
    base = {
        "faction_priority": ["贝洛伯格", "仙舟", "巡海游侠"],
        "character_priority": ["阿格莱雅"],
        "economy_mode": "adaptive",
        "aggression": "balanced",
        "event_whitelist": {"中产阶级": 82, "定期福利": 90},
        "boss_counter": {"电视机": ["昼之半神"]},
        "dot_punish_envs": ["净化身心"],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestCurrencyWarDecisions(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    # —— eval 单调性 ——

    def test_synergy_more_tiers_higher(self):
        """同阵营,激活更高 tier → 更高分。巡海游侠 tiers=(1,2,3,4)。"""
        cfg = _cfg()
        s2 = GameState(board={"巡海游侠": 2})   # 2 tier
        s4 = GameState(board={"巡海游侠": 4})   # 4 tier
        self.assertGreater(synergy_score(s4, cfg.faction_priority),
                           synergy_score(s2, cfg.faction_priority))

    def test_synergy_combat_over_support(self):
        """同人数,战力型 > 辅助型。巡海游侠(combat) vs 星间旅人(support)。"""
        cfg = _cfg()
        combat = GameState(board={"巡海游侠": 1})
        support = GameState(board={"星间旅人": 1})
        self.assertGreater(synergy_score(combat, cfg.faction_priority),
                           synergy_score(support, cfg.faction_priority))

    def test_economy_interest(self):
        """中期,存金近 50 > 存金 0(利息加分)。"""
        _cfg()
        rich = GameState(gold=50, round_num=5, level=6, plane=2)
        poor = GameState(gold=0, round_num=5, level=6, plane=2)
        self.assertGreater(economy_score(rich, "adaptive"), economy_score(poor, "adaptive"))

    def test_economy_plane1_reduced(self):
        """第一位面利息价值衰减(保血):同 gold、各自等级=期望(去掉等级项),plane1 利息分 < plane2。"""
        s1 = GameState(gold=50, round_num=3, level=5, plane=1)   # expected(3,1)=5 → 等级项 0
        s2 = GameState(gold=50, round_num=3, level=7, plane=2)   # expected(3,2)=7 → 等级项 0
        self.assertGreater(economy_score(s2, "adaptive"), economy_score(s1, "adaptive"))

    # —— plan 硬门 ——

    def test_plan_no_negative_gold(self):
        """plan 后 gold 永不为负(模拟执行所有 action)。"""
        cfg = _cfg()
        state = GameState(
            gold=5, round_num=3, level=5, plane=1,
            shop=[ShopCard(x=377, faction="巡海游侠", name="", cost=3),
                  ShopCard(x=646, faction="仙舟", name="", cost=3)],
            bench=[],
        )
        actions = plan(state, cfg, cfg.faction_priority)
        gold = state.gold
        from sr_od.application.currency_war.cw_state import simulate
        for a in actions:
            gold_after = simulate(GameState(gold=gold), a).gold
            self.assertGreaterEqual(gold_after, 0, f"action {a} 使 gold 变负")
            gold = gold_after

    def test_plan_bench_full_sells_when_broke(self):
        """bench-full 且无金升等级 → 必卖最弱破墙。"""
        cfg = _cfg()
        # level=3 → bench_capacity=5;bench 塞 5 个 → 满;gold=0 升不起(成本 18)
        bench = [BenchChar(slot=i, faction="巡海游侠", star=1) for i in range(5)]
        state = GameState(gold=0, round_num=2, level=3, plane=1, bench=bench)
        actions = plan(state, cfg, cfg.faction_priority)
        self.assertTrue(any(isinstance(a, SellBench) for a in actions),
                        "bench-full 无金时应卖最弱破墙")

    def test_plan_bench_full_levels_when_rich(self):
        """bench-full 且金够 → 升等级破墙(而非卖)。"""
        cfg = _cfg()
        bench = [BenchChar(slot=i, faction="巡海游侠", star=1) for i in range(5)]
        state = GameState(gold=100, round_num=2, level=3, plane=1, bench=bench)
        actions = plan(state, cfg, cfg.faction_priority)
        self.assertTrue(any(isinstance(a, LevelUp) for a in actions),
                        "bench-full 金够时应升等级破墙")

    def test_plan_buys_synergy_push(self):
        """商店有能推阵营 tier 的牌 → plan 买入。"""
        cfg = _cfg()
        # board 巡海游侠=2(tier 1,2;接近 tier3);level=5 有空槽 deploy
        state = GameState(
            gold=20, round_num=3, level=5, plane=1,
            board={"巡海游侠": 2},
            shop=[ShopCard(x=377, faction="巡海游侠", name="", cost=3)],
        )
        actions = plan(state, cfg, cfg.faction_priority)
        self.assertTrue(any(isinstance(a, BuyCard) for a in actions),
                        "能推 tier 的牌应被买入")

    # —— 事件 + boss ——

    def test_decide_event_whitelist(self):
        """选项含白名单名 → 选它。"""
        cfg = _cfg()
        state = GameState()
        pick = decide_event(["随便一个", "中产阶级", "另一个"], cfg, state)
        self.assertEqual(pick.option_idx, 1, "应选白名单'中产阶级'")

    def test_decide_event_dot_punish_avoided(self):
        """走 DoT 时遇 dot_punish 环境 → 避开(选别的)。"""
        cfg = _cfg()
        state = GameState(board={"持续伤害": 2})  # 正在走 DoT
        pick = decide_event(["净化身心", "普通选项"], cfg, state)
        self.assertEqual(pick.option_idx, 1, "走 DoT 时应避开'净化身心'")

    def test_decide_boss_priority_demotes(self):
        """boss 克制表里的阵营被降到末尾。"""
        cfg = _cfg(faction_priority=["贝洛伯格", "昼之半神", "仙舟"])
        result = decide_boss_priority(["电视机"], cfg)
        self.assertEqual(result[-1], "昼之半神", "'电视机'应把'昼之半神'降末尾")
        self.assertEqual(result[0], "贝洛伯格")
