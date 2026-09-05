"""货币战争 策略决策(评估函数 + 贪心)测试 —— 纯逻辑,不依赖游戏/百科数据。

验证 cw_decisions 架构:eval 单调性、plan 硬门(gold≥0 / bench-full 必破 / level≤10)、
站位分流、3合1升星、凑整吃息跨档、char_quality 计已上阵、事件白名单/dot 主流派、
economy_mode、boss 克制。用 mock config(SimpleNamespace)避免 config IO。
"""
from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_comps import Comp
from sr_od.application.currency_war.kernel.cw_economy import (
    WIN_STREAK_BREAK_INTEREST,
    _expected_level,
    _refresh_cost,
    clicks_to_next_level,
    economy_score,
    get_node_goal,
    xp_click_cost,
)
from sr_od.application.currency_war.kernel.cw_events import (
    EncounterOption,
    SupplyOption,
    decide_encounter,
    decide_event,
    decide_supply,
)
from sr_od.application.currency_war.kernel.cw_state import (
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
    """mock CurrencyWarConfig(纯属性,决策函数用 getattr 读)。"""
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
    """r69:0126 区间表已删(单局相关≠基准,ADR-0126 三重降级)——get_node_goal 全走 DP;
    无状态传参 → _expected_level 先验 + adaptive fallback(非 0126 表值)。
    DP 带状态查询的语义锁随原 DP 模块退役(语义归 git 历史);此处锁 fallback 语义。"""
    g = get_node_goal(1, 1)
    assert g.target_level == _expected_level(1, 1), "无状态传参 → 先验曲线(非 0126 表)"
    assert g.spend_mode == "adaptive", "fallback spend=adaptive(r69 删表)"
    # 各位面 fallback 同语义(旧表的 saving/interest/level/allin 档位值不再存在)
    for pl, rn in ((1, 5), (2, 5), (3, 1), (3, 5)):
        g = get_node_goal(pl, rn)
        assert g.spend_mode == "adaptive", f"p{pl}r{rn} fallback adaptive"
        assert g.target_level == _expected_level(rn, pl), f"p{pl}r{rn} 先验曲线"


def test_get_node_goal_fallback() -> None:
    """未匹配(plane>3 / round 超区间)→ fallback:target_level=_expected_level, spend_mode=adaptive。"""
    fb = get_node_goal(4, 1)   # plane 4 无规则(CW 3 位面)→ fallback
    assert fb.target_level == _expected_level(1, 4)
    assert fb.spend_mode == "adaptive"


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





def test_rebuild_deployed_from_board_aligns_count_and_rows() -> None:
    """rebuild_deployed_from_board 从 board 重建 deployed,计数=sum(board),back 先填至 back_max 再 front。
    (出处备注:原引用「D-107」为会话局部编号,docs 树无持久索引,出处未考;
    rebuild 后攒息门的消费语义见 ADR-0117 `_saving_for_interest` 门条件。)"""
    from sr_od.application.currency_war.kernel.cw_state import rebuild_deployed_from_board
    dep = rebuild_deployed_from_board({"能量": 2, "护盾": 6}, back_max=6)   # 总 8
    # ADR-0392:rebuild 出槽位表(定长 10 含 None)——计数/口径断言走占用序
    assert sum(1 for d in dep if d is not None) == 8
    assert sum(1 for d in dep if d is not None
               and d.position_pref == "back") == 6    # back_max=6 先填满
    assert sum(1 for d in dep if d is not None
               and d.position_pref == "front") == 2   # 溢出 2 去 front
    assert sum(1 for d in dep if d is not None
               and d.faction == "能量") == 2          # faction 保留
    assert sum(1 for d in dep if d is not None
               and d.faction == "护盾") == 6


# —— level_plan 硬 gate(task#18 经济统一论):level_plan 说 level_up + 够钱 → 强制升级 ——





# —— deploy 站位 + 3合1 + 凑整吃息 + char_quality 已上阵(review r1 新覆盖)——


def test_compound_3merge() -> None:
    """买 3 张同名同星 → 自动合并升星(3×1星→1×2星)。"""
    from sr_od.application.currency_war.kernel.cw_state import bench_occupied
    s = GameState(gold=100)
    for _ in range(3):
        s = simulate(s, BuyCard(ShopCard(x=1, name="阿格莱雅", cost=1, star=1)))
    assert bench_occupied(s.bench) == 1, "3 同名1星应合并为1张"
    merged = [b for b in s.bench if b is not None]
    assert merged[0].star == 2, "合并后应为2星"


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


def test_decide_encounter_reward_neutral_no_tiebreak() -> None:
    """ADR-0519:奖励文本价值分恒中性(先验阶梯未证退役)——碾压局
    两档同难度,奖励文本不再改变选择(无词缀信号时按稳定序);
    不敢难时奖励同样不改变保守选择。"""
    cfg = _cfg()
    comp = _comp(["燃血"])
    formed = GameState(level=8, board={"燃血": 4},
                       deployed=[BenchChar(slot=i) for i in range(4)])
    # 碾压局(form 高)敢难:高难+棱彩 vs 高难+无奖励 → 奖励中性,两者
    # 难度项相同 → 得分平,稳定序(先出现者)胜
    opts = [EncounterOption(idx=0, difficulty=3, rewards=['棱彩装备']),
            EncounterOption(idx=1, difficulty=3, rewards=[])]
    pick = decide_encounter(opts, formed, comp, cfg)
    assert pick.idx == 0, "奖励中性:同难度同分,稳定序"
    # 未成型:奖励再好也不选高难
    unformed = GameState(level=1, deployed=[])
    opts2 = [EncounterOption(idx=0, difficulty=1, rewards=[]),
             EncounterOption(idx=1, difficulty=3, rewards=['棱彩装备'])]
    pick2 = decide_encounter(opts2, unformed, comp, cfg)
    assert pick2.idx == 0, "不敢难时好奖励不改变保守选择"


def test_reward_value_tiers() -> None:
    """ADR-0519:奖励文本价值分恒中性 0.5(先验阶梯未证退役,保守缺省)。"""
    from sr_od.application.currency_war.kernel.cw_events import _reward_value
    assert _reward_value(['棱彩装备']) == 0.5
    assert _reward_value(['进阶武装']) == 0.5
    assert _reward_value(['简易装备']) == 0.5
    assert _reward_value(['经验']) == 0.5
    assert _reward_value([]) == 0.5   # OCR 漏/无 → 中性不惩罚


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
    """P2+ 上浮由首达模型解出(W443 两态标定合一后现语义;ADR-0176 的
    「上浮」主张随 PLANE_LOSS_SCALE 退役,方向由标定决定):

    - P1:精确零漂移(ratio 分母恒等 → base 原值,M57 行为保持);
    - 弱板(lv4 → tier0)P2:不上浮(P2 标定 μ0≈13.2 低于 P1 弱板先验
      μ0=14 → ratio 夹下界 1.0)——「P2 恒更凶」旧先验不回植;
    - 中板(lv7 → tier2)P2:上浮(μ2≈4.6 > μ1=2.5)且落健康带;
    - P3 别名 P2 逐位相等(标定域声明);
    - 强板(lv10)顶 2.0 夹界(P1 分支 μ=0.8 极小)。
    """
    # P1 零漂移
    assert effective_hp_threshold(GameState(plane=1, level=4)) == 40
    # 弱板(lv4 → tier0)P2 不上浮(P1 先验 μ0=14 ≥ P2 标定 μ0)
    assert effective_hp_threshold(GameState(plane=2, round_num=1, level=4)) == 40
    # 中板(lv7 → tier2)P2 上浮落健康带
    t_p2 = effective_hp_threshold(GameState(plane=2, round_num=1, level=7))
    assert 40 < t_p2 <= 80, "中板 P2 上浮(模型导出)"
    # P3 剩余日程更短(同轮次 P3 已到后程,nodes_left 更少)→ 阈值略低
    t_p3 = effective_hp_threshold(GameState(plane=3, round_num=1, level=7))
    assert t_p3 < t_p2, "P3 同轮次剩余日程更短 → 所需缓冲更低(位面维=P2 别名)"
    # 强板(lv10 → tier 满)顶夹界(base×2.0 封顶)
    t_p2_strong = effective_hp_threshold(GameState(plane=2, round_num=1, level=10))
    assert t_p2_strong == min(100, 2 * 40), "强板 P2 顶 2.0 夹界"


# —— _board_alignment + shop_supply 收紧(梯度语义见 ADR-0105 board penalty)——


def test_board_alignment_deep_shallow_none() -> None:
    """_board_alignment —— board count≥2 → ×1.2(boost);count≥1 → ×1.0(neutral);
    全无 → ×0.3(重 penalty;×0.7→×0.3 的加深出自策略 review:原值压不过 acq 主导致
    spread,裁决与调参记录见 ADR-0105「_board_alignment 全不匹配 ×0.3(原 ×0.7)」)。"""
    from sr_od.application.currency_war.kernel.cw_comps import _board_alignment
    comp = Comp(name="test", factions=["仙舟", "追击"], core_chars=[],
                form_tiers={"仙舟": 5, "追击": 3}, strength="S", form_difficulty="medium")
    # deep-stack(仙舟:2)→ boost
    assert _board_alignment(comp, GameState(board={"仙舟": 2, "能量": 1})) == 1.2
    # shallow(仙舟:1)→ neutral
    assert _board_alignment(comp, GameState(board={"仙舟": 1, "能量": 1})) == 1.0
    # 全无 comp 阵营 → penalty
    assert _board_alignment(comp, GameState(board={"能量": 2, "护盾": 1})) == 0.3


def test_shop_supply_core_vs_noncore() -> None:
    """shop_supply 收紧(shop_supply 与 _board_alignment 同批收紧,ADR-0105 spread 修)——
    核心(form_tiers)阵营在 shop → 1.0;仅非核心 → 0.5。"""
    from sr_od.application.currency_war.kernel.cw_comps import shop_supply
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


def _mk_card(faction: str, cost: int, name: str = '未知卡') -> ShopCard:
    return ShopCard(x=500, faction=faction, name=name, cost=cost)


# ===== ADR-0125/0127 review 补测(H1 窗口语义 / room-bench / 同名 deploy 去重)=====

def _bc_at(slot, name, star=1, faction='?') -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


@pytest.mark.xfail(reason='r17 已知缺口:全场 3合1 落地后 eval 缺 star-aware 战力计价'
                   '(人数-2 vs 星级+1 在当前 eval 框架恒负);修法=synergy/comp_strength 星级敏感化,挂策略批',
                   strict=False)
# ===== ADR-0129 购买经验决策(单击价模型替整级大金;升级滞后 live 实锤修复) =====
def test_xp_helpers_clicks_and_cost() -> None:
    """clicks_to_next_level 向上取整;xp_click_cost 用 OCR 实读优先。"""
    assert clicks_to_next_level(GameState(level=5, xp_progress=(0, 20), hp=100)) == 5
    assert clicks_to_next_level(GameState(level=5, xp_progress=(18, 20), hp=100)) == 1
    assert clicks_to_next_level(GameState(level=6, xp_progress=None, hp=100)) == 10   # 40 XP / 4
    assert clicks_to_next_level(GameState(level=10, xp_progress=(0, 84), hp=100)) == 0
    assert xp_click_cost(GameState(level=5, hp=100)) == 4                      # 兜底
    assert xp_click_cost(GameState(level=5, level_up_cost=8, hp=100)) == 8     # OCR 实读


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
    from sr_od.application.currency_war.kernel.cw_investments import aggregate_economy
    e = aggregate_economy(['开源节流', '利息上调'])
    assert e.interest_cap_override == 10
    assert e.instant_gold == 35
    e2 = aggregate_economy(['加油站', '加油站'])
    assert e2.free_refresh_per_node == 2, "同名策略双持(理论)额度求和"


def test_economy_reclassified_fields_adr0142() -> None:
    """ADR-0142:9 条曾错装一次性 instant_gold 的重复性效果按原文归位。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
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
    """注册表全量 335(plaza API base 334,ADR-0150;+补遗 1,ADR-0133 ingest 体系);
    长尾经济抽取抽查。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
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
    """评估分(知识判据定序器)> 回落字典序 > 未注册 0(ADR-0524)。"""
    cfg = _cfg()
    st = GameState(board={}, hp=100)
    assert decide_event(["定期福利", "乱成一锅粥+"], cfg, st).option_idx == 0, "评估分高者胜"
    assert decide_event(["无名甲", "乱成一锅粥+"], cfg, st).option_idx == 1, "评估分(回落域之上) > 未注册 0"
    # 未注册(0) vs 回落字典序(>0) → 回落胜
    assert decide_event(["银色无名", "及时雨"], cfg, st).option_idx == 1


def test_decide_event_fallback_lexicographic() -> None:
    """品质回落纯字典序(ADR-0524,16 号稿 §1.6):主键=品质序(棱彩>金>银,
    游戏定义),次键=economy 有无;零拍值——旧 50/30/10/+economy20 序到分
    映射无推导已删。行为翻转已申报:翻转方向 = 向游戏定义序收敛(保守化)。"""
    cfg = _cfg()
    st = GameState(board={}, hp=100)
    # 主键:棱彩无经济 > 金无经济(旧制 50>30 同序,翻转面守护)
    pick = decide_event(["不虚此行", "狸狸的早晨"], cfg, st)
    assert pick.option_idx == 1 and 'prior' in pick.reason, "品质序主键:棱彩 > 金"
    # 翻转锁(旧制金 30 vs 银+经济 30 平手取前者 → 新制品质序定序:金 > 银有经济)
    pick2 = decide_event(["星星相印", "不虚此行"], cfg, st)
    assert pick2.option_idx == 1, "翻转锁:金 > 银有经济(旧制平手,新制主键定序)"
    # 次键:经济有无只在同品质内生效(棱彩+经济 > 棱彩无经济)
    pick3 = decide_event(["狸狸的早晨", "狸财经狸"], cfg, st)
    assert pick3.option_idx == 1, "次键:同品质内经济有无"
    # 回落域整体压低于评估分域(回落=「未评估时别全盲」,评估分有知识判据依据;
    # 翻转已申报:旧制棱彩+经济 70 曾压过评估分 12-65 段,新制一律评估分优先)
    pick4 = decide_event(["狸财经狸", "恢复生机"], cfg, st)
    assert pick4.option_idx == 1, "回落域 < 评估分域:评估分 12 > 回落最高档"
    # 未注册(0)仍在回落域之下(全盲才兜底 idx0)
    pick5 = decide_event(["狸狸的早晨", "银色无名"], cfg, st)
    assert pick5.option_idx == 0



# ===== ADR-0134 comp 匹配分(星徽套组对齐 target 压倒品质/白名单) =====
def test_strategy_bindings_extraction() -> None:
    """绑定派生:追击星徽套组 → (追击, 飞霄);无绑定策略 → 空集(安全回落)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        get_strategy,
        strategy_bindings,
    )
    fs, cs = strategy_bindings(get_strategy("追击星徽套组"))
    assert "追击" in fs and "飞霄" in cs
    fs2, cs2 = strategy_bindings(get_strategy("数值碾压"))
    assert not fs2 and not cs2, "纯战力无绑定 → 空(回落品质先验)"


def test_decide_event_comp_match_wins() -> None:
    """星徽套组对齐 target(飞霄)→ comp 命中域压过基准域;不对齐 = 回落字典序(ADR-0524)。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    feixiao = next(c for c in COMP_LIBRARY if "飞霄" in c.core_chars)
    cfg = _cfg()
    st = GameState(board={}, hp=100)
    # 对齐套组(追击+飞霄)= 双命中(45×2+20=110)压评估分与单命中;成型加速语义。
    pick = decide_event(["定期福利", "追击星徽套组"], cfg, st, target_comp=feixiao)
    assert pick.option_idx == 1 and 'comp-hit×2' in pick.reason, "双命中 110 > 评估分"
    # 不对齐:燃血套组 vs 追击 target → 无命中 = 回落字典序 < 评估分
    pick2 = decide_event(["定期福利", "燃血星徽套组"], cfg, st, target_comp=feixiao)
    assert pick2.option_idx == 0, "不对齐套组 = 回落域 < 评估分域"
    # N 定序锁:N=1(65)压回落域与低评估分,但被 N=2(110)压过(N 大者优先)
    pick_n1 = decide_event(["恢复生机", "追击星徽套组"], cfg, st, target_comp=feixiao)
    assert pick_n1.option_idx == 1 and 'comp-hit' in pick_n1.reason, "N≥1 域压过基准域"
    # 无 target(None)→ 无命中,回落字典序
    pick3 = decide_event(["无名甲", "乱成一锅粥+"], cfg, st)
    assert pick3.option_idx == 1


def test_decide_event_augment_dominance() -> None:
    """augment 定义型支配性优先序(ADR-0524,16 号稿 §1.4):定义型 > 一切常规
    评估项(含 comp-hit 双命中 110),仅低于用户 forbid;120 = 定序实现常数。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    feixiao = next(c for c in COMP_LIBRARY if "飞霄" in c.core_chars)
    st = GameState(board={}, hp=100)
    # 定义型(黑塔纪元,120)压过 comp-hit 双命中(110)
    pick = decide_event(["追击星徽套组", "黑塔纪元"], _cfg(), st, target_comp=feixiao)
    assert pick.option_idx == 1 and pick.reason.startswith('augment-defining'), \
        f"定义型支配:120 > comp-hit 110,实得 {pick.reason}"
    # 仅低于 forbid:用户 forbid 的定义型让位(steering hard− 10000)
    cfg_fb = _cfg(strategy_forbid=["黑塔纪元"])
    pick2 = decide_event(["追击星徽套组", "黑塔纪元"], cfg_fb, st, target_comp=feixiao)
    assert pick2.option_idx == 0, "forbid 是唯一压过定义型的家"


def test_env_faction_floor_category_tiers() -> None:
    """阵营匹配定序门(ADR-0524,16 号稿 §1.3):三档值 = category 定序档位
    邀请(70)< 契约(72)< 概念股(78);匹配 ⇒ 提到本 category 档位、压过全体
    env 裸分上界 72;禁读基数——档位序锁在 dict 本体。"""
    from sr_od.application.currency_war.kernel.cw_investments import ENV_FACTION_MATCH_FLOOR
    # 档位序锁(定序语义本体)
    assert (ENV_FACTION_MATCH_FLOOR['邀请'] < ENV_FACTION_MATCH_FLOOR['契约']
            < ENV_FACTION_MATCH_FLOOR['概念股']), "category 定序档位:邀请<契约<概念股"
    cfg = _cfg()
    st = GameState(board={}, hp=100, hp_readable=True)
    tgt = Comp(name="t3", factions=["追击"], core_chars=[], form_tiers={"追击": 4},
               strength="A", form_difficulty="medium")
    # 匹配 ⇒ 档位压过全体 env 裸分(78 > 上界 72)
    pick = decide_event(["追击概念股", "彩虹时代"], cfg, st, target_comp=tgt)
    assert pick.option_idx == 0 and 'env-faction' in pick.reason, "匹配档位 > 裸分上界"



def test_comp_char_positions_data() -> None:
    """三 comp 站位数据在库:绯英(爻光 back)/追击(知更鸟 front)/万敌(万敌 front)。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    by = {c.name: c.char_positions for c in COMP_LIBRARY}
    assert by["绯英欢愉"].get("爻光") == "back"
    assert by["追击飞霄"].get("知更鸟") == "front"
    assert by["万敌单C"].get("万敌") == "front"



# ===== ADR-0140 中期护航三套:已随清退评估批删除(2026-09) =====
# escort_for/ESCORT_COMPS/GROWTH_MECHANICS 生产消费点早已清零,清查报告
# OLD_MIX_AUDIT §7.2 裁定整段删除,本单测同批移除(锁的是已死词汇,非设计意图)。


# ===== ADR-0141 品质→敌难度进选卡(已退役面;ADR-0519) =====
def test_decide_event_refresh_suggestion_retired() -> None:
    """ADR-0519:刷新建议阈值(EVENT_REFRESH_SCORE_FLOOR=50,评估分中位
    估计)已按「未证即退役」删除——PickEvent.refresh 恒 False,烂手牌
    不再触发建议刷新(保守缺省:不弃当前手牌)。"""
    cfg = _cfg()
    st = GameState(board={}, hp=100, hp_readable=True)
    pick = decide_event(["赌神·银", "恢复生机", "气氛组"], cfg, st)   # 低分烂手牌
    assert pick.refresh is False and 'suggest-refresh' not in pick.reason
    pick2 = decide_event(["彩虹时代", "恢复生机", "气氛组"], cfg, st)  # env 72 高分
    assert pick2.refresh is False


def test_env_pick_value_adr0144() -> None:
    """ADR-0144 环境侧评估分:env 原恒 0 分(fallback 恒选第一张)→ 基准分 + 阵营条件分 + HP 钩子。"""
    from sr_od.application.currency_war.kernel.cw_investments import get_env
    cfg = _cfg()
    st = GameState(board={}, hp=100, hp_readable=True)   # 显式满血态(W823 None 化:默认构造=未观测,不再隐含满血)
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
    # HP 钩子已退役(ADR-0519:env 生存加分未证置 0):白银时代 35 < 增发货币 48
    # 在低血帧同样增发胜(钩子不再改变行为)
    pick_a = decide_event(["白银时代", "增发货币"], cfg, st)
    assert pick_a.option_idx == 1
    st_low = GameState(board={}, hp=20)
    pick_b = decide_event(["白银时代", "增发货币"], cfg, st_low)
    assert pick_b.option_idx == 1, "ADR-0519:低血 env 生存钩子已退役(35 < 48 恒)"
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


def test_decide_event_rarity_penalty_retired() -> None:
    """ADR-0519:品质难度惩罚(棱彩−12/−24、金−6/−12)已按「未证即退役」
    置 0——选卡只按注册表评估分排序,品质不再削分(机制方向金+3/彩+6
    仍是游戏定义知识,幅度无推导不落码)。"""
    cfg = _cfg()
    st = GameState(board={}, hp=100)
    # 评估分:免费午餐 50 银 / 黄金垃圾 48 金 / 乱成一锅粥+ 45 彩 → 银胜(分高者胜)
    pick = decide_event(["免费午餐", "黄金垃圾", "乱成一锅粥+"], cfg, st)
    assert pick.option_idx == 0
    # 高评估彩不再吃削分:鲜血阶梯 75(彩) vs 免费午餐 50(银)→ 彩胜(75 > 50)
    pick_b = decide_event(["鲜血阶梯", "免费午餐"], cfg, st)
    assert pick_b.option_idx == 0
    # 低血帧无加倍惩罚:乱成一锅粥+ 45(彩) vs 尾款交付 30(银)→ 彩胜恒成立
    pick_c = decide_event(["尾款交付", "乱成一锅粥+"], cfg, st)
    assert pick_c.option_idx == 1
    st_low = GameState(board={}, hp=20)
    pick3 = decide_event(["尾款交付", "乱成一锅粥+"], cfg, st_low)
    assert pick3.option_idx == 1, "ADR-0519:HP 加倍惩罚已退役,低血帧同序"
    # 未注册(0) vs 金经济(48)→ 金胜(纯评估分)
    pick2 = decide_event(["银色无名甲", "黄金垃圾"], cfg, st_low)
    assert pick2.option_idx == 1


def test_option_rarity_fallback_retired() -> None:
    """ADR-0519:_option_rarity LCS 品质兜底已随品质惩罚退役(唯一消费 =
    该惩罚),模块不再暴露该符号。"""
    import sr_od.application.currency_war.kernel.cw_events as _ce
    assert not hasattr(_ce, '_option_rarity')

