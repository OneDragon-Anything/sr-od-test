"""开拓者形态归一现状锁。

锁面 = 换排形态归一的现状不对称:swap 上报经归一口(换排即切换
前台记忆/后台欢愉形态,char_id/faction 同步),deploy_move 上报缺
归一(形态不随排切换)——后者为已申报的不对称缺陷,归一口统一后
第二段断言翻转为期待形态切换。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_deploy_move_param,
    report_action_swap_deploy_param,
)
from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    Unit,
    bench_view_of_slots,
    deployed_slots_of,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionDeployMoveParam,
    CwActionSwapDeployParam,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


def _gs_with_bench_trailblazer(deployed_occupied: bool):
    """bench 0 号槽 = 后台形态开拓者;deployed_occupied=True 时
    场上前排 1 号 = 普通角色『甲』(swap 场景需要在场交换对象)。"""
    gs = game_state_of(None)
    slots: list[BenchChar | None] = [None] * 9
    slots[0] = BenchChar(slot=1, char_id='开拓者·欢愉', star=4)
    gs.observe(gs.bench, bench_view_of_slots(slots),
               evidence='t', sig=_SIG_OBS)
    if deployed_occupied:
        gs.observe(gs.front_row,
                   [Unit(char_id='甲', star=1, equips=[], slot=1)],
                   evidence='t', sig=_SIG_OBS)
    return gs


def test_swap_report_normalizes_trailblazer_form_to_target_row() -> None:
    """swap 上报有归一:开拓者换排上场 → char_id 切换目标排形态。"""
    gs = _gs_with_bench_trailblazer(deployed_occupied=True)
    out = report_action_swap_deploy_param(
        gs, CwActionSwapDeployParam(deployed_idx=0, bench_idx=0), sig=_SIG)
    assert out.applied, f'swap 应成功,实得 {out.reason!r}'
    dep = deployed_slots_of(gs)
    assert dep[0].char_id == '开拓者·记忆', \
        f'换到前排 → 记忆形态,实得 {dep[0].char_id!r}'
    assert dep[0].position_pref == 'front', '排归属同步'


def test_deploy_move_report_lacks_form_normalization_current() -> None:
    """现状缺陷锚:deploy_move 上报缺归一——开拓者拖上场后排变了、
    形态(char_id)不切换。归一口统一后,本断言翻转为期待
    『开拓者·记忆』(申报的缺陷修复,禁顺带静默改)。"""
    gs = _gs_with_bench_trailblazer(deployed_occupied=False)
    out = report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='front',
                                    faction=''),
        sig=_SIG)
    assert out.applied, f'部署应成功,实得 {out.reason!r}'
    dep = deployed_slots_of(gs)
    assert dep[0].position_pref == 'front', '排归属写入'
    assert dep[0].char_id == '开拓者·欢愉', \
        f'现状 = 形态不随排切换,实得 {dep[0].char_id!r}'
