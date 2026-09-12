"""test_cw_affix_runtime_wiring —— 效果账本运行时挂点接线锁(词缀源+板面重写桥)。

被测:
- kernel/cw_affix_effects.register_affixes_from_names(简报/位面详情两读链
  共用登记体:注册表命中才登记 + 幂等 + acquired_t 节点序快照);
- 声明式驱动:词缀条目经既有挂点(节点 tick ``advance_node`` 同节点去重/
  登记当节点不推进守卫、计数 ``bump_key`` duties.track 落地门)自动辖及,
  挂点代码零来源特判(effect-domain.md §7.2「新增效果 = 新增规格声明,
  实例清单结构与挂点代码零改动」——现役三条词缀规格均无时限/计数面,
  驱动轨用合成 spec 验证,先例 = test_cw_affix_spec_registry 播种轨);
- 接线在场:效果账本挂点的生产调用点源扫锁——词缀两读链产出点
  (CwScreenBriefing._read_and_advance 开局首读 / CwScreenPlaneIntel
  .close_and_report 补采落点)调用共用登记体;选卡确认落地登记点
  (CwScreenInvestStrategy._append_confirmed_strategy)调用板面重写桥
  (apply_board_rewrite,设计 §5 全员晋升/人力重组两行的生产写端)。
  挂点被拆/改名时红,指向重接线。

设计出处(持久索引):docs/develop/sr_od/application/currency_war/game_state/effect-domain.md
§7.3(驱动事件映射·登记挂点纪律:best-effort 失败不阻塞读链)/§9.1(实例按
spec_key 唯一);BoardState 数据结构设计 §5.1(词缀效果辖域申报·挂点接线)。
"""

# ⚠️ 待归并标记(2026-09-12 data 域解体批;台账 = .debug/temp/cw_obs_rebuild/DEBT.md):
# 本文件主体 = kernel/cw_affix_effects 运行时挂点接线锁(kernel 语义),
# 非 data 表——待 kernel 接线主题归并,禁按 data 域处置。
from __future__ import annotations

import inspect
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_affix_effects import (
    register_affixes_from_names,
)
from sr_od.application.currency_war.kernel.cw_board_state import (
    ChannelSig,
    NodeKey,
    board_state_of,
    register_sig_actors,
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
from sr_od.application.currency_war.operations.cw_screen.cw_screen_briefing import (
    CwScreenBriefing,
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


# ==================== 3. 接线在场(源扫锁) ====================

def test_read_chain_producers_call_shared_register_body() -> None:
    """两读链产出点调用共用登记体:简报开局首读(_read_and_advance)与
    位面详情补采落点(close_and_report)任一被拆除/改名 → 本锁红,指向
    重接线(登记面缺位 = 词缀效果账本静默空转,改写面退回纯观察无对账输入)。"""
    src_briefing = inspect.getsource(CwScreenBriefing._read_and_advance)
    src_intel = inspect.getsource(CwScreenPlaneIntel.close_and_report)
    assert 'register_affixes_from_names' in src_briefing, \
        '简报读链登记挂点缺位(cw_screen_briefing._read_and_advance)'
    assert 'register_affixes_from_names' in src_intel, \
        '位面详情补采登记挂点缺位(cw_screen_plane_intel.close_and_report)'


def test_board_rewrite_bridge_wired_at_strategy_confirm_point() -> None:
    """选卡确认落地登记点调用板面重写桥(apply_board_rewrite,设计 §5
    全员晋升/人力重组两行的生产写端;与 register_strategy/burst 桥同点):
    调用被拆除 → 桥回归零生产调用方,板面重写族申报了语义而写端静默丢
    (出售面退款/清场不入记录,替换面失负写端留证),本锁红指向重接线。"""
    src = inspect.getsource(CwScreenInvestStrategy._append_confirmed_strategy)
    assert 'apply_board_rewrite' in src, \
        '选卡登记点板面重写桥接线缺位' \
        '(cw_screen_invest_strategy._append_confirmed_strategy)'
