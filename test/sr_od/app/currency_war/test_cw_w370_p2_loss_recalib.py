"""P2 损血标定锁(W443 批 C 两态定稿的批 3 重推版)。

批 3 预算收权:cw_horizon DP 世界模型(difficulty_scale/_hp_loss/solve/
平局扫描序)整模块退役,其专属锁随迁删除——两态标定的**存活消费面**=
registry 两表 + cw_plane_table.p_win_p2 胜率映射 + cw_first_passage
阈值层 μ 闭环,本文件只锁这些。删除锁的语义出处 = BLUEPRINT §3 DP
处置(git prior art);两态化治本记录见 ADR-0440。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① scoring 侧:vd_p2_loss = 20.05(P2 V_D 收益侧条件败局伤害,与
  Δwin_rate 相乘不双计;标定源=P2 损血谱粗档 w324 桶均值,冻结语料);
- ② registry 两表值锁(同一 W375 双源标定的两个 estimand,非双源):
  p2_node_loss_table=W375 无条件期望三档(标定自洽锚,无行为消费);
  p2_cond_loss_table=W375 条件败面三档(消费面=rounds_alive+阈值层 μ);
- ③ 板强→胜率映射形态:锚点逐位=表值、分段线性、b>2 钳 rung2;
- ④ 阈值层与胜率侧同标定源(双源合一不变量,防回植本地乘数);
- ⑤ 确定性折中常量 P2_LOSS_SCALE=6.0 在任何存活模块不复存在。
"""
from __future__ import annotations

import dataclasses

import pytest

from sr_od.application.currency_war import cw_plane_table
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

# 标定值单一源(cw_sim_checks 同值消费禁令:本文件只锁值,不做第二份推导)
_VD_P2_LOSS_CALIB = 20.05    # w354_p2_loss_calib.json p2|normal mean(条件伤害)
_W375_COND = {'normal': 12.77, 'encounter': 13.33,
              'boss': 15.50, 'reward': 0.0}


def test_vd_p2_loss_calibrated_value() -> None:
    """①scoring 侧重校值锁。"""
    assert DEFAULT_REGISTRY.vd_p2_loss == _VD_P2_LOSS_CALIB


def test_w375_tables_injected() -> None:
    """②两表值锁(无条件期望/条件败面各归其消费面;版本锚 v1)。"""
    assert DEFAULT_REGISTRY.p2_node_loss_table == {
        'normal': 10.16, 'encounter': 12.00,
        'boss': 15.50, 'reward': 0.0}
    assert DEFAULT_REGISTRY.p2_cond_loss_table == _W375_COND
    assert DEFAULT_REGISTRY.p2_loss_calib_version == 1


def test_two_state_pwin_interpolation() -> None:
    """③板强→胜率映射形态:锚点逐位=表值、分段线性、b>2 钳 rung2
    (与 p_win 表 k3 折叠同口径;单一源=cw_plane_table.p_win_p2)。"""
    assert cw_plane_table.p_win_p2(0.0) == DEFAULT_REGISTRY.p_win_p2_by_rung[0]
    assert cw_plane_table.p_win_p2(1.0) == DEFAULT_REGISTRY.p_win_p2_by_rung[1]
    assert cw_plane_table.p_win_p2(2.0) == DEFAULT_REGISTRY.p_win_p2_by_rung[2]
    assert cw_plane_table.p_win_p2(2.9) == cw_plane_table.p_win_p2(2.0), \
        'b>2 钳 rung2'
    mid = cw_plane_table.p_win_p2(1.5)
    expect = 0.5 * (DEFAULT_REGISTRY.p_win_p2_by_rung[1]
                    + DEFAULT_REGISTRY.p_win_p2_by_rung[2])
    assert mid == pytest.approx(expect)


def test_threshold_shares_calibration_with_pwin(monkeypatch) -> None:
    """④阈值层与胜率侧同标定源(双源合一不变量):_loss_dist P2 μ 的条件
    档同用 registry.p2_cond_loss_table——注入自定义条件档,阈值层 μ
    与 (1−p)·注入值闭环位移(改动标定面两处同步,防回植本地乘数)。"""
    from sr_od.application.currency_war.decision_v2 import registry as reg_mod
    from sr_od.application.currency_war.cw_first_passage import _loss_dist
    reg = dataclasses.replace(
        reg_mod.DEFAULT_REGISTRY, p2_cond_loss_table={
            'normal': 5.0, 'encounter': 5.0, 'boss': 5.0, 'reward': 0.0})
    monkeypatch.setattr(reg_mod, 'DEFAULT_REGISTRY', reg)
    mu = _loss_dist(2, 2)[1][0]
    assert mu == pytest.approx(
        (1.0 - cw_plane_table.p_win_p2(2)) * 5.0, abs=1e-9)


def test_p2_loss_scale_constant_retired() -> None:
    """⑤确定性折中常量退役锁:旧 P2_LOSS_SCALE=6.0 在存活模块
    (标定表/胜率映射/registry)不复存在(见 ADR-0440)。"""
    assert not hasattr(cw_plane_table, 'P2_LOSS_SCALE')
    assert not hasattr(DEFAULT_REGISTRY, 'P2_LOSS_SCALE')
