"""test_cw_investment 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- investments: test_cw_investments.py
- w162_invest_inject: test_cw_w162_invest_inject.py
- test_fortune_picker: test_fortune_picker.py
- test_invest_strategy_recognizer: test_invest_strategy_recognizer.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations

# ==================== investments ====================
from sr_od.application.currency_war.kernel.cw_comps import ENV_FACTION_MAP
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_ENVS,
    INVESTMENT_STRATEGIES,
    InvestmentEnv,
    env_faction,
    envs_boosting_faction,
    get_env,
    is_known_env,
)


def test_concept_stocks_have_faction() -> None:
    """概念股都带 faction(送该阵营角色+刷新率);昼之半神概念股→昼之半神。"""
    昼 = get_env("昼之半神概念股")
    assert isinstance(昼, InvestmentEnv)
    assert 昼.category == "概念股"
    assert 昼.faction == "昼之半神"
    # 所有概念股都有 faction
    for name, e in INVESTMENT_ENVS.items():
        if e.category == "概念股":
            assert e.faction, f"{name} 概念股应有 faction"


def test_env_faction_helper() -> None:
    """env_faction 查询;未知名→''。"""
    assert env_faction("追击概念股") == "追击"
    assert env_faction("仙舟邀请") == "仙舟"
    assert env_faction("不存在环境") == ""


def test_envs_boosting_faction() -> None:
    """加成某阵营的环境:仙舟 → 仙舟概念股 + 仙舟邀请。"""
    boost = envs_boosting_faction("仙舟")
    assert "仙舟概念股" in boost
    assert "仙舟邀请" in boost


def test_env_faction_map_derived() -> None:
    """cw_comps.ENV_FACTION_MAP 从 INVESTMENT_ENVS 派生(单一真相源,非硬编码)。"""
    # 派生值与注册表一致
    assert ENV_FACTION_MAP["昼之半神概念股"] == ["昼之半神"]
    assert ENV_FACTION_MAP["追击邀请"] == ["追击"]
    # 派生覆盖全部有 faction 的环境(概念股+邀请,不只旧的 5 个硬编码)
    assert len(ENV_FACTION_MAP) > 20, "派生 map 覆盖全部概念股+邀请(非旧 5 个)"


def test_strategies_t0_present() -> None:
    """T0 投资策略在注册表(高效决策/采购专员等)。"""
    assert "高效决策" in INVESTMENT_STRATEGIES
    assert "采购专员·彩" in INVESTMENT_STRATEGIES
    assert INVESTMENT_STRATEGIES["高效决策"].rarity == "棱彩"


def test_d68_full_registry_categories() -> None:
    """D-68:注册表全量,7 类齐全(概念股/邀请/契约/时代/经济/规则/专家)。"""
    cats = {e.category for e in INVESTMENT_ENVS.values()}
    assert cats == {"概念股", "邀请", "契约", "时代", "经济", "规则", "专家"}
    # 全量规模(36 → 远超;数据银行 83 总,本表收全部有名)
    assert len(INVESTMENT_ENVS) > 70, f"全量注册表应 >70,实际 {len(INVESTMENT_ENVS)}"


def test_d68_new_envs_present() -> None:
    """D-68:数据银行新发现的 4 个环境在注册表(原 doc 缺)。命运圣杯 = Fate 联动阵营。"""
    for name in ("红钻贵族", "蓝钻贵族", "命运圣杯邀请", "命运圣杯契约"):
        assert name in INVESTMENT_ENVS, f"{name} 应在注册表(D-68 新增)"
    # 命运圣杯邀请/契约带 faction(Fate 联动阵营)
    assert env_faction("命运圣杯邀请") == "命运圣杯"
    assert env_faction("命运圣杯契约") == "命运圣杯"
    # 战技点概念股实存(D-36 误标"未单抓",D-68 数据银行确认存在)
    战技 = get_env("战技点概念股")
    assert isinstance(战技, InvestmentEnv) and 战技.faction == "战技点"


def test_d68_nonexistent_concept_stocks_removed() -> None:
    """D-68:数据银行无「持续伤害概念股」「量子同频概念股」独立卡 → 不存在,从注册表删。

    (只剩持续伤害/量子同频的「邀请」「契约」形态,它们仍在。)
    """
    assert "持续伤害概念股" not in INVESTMENT_ENVS
    assert "量子同频概念股" not in INVESTMENT_ENVS
    # 邀请/契约形态仍在
    assert "持续伤害邀请" in INVESTMENT_ENVS and "持续伤害契约" in INVESTMENT_ENVS
    assert "量子同频邀请" in INVESTMENT_ENVS and "量子同频契约" in INVESTMENT_ENVS


def test_is_known_env() -> None:
    """is_known_env:注册表内 True,外 False(识别完整性信号,供 cw_screen_invest_env log warn)。"""
    assert is_known_env("追击概念股") is True
    assert is_known_env("命运圣杯邀请") is True
    assert is_known_env("不存在环境") is False
    assert is_known_env("") is False


# ===== ADR-0138 OCR 名归一用框架 LCS 相似匹配(非全等) =====
def test_canon_name_lcs_with_guards() -> None:
    """_canon_name:艺术小字形变靠 find_best_match_by_lcs(th=0.5);长度差>3 拒;效果 LCS<0.5 拒。"""
    from sr_od.application.currency_war.operations.tools.harvest_invest_codex import (
        HarvestInvestCodex,
    )
    op = HarvestInvestCodex.__new__(HarvestInvestCodex)
    op.kind = 'strategies'
    # 形变 + 分隔符差:• vs ·,OCR 误读(狸=禄)→ LCS 命中
    assert op._canon_name('飞光•传剑',
                          '获得【彦卿】和【景元】，他们获得【师徒】羁绊。'
                          '【彦卿】的【天河泻】获得强化，造成战斗中【仙舟】神君和【景元】累计伤害值15%的伤害。') == '飞光·传剑'
    assert op._canon_name('步狸村之谜', '获得一个穿戴【狼狩星徽】的【狸狸】') == '步狸村之谜'  # 图鉴勘误:狸是规范名(2026-08-15 前测试断言旧名'步禄村之谜'未同步)
    # 防误配:短名偶合高分(胜利，还 vs 返利)→ 长度守卫拒(6 vs 2);效果不符拒
    assert op._canon_name('胜利，还', '使当前连胜数变成3连胜') == '胜利，还'
    # 全等直通
    assert op._canon_name('开源节流', '获得10金币') == '开源节流'


# ===== ADR-0150 两层架构:plaza API base × curated overlay =====
def test_adr0150_base_layer_full() -> None:
    """base 层全量:策略 335(334 plaza + 1 补遗)/ 环境 83(官方全量,与数据银行同口径)。"""
    from sr_od.application.currency_war.data.cw_invest_data import (
        PLAZA_AUGMENTS,
        PLAZA_PORTALS,
    )
    assert len(PLAZA_AUGMENTS) == 334
    assert len(PLAZA_PORTALS) == 83
    assert len(INVESTMENT_STRATEGIES) == 335  # + 补遗 追击星徽套组(二)
    assert len(INVESTMENT_ENVS) == 83
    # id 主键唯一
    ids = [a.id for a in PLAZA_AUGMENTS]
    assert len(set(ids)) == len(ids)
    # 补遗在表且 source 是米游社 content
    extra = INVESTMENT_STRATEGIES["追击星徽套组(二)"]
    assert extra.source == "6302"


def test_adr0150_overlay_no_orphans() -> None:
    """overlay(STRATEGY_ECONOMY/ENV_CATEGORY/ENV_FACTION/PICK_VALUE/ENV_PICK_VALUE)键 ⊆ 注册表键。

    构建层 import 即 raise 孤儿;此处显式断言防回归(版本更新后重跑生成器,
    overlay 键未跟改名 → 本测试红,提示修 overlay)。
    """
    from sr_od.application.currency_war.kernel.cw_investments import (
        ENV_CATEGORY,
        ENV_FACTION,
        ENV_PICK_VALUE,
        PICK_VALUE,
        STRATEGY_ECONOMY,
    )
    assert set(STRATEGY_ECONOMY) <= set(INVESTMENT_STRATEGIES)
    assert set(PICK_VALUE) <= set(INVESTMENT_STRATEGIES)
    assert set(ENV_CATEGORY) <= set(INVESTMENT_ENVS)
    assert set(ENV_FACTION) <= set(INVESTMENT_ENVS)
    assert set(ENV_PICK_VALUE) <= set(INVESTMENT_ENVS)


def test_adr0150_key_convention() -> None:
    """键约定(canon 归一,OCR 精确匹配层一致):半角冒号/逗号、无空格、无 •、无罗马数字。

    OCR 实测把全角冒号读成半角(战术专家:佩拉)→ 键用半角;叹号保持官方全角
    (艾丝妲的猛犬！/都是这家伙的错！,无实测证据不动)。
    """
    bad = [n for n in INVESTMENT_STRATEGIES if "：" in n or "，" in n or "•" in n
           or n != n.strip() or any(c.isspace() for c in n) or any(c in "ⅠⅡⅢ" for c in n)]
    assert not bad, f"策略键未 canon 归一:{bad[:5]}"
    bad_env = [n for n in INVESTMENT_ENVS if "：" in n or "，" in n or "•" in n
               or any(c.isspace() for c in n)]
    assert not bad_env, f"环境键未 canon 归一:{bad_env[:5]}"
    # OCR 友好形抽查(旧键已 RENAME)
    assert "本姑娘就是罗刹" in INVESTMENT_STRATEGIES
    assert "摸个鱼吧III" in INVESTMENT_STRATEGIES


def test_adr0150_official_data_corrections() -> None:
    """官方 API 修正落表:rarity 13 条(抽查)+ 占位 effect 替换为官方全文。"""
    # 原 curated 手打错(占位 effect + 品质错)
    assert INVESTMENT_STRATEGIES["定点爆破"].rarity == "棱彩"
    assert INVESTMENT_STRATEGIES["数值碾压"].rarity == "棱彩"
    assert INVESTMENT_STRATEGIES["攻防一体"].rarity == "棱彩"
    assert INVESTMENT_STRATEGIES["返利+"].rarity == "银"
    # 原 codex 采集错(棱彩 → 金)
    assert INVESTMENT_STRATEGIES["步狸村之谜"].rarity == "金"
    # 占位 4 字 effect 已被官方全文替换
    for name in ("定点爆破", "数值碾压", "攻防一体", "羁绊的力量"):
        assert len(INVESTMENT_STRATEGIES[name].effect) > 20, f"{name} 效果仍是占位"
    # 效果数值纠错(艾丝妲的猛犬 ×1000% → 官方 ×2000%)
    assert "2000%" in INVESTMENT_STRATEGIES["艾丝妲的猛犬！"].effect


def test_adr0150_plaza_new_entries() -> None:
    """plaza API 补齐 14 条(米游社 doc 315 之外的版本新条目);环境 83 全量无缺。"""
    for name in ("星星相印", "命运圣杯星徽", "不虚此行", "离火燎原", "战术专家:佩拉",
                 "领航专家:姬子", "狸财经狸", "狸狸的早晨", "大变活狸", "环保大使叽米",
                 "黑塔纪元", "飞光·映月", "都是这家伙的错！", "摸个鱼吧III", "锻冶专家:刃"):
        assert name in INVESTMENT_STRATEGIES, f"{name} 应在注册表(plaza 补齐)"
    # 飞光·映月效果已知(召唤物建档待办闭环):镜流+特殊1费景元,师徒羁绊
    assert "镜流" in INVESTMENT_STRATEGIES["飞光·映月"].effect


# ===== W144 OCR 间隔号形变归一(AGENTS.md OCR 分层②;run_20260826_004527 实机缺陷链)=====
def test_w144_get_strategy_bullet_variant_hits() -> None:
    """①`全都要•彩`(OCR 把 · 误读为 •)经 get_strategy 命中注册表条目,返回规范形。

    修前:精确查 miss → cw_screen_invest_strategy L216 假告警「数据缺口」。
    """
    from sr_od.application.currency_war.kernel.cw_investments import (
        get_strategy,
        normalize_invest_name,
    )
    s = get_strategy('全都要•彩')
    assert s is not None, 'bullet 形变名应命中注册表(归一后精确查)'
    assert s.name == '全都要·彩'          # 返回的是注册表规范形条目
    assert s.rarity == '棱彩'
    # 归一函数本体:无歧义映射;非形变字符不动
    assert normalize_invest_name('全都要•彩') == '全都要·彩'
    assert normalize_invest_name('飞光‧传剑') == '飞光·传剑'   # U+2027 同族
    assert normalize_invest_name('开源节流') == '开源节流'
    # 环境名同口径(银·金·彩 是注册表唯一含 · 的环境名)
    from sr_od.application.currency_war.kernel.cw_investments import get_env
    assert get_env('银•金•彩') is not None


def test_w144_economy_aggregate_bullet_name_not_dropped() -> None:
    """②economy 聚合:active_strategies 含 bullet 形变名时经济效果不再静默丢。

    修前:`economy_effect_of('采购专员•彩')` 精确查 miss → 全 0 EconomyEffect
    → cw_economy 按名聚合把策略经济效果静默丢弃(真金影响,run_20260826_004527 缺陷链)。
    锚卡:采购专员·彩(含 · 名 + STRATEGY_ECONOMY 有 economy:refresh_surprise_every=5)。
    对照:规范名与 bullet 形变名聚合结果逐字段相等;真未知名仍全 0(归一不虚增)。
    """
    from sr_od.application.currency_war.kernel.cw_investments import (
        EconomyEffect,
        aggregate_economy,
        economy_effect_of,
    )
    eff_canon = economy_effect_of('采购专员·彩')
    eff_bullet = economy_effect_of('采购专员•彩')
    assert eff_canon.refresh_surprise_every == 5
    assert eff_bullet == eff_canon, 'bullet 形变名与规范名的经济效果应等价(修前 miss 全 0)'
    # 聚合口径:bullet 形变名混在 active_strategies 里,效果必须聚合上
    agg = aggregate_economy(['采购专员•彩', '本金充裕'])
    assert agg.refresh_surprise_every == 5 and agg.instant_gold == 26
    # 对照:完全未知名(非形变)仍全 0(归一只做无歧义映射,不虚增)
    assert economy_effect_of('完全未知策略') == EconomyEffect()


def test_w144_raw_name_not_polluted_by_lookup() -> None:
    """③原始名保留:查找边界归一不回写——get_strategy 不改注册表键,也不改入参语义。

    数据边界声明:采集/telemetry(invest_cards.jsonl)在 cw_screen_invest_strategy 内
    直接用 OCR 原始名落盘,不经 get_strategy → 无直接可测入口;此处锁「查找不改
    注册表与写入端」:get_strategy 归一仅作用于查询入参,INVESTMENT_STRATEGIES 键集
    不含任何 bullet 形变(注册表数据层未被规范化污染)。
    """
    from sr_od.application.currency_war.kernel.cw_investments import (
        INVESTMENT_ENVS,
        get_strategy,
    )
    # 查询 bullet 名后,注册表键集不变(无 bullet 键被写入/替换)
    _ = get_strategy('全都要•彩')
    bad = [n for n in INVESTMENT_STRATEGIES if any(c in n for c in '•‧∙・')]
    assert not bad, f'注册表被归一污染(出现 bullet 键):{bad[:5]}'
    bad_env = [n for n in INVESTMENT_ENVS if any(c in n for c in '•‧∙・')]
    assert not bad_env, f'环境注册表被归一污染:{bad_env[:5]}'


def test_w144_augment_affinity_normalized_lookup() -> None:
    """④dict 直查消费点走规范化入口:AUGMENT_COMP_AFFINITY(飞光·传剑 等含 · 键)bullet 形变不再 miss。"""
    from sr_od.application.currency_war.kernel.cw_comps import (
        augment_affinity,
        augment_env_affinity,
    )
    assert augment_affinity('飞光•传剑') == {'景元仙舟': 1.0}
    assert augment_affinity('黑塔纪元') == {'大黑塔银河学者': 1.0}   # 无分隔符名不受影响
    assert augment_affinity('不存在策略') == {}
    # 环境侧同口径(ENV_COMP_AFFINITY 现键无 ·,锁守卫:未来加含 · 键时同样被归一救)
    assert augment_env_affinity('不存在环境') == {}
    from sr_od.application.currency_war.kernel.cw_comps import ENV_COMP_AFFINITY
    assert augment_env_affinity('仙舟概念股') == ENV_COMP_AFFINITY['仙舟概念股']
def test_adr0151_bindings_table_valid() -> None:
    """语义绑定表:键 ⊆ 注册表;值 ⊆ FACTIONS/CHARACTERS(构建层孤儿 raise + 此处显式断言)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.data.cw_factions import FACTIONS
    from sr_od.application.currency_war.kernel.cw_investments import STRATEGY_BINDINGS

    assert set(STRATEGY_BINDINGS) <= set(INVESTMENT_STRATEGIES)
    for name, (fs, cs) in STRATEGY_BINDINGS.items():
        assert fs <= set(FACTIONS), f"{name} 阵营值不在 FACTIONS:{sorted(fs - set(FACTIONS))}"
        assert cs <= set(CHARACTERS), f"{name} 角色值不在 CHARACTERS:{sorted(cs - set(CHARACTERS))}"
    # 未建模卡 → 空绑定(新 API 卡待 diff 提示后建模,不炸)
    from sr_od.application.currency_war.kernel.cw_investments import (
        get_strategy,
        strategy_bindings,
    )
    fs, cs = strategy_bindings(get_strategy("开源节流"))
    assert fs == frozenset() and cs == frozenset()


def test_adr0151_noise_bindings_removed() -> None:
    """文本扫描噪声清除(泛用效果顺带提及阵营 ≠ 绑定):战术义眼/祝福系不再误绑。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        get_strategy,
        strategy_bindings,
    )

    for name in ("战术义眼", "战术义眼+", "战术义眼++", "生命之花祝福",
                 "幸运星祝福", "折叠小刀祝福", "和平手枪祝福", "量产型装甲祝福"):
        fs, cs = strategy_bindings(get_strategy(name))
        assert not fs and not cs, f"{name} 应无绑定(泛用数值卡,旧扫描曾误绑)"


def test_adr0151_semantic_bindings_present() -> None:
    """语义绑定抽查:套组/机制强化/赠角色 三类 + 契约环境阵营。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_BINDINGS,
        env_faction,
        get_strategy,
        strategy_bindings,
    )

    # 套组:阵营+角色双绑
    assert STRATEGY_BINDINGS["追击星徽套组"] == (frozenset({"追击"}), frozenset({"飞霄"}))
    # 机制强化:阵营绑
    assert strategy_bindings(get_strategy("离火燎原"))[0] == frozenset({"减益"})
    assert strategy_bindings(get_strategy("超充站"))[0] == frozenset({"能量"})
    # 赠 key 角色:仅角色绑
    assert STRATEGY_BINDINGS["双龙会"] == (frozenset(), frozenset({"丹恒·饮月", "丹恒·腾荒"}))
    # 偶像经济:火花 = 星间旅人 4 费核心(plaza traits 确认)→ 阵营+角色双绑
    assert STRATEGY_BINDINGS["偶像经济"] == (frozenset({"星间旅人"}), frozenset({"火花"}))
    # 盗用身份:{NICKNAME} 占位符已归一为 开拓者(生成器 strip_rich)
    assert "开拓者" in get_strategy("盗用身份").effect and "{" not in get_strategy("盗用身份").effect
    # 契约环境阵营(ADR-0151 补:赠阵营角色)
    for name, faction in (("量子同频契约", "量子同频"), ("公司契约", "公司"),
                          ("持续伤害契约", "持续伤害"), ("战技点契约", "战技点"),
                          ("星核猎手契约", "星核猎手"), ("欢愉契约", "欢愉"),
                          ("特邀专家:加拉赫", "击破")):
        assert env_faction(name) == faction, f"{name} 应绑 {faction}"


def test_megastar_set_binding_derived_from_single() -> None:
    """套组绑定由单件条目 + 名字规则派生(共享同一元组对象):
    改单件即改套组;套组条目禁再手写(重建即漂移双源)。"""
    from sr_od.application.currency_war.kernel.cw_investments import STRATEGY_BINDINGS
    assert STRATEGY_BINDINGS["追击星徽套组"] is STRATEGY_BINDINGS["追击星徽"]
    assert STRATEGY_BINDINGS["追击星徽套组(二)"] is STRATEGY_BINDINGS["追击星徽"]


# ==================== w162_invest_inject ====================

import logging

import pytest

from sr_od.application.currency_war.sim import engine_p1 as cw_sim
from sr_od.application.currency_war.sim.cw_sim_invest import (
    SIM_STRATEGY_PICK_SCHEDULE,
    SimInvestProfile,
    env_freq_table,
    freq_dropped_names,
    sample_invest_profile,
    strategy_freq_table,
)


@pytest.fixture(autouse=True)
def _quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 logging.disable 是全局态:pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(prev)


_POOL = 'fallback'
KEYS = ('final_hp', 'hp_trail', 'refreshes', 'dir_round', 'level')


def _snap(seed: int, **kw):
    r = cw_sim.simulate_p1(seed, pool=_POOL, **kw)
    return {k: getattr(r, k) for k in KEYS} | {'n_ledger': len(r.ledger)}


# ---------- 零漂移门 ----------

def test_invest_off_is_bit_identical() -> None:
    """默认(不传 invest)与显式 False 逐位同——主路径零漂移。"""
    for s in range(4):
        assert _snap(s) == _snap(s, invest=False)


def test_empty_profile_equals_off() -> None:
    """空剧本(无环境无选卡)= 关:注入脚手架对主 rng 零消耗。"""
    empty = SimInvestProfile()
    for s in range(4):
        assert _snap(s) == _snap(s, invest=empty)


def test_sample_profile_deterministic() -> None:
    """同 seed 同剧本(独立 rng 流;A/B 配对可比性的基础)。"""
    for s in (0, 7, 42):
        assert sample_invest_profile(s) == sample_invest_profile(s)


# ---------- 注入语义位 ----------

def test_inject_writes_session_semantic_slots() -> None:
    """环境+选卡写 session 语义位(handler 写点对齐)+ state 镜像。

    用单轮剧本验证:开局环境即写;选卡轮 append 进 active_strategies
    (去重:同名二选一只入一次);SimResult 观测字段同步。
    """
    prof = SimInvestProfile(
        active_env='银河学者概念股',
        picks=((1, 1, '黑塔纪元'), (1, 3, '黑塔纪元')),   # 重名 → 去重
    )
    r = cw_sim.simulate_p1(0, pool=_POOL, invest=prof)
    assert r.invest_env == '银河学者概念股'
    assert r.invest_strategies == ('黑塔纪元',)


def test_inject_session_carries_fields() -> None:
    """注入后 session(生产持久宿主)携带 active_env/active_strategies。"""
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )
    sess = StrategySession()
    prof = SimInvestProfile(active_env='火药味',
                            picks=((1, 1, '加油站'),))
    cw_sim.simulate_p1(0, pool=_POOL, session=sess, invest=prof)
    assert sess.active_env == '火药味'
    assert '加油站' in sess.active_strategies


# ---------- ①资格通道激活 ----------

def test_direct_line_qualified_via_injected_env() -> None:
    """①资格通道直证:注入环境亲和 → _direct_line_qualified 为真
    (无注入语料下恒假,W161 缺口本体)。"""
    from sr_od.application.currency_war.kernel.cw_intention import (
        _direct_line_qualified,
    )
    from sr_od.application.currency_war.kernel.cw_state import GameState
    st = GameState()
    assert not _direct_line_qualified(st, '大黑塔银河学者')
    st.active_env = '银河学者概念股'
    assert _direct_line_qualified(st, '大黑塔银河学者')


def test_invest_on_activates_p1_lock() -> None:
    """缺口闭合直证:注入批 p1_locked_rounds 分布非零(off 恒 0)。"""
    prof = SimInvestProfile(
        active_env='银河学者概念股',
        picks=((1, 1, '黑塔纪元'),),   # 策略侧亲和 → 大黑塔银河学者
    )
    on = [cw_sim.simulate_p1(s, pool=_POOL, invest=prof).p1_locked_rounds
          for s in range(8)]
    off = [cw_sim.simulate_p1(s, pool=_POOL).p1_locked_rounds
           for s in range(8)]
    assert all(v == 0 for v in off)       # W161 缺口:off 口径恒 0
    assert any(v > 0 for v in on)         # 注入后锁定分布非零


# ---------- 经济聚合子集 ----------

def test_gold_per_node_and_instant_gold_apply() -> None:
    """定期福利(+4 金选卡 / 每节点 +2):账本收入行出现 invest 键。"""
    prof = SimInvestProfile(picks=((1, 1, '定期福利'),))
    r = cw_sim.simulate_p1(0, pool=_POOL, invest=prof)
    rows = [row for row in r.ledger
            if (row.get('sim') or {}).get('income', {}).get('invest')]
    assert rows, 'gold_per_node 未进账本收入分解'


# (加油站免费刷取证局锁 test_free_refresh_per_node_zero_cost 已随
# decision_v2 基线臂退役删除——取证形态不可复现;dd-038 检查点② /
# commit b94e9cfb,2026-09-04 用户裁定清理;不变式语义见 ADR-0131。)


# ---------- 频次表与日程 ----------

def test_freq_tables_registry_known() -> None:
    """频次表全注册表内(丢名走 freq_dropped_names 披露,不进表)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        get_env,
        get_strategy,
    )
    for name, _ in strategy_freq_table():
        assert get_strategy(name) is not None, name
    for name, _ in env_freq_table():
        assert get_env(name) is not None, name


def test_schedule_keys_unique_and_ordered() -> None:
    """日程键 (plane, round) 唯一且按位面-轮升序。"""
    keys = [(p, r) for p, r, _ in SIM_STRATEGY_PICK_SCHEDULE]
    assert len(keys) == len(set(keys))
    assert keys == sorted(keys)


def test_plaza_names_canon_colon() -> None:
    """全角冒号 plaza 名(如 骇客专家：银狼)归一后进表(不丢)。"""
    table = dict(strategy_freq_table())
    assert '骇客专家:银狼' in table
    # 披露通道存在(即使本版零丢弃,键可达)
    assert isinstance(freq_dropped_names(), dict)



# ==================== test_fortune_picker ====================

import sys
from pathlib import Path

sys.path.insert(0, 'src')

FIX = Path(__file__).resolve().parents[4] / 'screens' / 'cw_fortune_picker' / 'event_three_cards.webp'


def _ocr_cards(path) -> list[str]:
    import cv2
    import numpy as np
    try:
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
        m = OnnxOcrMatcher()
    except Exception:
        return []
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    res = m.run_ocr(img)
    XS = (510, 900, 1290)
    buckets: dict[int, list[str]] = {x: [] for x in XS}
    for t, mr in (res or {}).items():
        if mr.max is None:
            continue
        cy, cx = mr.max.center.y, mr.max.center.x
        if 290 <= cy <= 410:
            nearest = min(XS, key=lambda x: abs(x - cx))
            if abs(nearest - cx) < 190:
                buckets[nearest].append(t)
    return [' '.join(buckets[x]) for x in XS]


def test_fortune_cards_ocr_on_fixture():
    """局32 实拍:三卡应识别出 深层奥迹/原始奥迹/留白卡 关键词。"""
    if not FIX.exists():
        import pytest
        pytest.skip('fixture 缺失')
    texts = _ocr_cards(FIX)
    if not any(texts):
        import pytest
        pytest.skip('OCR 模型不可用')
    joined = ' '.join(texts)
    assert '奥迹' in joined, f'强化卡关键词应识别: {texts}'
    assert '留白' in joined or '黑天鹅' in joined, f'第三卡应识别: {texts}'


# ==================== test_invest_strategy_recognizer ====================

from unittest.mock import MagicMock

import sr_od.application.currency_war.obs.recognizers.invest_strategy_recognizer as mod
from sr_od.application.currency_war.obs.recognizers.invest_strategy_recognizer import (
    InvestStrategyRecognizer,
)


def test_screen_name_matches_invest_strategy() -> None:
    """recognizer 注册的 screen_name = '货币战争-投资策略'(与 screen_info 一致)。"""
    assert InvestStrategyRecognizer.screen_name == '货币战争-投资策略'


def _mock_ocr(monkeypatch, names: list[str]) -> None:
    monkeypatch.setattr(mod, '_area_rect', lambda ctx, name, screen_name=None: MagicMock())
    monkeypatch.setattr(mod, '_ocr', lambda ctx, screen, rect: [MagicMock(data=n) for n in names])


def test_recognize_parses_three_strategies(monkeypatch) -> None:
    """3 张策略卡 → strategies 名列表(滤数字/符号噪声)。"""
    _mock_ocr(monkeypatch, ['乱成一锅粥', '盗用身份', '远见'])

    out = InvestStrategyRecognizer().recognize(MagicMock(), MagicMock(), MagicMock())
    assert out == {'strategies': ['乱成一锅粥', '盗用身份', '远见']}


def test_recognize_filters_short_noise(monkeypatch) -> None:
    """滤单字噪声 / 纯数字(只留 2-10 字中文)。"""
    _mock_ocr(monkeypatch, ['团队力量·金', '1', '啊'])

    out = InvestStrategyRecognizer().recognize(MagicMock(), MagicMock(), MagicMock())
    assert out == {'strategies': ['团队力量·金']}   # '1'(纯数字) '啊'(单字)被滤


def test_recognize_empty_when_unreadable(monkeypatch) -> None:
    """读不到(area 缺 / OCR 无果)→ 空 list(不伪造)。"""
    monkeypatch.setattr(mod, '_area_rect', lambda ctx, name, screen_name=None: None)
    monkeypatch.setattr(mod, '_ocr', lambda ctx, screen, rect: [])

    out = InvestStrategyRecognizer().recognize(MagicMock(), MagicMock(), MagicMock())
    assert out == {'strategies': []}
