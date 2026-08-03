"""货币战争 策略决策(评估函数 + 贪心)测试 —— 纯逻辑,不依赖游戏/百科数据。

验证 cw_decisions 架构:eval 单调性、plan 硬门(gold≥0 / bench-full 必破 / level≤10)、
站位分流、3合1升星、凑整吃息跨档、char_quality 计已上阵、事件白名单/dot 主流派、
economy_mode、boss 克制。用 mock config(SimpleNamespace)避免 config IO。
"""
from __future__ import annotations

import random
from types import SimpleNamespace

from sr_od.application.currency_war.cw_decisions import (
    MAX_REFRESH_PER_ROUND,
    _maybe_sell_for_interest,
    char_quality_score,
    decide_boss_priority,
    decide_event,
    economy_score,
    plan,
    synergy_score,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    DeployMove,
    GameState,
    LevelUp,
    RefreshShop,
    SellBench,
    ShopCard,
    simulate,
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
        s2 = GameState(board={"巡海游侠": 2})
        s4 = GameState(board={"巡海游侠": 4})
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
        rich = GameState(gold=50, round_num=5, level=6, plane=2)
        poor = GameState(gold=0, round_num=5, level=6, plane=2)
        self.assertGreater(economy_score(rich, "adaptive"), economy_score(poor, "adaptive"))

    def test_phase_weights_hp_danger_reduces_economy(self):
        """A3 + review agent:HP 危险才保血(economy 降权);健康时 economy 不压(snowball 到 50)。
        原"前期 plane1 → economy 0.4"已被研究推翻(前期该 snowball 经济),改测 HP 维度。"""
        from sr_od.application.currency_war.cw_decisions import evaluate
        cfg = _cfg()
        healthy = GameState(gold=50, round_num=3, level=5, plane=1)         # hp100 健康:economy 权重 1.0
        danger = GameState(gold=50, round_num=3, level=5, plane=1, hp=30)   # hp<HP_DANGER:economy 权重 0.4
        # 同 economy_score(50 金),HP 危险时 economy 降权 → evaluate 总分更低
        self.assertGreater(evaluate(healthy, cfg, cfg.faction_priority),
                           evaluate(danger, cfg, cfg.faction_priority),
                           "HP 危险时 economy 降权,总分 < 健康(同为 plane1)")

    def test_refresh_cap_dynamic(self):
        """_refresh_cap 关键回合放宽(review agent + 用户:固定 2 太死)。"""
        from sr_od.application.currency_war.cw_decisions import MAX_REFRESH_PER_ROUND, _refresh_cap
        base = GameState(gold=50, round_num=3, level=5, plane=1, hp=100)     # 健康前期
        self.assertEqual(_refresh_cap(base), MAX_REFRESH_PER_ROUND, "健康前期 = 基线 2")
        late = GameState(gold=50, round_num=6, level=8, plane=3, hp=100)     # plane3/升8
        self.assertGreater(_refresh_cap(late), MAX_REFRESH_PER_ROUND, "plane3/升8 放宽")
        danger = GameState(gold=50, round_num=3, level=5, plane=1, hp=30)    # HP 危险
        self.assertGreater(_refresh_cap(danger), MAX_REFRESH_PER_ROUND, "HP 危险放宽")

    def test_economy_mode_effects(self):
        """economy_mode 只调利息项:rush_level < adaptive < interest_first。"""
        s = GameState(gold=50, round_num=5, level=6, plane=2)
        adaptive = economy_score(s, "adaptive")
        self.assertLess(economy_score(s, "rush_level"), adaptive, "rush_level 降低利息项")
        self.assertGreater(economy_score(s, "interest_first"), adaptive, "interest_first 抬高利息项")

    def test_economy_rush_level_rewards_level(self):
        """rush_level 等级项 ×1.5:等级领先时 rush_level > adaptive(review r5 修)。"""
        ahead = GameState(gold=0, round_num=3, level=7, plane=1)   # expected_level(3,1)=5,level=7 领先
        self.assertGreater(economy_score(ahead, "rush_level") - economy_score(ahead, "adaptive"), 0,
                           "等级领先时 rush_level 应 > adaptive(等级项加权)")

    def test_evaluate_target_comp_applies_progress(self):
        """战略↔战术接法:evaluate(target_comp) = evaluate() − TARGET_PROGRESS_WEIGHT × 剩余进度。

        target_comp 给定时扣「剩余成型进度」分(接近 form_tiers → 少扣);None 时不扣(向后兼容)。
        """
        from sr_od.application.currency_war.cw_comps import get_comp
        from sr_od.application.currency_war.cw_decisions import (
            TARGET_PROGRESS_WEIGHT,
            _target_progress_remaining,
            evaluate,
        )
        cfg = _cfg()
        青雀 = get_comp("巡击青雀")   # form_tiers {仙舟:5, 追击:3}
        s_far = GameState(board={})                       # 完全没起步 → 剩余 1.0
        s_close = GameState(board={"仙舟": 5, "追击": 3})  # 已成型 → 剩余 0.0
        # _target_progress_remaining:已成型=0,没起步=1
        self.assertAlmostEqual(_target_progress_remaining(s_close, 青雀), 0.0, places=6)
        self.assertAlmostEqual(_target_progress_remaining(s_far, 青雀), 1.0, places=6)
        # evaluate(target) = evaluate() − WP × remaining(精确关系)
        base_far = evaluate(s_far, cfg, cfg.faction_priority)
        self.assertAlmostEqual(evaluate(s_far, cfg, cfg.faction_priority, target_comp=青雀),
                               base_far - TARGET_PROGRESS_WEIGHT * 1.0, places=6)
        # 已成型时 target 不扣分(= 无 target 的 evaluate)
        base_close = evaluate(s_close, cfg, cfg.faction_priority)
        self.assertAlmostEqual(evaluate(s_close, cfg, cfg.faction_priority, target_comp=青雀),
                               base_close, places=6,
                               msg="已成型 → 剩余 0 → target 不扣分")
        # 接近成型 > 远离成型(有 target 时,战略导向)
        self.assertGreater(evaluate(s_close, cfg, cfg.faction_priority, target_comp=青雀),
                           evaluate(s_far, cfg, cfg.faction_priority, target_comp=青雀),
                           "接近 target 成型 → evaluate 更高")

    # —— plan 硬门 ——

    def test_plan_no_negative_gold(self):
        """plan 后 gold 永不为负(模拟执行所有 action)。"""
        cfg = _cfg()
        state = GameState(
            gold=5, round_num=3, level=5, plane=1,
            shop=[ShopCard(x=377, faction="巡海游侠", name="", cost=3),
                  ShopCard(x=646, faction="仙舟", name="", cost=3)],
        )
        actions = plan(state, cfg, cfg.faction_priority)
        gold = state.gold
        for a in actions:
            gold = simulate(GameState(gold=gold), a).gold
            self.assertGreaterEqual(gold, 0, f"action {a} 使 gold 变负")

    def test_plan_bench_full_sells_when_broke(self):
        """bench-full(OCR 标志)且无金升等级 → 必卖最弱破墙。"""
        cfg = _cfg()
        bench = [BenchChar(slot=i, faction="巡海游侠", star=1) for i in range(3)]
        state = GameState(gold=0, round_num=2, level=3, plane=1, bench=bench, bench_full_flag=True)
        actions = plan(state, cfg, cfg.faction_priority)
        self.assertTrue(any(isinstance(a, SellBench) for a in actions),
                        "bench-full 无金时应卖最弱破墙")

    def test_plan_bench_full_levels_when_rich(self):
        """bench-full(OCR 标志)且金够 → 升等级破墙(而非卖)。"""
        cfg = _cfg()
        bench = [BenchChar(slot=i, faction="巡海游侠", star=1) for i in range(3)]
        state = GameState(gold=100, round_num=2, level=3, plane=1, bench=bench, bench_full_flag=True)
        actions = plan(state, cfg, cfg.faction_priority)
        self.assertTrue(any(isinstance(a, LevelUp) for a in actions),
                        "bench-full 金够时应升等级破墙")

    def test_plan_buys_synergy_push(self):
        """商店有能推阵营 tier 的牌 → plan 买入。"""
        cfg = _cfg()
        state = GameState(
            gold=20, round_num=3, level=5, plane=1,
            board={"巡海游侠": 2},
            shop=[ShopCard(x=377, faction="巡海游侠", name="", cost=3)],
        )
        actions = plan(state, cfg, cfg.faction_priority)
        self.assertTrue(any(isinstance(a, BuyCard) for a in actions), "能推 tier 的牌应被买入")

    def test_plan_no_levelup_at_max(self):
        """满级(10)时不再升等级(level≤10 硬门)。"""
        cfg = _cfg()
        state = GameState(gold=200, round_num=6, level=10, plane=3, bench_full_flag=True)
        actions = plan(state, cfg, cfg.faction_priority)
        self.assertFalse(any(isinstance(a, LevelUp) for a in actions), "满级不应再升等级")

    def test_plan_caps_refresh_per_round(self):
        """每回合主动刷新(D 牌)次数 ≤ MAX_REFRESH_PER_ROUND(review r5:防无限刷死代码)。"""
        cfg = _cfg()
        # 高金 + 商店无可用牌 → 刷新期望可能正;即便如此也被上限挡住
        state = GameState(gold=80, round_num=4, level=6, plane=2,
                          shop=[ShopCard(x=1, faction="公司", name="", cost=5)])
        actions = plan(state, cfg, cfg.faction_priority, rng=random.Random(0))
        n_refresh = sum(1 for a in actions if isinstance(a, RefreshShop))
        self.assertLessEqual(n_refresh, MAX_REFRESH_PER_ROUND,
                             f"每回合刷新应 ≤ {MAX_REFRESH_PER_ROUND},实际 {n_refresh}")

    # —— deploy 站位 + 3合1 + 凑整吃息 + char_quality 已上阵(review r1 新覆盖)——

    def test_deploy_uses_position_pref(self):
        """deploy 按 position_pref 分流:front 偏好→前排,back 偏好→后排。"""
        cfg = _cfg()
        state = GameState(
            gold=10, round_num=3, level=5, plane=1,
            bench=[BenchChar(slot=0, faction="巡海游侠", star=1, position_pref="front"),
                   BenchChar(slot=1, faction="巡海游侠", star=1, position_pref="back")],
        )
        actions = plan(state, cfg, cfg.faction_priority)
        rows = {a.to_row for a in actions if isinstance(a, DeployMove)}
        self.assertIn("front", rows, "front 偏好角色应 deploy 到前排")
        self.assertIn("back", rows, "back 偏好角色应 deploy 到后排")

    def test_compound_3merge(self):
        """买 3 张同名同星 → 自动合并升星(3×1星→1×2星)。"""
        s = GameState(gold=100)
        for _ in range(3):
            s = simulate(s, BuyCard(ShopCard(x=1, name="阿格莱雅", cost=1, star=1)))
        self.assertEqual(len(s.bench), 1, "3 同名1星应合并为1张")
        self.assertEqual(s.bench[0].star, 2, "合并后应为2星")

    def test_sell_for_interest_crosses_boundary(self):
        """凑整吃息:gold=39 卖1星(回1)→40 跨档应卖;gold=31→32 不跨档不卖。

        直接测 _maybe_sell_for_interest(绕开贪心,避免 bench 角色被先 deploy 掉)。
        """
        cfg = _cfg()
        a39: list = []
        _maybe_sell_for_interest(
            GameState(gold=39, bench=[BenchChar(slot=0, faction="公司", star=1)]),
            a39, [], cfg)
        self.assertTrue(any(isinstance(a, SellBench) for a in a39), "gold=39 卖1星→40 跨档应卖")
        a31: list = []
        _maybe_sell_for_interest(
            GameState(gold=31, bench=[BenchChar(slot=0, faction="公司", star=1)]),
            a31, [], cfg)
        self.assertFalse(any(isinstance(a, SellBench) for a in a31), "gold=31→32 不跨档不应卖")

    def test_char_quality_counts_deployed(self):
        """char_quality 计已上阵优先角色(deploy 不丢分)。"""
        s_bench = GameState(bench=[BenchChar(slot=0, char_id="阿格莱雅", faction="巡海游侠", star=1)])
        s_dep = GameState(deployed=[BenchChar(slot=0, char_id="阿格莱雅", faction="巡海游侠", star=1)])
        v_bench = char_quality_score(s_bench, ["阿格莱雅"])
        v_dep = char_quality_score(s_dep, ["阿格莱雅"])
        self.assertGreater(v_dep, 0, "已上阵优先角色应计分")
        self.assertEqual(v_bench, v_dep, "bench 与 deployed 的优先角色同等计分")

    # —— 事件 + boss ——

    def test_decide_event_whitelist(self):
        """选项含白名单名 → 选它。"""
        cfg = _cfg()
        pick = decide_event(["随便一个", "中产阶级", "另一个"], cfg, GameState())
        self.assertEqual(pick.option_idx, 1, "应选白名单'中产阶级'")

    def test_decide_event_dot_needs_major_faction(self):
        """DoT 避坑需 DoT 为主流派(count≥2):count=2 避,count=1 不避。"""
        cfg = _cfg()
        s2 = GameState(board={"持续伤害": 2})  # 主派 → 避 净化身心
        self.assertNotEqual(decide_event(["净化身心", "普通选项"], cfg, s2).option_idx, 0,
                            "count=2 走DoT应避净化身心")
        s1 = GameState(board={"持续伤害": 1})  # 仅顺带1张 → 不避
        # count=1 不触发 on_dot,净化身心 无惩罚;两选项白名单都0分 → 选第一个(idx0)
        self.assertEqual(decide_event(["净化身心", "普通选项"], cfg, s1).option_idx, 0,
                         "count=1 非DoT主派,不避(选第一个)")

    def test_decide_boss_priority_demotes(self):
        """boss 克制表里的阵营被降到末尾。"""
        cfg = _cfg(faction_priority=["贝洛伯格", "昼之半神", "仙舟"])
        result = decide_boss_priority(["电视机"], cfg)
        self.assertEqual(result[-1], "昼之半神", "'电视机'应把'昼之半神'降末尾")
        self.assertEqual(result[0], "贝洛伯格")
