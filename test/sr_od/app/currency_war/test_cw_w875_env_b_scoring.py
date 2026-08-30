"""货币战争 W875 环境 B 类评分补全包 + 长线利好刷价参数 锁组。

出处:W873 环境盘点(.debug/temp/currency_war/w873_invest_env_audit/REPORT.md)
+ W872 攻击口径(映射行须有 comp 携带 tag 才非死映射);
机制真值 = affix_effects_data.py / cw_invest_data.py(id=120 长线利好)逐字。

锁语义:
- 开关生命周期第 1 态(默认关):全关 = 基表/基价零漂移(本组多条「关=中性」断言)。
- 死映射防线:W875 每行映射的 tag 其 counter/synergy 值域必须 ⊆ comp 实际携带
  的 mechanic_attributes 词汇(零携带 = 空转映射,禁)。
- 判定未准入的 6 词条(区别对待/霸凌弱者/以人为本/挫其锋芒/应激反应/一鼓作气)
  不得进映射——挂账待 comp 侧建模批,建模完成前入表即死映射。

注意:W875 行为开关默认关,本组开臂断言用 dataclasses.replace 构造开臂 registry
注入,不碰 DEFAULT_REGISTRY(测试零真实副作用纪律)。
"""
from __future__ import annotations

from dataclasses import replace

from sr_od.application.currency_war.data.affix_effects_data import AFFIX_EFFECTS
from sr_od.application.currency_war.kernel.cw_comps import (
    AFFIX_MECHANIC_MAP,
    COMP_LIBRARY,
    MECHANIC_COUNTERS,
    MECHANIC_SYNERGIES,
    W875_AFFIX_MECHANIC_MAP,
    W875_MECHANIC_COUNTERS,
    W875_MECHANIC_SYNERGIES,
    Comp,
    mechanics_fit,
    merged_mechanic_tables,
)
from sr_od.application.currency_war.kernel.cw_economy import refresh_cost_effective
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import GameState


def _comp(*attrs: str) -> Comp:
    """构造仅带指定 mechanic_attributes 的测试 comp(不污染 COMP_LIBRARY)。"""
    return Comp(name="测试comp", factions=[], core_chars=[], form_tiers={},
                strength="A", form_difficulty="easy", mechanic_attributes=list(attrs))


def _carried_tags() -> set[str]:
    """全仓 comp 实际携带的机制属性 tag 词汇(W872 口径的死映射判据)。"""
    comps = list(COMP_LIBRARY.values()) if isinstance(COMP_LIBRARY, dict) else list(COMP_LIBRARY)
    out: set[str] = set()
    for c in comps:
        out.update(getattr(c, "mechanic_attributes", []) or [])
    return out


def _arm(**flags: bool):
    return replace(DEFAULT_REGISTRY, **flags)


# —— 第 1 态默认关:零漂移 ——


def test_w875_default_off_tables_are_base() -> None:
    """全关时合并表原样返回基表对象(零分配零漂移)。"""
    affix_map, counters, synergies = merged_mechanic_tables()
    assert affix_map is AFFIX_MECHANIC_MAP
    assert counters is MECHANIC_COUNTERS
    assert synergies is MECHANIC_SYNERGIES


def test_w875_default_off_new_affixes_neutral() -> None:
    """开关关:能量逃逸/同步行动未入映射 → 词缀透传原名,对任何 comp 恒中性 0.5。"""
    from sr_od.application.currency_war.kernel.cw_comps import current_enemy_mechanics
    c = _comp("连携高频开大", "速度依赖", "量子拉条")
    st = GameState(enemy_affixes=["能量逃逸", "同步行动"])
    assert mechanics_fit(c, current_enemy_mechanics(st)) == 0.5


# —— 开臂断言(逐条独立子旗标)——


def test_w875_energy_leak_counters_ult_dependent() -> None:
    """能量逃逸(敌受击使攻击者能量 -4,affix_effects_data 逐字)→ 克连携高频开大。

    出处=cw_registry.w875_energy_leak_enabled 注记;机制 tag=能量削弱。
    端到端走词缀映射(current_enemy_mechanics)→ mechanics_fit。
    """
    from sr_od.application.currency_war.kernel.cw_comps import current_enemy_mechanics
    ult = _comp("连携高频开大")
    other = _comp("击破")
    st = GameState(enemy_affixes=["能量逃逸"])
    reg_on = _arm(w875_energy_leak_enabled=True)
    assert mechanics_fit(ult, current_enemy_mechanics(st, reg_on), registry=reg_on) < 0.5, \
        "能量削弱克开大依赖 → 降"
    assert mechanics_fit(other, current_enemy_mechanics(st, reg_on), registry=reg_on) == 0.5, \
        "无载体 comp 不受本 tag 影响"


def test_w875_sync_action_counters_speed() -> None:
    """同步行动(我方行动提前时敌也提前 20%,affix_effects_data 逐字)→ 克速度依赖/量子拉条。

    出处=cw_registry.w875_sync_action_enabled 注记;机制 tag=行动喂敌。
    """
    from sr_od.application.currency_war.kernel.cw_comps import current_enemy_mechanics
    fast = _comp("速度依赖")
    quantum = _comp("量子拉条")
    st = GameState(enemy_affixes=["同步行动"])
    reg_on = _arm(w875_sync_action_enabled=True)
    mechs = current_enemy_mechanics(st, reg_on)
    assert mechanics_fit(fast, mechs, registry=reg_on) < 0.5
    assert mechanics_fit(quantum, mechs, registry=reg_on) < 0.5


# —— 死映射防线(W872 口径)——


def test_w875_map_rows_have_carried_tags() -> None:
    """W875 每行映射 tag 的 counter/synergy 值域必须非空且 ⊆ comp 实际携带词汇。"""
    carried = _carried_tags()
    assert carried, "COMP_LIBRARY 携带词汇为空 = 判据失效"
    for affix, tag in W875_AFFIX_MECHANIC_MAP.items():
        values = (W875_MECHANIC_COUNTERS.get(tag, [])
                  + W875_MECHANIC_SYNERGIES.get(tag, []))
        assert values, f"{affix}→{tag} 的克制/受利值域为空 = 死映射(空转行)"
        dead = [a for a in values if a not in carried]
        assert not dead, f"{affix}→{tag} 值域含零携带 tag {dead} = 死映射(W872 口径)"


def test_w875_map_rows_grounded_in_affix_truth() -> None:
    """W875 词缀行必须存在于机制真值注册表,且效果原文含判据关键词(防运行时写档漂移)。"""
    grounds = {"能量逃逸": "能量降低", "同步行动": "行动提前"}
    for affix, keyword in grounds.items():
        assert affix in AFFIX_EFFECTS, f"{affix} 不在 affix_effects_data = 映射无真值"
        assert keyword in AFFIX_EFFECTS[affix], f"{affix} 效果原文缺判据关键词「{keyword}」"


def test_w875_degraded_affixes_not_mapped() -> None:
    """6 条未准入词条不得进任何映射(区别对待/霸凌弱者/以人为本/挫其锋芒/应激反应/一鼓作气)。

    判定依据:comp 侧无对应 mechanic_attributes tag 词汇(W872 攻击 §③),
    入表即零携带死映射;挂账待 comp 侧建模批。
    """
    degraded = ("区别对待", "霸凌弱者", "以人为本", "挫其锋芒", "应激反应", "一鼓作气")
    for name in degraded:
        assert name not in AFFIX_MECHANIC_MAP, f"{name} 未建模却已入基表映射"
        assert name not in W875_AFFIX_MECHANIC_MAP, f"{name} 未建模却已入 W875 映射"
        assert name in AFFIX_EFFECTS, f"{name} 应在机制真值注册表(挂账的机制事实仍需在档)"


# —— 长线利好刷价参数(机制真值 = cw_invest_data id=120 逐字)——


def test_longterm_registry_truth_lock() -> None:
    """阈值 30 / 折后价 1 为机制常量锁(id=120 原文「花费金币进行30次刷新后…只需要1金币」)。"""
    assert DEFAULT_REGISTRY.longterm_refresh_threshold == 30
    assert DEFAULT_REGISTRY.longterm_refresh_price == 1
    assert DEFAULT_REGISTRY.longterm_refresh_discount_enabled is False, "生命周期第 1 态:默认关"


def test_longterm_refresh_cost_flag_off_is_base() -> None:
    """开关关:任何条件下恒基价(shop_refresh_cost 缺省 2)。"""
    s = GameState(active_env="长线利好")
    for count in (0, 29, 30, 999):
        assert refresh_cost_effective(s, count) == 2, f"关臂 count={count} 应恒基价"


def test_longterm_refresh_cost_arm_gated_by_count_and_env() -> None:
    """开关开:折后价 = 计数过阈值 ∧ 长线利好台账在场,两条件缺一不可。"""
    reg = _arm(longterm_refresh_discount_enabled=True)
    s_env = GameState(active_env="长线利好")
    s_other = GameState(active_env="火药味")
    assert refresh_cost_effective(s_env, 29, reg) == 2, "未过阈值(30 刷)→ 基价"
    assert refresh_cost_effective(s_env, 30, reg) == 1, "过阈值 ∧ 长线利好 → 折后价"
    assert refresh_cost_effective(s_other, 999, reg) == 2, "非长线利好环境 → 基价"
