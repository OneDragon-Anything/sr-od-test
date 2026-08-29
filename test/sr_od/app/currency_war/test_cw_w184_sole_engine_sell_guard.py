# -*- coding: utf-8 -*-
"""W184/ADR-0373 卖侧唯一体系引擎守卫单帧锁(S2 恶化谱系修法)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 守卫触发:TT 体系件(全羁绊口径,「持续伤害」是流派非阵营)在
  owned≤tier 时不进任何卖件通道——candidates 不生成卖候选(三 tag
  全无)+ sell_priority_key=None(carry_gate ④/两补偿器统一挡);
- ② 跌破 tier 边界:owned=tier(两件 DOT)卖一件 → 拒(71 卡芙卡型:
  卖出使体系在手数跌破 tier);
- ③ 清空边界:owned=1(唯一 owned 引擎件)→ 拒(37/43/45/90 型);
- ④ 不辖·非 TT 件:off_target 照旧(散件清理合法面);
- ⑤ 不辖·冗余件:owned>tier(仙舟 4 distinct 件)→ 卖候选照旧生成
  (体系有余量时清仓不受辖);
- ⑥ flag off 逐位回 W179 后行为(sole 件重新可卖);
- ⑦ 应急态(for_gold)同样不辖卖出:唯一引擎件不为折现清空。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.discipline import (
    sell_priority_key,
    sole_engine_sell_blocked,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY
_REG_OFF = dataclasses.replace(_REG, sell_sole_engine_guard_enabled=False)


def _sess() -> StrategySession:
    s = StrategySession()
    s.v2_round_key = (1, 5)
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 60, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _bc(name: str, faction: str, slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _sell_cands(st: GameState, sess: StrategySession, reg=_REG):
    return [c for c in generate_candidates(st, sess, reg)
            if c.tag in ('off_target', 'for_gold', 'free_bench')]


def test_guard_blocks_sole_engine_piece() -> None:
    """③清空边界:唯一 owned DOT 引擎件(艾丝妲,bench 单件)→ 三卖
    tag 候选全无 + 弱序键 None + 谓词真(W181 seed37/43/45 型:
    演进换线把体系件下场到 bench 后被 off_target 卖出)。"""
    sess = _sess()
    st = _state(bench=[_bc('艾丝妲', '持续伤害')])
    assert sole_engine_sell_blocked(st.bench[0], st, _REG) is True
    assert _sell_cands(st, sess) == []
    assert sell_priority_key(st.bench[0], st, sess, None, _REG) is None


def test_guard_blocks_tier_drop_boundary() -> None:
    """②跌破 tier 边界:两件 DOT(owned=tier=2)卖任一件 → 拒
    (seed71 卡芙卡型:owned 2→1 < tier 2)。"""
    sess = _sess()
    st = _state(bench=[_bc('艾丝妲', '持续伤害', 0),
                       _bc('卡芙卡', '公司', 1)])
    for i in (0, 1):
        assert sole_engine_sell_blocked(st.bench[i], st, _REG) is True
        assert sell_priority_key(st.bench[i], st, sess, None, _REG) is None
    assert _sell_cands(st, sess) == []


def test_guard_not_govern_non_tt_piece() -> None:
    """④不辖·非 TT 件:银枝(智识,非四过渡体系)照旧 off_target
    (bench 溢出腾位/economy 散件清理的合法面)。"""
    sess = _sess()
    st = _state(bench=[_bc('银枝', '智识')])
    assert sole_engine_sell_blocked(st.bench[0], st, _REG) is False
    cands = _sell_cands(st, sess)
    assert [c.breakdown_hint.get('name') for c in cands] == ['银枝']
    assert cands[0].tag == 'off_target'
    assert sell_priority_key(st.bench[0], st, sess, None, _REG) is not None


def test_guard_not_govern_redundant_tt_piece() -> None:
    """⑤不辖·冗余件:仙舟 4 distinct 件(owned=4>tier=3)→ 青雀
    照旧生成 off_target 卖候选(体系有余量时的清仓不受辖)。"""
    sess = _sess()
    st = _state(bench=[_bc('青雀', '仙舟', 0), _bc('停云', '仙舟', 1),
                       _bc('藿藿', '仙舟', 2), _bc('爻光', '仙舟', 3)])
    names = [c.breakdown_hint.get('name')
             for c in _sell_cands(st, sess)]
    assert '青雀' in names, f'冗余 TT 件应可卖:{names}'


def test_guard_covers_deployed_and_flows_caliber() -> None:
    """辖域口径:owned=bench∪deployed 逐件计(deployed 的 DOT 件也
    计入 owned——53 卡芙卡在场+bench 卖不因「场上还有」放行恒真,
    本锁锁 bench 单件与 deployed 计数合并后的 tier 边界)。"""
    sess = _sess()
    # bench 桑博 + deployed 椒丘 = owned DOT 2 = tier → 桑博卖拒
    st = _state(bench=[_bc('桑博', '持续伤害')],
                deployed=[_bc('椒丘', '持续伤害', slot=9)])
    assert sole_engine_sell_blocked(st.bench[0], st, _REG) is True
    # 再加 deployed 艾丝妲 → owned 3 > tier 2 → 桑博可卖
    # (W192/ADR-0375 适配:桑博=贝+DOT 双籍,希儿系侧另辖——补 deployed
    # 娜塔莎(贝)使希儿系在手 2>1,本锁回归纯 TT 口径;希儿系辖域由
    # test_cw_w192_seele_scope ⑤ 锁)
    st2 = _state(bench=[_bc('桑博', '持续伤害')],
                 deployed=[_bc('椒丘', '持续伤害', slot=9),
                           _bc('艾丝妲', '持续伤害', slot=10),
                           _bc('娜塔莎', '贝洛伯格', slot=11)])
    assert sole_engine_sell_blocked(st.bench[0], st2, _REG) is False


def test_guard_emergency_not_liquidated() -> None:
    """⑦应急态:hp≤emergency_hp 时唯一 DOT 引擎件也不为折现清空
    (for_gold 候选不生成——[18] 应急是最小必要支出,不是清空引擎)。"""
    sess = _sess()
    st = _state(hp=20, bench=[_bc('艾丝妲', '持续伤害')])
    assert _sell_cands(st, sess) == []


def test_flag_off_restores_w179_behavior() -> None:
    """⑥flag off 逐位回退:sole 引擎件重新生成 off_target 卖候选
    + 弱序键非 None(= W179 后行为)。"""
    sess = _sess()
    st = _state(bench=[_bc('艾丝妲', '持续伤害')])
    assert sole_engine_sell_blocked(st.bench[0], st, _REG_OFF) is False
    cands = _sell_cands(st, sess, _REG_OFF)
    assert [c.breakdown_hint.get('name') for c in cands] == ['艾丝妲']
    assert cands[0].tag == 'off_target'
    assert sell_priority_key(st.bench[0], st, sess, None, _REG_OFF) \
        is not None
