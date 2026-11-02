"""strategy_bond_tier_fired 域测试(镜像 src = kernel/cw_game_state.py 的
Field/schema 独立键/种子/rebuild 登记 + kernel/cw_projection_audit.py 的
strategy_bond_tier_fired 审计行)。

测试面依据 = 迭代设计 designs/T-271-mengjing-dawutai.md §2.2 闩域 +
fields.md 组判据(先例 = 同目录 test_strategy_conditional_done_snapshot.py
同构形;梦境大舞台 id 252301 首例):
- 快照存续:闩值进快照 → restore 往返逐位相等(tuple-of-str 不漂移为
  list——rebuild 登记在位为前提,未登记域恢复面 = 静默类型漂移);
  复合键 '<卡名>#<档位>' 逐位保真 = 恢复局逐档跳过判定天然闭合,不重发;
- 冷建种子底座 = ()(A 类,同 strategy_conditional_done 种子族);
- 审计行:PROJECTION_AUDIT 出 strategy_bond_tier_fired 行
  (process_only,条件评估真值无观察读端;容器字段完备性纪律的显式锁,
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
    """种子底座(冷建空集)+ 快照→恢复类型不变(tuple-of-str)+ 逐位
    相等——闩随快照存续 = 恢复局(离线回放)检查腿跳过判定天然闭合,
    不重发(降档再回不弹同口径)。"""
    seed_gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(seed_gs)
    assert seed_gs.strategy_bond_tier_fired.value == (), '冷建空底座'

    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True
    gs.write_logic(gs.strategy_bond_tier_fired,
                   ('梦境大舞台#3', '梦境大舞台#7'),
                   produced_by='test-seed', evidence='t:fired', sig=_LSIG)
    snap = gs.full_state_snapshot()

    restored = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(restored, snap)
    dv = restored.strategy_bond_tier_fired.value
    assert dv == ('梦境大舞台#3', '梦境大舞台#7'), f'闩值往返失真: {dv!r}'
    assert isinstance(dv, tuple) and isinstance(dv[0], str), \
        'tuple-of-str 不漂移为 list(rebuild 登记面)'

    # 恢复局跳过判定语义(域消费面):已闩复合键在册 = 对应档跳过
    # (此处只锁域值语义载体,检查腿行为归 cw_gain_chain 锁文件)。


def test_audit_row_declared_process_only() -> None:
    """对账申报(容器字段完备性纪律):strategy_bond_tier_fired 必须在
    PROJECTION_AUDIT 登记行,行状态 = process_only(条件评估真值非观察
    投影,无观察读端;strategy_conditional_done 行同构)。"""
    from sr_od.application.currency_war.kernel.cw_projection_audit import (
        AUDIT_PROCESS_ONLY,
        PROJECTION_AUDIT,
    )
    row = PROJECTION_AUDIT.get('strategy_bond_tier_fired')
    assert row is not None, '登记行在册'
    assert row.status == AUDIT_PROCESS_ONLY, '无观察读端 → process_only'
