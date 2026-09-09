"""统一观察架构·画面 op 基类锁(试点步骤 1;设计正本 =
docs/develop/currency_war/design/统一观察架构-画面op基类设计.md,下称
「架构设计」;§9.1 新锁面 = 基类生命周期锁(六段各一段)+ on_outcome
触发时点轴锁(落地门/发射型各一))。

锁的语义(测试纪律 7 自检;出处 = 架构设计 §5.1/§6.4-R-E):

- **生命周期六段锁**:被测面 = CwScreenOpBase.run_lifecycle 模板的段序与
  段职责——observe(适配器①)→ reconcile(对账)→ decide→act→on_outcome→
  验证(后四段在单动作决策循环内逐动作迭代)。段迹(_lifecycle_trace,
  只增不改)是断言载体;红 = 段被跳/段序颠倒/段职责断线(如 decide 不经
  策略器、act 不经适配器位)。
- **触发时点轴锁**(§6.4-R-E):落地回执门(默认)= progressed 为触发
  前提,未落地不触发(§6.5-1);发射型 = 逐件显式申报(未入申报面注册
  即炸错)+ 点击发射时点触发、与落地解耦。在册发射型成员 = F-3 裁决
  两件:encounter_refresh_used + strategy_refresh_used(遭遇/策略屏
  刷新计数,各屏 op 迁移批接线)。

装配 = ``_cw_helpers.make_prep_round_director`` 单一源(其 harness 已装入
装配点分流桩端口 → run() 经装配点判据走六段新路径,架构设计 §9.1 主门 a)。
执行器注入面 = 模块级 ``PrepActionExecutor`` 构造点桩(与 test_cw_gate_hooks
同款:单轮入口会重建执行器,桩构造点保注入面)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    DeferSpheres,
    LevelUp,
    OpenShop,
    PrepAction,
    StartBattle,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_op_base import (
    EMIT_TRIGGERED_DECLARED,
    OUTCOME_TRIGGER_EMITTED,
    OUTCOME_TRIGGER_LANDED,
)
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)
from test.sr_od.app.currency_war._cw_helpers import make_prep_round_director


def _stub_executor(monkeypatch: pytest.MonkeyPatch, validate_err=None,
                   execute_result: tuple[bool, str] = (True, 'ok')):
    """执行器构造点桩(返回注入面;调用记录挂 returned 对象)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep as pd_mod,
    )
    stub = SimpleNamespace(validate=lambda a: validate_err,
                           execute=lambda a: execute_result,
                           execute_calls=[])
    orig_execute = stub.execute

    def _recording_execute(action):
        stub.execute_calls.append(action)
        return orig_execute(action)

    stub.execute = _recording_execute
    monkeypatch.setattr(pd_mod, 'PrepActionExecutor',
                        lambda op, ctx: stub)
    return stub


def _run_director(test_context, monkeypatch, scripted_actions, *, overlay=None):
    """装配 + 单轮驱动(fast_sleep + running_state 外壳;返回
    (director, match, session, round_result))。"""
    d, match, session = make_prep_round_director(
        test_context, monkeypatch, scripted_actions, overlay=overlay)
    with fast_sleep():
        enter_running_state(test_context)
        try:
            rr = d.run()
        finally:
            reset_running_state(test_context, d)
    return d, match, session, rr


# ==================== 生命周期六段锁(架构设计 §5.1)====================


def test_segment_observe_adapter_feeds_blackboard(
        test_context, monkeypatch) -> None:
    """段1 observe:适配器①产物入黑板(prep_obs_frame 写者白名单 = 入口
    观察装配点,W971 §2),段迹首段 = observe。红 = 观察段被跳过或 payload
    断流(decide 读不到本帧黑板)。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        PrepObservation,
    )

    marker = PrepObservation()
    d, _match, session = make_prep_round_director(
        test_context, monkeypatch, [DeferSpheres()])
    seen: dict = {}

    def _fake_observe(heavy: bool = True, screen=None) -> PrepObservation:
        assert heavy is True, '入口观察 = heavy(ADR-0517 单动作循环契约)'
        session.prep_obs_frame = marker   # 现役写点语义:黑板由观察装配点写
        return marker

    monkeypatch.setattr(d, '_observe', _fake_observe)

    class _SpyStrategy:
        def decide_prep_screen(self, sess, config):
            seen['frame'] = sess.prep_obs_frame
            return [DeferSpheres()]

    _match.strategy = _SpyStrategy()
    with fast_sleep():
        enter_running_state(test_context)
        try:
            d.run()
        finally:
            reset_running_state(test_context, d)
    assert d._lifecycle_trace[0] == 'observe', f'首段须为 observe:{d._lifecycle_trace}'
    assert seen.get('frame') is marker, (
        '适配器① payload 须经黑板流入 decide(观察→决策断线)')


def test_segment_reconcile_consumes_pending_accounts(
        test_context, monkeypatch) -> None:
    """段2 reconcile:上一访问暂存的动作级对账族(pending accts)在入口
    定型帧消费并清空(ADR-0517 决策 8:入口观察即对账)。红 = 对账段被跳
    或消费后不清(跨访问重复对账)。"""
    d, _match, session = make_prep_round_director(
        test_context, monkeypatch, [DeferSpheres()])
    exec_state_of(session).cw_prep_pending_accts = [
        {'key': 'SellBench', 'progressed': True, 'drag_expect': None,
         'equip_expect': None, 'dep_delta': 0, 'dep_pre': None,
         'unit_open': False}]
    consumed: list[dict] = []
    monkeypatch.setattr(
        d, '_v2_post_frame_accounting',
        lambda obs, acct, sess: consumed.append(dict(acct)))
    with fast_sleep():
        enter_running_state(test_context)
        try:
            d.run()
        finally:
            reset_running_state(test_context, d)
    assert 'reconcile' in d._lifecycle_trace, f'段迹缺 reconcile:{d._lifecycle_trace}'
    assert any(c.get('key') == 'SellBench' for c in consumed), (
        f'暂存对账族未被消费:{consumed!r}')
    assert exec_state_of(session).cw_prep_pending_accts == [], (
        '对账族消费后必须清空(防跨访问重复对账)')


def test_segment_decide_consumes_strategy_interface(
        test_context, monkeypatch) -> None:
    """段3 decide:策略消费 = 策略器接口 decide_prep_screen(session, config)
    (契约面 ADR-0583 不动;黑板 = session.prep_obs_frame)。红 = decide 段
    绕开策略器接口。"""
    d, _match, session = make_prep_round_director(
        test_context, monkeypatch, [DeferSpheres()])
    calls: list[tuple[object, object]] = []

    class _SpyStrategy:
        def decide_prep_screen(self, sess, config):
            calls.append((sess, config))
            return [DeferSpheres()]

    _match.strategy = _SpyStrategy()
    with fast_sleep():
        enter_running_state(test_context)
        try:
            d.run()
        finally:
            reset_running_state(test_context, d)
    assert 'decide' in d._lifecycle_trace
    assert len(calls) == 1, f'decide 恰一次,实得 {len(calls)}'
    sess_arg, _cfg_arg = calls[0]
    assert sess_arg is session, 'decide 输入 = 对局 session(黑板宿主)'


def test_segment_act_routes_action_port(
        test_context, monkeypatch) -> None:
    """段4 act:注入动作适配器在场 → 意图经适配器位落地(§6.2 端口),
    回执驱动结束判定;缺省适配器 = 现役点击链(本锁以注入替位验证端口
    分派面)。红 = act 段绕开适配器位直调执行器。"""
    d, _match, session = make_prep_round_director(
        test_context, monkeypatch, [StartBattle()])
    _stub_executor(monkeypatch)
    port_calls: list[tuple[object, PrepAction]] = []

    class _PortStub:
        def execute(self, op, action):
            port_calls.append((op, action))
            return True, '经端口落地'

    d._action_adapter = _PortStub()
    with fast_sleep():
        enter_running_state(test_context)
        try:
            rr = d.run()
        finally:
            reset_running_state(test_context, d)
    assert 'act' in d._lifecycle_trace
    assert len(port_calls) == 1 and isinstance(port_calls[0][1], StartBattle), (
        f'意图须恰一次经动作适配器位:{port_calls!r}')
    assert d._executor.execute_calls == [], (
        '适配器在场时执行器不得被直调(端口分派失效)')
    assert '出战' in (rr.status or ''), '适配器回执须驱动结束判定'


def test_segment_on_outcome_fires_registered_hook(
        test_context, monkeypatch) -> None:
    """段5 on_outcome:落地登记注册表按意图类型触发(本 op 在册两件 =
    经验期望账本推进;OpenShop 件经注册表收到执行回执)。红 = 注册表
    断线(登记件不再随动作落地推进)。"""
    d, _match, session = make_prep_round_director(
        test_context, monkeypatch, [OpenShop(read_only=True)])
    fired: list[str] = []
    monkeypatch.setattr(d, '_xp_apply_buy_clicks',
                        lambda detail: fired.append(detail))
    with fast_sleep():
        enter_running_state(test_context)
        try:
            rr = d.run()
        finally:
            reset_running_state(test_context, d)
    assert 'on_outcome' in d._lifecycle_trace
    assert fired == ['read_only 读牌完成'], (
        f'OpenShop 落地登记件须恰触发一次(收到回执 detail):{fired!r}')
    assert '交回外循环重识别' in (rr.status or ''), '终结出口语义不受收编影响'


def test_segment_verify_consumes_outcome_and_recovers(
        test_context, monkeypatch) -> None:
    """段6 验证:执行侧验证回执消费——progressed=False → 恢复原语一次 +
    交回外循环(fail-stop,契约 §2);段迹收尾 = verify。红 = 回执消费/
    失败恢复编排断线。"""
    d, _match, session = make_prep_round_director(
        test_context, monkeypatch, [StartBattle()])
    _stub_executor(monkeypatch, execute_result=(False, '验证失败(备战标识未消失)'))
    recoveries: list[bool] = []
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep as pd_mod,
    )
    monkeypatch.setattr(pd_mod, 'try_recovery',
                        lambda op_, ctx_: recoveries.append(True) or ('close', True))
    with fast_sleep():
        enter_running_state(test_context)
        try:
            rr = d.run()
        finally:
            reset_running_state(test_context, d)
    assert d._lifecycle_trace[-1] == 'verify', f'末段须为 verify:{d._lifecycle_trace}'
    assert len(recoveries) == 1, '验证失败须恰编排一次恢复原语'
    assert '验证失败' in (rr.status or '') and '交回外循环' in (rr.status or '')


# ==================== on_outcome 触发时点轴锁(架构设计 §6.4-R-E)====================


def test_outcome_gate_fires_only_on_landed(
        test_context, monkeypatch) -> None:
    """落地回执门(默认型;§6.5-1 未落地不计数):LevelUp 登记件 = 经验
    期望账本推进,验证失败(progressed=False)不触发,执行落地才触发。
    红 = 登记件在未落地帧被误触发(「未落地不计数」口径破缺;本锁是
    触发时点轴的落地门半边)。"""
    d, _match, session = make_prep_round_director(
        test_context, monkeypatch, [LevelUp()])
    fired: list[bool] = []
    monkeypatch.setattr(d, '_xp_apply_levelup', lambda: fired.append(True))
    _stub = _stub_executor(monkeypatch)
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep as pd_mod,
    )
    monkeypatch.setattr(pd_mod, 'try_recovery',
                        lambda op_, ctx_: ('close', True))
    with fast_sleep():
        enter_running_state(test_context)
        try:
            # 第一轮:验证失败(未落地)→ 落地门不得触发
            _stub.execute = lambda a: (False, 'x')
            d.run()
            assert fired == [], '未落地不得触发落地回执门登记件(§6.5-1)'
            # 第二轮:执行落地 → 恰触发一次
            _stub.execute = lambda a: (True, 'ok')
            d.run()
        finally:
            reset_running_state(test_context, d)
    assert fired == [True], f'落地帧恰触发一次,实得 {fired!r}'


def test_outcome_axis_emit_requires_declaration_and_fires_at_emission(
        test_context, monkeypatch) -> None:
    """发射型半边(§6.4-R-E 逐件显式申报):①未入申报面的发射型注册
    直接炸错(禁静默选型);②在册成员(encounter_refresh_used,遭遇刷新
    计数)注册后于点击发射时点触发,与落地解耦(随点击置位不等验效,
    §6.5-4);③默认触发型 = 落地回执门;④申报面在册 = F-3 裁决两件。
    红 = 发射型可静默注册 / 发射型被落地门误闸 / 在册成员漂移。"""
    d, _match, session = make_prep_round_director(
        test_context, monkeypatch, [DeferSpheres()])

    class _AnyAction(PrepAction):
        pass

    # ①申报门:未申报名注册发射型 = 炸错
    with pytest.raises(ValueError, match='申报'):
        d.register_outcome_hook(_AnyAction, lambda _o: None,
                                trigger=OUTCOME_TRIGGER_EMITTED,
                                name='undeclared_member')
    # ②在册成员合法注册 + 发射时点触发(与落地解耦:不看 progressed)
    fired: list[str] = []
    d.register_outcome_hook(_AnyAction,
                            lambda o: fired.append(o.evidence),
                            trigger=OUTCOME_TRIGGER_EMITTED,
                            name='encounter_refresh_used')
    assert fired == [] and d.fire_emit_hooks(
        _AnyAction(), evidence='refresh_click') == 1
    assert fired == ['refresh_click'], (
        f'发射型须在发射时点携发射证据触发:{fired!r}')
    # ③默认触发型 = 落地回执门(注册 API 不显式点名 = 落地门,禁静默发射型)
    d.register_outcome_hook(_AnyAction, lambda _o: None, name='plain_landed')
    assert all(spec.trigger == OUTCOME_TRIGGER_LANDED
               for spec in d._outcome_hooks[_AnyAction]
               if spec.name == 'plain_landed')
    # ④在册申报面 = F-3 裁决两件(架构设计 §6.4-R-E「在册成员两件(F3)」
    #   = 遭遇 + 策略屏刷新计数)。钉成员在场不变量而非全集快照:新增成员
    #   走「先改申报面再登记」正门(申报门①炸错兜底),本锁红 = 在册
    #   成员被移除/更名(面漂移)
    assert {'encounter_refresh_used',
            'strategy_refresh_used'} <= set(EMIT_TRIGGERED_DECLARED)
