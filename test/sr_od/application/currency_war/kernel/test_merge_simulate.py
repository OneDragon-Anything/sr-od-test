"""合成引擎升星事实采集测试(镜像 src = kernel/cw_merge_simulate.py 的
被测函数 ``_merge_bench`` / ``_apply_full_bench_merge_buy``)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-26-liangzi-tongpin-qiyue.md(定稿)§2.3 条 1 + §4.2:
- **on_merge 事实回调**(additive 参数):每完成一级合并、该级升星落定后
  依次收 ``(角色名, 新星级)``;级联两级 = 两条事实;单级 = 一条;
  无合并 = 零回调;缺省 None = 现行为;
- **on_step 既有消费者回归**:on_step 的调用时机/次数不因 on_merge
  在场而变(既有消费者 merge_cascade_write 逐级落行/collect_ore
  逐步写零破坏);
- **满栏合成买路径**:_apply_full_bench_merge_buy 的 on_merge 透传
  同锁,拒买前置(None)零事实。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)

from sr_od.application.currency_war.kernel.cw_merge_simulate import (
    _apply_full_bench_merge_buy,
    _merge_bench,
)


def _bench(entries: list) -> list:
    """工作槽表(条目 + 补空到 9;元素 None = 空洞)。"""
    out = list(entries)
    while len(out) < 9:
        out.append(None)
    return out


def test_on_merge_cascade_two_levels_in_order() -> None:
    """级联两级事实(T-26 设计 §4.2):预置 2×1★花火 + 2×2★花火,推演进
    一只 1★(模拟买牌腿后调引擎)→ on_merge 依次收 (花火, 2)、(花火, 3)
    ——逐级触发判例:每完成一级 3 合 1 各一条事实,顺序 = 合成推进序。"""
    bench = _bench([_bc('花火'), _bc('花火'),
                    _bc('花火', star=2), _bc('花火', star=2)])
    bench[4] = _bc('花火')   # 待合并的第 3 只 1★
    facts: list[tuple[str, int]] = []
    _merge_bench(bench, [], on_merge=lambda cid, s: facts.append((cid, s)))
    assert facts == [('花火', 2), ('花火', 3)], \
        f'级联两级各一条事实,顺序推进: {facts}'
    stars = sorted(s.unit.star for s in bench
                   if s is not None and s.kind == 'unit')
    assert stars == [3], f'终态 = 1 个 3★ 产物: {stars}'


def test_on_merge_single_level_and_zero_merge() -> None:
    """单级一条 / 无合并零回调(T-26 设计 §4.2):3×1★希儿 → 恰一条
    (希儿, 2);无三连(2×1★)→ on_merge 零调用且零推进。"""
    bench = _bench([_bc('希儿'), _bc('希儿'), _bc('希儿')])
    facts: list[tuple[str, int]] = []
    _merge_bench(bench, [], on_merge=lambda cid, s: facts.append((cid, s)))
    assert facts == [('希儿', 2)], f'单级恰一条: {facts}'

    bench2 = _bench([_bc('希儿'), _bc('希儿')])
    facts2: list[tuple[str, int]] = []
    steps: list[int] = []
    _merge_bench(bench2, [], on_step=lambda: steps.append(1),
                 on_merge=lambda cid, s: facts2.append((cid, s)))
    assert facts2 == [] and steps == [], '无合并:事实与步回调均零调用'


def test_on_step_consumer_regression_with_on_merge() -> None:
    """on_step 既有消费者回归(T-26 设计 §4.2 末句):on_merge 在场不改变
    on_step 的调用次数与终态语义——每级合并恰一次 on_step、回调内看到
    该级完成后的状态;on_merge 在 on_step 之前收事实(同点相邻,事实
    先于步写)。"""
    bench = _bench([_bc('花火'), _bc('花火'), _bc('花火')])
    facts: list[tuple[str, int]] = []
    step_stars: list[list[int]] = []

    def on_step() -> None:
        step_stars.append(sorted(
            s.unit.star for s in bench
            if s is not None and s.kind == 'unit'))

    _merge_bench(bench, [], on_step=on_step,
                 on_merge=lambda cid, s: facts.append((cid, s)))
    assert facts == [('花火', 2)], '事实回调正常'
    assert len(step_stars) == 1 and step_stars[0] == [2], \
        f'on_step 每级恰一次且看该级终态: {step_stars}'


def test_full_bench_merge_buy_on_merge_passthrough() -> None:
    """满栏合成买事实透传(T-26 设计 §2.3 条 1 后半):满栏 + 店内 2 张
    同名 → k=2 买入 3 合 1,on_merge 收一条 (希儿, 2);拒买前置
    (合成不可达)→ None 且零事实。"""
    bench = _bench([_bc(f'c{i}') for i in range(8)] + [_bc('希儿')])
    shop = [_card('希儿', cost=3, x=1), _card('希儿', cost=3, x=2)]
    facts: list[tuple[str, int]] = []
    k = _apply_full_bench_merge_buy(
        bench, [], _card('希儿', cost=3), shop,
        on_merge=lambda cid, s: facts.append((cid, s)))
    assert k == 2, f'满栏 k = min(店内 2, 3−已有 1 mod 3) = 2: {k}'
    assert facts == [('希儿', 2)], f'透传收一条事实: {facts}'

    # 拒买前置:无同名牌在席(own=0)→ None,零事实零推进
    bench2 = _bench([_bc(f'c{i}') for i in range(9)])
    facts2: list[tuple[str, int]] = []
    k2 = _apply_full_bench_merge_buy(
        bench2, [], _card('花火', cost=2), None,
        on_merge=lambda cid, s: facts2.append((cid, s)))
    assert k2 is None and facts2 == [], '前置不满足:None 且零事实'
