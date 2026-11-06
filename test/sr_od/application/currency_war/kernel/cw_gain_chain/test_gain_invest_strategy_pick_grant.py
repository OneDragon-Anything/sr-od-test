"""gain_invest_strategy 环境取卡触发发放接入调用测试(镜像 src =
kernel/cw_gain_chain.py 的 gain_invest_strategy 金币分支接入调用段;按被测方法拆
目录规范落位,先例 = 同目录 test_gain_invest_env.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-46-celue-dashi.md(定稿)§4 锁 3(§2.1(c) 落地形态):
- live 同口(report_action_pick_invest_strategy_param)两连笔——首笔 +2 金、
  次笔 +4 金(含本张口径的链级锁),active_strategies 注册不受触发影响;
- 次序锁:注入 on_strategy_gained 抛异常 → 金已入账且异常上抛
  (锁「金币分支在③前」接入调用位置)。
构造沿现役获得链测试先例:直写 opts 定向选入策略大师(环境经
report_action_pick_invest_env_param),策略经 report_action_pick_invest_
strategy_param 上报。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_env_param,
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickInvestEnvParam,
    CwActionPickInvestStrategyParam,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')


def _make_gs(gold: int) -> GameState:
    """观测面组装(金账观察直构;取安静未收录卡,席位/道具/效果域
    零触碰,非本测焦点不播种)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, gold, sig=_SIG_OBS)
    return gs


def _pick_env_celuedashi(gs: GameState) -> None:
    """定向选入策略大师(直写 opts + 环境上报,现役先例同手法)。"""
    gs.write_logic(gs.invest_env_opts, ['策略大师', '轮岗', '头彩'],
                   produced_by='test', evidence='t:opts', sig=_LSIG)
    out = report_action_pick_invest_env_param(
        gs, CwActionPickInvestEnvParam(idx=0, norm_name='策略大师'), _LSIG)
    assert out.applied and gs.active_env.value == '策略大师', '前置:环境在场'


def test_two_consecutive_picks_gold_2_then_4(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """两连笔链级锁(T-46 设计 §4 锁 3):live 同口首笔取卡 +2 金、次笔
    +4 金(金额 = 2×含本张已持有数);active_strategies 注册不受触发
    影响(两张依序入列)。取未收录安静卡,排除策略效果域噪声。"""
    gs = _make_gs(gold=30)
    _pick_env_celuedashi(gs)
    out1 = report_action_pick_invest_strategy_param(
        gs, CwActionPickInvestStrategyParam(idx=0, norm_name='随便一张未收录卡'),
        _LSIG)
    assert out1.applied and out1.reason == 'gain_chain_applied'
    assert gs.gold.value == 32, f'首笔 +2(2×1): {gs.gold.value}'
    assert gs.active_strategies.value == ['随便一张未收录卡'], '注册照常'
    out2 = report_action_pick_invest_strategy_param(
        gs, CwActionPickInvestStrategyParam(
            idx=0, norm_name='随便第二张未收录卡'),
        _LSIG)
    assert out2.applied
    assert gs.gold.value == 36, f'次笔 +4(2×2): {gs.gold.value}'
    assert gs.active_strategies.value == ['随便一张未收录卡',
                                          '随便第二张未收录卡'], \
        '注册两张依序入列,发放不扰持卡面'


def test_gold_leg_lands_before_strategy_effects_reraise(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """次序锁(T-46 设计 §4 锁 3):注入 on_strategy_gained 抛异常 →
    金已入账且异常上抛(金币分支在③前:③ 直调零防护,异常发生在金入账
    之后不回吞)。"""
    import sr_od.application.currency_war.kernel.cw_gain_chain as gcm

    def _boom(gs, name, *, rand, sig, rng=None):
        raise RuntimeError('效果分派爆炸')

    monkeypatch.setattr(gcm, 'on_strategy_gained', _boom)
    gs = _make_gs(gold=30)
    _pick_env_celuedashi(gs)
    with pytest.raises(RuntimeError, match='效果分派爆炸'):
        report_action_pick_invest_strategy_param(
            gs, CwActionPickInvestStrategyParam(
                idx=0, norm_name='随便一张未收录卡'),
            _LSIG)
    assert gs.gold.value == 32, '金已入账(异常不回吞)'
    assert gs.active_strategies.value == ['随便一张未收录卡'], \
        '注册分支(①)先于③,照常成立'
