"""货币战争 投资策略/环境领域模型(cw_investments)测试 —— 纯逻辑,不依赖游戏。

验证 InvestmentEnv(概念股/邀请带 faction)+ 派生 ENV_FACTION_MAP(单一真相源)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_comps import ENV_FACTION_MAP
from sr_od.application.currency_war.cw_investments import (
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
    """is_known_env:注册表内 True,外 False(识别完整性信号,供 handle_invest_env log warn)。"""
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
    from sr_od.application.currency_war.cw_invest_data import PLAZA_AUGMENTS, PLAZA_PORTALS
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
    from sr_od.application.currency_war.cw_investments import (
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


# ===== ADR-0151 策略语义绑定(逐卡手建模;↺ ADR-0134 文本扫描派生)=====
def test_adr0151_bindings_table_valid() -> None:
    """语义绑定表:键 ⊆ 注册表;值 ⊆ FACTIONS/CHARACTERS(构建层孤儿 raise + 此处显式断言)。"""
    from sr_od.application.currency_war.cw_chars import CHARACTERS
    from sr_od.application.currency_war.cw_factions import FACTIONS
    from sr_od.application.currency_war.cw_investments import STRATEGY_BINDINGS

    assert set(STRATEGY_BINDINGS) <= set(INVESTMENT_STRATEGIES)
    for name, (fs, cs) in STRATEGY_BINDINGS.items():
        assert fs <= set(FACTIONS), f"{name} 阵营值不在 FACTIONS:{sorted(fs - set(FACTIONS))}"
        assert cs <= set(CHARACTERS), f"{name} 角色值不在 CHARACTERS:{sorted(cs - set(CHARACTERS))}"
    # 未建模卡 → 空绑定(新 API 卡待 diff 提示后建模,不炸)
    from sr_od.application.currency_war.cw_investments import get_strategy, strategy_bindings
    fs, cs = strategy_bindings(get_strategy("开源节流"))
    assert fs == frozenset() and cs == frozenset()


def test_adr0151_noise_bindings_removed() -> None:
    """文本扫描噪声清除(泛用效果顺带提及阵营 ≠ 绑定):战术义眼/祝福系不再误绑。"""
    from sr_od.application.currency_war.cw_investments import get_strategy, strategy_bindings

    for name in ("战术义眼", "战术义眼+", "战术义眼++", "生命之花祝福",
                 "幸运星祝福", "折叠小刀祝福", "和平手枪祝福", "量产型装甲祝福"):
        fs, cs = strategy_bindings(get_strategy(name))
        assert not fs and not cs, f"{name} 应无绑定(泛用数值卡,旧扫描曾误绑)"


def test_adr0151_semantic_bindings_present() -> None:
    """语义绑定抽查:套组/机制强化/赠角色 三类 + 契约环境阵营。"""
    from sr_od.application.currency_war.cw_investments import (
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

