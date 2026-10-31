"""mandate_v1 决策载荷锁面(三键组与直算一致 + 回退分支两态 + wrapper 降级)。

被测 = src/sr_od/application/currency_war/strategies/impl/mandate_v1/
decision_payload.py(build_decision_payload)与 bridge.MandateV1Strategy.
decision_payload 覆写;
设计出处 = strategy-docs/strategy-telemetry.md(payload 键表正本)+
changes/2026-10-24-strategy-telemetry/details/capture-store.md §3。
判据:payload 三键与 gs/state 现读直算一致;window 结论与
``entry._entry_window_open`` 直调一致;k_fallback 与
``cw_intention.k_empty_window_fallback`` 直调一致;锁定帧 candidates=[];
覆写后的钩子异常仍由基类 wrapper 降级 {}。
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_gs,
    cw4_members,
)

from sr_od.application.currency_war.kernel import cw_intention
from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickPartnerParam,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    set_decision_sink,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    session_scope,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.decision_payload import (
    build_decision_payload,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_CFG = SimpleNamespace(strategy_seed=None)


def _make(gs: GameState) -> MandateV1Strategy:
    """装配被测策略器(终态契约构造注入;registry 缺省 = DEFAULT_REGISTRY)。"""
    return MandateV1Strategy(gs, _CFG)


def _held_names(gs: GameState) -> set[str]:
    """持有域名字集(bench ∪ deployed;与被测读口同源派生,供期望集计算)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        bench_units_of,
        deployed_rows_of,
    )
    front, back = deployed_rows_of(gs)
    return {str(getattr(u, 'char_id', '') or '')
            for u in (*bench_units_of(gs), *front, *back) if u is not None}


def _expected_window(gs: GameState, k_members: list[str],
                     comps: list) -> dict:
    """window 键期望值直算(与被测同一数据源,逐键独立重推):
    键集 = k_members ∪ 持有域 ∩ 终局库成员;open = 判定核直调;
    sig = 查表序 comps 内首个信号行。"""
    expected: dict[str, dict] = {}
    for char in sorted(set(k_members)
                       | (_held_names(gs) & entry._ENDGAME_LIBRARY_MEMBERS)):
        sig = None
        for comp in comps:
            row = comp.entry_signals.get(char)
            if row is not None:
                sig = [row[0], row[1]]
                break
        expected[char] = {
            'open': entry._entry_window_open(gs, char),
            'sig': sig,
        }
    return expected


def _assert_window_matches_direct(gs: GameState, payload: dict,
                                  comps: list) -> None:
    """window 键值与判定核/信号行直调一致(完成判据项;逐键直调对照)。"""
    window = payload['window']
    for char, cell in window.items():
        assert cell['open'] == entry._entry_window_open(gs, char), char
    assert window == _expected_window(gs, payload['k_members'], comps)


def test_locked_frame_three_keys_and_window_consistent() -> None:
    """锁定帧三键直算一致:direction(锁定/线名/候选清空)+ k_members
    (锁定线名单,统一线内名单读口——排序序,非注册表序;配方槽空集
    时 = 锁定线单源)+ k_fallback(分支未运行)+ window(结论与 sig 同
    查表序);另锁 payload 可 JSON 序列化(sink json.dumps 前置契约)。"""
    gs = cw4_gs(None, plane=1, round_num=2, node='prep',
                bench=[cw4_bc('花火')])
    strat = _make(gs)
    st = state_of(gs)
    st.line_candidates = ('候选甲', '候选乙', '候选丙')   # 锁定前非空候选态
    session_scope.write_line_lock(gs, '黄泉减益')
    comp = get_comp('黄泉减益')
    assert comp is not None
    k_members = cw4_members(comp)

    payload = strat.decision_payload()

    assert payload['direction'] == {
        'locked': True, 'comp': '黄泉减益', 'candidates': [],
    }
    assert payload['k_members'] == sorted(k_members)
    assert payload['k_fallback'] == {'hit': False, 'band': ''}
    _assert_window_matches_direct(gs, payload, [comp])
    json.dumps(payload)   # 行行自足:载荷可整体序列化落盘


def test_unlocked_recipe_frame_window_set_boundary() -> None:
    """P1 未锁配方帧:direction 回落配方键(locked=False/候选透传);
    window 角色集边界 = k_members ∪ 持有域终局库成员——备战席终局件
    入集(被窗口挡住的判域主体),持有域注册表外名字不入集。"""
    gs = cw4_gs(None, plane=1, round_num=1, node='prep',
                bench=[cw4_bc('花火'), cw4_bc('杂1')])
    strat = _make(gs)
    st = state_of(gs)
    comp = get_comp('专家桑博DOT')
    assert comp is not None
    st.opening_recipe_comp = comp
    st.line_candidates = ('线一', '线二', '线三')

    payload = strat.decision_payload()

    assert payload['direction'] == {
        'locked': False, 'comp': comp.name,
        'candidates': ['线一', '线二', '线三'],
    }
    # 未锁帧统一线内名单 = 候选并集(假线名解析失败跳过)∪ 配方成员
    # = 配方成员集;排序序(读口 = sell_line_membership)。
    assert payload['k_members'] == sorted(cw4_members(comp))
    assert payload['k_fallback'] == {'hit': False, 'band': ''}
    assert '花火' in payload['window']
    assert '杂1' not in payload['window']   # 终局库外持有件不入窗口键集
    _assert_window_matches_direct(gs, payload, list(COMP_LIBRARY))


def test_k_fallback_hit_and_miss_states() -> None:
    """回退分支两态与 cw_intention 直调一致:方向缺 ∧ 意向缺帧 = 分支未
    运行(hit=False/band='');方向缺 ∧ 意向在场 = 分支运行,带名与成员集
    与 k_empty_window_fallback 同参直调一致(空板面 P1 = p1_gap 带)。"""
    # 未命中态:无方向、无意向载体(保守侧不回退)
    gs_miss = cw4_gs(None, plane=1, round_num=2, node='prep')
    payload_miss = build_decision_payload(gs_miss, DEFAULT_REGISTRY)
    assert payload_miss['k_members'] == []
    assert payload_miss['k_fallback'] == {'hit': False, 'band': ''}

    # 命中态:意向在场(空板面支持度 0 < 锁门槛 → p1_gap 带非空成员集)
    gs_hit = cw4_gs(None, plane=1, round_num=2, node='prep')
    state_of(gs_hit).v3_intention = cw_intention.IntentionState()
    payload_hit = build_decision_payload(gs_hit, DEFAULT_REGISTRY)
    members, band = cw_intention.k_empty_window_fallback(
        gs_hit, state_of(gs_hit).v3_intention,
        session=gs_hit, registry=DEFAULT_REGISTRY)
    assert members, '前置:测试场景回退分支应产出非空成员集'
    assert payload_hit['k_fallback'] == {'hit': True, 'band': band}
    assert payload_hit['k_members'] == sorted(members)


def test_payload_hook_exception_degrades_via_wrapper() -> None:
    """覆写后的钩子异常仍由基类 wrapper 降级 {}(降级唯一通道在
    wrapper,决策返回值不受影响;sink = 内存假闭包,teardown 摘除)。"""

    class _PayloadBoomStrategy(MandateV1Strategy):
        """mandate 实类 + payload 必抛(降级分支场景)。"""

        def decide_partner(self) -> CwActionPickPartnerParam:
            return CwActionPickPartnerParam(idx=0, reason='probe')

        def decision_payload(self) -> dict:
            raise RuntimeError('payload boom')

    records: list[dict] = []
    set_decision_sink(records.append)
    try:
        strat = _PayloadBoomStrategy(
            GameState(schema_version=GAME_STATE_SCHEMA_VERSION), _CFG)
        result = strat.decide_partner()
        assert isinstance(result, CwActionPickPartnerParam)
        assert records[0]['payload'] == {}
    finally:
        set_decision_sink(None)


def test_payload_pure_read_no_state_mutation() -> None:
    """纯读纪律:同帧连调两次结论一致,且不写 cw4_counters/意向缓存
    (载荷不得改变决策行为面)。"""
    gs = cw4_gs(None, plane=1, round_num=2, node='prep',
                bench=[cw4_bc('花火')])
    strat = _make(gs)
    state_of(gs).v3_intention = cw_intention.IntentionState()
    counters_before = dict(state_of(gs).cw4_counters)
    first = strat.decision_payload()
    second = strat.decision_payload()
    assert first == second
    assert state_of(gs).cw4_counters == counters_before
