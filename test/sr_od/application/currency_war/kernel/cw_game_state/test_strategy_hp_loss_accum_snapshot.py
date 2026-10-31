"""strategy_hp_loss_accum 域测试(镜像 src = kernel/cw_game_state.py 的
Field/schema 独立键/种子/rebuild 登记 + kernel/cw_projection_audit.py 的
strategy_hp_loss_accum 审计行)。

测试面依据 = 迭代设计 designs/T-142-baoxian.md §4 锁 8 + §2.2(种子
分诊 A 类:0 = 无累积语义中性,种 0 不伪装已触发):
- 快照存续:累积值进快照 → restore 往返逐位相等(int 保型直通免
  rebuild 登记——_json_safe 对 int 无漂移,env_grant_uid_seq 同款);
- 冷建种子底座 = 0(触发函数累加取模零 None 防御);
- 登记四件:schema 独立键版本 1 + 审计行 PROCESS_ONLY(容器字段完备性
  纪律的显式锁;fields.md §3.5.6c 为正本登记面,文档完备性归评审把关,
  本锁锁代码登记面)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    DEFAULT_GS_SCHEMA,
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    restore_state_snapshot,
    seed_opening_state,
)

_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')


def test_seed_zero_and_snapshot_roundtrip() -> None:
    """种子底座(冷建 0 = 无累积语义中性)+ 快照→恢复类型不变(int 保型
    直通)+ 逐位相等——累积值随快照存续 = 恢复局档位边界不位移(无 done
    闩的周期型触发器,累积器即跨战结转唯一载体)。"""
    seed_gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(seed_gs)
    assert seed_gs.strategy_hp_loss_accum.value == 0, '冷建零底座'

    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True
    gs.write_logic(gs.strategy_hp_loss_accum, 45,
                   produced_by='test-seed', evidence='t:accum', sig=_LSIG)
    snap = gs.full_state_snapshot()

    restored = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(restored, snap)
    dv = restored.strategy_hp_loss_accum.value
    assert dv == 45 and isinstance(dv, int), \
        f'累积值往返失真(int 保型直通): {dv!r}'


def test_schema_independent_key_registered() -> None:
    """schema 独立键版本 1(同 env_grants_done 先例不并入他域 bump——
    他域本体未变,bump 会对旧档谎报域内容变更)。"""
    assert DEFAULT_GS_SCHEMA.get('strategy_hp_loss_accum') == 1, \
        'schema 独立键未登记'


def test_audit_row_declared_process_only() -> None:
    """对账申报(容器字段完备性纪律):strategy_hp_loss_accum 必须在
    PROJECTION_AUDIT 登记行,行状态 = process_only(发放记账过程量,
    无观察读端;env_grants_done/ore_declared_done 行同构)。"""
    from sr_od.application.currency_war.kernel.cw_projection_audit import (
        AUDIT_PROCESS_ONLY,
        PROJECTION_AUDIT,
    )
    row = PROJECTION_AUDIT.get('strategy_hp_loss_accum')
    assert row is not None, '登记行在册'
    assert row.status == AUDIT_PROCESS_ONLY, '无观察读端 → process_only'
