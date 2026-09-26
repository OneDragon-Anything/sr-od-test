"""sim 接缝锁测试(端口模块 + CwOperation 覆写面 + 事件钩子槽 + 桩)。

锁设计约定(sim 统一迭代 design.md §2 接口契约 + flow-seam 详设 §1/§2/§4):
- 端口模块槽缺省关(不装后端 = 纯实机,读屏改道 helper 走原读链);
- 单装配纪律(重复安装 raise / uninstall 幂等 / teardown 必卸);
- sim 模式 CwOperation 三条腿:screenshot 哨兵帧不触 controller、点击
  腿经后端 click_answer(机械镜:档案点位直成功 + until 可见性问询)、
  find_area 腿 visible 应答;
- controller 桩:直连真实 IO 触碰即 AssertionError(双保险兜底);
- kernel 事件钩子:事实事件缺省关零行为(sink 未装时 emit 零外送;
  画面转移后果的声明通道锁 = test_cw_world_decl)。
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


# (事实事件缺省关测试已随事实事件槽退役删除:
#  事实事件槽本体与全部广播调用点同批删除,sim 呈现 =
#  容器登记 + 问询时点懒呈现,锁在 test_cw_sim_backend 懒呈现两测试。)


# ============================================================ 3.4 联调接线锁

def test_identity_helper_filters_by_screen_list():
    """画面身份读点改道 helper(sim 统一 3.4;flow-seam 附录 A.2
    「sim 画面身份归 screen_identity」):装配后 = 状态机答口,且清单外
    返回 None(与实机 get_match_screen_name 清单过滤同形,备战双锚默认
    分支不受扰);缺省关 = 原识别链零行为变化。"""
    with sim_backend_fixture(MinimalSimBackend(screen='货币战争-补给')):
        assert cw_sim_ports.sim_or_live_identity(
            ('货币战争-补给',), lambda: 'LIVE') == '货币战争-补给'
        assert cw_sim_ports.sim_or_live_identity(
            (_PREP_SCREEN,), lambda: 'LIVE') is None
    assert cw_sim_ports.sim_or_live_identity(
        (_PREP_SCREEN,), lambda: 'LIVE') == 'LIVE'


def test_mechanical_io_allowed_default_true_sim_false():
    """机械 IO 腿检查口(直连旁路 port 检查的共用判定,flow-seam §2):
    实机(未装配)= True 零行为变化;sim 装配后 = False(机械腿静默
    跳过,自上报照走)。"""
    assert cw_sim_ports.mechanical_io_allowed() is True
    with sim_backend_fixture():
        assert cw_sim_ports.mechanical_io_allowed() is False
    assert cw_sim_ports.mechanical_io_allowed() is True


def test_action_rng_provider_seeded_on_install_reset_on_uninstall():
    """动作腿采样 rng 注入槽(T-2 偏差申报的归属点接线):SimBackend
    install_backend 接通提供槽(流键 rng,同 seed 同调用序确定性);
    uninstall_backend 复位 = 实机未播种口径零变化。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        provided_action_rng,
    )
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        SimBackend,
        install_backend,
        uninstall_backend,
    )
    from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

    assert provided_action_rng('collect_ore') is None, '缺省必须关'
    install_backend(SimBackend(seed=9, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108)))
    try:
        first = provided_action_rng('collect_ore').random()
    finally:
        uninstall_backend()
    assert provided_action_rng('collect_ore') is None, '卸载必须复位'
    install_backend(SimBackend(seed=9, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108)))
    try:
        second = provided_action_rng('collect_ore').random()
    finally:
        uninstall_backend()
    assert first == second, '同 seed 同键序采样必须一致(确定性)'
