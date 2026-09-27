"""CW 统一动作工厂 批2c 锁面(书册卡开卡归位 R10;卡片臂策略器化 2026-09-19)。

 §3.2c 判据 +
 R10 条款。规则正本 = flow/action-logic-state.md §3.7。
2026-09-19 用户裁定:开卡时机归策略实现管——备战环入口清场段
(``cw_screen_prep._clear_prep_cards``)撤销,发射位 = 策略器 entry ①
prep 实体面卡片臂(容器 bench kind 触发);本文件接线锁随之换面。

锁面全部为运行时行为锁(源码扫描测试禁止,AGENTS.md §10.4);
kernel/执行器级用桩宿主,零真实 IO(harness 惯例同 test_cw_unified_action_2a)。
"""

from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
    deployed_indexed_of_view,
)


import time
from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_deploy_move_param,
    report_action_open_bookcard_param,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    Unit,
    bench_free_slots,
    bench_view_slots_of,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CW_ACTION_TYPES,
    CwActionOpenBookcardParam,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')


# ===== 词表行 + F3 注册行(判据:CwActionOpenBookcardParam 词表行 + 注册行在册)=====

def test_open_bookcard_registered_and_validated():
    """R10 归位:CwActionOpenBookcardParam 在统一词表白名单(漏登记先例 CwActionOpenTomeParam:
    漏登记时执行面 validate 拒「未知动作类型」,动作从未真正执行);F3
    静态参数域与 CwActionOpenBoxParam/CwActionOpenTomeParam 同形(slot=None 或 1..备战栏槽位)。"""
    assert CwActionOpenBookcardParam in CW_ACTION_TYPES
    from sr_od.application.currency_war import prep_actions as pa
    ex = pa.PrepActionExecutor.__new__(pa.PrepActionExecutor)
    ex._bench_pts = [Point(i * 10, i * 10) for i in range(9)]
    assert ex.validate(CwActionOpenBookcardParam()) is None
    assert ex.validate(CwActionOpenBookcardParam(slot=9)) is None
    err = ex.validate(CwActionOpenBookcardParam(slot=10))
    assert err is not None and '越界' in err


# ===== 执行器机械半(判据:备战侧发射 → 点槽;体自 open_card 迁入)=====

class _RecordingController:
    def __init__(self) -> None:
        self.moves: list[Point] = []
        self.clicks: list[Point] = []

    def mouse_move(self, p: Point) -> None:
        self.moves.append(p)

    def click(self, p: Point) -> None:
        self.clicks.append(p)


def _make_executor(controller: _RecordingController, screens: list | None):
    """执行器桩宿主(同 unified_action_2a harness 形状;本文件自持)。"""
    from sr_od.application.currency_war import prep_actions as pa
    op = SimpleNamespace(park_cursor=lambda **kw: None,
                         screenshot=lambda: (screens.append(1) if
                                             screens is not None else None)
                         or object())
    ctx = SimpleNamespace(controller=controller, cw_match=None,
                          run_context=None,
                          screen_loader=SimpleNamespace(
                              get_screen=lambda name: None))
    return pa.PrepActionExecutor(op, ctx)


def test_open_bookcard_executor_mechanical(monkeypatch):
    """机械半:`find_bookcards` 识别 → 首张槽中心单击 → 固定动画等待;
    slot 对位不中 / 识别空 = 未发出零点击(与 CwActionOpenBoxParam/CwActionOpenTomeParam 同形)。
    动画等待值家族单一源(_OVERLAY_ANIM_WAIT_S;判效交下一帧观察)。"""
    from sr_od.application.currency_war.obs import cw_identity_obs
    monkeypatch.setattr(cw_identity_obs, 'find_bookcards',
                        lambda screen, slots: [(2, Point(123, 456))])
    monkeypatch.setattr(cw_identity_obs, '_ctx_slots',
                        lambda ctx, name, n: [])
    monkeypatch.setattr(time, 'sleep', lambda s: None)   # 动画等待桩(零真实等待)
    controller = _RecordingController()
    ex = _make_executor(controller, [])
    detail, emitted = ex._open_bookcard(CwActionOpenBookcardParam())
    assert emitted and '槽2' in detail
    assert [(p.x, p.y) for p in controller.clicks] == [(123, 456)]
    assert len(controller.moves) == 1   # bug#1 缓解口径:先移后点
    # slot 指定但实读无该槽 → 未发出零点击(对位语义同 _open_box)
    controller2 = _RecordingController()
    ex2 = _make_executor(controller2, [])
    detail2, emitted2 = ex2._open_bookcard(CwActionOpenBookcardParam(slot=5))
    assert not emitted2 and controller2.clicks == []
    # 识别空 → 未发出(交回外循环重观察重派)
    monkeypatch.setattr(cw_identity_obs, 'find_bookcards',
                        lambda screen, slots: [])
    controller3 = _RecordingController()
    ex3 = _make_executor(controller3, [])
    detail3, emitted3 = ex3._open_bookcard(CwActionOpenBookcardParam())
    assert not emitted3 and controller3.clicks == []


# ===== 逻辑态摘件对账(判据:开卡后槽位表与实机一致)=====

def test_open_bookcard_logic_state_frees_slot():
    """开卡即腾席(阶段 3.5 容器版;原黑板 free_bench_slots +1 语义随
    _project_prep_obs 退役):书册卡槽(容器 kind='bookcard',kind 细分批
    起不再统一降级 supply_box)经 CwActionOpenBookcardParam 腾席 = 槽
    kind → empty——bench_free_slots 派生 +1(容器读口单点),其余槽不动。
    降级口径(slot kind='supply_box')= 类型不符拒零写(防跨物误腾)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    session = cw4_session()
    gs = game_state_of(session)
    _sig = ChannelSig(family='obs', actor='cw4_seed',
                      mode='synthesized')
    _slots = [BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1,
                                               equips=[])),
              BenchSlot(kind='bookcard')]
    _slots += [BenchSlot(kind='empty') for _ in range(7)]
    gs.observe(gs.bench, BenchView(slots=_slots, capacity=9), sig=_sig)
    before = bench_free_slots(gs)
    assert before == 7
    report_action_open_bookcard_param(
        gs, CwActionOpenBookcardParam(slot=2),
        sig=ChannelSig(family='logic_action', actor='CwScreenPrep'))
    assert gs.bench.value.slots[1].kind == 'empty'
    assert bench_free_slots(gs) == before + 1
    # 类型不符拒零写:supply_box 槽不是本动作的腾席对象(开箱 = OpenBox 辖)
    before_seq = gs.write_seq
    report_action_open_bookcard_param(
        gs, CwActionOpenBookcardParam(slot=2),
        sig=ChannelSig(family='logic_action', actor='CwScreenPrep'))
    assert gs.write_seq == before_seq   # 槽已 empty,陈旧提案零写


# ===== 卡片臂接线锁(判据:容器 bench kind → 策略器 entry ① 发射终结动作)=====

def _emit_with_bench(bench_slots: list[BenchSlot]):
    """观测 bench 后调 entry.emit(臂① 早返回面;session = cw4 冷建)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    from sr_od.application.currency_war.strategies.impl.mandate_v1 import entry
    session = cw4_session()
    gs = game_state_of(session)
    _slots = list(bench_slots)
    _slots += [BenchSlot(kind='empty')] * (9 - len(_slots))
    gs.observe(gs.bench, BenchView(slots=_slots, capacity=9),
               sig=ChannelSig(family='obs', actor='CwScreenPrep',
                              mode='read'))
    return entry.emit(session, None)


def test_entry_card_arms_emit_from_bench_kind():
    """用户裁定 2026-09-19(开卡时机归策略器):容器 bench 槽位 kind
    'bookcard' → entry ① 卡片臂发射 CwActionOpenBookcardParam(物理槽号
    = 下标 +1);优先序卡先于箱(旧「入口清场先于观察」全局序)。
    (历史注:「trial_card」臂随幻影机制撤销——备战栏发光金卡 = 动画帧
    误判,用户定谳 2026-09-19,禁再建模。)"""
    # bookcard 槽 → OpenBookcard(slot=下标+1)
    out = _emit_with_bench([BenchSlot(kind='unit', unit=Unit(
        char_id='甲', star=1, equips=[])),
        BenchSlot(kind='bookcard')])
    assert len(out) == 1 and isinstance(out[0].action, CwActionOpenBookcardParam)
    assert out[0].action.slot == 2
    # 优先序:卡先于箱(旧「入口清场先于观察」全局序)
    out = _emit_with_bench([BenchSlot(kind='bookcard'),
                            BenchSlot(kind='supply_box')])
    assert isinstance(out[0].action, CwActionOpenBookcardParam)


def test_entry_box_tome_arms_read_benchview_kind():
    """回归锁:开箱/开典籍臂与卡片臂同读容器 BenchView.slots kind
    (占位件三分类 kind 直读,单一形状无换形路)。本锁钉死 box/tome 臂
    在真 kind 载荷上照常命中。"""
    out = _emit_with_bench([BenchSlot(kind='supply_box')])
    assert len(out) == 1
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionOpenBoxParam,
        CwActionOpenTomeParam,
    )
    assert isinstance(out[0].action, CwActionOpenBoxParam)
    assert out[0].action.slot == 1
    slots = [BenchSlot(kind='empty')] * 9
    slots[3] = BenchSlot(kind='tome')
    out = _emit_with_bench(slots)
    assert len(out) == 1 and isinstance(out[0].action, CwActionOpenTomeParam)
    assert out[0].action.slot == 4


def test_bench_slot_bookcard_kind_occupies_one_slot():
    """容器 kind 细分占席语义:bookcard 槽恒占 1 席(kind ≠ empty),
    席空数派生同源(bench_free_slots,9−2=7)。(legacy 旗标往返面
    随换形层退役删除。)"""
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1,
                                              equips=[])),
             BenchSlot(kind='bookcard')]
    slots += [BenchSlot(kind='empty')] * 7
    view = BenchView(slots=slots, capacity=9)
    assert view.slots[1].kind == 'bookcard'
    # 占席语义:bookcard 占 1 槽,席空数派生同源(9−2=7)
    from test.sr_od.application.currency_war._cw_helpers import cw4_session
    _gs = game_state_of(cw4_session())
    _sig = ChannelSig(family='obs', actor='CwScreenPrep', mode='read')
    _gs.observe(_gs.bench, view, sig=_sig)
    assert bench_free_slots(_gs) == 7


# ===== CwActionDeployMoveParam 帧投影占用集(改动三审 代-1 应修行为锁)=====

def test_deploymove_projection_records_resolved_row():
    """CwActionDeployMoveParam 容器逻辑态载荷直落锁:容器写侧按载荷
    (to_row, to_slot) 直落——目标有人 = 交换(被占位者回源 bench 槽),
    载荷槽空 = 放置,源槽空 = 陈旧提案零写(框架零落位决定)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import CwActionDeployMoveParam
    session = cw4_session()
    gs = game_state_of(session)
    _sig = ChannelSig(family='obs', actor='cw4_seed',
                      mode='synthesized')
    _logic = ChannelSig(family='logic_action', actor='CwScreenPrep')
    _slots = [BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1,
                                               equips=[]))]
    _slots += [BenchSlot(kind='empty') for _ in range(8)]
    gs.observe(gs.bench, BenchView(slots=_slots, capacity=9), sig=_sig)
    # 前排满(4 人):载荷指前排 2 号(丙1 占位)→ 交换,甲落 2 号、
    # 丙1 回源 bench 槽 3
    gs.observe(gs.deployed, _dvs([Unit(char_id=f'丙{i}', star=1, equips=[])
                                  for i in range(4)], []),
               sig=_sig)
    report_action_deploy_move_param(gs, CwActionDeployMoveParam(bench_idx=0,
                                                   to_row='front',
                                                   to_slot=2,
                                                   faction=''),
                                    sig=_logic)
    dep = deployed_indexed_of_view(gs.deployed.value)
    assert dep[1] is not None and dep[1].char_id == '甲', \
        '载荷直落:落参数指定槽(to_slot=2 → 表下标 1)'
    assert [d.char_id for i, d in enumerate(dep[:4]) if i != 1] \
        == ['丙0', '丙2', '丙3'], '交换只动目标槽,其余占位不受波及'
    _b = bench_view_slots_of(gs)[0]
    assert _b is not None and _b.kind == 'unit' and _b.unit.char_id == '丙1', \
        '交换语义:被占位角色回发射者源 bench 槽'
    # 载荷槽空 = 放置(前排 1 号被乙占,载荷指 2 号空槽 → 照落 2 号)
    gs2 = game_state_of(cw4_session())
    gs2.observe(gs2.bench, BenchView(slots=_slots, capacity=9), sig=_sig)
    gs2.observe(gs2.deployed, _dvs([Unit(char_id='乙', star=1, equips=[])],
                                   []), sig=_sig)
    report_action_deploy_move_param(gs2, CwActionDeployMoveParam(bench_idx=0,
                                                    to_row='front',
                                                    to_slot=2,
                                                    faction=''),
                                    sig=_logic)
    dep2 = deployed_indexed_of_view(gs2.deployed.value)
    assert dep2[1] is not None and dep2[1].char_id == '甲'   # 载荷槽 = 表 1 位
    assert dep2[0].char_id == '乙', '占位槽不受放置波及'
    # 源槽无件(bench_idx 越界空槽)= 陈旧提案,本口零写
    before = gs2.write_seq
    report_action_deploy_move_param(gs2, CwActionDeployMoveParam(bench_idx=5,
                                                    to_row='front',
                                                    to_slot=2,
                                                    faction=''),
                                    sig=_logic)
    assert gs2.write_seq == before


# ===== CwScreenExpertInvite 收缩(判据:无开卡残留,入口=弹窗已开)=====

def test_expert_invite_entry_select_only(test_context, monkeypatch):
    """收缩为弹窗画面 op:open_card 节点拆退役(属性不在场);入口门 =
    弹窗已开单一形态(两 node 形态观察 node 承载,迭代
    )——弹窗不在 = fail 交回外循环重识别
    (外循环按下一帧画面重分发自愈;开卡缺位由备战词表
    CwActionOpenBookcardParam 链承接)。选卡成功链的行为面由决策出口守卫
    锁组承重,本锁不重复。"""
    from test.sr_od.application.currency_war._cw_helpers import (
        Area,
        run_node,
    )

    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_expert_invite as mod,
    )
    op = mod.CwScreenExpertInvite(test_context)
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'screenshot', lambda: object(), raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: Area(False))
    rs = run_node(test_context, op, op.observe)
    assert not rs.is_success and '弹窗未现' in (rs.status or '')


# ===== CwScreenExpertInvite 决策出口守卫锁组(原「决策链异常降级」锁 =====
# ===== 原位改写:异常传播/返回契约/值域/正路两态/局外无早退支自然失败; =====
# ===== op-layer §1.1 出口③ + §1.3 + 全族删门)=====

def _expert_guard_harness(test_context, monkeypatch, strategy):
    """守卫锁组装配(承原降级锁 harness 改写):obs 读链桩 + area_center 桩
    (迁观察链 = 观察上报坐标域种子,act 决策段零 area_center 可桩)+ 注册
    表 action_op_for 派发捕获桩。strategy = decide_expert_invite 注入体
    (match = StrategySession 冷建;strategy=None = 局外无 match 语境)。
    返回 (op, match, dispatches)。"""
    from test.sr_od.application.currency_war._cw_helpers import Area

    from sr_od.application.currency_war.kernel import cw_obs_core
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.obs import cw_observation
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_expert_invite as mod,
    )

    session = StrategySession()
    match = (None if strategy is None else SimpleNamespace(
        session=session,
        strategy=SimpleNamespace(decide_expert_invite=strategy)))
    if match is not None:
        match.gs = game_state_of(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = mod.CwScreenExpertInvite(test_context)
    # 卡羁绊/板面读链桩(观察载体在位:卡-1 = 能量,与板面 {'仙舟': 2}
    # 无同线;判据语义对锁组无感——决策值全由 strategy 桩给定)。
    monkeypatch.setattr(mod, '_resolve_card_bonds',
                        lambda ctx, screen, a: '能量' if a == '卡-1' else None)
    monkeypatch.setattr(cw_observation, 'read_board',
                        lambda ctx, screen: {'仙舟': 2})
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'screenshot', lambda: object(), raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: Area(True))
    # 坐标域种子(观察链桩;观察上报经 report 落容器,决策段零坐标现算,
    # 坐标消费 = 动作 op 容器取点锁 test_cw_unified_action_4)。
    _pts = {'卡-1': Point(300, 400), '卡-2': Point(700, 400),
            '卡-3': Point(1100, 400), '卡-4': Point(1500, 400),
            mod.CASH_AREA: Point(500, 900)}
    monkeypatch.setattr(cw_obs_core, 'area_center',
                        lambda ctx, name, screen: _pts.get(name))
    # 派发捕获桩(机械链行为锁 = test_cw_unified_action_4)。
    dispatches: list = []

    class _StubPickOp:
        def __init__(self, param, env) -> None:
            self.param = param
            self.env = env

        def execute(self) -> bool:
            dispatches.append(self)
            return True

    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as _reg
    monkeypatch.setattr(_reg, 'action_op_for',
                        lambda act, ctx, env: _StubPickOp(act, env))
    return op, match, dispatches


def test_expert_invite_decision_exception_propagates(test_context, monkeypatch):
    """锁A(异常传播,op-layer §1.1 出口③):策略桩 decide_expert_invite
    抛 RuntimeError → act 异常传播(pytest.raises)、零派发、_pick_pending
    保持 None。原「异常不出 op,落现金为王兜底续跑」降级形态随守卫化退役
    (策略异常 = 错误传播交外循环,流程侧禁任何兜底决策)。红 = 异常被
    吸收降级续跑 / 派发照发。"""
    from test.harness.fixture_controller import fast_sleep
    from test.sr_od.application.currency_war._cw_helpers import run_node

    def _boom() -> None:
        raise RuntimeError('决策链注入异常(测试)')

    op, _match, dispatches = _expert_guard_harness(test_context, monkeypatch,
                                                   _boom)
    rs = run_node(test_context, op, op.observe)
    assert rs.is_success, f'在门观察 success:{rs!r}'
    with fast_sleep(op), pytest.raises(RuntimeError):
        op.act()
    assert dispatches == [], '异常传播 = 零派发(零盲发)'
    assert op._pick_pending is None, '异常传播 = pending 保持 None'


def test_expert_invite_decision_invalid_return_named_fail(test_context,
                                                          monkeypatch):
    """锁B(返回契约,op-layer §1.1 出口③):策略桩返回 None 与词表外对象
    (SimpleNamespace(idx=0))两子态 → act 具名 round_fail(消息含「决策
    无有效输出」与原值 repr)、零派发零点击、_pick_pending None。原
    AttributeError 传播路径收编进具名 fail(诊断面原值 repr 直读)。红 =
    盲发派发 / 消息缺原值。"""
    from test.harness.fixture_controller import fast_sleep
    from test.sr_od.application.currency_war._cw_helpers import run_node

    for bad, frag in ((None, 'None'), (SimpleNamespace(idx=0), 'idx=0')):
        op, _match, dispatches = _expert_guard_harness(
            test_context, monkeypatch, lambda b=bad: b)
        rs = run_node(test_context, op, op.observe)
        assert rs.is_success, f'在门观察 success:{rs!r}'
        with fast_sleep(op):
            rs = op.act()
        assert not rs.is_success and '决策无有效输出' in (rs.status or ''), \
            f'词表外/None = 具名 fail 零盲发:{rs!r}'
        assert frag in (rs.status or ''), f'消息含原值 repr({frag}):{rs!r}'
        assert dispatches == [], '零派发零点击(守卫①拦截)'
        assert op._pick_pending is None, 'pending 保持 None'


def test_expert_invite_pick_idx_out_of_domain_asserts(test_context,
                                                      monkeypatch):
    """锁C(值域,op-layer §1.3):真词表类域外 idx(-2 = 原「<0 静默并入
    现金分支」路径 / 4 = 原 IndexError 意外出口)→ AssertionError 传播、
    零派发零点击、_pick_pending None;idx=-1 不炸(域内现金语义,归锁D)。
    红 = 域外并入现金分支 / 越界非守卫断言出口。"""
    from test.harness.fixture_controller import fast_sleep
    from test.sr_od.application.currency_war._cw_helpers import run_node

    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickExpertInviteParam,
    )

    for bad_idx in (-2, 4):
        op, _match, dispatches = _expert_guard_harness(
            test_context, monkeypatch,
            lambda i=bad_idx: CwActionPickExpertInviteParam(idx=i))
        run_node(test_context, op, op.observe)
        with fast_sleep(op), pytest.raises(AssertionError):
            op.act()
        assert dispatches == [], f'域外 idx={bad_idx} = 零派发零点击'
        assert op._pick_pending is None, 'pending 保持 None'


def test_expert_invite_decision_direct_dispatch_two_states(test_context,
                                                           monkeypatch):
    """锁D(正路两态):真词表类 idx=-1 → 恰一次派发、派发 param 即策略产
    实例(is 比对,零重建构造点)、env.idx == -1 且 env 停喂 target
    (idx-only)、容器坐标域 cash_point 在位(坐标源断言 = 容器值,机械
    消费归 test_cw_unified_action_4 容器取点锁)、round WAIT;idx=1 →
    env.idx == 1、容器 card_points[1] 在位、_pick_pending 置位。红 = 重建
    构造点回潮 / env 复喂 target / 观察双写断流。"""
    from test.harness.fixture_controller import fast_sleep
    from test.sr_od.application.currency_war._cw_helpers import run_node

    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickExpertInviteParam,
    )

    pts = [(300, 400), (700, 400), (1100, 400), (1500, 400)]
    for idx in (-1, 1):
        pick = CwActionPickExpertInviteParam(idx=idx)
        op, match, dispatches = _expert_guard_harness(
            test_context, monkeypatch, lambda p=pick: p)
        rs = run_node(test_context, op, op.observe)
        assert rs.is_success, f'在门观察 success:{rs!r}'
        payload = match.gs.expert_invite.value
        assert payload.card_points == pts and payload.cash_point == (500, 900), \
            f'观察上报同门双写坐标域:{payload!r}'
        with fast_sleep(op):
            rs = op.act()
        assert not rs.is_success and '点击已发' in (rs.status or ''), \
            f'round WAIT 机械交回:{rs!r}'
        assert len(dispatches) == 1, f'恰一次派发:{dispatches!r}'
        assert dispatches[0].param is pick, '直发策略产实例(零重建)'
        assert dispatches[0].env.idx == idx, 'env.idx = 策略产值'
        assert dispatches[0].env.target is None, 'env = idx-only(停喂 target)'
        if idx == 1:
            assert op._pick_pending == (1, ['能量', None, None, None]), \
                f'_pick_pending 置位:{op._pick_pending!r}'


def test_expert_invite_no_match_fails_via_normal_chain(test_context,
                                                       monkeypatch):
    """锁E(局外无早退支,用户裁决 2026-09-22 全族删门,op-layer §1.1):
    cw_match = None(观察链桩照常给 obs)→ act 不设局外早退门,沿正常
    链路因缺上下文自然失败(AttributeError)、零派发零点击、_pick_pending
    保持 None;kernel choose_expert_index 桩零调用(兜底判据支退役的回归
    锁)。红 = 局外 round_success 早退门回潮 / 局外兜底决策/派发回潮。"""
    from test.harness.fixture_controller import fast_sleep
    from test.sr_od.application.currency_war._cw_helpers import run_node

    from sr_od.application.currency_war.kernel import cw_events

    calls: list = []

    def _spy_choose(*args, **kwargs):
        calls.append(args)
        return -1

    monkeypatch.setattr(cw_events, 'choose_expert_index', _spy_choose)
    op, _match, dispatches = _expert_guard_harness(test_context, monkeypatch,
                                                   None)
    rs = run_node(test_context, op, op.observe)
    assert rs.is_success, f'在门观察 success:{rs!r}'
    assert op._obs is not None, '观察链桩照常给 obs'
    with fast_sleep(op), pytest.raises(AttributeError, match='strategy'):
        op.act()   # 无 match 正常链路失败
    assert dispatches == [], '局外 = 零派发零点击'
    assert calls == [], 'kernel choose_expert_index 零调用(兜底判据支退役)'
    assert op._pick_pending is None, 'pending 保持 None'


def test_expert_invite_report_dual_domain_write():
    """report 双写锁(选择坐标观察上报,op-layer §1.1 :35):同一调用同一
    写门写 ``ExpertInvitePayload`` 四字段(card_bonds/board/card_points/
    cash_point);同序等长写端构造守卫——不等长(定长 4)= AssertionError
    响亮暴露零写;坐标域欠供(None)随名字域同门照报(:34 欠账形态同格,
    不半截收敛——清偿批同名同坐标一次落净)。红 = 拆门双写 / 等长守卫
    缺位 / 坐标域单独收敛。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    from sr_od.application.currency_war.kernel.cw_screen_report.expert_invite import (
        CwScreenExpertInviteObs,
        report_screen_expert_invite_obs,
    )

    pts = [(300, 400), (700, 400), (1100, 400), (1500, 400)]
    gs = game_state_of(cw4_session())
    report_screen_expert_invite_obs(gs, CwScreenExpertInviteObs(
        on_screen=True, card_bonds=['仙舟', None, None, None],
        board={'仙舟': 3}, card_points=pts, cash_point=(500, 900)))
    payload = gs.expert_invite.value
    assert payload is not None, 'report 落容器'
    assert payload.card_bonds == ['仙舟', None, None, None]
    assert payload.board == {'仙舟': 3}
    assert payload.card_points == pts, '坐标域同门一并写'
    assert payload.cash_point == (500, 900), '现金为王点同门一并写'
    # 等长守卫触发即红(不等长 = 观察 bug,响亮暴露零写)
    before = gs.write_seq
    with pytest.raises(AssertionError):
        report_screen_expert_invite_obs(gs, CwScreenExpertInviteObs(
            on_screen=True, card_bonds=['仙舟', None, None, None],
            board={}, card_points=pts[:3]))
    assert gs.write_seq == before, '等长守卫拦截 = 零写'
    # 坐标域欠供(None)随名字域同门照报(不半截收敛)
    gs2 = game_state_of(cw4_session())
    report_screen_expert_invite_obs(gs2, CwScreenExpertInviteObs(
        on_screen=True, card_bonds=['仙舟', None, None, None], board={}))
    p2 = gs2.expert_invite.value
    assert p2.card_points is None and p2.cash_point is None, '坐标域欠供照报 None'
    assert p2.card_bonds == ['仙舟', None, None, None], '名字域照报(同门)'
