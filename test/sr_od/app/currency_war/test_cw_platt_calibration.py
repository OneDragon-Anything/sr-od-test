"""W509:影子模型 Platt 概率再校准层的锁测试。

出处(设计单一源):
- 校准层语义/默认恒等零漂移/拟合纪律(只许遥测锚拟合、先验面禁入)
  = ``cw_win_model.PlattCalibrator`` / ``fit_platt_scaling`` docstring;
- 选 Platt 而非温度缩放的依据 = 失真形态是「偏移主导 + 尺度分量」,
  单参数温度缩放表达不了纯偏移(Platt 双参数严格包含温度缩放为特例);
- 纯函数锁判据 = ``fit_platt_scaling`` 零 IO、零随机、同入参同参。
"""
from __future__ import annotations

import math

import pytest

from sr_od.application.currency_war.telemetry.cw_win_model import (
    PlattCalibrator,
    fit_platt_scaling,
)


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


# --- 恒等默认零漂移锁 --------------------------------------------------------

def test_identity_default_is_zero_drift() -> None:
    """默认参数 a=1, b=0 = 恒等映射:任意合法 p 逐位不变(校准层关闭态)。"""
    assert PlattCalibrator().a == 1.0 and PlattCalibrator().b == 0.0
    for p in (0.0, 1e-9, 0.01, 0.2, 0.5, 0.7321, 0.99, 1.0 - 1e-9, 1.0):
        assert PlattCalibrator().apply(p) == p, p


def test_identity_short_circuit_exact() -> None:
    """恒等短路路径返回原 float 对象值(非 sigmoid 数值往返),杜绝浮点漂移。"""
    p = 0.123456789012345678
    assert PlattCalibrator().apply(p) is p or PlattCalibrator().apply(p) == p


def test_out_of_range_input_passthrough() -> None:
    """越界/非有限输入原样返回(防御口径:不静默修正也不抛)。"""
    cal = PlattCalibrator(a=2.0, b=-1.0)
    assert cal.apply(-0.1) == -0.1 and cal.apply(1.1) == 1.1
    assert math.isnan(cal.apply(float('nan')))
    assert cal.apply(float('inf')) == float('inf')


# --- 拟合纯函数锁 ------------------------------------------------------------

def test_fit_recovers_known_linear_logit_transform() -> None:
    """可识别性锁:标签按 ``y ~ Bernoulli(sigmoid(a·logit(p)+b))`` 采样
    (真随机噪声标签 → 数据不可分,LR 极大似然一致),拟合应恢复 (a, b)
    (有限样本估计误差,量级锁 ±40%)。注:近可分数据(标签近乎确定性)
    会使无正则 LR 斜率发散,是 Platt 已知边界——故必须用伯努利采样标签。"""
    a_true, b_true = 1.8, -1.2
    n = 4000
    ys: list[int] = []
    ps: list[float] = []
    # 确定性伪随机(lcg),保持纯函数测试零随机依赖
    s = 12345
    for i in range(n):
        z = -3.0 + 6.0 * i / n
        p = _sigmoid(z)
        q = _sigmoid(a_true * z + b_true)  # logit(p) == z,真后验即 Platt 模型
        s = (s * 1103515245 + 12345) % (1 << 31)
        ys.append(1 if s / (1 << 31) < q else 0)
        ps.append(p)
    cal = fit_platt_scaling(ys, ps)
    assert cal.a == pytest.approx(a_true, rel=0.4)
    assert cal.b == pytest.approx(b_true, abs=0.8)


def test_fit_is_pure_and_deterministic() -> None:
    """纯函数锁:同入参两次拟合结果逐一相同(零随机/零 IO 的可观测面)。"""
    ys = [1, 0, 1, 1, 0, 0, 1, 0] * 5
    ps = [0.9, 0.1, 0.8, 0.7, 0.2, 0.3, 0.6, 0.4] * 5
    c1 = fit_platt_scaling(ys, ps)
    c2 = fit_platt_scaling(ys, ps)
    assert c1 == c2 and (c1.a, c1.b) != (1.0, 0.0)


def test_fit_degenerate_inputs_fall_back_identity() -> None:
    """退化输入(空/单类/全非法概率)→ 恒等降级(校准层自动关闭,不抛):
    单类锚定不了偏移与尺度,硬拟合会把校准面扭曲成常数——宁可不校准。"""
    ident = PlattCalibrator()
    assert fit_platt_scaling([], []) == ident
    assert fit_platt_scaling([1, 1, 1], [0.2, 0.5, 0.9]) == ident
    assert fit_platt_scaling([0, 0, 0], [0.2, 0.5, 0.9]) == ident
    assert fit_platt_scaling([1, 0], [float('nan'), 0.5]) == ident
    # 部分行非法:合法行仍参与拟合(剔除而非整批作废)
    c = fit_platt_scaling([1, 0, 1, 0], [1.5, 0.1, 0.9, 0.2])
    assert c.a > 0  # 正常学出正斜率


def test_fit_reduces_systematic_undershoot() -> None:
    """语义锁(锁的是校准意图,不是 LR 数值):构造「排序好但概率整体
    下压」的锚(欠冲形态,出处=W495 影子对拍顶桶偏差 −0.30),
    拟合后的校准应把桶均值偏差显著收窄。"""
    n = 1500
    ys: list[int] = []
    ps: list[float] = []
    s = 777
    for i in range(n):
        z = -3.0 + 6.0 * i / n
        s = (s * 1103515245 + 12345) % (1 << 31)
        noise = s / (1 << 31) - 0.5
        ys.append(1 if z + noise > 0 else 0)
        ps.append(_sigmoid(0.35 * z - 0.6))  # 压缩 + 下压 → 高分段欠冲
    cal = fit_platt_scaling(ys, ps)
    bias_before = sum(ps) / n - sum(ys) / n
    ps_cal = [cal.apply(p) for p in ps]
    bias_after = sum(ps_cal) / n - sum(ys) / n
    assert abs(bias_after) < abs(bias_before)
    # 顶桶(原分数最高段)欠冲收敛方向
    k = n // 4
    top = sorted(range(n), key=lambda i: ps[i])[-k:]
    bias_top_before = sum(ps[i] for i in top) / k - sum(ys[i] for i in top) / k
    bias_top_after = (sum(ps_cal[i] for i in top) / k
                      - sum(ys[i] for i in top) / k)
    assert abs(bias_top_after) < abs(bias_top_before)
