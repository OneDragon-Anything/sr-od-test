"""开源节流条件息顶满捕获效果条目测试(镜像 src = kernel/cw_gain_chain.py 的
capture_strategy_interest_topup + kernel/cw_game_state.py tick 闸接入调用;
宿主文件 test_game_state.py 超限冻结,按被测函数拆目录新文件落位)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 3 + REVIEW-
T295 §3.3 裁决点 2(tick 闸内捕获〔桥后滚位前〕+ 账本计数载体 + 置数
禁累加):
- 四态:持卡∧未花费 → 载体 = resolved 帽且滚位照常;已花费/不可评估
  (None)/未持卡 → 载体 0;
- **S2 回归红线 = 闸内序锁(行为形)**:捕获行位于滚位行之前——已花费
  用例即判别器:序若颠倒(滚位先),捕获读到滚位后的 False → 载体 = 帽
  → 顶满恒发错发,本组断言钉死(源码序由本行为锁承载,测试仓禁源码
  扫描断言);sim 链同型红线用例见 sim/cw_sim_backend/
  test_strategy_interest_topup_sim_chain.py;
- 置数语义禁累加:连续两节点未花费,载体恒帽值不翻倍(r2-C2 备案:
  窗口异常未消费时累加会放大错发)。

驱动口 = advance_node_effective(序位前进唯一落账入口,尾段自带
tick_effect_boundary;先消耗拿卡节点复现「持卡局下一节点边界捕获」
真实时序)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    CounterKey,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    advance_node_effective,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)

_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '开源节流'
_SPEC_ID = STRATEGY_EFFECTS[_CARD].id
_TOPUP_KEY = CounterKey.INTEREST_TOPUP


def _advance(gs: GameState, plane: int, round_num: int) -> None:
    assert advance_node_effective(gs, (plane, round_num),
                                  actor='TestDriver', sig=_LSIG,
                                  source='logic'), \
        f'推进被去重守卫挡下: {(plane, round_num)}'


def _gs_holding(prev: bool | None, holding: bool = True) -> GameState:
    """持卡时序状态容器:先消耗 (1,1)(拿卡节点,tick 已过),再持卡 +
    种 prev,下一 advance 触发捕获。(1,1) 先进闸同
    test_tick_pending_strategy_grants._gs_with_queue 拿卡时序先例。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _advance(gs, 1, 1)
    if holding:
        gs.write_logic(gs.active_strategies, [_CARD],
                       produced_by='test-seed', evidence='t:strat', sig=_LSIG)
        gs.effects.register_strategy(STRATEGY_EFFECTS[_CARD],
                                     acquired_key=(1, 1))
    if prev is not None:
        gs.write_logic(gs.prev_node_spent, prev,
                       produced_by='test-seed', evidence='t:prev', sig=_LSIG)
    return gs


def _carrier(gs: GameState) -> int:
    return gs.effects.counter(_SPEC_ID, _TOPUP_KEY)


def test_capture_unspent_carrier_set_and_roll_intact() -> None:
    """持卡 ∧ 未花费 → 载体 = resolved 帽 9,滚位照常(锁 3 第一态)。"""
    gs = _gs_holding(prev=False)
    _advance(gs, 1, 2)
    assert _carrier(gs) == 9, f'载体 = resolved 帽: {_carrier(gs)}'
    assert gs.prev_node_spent.value is False, '滚位照常(捕获毕滚位)'


def test_capture_spent_carrier_zero_order_redline() -> None:
    """持卡 ∧ 已花费 → 载体 0 且滚位照常——**S2 回归红线闸内序锁**
    (锁 3 红线):本用例即序判别器,捕获行在滚位行之前时 prev 读到
    True → 载体 0;序若被颠倒(滚位先行),捕获读滚位后的 False →
    载体 = 9 → 顶满恒发错发形态,本断言红。"""
    gs = _gs_holding(prev=True)
    _advance(gs, 1, 2)
    assert _carrier(gs) == 0, \
        f'已花费不授(捕获须读滚位前真值): {_carrier(gs)}'
    assert gs.prev_node_spent.value is False, '滚位照常(判等跳写除外)'


def test_capture_unread_prev_conservative_zero() -> None:
    """持卡 ∧ prev 未写(None 直构)→ 载体 0(禁猜口径,本金充裕金
    None 同款;锁 3 第三态)。None 态取直构状态容器不跑种子窗(捕获函数层
    直调)——tick 闸路径下首闸滚位会把直构 None 滚成 False
    (evidence prev_node_spent_roll),None 态在 advanced 闸内结构性不可达,
    tick 级 None 等价归本函数层锁 + 禁猜分支单一源
    (cw_economy.strategy_interest_floor,锁 1 参数化同态)。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        capture_strategy_interest_topup,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert gs.prev_node_spent.value is None, '直构状态容器不跑种子(前置)'
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:strat', sig=_LSIG)
    gs.effects.register_strategy(STRATEGY_EFFECTS[_CARD],
                                 acquired_key=(1, 1))
    capture_strategy_interest_topup(gs, frame='p1-r1')
    assert _carrier(gs) == 0, 'None = 条件不可评估,保守零顶满'


def test_capture_not_holding_carrier_zero() -> None:
    """未持卡 → 载体 0(锁 3 第四态;未持卡局全程零簿记增量)。"""
    gs = _gs_holding(prev=False, holding=False)
    _advance(gs, 1, 2)
    assert _carrier(gs) == 0, '未持卡零顶满'


def test_capture_set_not_accumulate_across_nodes() -> None:
    """置数语义禁累加(锁 3 伴生红线):连续两节点未花费,载体两次置数
    恒帽值不翻倍——自增形遇窗口异常未消费会把单拍值放大成错发
    (载体写端 = set_counter 覆写,bump 自增形禁用)。"""
    gs = _gs_holding(prev=False)
    _advance(gs, 1, 2)
    assert _carrier(gs) == 9
    _advance(gs, 1, 3)
    assert _carrier(gs) == 9, f'置数非累加: {_carrier(gs)}'


@pytest.mark.parametrize('prev', [True, False])
def test_capture_no_entry_host_silent_skip(prev: bool) -> None:
    """条目不在场(名单有卡、账本登记缺)零动作静默:载体宿主缺位时
    捕获不炸不落(登记缺陷已由获得链登记分支留存证据,此处不双报)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _advance(gs, 1, 1)
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:strat', sig=_LSIG)
    if prev is not None:
        gs.write_logic(gs.prev_node_spent, prev,
                       produced_by='test-seed', evidence='t:prev', sig=_LSIG)
    _advance(gs, 1, 2)   # 无 register_strategy:条目缺位,捕获静默
    assert _carrier(gs) == 0, '无宿主条目零计数落点(消费半边读 0)'
