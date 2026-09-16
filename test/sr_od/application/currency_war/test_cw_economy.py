"""CW 经济域测试(#4):金守恒(单代表)/ budget 拒付(fail-closed 单代表)/
R2 息线 floor / D 牌期望边界 / ev_arm 值域(aggregate_economy 分型登记)。

覆盖面(金钱类按 2026-09-09 编排者裁决收缩:实机结算对账 + sim 段检双层
已覆盖逐面金钱锁,单位层只留 commit→sim 空窗价值):
- budget 拒付(1 代表,归 fail-closed):hp 不可信帧 blood_xp_gate 拒;
- R2 息线 floor:cap 语境参数化锁(ADR-0598 注入面);
- D 牌期望边界:expected_refreshes/refresh_prob 边界一条(p≤0/j≥k/
  查表缺级 → 0;v/a 参数从注册表单一源现算,不手抄常数);
- ev_arm 值域:aggregate_economy 分型登记表逐字段算子期望(值域表)。

退役面(审计判决删除):金净守恒代表锁(test_gold_net_conserved_buy_sell_
roundtrip,连 simulate import——锁的 simulate 全仓零生产消费,金钱面
= 实机结算对账 + transfer_golden 活转移函数直锁)、economy_score 利息/
streak 真值(src 零调用)、区分力非零证明锚(元测试)、refresh_prob 查表
一致性锚(缺级→0 腿并入 D 牌期望边界)、xp 兜底支钳 0 单测(并入 joy
真值表一行)、pair 断供驱逐墓碑、ADR-0150 base 层全量计数锚(纯数据计
数;其「过继锁禁删」声明随审计判决解除,335/83 计数归编 #15
test_cw_data_registry 待承接)。

合并面(第二刀):xp 费用无折扣不变+显示价直通并一;排程触发①②参数化
真值表并一;预算值域+w721 塌缩带(合法 0 帧表驱动)并一;pair 物化+
断供清零并一。

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
    refresh_ev_budget,
    reserve_cap,
    schedule_upgrade,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    pair_target_comp,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    EconomyEffect,
    aggregate_economy,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    BenchChar,
    CwSimFrame,
    RefreshShop,
    ShopCard,
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
        # (字段, 两成员值, 登记算子期望)
        ('xp_buy_hp_cost', (6, 8), 6),
        ('refresh_surprise_every', (0, 3), 3),
        ('gold_next_nodes_count', (2, 5), 5),
        ('win_reward_mult', (1.5, 2.0), 2.0),
        ('interest_cap_override', (3, 7), 7),
        ('interest_flat_per_node', (2, 3), 5),
        ('gold_at_node', (70, 30), 100),
        ('gold_at_node_offset', (5, 3), 3),
        ('gold_at_level', (40, 25), 65),
        ('gold_at_level_target', (9, 5), 5),
        ('xp_click_discount_from_level', (1, 2), 3),
        ('xp_click_discount_from_level_at', (8, 6), 6),
        ('refresh_shop_rewrite_every_3cost', (0, 4), 4),
    ]
    for fname, (va, vb), expect in cases:
        names = patched_registry(
            [_mk('甲', **{fname: va}), _mk('乙', **{fname: vb})])
        got = getattr(aggregate_economy(names), fname)
        assert got == expect, f'{fname}: 期望 {expect}(登记算子), 实现={got}'
        ref = _reference_aggregate([EconomyEffect(**{fname: va}),
                                    EconomyEffect(**{fname: vb})])
        assert ref[fname] == expect


# (金净守恒代表锁已删——simulate 零生产消费,审计判决;金钱面 = 实机
#  结算对账 + test_cw_transfer_golden 活转移函数直锁。)


# ==================== R2 息线 floor(cap 语境参数化) ====================
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


# ==================== budget 拒付单代表(归 fail-closed;自 test_cw_blood_xp_gate 并入) ====================
# (金钱类收缩:T6 阈值边界逐点红证按裁决不搬,git 可复活。)


def _blood_session(active: list[str] | None = None, **state_kw) -> SimpleNamespace:
    """血闸消费面依赖桩:active_strategies(其余无关;金账读容器)。"""
    return SimpleNamespace(
        active_strategies=list(active or ['奋斗协议']),
    )


def _blood_gs(hp: int | None, *, source: str = 'observation',
              level: int | None = None) -> GameState:
    """血闸容器帧构造器(波 2 起闸输入 = GameState;来源三态即旧两位
    语义的容器形态:observation=真读/prior=不可信 fail-closed)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        GAME_STATE_SCHEMA_VERSION,
        ChannelSig,
        GameState,
    )
    sig = ChannelSig(family='obs', actor='cw_observation', mode='read')
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if level is not None:
        gs.observe(gs.level, level, sig=sig)
    if hp is not None:
        if source == 'observation':
            gs.observe(gs.hp, hp, sig=sig)
        elif source == 'prior':
            gs.write_prior(gs.hp, hp, evidence='prior:adr-0559', sig=sig)
        else:
            raise ValueError(f'未知 source {source!r}')
    return gs


def test_blood_xp_gate_untrusted_hp_fail_closed() -> None:
    """T7 hp 不可信帧 fail-closed(P21 blood_budget_levelup_blocked 同面同论证:
    误放=血线内追级、误拦=少升一级,非对称);消费面 gs 缺席同向;
    金本位(无 active 血本位卡)恒 True 直通(零改动面)。"""
    assert blood_xp_gate(None, True, 3, 6) is False    # hp 无真值
    assert blood_xp_gate(100, False, 3, 6) is False    # 可信位 False
    assert blood_xp_gate(None, False, 3, 6) is False
    # 消费适配面:gs 缺席 fail-closed;金本位直通
    assert blood_xp_gate_for(None, _blood_session()) is False
    assert blood_xp_gate_for(_blood_gs(100),
                             SimpleNamespace(active_strategies=[])) is True
    # 不可信帧经消费适配面同样拒(兜底 100 帧语义 = ADR-0282:两位皆 False,
    # 容器形态 = prior 支来源,prior/logic 支 fail-closed)
    st_ghost = _blood_gs(100, source='prior', level=3)
    assert blood_xp_gate_for(st_ghost, _blood_session()) is False


# ==================== D 牌期望模型边界 ====================
# 边界语义(data/cw_shop_odds.py 现行口径):p≤0/k≤0/j≥k → 0;查表无数据 → 0。
# v/a 参数从注册表单一源现算(DISTINCT_CARDS_PER_COST/POOL_COPIES_PER_CARD),
# 不手抄常数;单一源守卫 = 本文件 expected_refreshes 边界组(禁第二实现)。

def test_expected_refreshes_boundaries() -> None:
    """D 牌期望边界一条:p≤0 → 0(该等级不出该费用,刷不到,无穷循环前置
    短路);j≥k → 0(已凑齐,无需再刷;2星 k=3 与 3星 k=9 两档);查表
    缺级 → 0(refresh_prob 同契约,该等级不出该费用)。"""
    assert expected_refreshes(
        0.0, DISTINCT_CARDS_PER_COST[3], POOL_COPIES_PER_CARD[3], 0, 3, 0,
    ) == 0.0
    assert expected_refreshes(
        0.4, DISTINCT_CARDS_PER_COST[3], POOL_COPIES_PER_CARD[3], 0, 3, 3,
    ) == 0.0
    assert expected_refreshes(
        0.4, DISTINCT_CARDS_PER_COST[3], POOL_COPIES_PER_CARD[3], 0, 9, 10,
    ) == 0.0
    assert refresh_prob(99, 3) == 0.0, '查表缺级 → 0'


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


def test_xp_fee_no_discount_invariant_and_display_passthrough() -> None:
    """xp 费用两形态一锁(合并原 test_xp_fee_no_discount_invariance /
    test_xp_click_display_price_passthrough,断言腿逐条保留):

    - 无折扣局不变锁:未持任何折扣卡时费用与改前逐位一致(方案审修改
      清单④①)——显示价支原值直通、兜底支基价 4、upgrade_plan_fee =
      击数×同价(击数值来自 cw_plane_table 注册表,非本锁辖值)。改前
      病理只在持折扣卡时显形,本锁钉住占绝大多数的无间谍局零漂移;
    - 显示价直通锁:持商业间谍时显示价 3 原样返回(改前双扣 = 2,真值 3)。
      依据 = strategy-env-impacts §3 商业间谍条「显示价即折后价,游戏已
      算好」(2026-09-10 用户确认);对已折显示价再减模型折扣 = 双重折扣,
      对等级门折扣同样成立(成长快乐 8 级起,游戏侧显示价已含)。"""
    from sr_od.application.currency_war.kernel.cw_economy import (
        upgrade_plan_fee,
        xp_click_cost,
    )
    from sr_od.application.currency_war.kernel.cw_plane_table import (
        clicks_to_level,
    )
    # 无折扣局不变(显示价支/兜底支/upgrade_plan_fee 两支)
    assert xp_click_cost(_xp_state(display=3)) == 3     # 显示价支:原样
    assert xp_click_cost(_xp_state(display=5)) == 5
    assert xp_click_cost(_xp_state(display=None)) == 4  # 兜底支:基价
    assert upgrade_plan_fee(_xp_state(level=5, display=3)) \
        == clicks_to_level(5) * 3
    assert upgrade_plan_fee(_xp_state(level=5, display=None)) \
        == clicks_to_level(5) * 4
    # 显示价直通(持折扣卡;改前双扣,等级门同理)
    assert xp_click_cost(_xp_state(strategies=[_JUST_SPY], display=3)) == 3
    assert xp_click_cost(_xp_state(level=8, strategies=[_JUST_JOY],
                                   display=3)) == 3


@pytest.mark.parametrize('level,strategies,expected,patch_discount', [
    (7, [_JUST_JOY], 4, None),              # 等级门前:无减项
    (8, [_JUST_JOY], 3, None),              # 门前跨档:−1
    (9, [_JUST_JOY], 3, None),              # 门后持续
    (7, [_JUST_SPY, _JUST_JOY], 3, None),   # 门前:仅间谍 −1
    (8, [_JUST_SPY, _JUST_JOY], 2, None),   # 门后:折扣叠加 −2
    (7, [], 0, 6),                          # 兜底支钳 0:折扣合计超基准不出负
], ids=['gate-before', 'gate-at', 'gate-persists',
        'spy-only-before', 'stacked-after', 'clamp-zero'])
def test_xp_click_joy_level_gate_truth_table(
        level: int, strategies: list[str], expected: int,
        patch_discount: int | None, monkeypatch: pytest.MonkeyPatch) -> None:
    """成长的快乐真值表锁(兜底支等级门;方案审关键修改②,关闭
    「登记不消费」豁免口)+ 兜底支下限 0 钳行。

    聚合分型已在册(sum+guarded_min,AGG_FIELDS 两字段在表),本锁钉消费位:
    折扣合计 = xp_buy_cost_discount + (等级 ≥ xp_click_discount_from_level_at
    时 xp_click_discount_from_level)。sim 恒兜底支(无 OCR),不消费 =
    sim 对该卡局费用恒虚高 1 金/击,恰保留本修复要消灭的 sim/实机分歧。
    钳 0 行:注册表现无合计 ≥4 的折扣源(间谍 1 + 快乐 1 = 2),钳臂经
    _strategy_economy 缝注入合成折扣覆盖(monkeypatch.setattr 隔离,测试
    零真实副作用)。"""
    from sr_od.application.currency_war.kernel import cw_economy as ke
    from sr_od.application.currency_war.kernel.cw_economy import xp_click_cost
    if patch_discount is not None:
        monkeypatch.setattr(
            ke, '_strategy_economy',
            lambda _st: EconomyEffect(xp_buy_cost_discount=patch_discount))
    assert xp_click_cost(
        _xp_state(level=level, strategies=strategies)) == expected


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


# (三审整删)原 test_upgrade_plan_fee_no_second_discount_implementation
# 「结构锁」(getsource 断言函数体内禁第二处取价/折扣实现)——源码扫描形态
# (README 禁止清单);委托语义行为半由
# test_upgrade_plan_fee_delegates_discount_aware_pricing 辖,「同一语义
# 两处实现」防线归 review 与代码规范。


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


# --- 排程核规则锁(W615 R4;触发①②真值表并一)-----------------------


def _schedule_rows() -> dict:
    """排程触发①②表行构造器(帧构造延迟调用,保各触发前置构帧差异;
    断言腿逐条 = 原 test_schedule_pop_slot_trigger /
    test_schedule_probability_trigger_requires_engine)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_vocab import (
        deployed_occupied,
    )

    def _ch(name: str, slot: int, star: int) -> BenchChar:
        fac = (CHARACTERS[name].factions or ('?',))[0]
        return BenchChar(slot=slot, char_id=name, faction=fac, star=star)

    def _formed_bench() -> list[BenchChar]:
        return [_ch('阿格莱雅', i, 2) for i in range(BENCH_CAPACITY)]

    def pop_not_full():
        # ①负腿:bench 满 2★ 成型件 ∧ deployed 未满 → 人口位不触发
        #(gold 30<息线:禁升②不触发——双负前置帧)
        st = _ba_state(gold=30, level=6, r=9, bench=_formed_bench())
        assert deployed_occupied(st.deployed) < st.max_units()   # 有空位
        assert not schedule_upgrade(cw4_box(st), _ba_sess_of(st))
        st.dep = None
        return st, _ba_sess_of(st)

    def pop_cap_full():
        # ①正腿:cap 满(deployed 填满)→ 人口位触发(最高义务)
        st = _ba_state(gold=30, level=6, r=9, bench=_formed_bench())
        st.dep = None
        st.deployed = [BenchChar(slot=20 + i, char_id=f'杂{i}',
                                 faction='公司', star=1)
                       for i in range(st.max_units())]
        assert deployed_occupied(st.deployed) >= st.max_units()
        return st, _ba_sess_of(st)

    def prob_engine_live():
        # ②正腿:锁定 4 费核(大移位带,U_L 检验过;ADR-0516 修正①)
        #+ 息引擎已立 + 峰值 9>7 ∧ 60≥息线
        return _ba_state(gold=60, level=7), _ba_locked_4cost_sess()

    def prob_engine_missing():
        # ②负腿:金 49<息线 50 → 引擎未立,禁升(False 即预告态也不发)
        return _ba_state(gold=49, level=7), _ba_locked_4cost_sess()

    def prob_peak_reached():
        # ②负腿:峰值已达(lv9=峰值级)→ 无排程
        return _ba_state(gold=60, level=9), _ba_locked_4cost_sess()

    return {
        'pop-slot-bench-formed-not-full': (pop_not_full, False),
        'pop-slot-cap-full': (pop_cap_full, True),
        'probability-engine-live-peak-ahead': (prob_engine_live, True),
        'probability-engine-missing': (prob_engine_missing, False),
        'probability-peak-reached': (prob_peak_reached, False),
    }


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


@pytest.mark.parametrize('case_id', list(_schedule_rows()))
def test_schedule_triggers_truth_table(case_id: str) -> None:
    """排程触发①②真值表一锁(参数化并一):
    ①人口位[33]:cap 满 ∧ bench 有成型件(2★)→ 排程(最高义务,不受
    息引擎前置辖——当轮兑现战力);
    ②概率级[3]+[12]:目标峰值级>当前级 ∧ 息引擎已立;禁升条件 = 息引擎
    未立不追级(gold<息线,False 即预告态也不发)、峰值已达无排程。"""
    build, expect_scheduled = _schedule_rows()[case_id]
    st, sess = build()
    got = schedule_upgrade(cw4_box(st), sess)
    if expect_scheduled:
        assert got, f'{case_id}: 应排程'
    else:
        assert not got, f'{case_id}: 不应排程'


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


# --- 预算核契约锁(W623 D2;值域+合法 0 帧表驱动并一)---------------------


def _budget_rows() -> dict:
    """预算值域表行(id → (帧构造, 期望);期望 int = 精确值,'>0' = 正值)。"""
    def _collapse_frame():
        # 塌缩带帧(ADR-0475):锁定 4 费核 ∧ lv5(比值 0.05 < ω=0.1)
        return _ba_state(gold=200, level=5, hp=80,
                         shop=[_sc('桑博', 2)], board={})

    return {
        # 6 刷帽(值域上界单一源)
        'refresh-cap-six': (lambda: (_ba_state(gold=200, level=6),
                                     StrategySession()), 6),
        # 合法 0 帧:g=R*(溢余 0)
        'legal-zero-exact-reserve': (lambda: (_ba_state(gold=50, level=6),
                                              StrategySession()), 0),
        # 合法 0 帧:溢余 1<刷价(准入门辖域)
        'legal-zero-below-threshold': (lambda: (_ba_state(gold=51, level=6),
                                                StrategySession()), 0),
        # 塌缩带归零(合法 0 帧第三类;原 test_w721_collapse_band 零帧腿,
        # 独家覆盖——原主题文件 test_cw_w721_overlay_b_budget 已消亡)
        'collapse-band-locked-4cost-lv5': (
            lambda: (_collapse_frame(), _ba_locked_4cost_sess()), 0),
        # 同帧未锁定(兜底链)不归零——空帧豁免(D1「空帧不缩供给」契约)
        'collapse-fallback-exempt': (
            lambda: (_collapse_frame(), StrategySession()), '>0'),
    }


@pytest.mark.parametrize('case_id', list(_budget_rows()))
def test_budget_value_domain_and_legal_zero_frames(case_id: str) -> None:
    """预算核契约一锁(值域+合法 0 帧表驱动,合并原
    test_budget_value_domain_and_legal_zero_frames /
    test_w721_collapse_band_zero_and_fallback_exempt,断言腿逐条保留):
    值域 [0,6](6 刷帽单一源);合法 0 帧三类共存——g≤R* 常态帧(全恒正
    = 契约未实现)、准入门辖域帧、塌缩带归零帧(ADR-0475;归零帧再多
    一类 max 合并结构不变);塌缩同形态的未锁定帧(兜底链)不归零——
    空帧豁免优先(细则见 ADR-0475)。"""
    build, expect = _budget_rows()[case_id]
    st, sess = build()
    got = refresh_ev_budget(cw4_box(st), sess)
    if expect == '>0':
        assert got > 0, f'{case_id}: 应为正值(空帧豁免)'
    else:
        assert got == expect, f'{case_id}: 预算期望 {expect}'


# (test_blood_budget_stop_not_inflated_by_budget_merge 已随 DP 姿态/泄息
#  指令死链删除——统一迁移批 ② MAP B 类。)


# --- R3 · pair 断供驱逐(蓝图 §4.3-R3 推广)------------------------------------


def test_pair_materialization_and_drought_reset() -> None:
    """pair 体系两面一锁(合并原 test_pair_eviction_keeps_target_chain_
    materialized / test_pair_drought_resets_when_member_visible,断言腿
    逐条保留):

    - 物化面(W578 代理门):pair 物化 → pair_target_comp(新 pair)非空
      且档位账随物化(target 链不盲;W622 P2 病灶防回归;驱逐退役后同样
      成立——部署/评分消费面不盲);
    - 断供清零面:成员再现(在店/到手)→ 断供计数清零(计数语义同
      LineTrack frozen_rounds:窗口重开即清零)。"""
    # 物化面
    pair = ('仙舟', '持续伤害')
    comp = pair_target_comp(pair)
    assert comp is not None and comp.core_chars
    assert comp.form_tiers    # 档位账随物化(部署/评分消费面不盲)
    # 断供清零面
    ist = IntentionState()
    ist.p1_pair = ('持续伤害', '仙舟')
    sess = StrategySession()
    state_of(sess).v3_intention = ist
    st = _ba_state(r=5, gold=100,
                shop=[_sc('卡芙卡', 4)], board={})   # 卡芙卡=DOT 系成员
    update_intention(cw4_box(st), ist, sess)
    assert ist.pair_drought.get('持续伤害', 0) == 0


def test_injection_consistency_single_registry_source() -> None:
    """注入一致性锁(W636 A):披露函数现算写入的披露字段与显式注入的
    接缝值逐字段一致——禁「部分字段落 DEFAULT」的双源混用(P6 契约)。
    cap 归一(ADR-0516 三源归一 + ADR-0598 随批扩展):
    schedule ② 前置息线与预算面守息线分量(reserve_cap 守息线/
    refresh_ev_budget 溢余面)都随 session
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
    # 披露面装配单源(W636 A 载体 = 披露函数):注入 reg2 披露后,披露
    # 字段 == 逐字段显式注入值(现算与披露写入合一 =
    # economy_cycle.disclose_budget;局内事实先经合成口喂入 = 生产同路)
    from test.sr_od.application.currency_war._cw_helpers import cw4_feed

    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
        gold_of,
    )
    cw4_feed(sess_ov, st2)
    from sr_od.application.currency_war.strategies.impl.mandate_v1.economy_cycle import (
        disclose_budget,
        obligation,
    )
    disclose_budget(game_state_of(sess_ov), sess_ov, reg2)
    st_ov = state_of(sess_ov)
    assert st_ov.v3_reserve_cap == reserve_cap(cw4_box(st2), sess_ov)
    assert st_ov.v3_reserve_overflow == max(
        0, gold_of(game_state_of(sess_ov)) - st_ov.v3_reserve_cap)
    assert st_ov.v3_release_budget == obligation(cw4_box(st2), sess_ov, reg2)
    assert st_ov.v3_disclosure_key == (st2.plane, st2.round_num)
    # registry 旋钮(非注册表可达值 cap=4)对披露预算面逐位惰性:非买断
    # session 同帧披露,储备线 = 默认息线链(旋钮不动预算面)
    cw4_feed(sess, st2)
    disclose_budget(game_state_of(sess), sess, reg2)
    st_base = state_of(sess)
    assert st_base.v3_reserve_cap == reserve_cap(cw4_box(st2), sess)


# (原 test_tracking_view_isolated_from_session_writers 随修正裁定
#  删除:锁主对象 _tracking_view(tracking 优先 + snapshot 静默回退)已按
#  裁定退役——滞回职责被对账仲裁批 kernel 锚定取代,回退路径即要消灭的掩盖
#  面;策略消费只剩 game state。snapshot_copy 自身语义由迁移哨兵锁另辖。)

