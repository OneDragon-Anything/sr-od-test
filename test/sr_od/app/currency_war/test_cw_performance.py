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

import pytest

from sr_od.application.currency_war.cw_comps import ScoreContext, get_comp
from sr_od.application.currency_war.cw_performance import (
    PerformanceTracker,
    RoundOutcome,
    comp_viability,
    is_run_dead,
)
from sr_od.application.currency_war.cw_state import GameState


def _out(round_num: int, hp: int, node: str = "普通战斗", comp: str = "c1",
         fold: bool = False, conf: float = 1.0, plane: int = 1) -> RoundOutcome:
    return RoundOutcome(round_num=round_num, plane=plane, node_type=node, comp_tag=comp,
                        intentional_fold=fold, hp_after=hp, hp_confidence=conf)


# —— r6 F1: intentional_fold 排除 ——


def test_fold_excluded_from_trend() -> None:
    """故意输(fold)的大掉血不污染 trend:fold 排除后只 1 个 qualifying → None。"""
    t = PerformanceTracker()
    t.record(_out(1, 100))
    t.record(_out(2, 50, fold=True))    # 故意输掉 50 —— 排除
    assert t.recent_hp_loss_trend() is None, "fold 排除后 <2 → None(不污染)"


def test_non_fold_big_loss_detected() -> None:
    """同样掉 50 但非 fold → trend 检测到大掉血(对照)。"""
    t = PerformanceTracker()
    t.record(_out(1, 100))
    t.record(_out(2, 50))               # 非故意 → 进 trend
    trend = t.recent_hp_loss_trend()
    assert trend is not None
    assert trend > 0, "非 fold 大掉血应被检测"


# —— r6 F2: 归一化(boss 掉得多不误判)——


def test_boss_loss_normalized_not_misjudged() -> None:
    """打 boss 掉 30(normalized 30/3=10)≈ 普通关掉 10(normalized 10/1=10):归一化后等价。"""
    t_normal = PerformanceTracker()
    t_normal.record(_out(1, 100, node="普通战斗"))
    t_normal.record(_out(2, 90, node="普通战斗"))    # 掉 10
    t_boss = PerformanceTracker()
    t_boss.record(_out(1, 100, node="普通战斗"))
    t_boss.record(_out(2, 70, node="boss"))          # 掉 30,但 boss expected_drop=3.0
    assert t_normal.recent_hp_loss_trend() == pytest.approx(t_boss.recent_hp_loss_trend(), abs=1e-6), (
        "归一化后 boss 掉 30 ≈ 普通关掉 10(不误判弱)"
    )


# —— r6 F4: comp_tag 降权(pivot 后旧 comp ×0.3)——


def test_comp_tag_downweight() -> None:
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
    assert t_mixed.recent_hp_loss_trend(comp_tag="A") < t_all_a.recent_hp_loss_trend(comp_tag="A"), (
        "旧 comp(B)大掉血降权 → trend(A) < 全 A"
    )


# —— r6 F6: 冷启动(<2 → None)——


def test_cold_start_returns_none() -> None:
    """<2 qualifying outcome(无首个差分)→ None。"""
    t = PerformanceTracker()
    assert t.recent_hp_loss_trend() is None, "0 outcome → None"
    t.record(_out(1, 100))
    assert t.recent_hp_loss_trend() is None, "1 outcome 无差分 → None"
    t.record(_out(2, 90))
    assert t.recent_hp_loss_trend() is not None, "2 outcome 有首个差分 → 非 None"


# —— r5: 低置信(<0.7)不进 trend ——


def test_low_confidence_excluded() -> None:
    """OCR 低置信(<0.7)的 outcome 不进 trend(防抖动):只剩 1 个高置信 → None。"""
    t = PerformanceTracker()
    t.record(_out(1, 100, conf=0.9))
    t.record(_out(2, 50, conf=0.4))     # 低置信 → 排除
    assert t.recent_hp_loss_trend() is None, "低置信排除后 <2 → None"
    # 对照:同掉血但高置信 → 检测到
    t2 = PerformanceTracker()
    t2.record(_out(1, 100, conf=0.9))
    t2.record(_out(2, 50, conf=0.9))
    assert t2.recent_hp_loss_trend() is not None


# —— perf_for_comp 映射 ——


def test_perf_for_comp_mapping() -> None:
    """trend=None→None;trend=0→1.0;trend=HP_LOSS_FULL→0。"""
    t = PerformanceTracker()
    assert t.perf_for_comp("A") is None, "冷启动 → None"
    # trend=0(不掉血)→ perf=1.0
    t.record(_out(1, 100, comp="A"))
    t.record(_out(2, 100, comp="A"))
    assert t.perf_for_comp("A") == pytest.approx(1.0, abs=1e-6), "不掉血 → perf=1.0"
    # 每回合掉 HP_LOSS_FULL → trend=HP_LOSS_FULL → perf≈0(用独立 tracker 避免上面 0-delta 稀释)
    t2 = PerformanceTracker()
    t2.record(_out(1, 100, comp="A"))
    t2.record(_out(2, 70, comp="A"))
    t2.record(_out(3, 40, comp="A"))
    perf = t2.perf_for_comp("A")
    assert perf is not None
    assert perf < 0.2, "每回合掉 HP_LOSS_FULL → perf 趋 0"


# —— comp_viability: obs None→纯先验;rounds_seen 增→obs_weight 升 ——


def test_comp_viability_cold_start_pure_prior() -> None:
    """tracker 空(obs None)→ comp_viability = 纯先验(无观测项)。"""
    阿雅 = get_comp("昼神阿雅")
    state = GameState(board={"昼之半神": 4})
    ctx = ScoreContext(mechanics=set())
    t = PerformanceTracker()
    v = comp_viability(阿雅, state, ctx, t)
    assert v > 0.0
    assert v <= 1.0
    # 纯先验(ADR-0107 动态归一:equip/mech 无数据返 None → 剔除,权重重分配给 form/star):
    # = 0.40*form(1.0) / (0.40+0.15) = 0.40/0.55 ≈ 0.727(star=0 无核心持有,仍进加权但贡献 0)
    assert v == pytest.approx(0.727, abs=1e-2), "冷启动纯先验(动态归一,无 equip/mech 数据)"


def test_comp_viability_observation_blends() -> None:
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
    assert warm < cold, "观测到大掉血 → viability 低于纯先验"


def test_star_achievement_scales_with_core_star() -> None:
    """star_achievement:核心角色 star 升 → 达成度高(1星=0 / 2星=0.5 / 3星=1.0;review HIGH-1)。"""
    from sr_od.application.currency_war.cw_performance import star_achievement
    from sr_od.application.currency_war.cw_state import BenchChar
    飞霄 = get_comp("追击飞霄")
    core = 飞霄.core_chars[0]
    s1 = GameState(bench=[BenchChar(slot=0, char_id=core, faction='追击', star=1)])
    assert star_achievement(飞霄, s1) == pytest.approx(0.0, abs=1e-6)
    s2 = GameState(bench=[BenchChar(slot=0, char_id=core, faction='追击', star=2)])
    assert star_achievement(飞霄, s2) == pytest.approx(0.5, abs=1e-6)
    s3 = GameState(bench=[BenchChar(slot=0, char_id=core, faction='追击', star=3)])
    assert star_achievement(飞霄, s3) == pytest.approx(1.0, abs=1e-6)
    assert star_achievement(飞霄, GameState()) == 0.0   # 无核心持有 → 0


# —— is_run_dead 三门 ——


def test_is_run_dead_three_gates() -> None:
    """死局 = HP低 + trend高 + 锁不住血节点;缺一门 → False;冷启动 → False。"""
    # 造 trend>15:o1(100)→o2(80) 掉 20
    def _tracker() -> PerformanceTracker:
        t = PerformanceTracker()
        t.record(_out(1, 100))
        t.record(_out(2, 80))
        return t
    t = _tracker()
    danger_boss = GameState(hp=10)          # hp<DEAD_HP(20)
    assert is_run_dead(danger_boss, t, "boss"), "hp低+trend高+boss → 死"
    assert not is_run_dead(danger_boss, t, "普通战斗"), "普通关可能锁血 → 不死"
    safe_hp = GameState(hp=80)              # hp 不低
    assert not is_run_dead(safe_hp, t, "boss"), "hp 不低 → 不死"
    # 冷启动(trend None)→ 不死
    assert not is_run_dead(danger_boss, PerformanceTracker(), "boss"), "冷启动 trend None → 不死"


# —— boss_kill_signal / set_required_damage ——
# ⚖️ 已随敌方侧死链删除(2026-08-16 review D4-D7):boss 击杀信号与伤害基准的正式归宿
# 是 19 号伤害账本(cw_damage_ledger,ADR-0166);原方法无生产调用/无读者,测试随之移除。
# ledger 侧对应用例见 test_cw_damage_ledger.py(括号法收敛/修改器定价)。


# —— is_losing_streak(连败=持续高掉血)——


def test_is_losing_streak_threshold_and_cold_start() -> None:
    """is_losing_streak:trend > HP_LOSS_FULL*0.6(=18)→ True;低掉血 → False;冷启动 → False。"""
    # 每回合掉 20(普通关 normalized=20)> 18 → streak
    t_streak = PerformanceTracker()
    t_streak.record(_out(1, 100))
    t_streak.record(_out(2, 80))
    assert t_streak.is_losing_streak(), "trend=20>18 → 连败"
    # 小掉血(normalized=5)< 18 → 非 streak
    t_ok = PerformanceTracker()
    t_ok.record(_out(1, 100))
    t_ok.record(_out(2, 95))
    assert not t_ok.is_losing_streak(), "trend=5<18 → 非连败"
    # 冷启动(样本不足 trend=None)→ False
    assert not PerformanceTracker().is_losing_streak(), "冷启动 → False"


# —— RoundOutcome 字段完整性(telemetry 用)——


def test_round_outcome_dual_sided_fields() -> None:
    """RoundOutcome 双侧字段(自身 + 敌方)完整;敌方 None 表不可观测。"""
    o = RoundOutcome(round_num=1, plane=1, node_type="boss", comp_tag="c",
                     hp_after=80, hp_confidence=0.9, enemy_hp_after=None,
                     damage_dealt=None, killed=True)
    assert o.hp_after == 80
    assert o.killed
    assert o.enemy_hp_after is None
