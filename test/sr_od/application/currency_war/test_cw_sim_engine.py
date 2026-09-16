"""sim 重做 S9(主引擎 reset/step 步进协议 + 相位状态机)回归锁。

设计正本 = ``docs/develop/sr_od/application/currency_war/changes/
2026-09-15-sim-redesign/design.md`` §2.5;锁面 = reset 开局真值与
相位路由/环境屏门控/PREP 动作经单一转移函数/节点结算推进序(收入/
商店/offer 日程/选卡族/补给/遭遇/奖励球)/局终三通道(P2 走完/
p3_unobserved)/simulate_run 薄包装;r3 返工增锁 = M10 装备四路
PREP 分派接线 + U24 披露三键并表 + M21 planner 触发正典
(planner_overlay_due + 全域扫描 + SILVER_WOLF_ID)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_equipment_data import (
    EQUIPMENTS,
    get_equip,
)
from sr_od.application.currency_war.data.cw_synthesis import CROSS_RECIPES
from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopCard,
    ShopPayload,
    ShopSlot,
    Unit,
    bench_view_of_slots,
    register_sig_actors,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BuyCard,
    FurnaceUse,
    OpenBox,
    PickEvent,
    PrecisionWrenchUse,
    StartBattle,
    WearEquip,
    WrenchUse,
)
from sr_od.application.currency_war.sim.cw_sim_engine import (
    DISCLOSURE_P3_UNOBSERVED,
    DISCLOSURE_SHOP_LOCK,
    CwSimEngine,
    RunResult,
    simulate_run,
)
from sr_od.application.currency_war.sim.cw_sim_equips import (
    FURNACE_CHAR_MODE_PENDING,
    TOOL_EFFECTS_PENDING,
    UNMODELED_GRANTS,
)
from sr_od.application.currency_war.sim.cw_sim_phase import CwSimPhase
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig
from sr_od.application.currency_war.sim.cw_sim_special import SILVER_WOLF_ID

register_sig_actors('TestSigWriter')

_SIG = ChannelSig(family='obs', actor='TestSigWriter')

_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)


def _auto(frame):
    """全相位自适应桩策略(「无动作 = 选终结动作」 mandate 语义的
    测试桩形态;球面板 = 点第一个剩余球)。"""
    phase = frame.phase
    if phase is CwSimPhase.REWARD_BALL:
        return PickEvent(option_idx=0)
    if phase in (CwSimPhase.OPENING_ENV, CwSimPhase.INVEST_OFFER,
                 CwSimPhase.ENCOUNTER_OFFER, CwSimPhase.SUPPLY_PICK,
                 CwSimPhase.BOX_PICK, CwSimPhase.EVENT_OVERLAY):
        return PickEvent(option_idx=0)
    return StartBattle()


def _drive(engine: CwSimEngine, seed: int, cfg: RunConfig = _CFG,
           max_steps: int = 4000) -> RunResult:
    """reset + 桩策略驱动到局终(测试辅助;步数上限防写环)。"""
    frame = engine.reset(seed, cfg)
    for _ in range(max_steps):
        if frame.phase is CwSimPhase.GAME_OVER:
            break
        ret = engine.step(_auto(frame))
        if ret.result is not None:
            return ret.result
        frame = ret.observation
    raise AssertionError('未在步数上限内局终')


# ============================================================ reset 面

def test_reset_writes_opening_truth_and_enters_p1r1() -> None:
    """reset:M01 开局真值(Hp 实证档/金3/等级3)+ boss 名单 +
    env_present=False 直接进 P1r1 备战(含轮首收入:金 3→7)。"""
    eng = CwSimEngine()
    frame = eng.reset(7, _CFG)
    assert frame.phase is CwSimPhase.PREP
    assert (frame.node.plane, frame.node.round_num) == (1, 1)
    assert frame.node.kind == 'reward'
    assert frame.gs.hp.value == 82, 'A8/108 无词缀实证档'
    assert frame.gs.gold.value == 7, '开局 3 + P1r1 收入(3 基础+0 息+1 连胜档)'
    assert frame.gs.level.value == 3
    assert len(frame.gs.plane_bosses.value) == 3


def test_reset_env_present_opens_env_screen() -> None:
    """U07②/U08:env_present=True → 首相位 = OPENING_ENV(开局无策略
    选卡,该屏即环境屏);选 1 后 active_env 定局并进 P1r1。"""
    eng = CwSimEngine()
    frame = eng.reset(11, RunConfig(selected_difficulty='A8',
                                    enemy_difficulty=108, env_present=True))
    assert frame.phase is CwSimPhase.OPENING_ENV
    assert len(frame.options) == 3
    ret = eng.step(PickEvent(option_idx=0))
    assert ret.observation.phase is CwSimPhase.PREP
    assert ret.observation.gs.active_env.value == frame.options[0]


def test_reset_rejects_non_standard_mode_u27() -> None:
    """U27:非标准博弈显式拒(不猜差异)。"""
    with pytest.raises(ValueError, match='首版辖域'):
        CwSimEngine().reset(1, RunConfig(selected_difficulty='A8',
                                         enemy_difficulty=108,
                                         game_mode='超频博弈'))


# ============================================================ PREP 面

def test_prep_actions_via_single_transfer_function() -> None:
    """PREP:动作经 kernel 单一转移函数(买牌金账);engine 不自判拒绝。"""
    eng = CwSimEngine()
    frame = eng.reset(7, _CFG)
    gold_before = frame.gs.gold.value
    shop_cards = [s.card for s in frame.gs.shop.value.cards
                  if s.kind == 'content']
    cheap = min(shop_cards, key=lambda c: c.cost)
    ret = eng.step(BuyCard(card=cheap))
    assert ret.outcome is not None and ret.outcome.applied
    assert ret.observation.gs.gold.value == gold_before - cheap.cost


def test_shop_lock_disclosure_present() -> None:
    """裁定②:整店锁 = 引擎自有状态 + 披露(锁语义在册,动作通道缺)。"""
    eng = CwSimEngine()
    frame = eng.reset(7, _CFG)
    assert DISCLOSURE_SHOP_LOCK in frame.disclosures


def test_open_box_leads_to_box_pick() -> None:
    """OpenBox → BOX_PICK(4 选 1 占位)→ 选装入账 → 回 PREP。"""
    eng = CwSimEngine()
    eng.reset(7, _CFG)
    ret = eng.step(OpenBox())
    assert ret.observation.phase is CwSimPhase.BOX_PICK
    assert len(ret.observation.box_options) == 4
    ret2 = eng.step(PickEvent(option_idx=0))
    assert ret2.observation.phase is CwSimPhase.PREP
    assert len(ret2.observation.gs.equips.value) == 1


# ================================================== M10 四路接线(r3)

def _advance_pair() -> tuple[str, str, str]:
    """取一对真配方(组件A, 组件B, 进阶产物)(注册表单一源取用)。"""
    advance, (a, b) = next(iter(CROSS_RECIPES.items()))
    return a, b, advance


def test_disclosure_three_keys_merged_into_result() -> None:
    """U24/M10 披露三键并表(unmodeled_grants/tool_effects/furnace_char)
    进观测帧与局结果披露集——「发放空表随局披露」名实相符。"""
    frame = CwSimEngine().reset(7, _CFG)
    assert {UNMODELED_GRANTS, TOOL_EFFECTS_PENDING,
            FURNACE_CHAR_MODE_PENDING} <= set(frame.disclosures)
    result = _drive(CwSimEngine(), 61)
    assert {UNMODELED_GRANTS, TOOL_EFFECTS_PENDING,
            FURNACE_CHAR_MODE_PENDING} <= set(result.unmodeled)


def test_prep_wear_equip_routes_to_sim_leg() -> None:
    """M10 接线:PREP 的 WearEquip 经 cw_sim_equips 腿(穿着即合成),
    不再落 kernel 商店转移口 unsupported_action_type 零写拒;owned 无
    该件 = 腿拒回声(applied=False)。"""
    a, b, advance = _advance_pair()
    eng = CwSimEngine()
    gs = eng.reset(7, _CFG).gs
    slots: list[BenchChar | None] = [None] * 9
    slots[0] = BenchChar(slot=1, char_id='淘金客', faction='散', star=1,
                         equips=[a])
    gs.observe(gs.bench, bench_view_of_slots(slots), sig=_SIG)
    gs.observe(gs.equips, [b], sig=_SIG)
    ret = eng.step(WearEquip(item_name=b, char_name='淘金客',
                             row='front', slot=1))
    assert ret.outcome is not None and ret.outcome.applied, '腿生效(旧=零写拒)'
    worn = [list(s.unit.equips) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]
    assert worn == [[advance]], f'穿着即合成:{a}+{b} → {advance}'
    assert gs.equips.value == [], '库存件已穿上'
    ret_rej = eng.step(WearEquip(item_name='不在库的装备', char_name='淘金客',
                                 row='front', slot=1))
    assert not ret_rej.outcome.applied and ret_rej.outcome.reason


def test_prep_wrench_routes_unequip_and_consume() -> None:
    """M10 接线:扳手 = 取下回区 + 工具消耗;精密扳手 = 同取下不消耗。"""
    a, _b, _adv = _advance_pair()
    eng = CwSimEngine()
    gs = eng.reset(7, _CFG).gs
    gs.observe(gs.front_row,
               [Unit(char_id='淘金客', star=1, equips=[a])], sig=_SIG)
    gs.observe(gs.equips, ['拆装扳手', '精密拆装扳手'], sig=_SIG)
    ret = eng.step(WrenchUse(row='front', slot=1))
    assert ret.outcome is not None and ret.outcome.applied
    assert gs.front_row.value[0].equips == [], '穿戴回区'
    assert gs.equips.value == ['精密拆装扳手', a], '扳手消耗 + 装备入库'
    ret2 = eng.step(PrecisionWrenchUse(row='front', slot=1))
    assert ret2.outcome is not None and ret2.outcome.applied
    assert '精密拆装扳手' in gs.equips.value, '精密扳手不消耗'


def test_prep_furnace_routes_by_target_kind() -> None:
    """冶金炉双模式接线:equip 模式 = 同类型重掷生效(M10/炉 流引擎
    装配);char 模式首版不建模 = 显式拒 + 披露键在册。"""
    simple = sorted(n for n, e in EQUIPMENTS.items()
                    if e.category == '简易')
    src = simple[0]
    eng = CwSimEngine()
    gs = eng.reset(7, _CFG).gs
    gs.observe(gs.equips, [src], sig=_SIG)
    ret = eng.step(FurnaceUse(target_kind='equip', item_name=src))
    assert ret.outcome is not None and ret.outcome.applied
    new_name = gs.equips.value[0]
    assert new_name != src and get_equip(new_name).category == '简易', \
        '同类型(同 category)重掷'
    ret2 = eng.step(FurnaceUse(target_kind='char', row='front', slot=1))
    assert ret2.outcome is not None and not ret2.outcome.applied, \
        '拖角色模式未建模显式拒'
    assert gs.equips.value == [new_name], '拒 = 零写'
    assert FURNACE_CHAR_MODE_PENDING in ret2.observation.disclosures


def test_planner_trigger_fires_on_deployed_merge() -> None:
    """M21 触发正典:判据 = planner_overlay_due(动作前后全域银狼最高
    星级快照);kernel 合成产物落点 = 场上同名位(M07)→ 产物落部署位
    也必触发(旧「仅扫备战席 star≥2」近似在此漏触发);银狼身份单一源
    = SILVER_WOLF_ID。overlay 呈现于下一结算收尾(M22 队列序)。"""
    eng = CwSimEngine()
    gs = eng.reset(7, _CFG).gs
    slots: list[BenchChar | None] = [None] * 9
    slots[0] = BenchChar(slot=1, char_id=SILVER_WOLF_ID, faction='?',
                         star=1)
    gs.observe(gs.bench, bench_view_of_slots(slots), sig=_SIG)
    gs.observe(gs.front_row, [Unit(char_id=SILVER_WOLF_ID, star=1)],
               sig=_SIG)
    card = ShopCard(name=SILVER_WOLF_ID, cost=3, star=1)
    gs.observe(gs.shop, ShopPayload(
        cards=[ShopSlot(kind='content', card=card)]), sig=_SIG)
    ret = eng.step(BuyCard(card=card))
    assert ret.outcome is not None and ret.outcome.applied
    assert gs.front_row.value[0].star == 2, '合成产物落场上同名位(M07)'
    assert all(not (s is not None and s.kind == 'unit'
                    and s.unit is not None
                    and s.unit.char_id == SILVER_WOLF_ID)
               for s in gs.bench.value.slots), '备战席已无银狼(旧判据必漏)'
    frame = ret.observation
    for _ in range(64):
        if frame.phase is CwSimPhase.EVENT_OVERLAY:
            break
        ret2 = eng.step(_auto(frame))
        assert ret2.result is None, '该Setup 不应局终'
        frame = ret2.observation
    assert frame.phase is CwSimPhase.EVENT_OVERLAY
    assert frame.overlay_kind == 'planner', '部署位合成 2★ 银狼必触发'


# ============================================================ 结算推进

def test_reward_win_leads_to_ball_phase_and_settlement() -> None:
    """奖励节点胜 → REWARD_BALL(U23 单例锚 8 球)→ 逐球点完 →
    推进下一节点;败 → 直接推进。流键定 seed,双分支都锁。"""
    for seed in (7, 21):
        eng = CwSimEngine()
        eng.reset(seed, _CFG)
        ret = eng.step(StartBattle())
        phase_after = ret.observation.phase
        node_after = ret.observation.node
        if phase_after is CwSimPhase.REWARD_BALL:
            assert len(ret.observation.balls) == 8, 'U23 单例锚'
            ret2 = eng.step(PickEvent(option_idx=0))
            assert len(ret2.observation.balls) == 7, '逐球收缩'
        else:
            assert phase_after is CwSimPhase.PREP
            assert (node_after.plane, node_after.round_num) == (1, 2)


def test_supply_node_picks_equipment() -> None:
    """P1r5 补给:StartBattle → SUPPLY_PICK(3 选 1)→ 选装入账。"""
    eng = CwSimEngine()
    frame = eng.reset(1013, _CFG)
    # 驱动到 P1r5(supply)
    for _ in range(64):
        if (frame.node.plane, frame.node.round_num, frame.node.kind) \
                == (1, 5, 'supply') and frame.phase is CwSimPhase.PREP:
            break
        ret = eng.step(_auto(frame))
        frame = ret.observation
    ret = eng.step(StartBattle())
    assert ret.observation.phase is CwSimPhase.SUPPLY_PICK
    assert len(ret.observation.supply_options) == 3
    ret2 = eng.step(PickEvent(option_idx=0))
    assert ret2.observation.gs.equips.value, '选中装备入账'


def test_invest_offer_fires_at_p1r3_u07() -> None:
    """U07:打完 1-2 → P1r3 备战窗口前呈现 INVEST_OFFER;选卡入
    active_strategies(全程去重集累计)。"""
    eng = CwSimEngine()
    frame = eng.reset(1013, _CFG)
    seen_offer = False
    for _ in range(64):
        if frame.phase is CwSimPhase.INVEST_OFFER:
            seen_offer = True
            assert (frame.node.plane, frame.node.round_num) == (1, 3)
            break
        ret = eng.step(_auto(frame))
        frame = ret.observation
    assert seen_offer, 'P1r3 前应呈现策略 offer'
    ret = eng.step(PickEvent(option_idx=0))
    assert ret.observation.phase is CwSimPhase.PREP
    assert len(ret.observation.gs.active_strategies.value) == 1


def test_encounter_pick_then_settle() -> None:
    """P1r7 遭遇:StartBattle → ENCOUNTER_OFFER(4 档)→ 选档结算
    (U01 随机输出面:难度档不消费,局终/推进双分支皆合法;chosen
    写入面由 S7 单测锁)。"""
    eng = CwSimEngine()
    frame = eng.reset(1013, _CFG)
    for _ in range(64):
        if (frame.node.kind == 'encounter'
                and frame.phase is CwSimPhase.PREP):
            break
        ret = eng.step(_auto(frame))
        frame = ret.observation
    assert (frame.node.plane, frame.node.round_num) == (1, 7)
    ret = eng.step(StartBattle())
    assert ret.observation.phase is CwSimPhase.ENCOUNTER_OFFER
    assert len(ret.observation.encounter_options) == 4
    ret2 = eng.step(PickEvent(option_idx=1))
    if ret2.observation is not None:
        assert ret2.observation.phase is CwSimPhase.PREP, 'P1r8 备战'
    else:
        assert ret2.result is not None, '败死局终(随机输出面合法分支)'


# ============================================================ 局终

def test_full_run_terminates_with_p2_completion() -> None:
    """第一期限 P1+P2:P2 boss 结算完成 → 走完终局(下一步即未观测
    P3 → 披露 p3_unobserved);hp_trail 全程非负;败死终局(M14 dead
    通道)同为合法形态(seed 61 = 走完通道锚)。"""
    result = _drive(CwSimEngine(), 61)
    assert result.plane_reached == 2
    assert result.final_hp >= 0
    assert all(hp >= 0 for hp in result.hp_trail)
    assert DISCLOSURE_P3_UNOBSERVED in result.unmodeled
    assert len(result.hp_trail) >= 8, 'hp 轨迹覆盖两位面'


def test_death_channel_terminates_mid_run() -> None:
    """M14 dead 通道:再次归零 → 局终(中途 plane;无 p3 披露)——
    随机输出面下的合法终局形态(seed 1 = P2 boss 败死锚)。"""
    result = _drive(CwSimEngine(), 1)
    assert result.final_hp == 0
    assert 1 <= result.plane_reached <= 2
    assert DISCLOSURE_P3_UNOBSERVED not in result.unmodeled


def test_simulate_run_wrapper_same_result() -> None:
    """候选 A 薄包装:同一 seed 同一桩策略,结果与手工驱动一致
    (包装 = B 之上的纯语法糖,零状态面)。"""
    r1 = simulate_run(61, _CFG, _auto)
    r2 = _drive(CwSimEngine(), 61)
    assert r1 == r2
    assert isinstance(r1, RunResult)


def test_step_after_game_over_rejected() -> None:
    """局终后 step = RuntimeError(防幻局)。"""
    eng = CwSimEngine()
    _drive(eng, 61)
    with pytest.raises(RuntimeError, match='局已结束'):
        eng.step(StartBattle())
