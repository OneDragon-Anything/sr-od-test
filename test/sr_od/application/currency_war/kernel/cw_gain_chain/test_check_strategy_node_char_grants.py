"""策略卡每节点绑定角色复制发放检查腿测试(镜像 src = kernel/
cw_gain_chain.py 的 ``check_strategy_node_char_grants``;分方法拆目录规范
落位,文件镜像超限纪律 = 新函数落拆目录新文件,先例 = 同目录
check_strategy_* 族镜像文件)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-165-jiazhi-touzi-jin.md(定稿)§4 锁 4/5/7 + REVIEW-T165 §2/④
(七裁决点全部默认案):

- 锁 4 常规:绑定在场 + prev_kind 非 supply → 恰 1 名 1★ 同名
  (rand=False 确定发放语义;直构容器恒未锚定,写通道断言按
  write_logic_rand 现值形;显式置 prep_anchored=True 才断言 logic 通道);
  未持卡零写;持卡未绑定零写 + defect 证据行(状态机缺口 fail-closed);
- 锁 5 补给后:prev_kind='supply' → 恰 3 名;同位面三形态(P1r5→P1r6 /
  P2r3→P2r4 / P3r3→P3r4)经节点序列真值表现值推导 prev_kind 断言;跨
  位面分支 = 防御代码阴性申报(现役日程三位面末位恒 boss);P1r1(None)
  → 1 名;
- 锁 7 双持共发:金+彩两键并存同窗共发数量独立;彩未注册获得腿前绑定
  恒缺 → 金侧行为不受扰(彩侧 fail-closed 留证)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    DEFECT_STRATEGY_CHAR_BIND_MISSING,
    check_strategy_node_char_grants,
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
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    node_sequence_of,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='SimBackendTest',
                   mode='compute')

_CARD = '价值投资·金'

_BOUND = '青雀'   # 绑定名占位:任意注册表规范名即可(名字身份绑定)


class _RowSink:
    """缺陷台账行收集(镜像 test_gain_chain 同名 fixture,装配 + 必达收尾)。"""

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


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             cards: list[str] | None = None,
             bindings: dict[str, str] | None = None,
             anchored: bool = False) -> GameState:
    """直构容器(bench 槽位 (角色名, 星);cards = 持卡;bindings = 绑定域
    现值;anchored = 显式置位锚定标志〔通道断言切换〕)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=n, star=s))
                 for n, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if cards is not None:
        gs.observe(gs.active_strategies, list(cards), sig=_SIG_OBS)
    if bindings:
        gs.write_logic(gs.strategy_char_grant_bindings, dict(bindings),
                       produced_by='test-seed', evidence='t:bind',
                       sig=_LSIG)
    if anchored:
        gs.prep_anchored = True
    return gs


def test_regular_node_grants_single_copy(rows_sink) -> None:
    """锁 4 常规:绑定在场 + prev_kind 非 supply → 恰 1 名 1★ 同名
    (确定发放;直构容器恒未锚定 → 写通道 = write_logic_rand 现值形,
    与 discharge_due_item_grants rand=False 同形);返回值 = 合计 1。"""
    gs = _make_gs(bench=[], cards=[_CARD], bindings={_CARD: _BOUND})
    seq0 = gs.write_seq
    granted = check_strategy_node_char_grants(gs, prev_kind='battle',
                                              sig=_LSIG)
    assert granted == 1, '基础发放 = 1 名'
    units = bench_units_of(gs)
    assert [(u.char_id, u.star) for u in units] == [(_BOUND, 1)], \
        '恰 1 名 1★ 绑定同名'
    assert gs.bench.source == 'logic_rand', \
        '直构容器未锚定 → 随机态通道(容器锚定态决定,rand=False 同形)'
    assert (gs.bench.evidence or '').startswith(
        f'strategy_node_char:{_CARD}'), '发放写 evidence 前缀'
    assert gs.write_seq > seq0, '落位写发生'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_regular_node_grants_logic_channel_when_anchored(rows_sink) -> None:
    """锁 4 通道切换面:显式置 prep_anchored=True 的容器上 → 确定发放走
    logic 通道(失配网原样生效)。"""
    gs = _make_gs(bench=[], cards=[_CARD], bindings={_CARD: _BOUND},
                  anchored=True)
    check_strategy_node_char_grants(gs, prev_kind='encounter', sig=_LSIG)
    assert gs.bench.source == 'logic', '锚定容器确定发放 → 确定面'
    assert [(u.char_id, u.star) for u in bench_units_of(gs)] == \
        [(_BOUND, 1)], '发放真值同形'


def test_no_card_zero_write(rows_sink) -> None:
    """锁 4 负锁:未持卡 → 零写零发放(表外卡同路,登记表外禁猜装)。"""
    for cards in (None, ['躺平']):
        gs = _make_gs(bench=[], cards=cards)
        seq0 = gs.write_seq
        granted = check_strategy_node_char_grants(gs, prev_kind='supply',
                                                  sig=_LSIG)
        assert granted == 0 and gs.write_seq == seq0, \
            f'{cards}: 零命中零发放'
        assert bench_units_of(gs) == [], '备战零动'
    assert rows_sink.kinds() == [], '未持卡无缺口申报'


def test_held_without_binding_fails_closed(rows_sink) -> None:
    """锁 4 负锁(核心):持卡未绑定 = 状态机缺口 → defect 证据行 +
    fail-closed 零发放(禁猜绑定名)。"""
    gs = _make_gs(bench=[], cards=[_CARD], bindings=None)
    seq0 = gs.write_seq
    granted = check_strategy_node_char_grants(gs, prev_kind='battle',
                                              sig=_LSIG)
    assert granted == 0 and gs.write_seq == seq0, 'fail-closed 零写'
    assert rows_sink.kinds() == [DEFECT_STRATEGY_CHAR_BIND_MISSING], \
        '缺陷留存证据行(状态机缺口非正常形态)'


def test_supply_prev_grants_three(rows_sink) -> None:
    """锁 5 补给后主锁:prev_kind='supply' → 恰 3 名 1★(「补给后」=
    前一进入节点为补给 → 本次进入 1+2=3 名,文义直读);批内 3 同名
    1★ 凑三 → 获得链现役升星级联自然合并(返回值 = 发放名数,级联
    前口径)。"""
    gs = _make_gs(bench=[], cards=[_CARD], bindings={_CARD: _BOUND})
    granted = check_strategy_node_char_grants(gs, prev_kind='supply',
                                              sig=_LSIG)
    assert granted == 3, '补给后 = 1+2 = 3 名'
    units = bench_units_of(gs)
    assert [(u.char_id, u.star) for u in units] == [(_BOUND, 2)], \
        '3 名 1★ 同名批内凑三 → 链现役 3 合 1 升星级联 = 席面 1 只 2★'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_supply_after_positions_derived_from_schedule(rows_sink) -> None:
    """锁 5 同位面三形态(经节点序列真值表现值推导 prev_kind):P1r5→
    P1r6 / P2r3→P2r4 / P3r3→P3r4 三处前序位恒 supply(现役日程)→
    派生 prev_kind='supply' → 各恰 3 名;跨位面分支阴性申报(三位面末
    位恒 boss → r1 跨位面推导现役不可达 supply 形态,防御代码);P1r1
    (无前节点,None)→ 基础 1 名。"""
    # 同位面三形态:前序位推导真值 = supply(现役日程锁 + 发放数锁)
    for plane, r in ((1, 6), (2, 4), (3, 4)):
        prev_kind = node_sequence_of(plane)[r - 2]
        assert prev_kind == 'supply', f'P{plane}r{r - 1} = 补给(现役日程)'
        gs = _make_gs(bench=[], cards=[_CARD], bindings={_CARD: _BOUND})
        granted = check_strategy_node_char_grants(gs, prev_kind=prev_kind,
                                                  sig=_LSIG)
        assert granted == 3, f'P{plane}r{r}: 补给后继窗 = 3 名'
    # 跨位面阴性申报:现役日程下 r1 的跨位面前节点恒 boss(非 supply
    # → 基础 1 名,「补给后」跨位面不可达,防御分支无生产路径)
    for plane in (2, 3):
        prev_kind = node_sequence_of(plane - 1)[-1]
        assert prev_kind == 'boss', f'P{plane}r1 跨位面前节点 = boss(阴性)'
    # P1r1:无前节点(None)→ 基础 1 名照发
    gs = _make_gs(bench=[], cards=[_CARD], bindings={_CARD: _BOUND})
    granted = check_strategy_node_char_grants(gs, prev_kind=None, sig=_LSIG)
    assert granted == 1, 'P1r1 无前节点 = 基础 1 名'
    assert rows_sink.kinds() == [], '全形态零申报行'


def test_dual_hold_grants_independent_fail_closed(
        rows_sink, monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 7 双持共发:金+彩两键并存 → 金侧行为不受扰(数量独立)。
    两形态:①现役形(彩未注册获得腿 = 绑定表外卡)→ 金侧照发、彩侧
    表外卡静默零写;②彩注册后形(monkeypatch 表加彩行,绑定双键并存)
    → 各按绑定独立判定发放,数量互不挤占。"""
    # ① 现役形:彩 = 绑定表内卡[T-321 展开卡批注册]但绑定缺 → 持卡未
    # 绑定 defect 分支申报一行(bind_missing),金侧行为不受扰
    gs = _make_gs(bench=[], cards=[_CARD, '价值投资·彩'],
                  bindings={_CARD: _BOUND})
    granted = check_strategy_node_char_grants(gs, prev_kind='supply',
                                              sig=_LSIG)
    assert granted == 3, '金侧 3 名(彩侧表外卡不计入)'
    units = bench_units_of(gs)
    assert all(u.char_id == _BOUND for u in units) \
        and sum(3 ** (u.star - 1) for u in units) == 3, \
        '共发面 = 金侧绑定名 3 份副本质量(升星级联保质量;彩侧零写)'
    assert rows_sink.kinds() == ['gain_chain_strategy_char_bind_missing'], \
        '彩侧表内卡绑定缺 = defect 申报一行(金侧零扰动)'

    # ② 彩注册后形[T-321 展开卡批注册已兑现,monkeypatch 冗余无害]:
    # 表加彩行 + 绑定双键并存;先清形①申报行(sink 同测试内累积)
    rows_sink.rows.clear()
    from sr_od.application.currency_war.kernel import cw_gain_chain
    monkeypatch.setitem(cw_gain_chain._STRATEGY_CHAR_GRANT_BINDINGS,
                        '价值投资·彩', (2, 1, 2))
    gs2 = _make_gs(bench=[], cards=[_CARD, '价值投资·彩'],
                   bindings={_CARD: _BOUND, '价值投资·彩': '卡芙卡'})
    granted2 = check_strategy_node_char_grants(gs2, prev_kind='battle',
                                               sig=_LSIG)
    assert granted2 == 2, '双持共发 = 1+1(数量独立)'
    names = sorted(u.char_id for u in bench_units_of(gs2))
    assert names == sorted([_BOUND, '卡芙卡']), '各按绑定逐卡发放'
    assert rows_sink.kinds() == [], '双绑定齐备零申报行'
