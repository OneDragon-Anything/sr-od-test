"""strategy_conditional_done 域测试(镜像 src = kernel/cw_game_state.py 的
Field/schema 独立键/种子/rebuild 登记 + kernel/cw_projection_audit.py 的
strategy_conditional_done 审计行)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§4 锁 6/7:
- 快照存续:一次性标志位值进快照 → restore 往返逐位相等(tuple-of-str 不漂移为
  list——rebuild 登记在位为前提,未登记域恢复面 = 静默类型漂移);
- 每局全新创建种子初始值 = ()(A 类,同 env_grants_done 种子族);
- 审计行:PROJECTION_AUDIT 出 strategy_conditional_done 行
  (process_only,发放登记事实无观察读端;状态容器字段完备性纪律的显式锁,
  表完备性另有抽检测试兜底)。
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


def test_seed_empty_and_snapshot_roundtrip() -> None:
    """种子初始值(每局全新创建空集)+ 快照→恢复类型不变(tuple-of-str)+ 逐位
    相等——done 随快照存续 = 恢复局(离线回放)检查效果条目跳过判定天然闭合,
    不重发。"""
    seed_gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(seed_gs)
    assert seed_gs.strategy_conditional_done.value == (), '每局全新创建空初始值'

    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True
    gs.write_logic(gs.strategy_conditional_done, ('规模效应',),
                   produced_by='test-seed', evidence='t:done', sig=_LSIG)
    snap = gs.full_state_snapshot()

    restored = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(restored, snap)
    dv = restored.strategy_conditional_done.value
    assert dv == ('规模效应',), f'一次性标志位值往返失真: {dv!r}'
    assert isinstance(dv, tuple) and isinstance(dv[0], str), \
        'tuple-of-str 不漂移为 list(rebuild 登记面)'

    # 恢复局跳过判定语义(域消费面):已置一次性标志位卡名已登记 = 检查效果条目跳过
    # (此处只锁域值语义载体,检查效果条目行为归 cw_gain_chain 锁文件)。


def test_audit_row_declared_process_only() -> None:
    """对账申报(状态容器字段完备性纪律):strategy_conditional_done 必须在
    PROJECTION_AUDIT 登记行,行状态 = process_only(发放登记事实非观察
    投影,无观察读端;env_grants_done 行同构)。"""
    from sr_od.application.currency_war.kernel.cw_projection_audit import (
        AUDIT_PROCESS_ONLY,
        PROJECTION_AUDIT,
    )
    row = PROJECTION_AUDIT.get('strategy_conditional_done')
    assert row is not None, '登记行已登记'
    assert row.status == AUDIT_PROCESS_ONLY, '无观察读端 → process_only'
