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

族展开续写面 = 概念股族展开卡登记约定(燃血概念股 id 1002 族内第二实例/
能量概念股 id 1003 第三实例/列车同行概念股 id 1004 第四实例/银河学者
概念股 id 1005 第五实例,均与追击登记行同构仅值异;正本 = fields.md
§5.2 效果缺口与载体登记):登记形状锁
+ 域校验与池派生现算比对。列车同行批随行落地「开拓者双形态角色位合并
约定」(牌库中开拓者占单一角色位,random_char_pool 尾部剔除键侧条目,
采样即发放名 = 值侧形态恒欢愉;economy.md §8):合并机制锁 + 既有 cost
轴/能量域锁的池期望值同步按合并后口径现算。银河学者域现值无开拓者
条目、无独立单位成员,合并对本域零作用,池 = 原始域(双阵营成员真理
医生照发,「姬子·启行」定谳同案)。
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
    ('追击') 名集现算双射(注册表派生,非快照不手抄);池名 ⊆ 注册表。"""
    spec = ENV_GIFTS['追击概念股'].chars_random_immediate[0]
    expected = {c.name for c in chars_by_faction('追击')}
    assert set(random_char_pool(spec)) == expected, \
        '阵营轴池 = chars_by_faction 全域(注册表现算双射)'
    assert set(random_char_pool(spec)) <= CHARACTER_ROSTER


def test_simple_category_equip_pool_nonempty() -> None:
    """简易装备类别池非空(gain-chain.md §3 随机装备支段:类别池 =
    equips_by_category 注册表派生单源):登记类别 '简易' 现值池非空
    (构建期类别闭集 + 池非空校验已闸,显式断言登记类别可采样)。"""
    assert equips_by_category('简易'), '登记类别池非空(采样腿可达)'


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
        {c.name for c in chars_by_cost(4)} - {'开拓者·记忆'}, \
        'cost 轴池 = 费用档全档剔除开拓者·记忆(可选化缺省星级行为不变,' \
        '开拓者双形态按角色位合并)'


def test_ranxue_concept_stock_entry_shape() -> None:
    """燃血概念股登记形状锁(概念股族展开卡登记约定,正本 = fields.md
    §5.2 效果缺口与载体登记):∈ ENV_GIFTS 且 ∉ ENV_ECONOMY(import 期
    互斥校验半边显式断言);阵营轴 spec = faction '燃血'(desc【燃血】
    直读,流派名非角色名,与卡名剥「概念股」后缀的 ENV_FACTION 派生值
    双源同值)+ star 1(先验,desc 未标星);随机装备 = ('简易',)
    (desc「初始简易装备」类别明文,单数叙述默认 1 件)。族内第二实例,
    与追击登记行同构仅值异。"""
    assert '燃血概念股' in ENV_GIFTS
    assert '燃血概念股' not in ENV_ECONOMY
    grant = ENV_GIFTS['燃血概念股']
    assert grant.chars_random_immediate == \
        (RandomCharSpec(faction='燃血', star=1),)
    assert grant.equips_random_immediate == ('简易',)


def test_ranxue_faction_pool_matches_registry_and_validates() -> None:
    """燃血域登记校验 + 池派生(概念股族展开卡登记约定;gain-chain.md
    §3 随机支段:阵营轴 = chars_by_faction 默认含流派匹配):燃血概念股
    过 _validate_env_gifts 现行全套(含 _validate_random_char_spec 阵营轴
    分支——轴互斥/星级域/池非空,「燃血」流派域非空天然通过);
    random_char_pool 阵营 spec 现值 = chars_by_faction('燃血') 名集现算
    双射(注册表派生,非快照不手抄;池规模只记注释不做断言值——现值
    8 名含纯 flows 成员布洛妮娅,随版本正常变动)。"""
    cw_investments._validate_env_gifts()
    spec = ENV_GIFTS['燃血概念股'].chars_random_immediate[0]
    expected = {c.name for c in chars_by_faction('燃血')}
    assert set(random_char_pool(spec)) == expected, \
        '阵营轴池 = chars_by_faction 全域(注册表现算双射)'
    assert set(random_char_pool(spec)) <= CHARACTER_ROSTER


def test_nengliang_concept_stock_entry_shape() -> None:
    """能量概念股登记形状锁(概念股族展开卡登记约定,正本 = fields.md
    §5.2 效果缺口与载体登记):∈ ENV_GIFTS 且 ∉ ENV_ECONOMY(import 期
    互斥校验半边显式断言);阵营轴 spec = faction '能量'(desc【能量】
    直读,流派名非角色名,与卡名剥「概念股」后缀的 ENV_FACTION 派生值
    双源同值)+ star 1(先验,desc 未标星);随机装备 = ('简易',)
    (desc「初始简易装备」类别明文,单数叙述默认 1 件)。族内第三实例,
    与追击/燃血登记行同构仅值异。"""
    assert '能量概念股' in ENV_GIFTS
    assert '能量概念股' not in ENV_ECONOMY
    grant = ENV_GIFTS['能量概念股']
    assert grant.chars_random_immediate == \
        (RandomCharSpec(faction='能量', star=1),)
    assert grant.equips_random_immediate == ('简易',)


def test_nengliang_faction_pool_matches_registry_and_validates() -> None:
    """能量域登记校验 + 池派生(概念股族展开卡登记约定;gain-chain.md
    §3 随机支段:阵营轴 = chars_by_faction 默认含流派匹配):能量概念股
    过 _validate_env_gifts 现行全套(含 _validate_random_char_spec 阵营轴
    分支——轴互斥/星级域/池非空,「能量」流派域非空天然通过);
    random_char_pool 阵营 spec 现值 = chars_by_faction('能量') 名集剔除
    '开拓者·记忆' 现算比对(开拓者双形态按角色位合并约定,采样域即发放
    域恒发欢愉;注册表派生非快照不手抄,池规模只记注释零断言值——现值
    8 名,随版本正常变动)。"""
    cw_investments._validate_env_gifts()
    spec = ENV_GIFTS['能量概念股'].chars_random_immediate[0]
    expected = {c.name for c in chars_by_faction('能量')} - {'开拓者·记忆'}
    assert set(random_char_pool(spec)) == expected, \
        '阵营轴池 = chars_by_faction 全域剔除开拓者·记忆(双形态合并现算)'
    assert set(random_char_pool(spec)) <= CHARACTER_ROSTER


def test_lieche_concept_stock_entry_shape() -> None:
    """列车同行概念股登记形状锁(概念股族展开卡登记约定,正本 = fields.md
    §5.2 效果缺口与载体登记):∈ ENV_GIFTS 且 ∉ ENV_ECONOMY(import 期
    互斥校验半边显式断言);阵营轴 spec = faction '列车同行'(desc
    【列车同行】直读,阵容羁绊名非角色名,与卡名剥「概念股」后缀的
    ENV_FACTION 派生值双源同值)+ star 1(先验,desc 未标星);随机装备
    = ('简易',)(desc「初始简易装备」类别明文,单数叙述默认 1 件)。
    族内第四实例,与追击/燃血/能量登记行同构仅值异。"""
    assert '列车同行概念股' in ENV_GIFTS
    assert '列车同行概念股' not in ENV_ECONOMY
    grant = ENV_GIFTS['列车同行概念股']
    assert grant.chars_random_immediate == \
        (RandomCharSpec(faction='列车同行', star=1),)
    assert grant.equips_random_immediate == ('简易',)


def test_lieche_faction_pool_matches_registry_and_validates() -> None:
    """列车同行域登记校验 + 池派生(概念股族展开卡登记约定 + 开拓者双
    形态角色位合并约定;gain-chain.md §3 随机支段:阵营轴 = 规格过滤池):
    列车同行概念股过 _validate_env_gifts 现行全套(含
    _validate_random_char_spec 阵营轴分支——轴互斥/星级域/池非空,
    「列车同行」阵营域非空天然通过);random_char_pool 阵营 spec 现值 =
    chars_by_faction('列车同行') 名集剔除'开拓者·记忆' 现算比对(合并
    修正主锁:开拓者双形态按角色位合并,采样即发放名恒欢愉;注册表派生
    非快照不手抄,池规模只记注释零断言值——现值 7 名,随版本正常变动);
    显式断言'开拓者·欢愉' ∈ 池(发放恒欢愉形态)、'开拓者·记忆' ∉ 池
    (键侧剔除)、'姬子·启行' ∈ 池(独立单位照发定谳)。"""
    cw_investments._validate_env_gifts()
    spec = ENV_GIFTS['列车同行概念股'].chars_random_immediate[0]
    expected = {c.name for c in chars_by_faction('列车同行')} \
        - {'开拓者·记忆'}
    assert set(random_char_pool(spec)) == expected, \
        '阵营轴池 = chars_by_faction 全域剔除开拓者·记忆(双形态合并现算)'
    assert '开拓者·欢愉' in random_char_pool(spec), \
        '发放恒欢愉形态(采样即发放名)'
    assert '开拓者·记忆' not in random_char_pool(spec), \
        '键侧条目剔除(牌库单一角色位)'
    assert '姬子·启行' in random_char_pool(spec), \
        '独立单位在候选内照发(实机知识定谳)'
    assert set(random_char_pool(spec)) <= CHARACTER_ROSTER


def test_dual_form_merge_pool_construction() -> None:
    """开拓者双形态按角色位合并机制锁(开拓者双形态角色位合并约定,
    正本 = fields.md §5.2 效果缺口与载体登记 + economy.md §8:键侧条目
    剔除在 type_tag 过滤之后,消费 = random_char_pool 尾部统一收口):
    4 费档池 = chars_by_cost(4) 剔除'开拓者·记忆'现算(人才引进采样
    概率随合并向实机真值收敛);3 费档无开拓者条目 = chars_by_cost(3)
    全档回归(合并对无双形态档零扰);能量域直构 spec 池 = chars_by_
    faction('能量') 剔除'开拓者·记忆'现算(已落地能量概念股登记条目随
    合并自动收敛)。池规模只记注释零断言值(现值 13/14/8,随版本变动)。"""
    assert set(random_char_pool(RandomCharSpec(cost=4))) == \
        {c.name for c in chars_by_cost(4)} - {'开拓者·记忆'}, \
        '4 费档剔除开拓者·记忆(双形态合并)'
    assert set(random_char_pool(RandomCharSpec(cost=3))) == \
        {c.name for c in chars_by_cost(3)}, \
        '3 费档无开拓者 = 全档回归(合并零扰)'
    energy_expected = {c.name for c in chars_by_faction('能量')} \
        - {'开拓者·记忆'}
    assert set(random_char_pool(RandomCharSpec(faction='能量'))) == \
        energy_expected, '能量域直构 spec 同收口(剔除开拓者·记忆)'


def test_yinhe_concept_stock_entry_shape() -> None:
    """银河学者概念股登记形状锁(概念股族展开卡登记约定,正本 = fields.md
    §5.2 效果缺口与载体登记):∈ ENV_GIFTS 且 ∉ ENV_ECONOMY(import 期
    互斥校验半边显式断言);阵营轴 spec = faction '银河学者'(desc
    【银河学者】直读,阵营羁绊名非角色名,与卡名剥「概念股」后缀的
    ENV_FACTION 派生值双源同值)+ star 1(先验,desc 未标星);随机装备
    = ('简易',)(desc「初始简易装备」类别明文,单数叙述默认 1 件,
    装备身份零先验——economy.md「概念股送装备件」四卡线索名单不含银河
    学者,均匀 v0 + 按卡固定假说随家族披露键待校准)。族内第五实例,
    与追击/燃血/能量/列车同行登记行同构仅值异。"""
    assert '银河学者概念股' in ENV_GIFTS
    assert '银河学者概念股' not in ENV_ECONOMY
    grant = ENV_GIFTS['银河学者概念股']
    assert grant.chars_random_immediate == \
        (RandomCharSpec(faction='银河学者', star=1),)
    assert grant.equips_random_immediate == ('简易',)


def test_yinhe_faction_pool_matches_registry_and_validates() -> None:
    """银河学者域登记校验 + 池派生(概念股族展开卡登记约定;gain-chain.md
    §3 随机支段:阵营轴 = 规格过滤池):银河学者概念股过 _validate_env_
    gifts 现行全套(含 _validate_random_char_spec 阵营轴分支——轴互斥/
    星级域/池非空,「银河学者」阵营域非空天然通过);random_char_pool
    阵营 spec 现值 = chars_by_faction('银河学者') 名集现算比对(注册表
    派生非快照不手抄,池规模只记注释零断言值——现值 5 名,随版本正常
    变动);显式断言'真理医生' ∈ 池(双阵营成员「银河学者、星间旅人」
    按 factions 轴在池照发,镜像列车同行批'姬子·启行'的定谳断言式;
    本域无开拓者条目,双形态合并对本域零作用,池 = 原始域)。"""
    cw_investments._validate_env_gifts()
    spec = ENV_GIFTS['银河学者概念股'].chars_random_immediate[0]
    expected = {c.name for c in chars_by_faction('银河学者')}
    assert set(random_char_pool(spec)) == expected, \
        '阵营轴池 = chars_by_faction 全域(注册表现算双射,合并对本域零作用)'
    assert '真理医生' in random_char_pool(spec), \
        '双阵营成员在池照发(实机知识定谳)'
    assert set(random_char_pool(spec)) <= CHARACTER_ROSTER
