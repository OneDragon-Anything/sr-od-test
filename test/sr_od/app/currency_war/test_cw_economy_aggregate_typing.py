"""aggregate_economy 字段聚合分型登记三半边断言(design_economy §E6)。

前置缺陷 R83-1/R85-3(登记表 R83/R85 对照行;规格=IMPL_DESIGN §2.12 前置
缺陷清单)修复的配套防线:五族枚举补全后,「字段在册+字段被枚举+聚合语义
等价」三件事各有独立半边封口,防分型层复发。

分型表(本测试位常量表)= 聚合语义机器可读单一源(§E6 裁决:代码即载体,
禁文档表与测试硬编码双源)。三半边:
①  EconomyEffect 全字段 ⊆ 分型登记(聚合型 ∪ 不进 aggregate 断言型,
    后者各注归位通道)——新增字段未登记即红;
②  聚合型字段 ⊆ aggregate_economy 实现枚举——登记为聚合型而实现未
    枚举 ⇒ 消费链静默丢值,单条目探针即红;
③  实现实际聚合形态 ≡ 登记语义——测试位参考求值器按分型表算子规约
    机械驱动(单一源=分型表,禁手写第二份聚合实现),与实现并行求值
    逐字段比对。

fixture 区分力义务(§E6 伪护栏家族封口):每聚合型字段的最小区分集
见 _DISTINGUISH_FIXTURES;另含「仅隶属断言下恒绿、语义等价断言下红」
的区分力非零证明锚(test_half3_detection_power_proof:篡改分型表算子后,
同 fixture 下求值器与实现必须分歧)。
"""
from dataclasses import fields

import pytest

from sr_od.application.currency_war.kernel import cw_investments as inv
from sr_od.application.currency_war.kernel.cw_investments import (
    EconomyEffect,
    aggregate_economy,
)

# ===== 分型登记表(机器可读单一源;§E6)=====
# field -> 算子规约(算子 + 恒等元/初值 + 过滤谓词)。
# 算子词表(非封闭;实现出现词表外形态=登记缺口,由半边③检出):
#   sum            加法求和(初值 0)
#   max            取宽(初值=字段默认)
#   guarded_min    守卫 min 并宽(哨兵 0:非零成员取 min,全零/空=0)
#   or             等值选择 or(恒等元 0;左折叠取首个非恒等元)
#   prob           概率补集合成 1−∏(1−ci)(初值 0.0)
#   filter_max     过滤谓词 + 后置取宽(过滤入集、循环外 max)
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

# 不进 aggregate 断言型(§E6「不进 aggregate 断言型」:bool/tuple/期权 str/
# 调度族 + 各注归位通道——数值但消费不经聚合链的字段同样在此登记通道)。
AGG_EXCLUDED: dict[str, str] = {
    'difficulty_delta': '难度账走台账逐策略(36 号账本),不经聚合',
    'difficulty_per_streak': '难度账走台账逐策略,不经聚合',
    'difficulty_node_types': 'tuple 限定族(Δ 限定节点型),调度面归位',
    'future_quality_upgrade': '期权 str,期权侧消费',
    'difficulty_inflation_exempt': 'bool 行为条件流',
    'hp_gold_swap': 'bool 行为条件流(33 号 λ_hp 消费)',
    'gold_per_hp_lost_now': 'bool 行为条件流(选卡时点结算)',
    'xp_instant': 'oneshot:选卡时点单次入账(engine_p1 economy_effect_of 逐卡),禁并入每节点 flow 双计',
    'gold_per_2star2cost_merge': '合成触发族,cw_effect_ledger 逐策略路由',
    'gold_per_3star_merge': '合成触发族,cw_effect_ledger 逐策略路由',
    'refresh_per_compose': '合成触发族,cw_effect_ledger 逐策略路由',
    'sell_price_mult': '出售动作面逐策略消费(乘子族,无聚合通道)',
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


# ===== 半边①:全字段 ⊆ 分型登记(新增字段未登记即红)=====
def test_half1_all_fields_registered() -> None:
    declared = {f.name for f in fields(EconomyEffect)}
    registered = set(AGG_FIELDS) | set(AGG_EXCLUDED)
    assert declared == registered, (
        f'EconomyEffect 字段与分型登记不对账: '
        f'未登记={declared - registered}, 登记多余={registered - declared}')


# ===== 半边②:聚合型字段 ⊆ 实现枚举(单条目探针;静默丢值即红)=====
def test_half2_registered_fields_enumerated(patched_registry) -> None:
    for fname, spec in AGG_FIELDS.items():
        # 单条目非默认探针:实现未枚举该字段 ⇒ 聚合结果停留默认值
        probe = {'interest_cap_override': 7, 'win_reward_mult': 2.0,
                 'refresh_free_chance': 0.45, 'xp_buy_hp_cost': 6,
                 'refresh_surprise_every': 4, 'gold_next_nodes_count': 3}
        if fname not in probe:
            probe = {fname: {'sum': 11, 'max': 3, 'guarded_min': 4,
                             'or': 6, 'prob': 0.4}[spec['op']]}
        names = patched_registry([_mk('探针', **probe)])
        got = getattr(aggregate_economy(names), fname)
        default = getattr(EconomyEffect(), fname)
        assert got != default, (
            f'{fname} 登记为聚合型但 aggregate_economy 未枚举(静默丢值): got={got}')


# ===== 半边③:实现聚合形态 ≡ 登记语义(参考求值器逐字段对拍)=====
def test_half3_reference_evaluator_matches(patched_registry) -> None:
    entries = [
        _mk('甲', instant_gold=5, gold_at_node=70, gold_at_node_offset=5,
            interest_flat_per_node=2, xp_buy_hp_cost=6, gold_next_nodes_count=2,
            refresh_surprise_every=0, win_reward_mult=1.0),
        _mk('乙', instant_gold=7, gold_at_node=30, gold_at_node_offset=3,
            interest_flat_per_node=3, xp_buy_hp_cost=8, gold_next_nodes_count=5,
            refresh_surprise_every=3, interest_cap_override=5,
            win_reward_mult=1.5, refresh_free_chance=0.3),
        _mk('丙', gold_at_level=40, gold_at_level_target=9,
            xp_click_discount_from_level=1, xp_click_discount_from_level_at=8,
            refresh_shop_rewrite_every_3cost=0, gold_per_level_up=2),
        _mk('丁', gold_at_level=25, gold_at_level_target=5,
            xp_click_discount_from_level=2, xp_click_discount_from_level_at=6,
            refresh_shop_rewrite_every_3cost=4, gold_per_level_up=3),
        _mk('无经济'),   # economy=None(战力类)→ 恒等元贡献
    ]
    # effects 与 names 同源(求值器输入=注册表条目的 economy;miss 路径
    # 经未注册名,亦=恒等元)
    effects = [s.economy for _, s in entries if s.economy is not None]
    names = patched_registry(entries, extra_unknown='完全未注册名')
    ref = _reference_aggregate(effects)
    agg = aggregate_economy(names)
    for fname, expect in ref.items():
        got = getattr(agg, fname)
        assert got == expect, (
            f'{fname}: 实现聚合形态与分型登记语义不符 '
            f'(impl={got!r}, reference={expect!r})')


# 区分力 fixture(§E6 义务:每聚合型字段 ≥1 个能区分登记算子与同型
# 备选算子的构造;下表同时是半边③ fixture 的语义来源)。
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
# 必须与实现分歧——证明本断言集在「仅隶属断言(①②)恒绿」的语义错账
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
