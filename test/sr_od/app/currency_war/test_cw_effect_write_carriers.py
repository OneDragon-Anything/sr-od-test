"""效果写端三载体主题锁(T-63:节点边界金结算载体/工具执行批/拷贝仪参与计数载体)。

设计出处(持久索引):
- 归属判据正本 = docs/develop/sr_od/application/currency_war/game_state/effect-domain.md §6.3
  (确定性→逻辑写;含随机→零逻辑写端,观察收口)+ §6.1(随事件必须落账
  →单版本事务内急算,组合写=一次落账);
- 写入归属申报单一源 = kernel/cw_affix_effects.py EQUIP_REWRITE_DECLARATIONS
  × EQUIP_WRITE_SIDES(逐件登记形与收口去向);
- 实现单一源 = kernel/cw_effect_inventory.py 文末「节点边界金结算载体/
  工具执行批·穿域特权化腿/拷贝仪参与计数载体」三段 +
  kernel/cw_affix_effects.py「工具执行批·执行写端分派」段;
- 轮首收入公式单一源 = kernel/cw_economy.round_start_income(T-21 收口;
  本文件对收入值的预期一律现场重算同源比对,禁复制数值);
- 既有底座锁(登记恰等/贡献算术零直写/负写端具名)在
  test_cw_equip_rewrite_write.py,本文件不重复。

辖域 = 组合写单次落账(收入+财富+宝钻增量)/扳手获得回执窗收口/穿域特权化
双腿/工具分派路由全表/拷贝仪参与计数成熟入席(阈值表/现值观察面/席满申报)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
from sr_od.application.currency_war.kernel.cw_affix_effects import (
    EQUIP_WRITE_SIDES,
    apply_tool_execution_write,
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
from sr_od.application.currency_war.kernel.cw_economy import (
    LostNodeRef,
    round_start_income,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    COPY_MACHINE_MATURE_BATTLES,
    equip_node_gold_grant,
    settle_copy_machine_participation,
    settle_node_boundary_gold,
    settle_wrench_duplicate_gold,
    transform_worn_equip_to_privilege,
)

register_sig_actors('TestSigWriter')


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
             gold: int | None = None) -> BoardState:
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
    return bs


def _bench_view(occupied: int = 0, capacity: int = 9) -> BenchView:
    """前置 N 槽已占(1★单位)、其余空槽的标准备战席。"""
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=_char_by_cost(1), star=1,
                                 slot=i + 1))
             for i in range(occupied)]
    slots += [BenchSlot(kind='empty')] * (capacity - occupied)
    return BenchView(slots=slots, capacity=capacity)


# ==================== 1. 节点边界金结算载体(组合写单次落账) ====================


def test_node_boundary_settlement_combines_income_and_contributions() -> None:
    """组合写主行为:轮首收入(cw_economy 单一源现算同源比对)+ 财富贡献
    合并为**单次**金面 write_logic;收入预期 = round_start_income 同输入
    重算(禁在本文件复制收入数值,对 T-21 单一源只锁衔接不锁值)。"""
    bs = _make_bs(front=[_wearing(1, 1, 1, ['财富'])],
                  equips=['财富'], gold=20)
    income = round_start_income(plane=1, round_num=3, node_type='battle',
                                gold=20, streak=2)
    expected_total = (income.total + equip_node_gold_grant(bs))
    seq0 = bs.write_seq
    report = settle_node_boundary_gold(bs, plane=1, round_num=3,
                                       node_type='battle', streak=2,
                                       frame='p1-r3')
    assert report.branch == income.branch == 'combat'
    assert report.income_total == income.total
    assert report.wealth_gold == equip_node_gold_grant(bs) == 8  # 2 件×4
    assert report.total == expected_total
    assert report.written is True
    assert bs.gold.value == 20 + expected_total
    assert bs.gold.source == 'logic'
    assert bs.gold.evidence == 'node_boundary_gold@p1-r3'
    assert bs.write_seq == seq0 + 1, '组合写 = 单次落账,恰占一个写点版本'


def test_node_boundary_settlement_diamond_delta_passthrough() -> None:
    """宝钻增量透传:调用侧进度载体折算的本拍增量并入同一次写入(载体禁
    内发明进度存储——T-51 缺口申报面,缺省 0 = 保守零授予)。"""
    bs = _make_bs(front=[_wearing(1, 1, 1, ['财富宝钻'])], gold=50)
    income = round_start_income(plane=2, round_num=1, node_type='battle',
                                gold=50, streak=0)
    seq0 = bs.write_seq
    report = settle_node_boundary_gold(bs, plane=2, round_num=1,
                                       node_type='battle', streak=0,
                                       diamond_gold=2)
    assert report.diamond_gold == 2
    assert bs.gold.value == 50 + income.total + 2
    assert bs.write_seq == seq0 + 1


def test_node_boundary_settlement_supply_branch_streak_neutral() -> None:
    """补给轮分支透传(连胜不动由 round_start_income 辖):branch='supply';
    高连胜输入下收入连胜分量恒 0——衔接语义按收入单一源,本载体零改写。"""
    bs = _make_bs(gold=30)
    income = round_start_income(plane=1, round_num=4, node_type='supply',
                                gold=30, streak=5)
    assert income.streak == 0
    report = settle_node_boundary_gold(bs, plane=1, round_num=4,
                                       node_type='supply', streak=5)
    assert report.branch == 'supply'
    assert report.income_total == income.total


def test_node_boundary_settlement_loss_comp_branch() -> None:
    """败补分支透传:lost_node 在场且当前为战斗类 → 补发基项按被败节点
    平面感知键,连胜取 0(口径单一源 = cw_economy,本载体只锁衔接)。"""
    bs = _make_bs(gold=10)
    lost = LostNodeRef(plane=1, round_num=9, node_type='battle')
    income = round_start_income(plane=2, round_num=1, node_type='battle',
                                gold=10, streak=3, lost_node=lost)
    assert income.branch == 'loss_comp' and income.streak == 0
    report = settle_node_boundary_gold(bs, plane=2, round_num=1,
                                       node_type='battle', streak=3,
                                       lost_node=lost)
    assert report.branch == 'loss_comp'
    assert report.income_total == income.total


def test_node_boundary_settlement_skips_when_gold_unread() -> None:
    """金未读(None)= 无累加基座,整拍跳过零写入(禁造假基座;板面重写
    桥金面同族先例)——报告 written=False、零增量留证。"""
    bs = _make_bs(front=[_wearing(1, 1, 1, ['财富'])])
    seq0 = bs.write_seq
    report = settle_node_boundary_gold(bs, plane=1, round_num=3,
                                       node_type='battle', streak=1)
    assert report.written is False and report.total == 0
    assert report.branch == ''
    assert bs.gold.value is None
    assert bs.write_seq == seq0, '跳过 = 零写入零占版本'


def test_wrench_duplicate_gold_settlement() -> None:
    """获得回执窗收口:精密在场 → 拆装扳手获得改 +1 金(单次直写,窗口
    独占);精密不在场 = 0 零写入(扳手照常入栏,消耗品处置归调用侧)。"""
    held = _make_bs(equips=['精密拆装扳手'], gold=10)
    seq0 = held.write_seq
    assert settle_wrench_duplicate_gold(held, frame='loot') == 1
    assert held.gold.value == 11 and held.gold.source == 'logic'
    assert held.gold.evidence == 'equip_wrench_gold@loot'
    assert held.write_seq == seq0 + 1
    not_held = _make_bs(equips=['拆装扳手'], gold=10)
    seq1 = not_held.write_seq
    assert settle_wrench_duplicate_gold(not_held) == 0
    assert not_held.gold.value == 10
    assert not_held.write_seq == seq1
    unread = _make_bs(equips=['精密拆装扳手'])
    assert settle_wrench_duplicate_gold(unread) == 0  # 金未读零写入


# ==================== 2. 工具执行批·穿域特权化腿 ====================


def test_transform_worn_equip_privilege_across_containers() -> None:
    """穿域特权化:目标单位按观察态全字段相等定位,前台/后台/备战席三容器
    均可命中;只变换选定单件(首个命中),同单位其余装备与同容器其他单位
    原样;写入所在容器(source=logic)。"""
    front_unit = _wearing(1, 1, 1, ['生命之环', '拆装扳手'])
    back_unit = _wearing(2, 2, 1, ['生命之环'])
    bs = _make_bs(front=[front_unit], back=[back_unit],
                  bench=BenchView(slots=[BenchSlot(
                      kind='unit',
                      unit=_wearing(3, 1, 1, ['生命之环']))] * 1, capacity=9))
    seq0 = bs.write_seq
    got = transform_worn_equip_to_privilege(bs, front_unit, '生命之环')
    assert got == '生命之环·特权'
    assert bs.front_row.value[0].equips == ['生命之环·特权', '拆装扳手']
    assert bs.front_row.value[0].char_id == front_unit.char_id
    assert bs.front_row.source == 'logic'
    assert bs.write_seq == seq0 + 1
    got = transform_worn_equip_to_privilege(bs, back_unit, '生命之环')
    assert got == '生命之环·特权'
    assert bs.back_row.value[0].equips == ['生命之环·特权']
    assert bs.back_row.source == 'logic'
    bench_unit = bs.bench.value.slots[0].unit
    got = transform_worn_equip_to_privilege(bs, bench_unit, '生命之环')
    assert got == '生命之环·特权'
    assert bs.bench.value.slots[0].unit.equips == ['生命之环·特权']
    assert bs.bench.source == 'logic'


def test_transform_worn_equip_rejects_not_worn_or_stale() -> None:
    """非已穿名单 = 调用错显式炸错(「选择一件」合法输入域);目标单位
    未定位(调用侧快照陈旧)= 零写入返回 None,禁按陈旧快照盲写。"""
    bs = _make_bs(front=[_wearing(1, 1, 1, ['生命之环'])])
    with pytest.raises(ValueError):
        transform_worn_equip_to_privilege(bs, bs.front_row.value[0],
                                          '拆装扳手')  # 未穿
    stale = Unit(char_id=_char_by_cost(5), star=3, equips=['生命之环'], slot=4)
    seq0 = bs.write_seq
    assert transform_worn_equip_to_privilege(bs, stale, '生命之环') is None
    assert bs.write_seq == seq0


# ==================== 3. 工具执行批·分派路由全表 ====================


def test_tool_dispatch_spawn_legs() -> None:
    """入席腿:员工投影仪门=3(超门拒落零写/门内落位 1★ 复制);完美投影
    仪无门;费用缺失 = 调用错(缺费用会假过费用门,禁缺省放行)。"""
    bs = _make_bs(bench=_bench_view())
    seq0 = bs.write_seq
    r = apply_tool_execution_write(bs, '员工投影仪', target_char_id=_char_by_cost(4),
                                   target_cost=4)
    assert (r.leg, r.performed) == ('spawn', False)
    assert bs.write_seq == seq0, '超门拒落 = 零写入'
    r = apply_tool_execution_write(bs, '员工投影仪', target_char_id=_char_by_cost(3),
                                   target_cost=3)
    assert r.performed is True
    assert bs.bench.value.slots[0].unit.star == 1
    r = apply_tool_execution_write(bs, '完美投影仪', target_char_id=_char_by_cost(5),
                                   target_cost=5)
    assert r.performed is True
    assert bs.write_seq == seq0 + 2
    with pytest.raises(ValueError):
        apply_tool_execution_write(bs, '员工投影仪',
                                   target_char_id=_char_by_cost(1))  # 缺费用


def test_tool_dispatch_grant_and_privilege_legs() -> None:
    """入区腿(好运令牌,选定进阶件入库存)与特权化双腿(特权赋予卡:
    target_equip_name=库存腿 / target_unit+chosen_worn_equip=穿域腿);
    非进阶选件与双腿皆缺 = 调用错。"""
    bs = _make_bs(equips=[], front=[_wearing(1, 1, 1, ['生命之环'])])
    r = apply_tool_execution_write(bs, '好运令牌', chosen_equip='生命之环')
    assert (r.leg, r.performed) == ('grant', True)
    assert bs.equips.value == ['生命之环']
    with pytest.raises(ValueError):
        apply_tool_execution_write(bs, '好运令牌', chosen_equip='财富宝钻')
    r = apply_tool_execution_write(bs, '特权赋予卡', target_equip_name='生命之环')
    assert (r.leg, r.performed) == ('inventory', True)
    assert bs.equips.value == ['生命之环·特权']
    r = apply_tool_execution_write(bs, '特权赋予卡',
                                   target_unit=bs.front_row.value[0],
                                   chosen_worn_equip='生命之环')
    assert (r.leg, r.performed) == ('worn', True)
    assert bs.front_row.value[0].equips == ['生命之环·特权']
    with pytest.raises(ValueError):
        apply_tool_execution_write(bs, '特权赋予卡')  # 双腿皆缺


def test_tool_dispatch_zero_write_and_unknown_tool() -> None:
    """零写形留证:拆装扳手(op 既有)/精密拆装扳手(贡献算术,金面归获得
    回执窗收口)/冶金炉(观察收口)performed=False 零写;集外名与非工具名
    (数据拷贝仪=特殊类)= 调用错。"""
    bs = _make_bs(equips=['拆装扳手'], gold=10)
    seq0 = bs.write_seq
    for tool in ('拆装扳手', '精密拆装扳手', '冶金炉'):
        r = apply_tool_execution_write(bs, tool)
        assert r.leg == 'none' and r.performed is False, tool
        assert r.detail  # 零写处置留证非空
    assert bs.write_seq == seq0, '零写形零占版本'
    with pytest.raises(ValueError):
        apply_tool_execution_write(bs, '不存在的工具')
    with pytest.raises(ValueError):
        apply_tool_execution_write(bs, '数据拷贝仪')  # 特殊类非工具


def test_tool_dispatch_covers_all_tool_family() -> None:
    """官方工具族七件全在分派辖域(注册表 category=工具 ↔ 登记表键集);
    家族增删件后本锁红指向分派路由评审。"""
    tools = {n for n, e in EQUIPMENTS.items() if e.category == '工具'}
    assert tools == {'员工投影仪', '好运令牌', '完美投影仪', '拆装扳手',
                     '特权赋予卡', '精密拆装扳手', '冶金炉'}
    assert tools <= set(EQUIP_WRITE_SIDES)
    gate = {'员工投影仪': 3, '完美投影仪': 0}
    for t in tools:
        if t in ('员工投影仪', '完美投影仪'):
            assert (EQUIP_WRITE_SIDES[t]
                    == 'bridge:spawn_equip_bench_unit') and t in gate


# ==================== 4. 拷贝仪参与计数载体 ====================


def test_copy_machine_threshold_table() -> None:
    """成熟阈值表(官方文「每参与 N 场战斗」;cw_equipment_data 同源):
    拷贝仪/Pro=3、Max=2;族外零条目。"""
    assert COPY_MACHINE_MATURE_BATTLES == {'数据拷贝仪': 3, '数据拷贝仪Pro': 3,
                                           '数据拷贝仪Max': 2}


def test_copy_machine_participation_maturity_and_spawn() -> None:
    """参与计数主行为:前台穿戴者逐场推进(单调),第 3 场整除成熟 → 穿戴
    者 1★ 复制入备战席第一空槽;非成熟拍零写零占版本。"""
    wearer = _wearing(2, 1, 1, ['数据拷贝仪'])
    bs = _make_bs(front=[wearer], bench=_bench_view(occupied=2))
    seq0 = bs.write_seq
    assert settle_copy_machine_participation(bs) == []
    assert bs.write_seq == seq0
    assert settle_copy_machine_participation(bs) == []
    seq1 = bs.write_seq
    matured = settle_copy_machine_participation(bs)
    assert len(matured) == 1
    m = matured[0]
    assert (m.equip, m.wearer, m.count, m.placed) == (
        '数据拷贝仪', wearer.char_id, 3, True)
    assert bs.write_seq == seq1 + 1, '成熟 = 入席桥单次直写'
    spawned = bs.bench.value.slots[2].unit
    assert spawned.char_id == wearer.char_id and spawned.star == 1
    assert bs.effects.equip_progress_of('数据拷贝仪', wearer.char_id) == 3
    assert settle_copy_machine_participation(bs) == []          # 第 4 场
    assert settle_copy_machine_participation(bs) == []          # 第 5 场
    matured = settle_copy_machine_participation(bs)             # 第 6 场再熟
    assert matured[0].count == 6 and matured[0].placed is True


def test_copy_machine_max_threshold_and_bench_wearer_excluded() -> None:
    """Max 阈值=2(第 2 场即成熟);备战席穿戴者未上场不参战(现值观察面
    =前台+后台),计数零推进。"""
    front_wearer = _wearing(1, 1, 1, ['数据拷贝仪Max'])
    bench_wearer = _wearing(3, 1, 1, ['数据拷贝仪Max'])
    bs = _make_bs(front=[front_wearer],
                  bench=BenchView(slots=[BenchSlot(kind='unit',
                                                   unit=bench_wearer)]
                                  + [BenchSlot(kind='empty')] * 8, capacity=9))
    assert settle_copy_machine_participation(bs) == []
    matured = settle_copy_machine_participation(bs)
    assert [m.wearer for m in matured] == [front_wearer.char_id]
    assert matured[0].count == 2
    assert bs.effects.equip_progress_of('数据拷贝仪Max',
                                        bench_wearer.char_id) == 0
    assert bs.effects.equip_progress_of('数据拷贝仪Max',
                                        front_wearer.char_id) == 2


def test_copy_machine_bench_full_maturity_consumed() -> None:
    """席满成熟未入席:placed=False 留证,参与计数是事实推进不因落位失败
    回退(单调不重置,§3);下一成熟周期照常推进。"""
    wearer = _wearing(1, 1, 1, ['数据拷贝仪'])
    bs = _make_bs(front=[wearer], bench=_bench_view(occupied=9))
    for _ in range(2):
        assert settle_copy_machine_participation(bs) == []
    matured = settle_copy_machine_participation(bs)
    assert len(matured) == 1 and matured[0].placed is False
    assert bs.effects.equip_progress_of('数据拷贝仪', wearer.char_id) == 3
    seq0 = bs.write_seq
    assert settle_copy_machine_participation(bs) == []   # 第 4 场非成熟
    assert bs.write_seq == seq0


def test_copy_machine_rows_unobserved_and_key_isolation() -> None:
    """行字段从未观察 = 无参战读数,跳过不猜(零推进);进度键 = (装备名,
    装备者) 天然隔离——不同装备/不同穿戴者不串账;n 非正 = 调用错炸错。"""
    wearer = _wearing(1, 1, 1, ['数据拷贝仪'])
    bs = _make_bs(front=[wearer])   # bench 未观察不碍事;front 已读
    empty = BoardState(schema_version=BS_SCHEMA_VERSION)   # 全字段未观察
    assert settle_copy_machine_participation(empty) == []
    assert empty.effects.equip_progress == {}
    other = _make_bs(front=[_wearing(2, 1, 1, ['数据拷贝仪Pro'])])
    settle_copy_machine_participation(other)
    assert bs.effects.equip_progress_of('数据拷贝仪', wearer.char_id) == 0, \
        '不同 BoardState 会话天然隔离'
    eff = other.effects
    assert eff.bump_equip_progress('数据拷贝仪Pro', '甲') == 1
    assert eff.bump_equip_progress('数据拷贝仪', '甲') == 1
    assert eff.equip_progress_of('数据拷贝仪Pro', '甲') == 1
    assert eff.equip_progress_of('数据拷贝仪', '甲') == 1
    with pytest.raises(ValueError):
        eff.bump_equip_progress('数据拷贝仪', '甲', 0)
