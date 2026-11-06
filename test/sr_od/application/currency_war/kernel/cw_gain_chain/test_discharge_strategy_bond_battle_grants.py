"""策略卡羁绊条件节点窗交付检查效果条目测试(镜像 src = kernel/cw_gain_chain.py
的 discharge_strategy_bond_battle_grants;两拍制发放拍,含 rng)。

测试面依据 = 迭代设计 designs/T-172-buyao-xiaokan-women-de-jiban.md §4
锁 4/7/9 + REVIEW-T172(直构形态先例 = 同目录
test_check_strategy_boss_battle_grants.py;采样断言 = 固定 rng 同种子
重放,禁手抄池清单,T-116 家族口径):
- 武装态门:armed 非 True(None = 未观察未武装 / False = 已消费)→ 0
  零写;
- 交付真值:armed True → 星徽池逐件独立掷 ×5(放回,卡面无「不同」
  限定)、名 = 同种子重放采样值、evidence ``strategy_bond_battle#<卡名>
  #equip``(原语内追加 #equip 后缀,断言前缀匹配禁精确)、随机态通道
  (source = logic_rand)、消费武装 armed False(evidence
  ``strategy_bond_battle#consume``);
- **rng 必填无缺省**(签名锁):较损血效果条目「缺省回退自掷」更严——本效果条目
  唯一消费方 = sim 调用点传流键,无缺省形态则采样猜测口径的结构性风险
  面消失,签名退化(加缺省)即红;
- 可重复无 done 一次性标志位:消费后重新武装 → 再交付(armed 消费-再武装链,
  一局发放次数 = 合格战斗数)。
"""
from __future__ import annotations

import inspect
import random

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    discharge_strategy_bond_battle_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    equips_by_category,
)

_SIG_OBS = ChannelSig(family='obs', actor='TestSigWriter')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '不要小看我们的羁绊'
_POOL = equips_by_category('星徽')
_EQ_SEED = 20261103


def _gs(*, armed: bool | None) -> GameState:
    """直构 gs(equips 观察定发放承载;armed 直接置态)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:card', sig=_LSIG)
    if armed is not None:
        gs.write_logic(gs.strategy_bond_battle_armed, armed,
                       produced_by='test-seed', evidence='t:armed',
                       sig=_LSIG)
    return gs


def test_rng_parameter_mandatory_no_default() -> None:
    """锁 9(rng 必填签名锁):rng 形参 keyword-only 且无缺省——采样
    强制显式注入,签名退化(加缺省回退自掷)即红。"""
    sig = inspect.signature(discharge_strategy_bond_battle_grants)
    param = sig.parameters['rng']
    assert param.kind == inspect.Parameter.KEYWORD_ONLY, \
        'rng 应为 keyword-only 形参'
    assert param.default is inspect.Parameter.empty, \
        'rng 必填无缺省(缺省自掷 = 猜测口径通道被重开)'


def test_unarmed_states_zero_grant() -> None:
    """锁 7a(武装态门):armed None(未观察)与 False(已消费)两态
    → 0 零写(不发不消费,evidence 面零新增)。"""
    for armed in (None, False):
        gs = _gs(armed=armed)
        before = gs.write_seq
        assert discharge_strategy_bond_battle_grants(
            gs, rng=random.Random(_EQ_SEED), sig=_LSIG) == 0, \
            f'armed={armed!r} 误发放'
        assert gs.equips.value == [], f'armed={armed!r} 误入栏'
        assert gs.strategy_bond_battle_armed.value == armed, \
            f'armed={armed!r} 被误写'
        assert gs.write_seq == before, f'armed={armed!r} 误写'


def test_armed_delivers_five_starbadges_and_consumes(
        monkeypatch) -> None:
    """锁 1 单元面(发放拍):armed True → equips 恰 +5、逐件 ∈ 星徽
    池、名 = 同种子重放采样序列(逐件独立掷 = 放回语义)、5 笔装备写
    evidence 前缀 ``strategy_bond_battle#<卡名>``(#equip 后缀,前缀
    匹配禁精确)、随机态通道(source = logic_rand)、消费武装 armed
    False(evidence ``strategy_bond_battle#consume``)。"""
    _replay = random.Random(_EQ_SEED)
    picks = [_replay.choice(_POOL) for _ in range(5)]
    gs = _gs(armed=True)
    evidences: list[str] = []
    real_rand = gs.write_logic_rand

    def _rec_rand(target, value, **kw):
        if gs._field_name(target) == 'equips':
            evidences.append(str(kw.get('evidence')))
        return real_rand(target, value, **kw)

    monkeypatch.setattr(gs, 'write_logic_rand', _rec_rand)
    n = discharge_strategy_bond_battle_grants(
        gs, rng=random.Random(_EQ_SEED), sig=_LSIG)
    assert n == 5, f'发放件数漂移: {n}'
    assert gs.equips.value == picks, f'入栏序应 = 采样序: {gs.equips.value}'
    assert all(name in set(_POOL) for name in gs.equips.value), '发放名出池'
    assert gs.equips.source == 'logic_rand', '采样发放应走随机态通道'
    assert len(evidences) == 5, f'装备写笔数漂移: {evidences!r}'
    for ev in evidences:
        assert ev.startswith(f'strategy_bond_battle#{_CARD}'), \
            f'evidence 前缀漂移: {ev!r}'
        assert ev.endswith('#equip'), f'evidence 后缀漂移: {ev!r}'
    assert gs.strategy_bond_battle_armed.value is False, '交付后未消费武装'
    assert gs.strategy_bond_battle_armed.evidence == \
        'strategy_bond_battle#consume', \
        f'消费笔 evidence 漂移: {gs.strategy_bond_battle_armed.evidence}'


def test_repeatable_rearm_then_deliver_again() -> None:
    """锁 4 单元面(可重复链):交付消费(False)→ 重新武装(True)→
    再交付再 +5(共 10,armed 消费-再武装链;无 done 一次性标志位,一局发放次数
    = 合格战斗数)。"""
    gs = _gs(armed=True)
    first = discharge_strategy_bond_battle_grants(
        gs, rng=random.Random(_EQ_SEED), sig=_LSIG)
    assert first == 5 and gs.strategy_bond_battle_armed.value is False
    gs.write_logic(gs.strategy_bond_battle_armed, True,
                   produced_by='test-seed', evidence='t:rearm', sig=_LSIG)
    second = discharge_strategy_bond_battle_grants(
        gs, rng=random.Random(_EQ_SEED + 1), sig=_LSIG)
    assert second == 5, '再武装后未二次交付'
    assert len(gs.equips.value) == 10, f'两次交付应共 +10: {len(gs.equips.value)}'
    assert all(name in set(_POOL) for name in gs.equips.value), '发放名出池'
    assert gs.strategy_bond_battle_armed.value is False, '二次交付后未消费'
