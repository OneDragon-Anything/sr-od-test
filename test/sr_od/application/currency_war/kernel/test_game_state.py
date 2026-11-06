"""GameState 迁移回归测试(迁移批次一;设计正本 = docs/develop/sr_od/application/currency_war/
容器数据结构设计,下称「设计」;正本 = game_state/fields.md)。

测试面 = 写入口两态制与构造守卫(§2.1-§2.4/§8.6-5)+ 派生不存储
(§8.6-4 续)+ 观察流接线与 hp 失读统一口径 + 心跳哨兵(§2.4 关键
结构 2)+ sim 合成口箱占席语义(§3.2.5;迁移批次一任务书第 7 件)
+ 设计 §8.7 批次三(挂点机制/B1 桥)与批次四(退役 + relay 空值闸)
两组测试。机制主题归并(禁批次命名):本文件 = GameState 容器机制正名
主题文件,消费切换批(刷新计数/结算覆盖/合成升星判定/streak 解析/
备战席读链)、容器合同(六通道/版本流水/快照/画面上下文/渠道签名
封闭集)、开局种子底座与锚定标志、deployed 视图桥与快照迁移各节按
机制并入(断言体零语义改动)。

退役面:§8.6 差距清单逐条测试(gap3/gap4 组)与 §3 字段语义抽样组已删;
心跳写点序/断流计数两个测试并一,level_up/battle_end 挂点两个测试并一,
tick/advance_node 两个测试并一(并入分支见各测试 docstring)。

合并面(第二刀,断言分支零丢失):bench_free 两形态参数化并一;失配缺陷
台账+sink drain 并一;合成口真值域 on/off 参数化并一;feed 接线+hp 三
分支同帧驱动并一;burst/per_node 授权两形态参数化并一;relay 单元三个测试
表驱动并一;relay 端到端两个测试并一;席位视图转换三个测试并一(ShopCard 映射
单测试独立)。

草板对照物 = .debug/temp/currency_war/record_data_model/board_state.py
(易失产物,不构成出处;出处 = 设计章节号)。
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel import cw_game_state as gs_mod
from sr_od.application.currency_war.kernel.cw_economy import (
    REFRESH_COST_BASE,
    XP_TO_NEXT_LEVEL,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    ActiveEffectInventory,
    CounterKey,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BENCH_CAPACITY_DEFAULT,
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    NodeKey,
    OreSight,
    Unit,
    apply_effect_burst_grant,
    apply_settlement_cover,
    bench_free_slots,
    bench_is_full,
    board_next_tier_of,
    consume_defect_sink,
    deployed_indexed_of_view,
    deployed_rows_of_view,
    deployed_view_of_indexed,
    deployed_view_sequential,
    game_state_of,
    grant_effect_node_refresh_balance,
    prep_anchored_of,
    project_effect_capacity,
    set_defect_sink,
    shop_card_to_container,
    shop_cards_to_legacy,
    write_match_final,
)

# ---- W1 sig 铺满 helper(测试写入口签名必填,ADR-0634;actor 已登记)----
from sr_od.application.currency_war.kernel.cw_game_state import (  # noqa: E402
    ChannelSig as _ChannelSig,
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
from sr_od.application.currency_war.kernel.cw_opening_hp import (
    OPENING_HP_BASE,
)
from sr_od.application.currency_war.kernel.cw_reconcile import (
    reconcile_tracking,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    ShopCard as StateShopCard,
)


def _sig() -> _ChannelSig:
    """渠道①签名(obs 族;观察/沿用/先验/离屏/观察事件)。"""
    return _ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _bslot(slot_no: int, name: str, star: int) -> BenchSlot:
    """备战席占席条目直构(种子容器形状)。"""
    return BenchSlot(kind='unit', unit=Unit(char_id=name, star=star))


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
    """ADR-0651 两态制核心测试(写通道合同正本,全仓唯一份):逻辑推算值经
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
    """§3.2.5 席空数派生两形态一测试(参数化并一):
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
    test_consume_defect_sink_drains,断言分支逐条保留):

    - 失配分支:观察覆盖 logic 值失配 → 失配记入缺陷台账(挂点注入,缺省
      关);观察赢——来源改回 observation。失配 = 推算 bug 留证修码;
      一致反分支 = 投影被实读核实形态,零缺陷行;
    - drain 分支:挂点 = 注入槽模式(缺省关+显式接通;模块级缓冲在 setup
      先清,隔离整条副作用链);consume 供装配点取走行后复位,防跨局
      残留。"""
    # —— 失配分支(失配留证 + 观察赢)——
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
        '行携带观察侧组 id 与逻辑侧写端注记(本分支均无)'
    assert gs.gold.source == 'observation', '观察赢:来源改回 observation'
    assert drained == rows, 'consume 取走行(装配点消费面)'
    assert consume_defect_sink() == [], '消费后复位,防跨局残留'
    # 一致反分支:观察值与 logic 值一致 = 静默核实,不留缺陷行
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
    """失配三分流并一测试(,design §2.3):

    - 真失配分支:缺陷行落盘后安灯钩子同步被调(行同构);sim 前缀两值
      (sim:engine 现役 / sim:synthesized 本迭代并列)→ 不落行不调钩子;
    - 豁免分支:精确键(画面×字段×写端前缀)命中 → exempt_mismatch 行
      (同形状换 kind),无告警面消费、钩子不被调;写端前缀不中 → 真失配
      照落(同字段他写端不被吞);
    - 处置序分支(验收 minor3):sim 证据 + 豁免条目同时命中 → 豁免先行
      落 exempt 行(处置序 = 豁免→sim→真失配,禁 sim 检查提前翻转语义);
      真失配分支 [cw!] 告警面被调、豁免分支不被调(验收 minor2)。"""
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

    # —— 真失配分支:行落盘 + 钩子被调(行同构)+ 覆盖照常 ——
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

    # —— 豁免分支:精确键命中 → exempt 行(钩子不被调);前缀不中 → 真失配 ——
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
    assert bs3.gold.source == 'observation', '豁免分支覆盖照常(观察赢)'

    # —— 处置序分支(验收 minor3):sim 证据 + 豁免条目同击 → 豁免先行 ——
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

    # —— 前缀不中反分支:恢复精确条目注册表,他写端 → 真失配照落 ——
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


def test_write_logic_rand_and_observe_random_outcome(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """逻辑随机态(logic_rand)契约并一测试:写口/观察覆盖差异/消费查询面。

    - 写口分支:write_logic_rand 落 source=logic_rand,策略器立即可读;
      渠道族守卫与 write_logic 同一条(obs 族签名显式炸);prov 快照随写;
    - 观察覆盖分支:差异 = 随机效果落地**预期内非 bug**——只落
      logic_rand_outcome 台账行(无 [cw!] 告警、安灯不触发),覆盖照常
      观察赢;等值观察零新信息不产行;
    - 消费查询分支:logic_rand_fields 列随机态字段、观察后自然移出;
      logic_written_fields(严格对账巡检面)不辖随机态字段。"""
    from sr_od.application.currency_war.kernel import cw_game_state as _gs_mod
    from sr_od.application.currency_war.kernel import (
        cw_mismatch_policy as _policy,
    )

    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    warns: list[tuple] = []
    monkeypatch.setattr(_gs_mod.log, 'warning',
                        lambda *a, **k: warns.append(a))

    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    # 渠道族守卫:随机直写与 write_logic 同族校验,obs 族签名拒绝
    with pytest.raises(ValueError):
        gs.write_logic_rand(gs.gold, 12, produced_by='TestSigWriter',
                            sig=_sig())
    # —— 写口分支 ——
    gs.write_logic_rand(gs.gold, 12, produced_by='TestSigWriter',
                        evidence='ore_rand@p1-r2', sig=_lsig())
    assert gs.gold.source == 'logic_rand' and gs.gold.value == 12, \
        '随机口径直写落 logic_rand 来源,策略器立即可读'
    assert gs.logic_rand_fields() == ['gold'], '随机态字段已登记(消费门查询口)'
    assert gs.gold not in [getattr(gs, n) for n in gs.logic_written_fields()] \
        and 'gold' not in gs.logic_written_fields(), \
        '严格对账巡检面(logic_written_fields)不辖随机态字段'
    snap = gs.full_state_snapshot()
    assert snap['prov']['gold']['source'] == 'logic_rand', \
        'prov 快照随写(遥测面可判读随机口径)'
    # —— 观察覆盖分支:差异 = 预期内,logic_rand_outcome 行,无告警无安灯 ——
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.gold, 25, evidence='prep_gold@p1-r2', sig=_sig())
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert len(rows) == 1 and rows[0]['kind'] == 'logic_rand_outcome', \
        '差异只落随机结果台账行(预期内,不进失配三分流)'
    assert rows[0]['expected'] == 12 and rows[0]['actual'] == 25 \
        and rows[0]['logic_evidence'] == 'ore_rand@p1-r2', \
        '行携带随机口径预期/实读/写端注记(校准遥测面)'
    assert fired == [], '安灯不触发(随机落地非 bug)'
    assert not any('观察覆盖 logic 失配' in str(w) for w in warns), \
        '无 [cw!] 告警面'
    assert gs.gold.source == 'observation' and gs.gold.value == 25, \
        '覆盖照常 = 随机结果采新(观察赢)'
    assert gs.logic_rand_fields() == [], '观察后字段自然移出随机态清单'
    # —— 等值观察反分支:随机口径撞中实读 = 零新信息,不产行 ——
    bs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    bs2.write_logic_rand(bs2.gold, 12, produced_by='TestSigWriter',
                         sig=_lsig())
    rows_eq: list[dict] = []
    set_defect_sink(rows_eq.append)
    try:
        bs2.observe(bs2.gold, 12, sig=_sig())
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert rows_eq == [], '等值观察零新信息不产行(settle_truth 同纪律)'


def test_any_logic_rand_truth_table() -> None:
    """any_logic_rand 污染判定口真值表(logic-rand-sampling 迭代):
    空集 → False;含随机态域 → True;全非随机态 → False;未登记名
    容错跳过不炸。消费面 = 动作上报入口跨动作污染判定(design §2.2 #3)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, 10, sig=_sig())
    gs.write_logic(gs.hp, 80, produced_by='TestSigWriter', sig=_lsig())
    assert gs.any_logic_rand([]) is False, '空集恒 False'
    assert gs.any_logic_rand(['gold', 'hp']) is False, '无随机态 → False'
    gs.write_logic_rand(gs.gold, 12, produced_by='TestSigWriter', sig=_lsig())
    assert gs.any_logic_rand(['gold', 'hp']) is True, '含随机态域 → True'
    assert gs.any_logic_rand(['hp']) is False, '其余域不误报'
    assert gs.any_logic_rand(['nonexistent_field', 'gold']) is True, \
        '未登记名容错跳过,不炸且不遮蔽已登记判定'


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
    """§2.1/§3.2.5 种子真值域 on/off 两形态一测试(参数化并一;载体迁移 =
    benchchar-retirement P5,原合成口 at_round 轮键注记随口退役,证据
    恒种子基串 sim:synthesized——断言值改写逐处申报):
    - truth-on:真值种子 bench 槽位保序(0 基下标 → 1 基物理槽位),
      记录模型不采 sim「箱不占席」内部口径;evidence 恒带
      sim:synthesized 标记;真值记 observation;
    - truth-off:种子声明缺席的字段不写(sim 无识别过程,不存在失读;
      未建模域保持 None 诚实缺位,禁种子合成假值;种子不写节点序——
      节点由观察链派生)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if case == 'truth-on-preserves-bench-slots':
        cw4_gs(gs, gold=20, level=1, hp=80,
               bench=[_bslot(1, '阿格莱雅', 1), None, _bslot(3, '花火', 2)],
               node_fill=False, shop_screen='off')
        view = gs.bench.value
        assert view is not None and view.capacity == 9
        assert [s.kind for s in view.slots] == ['unit', 'empty', 'unit'] \
            + ['empty'] * 6, '槽位保序:种子紧缩/稀疏表 1:1 映射物理槽位'
        assert view.slots[0].unit is not None \
            and view.slots[0].unit.char_id == '阿格莱雅'
        assert gs.gold.value == 20
        # 改写申报:原断言 evidence=='sim:synthesized@p1-r2'(at_round
        # 轮键并入注记,P2-6)随合成口退役;种子证据恒基串。
        assert gs.gold.evidence == 'sim:synthesized', \
            '§2.1:evidence 恒带 sim 真值合成标记'
        assert gs.gold.source == 'observation', 'sim 真值记 observation'
        assert gs.hp.value == 80
        return
    # truth-off:裸种子(仅 gold=0/level=1/back_layout 域照写,其余缺席)
    cw4_gs(gs, gold=0, level=1, hp=None, node_fill=False,
           shop_screen='off')
    assert gs.hp.value is None
    assert gs.node.value is None, \
        'node 缺席种子不合成 kind 占位(P1-1 同型泛化)'
    assert gs.node_pos.value is None, '种子不写节点序(节点由观察链派生)'
    assert gs.gold.value == 0 \
        and gs.gold.evidence == 'sim:synthesized', \
        'gold 真值(缺省 0)种子记 observation'


def test_synthesis_unread_bench_no_clobber() -> None:
    """bench 写门(载体迁移 = benchchar-retirement P5;语义锚:未读域≠
    真空域)。种子对未声明 bench 域整域跳写(bench_unread)——容器内
    备战装配环的真读观察保持原值原版本;可读真值种子照写不回归。
    原防御对象 = 旧合成口无门合成把漏斗真读覆盖成「9 槽全空」假真空
    (实机 2026-09-13 商店段循环崩溃实证),载体随合成口退役,跳写
    语义在种子域纪律层等价存续(防覆盖 = 种子只写声明域)。"""
    sig = _sig()
    # 容器先有漏斗真读(deploy 后留 bench:物理槽 4 一人,1 基槽号信息位)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='empty')] * 3
        + [BenchSlot(kind='unit', unit=Unit(char_id='银枝', star=1))]
        + [BenchSlot(kind='empty')] * 5,
        capacity=BENCH_CAPACITY_DEFAULT), sig=sig)
    bench_field_before = gs.bench   # Field 实例同一性:_swap 写入即换实例
    # 未读 bench 域种子(bench_unread)
    cw4_gs(gs, gold=0, level=1, node_fill=False, shop_screen='off',
           hp=None, bench_unread=True)
    view = gs.bench.value
    assert view is not None and view.slots[3].unit is not None \
        and view.slots[3].unit.char_id == '银枝', \
        '未读 bench 种子跳写:容器内漏斗真读保持原值'
    assert gs.bench is bench_field_before, \
        '跳写 = bench Field 实例不换(其余域照写,版本推进不涉本域)'
    # 可读真值种子照写:域语义不回归
    cw4_gs(gs, gold=0, level=1, node_fill=False, shop_screen='off',
           hp=None, bench=[_bslot(1, '花火', 2)])
    assert gs.bench.value.slots[0].unit is not None \
        and gs.bench.value.slots[0].unit.char_id == '花火', \
        '可读种子照写(真值域语义不变)'


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
    monkeypatch.setattr(obs, 'read_phase_round', lambda ctx, screen, round_caps=None: (1, 4),
                        raising=False)
    monkeypatch.setattr(obs, 'read_hp_opt', lambda ctx, screen: None,
                        raising=False)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='':
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
    monkeypatch.setattr(obs, 'board_from_deployed', lambda tracked: None,
                        raising=False)
    monkeypatch.setattr(obs, 'is_prep_like_frame',
                        lambda ctx, screen: True, raising=False)
    monkeypatch.setattr(obs, '_board_pairs',
                        lambda ctx, screen, max_count=9, expected=None:
                        ({'列车同行': (2, 3)}, True), raising=False)


def test_observation_feed_wiring_and_hp_loss_semantics(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """观察流接线 + hp 失读统一口径同帧驱动一测试(合并原
    test_observation_feed_wires_board_state /
    test_observation_feed_hp_unified_loss_semantics,断言分支逐条保留):

    - 接线分支(任务书件 2):read_game_state 观察流——真读字段进 GameState
      (observation);失读字段走 carried/prior;hp 写入闸:非真读帧不经
      observe 假值入账;
    - hp 三分支(§2.2,任务书件 1 断言面):①字段已有正式值 → 失读写
      carried(沿用+来源帧标注);②字段从未读过 → 保持 None(机制性
      None,session 外源值禁猜入);真值帧 → observation 转正。"""
    from sr_od.application.currency_war.obs import cw_observation

    # —— 接线分支:干净 prep_clean 帧,真读值进容器,hp 开局先验形态 ——
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

    # —— hp 三分支(独立 session;同帧驱动,换 reconcile 读数)——
    # 终态契约 §A:session 暖启动真值(last_hp_real)不再抑制先验——
    # prior = 难度表值(source='prior',fail-closed 非真读),对任何未读
    # 容器诚实落账;「禁猜」语义由 trusted 位承载(prior ⇒ False)。
    from sr_od.application.currency_war.kernel import cw_reconcile

    sess2 = SimpleNamespace(last_streak=0, active_strategies=[],
                            last_hp_real=80, last_hp_real_node=12)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='':
                        (80, False), raising=False)
    cw_observation.read_game_state(_feed_ctx(sess2), None,
                                   phase='prep_clean')
    bs2 = game_state_of(sess2)
    assert bs2.hp.value == 80 and bs2.hp.source == 'prior', \
        '② 读不到 → 难度表先验 prior 落账(fail-closed,非真读;终态契约 §A)'

    # 真值帧到达 → observation 转正
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='':
                        (76, True), raising=False)
    cw_observation.read_game_state(_feed_ctx(sess2), None, phase='prep_clean')
    assert bs2.hp.value == 76 and bs2.hp.source == 'observation'

    # 再失读(读不到,先验已在前帧落账)→ 处置①carried 沿用上次好值
    #(禁清成 None;终态契约 §A:(值,False) 拒信态已随守卫退役——miss 恒
    # (先验或 None, False),沿用走 gs.carry)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='':
                        (None, False), raising=False)
    cw_observation.read_game_state(_feed_ctx(sess2), None, phase='prep_clean')
    assert bs2.hp.value == 76, '硬边界:正式值永不清成 None(沿用上一真值 76)'
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
    monkeypatch.setattr(obs, 'read_phase_round', lambda ctx, screen, round_caps=None: (1, 5),
                        raising=False)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='':
                        (82, False), raising=False)
    monkeypatch.setattr(obs, 'read_level_up_cost', lambda ctx, screen: 4,
                        raising=False)
    monkeypatch.setattr(obs, 'board_from_deployed', lambda tracked: None,
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
    monkeypatch.setattr(obs, 'read_phase_round', lambda ctx, screen, round_caps=None: (1, 9),
                        raising=False)
    monkeypatch.setattr(cw_reconcile, 'reconcile_hp',
                        lambda sess_, opt, screen, source='':
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
    """漏斗画面名贯通测试():主喂入口
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
#  test_observe_over_logic_mismatch_defect_row_and_sink_drain 的 drain 分支。)


# ============================================================ §8.7 批次三
# 策略器状态归位(原独立批次文件按主题文件纪律归并入本文件;断言体零语义
# 改动)。测试面 = §8.7 批次三现存件:§5.1 effect_inventory 挂点机制(登记/
# 节点 tick 与 advance/计数 bump/到期尾款返回面)+ §3.2.19 跳过递减/
# §5.1 账本载体归一(挂点
# 写点落在 GameState.effects 单例)。断言全部按设计语义写,与上方批次一/
# 消费批测试面不重复。


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
    e_skip = inv.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_key=(1, 5))
    assert e_skip.remaining_uses == 2 and e_skip.remaining_nodes is None
    e_lie = inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_key=(1, 5))
    assert e_lie.remaining_nodes == 3 and e_lie.remaining_uses is None


def test_node_tick_and_advance_dedup_guard_expiry() -> None:
    """§5.1 节点推进(tick_node/advance_node 双口):同节点去重(每备战环
    采样只推进一次)/登记当节点不推进(「持续 N 个节点」= 登记节点的后继
    N 节点,实采定谳前保守读)/归零移除并返回到期条目(尾款触发面);
    advance_node 的 advanced 位 = 余额累加闸(同节点重复推进 advanced=
    False,每节点恰一次)。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_key=(1, 5))
    assert inv.tick_node((1, 5)) == [], '登记当节点不推进(吞节点即错口径)'
    assert inv.tick_node((1, 5)) == [], '同节点去重:幂等'
    assert inv.first('102001').remaining_nodes == 3
    assert inv.tick_node((1, 6)) == [] and inv.first('102001').remaining_nodes == 2
    assert inv.tick_node((1, 6)) == [], '同节点去重'
    inv.tick_node((1, 7))
    expired = inv.tick_node((1, 8))
    assert [e.spec.id for e in expired] == ['102001'], '归零移除+到期返回'
    assert inv.first('102001') is None
    assert inv.tick_node((1, 8)) == [], '空清单 tick 幂等'
    # advance_node 双返回口:advanced 位 = 余额累加闸门
    inv2 = ActiveEffectInventory()
    inv2.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_key=(1, 5))
    advanced, expired1 = inv2.advance_node((1, 6))
    assert advanced is True and expired1 == []
    advanced2, _ = inv2.advance_node((1, 6))
    assert advanced2 is False, '同节点去重位 = 余额累加闸门'
    inv2.advance_node((1, 7))
    advanced3, expired3 = inv2.advance_node((1, 8))
    assert advanced3 is True and [e.spec.id for e in expired3] == ['102001'], \
        '三次有效推进(6/7/8)后到期移除'


# ============================================================ B1 账本→字段桥
# §5.1/§3.3.5-6/§3.2.5:burst(登记一次性)/per_node(每节点)/容量投影三形态


@pytest.mark.parametrize('case', ['burst-once-grant',
                                  'per-node-once-per-node'])
def test_effect_refresh_balance_grant_forms(case: str) -> None:
    """B1 桥·免费刷发放两形态一测试(参数化并一;2026-09-21 Field 化:免费
    次数升格容器字段 ``gs.free_refresh_left``,两桥 write_logic 同格登记,
    None 基 = 0 起算):
    - burst:登记时点把 payload.free_refresh_burst 一次性累加进 Field
      (固定理财即时段=2 活载体);零额度 payload(免战牌)= no-op 零行。
      「一次性」由调用点唯一性承载(登记挂点,接线测试辖),函数本体不加
      去重;
    - per_node:节点边界一次,把在场条目声明的每节点额度累加进 Field
      (双手狸 free_refresh_on_node_enter=2 活载体);同节点重复挂点采样
      不双计(闸 = advance_node advanced 位)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if case == 'burst-once-grant':
        assert gs.free_refresh_left.value is None, '未发放 = 未写(None 基)'
        apply_effect_burst_grant(gs, STRATEGY_EFFECTS['固定理财'],
                                 frame='p1-r2')
        assert gs.free_refresh_left.value == 2, 'None 基 = 0 起算'
        assert gs.free_refresh_left.source == 'logic'
        assert gs.free_refresh_left.evidence == 'effect_burst@p1-r2'
        apply_effect_burst_grant(gs, STRATEGY_EFFECTS['免战牌'])
        assert gs.free_refresh_left.value == 2, '零额度 = no-op 零行'
        return
    gs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                 acquired_key=(1, 5))
    adv, _ex = gs.effects.advance_node((1, 6))
    if adv:
        grant_effect_node_refresh_balance(gs, frame='p1-r6')
    assert gs.free_refresh_left.value == 2, 'None 基 = 0 起算'
    # 同节点重复采样(挂点每备战环一次):去重位关闭累加
    adv2, _ex2 = gs.effects.advance_node((1, 6))
    if adv2:
        grant_effect_node_refresh_balance(gs, frame='p1-r6')
    assert gs.free_refresh_left.value == 2, '同节点禁双计'
    adv3, _ex3 = gs.effects.advance_node((1, 7))
    if adv3:
        grant_effect_node_refresh_balance(gs, frame='p1-r7')
    assert gs.free_refresh_left.value == 4, '下一节点再 +2'


def test_gas_station_pick_node_grant_matches_official_text() -> None:
    """拿卡登记期核查测试·加油站(a 组,行为结论单一源 =
    docs/game/currency_war/research/per_node_pick_node_grant.md):官方文
    「现在及每次进入新节点时获得1次免费刷新」——拿卡当节点即享:
    - 本节点边界推进先于拿卡(终结动作上报时序),登记前零发放;
    - 拿卡登记期 burst +1(「现在」分支,apply_effect_burst_grant 按 payload);
    - 拿卡节点边界去重(已推进过)不重复发 per_node;
    - 下一节点边界 per_node +1(「每次进入新节点」分支)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.effects.advance_node((1, 2))   # 本节点边界已在拿卡前推进(拿卡晚于边界)
    grant_effect_node_refresh_balance(gs, frame='p1-r2')
    assert gs.free_refresh_left.value is None, '效果登记前边界零发放(零行)'
    apply_effect_burst_grant(gs, STRATEGY_EFFECTS['加油站'], frame='p1-r2')
    gs.effects.register_strategy(STRATEGY_EFFECTS['加油站'], acquired_key=(1, 2))
    assert gs.free_refresh_left.value == 1, '拿卡当节点「现在」分支即发'
    adv_same, _ex = gs.effects.advance_node((1, 2))
    if adv_same:
        grant_effect_node_refresh_balance(gs, frame='p1-r2')
    assert gs.free_refresh_left.value == 1, '拿卡节点边界去重不补发'
    adv_next, _ex2 = gs.effects.advance_node((1, 3))
    assert adv_next is True
    grant_effect_node_refresh_balance(gs, frame='p1-r3')
    assert gs.free_refresh_left.value == 2, '下一节点「每次进入新节点」分支 +1'


def test_per_node_family_without_now_clause_no_pick_grant() -> None:
    """拿卡登记期核查测试·(b) 组(结论单一源 =
    docs/game/currency_war/research/per_node_pick_node_grant.md):官方文无
    「现在/立刻」立即分支的三张(搜打撤/双手狸开键盘!/本金充裕+)payload
    不得携带登记期 burst 额度——拿卡当节点不发放,首发放次节点起。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_ECONOMY,
    )
    assert STRATEGY_ECONOMY['搜打撤'].free_refresh_burst == 0
    assert getattr(STRATEGY_EFFECTS['双手狸开键盘！'].payload,
                   'free_refresh_burst', 0) == 0
    assert STRATEGY_ECONOMY['本金充裕'].free_refresh_burst == 0
    assert STRATEGY_ECONOMY['本金充裕+'].free_refresh_burst == 0
    # 已登记代表(双手狸):登记期零发放,首发放 = 下一节点边界 +2。
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                 acquired_key=(1, 2))
    apply_effect_burst_grant(gs, STRATEGY_EFFECTS['双手狸开键盘！'])
    assert gs.free_refresh_left.value is None, '无立即分支 = 登记期零发放(零行)'
    adv_next, _ex = gs.effects.advance_node((1, 3))
    assert adv_next is True
    grant_effect_node_refresh_balance(gs, frame='p1-r3')
    assert gs.free_refresh_left.value == 2, '首发放 = 下一节点 +2'


def test_free_lunch_ledger_zero_per_node_grant() -> None:
    """免费午餐 per_node 负向(T-88 设计 §4 锁 2):仅持免费午餐的账本
    节点边界零授予——EconomyEffect 纯 burst 一条效果条目(free_refresh_per_node/
    条件三元组/BattlefieldEffect 载体字段全缺省 0,桥鸭子读缺省),桥零
    授予跳写,free_refresh_left 保持未写(None 基零行);burst 腿归登记
    挂点,与本桥无关。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.effects.register_strategy(STRATEGY_EFFECTS['免费午餐'],
                                 acquired_key=(1, 2))
    adv, _ex = gs.effects.advance_node((1, 3))
    assert adv is True
    grant_effect_node_refresh_balance(gs, frame='p1-r3')
    assert gs.free_refresh_left.value is None, '纯 burst 卡节点边界零授予(零行)'


def test_deposit_return_none_conditional_zero_grant() -> None:
    """存款回报保守零授予(T-92 设计 §4 锁 3):直构容器不跑种子
    (prev_node_spent 未写 = None)→ 桥对存款回报条目零授予——禁猜口径
    (本金充裕金 None 同款;None = 条件不可评估,非「未花费」)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert gs.prev_node_spent.value is None, '直构容器不跑种子(前置)'
    gs.effects.register_strategy(STRATEGY_EFFECTS['存款回报'],
                                 acquired_key=(1, 2))
    adv, _ex = gs.effects.advance_node((1, 3))
    assert adv is True
    grant_effect_node_refresh_balance(gs, frame='p1-r3')
    assert gs.free_refresh_left.value is None, 'None = 保守零授予(零行)'


def test_capacity_projection_activates_and_recovers() -> None:
    """桥·容量投影(§3.2.5):已登记容量声明 payload.capacity_limit=3 → bench
    容量投影 3;条目到期移除 → 回默认 9;bench 未观察(None)= 无容器跳过;
    零声明条目 → 恒默认 9(幂等)。声明契约 = payload 鸭子属性
    capacity_limit(机制先于数据,鸭子桩承载)。槽表归一(容量条目入册同批
    义务):9 长全尾空表随投影截断到容量长(容量外全空 = 无损)。"""
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
        duration_nodes=2), acquired_key=(1, 5))
    project_effect_capacity(gs)
    assert gs.bench.value is None, 'bench 未观察 = 无容器,不造帧'
    # 观察(默认容量 9)→ 投影 3,槽表随尾空截断归一到 3 长
    slots = [BenchSlot(kind='unit')] + [BenchSlot(kind='empty')] * 8
    gs.observe(gs.bench, BenchView(slots=slots, capacity=BENCH_CAPACITY_DEFAULT), sig=_sig())
    project_effect_capacity(gs)
    assert gs.bench.value.capacity == 3, '激活期容量 = 声明值'
    assert len(gs.bench.value.slots) == 3, '槽表尾空截断归一(9 长全尾空 → 3)'
    assert gs.bench.value.slots[0].kind == 'unit', '容量内槽位无损保留'
    assert gs.bench.source == 'logic' \
        and gs.bench.evidence == 'capacity_project'
    # 条目到期(N_NODES=2,两次推进)→ 移除后投影回默认 9
    inv.advance_node((1, 6))
    inv.advance_node((1, 7))
    project_effect_capacity(gs)
    assert gs.bench.value.capacity == BENCH_CAPACITY_DEFAULT == 9, \
        '到期自动回 9(§3.2.5)'


def test_capacity_projection_slot_overflow_keeps_truth(monkeypatch) -> None:
    """槽表归一边界(进窗占席 >3 判据,裁决点 4 默认案钉子):容量外存在
    占席槽 → **不截断**(禁丢真值)+ log 缺陷级留证 + 容量字段照写;容量外
    真值下毒由拒落兜底防(bench_place 按表长,不读 capacity)。"""
    from types import SimpleNamespace as _NS

    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        DurationKind,
        DutyFlags,
        EffectKind,
        EffectSpec,
        TriggerKind,
    )

    logs: list[str] = []
    monkeypatch.setattr(gs_mod.log, 'warning',
                        lambda msg, *a: logs.append(msg % a if a else str(msg)))
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.effects.register_strategy(EffectSpec(
        id='test_cap2', name='容量测试桩2', trigger=TriggerKind.CONDITIONAL,
        duration=DurationKind.N_NODES, category=EffectKind.ECONOMY,
        payload=_NS(capacity_limit=3), duties=DutyFlags(track=True),
        duration_nodes=2), acquired_key=(1, 5))
    slots = ([BenchSlot(kind='empty')] * 4
             + [BenchSlot(kind='unit', unit=Unit(char_id='花火', star=1))]
             + [BenchSlot(kind='empty')] * 4)
    gs.observe(gs.bench, BenchView(slots=slots,
                                   capacity=BENCH_CAPACITY_DEFAULT),
               sig=_sig())
    project_effect_capacity(gs)
    view = gs.bench.value
    assert view.capacity == 3, '容量字段照写(激活期 = 声明值)'
    assert len(view.slots) == 9, '容量外有占席 → 不截断(禁丢真值)'
    assert view.slots[4].kind == 'unit', '容量外占席槽位原样保留'
    assert any('容量外占席' in m for m in logs), '缺陷级留证(log)'


def test_capacity_projection_multi_entry_min_and_noop() -> None:
    """limits 推导单一源(active_capacity_limit):两条目已登记取 min(叠加
    收紧向);零条目 + 表已归一 → 全视图相等零写(no-op 逐位,防回归
    冗余行)。"""
    from types import SimpleNamespace as _NS

    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        DurationKind,
        DutyFlags,
        EffectKind,
        EffectSpec,
        TriggerKind,
    )
    from sr_od.application.currency_war.kernel.cw_game_state import (
        active_capacity_limit,
    )

    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert active_capacity_limit(gs) == BENCH_CAPACITY_DEFAULT, \
        '零条目 = 默认 9'
    gs.effects.register_strategy(EffectSpec(
        id='test_cap3', name='容量测试桩3', trigger=TriggerKind.CONDITIONAL,
        duration=DurationKind.N_NODES, category=EffectKind.ECONOMY,
        payload=_NS(capacity_limit=5), duties=DutyFlags(track=True),
        duration_nodes=9), acquired_key=(1, 5))
    gs.effects.register_strategy(EffectSpec(
        id='test_cap4', name='容量测试桩4', trigger=TriggerKind.CONDITIONAL,
        duration=DurationKind.N_NODES, category=EffectKind.ECONOMY,
        payload=_NS(capacity_limit=3), duties=DutyFlags(track=True),
        duration_nodes=9), acquired_key=(1, 5))
    assert active_capacity_limit(gs) == 3, '多声明取 min(叠加收紧向)'
    slots = [BenchSlot(kind='empty')] * 3
    gs.observe(gs.bench, BenchView(slots=slots, capacity=3), sig=_sig())
    seq = gs.write_seq
    project_effect_capacity(gs)
    assert gs.write_seq == seq, '表已归一(3 长 capacity 3)→ 全视图相等零写'


def test_consume_use_decrements_removes_and_tolerates_missing() -> None:
    """§3.2.19 跳过递减:落地一次 −1;归零移除;无已登记条目返 None 零动作
    (递减挂点与登记挂点解耦,不炸执行链)。"""
    inv = ActiveEffectInventory()
    assert inv.consume_use('151301') is None, '未登记 = None 零动作'
    inv.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_key=(1, 3))
    assert inv.consume_use('151301') == 1
    assert inv.first('151301') is not None, '尚有余量不移除'
    assert inv.consume_use('151301') == 0
    assert inv.first('151301') is None, '用尽 = 效果离场'
    assert inv.consume_use('151301') is None


def test_bump_key_advances_only_tracked_entries() -> None:
    """§5.1 计数 bump:动作侧全量推进只辖 duties.track=True 条目(「谁要
    记账」的声明单一源);消费按 (spec_id, key) 隔离读。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['采购专员·金'], acquired_key=(1, 1))  # track=True
    inv.register_strategy(STRATEGY_EFFECTS['人力重组'], acquired_key=(1, 1))     # predict only
    inv.bump_key(CounterKey.REFRESH)
    inv.bump_key(CounterKey.REFRESH)
    assert inv.counter('201201', CounterKey.REFRESH) == 2
    assert inv.counter('102801', CounterKey.REFRESH) == 0, \
        '未声明记账义务的条目不被推进'


def test_market_intervention_track_counts_refreshes() -> None:
    """市场干预计数面生效(T-113 设计 §4 锁 3,窄化只证本卡新事实):
    duties.track=True 声明生效——登记后一次刷新推进本卡 REFRESH 计数。
    bump 只辖 track 条目与 (spec_id, key) 隔离两语义 = 存量锁
    test_bump_key_advances_only_tracked_entries 已辖,本锁不重复建。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['市场干预'], acquired_key=None)
    inv.record_refresh(free=False)
    assert inv.counter('102201', CounterKey.REFRESH) == 1, \
        '登记后一次刷新推进本卡计数(track 声明生效)'


def test_on_buy_bumps_buy_key_by_k() -> None:
    """购买回调计数面(形态镜像 on_level_up;挂点 = 买牌上报函数获取
    计算完时点):满栏合成一击多买按实际张数 k 计 k 次(返利族「每购
    3 张 5 费」门槛面);推进只辖 duties.track=True 条目(bump_key 同一
    承载);缺省 k=1 = 简单分支单击单张。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['采购专员·金'], acquired_key=(1, 1))  # track=True
    inv.on_buy(card=None, star=1, k=3)
    assert inv.counter('201201', CounterKey.BUY) == 3, 'k 张计 k 次'
    inv.on_buy(card=None, star=1)
    assert inv.counter('201201', CounterKey.BUY) == 4, '缺省 k=1'


# ============================================================ 挂点接线测试(缓交)
# 原 test_effect_hooks_wired_at_production_sites(§5.1 四挂点+B1 桥两采样点
# 字符串在场断言)本批不收录:分诊=修复需 import 在飞互斥面符号
# (cw_screen_shop 的执行落地 bump、cw_loop 的节点 tick),且本体为
# 源码扫描形态(AGENTS §10.4.4 禁)。挂点接线的行为测试待在飞批落地后按
# 行为测试形态重写,台账见 .debug/progress//reports/
# 分诊报告(易失)。


# ============================================================ 第 15 轮对抗审 C8
# sim 合成口 payload 离屏分支(§2.2 例外:真值缺席 = 结构离屏,禁旧 payload 残留)


def test_synthesis_payload_offscreen_branch() -> None:
    """C8:种子空店离屏分支(shop_screen='off';§2.2 例外:真值缺席 =
    结构离屏,禁旧 payload 残留)——禁旧 shop payload 连旧 evidence 残留
    (把「不在商店」帧误读成「商店仍开着」);encounter/supply 两域种子
    不建模,恒离屏口径;牌面在场帧照常观察落 payload。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    cw4_gs(gs, gold=0, level=1, node_fill=False,
           shop=[StateShopCard(x=1, name='花火', cost=2, star=1,
                                cost_source='badge')])
    # 改写依据:三态定长五槽模型(用户三态裁定 2026-09-13)后 payload
    # 形态 = ShopSlot 包裹,x=1 → 下标 1 content 槽;离屏分支断言不变。
    _slot = gs.shop.value.cards[1] if gs.shop.value is not None else None
    assert _slot is not None and _slot.kind == 'content' \
        and _slot.card is not None and _slot.card.name == '花火'

    # 连续种子帧:空店离屏(旧 payload 不残留)
    cw4_gs(gs, gold=0, level=1, hp=None, node_fill=False,
           shop_screen='off')
    assert gs.shop.value is None, '离屏帧 payload 置 None(禁残留)'
    assert gs.shop.source == 'observation' \
        and gs.shop.evidence == 'left_screen', '结构离屏 = left_screen 标记'
    assert gs.encounter.value is None \
        and gs.encounter.evidence == 'left_screen'
    assert gs.supply.value is None and gs.supply.evidence == 'left_screen'


def test_synthesis_shop_empty_keeps_payload_in_recognition_domain() -> None:
    """识别域空店失读窗(shop_screen='unread',店开相位实机喂入口径)
    空牌面 = 买空/OCR 失读窗 → 不写保现值(失读窗沿用上一开店牌面),禁按
    离屏清 None。实证 = 2026-09-13 实机局 run_20260913_085025:买空店重进
    被真值口径清 None,``decide_shop_action`` 在屏前置 shop=None 契约崩
    循环(journal 同帧 current_screen 开商店 ∧ prov.shop left_screen)。
    真值域缺省分支的同帧行为 = test_synthesis_payload_offscreen_branch
    (离屏锁不变,两域分叉 = 三态语义在种子层 shop_screen 字段的表达)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    cw4_gs(gs, gold=0, level=1, node_fill=False,
           shop=[StateShopCard(x=1, name='花火', cost=2, star=1,
                                cost_source='badge')])
    assert gs.shop.value is not None

    # 买空店重进帧:shop 空表,识别域口径 → 保现值沿用(其余域照常种子)
    cw4_gs(gs, gold=0, level=1, hp=None, node_fill=False,
           shop_screen='unread')
    assert gs.shop.value is not None, '识别域空表 = 失读窗,禁清 None'
    # 改写依据:三态定长五槽模型(用户三态裁定 2026-09-13)后沿用值形态 =
    # ShopSlot 包裹,content 槽紧缩视图语义等价旧紧缩列表读法。
    assert [s.card.name for s in gs.shop.value.cards
            if s.kind == 'content'] == ['花火'], \
        '沿用上一开店牌面(失读窗语义,同观察漏斗「空牌面不写」口径)'
    assert gs.shop.evidence != 'left_screen', '识别域空表非结构离屏'


# ============================================================ §8.7 批次四
# 退役 + relay 空值闸(原独立批次文件按主题文件纪律归并入本文件;断言体
# 零语义改动)。测试面 = §8.7 批次四:
# - relay 会话侧值已确立闸(§2.1:会话载体默认空值 ''/[] 是「未知」非
#   「已知事实」,禁中继成正式值;字符串非空/列表非空才中继)——单元测试 +
#   恢复局场景端到端测试(新 session 空默认不落 GameState、真值后到可落);
#   端到端两个测试复用上方观察流域的 _feed_ctx/_patch_clean_readers(镜像字段
#   中继走 feed 尾部公共段,reader 读值与本组断言面无关);
# - 退役载体零残留(AST 级静态测试,标识符面):已退役符号全仓零命中 +
#   记录面(kernel/cw_game_state.py)零 last_state 标识符命中。
# payload 域三域口径的对齐断言在本文件上方(test_leave_screen_payload_only
# 负断言辖 settlement),本节不重复。

#: §2.1 五镜像字段(批次二 feed 中继点;恢复局新 session 停在空默认的面)。
_MIRROR_FIELDS = ('active_strategies', 'active_env', 'plane_bosses',
                  'enemy_affixes')
# (selected_difficulty 已随终态契约 §B 退出中继镜像:写入端 = 入口链漏斗
#  直写 gs.write_logic,证据注记不同。)


# ============================================================ §2.1 relay 空值闸


def test_relay_unit_gate_truth_table() -> None:
    """§2.1 relay 空值闸单元测试(表驱动并一;合并原
    test_relay_rejects_session_empty_defaults /
    test_relay_gate_scope_is_empty_string_and_containers_only /
    test_relay_empty_refusal_does_not_block_late_truth;断言分支逐条保留):

    - 空值 = 未知态禁中继:字符串空/空白、列表/元组/字典/集合空 = 会话
      侧值未确立,一律拒写(返回 False,字段保持从未写过,不留来源痕迹);
    - 闸辖域 = 空字符串与空容器(§2.1 词面:字符串非空/列表非空);falsy
      但有语义的标量(如 streak=0 真 0)不受闸辖,禁过度收紧;非空列表
      即确立(结构已知,元素 None = 简报源未读得位,保位语义,§8.4);
    - 拒后真值后到可落(恢复局核心语义):空默认被拒后字段仍是「从未
      写过」——真值后到正常落(logic + session_carrier);「持卡名单 []
      为假事实、拦截后到真值」的缺陷面由本分支钉死;
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
    """§2.1 恢复局场景端到端一测试(两阶段并一;合并原
    test_restore_session_empty_mirrors_not_relayed /
    test_restore_session_late_truth_relay_lands,断言分支逐条保留):

    - 阶段 1(空默认拒):恢复局新 session 五镜像字段停会话默认
      (''/[])→ 生产 feed(read_game_state 观察流)逐帧中继全被空值闸拒:
      非种子的 plane_bosses 保持 None(未知态不固化成正式值);开局种子
      底座三 A 类镜像字段(active_strategies/active_env/enemy_affixes)
      冷建即种子态,拒写语义 = 保持种子原样、不落 session_carrier 痕迹;
    - 阶段 2(真值后到):session 侧被接管协议/事件屏 handler 写入 →
      下一帧中继正常落五镜像(source=logic + evidence=session_carrier)
      ——空默认拒写不拦截后到真值。"""
    from sr_od.application.currency_war.obs import cw_observation

    sess = SimpleNamespace(last_streak=0, active_strategies=[])
    _patch_clean_readers(monkeypatch)
    ctx = _feed_ctx(sess)

    cw_observation.read_game_state(ctx, None, phase='prep_clean')

    gs = game_state_of(sess)
    assert gs.plane_bosses.value is None, '非种子镜像保持 None(空默认拒)'
    for name in ('active_strategies', 'active_env', 'enemy_affixes'):
        fld = getattr(gs, name)
        assert fld.source == 'logic_rand' \
            and fld.evidence == 'seed:opening', \
            f'空默认拒写:保持开局种子态不落中继痕迹:{name}'

    # 真值后到(恢复局:简报/事件屏/难度确认屏写端补齐会话侧事实)
    # active 双字段播种随终态契约 §B 迁容器(write_logic 直写;中继读已切容器源)
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso_t,
    )
    _gso_t(sess).write_logic(
        _gso_t(sess).active_strategies, ['白银投资'],
        produced_by='test',
        sig=ChannelSig(family='logic_action', actor='CwLoop',
                       screen='', mode='compute'))
    _gso_t(sess).write_logic(
        _gso_t(sess).active_env, '昼之半神概念股',
        produced_by='test',
        sig=ChannelSig(family='logic_action', actor='CwLoop',
                       screen='', mode='compute'))
    # briefing 双字段播种随终态契约 §B 迁容器(write_logic 直写)
    _gso_t(sess).write_logic(
        _gso_t(sess).plane_bosses, ['首领甲', None, None],
        produced_by='test',
        sig=ChannelSig(family='logic_action', actor='CwLoop',
                       screen='', mode='compute'))
    _gso_t(sess).write_logic(
        _gso_t(sess).enemy_affixes, ['正当防卫'],
        produced_by='test',
        sig=ChannelSig(family='logic_action', actor='CwLoop',
                       screen='', mode='compute'))
    # (selected_difficulty 已随终态契约 §B 改入口链直写 gs,不经中继——
    #  该字段断言随写入端迁移归入口链测试。)
    gs.write_logic(gs.selected_difficulty, 'A8', produced_by='test',
                   sig=ChannelSig(family='logic_action', actor='CwLoop',
                                  screen='', mode='compute'))
    cw_observation.read_game_state(ctx, None, phase='prep_clean')

    assert gs.active_strategies.value == ['白银投资']
    assert gs.active_env.value == '昼之半神概念股'
    assert gs.plane_bosses.value == ['首领甲', None, None]
    assert gs.enemy_affixes.value == ['正当防卫']
    assert gs.selected_difficulty.value == 'A8'
    for name in _MIRROR_FIELDS:
        fld = getattr(gs, name)
        assert fld.source == 'logic', f'中继形态 logic(§2.1):{name}'
        # 终态契约 §B:镜像四字段全改写端直写(无中继注记)
        assert fld.evidence is None, f'直写形态(无 session_carrier):{name}'


# ==================== 容器视图转换/合成口/ShopCard 映射(自 w5_passthrough 归并) ====================

# 旧槽表换算族的席位转换测试随换形层退役删除:被测换形口不复存在,
# 阵营派生消费面走注册表单一源(char_first_faction,faction 三类口径
# 测试另辖)。ShopCard 映射单一源往返分支保留(test_shop_card_mapping_roundtrip)。
def _mk_legacy_card(x: int, name: str, *, cost: int = 1, star: int = 1,
                    faction: str = '仙舟',
                    cost_source: str = 'badge',
                    slot: int = 0):
    from sr_od.application.currency_war.kernel.cw_vocab import ShopCard
    return ShopCard(x=x, faction=faction, name=name, cost=cost, star=star,
                    cost_source=cost_source,
                    slot=slot)


def test_shop_card_mapping_roundtrip() -> None:
    """映射单一源往返:旧→容器保五记录字段+槽号;容器→旧 x 置 0 不消费、
    slot 自容器透传(执行/读取器域处置语义见映射函数)。"""
    legacy = _mk_legacy_card(300, '希儿', cost=1, star=2,
                             cost_source='roster_fallback',
                             slot=3)
    container = shop_card_to_container(legacy)
    assert (container.name, container.faction, container.cost,
            container.star, container.cost_source, container.slot) == \
        ('希儿', '仙舟', 1, 2, 'roster_fallback', 3), \
        '五记录字段原值透传不折叠(cost_source 证据分级禁丢);物理槽号透传'
    assert not hasattr(container, 'x'), '容器牌无执行域坐标字段'
    back = shop_cards_to_legacy([container])
    assert back[0].x == 0, 'x 置 0 不消费(执行侧按槽号现取坐标)'
    assert back[0].slot == 3, '槽号自容器透传(点击取坐标依据,不按下标)'


# ============================================================ 消费切换批
# §3.3.6-8 刷新执行计数 / §3.5.1 结算覆盖写端 / §3.2.18 合成升星判定 /
# §8.8 streak 失读解析 / 备战席读链空集失读 / 特效窗判定口 /
# §3.4.5 四事件屏 chosen 记录面

def test_refresh_execution_paid_and_free_frame_gates() -> None:
    """§3.3.6-8 刷新执行计数主测试(三条分支一测试):①付费刷新 = paid+1 ∧
    total+1;②免费帧闸 = 免费帧不进付费累计(长线利好触发计数载体禁混入
    免费刷)∧ total 照计;③免费余额下限 0(扣减在 Field,由上报函数承载
    ——2026-09-21 Field 化:免费次数升格容器字段 ``gs.free_refresh_left``,
    账本 ``record_refresh`` 只留 paid/total 累计;Field 下限 0 校验 = 上报
    函数扣减分支,见 test_shop_projection_logic 刷新 Field 段)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.effects.record_refresh(free=False)
    assert gs.effects.refresh_paid == 1
    assert gs.effects.refresh_total == 1
    # ② 免费帧闸:免费刷新不进付费计数(余额账已迁 Field,账本零动作)
    bs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    bs2.effects.record_refresh(free=True)
    assert bs2.effects.refresh_paid == 0, '免费帧禁写付费计数'
    assert bs2.effects.refresh_total == 1, '全量计数含免费'
    bs2.effects.record_refresh(free=True)
    assert bs2.effects.refresh_paid == 0, '免费帧恒不进付费计数'


def test_settlement_cover_writes_truth_group() -> None:
    """§3.5.1 结算覆盖写端四形态一测试:①胜局 = observation 真值组(hp/
    streak 带方向/gold·level·xp 仅胜局)+ settlement 结构同步落;
    ②败局页无收入面板(gold/level/xp 缺席不写),hp/streak 真值照覆;
    ③hp 失读(结算页 OCR miss)不写(不可信帧不写,§2.2 写入闸),不清
    既有正式值;④progress_delta 带符号真值落 settlement 结构(胜局正/
    败局负;battle_wait 调用点传参为接线半,本测试辖函数半)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    apply_settlement_cover(gs, hp_after=76, streak_after=4,
                           killed=True, gold=23, level=6, xp=(3, 10))
    assert gs.hp.value == 76 and gs.hp.source == 'observation'
    assert gs.streak.value == 4, '带方向真值(正=连胜)'
    assert gs.gold.value == 23 and gs.level.value == 6
    assert gs.xp.value == (3, 10)
    s = gs.settlement.value
    assert s is not None and s.hp_after == 76 and s.killed is True
    # ② 败局页
    bs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    apply_settlement_cover(bs2, hp_after=41, streak_after=-2, killed=False)
    assert bs2.hp.value == 41 and bs2.streak.value == -2
    assert bs2.gold.value is None and bs2.level.value is None
    assert bs2.xp.value is None
    assert bs2.settlement.value.gold is None
    # ③ hp 失读不写
    bs3 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    bs3.observe(bs3.hp, 80, sig=_sig())
    apply_settlement_cover(bs3, hp_after=None, streak_after=None)
    assert bs3.hp.value == 80 and bs3.hp.source == 'observation'
    # ④ progress_delta 带符号
    bs4 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    apply_settlement_cover(bs4, hp_after=76, streak_after=4, killed=True,
                           progress_delta=2, gold=23)
    assert bs4.settlement.value is not None \
        and bs4.settlement.value.progress_delta == 2
    apply_settlement_cover(bs4, hp_after=70, streak_after=-1, killed=False,
                           progress_delta=-22)
    assert bs4.settlement.value.progress_delta == -22, '败局负增量照落'


def test_detect_merge_upgrade_signature() -> None:
    """§3.2.18 修法 a 触发判定:同名最高星被抬升 = 合成签名(星级只经
    合成上升);普通买新卡/无变化 → False。种子 = 生产同形快照
    (_NS(bench=占席条目, deployed=行域 Unit),与 buy_card 升星分支同构)。"""
    from types import SimpleNamespace as _NS

    from sr_od.application.currency_war.kernel.cw_game_state import (
        BenchSlot,
        Unit,
        detect_merge_upgrade,
    )

    def _b(slot: int, name: str, star: int) -> BenchSlot:
        return BenchSlot(kind='unit', unit=Unit(char_id=name, star=star))

    def _mk(bench, deployed=None):
        return _NS(bench=list(bench), deployed=list(deployed or []))

    c1 = _b(1, '花火', 1)
    c2 = _b(2, '花火', 1)
    c3 = _b(3, '花火', 1)
    cur = _mk([c1, c2, c3])
    proj = _mk([_b(1, '花火', 2)])
    assert detect_merge_upgrade(cur, proj) is True, '3 合 1 → 同名最高星抬升'
    assert detect_merge_upgrade(cur, _mk([c1, c2, c3])) is False, '无变化'
    assert detect_merge_upgrade(
        _mk([c1]), _mk([c1, _b(2, '花火', 1)]),
    ) is False, '普通买新卡不抬最高星'
    deployed_old = _mk([], [Unit(char_id='希儿', star=1)])
    deployed_new = _mk([], [Unit(char_id='希儿', star=2)])
    assert detect_merge_upgrade(deployed_old, deployed_new) is True, \
        '合成域 = 全场(bench+deployed)'


def test_streak_miss_semantics_parse_and_observation_half() -> None:
    """streak 失读两条分支并一:

    - 解析分支(§8.8):失读 → None(与 read_hp 100 假值同型消除);
      '连胜×0' = 真 0(方向真值,fixture 核实 2026-08-11),两者分写;
    - 消费分支(失读守卫):结算带符号真值由 apply_settlement_cover
      直写 gs.streak(见上方结算覆盖测试)——失读跳过语义由覆盖写端
      None 守卫承载(fields.md §3.2.12/§3.5.1)。"""
    from sr_od.application.currency_war.obs.cw_settlement_obs import (
        parse_streak,
    )
    # 解析分支
    assert parse_streak(['挑战结束', '数据统计']) is None, '失读非 0'
    assert parse_streak(['连胜×0']) == 0, '真 0 保留'
    assert parse_streak(['连败×2']) == -2


def test_bench_read_empty_is_miss_not_full(monkeypatch) -> None:
    """P2-1:备战席 SIFT 空集 = 失读(overlay 残留/动画帧/识别退化)≠实席
    全空——读链直产(P6,原观察写端值构造器空集守卫移驻读链)零占用返
    None(调用方走 carried,§2.2 处置①;宁缺勿造),禁把「9 槽全空」当
    observation 入记录(席空数派生误报 free=9/挂起合成升星预期被空视图
    误清);非空 = 槽位保序视图 + 占位件 (kind, 品名) 识别期细分(带名
    槽件,T-39 设计 §2.5)+ SIFT 身份胜出;越界条目丢弃(读链漂移)。"""
    from sr_od.application.currency_war.obs import cw_identity_obs as obs
    # 空读:零命中 + 零占槽物品 → None(禁合成全空视图)
    monkeypatch.setattr(obs, 'identify_slots', lambda *a, **k: [])
    monkeypatch.setattr(obs, '_ctx_slots', lambda ctx, prefix, count: [])
    monkeypatch.setattr(obs, '_bench_item_kind_by_slot',
                        lambda ctx, screen: {})
    assert obs.read_bench_view(object(), object(), object()) is None, \
        '空集 = 失读,禁合成全空视图'
    # 非空 = 槽位保序视图;越界条目不落槽;占位物品 (kind, 品名) 细分带名,
    # SIFT 身份胜出
    from sr_od.application.currency_war.kernel.cw_game_state import Unit
    view = obs._bench_view_of(
        [(2, Unit(char_id='花火', star=2)),
         (10, Unit(char_id='越界角色', star=1)),    # 越界:丢弃
         (0, Unit(char_id='越界角色2', star=1))],  # 越界:丢弃
        {1: ('tome', '星徽秘典'), 2: ('supply_box', '简易武装箱')})
    assert view is not None
    assert [(s.kind, s.item) for s in view.slots] == \
        [('tome', '星徽秘典'), ('unit', None)] + [('empty', None)] * 7, \
        '槽位保序(物理槽 1=典籍带名,2=角色);越界条目不落槽;占槽物品只填空槽'
    assert view.slots[1].unit is not None and view.slots[1].unit.star == 2


def test_merge_effect_window_gate_default_off_and_injectable(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """P3-10:特效窗判定读口——screen=None/槽缺省关恒 False(核对放行,
    与既有门 best-effort 语义同向);注入后按实现判定(monkeypatch 还原)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile

    assert cw_reconcile.is_merge_effect_window(None) is False, \
        'screen=None 不拦(离线/测试注入态)'
    monkeypatch.setattr(cw_reconcile, '_IS_MERGE_EFFECT_FRAME', None,
                        raising=False)
    assert cw_reconcile.is_merge_effect_window(object()) is False, \
        '槽缺省关(未装配)= 核对放行'
    monkeypatch.setattr(cw_reconcile, '_IS_MERGE_EFFECT_FRAME',
                        lambda screen: True, raising=False)
    assert cw_reconcile.is_merge_effect_window(object()) is True, \
        '窗内 = 顺延核对信号'
    monkeypatch.setattr(cw_reconcile, '_IS_MERGE_EFFECT_FRAME',
                        lambda screen: False, raising=False)
    assert cw_reconcile.is_merge_effect_window(object()) is False


def _op_with_session(op_cls: type, sess: object) -> object:
    """``__new__`` 绕过 op 构造(SrContext 全量依赖不可裸建);只喂四屏
    chosen 记录面读取的唯一 ctx 依赖面 = cw_match.session。"""
    op = op_cls.__new__(op_cls)
    op.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=sess))
    return op


def _chosen_rows() -> dict:
    """chosen 记录面表行(遭遇/专家/祈愿三案;每行 = op 类 + chosen 字段
    + 真选调用 + 期望值 + fallback 调用集;supply 暂存生命周期独立成案,
    归事件屏驱动测试)。遭遇臂 = 动作侧发射即写(遭遇扩围批:写端迁
    ``kernel/cw_action_report/pick_encounter.py``,真选/fallback 经 report
    函数直调,payload 槽前置播种模拟入口观察)。"""
    from sr_od.application.currency_war.kernel.cw_action_report.pick_encounter import (
        report_action_pick_encounter_param,
    )
    from sr_od.application.currency_war.kernel.cw_events import EncounterOption
    from sr_od.application.currency_war.kernel.cw_game_state import (
        EncounterPayload,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickEncounterParam,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_encounter,
        cw_screen_expert_invite,
        cw_screen_wish_trial,
    )

    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2']),
            EncounterOption(idx=1, difficulty=3, rewards=['随机4费×3'])]
    bonds: list[str | None] = ['仙舟', None, '贝洛伯格', None]
    _sig = ChannelSig(family='logic_action', actor='test', mode='compute')

    def _enc_report(op, idx: int, *, seed: bool) -> None:
        gs = game_state_of(op.ctx.cw_match.session)
        if seed:
            gs.write_logic(gs.encounter, EncounterPayload(options=list(opts)),
                           produced_by='test', sig=_sig)
        report_action_pick_encounter_param(
            gs, CwActionPickEncounterParam(idx=idx), _sig)

    return {
        'encounter': {
            'op_cls': cw_screen_encounter.CwScreenEncounter,
            'field': 'chosen_encounter',
            'pick': lambda op: _enc_report(op, 1, seed=True),
            'expected': (3, '随机4费×3'),
            'fallbacks': [
                lambda op: _enc_report(op, 1, seed=False),   # payload 离屏(观察层失约)
                lambda op: _enc_report(op, 5, seed=True)],   # idx 越界(盲选防御)
        },
        'expert': {
            'op_cls': cw_screen_expert_invite.CwScreenExpertInvite,
            'field': 'chosen_expert',
            'pick': lambda op: op._record_chosen_expert(0, bonds),
            'expected': '仙舟',
            'fallbacks': [
                lambda op: op._record_chosen_expert(-1, bonds),   # 现金为王兜底
                lambda op: op._record_chosen_expert(9, bonds),    # 越界(防御面)
                lambda op: op._record_chosen_expert(1, bonds)],   # 羁绊缺失(防御面)
        },
        'wish': {
            'op_cls': cw_screen_wish_trial.CwScreenWishTrial,
            'field': 'chosen_wish',
            'pick': lambda op: op._record_chosen(['累计刷新10次', '', ''], 0),
            'expected': '累计刷新10次',
            'fallbacks': [
                lambda op: op._record_chosen(None, 0),            # objective 未读到
                lambda op: op._record_chosen(['', '难度3+战斗'], 0),  # 选中槽文本空
                lambda op: op._record_chosen(['累计刷新10次'], 7)],    # 越界
        },
    }


@pytest.mark.parametrize('case_id', list(_chosen_rows()))
def test_chosen_record_face_true_pick_only(case_id: str) -> None:
    """四事件屏 chosen_* 记录面真值表一测试(§3.4.5 余屏写端;三案表驱动
    并一):

    - 真选写:值 = 原名口径(遭遇 = (难度档, 奖励文本) / 专家 = 卡羁绊
      原文名 / 祈愿 = objective 原文名),source=logic(单次逻辑写入);
    - fallback(无会话/候选未读到/越界/羁绊缺失/选中槽文本空)不写;
      专家「现金为王」兜底不写——该事实由 ConfirmExpertCash +4 金到账
      登记通道承载,照旧不动;真选守卫照 chosen_tome 式。
    (写端接线在位/落地验真后写的调用时点面归 review 与代码规范;本测试
    辖记录面行为半。)"""
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    row = _chosen_rows()[case_id]
    sess = StrategySession()
    op = _op_with_session(row['op_cls'], sess)
    row['pick'](op)
    fld = getattr(game_state_of(sess), row['field'])
    assert fld.value == row['expected'], f'{case_id}: 真选值 = 原名口径'
    assert fld.source == 'logic', f'{case_id}: 单次逻辑写入(source=logic)'
    # fallback 帧(全新会话):逐个不写
    sess2 = StrategySession()
    op2 = _op_with_session(row['op_cls'], sess2)
    for fallback in row['fallbacks']:
        fallback(op2)
    assert getattr(game_state_of(sess2), row['field']).value is None, \
        f'{case_id}: fallback 不写'


# ============================================================ 容器合同
# §1 写入口六通道(observe/carry/身份匹配)/ §2 版本与状态流水 /
# §3 快照 / §4 画面上下文与节点域 / §5 坐标系纯函数 / §6 终局 /
# §9 渠道签名封闭集

def _gs() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


def test_observe_writes_and_overrides() -> None:
    """观察通道:亲眼看 → source=observation,覆盖旧值;value=None 拒绝
    (§2.2 失读不是观察值,禁清正式值);渠道面校验 = 观察 口 只收 obs 族。"""
    gs = _gs()
    gs.observe(gs.gold, 37, sig=_sig())
    assert gs.gold.value == 37 and gs.gold.source == 'observation'
    gs.observe(gs.gold, 40, sig=_sig())
    assert gs.gold.value == 40
    with pytest.raises(ValueError, match='observe 不接受 None'):
        gs.observe(gs.gold, None, sig=_sig())
    with pytest.raises(ValueError, match="不属本写入口合法族"):
        gs.observe(gs.gold, 1, sig=_lsig())


def test_carry_carries_good_value_and_skips_never_read() -> None:
    """失读处置①(§2.2):沿用上次好值,evidence=carried:<帧>;
    从未读字段(机制性 None)→ no-op 不占版本不换来源(不造假历史)。"""
    gs = _gs()
    gs.observe(gs.gold, 30, sig=_sig())
    v_before = gs.current_version()
    gs.carry(gs.gold, frame='p1-r2', sig=_sig())
    assert gs.gold.source == 'carried'
    assert gs.gold.evidence == 'carried:p1-r2'
    assert gs.gold.value == 30
    assert gs.current_version() == v_before + 1
    hp_version = gs.current_version()
    gs.carry(gs.hp, frame='p1-r2', sig=_sig())
    assert gs.hp.source == 'observation' and gs.hp.value is None
    assert gs.current_version() == hp_version, '从未读 carry 不占版本'


def test_cross_instance_field_reference_rejected() -> None:
    """身份匹配(§8.4):target 须是本单例字段现引用,跨单例引用 = 写丢
    事故形态,显式炸错禁静默。"""
    gs_a, gs_b = _gs(), _gs()
    with pytest.raises(KeyError):
        gs_a.observe(gs_b.gold, 1, sig=_sig())


def test_versions_monotonic_reads_do_not_consume() -> None:
    """版本语义(§3.2.2):写占版本;读(current_version)不占;
    carry 未读字段不占(no-op)。"""
    gs = _gs()
    assert gs.current_version() == 0
    gs.observe(gs.gold, 1, sig=_sig())
    v1 = gs.current_version()
    assert v1 == 1
    assert gs.current_version() == v1, '读不占版本'
    gs.observe(gs.gold, 2, sig=_sig())
    assert gs.current_version() == v1 + 1


@pytest.fixture()
def journal_sink():
    """未设 run_id_provider 的空转 sink:验证「局外拒写行」分支。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        set_state_journal_sink,
    )
    rows: list[dict] = []
    set_state_journal_sink(rows.append)
    yield rows
    set_state_journal_sink(None)


def test_journal_rows_self_contained_and_run_gated(journal_sink) -> None:
    """状态流水行(§3.2.3):写入行带 v/ts/run_id/field/after/自足 state 快照/
    sig;run_id 空 = 局外写入,拒写行(诚实缺失,不写假行)。"""
    gs = _gs()
    gs.observe(gs.gold, 5, sig=_sig())
    rows = journal_sink
    assert rows == [], '无 run_id(局外)不落行'
    run_sink: list[dict] = []
    from sr_od.application.currency_war.kernel.cw_game_state import (
        set_run_id_provider,
        set_state_journal_sink,
    )
    set_state_journal_sink(run_sink.append)
    set_run_id_provider(lambda: 'run_probe')
    try:
        gs.observe(gs.hp, 70, sig=_sig())
    finally:
        set_state_journal_sink(None)
        set_run_id_provider(None)
    assert len(run_sink) == 1
    row = run_sink[0]
    assert row['row'] == 'write' and row['field'] == 'hp'
    assert row['after'] == 70 and row['run_id'] == 'run_probe'
    assert row['state']['values']['hp'] == 70, '行内 state 自足'
    assert row['sig']['actor'] == 'TestSigWriter'


def test_same_value_rewrite_flags_and_consumes_version(journal_sink) -> None:
    """同值重写:仍占版本(写语义统一),行带 same_value=True
    (判读者可辨「重复写」与「值变化」)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        set_run_id_provider,
        set_state_journal_sink,
    )
    gs = _gs()
    gs.observe(gs.gold, 9, sig=_sig())
    run_sink: list[dict] = []
    set_state_journal_sink(run_sink.append)
    set_run_id_provider(lambda: 'run_probe')
    try:
        gs.observe(gs.gold, 9, sig=_sig())
    finally:
        set_state_journal_sink(None)
        set_run_id_provider(None)
    assert gs.current_version() == 2
    assert run_sink[-1]['same_value'] is True


def test_match_facts_domain_version_bumped_lands_in_journal_rows() -> None:
    """match_facts 域版本 bump 落行(接管域):DEFAULT_GS_SCHEMA 声明值与
    写行内嵌快照 state.gs_schema 同值(行行自足,判读不前溯可查域版本)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        DEFAULT_GS_SCHEMA,
        set_run_id_provider,
        set_state_journal_sink,
    )
    gs = _gs()
    run_sink: list[dict] = []
    set_state_journal_sink(run_sink.append)
    set_run_id_provider(lambda: 'run_probe')
    try:
        gs.write_logic(gs.lv999_cost_tier, 1, produced_by='ContractTest',
                       evidence='match_facts_domain_version_probe',
                       sig=_lsig())
    finally:
        set_state_journal_sink(None)
        set_run_id_provider(None)
    assert len(run_sink) == 1
    row = run_sink[0]
    assert row['row'] == 'write' and row['field'] == 'lv999_cost_tier'
    assert row['after'] == 1
    assert row['state']['gs_schema']['match_facts'] \
        == DEFAULT_GS_SCHEMA['match_facts'], \
        '域版本 bump 落行(行内 state 快照携带,与声明值同源)'


def test_obs_event_consumes_version_without_state_change(journal_sink) -> None:
    """观察事件行(行型 2):同流占版本、零 Field 变更;事件词表封闭
    (arbitrate|miss|popup|chain_diff),集外炸错。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        OBS_EVENT_EVENTS,
        set_run_id_provider,
        set_state_journal_sink,
    )
    assert OBS_EVENT_EVENTS == ('arbitrate', 'miss', 'popup', 'chain_diff')
    gs = _gs()
    gs.observe(gs.gold, 3, sig=_sig())
    v = gs.current_version()
    run_sink: list[dict] = []
    set_state_journal_sink(run_sink.append)
    set_run_id_provider(lambda: 'run_probe')
    try:
        gs.note_obs_event('arbitrate', 'hp', {'old': 1, 'new': 2},
                          verdict='冲突', sig=_sig())
    finally:
        set_state_journal_sink(None)
        set_run_id_provider(None)
    assert gs.current_version() == v + 1, 'obs_event 占版本'
    assert gs.gold.value == 3, '零状态变更'
    assert run_sink[-1]['row'] == 'obs_event'
    with pytest.raises(ValueError, match='集外'):
        gs.note_obs_event('bogus', 'hp', None, sig=_sig())


def test_full_state_snapshot_shape() -> None:
    """自足快照(§3.2.3):values 只收非 None;prov 记非默认来源
    (source≠observation 或 evidence 非 None);同态同形 = 同内容快照逐键一致。"""
    gs = _gs()
    gs.observe(gs.gold, 30, sig=_sig())
    gs.write_logic(gs.hp, 70, produced_by='p', sig=_lsig())
    snap = gs.full_state_snapshot()
    assert snap['values']['gold'] == 30 and snap['values']['hp'] == 70
    assert 'hp' in snap['prov'] and snap['prov']['hp']['source'] == 'logic'
    assert 'gold' not in snap['prov'], 'observation 无 evidence 不进 prov'
    bs2 = _gs()
    bs2.observe(bs2.gold, 30, sig=_sig())
    bs2.write_logic(bs2.hp, 70, produced_by='p', sig=_lsig())
    assert bs2.full_state_snapshot() == snap, '同态同形'


def test_screen_context_writes_pair_only_no_advance() -> None:
    """漏斗瘦身(design §2.4 攻击 B1):observe_screen_context 只写上下文对
    (prev/current)——推进域(node_pos/hist)零触碰,四推断分支已退役;节点
    推进唯一落账入口 = advance_node_effective(动作上报/观察锚定)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        SCREEN_PREP_FRAME,
    )
    gs = _gs()
    gs.observe_screen_context(SCREEN_PREP_FRAME, sig=_sig())
    assert gs.current_screen.value == SCREEN_PREP_FRAME, '上下文对写入'
    assert gs.node_pos.value is None and gs.node_hist_pos is None, \
        '备战帧上下文零推进(分支已退役)'
    other = _gs()
    other.observe_screen_context('货币战争-战斗等待', sig=_sig())
    other.observe_screen_context('货币战争-补给', sig=_sig())
    assert other.node_pos.value is None and other.node_hist_pos is None, \
        '战斗等待→补给(prev∈旧守卫族形态)零推进(弹窗分支已退役)'


def test_boss_briefing_report_types_hist_node() -> None:
    """BOSS 类型直定迁移(design §2.5 表):简报屏上报经 kernel report
    直定 boss 类型,目标 = 现 hist;序号推进半部已退役(简报上报零
    node_pos 写);hist 未推进 = 零写禁猜。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        observe_node_anchor,
    )
    from sr_od.application.currency_war.kernel.cw_screen_report.boss_briefing import (
        CwScreenBossBriefingObs,
        report_screen_boss_briefing_obs,
    )
    gs = _gs()
    report_screen_boss_briefing_obs(
        gs, CwScreenBossBriefingObs(on_screen=True))
    assert gs.node.value is None, 'hist 未推进零写(禁猜)'
    assert gs.node_pos.value is None, '简报上报零序号写(序号半部已退役)'
    observe_node_anchor(gs, (2, 1),
                        trigger_screen='货币战争-备战', actor='TestAnchor')
    report_screen_boss_briefing_obs(
        gs, CwScreenBossBriefingObs(on_screen=True))
    assert gs.node.value is not None \
        and gs.node.value.kind == 'boss', '类型随简报证据落账(boss)'
    assert (gs.node.value.plane, gs.node.value.round_num) == (2, 1), \
        '目标 = 现 hist 反解位(禁写死 round=9)'


def test_board_next_tier_concrete_shape() -> None:
    """坐标系纯函数:棋盘阵营升档 = 同阵营 ≥2 才有下一档(具体形直测;
    节点序位键原语测试 = test_node_pos_primitive)。"""
    assert board_next_tier_of({'仙舟': 2, '联盟': 1}) == {'仙舟': 3}
    assert board_next_tier_of({}) == {}


def test_write_match_final_idempotent() -> None:
    """终局行(G12 写前查重):首写 True,同段二写 no-op 返 False
    (终局防重)。"""
    gs = _gs()
    assert write_match_final(gs, final_type='loss', plane=1) is True
    assert write_match_final(gs, final_type='loss', plane=1) is False


def test_channel_family_closed_set() -> None:
    """§3.2.1/§3.2.4 硬约束 2 签名门两分支:①family 封闭集 {obs,
    logic_action, logic_hook},集外 = 红;②per-family 模态封闭(obs 族子模
    = read/carried/prior/synthesized,logic 两族恒 compute,集外 = 红)。
    actor 无白名单闸(仅遥测身份标注)。"""
    for family in ('obs', 'logic_action', 'logic_hook'):
        assert ChannelSig(family=family, actor='cw_observation').family == family
    with pytest.raises(ValueError):
        ChannelSig(family='event', actor='x')
    with pytest.raises(ValueError):
        ChannelSig(family='hook', actor='x')
    # ② per-family 模态封闭
    for mode in ('read', 'carried', 'prior', 'synthesized'):
        ChannelSig(family='obs', actor='cw_observation', mode=mode)
    with pytest.raises(ValueError):
        ChannelSig(family='obs', actor='cw_observation', mode='compute')
    for family in ('logic_action', 'logic_hook'):
        ChannelSig(family=family, actor='CwScreenPrep', mode='compute')
        with pytest.raises(ValueError):
            ChannelSig(family=family, actor='CwScreenPrep', mode='read')


# ============================================================ 开局种子底座 + 锚定标志 + carry 收窄

#: A 类种子字段全集(与 seed_opening_state 写面一一对应;board 不入——
#: 派生量禁双写,journal 行面断言兜住;行域合卷为 deployed 单字段)。
_A_SEEDED: tuple[str, ...] = (
    'deployed', 'bench', 'equips', 'occupied_equips',
    'spheres', 'gold', 'level', 'xp', 'hp', 'streak', 'back_layout',
    'deploy_cap', 'overflow_warning', 'overflow_card', 'active_env',
    'active_strategies', 'unlocked_experts', 'pending_item_grants',
    'enemy_affixes',
    'shop_refresh_cost', 'prev_node_spent',
    'strategy_refresh_left',
    # 晶矿附着奖励与声明通道三域(迭代 2026-10-10-ore-reward-attach:
    # 空底座,幂等守卫 membership 与挂接入口合并写零 None 防御)
    'ore_rewards', 'ore_declared_pending', 'ore_declared_done',
    # 环境条件发放已发标记(迭代 2026-10-10-env-conditional-grants:
    # 空底座,「本局首次」守卫初始真值 = 空集)
    'env_grants_done',
    # 环境发放上场锁 + 发号计数器(T-30 星核猎手契约:空/零底座,
    # 守卫 membership 与发号均零 None 防御)
    'env_grant_deploy_locks', 'env_grant_uid_seq',
    # 环境倒计时件开盒队列(T-34 命运礼物:空底座,到点弹除比较判定
    # 零 None 防御)
    'pending_item_opens',
    # 策略延时 offer 倒计时队列(空底座,递减/到点判定零 None 防御)
    'pending_strategy_offers',
    # 策略延时发放倒计时队列(空底座,递减/到点判定零 None 防御)
    'pending_strategy_grants',
    # 佩佩客串离场倒计时队列(空底座,递减/弹除判定零 None 防御,
    # T-368 佩佩客串批)
    'pending_kechuan_leaves',
    # 策略卡条件发放已发标记(空底座,检查腿跳过判定零 None 防御)
    'strategy_conditional_done',
    # 绑定型随机角色授予名字绑定域(空 dict 底座,复制发放腿键查判定
    # 零 None 防御;空 = 未持绑定卡的正常态)
    'strategy_char_grant_bindings',
    # 分期金剩余效果条数容器(空 dict 底座,节点窗腿键查判定零 None 防御;
    # 空 = 未持分期卡的正常态,T-177 长期主义首例)
    'strategy_gold_next_nodes_left',
    # 策略卡羁绊档位条件发放已发档位一次性标志位(空 tuple 底座,检查腿 membership
    # 判定零 None 防御;空 = 无档已发的正常态)
    'strategy_bond_tier_fired',
    # 策略卡赠礼条件两条效果条目已发标记(空 tuple 底座,检查腿 membership 判定
    # 零 None 防御;空 = 无腿已发的正常态)
    'strategy_grants_done',
    # 损血档位触发累积器(零底座,触发函数累加取模零 None 防御;
    # 0 = 无累积语义中性,种 0 不伪装已触发)
    'strategy_hp_loss_accum',
    # 惊喜盒板件 ⏳N 读数观察域(迭代 2026-10-19-giftbox-piece-obs:
    # 空底座,整条替换写零 None 防御)
    'giftbox_sight',
)

#: B/C 类抽检面(None = 设计语义或无观察源,设计分诊表禁种)。
_BC_UNSEEDED: tuple[str, ...] = (
    'node', 'node_pos', 'node_path', 'shop', 'encounter', 'supply',
    'settlement', 'match_final', 'selected_difficulty', 'enemy_difficulty',
    'game_mode', 'env_refresh_left', 'supply_refresh_left',
    'encounter_refresh_left', 'plane_bosses',
    'event_overlay',
    'lv999_cost_tier', 'round_fresh_buys', 'level_up_cost', 'top_bar_raw',
    'tracked_account_observed', 'consumables', 'board',
    # 逐位面节点序列场字段(T-8:None = 未注册态是设计语义,B 类不种)
    'node_seq_by_plane',
)

_OBS_SIG = ChannelSig(family='obs', actor='CwScreenPrep', mode='read')


def test_cold_build_seeds_all_a_fields(monkeypatch) -> None:
    """冷建即含种子(缓存单例支):A 类逐字段值 + 来源(logic_rand/
    seed:opening)+ journal 种子行过滤键(actor/mode);B/C 类仍 None;
    board 不落种子行;锚定标志缺省 False。"""
    rows: list[dict] = []
    monkeypatch.setattr(gs_mod, '_STATE_JOURNAL_SINK', rows.append)
    monkeypatch.setattr(gs_mod, '_RUN_ID_PROVIDER', lambda: 'seed-t')
    session = StrategySession()
    gs = game_state_of(session)

    # —— A 类逐字段值(种子值语义:常量引用单一源,不手抄可查表值)——
    assert gs.bench.value == BenchView(
        slots=[BenchSlot(kind='empty')] * BENCH_CAPACITY_DEFAULT,
        capacity=BENCH_CAPACITY_DEFAULT)
    assert deployed_rows_of_view(gs.deployed.value) == ([], [])
    assert gs.deployed.value.back_slots == [None] * 6, '后排容量基线 6'
    assert gs.equips.value == []
    assert gs.occupied_equips.value == {}
    assert gs.spheres.value == OreSight()
    assert gs.ore_rewards.value == {}, '附着奖励域冷建空底座'
    assert gs.ore_declared_pending.value == (), '声明队列冷建空底座'
    assert gs.ore_declared_done.value == (), '声明消费标记冷建空底座'
    assert gs.env_grants_done.value == (), '条件发放标记冷建空底座'
    assert gs.env_grant_deploy_locks.value == (), '上场锁域冷建空底座'
    assert gs.env_grant_uid_seq.value == 0, '发号计数器冷建零底座'
    assert gs.pending_item_opens.value == (), '开盒队列冷建空底座'
    assert gs.pending_strategy_offers.value == (), '延时 offer 队列冷建空底座'
    assert gs.pending_strategy_grants.value == (), '延时发放队列冷建空底座'
    assert gs.strategy_conditional_done.value == (), '条件发放标记冷建空底座'
    assert gs.strategy_char_grant_bindings.value == {}, \
        '绑定域冷建空底座'
    assert gs.strategy_gold_next_nodes_left.value == {}, \
        '分期金剩余发放数容器,每局全新创建(空初始值)'
    assert gs.strategy_bond_tier_fired.value == (), \
        '羁绊档位一次性标志位冷建空底座'
    assert gs.strategy_hp_loss_accum.value == 0, '损血累积器冷建零底座'
    assert gs.giftbox_sight.value == (), '板件读数域冷建空底座'
    assert gs.gold.value == 3
    assert gs.level.value == 3
    assert gs.xp.value == (0, XP_TO_NEXT_LEVEL[3])
    assert gs.hp.value == OPENING_HP_BASE
    assert gs.streak.value == 0
    assert gs.back_layout.value == 6
    assert gs.deploy_cap.value == 3
    assert gs.overflow_warning.value is False
    assert gs.overflow_card.value == ''
    assert gs.active_env.value == ''
    assert gs.active_strategies.value == []
    assert gs.pending_item_grants.value == [], '定时道具队列冷建空底座'
    assert gs.enemy_affixes.value == []
    assert gs.shop_refresh_cost.value == REFRESH_COST_BASE
    assert gs.prev_node_spent.value is False
    assert gs.strategy_refresh_left.value == {}
    # —— 来源断言:logic_rand + seed:opening(种子字段全集)——
    for name in _A_SEEDED:
        f = getattr(gs, name)
        assert f.source == 'logic_rand', name
        assert f.evidence == 'seed:opening', name
    # —— journal 种子行:过滤键 actor + mode;行字段集 = 种子全集
    # (board 派生行不产:种子空行零差 + 板未读无派生基座 = 禁双写守住)——
    seed_rows = [r for r in rows if r['sig']['actor'] == 'GsOpeningSeed']
    assert {r['field'] for r in seed_rows} == set(_A_SEEDED)
    assert all(r['sig']['mode'] == 'compute' for r in seed_rows)
    # —— B/C 类字段仍 None ——
    for name in _BC_UNSEEDED:
        assert getattr(gs, name).value is None, name
    # —— 锚定标志缺省 False(直读 + 读口解析,本体直通形态)——
    assert gs.prep_anchored is False
    assert prep_anchored_of(session) is False
    assert prep_anchored_of(gs) is False


def test_giftbox_sight_domain_registration() -> None:
    """giftbox_sight 域五件套:schema 独立键版本 1(不并入任何域 bump)
    + 快照 rebuild 往返(_json_safe 落 list,rebuild 还原 tuple 不漂移)
    + 投影审计行 observation_only。种子底座锁 =
    test_cold_build_seeds_all_a_fields(同文件,不重复)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        DEFAULT_GS_SCHEMA,
        restore_state_snapshot,
        seed_opening_state,
    )
    from sr_od.application.currency_war.kernel.cw_projection_audit import (
        AUDIT_OBSERVATION_ONLY,
        PROJECTION_AUDIT,
    )

    assert DEFAULT_GS_SCHEMA['giftbox_sight'] == 1, \
        '独立键版本 1(不并入任何域版本 bump)'

    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(gs)
    assert gs.giftbox_sight.value == ()
    gs.observe(gs.giftbox_sight, (12, 9), evidence='t', sig=_OBS_SIG)
    snap = gs.full_state_snapshot()

    restored = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(restored, snap)
    assert restored.giftbox_sight.value == (12, 9), '读数往返无损'
    assert isinstance(restored.giftbox_sight.value, tuple), \
        'tuple 不漂移为 list'

    row = PROJECTION_AUDIT.get('giftbox_sight')
    assert row is not None, '审计表已登记(完备性双向锁另一半)'
    assert row.status == AUDIT_OBSERVATION_ONLY, \
        '观察读端 + 零逻辑写端(纯旁路证据域)'


def test_none_session_and_direct_construct_not_seeded() -> None:
    """session=None 一次性支与直构 GameState 不种(种子只挂两个缓存单例
    建支;测试/sim 直构域依赖未写形态)。"""
    gs_none = game_state_of(None)
    assert gs_none.gold.value is None
    assert gs_none.gold.source == 'observation'   # 从未写(非种子通道)
    assert gs_none.bench.value is None

    direct = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert direct.gold.value is None and direct.bench.value is None
    assert direct.level.value is None and direct.hp.value is None


def test_reconcile_bench_anchor_sets_prep_anchored() -> None:
    """锚定标志生产置位:reconcile_tracking bench 侧屏幕真值写回成功 →
    prep_anchored 置位 + 读口 True(tracked True 同一成功条件)。"""
    session = StrategySession()
    assert prep_anchored_of(session) is False

    ok, _, _ = reconcile_tracking(session, _bench_view1('花火', 1),
                                  DeployedView(), screen=None, source='test')

    assert ok is True
    assert game_state_of(session).tracked_account_observed.value is True
    assert game_state_of(session).prep_anchored is True
    assert prep_anchored_of(session) is True


def test_reconcile_deployed_only_keeps_prep_anchored_off() -> None:
    """失败形态不置位:bench 侧未读(deployed-only 写回成功)= 未锚定,
    一次性标志位保持 False——两一次性标志位同一成功条件,不新增判断分支。"""
    session = StrategySession()

    ok, _, _ = reconcile_tracking(session, None, DeployedView(), screen=None,
                                  source='test')

    assert ok is True   # deployed 侧照常写回
    assert game_state_of(session).tracked_account_observed.value is None
    assert prep_anchored_of(session) is False


def test_carry_narrows_logic_rand_keeps_legacy() -> None:
    """carry 收窄双臂:现值来源 logic_rand(种子态)失读不沿用——值与
    来源不变,宁保持未验证态不洗白成 carried;非 rand 来源(logic)存量
    行为不变(沿用 + carried:<帧> 注记)。"""
    logic_sig = ChannelSig(family='logic_action', actor='test',
                           mode='compute')
    # 收窄臂:logic_rand 现值(种子形态)→ carry 不动
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic_rand(gs.gold, 3, produced_by='GsOpeningSeed',
                        evidence='seed:opening', sig=logic_sig)
    gs.carry(gs.gold, frame='f1', sig=_OBS_SIG)
    assert gs.gold.value == 3
    assert gs.gold.source == 'logic_rand'
    assert gs.gold.evidence == 'seed:opening'
    # 存量回归臂:logic 现值照旧沿用
    gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs2.write_logic(gs2.hp, 80, produced_by='test', sig=logic_sig)
    gs2.carry(gs2.hp, frame='f1', sig=_OBS_SIG)
    assert gs2.hp.source == 'carried'
    assert gs2.hp.evidence == 'carried:f1'
    assert gs2.hp.value == 80


def _bench_view1(name: str, star: int) -> BenchView:
    """单占用槽视图(槽 1)构造(P6 直产读载体,同 tracked 观察态测试)。"""
    slots = [BenchSlot(kind='empty')] * 8
    return BenchView(slots=[BenchSlot(
        kind='unit', unit=Unit(char_id=name, star=star))] + slots)


# ============================================================ deployed 视图桥 + 快照迁移
# (DeployedView 容器合并落地测试:快照旧档迁移等价 / 视图 ↔ 定长工作表
#  两桥往返 / 紧缩行序顺延 / 容量继承 / 信息位退役)

_M31_SIG_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')


def _m31_u(cid: str, star: int = 1,
           equips: list[str] | None = None) -> Unit:
    return Unit(char_id=cid, star=star, equips=list(equips or []))


def _m31_gs_with(view: DeployedView,
                 bench: list[BenchSlot] | None = None) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots = list(bench or []) + [BenchSlot(kind='empty')] * (
        BENCH_CAPACITY_DEFAULT - len(bench or []))
    gs.observe(gs.bench, BenchView(slots=slots,
                                   capacity=BENCH_CAPACITY_DEFAULT),
               sig=_M31_SIG_OBS)
    gs.observe(gs.deployed, view, sig=_M31_SIG_OBS)
    gs.observe(gs.gold, 10, sig=_M31_SIG_OBS)
    return gs


def test_restore_migrates_schema1_rows_snapshot_by_slot_bits() -> None:
    """旧档迁移主测试:schema 1 行域档 → deployed 视图按 slot 信息位
    等价落位(前排槽 4 → front_slots[3];后排槽 1 → back_slots[0]);
    行键消费后摘除,restore 幂等可重放。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        restore_state_snapshot,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    snap = {'values': {
        'front_row': [{'char_id': '丙', 'star': 2, 'equips': ['轮滑鞋'],
                       'slot': 4}],
        'back_row': [{'char_id': '丁', 'star': 1, 'equips': [],
                      'slot': 1}],
    }, 'prov': {}}

    restore_state_snapshot(gs, snap)

    view = gs.deployed.value
    assert [u.char_id if u else None for u in view.front_slots] \
        == [None, None, None, '丙'], '槽位语义等价(前排槽 4 → 下标 3)'
    assert [u.char_id if u else None for u in view.back_slots][:2] \
        == ['丁', None], '后排槽 1 → 下标 0'
    assert view.front_slots[3].equips == ['轮滑鞋'], '装备随单位重建'
    # 重放幂等(转换不破坏原 snap:values 拷贝单次转换)
    gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs2, snap)
    assert gs2.deployed.value == view


def test_restore_migrates_missing_slot_bits_sequential_fallback() -> None:
    """迁移兜底分支:slot 信息位缺席(0)按占用序顺延;越界(>cap)
    同兜底(旧 deployed_rows_to_indexed 兼容口径同向)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        restore_state_snapshot,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs, {'values': {
        'front_row': [{'char_id': '甲', 'star': 1, 'equips': [], 'slot': 0},
                      {'char_id': '乙', 'star': 1, 'equips': [], 'slot': 99}],
        'back_row': [],
    }, 'prov': {}})
    assert [u.char_id if u else None for u in gs.deployed.value.front_slots] \
        == ['甲', '乙', None, None], '缺席/越界顺延落位'


def test_new_schema_snapshot_round_trip_no_legacy_keys() -> None:
    """新档往返:schema 2 快照只现 deployed 键(front_row/back_row
    均不现),往返视图逐位等价(含空槽显式 None)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        restore_state_snapshot,
    )
    gs = _m31_gs_with(DeployedView(
        front_slots=[_m31_u('甲'), None, _m31_u('乙'), None],
        back_slots=[None, _m31_u('丙'), None, None, None, None]))
    snap = gs.full_state_snapshot()
    assert 'deployed' in snap['values']
    assert 'front_row' not in snap['values'] \
        and 'back_row' not in snap['values'], '新档行键不现'

    gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs2, snap)
    assert gs2.deployed.value == gs.deployed.value, '往返逐位等价'


def test_pending_item_opens_snapshot_round_trip() -> None:
    """倒计时件开盒队列快照存续(T-34 命运礼物设计 §4 锁 7,迭代
    2026-09-23-invest-effects-calc;rebuild 登记在位为前提——未登记域
    恢复面拿 list-of-lists 静默类型漂移,T-30 对抗 F5 义务同款):
    ①带队列快照 → restore 往返逐位相等(解锁序位嵌套元组重建);
    ②空队列快照往返 = ();③快照无该键(无快照接管局,披露 4 形态)
    → 恢复域值 None = 未写形态,开盒原语按空队列零写处理。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        restore_state_snapshot,
    )
    sig = ChannelSig(family='logic_action', actor='test-seed',
                     mode='compute')
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    queue = (('惊喜盒', (2, 4)), ('惊喜盒', (3, 1)))
    gs.write_logic(gs.pending_item_opens, queue,
                   produced_by='test-seed', evidence='t:queue', sig=sig)
    snap = gs.full_state_snapshot()
    assert 'pending_item_opens' in snap['values'], '队列进快照'

    gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs2, snap)
    assert gs2.pending_item_opens.value == queue, '往返逐位相等'

    gs3 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs3.write_logic(gs3.pending_item_opens, (), produced_by='test-seed',
                    evidence='t:queue', sig=sig)
    snap3 = gs3.full_state_snapshot()
    gs4 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs4, snap3)
    assert gs4.pending_item_opens.value == (), '空队列往返 = ()'

    snap_no_key = {'values': {}, 'prov': {}}
    gs5 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs5, snap_no_key)
    assert gs5.pending_item_opens.value is None, \
        '快照无键 → 未写形态(接管局队列空,开盒/回退零触发)'


def test_indexed_bridge_round_trip_within_back_capacity() -> None:
    """两桥往返等价:视图 → 定长 10 表 → 视图(后排容量 6 内逐位
    等价;7-9 扩展格截断 = 旧 tracked 表硬上限语义,续辖)。"""
    view = DeployedView(
        front_slots=[_m31_u('甲'), None, _m31_u('乙'), None],
        back_slots=[None, _m31_u('丙'), None, None, _m31_u('丁'), None,
                    _m31_u('越界七格')])   # 后排第 7 格(超出 6)
    dep = deployed_indexed_of_view(view)
    assert len(dep) == 10, '定长 10 工作表'
    assert dep[0].char_id == '甲' and dep[2].char_id == '乙'
    assert dep[5].char_id == '丙' and dep[8].char_id == '丁'
    assert dep[9] is None
    back2 = deployed_view_of_indexed(dep, view)
    assert back2.front_slots == view.front_slots
    assert back2.back_slots[:6] == view.back_slots[:6]
    assert back2.back_slots[6:] == [_m31_u('越界七格')], \
        '7-9 扩展格继承原视图(容量改写不丢扩展格)'


def test_sequential_placement_matches_compact_row_semantics() -> None:
    """紧缩行序顺延落位 = 旧紧凑行域「顺序即占位」口径:第 k 个单位
    落槽 k;紧缩行读回(deployed_rows_of_view)保序往返。"""
    view = deployed_view_sequential(
        [_m31_u('甲'), _m31_u('乙')], [_m31_u('丙'), _m31_u('丁')],
        back_capacity=6)
    assert [u.char_id if u else None for u in view.front_slots] \
        == ['甲', '乙', None, None]
    assert [u.char_id if u else None for u in view.back_slots] \
        == ['丙', '丁', None, None, None, None]
    front, back = deployed_rows_of_view(view)
    assert [u.char_id for u in front] == ['甲', '乙']
    assert [u.char_id for u in back] == ['丙', '丁'], '紧缩行保序'


def test_deployed_field_replacement_inherits_capacity() -> None:
    """容量变化 = 整视图结构性写:seed 底座后排容量 6;7-9 扩展格由
    语义写端显式扩容(工作副本桥 orig 参继承),禁静默截断。"""
    view = deployed_view_sequential([], [_m31_u('甲')] * 7, back_capacity=7)
    assert len(view.back_slots) == 7, '7 格局显式扩容'
    dep = deployed_indexed_of_view(view)
    assert [d.char_id for d in dep[4:10]] == ['甲'] * 6, \
        '动作坐标系 10 槽内:后排 1-6 格'
    rebuilt = deployed_view_of_indexed(dep, view)
    assert rebuilt.back_slots == view.back_slots, \
        '桥继承 orig 容量(7 格不截断回 6)'


def test_unit_has_no_slot_information_bit() -> None:
    """信息位退役直测:Unit 数据类无 slot 字段(位置 = 载体下标纯派生;
    快照序列化同样不出现该键)。"""
    assert not any(f.name == 'slot' for f in dataclasses.fields(Unit))
    gs = _m31_gs_with(DeployedView(front_slots=[_m31_u('甲'), None, None, None],
                                   back_slots=[None] * 6))
    snap = gs.full_state_snapshot()
    front_raw = snap['values']['deployed']['front_slots']
    assert front_raw[0] == {'char_id': '甲', 'star': 1, 'equips': [],
                            'uid': None}, \
        '序列化键集 = 身份/星级/装备/实例号(槽位不入 Unit;uid = T-30 '\
        '实例粒度上场锁尾字段,units 域版本 3)'


def test_deployed_view_of_hits_back_bounds_and_extension() -> None:
    """观察命中构造的越界边界:后排命中越提示容量但在布局值域 {6..9}
    内 → 扩容落位;超上界 9 或 <1 → 丢弃留证不崩。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        deployed_view_of_hits,
    )
    view = deployed_view_of_hits(
        [], [(8, _m31_u('甲')), (3, _m31_u('乙'))], back_capacity=6)
    assert len(view.back_slots) == 8, '合法命中(≤9)越提示 6 → 扩容'
    assert view.back_slots[7].char_id == '甲'
    assert view.back_slots[2].char_id == '乙'

    view2 = deployed_view_of_hits(
        [], [(10, _m31_u('越界')), (0, _m31_u('零位'))], back_capacity=9)
    assert all(u is None for u in view2.back_slots), \
        '>布局上界 9 / <1 → 丢弃(读链漂移留证,不扩容不落位)'
    assert len(view2.back_slots) == 9, '容量不被漂移命中撑大'


