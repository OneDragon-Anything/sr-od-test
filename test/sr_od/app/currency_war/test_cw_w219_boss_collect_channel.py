"""W219(ADR-0397)行为锁:boss 采集主通道切 CollectPlaneIntel。

锁三件事(修复语义的固化出口):
- **简报读数不进 session**:`ctx.cw_briefing_bosses`(简报三卡 OCR,画面 x 序)
  不再 copy 进 `session.briefing_bosses`——简报卡排列≠位面序(2026-08-26 佩佩局
  实证:读数 [巨鹿,造梦互动,深穹智械] vs 位面详情逐位面亲证 [巨鹿,增熵,绘师]),
  按序消费 = 位面 2/3 的 boss_fit 从第一天打错 boss;
- **实采通道存在且统一**:session.briefing_bosses 唯一写入端 = battle_loop 备战
  稳定帧的 CollectPlaneIntel 实采块(触发条件「新 match 且 session 空」——开局局
  简报后 session 恒空,自然走同通道,接管局同);
- **消费端回归**:session.briefing_bosses(实采真值,位面序)→ state.plane_bosses
  (default_strategy.update_target 注入,boss_fit 输入)。

静态锁模式沿用 r333/r337/w28 先例(inspect.getsource 断言接线形态)。
"""
import inspect


def test_briefing_boss_slot_not_copied_into_session() -> None:
    """锁①:简报候选集槽不再被 copy 进 session(旧 __init__ copy 行不存在)。"""
    from sr_od.application.currency_war.operations import battle_loop

    src = inspect.getsource(battle_loop.CurrencyWarRunLoop)
    # 旧接线唯一形态:`_session.briefing_bosses = list(self.ctx.cw_briefing_bosses)`
    # (ADR-0397 前的 __init__ copy)。任何把简报读数按序送进 session 的回潮都算破坏。
    assert '_session.briefing_bosses = list(self.ctx.cw_briefing_bosses)' not in src, (
        '简报读数回潮进 session(ADR-0397:简报卡排列≠位面序,禁止按序当 plane_bosses)'
    )
    # ctx 简报槽仍可被写(候选集/遥测),但不应有任何「取走清空」式消费残留
    # (旧 copy 块的配套行;存在 = 又有消费方把它当真值)。
    assert 'self.ctx.cw_briefing_bosses = None' not in src


def test_collect_plane_intel_is_session_boss_writer() -> None:
    """锁②:session.briefing_bosses 唯一写入端 = CollectPlaneIntel 实采块,开局局统一触发。"""
    from sr_od.application.currency_war.operations import battle_loop

    src = inspect.getsource(battle_loop.CurrencyWarRunLoop)
    # 实采写入端:接管/开局统一块的 `_sess.briefing_bosses = _names`
    assert '_sess.briefing_bosses = _names' in src, (
        'CollectPlaneIntel 实采接线消失(session.briefing_bosses 失去写入端)'
    )
    # 触发条件含「session.briefing_bosses 空」——开局局简报后 session 恒空,
    # 该条件保证开局局与接管局走同一实采通道(条件退化成「仅接管局」即回潮)。
    assert "not getattr(self.ctx.cw_match.session, 'briefing_bosses', None)" in src
    # 实采 op 确实被调用(防条件块保留但 op 调用被删的空壳)。
    assert 'CollectPlaneIntel(self.ctx)' in src


def test_session_collected_bosses_flow_to_state_plane_bosses() -> None:
    """锁③(消费端回归):session.briefing_bosses(位面序实采真值)→ state.plane_bosses。"""
    from sr_od.application.currency_war.cw_strategy import StrategySession
    from sr_od.application.currency_war.cw_state import GameState
    from sr_od.application.currency_war.strategies.default_strategy import (
        DefaultCwStrategy,
    )

    # 佩佩局亲证真值序(位面 1..3)——实采值经注入链进 state 供 boss_fit 按位面消费
    truth = ['巨鹿', '增熵', '绘师']
    state = GameState()
    session = StrategySession()
    session.briefing_bosses = list(truth)
    DefaultCwStrategy().update_target(state, session, None)
    assert state.plane_bosses == truth, (
        f'实采真值未注入 state.plane_bosses(实际 {state.plane_bosses})'
    )
