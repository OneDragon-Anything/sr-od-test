"""W62 件2(ADR-0329)d2 卖通道生产接线锁:守卫 / 槽位语义执行 / income 口径 / gold 对拍含卖入。

设计章2.9 测试锁设计;新锁一律按 ADR-0316 槽位语义(定长 9 槽 None 混排)写。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    SellBench,
    bench_occupied,
    mutate_bench_deployed,
)
from sr_od.application.currency_war.telemetry.cw_telemetry import (
    TelemetryRecorder,
    query_economy,
    serialize_action,
)
from sr_od.application.currency_war.operations.prep.shop import (
    expected_gold_after_actions,
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


def test_serialize_sellbench_income_and_economy_view():
    """锁 3(income 口径,W50 补采端):SellBench.income 落 decisions 行 + query_economy 卖+NN。"""
    d = serialize_action(SellBench(bench_idx=0, income=6))
    assert d['__type__'] == 'SellBench'
    assert d['income'] == 6
    with tempfile.TemporaryDirectory(prefix='cw_w69_sell_') as tmp:
        rec = TelemetryRecorder(replay_dir=tmp, enabled=True)
        rec.start_run('r1', 'A8')
        rec.record_decision('r1', 'A8', GameState(gold=50, round_num=1, plane=1),
                            'c', {}, {},
                            [SellBench(bench_idx=0, income=6)])
        eco = query_economy(Path(tmp), 'r1')
        assert any('卖+6' in ln for ln in eco), f'economy 视图应汇总卖入,实际 {eco}'


def test_expected_gold_includes_sell_income():
    """锁 4(必改项回归,设计章2.7):gold 差值对拍计算含卖入——
    卖轮实际金 = 开店金 − 花出 + 卖入;旧口径(不含卖入)会误报冲突。"""
    # 卖轮:开店金 50,买 2 费 + 卖入 6 → 实读金应 = 54
    assert expected_gold_after_actions(50, 2, 6) == 54
    # 旧口径(不含卖入)= 48 ≠ 54 → 不修则每卖轮 gold_delta 冲突留证
    assert 50 - 2 != 54
    # 无卖轮时卖入=0,行为不变(向后兼容)
    assert expected_gold_after_actions(50, 10, 0) == 40
