"""策略延时 offer 入队原语与登记腿测试(镜像 src = kernel/cw_gain_chain.py
的 queue_delayed_invest_offer + kernel/cw_gain_effects.py 的
_make_delayed_offer_effect 派生条目)。

测试面依据 = 迭代设计 designs/T-98-huangjin-qihuo.md §4(锁 2 登记腿
3+1 条 / 锁 6 live 链登记;live 无呈现动作由模块边界承担——kernel 不
import sim,不设静态扫描锁):
- 拿卡黄金期货 → 队列 (('黄金期货', 5),) + 效果串
  strategy_offer_scheduled:金@5;
- 未登记策略卡(表外名 + 在册无腿卡)零写;
- 递归形态(monkeypatch 临时加彩虹期货行)→ 链式再入队(锁「handler
  按注册表驱动」机制,非本批交付行为——现役注册面仅黄金期货);
- live 落地形态(gain_invest_strategy 同函数,session=None 直构)队列
  照写,零世界呈现动作。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel import cw_gain_chain
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)


def _lsig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='CwGainChain',
                      mode='compute')


def _gs() -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True   # 置闩:登记 = 确定事件,锁确定面写通道
    return gs


def test_pick_gold_futures_queues_delayed_offer() -> None:
    """登记腿主条(handler 分派形态):拿卡黄金期货 → 队列恰
    (('黄金期货', 5),)(元素 = (触发卡规范名, 登记节拍))+ 效果串
    strategy_offer_scheduled:金@5;确定面写(source = logic)。"""
    gs = _gs()
    effects = on_strategy_gained(gs, '黄金期货', rand=False, sig=_lsig(),
                                 rng=random.Random(0))
    assert effects == ('strategy_offer_scheduled:金@5',)
    assert gs.pending_strategy_offers.value == (('黄金期货', 5),), \
        f'队列值: {gs.pending_strategy_offers.value}'
    assert gs.pending_strategy_offers.source == 'logic', '登记走确定面'


def test_unregistered_cards_zero_write() -> None:
    """未登记卡零写(两形):表外名(查无效果安静不写)与在册无腿卡
    (躺平,注册表有卡但无登记行)均 → 零效果串 + 队列零写。"""
    for name in ('随便一张未收录卡', '躺平'):
        gs = _gs()
        seq_before = gs.write_seq
        effects = on_strategy_gained(gs, name, rand=False, sig=_lsig(),
                                     rng=random.Random(0))
        assert effects == ()
        assert gs.pending_strategy_offers.value in (None, ()), \
            f'{name} 队列被写'
        assert gs.write_seq == seq_before, f'{name} 出现额外写行'


def test_recursive_form_chained_requeue(monkeypatch) -> None:
    """递归形态(锁机制非交付行为):注册表临时加彩虹期货行 + 效果表
    同步派生条目 → 拿卡彩虹期货链式再入队,登记值按临时行(棱彩@5)——
    handler 按注册表驱动,族批注册落地后即真行为,零新增机制件。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        _make_delayed_offer_effect,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        StrategyDelayedOffer,
    )
    monkeypatch.setitem(
        cw_gain_chain.STRATEGY_DELAYED_OFFERS, '彩虹期货',
        StrategyDelayedOffer(id='201101', delay_nodes=5,
                             offer_quality='棱彩'))
    monkeypatch.setitem(cw_gain_chain.PICK_INVEST_EFFECTS, '彩虹期货',
                        _make_delayed_offer_effect('彩虹期货'))
    gs = _gs()
    effects = on_strategy_gained(gs, '彩虹期货', rand=False, sig=_lsig(),
                                 rng=random.Random(0))
    assert effects == ('strategy_offer_scheduled:棱彩@5',)
    assert gs.pending_strategy_offers.value == (('彩虹期货', 5),)


def test_live_gain_chain_queues_offer_zero_world_action() -> None:
    """live 链登记(不对称申报的行为半边):live 落地形态同函数
    (gain_invest_strategy,session=None 直构)→ 注册去重 + 队列照写;
    kernel 零呈现动作(呈现腿仅存在于 sim 模块,模块边界承担,无静态
    扫描锁)。"""
    gs = _gs()
    outcome = gain_invest_strategy(gs, None, '黄金期货', rand=False,
                                   sig=_lsig(), rng=random.Random(0),
                                   producer='CwActionReport')
    assert outcome.placed is True
    assert '黄金期货' in (gs.active_strategies.value or []), '持卡注册'
    assert outcome.effects == ('strategy_offer_scheduled:金@5',)
    assert gs.pending_strategy_offers.value == (('黄金期货', 5),), \
        f'live 链队列: {gs.pending_strategy_offers.value}'
