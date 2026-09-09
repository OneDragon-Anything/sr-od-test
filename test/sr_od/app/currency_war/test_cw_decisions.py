"""货币战争 决策族单元测试(cw_events / cw_economy / cw_state 阈值与 simulate /
cw_comps 对齐与供给 / cw_investments 注册表先验)—— 纯逻辑,不依赖游戏/百科数据。

覆盖面:economy_score 各分项与 economy_mode、get_node_goal 先验 fallback、
3合1 升星(simulate 买入路径)、decide_event 全定序族(steering 轴 / ADR-0524
回落字典序 / ADR-0578 血本位回避 / ADR-0133·0144 注册表先验)、decide_encounter /
decide_supply 分支、effective_hp_threshold 职级表接线与位面相对序。
用 mock config(SimpleNamespace)避免 config IO。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_comps import Comp
from sr_od.application.currency_war.kernel.cw_economy import (
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
    DIFFICULTY_HP_TABLE,
    HP_SAFE_THRESHOLD,
    BenchChar,
    BuyCard,
    GameState,
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
    # 各位面 fallback 同语义(旧表的 saving/interest/level/allin 档位值不再存在);
    # (4, 1) = plane 越界(CW 3 位面)走同一 fallback 支(原独立 fallback 测并入)
    for pl, rn in ((1, 5), (2, 5), (3, 1), (3, 5), (4, 1)):
        g = get_node_goal(pl, rn)
        assert g.spend_mode == "adaptive", f"p{pl}r{rn} fallback adaptive"
        assert g.target_level == _expected_level(rn, pl), f"p{pl}r{rn} 先验曲线"


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
    from sr_od.application.currency_war.kernel.cw_state import (
        rebuild_deployed_from_board,
    )
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
    """strategy_priority:低评估分命中优先轴 → +30 反超(soft 倾向,非硬绑定)。
    T-155 重推:S2 经济引擎档(域带 111-119)入序后,priority +30 的可压面 =
    常规评估域(≤75),压不动引擎域带(锚位语义,ADR-0597)——用例对换成
    两张非引擎卡保原命题(42+30=72 > 48),另加一行边界锁。"""
    cfg = _cfg(strategy_priority=["着眼当下"])   # 着眼当下 42 vs 成本控制 48(均非引擎)
    pick = decide_event(["成本控制", "着眼当下"], cfg, GameState())
    assert pick.option_idx == 1, "priority +30 应让着眼当下(42+30)反超成本控制(48)"
    # 边界锁:soft +30 不可跨越 S2 引擎域带(48+30=78 < 111)
    cfg2 = _cfg(strategy_priority=["成本控制"])   # 成本控制 48(非引擎) vs 免费午餐(引擎)
    pick2 = decide_event(["免费午餐", "成本控制"], cfg2, GameState())
    assert pick2.option_idx == 0 and 'econ-engine' in pick2.reason, \
        f"priority +30 不得把常规评估卡抬过引擎域带,实得 {pick2.reason}"


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
    """ADR-0519:奖励文本价值分恒中性 0.5(先验阶梯未证退役,保守缺省)。

    (CUT7 收缩:5 行 → 2 代表行——_reward_value 是恒值查表,任意奖励
    词形同返 0.5,留具名奖励与空值(OCR 漏/无)两端,2026-09-09。)"""
    from sr_od.application.currency_war.kernel.cw_events import _reward_value
    assert _reward_value(['棱彩装备']) == 0.5
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


# —— difficulty → 保血阈值(D-32;ADR-0204 起阈值表为代码常量 cw_state.DIFFICULTY_HP_TABLE)——


def test_effective_hp_threshold_fallback_no_difficulty() -> None:
    """difficulty 未检测("")→ 回退 HP_SAFE_THRESHOLD(期望从 kernel 单一源现取)。"""
    s = GameState()  # difficulty 默认 ""
    assert effective_hp_threshold(s) == HP_SAFE_THRESHOLD


def test_effective_hp_threshold_override_by_difficulty() -> None:
    """selected_difficulty="A8" + 表含 A8 → 用覆盖值(高难更早保血;期望=表值现取,
    校准值本身的现值锚由 test_cw_w443 的 A8 链式锁间接承载)。"""
    s = GameState(selected_difficulty="A8")
    assert effective_hp_threshold(s) == DIFFICULTY_HP_TABLE["A8"]


def test_effective_hp_threshold_missing_key_falls_back() -> None:
    """表无此键(OCR 读到未收录职级)→ .get 兜底回退 HP_SAFE_THRESHOLD。
    (原体断言 A4=40 实为表命中支,与 override 测同支且对兜底分支零判别力——
    换真缺键 "Z9" 补上该支的判别。)"""
    s = GameState(selected_difficulty="Z9")
    assert effective_hp_threshold(s) == HP_SAFE_THRESHOLD


def test_effective_hp_threshold_plane_model_ratio() -> None:
    """P2+ 上浮由首达模型解出(W443 两态标定合一后现语义)——本测只锁**位面间
    相对序**(独家面):位面维在模型内 = P2 别名,但同 tier 同轮次 P3 已到后程
    (nodes_left 更少)→ 阈值低于 P2。

    P2 现值分布(40/74/73/80)与 P1 零漂移由 test_cw_two_state_unification
    现值锁与结构锚辖,不在此重复(原重复断言按超集留存原则删除)。
    """
    t_p2 = effective_hp_threshold(GameState(plane=2, round_num=1, level=7))
    t_p3 = effective_hp_threshold(GameState(plane=3, round_num=1, level=7))
    assert t_p3 < t_p2, "P3 同 tier 同轮次剩余日程更短 → 所需缓冲更低"


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
    """shop_supply 核心判定取 form_tiers 键非 factions 全集(ADR-0105 spread 修同批收紧):
    仅**非核心**阵营(盛会之星:factions 有、form_tiers 无)在 shop → 0.5 半信号。
    1.0(core 在 shop)/0.3(board-only)/0.0(都无)三分支由 test_cw_comps
    shop_supply 组锁,不在此重复(原 core→1.0 断言与其同支同值,已删)。"""
    from sr_od.application.currency_war.kernel.cw_comps import shop_supply
    target = Comp(name="test", factions=["仙舟", "追击", "盛会之星"], core_chars=[],
                  form_tiers={"仙舟": 5, "追击": 3}, strength="S", form_difficulty="medium")
    s_noncore = GameState(shop=[ShopCard(x=1, faction="盛会之星", name="", cost=1)])
    assert shop_supply(target, s_noncore) == 0.5


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
    """注册表长尾经济抽取抽查(ADR-0133 ingest 体系)。全量计数 335 由
    test_cw_investment.test_adr0150_base_layer_full 锁,不在此重复计数。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        get_strategy,
    )
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
    assert decide_event(["无名甲", "乱成一锅粥+"], cfg, st).option_idx == 1, "评估分 > 未注册 0"
    # (原「银色无名 vs 及时雨」断言已删:回落域 > 未注册域的交界由
    #  test_decide_event_fallback_lexicographic pick5 同事实锁定,此处不再双写。)


def test_decide_event_fallback_lexicographic(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """品质回落纯字典序(ADR-0524,16 号稿 §1.6):主键=品质序(棱彩>金>银,
    游戏定义),次键=economy 有无;零拍值——旧 50/30/10/+economy20 序到分
    映射无推导已删。行为翻转已申报:翻转方向 = 向游戏定义序收敛(保守化)。
    T-155 重推(ADR-0597):注册表内未评卡+有经济卡已全部为持续通道卡
    (落 S2 引擎域带,不再走回落域),回落域对位改合成注入条目保原命题
    (teardown 自动恢复,同 test_decide_event_unevaluated_blood_candidate_level)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        INVESTMENT_STRATEGIES,
        EconomyEffect,
        InvestmentStrategy,
    )
    monkeypatch.setitem(
        INVESTMENT_STRATEGIES, '测试银卡',
        InvestmentStrategy(name='测试银卡', rarity='银', effect='测试注入',
                           economy=EconomyEffect(instant_gold=6)))
    monkeypatch.setitem(
        INVESTMENT_STRATEGIES, '测试彩卡乙',
        InvestmentStrategy(name='测试彩卡乙', rarity='棱彩', effect='测试注入',
                           economy=EconomyEffect(instant_gold=6)))
    cfg = _cfg()
    st = GameState(board={}, hp=100)
    # 主键:棱彩无经济 > 金无经济(旧制 50>30 同序,翻转面守护)
    pick = decide_event(["不虚此行", "狸狸的早晨"], cfg, st)
    assert pick.option_idx == 1 and 'prior' in pick.reason, "品质序主键:棱彩 > 金"
    # 翻转锁(旧制金 30 vs 银+经济 30 平手取前者 → 新制品质序定序:金 > 银有经济)
    pick2 = decide_event(["测试银卡", "不虚此行"], cfg, st)
    assert pick2.option_idx == 1, "翻转锁:金 > 银有经济(旧制平手,新制主键定序)"
    # 次键:经济有无只在同品质内生效(棱彩+经济 > 棱彩无经济)
    pick3 = decide_event(["狸狸的早晨", "测试彩卡乙"], cfg, st)
    assert pick3.option_idx == 1, "次键:同品质内经济有无"
    # 回落域整体压低于评估分域(回落=「未评估时别全盲」,评估分有知识判据依据;
    # 翻转已申报:旧制棱彩+经济 70 曾压过评估分 12-65 段,新制一律评估分优先)
    pick4 = decide_event(["测试彩卡乙", "恢复生机"], cfg, st)
    assert pick4.option_idx == 1, "回落域 < 评估分域:评估分 12 > 回落最高档"
    # 未注册(0)仍在回落域之下(全盲才兜底 idx0)
    pick5 = decide_event(["狸狸的早晨", "银色无名"], cfg, st)
    assert pick5.option_idx == 0


# ===== ADR-0134 comp 匹配分(星徽套组对齐 target 压倒品质/白名单) =====
# (原 test_strategy_bindings_extraction 已删:追击星徽套组绑定精确等值锁在
#  test_cw_investment.test_adr0151_semantic_bindings_present,无绑定回落支在
#  test_adr0151_bindings_table_valid —— 两断言面均为其子集/等价。)
def test_decide_event_comp_match_wins() -> None:
    """S3 终局对齐族语义锁(T-155 重推;ADR-0597):对齐对象 = D* 预期终局
    方向(①锁线级联),不再消费过渡对 target_comp——旧锁语义(∩过渡对)已随
    用户裁定「投资选卡不为过渡阵容服务」过期,本锁改构造 D*① 锁线。
    对齐套组(追击+飞霄)∩D*(追击飞霄)= 双命中(45×2+20=110)压评估分与
    单命中;不对齐 = 回落字典序(ADR-0524)。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    feixiao_comp = next(c for c in COMP_LIBRARY if "飞霄" in c.core_chars)
    cfg = _cfg()
    st = GameState(board={}, hp=100)
    # 对齐套组(追击+飞霄)= 双命中 110 > 评估分(对位卡换鲜血阶梯 75——
    # 原对位定期福利已入 S2 引擎域带 115 > 110,域带语义由 priority 锁边界行承载)
    pick = decide_event(["鲜血阶梯", "追击星徽套组"], cfg, st,
                        locked_comp=feixiao_comp.name)
    assert pick.option_idx == 1 and 'align×2' in pick.reason, "双命中 110 > 评估分"
    # 不对齐:燃血套组 vs 追击 D* → 无命中 = 回落字典序 < 评估分
    pick2 = decide_event(["鲜血阶梯", "燃血星徽套组"], cfg, st,
                         locked_comp=feixiao_comp.name)
    assert pick2.option_idx == 0, "不对齐套组 = 回落域 < 评估分域"
    # N 定序锁:N=1(65)压回落域与低评估分,但被 N=2(110)压过(N 大者优先)
    pick_n1 = decide_event(["恢复生机", "追击星徽套组"], cfg, st,
                           locked_comp=feixiao_comp.name)
    assert pick_n1.option_idx == 1 and 'align×' in pick_n1.reason, "N≥1 域压过基准域"


def test_decide_event_d_star_cascade() -> None:
    """D* 级联消费面语义锁(T-155 重推时并入本簇;ADR-0597 §5.1/§5.1.1):
    ①层信号(投资亲和)不进 D*;evicted 线不进 D*(「等同信号未发生」契约的
    消费面镜像);weak_planes 弱面线不进 D*;demoted_endgame → D*=∅。"""
    from sr_od.application.currency_war.kernel.cw_state import ShopCard
    st = GameState(board={}, hp=100, plane=1)
    st.shop = [ShopCard(x=1, name='姬子·启行', cost=3, star=1)]
    # ②资产信号 → S3 对齐(列车同行绑定集)
    pick = decide_event(["追击星徽套组", "列车同行星徽套组"], _cfg(), st)
    assert 'align×' in pick.reason and pick.option_idx == 1, \
        f"D*②(核心在店)应喂 S3 对齐,实得 {pick.reason}"
    # evicted 继承:列车同行被意向层驱逐 → 信号视同未发生 → S3 全 N=0
    pick2 = decide_event(["追击星徽套组", "列车同行星徽套组"], _cfg(), st,
                         evicted=frozenset({'列车同行'}))
    assert 'align' not in pick2.reason, \
        f"被驱逐线不得进 D*,实得 {pick2.reason}"
    # demoted_endgame → D*=∅(降格终局无对齐语义)
    pick3 = decide_event(["追击星徽套组", "列车同行星徽套组"], _cfg(), st,
                         locked_comp='列车同行', demoted_endgame=True)
    assert 'align' not in pick3.reason, f"降格帧 D*=∅,实得 {pick3.reason}"
    # ①层排除:投资环境亲和(银河学者概念股→大黑塔银河学者)只发①信号,
    # 不进 D*(反投资自证:候选卡的亲和不得参与证明选它自己)
    st2 = GameState(board={}, hp=100, plane=1)
    st2.active_env = '银河学者概念股'
    pick4 = decide_event(["银河学者星徽套组", "追击星徽套组"], _cfg(), st2)
    assert 'align' not in pick4.reason, \
        f"①层亲和信号不得进 D*(投资自证环),实得 {pick4.reason}"


def test_decide_event_augment_dominance() -> None:
    """augment 定义型支配性优先序(ADR-0524,16 号稿 §1.4):定义型 > 一切常规
    评估项(含 S3 对齐双命中 110/S2 域带),仅低于用户 forbid;120 = 定序实现
    常数。T-155 重推:对齐构造换 D*① 锁线(旧 target_comp 已退役,ADR-0597)。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    feixiao_comp = next(c for c in COMP_LIBRARY if "飞霄" in c.core_chars)
    st = GameState(board={}, hp=100)
    # 定义型(黑塔纪元,120)压过 S3 对齐双命中(110)
    pick = decide_event(["追击星徽套组", "黑塔纪元"], _cfg(), st,
                        locked_comp=feixiao_comp.name)
    assert pick.option_idx == 1 and pick.reason.startswith('augment-defining'), \
        f"定义型支配:120 > align 110,实得 {pick.reason}"
    # 仅低于 forbid:用户 forbid 的定义型让位(steering hard− 10000)
    cfg_fb = _cfg(strategy_forbid=["黑塔纪元"])
    pick2 = decide_event(["追击星徽套组", "黑塔纪元"], cfg_fb, st,
                         locked_comp=feixiao_comp.name)
    assert pick2.option_idx == 0, "forbid 是唯一压过定义型的家"


def test_env_faction_floor_category_tiers() -> None:
    """阵营匹配定序门·档位序锁(ADR-0524,16 号稿 §1.3):三档值 = category
    定序档位 邀请(70)< 契约(72)< 概念股(78),禁读基数——档位序锁在 dict 本体。
    「匹配 ⇒ 档位压过全体 env 裸分」行为面由 test_env_pick_value_adr0144
    (pick3/pick_d)锁,原此处同入同判的重复 pick 已删。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        ENV_FACTION_MATCH_FLOOR,
    )
    assert (ENV_FACTION_MATCH_FLOOR['邀请'] < ENV_FACTION_MATCH_FLOOR['契约']
            < ENV_FACTION_MATCH_FLOOR['概念股']), "category 定序档位:邀请<契约<概念股"


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
    """刷新建议判据换代(T-162 重立,2026-09 设计四轮对抗定稿;旧锁语义过期声明:
    旧断言「评估分阈值退役 → refresh 恒 False、烂手牌不刷」钉的是 ADR-0519 C10
    的阈值式判据——该判据按 T-162 换推导重立为**零阈值结构存在性判据**(无
    S1/S2 顶级卡 ∧ max_N≠1 即触发),「烂手牌」恰是新判据的核心触发帧,旧语义
    被设计明文取代,非机械跟绿)。新语义:全普通三卡 → 建议刷全部槽;env 混合帧
    (fail-closed 轴钉死)仍恒不刷。"""
    cfg = _cfg()
    st = GameState(board={}, hp=100, hp_readable=True)
    pick = decide_event(["赌神·银", "恢复生机", "气氛组"], cfg, st)   # 全普通手牌
    assert pick.refresh is True and pick.refresh_slots == (0, 1, 2)
    assert 'refresh-suggest' in pick.reason
    pick2 = decide_event(["彩虹时代", "恢复生机", "气氛组"], cfg, st)  # env 混合帧 → 阻断
    assert pick2.refresh is False and pick2.refresh_slots == ()


def test_env_pick_value_adr0144() -> None:
    """ADR-0144 环境侧评估分:env 原恒 0 分(fallback 恒选第一张)→ 基准分 + 阵营条件分 + HP 钩子。"""
    from sr_od.application.currency_war.kernel.cw_investments import get_env
    cfg = _cfg()
    st = GameState(board={}, hp=100, hp_readable=True)   # 显式满血态(W823 None 化:默认构造=未观测,不再隐含满血)
    # 基准分:彩虹时代 72 > 增发货币 48(旧:全 0 分 → 恒选第一张)
    pick = decide_event(["增发货币", "彩虹时代"], cfg, st)
    assert pick.option_idx == 1
    assert 'env-eval' in pick.reason
    # 阵营条件分:无 comp 时 追击概念股 52 < 彩虹时代 72;D* 含追击 → floor 78 反超
    # (T-155 重推:floor 触发条件从 target_comp 换 D*① 锁线,ADR-0597;归因串
    # env-faction → align-locked = D* 来源级)
    pick2 = decide_event(["追击概念股", "彩虹时代"], cfg, st)
    assert pick2.option_idx == 1, "无 comp:裸分 52 < 72"
    pick3 = decide_event(["追击概念股", "彩虹时代"], cfg, st, locked_comp='追击飞霄')
    assert pick3.option_idx == 0 and 'align-locked' in pick3.reason, "D* 匹配:78 > 72"
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
    # (对位卡换着眼当下 42——原对位免费午餐已入 S2 引擎域带,ADR-0597)
    pick_c = decide_event(["着眼当下", "彩虹时代"], cfg, st)   # 42 vs 72
    assert pick_c.option_idx == 1
    # ADR-0144b 跨表污染守卫(评审+自查双实证:83 env 名 29 个 LCS 误中策略名):
    # ①env 名不进策略 LCS 兜底(增发货币曾误中超发货币 55 计分);②env 无品质不吃难度惩罚
    # (列车同行概念股曾误中列车同行星徽棱彩 -12,floor 78 被削到 66 —— 评审量化)。
    pick_d = decide_event(["列车同行概念股", "增发货币"], cfg, st, locked_comp='列车同行')
    assert pick_d.option_idx == 0 and 'align-locked' in pick_d.reason, "floor 78 无品质惩罚叠加"
    pick_e = decide_event(["增发货币", "头彩"], cfg, st)   # 48 vs 55:头彩 env 分高,表内胜出(无策略串台)
    assert pick_e.option_idx == 1 and 'env-eval' in pick_e.reason


def test_decide_event_rarity_penalty_retired() -> None:
    """ADR-0519:品质难度惩罚(棱彩−12/−24、金−6/−12)已按「未证即退役」
    置 0——选卡只按注册表评估分排序,品质不再削分(机制方向金+3/彩+6
    仍是游戏定义知识,幅度无推导不落码)。"""
    cfg = _cfg()
    st = GameState(board={}, hp=100)
    # 评估分/引擎域带:免费午餐(引擎,50→115) / 黄金垃圾 48 金 / 乱成一锅粥+(引擎,45→114.6)
    # → 免费午餐胜(T-155 后引擎域带定序,ADR-0597;原「评估分 50 > 48 > 45」同序)
    pick = decide_event(["免费午餐", "黄金垃圾", "乱成一锅粥+"], cfg, st)
    assert pick.option_idx == 0
    # 高评估彩不再吃削分:鲜血阶梯 75(彩,economy None) vs 黄金垃圾 48(金)→ 彩胜
    # (T-155 重推:原对位免费午餐已入引擎域带(115>75),换同域(S4)对位保原命题)
    pick_b = decide_event(["鲜血阶梯", "黄金垃圾"], cfg, st)
    assert pick_b.option_idx == 0
    # 低血帧无加倍惩罚:乱成一锅粥+(引擎域带) vs 尾款交付 30(银)→ 彩胜恒成立
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


# ===== [40]① 选择层血本位回避(T-99①;ADR-0578;裁定 = 2026-08-31 OPEN-6
# ===== 「主动选择=回避」,user_playstyle.md L272-276)=====


def test_decide_event_blood_economy_avoided() -> None:
    """T1 主红证锁:血本位卡当帧基线 argmax(奋斗协议 45 > 42/42),排除支移除
    → 它以 45 分入选、本锁即红——锁钉在回避规则本身。三态触发序 L1:可入选
    非血集非空 → 其 argmax,winner reason 附 '+blood-avoided'(观测锚)。"""
    from sr_od.application.currency_war.kernel.cw_investments import pick_value_of
    cfg = _cfg()
    st = GameState(board={}, hp=100)
    assert pick_value_of('奋斗协议') > pick_value_of('乱成一锅粥'), \
        'premise:血卡确为基线 argmax(45 > 42)'
    pick = decide_event(['奋斗协议', '乱成一锅粥', '着眼当下'], cfg, st)
    assert pick.option_idx in (1, 2), f'血本位卡不得入选,实得 {pick}'
    assert 'blood-avoided' in pick.reason, f'观测锚缺失,实得 {pick.reason}'


def test_decide_event_priority_cannot_rescue_blood() -> None:
    """T1b(F1 补声明面):strategy_priority +30 是分值族内软加分,血本位排除是
    集合级结构规则(ADR-0578)——血卡无论加多少分都进不了可入选非血分区,
    winner reason 不携带 user-priority 归因。"""
    cfg = _cfg(strategy_priority=['奋斗协议'])
    st = GameState(board={}, hp=100)
    pick = decide_event(['奋斗协议', '乱成一锅粥', '爆晶矿·金'], cfg, st)
    assert pick.option_idx != 0, 'priority 不得把血卡救回可入选分区'
    assert 'blood-avoided' in pick.reason and 'user-priority' not in pick.reason, \
        f'实得 {pick.reason}'


def test_decide_event_blood_forced_when_no_alternative() -> None:
    """T2 三态触发序 L2 兜底支(F4e 前提锁):可入选非血集空(唯一非血卡被禁)
    → 血卡间常规评估序 argmax、reason 显影 blood-forced;user-forbid「有替代
    永不选」的替代语义兑现——被禁非血卡让位于非禁血卡。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        get_strategy,
        is_blood_economy,
    )
    # 前提锁:两血卡确经谓词判血(兜底支语义才成立)
    assert is_blood_economy(get_strategy('奋斗协议').economy)
    assert is_blood_economy(get_strategy('不等价交换').economy)
    cfg = _cfg(strategy_forbid=['乱成一锅粥'])
    st = GameState(board={}, hp=100)
    pick = decide_event(['奋斗协议', '不等价交换', '乱成一锅粥'], cfg, st)
    assert pick.option_idx in (0, 1), f'被禁非血卡不得入选,实得 {pick}'
    assert 'blood-forced' in pick.reason, f'兜底支显影缺失,实得 {pick.reason}'


def test_is_blood_economy_family_lock() -> None:
    """T3 族边界锁(ADR-0578):当前族集 = {奋斗协议, 不等价交换},与 [40] 裁定
    原文点名完全一致。反向钉死两类陷阱:①名字陷阱——鲜血阶梯(75 分顶分卡)
    名带血实为战力卡(effect 无 HP 经济字段,economy=None);②补偿型字段——
    保险/星际和平保险的按损血给金不改支付币种,不入族。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_ECONOMY,
        EconomyEffect,
        get_strategy,
        is_blood_economy,
    )
    family = {n for n, e in STRATEGY_ECONOMY.items() if is_blood_economy(e)}
    assert family == {'奋斗协议', '不等价交换'}, f'族集漂移:{family}'
    assert get_strategy('鲜血阶梯') is not None
    assert get_strategy('鲜血阶梯').economy is None
    assert is_blood_economy(get_strategy('鲜血阶梯').economy) is False
    assert is_blood_economy(EconomyEffect(gold_per_20hp_lost=5)) is False
    assert is_blood_economy(EconomyEffect(gold_per_hp_lost_now=True)) is False
    assert is_blood_economy(None) is False


def test_decide_event_lcs_path_blood_resolved() -> None:
    """T5 帧①(F3 修复面):已评估血卡 × OCR 形变名——LCS 解析名经谓词判血 →
    排除,病灶帧(奋斗协议形变名 45 分入选)不复发;非血形变名裸分行为不变
    (eval-lcs 语义保持,解析单一源 = resolve_strategy_canonical)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        pick_value_of,
        resolve_strategy_canonical,
    )
    cfg = _cfg()
    st = GameState(board={}, hp=100)
    assert resolve_strategy_canonical('奋斗协讉') == '奋斗协议'
    assert pick_value_of('着眼当丅') == 42, '非血形变名 LCS 裸分前提'
    # 帧①:形变血卡(45)被排除,真卡着眼当下(42)入选;红证:无分类时形变名
    # 45 分 argmax 入选
    pick = decide_event(['奋斗协讉', '着眼当下'], cfg, st)
    assert pick.option_idx == 1, f'形变血卡不得入选,实得 {pick}'
    assert 'blood-avoided' in pick.reason
    # 非血形变名:eval-lcs 裸分行为零漂移(仍按解析分竞争并可选)
    pick2 = decide_event(['奋斗协议', '着眼当丅'], cfg, st)
    assert pick2.option_idx == 1 and 'eval-lcs' in pick2.reason


def test_decide_event_unevaluated_blood_candidate_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """T5 帧②(N2 候选级挂点):未评估血卡 × OCR 形变名——解析分类不依赖
    PICK_VALUE 命中(eval-lcs 分支对未评估卡不可达:分值支内挂点会漏,全弱帧
    0 分入选)。红证:无候选级分类时形变血卡 0 分 argmax 入选、本锁红。
    注入条目 teardown 自动恢复(monkeypatch.setitem)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        INVESTMENT_STRATEGIES,
        EconomyEffect,
        InvestmentStrategy,
        resolve_strategy_canonical,
    )
    monkeypatch.setitem(
        INVESTMENT_STRATEGIES, '血契协议',
        InvestmentStrategy(name='血契协议', rarity='棱彩',
                           effect='购买经验值消耗6点小队生命值而非金币(测试注入,未评估)',
                           economy=EconomyEffect(xp_buy_hp_cost=6)))
    assert resolve_strategy_canonical('血契协讉') == '血契协议'
    cfg = _cfg()
    st = GameState(board={}, hp=100)
    # 全弱帧:未评估血卡(形变名,0 分)vs 未注册名(0 分)——无分类时 idx0 入选
    pick = decide_event(['血契协讉', '银色无名'], cfg, st)
    assert pick.option_idx == 1, f'未评估血卡不得经形变名入选,实得 {pick}'
    assert 'blood-avoided' in pick.reason

