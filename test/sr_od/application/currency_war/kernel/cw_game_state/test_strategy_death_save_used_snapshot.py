"""strategy_death_save_used 域测试(镜像 src = kernel/cw_game_state.py 的
Field/schema 独立键/种子 + kernel/cw_projection_audit.py 的
strategy_death_save_used 审计行)。

测试面依据 = 迭代设计 designs/T-323-cang-yishou.md §2.2 配套义务 +
§4 锁 8(字段完备性;先例 = 同目录 test_strategy_conditional_done_
snapshot.py):
- 种子分诊 = B 类(None = 未判定系设计语义,开局不种——种 False 会把
  「未判定」伪装成「已判定未触发」,同 hp_floor_triggered 先例);
- 快照存续:一次性标志位值进快照 → restore 往返逐位相等(bool 保型直通免 rebuild
  登记,同 env_grant_uid_seq 先例——未登记域若发生类型漂移在此暴露);
- 审计行:PROJECTION_AUDIT 出 strategy_death_save_used 行(process_only,
  发放簿记过程量无观察读端——救援事件 live 由游戏自算自显,一次性标志位 live 零写
  零消费实机(live)和模拟器(sim)两边不对称;容器字段完备性纪律的显式锁,表完备性另有抽检测试
  兜底)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    restore_state_snapshot,
    seed_opening_state,
)

_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')


def test_seed_none_opening_and_snapshot_roundtrip() -> None:
    """种子初始值(开局不种 None)+ 快照→恢复逐位相等(bool 保型直通)
    ——一次性标志位随快照存续 = 接管局不丢(救援一次性跨接管不重发;接管局一次性标志位
    None = 可再救一次,与 hp_floor_triggered 接管形态同款申报)。"""
    seed_gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(seed_gs)
    assert seed_gs.strategy_death_save_used.value is None, \
        '每局全新创建种子初始值应不种(B 类,None = 未判定设计语义)'

    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True
    gs.write_logic(gs.strategy_death_save_used, True,
                   produced_by='test-seed', evidence='t:latch', sig=_LSIG)
    snap = gs.full_state_snapshot()

    restored = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(restored, snap)
    dv = restored.strategy_death_save_used.value
    assert dv is True, f'一次性标志位值往返失真: {dv!r}'
    assert isinstance(dv, bool), 'bool 保型直通(rebuild 免登记前提面)'


def test_audit_row_declared_process_only() -> None:
    """对账申报(容器字段完备性纪律):strategy_death_save_used 必须在
    PROJECTION_AUDIT 登记行,行状态 = process_only(发放簿记过程量非
    观察投影,无观察读端;strategy_conditional_done 行同构)。"""
    from sr_od.application.currency_war.kernel.cw_projection_audit import (
        AUDIT_PROCESS_ONLY,
        PROJECTION_AUDIT,
    )
    row = PROJECTION_AUDIT.get('strategy_death_save_used')
    assert row is not None, '登记行已登记'
    assert row.status == AUDIT_PROCESS_ONLY, '无观察读端 → process_only'
