"""并发 review 修复的回归锁:卖出 income 补齐 + tracked 紧凑态防错槽。

背景(2026-08-25 独立 review 的两个实机缺陷修复,无测试配套——本文件补):
①candidates.generate_candidates 的 SellBench 候选此前不带 income——
arbiter 主采纳通道执行后,shop.py 的 gold 差值对拍把回金当「多出来的金」
误报 gold_delta 冲突(carry_gate/remediation 路径都带 income,唯独主通道缺);
②shop.py 卖出执行段:session.tracked_bench_chars 可能是对账写回的紧凑态
(中间有空槽),直接传 mutate_bench_deployed 会让 pad_bench 按 index 补 None
错位 → 清错槽——修复为先经 bench_from_compact 统一为槽位表语义。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    SellBench,
    sell_refund,
)
from sr_od.application.currency_war.decision_v2.candidates import generate_candidates


def _bench_with_sellable() -> list[BenchChar | None]:
    """含可卖件的槽位表:槽 0 三月七(1费1★,回金 1)、槽 2 砂金(2费,1★)。"""
    bench: list[BenchChar | None] = [None] * 9
    bench[0] = BenchChar(slot=1, char_id='三月七', faction='护盾')
    bench[2] = BenchChar(slot=3, char_id='砂金', faction='宇宙市场')
    return bench


def test_sell_candidates_carry_income() -> None:
    """①:生成器产出的 SellBench 候选必带 income(sell_refund 口径)。

    主采纳通道执行后 shop.py gold 对拍用它算期望回金;缺 income=回金被
    记为「未观收入」误报冲突(独立 review 实机发现)。
    """
    from sr_od.application.currency_war.cw_state import GameState
    from sr_od.application.currency_war.cw_strategy import StrategySession
    from sr_od.application.currency_war.decision_v2.registry import \
        DecisionV2Registry

    state = GameState()
    state.bench = _bench_with_sellable()
    state.gold = 10
    sess = StrategySession()
    cands = generate_candidates(state, sess, DecisionV2Registry())
    sells = [c for c in cands if isinstance(c.action, SellBench)]
    assert sells, '应生成卖出候选(垫层可回收语境)'
    for c in sells:
        name = c.action and c.breakdown_hint.get('name')
        ch = CHARACTERS.get(name or '')
        if ch is not None and ch.cost:
            expected = sell_refund(1, ch.cost)
            assert c.action.income == expected, (
                f'{name} 卖出候选 income 应为 sell_refund={expected},'
                f'实际 {c.action.income}(gold 对拍依赖此值)'
            )


def test_tracked_compact_guard_semantics() -> None:
    """②:tracked 紧凑态(含空洞)进 mutate 前的形状统一语义锁。

    修复链:bench_from_compact(滤 None→按 slot 入槽位表)→ mutate 就地
    pad/清槽按槽位语义执行。锁核心不变量:紧凑态输入经统一后,
    SellBench(idx=2) 清的是槽位 2(砂金),不是错位的槽位 1。
    """
    from sr_od.application.currency_war.cw_state import (
        bench_from_compact,
        mutate_bench_deployed,
    )

    # 模拟对账写回的紧凑态:槽 1 三月七 + 槽 3 砂金(中间槽 2 空)
    compact = [BenchChar(slot=1, char_id='三月七', faction='护盾'),
               BenchChar(slot=3, char_id='砂金', faction='宇宙市场')]
    tracked = bench_from_compact([bc for bc in compact])   # 修复同款调用
    assert tracked[0] is not None and tracked[0].char_id == '三月七'
    assert tracked[1] is None                              # 空槽保持空
    assert tracked[2] is not None and tracked[2].char_id == '砂金'

    # 卖槽位 2(0-based,即砂金)→ 该槽置 None,三月七不动
    action = SellBench(bench_idx=2, income=3)
    mutate_bench_deployed(tracked, [], action)
    assert tracked[2] is None, '卖出槽位应置 None'
    assert tracked[0] is not None and tracked[0].char_id == '三月七', \
        '相邻占用槽不受影响(紧凑态防错槽核心)'
