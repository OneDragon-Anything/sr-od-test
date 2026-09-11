"""装备改写成员写端落码主题锁(EQUIP_WRITE_SIDES 登记面 + 装备改写写端桥)。

设计出处(持久索引):
- 归属判据 = BoardState 数据结构设计 §5.3(docs/develop/sr_od/application/
  currency_war/changes/2026-09-11-unified-state/details/BoardState-数据结构
  设计.md,迭代期详设;持久正本 = docs/develop/currency_war/game_state/
  effect-domain.md §6.3 写入归属判据):确定性可算 → 逻辑写;含随机 → 零
  逻辑写端,观察收口;
- 写入归属申报单一源 = kernel/cw_affix_effects.py EQUIP_REWRITE_DECLARATIONS
  × EQUIP_WRITE_SIDES(逐件写端落码登记;键恰等与目标可解析由生产模块
  import 即炸校验单一承责,本文件不重复);
- 实现单一源 = kernel/cw_effect_inventory.py 文末「装备改写写端」段
  (写端桥/贡献算术/计数底座;窗口独占性分形判据见该段头注);
- 谓词扫描恰等锁(申报表 ↔ 装备注册表)在 test_cw_affix_spec_registry.py。

辖域 = 写端登记恰等与词表 + 落码形服务面映射 + 桥行为(获得 hp/入席/入区/
特权化)+ 贡献算术(零直写纪律)+ 负写端具名锁(随机面/真值同拍送达面)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
from sr_od.application.currency_war.kernel.cw_affix_effects import (
    EQUIP_REWRITE_DECLARATIONS,
    EQUIP_WRITE_SIDES,
    scan_rewrite_equipments,
)
from sr_od.application.currency_war.kernel.cw_board_state import (
    BS_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    BoardState,
    ChannelSig,
    Unit,
    register_sig_actors,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    DIAMOND_PHASE_STEP,
    EQUIP_PRIVILEGE_SUFFIX,
    STAFF_PROJECTOR_COST_GATE,
    TREASURE_ACQUIRE_HP,
    WEALTH_GOLD_PER_NODE,
    apply_equip_acquire_hp,
    equip_diamond_phase_gold,
    equip_node_gold_grant,
    equip_wrench_duplicate_gold,
    grant_equip_item,
    held_equip_count,
    privilege_counterpart,
    spawn_equip_bench_unit,
    transform_equip_to_privilege,
    worn_equip_count,
)

register_sig_actors('TestSigWriter')

# 同次运行只算一次(锁契约:重结果一次复用)
_EQUIP_SCAN = scan_rewrite_equipments()


def _sig() -> ChannelSig:
    """渠道①签名(obs 族;观察构造 BoardState 前置态)。"""
    return ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _char_by_cost(cost: int) -> str:
    """从角色注册表按费用取一个稳定代表名(数据在仓,断言可复现)。"""
    names = sorted(n for n, c in CHARACTERS.items() if c.cost == cost)
    assert names, f'注册表缺 cost={cost} 角色(数据面漂移,换锚并同步本注释)'
    return names[0]


def _wearing(cost: int, star: int, slot: int,
             equips: list[str]) -> Unit:
    return Unit(char_id=_char_by_cost(cost), star=star, slot=slot,
                equips=list(equips))


def _make_bs(*, front: list[Unit] | None = None,
             back: list[Unit] | None = None,
             bench: BenchView | None = None,
             equips: list[str] | None = None,
             gold: int | None = None,
             hp: int | None = None) -> BoardState:
    """构造带前置观察态的 BoardState(None = 该字段从未观察)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    if front is not None:
        bs.observe(bs.front_row, front, sig=_sig())
    if back is not None:
        bs.observe(bs.back_row, back, sig=_sig())
    if bench is not None:
        bs.observe(bs.bench, bench, sig=_sig())
    if equips is not None:
        bs.observe(bs.equips, list(equips), sig=_sig())
    if gold is not None:
        bs.observe(bs.gold, gold, sig=_sig())
    if hp is not None:
        bs.observe(bs.hp, hp, sig=_sig())
    return bs


def _bench_view(occupied: int = 0, capacity: int = 9) -> BenchView:
    """前置 N 槽已占(1★单位)、其余空槽的标准备战席。"""
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=_char_by_cost(1), star=1,
                                 slot=i + 1))
             for i in range(occupied)]
    slots += [BenchSlot(kind='empty')] * (capacity - occupied)
    return BenchView(slots=slots, capacity=capacity)


# ==================== 1. 写端登记面(恰等 + 词表 + 服务面映射) ====================


def test_write_side_registry_exact_coverage() -> None:
    """写端登记键集 == 申报表键集 == 谓词扫描命中集(三层恰等,零静默):
    登记漏件/多件即红;键恰等与目标可解析的日常守卫在生产 import 即炸
    校验,本锁把三层对齐面显式钉在测试面(防校验被删后静默失联)。"""
    assert set(EQUIP_WRITE_SIDES) == set(EQUIP_REWRITE_DECLARATIONS)
    assert set(EQUIP_WRITE_SIDES) == set(_EQUIP_SCAN)
    assert len(EQUIP_WRITE_SIDES) == 25


def test_write_side_value_vocabulary() -> None:
    """值词表封闭四形:bridge:/contribution:/op:/observation——集外值由
    生产校验即炸,本锁钉词表本身(新增形须先扩词表与分形判据再入册)。"""
    for side in EQUIP_WRITE_SIDES.values():
        assert (side == 'observation'
                or side.startswith(('bridge:', 'contribution:', 'op:'))), side


def test_write_side_service_surface_mapping() -> None:
    """落码形服务面映射(入席桥七件共享/其余桥一对一/贡献算术三件):
    服务面漂移(件换桥/桥换件)即红,防共享桥辖域静默扩缩。"""
    spawn_items = {'员工投影仪', '完美投影仪', '数据拷贝仪', '数据拷贝仪Max',
                   '数据拷贝仪Pro', '分身墨镜', '分身墨镜Max'}
    assert {n for n, s in EQUIP_WRITE_SIDES.items()
            if s == 'bridge:spawn_equip_bench_unit'} == spawn_items
    assert EQUIP_WRITE_SIDES['极·阿瓦隆'] == 'bridge:apply_equip_acquire_hp'
    assert EQUIP_WRITE_SIDES['好运令牌'] == 'bridge:grant_equip_item'
    assert (EQUIP_WRITE_SIDES['特权赋予卡']
            == 'bridge:transform_equip_to_privilege')
    assert EQUIP_WRITE_SIDES['财富'] == 'contribution:equip_node_gold_grant'
    assert (EQUIP_WRITE_SIDES['财富宝钻']
            == 'contribution:equip_diamond_phase_gold')
    assert (EQUIP_WRITE_SIDES['精密拆装扳手']
            == 'contribution:equip_wrench_duplicate_gold')
    assert EQUIP_WRITE_SIDES['拆装扳手'].startswith('op:')


def test_negative_write_sides_named() -> None:
    """负写端具名锁:随机面(冶金炉/随便骰子族/干将莫邪族随机投影)、真值
    同拍送达面(诅咒·阿瓦隆/罪孽王冠——结算屏真值已含该效果,独立直写=
    双计/部分预测刷缺陷台账)、字段缺位面(生命之环族 hp_max)、豁免面
    (诅咒·宝石剑容量)恰 11 件登记 observation——负写端集扩缩须过评审,
    合谋收缩(改词表绕锁)由值词表封闭锁拦。"""
    observation_items = {n for n, s in EQUIP_WRITE_SIDES.items()
                         if s == 'observation'}
    assert observation_items == {
        '诅咒·阿瓦隆', '罪孽王冠', '生命之环', '生命之环·特权',
        '诅咒·宝石剑泽尔里奇', '冶金炉', '干将莫邪', '极·干将莫邪',
        '诅咒·干将莫邪', '随便骰子', '随便骰子·特权',
    }
    for n in observation_items:
        assert '观察收口' in EQUIP_REWRITE_DECLARATIONS[n], n


# ==================== 2. 计数底座(贡献算术的输入面) ====================


def test_held_and_worn_count_basis() -> None:
    """持有件数 = 前排已穿 + 后排已穿 + 备战席已穿(记录内)+ 库存四源和;
    已穿件数 = 前排 + 后排(「装备者」口径,库存/备战席不计)。字段从未
    观察(None)= 该源跳过不猜。"""
    cost = _char_by_cost(1)
    bs = _make_bs(
        front=[_wearing(1, 1, 1, ['财富']), _wearing(2, 2, 2, [])],
        back=[_wearing(3, 1, 1, ['财富', '生命之环'])],
        bench=_bench_view(occupied=1),
        equips=['财富', '拆装扳手'])
    # 给备战席首位单位穿一件(构造后置:直接重建 bench 视图)
    bs.observe(bs.bench, BenchView(
        slots=[BenchSlot(kind='unit',
                         unit=_wearing(1, 1, 1, ['财富宝钻']))]
        + [BenchSlot(kind='empty')] * 8, capacity=9), sig=_sig())
    assert held_equip_count(bs, '财富') == 3      # 前1+后1+库存1
    assert worn_equip_count(bs, '财富') == 2      # 前1+后1(「装备者」口径)
    assert held_equip_count(bs, '财富宝钻') == 1  # 备战席已穿(记录内)
    assert worn_equip_count(bs, '财富宝钻') == 0
    assert held_equip_count(bs, '生命之环') == 1
    # 全字段未观察 = 零源,诚实 0(不猜)
    empty = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert held_equip_count(empty, '财富') == 0
    assert worn_equip_count(empty, '财富') == 0
    assert cost  # 稳定性锚(防 _char_by_cost 被优化掉的面)


# ==================== 3. 写端桥行为(窗口独占直写) ====================


def test_apply_equip_acquire_hp_window_exclusive_write() -> None:
    """极·阿瓦隆获得回执:hp 逻辑直写 +50(窗口独占完全预测);返回实际
    增益;来源=logic、produced_by=EffectLedgerBridge、evidence 带事件名。"""
    bs = _make_bs(hp=82)
    seq0 = bs.write_seq
    gained = apply_equip_acquire_hp(bs, frame='p1-r3')
    assert gained == TREASURE_ACQUIRE_HP == 50
    assert bs.hp.value == 132 and bs.hp.source == 'logic'
    assert bs.hp.evidence == 'equip_acquire_hp@p1-r3'
    assert bs.write_seq == seq0 + 1


def test_apply_equip_acquire_hp_skips_when_hp_unread() -> None:
    """hp 从未读(None)= 无累加基座,跳过零写入(hp 写入闸辖:不可信不写,
    禁造假基座)——与板面重写桥金面跳过同族先例。"""
    bs = _make_bs(front=[_wearing(1, 1, 1, [])])
    seq0 = bs.write_seq
    assert apply_equip_acquire_hp(bs) == 0
    assert bs.hp.value is None and bs.hp.source == 'observation'
    assert bs.write_seq == seq0, '跳过 = 零写入零占版本'


def test_spawn_equip_bench_unit_appends_to_first_empty_slot() -> None:
    """入席桥主行为:复制单位落第一个空槽,其余槽与容量原样保留;落位单位
    slot = 落位物理槽(1 基,slots[i] ↔ 槽 i+1);来源=logic、evidence 带
    事件名。"""
    bs = _make_bs(bench=_bench_view(occupied=2))
    seq0 = bs.write_seq
    char = _char_by_cost(3)
    ok = spawn_equip_bench_unit(bs, char, 1, 3, frame='tool_drag')
    assert ok is True
    assert bs.write_seq == seq0 + 1 and bs.bench.source == 'logic'
    assert bs.bench.evidence == 'equip_spawn@tool_drag'
    view = bs.bench.value
    assert view.capacity == 9 and len(view.slots) == 9
    spawned = view.slots[2]                     # 前 2 槽已占 → 落第 3 槽
    assert spawned.kind == 'unit' and spawned.unit is not None
    assert spawned.unit.char_id == char and spawned.unit.star == 1
    assert spawned.unit.slot == 3               # 1 基物理槽位
    assert view.slots[0].unit is not None and view.slots[1].unit is not None
    assert all(s.kind == 'empty' for s in view.slots[3:])


def test_spawn_equip_bench_unit_cost_gate() -> None:
    """费用门:员工投影仪门 =3(官方「3费及以下」)——超门拒落 = 游戏端
    拒拖拽语义,零写入;门内放行;无门形(完美投影仪/拷贝仪/分身墨镜)
    cost_gate=0 不设限。"""
    bs = _make_bs(bench=_bench_view())
    seq0 = bs.write_seq
    assert spawn_equip_bench_unit(bs, _char_by_cost(4), 1, 4,
                                  cost_gate=STAFF_PROJECTOR_COST_GATE) is False
    assert bs.write_seq == seq0, '超门拒落 = 零写入'
    assert spawn_equip_bench_unit(bs, _char_by_cost(3), 1, 3,
                                  cost_gate=STAFF_PROJECTOR_COST_GATE) is True
    assert spawn_equip_bench_unit(bs, _char_by_cost(5), 1, 5) is True
    assert bs.write_seq == seq0 + 2


def test_spawn_equip_bench_unit_bench_full_or_unobserved() -> None:
    """席满(无空槽,与派生席满判定同源)或 bench 从未观察 → False 零写入:
    游戏端拒落/无容器,落位真值由观察给出。"""
    full = _make_bs(bench=_bench_view(occupied=9))
    seq0 = full.write_seq
    assert spawn_equip_bench_unit(full, _char_by_cost(1), 1, 1) is False
    assert full.write_seq == seq0
    unobserved = BoardState(schema_version=BS_SCHEMA_VERSION)
    seq0 = unobserved.write_seq
    assert spawn_equip_bench_unit(unobserved, _char_by_cost(1), 1, 1) is False
    assert unobserved.write_seq == seq0


def test_spawn_equip_bench_unit_star_domain() -> None:
    """star 集 1..3 外 = 调用错显式炸错(星级未采证的单位禁走本桥,走观察
    收口——银狼LV.999 星级未采证即此边界)。"""
    bs = _make_bs(bench=_bench_view())
    with pytest.raises(ValueError):
        spawn_equip_bench_unit(bs, _char_by_cost(1), 4, 1)


def test_grant_and_transform_equips_inventory() -> None:
    """装备库存双腿:①单件入区 = 追加(原序保留);②特权化 = 仅目标名替换
    (·特权后缀映射),其余件原样;库存未观察/无此件 = 零写入。"""
    bs = _make_bs(equips=['生命之环', '拆装扳手'])
    seq0 = bs.write_seq
    assert grant_equip_item(bs, privilege_counterpart('生命之环'),
                            frame='token_pick') is True
    assert bs.equips.value == ['生命之环', '拆装扳手', '生命之环·特权']
    assert bs.equips.evidence == 'equip_grant@token_pick'
    assert bs.write_seq == seq0 + 1
    assert transform_equip_to_privilege(bs, '生命之环') == '生命之环·特权'
    assert bs.equips.value == ['生命之环·特权', '拆装扳手', '生命之环·特权']
    assert bs.equips.evidence == 'equip_transform'
    # 无此件 = 零写入(返回 None)
    seq1 = bs.write_seq
    assert transform_equip_to_privilege(bs, '不存在的进阶') is None
    assert bs.write_seq == seq1
    # 库存未观察 = 零写入(无容器)
    empty = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert grant_equip_item(empty, '生命之环') is False
    assert transform_equip_to_privilege(empty, '生命之环') is None


def test_privilege_counterpart_bijection_over_registry() -> None:
    """·特权后缀映射全量双射(注册表驱动):36 进阶 ↔ 36 特权——映射单一
    源 = EQUIP_PRIVILEGE_SUFFIX 后缀规则,注册表增删件后本锁红指向重扫。"""
    advance = {n for n, e in EQUIPMENTS.items() if e.category == '进阶'}
    privilege = {n for n, e in EQUIPMENTS.items() if e.category == '特权'}
    assert advance and privilege
    assert {privilege_counterpart(n) for n in advance} == privilege
    for n in advance:
        assert EQUIPMENTS[privilege_counterpart(n)].category == '特权'
    assert EQUIP_PRIVILEGE_SUFFIX == '·特权'


# ==================== 4. 贡献算术(零直写纪律) ====================


def test_equip_node_gold_grant_contribution() -> None:
    """财富贡献算术:+4×持有件数(已穿前后排 + 库存,持有口径——官方文无
    「装备者」限定);纯算术零直写:金值/来源/写点序不动——组合写归节点
    边界金结算载体,先落单独直写必与轮首收入同窗失配刷缺陷台账。"""
    bs = _make_bs(
        front=[_wearing(1, 1, 1, ['财富'])],
        equips=['财富'],
        gold=20)
    seq0 = bs.write_seq
    assert equip_node_gold_grant(bs) == 2 * WEALTH_GOLD_PER_NODE == 8
    assert bs.gold.value == 20 and bs.gold.source == 'observation'
    assert bs.write_seq == seq0, '贡献算术零直写零占版本'


def test_equip_diamond_phase_gold_worn_basis_and_floor() -> None:
    """宝钻贡献算术:已穿件数 ×(累计阶段 ÷ 3 整除)——「装备者」口径(库存
    不计);零头阶段经整除天然结转;负累计 = 调用错炸错。"""
    bs = _make_bs(front=[_wearing(1, 1, 1, ['财富宝钻']),
                         _wearing(2, 2, 2, ['财富宝钻'])],
                  equips=['财富宝钻'])
    assert DIAMOND_PHASE_STEP == 3
    assert equip_diamond_phase_gold(bs, phases_elapsed=2) == 0    # 零头未到
    assert equip_diamond_phase_gold(bs, phases_elapsed=3) == 2    # 2 穿 ×1
    assert equip_diamond_phase_gold(bs, phases_elapsed=7) == 4    # 2 穿 ×2
    with pytest.raises(ValueError):
        equip_diamond_phase_gold(bs, phases_elapsed=-1)


def test_equip_wrench_duplicate_gold_contribution() -> None:
    """精密扳手贡献算术:持有精密时每笔拆装扳手获得改 +1 金(定额与持有
    件数无关);精密不在场 = 0(扳手照常入栏);纯算术零直写。"""
    held = _make_bs(equips=['精密拆装扳手'], gold=10)
    seq0 = held.write_seq
    assert equip_wrench_duplicate_gold(held) == 1
    assert held.gold.value == 10 and held.write_seq == seq0
    not_held = _make_bs(equips=['拆装扳手'], gold=10)
    assert equip_wrench_duplicate_gold(not_held) == 0
