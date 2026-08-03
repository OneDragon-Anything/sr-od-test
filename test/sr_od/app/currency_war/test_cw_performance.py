"""货币战争 观测反馈(cw_performance)测试 —— 纯逻辑,不依赖游戏。

锁 r5/r6 交互行为(10_battle_and_enemies.md):
- r6 F1: intentional_fold 排除(防"故意输"污染 trend)。
- r6 F2: 归一化(打 boss 掉得多但归一化后不误判弱)。
- r6 F4: comp_tag 降权(pivot 后旧 comp ×0.3 不全删)。
- r6 F6: 冷启动(<2 outcome → None)。
- r5: 低置信(<0.7)不进 trend。
- comp_viability: obs None→纯先验;rounds_seen 增→obs_weight 升。
- is_run_dead: 三门(HP 低 + trend 高 + 锁不住血节点)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_comps import ScoreContext, get_comp
from sr_od.application.currency_war.cw_performance import (
    HP_LOSS_FULL,
    PerformanceTracker,
    RoundOutcome,
    comp_viability,
    is_run_dead,
)
from sr_od.application.currency_war.cw_state import GameState
from test import SrTestBase


def _out(round_num: int, hp: int, node: str = "普通战斗", comp: str = "c1",
         fold: bool = False, conf: float = 1.0, plane: int = 1) -> RoundOutcome:
    return RoundOutcome(round_num=round_num, plane=plane, node_type=node, comp_tag=comp,
                        intentional_fold=fold, hp_after=hp, hp_confidence=conf)


class TestCurrencyWarPerformance(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    # —— r6 F1: intentional_fold 排除 ——

    def test_fold_excluded_from_trend(self):
        """故意输(fold)的大掉血不污染 trend:fold 排除后只 1 个 qualifying → None。"""
        t = PerformanceTracker()
        t.record(_out(1, 100))
        t.record(_out(2, 50, fold=True))    # 故意输掉 50 —— 排除
        self.assertIsNone(t.recent_hp_loss_trend(), "fold 排除后 <2 → None(不污染)")

    def test_non_fold_big_loss_detected(self):
        """同样掉 50 但非 fold → trend 检测到大掉血(对照)。"""
        t = PerformanceTracker()
        t.record(_out(1, 100))
        t.record(_out(2, 50))               # 非故意 → 进 trend
        trend = t.recent_hp_loss_trend()
        self.assertIsNotNone(trend)
        self.assertGreater(trend, 0, "非 fold 大掉血应被检测")

    # —— r6 F2: 归一化(boss 掉得多不误判)——

    def test_boss_loss_normalized_not_misjudged(self):
        """打 boss 掉 30(normalized 30/3=10)≈ 普通关掉 10(normalized 10/1=10):归一化后等价。"""
        t_normal = PerformanceTracker()
        t_normal.record(_out(1, 100, node="普通战斗"))
        t_normal.record(_out(2, 90, node="普通战斗"))    # 掉 10
        t_boss = PerformanceTracker()
        t_boss.record(_out(1, 100, node="普通战斗"))
        t_boss.record(_out(2, 70, node="boss"))          # 掉 30,但 boss expected_drop=3.0
        self.assertAlmostEqual(t_normal.recent_hp_loss_trend(), t_boss.recent_hp_loss_trend(), places=6,
                               msg="归一化后 boss 掉 30 ≈ 普通关掉 10(不误判弱)")

    # —— r6 F4: comp_tag 降权(pivot 后旧 comp ×0.3)——

    def test_comp_tag_downweight(self):
        """pivot 后旧 comp(B)的大掉血 ×0.3 降权:trend(A) < 全 A 同掉血的 trend。"""
        # 全 A:o1(100)→o2(90)→o3(70),trend = (10+20)/2 = 15
        t_all_a = PerformanceTracker()
        t_all_a.record(_out(1, 100, comp="A"))
        t_all_a.record(_out(2, 90, comp="A"))
        t_all_a.record(_out(3, 70, comp="A"))
        # 混合:o1(100,A)→o2(90,A)→o3(70,B 旧 comp):B 的 20 掉血 ×0.3 降权
        t_mixed = PerformanceTracker()
        t_mixed.record(_out(1, 100, comp="A"))
        t_mixed.record(_out(2, 90, comp="A"))
        t_mixed.record(_out(3, 70, comp="B"))
        self.assertLess(t_mixed.recent_hp_loss_trend(comp_tag="A"),
                        t_all_a.recent_hp_loss_trend(comp_tag="A"),
                        "旧 comp(B)大掉血降权 → trend(A) < 全 A")

    # —— r6 F6: 冷启动(<2 → None)——

    def test_cold_start_returns_none(self):
        """<2 qualifying outcome(无首个差分)→ None。"""
        t = PerformanceTracker()
        self.assertIsNone(t.recent_hp_loss_trend(), "0 outcome → None")
        t.record(_out(1, 100))
        self.assertIsNone(t.recent_hp_loss_trend(), "1 outcome 无差分 → None")
        t.record(_out(2, 90))
        self.assertIsNotNone(t.recent_hp_loss_trend(), "2 outcome 有首个差分 → 非 None")

    # —— r5: 低置信(<0.7)不进 trend ——

    def test_low_confidence_excluded(self):
        """OCR 低置信(<0.7)的 outcome 不进 trend(防抖动):只剩 1 个高置信 → None。"""
        t = PerformanceTracker()
        t.record(_out(1, 100, conf=0.9))
        t.record(_out(2, 50, conf=0.4))     # 低置信 → 排除
        self.assertIsNone(t.recent_hp_loss_trend(), "低置信排除后 <2 → None")
        # 对照:同掉血但高置信 → 检测到
        t2 = PerformanceTracker()
        t2.record(_out(1, 100, conf=0.9))
        t2.record(_out(2, 50, conf=0.9))
        self.assertIsNotNone(t2.recent_hp_loss_trend())

    # —— perf_for_comp 映射 ——

    def test_perf_for_comp_mapping(self):
        """trend=None→None;trend=0→1.0;trend=HP_LOSS_FULL→0。"""
        t = PerformanceTracker()
        self.assertIsNone(t.perf_for_comp("A"), "冷启动 → None")
        # trend=0(不掉血)→ perf=1.0
        t.record(_out(1, 100, comp="A"))
        t.record(_out(2, 100, comp="A"))
        self.assertAlmostEqual(t.perf_for_comp("A"), 1.0, places=6, msg="不掉血 → perf=1.0")
        # 每回合掉 HP_LOSS_FULL → trend=HP_LOSS_FULL → perf≈0(用独立 tracker 避免上面 0-delta 稀释)
        t2 = PerformanceTracker()
        t2.record(_out(1, 100, comp="A"))
        t2.record(_out(2, 70, comp="A"))
        t2.record(_out(3, 40, comp="A"))
        perf = t2.perf_for_comp("A")
        self.assertIsNotNone(perf)
        self.assertLess(perf, 0.2, "每回合掉 HP_LOSS_FULL → perf 趋 0")

    # —— comp_viability: obs None→纯先验;rounds_seen 增→obs_weight 升 ——

    def test_comp_viability_cold_start_pure_prior(self):
        """tracker 空(obs None)→ comp_viability = 纯先验(无观测项)。"""
        阿雅 = get_comp("昼神阿雅")
        state = GameState(board={"昼之半神": 4})
        ctx = ScoreContext(mechanics=set())
        t = PerformanceTracker()
        v = comp_viability(阿雅, state, ctx, t)
        self.assertGreater(v, 0.0)
        self.assertLessEqual(v, 1.0)
        # 纯先验 = 0.45*form(1.0) + 0.30*equip(0.5) + 0.25*mech(0.5) = 0.45+0.15+0.125 = 0.725
        self.assertAlmostEqual(v, 0.725, places=2, msg="冷启动纯先验")

    def test_comp_viability_observation_blends(self):
        """rounds_seen 多 + 掉血大 → comp_viability 低于纯先验(观测拉低)。"""
        阿雅 = get_comp("昼神阿雅")
        state = GameState(board={"昼之半神": 4})
        ctx = ScoreContext(mechanics=set())
        cold = comp_viability(阿雅, state, ctx, PerformanceTracker())
        # 灌 6 回合稳定大掉血观测(阿雅,window 内每回合掉 20 不撞底:trend=20 → perf≈0.33)
        t = PerformanceTracker()
        for r, hp in enumerate([100, 80, 60, 40, 20, 0], start=1):
            t.record(_out(r, hp, comp="昼神阿雅"))
        warm = comp_viability(阿雅, state, ctx, t)
        self.assertLess(warm, cold, "观测到大掉血 → viability 低于纯先验")

    # —— is_run_dead 三门 ——

    def test_is_run_dead_three_gates(self):
        """死局 = HP低 + trend高 + 锁不住血节点;缺一门 → False;冷启动 → False。"""
        # 造 trend>15:o1(100)→o2(80) 掉 20
        def _tracker() -> PerformanceTracker:
            t = PerformanceTracker()
            t.record(_out(1, 100))
            t.record(_out(2, 80))
            return t
        t = _tracker()
        danger_boss = GameState(hp=10)          # hp<DEAD_HP(20)
        self.assertTrue(is_run_dead(danger_boss, t, "boss"), "hp低+trend高+boss → 死")
        self.assertFalse(is_run_dead(danger_boss, t, "普通战斗"), "普通关可能锁血 → 不死")
        safe_hp = GameState(hp=80)              # hp 不低
        self.assertFalse(is_run_dead(safe_hp, t, "boss"), "hp 不低 → 不死")
        # 冷启动(trend None)→ 不死
        self.assertFalse(is_run_dead(danger_boss, PerformanceTracker(), "boss"), "冷启动 trend None → 不死")

    # —— boss_kill_signal ——

    def test_boss_kill_signal(self):
        """boss 节点 killed 可观测 → 击杀率;无 boss 观测 → None。"""
        t = PerformanceTracker()
        self.assertIsNone(t.boss_kill_signal(), "无 boss 观测 → None")
        t.record(_out(1, 90, node="boss", comp="c"))
        t.record(RoundOutcome(round_num=2, plane=1, node_type="boss", comp_tag="c", killed=True))
        t.record(RoundOutcome(round_num=3, plane=1, node_type="boss", comp_tag="c", killed=False))
        sig = t.boss_kill_signal()
        self.assertIsNotNone(sig)
        self.assertAlmostEqual(sig, 0.5, places=6, msg="1 杀 1 未杀 → 0.5")

    # —— RoundOutcome 字段完整性(telemetry 用)——

    def test_round_outcome_dual_sided_fields(self):
        """RoundOutcome 双侧字段(自身 + 敌方)完整;敌方 None 表不可观测。"""
        o = RoundOutcome(round_num=1, plane=1, node_type="boss", comp_tag="c",
                         hp_after=80, hp_confidence=0.9, enemy_hp_after=None,
                         damage_dealt=None, killed=True)
        self.assertEqual(o.hp_after, 80)
        self.assertTrue(o.killed)
        self.assertIsNone(o.enemy_hp_after)
