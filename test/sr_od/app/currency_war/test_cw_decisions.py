"""货币战争 策略决策(评估函数 + 贪心)测试 —— 纯逻辑,不依赖游戏/百科数据。

验证 cw_decisions 架构:eval 单调性、plan 硬门(gold≥0 / bench-full 必破 / level≤10)、
站位分流、3合1升星、凑整吃息跨档、char_quality 计已上阵、事件白名单/dot 主流派、
economy_mode、boss 克制。用 mock config(SimpleNamespace)避免 config IO。
"""
from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.cw_comps import Comp
from sr_od.application.currency_war.cw_economy import (
    WIN_STREAK_BREAK_INTEREST,
    _expected_level,
    _refresh_cost,
    clicks_to_next_level,
    economy_score,
    get_node_goal,
    xp_click_cost,
)
from sr_od.application.currency_war.cw_evaluate import (
    MAX_REFRESH_PER_ROUND,
    OPTIONALITY_WEIGHT,
    TARGET_PROGRESS_WEIGHT,
    TRANSITION_TEMPO_BONUS,
    _economy_mode_for,
    _phase_weights,
    _refresh_cap,
    _should_save_for_interest,
    _target_progress_remaining,
    alpha_t,
    char_quality_score,
    evaluate,
    optionality_score,
    synergy_score,
    transition_tempo_score,
)
from sr_od.application.currency_war.cw_events import (
    EncounterOption,
    SupplyOption,
    _option_rarity,
    decide_encounter,
    decide_event,
    decide_supply,
)
from sr_od.application.currency_war.cw_plan import (
    REINFORCE_BONUS,
    SPREAD_PENALTY,
    _bench_faction_counts,
    _concentration_delta,
    _distinct_factions,
    _maybe_sell_for_interest,
    _pick_deploy_row,
    _sample_cost,
    _sample_shop,
    _should_deploy,
    level_up_gate,
    plan,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    DeployMove,
    GameState,
    LevelUp,
    RefreshShop,
    SellBench,
    ShopCard,
    effective_hp_threshold,
    simulate,
)


def _cfg(**overrides) -> SimpleNamespace:
    """mock CurrencyWarConfig(纯属性,evaluate/plan 用 getattr 读)。"""
    base = {
        "faction_priority": ["贝洛伯格", "仙舟", "巡海游侠"],
        "character_priority": ["阿格莱雅"],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _comp(attrs: list[str]) -> Comp:
    """构造测试 comp(控 mechanic_attributes,验 mechanics_fit 克/利)。"""
    return Comp(name="t", factions=["燃血"], core_chars=[], form_tiers={"燃血": 4},
                strength="A", form_difficulty="medium", mechanic_attributes=attrs)


def _comp_key(key_equips: list[str]) -> Comp:
    """构造测试 comp(控 key_equips,验 decide_supply key 契合)。"""
    return Comp(name="t", factions=[], core_chars=[], form_tiers={},
                strength="A", form_difficulty="medium", key_equips=key_equips)


# —— eval 单调性 ——


def test_synergy_more_tiers_higher() -> None:
    """同阵营,激活更高 tier → 更高分。巡海游侠 tiers=(1,2,3,4)。"""
    cfg = _cfg()
    s2 = GameState(board={"巡海游侠": 2})
    s4 = GameState(board={"巡海游侠": 4})
    assert synergy_score(s4, cfg.faction_priority) > synergy_score(s2, cfg.faction_priority)


def test_synergy_combat_over_support() -> None:
    """同人数,战力型 > 辅助型。巡海游侠(combat) vs 星间旅人(support)。"""
    cfg = _cfg()
    combat = GameState(board={"巡海游侠": 1})
    support = GameState(board={"星间旅人": 1})
    assert synergy_score(combat, cfg.faction_priority) > synergy_score(support, cfg.faction_priority)


def test_economy_interest() -> None:
    """中期,存金近 50 > 存金 0(利息加分)。"""
    rich = GameState(gold=50, round_num=5, level=6, plane=2)
    poor = GameState(gold=0, round_num=5, level=6, plane=2)
    assert economy_score(rich, "adaptive") > economy_score(poor, "adaptive")


def test_economy_streak_bonus() -> None:
    """C 杠杆 2(streak 接线)。ADR-0128(复查 #5,核心机制:27):货币战争**无连败补偿** ——
    只计连胜方向;连败 0 分(旧 magnitude 对称计 = 虚构连败金,已修)。
    """
    base = GameState(gold=50, round_num=5, level=6, plane=2)             # streak 默认 0
    win3 = GameState(gold=50, round_num=5, level=6, plane=2, streak=3)   # 连胜 3
    loss3 = GameState(gold=50, round_num=5, level=6, plane=2, streak=-3)  # 连败 3
    assert economy_score(win3, "adaptive") > economy_score(base, "adaptive"), "连胜 3 > 无 streak"
    assert economy_score(loss3, "adaptive") == pytest.approx(economy_score(base, "adaptive")), (
        "无连败补偿:连败 3 不加分(核心机制:27)"
    )


def test_get_node_goal_node_plan_rules() -> None:
    """node_plan 骨架(14 §2):节点 → NodeGoal target_level / spend_mode(人玩节奏)。"""
    assert (get_node_goal(1, 1).target_level, get_node_goal(1, 1).spend_mode) == (4, "saving"), "P1 早期 冲Lv4 攒息"
    assert (get_node_goal(1, 5).target_level, get_node_goal(1, 5).spend_mode) == (6, "interest"), "P1 中期 Lv6 吃息"
    assert (get_node_goal(2, 5).target_level, get_node_goal(2, 5).spend_mode) == (8, "level"), "P2 中后期 lv8(H4 软化:M8 lv9 锚点疑幽灵)"
    assert (get_node_goal(3, 1).target_level, get_node_goal(3, 1).spend_mode) == (9, "allin"), "P3 早期 上 9"
    assert (get_node_goal(3, 5).target_level, get_node_goal(3, 5).spend_mode) == (10, "allin"), "P3 后期 上 10"


def test_get_node_goal_fallback() -> None:
    """未匹配(plane>3 / round 超区间)→ fallback:target_level=_expected_level, spend_mode=adaptive。"""
    fb = get_node_goal(4, 1)   # plane 4 无规则(CW 3 位面)→ fallback
    assert fb.target_level == _expected_level(1, 4)
    assert fb.spend_mode == "adaptive"


def test_maybe_sell_for_interest_allin_skips() -> None:
    """node_plan spend_mode allin(P3)→ _maybe_sell_for_interest 跳过(花光成型不囤息;14 §2.2)。"""
    cfg = _cfg()
    # P3 round 3 → allin;gold 39 + 可卖 bench(飞霄,refund 1 → 跨 40 档)→ 正常会卖,allin 跳过
    state = GameState(gold=39, round_num=3, level=9, plane=3,
                      bench=[BenchChar(slot=0, char_id='飞霄', faction='追击', star=1)])
    actions: list = []
    _maybe_sell_for_interest(state, actions, cfg.character_priority, cfg)
    assert not any(isinstance(a, SellBench) for a in actions), "P3 allin → 不卖息(花光成型)"


def test_sample_cost_uses_refresh_prob() -> None:
    """A4.3:_sample_cost 用 REFRESH_PROB 权威表(Lv1-3 纯 1 费;Lv4 只 1/2/3 费;Lv10 不出表外)。"""
    rng = random.Random(0)
    assert all(_sample_cost(1, rng) == 1 for _ in range(20)), "Lv1 纯 1 费(REFRESH_PROB[1]={1:1.0})"
    for _ in range(50):
        assert _sample_cost(4, rng) in (1, 2, 3), "Lv4 只 1/2/3 费(不出 4/5)"
    for _ in range(50):
        assert 1 <= _sample_cost(10, rng) <= 5, "Lv10 出 1-5 费(不出表外)"


def test_phase_weights_hp_danger_reduces_economy() -> None:
    """A3 + review agent:HP 危险才保血(economy 降权);健康时 economy 不压(snowball 到 50)。
    原"前期 plane1 → economy 0.4"已被研究推翻(前期该 snowball 经济),改测 HP 维度。"""
    cfg = _cfg()
    healthy = GameState(gold=50, round_num=3, level=5, plane=1)         # hp100 健康:economy 权重 1.0
    danger = GameState(gold=50, round_num=3, level=5, plane=1, hp=30)   # hp<HP_DANGER:economy 权重 0.4
    # 同 economy_score(50 金),HP 危险时 economy 降权 → evaluate 总分更低
    assert evaluate(healthy, cfg, cfg.faction_priority) > evaluate(danger, cfg, cfg.faction_priority), (
        "HP 危险时 economy 降权,总分 < 健康(同为 plane1)"
    )


def test_refresh_cap_dynamic() -> None:
    """_refresh_cap 关键回合放宽(review agent + 用户:固定 2 太死)。"""
    base = GameState(gold=50, round_num=3, level=5, plane=1, hp=100)     # 健康前期
    assert _refresh_cap(base) == MAX_REFRESH_PER_ROUND, "健康前期 = 基线 2"
    late = GameState(gold=50, round_num=6, level=8, plane=3, hp=100)     # plane3/升8
    assert _refresh_cap(late) > MAX_REFRESH_PER_ROUND, "plane3/升8 放宽"
    danger = GameState(gold=50, round_num=3, level=5, plane=1, hp=30)    # HP 危险
    assert _refresh_cap(danger) > MAX_REFRESH_PER_ROUND, "HP 危险放宽"

    # ADR-0131:刷新放宽改效果驱动(旧 REFRESH_DISCOUNT_STRATEGIES 名单已删 —— 语义全错)
    # 加油站(每节点 1 次免费刷新)→ 有免费额度 → 放宽
    with_discount = GameState(gold=50, round_num=3, level=5, plane=1, hp=100,
                              active_strategies=['加油站'])
    assert _refresh_cap(with_discount) >= 6, "有免费刷新额度策略 → 放宽到 6"
    # 与关键回合叠加:max(plane3/升8/HP危险=4, 免费额度=6) = 6
    with_discount_late = GameState(gold=50, round_num=6, level=8, plane=3, hp=100,
                                   active_strategies=['高效决策'])   # 9999 次免费刷爆发窗
    assert _refresh_cap(with_discount_late) >= 6, "关键回合 + 免费刷策略 → 仍 ≥6"
    # 无经济效果策略 → 不放宽(验证效果驱动精确,非「持有任意策略」)
    with_non_discount = GameState(gold=50, round_num=3, level=5, plane=1, hp=100,
                                  active_strategies=['羁绊的力量'])
    assert _refresh_cap(with_non_discount) == MAX_REFRESH_PER_ROUND, "无刷新效果策略 → 不放宽"
    # 砂里淘金无刷新经济效果(电表倒转不推荐 bot 玩法,未注册经济效果)
    from sr_od.application.currency_war.cw_investments import economy_effect_of
    assert economy_effect_of('砂里淘金').free_refresh_per_node == 0, "砂里淘金无免费刷新效果"


def test_economy_mode_effects() -> None:
    """economy_mode 只调利息项:rush_level < adaptive < interest_first。"""
    s = GameState(gold=50, round_num=5, level=6, plane=2)
    adaptive = economy_score(s, "adaptive")
    assert economy_score(s, "rush_level") < adaptive, "rush_level 降低利息项"
    assert economy_score(s, "interest_first") > adaptive, "interest_first 抬高利息项"


def test_economy_rush_level_rewards_level() -> None:
    """rush_level 等级项 ×1.5:等级领先时 rush_level > adaptive(review r5 修)。"""
    ahead = GameState(gold=0, round_num=3, level=7, plane=1)   # expected_level(3,1)=5,level=7 领先
    assert economy_score(ahead, "rush_level") - economy_score(ahead, "adaptive") > 0, (
        "等级领先时 rush_level 应 > adaptive(等级项加权)"
    )


def test_evaluate_target_comp_applies_progress() -> None:
    """战略↔战术接法(晚期 α=1):evaluate(target) = evaluate() − WP × 剩余进度。

    成型压力(target_progress)随 α(t) 缩:早期 α=0 不罚(未成型正常),晚期 α=1 全罚。
    故用**晚期**状态(plane3 r6,α=1)验精确关系;早期 α=0 的灵活期权行为见
    ``test_evaluate_optionality_alpha_blend``。target_comp=None 时不扣(向后兼容)。
    """
    from sr_od.application.currency_war.cw_comps import get_comp
    cfg = _cfg()
    飞霄 = get_comp("追击飞霄")   # form_tiers {追击:3}
    # 晚期 α=1(elapsed 18 > R_CLOSE 12)→ target_progress 全罚 + optionality=0
    s_far = GameState(board={}, plane=3, round_num=6)              # 完全没起步 → 剩余 1.0
    s_close = GameState(board={"追击": 3}, plane=3, round_num=6)    # 已成型 → 剩余 0.0
    # _target_progress_remaining:已成型=0,没起步=1
    assert _target_progress_remaining(s_close, 飞霄) == pytest.approx(0.0)
    assert _target_progress_remaining(s_far, 飞霄) == pytest.approx(1.0)
    # evaluate(target) = evaluate() − WP × remaining(α=1 精确关系;optionality=0)
    base_far = evaluate(s_far, cfg, cfg.faction_priority)
    assert (evaluate(s_far, cfg, cfg.faction_priority, target_comp=飞霄)
            == pytest.approx(base_far - TARGET_PROGRESS_WEIGHT * 1.0))
    # 已成型时 target progress 不扣分(剩余 0);T#97 step-2(tuned)target bonus(×1.5 on tier)对 target 阵营加成
    # → evaluate(s_close, target) > base_close(target 阵营 追击 tier ×1.5)。
    base_close = evaluate(s_close, cfg, cfg.faction_priority)
    assert (evaluate(s_close, cfg, cfg.faction_priority, target_comp=飞霄)
            > base_close), "已成型 → progress 不扣分 + target tier bonus → > base_close"
    # 接近成型 > 远离成型(有 target 时,战略导向)
    assert (evaluate(s_close, cfg, cfg.faction_priority, target_comp=飞霄)
            > evaluate(s_far, cfg, cfg.faction_priority, target_comp=飞霄)), (
        "接近 target 成型 → evaluate 更高"
    )


# —— plan 硬门 ——


def test_plan_no_negative_gold() -> None:
    """plan 后 gold 永不为负(模拟执行所有 action)。"""
    cfg = _cfg()
    state = GameState(
        gold=5, round_num=3, level=5, plane=1,
        shop=[ShopCard(x=377, faction="巡海游侠", name="", cost=3),
              ShopCard(x=646, faction="仙舟", name="", cost=3)],
    )
    actions = plan(state, cfg, cfg.faction_priority)
    gold = state.gold
    for a in actions:
        gold = simulate(GameState(gold=gold), a).gold
        assert gold >= 0, f"action {a} 使 gold 变负"


def test_plan_bench_full_sells_when_broke() -> None:
    """bench-full(OCR 标志)且无金升等级 → 必卖最弱破墙。"""
    cfg = _cfg()
    bench = [BenchChar(slot=i, faction="巡海游侠", star=1) for i in range(3)]
    state = GameState(gold=0, round_num=2, level=3, plane=1, bench=bench, bench_full_flag=True)
    actions = plan(state, cfg, cfg.faction_priority)
    assert any(isinstance(a, SellBench) for a in actions), "bench-full 无金时应卖最弱破墙"


def test_plan_bench_full_levels_when_rich() -> None:
    """bench-full(OCR 标志)且金够 → 升等级破墙(而非卖)。"""
    cfg = _cfg()
    bench = [BenchChar(slot=i, faction="巡海游侠", star=1) for i in range(3)]
    state = GameState(gold=100, round_num=2, level=3, plane=1, bench=bench, bench_full_flag=True)
    actions = plan(state, cfg, cfg.faction_priority)
    assert any(isinstance(a, LevelUp) for a in actions), "bench-full 金够时应升等级破墙"


def test_plan_buys_synergy_push() -> None:
    """商店有能推阵营 tier 的牌 → plan 贪心买入。

    状态隔离 level gate(D-24):level=4=期望(4,1)、goal[4]=roll → 不落后期望、不触发 level_up/saving
    (D-24:落后期望会先升等级花掉金 → 买不起;该 level gate 行为另测
    test_plan_levels_when_behind_expected_even_if_goal_roll)。本例只验贪心买牌推 tier。"""
    cfg = _cfg()
    state = GameState(
        gold=20, round_num=1, level=4, plane=1,
        board={"巡海游侠": 2},
        shop=[ShopCard(x=377, faction="巡海游侠", name="", cost=3)],
    )
    actions = plan(state, cfg, cfg.faction_priority)
    assert any(isinstance(a, BuyCard) for a in actions), "能推 tier 的牌应被买入(无 level gate 干预)"


def test_plan_d142_tempo_weak_board_buys_not_save() -> None:
    """D-142 tempo(战力断档)破息:板弱(无 target)+ 板满 + 健康 + gold<50 → **破息买 reinforce**(非 buy0)。

    实跑 match2 r3:board 满+散+gold11+无 target → 旧 _saving_for_interest(gold<50 + 满 + 健康)堵死全部非 target
    买 → 无 target 全堵 → buy0 → 永不集中 → 永无 target → 死循环。D-142 加板强判据(板弱不攒息/级),
    本测锁之:该场景 plan 应买 reinforce(击破 existing→count2→emergent target),非空。"""
    cfg = _cfg()
    state = GameState(
        gold=11, hp=100, round_num=1, level=4, plane=1,
        board={"击破": 1, "追击": 1, "仙舟": 1, "能量": 1},   # 4 阵营各 1(散;无 target → 板弱)
        deployed=[BenchChar(slot=0, faction="击破"),           # deployed 4 = max_units min(4,10)=4(板满)
                  BenchChar(slot=1, faction="追击"),
                  BenchChar(slot=2, faction="仙舟"),
                  BenchChar(slot=3, faction="能量")],
        shop=[ShopCard(x=377, faction="击破", name="", cost=1)],  # reinforce 击破(existing 阵营)
    )
    actions = plan(state, cfg, cfg.faction_priority)   # 无 target_comp → _board_strong=False → 不 _saving
    assert any(isinstance(a, BuyCard) for a in actions), (
        "D-142:板弱(无 target)+ 满 + 健康 + gold<50 → 破息买 reinforce(非 buy0 死循环)"
    )


def test_plan_d79_prefilter_skips_offtarget_priority_for_target() -> None:
    """D-79:commitment prefilter 不再豁免 character_priority 的 off-target 角色。

    target=DOT队(持续伤害/减益),shop 有 阿格莱雅(能量,priority 列,off-target)+ 黄泉(减益,target core),
    gold=3(够黄泉 或 阿格莱雅,非两者)→ 买 target 黄泉(深化 comp),不买 off-target 阿格莱雅。
    旧码(D-79 前)priority 豁免 + buy delta 加 CHAR_PRIORITY_BONUS×2(+16)→ 阿格莱雅 先买 → gold 剩 2
    买不起黄泉 → 漏 target、买 off-target → board spread(plane1-9 实采 7 阵营零成型根因)。
    level=4=期望(1,1)避 level/saving 门,纯验 prefilter。
    """
    target = Comp(name="DOT队", factions=["持续伤害", "减益"],
                  core_chars=["卡芙卡", "桑博", "黄泉"], form_tiers={"持续伤害": 4, "减益": 4},
                  strength="B", form_difficulty="easy")
    cfg = _cfg(character_priority=["阿格莱雅"])   # 阿格莱雅 在 priority(模拟 DEFAULT_CHARACTER_PRIORITY)
    state = GameState(
        gold=3, round_num=1, level=4, plane=1,
        shop=[ShopCard(x=100, faction="能量", name="阿格莱雅", cost=1),
              ShopCard(x=200, faction="减益", name="黄泉", cost=3)],
    )
    actions = plan(state, cfg, cfg.faction_priority, rng=random.Random(0), target_comp=target)
    buys = [a.card.name for a in actions if isinstance(a, BuyCard)]
    assert "黄泉" in buys, "target core 黄泉 应买(prefilter 让 target 通过)"
    assert "阿格莱雅" not in buys, "off-target priority 阿格莱雅 应跳过(D-79:prefilter 不再豁免 priority)"


def test_plan_t97_committed_refuses_offtarget_when_no_target_in_shop() -> None:
    """T#97:已 commit + shop 无 target 卡 → 拒 off-target(commit 后买散牌 = spread 根因)。

    live 复现(plane1 r1-3,target 追击飞霄[追击]):买完唯一 target 卡(追击/赛飞儿)后 simulate 把它移出
    shop → shop 无 target → 旧 prefilter「防饿死」放行 off-target → 买 能量/持续伤害 散牌 → board spread
    → plane2 comp 弱秒死。修:已 commit 也拒 off-target(该 Refresh 找 target / 攒金;drought bail 处理
    真不可达)。**未 commit**(round=1)同 shop 仍放行 off-target(早期 tempo,防饿死)。

    level=10 隔离 level/saving 门(无 _want_level / _saving_for_level);deployed=0 避 _saving_for_interest
    → 唯一阻断 off-target 的是 commitment prefilter(纯验 T#97 逻辑)。
    """
    target = Comp(name="追击飞霄", factions=["追击"], core_chars=["飞霄", "知更鸟", "缇宝", "不死途"],
                  form_tiers={"追击": 3}, strength="B", form_difficulty="medium")
    shop = [ShopCard(x=100, faction="能量", name="阿格莱雅", cost=1),
            ShopCard(x=200, faction="持续伤害", name="艾丝妲", cost=1),
            ShopCard(x=300, faction="群攻", name="黑塔", cost=1)]
    cfg = _cfg()
    # 已 commit:board 有 target 投入(追击×2 → form_progress 0.67>0)+ round=4 轮数兜底 → committed
    # (D-90:轮数兜底现要求 form_progress>0,防零投入误锁;故 state 需给 target 真实投入才算 commit)
    st_comm = GameState(gold=6, round_num=4, level=10, plane=1, shop=shop, board={"追击": 2})
    buys_comm = [a.card.name for a in plan(st_comm, cfg, cfg.faction_priority,
                                           rng=random.Random(0), target_comp=target)
                 if isinstance(a, BuyCard)]
    assert buys_comm == [], (
        f"已 commit + shop 无 target → 不买 off-target(应 Refresh 找 target / 攒金),got {buys_comm}"
    )
    # 未 commit:round=1 → 早期 tempo 允许 off-target(回归守卫:别把早期也禁了 → 饿死)
    st_early = GameState(gold=6, round_num=1, level=10, plane=1, shop=shop)
    buys_early = [a.card.name for a in plan(st_early, cfg, cfg.faction_priority,
                                            rng=random.Random(0), target_comp=target)
                  if isinstance(a, BuyCard)]
    assert buys_early, "未 commit + shop 无 target → 允许 off-target tempo(早期不该饿死)"


def test_plan_d137_buys_target_faction_despite_board_spread() -> None:
    """D-137:target 阵营卡即使 board 已 ≥cap 阵营也该买(target 免 spread 罚)。

    复现 round3(target=DOT队,board 4 阵营,shop 有 target 卡 减益/椒丘):旧逻辑 _concentration_delta
    对新 target 阵营 减益 也 -8 spread 罚 → buy delta 负 → 不买 → comp 永不深 → buy0 输。修:target 阵营免罚。
    """
    dot = Comp(name="DOT队", factions=["持续伤害", "减益"], core_chars=["卡芙卡"],
               form_tiers={"持续伤害": 4, "减益": 3}, strength="B", form_difficulty="easy")
    shop = [ShopCard(x=100, faction="减益", name="椒丘", cost=1),    # target 阵营(新进)
            ShopCard(x=200, faction="群攻", name="黑塔", cost=1)]   # off-target
    cfg = _cfg()
    # board 已 4 阵营(≥cap 3)+ level10(无 saving)+ 减益 target 卡 → 应买减益(不再被 spread 罚卡死)
    # gold=25(非利息档边界):ADR-0102 后 round4=P1 mid interest→interest_first,bot 会保利息档;
    # 用 25(买 1 费卡 25→24 不掉档)隔离 concentration 测试,免被 tempo 档边界副作用干扰。
    st = GameState(gold=25, round_num=4, level=10, plane=1,
                   board={"银河学者": 2, "击破": 1, "群攻": 1, "持续伤害": 1}, shop=shop)
    buys = [a.card.faction for a in plan(st, cfg, cfg.faction_priority,
                                         rng=random.Random(0), target_comp=dot)
            if isinstance(a, BuyCard)]
    assert "减益" in buys, (
        f"target 阵营卡(减益)board≥cap 也应买(D-137 免 spread 罚),got buys={buys}"
    )


def test_rebuild_deployed_from_board_aligns_count_and_rows() -> None:
    """D-107:rebuild_deployed_from_board 从 board 重建 deployed,计数=sum(board),back 先填至 back_max 再 front。"""
    from sr_od.application.currency_war.cw_state import rebuild_deployed_from_board
    dep = rebuild_deployed_from_board({"能量": 2, "护盾": 6}, back_max=6)   # 总 8
    assert len(dep) == 8
    assert sum(1 for d in dep if d.position_pref == "back") == 6    # back_max=6 先填满
    assert sum(1 for d in dep if d.position_pref == "front") == 2   # 溢出 2 去 front
    assert sum(1 for d in dep if d.faction == "能量") == 2          # faction 保留
    assert sum(1 for d in dep if d.faction == "护盾") == 6


def test_plan_t107_saves_interest_when_board_full_low_gold() -> None:
    """D-107(RC1,治 T#97 战术层 desync):board 满 + gold<50 + hp ok → _saving_for_interest 抑制散买(攒息)。

    根因(子agent 查实):read_game_state 不填 deployed → 恒 [] → deployed_count() 恒 0 →
    _saving_for_interest(需 deployed>=max_units)永不触发 → bot 不攒息、散买 off-target(gold→0 spread 根因)。
    修:rebuild_deployed_from_board 从 board 真值重建 deployed → 计数对齐 → 攒息门触发。
    round=2 未 commit(隔离 saving,非 D-106 commitment);level=8 → max_units=8 = board 计数(满)。
    """
    from sr_od.application.currency_war.cw_state import rebuild_deployed_from_board
    target = Comp(name="DOT队", factions=["持续伤害", "减益"], core_chars=["卡芙卡"],
                  form_tiers={"持续伤害": 4, "减益": 4}, strength="B", form_difficulty="easy")
    cfg = _cfg()
    state = GameState(gold=30, hp=100, level=8, round_num=2, plane=1,
                      board={"持续伤害": 4, "减益": 4})
    state.deployed = rebuild_deployed_from_board(state.board, state.back_max)
    assert state.deployed_count() == 8 and state.deployed_count() >= state.max_units(), "rebuild 后计数=board 真"
    state.shop = [ShopCard(x=100, faction="能量", name="阿格莱雅", cost=1)]   # off-target,买得起
    actions = plan(state, cfg, cfg.faction_priority, rng=random.Random(0), target_comp=target)
    buys = [a.card.name for a in actions if isinstance(a, BuyCard)]
    assert "阿格莱雅" not in buys, (
        "board 满 + gold<50 + hp ok → _saving_for_interest 攒息,不散买 off-target(D-107 RC1)"
    )


def test_should_save_for_interest_winning_streak_breaks_it() -> None:
    """C 杠杆 3 winning half(R2-4b,ADR-0117):连胜 ≥ WIN_STREAK_BREAK_INTEREST → 破息(保连胜>吃息)。

    同场景(board 满 + gold<50 + HP 安全 + 板强):streak=0/连败(HP 安全)→ 攒息 True;连胜 ≥2 → False
    (花钱提质量维持连胜,断连胜亏 > 利息亏)。连败 fold 半已由 HP-gating 覆盖(HP 安全仍 fold 攒息)。
    streak 带符号(parse_streak:连胜 +/连败 −),magnitude 对称给金(economy_score),方向驱 plan 行为(本测)。
    """
    from sr_od.application.currency_war.cw_state import rebuild_deployed_from_board
    target = Comp(name="DOT队", factions=["持续伤害", "减益"], core_chars=["卡芙卡"],
                  form_tiers={"持续伤害": 4, "减益": 4}, strength="B", form_difficulty="easy")
    cfg = _cfg()
    base = GameState(gold=30, hp=100, level=8, round_num=2, plane=1, board={"持续伤害": 4, "减益": 4})
    base.deployed = rebuild_deployed_from_board(base.board, base.back_max)
    assert base.deployed_count() >= base.max_units(), "板满前置(隔离)"
    # streak=0(默认 None):全条件满足 → 攒息
    assert _should_save_for_interest(base, cfg, target) is True, "无连胜 + 板满+gold<50+HP安全+板强 → 攒息"
    # 连败 streak=-3(HP 安全):magnitude 对称(连败也 fold 攒息;急救由 HP-gate,此处 HP 安全不急救)
    loss = base.copy()
    loss.streak = -3
    assert _should_save_for_interest(loss, cfg, target) is True, "连败(HP 安全)→ 仍 fold 攒息(非急救)"
    # 连胜 streak=3:保连胜 > 吃息 → 破息
    win = base.copy()
    win.streak = 3
    assert _should_save_for_interest(win, cfg, target) is False, "连胜 ≥2 → 破息提质量保连胜(R2-4b)"
    # 连胜刚好 = 阈值(2)→ 也破息(边界,auto-chess 连胜金 2 连起档)
    win2 = base.copy()
    win2.streak = WIN_STREAK_BREAK_INTEREST
    assert _should_save_for_interest(win2, cfg, target) is False, "连胜=阈值(2)→ 破息(边界)"
    # 连胜 1(<阈值)→ 不破息(1 连无连胜金,不值得破息)
    win1 = base.copy()
    win1.streak = 1
    assert _should_save_for_interest(win1, cfg, target) is True, "连胜 1(<阈值)→ 仍攒息(未到连胜金档)"


# —— level_plan 硬 gate(task#18 经济统一论):level_plan 说 level_up + 够钱 → 强制升级 ——


def test_plan_levels_up_when_affordable_and_planned() -> None:
    """task#18 核心:level_plan 说 level_up + 够钱 → plan 升级(硬 gate,不靠贪心 eval)。

    回归守卫:replay 32 局「升 0 次」bug —— 旧版 LevelUp 候选 delta 永负(花大金升级的利息损失
    压过 level_val)→ 永不选 → bot 卡 lv5-6 → 弱 comp → plane2 死。改硬 gate 强制执行 level_plan。
    """
    from sr_od.application.currency_war.cw_comps import get_comp
    列车 = get_comp("列车同行")   # level_plan[5]="level_up"
    cfg = _cfg()
    state = GameState(gold=40, round_num=4, level=5, plane=1)   # cost(5→6)=36,gold 40>=36
    actions = plan(state, cfg, cfg.faction_priority, target_comp=列车)
    assert any(isinstance(a, LevelUp) for a in actions), (
        "level_plan[5]=level_up + gold>=cost(36) → 硬 gate 应升级"
    )


def test_plan_generic_curve_levels_mid_game() -> None:
    """task#18:comp 未填 level_plan(DOT队)→ 通用曲线兜底(lv5=level_up)+ 够钱 → 升级。

    多数 comp 未填 level_plan;通用曲线(_DEFAULT_LEVEL_GOAL)保证它们也有合理经济行为(中后期推等级),
    不再依赖每 comp 手填曲线。
    """
    from sr_od.application.currency_war.cw_comps import get_comp
    dot = get_comp("DOT队")   # 无 level_plan → 退回通用曲线
    cfg = _cfg()
    state = GameState(gold=40, round_num=4, level=5, plane=1)   # 通用曲线[5]=level_up,cost36,gold40>=36
    actions = plan(state, cfg, cfg.faction_priority, target_comp=dot)
    assert any(isinstance(a, LevelUp) for a in actions), (
        "DOT队 无 level_plan → 通用曲线 lv5=level_up + gold>=cost → 应升级"
    )


def test_plan_no_levelup_when_cannot_afford() -> None:
    """task#18:goal=level_up 但金不够升级金 → 不升级(硬 gate 的 afford 守卫,防负金)。"""
    from sr_od.application.currency_war.cw_comps import get_comp
    列车 = get_comp("列车同行")   # level_plan[5]=level_up
    cfg = _cfg()
    state = GameState(gold=10, round_num=4, level=5, plane=1)   # cost36,gold10<36
    actions = plan(state, cfg, cfg.faction_priority, target_comp=列车)
    assert not any(isinstance(a, LevelUp) for a in actions), (
        "金不够升级金(cost36)→ 硬 gate 不应升级"
    )


# —— A2 战略层接线(plan → select_comp → evaluate(target),2026-08-04)——


def test_plan_target_steers_buy_over_reactive() -> None:
    """A2 接线核心区分性:有 target 时买 target 阵营牌,而非 reactive 偏好的他派。

    强制 target=万敌单C(``character_build_around=['万敌']`` 只放过含万敌的 comp;万敌 1 费 lv1 可刷);
    空板 + 金 1(只够买 1 张)+ 商店[夜之半神 cost1, 列车同行 cost1]。
    - reactive(无 target):synergy 上 列车同行(ceiling 0.5)> 夜之半神 → 会先买列车同行;
    - 有 target:夜之半神买还降万敌单C target_progress 剩余 → 夜之半神反超 → 买它(万敌属夜之半神+燃血)。
    **断线(plan 不传 target)= 退回 reactive 买列车同行 → 本测试失败**(回归守卫)。
    """
    cfg = _cfg(character_build_around=["万敌"])
    state = GameState(
        gold=1, round_num=1, level=1, plane=1,
        shop=[ShopCard(x=1, faction="夜之半神", name="", cost=1),
              ShopCard(x=2, faction="列车同行", name="", cost=1)],
    )
    actions = plan(state, cfg, cfg.faction_priority, rng=random.Random(0))
    buys = [a for a in actions if isinstance(a, BuyCard)]
    assert buys, "金 1 够买 cost1,应至少买入 1 张"
    assert buys[0].card.faction == "夜之半神", (
        "有 target(万敌单C)时应买夜之半神(target 阵营),而非 reactive 偏好的列车同行"
    )


def test_plan_buys_toward_committed_comp() -> None:
    """A2 接线集成:板面已深入某 comp(列车同行 3/4,progress 0.75)→ plan 买该 comp 阵营牌收敛。

    锁定战略↔战术集成:select_comp 选已深入的 comp 作 target,plan 买入推进其成型。
    level=3(level_plan=roll,不触发 spending gate)→ 列车同行牌正常买入。
    """
    cfg = _cfg()
    state = GameState(
        gold=10, round_num=3, level=3, plane=1,
        board={"列车同行": 3},
        shop=[ShopCard(x=1, faction="列车同行", name="", cost=1)],
    )
    actions = plan(state, cfg, cfg.faction_priority)
    assert any(isinstance(a, BuyCard) and a.card.faction == "列车同行" for a in actions), (
        "板面深入列车同行 → 应买列车同行牌向 target 收敛"
    )


def test_plan_uses_passed_target_comp_not_reselect() -> None:
    """target 稳定性(task#16):plan(target_comp=X) 用 X 驱动买牌,**不内部重选**。

    同 state + 不同 target_comp → 买不同 target 阵营牌(证明传入 target 生效,非每轮 select_comp)。
    防 2026-08-04 实跑的 target 振荡(列车同行↔DOT队)→ churn。
    """
    from sr_od.application.currency_war.cw_comps import get_comp
    巡海击破 = get_comp("巡海击破")   # factions=['击破'](ADR-0152:击破流萤更名)
    dot队 = get_comp("DOT队")         # factions=['持续伤害','减益']
    cfg = _cfg()
    state = GameState(
        gold=3, round_num=3, level=5, plane=1,
        shop=[ShopCard(x=1, faction="击破", name="", cost=1),
              ShopCard(x=2, faction="持续伤害", name="", cost=1)],
    )
    a1 = plan(state, cfg, cfg.faction_priority, rng=random.Random(0), target_comp=巡海击破)
    buys1 = [a for a in a1 if isinstance(a, BuyCard)]
    a2 = plan(state, cfg, cfg.faction_priority, rng=random.Random(0), target_comp=dot队)
    buys2 = [a for a in a2 if isinstance(a, BuyCard)]
    assert buys1, "target=巡海击破 应买牌"
    assert buys1[0].card.faction == "击破", "target=巡海击破 → 买击破(target 阵营)"
    assert buys2, "target=DOT队 应买牌"
    assert buys2[0].card.faction == "持续伤害", "target=DOT队 → 买持续伤害(target 阵营)"


def test_plan_no_levelup_at_max() -> None:
    """满级(10)时不再升等级(level≤10 硬门)。"""
    cfg = _cfg()
    state = GameState(gold=200, round_num=6, level=10, plane=3, bench_full_flag=True)
    actions = plan(state, cfg, cfg.faction_priority)
    assert not any(isinstance(a, LevelUp) for a in actions), "满级不应再升等级"


def test_plan_caps_refresh_per_round() -> None:
    """每回合主动刷新(D 牌)次数受 _refresh_cap 约束(review r5 防无限刷 + ADR-0128 comp 停留放宽)。

    基线:target lv6=level_up(列车同行)非停留 roll → ≤ MAX_REFRESH_PER_ROUND;
    comp 停留 roll 级(列车 lv7=roll 3星姬子)→ 放宽到 4(人玩「停留概率级 D 核心」)。
    """
    from sr_od.application.currency_war.cw_comps import COMP_LIBRARY
    cfg = _cfg()
    train = next(c for c in COMP_LIBRARY if c.name == "列车同行")
    # 金 30(追级地板 20 之上、升不起整级)→ 停留 lv6 非 roll;商店无可用牌 → 刷新期望可能正,但受基线上限挡
    state = GameState(gold=30, round_num=4, level=6, plane=2,
                      shop=[ShopCard(x=1, faction="公司", name="", cost=5)])
    actions = plan(state, cfg, cfg.faction_priority, rng=random.Random(0), target_comp=train)
    n_refresh = sum(1 for a in actions if isinstance(a, RefreshShop))
    assert n_refresh <= MAX_REFRESH_PER_ROUND, f"非停留回合刷新应 ≤ {MAX_REFRESH_PER_ROUND},实际 {n_refresh}"
    # comp 停留 roll(lv7)→ cap 放宽 4(ADR-0128)
    state7 = GameState(gold=80, round_num=4, level=7, plane=2,
                       shop=[ShopCard(x=1, faction="公司", name="", cost=5)])
    actions7 = plan(state7, cfg, cfg.faction_priority, rng=random.Random(0), target_comp=train)
    n7 = sum(1 for a in actions7 if isinstance(a, RefreshShop))
    assert n7 <= 4, f"停留 roll 回合刷新应 ≤ 4(放宽),实际 {n7}"


# —— deploy 站位 + 3合1 + 凑整吃息 + char_quality 已上阵(review r1 新覆盖)——


def test_deploy_uses_position_pref() -> None:
    """deploy 按 position_pref 分流:front 偏好→前排,back 偏好→后排。"""
    cfg = _cfg()
    state = GameState(
        gold=10, round_num=3, level=5, plane=1,
        bench=[BenchChar(slot=0, faction="巡海游侠", star=1, position_pref="front"),
               BenchChar(slot=1, faction="巡海游侠", star=1, position_pref="back")],
    )
    actions = plan(state, cfg, cfg.faction_priority)
    rows = {a.to_row for a in actions if isinstance(a, DeployMove)}
    assert "front" in rows, "front 偏好角色应 deploy 到前排"
    assert "back" in rows, "back 偏好角色应 deploy 到后排"


def test_compound_3merge() -> None:
    """买 3 张同名同星 → 自动合并升星(3×1星→1×2星)。"""
    s = GameState(gold=100)
    for _ in range(3):
        s = simulate(s, BuyCard(ShopCard(x=1, name="阿格莱雅", cost=1, star=1)))
    assert len(s.bench) == 1, "3 同名1星应合并为1张"
    assert s.bench[0].star == 2, "合并后应为2星"


def test_sell_for_interest_crosses_boundary() -> None:
    """凑整吃息:gold=39 卖1星(回1)→40 跨档应卖;gold=31→32 不跨档不卖。

    直接测 _maybe_sell_for_interest(绕开贪心,避免 bench 角色被先 deploy 掉)。
    """
    cfg = _cfg()
    a39: list = []
    _maybe_sell_for_interest(
        GameState(gold=39, bench=[BenchChar(slot=0, faction="公司", star=1)]),
        a39, [], cfg)
    assert any(isinstance(a, SellBench) for a in a39), "gold=39 卖1星→40 跨档应卖"
    a31: list = []
    _maybe_sell_for_interest(
        GameState(gold=31, bench=[BenchChar(slot=0, faction="公司", star=1)]),
        a31, [], cfg)
    assert not any(isinstance(a, SellBench) for a in a31), "gold=31→32 不跨档不应卖"


def test_char_quality_counts_deployed() -> None:
    """char_quality 计已上阵优先角色(deploy 不丢分)。"""
    s_bench = GameState(bench=[BenchChar(slot=0, char_id="阿格莱雅", faction="巡海游侠", star=1)])
    s_dep = GameState(deployed=[BenchChar(slot=0, char_id="阿格莱雅", faction="巡海游侠", star=1)])
    v_bench = char_quality_score(s_bench, ["阿格莱雅"])
    v_dep = char_quality_score(s_dep, ["阿格莱雅"])
    assert v_dep > 0, "已上阵优先角色应计分"
    assert v_bench == v_dep, "bench 与 deployed 的优先角色同等计分"


# —— 事件 + boss ——
# (原 test_decide_event_whitelist 已删,ADR-0204:event_whitelist 配置删除,用户语义由
#  strategy/env priority(+30)/forbid(−10000)覆盖,见下方转向轴测试族。)


def test_decide_event_dot_needs_major_faction() -> None:
    """DoT 避坑需 DoT 为主流派(count≥2):count=2 避,count=1 不避。"""
    cfg = _cfg()
    s2 = GameState(board={"持续伤害": 2})  # 主派 → 避 净化身心
    assert decide_event(["净化身心", "普通选项"], cfg, s2).option_idx != 0, (
        "count=2 走DoT应避净化身心"
    )
    s1 = GameState(board={"持续伤害": 1})  # 仅顺带1张 → 不避
    # count=1 不触发 on_dot,净化身心 无惩罚;两选项白名单都0分 → 选第一个(idx0)
    assert decide_event(["净化身心", "普通选项"], cfg, s1).option_idx == 0, (
        "count=1 非DoT主派,不避(选第一个)"
    )


# —— 用户转向轴:投资策略/环境 priority/forbid(config.md §3;2026-08-17 用户定调)——


def test_decide_event_strategy_forbid_avoided() -> None:
    """strategy_forbid:被禁策略有替代时永不选(哪怕评估分更高)。"""
    cfg = _cfg(strategy_forbid=["淘金客"])   # 淘金客 eval=50 > 成本控制 48
    pick = decide_event(["淘金客", "成本控制"], cfg, GameState())
    assert pick.option_idx == 1, "淘金客被禁,应选成本控制"


def test_decide_event_strategy_priority_boost() -> None:
    """strategy_priority:低评估分命中优先轴 → +30 反超(soft 倾向,非硬绑定)。"""
    cfg = _cfg(strategy_priority=["成本控制"])   # 成本控制 48 vs 淘金客 50
    pick = decide_event(["淘金客", "成本控制"], cfg, GameState())
    assert pick.option_idx == 1, "priority +30 应让成本控制(48+30)反超淘金客(50)"


def test_decide_event_env_axes() -> None:
    """env_forbid / env_priority 走 env 轴(注册表命中归 env,不落 strategy 轴)。"""
    # 长线利好 65 vs 蓝海 38:forbid 长线利好 → 选蓝海
    cfg = _cfg(env_forbid=["长线利好"])
    assert decide_event(["长线利好", "蓝海"], cfg, GameState()).option_idx == 1, (
        "长线利好被禁应选蓝海"
    )
    # priority 蓝海 → 38+30=68 > 65 → 反超
    cfg = _cfg(env_priority=["蓝海"])
    assert decide_event(["长线利好", "蓝海"], cfg, GameState()).option_idx == 1, (
        "蓝海 priority +30 应反超长线利好"
    )
    # strategy 轴不误伤 env 名(只配 strategy_forbid 时 env 选项不受影响)
    cfg = _cfg(strategy_forbid=["蓝海"])
    assert decide_event(["长线利好", "蓝海"], cfg, GameState()).option_idx == 0, (
        "strategy_forbid 不该影响 env 选项"
    )


# —— 遭遇节点 decide_encounter(design 08;纯逻辑)——


def test_decide_encounter_refresh_when_all_counter() -> None:
    """全分支词缀都克 comp + 刷新未用 → 刷新换批(避开高危)。"""
    cfg = _cfg()
    comp = _comp(["速度依赖"])  # 忽快忽慢→速度抑制 counter(克)
    opts = [EncounterOption(idx=0, difficulty=1, affixes=["忽快忽慢"]),
            EncounterOption(idx=1, difficulty=2, affixes=["忽快忽慢"])]
    pick = decide_encounter(opts, GameState(), comp, cfg, refresh_used=False)
    assert pick.refresh, "全分支克 comp 应刷新换批"


def test_decide_encounter_no_refresh_when_used() -> None:
    """刷新已用 → 不再刷(按最优分支选)。"""
    cfg = _cfg()
    comp = _comp(["速度依赖"])
    opts = [EncounterOption(idx=0, difficulty=1, affixes=["忽快忽慢"])]
    pick = decide_encounter(opts, GameState(), comp, cfg, refresh_used=True)
    assert not pick.refresh, "刷新已用不再刷"


def test_decide_encounter_unformed_picks_low_difficulty() -> None:
    """未成型(level 低/deployed 空)→ 偏低难度(生存优先);中性词缀按难度选。"""
    cfg = _cfg()
    comp = _comp(["燃血"])
    unformed = GameState(level=1, deployed=[])   # max_units=1, deployed 0 → 未成型
    opts = [EncounterOption(idx=0, difficulty=1),    # 中性(无词缀)
            EncounterOption(idx=1, difficulty=3)]
    pick = decide_encounter(opts, unformed, comp, cfg)
    assert pick.idx == 0, "未成型应选低难度(diff=1)"
    assert not pick.refresh


def test_decide_encounter_formed_buff_picks_high_difficulty() -> None:
    """成型 + 词缀利 comp(debuff=buff)→ 挑高难度拿奖励。"""
    cfg = _cfg()
    comp = _comp(["燃血"])  # 正当防卫→反伤,对燃血是 synergy(debuff=buff,利)
    # 成型:board 满足 form_tiers + deployed ≥ max_units/2
    formed = GameState(level=8, board={"燃血": 4},
                       deployed=[BenchChar(slot=i) for i in range(4)])
    opts = [EncounterOption(idx=0, difficulty=1, affixes=["正当防卫"]),
            EncounterOption(idx=1, difficulty=3, affixes=["正当防卫"])]
    pick = decide_encounter(opts, formed, comp, cfg)
    assert pick.idx == 1, "成型 + 利 comp 应挑高难度(diff=3)拿奖励"
    assert not pick.refresh, "利 comp 不刷新"


# —— 补给节点 decide_supply(design 07/08;纯逻辑)——


def test_decide_supply_diamond_first() -> None:
    """带钻选项 → 选它(碾压装备价值)。"""
    cfg = _cfg()
    opts = [SupplyOption(idx=0, equip="反重力皮靴"),                 # 高价值但无钻
            SupplyOption(idx=1, equip="光能电池", has_diamond=True)]  # 带钻
    pick = decide_supply(opts, GameState(), _comp_key([]), cfg)
    assert pick.idx == 1, "带钻应优先选"
    assert not pick.refresh


def test_decide_supply_refresh_when_no_diamond() -> None:
    """全无钻 + 刷新未用 → 刷新找钻。"""
    cfg = _cfg()
    opts = [SupplyOption(idx=0, equip="反重力皮靴")]
    pick = decide_supply(opts, GameState(), _comp_key([]), cfg, refresh_used=False)
    assert pick.refresh, "无钻应刷新找钻"


def test_decide_supply_key_equip_when_refresh_used() -> None:
    """刷新已用 → 按 target_comp.key_equips 契合选(命脉级,碾压通用价值)。"""
    cfg = _cfg()
    comp = _comp_key(["反重力皮靴"])   # 反重力靴是命脉
    opts = [SupplyOption(idx=0, equip="光能电池"),      # 通用 value 3
            SupplyOption(idx=1, equip="反重力皮靴")]    # key_fit +10 → 5+10=15
    pick = decide_supply(opts, GameState(), comp, cfg, refresh_used=True)
    assert pick.idx == 1, "刷新已用应选 key_equips 契合的"
    assert not pick.refresh


def test_decide_supply_generic_value_when_no_key() -> None:
    """刷新已用 + 无 key 契合 → 通用装备价值高者优先(鞋>电池)。"""
    cfg = _cfg()
    opts = [SupplyOption(idx=0, equip="光能电池"),      # value 3
            SupplyOption(idx=1, equip="反重力皮靴")]    # value 5
    pick = decide_supply(opts, GameState(), _comp_key([]), cfg, refresh_used=True)
    assert pick.idx == 1, "无 key 契合应选通用价值高的(反重力皮靴)"
    assert not pick.refresh


# —— optionality_score + α(t)(design 02/03 P1-1 + F-3;纯逻辑)——


def test_alpha_t_monotonic() -> None:
    """α(t) 随总回合单调:早(elapsed<R_OPEN)→0、晚(>R_CLOSE)→1、中线性。"""
    assert alpha_t(GameState(plane=1, round_num=1)) == 0.0, "elapsed1<R_OPEN → 0"  # elapsed=1
    assert alpha_t(GameState(plane=3, round_num=6)) == 1.0, "elapsed18>R_CLOSE → 1"  # elapsed=18
    assert alpha_t(GameState(plane=2, round_num=1)) == pytest.approx(0.5), "elapsed7 中点 → 0.5"  # elapsed=7


def test_optionality_shared_char_rewards() -> None:
    """bench 角色属 ≥2 comp(风堇∈昼神阿雅+万敌)→ 加分;只属 1 comp(飞霄)→ 0;空 → 0。"""
    multi = GameState(bench=[BenchChar(slot=0, char_id="风堇")])     # 风堇 ∈ 2 comp
    single = GameState(bench=[BenchChar(slot=0, char_id="飞霄")])    # 飞霄 ∈ 1 comp(追击飞霄)
    empty = GameState(bench=[])
    assert optionality_score(multi) > 0.0, "风堇 属 2 comp 应加分"
    assert optionality_score(single) == 0.0, "飞霄 只属 1 comp 不加分"
    assert optionality_score(empty) == 0.0, "空 bench → 0"


def test_evaluate_optionality_alpha_blend() -> None:
    """承诺-期权混合(ADR 0096 / F-3,2026-08-11 接线 ``α·commit + (1−α)·optionality``)。

    风堇(∈2 comp)vs 飞霄(∈1 comp):同 1 bench 角色、同 star=1、都不在 character_priority →
    char_quality / synergy / economy 完全相同,差**仅 optionality**(隔离)。
    - 早(α=0):风堇 − 飞霄 == OPTIONALITY_WEIGHT(optionality 全);成型压力 0(未成型不该罚)。
    - 晚(α=1):差 == 0(optionality=0,让位 commit)。
    """
    from sr_od.application.currency_war.cw_comps import get_comp
    cfg = _cfg()
    飞霄comp = get_comp("追击飞霄")
    # 早期(plane1 r1 → α=0)
    early_vers = GameState(bench=[BenchChar(slot=0, char_id="风堇")], plane=1, round_num=1)
    early_one = GameState(bench=[BenchChar(slot=0, char_id="飞霄")], plane=1, round_num=1)
    assert alpha_t(early_vers) == 0.0
    _diff_early = evaluate(early_vers, cfg, cfg.faction_priority) - evaluate(early_one, cfg, cfg.faction_priority)
    assert _diff_early == pytest.approx(OPTIONALITY_WEIGHT), (
        "早期 α=0 → optionality 全:风堇 − 飞霄 == OPTIONALITY_WEIGHT(隔离 char/synergy/econ 后仅 optionality)"
    )
    # 早期成型压力=0:空 board + 空 bench,有 target 也不扣(未成型正常;BENCH_TARGET/optionality 均为 0)
    s_empty = GameState(board={}, plane=1, round_num=1)
    _base = evaluate(s_empty, cfg, cfg.faction_priority)
    assert evaluate(s_empty, cfg, cfg.faction_priority, target_comp=飞霄comp) == pytest.approx(_base), (
        "早期 α=0 → target_progress 不罚(未成型正常)"
    )
    # 晚期(plane3 r6 → α=1):optionality=0,风堇/飞霄 持平
    late_vers = GameState(bench=[BenchChar(slot=0, char_id="风堇")], plane=3, round_num=6)
    late_one = GameState(bench=[BenchChar(slot=0, char_id="飞霄")], plane=3, round_num=6)
    assert alpha_t(late_vers) == 1.0
    _diff_late = evaluate(late_vers, cfg, cfg.faction_priority) - evaluate(late_one, cfg, cfg.faction_priority)
    assert _diff_late == pytest.approx(0.0), "晚期 α=1 → optionality=0,风堇/飞霄 持平(让位 commit)"


def test_transition_tempo_score_rewards_tempo_factions() -> None:
    """P1 过渡羁绊分:激活档判据(评审🟡7,ADR-0152 续)—— 仙舟(3/5/7/10)2 人不激活=0、3 人激活;
    巡海游侠(1/…)1 人即 tier-1;非过渡 ≥2 → 0;封顶 2。"""
    # 仙舟 2 人:最低档 3 未激活 → 不算凑出(评审🟡7:旧 ≥2 死板判据给幻影分)
    assert transition_tempo_score(GameState(board={'仙舟': 2})) == 0.0
    # 仙舟 3 人:tier-1 激活 → tempo
    assert transition_tempo_score(GameState(board={'仙舟': 3})) == pytest.approx(TRANSITION_TEMPO_BONUS)
    # 2 过渡羁绊(人上人级:仙舟3 + dot2)
    assert transition_tempo_score(GameState(board={'仙舟': 3, '持续伤害': 2})) == pytest.approx(2 * TRANSITION_TEMPO_BONUS)
    # 3 过渡羁绊 → 封顶 2(边际递减)
    assert transition_tempo_score(GameState(board={'仙舟': 3, '狼狩': 3, '列车同行': 2})) == pytest.approx(2 * TRANSITION_TEMPO_BONUS)
    # 非过渡羁绊 ≥2 → 0(追击 是成型羁绊非过渡)
    assert transition_tempo_score(GameState(board={'追击': 3})) == 0.0
    # 巡海游侠最低档 1:1 人即激活(评审🟡7:与真实 tier 对齐,不再要求 ≥2)
    assert transition_tempo_score(GameState(board={'巡海游侠': 1})) == pytest.approx(TRANSITION_TEMPO_BONUS)


def test_evaluate_transition_tempo_early_game() -> None:
    """过渡羁绊早期(α=0)加分保血(review round-4 HIGH-2);α-fade 同 optionality(已测)。"""
    cfg = _cfg()
    early_tempo = GameState(board={'仙舟': 2}, plane=1, round_num=1)   # α=0,有过渡羁绊
    early_empty = GameState(board={}, plane=1, round_num=1)            # α=0,无
    assert evaluate(early_tempo, cfg, cfg.faction_priority) > evaluate(early_empty, cfg, cfg.faction_priority), (
        "早期 α=0 → 过渡羁绊(仙舟2)加分稳血"
    )


def test_phase_weights_hp_threshold_override() -> None:
    """保血阈值可调触发点(D-18 unification;现 HP_DANGER 直传,ADR-0204 后阈值表为代码常量):默认 40 时 hp=50 平衡,
    threshold=60 时 hp=50 触发保血。"""
    assert _phase_weights(1, 50) == (1.0, 1.0, 1.0), "默认 threshold=40,hp=50 健康→平衡"
    assert _phase_weights(1, 50, hp_threshold=60) == (1.2, 0.4, 1.2), (
        "threshold=60,hp=50<60 → 保血"
    )


def test_plan_levels_when_behind_expected_even_if_goal_roll() -> None:
    """D-24: 落后期望等级 + 够钱 → 升级(即使 goal=roll)。修 chicken-egg(卡 roll 等级永不升)。"""
    cfg = _cfg()
    # lv4, plane1 round4 → expected=6;goal[4]=roll(非 level_up);gold 40 >= cost[5]=30
    s = GameState(gold=40, level=4, plane=1, round_num=4)
    actions = plan(s, cfg, cfg.faction_priority)
    assert any(isinstance(a, LevelUp) for a in actions), (
        "落后期望(lv4<6)+ 够钱 → 应升级(即使 goal[4]=roll,D-24 chicken-egg 修)"
    )


# —— difficulty → 保血阈值(D-32;ADR-0204 起阈值表为代码常量 cw_state.DIFFICULTY_HP_TABLE)——


def test_effective_hp_threshold_fallback_no_difficulty() -> None:
    """difficulty 未检测("")→ 回退 HP_SAFE_THRESHOLD(40)。"""
    s = GameState()  # difficulty 默认 ""
    assert effective_hp_threshold(s) == 40, "无 difficulty → 默认 40"


def test_effective_hp_threshold_override_by_difficulty() -> None:
    """selected_difficulty="A8" + 表含 A8 → 用覆盖值(高难更早保血)。"""
    s = GameState(selected_difficulty="A8")
    assert effective_hp_threshold(s) == 55, "A8 表值 55(高难保血地板)"


def test_effective_hp_threshold_missing_key_falls_back() -> None:
    """difficulty="A4" → 表值 40(低难不吃升阶)。"""
    s = GameState(selected_difficulty="A4")
    assert effective_hp_threshold(s) == 40, "A4 → 40"


def test_effective_hp_threshold_plane_model_ratio() -> None:
    """ADR-0176:P2+ 上浮由首达模型解出(替代 0174 手写 ×1.25/×1.5)。

    - P1:精确零漂移(ratio 分母恒等 → base 原值,M57 行为保持);
    - 弱板 P2:上浮 >1 且落于健康带(ratio 夹 [1,2] → ≤80);
    - 弱板 P3 ≥ P2(位面难度单调进乘子);
    - 弱板 > 强板(乘子随板强变化,手写常乘子做不到)。
    """
    # P1 零漂移
    assert effective_hp_threshold(GameState(plane=1, level=4)) == 40
    # 弱板(lv4)P2 上浮
    t_p2 = effective_hp_threshold(GameState(plane=2, round_num=1, level=4))
    assert t_p2 > 40, "弱板 P2 应上浮(模型导出)"
    assert 40 < t_p2 <= 80, "上浮落健康带(≤2.0 夹界)"
    # 位面单调
    t_p3 = effective_hp_threshold(GameState(plane=3, round_num=1, level=4))
    assert t_p3 >= t_p2, "P3 乘子 ≥ P2"
    # 强板(lv10 → tier 满)同样上落健康带:CV 恒定先验下 ratio≈μ 比(≈1.6)近全域常数,
    # 板强分化待实测桶(肥尾)替换先验后由本测试家族的 ratio 断言接管 —— 当前断言健壮带。
    t_p2_strong = effective_hp_threshold(GameState(plane=2, round_num=1, level=10))
    assert 40 < t_p2_strong <= 80, "强板 P2 上浮同样落健康带(细格下无量化病态)"


def test_eval_difficulty_aware_hp_threshold() -> None:
    """evaluate 经 effective_hp_threshold 接 difficulty:A8 表值 55 时 hp=42<55→保血权重;
    无 difficulty 时 hp=42>40→健康权重(证明 difficulty 派生改变 eval 行为,D-32 接线有效)。"""
    s_a8 = GameState(selected_difficulty="A8", hp=42, plane=1)
    assert (_phase_weights(s_a8.plane, s_a8.hp, effective_hp_threshold(s_a8))
            == (1.2, 0.4, 1.2)), "A8 表值 55,hp=42<55 → 保血权重"
    s_none = GameState(hp=42, plane=1)
    assert (_phase_weights(s_none.plane, s_none.hp, effective_hp_threshold(s_none))
            == (1.0, 1.0, 1.0)), "无 difficulty,threshold=40,hp=42>40 → 健康权重"


def test_sample_shop_weights_target_factions() -> None:
    """D-63/F2:_sample_shop 加权 target_comp 阵营(蒙特卡洛 roll 估值该考虑 roll 出 target 卡的价值)。

    target 阵营不在 user priority 时,采样仍加权它(2×)→ r_yes(target) > r_no(无 target)。
    解「roll 估值偏低 → bot 不 roll → shop 无 target 卡时纯攒金 → target 永不深成型」。
    """
    state = GameState(level=6)
    target = Comp(name="T", factions=["击破"], core_chars=[], form_tiers={"击破": 3},
                  strength="B", form_difficulty="medium")

    def hit_rate(seed: int, target_comp: Comp | None) -> float:
        rng = random.Random(seed)
        n_hit = n_tot = 0
        for _ in range(2000):
            for c in _sample_shop(state, [], rng, n=5, target_comp=target_comp):
                n_tot += 1
                n_hit += (c.faction == "击破")
        return n_hit / n_tot

    r_no = hit_rate(42, None)        # 无 target:击破 不加权(均匀)
    r_yes = hit_rate(42, target)     # 有 target:击破 加权 2×
    assert r_yes > r_no * 1.5, f"target 阵营该被加权采样:r_yes={r_yes:.3f} vs r_no={r_no:.3f}"


# —— D-109: _board_alignment + shop_supply 收紧 ——


def test_board_alignment_deep_shallow_none() -> None:
    """D-109:_board_alignment —— board count≥2 → ×1.2(boost);count≥1 → ×1.0(neutral);全无 → ×0.3(重 penalty;review🔴 改:原0.7 压不过 acq 主导致 spread)。"""
    from sr_od.application.currency_war.cw_comps import _board_alignment
    comp = Comp(name="test", factions=["仙舟", "追击"], core_chars=[],
                form_tiers={"仙舟": 5, "追击": 3}, strength="S", form_difficulty="medium")
    # deep-stack(仙舟:2)→ boost
    assert _board_alignment(comp, GameState(board={"仙舟": 2, "能量": 1})) == 1.2
    # shallow(仙舟:1)→ neutral
    assert _board_alignment(comp, GameState(board={"仙舟": 1, "能量": 1})) == 1.0
    # 全无 comp 阵营 → penalty
    assert _board_alignment(comp, GameState(board={"能量": 2, "护盾": 1})) == 0.3


def test_shop_supply_core_vs_noncore() -> None:
    """D-109:shop_supply 收紧 —— 核心(form_tiers)阵营在 shop → 1.0;仅非核心 → 0.5。"""
    from sr_od.application.currency_war.cw_comps import shop_supply
    # comp: factions=[仙舟,追击,盛会之星],form_tiers={仙舟:5,追击:3} → core={仙舟,追击},盛会之星 非核心
    target = Comp(name="test", factions=["仙舟", "追击", "盛会之星"], core_chars=[],
                  form_tiers={"仙舟": 5, "追击": 3}, strength="S", form_difficulty="medium")
    # 核心阵营(仙舟)在 shop → 1.0
    s_core = GameState(shop=[ShopCard(x=1, faction="仙舟", name="", cost=1)])
    assert shop_supply(target, s_core) == 1.0
    # 仅非核心(盛会之星)在 shop → 0.5
    s_noncore = GameState(shop=[ShopCard(x=1, faction="盛会之星", name="", cost=1)])
    assert shop_supply(target, s_noncore) == 0.5


# ===== D-122 concentration(deployed-lock 防 spread)=====


def test_concentration_delta_reinforce_vs_spread() -> None:
    """D-122 L1 _concentration_delta:强化已 collect 阵营 +REINFORCE_BONUS;新阵营≥cap −SPREAD_PENALTY。"""
    # board 有 仙舟 → 买 仙舟 = reinforce
    s = GameState(board={"仙舟": 1})
    assert _concentration_delta(ShopCard(x=0, faction="仙舟"), s) == REINFORCE_BONUS
    # 空 board + 新阵营(第 1,未达 cap)= 中性 0(允许集中起步)
    assert _concentration_delta(ShopCard(x=0, faction="仙舟"), GameState(board={})) == 0.0
    # 已 3 阵营(cap)+ 第 4 新阵营 = spread penalty(防 deployed-lock 永久占槽)
    s_cap = GameState(board={"仙舟": 1, "追击": 1, "击破": 1})
    assert _concentration_delta(ShopCard(x=0, faction="能量"), s_cap) == -SPREAD_PENALTY
    # bench 也算 collected(强化 bench 已有阵营)
    s_bench = GameState(board={}, bench=[BenchChar(slot=1, char_id="x", faction="仙舟")])
    assert _concentration_delta(ShopCard(x=0, faction="仙舟"), s_bench) == REINFORCE_BONUS
    # D-137: target 阵营卡(新进,board≥cap)→ 免 spread 罚(target 阵营深化 comp 非 spread;
    # round3 DOT 队 减益 因 board 4 阵营被旧逻辑 -8 罚 → target 卡不买 → comp 不深 → buy0)
    dot = Comp(name="DOT", factions=["持续伤害", "减益"], core_chars=["卡芙卡"],
               form_tiers={"持续伤害": 4}, strength="B", form_difficulty="easy")
    assert _concentration_delta(ShopCard(x=0, faction="减益"), s_cap, dot) == 0.0   # target 阵营免罚
    assert _concentration_delta(ShopCard(x=0, faction="杂牌", name="卡芙卡"), s_cap, dot) == 0.0  # core_char 免罚
    assert _concentration_delta(ShopCard(x=0, faction="能量"), s_cap, dot) == -SPREAD_PENALTY  # off-target 仍罚


def test_should_deploy_target_or_concentrated() -> None:
    """D-122 L2 _should_deploy:target 阵营 OR 集中阵营(board+bench count≥2)才 deploy;off-target 单张留 bench。"""
    dot = Comp(name="DOT", factions=["持续伤害", "减益"], core_chars=["卡芙卡"],
               form_tiers={"持续伤害": 4}, strength="B", form_difficulty="easy")
    # target 阵营角色 → deploy(深化 target)
    assert _should_deploy(BenchChar(slot=1, char_id="x", faction="持续伤害"),
                          GameState(board={"持续伤害": 1}), dot) is True
    # off-target 单张(count 1)+ 有 target → 留 bench(防 spread-lock)
    assert _should_deploy(BenchChar(slot=1, char_id="y", faction="仙舟"),
                          GameState(board={"持续伤害": 1}), dot) is False
    # off-target 但 board count≥2(集中)+ 无 target → deploy(集中深化,emergent)
    assert _should_deploy(BenchChar(slot=1, char_id="z", faction="仙舟"),
                          GameState(board={"仙舟": 2}), None) is True
    # off-target count 1 + 无 target → 留 bench(r1 散单不 deploy)
    assert _should_deploy(BenchChar(slot=1, char_id="z", faction="仙舟"),
                          GameState(board={"仙舟": 1}), None) is False


def test_distinct_factions_and_counts_include_board() -> None:
    """D-122 fix:board(deployed ground truth)+ bench 都算 collected(曾漏 board 致 _should_deploy 误判)。"""
    s = GameState(board={"仙舟": 2}, bench=[BenchChar(slot=1, char_id="x", faction="击破")])
    assert _distinct_factions(s) == {"仙舟", "击破"}
    assert _bench_faction_counts(s) == {"仙舟": 2, "击破": 1}


def test_economy_mode_for_maps_spend_mode() -> None:
    """ADR-0102:_economy_mode_for 把 node spend_mode → economy_score 档位(14 §2.2;
    ADR-0204 起 spend_mode 单一源,原 config.economy_mode 辅档已删)。"""
    # P1 早期 saving → interest_first(攒息 snowball)
    assert _economy_mode_for(GameState(plane=1, round_num=1)) == "interest_first"
    # P1 中期 interest → interest_first
    assert _economy_mode_for(GameState(plane=1, round_num=5)) == "interest_first"
    # P2 level → rush_level(弱化守息 + 强化等级,升人口);ADR-0148:穷金(gold<30)降档
    # interest_first(息引擎重建,M20 实证 P1 末烧空进场 13-18 金 rush 是破产螺旋)
    assert _economy_mode_for(GameState(plane=2, round_num=3, gold=50)) == "rush_level"
    assert _economy_mode_for(GameState(plane=2, round_num=3, gold=18)) == "interest_first"
    assert _economy_mode_for(GameState(plane=2, round_num=3, gold=0)) == "interest_first"   # 原默认态
    # P1 后期 hold → adaptive(economy-low 非此处处理)
    assert _economy_mode_for(GameState(plane=1, round_num=8)) == "adaptive"
    # P3 allin → adaptive(economy-low 由 _phase_weights plane3 we=0.3)
    assert _economy_mode_for(GameState(plane=3, round_num=2)) == "adaptive"


# (原 test_economy_mode_for_adaptive_falls_back_to_config 已删,ADR-0204:
#  config.economy_mode 死配置删除,adaptive 节点恒 neutral。)


# ===== ADR-0124 买牌 tempo 例外 =====

def _mk_card(faction: str, cost: int, name: str = '未知卡') -> ShopCard:
    return ShopCard(x=500, faction=faction, name=name, cost=cost)


def test_prefilter_tempo_exception_unformed() -> None:
    """ADR-0124:未成型 commit 期,板直接增强散牌(≥2 同阵营)不被 prefilter 拒。"""
    from sr_od.application.currency_war.cw_comps import form_progress, get_comp
    from sr_od.application.currency_war.cw_state import BuyCard

    comp = get_comp('列车同行')
    st = GameState(plane=1, round_num=4, level=6, gold=10, board={'仙舟': 2, '列车同行': 1})
    assert form_progress(comp, st) < 0.4   # 前提:未成型
    st.shop = [_mk_card('仙舟', 2)]
    acts = plan(st, _cfg(), [], rng=random.Random(7), target_comp=comp)
    assert any(isinstance(a, BuyCard) for a in acts), '仙舟已 2,板增强散牌应可买(tempo 例外)'


def test_prefilter_strict_when_formed() -> None:
    """ADR-0124:成型后(fp≥COMMIT_FRAC)仍严格拒 off-target 散牌(T#97 不变)。"""
    from sr_od.application.currency_war.cw_comps import form_progress, get_comp
    from sr_od.application.currency_war.cw_state import BuyCard

    comp = get_comp('列车同行')
    st = GameState(plane=1, round_num=8, level=8, gold=10, board={'列车同行': 4})
    assert form_progress(comp, st) >= 0.4
    st.shop = [_mk_card('仙舟', 3)]
    acts = plan(st, _cfg(), [], rng=random.Random(7), target_comp=comp)
    assert not any(isinstance(a, BuyCard) for a in acts), '成型后 off-target 严格拒'



# ===== ADR-0125/0127 review 补测(H1 窗口语义 / room-bench / 同名 deploy 去重)=====

def _bc_at(slot, name, star=1, faction='?') -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def test_h1_merge_window_reachable_from_shop() -> None:
    """review H1:deployed 1 + bench 1 + shop 同名 → 可买(第 3 份 = 游戏语义当场升星)。"""
    from sr_od.application.currency_war.cw_comps import get_comp
    from sr_od.application.currency_war.cw_state import BuyCard
    comp = get_comp('列车同行')
    st = GameState(gold=20, level=6, plane=1, round_num=5,
                   deployed=[_bc_at(1, '三月七', faction='列车同行')],
                   bench=[_bc_at(1, '三月七', faction='列车同行')],
                   board={'列车同行': 1})
    st.shop = [_mk_card('列车同行', 1, name='三月七')]
    acts = plan(st, _cfg(), [], rng=random.Random(7), target_comp=comp)
    assert any(isinstance(a, BuyCard) for a in acts), 'deployed1+bench1 买第3份应可达(全场合并语义)'


def test_h1_copies_cap_at_3() -> None:
    """review H1:总副本 ≥3(1★)不再买(纯浪费)。"""
    from sr_od.application.currency_war.cw_comps import get_comp
    from sr_od.application.currency_war.cw_state import BuyCard
    comp = get_comp('列车同行')
    st = GameState(gold=20, level=6, plane=1, round_num=5,
                   deployed=[_bc_at(1, '三月七', faction='列车同行')],
                   bench=[_bc_at(1, '三月七', faction='列车同行'),
                           _bc_at(2, '三月七', faction='列车同行')],
                   board={'列车同行': 1})
    st.shop = [_mk_card('列车同行', 1, name='三月七')]
    acts = plan(st, _cfg(), [], rng=random.Random(7), target_comp=comp)
    assert not any(isinstance(a, BuyCard) for a in acts), '1★ 副本已 3 → 不再买'


def test_m3_no_same_name_double_deploy_in_plan() -> None:
    """review M3:场上同名已 deployed → plan 不再 emit 该角色的 DeployMove(游戏 5.1.7 禁双)。"""
    from sr_od.application.currency_war.cw_comps import get_comp
    from sr_od.application.currency_war.cw_state import DeployMove
    comp = get_comp('列车同行')
    st = GameState(gold=10, level=6, plane=1, round_num=5,
                   deployed=[_bc_at(1, '三月七', faction='列车同行')],
                   bench=[_bc_at(1, '三月七', star=2, faction='列车同行')],   # 2★ 同名(merge 产物)
                   board={'列车同行': 1})
    st.shop = []
    acts = plan(st, _cfg(), [], rng=random.Random(7), target_comp=comp)
    assert not any(isinstance(a, DeployMove) for a in acts), '同名 2★ 不得与场上 1★ 双上阵'



# ===== ADR-0129 购买经验决策(单击价模型替整级大金;升级滞后 live 实锤修复) =====
def test_xp_helpers_clicks_and_cost() -> None:
    """clicks_to_next_level 向上取整;xp_click_cost 用 OCR 实读优先。"""
    assert clicks_to_next_level(GameState(level=5, xp_progress=(0, 20), hp=100)) == 5
    assert clicks_to_next_level(GameState(level=5, xp_progress=(18, 20), hp=100)) == 1
    assert clicks_to_next_level(GameState(level=6, xp_progress=None, hp=100)) == 10   # 40 XP / 4
    assert clicks_to_next_level(GameState(level=10, xp_progress=(0, 84), hp=100)) == 0
    assert xp_click_cost(GameState(level=5, hp=100)) == 4                      # 兜底
    assert xp_click_cost(GameState(level=5, level_up_cost=8, hp=100)) == 8     # OCR 实读


def test_level_up_gate_floor_semantics() -> None:
    """追级期地板 20(旧门要求整级 36-60 大金 → 过度保守);非追级/满级不点。"""
    # 追级期(P1r1 target 4,cur 3):扣单击价后 ≥20 才点
    assert level_up_gate(GameState(level=3, gold=24, hp=100, plane=1, round_num=1))
    assert not level_up_gate(GameState(level=3, gold=23, hp=100, plane=1, round_num=1))
    # 非追级期(lv8 已到 P2 地板 8 且通用 goal=roll):不追级 → gate False(攒息)
    assert not level_up_gate(GameState(level=8, gold=80, hp=100, plane=2, round_num=1))
    # 满级
    assert not level_up_gate(GameState(level=10, gold=99, hp=100))


def test_plan_emits_xp_clicks_to_complete_level() -> None:
    """plan 买经验按「点到下一级」发多次单击(每击 4 金),非旧整级大金一次。"""
    s = GameState(level=5, gold=60, xp_progress=(0, 20), hp=100, plane=1, round_num=7)
    actions = plan(s, _cfg(), [], reactive=True)
    lv = [a for a in actions if isinstance(a, LevelUp)]
    assert len(lv) == 5, "0/20 → 5 击升 6 级"
    assert sum(a.cost for a in lv) == 20


def test_plan_bench_full_levels_with_clicks() -> None:
    """bench-full 破墙:点够升 1 级的单击数(旧按整级大金判可负担性 → 高估 → 不必要卖牌)。"""
    s = GameState(level=4, gold=30, xp_progress=(2, 6), hp=100, plane=1, round_num=3)
    s.bench = [BenchChar(slot=i) for i in range(9)]   # 满
    actions = plan(s, _cfg(), [], rng=random.Random(7), reactive=True)
    lv = [a for a in actions if isinstance(a, LevelUp)]
    # bench-full 段 1 击(2/6 → 升 5);主 gate 若仍追级且预算够可再点(goal[5]=level_up)→ 断 ≥1
    assert len(lv) >= 1, "2/6 → 至少 1 击升 5 级"
    # 破墙优先级:LevelUp 全部先于任何 SellBench(点得起经验就不靠卖牌破墙;
    # 尾部凑息卖非关键牌是合法经济行为,不在此禁)
    first_sell = next((i for i, a in enumerate(actions) if isinstance(a, SellBench)), len(actions))
    first_lv = next((i for i, a in enumerate(actions) if isinstance(a, LevelUp)), len(actions))
    assert first_lv < first_sell, f"LevelUp 应先于 SellBench(得 {actions})"



# ===== ADR-0131 投资策略经济效果进模型(免费刷新/利息上限/买经验折扣/每节点金) =====
def test_refresh_cost_free_allowance() -> None:
    """_refresh_cost:加油站(每节点 1 次免费)→ 第 1 次刷新 0 金、第 2 次恢复 2 金。"""
    s = GameState(gold=10, hp=100, active_strategies=['加油站'])
    assert _refresh_cost(s, 0) == 0, "免费额度内第 1 次刷新 = 0 金"
    assert _refresh_cost(s, 1) == 2, "额度用尽 → 恢复 2 金"
    s2 = GameState(gold=10, hp=100)   # 无策略
    assert _refresh_cost(s2, 0) == 2


def test_economy_interest_cap_override() -> None:
    """economy_score 利息上限覆写:利息上调(cap 10)gold 100 → 满 10 档;买断制 → 0 档不吃息。"""
    plain = GameState(gold=100, round_num=5, level=6, plane=2)
    raised = GameState(gold=100, round_num=5, level=6, plane=2,
                       active_strategies=['利息上调'])
    bought_out = GameState(gold=100, round_num=5, level=6, plane=2,
                           active_strategies=['买断制'])
    assert economy_score(raised, "adaptive") > economy_score(plain, "adaptive"), "cap 10 > cap 5(同金)"
    # 买断制不吃息但有每节点 4XP + 立刻 15 金(选时) —— 利息项归零(比同金 plain 低息差部分)
    assert economy_score(bought_out, "adaptive") < economy_score(raised, "adaptive")


def test_economy_gold_per_node_income() -> None:
    """定期福利(每节点 +2 金)→ economy_score 高于无策略同局面(白拿收入计入)。"""
    base = GameState(gold=50, round_num=5, level=6, plane=2)
    with_wf = GameState(gold=50, round_num=5, level=6, plane=2,
                        active_strategies=['定期福利'])
    assert economy_score(with_wf, "adaptive") > economy_score(base, "adaptive")


def test_xp_click_cost_strategy_discount() -> None:
    """商业间谍(买经验 -1 金)→ xp_click_cost 折扣;无策略不受影响。"""
    s = GameState(level=5, hp=100, active_strategies=['商业间谍'])
    assert xp_click_cost(s) == 3, "4 - 1 = 3"
    s2 = GameState(level=5, hp=100)
    assert xp_click_cost(s2) == 4


def test_aggregate_economy_caps_take_max() -> None:
    """aggregate:利息上限取 max(开源节流 9 + 利息上调 10 → 10);免费额度求和。"""
    from sr_od.application.currency_war.cw_investments import aggregate_economy
    e = aggregate_economy(['开源节流', '利息上调'])
    assert e.interest_cap_override == 10
    assert e.instant_gold == 35
    e2 = aggregate_economy(['加油站', '加油站'])
    assert e2.free_refresh_per_node == 2, "同名策略双持(理论)额度求和"


def test_economy_reclassified_fields_adr0142() -> None:
    """ADR-0142:9 条曾错装一次性 instant_gold 的重复性效果按原文归位。"""
    from sr_od.application.currency_war.cw_investments import (
        aggregate_economy,
        get_strategy,
    )
    # 特战资金系 → gold_per_boss_node(非一次性)
    s = get_strategy('特战资金+')
    assert s is not None and s.economy is not None
    assert s.economy.gold_per_boss_node == 11 and s.economy.instant_gold == 0
    # 长期主义系 → 分期节点金(现在+3次,非一次性9金)
    s2 = get_strategy('长期主义')
    assert s2 is not None and s2.economy is not None
    assert s2.economy.gold_next_nodes_amount == 7 and s2.economy.gold_next_nodes_count == 3
    assert s2.economy.instant_gold == 0
    # 节节高升 → 每次升级金
    s3 = get_strategy('节节高升')
    assert s3 is not None and s3.economy is not None and s3.economy.gold_per_level_up == 1
    # 返利 → 纯 gold_per_three_5cost(返利+ 对照:6 即时 + 3/三张)
    s4 = get_strategy('返利')
    assert s4 is not None and s4.economy is not None
    assert s4.economy.gold_per_three_5cost == 3 and s4.economy.instant_gold == 0
    # 保险 → 按损血,不进一次性
    s5 = get_strategy('保险')
    assert s5 is not None and s5.economy is not None and s5.economy.gold_per_20hp_lost == 5
    # 按劳分配/剩余价值 → 每场结算金 ≈ per_node 保守
    for _n in ('按劳分配', '剩余价值'):
        _s = get_strategy(_n)
        assert _s is not None and _s.economy is not None
        assert _s.economy.gold_per_node == 1 and _s.economy.instant_gold == 0
    # 聚合:分期金 amount 求和 / count 取 max
    agg = aggregate_economy(['长期主义+', '长期主义'])
    assert agg.gold_next_nodes_amount == 16 and agg.gold_next_nodes_count == 3



# ===== ADR-0133 全量图鉴 ingest + decide_event 注册表先验 =====
def test_strategy_registry_full_ingest() -> None:
    """注册表全量 315(curated 19 + doc ingest 296);长尾经济抽取抽查。"""
    from sr_od.application.currency_war.cw_investments import (
        INVESTMENT_STRATEGIES,
        get_strategy,
    )
    assert len(INVESTMENT_STRATEGIES) == 335   # 334(plaza API base,ADR-0150)+1(补遗 追击星徽套组(二))
    s = get_strategy("乱成一锅粥+")
    assert s is not None and s.economy is not None
    assert s.economy.instant_gold == 14 and s.economy.free_refresh_burst == 7
    # 搜打撤 = 每当进入新节点获得1次 → per_node 非 burst(条件修正)
    s2 = get_strategy("搜打撤")
    assert s2 is not None and s2.economy is not None and s2.economy.free_refresh_per_node == 1
    # 条件性免费刷不按无条件 per_node 计(存款回报)
    s3 = get_strategy("存款回报")
    assert s3 is not None and s3.economy is None
    # 战力/条件长尾也有名录(选卡先验可查)
    assert get_strategy("盗用身份") is not None and get_strategy("盗用身份").rarity == "棱彩"


def test_decide_event_registry_prior() -> None:
    """先验:白名单 T0(90)仍胜棱彩经济先验(70);先验胜未注册(0)。"""
    cfg = _cfg()
    st = GameState(board={}, hp=100)
    assert decide_event(["定期福利", "乱成一锅粥+"], cfg, st).option_idx == 0, "白名单 T0 > 先验"
    assert decide_event(["无名甲", "乱成一锅粥+"], cfg, st).option_idx == 1, "棱彩经济先验 > 未注册 0"
    # 品质梯度:棱彩无经济(50) vs 未注册(0)
    assert decide_event(["银色无名", "及时雨"], cfg, st).option_idx == 1



# ===== ADR-0134 comp 匹配分(星徽套组对齐 target 压倒品质/白名单) =====
def test_strategy_bindings_extraction() -> None:
    """绑定派生:追击星徽套组 → (追击, 飞霄);无绑定策略 → 空集(安全回落)。"""
    from sr_od.application.currency_war.cw_investments import (
        get_strategy,
        strategy_bindings,
    )
    fs, cs = strategy_bindings(get_strategy("追击星徽套组"))
    assert "追击" in fs and "飞霄" in cs
    fs2, cs2 = strategy_bindings(get_strategy("数值碾压"))
    assert not fs2 and not cs2, "纯战力无绑定 → 空(回落品质先验)"


def test_decide_event_comp_match_wins() -> None:
    """星徽套组对齐 target(飞霄)→ 压倒白名单 T0 与棱彩品质先验;不对齐 = 裸品质。"""
    from sr_od.application.currency_war.cw_comps import COMP_LIBRARY
    feixiao = next(c for c in COMP_LIBRARY if "飞霄" in c.core_chars)
    cfg = _cfg()
    st = GameState(board={}, hp=100)
    # 对齐套组(追击+飞霄,65+) vs 白名单 T0 定期福利(90)—— comp 匹配 1 命中 = 65 < 90?
    # 单命中 45+20=65 不压 T0;双命中(阵营+角色都在 target)= 110 压 T0(成型加速语义)。
    pick = decide_event(["定期福利", "追击星徽套组"], cfg, st, target_comp=feixiao)
    assert pick.option_idx == 1, "阵营+角色双命中(110) > 白名单 T0(90)"
    # 不对齐:燃血套组 vs 追击 target → 无命中 = 裸棱彩品质 50 < T0 90
    pick2 = decide_event(["定期福利", "燃血星徽套组"], cfg, st, target_comp=feixiao)
    assert pick2.option_idx == 0, "不对齐套组 = 裸品质(50) < 白名单 T0(90)"
    # 无 target(None)→ 行为同旧(品质先验)
    pick3 = decide_event(["无名甲", "乱成一锅粥+"], cfg, st)
    assert pick3.option_idx == 1



# ===== ADR-0139 comp 特定站位覆盖命途默认(char_positions) =====
def test_pick_deploy_row_comp_override() -> None:
    """char_positions 覆盖:绯英 comp 爻光(命途默认 front)→ back;万敌 comp 万敌 → front;无 comp 条目按默认。"""
    from sr_od.application.currency_war.cw_comps import COMP_LIBRARY
    fy = next(c for c in COMP_LIBRARY if c.name == "绯英欢愉")
    wd = next(c for c in COMP_LIBRARY if c.name == "万敌单C")
    # 爻光:Character 命途默认 front(欢愉),但绯英 comp 要求 back(攻略实证)
    from sr_od.application.currency_war.cw_state import BenchChar
    yaoguang = BenchChar(slot=1, char_id="爻光", faction="欢愉", position_pref="front")
    st = GameState(hp=100, board={}, level=6)
    st.deployed = [BenchChar(slot=i, char_id=f"c{i}") for i in range(3)]
    row_no, _ = _pick_deploy_row(st, yaoguang)
    assert row_no == "front", "无 comp 覆盖按命途默认 front"
    row_fy, ok = _pick_deploy_row(st, yaoguang, fy)
    assert ok and row_fy == "back", "绯英 comp:爻光必后台(ADR-0139)"
    # 万敌:front
    wd_char = BenchChar(slot=2, char_id="万敌", faction="夜之半神", position_pref="front")
    row_wd, ok2 = _pick_deploy_row(st, wd_char, wd)
    assert ok2 and row_wd == "front"


def test_comp_char_positions_data() -> None:
    """三 comp 站位数据在库:绯英(爻光 back)/追击(知更鸟 front)/万敌(万敌 front)。"""
    from sr_od.application.currency_war.cw_comps import COMP_LIBRARY
    by = {c.name: c.char_positions for c in COMP_LIBRARY}
    assert by["绯英欢愉"].get("爻光") == "back"
    assert by["追击飞霄"].get("知更鸟") == "front"
    assert by["万敌单C"].get("万敌") == "front"



# ===== ADR-0140 中期护航三套(escort_for + tempo 护航感知) =====
def test_escort_for_serves_matching() -> None:
    """escort_for 按 target 机制属性匹配:希儿量子(量子拉条)→龙丹护航;巡海击破→灵砂护航;万敌(燃血成长型)→None。"""
    from sr_od.application.currency_war.cw_comps import COMP_LIBRARY, escort_for
    xe = next(c for c in COMP_LIBRARY if c.name == "希儿量子")
    lj = next(c for c in COMP_LIBRARY if c.name == "巡海击破")   # ADR-0152:击破流萤更名
    wd = next(c for c in COMP_LIBRARY if c.name == "万敌单C")
    assert escort_for(xe).name == "龙丹护航"
    assert escort_for(lj).name == "灵砂护航"
    assert escort_for(wd) is None, "成长型(燃血)不护航"


def test_transition_tempo_escort_bonus() -> None:
    """护航羁绊凑出(≥2)→ tempo 分加权(P1 后期窗口内);过窗口/无 target 无加。"""
    from sr_od.application.currency_war.cw_comps import COMP_LIBRARY
    xe = next(c for c in COMP_LIBRARY if c.name == "希儿量子")
    base = GameState(hp=100, board={"战技点": 2}, plane=1, round_num=7)   # 无过渡羁绊计数
    with_t = transition_tempo_score(base, xe)
    without_t = transition_tempo_score(base, None)
    assert with_t > TRANSITION_TEMPO_BONUS * 1.4, "护航羁绊(战技点 2)命中 → 1.5x 加权"
    assert without_t == 0.0, "无 target 无护航分"
    late = GameState(hp=100, board={"战技点": 2}, plane=2, round_num=8)   # 过 2-7 分水岭
    assert transition_tempo_score(late, xe) == 0.0, "过分水岭退役,无加"



# ===== ADR-0141 品质→敌难度进选卡(金+3/彩+6 的风险项) =====
def test_roll_affordable_gate_adr0147() -> None:
    """ADR-0147 roll 可负担性门:M20 死亡态(lv7 穷金)拦截;P2 健康金(35+)放行。

    M20 死亡窗实证:roll 分支满血也 cap=4 × 5 轮 plan,散板 MC 恒正烧光金(18→0)。
    门:E[刷到下一张核心]×2金(lv7 3费 ≈13.7金)vs 预算金(gold−xp_floor 20)。
    """
    from types import SimpleNamespace

    from sr_od.application.currency_war.cw_comps import COMP_LIBRARY
    from sr_od.application.currency_war.cw_economy import roll_affordable
    tgt = next(c for c in COMP_LIBRARY if c.name == '列车同行')
    cfg = SimpleNamespace()
    assert not roll_affordable(GameState(board={}, gold=18, level=7, plane=2, round_num=2), cfg, tgt)
    assert not roll_affordable(GameState(board={}, gold=5, level=7, plane=2, round_num=2), cfg, tgt)
    assert roll_affordable(GameState(board={}, gold=35, level=7, plane=2, round_num=2), cfg, tgt)
    assert roll_affordable(GameState(board={}, gold=50, level=7, plane=2, round_num=2), cfg, tgt)
    assert not roll_affordable(GameState(board={}, gold=50, level=6, plane=1, round_num=5), cfg, tgt)


def test_decide_event_refresh_suggestion_adr0146() -> None:
    """ADR-0146:三张最优 < 50 → PickEvent.refresh=True(纯建议,handler 决定真刷否)。"""
    cfg = _cfg()
    st = GameState(board={})
    pick = decide_event(["赌神·银", "恢复生机", "气氛组"], cfg, st)   # 20/12/20
    assert pick.refresh is True and 'suggest-refresh' in pick.reason
    pick2 = decide_event(["彩虹时代", "恢复生机", "气氛组"], cfg, st)   # env 72
    assert pick2.refresh is False
    pick3 = decide_event(["远见", "恢复生机", "气氛组"], cfg, st)      # 策略 eval 70(原白名单 90 案例已删,ADR-0204)
    assert pick3.refresh is False


def test_env_pick_value_adr0144() -> None:
    """ADR-0144 环境侧评估分:env 原恒 0 分(fallback 恒选第一张)→ 基准分 + 阵营条件分 + HP 钩子。"""
    from sr_od.application.currency_war.cw_investments import get_env
    cfg = _cfg()
    st = GameState(board={})
    # 基准分:彩虹时代 72 > 增发货币 48(旧:全 0 分 → 恒选第一张)
    pick = decide_event(["增发货币", "彩虹时代"], cfg, st)
    assert pick.option_idx == 1
    assert 'env-eval' in pick.reason
    # 阵营条件分:无 comp 时 追击概念股 52 < 彩虹时代 72;target 含追击 → floor 78 反超
    pick2 = decide_event(["追击概念股", "彩虹时代"], cfg, st)
    assert pick2.option_idx == 1, "无 comp:裸分 52 < 72"
    tgt = Comp(name="t2", factions=["追击"], core_chars=[], form_tiers={"追击": 4},
               strength="A", form_difficulty="medium")
    pick3 = decide_event(["追击概念股", "彩虹时代"], cfg, st, target_comp=tgt)
    assert pick3.option_idx == 0 and 'env-faction' in pick3.reason, "comp 匹配:78 > 72"
    # HP 钩子:白银时代 35 vs 增发货币 48 —— 正常增发胜;hp<40 白银 35+15=50 反超(降难度求稳)
    pick_a = decide_event(["白银时代", "增发货币"], cfg, st)
    assert pick_a.option_idx == 1
    st_low = GameState(board={}, hp=20)
    pick_b = decide_event(["白银时代", "增发货币"], cfg, st_low)
    assert pick_b.option_idx == 0, "HP危:50 > 48 —— 环境钩子改变行为"
    # 注册表字段实值(评估表派生):彩虹时代 72 / 追击概念股 52
    _e = get_env("彩虹时代")
    assert _e is not None and _e.pick_value == 72
    _e2 = get_env("追击概念股")
    assert _e2 is not None and _e2.pick_value == 52
    # 策略/env 注册表不相交:策略名不落 env 分支
    pick_c = decide_event(["免费午餐", "彩虹时代"], cfg, st)   # 50 vs 72
    assert pick_c.option_idx == 1
    # ADR-0144b 跨表污染守卫(评审+自查双实证:83 env 名 29 个 LCS 误中策略名):
    # ①env 名不进策略 LCS 兜底(增发货币曾误中超发货币 55 计分);②env 无品质不吃难度惩罚
    # (列车同行概念股曾误中列车同行星徽棱彩 -12,floor 78 被削到 66 —— 评审量化)。
    tgt2 = Comp(name="tf", factions=["列车同行"], core_chars=[], form_tiers={"列车同行": 4},
                strength="A", form_difficulty="medium")
    pick_d = decide_event(["列车同行概念股", "增发货币"], cfg, st, target_comp=tgt2)
    assert pick_d.option_idx == 0 and 'env-faction' in pick_d.reason, "floor 78 无品质惩罚叠加"
    pick_e = decide_event(["增发货币", "头彩"], cfg, st)   # 48 vs 55:头彩 env 分高,表内胜出(无策略串台)
    assert pick_e.option_idx == 1 and 'env-eval' in pick_e.reason


def test_decide_event_rarity_difficulty_penalty() -> None:
    """ADR-0143 评估分基线上:惩罚只调相对序;HP 危险加倍改变行为。"""
    cfg = _cfg()
    st = GameState(board={}, hp=100)
    # 三张经济类(避开白名单,评估分:乱成一锅粥+ 45 彩 / 黄金垃圾 48 金 / 免费午餐 50 银)
    pick = decide_event(["免费午餐", "黄金垃圾", "乱成一锅粥+"], cfg, st)
    # 分:午餐 50-0 / 垃圾 48-6=42 / 锅粥+ 45-12=33 → 银胜(评估分已含品质+经济,0143 行为改变:
    # 旧裸先验下彩 58 胜;现在「免费午餐」被评为好卡,惩罚叠加后仍压过 —— 分数为纲非品质为纲)
    assert pick.option_idx == 0
    # 高评估彩压过惩罚:鲜血阶梯 75(彩) vs 免费午餐 50(银):75-12=63 > 50 → 彩胜
    # (惩罚只调相对序非禁选,0143 语义不变)
    pick_b = decide_event(["鲜血阶梯", "免费午餐"], cfg, st)
    assert pick_b.option_idx == 0, "高评估彩(63)仍胜银(50) —— 惩罚只调相对序"
    # HP 危险加倍 + 评估分接近:乱成一锅粥+ 45(彩) vs 尾款交付 30(银):
    # 正常 45-12=33 > 30 彩胜;危险 45-24=21 < 30 → **银胜**(危险期惩罚改变行为,设计意图:
    # 低血时不再为品质赌难度;剩余价值是金不适用此例,尾款交付=银 eval 30)
    pick_c = decide_event(["尾款交付", "乱成一锅粥+"], cfg, st)
    assert pick_c.option_idx == 1, "正常期:彩(33)胜银(30)"
    st_low = GameState(board={}, hp=20)
    pick3 = decide_event(["尾款交付", "乱成一锅粥+"], cfg, st_low)
    assert pick3.option_idx == 0, "HP危:银(30)胜彩(21) —— 危险期惩罚改变行为"
    # 未注册(0) vs 金经济(48-12=36) → 金胜
    pick2 = decide_event(["银色无名甲", "黄金垃圾"], cfg, st_low)
    assert pick2.option_idx == 1


def test_option_rarity_lcs_fallback() -> None:
    """_option_rarity:精确名直查;OCR 形变名(•→·)走 LCS 兜底;未知返空。"""
    assert _option_rarity("及时雨") == "棱彩"
    assert _option_rarity("全都要•银") == "银"   # LCS 兜底(注册表是 ·)
    assert _option_rarity("完全不存在的名字xyz") == ""

