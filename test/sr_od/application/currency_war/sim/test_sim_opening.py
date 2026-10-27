"""sim 开局与日程(M01/M03)回归测试(基座/RunConfig/流键/日程真值)。

测试面(设计已裁定的表现):U28 开局四要素/U15 HP 实证档硬表/
流键子流隔离/§2.2 M03 地面真值序列(P1+P2+P3 全在表)。相位词表随旧引擎
相位机退役(替代面 = 画面状态机,测试面 = test_sim_backend.py)。
"""
from __future__ import annotations

import dataclasses

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    P1_NODE_SEQUENCE,
    P2_NODE_SEQUENCE,
    P3_NODE_SEQUENCE,
    PlaneSeqMissingError,
    node_sequence_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.sim.cw_sim_opening import (
    OPENING_DEPLOY_CAP,
    OPENING_GOLD,
    OPENING_LEVEL,
    OpeningHpUnsampledError,
    apply_opening,
    opening_bench_chars,
    opening_hp_or_raise,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig
from sr_od.application.currency_war.sim.cw_sim_streams import stream_rng


def _cfg(**kw) -> RunConfig:
    """最小合法配置(A8/108 实证档;词缀/开关按用例覆写)。"""
    base: dict = {'selected_difficulty': 'A8', 'enemy_difficulty': 108}
    base.update(kw)
    return RunConfig(**base)


# ============================================================ RunConfig(M01 正典字段)

def test_run_config_env_present_defaults_to_no_env_branch() -> None:
    """U07④:环境在场 = 显式必填字段,缺省 False = 无环境支路;
    配置为局级输入(冻结值对象,禁运行中改写)。"""
    cfg = _cfg()
    assert cfg.env_present is False
    assert cfg.boss_roster_override is None, '缺省 = 用 sim 内置 boss 表(U02)'
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.env_present = True   # type: ignore[misc]


# ============================================================ 流键子流(§2.0.4)

def test_stream_rng_deterministic_and_key_isolated() -> None:
    """同 (seed, 流键) 同序列;流键互不扰动(甲流先消耗,乙流逐位不变
    ——旧单 rng 消耗序耦合病灶的结构性消除);seed 变则流变。"""
    a1 = stream_rng(7, 'M05/p1/r3')
    a2 = stream_rng(7, 'M05/p1/r3')
    assert [a1.random() for _ in range(5)] == [a2.random() for _ in range(5)]
    b = stream_rng(7, 'M13/p1/r7')
    expect = [b.random() for _ in range(5)]
    _ = [a1.random() for _ in range(50)]   # 甲流狂耗,不得扰动乙流
    b2 = stream_rng(7, 'M13/p1/r7')
    assert [b2.random() for _ in range(5)] == expect
    c1 = stream_rng(8, 'M05/p1/r3')
    c2 = stream_rng(7, 'M05/p1/r3')
    assert [c1.random() for _ in range(8)] != [c2.random() for _ in range(8)], \
        'seed 变则同键流变(可复现承诺 = seed+开局参数+注册表指纹)'


# ============================================================ 日程真值(M03/U19)

def test_plane_truth_sequences_three_planes() -> None:
    """P1=9/P2=7/P3=7 地面真值序列逐位钉死(P1 42 局零反例;P3 =
    2026-10-15 用户裁定入码,证据等级低于 P1/P2,单一源 =
    plane_schedule_observed.md);表外位面直查响亮(缺键防御)。"""
    assert P1_NODE_SEQUENCE == ('reward', 'reward', 'battle', 'battle',
                                'supply', 'battle', 'encounter', 'reward',
                                'boss')
    assert P2_NODE_SEQUENCE == ('battle', 'battle', 'supply', 'battle',
                                'encounter', 'reward', 'boss')
    assert P3_NODE_SEQUENCE == ('battle', 'battle', 'supply', 'battle',
                                'encounter', 'reward', 'boss')
    assert node_sequence_of(1) == P1_NODE_SEQUENCE
    assert node_sequence_of(2) == P2_NODE_SEQUENCE
    assert node_sequence_of(3) == P3_NODE_SEQUENCE
    with pytest.raises(PlaneSeqMissingError, match='不在节点序列表'):
        node_sequence_of(4)


# ============================================================ M01 开局

def test_opening_hp_empirical_tiers_only() -> None:
    """U15:实证档硬表(A8/108 → 82;「开局不利」恒 −20 → 62,单一
    承载方 = cw_opening_hp);非实证档报错索样本,禁外推。"""
    assert opening_hp_or_raise(_cfg()) == 82
    assert opening_hp_or_raise(_cfg(enemy_affixes=('开局不利',))) == 62
    with pytest.raises(OpeningHpUnsampledError, match='索样本'):
        opening_hp_or_raise(_cfg(selected_difficulty='A7'))
    with pytest.raises(OpeningHpUnsampledError, match='索样本'):
        opening_hp_or_raise(_cfg(enemy_difficulty=120))


def test_opening_hand_u28_domain_over_seeds() -> None:
    """U28 四要素逐局核:4 张全 1★、形状 ∈ {(1,1,1,3),(1,1,2,2)}、
    卡名属注册表同费档;2:1 形状比在宽置信带内(±9σ,禁卡边)。"""
    shape_a = 0
    rounds = 400
    for seed in range(rounds):
        chars = opening_bench_chars(stream_rng(seed, 'M01/opening_hand'))
        assert len(chars) == 4
        assert all(c.unit.star == 1 for c in chars)
        costs = sorted(CHARACTERS[c.unit.char_id].cost for c in chars)
        assert costs in ([1, 1, 1, 3], [1, 1, 2, 2]), \
            f'seed={seed} 形状 {costs} 出局(U28 双形状域外)'
        if costs == [1, 1, 1, 3]:
            shape_a += 1
    ratio = shape_a / rounds
    assert 0.55 <= ratio <= 0.78, \
        f'形状比 {ratio:.3f} 偏离 U28 定案 2:1(宽带 ±9σ)'


def test_opening_hand_fixed_deck_pool_no_experts() -> None:
    """开局手牌固定牌库口径(economy.md §8 用户裁定 2026-10-28「授予/
    发放候选 = 当时牌库里存在的角色」):多 seed 全量核 4 张卡名均 ∉
    EXPERT_CHARS——抽名源 = fixed_pool 成员(同函数 docstring「M06 固定
    牌库该费档名集」既有申报的代码归位,消 chars_by_cost 含专家的代码-
    文档相悖);成员断言走注册表现算不手抄。"""
    from sr_od.application.currency_war.data.cw_chars import EXPERT_CHARS
    for seed in range(120):
        chars = opening_bench_chars(stream_rng(seed, 'M01/opening_hand'))
        names = [c.unit.char_id for c in chars]
        assert not (set(names) & EXPERT_CHARS), \
            f'seed={seed} 开局手牌混入专家: {names}'


def test_apply_opening_writes_container_opening_state() -> None:
    """开局态写入容器(obs 渠道;u07u28 §③:金 3/等级 3/cap 3;
    M06 首个写端 = 开局备战席先于商店发牌)。"""
    sess = StrategySession()
    gs = game_state_of(sess)
    apply_opening(gs, _cfg(enemy_affixes=('开局不利',)),
                  stream_rng(11, 'M01/opening_hand'))
    assert gs.hp.value == 62 and gs.hp.source == 'observation'
    assert gs.gold.value == OPENING_GOLD and gs.level.value == OPENING_LEVEL
    assert gs.deploy_cap.value == OPENING_DEPLOY_CAP
    assert gs.xp.value == (0, 4), '等级 3 门槛表首档 = 4(cw_economy XP 表)'
    assert gs.streak.value == 0
    assert gs.selected_difficulty.value == 'A8'
    assert gs.enemy_affixes.value == ['开局不利']
    assert gs.hp.evidence is not None \
        and gs.hp.evidence.startswith('sim:engine:'), \
        '引擎直写 evidence 带 sim:engine 前缀(失配抑制登记面契约)'
    units = [s.unit for s in gs.bench.value.slots if s.unit is not None]
    assert len(units) == 4 and all(u.star == 1 for u in units), \
        '开局备战席 = 4 张全 1★(M06 派生池不变量首个写端)'
    assert gs.heartbeat() > 0, '开局写入推进容器心跳'
