"""GameState 容器合同（kernel 判策核心的第一层：状态怎么写、怎么读、怎么记账）。

被测模块：``kernel/cw_game_state.py``（容器+写入口+映射+终局）、
``kernel/cw_vocab.py``（动作词表与局内模拟 ``simulate``）、
``kernel/cw_strategy_session.py``（会话载体）。

合同面（全部从源码推导，§节号 = 源码 docstring 引用的设计条款）：
- §1 写入口六通道：observe / carry / write_prior / leave_screen /
  write_logic / relay 各自的接受域与拒绝口径；
- §2 版本与状态流水：写占版本、读不占、obs_event 占版本零状态变更、
  同值重写 same_value 旗标、行自足快照、局外（无 run_id）拒写行；
- §3 快照：full_state_snapshot 值域/来源注记/同态同形；
- §4 画面上下文与节点域(动作上报化切换后口径:漏斗只写上下文对;
  BOSS 类型直定迁移);
- §5 合成口与新旧映射（sim 合成、ShopCard 往返、bench/deployed 槽表）；
- §6 终局与结算（write_match_final 幂等、词汇封闭）。

退役面（审计判决删除）：§7 动作模拟两锁（test_simulate_buy_card_moves_
shop_to_bench / test_simulate_level_up_costs_and_levels,连 _mk_state
助手）——锁的 ``cw_vocab.simulate`` 全仓零生产消费（S9/S10 后动作链
全走 apply_*_logic 直锁,商店动作状态面 = test_cw_transfer_golden 与
test_cw_shop_projection_logic 的活函数锁),src 指针对账零命中。
§8 执行状态延迟绑定锁（test_exec_state_lazy_binding）随 ExecState
载体退役删除——载体类与访问口整体消失（局内事实宿主 = GameState
容器）,无可锁语义。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    GameState,
    bench_free_slots,
    bench_is_full,
    board_next_tier_of,
    node_ordinal_of,
    slot_occupies,
    write_match_final,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig as Sig,
)


def _sig() -> Sig:
    return Sig(family='obs', actor='TestSigWriter', mode='read')


def _lsig() -> Sig:
    return Sig(family='logic_action', actor='TestSigWriter', mode='compute')


def _hsig() -> Sig:
    return Sig(family='logic_hook', actor='TestSigWriter', mode='compute')


def _gs() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


# ============================================================ §1 写入口六通道

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


# ============================================================ §1 写入口六通道
# (先验前缀/离屏辖域/逻辑直写/载体中继四通道合同正本 =
#  test_cw_game_state.py 与 test_cw_game_state_consume.py 的同名行为锁,
#  本文件不再留第二份;观察通道见上。)

def test_cross_instance_field_reference_rejected() -> None:
    """身份匹配(§8.4):target 须是本单例字段现引用,跨单例引用 = 写丢
    事故形态,显式炸错禁静默。"""
    gs_a, gs_b = _gs(), _gs()
    with pytest.raises(KeyError):
        gs_a.observe(gs_b.gold, 1, sig=_sig())


# ============================================================ §2 版本与状态流水

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
    """match_facts 域版本 bump 落行(接管域迭代 2026-09-20-takeover-intel-pipeline:
    接管补采计数/完成闩两字段退役 = 域内容变更,gs_schema 域版本 3;
    银狼升星记账批 2026-09-20-yinlang-starup-accounting 新增
    lv999_cost_tier = 域版本 4):
    DEFAULT_GS_SCHEMA 声明值 = 4,写行内嵌快照
    state.gs_schema 同值(行行自足,判读不前溯可查域版本)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        DEFAULT_GS_SCHEMA,
        set_run_id_provider,
        set_state_journal_sink,
    )
    assert DEFAULT_GS_SCHEMA['match_facts'] == 4
    gs = _gs()
    run_sink: list[dict] = []
    set_state_journal_sink(run_sink.append)
    set_run_id_provider(lambda: 'run_probe')
    try:
        gs.write_logic(gs.resumed_match, True, produced_by='ResumeAttach',
                       evidence='takeover_resumed', sig=_hsig())
    finally:
        set_state_journal_sink(None)
        set_run_id_provider(None)
    assert len(run_sink) == 1
    row = run_sink[0]
    assert row['row'] == 'write' and row['field'] == 'resumed_match'
    assert row['after'] is True
    assert row['state']['gs_schema']['match_facts'] == 4, \
        '域版本 bump 落行(行内 state 快照携带)'
    assert row['sig']['family'] == 'logic_hook', '接管协议渠道③签名随行'


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


# ============================================================ §3 快照

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


# ============================================================ §4 画面上下文与节点域(动作上报化切换后口径)

def test_screen_context_writes_pair_only_no_advance() -> None:
    """漏斗瘦身(迭代 2026-09-20-node-advance-action-report design §2.4
    攻击 B1):observe_screen_context 只写上下文对(prev/current)——推进域
    (node_ord/hist)零触碰,四推断腿已退役;节点推进唯一落账入口 =
    advance_node_effective(动作上报/观察锚定)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        SCREEN_PREP_FRAME,
    )
    gs = _gs()
    gs.observe_screen_context(SCREEN_PREP_FRAME, sig=_sig())
    assert gs.current_screen.value == SCREEN_PREP_FRAME, '上下文对写入'
    assert gs.node_ord.value is None and gs.node_hist_ord is None, \
        '备战帧上下文零推进(腿已退役)'
    other = _gs()
    other.observe_screen_context('货币战争-战斗等待', sig=_sig())
    other.observe_screen_context('货币战争-补给', sig=_sig())
    assert other.node_ord.value is None and other.node_hist_ord is None, \
        '战斗等待→补给(prev∈旧守卫族形态)零推进(弹窗腿已退役)'


def test_boss_briefing_report_types_hist_node() -> None:
    """BOSS 类型直定迁移(design §2.5 表):简报屏上报经 kernel report
    直定 boss 类型,目标 = 现 hist;序号推进半部已退役(简报上报零
    node_ord 写);hist 未推进 = 零写禁猜。"""
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
    assert gs.node_ord.value is None, '简报上报零序号写(序号半部已退役)'
    observe_node_anchor(gs, node_ordinal_of(2, 1),
                        trigger_screen='货币战争-备战', actor='TestAnchor')
    report_screen_boss_briefing_obs(
        gs, CwScreenBossBriefingObs(on_screen=True))
    assert gs.node.value is not None \
        and gs.node.value.kind == 'boss', '类型随简报证据落账(boss)'
    assert (gs.node.value.plane, gs.node.value.round_num) == (2, 1), \
        '目标 = 现 hist 反解位(禁写死 round=9)'


# ============================================================ §5 合成口与映射
# (sim 合成口合同锁正本 = test_cw_game_state.py sim 合成口组,含
#  「node_ord 不写」腿;ShopCard 往返 / bench-deployed 槽表转换的合同锁
#  正本 = test_cw_game_state.py「容器视图转换」组;此处不重复。)


def test_node_ordinal_and_tier_helpers() -> None:
    """坐标系纯函数:节点序(位面内序 + 前面位面累计);棋盘阵营升档
    (同阵营 ≥2 才有下一档);bench 空位语义。"""
    assert (node_ordinal_of(1, 1), node_ordinal_of(1, 9),
            node_ordinal_of(2, 1)) == (1, 9, 10)
    assert board_next_tier_of({'仙舟': 2, '联盟': 1}) == {'仙舟': 3}
    assert slot_occupies('bench') and slot_occupies('deployed')
    gs = _gs()
    assert bench_free_slots(gs) is None, 'bench 未读 = 诚实缺位(非 0)'
    assert bench_is_full(gs) is None


# ============================================================ §6 终局与结算

def test_write_match_final_idempotent() -> None:
    """终局行(G12 写前查重):首写 True,同段二写 no-op 返 False
    (终局防重)。"""
    gs = _gs()
    assert write_match_final(gs, final_type='loss', plane=1) is True
    assert write_match_final(gs, final_type='loss', plane=1) is False


# (结算覆盖合同锁正本 = test_cw_game_state_consume.py 三件
#  test_settlement_cover_writes_truth_group / _loss_page / _unread_hp。)


# (§7 动作模拟两锁已删——simulate 零生产消费,审计判决;活转移函数
#  test_cw_transfer_golden / test_cw_shop_projection_logic 直锁。)


# (§8 执行状态延迟绑定锁已删——ExecState 载体连同访问口整体退役,
#  局内事实宿主 = GameState 容器,无可锁语义。)


# ============================================================ fixtures

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


# ============================================================ §9 渠道签名封闭集(渠道门,自 state_journal 归并)

def test_channel_family_closed_set() -> None:
    """§3.2.1/§3.2.4 硬约束 2 签名门两分支:①family 封闭集 {obs,
    logic_action, logic_hook},集外 = 红;②per-family 模态封闭(obs 族子模
    = read/carried/prior/synthesized,logic 两族恒 compute,集外 = 红)。
    actor 无白名单闸(仅遥测身份标注)。"""
    for family in ('obs', 'logic_action', 'logic_hook'):
        assert Sig(family=family, actor='cw_observation').family == family
    with pytest.raises(ValueError):
        Sig(family='event', actor='x')
    with pytest.raises(ValueError):
        Sig(family='hook', actor='x')
    # ② per-family 模态封闭
    for mode in ('read', 'carried', 'prior', 'synthesized'):
        Sig(family='obs', actor='cw_observation', mode=mode)
    with pytest.raises(ValueError):
        Sig(family='obs', actor='cw_observation', mode='compute')
    for family in ('logic_action', 'logic_hook'):
        Sig(family=family, actor='CwScreenPrep', mode='compute')
        with pytest.raises(ValueError):
            Sig(family=family, actor='CwScreenPrep', mode='read')
