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

from sr_od.application.currency_war.kernel.cw_board_state import (
    board_state_bridge,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    refresh_ev_budget,
    reserve_cap,
    schedule_upgrade,
)
from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_intention import (
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
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_REG = DEFAULT_REGISTRY
# (危机臂关行为锁注入 _REG_CRISIS_OFF 已随 crisis_release_enabled
# 死旋钮删除——零消费,dd-038 统一迁移批 / commit b94e9cfb,
# 2026-09-04 用户裁定清理。)


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


def _locked_4cost_sess() -> StrategySession:
    """锁定 4 费核意向的 session(ADR-0516 U_L 阈值检验重锚帧):
    4 费峰值级 9,L7→8 概率 0.10→0.22 大移位带(期望刷费省 ≈103 金
    > U_L = 13击×4金 = 52 + 息损)⇒ ② 臂检验过——旧「裸峰值级>当前级」
    直觉帧(2 费小移位带,benefit ≈9.9 < U_L 20)按修正①被正确收紧
    (负向锁 = test_schedule_ul_threshold_negative_small_shift_band),
    锁随新判据重锚(反例锚=希儿 lv7 省 28 < 升 40,ADR-0516)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    from sr_od.application.currency_war.kernel.cw_intention import intention_core

    comp = next(c for c in COMP_LIBRARY
                if (CHARACTERS.get(intention_core(c)) is not None
                    and CHARACTERS[intention_core(c)].cost == 4))
    sess = StrategySession()
    state_of(sess).v3_intention = IntentionState(
        phase='locked', locked_comp=comp.name)
    return sess


def test_schedule_probability_trigger_requires_engine() -> None:
    """触发②[3]+[12]:目标峰值级>当前级 ∧ 息引擎已立;禁升条件=
    息引擎未立不追级(gold<息线,False 即预告态也不发)。"""
    # 锁定 4 费核(大移位带,U_L 检验过;ADR-0516 修正①)+ 息引擎已立
    sess = _locked_4cost_sess()
    st = _state(gold=60, level=7)             # 峰值 9>7 ∧ 60≥50 ∧ U_L 过
    assert schedule_upgrade(st, sess)
    st_low = _state(gold=49, level=7)         # 引擎未立:禁升
    assert not schedule_upgrade(st_low, _locked_4cost_sess())
    st_done = _state(gold=60, level=9)        # 峰值已达:无排程
    assert not schedule_upgrade(st_done, _locked_4cost_sess())


def test_schedule_ul_threshold_negative_small_shift_band() -> None:
    """ADR-0516 修正①负向锁:2 费小移位带帧断言 U_L 阈值检验 False。

    帧形态:锁定 2 费核(峰值级 6>当前级 5,「峰值级>当前级」合取
    成立)、E(D|5)=28.63 / E(D|6)=23.69 ⇒ benefit = 刷价 2×4.95
    ≈ 9.9 < U_L = 5击×4金 = 20(+息损 ≥0)——纯概率账独自不过阈
    ⇒ ``_upgrade_ul_threshold_ok`` 返回 False。检验被删(恒 True)或
    反向(比较项颠倒)本锁发红;正向对照 = 4 费大移位带帧(同文件
    test_schedule_probability_trigger_requires_engine)。
    """
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    from sr_od.application.currency_war.kernel.cw_economy import (
        _upgrade_ul_threshold_ok,
    )
    from sr_od.application.currency_war.kernel.cw_intention import intention_core

    comp = next(c for c in COMP_LIBRARY
                if (CHARACTERS.get(intention_core(c)) is not None
                    and CHARACTERS[intention_core(c)].cost == 2))
    sess = StrategySession()
    state_of(sess).v3_intention = IntentionState(
        phase='locked', locked_comp=comp.name)
    st = _state(gold=60, level=5)      # 2 费 lv5→6:benefit≈9.9 < U_L 20
    assert not _upgrade_ul_threshold_ok(st, sess)
    # 行为面同帧:schedule_upgrade ② 臂同样被收紧(引擎已立 60≥息线、
    # 峰值 6>5,唯 U_L 检验拦下)
    assert not schedule_upgrade(st, sess)


def test_schedule_predictive_even_when_fee_unaffordable() -> None:
    """预告态契约(W623 D1,判前锁):排程不以当帧可负担为前置——
    gold 51(远不够升级费)∧ 峰值未达 → 排程照发、R* 计入升级费;
    「付得起才排」会造 R* 塌缩 → 义务花光 → 更排不上的贫穷循环。"""
    st = _state(gold=51, level=7)
    assert schedule_upgrade(st, _locked_4cost_sess())
    assert reserve_cap(st, _locked_4cost_sess()) > 50


def test_schedule_gold_digger_retires_levelup(monkeypatch) -> None:
    """淘金客姿态:升级通道退役(W621:LevelUp 退役是刷驱姿态主驱动;
    谓词单一址=cw_investments.refresh_invest_active,授权链同址关闭)。"""
    st = _state(gold=100, level=7)
    assert schedule_upgrade(st, _locked_4cost_sess())   # 前置:常态帧排程成立
    monkeypatch.setattr(
        'sr_od.application.currency_war.kernel.cw_investments.STRATEGY_ECONOMY',
        {'淘金客': EconomyEffect(xp_per_refresh=2)})
    st.active_strategies = ['淘金客']
    assert not schedule_upgrade(st, _locked_4cost_sess())


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
    契约优先)。本锁为塌缩带归零语义独家覆盖(原主题文件
    test_cw_w721_overlay_b_budget 已消亡);细则见 ADR-0475。"""
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
    state_of(sess_locked).v3_intention = IntentionState(
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


def test_pair_drought_counters_never_evict() -> None:
    """ADR-0519 重锚:断供驱逐已退役(未证阈值「未证即退役」)——
    断供计数器照常累积(遥测/撤销证据输入),pair_evicted 恒空集、
    pair 方向不因断供被移出候选。另锁锁线门槛 1.0(羁绊满员当量):
    _starve_frame 的 0.5 支持度(各系单件)不足以锁 pair(空窗)。"""
    ist = IntentionState()
    sess = StrategySession()
    state_of(sess).v3_intention = ist
    update_intention(board_state_bridge(_starve_frame()), ist, sess)
    assert ist.p1_pair == (), \
        '支持度 0.5(各系单件)< 门槛 1.0(羁绊满员)→ 空窗不锁(ADR-0519)'
    # 显式 pair 方向在场(模拟已锁帧),断供多轮:计数累积、永不驱逐
    ist2 = IntentionState()
    ist2.p1_pair = ('列车同行', '持续伤害')
    sess2 = StrategySession()
    state_of(sess2).v3_intention = ist2
    for _ in range(6):
        update_intention(board_state_bridge(_starve_frame()), ist2, sess2)
    assert ist2.pair_evicted == set(), '驱逐分支已退役(ADR-0519)'
    assert max(ist2.pair_drought.values(), default=0) >= 1, \
        '断供计数保留(pair 重派生随门槛收紧频繁回 (),计数窗口见注)'


def test_pair_eviction_keeps_target_chain_materialized() -> None:
    """W578 代理门:pair 物化 → pair_target_comp(新 pair)非空
    (target 链不盲;W622 P2 病灶防回归;驱逐退役后同样成立)。"""
    pair = ('仙舟', '持续伤害')
    comp = pair_target_comp(pair)
    assert comp is not None and comp.core_chars
    assert comp.form_tiers    # 档位账随物化(部署/评分消费面不盲)


def test_injection_consistency_single_registry_source() -> None:
    """注入一致性锁(W636 A):prep_brain._budget 装配的 BudgetView 与
    显式注入的接缝值逐字段一致——禁「部分字段落 DEFAULT」的双源混用
    (P6 契约)。cap 归一(ADR-0516 三源归一 + ADR-0598 随批扩展):
    schedule ② 前置息线与预算面守息线分量(reserve_cap floor/
    BudgetView.interest_floor/refresh_ev_budget 溢余面)都随 session
    resolved 链(session.active_strategies 注入面,registry 可达值域
    = 买断制 0/开源节流 9/利息上调 10)移动,registry.interest_cap
    注入不再移动任何息线。锁语义重推(锁存在性纪律,ADR-0598):旧锁
    「注入面 cw4_cap_override=4(registry 不可达值)压过 registry 旋钮」
    随死通道退役重写为「买断制(可达值 0)在排程前置与预算面同帧
    生效,registry 旋钮双臂逐位不动」——判别结构(链动/旋钮不动)
    保形。"""
    import dataclasses
    reg2 = dataclasses.replace(_REG, interest_cap=4)
    st1 = _state(gold=45, level=7, r=5)
    sess = _locked_4cost_sess()
    assert not schedule_upgrade(st1, sess, _REG)
    assert not schedule_upgrade(st1, sess, reg2)   # registry 旋钮不动 resolved 链
    sess_ov = _locked_4cost_sess()
    sess_ov.active_strategies = ['买断制']   # 注册表可达覆写 cap=0 → 息线 0
    assert schedule_upgrade(st1, sess_ov)    # gold 45 ≥ 息线 0 → ② 前置过
    assert refresh_ev_budget(st1, sess, reg2) == refresh_ev_budget(
        st1, sess, _REG)   # registry 旋钮对预算逐位惰性(ADR-0598 归一)
    # 预算面同链:R* 守息线分量随 resolved cap 动(买断制 floor=0+费
    # < 默认 50+费),registry 旋钮不动;gold 96:默认 R*=50+lv7 升级金
    #(52)=102 → 零预算;买断制 R*=0+52=52 → 正预算(lv5 旧帧随 U_L
    # 重锚帧上移,数字按帧现算)
    st2 = _state(gold=96, level=7, r=5)
    assert reserve_cap(st2, sess_ov) < reserve_cap(st2, sess)
    assert refresh_ev_budget(st2, sess, _REG) == 0
    assert refresh_ev_budget(st2, sess_ov) > 0
    # BudgetView 装配单源:传入 reg2 的 BudgetView == 逐字段显式注入值
    from sr_od.application.currency_war.strategies.impl.mandate_v1.assembly import (
        _budget,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.economy_cycle import (
        obligation,
    )
    bv = _budget(st2, sess_ov, reg2)
    assert bv.interest_floor == 0   # resolved 链(买断制)压过 registry 旋钮
    assert bv.reserve_cap == reserve_cap(st2, sess_ov)
    assert bv.obligation == obligation(st2, sess_ov, reg2)
    assert bv.schedule == schedule_upgrade(st2, sess_ov, reg2)
    assert bv.ev_auth == refresh_ev_budget(st2, sess_ov, reg2)
    bv_base = _budget(st2, sess, reg2)
    assert bv_base.interest_floor == 50   # registry cap=4 不再移动预算面息线


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
    exec_state_of(sess).tracked_bench_chars = [live_b]
    exec_state_of(sess).tracked_deployed = [live_d]
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
    state_of(sess).v3_intention = ist
    st = _state(r=5, gold=100,
                shop=[_sc('卡芙卡', 4)], board={})   # 卡芙卡=DOT 系成员
    update_intention(board_state_bridge(st), ist, sess)
    assert ist.pair_drought.get('持续伤害', 0) == 0
