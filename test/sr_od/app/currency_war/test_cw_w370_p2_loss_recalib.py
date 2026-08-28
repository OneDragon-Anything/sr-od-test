"""P2 损血参数重校锁(P2 生存批 C2:预算参数按实测谱重校)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① scoring 侧:vd_p2_loss = 20.05(P2 V_D 收益侧条件败局伤害,与
  Δwin_rate 相乘不双计);标定源=P2 损血谱粗档(冻结语料 w324 桶均值
  普通战斗 20.05,n=19;删失 hp≤1 → 偏低估方向的取值下界);
- ② DP 侧:P2 段难度系数为常数 P2_LOSS_SCALE=6.0(位面内无梯度——
  节点/板强梯度均未标定,摊平为最少假设),×HP_LOSS_PRIOR[2]=2.5 ≙ 15.0
  (三源中位实机 15.3 → 6.1 / 事件级 CI 下界 15.0 → 6.0,取 6.0 压模型内
  必死区宽度;推导、置信区间与两态化挂账见常量注释);
- ③ P1/P3 段零漂移:difficulty_scale P1 分段(0.5/0.9/1.4)与 P3 段
  (1.8+0.05·node)逐位旧语义——重校辖域仅 P2;
- ④ DP 全等式:_hp_loss(P2, b=2, rb=0)= 20.05(①②在 DP 入口处的
  乘积闭环,防两常量之一被单独回退)。

防回退依据:P2 死亡率实机 93.0% ≈ sim 92.67%(W350 对拍),典型作战板
每战实测损血 15-20(条件 20.05/实机存活局事件 −15.3);旧参数(DP 隐含
≈4/vd 16.0)系统性高估 P2 存活力 → 欠战力投资,是 P2 生存短板的决策侧
病灶。回退=重新走标定流程,不接受静默改参。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war import cw_horizon as hz
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

# 标定值单一源(cw_sim_checks 同值消费禁令:本文件只锁值,不做第二份推导)
_VD_P2_LOSS_CALIB = 20.05    # w354_p2_loss_calib.json p2|normal mean(条件伤害)
_P2_LOSS_SCALE_CALIB = 6.0   # = 15.0/2.5(三源中位/CI 下界口径,见常量注释)


def test_vd_p2_loss_calibrated_value() -> None:
    """①scoring 侧重校值锁。"""
    assert DEFAULT_REGISTRY.vd_p2_loss == _VD_P2_LOSS_CALIB


def test_p2_difficulty_scale_constant() -> None:
    """②P2 段难度系数=常数 8.02(全位面内节点无梯度)。"""
    assert hz.P2_LOSS_SCALE == _P2_LOSS_SCALE_CALIB
    for node in range(9):
        assert hz.difficulty_scale(9 + node) == hz.P2_LOSS_SCALE, node


def test_p1_p3_scales_unchanged() -> None:
    """③P1/P3 段零漂移(重校辖域仅 P2 的结构锚)。"""
    for node in range(9):
        expect = 0.5 if node < 4 else (0.9 if node < 8 else 1.4)
        assert hz.difficulty_scale(node) == expect, node
        assert hz.difficulty_scale(18 + node) == 1.8 + 0.05 * node, node


def test_dp_hp_loss_p2_typical_board() -> None:
    """④DP 入口闭环:b=2 典型板在 P2 任一节点的每战期望损血=重校值
    15.0(系数 × 先验;两常量不可单独回退)。"""
    for node in (0, 3, 6):
        t = 9 + node
        # 浮点乘积的尾差用相对近似吸收(锁语义不锁位)
        assert hz._hp_loss(t, 7, 0.0) == pytest.approx(15.0, abs=0.01), node


def test_p2_tie_break_conservative(monkeypatch) -> None:
    """⑤P2 全死区平局裁决为存息(低花费),不是烧钱姿态
    (W371 M1 必修:堵「死→烧光」扫描序病理;P1 槽保持旧序零漂移)。"""
    # 全死区帧:hp=5、金 20、lv6——任何可行动作(升级/刷)都抬不过
    # drop(最高 b=2.32 → 11.7 > 5)→ 全动作 V≡0 → 平局由扫描序裁决
    sol = hz._solved(None)
    posture = sol.posture(9, 20, 6, 5, 0.0)
    assert posture.v == 0.0, '前置:该帧应为全死区(V≡0)'
    assert posture.save and posture.refresh_budget == 0 \
        and not posture.level_up, posture.tag
