"""W62 件2(ADR-0329)d2 卖通道生产接线锁:守卫与槽位语义执行。

设计章2.5/2.9 测试锁设计;新锁一律按 ADR-0316 槽位语义(定长 9 槽 None 混排)写。

(W707 对账瘦身·w729 收尾执行:原锁 3(income 口径)并入
test_cw_w323_sell_income_telemetry(读端 fallback 锁已覆盖 SellBench.income
→ decisions → query_economy 全链);原锁 4(gold 对拍含卖入)与
test_cw_w510_refreshfee 末两断言逐字重复,退役。失去保护面由上述两处承接。)
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    SellBench,
    bench_occupied,
    mutate_bench_deployed,
)
from sr_od.application.currency_war.operations.prep.shop import (
    sell_guard_ok,
)


def _mk_bench(names: list[str | None]) -> list[BenchChar | None]:
    """按槽位语义构造定长 9 槽表(下标=槽位;None=空槽)。"""
    out: list[BenchChar | None] = [None] * 9
    for i, n in enumerate(names):
        if n:
            out[i] = BenchChar(slot=i + 1, char_id=n, faction='散')
    return out


def test_sell_guard_ok_blocks_stale_slot():
    """锁 1(守卫,设计章2.5):生成期期望名 vs 执行期现槽名——不符=槽位已被
    前序动作消费(3合1 merge/前笔卖出)→ 拦截。"""
    assert sell_guard_ok('万敌', '万敌') is True      # 一致 → 放行
    assert sell_guard_ok('万敌', '银枝') is False     # 现槽已换人 → 拦截
    assert sell_guard_ok('万敌', None) is False       # 现槽已空(被消费)→ 拦截
    assert sell_guard_ok(None, '万敌') is False       # 生成期本就空 → 拦截
    assert sell_guard_ok('', '万敌') is False         # 生成期空名 → 拦截


def test_mutate_sell_bench_slot_semantics_no_shift():
    """锁 2(槽位语义执行,ADR-0316):乱序多笔 SellBench 置 None 不紧缩——
    其余槽位不动(无左移),任意发射序零漂移。"""
    bench = _mk_bench(['万敌', '银枝', '银狼', '娜塔莎', '赛飞儿', '飞霄'])
    deployed: list[BenchChar] = []
    # 乱序发射 [Sell(4), Sell(2)]:先卖 idx4(赛飞儿)→ 再卖 idx2(银狼)
    mutate_bench_deployed(bench, deployed, SellBench(bench_idx=4))
    mutate_bench_deployed(bench, deployed, SellBench(bench_idx=2))
    assert bench[4] is None, 'idx4 卖后置 None'
    assert bench[2] is None, 'idx2 卖后置 None'
    assert [c.char_id for c in bench if c is not None] == ['万敌', '银枝', '娜塔莎', '飞霄'], (
        '其余槽位不动(无左移)')
    assert bench_occupied(bench) == 4
