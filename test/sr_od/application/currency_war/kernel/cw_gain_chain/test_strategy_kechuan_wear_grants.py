"""策略卡完美通关穿戴检查腿测试(镜像 src = kernel/cw_gain_chain.py 的
check_strategy_kechuan_wear_grants)。

测试面依据 = 迭代设计 designs/T-368-peipei-kechuan.md §9.2 效果条目②
(v3.1,用户裁定 2026-11-05 真实建模;直构形态先例 = 同目录
test_check_strategy_battle_grants.py 的状态容器直置):
- 完胜触发:持卡 ∧ won ∧ hp_delta==0 ∧ 场上本卡佩佩(uid ∈ 离场队列)
  → Unit.equips 直写 append 1 件 ∈ 进阶池,效果串 kechuan_wear 前缀;
- 完美通关未达成不穿(won=False / hp_delta!=0 两条件并列必要,win 金
  同款扑满败局 won=False ∧ hp_delta=0 形态防误发);
- uid 过滤:场上 uid 不在队列的佩佩(他卡发放个体)零穿戴——多来源
  混池的「这只佩佩」建模意图判据(F1 修正的核心承载);
- 队列空集跳写零发(本卡佩佩全部离场后持卡局自然零穿戴);
- 直写旁路转换拦截:持好运来局穿戴件仍 ∈ 进阶池不被转换(穿戴非玩家
  获得,结构性旁路 STRATEGY_EQUIP_GAIN_CONVERSIONS;装备库存零增——
  与离场转移走 gain_equipment 转换形成对照);
- bench/deployed 未观察 → 零写(宁缺勿造,win 金同契约)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_kechuan_wear_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    equips_by_category,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '佩佩客串'
_ADV_POOL = tuple(equips_by_category('进阶'))


def _slot(unit: Unit | None) -> BenchSlot:
    return BenchSlot(kind='unit', unit=unit) if unit is not None \
        else BenchSlot(kind='empty')


def _gs(*, card: str | None = _CARD,
        bench_units: list[Unit] | None = None,
        dep_units: list[Unit] | None = None,
        queue: tuple = ()) -> GameState:
    """持卡 + 板面直置 + 离场队列直置(card=None = 未持卡;bench/dep
    None = 未观察;queue = pending_kechuan_leaves 元素序列)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True   # 采样直写形态 = 锁随机态写通道(先例同款)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    if bench_units is not None:
        slots = [_slot(u) for u in bench_units]
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9),
                   sig=_SIG_OBS)
    if dep_units is not None:
        gs.observe(gs.deployed, DeployedView(front_slots=dep_units,
                                             back_slots=[]), sig=_SIG_OBS)
    if queue:
        gs.write_logic(gs.pending_kechuan_leaves, tuple(queue),
                       produced_by='test-seed', evidence='t:queue',
                       sig=_LSIG)
    return gs


def _bench_units(gs: GameState) -> list[Unit]:
    return [s.unit for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def test_perfect_win_wears_random_advanced() -> None:
    """完胜触发主链:持卡 + 队列 uid=1 + 备战佩佩 uid=1 → equips +1 件
    ∈ 进阶池(采样单一源池);效果串 kechuan_wear 前缀带 uid;穿戴写 =
    bench 域随机态(source = logic_rand 采样直写形态——prep_anchored 锚定标志
    定窗 rand=True 恒 write_logic_rand)。"""
    gs = _gs(bench_units=[Unit(char_id='佩佩', star=1, uid=1)], queue=((1, 5),))
    effects = check_strategy_kechuan_wear_grants(
        gs, won=True, hp_delta=0, sig=_LSIG, rng=random.Random(7))
    assert len(effects) == 1 and effects[0].startswith('kechuan_wear:'), \
        f'效果串形态: {effects!r}'
    assert '(uid=1)' in effects[0], f'效果串带个体 uid: {effects!r}'
    units = _bench_units(gs)
    assert len(units) == 1
    worn = units[0].equips
    assert len(worn) == 1 and worn[0] in _ADV_POOL, \
        f'穿戴 1 件 ∈ 进阶池: {worn!r}'
    assert gs.bench.source == 'logic_rand', '采样直写 = 随机态(source)'


def test_not_perfect_win_no_wear() -> None:
    """完美通关未达成不穿:hp_delta=1(胜但损血)/won=False(扑满败局
    hp_delta=0 形态)两条件并列必要,零写零效果串。"""
    for kw in ({'won': True, 'hp_delta': 1}, {'won': False, 'hp_delta': 0}):
        gs = _gs(bench_units=[Unit(char_id='佩佩', star=1, uid=1)],
                 queue=((1, 5),))
        effects = check_strategy_kechuan_wear_grants(
            gs, sig=_LSIG, rng=random.Random(7), **kw)
        assert effects == (), f'{kw} 误穿戴: {effects!r}'
        assert _bench_units(gs)[0].equips == [], f'{kw} equips 误增'


def test_uid_filter_excludes_other_source_peipei() -> None:
    """uid 过滤他卡佩佩:场上佩佩 uid=99 不在离场队列(招财狗等他卡发放
    个体,零入队)→ 零穿戴(「这只佩佩」个体归属承载判据,F1 核心)。"""
    gs = _gs(bench_units=[Unit(char_id='佩佩', star=1, uid=99)], queue=((1, 5),))
    effects = check_strategy_kechuan_wear_grants(
        gs, won=True, hp_delta=0, sig=_LSIG, rng=random.Random(7))
    assert effects == (), f'他卡佩佩误穿戴: {effects!r}'
    assert _bench_units(gs)[0].equips == [], '他卡佩佩 equips 误增'


def test_empty_owned_set_zero_write() -> None:
    """队列空集跳写零发:持卡但本卡佩佩全离场(队列空)→ 零写零效果串
    (池内即使还有 uid 未知的佩佩也不辖——无 uid 载体不可确认为本卡)。"""
    gs = _gs(bench_units=[Unit(char_id='佩佩', star=1)], queue=())
    effects = check_strategy_kechuan_wear_grants(
        gs, won=True, hp_delta=0, sig=_LSIG, rng=random.Random(7))
    assert effects == (), f'空集误穿戴: {effects!r}'


def test_direct_write_bypasses_conversion() -> None:
    """直写旁路转换拦截:持好运来局(转换表 '进阶'→好运令牌)穿戴件仍
    ∈ 进阶池不被转换,装备库存 gs.equips 零增——穿戴非玩家获得(C2
    定性;与离场转移走原语转换形成对照,对照面归离场链测试)。"""
    gs = _gs(bench_units=[Unit(char_id='佩佩', star=1, uid=1)], queue=((1, 5),))
    gs.write_logic(gs.active_strategies, [_CARD, '好运来'],
                   produced_by='test-seed', evidence='t:card2', sig=_LSIG)
    effects = check_strategy_kechuan_wear_grants(
        gs, won=True, hp_delta=0, sig=_LSIG, rng=random.Random(7))
    assert len(effects) == 1, f'穿戴效果串: {effects!r}'
    worn = _bench_units(gs)[0].equips
    assert worn[0] in _ADV_POOL, f'穿戴件被转换(C2 翻案信号): {worn!r}'
    assert worn[0] != '好运令牌', '穿戴件不得为转换目标'
    assert gs.equips.value in (None, [], ()), '穿戴不得入装备库存'


def test_unobserved_board_zero_write() -> None:
    """bench/deployed 未观察 → 空(宁缺勿造,win 金同契约)。"""
    gs = _gs(queue=((1, 5),))
    assert check_strategy_kechuan_wear_grants(
        gs, won=True, hp_delta=0, sig=_LSIG, rng=random.Random(7)) == ()
