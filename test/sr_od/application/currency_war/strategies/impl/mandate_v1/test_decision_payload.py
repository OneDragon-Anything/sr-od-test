"""mandate_v1 决策载荷锁面(键组与直算一致 + 回退分支两态 + wrapper 降级)。

被测 = src/sr_od/application/currency_war/strategies/impl/mandate_v1/
decision_payload.py(build_decision_payload)与 bridge.MandateV1Strategy.
decision_payload 覆写;
设计出处 = strategy-docs/strategy-telemetry.md(payload 键表正本)+
changes/2026-10-24-strategy-telemetry/details/capture-store.md §3。
判据:payload 各键与 gs/state 现读直算一致;k_fallback 与
``cw_intention.k_empty_window_fallback`` 直调一致;锁定帧 candidates=[];
过渡候选槽照录、member_rank 二元组与统一优先级装配同源(终局 (0, 线内
序数)/过渡 (1, 候选位次));覆写后的钩子异常仍由基类 wrapper 降级 {}。
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
    get_comp,
    member_rank_of,
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


def test_locked_frame_three_keys_and_window_consistent() -> None:
    """锁定帧三键直算一致:direction(锁定/线名/候选清空)+ k_members
    (锁定线名单,统一线内名单读口——排序序,非注册表序;配方槽空集
    时 = 锁定线单源)+ k_fallback(分支未运行);另锁 payload 可 JSON
    序列化(sink json.dumps 前置契约)。"""
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
    # 过渡候选槽未种植 = 空槽照录;锁定帧 member_rank = 锁定线知识卡
    # 序数表包 (0, 线内序数)(过渡支无候选,终局半边单源)。
    assert payload['transition_candidates'] == []
    assert payload['member_rank'] == {
        n: (0, p) for n, p in member_rank_of(comp).items()}
    json.dumps(payload)   # 行行自足:载荷可整体序列化落盘


def test_unlocked_recipe_frame_direction_and_members() -> None:
    """P1 未锁配方帧:direction 回落配方键(locked=False/候选透传)。

    k_members 口径(过渡支 = 32 号稿 §2 双层名单):
    候选并集(假线名解析失败跳过)∪ 过渡候选成员 = 过渡并集
    (transition_candidates 槽展开;direction 配方键仍读
    opening_recipe_comp,两槽种植相互独立)。"""
    gs = cw4_gs(None, plane=1, round_num=1, node='prep',
                bench=[cw4_bc('花火'), cw4_bc('杂1')])
    strat = _make(gs)
    st = state_of(gs)
    comp = get_comp('专家桑博DOT')
    assert comp is not None
    st.opening_recipe_comp = comp
    st.line_candidates = ('线一', '线二', '线三')
    st.transition_candidates = (('持续伤害', '希儿系'),)

    payload = strat.decision_payload()

    assert payload['direction'] == {
        'locked': False, 'comp': comp.name,
        'candidates': ['线一', '线二', '线三'],
    }
    # 未锁帧统一线内名单 = 候选并集(假线名解析失败跳过)∪ 过渡候选
    # 成员 = 过渡并集;排序序(读口 = sell_line_membership)。
    assert payload['k_members'] == sorted(
        cw_intention._pair_members(('持续伤害', '希儿系')))
    assert payload['k_fallback'] == {'hit': False, 'band': ''}
    # 过渡候选槽照录(嵌套 list 序列化形态);member_rank 二元组 = 过渡
    # 半边全 (1, 候选位次)(假线名解析失败 → 终局半边空,唯一候选 →
    # 位次 1,键集与过渡候选成员并集同集)。
    assert payload['transition_candidates'] == [['持续伤害', '希儿系']]
    assert payload['member_rank'] == dict.fromkeys(
        cw_intention._pair_members(('持续伤害', '希儿系')), (1, 1))


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


# ==================== 产物透传键(pick-margin-telemetry design §2.2;
# ====================  键闭集 7 = 现读 5 + 产物透传 2;window 键已随
# ====================  entry_signals 整体退役)====================

def test_payload_seven_key_closed_set() -> None:
    """payload 键闭集 = 7 键(现读 5 + 产物透传 2;strategy-telemetry.md
    键表口径统一——缺省形态下产物透传两键恒 None 但键恒在;window 键
    已随 entry_signals 整体退役不再产出)。"""
    gs = cw4_gs(None, plane=1, round_num=2, node='prep')
    payload = build_decision_payload(gs, DEFAULT_REGISTRY)
    assert set(payload) == {
        'direction', 'k_members', 'k_fallback',
        'transition_candidates', 'member_rank',
        'pick_margin', 'deploy_margin',
    }


def test_pick_margin_key_from_action_result() -> None:
    """pick_margin = 词表动作字段透传(design §2.1):带 margin 的选卡
    动作实例 → 键值原样;无该字段的动作 → None(非选卡帧不落值)。
    直调 build 传 result 与 bridge 覆写经钩子传入同源。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickInvestEnvParam,
        CwActionPickPartnerParam,
    )
    margin = {'runner_up': '彩虹时代', 'runner_up_total': 0.0,
              'margin': 10.0}
    action = CwActionPickInvestEnvParam(idx=0, reason='probe',
                                        margin=margin)
    gs = cw4_gs(None, plane=1, round_num=2, node='prep')
    payload = build_decision_payload(gs, DEFAULT_REGISTRY, result=action)
    assert payload['pick_margin'] == margin
    # 无 margin 字段的动作(非投资选卡帧)→ None。
    plain = build_decision_payload(
        gs, DEFAULT_REGISTRY,
        result=CwActionPickPartnerParam(idx=0, reason='probe'))
    assert plain['pick_margin'] is None
    # bridge 覆写经钩子消费同源(wrapper 传 result 的通道终点)。
    strat = _make(gs)
    assert strat.decision_payload(action)['pick_margin'] == margin
    assert strat.decision_payload()['pick_margin'] is None


def test_deploy_margin_slot_read_once_and_clear() -> None:
    """deploy_margin 私有槽帧定界(design §2.1 读后清):槽种值 →
    钩子读到原值 + 读后即清(一次性消费,第二次读 = None);槽空帧
    键值 None。清槽挂 bridge 覆写,build 直调不清(模块零写纪律)。"""
    gs = cw4_gs(None, plane=1, round_num=2, node='prep')
    strat = _make(gs)
    st = state_of(gs)
    assert strat.decision_payload()['deploy_margin'] is None   # 槽空帧
    st.deploy_margin = {'diff_empty': True}
    first = strat.decision_payload()
    assert first['deploy_margin'] == {'diff_empty': True}
    assert st.deploy_margin is None, '读后清:槽即清(一次性消费)'
    assert strat.decision_payload()['deploy_margin'] is None
    # build 直调只读不清(零写纪律:清槽不入 decision_payload 模块)。
    st.deploy_margin = {'diff_empty': True}
    assert build_decision_payload(gs, DEFAULT_REGISTRY)[
        'deploy_margin'] == {'diff_empty': True}
    assert st.deploy_margin == {'diff_empty': True}
