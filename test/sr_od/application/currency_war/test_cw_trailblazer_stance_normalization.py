"""开拓者形态归一锁(§3 不变量 5 哨兵)。

锁面 = 换排形态归一归一口唯一:swap 上报与 deploy_move 上报均经同源
归一核(cw_exec_state.trailblazer_row_identity → trailblazer_row_unit),
换排即切换前台记忆/后台欢愉形态(char_id/faction 同步)。P3 申报的
缺陷修复(deploy_move 上报缺归一)落地后,第二段断言已由现状锚
翻转为期待形态切换(唯一允许翻转的锁,提交说明单独申报)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)

from test.sr_od.application.currency_war._cw_helpers import cw4_bview

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_deploy_move_param,
    report_action_swap_deploy_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    ChannelSig,
    Unit,
    deployed_rows_of,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionDeployMoveParam,
    CwActionSwapDeployParam,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


def _gs_with_bench_trailblazer(deployed_taken: bool):
    """bench 0 号槽 = 后台形态开拓者;deployed_taken=True 时
    场上前排 1 号 = 普通角色『甲』(swap 场景需要在场交换对象)。"""
    gs = game_state_of(None)
    slots: list[BenchSlot | None] = [None] * 9
    slots[0] = BenchSlot(kind='unit', unit=Unit(char_id='开拓者·欢愉',
                                                star=4))
    gs.observe(gs.bench, cw4_bview(slots),
               evidence='t', sig=_SIG_OBS)
    if deployed_taken:
        gs.observe(gs.deployed, _dvs([Unit(char_id='甲', star=1, equips=[])], []),
                   evidence='t', sig=_SIG_OBS)
    return gs


def test_swap_report_normalizes_trailblazer_form_to_target_row() -> None:
    """swap 上报有归一:开拓者换排上场 → char_id 切换目标排形态。"""
    gs = _gs_with_bench_trailblazer(deployed_taken=True)
    out = report_action_swap_deploy_param(
        gs, CwActionSwapDeployParam(deployed_idx=0, bench_idx=0), sig=_SIG)
    assert out.applied, f'swap 应成功,实得 {out.reason!r}'
    front, _ = deployed_rows_of(gs)
    assert front and front[0].char_id == '开拓者·记忆', \
        f'换到前排 → 记忆形态,实得 {front[0].char_id!r}'   # 排归属 = 前排行成员


def test_deploy_move_report_normalizes_trailblazer_form_to_target_row() -> None:
    """deploy_move 上报与 swap 同源归一(benchchar-retirement P3 缺陷修复
    申报面,design §3 不变量 5):开拓者拖上场 → 排变、形态(char_id)
    同步切目标排(原现状锚 = 缺归一,已按申报翻转,全文件唯一语义变更
    点)。"""
    gs = _gs_with_bench_trailblazer(deployed_taken=False)
    out = report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='front',
                                    to_slot=1, faction=''),
        sig=_SIG)
    assert out.applied, f'部署应成功,实得 {out.reason!r}'
    front, _ = deployed_rows_of(gs)
    assert front and front[0].char_id == '开拓者·记忆', \
        f'换到前排 → 记忆形态(与 swap 同源归一),实得 {front[0].char_id!r}'
    # 排归属 = 容器行域承载(前排行成员)
