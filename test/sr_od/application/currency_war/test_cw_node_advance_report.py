"""节点推进动作上报 kernel 原语直测:迭代
节点推进上报判据面
(推进生效原语 advance_node_effective / report_node_advance 观察态门 /
observe_node_anchor 锚定处置),2026-10-12-abolish-node-ordinal §3.2 起
节点序位 = (位面, 轮) 元组键。

判据 ↔ 测试对照(landing §3.1 完成判据 + 本迭代 design §2.11 锁 2/3):

- value=None 门挡(攻击 R1 回归锁)        → test_gate_blocks_fresh_container
- v=None 首锚定建账含尾段发放            → test_first_anchor_establishes_and_grants
- source=logic 门挡(重复上报结构不可能)  → test_gate_blocks_unconfirmed_logic
- 门放行推进恰一档                       → test_gate_passes_advances_exactly_one
- 等值观察翻锚定后可再推进               → test_reanchor_unlocks_next_advance
- R<v 丢弃留证(倒退免疫)                → test_stale_reading_dropped
- R>v 补推经原语含尾段发放(跳档不漏发)   → test_repair_advance_ticks_ledger
- 跨位面推进(位面末后继 = 下位面首)      → test_cross_plane_advance
- 越域读数丢弃(位面在表守卫,锁 4)       → test_out_of_domain_reading_dropped
- 终局事件式(P2 末确认,锁 3)            → test_terminal_match_end_event_style
"""

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    GameState,
    effective_node_pos,
    observe_node_anchor,
    report_node_advance,
)
from sr_od.application.currency_war.kernel.cw_investments import STRATEGY_EFFECTS

_ACTOR = 'TestHost'


def _gs_with_double_pair() -> GameState:
    """新容器 + 双手狸在册(每进节点 +2 免费刷新,发放断言活载体)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                 acquired_key=(1, 5))
    return gs


def test_gate_blocks_fresh_container() -> None:
    """value 守卫(攻击 R1 回归锁):新容器 node_pos=(None, 'observation')
    (Field 缺省 source 即 observation)——门必须按 value 在场判定,否则
    开局/恢复局首次终结确认误放行且 candidate 无定义。"""
    gs = _gs_with_double_pair()
    assert report_node_advance(gs, trigger='settle_confirm').applied is False
    assert gs.node_pos.value is None, '零推进'
    assert gs.node_hist_pos is None
    assert gs.free_refresh_left.value is None, '门挡 = 不触效果尾段(零 Field 行)'


def test_first_anchor_establishes_and_grants() -> None:
    """v=None 首锚定行:任何读数经原语落账(observation 确认态)+ 效果尾段。"""
    gs = _gs_with_double_pair()
    token = observe_node_anchor(gs, (1, 1), trigger_screen='货币战争-备战',
                                actor=_ACTOR)
    assert token == 'first_anchor'
    assert gs.node_pos.value == (1, 1) and gs.node_pos.source == 'observation'
    assert gs.node_hist_pos == (1, 1)
    assert gs.free_refresh_left.value == 2, '首锚定即节点进入,尾段发放'


def test_gate_blocks_unconfirmed_logic() -> None:
    """source=logic 门挡:动作推进后未锚定前,任何第二次上报零推进——
    重复上报在结构上不可能(观察态门语义)。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (1, 2), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert gs.node_pos.value == (1, 3) and gs.node_pos.source == 'logic'
    balance_after_first = gs.free_refresh_left.value
    assert report_node_advance(gs, trigger='settle_confirm').applied is False
    assert gs.node_pos.value == (1, 3), '重复上报零推进'
    assert gs.free_refresh_left.value == balance_after_first, '门挡不触尾段'


def test_gate_passes_advances_exactly_one() -> None:
    """门放行:candidate = sequence_next(生效序位),推进恰一档。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (1, 2), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert gs.node_pos.value == (1, 3)
    assert gs.node_hist_pos == (1, 3)
    assert effective_node_pos(gs) == (1, 3)


def test_reanchor_unlocks_next_advance() -> None:
    """等值观察翻锚定:logic 态被同值观察确认后翻 observation,下一终结
    动作解锁——漏点自愈链的解锁半(重试确认可推进)。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (1, 2), trigger_screen='货币战争-备战', actor=_ACTOR)
    report_node_advance(gs, trigger='settle_confirm')
    assert gs.node_pos.source == 'logic'
    assert observe_node_anchor(gs, (1, 3), trigger_screen='货币战争-备战',
                               actor=_ACTOR) == 'reanchor'
    assert gs.node_pos.source == 'observation'
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert gs.node_pos.value == (1, 4)


def test_stale_reading_dropped() -> None:
    """R<v 倒退免疫:不写 + 现值保持(logic 或 observation 态同规)。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (1, 5), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert observe_node_anchor(gs, (1, 4), trigger_screen='货币战争-备战',
                               actor=_ACTOR) == 'stale_dropped'
    assert gs.node_pos.value == (1, 5), '倒退读数不落账'
    assert gs.node_hist_pos == (1, 5)


def test_repair_advance_ticks_ledger() -> None:
    """R>v 补推经原语(攻击 F2① 回归锁):漏上报自愈路径同样触发效果
    尾段——账本 advance_node 去重是序位相等判,补推不 tick 即跳档漏发。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (1, 2), trigger_screen='货币战争-备战', actor=_ACTOR)
    report_node_advance(gs, trigger='settle_confirm')   # → (1, 3)
    assert gs.free_refresh_left.value == 4   # 节点 (1,2) + (1,3) 各 +2
    assert observe_node_anchor(gs, (1, 5), trigger_screen='货币战争-备战',
                               actor=_ACTOR) == 'advance'
    assert effective_node_pos(gs) == (1, 5)
    assert gs.free_refresh_left.value == 6, \
        '补推节点 (1,5) 当帧拿到发放(漏 tick 即永久少一档)'


def test_cross_plane_advance() -> None:
    """跨位面推进(design §2.11 锁 2):P1 位面末 (1,9) 确认 → (2,1)
    (后继原语跨位面);跨位面字典序严格性 (1,10) < (2,1) 由锚定倒退
    免疫分支自然严格(修饰局形态同构,默认局锁本位)。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (1, 9), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert gs.node_pos.value == (2, 1) and gs.node_pos.source == 'logic'
    assert gs.node_hist_pos == (2, 1)
    assert effective_node_pos(gs) == (2, 1)


def test_out_of_domain_reading_dropped() -> None:
    """越域读数丢弃(design §2.11 锁 4 位面在表守卫):位面 3 无序列表
    (OCR 位面误读形态)→ 不写任何水位 + arbitrate 留证,返回
    out_of_domain_dropped(与 prep suppress 零写入/supply 响亮抛错语义
    等价的 kernel 侧显式处置)。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (1, 2), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert observe_node_anchor(gs, (3, 1), trigger_screen='货币战争-补给',
                               actor=_ACTOR) == 'out_of_domain_dropped'
    assert gs.node_pos.value == (1, 2), '越域读数不写水位'
    assert gs.node_hist_pos == (1, 2), '越域读数不推 hist'


def test_terminal_match_end_event_style() -> None:
    """终局事件式(design §2.11 锁 3):P2 末 boss (2,7) 结算确认 →
    sequence_next = None → applied=True reason='match_end' + 声明
    next_screen='';零写入(node_pos/node_hist_pos 保持锚定态)零效果
    tick(在册效果余期不递减)。applied 语义扩展 = 终结动作落地事实。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (2, 7), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert gs.free_refresh_left.value == 2, '锚定 (2,7) 当帧发放(对照基线)'
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied is True, 'applied = 终结动作落地事实(语义扩展)'
    assert out.reason == 'match_end'
    assert out.world_decl is not None
    assert out.world_decl.next_screen == ''
    assert out.world_decl.trigger == 'node_advance'
    assert gs.node_pos.value == (2, 7), '终局零写入'
    assert gs.node_hist_pos == (2, 7), '终局不推水位'
    assert gs.free_refresh_left.value == 2, '终局零效果 tick(余期不递减)'
