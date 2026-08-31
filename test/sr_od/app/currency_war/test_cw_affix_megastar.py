# -*- coding: utf-8 -*-
"""test_cw_affix_megastar 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w875_env_b_scoring: test_cw_w875_env_b_scoring.py
- w878_deadtag_revive: test_cw_w878_deadtag_revive.py
- w88_star_investment: test_cw_w88_star_investment.py
- w607_affix_consumption: test_cw_w607_affix_consumption.py
- w607_h2o_verdict: test_cw_w607_h2o_verdict.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== w875_env_b_scoring ====================

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


# ==================== w878_deadtag_revive ====================

from dataclasses import replace

from sr_od.application.currency_war.data.cw_enemy_data import COMP_ATTR_TAGS
from sr_od.application.currency_war.kernel.cw_comps import (
    AFFIX_MECHANIC_MAP,
    ATTRIBUTE_TYPE_FACTIONS,
    COMP_LIBRARY,
    ESCORT_COMPS,
    MEGASTAR_BY_ATTRIBUTE,
    W878_GATED_TAGS,
    Comp,
    effective_mechanic_attributes,
    mechanics_fit,
    w878_active_tags,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import GameState

W878_FLAGS = ("w878_mono_attribute_enabled", "w878_formed_bond_enabled",
              "w878_slow_burn_enabled", "w878_synth_equip_dep_enabled")


def _w878_deadtag_revive_comp(*attrs: str) -> Comp:
    """构造仅带指定 mechanic_attributes 的测试 comp(不污染 COMP_LIBRARY)。"""
    return Comp(name="测试comp", factions=[], core_chars=[], form_tiers={},
                strength="A", form_difficulty="easy", mechanic_attributes=list(attrs))


def _comp_by_name(name: str) -> Comp:
    for c in COMP_LIBRARY:
        if c.name == name:
            return c
    raise AssertionError(f"COMP_LIBRARY 无 {name}")


def _w878_deadtag_revive_arm(**flags: bool):
    return replace(DEFAULT_REGISTRY, **flags)


def _fit_with(comp: Comp, affix: str, reg=DEFAULT_REGISTRY) -> float | None:
    """端到端:词缀经映射(current_enemy_mechanics 同源逻辑)→ mechanics_fit。"""
    from sr_od.application.currency_war.kernel.cw_comps import current_enemy_mechanics
    return mechanics_fit(comp, current_enemy_mechanics(GameState(enemy_affixes=[affix]), reg),
                         registry=reg)


# —— 第 1 态默认关:零漂移 ——


def test_w878_flags_default_off() -> None:
    """四个子旗标默认全关(生命周期第 1 态),w878_active_tags 空集。"""
    for f in W878_FLAGS:
        assert getattr(DEFAULT_REGISTRY, f) is False, f"{f} 默认必须关"
    assert w878_active_tags() == frozenset()


def test_w878_default_off_revived_tags_neutral() -> None:
    """开关关:复活 tag 不参与求交 —— 打 tag comp 遇对应词缀仍恒 0.5(基表路径零漂移)。

    逐条对应:量子熄火×希儿量子(单属性队)/极速制冷×DOT队(慢速)/
    变宝为废×反甲白厄(依赖合成装备)/形单影只×列车同行(成型羁绊队)。
    """
    pairs = [("希儿量子", "量子熄火"), ("DOT队", "极速制冷"),
             ("反甲白厄", "变宝为废"), ("列车同行", "形单影只")]
    for comp_name, affix in pairs:
        assert _fit_with(_comp_by_name(comp_name), affix) == 0.5, \
            f"关臂时 {comp_name}×{affix} 应恒中性"


def test_w878_default_off_effective_attrs_passthrough() -> None:
    """关臂:无 W878 tag 的 comp 属性集原对象透传(零分配);有则仅滤除 W878 tag。"""
    plain = _w878_deadtag_revive_comp("击破", "燃血")
    assert effective_mechanic_attributes(plain) is plain.mechanic_attributes
    mixed = _w878_deadtag_revive_comp("DoT", "慢速", "成型羁绊队")
    assert effective_mechanic_attributes(mixed) == ["DoT"]


# —— 开臂断言(逐 tag 独立子旗标;机制真值 = affix_effects_data 词条原文)——


def test_w878_mono_attribute_counters_by_quantum_extinguish() -> None:
    """量子熄火(量子伤害 1 点×4 次)克单属性队:希儿量子降分,其他 comp 不受影响。

    出处 = final_comps README D3「希儿怕量子熄火」明文(玩法文档层)。
    """
    reg = _w878_deadtag_revive_arm(w878_mono_attribute_enabled=True)
    assert _fit_with(_comp_by_name("希儿量子"), "量子熄火", reg) < 0.5, \
        "单属性队被属性熄火克 → 降"
    assert _fit_with(_comp_by_name("DOT队"), "量子熄火", reg) == 0.5, \
        "非单属性队 comp 不受影响"


def test_w878_formed_bond_benefits_from_lone() -> None:
    """形单影只(1/2/3 未激活羁绊 → 伤害 85%/60%/30%)利成型羁绊队(羁绊全不受罚,synergy)。

    出处 = 形单影只词条原文 + README B1 羁绊档位乘区;量级 = 全表最大(-70%)。
    """
    reg = _w878_deadtag_revive_arm(w878_formed_bond_enabled=True)
    assert _fit_with(_comp_by_name("列车同行"), "形单影只", reg) > 0.5, \
        "成型羁绊队羁绊全 → 不受罚 = 相对利好"
    assert _fit_with(_w878_deadtag_revive_comp("高频低单次"), "形单影只", reg) == 0.5, \
        "无成型羁绊队 tag 的 comp 恒中性"


def test_w878_slow_counters_dot_burn() -> None:
    """冻结族(极速制冷:耗战技点冻结)克慢速:DOT 磨血族降分。

    出处 = final_dot_kafka(叠层×引爆磨血胜利条件);冻结使单位整回合无法行动 ≈ DPS 归零,
    对慢热队是战力腰斩级 → 与 -0.25 步进量级匹配。
    """
    reg = _w878_deadtag_revive_arm(w878_slow_burn_enabled=True)
    assert _fit_with(_comp_by_name("DOT队"), "极速制冷", reg) < 0.5
    assert _fit_with(_comp_by_name("专家桑博DOT"), "坠入陷阱", reg) < 0.5


def test_w878_synth_equip_dep_counters_baie() -> None:
    """变宝为废(首次进阶合成 50% 垃圾袋)克依赖合成装备:反甲白厄降分。

    出处 = final_baie_reflect(反甲装备流,以牙还牙甲=胜利条件);合成侧已由 junk_first
    处理,本 tag 只补选型侧(互补禁重复)。按两旗标禁独立开臂约束(构造期校验),
    开选型侧必须同开 junk_first(联动评审臂),故本用例同开两侧。
    """
    reg = _w878_deadtag_revive_arm(w878_synth_equip_dep_enabled=True, junk_first_sacrifice_enabled=True)
    assert _fit_with(_comp_by_name("反甲白厄"), "变宝为废", reg) < 0.5
    assert _fit_with(_comp_by_name("万敌单C"), "变宝为废", reg) == 0.5


# —— 结构锁(值域 ⊆ comp 携带词汇;W872 死映射口径)——


def _w878_deadtag_revive_carried_tags() -> set[str]:
    """全仓 comp 实际携带的机制属性 tag 词汇(W872 口径的死映射判据)。"""
    out: set[str] = set()
    for c in COMP_LIBRARY:
        out.update(getattr(c, "mechanic_attributes", []) or [])
    return out


def _effective_carried_tags(reg) -> set[str]:
    """开臂态全仓**生效**携带词汇 = 静态标注 ∪ 判据性动态并入(w882 角度1 采纳)。

    单属性队载体的主形态是判据性动态并入(effective_mechanic_attributes 按
    ATTRIBUTE_TYPE_FACTIONS 判据注入),静态标注只是希儿量子基线的另一形态 ——
    死映射判据必须数「生效携带」而非「静态标注」,否则判据性载体被误判死映射。
    """
    out = _w878_deadtag_revive_carried_tags()
    for c in COMP_LIBRARY:
        out.update(effective_mechanic_attributes(c, reg))
    return out


def test_w878_revived_base_rows_not_dead() -> None:
    """4 个复活 tag 所在基表行(属性熄火/装备依赖/成型羁绊利好/冻结)非死映射。

    非死判据(W872 口径,按映射链重推):机制 tag 的克制/受利目标集非空,且目标
    每个词都被**生效携带**(静态标注 ∪ 判据性动态并入,开臂态)。复活前这些行
    零携带 = 恒 0.5 空转死映射;本批补载体后必须保持非死(回归防线)。

    语义演进注记:原版直接断言 AFFIX_MECHANIC_MAP 值 ∈ 静态携带 —— 单属性队行
    按此判死是误报:该行机制词「属性熄火」本就非 comp 词汇,其载体走判据性动态
    并入(ATTRIBUTE_TYPE_FACTIONS 判据,w882 攻击角度1 采纳),静态零标注是设计
    形态而非回归;判据改为顺映射链数「克制/受利目标词的生效携带」。
    """
    reg = _w878_deadtag_revive_arm(w878_mono_attribute_enabled=True,
               w878_formed_bond_enabled=True,
               w878_slow_burn_enabled=True,
               w878_synth_equip_dep_enabled=True,
               junk_first_sacrifice_enabled=True)
    carried = _effective_carried_tags(reg)
    from sr_od.application.currency_war.kernel.cw_comps import (
        MECHANIC_COUNTERS,
        MECHANIC_SYNERGIES,
    )
    revived_rows = {
        "属性熄火": AFFIX_MECHANIC_MAP["风之熄火"],   # 7 条熄火词条同 tag
        "装备依赖": AFFIX_MECHANIC_MAP["变宝为废"],
        "成型羁绊利好": AFFIX_MECHANIC_MAP["形单影只"],
        "冻结": AFFIX_MECHANIC_MAP["极速制冷"],
    }
    for affix, mechanic in revived_rows.items():
        targets = set(MECHANIC_COUNTERS.get(mechanic, [])) | set(MECHANIC_SYNERGIES.get(mechanic, []))
        assert targets, f"行 {affix}→{mechanic} 无克制/受利目标 = 空转死映射"
        missing = targets - carried
        assert not missing, f"行 {affix}→{mechanic} 目标 {missing} 无任何 comp 生效携带 = 死映射回归"


# —— 判据边界锁(载体集 = 裁决判型,防标注漂移)——


def test_w878_mono_attribute_carrier_boundary() -> None:
    """单属性队载体判据锁(判据性,非枚举):每个生效载体须「属性型羁绊主档 ≥4」。

    w882 攻击采纳:原「唯一载体=希儿量子」枚举锁把单例钉成制度性盲区
    (final_daheita_aoe 明文冰之熄火 counter 大黑塔,但枚举锁使该克制恒中性且
    未来补载体必锁红)——改判据后,新属性 comp(如火纯色线)落档即自动入判,
    错载体(属性型羁绊非主档/档深不足)自动拦。判据载体集 = cw_comps
    .ATTRIBUTE_TYPE_FACTIONS(V4.4 仅量子同频按角色属性聚合)。

    载体集口径 = 开臂态**生效携带**(静态标注 ∪ 判据性动态并入):动态载体是
    本 tag 的主形态,只数静态标注会把判据性载体漏成空集误判「复活未落码」。
    """
    reg = _w878_deadtag_revive_arm(w878_mono_attribute_enabled=True)
    carriers = [c for c in COMP_LIBRARY
                if "单属性队" in effective_mechanic_attributes(c, reg)]
    assert carriers, "单属性队载体为空 = 复活未落码"
    assert any(c.name == "希儿量子" for c in carriers), \
        "证据基线(final_comps README D3 明文)不得丢失"
    for c in carriers:
        attr_mains = {f: t for f, t in c.form_tiers.items()
                      if f in ATTRIBUTE_TYPE_FACTIONS}
        assert attr_mains and max(attr_mains.values()) >= 4, \
            f"{c.name} 单属性队载体缺属性型羁绊主档 ≥4(判据漂移: {c.form_tiers})"


def test_w878_mono_attribute_dynamic_injection() -> None:
    """判据性动态载体行为锁:满足判据(属性型羁绊主档 ≥4)的 comp 无需静态标注,
    单属性队臂开启时被 effective_mechanic_attributes 动态并入「单属性队」携带,
    端到端吃量子熄火 counter 降分;档深不足/关臂不并入(零漂移)。

    出处 = w882 攻击角度1 采纳项(枚举锁改判据载体)+ ATTRIBUTE_TYPE_FACTIONS
    消费点接线(「属性熄火」行从死映射转活的实现载体)。守卫移除验证:断开
    effective_mechanic_attributes 的动态并入分支,本锁必红。
    """
    from sr_od.application.currency_war.kernel.cw_comps import current_enemy_mechanics

    def _pred_comp(tier: int) -> Comp:
        return Comp(name="判据comp", factions=["量子同频"], core_chars=[],
                    form_tiers={"量子同频": tier}, strength="A",
                    form_difficulty="easy", mechanic_attributes=["击破"])

    off = DEFAULT_REGISTRY
    armed = _w878_deadtag_revive_arm(w878_mono_attribute_enabled=True)
    # 关臂:零漂移,判据 comp 不携带
    assert "单属性队" not in effective_mechanic_attributes(_pred_comp(4), off)
    # 开臂 + 档深达标:动态并入,端到端吃 counter
    assert effective_mechanic_attributes(_pred_comp(4), armed) == ["击破", "单属性队"]
    fit = mechanics_fit(_pred_comp(4),
                        current_enemy_mechanics(GameState(enemy_affixes=["量子熄火"]), armed),
                        registry=armed)
    assert fit < 0.5, "判据载体开臂后应吃量子熄火 counter 降分"
    # 档深不足(3 < 4):不并入,恒中性(宁缺勿错)
    assert "单属性队" not in effective_mechanic_attributes(_pred_comp(3), armed)
    # 主档非判据集不误收(w922 审计 P2-2 反例形态):列车同行5 主档 + 量子同频4 副档
    # —— 羁绊乘区驱动型,即使属性羁绊档深达标也不是单属性队(「主档」校验)。
    multi_main = Comp(name="多主档comp", factions=["列车同行"], core_chars=[],
                      form_tiers={"列车同行": 5, "量子同频": 4}, strength="A",
                      form_difficulty="easy", mechanic_attributes=["击破"])
    assert "单属性队" not in effective_mechanic_attributes(multi_main, armed)
    # 并列最深档含属性羁绊判真(双主档形态,主档校验的合法边界)
    tied_main = Comp(name="双主档comp", factions=["量子同频", "列车同行"], core_chars=[],
                     form_tiers={"量子同频": 4, "列车同行": 4}, strength="A",
                     form_difficulty="easy", mechanic_attributes=["击破"])
    assert "单属性队" in effective_mechanic_attributes(tied_main, armed)
    # 副羁绊宽口径不算(form_tiers 无属性羁绊主档,仅 flex 层出现不判)
    flex_only = Comp(name="副羁绊comp", factions=[], core_chars=[],
                     form_tiers={"贝洛伯格": 4}, strength="A",
                     form_difficulty="easy", mechanic_attributes=["击破"])
    assert "单属性队" not in effective_mechanic_attributes(flex_only, armed)


def test_w878_slow_carrier_boundary() -> None:
    """慢速载体 ⊆ DoT 持有者(判据 = DOT 磨血胜利条件;大招流不算慢速)。"""
    for c in COMP_LIBRARY:
        if "慢速" in c.mechanic_attributes:
            assert "DoT" in c.mechanic_attributes, f"{c.name} 慢速缺 DoT 载体判据"
    dot_holders = {c.name for c in COMP_LIBRARY if "DoT" in c.mechanic_attributes}
    slow = {c.name for c in COMP_LIBRARY if "慢速" in c.mechanic_attributes}
    assert slow, "慢速载体为空 = 复活未落码"
    assert slow <= dot_holders


def test_w878_synth_equip_carrier_boundary() -> None:
    """依赖合成装备唯一载体 = 反甲白厄(装备即胜利条件判据)。"""
    carriers = [c.name for c in COMP_LIBRARY if "依赖合成装备" in c.mechanic_attributes]
    assert carriers == ["反甲白厄"], f"依赖合成装备载体漂移: {carriers}"


def test_w878_bond_exclusions_not_tagged() -> None:
    """成型羁绊队排除装备流/单核族(README B1/C4 判非):红A/万敌/白厄不打 tag。"""
    excluded = ("命运圣杯红A", "万敌单C", "反甲白厄")
    for name in excluded:
        c = _comp_by_name(name)
        assert "成型羁绊队" not in c.mechanic_attributes, \
            f"{name} 属装备流/单核族(羁绊不满也有战力),不应打成型羁绊队"
    tagged = [c.name for c in COMP_LIBRARY if "成型羁绊队" in c.mechanic_attributes]
    assert len(tagged) >= 10, f"羁绊驱动型载体数异常偏少: {len(tagged)}"


# —— 滤除口不交集结构锁(w882 攻击角度5 采纳)——


def test_w878_gated_tags_disjoint_from_raw_attr_lookup_tables() -> None:
    """W878 词汇集与三张直读原始 mechanic_attributes 的查表不交集(结构保证)。

    effective_mechanic_attributes 是 mechanic_attributes 的唯一**评分**滤除口,
    但另有三处直读原始属性:boss_fit 兜底 matchup(COMP_ATTR_TAGS)/护航 serves
    匹配(ESCORT_COMPS)/巨星兜底(MEGASTAR_BY_ATTRIBUTE)——当前不泄漏靠
    三张表恰好不含 W878 词汇,属巧合非结构:任一侧新增撞车词汇(如给巨星兜底
    加「成型羁绊队→某巨星」)会造出绕过开关的常开行为,且默认关零漂移锁测不到
    (现有锁只测 mechanics_fit 路径)。本锁把「碰巧不泄漏」升级为「被锁住的
    永不泄漏」:滤除口词汇或任一查表新增撞车词即红,逼先修接线再扩词汇。
    """
    gated = set(W878_GATED_TAGS)
    escort_serves = {s for ec in ESCORT_COMPS for s in ec.serves}
    enemy_tags = set(COMP_ATTR_TAGS) | set(COMP_ATTR_TAGS.values())
    mega_attrs = set(MEGASTAR_BY_ATTRIBUTE)
    clash = gated & (escort_serves | enemy_tags | mega_attrs)
    assert not clash, \
        f"W878 词汇撞进直读原始属性的查表(绕过滤除口风险): {clash}——" \
        "先让该消费点改走 effective_mechanic_attributes,再扩词汇"


# —— 两旗标禁独立开臂(构造期校验锁;w882 攻击旗标交互角度采纳)——


def test_w878_synth_flag_cannot_arm_without_junk_first() -> None:
    """选型侧(synth_equip_dep)单独开臂 = 构造期 ValueError;junk 侧单独开/两侧同开合法。

    依据:选型 -0.25 与执行侧牺牲合成防护是同一机制(变宝为废)的两面,选型惩罚叠
    已有防护疑过反应,禁未对照单独开臂;junk_first 防护先行合法。校验落点 =
    DecisionV2Registry.__post_init__(缺省两 False,零漂移)。
    """
    import pytest

    with pytest.raises(ValueError, match="禁独立开臂"):
        _w878_deadtag_revive_arm(w878_synth_equip_dep_enabled=True)
    _w878_deadtag_revive_arm(junk_first_sacrifice_enabled=True)          # junk 侧单独开合法
    _w878_deadtag_revive_arm(w878_synth_equip_dep_enabled=True,          # 联动同开合法
         junk_first_sacrifice_enabled=True)


# ==================== w88_star_investment ====================

from types import SimpleNamespace


from sr_od.application.currency_war.sim.checks.ledger import check_coldstart_seed_squander

from sr_od.application.currency_war.sim.checks.pool import check_engine_seed_not_resold
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.discipline import (
    engine_char_names,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import score_state

_REG = DEFAULT_REGISTRY
_CARRY = '姬子·启行'          # 引擎件(恒在目标集)
_PAIR_FILLER = '花火'          # 目标件(锁线视窗内)
_NON_DIRECTION = '翡翠'        # 公司件,线外散件(冷启动反例)


def _bench(name: str, faction: str = '仙舟罗浮',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _sess(line: bool = True) -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    if line:
        from sr_od.application.currency_war.kernel.cw_intention import (
            HoardTarget,
            IntentionState,
        )
        ist = IntentionState()
        ist.phase = 'locked'
        ist.locked_comp = '姬子列车'
        s.v3_intention = ist
        s.v3_hoard = HoardTarget(
            frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
            frozenset(), 'locked')
        s.v3_core_names = {'姬子·启行'}
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 6, 'gold': 60, 'level': 5,
            'board': {'仙舟罗浮': 1}, 'bench': [], 'shop': [], 'hp': 100}
    base.update(kw)
    return GameState(**base)


# --- 件1:核心升星价值项 ------------------------------------------------------


def test_core_star_term_values_2star_target() -> None:
    """2★ 目标件显影 core_star=unit;1★ 不显影;非目标 2★ 不显影([31]
    填充件可回收语义保留)。"""
    sess = _sess()
    st_2star = _state(bench=[_bench(_PAIR_FILLER, star=2)])
    st_1star = _state(bench=[_bench(_PAIR_FILLER, star=1)])
    v2 = score_state(st_2star, _REG, sess)['core_star']
    v1 = score_state(st_1star, _REG, sess)['core_star']
    import pytest
    assert v2 == pytest.approx(_REG.core_star_unit * _REG.bench_form_weight), \
        f'bench 2★ 目标件应按折减权重显影(实际 {v2})'
    assert v1 == 0.0
    # 非目标 2★ 不受保护
    st_off = _state(bench=[_bench('星期日', faction='盛会之星', star=2)])
    assert score_state(st_off, _REG, sess)['core_star'] == 0.0


def test_core_star_deployed_full_weight_and_ab_off() -> None:
    """deployed 2★ 全额;core_star_unit=0 关闭(A/B 基线臂)。"""
    sess = _sess()
    st = _state(
        deployed=[SimpleNamespace(char_id=_CARRY, faction='列车同行',
                                  star=2, position_pref='back',
                                  equips=(), slot=0)])
    assert score_state(st, _REG, sess)['core_star'] == _REG.core_star_unit
    reg_off = DecisionV2Registry(core_star_unit=0.0)
    assert score_state(st, reg_off, sess)['core_star'] == 0.0


# --- 件2:coldstart v2 防线 ---------------------------------------------------


def test_coldstart_door_single_frame() -> None:
    """v2 冷启动门单帧锁:P1 r1 板面空,pair 通道只放行方向件(引擎件/
    同名副本);线外散件不生成买候选(局49 形态,v1 门语义在 v2 的载体)。"""
    sess = _sess(line=False)   # 无方向(冷启动常态)
    _eng = next(iter(engine_char_names()))
    st = _state(round_num=1, board={}, shop=[
        SimpleNamespace(name=_eng, faction='列车同行', cost=3,
                        x=0, star=1),
        SimpleNamespace(name=_NON_DIRECTION, faction='公司', cost=1,
                        x=0, star=1),
    ])
    cands = generate_candidates(st, sess, _REG)
    tags = {c.action.card.name: c.tag for c in cands
            if c.action.__class__.__name__ == 'BuyCard'}
    assert tags.get(_NON_DIRECTION) is None, \
        f'冷启动线外散件 {_NON_DIRECTION} 不应生成买候选(实际 {tags})'
    assert _eng in tags, '引擎件(方向件)冷启动应放行'


def _cw_row(plane: int, rn: int, actions: list[dict]) -> dict:
    return {'plane': plane, 'round_num': rn, 'actions': actions,
            'state': {}}


def _buy(name: str, reason: str, cost: int = 1) -> dict:
    return {'__type__': 'BuyCard', 'reason': reason,
            'card': {'name': name, 'cost': cost}}


def _sell(name: str) -> dict:
    return {'__type__': 'SellBench', 'name': name}


def test_coldstart_checker_catches_d2_pair_violation() -> None:
    """变异自检(检查器非安慰剂):去门账本(p1 r1 d2_pair 买线外散件)
    必须涌现违规——v2 标签面(d2_ 前缀归一化)可被检查器消费。"""
    rows = [_cw_row(1, 1, [_buy(_NON_DIRECTION, 'd2_pair')]),
            _cw_row(1, 2, [_buy(_NON_DIRECTION, 'd2_pair')])]
    v = check_coldstart_seed_squander(rows)
    assert len(v) == 2, \
        f'去门变异必须涌现违规(实际 {v})——检查器对 v2 标签面失明'


def test_coldstart_checker_passes_legal_v2_ledger() -> None:
    """合法 v2 账本不误报:方向件(engine_seed)/copy(3合1 素材)放行。"""
    rows = [_cw_row(1, 1, [_buy('姬子·启行', 'd2_engine_seed', 3),
                           _buy('花火', 'd2_copy')]),
            _cw_row(1, 2, [_buy('三月七', 'd2_line_carry')])]
    assert check_coldstart_seed_squander(rows) == []


# --- 件3:engine_seed 买/卖互踩(窗口绝对不让位)-------------------------------


def test_carry_gate_yields_to_fresh_seed() -> None:
    """seed16 回归锁:bench 满+唯一可卖=新鲜 engine_seed 种子 →
    carry_gate 本轮不腾(旧 W51 死锁豁免=买侧见即买与卖侧腾位互踩,
    r4 买 r6 卖 r7 再买;ADR-0339 件3 裁决移除豁免)。"""
    from sr_od.application.currency_war.kernel.cw_intention import HoardTarget
    from sr_od.application.currency_war.decision.decision_v2.discipline import (
        carry_gate_actions,
    )

    sess = _sess()
    sess.v2_round_key = (1, 4)
    sess.v2_seed_bought = {'姬子·启行': ((1, 3), 1)}
    bench = ([_bench('姬子·启行', faction='列车同行', slot=0)]
             + [_bench(n, faction='仙舟罗浮', slot=i)
                for i, n in enumerate(['藿藿', '爻光', '三月七', '花火',
                                       '瓦尔特', '藿藿', '爻光', '三月七'],
                                      start=1)])
    st = _state(round_num=4, gold=50,
                shop=[SimpleNamespace(name='姬子·启行', faction='列车同行',
                                      cost=4, x=0, star=1)],
                bench=bench)
    assert carry_gate_actions(st, sess, _REG) == [], \
        '窗口内种子不让位给 carry 腾位(carry 延后 ≤2 轮,死锁有界)'


def test_seed_age_blocked_phantom_cnt_not_exempt() -> None:
    """幻影计数锁:cnt≥2 但真持有 <2 份(登记重复/执行层否决留痕)
    不解除种子保护(seed16 姬子·启行单买 cnt=2 被 r5 卖出的互踩根因);
    真持有 ≥2 份才走素材语境豁免。"""
    from sr_od.application.currency_war.kernel.cw_discipline_rules import (
        seed_age_blocked,
    )
    sess = _sess()
    sess.v2_round_key = (1, 5)
    sess.v2_seed_bought = {'姬子·启行': ((1, 4), 2)}
    st = _state(round_num=5, bench=[_bench('姬子·启行',
                                            faction='列车同行')])
    bc = st.bench[0]
    assert seed_age_blocked(bc, st, sess) is True, \
        '幻影 cnt=2(真持有 1 份)不得解除种子保护'
    st2 = _state(round_num=5,
                 bench=[_bench('姬子·启行', faction='列车同行', slot=0),
                        _bench('姬子·启行', faction='列车同行', slot=1)])
    assert seed_age_blocked(st2.bench[0], st2, sess) is False, \
        '真持有 2 份=3合1 素材语境,豁免(不挡)'


def test_checker_flags_reason_channel_resale() -> None:
    """检查器(reason 口径,语义不变):engine_seed 买入 ≤2 轮内单份回卖
    必报(seed16 姬子·启行 r4 买 r6 卖形态的账本侧锁)。"""
    rows = [_cw_row(1, 4, [_buy('姬子·启行', 'd2_engine_seed', 3)]),
            _cw_row(1, 6, [_sell('姬子·启行')])]
    v = check_engine_seed_not_resold(rows)
    assert len(v) == 1 and '姬子·启行' in v[0], f'回卖未报(实际 {v})'


def test_checker_bounds_and_merge_exemption() -> None:
    """边界:>2 轮后卖不报([21] 囤件窗口外合法);同轮 ≥2 份=3合1
    素材语境豁免不报。"""
    rows_late = [_cw_row(1, 4, [_buy('姬子·启行', 'd2_engine_seed', 3)]),
                 _cw_row(1, 8, [_sell('姬子·启行')])]
    assert check_engine_seed_not_resold(rows_late) == []
    rows_merge = [_cw_row(1, 4, [_buy('姬子·启行', 'd2_engine_seed', 3),
                                 _buy('姬子·启行', 'd2_engine_seed', 3)]),
                  _cw_row(1, 5, [_sell('姬子·启行')])]
    assert check_engine_seed_not_resold(rows_merge) == []


# ==================== w607_affix_consumption ====================

from dataclasses import replace
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    _line_env_qualified,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.operations.prep.equip_all import (
    _opening_hold_active,
    _rust_release_active,
)

_WANDI = '万敌单C'   # hp_charge_stack 累积型线(global_accumulators 注册,accumulator_family §4.1)
_SEELE = '希儿量子'   # 非累积型线(判据不辖,恒 None)


def _w607_affix_consumption_state(affixes: list[str], plane: int = 2, round_num: int = 1) -> GameState:
    st = GameState()
    st.plane = plane
    st.round_num = round_num
    st.enemy_affixes = list(affixes)
    return st


# ===== H1:_line_env_qualified 四态真值表 =====

def test_h1_non_accumulator_line_not_governed() -> None:
    """非累积型线 → None(判据不辖,资格面不变)。"""
    assert _line_env_qualified(_w607_affix_consumption_state(['净化身心']), _SEELE) is None


def test_h1_empty_affixes_missing_evidence() -> None:
    """词缀可信位缺失(空)→ None:不猜,放行(动态剔除同款)。"""
    assert _line_env_qualified(_w607_affix_consumption_state([]), _WANDI) is None


def test_h1_strong_env_hit() -> None:
    """强环境命中:正当防卫→反伤 / 忍无可忍→多段惩罚(accumulator_family §3)。"""
    assert _line_env_qualified(_w607_affix_consumption_state(['正当防卫']), _WANDI) is True
    assert _line_env_qualified(_w607_affix_consumption_state(['忍无可忍']), _WANDI) is True


def test_h1_adverse_or_unmapped_affix_miss() -> None:
    """环境不命中→False;未入 AFFIX_MECHANIC_MAP 的词缀(灼热轰炸)按不命中(宁缺勿错)。"""
    assert _line_env_qualified(_w607_affix_consumption_state(['净化身心']), _WANDI) is False
    assert _line_env_qualified(_w607_affix_consumption_state(['灼热轰炸']), _WANDI) is False


# ===== H1:锁线过滤(gate on/off × 环境)=====

def _wandi_visible_state(affixes: list[str]) -> GameState:
    st = _w607_affix_consumption_state(affixes)
    st.shop = [SimpleNamespace(name='万敌')]   # ③核心卡信号:意向核心可见
    return st


def test_h1_unconditional_adverse_env_holds_lock() -> None:
    """行为无条件化(W628 清偿):环境不命中 → 缓锁(判据恒在,无开关)。"""
    ist = update_intention(_wandi_visible_state(['净化身心']), IntentionState())
    assert ist.locked_comp == ''


def test_h1_strong_env_locks() -> None:
    """强环境命中 → 照常落锁(判据恒在,无开关)。"""
    ist = update_intention(_wandi_visible_state(['正当防卫']),
                           IntentionState())
    assert ist.locked_comp == _WANDI


def test_h1_missing_affixes_does_not_block() -> None:
    """词缀空帧(None=信息缺失)→ 不拦(不猜)。"""
    ist = update_intention(_wandi_visible_state([]),
                           IntentionState())
    assert ist.locked_comp == _WANDI


# ===== H3:_opening_hold_active 真值表(含降级锁)=====

_BATTLE_NODES = frozenset({'战斗', 'boss', '遭遇', '精英'})


def test_h3_default_unconditional_gate_on() -> None:
    """行为无条件化(W628 清偿):registry 默认恒 True,生产配置无关臂。"""
    assert DEFAULT_REGISTRY.opening_hold_battle_gate_enabled is True
    assert _opening_hold_active(2, '战斗', True, _BATTLE_NODES) is False


def test_h3_gate_on_battle_node_no_hold() -> None:
    """开臂:r2 战斗节点不 hold(W593 闸门①病灶:白板挨打)。"""
    assert _opening_hold_active(2, '战斗', True, _BATTLE_NODES) is False
    assert _opening_hold_active(2, 'boss', True, _BATTLE_NODES) is False


def test_h3_gate_on_non_battle_node_holds() -> None:
    """开臂:非战斗节点(奖励/补给/投资)维持 hold(r388 原语义保留)。"""
    for nt in ('奖励', '补给', '投资', '巨星'):
        assert _opening_hold_active(2, nt, True, _BATTLE_NODES) is True, nt


def test_h3_gate_on_round3_plus_no_hold() -> None:
    """r>2:无论节点类型都不属 opening hold(r70 语义接手)。"""
    assert _opening_hold_active(3, '奖励', True, _BATTLE_NODES) is False


def test_h3_missing_round_not_opening() -> None:
    """round 缺失(P1 之外/读不到)→ False(同旧「非开局轮」)。"""
    assert _opening_hold_active(None, '战斗', True, _BATTLE_NODES) is False


def test_h3_missing_node_type_degrades_to_old_hold() -> None:
    """降级锁:node_type 缺失(OCR+台账都空)→ 维持现状 hold(观察缺失不改行为)。"""
    assert _opening_hold_active(2, None, True, _BATTLE_NODES) is True


# ===== H2②:_rust_release_active 真值表 =====

def test_h2_default_unconditional_gate_on() -> None:
    """行为无条件化(W628 清偿):registry 默认恒 True,生产配置无关臂。"""
    assert DEFAULT_REGISTRY.rust_wear_release_enabled is True
    assert _rust_release_active(['库藏生锈'], True) is True


def test_h2_gate_on_rust_present_releases() -> None:
    """开臂+库藏生锈在场 → 豁免(owned 滞留=喂敌,competitors.md:45)。"""
    assert _rust_release_active(['库藏生锈', '忍无可忍'], True) is True


def test_h2_gate_on_no_rust_no_release() -> None:
    """开臂+词条不在场 → 不豁免(hold 原语义)。"""
    assert _rust_release_active(['忍无可忍'], True) is False
    assert _rust_release_active(None, True) is False


# ===== 注册表面 =====

def test_h1_strong_env_registry_nonempty_for_hp_charge_stack() -> None:
    """数据层守卫:hp_charge_stack 强环境集已建模且含多动/反伤两类机制 tag。"""
    from sr_od.application.currency_war.kernel.cw_comps import STRONG_ENV_MECHS
    assert {'反伤', '多段惩罚'} <= set(STRONG_ENV_MECHS['hp_charge_stack'])
    assert get_comp(_WANDI) is not None   # 判据锚:注册表存在该累积型线


# ==================== w607_h2o_verdict ====================

from sr_od.application.currency_war.kernel.cw_events import _EQUIP_VALUE
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY

# 装备获取评分面常数(cw_events 生产单一源)
_KEY_FIT_BONUS = 10          # decide_supply key_equips 命中加分
_PLANNER_KEY_BONUS = 15      # decide_planner 装备类 key 命中加分
_PLANNER_UPGRADE_FLOOR = 40  # 升费卡最低分(100−60 银狼不在场罚后下界)
_PLANNER_WEAKEN_SCORE = 55   # 弱化卡基础分


def _rust_per_piece() -> float:
    reg = DEFAULT_REGISTRY
    return (reg.rust_hoard_damage_share * reg.expected_battle_loss
            * reg.battles_left_est * reg.hp_to_gold)


def test_h2o_per_piece_gold_equivalent_bound() -> None:
    """每件扣减 = 0.75 金当量,封顶 7.5(registry/文档实采常量推导,非独立魔数)。"""
    reg = DEFAULT_REGISTRY
    assert reg.rust_hoard_damage_share == 0.03   # competitors.md:45 敌伤面
    assert reg.rust_hoard_penalty_cap == 10      # competitors.md:45 计件上限
    total = _rust_per_piece() * reg.rust_hoard_penalty_cap
    assert abs(_rust_per_piece() - 0.75) < 1e-9
    assert total < _KEY_FIT_BONUS, '最大滞留扣减须仍小于 key_fit 边际,否则补给面翻红重评'


def test_h2o_supply_face_no_reorder() -> None:
    """补给面无翻转:key 恒先(key_fit 10 > 封顶 7.5),非 key 间扣减同额序不变。"""
    total = _rust_per_piece() * DEFAULT_REGISTRY.rust_hoard_penalty_cap
    key_margin = _KEY_FIT_BONUS - total
    assert key_margin > 0, 'key_fit 边际被滞留扣减侵蚀穿 → 补给选序翻转,重评'
    # 非 key 件间:扣减 = f(owned+1),与候选身份无关 → 同额平移不改序
    assert len(set(_EQUIP_VALUE.values())) > 1   # 前提:价值表有区分度


def test_h2o_planner_face_no_flip() -> None:
    """巨星策划面:装备类扣后上界仍低于升费/弱化下界 → 选型不翻转。"""
    equip_upper = max(_EQUIP_VALUE.values()) + _PLANNER_KEY_BONUS
    total = _rust_per_piece() * DEFAULT_REGISTRY.rust_hoard_penalty_cap
    assert equip_upper - total < _PLANNER_UPGRADE_FLOOR, (
        '装备类扣后触及升费下界 → 策划面翻转,重评')
    assert equip_upper - total < _PLANNER_WEAKEN_SCORE
