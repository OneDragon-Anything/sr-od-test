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
    """screen_loader 桩:get_screen 恒 None → area_center 走缺失臂
    (None;供「area 缺失 = 显式失败禁兜底坐标」语义锁)。"""
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
    assert CwActionPickEncounterOp(env.op.ctx, EncounterPick(idx=1), env=env).run().is_success
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
    rs2 = CwActionPickEncounterOp(env2.op.ctx, EncounterPick(idx=1), env=env2).run()
    assert not rs2.is_success, '卡位 area 缺失 = 显式 round_fail(禁兜底坐标)'
    assert ctrl2.clicks == [] and ctrl2.moves == [], '失败臂零点击零移动'
    assert confirm_calls2 == [], '失败臂不进确认步'
    assert env2.round_result is rs2, '失败轮次结果经旁路回传'


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
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickMegastarParam,
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

    # 策略 param → strategy 支(类型机械分派锁)。
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
    ``fortune_opts_xy`` 读(缺/越界 = 守卫断言,二态见下一锁)→
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
    """命运卜者取点守卫二态锁(坐标随报条款;A 类伴随域无 None 元素,
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
    ``wish_trial_opts_xy`` 读(缺/越界 = 守卫断言,二态见下一锁)→
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
    """祈愿试炼取点守卫二态锁(选择坐标观察上报条款;A 类伴随域无 None
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
    """专家邀请函选卡取坐标锁(选择坐标观察上报收敛,op-layer.md §1.1 :35):
    点击点 = 容器 ``expert_invite`` payload 双源按 param.idx 取——idx=-1 =
    词表特形(现金为王)显式分支消费 ``cash_point``;idx ∈ 0..3 = 消费
    ``card_points[idx]``(坐标单一真相源 = 观察上报;禁回退 env.target、
    禁坐标现算)→ 点击 + 自上报照发(env idx-only 停喂 target);缺席
    (payload 缺席 / cash_point None / card_points None·长度≠4 / idx 越界)
    = 守卫断言 AssertionError 响亮暴露且零点击零上报(防 bug 路栏非控制
    流,禁现算回退)。原 env.target 过渡取点行为锁
    (test_pick_no_confirm_ops_click_and_self_report 专家行)随收敛批退役
    改写。"""
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
    """星徽秘典选卡取坐标锁(选择坐标观察上报收敛,op-layer.md §1.1 :35):
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
    """武装箱选卡取坐标锁(选择坐标观察上报收敛,op-layer.md §1.1 :35):
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
