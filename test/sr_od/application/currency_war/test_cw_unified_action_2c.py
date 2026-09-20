"""CW 统一动作工厂 批2c 锁面(书册卡开卡归位 R10;卡片臂策略器化 2026-09-19)。

出处 = docs/develop/sr_od/application/currency_war/changes/
2026-09-14-unified-action-factory/landing.md §3.2c 判据 +
design.md §2.6 R10 条款。规则正本 = flow/action-logic-state.md §3.7。
2026-09-19 用户裁定:开卡时机归策略实现管——备战环入口清场段
(``cw_screen_prep._clear_prep_cards``)撤销,发射位 = 策略器 entry ①
prep 实体面卡片臂(容器 bench kind 触发);本文件接线锁随之换面。

锁面全部为运行时行为锁(源码扫描测试禁止,AGENTS.md §10.4);
kernel/执行器级用桩宿主,零真实 IO(harness 惯例同 test_cw_unified_action_2a)。
"""

from __future__ import annotations

import time
from types import SimpleNamespace

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
    bench_slots_to_legacy,
    deployed_slots_of,
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
    _sig = ChannelSig(family='obs', actor='synthesize_from_game_state',
                      mode='synthesized')
    _slots = [BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1,
                                               equips=[], slot=1)),
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
        char_id='甲', star=1, equips=[], slot=1)),
        BenchSlot(kind='bookcard')])
    assert len(out) == 1 and isinstance(out[0].action, CwActionOpenBookcardParam)
    assert out[0].action.slot == 2
    # 优先序:卡先于箱(旧「入口清场先于观察」全局序)
    out = _emit_with_bench([BenchSlot(kind='bookcard'),
                            BenchSlot(kind='supply_box')])
    assert isinstance(out[0].action, CwActionOpenBookcardParam)


def test_entry_box_tome_arms_read_benchview_kind():
    """回归锁:开箱/开典籍臂与卡片臂同读容器 BenchView.slots kind
    (历史隐患申报:臂曾读 legacy ``bench_slots_of`` 元素 .kind——legacy
    换算把占位件压成 is_item_slot 布尔,元素无 kind 属性,bench 非空即
    AttributeError)。本锁钉死 box/tome 臂在真 kind 载荷上照常命中。"""
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


def test_bench_slot_bookcard_kind_roundtrip_as_item_placeholder():
    """容器 kind 细分往返:bookcard 槽经 legacy 换算 = 占位件
    is_item_slot 旗标——部署装配点识别线/占位恒拒防线消费同
    旗标;占席语义不变(kind ≠ empty 占 1 槽,席空数派生同源)。"""
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1,
                                              equips=[], slot=1)),
             BenchSlot(kind='bookcard')]
    slots += [BenchSlot(kind='empty')] * 7
    view = BenchView(slots=slots, capacity=9)
    legacy = bench_slots_to_legacy(view)
    assert legacy[0] is not None and legacy[0].char_id == '甲'
    assert legacy[1].is_item_slot
    # 占席语义:bookcard 占 1 槽,席空数派生同源(9−2=7)
    from test.sr_od.application.currency_war._cw_helpers import cw4_session
    _gs = game_state_of(cw4_session())
    _sig = ChannelSig(family='obs', actor='CwScreenPrep', mode='read')
    _gs.observe(_gs.bench, view, sig=_sig)
    assert bench_free_slots(_gs) == 7


# ===== CwActionDeployMoveParam 帧投影占用集(改动三审 代-1 应修行为锁)=====

def test_deploymove_projection_records_resolved_row():
    """CwActionDeployMoveParam 容器逻辑态载荷直落锁(落位载荷契约改造;
    原「deployed_place 首空单一源 fallback」锁随首空位退役翻面):断言
    容器写侧按载荷 (to_row, to_slot) 直落——目标有人 = 交换(被占位者
    回源 bench 槽),载荷槽空 = 放置,源槽空 = 陈旧提案零写。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    from sr_od.application.currency_war.kernel.cw_game_state import (
        bench_slots_of,
        game_state_of,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import CwActionDeployMoveParam
    session = cw4_session()
    gs = game_state_of(session)
    _sig = ChannelSig(family='obs', actor='synthesize_from_game_state',
                      mode='synthesized')
    _logic = ChannelSig(family='logic_action', actor='CwScreenPrep')
    _slots = [BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1,
                                               equips=[], slot=3))]
    _slots += [BenchSlot(kind='empty') for _ in range(8)]
    gs.observe(gs.bench, BenchView(slots=_slots, capacity=9), sig=_sig)
    # 前排满(4 人):载荷指前排 2 号(丙1 占位)→ 交换,甲落 2 号、
    # 丙1 回源 bench 槽 3
    gs.observe(gs.front_row, [Unit(char_id=f'丙{i}', star=1, equips=[],
                                   slot=i + 1) for i in range(4)],
               sig=_sig)
    report_action_deploy_move_param(gs, CwActionDeployMoveParam(bench_idx=0,
                                                   to_row='front',
                                                   to_slot=2,
                                                   faction=''),
                                    sig=_logic)
    dep = deployed_slots_of(gs)
    assert dep[1] is not None and dep[1].char_id == '甲', \
        '载荷直落:落参数指定槽(to_slot=2 → 表下标 1)'
    assert [d.char_id for i, d in enumerate(dep[:4]) if i != 1] \
        == ['丙0', '丙2', '丙3'], '交换只动目标槽,其余占位不受波及'
    _b = bench_slots_of(gs)[0]
    assert _b is not None and _b.char_id == '丙1', \
        '交换语义:被占位角色回发射者源 bench 槽'
    # 载荷槽空 = 放置(前排 1 号被乙占,载荷指 2 号空槽 → 照落 2 号)
    gs2 = game_state_of(cw4_session())
    gs2.observe(gs2.bench, BenchView(slots=_slots, capacity=9), sig=_sig)
    gs2.observe(gs2.front_row, [Unit(char_id='乙', star=1, equips=[],
                                     slot=1)], sig=_sig)
    report_action_deploy_move_param(gs2, CwActionDeployMoveParam(bench_idx=0,
                                                    to_row='front',
                                                    to_slot=2,
                                                    faction=''),
                                    sig=_logic)
    dep2 = deployed_slots_of(gs2)
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
    2026-09-18-screen-op-flat-report)——弹窗不在 = fail 交回外循环重识别
    (外循环按下一帧画面重分发自愈;开卡缺位由备战词表
    CwActionOpenBookcardParam 链承接)。选卡成功链的行为面由决策链降级锁
    承重,本锁不重复。"""
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


# ===== CwScreenExpertInvite 决策链异常降级(三姊妹 handler catch→fallback
# ===== 姿态对齐;兜底 = kernel 直调同无 match else 分支,现金为王语义)=====

def test_expert_invite_decision_chain_error_falls_cash(test_context,
                                                       monkeypatch):
    """局内决策链 decide_expert_invite 抛异常 → 异常不出 op,落「现金为王」
    兜底(kernel 直调同无 match else 分支),round 照常机械交回(与
    fortune/equip 两姊妹 handler 的 catch→fallback 防御姿态对齐;补丁前该
    链异常直接冒出 op 中断本轮)。写槽(弹窗载体)已由观察 node report 落
    容器(两 node 形态,迭代 2026-09-18-screen-op-flat-report):本锁经
    读屏函数注入点驱动观察 node(卡羁绊/板面读链桩)装载 obs,再驱动
    决策动作 node。本例输入:卡羁绊有读数但与板面无同线 → 兜底 kernel
    判据 ③ 落现金为王。红 = 异常逃逸 / report 断流 / 落点漂移 / 缺坐标
    fail 交回。"""
    from test.harness.fixture_controller import fast_sleep
    from test.sr_od.application.currency_war._cw_helpers import Area, run_node

    from sr_od.application.currency_war.kernel import cw_obs_core
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.obs import cw_observation
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_expert_invite as mod,
    )

    def _boom():
        raise RuntimeError('决策链注入异常(测试)')

    session = StrategySession()
    match = SimpleNamespace(
        session=session,
        strategy=SimpleNamespace(decide_expert_invite=_boom))
    match.gs = game_state_of(match.session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = mod.CwScreenExpertInvite(test_context)
    # 卡羁绊读数在位但与板面({'仙舟': 2})无同线 → 兜底 kernel 判据落 -1
    monkeypatch.setattr(mod, '_resolve_card_bonds',
                        lambda ctx, screen, a: '能量' if a == '卡-1' else None)
    monkeypatch.setattr(cw_observation, 'read_board',
                        lambda ctx, screen: {'仙舟': 2})
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'screenshot', lambda: object(), raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: Area(True))
    rs = run_node(test_context, op, op.observe)
    assert rs.is_success, f'在门观察 success:{rs!r}'
    assert match.gs.expert_invite.value is not None, (
        '观察上报落容器(ExpertInvitePayload 经 report 写槽)')
    _pts = {'卡-1': Point(300, 400), mod.CASH_AREA: Point(500, 900)}
    monkeypatch.setattr(cw_obs_core, 'area_center',
                        lambda ctx, name, screen: _pts.get(name))
    # pick-op-unify:点卡即选迁入 CwActionPickExpertInviteOp;本锁桩派发
    # 捕获(param/env),机械链行为锁 = test_cw_unified_action_4。
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
    with fast_sleep(op):   # 轮间等待桩(零真实等待)
        rs = op.act()
    assert not rs.is_success and '点击已发' in (rs.status or ''), (
        f'异常被吸收,round 照常机械交回:{rs!r}')
    assert len(dispatches) == 1, f'选卡链恰一次派发:{dispatches!r}'
    assert dispatches[0].param.idx == -1, (
        f'兜底应落「现金为王」(idx=-1):{dispatches[0].param!r}')
    assert (dispatches[0].env.target.x, dispatches[0].env.target.y) == (
        500, 900), f'兜底应落「现金为王」area:{dispatches[0].env.target!r}'
