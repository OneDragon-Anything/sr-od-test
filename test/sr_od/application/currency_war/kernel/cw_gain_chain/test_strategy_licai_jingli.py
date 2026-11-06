"""狸财经狸(id 304001)登记行为锁(镜像 src = STRATEGY_GRANTS
'狸财经狸' 具名角色发放行 + 校验器四查 + 估值档位 'off' 静默 + 获得链
零写;先例 = 同目录天降救兵组合锁 + 龙虎兄弟狸同形段)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-335 对应稿
(REVIEW-T335 无需用户决定 7/7;卡面官方原文:「获得1个【狸狸】，它带着初始资金
30【金币】来帮你理财，每回合获得利息+2金币。当你的金币少于20时，从狸狸
那里取出10金币存款。进入第三位面首领节点时，取出所有存款。
一个月内花光十个亿，你就可以继承狸的财产！。」):

- 登记:chars_immediate = ('狸职狸狸',) 名称归一纪律直读(「狸狸」∉
  roster,实机浮窗名归一;获得链 on_strategy_gained 零写零容器写 =
  登记非运行时发放定论);
- 估值:gift_hit_tier = 'off'(召唤单位无估值档位,摸个鱼吧II 单名
  先例同判)/grant_gift_value = 0.0;
- 息效果条目:STRATEGY_ECONOMY interest_flat 注册行已登记零新增锁(存量四
  文件锁即回归网,零改动定论不建锁先例)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_comps import (
    gift_hit_tier,
)
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
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_GRANTS,
    _validate_strategy_grants,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.gift_value import (
    grant_gift_value,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPre')
_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')
_CARD = '狸财经狸'


def _make_gs() -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty')] * 9,
                                   capacity=9), sig=_SIG_OBS)
    return gs


def test_registry_row_and_validator() -> None:
    """登记行单一源+校验器四查全过(import 即炸族直调同款)。"""
    _validate_strategy_grants()
    row = STRATEGY_GRANTS[_CARD]
    assert row.chars_immediate == ('狸职狸狸',), f'登记名归一: {row!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'
    assert INVESTMENT_STRATEGIES[_CARD].source == 'plaza:304001', \
        '注册行 id 对拍(304001)'


def test_valuation_off_and_zero_gain_chain_write() -> None:
    """估值 off 档+零值+获得链零写(登记非运行时发放定论)。"""
    gs = _make_gs()
    gs.observe(gs.active_strategies, [_CARD], sig=_SIG_OBS)
    tier = STRATEGY_GRANTS[_CARD]
    assert gift_hit_tier(tier) == 'off', \
        f'召唤单位无估值档位: {gift_hit_tier(tier)}'
    assert grant_gift_value(tier, frozenset()) == 0.0, '零估值扰动'
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=None)
    assert effects == (), f'获得链零写: {effects}'
    assert gs.write_seq == seq_before, '零容器写(登记非运行时发放)'
