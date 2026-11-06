"""搜打撤每节点免费刷新腿生效链测试(镜像 src = cw_investments.py
STRATEGY_EFFECTS['搜打撤'] overlay 条目 + cw_game_state.py 节点边界桥
grant_effect_node_refresh_balance;镜像母本 = test_game_state.py
test_gas_station_pick_node_grant_matches_official_text(a 组)/
test_per_node_family_without_now_clause_no_pick_grant(b 组),宿主超限
禁追加故落本拆目录新文件)。

测试面依据 = 迭代设计 designs/T-332-souda-che.md §2.1/§4 锁 1:
- 搜打撤 = (b) 组形(卡文句①无「现在/立刻」立即措辞,
  per_node_pick_node_grant.md §3.2):拿卡当节点不发放,首发放 =
  下一节点边界 +1;
- overlay 条目补齐前 payload 永不入 gs.effects = 节点边界桥恒零
  (登记缺口形态本锁以「登记前边界零发放」承载);
- payload 实例同一性:EffectSpec.payload is STRATEGY_ECONOMY['搜打撤']
  (共享实例单一源,EconomyEffect frozen dataclass,桥鸭子类型读取(duck typing) per_node
  字段与注册行同源)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    GameState,
    apply_effect_burst_grant,
    grant_effect_node_refresh_balance,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
)

_CARD = '搜打撤'


def test_soudache_overlay_payload_single_instance() -> None:
    """payload 实例同一性(共享实例单一源):条目 payload 与注册行
    STRATEGY_ECONOMY['搜打撤'] 同一对象——桥鸭子类型读取的 free_refresh_
    per_node 与注册面单一源,禁字段拷贝第二源。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.payload is STRATEGY_ECONOMY[_CARD], \
        'payload 应引注册行同一实例(禁拷贝第二源)'
    assert spec.payload.free_refresh_per_node == 1, '每节点 +1 载体漂移'
    assert spec.payload.free_refresh_burst == 0, \
        '(b) 组不得携带登记期 burst(拿卡当节点不发放)'


def test_soudache_pick_node_zero_then_next_nodes_plus_one() -> None:
    """腿 1 生效时序(b 组形):拿卡当节点边界零发放(含同节点去重
    与 burst 桥零操作)→ 次节点边界 +1 → 再次节点再 +1。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    # 本节点边界已在拿卡前推进(终结动作上报时序:拿卡晚于边界),
    # 效果登记前边界零发放(零行)。
    gs.effects.advance_node((1, 2))
    grant_effect_node_refresh_balance(gs, frame='p1-r2')
    assert gs.free_refresh_left.value is None, '效果登记前边界零发放(零行)'
    # 登记期:burst 桥按 payload 发放,搜打撤 burst=0 = no-op 零行。
    apply_effect_burst_grant(gs, STRATEGY_EFFECTS[_CARD], frame='p1-r2')
    gs.effects.register_strategy(STRATEGY_EFFECTS[_CARD],
                                 acquired_key=(1, 2))
    assert gs.free_refresh_left.value is None, \
        '(b) 组登记期零发放(拿卡当节点不发放)'
    # 拿卡节点边界去重位(已推进过)不补发。
    adv_same, _ex = gs.effects.advance_node((1, 2))
    if adv_same:
        grant_effect_node_refresh_balance(gs, frame='p1-r2')
    assert gs.free_refresh_left.value is None, '拿卡节点边界去重不补发'
    # 次节点边界 +1(句①「每当你进入新节点时」分支)。
    adv_next, _ex2 = gs.effects.advance_node((1, 3))
    assert adv_next is True
    grant_effect_node_refresh_balance(gs, frame='p1-r3')
    assert gs.free_refresh_left.value == 1, '次节点边界 +1'
    # 再次节点再 +1(逐节点累加)。
    adv_next2, _ex3 = gs.effects.advance_node((1, 4))
    assert adv_next2 is True
    grant_effect_node_refresh_balance(gs, frame='p1-r4')
    assert gs.free_refresh_left.value == 2, '再次节点再 +1(累计)'
