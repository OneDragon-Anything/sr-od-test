"""专家研讨会 sim 全链轻量局测试(镜像 src 主断言对象 = 环境发放经 sim
后端全链;按流程级测试落位本目录,引擎驱动助手 import 自
sim/test_sim_backend.py〔已登记超限拆分债文件,禁追加,只 import 复用不改;
先例 = 本目录 test_env_deploy_lock_sim_chain.py 与 T-32
test_equip_env_pick_sim_full_chain_blue_diamond〕)。

测试面依据 = 迭代 T-39 专家研讨会设计(.debug/progress/2026-09-23-invest-
effects-calc/designs/T-39-zhuanjia-yantaohui.md)§2.1/§2.4 + §4 锁 8:
- 选卡后 bench = 4 开局手牌 + bookcard 槽 + supply_box 槽(卡文序,带名);
- 开卡上报 applied + 槽腾空 + SCREEN_EXPERT 呈现(advance 纯转移;
  呈现数据源 = 容器登记,open_bookcard 上报内 register);
- 选卡上报消费 expert_invite 登记 + 纯转移回备战(注:sim 选卡上报 =
  容器零写契约〔zero_writes.py〕,``chosen_expert`` 容器写 = live 画面 op
  落地复查点、由 kernel 侧既有锁面承担——本链断言消费与转移面);
- 武装箱开箱链独立正常(箱画面候选 → 选定 → 所得经获得链入栏);
- 同 seed 重放确定(环境道具分支零采样)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _env_pick_backend,
    _seed_and_pick_env,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_open_bookcard_param,
    report_action_open_box_param,
    report_action_pick_box_card_param,
    report_action_pick_expert_invite_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionOpenBoxParam,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BOX,
    SCREEN_EXPERT,
    SCREEN_PREP,
    uninstall_backend,
)

_SIG = ChannelSig(family='logic_action', actor='SimBackendTest',
                  mode='compute')


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(选卡上报产 EXPERT_UNLOCK_NAME_UNOBSERVED 申报行;
    前清防他测残留、后清防本测外泄——沿 sim/test_sim_backend 同名 fixture
    先例,fixture 不可跨文件 import 故本文件自带同名同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _run_expert_chain(seed: int) -> tuple[list, list[str]]:
    """播种选专家研讨会 + 开卡/选卡/开箱三链全走(调用方负责 uninstall;
    返回 = 选卡后槽位快照 + 终态 equips,供同 seed 重放对拍)。"""
    b = _env_pick_backend(seed)
    try:
        gs = b.gs
        _seed_and_pick_env(b, '专家研讨会')
        # —— 选卡后:4 开局手牌 + bookcard 槽 + supply_box 槽(卡文序)——
        slots = [(s.kind, s.item) for s in gs.bench.value.slots
                 if s is not None and s.kind != 'empty']
        assert slots == ([('unit', None)] * 4
                         + [('bookcard', '专家邀请函'),
                            ('supply_box', '简易武装箱')]), \
            f'bench 两槽卡文序带名: {slots}'
        # —— 开卡上报 + SCREEN_EXPERT 呈现(advance 纯转移)——
        open_out = report_action_open_bookcard_param(
            gs, SimpleNamespace(slot=None), _SIG)
        assert open_out.applied, '开卡上报 applied'
        left = [(s.kind, s.item) for s in gs.bench.value.slots
                if s is not None and s.kind != 'empty']
        assert ('bookcard', '专家邀请函') not in left, '槽腾空'
        cw_sim_ports.declare_world(open_out.world_decl)
        assert b.screen_identity() == SCREEN_EXPERT, '专家邀请函弹窗呈现'
        # —— 选卡上报消费登记 + 纯转移回备战 ——
        pick_out = report_action_pick_expert_invite_param(
            gs, SimpleNamespace(idx=0), _SIG)
        assert pick_out.applied
        assert all(p.kind != 'expert_invite'
                   for p in gs.screen_changes.pending), '登记已消费'
        cw_sim_ports.declare_world(pick_out.world_decl)
        assert b.screen_identity() == SCREEN_PREP, '选卡交回备战'
        # —— 武装箱开箱链独立正常 ——
        box_out = report_action_open_box_param(
            gs, CwActionOpenBoxParam(), _SIG)
        cw_sim_ports.declare_world(box_out.world_decl)
        assert b.screen_identity() == SCREEN_BOX, '箱画面呈现'
        cands = gs.box_card_names.value
        assert cands is not None and len(cands) == 4, '候选写容器'
        b._handle_click_source(SCREEN_BOX, '装备卡-3')
        pick_box = report_action_pick_box_card_param(
            gs, SimpleNamespace(), _SIG)
        assert pick_box.applied
        cw_sim_ports.declare_world(pick_box.world_decl)
        assert cands[2] in (gs.equips.value or []), '开箱所得经获得链入栏'
        assert b.screen_identity() == SCREEN_PREP, '模态交回备战'
        return slots, list(gs.equips.value or [])
    finally:
        uninstall_backend()


def test_expert_invite_env_sim_full_chain(
        _isolate_defect_buffer) -> None:
    """sim 全链轻量局(T-39 设计 §4 锁 8):五段断言见模块 docstring;
    写状态副本发放域登记一处,实机(live)和模拟器(sim)两边同链零 sim 私有接入调用(链原语复用 = kernel
    单一获得链,sim 写状态副本即容器写)。"""
    slots, equips = _run_expert_chain(7)
    assert len(slots) == 6, '4 开局手牌 + 2 道具槽'
    assert len(equips) == 1, '开箱所得 1 件入栏'


def test_expert_invite_env_sim_replay_deterministic(
        _isolate_defect_buffer) -> None:
    """同 seed 重放确定(T-39 设计 §4 锁 8 确定性面):环境道具分支零采样,
    两跑槽位快照与 equips 终态逐位一致。"""
    first = _run_expert_chain(7)
    second = _run_expert_chain(7)
    assert first == second, '同 seed 重放逐位确定'
