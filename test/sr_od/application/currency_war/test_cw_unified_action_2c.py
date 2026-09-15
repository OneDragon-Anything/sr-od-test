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
    ChannelSig,
    apply_prep_action_logic,
    board_state_of,
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
    """开卡即腾席(R10 视觉域):书册卡无独立载荷列表字段(箱/典籍有
    boxes/tomes,书册卡占席事实只在 free_bench_slots 现读口径)→ 摘件 =
    腾席 +1(与 heavy 现读 slot_occupied 扫描同式);其余视觉域字段不动;
    容器 GameState 零写(apply_prep_action_logic 集外动作型直接返回)。"""
    stub = CwScreenPrep.__new__(CwScreenPrep)   # 绕道构造(无框架状态)
    stub._session = lambda: None
    obs = kpa.PrepObservation(free_bench_slots=5, tomes=[(3, Point(1, 1))])
    out = CwScreenPrep._project_prep_obs(stub, OpenBookcard(), obs)
    assert out.free_bench_slots == 6
    # 其余视觉域字段不动(Point 无结构等价,按坐标元组比对)
    assert [(t[0], t[1].x, t[1].y) for t in out.tomes] == [(3, 1, 1)]
    # 容器零写:kernel 写口对本动作直接返回(视觉域推进,落点 = 备战观察帧)
    bs = board_state_of(None)
    apply_prep_action_logic(bs, OpenBookcard(), produced_by='T', sig=_SIG)
    assert bs.write_seq == 0


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
    assert not hasattr(op, 'open_card')
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'screenshot', lambda: object(), raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: Area(False))
    rs = run_node(test_context, op, op.choose)
    assert not rs.is_success and '弹窗未现' in (rs.status or '')
