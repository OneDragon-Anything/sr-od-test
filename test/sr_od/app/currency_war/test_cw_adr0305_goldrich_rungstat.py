"""ADR-0305 锁(件3 金充裕买偏置 + 件2 rung 统计口径)。

锁定对象:
① 金充裕买偏置(scoring):金 ≥ goldrich_min_gold(28)的 0 分板面
   差分买候选(engine_seed/pair/copy/bridge_core)顶成 +bias——
   同板双态(gold 35 vs 20,均 <50 息不计值)差分恰 = bias
   (0302 crisis 偏置锁的同型加性锁);金 < 下沿不触发;bias=0
   关闭;息崖(52→49)负分不被翻越;
② rung 统计口径(cw_sim._battles_before_engines):首达 e2 前的
   战斗类结算计数(battle/encounter/boss,round < e2 轮),奖励
   不计;未达 e2 → None——0304「30 vs 10」未定义口径误读的防再犯。
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

from sr_od.application.currency_war.cw_sim import (
    _battles_before_engines,
    _first_engines_round,
)
from sr_od.application.currency_war.cw_state import BenchChar, GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    score_candidate,
)

_REG = DEFAULT_REGISTRY
#: 偏置开臂(显式 0.5;默认 0=三窗否决后回退关闭,通道保留)
_REG_ON = dataclasses.replace(DEFAULT_REGISTRY, goldrich_buy_bias=0.5)


def _card(name: str, faction: str = '公司', cost: int = 1) -> object:
    return SimpleNamespace(name=name, faction=faction, cost=cost,
                           x=0, star=1)


def _bench(name: str, faction: str = '仙舟',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _sess() -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 35, 'level': 6,
            'board': {'公司': 6},
            'deployed': [_bench(f'板件{i}', faction='公司', slot=i)
                         for i in range(6)],
            'bench': [], 'shop': [], 'hp': 40}
    base.update(kw)
    return GameState(**base)


def _buy_score(st: GameState, registry=_REG) -> float:
    """pair 凑数件(板面 公司 6 满档、cap 满、无进度余量——板面差分
    恒 0 的诊断指纹件)的买候选评分(层1 真链生成,tag=pair)。"""
    sess = _sess()
    cands = [c for c in generate_candidates(st, sess, registry)
             if c.action.__class__.__name__ == 'BuyCard']
    assert cands, 'pair 凑数件(同阵营已持有)应生成买候选'
    val, _ = score_candidate(cands[0], st, sess, registry)
    return val


# --- ① 金充裕买偏置 ----------------------------------------------------------


def test_goldrich_bias_default_off() -> None:
    """定谳待清锁:概念已被 A/B 否决(三窗 gap 无一致方向,成型加速
    可见但 hp 不跟;ADR-0305,ADR-0408 同族复证同构)——开关生命周期
    第 4 态待清,删除批=注册表三字段与 scoring 消费块同批;删除批前
    默认 bias 恒 0(行为零漂移)。与 ADR-0445 的边界:本偏置辖金
    28-50 储备段,溢余义务(g>R*)不吞并其辖域,清理依据是自身 A/B
    否决非义务覆盖。金下沿/辖标签常量随锁(28 / 四标签)。"""
    assert _REG.goldrich_buy_bias == 0.0
    assert _REG.goldrich_min_gold == 28
    assert _REG.goldrich_buy_tags == frozenset(
        {'engine_seed', 'pair', 'copy', 'bridge_core'})


def test_goldrich_bias_additive() -> None:
    """金 35 vs 20 同板差分恰 = goldrich_buy_bias(0 差分件双态唯一
    差异=偏置;两态均 <50 息 EV 同为 0);金充裕态分为正。"""
    v_rich = _buy_score(_state(gold=35, shop=[_card('金充裕测试件')]),
                        _REG_ON)
    v_lean = _buy_score(_state(gold=20, shop=[_card('金充裕测试件')]),
                        _REG_ON)
    assert v_lean == 0.0, f'基线应为 0 差分(实际 {v_lean})'
    assert v_rich - v_lean == _REG_ON.goldrich_buy_bias, (v_rich, v_lean)
    assert v_rich > 0, '金充裕段 0 分差分件应可执行(>0)'


def test_goldrich_gold_gate() -> None:
    """金下沿:gold ≥ goldrich_min_gold 触发,< 下沿不触发(差分 0)。"""
    v_edge = _buy_score(_state(gold=28, shop=[_card('金充裕测试件')]),
                        _REG_ON)
    v_below = _buy_score(_state(gold=27, shop=[_card('金充裕测试件')]),
                         _REG_ON)
    assert v_edge - v_below == _REG_ON.goldrich_buy_bias, (v_edge, v_below)


def test_goldrich_bias_off_channel() -> None:
    """bias=0 = 通道关闭(同板双金差分 0;A/B 关臂语义)。"""
    v_rich = _buy_score(_state(gold=35, shop=[_card('金充裕测试件')]), _REG)
    v_lean = _buy_score(_state(gold=20, shop=[_card('金充裕测试件')]), _REG)
    assert v_rich - v_lean == 0.0, (v_rich, v_lean)


def test_goldrich_bias_does_not_cross_interest_cliff() -> None:
    """息崖保持:金 52 买 3 费(52→49 跌破满息平台)恒负分,
    偏置只顶 0 分差分(val==0 守卫),不翻越负息崖。"""
    val = _buy_score(_state(gold=52, shop=[_card('金充裕测试件', cost=3)]),
                     _REG_ON)
    assert val < 0, f'息崖下金充裕买应负分(实际 {val})'


# --- ② rung 统计口径 ---------------------------------------------------------


def _fake_res() -> SimpleNamespace:
    """最小 ledger/hp_events 载体:r1 仙舟1 → r2 仙舟3 → r4 双体系。"""
    return SimpleNamespace(
        ledger=[
            {'round_num': 1,
             'state': {'board_factions': {'仙舟': 1}, 'deployed': []}},
            {'round_num': 2,
             'state': {'board_factions': {'仙舟': 3}, 'deployed': []}},
            {'round_num': 3,
             'state': {'board_factions': {'仙舟': 3}, 'deployed': []}},
            {'round_num': 4, 'state': {
                'board_factions': {'仙舟': 3, '列车同行': 2},
                'deployed': []}},
        ],
        hp_events=[
            (1, 'battle', -5, False),
            (2, 'reward', 2, False),
            (3, 'encounter', -4, False),
            (4, 'boss', -8, False),
        ],
    )


def test_battles_before_e2_metric_semantics() -> None:
    """e2 首达 r4(仙舟3+列车2):此前战斗类 = r1 battle + r3 encounter
    = 2(r2 reward 不计;r4 当轮不计,< 严格)。"""
    res = _fake_res()
    assert _first_engines_round(res, 2) == 4
    assert _battles_before_engines(res, 2) == 2


def test_battles_before_e2_none_when_never() -> None:
    """未达 e2 → None(与 _first_engines_round 同 None 语义;
    批报告均值只对达成局算)。"""
    res = _fake_res()
    assert _first_engines_round(res, 3) is None
    assert _battles_before_engines(res, 3) is None
