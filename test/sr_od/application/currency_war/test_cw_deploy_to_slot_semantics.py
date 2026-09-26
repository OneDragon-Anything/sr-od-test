"""落位载荷与执行面锁(P2 拖拽语义落码;载荷契约/拖拽语义/sim 语义)。

设计依据 = docs/develop/sr_od/application/currency_war/changes/
2026-09-20-benchchar-retirement/design.md §2.2(落位决策权归策略层):
- 载荷契约:CwActionDeployMoveParam.to_slot(排内 1 基画面槽号)与 to_row
  合成完整落位意图;执行链与容器写侧均禁首空位现读,按载荷直落;
- 拖拽语义 = 游戏规则:目标槽空 = 放置,有人 = 交换交互;执行层不判断
  占位、不拒、禁静默换槽;
- sim 语义:引擎忠实建模游戏拖拽语义,禁发明私有「占位拒绝」规则。

锁面:
① 载荷 (to_row, to_slot) 直落 = 参数指定槽(反「首空」证据:存在更低位
   空槽仍落载荷指定槽),写侧与执行链 tracked 同规则;
② 容器写侧落位与执行拖点同源——同一载荷下,写侧落表下标 = 执行 tracked
   写入下标 = 拖点 area 序(to_slot−1),换算单一源 = deployed_idx_of;
③ 目标槽有人 = 交换(被占位角色回发射者源 bench 槽,与
   CwActionSwapDeployParam 换位契约同语义),sim 应用与执行链均不拒。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
    deployed_indexed_of_view,
)


import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_deploy_move_param,
)
from sr_od.application.currency_war.kernel.cw_exec_state import (
    DEPLOYED_CAPACITY,
    deployed_idx_of,
    deployed_rows_to_indexed,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    ChannelSig,
    GameState,
    Unit,
    bench_view_slots_of,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionDeployMoveParam,
    mutate_bench_deployed,
)
from sr_od.application.currency_war.operations.cw_op.cw_deploy_move_action import (
    CwActionDeployMoveOp,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='CwScreenPrep')


def _gs(*, bench: list[BenchSlot | None] | None = None,
        front: list[Unit] | None = None,
        back: list[Unit] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        from sr_od.application.currency_war.kernel.cw_game_state import (
            BenchView,
        )
        slots = list(bench) + [BenchSlot(kind='empty')] * (9 - len(bench))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if front is not None or back is not None:
        gs.observe(gs.deployed, _dvs(list(front or []),
                                     list(back or [])), sig=_SIG_OBS)
    return gs


def _unit(cid: str, slot: int, star: int = 1) -> Unit:
    return Unit(char_id=cid, star=star, equips=[])


# ===== ① 写侧:载荷直落,非首空 =====

def test_write_side_lands_at_payload_slot_not_first_empty():
    """反「首空」证据:前排 2 号空、载荷指 3 号 → 落 3 号,2 号保持空
    (首空位现读若在,会落 2 号)。"""
    gs = _gs(bench=[BenchSlot(kind='unit', unit=_unit('甲', 1))],
             front=[_unit('乙', 1)])
    out = report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='front', to_slot=3,
                                    faction=''),
        sig=_SIG_LOGIC)
    assert out.applied, f'应按载荷直落,实得 {out.reason!r}'
    dep = deployed_indexed_of_view(gs.deployed.value)
    assert dep[2] is not None and dep[2].char_id == '甲', \
        '落位 = 载荷指定槽(表下标 2)'
    assert dep[1] is None, '更低位的空槽(2 号)不被静默填充(禁首空位现读)'
    _s0 = bench_view_slots_of(gs)[0]
    assert _s0 is None or _s0.kind == 'empty', '源槽摘除'


def test_write_side_rejects_invalid_payload_slot_zero_write():
    """载荷槽非法(前排无 5 号 / 后排 7 号越出定长表)= 零写,源槽不摘
    (陈旧载荷;执行层唯一失败形态 = 拖拽未生效,拒绝面只在载荷静态域)。"""
    gs = _gs(bench=[BenchSlot(kind='unit', unit=_unit('甲', 1))],
             front=[_unit('乙', 1)])
    for row, slot in (('front', 5), ('back', 7)):
        before = gs.write_seq
        out = report_action_deploy_move_param(
            gs, CwActionDeployMoveParam(bench_idx=0, to_row=row, to_slot=slot,
                                        faction=''),
            sig=_SIG_LOGIC)
        assert not out.applied and out.reason.startswith('to_slot_invalid')
        assert gs.write_seq == before, '载荷槽非法 = 整笔零写'


# ===== ② 执行链:拖点与 tracked 同落载荷槽(与写侧同源)=====

def _deploy_op_env(session: object, drags: list[dict]):
    """DeployMoveOp 离线执行环境(坐标注入;drag_to kwargs 全录)。"""
    from sr_od.application.currency_war import prep_actions as pa
    controller = type('_Ctl', (), {
        'mouse_move': lambda self, p: None,
        'drag_to': lambda self, **kw: drags.append(kw),
    })()
    sl = type('_SL', (), {'get_screen': lambda self, n: None})()
    op = type('_Op', (), {
        'screenshot': staticmethod(lambda: None),
        'park_cursor': staticmethod(lambda **kw: None),
        'ctx': type('_Ctx', (), {
            'controller': controller,
            'cw_match': (None if session is None
                         else type('_M', (), {'session': session})()),
            'run_context': None,
            'screen_loader': sl,
        })(),
    })()
    ctx = op.ctx
    ex = pa.PrepActionExecutor(op, ctx)
    ex._bench_pts = [Point(300, 800)] * 9
    ex._front_pts = [Point(300 + i * 140, 400) for i in range(4)]
    ex._back_pts = [Point(300 + i * 140, 620) for i in range(6)]
    env = pa.PrepExecEnv(op=op, match=ctx.cw_match, executor=ex)
    return env


def test_executor_drag_point_and_tracked_lands_at_payload_slot(
        monkeypatch: pytest.MonkeyPatch):
    """执行链同源锁:载荷 (back, 3) → 拖点 = 后排 area 序 3−1;
    tracked 写入下标 = deployed_idx_of(同换算单一源,与容器写侧同式)。
    后排 1 号已有占位乙(更低位占用不影响),载荷槽 3 空 = 放置。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    session = StrategySession()
    gs = game_state_of(session)
    gs.tracked_books.bench = [BenchSlot(kind='unit',
                                        unit=Unit(char_id='甲', star=1))]
    dep = [None] * DEPLOYED_CAPACITY
    dep[deployed_idx_of('back', 1)] = Unit(char_id='乙', star=1, equips=[])
    gs.tracked_books.deployed = dep
    drags: list[dict] = []
    env = _deploy_op_env(session, drags)
    action = CwActionDeployMoveParam(bench_idx=0, to_row='back', to_slot=3,
                                     faction='')
    ok = CwActionDeployMoveOp(env.op.ctx, action, env=env).run()
    assert ok.is_success, '载荷槽合法 = 机械发出(占位只看载荷槽,不拒)'
    assert len(drags) == 1 and drags[0]['end'] == env.executor._back_pts[2], \
        '拖点 = 载荷槽 area 序(to_slot−1),与写侧同源'
    dep_after = list(gs.tracked_books.deployed)
    assert dep_after[deployed_idx_of('back', 3)] is not None \
        and dep_after[deployed_idx_of('back', 3)].char_id == '甲', \
        'tracked 落载荷槽(换算单一源 = deployed_idx_of)'
    assert dep_after[deployed_idx_of('back', 1)].char_id == '乙', \
        '既有占位不受放置波及(禁静默换槽)'
    assert gs.tracked_books.bench[0] is None, 'bench 侧摘除照旧'


def test_executor_occupied_target_swaps_without_rejection(
        monkeypatch: pytest.MonkeyPatch):
    """拖拽语义:载荷槽有人 = 交换交互——执行层不判断占位、不拒
    (round_success 照常发出);tracked 镜像:上场者落载荷槽、被占位者
    回源 bench 槽。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    session = StrategySession()
    gs = game_state_of(session)
    gs.tracked_books.bench = [BenchSlot(kind='unit',
                                        unit=Unit(char_id='甲', star=1))]
    dep = [None] * DEPLOYED_CAPACITY
    dep[deployed_idx_of('front', 2)] = Unit(char_id='乙', star=2, equips=[])
    gs.tracked_books.deployed = dep
    drags: list[dict] = []
    env = _deploy_op_env(session, drags)
    action = CwActionDeployMoveParam(bench_idx=0, to_row='front', to_slot=2,
                                     faction='')
    ok = CwActionDeployMoveOp(env.op.ctx, action, env=env).run()
    assert ok.is_success, '目标槽有人 = 交换交互,不视为异常、不拒'
    dep_after = list(gs.tracked_books.deployed)
    assert dep_after[deployed_idx_of('front', 2)].char_id == '甲', \
        '上场者落被占位载荷槽'
    _src = gs.tracked_books.bench[0]
    assert _src is not None and _src.kind == 'unit' \
        and _src.unit.char_id == '乙', \
        '被占位者回发射者源 bench 槽(交换契约,装备随单位对象)'


def test_executor_rejects_slot_beyond_screen_points_no_drag(
        monkeypatch: pytest.MonkeyPatch):
    """载荷槽越出画面槽位数(back 7 > 6 槽)= 陈旧载荷未发出
    (round_fail),零拖拽零 tracked 写(观察重派)。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    session = StrategySession()
    gs = game_state_of(session)
    gs.tracked_books.bench = [BenchSlot(kind='unit',
                                        unit=Unit(char_id='甲', star=1))]
    gs.tracked_books.deployed = [None] * DEPLOYED_CAPACITY
    drags: list[dict] = []
    env = _deploy_op_env(session, drags)
    action = CwActionDeployMoveParam(bench_idx=0, to_row='back', to_slot=7,
                                     faction='')
    ok = CwActionDeployMoveOp(env.op.ctx, action, env=env).run()
    assert not ok.is_success and drags == [], '越界载荷未发出'
    assert gs.tracked_books.bench[0] is not None, 'tracked 整笔未写'


# ===== ③ sim 应用:目标槽有人 = 交换语义 =====

def test_sim_applies_occupied_target_as_swap():
    """部署上报(动作腿单一源)对「目标槽有人」按交换建模:上场者落
    载荷槽、被占位角色回发射者源 bench 槽(经上报函数,零私有占位规则)。"""
    gs = _gs(bench=[BenchSlot(kind='unit', unit=_unit('甲', 1))],
             front=[_unit('乙', 1)])
    report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='front', to_slot=1,
                                    faction=''),
        _SIG_LOGIC)
    assert gs.deployed.value.front_slots[0].char_id == '甲', '上场者落载荷槽'
    slot = gs.bench.value.slots[0]
    assert slot.kind == 'unit' and slot.unit.char_id == '乙', \
        '被占位角色回源 bench 槽(交换语义,非占位拒绝)'


def test_sim_applies_empty_target_as_place():
    """对照腿:载荷槽空 = 放置(上报函数与写侧同一转移函数)。"""
    gs = _gs(bench=[BenchSlot(kind='unit', unit=_unit('甲', 1))],
             front=[], back=[])
    report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='back', to_slot=4,
                                    faction=''),
        _SIG_LOGIC)
    assert gs.deployed.value.back_slots[3].char_id == '甲', '空槽 = 放置(载荷槽 4)'


# ===== tracked 同步口(mutate_bench_deployed 部署分支)同规则 =====

def test_mutate_bench_deployed_deploy_branch_payload_direct():
    """tracked 同步口部署分支同吃载荷契约:载荷直落 + 有人 = 交换;
    载荷槽非法 = 整笔不写(bench 摘除也不做)。"""
    bench: list[BenchSlot | None] = [BenchSlot(kind='unit',
                                               unit=_unit('甲', 1))]
    dep: list[Unit | None] = [None] * DEPLOYED_CAPACITY
    dep[deployed_idx_of('back', 3)] = _unit('乙', 3)
    mutate_bench_deployed(
        bench, dep,
        CwActionDeployMoveParam(bench_idx=0, to_row='back', to_slot=3,
                                faction=''))
    assert dep[deployed_idx_of('back', 3)].char_id == '甲', '载荷直落'
    assert bench[0].kind == 'unit' and bench[0].unit.char_id == '乙', \
        '被占位者回源 bench 槽'
    # 载荷槽非法(后排 7 号越出定长表)= 整笔不写
    bench2: list[BenchSlot | None] = [BenchSlot(kind='unit',
                                                unit=_unit('甲', 1))]
    dep2: list[Unit | None] = [None] * DEPLOYED_CAPACITY
    mutate_bench_deployed(
        bench2, dep2,
        CwActionDeployMoveParam(bench_idx=0, to_row='back', to_slot=7,
                                faction=''))
    assert bench2[0] is not None and bench2[0].unit.char_id == '甲', \
        '载荷槽非法 = bench 摘除也不做'
    assert all(d is None for d in dep2), 'deployed 零写'
