"""CW 覆盖层弹窗/屏上动作 op 测试面(pick 全族 + 专家邀请函 + 刷新零效果
对账)。

规则正本 = flow/action_ops.md 与 screens/op-layer.md §1.1「选择坐标
观察上报」+ §1.3(决策出口守卫)。测试面三组(全部运行时行为测试,源码
扫描测试禁止,AGENTS.md §10.4;桩宿主零真实 IO):

- **pick op 机械行为**(五屏确认链,桩宿主记录点击):确认钮查找
  全族统一(用户裁定 2026-09-22)、选中点击坐标 = 容器单点源
  (``*_opts_xy``/payload,缺/越界 = 守卫断言,禁 env.target 回退、
  禁坐标现算)、轮次结果经 env.round_result 旁路回传、自上报接线;
- **专家邀请函**(画面 op 入口单一形态 + 决策出口守卫测试组:异常传播/
  返回契约/值域/正路两态/局外无早退支 + report 双写门);
- **投资环境刷新零效果留证**(证据齐 → 缺陷落台账 + 消费即清)。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_events import (
    MegastarPick,
    PartnerPick,
    PlannerPick,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickBoxCardParam,
    CwActionPickEncounterParam,
    CwActionPickExpertInviteParam,
    CwActionPickFortuneParam,
    CwActionPickInvestEnvParam,
    CwActionPickInvestStrategyParam,
    CwActionPickMegastarParam,
    CwActionPickStarTomeParam,
    CwActionPickSupplyParam,
    CwActionPickWishTrialParam,
)
from sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_env import (
    OverlayPickExecEnv,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_box_card_action import (
    CwActionPickBoxCardOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_encounter_action import (
    CwActionPickEncounterOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_expert_invite_action import (
    CwActionPickExpertInviteOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_fortune_action import (
    CwActionPickFortuneOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_invest_action import (
    CwActionPickInvestOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_megastar_action import (
    CwActionPickMegastarOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_partner_action import (
    CwActionPickPartnerOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_planner_action import (
    CwActionPickPlannerOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_star_tome_action import (
    CwActionPickStarTomeOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_supply_action import (
    CwActionPickSupplyOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_wish_trial_action import (
    CwActionPickWishTrialOp,
)
from sr_od.application.currency_war.telemetry import defects as cw_defects

# ============================================================ 桩宿主


class _RecordingController:
    def __init__(self) -> None:
        self.moves: list[Point] = []
        self.clicks: list[tuple[Point, float]] = []

    def mouse_move(self, p: Point) -> None:
        self.moves.append(p)

    def click(self, p: Point, press_time: float = 0.1) -> None:
        self.clicks.append((p, press_time))


class _NoSleep:
    """模块内 ``time`` 替身:机械等待记录不真睡(替身随模块迁移)."""

    def __init__(self) -> None:
        self.skipped: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.skipped.append(seconds)


def _screen_loader_none() -> SimpleNamespace:
    """screen_loader 桩:get_screen 恒 None → area_center 走缺失臂
    (None;供「area 缺失 = 显式失败禁兜底坐标」语义测试)。"""
    return SimpleNamespace(get_screen=lambda name: None)


@pytest.fixture()
def no_pick_sleep(monkeypatch):
    """pick 族各 op 模块与确认收尾助手的机械等待替身(零真睡;拆分后
    各 op 单文件,逐模块打桩)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_pick_box_card_action,
        cw_pick_encounter_action,
        cw_pick_expert_invite_action,
        cw_pick_fortune_action,
        cw_pick_invest_action,
        cw_pick_megastar_action,
        cw_pick_partner_action,
        cw_pick_planner_action,
        cw_pick_star_tome_action,
        cw_pick_supply_action,
        cw_pick_wish_trial_action,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        _overlay_confirm,
    )
    sleeper = _NoSleep()
    for mod in (cw_pick_box_card_action, cw_pick_encounter_action,
                cw_pick_expert_invite_action, cw_pick_fortune_action,
                cw_pick_invest_action, cw_pick_megastar_action,
                cw_pick_partner_action, cw_pick_planner_action,
                cw_pick_star_tome_action, cw_pick_supply_action,
                cw_pick_wish_trial_action):
        monkeypatch.setattr(mod, 'time', sleeper)
    monkeypatch.setattr(_overlay_confirm, 'time', _NoSleep())
    return sleeper


# ============================================================ pick op 机械行为


def test_encounter_pick_op_clicks_card_then_confirm(no_pick_sleep, monkeypatch):
    """遭遇确认链:idx=1 → 建档「遭遇卡-其二」area 取点点选 → 「按钮-选择」
    area 查找点击确认(确认钮查找全族统一,用户裁定 2026-09-22);轮次结果经
    env.round_result 旁路回传。卡位 area 缺失 = 显式 round_fail 零点击
    (禁兜底坐标,失败臂)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_pick_encounter_action as pick_mod

    rs = SimpleNamespace(sentinel='rs')
    ctrl = _RecordingController()
    confirm_calls: list[tuple] = []
    op = SimpleNamespace(
        ctx=SimpleNamespace(controller=ctrl, screen_loader=_screen_loader_none()),
        screenshot=lambda: 'shot',
        round_by_find_and_click_area=lambda shot, s, a, **kw:
            confirm_calls.append((s, a, kw)) or rs)
    env = OverlayPickExecEnv(op=op)
    # 命中臂:建档 area_center 命中「遭遇卡-其二」中心。
    monkeypatch.setattr(pick_mod, 'area_center',
                        lambda ctx, name, screen=None: Point(1288, 550))
    assert CwActionPickEncounterOp(env.op.ctx, CwActionPickEncounterParam(idx=1), env=env).run().is_success
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [(1288, 550)]
    assert len(ctrl.moves) == len(ctrl.clicks)   # 选中点击前 bug#1 缓解 mouse_move
    assert confirm_calls == [('货币战争-遭遇节点', '按钮-选择',
                              {'success_wait': 1.0})]
    assert env.round_result is rs

    # 失败臂:卡位 area 缺失(get_screen 恒 None)→ round_fail 零点击
    # 零确认步(禁兜底坐标静默点击);失败轮次结果经旁路回传。
    monkeypatch.setattr(pick_mod, 'area_center',
                        lambda ctx, name, screen=None: None)
    ctrl2 = _RecordingController()
    confirm_calls2: list[tuple] = []
    op2 = SimpleNamespace(
        ctx=SimpleNamespace(controller=ctrl2, screen_loader=_screen_loader_none()),
        screenshot=lambda: 'shot',
        round_by_find_and_click_area=lambda shot, s, a, **kw:
            confirm_calls2.append((s, a, kw)) or rs)
    env2 = OverlayPickExecEnv(op=op2)
    rs2 = CwActionPickEncounterOp(env2.op.ctx, CwActionPickEncounterParam(idx=1), env=env2).run()
    assert not rs2.is_success, '卡位 area 缺失 = 显式 round_fail(禁兜底坐标)'
    assert ctrl2.clicks == [] and ctrl2.moves == [], '失败臂零点击零移动'
    assert confirm_calls2 == [], '失败臂不进确认步'
    assert env2.round_result is rs2, '失败轮次结果经旁路回传'


def test_supply_pick_op_clicks_target_and_confirms(no_pick_sleep):
    """补给确认链:点卡 → 「按钮-确认」area 确认(机械半零判效);
    补给确认无到账登记写边(入栏/后果腿 =
    ``report_action_pick_supply_param`` 即时单相,行为测试见
    test_supply);本测试只校验机械点击面。"""
    confirm_calls: list[tuple] = []
    ctrl = _RecordingController()
    op = SimpleNamespace(
        ctx=SimpleNamespace(controller=ctrl),
        screenshot=lambda: 'shot',
        round_by_find_and_click_area=lambda shot, s, a, **kw:
            confirm_calls.append((s, a, kw)))
    session = StrategySession()
    env = OverlayPickExecEnv(
        op=op, match=SimpleNamespace(session=session),
        target=Point(500, 400),
        picked={'char': '希儿', 'equip': '星币收集器', 'has_diamond': True})
    assert CwActionPickSupplyOp(env.op.ctx, CwActionPickSupplyParam(idx=0), env=env).run().is_success
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [(500, 400)]
    assert confirm_calls == [('货币战争-补给', '按钮-确认',
                              {'success_wait': 1.5})]
    # 补给确认无到账登记写边(局外 ctx 无 cw_match,即时上报同跳过;
    # equips 保持开局种子 [] ,未混入选中装备名)。
    from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
    assert game_state_of(session).equips.value == []


def test_megastar_pick_op_clicks_confirm_once(no_pick_sleep):
    """巨星确认半:「按钮-确认选择」area 查找点击单发(确认钮查找全族
    统一,用户裁定 2026-09-22)。"""
    rs = SimpleNamespace(sentinel='rs')
    ctrl = _RecordingController()
    confirm_calls: list[tuple] = []
    op = SimpleNamespace(
        ctx=SimpleNamespace(controller=ctrl,
                            screen_loader=_screen_loader_none()),
        screenshot=lambda: 'shot',
        round_by_find_and_click_area=lambda shot, s, a, **kw:
            confirm_calls.append((s, a, kw)) or rs)
    _env = OverlayPickExecEnv(op=op)
    assert CwActionPickMegastarOp(op.ctx, MegastarPick(idx=0), env=_env).run().is_success
    assert confirm_calls == [('货币战争-盛会之星', '按钮-确认选择',
                              {'success_wait': 0.9})]
    assert ctrl.clicks == []   # 确认零直接坐标点击(area 查找点击承责)


def test_megastar_pick_op_select_clicks_container_xy(no_pick_sleep):
    """巨星选中半容器取点(选择坐标观察上报收敛,规范 = screens/
    op-layer.md §1.1「选择坐标观察上报」+ action_ops.md §1 增补 5):
    need_select=True → 点候选(点击坐标 = 容器 ``megastar_opts[param.idx].xy``,
    env 零机械下标零 target 传参)→ 确认钮(area 查找点击,全族统一)。
    红 = 选中半
    回潮消费 env.target / 容器取点断流 / 点击序漂移。"""
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        game_state_of,
    )

    ctrl = _RecordingController()
    session = StrategySession()
    _sig = ChannelSig(family='logic_action', actor='test', mode='compute')
    game_state_of(session).write_logic(
        game_state_of(session).megastar_opts,
        [MegastarOption(idx=0, char_id='花火', xy=(822, 333)),
         MegastarOption(idx=1, char_id='星期日', xy=(1061, 333))],
        produced_by='test', sig=_sig)
    rs = SimpleNamespace(sentinel='rs')
    ctx = SimpleNamespace(
        controller=ctrl,
        cw_match=SimpleNamespace(session=session))
    op = SimpleNamespace(ctx=ctx, screenshot=lambda: 'shot',
                         round_by_find_and_click_area=lambda shot, s, a, **kw: rs)
    env = OverlayPickExecEnv(op=op, need_select=True)
    assert CwActionPickMegastarOp(ctx, CwActionPickMegastarParam(idx=1),
                                  env=env).run().is_success
    # 点击序 = 选中位(容器 megastar_opts[param.idx].xy);确认 = area 查找
    # 点击(桩承接),零直接坐标点击。
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [(1061, 333)]
    assert len(ctrl.moves) == len(ctrl.clicks)


def test_partner_pick_op_pulses_select_then_confirm(no_pick_sleep):
    """伙伴脉冲链:未选中实证 → 点候选 + 「按钮-确认选择」area 查找点击
    确认(全族统一);脉冲计数与 pending 置位(画面 op 宿主状态经
    env.op 消费),轮次结果旁路回传。"""
    rs = SimpleNamespace(sentinel='rs', is_success=True)
    ctrl = _RecordingController()
    confirm_calls: list[tuple] = []
    op = SimpleNamespace(
        ctx=SimpleNamespace(controller=ctrl),
        screenshot=lambda: 'shot',
        _pick_point=Point(300, 300), _confirm_pulses=0, _confirm_pending=False,
        round_by_find_and_click_area=lambda shot, s, a, **kw:
            confirm_calls.append((s, a, kw)) or rs,
        round_retry=lambda **kw: rs)
    env = OverlayPickExecEnv(op=op, unselected=True)
    assert CwActionPickPartnerOp(env.op.ctx, PartnerPick(idx=0), env=env).run().is_success
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [(300, 300)]
    assert confirm_calls == [('货币战争-列车同行', '按钮-确认选择',
                              {'success_wait': 1.0, 'retry_wait': 1})]
    assert op._confirm_pulses == 1
    assert op._confirm_pending is True
    assert env.round_result is rs


def test_partner_pick_op_confirm_missing_retries_without_click(no_pick_sleep):
    """确认钮读缺 → 零点击 round_retry(脉冲计数不动;读缺分支语义)。"""
    rs_fail = SimpleNamespace(sentinel='fail', is_success=False)
    ctrl = _RecordingController()
    op = SimpleNamespace(
        ctx=SimpleNamespace(controller=ctrl),
        screenshot=lambda: 'shot',
        _pick_point=Point(300, 300), _confirm_pulses=2, _confirm_pending=False,
        round_by_find_and_click_area=lambda shot, s, a, **kw: rs_fail)
    env = OverlayPickExecEnv(op=op, unselected=False)
    assert CwActionPickPartnerOp(env.op.ctx, PartnerPick(idx=0), env=env).run().is_success
    assert ctrl.clicks == []
    assert op._confirm_pulses == 2   # 未点确认不计数
    assert env.round_result is rs_fail


def test_planner_pick_op_clicks_target_and_confirm(no_pick_sleep):
    """策划确认链:点卡(press_time 透传)→ 「按钮-骇入确认」area 查找
    点击确认(全族统一);轮次结果旁路回传。"""
    rs = SimpleNamespace(sentinel='rs')
    ctrl = _RecordingController()
    confirm_calls: list[tuple] = []
    op = SimpleNamespace(
        ctx=SimpleNamespace(controller=ctrl, screen_loader=_screen_loader_none()),
        CLICK_PRESS_TIME=0.15,
        screenshot=lambda: 'shot',
        round_by_find_and_click_area=lambda shot, s, a, **kw:
            confirm_calls.append((s, a, kw)) or rs)
    env = OverlayPickExecEnv(op=op, target=Point(700, 420))
    assert CwActionPickPlannerOp(env.op.ctx, PlannerPick(idx=1), env=env).run().is_success
    assert [(p.x, p.y, t) for p, t in ctrl.clicks] == [(700, 420, 0.15)]
    assert confirm_calls == [('货币战争-银狼升星', '按钮-骇入确认',
                              {'success_wait': 1.0})]
    assert env.round_result is rs


def test_invest_pick_op_clicks_target_confirms_and_self_reports(
        no_pick_sleep, monkeypatch):
    """投资确认链(投资两屏共用 op,拆类后两 param 类同指;即时上报契约):
    点选中位 → 「按钮-确认」area 查找点击确认(屏名按宿主屏类解析,全族
    统一)→ **按 param 类型立即自上报完整结果**(分步上报废
    除);轮次结果旁路回传;上报接线 = 机械链发出后恰一次。"""
    import sr_od.application.currency_war.operations.cw_op.cw_pick_invest_action as pick_mod

    rs = SimpleNamespace(sentinel='rs')
    ctrl = _RecordingController()
    confirm_calls: list[tuple] = []

    class _Host(SimpleNamespace):
        SCREEN_NAME = '货币战争-投资环境'   # round_by_find_and_click_area 屏名解析键

    op = _Host(ctx=SimpleNamespace(controller=ctrl),
               screenshot=lambda: 'shot',
               round_by_find_and_click_area=lambda shot, s, a, **kw:
                   confirm_calls.append((s, a, kw)) or rs)
    env = OverlayPickExecEnv(op=op, idx=2, target=Point(900, 450))
    reported: list = []
    monkeypatch.setattr(pick_mod, 'game_state_from_ctx',
                        lambda ctx: SimpleNamespace(sentinel='gs'))
    monkeypatch.setattr(pick_mod, 'report_action_pick_invest_env_param',
                        lambda gs, param, sig, **kw:
                        reported.append((gs, param, sig))
                        or SimpleNamespace(world_decl=None))
    assert CwActionPickInvestOp(env.op.ctx, CwActionPickInvestEnvParam(idx=2),
                                env=env).run().is_success
    # 点击序 = 选中位;确认 = area 查找点击(桩承接),零直接坐标点击。
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [(900, 450)]
    assert confirm_calls == [('货币战争-投资环境', '按钮-确认',
                              {'success_wait': 1.0})]
    assert env.round_result is rs
    # 即时上报接线(机械链发出后恰一次;param 原样透传;Env param → env 支)。
    assert len(reported) == 1 and reported[0][1].idx == 2

    # 策略 param → strategy 支(类型机械分派测试)。
    reported_st: list = []
    monkeypatch.setattr(pick_mod, 'report_action_pick_invest_strategy_param',
                        lambda gs, param, sig, **kw:
                        reported_st.append((gs, param, sig))
                        or SimpleNamespace(world_decl=None))
    env_st = OverlayPickExecEnv(op=op, idx=0, target=Point(700, 450))
    assert CwActionPickInvestOp(env_st.op.ctx,
                                CwActionPickInvestStrategyParam(idx=0),
                                env=env_st).run().is_success
    assert len(reported_st) == 1 and reported_st[0][1].idx == 0


def test_fortune_pick_op_clicks_card_confirms_and_self_reports(
        no_pick_sleep, monkeypatch):
    """命运卜者确认链(坐标随报收敛后):点卡坐标 = 按下标自容器
    ``fortune_opts_xy`` 读(缺/越界 = 守卫断言,二态见下一测试)→
    「按钮-确认选择」area 查找点击确认(全族统一);轮次结果旁路回传;
    自上报接线。env 停喂 idx/target(已收敛屏)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_pick_fortune_action as pick_mod

    rs = SimpleNamespace(sentinel='rs')
    ctrl = _RecordingController()
    confirm_calls: list[tuple] = []
    op = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl,
                                             screen_loader=_screen_loader_none()),
                         screenshot=lambda: 'shot',
                         round_by_find_and_click_area=lambda shot, s, a, **kw:
                             confirm_calls.append((s, a, kw)) or rs)
    seed_pts = [(510, 480), (900, 480), (1290, 480)]   # 容器坐标种子(3 槽定值)
    _gs = SimpleNamespace(fortune_opts_xy=SimpleNamespace(value=list(seed_pts)))
    monkeypatch.setattr(pick_mod, 'game_state_from_ctx', lambda ctx: _gs)
    reported: list = []
    monkeypatch.setattr(pick_mod, 'report_action_pick_fortune_param',
                        lambda gs, param, sig: reported.append(param)
                        or SimpleNamespace(world_decl=None))
    env = OverlayPickExecEnv(op=op)
    assert CwActionPickFortuneOp(env.op.ctx, CwActionPickFortuneParam(idx=1),
                                 env=env).run().is_success
    # 点击点 = 容器值(param.idx 对槽),零 env.target 依赖。
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [seed_pts[1]]
    assert confirm_calls == [('货币战争-命运卜者强化', '按钮-确认选择',
                              {'success_wait': 1.0})]
    assert env.round_result is rs
    assert len(reported) == 1 and reported[0].idx == 1


def test_fortune_pick_op_container_guard_rejects_without_click(
        no_pick_sleep, monkeypatch):
    """命运卜者取点守卫二态测试(坐标随报条款;A 类伴随域无 None 元素,
    守卫二态 = 缺域/越界):容器 fortune_opts_xy 缺席/空、param.idx 越界
    → AssertionError 且零点击零上报(禁坐标现算回退)。红 = 现算回退 /
    守卫缺位静默续跑。"""
    import sr_od.application.currency_war.operations.cw_op.cw_pick_fortune_action as pick_mod

    rs = SimpleNamespace(sentinel='rs')
    # (gs 桩 fortune_opts_xy.value,param.idx,消息片段)
    cases = [
        (None, 0, '缺席/空'),   # 容器缺域(Field 恒未观察 None)
        ([], 0, '缺席/空'),     # 容器空
        ([(510, 480), (900, 480), (1290, 480)], 3, '越界'),   # 槽数 = 3
    ]
    for xy_value, idx, fragment in cases:
        ctrl = _RecordingController()
        op = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl),
                             screenshot=lambda: 'shot',
                             round_by_find_and_click_area=lambda shot, s, a,
                             **kw: rs)
        _gs = SimpleNamespace(
            fortune_opts_xy=SimpleNamespace(value=xy_value))
        monkeypatch.setattr(pick_mod, 'game_state_from_ctx',
                            lambda ctx, g=_gs: g)
        reported: list = []
        monkeypatch.setattr(pick_mod, 'report_action_pick_fortune_param',
                            lambda gs, param, sig, r=reported:
                                r.append(param))
        env = OverlayPickExecEnv(op=op)
        with pytest.raises(AssertionError, match=fragment):
            CwActionPickFortuneOp(env.op.ctx,
                                  CwActionPickFortuneParam(idx=idx),
                                  env=env).run()
        assert ctrl.clicks == [], f'守卫拦截({fragment})= 零点击'
        assert reported == [], f'守卫拦截({fragment})= 零上报'


def test_wish_trial_pick_op_clicks_card_area_confirms_and_self_reports(
        no_pick_sleep, monkeypatch):
    """祈愿试炼确认链(坐标随报收敛后):点卡坐标 = 按下标自容器
    ``wish_trial_opts_xy`` 读(缺/越界 = 守卫断言,二态见下一测试)→
    「按钮-确认选择」area 查找点击确认(全族统一);轮次结果旁路回传;
    自上报接线。env 停喂 idx/target(已收敛屏)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_pick_wish_trial_action as pick_mod

    rs = SimpleNamespace(sentinel='rs')
    ctrl = _RecordingController()
    confirm_calls: list[tuple] = []

    def _confirm_stub(shot, s, a, **kw):
        confirm_calls.append((s, a, kw))
        return rs

    op = SimpleNamespace(
        ctx=SimpleNamespace(controller=ctrl),
        screenshot=lambda: 'shot',
        round_by_find_and_click_area=_confirm_stub,
        round_retry=lambda **kw: rs)
    seed_pts = [(660, 340), (960, 340), (1260, 340)]   # 容器坐标种子(3 槽定值)
    _gs = SimpleNamespace(wish_trial_opts_xy=SimpleNamespace(value=list(seed_pts)))
    monkeypatch.setattr(pick_mod, 'game_state_from_ctx', lambda ctx: _gs)
    reported: list = []
    monkeypatch.setattr(pick_mod, 'report_action_pick_wish_trial_param',
                        lambda gs, param, sig: reported.append(param)
                        or SimpleNamespace(world_decl=None))
    env = OverlayPickExecEnv(op=op)
    assert CwActionPickWishTrialOp(env.op.ctx, CwActionPickWishTrialParam(idx=0),
                                   env=env).run().is_success
    # 点击点 = 容器值(param.idx 对槽),零 env.target 依赖。
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [seed_pts[0]]
    assert len(ctrl.moves) == len(ctrl.clicks) == 1
    assert confirm_calls == [('货币战争-祈愿试炼', '按钮-确认选择',
                              {'success_wait': 1.5})]
    assert env.round_result is rs
    assert len(reported) == 1 and reported[0].idx == 0


def test_wish_trial_pick_op_container_guard_rejects_without_click(
        no_pick_sleep, monkeypatch):
    """祈愿试炼取点守卫二态测试(选择坐标观察上报条款;A 类伴随域无 None
    元素,守卫二态 = 缺域/越界):容器 wish_trial_opts_xy 缺席/空、
    param.idx 越界 → AssertionError 且零点击零上报(禁坐标现算回退)。
    红 = 现算回退 / 守卫缺位静默续跑。"""
    import sr_od.application.currency_war.operations.cw_op.cw_pick_wish_trial_action as pick_mod

    rs = SimpleNamespace(sentinel='rs')
    # (gs 桩 wish_trial_opts_xy.value,param.idx,案例标签;守卫单一合并
    # 断言(box_pick 同款),案例只辨二态不辨消息片段)
    cases = [
        (None, 0, '容器缺域'),   # Field 恒未观察 None
        ([], 0, '容器空'),
        ([(660, 340), (960, 340), (1260, 340)], 3, '越界(槽数 = 3)'),
    ]
    for xy_value, idx, label in cases:
        ctrl = _RecordingController()
        op = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl),
                             screenshot=lambda: 'shot',
                             round_by_find_and_click_area=lambda shot, s, a,
                             **kw: rs)
        _gs = SimpleNamespace(
            wish_trial_opts_xy=SimpleNamespace(value=xy_value))
        monkeypatch.setattr(pick_mod, 'game_state_from_ctx',
                            lambda ctx, g=_gs: g)
        reported: list = []
        monkeypatch.setattr(pick_mod, 'report_action_pick_wish_trial_param',
                            lambda gs, param, sig, r=reported:
                                r.append(param))
        env = OverlayPickExecEnv(op=op)
        with pytest.raises(AssertionError):
            CwActionPickWishTrialOp(env.op.ctx,
                                    CwActionPickWishTrialParam(idx=idx),
                                    env=env).run()
        assert ctrl.clicks == [], f'守卫拦截({label})= 零点击'
        assert reported == [], f'守卫拦截({label})= 零上报'


def test_pick_expert_invite_takes_point_from_container(no_pick_sleep,
                                                       monkeypatch):
    """专家邀请函选卡取坐标测试(选择坐标观察上报收敛,op-layer.md §1.1):
    点击点 = 容器 ``expert_invite`` payload 双源按 param.idx 取——idx=-1 =
    词表特形(现金为王)显式分支消费 ``cash_point``;idx ∈ 0..3 = 消费
    ``card_points[idx]``(坐标单一真相源 = 观察上报;禁回退 env.target、
    禁坐标现算)→ 点击 + 自上报照发(env idx-only 停喂 target);缺席
    (payload 缺席 / cash_point None / card_points None·长度≠4 / idx 越界)
    = 守卫断言 AssertionError 响亮暴露且零点击零上报(防 bug 路栏非控制
    流,禁现算回退)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_pick_expert_invite_action as pick_mod

    pts = [(300, 400), (700, 400), (1100, 400), (1500, 400)]

    def _make(payload_value):
        ctrl = _RecordingController()
        op = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl))
        env = OverlayPickExecEnv(op=op)
        gs = SimpleNamespace(
            expert_invite=SimpleNamespace(value=payload_value))
        reported: list = []
        monkeypatch.setattr(pick_mod, 'game_state_from_ctx',
                            lambda ctx: gs)
        monkeypatch.setattr(pick_mod, 'report_action_pick_expert_invite_param',
                            lambda gs_, param, sig, _r=reported:
                                _r.append(param)
                                or SimpleNamespace(world_decl=None))
        return op, env, ctrl, reported

    # ① idx=-1 → 恰消费 cash_point(词表特形显式分支);② idx=1 → 消费
    # card_points[1]:点击坐标 = 容器值,自上报照发。
    for idx, want_pt in ((-1, (500, 900)), (1, pts[1])):
        op, env, ctrl, reported = _make(SimpleNamespace(
            card_points=list(pts), cash_point=(500, 900)))
        assert CwActionPickExpertInviteOp(
            op.ctx, CwActionPickExpertInviteParam(idx=idx),
            env=env).run().is_success
        assert [(p.x, p.y) for p, _t in ctrl.clicks] == [want_pt]
        assert len(ctrl.moves) == len(ctrl.clicks) == 1
        assert len(reported) == 1 and reported[0].idx == idx

    # ③ 缺席/越界守卫(payload 值,分支覆盖):AssertionError 且零点击零上报。
    guard_cases = [
        (None, 1, 'payload 缺席(Field 恒未观察 None)'),
        (SimpleNamespace(card_points=list(pts), cash_point=None), -1,
         'cash_point 缺席'),
        (SimpleNamespace(card_points=None, cash_point=(500, 900)), 1,
         'card_points 缺席'),
        (SimpleNamespace(card_points=pts[:3], cash_point=(500, 900)), 1,
         'card_points 长度≠4(定长 4)'),
        (SimpleNamespace(card_points=list(pts), cash_point=(500, 900)), 4,
         'idx 越界'),
    ]
    for payload_value, idx, label in guard_cases:
        op, env, ctrl, reported = _make(payload_value)
        with pytest.raises(AssertionError):
            CwActionPickExpertInviteOp(
                op.ctx, CwActionPickExpertInviteParam(idx=idx),
                env=env).run()
        assert ctrl.clicks == [], f'守卫拦截({label})= 零点击'
        assert reported == [], f'守卫拦截({label})= 零上报'


def test_pick_star_tome_takes_point_from_container(no_pick_sleep, monkeypatch):
    """星徽秘典选卡取坐标测试(选择坐标观察上报收敛,op-layer.md §1.1):
    点击点 = 容器 ``star_tome_opts_xy[param.idx]``(坐标单一真相源 =
    观察上报;禁回退 env.target、禁坐标现算)→ safe_click + 自上报照发;
    坐标域缺席(gs 缺席)/下标越界 = 守卫断言 AssertionError 响亮暴露
    且零点击(防 bug 路栏非控制流,禁现算回退)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_pick_star_tome_action as pick_mod

    # ① 注入容器值 → 点击坐标 = 容器值 + 自上报照发(env idx-only 停喂
    # target;safe_click = mouse_move + click 防吞点击)。
    ctrl = _RecordingController()
    op = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl))
    env = OverlayPickExecEnv(op=op, idx=1)
    gs = SimpleNamespace(star_tome_opts_xy=SimpleNamespace(
        value=[(300, 500), (760, 500)]))
    reported: list = []
    monkeypatch.setattr(pick_mod, 'game_state_from_ctx', lambda ctx: gs)
    monkeypatch.setattr(pick_mod, 'report_action_pick_star_tome_param',
                        lambda gs_, param, sig, _r=reported:
                            _r.append(param)
                            or SimpleNamespace(world_decl=None))
    assert CwActionPickStarTomeOp(env.op.ctx, CwActionPickStarTomeParam(idx=1),
                                  env=env).run().is_success
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [(760, 500)]
    assert len(ctrl.moves) == len(ctrl.clicks) == 1
    assert len(reported) == 1 and reported[0].idx == 1

    # ② 坐标域缺席(gs 缺席)→ AssertionError 零点击。
    ctrl2 = _RecordingController()
    op2 = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl2))
    env2 = OverlayPickExecEnv(op=op2, idx=0)
    monkeypatch.setattr(pick_mod, 'game_state_from_ctx', lambda ctx: None)
    with pytest.raises(AssertionError):
        CwActionPickStarTomeOp(env2.op.ctx, CwActionPickStarTomeParam(idx=0),
                               env=env2).run()
    assert ctrl2.clicks == [] and ctrl2.moves == [], '缺席零点击(禁回退)'

    # ③ 下标越界 → AssertionError 零点击。
    ctrl3 = _RecordingController()
    op3 = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl3))
    env3 = OverlayPickExecEnv(op=op3, idx=5)
    monkeypatch.setattr(pick_mod, 'game_state_from_ctx', lambda ctx: gs)
    with pytest.raises(AssertionError):
        CwActionPickStarTomeOp(env3.op.ctx, CwActionPickStarTomeParam(idx=5),
                               env=env3).run()
    assert ctrl3.clicks == [] and ctrl3.moves == [], '越界零点击(禁回退)'


def test_pick_box_card_takes_point_from_container(no_pick_sleep, monkeypatch):
    """武装箱选卡取坐标测试(选择坐标观察上报收敛,op-layer.md §1.1):
    点击点 = 容器 ``box_card_names_xy[param.idx]``(坐标单一真相源 =
    观察上报;禁回退 env.target、禁坐标现算)→ 点击 + 自上报照发;
    坐标域缺席(gs 缺席)/下标越界 = 守卫断言 AssertionError 响亮暴露
    且零点击(防 bug 路栏非控制流,禁现算回退)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_pick_box_card_action,
    )

    # ① 注入容器值 → 点击坐标 = 容器值 + 自上报照发(env idx-only 停喂)。
    ctrl = _RecordingController()
    op = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl))
    env = OverlayPickExecEnv(op=op, idx=1)
    gs = SimpleNamespace(box_card_names_xy=SimpleNamespace(
        value=[(500, 290), (1027, 290)]))
    reported: list = []
    monkeypatch.setattr(cw_pick_box_card_action, 'game_state_from_ctx',
                        lambda ctx: gs)
    monkeypatch.setattr(cw_pick_box_card_action,
                        'report_action_pick_box_card_param',
                        lambda gs_, param, sig, _r=reported:
                            _r.append(param)
                            or SimpleNamespace(world_decl=None))
    assert CwActionPickBoxCardOp(env.op.ctx, CwActionPickBoxCardParam(idx=1),
                                 env=env).run().is_success
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [(1027, 290)]
    assert len(ctrl.moves) == len(ctrl.clicks) == 1
    assert len(reported) == 1 and reported[0].idx == 1

    # ② 坐标域缺席(gs 缺席)→ AssertionError 零点击。
    ctrl2 = _RecordingController()
    op2 = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl2))
    env2 = OverlayPickExecEnv(op=op2, idx=0)
    monkeypatch.setattr(cw_pick_box_card_action, 'game_state_from_ctx',
                        lambda ctx: None)
    with pytest.raises(AssertionError):
        CwActionPickBoxCardOp(env2.op.ctx, CwActionPickBoxCardParam(idx=0),
                              env=env2).run()
    assert ctrl2.clicks == [] and ctrl2.moves == [], '缺席零点击(禁回退)'

    # ③ 下标越界 → AssertionError 零点击。
    ctrl3 = _RecordingController()
    op3 = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl3))
    env3 = OverlayPickExecEnv(op=op3, idx=5)
    monkeypatch.setattr(cw_pick_box_card_action, 'game_state_from_ctx',
                        lambda ctx: gs)
    with pytest.raises(AssertionError):
        CwActionPickBoxCardOp(env3.op.ctx, CwActionPickBoxCardParam(idx=5),
                              env=env3).run()
    assert ctrl3.clicks == [] and ctrl3.moves == [], '越界零点击(禁回退)'


# ============================================================ 刷新零效果对账


def test_invest_env_refresh_no_effect_reconcile_records_defect(monkeypatch):
    """投资环境零效果留证(重入观察侧):证据齐(计数未扣 ∧ 名集
    未变)→ 缺陷落台账 + 证据消费即清;名集已变/读缺 → 零缺陷。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_invest_env import (
        CwScreenInvestEnv,
    )
    defect_calls: list = []
    monkeypatch.setattr(cw_defects, 'record_defect',
                        lambda *a, **k: defect_calls.append((a, k)))
    op = CwScreenInvestEnv.__new__(CwScreenInvestEnv)
    # 正臂:计数未扣(1→1)∧ 名集未变 → 缺陷
    op._refresh_evidence = (1, ['旧名'], [(1, 671, 983)], [('旧名', 100)])
    op._reconcile_refresh_no_effect()
    assert len(defect_calls) == 1
    args, kwargs = defect_calls[0]
    assert args[0] == 'invest_env' and args[1] == 'refresh_no_effect'
    assert kwargs['severity'] == cw_defects.SEVERITY_L2_RECORD
    assert op._refresh_evidence is None   # 消费即清
    # 反臂:名集已变(重掷生效)→ 零缺陷
    op._refresh_evidence = (1, ['旧名'], [(0, 671, 983)], [('新名', 100)])
    op._reconcile_refresh_no_effect()
    assert len(defect_calls) == 1
    # 反臂:刷后计数读缺(过渡帧)→ 不可判零缺陷
    op._refresh_evidence = (1, ['旧名'], [], [])
    op._reconcile_refresh_no_effect()
    assert len(defect_calls) == 1
    # 无待评证据 → 幂等空转
    op._reconcile_refresh_no_effect()
    assert len(defect_calls) == 1


# ============================================================ 专家邀请函:入口与决策出口守卫


def test_expert_invite_entry_select_only(test_context, monkeypatch):
    """收缩为弹窗画面 op:入口门 = 弹窗已开单一形态(两 node 形态观察
    node 承载)——弹窗不在 = fail 交回外循环重识别(外循环按下一帧画面
    重分发自愈;开卡缺位由备战词表 CwActionOpenBookcardParam 链承接)。
    选卡成功链的行为面由决策出口守卫测试组承重,本测试不重复。"""
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


def _expert_guard_harness(test_context, monkeypatch, strategy):
    """守卫测试组装配:obs 读链桩 + area_center 桩(迁观察链 = 观察上报
    坐标域种子,act 决策段零 area_center 可桩)+ 注册表 action_op_for
    派发捕获桩。strategy = decide_expert_invite 注入体(match =
    StrategySession 冷建;strategy=None = 局外无 match 语境)。
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
    # 无同线;判据语义对测试组无感——决策值全由 strategy 桩给定)。
    monkeypatch.setattr(mod, '_resolve_card_bonds',
                        lambda ctx, screen, a: '能量' if a == '卡-1' else None)
    monkeypatch.setattr(cw_observation, 'read_board',
                        lambda ctx, screen: {'仙舟': 2})
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'screenshot', lambda: object(), raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: Area(True))
    # 坐标域种子(观察链桩;观察上报经 report 落容器,决策段零坐标现算,
    # 坐标消费 = 动作 op 容器取点测试)。
    _pts = {'卡-1': Point(300, 400), '卡-2': Point(700, 400),
            '卡-3': Point(1100, 400), '卡-4': Point(1500, 400),
            mod.CASH_AREA: Point(500, 900)}
    monkeypatch.setattr(cw_obs_core, 'area_center',
                        lambda ctx, name, screen: _pts.get(name))
    # 派发捕获桩(机械链行为测试)。
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
    """测试A(异常传播,op-layer §1.1 出口③):策略桩 decide_expert_invite
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
    """测试B(返回契约,op-layer §1.1 出口③):策略桩返回 None 与词表外对象
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
    """测试C(值域,op-layer §1.3):真词表类域外 idx(-2 = 原「<0 静默并入
    现金分支」路径 / 4 = 原 IndexError 意外出口)→ AssertionError 传播、
    零派发零点击、_pick_pending None;idx=-1 不炸(域内现金语义,归测试D)。
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
    """测试D(正路两态):真词表类 idx=-1 → 恰一次派发、派发 param 即策略产
    实例(is 比对,零重建构造点)、env.idx == -1 且 env 停喂 target
    (idx-only)、容器坐标域 cash_point 在位(坐标源断言 = 容器值,机械
    消费归容器取点测试)、round WAIT;idx=1 → env.idx == 1、容器
    card_points[1] 在位、_pick_pending 置位。红 = 重建构造点回潮 / env
    复喂 target / 观察双写断流。"""
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
    """测试E(局外无早退支,用户裁决 2026-09-22 全族删门,op-layer §1.1):
    cw_match = None(观察链桩照常给 obs)→ act 不设局外早退门,沿正常
    链路因缺上下文自然失败(AttributeError)、零派发零点击、_pick_pending
    保持 None;kernel choose_expert_index 桩零调用(兜底判据支退役的回归
    测试)。红 = 局外 round_success 早退门回潮 / 局外兜底决策/派发回潮。"""
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
    """report 双写测试(选择坐标观察上报,op-layer §1.1):同一调用同一
    写门写 ``ExpertInvitePayload`` 四字段(card_bonds/board/card_points/
    cash_point);同序等长写端构造守卫——不等长(定长 4)= AssertionError
    响亮暴露零写;坐标域欠供(None)随名字域同门照报(欠账形态同格,
    不半截收敛——清偿批同名同坐标一次落净)。红 = 拆门双写 / 等长守卫
    缺位 / 坐标域单独收敛。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

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
