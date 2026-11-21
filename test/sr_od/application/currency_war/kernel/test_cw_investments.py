"""cw_investments 装备侧登记哨契约测试(ENV_GIFTS 类别词现役体系 + 哨值守)。

锁的设计约定:
- ENV_GIFTS 全部随机装备登记类别词必须在现役装备注册表派生池非空——
  登记词 = cw_equipment_data v4.7 现役类别体系(官方 7 类直落 + 派生类
  「简易装备」;官方分类表无「简易」类,简易件是合成材料层,生成器从
  compose_list 子件展开派生),词漂移(错字/版本改名)即红;
- 哨本体 = ``_validate_env_gifts`` import 期闸三件套:①随机装备类别池空
  哨 ②装备名漂移哨 ③'星徽'类别池独立闸(单一闸两消费者:环境侧劳务派遣
  合同 + 策略侧买彩票经 cw_gain_effects._STRATEGY_RANDOM_EQUIP_GRANTS
  星徽行搭便车)——测试逐支锁值守行为,防哨被注释/改坏后登记漂移静默
  逃过 import 闸。
"""

import pytest

from sr_od.application.currency_war.kernel import cw_investments as inv

# 换季修复锁定的两个登记词面:概念股族走派生类「简易装备」,劳务派遣
# 合同走官方类「星徽」(依据与旧→新对应 = cw_investments 概念股族模板声明)。
_EXPECTED_RANDOM_EQUIP_CATEGORIES = {'简易装备', '星徽'}


def test_env_gifts_random_equip_categories_have_pools() -> None:
    """ENV_GIFTS 随机装备登记类别词全部有非空现役池,且换季两词在场。"""
    cats = {c for g in inv.ENV_GIFTS.values()
            for c in g.equips_random_immediate}
    assert cats, 'ENV_GIFTS 随机装备登记为空(登记面被清?)'
    assert cats >= _EXPECTED_RANDOM_EQUIP_CATEGORIES, (
        f'换季类别词缺失: {_EXPECTED_RANDOM_EQUIP_CATEGORIES - cats}')
    for cat in cats:
        pool = inv.equips_by_category(cat)
        assert pool, f'类别 {cat!r} 派生池空(登记词漂移/注册表漂移?)'


def test_validate_env_gifts_healthy_registry_passes() -> None:
    """现值注册表下哨函数直调不炸(哨体完备性守卫)。"""
    inv._validate_env_gifts()


def test_validate_env_gifts_blocks_empty_category_pool(monkeypatch) -> None:
    """①哨:登记类别词派生池变空时炸出池空定位文案(注册表漂移场景)。

    清空「简易装备」类会连带剔掉具名哨②的样本(红钻/蓝钻),故仅保留
    随机词条目再清池,单独触达哨①分支。
    """
    kept = {n: g for n, g in inv.ENV_GIFTS.items() if not g.equips_immediate}
    monkeypatch.setattr(inv, 'ENV_GIFTS', kept)
    drifted = {n: e for n, e in inv.EQUIPMENTS.items()
               if e.category != '简易装备'}
    monkeypatch.setattr(inv, 'EQUIPMENTS', drifted)
    with pytest.raises(ValueError, match=r"随机装备池空.*'简易装备'"):
        inv._validate_env_gifts()


def test_validate_env_gifts_blocks_unknown_equip_name(monkeypatch) -> None:
    """②哨:具名发放装备不在注册表时炸出漂移文案(红钻贵族 '红钻' 样本)。"""
    drifted = {n: e for n, e in inv.EQUIPMENTS.items() if n != '红钻'}
    monkeypatch.setattr(inv, 'EQUIPMENTS', drifted)
    with pytest.raises(ValueError, match=r"装备名漂移.*'红钻'"):
        inv._validate_env_gifts()


def test_validate_env_gifts_blocks_empty_star_pool(monkeypatch) -> None:
    """③闸:'星徽' 类别池静默变空时炸出注册表漂移文案。

    前置哨①②会先于闸③炸(遍历序),故仅保留无装备登记的条目再清空
    星徽池,单独触达闸③分支。
    """
    kept = {n: g for n, g in inv.ENV_GIFTS.items()
            if not g.equips_random_immediate and not g.equips_immediate}
    monkeypatch.setattr(inv, 'ENV_GIFTS', kept)
    drifted = {n: e for n, e in inv.EQUIPMENTS.items()
               if e.category != '星徽'}
    monkeypatch.setattr(inv, 'EQUIPMENTS', drifted)
    with pytest.raises(ValueError, match=r"类别池空:'星徽' 类别过滤后无装备"):
        inv._validate_env_gifts()
