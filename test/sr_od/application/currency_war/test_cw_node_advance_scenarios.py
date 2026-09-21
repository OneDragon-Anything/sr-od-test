"""节点推进动作上报 场景锁(迭代
changes/2026-09-20-node-advance-action-report landing §3.6 走查集按新模型
收口;设计依据 = 同目录 design.md §2.1-§2.4/§2.7)。

场景 ↔ 测试对照(landing §3.6 清单;**已有的不重写**,本文件只收缺口):

- S1 开局首锚定建 1(v=None 行)→ 已有
  test_cw_node_advance_report.test_first_anchor_establishes_and_grants
- S2 快弹窗全型(确认→弹窗→选卡→备战锚定)→
  test_fast_popup_advance_precedes_pick_and_prep_reanchor
- 补给两形态 → 已有 test_cw_supply_advance_wiring(两剧本 + 证据 miss)
- boss 段(奖励关确认推进 + 简报类型直定 + 证据 miss/bail 后迟到流转
  不产生错位类型直定)→ test_boss_segment_bail_seam_and_cross_plane
  (简报直定 hist 目标基础锁 = 已有
  test_cw_game_state_contract.test_boss_briefing_report_types_hist_node)
- 跨位面确认(序号公式自然跨位,E13)→ 同上测试尾段
- S9 恢复局锚定 / 锁定臂门挡自愈(value 守卫挡首确认→战后锚定补齐)→
  test_locked_resume_value_guard_self_heal
- 重复上报结构挡 → 已有
  test_cw_node_advance_report.test_gate_blocks_unconfirmed_logic
- 结算真值金采样(条件族按结算金评估,design §2.7-3)→
  test_settle_truth_gold_samples_conditional_grant
- 补推当帧发放 → 已有
  test_cw_node_advance_report.test_repair_advance_ticks_ledger
"""
from __future__ import annotations

import time
from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    GameState,
    apply_settlement_cover,
    effective_node_ord,
    game_state_of,
    node_ordinal_of,
    observe_node_anchor,
    report_node_advance,
)
from sr_od.application.currency_war.kernel.cw_investments import STRATEGY_EFFECTS
from sr_od.application.currency_war.kernel.cw_screen_report.boss_briefing import (
    CwScreenBossBriefingObs,
    report_screen_boss_briefing_obs,
)

_ACTOR = 'TestHost'


def _gs_with(test_context, monkeypatch, spec_name: str) -> GameState:
    """session 旁表容器挂 ctx.cw_match(op 上报口供给面)+ 指定效果在册
    (发放断言活载体);返回容器与 gs_of_ctx 同源。"""
    session = cw4_session()
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    gs = game_state_of(session)
    gs.effects.register_strategy(STRATEGY_EFFECTS[spec_name], acquired_t=5)
    return gs


# ============================================================ S2 快弹窗全型


def test_fast_popup_advance_precedes_pick_and_prep_reanchor(
    test_context, monkeypatch,
) -> None:
    """S2 快弹窗全型:结算确认的转移证据 = 弹窗锚(投资策略,白名单全集
    成员)→ 确认时点即推进(design §2.3「先推进后选卡」由因果序结构性
    成立,不依赖弹窗推断);选卡登记零推进(登记语义归拿卡上报侧,
    design §2.6);选卡后备战帧锚定等值 reanchor 翻回观察态,下一终结
    动作解锁。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_settle_confirm import (
        CwOpSettleConfirm,
    )

    gs = _gs_with(test_context, monkeypatch, '双手狸开键盘！')
    observe_node_anchor(gs, 1, trigger_screen='货币战争-备战', actor=_ACTOR)

    op = CwOpSettleConfirm(test_context)
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    # 证据集仅弹窗锚命中(遭遇/投资策略锚 = 白名单成员;design §2.3
    # 证据集同源条款),其余锚 miss
    monkeypatch.setattr(
        op, 'round_by_find_area',
        lambda scr, s, a, **k: _Area(
            (s, a) == ('货币战争-投资策略', '标识-请选择投资策略')))
    rs = _run_node(test_context, op, op.confirm)

    assert rs.is_success, f'弹窗锚证据应放行上报:{rs!r}'
    assert gs.node_ord.value == 2 and gs.node_ord.source == 'logic', (
        '确认点击时点即推进(快弹窗:推进先于弹窗选卡)')

    # 选卡登记(拿卡上报侧):零节点推进
    gs.effects.register_strategy(STRATEGY_EFFECTS['加油站'], acquired_t=6)
    assert gs.node_ord.value == 2 and gs.node_ord.source == 'logic', (
        '选卡登记不推进节点(登记语义归拿卡侧,design §2.6)')

    # 选卡后备战帧锚定:等值 reanchor 翻观察态 → 下一终结动作解锁
    assert observe_node_anchor(gs, 2, trigger_screen='货币战争-备战',
                               actor='CwScreenPrep') == 'reanchor'
    assert report_node_advance(gs, trigger='settle_confirm') is True
    assert effective_node_ord(gs) == 3, 'reanchor 后下一确认可推进'


# ================================================== boss 段:bail 封缝 + 跨位面


def test_boss_segment_bail_seam_and_cross_plane(
    test_context, monkeypatch,
) -> None:
    """boss 段帧序列锁(S6/E12/E13 + 攻击 R3 bail 变体):

    - E12 奖励关结算确认推进 → boss 节点(位面末 ord 9);
    - **bail 封缝(T-2 reviewer 转交)**:CwOpSettleConfirm bail(过渡帧
      双 miss 上界退出)后流转迟到(简报锚后现身)——CwScreenBattleWait
      ③段白名单命中出口补 settle_confirm 上报,恢复「白名单命中 ⇒ 必有
      上报」不变量(design §2.3 证据集同源条款):hist 已推进至 boss 节点,
      简报类型直定目标不落错节点(不写奖励关 ord 8);
    - E13 boss 结算确认 → 序号公式自然跨位面(9+1=10=(2-1)*9+1,
      design §2.1),位面 2 首备战帧等值 reanchor 解锁下一确认。
    """
    from sr_od.application.currency_war.currency_war_config import (
        CurrencyWarConfig,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait as bwo,
    )

    gs = _gs_with(test_context, monkeypatch, '双手狸开键盘！')
    # 奖励关(ord 8)已锚定;结算确认推进 → boss 节点 ord 9(E12)
    observe_node_anchor(gs, 8, trigger_screen='货币战争-备战', actor=_ACTOR)
    assert report_node_advance(gs, trigger='settle_confirm') is True
    assert effective_node_ord(gs) == 9

    # bail 后迟到流转:hist 已在 9(logic),简报直定目标 = 9(boss 节点)
    report_screen_boss_briefing_obs(gs, CwScreenBossBriefingObs(on_screen=True))
    _node = gs.node.value
    assert _node is not None and _node.kind == 'boss'
    assert (_node.plane, _node.round_num) == (1, 9), (
        '简报类型直定目标 = 现 hist(boss 节点),不落错奖励关节点')

    # 补报出口(bail 封缝)行为锁:白名单命中 → settle_confirm 补报幂等
    # (op 内已报则观察态门挡零推进)
    st = bwo.SettlementState(run_start_ts=time.monotonic(), is_new_match=False)
    op = bwo.CwScreenBattleWait(
        test_context, st, CurrencyWarConfig(test_context.current_instance_idx))
    monkeypatch.setattr(op, 'last_screenshot', None, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(False))
    monkeypatch.setattr(op, '_hit_completion_anchor', lambda screen: True)
    rs = op.wait()
    assert rs.is_success and rs.status == 'back_to_loop', (
        f'白名单命中出口应交回循环:{rs!r}')
    assert effective_node_ord(gs) == 9, '补报幂等:已推进零重复推进'

    # E13:boss 结算确认 → 10 = 位面2 第1轮(序号公式自然跨位面)
    observe_node_anchor(gs, 9, trigger_screen='货币战争-备战', actor=_ACTOR)
    assert report_node_advance(gs, trigger='settle_confirm') is True
    assert effective_node_ord(gs) == 10 == node_ordinal_of(2, 1)
    # 位面 2 首备战帧等值 reanchor → 下一确认解锁
    assert observe_node_anchor(
        gs, node_ordinal_of(2, 1), trigger_screen='货币战争-备战',
        actor='CwScreenPrep') == 'reanchor'
    assert report_node_advance(gs, trigger='settle_confirm') is True
    assert effective_node_ord(gs) == 11


# ================================================= S9 恢复局 / 锁定臂自愈


def test_locked_resume_value_guard_self_heal(test_context, monkeypatch) -> None:
    """锁定臂门挡自愈(design §2.2/§2.3):锁定臂直出战无备战帧锚定
    (v=None)→ 首次结算确认被 **value 守卫**挡(攻击 R1:新容器缺省
    source 即 observation,门必须按 value 在场判);战后备战帧观察锚定
    以绝对读数首锚定补齐(恢复局重建语义,S9:R=局中任意节点)——
    绝对值坐标无 skew,后续终结动作正常推进。"""
    gs = _gs_with(test_context, monkeypatch, '双手狸开键盘！')

    # 锁定臂直出战:无任何锚定,首次结算确认被 value 守卫挡
    assert report_node_advance(gs, trigger='settle_confirm') is False
    assert gs.node_ord.value is None and gs.node_hist_ord is None, (
        'value 守卫挡首确认(零推进零 hist)')

    # 战后备战帧锚定:恢复局 mid-game 读数 7 → 首锚定 + 尾段发放
    assert observe_node_anchor(gs, 7, trigger_screen='货币战争-备战',
                               actor='CwScreenPrep') == 'first_anchor'
    assert gs.node_ord.value == 7 and gs.node_ord.source == 'observation'
    assert gs.node_hist_ord == 7
    assert gs.effects.free_refresh_balance == 2, '首锚定当帧发放(无 skew)'

    # 自愈后流程续行:下一结算确认正常推进
    assert report_node_advance(gs, trigger='settle_confirm') is True
    assert effective_node_ord(gs) == 8


# ================================================== 结算真值金采样(§2.7-3)


def test_settle_truth_gold_samples_conditional_grant(
    test_context, monkeypatch,
) -> None:
    """结算真值金采样(design §2.7-3):条件族(本金充裕,50/10/3)的
    每节点发放按 **结算真值金** 评估——结算链(apply_settlement_cover →
    settle_truth)先于「继续挑战」点击,推进时点采到的金 = 战后真值,
    比战前推算金(陈旧金)更准。时序锁:战前推算金低于阈值 → 首锚定
    零授予;结算真值 85 落账后确认推进 → 按真值授予 3 次。"""
    gs = _gs_with(test_context, monkeypatch, '本金充裕')

    # 战前推算金(旧路径快弹窗会采到的陈旧金):低于阈值
    gs.write_logic(gs.gold, 40, produced_by='TestBoardIncome',
                   sig=ChannelSig(family='logic_action',
                                  actor='TestBoardIncome', mode='compute'))
    observe_node_anchor(gs, 2, trigger_screen='货币战争-备战', actor=_ACTOR)
    assert gs.gold.value == 40
    assert gs.effects.free_refresh_balance == 0, (
        '战前陈旧金 40 ≤ 阈值 50:首锚定零条件授予')

    # 结算链先于确认点击:结算屏真值金 85 无条件收口(settle_truth)
    apply_settlement_cover(gs, hp_after=80, streak_after=1, gold=85)
    assert gs.gold.value == 85

    assert report_node_advance(gs, trigger='settle_confirm') is True
    assert effective_node_ord(gs) == 3
    assert gs.effects.free_refresh_balance == 3, (
        '推进时点按结算真值 85 评估:超出 35 → 每 10 金 1 次,封顶 3'
        '(采到陈旧金 40 则为 0——时序锁)')
