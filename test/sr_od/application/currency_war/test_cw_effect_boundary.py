"""效果推进段(tick_effect_boundary)直测:迁移迭代
changes/2026-09-15-effect-ledger-self-advance landing 3.1 判据面。

判据 → 测试对照(设计 design.md §2.1 a-f):
- ①None 守卫(未观察不当真进节点)        → test_none_guard_skips_whole_segment
- ②备战帧推进 → advanced + 刷新到账      → test_prep_frame_advances_and_grants
- ③金结算参数 = 派生序反解键(错窗防护)    → test_gold_settlement_key_matches
- ④同序幂等(无二次发放/结算)             → test_same_ord_idempotent
- ⑤败局跳过金结算、其余照常              → test_loss_skips_gold_only
- ⑥空/None 策略 → 聚合缺省参数结算照常    → test_strategies_none_still_settles
- ⑦kind 空串照传(else→combat 现值语义)   → test_kind_empty_passes_through
- 补给递延(prep_frame=False 不结算)      → test_non_prep_frame_defers_gold
- 金未读:水位不动 + 重试后落             → test_gold_none_watermark_retries
- None 守卫静默不上抛                    → test_none_guards_silent
- 水位入快照(离线判读可见)               → test_watermark_in_snapshot
- 段失败吞异常不上抛                     → test_segment_swallows_exceptions
"""

from sr_od.application.currency_war.kernel.cw_economy import round_start_income
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
    apply_settlement_cover,
    register_sig_actors,
    tick_effect_boundary,
)
from sr_od.application.currency_war.kernel.cw_investments import STRATEGY_EFFECTS

register_sig_actors('TestSigWriter')


def _sig():
    """渠道①签名(obs 族;观察写入口签名必填,ADR-0634)。"""
    return ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _mk_gs(*, gold=30, streak=2, strategies=(), node_kind='battle',
           killed=True, hist=12):
    """标准局面容器:节点 2-3、金 30、连胜 2、胜局结算(参数可覆写)。

    gold=None = 容器金未读形态(不 observe 金 + 结算页不带金);
    killed=None = 不写结算(容器 settlement 为 None)。
    """
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if gold is not None:
        gs.observe(gs.gold, gold, sig=_sig())
    gs.observe(gs.streak, streak, sig=_sig())
    if strategies:
        gs.observe(gs.active_strategies, list(strategies), sig=_sig())
    gs.observe(gs.node, NodeKey(plane=2, round_num=3, kind=node_kind), sig=_sig())
    gs.node_hist_ord = hist
    if killed is not None:
        apply_settlement_cover(gs, hp_after=76, streak_after=streak,
                               killed=killed)
    return gs


def test_none_guard_skips_whole_segment() -> None:
    """判据①:effective None → 整段跳过——在册效果零发放(「未观察不当真
    进节点」守卫,禁虚耗余期/虚累余额;现码 cw_loop 禁令随迁)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'], acquired_t=5)
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.free_refresh_balance.value is None, '未观察 = 不发放'
    assert gs.node_hist_ord is None


def test_prep_frame_advances_and_grants() -> None:
    """判据②:备战帧派生序推进 → 账本 advanced + 刷新余额按节点额度到账。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'], acquired_t=5)
    gs.node_hist_ord = 6
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.free_refresh_balance.value == 2, '每进节点 +2(双手狸活载体)'


def test_gold_settlement_key_matches() -> None:
    """判据③:金结算参数 = 派生序反解键(2-3)+ 镜像 kind;金额与
    round_start_income 单一源重算一致(F1 错窗防护:非镜像旧键)。"""
    gs = _mk_gs(gold=30, streak=2, strategies=(), node_kind='battle')
    expected = round_start_income(2, 3, 'battle', 30, 2)   # 缺省倍率/息修饰
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.gold.value == 30 + expected.total
    assert gs.boundary_settled_ord == 12


def test_strategies_in_still_settles() -> None:
    """判据⑥(在册半边):容器策略在册 → 聚合参数路径照常结算落水位。"""
    gs = _mk_gs(strategies=['固定理财'])
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.boundary_settled_ord == 12
    assert gs.gold.value == 30 + round_start_income(2, 3, 'battle', 30, 2).total


def test_same_ord_idempotent() -> None:
    """判据④:同序重复调用幂等——账本去重 + 水位已落 = 无二次结算。"""
    gs = _mk_gs()
    tick_effect_boundary(gs, prep_frame=True)
    gold_after_first = gs.gold.value
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.gold.value == gold_after_first, '同序禁二次结算'
    assert gs.boundary_settled_ord == 12


def test_loss_skips_gold_only() -> None:
    """判据⑤:败局(killed=False)→ 金结算跳过、水位不落(下一胜局节点重试,
    败补口径维持观察覆盖),推进/发放段照常。"""
    gs = _mk_gs(killed=False)
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.gold.value == 30, '败局不结金'
    assert gs.boundary_settled_ord is None, '败局水位不落'


def test_kind_empty_passes_through() -> None:
    """判据⑦:kind 空串照传 settle——round_start_income else→combat 落袋
    是现值语义(不设 kind 闸,加闸 = 收入语义变化)。"""
    gs = _mk_gs(node_kind='')
    expected = round_start_income(2, 3, '', 30, 2)
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.gold.value == 30 + expected.total


def test_non_prep_frame_defers_gold() -> None:
    """补给递延/过渡帧语义:prep_frame=False(0q/0p/弹窗推进帧、补给入口帧)
    → 账本推进照常、金结算不触发、水位不动;递延至备战帧恰结一次。"""
    gs = _mk_gs()
    tick_effect_boundary(gs, prep_frame=False)
    assert gs.gold.value == 30, '非备战帧不结算'
    assert gs.boundary_settled_ord is None, '水位不动'
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.gold.value == 30 + round_start_income(2, 3, 'battle', 30, 2).total
    assert gs.boundary_settled_ord == 12, '递延后备战帧恰结一次'


def test_gold_none_watermark_retries() -> None:
    """金未读形态:静默跳过且水位必不动(settle 对金未读返回 written=False
    ∧ total=0,与「无欠账」同形,不预判则误落水位 → 永久漏结)。

    2026-09-18 边界金补结批锁语义重推:金观察到达且带真值变化 =
    待补结闩消费(实读真值随覆盖照常入逻辑,补结由观察了结),其后公式
    结算禁再发生(真值 + 公式值双计防护,同族判据 =
    test_cw_boundary_gold_backfill.test_observation_consumes_latch_formula_
    must_not_double_add);公式重试腿 = 金读 carried 无观察到达形态,
    锁在 test_cw_boundary_gold_backfill.test_formula_settlement_normal_
    path_unaffected——本测试后半由「金可读后重试落水位」改锁「观察消费
    闩后公式禁发」。"""
    gs = _mk_gs(gold=None)
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.boundary_settled_ord is None, '金未读水位必不动'
    gs.observe(gs.gold, 25, sig=_sig())
    assert gs.exec_books.boundary_gold_pending is False, '真值变化观察消费闩'
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.boundary_settled_ord is None, '闩已消费,公式结算禁发'
    assert gs.gold.value == 25, '真值已在逻辑,禁公式叠算'


def test_none_guards_silent() -> None:
    """None 守卫静默:节点镜像缺席 → 金结算静默跳过(不上抛、无告警刷屏),
    推进段照常。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.node_hist_ord = 12
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.boundary_settled_ord is None


def test_watermark_in_snapshot() -> None:
    """水位入 full_state_snapshot(对照 node_hist_ord 先例):journal 行行
    自足的离线判读证据面(「这节点为什么没结金」可查)。"""
    gs = _mk_gs()
    assert 'boundary_settled_ord' in gs.full_state_snapshot()
    tick_effect_boundary(gs, prep_frame=True)
    assert gs.full_state_snapshot()['boundary_settled_ord'] == 12


def test_segment_swallows_exceptions(monkeypatch) -> None:
    """异常边界:段内失败吞 Exception 记 warning 不上抛(不毒化派生链)。"""

    def _boom(ordinal):
        raise RuntimeError('probe')

    gs = _mk_gs()
    monkeypatch.setattr(type(gs.effects), 'advance_node', _boom)
    tick_effect_boundary(gs, prep_frame=True)   # 不上抛即判据


def test_pipeline_0q_then_prep_settles_derived_key() -> None:
    """landing 3.2 接线判据(F1 错窗防护 + F7 恰一次):0q 过渡帧派生推进
    (2,1) 不结算(递延),备战帧结算键 = 派生序反解(2-1) 非镜像旧键 (1-9);
    备战腿同序派生经账本去重,无二次推进/发放。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        SCREEN_PLANE_TRANSITION,
        SCREEN_PREP_FRAME,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, 40, sig=_sig())
    gs.observe(gs.streak, 2, sig=_sig())
    gs.observe(gs.node, NodeKey(plane=1, round_num=9, kind='boss'), sig=_sig())
    apply_settlement_cover(gs, hp_after=70, streak_after=2, killed=True, gold=40)
    # 0q 过渡帧:phase_round = 离场位面读数(1,9),位面过渡腿派生推进 (2,1);
    # 效果段 prep_frame=False → 只推进不结算
    gs.observe_screen_context(SCREEN_PLANE_TRANSITION, phase_round=(1, 9), sig=_sig())
    assert gs.gold.value == 40, '过渡帧不结算(F1 错窗防护)'
    assert gs.boundary_settled_ord is None, '递延水位不动'
    # 备战帧:镜像随帧刷新(模拟漏斗序)+ 备战腿派生同序 → 恰一次结算
    gs.observe(gs.node, NodeKey(plane=2, round_num=1, kind='battle'), sig=_sig())
    gs.observe_screen_context(SCREEN_PREP_FRAME, phase_round=(2, 1),
                              top_raw='备战阶段 2-1', sig=_sig())
    expected = round_start_income(2, 1, 'battle', 40, 2)
    assert gs.gold.value == 40 + expected.total, '派生键结算(非镜像旧键 1-9)'
    assert gs.boundary_settled_ord == 10, '恰一次(同序派生去重)'
