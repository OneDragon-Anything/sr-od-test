"""货币战争 策略决策(评估函数 + 贪心)测试 —— 纯逻辑,不依赖游戏/百科数据。

验证 cw_decisions 架构:eval 单调性、plan 硬门(gold≥0 / bench-full 必破 / level≤10)、
站位分流、3合1升星、凑整吃息跨档、char_quality 计已上阵、事件白名单/dot 主流派、
economy_mode、boss 克制。用 mock config(SimpleNamespace)避免 config IO。
"""
from __future__ import annotations

import random
from types import SimpleNamespace

from sr_od.application.currency_war.cw_comps import Comp
from sr_od.application.currency_war.cw_decisions import (
    MAX_REFRESH_PER_ROUND,
    EncounterOption,
    SupplyOption,
    _maybe_sell_for_interest,
    _phase_weights,
    alpha_t,
    char_quality_score,
    decide_boss_priority,
    decide_encounter,
    decide_event,
    decide_supply,
    economy_score,
    optionality_score,
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
    effective_hp_threshold,
    simulate,
)
from test import SrTestBase


def _cfg(**overrides) -> SimpleNamespace:
    """mock CurrencyWarConfig(纯属性,evaluate/plan 用 getattr 读)。"""
    base = {
        "faction_priority": ["贝洛伯格", "仙舟", "巡海游侠"],
        "character_priority": ["阿格莱雅"],
        "economy_mode": "adaptive",
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
        from sr_od.application.currency_war.cw_decisions import (
            MAX_REFRESH_PER_ROUND,
            _refresh_cap,
        )
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
        """商店有能推阵营 tier 的牌 → plan 贪心买入。

        状态隔离 level gate(D-24):level=4=期望(4,1)、goal[4]=roll → 不落后期望、不触发 level_up/saving
        (D-24:落后期望会先升等级花掉金 → 买不起;该 level gate 行为另测
        test_plan_levels_when_behind_expected_even_if_goal_roll)。本例只验贪心买牌推 tier。"""
        cfg = _cfg()
        state = GameState(
            gold=20, round_num=1, level=4, plane=1,
            board={"巡海游侠": 2},
            shop=[ShopCard(x=377, faction="巡海游侠", name="", cost=3)],
        )
        actions = plan(state, cfg, cfg.faction_priority)
        self.assertTrue(any(isinstance(a, BuyCard) for a in actions), "能推 tier 的牌应被买入(无 level gate 干预)")

    # —— level_plan 硬 gate(task#18 经济统一论):level_plan 说 level_up + 够钱 → 强制升级 ——

    def test_plan_levels_up_when_affordable_and_planned(self):
        """task#18 核心:level_plan 说 level_up + 够钱 → plan 升级(硬 gate,不靠贪心 eval)。

        回归守卫:replay 32 局「升 0 次」bug —— 旧版 LevelUp 候选 delta 永负(花大金升级的利息损失
        压过 level_val)→ 永不选 → bot 卡 lv5-6 → 弱 comp → plane2 死。改硬 gate 强制执行 level_plan。
        """
        from sr_od.application.currency_war.cw_comps import get_comp
        列车 = get_comp("列车同行")   # level_plan[5]="level_up"
        cfg = _cfg()
        state = GameState(gold=40, round_num=4, level=5, plane=1)   # cost(5→6)=36,gold 40>=36
        actions = plan(state, cfg, cfg.faction_priority, target_comp=列车)
        self.assertTrue(any(isinstance(a, LevelUp) for a in actions),
                        "level_plan[5]=level_up + gold>=cost(36) → 硬 gate 应升级")

    def test_plan_generic_curve_levels_mid_game(self):
        """task#18:comp 未填 level_plan(DOT队)→ 通用曲线兜底(lv5=level_up)+ 够钱 → 升级。

        多数 comp 未填 level_plan;通用曲线(_DEFAULT_LEVEL_GOAL)保证它们也有合理经济行为(中后期推等级),
        不再依赖每 comp 手填曲线。
        """
        from sr_od.application.currency_war.cw_comps import get_comp
        dot = get_comp("DOT队")   # 无 level_plan → 退回通用曲线
        cfg = _cfg()
        state = GameState(gold=40, round_num=4, level=5, plane=1)   # 通用曲线[5]=level_up,cost36,gold40>=36
        actions = plan(state, cfg, cfg.faction_priority, target_comp=dot)
        self.assertTrue(any(isinstance(a, LevelUp) for a in actions),
                        "DOT队 无 level_plan → 通用曲线 lv5=level_up + gold>=cost → 应升级")

    def test_plan_no_levelup_when_cannot_afford(self):
        """task#18:goal=level_up 但金不够升级金 → 不升级(硬 gate 的 afford 守卫,防负金)。"""
        from sr_od.application.currency_war.cw_comps import get_comp
        列车 = get_comp("列车同行")   # level_plan[5]=level_up
        cfg = _cfg()
        state = GameState(gold=10, round_num=4, level=5, plane=1)   # cost36,gold10<36
        actions = plan(state, cfg, cfg.faction_priority, target_comp=列车)
        self.assertFalse(any(isinstance(a, LevelUp) for a in actions),
                         "金不够升级金(cost36)→ 硬 gate 不应升级")

    # —— A2 战略层接线(plan → select_comp → evaluate(target),2026-08-04)——

    def test_plan_target_steers_buy_over_reactive(self):
        """A2 接线核心区分性:有 target 时买 target 阵营牌,而非 reactive 偏好的他派。

        强制 target=击破流萤(``character_build_around=['流萤']`` 只放过含流萤的 comp);
        空板 + 金 1(只够买 1 张)+ 商店[击破 cost1, 列车同行 cost1]。
        - reactive(无 target):synergy 上 列车同行(ceiling 0.5)> 击破(0.33)→ 会先买列车同行;
        - 有 target:击破买还降击破流莺 target_progress 剩余(+WP×0.167 ≈ 2.5)→ 击破反超 → 买击破。
        **断线(plan 不传 target)= 退回 reactive 买列车同行 → 本测试失败**(回归守卫)。
        """
        cfg = _cfg(character_build_around=["流萤"])
        state = GameState(
            gold=1, round_num=1, level=1, plane=1,
            shop=[ShopCard(x=1, faction="击破", name="", cost=1),
                  ShopCard(x=2, faction="列车同行", name="", cost=1)],
        )
        actions = plan(state, cfg, cfg.faction_priority, rng=random.Random(0))
        buys = [a for a in actions if isinstance(a, BuyCard)]
        self.assertTrue(buys, "金 1 够买 cost1,应至少买入 1 张")
        self.assertEqual(buys[0].card.faction, "击破",
                         "有 target(击破流萤)时应买击破(target 阵营),而非 reactive 偏好的列车同行")

    def test_plan_buys_toward_committed_comp(self):
        """A2 接线集成:板面已深入某 comp(列车同行 3/4,progress 0.75)→ plan 买该 comp 阵营牌收敛。

        锁定战略↔战术集成:select_comp 选已深入的 comp 作 target,plan 买入推进其成型。
        level=3(level_plan=roll,不触发 spending gate)→ 列车同行牌正常买入。
        """
        cfg = _cfg()
        state = GameState(
            gold=10, round_num=3, level=3, plane=1,
            board={"列车同行": 3},
            shop=[ShopCard(x=1, faction="列车同行", name="", cost=1)],
        )
        actions = plan(state, cfg, cfg.faction_priority)
        self.assertTrue(any(isinstance(a, BuyCard) and a.card.faction == "列车同行" for a in actions),
                        "板面深入列车同行 → 应买列车同行牌向 target 收敛")

    def test_plan_uses_passed_target_comp_not_reselect(self):
        """target 稳定性(task#16):plan(target_comp=X) 用 X 驱动买牌,**不内部重选**。

        同 state + 不同 target_comp → 买不同 target 阵营牌(证明传入 target 生效,非每轮 select_comp)。
        防 2026-08-04 实跑的 target 振荡(列车同行↔DOT队)→ churn。
        """
        from sr_od.application.currency_war.cw_comps import get_comp
        击破流萤 = get_comp("击破流萤")   # factions=['击破']
        dot队 = get_comp("DOT队")         # factions=['持续伤害','减益']
        cfg = _cfg()
        state = GameState(
            gold=3, round_num=3, level=5, plane=1,
            shop=[ShopCard(x=1, faction="击破", name="", cost=1),
                  ShopCard(x=2, faction="持续伤害", name="", cost=1)],
        )
        a1 = plan(state, cfg, cfg.faction_priority, rng=random.Random(0), target_comp=击破流萤)
        buys1 = [a for a in a1 if isinstance(a, BuyCard)]
        a2 = plan(state, cfg, cfg.faction_priority, rng=random.Random(0), target_comp=dot队)
        buys2 = [a for a in a2 if isinstance(a, BuyCard)]
        self.assertTrue(buys1, "target=击破流萤 应买牌")
        self.assertEqual(buys1[0].card.faction, "击破", "target=击破流萤 → 买击破(target 阵营)")
        self.assertTrue(buys2, "target=DOT队 应买牌")
        self.assertEqual(buys2[0].card.faction, "持续伤害", "target=DOT队 → 买持续伤害(target 阵营)")

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

    # —— 遭遇节点 decide_encounter(design 08;纯逻辑)——

    def _comp(self, attrs: list[str]) -> Comp:
        """构造测试 comp(控 mechanic_attributes,验 mechanics_fit 克/利)。"""
        return Comp(name="t", factions=["燃血"], core_chars=[], form_tiers={"燃血": 4},
                    strength="A", form_difficulty="medium", mechanic_attributes=attrs)

    def test_decide_encounter_refresh_when_all_counter(self):
        """全分支词缀都克 comp + 刷新未用 → 刷新换批(避开高危)。"""
        cfg = _cfg()
        comp = self._comp(["速度依赖"])  # 忽快忽慢→速度抑制 counter(克)
        opts = [EncounterOption(idx=0, difficulty=1, affixes=["忽快忽慢"]),
                EncounterOption(idx=1, difficulty=2, affixes=["忽快忽慢"])]
        pick = decide_encounter(opts, GameState(), comp, cfg, refresh_used=False)
        self.assertTrue(pick.refresh, "全分支克 comp 应刷新换批")

    def test_decide_encounter_no_refresh_when_used(self):
        """刷新已用 → 不再刷(按最优分支选)。"""
        cfg = _cfg()
        comp = self._comp(["速度依赖"])
        opts = [EncounterOption(idx=0, difficulty=1, affixes=["忽快忽慢"])]
        pick = decide_encounter(opts, GameState(), comp, cfg, refresh_used=True)
        self.assertFalse(pick.refresh, "刷新已用不再刷")

    def test_decide_encounter_unformed_picks_low_difficulty(self):
        """未成型(level 低/deployed 空)→ 偏低难度(生存优先);中性词缀按难度选。"""
        cfg = _cfg()
        comp = self._comp(["燃血"])
        unformed = GameState(level=1, deployed=[])   # max_units=1, deployed 0 → 未成型
        opts = [EncounterOption(idx=0, difficulty=1),    # 中性(无词缀)
                EncounterOption(idx=1, difficulty=3)]
        pick = decide_encounter(opts, unformed, comp, cfg)
        self.assertEqual(pick.idx, 0, "未成型应选低难度(diff=1)")
        self.assertFalse(pick.refresh)

    def test_decide_encounter_formed_buff_picks_high_difficulty(self):
        """成型 + 词缀利 comp(debuff=buff)→ 挑高难度拿奖励。"""
        cfg = _cfg()
        comp = self._comp(["燃血"])  # 正当防卫→反伤,对燃血是 synergy(debuff=buff,利)
        # 成型:board 满足 form_tiers + deployed ≥ max_units/2
        formed = GameState(level=8, board={"燃血": 4},
                           deployed=[BenchChar(slot=i) for i in range(4)])
        opts = [EncounterOption(idx=0, difficulty=1, affixes=["正当防卫"]),
                EncounterOption(idx=1, difficulty=3, affixes=["正当防卫"])]
        pick = decide_encounter(opts, formed, comp, cfg)
        self.assertEqual(pick.idx, 1, "成型 + 利 comp 应挑高难度(diff=3)拿奖励")
        self.assertFalse(pick.refresh, "利 comp 不刷新")

    # —— 补给节点 decide_supply(design 07/08;纯逻辑)——

    def _comp_key(self, key_equips: list[str]) -> Comp:
        return Comp(name="t", factions=[], core_chars=[], form_tiers={},
                    strength="A", form_difficulty="medium", key_equips=key_equips)

    def test_decide_supply_diamond_first(self):
        """带钻选项 → 选它(碾压装备价值)。"""
        cfg = _cfg()
        opts = [SupplyOption(idx=0, equip="反重力皮靴"),                 # 高价值但无钻
                SupplyOption(idx=1, equip="光能电池", has_diamond=True)]  # 带钻
        pick = decide_supply(opts, GameState(), self._comp_key([]), cfg)
        self.assertEqual(pick.idx, 1, "带钻应优先选")
        self.assertFalse(pick.refresh)

    def test_decide_supply_refresh_when_no_diamond(self):
        """全无钻 + 刷新未用 → 刷新找钻。"""
        cfg = _cfg()
        opts = [SupplyOption(idx=0, equip="反重力皮靴")]
        pick = decide_supply(opts, GameState(), self._comp_key([]), cfg, refresh_used=False)
        self.assertTrue(pick.refresh, "无钻应刷新找钻")

    def test_decide_supply_key_equip_when_refresh_used(self):
        """刷新已用 → 按 target_comp.key_equips 契合选(命脉级,碾压通用价值)。"""
        cfg = _cfg()
        comp = self._comp_key(["反重力皮靴"])   # 反重力靴是命脉
        opts = [SupplyOption(idx=0, equip="光能电池"),      # 通用 value 3
                SupplyOption(idx=1, equip="反重力皮靴")]    # key_fit +10 → 5+10=15
        pick = decide_supply(opts, GameState(), comp, cfg, refresh_used=True)
        self.assertEqual(pick.idx, 1, "刷新已用应选 key_equips 契合的")
        self.assertFalse(pick.refresh)

    def test_decide_supply_generic_value_when_no_key(self):
        """刷新已用 + 无 key 契合 → 通用装备价值高者优先(鞋>电池)。"""
        cfg = _cfg()
        opts = [SupplyOption(idx=0, equip="光能电池"),      # value 3
                SupplyOption(idx=1, equip="反重力皮靴")]    # value 5
        pick = decide_supply(opts, GameState(), self._comp_key([]), cfg, refresh_used=True)
        self.assertEqual(pick.idx, 1, "无 key 契合应选通用价值高的(反重力皮靴)")
        self.assertFalse(pick.refresh)

    # —— optionality_score + α(t)(design 02/03 P1-1 + F-3;纯逻辑)——

    def test_alpha_t_monotonic(self):
        """α(t) 随总回合单调:早(elapsed<R_OPEN)→0、晚(>R_CLOSE)→1、中线性。"""
        self.assertEqual(alpha_t(GameState(plane=1, round_num=1)), 0.0, "elapsed1<R_OPEN → 0")  # elapsed=1
        self.assertEqual(alpha_t(GameState(plane=3, round_num=6)), 1.0, "elapsed18>R_CLOSE → 1")  # elapsed=18
        self.assertAlmostEqual(alpha_t(GameState(plane=2, round_num=1)), 0.5, places=2,    # elapsed=7
                               msg="elapsed7 中点 → 0.5")

    def test_optionality_shared_char_rewards(self):
        """bench 角色属 ≥2 comp(风堇∈昼神阿雅+万敌)→ 加分;只属 1 comp(青雀)→ 0;空 → 0。"""
        multi = GameState(bench=[BenchChar(slot=0, char_id="风堇")])     # 风堇 ∈ 2 comp
        single = GameState(bench=[BenchChar(slot=0, char_id="青雀")])    # 青雀 ∈ 1 comp(巡击青雀)
        empty = GameState(bench=[])
        self.assertGreater(optionality_score(multi), 0.0, "风堇 属 2 comp 应加分")
        self.assertEqual(optionality_score(single), 0.0, "青雀 只属 1 comp 不加分")
        self.assertEqual(optionality_score(empty), 0.0, "空 bench → 0")

    def test_phase_weights_hp_threshold_override(self):
        """config.hp_safe_threshold 可调保血触发点(D-18 unification):默认 40 时 hp=50 平衡,
        threshold=60 时 hp=50 触发保血。"""
        self.assertEqual(_phase_weights(1, 50), (1.0, 1.0, 1.0), "默认 threshold=40,hp=50 健康→平衡")
        self.assertEqual(_phase_weights(1, 50, hp_threshold=60), (1.2, 0.4, 1.2),
                         "threshold=60,hp=50<60 → 保血")

    def test_plan_levels_when_behind_expected_even_if_goal_roll(self):
        """D-24: 落后期望等级 + 够钱 → 升级(即使 goal=roll)。修 chicken-egg(卡 roll 等级永不升)。"""
        cfg = _cfg()
        # lv4, plane1 round4 → expected=6;goal[4]=roll(非 level_up);gold 40 >= cost[5]=30
        s = GameState(gold=40, level=4, plane=1, round_num=4)
        actions = plan(s, cfg, cfg.faction_priority)
        self.assertTrue(any(isinstance(a, LevelUp) for a in actions),
                        "落后期望(lv4<6)+ 够钱 → 应升级(即使 goal[4]=roll,D-24 chicken-egg 修)")

    # —— difficulty → hp_safe_threshold 派生(D-32,向后兼容)——

    def test_effective_hp_threshold_fallback_no_difficulty(self):
        """difficulty 未检测("")→ 回退 hp_safe_threshold(无该字段 → 40=HP_DANGER)。向后兼容。"""
        s = GameState()  # difficulty 默认 ""
        self.assertEqual(effective_hp_threshold(s, _cfg()), 40, "无 hp_safe_threshold 字段 → 默认 40")
        cfg50 = _cfg(hp_safe_threshold=50)
        self.assertEqual(effective_hp_threshold(s, cfg50), 50, "difficulty 未检测 → 用 hp_safe_threshold")

    def test_effective_hp_threshold_override_by_difficulty(self):
        """difficulty="A8" + override 含 A8 → 用覆盖值(高难更早保血)。"""
        s = GameState(difficulty="A8")
        cfg = _cfg(hp_safe_threshold=40, difficulty_hp_override={"A8": 55})
        self.assertEqual(effective_hp_threshold(s, cfg), 55, "A8 覆盖优先于 hp_safe_threshold")

    def test_effective_hp_threshold_missing_key_falls_back(self):
        """difficulty="A4" + override 只含 A8(无 A4 键)→ 回退 hp_safe_threshold。"""
        s = GameState(difficulty="A4")
        cfg = _cfg(hp_safe_threshold=40, difficulty_hp_override={"A8": 55})
        self.assertEqual(effective_hp_threshold(s, cfg), 40, "override 无 A4 键 → 回退 hp_safe_threshold")

    def test_eval_difficulty_aware_hp_threshold(self):
        """evaluate 经 effective_hp_threshold 接 difficulty:A8+override=55 时 hp=42<55→保血权重;
        无 difficulty 时 hp=42>40→健康权重(证明 difficulty 派生改变 eval 行为,D-32 接线有效)。"""
        s_a8 = GameState(difficulty="A8", hp=42, plane=1)
        cfg_a8 = _cfg(hp_safe_threshold=40, difficulty_hp_override={"A8": 55})
        self.assertEqual(_phase_weights(s_a8.plane, s_a8.hp, effective_hp_threshold(s_a8, cfg_a8)),
                         (1.2, 0.4, 1.2), "A8 override=55,hp=42<55 → 保血权重")
        s_none = GameState(hp=42, plane=1)
        self.assertEqual(_phase_weights(s_none.plane, s_none.hp, effective_hp_threshold(s_none, _cfg())),
                         (1.0, 1.0, 1.0), "无 difficulty,threshold=40,hp=42>40 → 健康权重")
