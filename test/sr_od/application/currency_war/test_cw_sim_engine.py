"""sim 重做 S9(主引擎 reset/step 步进协议 + 相位状态机)回归锁。

设计正本 = ``docs/develop/sr_od/application/currency_war/changes/
2026-09-15-sim-redesign/design.md`` §2.5;锁面 = reset 开局真值与
相位路由/环境屏门控/PREP 动作经单一转移函数/节点结算推进序(收入/
商店/offer 日程/选卡族/补给/遭遇/奖励球)/局终三通道(P2 走完/
p3_unobserved)/simulate_run 薄包装。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_vocab import (
    BuyCard,
    OpenBox,
    PickEvent,
    StartBattle,
)
from sr_od.application.currency_war.sim.cw_sim_engine import (
    DISCLOSURE_P3_UNOBSERVED,
    DISCLOSURE_SHOP_LOCK,
    CwSimEngine,
    RunResult,
    simulate_run,
)
from sr_od.application.currency_war.sim.cw_sim_phase import CwSimPhase
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

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
    assert frame.bs.hp.value == 82, 'A8/108 无词缀实证档'
    assert frame.bs.gold.value == 7, '开局 3 + P1r1 收入(3 基础+0 息+1 连胜档)'
    assert frame.bs.level.value == 3
    assert len(frame.bs.plane_bosses.value) == 3


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
    assert ret.observation.bs.active_env.value == frame.options[0]


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
    gold_before = frame.bs.gold.value
    shop_cards = [s.card for s in frame.bs.shop.value.cards
                  if s.kind == 'content']
    cheap = min(shop_cards, key=lambda c: c.cost)
    ret = eng.step(BuyCard(card=cheap))
    assert ret.outcome is not None and ret.outcome.applied
    assert ret.observation.bs.gold.value == gold_before - cheap.cost


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
    assert len(ret2.observation.bs.equips.value) == 1


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
    assert ret2.observation.bs.equips.value, '选中装备入账'


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
    assert len(ret.observation.bs.active_strategies.value) == 1


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
