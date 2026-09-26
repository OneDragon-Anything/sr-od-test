"""晶矿谓词席自由槽容器锁(迭代 2026-09-18-prep-obs-retirement 阶段 3.3/T-3)。

``_sphere_bench_free`` 改容器派生读口 ``bench_free_slots``(旧黑板
``free_bench_slots`` 独立记账退役)——锁:
- free 由容器 bench 槽位表派生;
- 宝箱/典籍占席经 ``slot_occupies`` 口径自动计入(slot_occupies 正本
  cw_game_state.py:1079-1082);
- bench 未观察(None = 不确定)→ BENCH_CAPACITY 保守(宁多收晶矿不误卖)。
"""
from test.sr_od.application.currency_war._cw_helpers import cw4_session

from sr_od.application.currency_war.kernel.cw_exec_state import (
    BENCH_CAPACITY,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.entry import (
    _ore_bench_free,
)

_SIG = ChannelSig(family='obs', actor='cw4_seed',
                  mode='synthesized')


def _write_bench(session, kinds: list[str]) -> None:
    """按 kind 清单写容器 bench 槽位表('unit' 槽带占位身份)。"""
    gs = game_state_of(session)
    slots = [BenchSlot(kind='empty') for _ in kinds]
    for i, kind in enumerate(kinds):
        if kind == 'unit':
            slots[i] = BenchSlot(kind='unit', unit=Unit(
                char_id=f'c{i}', star=1, equips=[]))
        elif kind in ('supply_box', 'tome'):
            slots[i] = BenchSlot(kind=kind)
    gs.observe(gs.bench, BenchView(slots=slots, capacity=len(kinds)),
               sig=_SIG)


def test_free_counts_units_and_items():
    """3 角色 + 1 箱 + 1 典籍 = 占 5 席 → free = 4(箱/典籍自动计入)。"""
    session = cw4_session()
    _write_bench(session, ['unit', 'unit', 'unit', 'supply_box', 'tome',
                           'empty', 'empty', 'empty', 'empty'])
    assert _ore_bench_free(game_state_of(session)) == 4


def test_free_unobserved_conservative_capacity():
    """bench 未观察(None = 不确定)→ BENCH_CAPACITY 保守(宁多收晶矿)。"""
    session = cw4_session()
    assert _ore_bench_free(game_state_of(session)) == BENCH_CAPACITY
