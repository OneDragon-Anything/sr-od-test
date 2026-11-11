"""策略卡死亡救援触发检查效果条目测试(镜像 src = kernel/cw_gain_chain.py 的
take_strategy_death_save)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 2/6 + 用户裁定
2026-11-04(一次性 + M-B 独立叠加 + R1 奖励随救援发放;直构形态先例 =
同目录 test_check_strategy_hp_loss_grants.py):
- 五态矩阵:①未持卡零写;②持卡 ∧ 一次性标志位 ∈ {None, False}(未用,两值均
  放行)→ 载荷三元组 + 一次性标志位置位 + 三笔写(hp 40/经验/金);③持卡 ∧ 一次性标志位
  True(已用)→ None 零写(一次性防复发);④hp 基座 None → None 零写
  (禁造假基座,None 局禁救援);
- 写序:一次性标志位置位先行,后 hp/经验/金同窗相邻(同 sig 同窗家族纪律);
- 奖励笔署名(锁 6):经验笔 produced_by = strategy_death_save 词根
  (经 grant_xp 形参如实署名,非缺省「EffectLedgerBridge:成功经验」桥
  语义);金笔 = observe 独立笔(扑满收入 observe 金同款,金面禁 logic
  直写),载荷一律取表载值。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_economy import (
    XP_TO_NEXT_LEVEL,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    take_strategy_death_save,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_DEATH_SAVE_GRANTS,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '藏一手'
_HP, _XP, _GOLD = STRATEGY_DEATH_SAVE_GRANTS[_CARD]


def _gs(*, card: bool = True, hp: int | None = 10,
        latch: bool | None = None) -> GameState:
    """直构 gs(节点 P1r3 观察定 evidence 帧;gold/hp 观察定发放承载;
    card = 持卡态;hp=None = 基座未观察态;latch = 预置一次性标志位值)。等级基座
    取 9 级(XP_TO_NEXT_LEVEL[9]=84 > 载荷 30,经验效果条目单笔不触发跨级
    level 连写——跨级连锁归 grant_xp 原语自身测试域)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='battle'),
               sig=_SIG_OBS)
    gs.observe(gs.gold, 10, sig=_SIG_OBS)
    if hp is not None:
        gs.observe(gs.hp, hp, sig=_SIG_OBS)
    gs.observe(gs.level, 9, sig=_SIG_OBS)
    gs.observe(gs.xp, (0, XP_TO_NEXT_LEVEL[9]), sig=_SIG_OBS)
    if card:
        gs.write_logic(gs.active_strategies, [_CARD],
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    if latch is not None:
        gs.write_logic(gs.strategy_death_save_used, latch,
                       produced_by='test-seed', evidence='t:latch',
                       sig=_LSIG)
    return gs


def _record_writes(gs: GameState,
                   monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic/observe 记录 (通道, 字段名, evidence, value,
    produced_by) 写序(透传真实现零行为变化;先例 =
    sim/cw_sim_backend/test_strategy_hp_loss_sim_chain 同名助手)。"""
    calls: list[tuple] = []

    def _wrap_logic(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((channel, gs._field_name(target), evidence, value,
                          produced_by))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    def _wrap_obs(real):
        def rec(target, value, *, evidence=None, sig, note=''):
            calls.append(('obs', gs._field_name(target), evidence, value,
                          None))
            real(target, value, evidence=evidence, sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic',
                        _wrap_logic(gs.write_logic, 'logic'))
    monkeypatch.setattr(gs, 'observe', _wrap_obs(gs.observe))
    return calls


def _death_save_rows(calls: list[tuple]) -> list[tuple]:
    """救援写端行(evidence 前缀 strategy_death_save:;sim:engine: 前缀
    为 observe 面包装,同前缀命中)。"""
    return [c for c in calls
            if 'strategy_death_save:' in str(c[2] or '')]


def test_no_card_zero_write() -> None:
    """锁 2①:未持卡 → None 零写(一次性标志位保持未判定 None,写序不变)。"""
    gs = _gs(card=False)
    assert take_strategy_death_save(gs, logic_sig=_LSIG) is None, \
        '未持卡误发放'
    assert gs.strategy_death_save_used.value is None, '未持卡误置一次性标志位'


def test_hit_latch_none_and_false_both_pass(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 2②:持卡 ∧ 一次性标志位未用(None/False 两态均放行)→ 载荷三元组 +
    一次性标志位置位 True + hp 写 40 + 经验 +30 + 金 +80(载荷全取表载值;
    一次性标志位 False = 已判定未触发态,与 None 同放行——表述统一防分支漏)。"""
    for latch in (None, False):
        gs = _gs(latch=latch)
        calls = _record_writes(gs, monkeypatch)
        assert take_strategy_death_save(gs, logic_sig=_LSIG) \
            == (_HP, _XP, _GOLD), f'一次性标志位 {latch!r} 态误拒'
        assert gs.strategy_death_save_used.value is True, '一次性标志位未置位'
        assert gs.hp.value == _HP, f'一次性标志位 {latch!r} 态 hp 写漂移'
        assert gs.gold.value == 10 + _GOLD, f'一次性标志位 {latch!r} 态金写漂移'
        assert gs.xp.value == (_XP, XP_TO_NEXT_LEVEL[9]), \
            f'一次性标志位 {latch!r} 态经验写漂移'
        rows = _death_save_rows(calls)
        assert len(rows) == 4, \
            f'一次性标志位 {latch!r} 态写笔数漂移: {[c[:3] for c in rows]}'


def test_latch_true_blocks_repeat() -> None:
    """锁 2③:一次性标志位已置位(True)→ None 零写(一次性防复发——每局仅首次
    致死触发救援,后续致死正常死亡;写序不变 = 全短路)。"""
    gs = _gs(latch=True)
    assert take_strategy_death_save(gs, logic_sig=_LSIG) is None, \
        '已置一次性标志位误二次发放'
    assert gs.hp.value == 10 and gs.gold.value == 10, '已置一次性标志位误写'


def test_hp_none_base_zero_write() -> None:
    """锁 2④:hp 基座未观察(None)→ None 零写(禁造假基座,
    apply_hp_outcome 未观察零写同款防御;现役开局初始值下不可达)。"""
    gs = _gs(hp=None)
    assert take_strategy_death_save(gs, logic_sig=_LSIG) is None, \
        'None 基座误发放'
    assert gs.strategy_death_save_used.value is None, 'None 基座误置一次性标志位'


def test_write_order_latch_first(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 2⑤:命中拍写序 = 一次性标志位置位先行 → hp → 经验 → 金(同 sig 同窗
    相邻写;evidence 帧互异可过滤审计)。"""
    gs = _gs()
    calls = _record_writes(gs, monkeypatch)
    take_strategy_death_save(gs, logic_sig=_LSIG)
    rows = _death_save_rows(calls)
    assert [(c[1], str(c[2]).replace('sim:engine:', '')) for c in rows] == [
        ('strategy_death_save_used', 'strategy_death_save:latch:p1r3'),
        ('hp', 'strategy_death_save:hp:p1r3'),
        ('xp', 'strategy_death_save:xp:p1r3'),
        ('gold', 'strategy_death_save:gold:p1r3'),
    ], f'写序漂移: {[(c[1], c[2]) for c in rows]}'


def test_xp_produced_by_named_not_bridge_default(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 6:经验笔 produced_by = strategy_death_save 词根(新写端新名,
    不沿用 grant_xp 缺省「EffectLedgerBridge:成功经验」桥语义伪装连续);
    经验/金两笔 evidence 分列。"""
    gs = _gs()
    calls = _record_writes(gs, monkeypatch)
    take_strategy_death_save(gs, logic_sig=_LSIG)
    xp_rows = [c for c in calls if c[1] == 'xp' and c[0] == 'logic']
    assert len(xp_rows) == 1, f'经验笔数漂移: {xp_rows!r}'
    assert xp_rows[0][4] == 'strategy_death_save', \
        f'经验笔署名漂移(桥缺省伪装): {xp_rows[0][4]!r}'
    gold_rows = [c for c in calls if c[1] == 'gold']
    assert len(gold_rows) == 1 and gold_rows[0][0] == 'obs', \
        '金笔必须为 observe 独立笔(金面禁 logic 直写)'
