# -*- coding: utf-8 -*-
"""P2 生存批单帧锁:C3 濒死带期望账 + C4 换线存活轮数门。

设计=`.debug/temp/currency_war/w353_p2_survival/DESIGN.md` §2 C3/C4、
§3 辖域表、§5 第一批。锁的是策略决策行为(单帧锁=回归工具):

- C3 濒死带(registry.dying_band_account_enabled,默认关=零漂移):
  应急深带内「再输一场即死」帧的支出授权收窄——非目标件买/盲刷/
  LevelUp 滤出,目标件买/定向刷新放行,卖/上阵不辖;四边界
  (开关/hp_readable 守卫/plane≥2/嵌套应急触发线)逐项;与 release
  辖区(hp>emergency_hp)零交集由「嵌套 is_emergency」结构保证。
- C4 存活轮数门(registry.line_switch_survival_gate_enabled,默认关):
  rounds_alive=ceil(hp/三档等权均值) ≥ E_rounds(新线)+余量;边界
  (开关/plane≥2/inf 豁免)与三档谱查表行为;与 should_switch_e 的
  串联语义(纯函数组合锁,drought bail 旁路不在本判据辖域)。
"""
from __future__ import annotations

import dataclasses
import math
from types import SimpleNamespace

from sr_od.application.currency_war.cw_state import (
    BuyCard,
    DeployMove,
    GameState,
    LevelUp,
    RefreshShop,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.cw_line_switch import (
    rounds_alive,
    should_switch_e,
    survival_gate,
)
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.filters import (
    dying_band_active,
    filter_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.cw_system_cards import engine_char_names

_REG_DYING = dataclasses.replace(DEFAULT_REGISTRY,
                                 dying_band_account_enabled=True)
_REG_GATE = dataclasses.replace(DEFAULT_REGISTRY,
                                line_switch_survival_gate_enabled=True)


def _card(name: str, cost: int = 1) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


def _dying_state(**kw) -> GameState:
    """濒死帧:P2 r3、应急深带内(hp=20 ≤ normal 档 20.05)、hp 可读。"""
    base = {
        'plane': 2, 'round_num': 3, 'gold': 30, 'level': 5,
        'hp': 20, 'hp_readable': True,
        'board': {}, 'deployed': [], 'bench': [], 'shop': [],
    }
    base.update(kw)
    return GameState(**base)


def _cands(target: str, other: str = '散件甲') -> list[Candidate]:
    """五类候选各一:目标件买/非目标件买/等级买/刷新/卖+上阵。"""
    return [
        Candidate(action=BuyCard(_card(target), reason=''), tag='line_carry',
                  source='shop'),
        Candidate(action=BuyCard(_card(other), reason=''), tag='plugin',
                  source='shop'),
        Candidate(action=LevelUp(cost=4), tag='levelup', source='xp'),
        Candidate(action=RefreshShop(cost=2), tag='refresh', source='shop'),
        Candidate(action=SellBench(bench_idx=0, income=1, expect=''),
                  tag='for_gold', source='bench'),
        Candidate(action=DeployMove(bench_idx=1, to_row='front',
                                    faction='仙舟罗浮'),
                  tag='deploy', source='fence'),
    ]


# --- C3:濒死带判据边界 -----------------------------------------------------


def test_dying_band_default_off() -> None:
    """默认关=零漂移:registry 缺省下濒死判据恒 False。"""
    assert not dying_band_active(_dying_state(), StrategySession(),
                                 DEFAULT_REGISTRY)


def test_dying_band_hp_readable_guard() -> None:
    """hp_readable=False(置信 0 帧,hp 是沿用值)假帧不评估。"""
    st = _dying_state(hp_readable=False, hp=1)
    assert not dying_band_active(st, StrategySession(), _REG_DYING)


def test_dying_band_plane_scope() -> None:
    """辖域 plane≥2:P1 濒死帧不辖(批辖域声明)。"""
    st = _dying_state(plane=1, round_num=7)
    assert not dying_band_active(st, StrategySession(), _REG_DYING)


def test_dying_band_nested_in_emergency() -> None:
    """触发线嵌套:hp>emergency_hp 恒 False——濒死带不新增覆盖态触发线,
    与 release FLIP 辖区(hp>25)零交集(结构互斥)。"""
    st = _dying_state(hp=DEFAULT_REGISTRY.emergency_hp + 1)
    assert not dying_band_active(st, StrategySession(), _REG_DYING)


def test_dying_band_threshold_boundary() -> None:
    """边界:hp ≤ 下一战期望损血(缺读节点→normal 档)即濒死;
    hp=20 ≤ 20.05 命中,hp=emergency_hp(25)>20.05 不命中。"""
    sess = StrategySession()
    assert dying_band_active(_dying_state(hp=20), sess, _REG_DYING)
    assert not dying_band_active(_dying_state(hp=25), sess, _REG_DYING)


def test_dying_band_boss_bucket_lookup() -> None:
    """三档谱查表:同一 hp=25(应急带内),boss 节点走 boss 档(≤26.71)
    濒死;normal 节点(>20.05)不濒死——档位查表生效。"""
    sess_boss = StrategySession()
    sess_boss.node_type_current = 'boss'
    sess_norm = StrategySession()
    assert dying_band_active(_dying_state(hp=25), sess_boss, _REG_DYING)
    assert not dying_band_active(_dying_state(hp=25), sess_norm, _REG_DYING)


# --- C3:支出授权收窄(链行为) ----------------------------------------------


def _target_name() -> str:
    """高确信目标件名(裸 session 目标集=引擎件全集,单一源回退语义)。"""
    return sorted(engine_char_names())[0]


def test_dying_band_narrows_spend_keeps_sell_deploy() -> None:
    """濒死帧收窄:非目标件买/盲刷/LevelUp 滤出;目标件买/卖/上阵放行。
    (金 30<40 危机囤金线,基线应急态 refresh 本就滤出。)"""
    tgt = _target_name()
    st = _dying_state()
    sess = StrategySession()
    kept, flog = filter_candidates(_cands(tgt), st, sess, _REG_DYING)
    tags = {c.tag for c in kept}
    actions = {id(c.action) for c in kept}
    assert any(isinstance(c.action, BuyCard) and c.action.card.name == tgt
               for c in kept), '目标件买必须放行'
    assert 'levelup' not in tags and 'refresh' not in tags
    assert not any(isinstance(c.action, BuyCard)
                   and c.action.card.name != tgt for c in kept)
    assert {'for_gold', 'deploy'} <= tags   # 卖(变现)/部署非支出,不辖
    # 金 30<40:refresh 被应急标签集滤出(基线行为),未到濒死收窄记账;
    # 濒死收窄的记账只对过了 allowed 的候选(此帧=非目标件买)
    drops = {e['tag']: e.get('dying_band', '') for e in flog if not e['kept']}
    assert drops.get('plugin') == 'nontarget_buy'
    nontarget_drop = [e for e in flog if e['tag'] == 'plugin']
    assert nontarget_drop and not nontarget_drop[0]['kept']
    assert actions   # kept 非空(目标件/卖/上阵)


def test_dying_band_directed_refresh_only_with_target_in_shop() -> None:
    """定向刷新:金 ≥40(危机囤金线开 refresh)时,店有目标件→放行;
    店无目标件→仍滤出(只授权「定向」刷新,不盲刷)。"""
    tgt = _target_name()
    sess = StrategySession()
    st_with = _dying_state(gold=45, shop=[_card(tgt)])
    kept, _ = filter_candidates(_cands(tgt), st_with, sess, _REG_DYING)
    assert any(isinstance(c.action, RefreshShop) for c in kept)
    st_without = _dying_state(gold=45, shop=[_card('无关件乙')])
    kept2, _ = filter_candidates(_cands(tgt), st_without, sess, _REG_DYING)
    assert not any(isinstance(c.action, RefreshShop) for c in kept2)


def test_dying_band_off_zero_drift() -> None:
    """零漂移锚:同帧开关关 → 与 DEFAULT_REGISTRY 逐位一致(非目标件买
    放行——应急标签集行为不变)。"""
    tgt = _target_name()
    st = _dying_state()
    sess = StrategySession()
    kept_off, _ = filter_candidates(_cands(tgt), st, sess, DEFAULT_REGISTRY)
    assert any(isinstance(c.action, BuyCard)
               and c.action.card.name != tgt for c in kept_off)


# --- C4:存活轮数门 ----------------------------------------------------------


def test_rounds_alive_lookup_table() -> None:
    """三档谱查表底座:rounds_alive=ceil(hp/等权均值)。默认表三档正值,
    均值≈21.14 → hp=50 → 3;hp=0 → 0。"""
    reg = DEFAULT_REGISTRY
    vals = [v for v in reg.line_switch_round_loss.values() if v > 0]
    assert len(vals) == 3, '三档(普通/遭遇/boss)粗谱必须齐备'
    mean = sum(vals) / len(vals)
    assert rounds_alive(_dying_state(hp=50), reg) == int(-(-50 // mean))
    assert rounds_alive(_dying_state(hp=0), reg) == 0


def test_survival_gate_default_off_and_scope() -> None:
    """开关关/plane<2/新线 inf → 放行(零漂移;inf 已被 should_switch_e
    的 alt_inf 拦,门不重复裁决)。"""
    sess = StrategySession()
    assert survival_gate(_dying_state(), sess, 3.0,
                         DEFAULT_REGISTRY) == (True, 'gate_off')
    st_p1 = _dying_state(plane=1)
    assert survival_gate(st_p1, sess, 99.0, _REG_GATE) == (True, 'gate_off')
    st_inf = _dying_state(hp=100)
    assert survival_gate(st_inf, sess, math.inf, _REG_GATE) == (True,
                                                                'gate_off')


def test_survival_gate_boundary() -> None:
    """门边界:rounds_alive ≥ E(新线)+余量放行,不足拦。
    hp=50 → ra=3;余量 1:E=1.5 → 需 2.5 放行;E=2.5 → 需 3.5 拦
    (边界取拦侧——估计量方差大的保守方向,设计 §2 C4「门取保守值」)。"""
    sess = StrategySession()
    st = _dying_state(hp=50)
    ok, why = survival_gate(st, sess, 1.5, _REG_GATE)
    assert ok and why == 'ok'
    ok, why = survival_gate(st, sess, 2.5, _REG_GATE)
    assert not ok and why.startswith('survival(')


def test_survival_gate_serial_after_e_rounds() -> None:
    """串联语义:第三道门——should_switch_e 判 ok 后门仍可拦;与 θ/δ/D_min
    同族(纯函数组合;消费点=default_strategy 换线采纳前)。"""
    sess = StrategySession()
    st = _dying_state(hp=50)
    do, _ = should_switch_e(4.54, 3.0, 2, DEFAULT_REGISTRY)
    assert do, '夹具前提:E_rounds 主判据放行'
    ok, _ = survival_gate(st, sess, 5.0, _REG_GATE)
    assert not ok, '存活轮数不足时串联门必须拦(堵转进死线)'
