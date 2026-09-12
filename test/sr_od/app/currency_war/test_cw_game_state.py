"""GameState 迁移回归锁(迁移批次一;设计正本 = docs/develop/sr_od/application/currency_war/
changes/2026-09-11-unified-state/details/GameState-数据结构设计.md,下称「设计」)。

锁面 = 设计 §8.6 差距清单逐条(草板旧契约禁复发的负锁)+ §3 字段语义抽样
+ 心跳不断流(§2.4 关键结构 2)+ sim 合成口箱占席语义(§3.2.5;迁移批次一
任务书第 7 件)+ 设计 §8.7 批次三(策略器状态归位)与批次四(退役 +
relay 空值闸)两组锁——原独立批次文件按主题文件纪律归并,断言体零语义
改动。断言全部按设计语义写,禁按 level 驱动表/线性外推写
(设计 §3.2.7 回归测试断言约束)。

草板对照物 = .debug/temp/currency_war/record_data_model/board_state.py
(易失产物,不构成出处;出处 = 设计章节号)。
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    BENCH_CAPACITY_DEFAULT,
    BS_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    GameState,
    Field,
    NodeKey,
    Unit,
    apply_effect_burst_grant,
    bench_free_slots,
    bench_is_full,
    board_state_of,
    consume_defect_sink,
    grant_effect_node_refresh_balance,
    note_board_state_heartbeat,
    project_effect_capacity,
    set_defect_sink,
    slot_occupies,
    synthesize_from_game_state,
)

# ---- W1 sig 铺满 helper(测试写入口签名必填,ADR-0634;actor 已登记)----
from sr_od.application.currency_war.kernel.cw_game_state import (  # noqa: E402
    ChannelSig as _ChannelSig,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    register_sig_actors as _register_sig_actors,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    ActiveEffectInventory,
    CounterKey,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    BenchChar,
    CwWorkFrame,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    ShopCard as StateShopCard,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CwStrategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    MandateState,
    StrategyState,
    state_of,
)

_register_sig_actors('TestSigWriter')


def _sig() -> _ChannelSig:
    """渠道①签名(obs 族;观察/沿用/先验/离屏/观察事件)。"""
    return _ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _lsig() -> _ChannelSig:
    """渠道②签名(logic_action 族;逻辑写入/confirm)。"""
    return _ChannelSig(family='logic_action', actor='TestSigWriter',
                       mode='compute')


def _hsig() -> _ChannelSig:
    """渠道③签名(logic_hook 族;relay 中继)。"""
    return _ChannelSig(family='logic_hook', actor='TestSigWriter',
                       mode='compute')


_REPO = Path(__file__).resolve().parents[5]
_PKG = _REPO / 'src' / 'sr_od' / 'application' / 'currency_war'



# ============================================================ §8.6-1/§2.1
# Field 四来源 observation/logic/carried/prior + evidence 注记


def test_field_has_four_sources_and_evidence() -> None:
    """§8.6-1:Field 来源四分类齐备;carried/prior 必带 evidence 注记(§2.1)。"""
    assert Field(value=1, source='observation').value == 1
    assert Field(value=1, source='logic').source == 'logic'
    carried = Field(value=3, source='carried', evidence='carried:p1-r4')
    assert carried.source == 'carried' and carried.evidence == 'carried:p1-r4'
    prior = Field(value=82, source='prior', evidence='prior:adr-0559')
    assert prior.source == 'prior' and prior.evidence == 'prior:adr-0559'


def test_board_state_schema_version_has_no_default() -> None:
    """任务书件 1:schema_version 无默认值(新局必显式申报域版本,禁静默缺省)。"""
    with pytest.raises(TypeError):
        GameState()  # type: ignore[call-arg]


# ============================================================ §8.6-2/§2.4
# 两个关键结构:帧观察完整度标注+心跳 / bs_schema
# (预期条目表已随 ADR-0651 两态制废除——两步机制测试套同步退役,
#  换两态直写锁 + 墓碑锁。)


def test_write_logic_direct_write_immediately_readable() -> None:
    """ADR-0651 两态制核心锁:逻辑推算值经 write_logic **直接写字段**
    (source=logic)——策略器立即可读,无「预期条目表挂账」中间态。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20, sig=_sig())
    bs.write_logic(bs.gold, 17, produced_by='TestSigWriter', sig=_lsig())
    assert bs.gold.value == 17, '逻辑直写:字段立即可读(策略器读得到)'
    assert bs.gold.source == 'logic', 'logic 值保持 logic 来源(§8.1)'


def test_two_step_mechanism_retired_tombstone() -> None:
    """ADR-0651 墓碑锁:expect/confirm/discard_expected/pending_entries/
    expected 条目表与模块级 PendingEntry/reconcile_pending_observation
    全套废除——复活即红(防两步机制半删回归)。"""
    for gone in ('expect', 'confirm', 'discard_expected', 'pending_entries'):
        assert not hasattr(GameState, gone), f'GameState.{gone} 应已废除'
    assert 'expected' not in {f.name for f in dataclasses.fields(GameState)}, \
        'expected 条目表应已删除'
    import sr_od.application.currency_war.kernel.cw_game_state as bs_mod
    assert not hasattr(bs_mod, 'PendingEntry'), 'PendingEntry 应已删除'
    assert not hasattr(bs_mod, 'reconcile_pending_observation'), \
        '核对点闭环函数应已删除'


def test_logic_written_fields_tracks_and_reanchors() -> None:
    """§8.4 logic_written_fields:已直写未重锚的 logic 字段名;观察覆盖后除名。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.write_logic(bs.gold, 17, produced_by='TestSigWriter', sig=_lsig())
    assert bs.logic_written_fields() == ['gold']
    bs.observe(bs.gold, 19, sig=_sig())
    assert bs.logic_written_fields() == [], '观察重锚后不再算 logic 在写'


def test_frame_obs_marker_consumed_on_read() -> None:
    """§2.4 关键结构 2:帧观察完整度标注 full/view/none,消费即清。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.mark_frame_obs('full')
    assert bs.consume_frame_obs() == 'full'
    assert bs.consume_frame_obs() == 'none', '消费即清'


def test_write_seq_is_monotonic_carrier() -> None:
    """§2.4:停更检测哨兵 = 只增不减计数(写点序号),不做帧标注现值
    (消费即清后当不了哨兵);心跳观察者断言「不断流」。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    seq0 = bs.heartbeat()
    bs.observe(bs.gold, 20, sig=_sig())
    bs.observe(bs.gold, 21, sig=_sig())
    bs.mark_frame_obs('full')
    assert bs.consume_frame_obs() == 'full', '消费标注不影响哨兵计数'
    seq1 = bs.heartbeat()
    assert seq1 > seq0, '写点推进 → 心跳单调递增(不断流)'
    bs.carry(bs.gold, frame='p1-r5', sig=_sig())
    assert bs.heartbeat() > seq1, 'carried 写也是写点,哨兵照常推进'


def test_bs_schema_domain_map_present() -> None:
    """§2.4 关键结构 3:bs_schema = 域粒度版本映射(缺域键 = 该域未建模)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    assert isinstance(bs.bs_schema, dict) and bs.bs_schema
    assert 'node' in bs.bs_schema and 'economy' in bs.bs_schema


# ============================================================ §8.6-3
# 画面附加域与缺口域(开局初值域/十事件屏域/结算事件位/刷新计数组/持久账本组)

# 画面附加域 = kernel 三域口径(cw_game_state._PAYLOAD_DOMAINS 同源):
# shop/encounter/supply。settlement 是结算真值组(§3.5.1)非画面 payload,
# 不在附加域词表(负断言见 test_leave_screen_payload_only)。
_PAYLOAD_DOMAINS = ('shop', 'encounter', 'supply')
_CHOSEN_DOMAINS = ('chosen_encounter', 'chosen_supply', 'chosen_megastar',
                   'chosen_partner', 'chosen_wish', 'chosen_fortune',
                   'chosen_hack', 'chosen_expert', 'chosen_tome',
                   'chosen_equip')
# ~~skip_battle_active/remaining 已移出本组(迁移批次二载体归一,§8.6-3):
# 免战牌激活态+剩余次数正本 = effect_inventory.remaining_uses(§5.1),
# GameState 不设平行 Field——负向锁见本文件下方 test_skip_battle_fields_retired。
_LEDGER_DOMAINS = ('equips', 'consumables')
_REFRESH_GROUP = ('free_refresh_balance', 'paid_refresh_count',
                  'total_refresh_count', 'prev_node_spent')
_NODE_SCREEN_REFRESH = ('encounter_refresh_used', 'supply_refresh_used',
                        'env_refresh_used', 'strategy_refresh_used')
_OPENING_DOMAINS = ('game_mode', 'node_path')


@pytest.mark.parametrize('name', _PAYLOAD_DOMAINS + _CHOSEN_DOMAINS
                         + _LEDGER_DOMAINS + _REFRESH_GROUP
                         + _NODE_SCREEN_REFRESH + _OPENING_DOMAINS)
def test_gap3_domains_present(name: str) -> None:
    """§8.6-3:草板未入的域在骨架里在场(设计 §8.4 注:迁移批次一补齐;
    P1-2 落地审:节点屏刷新计数组 §3.4.1-4 亦点名在列)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    assert isinstance(getattr(bs, name), Field), f'缺域:{name}'


def test_skip_battle_fields_retired() -> None:
    """§8.6-3 载体归一(迁移批次二):免战牌激活态+剩余次数正本 =
    effect_inventory.remaining_uses(ActiveEffect.remaining_uses「次数类
    余量(免战牌×2 等)」,§5.1 同型躺平/节省工位)——GameState 平行
    Field 按正本归一移除(改锁依据:设计正本明文,非机械跟绿)。"""
    field_names = {f.name for f in dataclasses.fields(GameState)}
    for banned in ('skip_battle_active', 'skip_battle_remaining'):
        assert banned not in field_names, f'免战牌平行 Field 应已归一移除:{banned}'


def test_gap3_node_screen_refresh_schema_domain() -> None:
    """P1-2:节点屏刷新计数组有 bs_schema 域键(缺域键 = 该域未建模,§3.7.1);
    逐卡计数形状 = 卡名 → 已用次数(§3.4.4)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    assert bs.bs_schema.get('node_screen_refresh') == 1
    bs.observe(bs.strategy_refresh_used, {'白银投资': 1}, sig=_sig())
    assert bs.strategy_refresh_used.value == {'白银投资': 1}


def test_gap4_missing_fields_present() -> None:
    """§8.6-4:board/level_up_cost/back_layout/spheres/分类子态/对局类型/
    节点序列台账/hp 保底事件位在场;bench 容量默认恒 9(§3.2.5)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    for name in ('board', 'level_up_cost', 'back_layout', 'spheres',
                 'prep_substate', 'hp_floor_triggered'):
        assert isinstance(getattr(bs, name), Field), f'缺字段:{name}'
    assert BENCH_CAPACITY_DEFAULT == 9 == BENCH_CAPACITY, \
        '备战席容量默认恒 9,不随等级变(§3.2.5;现役 cw_state 同口径)'
    bv = BenchView()
    assert bv.capacity == 9 and len(bv.slots) == 0


def test_game_mode_field_accepts_two_modes() -> None:
    """§3.1.2:对局类型=标准/超频博弈(两屏均无建档区域,接线前先补档——
    字段先入 schema,写端挂补档批)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.game_mode, '标准', sig=_sig())
    assert bs.game_mode.value == '标准'


def test_node_path_ledger_is_type_sequence() -> None:
    """§3.2.2:节点序列台账 = 本局节点**类型序**台账(权威写端=备战帧
    node_path 现读;内容主题替换族不改类型序,台账不受影响)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.node_path, ['battle', 'encounter', 'reward', 'boss'], sig=_sig())
    assert bs.node_path.value == ['battle', 'encounter', 'reward', 'boss']


def test_prep_substate_four_values() -> None:
    """§3.2.17:分类子态四档(三暗色锁定 + 恢复锁定);恢复锁定=会话推断档
    无帧识别锚,写端=接管协议(§6.3),禁按帧子态统一路由。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    for v in ('策略锁定', '遭遇锁定', '补给锁定', '恢复锁定'):
        bs.observe(bs.prep_substate, v, sig=_sig())
        assert bs.prep_substate.value == v


def test_hp_floor_event_is_pure_observation_registry() -> None:
    """§3.5.3:hp 保底触发事件位 = 纯观察登记、无判据载体(消费端按不确定降级)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    assert bs.hp_floor_triggered.value is None
    bs.observe(bs.hp_floor_triggered, True, sig=_sig())
    assert bs.hp_floor_triggered.value is True


# ============================================================ §8.6-4(续)
# 派生不存储:席空数/席满判定/board 下档阈值 = 计算函数,禁入 schema


def test_derived_quantities_not_stored() -> None:
    """§8.6-4:派生量禁入 schema(board_next_tier/席空数/席满判定;
    bench_full_flag 警告位已裁撤不建,§3.2.5)。"""
    field_names = {f.name for f in dataclasses.fields(GameState)}
    for banned in ('board_next_tier', 'free_bench_slots', 'bench_full_flag',
                   'bench_is_full'):
        assert banned not in field_names, f'派生量入了 schema:{banned}'


def test_bench_free_slots_unobserved_is_none() -> None:
    """§3.2.5:席空数没读到 = 不确定,**禁猜 0**——bench 从未观察返 None。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    assert bench_free_slots(bs) is None
    assert bench_is_full(bs) is None


def test_slot_occupancy_real_machine_truth() -> None:
    """§3.2.5 记录模型按实机真值:箱/秘典占席,空槽不占(奖励球不占席,
    它是点击目标不是席位居民)。"""
    assert slot_occupies('unit') is True
    assert slot_occupies('supply_box') is True, '补给箱落席占 1 槽(实机真值)'
    assert slot_occupies('tome') is True, '星徽秘典为席位内容物(占席待实机证实)'
    assert slot_occupies('empty') is False


def test_bench_free_slots_counts_occupying_kinds() -> None:
    """席空数派生 = capacity − 占席槽数;箱占席计入(实机真值,sim 无箱实体
    只是 sim 内部口径约定,不进记录模型)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    slots = [BenchSlot(kind='unit'), BenchSlot(kind='supply_box'),
             BenchSlot(kind='tome')] + [BenchSlot(kind='empty')] * 6
    bs.observe(bs.bench, BenchView(slots=slots, capacity=9), sig=_sig())
    assert bench_free_slots(bs) == 6
    assert bench_is_full(bs) is False
    full = [BenchSlot(kind='unit')] * 8 + [BenchSlot(kind='supply_box')]
    bs.observe(bs.bench, BenchView(slots=full, capacity=9), sig=_sig())
    assert bench_is_full(bs) is True, '8 单位 + 1 箱 = 满(箱占席)'


# ============================================================ §8.6-5
# 构造守卫:frozen 帧替换 + hp 不变式 + 缺陷台账挂点


def test_field_is_frozen_frame() -> None:
    """§8.6-5:Field 冻结——写入只能经 GameState API 换新帧,禁原地改。"""
    f = Field(value=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.value = 2  # type: ignore[misc]


def test_observe_replaces_frame_not_mutates() -> None:
    """§2.4:frozen 帧替换——旧帧引用保持旧值(持旧引用的读者不被跨时段写回污染)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    old = bs.gold
    bs.observe(bs.gold, 20, sig=_sig())
    assert old.value is None and old.source == 'observation'
    assert bs.gold.value == 20 and bs.gold is not old


def test_observe_rejects_none_loses_are_carried_not_cleared() -> None:
    """§2.2 硬边界:observe(None) 拒绝——失读走 carried(处置①)或保持 None
    (处置②),字段一旦有过正式值任何失读不得清成 None。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    with pytest.raises(ValueError):
        bs.observe(bs.hp, None, sig=_sig())
    bs.observe(bs.hp, 80, sig=_sig())
    bs.carry(bs.hp, frame='p1-r5', sig=_sig())
    assert bs.hp.value == 80, '失读帧沿用上次好值'
    assert bs.hp.source == 'carried' and bs.hp.evidence == 'carried:p1-r5'
    assert bs.hp.value is not None, '硬边界:正式值永不清成 None'


def test_carry_on_never_read_keeps_none() -> None:
    """§2.2 处置②:字段从未读过(机制性不可读态+新局)→ 保持 None
    (机制性 None 专指此态)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.carry(bs.gold, frame='p1-r1', sig=_sig())
    assert bs.gold.value is None


def test_write_prior_requires_prior_evidence() -> None:
    """§2.1/§3.1.6:prior 写入必带 prior: 来源注记;禁扩散(仅显式申报条目)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    with pytest.raises(ValueError):
        bs.write_prior(bs.hp, 82, evidence='carried:x', sig=_sig())
    bs.write_prior(bs.hp, 82, evidence='prior:adr-0559', sig=_sig())
    assert bs.hp.value == 82 and bs.hp.source == 'prior'


def test_leave_screen_payload_only() -> None:
    """§2.2 显式例外:画面附加域(kernel 三域口径 shop/encounter/supply)离开
    画面置 None 是结构事实,不受 carried 硬边界辖;整局字段禁走此口,
    settlement(结算真值组,§3.5.1)非画面 payload 同样禁离屏清值。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.shop, SimpleNamespace(cards=[]), sig=_sig())
    bs.observe(bs.encounter, SimpleNamespace(options=[]), sig=_sig())
    bs.observe(bs.supply, SimpleNamespace(options=[]), sig=_sig())
    bs.leave_screen(bs.shop, sig=_sig())
    bs.leave_screen(bs.encounter, sig=_sig())
    bs.leave_screen(bs.supply, sig=_sig())
    assert bs.shop.value is None and bs.encounter.value is None \
        and bs.supply.value is None
    bs.observe(bs.gold, 20, sig=_sig())
    with pytest.raises(ValueError):
        bs.leave_screen(bs.gold, sig=_sig()), '整局字段(有过正式值)禁离屏清值'
    bs.observe(bs.settlement, SimpleNamespace(hp_after=76), sig=_sig())
    with pytest.raises(ValueError):
        bs.leave_screen(bs.settlement, sig=_sig()), 'settlement 非画面附加域,禁离屏'


def test_observe_over_logic_mismatch_emits_defect_row() -> None:
    """§2.3/ADR-0651:观察覆盖 logic 值失配 → 失配记入缺陷台账(挂点注入,
    缺省关);观察赢——来源改回 observation。失配 = 推算 bug 留证修码。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.write_logic(bs.gold, 17, produced_by='TestSigWriter', sig=_lsig())
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        bs.observe(bs.gold, 19, sig=_sig())
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert len(rows) == 1
    assert rows[0]['field'] == 'gold'
    assert rows[0]['expected'] == 17 and rows[0]['actual'] == 19
    assert bs.gold.source == 'observation', '观察赢:来源改回 observation'


def test_observe_over_logic_match_silent() -> None:
    """§2.3/ADR-0651:观察值与 logic 值一致 = 投影被实读核实形态,不留缺陷行。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.write_logic(bs.gold, 17, produced_by='TestSigWriter', sig=_lsig())
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        bs.observe(bs.gold, 17, sig=_sig())
    finally:
        set_defect_sink(None)
    assert rows == []


# ============================================================ §8.6-7
# Unit.faction 删除:阵营由 char_id 查注册表派生(开拓者按当前排,ADR-0158)


def test_unit_has_no_faction_field() -> None:
    """§8.6-7:阵营不是 Unit 的存储字段(§3.2.3 禁与注册表双源)。"""
    unit_fields = {f.name for f in dataclasses.fields(Unit)}
    assert 'faction' not in unit_fields
    u = Unit(char_id='阿格莱雅', star=1)
    assert u.equips == [] and u.slot == 0


def test_bench_slot_kind_taxonomy() -> None:
    """§8.2:BenchSlot 四种内容之一;kind=unit 时 unit 有效。"""
    assert BenchSlot().kind == 'empty'
    s = BenchSlot(kind='unit', unit=Unit(char_id='花火', star=2))
    assert s.unit is not None and s.unit.star == 2


# ============================================================ §3 语义抽样


def test_streak_signed_value_preserved() -> None:
    """§3.2.12:streak 带符号(正=连胜/负=连败);无方向读数禁覆盖带符号值
    ——观察口只收带方向真值。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.streak, -3, sig=_sig())
    assert bs.streak.value == -3


def test_shop_refresh_cost_none_is_not_zero() -> None:
    """§3.3.4/ADR-0622:免费帧不写(None≠标价 0);识别失败=None 禁兜底改值
    ——失读走 carried,值保持上次读数。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    assert bs.shop_refresh_cost.value is None, '新局未读 = None,不是 0'
    bs.observe(bs.shop_refresh_cost, 2, sig=_sig())
    bs.carry(bs.shop_refresh_cost, frame='shop-free-frame', sig=_sig())
    assert bs.shop_refresh_cost.value == 2
    assert bs.shop_refresh_cost.value != 0


def test_event_overlay_none_vs_not_read_distinct() -> None:
    """§3.6.1:'none'=确认无浮层(显式枚举值);None=这一帧没读到。两者分写。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    assert bs.event_overlay.value is None, '未读到'
    bs.observe(bs.event_overlay, 'none', sig=_sig())
    assert bs.event_overlay.value == 'none', '确认无浮层'


def test_back_layout_writes_real_slot_count_with_superset_mark() -> None:
    """§3.2.7:布局档写真实槽位数;域外按 8 格超集读全扩展带,evidence 补
    superset 标记(防超集近似被当精确值消费)。断言不按 level 驱动表写。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.back_layout, 7, sig=_sig())
    assert bs.back_layout.value == 7
    bs.observe(bs.back_layout, 8, evidence='superset', sig=_sig())
    assert bs.back_layout.value == 8 and bs.back_layout.evidence == 'superset'


# ============================================================ 单例宿主与心跳观察者


def test_board_state_of_binds_per_session() -> None:
    """§1:单例,每局新建——session 对象 = 局身份,新 session = 新 GameState。"""
    s1 = SimpleNamespace()
    s2 = SimpleNamespace()
    assert board_state_of(s1) is board_state_of(s1)
    assert board_state_of(s1) is not board_state_of(s2)


def test_heartbeat_observer_flags_stall() -> None:
    """§2.4:心跳观察者采样单调推进量;连续 2 次零推进 = 断流计数上行
    (诊断位,不停机);有推进即复位。"""
    sess = SimpleNamespace()
    note_board_state_heartbeat(sess)   # 首采:基线
    note_board_state_heartbeat(sess)   # 零推进 #1
    bs = board_state_of(sess)
    assert bs.hb_stall_count == 1
    note_board_state_heartbeat(sess)   # 零推进 #2 → 达标
    assert bs.hb_stall_count >= 2
    bs.observe(bs.gold, 20, sig=_sig())            # 有推进
    note_board_state_heartbeat(sess)
    assert bs.hb_stall_count == 0, '推进即复位'


# ============================================================ §3.2.5(任务书件 7)
# sim 合成口:记录模型按实机真值箱占席;sim 真值合成 evidence 恒 sim:synthesized


def test_sim_synthesis_preserves_bench_slots() -> None:
    """§2.1/§3.2.5:sim 真值合成 bench 槽位保序(0 基下标 → 1 基物理槽位),
    记录模型不采 sim「箱不占席」内部口径。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    # 经构造器传入(__post_init__ pad 到定长 9,ADR-0316 形状契约;直赋值
    # 绕过 pad 是旧紧缩构造兼容域,合成口输出侧补齐见模块实现)。
    st = CwWorkFrame(bench=[
        BenchChar(slot=1, char_id='阿格莱雅', star=1),
        None,
        BenchChar(slot=3, char_id='花火', star=2),
    ])
    st.gold = 20
    st.hp = 80
    synthesize_from_game_state(bs, st, at_round='p1-r2')
    view = bs.bench.value
    assert view is not None and view.capacity == 9
    assert [s.kind for s in view.slots] == ['unit', 'empty', 'unit'] \
        + ['empty'] * 6, '槽位保序:sim 紧缩/稀疏表 1:1 映射物理槽位'
    assert view.slots[0].unit is not None \
        and view.slots[0].unit.char_id == '阿格莱雅'
    assert bs.gold.value == 20
    assert bs.gold.evidence == 'sim:synthesized@p1-r2', \
        '§2.1:evidence 恒带标记;at_round 轮键并入注记(P2-6,非死参)'
    assert bs.gold.source == 'observation', 'sim 真值记 observation'
    assert bs.hp.value == 80


def test_sim_synthesis_none_truth_not_written() -> None:
    """sim 帧真值 None 的字段不写(sim 无识别过程,不存在失读;未建模域保持
    None 诚实缺位,禁合成假值)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    st = CwWorkFrame()   # hp=None(未观测态);gold 默认 0 且 readable=True(P2-3 实断言依据)
    synthesize_from_game_state(bs, st, at_round='p1-r1')
    assert bs.hp.value is None
    assert bs.node.value is None, \
        'node_type 未建模(裸构造 None)不合成 kind 占位(P1-1 同型泛化)'
    assert bs.gold.value == 0 \
        and bs.gold.evidence == 'sim:synthesized@p1-r1', \
        'gold 真值(缺省 0,readable)合成 observation;at_round 并入 evidence(P2-6)'


def test_sim_engine_feeds_board_state() -> None:
    """任务书件 7:engine_p1 决策帧合成段接线——sim 引擎跑一局,session 的
    GameState 被喂入(心跳推进 + bench 观察 sim:synthesized)。"""
    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    class _PassiveStrategy:
        def decide_shop_screen(self, sess, cfg):  # noqa: ANN001
            return []

    sess = StrategySession()
    simulate_p1(7, pool='fallback', strategy=_PassiveStrategy(), session=sess)
    bs = board_state_of(sess)
    assert bs.heartbeat() > 0, 'sim 合成口推进心跳(不断流)'
    assert bs.bench.value is not None, '合成口写入 bench(槽位真值)'
    assert bs.gold.source == 'observation'
    assert bs.gold.evidence is not None \
        and bs.gold.evidence.startswith('sim:synthesized@'), \
        '引擎路径传轮键 → evidence 带标记+轮键后缀(P2-6)'


def _feed_ctx(sess: SimpleNamespace) -> SimpleNamespace:
    """read_game_state 观察流测试的最小 ctx(mock ocr_service 空读;
    screen_loader 空 = 全部 area rect 缺失 → 各 reader 自然失读)。"""
    return SimpleNamespace(
        cw_match=SimpleNamespace(session=sess),
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        ocr_service=SimpleNamespace(get_ocr_result_list=lambda **kw: []),
    )


def _patch_clean_readers(monkeypatch: pytest.MonkeyPatch) -> None:
    """prep_clean 帧各 reader 桩(只读链,零像素;真读值显式给定)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    from sr_od.application.currency_war.obs import cw_observation as obs

    monkeypatch.setattr(obs, 'read_gold_settled', lambda ctx, screen: 20,
                        raising=False)
    monkeypatch.setattr(obs, 'read_phase_round', lambda ctx, screen: (1, 4),
                        raising=False)
    monkeypatch.setattr(obs, 'read_hp_opt', lambda ctx, screen: None,
                        raising=False)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='', node_t=None:
                        (82, False), raising=False)
    monkeypatch.setattr(obs, 'read_node_type', lambda ctx, screen: 'battle',
                        raising=False)
    monkeypatch.setattr(obs, 'gate_node_type', lambda v, rn: v, raising=False)
    monkeypatch.setattr(obs, 'ledger_node_type',
                        lambda sess_, p, r: None, raising=False)
    monkeypatch.setattr(obs, 'verify_node_type_votes',
                        lambda ctx, screen, p, r: None, raising=False)
    monkeypatch.setattr(obs, 'read_xp_progress',
                        lambda ctx, screen, expected_level=None: (2, 8),
                        raising=False)
    monkeypatch.setattr(obs, 'read_level_raw_opt', lambda ctx, screen: 5,
                        raising=False)
    monkeypatch.setattr(obs, '_level_from_xp', lambda xp: None, raising=False)
    monkeypatch.setattr(obs, '_resolve_level',
                        lambda raw, exp, xp_lv, last: (5, [], True),
                        raising=False)
    monkeypatch.setattr(obs, 'resolve_paddle_pair',
                        lambda ctx, screen, level: (None, None), raising=False)
    monkeypatch.setattr(obs, 'board_from_tracked', lambda tracked: None,
                        raising=False)
    monkeypatch.setattr(obs, 'is_prep_like_frame',
                        lambda ctx, screen: True, raising=False)
    monkeypatch.setattr(obs, '_board_pairs',
                        lambda ctx, screen, max_count=9, expected=None:
                        ({'列车同行': (2, 3)}, True), raising=False)


def test_observation_feed_wires_board_state(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """任务书件 2:read_game_state 观察流接线——真读字段进 GameState
    (observation);失读字段走 carried/prior;hp 写入闸:非真读帧不经
    observe 假值入账。"""
    from sr_od.application.currency_war.obs import cw_observation

    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    _patch_clean_readers(monkeypatch)

    cw_observation.read_game_state(_feed_ctx(sess), None, phase='prep_clean')

    bs = board_state_of(sess)
    assert bs.gold.value == 20 and bs.gold.source == 'observation'
    assert bs.node.value is not None
    assert bs.node.value.plane == 1 and bs.node.value.round_num == 4
    assert bs.node.value.kind == 'battle'
    assert bs.hp.value == 82 and bs.hp.source == 'prior', \
        'hp 读不到∧session 无真值 = 开局先验形态,prior 写入(§3.1.6)'
    assert bs.hp.evidence == 'prior:adr-0559'
    assert bs.level.value == 5 and bs.level.source == 'observation'
    assert bs.board.value == {'列车同行': 2}


def test_observation_feed_hp_unified_loss_semantics(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """hp 失读统一口径三分支(§2.2,任务书件 1 断言面):
    ①字段已有正式值 → 失读写 carried(沿用+来源帧标注);
    ②字段从未读过 → 保持 None(机制性 None,session 外源值禁猜入);
    真值帧 → observation 转正。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    from sr_od.application.currency_war.obs import cw_observation

    sess = SimpleNamespace(last_streak=0, active_strategies=[],
                           last_hp_real=80, last_hp_real_node=12)
    _patch_clean_readers(monkeypatch)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='', node_t=None:
                        (80, False), raising=False)

    cw_observation.read_game_state(_feed_ctx(sess), None, phase='prep_clean')

    bs = board_state_of(sess)
    assert bs.hp.value is None, \
        'GameState 从未读过 → 处置②保持 None(session 暖启动值不入,禁猜)'

    # 真值帧到达 → observation 转正
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='', node_t=None:
                        (76, True), raising=False)
    cw_observation.read_game_state(_feed_ctx(sess), None, phase='prep_clean')
    assert bs.hp.value == 76 and bs.hp.source == 'observation'

    # 再失读 → 处置①carried 沿用上次好值(禁清成 None)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='', node_t=None:
                        (76, False), raising=False)
    cw_observation.read_game_state(_feed_ctx(sess), None, phase='prep_clean')
    assert bs.hp.value == 76, '硬边界:正式值永不清成 None'
    assert bs.hp.source == 'carried'
    assert (bs.hp.evidence or '').startswith('carried:')


def test_observation_feed_shop_open_reads_refresh_price(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """任务书件 6:商店开态帧刷新费通道(ADR-0622)——现场读数写 shop_refresh_cost
    (observation);识别失败 = carried(禁兜底改值,§3.3.4);hp 写入闸:
    商店开态 spec 无 'hp' → 假值防线(PHASE_FIELD_SPEC 门)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    from sr_od.application.currency_war.obs import cw_observation as obs

    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    monkeypatch.setattr(obs, 'read_gold_settled', lambda ctx, screen: 20,
                        raising=False)
    monkeypatch.setattr(obs, 'read_phase_round', lambda ctx, screen: (1, 5),
                        raising=False)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='', node_t=None:
                        (82, False), raising=False)
    monkeypatch.setattr(obs, 'read_level_up_cost', lambda ctx, screen: 4,
                        raising=False)
    monkeypatch.setattr(obs, 'board_from_tracked', lambda tracked: None,
                        raising=False)
    monkeypatch.setattr(obs, '_board_pairs',
                        lambda ctx, screen, max_count=9, expected=None:
                        ({}, False), raising=False)
    monkeypatch.setattr(obs, 'read_shop_cards', lambda ctx, screen: [],
                        raising=False)
    monkeypatch.setattr(obs, 'read_refresh_probs', lambda ctx, screen: None,
                        raising=False)
    monkeypatch.setattr('sr_od.application.currency_war.obs.cw_shop_refresh_obs'
                        '.read_shop_refresh_price',
                        lambda ctx, screen: 2, raising=False)

    obs.read_game_state(_feed_ctx(sess), None, phase='prep_shop_open')

    bs = board_state_of(sess)
    assert bs.shop_refresh_cost.value == 2
    assert bs.shop_refresh_cost.source == 'observation'

    # 识别失败:carried 保上次值,禁兜底(§3.3.4 None≠0)
    monkeypatch.setattr('sr_od.application.currency_war.obs.cw_shop_refresh_obs'
                        '.read_shop_refresh_price',
                        lambda ctx, screen: None, raising=False)
    obs.read_game_state(_feed_ctx(sess), None, phase='prep_shop_open')
    bs2 = board_state_of(sess)
    assert bs2.shop_refresh_cost.value == 2
    assert bs2.shop_refresh_cost.source == 'carried'


def test_observation_feed_battle_frame_kind_inherits(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """P1-1:battle_or_transit 帧 spec 无 node_type → kind 禁合成 'prep'
    占位假值——从 bs.node 现值继承合成新键(plane/round 真读更新),
    evidence 标继承;无现值且未读 → node 不写保持 None(禁猜)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    from sr_od.application.currency_war.obs import cw_observation as obs

    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    monkeypatch.setattr(obs, 'read_phase_round', lambda ctx, screen: (1, 9),
                        raising=False)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='', node_t=None:
                        (None, False), raising=False)

    # 无现值且未读:battle 帧 node 不写(占位 'prep' 已裁撤)
    obs.read_game_state(_feed_ctx(sess), None, phase='battle_or_transit')
    bs = board_state_of(sess)
    assert bs.node.value is None, 'kind 未读∧无现值 → node 不写(禁猜)'

    # 有现值(boss):继承 kind 合成新键,evidence 标继承
    bs.observe(bs.node, NodeKey(plane=1, round_num=8, kind='boss'),
               sig=_sig())
    obs.read_game_state(_feed_ctx(sess), None, phase='battle_or_transit')
    node = bs.node.value
    assert node is not None and node.kind == 'boss', \
        'kind 未读帧继承现值,禁覆成占位假值(P1-1)'
    assert node.round_num == 9, 'plane/round 真读照常更新'
    assert bs.node.evidence == 'kind_inherited'

    # node_type 真读帧(pre_clean):kind 用真读值,无继承标记
    _patch_clean_readers(monkeypatch)
    obs.read_game_state(_feed_ctx(sess), None, phase='prep_clean')
    assert bs.node.value.kind == 'battle'
    assert bs.node.evidence is None, '真读帧无继承标记'


def test_cost_source_passthrough_not_folded() -> None:
    """P2-4:cost_source 原值透传不折叠——roster_fallback 的「徽章失读」
    证据分级禁丢(生产 reader 产三值,批次二消费前必须有区分)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    st = CwWorkFrame()
    st.shop = [StateShopCard(x=1, name='花火', cost=2, star=1,
                             cost_source='roster_fallback')]
    synthesize_from_game_state(bs, st, at_round='p1-r3')
    card = bs.shop.value.cards[0]
    assert card.cost_source == 'roster_fallback', 'sim 合成口同样透传'


def test_consume_defect_sink_drains() -> None:
    """缺陷台账挂点 = 注入槽模式(测试纪律:缺省关+显式接通;模块级缓冲
    在 setup 先清,隔离整条副作用链);consume 供装配点取走行后复位,
    防跨局残留。"""
    consume_defect_sink()   # 清其他测试遗留(模块级缓冲 = 副作用链桩化点)
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.write_logic(bs.gold, 17, produced_by='TestSigWriter', sig=_lsig())
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        bs.observe(bs.gold, 18, sig=_sig())
    finally:
        drained = consume_defect_sink()
    assert len(rows) == 1 and drained == rows
    assert consume_defect_sink() == []


# ============================================================ §8.7 批次三
# 策略器状态归位(原独立批次文件按主题文件纪律归并入本文件;断言体零语义
# 改动)。锁面 = §8.7 批次三六件:§8.6-6 StrategyState 改名归位+泛型携带
# (§1 归属判据)/§5.1 effect_inventory 挂点接线(登记/节点 tick/计数 bump/
# 到期尾款返回面)/§3.2.19 免战牌 EffectSpec 条目+跳过递减/§3.4.1-4 节点屏
# 刷新计数组写端/§8.7 Snapshot 消费切换(mandate_v1 内部改读)/§5.1 账本
# 载体归一(session.effect_inventory → GameState.effects 单例)。断言全部
# 按设计语义写,与上方批次一/消费批锁面不重复。


# ============================================================ §8.6-6/§1
# StrategyState 改名归位 + 下沉策略实现层 + 泛型携带


def test_strategy_state_renamed_alias_is_same_object() -> None:
    """§8.6-6(批次三已落):类名改名归位为目标名 StrategyState;历史名
    MandateState = 同对象别名(isinstance/is X 全兼容,零行为差)。"""
    assert StrategyState is MandateState
    sess = StrategySession()
    assert state_of(sess) is sess.strategy_state
    assert isinstance(state_of(sess), StrategyState)
    assert isinstance(state_of(sess), MandateState), '别名 isinstance 兼容'


def test_framework_layer_does_not_import_concrete_state() -> None:
    """§1 归属判据(硬约束):框架层(kernel 桶 + one_dragon 框架包)不得
    import StrategyState 具体类型——泛型约束的静态锁。策略实现层
    (strategies/)与 app 桶按布局矩阵各自合法,不在本锁辖域。"""
    banned = re.compile(
        r'^\s*(?:from|import)\s+\S*(?:strategies\.impl\.mandate_v1'
        r'|mandate_state)\b', re.M)
    offenders: list[str] = []
    for f in sorted((_PKG / 'kernel').rglob('*.py')):
        if banned.search(f.read_text(encoding='utf-8')):
            offenders.append(str(f.relative_to(_PKG)))
    assert not offenders, f'kernel 桶 import 策略实现层具体状态:{offenders}'
    od_dir = _REPO / 'src' / 'one_dragon'
    cw_ref = re.compile(r'currency_war')
    od_offenders = [str(f.relative_to(_REPO / 'src'))
                    for f in sorted(od_dir.rglob('*.py'))
                    if cw_ref.search(f.read_text(encoding='utf-8',
                                                 errors='ignore'))]
    assert not od_offenders, f'one_dragon 框架包引用 CW 业务面:{od_offenders}'


def test_base_class_carries_state_only_generically() -> None:
    """§8.5/§1:策略器基类仅以泛型参数携带状态——``create_state`` 返回
    注解 = TypeVar(``_TState``) 而非具体类型;基类模块零 StrategyState
    import;具体绑定发生在策略实现层(CwFlowStrategy)。"""
    sig = inspect.signature(CwStrategy.create_state)
    assert '_TState' in str(sig.return_annotation), \
        '基类 create_state 返回注解必须是泛型参数,禁具体状态类型'
    src = inspect.getsource(CwStrategy)
    assert not re.search(r'(?:from|import)\s+\S*mandate_state', src) \
        and not re.search(r'(?:from|import)\s+\S*MandateState\b', src) \
        and not re.search(r'(?:from|import)\s+\S*StrategyState\b', src), \
        '基类零 import 具体状态类型(§1 框架不感知;docstring 提及不算)'

    from sr_od.application.currency_war.strategies.impl.flow import (
        CwFlowStrategy,
    )
    bases = getattr(CwFlowStrategy, '__orig_bases__', ())
    assert any(getattr(b, '__origin__', None) is CwStrategy for b in bases), \
        '泛型绑定必须在策略实现层的类声明上(CwStrategy[StrategyState])'


# ============================================================ §5.1 载体归一
# session.effect_inventory → GameState.effects 单例


def test_effect_inventory_is_board_state_ledger_read_through() -> None:
    """§5.1/§8.4 载体归一(批次三):账本单一实例 = GameState.effects;
    ``session.effect_inventory`` 是只读透传属性(历史写点读点零改动兼容),
    字段本体已从 session 移除——双账本漂移面消除。"""
    assert 'effect_inventory' not in {
        f.name for f in dataclasses.fields(StrategySession)}, \
        'session 不得再持有独立账本实例(双账本禁)'
    sess = StrategySession()
    inv = sess.effect_inventory
    assert inv is board_state_of(sess).effects, '透传属性指向 GameState 正本'
    with pytest.raises(AttributeError):
        sess.effect_inventory = ActiveEffectInventory(), '无 setter:禁直挂实例'


def test_level_up_hook_writes_unified_ledger() -> None:
    """升级标记挂点(prep_actions 既有)经归一后写 GameState 正本:
    session.effect_inventory.on_level_up() 与 bs.effects 事件计数同源。"""
    sess = StrategySession()
    sess.effect_inventory.on_level_up()
    assert board_state_of(sess).effects.event_count('_event_level_up') == 1, \
        '归一后写点落在单一实例(经属性写透)'


def test_battle_end_hook_writes_unified_ledger() -> None:
    """结算挂点(on_battle_end,§5.1 挂点清单第六挂点)经归一读口写
    GameState 正本:session.effect_inventory.on_battle_end() 与 bs.effects
    事件计数同源(镜像升级标记锁);挂点零 Field 写入(write_seq 不变——
    账本事件面在 inventory 方法域,不与观察覆盖争 frozen 帧域);注册表
    现役零 BATTLE_END 条目 → 挂点推进零效果条目触碰(effect-domain §7.4
    零条目 = 零驱动)。"""
    sess = StrategySession()
    bs = board_state_of(sess)
    seq0 = bs.write_seq
    sess.effect_inventory.on_battle_end()
    assert bs.effects.event_count('_event_battle_end') == 1, \
        '归一后写点落在单一实例(经属性写透)'
    assert bs.write_seq == seq0, \
        '挂点零 Field 写入(事件面与观察覆盖互不冲突)'
    assert bs.effects.entries == [], \
        '零 BATTLE_END 条目现役 = 零效果条目推进(零条目 = 零驱动)'


# ============================================================ §5.1 挂点机制
# register 播种 / tick 去重与到期 / consume_use / bump_key


def test_register_seeds_remaining_uses_and_nodes() -> None:
    """§3.2.19/§5.1:登记播种双轨——次数类(duration_uses>0)播
    remaining_uses(免战牌=2),N_NODES 播 remaining_nodes(躺平=3)。"""
    inv = ActiveEffectInventory()
    e_skip = inv.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_t=5)
    assert e_skip.remaining_uses == 2 and e_skip.remaining_nodes is None
    e_lie = inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_t=5)
    assert e_lie.remaining_nodes == 3 and e_lie.remaining_uses is None


def test_tick_node_dedup_and_acquired_guard_and_expiry() -> None:
    """§5.1 节点 tick:同节点去重(每备战环采样只推进一次)/登记当节点
    不推进(「持续 N 个节点」= 登记节点的后继 N 节点,实采定谳前保守读)/
    归零移除并返回到期条目(尾款触发面)。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_t=5)
    assert inv.tick_node(5) == [], '登记当节点不推进(吞节点即错口径)'
    assert inv.tick_node(5) == [], '同节点去重:幂等'
    assert inv.first('102001').remaining_nodes == 3
    assert inv.tick_node(6) == [] and inv.first('102001').remaining_nodes == 2
    assert inv.tick_node(6) == [], '同节点去重'
    inv.tick_node(7)
    expired = inv.tick_node(8)
    assert [e.spec.id for e in expired] == ['102001'], '归零移除+到期返回'
    assert inv.first('102001') is None
    assert inv.tick_node(8) == [], '空清单 tick 幂等'


def test_tick_node_without_ordinal_is_legacy_unconditional() -> None:
    """无 node_ordinal(旧签名)→ 无条件推进(测试/sim 直调兼容面)。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_t=5)
    inv.tick_node()
    assert inv.first('102001').remaining_nodes == 2


def test_advance_node_reports_advanced_flag() -> None:
    """B1 桥闸门:advance_node 返回 (advanced, expired)——同节点重复推进
    advanced=False(余额累加闸 = 每节点恰一次);tick_node 兼容口语义不变。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_t=5)
    advanced, expired = inv.advance_node(6)
    assert advanced is True and expired == []
    advanced2, _ = inv.advance_node(6)
    assert advanced2 is False, '同节点去重位 = 余额累加闸门'
    inv.advance_node(7)
    advanced3, expired3 = inv.advance_node(8)
    assert advanced3 is True and [e.spec.id for e in expired3] == ['102001'], \
        '三次有效推进(6/7/8)后到期移除'


# ============================================================ B1 账本→字段桥
# §5.1/§3.3.5-6/§3.2.5:burst(登记一次性)/per_node(每节点)/容量投影三形态


def test_burst_grant_adds_free_refresh_balance_once() -> None:
    """桥·burst:登记时点把 payload.free_refresh_burst 一次性累加进余额
    (固定理财即时段=2 活载体);零额度 payload(免战牌)= no-op。「一次性」
    由调用点唯一性承载(登记挂点,接线锁辖),函数本体不加去重。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    apply_effect_burst_grant(bs, STRATEGY_EFFECTS['固定理财'], frame='p1-r2')
    assert bs.free_refresh_balance.value == 2
    assert bs.free_refresh_balance.evidence == 'effect_burst@p1-r2'
    apply_effect_burst_grant(bs, STRATEGY_EFFECTS['免战牌'])
    assert bs.free_refresh_balance.value == 2, '零额度 = no-op'


def test_per_node_grant_adds_once_per_node() -> None:
    """桥·per_node:节点边界一次,把在场条目声明的每节点额度累加
    (双手狸 free_refresh_on_node_enter=2 活载体);同节点重复挂点采样不
    双计(闸 = advance_node advanced 位)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                 acquired_t=5)
    adv, _ex = bs.effects.advance_node(6)
    if adv:
        grant_effect_node_refresh_balance(bs, frame='p1-r6')
    assert bs.free_refresh_balance.value == 2
    # 同节点重复采样(挂点每备战环一次):去重位关闭累加
    adv2, _ex2 = bs.effects.advance_node(6)
    if adv2:
        grant_effect_node_refresh_balance(bs, frame='p1-r6')
    assert bs.free_refresh_balance.value == 2, '同节点禁双计'
    adv3, _ex3 = bs.effects.advance_node(7)
    if adv3:
        grant_effect_node_refresh_balance(bs, frame='p1-r7')
    assert bs.free_refresh_balance.value == 4, '下一节点再 +2'


def test_capacity_projection_activates_and_recovers() -> None:
    """桥·容量投影(§3.2.5):在册容量声明 payload.capacity_limit=3 → bench
    容量投影 3;条目到期移除 → 回默认 9;bench 未观察(None)= 无容器跳过;
    零声明条目 → 恒默认 9(幂等,当前注册表活载体为零,行为与接线前
    逐位一致)。声明契约 = payload 鸭子属性 capacity_limit(注册表建模批
    候选,§5.2 缺口;测试以鸭子桩承载声明,机制先于数据)。"""
    from types import SimpleNamespace as _NS

    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        DurationKind,
        DutyFlags,
        EffectKind,
        EffectSpec,
        TriggerKind,
    )

    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    # bench 未观察:无容器可写,投影跳过
    inv = bs.effects
    inv.register_strategy(EffectSpec(
        id='test_cap', name='容量测试桩', trigger=TriggerKind.CONDITIONAL,
        duration=DurationKind.N_NODES, category=EffectKind.ECONOMY,
        payload=_NS(capacity_limit=3), duties=DutyFlags(track=True),
        duration_nodes=2), acquired_t=5)
    project_effect_capacity(bs)
    assert bs.bench.value is None, 'bench 未观察 = 无容器,不造帧'
    # 观察(默认容量 9)→ 投影 3
    slots = [BenchSlot(kind='unit')] + [BenchSlot(kind='empty')] * 8
    bs.observe(bs.bench, BenchView(slots=slots, capacity=BENCH_CAPACITY_DEFAULT), sig=_sig())
    project_effect_capacity(bs)
    assert bs.bench.value.capacity == 3, '激活期容量 = 声明值'
    assert bs.bench.value.slots[0].kind == 'unit', '槽位表原样保留'
    assert bs.bench.source == 'logic' \
        and bs.bench.evidence == 'capacity_project'
    # 条目到期(N_NODES=2,两次推进)→ 移除后投影回默认 9
    inv.advance_node(6)
    inv.advance_node(7)
    project_effect_capacity(bs)
    assert bs.bench.value.capacity == BENCH_CAPACITY_DEFAULT == 9, \
        '到期自动回 9(§3.2.5)'


def test_consume_use_decrements_removes_and_tolerates_missing() -> None:
    """§3.2.19 跳过递减:落地一次 −1;归零移除;无在册条目返 None 零动作
    (递减挂点与登记挂点解耦,不炸执行链)。"""
    inv = ActiveEffectInventory()
    assert inv.consume_use('151301') is None, '未登记 = None 零动作'
    inv.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_t=3)
    assert inv.consume_use('151301') == 1
    assert inv.first('151301') is not None, '尚有余量不移除'
    assert inv.consume_use('151301') == 0
    assert inv.first('151301') is None, '用尽 = 效果离场'
    assert inv.consume_use('151301') is None


def test_bump_key_advances_only_tracked_entries() -> None:
    """§5.1 计数 bump:动作侧全量推进只辖 duties.track=True 条目(「谁要
    记账」的声明单一源);消费按 (spec_id, key) 隔离读。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['采购专员·金'], acquired_t=1)  # track=True
    inv.register_strategy(STRATEGY_EFFECTS['人力重组'], acquired_t=1)     # predict only
    inv.bump_key(CounterKey.REFRESH)
    inv.bump_key(CounterKey.REFRESH)
    assert inv.counter('201201', CounterKey.REFRESH) == 2
    assert inv.counter('102801', CounterKey.REFRESH) == 0, \
        '未声明记账义务的条目不被推进'


def test_skip_battle_spec_entry_matches_base_registry() -> None:
    """§8.7 批次三件 5(建模批件):免战牌 EffectSpec 条目 = id 与 base
    注册表双匹配(构建校验之外显式锁语义),次数种子 2,即时经验 30。"""
    spec = STRATEGY_EFFECTS['免战牌']
    assert spec.id == '151301'
    assert INVESTMENT_STRATEGIES['免战牌'].source == 'plaza:151301'
    assert spec.duration_uses == 2
    assert spec.payload.xp_instant == 30, \
        '+30 经验 = 选牌当场即时经验(§4 投资选择通用通道词表)'


# ============================================================ §3.4.1-4/§8.7
# 节点屏刷新计数组写端 + 挂点接线存在性(inspect 烟雾,README 第 8 条容忍档;
# 行为面已由上方函数级锁覆盖,op 装配面不重建重 harness)


def test_refresh_ledger_write_sites_wired() -> None:
    """件 6 写端接线存在性:遭遇屏(+1 置位,refresh_click)/策略屏
    (逐卡键=normalize_invest_name 规范名)/环境屏无执行链不接线
    (ADR-0600 环境侧未启用,零写端禁按值决策口径继续辖)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_encounter,
        cw_screen_invest_env,
        cw_screen_invest_strategy,
    )
    enc_src = inspect.getsource(cw_screen_encounter)
    assert 'encounter_refresh_used' in enc_src \
        and 'refresh_click' in enc_src, '遭遇屏刷计数写端在位'
    strat_src = inspect.getsource(cw_screen_invest_strategy)
    assert 'strategy_refresh_used' in strat_src \
        and 'normalize_invest_name' in strat_src, \
        '策略屏逐卡刷计数写端在位(键=规范卡名)'
    env_src = inspect.getsource(cw_screen_invest_env)
    assert 'env_refresh_used' not in env_src, \
        '环境屏刷新执行链未启用,无点击即无写端(禁观察镜像混入点击置位口径)'


def test_effect_hooks_wired_at_production_sites() -> None:
    """§5.1 挂点接线存在性:选卡登记(register_strategy)/执行落地门
    bump(REFRESH+BUY)/节点 tick(advance_node)/跳过递减(consume_use)
    四挂点 + B1 桥两采样点(burst 登记后/per_node+容量投影 tick 后)在
    生产调用面在位。"""
    from sr_od.application.currency_war import prep_actions
    from sr_od.application.currency_war.operations import cw_loop as cw_loop_mod
    from sr_od.application.currency_war.operations.cw_op import cw_op_buy_cards
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_invest_strategy,
    )
    strat_src = inspect.getsource(cw_screen_invest_strategy)
    assert 'register_strategy' in strat_src, '选卡登记挂点在位'
    assert 'apply_effect_burst_grant' in strat_src, \
        'B1 burst 桥采样点(登记后)在位'
    buy_src = inspect.getsource(cw_op_buy_cards)
    assert 'bump_key' in buy_src \
        and 'CounterKey.REFRESH' in buy_src \
        and 'CounterKey.BUY' in buy_src, '执行落地门计数 bump 在位'
    loop_src = inspect.getsource(cw_loop_mod)
    assert 'effects.advance_node' in loop_src, '节点 tick 挂点在位'
    assert 'grant_effect_node_refresh_balance' in loop_src, \
        'B1 per_node 桥采样点(tick 后)在位'
    assert 'project_effect_capacity' in loop_src, \
        'B1 容量投影采样点(备战帧观察后重锚)在位'
    prep_src = inspect.getsource(prep_actions)
    assert 'consume_use' in prep_src and '按钮-跳过' in prep_src, \
        '免战牌跳过递减挂点在位'


# ============================================================ 第 15 轮对抗审 C8
# sim 合成口 payload 离屏分支(§2.2 例外:真值缺席 = 结构离屏,禁旧 payload 残留)


def test_synthesis_payload_offscreen_branch() -> None:
    """C8:合成口 shop 真值缺席 = 结构离屏(置 None+left_screen,等价
    leave_screen)——禁旧 shop payload 连旧 evidence 残留(把「不在商店」帧
    误读成「商店仍开着」);encounter/supply 两域 sim 不建模,合成帧恒
    离屏口径;牌面在场帧照常观察落 payload。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    st_shop = CwWorkFrame()
    st_shop.shop = [StateShopCard(x=1, name='花火', cost=2, star=1,
                                  cost_source='badge')]
    synthesize_from_game_state(bs, st_shop, at_round='p1-r2')
    assert bs.shop.value is not None and bs.shop.value.cards[0].name == '花火'

    # 连续合成帧:真值缺席 → 离屏(旧 payload 不残留)
    st_prep = CwWorkFrame()
    synthesize_from_game_state(bs, st_prep, at_round='p1-r3')
    assert bs.shop.value is None, '离屏帧 payload 置 None(禁残留)'
    assert bs.shop.source == 'observation' \
        and bs.shop.evidence == 'left_screen', '结构离屏 = left_screen 标记'
    assert bs.encounter.value is None \
        and bs.encounter.evidence == 'left_screen'
    assert bs.supply.value is None and bs.supply.evidence == 'left_screen'


# ============================================================ §8.7 件 3
# Snapshot 消费切换:mandate_v1 内部改读 GameState 视图


def _bs_with_node(sess) -> None:
    bs = board_state_of(sess)
    bs.observe(bs.node, NodeKey(plane=2, round_num=5, kind='battle'), sig=_sig())


def test_snapshot_assembly_falls_back_to_board_state_view() -> None:
    """件 3:snapshot_from_obs 的 session 回退锚改读 GameState 视图——
    obs.state 缺席帧,plane/round 取记录值(与旧 last_state 直读在常态帧
    逐位一致;失读帧取 carried 沿用值 = 记录模型申报面)。"""
    from sr_od.application.currency_war.decision_assembly import snapshot_from_obs

    sess = StrategySession()
    _bs_with_node(sess)
    obs = SimpleNamespace(
        state=None, state_gold_trusted=False, bench_chars=[], deployed_chars=[],
        spheres=[], boxes=[], tomes=[], deploy_vacancy=0, free_bench_slots=None,
        front_occupied=set(), back_occupied=set(), front_size=4,
        shop_open=False, box_overlay_open=False, event_overlay=None,
    )
    snap = snapshot_from_obs(obs, sess)
    assert (snap.plane, snap.round_num) == (2, 5), \
        '回退锚 = GameState 记录值(非 last_state 原帧)'


def test_snapshot_anchor_state_falls_back_to_board_state_view() -> None:
    """件 3 收口墓碑(原锁:adapter._anchor_state 的 session 锚回退取
    GameState 记录值)——该缝已随 T-116 段 2 退役删除(snapshot_from_obs
    纯容器锚),符号复活即红;锚语义守护归 test_cw_w5_sim_retirement
    哨兵与容器锚现役锁。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        adapter as _adapter,
    )
    assert not hasattr(_adapter, '_anchor_state'), \
        'adapter._anchor_state 应已删除(T-116 段 2 缝收敛)'


# ============================================================ §8.7 批次四
# 退役 + relay 空值闸(原独立批次文件按主题文件纪律归并入本文件;断言体
# 零语义改动)。锁面 = §8.7 批次四:
# - relay 会话侧值已确立闸(§2.1:会话载体默认空值 ''/[] 是「未知」非
#   「已知事实」,禁中继成正式值;字符串非空/列表非空才中继)——单元锁 +
#   恢复局场景端到端锁(新 session 空默认不落 GameState、真值后到可落);
#   端到端两锁复用上方观察流域的 _feed_ctx/_patch_clean_readers(镜像字段
#   中继走 feed 尾部公共段,reader 读值与本组断言面无关);
# - 退役载体零残留(AST 级静态锁,标识符面):已退役符号全仓零命中 +
#   记录面(kernel/cw_game_state.py)零 last_state 标识符命中。
# payload 域三域口径的对齐断言在本文件上方(test_leave_screen_payload_only
# 负断言辖 settlement),本节不重复。

#: §2.1 五镜像字段(批次二 feed 中继点;恢复局新 session 停在空默认的面)。
_MIRROR_FIELDS = ('active_strategies', 'active_env', 'plane_bosses',
                  'enemy_affixes', 'selected_difficulty')


# ============================================================ §2.1 relay 空值闸


def test_relay_rejects_session_empty_defaults() -> None:
    """§2.1 空值=未知态禁中继:字符串空/空白、列表/元组/字典/集合空 = 会话
    侧值未确立,一律拒写(返回 False,字段保持从未写过)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    assert bs.relay(bs.active_env, '', sig=_hsig()) is False
    assert bs.relay(bs.selected_difficulty, '   ', sig=_hsig()) is False, \
        '空白字符串 = 无内容读数,同空域'
    assert bs.relay(bs.active_strategies, [], sig=_hsig()) is False
    assert bs.relay(bs.plane_bosses, (), sig=_hsig()) is False
    assert bs.relay(bs.enemy_affixes, {}, sig=_hsig()) is False
    for name in _MIRROR_FIELDS:
        fld = getattr(bs, name)
        assert fld.value is None, f'空默认禁落 GameState:{name}'
        assert fld.evidence is None, '拒写不留任何来源痕迹'


def test_relay_empty_refusal_does_not_block_late_truth() -> None:
    """恢复局核心语义:空默认被拒后字段仍是「从未写过」——真值后到可正常
    落(source=logic + evidence=session_carrier,§2.1 中继形态);「持卡名单
    [] 为假事实、拦截后到真值」的缺陷面由本锁钉死。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    assert bs.relay(bs.active_strategies, [], sig=_hsig()) is False
    assert bs.relay(bs.active_env, '', sig=_hsig()) is False
    assert bs.relay(bs.active_strategies, ['白银投资'], sig=_hsig()) is True
    assert bs.active_strategies.value == ['白银投资']
    assert bs.active_strategies.source == 'logic'
    assert bs.active_strategies.evidence == 'session_carrier'
    assert bs.relay(bs.active_env, '昼之半神概念股', sig=_hsig()) is True
    assert bs.active_env.value == '昼之半神概念股'
    assert bs.active_env.evidence == 'session_carrier'


def test_relay_gate_scope_is_empty_string_and_containers_only() -> None:
    """闸辖域 = 空字符串与空容器(§2.1 词面:字符串非空/列表非空);falsy 但
    有语义的标量(如 streak=0 真 0)不受闸辖,禁过度收紧。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    assert bs.relay(bs.streak, 0, sig=_hsig()) is True
    assert bs.streak.value == 0 and bs.streak.source == 'logic'
    assert bs.relay(bs.plane_bosses, [None, None, None], sig=_hsig()) is True, \
        '非空列表即确立(结构已知,元素 None = 该位面无身份,§8.4)'


# ============================================================ 恢复局场景端到端


def test_restore_session_empty_mirrors_not_relayed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """§2.1 恢复局场景(端到端):恢复局新 session 五镜像字段停会话默认
    (''/[])→ 生产 feed(read_game_state 观察流)逐帧中继全被空值闸拒,
    GameState 五字段保持 None(未知态不固化成正式值)。"""
    from sr_od.application.currency_war.obs import cw_observation

    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    _patch_clean_readers(monkeypatch)

    cw_observation.read_game_state(_feed_ctx(sess), None, phase='prep_clean')

    bs = board_state_of(sess)
    for name in _MIRROR_FIELDS:
        fld = getattr(bs, name)
        assert fld.value is None, f'恢复局空默认禁中继落记录:{name}'


def test_restore_session_late_truth_relay_lands(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """§2.1 恢复局场景(端到端续):真值后到(session 侧被接管协议/事件屏
    handler 写入)→ 下一帧中继正常落五镜像(source=logic + evidence=
    session_carrier)——空默认拒写不拦截后到真值。"""
    from sr_od.application.currency_war.obs import cw_observation

    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    _patch_clean_readers(monkeypatch)
    ctx = _feed_ctx(sess)

    cw_observation.read_game_state(ctx, None, phase='prep_clean')

    # 真值后到(恢复局:简报/事件屏/难度确认屏写端补齐会话侧事实)
    sess.active_strategies = ['白银投资']
    sess.active_env = '昼之半神概念股'
    sess.briefing_bosses = ['首领甲', None, None]
    sess.briefing_affixes = ['正当防卫']
    sess.selected_difficulty = 'A8'
    cw_observation.read_game_state(ctx, None, phase='prep_clean')

    bs = board_state_of(sess)
    assert bs.active_strategies.value == ['白银投资']
    assert bs.active_env.value == '昼之半神概念股'
    assert bs.plane_bosses.value == ['首领甲', None, None]
    assert bs.enemy_affixes.value == ['正当防卫']
    assert bs.selected_difficulty.value == 'A8'
    for name in _MIRROR_FIELDS:
        fld = getattr(bs, name)
        assert fld.source == 'logic', f'中继形态 logic(§2.1):{name}'
        assert fld.evidence == 'session_carrier', f'中继注记:{name}'


# ============================================================ AST 级静态锁(退役零残留)

#: 已退役符号(载体已删,防复活):免战牌平行 Field(批次二载体归一,§8.6-3)
#: 与席满警告位字段(§3.2.5 通道退役,载体随退役批删除)。
_RETIRED_SYMBOLS = ('skip_battle_active', 'skip_battle_remaining',
                    'bench_full_flag')


def _identifiers(path: Path) -> set[str]:
    """AST 标识符集(Name/Attribute/关键字形参)——docstring/注释/字典键
    字符串不属标识符,天然不在断言面(遥测行 'bench_full_flag' 键不受辖)。"""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.keyword) and node.arg:
            out.add(node.arg)
    return out


def test_ast_retired_symbols_zero_hits_repo_wide() -> None:
    """§8.7 批次四静态锁:已退役符号在 CW 包全仓零标识符命中(定义/引用/
    关键字实参皆算)——字段本体删除后的防复活锁(比字段存在性负锁更广:
    连「重新引用已删名」的代码也拦)。"""
    offenders: list[str] = []
    for f in sorted(_PKG.rglob('*.py')):
        hit = sorted(set(_RETIRED_SYMBOLS) & _identifiers(f))
        if hit:
            offenders.append(f'{f.relative_to(_PKG)}: {hit}')
    assert not offenders, f'已退役符号标识符复活:{offenders}'


def test_ast_record_layer_reads_no_last_state() -> None:
    """§8.7 批次四静态锁(记录面):kernel/cw_game_state.py 零 last_state
    标识符命中——记录模型只由观察流/写入 API/sim 合成口供数(§2.4),
    禁读 session.last_state 旧观察帧(帧新鲜度差域的独立性与记录/消费
    分离的结构前提)。

    **锁面边界申报**:「last_state 全仓 0 命中」= 迁移尾批完成态断言——
    执行侧装配源切换 ~18 点(ADR-0530,设计 §8.7 尾批行)在产消费
    last_state,尾批完成后把本断言面从记录面扩到全仓;现写全仓零命中
    断言 = 永久红锁,不做。
    """
    ids = _identifiers(_PKG / 'kernel' / 'cw_game_state.py')
    assert 'last_state' not in ids, \
        '记录面(kernel/cw_game_state.py)不得引用 last_state 旧帧'
