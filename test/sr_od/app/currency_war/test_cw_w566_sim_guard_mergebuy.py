# -*- coding: utf-8 -*-
"""W566:sim 满栏购买守卫解冻锁测试(ADR-0453 影响节兑现)。

sim 满栏 BuyCard 从「一律拒」(ADR-0283)升级为「触发合成则执行」
——与生产 ``cw_state.simulate`` 满栏分支同源:判据单一源 =
``merge_buy_completes``/``merge_buy_k``(merge_mechanics.md §2.5
自动多买);金 k×单价全款、店 k 张同身份牌下架、合成链照走。
``bench_full_skipped_*`` 计数语义收窄为「非合成拒买」——合成买
已执行,计入 skipped 会让拦截指标说谎。

手法:桩策略在决策时点直接构造满栏态(bench 填满 + 店内注入
同名牌),经真实 sim 执行层走完整动作循环——非 mock 执行分支。
"""
from __future__ import annotations


class _FullBenchStub:
    """一次性桩:首次 decide_prep 构造满栏态并提议一张店内牌,
    第二次调用记录执行后金(同轮内,无收入插入)→ 金差 = 执行账。"""

    def __init__(self, own_copies: int, shop_copies: int,
                 buy_name_idx: int = 0) -> None:
        self.own_copies = own_copies
        self.shop_copies = shop_copies
        self.buy_name_idx = buy_name_idx
        self.armed = True
        self.gold_before: int | None = None
        self.gold_after: int | None = None
        self.shop_target_left: int | None = None

    def update_target(self, st, sess, cfg) -> None:  # noqa: ANN001
        pass

    def decide_prep(self, st, sess, cfg):  # noqa: ANN001
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.cw_state import (
            BenchChar,
            BuyCard,
            ShopCard,
        )
        if not self.armed:
            if self.gold_after is None:
                # 首次记录 = 执行后同轮(轮内无收入插入,金差纯执行账)
                self.gold_after = st.gold
                names1 = sorted(n for n, c in CHARACTERS.items()
                                if c.cost == 1)
                self.shop_target_left = sum(
                    1 for c in st.shop
                    if c.name == names1[self.buy_name_idx])
            return []
        self.armed = False
        self.gold_before = st.gold
        names1 = sorted(n for n, c in CHARACTERS.items() if c.cost == 1)
        tgt = names1[self.buy_name_idx]
        fillers = [n for i, n in enumerate(names1)
                   if i != self.buy_name_idx][:9]
        # 满栏构造:filler 铺底 + own_copies 张目标(同星 1★)
        st.bench = [BenchChar(slot=i, char_id=fillers[i], faction='?')
                    for i in range(9 - self.own_copies)] \
            + [BenchChar(slot=8 - j, char_id=tgt, faction='?')
               for j in range(self.own_copies)]
        st.shop = [ShopCard(x=100 + j, faction='?', name=tgt, cost=1)
                   for j in range(self.shop_copies)]
        return [BuyCard(card=st.shop[0], reason='stub')]


def _run(stub) -> object:  # noqa: ANN001
    from sr_od.application.currency_war.cw_sim import simulate_p1
    return simulate_p1(1, pool='fallback', strategy=stub)


def _ledger_buys(res) -> list[dict]:  # noqa: ANN001
    return [a for row in res.ledger for a in (row.get('actions') or [])
            if a.get('__type__') == 'BuyCard']


def _total_skipped(res) -> int:  # noqa: ANN001
    return sum((row.get('sim') or {}).get('bench_full_skipped_buys', 0)
               for row in res.ledger)


def test_sim_fullbench_merge_buy_executes_k2() -> None:
    """满栏 own=1 + 店 2 张 → 自动多买 k=2 执行:金 2×全款、
    合成发生、bench 不超容、不计入 skipped。"""
    stub = _FullBenchStub(own_copies=1, shop_copies=2)
    res = _run(stub)
    cost = 1
    buys = _ledger_buys(res)
    assert any(a.get('count') == 2 for a in buys), \
        '满栏合成买未执行或 count 披露缺失(W566 回归)'
    assert stub.gold_before is not None and stub.gold_after is not None
    assert stub.gold_before - stub.gold_after == 2 * cost, \
        f'金账非 k×单价全款:{stub.gold_before - stub.gold_after}'
    assert _total_skipped(res) == 0, '合成买被计入 skipped(计数语义未收窄)'
    # 店 k 张同身份牌下架(槽消费语义)
    assert stub.shop_target_left == 0, \
        f'店内应下架 {stub.shop_copies} 张,剩 {stub.shop_target_left}'
    # 合成链照走:触发轮 sim.merges ≥1;全程 bench 不超容
    trig = [row for row in res.ledger
            if any(a.get('count') == 2 for a in (row.get('actions') or []))]
    assert trig and (trig[0].get('sim') or {}).get('merges', 0) >= 1
    from sr_od.application.currency_war.cw_state import BENCH_CAPACITY
    for row in res.ledger:
        bench_n = len((row.get('state') or {}).get('bench') or [])
        assert bench_n <= BENCH_CAPACITY, '满栏合成买后 bench 超容'


def test_sim_fullbench_merge_buy_executes_k1() -> None:
    """满栏 own=2 + 店 1 张 → k=1 合成买执行(旧 k=1 特例的
    守卫路径等价面),不计入 skipped。"""
    stub = _FullBenchStub(own_copies=2, shop_copies=1)
    res = _run(stub)
    buys = _ledger_buys(res)
    assert len(buys) == 1 and buys[0].get('count', 1) == 1
    assert stub.gold_before - stub.gold_after == 1
    assert _total_skipped(res) == 0
    trig = [row for row in res.ledger
            if any(a.get('__type__') == 'BuyCard'
                   for a in (row.get('actions') or []))]
    assert trig and (trig[0].get('sim') or {}).get('merges', 0) >= 1


def test_sim_fullbench_non_merge_buy_still_rejected() -> None:
    """满栏且不满足合成(own=0、店 1 张凑不满)→ 仍拒(ADR-0283
    兜底语义保留):金不动、牌不下架、计数披露。"""
    stub = _FullBenchStub(own_copies=0, shop_copies=1)
    res = _run(stub)
    assert _ledger_buys(res) == [], '非合成满栏买被错误执行'
    assert _total_skipped(res) == 1, '非合成拒买未计数'
    # 拒买路径无执行账:两时点间金只增(收入)不减——无购买/刷新支出
    assert stub.gold_after >= stub.gold_before, '拒买路径出现金支出'
