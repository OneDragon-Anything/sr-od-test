"""策略卡首领节点完成固定集发放登记表测试(镜像 src = kernel/
cw_investments.py 的 STRATEGY_BOSS_COMPLETION_GRANTS + 构建校验)。

测试面依据 = 迭代设计 designs/T-330-wuqi-pifashang.md §4 锁 1/2 +
REVIEW-T330 §4.3(校验面五哨逐哨定性全留,禁按「治理 = 全删」误删
漂移哨):①孤儿键/②id 双匹配(幸存面,id 字段表家族已登记形)/③items
非空/④逐件 ∈ 装备注册表名闭集/⑤类别断言(锁「全集 = 简易」语义)——
哨面共同性质 = 能被游戏版本变更(策略卡改名/数据 source 改/注册表
改版)独立触发,按 2026-10-28 治理判据属漂移哨全留;import 即炸语义
经直调校验函数锁定,防哨被再删。登记单一源:行值 = 卡面效果原文直读
(武器批发商 id 303501:「下个首领节点后，获得所有类型的简易装备各
1个。」),表值引用 SIMPLE_EQUIP_ALL 注册表派生冻结快照,禁手写名单
第二源(锁 2 双源同值 = 现算重取对拍冻结快照,注册表漂移自动跟随的
回归基准,防表值僵化)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_equipment_data import (
    EQUIPMENTS,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    SIMPLE_EQUIP_ALL,
    STRATEGY_BOSS_COMPLETION_GRANTS,
    StrategyBossCompletionGrant,
    _validate_strategy_boss_completion_grants,
    equips_by_category,
)

_CARD = '武器批发商'


def test_registry_rows_closed_set() -> None:
    """登记面闭集:族现役单成员(禁顺手代登记,同族后续卡各自独立批,
    扩名随批申报)。"""
    assert set(STRATEGY_BOSS_COMPLETION_GRANTS) == {_CARD}, \
        f'注册面漂移: {sorted(STRATEGY_BOSS_COMPLETION_GRANTS)!r}'


def test_registry_row_single_source() -> None:
    """登记单一源:行值 = 卡面原文直读(id 303501 / items = 简易池
    冻结快照);items 与 SIMPLE_EQUIP_ALL 引用同一(禁手写名单第二源的
    机械证据——表值必须引用同一快照对象);键 ∈ 策略注册表(孤儿哨
    现值通过 = import 过闸即证,显式对拍防静默漂移)。"""
    row = STRATEGY_BOSS_COMPLETION_GRANTS[_CARD]
    assert row.id == '303501', f'id 漂移: {row.id!r}'
    assert row.items is SIMPLE_EQUIP_ALL, 'items 须引用冻结快照本体'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'


def test_simple_pool_frozen_snapshot_matches_registry() -> None:
    """锁 2(池派生双源同值):冻结快照与注册表现算重取同值(注册表
    漂移自动跟随的回归基准,防表值僵化);快照非空(数据性质,哨 ③ 现值
    通过的对拍面)。"""
    assert set(SIMPLE_EQUIP_ALL) == set(equips_by_category('简易')), \
        f'池派生漂移: {SIMPLE_EQUIP_ALL!r}'
    assert len(SIMPLE_EQUIP_ALL) > 0, '简易池必须非空(数据性质)'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """哨①(孤儿键,漂移哨):键不在策略注册表 → ValueError(import
    即炸语义;直调校验函数锁同款行为,防哨被再删)。"""
    monkeypatch.setitem(STRATEGY_BOSS_COMPLETION_GRANTS, '不存在的卡',
                        StrategyBossCompletionGrant(id='1',
                                                    items=SIMPLE_EQUIP_ALL))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_boss_completion_grants()


def test_validator_id_mismatch_raises(monkeypatch) -> None:
    """哨②(id 双匹配,幸存面):id 与数据 source 改任一独立触发 →
    ValueError(数据行 source 改版/id 手抄改写双源;id 字段表家族
    已登记形)。"""
    monkeypatch.setitem(STRATEGY_BOSS_COMPLETION_GRANTS, _CARD,
                        StrategyBossCompletionGrant(id='999999',
                                                    items=SIMPLE_EQUIP_ALL))
    with pytest.raises(ValueError, match='id 双匹配失配'):
        _validate_strategy_boss_completion_grants()


def test_validator_empty_items_raises(monkeypatch) -> None:
    """哨③(items 非空,漂移哨):派生表达式注册表改版清空简易类别可
    独立触发 → ValueError。"""
    monkeypatch.setitem(STRATEGY_BOSS_COMPLETION_GRANTS, _CARD,
                        StrategyBossCompletionGrant(id='303501', items=()))
    with pytest.raises(ValueError, match='items 空'):
        _validate_strategy_boss_completion_grants()


def test_validator_non_equip_name_raises(monkeypatch) -> None:
    """哨④(逐件 ∈ 装备注册表名闭集,漂移哨):注册表改名后派生值含
    失效名独立触发 → ValueError。"""
    monkeypatch.setitem(STRATEGY_BOSS_COMPLETION_GRANTS, _CARD,
                        StrategyBossCompletionGrant(
                            id='303501', items=('不存在的装备',)))
    with pytest.raises(ValueError, match='非装备名'):
        _validate_strategy_boss_completion_grants()


def test_validator_non_simple_category_raises(monkeypatch) -> None:
    """哨⑤(类别断言,漂移哨,锁「全集 = 简易」语义):表达式误改后
    静默发放非简易件的防线下失效独立触发 → ValueError(非简易名 =
    注册表现取,零手抄第二源)。"""
    non_simple = next(n for n, e in EQUIPMENTS.items()
                      if e.category != '简易')
    monkeypatch.setitem(STRATEGY_BOSS_COMPLETION_GRANTS, _CARD,
                        StrategyBossCompletionGrant(id='303501',
                                                    items=(non_simple,)))
    with pytest.raises(ValueError, match='非简易件'):
        _validate_strategy_boss_completion_grants()
