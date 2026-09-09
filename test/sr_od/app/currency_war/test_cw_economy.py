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

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
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
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_ENVS,
    INVESTMENT_STRATEGIES,
    EconomyEffect,
    aggregate_economy,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    GameState,
    RefreshShop,
    SellBench,
    ShopCard,
    simulate,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_comp as _comp,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_decide as _decide,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_members as _members,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_session as _session,
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
    s0 = GameState(gold=50)
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


def _state(gold: int, level: int = 3) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2)
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
        dd-026 备选 2「拍常数」禁案的判别锁)。
        (金钱类收缩:floor 门过下界/贴线拒刷两行按裁决不搬,git 可复活。)"""
        comp, st, sess = self._frame(80)
        sess.active_strategies = ['利息上调']   # ADR-0598 注入面迁移
        acts = _decide(st, sess)
        assert not [a for a in acts if isinstance(a, RefreshShop)]


# —— economy_score 利息/streak 真值(自 test_cw_decisions economy 段并入) ——


def test_economy_interest() -> None:
    """中期,存金近 50 > 存金 0(利息加分)。"""
    rich = GameState(gold=50, round_num=5, level=6, plane=2)
    poor = GameState(gold=0, round_num=5, level=6, plane=2)
    assert economy_score(rich, "adaptive") > economy_score(poor, "adaptive")


def test_economy_streak_bonus() -> None:
    """C 杠杆 2(streak 接线)。ADR-0128(复查 #5,核心机制:27):货币战争**无连败补偿** ——
    只计连胜方向;连败 0 分(旧 magnitude 对称计 = 虚构连败金,已修)。
    """
    base = GameState(gold=50, round_num=5, level=6, plane=2)             # streak 默认 0
    win3 = GameState(gold=50, round_num=5, level=6, plane=2, streak=3)   # 连胜 3
    loss3 = GameState(gold=50, round_num=5, level=6, plane=2, streak=-3)  # 连败 3
    assert economy_score(win3, "adaptive") > economy_score(base, "adaptive"), "连胜 3 > 无 streak"
    assert economy_score(loss3, "adaptive") == pytest.approx(economy_score(base, "adaptive")), (
        "无连败补偿:连败 3 不加分(核心机制:27)"
    )


# ==================== budget 拒付单代表(归 fail-closed;自 test_cw_blood_xp_gate 并入) ====================
# (金钱类收缩:T6 阈值边界逐点红证按裁决不搬,git 可复活。)


def _blood_session(active: list[str] | None = None, **state_kw) -> SimpleNamespace:
    """血闸消费面依赖桩:active_strategies + last_state(其余无关)。"""
    return SimpleNamespace(
        active_strategies=list(active or ['奋斗协议']),
        last_state=GameState(**state_kw),
    )


def test_blood_xp_gate_untrusted_hp_fail_closed() -> None:
    """T7 hp 不可信帧 fail-closed(P21 blood_budget_levelup_blocked 同面同论证:
    误放=血线内追级、误拦=少升一级,非对称);消费面 state 缺席同向;
    金本位(无 active 血本位卡)恒 True 直通(零改动面)。"""
    assert blood_xp_gate(None, True, 3, 6) is False    # hp 无真值
    assert blood_xp_gate(100, False, 3, 6) is False    # 可信位 False
    assert blood_xp_gate(None, False, 3, 6) is False
    # 消费适配面:state 缺席 fail-closed;金本位直通
    assert blood_xp_gate_for(None, _blood_session()) is False
    assert blood_xp_gate_for(GameState(hp=100, hp_readable=True),
                             SimpleNamespace(active_strategies=[])) is True
    # 不可信帧经消费适配面同样拒(兜底 100 帧语义 = ADR-0282:两位皆 False,
    # 由读取端显式写;GameState 构造缺省 hp_readable=True 是 sim 恒真读帧约定)
    st_ghost = GameState(level=3, hp=100, hp_readable=False)
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
