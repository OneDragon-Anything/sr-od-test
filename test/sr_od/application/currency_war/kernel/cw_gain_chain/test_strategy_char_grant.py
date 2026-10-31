"""溜佩佩/溜佩佩+/招财狗(id 103401/103402/103501)具名角色发放腿锁(镜像 src =
kernel/cw_gain_effects.py 的 ``_STRATEGY_CHAR_GRANTS`` + ``_make_char_grant_
effect`` + ``PICK_INVEST_EFFECTS`` 推导;按被测方法拆目录规范落位——
test_gain_chain.py 超线冻结禁追加,新增测试落新镜像,先例 = 同目录姊妹
镜像文件)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-128-liu-peipei.md(定稿)§4 锁 2/3 + REVIEW-T128 七裁决点默认案:
- 腿语义 = 卡面「佩佩会在你的后排逛街」句(非「获得」直读,人工转正
  登记):具名确定发放 ``gain_character(rand=False)``,星级实参 1 =
  占位非先验(佩佩 = cost0 系统召唤单位无星级,环境侧佩佩发放同判);
  效果串 ``char_grant:佩佩(placed=True,merge=0)``(placed/merge 随串
  留证,前缀独立分域可过滤审计);
- 落位/升星/席满溢出语义全沿链现役:备战空槽落位、席满溢出落位并阻断
  出战(溢出位身份 = 角色名),零新增链为;
- 名单单一源:``_STRATEGY_CHAR_GRANTS`` 与登记表 STRATEGY_GRANTS 三卡
  chars_immediate 逐对相等(两处独立字面量的漂移在备战断言不可见,唯
  此锁 + 落位真值可暴露,箱腿一致性锁同构)。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    STRATEGY_GRANTS,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    _STRATEGY_CHAR_GRANTS,
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

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')


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


@pytest.mark.parametrize('card', ['溜佩佩', '溜佩佩+', '招财狗'])
def test_char_grant_leg_places_peipei(
        card: str, rows_sink: _RowSink) -> None:
    """腿行为主锁(设计 §4 锁 3):on_strategy_gained 直构(rand=False)
    → 备战追加恰 1 只 1★ 佩佩、效果串
    ``char_grant:佩佩(placed=True,merge=0)``(单发零升星)、确定发放走
    确定面、落位写 evidence = pick_invest_char_grant#place;正常路径零
    申报行。两卡效果体同形(金腿 9/15 差异不进效果体,归 STRATEGY_ECONOMY)。"""
    gs = _make_gs(bench=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, card, rand=False, sig=_LSIG,
                                 rng=random.Random(0))
    assert effects == ('char_grant:佩佩(placed=True,merge=0)',), '单发步串'
    units = bench_units_of(gs)
    assert [(u.char_id, u.star) for u in units] == [('佩佩', 1)], \
        '备战追加恰 1 只 1★ 佩佩(星级 1 = 占位非先验)'
    assert gs.bench.source == 'logic', '确定发放走确定面'
    assert gs.bench.evidence == 'pick_invest_char_grant#place', \
        '落位写 evidence(效果体 evidence + #place 后缀)'
    assert gs.write_seq > seq_before, '落位写一行'
    assert rows_sink.kinds() == [], '正常路径零申报行'


@pytest.mark.parametrize('card', ['溜佩佩', '溜佩佩+', '招财狗'])
def test_char_grant_leg_bench_full_overflow(
        card: str, rows_sink: _RowSink) -> None:
    """席满分支(链现役语义,角色与道具同款溢出落位):bench 满 9 →
    溢出落位,overflow_card == 佩佩(角色名两分形态;溢出位阻断出战 =
    溢出建模既定语义),效果串 placed=True;席满溢出是既定语义零申报行。
    填席用 9 只互异单位:升星判断 = 链对全池(备战∪上阵∪溢出)的现役
    机制,同名同星凑三会连升既有单位(与发放腿无关),互异填席隔离该面
    使本锁只辖溢出落位。"""
    fillers = [('希儿', 1), ('卡芙卡', 1), ('黄泉', 1), ('刃', 1),
               ('椒丘', 1), ('花火', 1), ('翡翠', 1), ('飞霄', 1),
               ('艾丝妲', 1)]
    gs = _make_gs(bench=fillers)
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, card, rand=False, sig=_LSIG,
                                 rng=random.Random(0))
    assert effects == ('char_grant:佩佩(placed=True,merge=0)',)
    assert gs.overflow_warning.value is True, '席满溢出落位(告警在场)'
    assert gs.overflow_card.value == '佩佩', '溢出位身份 = 角色名'
    assert len(bench_units_of(gs)) == 9, '备战席不超容,佩佩在溢出位'
    assert rows_sink.kinds() == [], '席满溢出落位是既定语义,零留证'


def test_strategy_char_grants_consistency_lock() -> None:
    """发放名单单一源一致性测试(箱腿 _STRATEGY_BOX_GRANTS 同构):效果体
    工厂表 _STRATEGY_CHAR_GRANTS 与登记表 STRATEGY_GRANTS 三卡
    chars_immediate 逐对相等(表集同校验,防工厂表扩员而登记面漏登——
    两处独立字面量的名字漂移在备战断言不可见,唯此测试 + 落位真值可
    暴露)。"""
    assert set(_STRATEGY_CHAR_GRANTS) == {'溜佩佩', '溜佩佩+', '招财狗'}
    for name, char in _STRATEGY_CHAR_GRANTS.items():
        assert STRATEGY_GRANTS[name].chars_immediate == (char,), \
            f'{name} 效果体发放名与登记表 chars_immediate 漂移'
