# -*- coding: utf-8 -*-
"""ADR-0293 标定批回归锁:标定参数快照 + 刷新双门 + 弱件换金偏置。

- 快照锁:标定五参(refresh_ev/refresh_max_round/refresh_min_gold/
  target_hold_base/off_target_sell_bias)逐值锁死 + registry 全字段
  hash 锁(任何漂移——包括未列字段——即红,防静默改参)。
- 行为锁:刷新轮界门(r>max 恒负分)/金保底门(金<min 不刷)/
  溢出件卖出偏置(0 分卖翻正)。
决策见 docs/develop/currency_war/decisions/0293-decision-v2-calibration.md。
"""
from __future__ import annotations

import hashlib
import json

from types import SimpleNamespace

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    RefreshShop,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    score_candidate,
)
from sr_od.application.currency_war.decision_v2.strategy import (
    DecisionV2Strategy,
)

#: ADR-0293 标定批次 registry 全字段快照 hash
#: (n=100 终验 mean 28.26/团灭 6/配对差 -2.89 的参数组)
#: ADR-0295 形态域结构批更新:新增 bench_form_weight/target_hold_cap_frac
#: 两字段(标定五参值不变);新批次 hash 见下
_EXPECTED_HASH = '16858a49a2430f6782dbcf44cadf2626aa79'
_EXPECTED_HASH += 'ce689c5bd61aa0f27b3506fab0b8'


def _card(name: str, faction: str = '仙舟罗浮', cost: int = 1) -> object:
    return SimpleNamespace(name=name, faction=faction, cost=cost,
                           x=0, star=1)


def _bench(name: str, faction: str = '仙舟罗浮',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 4, 'gold': 30, 'level': 5,
            'board': {'仙舟罗浮': 1}, 'bench': [], 'shop': [], 'hp': 100}
    base.update(kw)
    return GameState(**base)


def test_calibration_snapshot_values() -> None:
    """标定五参快照(ADR-0293 标定结果;改动须重标定+更新本锁)。"""
    assert DEFAULT_REGISTRY.refresh_ev == 2.5
    assert DEFAULT_REGISTRY.refresh_max_round == 6
    assert DEFAULT_REGISTRY.refresh_min_gold == 20
    assert DEFAULT_REGISTRY.target_hold_base == 9
    assert DEFAULT_REGISTRY.off_target_sell_bias == 0.5


def _norm(v):
    """可 JSON 化归一(tuple 键/集合→排序字符串;与 hash 计算同源)。"""
    if isinstance(v, dict):
        return {str(k): _norm(x)
                for k, x in sorted(v.items(), key=lambda t: str(t[0]))}
    if isinstance(v, (set, frozenset)):
        return sorted(map(str, v))
    if isinstance(v, tuple):
        return list(map(_norm, v))
    return v


def test_calibration_registry_hash() -> None:
    """registry 全字段 hash 锁:任何字段漂移即红(防静默改参)。"""
    payload = {f: _norm(getattr(DEFAULT_REGISTRY, f))
               for f in DecisionV2Registry.__dataclass_fields__}
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True,
                   ensure_ascii=False).encode('utf-8')).hexdigest()
    assert digest == _EXPECTED_HASH, (
        f'registry 漂移:hash {digest} != {_EXPECTED_HASH};'
        '若是有意改参——重标定(ADR-0293 流程)并更新本锁')


def test_refresh_round_gate() -> None:
    """轮界门:r≤6 按 refresh_ev 计净值;r>6 恒负分不刷。"""
    sess = StrategySession()
    cost = RefreshShop(cost=2).cost
    for rn, expect_pos in ((5, True), (7, False)):
        st = _state(round_num=rn, gold=50,
                    shop=[_card('占位件', faction='公司', cost=1)])
        cand = [c for c in generate_candidates(st, sess,
                                               DEFAULT_REGISTRY)
                if c.tag == 'refresh'][0]
        val, _ = score_candidate(cand, st, sess, DEFAULT_REGISTRY)
        if expect_pos:
            assert val == DEFAULT_REGISTRY.refresh_ev - cost
        else:
            assert val < 0, 'r>refresh_max_round 刷新必须恒负分'


def test_refresh_gold_floor_gate() -> None:
    """金保底门:金<20 不刷(防 re-decide 链抽干金流锁死息引擎)。"""
    st = _state(round_num=2, gold=15,
                shop=[_card('占位件', faction='公司', cost=1)])
    sess = StrategySession()
    cand = [c for c in generate_candidates(st, sess, DEFAULT_REGISTRY)
            if c.tag == 'refresh'][0]
    val, _ = score_candidate(cand, st, sess, DEFAULT_REGISTRY)
    assert val < 0, '金<refresh_min_gold 刷新必须恒负分'


def test_off_target_sell_bias_flips_zero_score() -> None:
    """弱件换金:持有域溢出件卖分 0+偏置>0(无偏置被非正分拒)。"""
    # 溢出构造:level 低、bench 远超 cap(depth 饱和)→ 卖不改形态
    st = _state(
        level=3, gold=10,
        shop=[_card('占位件', faction='公司', cost=1)],
        bench=[_bench('囤件甲', slot=1), _bench('囤件乙', slot=2),
               _bench('囤件丙', slot=3), _bench('囤件丁', slot=4)],
    )
    sess = StrategySession()
    sells = [c for c in generate_candidates(st, sess, DEFAULT_REGISTRY)
             if c.tag == 'off_target']
    assert sells, '溢出 bench 应生成 off_target 卖候选'
    val, _bd = score_candidate(sells[0], st, sess, DEFAULT_REGISTRY)
    # 溢出件(持有>cap):基础卖分 0,偏置翻正——「弱件换金」语义
    assert val == DEFAULT_REGISTRY.off_target_sell_bias, (
        f'溢出件卖分应为偏置值(实际 {val})')


def test_strategy_default_uses_calibrated_registry() -> None:
    """默认策略注入标定后 registry(标定参数即生产行为)。"""
    s = DecisionV2Strategy()
    assert s.registry is DEFAULT_REGISTRY
    assert s.registry.refresh_ev == 2.5
