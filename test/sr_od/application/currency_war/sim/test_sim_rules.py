"""sim 数值规则件回归测试(战斗结算 M12/M13/M14 / 敌人难度与名单
M19/M20/M21 / 轮首收入与连胜经济 M04/M15)。

测试面(全部 = 无状态规则函数,入参驱动、不经后端状态机):
- 战斗结算:U01 随机输出面(胜负 P=0.5 均匀伯努利/扣血均匀区间
  [23,70]/流键可复现)/U03 分项置 None/简化档标记/M14 结构规则(败才
  扣血/首次 0hp 保底剩 1/再次归零局终);
- 敌人:U25 难度定谳成分与基础 None 披露(品质彩 6/遭遇档 20/伟大征服
  连胜项;难度修改器节点型限定)/U02 boss 池采样与覆盖优先/U26 开拓者
  形态路由;
- 经济:U04 败轮金(被败节点基础奖励 + 利息,平面感知取键)/U05 补给轮
  照发/U06 无事件金/三分支单一源值分解/连胜双账转移/持卡收入修饰聚合链。

模块归宿 = sim/cw_sim_battle + cw_sim_enemy + cw_sim_special +
cw_sim_backend 规则件 + kernel/cw_economy(驱动反转迭代平移保留)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_economy import (
    LostNodeRef,
    round_start_income,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    IncomeApplied,
    apply_round_start_income,
    income_modifiers_of,
    streak_income_after,
    streak_signed_after,
)
from sr_od.application.currency_war.sim.cw_sim_battle import (
    SIM_BATTLE_FACE,
    SIM_HP_LOSS_MAX,
    SIM_HP_LOSS_MIN,
    SIM_WIN_PROB,
    apply_hp_outcome,
    settle_battle,
)
from sr_od.application.currency_war.sim.cw_sim_enemy import (
    BOSS_DEDUP_PENDING,
    DIFFICULTY_BASE_PENDING_U25,
    HOLY_GRAIL_BONUS,
    difficulty_of,
    resolve_plane_bosses,
)
from sr_od.application.currency_war.sim.cw_sim_special import (
    trailblazer_form_of,
)
from sr_od.application.currency_war.sim.cw_sim_streams import stream_rng

_OBS_SIG = ChannelSig(family='obs', actor='TestSigWriter')


def _hp_gs(hp: int | None = None) -> GameState:
    """空容器(可选 hp 观察写;战斗结算 HP 折算消费面用)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if hp is not None:
        gs.observe(gs.hp, hp, sig=_OBS_SIG)
    return gs


def _income_gs(gold: int, strategies: list[str] | None = None) -> GameState:
    """收入面容器(gold 必写;持卡策略按名观察)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, gold, sig=_OBS_SIG)
    if strategies:
        gs.observe(gs.active_strategies, list(strategies), sig=_OBS_SIG)
    return gs


# ============================================================ 战斗结算(M12/M13/M14)

class BattleLike:
    """apply_hp_outcome 入参最小桩(只辖 HP 折算消费面)。"""

    def __init__(self, won: bool, hp_delta: int) -> None:
        self.won = won
        self.hp_delta = hp_delta
        self.face = SIM_BATTLE_FACE
        self.progress = 0.0
        self.base_damage = None
        self.progress_damage = None


def test_battle_face_domain_over_seeds() -> None:
    """U01 输出域:胜 → hp_delta 0/进度达标;败 → 总扣血 ∈ [23,70]/
    进度均匀采样;分项恒 None(U03 直扣不拆);输出面带简化档标记。"""
    wins = 0
    rounds = 400
    for seed in range(rounds):
        out = settle_battle(stream_rng(seed, 'M13/p1/r7'),
                            plane=1, round_num=7)
        assert out.face == SIM_BATTLE_FACE
        assert out.base_damage is None and out.progress_damage is None, \
            'U03:分项第一期不拆,置 None 占位'
        if out.won:
            wins += 1
            assert out.hp_delta == 0 and out.progress == 1.0
        else:
            assert SIM_HP_LOSS_MIN <= -out.hp_delta <= SIM_HP_LOSS_MAX
            assert 0.0 <= out.progress < 1.0
    ratio = wins / rounds
    assert 0.42 <= ratio <= 0.58, \
        f'胜率 {ratio:.3f} 偏离 U01 定案 P=0.5(宽带 ±6σ)'


def test_battle_stream_reproducible() -> None:
    """§2.0.4:同 (seed, 流键) 结算逐位可复现(胜负+扣血+进度)。"""
    a = settle_battle(stream_rng(9, 'M13/p2/r3'), plane=2, round_num=3)
    b = settle_battle(stream_rng(9, 'M13/p2/r3'), plane=2, round_num=3)
    assert a == b


def test_hp_outcome_loss_and_win_paths() -> None:
    """M14:胜不扣血;败扣 hp(总扣血直扣,分项不拆)。"""
    gs = _hp_gs(82)
    floor_now, dead = apply_hp_outcome(gs, BattleLike(won=True, hp_delta=0))
    assert floor_now is False and dead is False
    assert int(gs.hp.value or 0) == 82, '胜利不掉血(多局确认口径)'
    bs2 = _hp_gs(82)
    loss_hp = 30
    floor_now, dead = apply_hp_outcome(bs2, BattleLike(won=False,
                                                       hp_delta=-loss_hp))
    assert (floor_now, dead) == (False, False)
    assert int(bs2.hp.value or 0) == 82 - loss_hp


def test_hp_floor_guarantee_once_then_game_over() -> None:
    """M14:首次归零保底剩 1(容器保底位翻真);再次归零 → 局终。"""
    gs = _hp_gs(40)
    first = BattleLike(won=False, hp_delta=-40)
    floor_now, dead = apply_hp_outcome(gs, first)
    assert (floor_now, dead) == (True, False)
    assert int(gs.hp.value or 0) == 1
    assert gs.hp_floor_triggered.value is True, '保底事件位翻真(已消费)'
    second = BattleLike(won=False, hp_delta=-23)
    floor_now2, dead2 = apply_hp_outcome(gs, second)
    assert (floor_now2, dead2) == (False, True), '再次归零 = 整局结束'
    assert int(gs.hp.value or 0) == 0


def test_win_prob_constant_is_ruling_value() -> None:
    """U01 定案常量钉死:P=0.5 / 区间 [23,70](锚定规则改常量须经
    新实测样本并入,常量漂移 = 设计裁决漂移)。"""
    assert SIM_WIN_PROB == 0.5
    assert (SIM_HP_LOSS_MIN, SIM_HP_LOSS_MAX) == (23, 70)


# ============================================================ 敌人难度与名单(M19/M20/M21)

def test_difficulty_known_components_and_base_none_u25() -> None:
    """U25:定谳成分(品质彩6/遭遇档20/伟大征服连胜项)逐项可算;
    基础曲线未采 → base=None 且 total=None(禁插值不出合计)。"""
    d = difficulty_of(['伟大征服'], node_kind='encounter', streak=2,
                      encounter_tier=3, base=None)
    assert d.base is None and d.total is None
    assert d.quality_bonus == 6, '伟大征服 = 棱彩档 +6(注册表 rarity)'
    assert d.encounter_tier_bonus == 20, '第三档 = 20'
    assert d.special_bonus == 2, 'difficulty_per_streak=1 × streak=2'
    assert d.strategy_delta == 0
    assert DIFFICULTY_BASE_PENDING_U25


def test_difficulty_total_with_base_and_node_scoped_delta() -> None:
    """base 可传(局级输入档):total = base + 定谳成分;难度修改器
    (−4,遭遇+首领限定)只在遭遇/首领节点计入。"""
    d_battle = difficulty_of(['难度修改器'], node_kind='battle',
                             streak=0, base=100)
    assert d_battle.strategy_delta == 0, '战斗节点不计节点型限定 Δ'
    assert d_battle.total == 100
    d_enc = difficulty_of(['难度修改器'], node_kind='encounter',
                          streak=0, base=100)
    assert d_enc.strategy_delta == -4 and d_enc.total == 96
    d_simple = difficulty_of(['简单模式'], node_kind='battle',
                             streak=0, base=100)
    assert d_simple.strategy_delta == -3, '无限定 Δ 恒计入'


def test_difficulty_holy_grail_constant_pending() -> None:
    """圣杯 +30 定谳真值在册;激活态占位(首版恒未激活)。"""
    d_off = difficulty_of([], node_kind='battle', streak=0, base=50)
    assert d_off.special_bonus == 0
    d_on = difficulty_of([], node_kind='battle', streak=0, base=50,
                         holy_grail_active=True)
    assert d_on.special_bonus == HOLY_GRAIL_BONUS == 30


def test_plane_boss_override_priority_and_pool_membership() -> None:
    """U02:RunConfig 覆盖位优先;None 位 → 内置池采样(池 = boss 机制
    注册表键集)。"""
    from sr_od.application.currency_war.data.cw_enemy_data import (
        BOSS_MECHANICS,
    )
    picked = resolve_plane_bosses(
        ('造梦兄弟影业', None, '灰手生命科技'), random.Random(1))
    assert picked[0] == '造梦兄弟影业' and picked[2] == '灰手生命科技'
    assert picked[1] in BOSS_MECHANICS
    full_sampled = resolve_plane_bosses(None, random.Random(2))
    assert all(b in BOSS_MECHANICS for b in full_sampled)
    assert BOSS_DEDUP_PENDING  # 去重语义占位披露键在册


# (planner 升星判据助手测试已随旧评估器退役删除:判据单一源 = 值回调
#  [S3],每费用档簿记校验在本仓 operations/test_overlay.py。)

def test_trailblazer_form_routing() -> None:
    """开拓者双形态按排路由(front=记忆/back=欢愉);非开拓者原样。"""
    assert trailblazer_form_of('开拓者', 'front') == '开拓者·记忆'
    assert trailblazer_form_of('开拓者', 'back') == '开拓者·欢愉'
    assert trailblazer_form_of('淘金客', 'front') == '淘金客'


# ============================================================ 轮首收入与连胜经济(M04/M15)

def test_supply_branch_pays_base_plus_interest_u05() -> None:
    """U05:补给轮照发基础奖励 + 利息,连胜分量恒 0(连胜计数不动是
    转移面的事,收入分支不发)。"""
    applied = apply_round_start_income(_income_gs(25), plane=1, round_num=5,
                                       node_type='supply', streak=3)
    assert applied.row.branch == 'supply'
    assert applied.row.base == 5 and applied.row.interest == 2
    assert applied.row.streak == 0 and applied.row.total == 7
    assert applied.gold_after == 32


def test_reward_branch_streak_paid_including_zero_counter() -> None:
    """奖励轮连胜照发(含 counter0=表首档 1,「连胜×0 仍发 1」85/85
    实证口径,M15);基础奖励平面感知键。"""
    hot = apply_round_start_income(_income_gs(25), plane=1, round_num=5,
                                   node_type='reward', streak=2)
    assert hot.row.streak == 2, 'streak_gold(2)=2'
    cold = apply_round_start_income(_income_gs(25), plane=1, round_num=5,
                                    node_type='reward', streak=0)
    assert cold.row.streak == 1, 'counter0 照发表首档'


def test_reward_branch_lost_round_drops_streak_component() -> None:
    """统一公式败局形(lost_round):奖励轮战败无连胜成分——基础+息照发,
    分支仍 reward(扑满败局消费面,2026-10-10 用户裁定);胜局形不变。
    (kernel 单一源直测;sim 包装不透传该参数,递延落账走 kernel 直调。)"""
    lost = round_start_income(1, 5, 'reward', 25, 3, lost_round=True)
    assert lost.branch == 'reward'
    assert lost.base == 5 and lost.interest == 2
    assert lost.streak == 0, '败局形:连胜成分 = 0(战败无)'
    assert lost.total == 7
    won = round_start_income(1, 5, 'reward', 25, 3)
    assert won.streak == 2, '胜局形不受参数影响(streak_gold(3)=2)'


def test_combat_branch_win_income() -> None:
    """常规战斗胜轮 = 基础 + 息 + 连胜×倍率(缺省倍率 1)。"""
    applied = apply_round_start_income(_income_gs(30), plane=1, round_num=6,
                                       node_type='battle', streak=4)
    assert applied.row.branch == 'combat'
    assert applied.row.base == 5 and applied.row.interest == 3
    assert applied.row.streak == 2, 'streak_gold(4)=2'
    assert applied.row.total == 10


def test_no_event_gold_component_u06() -> None:
    """U06:total 恒等于三分量之和,无第四随机分量(全分支)。"""
    for node_type in ('supply', 'reward', 'battle'):
        applied: IncomeApplied = apply_round_start_income(
            _income_gs(47), plane=1, round_num=4, node_type=node_type,
            streak=1)
        assert applied.row.total == (applied.row.base + applied.row.interest
                                     + applied.row.streak)


def test_loss_comp_pays_lost_node_base_u04() -> None:
    """U04:败补 = 被败节点基础奖励(平面感知键)+ 利息,连胜分量强制
    0;类型表(LOSS_GOLD_BY_NODE)路径不在收入面。"""
    applied = apply_round_start_income(
        _income_gs(25), plane=1, round_num=3, node_type='battle', streak=2,
        pending_loss=LostNodeRef(plane=1, round_num=1, node_type='reward'))
    assert applied.row.branch == 'loss_comp'
    assert applied.row.base == 3, '被败节点 = P1r1 → 基础奖励键 3(非当前轮 5)'
    assert applied.row.streak == 0, '败补支连胜分量恒 0'
    assert applied.row.total == 3 + 2


def test_loss_pending_retained_on_supply_reward_rounds() -> None:
    """败态归宿:supply/reward 轮分支优先(收入 = 该轮自身查表),败态
    不传入 kernel(保留待下一战斗轮消费,模块 docstring 契约)。"""
    applied = apply_round_start_income(
        _income_gs(25), plane=1, round_num=5, node_type='supply', streak=2,
        pending_loss=LostNodeRef(plane=1, round_num=4, node_type='battle'))
    assert applied.row.branch == 'supply', '分支优先级:supply 先于败补'
    assert applied.row.base == 5, '基础奖励 = 当前节点键(非被败节点)'


def test_streak_transfers_combat_only() -> None:
    """战斗类胜 +1/败归零(带符号取负向计数);奖励/补给轮两账都不动;
    扑满帧例外 = 胜 +1/败清零(2026-10-10 用户裁定,败清零非负账)。"""
    assert streak_income_after(3, node_type='battle', won=True) == 4
    assert streak_income_after(3, node_type='battle', won=False) == 0
    assert streak_income_after(3, node_type='reward', won=True) == 3
    assert streak_income_after(3, node_type='supply', won=False) == 3
    assert streak_signed_after(3, node_type='battle', won=True) == 4
    assert streak_signed_after(3, node_type='battle', won=False) == -1
    assert streak_signed_after(-2, node_type='battle', won=False) == -3
    assert streak_signed_after(-2, node_type='reward', won=False) == -2
    assert streak_signed_after(0, node_type='encounter', won=False) == -1
    assert streak_signed_after(3, node_type='reward', won=True,
                               piggy=True) == 4
    assert streak_signed_after(-2, node_type='reward', won=True,
                               piggy=True) == 1, '胜向与战斗类同式'
    assert streak_signed_after(3, node_type='reward', won=False,
                               piggy=True) == 0
    assert streak_signed_after(3, node_type='battle', won=False,
                               piggy=False) == -1, '非扑满照旧负账'


def test_income_modifiers_from_strategies() -> None:
    """聚合链平移:息帽覆写取宽(利息上调 10)/连胜倍率取最大不叠乘
    (伟大征服 3.0)/每节点固定息求和。"""
    mult, flat, cap = income_modifiers_of(_income_gs(0, strategies=['利息上调']))
    assert (mult, flat, cap) == (1.0, 0, 10)
    mult, flat, cap = income_modifiers_of(_income_gs(0, strategies=['伟大征服']))
    assert mult == 3.0 and cap is None
    mult, flat, cap = income_modifiers_of(_income_gs(0, strategies=['狸财经狸']))
    assert flat == 2, '狸财经狸每节点固定息(+2)入 flat 分量'


def test_cap_override_changes_interest_math() -> None:
    """息帽覆写落账:持「利息上调」时 100 金息 = 10(缺省帽 5 档下
    封顶 5),经同一 round_start_income 分支。"""
    applied = apply_round_start_income(_income_gs(100, strategies=['利息上调']),
                                       plane=1, round_num=5,
                                       node_type='supply', streak=0)
    assert applied.row.interest == 10
