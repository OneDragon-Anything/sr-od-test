"""cw_damage_ledger(19 号伤害双账本 v0)测试:括号法校准 + 对账三用(ADR-0166)。"""
import pytest

from sr_od.application.currency_war.cw_damage_ledger import DamageLedger


def test_bracket_calibration_converges():
    """核心:不等式括号法 —— 赢/超时约束把 base 区间单调收紧到真值邻域。"""
    led = DamageLedger()
    # 真值:battle base=1.0(难度 10 → 预算 1.0×1.052^10≈1.66);吞吐 1.6 → 超时;<1.66 → 超时
    # 模拟:难度 0,battle 预算真值 ≈ 1.0;我方吞吐 0.9(输)/1.2(赢 overkill)
    led2 = DamageLedger()
    led2.base['battle'] = (0.2, 5.0)          # 宽先验
    led2.record_battle(0.9, won=False, node_type='battle', difficulty=0)
    lo1, hi1 = led2.base['battle']
    led2.record_battle(1.2, won=True, node_type='battle', difficulty=0)
    lo2, hi2 = led2.base['battle']
    assert hi1 < 5.0            # 超时收紧上界
    assert lo2 > 0.2            # 赢局收紧下界
    assert hi2 > lo2            # 区间合法
    assert hi2 - lo2 < 4.8      # 显著窄于先验


def test_gap_and_predict():
    """对账:gap = 预算−吞吐;负 = 白过(奖励关省钱从原则变计算值)。"""
    led = DamageLedger()
    for _ in range(5):
        led.record_throughput(2.0)
    assert led.gap('reward', difficulty=0) < 0        # reward base=0 → 白过
    assert led.predict_win('reward', 0) is True
    assert led.gap('boss', difficulty=20) > 0         # boss 高难度 → 打不动
    assert led.predict_win('boss', 20) is False


def test_modifier_value_analytic():
    """难度修改器解析定价:银−4 ≈ −18% 敌血(1.052^4 ≈ 1.22)。"""
    led = DamageLedger()
    v = led.modifier_value(-4)
    assert -0.25 < v < -0.15          # ≈ −1/1.22 ≈ −18%
    assert led.modifier_value(0) == 0.0
    assert led.modifier_value(30) > 0  # 伟大征服 +30 → 敌血大增(负价值方向)


def test_throughput_running_mean():
    led = DamageLedger()
    led.record_throughput(1.0)
    led.record_throughput(2.0)
    led.record_throughput(3.0)
    assert led.throughput_n == 3
    assert abs(led.throughput_est - 2.0) < 1e-9


def test_diagnosis_split():
    """分诊:缺口型 vs 衰减型(hp_delta 单信号原则上做不了的分解)。"""
    led = DamageLedger()
    assert '缺口型' in led.diagnosis(0.5)
    assert '衰减型' in led.diagnosis(1.5, share_drop=-0.4)
    assert '缺口型' in led.diagnosis(1.5, share_drop=-0.05)


def test_constraint_conflict_widens_not_crashes():
    """约束冲突(模型错)→ 放宽包络不崩(L2 违反率负责暴露)。"""
    led = DamageLedger()
    led.base['battle'] = (1.0, 1.0)
    led.record_battle(0.1, won=False, node_type='battle', difficulty=0)
    lo, hi = led.base['battle']
    assert lo <= hi   # 合法(包络)
