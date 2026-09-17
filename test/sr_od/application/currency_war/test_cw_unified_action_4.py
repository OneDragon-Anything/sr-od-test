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
    PICK_ACTION_TYPES,
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
    register_sig_actors,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CW_ACTION_TYPES,
    HoldFrame,
    LevelUp,
    LevelUpShop,
    PickBoxCard,
    PickEncounter,
    PickInvest,
    PickMegastar,
    PickPartner,
    PickPlanner,
    PickStarTome,
    PickSupply,
    PickWishTrial,
    RefreshInvestCards,
    RefreshNodeOptions,
    RefreshShop,
    RefreshSupply,
)
from sr_od.application.currency_war.obs.cw_shop_refresh_obs import (
    refresh_board_changed_of,
)
from sr_od.application.currency_war.operations.cw_op.cw_action_base import (
    ActionOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_action_registry import (
    action_op_class_for_type,
    action_op_for,
)
from sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_action import (
    EncounterPickOp,
    MegastarPickOp,
    OverlayPickExecEnv,
    PartnerPickOp,
    PlannerPickOp,
    SupplyPickOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_prep_level_up_action import (
    PrepLevelUpOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_refresh_shop_action import (
    RefreshShopOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    ShopExecEnv,
    ShopVisitLedger,
)
from sr_od.application.currency_war.telemetry import defects as cw_defects

register_sig_actors('cw-t216-test')

_LOGIC_SIG = ChannelSig(family='logic_action', actor='cw-t216-test',
                        mode='compute')


# ===== 1. 注册完备锁(判据:词表全类型覆盖,遍历运行时元组,零源码读取)=====

# 终态契约新增动作类型的注册豁免集(策略器终态契约 landing §3.1 锁规格:
# 白名单成员要么有注册行、要么在豁免集——无 op 行例外申报):
# - PickEncounter/PickSupply/PickMegastar/PickPartner/PickPlanner 五子类
#   待终态切换批换键名入表,入表后移出本集(锁恢复全覆盖);
# - PickInvest/PickStarTome/PickWishTrial/PickBoxCard(handler 自管消费
#   链)+ 三刷新动作 + HoldFrame(分支拦截型)= 永久豁免,无 op 行。
_TERMINAL_CONTRACT_REGISTRY_EXEMPT = (
    PickEncounter, PickSupply, PickInvest, PickMegastar, PickPartner,
    PickPlanner, PickStarTome, PickWishTrial, PickBoxCard,
    RefreshNodeOptions, RefreshSupply, RefreshInvestCards, HoldFrame,
)


def test_registry_covers_unified_vocab_and_pick_types():
    """注册完备锁(批4 主判据):统一词表 CW_ACTION_TYPES + cw_events
    pick 族 PICK_ACTION_TYPES 两运行时元组逐类断言注册表**类级**解析可
    命中(不构造业务动作实例,不读源码)——未注册 = 锁红;退役 = 删类,
    元组中不存在即天然不可复活(R1)。

    终态契约扩展(landing §3.1):白名单新成员要么有注册行、要么在
    豁免集;豁免成员反向断言确无注册行(防误注册,误挂 op = 确认链
    字段错位暗雷)。"""
    for cls in CW_ACTION_TYPES + PICK_ACTION_TYPES:
        if cls in _TERMINAL_CONTRACT_REGISTRY_EXEMPT:
            with pytest.raises(AssertionError):
                action_op_class_for_type(cls)
            continue
        op_cls = action_op_class_for_type(cls)
        assert isinstance(op_cls, type) and issubclass(op_cls, ActionOp), \
            f'{cls.__name__} 解析产物非 ActionOp 子类: {op_cls}'
    for cls in _TERMINAL_CONTRACT_REGISTRY_EXEMPT:
        assert cls in CW_ACTION_TYPES, cls.__name__


def test_pick_rows_resolve_class_and_instance_consistently():
    """pick 五行收编面:类级解析与实例级工厂解析同 op 类(行序 is-a
    语义一致;实例级仅本锁构造,注册完备锁本体不构造)。"""
    rows = [
        (EncounterPick, EncounterPickOp),
        (SupplyPick, SupplyPickOp),
        (MegastarPick, MegastarPickOp),
        (PartnerPick, PartnerPickOp),
        (PlannerPick, PlannerPickOp),
    ]
    for cls, expected in rows:
        assert action_op_class_for_type(cls) is expected, cls.__name__
        assert type(action_op_for(cls(idx=0))) is expected, cls.__name__


def test_class_level_isa_fallback_matches_instance_query():
    """is-a 兜底语义同注册表:LevelUpShop is-a LevelUp,类级首中
    LevelUp 行 → PrepLevelUpOp,与实例级查询一致(批3 先例的类级复验)。"""
    assert action_op_class_for_type(LevelUpShop) is PrepLevelUpOp
    assert action_op_class_for_type(LevelUp) is PrepLevelUpOp
    assert type(action_op_for(LevelUpShop(cost=4))) is PrepLevelUpOp


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
    assert EncounterPickOp(EncounterPick(idx=1)).execute(env) is True
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
    assert SupplyPickOp(SupplyPick(idx=0)).execute(env) is True
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
    assert MegastarPickOp(MegastarPick(idx=0)).execute(
        OverlayPickExecEnv(op=op)) is True
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
    assert PartnerPickOp(PartnerPick(idx=0)).execute(env) is True
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
    assert PartnerPickOp(PartnerPick(idx=0)).execute(env) is True
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
    assert PlannerPickOp(PlannerPick(idx=1)).execute(env) is True
    assert [(p.x, p.y, t) for p, t in ctrl.clicks] == [
        (700, 420, 0.15), (CwScreenPlanner.CONFIRM.x, CwScreenPlanner.CONFIRM.y, 0.15)]
    assert op._confirm_pending is True
    assert env.round_result is rs


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
    原样 + 期望外发),零缺陷发射;退役字段不再在场(对象面运行时检查,
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
    assert RefreshShopOp(RefreshShop()).execute(env) is True
    # 只读不比:刷前/刷后名集原样落账,比对结果不再由动作 op 预计算
    assert ledger.refresh_pre_names == ['旧卡A']
    assert ledger.refresh_post_names == ['新卡A', '新卡B']
    assert not hasattr(ledger, 'refresh_board_changed')
    # 期望随账本外发(刷前构建,消费点 = 入口观察对账点)
    assert ledger.refresh_expect is not None
    assert ledger.refresh_expect[0].gold_after == 48
    # 零缺陷发射(refresh_expect_mismatch 迁观察侧对账点)
    assert defect_calls == []


def test_entry_reconcile_emits_expect_mismatch_defect(monkeypatch):
    """入口观察对账点·期望腿(批4 迁入宿主):入口金 ≠ 期望金 →
    refresh_expect_mismatch 缺陷落台账(零决策;plane/round 取期望构建
    时点快照)。免费腿不满足(金已扣)→ 无存证调用。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_buy_cards as buy_mod,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        build_refresh_expect,
    )
    defect_calls: list = []
    monkeypatch.setattr(cw_defects, 'record_defect',
                        lambda *a, **k: defect_calls.append((a, k)))
    free_calls: list = []
    monkeypatch.setattr(buy_mod, '_record_free_refresh_proc',
                        lambda *a, **k: free_calls.append((a, k)))
    expect = build_refresh_expect(50, 2, [('旧卡A', 1)], 2, 5)
    ledger = ShopVisitLedger()
    ledger.refresh_pre_gold = 50
    ledger.refresh_pre_names = ['旧卡A']
    ledger.refresh_pending_reconcile = True
    ledger.refresh_expect = expect
    entry = SimpleNamespace(
        gold=49,   # ≠ 期望 gold_after=48(刷价另有实况)→ 金腿开票
        shop=[SimpleNamespace(kind='content',
                              card=SimpleNamespace(name='新卡A')),
              SimpleNamespace(kind='content',
                              card=SimpleNamespace(name='新卡B'))],
        plane=2, round_num=5)
    buy_mod._reconcile_refresh_pending(SimpleNamespace(), ledger, entry)
    assert len(defect_calls) == 1
    args, kwargs = defect_calls[0]
    assert args[0] == 'shop' and args[1] == 'refresh_expect_mismatch'
    assert kwargs['plane'] == 2 and kwargs['round_num'] == 5
    assert kwargs['reader_source'] == 'refresh_expect_reconcile'
    assert 'gold/-: 48' in kwargs['expected'] and kwargs['observed'] == '49'
    assert free_calls == []


def test_entry_reconcile_free_leg_fires_on_unchanged_gold(monkeypatch):
    """入口观察对账点·免费腿(三值单一源消费):金未扣 ∧ 牌面已变 →
    存证调用(存证体桩化,零真实 IO);期望腿同帧同评(本例期望 None
    隔离)。名集未变分支 = 零存证(比对单一源的 False 臂)。"""
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
    ledger.refresh_expect = None   # 期望腿隔离
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
