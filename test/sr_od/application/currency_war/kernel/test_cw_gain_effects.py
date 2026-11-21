"""cw_gain_effects 随机装备族契约测试(泛化表类别词现役体系 + 池空哨 + 发放链)。

锁的设计约定:
- 泛化表 ``_STRATEGY_RANDOM_EQUIP_GRANTS`` 全部登记类别词必须在现役装备
  注册表派生池非空——登记词 = cw_equipment_data v4.7 现役类别体系(官方
  7 类直落 + 派生类「简易装备」;官方分类表无「简易」类,卡文短词
  「简易/进阶/特权」对应注册表词「简易装备/进阶装备/特权装备」),词漂移
  (错字/版本改名)即红;
- 池空哨 = 效果体工厂 ``_make_random_equip_effect`` 构建期单一收口
  (泛化表行与直书组合卡全经本工厂在本模块 import 期构建):派生池空即炸,
  测试锁哨值守行为,防哨被注释/改坏后登记漂移静默逃过 import 闸;
- 运行期空池显式报错不静默零写——曾以 log 兜底静默丢发(运行期抽到
  旧类别词即丢,无告警无 import 闸),本测试锁「禁静默兜底丢弃」回归面;
- 抽样发放链:泛化表行效果体真实入栏(equips 增量 = 采样名,效果串逐条
  对应),锁「登记词失效 → 池空 → 零发放」缺陷的治愈面。
"""

import random

import pytest

from sr_od.application.currency_war.kernel import cw_gain_effects as ge
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    equips_by_category,
)

_SIG = ChannelSig(family='logic_action', actor='test')

# 换季修复锁定的登记词面:泛化表在册三类别(「进阶装备」行系直书组合卡,
# 词面藏于闭包不可内省,由 import 期哨守卫——词错即模块炸,全测试红)。
_EXPECTED_TABLE_CATEGORIES = {'简易装备', '特权装备', '星徽'}


def test_random_equip_grant_categories_have_pools() -> None:
    """泛化表登记类别词全部有非空现役池,且换季三词在场。"""
    cats = {cat for cat, _n in ge._STRATEGY_RANDOM_EQUIP_GRANTS.values()}
    assert cats, '泛化随机装备表登记为空(登记面被清?)'
    assert cats >= _EXPECTED_TABLE_CATEGORIES, (
        f'换季类别词缺失: {_EXPECTED_TABLE_CATEGORIES - cats}')
    for cat in cats:
        pool = equips_by_category(cat)
        assert pool, f'类别 {cat!r} 派生池空(登记词漂移/注册表漂移?)'


def test_factory_blocks_empty_category_pool() -> None:
    """构建期哨:登记类别词派生池空时炸出池空定位文案(词漂移场景)。"""
    with pytest.raises(ValueError, match=r"类别池空.*'不存在类'"):
        ge._make_random_equip_effect('不存在类', 1)


def test_runtime_empty_pool_raises(monkeypatch) -> None:
    """运行期防线:池运行期变空显式报错,禁静默零写(log 兜底回归锁)。

    效果体须先在健康注册表下构建(构建期哨放行),再猴补派生口为恒空池
    触达运行期分支——静默零写旧形态在此表现为返回空表不炸,即红。
    """
    effect = ge._make_random_equip_effect('简易装备', 1)
    monkeypatch.setattr(ge, 'equips_by_category', lambda _cat: ())
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    with pytest.raises(ValueError, match=r'运行期漂移'):
        effect(gs, sig=_SIG, rng=random.Random(1))


def _gs_with_empty_equips() -> GameState:
    """发放链种子:equips 观察为空栏(未观察 = 原语拒落,非本测场景)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.equips, [], sig=ChannelSig(family='obs', actor='test'))
    return gs


def test_random_equip_grants_land_in_equips() -> None:
    """抽样发放链:泛化表行效果体真实入栏(静默丢装备缺陷回归锁)。

    count=1(打捞人才库+)与 count=2 放回(好运来)各一:效果串逐条
    对应入栏增量,采样名 ∈ 简易装备池——登记词失效期本链只产 log 零发放。
    """
    simple_pool = set(equips_by_category('简易装备'))
    gs1 = _gs_with_empty_equips()
    steps1 = ge.PICK_INVEST_EFFECTS['打捞人才库+'](
        gs1, sig=_SIG, rng=random.Random(7))
    assert len(steps1) == 1
    assert gs1.equips.value[0] in simple_pool
    assert steps1 == [f'strategy_random_equip:{gs1.equips.value[0]}']
    gs2 = _gs_with_empty_equips()
    steps2 = ge.PICK_INVEST_EFFECTS['好运来'](
        gs2, sig=_SIG, rng=random.Random(11))
    assert len(steps2) == 2
    assert [step.split(':', 1)[1] for step in steps2] == gs2.equips.value
    assert set(gs2.equips.value) <= simple_pool
