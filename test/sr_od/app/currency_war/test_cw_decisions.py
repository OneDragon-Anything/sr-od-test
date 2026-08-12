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
from sr_od.application.currency_war.cw_decisions import (
    MAX_REFRESH_PER_ROUND,
    REINFORCE_BONUS,
    SPREAD_PENALTY,
    EncounterOption,
    SupplyOption,
    _bench_faction_counts,
    _concentration_delta,
    _distinct_factions,
    _economy_mode_for,
    _maybe_sell_for_interest,
    _phase_weights,
    _sample_shop,
    _should_deploy,
    alpha_t,
    char_quality_score,
    decide_encounter,
    decide_event,
    decide_supply,
    economy_score,
    optionality_score,
    plan,
    synergy_score,
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
        "economy_mode": "adaptive",
        "event_whitelist": {"中产阶级": 82, "定期福利": 90},
        "dot_punish_envs": ["净化身心"],
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
    """C 杠杆 2(streak 接线):连胜/连败 magnitude 对称加分(auto-chess streak 档位金);0 streak 无加。

    fixture 核实(2026-08-11)结算「连胜×N」前缀=方向 → state.streak 带符号。方向驱动的 plan 行为
    (保连胜 vs fold)留 R2-4b,economy 只取 magnitude(连胜/连败都给金)。
    """
    base = GameState(gold=50, round_num=5, level=6, plane=2)             # streak 默认 0
    win3 = GameState(gold=50, round_num=5, level=6, plane=2, streak=3)   # 连胜 3
    loss3 = GameState(gold=50, round_num=5, level=6, plane=2, streak=-3)  # 连败 3
    assert economy_score(win3, "adaptive") > economy_score(base, "adaptive"), "连胜 3 > 无 streak"
    assert economy_score(win3, "adaptive") == pytest.approx(economy_score(loss3, "adaptive")), (
        "连胜/连败 magnitude 对称(都给档位金)"
    )


def test_get_node_goal_node_plan_rules() -> None:
    """node_plan 骨架(14 §2):节点 → NodeGoal target_level / spend_mode(人玩节奏)。"""
    from sr_od.application.currency_war.cw_decisions import get_node_goal
    assert (get_node_goal(1, 1).target_level, get_node_goal(1, 1).spend_mode) == (4, "saving"), "P1 早期 冲Lv4 攒息"
    assert (get_node_goal(1, 5).target_level, get_node_goal(1, 5).spend_mode) == (6, "interest"), "P1 中期 Lv6 吃息"
    assert (get_node_goal(2, 5).target_level, get_node_goal(2, 5).spend_mode) == (8, "level"), "P2 中后期 升 8 搜核心"
    assert (get_node_goal(3, 1).target_level, get_node_goal(3, 1).spend_mode) == (9, "allin"), "P3 早期 上 9"
    assert (get_node_goal(3, 5).target_level, get_node_goal(3, 5).spend_mode) == (10, "allin"), "P3 后期 上 10"


def test_get_node_goal_fallback() -> None:
    """未匹配(plane>3 / round 超区间)→ fallback:target_level=_expected_level, spend_mode=adaptive。"""
    from sr_od.application.currency_war.cw_decisions import (
        _expected_level,
        get_node_goal,
    )
    fb = get_node_goal(4, 1)   # plane 4 无规则(CW 3 位面)→ fallback
    assert fb.target_level == _expected_level(1, 4)
    assert fb.spend_mode == "adaptive"


def test_maybe_sell_for_interest_allin_skips() -> None:
    """node_plan spend_mode allin(P3)→ _maybe_sell_for_interest 跳过(花光成型不囤息;14 §2.2)。"""
    from sr_od.application.currency_war.cw_decisions import _maybe_sell_for_interest
    cfg = _cfg()
    # P3 round 3 → allin;gold 39 + 可卖 bench(飞霄,refund 1 → 跨 40 档)→ 正常会卖,allin 跳过
    state = GameState(gold=39, round_num=3, level=9, plane=3,
                      bench=[BenchChar(slot=0, char_id='飞霄', faction='追击', star=1)])
    actions: list = []
    _maybe_sell_for_interest(state, actions, cfg.character_priority, cfg)
    assert not any(isinstance(a, SellBench) for a in actions), "P3 allin → 不卖息(花光成型)"


def test_sample_cost_uses_refresh_prob() -> None:
    """A4.3:_sample_cost 用 REFRESH_PROB 权威表(Lv1-3 纯 1 费;Lv4 只 1/2/3 费;Lv10 不出表外)。"""
    from sr_od.application.currency_war.cw_decisions import _sample_cost
    rng = random.Random(0)
    assert all(_sample_cost(1, rng) == 1 for _ in range(20)), "Lv1 纯 1 费(REFRESH_PROB[1]={1:1.0})"
    for _ in range(50):
        assert _sample_cost(4, rng) in (1, 2, 3), "Lv4 只 1/2/3 费(不出 4/5)"
    for _ in range(50):
        assert 1 <= _sample_cost(10, rng) <= 5, "Lv10 出 1-5 费(不出表外)"


def test_phase_weights_hp_danger_reduces_economy() -> None:
    """A3 + review agent:HP 危险才保血(economy 降权);健康时 economy 不压(snowball 到 50)。
    原"前期 plane1 → economy 0.4"已被研究推翻(前期该 snowball 经济),改测 HP 维度。"""
    from sr_od.application.currency_war.cw_decisions import evaluate
    cfg = _cfg()
    healthy = GameState(gold=50, round_num=3, level=5, plane=1)         # hp100 健康:economy 权重 1.0
    danger = GameState(gold=50, round_num=3, level=5, plane=1, hp=30)   # hp<HP_DANGER:economy 权重 0.4
    # 同 economy_score(50 金),HP 危险时 economy 降权 → evaluate 总分更低
    assert evaluate(healthy, cfg, cfg.faction_priority) > evaluate(danger, cfg, cfg.faction_priority), (
        "HP 危险时 economy 降权,总分 < 健康(同为 plane1)"
    )


def test_refresh_cap_dynamic() -> None:
    """_refresh_cap 关键回合放宽(review agent + 用户:固定 2 太死)。"""
    from sr_od.application.currency_war.cw_decisions import (
        MAX_REFRESH_PER_ROUND,
        _refresh_cap,
    )
    base = GameState(gold=50, round_num=3, level=5, plane=1, hp=100)     # 健康前期
    assert _refresh_cap(base) == MAX_REFRESH_PER_ROUND, "健康前期 = 基线 2"
    late = GameState(gold=50, round_num=6, level=8, plane=3, hp=100)     # plane3/升8
    assert _refresh_cap(late) > MAX_REFRESH_PER_ROUND, "plane3/升8 放宽"
    danger = GameState(gold=50, round_num=3, level=5, plane=1, hp=30)    # HP 危险
    assert _refresh_cap(danger) > MAX_REFRESH_PER_ROUND, "HP 危险放宽"


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
    from sr_od.application.currency_war.cw_decisions import (
        TARGET_PROGRESS_WEIGHT,
        _target_progress_remaining,
        evaluate,
    )
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

    强制 target=击破流萤(``character_build_around=['流萤']`` 只放过含流萤的 comp);
    空板 + 金 1(只够买 1 张)+ 商店[击破 cost1, 列车同行 cost1]。
    - reactive(无 target):synergy 上 列车同行(ceiling 0.5)> 击破(0.33)→ 会先买列车同行;
    - 有 target:击破买还降击破流莺 target_progress 剩余(+WP×0.167 ≈ 2.5)→ 击破反超 → 买击破。
    **断线(plan 不传 target)= 退回 reactive 买列车同行 → 本测试失败**(回归守卫)。
    """
    cfg = _cfg(character_build_around=["流萤"])
    state = GameState(
        gold=1, round_num=1, level=1, plane=1,
        shop=[ShopCard(x=1, faction="击破", name="", cost=1),
              ShopCard(x=2, faction="列车同行", name="", cost=1)],
    )
    actions = plan(state, cfg, cfg.faction_priority, rng=random.Random(0))
    buys = [a for a in actions if isinstance(a, BuyCard)]
    assert buys, "金 1 够买 cost1,应至少买入 1 张"
    assert buys[0].card.faction == "击破", (
        "有 target(击破流萤)时应买击破(target 阵营),而非 reactive 偏好的列车同行"
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
    击破流萤 = get_comp("击破流萤")   # factions=['击破']
    dot队 = get_comp("DOT队")         # factions=['持续伤害','减益']
    cfg = _cfg()
    state = GameState(
        gold=3, round_num=3, level=5, plane=1,
        shop=[ShopCard(x=1, faction="击破", name="", cost=1),
              ShopCard(x=2, faction="持续伤害", name="", cost=1)],
    )
    a1 = plan(state, cfg, cfg.faction_priority, rng=random.Random(0), target_comp=击破流萤)
    buys1 = [a for a in a1 if isinstance(a, BuyCard)]
    a2 = plan(state, cfg, cfg.faction_priority, rng=random.Random(0), target_comp=dot队)
    buys2 = [a for a in a2 if isinstance(a, BuyCard)]
    assert buys1, "target=击破流萤 应买牌"
    assert buys1[0].card.faction == "击破", "target=击破流萤 → 买击破(target 阵营)"
    assert buys2, "target=DOT队 应买牌"
    assert buys2[0].card.faction == "持续伤害", "target=DOT队 → 买持续伤害(target 阵营)"


def test_plan_no_levelup_at_max() -> None:
    """满级(10)时不再升等级(level≤10 硬门)。"""
    cfg = _cfg()
    state = GameState(gold=200, round_num=6, level=10, plane=3, bench_full_flag=True)
    actions = plan(state, cfg, cfg.faction_priority)
    assert not any(isinstance(a, LevelUp) for a in actions), "满级不应再升等级"


def test_plan_caps_refresh_per_round() -> None:
    """每回合主动刷新(D 牌)次数 ≤ MAX_REFRESH_PER_ROUND(review r5:防无限刷死代码)。"""
    cfg = _cfg()
    # 高金 + 商店无可用牌 → 刷新期望可能正;即便如此也被上限挡住
    state = GameState(gold=80, round_num=4, level=6, plane=2,
                      shop=[ShopCard(x=1, faction="公司", name="", cost=5)])
    actions = plan(state, cfg, cfg.faction_priority, rng=random.Random(0))
    n_refresh = sum(1 for a in actions if isinstance(a, RefreshShop))
    assert n_refresh <= MAX_REFRESH_PER_ROUND, f"每回合刷新应 ≤ {MAX_REFRESH_PER_ROUND},实际 {n_refresh}"


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


def test_decide_event_whitelist() -> None:
    """选项含白名单名 → 选它。"""
    cfg = _cfg()
    pick = decide_event(["随便一个", "中产阶级", "另一个"], cfg, GameState())
    assert pick.option_idx == 1, "应选白名单'中产阶级'"


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
    from sr_od.application.currency_war.cw_decisions import OPTIONALITY_WEIGHT, evaluate
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
    """P1 过渡羁绊分(review round-4 HIGH-2):仙舟/狼狩/dot/列车/贝洛伯格 ≥2 → tempo;非过渡 ≥2 → 0;<2 → 0。"""
    from sr_od.application.currency_war.cw_decisions import (
        TRANSITION_TEMPO_BONUS,
        transition_tempo_score,
    )
    # 单过渡羁绊凑出(仙舟 2)
    assert transition_tempo_score(GameState(board={'仙舟': 2})) == pytest.approx(TRANSITION_TEMPO_BONUS)
    # 2 过渡羁绊(人上人级:仙舟 + dot)
    assert transition_tempo_score(GameState(board={'仙舟': 2, '持续伤害': 3})) == pytest.approx(2 * TRANSITION_TEMPO_BONUS)
    # 3 过渡羁绊 → 封顶 2(边际递减)
    assert transition_tempo_score(GameState(board={'仙舟': 2, '狼狩': 2, '列车同行': 2})) == pytest.approx(2 * TRANSITION_TEMPO_BONUS)
    # 非过渡羁绊 ≥2 → 0(追击 是成型羁绊非过渡)
    assert transition_tempo_score(GameState(board={'追击': 3})) == 0.0
    # 过渡羁绊只 1 人(未凑出 ≥2)→ 0
    assert transition_tempo_score(GameState(board={'仙舟': 1})) == 0.0


def test_evaluate_transition_tempo_early_game() -> None:
    """过渡羁绊早期(α=0)加分保血(review round-4 HIGH-2);α-fade 同 optionality(已测)。"""
    from sr_od.application.currency_war.cw_decisions import evaluate
    cfg = _cfg()
    early_tempo = GameState(board={'仙舟': 2}, plane=1, round_num=1)   # α=0,有过渡羁绊
    early_empty = GameState(board={}, plane=1, round_num=1)            # α=0,无
    assert evaluate(early_tempo, cfg, cfg.faction_priority) > evaluate(early_empty, cfg, cfg.faction_priority), (
        "早期 α=0 → 过渡羁绊(仙舟2)加分稳血"
    )


def test_phase_weights_hp_threshold_override() -> None:
    """config.hp_safe_threshold 可调保血触发点(D-18 unification):默认 40 时 hp=50 平衡,
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


# —— difficulty → hp_safe_threshold 派生(D-32,向后兼容)——


def test_effective_hp_threshold_fallback_no_difficulty() -> None:
    """difficulty 未检测("")→ 回退 hp_safe_threshold(无该字段 → 40=HP_DANGER)。向后兼容。"""
    s = GameState()  # difficulty 默认 ""
    assert effective_hp_threshold(s, _cfg()) == 40, "无 hp_safe_threshold 字段 → 默认 40"
    cfg50 = _cfg(hp_safe_threshold=50)
    assert effective_hp_threshold(s, cfg50) == 50, "difficulty 未检测 → 用 hp_safe_threshold"


def test_effective_hp_threshold_override_by_difficulty() -> None:
    """selected_difficulty="A8" + override 含 A8 → 用覆盖值(高难更早保血)。"""
    s = GameState(selected_difficulty="A8")
    cfg = _cfg(hp_safe_threshold=40, difficulty_hp_override={"A8": 55})
    assert effective_hp_threshold(s, cfg) == 55, "A8 覆盖优先于 hp_safe_threshold"


def test_effective_hp_threshold_missing_key_falls_back() -> None:
    """difficulty="A4" + override 只含 A8(无 A4 键)→ 回退 hp_safe_threshold。"""
    s = GameState(selected_difficulty="A4")
    cfg = _cfg(hp_safe_threshold=40, difficulty_hp_override={"A8": 55})
    assert effective_hp_threshold(s, cfg) == 40, "override 无 A4 键 → 回退 hp_safe_threshold"


def test_eval_difficulty_aware_hp_threshold() -> None:
    """evaluate 经 effective_hp_threshold 接 difficulty:A8+override=55 时 hp=42<55→保血权重;
    无 difficulty 时 hp=42>40→健康权重(证明 difficulty 派生改变 eval 行为,D-32 接线有效)。"""
    s_a8 = GameState(selected_difficulty="A8", hp=42, plane=1)
    cfg_a8 = _cfg(hp_safe_threshold=40, difficulty_hp_override={"A8": 55})
    assert (_phase_weights(s_a8.plane, s_a8.hp, effective_hp_threshold(s_a8, cfg_a8))
            == (1.2, 0.4, 1.2)), "A8 override=55,hp=42<55 → 保血权重"
    s_none = GameState(hp=42, plane=1)
    assert (_phase_weights(s_none.plane, s_none.hp, effective_hp_threshold(s_none, _cfg()))
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
    """ADR-0102:_economy_mode_for 把 node spend_mode → economy_score 档位(14 §2.2)。"""
    cfg = SimpleNamespace(economy_mode="adaptive")
    # P1 早期 saving → interest_first(攒息 snowball)
    assert _economy_mode_for(GameState(plane=1, round_num=1), cfg) == "interest_first"
    # P1 中期 interest → interest_first
    assert _economy_mode_for(GameState(plane=1, round_num=5), cfg) == "interest_first"
    # P2 level → rush_level(弱化守息 + 强化等级,升人口)
    assert _economy_mode_for(GameState(plane=2, round_num=3), cfg) == "rush_level"
    # P1 后期 hold → adaptive(economy-low 非 economy_mode 处理)
    assert _economy_mode_for(GameState(plane=1, round_num=8), cfg) == "adaptive"
    # P3 allin → adaptive(economy-low 由 _phase_weights plane3 we=0.3)
    assert _economy_mode_for(GameState(plane=3, round_num=2), cfg) == "adaptive"


def test_economy_mode_for_adaptive_falls_back_to_config() -> None:
    """ADR-0102:adaptive 节点(get_node_goal fallback,如 plane>3)→ config.economy_mode 用户偏好辅。"""
    cfg = SimpleNamespace(economy_mode="interest_first")
    assert _economy_mode_for(GameState(plane=4, round_num=1), cfg) == "interest_first"
