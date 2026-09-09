# -*- coding: utf-8 -*-
"""BoardState 迁移回归锁(迁移批次一;设计正本 = docs/develop/currency_war/
design/BoardState-数据结构设计.md,下称「设计」)。

锁面 = 设计 §8.6 差距清单逐条(草板旧契约禁复发的负锁)+ §3 字段语义抽样
+ 心跳不断流(§2.4 关键结构 2)+ sim 合成口箱占席语义(§3.2.5;迁移批次一
任务书第 7 件)。断言全部按设计语义写,禁按 level 驱动表/线性外推写
(设计 §3.2.7 回归测试断言约束)。

草板对照物 = .debug/temp/currency_war/record_data_model/board_state.py
(易失产物,不构成出处;出处 = 设计章节号)。
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_board_state import (
    BENCH_CAPACITY_DEFAULT,
    BS_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    BoardState,
    Field,
    NodeKey,
    Unit,
    bench_free_slots,
    bench_is_full,
    board_state_of,
    consume_defect_sink,
    note_board_state_heartbeat,
    set_defect_sink,
    slot_occupies,
    synthesize_from_game_state,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_state import (
    ShopCard as StateShopCard,
)


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
        BoardState()  # type: ignore[call-arg]


# ============================================================ §8.6-2/§2.4
# 三个关键结构:预期条目表 / 帧观察完整度标注+心跳 / bs_schema


def test_expected_entry_table_five_keys_and_last_wins() -> None:
    """§2.4 关键结构 1:预期条目五键齐备;同字段后写覆盖前写(last-wins)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    e1 = bs.expect(bs.gold, 17, confirm_point='prep_obs',
                   group_id='', at_round='p1-r4')
    assert e1.path and e1.confirm_point == 'prep_obs'
    assert e1.at_round == 'p1-r4'
    # last-wins:同字段再 expect → 旧条目被替换,表中仍一条
    e2 = bs.expect(bs.gold, 15, confirm_point='shop_wave_top',
                   group_id='', at_round='p1-r4')
    pending = bs.pending_entries()
    assert len(pending) == 1 and pending[0] is e2


def test_expect_leaves_field_unreadable_to_strategy() -> None:
    """§2.5 两步机制:预期只进条目表,字段值暂不动——策略器读字段读不到预期。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20)
    bs.expect(bs.gold, 17)
    assert bs.gold.value == 20, '预期未核实前字段保持原值(策略器不读预期)'
    assert bs.gold.source == 'observation'


def test_confirm_writes_logic_and_keeps_logic_source() -> None:
    """§2.5/§8.1:核实通过 → 字段写入且 source=logic(保持 logic,不翻 observation)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20)
    entry = bs.expect(bs.gold, 17)
    bs.confirm(entry)
    assert bs.gold.value == 17
    assert bs.gold.source == 'logic', 'logic 值保持 logic 来源(§8.1)'
    assert not bs.pending_entries(), '确认后条目清账'


def test_confirm_rejects_wrong_confirm_point() -> None:
    """§2.4 五键②:条目只在绑定的核对点可确认转正,错点确认显式炸错。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    entry = bs.expect(bs.gold, 17, confirm_point='shop_wave_top')
    with pytest.raises(ValueError):
        bs.confirm(entry, at_point='prep_obs')


def test_confirm_group_all_or_nothing() -> None:
    """§2.4 五键③:组内条目全有全无清账,禁单字段半确认中间态。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    g = 'buy-阿格莱雅-p1-r4'
    e_gold = bs.expect(bs.gold, 17, group_id=g, confirm_point='prep_obs')
    e_bench = bs.expect(bs.bench, BenchView(), group_id=g,
                        confirm_point='prep_obs')
    bs.confirm(e_gold, at_point='prep_obs')
    assert bs.gold.value == 17
    assert not bs.pending_entries(), '组确认 = 整组清账(全有全无)'


def test_discard_expected_clears_without_write() -> None:
    """§8.4 用法块第 4 步:点击落空 → 条目清账不写字段(观察赢前清预期)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20)
    entry = bs.expect(bs.gold, 17)
    bs.discard_expected(entry)
    assert not bs.pending_entries()
    assert bs.gold.value == 20, '清账不动字段值'


def test_logic_written_fields_tracks_and_reanchors() -> None:
    """§8.4 logic_written_fields:已确认未重锚的 logic 字段名;观察覆盖后除名。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    entry = bs.expect(bs.gold, 17)
    bs.confirm(entry)
    assert bs.logic_written_fields() == ['gold']
    bs.observe(bs.gold, 19)
    assert bs.logic_written_fields() == [], '观察重锚后不再算 logic 在写'


def test_frame_obs_marker_consumed_on_read() -> None:
    """§2.4 关键结构 2:帧观察完整度标注 full/view/none,消费即清。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.mark_frame_obs('full')
    assert bs.consume_frame_obs() == 'full'
    assert bs.consume_frame_obs() == 'none', '消费即清'


def test_write_seq_is_monotonic_carrier() -> None:
    """§2.4:停更检测哨兵 = 只增不减计数(写点序号),不做帧标注现值
    (消费即清后当不了哨兵);心跳观察者断言「不断流」。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    seq0 = bs.heartbeat()
    bs.observe(bs.gold, 20)
    bs.observe(bs.gold, 21)
    bs.mark_frame_obs('full')
    assert bs.consume_frame_obs() == 'full', '消费标注不影响哨兵计数'
    seq1 = bs.heartbeat()
    assert seq1 > seq0, '写点推进 → 心跳单调递增(不断流)'
    bs.carry(bs.gold, frame='p1-r5')
    assert bs.heartbeat() > seq1, 'carried 写也是写点,哨兵照常推进'


def test_bs_schema_domain_map_present() -> None:
    """§2.4 关键结构 3:bs_schema = 域粒度版本映射(缺域键 = 该域未建模)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert isinstance(bs.bs_schema, dict) and bs.bs_schema
    assert 'node' in bs.bs_schema and 'economy' in bs.bs_schema


# ============================================================ §8.6-3
# 画面附加域与缺口域(开局初值域/十事件屏域/结算事件位/刷新计数组/持久账本组)

# 画面附加域 = kernel 三域口径(cw_board_state._PAYLOAD_DOMAINS 同源):
# shop/encounter/supply。settlement 是结算真值组(§3.5.1)非画面 payload,
# 不在附加域词表(负断言见 test_leave_screen_payload_only)。
_PAYLOAD_DOMAINS = ('shop', 'encounter', 'supply')
_CHOSEN_DOMAINS = ('chosen_encounter', 'chosen_supply', 'chosen_megastar',
                   'chosen_partner', 'chosen_wish', 'chosen_fortune',
                   'chosen_hack', 'chosen_expert', 'chosen_tome',
                   'chosen_equip')
# ~~skip_battle_active/remaining 已移出本组(迁移批次二载体归一,§8.6-3):
# 免战牌激活态+剩余次数正本 = effect_inventory.remaining_uses(§5.1),
# BoardState 不设平行 Field——负向锁见本文件下方 test_skip_battle_fields_retired。
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
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert isinstance(getattr(bs, name), Field), f'缺域:{name}'


def test_skip_battle_fields_retired() -> None:
    """§8.6-3 载体归一(迁移批次二):免战牌激活态+剩余次数正本 =
    effect_inventory.remaining_uses(ActiveEffect.remaining_uses「次数类
    余量(免战牌×2 等)」,§5.1 同型躺平/节省工位)——BoardState 平行
    Field 按正本归一移除(改锁依据:设计正本明文,非机械跟绿)。"""
    field_names = {f.name for f in dataclasses.fields(BoardState)}
    for banned in ('skip_battle_active', 'skip_battle_remaining'):
        assert banned not in field_names, f'免战牌平行 Field 应已归一移除:{banned}'


def test_gap3_node_screen_refresh_schema_domain() -> None:
    """P1-2:节点屏刷新计数组有 bs_schema 域键(缺域键 = 该域未建模,§3.7.1);
    逐卡计数形状 = 卡名 → 已用次数(§3.4.4)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert bs.bs_schema.get('node_screen_refresh') == 1
    bs.observe(bs.strategy_refresh_used, {'白银投资': 1})
    assert bs.strategy_refresh_used.value == {'白银投资': 1}


def test_gap4_missing_fields_present() -> None:
    """§8.6-4:board/level_up_cost/back_layout/spheres/分类子态/对局类型/
    节点序列台账/hp 保底事件位在场;bench 容量默认恒 9(§3.2.5)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
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
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.game_mode, '标准')
    assert bs.game_mode.value == '标准'


def test_node_path_ledger_is_type_sequence() -> None:
    """§3.2.2:节点序列台账 = 本局节点**类型序**台账(权威写端=备战帧
    node_path 现读;内容主题替换族不改类型序,台账不受影响)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.node_path, ['battle', 'encounter', 'reward', 'boss'])
    assert bs.node_path.value == ['battle', 'encounter', 'reward', 'boss']


def test_prep_substate_four_values() -> None:
    """§3.2.17:分类子态四档(三暗色锁定 + 恢复锁定);恢复锁定=会话推断档
    无帧识别锚,写端=接管协议(§6.3),禁按帧子态统一路由。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    for v in ('策略锁定', '遭遇锁定', '补给锁定', '恢复锁定'):
        bs.observe(bs.prep_substate, v)
        assert bs.prep_substate.value == v


def test_hp_floor_event_is_pure_observation_registry() -> None:
    """§3.5.3:hp 保底触发事件位 = 纯观察登记、无判据载体(消费端按不确定降级)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert bs.hp_floor_triggered.value is None
    bs.observe(bs.hp_floor_triggered, True)
    assert bs.hp_floor_triggered.value is True


# ============================================================ §8.6-4(续)
# 派生不存储:席空数/席满判定/board 下档阈值 = 计算函数,禁入 schema


def test_derived_quantities_not_stored() -> None:
    """§8.6-4:派生量禁入 schema(board_next_tier/席空数/席满判定;
    bench_full_flag 警告位已裁撤不建,§3.2.5)。"""
    field_names = {f.name for f in dataclasses.fields(BoardState)}
    for banned in ('board_next_tier', 'free_bench_slots', 'bench_full_flag',
                   'bench_is_full'):
        assert banned not in field_names, f'派生量入了 schema:{banned}'


def test_bench_free_slots_unobserved_is_none() -> None:
    """§3.2.5:席空数没读到 = 不确定,**禁猜 0**——bench 从未观察返 None。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
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
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    slots = [BenchSlot(kind='unit'), BenchSlot(kind='supply_box'),
             BenchSlot(kind='tome')] + [BenchSlot(kind='empty')] * 6
    bs.observe(bs.bench, BenchView(slots=slots, capacity=9))
    assert bench_free_slots(bs) == 6
    assert bench_is_full(bs) is False
    full = [BenchSlot(kind='unit')] * 8 + [BenchSlot(kind='supply_box')]
    bs.observe(bs.bench, BenchView(slots=full, capacity=9))
    assert bench_is_full(bs) is True, '8 单位 + 1 箱 = 满(箱占席)'


# ============================================================ §8.6-5
# 构造守卫:frozen 帧替换 + hp 不变式 + 缺陷台账挂点


def test_field_is_frozen_frame() -> None:
    """§8.6-5:Field 冻结——写入只能经 BoardState API 换新帧,禁原地改。"""
    f = Field(value=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.value = 2  # type: ignore[misc]


def test_observe_replaces_frame_not_mutates() -> None:
    """§2.4:frozen 帧替换——旧帧引用保持旧值(持旧引用的读者不被跨时段写回污染)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    old = bs.gold
    bs.observe(bs.gold, 20)
    assert old.value is None and old.source == 'observation'
    assert bs.gold.value == 20 and bs.gold is not old


def test_observe_rejects_none_loses_are_carried_not_cleared() -> None:
    """§2.2 硬边界:observe(None) 拒绝——失读走 carried(处置①)或保持 None
    (处置②),字段一旦有过正式值任何失读不得清成 None。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    with pytest.raises(ValueError):
        bs.observe(bs.hp, None)
    bs.observe(bs.hp, 80)
    bs.carry(bs.hp, frame='p1-r5')
    assert bs.hp.value == 80, '失读帧沿用上次好值'
    assert bs.hp.source == 'carried' and bs.hp.evidence == 'carried:p1-r5'
    assert bs.hp.value is not None, '硬边界:正式值永不清成 None'


def test_carry_on_never_read_keeps_none() -> None:
    """§2.2 处置②:字段从未读过(机制性不可读态+新局)→ 保持 None
    (机制性 None 专指此态)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.carry(bs.gold, frame='p1-r1')
    assert bs.gold.value is None


def test_write_prior_requires_prior_evidence() -> None:
    """§2.1/§3.1.6:prior 写入必带 prior: 来源注记;禁扩散(仅显式申报条目)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    with pytest.raises(ValueError):
        bs.write_prior(bs.hp, 82, evidence='carried:x')
    bs.write_prior(bs.hp, 82, evidence='prior:adr-0559')
    assert bs.hp.value == 82 and bs.hp.source == 'prior'


def test_leave_screen_payload_only() -> None:
    """§2.2 显式例外:画面附加域(kernel 三域口径 shop/encounter/supply)离开
    画面置 None 是结构事实,不受 carried 硬边界辖;整局字段禁走此口,
    settlement(结算真值组,§3.5.1)非画面 payload 同样禁离屏清值。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.shop, SimpleNamespace(cards=[]))
    bs.observe(bs.encounter, SimpleNamespace(options=[]))
    bs.observe(bs.supply, SimpleNamespace(options=[]))
    bs.leave_screen(bs.shop)
    bs.leave_screen(bs.encounter)
    bs.leave_screen(bs.supply)
    assert bs.shop.value is None and bs.encounter.value is None \
        and bs.supply.value is None
    bs.observe(bs.gold, 20)
    with pytest.raises(ValueError):
        bs.leave_screen(bs.gold), '整局字段(有过正式值)禁离屏清值'
    bs.observe(bs.settlement, SimpleNamespace(hp_after=76))
    with pytest.raises(ValueError):
        bs.leave_screen(bs.settlement), 'settlement 非画面附加域,禁离屏'


def test_observe_over_logic_mismatch_emits_defect_row() -> None:
    """§2.3:观察覆盖 logic 值失配 → 失配记入缺陷台账(挂点注入,缺省关);
    观察赢——来源改回 observation。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    entry = bs.expect(bs.gold, 17)
    bs.confirm(entry)
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        bs.observe(bs.gold, 19)
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert len(rows) == 1
    assert rows[0]['field'] == 'gold'
    assert rows[0]['expected'] == 17 and rows[0]['actual'] == 19
    assert bs.gold.source == 'observation', '观察赢:来源改回 observation'


def test_observe_over_logic_match_silent() -> None:
    """§2.3:观察值与 logic 值一致 = 核实通过形态,不留缺陷行。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    entry = bs.expect(bs.gold, 17)
    bs.confirm(entry)
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        bs.observe(bs.gold, 17)
    finally:
        set_defect_sink(None)
    assert rows == []


def test_observe_does_not_touch_pending_entries() -> None:
    """§2.3:观察帧不得确认或清除未核实预期——预期只由它自己的核对点关闭。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    entry = bs.expect(bs.gold, 17)
    bs.observe(bs.gold, 19)
    assert bs.pending_entries() == [entry], '观察不清预期条目'


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
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.streak, -3)
    assert bs.streak.value == -3


def test_shop_refresh_cost_none_is_not_zero() -> None:
    """§3.3.4/ADR-0622:免费帧不写(None≠标价 0);识别失败=None 禁兜底改值
    ——失读走 carried,值保持上次读数。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert bs.shop_refresh_cost.value is None, '新局未读 = None,不是 0'
    bs.observe(bs.shop_refresh_cost, 2)
    bs.carry(bs.shop_refresh_cost, frame='shop-free-frame')
    assert bs.shop_refresh_cost.value == 2
    assert bs.shop_refresh_cost.value != 0


def test_event_overlay_none_vs_not_read_distinct() -> None:
    """§3.6.1:'none'=确认无浮层(显式枚举值);None=这一帧没读到。两者分写。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert bs.event_overlay.value is None, '未读到'
    bs.observe(bs.event_overlay, 'none')
    assert bs.event_overlay.value == 'none', '确认无浮层'


def test_back_layout_writes_real_slot_count_with_superset_mark() -> None:
    """§3.2.7:布局档写真实槽位数;域外按 8 格超集读全扩展带,evidence 补
    superset 标记(防超集近似被当精确值消费)。断言不按 level 驱动表写。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.back_layout, 7)
    assert bs.back_layout.value == 7
    bs.observe(bs.back_layout, 8, evidence='superset')
    assert bs.back_layout.value == 8 and bs.back_layout.evidence == 'superset'


# ============================================================ 单例宿主与心跳观察者


def test_board_state_of_binds_per_session() -> None:
    """§1:单例,每局新建——session 对象 = 局身份,新 session = 新 BoardState。"""
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
    bs.observe(bs.gold, 20)            # 有推进
    note_board_state_heartbeat(sess)
    assert bs.hb_stall_count == 0, '推进即复位'


# ============================================================ §3.2.5(任务书件 7)
# sim 合成口:记录模型按实机真值箱占席;sim 真值合成 evidence 恒 sim:synthesized


def test_sim_synthesis_preserves_bench_slots() -> None:
    """§2.1/§3.2.5:sim 真值合成 bench 槽位保序(0 基下标 → 1 基物理槽位),
    记录模型不采 sim「箱不占席」内部口径。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    # 经构造器传入(__post_init__ pad 到定长 9,ADR-0316 形状契约;直赋值
    # 绕过 pad 是旧紧缩构造兼容域,合成口输出侧补齐见模块实现)。
    st = GameState(bench=[
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
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    st = GameState()   # hp=None(未观测态);gold 默认 0 且 readable=True(P2-3 实断言依据)
    synthesize_from_game_state(bs, st, at_round='p1-r1')
    assert bs.hp.value is None
    assert bs.node.value is None, \
        'node_type 未建模(裸构造 None)不合成 kind 占位(P1-1 同型泛化)'
    assert bs.gold.value == 0 \
        and bs.gold.evidence == 'sim:synthesized@p1-r1', \
        'gold 真值(缺省 0,readable)合成 observation;at_round 并入 evidence(P2-6)'


def test_sim_engine_feeds_board_state() -> None:
    """任务书件 7:engine_p1 决策帧合成段接线——sim 引擎跑一局,session 的
    BoardState 被喂入(心跳推进 + bench 观察 sim:synthesized)。"""
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
    """任务书件 2:read_game_state 观察流接线——真读字段进 BoardState
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
        'BoardState 从未读过 → 处置②保持 None(session 暖启动值不入,禁猜)'

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
    bs.observe(bs.node, NodeKey(plane=1, round_num=8, kind='boss'))
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
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    st = GameState()
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
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    entry = bs.expect(bs.gold, 17)
    bs.confirm(entry)
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        bs.observe(bs.gold, 18)
    finally:
        drained = consume_defect_sink()
    assert len(rows) == 1 and drained == rows
    assert consume_defect_sink() == []
