"""GameState 迁移回归锁(迁移批次一;设计正本 = docs/develop/sr_od/application/currency_war/
changes/2026-09-11-unified-state/details/GameState-数据结构设计.md,下称「设计」)。

锁面 = 写入口两态制与构造守卫(§2.1-§2.4/§8.6-5)+ 派生不存储
(§8.6-4 续)+ 观察流接线与 hp 失读统一口径 + 心跳哨兵(§2.4 关键
结构 2)+ sim 合成口箱占席语义(§3.2.5;迁移批次一任务书第 7 件)
+ 设计 §8.7 批次三(挂点机制/B1 桥)与批次四(退役 + relay 空值闸)
两组锁——原独立批次文件按主题文件纪律归并,断言体零语义改动。断言
全部按设计语义写,禁按 level 驱动表/线性外推写(设计 §3.2.7 回归
测试断言约束)。

退役面:§8.6 差距清单逐条锁(gap3/gap4 组)与 §3 字段语义抽样组已删;
心跳写点序/断流计数两锁并一,level_up/battle_end 挂点两锁并一,
tick/advance_node 两锁并一(并入腿见各测试 docstring)。

合并面(第二刀,断言腿零丢失):bench_free 两形态参数化并一;失配缺陷
台账+sink drain 并一;合成口真值域 on/off 参数化并一;feed 接线+hp 三
分支同帧驱动并一;burst/per_node 授权两形态参数化并一;relay 单元三锁
表驱动并一(并自 test_cw_game_state_consume 移入 relay_skips_official);
relay 端到端两锁并一;席位视图转换三锁并一(ShopCard 映射单锁独立)。

草板对照物 = .debug/temp/currency_war/record_data_model/board_state.py
(易失产物,不构成出处;出处 = 设计章节号)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    ActiveEffectInventory,
    CounterKey,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BENCH_CAPACITY_DEFAULT,
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    GameState,
    NodeKey,
    Unit,
    apply_effect_burst_grant,
    bench_free_slots,
    bench_is_full,
    bench_slots_to_legacy,
    consume_defect_sink,
    deployed_rows_from_obs,
    game_state_of,
    grant_effect_node_refresh_balance,
    project_effect_capacity,
    set_defect_sink,
    shop_card_to_container,
    shop_cards_to_legacy,
    synthesize_from_game_state,
    unit_rows_to_deployed,
)

# ---- W1 sig 铺满 helper(测试写入口签名必填,ADR-0634;actor 已登记)----
from sr_od.application.currency_war.kernel.cw_game_state import (  # noqa: E402
    ChannelSig as _ChannelSig,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    register_sig_actors as _register_sig_actors,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_mismatch_policy import (
    EXEMPT_ANY as _EXEMPT_ANY,
)
from sr_od.application.currency_war.kernel.cw_mismatch_policy import (
    ExemptEntry as _ExemptEntry,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BenchChar,
    CwSimFrame,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    ShopCard as StateShopCard,
)

_register_sig_actors('TestSigWriter')


def _sig() -> _ChannelSig:
    """渠道①签名(obs 族;观察/沿用/先验/离屏/观察事件)。"""
    return _ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _lsig() -> _ChannelSig:
    """渠道②签名(logic_action 族;逻辑写入/confirm)。"""
    return _ChannelSig(family='logic_action', actor='TestSigWriter',
                       mode='compute')


def _hsig() -> _ChannelSig:
    """渠道③签名(logic_hook 族;relay 中继)。"""
    return _ChannelSig(family='logic_hook', actor='TestSigWriter',
                       mode='compute')



# ============================================================ §8.6-1/§2.1
# Field 四来源 observation/logic/carried/prior + evidence 注记


# ============================================================ §8.6-2/§2.4
# 心跳写点序哨兵(单调推进)


def test_write_logic_direct_write_immediately_readable() -> None:
    """ADR-0651 两态制核心锁(写通道合同正本,全仓唯一份):逻辑推算值经
    write_logic **直接写字段**(source=logic)——策略器立即可读,无「预期
    条目表挂账」中间态;evidence 透传入账。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, 20, sig=_sig())
    gs.write_logic(gs.gold, 17, produced_by='TestSigWriter',
                   evidence='probe@p1-r2', sig=_lsig())
    assert gs.gold.value == 17, '逻辑直写:字段立即可读(策略器读得到)'
    assert gs.gold.source == 'logic', 'logic 值保持 logic 来源(§8.1)'
    assert gs.gold.evidence == 'probe@p1-r2', 'evidence 原值透传'


def test_write_seq_monotonic_counter() -> None:
    """§2.4 写点序哨兵:停更检测载体 = 只增不减写点序(写点序号),不做帧标注
    现值(消费即清后当不了哨兵)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seq0 = gs.heartbeat()
    gs.observe(gs.gold, 20, sig=_sig())
    gs.observe(gs.gold, 21, sig=_sig())
    gs.mark_frame_obs('full')
    assert gs.consume_frame_obs() == 'full', '消费标注不影响哨兵计数'
    seq1 = gs.heartbeat()
    assert seq1 > seq0, '写点推进 → 心跳单调递增(不断流)'
    gs.carry(gs.gold, frame='p1-r5', sig=_sig())
    assert gs.heartbeat() > seq1, 'carried 写也是写点,哨兵照常推进'


# ============================================================ §8.6-4(续)
# 派生不存储:席空数/席满判定/board 下档阈值 = 计算函数,禁入 schema


@pytest.mark.parametrize('case', ['unobserved-honest-none',
                                  'occupying-kinds-counted'])
def test_bench_free_slots_and_full_derivation(case: str) -> None:
    """§3.2.5 席空数派生两形态一锁(参数化并一):
    - unobserved-honest-none:席空数没读到 = 不确定,**禁猜 0**——bench
      从未观察返 None(bench_is_full 同为 None);
    - occupying-kinds-counted:席空数派生 = capacity − 占席槽数;箱占席
      计入(实机真值,sim 无箱实体只是 sim 内部口径约定,不进记录模型),
      8 单位 + 1 箱 = 满。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if case == 'unobserved-honest-none':
        assert bench_free_slots(gs) is None
        assert bench_is_full(gs) is None
        return
    slots = [BenchSlot(kind='unit'), BenchSlot(kind='supply_box'),
             BenchSlot(kind='tome')] + [BenchSlot(kind='empty')] * 6
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_sig())
    assert bench_free_slots(gs) == 6
    assert bench_is_full(gs) is False
    full = [BenchSlot(kind='unit')] * 8 + [BenchSlot(kind='supply_box')]
    gs.observe(gs.bench, BenchView(slots=full, capacity=9), sig=_sig())
    assert bench_is_full(gs) is True, '8 单位 + 1 箱 = 满(箱占席)'


# ============================================================ §8.6-5
# 构造守卫:frozen 帧替换 + hp 不变式 + 缺陷台账挂点


def test_observe_replaces_frame_not_mutates() -> None:
    """§2.4:frozen 帧替换——旧帧引用保持旧值(持旧引用的读者不被跨时段写回污染)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    old = gs.gold
    gs.observe(gs.gold, 20, sig=_sig())
    assert old.value is None and old.source == 'observation'
    assert gs.gold.value == 20 and gs.gold is not old


def test_observe_rejects_none_loses_are_carried_not_cleared() -> None:
    """§2.2 硬边界:observe(None) 拒绝——失读走 carried(处置①)或保持 None
    (处置②),字段一旦有过正式值任何失读不得清成 None。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    with pytest.raises(ValueError):
        gs.observe(gs.hp, None, sig=_sig())
    gs.observe(gs.hp, 80, sig=_sig())
    gs.carry(gs.hp, frame='p1-r5', sig=_sig())
    assert gs.hp.value == 80, '失读帧沿用上次好值'
    assert gs.hp.source == 'carried' and gs.hp.evidence == 'carried:p1-r5'
    assert gs.hp.value is not None, '硬边界:正式值永不清成 None'


def test_write_prior_requires_prior_evidence() -> None:
    """§2.1/§3.1.6:prior 写入必带 prior: 来源注记;禁扩散(仅显式申报条目)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    with pytest.raises(ValueError):
        gs.write_prior(gs.hp, 82, evidence='carried:x', sig=_sig())
    gs.write_prior(gs.hp, 82, evidence='prior:adr-0559', sig=_sig())
    assert gs.hp.value == 82 and gs.hp.source == 'prior'


def test_leave_screen_payload_only() -> None:
    """§2.2 显式例外:画面附加域(kernel 三域口径 shop/encounter/supply)离开
    画面置 None 是结构事实,不受 carried 硬边界辖;整局字段禁走此口,
    settlement(结算真值组,§3.5.1)非画面 payload 同样禁离屏清值。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.shop, SimpleNamespace(cards=[]), sig=_sig())
    gs.observe(gs.encounter, SimpleNamespace(options=[]), sig=_sig())
    gs.observe(gs.supply, SimpleNamespace(options=[]), sig=_sig())
    gs.leave_screen(gs.shop, sig=_sig())
    gs.leave_screen(gs.encounter, sig=_sig())
    gs.leave_screen(gs.supply, sig=_sig())
    assert gs.shop.value is None and gs.encounter.value is None \
        and gs.supply.value is None
    assert gs.shop.source == 'observation' \
        and gs.shop.evidence == 'left_screen', \
        '离屏 = 置 None + left_screen 注记(§2.2 显式例外形态)'
    gs.observe(gs.gold, 20, sig=_sig())
    with pytest.raises(ValueError):
        gs.leave_screen(gs.gold, sig=_sig()), '整局字段(有过正式值)禁离屏清值'
    gs.observe(gs.settlement, SimpleNamespace(hp_after=76), sig=_sig())
    with pytest.raises(ValueError):
        gs.leave_screen(gs.settlement, sig=_sig()), 'settlement 非画面附加域,禁离屏'


def test_observe_over_logic_mismatch_defect_row_and_sink_drain() -> None:
    """§2.3/ADR-0651 失配缺陷台账 + 挂点消费并一(合并原
    test_observe_over_logic_mismatch_emits_defect_row /
    test_consume_defect_sink_drains,断言腿逐条保留):

    - 失配腿:观察覆盖 logic 值失配 → 失配记入缺陷台账(挂点注入,缺省
      关);观察赢——来源改回 observation。失配 = 推算 bug 留证修码;
      一致反腿 = 投影被实读核实形态,零缺陷行;
    - drain 腿:挂点 = 注入槽模式(缺省关+显式接通;模块级缓冲在 setup
      先清,隔离整条副作用链);consume 供装配点取走行后复位,防跨局
      残留。"""
    # —— 失配腿(失配留证 + 观察赢)——
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.gold, 17, produced_by='TestSigWriter', sig=_lsig())
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.gold, 19, sig=_sig())
    finally:
        set_defect_sink(None)
        drained = consume_defect_sink()
    assert len(rows) == 1
    assert rows[0]['field'] == 'gold'
    assert rows[0]['expected'] == 17 and rows[0]['actual'] == 19
    assert rows[0]['ts'], '行补 ts(journal 行同款秒级时刻)'
    assert rows[0]['screen'] is None and rows[0]['actor'] == 'TestSigWriter', \
        '行携带观察侧 sig(screen 缺省 None / actor)'
    assert rows[0]['group_id'] is None and rows[0]['logic_evidence'] is None, \
        '行携带观察侧组 id 与逻辑侧写端注记(本腿均无)'
    assert gs.gold.source == 'observation', '观察赢:来源改回 observation'
    assert drained == rows, 'consume 取走行(装配点消费面)'
    assert consume_defect_sink() == [], '消费后复位,防跨局残留'
    # 一致反腿:观察值与 logic 值一致 = 静默核实,不留缺陷行
    bs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    bs2.write_logic(bs2.gold, 17, produced_by='TestSigWriter', sig=_lsig())
    rows_ok: list[dict] = []
    set_defect_sink(rows_ok.append)
    try:
        bs2.observe(bs2.gold, 17, sig=_sig())
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert rows_ok == [], '一致 = 静默核实,零缺陷行'


def test_observe_mismatch_three_way_routing(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """失配三分流并一锁(迭代 2026-09-16-unified-obs-reconcile,design §2.3):

    - 真失配腿:缺陷行落盘后安灯钩子同步被调(行同构);sim 前缀两值
      (sim:engine 现役 / sim:synthesized 本迭代并列)→ 不落行不调钩子;
    - 豁免腿:精确键(画面×字段×写端前缀)命中 → exempt_mismatch 行
      (同形状换 kind),无告警面消费、钩子不被调;写端前缀不中 → 真失配
      照落(同字段他写端不被吞);
    - 处置序腿(验收 minor3):sim 证据 + 豁免条目同时命中 → 豁免先行
      落 exempt 行(处置序 = 豁免→sim→真失配,禁 sim 检查提前翻转语义);
      真失配腿 [cw!] 告警面被调、豁免腿不被调(验收 minor2)。"""
    from sr_od.application.currency_war.kernel import cw_game_state as _gs_mod
    from sr_od.application.currency_war.kernel import (
        cw_mismatch_policy as _policy,
    )

    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    warns: list[tuple] = []
    monkeypatch.setattr(_gs_mod.log, 'warning',
                        lambda *a, **k: warns.append(a))

    def _run_observe(gs: GameState, sig: _ChannelSig, read: int,
                     observed_evidence: str | None = None) -> list[dict]:
        rows_: list[dict] = []
        set_defect_sink(rows_.append)
        try:
            if observed_evidence is None:
                gs.observe(gs.gold, read, sig=sig)
            else:
                gs.observe(gs.gold, read, evidence=observed_evidence, sig=sig)
        finally:
            set_defect_sink(None)
            consume_defect_sink()
        return rows_

    # —— 真失配腿:行落盘 + 钩子被调(行同构)+ 覆盖照常 ——
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.gold, 17, produced_by='TestSigWriter',
                   evidence='free_refresh@p1-r4', sig=_lsig())
    _sig_screen = _ChannelSig(family='obs', actor='TestSigWriter',
                              screen='货币战争-备战', mode='read',
                              group_id='act:T@1')
    rows = _run_observe(gs, _sig_screen, 19)
    assert len(rows) == 1 and rows[0]['kind'] == 'observe_vs_logic_mismatch'
    assert fired and fired[0] == rows[0], '钩子收到与落盘同构的缺陷行'
    assert rows[0]['logic_evidence'] == 'free_refresh@p1-r4'
    assert gs.gold.source == 'observation', '观察赢覆盖照常'
    assert any('观察覆盖 logic 失配' in str(w) for w in warns), \
        '真失配带 [cw!] 告警面'

    # —— sim 前缀两值:不落行不调钩子(抑制语义,生产台账分流)——
    bs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    bs2.write_logic(bs2.gold, 17, produced_by='TestSigWriter', sig=_lsig())
    for prefix in ('sim:synthesized@p1-r2', 'sim:engine:income'):
        fired.clear()
        warns.clear()
        rows_sim = _run_observe(bs2, _sig(), 19, observed_evidence=prefix)
        assert rows_sim == [], f'{prefix} 抑制:不落生产台账'
        assert fired == [], f'{prefix} 抑制:安灯不触发'
        assert not any('观察覆盖 logic 失配' in str(w) for w in warns), \
            f'{prefix} 抑制:无告警'

    # —— 豁免腿:精确键命中 → exempt 行(钩子不被调);前缀不中 → 真失配 ——
    monkeypatch.setattr(_policy, 'EXEMPT_REGISTRY', {
        ('货币战争-备战', 'gold'): (_ExemptEntry(
            screen='货币战争-备战', field='gold',
            logic_evidence='free_refresh@', reason='测试豁免'),),
    })
    bs3 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    bs3.write_logic(bs3.gold, 17, produced_by='TestSigWriter',
                    evidence='free_refresh@p1-r4', sig=_lsig())
    fired.clear()
    rows_exempt = _run_observe(bs3, _sig_screen, 19)
    assert len(rows_exempt) == 1 \
        and rows_exempt[0]['kind'] == 'exempt_mismatch', \
        '豁免命中落 exempt 行(豁免 ≠ 消失,可审计)'
    assert rows_exempt[0]['ts'] and rows_exempt[0]['screen'] == '货币战争-备战' \
        and rows_exempt[0]['logic_evidence'] == 'free_refresh@p1-r4', \
        'exempt 行与真失配行同构(仅 kind 不同)'
    assert fired == [], '豁免命中:无告警无停机(钩子不被调)'
    assert not any('观察覆盖 logic 失配' in str(w) for w in warns), \
        '豁免命中:无 [cw!] 告警(验收 minor2)'
    assert bs3.gold.source == 'observation', '豁免腿覆盖照常(观察赢)'

    # —— 处置序腿(验收 minor3):sim 证据 + 豁免条目同击 → 豁免先行 ——
    monkeypatch.setattr(_policy, 'EXEMPT_REGISTRY', {
        ('货币战争-备战', 'gold'): (_ExemptEntry(
            screen='货币战争-备战', field='gold',
            logic_evidence=_EXEMPT_ANY, reason='测试条目'),),
    })
    bs5 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    bs5.write_logic(bs5.gold, 17, produced_by='TestSigWriter',
                    evidence='proj_sell_refund@p1-r1', sig=_lsig())
    fired.clear()
    rows_order = _run_observe(bs5, _sig_screen, 19,
                              observed_evidence='sim:synthesized@p1-r1')
    assert len(rows_order) == 1 \
        and rows_order[0]['kind'] == 'exempt_mismatch', \
        '豁免先于 sim 抑制(design §2.3 处置序;sim 检查提前即翻转为静默)'
    assert fired == []

    # —— 前缀不中反腿:恢复精确条目注册表,他写端 → 真失配照落 ——
    monkeypatch.setattr(_policy, 'EXEMPT_REGISTRY', {
        ('货币战争-备战', 'gold'): (_ExemptEntry(
            screen='货币战争-备战', field='gold',
            logic_evidence='free_refresh@', reason='测试条目'),),
    })
    bs4 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    bs4.write_logic(bs4.gold, 17, produced_by='TestSigWriter',
                    evidence='post_buy@p1-r4', sig=_lsig())
    fired.clear()
    rows_true = _run_observe(bs4, _sig_screen, 19)
    assert len(rows_true) == 1 \
        and rows_true[0]['kind'] == 'observe_vs_logic_mismatch', \
        '同字段他写端不中豁免 → 真失配照落(前缀维度防吞真失败)'
    assert len(fired) == 1, '真失配钩子照触发'


# ============================================================ 单例宿主与心跳观察者


def test_game_state_of_binds_per_session() -> None:
    """§1:单例,每局新建——session 对象 = 局身份,新 session = 新 GameState。"""
    s1 = SimpleNamespace()
    s2 = SimpleNamespace()
    assert game_state_of(s1) is game_state_of(s1)
    assert game_state_of(s1) is not game_state_of(s2)


# ============================================================ §3.2.5(任务书件 7)
# sim 合成口:记录模型按实机真值箱占席;sim 真值合成 evidence 恒 sim:synthesized


@pytest.mark.parametrize('case', ['truth-on-preserves-bench-slots',
                                  'truth-off-not-written'])
def test_sim_synthesis_truth_domain(case: str) -> None:
    """§2.1/§3.2.5 合成口真值域 on/off 两形态一锁(参数化并一):
    - truth-on:sim 真值合成 bench 槽位保序(0 基下标 → 1 基物理槽位),
      记录模型不采 sim「箱不占席」内部口径;evidence 恒带 sim:synthesized
      标记(at_round 轮键并入,P2-6 非死参);真值记 observation;
    - truth-off:sim 帧真值 None 的字段不写(sim 无识别过程,不存在失读;
      未建模域保持 None 诚实缺位,禁合成假值;合成口不写节点序——节点由
      观察链派生)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if case == 'truth-on-preserves-bench-slots':
        # 经构造器传入(__post_init__ pad 到定长 9,ADR-0316 形状契约;直赋值
        # 绕过 pad 是旧紧缩构造兼容域,合成口输出侧补齐见模块实现)。
        st = CwSimFrame(bench=[
            BenchChar(slot=1, char_id='阿格莱雅', star=1),
            None,
            BenchChar(slot=3, char_id='花火', star=2),
        ])
        st.gold = 20
        st.hp = 80
        synthesize_from_game_state(gs, st, at_round='p1-r2')
        view = gs.bench.value
        assert view is not None and view.capacity == 9
        assert [s.kind for s in view.slots] == ['unit', 'empty', 'unit'] \
            + ['empty'] * 6, '槽位保序:sim 紧缩/稀疏表 1:1 映射物理槽位'
        assert view.slots[0].unit is not None \
            and view.slots[0].unit.char_id == '阿格莱雅'
        assert gs.gold.value == 20
        assert gs.gold.evidence == 'sim:synthesized@p1-r2', \
            '§2.1:evidence 恒带标记;at_round 轮键并入注记(P2-6,非死参)'
        assert gs.gold.source == 'observation', 'sim 真值记 observation'
        assert gs.hp.value == 80
        return
    st = CwSimFrame()   # hp=None(未观测态);gold 默认 0 且 readable=True(P2-3 实断言依据)
    synthesize_from_game_state(gs, st, at_round='p1-r1')
    assert gs.hp.value is None
    assert gs.node.value is None, \
        'node_type 未建模(裸构造 None)不合成 kind 占位(P1-1 同型泛化)'
    assert gs.node_ord.value is None, '合成口不写节点序(节点由观察链派生)'
    assert gs.gold.value == 0 \
        and gs.gold.evidence == 'sim:synthesized@p1-r1', \
        'gold 真值(缺省 0,readable)合成 observation;at_round 并入 evidence(P2-6)'


def test_synthesis_unread_bench_no_clobber() -> None:
    """bench 写门(CwSimFrame.bench_readable,对齐 board_readable 先例):
    未读域≠真空域。v1 漏斗帧(read_game_state 不读 bench 身份,bench 恒
    默认空表)合成必须跳写 bench——容器内备战装配环的真读观察保持原值
    原版本;可读真值帧(sim 形态,缺省 True)照写不回归。回归形态 = 无门
    合成把 prep 装配环真读覆盖成「9 槽全空」假真空,容器与执行账 tracked
    两账从此不同源(实机 2026-09-13 商店段循环崩溃实证;原表述
    中的双账对账载体已随批退役,本门的防覆盖语义独立存续)。"""
    sig = _ChannelSig(family='obs', actor='TestSigWriter', mode='read')
    # 容器先有漏斗真读(deploy 后留 bench:物理槽 4 一人,1 基槽号信息位)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='empty')] * 3
        + [BenchSlot(kind='unit', unit=Unit(char_id='银枝', star=1, slot=4))]
        + [BenchSlot(kind='empty')] * 5,
        capacity=BENCH_CAPACITY_DEFAULT), sig=sig)
    bench_field_before = gs.bench   # Field 实例同一性:_swap 写入即换实例
    # v1 形态帧:bench 恒默认空表 + 不可读位(生产置位点 = read_game_state)
    st_v1 = CwSimFrame()
    st_v1.bench_readable = False
    synthesize_from_game_state(gs, st_v1, at_round='p1-r1')
    view = gs.bench.value
    assert view is not None and view.slots[3].unit is not None \
        and view.slots[3].unit.char_id == '银枝', \
        '未读 bench 合成跳写:容器内漏斗真读保持原值'
    assert gs.bench is bench_field_before, \
        '跳写 = bench Field 实例不换(其余域合成照写,版本推进不涉本域)'
    # 真值帧(sim 形态,缺省可读)照写:域语义不回归
    st_sim = CwSimFrame(bench=[BenchChar(slot=1, char_id='花火', star=2)])
    synthesize_from_game_state(gs, st_sim, at_round='p1-r2')
    assert gs.bench.value.slots[0].unit is not None \
        and gs.bench.value.slots[0].unit.char_id == '花火', \
        '可读帧合成照写(真值域语义不变)'


def _feed_ctx(sess: SimpleNamespace) -> SimpleNamespace:
    """read_game_state 观察流测试的最小 ctx(mock ocr_service 空读;
    screen_loader 空 = 全部 area rect 缺失 → 各 reader 自然失读)。"""
    return SimpleNamespace(
        cw_match=SimpleNamespace(session=sess),
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        ocr_service=SimpleNamespace(get_ocr_result_list=lambda **kw: []),
    )


def _patch_clean_readers(monkeypatch: pytest.MonkeyPatch) -> None:
    """prep_clean 帧各 reader 桩(只读链,零像素;真读值显式给定)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    from sr_od.application.currency_war.obs import cw_observation as obs

    monkeypatch.setattr(obs, 'read_gold_settled', lambda ctx, screen: 20,
                        raising=False)
    monkeypatch.setattr(obs, 'read_phase_round', lambda ctx, screen: (1, 4),
                        raising=False)
    monkeypatch.setattr(obs, 'read_hp_opt', lambda ctx, screen: None,
                        raising=False)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='', node_t=None:
                        (82, False), raising=False)
    monkeypatch.setattr(obs, 'read_node_type', lambda ctx, screen: 'battle',
                        raising=False)
    monkeypatch.setattr(obs, 'gate_node_type', lambda v, rn: v, raising=False)
    monkeypatch.setattr(obs, 'ledger_node_type',
                        lambda sess_, p, r: None, raising=False)
    monkeypatch.setattr(obs, 'verify_node_type_votes',
                        lambda ctx, screen, p, r: None, raising=False)
    monkeypatch.setattr(obs, 'read_xp_progress',
                        lambda ctx, screen, expected_level=None: (2, 8),
                        raising=False)
    monkeypatch.setattr(obs, 'read_level_raw_opt', lambda ctx, screen: 5,
                        raising=False)
    monkeypatch.setattr(obs, '_level_from_xp', lambda xp: None, raising=False)
    monkeypatch.setattr(obs, '_resolve_level',
                        lambda raw, exp, xp_lv, last: (5, [], True),
                        raising=False)
    monkeypatch.setattr(obs, 'resolve_paddle_pair',
                        lambda ctx, screen, level: (None, None), raising=False)
    monkeypatch.setattr(obs, 'board_from_tracked', lambda tracked: None,
                        raising=False)
    monkeypatch.setattr(obs, 'is_prep_like_frame',
                        lambda ctx, screen: True, raising=False)
    monkeypatch.setattr(obs, '_board_pairs',
                        lambda ctx, screen, max_count=9, expected=None:
                        ({'列车同行': (2, 3)}, True), raising=False)


def test_observation_feed_wiring_and_hp_loss_semantics(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """观察流接线 + hp 失读统一口径同帧驱动一锁(合并原
    test_observation_feed_wires_board_state /
    test_observation_feed_hp_unified_loss_semantics,断言腿逐条保留):

    - 接线腿(任务书件 2):read_game_state 观察流——真读字段进 GameState
      (observation);失读字段走 carried/prior;hp 写入闸:非真读帧不经
      observe 假值入账;
    - hp 三分支腿(§2.2,任务书件 1 断言面):①字段已有正式值 → 失读写
      carried(沿用+来源帧标注);②字段从未读过 → 保持 None(机制性
      None,session 外源值禁猜入);真值帧 → observation 转正。"""
    from sr_od.application.currency_war.obs import cw_observation

    # —— 接线腿:干净 prep_clean 帧,真读值进容器,hp 开局先验形态 ——
    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    _patch_clean_readers(monkeypatch)
    cw_observation.read_game_state(_feed_ctx(sess), None, phase='prep_clean')
    gs = game_state_of(sess)
    assert gs.gold.value == 20 and gs.gold.source == 'observation'
    assert gs.node.value is not None
    assert gs.node.value.plane == 1 and gs.node.value.round_num == 4
    assert gs.node.value.kind == 'battle'
    assert gs.hp.value == 82 and gs.hp.source == 'prior', \
        'hp 读不到∧session 无真值 = 开局先验形态,prior 写入(§3.1.6)'
    assert gs.hp.evidence == 'prior:adr-0559'
    assert gs.level.value == 5 and gs.level.source == 'observation'
    assert gs.board.value == {'列车同行': 2}

    # —— hp 三分支腿(独立 session;同帧驱动,换 reconcile 读数)——
    from sr_od.application.currency_war.kernel import cw_reconcile

    sess2 = SimpleNamespace(last_streak=0, active_strategies=[],
                            last_hp_real=80, last_hp_real_node=12)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='', node_t=None:
                        (80, False), raising=False)
    cw_observation.read_game_state(_feed_ctx(sess2), None,
                                   phase='prep_clean')
    bs2 = game_state_of(sess2)
    assert bs2.hp.value is None, \
        '② GameState 从未读过 → 处置②保持 None(session 暖启动值不入,禁猜)'

    # 真值帧到达 → observation 转正
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='', node_t=None:
                        (76, True), raising=False)
    cw_observation.read_game_state(_feed_ctx(sess2), None, phase='prep_clean')
    assert bs2.hp.value == 76 and bs2.hp.source == 'observation'

    # 再失读 → 处置①carried 沿用上次好值(禁清成 None)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='', node_t=None:
                        (76, False), raising=False)
    cw_observation.read_game_state(_feed_ctx(sess2), None, phase='prep_clean')
    assert bs2.hp.value == 76, '硬边界:正式值永不清成 None'
    assert bs2.hp.source == 'carried'
    assert (bs2.hp.evidence or '').startswith('carried:')


def test_observation_feed_shop_open_reads_refresh_price(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """任务书件 6:商店开态帧刷新费通道(ADR-0622)——现场读数写 shop_refresh_cost
    (observation);识别失败 = carried(禁兜底改值,§3.3.4);hp 写入闸:
    商店开态 spec 无 'hp' → 假值防线(PHASE_FIELD_SPEC 门)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    from sr_od.application.currency_war.obs import cw_observation as obs

    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    monkeypatch.setattr(obs, 'read_gold_settled', lambda ctx, screen: 20,
                        raising=False)
    monkeypatch.setattr(obs, 'read_phase_round', lambda ctx, screen: (1, 5),
                        raising=False)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='', node_t=None:
                        (82, False), raising=False)
    monkeypatch.setattr(obs, 'read_level_up_cost', lambda ctx, screen: 4,
                        raising=False)
    monkeypatch.setattr(obs, 'board_from_tracked', lambda tracked: None,
                        raising=False)
    monkeypatch.setattr(obs, '_board_pairs',
                        lambda ctx, screen, max_count=9, expected=None:
                        ({}, False), raising=False)
    # 改写依据:read_shop_cards 签名演进加 full_ocr 预解析透传参
    # (cw_observation.read_shop_cards),桩随签名对齐;桩返回值语义不变。
    monkeypatch.setattr(obs, 'read_shop_cards',
                        lambda ctx, screen, full_ocr=None: [],
                        raising=False)
    monkeypatch.setattr(obs, 'read_refresh_probs', lambda ctx, screen: None,
                        raising=False)
    monkeypatch.setattr('sr_od.application.currency_war.obs.cw_shop_refresh_obs'
                        '.read_shop_refresh_price',
                        lambda ctx, screen: 2, raising=False)

    obs.read_game_state(_feed_ctx(sess), None, phase='prep_shop_open')

    gs = game_state_of(sess)
    assert gs.shop_refresh_cost.value == 2
    assert gs.shop_refresh_cost.source == 'observation'

    # 识别失败:carried 保上次值,禁兜底(§3.3.4 None≠0)
    monkeypatch.setattr('sr_od.application.currency_war.obs.cw_shop_refresh_obs'
                        '.read_shop_refresh_price',
                        lambda ctx, screen: None, raising=False)
    obs.read_game_state(_feed_ctx(sess), None, phase='prep_shop_open')
    bs2 = game_state_of(sess)
    assert bs2.shop_refresh_cost.value == 2
    assert bs2.shop_refresh_cost.source == 'carried'


def test_observation_feed_battle_frame_kind_inherits(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """P1-1:battle_or_transit 帧 spec 无 node_type → kind 禁合成 'prep'
    占位假值——从 gs.node 现值继承合成新键(plane/round 真读更新),
    evidence 标继承;无现值且未读 → node 不写保持 None(禁猜)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    from sr_od.application.currency_war.obs import cw_observation as obs

    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    monkeypatch.setattr(obs, 'read_phase_round', lambda ctx, screen: (1, 9),
                        raising=False)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='', node_t=None:
                        (None, False), raising=False)

    # 无现值且未读:battle 帧 node 不写(占位 'prep' 已裁撤)
    obs.read_game_state(_feed_ctx(sess), None, phase='battle_or_transit')
    gs = game_state_of(sess)
    assert gs.node.value is None, 'kind 未读∧无现值 → node 不写(禁猜)'

    # 有现值(boss):继承 kind 合成新键,evidence 标继承
    gs.observe(gs.node, NodeKey(plane=1, round_num=8, kind='boss'),
               sig=_sig())
    obs.read_game_state(_feed_ctx(sess), None, phase='battle_or_transit')
    node = gs.node.value
    assert node is not None and node.kind == 'boss', \
        'kind 未读帧继承现值,禁覆成占位假值(P1-1)'
    assert node.round_num == 9, 'plane/round 真读照常更新'
    assert gs.node.evidence == 'kind_inherited'

    # node_type 真读帧(pre_clean):kind 用真读值,无继承标记
    _patch_clean_readers(monkeypatch)
    obs.read_game_state(_feed_ctx(sess), None, phase='prep_clean')
    assert gs.node.value.kind == 'battle'
    assert gs.node.evidence is None, '真读帧无继承标记'


def test_observation_feed_carries_screen_name_and_precise_exempt(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """漏斗画面名贯通锁(迭代 2026-09-16-unified-obs-reconcile):主喂入口
    read_game_state(screen_name=...) 观察侧 sig 带画面名 → 金字段失配行
    screen 在场(非 None),精确豁免键 (画面, gold, 写端前缀) 可命中。
    screen_name 缺省 None 形态 = 现状测试不变(sig.screen=None 仅通配可豁免)。"""
    from sr_od.application.currency_war.kernel import (
        cw_mismatch_policy as _policy,
    )
    from sr_od.application.currency_war.obs import cw_observation

    _patch_clean_readers(monkeypatch)   # 金真读桩 = 20

    def _sess_with_logic_gold() -> tuple[SimpleNamespace, object]:
        sess_ = SimpleNamespace(last_streak=0, active_strategies=[])
        gs_ = game_state_of(sess_)
        gs_.write_logic(gs_.gold, 17, produced_by='TestSigWriter',
                        evidence='free_refresh@p1-r4', sig=_lsig())
        return sess_, gs_

    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        sess, _gs = _sess_with_logic_gold()
        cw_observation.read_game_state(_feed_ctx(sess), None,
                                       phase='prep_clean',
                                       screen_name='货币战争-备战')
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    gold_rows = [r for r in rows if r['field'] == 'gold']
    assert len(gold_rows) == 1, '逻辑金 17 vs 真读 20 = 恰一失配行'
    assert gold_rows[0]['screen'] == '货币战争-备战', \
        '漏斗观察侧 sig.screen 贯通到失配行(精确键前提)'
    assert gold_rows[0]['actor'] == 'cw_observation'
    assert gold_rows[0]['logic_evidence'] == 'free_refresh@p1-r4'

    # 精确豁免键命中:同画面同字段同写端前缀 → exempt 行
    monkeypatch.setattr(_policy, 'EXEMPT_REGISTRY', {
        ('货币战争-备战', 'gold'): (_ExemptEntry(
            screen='货币战争-备战', field='gold',
            logic_evidence='free_refresh@', reason='测试豁免'),),
    })
    rows2: list[dict] = []
    set_defect_sink(rows2.append)
    try:
        sess2, _bs2 = _sess_with_logic_gold()
        cw_observation.read_game_state(_feed_ctx(sess2), None,
                                       phase='prep_clean',
                                       screen_name='货币战争-备战')
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    gold_rows2 = [r for r in rows2 if r['field'] == 'gold']
    assert len(gold_rows2) == 1 \
        and gold_rows2[0]['kind'] == 'exempt_mismatch', \
        '豁免注册表按画面键命中漏斗失配(键坐标系 = 观察侧 sig.screen)'


# (test_consume_defect_sink_drains 已并入上方
#  test_observe_over_logic_mismatch_defect_row_and_sink_drain 的 drain 腿。)


# ============================================================ §8.7 批次三
# 策略器状态归位(原独立批次文件按主题文件纪律归并入本文件;断言体零语义
# 改动)。锁面 = §8.7 批次三现存件:§5.1 effect_inventory 挂点机制(登记/
# 节点 tick 与 advance/计数 bump/到期尾款返回面)+ §3.2.19 跳过递减/
# §5.1 账本载体归一(挂点
# 写点落在 GameState.effects 单例)。断言全部按设计语义写,与上方批次一/
# 消费批锁面不重复。


# ============================================================ §5.1 载体归一
# 效果账本单实例 = GameState.effects;session 无独立字段(兼容读口已撤)


def test_level_up_and_battle_end_hooks_write_unified_ledger() -> None:
    """升级标记(prep_actions)与结算(battle_wait)两挂点直写 GameState
    正本:game_state_of(sess).effects 落单一实例,session 上无旁路字段。"""
    sess = StrategySession()
    game_state_of(sess).effects.on_level_up()
    assert game_state_of(sess).effects.event_count('_event_level_up') == 1, \
        '挂点写点落在单一实例'
    game_state_of(sess).effects.on_battle_end()
    assert game_state_of(sess).effects.event_count('_event_battle_end') == 1, \
        '挂点写点落在单一实例'
    assert not hasattr(sess, 'effect_inventory'), \
        'session 兼容读口已撤,禁残留旁路字段'


# ============================================================ §5.1 挂点机制
# register 播种 / tick 去重与到期 / consume_use / bump_key


def test_register_seeds_remaining_uses_and_nodes() -> None:
    """§3.2.19/§5.1:登记播种双轨——次数类(duration_uses>0)播
    remaining_uses(免战牌=2),N_NODES 播 remaining_nodes(躺平=3)。"""
    inv = ActiveEffectInventory()
    e_skip = inv.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_t=5)
    assert e_skip.remaining_uses == 2 and e_skip.remaining_nodes is None
    e_lie = inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_t=5)
    assert e_lie.remaining_nodes == 3 and e_lie.remaining_uses is None


def test_node_tick_and_advance_dedup_guard_expiry() -> None:
    """§5.1 节点推进(tick_node/advance_node 双口):同节点去重(每备战环
    采样只推进一次)/登记当节点不推进(「持续 N 个节点」= 登记节点的后继
    N 节点,实采定谳前保守读)/归零移除并返回到期条目(尾款触发面);
    advance_node 的 advanced 位 = 余额累加闸(同节点重复推进 advanced=
    False,每节点恰一次)。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_t=5)
    assert inv.tick_node(5) == [], '登记当节点不推进(吞节点即错口径)'
    assert inv.tick_node(5) == [], '同节点去重:幂等'
    assert inv.first('102001').remaining_nodes == 3
    assert inv.tick_node(6) == [] and inv.first('102001').remaining_nodes == 2
    assert inv.tick_node(6) == [], '同节点去重'
    inv.tick_node(7)
    expired = inv.tick_node(8)
    assert [e.spec.id for e in expired] == ['102001'], '归零移除+到期返回'
    assert inv.first('102001') is None
    assert inv.tick_node(8) == [], '空清单 tick 幂等'
    # advance_node 双返回口:advanced 位 = 余额累加闸门
    inv2 = ActiveEffectInventory()
    inv2.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_t=5)
    advanced, expired1 = inv2.advance_node(6)
    assert advanced is True and expired1 == []
    advanced2, _ = inv2.advance_node(6)
    assert advanced2 is False, '同节点去重位 = 余额累加闸门'
    inv2.advance_node(7)
    advanced3, expired3 = inv2.advance_node(8)
    assert advanced3 is True and [e.spec.id for e in expired3] == ['102001'], \
        '三次有效推进(6/7/8)后到期移除'


# ============================================================ B1 账本→字段桥
# §5.1/§3.3.5-6/§3.2.5:burst(登记一次性)/per_node(每节点)/容量投影三形态


@pytest.mark.parametrize('case', ['burst-once-grant',
                                  'per-node-once-per-node'])
def test_effect_refresh_balance_grant_forms(case: str) -> None:
    """B1 账本→字段桥·免费刷余额授权两形态一锁(参数化并一):
    - burst:登记时点把 payload.free_refresh_burst 一次性累加进余额
      (固定理财即时段=2 活载体);零额度 payload(免战牌)= no-op。
      「一次性」由调用点唯一性承载(登记挂点,接线锁辖),函数本体不加
      去重;
    - per_node:节点边界一次,把在场条目声明的每节点额度累加(双手狸
      free_refresh_on_node_enter=2 活载体);同节点重复挂点采样不双计
      (闸 = advance_node advanced 位)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if case == 'burst-once-grant':
        apply_effect_burst_grant(gs, STRATEGY_EFFECTS['固定理财'],
                                 frame='p1-r2')
        assert gs.free_refresh_balance.value == 2
        assert gs.free_refresh_balance.evidence == 'effect_burst@p1-r2'
        apply_effect_burst_grant(gs, STRATEGY_EFFECTS['免战牌'])
        assert gs.free_refresh_balance.value == 2, '零额度 = no-op'
        return
    gs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                 acquired_t=5)
    adv, _ex = gs.effects.advance_node(6)
    if adv:
        grant_effect_node_refresh_balance(gs, frame='p1-r6')
    assert gs.free_refresh_balance.value == 2
    # 同节点重复采样(挂点每备战环一次):去重位关闭累加
    adv2, _ex2 = gs.effects.advance_node(6)
    if adv2:
        grant_effect_node_refresh_balance(gs, frame='p1-r6')
    assert gs.free_refresh_balance.value == 2, '同节点禁双计'
    adv3, _ex3 = gs.effects.advance_node(7)
    if adv3:
        grant_effect_node_refresh_balance(gs, frame='p1-r7')
    assert gs.free_refresh_balance.value == 4, '下一节点再 +2'


def test_capacity_projection_activates_and_recovers() -> None:
    """桥·容量投影(§3.2.5):在册容量声明 payload.capacity_limit=3 → bench
    容量投影 3;条目到期移除 → 回默认 9;bench 未观察(None)= 无容器跳过;
    零声明条目 → 恒默认 9(幂等,当前注册表活载体为零,行为与接线前
    逐位一致)。声明契约 = payload 鸭子属性 capacity_limit(注册表建模批
    候选,§5.2 缺口;测试以鸭子桩承载声明,机制先于数据)。"""
    from types import SimpleNamespace as _NS

    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        DurationKind,
        DutyFlags,
        EffectKind,
        EffectSpec,
        TriggerKind,
    )

    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    # bench 未观察:无容器可写,投影跳过
    inv = gs.effects
    inv.register_strategy(EffectSpec(
        id='test_cap', name='容量测试桩', trigger=TriggerKind.CONDITIONAL,
        duration=DurationKind.N_NODES, category=EffectKind.ECONOMY,
        payload=_NS(capacity_limit=3), duties=DutyFlags(track=True),
        duration_nodes=2), acquired_t=5)
    project_effect_capacity(gs)
    assert gs.bench.value is None, 'bench 未观察 = 无容器,不造帧'
    # 观察(默认容量 9)→ 投影 3
    slots = [BenchSlot(kind='unit')] + [BenchSlot(kind='empty')] * 8
    gs.observe(gs.bench, BenchView(slots=slots, capacity=BENCH_CAPACITY_DEFAULT), sig=_sig())
    project_effect_capacity(gs)
    assert gs.bench.value.capacity == 3, '激活期容量 = 声明值'
    assert gs.bench.value.slots[0].kind == 'unit', '槽位表原样保留'
    assert gs.bench.source == 'logic' \
        and gs.bench.evidence == 'capacity_project'
    # 条目到期(N_NODES=2,两次推进)→ 移除后投影回默认 9
    inv.advance_node(6)
    inv.advance_node(7)
    project_effect_capacity(gs)
    assert gs.bench.value.capacity == BENCH_CAPACITY_DEFAULT == 9, \
        '到期自动回 9(§3.2.5)'


def test_consume_use_decrements_removes_and_tolerates_missing() -> None:
    """§3.2.19 跳过递减:落地一次 −1;归零移除;无在册条目返 None 零动作
    (递减挂点与登记挂点解耦,不炸执行链)。"""
    inv = ActiveEffectInventory()
    assert inv.consume_use('151301') is None, '未登记 = None 零动作'
    inv.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_t=3)
    assert inv.consume_use('151301') == 1
    assert inv.first('151301') is not None, '尚有余量不移除'
    assert inv.consume_use('151301') == 0
    assert inv.first('151301') is None, '用尽 = 效果离场'
    assert inv.consume_use('151301') is None


def test_bump_key_advances_only_tracked_entries() -> None:
    """§5.1 计数 bump:动作侧全量推进只辖 duties.track=True 条目(「谁要
    记账」的声明单一源);消费按 (spec_id, key) 隔离读。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['采购专员·金'], acquired_t=1)  # track=True
    inv.register_strategy(STRATEGY_EFFECTS['人力重组'], acquired_t=1)     # predict only
    inv.bump_key(CounterKey.REFRESH)
    inv.bump_key(CounterKey.REFRESH)
    assert inv.counter('201201', CounterKey.REFRESH) == 2
    assert inv.counter('102801', CounterKey.REFRESH) == 0, \
        '未声明记账义务的条目不被推进'


# ============================================================ 挂点接线锁(缓交)
# 原 test_effect_hooks_wired_at_production_sites(§5.1 四挂点+B1 桥两采样点
# 字符串在场断言)本批不收录:分诊=修复需 import 在飞互斥面符号
# (cw_screen_buy_cards 的执行落地 bump、cw_loop 的节点 tick),且本体为
# 源码扫描形态(AGENTS §10.4.4 禁)。挂点接线的行为锁待在飞批落地后按
# 行为锁形态重写,台账见 .debug/progress/2026-09-11-cw-clear-run/reports/
# 分诊报告(易失)。


# ============================================================ 第 15 轮对抗审 C8
# sim 合成口 payload 离屏分支(§2.2 例外:真值缺席 = 结构离屏,禁旧 payload 残留)


def test_synthesis_payload_offscreen_branch() -> None:
    """C8:合成口 shop 真值缺席 = 结构离屏(置 None+left_screen,等价
    leave_screen)——禁旧 shop payload 连旧 evidence 残留(把「不在商店」帧
    误读成「商店仍开着」);encounter/supply 两域 sim 不建模,合成帧恒
    离屏口径;牌面在场帧照常观察落 payload。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    st_shop = CwSimFrame()
    st_shop.shop = [StateShopCard(x=1, name='花火', cost=2, star=1,
                                  cost_source='badge')]
    synthesize_from_game_state(gs, st_shop, at_round='p1-r2')
    # 改写依据:三态定长五槽模型(用户三态裁定 2026-09-13)后 payload
    # 形态 = ShopSlot 包裹,x=1 → 下标 1 content 槽;离屏分支断言不变。
    _slot = gs.shop.value.cards[1] if gs.shop.value is not None else None
    assert _slot is not None and _slot.kind == 'content' \
        and _slot.card is not None and _slot.card.name == '花火'

    # 连续合成帧:真值缺席 → 离屏(旧 payload 不残留)
    st_prep = CwSimFrame()
    synthesize_from_game_state(gs, st_prep, at_round='p1-r3')
    assert gs.shop.value is None, '离屏帧 payload 置 None(禁残留)'
    assert gs.shop.source == 'observation' \
        and gs.shop.evidence == 'left_screen', '结构离屏 = left_screen 标记'
    assert gs.encounter.value is None \
        and gs.encounter.evidence == 'left_screen'
    assert gs.supply.value is None and gs.supply.evidence == 'left_screen'


def test_synthesis_shop_empty_keeps_payload_in_recognition_domain() -> None:
    """识别域(``shop_empty_off_screen=False``,店开相位实机喂入)
    空牌面 = 买空/OCR 失读窗 → 不写保现值(失读窗沿用上一开店牌面),禁按
    离屏清 None。实证 = 2026-09-13 实机局 run_20260913_085025:买空店重进
    被真值口径清 None,``decide_shop_action`` 在屏前置 shop=None 契约崩
    循环(journal 同帧 current_screen 开商店 ∧ prov.shop left_screen)。
    真值域缺省分支的同帧行为 = test_synthesis_payload_offscreen_branch
    (离屏锁不变,两域分叉 = 合成口 docstring「payload 域离屏分支」申报)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    st_shop = CwSimFrame()
    st_shop.shop = [StateShopCard(x=1, name='花火', cost=2, star=1,
                                  cost_source='badge')]
    synthesize_from_game_state(gs, st_shop, at_round='p1-r2')
    assert gs.shop.value is not None

    # 买空店重进帧:shop 空表,识别域口径 → 保现值沿用(其余域照常合成)
    st_empty = CwSimFrame()
    synthesize_from_game_state(gs, st_empty, at_round='p1-r2',
                               shop_empty_off_screen=False)
    assert gs.shop.value is not None, '识别域空表 = 失读窗,禁清 None'
    # 改写依据:三态定长五槽模型(用户三态裁定 2026-09-13)后沿用值形态 =
    # ShopSlot 包裹,content 槽紧缩视图语义等价旧紧缩列表读法。
    assert [s.card.name for s in gs.shop.value.cards
            if s.kind == 'content'] == ['花火'], \
        '沿用上一开店牌面(失读窗语义,同观察漏斗「空牌面不写」口径)'
    assert gs.shop.evidence != 'left_screen', '识别域空表非结构离屏'


# ============================================================ §8.7 批次四
# 退役 + relay 空值闸(原独立批次文件按主题文件纪律归并入本文件;断言体
# 零语义改动)。锁面 = §8.7 批次四:
# - relay 会话侧值已确立闸(§2.1:会话载体默认空值 ''/[] 是「未知」非
#   「已知事实」,禁中继成正式值;字符串非空/列表非空才中继)——单元锁 +
#   恢复局场景端到端锁(新 session 空默认不落 GameState、真值后到可落);
#   端到端两锁复用上方观察流域的 _feed_ctx/_patch_clean_readers(镜像字段
#   中继走 feed 尾部公共段,reader 读值与本组断言面无关);
# - 退役载体零残留(AST 级静态锁,标识符面):已退役符号全仓零命中 +
#   记录面(kernel/cw_game_state.py)零 last_state 标识符命中。
# payload 域三域口径的对齐断言在本文件上方(test_leave_screen_payload_only
# 负断言辖 settlement),本节不重复。

#: §2.1 五镜像字段(批次二 feed 中继点;恢复局新 session 停在空默认的面)。
_MIRROR_FIELDS = ('active_strategies', 'active_env', 'plane_bosses',
                  'enemy_affixes', 'selected_difficulty')


# ============================================================ §2.1 relay 空值闸


def test_relay_unit_gate_truth_table() -> None:
    """§2.1 relay 空值闸单元锁(表驱动并一;合并原
    test_relay_rejects_session_empty_defaults /
    test_relay_gate_scope_is_empty_string_and_containers_only /
    test_relay_empty_refusal_does_not_block_late_truth,并自
    test_cw_game_state_consume 移入 test_relay_skips_fields_with_
    official_value;断言腿逐条保留):

    - 空值 = 未知态禁中继:字符串空/空白、列表/元组/字典/集合空 = 会话
      侧值未确立,一律拒写(返回 False,字段保持从未写过,不留来源痕迹);
    - 闸辖域 = 空字符串与空容器(§2.1 词面:字符串非空/列表非空);falsy
      但有语义的标量(如 streak=0 真 0)不受闸辖,禁过度收紧;非空列表
      即确立(结构已知,元素 None = 该位面无身份,§8.4);
    - 拒后真值后到可落(恢复局核心语义):空默认被拒后字段仍是「从未
      写过」——真值后到正常落(logic + session_carrier);「持卡名单 []
      为假事实、拦截后到真值」的缺陷面由本腿钉死;
    - 已有正式值一律跳过:handler 已写的 logic 禁被中继翻成 observation
      (§8.1);observation 同样不翻。"""
    # ① 空默认拒(五镜像整体核:拒写后全部保持从未写过)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert gs.relay(gs.active_env, '', sig=_hsig()) is False
    assert gs.relay(gs.selected_difficulty, '   ', sig=_hsig()) is False, \
        '空白字符串 = 无内容读数,同空域'
    assert gs.relay(gs.active_strategies, [], sig=_hsig()) is False
    assert gs.relay(gs.plane_bosses, (), sig=_hsig()) is False
    assert gs.relay(gs.enemy_affixes, {}, sig=_hsig()) is False
    for name in _MIRROR_FIELDS:
        fld = getattr(gs, name)
        assert fld.value is None, f'空默认禁落 GameState:{name}'
        assert fld.evidence is None, '拒写不留任何来源痕迹'
    # ② 闸辖域表行:falsy 有语义标量放行 / 非空容器确立
    for name, value in (('streak', 0), ('plane_bosses', [None, None, None])):
        gs_scope = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        assert gs_scope.relay(getattr(gs_scope, name), value,
                              sig=_hsig()) is True, \
            f'{name}: 闸只辖空串与空容器'
        # relay 写后 Field 实例被替换(冻结帧替换语义),重读再断言
        fld_scope = getattr(gs_scope, name)
        assert fld_scope.value == value
        assert fld_scope.source == 'logic' \
            and fld_scope.evidence == 'session_carrier'
    # ③ 拒后真值后到可落(§2.1 中继形态)
    assert gs.relay(gs.active_strategies, ['白银投资'], sig=_hsig()) is True
    assert gs.active_strategies.value == ['白银投资']
    assert gs.active_strategies.source == 'logic'
    assert gs.active_strategies.evidence == 'session_carrier'
    assert gs.relay(gs.active_env, '昼之半神概念股', sig=_hsig()) is True
    assert gs.active_env.value == '昼之半神概念股'
    assert gs.active_env.evidence == 'session_carrier'
    # ④ 已有正式值跳过(handler 真写端与观察真值都不被中继翻写)
    gs.write_logic(gs.active_env, '战争边疆',
                   produced_by='CwScreenInvestEnv', sig=_lsig())
    assert gs.relay(gs.active_env, '昼之半神概念股', sig=_hsig()) is False
    assert gs.active_env.value == '战争边疆', 'handler 真写端值保持'
    assert gs.active_env.source == 'logic', '禁把 logic 翻成 observation'
    assert gs.active_env.evidence is None, '真写端 evidence 不被中继污染'
    gs.observe(gs.active_strategies, ['白银投资'], sig=_sig())
    assert gs.relay(gs.active_strategies, [], sig=_hsig()) is False
    assert gs.active_strategies.source == 'observation'


# ============================================================ 恢复局场景端到端


def test_restore_session_empty_refused_then_late_truth_lands(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """§2.1 恢复局场景端到端一锁(两阶段并一;合并原
    test_restore_session_empty_mirrors_not_relayed /
    test_restore_session_late_truth_relay_lands,断言腿逐条保留):

    - 阶段 1(空默认拒):恢复局新 session 五镜像字段停会话默认
      (''/[])→ 生产 feed(read_game_state 观察流)逐帧中继全被空值闸拒,
      GameState 五字段保持 None(未知态不固化成正式值);
    - 阶段 2(真值后到):session 侧被接管协议/事件屏 handler 写入 →
      下一帧中继正常落五镜像(source=logic + evidence=session_carrier)
      ——空默认拒写不拦截后到真值。"""
    from sr_od.application.currency_war.obs import cw_observation

    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    _patch_clean_readers(monkeypatch)
    ctx = _feed_ctx(sess)

    cw_observation.read_game_state(ctx, None, phase='prep_clean')

    gs = game_state_of(sess)
    for name in _MIRROR_FIELDS:
        fld = getattr(gs, name)
        assert fld.value is None, f'恢复局空默认禁中继落记录:{name}'

    # 真值后到(恢复局:简报/事件屏/难度确认屏写端补齐会话侧事实)
    sess.active_strategies = ['白银投资']
    sess.active_env = '昼之半神概念股'
    sess.briefing_bosses = ['首领甲', None, None]
    sess.briefing_affixes = ['正当防卫']
    sess.selected_difficulty = 'A8'
    cw_observation.read_game_state(ctx, None, phase='prep_clean')

    assert gs.active_strategies.value == ['白银投资']
    assert gs.active_env.value == '昼之半神概念股'
    assert gs.plane_bosses.value == ['首领甲', None, None]
    assert gs.enemy_affixes.value == ['正当防卫']
    assert gs.selected_difficulty.value == 'A8'
    for name in _MIRROR_FIELDS:
        fld = getattr(gs, name)
        assert fld.source == 'logic', f'中继形态 logic(§2.1):{name}'
        assert fld.evidence == 'session_carrier', f'中继注记:{name}'


# ==================== 容器视图转换/合成口/ShopCard 映射(自 w5_passthrough 归并) ====================

# deployed_rows_from_obs 分排守卫/unit_rows_to_deployed 旧槽表重建/bench_slots_to_legacy
# 注册表派生阵营/ShopCard 映射单一源往返 + kernel 内零旧类型引用静态锁
# (转换只许在映射函数发生)。断言零改动。
def _mk_legacy_card(x: int, name: str, *, cost: int = 1, star: int = 1,
                    faction: str = '仙舟',
                    cost_source: str = 'badge', merge_preview: int = 0,
                    slot: int = 0):
    from sr_od.application.currency_war.kernel.cw_vocab import ShopCard
    return ShopCard(x=x, faction=faction, name=name, cost=cost, star=star,
                    merge_preview=merge_preview, cost_source=cost_source,
                    slot=slot)


def test_container_seat_view_conversions() -> None:
    """容器席位转换往返一锁(三合一;合并原
    test_deployed_rows_from_obs_splits_rows_and_guards_empty /
    test_unit_rows_to_deployed_rebuilds_legacy_slot_table /
    test_bench_slots_to_legacy_derives_faction_from_registry,断言腿
    逐条保留):

    - 分排(SIFT 读链 → front/back):分排按 position_pref、行内 1 基
      slot 直传;空集/全无身份 = 失读返 None(P2-1 同款守卫,禁「全场
      无人」假观察);
    - 席位重建(容器席位 → 旧定长槽表,ADR-0392 0 基 0-3 前/4-9 后):
      视图收编后消费形状零变化(None 填充,行内 1 基 slot = 旧下标换算);
    - bench 槽表(BenchView → 旧槽表):阵营不入容器(§3.2.3),查角色
      注册表派生(识别链同源 get_char);槽位两端同构 1:1。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        bench_view_of_slots,
    )
    # —— 分排 + 失读守卫 ——
    assert deployed_rows_from_obs([]) is None
    assert deployed_rows_from_obs([BenchChar(slot=0, char_id='')]) is None
    front, back = deployed_rows_from_obs([
        BenchChar(slot=2, char_id='希儿', star=2, position_pref='front'),
        BenchChar(slot=1, char_id='景元', star=1, position_pref='back'),
        BenchChar(slot=3, char_id='花火', star=1, position_pref='back'),
    ])
    assert [(u.char_id, u.slot) for u in front] == [('希儿', 2)]
    assert [(u.char_id, u.slot) for u in back] == [('景元', 1), ('花火', 3)]
    # —— deployed 旧槽表重建(原 2 件帧:希儿前/景元后)——
    front2, back2 = deployed_rows_from_obs([
        BenchChar(slot=2, char_id='希儿', star=2, position_pref='front'),
        BenchChar(slot=1, char_id='景元', star=1, position_pref='back'),
    ])
    table = unit_rows_to_deployed(front2, back2)
    assert len(table) == 10
    assert table[1] is not None and table[1].char_id == '希儿' \
        and table[1].position_pref == 'front'
    assert table[4] is not None and table[4].char_id == '景元' \
        and table[4].position_pref == 'back'
    assert all(table[i] is None for i in (0, 2, 3, 5, 6, 7, 8, 9))
    # —— bench 槽表(阵营自注册表派生)——
    view = bench_view_of_slots([BenchChar(slot=1, char_id='花火', star=2),
                                None])
    btable = bench_slots_to_legacy(view)
    assert btable[0] is not None and btable[0].char_id == '花火' \
        and btable[0].star == 2 and btable[0].slot == 1
    assert btable[0].faction != '?', '阵营自注册表派生(非容器存储)'
    assert btable[1] is None and len(btable) == 9


def test_shop_card_mapping_roundtrip_and_frame_alignment() -> None:
    """映射单一源往返:旧→容器保五记录字段+槽号;容器→旧 x/merge_preview
    同帧对齐透传、slot 自容器透传,失配窗置 0(执行/读取器域引导窗,
    申报见映射函数)。"""
    legacy = _mk_legacy_card(300, '希儿', cost=1, star=2,
                             cost_source='roster_fallback',
                             merge_preview=2, slot=3)
    container = shop_card_to_container(legacy)
    assert (container.name, container.faction, container.cost,
            container.star, container.cost_source, container.slot) == \
        ('希儿', '仙舟', 1, 2, 'roster_fallback', 3), \
        '五记录字段原值透传不折叠(cost_source 证据分级禁丢);物理槽号透传'
    assert not hasattr(container, 'x') and not hasattr(container,
                                                       'merge_preview')
    back = shop_cards_to_legacy([container], frame_cards=[legacy])
    assert (back[0].x, back[0].merge_preview) == (300, 2), '同帧下标对齐'
    assert back[0].slot == 3, '槽号自容器透传(点击取坐标依据,不按下标)'
    back_misaligned = shop_cards_to_legacy([container],
                                           frame_cards=[legacy, legacy])
    assert (back_misaligned[0].x, back_misaligned[0].merge_preview) == (0, 0), \
        '长度失配 = 失配窗置缺省(禁错位对齐)'



