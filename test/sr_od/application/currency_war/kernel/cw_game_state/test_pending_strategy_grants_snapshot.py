"""策略延时发放队列快照存续测试(镜像 src = kernel/cw_game_state.py
的 pending_strategy_grants 域 + restore_state_snapshot rebuild 登记)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§4 锁 6(rebuild
登记在位为前提——未登记域恢复面拿 list-of-lists = 静默类型漂移):
①带队列快照 → restore 往返逐位相等;②空队列快照往返 = ();③快照无
该键(无快照接管局)→ 恢复域值 None = 未写形态。"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    restore_state_snapshot,
)


def test_pending_strategy_grants_snapshot_round_trip() -> None:
    """快照存续(锁 6):倒计时队列随快照往返逐位相等;live 恢复局队列
    悬置 = 模型推算知识存续(不对称申报,发放类效果条目 sim-only)。"""
    sig = ChannelSig(family='logic_action', actor='test-seed',
                     mode='compute')
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    queue = (('人才激励', 4), ('人才激励', 0))
    gs.write_logic(gs.pending_strategy_grants, queue,
                   produced_by='test-seed', evidence='t:queue', sig=sig)
    snap = gs.full_state_snapshot()
    assert 'pending_strategy_grants' in snap['values'], '队列进快照'

    gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs2, snap)
    assert gs2.pending_strategy_grants.value == queue, '往返逐位相等'

    gs3 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs3.write_logic(gs3.pending_strategy_grants, (), produced_by='test-seed',
                    evidence='t:queue', sig=sig)
    snap3 = gs3.full_state_snapshot()
    gs4 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs4, snap3)
    assert gs4.pending_strategy_grants.value == (), '空队列往返 = ()'

    snap_no_key = {'values': {}, 'prov': {}}
    gs5 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs5, snap_no_key)
    assert gs5.pending_strategy_grants.value is None, \
        '快照无键 → 未写形态(接管局队列空,递减/发放零触发)'
