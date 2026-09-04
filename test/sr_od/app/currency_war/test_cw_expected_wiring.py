"""期望态接线缺口三件批单测(DD-019 后果节三缺口;EXPECTED_STATE §3.3/§6)。

覆盖:①件1 overlay handler 侧到账登记(register_confirm_arrival 按 op 分道
语义 + prep_obs 覆盖点到账清账);②件2 CwOpEquipAll 装备分布期望态
(register_equip_worn 本体推进 + 条目登记 + 覆盖点清账);③件3 外循环 stall
消费 expected_state(prep_stall_pending_expected 只取 prep_obs 可确认条目)。
纯函数 + StrategySession 直构,零 IO 零识别。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_expected_state import (
    reconcile_expected,
    register_expected,
)
from sr_od.application.currency_war.kernel.cw_state import (
    DEPLOYED_FRONT_CAPACITY,
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.operations.cw_loop import (
    prep_stall_pending_expected,
)
from sr_od.application.currency_war.operations.cw_op.cw_op_equip_all import (
    register_equip_worn,
)
from sr_od.application.currency_war.operations.cw_screen._overlay_confirm import (
    register_confirm_arrival,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    prep_obs_actual_for,
)


def _session() -> StrategySession:
    s = StrategySession()
    s.last_state = GameState(gold=50, plane=1, round_num=4)
    return s


def _obs(gold_trusted: bool = False, spheres: bool = False) -> SimpleNamespace:
    return SimpleNamespace(state_gold_trusted=gold_trusted, spheres=spheres)


def _build_and_reconcile(s: StrategySession) -> list[dict]:
    """按生产 prep_obs 覆盖点同式(过滤+逐条目构造)reconcile,返 diff 行。"""
    act: dict = {}
    for p, e in list((getattr(s, 'expected_state', None) or {}).items()):
        if e.confirm_point != 'prep_obs':
            continue
        r = prep_obs_actual_for(s, e, s.last_state, _obs(), '', '')
        if r is not None:
            act[p] = r
    return reconcile_expected(s, 'prep_obs', act)


# ==================== 件1:overlay handler 侧到账登记 ====================

def test_confirm_box_arrival_owned_registered_and_cleared() -> None:
    """武装箱确认(ConfirmBox):owned += 选中装备(apply 推进本体)+ 条目
    登记;备战覆盖点本体确认 → 只清账不 diff。"""
    s = _session()
    register_confirm_arrival(s, 'ConfirmBox', '和平手枪', produced_by='t')
    assert '和平手枪' in s.last_owned_equips
    entry = s.expected_state['owned[和平手枪]']
    assert entry.kind == 'owned'
    assert _build_and_reconcile(s) == []
    assert 'owned[和平手枪]' not in s.expected_state


def test_confirm_supply_arrival_owned_registered() -> None:
    """补给节点确认(ConfirmSupply):owned += 选中装备名(§3.3 #18)。"""
    s = _session()
    register_confirm_arrival(s, 'ConfirmSupply', '轮滑鞋', produced_by='t')
    assert '轮滑鞋' in s.last_owned_equips
    assert 'owned[轮滑鞋]' in s.expected_state


def test_confirm_tome_arrival_star_badge_named() -> None:
    """秘典确认(ConfirmTome):owned += 「X星徽」(注册表命名对齐)。"""
    s = _session()
    register_confirm_arrival(s, 'ConfirmTome', '仙舟星徽', produced_by='t')
    assert '仙舟星徽' in s.last_owned_equips
    assert 'owned[仙舟星徽]' in s.expected_state


def test_confirm_strategy_arrival_cleared_via_body() -> None:
    """投资策略确认(ConfirmStrategy):active_strategies 条目登记(本体追加
    由 handler 既有写入点承担);本体已有该策略 → 覆盖点清账不 diff。"""
    s = _session()
    s.active_strategies.append('利息上调')
    register_confirm_arrival(s, 'ConfirmStrategy', '利息上调', produced_by='t')
    entry = s.expected_state['active_strategies[利息上调]']
    assert entry.kind == 'strategy'
    assert _build_and_reconcile(s) == []
    assert 'active_strategies[利息上调]' not in s.expected_state


def test_confirm_chosen_partner_megastar_registered() -> None:
    """巨星/伙伴确认(chosen_*,infra 未建 dict op → register_expected 直登):
    kind='strategy'、绑 prep_obs;本体已有 → 清账不 diff。"""
    s = _session()
    s.chosen_partner = '丹恒'
    register_confirm_arrival(s, 'ConfirmPartner', '丹恒', produced_by='t')
    assert s.expected_state['chosen_partner'].kind == 'strategy'
    assert _build_and_reconcile(s) == []
    assert 'chosen_partner' not in s.expected_state

    s2 = _session()
    s2.chosen_megastar = '花火'
    register_confirm_arrival(s2, 'ConfirmMegastar', '花火', produced_by='t')
    assert 'chosen_megastar' in s2.expected_state


def test_confirm_expert_cash_gold_binds_shop_wave_top() -> None:
    """专家邀请函「现金为王」:gold +4(待实读)绑 shop_wave_top——备战覆盖点
    透传不清账(F7);gold 可信源覆盖点清账不 diff(kind=gold 口径)。"""
    s = _session()
    register_confirm_arrival(s, 'ConfirmExpertCash', '现金为王', produced_by='t')
    entry = s.expected_state['gold']
    assert entry.kind == 'gold'
    assert entry.confirm_point == 'shop_wave_top'
    assert reconcile_expected(s, 'prep_obs', {}) == []
    assert 'gold' in s.expected_state
    assert reconcile_expected(s, 'shop_wave_top', {'gold': (54, True)}) == []
    assert 'gold' not in s.expected_state


def test_confirm_arrival_no_item_or_session_noop() -> None:
    """无 session / 无 item → 安全 no-op(确认收尾不被登记面阻塞)。"""
    register_confirm_arrival(None, 'ConfirmBox', '和平手枪')
    s = _session()
    register_confirm_arrival(s, 'ConfirmBox', '')
    assert not s.expected_state


# ==================== 件2:装备分布期望态(M7 穿装备) ====================

def _session_with_deployed() -> StrategySession:
    s = _session()
    s.last_owned_equips = ['轮滑鞋', '幸运星']
    front = BenchChar(slot=1, char_id='飞霄', star=1,
                      position_pref='front', equips=[])
    back = BenchChar(slot=1, char_id='卡芙卡', star=2,
                     position_pref='back', equips=[])
    s.tracked_deployed = [front] + [None] * (DEPLOYED_FRONT_CAPACITY - 1) \
        + [back] + [None] * (10 - DEPLOYED_FRONT_CAPACITY - 1)
    return s


def test_register_equip_worn_front_advances_distribution() -> None:
    """前排穿戴(落点已验后调用):owned −1 + 角色 equips +1,两覆盖点条目
    登记后由备战覆盖点只清账不 diff。"""
    s = _session_with_deployed()
    register_equip_worn(s, '轮滑鞋', '飞霄', 'front', 1, produced_by='t')
    assert s.last_owned_equips == ['幸运星']
    assert s.tracked_deployed[0].equips == ['轮滑鞋']
    assert 'owned[轮滑鞋]' in s.expected_state
    assert 'tracked_deployed[0]' in s.expected_state
    assert _build_and_reconcile(s) == []
    assert 'owned[轮滑鞋]' not in s.expected_state
    assert 'tracked_deployed[0]' not in s.expected_state


def test_register_equip_worn_back_slot_index() -> None:
    """后排槽位坐标系:slot=1 → 槽位表下标 DEPLOYED_FRONT_CAPACITY
    (与 apply_op_effect SellDeployed 同式)。"""
    s = _session_with_deployed()
    register_equip_worn(s, '幸运星', '卡芙卡', 'back', 1, produced_by='t')
    assert s.tracked_deployed[DEPLOYED_FRONT_CAPACITY].equips == ['幸运星']
    assert f'tracked_deployed[{DEPLOYED_FRONT_CAPACITY}]' in s.expected_state


def test_register_equip_worn_none_session_safe() -> None:
    """无 session → 安全 no-op(穿戴主循环不被登记面阻塞)。"""
    register_equip_worn(None, '轮滑鞋', '飞霄', 'front', 1)


# ==================== 件3:外循环 stall 消费 expected_state ====================

def test_prep_stall_pending_expected_filters_confirm_point() -> None:
    """只取 prep_obs 可确认条目(§6/F7):绑 shop_wave_top 的条目在本覆盖点
    不可确认 → 不计 stall 时钟;排序稳定保签名可比。"""
    s = _session()
    from sr_od.application.currency_war.kernel.cw_expected_state import (
        ExpectedEntry,
    )
    register_expected(s, ExpectedEntry(
        path='owned[和平手枪]', value='+1(待实读)', produced_by='t',
        at_round='p1-r2', kind='owned', confirm_point='prep_obs'))
    register_expected(s, ExpectedEntry(
        path='gold', value='+4(待实读)', produced_by='t', at_round='p1-r2',
        kind='gold', confirm_point='shop_wave_top'))
    out = prep_stall_pending_expected(s)
    assert out == ('owned[和平手枪]@p1-r2',)


def test_prep_stall_pending_expected_empty_session() -> None:
    """无容器 / 空容器 → 空元组(旧 session 构造路径兼容)。"""
    assert prep_stall_pending_expected(_session()) == ()
    assert prep_stall_pending_expected(None) == ()


def test_cw_loop_stall_block_consumes_pending_expected() -> None:
    """cw_loop stall 判定段接线烟雾(至多 1 条):prep_stall_pending_expected
    接线在场。失守场景 = 有人摘掉 stall 判定段对 pending 期望的消费接线,
    stall 留证退化为不带期望条目。不再加 'pending_expected' in src 之类
    子串断言(是本断言的子串,冗余);锁口径 = 接线存在性,至多 1 条烟雾。
    """
    import inspect

    from sr_od.application.currency_war.operations import cw_loop
    src = inspect.getsource(cw_loop)
    assert 'prep_stall_pending_expected' in src
