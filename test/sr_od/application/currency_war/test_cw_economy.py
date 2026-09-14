"""CW 经济域测试(#4):金守恒(单代表)/ budget 拒付(fail-closed 单代表)/
interest+streak 表锚 / ev_arm 值域(aggregate_economy 分型登记)。

覆盖面(金钱类按 2026-09-09 编排者裁决收缩:实机结算对账 + sim 段检双层
已覆盖逐面金钱锁,单位层只留 commit→sim 空窗价值):
- 金守恒(净守恒单代表):1★ 牌买卖回合 simulate 金总量守恒(净 0 对任意
  费用成立,注册表改费不红)——红 = 支出面与退金面静默分叉;
- budget 拒付(1 代表,归 fail-closed):hp 不可信帧 blood_xp_gate 拒;
- interest+streak 表锚:R2 息线 g*=10×cap 参数化表锚 + economy_score
  利息单调 + streak 只计连胜方向(ADR-0128 无连败补偿);
- ev_arm 值域:aggregate_economy 分型登记表逐字段算子期望(值域表)
  + 区分力非零证明锚(篡改登记必分歧,非恒绿护栏);
- 过继锁:投资注册表 335/83 计数(原 test_cw_investment 唯一承载,
  终局归编 #15 data_registry,重建期暂挂本文件防断链)。
退役面:投资收入入账本/息线 floor 行为两行/血闸阈值逐点(预算闸族逐面锁
按裁决不搬,git 可复活)。

来源:economy_typing(mv 主干)/ investment / r2_interest_floor /
blood_xp_gate 核 / decisions 之 economy 真值两行(2026-09-09 套件重建批
A,#4;金钱类收缩随编排者裁决)。其余历史锁已退役(git 可复活)。
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS

if TYPE_CHECKING:
    from sr_od.application.currency_war.kernel.cw_game_state import (
        GameState,
    )

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bsb,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_comp as _comp,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_decide as _decide,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_members as _members,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session as _session,
)

from sr_od.application.currency_war.data.cw_shop_odds import (
    DISTINCT_CARDS_PER_COST,
    POOL_COPIES_PER_CARD,
    expected_refreshes,
    expected_refreshes_for_card,
    refresh_prob,
)
from sr_od.application.currency_war.kernel import cw_investments as inv
from sr_od.application.currency_war.kernel.cw_economy import (
    blood_xp_gate,
    blood_xp_gate_for,
    economy_score,
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
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_ENVS,
    INVESTMENT_STRATEGIES,
    EconomyEffect,
    aggregate_economy,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    CwSimFrame,
    RefreshShop,
    SellBench,
    ShopCard,
    simulate,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# ==================== ev_arm 值域:aggregate_economy 分型登记 ====================
# 分型表(测试位常量表)= 聚合语义机器可读单一源(§E6 裁决:代码即载体,
# 禁文档表与测试硬编码双源)。
# 算子词表(非封闭;实现出现词表外形态=登记缺口):
#   sum/max/guarded_min/or/prob/filter_max(语义见 _fold)。
AGG_FIELDS: dict[str, dict] = {
    'instant_gold': {'op': 'sum'},
    'gold_per_node': {'op': 'sum'},
    'free_refresh_per_node': {'op': 'sum'},
    'free_refresh_burst': {'op': 'sum'},
    'refresh_surprise_every': {'op': 'guarded_min'},
    'gold_per_three_5cost': {'op': 'sum'},
    'interest_cap_override': {'op': 'filter_max', 'keep': lambda v: v is not None},
    'xp_per_refresh': {'op': 'sum'},
    'xp_per_node': {'op': 'sum'},
    'xp_buy_cost_discount': {'op': 'sum'},
    'win_reward_mult': {'op': 'filter_max', 'keep': lambda v: v != 1.0},
    'gold_per_boss_node': {'op': 'sum'},
    'gold_next_nodes_amount': {'op': 'sum'},
    'gold_next_nodes_count': {'op': 'max'},
    'gold_per_level_up': {'op': 'sum'},
    'gold_per_20hp_lost': {'op': 'sum'},
    'xp_buy_hp_cost': {'op': 'or'},
    'refresh_shop_rewrite_every_3cost': {'op': 'guarded_min'},
    'refresh_free_chance': {'op': 'prob'},
    # —— 五族枚举补全(R83-1/R85-3;数值求和 + 触发位守卫 min 并宽)——
    'interest_flat_per_node': {'op': 'sum'},
    'gold_at_node': {'op': 'sum'},
    'gold_at_node_offset': {'op': 'guarded_min'},
    'gold_at_level': {'op': 'sum'},
    'gold_at_level_target': {'op': 'guarded_min'},
    'xp_click_discount_from_level': {'op': 'sum'},
    'xp_click_discount_from_level_at': {'op': 'guarded_min'},
}


def _fold(op: str, a, b):
    """分型表算子的二元规约(求值器唯一执行体——单一源=表,非第二份实现)。"""
    if op == 'sum':
        return a + b
    if op == 'max':
        return max(a, b)
    if op == 'guarded_min':
        # 哨兵 0:非零成员取 min;任一侧为零(缺席)取另一侧
        return min(a, b) if (a and b) else (a or b)
    if op == 'or':
        return a or b
    if op == 'prob':
        return 1.0 - (1.0 - a) * (1.0 - b)
    if op == 'filter_max':
        raise ValueError('filter_max 走过滤后置通道,不经二元 fold')
    raise ValueError(f'分型表词表外算子: {op}(登记缺口,须补齐算子规约)')


def _reference_aggregate(effects: list[EconomyEffect],
                         table: dict[str, dict] | None = None) -> dict:
    """测试位参考求值器:按分型表机械驱动,产出 field->聚合值 dict。

    单一源=分型表(算子+哨兵+初值);本函数不含任何字段名分支。
    """
    table = AGG_FIELDS if table is None else table
    out: dict[str, object] = {}
    for fname, spec in table.items():
        if spec['op'] == 'filter_max':
            # 过滤谓词 + 后置取宽:过滤入集、循环外 max(不经二元 fold)
            kept = [getattr(e, fname) for e in effects
                    if spec['keep'](getattr(e, fname))]
            out[fname] = max(kept) if kept else getattr(EconomyEffect(), fname)
            continue
        acc = getattr(EconomyEffect(), fname)   # 初值=字段默认(恒等元)
        for e in effects:
            acc = _fold(spec['op'], acc, getattr(e, fname))
        out[fname] = acc
    return out


def _mk(name: str, **kw) -> tuple[str, inv.InvestmentStrategy]:
    """构造注册表外测试条目(经 normalize+查表路径入册——与生产同缝)。"""
    return name, inv.InvestmentStrategy(
        name=name, rarity='金', effect='测试构造',
        economy=EconomyEffect(**kw) if kw else None)


@pytest.fixture()
def patched_registry(monkeypatch):
    """测试缝:整表替换 INVESTMENT_STRATEGES(测试纪律第 1 条:整条副作用链桩化)。"""
    def _install(entries: list[tuple[str, inv.InvestmentStrategy]],
                 extra_unknown: str | None = None):
        names = [n for n, _ in entries]
        monkeypatch.setattr(inv, 'INVESTMENT_STRATEGIES', dict(entries))
        return names + ([extra_unknown] if extra_unknown else [])
    return _install


# 区分力 fixture(§E6 义务:每聚合型字段 ≥1 个能区分登记算子与同型
# 备选算子的构造;即各字段聚合值的「值域表」锚)。
def test_half3_distinguish_fixtures(patched_registry) -> None:
    cases = [
        # (字段, 两成员值, 登记算子期望, 被区分的备选算子及其错误值)
        ('xp_buy_hp_cost', (6, 8), 6, {'max': 8, 'sum': 14}),          # or vs max/sum
        ('refresh_surprise_every', (0, 3), 3, {'裸min': 0, 'sum': 3}),  # 守卫min vs 裸min
        ('gold_next_nodes_count', (2, 5), 5, {'sum': 7}),               # max vs sum
        ('win_reward_mult', (1.5, 2.0), 2.0, {'sum': 3.5, '乘积': 3.0}),
        ('interest_cap_override', (3, 7), 7, {'sum': 10}),
        ('interest_flat_per_node', (2, 3), 5, {'max': 3}),              # 五族:sum vs max
        ('gold_at_node', (70, 30), 100, {'max': 70}),
        ('gold_at_node_offset', (5, 3), 3, {'sum': 8, 'max': 5}),       # 触发位:守卫min
        ('gold_at_level', (40, 25), 65, {'max': 40}),
        ('gold_at_level_target', (9, 5), 5, {'sum': 14, 'max': 9}),
        ('xp_click_discount_from_level', (1, 2), 3, {'max': 2}),
        ('xp_click_discount_from_level_at', (8, 6), 6, {'sum': 14, 'max': 8}),
        ('refresh_shop_rewrite_every_3cost', (0, 4), 4, {'裸min': 0}),
    ]
    for fname, (va, vb), expect, _alt in cases:
        names = patched_registry(
            [_mk('甲', **{fname: va}), _mk('乙', **{fname: vb})])
        got = getattr(aggregate_economy(names), fname)
        assert got == expect, f'{fname}: 期望 {expect}(登记算子), 实现={got}'
        ref = _reference_aggregate([EconomyEffect(**{fname: va}),
                                    EconomyEffect(**{fname: vb})])
        assert ref[fname] == expect


# 区分力非零证明锚:篡改分型表算子(or→max)后,同 fixture 下求值器
# 必须与实现分歧——证明本断言集在「仅隶属断言恒绿」的语义错账
# 构造下会红,不是恒绿护栏。
def test_half3_detection_power_proof(patched_registry) -> None:
    mutated = {k: ({**v, 'op': 'max'} if k == 'xp_buy_hp_cost' else v)
               for k, v in AGG_FIELDS.items()}
    effects = [EconomyEffect(xp_buy_hp_cost=6), EconomyEffect(xp_buy_hp_cost=8)]
    names = patched_registry([_mk('甲', xp_buy_hp_cost=6),
                              _mk('乙', xp_buy_hp_cost=8)])
    impl = aggregate_economy(names).xp_buy_hp_cost
    assert impl == 6                       # 实现语义=or
    assert _reference_aggregate(effects, mutated)['xp_buy_hp_cost'] == 8 != impl


# ==================== 金守恒:净守恒单代表(金钱类按裁决收缩) ====================

def test_gold_net_conserved_buy_sell_roundtrip() -> None:
    """净守恒代表:1★ 牌买卖一回合金总量守恒——simulate 花 −cost、退
    +sell_refund(1★,cost)=cost,净 0(对任意费用成立,注册表改费不红;
    支出面与退金面经同一事务单一源 cw_state.simulate)。红 = 中间事务
    静默分叉(花金/退金两套算账走样)。"""
    s0 = CwSimFrame(gold=50)
    s1 = simulate(s0, BuyCard(ShopCard(x=0, name='三月七', cost=1, star=1)))
    assert s1.gold < s0.gold, '买入应扣金(花出面缺席)'
    s2 = simulate(s1, SellBench(bench_idx=0))
    assert s2.gold == s0.gold, (
        f'1★ 买卖回合应净守恒,实得 {s0.gold}→{s1.gold}→{s2.gold}')


def test_adr0150_base_layer_full() -> None:
    """base 层全量:策略 335(334 plaza + 1 补遗)/ 环境 83(官方全量,与数据银行同口径)。

    (过继锁:原 test_cw_investment 文件头声明本计数为全测试仓唯一承载,
    禁删;套件重建批 A 暂挂本文件防断链,终局归编 #15 test_cw_data_registry。)
    """
    from sr_od.application.currency_war.data.cw_invest_data import (
        PLAZA_AUGMENTS,
        PLAZA_PORTALS,
    )
    assert len(PLAZA_AUGMENTS) == 334
    assert len(PLAZA_PORTALS) == 83
    assert len(INVESTMENT_STRATEGIES) == 335  # + 补遗 追击星徽套组(二)
    assert len(INVESTMENT_ENVS) == 83
    # id 主键唯一
    ids = [a.id for a in PLAZA_AUGMENTS]
    assert len(set(ids)) == len(ids)
    # 补遗在表且 source 是米游社 content
    extra = INVESTMENT_STRATEGIES["追击星徽套组(二)"]
    assert extra.source == "6302"


# ==================== interest+streak 表锚(R2 息线 floor) ====================
# 测试基建(六件套单一源 = _cw_helpers;本文件 _state 为垫卡 shop
# 帧专属形状,留本地自持)


def _state(gold: int, level: int = 3) -> CwSimFrame:
    st = CwSimFrame(gold=gold, level=level, round_num=2)
    st.shop = [ShopCard(x=100, name='垫', cost=3, star=1)]
    st.bench = []
    st.deployed = []
    return st


class TestR2InterestFloor:

    def _frame(self, gold: int):
        """R1 可负担性过账帧(ADR-0516 形式二;旧 V_GAP 注入开闸语义随
        V̄ 链退役):lv6、合格集收缩到单目标成员(其余线成员 2★ 成型
        出域)、目标 j=2 差 1 张(账 ≈19 金)⇒ 金 ≥80 时 R1 必过,
        R2 成唯一门。视界先验(9,5,7)。
        """
        comp = _comp()
        members = _members(comp)
        target = min(
            (m for m in members
             if CHARACTERS[m].cost
             and 0.0 < expected_refreshes_for_card(
                 6, CHARACTERS[m].cost, 2, 2) < float('inf')),
            key=lambda m: expected_refreshes_for_card(
                 6, CHARACTERS[m].cost, 2, 2))
        others = [m for m in members if m != target]
        bench = [_bc(target), _bc(target, slot=2)] \
            + [_bc(m, star=2, slot=i + 3) for i, m in enumerate(others)]
        st = _state(gold, level=6)
        st.bench = bench
        sess = _session(comp)
        sess.plane_lengths_seen = [9, 5, 7]
        return comp, st, sess

    def test_cap_resolved_parameterizes_floor(self):
        """cap 语境锁(息线表锚):g*=10×cap_resolved 随 session 覆写参数
        化——cap=10(息律投资语境)下金 80 < 100+ρ ⇒ 拒(50 非域常数,
        息线 floor「拍常数」禁案的判别锁)。
        (金钱类收缩:floor 门过下界/贴线拒刷两行按裁决不搬,git 可复活。)"""
        comp, st, sess = self._frame(80)
        sess.active_strategies = ['利息上调']   # ADR-0598 注入面迁移
        acts = _decide(st, sess)
        assert not [a for a in acts if isinstance(a, RefreshShop)]


# —— economy_score 利息/streak 真值(自 test_cw_decisions economy 段并入) ——


def test_economy_interest() -> None:
    """中期,存金近 50 > 存金 0(利息加分)。"""
    rich = CwSimFrame(gold=50, round_num=5, level=6, plane=2)
    poor = CwSimFrame(gold=0, round_num=5, level=6, plane=2)
    assert economy_score(rich, "adaptive") > economy_score(poor, "adaptive")


def test_economy_streak_bonus() -> None:
    """C 杠杆 2(streak 接线)。ADR-0128(复查 #5,核心机制:27):货币战争**无连败补偿** ——
    只计连胜方向;连败 0 分(旧 magnitude 对称计 = 虚构连败金,已修)。
    """
    base = CwSimFrame(gold=50, round_num=5, level=6, plane=2)             # streak 默认 0
    win3 = CwSimFrame(gold=50, round_num=5, level=6, plane=2, streak=3)   # 连胜 3
    loss3 = CwSimFrame(gold=50, round_num=5, level=6, plane=2, streak=-3)  # 连败 3
    assert economy_score(win3, "adaptive") > economy_score(base, "adaptive"), "连胜 3 > 无 streak"
    assert economy_score(loss3, "adaptive") == pytest.approx(economy_score(base, "adaptive")), (
        "无连败补偿:连败 3 不加分(核心机制:27)"
    )


# ==================== budget 拒付单代表(归 fail-closed;自 test_cw_blood_xp_gate 并入) ====================
# (金钱类收缩:T6 阈值边界逐点红证按裁决不搬,git 可复活。)


def _blood_session(active: list[str] | None = None, **state_kw) -> SimpleNamespace:
    """血闸消费面依赖桩:active_strategies(其余无关;金账读容器)。"""
    return SimpleNamespace(
        active_strategies=list(active or ['奋斗协议']),
    )


def _blood_bs(hp: int | None, *, source: str = 'observation',
              level: int | None = None) -> GameState:
    """血闸容器帧构造器(波 2 起闸输入 = GameState;来源三态即旧两位
    语义的容器形态:observation=真读/prior=不可信 fail-closed)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        BS_SCHEMA_VERSION,
        ChannelSig,
        GameState,
    )
    sig = ChannelSig(family='obs', actor='cw_observation', mode='read')
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    if level is not None:
        bs.observe(bs.level, level, sig=sig)
    if hp is not None:
        if source == 'observation':
            bs.observe(bs.hp, hp, sig=sig)
        elif source == 'prior':
            bs.write_prior(bs.hp, hp, evidence='prior:adr-0559', sig=sig)
        else:
            raise ValueError(f'未知 source {source!r}')
    return bs


def test_blood_xp_gate_untrusted_hp_fail_closed() -> None:
    """T7 hp 不可信帧 fail-closed(P21 blood_budget_levelup_blocked 同面同论证:
    误放=血线内追级、误拦=少升一级,非对称);消费面 bs 缺席同向;
    金本位(无 active 血本位卡)恒 True 直通(零改动面)。"""
    assert blood_xp_gate(None, True, 3, 6) is False    # hp 无真值
    assert blood_xp_gate(100, False, 3, 6) is False    # 可信位 False
    assert blood_xp_gate(None, False, 3, 6) is False
    # 消费适配面:bs 缺席 fail-closed;金本位直通
    assert blood_xp_gate_for(None, _blood_session()) is False
    assert blood_xp_gate_for(_blood_bs(100),
                             SimpleNamespace(active_strategies=[])) is True
    # 不可信帧经消费适配面同样拒(兜底 100 帧语义 = ADR-0282:两位皆 False,
    # 容器形态 = prior 支来源,prior/logic 支 fail-closed)
    st_ghost = _blood_bs(100, source='prior', level=3)
    assert blood_xp_gate_for(st_ghost, _blood_session()) is False


# ==================== D 牌期望模型边界(自 test_cw_sim_suite.py shop_odds 节回补,T-197) ====================
# 前身 = test_cw_shop_odds.py 随测试重组批 f799914 整体退役;边界语义在现行
# data/cw_shop_odds.py 未演进(p≤0/k≤0/j≥k → 0;查表无数据 → 0),回补防回潮。
# v/a 参数从注册表单一源现算(DISTINCT_CARDS_PER_COST/POOL_COPIES_PER_CARD),
# 不手抄旧锁常数(README 第 9 条);单一源守卫与消费面公式 =
# test_cw_statefn.py(expected_refreshes 禁第二实现 + refresh_prob 进期望式)。

def test_zero_p_returns_zero() -> None:
    """p≤0 → 0(该等级不出该费用,刷不到;无穷循环前置短路)。"""
    assert expected_refreshes(
        0.0, DISTINCT_CARDS_PER_COST[3], POOL_COPIES_PER_CARD[3], 0, 3, 0,
    ) == 0.0


def test_owned_meets_target_returns_zero() -> None:
    """j≥k → 0(已凑齐,无需再刷;2星 k=3 与 3星 k=9 两档)。"""
    assert expected_refreshes(
        0.4, DISTINCT_CARDS_PER_COST[3], POOL_COPIES_PER_CARD[3], 0, 3, 3,
    ) == 0.0
    assert expected_refreshes(
        0.4, DISTINCT_CARDS_PER_COST[3], POOL_COPIES_PER_CARD[3], 0, 9, 10,
    ) == 0.0


def test_refresh_prob_lookup() -> None:
    """refresh_prob 查表:lv7 3费 = 0.40 实机 OCR 权威锚(D-91,2026-08-11
    商店刷新概率表);查表一致性 + 无数据等级 → 0(该等级不出该费用)。"""
    from sr_od.application.currency_war.data.cw_shop_odds import REFRESH_PROB
    assert refresh_prob(7, 3) == REFRESH_PROB[7][3]
    assert REFRESH_PROB[7][3] == pytest.approx(0.4, abs=1e-2)
    assert refresh_prob(99, 3) == 0.0, '无该等级 → 0'


# ==================== xp 买费折扣修复锁族(正本 = ADR-0632) ====================
# 规范语义 = strategy-env-impacts.md §2 通用模式 1(2026-09-10 定稿):
# 观察优先、兜底逻辑——显示价(最近备战帧 OCR,游戏已算好折扣)直通不再减;
# 观察缺省 → 兜底 = 基准 4 − 折扣(max 0;商业间谍 xp_buy_cost_discount +
# 成长的快乐等级门 xp_click_discount_from_level 族)。
# 改前病理(ADR-0632 背景核对):xp_click_cost 对两支无差别再减(显示价支双扣);
# upgrade_plan_fee 裸字段取价零折扣(反方向单侧错)——两函数互补单侧错。

_JUST_JOY = '成长的快乐'    # xp_click_discount_from_level=1 @8(cw_investments 注册)
_JUST_SPY = '商业间谍'      # xp_buy_cost_discount=1(cw_investments 注册)


def _xp_state(level: int = 5, strategies: list[str] | None = None,
              display: int | None = None) -> GameState:
    """费用轴最小决策帧(经济读口已切容器:桥装为测试迁移单一源形态)。
    strategies=已持投资策略;display=OCR 显示价,None=未读到走兜底支
    ——两支来源凭容器 level_up_cost Field 判别。"""
    st = CwSimFrame(gold=30, level=level, round_num=2)
    st.active_strategies = list(strategies or [])
    st.level_up_cost = display
    return _bsb(st)


def test_xp_fee_no_discount_invariance() -> None:
    """无折扣局不变锁:未持任何折扣卡时费用与改前逐位一致(方案审修改清单④①)。

    改前病理只在持折扣卡时显形,本锁钉住占绝大多数的无间谍局零漂移:
    显示价支原值直通、兜底支基价 4、upgrade_plan_fee = 击数×同价
    (击数值来自 cw_plane_table 注册表,非本锁辖值)。"""
    from sr_od.application.currency_war.kernel.cw_economy import (
        upgrade_plan_fee,
        xp_click_cost,
    )
    from sr_od.application.currency_war.kernel.cw_plane_table import (
        clicks_to_level,
    )
    assert xp_click_cost(_xp_state(display=3)) == 3     # 显示价支:原样
    assert xp_click_cost(_xp_state(display=5)) == 5
    assert xp_click_cost(_xp_state(display=None)) == 4  # 兜底支:基价
    assert upgrade_plan_fee(_xp_state(level=5, display=3)) \
        == clicks_to_level(5) * 3
    assert upgrade_plan_fee(_xp_state(level=5, display=None)) \
        == clicks_to_level(5) * 4


def test_xp_click_display_price_passthrough() -> None:
    """显示价直通锁:持商业间谍时显示价 3 原样返回(改前双扣 = 2,真值 3)。

    依据 = strategy-env-impacts §3 商业间谍条「显示价即折后价,游戏已算好」
    (2026-09-10 用户确认);对已折显示价再减模型折扣 = 双重折扣。"""
    from sr_od.application.currency_war.kernel.cw_economy import xp_click_cost
    assert xp_click_cost(_xp_state(strategies=[_JUST_SPY], display=3)) == 3
    # 直通对等级门折扣同样成立(成长快乐 8 级起,游戏侧显示价已含):
    assert xp_click_cost(_xp_state(level=8, strategies=[_JUST_JOY],
                                   display=3)) == 3


def test_xp_click_branch_equivalence_with_discount() -> None:
    """两支等价锁:同持卡同等级,观察支(显示价=基准−折扣)与兜底支同价。

    等价前提 = 显示价与注册表折扣模型同源(间谍 −1 → 显示 3);
    改前病理 = 显示价支再减 → 2 ≠ 3(本修复要关的回归本体,方案审④②)。"""
    from sr_od.application.currency_war.kernel.cw_economy import xp_click_cost
    observed = _xp_state(strategies=[_JUST_SPY], display=3)
    fallback = _xp_state(strategies=[_JUST_SPY], display=None)
    assert xp_click_cost(observed) == xp_click_cost(fallback) == 3


@pytest.mark.parametrize('level,strategies,expected', [
    (7, [_JUST_JOY], 4),                    # 等级门前:无减项
    (8, [_JUST_JOY], 3),                    # 门前跨档:−1
    (9, [_JUST_JOY], 3),                    # 门后持续
    (7, [_JUST_SPY, _JUST_JOY], 3),         # 门前:仅间谍 −1
    (8, [_JUST_SPY, _JUST_JOY], 2),         # 门后:折扣叠加 −2
], ids=['gate-before', 'gate-at', 'gate-persists',
        'spy-only-before', 'stacked-after'])
def test_xp_click_joy_level_gate_truth_table(
        level: int, strategies: list[str], expected: int) -> None:
    """成长的快乐真值表锁(兜底支等级门;方案审关键修改②,关闭
    「登记不消费」豁免口)。

    聚合分型已在册(sum+guarded_min,AGG_FIELDS 两字段在表),本锁钉消费位:
    折扣合计 = xp_buy_cost_discount + (等级 ≥ xp_click_discount_from_level_at
    时 xp_click_discount_from_level)。sim 恒兜底支(无 OCR),不消费 =
    sim 对该卡局费用恒虚高 1 金/击,恰保留本修复要消灭的 sim/实机分歧。"""
    from sr_od.application.currency_war.kernel.cw_economy import xp_click_cost
    assert xp_click_cost(
        _xp_state(level=level, strategies=strategies)) == expected


def test_xp_click_fallback_clamp_floor(monkeypatch) -> None:
    """兜底支下限 0 钳(语义保持):折扣合计超基准时钳 0 不出负。

    注册表现无合计 ≥4 的折扣源(间谍 1 + 快乐 1 = 2),钳臂经
    _strategy_economy 缝注入合成折扣覆盖(纯函数消费面,monkeypatch.setattr
    隔离,README 第 1 条)。"""
    from sr_od.application.currency_war.kernel import cw_economy as ke
    monkeypatch.setattr(
        ke, '_strategy_economy',
        lambda _st: EconomyEffect(xp_buy_cost_discount=6))
    assert ke.xp_click_cost(_xp_state(display=None)) == 0


def test_upgrade_plan_fee_delegates_discount_aware_pricing() -> None:
    """upgrade_plan_fee 委托锁:sim 形态(无显示价)持商业间谍时升级总费
    = 击数×3(改前裸字段取价 = 击数×4,反方向单侧错,方案审问题 3-a)。

    委托语义 = 击数面零变化(clicks_to_level 只供次数),取价唯一源 =
    xp_click_cost;显示价支委托后与直通同源(改前碰巧对 → 委托后结构性对)。"""
    from sr_od.application.currency_war.kernel.cw_economy import (
        upgrade_plan_fee,
    )
    from sr_od.application.currency_war.kernel.cw_plane_table import (
        clicks_to_level,
    )
    fallback = _xp_state(level=5, strategies=[_JUST_SPY], display=None)
    assert upgrade_plan_fee(fallback) == clicks_to_level(5) * 3
    observed = _xp_state(level=5, strategies=[_JUST_SPY], display=3)
    assert upgrade_plan_fee(observed) == clicks_to_level(5) * 3


def test_upgrade_plan_fee_no_second_discount_implementation() -> None:
    """结构锁:upgrade_plan_fee 内禁第二处独立取价/折扣实现(方案审关键修改①)。

    「同一语义两处实现」正是互补单侧错的漂移温床(ADR-0632);源面
    断言:只许委托 xp_click_cost,禁裸读 level_up_cost、禁折扣字段字样。"""
    import inspect

    from sr_od.application.currency_war.kernel import cw_economy as ke
    src = inspect.getsource(ke.upgrade_plan_fee)
    assert 'xp_click_cost' in src, '未委托 xp_click_cost 单一源'
    assert 'level_up_cost' not in src, '裸字段取价复活 = 第二实现回归'
    assert 'xp_buy_cost_discount' not in src, '独立折扣计算复活'


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
    from test.sr_od.application.currency_war._cw_helpers import cw4_feed
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
