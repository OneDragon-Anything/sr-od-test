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
4. 比对收口锁:三值对比单一源真值表 / RefreshShopOp 零比对只落账 /
   入口观察对账点两腿判定 / 投资环境零效果留证迁重入观察侧。
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
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopCard,
    ShopPayload,
    ShopSlot,
    game_state_of,
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
    CwActionPickEquipParam,
    CwActionPickExpertInviteParam,
    CwActionPickFortuneParam,
    CwActionPickInvestParam,
    CwActionPickMegastarParam,
    CwActionPickPartnerParam,
    CwActionPickPlannerParam,
    CwActionPickStarTomeParam,
    CwActionPickSupplyParam,
    CwActionPickWishTrialParam,
    CwActionRefreshInvestCardsParam,
    CwActionRefreshNodeOptionsParam,
    CwActionRefreshShopParam,
    CwActionRefreshSupplyParam,
)
from sr_od.application.currency_war.obs.cw_shop_refresh_obs import (
    refresh_board_changed_of,
)
from sr_od.application.currency_war.operations.cw_op.cw_action_registry import (
    action_op_class_for_type,
)
from sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_action import (
    CwActionPickBoxCardOp,
    CwActionPickEncounterOp,
    CwActionPickEquipOp,
    CwActionPickExpertInviteOp,
    CwActionPickFortuneOp,
    CwActionPickInvestOp,
    CwActionPickMegastarOp,
    CwActionPickPartnerOp,
    CwActionPickPlannerOp,
    CwActionPickStarTomeOp,
    CwActionPickSupplyOp,
    CwActionPickWishTrialOp,
    OverlayPickExecEnv,
)
from sr_od.application.currency_war.operations.cw_op.cw_prep_level_up_action import (
    CwActionLevelUpOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_refresh_shop_action import (
    CwActionRefreshShopOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    ShopExecEnv,
    ShopVisitLedger,
)
from sr_od.application.currency_war.telemetry import defects as cw_defects
from sr_od.operations.sr_operation import SrOperation

_LOGIC_SIG = ChannelSig(family='logic_action', actor='cw-t216-test',
                        mode='compute')


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
        (CwActionPickInvestParam, CwActionPickInvestOp),
        (CwActionPickFortuneParam, CwActionPickFortuneOp),
        (CwActionPickWishTrialParam, CwActionPickWishTrialOp),
        (CwActionPickStarTomeParam, CwActionPickStarTomeOp),
        (CwActionPickBoxCardParam, CwActionPickBoxCardOp),
        (CwActionPickExpertInviteParam, CwActionPickExpertInviteOp),
        (CwActionPickEquipParam, CwActionPickEquipOp),
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
    """pick 族模块与确认收尾助手的机械等待替身(零真睡)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_action as pick_mod
    from sr_od.application.currency_war.operations.cw_screen import (
        _overlay_confirm,
    )
    sleeper = _NoSleep()
    monkeypatch.setattr(pick_mod, 'time', sleeper)
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


def test_supply_pick_op_clicks_target_confirms_and_registers_arrival(
        no_pick_sleep):
    """补给确认链:点卡 → 「按钮-确认」area 确认 → 到账登记
    (ConfirmSupply 写边随确认链同体,last_owned_equips +1)。"""
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
    # 到账登记(写边;equip 未读到 = 不登记,此处正锁)。
    # 终态契约 §B:单一源 = gs.equips(容器直写)。
    from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
    assert game_state_of(session).equips.value == ['星币收集器']


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
    """策划确认链:点卡(press_time 透传)→ 确认(pending 置位 +
    全词裁决词);轮次结果旁路回传。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_planner import (
        CwScreenPlanner,
    )
    rs = SimpleNamespace(sentinel='rs')
    ctrl = _RecordingController()
    op = SimpleNamespace(
        ctx=SimpleNamespace(controller=ctrl, screen_loader=_screen_loader_none()),
        CLICK_PRESS_TIME=0.15,
        _confirm_pending=False,
        round_retry=lambda **kw: rs)
    env = OverlayPickExecEnv(op=op, target=Point(700, 420))
    assert CwActionPickPlannerOp(env.op.ctx, PlannerPick(idx=1), env=env).run().is_success
    assert [(p.x, p.y, t) for p, t in ctrl.clicks] == [
        (700, 420, 0.15), (CwScreenPlanner.CONFIRM.x, CwScreenPlanner.CONFIRM.y, 0.15)]
    assert op._confirm_pending is True
    assert env.round_result is rs


def test_invest_pick_op_clicks_target_confirms_and_self_reports(
        no_pick_sleep, monkeypatch):
    """投资确认链(pick-op-unify T-2,投资环境/策略两屏共用 op):
    点选中位 → 确认;轮次结果旁路回传;自上报在机械链发出后调用
    (零写函数被桩捕获 = 契约面接线锁;gs 供给桩 = 无局 None 时跳过)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_action as pick_mod

    rs = SimpleNamespace(sentinel='rs')
    ctrl = _RecordingController()
    op = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl),
                         round_retry=lambda **kw: rs)
    env = OverlayPickExecEnv(op=op, idx=2, target=Point(900, 450),
                             confirm=Point(1082, 982), entry_keyword='投资环境')
    reported: list = []
    monkeypatch.setattr(pick_mod, 'game_state_from_ctx',
                        lambda ctx: SimpleNamespace(sentinel='gs'))
    monkeypatch.setattr(pick_mod, 'report_action_pick_invest_param',
                        lambda gs, param, sig: reported.append((gs, param, sig)))
    assert CwActionPickInvestOp(env.op.ctx, CwActionPickInvestParam(idx=2),
                                env=env).run().is_success
    # 点击序 = 选中位 → 确认钮;每次点击前 bug#1 mouse_move 缓解。
    assert [(p.x, p.y) for p, _t in ctrl.clicks] == [(900, 450), (1082, 982)]
    assert len(ctrl.moves) == len(ctrl.clicks)
    assert env.round_result is rs
    # 自上报接线(机械链发出后恰一次;param 原样透传)。
    assert len(reported) == 1 and reported[0][1].idx == 2


def test_fortune_pick_op_clicks_card_confirms_and_self_reports(
        no_pick_sleep, monkeypatch):
    """命运卜者确认链(pick-op-unify T-3):点卡 → 确认;轮次结果旁路
    回传;自上报接线。确认钮 = 建档缺失臂兜底常量(screen_loader 桩)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_action as pick_mod
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
    import sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_action as pick_mod

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
    """点卡即选族四 op 行为锁(pick-op-unify T-4):装备/武装箱/星徽秘典/
    专家邀请函 = 选中点击 + 各自动画等待,零确认步;自上报接线;派发
    param 携真实 idx(专家邀请函含 -1 = 现金为王语义透传)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_action as pick_mod

    cases = [
        (CwActionPickEquipOp, CwActionPickEquipParam, Point(1070, 280),
         [(1070, 280)], 1),
        (CwActionPickBoxCardOp, CwActionPickBoxCardParam, Point(1027, 290),
         [(1027, 290)], 2),
        (CwActionPickStarTomeOp, CwActionPickStarTomeParam, Point(700, 500),
         [(700, 500)], 0),
        (CwActionPickExpertInviteOp, CwActionPickExpertInviteParam,
         Point(300, 600), [(300, 600)], -1),
    ]
    for op_cls, param_cls, target, want_clicks, want_idx in cases:
        ctrl = _RecordingController()
        op = SimpleNamespace(ctx=SimpleNamespace(controller=ctrl))
        env = OverlayPickExecEnv(op=op, idx=want_idx, target=target)
        reported: list = []
        monkeypatch.setattr(pick_mod, 'game_state_from_ctx',
                            lambda ctx: SimpleNamespace(sentinel='gs'))
        monkeypatch.setattr(pick_mod, 'report_action_pick_equip_param',
                            lambda gs, param, sig, _r=reported: _r.append(param),
                            raising=False)
        monkeypatch.setattr(pick_mod, 'report_action_pick_box_card_param',
                            lambda gs, param, sig, _r=reported: _r.append(param),
                            raising=False)
        monkeypatch.setattr(pick_mod, 'report_action_pick_star_tome_param',
                            lambda gs, param, sig, _r=reported: _r.append(param),
                            raising=False)
        monkeypatch.setattr(pick_mod, 'report_action_pick_expert_invite_param',
                            lambda gs, param, sig, _r=reported: _r.append(param),
                            raising=False)
        assert op_cls(env.op.ctx, param_cls(idx=want_idx),
                      env=env).run().is_success, param_cls.__name__
        assert [(p.x, p.y) for p, _t in ctrl.clicks] == want_clicks, \
            param_cls.__name__
        assert len(ctrl.moves) == len(ctrl.clicks), param_cls.__name__
        assert len(reported) == 1 and reported[0].idx == want_idx, \
            param_cls.__name__


# ===== 4. 比对收口锁(三面迁观察侧)=====

def test_refresh_board_changed_of_three_value():
    """三值对比单一源真值表(与退役前 execute 内联式逐字等价):任一侧
    空 = None 不可判不猜;否则 = 刷前/刷后具名牌名集不一致。"""
    assert refresh_board_changed_of([], ['a']) is None
    assert refresh_board_changed_of(['a'], []) is None
    assert refresh_board_changed_of([], []) is None
    assert refresh_board_changed_of(['a', 'b'], ['b', 'a']) is False
    assert refresh_board_changed_of(['a', 'b'], ['b', 'c']) is True


class _FakeShopRow:
    """read_shop_cards 读数行桩(kind/card.name 面)。"""

    def __init__(self, name: str | None) -> None:
        self.kind = 'content'
        self.card = SimpleNamespace(name=name, star=1, cost=1)


def _shop_state_with_gold_and_cards() -> tuple:
    """容器店面逻辑态(刷前现读输入;金 50 + 具名牌 1 张)。"""
    session = StrategySession()
    gs = game_state_of(session)
    gs.write_logic(gs.gold, 50, produced_by='cw-t216-test', sig=_LOGIC_SIG)
    slots = [ShopSlot(kind='content',
                      card=ShopCard(name='旧卡A', faction='', cost=1,
                                    star=1, slot=1))]
    slots += [ShopSlot(kind='empty')] * 4
    gs.write_logic(gs.shop, ShopPayload(cards=slots, refresh_probs={}),
                   produced_by='cw-t216-test', sig=_LOGIC_SIG)
    return session, game_state_of(session)


def test_refresh_shop_op_persists_evidence_without_comparison(monkeypatch):
    """RefreshShopOp 零比对(裁决3 批4):execute 只落账(刷前/刷后名集
    原样),零缺陷发射;退役字段不再在场(对象面运行时检查,
    非源码扫描)。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)
    defect_calls: list = []
    monkeypatch.setattr(cw_defects, 'record_defect',
                        lambda *a, **k: defect_calls.append((a, k)))
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_buy_cards as buy_mod,
    )
    monkeypatch.setattr(buy_mod, 'read_shop_cards',
                        lambda ctx, shot: [_FakeShopRow('新卡A'),
                                           _FakeShopRow('新卡B'),
                                           _FakeShopRow(None)])
    _session, state = _shop_state_with_gold_and_cards()
    ledger = ShopVisitLedger()
    env = ShopExecEnv(
        op=SimpleNamespace(
            ctx=SimpleNamespace(controller=_RecordingController()),
            screenshot=lambda: None),
        match=None, config=None, click_pts=[],
        level_btn=Point(0, 0), refresh_btn=Point(1603, 479),
        ledger=ledger, state=state)
    assert CwActionRefreshShopOp(env.op.ctx, CwActionRefreshShopParam(), env=env).run().is_success
    # 只读不比:刷前/刷后名集原样落账,比对结果不再由动作 op 预计算
    assert ledger.refresh_pre_names == ['旧卡A']
    assert ledger.refresh_post_names == ['新卡A', '新卡B']
    assert not hasattr(ledger, 'refresh_board_changed')
    # 零缺陷发射
    assert defect_calls == []


def test_entry_reconcile_free_leg_fires_on_unchanged_gold(monkeypatch):
    """入口观察对账点·免费腿(三值单一源消费):金未扣 ∧ 牌面已变 →
    存证调用(存证体桩化,零真实 IO)。名集未变分支 = 零存证(比对
    单一源的 False 臂)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_buy_cards as buy_mod,
    )
    free_calls: list = []
    monkeypatch.setattr(buy_mod, '_record_free_refresh_proc',
                        lambda *a, **k: free_calls.append((a, k)))
    ledger = ShopVisitLedger()
    ledger.refresh_pre_gold = 48
    ledger.refresh_pre_names = ['旧卡A']
    ledger.refresh_pending_reconcile = True
    entry = SimpleNamespace(
        gold=48,   # 金未扣
        shop=[SimpleNamespace(kind='content',
                              card=SimpleNamespace(name='新卡X'))],
        plane=1, round_num=3)
    buy_mod._reconcile_refresh_pending(SimpleNamespace(), ledger, entry)
    assert len(free_calls) == 1
    kwargs = free_calls[0][1]
    assert kwargs['pre_gold'] == 48 and kwargs['gold_after'] == 48
    assert kwargs['pre_names'] == ['旧卡A']
    assert kwargs['post_names'] == ['新卡X']
    # 名集未变(牌面没动)→ 零存证
    free_calls.clear()
    entry2 = SimpleNamespace(
        gold=48,
        shop=[SimpleNamespace(kind='content',
                              card=SimpleNamespace(name='旧卡A'))],
        plane=1, round_num=3)
    buy_mod._reconcile_refresh_pending(SimpleNamespace(), ledger, entry2)
    assert free_calls == []


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
