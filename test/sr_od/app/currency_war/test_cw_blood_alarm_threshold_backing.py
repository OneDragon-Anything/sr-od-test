"""血警三臂阈值 + emergency_hp 的推导背书锁。

锁推导结论而非哈希:全部阈值锚定 math_proofs P15 条件败局伤害
L_c(rung)=11.32−0.37·rung(registry.vd_p1_loss_* 单一源,ADR-0425)
与重生基数 rebirth_floor=20(口述 [18],user_playstyle.md):

- 单场打输线 10 = L_c 的 rung 代表值(中点 rung4≈9.84 / rung2≈10.58);
- 累计 20 ≈ 2×L_c(rung2)=21.2(急性臂:3 节点窗两次满额败局);
- 累计 30 ≈ 3×L_c(rung2)=31.7(慢性臂:5 节点窗三次满额败局);
- emergency_hp=25 ∈ (2×L_c, rebirth_floor+L_c) = (21.2, 30.6):
  双失缓冲带内、一次败局不破重生基数的下沿区。

若 registry.vd_p1_loss_* 或 rebirth_floor 重标定,本锁按推导式重算,
不是机械改期望常数。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.discipline import (
    BLOOD_MARGIN_LOW_HP,
    BloodAlarmTracker,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY


def _lc(rung: int) -> float:
    """P15 条件败局伤害期望(单一源=registry 拟合常数)。"""
    return (_REG.vd_p1_loss_intercept
            + _REG.vd_p1_loss_slope_rung * rung)


def test_emergency_hp_in_two_loss_buffer_band() -> None:
    """emergency_hp ∈ (2×L_c(rung2), rebirth_floor+L_c(rung2)):
    能吸收两次满额条件败局、且一次败局后仍可保住重生基数。"""
    lc2 = _lc(2)
    assert _REG.emergency_hp > 2 * lc2, \
        f'应急线({_REG.emergency_hp})须高于双失吸收上界 {2 * lc2:.1f}'
    assert _REG.emergency_hp < _REG.rebirth_floor + lc2, \
        (f'应急线({_REG.emergency_hp})须低于一次败局即破重生基数上界 '
         f'{_REG.rebirth_floor + lc2:.1f}')


def test_single_loss_line_at_conditional_loss_magnitude() -> None:
    """单场打输线 10 ∈ [L_c(rung4), L_c(rung0)] 且 ≥L_c(rung8):
    阈值落在条件败局期望的 rung 全域代表带内——达到该量级=结构性
    打输;低于它的败局(敌血近清空小伤害)作波动。"""
    assert _lc(8) <= 10 <= _lc(0)
    # L_c(4)=9.84 → 取整代表值容差:10 与中点差 <1
    assert abs(10 - _lc(4)) < 1.0


def test_cumulative_arms_are_loss_count_multiples() -> None:
    """②20/③30 = L_c(rung2) 的 2/3 倍取整(≤ 对应倍数、> 降一档):
    语义=窗内满额败局次数下限,而非任意魔数。"""
    lc2 = _lc(2)
    assert 2 * lc2 - 2 < 20 <= 2 * lc2      # 20 ≈ 2×10.58=21.2,取整容差 2
    assert 3 * lc2 - 2 < 30 <= 3 * lc2      # 30 ≈ 3×10.58=31.7


def test_arm1_two_consecutive_full_losses_trigger() -> None:
    """臂①:连续两场 ≥10 的满额败局 → 报警;单场不触发;
    连续两场 9(低于单场线)不触发——锁单场线的截断语义。"""
    t = BloodAlarmTracker()
    t.record('battle', 100, 89, t=1, plane=1)   # -11 ≥10
    assert not t.alarm_active()
    t.record('battle', 89, 78, t=2, plane=1)    # -11,连续第 2 场
    assert t.alarm_active()

    t2 = BloodAlarmTracker()
    t2.record('battle', 100, 92, t=1, plane=1)  # -8 <10(小伤害波动)
    t2.record('battle', 92, 84, t=2, plane=1)   # -8,连续但未达线
    assert not t2.alarm_active()


def test_arm2_three_battle_window_two_losses_equivalent() -> None:
    """臂②:3 个战斗节点累计 ≥20(≈2×L_c)触发——容 1 个良性节点
    的急性账;累计 18(两次小伤害败局)不触发。"""
    t = BloodAlarmTracker()
    t.record('battle', 100, 93, t=1, plane=1)   # -7
    t.record('battle', 93, 79, t=2, plane=1)    # -14
    t.record('battle', 79, 72, t=3, plane=1)    # -7,累计 28 ≥20
    assert t.alarm_active()

    t2 = BloodAlarmTracker()
    for i in range(3):
        t2.record('battle', 100 - 6 * i, 94 - 6 * i, t=i + 1, plane=1)
    assert sum(l for _t, l in t2.recent_losses) == 18
    assert not t2.alarm_active()


def test_arm3_five_battle_window_chronic_drift() -> None:
    """臂③:5 个战斗节点累计 ≥30(≈3×L_c)触发慢性漂移臂;
    窗口滚动——第 5 个节点喂入时含第 1 个节点的掉血。"""
    t = BloodAlarmTracker()
    losses = [6, 6, 6, 6, 6]   # 累计 30,无单场 ≥10、无 3 窗 ≥20
    hp = 100
    for i, l in enumerate(losses):
        t.record('battle', hp, hp - l, t=i + 1, plane=1)
        hp -= l
    assert t.alarm_active()

    t2 = BloodAlarmTracker()
    hp = 100
    for i, l in enumerate([5, 5, 5, 5, 5]):    # 累计 25 <30
        t2.record('battle', hp, hp - l, t=i + 1, plane=1)
        hp -= l
    assert not t2.alarm_active()


def test_25_40_gradient_semantics_unchanged() -> None:
    """两线并存梯度不因背书替换漂移:40=报警降档(discipline),
    25=应急覆盖态(registry),40>25 维持处置梯度。"""
    assert BLOOD_MARGIN_LOW_HP == 40
    assert _REG.emergency_hp == 25
    assert BLOOD_MARGIN_LOW_HP > _REG.emergency_hp


def _unused_session_guard() -> None:  # pragma: no cover
    # StrategySession 导入保留:后续行为锁若需 session 挂载(v3_alarm)
    # 沿用同一构造口径;本文件当前锁常量与 tracker 行为,无需实例。
    _ = StrategySession
