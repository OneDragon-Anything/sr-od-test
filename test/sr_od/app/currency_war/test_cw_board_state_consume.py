# -*- coding: utf-8 -*-
"""BoardState 消费切换批回归锁(迁移批次二;设计正本 =
docs/develop/currency_war/design/BoardState-数据结构设计.md,下称「设计」)。

锁面 = 批次二任务书件:§8.7 消费适配器(旧读取对象 → BoardState 适配层)/
§3.4 单次逻辑写入口(申报豁免写端)/§3.3.6-8 刷新执行事实组(免费帧闸)/
§3.3.1 cost_source 三值归并消费/§3.2.6 board 下档派生单一源(ADR-0488 同键
供给)/§3.5.1 结算覆盖写端/§6.2+§8.8 局终归档快照/§3.2.5 read_bench_full
通道退役墓碑。断言全部按设计语义写;批一 76 条回归锁另文件持续有效。
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_board_state import (
    BS_SCHEMA_VERSION,
    BoardState,
    COST_SOURCE_BADGE,
    COST_SOURCE_REGISTRY,
    NodeKey,
    apply_settlement_cover,
    archive_snapshot,
    bench_is_full,
    board_next_tier_of,
    board_state_of,
    consume_defect_sink,
    cost_source_group,
    record_refresh_execution,
    set_defect_sink,
)


from sr_od.application.currency_war.kernel.cw_bs_view import (
    game_state_view,
    strategy_input_state,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.obs import cw_observation as cobs

# ---- W1 sig 铺满 helper(测试写入口签名必填,ADR-0634;actor 已登记)----
from sr_od.application.currency_war.kernel.cw_board_state import (  # noqa: E402
    ChannelSig as _ChannelSig,
    register_sig_actors as _register_sig_actors,
)

_register_sig_actors('TestSigWriter')


def _sig() -> "_ChannelSig":
    """渠道①签名(obs 族;观察/沿用/先验/离屏/观察事件)。"""
    return _ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _lsig() -> "_ChannelSig":
    """渠道②签名(logic_action 族;逻辑写入/confirm)。"""
    return _ChannelSig(family='logic_action', actor='TestSigWriter',
                       mode='compute')


def _hsig() -> "_ChannelSig":
    """渠道③签名(logic_hook 族;relay 中继)。"""
    return _ChannelSig(family='logic_hook', actor='TestSigWriter',
                       mode='compute')



# ============================================================ §8.7 消费适配器


def _synth_bs_with(st: GameState) -> BoardState:
    """GameState 真值 → BoardState(sim 合成口,批一资产)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    from sr_od.application.currency_war.kernel.cw_board_state import (
        synthesize_from_game_state,
    )
    synthesize_from_game_state(bs, st, at_round='p1-r2')
    return bs


def test_view_modeled_domains_equal_frame_on_clean_frame() -> None:
    """§8.7 等价性:常态帧(无失读)下,已建模域视图值与旧直读帧逐位一致。"""
    st = GameState()
    st.gold = 37
    st.hp = 82
    st.streak = 3
    st.level = 5
    st.xp_progress = (2, 8)
    st.board = {'列车同行': 2}
    st.node_type = 'battle'
    st.plane = 1
    st.round_num = 4
    st.active_strategies = ['白银投资']
    st.selected_difficulty = 'A8'
    bs = _synth_bs_with(st)
    view = game_state_view(bs, st)
    assert view.gold == 37 and view.gold_readable is True
    assert view.level == 5 and view.streak == 3
    assert view.xp_progress == (2, 8)
    assert view.board == {'列车同行': 2}
    assert (view.plane, view.round_num, view.node_type) == (1, 4, 'battle')
    assert view.active_strategies == ['白银投资']


def test_view_carries_last_good_value_on_miss_frame() -> None:
    """§2.2 记录模型消费语义:失读帧(帧 raw 0 + readable False)下视图返回
    BoardState 沿用值——适配器存在的核心语义(批一镜像 + 消费切换闭环);
    回放语料无失读,此语义为 live 申报面。"""
    st = GameState()
    st.gold = 37
    bs = _synth_bs_with(st)
    # 失读帧:raw 0 + readable False(读屏 miss 形态)
    miss = GameState()
    miss.gold = 0
    miss.gold_readable = False
    view = game_state_view(bs, miss)
    assert view.gold == 37, '失读帧消费沿用值,禁 raw 0 兜底入决策'
    assert view.gold_readable is True


def test_view_bootstrap_empty_bs_passes_frame_through() -> None:
    """引导窗(bs 未观察)→ 帧值透传:与旧 ``last_state or GameState()``
    分支同语义,首帧前无行为差。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    fr = GameState()
    fr.gold = 12
    fr.plane = 2
    fr.round_num = 3
    view = game_state_view(bs, fr)
    assert view.gold == 12 and view.plane == 2 and view.round_num == 3


def test_view_hp_is_frame_passthrough_gate_authoritative() -> None:
    """hp 域 = 帧透传(申报):last_state.hp 是 gated_hp 门后消费值
    (ADR-0583 §2.4 同门纪律),BoardState.hp 是门前真值——消费视图取
    帧值(门已施),记录模型保留真值。"""
    st = GameState()
    st.hp = 82
    bs = _synth_bs_with(st)
    fr = GameState()
    fr.hp = 76   # 门后消费值(与 bs 真值不同)
    fr.hp_readable = True
    view = game_state_view(bs, fr)
    assert view.hp == 76, 'hp 消费 = 帧透传(门权威随帧),非记录真值'


def test_view_refresh_cost_policy_none_is_base_not_zero() -> None:
    """§3.3.4 消费策略申报:刷价未读到(None)→ 建模基价显式缺省(原
    ``or 2`` 兜底形态的搬迁归宿,数值恒同);现场识别值直通。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    view = game_state_view(bs, GameState())
    assert view.shop_refresh_cost == 2
    bs.observe(bs.shop_refresh_cost, 1, sig=_sig())   # 长线利好态现场识别值
    assert game_state_view(bs, GameState()).shop_refresh_cost == 1


def test_strategy_input_state_session_none_is_empty_view() -> None:
    """调用面单一源:session None(局外/裸调用)→ 空态视图,与旧
    ``or GameState()`` 分支同语义。"""
    view = strategy_input_state(None)
    assert isinstance(view, GameState)
    assert view.gold == 0 and view.plane == 1


def test_strategy_input_state_reads_board_state(tmp_path) -> None:
    """调用面单一源:正常 session → view(board_state_of(session),
    last_state);BoardState 有值域以记录值为准。"""
    sess = SimpleNamespace(last_state=None)
    bs = board_state_of(sess)
    bs.observe(bs.gold, 55, sig=_sig())
    view = strategy_input_state(sess)
    assert view.gold == 55


# ============================================================ §3.4 单次逻辑写入口


def test_write_logic_writes_confirmed_logic_source() -> None:
    """§3.4 申报豁免写端:单次逻辑写入直接转正(source=logic),并入
    logic_written_fields;之后照受观察覆盖辖(§2.3)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.write_logic(bs.chosen_megastar, '花火', produced_by='CwScreenMegastar',
                   sig=_lsig())
    assert bs.chosen_megastar.value == '花火'
    assert bs.chosen_megastar.source == 'logic'
    assert bs.chosen_megastar in [
        getattr(bs, n) for n in bs.logic_written_fields()]
    # 观察覆盖照常赢(豁免不是免检通道)
    bs.observe(bs.chosen_megastar, '希儿', sig=_sig())
    assert bs.chosen_megastar.value == '希儿'
    assert bs.chosen_megastar.source == 'observation'


def test_write_logic_over_logic_mismatch_still_defects() -> None:
    """§2.3 双向成立:logic 值被观察覆盖且失配 → 缺陷台账照常留证
    (write_logic 产物与 confirm 产物同受观察赢辖)。"""
    consume_defect_sink()
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.write_logic(bs.active_env, '昼之半神概念股', produced_by='x',
                   sig=_lsig())
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        bs.observe(bs.active_env, '战争边疆', sig=_sig())
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert len(rows) == 1 and rows[0]['field'] == 'active_env'


# ============================================================ §3.3.6-8 刷新执行事实组


def test_refresh_execution_paid_increments_paid_and_total() -> None:
    """§3.3.7/§3.3.8:付费刷新 = paid+1 ∧ total+1(RefreshShop 执行回执,
    写入=仅逻辑)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    record_refresh_execution(bs, free=False, frame='p1-r3')
    assert bs.paid_refresh_count.value == 1
    assert bs.total_refresh_count.value == 1
    assert bs.free_refresh_balance.value is None, '付费帧不动免费余额'


def test_refresh_execution_free_gate_skips_paid_count() -> None:
    """§3.3.7 免费帧闸(本批申报核心):免费帧不进付费累计(长线利好触发
    计数载体禁混入免费刷),消耗免费余额 + total 照计。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.write_logic(bs.free_refresh_balance, 2, produced_by='effect',
                   sig=_lsig())
    record_refresh_execution(bs, free=True, frame='p1-r3')
    assert bs.paid_refresh_count.value is None, '免费帧禁写付费计数'
    assert bs.free_refresh_balance.value == 1, '免费余额消耗'
    assert bs.total_refresh_count.value == 1, '全量计数含免费'


def test_refresh_execution_free_balance_floor_zero() -> None:
    """免费余额下限 0(计数器单调域,禁负值漂移)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.write_logic(bs.free_refresh_balance, 1, produced_by='effect',
                   sig=_lsig())
    record_refresh_execution(bs, free=True)
    record_refresh_execution(bs, free=True)
    assert bs.free_refresh_balance.value == 0


# ============================================================ §3.3.1 cost_source 三值归并


@pytest.mark.parametrize('src,group', [
    ('badge', COST_SOURCE_BADGE),
    ('roster', COST_SOURCE_REGISTRY),
    ('roster_fallback', COST_SOURCE_REGISTRY),
])
def test_cost_source_group_merges_three_to_two(src: str, group: str) -> None:
    """§3.3.1/§8.6-9:消费侧三值归并为两域(徽章直读 vs 注册表查表);
    roster_fallback 的「徽章失读」分级只丢在归并面,原值仍在存储。"""
    assert cost_source_group(src) == group


def test_cost_source_group_unknown_is_registry_conservative() -> None:
    """未知值保守归 registry(词表外值 = 上游漂移信号,归因看原值)。"""
    assert cost_source_group('mystery') == COST_SOURCE_REGISTRY


# ============================================================ §3.2.6 派生单一源(ADR-0488)


def test_board_next_tier_of_matches_registry_formula() -> None:
    """§3.2.6/§8.8 准入③:下档阈值派生 = 注册表 tiers 取 >count 最小档;
    obs computed 支与 sim 观测键(ADR-0488)均委托本源(结构锁:函数体
    调用 kernel 单一源,禁第三份推导)。"""
    from sr_od.application.currency_war.data.cw_factions import FACTIONS
    from sr_od.application.currency_war.sim.engine_p1 import (
        _board_next_tier_of as sim_board_next_tier_of,
    )
    board = {'列车同行': 2, '持续伤害': 0}
    expect = {}
    for f, c in board.items():
        tiers = FACTIONS[f].tiers if f in FACTIONS else ()
        nt = next((t for t in tiers if t > c), 0)
        if nt:
            expect[f] = nt
    assert board_next_tier_of(board) == expect
    assert sim_board_next_tier_of(board) == expect, 'sim 键 = 同一派生函数'
    assert board_next_tier_of({}) == {}


def test_sim_bench_full_key_supplied_by_derived_function() -> None:
    """ADR-0488 席满观测键同键供给:合成后的 BoardState 经
    bench_is_full 派生值 = 占用式(同一真值两形态;sim 段内 OR 支)。"""
    st = GameState()
    st.bench = [BenchChar(slot=1, char_id='花火', star=1)] * 9 + [None] * 0
    st.bench = [BenchChar(slot=i + 1, char_id='花火', star=1)
                for i in range(9)]
    bs = _synth_bs_with(st)
    assert bench_is_full(bs) is True
    st2 = GameState()
    st2.bench = [BenchChar(slot=1, char_id='花火', star=1)] + [None] * 8
    bs2 = _synth_bs_with(st2)
    assert bench_is_full(bs2) is False


# ============================================================ §3.5.1 结算覆盖写端


def test_settlement_cover_writes_truth_group() -> None:
    """§3.5.1:结算真值组覆盖 = observation;hp/streak 带方向/gold·level·xp
    仅胜局;settlement 结构同步落。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    apply_settlement_cover(bs, hp_after=76, streak_after=4,
                           killed=True, gold=23, level=6, xp=(3, 10))
    assert bs.hp.value == 76 and bs.hp.source == 'observation'
    assert bs.streak.value == 4, '带方向真值(正=连胜)'
    assert bs.gold.value == 23 and bs.level.value == 6
    assert bs.xp.value == (3, 10)
    s = bs.settlement.value
    assert s is not None and s.hp_after == 76 and s.killed is True


def test_settlement_cover_loss_page_writes_no_win_only_fields() -> None:
    """败局结算页:无收入面板(gold/level/xp 缺席不写,§3.5.1),hp/streak
    真值照覆。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    apply_settlement_cover(bs, hp_after=41, streak_after=-2, killed=False)
    assert bs.hp.value == 41 and bs.streak.value == -2
    assert bs.gold.value is None and bs.level.value is None
    assert bs.xp.value is None
    assert bs.settlement.value.gold is None


def test_settlement_cover_unread_hp_not_written() -> None:
    """hp 失读(结算页 OCR miss)→ 不写(不可信帧不写,§2.2 写入闸),
    不清既有正式值。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.hp, 80, sig=_sig())
    apply_settlement_cover(bs, hp_after=None, streak_after=None)
    assert bs.hp.value == 80 and bs.hp.source == 'observation'


# ============================================================ §6.2/§8.8 局终归档快照


def test_archive_snapshot_keys_and_prov_sparsity() -> None:
    """§8.8 两键形态(ADR-0651 两态制后):bs_prov 只记非默认来源(稀疏化)/
    bs_extra 工程结构+非 None 值(JSON 安全);bs_pending 挂起预期摘要键
    已随两步机制废除退役。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 55, sig=_sig())                       # 默认 observation 无注记 → prov 不记
    bs.write_prior(bs.hp, 82, evidence='prior:adr-0559',
                   sig=_sig())   # prior → prov 记
    bs.carry(bs.gold, frame='p1-r5', sig=_sig())              # carried → prov 记
    bs.observe(bs.node, NodeKey(plane=1, round_num=5, kind='boss'), sig=_sig())
    snap = archive_snapshot(bs)
    assert set(snap) == {'schema_version', 'bs_prov', 'bs_extra'}, \
        '两键形态:bs_pending 已随 ADR-0651 退役'
    assert snap['bs_prov']['hp'] == {'source': 'prior',
                                     'evidence': 'prior:adr-0559'}
    assert snap['bs_prov']['gold']['source'] == 'carried'
    assert 'node' not in snap['bs_prov'], '默认 observation 无注记不入 prov(稀疏化)'
    extra = snap['bs_extra']
    assert extra['bs_schema']['economy'] == 1
    assert extra['values']['gold'] == 55
    assert isinstance(extra['values']['node'], dict), 'dataclass 值 JSON 安全化'
    assert extra['values']['node']['kind'] == 'boss'


# ============================================================ §3.2.5 退役墓碑


def test_read_bench_full_channel_retired_tombstone() -> None:
    """§3.2.5:「备战席已满」警告 OCR 通道退役——墓碑调用即断言失败
    (防复活);席满判定唯一入口 = 派生(批一锁 bench_is_full)。"""
    with pytest.raises(RuntimeError, match='退役'):
        cobs.read_bench_full(None, None)

    with pytest.raises(RuntimeError, match='退役'):
        from sr_od.application.currency_war.operations.cw_screen import (
            cw_screen_prep,
        )
        cw_screen_prep.CwScreenPrep._bench_full_break_round(None, None, None, None, None)


# ============================================================ 扩单件 3:§2.1 载体中继收敛


def test_relay_writes_logic_with_carrier_evidence_when_never_written() -> None:
    """§2.1 载体中继:从未写过的字段 → source=logic + evidence=
    session_carrier(不设第五来源类,禁标 observation)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    assert bs.relay(bs.active_env, '昼之半神概念股', sig=_hsig()) is True
    assert bs.active_env.value == '昼之半神概念股'
    assert bs.active_env.source == 'logic'
    assert bs.active_env.evidence == 'session_carrier'


def test_relay_skips_fields_with_official_value() -> None:
    """§2.1 收敛核心:已有正式值的字段一律跳过——handler 已写的 logic
    禁被中继翻成 observation(§8.1);observation 同样不翻。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.write_logic(bs.active_env, '战争边疆', produced_by='CwScreenInvestEnv',
                   sig=_lsig())
    assert bs.relay(bs.active_env, '昼之半神概念股', sig=_hsig()) is False
    assert bs.active_env.value == '战争边疆', 'handler 真写端值保持'
    assert bs.active_env.source == 'logic', '禁把 logic 翻成 observation'
    assert bs.active_env.evidence is None, '真写端 evidence 不被中继污染'
    bs.observe(bs.active_strategies, ['白银投资'], sig=_sig())
    assert bs.relay(bs.active_strategies, [], sig=_hsig()) is False
    assert bs.active_strategies.source == 'observation'


# ============================================================ 扩单件 1:合成升星预期写端(§3.2.18 修法 a)


def test_detect_merge_upgrade_signature() -> None:
    """§3.2.18 修法 a 触发判定:同名最高星被抬升 = 合成签名(星级只经
    合成上升);普通买新卡/无变化 → False。"""
    from sr_od.application.currency_war.kernel.cw_board_state import (
        detect_merge_upgrade,
    )

    def _mk(bench, deployed=None):
        st = GameState()
        st.bench = bench
        st.deployed = deployed or []
        return st

    c1 = BenchChar(slot=1, char_id='花火', star=1)
    c2 = BenchChar(slot=2, char_id='花火', star=1)
    c3 = BenchChar(slot=3, char_id='花火', star=1)
    cur = _mk([c1, c2, c3])
    proj = _mk([BenchChar(slot=1, char_id='花火', star=2)])
    assert detect_merge_upgrade(cur, proj) is True, '3 合 1 → 同名最高星抬升'
    assert detect_merge_upgrade(cur, _mk([c1, c2, c3])) is False, '无变化'
    assert detect_merge_upgrade(
        _mk([c1]), _mk([c1, BenchChar(slot=2, char_id='花火', star=1)]),
    ) is False, '普通买新卡不抬最高星'
    deployed_old = _mk([], [BenchChar(slot=1, char_id='希儿', star=1)])
    deployed_new = _mk([], [BenchChar(slot=1, char_id='希儿', star=2)])
    assert detect_merge_upgrade(deployed_old, deployed_new) is True, \
        '合成域 = 全场(bench+deployed)'


def test_bench_view_of_slots_positional_mapping() -> None:
    """投影槽位表(0 基 + None 洞)→ BenchView 1:1(槽 i = 物理槽 i+1,
    与 sim 合成口同构);不足容量补空槽。"""
    from sr_od.application.currency_war.kernel.cw_board_state import (
        bench_view_of_slots,
    )
    view = bench_view_of_slots([
        BenchChar(slot=1, char_id='花火', star=2),
        None,
        BenchChar(slot=3, char_id='希儿', star=1),
    ])
    assert view.capacity == 9
    kinds = [s.kind for s in view.slots]
    assert kinds == ['unit', 'empty', 'unit'] + ['empty'] * 6
    assert view.slots[0].unit.star == 2
    assert view.slots[2].unit.slot == 3


def test_merge_projection_direct_write_and_observe_wins() -> None:
    """§3.2.18 修法 a 两态制形态(ADR-0651):BuyCard 合成升星投影经
    write_logic **直写 bench**(策略器立即可读);下一备战帧实读覆盖
    (观察赢)——一致静默,失配 = 投影 bug 缺陷留证后修推算代码。"""
    from sr_od.application.currency_war.kernel.cw_board_state import (
        bench_view_of_slots,
        consume_defect_sink,
        set_defect_sink,
    )
    consume_defect_sink()
    proj_bench = [BenchChar(slot=1, char_id='花火', star=2)] + [None] * 8
    proj_view = bench_view_of_slots(proj_bench)
    real_view = bench_view_of_slots([BenchChar(slot=1, char_id='花火', star=2)])
    # 一致路径:逻辑直写 → 字段立即可读;同值实读覆盖 = 静默
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.write_logic(bs.bench, proj_view, produced_by='BuyCard', sig=_lsig())
    assert bs.bench.value is proj_view and bs.bench.source == 'logic', \
        '投影直写:策略器立即可读(ADR-0651)'
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        bs.observe(bs.bench, real_view, sig=_sig())
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert rows == [], '投影与实读一致 = 零缺陷行'
    assert bs.bench.source == 'observation', '实读后来源翻 observation(正常)'
    # 失配路径:观察赢覆盖真值 + 缺陷留证(失配 = 推算 bug,修推算代码)
    bs2 = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs2.observe(bs2.bench, real_view, sig=_sig())
    bs2.write_logic(bs2.bench, bench_view_of_slots(
        [BenchChar(slot=1, char_id='花火', star=1)] + [None] * 8),
        produced_by='BuyCard', sig=_lsig())
    rows2: list[dict] = []
    set_defect_sink(rows2.append)
    try:
        bs2.observe(bs2.bench, real_view, sig=_sig())
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert len(rows2) == 1, '失配留证(kind=observe_vs_logic_mismatch)'
    assert rows2[0]['kind'] == 'observe_vs_logic_mismatch'
    assert bs2.bench.value == real_view \
        and bs2.bench.source == 'observation', \
        '观察赢:实读覆盖逻辑值(推算 bug 不挂账,留证修码)'


# ============================================================ 扩单件 4:parse_streak 失读 None 化(§8.8)


def test_parse_streak_miss_is_none_real_zero_is_zero() -> None:
    """§8.8:失读 → None(与 read_hp 100 假值同型消除);'连胜×0' = 真 0
    (方向真值,fixture 核实 2026-08-11),两者分写。"""
    from sr_od.application.currency_war.obs.cw_settlement_obs import (
        parse_streak,
    )
    assert parse_streak(['挑战结束', '数据统计']) is None, '失读非 0'
    assert parse_streak(['连胜×0']) == 0, '真 0 保留'
    assert parse_streak(['连败×2']) == -2


def test_settlement_observation_half_preserves_streak_on_miss() -> None:
    """失读守卫:obs.streak None → session.last_streak 跳过沿用(旧行为
    失读写 0 = 连胜/连败假复位);真值照写。"""
    from sr_od.application.currency_war.kernel.cw_performance import (
        RoundOutcome,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait import (
        _write_settlement_observation,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    def _obs(streak):
        return RoundOutcome(round_num=2, plane=1, node_type='普通战斗',
                            comp_tag='t', streak=streak)

    sess = StrategySession()
    sess.last_streak = 4
    _write_settlement_observation(sess, _obs(None), None)
    assert sess.last_streak == 4, '失读跳过:禁假复位'
    _write_settlement_observation(sess, _obs(-2), None)
    assert sess.last_streak == -2, '真值照写'


# ============================================================ 批次二返工批修复锁(P2-1/P3-x)

def test_bench_view_from_obs_empty_is_miss_not_full() -> None:
    """P2-1:备战席 SIFT 空集 = 失读(overlay 残留/动画帧/识别退化)≠实席
    全空——值构造返 None(调用方走 carried,§2.2 处置①;宁缺勿造),禁把
    「9 槽全空」当 observation 入记录(席空数派生误报 free=9/挂起合成升星
    预期被空视图误清);非空 = 槽位保序映射;越界条目丢弃(读链漂移)。"""
    from sr_od.application.currency_war.kernel.cw_board_state import (
        bench_view_from_obs,
    )
    assert bench_view_from_obs([]) is None, '空集 = 失读,禁合成全空视图'
    assert bench_view_from_obs(None) is None
    view = bench_view_from_obs([
        BenchChar(slot=2, char_id='花火', star=2),
        BenchChar(slot=0, char_id='越界角色', star=1),   # 越界:丢弃
        BenchChar(slot=11, char_id='越界角色2', star=1),  # 越界:丢弃
    ])
    assert view is not None
    assert [s.kind for s in view.slots] == ['empty', 'unit'] + ['empty'] * 7, \
        '槽位保序(物理槽 2);越界条目不落槽'
    assert view.slots[1].unit is not None and view.slots[1].unit.star == 2


def test_prep_bench_obs_miss_guard_and_tome_choice_wiring() -> None:
    """接线存在性烟雾(README 第 8 条容忍档;事故出处 = 批次二落地审 P2-1
    「空集写 9 槽全空假值」、P3-6「chosen_tome 写端缺位」、P3-10「特效窗
    核对噪声」):①prep 观察块经 bench_view_from_obs 守卫且失读分支走
    carry;②bookcard 选卡落地写 chosen_tome(write_logic,§3.4.5);
    ③prep 核对点过特效窗门(is_merge_effect_window,窗内顺延核对)。"""
    import inspect

    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_bookcard,
        cw_screen_prep,
    )
    prep_src = inspect.getsource(cw_screen_prep)
    assert 'bench_view_from_obs(obs.bench_chars)' in prep_src, \
        'P2-1:守卫函数接线在位'
    assert '_bs_obs.carry' in prep_src, 'P2-1:失读分支 carry(非 observe)'
    assert 'is_merge_effect_window(screen)' in prep_src, \
        'P3-10:核对点特效窗门在位'
    book_src = inspect.getsource(cw_screen_bookcard)
    assert '.chosen_tome' in book_src and 'write_logic' in book_src, \
        'P3-6:chosen_tome 写端接线在位'


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


def test_settlement_cover_carries_progress_delta() -> None:
    """P3-3:progress_delta 经覆盖写端落 settlement 结构(挑战进度带符号
    真值;battle_wait 调用点传参为接线半,本锁辖函数半)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    apply_settlement_cover(bs, hp_after=76, streak_after=4, killed=True,
                           progress_delta=2, gold=23)
    assert bs.settlement.value is not None \
        and bs.settlement.value.progress_delta == 2
    apply_settlement_cover(bs, hp_after=70, streak_after=-1, killed=False,
                           progress_delta=-22)
    assert bs.settlement.value.progress_delta == -22, '败局负增量照落'


def test_refresh_execution_evidence_carries_round_key() -> None:
    """P3-2:刷新执行逻辑写入的 evidence 落轮键(refresh_exec@<frame>,
    归因留证面;write_logic evidence 形参在册)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    record_refresh_execution(bs, free=False, frame='p1-r3')
    assert bs.total_refresh_count.evidence == 'refresh_exec@p1-r3'
    assert bs.paid_refresh_count.evidence == 'refresh_exec@p1-r3'
    record_refresh_execution(bs, free=True, frame='p2-r1')
    assert bs.total_refresh_count.evidence == 'refresh_exec@p2-r1', \
        '免费帧 total 也带当次轮键'


# ============================================================ 四事件屏 chosen_* 接线锁(设计 §3.4.5 余屏写端)

def _op_with_session(op_cls: type, sess: object) -> object:
    """``__new__`` 绕过 op 构造(SrContext 全量依赖不可裸建);只喂四屏
    chosen 记录面读取的唯一 ctx 依赖面 = cw_match.session。"""
    op = op_cls.__new__(op_cls)
    op.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=sess))
    return op


def test_encounter_chosen_written_on_true_pick_only() -> None:
    """遭遇屏 chosen_encounter 接线锁(§3.4.5 余屏写端;先例形态 = P3-6
    chosen_tome 锁):①写端接线在位且挂在出口验真通过分支;②真选写
    (难度档, 奖励文本)原名口径、source=logic;③fallback(无会话/候选
    未读到/越界)不写。"""
    import inspect

    from sr_od.application.currency_war.kernel.cw_events import EncounterOption
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_encounter,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    src = inspect.getsource(cw_screen_encounter)
    assert '.chosen_encounter' in src and 'write_logic' in src, \
        '遭遇屏 chosen_encounter 写端接线在位'
    assert 'if rs.is_success:' in src, '写在出口验真通过分支(非点击即写)'
    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2']),
            EncounterOption(idx=1, difficulty=3, rewards=['随机4费×3'])]
    sess = StrategySession()
    op = _op_with_session(cw_screen_encounter.CwScreenEncounter, sess)
    op._record_chosen(sess, opts, 1)
    bs = board_state_of(sess)
    assert bs.chosen_encounter.value == (3, '随机4费×3'), '值=(难度档,奖励文本)原名口径'
    assert bs.chosen_encounter.source == 'logic', '单次逻辑写入(source=logic)'
    sess2 = StrategySession()
    op2 = _op_with_session(cw_screen_encounter.CwScreenEncounter, sess2)
    op2._record_chosen(None, opts, 0)     # 无策略会话 = 盲选
    op2._record_chosen(sess2, [], 0)      # 候选未读到
    op2._record_chosen(sess2, opts, 5)    # 决策越界
    assert board_state_of(sess2).chosen_encounter.value is None, 'fallback 不写'


def test_supply_chosen_written_from_stash_after_exit_only() -> None:
    """补给节点 chosen_supply 接线锁(§3.4.5;列数动态 → 值=选定列三元组
    原文,不做列数假定):①真选暂存 → 出口验真方法写 (角色,装备,有钻石)
    且写后取走暂存;②暂存空(兜底点卡/刷新轮)不写;③pop 取走即清
    (重入轮入口先弃,防陈旧选跨轮/跨节点误写);无 match 安全空转。"""
    import inspect

    from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    src = inspect.getsource(cw_screen_supply_node)
    assert '.chosen_supply' in src and 'write_logic' in src, \
        '补给节点 chosen_supply 写端接线在位'
    assert '_pending_chosen_supply' in src, '选定暂存中转在位(出口验真后写)'
    sess = StrategySession()
    op = _op_with_session(cw_screen_supply_node.CwScreenSupplyNode, sess)
    exec_state_of(sess)._pending_chosen_supply = ('希儿', '星币收集器', True)
    op._record_chosen_supply()
    bs = board_state_of(sess)
    assert bs.chosen_supply.value == ('希儿', '星币收集器', True), '值=选定列三元组原名'
    assert bs.chosen_supply.source == 'logic', '单次逻辑写入(source=logic)'
    assert exec_state_of(sess)._pending_chosen_supply is None, \
        '写后取走暂存(不跨节点残留)'
    sess2 = StrategySession()
    op2 = _op_with_session(cw_screen_supply_node.CwScreenSupplyNode, sess2)
    op2._record_chosen_supply()
    assert board_state_of(sess2).chosen_supply.value is None, \
        '暂存空(兜底/刷新轮)不写'
    # pop 取走即清(重入轮防陈旧语义)
    exec_state_of(sess)._pending_chosen_supply = ('符玄', '旧选定', False)
    assert op._pop_pending_chosen_supply() == ('符玄', '旧选定', False)
    assert exec_state_of(sess)._pending_chosen_supply is None
    # 无 match(测试/离线无会话)→ pop/写均安全空转不炸
    op3 = _op_with_session(cw_screen_supply_node.CwScreenSupplyNode, None)
    op3.ctx = SimpleNamespace(cw_match=None)
    assert op3._pop_pending_chosen_supply() is None
    op3._record_chosen_supply()


def test_expert_chosen_written_on_card_pick_only() -> None:
    """专家邀请函 chosen_expert 接线锁(§3.4.5):卡分支写羁绊原文名;
    「现金为王」兜底分支不写(该事实由 ConfirmExpertCash +4 金到账登记
    通道承载,照旧不动)——真选守卫照 chosen_tome 式。"""
    import inspect

    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_expert_invite,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    src = inspect.getsource(cw_screen_expert_invite)
    assert '.chosen_expert' in src and 'write_logic' in src, \
        '专家邀请函 chosen_expert 写端接线在位'
    assert 'ConfirmExpertCash' in src, '现金为王 +4 金到账登记通道保持(照旧)'
    bonds: list[str | None] = ['仙舟', None, '贝洛伯格', None]
    sess = StrategySession()
    op = _op_with_session(cw_screen_expert_invite.CwScreenExpertInvite, sess)
    op._record_chosen_expert(0, bonds)
    assert board_state_of(sess).chosen_expert.value == '仙舟', '值=卡羁绊原文名'
    assert board_state_of(sess).chosen_expert.source == 'logic', \
        '单次逻辑写入(source=logic)'
    sess2 = StrategySession()
    op2 = _op_with_session(cw_screen_expert_invite.CwScreenExpertInvite, sess2)
    op2._record_chosen_expert(-1, bonds)   # 现金为王兜底
    op2._record_chosen_expert(9, bonds)    # 越界(防御面)
    op2._record_chosen_expert(1, bonds)    # 羁绊缺失(防御面)
    assert board_state_of(sess2).chosen_expert.value is None, \
        '兜底/越界/羁绊缺失不写'


def test_wish_chosen_written_with_objective_text_only() -> None:
    """祈愿试炼 chosen_wish 接线锁(§3.4.5):objective 原文名读到才写;
    未读到(None)/选中槽文本空 = 盲选 fallback 不写——真选守卫照
    chosen_tome 式。"""
    import inspect

    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_wish_trial,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    src = inspect.getsource(cw_screen_wish_trial)
    assert '.chosen_wish' in src and 'write_logic' in src, \
        '祈愿试炼 chosen_wish 写端接线在位'
    assert 'self._record_chosen(objs, pick_idx)' in src, \
        '写在出口验真(标识消失)之后的收案路径'
    sess = StrategySession()
    op = _op_with_session(cw_screen_wish_trial.CwScreenWishTrial, sess)
    op._record_chosen(['累计刷新10次', '', ''], 0)
    assert board_state_of(sess).chosen_wish.value == '累计刷新10次', \
        '值=objective 原文名'
    assert board_state_of(sess).chosen_wish.source == 'logic', \
        '单次逻辑写入(source=logic)'
    sess2 = StrategySession()
    op2 = _op_with_session(cw_screen_wish_trial.CwScreenWishTrial, sess2)
    op2._record_chosen(None, 0)                  # objective 未读到
    op2._record_chosen(['', '难度3+战斗'], 0)    # 选中槽文本空
    op2._record_chosen(['累计刷新10次'], 7)      # 越界
    assert board_state_of(sess2).chosen_wish.value is None, 'fallback 不写'
