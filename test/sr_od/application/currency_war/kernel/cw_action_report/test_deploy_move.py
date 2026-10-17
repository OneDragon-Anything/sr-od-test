"""report_action_deploy_move_param 上场锁守卫测试(镜像 src =
kernel/cw_action_report/deploy_move.py 的该被测函数,按拆目录规范落位;
同函数既有机制测试 = kernel/test_deploy.py〔超限只读复用〕)。

测试面依据 = 迭代 T-30 星核猎手契约设计(v2.1 定稿,迭代目录
.debug/progress/2026-09-23-invest-effects-calc)§2.4 + §4 锁 5:
- **实例语义**:锁期内对**被锁 uid** 的流萤 deploy_move = applied=False
  零写(reason=deploy_locked:*);同窗购入的同名流萤(uid=None)与
  合成产物(uid=None)部署放行;生效序位推进 ≥ 解锁序位后被锁张部署
  成功;
- **fail-open 面**:锁域/生效序位缺读 = 放行(live 身份失配的模型侧
  口径,守卫只按 GameState 锁记录状态拦,披露键
  env_battle_lock_live_identity_loss)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_deploy_move_param,
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
    CwActionDeployMoveParam,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='test-seed',
                        mode='compute')
_SIG_ACT = ChannelSig(family='logic_action', actor='CwScreenPrep')

_UNLOCK = (1, 9)


def _make_gs(*, bench_units: list[Unit], node_pos: tuple[int, int] | None,
             locks: tuple | None = (('流萤', 1, _UNLOCK),),
             ) -> GameState:
    """观察面组装:bench 直构 + deployed 空视图 + 生效序位观察锚定 +
    锁域 logic 直写播种(locks=None = 不种,直构未写形态)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots: list[BenchSlot | None] = [BenchSlot(kind='empty')] * 9
    for i, u in enumerate(bench_units):
        slots[i] = BenchSlot(kind='unit', unit=u)
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.deployed,
               DeployedView(front_slots=[None] * 4, back_slots=[None] * 6),
               sig=_SIG_OBS)
    if node_pos is not None:
        gs.observe(gs.node_pos, node_pos, sig=_SIG_OBS)
    if locks is not None:
        gs.write_logic(gs.env_grant_deploy_locks, locks,
                       produced_by='test-seed', sig=_SIG_LOGIC)
    return gs


def _param(bench_idx: int = 0) -> CwActionDeployMoveParam:
    return CwActionDeployMoveParam(bench_idx=bench_idx, to_row='back',
                                   to_slot=1, faction='星核猎手')


def test_locked_uid_deploy_refused_zero_write() -> None:
    """锁期内被锁 uid 直部署拒(设计 §4 锁 5):applied=False、reason =
    deploy_locked:*,bench/deployed 零写(陈旧提案拒绝同款零写形态)。"""
    gs = _make_gs(bench_units=[Unit(char_id='流萤', star=1, uid=1)],
                  node_pos=(1, 7))
    dep_before = gs.deployed.value
    bench_before = gs.bench.value
    out = report_action_deploy_move_param(gs, _param(), _SIG_ACT)
    assert out.applied is False
    assert out.reason == 'deploy_locked:流萤#uid1#unlock1-9'
    assert gs.deployed.value == dep_before, 'deployed 零写'
    assert gs.bench.value == bench_before, 'bench 零写'


def test_purchased_and_merged_units_pass() -> None:
    """同窗购入的同名流萤(uid=None)与合成产物(uid=None)部署放行
    (实例粒度:锁 = 环境送的那张,设计 §5-2 用户裁定)。"""
    gs = _make_gs(bench_units=[Unit(char_id='流萤', star=1, uid=None)],
                  node_pos=(1, 7))
    out = report_action_deploy_move_param(gs, _param(), _SIG_ACT)
    assert out.applied is True
    back = deployed_indexed_of_view(gs.deployed.value)[4:]
    assert back[0] is not None and back[0].char_id == '流萤', '落后排槽 1'


def test_unlocked_after_effective_reaches_unlock() -> None:
    """生效序位推进 ≥ 解锁序位(第 K+1 节点起)后被锁张部署成功(比对
    自愈,记录滞留不清理)。"""
    gs = _make_gs(bench_units=[Unit(char_id='流萤', star=1, uid=1)],
                  node_pos=_UNLOCK)
    out = report_action_deploy_move_param(gs, _param(), _SIG_ACT)
    assert out.applied is True


def test_fail_open_when_locks_or_effective_missing() -> None:
    """锁域缺读 / 生效序位缺读 = 放行(守卫只按 GameState 锁记录状态
    拦;缺无比对基准 fail-open,live 重观察丢 uid 的模型侧同口径)。"""
    gs = _make_gs(bench_units=[Unit(char_id='流萤', star=1, uid=1)],
                  node_pos=(1, 7), locks=None)
    assert report_action_deploy_move_param(
        gs, _param(), _SIG_ACT).applied is True
    gs = _make_gs(bench_units=[Unit(char_id='流萤', star=1, uid=1)],
                  node_pos=None)
    assert report_action_deploy_move_param(
        gs, _param(), _SIG_ACT).applied is True
