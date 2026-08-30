"""货币战争 W878 死 tag 复活 4 批 锁组。

出处:死映射裁决(死 tag 三问分诊报告,.debug/temp/currency_war/w876_deadtag_adjudication/
REPORT.md,离线只读分析)+ W872 攻击口径(映射行须有 comp 携带 tag 才非死映射);
机制真值 = affix_effects_data.py 词条原文逐字。

锁语义:
- 开关生命周期第 1 态(默认关):全关 = 基表路径零漂移(复活 tag 不参与评分求交,
  含对应词缀的局对任何 comp 恒 0.5 中性)。
- 结构锁(值域⊆词汇表):4 个复活 tag(单属性队/成型羁绊队/慢速/依赖合成装备)的
  基表映射行值域必须 ⊆ COMP_LIBRARY 实际携带词汇 —— 本批复活后这些基表行由死转活。
- 判据边界:每 tag 的载体集必须符合裁决判型(单属性队=属性型羁绊主档 ≥4 的 comp;
  慢速=DOT 载体;依赖合成装备=反甲装备流;成型羁绊队=羁绊驱动型,装备流/单核族不打)。
- 滤除口不交集结构锁:W878 词汇集与三张直读原始属性的查表(boss_fit 兜底/护航
  serves/巨星兜底)不交集,任一侧撞车即红(w882 攻击角度5 采纳)。
- 两旗标禁独立开臂:synth_equip_dep(选型侧)不得脱离 junk_first(执行侧防护)
  单独开臂,构造期校验(w882 攻击旗标交互角度采纳)。

注意:W878 行为开关默认关,开臂断言用 dataclasses.replace 构造开臂 registry 注入,
不碰 DEFAULT_REGISTRY(测试零真实副作用纪律)。
"""
from __future__ import annotations

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


def _comp(*attrs: str) -> Comp:
    """构造仅带指定 mechanic_attributes 的测试 comp(不污染 COMP_LIBRARY)。"""
    return Comp(name="测试comp", factions=[], core_chars=[], form_tiers={},
                strength="A", form_difficulty="easy", mechanic_attributes=list(attrs))


def _comp_by_name(name: str) -> Comp:
    for c in COMP_LIBRARY:
        if c.name == name:
            return c
    raise AssertionError(f"COMP_LIBRARY 无 {name}")


def _arm(**flags: bool):
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
    plain = _comp("击破", "燃血")
    assert effective_mechanic_attributes(plain) is plain.mechanic_attributes
    mixed = _comp("DoT", "慢速", "成型羁绊队")
    assert effective_mechanic_attributes(mixed) == ["DoT"]


# —— 开臂断言(逐 tag 独立子旗标;机制真值 = affix_effects_data 词条原文)——


def test_w878_mono_attribute_counters_by_quantum_extinguish() -> None:
    """量子熄火(量子伤害 1 点×4 次)克单属性队:希儿量子降分,其他 comp 不受影响。

    出处 = final_comps README D3「希儿怕量子熄火」明文(玩法文档层)。
    """
    reg = _arm(w878_mono_attribute_enabled=True)
    assert _fit_with(_comp_by_name("希儿量子"), "量子熄火", reg) < 0.5, \
        "单属性队被属性熄火克 → 降"
    assert _fit_with(_comp_by_name("DOT队"), "量子熄火", reg) == 0.5, \
        "非单属性队 comp 不受影响"


def test_w878_formed_bond_benefits_from_lone() -> None:
    """形单影只(1/2/3 未激活羁绊 → 伤害 85%/60%/30%)利成型羁绊队(羁绊全不受罚,synergy)。

    出处 = 形单影只词条原文 + README B1 羁绊档位乘区;量级 = 全表最大(-70%)。
    """
    reg = _arm(w878_formed_bond_enabled=True)
    assert _fit_with(_comp_by_name("列车同行"), "形单影只", reg) > 0.5, \
        "成型羁绊队羁绊全 → 不受罚 = 相对利好"
    assert _fit_with(_comp("高频低单次"), "形单影只", reg) == 0.5, \
        "无成型羁绊队 tag 的 comp 恒中性"


def test_w878_slow_counters_dot_burn() -> None:
    """冻结族(极速制冷:耗战技点冻结)克慢速:DOT 磨血族降分。

    出处 = final_dot_kafka(叠层×引爆磨血胜利条件);冻结使单位整回合无法行动 ≈ DPS 归零,
    对慢热队是战力腰斩级 → 与 -0.25 步进量级匹配。
    """
    reg = _arm(w878_slow_burn_enabled=True)
    assert _fit_with(_comp_by_name("DOT队"), "极速制冷", reg) < 0.5
    assert _fit_with(_comp_by_name("专家桑博DOT"), "坠入陷阱", reg) < 0.5


def test_w878_synth_equip_dep_counters_baie() -> None:
    """变宝为废(首次进阶合成 50% 垃圾袋)克依赖合成装备:反甲白厄降分。

    出处 = final_baie_reflect(反甲装备流,以牙还牙甲=胜利条件);合成侧已由 junk_first
    处理,本 tag 只补选型侧(互补禁重复)。按两旗标禁独立开臂约束(构造期校验),
    开选型侧必须同开 junk_first(联动评审臂),故本用例同开两侧。
    """
    reg = _arm(w878_synth_equip_dep_enabled=True, junk_first_sacrifice_enabled=True)
    assert _fit_with(_comp_by_name("反甲白厄"), "变宝为废", reg) < 0.5
    assert _fit_with(_comp_by_name("万敌单C"), "变宝为废", reg) == 0.5


# —— 结构锁(值域 ⊆ comp 携带词汇;W872 死映射口径)——


def _carried_tags() -> set[str]:
    """全仓 comp 实际携带的机制属性 tag 词汇(W872 口径的死映射判据)。"""
    out: set[str] = set()
    for c in COMP_LIBRARY:
        out.update(getattr(c, "mechanic_attributes", []) or [])
    return out


def test_w878_revived_base_rows_not_dead() -> None:
    """4 个复活 tag 所在基表行(属性熄火/装备依赖/成型羁绊利好/冻结)值域 ⊆ 携带词汇。

    复活前这些行零携带 = 恒 0.5 空转死映射;本批补载体后必须保持非死(回归防线)。
    """
    carried = _carried_tags()
    revived_rows = {
        "属性熄火": AFFIX_MECHANIC_MAP["风之熄火"],   # 7 条熄火词条同 tag
        "装备依赖": AFFIX_MECHANIC_MAP["变宝为废"],
        "成型羁绊利好": AFFIX_MECHANIC_MAP["形单影只"],
        "冻结": AFFIX_MECHANIC_MAP["极速制冷"],
    }
    for affix, tag in revived_rows.items():
        assert tag in carried, f"行 {affix}→{tag} 的 tag 无任何 comp 携带 = 死映射回归"


# —— 判据边界锁(载体集 = 裁决判型,防标注漂移)——


def test_w878_mono_attribute_carrier_boundary() -> None:
    """单属性队载体判据锁(判据性,非枚举):每个载体须「属性型羁绊主档 ≥4」。

    w882 攻击采纳:原「唯一载体=希儿量子」枚举锁把单例钉成制度性盲区
    (final_daheita_aoe 明文冰之熄火 counter 大黑塔,但枚举锁使该克制恒中性且
    未来补载体必锁红)——改判据后,新属性 comp(如火纯色线)落档即自动入判,
    错载体(属性型羁绊非主档/档深不足)自动拦。判据载体集 = cw_comps
    .ATTRIBUTE_TYPE_FACTIONS(V4.4 仅量子同频按角色属性聚合)。
    """
    carriers = [c for c in COMP_LIBRARY if "单属性队" in c.mechanic_attributes]
    assert carriers, "单属性队载体为空 = 复活未落码"
    assert any(c.name == "希儿量子" for c in carriers), \
        "证据基线(final_comps README D3 明文)不得丢失"
    for c in carriers:
        attr_mains = {f: t for f, t in c.form_tiers.items()
                      if f in ATTRIBUTE_TYPE_FACTIONS}
        assert attr_mains and max(attr_mains.values()) >= 4, \
            f"{c.name} 单属性队载体缺属性型羁绊主档 ≥4(判据漂移: {c.form_tiers})"


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
        _arm(w878_synth_equip_dep_enabled=True)
    _arm(junk_first_sacrifice_enabled=True)          # junk 侧单独开合法
    _arm(w878_synth_equip_dep_enabled=True,          # 联动同开合法
         junk_first_sacrifice_enabled=True)
