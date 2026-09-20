"""席空数 capacity 跟随单一源锁(T-17 用户裁定:三处消费读数统一改吃
``bench_free_slots``,跟随 BenchView.capacity——节省工位改写帧按实席
数计,非定长 9 基线)。

被锁行为(三处消费位各一,均为**关系断言**——同 occupancy 差一档
capacity,读数严格分档;非复述单一源实现):
1. ``cw_line_switch.e_rounds`` 买刷截断:capacity 8(6 占席 → 空位 2)
   vs capacity 9(6 占席 → 空位 3),affordable 充裕时 rolls = 空位数,
   E_rounds 比值 = (1+3)/(1+2) = 4/3(闭式可算,dist/p 同帧同源);
2. ``proof.assemble_lock_frame`` c_sat 席位压力项:capacity 8(7 占席 →
   空位 1,v_slot 席压项激活)vs capacity 9(7 占席 → 空位 2,「在库
   免手写」门 v_slot=0)⇒ c_hold 严格分档;
3. ``economy_cycle._scan_shop_buy_accounts`` O1 填补账:capacity 8
   (6 占席 → 空位 2)只扩账最便宜 2 件;capacity 9 同占席 → 3 件全扩。

载体 = 容器 BenchView 直写(节省工位效果帧的容器形态;capacity 字段
单一源语义见 kernel BenchView docstring)。
"""
from __future__ import annotations

import math

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    NodeKey,
    ShopCard,
    ShopPayload,
    ShopSlot,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    pair_target_comp,
)
from sr_od.application.currency_war.kernel.cw_line_switch import e_rounds
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof
from sr_od.application.currency_war.strategies.impl.mandate_v1.economy_cycle import (
    _scan_shop_buy_accounts,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_SIG = ChannelSig(family='logic_action', actor='cw-t17-test', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='cw-t17-test', mode='synthesized')

_PAIR = ('持续伤害', '希儿系')


def _pair_comp():
    return pair_target_comp(_PAIR)


def _filler_names(n: int) -> list[str]:
    """非持续伤害线的注册表角色名 n 个(占席件;锁前提自检)。"""
    names = [name for name, ch in sorted(CHARACTERS.items())
             if ch.cost and '持续伤害' not in (ch.flows or ())
             and name != '希儿']
    assert len(names) >= n, '注册表非 DOT 名不足(锁前提失效)'
    return names[:n]


def _slots(entries: list[tuple[str, int]], capacity: int) -> BenchView:
    """占席条目 → BenchView(空槽补齐至 capacity;T-17 载体)。"""
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=name, star=star, slot=i + 1))
             for i, (name, star) in enumerate(entries)]
    slots += [BenchSlot(kind='empty')] * (capacity - len(slots))
    return BenchView(slots=slots, capacity=capacity)


def _session_with(comp):
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = comp
    return s


# ===== 锁 1:e_rounds 买刷截断跟随 capacity =====


def test_e_rounds_rolls_follow_bench_capacity():
    """capacity 8(空位 2)vs 9(空位 3):affordable 充裕帧 rolls = 空位
    数,E_rounds 闭式比值 = 4/3(同 comp 同帧面,唯 bench capacity 差)。"""
    comp = _pair_comp()
    names = _filler_names(6)
    sess = _session_with(comp)

    def _e(capacity: int) -> float:
        gs = game_state_of(sess)
        gs.write_logic(gs.node,
                       NodeKey(plane=1, round_num=2, kind='prep'),
                       produced_by='t17', sig=_SIG)
        gs.write_logic(gs.level, 5, produced_by='t17', sig=_SIG)
        gs.write_logic(gs.gold, 100000, produced_by='t17', sig=_SIG)
        gs.write_logic(gs.bench,
                       _slots([(n, 1) for n in names], capacity),
                       produced_by='t17', sig=_SIG)
        return e_rounds(comp, gs)

    e8, e9 = _e(8), _e(9)
    assert math.isfinite(e8) and math.isfinite(e9), '锁前提:双帧 E 有限'
    assert abs(e8 / e9 - 4.0 / 3.0) < 1e-6, \
        f'席空数未跟随 capacity(E8/E9={e8 / e9!r},期望 4/3)'


# ===== 锁 2:proof c_sat 席位压力项跟随 capacity =====


def test_lock_frame_csat_follows_bench_capacity():
    """capacity 8(7 占席 → 空位 1)激活 v_slot 席压项;capacity 9(7 占席
    → 空位 2)落在「在库免手写」门内 c_sat=0 ⇒ c_hold 严格分档(占席
    名单/星级/其余帧面逐项相同,唯 capacity 差)。"""
    comp = _pair_comp()
    names = _filler_names(7)
    sess = _session_with(comp)

    def _frame(capacity: int):
        gs = game_state_of(sess)
        gs.write_logic(gs.node,
                       NodeKey(plane=1, round_num=2, kind='prep'),
                       produced_by='t17', sig=_SIG)
        gs.write_logic(gs.level, 5, produced_by='t17', sig=_SIG)
        gs.write_logic(gs.gold, 100000, produced_by='t17', sig=_SIG)
        gs.write_logic(gs.bench,
                       _slots([(n, 1) for n in names], capacity),
                       produced_by='t17', sig=_SIG)
        gs.write_logic(gs.front_row,
                       [Unit(char_id='希儿', star=1, slot=1)],
                       produced_by='t17', sig=_SIG)
        return proof.assemble_lock_frame(gs, sess)[2]

    f8 = _frame(8)
    f9 = _frame(9)
    assert f8.c_hold > f9.c_hold, \
        (f'席压项未跟随 capacity(c_hold@cap8={f8.c_hold!r}, '
         f'c_hold@cap9={f9.c_hold!r})')
    assert f8.c_hold > 0, '空位 1 帧席压项应激活'


# ===== 锁 3:O1 填补账扩账件数跟随 capacity =====


def test_fill_account_follows_bench_capacity():
    """capacity 8(6 占席 → 空位 2)只扩账最便宜 2 件;capacity 9 同占席
    → 3 件全扩(店内件非合成非跨档,费用即件价)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    def _scan(capacity: int):
        sess = cw4_session(_pair_comp())
        gs = game_state_of(sess)
        gs.write_logic(gs.node,
                       NodeKey(plane=1, round_num=2, kind='prep'),
                       produced_by='t17', sig=_SIG)
        gs.write_logic(gs.level, 5, produced_by='t17', sig=_SIG)
        gs.write_logic(gs.bench,
                       _slots([(f'注册表外散件{i}', 1) for i in range(6)],
                              capacity),
                       produced_by='t17', sig=_SIG)
        gs.observe(gs.shop,
                   ShopPayload(cards=[ShopSlot(kind='content', card=ShopCard(
                       name=f'注册表外件{c}', cost=c, star=1, slot=i + 1))
                       for i, c in enumerate((10, 20, 30))],
                       refresh_probs={}),
                   sig=_SIG_OBS)
        return _scan_shop_buy_accounts(gs, DEFAULT_REGISTRY)

    _costs8, fill8 = _scan(8)
    _costs9, fill9 = _scan(9)
    assert fill8 == [10, 20], f'空位 2 帧只扩账最便宜 2 件,实得 {fill8!r}'
    assert fill9 == [10, 20, 30], f'空位 3 帧三件全扩,实得 {fill9!r}'


# (锁前提自检:COMP_LIBRARY 引用保留防 tree-shake 误判——本文件锁面
#  经 pair_target_comp 走配方键面,不需要 library 实例。)
assert COMP_LIBRARY, '注册表 comp 库非空'
