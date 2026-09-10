"""统一观察架构·画面 op 基类锁(试点步骤 1;设计正本 =
docs/develop/currency_war/design/统一观察架构-画面op基类设计.md,下称
「架构设计」;§9.1 新锁面 = 基类生命周期锁(五段各一段)+ on_outcome
单一发射口锁)。

锁的语义(测试纪律 7 自检;出处 = 架构设计 §5.1/§6.4 v12/T-223 终裁):

- **生命周期五段锁**:被测面 = CwScreenOpBase.run_lifecycle 模板的段序与
  段职责——observe(适配器①)→ reconcile(对账)→ decide→act→on_outcome
  (后三段在单动作决策循环内逐动作迭代)。段迹(_lifecycle_trace,
  只增不改)是断言载体;红 = 段被跳/段序颠倒/段职责断线(如 decide 不经
  策略器、act 不经适配器位)。
- **验证段废除锁**(用户裁定 2026-09-10:「动作 op 只管机械执行,禁止做
  任何验证,也禁止在画面 op 做验证。如果观察正确,动作 op 没生效,那就
  是动作 op 有 bug,不应该为了 bug 增加验证这种复杂度」):生命周期模板
  无第六段——段迹止于 on_outcome,基类源面无「六段」/「verify」残段;
  落地判定完全归观察侧 reconcile 对账(T-223 最严读法:适配器只机械
  执行,成败/落地回执退役,§6.2/§6.5-1),不是生命周期段;动作未生效
  的处置 = 修动作适配器本身,禁验证+重试兜底。红 = 验证段复活。
- **单一发射口锁**(§6.4 v12;T-223 用户终裁 2026-09-10 最严读法):
  两 fire 口(落地回执门/发射型)合并为单一发射口 ``fire_outcome_hooks``
  ——发射即触发,与落地与否解耦;落地回执门(原 OUTCOME_TRIGGER_LANDED
  型)与端口回执 ``(progressed, detail)`` 退役,「未落地不计数」防线由
  观察侧 reconcile 对账承接(§6.5-1,纠偏/缺陷台账)。登记件逐件申报面
  = EMIT_TRIGGERED_DECLARED(原「选型闸」随两型制退役,逐件发射语义
  申报纪律保留:未入申报面注册即炸错)。在册成员 = 遭遇/策略屏刷新计数
  (F-3 裁决两件,口径续行)+ 备战经验账本两通道(CwScreenPrep 在册)。

装配 = ``_cw_helpers.make_prep_round_director`` 单一源(其 harness 已装入
装配点分流桩端口 → run() 经装配点判据走五段新路径,架构设计 §9.1 主门 a)。
五段模板锁(段数/段序/无验证段)用本文件内最小桩子类直驱 run_lifecycle,
不经备战 op——其决策循环的迭代/失败处置语义归备战修复批辖域,不属基类
模板锁面(段1-段5 职责锁仍经备战 op 走真实装配)。
执行器注入面 = 模块级 ``PrepActionExecutor`` 构造点桩(与 test_cw_gate_hooks
同款:单轮入口会重建执行器,桩构造点保注入面)。
"""
from __future__ import annotations

import inspect
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
    CwScreenOpBase,
)
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)
from test.sr_od.app.currency_war._cw_helpers import make_prep_round_director


def _stub_executor(monkeypatch: pytest.MonkeyPatch, validate_err=None,
                   detail: str = 'ok'):
    """执行器构造点桩(返回注入面;调用记录挂 returned 对象)。

    T-223:execute 机械执行无返回;机械摘要经 last_detail 旁路
    (与生产 PrepActionExecutor 同形态)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep as pd_mod,
    )
    stub = SimpleNamespace(validate=lambda a: validate_err,
                           last_detail=detail,
                           execute_calls=[])
    stub.execute = lambda action: stub.execute_calls.append(action)
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


# ==================== 生命周期五段锁(架构设计 §5.1)====================


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
    或消费后不清(跨访问重复对账)。acct 形态 = key-only(批3a:原
    acct['progressed'] 字段随 T-223 端口回执退役)。"""
    d, _match, session = make_prep_round_director(
        test_context, monkeypatch, [DeferSpheres()])
    exec_state_of(session).cw_prep_pending_accts = [
        {'key': 'SellBench', 'drag_expect': None,
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
    """段4 act:注入动作适配器在场 → 意图经适配器位机械执行(§6.2 端口,
    T-223 执行无返回),结束判定 = 发出即终结(出战);缺省适配器 = 现役
    点击链(本锁以注入替位验证端口分派面)。红 = act 段绕开适配器位直调
    执行器,或端口回执形态复活。"""
    d, _match, session = make_prep_round_director(
        test_context, monkeypatch, [StartBattle()])
    _stub_executor(monkeypatch)
    port_calls: list[tuple[object, PrepAction]] = []

    class _PortStub:
        def execute(self, op, action):
            port_calls.append((op, action))   # 机械执行,无返回(T-223)

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
    assert '出战' in (rr.status or ''), '发出即终结:出战发射完交回外循环战斗分支'


def test_segment_on_outcome_fires_registered_hook(
        test_context, monkeypatch) -> None:
    """段5 on_outcome:落地登记注册表按意图类型触发(本 op 在册两件 =
    经验期望账本推进;OpenShop 件经注册表收到机械摘要 detail)。红 = 注册
    表断线(登记件不再随动作发射推进)。"""
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
        f'OpenShop 发射登记件须恰触发一次(收到机械摘要 detail):{fired!r}')
    assert '交回外循环重识别' in (rr.status or ''), '终结出口语义不受收编影响'


class _FiveSegStub(CwScreenOpBase):
    """五段模板桩:子类钩子最小实现(基类模板管 observe/reconcile 两段,
    本桩决策循环管后三段),供模板段序锁直驱 run_lifecycle。"""

    def __init__(self, ctx) -> None:
        CwScreenOpBase.__init__(self, ctx, op_name='五段模板桩')

    def lifecycle_observe(self
                          ) -> tuple[dict, object | None]:
        return {'frame': 'stub'}, None

    def lifecycle_reconcile(self, payload: dict) -> None:
        return None

    def lifecycle_decision_cycle(self, payload: dict
                                 ) -> object:
        self._lifecycle_mark('decide')
        self._lifecycle_mark('act')
        self._lifecycle_mark('on_outcome')
        return self.round_success('五段走完')


def test_lifecycle_template_five_segments_exact_trace(
        test_context, monkeypatch) -> None:
    """五段模板锁(用户裁定 2026-09-10 验证段废除):run_lifecycle 一次
    访问的段迹恰为 observe→reconcile→decide→act→on_outcome 五段,无第六
    段、无验证残迹(落地判定归观察侧 reconcile,T-223/§6.2,非生命周期
    段)。红 = 验证段复活(段迹再现第六段)或段序漂移。"""
    op = _FiveSegStub(test_context)
    with fast_sleep():
        enter_running_state(test_context)
        try:
            rs = op.run_lifecycle()
        finally:
            reset_running_state(test_context, op)
    assert op._lifecycle_trace == ['observe', 'reconcile', 'decide', 'act',
                                   'on_outcome'], (
        f'生命周期模板须恰五段(验证段已废除,用户裁定 2026-09-10):'
        f'{op._lifecycle_trace}')
    assert rs.is_success, '模板走完 = 正常交回'


def test_lifecycle_base_source_free_of_verify_segment() -> None:
    """验证段废除·源面锁(同上裁定):基类模块源无「六段」表述、无
    'verify' 段迹字面。红 = 源面残段(文档表述/段迹字样回潮)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_op_base as base_mod,
    )
    src = inspect.getsource(base_mod)
    assert '六段' not in src, '基类源面残留「六段」表述(验证段已废除)'
    assert "'verify'" not in src, '基类源面残留 verify 段迹字面(验证段已废除)'


# ==================== on_outcome 单一发射口锁(架构设计 §6.4 v12/T-223)====================


def test_outcome_hooks_fire_at_emission_single_port(
        test_context, monkeypatch) -> None:
    """单一发射口(§6.4 v12;T-223 最严读法):登记件在动作发射时点触发,
    与落地与否解耦——执行器机械执行无成败回执,发射即登记恰一次(原落地
    回执门「未落地不计数」防线由观察侧 reconcile 对账承接,§6.5-1;原门
    本体与端口回执退役,墓碑 = 架构设计 §6.4)。红 = 发射登记件断线或
    双计。"""
    d, _match, session = make_prep_round_director(
        test_context, monkeypatch, [LevelUp()])
    fired: list[int] = []
    monkeypatch.setattr(d, '_xp_apply_levelup',
                        lambda: fired.append(1))
    _stub = _stub_executor(monkeypatch)
    with fast_sleep():
        enter_running_state(test_context)
        try:
            d.run()
        finally:
            reset_running_state(test_context, d)
    assert fired == [1], (
        f'发射时点恰触发一次(单一发射口,与落地解耦),实得 {fired!r}')
    assert len(_stub.execute_calls) == 1, '机械执行恰一次(登记跟随发射)'


def test_outcome_registry_emission_declaration_and_single_port(
        test_context, monkeypatch) -> None:
    """逐件申报面 + 单一发射口(§6.4 v12):①未入申报面的登记直接炸错
    (逐件显式申报,禁静默新增);②登记后经单一发射口在发射时点触发,
    携发射证据;③注册 API 无触发时点选型参数(两型制随 T-223 退役,
    落地回执门/OUTCOME_TRIGGER 常量墓碑化);④申报面在册 = F-3 裁决两件
    + 备战经验账本两通道。红 = 静默新增登记件 / 发射口断线 / 选型轴复活。"""
    d, _match, session = make_prep_round_director(
        test_context, monkeypatch, [DeferSpheres()])

    class _AnyAction(PrepAction):
        pass

    # ①申报门:未申报名注册 = 炸错
    with pytest.raises(ValueError, match='申报'):
        d.register_outcome_hook(_AnyAction, lambda _o: None,
                                name='undeclared_member')
    # ②在册成员合法注册 + 单一发射口发射时点触发(携发射证据)
    fired: list[str] = []
    d.register_outcome_hook(_AnyAction,
                            lambda o: fired.append(o.evidence),
                            name='encounter_refresh_used')
    assert fired == [] and d.fire_outcome_hooks(
        _AnyAction(), evidence='refresh_click') == 1
    assert fired == ['refresh_click'], (
        f'发射登记件须在发射时点携发射证据触发:{fired!r}')
    # ③选型轴退役:注册 API 无 trigger 参数(触发时点轴两型制已随 T-223
    #   退役,登记件一律发射型;OUTCOME_TRIGGER_LANDED/EMITTED 常量与
    #   fire_emit_hooks 双口不再存在——红 = 选型轴复活)
    import sr_od.application.currency_war.operations.cw_screen.\
        cw_screen_op_base as base_mod
    sig = inspect.signature(base_mod.CwScreenOpBase.register_outcome_hook)
    assert 'trigger' not in sig.parameters, (
        '注册 API 不得再收触发时点选型参数(两型制退役,T-223)')
    assert not hasattr(base_mod, 'OUTCOME_TRIGGER_LANDED'), (
        '落地回执门常量须已退役(T-223 最严读法)')
    assert not hasattr(base_mod, 'fire_emit_hooks'), (
        '两 fire 口须已合并单一发射口(T-223)')
    # ④在册申报面 = F-3 裁决两件(遭遇 + 策略屏刷新计数,口径续行)
    #   + 备战经验账本两通道(批3a 入册)。钉成员在场不变量而非全集快照:
    #   新增成员走「先改申报面再登记」正门(申报门①炸错兜底),本锁红 =
    #   在册成员被移除/更名(面漂移)
    assert {'encounter_refresh_used', 'strategy_refresh_used',
            'xp_ledger_levelup', 'xp_ledger_buy_clicks'} \
        <= set(EMIT_TRIGGERED_DECLARED)
