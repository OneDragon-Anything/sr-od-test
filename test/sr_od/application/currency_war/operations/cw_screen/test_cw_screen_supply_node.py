"""补给节点 op 测试(src 镜像 = operations/cw_screen/cw_screen_supply_node.py)。

两块测试面:
- 利息接线(镜像来源 C 计数刻;迭代 T-27 公司契约利息累计触发设计 v2.4
  复裁版 §2.5 来源 C + §4.8②):
  - 常规形态(备战帧已锚本节点 = 形态门开)领取完成刻推算计数(基座 =
    备战帧 gs.gold 观察 = 领取前真值);
  - 「自动弹」形态(本节点首次锚定发生在补给屏,形态门关)宁缺零计数;
    接管局形态同归宁缺;
  - 刷新分支/对照闸拒绝路径不经计数体 = 天然防补给 op 重入双计;
  - 局外兜底路径(match 缺席)零计数。
- 决策链接线行为面(supply-decision-wiring 迭代 §2.6 新增 1-4/6;存量
  三条行为测试住 test_obs_arch_event_screens.py〔超限只读〕,本文件按
  src 镜像规范承接增量):
  - 空候选 = 零点击终结零派发(禁盲选,§2.1);
  - 守卫①②:词表外/None 具名 round_fail 零盲发、idx 越界 AssertionError
    禁钳位,均派发前零点击(§2.3);
  - 对照闸拒绝防线:重调仍建议刷 → 实机 round_fail(计入外循环重派
    上限)/ sim 零点击终结零派发(§2.2,桩驱动);
  - sim 两态:刷新分支 = area 点击端口触发后端 ``_supply_refresh``
    (left−1 + 选项重掷落容器);pick 流 = 真 SimBackend + 真策略装配
    (装配缝 = test/harness/sim_backend_runner.run_sim_full_match 同源)
    → decide_supply 被调、owned 内容载荷分支入账写行、chosen_supply 写行、
    零节点推进(选完回备战弹店,推进归出战;占位池 char 恒空 → 单位入账
    分支结构性零写,design §2.2 申报)。

测试纪律:不连真游戏(fixture harness + fast_sleep 包 op 执行)、零真实
副作用(journal 走内存 sink,telemetry run 态测试复位)、共享对象改属性
必经 monkeypatch、串行。
"""
from __future__ import annotations

import random
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from test.harness.sim_backend_runner import (
    SimControllerStub,
    capture_state_journal,
    freeze_cw_module_time,
)
from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

from sr_od.application.currency_war.kernel import cw_game_state as gs_mod
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_start_battle_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    DEFAULT_INTEREST_CAP,
    interest,
)
from sr_od.application.currency_war.kernel.cw_events import (
    SupplyOption,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    game_state_of,
    report_node_advance,
)
from sr_od.application.currency_war.kernel.cw_screen_report.supply_node import (
    CwScreenSupplyNodeObs,
    report_screen_supply_node_obs,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickSupplyParam,
    CwActionRefreshSupplyParam,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
    CwScreenSupplyNode,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_SETTLE,
    SCREEN_SHOP,
    SCREEN_SUPPLY,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig
from sr_od.application.currency_war.telemetry import state as tel_state

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_FRAME = object()   # 稳定帧哨兵(screenshot 桩产物;读链桩只验传递不断言内容)


def _bare_op(test_context, monkeypatch, *, prep_anchored: bool):
    """补给 op 裸实例(计数体单元面;形态门 = 观察轮锚定 token 判的
    产物载体,读屏链归流程测试辖)。"""
    session = cw4_session()
    monkeypatch.setattr(test_context, 'cw_match', session, raising=False)
    op = CwScreenSupplyNode.__new__(CwScreenSupplyNode)
    op.ctx = test_context
    op._prep_anchored = prep_anchored
    gs = game_state_of(session)
    gs.observe(gs.active_env, '公司契约', sig=_SIG_OBS)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=_SIG_OBS)
    gs.observe(gs.gold, 100, sig=_SIG_OBS)
    return op, session


def test_source_c_pick_completion_counting(test_context, monkeypatch) -> None:
    """常规形态领取完成刻计数(T-27 设计 §4.8②):基座 = 备战帧 gs.gold
    观察 100 → 推算息 5(缺省 cap 满档,现算期望);cap/flat 推算单一源
    = estimate_node_interest;推算支与来源 A 面板读数无耦合(纯公式)。
    match 面 = 生产消费形态(gs 宿主)。"""
    op, session = _bare_op(test_context, monkeypatch, prep_anchored=True)
    gs = game_state_of(session)
    op._count_interest_after_pick(SimpleNamespace(gs=gs))
    assert gs.effects.interest_earned == interest(
        100, DEFAULT_INTEREST_CAP), '领取完成刻推算入账(基座 100,现算期望)'


def test_source_c_auto_popup_gate_counts_nothing(
        test_context, monkeypatch) -> None:
    """「自动弹」形态宁缺(T-27 设计 v2.4 复裁:无备战帧形态门关):
    基座不取(哪怕 gs.gold 在册——自动弹形态其值非本节点备战帧观察,
    禁用)→ 零计数;接管局形态同归宁缺口径。"""
    op, session = _bare_op(test_context, monkeypatch, prep_anchored=False)
    gs = game_state_of(session)
    op._count_interest_after_pick(SimpleNamespace(gs=gs))
    assert gs.effects.interest_earned == 0, '自动弹形态宁缺零计数'


def test_source_c_out_of_match_counts_nothing(
        test_context, monkeypatch) -> None:
    """局外兜底路径(match 缺席)零计数(容器不可得,禁猜)。"""
    op, session = _bare_op(test_context, monkeypatch, prep_anchored=True)
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    gs = game_state_of(session)
    op._count_interest_after_pick(None)
    assert gs.effects.interest_earned == 0, '局外路径零计数'


# ==================== 决策链接线行为面(实机态;supply-decision-wiring)====


def _make_supply_live(test_context, monkeypatch, *, pick, opts,
                      anchor=None, seed_left: int | None = None):
    """补给 op 实机态装配(真类实例,无 sim 后端):门桩 + 选项读链桩 +
    锚读桩 + 机械派发半桩 + controller 点击记录。
    ``pick`` = decide_supply 返回值或可调用(拒绝重调用例传迭代器);
    ``anchor`` = ``_read_refresh_anchor`` 桩返回值(默认 None = 锚读缺);
    ``seed_left`` = 观察前预写容器剩余读数(残值形态构造,None = 不预写)。
    返回 (op, match, session, stub, envs, clicks)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_action_registry,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node as sn,
    )

    session = cw4_session()
    _decide = pick if callable(pick) else (lambda: pick)
    _calls: list = []

    def _decide_counting():
        _calls.append(1)
        return _decide()

    match = SimpleNamespace(
        session=session,
        strategy=SimpleNamespace(decide_supply=_decide_counting))
    match.gs = game_state_of(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    if seed_left is not None:
        # 残值形态构造:观察前容器已持上次访问读数(读缺跳写语义 = 本次
        # 观察不覆盖,残值真实存在——design §2.2 对照闸残值分量)。
        match.gs.observe(match.gs.supply_refresh_left, seed_left,
                         sig=_SIG_OBS)
    op = CwScreenSupplyNode(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(True))
    monkeypatch.setattr(sn, 'read_supply_options',
                        lambda ctx, screen: list(opts))
    monkeypatch.setattr(op, '_read_refresh_anchor', lambda screen: anchor)
    # 节点条锚定桩(读不得 = 跳过;锚定接线测试归存量 behavior 面)
    monkeypatch.setattr(op, '_read_node_bar', lambda screen: None)

    class _StubPickOp:
        def __init__(self) -> None:
            self.executed = 0

        def execute(self) -> bool:
            self.executed += 1
            return True

    stub = _StubPickOp()
    envs: list = []
    monkeypatch.setattr(cw_action_registry, 'action_op_for',
                        lambda act, ctx, env: (envs.append(env), stub)[1])
    clicks: list = []
    monkeypatch.setattr(test_context.controller, 'mouse_move',
                        lambda p, **k: None, raising=False)
    monkeypatch.setattr(test_context.controller, 'click',
                        lambda p, **k: clicks.append((p.x, p.y)),
                        raising=False)
    return op, match, session, stub, envs, clicks


def test_supply_empty_options_zero_click_terminal(
        test_context, monkeypatch) -> None:
    """空候选零点击终结测试(§2.1):候选读缺(obs.options 空)→ 零点击
    零派发 round_success 终结交回重读。红 = 盲选派发回潮(CARD_BODY 兜底
    路径复活——选卡确认不可逆消耗本节点,禁盲选)。"""
    op, _m, _s, stub, _envs, clicks = _make_supply_live(
        test_context, monkeypatch,
        pick=CwActionPickSupplyParam(idx=0, reason='stub'), opts=[])
    _run_node(test_context, op, op.observe)
    assert op._obs is not None and op._obs.options == [], (
        '前置:观察轮 obs 装载空候选')
    rs = _run_node(test_context, op, op.act)
    assert rs.is_success and '零点击' in (rs.status or ''), (
        f'空候选 = 零点击终结交回重读:{rs!r}')
    assert clicks == [], f'零点击:{clicks!r}'
    assert stub.executed == 0, '零派发(禁盲选)'


def test_supply_guard_invalid_decision_named_fail(
        test_context, monkeypatch) -> None:
    """守卫①测试(§2.3):decide_supply 返回 None / 词表外类型 → 具名
    round_fail(消息含策略器原值 repr)零点击零派发。红 = 默认盲选派发
    回潮(决策失败被静默降级为不可逆的选卡消耗)。"""
    opt = SimpleNamespace(char='希儿', equip='星币收集器', has_diamond=False,
                          extra_equips=())
    for bad in (None, object()):
        op, _m, _s, stub, _envs, clicks = _make_supply_live(
            test_context, monkeypatch,
            pick=bad,
            opts=[(opt, SimpleNamespace(x=900, y=550))])
        assert _run_node(test_context, op, op.observe).is_success, (
            f'前置:观察 success(候选 1 元,bad={bad!r})')
        rs = _run_node(test_context, op, op.act)
        assert not rs.is_success and '决策无有效输出' in (rs.status or ''), (
            f'词表外/None = 具名 fail 零盲发(bad={bad!r}):{rs!r}')
        assert repr(bad) in (rs.status or ''), (
            f'消息含策略器原值 repr 留证(bad={bad!r}):{rs.status!r}')
        assert clicks == [] and stub.executed == 0, (
            f'守卫零盲发(零点击零派发):{clicks!r} executed={stub.executed}')


def test_supply_guard_out_of_range_idx_asserts(
        test_context, monkeypatch) -> None:
    """守卫②测试(§2.3):pick.idx 越界(真实 CwActionPickSupplyParam
    idx=5、options 1 元)→ AssertionError(消息含 idx/len/原值留证)、
    零点击零派发(守卫在派发前——越界放行会确认错卡,不可逆)。红 =
    静默钳位续跑回潮 / 越界放行派发。"""
    opt = SimpleNamespace(char='希儿', equip='星币收集器', has_diamond=False,
                          extra_equips=())
    op, _m, _s, stub, _envs, clicks = _make_supply_live(
        test_context, monkeypatch,
        pick=CwActionPickSupplyParam(idx=5, reason='stub'),
        opts=[(opt, SimpleNamespace(x=900, y=550))])
    assert _run_node(test_context, op, op.observe).is_success, (
        '前置:观察 success(obs.options 1 元)')
    with pytest.raises(AssertionError, match='禁钳位'):
        _run_node(test_context, op, op.act)
    assert clicks == [] and stub.executed == 0, (
        f'断言前零点击零派发:{clicks!r} executed={stub.executed}')


def test_supply_gate_rejection_redecide_still_refresh_live_round_fail(
        test_context, monkeypatch) -> None:
    """对照闸拒绝防线测试·实机(§2.2):「残值 ∧ 锚缺」帧(容器 left=1
    为上次访问残值,本次锚读缺不覆盖)建议刷 → 重调一次仍返刷新建议 →
    round_fail 交回(计入外循环 ``OP_FAIL_REDISPATCH_LIMIT``——零点击
    round_success 交回不计数,外循环对该循环无防护,故落防线,有界收敛;
    防线先例 = cw_screen_encounter.act 同款)。红 = 零点击 round_success
    终结交回回潮(无界重进循环面)。"""
    opt = SimpleNamespace(char='希儿', equip='星币收集器', has_diamond=False,
                          extra_equips=())
    op, _m, session, stub, _envs, clicks = _make_supply_live(
        test_context, monkeypatch,
        pick=CwActionRefreshSupplyParam(reason='stub-again'),
        opts=[(opt, SimpleNamespace(x=900, y=550))],
        anchor=None,
        seed_left=1)
    assert _run_node(test_context, op, op.observe).is_success, (
        '前置:观察 success(锚读缺,残值不覆盖)')
    assert game_state_of(session).supply_refresh_left.value == 1, (
        '前置:残值在容器(读缺跳写不覆盖)')
    rs = _run_node(test_context, op, op.act)
    assert not rs.is_success and '刷新锚点读缺' in (rs.status or ''), (
        f'重调仍建议刷新 → round_fail 交回:{rs!r}')
    assert clicks == [] and stub.executed == 0, (
        f'零点击零派发:{clicks!r} executed={stub.executed}')


# ==================== 决策链接线行为面(sim 两态)====================

_SIM_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)


def _feed_start_battle(gs) -> None:
    """出战上报 + 声明喂入(声明化单轨;动作 op「上报后一行喂入」同形,
    手法源 = test_sim_backend 世界喂入链)。"""
    out = report_action_start_battle_param(
        gs, SimpleNamespace(),
        ChannelSig(family='logic_action', actor='SimSupplyTest',
                   mode='compute'))
    cw_sim_ports.declare_world(out.world_decl)


def _feed_node_advance(gs, *, trigger: str) -> None:
    """节点推进上报 + 声明喂入(声明化单轨,手法源 = test_sim_backend)。"""
    out = report_node_advance(gs, trigger=trigger)
    assert out.applied, f'节点推进未落账: {out.reason!r}'
    cw_sim_ports.declare_world(out.world_decl)


@contextmanager
def _sim_supply_world(test_context, monkeypatch, *, seed: int = 61):
    """sim 补给节点世界装配缝(run_sim_full_match 装配段同源,不另发明):
    SimBackend(A8/108 标准局)+ 端口槽/事件钩子/动作分支 rng 提供槽
    (``install_backend`` 单点)+ controller 桩(任何真实 IO 触碰即炸 =
    机械执行分支零触碰的响亮证明)+ obs 读口纯钩子半部 + 世界驱动简报→P1r5
    补给节点窗(入口呈现 3 选项 + 免费刷新 left=1)。yield backend;
    teardown 必卸(端口槽进程全局,残留会把后续测试静默切进 sim 模式)。"""
    from sr_od.application.currency_war.kernel.cw_reconcile import (
        set_merge_effect_gate,
    )
    from sr_od.application.currency_war.obs.cw_identity_obs import (
        is_merge_effect_frame,
    )
    from sr_od.application.currency_war.obs.cw_observation import (
        reset_phase_round_cache,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        set_obs_reset_hook,
    )

    set_obs_reset_hook(reset_phase_round_cache)
    set_merge_effect_gate(is_merge_effect_frame)
    backend = SimBackend(seed=seed, cfg=_SIM_CFG)
    install_backend(backend)
    monkeypatch.setattr(test_context, 'controller', SimControllerStub())
    try:
        # 世界驱动到补给节点窗(喂入链手法源 = test_sim_backend.
        # test_supply_node_window_refresh_and_pick;P1r5 = 补给节点)。
        backend._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        backend._maybe_finish_wait()
        while backend.gs.node.value.round_num < 5:
            _feed_start_battle(backend.gs)
            if backend.screen_identity() == SCREEN_SETTLE:
                _feed_node_advance(backend.gs, trigger='settle_confirm')
        assert backend.screen_identity() == SCREEN_SUPPLY, (
            f'前置:世界在补给节点窗(实得 {backend.screen_identity()!r})')
        yield backend
    finally:
        uninstall_backend()


def _sim_match(test_context, monkeypatch, backend,
               strategy_seed: int = 61):
    """真策略装配段(run_sim_full_match 同源):StrategySession + 容器
    绑定(后端容器 = 流程唯一世界)+ MandateV1Strategy 构造 +
    CurrencyWarMatch 挂 ctx。返回 (match, strategy)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        bind_session_container,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CurrencyWarMatch,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        bridge as cw_bridge,
    )

    session = StrategySession()
    session.rng = random.Random(strategy_seed)
    bind_session_container(session, backend.gs)
    strategy = cw_bridge.MandateV1Strategy(
        backend.gs, SimpleNamespace(strategy_seed=strategy_seed))
    session.strategy_state = strategy.state
    match = CurrencyWarMatch(strategy, session, backend.gs,
                             performance=getattr(session, 'performance',
                                                 None))
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    return match, strategy


def test_supply_sim_refresh_leg_area_click_backend_refresh(
        test_context, monkeypatch) -> None:
    """刷新分支·sim 两态测试(§2.6 新增④ sim 半):sim 态(锚点分量恒过)
    建议刷 → 「文本-剩余次数」area 点击(基类 sim 改道 → 后端
    ``_supply_refresh``)→ left−1 + 选项重掷落容器,本访问终结交回;
    决策恰一次(零重调)。controller 桩在装 = 机械执行分支零触碰的结构性证明
    (刷新世界分支全走点击源端口)。"""
    with _sim_supply_world(test_context, monkeypatch, seed=53) as b:
        _match, strategy = _sim_match(test_context, monkeypatch, b)
        gs = b.gs
        assert gs.supply_refresh_left.value == 1, '前置:入口 left=1'
        _before = [(o.equip, o.extra_equips)
                   for o in gs.supply.value.options]
        # 桩驱动刷新建议(占位池可能含钻 → 真实 decide 会落选卡,刷新分支
        # 触发面需确定性注入;决策调用计数保留)。
        _decide_calls: list = []

        def _refresh_stub():
            _decide_calls.append(1)
            return CwActionRefreshSupplyParam(reason='stub')

        strategy.decide_supply = _refresh_stub
        op = CwScreenSupplyNode(test_context)
        assert _run_node(test_context, op, op.observe).is_success, (
            '前置:sim 观察 success(生成器产物装载 obs)')
        rs = _run_node(test_context, op, op.act)
        assert rs.is_success and '终结交回' in (rs.status or ''), (
            f'刷新后终结交回:{rs!r}')
        assert gs.supply_refresh_left.value == 0, '刷新分支:left−1'
        _after = [(o.equip, o.extra_equips)
                  for o in gs.supply.value.options]
        assert _after != _before, '刷新分支:选项重掷落容器'
        assert len(_decide_calls) == 1, f'决策恰一次(零重调):{_decide_calls!r}'
        assert gs.chosen_supply.value is None, '刷新轮零派发(chosen 零写)'


def test_supply_sim_gate_rejection_redecide_zero_click_terminal(
        test_context, monkeypatch) -> None:
    """对照闸拒绝防线测试·sim(§2.6 新增⑥ sim 半):桩驱动「重调仍返
    刷新建议」∧ left 刷尽(0)→ 零点击 round_success 终结零派发,容器
    零改(left 不变、选项不重掷;重进重读即恢复——sim 拒绝仅剩 left
    读缺形态,无机械锚读缺面)。"""
    with _sim_supply_world(test_context, monkeypatch, seed=53) as b:
        _match, strategy = _sim_match(test_context, monkeypatch, b)
        gs = b.gs
        # 预刷尽:left 1→0(后端刷新分支,剩余闸内嵌再验)。
        b._handle_click_source(SCREEN_SUPPLY, '文本-剩余次数')
        assert gs.supply_refresh_left.value == 0, '前置:left 刷尽'
        _before = [(o.equip, o.extra_equips)
                   for o in gs.supply.value.options]
        _decide_calls: list = []
        _orig = strategy.decide_supply

        def _refresh_stub():
            _decide_calls.append(1)
            return CwActionRefreshSupplyParam(reason='stub-again')

        strategy.decide_supply = _refresh_stub
        op = CwScreenSupplyNode(test_context)
        assert _run_node(test_context, op, op.observe).is_success
        rs = _run_node(test_context, op, op.act)
        assert rs.is_success and '零点击' in (rs.status or ''), (
            f'重调仍建议刷(sim)= 零点击终结交回:{rs!r}')
        assert gs.supply_refresh_left.value == 0, '拒绝轮容器 left 不变'
        _after = [(o.equip, o.extra_equips)
                  for o in gs.supply.value.options]
        assert _after == _before, '拒绝轮零重掷(选项不变)'
        assert len(_decide_calls) == 2, (
            f'拒绝 → 重调一次(恰两次决策):{_decide_calls!r}')
        assert gs.chosen_supply.value is None, '零派发(chosen 零写)'


def test_supply_sim_two_state_pick_flow(test_context, monkeypatch) -> None:
    """sim 两态 pick 流测试(§2.6 新增①):装 SimBackend 跑补给节点画面
    op——决策链接线(``decide_supply`` 被调,历史 sim 局结构性不可达面)、
    owned 内容载荷分支入账写行、``chosen_supply`` 写行、零节点推进
    (2026-10-29 流程模型对齐:选完关模态回备战自动弹店,推进归出战动作
    supply_finish)。装配缝 = run_sim_full_match 同源(真策略
    MandateV1Strategy;left 预刷尽使真实 decide 恒落选卡——次数闸内嵌,
    刷新建议不可能,决策确定性由 seed 承载)。动作 op 走真注册表派发:
    机械执行分支端口检查跳过,世界反应 = 上报声明链(内容载荷分支
    owned += 规范名)。占位池 char 恒空 → 单位入账分支结构性零写
    (design §2.2 申报;bench 分支对占位池不可达,不在断言面)。journal
    走内存 sink(零落盘),run 态测试复位。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        SupplyPayload,
    )

    tel_state.start_run('A8')   # journal 行归属铸造(直调 = 测试专用入口)
    try:
        with _sim_supply_world(test_context, monkeypatch, seed=61) as b:
            _match, strategy = _sim_match(test_context, monkeypatch, b)
            gs = b.gs
            # 预刷尽:left 1→0 → 真实 decide 恒落选卡(次数闸内嵌)。
            b._handle_click_source(SCREEN_SUPPLY, '文本-剩余次数')
            assert gs.supply_refresh_left.value == 0, '前置:left 刷尽'
            assert gs.supply.value is not None \
                and len(gs.supply.value.options) == 3, (
                '前置:占位池 3 选项在场')
            _bench_before = gs.bench.value
            _decide_calls: list = []
            _orig = strategy.decide_supply

            def _counting():
                _decide_calls.append(1)
                return _orig()

            strategy.decide_supply = _counting
            op = CwScreenSupplyNode(test_context)
            with capture_state_journal() as rows, freeze_cw_module_time():
                assert _run_node(test_context, op, op.observe).is_success, (
                    '前置:sim 观察 success')
                # 两态载体面:obs = 生成器产物(吃容器现值);实机执行
                # 载体不回填(sim 无读链,禁承载决策输入的载体归零)。
                assert op._obs is not None \
                    and op._obs.options == list(gs.supply.value.options), (
                    '决策输入 = obs 载体(生成器产物,两态同构)')
                assert op._card_points is None, (
                    'sim 不回填实机执行载体(_card_points 归 None)')
                rs = _run_node(test_context, op, op.act)
            assert rs.is_success and '终结交回' in (rs.status or ''), (
                f'选卡派发即终结交回:{rs!r}')
            assert _decide_calls == [1], (
                f'decide_supply 被调恰一次:{_decide_calls!r}')
            # chosen_supply 写行(确认即写;占位池 char 恒空 → ('', (装备,)) 形态)
            chosen = gs.chosen_supply.value
            assert chosen is not None and chosen[0] == '', (
                f'chosen_supply 写行:{chosen!r}')
            equip = chosen[1][0]
            assert equip in (o.equip for o in gs.supply.value.options), (
                '选定 = 在场选项内容(决策输入 = obs 载体)')
            # owned 内容载荷分支入账(装备入账分支 owned += 规范名;上报声明链驱动)
            assert equip in (gs.equips.value or []), 'owned 内容载荷分支入账'
            # 零节点推进(2026-10-29 流程模型对齐):选完关模态回备战并
            # 自动弹店,节点推进归出战动作 supply_finish
            assert gs.node.value.round_num == 5, (
                f'补给确认零节点推进:{gs.node.value!r}')
            assert b.screen_identity() == SCREEN_SHOP, (
                f'补给选完回备战自动弹店:{b.screen_identity()!r}')
            # journal 断言:chosen_supply 写行 + owned 装备入账分支写行
            #(journal after 经 _json_safe 序列化:tuple → list,node → dict)
            _chosen_json = [chosen[0], list(chosen[1])]
            assert any(r['field'] == 'chosen_supply'
                       and r['after'] == _chosen_json for r in rows), (
                f'journal:chosen_supply 写行(chosen={chosen!r},'
                f'rows={[(r["field"], r["after"]) for r in rows][-8:]!r})')
            assert any(r['field'] == 'equips'
                       and isinstance(r['after'], list)
                       and equip in r['after'] for r in rows), (
                f'journal:owned 装备入账分支写行(equip={equip!r})')
            assert not any(r['field'] == 'node' for r in rows), (
                'journal:零节点推进行(补给确认不再推节点)')
            # 单位入账分支结构性零写(design §2.2 申报面):占位池 char 恒空 →
            # 上报走装备入账分支分支,备战席零改动。
            assert gs.bench.value == _bench_before, (
                '单位入账分支零写(占位池 char 恒空)')
            assert isinstance(gs.supply.value, SupplyPayload)
    finally:
        tel_state.reset_run_state()   # run 态簇复位(测试复位正规入口)


# ==================== 未选集快照写点(打捞人才库族发源域)====================

_LIVE_OPTS = [
    (SupplyOption(idx=0, char='希儿', equip='光能电池'),
     SimpleNamespace(x=500, y=550)),
    (SupplyOption(idx=1, char='停云', equip='折叠小刀'),
     SimpleNamespace(x=900, y=550)),
    (SupplyOption(idx=2, char='三月七', equip='垃圾袋'),
     SimpleNamespace(x=1300, y=550)),
]


def test_supply_live_pick_writes_unchosen_same_window(
        test_context, monkeypatch) -> None:
    """未选集写点测试·live(真选分支确认即写同窗):真选确认 →
    ``unchosen_supply`` = 终屏列 − 选定列(按列身份消账——实例同一性
    断言,重复列形下按内容消账有歧义);与 ``chosen_supply`` 同 sig 同窗
    相邻(journal 行 = 同一确认动作原子面)。机械执行态限定写本测试即
    live 形态(无 sim 后端在装)。"""
    op, _m, session, stub, _envs, clicks = _make_supply_live(
        test_context, monkeypatch,
        pick=CwActionPickSupplyParam(idx=1, reason='stub'), opts=_LIVE_OPTS)
    assert _run_node(test_context, op, op.observe).is_success, (
        '前置:观察 success(候选 3 元)')
    rows: list[dict] = []
    monkeypatch.setattr(gs_mod, '_STATE_JOURNAL_SINK', rows.append)
    monkeypatch.setattr(gs_mod, '_RUN_ID_PROVIDER', lambda: 'test-run')
    try:
        rs = _run_node(test_context, op, op.act)
    finally:
        monkeypatch.setattr(gs_mod, '_STATE_JOURNAL_SINK', None)
        monkeypatch.setattr(gs_mod, '_RUN_ID_PROVIDER', lambda: None)
    assert rs.is_success and stub.executed == 1, f'选卡派发:{rs!r}'
    gs = game_state_of(session)
    unchosen = gs.unchosen_supply.value
    assert unchosen is not None and len(unchosen) == 2, f'余列快照: {unchosen!r}'
    assert unchosen[0] is _LIVE_OPTS[0][0] and unchosen[1] is _LIVE_OPTS[2][0], \
        '按列身份消账(选定 idx=1 之外两列,实例同一)'
    write_rows = [r for r in rows if r['row'] == 'write'
                  and r['field'] in ('chosen_supply', 'unchosen_supply')]
    assert [r['field'] for r in write_rows] == ['chosen_supply',
                                                'unchosen_supply'], \
        f'同窗相邻两行: {[r["field"] for r in write_rows]}'
    assert (write_rows[0]['sig']['family'], write_rows[0]['sig']['actor'],
            write_rows[0]['sig']['mode']) \
        == (write_rows[1]['sig']['family'], write_rows[1]['sig']['actor'],
            write_rows[1]['sig']['mode']) \
        == ('logic_action', 'CwScreenSupplyNode', 'compute'), \
        '两写行同 sig(logic_action/CwScreenSupplyNode/compute)'


def test_supply_non_pick_rounds_do_not_seed_unchosen(
        test_context, monkeypatch) -> None:
    """非真选轮零写测试(同 chosen_supply 真选守卫口径):刷新轮(对照闸
    放行,点钮终结)与对照闸拒绝轮(重调仍建议刷)与空候选轮 →
    ``unchosen_supply`` 恒零写(真选分支不可达 = 无写点)。"""
    from one_dragon.base.geometry.point import Point

    # 刷新轮:锚在位 + left=1 → 对照闸放行,点钮终结。
    op, _m, session, _stub, _envs, clicks = _make_supply_live(
        test_context, monkeypatch,
        pick=CwActionRefreshSupplyParam(reason='stub'),
        opts=_LIVE_OPTS, anchor=(1, Point(1414, 982)), seed_left=1)
    assert _run_node(test_context, op, op.observe).is_success
    rs = _run_node(test_context, op, op.act)
    assert rs.is_success and '终结交回' in (rs.status or ''), f'刷新轮:{rs!r}'
    assert game_state_of(session).unchosen_supply.value is None, '刷新轮零写'

    # 对照闸拒绝轮:锚缺 + 残值 → 重调仍建议刷 → round_fail。
    op2, _m2, session2, _stub2, _envs2, _clicks2 = _make_supply_live(
        test_context, monkeypatch,
        pick=CwActionRefreshSupplyParam(reason='stub-again'),
        opts=_LIVE_OPTS, anchor=None, seed_left=1)
    assert _run_node(test_context, op2, op2.observe).is_success
    rs2 = _run_node(test_context, op2, op2.act)
    assert not rs2.is_success, f'拒绝轮 round_fail:{rs2!r}'
    assert game_state_of(session2).unchosen_supply.value is None, '拒绝轮零写'

    # 空候选轮:零点击终结。
    op3, _m3, session3, _stub3, _envs3, _clicks3 = _make_supply_live(
        test_context, monkeypatch,
        pick=CwActionPickSupplyParam(idx=0, reason='stub'), opts=[])
    assert _run_node(test_context, op3, op3.observe).is_success
    rs3 = _run_node(test_context, op3, op3.act)
    assert rs3.is_success and '零点击' in (rs3.status or ''), f'空候选:{rs3!r}'
    assert game_state_of(session3).unchosen_supply.value is None, '空候选零写'


def test_supply_sim_pick_flow_unchosen_fail_closed(
        test_context, monkeypatch) -> None:
    """sim 形态未选集写点锁 + fail-closed 回归:sim 局决策分支可达真选
    写点(决策链接线后两态同链),但未选集域限机械执行态不种——
    ``unchosen_supply`` 恒 None → 检查函数恒第 2 门早退零发放(防未来
    误接线静默改 sim 行为):真选后 chosen 写行而 unchosen 恒 None;
    持卡局下一次成功观察帧过检查,bench/equips 零打捞增量。"""
    with _sim_supply_world(test_context, monkeypatch, seed=61) as b:
        _match, strategy = _sim_match(test_context, monkeypatch, b)
        gs = b.gs
        gs.observe(gs.active_strategies, ['打捞人才库'],
                   evidence='test:hold', sig=_SIG_OBS)
        # 预刷尽:left 1→0 → 真实 decide 恒落选卡(次数闸内嵌,先例 =
        # sim 两态 pick 流测试)。
        b._handle_click_source(SCREEN_SUPPLY, '文本-剩余次数')
        assert gs.supply_refresh_left.value == 0, '前置:left 刷尽'
        op = CwScreenSupplyNode(test_context)
        assert _run_node(test_context, op, op.observe).is_success, (
            '前置:sim 观察 success')
        rs = _run_node(test_context, op, op.act)
        assert rs.is_success and '终结交回' in (rs.status or ''), (
            f'sim 选卡派发:{rs!r}')
        assert gs.chosen_supply.value is not None, '前置:chosen 写行(sim 真选可达)'
        assert gs.unchosen_supply.value is None, (
            '未选集域 sim 恒 None(机械执行态限定写,fail-closed 载体面)')
        bench_after = gs.bench.value
        equips_after = list(gs.equips.value or [])
        # 持卡局下一次成功观察帧(sim 呈现链同函数):检查恒第 2 门早退,
        # 零打捞增量(真值对齐归 sim 补给真值专项,本卡零 sim 接线)。
        report_screen_supply_node_obs(
            gs, CwScreenSupplyNodeObs(
                in_node=True,
                options=list(gs.supply.value.options or [])))
        assert gs.bench.value == bench_after, '检查零发放:bench 不变'
        assert gs.equips.value == equips_after, '检查零发放:equips 不变'


def test_supply_sim_pick_take_all_fail_closed_latch_bookkeeping(
        test_context, monkeypatch) -> None:
    """全都要·银·sim pick 流 fail-closed 锁(选卡时点检查挂点,真注册表
    派发链全通):sim 局未选集恒 None(机械执行态限定写)→ 持卡局选卡
    派发后发放侧零写(bench/equips 不变),事件消耗闩照设 = 一笔无害簿记写
    (A 案,sim 闩笔申报形态);防未来误接线静默改变 sim 行为。"""
    with _sim_supply_world(test_context, monkeypatch, seed=61) as b:
        _match, _strategy = _sim_match(test_context, monkeypatch, b)
        gs = b.gs
        gs.observe(gs.active_strategies, ['全都要·银'],
                   evidence='test:hold', sig=_SIG_OBS)
        # 预刷尽:left 1→0 → 真实 decide 恒落选卡(次数闸内嵌)。
        b._handle_click_source(SCREEN_SUPPLY, '文本-剩余次数')
        assert gs.supply_refresh_left.value == 0, '前置:left 刷尽'
        bench_before = gs.bench.value
        equips_before = list(gs.equips.value or [])
        op = CwScreenSupplyNode(test_context)
        assert _run_node(test_context, op, op.observe).is_success, (
            '前置:sim 观察 success')
        rs = _run_node(test_context, op, op.act)
        assert rs.is_success and '终结交回' in (rs.status or ''), (
            f'sim 选卡派发:{rs!r}')
        assert gs.chosen_supply.value is not None, '前置:选卡确认已落地'
        assert gs.unchosen_supply.value is None, (
            '未选集域 sim 恒 None(fail-closed 载体面)')
        assert gs.strategy_conditional_done.value == \
            ('take_all#全都要·银#1',), (
            '事件消耗照耗(A 案 sim 簿记 = 一笔计数复合键 done 写,零世界效果)')
        assert gs.bench.value == bench_before, '发放侧零写:bench 不变'
        assert list(gs.equips.value) == \
            equips_before + [gs.chosen_supply.value[1][0]], (
            'equips 增量恰 = 选卡载荷自身入账(占位池单件),零全捞发放增量')


def test_supply_sim_pick_take_all_color_none_quota_zero_latch(
        test_context, monkeypatch) -> None:
    """全都要·彩·sim pick 流零簿记锁(选卡时点检查挂点,真注册表派发链
    全通):None 配额卡(recurring 无配额域)在 sim 形态(未选集恒 None,
    机械执行态限定写)下选卡派发后 done 域零 ``take_all#`` 键——与银卡
    同形态恰一键对照互证(A 案事件消耗簿记只对 int 配额卡存在),发放侧
    零写;防未来误接线静默改变 sim 行为。"""
    with _sim_supply_world(test_context, monkeypatch, seed=61) as b:
        _match, _strategy = _sim_match(test_context, monkeypatch, b)
        gs = b.gs
        gs.observe(gs.active_strategies, ['全都要·彩'],
                   evidence='test:hold', sig=_SIG_OBS)
        # 预刷尽:left 1→0 → 真实 decide 恒落选卡(次数闸内嵌)。
        b._handle_click_source(SCREEN_SUPPLY, '文本-剩余次数')
        assert gs.supply_refresh_left.value == 0, '前置:left 刷尽'
        bench_before = gs.bench.value
        equips_before = list(gs.equips.value or [])
        op = CwScreenSupplyNode(test_context)
        assert _run_node(test_context, op, op.observe).is_success, (
            '前置:sim 观察 success')
        rs = _run_node(test_context, op, op.act)
        assert rs.is_success and '终结交回' in (rs.status or ''), (
            f'sim 选卡派发:{rs!r}')
        assert gs.chosen_supply.value is not None, '前置:选卡确认已落地'
        assert gs.unchosen_supply.value is None, (
            '未选集域 sim 恒 None(fail-closed 载体面)')
        assert not any(
            k.startswith('take_all#')
            for k in (gs.strategy_conditional_done.value or ())), (
            'None 配额卡零闩格(done 域无 take_all# 键,正面断言)')
        assert gs.bench.value == bench_before, '发放侧零写:bench 不变'
        assert list(gs.equips.value) == \
            equips_before + [gs.chosen_supply.value[1][0]], (
            'equips 增量恰 = 选卡载荷自身入账,零全捞发放增量')
