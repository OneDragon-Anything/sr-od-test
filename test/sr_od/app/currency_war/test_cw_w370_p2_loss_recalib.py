"""P2 损血标定锁(W443 批 C:两态递推定稿;原 W370 重校 6.0 折中退役)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① scoring 侧:vd_p2_loss = 20.05(P2 V_D 收益侧条件败局伤害,与
  Δwin_rate 相乘不双计;标定源=P2 损血谱粗档 w324 桶均值,冻结语料);
- ② registry 两表值锁(同一 W375 双源标定的两个 estimand,非双源):
  p2_node_loss_table=W375 无条件期望三档(10.16/12.00/15.50,**无行为
  消费——标定自洽锚**,语义见 registry 注释与对齐锁);p2_cond_loss_table
  =W375 条件败面三档(12.77/13.33/15.50,消费面=两态决策层
  rounds_alive+DP 递推+阈值层 μ);
- ③ P1/P3 段零漂移:difficulty_scale P1 分段(0.5/0.9/1.4)与 P3 段
  (1.8+0.05·node)逐位旧语义;P2 槽误用 difficulty_scale 即 raise
  (P2 损血已走两态递推,防静默吃 P3 曲线);
- ④ DP 两态闭环:_hp_loss(P2)=(1−p(b))·L_cond——p=registry.
  p_win_p2_by_rung 分段线性(b∈{0,1,2} 锚),L_cond 非 boss 槽=
  normal+encounter 模板混合档、boss 端槽=boss 档;典型板数值闭环锁;
- ⑤ P2 全死区平局裁决为存息(低花费),不是烧钱姿态
  (W371 M1 必修:堵「死→烧光」扫描序病理;P1 槽保持旧序零漂移)。

防回退依据:两态化是 W371 A1/A2(必死区/强板悲观)的治本件——确定性
递推吃条件伤害是值函数坍缩与 6.0 折中的共同根;回退=重新走标定流程
(口径定稿见 ADR-0440),不接受静默改参。
"""
from __future__ import annotations

import dataclasses

import pytest

from sr_od.application.currency_war import cw_horizon as hz
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

# 标定值单一源(cw_sim_checks 同值消费禁令:本文件只锁值,不做第二份推导)
_VD_P2_LOSS_CALIB = 20.05    # w354_p2_loss_calib.json p2|normal mean(条件伤害)
_W375_UNCOND = {'normal': 10.16, 'encounter': 12.00,
                'boss': 15.50, 'reward': 0.0}
_W375_COND = {'normal': 12.77, 'encounter': 13.33,
              'boss': 15.50, 'reward': 0.0}


def test_vd_p2_loss_calibrated_value() -> None:
    """①scoring 侧重校值锁。"""
    assert DEFAULT_REGISTRY.vd_p2_loss == _VD_P2_LOSS_CALIB


def test_w375_tables_injected() -> None:
    """②两表值锁(无条件期望/条件败面各归其消费面;版本锚 v1)。"""
    assert DEFAULT_REGISTRY.p2_node_loss_table == _W375_UNCOND
    assert DEFAULT_REGISTRY.p2_cond_loss_table == _W375_COND
    assert DEFAULT_REGISTRY.p2_loss_calib_version == 1


def test_p1_p3_scales_unchanged() -> None:
    """③P1/P3 段零漂移(重校辖域仅 P2 的结构锚)+ P2 误用 raise。"""
    for node in range(9):
        expect = 0.5 if node < 4 else (0.9 if node < 8 else 1.4)
        assert hz.difficulty_scale(node) == expect, node
        assert hz.difficulty_scale(18 + node) == 1.8 + 0.05 * node, node
    with pytest.raises(ValueError):
        hz.difficulty_scale(9)


def _cond_mix() -> float:
    """非 boss 战斗槽条件档(normal+encounter 模板混合;与生产同源推导)。"""
    from sr_od.application.currency_war.cw_line_switch import (
        _P2_NODE_TEMPLATE, node_loss_kind)
    tbl = DEFAULT_REGISTRY.p2_cond_loss_table
    kinds = [node_loss_kind(nt) for nt in _P2_NODE_TEMPLATE]
    battle = [k for k in kinds if k not in ('reward', 'boss')]
    return sum(tbl[k] for k in battle) / len(battle)


def test_dp_hp_loss_p2_two_state() -> None:
    """④DP 两态闭环:drop=(1−p(b))·L_cond(kind)。
    - b=0(lv2):p=0.016 → 0.984·混合档;
    - b=2(lv7):p=0.657 → 0.343·混合档;
    - boss 端槽(日程 (9,7,9) 的 t=15):0.343·boss 档;
    - 中间板 b=1.6(lv6):分段线性 p=0.5594。"""
    mix = _cond_mix()
    assert hz._hp_loss(9, 2, 0.0) == pytest.approx(0.984 * mix, abs=0.01)
    assert hz._hp_loss(9, 7, 0.0) == pytest.approx(0.343 * mix, abs=0.01)
    assert hz._hp_loss(15, 7, 0.0, (9, 7, 9)) == pytest.approx(
        0.343 * _W375_COND['boss'], abs=0.01)
    assert hz._hp_loss(9, 6, 0.0) == pytest.approx(
        0.4406 * mix, abs=0.01)
    # 板强通道进胜率侧不进幅度侧(W371 A2):b0 与 b2 的 drop 比=胜率比
    assert hz._hp_loss(9, 2, 0.0) > hz._hp_loss(9, 7, 0.0) * 2


def test_p2_tie_break_conservative(monkeypatch) -> None:
    """⑤P2 全死区平局裁决为存息(低花费),不是烧钱姿态
    (W371 M1 必修:堵「死→烧光」扫描序病理;P1 槽保持旧序零漂移)。"""
    # 全死区帧:hp=5、金 20、lv6——任何可行动作(升级/刷)都抬不过
    # drop(b=1.6≈(1−0.5594)·混合档>5)→ 全动作 V≡0 → 平局由扫描序裁决
    sol = hz._solved(None)
    posture = sol.posture(9, 20, 6, 5, 0.0)
    assert posture.v == 0.0, '前置:该帧应为全死区(V≡0)'
    assert posture.save and posture.refresh_budget == 0 \
        and not posture.level_up, posture.tag


def test_p2_loss_scale_constant_retired() -> None:
    """确定性折中常量退役锁:旧 P2_LOSS_SCALE=6.0 不复存在(两态递推
    定稿后,「CI 下界压必死区」的折中前提不再成立——见 ADR-0440)。"""
    assert not hasattr(hz, 'P2_LOSS_SCALE')


def test_two_state_pwin_interpolation() -> None:
    """板强→胜率映射形态:锚点逐位=表值、分段线性、b>2 钳 rung2
    (与 p_win 表 k3 折叠同口径)。"""
    assert hz.p_win_p2(0.0) == DEFAULT_REGISTRY.p_win_p2_by_rung[0]
    assert hz.p_win_p2(1.0) == DEFAULT_REGISTRY.p_win_p2_by_rung[1]
    assert hz.p_win_p2(2.0) == DEFAULT_REGISTRY.p_win_p2_by_rung[2]
    assert hz.p_win_p2(2.9) == hz.p_win_p2(2.0), 'b>2 钳 rung2'
    mid = hz.p_win_p2(1.5)
    expect = 0.5 * (DEFAULT_REGISTRY.p_win_p2_by_rung[1]
                    + DEFAULT_REGISTRY.p_win_p2_by_rung[2])
    assert mid == pytest.approx(expect)


def test_threshold_shares_calibration_with_dp(monkeypatch) -> None:
    """阈值层与 DP 同标定源(双源合一不变量):_loss_dist P2 μ 的条件
    档同用 registry.p2_cond_loss_table——注入自定义条件档,阈值层 μ
    与 (1−p)·注入值闭环位移(改动标定面两处同步,防回植本地乘数)。"""
    from sr_od.application.currency_war.decision_v2 import registry as reg_mod
    from sr_od.application.currency_war.cw_first_passage import _loss_dist
    reg = dataclasses.replace(
        reg_mod.DEFAULT_REGISTRY, p2_cond_loss_table={
            'normal': 5.0, 'encounter': 5.0, 'boss': 5.0, 'reward': 0.0})
    monkeypatch.setattr(reg_mod, 'DEFAULT_REGISTRY', reg)
    mu = _loss_dist(2, 2)[1][0]
    assert mu == pytest.approx((1.0 - hz.p_win_p2(2)) * 5.0, abs=1e-9)
