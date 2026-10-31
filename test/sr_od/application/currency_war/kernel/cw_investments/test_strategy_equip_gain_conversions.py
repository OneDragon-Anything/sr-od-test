"""策略卡装备获得转换登记表测试(镜像 src = kernel/cw_investments.py 的
STRATEGY_EQUIP_GAIN_CONVERSIONS + 构建校验;按拆目录规范落位,先例 =
同目录 test_strategy_conditional_grants.py)。

测试面依据 = 迭代设计 designs/T-143-ziyou-shichang.md §4 锁 9 校验注册
义务 + REVIEW-T143 §3 漂移表 #10 校验面收敛(2026-10-28 治理口径):
三漂移哨留(孤儿键/源类别池非空/目标名 ∈ 词表 ∪ 装备注册表,均能被
游戏版本变更独立触发);源类别 ≠ 目标类别防自指属写表人纯笔误类,不加
import 期校验 → 降为表域数据性质测试(本文件 test_target_domain_
disjoint_no_self_reference,BENCH_ITEM_KINDS 键集一致性同口径归测试与
评审)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    BENCH_ITEM_NAMES,
    EQUIPMENTS,
    INVESTMENT_STRATEGIES,
    STRATEGY_EQUIP_GAIN_CONVERSIONS,
    _validate_strategy_equip_gain_conversions,
    equips_by_category,
)


def test_free_market_conversion_row_single_source() -> None:
    """登记单一源:自由市场行 = 卡面效果原文直读(「将要获得一件简易
    装备」→ 源类别简易;「改为获得1个【简易武装箱】」→ 目标占席道具);
    表键集闭族现役卡(装备获得转换族 3 卡,姊妹卡好运来/独家代言各自
    独立批领取,禁顺手代登记);base 溯源 id 对拍(id 130601 ↔
    plaza:130601)。"""
    assert set(STRATEGY_EQUIP_GAIN_CONVERSIONS) == {'自由市场'}, \
        '注册面 = 族现役首例(姊妹卡各自独立批,禁顺手代登记)'
    source_cat, target = STRATEGY_EQUIP_GAIN_CONVERSIONS['自由市场']
    assert (source_cat, target) == ('简易', '简易武装箱'), '行值 = 卡面直读'
    assert equips_by_category(source_cat), '源类别池非空(数据性质)'
    assert target in BENCH_ITEM_NAMES, '目标 = 占席道具(bench 分支现值)'
    base = INVESTMENT_STRATEGIES['自由市场']
    assert base.source == 'plaza:130601', f'溯源 id 对拍失同步: {base.source}'


def test_target_domain_disjoint_no_self_reference() -> None:
    """数据性质(防自指,治理口径归测试与评审非 import 校验):目标名不
    属源装备类别——若目标 ∈ 源类别池,转换转发再入装备域会形成转换环;
    现值目标域 = 占席道具,词表与装备注册表全互斥(目标域判别无歧义
    前提;泛化后继卡登记装备目标时本锁前提失效须随批改,勿盲改断言)。"""
    assert BENCH_ITEM_NAMES & set(EQUIPMENTS) == set(), \
        '占席道具词表与装备注册表互斥(目标域判别无歧义前提)'
    source_cat, target = STRATEGY_EQUIP_GAIN_CONVERSIONS['自由市场']
    assert target not in equips_by_category(source_cat), \
        '目标 ∉ 源类别池(转换无环数据性质)'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验①(孤儿哨):键不在 base 注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_EQUIP_GAIN_CONVERSIONS, '不存在的卡',
        ('简易', '简易武装箱'))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_equip_gain_conversions()


def test_validator_source_category_drift_raises(monkeypatch) -> None:
    """构建校验②(源类别漂移哨):源类别池空 → ValueError——类别名
    漂移的运行期实况 = 拦截谓词永不命中、转换静默失效(无异常无台账),
    import 期哨是唯一响亮拦截面(STRATEGY_HP_LOSS_GRANTS 类别漂移哨
    同形)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_EQUIP_GAIN_CONVERSIONS, '自由市场',
        ('不存在的类别', '简易武装箱'))
    with pytest.raises(ValueError, match='源类别漂移'):
        _validate_strategy_equip_gain_conversions()


def test_validator_target_name_drift_raises(monkeypatch) -> None:
    """构建校验③(目标名漂移哨):目标 ∉ BENCH_ITEM_NAMES ∪ EQUIPMENTS
    → ValueError——错名运行期实况 = 占席道具域落席直查 KeyError 炸原语
    或装备域盲追加幻影,import 期哨是唯一响亮拦截面
    (_validate_strategy_conditional_grants 装备名漂移哨同理由)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_EQUIP_GAIN_CONVERSIONS, '自由市场',
        ('简易', '不存在的目标'))
    with pytest.raises(ValueError, match='目标名漂移'):
        _validate_strategy_equip_gain_conversions()
