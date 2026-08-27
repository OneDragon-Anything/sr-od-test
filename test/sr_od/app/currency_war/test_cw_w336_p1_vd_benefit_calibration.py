# -*- coding: utf-8 -*-
"""W336/ADR-0425 P1 段 V_D 收益侧骨架值治理单帧锁。

外部审计缺口:vd_refresh_score 的 P1 收益侧战斗项用骨架值
(expected_battle_loss=10 × battles_left_est=5,双双自标「未标定」),
而 P12 修法只给了 P2 侧——P1 的战斗数本可用 plane_node_table 同法
推导。本批(ADR-0425,math_proofs P15):
- 战斗数:P1/P2 统一走 ev.battles_left_plane(槽序表逐轮推导,
  机制确定性,P15 检验点①);
- 掉血:条件败局伤害遥测拟合(p1_battle_loss_est,W324 语料 battle
  两态拟合,P15 检验点②;registry 注入 vd_p1_loss_intercept/slope)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 掉血拟合阶梯:loss(r)=11.32−0.37r(rung 域钳制 0-3)+registry
  注入改值生效;
- ② P1 战斗数槽序表推导:中文词表(普通战斗/遭遇/boss 计战斗,
  奖励/补给排除)逐轮切片;表缺退骨架缺省;旧名别名同一函数;
- ③ P1 core 通道收益:同帧注入槽序表 vs 无表,分值差=dwin×loss(2)
  ×hp_to_gold×Δbattles 逐位;
- ④ engine_jump_gold 同式:session 表推导进战斗数(缺省 None=骨架
  兜底,行为与 W131 锁①兼容);
- ⑤ 授权带变化方向:同一 P1 帧,新口径战斗项相对骨架值的方向由
  剩余战斗数与成型档决定——前中段(r2)抬升、末窗(r5/r8)收紧
  (骨架 5 系统性高估末窗剩余战斗)。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_intention import IntentionState
from sr_od.application.currency_war.cw_state import BenchChar, GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.ev import (
    battles_left_p2,
    battles_left_plane,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    engine_jump_gold,
    p1_battle_loss_est,
    vd_refresh_score,
)

_REG = DEFAULT_REGISTRY

#: P1 众数节点模板(cw_node_validate.P1_NODE_TEMPLATE 同源词表;
#: 槽 0-8 = r1-r9,战斗槽 = r3/r4/r6/r7/r9)
_P1_TABLE = ['奖励', '奖励', '普通战斗', '普通战斗', '补给',
             '普通战斗', '遭遇', '奖励', 'boss']


def _locked_sess(table: list[str] | None = None) -> StrategySession:
    s = StrategySession()
    s.v3_intention = IntentionState(phase='locked', locked_comp='DOT队')
    s.target_comp = get_comp('DOT队')
    s.v3_mode = 'economy'
    if table is not None:
        s.plane_node_table = list(table)
    return s


def _p1_state(r: int, gold: int = 100,
              bench: list[BenchChar] | None = None) -> GameState:
    return GameState(
        plane=1, round_num=r, gold=gold, level=8, hp=80,
        shop_refresh_cost=2,
        deployed=[BenchChar(slot=9 + i, char_id=f'杂件{i}',
                            faction='公司', star=1)
                  for i in range(4)],
        bench=bench or [BenchChar(slot=0, char_id='卡芙卡',
                                  faction='盛会之星', star=1),
                        BenchChar(slot=1, char_id='卡芙卡',
                                  faction='盛会之星', star=1)],
        shop=[], node_type='battle')


# --- ① 掉血拟合阶梯 -------------------------------------------------------------


def test_p1_loss_fit_ladder() -> None:
    """①loss(r)=11.32−0.37r:rung0-3 阶梯值;域钳制(rung=-1→0,
    rung=9→3);registry 注入改值生效(常量单一源在 registry)。"""
    st = _p1_state(5)
    assert abs(p1_battle_loss_est(st, _REG, rung=0) - 11.32) < 1e-9
    assert abs(p1_battle_loss_est(st, _REG, rung=1) - 10.95) < 1e-9
    assert abs(p1_battle_loss_est(st, _REG, rung=2) - 10.58) < 1e-9
    assert abs(p1_battle_loss_est(st, _REG, rung=3) - 10.21) < 1e-9
    assert abs(p1_battle_loss_est(st, _REG, rung=-1) - 11.32) < 1e-9
    assert abs(p1_battle_loss_est(st, _REG, rung=9) - 10.21) < 1e-9
    reg2 = dataclasses.replace(_REG, vd_p1_loss_intercept=12.0,
                               vd_p1_loss_slope_rung=-1.0)
    assert p1_battle_loss_est(st, reg2, rung=2) == 10.0
    # 缺省 rung=state 当前成型档(空体系板=0)
    assert abs(p1_battle_loss_est(st, _REG) - 11.32) < 1e-9


# --- ② P1 战斗数槽序表推导 -------------------------------------------------------


def test_p1_battles_left_from_table() -> None:
    """②P1 槽序表推导(P1/P2 同法):中文词表,奖励/补给排除;
    逐轮切片;表缺/裸 session → 骨架缺省;旧名 battles_left_p2 与
    battles_left_plane 同一函数(别名兼容)。"""
    st = _p1_state(5)
    s = _locked_sess(_P1_TABLE)
    # r5 起:补给,普通战斗,遭遇,奖励,boss → 3 场战斗
    assert battles_left_plane(st, s, _REG) == 3.0
    st2 = _p1_state(2)
    # r2 起:奖励,普通战斗,普通战斗,补给,普通战斗,遭遇,奖励,boss → 5
    assert battles_left_plane(st2, s, _REG) == 5.0
    st8 = _p1_state(8)
    # r8 起:奖励,boss → 1
    assert battles_left_plane(st8, s, _REG) == 1.0
    # 表缺/裸 session → registry 骨架缺省
    assert battles_left_plane(st, _locked_sess(), _REG) \
        == _REG.battles_left_est
    # 旧名别名(W154 消费点兼容)
    assert battles_left_p2 is battles_left_plane


# --- ③ P1 core 通道收益:表推导进分值 --------------------------------------------


def test_p1_core_vd_benefit_uses_table() -> None:
    """③同帧(lv8 roll 窗 core 通道)注入槽序表 vs 无表:
    分值差 = dwin(1→2)×loss(rung2)×hp_to_gold×Δbattles 逐位对拍
    (r6 剩余战斗 3 vs 缺省 5)。"""
    st = _p1_state(6, bench=[BenchChar(slot=0, char_id='卡芙卡',
                                       faction='盛会之星', star=1),
                             BenchChar(slot=1, char_id='卡芙卡',
                                       faction='盛会之星', star=1)])
    vd_tab = vd_refresh_score(st, _locked_sess(_P1_TABLE), _REG)
    vd_def = vd_refresh_score(st, _locked_sess(), _REG)
    assert vd_tab is not None and vd_def is not None
    dwin = _REG.h3_win_rate[2] - _REG.h3_win_rate[1]
    expected_diff = (dwin * p1_battle_loss_est(st, _REG, rung=2)
                     * _REG.hp_to_gold * (3 - 5))
    assert abs((vd_tab - vd_def) - expected_diff) < 1e-6, \
        (vd_tab, vd_def, expected_diff)


# --- ④ engine_jump_gold 战斗数透传 ----------------------------------------------


def test_engine_jump_gold_session_passthrough() -> None:
    """④jump(0) 带 session 槽序表 vs session=None:差=dwin(0→1)
    ×loss(rung1)×hp_to_gold×Δbattles(r5 帧剩余 3 vs 缺省 5);
    None 行为=骨架兜底(W131 锁①语义兼容)。"""
    st = _p1_state(5)
    dwin01 = _REG.h3_win_rate[1] - _REG.h3_win_rate[0]
    unit = dwin01 * p1_battle_loss_est(st, _REG, rung=1) * _REG.hp_to_gold
    diff = engine_jump_gold(0, st, _REG, _locked_sess(_P1_TABLE)) \
        - engine_jump_gold(0, st, _REG)
    assert abs(diff - unit * (3 - 5)) < 1e-6, diff


# --- ⑤ 授权带变化方向(效果声明的事前锚)------------------------------------------


def test_p1_authorization_band_direction() -> None:
    """⑤相对骨架值(expected_battle_loss=10×battles_left_est=5)的
    战斗项变化方向:前中段(r2,剩余 5 场+拟合档值 10.58/10.95>10)
    抬升;末窗(r5/r8,骨架 5 系统性高估剩余战斗)收紧——方向由
    剩余战斗数与成型档共同决定,不再是无信息常数。"""
    def win_term(r: int, rung: int) -> tuple[float, float]:
        st = _p1_state(r)
        dwin = _REG.h3_win_rate[rung] - _REG.h3_win_rate[rung - 1]
        new = (dwin * p1_battle_loss_est(st, _REG, rung=rung)
               * _REG.hp_to_gold
               * battles_left_plane(st, _locked_sess(_P1_TABLE), _REG))
        old = dwin * _REG.expected_battle_loss * _REG.hp_to_gold \
            * _REG.battles_left_est
        return new, old

    new2, old = win_term(2, 2)
    assert new2 > old, (new2, old)          # 前中段:抬升
    new5, _ = win_term(5, 2)
    assert new5 < old, (new5, old)          # 末窗:收紧
    new8, _ = win_term(8, 2)
    assert new8 < old, (new8, old)
