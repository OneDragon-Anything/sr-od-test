"""武装突入(id 302001)双箱组合登记行锁(镜像 src = PICK '武装突入'
行 _make_box_grant_effect(('简易武装箱', '简易武装箱')) + SG 箱腿组
两元素元组行;镜像表泛化 dict[str, tuple[str, …]] 首个 count>1 成员;
先例 = 同目录天降救兵组合锁形)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-315 对应稿
(REVIEW-T315 免裁 6/6;卡面官方原文:「遭遇节点的奖励变为2倍。获得2个
【简易武装箱】。」——效果条目1 奖励×2 双端盲零建模第三例[T-118/T-134 同型,
两截口径]/效果条目2 数量 = 双元素元组,席满逐件独立三态):

- 行为链真值:恰双箱逐件落席+效果串恰 2 条(双 box_grant)+rng 零消费
  (开箱分支确定发放);
- 席满双箱三态:箱1 备战空槽/箱2 溢出位被占 → 零写+DEFECT 留证形态
  (逐件独立,禁全有全无)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')
_CARD = '武装突入'
_SEED = 20261216


def _make_gs(*, slots: int = 9) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * slots,
                         capacity=9), sig=_SIG_OBS)
    return gs


def test_wuzhuang_chain_places_two_boxes() -> None:
    """行为链真值:恰双箱逐件落席+效果串恰 2 条+rng 零消费。"""
    gs = _make_gs()
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert len(effects) == 2, f'效果串恰 2 条: {effects}'
    assert all(e.startswith('box_grant:简易武装箱') for e in effects), \
        f'双箱腿: {effects}'
    boxes = [sl for sl in gs.bench.value.slots
             if sl.kind != 'unit' and sl.kind != 'empty'
             and getattr(sl, 'item', None) == '简易武装箱']
    assert len(boxes) == 2, f'恰双箱落席: {len(boxes)}'
    assert gs.write_seq > seq_before, '落位写'
    assert rng0.getstate() == rng_state0, 'rng 零消费(确定发放)'
