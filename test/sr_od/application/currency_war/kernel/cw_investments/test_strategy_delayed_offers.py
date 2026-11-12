"""策略卡延时 offer 注册表测试(镜像 src = kernel/cw_investments.py 的
StrategyDelayedOffer + STRATEGY_DELAYED_OFFERS + 构建校验)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§4(锁 1 经硬裁定
收缩:防登记笔误类校验「delay_nodes int/quality 越域」不落校验不落锁,
2026-10-28 治理口径同源——只留漂移哨;白银投资批同裁扩 refresh_count
值域哨不加)+ 原稿锁面(§ 号 = 原稿节序)§4(锁 2 值形泛化):
- 登记单一源:行值 = 卡面效果原文直读(黄金期货 id 101101/5 节点/金;
  黄金期货+ id 101102/4 节点/金;彩虹期货 id 201101/5 节点/棱彩;
  彩虹期货+ id 201102/4 节点/棱彩;白银投资 id 203201 两条效果条目
  (立刻/银/刷3)+(3节点/银/刷3)),
  表键集闭族现役卡(展开卡各自独立批领取,禁顺手代登记);
- 值形泛化锁:表值恒效果条目元组(期货四行一元元组语义不变;白银投资两条效果条目
  元组,条目序 = 登记序);
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
    「黄金投资策略三选一」→ 候选品质金;「不能刷新」→ refresh_count=0
    = 呈现恒空刷新授权承载);键集闭 = 族现役卡(族展开卡各自独立批
    领取,禁顺手代登记);base 溯源 id 对拍(id 101101 ↔ plaza:101101)。"""
    assert set(STRATEGY_DELAYED_OFFERS) == {'黄金期货', '黄金期货+',
                                            '彩虹期货', '彩虹期货+',
                                            '白银投资', '黄金投资', '摸个鱼吧I', '摸个鱼吧II'}, \
        '注册面 = 族现役五卡(展开卡各自独立批,禁顺手代登记)'
    row, = STRATEGY_DELAYED_OFFERS['黄金期货']
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
    row, = STRATEGY_DELAYED_OFFERS['黄金期货+']
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
    row, = STRATEGY_DELAYED_OFFERS['彩虹期货']
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
    row, = STRATEGY_DELAYED_OFFERS['彩虹期货+']
    assert row == StrategyDelayedOffer(id='201102', delay_nodes=4,
                                       offer_quality='棱彩')
    base = INVESTMENT_STRATEGIES['彩虹期货+']
    assert base.source == f"plaza:{row.id}", \
        f'溯源 id 对拍失同步: {base.source}'


def test_value_shape_generalized_tuple_silver_two_legs() -> None:
    """值形泛化锁(白银投资批):表值恒非空效果条目元组(逐行);期货四行
    一元元组语义不变(行值锁四条已直测);白银投资行 = 两条效果条目元组,
    条目序 = 登记序(立刻效果条目 delay 0 + 延时效果条目 delay 3,同品质银、同刷新
    授权 3;id 同源 203201 对拍)。「再获得一个」= 完整包复刻
    (用户裁定 2026-11-02,案 A:延时效果条目复刻立刻效果条目全参数)。"""
    for _name, _legs in STRATEGY_DELAYED_OFFERS.items():
        assert isinstance(_legs, tuple) and _legs, \
            f'{_name} 值形非非空元组: {_legs!r}'
        assert all(isinstance(_l, StrategyDelayedOffer) for _l in _legs), \
            f'{_name} 效果条目元素类型漂移'
    legs = STRATEGY_DELAYED_OFFERS['白银投资']
    assert legs == (
        StrategyDelayedOffer(id='203201', delay_nodes=0,
                             offer_quality='银', refresh_count=3),
        StrategyDelayedOffer(id='203201', delay_nodes=3,
                             offer_quality='银', refresh_count=3)), \
        f'白银投资两条效果条目值: {legs!r}'
    base = INVESTMENT_STRATEGIES['白银投资']
    assert base.source == 'plaza:203201', f'溯源 id 对拍: {base.source}'
    assert len({leg.id for leg in legs}) == 1, '两条效果条目同 id'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验①(孤儿哨):键不在 base 注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_DELAYED_OFFERS, '不存在的卡',
        (StrategyDelayedOffer(id='999999', delay_nodes=5,
                              offer_quality='金'),))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_delayed_offers()


def test_validator_id_mismatch_raises(monkeypatch) -> None:
    """构建校验②(id 双匹配哨):登记 id ≠ base 溯源 id → ValueError
    (版本改名且 id 仍在的漂移也炸)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_DELAYED_OFFERS, '黄金期货',
        (StrategyDelayedOffer(id='101999', delay_nodes=5,
                              offer_quality='金'),))
    with pytest.raises(ValueError, match='id 漂移'):
        _validate_strategy_delayed_offers()


def test_mogeyuba2_delay_row():
    """摸个鱼吧II 延时行锁:5 节点/棱彩品质/可刷新基形(201103 先例
    同款 refresh_count 缺省)。"""
    rows = STRATEGY_DELAYED_OFFERS['摸个鱼吧II']
    assert len(rows) == 1, '一条效果条目'
    row = rows[0]
    assert row.id == '260201', 'id 对拍'
    assert row.delay_nodes == 5, '深思熟虑 5 节点'
    assert row.offer_quality == '棱彩', '棱彩品质'

