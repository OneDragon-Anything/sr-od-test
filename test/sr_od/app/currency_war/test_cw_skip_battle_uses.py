"""免战牌次数类余量链行为锁(授予→余额→消费全链)。

设计依据(持久锚):
- 效果语义正本 = docs/develop/currency_war/game_state/effect-domain.md
  §8 免战牌条目(NODE_ENTER×WHILE_HELD×STATE,duties=track;次数余量
  唯一驱动 = 跳过执行成功回执 consume_use,达 2 移除;+30 经验 = 选牌
  当场)、§3(统一单调计数器模型)与 §4(递减余期与单调 counter 语义
  等价,表示法迁移候裁前按现行 remaining_uses 表示锁行为);
- 载体正本 = BoardState 数据结构设计(docs/develop/sr_od/application/
  currency_war/changes/2026-09-11-unified-state/details/
  BoardState-数据结构设计.md)§3.2.19(免战牌激活态与剩余跳过次数,
  正本 = effect_inventory.remaining_uses)/§5.1(登记播种与消费挂点)/
  §8.7 批次三件 5(EffectSpec 条目)与件 8(账本→字段桥三分);
- 卡文原文(效果语义出处)= data/cw_invest_data.py PlazaAugment
  id='151301'「进入战斗节点时,直接跳过战斗并进入下一个节点,可生效
  2次。获得30点经验。」

与 test_cw_board_state_batch3.py 的分工(测试纪律「同层不重复」):
彼文件锁**单链节**(登记播种/consume_use 单元/burst 桥零额度 no-op/
挂点接线烟雾/spec 条目 id 面);本文件锁**同一局内全链流**——授予
(登记 + burst 桥同点采样,生产登记挂点形状)→余额(卡文无刷新腿,
两桥零注入,全链零 Field 写)→节点推进(余量正交:次数类余量不被
节点推进吞,与 remaining_nodes 两维互不排斥)→消费(2→1→0 归零
离场)→缺位保守。混合清单求和段(免战牌+双手狸)证明桥活线,
负断言非空转。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_board_state import (
    BS_SCHEMA_VERSION,
    BoardState,
    apply_effect_burst_grant,
    grant_effect_node_refresh_balance,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    DurationKind,
    DutyFlags,
    EffectKind,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)

_SPEC_ID: str = '151301'   # 免战牌 plaza 稳定 id(= EffectSpec.id,恒稳)


def test_skip_card_grant_balance_consume_chain() -> None:
    """授予→余额→消费全链(一局同流;链节单元锁在 batch3,本锁锁流)。

    覆盖申报:生产登记挂点形状(登记 + burst 桥同点)/节点 tick 挂点
    形状(advance_node advanced 位闸门 + per-node 桥)/跳过递减
    (consume_use)。接线存在性烟雾与链节单元断言归 batch3,不在此重复。
    """
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    seq0 = bs.write_seq

    # —— 授予段:登记播种 + burst 桥同点(免战牌零刷新腿 → 余额零注入)
    bs.effects.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_t=5)
    apply_effect_burst_grant(bs, STRATEGY_EFFECTS['免战牌'])
    entry = bs.effects.first(_SPEC_ID)
    assert entry is not None
    assert entry.remaining_uses == 2 and entry.remaining_nodes is None, \
        '播种双轨:次数类播 remaining_uses=2,节点维为空'
    assert bs.free_refresh_balance.value is None, \
        '免战牌卡文无免费刷新腿 → burst 桥零注入(余额维持未写)'
    assert bs.write_seq == seq0, '授予段零 Field 写'

    # —— 节点推进段:advanced 位触发 per-node 桥(生产 tick 挂点形状);
    # 免战牌无 per-node 腿 → 余额不动;次数类余量与节点推进正交
    advanced, expired = bs.effects.advance_node(6)
    assert advanced is True and expired == []
    grant_effect_node_refresh_balance(bs)
    assert bs.free_refresh_balance.value is None, 'per-node 桥零注入'
    assert bs.effects.first(_SPEC_ID).remaining_uses == 2, \
        '节点推进不吞次数余量(唯一驱动=consume_use,两维正交)'
    assert bs.write_seq == seq0, '节点段仍零 Field 写'

    # —— 桥活线证人 + 混合清单求和形状:同账本并入有腿条目(双手狸
    # on_node_enter=2)后,求和恰 = 有腿条目自身额度。免战牌零贡献
    # 由此与「桥死」的空转绿区分(正样活线锁另在 batch3 burst/per_node)
    bs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                 acquired_t=5)
    advanced2, _expired2 = bs.effects.advance_node(7)
    assert advanced2 is True
    grant_effect_node_refresh_balance(bs)
    assert bs.free_refresh_balance.value == 2, \
        '混合清单求和恰 = 双手狸自身 2(免战牌零贡献,桥活线)'
    assert bs.free_refresh_balance.source == 'logic'
    assert bs.free_refresh_balance.evidence == 'effect_per_node'

    # —— 消费段:跳过执行落地 2→1→0,归零离场;消费不改写余额
    assert bs.effects.consume_use(_SPEC_ID) == 1
    assert bs.effects.first(_SPEC_ID) is not None, '尚有余量不移除'
    assert bs.effects.consume_use(_SPEC_ID) == 0
    assert bs.effects.first(_SPEC_ID) is None, '用尽 = 效果离场'
    assert bs.effects.consume_use(_SPEC_ID) is None, '缺位保守零动作'
    assert bs.free_refresh_balance.value == 2, '消费链不改写余额'


def test_skip_card_registry_semantics_gate() -> None:
    """卡文原文 ↔ 规格语义字段登记门(逐句映射)。

    id/duration_uses/xp_instant 三字段已由 batch3
    test_skip_battle_spec_entry_matches_base_registry 辖,本锁补其余
    语义面;其中「payload 零刷新腿」是两桥零注入行为的注册表前提,
    建模漂移(给免战牌误加刷新腿)在此与链锁双红。锁红 = 建模语义
    判定被改:对照卡文逐句重推后登记新语义,禁机械跟绿。
    """
    spec = STRATEGY_EFFECTS['免战牌']
    assert spec.trigger is TriggerKind.NODE_ENTER, \
        '「进入战斗节点时」= NODE_ENTER(节点推进族)'
    assert spec.duration is DurationKind.WHILE_HELD, \
        '「可生效2次」= 次数类持有期(余量用尽即离场,非固定节点数)'
    assert spec.category is EffectKind.STATE, \
        '跳过机制+自得经验归 STATE 族(经验发给自己;跳过本体由次数余量承载)'
    assert spec.duties == DutyFlags(track=True), \
        'duties=track 唯一(无预知/无姿态消费面;账本零决策消费=详设 §5.1 过渡口径)'
    payload = spec.payload
    assert payload.free_refresh_burst == 0, '无即时刷新腿(burst 桥零注入前提)'
    assert payload.free_refresh_per_node == 0, \
        '无每节点刷新腿(per-node 桥零注入前提)'
    assert payload.free_refresh_cond_gold_above == 0 \
        and payload.free_refresh_cond_gold_step == 0 \
        and payload.free_refresh_cond_cap == 0, '无条件刷新三元组'
    assert payload.xp_per_node == 0, \
        '经验腿仅选牌当场一支(xp_instant=30,batch3 已锁数值)'
