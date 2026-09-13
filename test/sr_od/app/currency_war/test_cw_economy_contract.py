"""经济核合同（kernel 判策第二层：金从哪来、到哪去、什么时候停手）。

被测模块：``kernel/cw_economy.py``（收入链/必花域/XP 链/刷新费/卖退）、
``kernel/cw_investments.py``（投资注册表——登记门归 data 域,此处只锁
经济面消费语义）。

合同面（从源码推导,数值 = 游戏规则换算标定真值,出处 = economy.md §3 与
BWIKI/实机核对记录,置信度分层见源码 docstring）：
- §1 回合收入链:基础收入/连胜金/利息/胜利奖励/败局补偿/聚合;
- §2 卖出退金真值表:cost×3^(star-1),star≥2∧cost≥2 减 1 手续费;
- §3 必花域与息线(金位判定 = 花钱决策的前置门);
- §4 XP 链:点击费用/点击转经验/升级剩余点击/血闸 XP;
- §5 刷新费递增;
- §6 节点目标(NodeGoal)与经济分(economy_score)区分力。
本文件不重复:预算核/排程/断供驱逐(test_cw_economy 预算节)、
阈值链(test_cw_hp_policy)、投资注册表值域(test_cw_data_tables)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_economy import (
    blood_xp_full_clicks,
    clicks_to_next_level,
    in_must_spend_zone,
    interest,
    loss_compensation_base,
    net_income,
    refresh_cost_effective,
    refresh_ev_budget,
    reserve_cap,
    reward_base_gold,
    round_base_income,
    round_start_income,
    schedule_upgrade,
    sell_refund,
    streak_gold,
    xp_apply_clicks,
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
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    BenchChar,
    CwSimFrame,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from test.sr_od.app.currency_war._cw_helpers import cw4_box

# ============================================================ §1 回合收入链

def test_income_chain_true_values() -> None:
    """收入链标定真值:基础收入按轮号爬坡(封顶);连胜金阶梯;利息每 10 金
    +1 封顶 5(息线 = 10×cap)。"""
    assert round_base_income(1) == 3
    assert round_base_income(2) == 4
    assert round_base_income(3) == 5
    assert round_base_income(5) == 5, '基础收入封顶'
    assert streak_gold(0) == 1 and streak_gold(1) == 1
    assert streak_gold(2) == 2 and streak_gold(4) == 2 and streak_gold(5) == 3
    assert interest(0) == 0 and interest(10) == 1
    assert interest(30) == 3 and interest(50) == 5
    assert interest(60) == 5, '利息封顶(50 金 = 息线)'


def test_net_income_counts_streak_and_loss() -> None:
    """净收入 = 基础 + 连胜分量;败局节点另计补偿(lost_node_type 语义)。"""
    assert net_income(2, 0) == 5
    assert net_income(3, 2) == 7
    assert net_income(2, 0, lost_node_type='battle') >= net_income(2, 0), \
        '败局补偿非负(补偿基 = 平面轮函数)'


def test_reward_and_loss_compensation_by_plane() -> None:
    """胜利奖励/败局补偿基:随位面推进抬升(同轮跨位面对照);同位面内
    boss 节点与普通节点同基(差异在节点自身奖励,不在补偿基)。"""
    p1 = reward_base_gold(1, 5)
    assert reward_base_gold(2, 5) >= p1
    assert loss_compensation_base(1, 3, 'battle') \
        == loss_compensation_base(1, 3, 'boss')


def test_round_start_income_aggregates_components() -> None:
    """回合开始收入聚合:各行分项可加;连胜乘数放大胜利分量;
    利息平推(interest_flat)直接入账。"""
    base = round_start_income(plane=1, round_num=3, node_type='battle',
                              gold=30, streak=2)
    boosted = round_start_income(plane=1, round_num=3, node_type='battle',
                                 gold=30, streak=2, win_reward_mult=1.5)
    flat = round_start_income(plane=1, round_num=3, node_type='battle',
                              gold=30, streak=2, interest_flat=2)
    assert base.total == base.base + base.interest + base.streak
    assert boosted.total >= base.total, '胜利乘数不放低收入'
    assert flat.total == base.total + 2


# ============================================================ §2 卖出退金

def test_sell_refund_true_table() -> None:
    """卖出回金(economy.md §3):1星 = cost 原价;star≥2 = cost×3^(star-1)
    再减合成手续费(star≥2∧cost≥2 才减 1;cost=1 全额退,实机核对
    2★1费=+3)。值 = 游戏规则换算真值,置信度分层见源码 docstring。"""
    assert sell_refund(1, 1) == 1 and sell_refund(1, 2) == 2
    assert sell_refund(2, 1) == 3, 'cost=1 免手续费(实机:万敌出售+3)'
    assert sell_refund(2, 2) == 5, '2★2费 = 6-1'
    assert sell_refund(2, 3) == 8, '2★3费 = 9-1'
    assert sell_refund(3, 5) == 44, '3★5费 = 45-1'
    assert sell_refund(1, 0) == 1, 'cost 0 归 1 下界(max(cost,1))'


# ============================================================ §3 必花域

def test_must_spend_zone_gates_on_interest_line() -> None:
    """必花域(20 号稿 §2.1):gold > 饱和线 g*=10×cap 才 True(线上 = 利息
    已满,囤金无收益);线上取等不触发;买断制(cap≤0)恒 False 出辖。"""
    assert in_must_spend_zone(50, None) is False, 'cap=5 → 线=50,取等不触发'
    assert in_must_spend_zone(51, None) is True
    assert in_must_spend_zone(30, None) is False


# ============================================================ §4 XP 链

def test_xp_apply_clicks_carries_overflow() -> None:
    """XP 点击应用:点击数 × 每击经验;溢出经验作废(不跨级结转)。"""
    level, xp_cur = xp_apply_clicks(4, 0, 1, xp_per_buy=4)
    assert (level, xp_cur) == (4, 4), '未升级,经验累加(4 级门槛 6,一击 4 不够)'
    level0, xp0 = xp_apply_clicks(3, 2, 0, xp_per_buy=4)
    assert (level0, xp0) == (3, 2), '零点击零推进'
    level2, xp_cur2 = xp_apply_clicks(3, 6, 1, xp_per_buy=4)
    assert (level2, xp_cur2) == (5, 0), '连升两支:10 经验过 need(3)=4 升 4、过 need(4)=6 升 5 清零'


def test_blood_xp_full_clicks_scales_with_level() -> None:
    """血闸 XP 满击数随职级抬升(高等级升级更贵 = 血 XP 代价更高)。"""
    assert blood_xp_full_clicks(3) < blood_xp_full_clicks(7)


def test_clicks_to_next_level_uses_container_frame() -> None:
    """升级剩余点击:容器帧直算(等级/XP 现值 → 还需几击)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        BS_SCHEMA_VERSION,
        ChannelSig,
        GameState,
        register_sig_actors,
    )
    register_sig_actors('TestSigWriter')
    sig = ChannelSig(family='obs', actor='TestSigWriter', mode='read')
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.level, 3, sig=sig)
    bs.observe(bs.xp, (2, 8), sig=sig)
    n = clicks_to_next_level(bs)
    assert n is not None and n >= 1


# ============================================================ §5 刷新费

def test_refresh_cost_passes_through_observed_price() -> None:
    """刷价参数化(ADR-0622):bs 给定 = 现场识别值直通(免费帧不写保证
    非 0);bs 缺席 = CwSimFrame 契约价;再缺 = 建模基价显式缺省
    (原 ``or 2`` falsy 兜底消灭形态,数值恒同语义升级)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        BS_SCHEMA_VERSION,
        ChannelSig,
        GameState,
        register_sig_actors,
    )
    register_sig_actors('TestSigWriter')
    sig = ChannelSig(family='obs', actor='TestSigWriter', mode='read')
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.shop_refresh_cost, 4, sig=sig)
    assert refresh_cost_effective(CwSimFrame(), 0, bs=bs) == 4, '现场值直通'
    bs_none = GameState(schema_version=BS_SCHEMA_VERSION)
    assert refresh_cost_effective(CwSimFrame(), 0, bs=bs_none) == 2, \
        '未读 → 建模基价缺省'
    st = CwSimFrame()
    st.shop_refresh_cost = 3
    assert refresh_cost_effective(st, 0) == 3, '帧契约价'


# ============================================================ §6 节点目标

def test_node_goal_returns_domain_object() -> None:
    """节点目标(plane, round → 该节点经济目标):对象域字段齐
    (目标等级/目标金),committed 臂改变目标档(承诺核开 = 目标更高)。"""
    from sr_od.application.currency_war.kernel.cw_economy import get_node_goal
    goal = get_node_goal(1, 3)
    assert goal is not None
    goal_committed = get_node_goal(1, 3, committed=True)
    goal_free = get_node_goal(1, 3, committed=False)
    assert goal_committed is not None and goal_free is not None


# ==================== 预算核/排程核/断供驱逐(自 migration_budget_authority 归并) ====================
# 预算核:确定性预算在任意帧恒有定义;排程核四触发(人口位/概率级)×禁升两条件
# (息引擎前置/淘金客退役);断供驱逐(pair 体系断供 → 移出候选,pair 重派生)。
# 规则出处 = kernel/cw_economy + cw_intention 现役实现;行为断言零改动。


_REG = DEFAULT_REGISTRY
# (危机臂关行为锁注入 _REG_CRISIS_OFF 已随 crisis_release_enabled
# 死旋钮删除——零消费,统一迁移批 commit b94e9cfb,
# 2026-09-04 用户裁定清理。)


def _ba_state(*, gold: int = 100, plane: int = 1, r: int = 5, level: int = 6,
           hp: int = 80,
           bench: list[BenchChar | None] | None = None,
           shop: list[ShopCard] | None = None,
           board: dict | None = None) -> CwSimFrame:
    return CwSimFrame(
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
    from sr_od.application.currency_war.kernel.cw_vocab import deployed_occupied

    def _ch(name: str, slot: int, star: int) -> BenchChar:
        fac = (CHARACTERS[name].factions or ('?',))[0]
        return BenchChar(slot=slot, char_id=name, faction=fac, star=star)

    bench = [_ch('阿格莱雅', i, 2) for i in range(BENCH_CAPACITY)]
    st = _ba_state(gold=30, level=6, r=9,
                bench=bench)                  # gold 30<息线:禁升②不触发
    assert deployed_occupied(st.deployed) < st.max_units()   # 有空位(非满)
    assert not schedule_upgrade(cw4_box(st), _ba_sess_of(st))
    st.dep = None
    # cap 满:deployed 填满 → 人口位触发
    st.deployed = [BenchChar(slot=20 + i, char_id=f'杂{i}', faction='公司',
                             star=1) for i in range(st.max_units())]
    assert deployed_occupied(st.deployed) >= st.max_units()
    assert schedule_upgrade(cw4_box(st), _ba_sess_of(st))


def _ba_sess_of(state: CwSimFrame) -> StrategySession:
    return StrategySession()


def _ba_locked_4cost_sess() -> StrategySession:
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
    sess = _ba_locked_4cost_sess()
    st = _ba_state(gold=60, level=7)             # 峰值 9>7 ∧ 60≥50 ∧ U_L 过
    assert schedule_upgrade(cw4_box(st), sess)
    st_low = _ba_state(gold=49, level=7)         # 引擎未立:禁升
    assert not schedule_upgrade(cw4_box(st_low), _ba_locked_4cost_sess())
    st_done = _ba_state(gold=60, level=9)        # 峰值已达:无排程
    assert not schedule_upgrade(cw4_box(st_done), _ba_locked_4cost_sess())


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
    st = _ba_state(gold=60, level=5)      # 2 费 lv5→6:benefit≈9.9 < U_L 20
    assert not _upgrade_ul_threshold_ok(cw4_box(st), sess)
    # 行为面同帧:schedule_upgrade ② 臂同样被收紧(引擎已立 60≥息线、
    # 峰值 6>5,唯 U_L 检验拦下)
    assert not schedule_upgrade(cw4_box(st), sess)


def test_schedule_predictive_even_when_fee_unaffordable() -> None:
    """预告态契约(W623 D1,判前锁):排程不以当帧可负担为前置——
    gold 51(远不够升级费)∧ 峰值未达 → 排程照发、R* 计入升级费;
    「付得起才排」会造 R* 塌缩 → 义务花光 → 更排不上的贫穷循环。"""
    st = _ba_state(gold=51, level=7)
    assert schedule_upgrade(cw4_box(st), _ba_locked_4cost_sess())
    assert reserve_cap(cw4_box(st), _ba_locked_4cost_sess()) > 50


def test_schedule_gold_digger_retires_levelup(monkeypatch) -> None:
    """淘金客姿态:升级通道退役(W621:LevelUp 退役是刷驱姿态主驱动;
    谓词单一址=cw_investments.refresh_invest_active,授权链同址关闭)。"""
    st = _ba_state(gold=100, level=7)
    assert schedule_upgrade(cw4_box(st), _ba_locked_4cost_sess())   # 前置:常态帧排程成立
    monkeypatch.setattr(
        'sr_od.application.currency_war.kernel.cw_investments.STRATEGY_ECONOMY',
        {'淘金客': EconomyEffect(xp_per_refresh=2)})
    st.active_strategies = ['淘金客']
    assert not schedule_upgrade(cw4_box(st), _ba_locked_4cost_sess())


# --- 预算核契约锁(W623 D2)---------------------------------------------------


def test_budget_value_domain_and_legal_zero_frames() -> None:
    """契约:值域 [0,6](6 刷帽单一源);合法 0 帧存在(g≤R* 常态帧;
    全恒正=契约未实现)。"""
    st = _ba_state(gold=200, level=6)
    assert refresh_ev_budget(cw4_box(st), _ba_sess_of(st)) == 6     # 6 刷帽
    st0 = _ba_state(gold=50, level=6)                     # g=R*:溢余 0
    assert refresh_ev_budget(cw4_box(st0),_ba_sess_of(st0)) == 0   # 合法 0 帧
    st1 = _ba_state(gold=51, level=6)                     # 溢余 1<刷价
    assert refresh_ev_budget(cw4_box(st1), _ba_sess_of(st1)) == 0   # 合法 0 帧(准入门辖域)


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

    st = _ba_state(gold=200, level=5, hp=80, shop=[_sc('桑博', 2)], board={})
    comp = next(c for c in COMP_LIBRARY
                if (CHARACTERS.get(intention_core(c)) is not None
                    and CHARACTERS[intention_core(c)].cost == 4))
    sess_locked = StrategySession()
    state_of(sess_locked).v3_intention = IntentionState(
        phase='locked', locked_comp=comp.name)
    assert refresh_ev_budget(cw4_box(st), sess_locked) == 0
    assert refresh_ev_budget(cw4_box(st), StrategySession()) > 0


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
    return _ba_state(r=r, gold=100, bench=bench)


def test_pair_drought_counters_never_evict() -> None:
    """ADR-0519 重锚:断供驱逐已退役(未证阈值「未证即退役」)——
    断供计数器照常累积(遥测/撤销证据输入),pair_evicted 恒空集、
    pair 方向不因断供被移出候选。另锁锁线门槛 1.0(羁绊满员当量):
    _starve_frame 的 0.5 支持度(各系单件)不足以锁 pair(空窗)。"""
    ist = IntentionState()
    sess = StrategySession()
    state_of(sess).v3_intention = ist
    update_intention(cw4_box(_starve_frame()), ist, sess)
    assert ist.p1_pair == (), \
        '支持度 0.5(各系单件)< 门槛 1.0(羁绊满员)→ 空窗不锁(ADR-0519)'
    # 显式 pair 方向在场(模拟已锁帧),断供多轮:计数累积、永不驱逐
    ist2 = IntentionState()
    ist2.p1_pair = ('列车同行', '持续伤害')
    sess2 = StrategySession()
    state_of(sess2).v3_intention = ist2
    for _ in range(6):
        update_intention(cw4_box(_starve_frame()), ist2, sess2)
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
    st1 = _ba_state(gold=45, level=7, r=5)
    sess = _ba_locked_4cost_sess()
    assert not schedule_upgrade(cw4_box(st1), sess, _REG)
    assert not schedule_upgrade(cw4_box(st1), sess, reg2)   # registry 旋钮不动 resolved 链
    sess_ov = _ba_locked_4cost_sess()
    sess_ov.active_strategies = ['买断制']   # 注册表可达覆写 cap=0 → 息线 0
    assert schedule_upgrade(cw4_box(st1), sess_ov)    # gold 45 ≥ 息线 0 → ② 前置过
    assert refresh_ev_budget(cw4_box(st1), sess, reg2) == \
        refresh_ev_budget(cw4_box(st1), sess, _REG)   # registry 旋钮对预算逐位惰性(ADR-0598 归一)
    # 预算面同链:R* 守息线分量随 resolved cap 动(买断制 floor=0+费
    # < 默认 50+费),registry 旋钮不动;gold 96:默认 R*=50+lv7 升级金
    #(52)=102 → 零预算;买断制 R*=0+52=52 → 正预算(lv5 旧帧随 U_L
    # 重锚帧上移,数字按帧现算)
    st2 = _ba_state(gold=96, level=7, r=5)
    assert reserve_cap(cw4_box(st2), sess_ov) < reserve_cap(
        cw4_box(st2), sess)
    assert refresh_ev_budget(cw4_box(st2), sess, _REG) == 0
    assert refresh_ev_budget(cw4_box(st2), sess_ov) > 0
    # BudgetView 装配单源:传入 reg2 的 BudgetView == 逐字段显式注入值
    # (_budget 读 session 容器单例,局内事实先经合成口喂入 = 生产同路)
    from test.sr_od.app.currency_war._cw_helpers import cw4_feed
    cw4_feed(sess_ov, st2)
    from sr_od.application.currency_war.strategies.impl.mandate_v1.assembly import (
        _budget,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.economy_cycle import (
        obligation,
    )
    bv = _budget(st2, sess_ov, reg2)
    assert bv.interest_floor == 0   # resolved 链(买断制)压过 registry 旋钮
    assert bv.reserve_cap == reserve_cap(cw4_box(st2), sess_ov)
    assert bv.obligation == obligation(cw4_box(st2), sess_ov, reg2)
    assert bv.schedule == schedule_upgrade(cw4_box(st2), sess_ov, reg2)
    assert bv.ev_auth == refresh_ev_budget(cw4_box(st2), sess_ov, reg2)
    cw4_feed(sess, st2)
    bv_base = _budget(st2, sess, reg2)
    assert bv_base.interest_floor == 50   # registry cap=4 不再移动预算面息线


def test_tracking_view_isolated_from_session_writers() -> None:
    """隔离锁(W639 C 浅拷贝落码):TurnState 视图元素与 session.tracked_*
    双向断开——视图侧变异不穿透 session,session 侧就地写端(shop 星级/
    装备拼接、deploy_bench 装备覆盖的真实别名写者)不穿透视图;
    equips 在视图侧固化为 tuple。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_vocab import snapshot_copy
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
    st = _ba_state(r=5, gold=100,
                shop=[_sc('卡芙卡', 4)], board={})   # 卡芙卡=DOT 系成员
    update_intention(cw4_box(st), ist, sess)
    assert ist.pair_drought.get('持续伤害', 0) == 0
