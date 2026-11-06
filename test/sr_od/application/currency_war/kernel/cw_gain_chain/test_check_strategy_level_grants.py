"""策略卡到级发放决策函数测试(镜像 src = kernel/cw_gain_chain.py 的
check_strategy_level_grants 纯决策本体 + LEVEL_GRANT_PRODUCER 署名)。

测试面依据 = 迭代设计 designs/T-108-chengzhang-jijin.md §4 锁 3/4/9
(实现批修正:直构前置态判定依据 = kernel/cw_economy.py XP_TO_NEXT_LEVEL
单一源,8 级直构可得):
- 短路矩阵(锁 9):未持卡 / 表外卡(STRATEGY_ECONOMY 已登记但无到级字段)/
  未达标 / 已置一次性标志位 → None;达标 → (规范卡名, 金额) 返回形状;
- 宁缺勿造(锁 4):level/gold 现值 None → None 且不封账,值到位重查
  发放(check_env_refresh_grants 三要素同款);
- 纯决策零写(live 零接入调用通道前提):达标态全量快照调用前后逐位相等;
- 快照存续(本腿语义层):一次性标志位后快照→恢复往返,决策函数跳过(恢复局不
  重发;域五件套 roundtrip 本体 = kernel/cw_game_state 锁文件已登记)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    LEVEL_GRANT_PRODUCER,
    check_strategy_level_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    restore_state_snapshot,
    seed_opening_state,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '成长基金'
_OUT_OF_SCOPE = '特战资金'   # STRATEGY_ECONOMY 已登记,boss 金字段非到级字段


def _seeded_gs() -> GameState:
    """开局初始值(level/gold 现值已登记;宁缺勿造分支用无种子每局全新创建)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True
    seed_opening_state(gs)
    return gs


def _hold(gs: GameState, card: str) -> None:
    gs.write_logic(gs.active_strategies, [card],
                   produced_by='test-seed', evidence='t:card', sig=_LSIG)


def _latch(gs: GameState, card: str = _CARD) -> None:
    gs.write_logic(gs.strategy_conditional_done, (card,),
                   produced_by=LEVEL_GRANT_PRODUCER, evidence='t:done',
                   sig=_LSIG)


def test_matrix_below_target_and_latch_short_circuit() -> None:
    """矩阵②③⑤序(锁 9):持卡 level 8(未达标)→ None;一次性标志位后同级 →
    None(一次性封账,等级单调不减下达标态持续为真靠一次性标志位封账)。"""
    gs = _seeded_gs()
    _hold(gs, _CARD)
    gs.observe(gs.level, 8, sig=_SIG_OBS)
    gs.observe(gs.gold, 10, sig=_SIG_OBS)
    assert check_strategy_level_grants(gs) is None, '未达标误发放'
    _latch(gs)
    gs.observe(gs.level, 9, sig=_SIG_OBS)
    assert check_strategy_level_grants(gs) is None, '一次性标志位后重发'


def test_matrix_no_card_and_out_of_scope_card() -> None:
    """矩阵①序(锁 9/3):未持卡 → None;持表外卡(STRATEGY_ECONOMY
    已登记但无 gold_at_level_target 字段,特战资金 = boss 金族)→ None
    ——交集过滤按字段现值,表外卡禁从效果原文自动猜装。"""
    gs = _seeded_gs()
    gs.observe(gs.level, 9, sig=_SIG_OBS)
    gs.observe(gs.gold, 10, sig=_SIG_OBS)
    assert check_strategy_level_grants(gs) is None, '未持卡误发放'
    _hold(gs, _OUT_OF_SCOPE)
    assert STRATEGY_ECONOMY[_OUT_OF_SCOPE].gold_at_level_target == 0, \
        '前置:表外卡确无到级字段(字段改值时本锁随批复审)'
    assert check_strategy_level_grants(gs) is None, '表外卡误发放'


def test_prefers_silence_on_unobserved_then_recovers() -> None:
    """宁缺勿造(锁 4):每局全新创建无种子(level/gold 恒 None)→ None;gold
    先到仍 None(level 缺);level 达标到位 → 发放(值到位重查自愈,
    决策零写故无封账残留)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True
    _hold(gs, _CARD)
    assert gs.level.value is None and gs.gold.value is None, '前置:每局全新创建'
    assert check_strategy_level_grants(gs) is None, '全缺误发放'
    gs.observe(gs.gold, 10, sig=_SIG_OBS)
    assert check_strategy_level_grants(gs) is None, 'level 缺误发放'
    gs.observe(gs.level, 9, sig=_SIG_OBS)
    assert check_strategy_level_grants(gs) == (_CARD, 40), '值到位未自愈'


def test_grant_shape_and_purity_zero_write() -> None:
    """返回形状 + 纯决策零写(live 零接入调用通道前提):达标 → (规范卡名,
    金额);全量快照调用前后逐位相等(零写零 rng 契约,任何容器写即红)。"""
    gs = _seeded_gs()
    _hold(gs, _CARD)
    gs.observe(gs.level, 9, sig=_SIG_OBS)
    gs.observe(gs.gold, 33, sig=_SIG_OBS)
    before = gs.full_state_snapshot()
    grant = check_strategy_level_grants(gs)
    assert grant == (_CARD, 40), f'返回形状漂移: {grant!r}'
    assert gs.full_state_snapshot() == before, '纯决策函数发生容器写'


def test_snapshot_roundtrip_latch_honored() -> None:
    """快照存续(本腿语义层):达标发放后落一次性标志位 → full_state_snapshot →
    restore 往返 → 决策函数对恢复局返回 None(中断恢复不重发;rebuild
    类型面归 cw_game_state 域锁)。"""
    gs = _seeded_gs()
    _hold(gs, _CARD)
    gs.observe(gs.level, 9, sig=_SIG_OBS)
    gs.observe(gs.gold, 10, sig=_SIG_OBS)
    assert check_strategy_level_grants(gs) == (_CARD, 40)
    _latch(gs)
    restored = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(restored, gs.full_state_snapshot())
    restored.prep_anchored = True
    _hold(restored, _CARD)
    assert check_strategy_level_grants(restored) is None, '恢复局重发'
