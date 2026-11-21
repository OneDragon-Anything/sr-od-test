"""UpgradeLightConeOp 手动路线失败适配 mock 测试(升级 op 适配迭代块 C)。

锁设计约定(docs/develop/sr_od/application/cultivation/changes/
upgrade-ops-adaptation/details/fail-adaptation.md §3):与块 B(角色线)同构,
差异 = 返回分类节点名(刷取返回分类)与失败重发回链挂点(副本刷取分流);
判停回家链同为关副本回大世界(手动路线副本关闭本就落大世界,既有
BACK_TO_WORLD 出口不变);计场时机保留现状(点击时计,不与角色线统一)。

测试手法:分支直呼 + find/click 响应器打桩(帧驱动由块 A 同款共享件流程
测试覆盖,不在此重复);预算算术用 _farm_rounds 直接置位。
"""

from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import fast_sleep

from sr_od.application.cultivation.light_cone.operations.upgrade_light_cone import (
    UpgradeLightConeOp,
)


def _make_op(test_context: SrTestContext, farm_rounds: int,
             farm_rounds_max: int) -> UpgradeLightConeOp:
    op = UpgradeLightConeOp(test_context, fill_generic=False, farm_dungeon=True,
                            use_fast_ticket=False, farm_rounds_max=farm_rounds_max)
    op._farm_rounds = farm_rounds
    return op


def _patch_find(monkeypatch: pytest.MonkeyPatch, op: UpgradeLightConeOp,
                hits: set[tuple[str, str]]) -> None:
    """打桩 find_area:按(画面,区域)命中表应答,其余 MISS。"""

    def _find(screen, screen_name, area_name, **kwargs):
        return SimpleNamespace(is_success=(screen_name, area_name) in hits)

    monkeypatch.setattr(op, 'round_by_find_area', _find)


def _patch_click(monkeypatch: pytest.MonkeyPatch, op: UpgradeLightConeOp,
                 clicked: list[tuple[str, str]]) -> None:
    """打桩 find_and_click:记录(画面,区域)并返回成功。"""

    def _click(screen, screen_name, area_name, **kwargs):
        clicked.append((screen_name, area_name))
        return SimpleNamespace(is_success=True)

    monkeypatch.setattr(op, 'round_by_find_and_click_area', _click)


def _patch_resume(monkeypatch: pytest.MonkeyPatch, success: bool,
                  status: str) -> None:
    class _StubResume:
        def __init__(self, ctx):
            pass

        def execute(self):
            return SimpleNamespace(success=success, status=status, data=None)

    monkeypatch.setattr(
        'sr_od.application.cultivation.light_cone.operations.upgrade_light_cone.'
        'ResumeFromBattleFail', _StubResume)


class TestEdgeDeclarations:
    """边结构锁:失败分支出口与新回链不被静默拆掉。"""

    def test_fail_retry_edge_routes_to_farm_split(
            self, test_context: SrTestContext) -> None:
        op = _make_op(test_context, farm_rounds=0, farm_rounds_max=1)
        op._init_network()
        edges = op._node_edges_map.get('刷取返回分类', [])
        retry_edges = [e for e in edges if e.status == '失败重发']
        assert len(retry_edges) == 1, f'失败重发应恰一条边,实际 {edges}'
        assert retry_edges[0].node_to.cn == '副本刷取分流'


class TestFailBranchBehavior:
    """失败画面分支行为(预算检查内联/三出口/结算回归)。"""

    def test_fail_below_budget_retries(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """预算未超 → 委托成功 → 失败重发。"""
        op = _make_op(test_context, farm_rounds=1, farm_rounds_max=2)
        _patch_find(monkeypatch, op, {('大世界-战斗失败', '标题-战斗失败')})
        clicked: list[tuple[str, str]] = []
        _patch_click(monkeypatch, op, clicked)
        _patch_resume(monkeypatch, success=True, status='已回挑战画面')

        result = op.back_after_farm()

        assert result.is_success
        assert result.status == '失败重发'
        assert clicked == [], '重发分支不应有清理点击'

    def test_fail_at_budget_exhausted_routes_world(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """预算耗尽 → 委托成功 → 关副本回大世界 → BACK_TO_WORLD(判停交升级循环)。"""
        op = _make_op(test_context, farm_rounds=2, farm_rounds_max=2)
        monkeypatch.setattr(op, 'screenshot', lambda: None)
        _patch_find(monkeypatch, op, {('大世界-战斗失败', '标题-战斗失败')})
        clicked: list[tuple[str, str]] = []
        _patch_click(monkeypatch, op, clicked)
        _patch_resume(monkeypatch, success=True, status='已回挑战画面')

        result = op.back_after_farm()

        assert result.is_success
        assert result.status == 'BACK_TO_WORLD'
        assert clicked == [('挑战副本', '按钮-关闭副本')], (
            f'判停应关副本回大世界:{clicked}'
        )

    def test_shared_op_fail_passes_through(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """共享件 fail → 原样透传(现场交调用方,不收尾)。"""
        op = _make_op(test_context, farm_rounds=1, farm_rounds_max=2)
        _patch_find(monkeypatch, op, {('大世界-战斗失败', '标题-战斗失败')})
        clicked: list[tuple[str, str]] = []
        _patch_click(monkeypatch, op, clicked)
        _patch_resume(monkeypatch, success=False, status='失败画面未能离开')

        result = op.back_after_farm()

        assert not result.is_success
        assert result.status == '失败画面未能离开'
        assert clicked == []

    def test_victory_settle_branch_regression(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """结算分支回归:旧形态结算(退出关卡在场,失败标题不在)仍点退出关卡。"""
        op = _make_op(test_context, farm_rounds=1, farm_rounds_max=2)
        _patch_find(monkeypatch, op, {('战斗画面', '按钮-退出关卡')})
        clicked: list[tuple[str, str]] = []
        _patch_click(monkeypatch, op, clicked)

        result = op.back_after_farm()

        assert clicked == [('战斗画面', '按钮-退出关卡')], '结算分支行为不变'
        assert result.result.name == 'RETRY', '结算退出后重入分类(既有行为)'

    def test_transition_frame_keeps_waiting(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """全锚 MISS(战斗中/过渡帧)→ 慢询等待,不点击(既有行为)。"""
        op = _make_op(test_context, farm_rounds=1, farm_rounds_max=2)
        _patch_find(monkeypatch, op, set())
        # 画面级判定也桩掉(直呼无真帧,测的是分支逻辑非识别层)
        monkeypatch.setattr(op, 'check_and_update_current_screen',
                            lambda screen, screen_name_list: None)
        clicked: list[tuple[str, str]] = []
        _patch_click(monkeypatch, op, clicked)

        with fast_sleep():
            result = op.back_after_farm()

        assert result.result.name == 'WAIT'
        assert clicked == []
