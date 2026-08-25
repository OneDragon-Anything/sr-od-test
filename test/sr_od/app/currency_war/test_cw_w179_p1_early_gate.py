# -*- coding: utf-8 -*-
"""W179/ADR-0372 P1 早期新件买入门单帧锁(pass_buy 修法)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 未锁形态期窗开:FORM 相位金 14(地板 20 拦截面)买 1费对成员
  → 同息档放行 + auth trace + 轮计数;
- ② 息档边界:同档 0 损放行 / 跨档拒([11] 口径:买入后不跨息档才
  放行,跨档走既有 EV 授权,不经本门);
- ③ bench 满拒([22]② bench 唯一稀缺);
- ④ 同名不辖:state 已持有 / 同轮前笔买入(working)后的同名第二笔
  都不经本门(3合1 素材语境交既有 copy 豁免面);
- ⑤ 刷新金零授权:同帧 refresh 候选拒([31] 买门与 W170 刷门管辖
  动作不交集——不授权任何刷新金);
- ⑥ flag off 逐位回 W174 后行为(金地板原样拒);
- ⑦ 单轮上限:cap 笔数耗尽后同窗同档第二笔拒(防 r1 扫店);
- ⑧ P2 不辖 / 应急态不辖([18] 纪律态优先);
- ⑨ p1_early_pair 读口:未锁期无门槛派生 top-2 / 锁定帧意向字段
  优先 / P2 恒空。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.cw_intention import (
    IntentionState,
    p1_early_pair,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
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
from sr_od.application.currency_war.decision_v2.scoring import score_all

_REG = DEFAULT_REGISTRY


def _sess() -> StrategySession:
    s = StrategySession()   # 未锁线 → FORM 相位(engines<2)
    s.v3_mode = 'economy'
    s.v2_round_key = (1, 4)
    s.v2_round_p1_early = 0
    return s


def _state(**kw) -> GameState:
    # 板面:三月七(列车,deployed)+ 青雀(仙舟,bench)→ 支持度 top-2
    # = (列车同行, 仙舟)(_P1_PAIR_PREF 序),未持有对成员 >> k=6
    base = {'plane': 1, 'round_num': 4, 'gold': 14, 'level': 4,
            'hp': 100, 'board': {}, 'bench': [BenchChar(
                slot=0, char_id='青雀', faction='仙舟', star=1)],
            'deployed': [BenchChar(slot=9, char_id='三月七',
                                   faction='列车同行', star=1)],
            'shop': [], 'node_type': 'battle'}
    base.update(kw)
    return GameState(**base)


def _cand(name: str, cost: int, tag: str = 'line_opportunistic') -> Candidate:
    return Candidate(
        action=BuyCard(ShopCard(name=name, faction='仙舟', cost=cost,
                                x=0, star=1), reason=''),
        tag=tag, source='shop')


def _buy_rows(res):
    return [r for r in res.log if r['tag'] == 'line_opportunistic']


def test_gate_open_form_phase_buy_passes() -> None:
    """①未锁形态期窗开:金 14(14-1=13<地板 20,旧路径必拒)买 1费
    仙舟对成员停云 → 同息档(14→13,档 1 不变)放行;auth trace 与
    轮计数在场——pass_buy 修法的行为本体。"""
    st = _state()
    s = _sess()
    cand = _cand('停云', 1)
    scored = score_all([cand], st, s, _REG)
    res = arbitrate(scored, st, s, _REG)
    row = _buy_rows(res)[0]
    assert row['accepted'] is True, row
    assert row['ev_auth'].get('p1_early'), row   # 授权依据 trace
    assert s.v2_round_p1_early == 1
    assert any(isinstance(a, BuyCard) and a.card.name == '停云'
               for a in res.actions)


def test_tier_boundary_same_vs_cross() -> None:
    """②息档边界:同档(14-1=13 档1)放行;跨档(11-2=9 档1→0)拒
    ——[11] 精确口径:跨档最多损 1 金,不经本门放行。"""
    st_ok = _state()
    s1 = _sess()
    res1 = arbitrate(score_all([_cand('停云', 1)], st_ok, s1, _REG),
                     st_ok, s1, _REG)
    assert _buy_rows(res1)[0]['accepted'] is True
    st_cross = _state(gold=11)
    s2 = _sess()
    res2 = arbitrate(score_all([_cand('停云', 2)], st_cross, s2, _REG),
                     st_cross, s2, _REG)
    row = _buy_rows(res2)[0]
    assert row['accepted'] is False, row
    assert 'gold_floor' in row['reject'], row
    assert not row.get('ev_auth', {}).get('p1_early')


def test_bench_full_gate_closed() -> None:
    """③bench 满(bench 余槽 <1)→ 窗关拒([22]② bench 唯一稀缺)。"""
    filler = [BenchChar(slot=i, char_id='银枝', faction='智识', star=1)
              for i in range(9)]
    st = _state(bench=filler)
    s = _sess()
    res = arbitrate(score_all([_cand('停云', 1)], st, s, _REG),
                    st, s, _REG)
    row = _buy_rows(res)[0]
    assert row['accepted'] is False, row


def test_same_name_not_governed() -> None:
    """④同名不辖:state 已持有(青雀在 bench)→ 不在门内集;同轮前笔
    买入(working 现持)后的同名第二笔也不经本门(distinct=对 working
    现持判定)。"""
    # ④a:已持有名(青雀)→ 门内集不含 → 拒
    st = _state()
    s = _sess()
    res = arbitrate(score_all([_cand('青雀', 1)], st, s, _REG),
                    st, s, _REG)
    row = _buy_rows(res)[0]
    assert row['accepted'] is False, row
    assert not row.get('ev_auth', {}).get('p1_early')
    # ④b:同轮两笔同名(停云×2)→ 只第一笔经门,第二笔无门授权
    st2 = _state()
    s2 = _sess()
    cands = [_cand('停云', 1), _cand('停云', 1)]
    res2 = arbitrate(score_all(cands, st2, s2, _REG), st2, s2, _REG)
    rows = _buy_rows(res2)
    gated = [r for r in rows if r.get('ev_auth', {}).get('p1_early')]
    assert len(gated) <= 1, rows   # 同名重复不辖(copy 面)


def test_no_refresh_authorized() -> None:
    """⑤刷新金零授权:同帧(金 14)refresh 候选拒——[3] 预算前提
    (50+刷+买)结构性不满足,V_D 无对象 → 非正分;本门只辖买不辖刷。"""
    from sr_od.application.currency_war.cw_state import RefreshShop
    st = _state()
    s = _sess()
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='shop')
    res = arbitrate(score_all([cand], st, s, _REG), st, s, _REG)
    row = next(r for r in res.log if r['tag'] == 'refresh')
    assert row['accepted'] is False, row
    assert not any(isinstance(a, RefreshShop) for a in res.actions)


def test_flag_off_reverts_bitwise() -> None:
    """⑥flag off:同帧回到 W174 后行为(gold_floor 原样拒)。"""
    reg = dataclasses.replace(_REG, p1_early_gate_enabled=False)
    st = _state()
    s = _sess()
    res = arbitrate(score_all([_cand('停云', 1)], st, s, reg),
                    st, s, reg)
    row = _buy_rows(res)[0]
    assert row['accepted'] is False, row
    assert '金<20' in row['reject'], row


def test_round_cap_blocks_second_buy() -> None:
    """⑦单轮上限(cap=1):同窗同档两个不同对成员,只第一笔过门,
    第二笔被上限截断(防 r1 扫店)。"""
    st = _state()
    s = _sess()
    cands = [_cand('停云', 1), _cand('藿藿', 1)]
    res = arbitrate(score_all(cands, st, s, _REG), st, s, _REG)
    rows = _buy_rows(res)
    gated = [r for r in rows if r.get('ev_auth', {}).get('p1_early')]
    assert len(gated) == 1, rows
    assert s.v2_round_p1_early == _REG.p1_early_round_cap


def test_p2_and_emergency_not_governed() -> None:
    """⑧P2 不辖(买入门只辖 P1)/ 应急态不辖([18] 纪律态地板优先)。"""
    st_p2 = _state(plane=2)
    s1 = _sess()
    res1 = arbitrate(score_all([_cand('停云', 1)], st_p2, s1, _REG),
                     st_p2, s1, _REG)
    assert _buy_rows(res1)[0]['accepted'] is False
    st_em = _state(hp=20)   # hp≤emergency_hp=25 → 应急态
    s2 = _sess()
    res2 = arbitrate(score_all([_cand('停云', 1)], st_em, s2, _REG),
                     st_em, s2, _REG)
    row = _buy_rows(res2)[0]
    assert row['accepted'] is False, row
    assert not row.get('ev_auth', {}).get('p1_early')


def test_p1_early_pair_read_port() -> None:
    """⑨p1_early_pair 读口:未锁期无门槛派生 top-2(与 _derive_p1_pair
    同口径但无 P1_PAIR_LOCK_MIN_SUPPORT);锁定帧意向字段优先;P2 恒空。"""
    st = _state()
    # 未锁:板上三月七(列车 0.5)+青雀(仙舟 1/3)→ top-2 无门槛派生
    assert p1_early_pair(st, None) == ('列车同行', '仙舟')
    # 配方锁定帧:p1_pair 优先于现场派生
    ist = IntentionState(p1_pair=('仙舟', '持续伤害'))
    assert p1_early_pair(st, ist) == ('仙舟', '持续伤害')
    # ①锁局帧:transition_pair 优先于 p1_pair
    ist2 = IntentionState(p1_pair=('仙舟', '持续伤害'),
                          transition_pair=('列车同行', '持续伤害'))
    assert p1_early_pair(st, ist2) == ('列车同行', '持续伤害')
    # 空板未锁(支持度全 0):无门槛同样派生(pref 序 top-2)——与
    # _derive_p1_pair(返回 ())的语义差异本体
    st_empty = _state(bench=[], deployed=[])
    assert p1_early_pair(st_empty, None) != ()
    from sr_od.application.currency_war.cw_intention import _derive_p1_pair
    assert _derive_p1_pair(st_empty) == ()
    # P2 恒空
    assert p1_early_pair(_state(plane=2), None) == ()
