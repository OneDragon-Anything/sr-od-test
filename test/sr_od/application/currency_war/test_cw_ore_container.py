"""晶矿容器化三锁(迭代 2026-09-18-prep-obs-retirement 阶段 3.4/T-4)。

晶矿决策输入换容器 spheres 域(OreSight.points 载荷坐标;旧黑板
``obs.spheres`` 读点清零)——锁:
- 读口还原:``ore_click_targets_of`` 把 OreSight.points 还原为
  ``(color, Point, r)`` 消费形态(select_ore_clicks 契约);
- CwActionCollectOreParam 容器逻辑态:载荷坐标精确摘除(上报函数
  report_action_collect_ore_param,原黑板腿逐位迁移);域未观察/
  载荷无交集 = 零写;
- 签名换源:``_ore_progress_sig`` 席/晶矿计数分量来自容器派生。
"""
from test.sr_od.application.currency_war._cw_helpers import cw4_session

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_collect_ore_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    OreSight,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    ore_click_targets_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import CwActionCollectOreParam

_SIG = ChannelSig(family='obs', actor='cw4_seed',
                  mode='synthesized')
_LOGIC_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')


def _write_spheres(session, points: tuple) -> None:
    """按容器域形态写 spheres(观察写端同款 OreSight 载荷)。"""
    gs = game_state_of(session)
    gs.observe(gs.spheres, OreSight(
        count=len(points),
        colors=tuple(dict.fromkeys(p[0] for p in points)),
        points=points), sig=_SIG)


def test_ore_click_targets_roundtrip():
    """读口还原:(color,x,y,r) 平铺 → (color, Point, r) 形态逐项对应。"""
    session = cw4_session()
    gs = game_state_of(session)
    _write_spheres(session, (('gold', 100, 200, 30), ('blue', 300, 400, 20)))
    targets = ore_click_targets_of(gs)
    assert [(c, p.x, p.y, r) for c, p, r in targets] == \
        [('gold', 100, 200, 30), ('blue', 300, 400, 20)]


def test_collect_ore_container_precise_drop():
    """容器逻辑态:CwActionCollectOreParam 载荷坐标精确摘除(未被点的晶矿保留);
    count/colors 随载荷同步重算。(logic-rand-sampling 迭代:摘除写改
    随机态,bench/level 前置守卫在册——未观察整批拒。)"""
    session = cw4_session()
    gs = game_state_of(session)
    _write_spheres(session, (('gold', 100, 200, 30), ('blue', 300, 400, 20)))
    from sr_od.application.currency_war.kernel.cw_game_state import (
        BenchSlot,
        BenchView,
    )

    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='empty') for _ in range(9)], capacity=9),
        sig=_SIG)
    gs.observe(gs.level, 5, sig=_SIG)
    report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((300, 400),)), sig=_LOGIC_SIG)
    view = gs.spheres.value
    assert view.points == (('gold', 100, 200, 30),)
    assert view.count == 1 and view.colors == ('gold',)
    assert gs.spheres.source == 'logic_rand', '摘除写属采样世界(随机态)'


def test_collect_ore_stale_payload_zero_write():
    """陈旧提案守卫:载荷与容器现值无交集(晶矿已被观察回补) → 零写。"""
    session = cw4_session()
    gs = game_state_of(session)
    _write_spheres(session, (('gold', 100, 200, 30),))
    report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=((999, 999),)), sig=_LOGIC_SIG)
    assert gs.spheres.value.points == (('gold', 100, 200, 30),)


def test_ore_empty_read_yields_no_targets():
    """空读上报语义锁(reviewer r1 打回项1):count=0/points=() 空载荷
    → 读口空列——空读照写语义兑现,防上一帧残留假晶矿坐标喂进点击载荷。"""
    session = cw4_session()
    gs = game_state_of(session)
    _write_spheres(session, ())
    assert ore_click_targets_of(gs) == []
