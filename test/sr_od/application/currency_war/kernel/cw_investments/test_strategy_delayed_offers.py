"""策略卡延时 offer 注册表测试(镜像 src = kernel/cw_investments.py 的
StrategyDelayedOffer + STRATEGY_DELAYED_OFFERS + 构建校验)。

测试面依据 = 迭代设计 designs/T-98-huangjin-qihuo.md §4(锁 1 经硬裁定
收缩:防登记笔误类校验「delay_nodes int/quality 越域」不落校验不落锁,
2026-10-28 治理口径同源——只留漂移哨):
- 登记单一源:行值 = 卡面效果原文直读(黄金期货 id 101101/5 节点/金;
  黄金期货+ id 101102/4 节点/金;彩虹期货 id 201101/5 节点/棱彩;
  彩虹期货+ id 201102/4 节点/棱彩),
  表键集闭族现役卡(展开卡各自独立批领取,禁顺手代登记);
- 构建校验 2 条(漂移哨,import 即炸语义经直调校验函数锁定):孤儿键 /
  id 双匹配(改名且 id 仍在的漂移也炸)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_DELAYED_OFFERS,
    StrategyDelayedOffer,
    _validate_strategy_delayed_offers,
)


def test_gold_futures_registry_row_single_source() -> None:
    """登记单一源:黄金期货行 = 卡面效果原文直读(「5个节点后」→ 5 拍,
    「黄金投资策略三选一」→ 候选品质金;「不能刷新」不立字段 = 呈现恒空
    刷新授权承载);键集闭 = 族现役卡(族展开卡各自独立批领取,禁顺手
    代登记);base 溯源 id 对拍(id 101101 ↔ plaza:101101)。"""
    assert set(STRATEGY_DELAYED_OFFERS) == {'黄金期货', '黄金期货+',
                                            '彩虹期货', '彩虹期货+'}, \
        '注册面 = 族现役四卡(展开卡各自独立批,禁顺手代登记)'
    row = STRATEGY_DELAYED_OFFERS['黄金期货']
    assert row == StrategyDelayedOffer(id='101101', delay_nodes=5,
                                       offer_quality='金')
    base = INVESTMENT_STRATEGIES['黄金期货']
    assert base.source == f"plaza:{row.id}", \
        f'溯源 id 对拍失同步: {base.source}'


def test_gold_futures_plus_registry_row_values() -> None:
    """行值直测:黄金期货+ 行 = 卡面效果原文直读(「4个节点后」→ 4 拍,
    「黄金投资策略三选一」→ 候选品质金;卡品质银是另一层次,与 offer
    候选品质无涉);base 溯源 id 对拍(id 101102 ↔ plaza:101102),
    结构镜像黄金期货行锁。"""
    row = STRATEGY_DELAYED_OFFERS['黄金期货+']
    assert row == StrategyDelayedOffer(id='101102', delay_nodes=4,
                                       offer_quality='金')
    base = INVESTMENT_STRATEGIES['黄金期货+']
    assert base.source == f"plaza:{row.id}", \
        f'溯源 id 对拍失同步: {base.source}'


def test_rainbow_futures_registry_row_values() -> None:
    """行值直测:彩虹期货行 = 卡面效果原文直读(「5个节点后」→ 5 拍,
    「棱彩投资策略三选一」→ 候选品质棱彩;数据行 rarity='金' 是卡自身
    品质另一层次,与 offer 候选品质无涉,两语义混淆即反转);base 溯源
    id 对拍(id 201101 ↔ plaza:201101),结构镜像黄金期货+ 行锁。"""
    row = STRATEGY_DELAYED_OFFERS['彩虹期货']
    assert row == StrategyDelayedOffer(id='201101', delay_nodes=5,
                                       offer_quality='棱彩')
    base = INVESTMENT_STRATEGIES['彩虹期货']
    assert base.source == f"plaza:{row.id}", \
        f'溯源 id 对拍失同步: {base.source}'


def test_rainbow_futures_plus_registry_row_values() -> None:
    """行值直测:彩虹期货+ 行 = 卡面效果原文直读(「4个节点后」→ 4 拍,
    「棱彩投资策略三选一」→ 候选品质棱彩);与彩虹期货仅倒计时数值不同,
    机制全量继承;base 溯源 id 对拍(id 201102 ↔ plaza:201102),结构
    镜像彩虹期货行锁。"""
    row = STRATEGY_DELAYED_OFFERS['彩虹期货+']
    assert row == StrategyDelayedOffer(id='201102', delay_nodes=4,
                                       offer_quality='棱彩')
    base = INVESTMENT_STRATEGIES['彩虹期货+']
    assert base.source == f"plaza:{row.id}", \
        f'溯源 id 对拍失同步: {base.source}'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验①(孤儿哨):键不在 base 注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_DELAYED_OFFERS, '不存在的卡',
        StrategyDelayedOffer(id='999999', delay_nodes=5,
                             offer_quality='金'))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_delayed_offers()


def test_validator_id_mismatch_raises(monkeypatch) -> None:
    """构建校验②(id 双匹配哨):登记 id ≠ base 溯源 id → ValueError
    (版本改名且 id 仍在的漂移也炸)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_DELAYED_OFFERS, '黄金期货',
        StrategyDelayedOffer(id='101999', delay_nodes=5,
                             offer_quality='金'))
    with pytest.raises(ValueError, match='id 漂移'):
        _validate_strategy_delayed_offers()
