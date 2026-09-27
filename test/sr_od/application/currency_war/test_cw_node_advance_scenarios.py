"""节点推进动作上报 场景锁(迭代
 §3.6 走查集按新模型
收口§2.4/§2.7)。

场景 ↔ 测试对照(landing §3.6 清单;**已有的不重写**,本文件只收缺口):

- S1 开局首锚定建 1(v=None 行)→ 已有
  test_cw_node_advance_report.test_first_anchor_establishes_and_grants
- S2 快弹窗全型(确认→弹窗→选卡→备战锚定)→
  test_fast_popup_advance_precedes_pick_and_prep_reanchor
- 补给两形态 → 已有 test_cw_supply_advance_wiring(两剧本,点击即推进)
- boss 段(奖励关确认点击即推进 + 简报类型直定 + 直定目标恒正确)→
  test_boss_segment_click_advance_and_cross_plane
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
    """S2 快弹窗全型:结算确认**点击即上报**(去证据门,用户裁定
    2026-09-21——点了就是上报,无弹窗锚探查)→ 推进先于弹窗选卡由因果序
    结构性成立(design §2.3,不依赖弹窗推断);选卡登记零推进(登记语义
    归拿卡上报侧,design §2.6);选卡后备战帧锚定等值 reanchor 翻回观察态,
    下一终结动作解锁。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_settle_confirm import (
        CwOpSettleConfirm,
    )

    gs = _gs_with(test_context, monkeypatch, '双手狸开键盘！')
    observe_node_anchor(gs, 1, trigger_screen='货币战争-备战', actor=_ACTOR)

    op = CwOpSettleConfirm(test_context)
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'screenshot', lambda: object())
    # 「继续挑战」点击机械半全桩命中(点击即上报,零证据探查)
    monkeypatch.setattr(
        op, 'round_by_find_and_click_area',
        lambda *a, **k: _Area(True))
    _run_node(test_context, op, op.confirm)

    assert gs.node_ord.value == 2 and gs.node_ord.source == 'logic', (
        '确认点击时点即推进(快弹窗:推进先于弹窗选卡)')

    # 选卡登记(拿卡上报侧):零节点推进
    gs.effects.register_strategy(STRATEGY_EFFECTS['加油站'], acquired_t=6)
    assert gs.node_ord.value == 2 and gs.node_ord.source == 'logic', (
        '选卡登记不推进节点(登记语义归拿卡侧,design §2.6)')

    # 选卡后备战帧锚定:等值 reanchor 翻观察态 → 下一终结动作解锁
    assert observe_node_anchor(gs, 2, trigger_screen='货币战争-备战',
                               actor='CwScreenPrep') == 'reanchor'
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert effective_node_ord(gs) == 3, 'reanchor 后下一确认可推进'


# ============================================== boss 段:直定目标 + 跨位面


def test_boss_segment_click_advance_and_cross_plane(
    test_context, monkeypatch,
) -> None:
    """boss 段帧序列锁(S6/E12/E13;去证据门重述 2026-09-21):

    - E12 奖励关结算确认**点击即推进** → boss 节点(位面末 ord 9);
    - 简报类型直定目标恒正确:无证据门 ⇒ 上报先于下一节点任何画面渲染
      恒成立 ⇒ hist 已推进至 boss 节点,简报直定不落错节点(不写奖励关
      ord 8)——原 bail 缝随证据等待机制退役结构性消失;
    - E13 boss 结算确认 → 序号公式自然跨位面(9+1=10=(2-1)*9+1,
      design §2.1),位面 2 首备战帧等值 reanchor 解锁下一确认。
    """
    gs = _gs_with(test_context, monkeypatch, '双手狸开键盘！')
    # 奖励关(ord 8)已锚定;结算确认点击即推进 → boss 节点 ord 9(E12)
    observe_node_anchor(gs, 8, trigger_screen='货币战争-备战', actor=_ACTOR)
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert effective_node_ord(gs) == 9

    # 简报帧直定:hist 已在 9(logic),简报直定目标 = 9(boss 节点)
    report_screen_boss_briefing_obs(gs, CwScreenBossBriefingObs(on_screen=True))
    _node = gs.node.value
    assert _node is not None and _node.kind == 'boss'
    assert (_node.plane, _node.round_num) == (1, 9), (
        '简报类型直定目标 = 现 hist(boss 节点),不落错奖励关节点')

    # E13:boss 结算确认 → 10 = 位面2 第1轮(序号公式自然跨位面)
    observe_node_anchor(gs, 9, trigger_screen='货币战争-备战', actor=_ACTOR)
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert effective_node_ord(gs) == 10 == node_ordinal_of(2, 1)
    # 位面 2 首备战帧等值 reanchor → 下一确认解锁
    assert observe_node_anchor(
        gs, node_ordinal_of(2, 1), trigger_screen='货币战争-备战',
        actor='CwScreenPrep') == 'reanchor'
    assert report_node_advance(gs, trigger='settle_confirm').applied
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
    assert report_node_advance(gs, trigger='settle_confirm').applied is False
    assert gs.node_ord.value is None and gs.node_hist_ord is None, (
        'value 守卫挡首确认(零推进零 hist)')

    # 战后备战帧锚定:恢复局 mid-game 读数 7 → 首锚定 + 尾段发放
    assert observe_node_anchor(gs, 7, trigger_screen='货币战争-备战',
                               actor='CwScreenPrep') == 'first_anchor'
    assert gs.node_ord.value == 7 and gs.node_ord.source == 'observation'
    assert gs.node_hist_ord == 7
    assert gs.free_refresh_left.value == 2, '首锚定当帧发放(无 skew)'

    # 自愈后流程续行:下一结算确认正常推进
    assert report_node_advance(gs, trigger='settle_confirm').applied
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
    assert gs.free_refresh_left.value is None, (
        '战前陈旧金 40 ≤ 阈值 50:首锚定零条件授予')

    # 结算链先于确认点击:结算屏真值金 85 无条件收口(settle_truth)
    apply_settlement_cover(gs, hp_after=80, streak_after=1, gold=85)
    assert gs.gold.value == 85

    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert effective_node_ord(gs) == 3
    assert gs.free_refresh_left.value == 3, (
        '推进时点按结算真值 85 评估:超出 35 → 每 10 金 1 次,封顶 3'
        '(采到陈旧金 40 则为 0——时序锁)')


# ================================= CwScreenPrep 锚定接线(design §2.4 写端 1)


def test_prep_heavy_receipt_anchors_node(test_context, monkeypatch) -> None:
    """备战帧锚定接线锁(design §2.4 写端 1,攻击 F1 定谳;T-6 r1 打回补):
    CwScreenPrep heavy 观察回执携带本帧 plane/round →
    ``observe_node_anchor``(唯一生产锚定缝,cw_screen_prep.py::_observe
    heavy 段)——首帧 first_anchor 建账含尾段发放、后续读数 advance/
    reanchor 落账、回执缺位跳过(禁猜)。本缝静默丢失时生产 value 门挡
    全程卡死,故直锁 wiring 面(与补给屏锚定对称,先例 =
    test_cw_supply_advance_wiring)。"""
    from sr_od.application.currency_war.obs import cw_observe_full as ofm
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep as pp,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        CwScreenPrep,
    )

    session = cw4_session()
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    gs = game_state_of(session)
    gs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'], acquired_t=5)

    # 回执剧本位:(plane, round) 可变;level=None(cap 审计跳过)
    _receipt: dict = {}

    def _fake_observe_full(ctx, screen, **kw):
        _r = _receipt.get('r')
        return {
            'bench_view': None, 'deployed_rows': None,
            'read_receipt': (SimpleNamespace(plane=_r[0], round_num=_r[1],
                                             level=None)
                             if _r is not None else None),
            'node_slots': None, 'owned_equips': None,
            'occupied_equips': None, 'substate': None,
        }

    monkeypatch.setattr(ofm, 'observe_full', _fake_observe_full)
    op = CwScreenPrep(test_context)
    monkeypatch.setattr(op, 'park_cursor', lambda **k: None)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(False))
    monkeypatch.setattr(op, '_reconcile_tracking',
                        lambda bv, dr, screen: (None, None, None))
    monkeypatch.setattr(pp, 'row_area_centers', lambda ctx, name: [])
    monkeypatch.setattr(pp, 'read_ore_sights', lambda ctx, screen: [])
    monkeypatch.setattr(pp, 'read_deploy_cap', lambda ctx, screen: None)
    monkeypatch.setattr(pp, 'read_deployed_count', lambda ctx, screen: None)

    def _run_observe() -> None:
        _run_node(test_context, op,
                  lambda: op._observe(True, screen=object()))

    # 回执缺位(读数未读)→ 跳过锚定(禁猜,best-effort)
    _receipt['r'] = None
    _run_observe()
    assert gs.node_ord.value is None, '回执缺位零锚定(禁猜)'

    # 开局首帧(1-1)→ first_anchor 建账 + 尾段发放
    _receipt['r'] = (1, 1)
    _run_observe()
    assert gs.node_ord.value == 1 and gs.node_ord.source == 'observation'
    assert gs.node_hist_ord == 1
    assert gs.free_refresh_left.value == 2, '首锚定当帧发放'

    # 下一节点读数(1-2)→ advance 补推落账(观察采新即确认态)
    _receipt['r'] = (1, 2)
    _run_observe()
    assert gs.node_ord.value == 2 and gs.node_ord.source == 'observation'

    # 同值再读 → reanchor(等值确认,源态保持 observation)
    _receipt['r'] = (1, 2)
    _run_observe()
    assert gs.node_ord.value == 2 and gs.node_ord.source == 'observation'
