"""sim 词缀转正闭环回归(接管补采委派链的 sim 呈现面;T-440)。

测试面(T-440 判据的可执行形态;根因与修法 =
``reports/T-439-r1.md`` §2/§5 方向 B + ``reports/T-440-r1.md``):

1. **端口缺省关(实机零变化定向锁)**:``sim_or_live_node_sequence`` /
   ``sim_or_live_plane_intel_view`` 未装后端时直通原读链(live_read),
   不触后端——守卫的裸 CV 读链语义逐字未动,实机路径零行为变化;
2. **备战节点条答口**:装 SimBackend 后备战帧合成节点行(state 按当前
   节点序位、类型自序列真值直出);非备战屏 = None(实机「半开帧读条
   = None」稳定判据语义同形);
3. **位面详情呈现面 + 点击源封闭链**:备战点节点条 → 详情屏模态呈现;
   切卡联动选中位面;点 boss 节点 → 详情条「首领」标签;点 X → 回备战;
   呈现面字段与实机 CV 读链逐点同形(选中位面/槽/词缀/标签/boss 名);
4. **词缀转正闭环集成**:词缀随机态(logic_rand)+ 真实 CwEntryPlaneIntel
   编排(真 CwScreenPlaneIntel 识别管线子 op)在 sim 状态副本上走通
   门 → 开详情 → 识别三位面 → 上报写门 → 关详情——随机态经 observe
   分支转正(谓词解除,封死等待态不可达)、画面回备战、真值落状态容器。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)
from test.harness.sim_backend_runner import (
    SimControllerStub,
    freeze_cw_module_time,
    sim_backend_fixture,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    bind_session_container,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    PLANE_NODE_TABLES,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_PLANE_INTEL,
    SCREEN_PREP,
    PlaneIntelPresentation,
    SimBackend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_TEST_SIG = ChannelSig(family='logic_action', actor='TestWriter',
                       mode='compute')


# ==================== 装配 ====================


def _prep_backend(seed: int = 20260923) -> SimBackend:
    """进 P1r1 备战窗的 SimBackend(reset → 简报 → wait_one_one 惰性完成)。"""
    backend = SimBackend(
        seed=seed,
        cfg=RunConfig(selected_difficulty='A8', enemy_difficulty=108,
                      env_present=False))
    assert backend.screen_identity() == SCREEN_BRIEFING
    backend._advance_briefing()          # env_present=False → wait_one_one 变体
    backend._maybe_finish_wait()         # 问询时点惰性完成 → P1r1 备战窗
    assert backend.screen_identity() == SCREEN_PREP
    return backend


class _Session:
    """对局 session 桩(weakref 可挂——状态容器按会话弱引用绑定,
    SimpleNamespace 不可弱引用)。"""


def _bind_session(test_context, monkeypatch, backend: SimBackend) -> _Session:
    """对局 session 桩 + 状态容器绑定(后端状态容器 = 流程唯一状态副本)。"""
    session = _Session()
    bind_session_container(session, backend.gs)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    return session


def _force_affix_rand(backend: SimBackend, names: list[str]) -> None:
    """词缀名单置随机态(敌后破坏删除分支的落账形态:剩余名单整条
    logic_rand 写;转正谓词 = ``enemy_affixes ∈ logic_rand_fields()``)。"""
    backend.gs.write_logic_rand(backend.gs.enemy_affixes, list(names),
                                produced_by='TestWriter', sig=_TEST_SIG)
    assert 'enemy_affixes' in backend.gs.logic_rand_fields()


# ==================== 1. 端口缺省关(实机零变化) ====================


def test_ports_default_off_pass_through_live_read() -> None:
    """不装后端 = 纯实机:两个新改道口直通 live_read 原读链,后端零触达
    (守卫裸 CV 读链语义逐字未动的定向锁;装后端分支行为归本文件其余面)。"""
    assert cw_sim_ports.sim_backend_installed() is False
    marker_slots = [SimpleNamespace(state='current')]
    assert cw_sim_ports.sim_or_live_node_sequence(lambda: marker_slots) \
        is marker_slots
    assert cw_sim_ports.sim_or_live_node_sequence(lambda: None) is None
    marker_view = SimpleNamespace(selected_plane=2)
    assert cw_sim_ports.sim_or_live_plane_intel_view(lambda: marker_view) \
        is marker_view
    assert cw_sim_ports.sim_or_live_plane_intel_view(lambda: None) is None


# ==================== 2. 备战节点条答口 ====================


def test_backend_node_sequence_synth_on_prep() -> None:
    """备战帧节点条合成:长度 = 序列长;current 槽 = 当前节点序位、类型 =
    序列真值;未来槽类型直出、过去槽 None;非备战屏 = None(半开帧判据
    语义同形);无真值不静默造行。"""
    backend = _prep_backend()
    with sim_backend_fixture(backend):
        seq = PLANE_NODE_TABLES[1]
        slots = backend.node_sequence()
        assert slots is not None and len(slots) == len(seq)
        cur = [s for s in slots if s.state == 'current']
        assert len(cur) == 1 and slots.index(cur[0]) == 0   # P1r1 = 首槽
        assert cur[0].node_type == seq[0]
        assert slots[0].node_type == seq[0]
        assert all(s.node_type == k
                   for s, k in zip(slots[1:], seq[1:], strict=True))
        # 简报屏(非备战)→ None:稳定判据「不可读」语义保持
        backend._announce_screen(SCREEN_BRIEFING)
        backend._screen = SCREEN_BRIEFING
        assert backend.node_sequence() is None


# ==================== 3. 位面详情呈现面 + 点击源封闭链 ====================


def test_plane_detail_click_chain_and_presentation(
        test_context, monkeypatch) -> None:
    """详情屏封闭链:备战点节点条 → 模态呈现(visible 门真值翻转);
    呈现面选中位面 = 当前节点位面;切卡联动;点 boss → 「首领」标签;
    点 X → 回备战;boss 名 = 位面序真值;词缀读数 = 状态副本现值。"""
    backend = _prep_backend()
    _force_affix_rand(backend, ['灼热轰炸', '能量'])
    with sim_backend_fixture(backend):
        from sr_od.application.currency_war.operations.cw_operation_base import (
            CwOperation,
        )

        class _ProbeOp(CwOperation):
            """探针 op(直调端口面;机械镜 round 结果消费 ctx 档案点位)。"""

            def __init__(self, ctx):
                CwOperation.__init__(self, ctx, op_name='pd-chain-probe',
                                     need_check_game_win=False)

        probe = _ProbeOp(test_context)
        # 开屏点击源(备战节点条)
        backend.click_answer(probe, SCREEN_PREP, '区域-节点条', None, None)
        assert backend.screen_identity() == SCREEN_PLANE_INTEL
        assert backend.visible(SCREEN_PLANE_INTEL, '标识-位面详情标题')
        assert not backend.visible(SCREEN_PREP, '备战标识-购买经验')
        view = backend.plane_intel_view()
        assert isinstance(view, PlaneIntelPresentation)
        assert view.selected_plane == 1
        assert view.node_type_label is None           # 未点 boss,标签未呈现
        assert view.enemy_affixes == ['灼热轰炸', '能量']
        assert view.boss_name == backend.gs.plane_bosses.value[0]
        assert [s.node_type for s in view.node_slots] \
            == list(PLANE_NODE_TABLES[1])
        # 切卡联动 + boss 标签呈现态
        backend.click_answer(probe, SCREEN_PLANE_INTEL,
                             '按钮-位面卡2', None, None)
        assert backend.plane_intel_view().selected_plane == 2
        assert backend.plane_intel_view().boss_name \
            == backend.gs.plane_bosses.value[1]
        backend.click_answer(probe, SCREEN_PLANE_INTEL,
                             '区域-节点条', None, None)
        assert backend.plane_intel_view().node_type_label == '首领'
        # 关屏点击源(X)→ 回备战,呈现态复位
        backend.click_answer(probe, SCREEN_PLANE_INTEL,
                             '按钮-关闭位面详情', None, None)
        assert backend.screen_identity() == SCREEN_PREP
        assert backend._pd_selected_plane is None
        assert backend._pd_boss_selected is False


# ==================== 4. 词缀转正闭环集成 ====================


def test_entry_chain_promotes_random_affixes_on_sim(
        test_context, monkeypatch) -> None:
    """词缀随机态 → 真实 CwEntryPlaneIntel 全链(真识别管线子 op)在 sim
    状态副本上走通:开详情 → 三位面识别 → 上报写门 observe 分支转正 →
    关详情回备战。红 = 委派链 sim 呈现面断裂(转正不可达 = 守卫封死
    活锁的对偶面);零直连 controller 触碰(桩兜底,触即炸)。"""
    backend = _prep_backend()
    _force_affix_rand(backend, ['灼热轰炸'])
    _bind_session(test_context, monkeypatch, backend)
    monkeypatch.setattr(test_context, 'controller', SimControllerStub())

    from sr_od.application.currency_war.operations.cw_entry.cw_entry_plane_intel import (
        CwEntryPlaneIntel,
    )

    op = CwEntryPlaneIntel(test_context)
    enter_running_state(test_context)
    try:
        with sim_backend_fixture(backend), freeze_cw_module_time(), \
                fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(test_context, op)
    assert result.success, f'委派链应收敛成功:{result.status!r}'
    assert result.status == CwEntryPlaneIntel.STATUS_DONE
    # 转正:随机态经写门 observe 分支覆盖,谓词解除(守卫封死态不可达)
    assert backend.gs.enemy_affixes.source == 'observation'
    assert 'enemy_affixes' not in backend.gs.logic_rand_fields()
    # 画面回备战(委派链闭环交回主循环)
    assert backend.screen_identity() == SCREEN_PREP


@pytest.mark.parametrize('names', [['灼热轰炸'], []])
def test_report_write_gate_promotion_branches(names: list[str]) -> None:
    """写门随机态分支语义锁(转正闭环的落账面):logic_rand 来源经
    observe 覆盖转正,空表读数(删尽态)同样转正、谓词解除。"""
    from sr_od.application.currency_war.kernel.cw_screen_report.plane_intel import (
        CwScreenPlaneIntelObs,
        report_screen_plane_intel_obs,
    )
    backend = _prep_backend()
    _force_affix_rand(backend, ['旧词缀'])
    gs = backend.gs
    report_screen_plane_intel_obs(gs, CwScreenPlaneIntelObs(
        on_screen=True, plane_bosses=list(gs.plane_bosses.value),
        enemy_affixes=list(names)))
    assert gs.enemy_affixes.source == 'observation'
    assert gs.enemy_affixes.value == names
    assert 'enemy_affixes' not in gs.logic_rand_fields()
