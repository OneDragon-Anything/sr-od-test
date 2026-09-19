"""效果推进段(tick_effect_boundary)直测:迁移迭代
changes/2026-09-15-effect-ledger-self-advance landing 3.1 判据面。

节点边界金公式结算腿已随「结算真值收口」批退役(回滚 b390db204/77503d353/
5f7f69820:金真值 = 结算屏右上角计数经 apply_settlement_cover/settle_truth
无条件收口,公式腿再叠算 = 双计)——本文件只保留账本推进/刷新发放/异常
边界三判据:

- ①None 守卫(未观察不当真进节点)        → test_none_guard_skips_whole_segment
- ②备战帧推进 → advanced + 刷新到账      → test_prep_frame_advances_and_grants
- 段失败吞异常不上抛                     → test_segment_swallows_exceptions
"""

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    GameState,
    tick_effect_boundary,
)
from sr_od.application.currency_war.kernel.cw_investments import STRATEGY_EFFECTS


def test_none_guard_skips_whole_segment() -> None:
    """判据①:effective None → 整段跳过——在册效果零发放(「未观察不当真
    进节点」守卫,禁虚耗余期/虚累余额;现码 cw_loop 禁令随迁)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'], acquired_t=5)
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.effects.free_refresh_balance == 0, '未观察 = 不发放'
    assert gs.node_hist_ord is None


def test_prep_frame_advances_and_grants() -> None:
    """判据②:备战帧派生序推进 → 账本 advanced + 刷新余额按节点额度到账。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'], acquired_t=5)
    gs.node_hist_ord = 6
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.effects.free_refresh_balance == 2, '每进节点 +2(双手狸活载体)'


def test_segment_swallows_exceptions(monkeypatch) -> None:
    """异常边界:段内失败吞 Exception 记 warning 不上抛(不毒化派生链)。"""

    def _boom(ordinal):
        raise RuntimeError('probe')

    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.node_hist_ord = 12
    monkeypatch.setattr(type(gs.effects), 'advance_node', _boom)
    tick_effect_boundary(gs, prep_frame=True)   # 不上抛即判据
