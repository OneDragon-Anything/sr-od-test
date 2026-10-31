"""策略卡延时发放注册表测试(镜像 src = kernel/cw_investments.py 的
StrategyDelayedGrant + STRATEGY_DELAYED_GRANTS + 构建校验)。

测试面依据 = 迭代设计 designs/T-106-rencai-jili.md §4 锁 1(经治理收缩:
防登记笔误类校验「delay_nodes 形/下界」不落校验不落锁——2026-10-28
治理口径,T-98 锁 1 同款收缩先例;只留漂移哨)+ T-107 展开卡随批扩面
(designs/T-107-rencai-jili-plus.md §4 锁 1 同型)+ 许诺特权随批扩面
(designs/T-139-xunuo-tequan.md §4 锁 1 同型):
- 登记单一源:行值 = 卡面效果原文直读(人才激励 id 101601/4 节点、
  人才激励+ id 101602/3 节点,两卡唯一差异 = 倒计时 4→3,发放物同
  员工投影仪;许诺特权 id 130201/7 节点/发放物特权武装箱),表键集
  闭族现役卡(展开卡各自独立批领取,禁顺手代登记);
- 构建校验 3 条(漂移哨,import 即炸语义经直调校验函数锁定):孤儿键 /
  id 双匹配(改名且 id 仍在的漂移也炸)/ 发放物名双域皆非。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    BENCH_ITEM_NAMES,
    INVESTMENT_STRATEGIES,
    STRATEGY_DELAYED_GRANTS,
    StrategyDelayedGrant,
    _validate_strategy_delayed_grants,
)


@pytest.mark.parametrize(('card', 'gid', 'delay', 'item'), [
    ('人才激励', '101601', 4, '员工投影仪'),
    ('人才激励+', '101602', 3, '员工投影仪'),
    ('许诺特权', '130201', 7, '特权武装箱'),
])
def test_rencai_jili_registry_row_single_source(
        card: str, gid: str, delay: int, item: str) -> None:
    """登记单一源(姊妹双卡 + 许诺特权参数化):行值 = 卡面效果原文直读
    (「N个节点后」→ N 拍,「获得1个【X】」→ 发放物 X;人才激励系即时腿
    「获得1个【员工投影仪】」由 PICK_INVEST_EFFECTS 工厂承载不入本表,
    许诺特权卡文纯延时单句零即时腿,登记腿 = 延时-only 单腿载体);
    base 溯源 id 对拍(id ↔ plaza:<id>)。表键集闭族现役三卡(未注册
    展开卡安静不写,禁顺手代登记)。"""
    assert set(STRATEGY_DELAYED_GRANTS) == {
        '人才激励', '人才激励+', '许诺特权'}, \
        '注册面 = 族现役三卡(未注册展开卡安静不写,禁顺手代登记)'
    row = STRATEGY_DELAYED_GRANTS[card]
    assert row == StrategyDelayedGrant(id=gid, delay_nodes=delay, item=item)
    base = INVESTMENT_STRATEGIES[card]
    assert base.source == f"plaza:{row.id}", \
        f'溯源 id 对拍失同步: {base.source}'


def test_grant_item_not_in_bench_wordlist() -> None:
    """发放物分道词表归属对拍(分道判据前提,注册表逐行锁):装备名
    不入占席词表(本专表不接入 BENCH_ITEM_NAMES 派生,装备名误入词表
    即被当占席道具——溢出腿假道具,该形态钉死);许诺特权发放物特权
    武装箱 = 占席词表在册 ∧ 装备表无条目(占席分道判据前提)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIPMENTS,
    )
    row = STRATEGY_DELAYED_GRANTS['人才激励']
    assert row.item in EQUIPMENTS, '发放物 = 装备表在册(装备腿分道)'
    assert row.item not in BENCH_ITEM_NAMES, \
        '装备名误入占席词表(禁入形态被破坏)'
    xunuo = STRATEGY_DELAYED_GRANTS['许诺特权']
    assert xunuo.item in BENCH_ITEM_NAMES, \
        '特权武装箱不在占席词表(占席分道判据前提被破坏)'
    assert xunuo.item not in EQUIPMENTS, \
        '占席道具误入装备表(分道双归属)'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验①(孤儿哨):键不在 base 注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_DELAYED_GRANTS, '不存在的卡',
        StrategyDelayedGrant(id='999999', delay_nodes=4,
                             item='员工投影仪'))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_delayed_grants()


def test_validator_id_mismatch_raises(monkeypatch) -> None:
    """构建校验②(id 双匹配哨):登记 id ≠ base 溯源 id → ValueError
    (版本改名且 id 仍在的漂移也炸)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_DELAYED_GRANTS, '人才激励',
        StrategyDelayedGrant(id='101999', delay_nodes=4,
                             item='员工投影仪'))
    with pytest.raises(ValueError, match='id 漂移'):
        _validate_strategy_delayed_grants()


def test_validator_item_unknown_raises(monkeypatch) -> None:
    """构建校验③(发放物名漂移哨):发放物双域皆非(装备表/占席词表
    均无)→ ValueError(版本改名/未知名,发放腿无从分道)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_DELAYED_GRANTS, '人才激励',
        StrategyDelayedGrant(id='101601', delay_nodes=4,
                             item='不存在的发放物'))
    with pytest.raises(ValueError, match='发放物名漂移'):
        _validate_strategy_delayed_grants()
