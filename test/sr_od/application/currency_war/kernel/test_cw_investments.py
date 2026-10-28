"""cw_investments 随机赠卡家族载体测试(RandomCharSpec / random_char_pool /
构建校验;迭代 2026-09-23-invest-effects-calc T-10 人才引进起,随批续建)。

校验治理口径 = 用户裁定 2026-10-28:防登记笔误的值域/互斥类 import 校验
全部移除且不再新增(判据 = 只能由写表人笔误触发 vs 能被游戏版本变更独立
触发);本文件相应锁随删,存留锁只打「漂移哨」行为与登记数据性质:
- **漂移哨锁**:规格过滤池空 / 随机装备池空 / 孤儿键等版本漂移形态照炸;
- **登记数据性质**(非快照断言):各卡 ∈ ENV_GIFTS 且 ∉ ENV_ECONOMY、
  池派生 = 注册表现算双射(空 type_tag = 费用档全员旁路、非空 = 含标签
  过滤);池规模作注释性快照非断言值。
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
    BENCH_ITEM_NAMES,
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


def test_talent_import_not_in_env_economy() -> None:
    """互斥面(T-10 设计 §4 测试 1 末项):人才引进 ∈ ENV_GIFTS 且 ∉
    ENV_ECONOMY——import 期互斥校验半边的显式断言。"""
    assert '人才引进' in ENV_GIFTS
    assert '人才引进' not in ENV_ECONOMY


def test_zhanli_tisheng_registration_and_typed_pool() -> None:
    """战力提升登记不变量(T-36 设计 §4 锁 1/2):∈ ENV_GIFTS 且 ∉
    ENV_ECONOMY(import 期互斥校验半边显式断言);登记规格 = 卡面直读
    (1 费/2★/类型标签「输出」);规格过滤池 = 注册表现算双射——每名
    1 费且 char_type 含「输出」标签(多标签计入,用户裁定 2026-10-21),
    池名 ⊆ 注册表。池规模 = 注释性快照(2026-10 时点 12 名),非断言值。"""
    assert '战力提升' in ENV_GIFTS
    assert '战力提升' not in ENV_ECONOMY
    spec = ENV_GIFTS['战力提升'].chars_random_immediate[0]
    assert spec == RandomCharSpec(cost=1, star=2, type_tag='输出')
    expected = {c.name for c in chars_by_cost(1)
                if '输出' in c.char_type.split('、')}
    assert set(random_char_pool(spec)) == expected, \
        '规格过滤池 = 费用档 × 类型含标签 双射(注册表现算)'
    assert set(random_char_pool(spec)) <= CHARACTER_ROSTER


def test_zhanli_biaosheng_registration_and_full_cost_pool() -> None:
    """战力飙升登记不变量(T-37 设计 §4 锁 1/2):∈ ENV_GIFTS 且 ∉
    ENV_ECONOMY(import 期互斥校验半边显式断言);登记规格 = 卡面直读
    (2 费/2★/无类型词 → type_tag 空);池 = 2 费全档注册表现算双射——
    池名 ⊆ 注册表;爻光费用勘误 2→1(注册表在册)自动不入池(勘误件
    防呆断言);池规模 = 注释性快照(2026-10 时点 15 名),非断言值。"""
    assert '战力飙升' in ENV_GIFTS
    assert '战力飙升' not in ENV_ECONOMY
    spec = ENV_GIFTS['战力飙升'].chars_random_immediate[0]
    assert spec == RandomCharSpec(cost=2, star=2)
    pool = set(random_char_pool(spec))
    assert pool == {c.name for c in chars_by_cost(2)}, \
        '无类型词 → 池 = 费用档全档(注册表现算)'
    assert pool <= CHARACTER_ROSTER
    assert '爻光' not in pool, '爻光费用勘误 2→1,不入 2 费池(勘误件防呆)'


def test_talent_reserve_registration_and_replace_flag() -> None:
    """人才储备登记不变量(T-43 设计 §4 锁 1):∈ ENV_GIFTS 且 ∉
    ENV_ECONOMY(import 期互斥校验半边显式断言);登记 = 三元素
    RandomCharSpec(3 费/1★ 先验)× 3 + replaces_opening_supply=True
    (开局替换首例);池 = 3 费全档注册表现算双射(无类型词),
    池名 ⊆ 注册表;池规模 = 注释性快照(2026-10 时点 14 名),非断言值。"""
    assert '人才储备' in ENV_GIFTS
    assert '人才储备' not in ENV_ECONOMY
    grant = ENV_GIFTS['人才储备']
    assert grant.replaces_opening_supply is True
    assert grant.chars_random_immediate == (
        RandomCharSpec(cost=3, star=1),
        RandomCharSpec(cost=3, star=1),
        RandomCharSpec(cost=3, star=1),
    )
    pool = set(random_char_pool(RandomCharSpec(cost=3, star=1)))
    assert pool == {c.name for c in chars_by_cost(3)}, \
        '无类型词 → 池 = 费用档全档(注册表现算)'
    assert pool <= CHARACTER_ROSTER


def test_replaces_opening_supply_unique_to_talent_reserve() -> None:
    """开局替换标记唯一性(T-43 设计 §4 锁 8 登记形态):replace 标记
    现值全表仅人才储备一卡,其余全部条目缺省 False——「前置支零行为差」
    的登记面前提钉死,防并行批误开。"""
    flagged = [n for n, g in ENV_GIFTS.items() if g.replaces_opening_supply]
    assert flagged == ['人才储备']


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
    """池派生性质测试(T-10 设计 §4 测试 2,注册表现算对照):空 type_tag
    = 费用档全员旁路,唯开拓者双形态按角色位合并收口(池 = 4 费档剔除
    '开拓者·记忆'——牌库中开拓者占单一角色位,采样即发放名恒欢愉,
    economy.md §8);非空 type_tag = char_type 含标签过滤(子集 + 逐名含
    标签);池名 ⊆ 注册表。池规模 = 注释性快照(2026-10 时点合并后
    13 名),非断言值(注册表随版本扩充)。"""
    pool_all = random_char_pool(RandomCharSpec(cost=4, star=1))
    assert set(pool_all) == {c.name for c in chars_by_cost(4)} \
        - {'开拓者·记忆'}, \
        'type_tag 空 = 全档旁路(开拓者双形态按角色位合并剔除键侧)'
    assert set(pool_all) <= CHARACTER_ROSTER
    pool_tag = random_char_pool(RandomCharSpec(cost=4, star=1,
                                               type_tag='输出'))
    assert pool_tag, '过滤池非空(注册表现值)'
    assert set(pool_tag) <= set(pool_all), '过滤池 ⊆ 全档'
    for name in pool_tag:
        assert '输出' in CHARACTERS[name].char_type.split('、')


# ==================== 阵容指向集(投资选卡阵容冲突护栏 §2.1)====================
# 判据 = changes/2026-10-17-invest-direction-guard/design.md §2.1 三条分支派生
# (faction/亲和/成员),期望值全部注册表现算(非快照),与设计 §4 测试
# 清单期望逐条对齐。

def test_strategy_scope_defining_card_heita_epoch() -> None:
    """黑塔纪元(绑 ∅ + {大黑塔, 黑塔}):角色入账分支①(大黑塔/黑塔 factions =
    银河学者)∪ 成员分支②(大黑塔 ∈ 大黑塔银河学者 core,该线 factions 全集
    = 银河学者+群攻)→ 全集两阵营(§4 清单:角色入账分支 + 成员分支带入大黑塔
    银河学者线 factions 全集)。"""
    assert strategy_faction_scope('黑塔纪元') == frozenset({'银河学者', '群攻'})


def test_strategy_scope_char_leg_qiongyu_qingque() -> None:
    """琼玉专家:青雀(绑 ∅ + {青雀})→ {仙舟}:青雀 factions = (仙舟,)
    且不在任何线 core/shared(成员分支零命中)→ 精确单阵营(§4 清单)。"""
    assert strategy_faction_scope('琼玉专家:青雀') == frozenset({'仙舟'})


def test_env_scope_affinity_leg_grail_invite_and_contract() -> None:
    """命运圣杯邀请/契约(faction 分支命运圣杯;同亲和表 {双王圣杯, 命运圣杯
    红A})→ 亲和分支双王圣杯线 factions 全集(命运圣杯+能量)→
    {命运圣杯, 能量}(副阵营随线带入,§2.1 例;§4 清单:邀请/契约同为
    亲和分支口径)。"""
    assert env_faction_scope('命运圣杯邀请') == frozenset({'命运圣杯', '能量'})
    assert env_faction_scope('命运圣杯契约') == frozenset({'命运圣杯', '能量'})


def test_env_scope_sampo_affinity_branch() -> None:
    """特邀专家:桑博 faction 分支空但亲和专家桑博DOT(1.0)→ 指向集 = 该线
    factions 全集 {持续伤害, 贝洛伯格}(单 faction 分支会误判通用,§4 清单)。"""
    assert env_faction_scope('特邀专家:桑博') == frozenset(
        {'持续伤害', '贝洛伯格'})


def test_env_scope_gallagher_faction_exception() -> None:
    """特邀专家:加拉赫 = faction 例外条(_ENV_FACTION_EXCEPTIONS → 击破)
    且无亲和 → {击破}(§4 清单)。"""
    assert env_faction_scope('特邀专家:加拉赫') == frozenset({'击破'})


def test_strategy_scope_membership_leg_equipfan_contains_pursuit() -> None:
    """成员分支(§4 清单):装备党绑飞霄,飞霄 ∈ 追击飞霄线 core → 该线
    factions {追击} 入集;阵营分支狼狩照常在集。"""
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
    """绑定角色不在 CHARACTERS → 跳过不炸(§4 清单;角色入账分支①收窄宁放行,
    注册表外名字不落任何线名单,成员分支同跳)。注入含未注册角色的绑定
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


def test_equips_random_immediate_pool_empty_raises(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """随机装备支池空哨(T-19 设计 §2.2 条 1-2 现行形态,2026-10-28 治理
    后类别闭集并入池空单一哨;import 即炸语义,注入 + 直调沿本文件惯用法):
    类别名错字/版本改名都表现为过滤池空 → 构建期拒。"""
    bad = dict(ENV_GIFTS)
    bad['劳务派遣合同'] = cw_investments.GiftGrant(
        equips_random_immediate=('不存在的类别',))
    monkeypatch.setattr(cw_investments, 'ENV_GIFTS', bad)
    with pytest.raises(ValueError, match='随机装备池空'):
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


def test_laowu_registry_surface() -> None:
    """登记面 + 白名单同键(T-19 设计 §4.1,2026-10-28 治理后形态):
    劳务派遣合同 ∈ ENV_GIFTS 且 ∈ ENV_BOSS_GRANTS(两表同键 = 各表各
    分支合法形态)且 ∉ ENV_ECONOMY(经济域零动作);登记形状 = 随机装备
    支 only(``('星徽',)``)。"""
    assert '劳务派遣合同' in ENV_GIFTS
    assert '劳务派遣合同' in cw_investments.ENV_BOSS_GRANTS
    assert '劳务派遣合同' not in ENV_ECONOMY
    assert ENV_GIFTS['劳务派遣合同'].equips_random_immediate == ('星徽',)


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
    ==(1,)+ 非空 pending_notes(notes 记裁定时点与结论)。"""
    entry = ENV_POOL_REWRITE['头彩']
    assert entry.rewrite_settled is True
    assert entry.rewrite_picks == (1,)
    assert entry.pending_notes, '定谳记录亦以非空 notes 承载'


def test_weicai_entry_settled_registered() -> None:
    """尾彩条目定谳锁(2026-10-16 用户裁定:覆盖面定谳 = offer 级,第 3
    次取卡机会 3 张候选全棱彩):登记 rewrite_settled=True + rewrite_picks
    ==(3,)+ 非空 pending_notes(定谳记录)。至此品质覆写族 7 键全部定谳
    或结构定形,注册表无未定谳部分型实体(「未定谳部分型不接入」语义由
    合成载体锁承载,test_sim_offer.py
    test_rewrite_slot_qualities_unsettaled_partial_stays_out)。"""
    entry = ENV_POOL_REWRITE['尾彩']
    assert entry.rewrite_settled is True
    assert entry.rewrite_picks == (3,)
    assert entry.pending_notes, '定谳记录亦以非空 notes 承载'


# ==================== 银·金·彩槽位向量定谳接入(2026-10-19 用户裁定批)====================

def test_yinjincai_entry_slot_qualities_registered() -> None:
    """银·金·彩条目定谳锁(2026-10-19 用户裁定:卡面直读即真值 = 左银
    中金右彩,旧「实测 offer 金重仓」观察记录同裁定作废):登记
    slot_qualities = ('银','金','棱彩')(坐标系 = 投资界面卡槽物理排位
    左→右 0..2)+ offer_structure 结构标记 + extra_pick_refreshes = 2
    (sim 策略屏刷新呈现与世界分支消费端)+ rewrite_quality 空(槽位向量型
    与品质改写型互斥)+ 非空 pending_notes(定谳记录)。"""
    entry = ENV_POOL_REWRITE['银·金·彩']
    assert entry.slot_qualities == ('银', '金', '棱彩')
    assert entry.offer_structure == 'silver_gold_prism_slots'
    assert entry.extra_pick_refreshes == 2
    assert entry.rewrite_quality == ''
    assert entry.rewrite_picks == ()
    assert entry.pending_notes, '定谳记录亦以非空 notes 承载'
    cw_investments._validate_env_pool_rewrite()


def test_env_pool_rewrite_slot_qualities_gates(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """槽位品质词集哨锁(import 即炸语义,注入 + 直调沿本文件惯用法;
    2026-10-28 治理后形态:同有同无/长度恒 3/双型互斥属防登记笔误类,
    校验随删——词集哨留,错字与版本增删品质都表现为词集外)。现表直调
    通过 = 银·金·彩在册回归。"""
    cw_investments._validate_env_pool_rewrite()
    # 品质不在词集 → 炸
    bad_vocab = dict(ENV_POOL_REWRITE)
    bad_vocab['银·金·彩'] = StrategyPoolRewrite(
        offer_structure='silver_gold_prism_slots',
        slot_qualities=('银', '金', '彩虹'), extra_pick_refreshes=2,
        pending_notes='x')
    monkeypatch.setattr(cw_investments, 'ENV_POOL_REWRITE', bad_vocab)
    with pytest.raises(ValueError, match='槽位品质漂移'):
        cw_investments._validate_env_pool_rewrite()


# ==================== 合并升星触发发放注册表(T-26 量子同频契约)====================


def test_env_merge_grants_registry_and_validation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ENV_MERGE_GRANTS 构建校验(T-26 设计 §2.1,import 即炸语义,注入 +
    直调沿 ENV_BOSS_GRANTS 测试惯用法;2026-10-28 治理后只留漂移哨):
    孤儿键/触发角色集或发放池含 CHARACTERS 外名 → 炸;空元组值形随治理
    删。现表直调通过。"""
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
    语义,注入 + 直调沿 ENV_MERGE_GRANTS 测试惯用法;2026-10-28 治理后
    只留漂移哨):孤儿键/角色名漂移(CHARACTER_ROSTER 外——版本改名
    静默失联即红)/双源失同步随治理删。现表直调通过。"""
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
    # 角色名漂移(data 注册表外名)
    bad = dict(_orig)
    bad['公司契约'] = (40, '不存在的角色X')
    monkeypatch.setattr(cw_investments, 'ENV_INTEREST_GRANTS', bad)
    with pytest.raises(ValueError, match='角色名漂移'):
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
    """三查 import 即炸语义(T-29 设计 §2.1;2026-10-28 治理后只留漂移
    哨,值形随删):①孤儿键 ②具名角色 ∉ CHARACTER_ROSTER ③随机羁绊池
    现值空(羁绊名错字 → 采样分支永远发不出)。"""
    def _bad(first=20, step=10, chars=('火花',), faction='战技点',
             key='战技点契约') -> dict:
        bad = dict(_ORIG_ORE_OPEN)
        bad[key] = (first, step, chars, faction)
        return bad

    cases = [
        ('孤儿键', _bad(key='不存在的环境X'), '孤儿键'),
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
    """三查 import 即炸语义(T-30 设计 §2.1/§4 锁 1;2026-10-28 治理后
    只留漂移哨,组形/名形/锁期形/双源随删):①孤儿键 ②参与名漂移
    ③发放角色漂移。"""
    bad_orphan = dict(_ORIG_BATTLE)
    bad_orphan['不存在环境X'] = _battle_grant()
    cases = [
        ('孤儿键', bad_orphan, '孤儿键'),
        ('参与名漂移', _bad(presence_groups=(('刃', '不存在的角色X'),
                                             ('卡芙卡',), ('银狼',))),
         '参与名漂移'),
        ('发放角色漂移', _bad(reward_char='不存在的角色X'), '发放角色漂移'),
    ]
    for _label, bad, match in cases:
        monkeypatch.setattr(cw_investments, 'ENV_BATTLE_GRANTS', bad)
        with pytest.raises(ValueError, match=match):
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


def test_red_diamond_registry_surface() -> None:
    """登记面与身份防污染(T-31 设计 §4 锁 1/3):红钻贵族 ∈ ENV_GIFTS
    且 ∉ ENV_ECONOMY;登记形状 = 装备入账分支('红钻',)+ 开箱分支('简易武装箱',);
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
    且 ∉ ENV_ECONOMY;登记形状 = 装备入账分支('蓝钻',)+ 开箱分支('简易武装箱',);
    蓝钻 ∈ EQUIPMENTS(装备身份)且 ∉ BENCH_ITEM_NAMES,'简易武装箱' ∈
    BENCH_ITEM_NAMES(派生面只扫 items 两通道,装备不进占席词表;
    红钻贵族姊妹行同判)。"""
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


def test_lieche_invite_registry_surface() -> None:
    """登记面(T-63 设计 §4 锁 1,2026-10-28 治理后形态):列车同行邀请
    ∈ ENV_GIFTS 且 ∉ ENV_ECONOMY;登记形状 = 具名装备单通道
    ``equips_immediate=('列车同行星徽',)``,角色/道具/替换旗全空(装备
    only = 邀请族「获得一个【X星徽】」的唯一发放形态);星徽 ∈ EQUIPMENTS
    (装备身份)且 ∉ BENCH_ITEM_NAMES(派生面只扫 items 两通道,装备不进
    占席词表;红钻贵族姊妹行同判)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIPMENTS,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        BENCH_ITEM_NAMES,
    )
    assert '列车同行邀请' in ENV_GIFTS
    assert '列车同行邀请' not in ENV_ECONOMY
    grant = ENV_GIFTS['列车同行邀请']
    assert grant.equips_immediate == ('列车同行星徽',)
    assert not grant.chars_immediate
    assert not grant.items_immediate
    assert grant.replaces_opening_supply is False
    assert '列车同行星徽' in EQUIPMENTS
    assert '列车同行星徽' not in BENCH_ITEM_NAMES


def test_yinhe_invite_registry_surface() -> None:
    """登记面(T-64 设计 §4 锁 1+2,治理后形态):银河学者邀请 ∈ ENV_GIFTS
    且 ∉ ENV_ECONOMY(∩ 断言 = T-63 治理后唯一防线,沿 T-62 批先例保留);
    登记形状 = 具名装备单通道 ``equips_immediate=('银河学者星徽',)``,
    角色/道具/替换旗全空(装备 only = 邀请族「获得一个【X星徽】」的唯一
    发放形态);星徽 ∈ EQUIPMENTS(装备身份;装备名漂移哨同判据)且 ∉
    BENCH_ITEM_NAMES(装备不进占席词表;列车同行邀请姊妹行同判)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIPMENTS,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        BENCH_ITEM_NAMES,
    )
    assert '银河学者邀请' in ENV_GIFTS
    assert '银河学者邀请' not in ENV_ECONOMY
    grant = ENV_GIFTS['银河学者邀请']
    assert grant.equips_immediate == ('银河学者星徽',)
    assert not grant.chars_immediate
    assert not grant.items_immediate
    assert grant.replaces_opening_supply is False
    assert '银河学者星徽' in EQUIPMENTS
    assert '银河学者星徽' not in BENCH_ITEM_NAMES


def test_beluoboge_invite_registry_surface() -> None:
    """登记面(T-65 设计 §4 锁 1+2,治理后形态):贝洛伯格邀请 ∈ ENV_GIFTS
    且 ∉ ENV_ECONOMY(∩ 断言 = T-63 治理后唯一防线,沿 T-62 批先例保留);
    登记形状 = 具名装备单通道 ``equips_immediate=('贝洛伯格星徽',)``,
    角色/道具/替换旗全空(装备 only = 邀请族「获得一个【X星徽】」的唯一
    发放形态);星徽 ∈ EQUIPMENTS(装备身份;装备名漂移哨同判据)且 ∉
    BENCH_ITEM_NAMES(装备不进占席词表;银河学者邀请姊妹行同判)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIPMENTS,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        BENCH_ITEM_NAMES,
    )
    assert '贝洛伯格邀请' in ENV_GIFTS
    assert '贝洛伯格邀请' not in ENV_ECONOMY
    grant = ENV_GIFTS['贝洛伯格邀请']
    assert grant.equips_immediate == ('贝洛伯格星徽',)
    assert not grant.chars_immediate
    assert not grant.items_immediate
    assert grant.replaces_opening_supply is False
    assert '贝洛伯格星徽' in EQUIPMENTS
    assert '贝洛伯格星徽' not in BENCH_ITEM_NAMES


def test_xingjian_lvren_invite_registry_surface() -> None:
    """登记面(T-66 设计 §4 锁 1+2,治理后形态):星间旅人邀请 ∈ ENV_GIFTS
    且 ∉ ENV_ECONOMY(∩ 断言 = T-63 治理后唯一防线,沿 T-62 批先例保留);
    登记形状 = 具名装备单通道 ``equips_immediate=('星间旅人星徽',)``,
    角色/道具/替换旗全空(装备 only = 邀请族「获得一个【X星徽】」的唯一
    发放形态);星徽 ∈ EQUIPMENTS(装备身份;装备名漂移哨同判据)且 ∉
    BENCH_ITEM_NAMES(装备不进占席词表;贝洛伯格邀请姊妹行同判)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIPMENTS,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        BENCH_ITEM_NAMES,
    )
    assert '星间旅人邀请' in ENV_GIFTS
    assert '星间旅人邀请' not in ENV_ECONOMY
    grant = ENV_GIFTS['星间旅人邀请']
    assert grant.equips_immediate == ('星间旅人星徽',)
    assert not grant.chars_immediate
    assert not grant.items_immediate
    assert grant.replaces_opening_supply is False
    assert '星间旅人星徽' in EQUIPMENTS
    assert '星间旅人星徽' not in BENCH_ITEM_NAMES


def test_xianzhou_invite_registry_surface() -> None:
    """登记面(T-67 设计 §4 锁 1+2,治理后形态):仙舟邀请 ∈ ENV_GIFTS
    且 ∉ ENV_ECONOMY(∩ 断言 = T-63 治理后唯一防线,沿 T-62 批先例保留);
    登记形状 = 具名装备单通道 ``equips_immediate=('仙舟星徽',)``,
    角色/道具/替换旗全空(装备 only = 邀请族「获得一个【X星徽】」的唯一
    发放形态);星徽 ∈ EQUIPMENTS(装备身份;装备名漂移哨同判据)且 ∉
    BENCH_ITEM_NAMES(装备不进占席词表;星间旅人邀请姊妹行同判)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIPMENTS,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        BENCH_ITEM_NAMES,
    )
    assert '仙舟邀请' in ENV_GIFTS
    assert '仙舟邀请' not in ENV_ECONOMY
    grant = ENV_GIFTS['仙舟邀请']
    assert grant.equips_immediate == ('仙舟星徽',)
    assert not grant.chars_immediate
    assert not grant.items_immediate
    assert grant.replaces_opening_supply is False
    assert '仙舟星徽' in EQUIPMENTS
    assert '仙舟星徽' not in BENCH_ITEM_NAMES


def test_langshou_invite_registry_surface() -> None:
    """登记面(T-68 设计 §4 锁 1+2,治理后形态):狼狩邀请 ∈ ENV_GIFTS
    且 ∉ ENV_ECONOMY(∩ 断言 = T-63 治理后唯一防线,沿 T-62 批先例保留);
    登记形状 = 具名装备单通道 ``equips_immediate=('狼狩星徽',)``,
    角色/道具/替换旗全空(装备 only = 邀请族「获得一个【X星徽】」的唯一
    发放形态);星徽 ∈ EQUIPMENTS(装备身份;装备名漂移哨同判据)且 ∉
    BENCH_ITEM_NAMES(装备不进占席词表;仙舟邀请姊妹行同判)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIPMENTS,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        BENCH_ITEM_NAMES,
    )
    assert '狼狩邀请' in ENV_GIFTS
    assert '狼狩邀请' not in ENV_ECONOMY
    grant = ENV_GIFTS['狼狩邀请']
    assert grant.equips_immediate == ('狼狩星徽',)
    assert not grant.chars_immediate
    assert not grant.items_immediate
    assert grant.replaces_opening_supply is False
    assert '狼狩星徽' in EQUIPMENTS
    assert '狼狩星徽' not in BENCH_ITEM_NAMES


def test_shenghui_zhixing_invite_registry_surface() -> None:
    """登记面(T-69 设计 §4 锁 1+2,治理后形态):盛会之星邀请 ∈ ENV_GIFTS
    且 ∉ ENV_ECONOMY(∩ 断言 = T-63 治理后唯一防线,沿 T-62 批先例保留);
    登记形状 = 具名装备单通道 ``equips_immediate=('盛会之星星徽',)``,
    角色/道具/替换旗全空(装备 only = 邀请族「获得一个【X星徽】」的唯一
    发放形态);星徽 ∈ EQUIPMENTS(装备身份;装备名漂移哨同判据)且 ∉
    BENCH_ITEM_NAMES(装备不进占席词表;狼狩邀请姊妹行同判)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIPMENTS,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        BENCH_ITEM_NAMES,
    )
    assert '盛会之星邀请' in ENV_GIFTS
    assert '盛会之星邀请' not in ENV_ECONOMY
    grant = ENV_GIFTS['盛会之星邀请']
    assert grant.equips_immediate == ('盛会之星星徽',)
    assert not grant.chars_immediate
    assert not grant.items_immediate
    assert grant.replaces_opening_supply is False
    assert '盛会之星星徽' in EQUIPMENTS
    assert '盛会之星星徽' not in BENCH_ITEM_NAMES


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
    """两查 import 即炸语义(T-33 设计 §2.1/§4 锁 1;2026-10-28 治理后
    只留漂移哨,锁期形/双登记防呆随删):①孤儿键 ②规格池空(模拟注册表
    漂移)。"""
    bad_orphan = dict(_ORIG_DEPLOY_LOCK)
    bad_orphan['不存在环境X'] = _deploy_lock_grant()
    cases = [
        ('孤儿键', bad_orphan, '孤儿键'),
    ]
    for _label, bad, match in cases:
        monkeypatch.setattr(cw_investments, 'ENV_DEPLOY_LOCK_GRANTS', bad)
        with pytest.raises(ValueError, match=match):
            cw_investments._validate_env_deploy_lock_grants()

    # ② 池空(模拟注册表漂移:5 费档全量桩空)
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


# ============================================================ 环境「战利品区
# 倒计时件+节点倒计时开盒」登记表(T-34 命运礼物,设计 = 迭代
# 2026-09-23-invest-effects-calc designs/T-34-mingyun-liwu.md §2.1 +
# §4 锁 1/锁 10 词表半边;注入 + 直调沿 deploy_lock 校验测试惯用法。)

_ORIG_DELAYED = dict(cw_investments.ENV_DELAYED_ITEM_GRANTS)


def _delayed_grant(**kw):
    """现役条目按参变体(缺省 = id 134 原文直读形态)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        EnvDelayedItemGrant,
    )
    base = {'item': '惊喜盒', 'open_delay_nodes': 12,
            'perfect_win_accel': True}
    base.update(kw)
    return EnvDelayedItemGrant(**base)


def _bad_delayed(**kw) -> dict:
    """命运礼物条目按参坏体(其余键保持现役)。"""
    bad = dict(_ORIG_DELAYED)
    bad['命运礼物'] = _delayed_grant(**kw)
    return bad


def test_env_delayed_item_grants_validation_raises(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """孤儿键 import 即炸语义(T-34 设计 §2.1/§4 锁 1;2026-10-28 治理后
    只留漂移哨,件名形/倒计时形/双登记/加速旗形随删)。"""
    bad_orphan = dict(_ORIG_DELAYED)
    bad_orphan['不存在环境X'] = _delayed_grant()
    monkeypatch.setattr(cw_investments, 'ENV_DELAYED_ITEM_GRANTS', bad_orphan)
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_env_delayed_item_grants()


def test_env_delayed_item_grants_current_entry_and_wordlist_untouched(
        ) -> None:
    """现役条目(T-34 设计 §2.1,id 134 卡面直读)+ 单表归属 + 词表零扩
    (T-34 设计 §4 锁 10 反向锁:惊喜盒 = 战利品区浮动件非占席,若实现批
    按 v1 占席惯性把件名加进 BENCH_ITEM_NAMES 派生词表,此断言红);
    现表直调通过(import 期已炸过一遍,直调 = 变体注入后的回归锚)。"""
    grant = cw_investments.ENV_DELAYED_ITEM_GRANTS['命运礼物']
    assert grant.item == '惊喜盒'
    assert grant.open_delay_nodes == 12
    assert grant.perfect_win_accel is True
    cw_investments._validate_env_delayed_item_grants()
    assert '命运礼物' in INVESTMENT_ENVS
    assert '命运礼物' not in ENV_GIFTS
    assert '命运礼物' not in cw_investments.ENV_DEPLOY_LOCK_GRANTS
    assert '惊喜盒' not in BENCH_ITEM_NAMES, \
        '倒计时件非占席,禁进占席道具词表(战利品区件锁)'
    assert '惊喜盒' not in CHARACTER_ROSTER, \
        '道具/角色域天然无交集(登记面不变量)'


def test_expert_set_matches_advisor_grant_char_union() -> None:
    """专家名单 ↔ advisor 解锁卡发放角色并集对拍(economy.md §1:专家顾问
    初始不参与普通商店招募,经投资环境/投资策略等通道解锁后本局入池——
    不变量「每个专家都有解锁卡、每张 advisor 卡的目标都是专家」;2026-10-24
    用户裁定按测试规范落对拍,替代 import 期对拍闸)。任一侧版本漂移即红:
    新专家角色入册而无解锁卡 / advisor 条目引用非专家名或漏发已置位角色,
    均不再静默。"""
    grant_chars = {
        name
        for grant in (*ENV_GIFTS.values(), *STRATEGY_GRANTS.values())
        if grant.advisor
        for name in (*grant.chars_immediate,
                     *(c[0] for c in grant.chars_conditional))
        # chars_conditional 元素形状 = (角色名, 条件描述) 二元组
        # (登记表禁第二形状),取 [0] 即发放角色名。
    }
    experts = {n for n, ch in CHARACTERS.items() if ch.is_expert}
    assert grant_chars == experts, \
        (f'专家名单与 advisor 解锁卡并集失配:'
         f'仅名单有={sorted(experts - grant_chars)},'
         f'仅解锁卡有={sorted(grant_chars - experts)}')
