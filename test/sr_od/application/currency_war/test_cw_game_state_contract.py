"""GameState 容器合同（kernel 判策核心的第一层：状态怎么写、怎么读、怎么记账）。

被测模块：``kernel/cw_game_state.py``（容器+写入口+映射+终局）、
``kernel/cw_vocab.py``（动作词表与局内模拟 ``simulate``）、
``kernel/cw_strategy_session.py``（会话载体）、``kernel/cw_exec_state.py``
（执行状态延迟绑定）。

合同面（全部从源码推导，§节号 = 源码 docstring 引用的设计条款）：
- §1 写入口六通道：observe / carry / write_prior / leave_screen /
  write_logic / relay 各自的接受域与拒绝口径；
- §2 版本与状态流水：写占版本、读不占、obs_event 占版本零状态变更、
  同值重写 same_value 旗标、行自足快照、局外（无 run_id）拒写行；
- §3 快照：full_state_snapshot 值域/来源注记/同态同形；
- §4 画面上下文 → 节点派生（四腿代表行 + 去重 + 冲突留证）；
- §5 合成口与新旧映射（sim 合成、ShopCard 往返、bench/deployed 槽表）；
- §6 终局与结算（write_match_final 幂等、词汇封闭）；
- §7 动作模拟（simulate 对买/卖/刷新/升级的状态迁移）；
- §8 会话与执行状态（StrategySession 镜像字段、ExecState 延迟绑定）。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_exec_state import (
    bind_exec_state,
    exec_state_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BENCH_CAPACITY_DEFAULT,
    BS_SCHEMA_VERSION,
    GameState,
    bench_free_slots,
    bench_is_full,
    board_next_tier_of,
    node_ordinal_of,
    register_sig_actors,
    slot_occupies,
    synthesize_from_game_state,
    write_match_final,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig as Sig,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BenchChar,
    BuyCard,
    CwSimFrame,
    LevelUpShop,
    RefreshShop,
    SellBench,
    ShopCard,
    simulate,
)

register_sig_actors('TestSigWriter')


def _sig() -> Sig:
    return Sig(family='obs', actor='TestSigWriter', mode='read')


def _lsig() -> Sig:
    return Sig(family='logic_action', actor='TestSigWriter', mode='compute')


def _hsig() -> Sig:
    return Sig(family='logic_hook', actor='TestSigWriter', mode='compute')


def _bs() -> GameState:
    return GameState(schema_version=BS_SCHEMA_VERSION)


# ============================================================ §1 写入口六通道

def test_observe_writes_and_overrides() -> None:
    """观察通道:亲眼看 → source=observation,覆盖旧值;value=None 拒绝
    (§2.2 失读不是观察值,禁清正式值);渠道面校验 = 观察 口 只收 obs 族。"""
    bs = _bs()
    bs.observe(bs.gold, 37, sig=_sig())
    assert bs.gold.value == 37 and bs.gold.source == 'observation'
    bs.observe(bs.gold, 40, sig=_sig())
    assert bs.gold.value == 40
    with pytest.raises(ValueError, match='observe 不接受 None'):
        bs.observe(bs.gold, None, sig=_sig())
    with pytest.raises(ValueError, match="不属本写入口合法族"):
        bs.observe(bs.gold, 1, sig=_lsig())


def test_carry_carries_good_value_and_skips_never_read() -> None:
    """失读处置①(§2.2):沿用上次好值,evidence=carried:<帧>;
    从未读字段(机制性 None)→ no-op 不占版本不换来源(不造假历史)。"""
    bs = _bs()
    bs.observe(bs.gold, 30, sig=_sig())
    v_before = bs.current_version()
    bs.carry(bs.gold, frame='p1-r2', sig=_sig())
    assert bs.gold.source == 'carried'
    assert bs.gold.evidence == 'carried:p1-r2'
    assert bs.gold.value == 30
    assert bs.current_version() == v_before + 1
    hp_version = bs.current_version()
    bs.carry(bs.hp, frame='p1-r2', sig=_sig())
    assert bs.hp.source == 'observation' and bs.hp.value is None
    assert bs.current_version() == hp_version, '从未读 carry 不占版本'


# ============================================================ §1 写入口六通道
# (先验前缀/离屏辖域/逻辑直写/载体中继四通道合同正本 =
#  test_cw_game_state.py 与 test_cw_game_state_consume.py 的同名行为锁,
#  本文件不再留第二份;观察通道见上。)

def test_cross_instance_field_reference_rejected() -> None:
    """身份匹配(§8.4):target 须是本单例字段现引用,跨单例引用 = 写丢
    事故形态,显式炸错禁静默。"""
    bs_a, bs_b = _bs(), _bs()
    with pytest.raises(KeyError):
        bs_a.observe(bs_b.gold, 1, sig=_sig())


# ============================================================ §2 版本与状态流水

def test_versions_monotonic_reads_do_not_consume() -> None:
    """版本语义(§3.2.2):写占版本;读(current_version)不占;
    carry 未读字段不占(no-op)。"""
    bs = _bs()
    assert bs.current_version() == 0
    bs.observe(bs.gold, 1, sig=_sig())
    v1 = bs.current_version()
    assert v1 == 1
    assert bs.current_version() == v1, '读不占版本'
    bs.observe(bs.gold, 2, sig=_sig())
    assert bs.current_version() == v1 + 1


def test_journal_rows_self_contained_and_run_gated(journal_sink) -> None:
    """状态流水行(§3.2.3):写入行带 v/ts/run_id/field/after/自足 state 快照/
    sig;run_id 空 = 局外写入,拒写行(诚实缺失,不写假行)。"""
    bs = _bs()
    bs.observe(bs.gold, 5, sig=_sig())
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
        bs.observe(bs.hp, 70, sig=_sig())
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
    bs = _bs()
    bs.observe(bs.gold, 9, sig=_sig())
    run_sink: list[dict] = []
    set_state_journal_sink(run_sink.append)
    set_run_id_provider(lambda: 'run_probe')
    try:
        bs.observe(bs.gold, 9, sig=_sig())
    finally:
        set_state_journal_sink(None)
        set_run_id_provider(None)
    assert bs.current_version() == 2
    assert run_sink[-1]['same_value'] is True


def test_obs_event_consumes_version_without_state_change(journal_sink) -> None:
    """观察事件行(行型 2):同流占版本、零 Field 变更;事件词表封闭
    (arbitrate|miss|popup),集外炸错。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        OBS_EVENT_EVENTS,
        set_run_id_provider,
        set_state_journal_sink,
    )
    assert OBS_EVENT_EVENTS == ('arbitrate', 'miss', 'popup')
    bs = _bs()
    bs.observe(bs.gold, 3, sig=_sig())
    v = bs.current_version()
    run_sink: list[dict] = []
    set_state_journal_sink(run_sink.append)
    set_run_id_provider(lambda: 'run_probe')
    try:
        bs.note_obs_event('arbitrate', 'hp', {'old': 1, 'new': 2},
                          verdict='冲突', sig=_sig())
    finally:
        set_state_journal_sink(None)
        set_run_id_provider(None)
    assert bs.current_version() == v + 1, 'obs_event 占版本'
    assert bs.gold.value == 3, '零状态变更'
    assert run_sink[-1]['row'] == 'obs_event'
    with pytest.raises(ValueError, match='集外'):
        bs.note_obs_event('bogus', 'hp', None, sig=_sig())


# ============================================================ §3 快照

def test_full_state_snapshot_shape() -> None:
    """自足快照(§3.2.3):values 只收非 None;prov 记非默认来源
    (source≠observation 或 evidence 非 None);同态同形 = 同内容快照逐键一致。"""
    bs = _bs()
    bs.observe(bs.gold, 30, sig=_sig())
    bs.write_logic(bs.hp, 70, produced_by='p', sig=_lsig())
    snap = bs.full_state_snapshot()
    assert snap['values']['gold'] == 30 and snap['values']['hp'] == 70
    assert 'hp' in snap['prov'] and snap['prov']['hp']['source'] == 'logic'
    assert 'gold' not in snap['prov'], 'observation 无 evidence 不进 prov'
    bs2 = _bs()
    bs2.observe(bs2.gold, 30, sig=_sig())
    bs2.write_logic(bs2.hp, 70, produced_by='p', sig=_lsig())
    assert bs2.full_state_snapshot() == snap, '同态同形'


# ============================================================ §4 画面上下文 → 节点派生

def test_screen_context_prep_leg_writes_authoritative_node() -> None:
    """备战腿(规则①):干净备战画面(SCREEN_PREP_FRAME)+ 顶栏
    (plane, round) 读数 → 节点域权威值;非备战画面不触发。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        SCREEN_PREP_FRAME,
    )
    bs = _bs()
    bs.observe_screen_context(SCREEN_PREP_FRAME, phase_round=(1, 1),
                              sig=_sig())
    assert bs.node_ord.value == 1, '备战腿落序键(逻辑层)'
    assert bs.node.value is None, '类型未定型,组合键不写'
    other = _bs()
    other.observe_screen_context('货币战争-战斗等待', phase_round=(1, 1),
                                 sig=_sig())
    assert other.node.value is None, '非备战画面不触发备战腿'


def test_screen_context_same_frame_revisit_does_not_readvance() -> None:
    """重复采到同值不再推进(候选 ≤ hist 不写不锚,去重键 =
    (run_id, effective_ord);同序恰一次推进)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        SCREEN_PREP_FRAME,
    )
    bs = _bs()
    bs.observe_screen_context(SCREEN_PREP_FRAME, phase_round=(1, 2),
                              sig=_sig())
    first = bs.node.value
    bs.observe_screen_context(SCREEN_PREP_FRAME, phase_round=(1, 2),
                              sig=_sig())
    assert bs.node.value == first, '同帧重采不再推进'


def test_screen_context_popup_leg_infers_and_types() -> None:
    """弹窗腿(规则④)+类型派生:守卫前置画面(战斗等待)后进专属弹窗
    (补给) → 推断推进 + 类型直定 supply。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        SCREEN_PREP_FRAME,
    )
    bs = _bs()
    bs.observe_screen_context(SCREEN_PREP_FRAME, phase_round=(1, 2),
                              sig=_sig())
    prep_node = bs.node.value
    bs.observe_screen_context('货币战争-战斗等待', sig=_sig())
    bs.observe_screen_context('货币战争-补给', sig=_sig())
    assert bs.node.value is not None
    assert bs.node.value.kind == 'supply'
    assert bs.node.value != prep_node


def test_screen_context_boss_brief_leg_advances_and_types() -> None:
    """BOSS 简报腿(规则③,确定性):0p 被采到 → 当前节点+1 且类型=boss
    (禁写死 round=9,boss 序位随位面格数漂移)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        SCREEN_BOSS_BRIEFING,
        SCREEN_PREP_FRAME,
    )
    bs = _bs()
    bs.observe_screen_context(SCREEN_PREP_FRAME, phase_round=(2, 1),
                              sig=_sig())
    before = bs.node_ord.value
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING, sig=_sig())
    assert bs.node_ord.value == before + 1, '当前节点+1(禁写死 round=9)'
    assert bs.node.value is not None and bs.node.value.kind == 'boss', '类型随简报证据同批落账'


def test_plane_transition_leg_advances_plane() -> None:
    """位面过渡腿(规则②,确定性):0q 被采到 → 逻辑节点 =
    (当前位面+1, 1)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        SCREEN_PLANE_TRANSITION,
        SCREEN_PREP_FRAME,
    )
    bs = _bs()
    bs.observe_screen_context(SCREEN_PREP_FRAME, phase_round=(1, 5),
                              sig=_sig())
    bs.observe_screen_context(SCREEN_PLANE_TRANSITION, sig=_sig())
    assert bs.node_ord.value == node_ordinal_of(2, 1), '逻辑节点 = (plane+1, 1)'


# ============================================================ §5 合成口与映射

def test_synthesize_writes_observation_with_sim_evidence() -> None:
    """sim 合成口(§2.6 域覆盖对齐):真值域直写 source=observation +
    evidence=sim:synthesized@<round>;缺席域不写(禁假值)。"""
    st = CwSimFrame()
    st.plane, st.round_num, st.gold, st.level = 2, 3, 55, 7
    bs = _bs()
    synthesize_from_game_state(bs, st, at_round='p2-r3')
    assert bs.gold.value == 55
    assert bs.gold.source == 'observation'
    assert bs.gold.evidence == 'sim:synthesized@p2-r3'
    assert bs.level.value == 7
    assert bs.node_ord.value is None, '合成口不写节点序(节点由观察链派生)'


# ============================================================ §5 合成口与映射
# (ShopCard 往返 / bench-deployed 槽表转换的合同锁正本 =
#  test_cw_game_state.py「容器视图转换」组;此处不重复。)


def test_node_ordinal_and_tier_helpers() -> None:
    """坐标系纯函数:节点序(位面内序 + 前面位面累计);棋盘阵营升档
    (同阵营 ≥2 才有下一档);bench 空位语义。"""
    assert (node_ordinal_of(1, 1), node_ordinal_of(1, 9),
            node_ordinal_of(2, 1)) == (1, 9, 10)
    assert board_next_tier_of({'仙舟': 2, '联盟': 1}) == {'仙舟': 3}
    assert slot_occupies('bench') and slot_occupies('deployed')
    bs = _bs()
    assert bench_free_slots(bs) is None, 'bench 未读 = 诚实缺位(非 0)'
    assert bench_is_full(bs) is None


# ============================================================ §6 终局与结算

def test_write_match_final_idempotent() -> None:
    """终局行(G12 写前查重):首写 True,同段二写 no-op 返 False
    (终局防重)。"""
    bs = _bs()
    assert write_match_final(bs, final_type='loss', plane=1) is True
    assert write_match_final(bs, final_type='loss', plane=1) is False


# (结算覆盖合同锁正本 = test_cw_game_state_consume.py 三件
#  test_settlement_cover_writes_truth_group / _loss_page / _unread_hp。)


# ============================================================ §7 动作模拟

def _mk_state() -> CwSimFrame:
    st = CwSimFrame()
    st.plane, st.round_num, st.gold, st.level = 1, 2, 10, 3
    st.shop = [ShopCard(x=100, faction='仙舟', name='希儿', cost=2, star=1)]
    st.bench = [None] * BENCH_CAPACITY_DEFAULT
    st.deployed = [None] * 10
    return st


def test_simulate_buy_card_moves_shop_to_bench() -> None:
    """simulate 合同:买牌 = 金减费 + 牌入 bench(2★ 合成走 merge 语义另辖);
    卖 bench = 金加退款 + 槽清空;刷新 = 店面换新(金减刷费)。"""
    st = _mk_state()
    st2 = simulate(st, BuyCard(card=st.shop[0]))
    assert st2.gold == 8, '10 - 费2'
    assert any(u is not None and u.char_id == '希儿' for u in st2.bench), \
        '牌入备战席'

    st3 = _mk_state()
    st3.bench[0] = BenchChar(slot=1, char_id='希儿', star=1,
                                   faction='仙舟')
    st4 = simulate(st3, SellBench(bench_idx=0, income=1, expect='希儿'))
    assert st4.bench[0] is None and st4.gold == 13, '退款按注册表 sell_refund(费2,1星)=3,与 income 形参无关'

    st5 = _mk_state()
    st6 = simulate(st5, RefreshShop(cost=2))
    assert st6.gold == 8, '刷新扣费(店内容更换需池上下文,归引擎域合同)'


def test_simulate_level_up_costs_and_levels() -> None:
    """升级模拟:金减级费,等级 +1。"""
    st = _mk_state()
    cost = 4
    st7 = simulate(st, LevelUpShop(cost=cost))
    assert st7.gold == 10 - cost
    assert st7.level == st.level + 1


# ============================================================ §8 会话与执行状态

def test_exec_state_lazy_binding() -> None:
    """执行状态延迟绑定:未绑定时 exec_state_of 产临时态;
    bind 后同 session 恒取同一实例(跨 op 共享执行账)。"""
    sess = StrategySession()
    st = exec_state_of(sess)
    assert st is not None
    bound = bind_exec_state(sess, st)
    assert exec_state_of(sess) is bound


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


# ============================================================ §9 渠道签名封闭集(登记门,自 state_journal 归并)

def test_channel_family_closed_set() -> None:
    """§3.2.1 硬约束 2:family 封闭集 {obs, logic_action, logic_hook},集外 = 红。"""
    for family in ('obs', 'logic_action', 'logic_hook'):
        assert Sig(family=family, actor='cw_observation').family == family
    with pytest.raises(ValueError):
        Sig(family='event', actor='x')
    with pytest.raises(ValueError):
        Sig(family='hook', actor='x')


def test_channel_mode_closed_set_per_family() -> None:
    """§3.2.1:obs 族子模 = read/carried/prior/synthesized;logic 两族恒 compute。"""
    for mode in ('read', 'carried', 'prior', 'synthesized'):
        Sig(family='obs', actor='cw_observation', mode=mode)
    with pytest.raises(ValueError):
        Sig(family='obs', actor='cw_observation', mode='compute')
    for family in ('logic_action', 'logic_hook'):
        Sig(family=family, actor='derive_node_observed', mode='compute')
        with pytest.raises(ValueError):
            Sig(family=family, actor='derive_node_observed', mode='read')


def test_actor_registration_gate() -> None:
    """§3.2.1/§3.2.4 硬约束 2:显式 sig 的 actor 须为登记面在册,集外 = 红。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        register_sig_actors,
    )
    register_sig_actors('TestActorR1')
    bs = _bs()
    with pytest.raises(ValueError):
        bs.observe(bs.gold, 20, sig=Sig(family='obs', actor='NeverRegistered'))
    bs.observe(bs.gold, 20, sig=Sig(family='obs', actor='TestActorR1'))
    assert bs.gold.value == 20
