"""forge_privilege_charges_left / forge_privilege_gained_count 域测试
(镜像 src = kernel/cw_game_state.py 的 Field/schema 独立键/缺省承载 +
kernel/cw_projection_audit.py 的同名审计行 + cw_effect_inventory 常量
与登记面一致)。

测试面依据 = 迭代设计 designs/T-418-duanye-zhuanjia-ren.md §2 裁决点
2-A(Field 缺省承载开局值,零置位写状态分支——无卡局不消费零行为差;
「耗尽后可充能」次数契约与免战牌 remaining_uses「用尽即效果离场」
分野,次数账权威版本不骑效果账本载体):
- 每局全新创建缺省 = 1/0(声明即真值);seed_opening_state 零置位(种子后值
  与来源双不变);
- 快照存续:次数/计数值进快照 → restore 往返逐位相等(int 保型直通
  免 rebuild 登记,env_grant_uid_seq 同款);
- 登记四件:schema 独立键版本 1(不并入他域 bump)+ 审计行
  PROCESS_ONLY × 2(状态容器字段完备性纪律的显式锁);
- 常量与登记面单一源:辖域角色/持卡键 = STRATEGY_GRANTS 同卡条目
  chars_immediate/advisor 一致(效果条目1 顾问解锁已登记零改动的正向护行)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    FORGE_PRIVILEGE_CARD,
    FORGE_PRIVILEGE_CHAR,
    FORGE_PRIVILEGE_GAINS_PER_CHARGE,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    DEFAULT_GS_SCHEMA,
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    restore_state_snapshot,
    seed_opening_state,
)

_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')


def test_field_defaults_carry_opening_state() -> None:
    """缺省承载锁:直构 GameState 次数 =1/计数 =0;seed_opening_state
    后值与来源双不变(零置位写状态分支——种子面一个不种,声明即开局真值)。"""
    direct = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert direct.forge_privilege_charges_left.value == 1, \
        '次数账缺省 = 基础 1 次'
    assert direct.forge_privilege_gained_count.value == 0, '计数器缺省 0'

    seeded = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(seeded)
    assert seeded.forge_privilege_charges_left.value == 1, \
        '种子面零置位(值不变)'
    assert seeded.forge_privilege_charges_left.evidence is None, \
        '种子面零置位(来源不变,非种子通道)'
    assert seeded.forge_privilege_gained_count.value == 0


def test_schema_independent_keys_registered() -> None:
    """schema 独立键版本 1 × 2(同 env_grants_done 先例不并入他域
    bump——他域本体未变,bump 会对旧档谎报域内容变更)。"""
    assert DEFAULT_GS_SCHEMA.get('forge_privilege_charges_left') == 1, \
        '次数账独立键未登记'
    assert DEFAULT_GS_SCHEMA.get('forge_privilege_gained_count') == 1, \
        '计数器独立键未登记'


def test_snapshot_roundtrip_int_straight_through() -> None:
    """快照→恢复类型不变(int 保型直通)+ 逐位相等——次数/计数值随
    快照存续 = 恢复局次数边界不位移。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.forge_privilege_charges_left, 2,
                   produced_by='test-seed', evidence='t:recharge', sig=_LSIG)
    gs.write_logic(gs.forge_privilege_gained_count, 10,
                   produced_by='test-seed', evidence='t:count', sig=_LSIG)
    snap = gs.full_state_snapshot()

    restored = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(restored, snap)
    charges = restored.forge_privilege_charges_left.value
    count = restored.forge_privilege_gained_count.value
    assert charges == 2 and isinstance(charges, int), \
        f'次数往返失真(int 保型直通): {charges!r}'
    assert count == 10 and isinstance(count, int), \
        f'计数往返失真(int 保型直通): {count!r}'


def test_audit_rows_declared_process_only() -> None:
    """对账申报(状态容器字段完备性纪律):两键必须在 PROJECTION_AUDIT
    登记行,行状态 = process_only(次数/计数 = 卡文推算知识,无观察
    读端;strategy_hp_loss_accum 行同构)。"""
    from sr_od.application.currency_war.kernel.cw_projection_audit import (
        AUDIT_PROCESS_ONLY,
        PROJECTION_AUDIT,
    )
    for name in ('forge_privilege_charges_left',
                 'forge_privilege_gained_count'):
        row = PROJECTION_AUDIT.get(name)
        assert row is not None, f'{name} 登记行已登记'
        assert row.status == AUDIT_PROCESS_ONLY, f'{name} process_only'


def test_constants_tie_to_registry_single_source() -> None:
    """常量与登记面单一源:持卡键/辖域角色 = STRATEGY_GRANTS 同卡条目
    chars_immediate/advisor 一致(效果条目1 顾问解锁+入商店登记面已登记零改动
    的正向护行)+ 扩次阈值 = 卡面数值 10。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_BINDINGS,
        STRATEGY_GRANTS,
    )
    grant = STRATEGY_GRANTS[FORGE_PRIVILEGE_CARD]
    assert grant.advisor is True, '效果条目1 顾问型已登记'
    assert grant.chars_immediate == (FORGE_PRIVILEGE_CHAR,), \
        '辖域角色 = 登记面 chars_immediate 单成员'
    assert FORGE_PRIVILEGE_CHAR in STRATEGY_BINDINGS[FORGE_PRIVILEGE_CARD][1], \
        '顾问角色绑定条目已登记'
    assert FORGE_PRIVILEGE_GAINS_PER_CHARGE == 10, '扩次阈值 = 卡面数值'
