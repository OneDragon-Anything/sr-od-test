"""两态底座批 A 单帧锁:p_win_p2_by_rung 注入 + 两态开关 + rung 取样坐标。

锁面:
- 注入值锁:p_win_p2_by_rung 三档 = W346 Δ池分 rung 胜占比实测
  (出处/口径勘误/证据等级见 registry.p_win_p2_by_rung 注释);
- 零漂移锚:rounds_two_state_enabled 默认关——表注入后消费侧仍逐位
  =条件常数投影(M1a),开关是行为唯一闸;
- 两态消费锁:开关开 + 表注入 → loss=(1−p_win)·表值(REDESIGN §3.6
  hp=29 数表 ra=7 各档同 p 夹具复现);
- rung 取样坐标锁:两态分支读 cw_sim._settle_rung(与 W346 表采样键
  同源),非 scoring._engines_formed——夹具让两坐标分裂(deployed 2
  仙舟 + bench 3 仙舟:混合域加权过 tier=3、settle deployed 域不过),
  锁死取样侧防坐标错位复发(错位方向=p_win 偏乐观=门偏松)。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.kernel import cw_battle_calib as cw_sim
from sr_od.application.currency_war.kernel.cw_line_switch import (
    rounds_alive,
    survival_gate,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import (
    _engines_formed,
)

P2_FULL_TABLE = ['battle', 'battle', 'encounter', 'reward',
                 'encounter', 'reward', 'boss']


def _state(**kw) -> GameState:
    base = {
        'plane': 2, 'round_num': 1, 'gold': 30, 'level': 5,
        'hp': 20, 'hp_readable': True,
        'board': {}, 'deployed': [], 'bench': [], 'shop': [],
    }
    base.update(kw)
    return GameState(**base)


def _sess() -> StrategySession:
    s = StrategySession()
    s.plane_node_table = list(P2_FULL_TABLE)
    s.plane_node_table_plane = 2
    s.round_num = 1
    return s


# --- 注入值锁 ----------------------------------------------------------------


def test_p_win_table_injection_values() -> None:
    """三档值与单调性(两态模型前提「p 对成型度单调不减」的实例面):
    {0: 0.016, 1: 0.413, 2: 0.657}=W346 Δ池 w346_dmg_delta.json 战斗
    d>0 占比(k3 钳制并入 rung2)。值动=重标定,须随批重锁。"""
    t = DEFAULT_REGISTRY.p_win_p2_by_rung
    assert t == {0: 0.016, 1: 0.413, 2: 0.657}
    assert t[0] <= t[1] <= t[2], '单调不减是两态模型的机制前提'
    assert all(0.0 <= v <= 1.0 for v in t.values())


def test_two_state_switch_default_off() -> None:
    """零漂移锚:开关默认关(即使 p_win 表已注入,投影仍走条件常数)。"""
    assert DEFAULT_REGISTRY.rounds_two_state_enabled is False


# --- 零漂移锚:开关关=条件常数逐位 ---------------------------------------------


def test_flag_off_table_injected_still_conditional_constant() -> None:
    """开关关 + 表已注入(默认 registry 现态)→ rounds_alive 与
    「p 表为空」的 M1a 条件常数投影逐位一致(W443 后幅度源=条件败面档
    12.77/13.33/15.50;hp=29:12.77→16.23→3.46→遭遇死 → ra=3;
    hp=43 → ra=5;hp=60 → ra=7,与 C4-L1 手算同数表)。"""
    reg_empty = dataclasses.replace(
        DEFAULT_REGISTRY, p_win_p2_by_rung={})
    for hp, ra in ((29, 3), (43, 5), (60, 7)):
        assert rounds_alive(_state(hp=hp), _sess()) == ra
        assert rounds_alive(_state(hp=hp), _sess(), reg_empty) == ra
    # 门链同锚:默认 registry 下门放行路径与注入前一致(开关关=放行
    # 由 gate 总开关辖,本锁辖投影口径不被表注入漂移)。
    assert DEFAULT_REGISTRY.line_switch_survival_gate_enabled is False


# --- 两态消费锁 ---------------------------------------------------------------


_REG_TWO = dataclasses.replace(
    DEFAULT_REGISTRY, rounds_two_state_enabled=True,
    line_switch_survival_gate_enabled=True,
    p_win_p2_by_rung={0: 0.65, 1: 0.65, 2: 0.65})


def test_flag_on_consumes_p_win() -> None:
    """开关开 → loss=(1−p_win)·条件败面档:空板 rung=0、p=0.65、hp=29 →
    ra=7 ≥ need → 放行(REDESIGN §3.6 两行行为的两态行;W443 后数表=
    条件档 12.77/13.33/15.50 ×0.35,总损 23.7<29 走完全表)。开关关时
    同帧 ra=3(上锁),闸唯一。"""
    assert rounds_alive(_state(hp=29), _sess(), _REG_TWO) == 7
    ok, why = survival_gate(_state(hp=29), _sess(), 2.0, _REG_TWO)
    assert ok and why == 'ok'


def test_flag_on_empty_table_degrades_to_conditional_constant() -> None:
    """开关开但表缺档(rung 缺键)→ p_win=0 → 退化条件常数(空表=
    缺档同路,M1a 保底不因开臂丢失;条件档下 hp=29:12.77→16.23→3.46
    →遭遇死 → ra=3)。"""
    reg = dataclasses.replace(
        DEFAULT_REGISTRY, rounds_two_state_enabled=True,
        p_win_p2_by_rung={1: 0.65, 2: 0.65})   # 缺 rung 0 键
    assert rounds_alive(_state(hp=29), _sess(), reg) == 3


# --- rung 取样坐标锁 -----------------------------------------------------------


def _mixed_domain_state() -> GameState:
    """deployed 2 仙舟 + bench 3 仙舟:混合域(_engines_formed,bench
    ×0.35 加权)仙舟计数 3.05 过 tier=3 → rung 1;settle 坐标
    (_settle_rung,deployed 全集)计数 2 不过 → rung 0。两坐标分裂。"""
    deployed = [BenchChar(slot=1, char_id='停云', faction='仙舟'),
                BenchChar(slot=2, char_id='藿藿', faction='仙舟')]
    bench = [BenchChar(slot=i, char_id='青雀', faction='仙舟')
             for i in (3, 4, 5)]
    return _state(hp=29, deployed=deployed, bench=bench)


def test_rung_sampling_follows_settle_rung_coordinate() -> None:
    """两态分支 rung 取样必须走 _settle_rung(与 W346 表采样键同源):
    本夹具下若错用 _engines_formed(rung 1,p=0.65)→ ra=7;正确 settle
    坐标(rung 0,p=0.0)→ 条件常数 ra=3。"""
    st = _mixed_domain_state()
    # 夹具前提自证:两坐标确已分裂
    assert cw_sim._settle_rung(st) == 0
    assert _engines_formed(st, DEFAULT_REGISTRY) == 1
    reg = dataclasses.replace(
        DEFAULT_REGISTRY, rounds_two_state_enabled=True,
        p_win_p2_by_rung={0: 0.0, 1: 0.65, 2: 0.65})
    assert rounds_alive(st, _sess(), reg) == 3

