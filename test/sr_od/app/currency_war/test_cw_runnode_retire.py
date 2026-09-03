"""RunNode 历史抽象退役批:行为等价锁(用户裁决:按新架构统一)。

RunSupplyNode → CwScreenSupplyNode(cw_screen/cw_screen_supply_node.py)、
RunMegastarNode → CwScreenMegastar 内联(委托壳废止)。本文件锁迁移前后的
**行为断言一致**:①验证完成才 success(离开节点画面)+ ADR-0264 关态基线
预置;②仍在节点内 = 做动作 + round_retry(计 node_max_retry_times=8 预算,
超限框架转 FAIL 交回——预算语义不变);③源码零残留(基类/包路径)。
"""
from pathlib import Path
from types import SimpleNamespace


def _make_op(cls, *, in_node: bool, do_action_calls: list):
    """构画面 op 桩(bypass __init__):round_by_find_area 程序化回 in_node。"""

    class _FakeArea:
        def __init__(self, ok: bool): self.is_success = ok

    class _Op(cls):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            self.last_screenshot = object()
            self.op_name = cls.__name__
            self.ctx = SimpleNamespace(cw_match=None)

        def round_by_find_area(self, scr, screen, area, **k):
            return _FakeArea(in_node)

        def _do_action(self, screen):
            do_action_calls.append(1)

        def round_success(self, status='', wait: float = 0):
            return SimpleNamespace(status=status, wait=wait, success=True)

        def round_retry(self, status='', wait: float = 0):
            return SimpleNamespace(status=status, wait=wait, success=None,
                                   _retry=True)

        def round_fail(self, status=''):
            return SimpleNamespace(status=status, success=False)

        def save_screenshot(self, prefix=None):
            return ''

    return _Op()


def _capture_baseline(monkeypatch) -> list:
    """桩化 cw_observation_gate.preset_stable_baseline(局部 import 面捕获)。"""
    from sr_od.application.currency_war.obs import cw_observation_gate as gate
    calls: list = []
    monkeypatch.setattr(gate, 'preset_stable_baseline',
                        lambda screen, profile=None: calls.append(profile))
    return calls


# ==================== 补给节点流转(行为等价①②) ====================

def test_supply_leaves_node_success_with_baseline(monkeypatch) -> None:
    """验证完成才 success:离开补给屏(锚 miss)→ success(节点完成)+
    关态稳定基线预置(ADR-0264 语义随迁)。"""
    from sr_od.application.currency_war.obs.cw_observation_gate import (
        PROFILE_CLOSED,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
        CwScreenSupplyNode,
    )
    calls = _capture_baseline(monkeypatch)
    actions: list = []
    op = _make_op(CwScreenSupplyNode, in_node=False, do_action_calls=actions)
    res = op.handle()
    assert res.success is True
    assert '节点完成' in res.status
    assert actions == []                       # 离开节点 = 不再发动作
    assert calls == [PROFILE_CLOSED]           # 关态基线预置(行为等价)


def test_supply_in_node_act_then_retry(monkeypatch) -> None:
    """仍在补给屏 → 做一个动作 + round_retry(计节点预算;不 success)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
        CwScreenSupplyNode,
    )
    _capture_baseline(monkeypatch)
    actions: list = []
    op = _make_op(CwScreenSupplyNode, in_node=True, do_action_calls=actions)
    res = op.handle()
    assert actions == [1]                      # 每轮恰好一个动作
    assert getattr(res, '_retry', False) is True


def test_supply_budget_semantics_unchanged() -> None:
    """预算语义不变:node_max_retry_times=8(原 RunNode 子类口径,
    超限框架转 FAIL bail 交回)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
        CwScreenSupplyNode,
    )
    node = CwScreenSupplyNode.handle.operation_node_annotation
    assert node.node_max_retry_times == 8


# ==================== 巨星流转(行为等价①②) ====================

def test_megastar_leaves_node_success_with_settle(monkeypatch) -> None:
    """巨星:overlay 消失 → success(完成承诺 = 固定 1.0s,原委托壳语义)
    + 关态基线预置;选中标记复位副作用随迁。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_flow_const import (
        CW_OVERLAY_SETTLE_S,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar import (
        CwScreenMegastar,
    )
    calls = _capture_baseline(monkeypatch)
    actions: list = []
    op = _make_op(CwScreenMegastar, in_node=False, do_action_calls=actions)
    res = op.handle()
    assert res.success is True
    assert res.wait == CW_OVERLAY_SETTLE_S
    assert actions == []
    assert calls  # 基线预置已发生


def test_megastar_in_node_act_then_retry(monkeypatch) -> None:
    """巨星:仍在 overlay → 一个动作 + round_retry。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar import (
        CwScreenMegastar,
    )
    _capture_baseline(monkeypatch)
    actions: list = []
    op = _make_op(CwScreenMegastar, in_node=True, do_action_calls=actions)
    res = op.handle()
    assert actions == [1]
    assert getattr(res, '_retry', False) is True


def test_megastar_budget_semantics_unchanged() -> None:
    """预算语义不变:node_max_retry_times=8(原 RunNode 子类口径)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar import (
        CwScreenMegastar,
    )
    node = CwScreenMegastar.handle.operation_node_annotation
    assert node.node_max_retry_times == 8


# ==================== 零残留 + 判据落档 ====================

def test_runnode_zero_residue_in_src() -> None:
    """grep 零残留:currency_war src 下无 RunNode 基类/run_nodes 包路径的
    活引用(sim/telemetry 注释中的旧类名 RunSupplyNode 不含 RunNode 子串,
    且按纪律不动)。"""
    root = Path('src/sr_od/application/currency_war')
    assert not (root / 'operations' / 'run_nodes').exists(), \
        'run_nodes/ 包应已删除'
    for p in root.rglob('*.py'):
        text = p.read_text(encoding='utf-8', errors='ignore')
        assert 'RunNode' not in text, f'{p} 残留 RunNode'
        assert 'run_nodes' not in text, f'{p} 残留 run_nodes'


def test_completion_model_criteria_documented() -> None:
    """判据落档锁(NAMING.md §6):完成验证模型选型判据在档。"""
    naming = (Path('docs/develop/currency_war/prereg/w971_flow_layer')
              / 'NAMING.md').read_text(encoding='utf-8')
    assert '完成验证模型选型判据' in naming
    assert 'CwScreenSupplyNode' in naming
    assert '依赖外循环重识别兜底' in naming
