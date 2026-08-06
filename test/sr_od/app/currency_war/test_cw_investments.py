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
