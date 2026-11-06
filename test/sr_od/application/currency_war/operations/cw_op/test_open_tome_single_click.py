"""货币战争 OpenTome 动作 op 单帧测试(状态容器槽位直点形态)。

形态依据 = open-actions-mechanical-pure design §2.1/§2.5(机械链 =
参数校验 → 槽号解析 → 建档坐标直查 → mouse_move+click → 自上报 →
round_success;op 对画面零识别,识别读门随批拆除):slot = 画面物理槽
1 基,None = op 内按 game state 状态容器现算首件槽(与决策层 mandate_v1
entry 消耗品臂 / 上报层 open_tome 同型现算,双出口守卫断言 = gs 缺席 /
状态容器无该 kind 首槽)。单击化依据 = 用户确认 2026-09-25 游戏实际 =
点典籍槽一次即弹星徽四选一(原双击序列第二击有误触风险;实机核凭据 =
待实机局 journal)。

测试面(design §2.5 测试条):slot 显式/None 现算两态 → 建档坐标点击 +
自上报腾席 + star_tome 登记 + success;slot 越界 AssertionError;None
现算双出口各一条 AssertionError;sim 形态 = 机械分支旁路静默成功 +
自上报状态容器推进(典籍上报无转移声明,零 advance 喂入)。
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
    CwActionOpenTomeParam,
)
from sr_od.application.currency_war.operations.cw_op.cw_open_tome_action import (
    CwActionOpenTomeOp,
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


def _bench_screen_loader():
    """screen_loader 桩:备战栏-1..9 假画面档(建档坐标 = 真实 Rect,
    中心 = slot N 点击点断言面;slot N 中心 = (125 + N*10, 912))。"""

    class _Screen:
        area_list = [SimpleNamespace(
            area_name=f'备战栏-{i}',
            pc_rect=Rect(100 + i * 10, 845, 150 + i * 10, 979))
            for i in range(1, 10)]

    return SimpleNamespace(get_screen=lambda name: _Screen())


def _tome_env(session, monkeypatch):
    """OpenTomeOp 离线执行环境:gs 装配于 test_context.cw_match(调用方
    先 monkeypatch),控制器记点击;time.sleep 桩(固定等待零耗时)。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)

    class _Op:
        ctx = SimpleNamespace(controller=_RecordingController(),
                              screen_loader=_bench_screen_loader())

    from sr_od.application.currency_war import prep_actions as pa
    ex = pa.PrepActionExecutor(_Op(), _Op.ctx)
    # 槽位表种子(screen_loader 桩读不到 row_area_centers 的建档 → 空表):
    # op 内 slot 守卫按真执行器形状(备战栏 9)判合法域,空表会让合法
    # 槽位误炸——机械 fixture 数据,非断言面。
    from one_dragon.base.geometry.point import Point
    ex._bench_pts = [Point(i * 10, i * 10) for i in range(9)]
    return PrepExecEnv(op=_Op(), match=SimpleNamespace(session=session),
                       executor=ex)


def _env_controller(env) -> _RecordingController:
    return env.executor._ctx.controller


def _seed_bench(gs, slots: list[BenchSlot]) -> None:
    _slots = list(slots) + [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.observe(gs.bench, BenchView(slots=_slots, capacity=9), sig=_SIG_OBS)


def _make_op(test_context, env, param) -> CwActionOpenTomeOp:
    return CwActionOpenTomeOp(test_context, param, env=env)


def _run(test_context, op):
    from test.sr_od.application.currency_war._cw_helpers import run_node
    return run_node(test_context, op, lambda: CwActionOpenTomeOp.run(op))


def test_explicit_slot_single_clicks_bench_center_and_reports(
        test_context, monkeypatch):
    """slot 显式(design §2.5):恰一次单击落备战栏-N 中心(单击化,无
    第二击)→ 自上报腾席 + star_tome 登记 → success。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    session = StrategySession()
    gs = game_state_of(session)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    _seed_bench(gs, [BenchSlot(kind='empty'), BenchSlot(kind='tome')])

    env = _tome_env(session, monkeypatch)
    op = _make_op(test_context, env, CwActionOpenTomeParam(slot=2))
    rr = _run(test_context, op)
    assert rr.is_success, '单击开典籍成功(选中即开启)'
    assert rr.status == '开典籍槽2', 'round 摘要显示显式槽号'
    assert _env_controller(env).clicks == [(145, 912)], \
        '恰一次点击落备战栏建档坐标中心(双击序列已退役)'
    assert len(_env_controller(env).moves) == 1, '防吞点击:先移后点'
    assert gs.bench.value.slots[1].kind == 'empty', '开件腾席落账'
    assert [p.kind for p in gs.screen_changes.pending] == ['star_tome'], \
        'star_tome 已登记'


def test_none_slot_resolves_first_tome_and_rebuilds_param(
        test_context, monkeypatch):
    """slot=None 现算(design §2.1-1/§2.5):gs 状态容器现算首件槽(与决策层
    同源同规则,下标+1)→ resolved slot 重建 param(入参对象不改写,
    journal/上报显示显式槽号)→ 点击落现算槽、上报按显式槽腾席。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    session = StrategySession()
    gs = game_state_of(session)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    _seed_bench(gs, [BenchSlot(kind='empty'), BenchSlot(kind='empty'),
                     BenchSlot(kind='tome')])

    env = _tome_env(session, monkeypatch)
    param_in = CwActionOpenTomeParam(slot=None)
    op = _make_op(test_context, env, param_in)
    rr = _run(test_context, op)
    assert rr.is_success and rr.status == '开典籍槽3', \
        '现算首件槽 = 状态容器下标+1,round 摘要显示'
    assert param_in.slot is None, '落地机制 = resolved slot 重建 param,不改写入参对象'
    assert _env_controller(env).clicks == [(155, 912)], '点击落现算槽建档坐标'
    assert gs.bench.value.slots[2].kind == 'empty', '上报按显式槽腾席'


def test_slot_out_of_range_guard_loud_zero_click(test_context, monkeypatch):
    """slot 越界(design §2.1-1 校验落点契约):守卫断言响亮暴露零点击
    (参数违法由 op 自判,不产生任何机械 IO)。"""
    env = _tome_env(StrategySession(), monkeypatch)
    op = _make_op(test_context, env, CwActionOpenTomeParam(slot=10))
    with pytest.raises(AssertionError) as ei:
        CwActionOpenTomeOp.run(op)
    assert '越界' in str(ei.value), '守卫断言消息带越界形态'
    assert _env_controller(env).clicks == [], '零点击'


def test_none_slot_double_exit_guards_loud_zero_click(
        test_context, monkeypatch):
    """None 现算双出口守卫(design §2.5 各一条 AssertionError):gs 为
    None / 状态容器无该 kind 首件槽,均响亮暴露零点击(与越界同款,零防御
    哲学:现算不出槽 = 决策数据缺席,不做兜底识别)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    # 出口 1:gs 为 None(无局/状态容器供给 None)
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    env = _tome_env(StrategySession(), monkeypatch)
    op = _make_op(test_context, env, CwActionOpenTomeParam(slot=None))
    with pytest.raises(AssertionError) as ei:
        CwActionOpenTomeOp.run(op)
    assert 'game state' in str(ei.value), '出口 1 消息指向 gs 缺席'
    assert _env_controller(env).clicks == [], '零点击'

    # 出口 2:状态容器无该 kind 首件槽(bench 全空)
    session2 = StrategySession()
    gs2 = game_state_of(session2)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session2), raising=False)
    _seed_bench(gs2, [])
    env2 = _tome_env(session2, monkeypatch)
    op2 = _make_op(test_context, env2, CwActionOpenTomeParam(slot=None))
    with pytest.raises(AssertionError) as ei2:
        CwActionOpenTomeOp.run(op2)
    assert 'kind=tome' in str(ei2.value), '出口 2 消息指向状态容器无首件槽'
    assert _env_controller(env2).clicks == [], '零点击'


def test_sim_form_bypasses_io_and_still_reports(test_context, monkeypatch):
    """sim 形态(design §2.5):机械分支旁路静默成功(零点击零移动),
    自上报照走(腾席 + star_tome 登记);典籍上报无转移声明 → 后端零
    advance 喂入。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    from sr_od.application.currency_war.sim import cw_sim_ports

    class _Backend:
        """占位后端:仅承载 advance 记录;其余端口触达即炸(本动作在
        sim 分支不得触后端读口)。"""

        def __init__(self) -> None:
            self.advances: list = []

        def screen_identity(self) -> str:
            raise AssertionError('OpenTome 不得触后端读口')

        def observe(self, screen_name: str) -> object:
            raise AssertionError('OpenTome 不得触后端观察')

        def visible(self, screen_name: str, area_name: str) -> bool:
            raise AssertionError('OpenTome 不得触后端门问询')

        def click_answer(self, *a) -> object:
            raise AssertionError('OpenTome 点击分支不经直调触后端')

        def advance(self, decl) -> None:
            self.advances.append(decl)

    backend = _Backend()
    cw_sim_ports.install_sim_backend(backend)
    try:
        session = StrategySession()
        gs = game_state_of(session)
        monkeypatch.setattr(test_context, 'cw_match',
                            SimpleNamespace(session=session), raising=False)
        _seed_bench(gs, [BenchSlot(kind='tome')])
        env = _tome_env(session, monkeypatch)
        op = _make_op(test_context, env, CwActionOpenTomeParam(slot=1))
        rr = _run(test_context, op)
        assert rr.is_success, 'sim 旁路静默成功'
        assert _env_controller(env).clicks == [] \
            and _env_controller(env).moves == [], '机械 IO 零触达'
        assert gs.bench.value.slots[0].kind == 'empty', '自上报腾席照走'
        assert [p.kind for p in gs.screen_changes.pending] == ['star_tome']
        assert backend.advances == [], '典籍上报无转移声明,零 advance'
    finally:
        cw_sim_ports.uninstall_sim_backend()
