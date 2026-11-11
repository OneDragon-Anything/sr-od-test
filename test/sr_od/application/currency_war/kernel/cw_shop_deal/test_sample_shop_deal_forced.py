"""kernel 强制费用档整店发牌采样器测试(公司严选 301401)。

镜像 src = kernel/cw_shop_deal.py 的 :func:`sample_shop_deal_forced`
(拆目录新文件,超线禁追加;基线采样器测试住同目录上级
test_cw_shop_deal.py,不追加)。

锁面(设计 = 已退役账本
设计稿(原件已退役) §4 锁 1,执行口径按 已退役评审稿(§ 号 = 原稿节序)§3④;过程件
引用寿命 = 迭代,语义以测试本体为准):
1. 种子 rng 全 4 费互异:unique=True 下 5 槽名互异且基准费恒 4;
2. 人才下沉局翻星合成性:2★ 与 1★ 并存,cost ∈ {4,12} 且名恒互异
   (只锁合成性与去重不破,与 p=0.2 占位值解耦);
3. 压桶短缺:4 费桶 drawable <5 → 填尽量多、余槽留 empty(短缺披露
   归调用方,本层只锁槽形);
4. 空桶全 empty:drawable = 0 → 5 槽全 empty、零 rng 消耗面(确定性
   重放 = 同种子两跑逐字节同构)。
压桶手法 = 3★ 备战席单位(held_copies 按 3^(star-1) 计副本,3★ = 9
副本 = 固定牌库 4 费满额 → drawable 过滤条件双杀:remaining=0 ∧
held≥9)。种子不读本机易失产物,断言依据全自造。
"""
from __future__ import annotations

import random

from test.sr_od.application.currency_war._cw_helpers import cw4_bc, cw4_gs

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_pool import drawable_names
from sr_od.application.currency_war.kernel.cw_shop_deal import (
    sample_shop_deal_forced,
)

_SEED = 'cw-shop-forced-deal'
_COST = 4


def cw4_unit3(name: str) -> Unit:
    """3★ 上阵单位(held 副本 9 = 4 费固定满额,压桶排除件)。"""
    return Unit(char_id=name, star=3)


def _four_cost_names() -> list[str]:
    """4 费非专家全名单(注册表派生,禁手抄——新角色入库自动跟随)。"""
    return sorted(n for n, ch in CHARACTERS.items()
                  if ch.cost == _COST and not ch.is_expert)


def _deal_forced(gs, *, unique: bool = True,
                 seed: str = _SEED) -> object:
    rng = random.Random(seed)
    return sample_shop_deal_forced(gs, rng, cost=_COST, unique=unique,
                                   level=3)


def test_unique_deal_five_distinct_four_cost() -> None:
    """锁 1a:种子 rng unique 发牌 → 5 槽全 content、名互异、基准费 4。"""
    gs = cw4_gs(active_env='')
    payload = _deal_forced(gs)
    assert len(payload.cards) == 5
    names = [s.card.name for s in payload.cards]
    assert len(set(names)) == 5, f'同帧去重(「独特」): {names}'
    for slot in payload.cards:
        assert slot.kind == 'content'
        assert slot.card.cost == _COST, f'强制费用档定死: {slot.card.cost}'
        assert slot.card.star == 1, '表外环境恒 1★'
        assert slot.card.cost_source == 'roster', '构造信源不变'


def test_two_star_env_composition_keeps_unique() -> None:
    """锁 1b:人才下沉局翻星合成性(固定种子 100 店):2★ 必现且
    cost = 基准费×3、名恒互异(翻星不改名集语义)。粗带只防参数错接。"""
    two_star_seen = 0
    for _ in range(100):
        gs = cw4_gs(active_env='人才下沉')
        payload = _deal_forced(gs)
        names = [s.card.name for s in payload.cards if s.card is not None]
        assert len(set(names)) == len(names), f'翻星局去重不破: {names}'
        for slot in payload.cards:
            if slot.card.star == 2:
                two_star_seen += 1
                assert slot.card.cost == _COST * 3, \
                    f'2★ 读数 = 基准费×3: {slot.card.cost}'
            else:
                assert slot.card.cost == _COST
    assert two_star_seen > 0, 'p=0.2 × 100 店必现 2★(行为丢失即红)'


def test_squeezed_bucket_fills_what_is_left() -> None:
    """锁 1c:桶 drawable=4(<5)→ 4 content + 1 empty,名互异。"""
    all_names = _four_cost_names()
    assert len(all_names) >= 6, '注册表 4 费非专家名单过短,压桶前提失真'
    squeezed = all_names[:9]      # 9 备战席槽全置 3★(各 9 副本 → 全排除)
    leftover = [n for n in all_names if n not in squeezed]
    assert len(leftover) < 5, f'压桶后 drawable 应 <5: {len(leftover)}'
    gs = cw4_gs(bench=[cw4_bc(n, star=3) for n in squeezed])
    assert len(drawable_names(gs, _COST)) == len(leftover)
    payload = _deal_forced(gs)
    content = [s for s in payload.cards if s.card is not None]
    empty = [s for s in payload.cards if s.card is None]
    assert len(content) == len(leftover), \
        f'填尽量多: {len(content)} != drawable {len(leftover)}'
    assert len(empty) == 5 - len(leftover), '余槽留 empty'
    assert len({s.card.name for s in content}) == len(content), '短缺局去重不破'


def test_empty_bucket_all_slots_empty() -> None:
    """锁 1d:桶 drawable=0 → 5 槽全 empty;同种子重放逐槽同构。"""
    all_names = _four_cost_names()
    # 全名单排除:备战席 9 槽 + 上阵 10 槽(前台 4 + 后台 6)= 19 ≥ 现役
    # 4 费非专家全数(held 副本 9/名 = 固定满额,注册表扩员自动跟随);
    # 上阵行种子 = Unit 直构(deployed 行域吃 Unit,备战席件构造器复用)。
    assert len(all_names) <= 19, '注册表 4 费非专家超排除槽容量,前提失真'
    gs = cw4_gs(bench=[cw4_bc(n, star=3) for n in all_names[:9]],
                front_row=tuple(cw4_unit3(n) for n in all_names[9:13]),
                back_row=tuple(cw4_unit3(n) for n in all_names[13:19]))
    assert drawable_names(gs, _COST) == []
    p1 = _deal_forced(gs, seed=_SEED)
    p2 = _deal_forced(gs, seed=_SEED)
    assert all(s.kind == 'empty' and s.card is None for s in p1.cards), \
        '空桶全 empty'
    assert [(s.kind, s.card) for s in p1.cards] \
        == [(s.kind, s.card) for s in p2.cards], '同种子重放确定'


def test_deterministic_replay_full_bucket() -> None:
    """满桶局同种子重放逐槽同构(两分支种子重放确定——翻星掷点随种子
    重放,非唯一分支)。"""
    gs = cw4_gs(active_env='人才下沉')
    p1 = _deal_forced(gs, seed=_SEED)
    p2 = _deal_forced(gs, seed=_SEED)
    assert [(s.card.name, s.card.cost, s.card.star) for s in p1.cards] \
        == [(s.card.name, s.card.cost, s.card.star) for s in p2.cards]


def test_non_unique_branch_symmetric_fill() -> None:
    """非 unique 分支(预留对称,现役无调用形):5 槽全 content、基准费
    4,不去重语义 = 允许重复(仅锁形不锁重复出现)。"""
    gs = cw4_gs(active_env='')
    payload = _deal_forced(gs, unique=False)
    assert len(payload.cards) == 5
    for slot in payload.cards:
        assert slot.kind == 'content' and slot.card is not None
        assert slot.card.cost == _COST and slot.card.star == 1
