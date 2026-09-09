"""CW 经济域测试(#4):金守恒 / budget 门(blood_xp_gate)/ interest+streak
表锚 / ev_arm 值域(aggregate_economy 分型登记)。

覆盖面:
- 金守恒:投资收入入账本(invest 键收入行)+ R2 息线下界(刷新通道
  刷后投影金 ≥ g*+ρ,金钱不蒸发);
- budget 门:blood_xp_gate 纯函数阈值红证 + hp 不可信帧 fail-closed;
- interest+streak 表锚:R2 息线 floor 三分支(门过下界 / 贴线拒刷 /
  cap 参数化表锚)+ economy_score 利息单调 + streak 只计连胜方向
  (ADR-0128 无连败补偿);
- ev_arm 值域:aggregate_economy 分型登记表逐字段算子期望(值域表)
  + 区分力非零证明锚(篡改登记必分歧,非恒绿护栏);
- 过继锁:投资注册表 335/83 计数(原 test_cw_investment 唯一承载,
  终局归编 #15 data_registry,重建期暂挂本文件防断链)。

来源:economy_typing(mv 主干)/ investment / r2_interest_floor /
blood_xp_gate 核 / decisions 之 economy 真值两行(2026-09-09 套件重建批
A,#4)。其余历史锁已退役(git 可复活)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_shop_odds import (
    expected_refreshes_for_card,
)
from sr_od.application.currency_war.kernel import cw_investments as inv
from sr_od.application.currency_war.kernel.cw_economy import (
    blood_xp_full_clicks,
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
    XP_TO_NEXT_LEVEL,
    GameState,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.sim import engine_p1 as cw_sim
from sr_od.application.currency_war.sim.cw_sim_invest import SimInvestProfile
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    _r2_card_reserve,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.interest import (
    saturation_line,
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

_POOL = 'fallback'


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


# ==================== 金守恒:投资收入入账本(自 test_cw_investment 并入) ====================

def test_gold_per_node_and_instant_gold_apply() -> None:
    """定期福利(+4 金选卡 / 每节点 +2):账本收入行出现 invest 键。"""
    prof = SimInvestProfile(picks=((1, 1, '定期福利'),))
    r = cw_sim.simulate_p1(0, pool=_POOL, invest=prof)
    rows = [row for row in r.ledger
            if (row.get('sim') or {}).get('income', {}).get('invest')]
    assert rows, 'gold_per_node 未进账本收入分解'


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

    @staticmethod
    def _floor(comp, level: int, bench: list) -> int:
        """帧内 floor = g*(默认局 cap_resolved=5) + ρ(合格集最低费)。"""
        return saturation_line(5) + _r2_card_reserve(
            tuple(_members(comp)), bench, [], GameState(
                gold=0, level=level, round_num=2))

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

    def test_floor_respected_when_gate_opens(self):
        """floor 结构锁(帧级,P54 §③):门过帧的刷后投影金 ≥ g*+ρ
        ——刷新通道永不掉满息档;本帧金=80(R1 总账 ≈19 ≤ 预算 30)
        ⇒ 发射。"""
        comp, st, sess = self._frame(80)
        acts = _decide(st, sess)
        rs = [a for a in acts if isinstance(a, RefreshShop)]
        assert rs, '门过帧应发射刷新(健康带下界 >0,P54 §④)'
        floor = self._floor(comp, 6, st.bench)
        assert st.gold - rs[0].cost >= floor

    def test_just_below_floor_rejected(self):
        """贴线拒刷(账本级):金 = g*+ρ(P40 刷窗 n_max=0)⇒ r1/r2 关,
        不发射刷新——旧值 b_target(0,0,0)=0 使此帧发射
        (gold≥2 病灶,P53 §④ 申报 1),floor 落码后为判别锁。"""
        comp = _comp()
        gold_at_floor = (saturation_line(5)
                         + _r2_card_reserve(tuple(_members(comp)),
                                            [], [], _state(0)))
        _c, st, sess = self._frame(gold_at_floor)
        acts = _decide(st, sess)
        assert not [a for a in acts if isinstance(a, RefreshShop)]

    def test_cap_resolved_parameterizes_floor(self):
        """cap 语境锁:g*=10×cap_resolved 随 session 覆写参数化——
        cap=10(息律投资语境)下金 80 < 100+ρ ⇒ 拒(50 非域常数,
        dd-026 备选 2「拍常数」禁案的判别锁)。"""
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


# ==================== budget 门:blood_xp_gate 核(自 test_cw_blood_xp_gate 并入) ====================


def _blood_session(active: list[str] | None = None, **state_kw) -> SimpleNamespace:
    """血闸消费面依赖桩:active_strategies + last_state(其余无关)。"""
    return SimpleNamespace(
        active_strategies=list(active or ['奋斗协议']),
        last_state=GameState(**state_kw),
    )


def test_blood_xp_gate_threshold() -> None:
    """T6 阈值边界逐点红证(全量口径帧;ADR-0578):
    lv3(XP_TO_NEXT_LEVEL[3]=4 → 全量 ⌈4/4⌉=1 击)cost=6:hp=6 → True / hp=5 → False;
    lv7(need=52 → 全量 13 击):hp=78 → True(78≥78)/ hp=77 → False。
    红证语义:移除闸 → False 案例放行。"""
    assert XP_TO_NEXT_LEVEL[3] == 4 and XP_TO_NEXT_LEVEL[7] == 52
    assert blood_xp_full_clicks(3) == 1 and blood_xp_full_clicks(7) == 13
    assert blood_xp_gate(6, True, 3, 6) is True    # 6 ≥ 1×6
    assert blood_xp_gate(5, True, 3, 6) is False   # 5 < 6
    assert blood_xp_gate(78, True, 7, 6) is True   # 78 ≥ 13×6
    assert blood_xp_gate(77, True, 7, 6) is False  # 77 < 78


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
