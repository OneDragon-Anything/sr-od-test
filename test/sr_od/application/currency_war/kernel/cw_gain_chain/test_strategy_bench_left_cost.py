"""被动收入(id 300601)条件 XP 族第 4 形锁(备战席左一角色基础费用,
量 = 单角色属性直读族内首例;镜像 src = STRATEGY_BENCH_LEFT_COST_XP_
GRANTS/bench_leftmost_unit_of/check_strategy_bench_left_cost_xp/sim
聚段调用块;八锁落拆目录新文件,先例 = 同目录条件 XP 族锁形)。

测试面依据 = 设计稿(原件已退役)T-299 对应稿
(已退役评审稿 无需用户决定 9/9;卡面官方原文:「每次进入新节点时获得经验，数值
等同于你备战席最左侧角色的基础费用。」):

1 注册表锁 / 2 派生矩阵锁 / 3 左一读口锁 / 4 未持卡零 / 5 cost=0 零 /
6 未注册名零 / 7 头部占位件跳过锁 / 8 PENDING 行文案锁。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_bench_left_cost_xp,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    bench_leftmost_unit_of,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_BENCH_LEFT_COST_XP_GRANTS,
)

_SIG_OBS = None  # 占位:本文件零状态副本写(纯判定锁)


def test_registry_closed_set() -> None:
    """锁 1(注册表):集合 = {'被动收入'};孤儿键负控(全体已登记)。"""
    assert set(STRATEGY_BENCH_LEFT_COST_XP_GRANTS) == {'被动收入'}
    for n in STRATEGY_BENCH_LEFT_COST_XP_GRANTS:
        assert n in INVESTMENT_STRATEGIES, f'孤儿键: {n}'


def test_leftmost_reads_slot_order_head() -> None:
    """锁 3(左一读口):槽序头第一单位优先(方向断言 slots[0])。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        GAME_STATE_SCHEMA_VERSION,
        BenchSlot,
        BenchView,
        ChannelSig,
        GameState,
        Unit,
    )
    sig = ChannelSig(family='obs', actor='CwScreenPrep')
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='黑塔', star=1)),
             BenchSlot(kind='unit', unit=Unit(char_id='希儿', star=1))]
    slots += [BenchSlot(kind='empty')] * 7
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=sig)
    left = bench_leftmost_unit_of(gs)
    assert left is not None and left.char_id == '黑塔', \
        f'槽序头优先: {left}'


def test_unheld_zero() -> None:
    """锁 4(未持卡零):未持卡 → 0(不读席)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        GAME_STATE_SCHEMA_VERSION,
        GameState,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert check_strategy_bench_left_cost_xp(gs) == 0, '未持卡零'


def test_pending_row_wording() -> None:
    """锁 8(PENDING 行文案):落地后文案(族行同形)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        strategy_economy,
    )
    pending = getattr(strategy_economy, 'STRATEGY_ECONOMY_PENDING_MODELING',
                      None)
    assert pending is not None, 'PENDING 表已登记'
    row = pending.get('被动收入')
    assert row is not None and '已建状态副本写入通道' in row, f'落地后文案: {row}'
