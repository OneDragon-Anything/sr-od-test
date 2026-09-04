"""W633 迁移批 3(预算收权)行为锁。

任务书=`.debug/temp/currency_war/w633_migration_b3/STATUS.md`;判前依据=
W623 预验尸(D0-D4)+ W630 A/B 协议 + W615 R1-R4 规则集。锁契约:

- D0 供给权交接(局23 型帧哨兵):确定性预算核在任意帧恒有定义
  (无 None 形状);溢余帧义务链活性 release≠0;无供给帧禁保守坍缩;
- 排程核规则锁(W615 §1.3/§2-R4):四触发(人口位/概率级)×禁升
  两条件(息引擎前置/淘金客退役)×预告态(不以当帧可负担为前置,
  W623 D1 防 R* 塌缩贫穷循环);
- 预算核契约锁(W623 D2):值域 [0,6]、合法 0 帧存在、血预算停手帧
  不被预算合并穿透;
- R3 断供驱逐(蓝图 §4.3-R3 推广):pair 体系断供 ≥5 轮 → 移出候选、
  pair 重派生;W578 代理门:驱逐后 pair_target_comp 物化非空。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.kernel.cw_economy import (
    refresh_ev_budget,
    reserve_cap,
    schedule_upgrade,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    PAIR_DROUGHT_EVICT_ROUNDS,
    IntentionState,
    pair_target_comp,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_investments import EconomyEffect
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import StrategySession

_REG = DEFAULT_REGISTRY
# 关行为锁显式注入(危机臂开臂后默认 registry=True,ADR-0503;让位语义
# 锁改注入 False 仍测,不删)。
_REG_CRISIS_OFF = dataclasses.replace(_REG, crisis_release_enabled=False)


def _state(*, gold: int = 100, plane: int = 1, r: int = 5, level: int = 6,
           hp: int = 80,
           bench: list[BenchChar | None] | None = None,
           shop: list[ShopCard] | None = None,
           board: dict | None = None) -> GameState:
    return GameState(
        plane=plane, round_num=r, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2,
        deployed=[], bench=bench if bench is not None else [None] * BENCH_CAPACITY,
        shop=shop if shop is not None else [], node_type='battle',
        board=board or {})


def _sc(name: str, cost: int = 2) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


# (D0 局23 帧哨兵/供给边界两测已随 DP 姿态核/泄息指令死链删除——
#  统一迁移批 ② MAP B 类;build_round_posture/evaluate_release 随 v2 消亡。)


# --- 排程核规则锁(W615 R4)---------------------------------------------------


def test_schedule_pop_slot_trigger() -> None:
    """触发①[33] 人口位:cap 满 ∧ bench 有成型件(2★)→ 排程
    (最高义务;不受息引擎前置辖——当轮兑现战力)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_state import deployed_occupied

    def _ch(name: str, slot: int, star: int) -> BenchChar:
        fac = (CHARACTERS[name].factions or ('?',))[0]
        return BenchChar(slot=slot, char_id=name, faction=fac, star=star)

    bench = [_ch('阿格莱雅', i, 2) for i in range(BENCH_CAPACITY)]
    st = _state(gold=30, level=6, r=9,
                bench=bench)                  # gold 30<息线:禁升②不触发
    assert deployed_occupied(st.deployed) < st.max_units()   # 有空位(非满)
    assert not schedule_upgrade(st, sess_of(st))
    st.dep = None
    # cap 满:deployed 填满 → 人口位触发
    st.deployed = [BenchChar(slot=20 + i, char_id=f'杂{i}', faction='公司',
                             star=1) for i in range(st.max_units())]
    assert deployed_occupied(st.deployed) >= st.max_units()
    assert schedule_upgrade(st, sess_of(st))


def sess_of(state: GameState) -> StrategySession:
    return StrategySession()


def test_schedule_probability_trigger_requires_engine() -> None:
    """触发②[3]+[12]:目标峰值级>当前级 ∧ 息引擎已立;禁升条件=
    息引擎未立不追级(gold<息线,False 即预告态也不发)。"""
    st = _state(gold=60, level=5)             # 绯英 2费峰值 6>5 ∧ 60≥50
    assert schedule_upgrade(st, sess_of(st))
    st_low = _state(gold=49, level=5)         # 引擎未立:禁升
    assert not schedule_upgrade(st_low, sess_of(st_low))
    st_done = _state(gold=60, level=6)        # 峰值已达:无排程
    assert not schedule_upgrade(st_done, sess_of(st_done))


def test_schedule_predictive_even_when_fee_unaffordable() -> None:
    """预告态契约(W623 D1,判前锁):排程不以当帧可负担为前置——
    gold 51(远不够升级费)∧ 峰值未达 → 排程照发、R* 计入升级费;
    「付得起才排」会造 R* 塌缩 → 义务花光 → 更排不上的贫穷循环。"""
    st = _state(gold=51, level=5)
    assert schedule_upgrade(st, sess_of(st))
    assert reserve_cap(st, sess_of(st), _REG) > 50


def test_schedule_gold_digger_retires_levelup(monkeypatch) -> None:
    """淘金客姿态:升级通道退役(W621:LevelUp 退役是刷驱姿态主驱动;
    谓词单一址=cw_investments.refresh_invest_active,授权链同址关闭)。"""
    st = _state(gold=100, level=5)
    assert schedule_upgrade(st, sess_of(st))   # 前置:常态帧排程成立
    monkeypatch.setattr(
        'sr_od.application.currency_war.kernel.cw_investments.STRATEGY_ECONOMY',
        {'淘金客': EconomyEffect(xp_per_refresh=2)})
    st.active_strategies = ['淘金客']
    assert not schedule_upgrade(st, sess_of(st))


# --- 预算核契约锁(W623 D2)---------------------------------------------------


def test_budget_value_domain_and_legal_zero_frames() -> None:
    """契约:值域 [0,6](6 刷帽单一源);合法 0 帧存在(g≤R* 常态帧;
    全恒正=契约未实现)。"""
    st = _state(gold=200, level=6)
    assert refresh_ev_budget(st, sess_of(st)) == 6     # 6 刷帽
    st0 = _state(gold=50, level=6)                     # g=R*:溢余 0
    assert refresh_ev_budget(st0, sess_of(st0)) == 0   # 合法 0 帧
    st1 = _state(gold=51, level=6)                     # 溢余 1<刷价
    assert refresh_ev_budget(st1, sess_of(st1)) == 0   # 合法 0 帧(准入门辖域)


# (test_blood_budget_stop_not_inflated_by_budget_merge 已随 DP 姿态/泄息
#  指令死链删除——统一迁移批 ② MAP B 类。)


def test_w721_collapse_band_zero_and_fallback_exempt() -> None:
    """0 帧契约第三类(塌缩带归零)扩类用例(ADR-0475;补在穿透锁组:
    归零帧再多一类,max 合并结构不变):①锁定 4 费核 ∧ lv5(比值 0.05
    < ω=0.1)→ 预算 0(合法 0 帧第三类,穿透锁口径=合法 0 不是虚标);
    ②同一形态的未锁定帧(兜底链)不归零——空帧豁免(D1「空帧不缩供给」
    契约优先)。公式与单一址细则=test_cw_w721_overlay_b_budget。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
        intention_core,
    )

    st = _state(gold=200, level=5, hp=80, shop=[_sc('桑博', 2)], board={})
    comp = next(c for c in COMP_LIBRARY
                if (CHARACTERS.get(intention_core(c)) is not None
                    and CHARACTERS[intention_core(c)].cost == 4))
    sess_locked = StrategySession()
    sess_locked.v3_intention = IntentionState(
        phase='locked', locked_comp=comp.name)
    assert refresh_ev_budget(st, sess_locked) == 0
    assert refresh_ev_budget(st, StrategySession()) > 0


# --- R3 · pair 断供驱逐(蓝图 §4.3-R3 推广)------------------------------------


def _starve_frame(r: int = 5):
    """配方锁帧工厂:bench 有 DOT/列车成员(支持度保 pair 重派生不脱窗),
    店空(两体系新件渠道全断——「补不进的新件」量供给渠道,到手资产
    不救供给)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS

    def _ch(name: str, slot: int) -> BenchChar:
        fac = (CHARACTERS[name].factions or ('?',))[0]
        return BenchChar(slot=slot, char_id=name, faction=fac, star=1)
    bench = [_ch('卡芙卡', 0), _ch('姬子', 1)] \
        + [None] * (BENCH_CAPACITY - 2)
    return _state(r=r, gold=100, bench=bench)


def test_pair_drought_eviction_threshold_and_rederivation() -> None:
    """断供 ≥5 轮 → 体系移出候选、pair 重派生排除;<5 轮不驱逐。
    阈值=PAIR_DROUGHT_EVICT_ROUNDS(保守 5,DROUGHT_BAIL 同族先验;
    探针批标定挂账=说服包 R3 断供探针)。"""
    ist = IntentionState()
    sess = StrategySession()
    sess.v3_intention = ist
    # 首轮:支持度(bench 卡芙卡+姬子)派生 pair;店空开始断供计数
    update_intention(_starve_frame(), ist, sess)
    assert ist.p1_pair == ('列车同行', '持续伤害'), ist.p1_pair
    for _ in range(PAIR_DROUGHT_EVICT_ROUNDS - 1):
        update_intention(_starve_frame(), ist, sess)
    assert ist.pair_evicted == set(), ist.pair_evicted
    # 第 5 轮:两体系均断供达阈 → 同时驱逐,pair 重派生排除
    update_intention(_starve_frame(), ist, sess)
    assert {'列车同行', '持续伤害'} <= ist.pair_evicted
    assert not (set(ist.p1_pair) & {'列车同行', '持续伤害'})


def test_pair_eviction_keeps_target_chain_materialized() -> None:
    """W578 代理门:驱逐后 pair 重派生 → pair_target_comp(新 pair)
    物化非空(target 链不因驱逐全盲;W622 P2 病灶防回归)。"""
    pair = ('仙舟', '持续伤害')
    comp = pair_target_comp(pair)
    assert comp is not None and comp.core_chars
    assert comp.form_tiers    # 档位账随物化(部署/评分消费面不盲)


def test_injection_consistency_single_registry_source() -> None:
    """注入一致性锁(W636 A):三接缝(schedule/refresh_ev_budget/
    reserve_cap)显式注入同一非默认 registry 时行为同变,prep_brain.
    _budget 装配的 BudgetView 与显式注入的接缝值逐字段一致——禁
    「部分字段落 DEFAULT」的双源混用(P6 契约)。interest_cap 4→息线 40。"""
    import dataclasses
    reg2 = dataclasses.replace(_REG, interest_cap=4)
    # 息线随注入移动:gold 45 → 默认(50)不排程/零预算;注入(40)排程
    st1 = _state(gold=45, level=5, r=5)
    sess = StrategySession()
    assert not schedule_upgrade(st1, sess, _REG)
    assert schedule_upgrade(st1, sess, reg2)
    assert refresh_ev_budget(st1, sess, reg2) > refresh_ev_budget(
        st1, sess, _REG)   # 息线下移 → 排程开+溢余面变化,预算随之
    # gold 62:默认 R*=50+lc5=66 → 零预算;注入 R*=40+lc5=56 → 正预算
    st2 = _state(gold=62, level=5, r=5)
    assert reserve_cap(st2, sess, reg2) < reserve_cap(st2, sess, _REG)
    assert refresh_ev_budget(st2, sess, _REG) == 0
    assert refresh_ev_budget(st2, sess, reg2) > 0
    # BudgetView 装配单源:传入 reg2 的 BudgetView == 逐字段显式注入值
    from sr_od.application.currency_war.strategies.impl.mandate_v1.assembly import (
        _budget,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.economy_cycle import (
        obligation,
    )
    bv = _budget(st2, sess, reg2)
    assert bv.interest_floor == 40
    assert bv.reserve_cap == reserve_cap(st2, sess, reg2)
    assert bv.obligation == obligation(st2, sess, reg2)
    assert bv.schedule == schedule_upgrade(st2, sess, reg2)
    assert bv.ev_auth == refresh_ev_budget(st2, sess, reg2)


def test_tracking_view_isolated_from_session_writers() -> None:
    """隔离锁(W639 C 浅拷贝落码):TurnState 视图元素与 session.tracked_*
    双向断开——视图侧变异不穿透 session,session 侧就地写端(shop 星级/
    装备拼接、deploy_bench 装备覆盖的真实别名写者)不穿透视图;
    equips 在视图侧固化为 tuple。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_state import snapshot_copy
    from sr_od.application.currency_war.strategies.impl.mandate_v1.assembly import (
        _tracking_view,
    )

    def _ch(name: str, slot: int) -> BenchChar:
        fac = (CHARACTERS[name].factions or ('?',))[0]
        return BenchChar(slot=slot, char_id=name, faction=fac, star=1,
                         equips=['0'])

    sess = StrategySession()
    live_b = _ch('卡芙卡', 0)
    live_d = _ch('姬子', 0)
    sess.tracked_bench_chars = [live_b]
    sess.tracked_deployed = [live_d]
    # 直调 _tracking_view(snapshot 传空 fresh-read 兜底面)
    from sr_od.application.currency_war.strategies.impl.mandate_v1.contracts import (
        Snapshot,
    )
    snap = Snapshot(plane=1, round_num=5)
    bench, deployed = _tracking_view(sess, snap)
    assert bench and deployed
    # 视图侧变异 → session tracked 不受影响
    bench[0].star = 99
    bench[0].equips = ('x',)
    deployed[0].equips = ('y',)
    assert live_b.star == 1 and live_b.equips == ['0']
    assert live_d.equips == ['0']
    # session 侧就地写(真实别名写者形态:shop 星级/装备拼接、deploy 覆盖)
    live_b.star = 3
    live_b.equips = live_b.equips + ['1']
    live_d.equips = ['2']
    assert bench[0].star == 99 and tuple(bench[0].equips) == ('x',)
    assert tuple(deployed[0].equips) == ('y',)
    # snapshot_copy 自身:equips 固化 tuple
    cp = snapshot_copy(live_b)
    assert isinstance(cp.equips, tuple) and tuple(cp.equips) == ('0', '1')
    assert cp is not live_b
    # tracking 空 → fresh read 补缺(并自 test_cw_w620_tracking_view:
    # 优先读+快照拷贝语义由本锁前半辖,兜底半句随迁至此)
    sess_fresh = StrategySession()
    bench_fresh, deployed_fresh = _tracking_view(sess_fresh, snap)
    assert bench_fresh == tuple(snap.bench)
    assert deployed_fresh == tuple(snap.deployed)


def test_pair_drought_resets_when_member_visible() -> None:
    """成员再现(在店/到手)→ 断供计数清零(计数语义同 LineTrack
    frozen_rounds:窗口重开即清零)。"""
    ist = IntentionState()
    ist.p1_pair = ('持续伤害', '仙舟')
    sess = StrategySession()
    sess.v3_intention = ist
    st = _state(r=5, gold=100,
                shop=[_sc('卡芙卡', 4)], board={})   # 卡芙卡=DOT 系成员
    update_intention(st, ist, sess)
    assert ist.pair_drought.get('持续伤害', 0) == 0
