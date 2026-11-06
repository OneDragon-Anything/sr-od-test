"""彩虹矿(id 301201)节点条件晶矿发放锁(镜像 src = STRATEGY_REWARD_
ORE_GRANTS 白名单表 + check_strategy_reward_ore_grants 纯判定 + sim
聚段调用块/呈现段补点;载体 = T-283 迷之旅人三件套形状骑字段,先例 =
同目录条件发放族锁形)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-306 对应稿
(REVIEW-T306 免裁 6/6;卡面官方原文:「进入新的奖励节点时，获得1个晶
矿。」——表值 = 发矿数卡面明写;晶矿无 placement 发放即一次性标志位,载体自证差异):

- 注册表锁:集合 = {'彩虹矿': 1} + 孤儿键负控;
- 判定矩阵锁:未持卡 0 / 非 reward 节点 0 / 持卡 reward 首窗发 1+一次性标志位 /
  重放零重发(一次性标志位命中);
- PENDING 行文案锁。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    STRATEGY_GIFT_LEG_REWARD_ORE,
    check_strategy_reward_ore_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_REWARD_ORE_GRANTS,
)

_SIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp', mode='compute')

_CARD = '彩虹矿'


_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')


def _make_gs(*, held: tuple[str, ...] = ()) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if held:
        gs.write_logic(gs.active_strategies, list(held),
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    return gs


def test_registry_closed_set() -> None:
    """注册表锁:集合 = {'彩虹矿': 1};孤儿键负控。"""
    assert STRATEGY_REWARD_ORE_GRANTS == {_CARD: 1, '彩虹矿+': 1}, '集合值对拍(展开卡 +1 行)'
    for n in STRATEGY_REWARD_ORE_GRANTS:
        assert n in INVESTMENT_STRATEGIES, f'孤儿键: {n}'


def test_gate_matrix_and_latch() -> None:
    """判定矩阵锁:非 reward 0 / 未持卡 0 / 持卡 reward 首窗发 1+一次性标志位 /
    重放零重发。"""
    gs = _make_gs(held=(_CARD,))
    assert check_strategy_reward_ore_grants(gs, node_kind='battle',
                                            sig=_SIG) == 0, '非 reward 0'
    gs2 = _make_gs()
    assert check_strategy_reward_ore_grants(gs2, node_kind='reward',
                                            sig=_SIG) == 0, '未持卡 0'
    gs3 = _make_gs(held=(_CARD,))
    got = check_strategy_reward_ore_grants(gs3, node_kind='reward',
                                           sig=_SIG)
    assert got == 1, f'持卡 reward 首窗发 1: {got}'
    latch = f'{_CARD}#{STRATEGY_GIFT_LEG_REWARD_ORE}'
    assert latch in (gs3.strategy_grants_done.value or ()), f'一次性标志位: {latch}'
    again = check_strategy_reward_ore_grants(gs3, node_kind='reward',
                                             sig=_SIG)
    assert again == 0, f'重放零重发: {again}'
