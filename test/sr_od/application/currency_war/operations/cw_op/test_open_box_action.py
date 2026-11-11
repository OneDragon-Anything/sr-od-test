"""货币战争 OpenBox 动作 op 单帧测试(状态容器槽位直点形态)。

形态依据 = 原稿锁面§2.5(机械链 =
参数校验 → 槽号解析 → 建档坐标直查 → mouse_move+click → 自上报 →
round_success;op 对画面零识别,识别读门随批拆除):slot = 画面物理槽
1 基,None = op 内按 game state 状态容器现算首件槽(与决策层 mandate_v1
entry 消耗品臂 / 上报层同型现算,双出口守卫断言 = gs 缺席 / 状态容器无该
kind 首槽);点击点 = 「武装箱开启位-{slot}」建档 area 中心(「点哪能开」
实测定准进建档,原 +41px 代码魔法数随批退役进建档)。

测试面(原稿锁面 测试条):slot 显式/None 现算两态 → 建档坐标点击 +
自上报(box_card 登记 + 声明喂入)+ success;slot 越界 AssertionError;
None 现算双出口各一条 AssertionError;sim 形态 = 机械分支旁路静默成功
+ 后端状态副本推进(advance 收到 open_box 声明)。
开箱上报 = 零写族(腾席事实归下一入口 heavy 实读),状态容器 bench 零写
是非本测断言面(权威版本 = test_overlay 零写族覆盖)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.rectangle import Rect
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    consume_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionOpenBoxParam,
)
from sr_od.application.currency_war.operations.cw_op.cw_open_box_action import (
    CwActionOpenBoxOp,
)
from sr_od.application.currency_war.prep_actions import PrepExecEnv

_SIG_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')


@pytest.fixture(autouse=True)
def _drain_defect_buffer():
    consume_defect_sink()
    yield
    consume_defect_sink()


class _RecordingController:
    """点击记录桩(None 坐标解引用即炸 = 零防御自然失败形态)。"""

    def __init__(self) -> None:
        self.moves: list[tuple[int, int]] = []
        self.clicks: list[tuple[int, int]] = []

    def mouse_move(self, pt) -> None:
        self.moves.append((pt.x, pt.y))

    def click(self, pt) -> None:
        self.clicks.append((pt.x, pt.y))


def _box_screen_loader():
    """screen_loader 桩:武装箱开启位-1..9 假画面档(建档坐标 = 真实
    Rect,中心 = slot N 开启点击点断言面;slot N 中心 = (125 + N*10, 900))。"""

    class _Screen:
        area_list = [SimpleNamespace(
            area_name=f'武装箱开启位-{i}',
            pc_rect=Rect(100 + i * 10, 860, 150 + i * 10, 940))
            for i in range(1, 10)]

    return SimpleNamespace(get_screen=lambda name: _Screen())


def _box_env(monkeypatch):
    """OpenBoxOp 离线执行环境(gs 装配于 test_context.cw_match,调用方
    先 monkeypatch);控制器记点击;time.sleep 桩(固定等待零耗时)。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)

    class _Op:
        ctx = SimpleNamespace(controller=_RecordingController(),
                              screen_loader=_box_screen_loader())

    from sr_od.application.currency_war import prep_actions as pa
    ex = pa.PrepActionExecutor(_Op(), _Op.ctx)
    # 槽位表种子(screen_loader 桩读不到 row_area_centers 的建档 → 空表):
    # op 内 slot 守卫按真执行器形状(备战栏 9)判合法域,空表会让合法
    # 槽位误炸——机械 fixture 数据,非断言面。
    from one_dragon.base.geometry.point import Point
    ex._bench_pts = [Point(i * 10, i * 10) for i in range(9)]
    return PrepExecEnv(op=_Op(), match=None, executor=ex)


def _env_controller(env) -> _RecordingController:
    return env.executor._ctx.controller


def _seed_bench(gs, slots: list[BenchSlot]) -> None:
    _slots = list(slots) + [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.observe(gs.bench, BenchView(slots=_slots, capacity=9), sig=_SIG_OBS)


def _run(test_context, op):
    from test.sr_od.application.currency_war._cw_helpers import run_node
    return run_node(test_context, op, lambda: CwActionOpenBoxOp.run(op))


def test_explicit_slot_clicks_open_area_and_declares_world(
        test_context, monkeypatch):
    """slot 显式(原稿锁面):单击落「武装箱开启位-N」建档中心 →
    自上报(box_card 点击直弹登记 + 后果声明随 round data 携带)→
    success。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    session = StrategySession()
    gs = game_state_of(session)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    _seed_bench(gs, [BenchSlot(kind='supply_box')])

    env = _box_env(monkeypatch)
    op = CwActionOpenBoxOp(test_context, CwActionOpenBoxParam(slot=1),
                           env=env)
    rr = _run(test_context, op)
    assert rr.is_success and rr.status == '开箱槽1', '机械执行成功 + 摘要显示槽号'
    assert _env_controller(env).clicks == [(135, 900)], \
        '点击落武装箱开启位建档坐标中心'
    assert len(_env_controller(env).moves) == 1, '防吞点击:先移后点'
    assert [p.kind for p in gs.screen_changes.pending] == ['box_card'], \
        '点击直弹已登记(武装箱选择画面出现事实)'
    assert rr.data is not None, '后果声明随 round data 携带(journal 记账面)'


def test_none_slot_resolves_first_box_and_rebuilds_param(
        test_context, monkeypatch):
    """slot=None 现算(原稿锁面§2.5):gs 状态容器现算首个 supply_box 槽
    (下标+1)→ resolved slot 重建 param(入参对象不改写)→ 点击落现算
    槽建档坐标、round 摘要显示显式槽号。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    session = StrategySession()
    gs = game_state_of(session)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    _seed_bench(gs, [BenchSlot(kind='unit'), BenchSlot(kind='unit'),
                     BenchSlot(kind='unit'), BenchSlot(kind='unit'),
                     BenchSlot(kind='supply_box')])

    env = _box_env(monkeypatch)
    param_in = CwActionOpenBoxParam(slot=None)
    op = CwActionOpenBoxOp(test_context, param_in, env=env)
    rr = _run(test_context, op)
    assert rr.is_success and rr.status == '开箱槽5', \
        '现算首件槽 = 状态容器下标+1,round 摘要显示'
    assert param_in.slot is None, '落地机制 = resolved slot 重建 param,不改写入参对象'
    assert _env_controller(env).clicks == [(175, 900)], '点击落现算槽建档坐标'


def test_slot_out_of_range_guard_loud_zero_click(test_context, monkeypatch):
    """slot 越界(原稿锁面 校验落点契约):守卫断言响亮暴露零点击。"""
    env = _box_env(monkeypatch)
    op = CwActionOpenBoxOp(test_context, CwActionOpenBoxParam(slot=10),
                           env=env)
    with pytest.raises(AssertionError) as ei:
        CwActionOpenBoxOp.run(op)
    assert '越界' in str(ei.value), '守卫断言消息带越界形态'
    assert _env_controller(env).clicks == [], '零点击'


def test_none_slot_double_exit_guards_loud_zero_click(
        test_context, monkeypatch):
    """None 现算双出口守卫(原稿锁面 各一条 AssertionError):gs 为
    None / 状态容器无 supply_box 首件槽,均响亮暴露零点击(现算不出槽 =
    决策数据缺席,不做兜底识别)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    # 出口 1:gs 为 None(无局/状态容器供给 None)
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    env = _box_env(monkeypatch)
    op = CwActionOpenBoxOp(test_context, CwActionOpenBoxParam(slot=None),
                           env=env)
    with pytest.raises(AssertionError) as ei:
        CwActionOpenBoxOp.run(op)
    assert 'game state' in str(ei.value), '出口 1 消息指向 gs 缺席'
    assert _env_controller(env).clicks == [], '零点击'

    # 出口 2:状态容器无 supply_box 首件槽(bench 全空)
    session2 = StrategySession()
    gs2 = game_state_of(session2)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session2), raising=False)
    _seed_bench(gs2, [])
    env2 = _box_env(monkeypatch)
    op2 = CwActionOpenBoxOp(test_context, CwActionOpenBoxParam(slot=None),
                            env=env2)
    with pytest.raises(AssertionError) as ei2:
        CwActionOpenBoxOp.run(op2)
    assert 'kind=supply_box' in str(ei2.value), '出口 2 消息指向状态容器无首件槽'
    assert _env_controller(env2).clicks == [], '零点击'


def test_sim_form_silent_bypass_and_backend_world_advance(
        test_context, monkeypatch):
    """sim 形态(原稿锁面):机械分支旁路静默成功(零点击零移动),
    自上报照走(box_card 登记),后果声明经 declare_world 喂入后端
    advance(trigger = open_box)——sim 后端状态副本建模由此真正收到上报。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    from sr_od.application.currency_war.sim import cw_sim_ports

    class _Backend:
        """占位后端:advance 记录;其余端口触达即炸(本动作在 sim 分支
        不触后端读口)。"""

        def __init__(self) -> None:
            self.advances: list = []

        def screen_identity(self) -> str:
            raise AssertionError('OpenBox 不得触后端读口')

        def observe(self, screen_name: str) -> object:
            raise AssertionError('OpenBox 不得触后端观察')

        def visible(self, screen_name: str, area_name: str) -> bool:
            raise AssertionError('OpenBox 不得触后端门问询')

        def click_answer(self, *a) -> object:
            raise AssertionError('OpenBox 点击分支不经直调触后端')

        def advance(self, decl) -> None:
            self.advances.append(decl)

    backend = _Backend()
    cw_sim_ports.install_sim_backend(backend)
    try:
        session = StrategySession()
        gs = game_state_of(session)
        monkeypatch.setattr(test_context, 'cw_match',
                            SimpleNamespace(session=session), raising=False)
        _seed_bench(gs, [BenchSlot(kind='supply_box')])
        env = _box_env(monkeypatch)
        op = CwActionOpenBoxOp(test_context, CwActionOpenBoxParam(slot=1),
                               env=env)
        rr = _run(test_context, op)
        assert rr.is_success, 'sim 旁路静默成功'
        assert _env_controller(env).clicks == [] \
            and _env_controller(env).moves == [], '机械 IO 零触达'
        assert [p.kind for p in gs.screen_changes.pending] == ['box_card'], \
            '武装箱选择画面呈现登记照走'
        assert len(backend.advances) == 1 \
            and backend.advances[0].trigger == 'open_box', \
            '后果声明喂入后端 advance(状态副本推进主通道)'
    finally:
        cw_sim_ports.uninstall_sim_backend()
