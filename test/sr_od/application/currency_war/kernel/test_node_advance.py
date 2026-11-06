"""节点序位与推进测试面(推进/锚定原语 + 场景走查 + 环境修饰序位表)。

节点序位 = (位面, 轮) 元组键(2026-10-12-abolish-node-ordinal §3.2)。
三节测试面:

- **推进原语判据面**(``advance_node_effective`` /
  ``report_node_advance`` 观察态门 / ``observe_node_anchor`` 锚定处置,
  landing §3.1 完成判据 + design §2.11 测试 2/3):门挡/首锚定/重复上报
  结构挡/恰一档/等值翻锚/倒退免疫/补推含尾段发放/跨位面/越域丢弃/
  终局事件式;
- **场景走查测试**(landing §3.6 走查集:快弹窗全型/boss 段/恢复局
  自愈/结算真值金采样/备战锚定接入调用;已有判据不重写,本节只收缺口);
- **环境修饰序位表**(人身意外险 id 107 节点序列环境修饰,设计 §4
  锁 1-11;设计权威版本 = .debug/progress/2026-09-23-invest-effects-calc/
  designs/T-8-renshenyiwai-xian.md,钉住设计约定不断言实现细节):修饰规则
  纯函数/场字段生命周期/next_screen 推导/观察读链两位数/白名单归属/
  sim 状态副本里的值/键化消费面/acquired_key 同坐标系/结算读数与单调门。
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

from sr_od.application.currency_war.kernel import cw_game_state as gs_mod
from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel import cw_node_schedule as ns
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    _portal_acquired_key,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
    _obs_node_pos,
    _shop_panel_type_target,
    _write_derived_node_type,
    apply_settlement_cover,
    effective_node_pos,
    game_state_of,
    observe_node_anchor,
    report_node_advance,
    restore_state_snapshot,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    P1_NODE_SEQUENCE,
    P2_NODE_SEQUENCE,
    P3_NODE_SEQUENCE,
    PLANE_NODE_TABLES,
    node_round_cap,
    node_sequence_of,
    resolve_plane_node_seqs,
)
from sr_od.application.currency_war.kernel.cw_screen_report.boss_briefing import (
    CwScreenBossBriefingObs,
    report_screen_boss_briefing_obs,
)
from sr_od.application.currency_war.obs.cw_observation import (
    parse_phase_round_text,
    phase_round_in_range,
)
from sr_od.application.currency_war.obs.cw_settlement_obs import (
    parse_settlement_round,
)

_ACTOR = 'TestHost'
_SIG_OBS = ChannelSig(family='obs', actor='TestSeqEnv', mode='read')


def _logic_sig(actor: str = 'TestSeqEnv') -> ChannelSig:
    return ChannelSig(family='logic_action', actor=actor, mode='compute')


# ================================================================ 推进原语判据面

def _gs_with_double_pair() -> GameState:
    """新容器 + 双手狸已登记(每进节点 +2 免费刷新,发放断言活载体)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                 acquired_key=(1, 5))
    return gs


def test_gate_blocks_fresh_container() -> None:
    """value 守卫(攻击 R1 回归测试):新容器 node_pos=(None, 'observation')
    (Field 缺省 source 即 observation)——门必须按 value 在场判定,否则
    开局/恢复局首次终结确认误放行且 candidate 无定义。"""
    gs = _gs_with_double_pair()
    assert report_node_advance(gs, trigger='settle_confirm').applied is False
    assert gs.node_pos.value is None, '零推进'
    assert gs.node_hist_pos is None
    assert gs.free_refresh_left.value is None, '门挡 = 不触效果尾段(零 Field 行)'


def test_first_anchor_establishes_and_grants() -> None:
    """v=None 首锚定行:任何读数经原语落账(observation 确认态)+ 效果尾段。"""
    gs = _gs_with_double_pair()
    token = observe_node_anchor(gs, (1, 1), trigger_screen='货币战争-备战',
                                actor=_ACTOR)
    assert token == 'first_anchor'
    assert gs.node_pos.value == (1, 1) and gs.node_pos.source == 'observation'
    assert gs.node_hist_pos == (1, 1)
    assert gs.free_refresh_left.value == 2, '首锚定即节点进入,尾段发放'


def test_gate_blocks_unconfirmed_logic() -> None:
    """source=logic 门挡:动作推进后未锚定前,任何第二次上报零推进——
    重复上报在结构上不可能(观察态门语义)。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (1, 2), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert gs.node_pos.value == (1, 3) and gs.node_pos.source == 'logic'
    balance_after_first = gs.free_refresh_left.value
    assert report_node_advance(gs, trigger='settle_confirm').applied is False
    assert gs.node_pos.value == (1, 3), '重复上报零推进'
    assert gs.free_refresh_left.value == balance_after_first, '门挡不触尾段'


def test_gate_passes_advances_exactly_one() -> None:
    """门放行:candidate = sequence_next(生效序位),推进恰一档。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (1, 2), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert gs.node_pos.value == (1, 3)
    assert gs.node_hist_pos == (1, 3)
    assert effective_node_pos(gs) == (1, 3)


def test_reanchor_unlocks_next_advance() -> None:
    """等值观察翻锚定:logic 态被同值观察确认后翻 observation,下一终结
    动作解锁——漏点自愈链的解锁半(重试确认可推进)。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (1, 2), trigger_screen='货币战争-备战', actor=_ACTOR)
    report_node_advance(gs, trigger='settle_confirm')
    assert gs.node_pos.source == 'logic'
    assert observe_node_anchor(gs, (1, 3), trigger_screen='货币战争-备战',
                               actor=_ACTOR) == 'reanchor'
    assert gs.node_pos.source == 'observation'
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert gs.node_pos.value == (1, 4)


def test_settle_confirm_wires_battle_grant_once() -> None:
    """T-30 同战共现条件发放接入调用(settle_confirm 分支,黑天鹅直登相邻):
    真推进恰好查一次——三将同战结算后 bench 增 1★流萤带实例号 + 锁记录
    落账;重复上报(观察态门挡)不重查不重发;再推进 done 短路不重发
    且黑天鹅占卜屋计数器计数不受发放影响(回归锁);supply_finish 推进
    不触发本检查(分支封闭集内仅 settle_confirm 接入调用)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        BenchSlot,
        BenchView,
        DeployedView,
        Unit,
    )

    def _ready_gs() -> GameState:
        gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        gs.observe(gs.active_env, '星核猎手契约', sig=_SIG_OBS)
        trio = [Unit(char_id=c, star=1)
                for c in ('刃', '卡芙卡', '银狼', '黑天鹅')]
        gs.observe(gs.deployed,
                   DeployedView(front_slots=trio + [None],
                                back_slots=[None] * 6), sig=_SIG_OBS)
        gs.observe(gs.bench,
                   BenchView(slots=[BenchSlot(kind='empty')] * 9,
                             capacity=9), sig=_SIG_OBS)
        observe_node_anchor(gs, (1, 5), trigger_screen='货币战争-备战',
                            actor=_ACTOR)
        return gs

    def _bench_chars(gs_: GameState) -> list[tuple[str, int, int | None]]:
        return [(s.unit.char_id, s.unit.star, s.unit.uid)
                for s in gs_.bench.value.slots
                if s is not None and s.kind == 'unit' and s.unit is not None]

    gs = _ready_gs()
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied and gs.node_pos.value == (1, 6), '真推进一档'
    assert _bench_chars(gs) == [('流萤', 1, 1)], '发放 1★流萤带实例号'
    assert gs.env_grants_done.value == \
        (('星核猎手契约', 'battle_co_presence'),), 'done 封账'
    assert gs.env_grant_deploy_locks.value == (('流萤', 1, (1, 8)),), \
        '锁记录 = (发放角色, uid, 解锁序位 = 生效序位 (1,6) 步进 2 步)'
    assert gs.screen_changes.fortune_battles == 1, '黑天鹅计数照走'
    # 重复上报:观察态门挡(结构性不重查),零重发
    assert report_node_advance(gs, trigger='settle_confirm').applied is False
    assert _bench_chars(gs) == [('流萤', 1, 1)], '不重发'
    assert gs.env_grant_uid_seq.value == 1, 'uid 不再发号'
    # 翻锚定后第二次真推进:done 短路零写,黑天鹅计数器继续不受影响
    observe_node_anchor(gs, (1, 6), trigger_screen='货币战争-备战',
                        actor=_ACTOR)
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert _bench_chars(gs) == [('流萤', 1, 1)], 'done 短路不重发'
    assert gs.env_grant_uid_seq.value == 1
    assert gs.screen_changes.fortune_battles == 2, '计数器不受发放影响'

    # supply_finish 推进不触发本检查(推进照走,零发放零 done)
    gs2 = _ready_gs()
    assert report_node_advance(gs2, trigger='supply_finish').applied
    assert gs2.node_pos.value == (1, 6)
    assert _bench_chars(gs2) == [], 'supply_finish 不触发'
    assert gs2.env_grants_done.value is None, '零 done'


def test_stale_reading_dropped() -> None:
    """R<v 倒退免疫:不写 + 现值保持(logic 或 observation 态同规)。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (1, 5), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert observe_node_anchor(gs, (1, 4), trigger_screen='货币战争-备战',
                               actor=_ACTOR) == 'stale_dropped'
    assert gs.node_pos.value == (1, 5), '倒退读数不落账'
    assert gs.node_hist_pos == (1, 5)


def test_repair_advance_ticks_ledger() -> None:
    """R>v 补推经原语(攻击 F2① 回归测试):漏上报自愈路径同样触发效果
    尾段——账本 advance_node 去重是序位相等判,补推不 tick 即跳档漏发。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (1, 2), trigger_screen='货币战争-备战', actor=_ACTOR)
    report_node_advance(gs, trigger='settle_confirm')   # → (1, 3)
    assert gs.free_refresh_left.value == 4   # 节点 (1,2) + (1,3) 各 +2
    assert observe_node_anchor(gs, (1, 5), trigger_screen='货币战争-备战',
                               actor=_ACTOR) == 'advance'
    assert effective_node_pos(gs) == (1, 5)
    assert gs.free_refresh_left.value == 6, \
        '补推节点 (1,5) 当帧拿到发放(漏 tick 即永久少一档)'


def test_cross_plane_advance() -> None:
    """跨位面推进(design §2.11 测试 2):P1 位面末 (1,9) 确认 → (2,1)
    (后继原语跨位面);跨位面字典序严格性 (1,10) < (2,1) 由锚定倒退
    免疫分支自然严格(修饰局形态同构,默认局锁本位)。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (1, 9), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert gs.node_pos.value == (2, 1) and gs.node_pos.source == 'logic'
    assert gs.node_hist_pos == (2, 1)
    assert effective_node_pos(gs) == (2, 1)


def test_out_of_domain_reading_dropped() -> None:
    """越域读数丢弃(design §2.11 测试 4 位面在表守卫):位面 4 无序列表
    (OCR 位面误读形态)→ 不写任何水位 + arbitrate 留证,返回
    out_of_domain_dropped(与 prep suppress 零写入/supply 响亮抛错语义
    等价的 kernel 侧显式处置;位面 3 行入表后表外防御 = ≥4)。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (1, 2), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert observe_node_anchor(gs, (4, 1), trigger_screen='货币战争-补给',
                               actor=_ACTOR) == 'out_of_domain_dropped'
    assert gs.node_pos.value == (1, 2), '越域读数不写水位'
    assert gs.node_hist_pos == (1, 2), '越域读数不推 hist'


def test_terminal_match_end_event_style() -> None:
    """终局事件式(design §2.11 测试 3):位面 3 末 boss (3,7) 结算确认 →
    sequence_next = None → applied=True reason='match_end' + 声明
    next_screen='';零写入(node_pos/node_hist_pos 保持锚定态)零效果
    tick(已登记效果余期不递减)。applied 语义扩展 = 终结动作落地事实。"""
    gs = _gs_with_double_pair()
    observe_node_anchor(gs, (3, 7), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert gs.free_refresh_left.value == 2, '锚定 (3,7) 当帧发放(对照基线)'
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied is True, 'applied = 终结动作落地事实(语义扩展)'
    assert out.reason == 'match_end'
    assert out.world_decl is not None
    assert out.world_decl.next_screen == ''
    assert out.world_decl.trigger == 'node_advance'
    assert gs.node_pos.value == (3, 7), '终局零写入'
    assert gs.node_hist_pos == (3, 7), '终局不推水位'
    assert gs.free_refresh_left.value == 2, '终局零效果 tick(余期不递减)'


# ================================================================ 场景走查测试

def _gs_with(test_context, monkeypatch, spec_name: str) -> GameState:
    """session 旁表容器挂 ctx.cw_match(op 上报口供给面)+ 指定效果已登记
    (发放断言活载体);返回容器与 gs_of_ctx 同源。"""
    session = cw4_session()
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    gs = game_state_of(session)
    gs.effects.register_strategy(STRATEGY_EFFECTS[spec_name],
                                 acquired_key=(1, 5))
    return gs


def test_fast_popup_advance_precedes_pick_and_prep_reanchor(
        test_context, monkeypatch,
) -> None:
    """快弹窗全型(landing §3.6 S2):结算确认**点击即上报**(去证据门,
    用户裁定 2026-09-21——点了就是上报,无弹窗锚探查)→ 推进先于弹窗
    选卡由因果序结构性成立(design §2.3,不依赖弹窗推断);选卡登记零
    推进(登记语义归拿卡上报侧,design §2.6);选卡后备战帧锚定等值
    reanchor 翻回观察态,下一终结动作解锁。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_settle_confirm import (
        CwOpSettleConfirm,
    )

    gs = _gs_with(test_context, monkeypatch, '双手狸开键盘！')
    observe_node_anchor(gs, (1, 1), trigger_screen='货币战争-备战', actor=_ACTOR)

    op = CwOpSettleConfirm(test_context)
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'screenshot', lambda: object())
    # 「继续挑战」点击机械半全桩命中(点击即上报,零证据探查)
    monkeypatch.setattr(
        op, 'round_by_find_and_click_area',
        lambda *a, **k: _Area(True))
    _run_node(test_context, op, op.confirm)

    assert gs.node_pos.value == (1, 2) and gs.node_pos.source == 'logic', (
        '确认点击时点即推进(快弹窗:推进先于弹窗选卡)')

    # 选卡登记(拿卡上报侧):零节点推进
    gs.effects.register_strategy(STRATEGY_EFFECTS['加油站'], acquired_key=(1, 6))
    assert gs.node_pos.value == (1, 2) and gs.node_pos.source == 'logic', (
        '选卡登记不推进节点(登记语义归拿卡侧,design §2.6)')

    # 选卡后备战帧锚定:等值 reanchor 翻观察态 → 下一终结动作解锁
    assert observe_node_anchor(gs, (1, 2), trigger_screen='货币战争-备战',
                               actor='CwScreenPrep') == 'reanchor'
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert effective_node_pos(gs) == (1, 3), 'reanchor 后下一确认可推进'


def test_boss_segment_click_advance_and_cross_plane(
        test_context, monkeypatch,
) -> None:
    """boss 段帧序列测试(landing §3.6 S6/E12/E13;去证据门重述 2026-09-21):

    - E12 奖励关结算确认**点击即推进** → boss 节点 (1,9);
    - 简报类型直定目标恒正确:无证据门 ⇒ 上报先于下一节点任何画面渲染
      恒成立 ⇒ hist 已推进至 boss 节点,简报直定不落错节点(不写奖励关
      (1,8))——原 bail 缝随证据等待机制退役结构性消失;
    - E13 boss 结算确认 → 后继原语自然跨位面((1,9) → (2,1),design
      §2.1),位面 2 首备战帧等值 reanchor 解锁下一确认。
    """
    gs = _gs_with(test_context, monkeypatch, '双手狸开键盘！')
    # 奖励关 (1,8) 已锚定;结算确认点击即推进 → boss 节点 (1,9)(E12)
    observe_node_anchor(gs, (1, 8), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert effective_node_pos(gs) == (1, 9)

    # 简报帧直定:hist 已在 (1,9)(logic),简报直定目标 = (1,9)(boss 节点)
    report_screen_boss_briefing_obs(gs, CwScreenBossBriefingObs(on_screen=True))
    _node = gs.node.value
    assert _node is not None and _node.kind == 'boss'
    assert (_node.plane, _node.round_num) == (1, 9), (
        '简报类型直定目标 = 现 hist(boss 节点),不落错奖励关节点')

    # E13:boss 结算确认 → (2,1)(后继原语自然跨位面)
    observe_node_anchor(gs, (1, 9), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert effective_node_pos(gs) == (2, 1)
    # 位面 2 首备战帧等值 reanchor → 下一确认解锁
    assert observe_node_anchor(
        gs, (2, 1), trigger_screen='货币战争-备战',
        actor='CwScreenPrep') == 'reanchor'
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert effective_node_pos(gs) == (2, 2)


def test_locked_resume_value_guard_self_heal(test_context, monkeypatch) -> None:
    """锁定臂门挡自愈(design §2.2/§2.3,landing §3.6 S9):锁定臂直出战
    无备战帧锚定(v=None)→ 首次结算确认被 **value 守卫**挡(攻击 R1:
    新容器缺省 source 即 observation,门必须按 value 在场判);战后备战
    帧观察锚定以绝对读数首锚定补齐(恢复局重建语义,R=局中任意节点)——
    键表示无 skew,后续终结动作正常推进。"""
    gs = _gs_with(test_context, monkeypatch, '双手狸开键盘！')

    # 锁定臂直出战:无任何锚定,首次结算确认被 value 守卫挡
    assert report_node_advance(gs, trigger='settle_confirm').applied is False
    assert gs.node_pos.value is None and gs.node_hist_pos is None, (
        'value 守卫挡首确认(零推进零 hist)')

    # 战后备战帧锚定:恢复局 mid-game 读数 (1,7) → 首锚定 + 尾段发放
    assert observe_node_anchor(gs, (1, 7), trigger_screen='货币战争-备战',
                               actor='CwScreenPrep') == 'first_anchor'
    assert gs.node_pos.value == (1, 7) and gs.node_pos.source == 'observation'
    assert gs.node_hist_pos == (1, 7)
    assert gs.free_refresh_left.value == 2, '首锚定当帧发放(无 skew)'

    # 自愈后流程续行:下一结算确认正常推进
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert effective_node_pos(gs) == (1, 8)


def test_settle_truth_gold_samples_conditional_grant(
        test_context, monkeypatch,
) -> None:
    """结算真值金采样(design §2.7-3):条件族(本金充裕,50/10/3)的
    每节点发放按 **结算真值金** 评估——结算链(apply_settlement_cover →
    settle_truth)先于「继续挑战」点击,推进时点采到的金 = 战后真值,
    比战前推算金(陈旧金)更准。时序测试:战前推算金低于阈值 → 首锚定
    零授予;结算真值 85 落账后确认推进 → 按真值授予 3 次。"""
    gs = _gs_with(test_context, monkeypatch, '本金充裕')

    # 战前推算金(旧路径快弹窗会采到的陈旧金):低于阈值
    gs.write_logic(gs.gold, 40, produced_by='TestBoardIncome',
                   sig=ChannelSig(family='logic_action',
                                  actor='TestBoardIncome', mode='compute'))
    observe_node_anchor(gs, (1, 2), trigger_screen='货币战争-备战', actor=_ACTOR)
    assert gs.gold.value == 40
    assert gs.free_refresh_left.value is None, (
        '战前陈旧金 40 ≤ 阈值 50:首锚定零条件授予')

    # 结算链先于确认点击:结算屏真值金 85 无条件收尾(settle_truth)
    apply_settlement_cover(gs, hp_after=80, streak_after=1, gold=85)
    assert gs.gold.value == 85

    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert effective_node_pos(gs) == (1, 3)
    assert gs.free_refresh_left.value == 3, (
        '推进时点按结算真值 85 评估:超出 35 → 每 10 金 1 次,封顶 3'
        '(采到陈旧金 40 则为 0——时序测试)')


def _prep_heavy_harness(test_context, monkeypatch, session):
    """CwScreenPrep heavy 观察跑壳(锚定写端接入调用测试共用):observe_full 桩
    按 ``receipt['r']`` 回传读数回执(None = 缺位),其余观察面全桩零;
    返回 (gs, op, receipt)。本缝静默丢失时生产 value 门挡全程卡死,故
    直测 wiring 面(与补给屏锚定对称,先例 = test_supply)。"""
    from sr_od.application.currency_war.obs import cw_observe_full as ofm
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep as pp,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        CwScreenPrep,
    )

    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    gs = game_state_of(session)
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
    return gs, op, _receipt


def test_deposit_return_conditional_grant_and_roll(
        test_context, monkeypatch,
) -> None:
    """存款回报条件发放+滚位(T-92 设计 §4 锁 2,核心;全链 =
    observe/report 原语经 advance_node_effective 尾段桥+滚位同闸):
    - 未花费进边界 tick:桥 +2 且滚位判等跳写(False 保持,零滚位行);
    - 节点内买牌上报置 True → 下一边界:True 不授予但滚回 False;
    - 再一未花费边界:+2 照常,连续未花费 journal 零滚位新行。"""
    rows: list[dict] = []
    monkeypatch.setattr(gs_mod, '_STATE_JOURNAL_SINK', rows.append)
    monkeypatch.setattr(gs_mod, '_RUN_ID_PROVIDER', lambda: 't92-l2')
    from test.sr_od.application.currency_war._cw_helpers import (
        cw4_card as _card,
    )

    from sr_od.application.currency_war.kernel.cw_action_report.buy_card import (
        report_action_buy_card_param,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionBuyCardParam,
    )

    gs = _gs_with(test_context, monkeypatch, '存款回报')
    assert gs.prev_node_spent.value is False, '开局种子 False(前置)'
    observe_node_anchor(gs, (1, 2), trigger_screen='货币战争-备战',
                        actor=_ACTOR)
    assert gs.free_refresh_left.value == 2, '未花费首边界 +2(桥条件腿)'
    assert gs.prev_node_spent.value is False, '滚位判等跳写(False 保持)'

    # 节点 (1,2) 内买牌上报(置位通道 1)
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('希儿', cost=3)),
        _logic_sig('CwScreenShop'))
    assert out.applied, '买牌上报成功'
    assert gs.prev_node_spent.value is True, '花费事件置位'

    # 推进 (1,3):True 不授予,评估毕滚位复位 False
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert effective_node_pos(gs) == (1, 3)
    assert gs.free_refresh_left.value == 2, '上节点已花费 → 不授予'
    assert gs.prev_node_spent.value is False, '评估毕滚位复位'
    assert gs.prev_node_spent.evidence == 'prev_node_spent_roll@1-3'

    # 再一未花费边界 (1,4):+2 照常,滚位判等零新行
    observe_node_anchor(gs, (1, 3), trigger_screen='货币战争-备战',
                        actor=_ACTOR)   # 等值 reanchor 解锁下一推进
    assert report_node_advance(gs, trigger='settle_confirm').applied
    assert effective_node_pos(gs) == (1, 4)
    assert gs.free_refresh_left.value == 4, '未花费边界再 +2'
    assert gs.prev_node_spent.value is False, '判等跳写(False 保持)'

    roll_rows = [r for r in rows if r['field'] == 'prev_node_spent'
                 and r['sig']['actor'] == 'EffectLedgerBridge']
    assert len(roll_rows) == 1, \
        '连续未花费边界判等跳写:滚位行恰 1(仅 1-3;1-2/1-4 零行)'


def test_prep_heavy_receipt_anchors_node(test_context, monkeypatch) -> None:
    """备战帧锚定接入调用测试(design §2.4 写端 1,攻击 F1 定论):CwScreenPrep
    heavy 观察回执携带本帧 plane/round → ``observe_node_anchor``(唯一
    生产锚定缝,cw_screen_prep.py::_observe heavy 段)——首帧 first_anchor
    建账含尾段发放、后续读数 advance/reanchor 落账、回执缺位跳过(禁猜)。"""
    session = cw4_session()
    gs, op, _receipt = _prep_heavy_harness(test_context, monkeypatch, session)
    gs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                 acquired_key=(1, 5))

    def _run_observe() -> None:
        _run_node(test_context, op,
                  lambda: op._observe(True, screen=object()))

    # 回执缺位(读数未读)→ 跳过锚定(禁猜,best-effort)
    _receipt['r'] = None
    _run_observe()
    assert gs.node_pos.value is None, '回执缺位零锚定(禁猜)'

    # 开局首帧(1-1)→ first_anchor 建账 + 尾段发放
    _receipt['r'] = (1, 1)
    _run_observe()
    assert gs.node_pos.value == (1, 1) and gs.node_pos.source == 'observation'
    assert gs.node_hist_pos == (1, 1)
    assert gs.free_refresh_left.value == 2, '首锚定当帧发放'

    # 下一节点读数(1-2)→ advance 补推落账(观察采新即确认态)
    _receipt['r'] = (1, 2)
    _run_observe()
    assert gs.node_pos.value == (1, 2) and gs.node_pos.source == 'observation'

    # 同值再读 → reanchor(等值确认,源态保持 observation)
    _receipt['r'] = (1, 2)
    _run_observe()
    assert gs.node_pos.value == (1, 2) and gs.node_pos.source == 'observation'


# ================================================================ 环境修饰序位表

def _modified() -> dict[int, tuple[str, ...]]:
    return resolve_plane_node_seqs('人身意外险')


def _gs_with_field(
        value: dict[int, tuple[str, ...]] | None) -> GameState:
    """带场字段的裸容器(写通道 = 生产写口 write_logic;None = 未注册态)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if value is not None:
        gs.write_logic(gs.node_seq_by_plane, value,
                       produced_by='TestSeqEnv', evidence='node_seq:env',
                       sig=_logic_sig())
    return gs


# ------------------------------------------------------------ 修饰规则

def test_lock1_resolve_default_env_returns_default_tables() -> None:
    """表外环境(含空名)原样返回默认表;默认表元组对象不被复制也不
    被原地改(对象同一性)。"""
    for name in ('头彩', '火药味', '过剩经费', ''):
        out = resolve_plane_node_seqs(name)
        assert out == {1: P1_NODE_SEQUENCE, 2: P2_NODE_SEQUENCE,
                       3: P3_NODE_SEQUENCE}
        assert out[1] is P1_NODE_SEQUENCE and out[2] is P2_NODE_SEQUENCE \
            and out[3] is P3_NODE_SEQUENCE
    assert PLANE_NODE_TABLES == {1: P1_NODE_SEQUENCE, 2: P2_NODE_SEQUENCE,
                                 3: P3_NODE_SEQUENCE}


def test_lock1_resolve_modified_inserts_supply_before_each_boss() -> None:
    """人身意外险:P1 r9 supply + r10 boss、P2 r7 supply + r8 boss、
    P3 r7 supply + r8 boss(每个 boss 位前各一;P3 行入表后插入自动
    适用,统一注册表迁移护航)。"""
    mod = _modified()
    assert set(mod) == {1, 2, 3}
    assert mod[1][-2:] == ('supply', 'boss')
    assert mod[1][:-2] == P1_NODE_SEQUENCE[:-1]
    assert len(mod[1]) == 10
    assert mod[2][-2:] == ('supply', 'boss')
    assert mod[2][:-2] == P2_NODE_SEQUENCE[:-1]
    assert len(mod[2]) == 8
    assert mod[3][-2:] == ('supply', 'boss')
    assert mod[3][:-2] == P3_NODE_SEQUENCE[:-1]
    assert len(mod[3]) == 8


# (原「正反解互逆」测试整体退役:kernel 正解 node_ordinal_of 与反解
#  node_pos_of 已随键化删除,无可互逆对象(设计披露 5);后继语义测试 =
#  test_node_pos_primitive.py 的 sequence_next 四态契约 + 本文件
#  键化消费面各测试。)

# ------------------------------------------------------------ 场字段生命周期

def test_lock3_write_leg_whitelist_full_modified_table() -> None:
    """环境注册(白名单内)→ 字段落修饰表,evidence='node_seq:env',
    通道 = logic(确定性可计算);字段恒全量无半态。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        gain_invest_env,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gain_invest_env(gs, None, '人身意外险', rand=False, sig=_logic_sig())
    assert gs.node_seq_by_plane.value == _modified()
    assert gs.node_seq_by_plane.source == 'logic'
    assert gs.node_seq_by_plane.evidence == 'node_seq:env'


def test_lock3_write_leg_non_whitelist_full_default_table() -> None:
    """环境注册(白名单外)→ 字段落默认表(注册后恒全量);OCR 形变名
    经归一后命中。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        gain_invest_env,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gain_invest_env(gs, None, '火药味', rand=False, sig=_logic_sig())
    assert gs.node_seq_by_plane.value == dict(PLANE_NODE_TABLES)


def test_lock3_none_field_consumers_fall_back_to_default() -> None:
    """字段 None(未注册)→ 消费方回退默认表;裸容器字段缺省 None。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert gs.node_seq_by_plane.value is None
    assert node_sequence_of(1, gs.node_seq_by_plane.value) \
        == P1_NODE_SEQUENCE
    assert node_round_cap(2, gs.node_seq_by_plane.value) == 7


def test_lock3_snapshot_restore_carries_field() -> None:
    """快照恢复随容器现值携带(键 int 化 + 值 tuple 化重建)。"""
    gs = _gs_with_field(_modified())
    snap = gs.full_state_snapshot()
    gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs2, snap)
    assert gs2.node_seq_by_plane.value == _modified()
    assert all(isinstance(k, int) for k in gs2.node_seq_by_plane.value)
    assert all(isinstance(v, tuple) for v in gs2.node_seq_by_plane.value.values())


# ------------------------------------------------------------ next_screen 推导

def test_lock4_next_screen_modified_regime() -> None:
    """修饰制推进声明:P1 r8→r9 = 补给、r9→r10 = boss 简报、跨位面 =
    位面过渡、P2 r7→r8 = boss 简报、P2 r8 → 位面过渡(P3 在表)、
    P3 r7→r8 = boss 简报(插入尾槽)、P3 r8 后无后继 = 局终声明事件式。
    2026-10-29 流程模型对齐口径:node_advance 稳态落点 = 新节点窗的
    呈现屏(弹窗型节点 = 备战底层上的节点弹窗模态,battle/reward =
    开商店档,位面首 = 位面过渡),修饰局插入位随表自动适用。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        SCREEN_BOSS_BRIEFING,
    )
    gs = _gs_with_field(_modified())
    anchor = '货币战争-备战'
    observe_node_anchor(gs, (1, 8), trigger_screen=anchor, actor='TestSeqEnv')
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied and out.world_decl.next_screen == '货币战争-补给'
    observe_node_anchor(gs, (1, 9), trigger_screen=anchor, actor='TestSeqEnv')
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied and out.world_decl.next_screen == SCREEN_BOSS_BRIEFING
    observe_node_anchor(gs, (1, 10), trigger_screen=anchor, actor='TestSeqEnv')
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied \
        and out.world_decl.next_screen == '货币战争-位面过渡'
    observe_node_anchor(gs, (2, 7), trigger_screen=anchor, actor='TestSeqEnv')
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied and out.world_decl.next_screen == SCREEN_BOSS_BRIEFING
    observe_node_anchor(gs, (2, 8), trigger_screen=anchor, actor='TestSeqEnv')
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied \
        and out.world_decl.next_screen == '货币战争-位面过渡', \
        'P2 末跨入 P3(位面 3 在表)'
    observe_node_anchor(gs, (3, 7), trigger_screen=anchor, actor='TestSeqEnv')
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied and out.world_decl.next_screen == SCREEN_BOSS_BRIEFING
    observe_node_anchor(gs, (3, 8), trigger_screen=anchor, actor='TestSeqEnv')
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied and out.world_decl.next_screen == '', \
        'P3 末无后继 → 局终声明事件式(match_end,超位面 3 = 胜利终局)'


# ------------------------------------------------------------ 观察读链两位数

def test_lock6_parse_and_cap_two_digit_round() -> None:
    """「1-10」形:修饰局(round_caps=修饰表)整读 (1,10);默认局
    (caps=None/默认表)P1 仍拒(cap 9,现役口径回归)。「A8」类错源仍拒;
    位面化上限外仍拒;(Lv.12-3)旧误读窗被两位数正则顺带拒掉。"""
    assert parse_phase_round_text('备战阶段 1-10') == (1, 10)
    assert phase_round_in_range((1, 10), _modified()) is True
    assert phase_round_in_range((1, 10), dict(PLANE_NODE_TABLES)) is False
    assert phase_round_in_range((1, 10), None) is False
    assert parse_phase_round_text('A8') is None
    assert parse_phase_round_text('A8', digit_fallback=True) == (8, 8)
    assert phase_round_in_range((8, 8), _modified()) is False
    assert phase_round_in_range((1, 11), _modified()) is False, 'cap 10'
    assert phase_round_in_range((2, 9), _modified()) is False, 'cap 8'
    assert phase_round_in_range((1, 13), _modified()) is False
    assert parse_phase_round_text('Lv.12-3') == (12, 3)
    assert phase_round_in_range((12, 3), None) is False
    assert parse_phase_round_text('备战阶段 1-3') == (1, 3)
    assert phase_round_in_range((1, 3), None) is True
    # read_phase_round 主链不带数字回退(w891 停用裁定共享实现关该支)
    assert parse_phase_round_text('Lv.3') is None
    assert parse_phase_round_text('Lv.3', digit_fallback=True) == (3, 3)


def test_lock6_p3_cap_and_out_of_domain_margin() -> None:
    """round 读数上限三态:修饰表 P3 = 8(插入随动)、默认表 P3 = 7
    (入表口径);真表外位面(≥4)缺键两态均落 12 余量(数值单一源 =
    node_round_cap)。"""
    assert node_round_cap(3, _modified()) == 8
    assert node_round_cap(3, None) == 7
    assert node_round_cap(4, _modified()) == 12
    assert node_round_cap(4, None) == 12


def test_lock6_recognizer_tool_state_shares_parsing(
        test_context, monkeypatch) -> None:
    """battle_prep_recognizer 与正解共享解析(同正则同值域);工具态
    round_caps 恒 None → cap 回退默认长度 P1=9:「1-10」不作放行要求
    (工具面显示 r9 口径,修饰局真值由场字段/台账承载)。"""
    from sr_od.application.currency_war.obs.recognizers import (
        battle_prep_recognizer as rec,
    )

    _blob = {'text': '备战阶段 1-3'}

    def _fake_ocr(ctx, screen, rect):
        return [SimpleNamespace(data=_blob['text'])]

    monkeypatch.setattr(rec, '_ocr', _fake_ocr)
    assert rec._read_phase_round_pure(test_context, object()) == (1, 3)
    _blob['text'] = '备战阶段 1-10'
    assert rec._read_phase_round_pure(test_context, object()) is None, \
        '工具态 cap 回退默认 9,r10 拒(披露:1-10 断言对 recognizer 不作要求)'
    _blob['text'] = '第2位面'
    assert rec._read_phase_round_pure(test_context, object()) == (2, 2)


def test_lock6_recorder_and_funnel_wiring_passes_caps(
        monkeypatch) -> None:
    """cw_match_recorder 语料采集与 read_game_state 漏斗接入调用:
    round_caps 透传场字段现值(实时态);局外无容器 = None 回退。"""
    from sr_od.application.currency_war.telemetry import cw_match_recorder

    captured: dict = {}

    def _fake_read(ctx, img, round_caps=None):
        captured['caps'] = round_caps
        return 1, 10

    monkeypatch.setattr(cw_match_recorder, 'read_phase_round', _fake_read)
    # 实时态:session 旁表单例(game_state_from_ctx 取口 = cw_match.session)
    session = cw4_session()
    gs = game_state_of(session)
    gs.write_logic(gs.node_seq_by_plane, _modified(),
                   produced_by='TestSeqEnv', evidence='node_seq:env',
                   sig=_logic_sig())
    ctx = SimpleNamespace(cw_match=SimpleNamespace(session=session))
    cw_match_recorder.extract_frame(ctx, object(), object())
    assert captured['caps'] == _modified()
    # 局外:无 match → caps None(回退默认口径,设计披露 10②)
    cw_match_recorder.extract_frame(SimpleNamespace(), object(), object())
    assert captured['caps'] is None


# ------------------------------------------------------------ 白名单归属校验

def test_lock7_registry_ownership_orphan_key_raises(monkeypatch) -> None:
    """注册表键改名漂移(注册表无此环境)→ 校验炸(键 ⊆ INVESTMENT_ENVS,
    防版本改名静默失联);现役键校验通过。"""
    cw_investments._validate_env_node_seq()   # 现役键通过
    monkeypatch.setattr(ns, 'ENV_NODE_REWRITE_RULES',
                        {'不存在的环境': (('insert_supply_before_boss',),)})
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_env_node_seq()


# ------------------------------------------------------------ 键化消费面

def _shop_gs_with_target(mod_target_pos: tuple[int, int],
                         mirror: NodeKey | None) -> GameState:
    """修饰局商店帧容器:生效键 = 修饰制目标序位(hist/ord 同值),镜像按参。"""
    gs = _gs_with_field(_modified())
    observe_node_anchor(gs, mod_target_pos, trigger_screen='货币战争-备战',
                        actor='TestSeqEnv')
    if mirror is not None:
        gs.observe(gs.node, mirror, evidence='t', sig=_SIG_OBS)
    return gs


def test_lock9_shop_chain_query_key_modified_not_9shift(monkeypatch) -> None:
    """①商店查链:修饰局 P2 r2 店开帧 → 链查询键 = (2,2),非 9 制解码的
    (2,3)(漏改则恒查后一节点,类型查链静默失效);目标即键,直定无反解
    (旧 _node_key_for_ord 反解测试随表示退役)。"""
    gs = _shop_gs_with_target((2, 2), NodeKey(plane=2, round_num=2, kind=''))
    queried: list[tuple[int, int]] = []

    def _fake_chain(g, plane, round_num):
        queried.append((plane, round_num))
        from sr_od.application.currency_war.kernel.cw_game_state import (
            ChainQuery,
        )
        return ChainQuery(token=None)   # 链缺 = 零写,只校验查询键

    monkeypatch.setattr(gs_mod, 'chain_node_type', _fake_chain)
    gs.observe_screen_context('货币战争-备战-开商店', sig=_SIG_OBS)
    assert queried == [(2, 2)]


def test_lock9_mirror_sequence_reads_field(monkeypatch) -> None:
    """③镜像序:镜像 (2,3)/生效键 (2,2) 的修饰局 →
    `_shop_panel_type_target` 取 max = (2,3)(镜像领先保护维持);
    镜像即键不依赖场字段(字段 None 反差镜下仍 (2,3)——9 制退化值
    随表示消亡)。"""
    gs = _shop_gs_with_target((2, 2), NodeKey(plane=2, round_num=3, kind='battle'))
    assert _obs_node_pos(gs) == (2, 3)
    assert _shop_panel_type_target(gs) == (2, 3)
    # 字段 None:镜像键派生不依赖场字段
    gs9 = _shop_gs_with_target((2, 2), NodeKey(plane=2, round_num=3,
                                               kind='battle'))
    gs9.write_logic(gs9.node_seq_by_plane, None, produced_by='TestSeqEnv',
                    evidence='t:none', sig=_logic_sig())
    assert _obs_node_pos(gs9) == (2, 3)


def test_lock9_direct_write_regression_immunity_uses_field() -> None:
    """②直定倒退免疫:镜像 (2,3) 领先、直定目标 (2,2) → 镜像键 (2,3) >
    (2,2) 丢弃留证不回写;直定目标 (2,3) 照常落 (2,3) 键。"""
    gs = _shop_gs_with_target((2, 2), NodeKey(plane=2, round_num=3,
                                              kind='battle'))
    seq = gs.write_seq
    _write_derived_node_type(gs, 'boss', target_pos=(2, 2), actor='TestSeqEnv',
                             trigger_screen='货币战争-备战-开商店',
                             seq=seq + 1)
    assert gs.node.value.round_num == 3, '倒退丢弃:镜像节点不被回写'
    # 同帧不落直定(node 镜像未被改写;丢弃走 obs_event 留证)
    _write_derived_node_type(gs, 'boss', target_pos=(2, 3), actor='TestSeqEnv',
                             trigger_screen='货币战争-备战-开商店',
                             seq=seq + 2)
    assert (gs.node.value.plane, gs.node.value.round_num, gs.node.value.kind) \
        == (2, 3, 'boss'), '目标 = (2,3),直定落同键'


def test_lock9_prep_anchor_write_end_passes_field(
        test_context, monkeypatch) -> None:
    """④live 锚定写端 1(CwScreenPrep 备战帧,P2 战斗节点唯一节点键
    观察写端):修饰局 (2,1) 回执 → 锚定 = (2,1) 序位(键直传,无坐标
    换算——9 制影子轨道病理随表示消亡)。"""
    session = cw4_session()
    gs, op, _receipt = _prep_heavy_harness(test_context, monkeypatch, session)
    gs.write_logic(gs.node_seq_by_plane, _modified(),
                   produced_by='TestSeqEnv', evidence='node_seq:env',
                   sig=_logic_sig())
    _receipt['r'] = (2, 1)
    _run_node(test_context, op, lambda: op._observe(True, screen=object()))
    assert gs.node_pos.value == (2, 1), \
        '修饰局 (2,1) 锚定 = 序位键直传'
    assert gs.node_pos.source == 'observation'


def test_lock9_supply_bar_write_end_passes_field(test_context) -> None:
    """④live 锚定写端 2(CwScreenSupplyNode 节点条):修饰局「2-7」读数
    → (2,7) 序位键;「2-8」随 cap 8 放行 = (2,8);场字段缺位反差镜 =
    cap 7:读数仍 (2,7)(键表示下两态同值)、「2-8」拒(cap 不放宽)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
        CwScreenSupplyNode,
    )

    def _make(ctx_gs, text: str):
        def _map(**kw):
            return {text: SimpleNamespace(
                max=SimpleNamespace(center=SimpleNamespace(x=1, y=1)))}
        ctx = SimpleNamespace(
            screen_loader=SimpleNamespace(get_area=lambda s, a: SimpleNamespace(
                pc_rect=SimpleNamespace(x1=10, y1=10, x2=200, y2=40))),
            ocr_service=SimpleNamespace(get_ocr_result_map=_map),
            cw_match=SimpleNamespace(gs=ctx_gs),
        )
        op = CwScreenSupplyNode.__new__(CwScreenSupplyNode)
        op.ctx = ctx
        return op

    mod = _modified()
    op = _make(_gs_with_field(mod), '备战阶段 2-7')
    assert op._read_node_bar(object()) == (2, 7), '修饰制 (2,7) 序位键'
    op = _make(_gs_with_field(mod), '备战阶段 2-8')
    assert op._read_node_bar(object()) == (2, 8), 'cap 随场字段放宽到 8'

    # 反差镜:场字段缺位(未注册)→ cap 7:「2-7」读数仍 (2,7)、「2-8」拒
    op9 = _make(_gs_with_field(None), '备战阶段 2-7')
    assert op9._read_node_bar(object()) == (2, 7)
    op9 = _make(_gs_with_field(None), '备战阶段 2-8')
    assert op9._read_node_bar(object()) is None


# ------------------------------------------------------------ acquired_key 同坐标系

def test_lock10_acquired_key_same_coordinate_system() -> None:
    """登记时点快照与推进入账同坐标系:修饰局 (2,2) 登记「接下来 N 节点」
    → 快照 = (2,2) 序位元组;登记节点当拍不递减,推进至 (2,3) 起递减。"""
    session = cw4_session()
    gs = game_state_of(session)
    gs.write_logic(gs.node_seq_by_plane, _modified(),
                   produced_by='TestSeqEnv', evidence='node_seq:env',
                   sig=_logic_sig())
    gs.observe(gs.node, NodeKey(plane=2, round_num=2, kind='battle'),
               evidence='t', sig=_SIG_OBS)
    acquired = _portal_acquired_key(gs, session)
    assert acquired == (2, 2), '登记快照 = (2,2) 序位元组'
    gs.effects.register_strategy(STRATEGY_EFFECTS['躺平'], acquired)
    advanced, expired = gs.effects.advance_node((2, 2))
    assert advanced and not expired
    entry = next(e for e in gs.effects.entries if e.spec.name == '躺平')
    assert entry.remaining_nodes == 3, '登记节点当拍不递减'
    advanced, expired = gs.effects.advance_node((2, 3))
    assert advanced and not expired
    assert entry.remaining_nodes == 2, '推进至 (2,3) 起递减'


# ------------------------------------------------------------ 结算读数与单调门

def test_lock11_parse_settlement_round_two_digit_and_noise() -> None:
    """结算屏读数:「1-10」→ (1,10)(修饰局 caps);caps=None 回退默认
    长度拒;「11-6」粘连噪声仍拒(lookaround 保留);值域外 (1,13) 拒。"""
    mod = _modified()
    assert parse_settlement_round(['挑战结束', '1-10', '战斗'], mod) == (1, 10)
    assert parse_settlement_round(['挑战结束', '1-10', '战斗'], None) is None
    assert parse_settlement_round(['挑战结束', '1-6', '战斗'], None) == (1, 6)
    assert parse_settlement_round(['挑战结束', '11-6', '战斗'], mod) is None
    assert parse_settlement_round(['挑战结束', '1-13', '战斗'], mod) is None
    assert parse_settlement_round(['挑战结束', '13-2', '战斗'], mod) is None


def _battle_wait_op(test_context, monkeypatch, last_known: tuple[int, int],
                    screen_round: tuple[int, int] | None,
                    captured: dict, outcome=None):
    """battle_wait 裸实例 + 全桩面(先例 = test_env_grants):
    last_known = read_phase_round 桩值;screen_round = parse_settlement_round
    桩值;captured 收集 read_round_outcome/apply_settlement_cover 入参。"""
    from sr_od.application.currency_war.kernel.cw_performance import (
        RoundOutcome,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait as bw,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait import (
        CwScreenBattleWait,
        SettlementState,
    )

    session = cw4_session()
    st = SettlementState(battle_ts=1234.0, run_start_ts=time.monotonic(),
                         is_new_match=False)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    monkeypatch.setattr(test_context, 'ocr_service',
                        SimpleNamespace(get_ocr_result_list=lambda **k: []),
                        raising=False)
    op = CwScreenBattleWait.__new__(CwScreenBattleWait)
    op.ctx = test_context
    op._st = st
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(False))
    monkeypatch.setattr(bw, 'read_phase_round',
                        lambda ctx, scr, round_caps=None: last_known)
    monkeypatch.setattr(bw, 'parse_settlement_round',
                        lambda texts, round_caps=None: screen_round)
    if outcome is None:
        outcome = RoundOutcome(round_num=1, plane=1, node_type='普通战斗',
                               comp_tag='c', hp_after=3, hp_confidence=1.0,
                               killed=False)

    queue = [outcome]

    def _fake_outcome(ctx, scr, **k):
        captured['outcome_plane'] = k.get('plane')
        captured['outcome_round'] = k.get('round_num')
        captured['outcome_killed'] = getattr(
            queue[0], 'killed', None) if queue else None
        return queue.pop(0)

    monkeypatch.setattr(bw, 'read_round_outcome', _fake_outcome)

    real_cover = gs_mod.apply_settlement_cover

    def _fake_cover(gs, **k):
        captured['cover_killed'] = k.get('killed')
        return real_cover(gs, **k)

    monkeypatch.setattr(gs_mod, 'apply_settlement_cover', _fake_cover)
    return op


def test_lock11_monotonic_gate_tuple_compare(
        test_context, monkeypatch) -> None:
    """结算单调门元组比较:(1,10) 后遇 (2,1) 结算屏被采(前进,塌缩
    消除);(2,1) 后遇陈旧 (1,10) 被拒(防修饰局重放残留);同轮重录
    (2,1)==(2,1) 照常接受。"""
    # 采:last-known (1,10) + 结算屏 (2,1) → 行落 (2,1)
    captured: dict = {}
    op = _battle_wait_op(test_context, monkeypatch, (1, 10), (2, 1), captured)
    op._record_round_outcome(object())
    assert (captured['outcome_plane'], captured['outcome_round']) == (2, 1)

    # 拒:last-known (2,1) + 陈旧 (1,10) → 保 last-known
    captured = {}
    op = _battle_wait_op(test_context, monkeypatch, (2, 1), (1, 10), captured)
    op._record_round_outcome(object())
    assert (captured['outcome_plane'], captured['outcome_round']) == (2, 1), \
        '陈旧 (1,10) < (2,1) 字典序拒(9 制下同为 10 会被平局放行)'

    # 同轮重录:(2,1) == (2,1) → 接受
    captured = {}
    op = _battle_wait_op(test_context, monkeypatch, (2, 1), (2, 1), captured)
    op._record_round_outcome(object())
    assert (captured['outcome_plane'], captured['outcome_round']) == (2, 1)


def test_lock11_killed_hp_fallback_path_gone(
        test_context, monkeypatch) -> None:
    """killed-hp 兜底门删除:两主路径(progress 符号/killed 文本)同失
    (killed=None ∧ progress=None)→ killed 保持 None 观察收尾,无 HP
    推断路径(旧门会按 hp 对比产出 killed)。"""
    from sr_od.application.currency_war.kernel.cw_performance import (
        RoundOutcome,
    )
    session = cw4_session()
    gs = game_state_of(session)
    gs.observe(gs.hp, 50, evidence='t', sig=_SIG_OBS)   # 旧门的前置真值源
    captured: dict = {}
    outcome = RoundOutcome(round_num=1, plane=1, node_type='普通战斗',
                           comp_tag='c', hp_after=60, hp_confidence=1.0,
                           killed=None, progress_delta=None)
    op = _battle_wait_op(test_context, monkeypatch, (1, 1), None, captured,
                         outcome=outcome)
    op._record_round_outcome(object())
    assert captured.get('cover_killed') is None, \
        'HP 推断路径消亡:killed 诚实缺位(旧门会产出 True/False)'


# ------------------------------------------------------------ sim 状态副本里的值

_DEF_STEPS = 400


def _start_game(env_present: bool, seed: int = 7):
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        SimBackend,
        install_backend,
    )
    from sr_od.application.currency_war.sim.cw_sim_run_config import (
        RunConfig,
    )
    cfg = RunConfig(selected_difficulty='A8', enemy_difficulty=108,
                    env_present=env_present)
    b = SimBackend(seed=seed, cfg=cfg)
    install_backend(b)
    return b


def _drive_step(b, rng_seed: int) -> None:
    """单步驱动(backend 直驱,先例 = test_sim_backend._drive_step;
    按呈现屏分派到对应真实写端,18 动作全量单轨)。"""

    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_megastar_param,
        report_action_pick_planner_param,
        report_action_pick_supply_param,
    )
    from sr_od.application.currency_war.kernel.cw_action_report.close_shop import (
        report_action_close_shop_param,
    )
    from sr_od.application.currency_war.kernel.cw_game_state import (
        report_node_advance,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionCloseShopParam,
    )
    from sr_od.application.currency_war.sim import cw_sim_ports
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        SCREEN_ENCOUNTER,
        SCREEN_INVEST_STRATEGY,
        SCREEN_PREP,
        SCREEN_SETTLE,
        SCREEN_SHOP,
        SCREEN_SUPPLY,
        stream_rng,
    )

    screen = b.screen_identity()
    gs = b.gs
    if screen == SCREEN_SUPPLY:
        opts = gs.supply.value.options
        gs.write_logic(gs.chosen_supply,
                       ('', (opts[0].equip, *opts[0].extra_equips)),
                       produced_by='Test', evidence='t:chosen',
                       sig=_logic_sig('Test'))
        out = report_action_pick_supply_param(
            gs, SimpleNamespace(idx=0, char_name='', norm_item=opts[0].equip),
            _logic_sig('Test'))
        cw_sim_ports.declare_world(out.world_decl)
        # 2026-10-29 流程模型对齐:补给确认零推进(选完关模态回备战自动
        # 弹店),节点推进归出战动作(start_battle 对 supply 走 supply_finish)。
    elif screen == SCREEN_SHOP:
        out = report_action_close_shop_param(gs, CwActionCloseShopParam(),
                                             _logic_sig('Test'))
        assert out.applied
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_INVEST_STRATEGY:
        opts = gs.invest_strategy_opts.value
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_pick_invest_strategy_param,
        )
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name=opts[0]), _logic_sig('Test'),
            rng=stream_rng(rng_seed, 'M11/pick/part'),
            session=SimpleNamespace())
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_SETTLE:
        out = report_node_advance(gs, trigger='settle_confirm')
        assert out.applied, out.reason
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == '货币战争-位面过渡':
        b._handle_click_source('货币战争-位面过渡', '区域-空白点击')
    elif screen == '货币战争-BOSS简报':
        b._handle_click_source('货币战争-BOSS简报', '区域-空白点击')
    elif screen == SCREEN_ENCOUNTER:
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_pick_encounter_param,
        )
        out = report_action_pick_encounter_param(
            gs, SimpleNamespace(idx=0), _logic_sig('Test'))
        assert out.applied
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == '货币战争-盛会之星':
        out = report_action_pick_megastar_param(gs, SimpleNamespace(),
                                                _logic_sig('Test'))
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == '货币战争-银狼升星':
        out = report_action_pick_planner_param(gs, SimpleNamespace(),
                                               _logic_sig('Test'))
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_PREP:
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_start_battle_param,
        )
        out = report_action_start_battle_param(gs, SimpleNamespace(),
                                               _logic_sig('Test'))
        cw_sim_ports.declare_world(out.world_decl)
    else:
        raise AssertionError(f'未知呈现屏 {screen}')


def test_lock5_sim_modified_game_full_chain(monkeypatch) -> None:
    """修饰局 sim 全链:选人身意外险 → 场字段落修饰表;P1 r9 呈现补给屏
    (M18 选项)+ 收入 supply 分支(连胜不动);r10 boss;P2 r7/r8 同构;
    P3 r7 插入补给自动适用,走完 P3 r8 = 胜利终局(run_complete 披露,
    修饰局共 25 节点);全程零 DECL_SCREEN_DRIFT。seed 24 = 修饰局走满
    锚(探针实测:唯一前 80 号内达 (3,8) 胜利终局的种子;P3 插入使
    boss 挪至 r8,结算流键随轮次变化,与默认局存活集不同)。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_invest_env_param,
    )
    from sr_od.application.currency_war.sim import cw_sim_ports
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        DECL_SCREEN_DRIFT,
        DISCLOSURE_RUN_COMPLETE,
        SCREEN_BOSS_BRIEFING,
        SCREEN_BRIEFING,
        SCREEN_INVEST_ENV,
        SCREEN_SUPPLY,
        uninstall_backend,
    )

    b = _start_game(env_present=True, seed=24)
    try:
        assert b.screen_identity() == SCREEN_BRIEFING
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        assert b.screen_identity() == SCREEN_INVEST_ENV
        # 定向候选(测试种子,同写入口):idx=1 = 人身意外险
        b.gs.observe(b.gs.invest_env_opts,
                     ('头彩', '人身意外险', '轮岗'),
                     evidence='sim:synthesized', sig=_SIG_OBS)
        out = report_action_pick_invest_env_param(
            b.gs, SimpleNamespace(idx=1), _logic_sig('Test'))
        assert out.applied
        assert (b.gs.active_env.value or '') == '人身意外险'
        assert b.gs.node_seq_by_plane.value == _modified(), \
            '环境注册即落修饰表(获得链写分支,sim 与 live 同链)'
        cw_sim_ports.declare_world(out.world_decl)
        b._maybe_finish_wait()

        seen_supply_r9 = False
        seen_boss_r10 = False
        seen_supply_p2r7 = False
        seen_supply_p3r7 = False
        for _ in range(_DEF_STEPS):
            if b.done:
                break
            screen = b.screen_identity()
            node = b.gs.node.value
            if screen == SCREEN_SUPPLY and node is not None:
                if (node.plane, node.round_num) == (1, 9):
                    seen_supply_r9 = True
                    assert len(b.gs.supply.value.options) == 3, \
                        'M18 三选一(插入补给走现役通道)'
                if (node.plane, node.round_num) == (2, 7):
                    seen_supply_p2r7 = True
                if (node.plane, node.round_num) == (3, 7):
                    seen_supply_p3r7 = True
            if screen == SCREEN_BOSS_BRIEFING and node is not None \
                    and (node.plane, node.round_num) == (1, 10):
                seen_boss_r10 = True
            _drive_step(b, 24)
        assert seen_supply_r9, 'P1 r9 = 插入补给屏'
        assert seen_boss_r10, 'P1 r10 = boss 简报'
        assert seen_supply_p2r7, 'P2 r7 = 插入补给屏'
        assert seen_supply_p3r7, 'P3 r7 = 插入补给屏(P3 行入表自动适用)'
        assert b.done, '局终(走完修饰 P3)'
        assert DISCLOSURE_RUN_COMPLETE in b.disclosures, \
            '超位面 3 = 胜利终局'
        assert DECL_SCREEN_DRIFT not in b.disclosures, \
            b.disclosures.get(DECL_SCREEN_DRIFT)
        assert (b.gs.node.value.plane, b.gs.node.value.round_num) == (3, 8), \
            '修饰局真实末节点 = P3 r8(25 节点)'
    finally:
        uninstall_backend()


def test_lock5_sim_modified_supply_income_keeps_streak() -> None:
    """插入补给轮首收入走 supply 分支:连胜不动(连胜转移在战斗结算后,
    补给轮无结算)。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_invest_env_param,
    )
    from sr_od.application.currency_war.sim import cw_sim_ports
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        SCREEN_BRIEFING,
        SCREEN_SUPPLY,
        uninstall_backend,
    )

    b = _start_game(env_present=True, seed=61)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b.gs.observe(b.gs.invest_env_opts,
                     ('头彩', '人身意外险', '轮岗'),
                     evidence='sim:synthesized', sig=_SIG_OBS)
        out = report_action_pick_invest_env_param(
            b.gs, SimpleNamespace(idx=1), _logic_sig('Test'))
        cw_sim_ports.declare_world(out.world_decl)
        b._maybe_finish_wait()
        # 快进到 P1 r8 reward 节点窗(先行 battle r3/r4 已建连胜);
        # r8 奖励轮出战结算后推进进 r9 插入补给窗。
        for _ in range(_DEF_STEPS):
            node = b.gs.node.value
            if b.done or (node is not None
                          and (node.plane, node.round_num) == (1, 8)):
                break
            _drive_step(b, 61)
        assert (b.gs.node.value.plane, b.gs.node.value.round_num) == (1, 8)
        _drive_step(b, 61)   # (1,8) 窗收尾自动弹店 → 关店回备战
        _drive_step(b, 61)   # 奖励轮出战 → 结算页(连胜不动,奖励轮非战斗类)
        _drive_step(b, 61)   # settle_confirm → 推进进 r9 插入补给窗
        assert b.screen_identity() == SCREEN_SUPPLY
        assert (b.gs.node.value.plane, b.gs.node.value.round_num) == (1, 9)
        streak_at_supply = int(b.gs.streak.value or 0)
        assert streak_at_supply >= 1, '前置非零连胜已建立(r3/r4 战斗轮)'
        _drive_step(b, 61)   # 补给选卡 → 回备战自动弹店(确认零推进)
        _drive_step(b, 61)   # 关店回备战
        _drive_step(b, 61)   # 出战 = 补给节点完成(supply_finish) → r10
        assert (b.gs.node.value.plane, b.gs.node.value.round_num) == (1, 10)
        assert int(b.gs.streak.value or 0) == streak_at_supply, \
            '补给轮连胜不动(收入 supply 分支/连胜转移战斗结算后)'
    finally:
        uninstall_backend()


def test_lock8_sim_default_game_regression() -> None:
    """默认局回归:无环境局全链一次,局终 = 走进位面 3 后 hp 归零死亡分支
    (seed 61 探针锚:前 16 节点与现役基线逐值同,3-5 遭遇战死,保底已用;
    默认环境零修饰行为不变),零 DECL_SCREEN_DRIFT;败局无 run_complete
    披露(胜负判别单一源在披露集)。"""
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        DECL_SCREEN_DRIFT,
        DISCLOSURE_RUN_COMPLETE,
        SCREEN_BRIEFING,
        uninstall_backend,
    )

    b = _start_game(env_present=False, seed=61)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        assert b.gs.node_seq_by_plane.value is None
        for _ in range(_DEF_STEPS):
            if b.done:
                break
            _drive_step(b, 61)
        assert b.done
        assert DISCLOSURE_RUN_COMPLETE not in b.disclosures, \
            'hp 归零败局不经胜利分支'
        assert DECL_SCREEN_DRIFT not in b.disclosures
        assert (b.gs.node.value.plane, b.gs.node.value.round_num) == (3, 5), \
            '默认局 seed 61 终点 = P3 r5(死亡分支,基线轮次探针实测)'
        assert int(b.gs.hp.value or 0) == 0, 'hp 归零'
        assert bool(b.gs.hp_floor_triggered.value) is True, '保底已用'
    finally:
        uninstall_backend()
