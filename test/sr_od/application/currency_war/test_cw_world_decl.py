"""世界后果声明对照锁骨架(schema 形状 / 载体兼容 / 喂入端口 / 分派校验)。

锁设计约定(动作后果声明化迭代总纲 design.md §2.2 契约 1/2/3 + 详设
details/world-decl.md §1/§3/§7;3.1 = 声明基建骨架,行为对照锁随
3.2/3.3 按 §2 对照表增量填充,本文件先锁结构):
- WorldDecl 形状锁(冻结 dataclass;字段序 = next_screen 在前,位置
  构造契约);
- LogicOutcome.world_decl 缺省兼容锁(缺省 None,既有全量构造点
  零改动兼容);
- declare_world 喂入契约锁(未装配 no-op = 实机零行为变化的机制
  前提;装配后转发后端 advance;decl=None 端口层直返);
- advance 分派表集外值 ValueError 锁(封闭集防线与转移事件同型)。
"""
import dataclasses

import pytest
from test.harness.sim_backend_runner import (
    MinimalSimBackend,
    sim_backend_fixture,
)

from sr_od.application.currency_war.kernel.cw_game_state import LogicOutcome
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_ports import declare_world


def test_world_decl_shape_lock():
    """WorldDecl 形状锁(契约 1):冻结 dataclass;字段面 = next_screen/
    trigger 且 next_screen 在前(18 个上报构造点与 backend 消费端按此
    位置契约解析;字段增删/换序/可变性漂移 = 声明契约破坏)。"""
    assert [f.name for f in dataclasses.fields(WorldDecl)] == [
        'next_screen', 'trigger']
    decl = WorldDecl(next_screen='货币战争-备战', trigger='')
    with pytest.raises(dataclasses.FrozenInstanceError):
        decl.next_screen = 'x'  # type: ignore[misc]


def test_logic_outcome_world_decl_default_compat():
    """LogicOutcome.world_decl 缺省兼容锁(契约 2):缺省 None =
    既有全量构造点零改动兼容——关键字构造(applied 起)与位置构造
    (至 bought_count 位)均不受新字段影响,拒绝路径(world_decl=None)
    语义不变。"""
    assert LogicOutcome(applied=True).world_decl is None
    positional = LogicOutcome(True, '同名拒上', 3, None, 2)
    assert positional.world_decl is None
    assert positional.bought_count == 2


def test_declare_world_port_default_off_and_forwarding():
    """declare_world 喂入契约锁(契约 3):未装配 = no-op(实机零开销
    零行为变化——本迭代产物「在库未接线」的机制前提);装配后 =
    后端 advance(decl) 恰转发一次;decl = None(非转移动作)端口层
    直返,装配与否都不触后端。"""
    # 未装配:no-op 不响(纯实机缺省态)
    assert cw_sim_ports.get_sim_backend() is None
    declare_world(WorldDecl(next_screen='货币战争-备战', trigger=''))
    declare_world(None)

    class _RecordingBackend(MinimalSimBackend):
        """advance 调用记录桩(喂入转发的观测面;其余端口腿继承最小实现)。"""

        def __init__(self) -> None:
            super().__init__()
            self.advanced: list[WorldDecl] = []

        def advance(self, decl: WorldDecl) -> None:
            self.advanced.append(decl)

    backend = _RecordingBackend()
    with sim_backend_fixture(backend):
        declare_world(None)
        assert backend.advanced == []
        decl = WorldDecl(next_screen='货币战争-备战', trigger='')
        declare_world(decl)
        assert backend.advanced == [decl]
    assert cw_sim_ports.get_sim_backend() is None, 'teardown 必卸'


def test_advance_trigger_out_of_set_raises():
    """advance 分派表集外值 ValueError 锁(详设 world-decl.md §3 集外
    处置):集外 trigger 响亮(构造点漂移 = 接线 bug 禁静默),与现行
    转移事件封闭集同等防线;'' 纯转移恒在键集(空串安全 = 不 raise,
    零专属过程)。"""
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        ADVANCE_TRIGGER_KINDS,
        SimBackend,
    )
    from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

    backend = SimBackend(seed=9, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    # box_pick = 详设点名的禁入反例(与画面名/动作名错位的自造词)
    with pytest.raises(ValueError, match='分派表'):
        backend.advance(WorldDecl(next_screen='货币战争-备战',
                                  trigger='box_pick'))
    assert '' in ADVANCE_TRIGGER_KINDS
    backend.advance(WorldDecl(next_screen='货币战争-备战', trigger=''))
