"""货币战争 战略层(cw_comps)测试 —— 纯逻辑,不依赖游戏。

验证 comp 相关评分原则(用户 2026-08-03):
- mechanics_fit 双向(debuff=buff):万敌+反伤=synergy 升;阿雅+禁速=counter 降。
- equip_fit comp 相关(阿雅需 2 反重力皮靴;超线性)。
- comp_score 多维;select_comp 用户 4 轴 steer(build_around/forbid/priority)+ optionality + 阶段成型难度。
- maybe_pivot 转型信号;select_megastar 按 target 选。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_comps import (
    COMP_LIBRARY,
    MECHANIC_COUNTERS,
    MECHANIC_SYNERGIES,
    _difficulty_phase_factor,
    boss_fit,
    comp_score,
    comp_score_breakdown,
    current_enemy_mechanics,
    env_fit,
    equip_fit,
    form_progress,
    get_comp,
    make_score_context,
    maybe_pivot,
    mechanics_fit,
    progress,
    select_comp,
    select_megastar,
)
from sr_od.application.currency_war.cw_state import BenchChar, GameState
from test import SrTestBase


def _cfg(**overrides) -> SimpleNamespace:
    base = {
        "faction_priority": ["贝洛伯格", "仙舟"],
        "character_priority": ["阿格莱雅", "流萤"],
        "character_build_around": [],
        "character_forbid": [],
        "faction_forbid": [],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestCurrencyWarComps(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    # —— form_progress / progress 单调 ——(巡击青雀 factions=[仙舟,追击],form_tiers={仙舟:5,追击:3})

    def test_form_progress_monotonic(self):
        青雀 = get_comp("巡击青雀")
        s0 = GameState(board={})
        s_half = GameState(board={"仙舟": 3, "追击": 2})
        s_full = GameState(board={"仙舟": 5, "追击": 3})
        v0 = form_progress(青雀, s0)
        v_half = form_progress(青雀, s_half)
        v_full = form_progress(青雀, s_full)
        self.assertEqual(v0, 0.0)
        self.assertGreater(v_half, v0)
        self.assertGreater(v_full, v_half)
        self.assertAlmostEqual(v_full, 1.0, places=6, msg="成型满 tier → form_progress=1.0")

    def test_progress_includes_core_chars(self):
        """progress = 0.6 form + 0.4 core_char;持有核心角色 → 高于纯 form_progress。"""
        青雀 = get_comp("巡击青雀")
        s_no_core = GameState(board={"仙舟": 5, "追击": 3})   # 满成型但无核心角色
        s_with_core = GameState(board={"仙舟": 5, "追击": 3},
                                bench=[BenchChar(slot=0, char_id="青雀", faction="仙舟")])
        self.assertGreater(progress(青雀, s_with_core), progress(青雀, s_no_core),
                           "持有核心角色 → progress 更高")

    # —— equip_fit comp 相关(阿雅需 2 反重力皮靴)——

    def test_equip_fit_aya_two_boots_supralinear(self):
        """阿雅 key_equips=[反重力皮靴×2]:0 靴中性;1 靴部分;2 靴满;无关装备略低。"""
        阿雅 = get_comp("昼神阿雅")
        none_eq = GameState()                                   # 无装备数据 → 中性 0.5
        one = GameState(equips=["反重力皮靴"])
        two = GameState(equips=["反重力皮靴", "反重力皮靴"])
        irrelevant = GameState(equips=["别的装备"])
        self.assertEqual(equip_fit(阿雅, none_eq), 0.5, "无装备数据 → 中性")
        self.assertAlmostEqual(equip_fit(阿雅, two), 1.0, places=6, msg="2 靴满 → 1.0")
        self.assertGreater(equip_fit(阿雅, two), equip_fit(阿雅, one), "2 靴 > 1 靴")
        self.assertGreater(equip_fit(阿雅, one), 0.5, "1 靴 > 中性(超线性奖励)")
        self.assertLess(equip_fit(阿雅, irrelevant), 0.5, "持装备但无关键件 → 略低")

    def test_equip_fit_no_key_equips_neutral(self):
        """comp 无关键装备依赖 → 中性 0.5(用局部 Comp,不污染共享 COMP_LIBRARY)。"""
        from sr_od.application.currency_war.cw_comps import Comp
        comp_no_equip = Comp(name="测试", factions=["巡海游侠"], core_chars=[], form_tiers={},
                             strength="A", form_difficulty="easy", key_equips=[])
        self.assertEqual(equip_fit(comp_no_equip, GameState(equips=["冷笑话引擎"])), 0.5,
                         "无 key_equips 的 comp → 装备中性 0.5")

    # —— mechanics_fit 双向(debuff=buff;用户核心洞察)——

    def test_mechanics_fit_wandi_debuff_is_buff(self):
        """万敌[燃血] + 反伤 → synergy 升(>0.5):debuff 对燃血队是 buff(debuff=buff 典型)。"""
        万敌 = get_comp("万敌单C")
        self.assertGreater(mechanics_fit(万敌, {"反伤"}), 0.5, "正当防卫反伤利燃血 → 升")

    def test_mechanics_fit_aya_countered_by_speed_suppress(self):
        """阿雅[速度依赖] + 速度抑制(忽快忽慢) → counter 降(<0.5)。"""
        阿雅 = get_comp("昼神阿雅")
        self.assertLess(mechanics_fit(阿雅, {"速度抑制"}), 0.5, "忽快忽慢克极端高速(阿雅鞋队)→ 降")

    def test_mechanics_fit_wandi_countered_by_permanent_trauma(self):
        """万敌[燃血] + 掉血削上限(永久创伤) → counter 降(<0.5)。⚠️ 燃血的反例:
        反伤利燃血(debuff=buff),但永久创伤(掉血→减上限)克燃血。一词缀双向的复杂情况。"""
        万敌 = get_comp("万敌单C")
        self.assertLess(mechanics_fit(万敌, {"掉血削上限"}), 0.5, "永久创伤克燃血(掉血减上限双损)")

    def test_mechanics_fit_neutral_when_no_mechanics(self):
        """无机制信息 → 中性 0.5(不奖不罚)。"""
        万敌 = get_comp("万敌单C")
        self.assertEqual(mechanics_fit(万敌, set()), 0.5)

    def test_mechanics_fit_same_affix_opposite_direction(self):
        """同一'反伤'词缀:对万敌=利(>0.5),对反甲白厄=克(<0.5)—— 一词缀双向。"""
        万敌 = get_comp("万敌单C")
        白厄 = get_comp("反甲白厄")
        self.assertGreater(mechanics_fit(万敌, {"反伤"}), 0.5)
        self.assertLess(mechanics_fit(白厄, {"反伤"}), 0.5, "反伤克高频低单次(白厄)")

    def test_mechanic_tables_bidirectional(self):
        """MECHANIC 表双向:反伤既在 COUNTERS(克高频)又在 SYNERGIES(利燃血)。"""
        self.assertIn("反伤", MECHANIC_COUNTERS)
        self.assertIn("反伤", MECHANIC_SYNERGIES)
        self.assertIn("高频低单次", MECHANIC_COUNTERS["反伤"])
        self.assertIn("燃血", MECHANIC_SYNERGIES["反伤"])

    # —— boss_fit / env_fit ——

    def test_boss_fit_aya_tv(self):
        """阿雅 boss_weakness=[电视机];遇电视机 → 0;无 boss → 0.5。"""
        阿雅 = get_comp("昼神阿雅")
        self.assertEqual(boss_fit(阿雅, ["电视机"]), 0.0)
        self.assertEqual(boss_fit(阿雅, []), 0.5)
        self.assertEqual(boss_fit(阿雅, ["别的boss"]), 0.5)

    def test_env_fit_t0_hardbind(self):
        """T0 env(昼之半神概念股)近乎硬绑昼神阿雅 → 1.0;别的 comp 仍 0.5。"""
        阿雅 = get_comp("昼神阿雅")
        列车 = get_comp("列车同行")
        self.assertAlmostEqual(env_fit(阿雅, "昼之半神概念股"), 1.0, places=6)
        self.assertEqual(env_fit(列车, "昼之半神概念股"), 0.5, "env 不加成该 comp → 0.5")

    def test_env_fit_faction_map(self):
        """env 加成对应阵营(追击邀请 → 含追击的巡击青雀 → 1.0)。"""
        青雀 = get_comp("巡击青雀")
        self.assertAlmostEqual(env_fit(青雀, "追击邀请"), 1.0, places=6)
        self.assertEqual(env_fit(青雀, ""), 0.5)

    # —— current_enemy_mechanics 映射 ——

    def test_current_enemy_mechanics_maps_affixes(self):
        """敌人词缀(OCR 名)→ 机制 tag;未知词缀原样透传。"""
        s = GameState(enemy_affixes=["正当防卫", "急速制冷", "未知词缀"])
        mechs = current_enemy_mechanics(s)
        self.assertIn("反伤", mechs)
        self.assertIn("冻结", mechs)
        self.assertIn("未知词缀", mechs)   # 未知原样当 tag

    # —— select_comp steer(用户 4 轴)+ optionality + 阶段难度 ——

    def test_select_comp_build_around_filter(self):
        """character_build_around 必含:只留含该角色的 comp。"""
        cfg = _cfg(character_build_around=["流萤"])
        s = GameState(round_num=5, gold=50)
        result = select_comp(s, make_score_context(s), cfg)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "击破流萤", "build_around=流萤 → 只剩击破流萤")

    def test_select_comp_forbid_filter(self):
        """character_forbid / faction_forbid 排除。"""
        s = GameState(round_num=5, gold=50)
        cfg_char = _cfg(character_forbid=["阿格莱雅"])
        names = [c.name for c in select_comp(s, make_score_context(s), cfg_char, top_n=99)]
        self.assertNotIn("昼神阿雅", names, "forbid 阿格莱雅 → 排除昼神阿雅")
        cfg_fac = _cfg(faction_forbid=["仙舟"])
        names2 = [c.name for c in select_comp(s, make_score_context(s), cfg_fac, top_n=99)]
        self.assertNotIn("巡击青雀", names2, "forbid 仙舟 → 排除巡击青雀")

    def test_select_comp_optionality_top_n(self):
        """top_n=N → 返回 N 个(按 comp_score 降序;用空 priority 避免 boost 干扰排序断言)。"""
        s = GameState(round_num=5, gold=50)
        cfg = _cfg(character_priority=[], faction_priority=[])   # 空 → boost=0,排序=纯 comp_score
        ctx = make_score_context(s)
        top3 = select_comp(s, ctx, cfg, top_n=3)
        self.assertEqual(len(top3), 3)
        # 降序:第 1 的 comp_score ≥ 第 2 ≥ 第 3
        self.assertGreaterEqual(comp_score(top3[0], s, ctx), comp_score(top3[1], s, ctx))
        self.assertGreaterEqual(comp_score(top3[1], s, ctx), comp_score(top3[2], s, ctx))

    def test_difficulty_phase_factor_early_prefers_easy(self):
        """早期/穷:easy×1.15、hard×0.85;后期均 1.0。"""
        列车 = get_comp("列车同行")     # easy
        白厄 = get_comp("反甲白厄")     # hard
        early = GameState(round_num=1, gold=10)
        late = GameState(round_num=10, gold=80)
        self.assertGreater(_difficulty_phase_factor(列车, early), _difficulty_phase_factor(白厄, early),
                           "早期 easy 因子 > hard")
        self.assertEqual(_difficulty_phase_factor(列车, late), 1.0)
        self.assertEqual(_difficulty_phase_factor(白厄, late), 1.0)

    # —— comp_score / breakdown ——

    def test_comp_score_in_range_and_breakdown_keys(self):
        """comp_score 在合理范围;breakdown 含 schema 稳定字段(telemetry 用)。"""
        阿雅 = get_comp("昼神阿雅")
        s = GameState(board={"昼之半神": 4}, round_num=8, gold=60,
                      enemy_affixes=["禁速"], active_env="昼之半神概念股")
        ctx = make_score_context(s)
        sc = comp_score(阿雅, s, ctx)
        self.assertGreater(sc, 0.0)
        bd = comp_score_breakdown(阿雅, s, ctx)
        for key in ("progress", "mechanics_fit", "env_fit", "boss_fit", "equip_fit", "strength", "form_progress"):
            self.assertIn(key, bd, f"breakdown 缺 schema 字段 {key}")

    # —— maybe_pivot ——

    def test_maybe_pivot_no_target_returns_best(self):
        """target=None → maybe_pivot 返回 select_comp 第一(承诺转型到最优)。"""
        cfg = _cfg()
        s = GameState(round_num=5, gold=50)
        result = maybe_pivot(s, make_score_context(s), cfg, target=None)
        self.assertIsNotNone(result)

    def test_maybe_pivot_low_hp_returns_fastest_easy(self):
        """hp<30 保命转型 → 返回成型最快的 easy comp(typical_form_round 最小)。"""
        cfg = _cfg()
        s = GameState(hp=20, round_num=5, gold=50)
        result = maybe_pivot(s, make_score_context(s), cfg, target=get_comp("昼神阿雅"))
        self.assertIsNotNone(result)
        # 列车同行(easy,typical_form_round=4)是成型最快的 easy 之一
        self.assertEqual(result.form_difficulty, "easy")

    def test_maybe_pivot_low_hp_signal3_preempts_signal1(self):
        """D-40:hp 危险时信号 3(保命)抢占信号 1(更优涌现)—— 即使有更优 comp 涌现,也只切最快 easy,
        不切高难度 comp(防振荡 churn:列车同行→...→昼神阿雅 死亡螺旋)。target=巡击青雀(medium),
        board 成型列车同行(更优,信号 1 会选它),但 hp=20 危险 → 应选最快 easy(DOT队),非列车同行。"""
        cfg = _cfg(faction_priority=["列车同行"])
        s = GameState(board={"列车同行": 4}, round_num=5, plane=1, hp=20, gold=50)  # 列车同行成型(信号1 会选)
        result = maybe_pivot(s, make_score_context(s), cfg, target=get_comp("巡击青雀"))
        self.assertIsNotNone(result, "hp 危险应 pivot 到最快 easy")
        self.assertEqual(result.form_difficulty, "easy", "保命只选 easy comp")
        self.assertNotEqual(result.name, "列车同行", "不该切到成型的列车同行(信号1 的选择)—— 保命要最快 easy")

    def test_maybe_pivot_better_comp_emerges(self):
        """信号 1(更优涌现):target=反甲白厄(毁灭),场面成型列车同行(更优 + 分差>PIVOT_GAP)
        → pivot 到列车同行。early round(remaining 足够)+ hp 健康 → 信号 2/3 不触发,只验信号 1。"""
        cfg = _cfg(faction_priority=["列车同行"])
        s = GameState(board={"列车同行": 4}, round_num=2, plane=1, hp=100, gold=50)  # 列车同行成型
        target = get_comp("反甲白厄")  # 毁灭,场面没有 → 远不如列车同行
        result = maybe_pivot(s, make_score_context(s), cfg, target=target)
        self.assertIsNotNone(result, "更优 comp 涌现应 pivot")
        self.assertEqual(result.name, "列车同行", "应 pivot 到更优的列车同行")

    def test_maybe_pivot_ceiling_unreachable_switches_easy(self):
        """信号 2(ceiling 不可达):target=阿雅(form_round=8)但 plane3 round5 → remaining≈1<8;
        board 部分成型使阿雅=best(信号 1 跳过)→ 切成型最快的 easy comp。"""
        cfg = _cfg(faction_priority=["昼之半神"])
        s = GameState(board={"昼之半神": 2}, round_num=5, plane=3, hp=100, gold=50)  # 阿雅部分但来不及
        target = get_comp("昼神阿雅")
        result = maybe_pivot(s, make_score_context(s), cfg, target=target)
        self.assertIsNotNone(result, "target 来不及成型应 pivot")
        self.assertEqual(result.form_difficulty, "easy", "ceiling 不可达 → 切 easy")

    def test_maybe_pivot_formed_target_no_ceiling_pivot(self):
        """信号2 已成型守卫:target=阿雅已成型(board=昼之半神:4=form_tiers)+ plane3 round5
        (remaining≈1<8)→ **不**因 ceiling 切走(form_progress=1.0 豁免信号2;不该放弃已完成 comp)。"""
        cfg = _cfg(faction_priority=["昼之半神"])
        s = GameState(board={"昼之半神": 4}, round_num=5, plane=3, hp=100, gold=50)  # 阿雅成型
        target = get_comp("昼神阿雅")
        result = maybe_pivot(s, make_score_context(s), cfg, target=target)
        self.assertIsNone(result, "已成型 target 不该因 ceiling 切走(信号2 已成型守卫)")

    # —— select_megastar ——

    def test_select_megastar_binds_core(self):
        """target.core_chars 含可选巨星 → 绑该角色(巡击青雀含知更鸟)。"""
        青雀 = get_comp("巡击青雀")
        self.assertEqual(select_megastar(GameState(), 青雀, ["知更鸟", "花火"]), "知更鸟")

    def test_select_megastar_no_target_returns_first(self):
        """无 target → 返回第一个可选(naive 兜底)。"""
        self.assertEqual(select_megastar(GameState(), None, ["花火", "知更鸟"]), "花火")

    def test_select_megastar_empty_returns_none(self):
        """无可选 → None。"""
        self.assertIsNone(select_megastar(GameState(), None, []))

    # —— COMP_LIBRARY 完整性 ——

    def test_comp_library_well_formed(self):
        """COMP_LIBRARY 每 comp 字段完整(form_tiers>0、strength 合法、difficulty 合法)。"""
        for c in COMP_LIBRARY:
            self.assertTrue(c.name, "comp 必须有名")
            self.assertTrue(c.factions, f"{c.name} 必须有 factions")
            self.assertTrue(c.form_tiers, f"{c.name} 必须有 form_tiers")
            self.assertIn(c.strength, ("S", "A", "B"), f"{c.name} strength 非法")
            self.assertIn(c.form_difficulty, ("easy", "medium", "hard"), f"{c.name} difficulty 非法")
            for f, t in c.form_tiers.items():
                self.assertGreater(t, 0, f"{c.name} form_tiers[{f}] 必须>0")

    def test_comp_library_core_chars_canonical(self):
        """COMP_LIBRARY core_chars 必须用规范名(CHARACTER_ROSTER),禁粉丝缩写(红A/杨叔/记忆主等)。

        用户 2026-08-03:有全量 roster 就该用它,别在代码数据里缩写。OCR/char_id 匹配靠规范名。
        """
        from sr_od.application.currency_war.cw_chars import CHARACTER_ROSTER
        for comp in COMP_LIBRARY:
            for c in comp.core_chars:
                self.assertIn(c, CHARACTER_ROSTER,
                              f"{comp.name}.core_chars 含非规范名 '{c}'(不在 CHARACTER_ROSTER)")

    def test_comp_library_key_equips_canonical(self):
        """COMP_LIBRARY key_equips 必须是规范装备名(EQUIPMENTS 注册表内)。

        工程化:装备也是领域实体,有注册表;key_equips 引用规范名(与 core_chars 同纪律)。
        """
        from sr_od.application.currency_war.cw_equipment import EQUIPMENTS
        for comp in COMP_LIBRARY:
            for e in comp.key_equips:
                self.assertIn(e, EQUIPMENTS,
                              f"{comp.name}.key_equips 含非规范装备名 '{e}'(不在 EQUIPMENTS 注册表)")
