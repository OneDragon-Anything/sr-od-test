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
    ENV_POOL_REWRITE,
    ENV_REROLL_NAMES,
    INVESTMENT_ENVS,
    INVESTMENT_STRATEGIES,
    STRATEGY_BINDINGS,
    STRATEGY_GRANTS,
    GiftGrant,
    RandomCharSpec,
    StrategyPoolRewrite,
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


def test_env_reroll_names_member_validation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """追加随机环境名单成员校验(设计 §4 测试 1):成员 ∉ INVESTMENT_ENVS
    → 校验炸(防注册表改名/移除后名单静默失联——失联形态 = sim 掷骰永不
    中、live 永不申报);现役成员(蓝海)在册通过。注入 + 直调沿本文件
    ENV_GIFTS 校验测试惯用法(import 期调用,重触 = 直调校验函数)。"""
    # 现役成员:直调现值表零炸 + 全员在册
    cw_investments._validate_env_reroll_names()
    assert set(INVESTMENT_ENVS) >= ENV_REROLL_NAMES
    assert '蓝海' in ENV_REROLL_NAMES
    # 孤儿键:注入注册表外名字 → ValueError
    monkeypatch.setattr(cw_investments, 'ENV_REROLL_NAMES',
                        frozenset({'不存在的环境X'}))
    with pytest.raises(ValueError, match='ENV_REROLL_NAMES 孤儿键'):
        cw_investments._validate_env_reroll_names()


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


# ==================== 随机装备支 + 首领节点发放白名单 ====================
# (劳务派遣合同,效果原文「获得随机星徽,每次进入首领节点时,获得对应
# 羁绊的随机角色」;设计 = 该迭代 designs/T-19-laowu-paiqian-hetong.md
# §2.1-§2.3/§4.1,定稿。)


def test_equips_random_immediate_category_validation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """随机装备支类别校验(T-19 设计 §2.2 条 1-2,import 即炸语义,注入 +
    直调沿本文件惯用法):类别名 ∈ EQUIPMENTS category 词集闭集(越界 =
    采样池必空,构建期拒)。"""
    bad = dict(ENV_GIFTS)
    bad['劳务派遣合同'] = cw_investments.GiftGrant(
        equips_random_immediate=('不存在的类别',))
    monkeypatch.setattr(cw_investments, 'ENV_GIFTS', bad)
    with pytest.raises(ValueError, match='随机装备类别名'):
        cw_investments._validate_env_gifts()


def test_star_category_pool_derivation_nonempty() -> None:
    """'星徽' 类别池(T-19 设计 §2.2 条 4 独立闸 + §2.1 helper 派生性质):
    equips_by_category 现算 = 注册表 category 过滤(零硬编码第二源),
    '星徽' 池非空且逐名 category='星徽'(池规模 22 = 注释性快照,非断言值);
    直调校验器现值表零炸(含独立星徽池闸)。"""
    pool = cw_investments.equips_by_category('星徽')
    assert pool, '星徽池非空(首例登记前提)'
    from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
    assert all(EQUIPMENTS[n].category == '星徽' for n in pool)
    cw_investments._validate_env_gifts()


def test_laowu_random_equip_grant_not_empty_grant_both_tables(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """空发放集判定并入 equips_random_immediate(env/策略两表,T-19 设计
    §2.2 条 3/条 5):随机装备支 only 条目 = 合法登记形态,两表校验均不得
    炸——未并入时该登记会被「空发放集」误炸(env 侧 import 期即拦)。"""
    assert ENV_GIFTS['劳务派遣合同'].equips_random_immediate == ('星徽',)
    cw_investments._validate_env_gifts()
    # 策略侧:GiftGrant 两表共享,注入随机装备支 only 条目同样通过
    bad = dict(STRATEGY_GRANTS)
    bad['佩佩驾到'] = cw_investments.GiftGrant(
        equips_random_immediate=('星徽',))
    monkeypatch.setattr(cw_investments, 'STRATEGY_GRANTS', bad)
    cw_investments._validate_strategy_grants()


def test_laowu_not_in_env_economy() -> None:
    """互斥面 + 白名单同键(T-19 设计 §4.1):劳务派遣合同 ∈ ENV_GIFTS 且
    ∈ ENV_BOSS_GRANTS(两表同键 = 各表各腿合法形态)且 ∉ ENV_ECONOMY
    (防错装闸在册——经济域零动作,import 期互斥校验显式半边)。"""
    assert '劳务派遣合同' in ENV_GIFTS
    assert '劳务派遣合同' in cw_investments.ENV_BOSS_GRANTS
    assert '劳务派遣合同' not in ENV_ECONOMY


def test_env_boss_grants_registry_and_validation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ENV_BOSS_GRANTS 构建校验(T-19 设计 §2.3,import 即炸语义,注入 +
    直调沿 ENV_STREAK_GRANTS 测试惯用法):孤儿键 → 炸;现表默认通过且
    与 ENV_GIFTS 同键并存合法(校验器无反例拒绝)。"""
    assert frozenset({'劳务派遣合同'}) == cw_investments.ENV_BOSS_GRANTS
    cw_investments._validate_env_boss_grants()

    # 孤儿键(版本更新改名/移除后静默失联 → 构建期炸)
    bad = frozenset({'不存在环境X'})
    monkeypatch.setattr(cw_investments, 'ENV_BOSS_GRANTS', bad)
    with pytest.raises(ValueError, match='ENV_BOSS_GRANTS 孤儿键'):
        cw_investments._validate_env_boss_grants()


# ==================== 联席决策挂点结构闸(T-23)====================
# (extra_strategy_offer_node 坐标系 = (位面, 轮次) 单点两元各 1 基;
# 执行消费端 = sim JOINT_DECISION_EXTRA_SLOT 派生。)

def test_env_pool_rewrite_offer_node_gate(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ENV_POOL_REWRITE 挂点结构闸(T-23 设计 §4.2,import 即炸语义,
    注入 + 直调沿本文件惯用法):extra_strategy_offer_node 非 None 时
    位面 ∈ PLANE_NODE_TABLES 且轮次 ≤ 该位面序列长——越界 (2,9)(超
    P2 序列长 7)与位面不在表 (4,1) 均炸(登记笔误 import 期响,防 sim
    挂点比对静默恒 False);合法 (3,5) 放行(策略大师同构卡将按此登记);
    现表直调通过 = 联席决策 (2,6) 在册回归。"""
    # 现表回归:联席决策 (2,6) 在册,直调零炸
    cw_investments._validate_env_pool_rewrite()
    assert ENV_POOL_REWRITE['联席决策'].extra_strategy_offer_node == (2, 6)
    # 合法挂点放行(P3 序列长 7,3-5 在表内)
    ok = dict(ENV_POOL_REWRITE)
    ok['联席决策'] = StrategyPoolRewrite(extra_strategy_offer_node=(3, 5))
    monkeypatch.setattr(cw_investments, 'ENV_POOL_REWRITE', ok)
    cw_investments._validate_env_pool_rewrite()
    # 越界挂点:轮次 9 超 P2 序列长 7 → 炸
    bad = dict(ENV_POOL_REWRITE)
    bad['联席决策'] = StrategyPoolRewrite(extra_strategy_offer_node=(2, 9))
    monkeypatch.setattr(cw_investments, 'ENV_POOL_REWRITE', bad)
    with pytest.raises(ValueError, match='轮次超位面节点数'):
        cw_investments._validate_env_pool_rewrite()
    # 位面不在真值表(现役键 {1,2,3})→ 炸
    bad_plane = dict(ENV_POOL_REWRITE)
    bad_plane['联席决策'] = StrategyPoolRewrite(
        extra_strategy_offer_node=(4, 1))
    monkeypatch.setattr(cw_investments, 'ENV_POOL_REWRITE', bad_plane)
    with pytest.raises(ValueError, match='位面不在节点真值表'):
        cw_investments._validate_env_pool_rewrite()


# ==================== 头彩定谳接入(rewrite_settled 开关)====================

def test_toucai_entry_settled_registered() -> None:
    """头彩条目定谳锁(2026-10-16 用户裁定:覆盖面定谳 = offer 级,第 1
    次取卡机会 3 张候选全棱彩):登记 rewrite_settled=True + rewrite_picks
    ==(1,)+ 非空 pending_notes(定谳条目仍走 pending 必填闸,notes 记
    裁定时点与结论,闸字面与语义均满足)。"""
    entry = ENV_POOL_REWRITE['头彩']
    assert entry.rewrite_settled is True
    assert entry.rewrite_picks == (1,)
    assert entry.pending_notes, '定谳记录亦以非空 notes 承载'


def test_env_pool_rewrite_settled_gate(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """settled 定谳闸锁(import 即炸语义,注入 + 直调沿 T-23
    test_env_pool_rewrite_offer_node_gate 同函数惯用法):rewrite_settled
    =True 而 rewrite_quality 为空 → 炸(settled 标记只对品质改写型有意
    义,防登记错位)。现役全表过闸回归 = T-23 同函数在册断言,settled
    头彩条目随本卡落地被其自动覆盖,不重复立断言。"""
    bad = dict(ENV_POOL_REWRITE)
    bad['联席决策'] = StrategyPoolRewrite(rewrite_settled=True)
    monkeypatch.setattr(cw_investments, 'ENV_POOL_REWRITE', bad)
    with pytest.raises(ValueError, match='settled 定谳闸'):
        cw_investments._validate_env_pool_rewrite()


def test_weicai_entry_settled_registered() -> None:
    """尾彩条目定谳锁(2026-10-16 用户裁定:覆盖面定谳 = offer 级,第 3
    次取卡机会 3 张候选全棱彩):登记 rewrite_settled=True + rewrite_picks
    ==(3,)+ 非空 pending_notes(定谳记录)。至此品质覆写族 7 键全部定谳
    或结构定形,注册表无未定谳部分型实体(「未定谳部分型不接入」语义由
    合成载体锁承载,test_sim_offer.py
    test_rewrite_quality_for_pick_unsettaled_partial_stays_out)。"""
    entry = ENV_POOL_REWRITE['尾彩']
    assert entry.rewrite_settled is True
    assert entry.rewrite_picks == (3,)
    assert entry.pending_notes, '定谳记录亦以非空 notes 承载'


# ==================== 合并升星触发发放注册表(T-26 量子同频契约)====================


def test_env_merge_grants_registry_and_validation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ENV_MERGE_GRANTS 构建校验(T-26 设计 §2.1,import 即炸语义,注入 +
    直调沿 ENV_BOSS_GRANTS 测试惯用法):孤儿键/触发角色集或发放池含
    CHARACTERS 外名/空元组 → 炸(触发集漂移 = 事件永不命中,发放池漂移
    = 采出假身份混进席面,登记笔误前置可见);现表直调通过。"""
    assert cw_investments.ENV_MERGE_GRANTS == {
        '量子同频契约': (('花火', '缇宝'), ('符玄', '希儿'))}, \
        '首例登记(id 125 原文直读)'
    cw_investments._validate_env_merge_grants()

    _orig = dict(cw_investments.ENV_MERGE_GRANTS)
    _entry = (('花火',), ('符玄',))
    # 孤儿键(版本更新改名/移除后静默失联 → 构建期炸)
    bad = dict(_orig)
    bad['不存在环境X'] = _entry
    monkeypatch.setattr(cw_investments, 'ENV_MERGE_GRANTS', bad)
    with pytest.raises(ValueError, match='ENV_MERGE_GRANTS 孤儿键'):
        cw_investments._validate_env_merge_grants()
    # 触发角色集漂移(角色注册表外名)
    bad = dict(_orig)
    bad['量子同频契约'] = (('花火', '不存在的角色X'), ('符玄',))
    monkeypatch.setattr(cw_investments, 'ENV_MERGE_GRANTS', bad)
    with pytest.raises(ValueError, match='触发角色集'):
        cw_investments._validate_env_merge_grants()
    # 发放池漂移(角色注册表外名)
    bad = dict(_orig)
    bad['量子同频契约'] = (('花火',), ('符玄', '不存在的角色X'))
    monkeypatch.setattr(cw_investments, 'ENV_MERGE_GRANTS', bad)
    with pytest.raises(ValueError, match='发放池'):
        cw_investments._validate_env_merge_grants()
    # 空触发集 / 空发放池
    for label, entry in (('触发角色集', ((), ('符玄',))),
                         ('发放池', (('花火',), ()))):
        bad = dict(_orig)
        bad['量子同频契约'] = entry
        monkeypatch.setattr(cw_investments, 'ENV_MERGE_GRANTS', bad)
        with pytest.raises(ValueError, match=label):
            cw_investments._validate_env_merge_grants()


def test_merge_contract_coexists_with_estimation_tables() -> None:
    """表间并存合法(T-26 设计 §2.1 豁免声明显式半边):量子同频契约
    ∈ ENV_GIFTS(chars_conditional 辖估值域档位)且 ∈ ENV_MERGE_GRANTS
    (本表辖世界发放触发)且 ∉ ENV_ECONOMY(零金流,经济域无条目)。"""
    assert '量子同频契约' in ENV_GIFTS
    assert '量子同频契约' in cw_investments.ENV_MERGE_GRANTS
    assert '量子同频契约' not in ENV_ECONOMY


def test_env_interest_grants_registry_and_validation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ENV_INTEREST_GRANTS 构建校验(T-27 设计 §2.1/§4.1,import 即炸
    语义,注入 + 直调沿 ENV_MERGE_GRANTS 测试惯用法):孤儿键/阈值形
    (0/负/bool/非 int)/角色名形(空串)/角色名漂移(CHARACTER_ROSTER
    外——锁 data 注册表防版本改名静默失联,CHARACTERS 是 cw_pool 商店池
    域另一符号勿混用)/双源失同步(ENV_GIFTS chars_conditional 首元
    ≠ 发放名,两表同出卡面单侧改动即漂移)→ 炸;现表直调通过。"""
    assert cw_investments.ENV_INTEREST_GRANTS == {'公司契约': (40, '托帕&账账')}, \
        '首例登记(id 126 原文直读「累计获得40利息后,获得【托帕&账账】」)'
    cw_investments._validate_env_interest_grants()

    _orig = dict(cw_investments.ENV_INTEREST_GRANTS)
    # 孤儿键(版本更新改名/移除后静默失联 → 构建期炸)
    bad = dict(_orig)
    bad['不存在环境X'] = (40, '托帕&账账')
    monkeypatch.setattr(cw_investments, 'ENV_INTEREST_GRANTS', bad)
    with pytest.raises(ValueError, match='ENV_INTEREST_GRANTS 孤儿键'):
        cw_investments._validate_env_interest_grants()
    # 阈值形四态(≤0 = 条件永真使 done 守卫登记刻即触发;bool 是 int
    # 子类显式拒)
    for label, threshold in (('阈值形', 0), ('阈值形', -5),
                             ('阈值形', True), ('阈值形', '40')):
        bad = dict(_orig)
        bad['公司契约'] = (threshold, '托帕&账账')
        monkeypatch.setattr(cw_investments, 'ENV_INTEREST_GRANTS', bad)
        with pytest.raises(ValueError, match=label):
            cw_investments._validate_env_interest_grants()
    # 角色名形(空串 = 发放写出假身份)
    bad = dict(_orig)
    bad['公司契约'] = (40, '')
    monkeypatch.setattr(cw_investments, 'ENV_INTEREST_GRANTS', bad)
    with pytest.raises(ValueError, match='角色名形'):
        cw_investments._validate_env_interest_grants()
    # 角色名漂移(data 注册表外名)
    bad = dict(_orig)
    bad['公司契约'] = (40, '不存在的角色X')
    monkeypatch.setattr(cw_investments, 'ENV_INTEREST_GRANTS', bad)
    with pytest.raises(ValueError, match='角色名漂移'):
        cw_investments._validate_env_interest_grants()
    # 双源失同步(ENV_GIFTS 条件具名集首元 ≠ 本表发放角色;两形态 =
    # 估侧改 / 世界侧改,单侧改动即漂移;世界侧形态用注册表内在册他名
    # ——注册表外名会先触角色名漂移,序位即校验③先于④;发放名先复原,
    # 上形态遗留的漂移登记会抢在双源前触发③)
    monkeypatch.setattr(cw_investments, 'ENV_INTEREST_GRANTS', _orig)
    _gifts_orig = dict(ENV_GIFTS)
    bad_gifts = dict(_gifts_orig)
    bad_gifts['公司契约'] = GiftGrant(
        chars_immediate=('翡翠', '砂金'),
        chars_conditional=(('别的角色', '累计获得40利息后'),),
    )
    monkeypatch.setattr(cw_investments, 'ENV_GIFTS', bad_gifts)
    with pytest.raises(ValueError, match='双源失同步'):
        cw_investments._validate_env_interest_grants()
    bad = dict(_orig)
    bad['公司契约'] = (40, '翡翠')
    monkeypatch.setattr(cw_investments, 'ENV_GIFTS', _gifts_orig)
    monkeypatch.setattr(cw_investments, 'ENV_INTEREST_GRANTS', bad)
    with pytest.raises(ValueError, match='双源失同步'):
        cw_investments._validate_env_interest_grants()


def test_interest_contract_coexists_with_gifts_table() -> None:
    """表间并存合法(T-27 设计 §2.1 豁免声明显式半边):公司契约
    ∈ INVESTMENT_ENVS 且 ∈ ENV_GIFTS(chars_conditional 首元 = 托帕&账账,
    辖估值域档位)且 ∈ ENV_INTEREST_GRANTS(本表辖世界发放触发)且
    ∉ ENV_ECONOMY(零金流,经济域无条目)。"""
    assert '公司契约' in INVESTMENT_ENVS
    assert '公司契约' in ENV_GIFTS
    assert ENV_GIFTS['公司契约'].chars_conditional[0][0] == '托帕&账账'
    assert '公司契约' in cw_investments.ENV_INTEREST_GRANTS
    assert '公司契约' not in ENV_ECONOMY


def test_dot_contract_not_in_any_conditional_grant_table() -> None:
    """五表反向锁(T-28 设计稿 §4.2):持续伤害契约 ∈ ENV_GIFTS(
    chars_immediate = 椒丘/卡芙卡 + chars_conditional 首元 = 黑天鹅,辖
    估值域档位)且**不入五张世界发放条件登记表**——本卡建模形状 =
    猜测写+证实(计数源无世界真值生产点),非条件检查型;误补登记 =
    双引擎重复发放回归信号(数据断言非源码扫描)。"""
    assert '持续伤害契约' in INVESTMENT_ENVS
    assert ENV_GIFTS['持续伤害契约'].chars_immediate == ('椒丘', '卡芙卡')
    assert ENV_GIFTS['持续伤害契约'].chars_conditional[0][0] == '黑天鹅'
    for table_name, table in (
            ('ENV_STREAK_GRANTS', cw_investments.ENV_STREAK_GRANTS),
            ('ENV_REFRESH_GRANTS', cw_investments.ENV_REFRESH_GRANTS),
            ('ENV_BOSS_GRANTS', cw_investments.ENV_BOSS_GRANTS),
            ('ENV_MERGE_GRANTS', cw_investments.ENV_MERGE_GRANTS),
            ('ENV_INTEREST_GRANTS', cw_investments.ENV_INTEREST_GRANTS)):
        assert '持续伤害契约' not in table, \
            f'{table_name} 误登记(猜测写+证实型不入条件检查表)'
    assert '持续伤害契约' not in ENV_ECONOMY


# ============================================================ 晶矿开启触发发放登记表
# (T-29 战技点契约,设计 = 迭代 2026-09-23-invest-effects-calc designs/
# T-29-zhanjidian-qiyue.md §2.1 + §4 锁 1;注入 + 直调沿本文件校验测试
# 惯用法——import 期调用,重触 = 直调校验函数。)

_ORIG_ORE_OPEN = dict(cw_investments.ENV_ORE_OPEN_GRANTS)


def test_env_ore_open_grants_validation_raises(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """四查 import 即炸语义(T-29 设计 §2.1):①孤儿键 ②首阈值/步长
    非正 int(bool 显式拒,纯 int 判会被 True 当 1 混过)③具名角色
    ∉ CHARACTER_ROSTER ④随机羁绊池现值空(羁绊名错字 → 采样腿永远
    发不出,前置可见)。"""
    def _bad(first=20, step=10, chars=('火花',), faction='战技点',
             key='战技点契约') -> dict:
        bad = dict(_ORIG_ORE_OPEN)
        bad[key] = (first, step, chars, faction)
        return bad

    cases = [
        ('孤儿键', _bad(key='不存在的环境X'), '孤儿键'),
        ('首阈值非正', _bad(first=0), '值形'),
        ('首阈值 bool', _bad(first=True), '值形'),
        ('步长非正', _bad(step=0), '值形'),
        ('步长 bool', _bad(step=True), '值形'),
        ('具名角色漂移', _bad(chars=('不存在的角色X',)), '角色名漂移'),
        ('随机羁绊池空', _bad(faction='不存在的羁绊X'), '随机羁绊池空'),
    ]
    for _label, bad, match in cases:
        monkeypatch.setattr(cw_investments, 'ENV_ORE_OPEN_GRANTS', bad)
        with pytest.raises(ValueError, match=match):
            cw_investments._validate_env_ore_open_grants()


def test_env_ore_open_grants_current_entry_and_coexistence() -> None:
    """现役条目(T-29 设计 §2.1,id 128 卡面直读)+ 表间并存合法
    (豁免声明显式半边,沿公司契约并存测试同构):战技点契约 = (首阈值
    20, 步长 10, 具名 = 火花, 随机羁绊 = 战技点);∈ INVESTMENT_ENVS 且
    ∈ ENV_GIFTS(估值域档位并存)且 ∉ ENV_ECONOMY(零金流)且 ∉
    ENV_ORE_GRANTS(彼表 = 发放晶矿,键域无交集)。"""
    assert cw_investments.ENV_ORE_OPEN_GRANTS['战技点契约'] == \
        (20, 10, ('火花',), '战技点')
    assert '战技点契约' in INVESTMENT_ENVS
    assert '战技点契约' in ENV_GIFTS
    assert '战技点契约' not in ENV_ECONOMY
    assert '战技点契约' not in cw_investments.ENV_ORE_GRANTS


# ============================================================ 同战共现触发发放登记表
# (T-30 星核猎手契约,设计 = 迭代 2026-09-23-invest-effects-calc designs/
# T-30-xinghe-lieshou-qiyue.md §2.1 + §4 锁 1;注入 + 直调沿本文件校验测试
# 惯用法。)

_ORIG_BATTLE = dict(cw_investments.ENV_BATTLE_GRANTS)


def _battle_grant(**kw):
    """现役条目按参变体(缺省 = id 129 原文直读形态)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        EnvBattleGrant,
    )
    base = {'presence_groups': (('刃', '千冶·刃'), ('卡芙卡',),
                                ('银狼LV.999', '银狼')),
            'reward_char': '流萤', 'deploy_lock_nodes': 2}
    base.update(kw)
    return EnvBattleGrant(**base)


def _bad(**kw) -> dict:
    """星核猎手契约条目按参坏体(其余键保持现役)。"""
    bad = dict(_ORIG_BATTLE)
    bad['星核猎手契约'] = _battle_grant(**kw)
    return bad


def test_env_battle_grants_validation_raises(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """五查 import 即炸语义(T-30 设计 §2.1/§4 锁 1):①孤儿键 ②参与组形
    (空外层 = 条件永真使 done 登记刻即触发;空组 = 永不满足使发放不可达;
    参与名漂移/空串——锁 data 注册表防版本改名)③发放角色形(空串/漂移)
    ④锁期形(0/负/bool——解锁序位不后移使锁无消费面)⑤双源失同步
    (ENV_GIFTS 条件具名集首元 ≠ 本表发放角色,两表同出卡面单侧改动即
    漂移,两形态 = 估侧改/世界侧改)。"""
    bad_orphan = dict(_ORIG_BATTLE)
    bad_orphan['不存在环境X'] = _battle_grant()
    cases = [
        ('孤儿键', bad_orphan, '孤儿键'),
        ('参与组空外层', _bad(presence_groups=()), '参与组形'),
        ('参与组内空组', _bad(presence_groups=(('刃',), ())), '参与组形'),
        ('参与名漂移', _bad(presence_groups=(('刃', '不存在的角色X'),
                                             ('卡芙卡',), ('银狼',))),
         '参与名漂移'),
        ('参与名空串', _bad(presence_groups=(('',), ('卡芙卡',),
                                             ('银狼',))), '参与名形'),
        ('发放角色空串', _bad(reward_char=''), '发放角色形'),
        ('发放角色漂移', _bad(reward_char='不存在的角色X'), '发放角色漂移'),
        ('锁期零', _bad(deploy_lock_nodes=0), '锁期形'),
        ('锁期负', _bad(deploy_lock_nodes=-2), '锁期形'),
        ('锁期 bool', _bad(deploy_lock_nodes=True), '锁期形'),
    ]
    for _label, bad, match in cases:
        monkeypatch.setattr(cw_investments, 'ENV_BATTLE_GRANTS', bad)
        with pytest.raises(ValueError, match=match):
            cw_investments._validate_env_battle_grants()

    # 双源失同步两形态(沿 interest ⑤ 测试序位纪律:世界侧形态用注册表
    # 内在册他名,注册表外名会先触角色名漂移)
    from sr_od.application.currency_war.kernel.cw_investments import (
        GiftGrant as _GG,
    )
    _gifts_orig = dict(ENV_GIFTS)
    bad_gifts = dict(_gifts_orig)
    bad_gifts['星核猎手契约'] = _GG(
        chars_immediate=('卡芙卡',),
        chars_conditional=(('别的角色', '同战一役后获得'),),
    )
    monkeypatch.setattr(cw_investments, 'ENV_GIFTS', bad_gifts)
    monkeypatch.setattr(cw_investments, 'ENV_BATTLE_GRANTS', _ORIG_BATTLE)
    with pytest.raises(ValueError, match='双源失同步'):
        cw_investments._validate_env_battle_grants()
    bad = dict(_ORIG_BATTLE)
    bad['星核猎手契约'] = _battle_grant(reward_char='翡翠')
    monkeypatch.setattr(cw_investments, 'ENV_GIFTS', _gifts_orig)
    monkeypatch.setattr(cw_investments, 'ENV_BATTLE_GRANTS', bad)
    with pytest.raises(ValueError, match='双源失同步'):
        cw_investments._validate_env_battle_grants()


def test_env_battle_grants_current_entry_and_coexistence() -> None:
    """现役条目(T-30 设计 §2.1,id 129 卡面直读)+ 表间并存合法
    (豁免声明显式半边)+ 现表直调通过(构建校验在 import 期已炸过一遍,
    直调 = 变体注入后的回归锚):星核猎手契约 = AND-of-ORs 三参与组 +
    流萤 + 锁期 2;∈ INVESTMENT_ENVS 且 ∈ ENV_GIFTS(条件具名集首元 =
    流萤,双源同值)且 ∉ ENV_ECONOMY(零金流)。"""
    grant = cw_investments.ENV_BATTLE_GRANTS['星核猎手契约']
    assert grant.presence_groups == (('刃', '千冶·刃'), ('卡芙卡',),
                                     ('银狼LV.999', '银狼'))
    assert grant.reward_char == '流萤'
    assert grant.deploy_lock_nodes == 2
    cw_investments._validate_env_battle_grants()
    assert '星核猎手契约' in INVESTMENT_ENVS
    assert ENV_GIFTS['星核猎手契约'].chars_conditional[0][0] == '流萤'
    assert '星核猎手契约' not in ENV_ECONOMY


# ============================================================ 即时装备通道
# (环境确定性具名装备发放:equips_immediate;迭代
# 2026-09-23-invest-effects-calc T-31 红钻贵族)


def test_equip_immediate_drift_check_raises(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """装备名漂移(T-31 设计 §4 锁 1 ⑧):equips_immediate 含 EQUIPMENTS
    外名(武装箱系不在装备注册表)→ 构建校验炸——发放写出库存里不存在的
    名字 = 假身份混进 equips,import 期拦。"""
    bad = dict(ENV_GIFTS)
    bad['红钻贵族'] = GiftGrant(equips_immediate=('简易武装箱',))
    monkeypatch.setattr(cw_investments, 'ENV_GIFTS', bad)
    with pytest.raises(ValueError, match='装备名漂移'):
        cw_investments._validate_env_gifts()


def test_equip_item_channel_clash_raises(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """装备/道具通道同名互斥(T-31 设计 §4 锁 1 ⑨):同一 GiftGrant 内
    equips_immediate 与 items 两通道同名件 → 构建校验炸(身份串行防呆;
    现值登记 红钻/简易武装箱 异名,天然通过)。"""
    bad = dict(ENV_GIFTS)
    bad['红钻贵族'] = GiftGrant(equips_immediate=('红钻',),
                                items_immediate=('红钻',))
    monkeypatch.setattr(cw_investments, 'ENV_GIFTS', bad)
    with pytest.raises(ValueError, match='通道同名'):
        cw_investments._validate_env_gifts()


def test_equip_only_grant_not_empty_grant_both_tables(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """空发放集判定并入 equips_immediate(env/策略两表,T-31 设计 §2.2
    条 3 + 策略侧家族义务):装备腿 only 条目 = 合法登记,两表校验均不得
    误炸;全空条目照炸由既有锁承载,不重复。"""
    cw_investments._validate_env_gifts()  # 现值表(红钻贵族 = 装备+箱)直调
    bad = dict(STRATEGY_GRANTS)
    bad['佩佩驾到'] = GiftGrant(equips_immediate=('红钻',))
    monkeypatch.setattr(cw_investments, 'STRATEGY_GRANTS', bad)
    cw_investments._validate_strategy_grants()


def test_red_diamond_registry_surface() -> None:
    """登记面与身份防污染(T-31 设计 §4 锁 1/3):红钻贵族 ∈ ENV_GIFTS
    且 ∉ ENV_ECONOMY;登记形状 = 装备腿('红钻',)+ 箱腿('简易武装箱',);
    红钻 ∈ EQUIPMENTS(装备身份)且 ∉ BENCH_ITEM_NAMES,'简易武装箱' ∈
    BENCH_ITEM_NAMES(派生面只扫 items 两通道,装备不进占席词表)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIPMENTS,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        BENCH_ITEM_NAMES,
    )
    assert '红钻贵族' in ENV_GIFTS
    assert '红钻贵族' not in ENV_ECONOMY
    grant = ENV_GIFTS['红钻贵族']
    assert grant.equips_immediate == ('红钻',)
    assert grant.items_immediate == ('简易武装箱',)
    assert '红钻' in EQUIPMENTS
    assert '红钻' not in BENCH_ITEM_NAMES
    assert '简易武装箱' in BENCH_ITEM_NAMES


def test_blue_diamond_registry_surface() -> None:
    """登记面与身份防污染(T-32 设计 §4 锁 1/4):蓝钻贵族 ∈ ENV_GIFTS
    且 ∉ ENV_ECONOMY;登记形状 = 装备腿('蓝钻',)+ 箱腿('简易武装箱',);
    蓝钻 ∈ EQUIPMENTS(装备身份)且 ∉ BENCH_ITEM_NAMES,'简易武装箱' ∈
    BENCH_ITEM_NAMES(派生面只扫 items 两通道,装备不进占席词表;
    红钻贵族姊妹行同判)。import 过闸 = 模块加载即对全表现值(含本行)
    跑 _validate_env_gifts ⑧装备名/⑨通道同名/③空发放集/④∩ENV_ECONOMY。"""
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIPMENTS,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        BENCH_ITEM_NAMES,
    )
    assert '蓝钻贵族' in ENV_GIFTS
    assert '蓝钻贵族' not in ENV_ECONOMY
    grant = ENV_GIFTS['蓝钻贵族']
    assert grant.equips_immediate == ('蓝钻',)
    assert grant.items_immediate == ('简易武装箱',)
    assert '蓝钻' in EQUIPMENTS
    assert '蓝钻' not in BENCH_ITEM_NAMES
    assert '简易武装箱' in BENCH_ITEM_NAMES


# ============================================================ 环境「随机赠卡+上场锁」登记表
# (T-33 英雄登场,设计 = 迭代 2026-09-23-invest-effects-calc designs/
# T-33-yingxiong-dengchang.md §2.1 + §4 锁 1;注入 + 直调沿本文件校验测试
# 惯用法。)

_ORIG_DEPLOY_LOCK = dict(cw_investments.ENV_DEPLOY_LOCK_GRANTS)


def _deploy_lock_grant(**kw):
    """现役条目按参变体(缺省 = id 133 原文直读形态)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        EnvDeployLockGrant,
    )
    base = {'spec': RandomCharSpec(cost=5, star=2),
            'deploy_lock_nodes': 19, 'perfect_win_accel': True}
    base.update(kw)
    return EnvDeployLockGrant(**base)


def _bad_deploy_lock(**kw) -> dict:
    """英雄登场条目按参坏体(其余键保持现役)。"""
    bad = dict(_ORIG_DEPLOY_LOCK)
    bad['英雄登场'] = _deploy_lock_grant(**kw)
    return bad


def test_env_deploy_lock_grants_validation_raises(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """五查 import 即炸语义(T-33 设计 §2.1/§4 锁 1):①孤儿键 ②spec 值域
    (cost 0/6、star 0/4、type_tag 词表外——_validate_env_gifts ⑥ 同款判据,
    bool 显式拒)③规格池空(模拟注册表漂移)④锁期形(0/负/bool——
    ENV_BATTLE_GRANTS 锁期形④逐字同款)⑤双登记防呆(set ∩ ENV_GIFTS ≠ ∅
    = 赠卡双发 + 锁记录双写)。"""
    bad_orphan = dict(_ORIG_DEPLOY_LOCK)
    bad_orphan['不存在环境X'] = _deploy_lock_grant()
    bad_pool = _bad_deploy_lock(
        spec=RandomCharSpec(cost=5, star=2, type_tag='不存在的标签X'))
    cases = [
        ('孤儿键', bad_orphan, '孤儿键'),
        ('cost 0', _bad_deploy_lock(spec=RandomCharSpec(cost=0, star=2)),
         '费用档'),
        ('cost 6', _bad_deploy_lock(spec=RandomCharSpec(cost=6, star=2)),
         '费用档'),
        ('cost bool', _bad_deploy_lock(spec=RandomCharSpec(cost=True, star=2)),
         '费用档'),
        ('star 0', _bad_deploy_lock(spec=RandomCharSpec(cost=5, star=0)),
         '星级'),
        ('star 4', _bad_deploy_lock(spec=RandomCharSpec(cost=5, star=4)),
         '星级'),
        ('type_tag 词表外', bad_pool, '类型标签'),
        ('锁期零', _bad_deploy_lock(deploy_lock_nodes=0), '锁期形'),
        ('锁期负', _bad_deploy_lock(deploy_lock_nodes=-1), '锁期形'),
        ('锁期 bool', _bad_deploy_lock(deploy_lock_nodes=True), '锁期形'),
    ]
    for _label, bad, match in cases:
        monkeypatch.setattr(cw_investments, 'ENV_DEPLOY_LOCK_GRANTS', bad)
        with pytest.raises(ValueError, match=match):
            cw_investments._validate_env_deploy_lock_grants()

    # ③ 池空(模拟注册表漂移:5 费档全量桩空)
    from sr_od.application.currency_war.kernel.cw_investments import (
        random_char_pool as _rcp,
    )
    monkeypatch.setattr(cw_investments, 'ENV_DEPLOY_LOCK_GRANTS',
                        _ORIG_DEPLOY_LOCK)
    monkeypatch.setattr(cw_investments, 'random_char_pool',
                        lambda spec: [])
    try:
        with pytest.raises(ValueError, match='池空'):
            cw_investments._validate_env_deploy_lock_grants()
    finally:
        monkeypatch.setattr(cw_investments, 'random_char_pool', _rcp)

    # ⑤ 双登记防呆(英雄登场同时在两表 = 赠卡双发 + 锁记录双写)
    bad_gifts = dict(ENV_GIFTS)
    bad_gifts['英雄登场'] = GiftGrant(
        chars_random_immediate=(RandomCharSpec(cost=5, star=2),))
    monkeypatch.setattr(cw_investments, 'ENV_GIFTS', bad_gifts)
    monkeypatch.setattr(cw_investments, 'ENV_DEPLOY_LOCK_GRANTS',
                        _ORIG_DEPLOY_LOCK)
    with pytest.raises(ValueError, match='双表'):
        cw_investments._validate_env_deploy_lock_grants()


def test_env_deploy_lock_grants_current_entry_and_coexistence() -> None:
    """现役条目(T-33 设计 §2.1,id 133 卡面直读)+ 表间并存合法 + 现表
    直调通过(import 期已炸过一遍,直调 = 变体注入后的回归锚):英雄登场
    = RandomCharSpec(5,2) + 锁期 19 + 完胜加速;∈ INVESTMENT_ENVS 且
    ∉ ENV_GIFTS ∉ ENV_ECONOMY ∉ ENV_BATTLE_GRANTS(各表无本卡条目,
    单表归属)。"""
    grant = cw_investments.ENV_DEPLOY_LOCK_GRANTS['英雄登场']
    assert grant.spec == RandomCharSpec(cost=5, star=2)
    assert grant.deploy_lock_nodes == 19
    assert grant.perfect_win_accel is True
    cw_investments._validate_env_deploy_lock_grants()
    assert '英雄登场' in INVESTMENT_ENVS
    assert '英雄登场' not in ENV_GIFTS
    assert '英雄登场' not in ENV_ECONOMY
    assert '英雄登场' not in cw_investments.ENV_BATTLE_GRANTS
    # 5 费全档池非空(注册表现算,池规模作注释性快照非断言值:
    # 2026-10 时点 9 名)
    assert len(random_char_pool(grant.spec)) > 0
