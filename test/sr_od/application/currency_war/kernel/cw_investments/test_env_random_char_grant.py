"""RandomCharSpec 阵营轴 + 概念股族登记测试(镜像 src =
kernel/cw_investments.py;按拆目录规范落位本目录,同源载体兄弟测试 =
kernel/test_cw_investments.py 随机赠卡家族段〔超限只读复用〕)。

测试面依据 = gain-chain.md §3 随机支段(阵营轴采样域语义)+ fields.md
§5.2 效果缺口与载体登记(披露键组)+ 语义描述「概念股族模式卡登记约定」:
- **轴互斥**:cost 与 faction 恰好一轴非空(双空 = 全角色池,几乎必为
  登记笔误,拒收;双填 = 轴语义不明,拒收)——ENV_GIFTS 与
  ENV_DEPLOY_LOCK_GRANTS 两表共享同一校验助手;
- **阵营域空防呆**:误登角色名/笔误阵营名 → chars_by_faction 域空 →
  校验炸(误登角色名本会进 chars_immediate 具名检查域,误入阵营轴 =
  域空天然拦截);
- **概念股条目形状锁**:登记 = 阵营轴 spec(faction='追击', star=1 先验)
  + equips_random_immediate=('简易',);
- **池派生阵营支**:random_char_pool 阵营轴 = chars_by_faction 注册表
  现算比对(非快照,不手抄名单);
- **cost 轴回归**:既有条目(人才引进/英雄登场)登记形状与校验不受
  cost/star 可选化影响。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_chars import (
    CHARACTER_ROSTER,
    chars_by_cost,
    chars_by_faction,
)
from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_DEPLOY_LOCK_GRANTS,
    ENV_ECONOMY,
    ENV_GIFTS,
    GiftGrant,
    RandomCharSpec,
    equips_by_category,
    random_char_pool,
)


def test_axis_exclusivity_both_empty_and_both_filled_raise(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """采样轴互斥(概念股族登记约定;两表共享助手单一源):双空
    (RandomCharSpec() = 全角色池)与双填(cost+faction 同填)注入
    ENV_GIFTS 与 ENV_DEPLOY_LOCK_GRANTS 均校验炸——互斥检查住共享助手,
    两表同享,防登记笔误静默放行。"""
    for bad_spec in (RandomCharSpec(),                       # 双空
                     RandomCharSpec(cost=4, faction='追击'),  # 双填
                     RandomCharSpec(faction='追击', cost=1, star=2)):
        bad_gifts = dict(ENV_GIFTS)
        bad_gifts['人才引进'] = GiftGrant(chars_random_immediate=(bad_spec,))
        monkeypatch.setattr(cw_investments, 'ENV_GIFTS', bad_gifts)
        with pytest.raises(ValueError, match='采样轴'):
            cw_investments._validate_env_gifts()
        bad_locks = dict(ENV_DEPLOY_LOCK_GRANTS)
        bad_locks['英雄登场'] = cw_investments.EnvDeployLockGrant(
            spec=bad_spec, deploy_lock_nodes=19, perfect_win_accel=True)
        monkeypatch.setattr(cw_investments, 'ENV_DEPLOY_LOCK_GRANTS',
                            bad_locks)
        with pytest.raises(ValueError, match='采样轴'):
            cw_investments._validate_env_deploy_lock_grants()


def test_faction_domain_empty_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """阵营域空防呆(共享助手池非空查):误登角色名('飞霄' = 角色名非
    阵营名)与笔误阵营名 → chars_by_faction 域空 → 校验炸(import 期
    拦截——错名发放 = 采样腿永发不出的静默残缺,登记笔误前置可见)。"""
    for bad_faction in ('飞霄', '追姬'):
        bad = dict(ENV_GIFTS)
        bad['追击概念股'] = GiftGrant(
            chars_random_immediate=(RandomCharSpec(faction=bad_faction),),
            equips_random_immediate=('简易',))
        monkeypatch.setattr(cw_investments, 'ENV_GIFTS', bad)
        with pytest.raises(ValueError, match='池空'):
            cw_investments._validate_env_gifts()


def test_zhuiji_concept_stock_entry_shape() -> None:
    """追击概念股登记形状锁(概念股族模式卡登记约定,正本 = fields.md
    §5.2 效果缺口与载体登记):∈ ENV_GIFTS 且 ∉ ENV_ECONOMY(import 期
    互斥校验半边显式断言);阵营轴 spec = faction '追击'(desc【追击】
    直读,流派名非角色名)+ star 1(先验,desc 未标星);随机装备 =
    ('简易',)(desc「初始简易装备」类别明文,单数叙述默认 1 件)。"""
    assert '追击概念股' in ENV_GIFTS
    assert '追击概念股' not in ENV_ECONOMY
    grant = ENV_GIFTS['追击概念股']
    assert grant.chars_random_immediate == \
        (RandomCharSpec(faction='追击', star=1),)
    assert grant.equips_random_immediate == ('简易',)


def test_random_char_pool_faction_axis_matches_registry() -> None:
    """池派生阵营支(gain-chain.md §3 随机支段:阵营轴 = chars_by_faction
    默认含流派匹配):random_char_pool 阵营 spec 现值 = chars_by_faction
    ('追击') 名集现算双射(注册表派生,非快照不手抄);池名 ⊆ 注册表;
    池规模 = 注释性快照(2026-10 时点 8 名),非断言值。"""
    spec = ENV_GIFTS['追击概念股'].chars_random_immediate[0]
    expected = {c.name for c in chars_by_faction('追击')}
    assert set(random_char_pool(spec)) == expected, \
        '阵营轴池 = chars_by_faction 全域(注册表现算双射)'
    assert set(random_char_pool(spec)) <= CHARACTER_ROSTER
    assert len(expected) == 8, '注释性快照(漂移即提示,非行为断言)'


def test_simple_category_equip_pool_nonempty() -> None:
    """简易装备类别池非空(gain-chain.md §3 随机装备支段:类别池 =
    equips_by_category 注册表派生单源):登记类别 '简易' 现值池非空
    (构建期类别闭集 + 池非空校验已闸,显式断言登记类别可采样);池规模
    = 注释性快照(2026-10 时点 8 件),非断言值。"""
    pool = equips_by_category('简易')
    assert pool, '登记类别池非空(采样腿可达)'
    assert len(pool) == 8, '注释性快照(漂移即提示,非行为断言)'


def test_cost_axis_existing_entries_regression() -> None:
    """cost 轴既有条目回归(可选化零迁移:既有 5 个登记条目与
    ENV_DEPLOY_LOCK_GRANTS 均关键字传参):人才引进(费用轴首例,4 费/
    1★ 先验)与英雄登场(锁表,5 费/2★ 明写)登记形状不变、两表构建
    校验对现值通过、cost 轴池 = 全档现算——star 默认值 1 使
    RandomCharSpec(cost=4) 与显式 star=1 同值。"""
    assert ENV_GIFTS['人才引进'].chars_random_immediate == \
        (RandomCharSpec(cost=4, star=1),)
    assert ENV_DEPLOY_LOCK_GRANTS['英雄登场'].spec == \
        RandomCharSpec(cost=5, star=2)
    cw_investments._validate_env_gifts()
    cw_investments._validate_env_deploy_lock_grants()
    assert set(random_char_pool(RandomCharSpec(cost=4))) == \
        {c.name for c in chars_by_cost(4)}, \
        'cost 轴池 = 费用档全档(可选化后缺省星级行为不变)'
