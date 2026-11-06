"""策略卡周期离场弹除链测试(镜像 src = kernel/cw_gain_chain.py 的
discharge_due_kechuan_leaves + _remove_kechuan_units + cw_game_state
_tick_pending_kechuan_leaves)。

测试面依据 = 迭代设计 designs/T-368-peipei-kechuan.md §9.2 效果条目③
(v3.1,用户裁定 2026-11-05 真实建模;T-207 四缺口之「离场原语缺」本批
立项收尾):
- 后继 N 计数锚:队列 (uid, 5) tick×4 后 remaining=1 未到期,tick×5 后
  remaining=0 到期弹除(拿卡节点不计入 = tick 挂节点推进边界承载,
  pending_strategy_grants 同形);remaining<=0「到了及以后都算」;
- 离场原语移除:uid 命中 ∧ 身份==佩佩 → 槽位置 None;uid 不命中
  (他卡佩佩)零波及——个体归属承载判据;溢出位身份串无 uid 载体
  结构性不可移除(溢出佩佩豁离场);
- 装备转移走 gain_equipment 原语:佩佩持进阶件 → gs.equips 入栏;
  持好运来局转换拦截自动跟随(留下件变好运令牌——「留下所有装备」=
  玩家获得判读,与穿戴条目直写不转换形成对照);转移写 = 随机态
  (sim 佩佩恒采样个体,判读 4 单分支);
- 计数域清账:到期条目弹除,未到期条目保留;
- 招财狗金计数随离场回落:win 金按池内佩佩总数计数,本卡佩佩离场后
  自动退出计数池(招财狗发放个体不受波及)——B 案恒在场高估分叉消解。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_win_gold_grants,
    discharge_due_kechuan_leaves,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
    _tick_pending_kechuan_leaves,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '佩佩客串'
_EQ = '反重力皮靴'   # 进阶池真实注册件(equips_by_category('进阶') 成员)
_EQ2 = '以牙还牙甲'   # 进阶池第二件(独家代言占位件同款)


def _slot(unit: Unit | None) -> BenchSlot:
    return BenchSlot(kind='unit', unit=unit) if unit is not None \
        else BenchSlot(kind='empty')


def _gs(*, card: str | None = None,
        bench_units: list[Unit] | None = None,
        queue: tuple = (),
        inventory: bool = True) -> GameState:
    """持卡 + 板面直置 + 离场队列直置(card=None = 未持卡;inventory=
    False = 装备库存保持未读 None,拒落形态)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    if bench_units is not None:
        slots = [_slot(u) for u in bench_units]
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9),
                   sig=_SIG_OBS)
    gs.observe(gs.deployed, DeployedView(front_slots=[], back_slots=[]),
               sig=_SIG_OBS)
    # 装备库存观察态(gain_equipment 原语内拒落语义:equips 未读 = 入栏
    # 承载缺零写——转移链测试需承载在场,seed 空库存)
    if inventory:
        gs.observe(gs.equips, [], sig=_SIG_OBS)
    if queue:
        gs.write_logic(gs.pending_kechuan_leaves, tuple(queue),
                       produced_by='test-seed', evidence='t:queue',
                       sig=_LSIG)
    return gs


def _bench_units(gs: GameState) -> list[Unit]:
    return [s.unit for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def test_successor_n_counter_fires_on_fifth_successor() -> None:
    """后继 N 计数锚:登记 (uid,5) → tick×4 remaining=1 未到期(弹除
    零动作、佩佩在席)→ tick×5 remaining=0 到期 → 弹除移除(拿卡节点
    不计入 = 第 5 个后继节点窗收尾触发,人才激励同刻度)。"""
    pp = Unit(char_id='佩佩', star=1, uid=1)
    gs = _gs(bench_units=[pp], queue=((1, 5),))
    for expected_remaining in (4, 3, 2, 1):
        _tick_pending_kechuan_leaves(gs)
        assert gs.pending_kechuan_leaves.value == ((1, expected_remaining),), \
            f'tick 递减至 {expected_remaining}: ' \
            f'{gs.pending_kechuan_leaves.value!r}'
    assert discharge_due_kechuan_leaves(gs, sig=_LSIG) == (), \
        'remaining=1 未到期误弹除'
    assert _bench_units(gs) == [pp], '未到期误移除'
    _tick_pending_kechuan_leaves(gs)
    assert gs.pending_kechuan_leaves.value == ((1, 0),), \
        f'tick×5 remaining=0: {gs.pending_kechuan_leaves.value!r}'
    effects = discharge_due_kechuan_leaves(gs, sig=_LSIG)
    assert any(e.startswith('kechuan_left(uid=1)') for e in effects), \
        f'离场效果串: {effects!r}'
    assert _bench_units(gs) == [], '到期佩佩未移除'
    assert gs.pending_kechuan_leaves.value == (), '计数域未清账'


def test_remove_by_uid_spares_other_source() -> None:
    """离场原语 uid 过滤:两只佩佩(本卡 uid=1 / 他卡 uid=2),到期条目
    仅 uid=1 → 只移除本卡个体,他卡佩佩零波及;装备随移除转入库存
    (gain_equipment 原语入栏,gs.equips +2)。"""
    ours = Unit(char_id='佩佩', star=1, uid=1, equips=[_EQ, _EQ2])
    theirs = Unit(char_id='佩佩', star=1, uid=2)
    gs = _gs(bench_units=[ours, theirs], queue=((1, 0), (2, 5)))
    effects = discharge_due_kechuan_leaves(gs, sig=_LSIG)
    units = _bench_units(gs)
    assert [(u.char_id, u.uid) for u in units] == [('佩佩', 2)], \
        f'仅本卡个体离场: {units!r}'
    assert gs.equips.value is not None and len(gs.equips.value) == 2, \
        f'装备转移走 gain_equipment 入栏: {gs.equips.value!r}'
    assert _EQ in gs.equips.value and _EQ2 in gs.equips.value, \
        f'入栏件与佩戴件一致: {gs.equips.value!r}'
    assert any(e.startswith('kechuan_leave:') for e in effects), \
        f'转移效果串: {effects!r}'
    assert gs.pending_kechuan_leaves.value == ((2, 5),), \
        f'到期条目弹除,未到期保留: {gs.pending_kechuan_leaves.value!r}'


def test_transfer_follows_conversion_on_lucky_hold() -> None:
    """转移转换拦截自动跟随:持好运来局(转换表 '进阶'→好运令牌),
    本卡佩佩留下的进阶件按转换表变好运令牌入栏(「留下所有装备」=
    玩家获得判读,与穿戴条目直写不转换形成对照——同一局穿戴件在身上
    不转换、离场件入栏才转换)。"""
    ours = Unit(char_id='佩佩', star=1, uid=1, equips=[_EQ])
    gs = _gs(bench_units=[ours, Unit(char_id='佩佩', star=1, uid=2)],
             queue=((1, 0),))
    gs.write_logic(gs.active_strategies, ['好运来'],
                   produced_by='test-seed', evidence='t:card', sig=_LSIG)
    discharge_due_kechuan_leaves(gs, sig=_LSIG)
    assert gs.equips.value == ['好运令牌'], \
        f'离场件被转换(玩家获得判读): {gs.equips.value!r}'


def test_transfer_write_rand_form() -> None:
    """转移写入 = 随机态(判读 4:sim 佩佩恒采样个体恒逻辑随机态,
    sim 单分支;移除写同形态)。"""
    ours = Unit(char_id='佩佩', star=1, uid=1, equips=[_EQ])
    gs = _gs(bench_units=[ours], queue=((1, 0),))
    discharge_due_kechuan_leaves(gs, sig=_LSIG)
    assert gs.bench.source == 'logic_rand', '移除写 = 随机态(source)'
    assert gs.equips.source == 'logic_rand', '转移写 = 随机态(source)'


def test_win_gold_count_falls_after_leave() -> None:
    """招财狗金计数随离场回落:持招财狗,池内两只佩佩(本卡 uid=1 +
    他卡 uid=2)win 金 = 2×表值;本卡离场后 = 1×表值(他卡个体不受
    波及,自动退出/保留计数池——B 案恒在场高估分叉消解)。"""
    gs = _gs(card='招财狗',
             bench_units=[Unit(char_id='佩佩', star=1, uid=1),
                          Unit(char_id='佩佩', star=1, uid=2)],
             queue=((1, 0),))
    assert check_strategy_win_gold_grants(
        gs, won=True, hp_delta=0) == 2, '离场前双佩佩计数'
    discharge_due_kechuan_leaves(gs, sig=_LSIG)
    assert check_strategy_win_gold_grants(
        gs, won=True, hp_delta=0) == 1, '离场后计数回落至他卡个体'


def test_unobserved_board_zero_write() -> None:
    """bench/deployed 未观察 → 队列照弹(条目清账)零移除零转移
    (宁缺勿造,对象域结构性不可执行)。"""
    gs = _gs(queue=((1, 0),))
    effects = discharge_due_kechuan_leaves(gs, sig=_LSIG)
    assert effects == ('kechuan_left(uid=1)',), f'条目照弹: {effects!r}'
    assert gs.pending_kechuan_leaves.value == (), '队列已清'
    assert gs.bench.value is None, '未观察域零写'


def test_unobserved_inventory_transfer_rejected() -> None:
    """装备库存未观察 → 移除照常、转移拒落零写(gain_equipment 原语内
    拒落语义:入栏承载缺 = 该件状态副本中丢失,留存证据于效果串
    placed=False——拒落面归原语既定语义,9.5-5 零特殊处理申报)。"""
    ours = Unit(char_id='佩佩', star=1, uid=1, equips=[_EQ])
    gs = _gs(bench_units=[ours], queue=((1, 0),), inventory=False)
    effects = discharge_due_kechuan_leaves(gs, sig=_LSIG)
    assert _bench_units(gs) == [], '移除不受库存未观察影响'
    assert f'kechuan_leave:{_EQ}(placed=False,uid=1)' in effects, \
        f'转移拒落留证: {effects!r}'
