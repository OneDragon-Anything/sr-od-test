"""狸职手续(id 204001)具名角色发放腿 count 泛化把结果写进状态副本的实现分支锁(镜像 src =
kernel/cw_gain_effects.py ``_STRATEGY_CHAR_GRANTS['狸职手续'] =
('狸职狸狸', 3)`` + ``_make_char_grant_effect`` count 循环;按被测方法拆
目录规范落位——test_gain_chain.py 超线冻结禁追加,新锁落新镜像,先例 =
同目录 test_strategy_huanyu_grants.py;单发成员(只数 = 1)归同目录
test_strategy_char_grant.py,本文件只辖只数 > 1 成员)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-207-lizhi-shouxu.md(定稿)§4 锁 1/锁 4 + REVIEW-T207 九裁决点默认案:
- 注册行直测:登记名 = 实机录名「狸职狸狸」归一(防回退卡面用名
  「狸狸」——该形态会被登记面角色名漂移哨炸,锁先行暴露意图),只数 3
  不进登记表(估值档位与只数无关),把结果写进状态副本的实现分支只数单一源 = 工厂表行值;
- 世界发放腿(count=3):on_strategy_gained 直构(rand=False)→ 狸职狸狸
  逐次三发,每发一条 ``char_grant:`` 串;同名凑三触发链现役合成级联 =
  链上如实记账(池终态 1×2★,merge 计数随串留证),席满溢出分支
  overflow_card = 狸职狸狸(单位 kind 侧,非占席道具侧)。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    DEFECT_OVERFLOW_TAKEN,
    STRATEGY_GRANTS,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    _STRATEGY_CHAR_GRANTS,
    PICK_INVEST_EFFECTS,
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
    BENCH_ITEM_NAMES,
    INVESTMENT_STRATEGIES,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '狸职手续'


def _make_gs(*, bench: list[tuple[str, int]] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察;bench 直构槽位 (角色名, 星)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=n, star=s))
                 for n, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    return gs


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


def test_lizhi_registry_row_name_canonicalization() -> None:
    """注册行直测(设计 §4 锁 1):登记发放对象 = 实机录名「狸职狸狸」,
    卡面用名「狸狸」非注册名(归一防回退——按卡面用名登记会被登记面角色
    名漂移哨炸);只数 3 不进登记表,把结果写进状态副本的实现分支只数单一源 = 工厂表行值;
    注册 id 对拍 plaza:204001。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTER_ROSTER
    grant = STRATEGY_GRANTS[_CARD]
    assert grant.chars_immediate == ('狸职狸狸',), '登记名 = 实机录名归一'
    assert '狸狸' not in grant.chars_immediate, '卡面用名非注册名(防回退)'
    assert _STRATEGY_CHAR_GRANTS[_CARD] == ('狸职狸狸', 3, 1), \
        '世界腿只数单一源 = 工厂表行值(卡面明写 3)'
    assert '狸狸' not in CHARACTER_ROSTER, '卡面用名确在注册表外(锁前提)'
    assert INVESTMENT_STRATEGIES[_CARD].source == 'plaza:204001', \
        '注册行 id 对拍'
    assert _CARD in PICK_INVEST_EFFECTS, '世界发放腿注册在册'


def test_lizhi_char_grant_triple_with_merge_cascade(
        rows_sink: _RowSink) -> None:
    """世界发放腿主锁(设计 §4 锁 4,链上如实记账默认案):备战空席直构
    → 狸职狸狸逐次三发(每发一条 char_grant 串,placed=True),第 3 发
    同名凑三触发链现役 3 合 1 合成级联 → 池终态 = 恰 1 只 2★,merge 计数
    随串留证(第 3 串 merge=1);确定发放走确定面,正常路径零申报行。
    sim 交付态 1×2★ 与实拍「三只共存」的分歧按族级申报留证,零特判。"""
    gs = _make_gs(bench=[])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=random.Random(0))
    assert effects == (
        'char_grant:狸职狸狸(placed=True,merge=0,uid=1)',
        'char_grant:狸职狸狸(placed=True,merge=0,uid=2)',
        'char_grant:狸职狸狸(placed=True,merge=1,uid=3)',
    ), '逐次三发 + 合成级联 merge 计数随串留证'
    units = bench_units_of(gs)
    assert [(u.char_id, u.star) for u in units] == [('狸职狸狸', 2)], \
        '池终态 = 1×2★(三合一级联,星级 1 发放占位非先验)'
    assert gs.bench.source == 'logic', '确定发放走确定面'
    assert len(gs.bench.value.slots) == 9, '备战席容量不变式'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_lizhi_char_grant_bench_full_overflow_unit_kind(
        rows_sink: _RowSink) -> None:
    """席满溢出分支(设计 §4 锁 4,链现役语义):bench 满 9(互异单位,
    隔离升星面)→ 第 1 发溢出落位(overflow_card = 狸职狸狸,单位 kind
    侧——狸职狸狸 ∉ 占席道具词表,身份两分不落道具侧),第 2/3 发溢出位
    已占 = 零写留证(DEFECT_OVERFLOW_TAKEN 各一行,placed=False 随串)。"""
    fillers = [('希儿', 1), ('卡芙卡', 1), ('黄泉', 1), ('刃', 1),
               ('椒丘', 1), ('花火', 1), ('翡翠', 1), ('飞霄', 1),
               ('艾丝妲', 1)]
    gs = _make_gs(bench=fillers)
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=random.Random(0))
    assert effects == (
        'char_grant:狸职狸狸(placed=True,merge=0,uid=1)',
        'char_grant:狸职狸狸(placed=False,merge=0,uid=2)',
        'char_grant:狸职狸狸(placed=False,merge=0,uid=3)',
    ), '第 1 发溢出落位,第 2/3 发溢出位已占零写'
    assert gs.overflow_warning.value is True, '席满溢出落位(告警在场)'
    assert gs.overflow_card.value == '狸职狸狸', '溢出位身份 = 角色名'
    assert '狸职狸狸' not in BENCH_ITEM_NAMES, \
        '单位 kind 侧(非占席道具侧,身份两分前提)'
    assert len(bench_units_of(gs)) == 9, '备战席不超容,狸职狸狸在溢出位'
    assert rows_sink.kinds() == [DEFECT_OVERFLOW_TAKEN,
                                 DEFECT_OVERFLOW_TAKEN], '零写两留证'
