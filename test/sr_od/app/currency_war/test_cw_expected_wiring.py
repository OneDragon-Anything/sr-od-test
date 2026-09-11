"""op 逻辑效果推进接线单测(两态制 ADR-0651;前身为 DD-019 三缺口期望态接线批)。

覆盖:①overlay handler 侧确认逻辑推进(register_confirm_arrival 按 op 分道:
owned 本体直推 / 现金为王 gold 直推 / chosen_* 与 ConfirmStrategy 零写——
写端在各 handler);②装备分布逻辑推进(register_equip_worn 本体推进);
③apply_op_effect 原子 op 字段直推(卖出回金/owned 增减);④墓碑锁
(expected_state 条目表全套 API 复活即红)。纯函数 + StrategySession 直构,
零 IO 零识别。
"""
from __future__ import annotations
from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of

from sr_od.application.currency_war.kernel.cw_expected_state import (
    apply_op_effect,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PickBoxCard,
    SellBench,
    SellDeployed,
)
from sr_od.application.currency_war.kernel.cw_state import (
    DEPLOYED_FRONT_CAPACITY,
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.operations.cw_op.cw_op_equip_all import (
    register_equip_worn,
)
from sr_od.application.currency_war.operations.cw_screen._overlay_confirm import (
    register_confirm_arrival,
)


def _session() -> StrategySession:
    s = StrategySession()
    s.last_state = GameState(gold=50, plane=1, round_num=4)
    return s


# ==================== ①overlay handler 侧确认逻辑推进 ====================

def test_confirm_box_arrival_owned_direct_advance() -> None:
    """武装箱确认(ConfirmBox):owned += 选中装备(本体直推,策略器
    立即可读;无条目表挂账)。"""
    s = _session()
    register_confirm_arrival(s, 'ConfirmBox', '和平手枪', produced_by='t')
    assert '和平手枪' in s.last_owned_equips
    assert getattr(exec_state_of(s), 'expected_state', None) is None, \
        '两态制:无 expected_state 条目表'


def test_confirm_supply_arrival_owned_direct_advance() -> None:
    """补给节点确认(ConfirmSupply):owned += 选中装备名。"""
    s = _session()
    register_confirm_arrival(s, 'ConfirmSupply', '轮滑鞋', produced_by='t')
    assert '轮滑鞋' in s.last_owned_equips


def test_confirm_tome_arrival_star_badge_named() -> None:
    """秘典确认(ConfirmTome):owned += 「X星徽」(注册表命名对齐)。"""
    s = _session()
    register_confirm_arrival(s, 'ConfirmTome', '仙舟星徽', produced_by='t')
    assert '仙舟星徽' in s.last_owned_equips


def test_confirm_expert_cash_gold_direct_advance() -> None:
    """专家邀请函「现金为王」:gold +4 直推 session.last_state.gold
    (原「待实读」挂账条目随两态制废除转直推;shop_wave_top 实读覆盖修正)。"""
    s = _session()
    register_confirm_arrival(s, 'ConfirmExpertCash', '现金为王', produced_by='t')
    assert s.last_state.gold == 54, 'gold +4 逻辑直推(策略器立即可读)'


def test_confirm_arrival_no_item_or_session_noop() -> None:
    """无 session / 无 item → 安全 no-op(确认收尾不被推进面阻塞)。"""
    register_confirm_arrival(None, 'ConfirmBox', '和平手枪')
    s = _session()
    register_confirm_arrival(s, 'ConfirmBox', '')
    assert s.last_owned_equips in (None, [])


# ==================== ②装备分布逻辑推进(M7 穿装备) ====================

def _session_with_deployed() -> StrategySession:
    s = _session()
    s.last_owned_equips = ['轮滑鞋', '幸运星']
    front = BenchChar(slot=1, char_id='飞霄', star=1,
                      position_pref='front', equips=[])
    back = BenchChar(slot=1, char_id='卡芙卡', star=2,
                     position_pref='back', equips=[])
    exec_state_of(s).tracked_deployed = [front] + [None] * (DEPLOYED_FRONT_CAPACITY - 1) \
        + [back] + [None] * (10 - DEPLOYED_FRONT_CAPACITY - 1)
    return s


def test_register_equip_worn_front_advances_distribution() -> None:
    """前排穿戴(落点已验后调用):owned −1 + 角色 equips +1(本体直推)。"""
    s = _session_with_deployed()
    register_equip_worn(s, '轮滑鞋', '飞霄', 'front', 1, produced_by='t')
    assert s.last_owned_equips == ['幸运星']
    assert exec_state_of(s).tracked_deployed[0].equips == ['轮滑鞋']


def test_register_equip_worn_back_slot_index() -> None:
    """后排槽位坐标系:slot=1 → 槽位表下标 DEPLOYED_FRONT_CAPACITY
    (与 apply_op_effect SellDeployed 同式)。"""
    s = _session_with_deployed()
    register_equip_worn(s, '幸运星', '卡芙卡', 'back', 1, produced_by='t')
    assert exec_state_of(s).tracked_deployed[DEPLOYED_FRONT_CAPACITY].equips \
        == ['幸运星']


def test_register_equip_worn_none_session_safe() -> None:
    """无 session → 安全 no-op(穿戴主循环不被推进面阻塞)。"""
    register_equip_worn(None, '轮滑鞋', '飞霄', 'front', 1)


# ==================== ③apply_op_effect 原子 op 字段直推 ====================

def test_apply_op_effect_sell_bench_advances_gold_refund() -> None:
    """卖备战席:按注册表费算回金直推 last_state.gold(sell_refund
    星级×费率);tracked 本体推进 = 执行器辖,本函数不碰。"""
    s = _session()
    exec_state_of(s).tracked_bench_chars = [
        BenchChar(slot=3, char_id='花火', star=2, position_pref='?')]
    effects = apply_op_effect(s, SellBench(slot=3), produced_by='t')
    # 回金 = sell_refund(2星, 花火费):直推为非零正增量(具体值 = 注册表
    # 单一源,断言锁定「推进发生且为正」,不锁分布数值)
    assert s.last_state.gold > 50, '卖出回金逻辑直推'
    assert any(e['path'] == 'gold' for e in effects)


def test_apply_op_effect_pick_box_card_advances_owned() -> None:
    """武装箱选卡:owned += 选中装备(detail 形态「选卡 <名>」解析)。"""
    s = _session()
    apply_op_effect(s, PickBoxCard(), detail='选卡 轮滑鞋', produced_by='t')
    assert '轮滑鞋' in s.last_owned_equips


def test_apply_op_effect_sell_deployed_returns_equips_to_owned() -> None:
    """卖上阵角色:装备全额返还 → owned 直推 +1/件(游戏规则推算值)。"""
    s = _session()
    s.last_owned_equips = []
    exec_state_of(s).tracked_deployed = [
        BenchChar(slot=1, char_id='希儿', star=1, position_pref='front',
                  equips=['星海'])]
    apply_op_effect(s, SellDeployed(row='front', slot=1), produced_by='t')
    assert '星海' in s.last_owned_equips


def test_apply_op_effect_none_session_safe() -> None:
    """session=None → 空效果表 no-op(离线/无局调用面)。"""
    assert apply_op_effect(None, PickBoxCard()) == []


# ==================== ④墓碑锁(条目表全套 API 废除) ====================

def test_expected_state_ledger_api_retired() -> None:
    """ADR-0651 墓碑:ExpectedEntry/register_expected/clear_expected/
    reconcile_expected/set_evidence_sink/prep_obs_actual_for/
    prep_stall_pending_expected 复活即红(防挂账对账机制半删回归)。"""
    import sr_od.application.currency_war.kernel.cw_expected_state as es
    for gone in ('ExpectedEntry', 'register_expected', 'clear_expected',
                 'reconcile_expected', 'set_evidence_sink',
                 '_emit_evidence', 'expected_round_key'):
        assert not hasattr(es, gone), f'cw_expected_state.{gone} 应已废除'
    assert not hasattr(exec_state_of(_session()), 'expected_state'), \
        'ExecState.expected_state 容器应已删除'
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep,
    )
    assert not hasattr(cw_screen_prep, 'prep_obs_actual_for'), \
        'prep_obs 覆盖点单条目实读构造器应已废除'
    from sr_od.application.currency_war.operations import cw_loop
    assert not hasattr(cw_loop, 'prep_stall_pending_expected'), \
        'stall 滞留期望线索应已废除'


def test_confirm_chosen_family_has_no_registration_side_channel() -> None:
    """chosen_*(巨星/伙伴)与 ConfirmStrategy 经 register_confirm_arrival
    零写——写端 = 各 handler 的 write_logic/本体追加(单一写者,ADR-0651
    无「到账登记」旁路)。"""
    s = _session()
    s.chosen_partner = '丹恒'
    register_confirm_arrival(s, 'ConfirmPartner', '丹恒', produced_by='t')
    assert getattr(exec_state_of(s), 'expected_state', None) is None
    # 无 owned/gold 副作用
    assert s.last_state.gold == 50
    assert s.last_owned_equips in (None, [])
