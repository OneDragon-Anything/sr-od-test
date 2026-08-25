# -*- coding: utf-8 -*-
"""W114/ADR-0346 相位影子观测单帧锁(经济循环总模型步①)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- 相位判定四例(W113 §3.1 切换判据表,裁决后版本:无等级项/核心须上场):
  ①意向未锁+板面空 → FORM(form_ok=False);
  ②意向锁定+羁绊凑够+核心上场 2★+金 40 → HOARD(form_ok=True);
  ③同②帧但金 55 → SPEND;
  ④意向锁定+羁绊凑够但核心仍 1★ → FORM(核心未达;躺 bench 也不算)。
- 影子零消费:decide_prep 计算相位只写 session/遥测,不改变任何决策。
- sim 端到端:账本行带 phase/form_ok/form_score 字段且值域合法。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_intention import (
    IntentionState,
    intention_core,
)
from sr_od.application.currency_war.cw_sim import simulate_p1
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.phase import (
    Phase,
    derive_phase,
    form_ok,
    form_score,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)


def _comp_frame(**kw) -> GameState:
    """成型态帧:DOT队 form_tiers 全满(board 只数上场)+ 核心上场 2★。"""
    comp = get_comp('DOT队')
    core = intention_core(comp)
    base = {
        'plane': 1, 'round_num': 7, 'gold': 40, 'level': 5,
        'hp': 60, 'board': {f: t for f, t in comp.form_tiers.items()},
        'deployed': [BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                               star=2)],
        'bench': [], 'shop': [],
    }
    base.update(kw)
    return GameState(**base)


def _sess_locked() -> StrategySession:
    sess = StrategySession()
    sess.v3_intention = IntentionState(phase='locked', locked_comp='DOT队')
    return sess


def test_case1_unlocked_empty_board_form() -> None:
    """①意向未锁+板面空 → FORM;form_ok=False(兜底门:score 0 < 0.5)。"""
    state = GameState(plane=1, round_num=1, gold=10, level=3, hp=100)
    sess = StrategySession()   # 默认 unlocked
    assert form_ok(state, sess, DEFAULT_REGISTRY) is False
    assert derive_phase(state, sess, DEFAULT_REGISTRY) is Phase.FORM
    assert form_score(state, DEFAULT_REGISTRY) == 0.0


def test_case2_locked_formed_gold40_hoard() -> None:
    """②意向锁定+羁绊凑够+核心上场 2★+金 40 → HOARD;form_ok=True。"""
    state = _comp_frame(gold=40)
    sess = _sess_locked()
    assert form_ok(state, sess, DEFAULT_REGISTRY) is True
    assert derive_phase(state, sess, DEFAULT_REGISTRY) is Phase.HOARD


def test_case3_same_frame_gold55_spend() -> None:
    """③同②帧但金 55(≥interest_floor=50)→ SPEND。"""
    state = _comp_frame(gold=55)
    sess = _sess_locked()
    assert form_ok(state, sess, DEFAULT_REGISTRY) is True
    assert derive_phase(state, sess, DEFAULT_REGISTRY) is Phase.SPEND


def test_case4_core_one_star_form() -> None:
    """④意向锁定+羁绊凑够但核心仍 1★ → FORM(核心未达 2★)。

    附:核心 2★ 躺 bench(未上场)同样不算——「核心须上场」裁决。
    """
    comp = get_comp('DOT队')
    core = intention_core(comp)
    # 核心上场但 1★
    s1 = _comp_frame(deployed=[BenchChar(slot=0, char_id=core,
                                         faction='仙舟罗浮', star=1)])
    # 核心 2★ 但在 bench 不在场上
    s2 = _comp_frame(deployed=[], bench=[
        BenchChar(slot=0, char_id=core, faction='仙舟罗浮', star=2)])
    for s in (s1, s2):
        sess = _sess_locked()
        assert form_ok(s, sess, DEFAULT_REGISTRY) is False, (
            '核心未达(1★ 或未上场)时 form_ok 必须为 False')
        assert derive_phase(s, sess, DEFAULT_REGISTRY) is Phase.FORM


def test_phase_score_bounds_and_fallback_gate() -> None:
    """form_score ∈ [0,1];兜底门走 registry 常量(可 A/B 注入,禁散落)。

    兜底降级路径:未锁但上场阵容拉满 2 过渡体系(仙舟3+列车2 真角色
    上场)→ score ≥ gate → form_ok True(体系判定单一源 _engines_count)。
    """
    assert 0.0 <= DEFAULT_REGISTRY.phase_form_score_gate <= 1.0
    from sr_od.application.currency_war.cw_chars import CHARACTERS
    from sr_od.application.currency_war.cw_deploy_logic import (
        TRANSITION_TRAITS,
    )
    traits = dict(TRANSITION_TRAITS)
    want: list[tuple[str, int]] = list(traits.items())[:2]   # 前两体系
    deployed: list[BenchChar] = []
    used: set[str] = set()
    for bond, tier in list(traits.items())[:2]:   # 前两体系逐个凑
        got = 0
        for cid, ch in CHARACTERS.items():
            if got >= tier or cid in used:
                continue
            if bond in (ch.factions or ()) + (ch.flows or ()):
                used.add(cid)
                got += 1
                deployed.append(BenchChar(
                    slot=len(deployed), char_id=cid,
                    faction=ch.factions[0], star=1))
        assert got >= tier, f'角色表凑不齐体系 {bond}×{tier}'
    state = GameState(plane=1, round_num=5, gold=30, level=6, hp=80,
                      deployed=deployed, bench=[], shop=[])
    sess = StrategySession()   # unlocked → 兜底门路径
    score = form_score(state, DEFAULT_REGISTRY)
    assert score >= DEFAULT_REGISTRY.phase_form_score_gate, score
    assert form_ok(state, sess, DEFAULT_REGISTRY) is True
    assert derive_phase(state, sess, DEFAULT_REGISTRY) is Phase.HOARD


def test_sim_ledger_has_phase_fields() -> None:
    """sim 端到端:账本每轮行带 phase/form_ok/form_score,值域合法
    (影子字段零消费——存在性与值域,不锁分布)。"""
    res = simulate_p1(0, pool='snapshot')
    assert res.ledger, 'sim 账本为空'
    for row in res.ledger:
        assert row.get('phase') in ('FORM', 'HOARD', 'SPEND'), row
        assert isinstance(row.get('form_ok'), bool), row
        assert 0.0 <= float(row.get('form_score') or 0.0) <= 1.0, row
