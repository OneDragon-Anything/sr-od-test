"""CW 统一动作工厂 批4 锁面(事件线 pick 收编 + 比对收口迁移 + 注册完备
锁)。

出处 = docs/develop/sr_od/application/currency_war/changes/
2026-09-14-unified-action-factory/landing.md §3.4 完成判据 + design.md
§2.5(pick 注册 / 注册完备锁)+ §2.4 比对收口清单(三面迁观察侧)。

锁面全部为运行时行为锁(源码扫描测试禁止,AGENTS.md §10.4);桩宿主
零真实 IO(harness 惯例同 test_cw_unified_action_2a/3)。

锁面清单:
1. 注册完备锁:遍历统一词表 CW_ACTION_TYPES + cw_events pick 族
   PICK_ACTION_TYPES(运行时元组,零源码读取),逐类断言注册表类级
   解析可命中(action_op_class_for_type;is-a 兜底语义同注册表);
2. pick 五行类级/实例级解析一致性 + 未知类型响亮暴露;
3. pick op 机械行为锁(五屏确认链,桩宿主记录点击);
4. 比对收口锁:三值对比单一源真值表 / 投资环境零效果留证迁重入观察侧。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_events import (
    EncounterPick,
    MegastarPick,
    PartnerPick,
    PlannerPick,
    SupplyPick,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CW_ACTION_TYPES,
    CwActionLevelUpParam,
    CwActionLevelUpShopParam,
    CwActionPickBoxCardParam,
    CwActionPickEncounterParam,
    CwActionPickExpertInviteParam,
    CwActionPickFortuneParam,
    CwActionPickInvestEnvParam,
    CwActionPickInvestStrategyParam,
    CwActionPickMegastarParam,
    CwActionPickPartnerParam,
    CwActionPickPlannerParam,
    CwActionPickStarTomeParam,
    CwActionPickSupplyParam,
    CwActionPickWishTrialParam,
    CwActionRefreshInvestCardsParam,
    CwActionRefreshNodeOptionsParam,
    CwActionRefreshSupplyParam,
)
from sr_od.application.currency_war.operations.cw_op.cw_action_registry import (
    action_op_class_for_type,
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
from sr_od.application.currency_war.operations.cw_op.cw_prep_level_up_action import (
    CwActionLevelUpOp,
)
from sr_od.application.currency_war.telemetry import defects as cw_defects
from sr_od.operations.sr_operation import SrOperation

# ===== 1. 注册完备锁(判据:词表全类型覆盖,遍历运行时元组,零源码读取)=====

# 终态契约动作类型的注册豁免集(终态契约 landing §3.5 锁规格:白名单
# 成员要么有注册行、要么在豁免集——无 op 行例外申报):
# - 三刷新动作(handler 自管点击链;attack4 M6 裁定 (a):与
#   CwActionRefreshInvestCardsParam 同型豁免)。
# (HoldFrame 曾在豁免集,随 2026-09-20 用户裁定收编进
#  CwActionObsParam(scope='outer_loop') 删除;7 pick 类已随
#  pick-op-unify 批收编入表——豁免集现形 = 三刷新动作。)
_TERMINAL_CONTRACT_REGISTRY_EXEMPT = (
    CwActionRefreshNodeOptionsParam, CwActionRefreshSupplyParam, CwActionRefreshInvestCardsParam,
)


def test_registry_covers_unified_vocab_and_pick_types():
    """注册完备锁(批4 主判据;终态契约 §2.2 收敛单表):统一词表
    CW_ACTION_TYPES 单表逐类断言注册表**类级**解析可命中(不构造业务
    动作实例,不读源码)——未注册 = 锁红;退役 = 删类,元组中不存在即
    天然不可复活(R1)。kernel EVENT_PICK_TYPES = 纯函数返回载体,策略
    产出词表化后不再进注册表面(§2.2)。

    终态契约扩展(landing §3.5):白名单新成员要么有注册行、要么在
    豁免集;豁免成员反向断言确无注册行(防误注册,误挂 op = 确认链
    字段错位暗雷)。"""
    for cls in CW_ACTION_TYPES:
        if cls in _TERMINAL_CONTRACT_REGISTRY_EXEMPT:
            with pytest.raises(AssertionError):
                action_op_class_for_type(cls)
            continue
        op_cls = action_op_class_for_type(cls)
        assert isinstance(op_cls, type) and issubclass(op_cls, SrOperation), \
            f'{cls.__name__} 解析产物非 SrOperation 子类: {op_cls}'
    for cls in _TERMINAL_CONTRACT_REGISTRY_EXEMPT:
        assert cls in CW_ACTION_TYPES, cls.__name__


def test_pick_rows_resolve_class_and_instance_consistently():
    """pick 行收编面(终态契约 §2.2 换键名:策略器产出 = 词表子类型;
    pick-op-unify 批起分批扩至全 12 类):
    类级解析与实例级工厂解析同 op 类(行序 is-a 语义一致;实例级仅本锁
    构造,注册完备锁本体不构造)。"""
    rows = [
        (CwActionPickEncounterParam, CwActionPickEncounterOp),
        (CwActionPickSupplyParam, CwActionPickSupplyOp),
        (CwActionPickMegastarParam, CwActionPickMegastarOp),
        (CwActionPickPartnerParam, CwActionPickPartnerOp),
        (CwActionPickPlannerParam, CwActionPickPlannerOp),
        (CwActionPickInvestEnvParam, CwActionPickInvestOp),   # 投资两屏拆类:两行同指一 op
        (CwActionPickInvestStrategyParam, CwActionPickInvestOp),
        (CwActionPickFortuneParam, CwActionPickFortuneOp),
        (CwActionPickWishTrialParam, CwActionPickWishTrialOp),
        (CwActionPickStarTomeParam, CwActionPickStarTomeOp),
        (CwActionPickBoxCardParam, CwActionPickBoxCardOp),
        (CwActionPickExpertInviteParam, CwActionPickExpertInviteOp),
    ]
    for cls, expected in rows:
        assert action_op_class_for_type(cls) is expected, cls.__name__


def test_class_level_isa_fallback_matches_instance_query():
    """is-a 兜底语义同注册表:CwActionLevelUpShopParam is-a CwActionLevelUpParam,类级首中
    CwActionLevelUpParam 行 → PrepLevelUpOp,与实例级查询一致(批3 先例的类级复验)。"""
    assert action_op_class_for_type(CwActionLevelUpShopParam) is CwActionLevelUpOp
    assert action_op_class_for_type(CwActionLevelUpParam) is CwActionLevelUpOp


def test_unknown_type_loud_at_class_level():
    """词表外类型 = 类级解析 AssertionError 响亮暴露(ADR-0517 决策 9
    语义,禁静默跳过)。"""

    class _NotVocab:
        pass

    with pytest.raises(AssertionError):
        action_op_class_for_type(_NotVocab)


# ===== 3. pick op 机械行为锁(桩宿主;五屏确认链)=====

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
    """screen_loader 桩:get_screen 恒 None → area_center 全走兜底常量
    (screen_info 缺失臂,常量兜底语义顺带在锁)。"""
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


def test_encounter_pick_op_clicks_card_then_confirm(no_pick_sleep):
    """遭遇确认链:idx=1 → 右卡兜底常量点选 → 确认钮点选;轮次结果经
    env.round_result 旁路回传(emit_overlay_confirm 机械交回)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_encounter import (
        CwScreenEncounter,
    )
    rs = SimpleNamespace(sentinel='rs')
    ctrl = _RecordingController()
    op = SimpleNamespace(
        ctx=SimpleNamespace(controller=ctrl, screen_loader=_screen_loader_none()),
        round_retry=lambda **kw: rs)
    env = OverlayPickExecEnv(op=op)
    assert CwActionPickEncounterOp(env.op.ctx, EncounterPick(idx=1), env=env).run().is_success
    assert [p for p, _t in ctrl.clicks] == [CwScreenEncounter.CARD_RIGHT,
                                            CwScreenEncounter.SELECT_BTN]
    assert len(ctrl.moves) == len(ctrl.clicks)   # 每次点击前 bug#1 缓解 mouse_move
    assert env.round_result is rs


def test_supply_pick_op_clicks_target_and_confirms(no_pick_sleep):
    """补给确认链:点卡 → 「按钮-确认」area 确认(机械半零判效);
    补给确认无到账登记写边(入栏/后果腿 =
    ``report_action_pick_supply_param`` 即时单相,行为锁见
    test_cw_supply_pick_immediate_report);本锁只锁机械点击面。"""
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
    assert CwActionPickSupplyOp(env.op.ctx, SupplyPick(idx=0), env=env).run().is_success
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [(500, 400)]
    assert confirm_calls == [('货币战争-补给', '按钮-确认',
                              {'success_wait': 1.5})]
    # 补给确认无到账登记写边(局外 ctx 无 cw_match,即时上报同跳过;
    # equips 保持开局种子 [] ,未混入选中装备名)。
    from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
    assert game_state_of(session).equips.value == []


def test_megastar_pick_op_clicks_confirm_once(no_pick_sleep):
    """巨星确认半:确认钮单发(screen_info 缺失走兜底常量)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar import (
        CwScreenMegastar,
    )
    ctrl = _RecordingController()
    op = SimpleNamespace(
        ctx=SimpleNamespace(controller=ctrl,
                            screen_loader=_screen_loader_none()))
    _env = OverlayPickExecEnv(op=op)
    assert CwActionPickMegastarOp(op.ctx, MegastarPick(idx=0), env=_env).run().is_success
    assert [p for p, _t in ctrl.clicks] == [CwScreenMegastar.CONFIRM]


def test_megastar_pick_op_select_clicks_container_xy(no_pick_sleep):
    """巨星选中半容器取点(选择坐标观察上报收敛,规范 = screens/
    op-layer.md §1.1「选择坐标观察上报」+ action_ops.md §1 增补 5):
    need_select=True → 点候选(点击坐标 = 容器 ``megastar_opts[idx].xy``,
    env idx-only 零 target 传参)→ 确认钮(兜底常量臂)。红 = 选中半
    回潮消费 env.target / 容器取点断流 / 点击序漂移。"""
    from sr_od.application.currency_war.kernel.cw_events import MegastarOption
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        game_state_of,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickMegastarParam,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar import (
        CwScreenMegastar,
    )

    ctrl = _RecordingController()
    session = StrategySession()
    _sig = ChannelSig(family='logic_action', actor='test', mode='compute')
    game_state_of(session).write_logic(
        game_state_of(session).megastar_opts,
        [MegastarOption(idx=0, char_id='花火', xy=(822, 333)),
         MegastarOption(idx=1, char_id='星期日', xy=(1061, 333))],
        produced_by='test', sig=_sig)
    ctx = SimpleNamespace(
        controller=ctrl,
        screen_loader=_screen_loader_none(),   # area 缺失 → 确认走兜底常量
        cw_match=SimpleNamespace(session=session))
    op = SimpleNamespace(ctx=ctx)
    env = OverlayPickExecEnv(op=op, idx=1, need_select=True)
    assert CwActionPickMegastarOp(ctx, CwActionPickMegastarParam(idx=1),
                                  env=env).run().is_success
    # 点击序 = 选中位(容器 megastar_opts[1].xy)→ 确认钮;每次点击前 mouse_move。
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [
        (1061, 333), (CwScreenMegastar.CONFIRM.x, CwScreenMegastar.CONFIRM.y)]
    assert len(ctrl.moves) == len(ctrl.clicks)


def test_partner_pick_op_pulses_select_then_confirm(no_pick_sleep):
    """伙伴脉冲链:未选中实证 → 点候选 + 点确认;脉冲计数与 pending
    置位(画面 op 宿主状态经 env.op 消费),轮次结果旁路回传。"""
    rs = SimpleNamespace(sentinel='rs')
    ctrl = _RecordingController()
    op = SimpleNamespace(
        ctx=SimpleNamespace(controller=ctrl),
        screenshot=lambda: 'shot',
        _pick_point=Point(300, 300), _confirm_pulses=0, _confirm_pending=False,
        _find_text_center=lambda shot, text: Point(900, 600),
        round_retry=lambda **kw: rs)
    env = OverlayPickExecEnv(op=op, unselected=True)
    assert CwActionPickPartnerOp(env.op.ctx, PartnerPick(idx=0), env=env).run().is_success
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [(300, 300), (900, 600)]
    assert op._confirm_pulses == 1
    assert op._confirm_pending is True
    assert env.round_result is rs


def test_partner_pick_op_confirm_missing_retries_without_click(no_pick_sleep):
    """确认钮读缺 → 零点击 round_retry(脉冲计数不动;读缺分支语义)。"""
    rs = SimpleNamespace(sentinel='rs')
    ctrl = _RecordingController()
    op = SimpleNamespace(
        ctx=SimpleNamespace(controller=ctrl),
        screenshot=lambda: 'shot',
        _pick_point=Point(300, 300), _confirm_pulses=2, _confirm_pending=False,
        _find_text_center=lambda shot, text: None,
        round_retry=lambda **kw: rs)
    env = OverlayPickExecEnv(op=op, unselected=False)
    assert CwActionPickPartnerOp(env.op.ctx, PartnerPick(idx=0), env=env).run().is_success
    assert ctrl.clicks == []
    assert op._confirm_pulses == 2   # 未点确认不计数
    assert env.round_result is rs


def test_planner_pick_op_clicks_target_and_confirm(no_pick_sleep):
    """策划确认链:点卡(press_time 透传)→ 确认(全词裁决词);轮次结果
    旁路回传(单相即时上报迭代后宿主无 pending 置位面)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_yinlang import (
        CwScreenYinLang,
    )
    rs = SimpleNamespace(sentinel='rs')
    ctrl = _RecordingController()
    op = SimpleNamespace(
        ctx=SimpleNamespace(controller=ctrl, screen_loader=_screen_loader_none()),
        CLICK_PRESS_TIME=0.15,
        round_retry=lambda **kw: rs)
    env = OverlayPickExecEnv(op=op, target=Point(700, 420))
    assert CwActionPickPlannerOp(env.op.ctx, PlannerPick(idx=1), env=env).run().is_success
    assert [(p.x, p.y, t) for p, t in ctrl.clicks] == [
        (700, 420, 0.15), (CwScreenYinLang.CONFIRM.x, CwScreenYinLang.CONFIRM.y, 0.15)]
    assert env.round_result is rs


def test_invest_pick_op_clicks_target_confirms_and_self_reports(
        no_pick_sleep, monkeypatch):
    """投资确认链(投资两屏共用 op,拆类后两 param 类同指;即时上报契约):
    点选中位 → 确认 → **按 param 类型立即自上报完整结果**(分步上报废
    除);轮次结果旁路回传;上报接线 = 机械链发出后恰一次。"""
    import sr_od.application.currency_war.operations.cw_op.cw_pick_invest_action as pick_mod

    rs = SimpleNamespace(sentinel='rs')
    ctrl = _RecordingController()
    op = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl),
                         round_retry=lambda **kw: rs)
    env = OverlayPickExecEnv(op=op, idx=2, target=Point(900, 450),
                             confirm=Point(1082, 982), entry_keyword='投资环境')
    reported: list = []
    monkeypatch.setattr(pick_mod, 'game_state_from_ctx',
                        lambda ctx: SimpleNamespace(sentinel='gs'))
    monkeypatch.setattr(pick_mod, 'report_action_pick_invest_env_param',
                        lambda gs, param, sig, **kw:
                        reported.append((gs, param, sig)))
    assert CwActionPickInvestOp(env.op.ctx, CwActionPickInvestEnvParam(idx=2),
                                env=env).run().is_success
    # 点击序 = 选中位 → 确认钮;每次点击前 bug#1 mouse_move 缓解。
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [(900, 450), (1082, 982)]
    assert len(ctrl.moves) == len(ctrl.clicks)
    assert env.round_result is rs
    # 即时上报接线(机械链发出后恰一次;param 原样透传;Env param → env 支)。
    assert len(reported) == 1 and reported[0][1].idx == 2

    # 策略 param → strategy 支(类型机械分派锁)。
    reported_st: list = []
    monkeypatch.setattr(pick_mod, 'report_action_pick_invest_strategy_param',
                        lambda gs, param, sig, **kw:
                        reported_st.append((gs, param, sig)))
    env_st = OverlayPickExecEnv(op=op, idx=0, target=Point(700, 450),
                                confirm=Point(1082, 982), entry_keyword='投资策略')
    assert CwActionPickInvestOp(env_st.op.ctx,
                                CwActionPickInvestStrategyParam(idx=0),
                                env=env_st).run().is_success
    assert len(reported_st) == 1 and reported_st[0][1].idx == 0


def test_fortune_pick_op_clicks_card_confirms_and_self_reports(
        no_pick_sleep, monkeypatch):
    """命运卜者确认链(pick-op-unify T-3):点卡 → 确认;轮次结果旁路
    回传;自上报接线。确认钮 = 建档缺失臂兜底常量(screen_loader 桩)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_pick_fortune_action as pick_mod
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_fortune import (
        CwScreenFortune,
    )

    rs = SimpleNamespace(sentinel='rs')
    ctrl = _RecordingController()
    op = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl,
                                             screen_loader=_screen_loader_none()),
                         round_retry=lambda **kw: rs)
    env = OverlayPickExecEnv(op=op, idx=1, target=Point(900, 480))
    reported: list = []
    monkeypatch.setattr(pick_mod, 'game_state_from_ctx',
                        lambda ctx: SimpleNamespace(sentinel='gs'))
    monkeypatch.setattr(pick_mod, 'report_action_pick_fortune_param',
                        lambda gs, param, sig: reported.append(param))
    assert CwActionPickFortuneOp(env.op.ctx, CwActionPickFortuneParam(idx=1),
                                 env=env).run().is_success
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [
        (900, 480), (CwScreenFortune.CONFIRM.x, CwScreenFortune.CONFIRM.y)]
    assert env.round_result is rs
    assert len(reported) == 1 and reported[0].idx == 1


def test_wish_trial_pick_op_clicks_card_area_confirms_and_self_reports(
        no_pick_sleep, monkeypatch):
    """祈愿试炼确认链(pick-op-unify T-3):点卡 → 「按钮-确认选择」area
    确认;轮次结果旁路回传;自上报接线。"""
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
    env = OverlayPickExecEnv(op=op, idx=0, target=Point(960, 340))
    reported: list = []
    monkeypatch.setattr(pick_mod, 'game_state_from_ctx',
                        lambda ctx: SimpleNamespace(sentinel='gs'))
    monkeypatch.setattr(pick_mod, 'report_action_pick_wish_trial_param',
                        lambda gs, param, sig: reported.append(param))
    assert CwActionPickWishTrialOp(env.op.ctx, CwActionPickWishTrialParam(idx=0),
                                   env=env).run().is_success
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [(960, 340)]
    assert confirm_calls == [('货币战争-祈愿试炼', '按钮-确认选择',
                              {'success_wait': 1.5})]
    assert env.round_result is rs
    assert len(reported) == 1 and reported[0].idx == 0


def test_pick_no_confirm_ops_click_and_self_report(
        no_pick_sleep, monkeypatch):
    """点卡即选族三 op 行为锁(pick-op-unify T-4):武装箱/星徽秘典/
    专家邀请函 = 选中点击 + 各自动画等待,零确认步;自上报接线;派发
    param 携真实 idx(专家邀请函含 -1 = 现金为王语义透传。原装备行随
    选择装备屏误判退役删除)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_pick_box_card_action,
        cw_pick_expert_invite_action,
        cw_pick_star_tome_action,
    )

    # (op_cls, param_cls, target, want_clicks, want_idx, op_mod, report_name)
    cases = [
        (CwActionPickBoxCardOp, CwActionPickBoxCardParam, Point(1027, 290),
         [(1027, 290)], 2, cw_pick_box_card_action,
         'report_action_pick_box_card_param'),
        (CwActionPickStarTomeOp, CwActionPickStarTomeParam, Point(700, 500),
         [(700, 500)], 0, cw_pick_star_tome_action,
         'report_action_pick_star_tome_param'),
        (CwActionPickExpertInviteOp, CwActionPickExpertInviteParam,
         Point(300, 600), [(300, 600)], -1, cw_pick_expert_invite_action,
         'report_action_pick_expert_invite_param'),
    ]
    for op_cls, param_cls, target, want_clicks, want_idx, op_mod, report_name in cases:
        ctrl = _RecordingController()
        op = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl))
        env = OverlayPickExecEnv(op=op, idx=want_idx, target=target)
        reported: list = []
        monkeypatch.setattr(op_mod, 'game_state_from_ctx',
                            lambda ctx: SimpleNamespace(sentinel='gs'))
        monkeypatch.setattr(op_mod, report_name,
                            lambda gs, param, sig, _r=reported: _r.append(param),
                            raising=False)
        assert op_cls(env.op.ctx, param_cls(idx=want_idx),
                      env=env).run().is_success, param_cls.__name__
        assert [(p.x, p.y) for p, _t in ctrl.clicks] == want_clicks, \
            param_cls.__name__
        assert len(ctrl.moves) == len(ctrl.clicks), param_cls.__name__
        assert len(reported) == 1 and reported[0].idx == want_idx, \
            param_cls.__name__


# (原 test_refresh_board_changed_of_three_value 删:三值对比单一源
#  refresh_board_changed_of 已随 2026-09-21 商店迭代清理批退役——两消费面
#  (段顶对账点/刷新回执 extra)均随免费刷新 proc 通道退役,生产零消费
#  实证(grep);判效权归下一入口观察对账。)


# (原 test_refresh_shop_op_persists_evidence_without_comparison 及其
#  _FakeShopRow/_shop_state_with_gold_and_cards 桩删:宿主面(刷前/刷后
#  名集落账)已随 2026-09-21 商店迭代 3.3 零读屏化退役——动作 op 零读屏
#  (action_ops §1 增补 3),ledger 对账件字段删除,判效权归下一入口
#  观察;刷新机械执行锁正本 = test_cw_refresh_fee_field_value。)


# (原 test_entry_reconcile_free_leg_fires_on_unchanged_gold 删:宿主
#  _reconcile_refresh_pending/_record_free_refresh_proc 已随 2026-09-21
#  Field 化退役——免费刷新事实可见性改由 free_refresh_left Field 锚定
#  失配安灯承接,锁与所辖面同批退役,正本 = test_cw_shop_refresh_field。)


def test_invest_env_refresh_no_effect_reconcile_records_defect(monkeypatch):
    """投资环境零效果留证(批4 迁重入观察侧):证据齐(计数未扣 ∧ 名集
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
