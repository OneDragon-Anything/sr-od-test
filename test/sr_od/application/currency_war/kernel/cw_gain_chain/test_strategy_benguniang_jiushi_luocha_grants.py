"""本姑娘就是罗刹(id 352501)行为锁(镜像 src = cw_gain_effects.py 的
``_STRATEGY_CHAR_GRANTS`` 行 + ``_make_char_grant_effect`` 星级扩展 +
PICK 推导 + ``_STRATEGY_NODE_CHAR_GRANTS`` 具名固定子形姊妹专表;先例 =
同目录 test_strategy_lunhui_buzhi_grants.py 轮回不止同卡两表形态)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-408-benguniang-jiushi-luocha.md(定稿 v1.1)§4 锁 1/2:

- 腿1(即时 2★三月七):首句「获得2星【三月七】」即时直读行骑厂(表
  +1 行,PICK 行由生成式注册段自动派生,禁字面量第二源),确定发放
  rand=False,星级 2 = desc 明写结构值直读非先验;效果串
  ``char_grant:三月七(placed=…,merge=…,uid=…)`` = 工厂现值形;2★ 直授
  不与 1★ 存量合并(合并判据 = 同名同星,星级不同不触发,链现役语义);
- 腿2(每节点 1★三月七)行为真值 = 检查函数具名形分支,归同目录
  test_check_strategy_node_char_grants.py 函数镜像文件(本文件只辖登记
  行值对拍);两腿零 rng 确定发放;
- 腿3(化身罗刹+战斗行为)零建模五证 = U01 sim 战斗纯随机面/BattleOutcome
  无行为真值/收入统一公式无接口/变身非发放不入册(登记面注释在码)/
  live 游戏自算零义务——本文件零效果锁钉 STRATEGY_EFFECTS 恒空。
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
    _STRATEGY_NODE_CHAR_GRANTS,
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
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '本姑娘就是罗刹'


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


def test_registration_faces() -> None:
    """登记面锁(锁 1):登记表 chars_immediate = ('三月七',) 单腿白得型
    (advisor False 非顾问入商店)/工厂表行 ('三月七', 1, 2)(2★ = desc
    明写直读,家族首个非 1 星级行)/姊妹专表行 ('三月七', 1)(每节点名数
    = 卡面单数直读)/PICK 行在册(生成式注册段自工厂表派生,表为单一源,
    禁字面量第二源)。"""
    grant = STRATEGY_GRANTS[_CARD]
    assert grant.chars_immediate == ('三月七',), '登记面 = 即时单腿名级'
    assert grant.advisor is False, '白得型直接送卡,非顾问入商店'
    assert _STRATEGY_CHAR_GRANTS[_CARD] == ('三月七', 1, 2), \
        '工厂表行值 = (三月七, 1, 2★ 直读)'
    assert _STRATEGY_NODE_CHAR_GRANTS[_CARD] == ('三月七', 1), \
        '姊妹专表行值 = (三月七, 每节点 1 名)'
    assert _CARD in PICK_INVEST_EFFECTS, '世界发放腿注册在册'


def test_pick_leg_grants_two_star_march(rows_sink: _RowSink) -> None:
    """腿1 世界锁(锁 2):on_strategy_gained 直构(rand=False)→ 备战追加
    恰 1 只 2★ 三月七、效果串 = 工厂现值形 ``char_grant:三月七(placed=
    True,merge=0,uid=1)``(单发零升星);确定发放走确定面;正常路径零
    申报行。"""
    gs = _make_gs(bench=[])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=random.Random(0))
    assert effects == ('char_grant:三月七(placed=True,merge=0,uid=1)',), \
        f'单发步串: {effects!r}'
    units = bench_units_of(gs)
    assert [(u.char_id, u.star) for u in units] == [('三月七', 2)], \
        '备战追加恰 1 只 2★ 三月七(星级 = desc「2星」直读)'
    assert all(u.uid is not None for u in units), \
        '发放刻赋实例号(具名角色发放族名单全部键发号纪律)'
    assert gs.bench.source == 'logic', '确定发放走确定面'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_pick_leg_no_merge_with_one_star_copy(rows_sink: _RowSink) -> None:
    """腿1 非空备战席回归(锁 2 后半):预置 1★ 三月七 → 2★ 直授零合并
    (合并判据 = 同名同星,星级不同不触发,链现役语义)——升星只走同名
    同星凑三通道,即时 2★ 与每节点 1★ 复制腿并存是设计语义非缺口。"""
    gs = _make_gs(bench=[('三月七', 1)])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=random.Random(0))
    assert effects == ('char_grant:三月七(placed=True,merge=0,uid=1)',), \
        f'单发步串: {effects!r}'
    assert [(u.char_id, u.star) for u in bench_units_of(gs)] == [
        ('三月七', 1), ('三月七', 2)], '2★ 直授零合并,两档并存'
    assert rows_sink.kinds() == [], '零申报行'


def test_zero_effect_registration() -> None:
    """零效果锁(腿3 零建模面钉):STRATEGY_EFFECTS 恒空(卡面经济/战力
    条目零登记,变身+战斗行为 = sim 域结构外,防未来误登记)+ 商店停机
    钩子名单不含本卡(零商店改写/计数采集面;名单访问形 = 类限定
    ClassVar)。"""
    assert _CARD not in STRATEGY_EFFECTS, 'STRATEGY_EFFECTS 零登记'
    assert _CARD not in CwScreenPrep._SPEC_INVEST_WATCH_NAMES, \
        '停机钩子名单零成员'
