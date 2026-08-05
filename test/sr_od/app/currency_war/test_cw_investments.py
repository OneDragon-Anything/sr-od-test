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
