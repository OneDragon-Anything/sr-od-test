"""CwStrategy 捕获缝锁面(显式 14 入口闭集包裹 + in-flight 守卫 + 信封契约)。

被测 = src/sr_od/application/currency_war/strategies/impl/cw_strategy.py;
设计出处 = 策略遥测捕获缝设计(捕获缝 / 信封与槽 / 信封键闭集 /
测试锁面);遥测正本 = strategy-docs/strategy-telemetry.md。
测试零真实副作用:sink 注入用内存假闭包;落盘面由
test_strategy_telemetry.py 以 tmp_path 根承接。
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_decision_ctx import (
    reset_decision_tag,
    take_decision_tag,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwAction,
    CwActionObsParam,
    CwActionPickPartnerParam,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    DECISION_ENTRY_NAMES,
    CwStrategy,
    set_decision_sink,
)
from sr_od.application.currency_war.strategies.impl.flow import CwFlowStrategy
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)


def _probe_action() -> CwActionPickPartnerParam:
    """探针动作(带归因字段,供 emitted 摘要断言)。"""
    return CwActionPickPartnerParam(idx=0, reason='probe', route_tag='probe_tag')


class _ProbeStrategy(CwStrategy):
    """最小具现探针:14 入口全部最小实现(备战入口返回空动作形态,供
    清槽分支);包裹面在类创建时经 ``__init_subclass__`` 挂上。"""

    STRATEGY_ID = 'probe'

    def decide_prep_screen(self) -> CwAction:
        return CwActionObsParam(scope='outer_loop', reason='probe')

    def decide_shop_action(self) -> CwAction:
        return _probe_action()

    def decide_invest_strategy(self) -> CwAction:
        return _probe_action()

    def decide_invest_env(self) -> CwAction:
        return _probe_action()

    def decide_supply(self) -> CwAction:
        return _probe_action()

    def decide_encounter(self) -> CwAction:
        return _probe_action()

    def decide_megastar(self) -> CwAction:
        return _probe_action()

    def decide_partner(self) -> CwAction:
        return _probe_action()

    def decide_planner(self) -> CwAction:
        return _probe_action()

    def decide_star_tome(self) -> CwAction:
        return _probe_action()

    def decide_wish_trial(self) -> CwAction:
        return _probe_action()

    def decide_box_card(self) -> CwAction:
        return _probe_action()

    def decide_fortune(self) -> CwAction:
        return _probe_action()

    def decide_expert_invite(self) -> CwAction:
        return _probe_action()


class _SuperChainStrategy(_ProbeStrategy):
    """decide_partner 覆写后 super() 复用基类实现(in-flight 守卫场景,
    实证同型 = MandateV1Strategy.decide_shop_action 末行 super() 调用)。"""

    def decide_partner(self) -> CwAction:
        return super().decide_partner()


class _PayloadBoomStrategy(_ProbeStrategy):
    """payload 钩子必抛场景(异常降级 {} 的降级分支)。"""

    def decision_payload(self) -> dict:
        raise RuntimeError('payload boom')


class _DriverProbeStrategy(_ProbeStrategy):
    """序列驱动器形态(方法名不在闭集;返回 list;内层单动作核在闭集内)。"""

    def decide_shop_screen(self) -> list:
        return [self.decide_shop_action()]


def _make(cls: type[CwStrategy]) -> CwStrategy:
    return cls(GameState(schema_version=GAME_STATE_SCHEMA_VERSION),
               SimpleNamespace(strategy_seed=None))


@pytest.fixture
def capture_sink() -> list[dict]:
    """内存假 sink(槽注入 + teardown 摘除;槽是进程级,防跨测试残留)。"""
    records: list[dict] = []
    set_decision_sink(records.append)
    yield records
    set_decision_sink(None)
    reset_decision_tag()


def test_envelope_closed_set_and_dtag_format(
        capture_sink: list[dict]) -> None:
    """信封键闭集(8 键,无 run_id——run_id 归 sink 落盘前补齐)+ dtag
    格式 <strategy_id>:<dseq> + emitted 恰一动作三键 + payload 缺省 {}。"""
    strat = _make(_ProbeStrategy)
    result = strat.decide_partner()
    assert isinstance(result, CwActionPickPartnerParam)   # 返回值原样透传
    assert len(capture_sink) == 1
    env = capture_sink[0]['envelope']
    assert set(env) == {'strategy_id', 'schema_version', 'dseq', 'dtag',
                        'entry', 'node', 'ts', 'emitted'}
    assert env['strategy_id'] == 'probe'
    assert env['entry'] == 'decide_partner'
    assert env['dseq'] == 1
    assert env['dtag'] == 'probe:1'
    assert env['node'] is None   # 节点未观察 → null 帧
    datetime.fromisoformat(env['ts'])   # ISO8601 可解析
    assert env['emitted'] == [{'op': 'CwActionPickPartnerParam',
                               'reason': 'probe', 'route_tag': 'probe_tag'}]
    assert capture_sink[0]['payload'] == {}   # 基类缺省钩子零载荷
    strat.decide_partner()   # dseq 按实例自增
    assert capture_sink[1]['envelope']['dtag'] == 'probe:2'


def test_envelope_node_reads_gs_node(capture_sink: list[dict]) -> None:
    """node = gs.node 现读三键(plane/round_num/kind;键名与 journal
    round_num 对齐)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.node, NodeKey(plane=2, round_num=3, kind='prep'),
               sig=ChannelSig(family='obs', actor='TestCapture'))
    strat = _ProbeStrategy(gs, SimpleNamespace(strategy_seed=None))
    strat.decide_partner()
    assert capture_sink[0]['envelope']['node'] == {
        'plane': 2, 'round_num': 3, 'kind': 'prep'}


def test_closed_set_wrap_face() -> None:
    """显式闭集包裹面:闭集 = ABC 抽象入口全集(14);decide_shop_screen
    驱动器不被包;在役类(MandateV1)闭集入口全部已包。"""
    assert len(DECISION_ENTRY_NAMES) == 14
    assert set(CwStrategy.__abstractmethods__) == DECISION_ENTRY_NAMES
    assert not getattr(CwFlowStrategy.decide_shop_screen,
                       '_decision_recorded', False)
    assert not getattr(MandateV1Strategy.decide_shop_screen,
                       '_decision_recorded', False)
    for name in DECISION_ENTRY_NAMES:
        assert getattr(getattr(MandateV1Strategy, name),
                       '_decision_recorded', False), name


def test_driver_not_wrapped_inner_actions_recorded(
        capture_sink: list[dict]) -> None:
    """驱动器(list 返回)自身零记录;内层闭集入口逐动作产记录
    (capture-store §2 驱动器语义:装 sink 即逐动作产记录)。"""
    strat = _make(_DriverProbeStrategy)
    out = strat.decide_shop_screen()
    assert isinstance(out, list) and len(out) == 1
    assert [r['envelope']['entry'] for r in capture_sink] == \
        ['decide_shop_action']


def test_inflight_super_chain_single_record(
        capture_sink: list[dict]) -> None:
    """super() 复用基类实现 → 恰一条记录(内层直通:不记录、不重复自增)。"""
    strat = _make(_SuperChainStrategy)
    result = strat.decide_partner()
    assert isinstance(result, CwActionPickPartnerParam)
    assert len(capture_sink) == 1
    assert capture_sink[0]['envelope']['dseq'] == 1   # 仅外层自增一次
    assert capture_sink[0]['envelope']['entry'] == 'decide_partner'


def test_payload_hook_exception_degrades_to_empty(
        capture_sink: list[dict]) -> None:
    """payload 钩子异常 → {} 降级,decide 返回值不受影响。"""
    strat = _make(_PayloadBoomStrategy)
    result = strat.decide_partner()
    assert isinstance(result, CwActionPickPartnerParam)
    assert capture_sink[0]['payload'] == {}


def test_sink_exception_does_not_poison_return() -> None:
    """sink 抛异常 → decide 返回值原样;后续槽操作照常执行(守卫分立)。"""
    def _boom(record: dict) -> None:
        raise RuntimeError('sink boom')

    set_decision_sink(_boom)
    try:
        strat = _make(_ProbeStrategy)
        result = strat.decide_partner()
        assert isinstance(result, CwActionPickPartnerParam)
        assert take_decision_tag() == 'probe:1'   # sink 失败不阻断盖槽
    finally:
        set_decision_sink(None)
        reset_decision_tag()


def test_empty_action_clears_slot_and_action_sets_tag(
        capture_sink: list[dict]) -> None:
    """kernel 槽分支:空动作(CwActionObsParam)清槽防陈旧 dtag;
    非空动作盖 dtag,与信封同值。"""
    strat = _make(_ProbeStrategy)
    strat.decide_prep_screen()   # 空动作形态
    assert take_decision_tag() is None
    strat.decide_partner()
    assert take_decision_tag() == capture_sink[1]['envelope']['dtag']
    assert take_decision_tag() is None   # take 读后清
    assert capture_sink[1]['envelope']['dtag'] == 'probe:2'


def test_pure_unit_zero_file_side_effect(tmp_path) -> None:
    """纯单测(不注入 sink)= 零文件副作用:recorder 根重定向后 decide,
    根下零 strategy/ 目录(槽缺省 None = 零写)。"""
    from sr_od.application.currency_war.telemetry.state import (
        reset_run_state,
        set_recorder_replay_dir,
        start_run,
    )

    reset_run_state()
    set_recorder_replay_dir(tmp_path)
    try:
        start_run()
        _make(_ProbeStrategy).decide_partner()
        assert not (tmp_path / 'strategy').exists()
    finally:
        set_recorder_replay_dir(None)
        reset_run_state()


def test_legacy_signature_payload_override_degrades(
        capture_sink: list[dict]) -> None:
    """钩子兼容形(词表动作字段通道):wrapper 传
    result 调钩子,第三方**旧签名覆写**(无 result 形参)收到多余实参
    TypeError → 走既有异常降级 {} 通道,决策返回值零毒化、不炸——
    基类缺省参兼容形把破坏面收窄到「载荷降级」而非「决策崩溃」。"""

    class _LegacyOverrideStrategy(_ProbeStrategy):
        """旧签名覆写(返回非空 dict,证明降级非异常测试副产物)。"""

        def decision_payload(self) -> dict:
            return {'legacy': True}

    strat = _make(_LegacyOverrideStrategy)
    result = strat.decide_partner()
    assert isinstance(result, CwActionPickPartnerParam)
    assert capture_sink[0]['payload'] == {}, \
        '旧签名覆写 → TypeError → 降级 {}(不误吞覆写值,也不毒化决策)'
