"""大扩招组合效果体锁(镜像 src = kernel/cw_gain_effects.py 的
``PICK_INVEST_EFFECTS['大扩招']`` 组合登记行;按被测方法拆目录规范落位——
test_gain_chain.py 超线冻结禁追加,新增测试落新镜像,先例 = 同目录
test_strategy_compose_grant_plus.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-197-dakuozhao.
md §3 锁 4/锁 5/锁 6/锁 8 + REVIEW-T197 八裁决点默认案:
- 组合登记 = 随机角色腿(变量计数)×具名装备腿,_compose_grant_legs 组合,
  腿序 = 卡文语序随机先/具名后;
- 变量计数(锁 6):效果串条数随注入持金按 dakuozhao_deduction_plan
  角色数分量走(非表载常量)——与 sim 扣金负腿同函数单一源;
- 效果体零写金(锁 5):扣金归 sim 负腿,效果体执行前后 gold 容器
  值/证据笔零触碰(实机(live)和模拟器(sim)两边发放量与扣金解耦);
- 放回语义(锁 8):同 rng 实例 n 抽可重复(预采样序列含重复名 +
  效果串如实携带);
- 席满变体(锁 4):bench 预满 9 → 首抽溢出落位写 overflow 两字段、
  其余抽零写、金零触碰(发放事实与落位成败解耦,效果串恒 n 条;
  扣金不变 = 效果体本就零写金)。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    bench_units_of,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    RandomCharSpec,
    dakuozhao_deduction_plan,
    random_char_pool,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '大扩招'

_NAMED_EQUIP = '完美投影仪'

#: 主锁种子(7 抽形态,前提 = 序列内同名至多 2 只——零升星前提,见主锁
#: 守卫;失配 = 换种子)。
_RECRUIT_SEED = 203103

#: 放回锁种子(10 抽形态,前提 = 序列含重复名——放回语义实证载体,
#: 守卫先行;失配 = 换种子)。
_REPLACEMENT_SEED = 203102


def _pool() -> list[str]:
    """4 费采样池(注册表派生单源,禁手抄清单)。"""
    return random_char_pool(RandomCharSpec(cost=4, star=1))


def _sample(seed: int, count: int) -> list[str]:
    """预采样序列(独立 rng 实例按效果体消费序 n 抽放回;与注入 rng
    同种子同序,腿序改排/采样改式 = 序列漂移即红)。"""
    rng = random.Random(seed)
    pool = _pool()
    return [rng.choice(pool) for _ in range(count)]


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             equips: list[str] | None = None,
             gold: int | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察;镜像
    test_strategy_compose_grant_plus._make_gs,gold 支为本卡新增——
    变量计数腿的现算输入)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
                 for c, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    if gold is not None:
        gs.observe(gs.gold, gold, evidence='t:gold-seed', sig=_SIG_OBS)
    return gs


class _RowSink:
    """缺陷台账行收集(镜像 test_gain_chain 同名 fixture)。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        set_defect_sink(self.rows.append)

    def close(self) -> None:
        set_defect_sink(None)
        consume_defect_sink()

    def kinds(self) -> list[str]:
        return [r['kind'] for r in self.rows]


@pytest.fixture
def rows_sink() -> _RowSink:
    s = _RowSink()
    try:
        yield s
    finally:
        s.close()


def test_dakuozhao_compose_legs_variable_count_chain(
        rows_sink: _RowSink) -> None:
    """组合腿 + 变量计数锁(锁 4/锁 6 主形态):注入持金 30 → 效果串
    恰 7+1 条且顺序 = 随机腿 7 条(名 = 预采样序列,∈4 费池派生集、
    全 1★ 落席)+ 具名腿 1 条(named_equip_grant:完美投影仪 placed);
    bench 恰 +7;equips 恰 +完美投影仪;条数与公式角色数分量对拍
    (单一源锁);效果体零写金(锁 5,gold 值与证据笔保持种子笔);
    正常路径零申报行。

    零升星前提:预采样序列同名至多 2 只(3 合 1 不触发,bench 净增
    = 抽数;破前提 = 换种子,勿盲改断言数)。"""
    expected = _sample(_RECRUIT_SEED, 7)
    # 前提守卫:同名至多 2(零升星)/持金 30 → 公式 n = 7。
    assert max(expected.count(x) for x in set(expected)) <= 2, \
        '种子前提破(同名 ≥3 触发升星):换 _RECRUIT_SEED'
    assert dakuozhao_deduction_plan(30) == (28, 7), '公式对拍前提'

    gs = _make_gs(bench=[], equips=[], gold=30)
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG,
                               rng=random.Random(_RECRUIT_SEED))
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [(name, 1) for name in expected], \
        'bench 恰 +7 全 1★ 且逐抽名 = 预采样序列(同 rng 掷序)'
    assert gs.equips.value == [_NAMED_EQUIP], 'equips 恰 +完美投影仪'
    assert out.effects == (
        *(f'strategy_gift_random:{name}@1star' for name in expected),
        f'named_equip_grant:{_NAMED_EQUIP}(placed=True)',
    ), '效果串恰 7+1 条且顺序 = 卡文语序(随机腿先/具名腿后)'
    # 锁 5(效果体零写金):值与证据笔零触碰(种子笔 t:gold-seed 保持,
    # 扣金归 sim 负腿,live 面金面禁直写)。
    assert int(gs.gold.value or 0) == 30, '金值零触碰'
    assert gs.gold.evidence == 't:gold-seed', '金证据笔零触碰'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_dakuozhao_count_follows_formula_gold_axis(
        rows_sink: _RowSink) -> None:
    """锁 6(变量计数对公式轴):持金 8 → 效果串随机腿恰 2 条
    (= dakuozhao_deduction_plan(8)[1])——发放只数非表载常量,随注入
    持金沿公式走(效果体与 sim 负腿同函数,两端数量口径天然一致;
    主形态 30→7 见组合锁,本锁换点证「不是恒 7」)。"""
    expected = _sample(_RECRUIT_SEED, 2)
    assert dakuozhao_deduction_plan(8) == (8, 2), '公式对拍前提'
    gs = _make_gs(bench=[], equips=[], gold=8)
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG,
                               rng=random.Random(_RECRUIT_SEED))
    assert out.effects == (
        *(f'strategy_gift_random:{name}@1star' for name in expected),
        f'named_equip_grant:{_NAMED_EQUIP}(placed=True)',
    ), '持金 8 → 随机腿恰 2 条(变量计数,非常量发放)'
    assert len(bench_units_of(gs)) == 2


def test_dakuozhao_replacement_sampling_with_repetition(
        rows_sink: _RowSink) -> None:
    """锁 8(放回语义):持金 40 → 10 抽,预采样序列含重复名(前提
    守卫先行)且效果串如实携带同名(放回 = 可重复,锁计数与重复存在性,
    非具体名)。落位面:9 空槽容 9 只,第 10 抽溢出(四态②,效果串恒
    10 条 = 发放事实与落位成败解耦)。"""
    expected = _sample(_REPLACEMENT_SEED, 10)
    assert len(set(expected)) < 10, \
        '种子前提破(10 抽无重复,放回语义无实证载体):换 _REPLACEMENT_SEED'
    assert dakuozhao_deduction_plan(40) == (40, 10), '公式对拍前提'
    gs = _make_gs(bench=[], equips=[], gold=40)
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG,
                               rng=random.Random(_REPLACEMENT_SEED))
    assert out.effects == (
        *(f'strategy_gift_random:{name}@1star' for name in expected),
        f'named_equip_grant:{_NAMED_EQUIP}(placed=True)',
    ), '效果串恒 10 条且逐抽名 = 预采样序列(含重复名 = 放回实证)'


def test_dakuozhao_bench_full_overflow_then_zero_writes(
        rows_sink: _RowSink) -> None:
    """席满变体(锁 4):bench 预满 9 → 首抽溢出落位写 overflow 两字段
    (warning=True + card=首抽名)、其余抽零写(overflow_card 保持首抽名、
    bench 满 9 不变)、金零触碰(效果体零写金 = 扣金与落位解耦);
    效果串恒 n 条(发放事实与落位成败解耦,席满不减条)。

    布景约束:预置 9 只**互异名**(同名单星 ×9 自身即 3 合 1 燃料——
    首抽落溢出后链升星判定会立即合成腾位、溢出吸收回席清两字段,
    席满前提被链现役善后消解,布景须避开该自扰)。"""
    expected = _sample(_RECRUIT_SEED, 7)
    assert max(expected.count(x) for x in set(expected)) <= 2, \
        '种子前提破(同名 ≥3 触发升星扰动席满断言):换 _RECRUIT_SEED'
    gs = _make_gs(bench=[(f'测试单位{i}', 1) for i in range(9)],
                  equips=[], gold=30)
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG,
                               rng=random.Random(_RECRUIT_SEED))
    assert out.effects == (
        *(f'strategy_gift_random:{name}@1star' for name in expected),
        f'named_equip_grant:{_NAMED_EQUIP}(placed=True)',
    ), '席满不减条(效果串恒 n 条)'
    assert gs.overflow_warning.value is True, '溢出落位写 warning'
    assert str(gs.overflow_card.value or '') == expected[0], \
        '溢出落位写首抽名(链四态②)'
    assert len(bench_units_of(gs)) == 9, 'bench 满 9 不变(其余抽零写)'
    assert int(gs.gold.value or 0) == 30, '金零触碰(扣金与落位解耦)'
    assert gs.gold.evidence == 't:gold-seed', '金证据笔零触碰'


def test_dakuozhao_zero_gold_zero_grant(rows_sink: _RowSink) -> None:
    """零金边界:持金 0 → 公式 (0, 0) → 随机腿零条(fail-closed),
    具名腿照发(卡文「获得1个【完美投影仪】」无持金条件)。"""
    assert dakuozhao_deduction_plan(0) == (0, 0), '公式对拍前提'
    gs = _make_gs(bench=[], equips=[], gold=0)
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG,
                               rng=random.Random(_RECRUIT_SEED))
    assert out.effects == (f'named_equip_grant:{_NAMED_EQUIP}(placed=True)',), \
        '随机腿零条 + 具名腿照发'
    assert bench_units_of(gs) == []
