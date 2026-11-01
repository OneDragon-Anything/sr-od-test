"""策略卡首领战后随机装备发放检查腿测试(镜像 src = kernel/cw_gain_chain.py
的 check_strategy_boss_battle_grants)。

测试面依据 = 迭代设计 designs/T-166-qiang-zaishou.md §4 锁 3/4/7 +
REVIEW-T166(直构形态先例 = 同目录 test_check_strategy_hp_loss_grants.py
的容器直置;采样单一源纪律 = roll_random_equip 禁第二采样表达式):
- 条件矩阵短路:node_kind 非 boss(battle/encounter/reward/supply)→ 空;
  未持卡/表外卡 → 空;
- 发放真值:固定 rng 注入 → equips 恰 +1、名 = 同种子对同池重放采样值
  (禁手抄池清单,T-116 家族口径)、evidence ``strategy_boss_battle#<卡名>
  #equip``(原语内追加 #equip 后缀)、随机态通道(source = logic_rand,
  rand=True 采样效果子链)、返回值 = 发放名序列;
- 可重复无 done 闩(卡面无「首次」限定 = 每次 boss 战后都发,防重归
  调用方节点键幂等守卫);
- rng 缺省回退自掷路径与显式传参路径**写语义同构**(零写计数/evidence
  形态/发放件数一致;非结果等价——自掷路径采样值不可复现,断言只锁
  写面形态与名 ∈ 池,设计稿 §4 锁 7 收窄口径)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_boss_battle_grants,
    roll_random_equip,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    equips_by_category,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '枪在手'

#: 固定种子(采样名失配 = 换种子,禁手抄池清单)。
_EQ_SEED = 20261102


def _gs(*, card: str | None = _CARD) -> GameState:
    """直构 gs(equips 观察定发放承载;card=None = 未持卡)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    return gs


def _expected_pick(seed: int) -> str:
    return roll_random_equip(random.Random(seed), '简易')


def test_non_boss_kind_short_circuit() -> None:
    """锁 7a/3:node_kind != 'boss' → 空(节点类型条件在矩阵首位短路,
    持卡与否零影响;kind = 调用方传结算点现值,修饰局场字段改写天然
    跟随)。"""
    for kind in ('battle', 'encounter', 'reward', 'supply', ''):
        gs = _gs()
        before = gs.write_seq
        assert check_strategy_boss_battle_grants(gs, kind, _LSIG,
                                                 rng=random.Random(
                                                     _EQ_SEED)) == (), \
            f'非首领 kind={kind!r} 误发放'
        assert gs.equips.value == [], f'非首领 kind={kind!r} 误入栏'
        assert gs.write_seq == before, f'非首领 kind={kind!r} 误写'


def test_no_card_and_out_of_registry_zero_grant() -> None:
    """锁 4:未持卡 + boss → 空;持表外卡(躺平,效果原文含装备字样但不
    在登记表)+ boss → 空(表外卡一律无条目,禁从效果原文自动猜装的
    通道纪律)。"""
    for card in (None, '躺平'):
        gs = _gs(card=card)
        before = gs.write_seq
        assert check_strategy_boss_battle_grants(gs, 'boss', _LSIG,
                                                 rng=random.Random(
                                                     _EQ_SEED)) == (), \
            f'card={card!r} 误发放'
        assert gs.equips.value == [], f'card={card!r} 误入栏'
        assert gs.write_seq == before, f'card={card!r} 误写'


def test_boss_grant_places_sampled_equip() -> None:
    """锁 2 单元面:持卡 + boss → equips 恰 +1、名 = 同种子重放采样值
    (∈ 简易池派生集)、evidence ``strategy_boss_battle#枪在手#equip``、
    随机态通道(source = logic_rand)、返回值 = (采样名,)。"""
    pick = _expected_pick(_EQ_SEED)
    gs = _gs()
    out = check_strategy_boss_battle_grants(gs, 'boss', _LSIG,
                                            rng=random.Random(_EQ_SEED))
    assert out == (pick,), f'返回值漂移: {out!r}'
    assert gs.equips.value == [pick], 'equips 恰 +1 且名 = 采样值'
    assert pick in equips_by_category('简易'), '发放名 ∈ 简易池'
    assert gs.equips.source == 'logic_rand', '采样发放应走随机态通道'
    assert gs.equips.evidence == f'strategy_boss_battle#{_CARD}#equip', \
        f'evidence 漂移: {gs.equips.evidence}'


def test_repeatable_no_done_latch() -> None:
    """可重复(无 done 闩):同 kind 连调两次 → 两件入栏(卡面无「首次」
    限定 = 每次 boss 战后都发,一局现役最多 3 次;防重归调用方节点键
    幂等守卫,本函数零二次守卫)。"""
    gs = _gs()
    first = check_strategy_boss_battle_grants(gs, 'boss', _LSIG,
                                              rng=random.Random(_EQ_SEED))
    second = check_strategy_boss_battle_grants(gs, 'boss', _LSIG,
                                               rng=random.Random(_EQ_SEED))
    assert len(first) == 1 and len(second) == 1, '两次调用应各发 1 件'
    assert len(gs.equips.value) == 2, f'重复发放未入栏: {gs.equips.value!r}'
    assert all(n in equips_by_category('简易')
               for n in gs.equips.value), '发放名出池'


def test_default_rng_path_write_semantics_isomorphic() -> None:
    """锁 7(写语义同构,非结果等价):rng 缺省回退自掷路径与显式传参
    路径写面形态一致(发放件数/通道/evidence 前缀),采样值不可复现
    (自掷 = 猜测口径)故只断言名 ∈ 池,禁按显式路径采样值断言。"""
    gs = _gs()
    out = check_strategy_boss_battle_grants(gs, 'boss', _LSIG)
    assert len(out) == 1, '自掷路径发放件数漂移'
    assert out[0] in equips_by_category('简易'), '自掷路径发放名出池'
    assert gs.equips.value == [out[0]], '自掷路径入栏漂移'
    assert gs.equips.source == 'logic_rand', '自掷路径通道漂移'
    assert gs.equips.evidence == f'strategy_boss_battle#{_CARD}#equip', \
        '自掷路径 evidence 形态漂移'
