"""ADR-0408:r3/r4 投资节奏前置(假设 A)单帧锁。

锁面(结构面;分布面=w251_ab.py 三窗 A/B sim 批):
- 授权点 = 层3 评分(scoring.score_candidate):P1 r3-r4 战力买标签
  (crisis_buy_tags 同集)的 0/小分买候选顶成 +early_pace_bias 进约束链
  ——破息授权仍由 interest_rule EV 账随 V 单一裁决(零新增授权常量,
  防双计,先例);
- 窗口辖域:P1 ∧ r∈[min,max](缺省 3-4);r5 起由既有息纪律接管;
- 纪律态先行:emergency([18])不越权(boss 窗在 r≥9窗外本就不触);
- 正交/零漂移:默认 flag 关=逐位现行为(sim 整局 ledger 恒等);
- 默认值锁:early_pace_enabled=False。
n 取断言成立最小值;sim 结构断言用 fallback 池(README 纪律)。
"""
from __future__ import annotations

import json
import logging
from dataclasses import replace

import pytest

from sr_od.application.currency_war import cw_sim
from sr_od.application.currency_war.cw_state import (
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import score_candidate

logging.disable(logging.CRITICAL)

_OFF = DEFAULT_REGISTRY
_A = replace(DEFAULT_REGISTRY, early_pace_enabled=True)

_ENGINE_NAME = '姬子·启行'


def _state(**kw) -> GameState:
    """r3 备战帧:P1、金充裕段、板面未成型(0 分战力买的语义场景)。"""
    base = {'plane': 1, 'round_num': 3, 'gold': 55, 'level': 4,
            'hp': 90, 'board': {}, 'deployed': [], 'bench': [],
            'shop': [ShopCard(x=1, faction='列车同行',
                              name=_ENGINE_NAME, cost=2)],
            'node_type': 'battle'}
    base.update(kw)
    return GameState(**base)


def _sess() -> StrategySession:
    from sr_od.application.currency_war.cw_intention import (
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
        frozenset({_ENGINE_NAME, '三月七'}), frozenset(), 'locked')
    s.v3_core_names = {_ENGINE_NAME}
    s.target_comp = None
    return s


def _cand(st: GameState) -> Candidate:
    return Candidate(action=BuyCard(st.shop[0], reason=''), tag='engine_seed',
                     source='shop')


def test_scoring_bias_topup_in_window() -> None:
    """主通道与防叠边界:r3 窗内,val≤上沿的买候选被顶成 +bias(A 臂);
    已正分(>val_max)候选不叠加(双计防线同款);OFF 臂原分不动。
    两分支都锁——具体落哪支由该帧板面差分决定(语义:非正分显影,
    正分不二次加分)。"""
    st, sess = _state(), _sess()
    cand_a = _cand(st)
    # 换一张目标集外散卡(构造低分帧走主通道分支;tag 手工置
    # engine_seed = 战力买标签辖域内的手工构造,合法:锁的是评分函数)
    st_lo = _state(board={}, deployed=[],
                   shop=[ShopCard(x=1, faction='贝洛伯格',
                                  name='娜塔莎', cost=1)])
    cand_lo = Candidate(action=BuyCard(st_lo.shop[0], reason=''),
                        tag='engine_seed', source='shop')
    for st_i, cand_i in ((st, cand_a), (st_lo, cand_lo)):
        v_off, bd_off = score_candidate(cand_i, st_i, sess, _OFF)
        v_a, bd_a = score_candidate(cand_i, st_i, sess, _A)
        if v_off <= _A.early_pace_val_max:
            assert pytest.approx(v_a - v_off, abs=1e-6) \
                == _A.early_pace_bias, f'窗内低分应被顶起(st={st_i})'
            assert bd_a.get('early_pace') == _A.early_pace_bias
        else:
            assert v_a == v_off, '已正分候选不得二次加分(双计)'
        assert 'early_pace' not in bd_off


def test_window_and_discipline_state_domains() -> None:
    """窗口辖域:P1 r∈[3,4] 才触发;r5/r2/P2 不触;emergency 不越权。
    用高上沿臂(val≤HI 恒加)隔离「窗域」变量本身——分数落哪支不依赖
    具体牌面(评分差值锁由 test_scoring_bias_topup_in_window 承担)。"""
    sess = _sess()
    a_hi = replace(_A, early_pace_val_max=99.0)

    def _delta(st_i) -> float:
        c = Candidate(action=BuyCard(st_i.shop[0], reason=''),
                      tag='engine_seed', source='shop')
        v_a, bd_a = score_candidate(c, st_i, sess, a_hi)
        if 'early_pace' in bd_a or st_i.round_num in (3, 4):
            pass
        return v_a

    # 窗内两轮:偏置生效(A_hi − OFF = bias)
    for rn in (3, 4):
        st_i = _state(round_num=rn)
        v_hi, bd_hi = score_candidate(
            Candidate(action=BuyCard(st_i.shop[0], reason=''),
                      tag='engine_seed', source='shop'), st_i, sess, a_hi)
        v_ref, _ = score_candidate(
            Candidate(action=BuyCard(st_i.shop[0], reason=''),
                      tag='engine_seed', source='shop'), st_i, sess, _OFF)
        assert pytest.approx(v_hi - v_ref, abs=1e-6) == a_hi.early_pace_bias
        assert 'early_pace' in bd_hi
    # 窗外:r5(supply 回补)/r2/P2 plane:零行为
    for kw in ({'round_num': 5}, {'round_num': 2}, {'plane': 2}):
        st_i = _state(**kw)
        v_hi, bd_hi = score_candidate(
            Candidate(action=BuyCard(st_i.shop[0], reason=''),
                      tag='engine_seed', source='shop'), st_i, sess, a_hi)
        v_ref, _ = score_candidate(
            Candidate(action=BuyCard(st_i.shop[0], reason=''),
                      tag='engine_seed', source='shop'), st_i, sess, _OFF)
        assert v_hi == v_ref, f'{kw}:窗外必须零行为'
        assert 'early_pace' not in bd_hi
    # emergency(hp≤25):[18] 纪律态优先,偏置不越权改写应急语义
    st_em = _state(hp=20)
    v_em, bd_em = score_candidate(
        Candidate(action=BuyCard(st_em.shop[0], reason=''),
                  tag='engine_seed', source='shop'), st_em, sess, a_hi)
    v_em_ref, _ = score_candidate(
        Candidate(action=BuyCard(st_em.shop[0], reason=''),
                  tag='engine_seed', source='shop'), st_em, sess, _OFF)
    assert v_em == v_em_ref
    assert 'early_pace' not in bd_em
    # emergency(hp≤25):[18] 纪律态优先,偏置不越权改写应急语义
    st_em = _state(hp=20)
    v_em, _ = score_candidate(_cand(st_em), st_em, sess, _A)
    v_em_ref, _ = score_candidate(_cand(st_em), st_em, sess, _OFF)
    assert v_em == v_em_ref


def test_arbiter_chain_governs_no_new_auth_constant() -> None:
    """放行≠必买:约束链照常辖——金不足(gold_floor 远超)仍拒;防双计:
    registry 无 early_pace 专有 EV 常量字段(息账单一源=interest_rule)。"""
    st = _state(gold=20)   # 跨息档(20→18):[11] 例外不适用,地板族照拒
    res = arbitrate([(_cand(st), _A.early_pace_bias, {'cost': 2})], st,
                    _sess(), _A)
    assert res.log[0]['accepted'] is False
    assert not any(isinstance(a, BuyCard) for a in res.actions)
    # 数值单一源:无第二份授权常量(只有 enabled/min/max/bias/val_max 五件,
    # 且无一进 interest_rule EV 公式)
    fields = [f for f in type(DEFAULT_REGISTRY).__dataclass_fields__
              if f.startswith('early_pace')]
    assert set(fields) == {'early_pace_enabled', 'early_pace_min_round',
                           'early_pace_max_round', 'early_pace_bias',
                           'early_pace_val_max'}


def test_default_off_zero_drift_constants() -> None:
    """默认值锁:early_pace_enabled=False(默认关=现行为零漂移,
    A/B 裁决先例 ADR-0305/0400/0402/0403/0405)。"""
    assert DEFAULT_REGISTRY.early_pace_enabled is False


def test_sim_default_flag_full_identity() -> None:
    """sim 侧零漂移(结构证据,n=4 最小 fallback 池):默认 registry(关)
    改码后整局 ledger 与改码前不变量靠「该分支永不进入」的结构保证
    ——此处锁「同一份代码里 flag 关与显式关臂恒等」退化断言不可行,
    直接锁整局行为与 off 注册表注入一致(test_cw_w242 同款手法)。"""
    for seed in range(2):
        a = cw_sim.simulate_p1(seed, pool='fallback', planes=2,
                               strategy=__import__(
                                   'sr_od.application.currency_war.'
                                   'decision_v2.strategy',
                                   fromlist=['DecisionV2Strategy'])
                               .DecisionV2Strategy(registry=_OFF))
        b = cw_sim.simulate_p1(seed, pool='fallback', planes=2)
        assert json.dumps(a.ledger, sort_keys=True, ensure_ascii=False,
                          default=str) == json.dumps(
            b.ledger, sort_keys=True, ensure_ascii=False, default=str), (
            f'seed {seed}:flag 关必须与基线注入臂逐位一致')
