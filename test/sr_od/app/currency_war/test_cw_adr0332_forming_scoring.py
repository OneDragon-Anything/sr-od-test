"""ADR-0332 成型评分活性锁(d2 评分批;P1 boss 转化)。

锁定对象(decision_v2/scoring.py):
① 息崖平滑(war 破息窗):P1 r≥5 非应急买入跌破 50 满息平台时,息损
   修正为真实档位损失(-5),不再扣全平台消失(-25)——消除与层4
   boss_breaker 地板(10)授权的双重计罚;emergency(-25,[18])与
   经济态(r<5,-25,[17])保持;
② 成型补充偏置:未成型(引擎<2)+ 引擎件候选在破息窗的 0/小负分买入
   顶成正分(forming_bias,加性);成型后(引擎≥2)偏置关闭([13] 成型
   即停手);emergency 不顶([18] 深负分禁域);
③ 常量锁:forming_bias / forming_bias_val_max。
决策见 docs/develop/currency_war/decisions/0332-forming-scoring-activity.md。
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

from sr_od.application.currency_war.cw_state import BenchChar, GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    _cand_is_engine_piece,
    score_candidate,
)

_REG = DEFAULT_REGISTRY


def _card(name: str, faction: str = '仙舟', cost: int = 1) -> object:
    return SimpleNamespace(name=name, faction=faction, cost=cost,
                           x=0, star=1)


def _bench(name: str, faction: str = '公司',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _sess() -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 7, 'gold': 55, 'level': 6, 'hp': 80,
            'board': {'公司': 6},
            'deployed': [_bench(f'板件{i}', faction='公司', slot=i)
                         for i in range(6)],
            'bench': [], 'shop': [], 'hp': 80}
    base.update(kw)
    return GameState(**base)


def _buy_cand(st: GameState, name: str):
    """层1 真链生成指定买候选(取首个;无则断言失败)。"""
    cands = [c for c in generate_candidates(st, _sess(), _REG)
             if c.action.__class__.__name__ == 'BuyCard'
             and c.action.card.name == name]
    assert cands, f'店件 {name} 应生成买候选'
    return cands[0]


# --- ① 息崖平滑(war 破息窗) ------------------------------------------------


def test_cliff_smooth_war_window_crossing() -> None:
    """war 窗(P1 r7 非应急)gold 52 买 3 费引擎件(52→49 破平台):
    息损平滑到真实档位(-5)+ 成型偏置 → 正分(修复前 -24.55 恒死)。"""
    st = _state(gold=52, shop=[_card('爻光', cost=3)])
    cand = _buy_cand(st, '爻光')
    val, bd = score_candidate(cand, st, _sess(), _REG)
    assert bd['base']['interest'] == 25.0, bd['base']
    assert bd['after']['interest'] == 0.0, bd['after']
    assert val > 0, f'war 窗破平台买应正分(平滑+偏置;实际 {val})'


def test_cliff_kept_in_emergency() -> None:
    """emergency(hp20)同场景:息崖 -25 保持([18] 不为苟住破息,
    ADR-0302 锁同族);偏置禁域(不顶深负)→ 恒负分。"""
    st = _state(gold=52, hp=20, shop=[_card('爻光', cost=3)])
    cand = _buy_cand(st, '爻光')
    val, _ = score_candidate(cand, st, _sess(), _REG)
    assert val < 0, f'emergency 破平台买应负分(息崖保持;实际 {val})'


def test_cliff_kept_in_economy_window() -> None:
    """经济态(r4 非破息窗)gold 52 买 3 费:不触发平滑/偏置 → 恒负分
    ([17] 满息平台,经济态破 50 不被授权)。"""
    st = _state(round_num=4, gold=52, shop=[_card('爻光', cost=3)])
    cand = _buy_cand(st, '爻光')
    val, _ = score_candidate(cand, st, _sess(), _REG)
    assert val < 0, f'经济态破平台买应负分(实际 {val})'


# --- ② 成型补充偏置 ----------------------------------------------------------


def test_forming_bias_additive() -> None:
    """未成型 + 引擎件跨 50 平台买入(平滑后小负):forming_bias 加性
    (on−off 差分恰=bias);偏置开时分正(可执行)——修复前 -24.55 恒死。"""
    st = _state(gold=52, shop=[_card('爻光', cost=3)])
    cand = _buy_cand(st, '爻光')
    assert _cand_is_engine_piece(cand), '爻光应为引擎件'
    reg_off = dataclasses.replace(_REG, forming_bias=0.0)
    v_off, _ = score_candidate(cand, st, _sess(), reg_off)
    v_on, _ = score_candidate(cand, st, _sess(), _REG)
    assert v_off < 0, f'前置:平滑后应小负(实际 {v_off})'
    assert v_on - v_off == _REG.forming_bias, (v_off, v_on)
    assert v_on > 0, '未成型+引擎件跨平台应可执行(>0)'


def test_forming_bias_off_when_formed() -> None:
    """成型后(引擎≥2,[13] 成型即停手):引擎件买入不顶偏置
    (on−off 差分=0)。"""
    st = _state(
        deployed=[_bench('爻光', faction='仙舟', slot=0),
                  _bench('藿藿', faction='仙舟', slot=1),
                  _bench('符玄', faction='仙舟', slot=2),
                  _bench('卡芙卡', faction='星核猎手', slot=3),
                  _bench('黑天鹅', faction='盛会之星', slot=4),
                  _bench('板件5', faction='公司', slot=5)],
        board={'仙舟': 3, '持续伤害': 2, '公司': 1},
        shop=[_card('停云')],   # 仙舟件(引擎件,但板面已成)
    )
    cand = _buy_cand(st, '停云')
    reg_off = dataclasses.replace(_REG, forming_bias=0.0)
    v_off, _ = score_candidate(cand, st, _sess(), reg_off)
    v_on, _ = score_candidate(cand, st, _sess(), _REG)
    assert v_on - v_off == 0.0, (v_off, v_on)


def test_forming_bias_not_on_already_positive() -> None:
    """已正分(>forming_bias_val_max)的引擎件买入不叠加偏置
    (防 ADR-0301「高单位挤掉目标件」过冲;只顶 0/小负)。"""
    # cap 有空位:买 爻光 部署成引擎 → 板面差分大正 → 出带上沿
    st = _state(
        deployed=[_bench('爻光', faction='仙舟', slot=0),
                  _bench('藿藿', faction='仙舟', slot=1),
                  _bench('板件2', faction='公司', slot=2),
                  _bench('板件3', faction='公司', slot=3),
                  _bench('板件4', faction='公司', slot=4)],
        board={'仙舟': 2, '公司': 3},
        shop=[_card('饮月')] if False else [_card('符玄')],
    )
    cand = _buy_cand(st, '符玄')
    reg_off = dataclasses.replace(_REG, forming_bias=0.0)
    v_off, _ = score_candidate(cand, st, _sess(), reg_off)
    v_on, _ = score_candidate(cand, st, _sess(), _REG)
    assert v_off > _REG.forming_bias_val_max, \
        f'场景前置:板面差分应出带上沿(实际 {v_off})'
    assert v_on - v_off == 0.0, (v_off, v_on)


def test_forming_bias_off_channel_constants() -> None:
    """常量锁:bias 默认开(5.0);顶分上沿 0.5。"""
    assert _REG.forming_bias == 5.0
    assert _REG.forming_bias_val_max == 0.5
