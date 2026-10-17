"""report_action_swap_deploy_param 上场锁守卫测试(镜像 src =
kernel/cw_action_report/swap_deploy.py 的该被测函数,按拆目录规范落位;
同函数既有机制测试 = kernel/test_deploy.py〔超限只读复用〕)。

测试面依据 = 迭代 T-30 星核猎手契约设计(v2.1 定稿,迭代目录
.debug/progress/2026-09-23-invest-effects-calc)§2.4 + §4 锁 5:
bench ↔ deployed 对调 = bench 单位经对调上场的**第二条直部署通道**,
与 deploy_move 同核守卫(deploy_lock_block_reason 单一源)——锁期内对
被锁 uid 的流萤对调 = applied=False 零写;解锁后对调成功。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_swap_deploy_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
    deployed_indexed_of_view,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionSwapDeployParam,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='test-seed',
                        mode='compute')
_SIG_ACT = ChannelSig(family='logic_action', actor='CwScreenPrep')

_UNLOCK = (1, 9)


def _make_gs(*, bench_unit: Unit, node_pos: tuple[int, int],
             locks: tuple = (('流萤', 1, _UNLOCK),)) -> GameState:
    """观察面组装:bench 0 号槽上场单位 + deployed 前排 0 号槽占位 +
    生效序位观察锚定 + 锁域 logic 直写播种。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots: list[BenchSlot | None] = [BenchSlot(kind='empty')] * 9
    slots[0] = BenchSlot(kind='unit', unit=bench_unit)
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.deployed,
               DeployedView(front_slots=[Unit(char_id='刃', star=1),
                                         None, None, None],
                            back_slots=[None] * 6), sig=_SIG_OBS)
    gs.observe(gs.node_pos, node_pos, sig=_SIG_OBS)
    gs.write_logic(gs.env_grant_deploy_locks, locks,
                   produced_by='test-seed', sig=_SIG_LOGIC)
    return gs


def _param() -> CwActionSwapDeployParam:
    return CwActionSwapDeployParam(deployed_idx=0, bench_idx=0)


def test_locked_uid_swap_refused_zero_write() -> None:
    """锁期内被锁 uid 经对调上场拒(设计 §4 锁 5 第二直部署通道):
    applied=False、reason = deploy_locked:*,bench/deployed 零写。"""
    gs = _make_gs(bench_unit=Unit(char_id='流萤', star=1, uid=1),
                  node_pos=(1, 7))
    dep_before = gs.deployed.value
    bench_before = gs.bench.value
    out = report_action_swap_deploy_param(gs, _param(), _SIG_ACT)
    assert out.applied is False
    assert out.reason == 'deploy_locked:流萤#uid1#unlock1-9'
    assert gs.deployed.value == dep_before, 'deployed 零写'
    assert gs.bench.value == bench_before, 'bench 零写'


def test_swap_passes_after_unlock() -> None:
    """生效序位 ≥ 解锁序位后被锁张对调上场成功(比对自愈)。"""
    gs = _make_gs(bench_unit=Unit(char_id='流萤', star=1, uid=1),
                  node_pos=_UNLOCK)
    out = report_action_swap_deploy_param(gs, _param(), _SIG_ACT)
    assert out.applied is True
    assert deployed_indexed_of_view(gs.deployed.value)[0].char_id == '流萤'


def test_purchased_same_name_swap_passes() -> None:
    """购入同名张(uid=None)锁期内对调放行(实例粒度,设计 §5-2)。"""
    gs = _make_gs(bench_unit=Unit(char_id='流萤', star=1, uid=None),
                  node_pos=(1, 7))
    assert report_action_swap_deploy_param(
        gs, _param(), _SIG_ACT).applied is True
