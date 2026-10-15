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
    INVESTMENT_STRATEGIES,
    STRATEGY_BINDINGS,
    STRATEGY_GRANTS,
    GiftGrant,
    RandomCharSpec,
    env_faction_scope,
    random_char_pool,
    strategy_faction_scope,
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


# ==================== 阵容指向集(投资选卡阵容冲突护栏 §2.1)====================
# 判据 = changes/2026-10-17-invest-direction-guard/design.md §2.1 三腿派生
# (faction/亲和/成员),期望值全部注册表现算(非快照),与设计 §4 测试
# 清单期望逐条对齐。

def test_strategy_scope_defining_card_heita_epoch() -> None:
    """黑塔纪元(绑 ∅ + {大黑塔, 黑塔}):角色腿①(大黑塔/黑塔 factions =
    银河学者)∪ 成员腿②(大黑塔 ∈ 大黑塔银河学者 core,该线 factions 全集
    = 银河学者+群攻)→ 全集两阵营(§4 清单:角色腿 + 成员腿带入大黑塔
    银河学者线 factions 全集)。"""
    assert strategy_faction_scope('黑塔纪元') == frozenset({'银河学者', '群攻'})


def test_strategy_scope_char_leg_qiongyu_qingque() -> None:
    """琼玉专家:青雀(绑 ∅ + {青雀})→ {仙舟}:青雀 factions = (仙舟,)
    且不在任何线 core/shared(成员腿零命中)→ 精确单阵营(§4 清单)。"""
    assert strategy_faction_scope('琼玉专家:青雀') == frozenset({'仙舟'})


def test_env_scope_affinity_leg_grail_invite_and_contract() -> None:
    """命运圣杯邀请/契约(faction 腿命运圣杯;同亲和表 {双王圣杯, 命运圣杯
    红A})→ 亲和腿双王圣杯线 factions 全集(命运圣杯+能量)→
    {命运圣杯, 能量}(副阵营随线带入,§2.1 例;§4 清单:邀请/契约同为
    亲和腿口径)。"""
    assert env_faction_scope('命运圣杯邀请') == frozenset({'命运圣杯', '能量'})
    assert env_faction_scope('命运圣杯契约') == frozenset({'命运圣杯', '能量'})


def test_env_scope_sampo_affinity_leg() -> None:
    """特邀专家:桑博 faction 腿空但亲和专家桑博DOT(1.0)→ 指向集 = 该线
    factions 全集 {持续伤害, 贝洛伯格}(单 faction 腿会误判通用,§4 清单)。"""
    assert env_faction_scope('特邀专家:桑博') == frozenset(
        {'持续伤害', '贝洛伯格'})


def test_env_scope_gallagher_faction_exception() -> None:
    """特邀专家:加拉赫 = faction 例外条(_ENV_FACTION_EXCEPTIONS → 击破)
    且无亲和 → {击破}(§4 清单)。"""
    assert env_faction_scope('特邀专家:加拉赫') == frozenset({'击破'})


def test_strategy_scope_membership_leg_equipfan_contains_pursuit() -> None:
    """成员腿(§4 清单):装备党绑飞霄,飞霄 ∈ 追击飞霄线 core → 该线
    factions {追击} 入集;阵营腿狼狩照常在集。"""
    scope = strategy_faction_scope('装备党')
    assert '追击' in scope
    assert '狼狩' in scope


def test_strategy_scope_multi_faction_char_expansion() -> None:
    """多阵营角色展开(§4 清单):列车同行星徽绑丹恒·饮月(factions =
    仙舟+列车同行)→ 两阵营全入集。"""
    assert {'仙舟', '列车同行'} <= strategy_faction_scope('列车同行星徽')


def test_scope_unbound_and_unregistered_empty() -> None:
    """无绑定/未注册 → 空集(通用卡,护栏不辖):打捞人才库(注册表在册、
    STRATEGY_BINDINGS 无条目);未注册策略名;未注册环境名(§4 清单)。"""
    assert '打捞人才库' in INVESTMENT_STRATEGIES
    assert strategy_faction_scope('打捞人才库') == frozenset()
    assert strategy_faction_scope('不存在的策略名') == frozenset()
    assert env_faction_scope('不存在的环境名') == frozenset()


def test_strategy_scope_unregistered_char_skipped(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """绑定角色不在 CHARACTERS → 跳过不炸(§4 清单;角色腿①收窄宁放行,
    注册表外名字不落任何线名单,成员腿同跳)。注入含未注册角色的绑定
    条目验证(表注入沿本文件 ENV_GIFTS 校验测试惯用法)。"""
    fake = dict(STRATEGY_BINDINGS)
    fake['测试卡(不存在角色)'] = (
        frozenset({'狼狩'}), frozenset({'不存在的角色X', '黑塔'}))
    monkeypatch.setattr(cw_investments, 'STRATEGY_BINDINGS', fake)
    assert strategy_faction_scope('测试卡(不存在角色)') == frozenset(
        {'狼狩', '银河学者', '群攻'})


def test_scope_queries_normalize_ocr_variants() -> None:
    """查询归一(§2.1 明文):全角冒号/分隔符 bullet 形变与规范名同值——
    持有名 OCR 形变不归一 = 查表 miss → 基准弱化漏拦。"""
    assert strategy_faction_scope('琼玉专家：青雀') == frozenset({'仙舟'})
    assert strategy_faction_scope('飞光•映月') == \
        strategy_faction_scope('飞光·映月')
    assert env_faction_scope('特邀专家：桑博') == \
        env_faction_scope('特邀专家:桑博')
