"""sim 接缝锁测试(端口模块 + CwOperation 覆写面 + 事件钩子槽 + 桩)。

锁设计约定(sim 统一迭代 design.md §2 接口契约 + flow-seam 详设 §1/§2/§4):
- 端口模块槽缺省关(不装后端 = 纯实机,读屏改道 helper 走原读链);
- 单装配纪律(重复安装 raise / uninstall 幂等 / teardown 必卸);
- sim 模式 CwOperation 三条腿:screenshot 哨兵帧不触 controller、点击
  腿经后端 click_answer(机械镜:档案点位直成功 + until 可见性问询)、
  find_area 腿 visible 应答;
- controller 桩:直连真实 IO 触碰即 AssertionError(双保险兜底);
- kernel 事件钩子:转移事件封闭集校验 + 上报函数 applied 出口广播、
  缺省关零行为。
"""
import pytest
from test.harness.sim_backend_runner import (
    MinimalSimBackend,
    SimControllerStub,
    sim_backend_fixture,
)

from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from sr_od.application.currency_war.kernel.cw_action_report.zero_writes import (
    report_action_open_box_param,
)
from sr_od.application.currency_war.kernel.cw_event_hooks import (
    TRANSITION_EVENT_KINDS,
    emit_transition_event,
    set_transition_event_sink,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_vocab import CwActionOpenBoxParam
from sr_od.application.currency_war.operations.cw_operation_base import (
    CwOperation,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_ports import (
    install_sim_backend,
    sim_backend_installed,
    sim_or_live_observation,
    uninstall_sim_backend,
)

#: 哨兵帧形状(1080p 基准,area 裁剪不崩、识别恒空 = 双保险第一线)
_SENTINEL_SHAPE = (1080, 1920, 3)
#: 真实建档(screen_info currency_war_battle_prep.yml):点击腿测试用
_PREP_SCREEN = '货币战争-备战'


class _ProbeOp(CwOperation):
    """探针 op:直调基类覆写面(不走 execute 循环,零运行态前置)。"""

    def __init__(self, ctx):
        CwOperation.__init__(self, ctx, op_name='sim-seam-probe',
                             need_check_game_win=False)

    @operation_node(name='probe', is_start_node=True)
    def run(self) -> OperationRoundResult:
        return self.round_success()


@pytest.fixture
def _sim_ctx(test_context, monkeypatch):
    """测试 ctx + controller 桩(monkeypatch 自动还原,防污染共享 ctx)。

    桩兜底语义:测试体内任何直连 controller 路径未改道 = 撞桩即炸,
    测试红 = 覆写面漏改,真值可见。
    """
    monkeypatch.setattr(test_context, 'controller', SimControllerStub())
    return test_context


def test_ports_default_off_and_live_read_chain():
    """端口缺省关:不装后端 = 纯实机(判据 1 的缺省前提)。

    读屏改道 helper 未装配时执行原读链(live_read),不触后端口。"""
    assert sim_backend_installed() is False
    assert cw_sim_ports.get_sim_backend() is None
    marker = object()
    assert sim_or_live_observation(_PREP_SCREEN, lambda: marker) is marker


def test_install_discipline_duplicate_raises_uninstall_idempotent():
    """单装配纪律(端口协议锁):重复安装 raise;uninstall 幂等;
    卸载后可再装;teardown 卸载复位。"""
    with sim_backend_fixture() as backend:
        assert sim_backend_installed() is True
        assert cw_sim_ports.get_sim_backend() is backend
        with pytest.raises(RuntimeError, match='重复安装'):
            install_sim_backend(MinimalSimBackend())
    # teardown 必卸
    assert sim_backend_installed() is False
    # uninstall 幂等 + 卸载后可再装
    uninstall_sim_backend()
    assert sim_backend_installed() is False
    with sim_backend_fixture():
        assert sim_backend_installed() is True


def test_screenshot_returns_sentinel_without_touching_controller(_sim_ctx):
    """sim 哨兵帧:装配后端后 CwOperation.screenshot 返回 1080p 空白帧、
    last_screenshot 置位,全程不触 controller(ctx.controller = 桩,触即炸)。
    空白语义:漏改的帧消费者在哨兵帧上真识别 = 恒未找到(双保险第一线)。"""

    with sim_backend_fixture():
        op = _ProbeOp(_sim_ctx)
        frame = op.screenshot()
        assert frame.shape == _SENTINEL_SHAPE
        assert not frame.any()
        assert op.last_screenshot is frame
        assert op.last_screenshot_time > 0


def test_direct_controller_access_raises(_sim_ctx):
    """controller 桩(双保险兜底):sim 装配下直连 controller 任何接口
    = AssertionError 响亮(报「sim 模式触碰真实 IO」)。"""
    with sim_backend_fixture():
        op = _ProbeOp(_sim_ctx)
        with pytest.raises(AssertionError, match='sim 模式触碰真实 IO'):
            _ = op.ctx.controller.click
        with pytest.raises(AssertionError, match='sim 模式触碰真实 IO'):
            _ = op.ctx.controller.game_win


def test_click_leg_archive_point_and_until_polling(_sim_ctx):
    """sim 点击腿(机械镜契约):无 until = 档案点位直成功(node_clicked
    置位);带 until = 先点击后 round_wait,转移证据可见后下一轮
    round_success;轮询重入不重复进后端 click_answer(点击腿不重发);
    区域未建档 = round_fail 响亮。"""
    until_target = (_PREP_SCREEN, '按钮-商店')
    with sim_backend_fixture() as backend:
        op = _ProbeOp(_sim_ctx)
        # ① 无 until:直成功 + 后端收到恰一次点击
        r1 = op.round_by_find_and_click_area(
            screen_name=_PREP_SCREEN, area_name='按钮-商店')
        assert r1.result is OperationRoundResultEnum.SUCCESS
        assert op.node_clicked is True
        assert backend.clicked == [('货币战争-备战', '按钮-商店')]
        # ② until 未满足:round_wait 轮询,且不重复进后端(点击腿已成功)
        r2 = op.round_by_find_and_click_area(
            screen_name=_PREP_SCREEN, area_name='按钮-商店',
            until_find_all=[until_target])
        assert r2.result is OperationRoundResultEnum.WAIT
        assert backend.clicked == [('货币战争-备战', '按钮-商店')]
        # ③ 转移证据可见:下一轮 round_success(轮询腿直接问 visible)
        backend.visible_areas.add(until_target)
        r3 = op.round_by_find_and_click_area(
            screen_name=_PREP_SCREEN, area_name='按钮-商店',
            until_find_all=[until_target])
        assert r3.result is OperationRoundResultEnum.SUCCESS
        assert backend.clicked == [('货币战争-备战', '按钮-商店')]
        # ④ 区域未建档:fail 响亮(与实机 AREA_NO_CONFIG 同形)
        r4 = op.round_by_find_and_click_area(
            screen_name=_PREP_SCREEN, area_name='不存在的区域')
        assert r4.result is OperationRoundResultEnum.FAIL


def test_find_area_leg_visible_query(_sim_ctx):
    """sim find_area 腿:端口 visible 应答(可见 = success,不可见 =
    retry),不触截图识别链。"""
    area = (_PREP_SCREEN, '按钮-商店')
    with sim_backend_fixture() as backend:
        op = _ProbeOp(_sim_ctx)
        r_miss = op.round_by_find_area(None, area[0], area[1])
        assert r_miss.result is OperationRoundResultEnum.RETRY
        backend.visible_areas.add(area)
        r_hit = op.round_by_find_area(None, area[0], area[1])
        assert r_hit.result is OperationRoundResultEnum.SUCCESS


def test_transition_event_closed_set_and_default_off():
    """事件钩子槽:转移事件封闭集 emit 校验(集外 ValueError 响亮);
    上报函数 applied 出口广播(open_box 真实生产路径:零写族
    applied=True);事实事件缺省关 = 未装 sink 时 emit 零行为。"""
    assert 'open_box' in TRANSITION_EVENT_KINDS
    with pytest.raises(ValueError, match='集外'):
        emit_transition_event('不在封闭集的动作')
    events: list = []
    set_transition_event_sink(events.append)
    try:
        gs = GameState(schema_version=1)
        sig = ChannelSig(family='logic_action', actor='sim-seam-test',
                         mode='compute')
        report_action_open_box_param(gs, CwActionOpenBoxParam(), sig)
        assert [e.kind for e in events] == ['open_box']
    finally:
        set_transition_event_sink(None)
    # 事实事件缺省关(sink 恒 None):emit 零行为
    from sr_od.application.currency_war.kernel.cw_event_hooks import (
        emit_fact_event,
    )
    emit_fact_event('board_changed')
