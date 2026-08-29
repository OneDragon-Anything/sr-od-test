"""W436/ADR-0438:非正分门 merge 完成豁免单帧锁。

背景(W431 定位):第三张副本买候选(买入即合成 2★,merge=True)的
价值在星级阶梯不在板面差分,评分维对它构造性零增量 → 被 arbiter
非正分门结构性拒(74 笔主病灶)。修法=registry.merge_completion_exempt
开关(默认关=零漂移锚)开时豁免放行进入约束链——与 'copy' 标签
C 豁免(W242/ADR-0405 C 项)同为「完成素材放行」语义对称。

锁面:
- 开关开(生产默认,ADR-0438 开臂):merge 买候选非正分放行进约束链,
  且无条件于末窗 gap(完成价值全程存在,与 C 豁免的定向授权辖域区分);
- 回退态(显式关):merge 买候选非正分照拒(W431 病灶历史行为,
  代码留作回退通道);
- 豁免≠必买:金地板照拒(约束链不豁免);
- 定向性:非 merge 候选不豁免;synthesize 候选(merge=True 但非
  BuyCard)不辖,防语义外溢。
n 取断言成立最小值。
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision_v2.candidates import (
    Candidate,
    Synthesize,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)

logging.disable(logging.CRITICAL)

_FILLER = '娜塔莎'
_FAC = '贝洛伯格'


def _sess() -> StrategySession:
    from sr_od.application.currency_war.kernel.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {'姬子·启行'}
    s.target_comp = SimpleNamespace(factions=('列车同行',),
                                    core_chars=('姬子·启行',))
    return s


def _deployed(name: str, faction: str, star: int = 1,
              slot: int = 0) -> SimpleNamespace:
    return SimpleNamespace(char_id=name, faction=faction, star=star,
                           position_pref='back', equips=(), slot=slot)


def _state(**kw) -> GameState:
    """差一张凑 2★ 帧:P1 r5(非末窗,gap=0——豁免无条件于 gap 的
    证明帧)。"""
    base = {'plane': 1, 'round_num': 5, 'gold': 55, 'level': 5,
            'hp': 60,
            'board': {'列车同行': 1, _FAC: 1},
            'deployed': [_deployed('姬子·启行', '列车同行'),
                         _deployed(_FILLER, _FAC)],
            'bench': [], 'shop': [], 'node_type': 'battle'}
    base.update(kw)
    return GameState(**base)


def _merge_cand(cost: int = 3) -> Candidate:
    """第三张副本买候选(merge=True;tag= W431 实测主病灶人群
    line_opportunistic,非 'copy'——C 豁免不辖该人群)。"""
    return Candidate(action=BuyCard(
        ShopCard(x=1, faction=_FAC, name=_FILLER, cost=cost), reason=''),
        tag='line_opportunistic', source='shop', merge=True)


_REG_ON = DecisionV2Registry(merge_completion_exempt=True)
_REG_OFF = DecisionV2Registry(merge_completion_exempt=False)


def test_default_on_and_off_fallback_rejects() -> None:
    """生产默认=开(ADR-0438 开臂);显式关=回退非正分拒(W431
    病灶历史行为,回退通道保持可用)。"""
    assert DEFAULT_REGISTRY.merge_completion_exempt is True
    st = _state()
    res = arbitrate([(_merge_cand(), 0.0, {'cost': 3})], st, _sess(),
                    _REG_OFF)
    assert res.log[0]['reject'] == '非正分'
    assert not any(isinstance(a, BuyCard) for a in res.actions)


def test_merge_exempt_passes_gate_gap_independent() -> None:
    """主通道:开关开时非正分 merge 买候选放行进约束链并采纳;r5
    非末窗(gap=0)即放行——完成素材豁免无条件于定向授权窗。"""
    st = _state()
    res = arbitrate([(_merge_cand(), 0.0, {'cost': 3})], st, _sess(),
                    _REG_ON)
    assert res.log[0]['accepted'] is True, f'log={res.log[0]}'
    assert any(isinstance(a, BuyCard) for a in res.actions)


def test_exempt_not_must_buy_gold_floor_governs() -> None:
    """豁免≠必买:低金帧(金 < 地板)放行后 gold_floor 照拒——
    豁免只跳过非正分门,约束链不豁免。"""
    st = _state(gold=20)   # HOARD 段:跨息档买(20→17 破 2 档)攒息拒
    res = arbitrate([(_merge_cand(), 0.0, {'cost': 3})], st, _sess(),
                    _REG_ON)
    assert res.log[0]['accepted'] is False
    assert not any(isinstance(a, BuyCard) for a in res.actions)


def test_non_merge_and_synthesize_not_exempted() -> None:
    """定向性:非 merge 候选不豁免;synthesize 候选虽 merge=True 但
    非 BuyCard,不辖(防语义外溢)。"""
    st = _state()
    sess = _sess()
    plain = Candidate(action=BuyCard(
        ShopCard(x=1, faction=_FAC, name='三月七', cost=3), reason=''),
        tag='line_opportunistic', source='shop', merge=False)
    res = arbitrate([(plain, 0.0, {'cost': 3})], st, sess, _REG_ON)
    assert res.log[0]['reject'] == '非正分'
    syn = Candidate(action=Synthesize(name=_FILLER, star=1, copies=3),
                    tag='synthesize', source='merge_pool', merge=True)
    res_syn = arbitrate([(syn, 0.0, {'cost': 0})], st, sess, _REG_ON)
    assert res_syn.log[0]['reject'] == '非正分'
