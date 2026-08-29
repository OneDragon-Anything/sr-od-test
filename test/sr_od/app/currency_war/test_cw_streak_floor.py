# -*- coding: utf-8 -*-
"""连胜 EV 地板标定账单帧锁(discipline._streak_floor,ADR-0356 挂账项
标定落地)。

锁契约(每条=一个确定输入下的确定行为;不锁分布浮点全值):
- ① boss 位面末(remaining=0)fire:V_blood(免掉血)单独支撑——
  旧账 (tier−1)×remaining 在此恒不 fire,此锁防回退旧口径;
- ② encounter / 位面临近 battle(硬节点)fire;
- ③ 非硬节点(reward/supply)不 fire(扑满不掉血,深花保血无对象);
- ④ 连胜 <2 不 fire(授权语义只在连胜在手时开通);
- ⑤ C 侧真实跨档锁:带宽 [5, boss_floor) 内最坏跨 2 档(金 20 花 15
  跨 20 档与 10 档)× interest_recovery_rounds=3 → 6 金,锁回档口径
  不漂移;并锁「金 20 的 battle 帧因 C 升至 6 > V 而不 fire」(逐轮
  精算口径的行为面,非巧合值)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.discipline import (
    _streak_floor,
)
from sr_od.application.currency_war.decision_v2.ev import interest_cost
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 12, 'level': 5,
            'hp': 70, 'board': {}, 'bench': [], 'shop': [],
            'node_type': 'battle'}
    base.update(kw)
    return GameState(**base)


def _sess(streak: int = 2,
          node: str | None = None) -> StrategySession:
    sess = StrategySession()
    sess.last_streak = streak
    if node is not None:
        sess.node_type_current = node
    return sess


def test_boss_plane_end_fires_on_blood_term() -> None:
    """①boss r9(remaining=0,连胜金项为 0)→ fire 返 5:V_blood
    单独支撑(0.923×26.71×0.5≈12.3 ≥ C)。"""
    st = _state(round_num=9, node_type='boss')
    assert _streak_floor(st, _sess(node='boss'), _REG,
                         _REG.boss_floor) == 5


def test_encounter_and_battle_hard_nodes_fire() -> None:
    """②encounter(11.7≥3)与位面临近 battle(5.6≥3)→ 返 5。"""
    st_enc = _state(round_num=6, node_type='encounter')
    assert _streak_floor(st_enc, _sess(node='encounter'), _REG,
                         _REG.boss_floor) == 5
    # battle 硬节点=本位面剩余 ≤3(r9 节点图兜底口径)
    st_btl = _state(round_num=9, node_type='battle')
    assert _streak_floor(st_btl, _sess(), _REG,
                         _REG.boss_floor) == 5


def test_non_hard_node_and_low_streak_do_not_fire() -> None:
    """③非硬节点(reward,扑满不掉血)与 ④连胜<2 → 地板原值。"""
    st_r = _state(round_num=4, node_type='reward')
    assert _streak_floor(st_r, _sess(streak=2), _REG, 30) == 30
    st_s = _state(round_num=4, node_type='supply')
    assert _streak_floor(st_s, _sess(streak=2), _REG, 30) == 30
    st_b = _state(round_num=6, node_type='encounter')
    assert _streak_floor(st_b, _sess(streak=1, node='encounter'),
                         _REG, _REG.boss_floor) == _REG.boss_floor


def test_interest_cost_band_worst_case() -> None:
    """⑤带宽 [5, 10) 的息成本上界:金 20 花 15 → 跨 2 档 × recovery
    3.0 = 6 金(真实跨档入参;金 15 花 10 跨 0 档不构成上界)。"""
    st = _state(gold=20)
    assert interest_cost(20, 15, st,
                         _REG.interest_recovery_rounds) == 6.0
    # 行为面:金 20 的 battle 硬节点帧,C 升至 6 > V(≈5.6)→ 不 fire
    # (逐轮精算口径——金低档同帧 C=3 时 fire,见 ②)
    st_btl = _state(round_num=9, gold=20, node_type='battle')
    assert _streak_floor(st_btl, _sess(), _REG,
                         _REG.boss_floor) == _REG.boss_floor
