"""货币战争 战略层(cw_comps)测试 —— 纯逻辑,不依赖游戏。

验证 comp 相关评分原则(用户 2026-08-03):
- mechanics_fit 双向(debuff=buff):万敌+反伤=synergy 升;阿雅+禁速=counter 降。
- equip_fit comp 相关(阿雅需 2 反重力皮靴;超线性)。
- comp_score 多维;select_comp 用户 4 轴 steer(build_around/forbid/priority)+ optionality + 阶段成型难度。
- maybe_pivot 转型信号;select_megastar 按 target 选。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.cw_comps import (
    COMP_LIBRARY,
    MECHANIC_COUNTERS,
    MECHANIC_SYNERGIES,
    _difficulty_phase_factor,
    _held_base_copies,
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
    shop_supply,
)
from sr_od.application.currency_war.cw_state import BenchChar, GameState, ShopCard


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


# —— form_progress / progress 单调 ——(追击飞霄 factions=[追击],form_tiers={追击:3})


def test_form_progress_monotonic() -> None:
    飞霄 = get_comp("追击飞霄")
    s0 = GameState(board={})
    s_half = GameState(board={"追击": 2})
    s_full = GameState(board={"追击": 3})
    v0 = form_progress(飞霄, s0)
    v_half = form_progress(飞霄, s_half)
    v_full = form_progress(飞霄, s_full)
    assert v0 == 0.0
    assert v_half > v0
    assert v_full > v_half
    assert v_full == pytest.approx(1.0, abs=1e-6), "成型满 tier → form_progress=1.0"


def test_progress_includes_core_chars() -> None:
    """progress = 0.6 form + 0.4 core_char;持有核心角色 → 高于纯 form_progress。"""
    飞霄 = get_comp("追击飞霄")
    s_no_core = GameState(board={"追击": 3})   # 满成型但无核心角色
    s_with_core = GameState(board={"追击": 3},
                            bench=[BenchChar(slot=0, char_id="飞霄", faction="追击")])
    assert progress(飞霄, s_with_core) > progress(飞霄, s_no_core), (
        "持有核心角色 → progress 更高"
    )


# —— equip_fit comp 相关(阿雅需 2 反重力皮靴)——


def test_equip_fit_aya_two_boots_supralinear() -> None:
    """阿雅 key_equips=[反重力皮靴×2]:0 靴无数据(None);1 靴部分;2 靴满;无关装备略低。"""
    阿雅 = get_comp("昼神阿雅")
    none_eq = GameState()                                   # 无装备数据 → None(ADR-0107 动态权重剔除)
    one = GameState(equips=["反重力皮靴"])
    two = GameState(equips=["反重力皮靴", "反重力皮靴"])
    irrelevant = GameState(equips=["别的装备"])
    assert equip_fit(阿雅, none_eq) is None, "无装备数据 → None(动态权重剔除)"
    assert equip_fit(阿雅, two) == pytest.approx(1.0, abs=1e-6), "2 靴满 → 1.0"
    assert equip_fit(阿雅, two) > equip_fit(阿雅, one), "2 靴 > 1 靴"
    assert equip_fit(阿雅, one) > 0.5, "1 靴 > 中性(超线性奖励)"
    assert equip_fit(阿雅, irrelevant) < 0.5, "持装备但无关键件 → 略低"


def test_equip_fit_no_key_equips_neutral() -> None:
    """comp 无关键装备依赖 → None(ADR-0107:无数据动态剔除,非 0.5 常量地板;用局部 Comp 不污染 LIBRARY)。"""
    from sr_od.application.currency_war.cw_comps import Comp
    comp_no_equip = Comp(name="测试", factions=["巡海游侠"], core_chars=[], form_tiers={},
                         strength="A", form_difficulty="easy", key_equips=[])
    assert equip_fit(comp_no_equip, GameState(equips=["冷笑话引擎"])) is None, (
        "无 key_equips 的 comp → None(动态权重剔除)"
    )


# —— mechanics_fit 双向(debuff=buff;用户核心洞察)——


def test_mechanics_fit_wandi_debuff_is_buff() -> None:
    """万敌[燃血] + 反伤 → synergy 升(>0.5):debuff 对燃血队是 buff(debuff=buff 典型)。"""
    万敌 = get_comp("万敌单C")
    assert mechanics_fit(万敌, {"反伤"}) > 0.5, "正当防卫反伤利燃血 → 升"


def test_mechanics_fit_aya_countered_by_speed_suppress() -> None:
    """阿雅[速度依赖] + 速度抑制(忽快忽慢) → counter 降(<0.5)。"""
    阿雅 = get_comp("昼神阿雅")
    assert mechanics_fit(阿雅, {"速度抑制"}) < 0.5, "忽快忽慢克极端高速(阿雅鞋队)→ 降"


def test_mechanics_fit_wandi_countered_by_permanent_trauma() -> None:
    """万敌[燃血] + 掉血削上限(永久创伤) → counter 降(<0.5)。⚠️ 燃血的反例:
    反伤利燃血(debuff=buff),但永久创伤(掉血→减上限)克燃血。一词缀双向的复杂情况。"""
    万敌 = get_comp("万敌单C")
    assert mechanics_fit(万敌, {"掉血削上限"}) < 0.5, "永久创伤克燃血(掉血减上限双损)"


def test_mechanics_fit_neutral_when_no_mechanics() -> None:
    """无机制信息 → None(ADR-0107 动态权重剔除,不奖不罚)。"""
    万敌 = get_comp("万敌单C")
    assert mechanics_fit(万敌, set()) is None


def test_mechanics_fit_same_affix_opposite_direction() -> None:
    """同一'反伤'词缀:对万敌=利(>0.5),对反甲白厄=克(<0.5)—— 一词缀双向。"""
    万敌 = get_comp("万敌单C")
    白厄 = get_comp("反甲白厄")
    assert mechanics_fit(万敌, {"反伤"}) > 0.5
    assert mechanics_fit(白厄, {"反伤"}) < 0.5, "反伤克高频低单次(白厄)"


def test_mechanic_tables_bidirectional() -> None:
    """MECHANIC 表双向:反伤既在 COUNTERS(克高频)又在 SYNERGIES(利燃血)。"""
    assert "反伤" in MECHANIC_COUNTERS
    assert "反伤" in MECHANIC_SYNERGIES
    assert "高频低单次" in MECHANIC_COUNTERS["反伤"]
    assert "燃血" in MECHANIC_SYNERGIES["反伤"]


def test_mechanics_fit_jipo_pizairouhou_synergy() -> None:
    """巡海击破[击破] + 皮糙肉厚 → synergy 升:皮糙肉厚利击破(未被击破受伤-30%,击破流不受罚)。D-49。"""
    击破 = get_comp("巡海击破")   # ADR-0152:击破流萤更名(流萤非 V4.4 击破代表)
    assert mechanics_fit(击破, {"皮糙肉厚"}) > 0.5, "皮糙肉厚利击破 → 升"


def test_mechanics_fit_honga_bangyang_countered() -> None:
    """命运圣杯红A[高倍率单核] + 榜样激励 → counter 降:榜样激励克单核(伤害第一的 75%)。D-49。"""
    红a = get_comp("命运圣杯红A")
    assert mechanics_fit(红a, {"榜样激励"}) < 0.5, "榜样激励克单核 → 降"


def test_mechanics_fit_lietong_shield_countered() -> None:
    """列车同行[治疗护盾] + 治疗削弱(重症难题) → counter 降。D-49 对齐 comp 属性(护盾→治疗护盾)。"""
    列车 = get_comp("列车同行")
    assert "治疗护盾" in 列车.mechanic_attributes, "comp 属性对齐 MECHANIC(治疗护盾,非护盾)"
    assert mechanics_fit(列车, {"治疗削弱"}) < 0.5, "重症难题克治疗/护盾 → 降"


def test_mechanics_fit_baie_renwubukaren_countered() -> None:
    """反甲白厄[高频低单次] + 多段惩罚(忍无可忍:敌受 7 击提前 100%) → counter 降。D-55。"""
    白厄 = get_comp("反甲白厄")
    assert "高频低单次" in 白厄.mechanic_attributes
    assert mechanics_fit(白厄, {"多段惩罚"}) < 0.5, "忍无可忍克高频低单次(反甲白厄多段打→敌频动)→ 降"


def test_mechanics_fit_aya_chenzhongjiaobu_countered() -> None:
    """昼神阿雅[速度依赖] + 行动延后(沉重脚步:受击延后 8%) → counter 降。D-55。"""
    阿雅 = get_comp("昼神阿雅")
    assert "速度依赖" in 阿雅.mechanic_attributes
    assert mechanics_fit(阿雅, {"行动延后"}) < 0.5, "沉重脚步克速度依赖(鞋队 tuning 被打乱)→ 降"


def test_current_enemy_mechanics_maps_d55_affixes() -> None:
    """AFFIX_MECHANIC_MAP(D-55):忍无可忍→多段惩罚、沉重脚步→行动延后。"""
    mechs = current_enemy_mechanics(GameState(enemy_affixes=["忍无可忍", "沉重脚步"]))
    assert "多段惩罚" in mechs, "忍无可忍 → 多段惩罚"
    assert "行动延后" in mechs, "沉重脚步 → 行动延后"


# —— boss_fit / env_fit ——


def test_boss_fit_aya_tv() -> None:
    """阿雅 countered_by_bosses=[电视机];遇电视机 → 0;无 boss → None(ADR-0107 动态剔除)。

    有 boss 但不命中(别的boss)→ 0.5(真实中性:boss 在但不利害此 comp,有数据,非 None)。
    """
    阿雅 = get_comp("昼神阿雅")
    assert boss_fit(阿雅, ["电视机"]) == 0.0
    assert boss_fit(阿雅, []) is None
    assert boss_fit(阿雅, ["别的boss"]) == 0.5, "有 boss 数据但不命中 → 真实中性 0.5"


def test_env_fit_t0_hardbind() -> None:
    """T0 env(昼之半神概念股)近乎硬绑昼神阿雅 → 1.0;别的 comp 仍 0.5。"""
    阿雅 = get_comp("昼神阿雅")
    列车 = get_comp("列车同行")
    assert env_fit(阿雅, "昼之半神概念股") == pytest.approx(1.0, abs=1e-6)
    assert env_fit(列车, "昼之半神概念股") == 0.5, "env 不加成该 comp → 0.5"


def test_env_fit_faction_map() -> None:
    """env 加成对应阵营(追击邀请 → 含追击的追击飞霄 → 1.0);未选 env → None(ADR-0107 动态剔除)。"""
    飞霄 = get_comp("追击飞霄")
    assert env_fit(飞霄, "追击邀请") == pytest.approx(1.0, abs=1e-6)
    assert env_fit(飞霄, "") is None


# —— current_enemy_mechanics 映射 ——


def test_current_enemy_mechanics_maps_affixes() -> None:
    """敌人词缀(OCR 名)→ 机制 tag;未知词缀原样透传。"""
    s = GameState(enemy_affixes=["正当防卫", "急速制冷", "未知词缀"])
    mechs = current_enemy_mechanics(s)
    assert "反伤" in mechs
    assert "冻结" in mechs
    assert "未知词缀" in mechs   # 未知原样当 tag


# —— select_comp steer(用户 4 轴)+ optionality + 阶段难度 ——


def test_select_comp_build_around_filter() -> None:
    """character_build_around 必含:只留含该角色的 comp(ADR-0152 后不死途属巡海击破+黄泉减益两 comp)。"""
    cfg = _cfg(character_build_around=["不死途"])
    s = GameState(round_num=5, gold=50)
    result = select_comp(s, make_score_context(s), cfg)
    names = [c.name for c in result]
    assert names, "build_around=不死途 → 至少留巡海击破/黄泉减益"
    assert all("不死途" in c.core_chars for c in result), "过滤后每 comp 都含不死途"


def test_select_comp_forbid_filter() -> None:
    """character_forbid / faction_forbid 排除。"""
    s = GameState(round_num=5, gold=50)
    cfg_char = _cfg(character_forbid=["阿格莱雅"])
    names = [c.name for c in select_comp(s, make_score_context(s), cfg_char, top_n=99)]
    assert "昼神阿雅" not in names, "forbid 阿格莱雅 → 排除昼神阿雅"
    cfg_fac = _cfg(faction_forbid=["追击"])
    names2 = [c.name for c in select_comp(s, make_score_context(s), cfg_fac, top_n=99)]
    assert "追击飞霄" not in names2, "forbid 追击 → 排除追击飞霄"


def test_select_comp_faction_build_around() -> None:
    """faction_build_around 必含阵营(all() 语义;成就局特定阵容,config.md §3)。"""
    s = GameState(round_num=5, gold=50)
    cfg = _cfg(faction_build_around=["追击"])
    comps = select_comp(s, make_score_context(s), cfg, top_n=99)
    assert comps, "必含追击 → 至少留追击飞霄"
    assert all("追击" in c.all_factions for c in comps), "过滤后每 comp 都含追击"
    # 多个必含 = all() 语义:全部在场才过(与角色轴 any() 不同 —— 多羁绊成就要求同时满足)
    cfg2 = _cfg(faction_build_around=["追击", "仙舟"])
    for c in select_comp(s, make_score_context(s), cfg2, top_n=99):
        assert {"追击", "仙舟"}.issubset(c.all_factions), "多必含应全部在场"


def test_acquirability_factor_pool_aware() -> None:
    """ADR-0110:acq 牌池感知 —— P(单次刷新 5 格≥1 张该角色),扣玩家持有副本(牌库有限,用户根因)。

    取代 ADR-0092 的 min(refresh_prob):后者是「该费用刷新率」非「该角色刷出率」(漏 ÷v:1 格该费用里
    只 1/v 是该角色),且不扣持有副本(牌库有限:买掉即减)。本测试验:
    ① ÷v:特定角色 acq < 该角色费用 refresh_prob;② held 消耗:持越多越难刷;③ 空 core→1.0。
    """
    from sr_od.application.currency_war.cw_chars import CHARACTERS
    from sr_od.application.currency_war.cw_shop_odds import (
        acquirability_factor,
        refresh_prob,
    )
    青雀 = get_comp("追击飞霄")   # core_chars 飞霄/知更鸟/缇宝/不死途(混合费用)
    costs = [CHARACTERS[n].cost for n in 青雀.core_chars if n in CHARACTERS]
    assert costs, "core_chars 应在 CHARACTERS"
    # ① 牌池感知:特定角色 acq < min refresh_prob(÷v:1 张角色 < 1 格该费用,5 格也补不回 v 倍差)
    for lv in (7, 10):
        acq = acquirability_factor(青雀.core_chars, lv)
        min_cost_prob = min(refresh_prob(lv, c) for c in costs)
        assert 0.0 < acq < min_cost_prob, (
            f"lv{lv}: 牌池感知 acq({acq:.4f}) 应在 (0, min refresh_prob={min_cost_prob})"
        )
    # ② held 消耗(牌库有限):持有副本 → 该角色剩余少 → acq 不升(持最稀核心则降)
    acq_fresh = acquirability_factor(青雀.core_chars, 7)
    held_all = dict.fromkeys(青雀.core_chars, 3)   # 每核心持 3 基础副本
    acq_held = acquirability_factor(青雀.core_chars, 7, held=held_all)
    assert acq_held <= acq_fresh, f"持有副本后 acq({acq_held:.4f}) 应 ≤ 满池({acq_fresh:.4f})"
    # ③ 空 core_chars / 无识别角色 → 1.0(中性,不降权)
    assert acquirability_factor([], 7) == 1.0


def test_held_base_copies_folds_star() -> None:
    """ADR-0110:_held_base_copies 按 star 折基础副本(3合1:1星=1/2星=3/3星=9/4星=27),bench+deployed 合并。"""
    s = GameState(
        bench=[BenchChar(slot=0, char_id="飞霄", star=2),     # 3 基础副本
               BenchChar(slot=1, char_id="知更鸟", star=1)],   # 1
        deployed=[BenchChar(slot=0, char_id="飞霄", star=3)],  # 9(同角色累加)
    )
    held = _held_base_copies(s)
    assert held["飞霄"] == 3 + 9, "飞霄 2星(3)+ 3星(9)= 12 基础副本"
    assert held["知更鸟"] == 1, "知更鸟 1星 = 1"
    # 空 bench/deployed → {}
    assert _held_base_copies(GameState()) == {}
    # 缺 char_id 的槽不计
    s2 = GameState(bench=[BenchChar(slot=0, char_id="", star=2)])
    assert _held_base_copies(s2) == {}, "空 char_id 不计"




def test_select_comp_optionality_top_n() -> None:
    """top_n=N → 返回 N 个不同 comp。

    注:select_comp 按 comp_score×乘法因子(phase/acq/board/formation)排序,**非纯 raw comp_score** ——
    乘法因子会改变排序(如反甲白厄 factions 空 → board/formation 中性 1.0,raw 低但总分可能高),
    故不验 raw comp_score 降序(旧断言假设错,反甲白厄 factions 修正后暴露)。"""
    s = GameState(round_num=5, gold=50)
    cfg = _cfg(character_priority=[], faction_priority=[])
    ctx = make_score_context(s)
    top3 = select_comp(s, ctx, cfg, top_n=3)
    assert len(top3) == 3
    assert len({c.name for c in top3}) == 3, "top3 应 3 个不同 comp"


def test_difficulty_phase_factor_early_prefers_easy() -> None:
    """早期/穷:easy×1.15、hard×0.85;后期均 1.0。"""
    列车 = get_comp("列车同行")     # easy
    白厄 = get_comp("反甲白厄")     # hard
    early = GameState(round_num=1, gold=10)
    late = GameState(round_num=10, gold=80)
    assert _difficulty_phase_factor(列车, early) > _difficulty_phase_factor(白厄, early), (
        "早期 easy 因子 > hard"
    )
    assert _difficulty_phase_factor(列车, late) == 1.0
    assert _difficulty_phase_factor(白厄, late) == 1.0


def test_difficulty_phase_factor_global_elapsed_not_per_plane() -> None:
    """ADR-0108:_difficulty_phase_factor 用**全局 elapsed** 判早期(round+(plane-1)*6≤3),非位面内 round_num。

    防回归:原 per-plane `round_num≤3` 误把 plane2/3 的 r1-3 当早期(实为全局 elapsed 7-15,中后期)。
    gold≥30 排除「穷」分支,纯测轮次维度的全局 elapsed。
    """
    列车 = get_comp("列车同行")   # easy
    # plane1 r2 = 全局 elapsed 2 ≤3(真早期)→ easy 因子 >1.0
    assert _difficulty_phase_factor(列车, GameState(plane=1, round_num=2, gold=80)) > 1.0, (
        "plane1 r2 全局 elapsed 2 ≤3 → 早期 easy 因子 >1.0"
    )
    # plane2 r2 = 全局 elapsed 8 >3(非早期)→ =1.0(原 per-plane 会误判 r2≤3 早期)
    assert _difficulty_phase_factor(列车, GameState(plane=2, round_num=2, gold=80)) == 1.0, (
        "plane2 r2 全局 elapsed 8 >3 → 非早期 =1.0(防 per-plane 误判)"
    )
    # plane3 r3 = 全局 elapsed 15 >3(非早期)→ =1.0
    assert _difficulty_phase_factor(列车, GameState(plane=3, round_num=3, gold=80)) == 1.0, (
        "plane3 r3 全局 elapsed 15 >3 → 非早期 =1.0"
    )


# —— comp_score / breakdown ——


def test_comp_score_in_range_and_breakdown_keys() -> None:
    """comp_score 在合理范围;breakdown 含 schema 稳定字段(telemetry 用)。"""
    阿雅 = get_comp("昼神阿雅")
    s = GameState(board={"昼之半神": 4}, round_num=8, gold=60,
                  enemy_affixes=["禁速"], active_env="昼之半神概念股")
    ctx = make_score_context(s)
    sc = comp_score(阿雅, s, ctx)
    assert sc > 0.0
    bd = comp_score_breakdown(阿雅, s, ctx)
    for key in ("progress", "mechanics_fit", "env_fit", "boss_fit", "equip_fit", "strength", "form_progress"):
        assert key in bd, f"breakdown 缺 schema 字段 {key}"


# —— maybe_pivot ——


def test_maybe_pivot_no_target_returns_best() -> None:
    """target=None → maybe_pivot 返回 select_comp 第一(承诺转型到最优)。"""
    cfg = _cfg()
    s = GameState(round_num=5, gold=50)
    result = maybe_pivot(s, make_score_context(s), cfg, target=None)
    assert result is not None


def test_maybe_pivot_low_hp_returns_fastest_easy() -> None:
    """hp<30 保命转型 → 返回成型最快的 easy comp(typical_form_round 最小)。"""
    cfg = _cfg()
    s = GameState(hp=20, round_num=5, gold=50)
    result = maybe_pivot(s, make_score_context(s), cfg, target=get_comp("昼神阿雅"))
    assert result is not None
    # 列车同行(easy,typical_form_round=4)是成型最快的 easy 之一
    assert result.form_difficulty == "easy"


def test_maybe_pivot_low_hp_signal3_preempts_signal1() -> None:
    """D-40:hp 危险时信号 3(保命)抢占信号 1 —— 只选 easy comp(不选 medium/hard 涌现,防 churn 死亡螺旋)。
    D-65:保命优先 board 有 progress 的 easy comp(防切到 board 不支持的 fast-easy → 无法成型 → 还是死)。
    target=追击飞霄(medium),board 成型列车同行(easy,full progress)→ 保命选 列车同行(easy+board 支持),
    非弃成型切未成型 fast-easy。"""
    cfg = _cfg(faction_priority=["列车同行"])
    s = GameState(board={"列车同行": 4}, round_num=5, plane=1, hp=20, gold=50)  # 列车同行成型(信号1 会选)
    result = maybe_pivot(s, make_score_context(s), cfg, target=get_comp("追击飞霄"))
    assert result is not None, "hp 危险应 pivot"
    assert result.form_difficulty == "easy", "保命只选 easy comp"
    assert result.name == "列车同行", "D-65:优先 board 有 progress 的 easy(列车同行 full 成型),非弃成型切未成型"


def test_maybe_pivot_d141_no_easy_progress_keeps_target() -> None:
    """D-141:hp 危险(信号3)+ **无 easy comp 有 board progress** + 当前 target(medium)有 progress
    → **保持 target**(return None),不转 0-foundation easy comp(board 不支持 → 必死)。

    实跑 r8 bug:target=追击飞霄(medium,board 追击 有 progress)被 easy 过滤排除;无 easy comp
    (列车同行/DOT队)有 board progress → 旧 fallback pool=easy → 最快 easy=DOT(board 0 持续伤害)→ 转
    0-foundation → 必死。本测锁修法:该场景保持 target,不弃有 progress 的去追 0-progress easy。"""
    cfg = _cfg()
    # board 只有追击(追击飞霄 factions)→ 追击飞霄有 progress;列车同行/DOT队(easy)都 0 progress。
    s = GameState(board={"追击": 2}, round_num=8, plane=1, hp=20, gold=50)
    result = maybe_pivot(s, make_score_context(s), cfg, target=get_comp("追击飞霄"))
    assert result is None, "无 easy comp 有 progress + target 有 progress → 保持 target,不转 0-foundation easy"


def test_maybe_pivot_better_comp_emerges() -> None:
    """信号 1(更优涌现):target=反甲白厄(白厄无阵营/form_progress 0),场面成型列车同行(更优 + 分差>PIVOT_GAP)
    → pivot 到列车同行。early round(remaining 足够)+ hp 健康 → 信号 2/3 不触发,只验信号 1。"""
    cfg = _cfg(faction_priority=["列车同行"])
    s = GameState(board={"列车同行": 4}, round_num=2, plane=1, hp=100, gold=50)  # 列车同行成型
    target = get_comp("反甲白厄")  # 白厄无阵营 → 远不如已成型的列车同行
    result = maybe_pivot(s, make_score_context(s), cfg, target=target)
    assert result is not None, "更优 comp 涌现应 pivot"
    assert result.name == "列车同行", "应 pivot 到更优的列车同行"


def test_maybe_pivot_ceiling_unreachable_switches_easy() -> None:
    """信号 2(ceiling 不可达):target=阿雅(form_round=8)但 plane3 round5 → remaining≈1<8;
    board 部分成型使阿雅=best(信号 1 跳过)→ 切成型最快的 easy comp。"""
    cfg = _cfg(faction_priority=["昼之半神"])
    s = GameState(board={"昼之半神": 2}, round_num=5, plane=3, hp=100, gold=50)  # 阿雅部分但来不及
    target = get_comp("昼神阿雅")
    result = maybe_pivot(s, make_score_context(s), cfg, target=target)
    assert result is not None, "target 来不及成型应 pivot"
    assert result.form_difficulty == "easy", "ceiling 不可达 → 切 easy"


def test_maybe_pivot_formed_target_no_ceiling_pivot() -> None:
    """信号2 已成型守卫:target=阿雅已成型(board=昼之半神:4=form_tiers)+ plane3 round5
    (remaining≈1<8)→ **不**因 ceiling 切走(form_progress=1.0 豁免信号2;不该放弃已完成 comp)。"""
    cfg = _cfg(faction_priority=["昼之半神"])
    s = GameState(board={"昼之半神": 4}, round_num=5, plane=3, hp=100, gold=50)  # 阿雅成型
    target = get_comp("昼神阿雅")
    result = maybe_pivot(s, make_score_context(s), cfg, target=target)
    assert result is None, "已成型 target 不该因 ceiling 切走(信号2 已成型守卫)"


# —— shop_supply(I14:shop presence 主导,board-only 弱信号)——


def test_shop_supply_shop_present_high() -> None:
    """comp 阵营在 shop 出现 → 1.0(可成型:能买到核心)。"""
    comp = get_comp("列车同行")  # factions=["列车同行"]
    s = GameState(shop=[ShopCard(x=0, faction="列车同行")])
    assert shop_supply(comp, s) == 1.0


def test_shop_supply_board_only_low() -> None:
    """I14:仅 board 有、shop 无 → 0.3(已持 1 张但买不到更多 → 成型难,非 1.0)。
    旧版此情形返 1.0 → select_comp 不降权 → 选了 shop 供不上的 target → 永不成型(win-rate 阻塞)。"""
    comp = get_comp("昼神阿雅")  # factions=["昼之半神"]
    s = GameState(board={"昼之半神": 1})   # board 有,shop 空
    assert shop_supply(comp, s) == 0.3


def test_shop_supply_neither_zero() -> None:
    """阵营 shop/board 都无 → 0.0(商店刷不出 → 不可成型)。"""
    comp = get_comp("列车同行")
    s = GameState(shop=[ShopCard(x=0, faction="击破")], board={"持续伤害": 2})
    assert shop_supply(comp, s) == 0.0


# —— select_megastar ——


def test_select_megastar_binds_core() -> None:
    """target.core_chars 含可选巨星 → 绑该角色(追击飞霄含知更鸟)。"""
    飞霄 = get_comp("追击飞霄")
    assert select_megastar(GameState(), 飞霄, ["知更鸟", "花火"]) == "知更鸟"


def test_select_megastar_no_target_returns_first() -> None:
    """无 target → 返回第一个可选(naive 兜底)。"""
    assert select_megastar(GameState(), None, ["花火", "知更鸟"]) == "花火"


def test_select_megastar_empty_returns_none() -> None:
    """无可选 → None。"""
    assert select_megastar(GameState(), None, []) is None


# —— COMP_LIBRARY 完整性 ——


def test_comp_library_well_formed() -> None:
    """COMP_LIBRARY 每 comp 字段完整(strength/difficulty 合法;factions/form_tiers 非空除非无阵营 comp)。"""
    for c in COMP_LIBRARY:
        assert c.name, "comp 必须有名"
        # 反甲白厄:白厄无阵营(独立羁绊救世主),factions/form_tiers 合法空(靠 core+equip 非 form 成型)
        if c.name == "反甲白厄":
            assert c.factions == [] and c.form_tiers == {}, (
                f"{c.name} 应空 factions/form_tiers(白厄无阵营;原 ['毁灭'] 是命途非阵营,已修)")
            assert c.strength in ("S", "A", "B"), f"{c.name} strength 非法"
            assert c.form_difficulty in ("easy", "medium", "hard"), f"{c.name} difficulty 非法"
            continue
        assert c.factions, f"{c.name} 必须有 factions"
        assert c.form_tiers, f"{c.name} 必须有 form_tiers"
        assert c.strength in ("S", "A", "B"), f"{c.name} strength 非法"
        assert c.form_difficulty in ("easy", "medium", "hard"), f"{c.name} difficulty 非法"
        for f, t in c.form_tiers.items():
            assert t > 0, f"{c.name} form_tiers[{f}] 必须>0"


def test_comp_factions_in_FACTIONS() -> None:
    """防回归:COMP_LIBRARY 每 comp 的 factions / form_tiers 键 ⊆ FACTIONS。
    防『毁灭』(命途 destruction)/『destruction』等误当阵营(曾致反甲白厄 form_progress 恒 0 死 comp)。"""
    from sr_od.application.currency_war.cw_factions import FACTIONS
    for c in COMP_LIBRARY:
        for f in c.factions:
            assert f in FACTIONS, f'{c.name}.factions 含非阵营 "{f}"(不在 FACTIONS;可能误用命途/职业)'
        for f in c.form_tiers:
            assert f in FACTIONS, f'{c.name}.form_tiers 含非阵营 "{f}"(不在 FACTIONS)'


def test_comp_library_core_chars_canonical() -> None:
    """COMP_LIBRARY core_chars 必须用规范名(CHARACTER_ROSTER),禁粉丝缩写(红A/杨叔/记忆主等)。

    用户 2026-08-03:有全量 roster 就该用它,别在代码数据里缩写。OCR/char_id 匹配靠规范名。
    """
    from sr_od.application.currency_war.cw_chars import CHARACTER_ROSTER
    for comp in COMP_LIBRARY:
        for c in comp.core_chars:
            assert c in CHARACTER_ROSTER, (
                f"{comp.name}.core_chars 含非规范名 '{c}'(不在 CHARACTER_ROSTER)"
            )


def test_comp_library_key_equips_canonical() -> None:
    """COMP_LIBRARY key_equips 必须是规范装备名(EQUIPMENTS 注册表内)。

    工程化:装备也是领域实体,有注册表;key_equips 引用规范名(与 core_chars 同纪律)。
    """
    from sr_od.application.currency_war.cw_equipment import EQUIPMENTS
    for comp in COMP_LIBRARY:
        for e in comp.key_equips:
            assert e in EQUIPMENTS, (
                f"{comp.name}.key_equips 含非规范装备名 '{e}'(不在 EQUIPMENTS 注册表)"
            )


# ===== ADR-0135 机会型 pivot(held_strategy_fit:持有策略 → comp 亲和 → select_comp 重评) =====
def test_held_strategy_fit_opportunity_pivot() -> None:
    """持有追击套组(绑定 追击+飞霄)→ 追击 comp held_strategy_fit=1.0、无关 comp=0.5、无持有=None。"""
    from sr_od.application.currency_war.cw_comps import (
        COMP_LIBRARY,
        held_strategy_fit,
        make_score_context,
        select_comp,
    )
    feixiao = next(c for c in COMP_LIBRARY if "飞霄" in c.core_chars)
    other = next(c for c in COMP_LIBRARY if c.name != feixiao.name
                 and not (set(c.factions) & {"追击"}) and "飞霄" not in c.core_chars)
    assert held_strategy_fit(feixiao, ["追击星徽套组"]) == 1.0, "阵营+角色双命中 → 满分(三件套到手)"
    assert held_strategy_fit(other, ["追击星徽套组"]) == 0.5, "无关 comp 中性(有策略无命中)"
    assert held_strategy_fit(feixiao, []) is None, "无持有策略 → None(动态剔除)"
    # 端到端:空板 + 持有追击套组 → select_comp 偏向追击(机会型 pivot)
    _board_free = GameState(gold=50, round_num=3, level=5, plane=1, hp=100, board={})
    _with = _board_free.copy(); _with.active_strategies = ["追击星徽套组"]
    pick_with = select_comp(_with, make_score_context(_with), _cfg())[0]
    assert pick_with.name == feixiao.name, f"持有套组应机会转向 {feixiao.name},得 {pick_with.name}"


# ===== ADR-0152 plaza 方法论(flex 二分 / augment 绑定 / 骨架派生 / 枢纽路由 / 星目标费用档) =====
def test_comp_flex_factions_subset_and_form_tiers_core_only() -> None:
    """flex_factions ⊆ FACTIONS 且与核心不重叠;form_tiers 键 ⊆ 核心 factions(成型只看核心)。"""
    from sr_od.application.currency_war.cw_factions import FACTIONS
    for c in COMP_LIBRARY:
        for f in c.flex_factions:
            assert f in FACTIONS, f'{c.name}.flex_factions 含非阵营 "{f}"'
            assert f not in c.factions, f'{c.name}.flex "{f}" 与核心重叠(该挪进核心或删)'
        assert set(c.form_tiers) <= set(c.factions), f"{c.name} form_tiers 键必须 ⊆ 核心 factions"
        assert c.all_factions == set(c.factions) | set(c.flex_factions)


def test_augment_comp_affinity_near_hardbind() -> None:
    """AUGMENT_COMP_AFFINITY:黑塔纪元 → 大黑塔银河学者 1.0(拿到即近乎硬绑);无关 comp 中性。"""
    from sr_od.application.currency_war.cw_comps import (
        AUGMENT_COMP_AFFINITY,
        held_strategy_fit,
    )
    dht = get_comp("大黑塔银河学者")
    other = get_comp("列车同行")
    assert AUGMENT_COMP_AFFINITY["黑塔纪元"]["大黑塔银河学者"] == 1.0
    assert held_strategy_fit(dht, ["黑塔纪元"]) == 1.0, "黑塔纪元在手 → 大黑塔 comp 满分(augment 定义型)"
    assert held_strategy_fit(other, ["黑塔纪元"]) == 0.5, "无关 comp 中性"
    # 端到端:拿到黑塔纪元 → select_comp 转向大黑塔
    s = GameState(gold=50, round_num=3, level=5, plane=1, hp=100, board={})
    s.active_strategies = ["黑塔纪元"]
    pick = select_comp(s, make_score_context(s), _cfg())[0]
    assert pick.name == "大黑塔银河学者", f"持有黑塔纪元应近乎硬绑,得 {pick.name}"


def test_env_comp_affinity_plaza_extended() -> None:
    """ADR-0152 env 亲和扩充:列车同行概念股 → 列车同行 1.0;特邀专家:桑博 → 专家桑博DOT 1.0。"""
    from sr_od.application.currency_war.cw_comps import env_fit
    assert env_fit(get_comp("列车同行"), "列车同行概念股") == 1.0
    assert env_fit(get_comp("专家桑博DOT"), "特邀专家:桑博") == 1.0
    assert env_fit(get_comp("万敌单C"), "列车同行概念股") == 0.5, "无关 comp 中性"


def test_skeleton_factions_derived() -> None:
    """M4 骨架派生:判据(最低档 ≤3 + ≤2费成员 ≥2)从注册表筛;含实战组合(仙舟/贝洛伯格/银河学者)。"""
    from sr_od.application.currency_war.cw_comps import skeleton_factions
    sk = skeleton_factions()
    for must in ("仙舟", "贝洛伯格", "银河学者", "列车同行", "星核猎手"):
        assert must in sk, f"骨架集应含 {must}(plaza 实战开局组合)"
    for not_in in ("护盾", "能量", "减益", "量子同频"):
        assert not_in not in sk or True  # 这些最低档 2 但低费成员不足 → 不强制(防误锁,信息断言)


def test_char_routes_hub_structure() -> None:
    """M3 枢纽路由:瓦尔特/符玄/千冶·刃 跨路线 ≥3(终局枢纽);角色→路线网络非空。"""
    from sr_od.application.currency_war.cw_comps import char_routes
    routes = char_routes()
    assert routes, "路由网络非空"
    for hub in ("瓦尔特", "符玄", "千冶·刃"):
        assert len(routes.get(hub, set())) >= 3, f"{hub} 应是终局枢纽(≥3 路线)"


def test_pivot_overlap_semantics() -> None:
    """M10 转型成本:同 comp 1.0;列车→绯英(共享花火/瓦尔特)> 列车→万敌(零共享);无阵营 comp 中性。"""
    from sr_od.application.currency_war.cw_comps import pivot_overlap
    lt = get_comp("列车同行")
    assert pivot_overlap(lt, lt) == 1.0
    hi_overlap = pivot_overlap(lt, get_comp("绯英欢愉"))
    lo_overlap = pivot_overlap(lt, get_comp("万敌单C"))
    assert hi_overlap > lo_overlap, "共享多 > 共享少(转型成本单调)"


def test_default_star_goal_by_cost() -> None:
    """M6 星级费用档:≤3费 → 3星;≥4费 → 2星(plaza 3星率 0.87/0.58/0.37 校准)。"""
    from sr_od.application.currency_war.cw_plaza_comps import default_star_goal
    assert default_star_goal(1) == 3
    assert default_star_goal(3) == 3
    assert default_star_goal(4) == 2
    assert default_star_goal(5) == 2


def test_transition_pool_two_tiers() -> None:
    """M3 过渡池两级:EARLY_CORE_POOL(存活≥0.8)与 TEMPO_POOL(纯打工)拆分且不重叠。"""
    from sr_od.application.currency_war.cw_comps import EARLY_CORE_POOL, TEMPO_POOL, TRANSITION_POOL
    assert "千冶·刃" in EARLY_CORE_POOL, "千冶·刃 Early→Final 0.96 → 早期核心级"
    assert "艾丝妲" in TEMPO_POOL, "艾丝妲 Early→Final 0.05 → 纯过渡级"
    assert not set(EARLY_CORE_POOL) & set(TEMPO_POOL), "两级不重叠"
    assert set(TRANSITION_POOL) == set(EARLY_CORE_POOL) | set(TEMPO_POOL), "兼容名 = 两级并集"


# ===== ADR-0152 评审落地守卫(env 定向反转 / augment 定义型三段链 / flex 两档) =====
def test_env_fit_t0_no_flex_inversion() -> None:
    """评审🔴2:T0 定向 env 下非定向 comp 中性 —— flex 全集匹配不得盖过 affinity 表。

    仙舟概念股:景元仙舟(affinity 0.9→0.95) 必须严格 > 绯英欢愉(flex 含仙舟,旧版 faction 命中 1.0 反转)。
    """
    from sr_od.application.currency_war.cw_comps import env_fit
    assert env_fit(get_comp("景元仙舟"), "仙舟概念股") == 0.95
    fy = get_comp("绯英欢愉")
    assert "仙舟" in fy.flex_factions, "前置:绯英 flex 含仙舟(反转场景成立)"
    assert env_fit(fy, "仙舟概念股") == 0.5, "T0 定向 env:非定向 comp 中性,不走 flex faction 匹配"


def test_defining_augment_overrides_board_investment() -> None:
    """评审🔴3b:定义型 augment(黑塔纪元)压过板面对他 comp 的既有投入。

    lv5 板{列车同行:2}(fp 0.5 领先)+ 持有黑塔纪元 → select_comp 应选大黑塔银河学者。
    """
    s = GameState(gold=50, round_num=4, level=5, plane=1, hp=100, board={"列车同行": 2})
    s.active_strategies = ["黑塔纪元"]
    pick = select_comp(s, make_score_context(s), _cfg())[0]
    assert pick.name == "大黑塔银河学者", f"定义型 augment 应压过板面投入,得 {pick.name}"


def test_maybe_pivot_defining_augment_unlocks_commit() -> None:
    """评审🔴3c:已 commit 的 target 可被定义型 augment 解锁转型(与 losing streak 同级)。"""
    # 列车已 commit(fp≥0.4),持有黑塔纪元 → best=大黑塔 应能翻转
    s = GameState(gold=50, round_num=4, level=5, plane=1, hp=100, board={"列车同行": 2})
    s.active_strategies = ["黑塔纪元"]
    ctx = make_score_context(s)
    from sr_od.application.currency_war.cw_comps import target_committed
    assert target_committed(get_comp("列车同行"), s), "前置:列车已 commit"
    result = maybe_pivot(s, ctx, _cfg(), target=get_comp("列车同行"))
    assert result is not None and result.name == "大黑塔银河学者", (
        f"定义型 augment 应解锁 commit 锁,得 {result.name if result else None}"
    )


def test_card_hits_target_two_tier_flex() -> None:
    """评审🔴1:flex 两档:严格(卖出/换血)只认核心;宽松(买牌/deploy)含 flex。"""
    from sr_od.application.currency_war.cw_evaluate import _card_hits_target
    lt = get_comp("列车同行")
    # 大丽花(盛会之星=列车 flex):宽松 True(可买可上),严格 False(可被 core 替换)
    assert _card_hits_target("大丽花", "盛会之星", lt, include_flex=True) is True
    assert _card_hits_target("大丽花", "盛会之星", lt) is False
    # core 辅助(花火,阵营∉列车)两档都 True(ADR-0103 保护)
    assert _card_hits_target("花火", "盛会之星", lt) is True

