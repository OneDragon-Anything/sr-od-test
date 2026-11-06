"""entry.emit 骨架帧装配测试(k_members 换源的空窗判定面;阶段 1 =
roster-plane1-union design §2.6 换源不消亡)。

被测 = ``strategies/impl/mandate_v1/entry.py`` 的 ``emit`` 顶段 k_members
装配:读口换源为统一线内名单(``sell_line_membership``,§2.1 口径)
后,K 空窗回退的触发条件从「无方向(direction_comp_of → None)」改为
「名单真空(未锁定 ∧ 候选/配方全空)」——未锁帧有候选即有名单,不再
落 kernel 回退带;真·空窗帧回退照常运行(回退本体零改)。

观测面 = ``prep_k_fallback_<band>`` 计数键(写入端单一源 = entry.emit
顶段;decision_payload 同参重推导不写计数)。种子纪律 = 容器即 session
(生产形态 session/gs 同一对象;一次性容器经 cw4_gs(None) 冷建)。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.strategies.impl.mandate_v1 import entry
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)


def _emit_gs(*, candidates: tuple[str, ...]):
    """最小可扫帧种子:上场 1 人(免空板守卫路径)+ 充裕金;候选快照
    按参种入(无配方/无锁定;方向键 = None 形态)。返回容器(即
    session/状态宿主)。"""
    gs = cw4_gs(None, level=5, gold=200, node='prep',
                front_row=[Unit(char_id='刃', star=1)])
    state_of(gs).line_candidates = candidates
    return gs


def _fallback_keys(gs) -> list[str]:
    return [k for k in state_of(gs).cw4_counters
            if k.startswith('prep_k_fallback_')]


def test_emit_no_fallback_when_candidates_present() -> None:
    """换源后空窗判定 = 名单真空:未锁帧有候选(方向键 None——无配方
    无锁定)→ 统一线内名单非空,回退不运行;旧读口按「无方向」判定
    会落 p1_gap/p1_lock_band 带(换源后候选即名单,§2.1 口径)。"""
    gs = _emit_gs(candidates=('列车同行·反震',))
    state_of(gs).v3_intention = IntentionState()
    entry.emit(gs, None)
    assert _fallback_keys(gs) == [], '候选在场 = 名单非空,非空窗'


def test_emit_fallback_runs_on_true_empty_roster() -> None:
    """真·空窗(未锁定 ∧ 候选/配方全空)∧ 意向载体在场 → 回退照常
    运行(P1 带防「K 空→零买入→支持度永不涨」死锁环;换源只改判定
    条件,回退本体与计数键零改)。"""
    gs = _emit_gs(candidates=())
    state_of(gs).v3_intention = IntentionState()
    entry.emit(gs, None)
    keys = _fallback_keys(gs)
    assert keys and all(k.endswith(('p1_gap', 'p1_lock_band'))
                        for k in keys), '真·空窗帧回退带在案'


def test_prep_entry_clears_deploy_margin_slot() -> None:
    """部署私有槽入口清(pick-margin-telemetry design §2.1 帧定界
    双保险之一):prep 入口清空陈旧槽——上一帧写槽后 emit 段/truncate
    抛异常的残留(决策入口异常不调 payload 钩子)由本清兜底,非部署
    帧读到恒空。状态归一 = cw4_decide 先例(策略器状态 = 会话播种
    对象,构造重接入调用后显式归位)。"""
    from types import SimpleNamespace

    from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
        MandateV1Strategy,
    )
    gs = _emit_gs(candidates=('列车同行·反震',))
    st = state_of(gs)
    strat = MandateV1Strategy(gs, SimpleNamespace(strategy_seed=None))
    strat.state = st   # 状态归一(cw4_decide 先例)
    st.deploy_margin = {'runner_up': ['陈旧残留'], 'first_diff_layer': 1,
                        'layer_gap': 1.0}
    strat.decide_prep_screen()
    assert st.deploy_margin is None, '入口清:跨帧陈旧槽被清空'
