"""strategy_char_grant_bindings 域测试(镜像 src = kernel/cw_game_state.py
的 Field/schema 独立键/种子/rebuild 登记 + kernel/cw_projection_audit.py
的 strategy_char_grant_bindings 审计行;按被测域拆目录规范落位,先例 =
同目录 test_strategy_conditional_done_snapshot.py)。

测试面依据 = 原稿锁面
原稿锁面§2.2 域四件套义务:

- 快照存续:绑定 dict 进快照 → restore 往返逐位相等(str→str 双显式
  化不漂移——rebuild 登记在位为前提,未登记域恢复面 = 静默类型漂移);
- 每局全新创建种子初始值 = {}(A 类,同 pending_item_grants 种子族——域值恒非
  None,复制发放类效果条目键查判定零 None 防御);
- 审计行:PROJECTION_AUDIT 出 strategy_char_grant_bindings 行
  (process_only,掷骰结果非观察投影,无观察读端)。
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

_CARD = '价值投资·金'


def test_seed_empty_and_snapshot_roundtrip() -> None:
    """种子初始值(每局全新创建空 dict)+ 快照→恢复类型不变(str→str dict)+
    逐位相等——绑定随快照存续 = 恢复局复制发放类效果条目判据不丢。"""
    seed_gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(seed_gs)
    assert seed_gs.strategy_char_grant_bindings.value == {}, '每局全新创建空初始值'

    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True
    gs.write_logic(gs.strategy_char_grant_bindings, {_CARD: '青雀'},
                   produced_by='test-seed', evidence='t:bind', sig=_LSIG)
    snap = gs.full_state_snapshot()

    restored = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(restored, snap)
    dv = restored.strategy_char_grant_bindings.value
    assert dv == {_CARD: '青雀'}, f'绑定值往返失真: {dv!r}'
    assert isinstance(dv, dict) and all(
        isinstance(k, str) and isinstance(v, str)
        for k, v in dv.items()), 'str→str dict 不漂移(rebuild 登记面)'


def test_audit_row_declared_process_only() -> None:
    """对账申报(状态容器字段完备性纪律):strategy_char_grant_bindings 必须
    在 PROJECTION_AUDIT 登记行,行状态 = process_only(掷骰结果非观察
    投影,无观察读端;strategy_conditional_done 行同构)。"""
    from sr_od.application.currency_war.kernel.cw_projection_audit import (
        AUDIT_PROCESS_ONLY,
        PROJECTION_AUDIT,
    )
    row = PROJECTION_AUDIT.get('strategy_char_grant_bindings')
    assert row is not None, '登记行已登记'
    assert row.status == AUDIT_PROCESS_ONLY, '无观察读端 → process_only'
