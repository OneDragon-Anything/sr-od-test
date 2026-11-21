"""ChallengeOrnamentExtraction.start_fight 开战失败重试测试(节点级 mock)。

覆盖(2026-09-25 一条龙开拓力实证):StartFightForElite 攻击 4 次全部
「未进入战斗 尝试攻击」→ op 失败直接上抛,本局 0/3 体力未消耗。
修复 = 开战失败后不再原地失败,回「向红点移动」重新索敌走位一次
再开战(限重试 1 次,超过仍有界失败)。
"""
from unittest.mock import MagicMock, patch

from sr_od.application.div_uni.operations.ornamenet_extraction import (
    ChallengeOrnamentExtraction,
)
from sr_od.context.sr_context import SrContext
from sr_od.interastral_peace_guide.guide_def import GuideMission


def _make_op() -> ChallengeOrnamentExtraction:
    ctx = MagicMock(spec=SrContext)
    mission = MagicMock(spec=GuideMission)
    op = ChallengeOrnamentExtraction(ctx, mission=mission, run_times=1, diff=0,
                                     file_num=0, team_name='', support_character='')
    op.last_screenshot = object()
    # handle_init 正常初始化;节点单测不跑 handle_init 需手供
    op.battle_fail_times = 0
    op.battle_success_times = 0
    op.fight_retry_times = 0
    op.choose_times = 1
    return op


def _start_fight_execute_result(success: bool) -> MagicMock:
    result = MagicMock()
    result.success = success
    return result


def test_start_fight_failure_routes_reapproach_retry() -> None:
    """开战失败且未超限 → round_success('开战失败 重新走位') 回向红点移动节点,
    计入重试次数;不把失败直接上抛。"""
    op = _make_op()
    fail_result = _start_fight_execute_result(success=False)
    reroute_result = MagicMock()
    with patch('sr_od.application.div_uni.operations.ornamenet_extraction.StartFightForElite') as op_cls, \
         patch.object(op, 'round_success', return_value=reroute_result) as round_success, \
         patch.object(op, 'round_by_op_result') as round_by_op_result:
        op_cls.return_value.execute.return_value = fail_result
        result = op.start_fight()
    assert result is reroute_result
    round_success.assert_called_once_with('开战失败 重新走位')
    round_by_op_result.assert_not_called()
    assert op.fight_retry_times == 1


def test_start_fight_fails_bounded_after_retry_exhausted() -> None:
    """重试名额已用尽后再失败 → 失败直接上抛(round_by_op_result 透传),
    不会无限「走位→开战」循环。"""
    op = _make_op()
    op.fight_retry_times = 1
    fail_result = _start_fight_execute_result(success=False)
    passthrough = MagicMock()
    with patch('sr_od.application.div_uni.operations.ornamenet_extraction.StartFightForElite') as op_cls, \
         patch.object(op, 'round_success') as round_success, \
         patch.object(op, 'round_by_op_result', return_value=passthrough) as round_by_op_result:
        op_cls.return_value.execute.return_value = fail_result
        result = op.start_fight()
    assert result is passthrough
    round_success.assert_not_called()
    round_by_op_result.assert_called_once_with(fail_result)
    assert op.fight_retry_times == 2


def test_start_fight_success_passthrough() -> None:
    """开战成功 → 正常透传,不消耗重试名额。"""
    op = _make_op()
    ok_result = _start_fight_execute_result(success=True)
    passthrough = MagicMock()
    with patch('sr_od.application.div_uni.operations.ornamenet_extraction.StartFightForElite') as op_cls, \
         patch.object(op, 'round_success') as round_success, \
         patch.object(op, 'round_by_op_result', return_value=passthrough) as round_by_op_result:
        op_cls.return_value.execute.return_value = ok_result
        result = op.start_fight()
    assert result is passthrough
    round_success.assert_not_called()
    round_by_op_result.assert_called_once_with(ok_result)
    assert op.fight_retry_times == 0


def test_reapproach_edge_declared_in_graph() -> None:
    """节点图存在 进入战斗--(开战失败 重新走位)-->向红点移动 的回路边——
    回路边缺失时开战失败重试只是返回状态,流程不会真正回到走位节点。"""
    op = _make_op()
    op._init_network()
    edges = op._node_edges_map['进入战斗']
    edge_targets = [edge.node_to.cn for edge in edges if edge.status == '开战失败 重新走位']
    assert edge_targets == ['向红点移动']
