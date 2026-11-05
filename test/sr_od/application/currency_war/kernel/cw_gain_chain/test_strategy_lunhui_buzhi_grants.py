"""轮回不止(id 332201)行为锁(镜像 src = cw_gain_effects.py 的
``_STRATEGY_CHAR_GRANTS`` + ``_make_char_grant_effect`` PICK 推导 +
cw_investments.py 位面开始角色子形专表;先例 = 同目录
test_strategy_char_grant.py 具名角色发放族 + test_strategy_zhongshen_
xuexi.py 位面开始通道姊妹)。

测试面依据 = 卡面官方原文(cw_invest_data.PLAZA_AUGMENTS id 332201:
「获得【白厄】和一件【轮回者】装备。进入第二/三位面时，再获得一次。
本局游戏结束时，【白厄】携带着装备成为新的【轮回者】。若游戏结束时
【白厄】不在队伍中，【轮回者】的装备变为初始状态。」)与在码登记裁定:

- 腿1a:「获得【白厄】」具名直读行骑厂(表 +1 行,PICK 行由生成式注册
  段自动派生),确定发放 rand=False,星级 1 = roster 单位先验;
  效果串 ``char_grant:白厄(placed=…,merge=…,uid=…)`` = 工厂现值形;
- 「一件【轮回者】装备」零建模 = cw_investments.STRATEGY_REINCARNATOR_
  UNMODELED 披露键申报(四面零数据);腿3/腿4 局终域零建模同键覆盖;
- 零效果面:STRATEGY_EFFECTS 恒空 + 商店停机钩子名单零成员(负集合锁,
  防未来误登记)。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    bench_units_of,
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


def _make_gs(*, bench: list[tuple[str, int]] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察;bench 直构槽位 (角色名, 星)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=n, star=s))
                 for n, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    return gs


def test_pick_leg_grants_baie() -> None:
    """腿1a 主锁:on_strategy_gained 直构(rand=False)→ 备战追加恰 1 只
    1★ 白厄、效果串 = 工厂现值形 ``char_grant:白厄(placed=True,merge=0,
    uid=1)``(单发零升星;uid = PICK 具名角色发放族发号纪律,名单全部键
    非本卡特例);落位写 evidence = pick_invest_char_grant#place。"""
    gs = _make_gs(bench=[])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, '轮回不止', rand=False, sig=_LSIG,
                                 rng=random.Random(0))
    assert effects == ('char_grant:白厄(placed=True,merge=0,uid=1)',), \
        f'单发步串: {effects!r}'
    units = bench_units_of(gs)
    assert [(u.char_id, u.star) for u in units] == [('白厄', 1)], \
        '备战追加恰 1 只 1★ 白厄(星级 1 = roster 单位先验)'
    assert all(u.uid is not None for u in units), \
        '发放刻赋实例号(具名角色发放族名单全部键发号纪律)'


def test_pick_leg_grants_baie_on_occupied_bench() -> None:
    """腿1a 非空备战席回归:白厄 ≠ 既有单位同名同星,落位零合成级联
    (互异填席隔离升星判断面,链现役语义本表不特判)。"""
    gs = _make_gs(bench=[('希儿', 1)])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, '轮回不止', rand=False, sig=_LSIG,
                                 rng=random.Random(0))
    assert effects == ('char_grant:白厄(placed=True,merge=0,uid=1)',), \
        f'单发步串: {effects!r}'
    assert [(u.char_id, u.star) for u in bench_units_of(gs)] == [
        ('希儿', 1), ('白厄', 1)], '追加落位零合成'


def test_zero_effect_registration() -> None:
    """零效果锁:STRATEGY_EFFECTS 恒空(卡面经济/战力条目零登记,防未来
    误登记)+ 商店停机钩子名单不含本卡(本卡零商店改写/计数采集面;
    名单访问形 = 类限定 ClassVar)。"""
    assert '轮回不止' not in STRATEGY_EFFECTS, 'STRATEGY_EFFECTS 零登记'
    assert '轮回不止' not in CwScreenPrep._SPEC_INVEST_WATCH_NAMES, \
        '停机钩子名单零成员'


@pytest.mark.parametrize('leg_table', [
    pytest.param('items_immediate', id='items-leg-empty'),
    pytest.param('chars_conditional', id='conditional-leg-empty'),
])
def test_registration_legs_shape(leg_table: str) -> None:
    """登记面腿形锁:STRATEGY_GRANTS 条目 = chars_immediate ('白厄',) 单腿,
    条件集/道具集恒空(重复腿不入条件集,登记裁定在码;轮回者装备腿零
    建模不入 equips——equip 字段校验闸天然拒绝非注册装备名,登记面
    自洽非遗漏)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_GRANTS,
    )
    grant = STRATEGY_GRANTS['轮回不止']
    expected = {'items_immediate': (), 'chars_conditional': ()}[leg_table]
    assert getattr(grant, leg_table) == expected, f'{leg_table} 恒空'
