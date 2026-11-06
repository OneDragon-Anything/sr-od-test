"""席空数 capacity 跟随单一源测试(T-17 用户裁定:三处消费读数统一改吃
``bench_free_slots``,跟随 BenchView.capacity——节省工位改写帧按实席
数计,非定长 9 基线)。

被测行为(关系断言——同 occupancy 差一档 capacity,读数严格分档;
非复述单一源实现):``cw_line_switch.e_rounds`` 买刷截断:capacity 8
(6 占席 → 空位 2)vs capacity 9(6 占席 → 空位 3),affordable 充裕时
rolls = 空位数,E_rounds 比值 = (1+3)/(1+2) = 4/3(闭式可算,dist/p
同帧同源)。

(原 proof.assemble_lock_frame c_sat 席压项与 economy_cycle O1 填补账
两个测试已随退役载体在前轮删除,docstring 本处同步收敛为单测试。)

载体 = 状态容器 BenchView 直写(节省工位效果帧的状态容器形态;capacity 字段
单一源语义见 kernel BenchView docstring)。
"""
from __future__ import annotations

import math

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    NodeKey,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_line_switch import e_rounds
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_SIG = ChannelSig(family='logic_action', actor='cw-t17-test', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='cw-t17-test', mode='synthesized')

def _pair_comp():
    """线构造(换源:原配方伪阵容 pair_target_comp 已随配方决策层退役,
    改用注册表真线——持续伤害系,占席件按非 DOT 名筛除保持线外)。"""
    comp = get_comp('专家桑博DOT')
    assert comp is not None
    return comp


def _filler_names(n: int) -> list[str]:
    """非持续伤害线的注册表角色名 n 个(占席件;测试前提自检)。"""
    names = [name for name, ch in sorted(CHARACTERS.items())
             if ch.cost and '持续伤害' not in (ch.flows or ())
             and name != '希儿']
    assert len(names) >= n, '注册表非 DOT 名不足(测试前提失效)'
    return names[:n]


def _slots(entries: list[tuple[str, int]], capacity: int) -> BenchView:
    """占席条目 → BenchView(空槽补齐至 capacity;T-17 载体)。"""
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=name, star=star))
             for i, (name, star) in enumerate(entries)]
    slots += [BenchSlot(kind='empty')] * (capacity - len(slots))
    return BenchView(slots=slots, capacity=capacity)


def _session_with(comp):
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = comp
    return s


# ===== 测试 1:e_rounds 买刷截断跟随 capacity =====


def test_e_rounds_rolls_follow_bench_capacity():
    """capacity 8(空位 2)vs 9(空位 3):affordable 充裕帧 rolls = 空位
    数,E_rounds 闭式比值 = 4/3(同 comp 同帧面,唯 bench capacity 差)。
    容量 3 帧复跑(容量时限族首例建模后的存量跟随锁扩面:2 占席 → 空位 1,
    e3/e9 = (1+3)/(1+1) = 2.0)——派生口对任意容量档跟随,非只 8/9 两档。"""
    comp = _pair_comp()
    names = _filler_names(6)
    sess = _session_with(comp)

    def _e(capacity: int, occupied: int) -> float:
        gs = game_state_of(sess)
        gs.write_logic(gs.node,
                       NodeKey(plane=1, round_num=2, kind='prep'),
                       produced_by='t17', sig=_SIG)
        gs.write_logic(gs.level, 5, produced_by='t17', sig=_SIG)
        gs.write_logic(gs.gold, 100000, produced_by='t17', sig=_SIG)
        gs.write_logic(gs.bench,
                       _slots([(n, 1) for n in names[:occupied]], capacity),
                       produced_by='t17', sig=_SIG)
        return e_rounds(comp, gs)

    e8, e9, e3 = _e(8, 6), _e(9, 6), _e(3, 2)
    assert math.isfinite(e8) and math.isfinite(e9) and math.isfinite(e3), \
        '测试前提:三帧 E 有限'
    assert abs(e8 / e9 - 4.0 / 3.0) < 1e-6, \
        f'席空数未跟随 capacity(E8/E9={e8 / e9!r},期望 4/3)'
    assert abs(e3 / e9 - 2.0) < 1e-6, \
        f'容量 3 帧未跟随(E3/E9={e3 / e9!r},期望 2.0——容量时限族首例扩面)'
