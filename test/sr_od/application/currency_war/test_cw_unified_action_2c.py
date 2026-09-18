"""CW 统一动作工厂 批2c 锁面(书册卡开卡归位 R10)。

出处 = docs/develop/sr_od/application/currency_war/changes/
2026-09-14-unified-action-factory/landing.md §3.2c 判据 +
design.md §2.6 R10 条款。规则正本 = flow/action-logic-state.md §3.7。

锁面全部为运行时行为锁(源码扫描测试禁止,AGENTS.md §10.4);
kernel/执行器级用桩宿主,零真实 IO(harness 惯例同 test_cw_unified_action_2a)。
"""

from __future__ import annotations

import time
from types import SimpleNamespace

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel import cw_prep_actions as kpa
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    Unit,
    apply_prep_action_logic,
    bench_free_slots,
    deployed_slots_of,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CW_ACTION_TYPES,
    OpenBookcard,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')


# ===== 词表行 + F3 注册行(判据:OpenBookcard 词表行 + 注册行在册)=====

def test_open_bookcard_registered_and_validated():
    """R10 归位:OpenBookcard 在统一词表白名单(漏登记先例 OpenTome:
    漏登记时执行面 validate 拒「未知动作类型」,动作从未真正执行);F3
    静态参数域与 OpenBox/OpenTome 同形(slot=None 或 1..备战栏槽位)。"""
    assert OpenBookcard in CW_ACTION_TYPES
    from sr_od.application.currency_war import prep_actions as pa
    ex = pa.PrepActionExecutor.__new__(pa.PrepActionExecutor)
    ex._bench_pts = [Point(i * 10, i * 10) for i in range(9)]
    assert ex.validate(OpenBookcard()) is None
    assert ex.validate(OpenBookcard(slot=9)) is None
    err = ex.validate(OpenBookcard(slot=10))
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
    slot 对位不中 / 识别空 = 未发出零点击(与 OpenBox/OpenTome 同形)。
    动画等待值家族单一源(_OVERLAY_ANIM_WAIT_S;判效交下一帧观察)。"""
    from sr_od.application.currency_war.obs import cw_identity_obs
    monkeypatch.setattr(cw_identity_obs, 'find_bookcards',
                        lambda screen, slots: [(2, Point(123, 456))])
    monkeypatch.setattr(cw_identity_obs, '_ctx_slots',
                        lambda ctx, name, n: [])
    monkeypatch.setattr(time, 'sleep', lambda s: None)   # 动画等待桩(零真实等待)
    controller = _RecordingController()
    ex = _make_executor(controller, [])
    detail, emitted = ex._open_bookcard(OpenBookcard())
    assert emitted and '槽2' in detail
    assert [(p.x, p.y) for p in controller.clicks] == [(123, 456)]
    assert len(controller.moves) == 1   # bug#1 缓解口径:先移后点
    # slot 指定但实读无该槽 → 未发出零点击(对位语义同 _open_box)
    controller2 = _RecordingController()
    ex2 = _make_executor(controller2, [])
    detail2, emitted2 = ex2._open_bookcard(OpenBookcard(slot=5))
    assert not emitted2 and controller2.clicks == []
    # 识别空 → 未发出(交回外循环重观察重派)
    monkeypatch.setattr(cw_identity_obs, 'find_bookcards',
                        lambda screen, slots: [])
    controller3 = _RecordingController()
    ex3 = _make_executor(controller3, [])
    detail3, emitted3 = ex3._open_bookcard(OpenBookcard())
    assert not emitted3 and controller3.clicks == []


# ===== 逻辑态摘件对账(判据:开卡后槽位表与实机一致)=====

def test_open_bookcard_logic_state_frees_slot():
    """开卡即腾席(阶段 3.5 容器版;原黑板 free_bench_slots +1 语义随
    _project_prep_obs 退役):书册卡槽(容器 kind='supply_box',读链 is_item_slot
    并入口径)经 OpenBookcard 腾席 = 槽 kind → empty——bench_free_slots
    派生 +1(容器读口单点),其余槽不动。"""
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
              BenchSlot(kind='supply_box')]
    _slots += [BenchSlot(kind='empty') for _ in range(7)]
    gs.observe(gs.bench, BenchView(slots=_slots, capacity=9), sig=_sig)
    before = bench_free_slots(gs)
    assert before == 7
    apply_prep_action_logic(gs, OpenBookcard(slot=2), produced_by='T',
                            sig=ChannelSig(family='logic_action',
                                           actor='CwScreenPrep'))
    assert gs.bench.value.slots[1].kind == 'empty'
    assert bench_free_slots(gs) == before + 1


# ===== 链拆接线锁(判据:预清场改产 OpenBookcard 经执行器 + 交回)=====

def test_clear_prep_cards_emits_open_bookcard_and_signals_handback(monkeypatch):
    """链拆编排:`_clear_prep_cards` 书册卡腿改产词表动作 OpenBookcard 经
    执行器发射(单一发射口,遥测动作行 OpenBookcard 在册)且返回 True
    (调用方必须立即交回——弹窗已弹,heavy 观察禁读弹窗帧);识别空 =
    False 照常续跑。原 journal 包装全链路径退役(现役 journal_wrapped_
    execute 消费面归零)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    from sr_od.application.currency_war.obs import cw_identity_obs
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep as pd_mod,
    )
    monkeypatch.setattr(cw_identity_obs, 'find_trial_reveal_cards',
                        lambda screen, slots: [])
    monkeypatch.setattr(cw_identity_obs, 'find_bookcards',
                        lambda screen, slots: [(2, Point(10, 20))])
    monkeypatch.setattr(cw_identity_obs, '_ctx_slots',
                        lambda ctx, name, n: [])
    monkeypatch.setattr(cw_obs_core, 'is_prep_like_frame',
                        lambda ctx, screen: True)

    d = pd_mod.CwScreenPrep.__new__(pd_mod.CwScreenPrep)   # 绕道构造
    d.ctx = SimpleNamespace(controller=SimpleNamespace(
        mouse_move=lambda p: None, click=lambda p: None))
    monkeypatch.setattr(d, 'screenshot', lambda: object())

    executed: list = []

    class _Ex:
        def validate(self, action):
            return None

    d._executor = _Ex()

    def _fake_act(action, obs=None):
        executed.append(action)

    d._act_execute = _fake_act

    assert d._clear_prep_cards() is True
    assert len(executed) == 1
    assert type(executed[0]) is OpenBookcard
    assert executed[0].slot == 2
    # 识别空 → False(调用方续跑 heavy 观察,书册卡腿静默跳过)
    monkeypatch.setattr(cw_identity_obs, 'find_bookcards',
                        lambda screen, slots: [])
    assert d._clear_prep_cards() is False
    assert len(executed) == 1


# ===== DeployMove 帧投影占用集(改动三审 代-1 应修行为锁)=====

def test_deploymove_projection_records_resolved_row():
    """DeployMove 容器逻辑态首空落位 fallback 锁(阶段 3.5 宿主迁移版;
    原黑板占用集 fallback 记行锁随 _project_prep_obs 退役,新锁断言容器
    ``deployed_place`` 首空单一源的 fallback 语义:首选排满落位 fallback
    另一排,记实落排)。"""
    from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar
    from sr_od.application.currency_war.kernel.cw_vocab import DeployMove
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    session = cw4_session()
    gs = game_state_of(session)
    _sig = ChannelSig(family='obs', actor='synthesize_from_game_state',
                      mode='synthesized')
    _logic = ChannelSig(family='logic_action', actor='CwScreenPrep')
    _slots = [BenchSlot(kind='unit', unit=Unit(char_id='甲', star=1,
                                               equips=[], slot=3))]
    _slots += [BenchSlot(kind='empty') for _ in range(8)]
    gs.observe(gs.bench, BenchView(slots=_slots, capacity=9), sig=_sig)
    # 前排满(4 人)fallback 后排:实落后排(记实落排语义由 deployed_place
    # 首空单一源承载)
    gs.observe(gs.front_row, [Unit(char_id=f'丙{i}', star=1, equips=[],
                                   slot=i + 1) for i in range(4)],
               sig=_sig)
    apply_prep_action_logic(gs, DeployMove(bench_idx=0, to_row='front',
                                           faction=''),
                            produced_by='T', sig=_logic)
    dep = deployed_slots_of(gs)
    assert dep[4] is not None and dep[4].char_id == '甲'   # 后排首槽
    # 前排保持原 4 人(不被新增污染;fallback 实落排语义)
    assert [d.char_id for d in dep[:4]] == ['丙0', '丙1', '丙2', '丙3']
    # 前排有空位:首选排照落(回归面)
    gs2 = game_state_of(cw4_session())
    gs2.observe(gs2.bench, BenchView(slots=_slots, capacity=9), sig=_sig)
    gs2.observe(gs2.front_row, [Unit(char_id='乙', star=1, equips=[],
                                     slot=1)], sig=_sig)
    apply_prep_action_logic(gs2, DeployMove(bench_idx=0, to_row='front',
                                            faction=''),
                            produced_by='T', sig=_logic)
    dep2 = deployed_slots_of(gs2)
    assert dep2[1] is not None and dep2[1].char_id == '甲'   # 首空 = 表 1 位(0 位是乙)
    # 源槽无件(bench_idx 越界空槽)= 陈旧提案,本口零写
    before = gs2.write_seq
    apply_prep_action_logic(gs2, DeployMove(bench_idx=5, to_row='front',
                                            faction=''),
                            produced_by='T', sig=_logic)
    assert gs2.write_seq == before


# ===== CwScreenExpertInvite 收缩(判据:无开卡残留,入口=弹窗已开)=====

def test_expert_invite_entry_select_only(test_context, monkeypatch):
    """收缩为弹窗画面 op:open_card 节点拆退役(属性不在场);入口门 =
    弹窗已开单一形态——弹窗不在 = fail 交回外循环重识别(外循环按下一帧
    画面重分发自愈;开卡缺位由备战词表 OpenBookcard 链承接)。选卡成功链
    的行为面由 obs_arch step3 生命周期段迹锁承重,本锁不重复。"""
    from test.sr_od.application.currency_war._cw_helpers import (
        Area,
        run_node,
        uninstall_ports,
    )

    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_expert_invite as mod,
    )
    uninstall_ports(monkeypatch)   # 生产缺省形态(旧路径直连)
    op = mod.CwScreenExpertInvite(test_context)
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'screenshot', lambda: object(), raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: Area(False))
    rs = run_node(test_context, op, op.choose)
    assert not rs.is_success and '弹窗未现' in (rs.status or '')


# ===== CwScreenExpertInvite 决策链异常降级(三姊妹 handler catch→fallback
# ===== 姿态对齐;兜底 = kernel 直调同无 match else 分支,现金为王语义)=====

def test_expert_invite_decision_chain_error_falls_cash(test_context,
                                                       monkeypatch):
    """局内决策链(write_logic → decide_expert_invite)任一环抛异常 → 异常
    不出 op,落「现金为王」兜底(kernel 直调同无 match else 分支),round
    照常机械交回(与 fortune/equip 两姊妹 handler 的 catch→fallback 防御
    姿态对齐;补丁前该链异常直接冒出 op 中断本轮)。本例输入:卡羁绊有读数
    但与板面无同线 → 兜底 kernel 判据 ③ 落现金为王。红 = 异常逃逸 /
    落点漂移 / 缺坐标 fail 交回。"""
    from test.harness.fixture_controller import fast_sleep

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
    _pts = {'卡-1': Point(300, 400), mod.CASH_AREA: Point(500, 900)}
    monkeypatch.setattr(cw_obs_core, 'area_center',
                        lambda ctx, name, screen: _pts.get(name))
    clicks: list[Point] = []
    monkeypatch.setattr(
        test_context, 'controller',
        SimpleNamespace(mouse_move=lambda p: None,
                        click=lambda p: clicks.append(p)), raising=False)
    with fast_sleep(op):   # 选卡动画等待/轮间等待桩(零真实等待)
        rs = op._handle_overlay(object())
    assert not rs.is_success and '点击已发' in (rs.status or ''), (
        f'异常被吸收,round 照常机械交回:{rs!r}')
    assert [(p.x, p.y) for p in clicks] == [(500, 900)], (
        f'兜底应落「现金为王」area:{[(p.x, p.y) for p in clicks]}')
