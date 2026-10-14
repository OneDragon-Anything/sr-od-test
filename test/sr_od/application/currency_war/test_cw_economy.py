"""CW 经济域测试(#4):金守恒(单代表)/ budget 拒付(fail-closed 单代表)/
R2 息线 floor / D 牌期望边界 / ev_arm 值域(aggregate_economy 分型登记)/
视界族场字段门面契约(horizon)/ 预算遥测披露(写读闭环/轮界/spent 累计)。

覆盖面(金钱类按 2026-09-09 编排者裁决收缩:实机结算对账 + sim 段检双层
已覆盖逐面金钱锁,单位层只留 commit→sim 空窗价值):
- budget 拒付(1 代表,归 fail-closed):hp 不可信帧 blood_xp_gate 拒;
- R2 息线 floor:cap 语境参数化锁(ADR-0598 注入面);
- D 牌期望边界:expected_refreshes/refresh_prob 边界一条(p≤0/j≥k/
  查表缺级 → 0;v/a 参数从注册表单一源现算,不手抄常数);
- ev_arm 值域:aggregate_economy 分型登记表逐字段算子期望(值域表)。

退役面(审计判决删除):金净守恒代表锁(test_gold_net_conserved_buy_sell_
roundtrip,连 simulate import——锁的 simulate 全仓零生产消费,金钱面
= 实机结算对账 + gain_chain 活转移函数直锁(test_cw_gain_chain))、利息/streak 真值
(src 零调用)、区分力非零证明锚(元测试)、refresh_prob 查表
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

from pathlib import Path
from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bsb,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_comp as _comp,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_decide as _decide,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_members as _members,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session as _session,
)

from one_dragon.base.geometry.point import Point
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
    HP_SAFE_THRESHOLD,
    blood_xp_gate,
    blood_xp_gate_for,
    effective_hp_threshold,
    refresh_ev_budget,
    reserve_cap,
    schedule_upgrade,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    reserve_cap as kernel_reserve_cap,
)
from sr_od.application.currency_war.kernel.cw_first_passage import (
    board_tier_of,
    plane_hp_ratio,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    GameState,
    NodeKey,
    Unit,
    game_state_of,
    gold_of,
    level_of,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    pair_target_comp,
    total_remaining_nodes,
    update_p1_recipe,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    EconomyEffect,
    aggregate_economy,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    P1_NODE_SEQUENCE,
    P2_NODE_SEQUENCE,
    resolve_plane_node_seqs,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    strategy_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    CwAction,
    CwActionBuyCardParam,
    CwActionRefreshShopParam,
    ShopCard,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_shop import (
    accrue_release_spent,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.economy_cycle import (
    disclose_budget,
    disclose_budget_at_shop_frame,
    obligation,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.horizon import (
    r_global,
    r_remaining,
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
#  结算对账 + test_cw_gain_chain 卖/换上报 v2 族契约节(活转移函数直锁)。)


# ==================== R2 息线 floor(cap 语境参数化) ====================
# 测试基建(六件套单一源 = _cw_helpers;本文件 _state 为垫卡 shop
# 帧专属形状,留本地自持)


def _state(sess, gold: int, level: int = 3) -> None:
    """R2 决策种子(垫卡店帧:牌位越界丢卡 = 在屏空牌面)。"""
    cw4_gs(sess, gold=gold, level=level,
           shop=[_card('垫', cost=3, x=100)])


class TestR2InterestFloor:

    def _frame(self, gold: int):
        """R1 可负担性过账种子(ADR-0516 形式二;旧 V_GAP 注入开闸语义随
        V̄ 链退役):lv6、合格集收缩到单目标成员(其余线成员 2★ 成型
        出域)、目标 j=2 差 1 张(账 ≈19 金)⇒ 金 ≥80 时 R1 必过,
        R2 成唯一门。视界 = 场字段默认表(P1=9/P2=7,None 未注册回退;
        plane_lengths_seen 写入 = 簿记位,不入决策)。
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
        bench = [_bc(target), _bc(target)] \
            + [_bc(m, star=2) for i, m in enumerate(others)]
        sess = _session(comp)
        from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
        game_state_of(sess).node_books.plane_lengths_seen = [9, 5, 7]   # 簿记位(视界真值 = 场字段,不入决策)
        cw4_gs(sess, gold=gold, level=6, bench=bench)
        return comp, sess

    def test_cap_resolved_parameterizes_floor(self):
        """cap 语境锁(息线表锚):g*=10×cap_resolved 随 session 覆写参数
        化——cap=10(息律投资语境)下金 80 < 100+ρ ⇒ 拒(50 非域常数,
        息线 floor「拍常数」禁案的判别锁)。
        (金钱类收缩:floor 门过下界/贴线拒刷两行按裁决不搬,git 可复活。)"""
        comp, sess = self._frame(80)
        _seed_actives(sess, ['利息上调'])   # ADR-0598 注入面迁移(容器单源)
        acts = _decide(sess)
        assert not [a for a in acts if isinstance(a, CwActionRefreshShopParam)]


# ==================== budget 拒付单代表(归 fail-closed;自 test_cw_blood_xp_gate 并入) ====================
# (金钱类收缩:T6 阈值边界逐点红证按裁决不搬,git 可复活。)


def _seed_actives(sess, names: list[str]) -> None:
    """持卡播种(终态契约 §B:单一源 = 容器,write_logic 直写)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        game_state_of,
    )
    game_state_of(sess).write_logic(
        game_state_of(sess).active_strategies, list(names),
        produced_by='test',
        sig=ChannelSig(family='logic_action', actor='CwLoop',
                       screen='', mode='compute'))


def _blood_session(active: list[str] | None = None, **state_kw) -> SimpleNamespace:
    """血闸消费面依赖桩(容器单源播种;其余无关)。"""
    s = SimpleNamespace()
    _seed_actives(s, list(active or ['奋斗协议']))
    return s


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
    """费用轴最小决策种子(经济读口已切容器:桥装为测试迁移单一源形态)。
    strategies=已持投资策略;display=OCR 显示价,None=未读到走兜底支
    ——两支来源凭容器 level_up_cost Field 判别。"""
    return _bsb(gold=30, level=level, round_num=2,
                active_strategies=list(strategies or []),
                level_up_cost=display)


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


def _ba_state(*, gold: int = 100, plane: int = 1, round_num: int = 5,
              level: int = 6, hp: int = 80,
              bench: list | None = None,
              shop: list[ShopCard] | None = None,
              board: dict | None = None,
              front_row: list[Unit] | None = None,
              back_row: list[Unit] | None = None,
              active_strategies: list[str] | None = None) -> dict:
    """排程/预算核场景种子轴(容器域直写;返回 = ``_bsb`` kwargs,
    每次调用点装箱出新容器,与旧「帧→桥」逐次新容器语义同构)。"""
    axes: dict = {'plane': plane, 'round_num': round_num, 'gold': gold,
                  'level': level, 'hp': hp, 'shop_refresh_cost': 2,
                  'node': 'battle'}
    if bench is not None:
        axes['bench'] = bench
    if shop is not None:
        axes['shop'] = shop
    if board:
        axes['board'] = board
    if front_row:
        axes['front_row'] = front_row
    if back_row:
        axes['back_row'] = back_row
    if active_strategies:
        axes['active_strategies'] = active_strategies
    return axes


def _sc(name: str, cost: int = 2) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


# (D0 局23 帧哨兵/供给边界两测已随 DP 姿态核/泄息指令死链删除——
#  统一迁移批 ② MAP B 类;build_round_posture/evaluate_release 随 v2 消亡。)


# --- 排程核规则锁(W615 R4;触发①②真值表并一)-----------------------


def _schedule_rows() -> dict:
    """排程触发①②表行构造器(种子轴构造延迟调用,保各触发前置差异;
    断言腿逐条 = 原 test_schedule_pop_slot_trigger /
    test_schedule_probability_trigger_requires_engine)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        max_units_of,
    )

    def _formed_bench() -> list:
        # 2★ 成型件九连(注册表前排角色名;阵营经注册表派生,名字表达纪律)
        return [_bc('阿格莱雅', star=2)
                for i in range(BENCH_CAPACITY)]

    def pop_not_full():
        # ①负腿:bench 满 2★ 成型件 ∧ 未部署(有空位)→ 人口位不触发
        #(gold 30<息线:禁升②不触发——双负前置种子)
        st = _ba_state(gold=30, level=6, round_num=9, bench=_formed_bench())
        assert not st.get('front_row') and not st.get('back_row')   # 有空位
        return st, _ba_sess_of(st)

    def pop_cap_full():
        # ①正腿:cap 满(上场 6 人 = lv6 席位上限,前排 4 + 后排 2)
        #→ 人口位触发(最高义务);'杂{i}' = 注册表外名(未知阵营占位)
        front = [Unit(char_id=f'杂{i}', star=1) for i in range(4)]
        back = [Unit(char_id=f'杂{i}', star=1) for i in range(4, 6)]
        st = _ba_state(gold=30, level=6, round_num=9, bench=_formed_bench(),
                       front_row=front, back_row=back)
        assert len(front) + len(back) >= max_units_of(_bsb(**st))
        return st, _ba_sess_of(st)

    def prob_engine_live():
        # ②臂退役后的排程面(迭代 2026-10-12-prep-shop-workflow-
        # redesign 批 3.4;line_and_upgrade §2.3 升级②臂行):概率改善
        # 排程语义已迁策略层概率主账(criteria/levelup.prob_account_ok,
        # 锁定后 ∧ plane2_started 双条件),本函数人口位单臂——此类帧
        # (息引擎已立 + 峰值在前 + 金 60)不再排程
        return _ba_state(gold=60, level=7), _ba_locked_4cost_sess()

    def prob_engine_missing():
        # ②退役帧对照:金 49<息线(旧②负腿形态)——同样不排程
        return _ba_state(gold=49, level=7), _ba_locked_4cost_sess()

    def prob_peak_reached():
        # ②退役帧对照:峰值已达——不排程
        return _ba_state(gold=60, level=9), _ba_locked_4cost_sess()

    return {
        'pop-slot-bench-formed-not-full': (pop_not_full, False),
        'pop-slot-cap-full': (pop_cap_full, True),
        'probability-engine-live-peak-ahead': (prob_engine_live, False),
        'probability-engine-missing': (prob_engine_missing, False),
        'probability-peak-reached': (prob_peak_reached, False),
    }


def _ba_sess_of(state: dict) -> StrategySession:
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
    """排程触发真值表一锁(参数化并一;迭代 2026-10-12-prep-shop-
    workflow-redesign 批 3.4 后 = 人口位单臂):
    ①人口位[33]:cap 满 ∧ bench 有成型件(2★)→ 排程(最高义务,不受
    可负担前置辖——当轮兑现战力);
    ②概率级已随升级判据重轴退役(「概率改善才升」语义迁策略层概率
    主账,criteria/levelup.prob_account_ok——锁定后 ∧ plane2_started
    双条件消费,line_and_upgrade §2.3 升级②臂行):旧②三形态帧
    (引擎已立/未立/峰值已达)在本函数一律不排程。"""
    build, expect_scheduled = _schedule_rows()[case_id]
    st, sess = build()
    got = schedule_upgrade(_bsb(**st), sess)
    if expect_scheduled:
        assert got, f'{case_id}: 应排程'
    else:
        assert not got, f'{case_id}: 不应排程'


# (U_L 阈值检验负向锁 test_schedule_ul_threshold_negative_small_shift_band
#  已随 schedule_upgrade ②臂退役消亡——迭代 2026-10-12-prep-shop-
#  workflow-redesign 批 3.4:检验函数 _upgrade_ul_threshold_ok 随②臂
#  删除,「小移位带过度升级」的防线由策略层概率主账
#  criteria/levelup.prob_account_ok 承载〔同一不等式形态,辖域改锁定后
#  ∧ plane2_started 双条件,负向锁 = test_cw_levelup_prob_axis 的
#  概率账不触发形态〕;替代语义考古走 git 历史。)


def test_schedule_predictive_even_when_fee_unaffordable() -> None:
    """预告态契约(W623 D1,判前锁):排程不以当帧可负担为前置——
    人口位触发帧(cap 满 ∧ bench 2★ 成型件)gold 30(远不够升级费)
    → 排程照发、R* 计入升级费;「付得起才排」会造 R* 塌缩 → 义务
    花光 → 更排不上的贫穷循环。(重锚申报:原用概率级②帧承载,
    ②臂随升级判据重轴退役〔迭代 2026-10-12-prep-shop-workflow-
    redesign 批 3.4〕后改人口位帧,契约语义不变。)"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        max_units_of,
    )
    front = [Unit(char_id=f'杂{i}', star=1) for i in range(4)]
    back = [Unit(char_id=f'杂{i}', star=1) for i in range(4, 6)]
    bench = [_bc('阿格莱雅', star=2) for i in range(BENCH_CAPACITY)]
    st = _ba_state(gold=30, level=6, round_num=5, bench=bench,
                   front_row=front, back_row=back)
    assert len(front) + len(back) >= max_units_of(_bsb(**st))
    assert schedule_upgrade(_bsb(**st), StrategySession())
    assert reserve_cap(_bsb(**st), StrategySession()) > 50


def test_schedule_gold_digger_retires_levelup(monkeypatch) -> None:
    """淘金客姿态:升级通道退役(W621:CwActionLevelUpParam 退役是刷驱姿态主驱动;
    谓词单一址=cw_investments.refresh_invest_active,授权链同址关闭)。
    (重锚申报:原前置用概率级②帧,②臂随升级判据重轴退役〔迭代
    2026-10-12-prep-shop-workflow-redesign 批 3.4〕后改人口位帧,
    淘金客停机语义不变。)"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        max_units_of,
    )
    front = [Unit(char_id=f'杂{i}', star=1) for i in range(4)]
    back = [Unit(char_id=f'杂{i}', star=1) for i in range(4, 6)]
    bench = [_bc('阿格莱雅', star=2) for i in range(BENCH_CAPACITY)]
    st = _ba_state(gold=100, level=6, round_num=5, bench=bench,
                   front_row=front, back_row=back)
    assert len(front) + len(back) >= max_units_of(_bsb(**st))
    assert schedule_upgrade(_bsb(**st), StrategySession())   # 前置:常态帧排程成立
    monkeypatch.setattr(
        'sr_od.application.currency_war.kernel.cw_investments.STRATEGY_ECONOMY',
        {'淘金客': EconomyEffect(xp_per_refresh=2)})
    st['active_strategies'] = ['淘金客']   # 持卡后:升级通道退役,不排程
    assert not schedule_upgrade(_bsb(**st), StrategySession())


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
    got = refresh_ev_budget(_bsb(**st), sess)
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
    st = _ba_state(round_num=5, gold=100,
                shop=[_sc('卡芙卡', 4)], board={})   # 卡芙卡=DOT 系成员
    update_p1_recipe(_bsb(**st), ist, sess)
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
    保形。(②臂随升级判据重轴退役〔批 3.4〕后,排程面的链动腿消亡,
    预算面的链动腿保形承载本锁。)"""
    import dataclasses
    reg2 = dataclasses.replace(_REG, interest_cap=4)
    st1 = _ba_state(gold=45, level=7)
    sess = _ba_locked_4cost_sess()
    # 排程面:②臂已随升级判据重轴退役(批 3.4),本帧(无人口位触发)
    # 两 registry 下同 False——registry 旋钮不动排程的判别结构保形;
    # 概率改善排程的 resolved 链语义已迁策略层概率主账
    assert not schedule_upgrade(_bsb(**st1), sess, _REG)
    assert not schedule_upgrade(_bsb(**st1), sess, reg2)   # registry 旋钮不动 resolved 链
    sess_ov = _ba_locked_4cost_sess()
    _seed_actives(sess_ov, ['买断制'])   # 注册表可达覆写 cap=0 → 息线 0
    assert not schedule_upgrade(_bsb(**st1), sess_ov)   # ②退役:买断制帧同不排程
    assert refresh_ev_budget(_bsb(**st1), sess, reg2) == \
        refresh_ev_budget(_bsb(**st1), sess, _REG)   # registry 旋钮对预算逐位惰性(ADR-0598 归一)
    # 预算面同链:R* 守息线分量随 resolved cap 动(买断制 floor=0
    # < 默认 50),registry 旋钮不动;②臂退役后无排程帧 R* = 守息线
    # 单分量:gold 45 ≤ 默认 50 → 零预算;买断制 0 → 正预算
    st2 = _ba_state(gold=45, level=7)
    assert reserve_cap(_bsb(**st2), sess_ov) < reserve_cap(
        _bsb(**st2), sess)
    assert refresh_ev_budget(_bsb(**st2), sess, _REG) == 0
    assert refresh_ev_budget(_bsb(**st2), sess_ov) > 0
    # 披露面装配单源(W636 A 载体 = 披露函数):注入 reg2 披露后,披露
    # 字段 == 逐字段显式注入值(现算与披露写入合一 =
    # economy_cycle.disclose_budget;局内事实先经种子写容器 = 生产同路;
    # 装配轴 = 桥配方轴集剥 D 类域(shop_refresh_cost 属桥补写域,feed
    # 配方域覆盖集不含))
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
        gold_of,
    )
    _feed_axes = {k: v for k, v in st2.items()
                  if k != 'shop_refresh_cost'}
    cw4_gs(sess_ov, shop_screen='on', **_feed_axes)
    from sr_od.application.currency_war.strategies.impl.mandate_v1.economy_cycle import (
        disclose_budget,
        obligation,
    )
    disclose_budget(game_state_of(sess_ov), sess_ov, reg2)
    st_ov = state_of(sess_ov)
    assert st_ov.v3_reserve_cap == reserve_cap(_bsb(**st2), sess_ov)
    assert st_ov.v3_reserve_overflow == max(
        0, gold_of(game_state_of(sess_ov)) - st_ov.v3_reserve_cap)
    assert st_ov.v3_release_budget == obligation(_bsb(**st2), sess_ov, reg2)
    assert st_ov.v3_disclosure_key == (st2['plane'], st2['round_num'])
    # registry 旋钮(非注册表可达值 cap=4)对披露预算面逐位惰性:非买断
    # session 同帧披露,储备线 = 默认息线链(旋钮不动预算面)
    cw4_gs(sess, shop_screen='on', **_feed_axes)
    disclose_budget(game_state_of(sess), sess, reg2)
    st_base = state_of(sess)
    assert st_base.v3_reserve_cap == reserve_cap(_bsb(**st2), sess)


# (原 test_tracking_view_isolated_from_session_writers 随修正裁定
#  删除:锁主对象 _tracking_view(tracking 优先 + snapshot 静默回退)已按
#  裁定退役——滞回职责被对账仲裁批 kernel 锚定取代,回退路径即要消灭的掩盖
#  面;策略消费只剩 game state。)


# ===== effective_cost(银狼升星记账批:当前费用档唯一读口)=====


def test_effective_cost_tier_and_registry_routing():
    """当前费用档读口三形态:LV.999 档透传(未观察归约 3)/其余角色注册表
    值/未注册名 0(与 bench_char_cost 未知→3 退款保守估分野)。锁设计
    。"""
    from dataclasses import replace

    from sr_od.application.currency_war.kernel.cw_economy import effective_cost
    from sr_od.application.currency_war.kernel.cw_game_state import (
        GAME_STATE_SCHEMA_VERSION,
        Field,
        GameState,
    )

    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert gs.lv999_cost_tier.value is None
    # 未观察 = 未触发任何变换 → 开局档 3(读口 None 归约)
    assert effective_cost(gs, '银狼LV.999') == 3
    # 升费腿/上阵变费腿写档后透传(值域 {3,4,5};Field frozen,写 = 换帧,
    # 测试以 replace 构造等价帧)
    gs = replace(gs, lv999_cost_tier=Field(value=4, source='logic'))
    assert effective_cost(gs, '银狼LV.999') == 4
    gs = replace(gs, lv999_cost_tier=Field(value=5, source='logic'))
    assert effective_cost(gs, '银狼LV.999') == 5
    # 其余角色 = 注册表静态起始费(档字段不影响非 LV.999 路由)
    assert effective_cost(gs, '希儿') == CHARACTERS['希儿'].cost
    # 未注册名 → 0(无费用语义;与 bench_char_cost 未知→3 分野锁)
    assert effective_cost(gs, '不存在角色') == 0


# ==================== 视界族场字段门面(horizon)=====================
# 锁面地图(判据 = 迭代 abolish-node-ordinal details/horizon-cleanup.md
# §3 门面契约 / §6 boss kind 化 / §8 行为变化申报):
# 门面默认表逐值对拍 / 修饰表封顶 / None 回退 / 位面 ∉ 键集 → 0 /
# hp_safe 阈 nodes_left 封顶 / total_remaining_nodes 与门面同值。
# (boss 计数 kind 化的通道级判别锁 = 本文件外
# test_cw_invest_strategy::test_cash_boss_channel_kind_count /
# test_cash_boss_channel_kind_not_geometry,申报面不再重复。)

_HZ_MODIFIED = resolve_plane_node_seqs('人身意外险')

_HZ_SIG_OBS = ChannelSig(family='obs', actor='TestHorizonRebase', mode='read')
_HZ_SIG_LOGIC = ChannelSig(family='logic_action', actor='TestHorizonRebase',
                           mode='compute')


def _hz_gs_at(plane: int, round_num: int,
              node_seqs: dict[int, tuple[str, ...]] | None = None) -> GameState:
    """帧构造(可选写节点序列场字段;None = 未注册态,与生产消费读法
    同通道 write_logic)。"""
    gs = game_state_of(SimpleNamespace())
    if node_seqs is not None:
        gs.write_logic(gs.node_seq_by_plane, node_seqs,
                       produced_by='TestHorizonRebase',
                       evidence='node_seq:env', sig=_HZ_SIG_LOGIC)
    gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num, kind=''),
               evidence='test', sig=_HZ_SIG_OBS)
    return gs


def _hz_legacy_r_global(seq_lengths: dict[int, int], plane: int,
                        node_in_plane: int) -> int:
    """退役 kernel r_global 的逐值对拍参照(同真值源长度表入参;
    含当前节点 + 到局终,长度源由调用方给定 = 对拍公平性)。"""
    in_plane = max(0, seq_lengths[plane] - (node_in_plane - 1))
    return in_plane + sum(v for k, v in seq_lengths.items() if k > plane)


def test_facade_default_table_matches_legacy_formula_frame_by_frame():
    """默认表(None 回退)全 modeled 帧逐值对拍:门面场字段求和 =
    退役公式(同真值源),含当前节点、到局终、封顶 modeled planes
    (默认局总视界 16,旧 27 制不再出现)。"""
    lengths = {1: len(P1_NODE_SEQUENCE), 2: len(P2_NODE_SEQUENCE)}
    for plane in (1, 2):
        for rnd in range(1, lengths[plane] + 1):
            gs = _hz_gs_at(plane, rnd)
            expect = _hz_legacy_r_global(lengths, plane, rnd)
            assert r_global(gs, plane, rnd) == expect, (plane, rnd)
            assert r_remaining(gs, plane, rnd) == expect, (plane, rnd)


def test_facade_none_fallback_default_table():
    """None(未注册态)回退默认表:P1R1 = 16(默认表 P1+P2,零 P3
    虚拟);P2R1 = 7(旧 schedule_of 先验回退给 9 → 7,details §8.5
    真值修正方向)。"""
    gs = _hz_gs_at(1, 1)
    assert r_global(gs, 1, 1) == 16
    assert r_global(gs, 2, 1) == 7


def test_facade_modified_table_unclamped_truth():
    """修饰表(P1=10/P2=8)封顶对拍:[1,9] 夹取不存在的真值——
    (1,10) 在位面内仍余 1(旧夹取归 0,details §8.1 少 1 偏差消除);
    (1,9) 余 2;(1,1) = 10+8 = 18(details §8.2 修饰局总视界);
    位面末 (2,8) = 1。"""
    assert r_global(_hz_gs_at(1, 1, _HZ_MODIFIED), 1, 1) == 18
    assert r_global(_hz_gs_at(1, 9, _HZ_MODIFIED), 1, 9) == 10
    assert r_global(_hz_gs_at(1, 10, _HZ_MODIFIED), 1, 10) == 9
    assert r_global(_hz_gs_at(2, 8, _HZ_MODIFIED), 2, 8) == 1


def test_facade_plane_outside_key_set_returns_zero():
    """位面 ∉ 序列表键集(含 P3)契约 = 返回 0(details §3:局终后无
    剩余轮;禁 KeyError/异常形态;P3 = 建模域外 = 运行终局)。"""
    for seqs in (None, _HZ_MODIFIED):
        gs = _hz_gs_at(3, 1, seqs)
        assert r_global(gs, 3, 1) == 0
        assert r_remaining(gs, 3, 7) == 0


def test_hp_safe_nodes_left_capped_at_modeled_planes():
    """hp_safe 阈对拍:默认局 P2R1 nodes_left 27 制闭式 18 → 场字段
    modeled 总长 7(期望值用生产 plane_hp_ratio 按 7 重算,单测对象 =
    nodes_left 接线,非生存模型;帧取 lv7 = 板强档 2——该档 7/18 节点
    两口径比值分叉 1.75 vs 1.851,接线错接旧闭式即红);P1 分支同式
    不变(直接返 base);P3 帧(位面 ∉ 键集 → 0)→ 零未来掉血节点 →
    阈回落 base。"""
    p2r1 = _hz_gs_at(2, 1)
    p2r1.observe(p2r1.level, 7, evidence='test', sig=_HZ_SIG_OBS)
    tier = board_tier_of(level_of(p2r1))
    assert tier == 2, '前置:该档下 nodes_left 两口径可判别'
    assert plane_hp_ratio(tier, 7, plane=2) != plane_hp_ratio(tier, 18, plane=2)
    expect = min(100, int(HP_SAFE_THRESHOLD * plane_hp_ratio(tier, 7, plane=2)))
    assert effective_hp_threshold(p2r1) == expect
    # P1 分支:plane <= 1 直接返 base(difficulty 缺省 → HP_SAFE_THRESHOLD)
    assert effective_hp_threshold(_hz_gs_at(1, 5)) == HP_SAFE_THRESHOLD
    # P3 帧:nodes_left = 0 → ratio 1.0 → base
    assert effective_hp_threshold(_hz_gs_at(3, 1)) == HP_SAFE_THRESHOLD


def test_total_remaining_nodes_matches_facade_in_modeled_planes():
    """修正后默认局 P1/P2 段与门面同值(逐帧);P3 段不再虚构(旧 27
    制闭式在 P3 仍给正余量,新 = 0)。"""
    lengths = {1: len(P1_NODE_SEQUENCE), 2: len(P2_NODE_SEQUENCE)}
    for plane in (1, 2):
        for rnd in range(1, lengths[plane] + 1):
            gs = _hz_gs_at(plane, rnd)
            assert total_remaining_nodes(gs) == r_global(gs, plane, rnd), \
                (plane, rnd)
    assert total_remaining_nodes(_hz_gs_at(3, 1)) == 0


# ==================== 预算遥测披露(决策环数据流断链修复 · 缺陷②回归)=====
# 病理(ADR-0571):v3_reserve_cap / v3_reserve_overflow /
# v3_release_budget / v3_release_spent 全库零写点,预算现算每帧算完即丢。
# 修复 = 写点 + 键戳轮界(备战决策入口 + 店开观察帧双写)。

class _StubMatch:
    """match 替身(执行回执位只消费 .session)。"""

    def __init__(self, session: StrategySession) -> None:
        self.session = session


def _disclose_cur(sess: StrategySession, plane: int, round_num: int,
                  gold: int = 53, node_type: str | None = None) -> None:
    """容器域种子(node_type = 节点轴;决策面直读容器)。"""
    cw4_gs(sess, gold=gold, level=5, plane=plane, round_num=round_num,
           hp=100, node=node_type)


def _run_shop_visit_offline_host(monkeypatch: pytest.MonkeyPatch,
                                 tmp_path: Path, disclose_impl) -> tuple[
        list, object, object]:
    """锁 F 行为腿共用离线宿主(零真实副作用)。替身面 = 观察节点段顶
    消费面(读屏/帧留证/种子读链/决策源/遥测单例全替身)+ 关店执行位
    点击桩化:决策源首动作即 CwActionCloseShopParam 终结,循环只走入口
    观察段一次后经统一执行路径关店收工;入口读屏回执 gold=10 非零
    (跳过 gold 救援重读支);种子段读链桩 = 分型的「屏幕席真空」合法态
    (生产 SIFT 读链离线不可用,空账重建出口按合法态零写零台账);帧留证
    不落盘。返回 (warned, rr, ledger);rr=None = 正常收工(出参交接契约,
    详设 §2.2)。驱动 = 真类实例 + 节点函数直驱(过渡薄壳已随 3.4 退役,
    先例 = test_cw_shop_screen_op)。
    disclose_impl 替换店开帧披露写点(接线点为函数内 lazy import,每次
    调用取模块属性,monkeypatch 即生效)。"""
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_shop as buy_mod
    from sr_od.application.currency_war.kernel.cw_vocab import CwActionCloseShopParam
    from sr_od.application.currency_war.obs.cw_observation import (
        GameStateReadReceipt,
    )
    from sr_od.application.currency_war.operations.cw_op.cw_close_shop_action import (
        CwActionCloseShopOp,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CurrencyWarMatch,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        economy_cycle as economy_cycle_mod,
    )
    from sr_od.application.currency_war.telemetry import recorder as rec_mod
    from sr_od.application.currency_war.telemetry import state as tel_state

    # 遥测单例隔离(run 态簇 + 缺陷台账去重键;缺陷台账行落 tmp_path)。
    monkeypatch.setattr(tel_state, '_RECORDER',
                        rec_mod.TelemetryRecorder(enabled=True,
                                                  replay_dir=tmp_path))
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 't1host')
    monkeypatch.setattr(tel_state, '_defect_seen', {})
    monkeypatch.setattr(tel_state, '_defect_seen_run', '')

    class _CloseShopStrategy:
        """替身决策源:首动作即 CwActionCloseShopParam 终结(段顶接线段后立即收工)。"""

        def decide_shop_action(self) -> CwActionCloseShopParam:
            return CwActionCloseShopParam()

    match = CurrencyWarMatch(_CloseShopStrategy(), StrategySession())

    class _Ctl:
        """op 框架经 ctx.controller 触达的最小替身(截图/光标停车)。"""

        def screenshot(self, *a, **k):
            return (0.0, b'')

        def park_cursor(self, *a, **k) -> None:
            pass

    class _Op:
        """离线宿主替身:观察节点消费面仅 ctx(controller 截图/停车)。"""

        ctx = SimpleNamespace(current_instance_idx=1, cw_match=match,
                              controller=_Ctl())

    def _entry_receipt(*a, **k) -> GameStateReadReceipt:
        """段顶入口观察回执(gold=10 非零,跳过 gold 救援重读支)。"""
        return GameStateReadReceipt(gold=10, gold_readable=True, hp=100,
                                    hp_readable=True, hp_trusted=True,
                                    level=5, plane=1, round_num=8)

    # 关店执行位点击桩化(统一执行路径含 CloseShop 真点击;离线零画面):
    # 「收起」命中 → 点击臂(动画等待经全局 time 桩跳过)。
    monkeypatch.setattr(CwActionCloseShopOp, 'screenshot', lambda self: None)
    monkeypatch.setattr(CwActionCloseShopOp, 'round_by_find_and_click_area',
                        lambda self, *a, **k: SimpleNamespace(is_success=True))
    monkeypatch.setattr('time.sleep', lambda _s: None)
    monkeypatch.setattr(buy_mod, 'read_game_state', _entry_receipt)
    monkeypatch.setattr(buy_mod, 'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(buy_mod, 'shop_card_click_points',
                        lambda ctx: [Point(50, 50)] * 5)   # 定长 5 槽(段首全 5 槽门)
    monkeypatch.setattr(buy_mod, 'area_center', lambda *a, **k: (0, 0))
    monkeypatch.setattr(buy_mod.time, 'sleep', lambda s: None)
    monkeypatch.setattr(buy_mod, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                                    ev_arm=''))
    monkeypatch.setattr(economy_cycle_mod, 'disclose_budget_at_shop_frame',
                        disclose_impl)
    warned: list = []
    monkeypatch.setattr(buy_mod.log, 'warning',
                        lambda *a, **k: warned.append(a))
    from one_dragon.base.operation.operation_round_result import (
        OperationRoundResultEnum,
    )
    shell = buy_mod.CwScreenShop(_Op.ctx)
    rr = shell.observe()
    if not rr.is_success:
        return warned, rr, None
    while True:
        rr = shell.act()
        if rr.result == OperationRoundResultEnum.SUCCESS:
            return warned, None, shell.ledger
        if rr.result == OperationRoundResultEnum.WAIT:
            continue
        return warned, rr, None


class TestBudgetDisclosureWriteRead:

    def test_state_fields_equal_same_frame_computed_values(self):
        """披露后状态四字段 == 同帧独立现算值(R*/溢余/义务)。红证 =
        现码恒 0(52 行全零实证);本腿断的是「值对」,非「非零」。
        W6 波 4:预算接缝读 session 容器单例,种子先于披露(生产同路 =
        观察漏斗,测试同路 = cw4_gs 容器域种子)。"""
        sess = StrategySession()
        # 构造金 120:开局种子底座后备战帧息帽含排程升级费(种子域喂入
        # reserve_cap 现算),取高金保「溢余/义务非退化」判据有效。
        _disclose_cur(sess, 1, 8, 120, node_type='prep')
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        # 独立现算 oracle:同输入现算确定 ⇒ 与披露写点内部同值(非转抄
        # 披露字段);重算输入 = 同一容器实例(键戳/轮轴的单一来源)。
        state = game_state_of(sess)
        expected_cap = kernel_reserve_cap(state, sess)
        assert st.v3_reserve_cap == expected_cap
        assert st.v3_reserve_overflow == max(
            0, int(gold_of(state) or 0) - expected_cap)
        assert st.v3_release_budget == obligation(state, sess,
                                                  DEFAULT_REGISTRY)
        assert st.v3_disclosure_key == (1, 8)
        # 构造帧结构性非退化(gold 高于息线 ⇒ 溢余/义务应非零;恒 0 =
        # 写点断裂的病理签名回归)
        assert st.v3_reserve_overflow > 0
        assert st.v3_release_budget > 0


class TestShopOpenFrameDualWrite:

    def test_prep_frame_without_gold_keeps_zero_semantics(self):
        """prep 关店帧 ⇒ overflow/budget 恒 0 =「金未采」已知语义(非
        真 0;实机首局 g_20260907_025608 锚⑤定谳),reserve_cap 不受
        影响(gold 无关)——关店 0 语义由容器金缺席承载(F2 门:gold
        仅店开态可信,关店读空不写容器)。"""
        sess = StrategySession()
        cw4_gs(sess, gold_unread=True, level=5, plane=1, round_num=8,
               hp=100, node='prep')
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        assert st.v3_reserve_cap == kernel_reserve_cap(
            game_state_of(sess), sess)
        assert st.v3_reserve_overflow == 0
        assert st.v3_release_budget == 0

    def test_shop_open_frame_overwrites_with_frame_values(self):
        """店开观察帧覆写:overflow/budget 变帧现值(gold 120 > 息帽 ⇒
        溢余/义务 >0;开局种子底座后备战帧息帽含排程升级费,构造金取高
        保非退化);同轮重复覆写不清 spent(轮界清零归 prep 键戳
        独占);下轮 prep 关店帧 ⇒ 披露 = 容器现值重算(W6 波 4 语义
        变更;键戳翻轮清零断言面 = 锁 D 主锁,此处不重复)。"""
        sess = StrategySession()
        # ① prep 关店帧(轮入口披露;种子金(基线 3)低于息帽,溢余 0——
        # 「金未采/金低」两形态在披露面同值,语义注释见锁 F 首案)
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        assert st.v3_reserve_overflow == 0
        # ② 店开帧覆写(帧现值):金源切容器(W6 波 4),店开帧经种子写
        # 容器(生产同路 = 观察漏斗;测试同路 = cw4_gs 容器域种子),披露读
        # 容器现值
        cw4_gs(sess, gold=120, level=5, plane=1, round_num=8, hp=100,
               node='prep')
        disclose_budget_at_shop_frame(game_state_of(sess), sess)
        assert st.v3_reserve_overflow == 120 - st.v3_reserve_cap
        assert st.v3_reserve_overflow > 0
        assert st.v3_release_budget > 0
        # ③ 同轮重复覆写不清 spent
        st.v3_release_spent = 4
        disclose_budget_at_shop_frame(game_state_of(sess), sess)
        assert st.v3_release_spent == 4
        # ④ 下轮 prep 关店帧(金失读 → 容器 carry 沿用店开金,funnel 同
        # 口径):披露 = 容器现值重算。「陈旧店开溢余复位 0」旧语义随
        # 金源切容器消亡——失读沿用下披露恒按沿用金重算,不存在复位面;
        # F1 新会话构造测不到「覆写后再披露」面(翻轮清零语义归锁 D)。
        cw4_gs(sess, gold_unread=True, level=5, plane=1, round_num=9,
               hp=100, node='prep')
        disclose_budget(game_state_of(sess), sess)
        assert st.v3_reserve_overflow == 120 - st.v3_reserve_cap
        assert st.v3_reserve_overflow > 0


class TestRoundBoundaryReset:

    def test_new_round_clears_spent_and_reason_and_renews_key(self):
        """同 session 连续两轮(p1r8→p1r9)披露:新轮首帧 spent==0、
        reason==''(F5 裁决①:reason 并入键戳清零块,杜绝跨轮陈读)、
        键戳已翻新。键戳轴 = session 容器(W6 波 4),每轮披露前喂入。"""
        sess = StrategySession()
        _disclose_cur(sess, 1, 8, 53, node_type='prep')
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        st.v3_release_spent = 7
        st.v3_release_reason = 'must_spend'
        _disclose_cur(sess, 1, 9, 53, node_type='prep')
        disclose_budget(game_state_of(sess), sess)
        assert st.v3_release_spent == 0
        assert st.v3_release_reason == ''
        assert st.v3_disclosure_key == (1, 9)

    def test_same_round_redisclosure_keeps_accumulation(self):
        """同轮重披露(幂等重入)不清账:键戳同值 ⇒ 只覆写三预算字段,
        spent 存活期 = 本轮披露后至下一轮键戳变更(与「轮内截至采样时点
        累计」语义一致)。键戳轴 = session 容器(W6 波 4),披露前喂入。"""
        sess = StrategySession()
        _disclose_cur(sess, 1, 8, 53, node_type='prep')
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        accrue_release_spent(_StubMatch(sess), CwActionRefreshShopParam(cost=2), True)
        _disclose_cur(sess, 1, 8, 51, node_type='prep')
        disclose_budget(game_state_of(sess), sess)   # 同轮重入(刷新后金位变化)
        assert st.v3_release_spent == 2
        assert st.v3_disclosure_key == (1, 8)


class TestReleaseSpentAccrual:

    def test_two_refreshes_accumulate_per_receipt(self):
        """执行一次 CwActionRefreshShopParam(cost=2) ⇒ spent==2;同 visit
        第二笔 ⇒ 4(执行回执位逐笔累计)。键戳轴 = session 容器(W6 波 4),
        披露前喂入使键戳成文。"""
        sess = StrategySession()
        _disclose_cur(sess, 1, 8, 53, node_type='prep')
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        m = _StubMatch(sess)
        accrue_release_spent(m, CwActionRefreshShopParam(cost=2), True)
        assert st.v3_release_spent == 2
        accrue_release_spent(m, CwActionRefreshShopParam(cost=2), True)
        assert st.v3_release_spent == 4

    def test_failed_execution_not_accrued(self):
        """未落地(_ok=False)不记账——与 apply_action_outcome「两侧都不
        动」同纪律(实花=真执行)。"""
        sess = StrategySession()
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        accrue_release_spent(_StubMatch(sess), CwActionRefreshShopParam(cost=2), False)
        assert st.v3_release_spent == 0

    def test_non_refresh_actions_not_accrued(self):
        """首版口径只计刷新:买牌/升级/关店不进 spent(宁窄勿虚,
        ADR-0571 收窄申报)。"""
        sess = StrategySession()
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        m = _StubMatch(sess)
        accrue_release_spent(m, CwActionBuyCardParam(card=ShopCard(x=1, name='x', cost=3),
                                        reason='t'), True)
        assert st.v3_release_spent == 0

    def test_stale_key_receipt_not_accrued(self):
        """F4 探针①:回执轮次 ≠ 键戳(键戳 r8、回执 r9)⇒ 不累计——
        防「本轮预算披露行混入上轮累计」的键界漂移。轮键现役轴 = 容器
        读口:喂入翻轮即回执轮已翻,键戳仍钉上一轮。"""
        sess = StrategySession()
        _disclose_cur(sess, 1, 8, 53, node_type='prep')
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        _disclose_cur(sess, 1, 9, 53, node_type='prep')
        accrue_release_spent(_StubMatch(sess), CwActionRefreshShopParam(cost=2), True)
        assert st.v3_release_spent == 0

    def test_no_key_stamp_session_not_accrued(self):
        """F4 探针②:非 mandate_v1 栈(裸 session 无键戳)⇒ 不累计——
        防「spent>0 而预算三字段=None」混合行形态(recorder None 语义
        声明;异型策略状态对象经防御 getattr 走缺省)。"""
        sess = StrategySession()
        st = state_of(sess)
        assert st.v3_disclosure_key is None
        accrue_release_spent(_StubMatch(sess), CwActionRefreshShopParam(cost=2), True)
        assert st.v3_release_spent == 0
        assert strategy_state_of(sess) is st


def test_armed_shortcircuit_frame_writes_no_disclosure(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """armed 短路帧不披露单帧锁:预算披露落点 = 备战决策入口前置发射位
    判定之后(非 armed 帧才到达),armed 帧在三遍编排前短路 return ⇒
    披露字段零写。发射准入核桩 = armed 单键替身(真 armed 帧需配方完备
    板面,与本锁无关——锁的是落点位次,非 armed 判据本体);替身返回
    缺 quality/quality_eval_error 键 = 常态发射帧。"""
    import sr_od.application.currency_war.kernel.cw_launch_admission as admit_mod
    import sr_od.application.currency_war.strategies.impl.mandate_v1.bridge as bridge_mod
    from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
        MandateV1Strategy,
    )

    sess = StrategySession()
    _disclose_cur(sess, 1, 8, 53, node_type='prep')
    monkeypatch.setattr(admit_mod, 'readiness_launch_decision',
                        lambda *a, **k: {'armed': True})

    def _no_reach(*a, **k):
        raise AssertionError('armed 帧短路后不得到达三遍编排')

    monkeypatch.setattr(bridge_mod, 'decide_prep_frame', _no_reach)
    action = MandateV1Strategy(
        game_state_of(sess),
        SimpleNamespace(strategy_seed=None)).decide_prep_screen()   # 终态契约:构造注入
    assert isinstance(action, CwAction), 'armed 帧应短路产出发射意图动作'
    st = state_of(sess)
    assert st.v3_disclosure_key is None, 'armed 短路帧不得盖披露键戳'
    assert st.v3_reserve_cap == 0
    assert st.v3_reserve_overflow == 0
    assert st.v3_release_budget == 0


def test_shop_frame_disclosure_wired_at_shop_entry(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """接线存在锁(店开帧第二写点):spy 计数 = 店开观察帧段顶接线段
    恰调用一次(接线断裂/漂移即红)+ 循环收工两腿。"""
    seen_calls: list = []

    def _spy(state, session, registry=None) -> None:
        seen_calls.append(1)

    _warned, rr, ledger = _run_shop_visit_offline_host(monkeypatch, tmp_path,
                                                       _spy)
    assert len(seen_calls) == 1, \
        f'店开帧披露写点调用次数异常({len(seen_calls)}):接线断裂/漂移'
    assert rr is None and ledger is not None, '商店循环未正常收工'


def test_shop_frame_disclosure_failure_degrades_with_warning(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """行为锁:披露覆写失败 → log.warning 降级留痕、不外抛中断商店循环
    (遥测 best-effort 契约;锚⑤缺陷无声复发防线)。触发法 = 披露写点
    monkeypatch 成抛错,经共用离线宿主驱动观察 node 段顶接线段,断言
    warning 被调且循环正常收工——log 措辞/写法漂移不再假红。"""

    def _boom(*a, **k):
        raise RuntimeError('t1 注入:披露覆写失败')

    warned, rr, ledger = _run_shop_visit_offline_host(monkeypatch, tmp_path,
                                                      _boom)
    assert warned, '披露覆写失败未走 log.warning 降级(静默 no-op 回归)'
    assert rr is None and ledger is not None, \
        '降级未收工:披露失败不应中断商店循环'

