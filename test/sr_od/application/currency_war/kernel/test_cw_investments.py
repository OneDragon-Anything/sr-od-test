"""cw_investments 随机赠卡家族载体测试(RandomCharSpec / random_char_pool /
构建校验扩展;迭代 2026-09-23-invest-effects-calc T-10 人才引进)。

测试面依据 = 该迭代 designs/T-10-rencai-yinjin.md §2.1-§2.2(定稿):
- **载体值域三查**(import 即炸语义,注入 + 直调沿 ENV_GIFTS 校验测试
  惯用法):cost 1-5 / star 1-3 / type_tag ∈ 注册表 char_type 标签闭集,
  bool 显式拒(bool 是 int 子类,True 会被纯 int 判当 1 混过);
- **空发放集判定并入 chars_random_immediate**(env/策略两表):随机支
  only 条目是合法登记形态,不得被「空发放集」误炸;全空条目照炸
  (env 侧全空对照 = 既有测试 kernel/test_gain_chain.py
  test_env_gifts_validation_empty_grant_includes_scheduled,不重复);
- **互斥面**:人才引进 ∩ ENV_ECONOMY = ∅(import 期互斥校验显式半边);
- **池派生性质**(注册表现算对照,非快照断言):空 type_tag = 费用档
  全员旁路、非空 = char_type 含标签过滤;池规模作注释性快照(2026-10
  时点 4 费 14 名)非断言值。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_chars import (
    CHARACTER_ROSTER,
    CHARACTERS,
    chars_by_cost,
)
from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_ECONOMY,
    ENV_GIFTS,
    STRATEGY_GRANTS,
    GiftGrant,
    RandomCharSpec,
    random_char_pool,
)


def test_random_char_spec_value_domain_raises(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """RandomCharSpec 值域三查(T-10 设计 §2.2 条 1):cost 1-5、star
    1-3(Unit.star 值域)、type_tag ∈ 注册表标签闭集(错字致池空静默);
    cost/star 拒 bool(True 是 int 子类,纯 int 判会当 1 混过)。"""
    bad_specs = [
        RandomCharSpec(cost=0, star=1),      # 费用档下界外
        RandomCharSpec(cost=6, star=1),      # 费用档上界外
        RandomCharSpec(cost=True, star=1),   # bool 拒
        RandomCharSpec(cost=4, star=0),      # 星级下界外
        RandomCharSpec(cost=4, star=4),      # 星级上界外
        RandomCharSpec(cost=4, star=True),   # bool 拒
        RandomCharSpec(cost=4, star=1, type_tag='輸出'),  # 闭集外(错字)
    ]
    for spec in bad_specs:
        bad = dict(ENV_GIFTS)
        bad['人才引进'] = GiftGrant(chars_random_immediate=(spec,))
        monkeypatch.setattr(cw_investments, 'ENV_GIFTS', bad)
        with pytest.raises(ValueError):
            cw_investments._validate_env_gifts()


def test_random_only_grant_not_empty_grant_both_tables(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """空发放集判定并入新字段(env/策略两表,T-10 设计 §2.2 条 3/4):
    chars_random_immediate-only 条目 = 合法登记,两表校验均不得炸——
    未并入时随机支登记会被「空发放集」误炸(import 期即拦)。"""
    # env 侧:现值表(人才引进 = 随机支 only)直调通过
    cw_investments._validate_env_gifts()
    # 策略侧:GiftGrant 两表共享,注入随机支 only 条目同样通过
    bad = dict(STRATEGY_GRANTS)
    bad['佩佩驾到'] = GiftGrant(
        chars_random_immediate=(RandomCharSpec(cost=2, star=1),))
    monkeypatch.setattr(cw_investments, 'STRATEGY_GRANTS', bad)
    cw_investments._validate_strategy_grants()
    # 对照:全空条目在策略侧照炸(判定仍在,只是并入新通道)
    bad2 = dict(STRATEGY_GRANTS)
    bad2['佩佩驾到'] = GiftGrant()
    monkeypatch.setattr(cw_investments, 'STRATEGY_GRANTS', bad2)
    with pytest.raises(ValueError, match='空发放集'):
        cw_investments._validate_strategy_grants()


def test_talent_import_not_in_env_economy() -> None:
    """互斥面(T-10 设计 §4 测试 1 末项):人才引进 ∈ ENV_GIFTS 且 ∉
    ENV_ECONOMY——import 期互斥校验半边的显式断言。"""
    assert '人才引进' in ENV_GIFTS
    assert '人才引进' not in ENV_ECONOMY


def test_random_char_pool_derivation_properties() -> None:
    """池派生性质测试(T-10 设计 §4 测试 2,注册表现算对照):空 type_tag =
    费用档全员旁路(池 = 4 费全档);非空 type_tag = char_type 含标签
    过滤(子集 + 逐名含标签);池名 ⊆ 注册表。池规模 = 注释性快照
    (2026-10 时点 14 名),非断言值(注册表随版本扩充)。"""
    pool_all = random_char_pool(RandomCharSpec(cost=4, star=1))
    assert set(pool_all) == {c.name for c in chars_by_cost(4)}, \
        'type_tag 空 = 全档旁路'
    assert set(pool_all) <= CHARACTER_ROSTER
    pool_tag = random_char_pool(RandomCharSpec(cost=4, star=1,
                                               type_tag='输出'))
    assert pool_tag, '过滤池非空(注册表现值)'
    assert set(pool_tag) <= set(pool_all), '过滤池 ⊆ 全档'
    for name in pool_tag:
        assert '输出' in CHARACTERS[name].char_type.split('、')
