"""test_cw_affix_runtime_wiring —— 效果账本运行时挂点接线锁(词缀源+板面重写桥)。

被测:
- kernel/cw_affix_effects.register_affixes_from_names(简报/位面详情两读链
  共用登记体:注册表命中才登记 + 幂等 + acquired_t 节点序快照);
- 声明式驱动:词缀条目经既有挂点(节点 tick ``advance_node`` 同节点去重/
  登记当节点不推进守卫、计数 ``bump_key`` duties.track 落地门)自动辖及,
  挂点代码零来源特判(effect-domain.md §7.2「新增效果 = 新增规格声明,
  实例清单结构与挂点代码零改动」——现役三条词缀规格均无时限/计数面,
  驱动轨用合成 spec 验证,先例 = test_cw_affix_spec_registry 播种轨);
- 挂点接线经生产链路(行为锁;原「调用点源扫」在场锁按纪律 8 退役):
  简报开局首读(_read_and_advance)与位面详情补采落点(close_and_report)
  真实驱动产出登记事实(账本条目在案);选卡确认落地登记点
  (_append_confirmed_strategy)以注册表真条目驱动板面重写桥落成
  BoardState 写端(清场+退款入金,设计 §5 全员晋升/人力重组两行的生产
  写端)。挂点被拆/改名时账本零条目/板面原值,断言红,指向重接线。

设计出处(持久索引):docs/develop/sr_od/application/currency_war/game_state/effect-domain.md
§7.3(驱动事件映射·登记挂点纪律:best-effort 失败不阻塞读链)/§9.1(实例按
spec_key 唯一);BoardState 数据结构设计 §5.1(词缀效果辖域申报·挂点接线)。
"""

# ⚠️ 待归并标记(2026-09-12 data 域解体批;台账 = .debug/temp/cw_obs_rebuild/DEBT.md):
# 本文件主体 = kernel/cw_affix_effects 运行时挂点接线锁(kernel 语义),
# 非 data 表——待 kernel 接线主题归并,禁按 data 域处置。
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_affix_effects import (
    register_affixes_from_names,
)
from sr_od.application.currency_war.kernel.cw_board_state import (
    ChannelSig,
    NodeKey,
    board_state_of,
    register_sig_actors,
    synthesize_from_game_state,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    SOURCE_AFFIX,
    ActiveEffectInventory,
    CounterKey,
    DurationKind,
    DutyFlags,
    EffectKind,
    EffectSpec,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_investments import EconomyEffect
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_invest_strategy import (
    CwScreenInvestStrategy,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_intel import (
    CwScreenPlaneIntel,
)

register_sig_actors('TestAffixWiring')


def _sig() -> ChannelSig:
    """观察签名(登记前 node 单例播种用;actor 已 register_sig_actors)。"""
    return ChannelSig(family='obs', actor='TestAffixWiring', mode='read')


def _session_with_node(plane: int, round_num: int) -> tuple[SimpleNamespace, object]:
    """裸 session 桩 + node 单例已播种(board_state_of 裸对象惰性建,§单例口)。"""
    sess: SimpleNamespace = SimpleNamespace()
    bs = board_state_of(sess)
    bs.observe(bs.node, NodeKey(plane=plane, round_num=round_num), sig=_sig())
    return sess, bs


# ==================== 1. 共用登记体(register_affixes_from_names) ====================

def test_registers_only_registry_hits() -> None:
    """注册表命中才登记:命中词缀入账本(source='affix');注册表外词缀
    (首领强化类纯数值)与豁免词缀(开局不利,专用写端载体)零条目;
    名集内重名去重不双登记。"""
    sess: SimpleNamespace = SimpleNamespace()
    reg = register_affixes_from_names(
        sess, ['成长的烦恼', '首领强化', '开局不利', '变宝为废', '成长的烦恼'])
    assert reg == ['成长的烦恼', '变宝为废'], '返回值 = 实际登记名(保序去重)'
    affix_ids = [e.spec.id
                 for e in board_state_of(sess).effects.by_source(SOURCE_AFFIX)]
    assert affix_ids == ['成长的烦恼', '变宝为废']


def test_idempotent_reregistration() -> None:
    """幂等:已登记词缀跳过、只补新增;全集重复调用零新增(简报重入/retry、
    补采重跑同词缀集不得双登记——实例按 spec_key 唯一)。"""
    sess: SimpleNamespace = SimpleNamespace()
    assert register_affixes_from_names(sess, ['成长的烦恼']) == ['成长的烦恼']
    assert register_affixes_from_names(sess, ['成长的烦恼', '变宝为废']) \
        == ['变宝为废']
    assert register_affixes_from_names(sess, ['成长的烦恼', '变宝为废']) == []
    assert len(board_state_of(sess).effects.by_source(SOURCE_AFFIX)) == 2


def test_acquired_t_uses_board_node_snapshot() -> None:
    """acquired_t = 登记时点节点序快照:(plane-1)*9+round 基 1,BoardState
    节点单例优先(与策略源登记挂点同坐标系)。"""
    sess, bs = _session_with_node(plane=2, round_num=3)
    register_affixes_from_names(sess, ['成长的烦恼'])
    assert bs.effects.first('成长的烦恼').acquired_t == (2 - 1) * 9 + 3


def test_acquired_t_falls_back_to_last_state_then_none() -> None:
    """node 未读 → 回退 session.last_state(引导窗同式);两者皆缺 → None
    (登记期快照缺位不炸登记面,词缀现役 WHILE_HELD 无余期语义)。"""
    sess = SimpleNamespace(last_state=SimpleNamespace(plane=2, round_num=1))
    register_affixes_from_names(sess, ['成长的烦恼'])
    assert board_state_of(sess).effects.first('成长的烦恼').acquired_t == 10
    sess_none: SimpleNamespace = SimpleNamespace()
    register_affixes_from_names(sess_none, ['成长的烦恼'])
    assert board_state_of(sess_none).effects.first('成长的烦恼').acquired_t is None


# ==================== 2. 声明式驱动(挂点零来源特判) ====================

def test_affix_entry_driven_by_node_tick_declaratively() -> None:
    """词缀 N_NODES 条目经节点 tick 挂点机制自动推进:登记当节点不推进 →
    同节点去重(advanced=False 零重复递减)→ 达 0 到期移除——与策略源共用
    同一 advance_node,词缀侧零特判(合成 spec,先例 = 播种轨验证)。"""
    inv = ActiveEffectInventory()
    spec = EffectSpec(id='词缀时限形', name='词缀时限形',
                      trigger=TriggerKind.NODE_ENTER,
                      duration=DurationKind.N_NODES,
                      category=EffectKind.ECONOMY, payload=EconomyEffect(),
                      duties=DutyFlags(track=True), duration_nodes=3)
    inv.register_affix(spec, acquired_t=5)
    advanced, expired = inv.advance_node(6)
    assert advanced and expired == []
    assert inv.first('词缀时限形').remaining_nodes == 2
    advanced_again, _ = inv.advance_node(6)
    assert not advanced_again, '同节点重采样被去重键挡下'
    assert inv.first('词缀时限形').remaining_nodes == 2, '去重轮零重复递减'
    inv.advance_node(7)
    inv.advance_node(8)
    assert inv.first('词缀时限形') is None, '第 3 次有效推进到期移除'


def test_bump_key_drives_track_declared_affix_entry() -> None:
    """计数 bump 挂点机制按 duties.track 辖及词缀条目:track 开的词缀条目
    随动作落地门推进,未声明 track 的词缀条目零计数——「谁要记账」单一源 =
    EffectSpec.duties.track,来源词表不参与过滤(来源特判 = 本锁红)。"""
    inv = ActiveEffectInventory()
    track_spec = EffectSpec(id='词缀计数形', name='词缀计数形',
                            trigger=TriggerKind.ON_REFRESH,
                            duration=DurationKind.WHILE_HELD,
                            category=EffectKind.BATTLEFIELD,
                            payload=EconomyEffect(),
                            duties=DutyFlags(track=True))
    silent_spec = EffectSpec(id='词缀静默形', name='词缀静默形',
                             trigger=TriggerKind.ON_REFRESH,
                             duration=DurationKind.WHILE_HELD,
                             category=EffectKind.BATTLEFIELD,
                             payload=EconomyEffect(),
                             duties=DutyFlags())
    inv.register_affix(track_spec, acquired_t=1)
    inv.register_affix(silent_spec, acquired_t=1)
    inv.bump_key(CounterKey.REFRESH)
    assert inv.counter('词缀计数形', CounterKey.REFRESH) == 1
    assert inv.counter('词缀静默形', CounterKey.REFRESH) == 0


# ==================== 3. 挂点接线经生产链路(行为锁;原源码在场锁退役) ====================

def test_briefing_read_chain_registers_hits_into_ledger(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """简报开局首读经生产链路把注册表命中词缀登记进效果账本(替代原
    「调用点源扫」在场锁——纪律 8 肯定性在场禁档;失守语义 = 登记面缺位
    致账本静默空转,现由真实驱动承载:删调用/改名 → 账本零条目即红)。
    出处 = effect-domain.md §7.3(登记挂点纪律:best-effort 失败不阻塞
    读链;登记体自身幂等由 §1 锁辖)。"""
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_briefing as bm,
    )
    session = StrategySession()
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    op = bm.CwScreenBriefing(test_context)
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'round_by_find_and_click_area',
                        lambda *a, **k: SimpleNamespace(is_success=True),
                        raising=False)
    monkeypatch.setattr(bm, 'read_affixes_with_pos',
                        lambda ctx, scr: [('成长的烦恼',
                                           SimpleNamespace(x=1, y=1))])
    monkeypatch.setattr(bm, 'read_bosses', lambda ctx, scr: [])
    monkeypatch.setattr(bm, 'read_briefing_enemy_difficulty',
                        lambda ctx, scr: None)
    monkeypatch.setattr(bm.CwScreenBriefing, '_collect_affix_effects',
                        lambda self, aff: {})
    rs = op._read_and_advance(op.last_screenshot)
    assert session.briefing_affixes == ['成长的烦恼'], '读链直写 session 在环'
    assert not rs.is_success and '重入观察裁决' in (rs.status or ''), \
        f'「下一步」已发机械交回(主链保形):{rs!r}'
    assert [e.spec.id
            for e in board_state_of(session).effects.by_source(SOURCE_AFFIX)] \
        == ['成长的烦恼'], '读链登记挂点缺位 = 账本零条目(静默空转)'


def test_plane_intel_close_report_registers_hits_into_ledger(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """位面详情补采落点(close_and_report)经生产链路登记词缀入账本
    (同上替代形态;补采产出点 = ctx 中转与登记挂点同段,接管局补采
    重跑幂等由登记体辖)。出处 = effect-domain.md §7.3。"""
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    session = StrategySession()
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    # ctx 中转槽 monkeypatch 预登记(生产在 close_and_report 内赋值,拆卸
    # 时还原,纪律 1:共享 ctx 改动一律走 monkeypatch)
    monkeypatch.setattr(test_context, 'cw_plane_bosses', [], raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_affixes', [], raising=False)
    op = CwScreenPlaneIntel(test_context)
    monkeypatch.setattr(op, 'screenshot', lambda: object(), raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda *a, **k: SimpleNamespace(is_success=False),
                        raising=False)
    op._affixes = ['成长的烦恼']
    rs = op.close_and_report()
    assert rs.is_success, f'补采收尾语义:{rs!r}'
    assert test_context.cw_plane_affixes == ['成长的烦恼'], 'ctx 中转在环'
    assert [e.spec.id
            for e in board_state_of(session).effects.by_source(SOURCE_AFFIX)] \
        == ['成长的烦恼'], '补采登记挂点缺位 = 账本零条目(静默空转)'


def test_append_confirmed_strategy_applies_board_rewrite(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """选卡确认落地登记点把板面重写桥落成 BoardState 写端(替代原源码
    在场锁):真实驱动 ``_append_confirmed_strategy('人力重组')``——
    注册表真条目(payload.board_rewrite = sell_all,单一源 =
    STRATEGY_EFFECTS)→ 出售面清场 + 退款按卖价公式入金;期望值从容器
    观察值经 cw_state 单一源现算(纪律 9),删桥调用 → 板面保持原值即红。
    出处 = BoardState 数据结构设计 §5 人力重组行 / effect-domain.md §6.3
    (归属判据确定性分支)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_EFFECTS,
        normalize_invest_name,
    )
    from sr_od.application.currency_war.kernel.cw_state import (
        bench_char_cost,
        sell_refund,
    )
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    # 锁前提自检:注册表锚在位(区分「注册表值漂移」与「桥调用被拆」)
    assert STRATEGY_EFFECTS.get(normalize_invest_name('人力重组')) is not None, \
        '人力重组注册表锚漂移(换锚并同步本注释)'
    session = StrategySession()
    frame = GameState(plane=1, round_num=2)
    frame.gold = 40
    frame.bench = [BenchChar(slot=1, char_id='希儿', star=1)]
    frame.deployed = [BenchChar(slot=1, char_id='景元', star=2,
                                position_pref='front')]
    # 合成进 session 惰性单例板(生产桥读写 = board_state_of(session),
    # 独立 BoardState 对象不进桥视线)
    bs = board_state_of(session)
    synthesize_from_game_state(bs, frame, at_round='p1-r2')
    # 期望退款从容器观察值经单一源现算(与桥内同式,预驱动读取)
    sold = (list(bs.front_row.value) + list(bs.back_row.value)
            + [s.unit for s in bs.bench.value.slots
               if s.kind == 'unit' and s.unit is not None])
    expected_refund = sum(sell_refund(int(u.star), bench_char_cost(u))
                          for u in sold)
    assert expected_refund > 0, '锁前提:合成板面非空(空场驱动无判别力)'
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    op = CwScreenInvestStrategy(test_context)
    op._append_confirmed_strategy('人力重组')
    assert list(bs.front_row.value) == [] and list(bs.back_row.value) == [], \
        '出售面清场写端缺位(桥调用被拆 → 板面保持原值即本断言红)'
    assert all(s.kind == 'empty' for s in bs.bench.value.slots), \
        '备战席清场写端缺位(容量保留语义由载体锁辖)'
    assert bs.gold.value == 40 + expected_refund, (
        f'退款按卖价公式入金(确定性分支,禁零写入):'
        f'{bs.gold.value} vs {40 + expected_refund}')
    assert session.active_strategies == ['人力重组'], '持卡本体追加在环'
