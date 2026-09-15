"""sim 重做 S7(M16 遭遇/M17 奖励球·扑满·箱/M18 补给/M22 overlay)回归锁。

设计正本 = ``docs/develop/sr_od/application/currency_war/changes/
2026-09-15-sim-redesign/design.md``;锁面 = U22 遭遇档位结构与加成
真值/U23 球面板单例锚与入账语义/扑满替换单一源/U24 补给 3 选 1 基础件
均匀 + 带钻占位/M22 overlay 队列框架与占位披露。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_game_state import (
    BS_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
    register_sig_actors,
)
from sr_od.application.currency_war.sim.cw_sim_nodes import (
    BOX_CANDIDATES,
    ENCOUNTER_TIER_BONUS,
    ENCOUNTER_TIER_COUNT,
    apply_ball_pick,
    apply_box_pick,
    apply_encounter_pick,
    apply_supply_pick,
    box_options,
    encounter_options,
    is_piggy_node,
    reward_ball_panel,
    supply_options,
)
from sr_od.application.currency_war.sim.cw_sim_overlay import (
    OVERLAY_KINDS,
    OverlayQueue,
    apply_disclosed_pick,
    pending_disclosure_items,
    sample_options,
)

register_sig_actors('TestSigWriter')


def _bs(node_kind: str = 'reward') -> GameState:
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    sig = ChannelSig(family='obs', actor='TestSigWriter')
    bs.observe(bs.node, NodeKey(plane=1, round_num=7, kind=node_kind), sig=sig)
    return bs


# ============================================================ M16 遭遇

def test_encounter_options_structure_and_tier_bonus_truth() -> None:
    """U22:档位集 = 四档序结构;遭遇等级加成四档 0/10/20/30 = 定谳
    真值(economy.md §9,唯一有档数值)。"""
    opts = encounter_options()
    assert len(opts) == ENCOUNTER_TIER_COUNT == 4
    assert [o.difficulty for o in opts] == [1, 2, 3, 4]
    assert [o.idx for o in opts] == [0, 1, 2, 3]
    assert ENCOUNTER_TIER_BONUS == (0, 10, 20, 30)


def test_encounter_pick_writes_chosen() -> None:
    """选档入账:chosen_encounter = (难度档 1 基, 奖励文本)——引擎把
    加成表对应档进 M19 难度账。"""
    bs = _bs()
    tier, reward_text = apply_encounter_pick(bs, 2)
    assert tier == 3
    assert bs.chosen_encounter.value == (3, reward_text)
    assert reward_text


# ============================================================ M17 奖励球/扑满/箱

def test_piggy_env_replacement_single_source() -> None:
    """扑满替换守卫:经济过热族环境 + reward 节点 → True;其它环境/
    其它节点型恒 False(单一源 = PIGGY_ENV_NAMES × active_env)。"""
    bs = _bs('reward')
    bs.observe(bs.active_env, '经济过热', sig=ChannelSig(family='obs', actor='TestSigWriter'))
    assert is_piggy_node(bs)
    bs.observe(bs.active_env, '轮岗', sig=ChannelSig(family='obs', actor='TestSigWriter'))
    assert not is_piggy_node(bs)
    assert not is_piggy_node(_bs('battle')), '非奖励节点恒 False'


def test_reward_ball_panel_u23_anchor() -> None:
    """U23 单例锚:面板 = 1 大金球+5 蓝球+2 灰球(共 8 球;颜色结构 =
    唯一有据面)。"""
    panel = reward_ball_panel()
    assert len(panel) == 8
    by_color = {c: sum(1 for b in panel if b.color == c)
                for c in ('金', '蓝', '灰')}
    assert by_color == {'金': 1, '蓝': 5, '灰': 2}


def test_ball_pick_gold_and_equip_settlement() -> None:
    """点球即时入账:金球直加金账;蓝球直入装备栏。"""
    bs = _bs()
    sig = ChannelSig(family='obs', actor='TestSigWriter')
    bs.observe(bs.gold, 10, sig=sig)
    kind, amount = apply_ball_pick(bs, 0, rng=random.Random(1))  # 0 = 金球
    assert (kind, amount) == ('gold', 30)
    assert bs.gold.value == 40
    equip_count_before = len(bs.equips.value or [])
    kind, amount = apply_ball_pick(bs, 1, rng=random.Random(2))  # 1 = 蓝球
    assert (kind, amount) == ('equip', 1)
    assert len(bs.equips.value) == equip_count_before + 1


def test_box_pick_four_choices_into_equips() -> None:
    """补给箱 4 选 1 装备:候选 = 4(U23);开箱入装备栏。"""
    assert len(box_options()) == BOX_CANDIDATES == 4
    bs = _bs()
    pick = box_options()[0]
    apply_box_pick(bs, pick)
    assert bs.equips.value == [pick]


# ============================================================ M18 补给

def test_supply_options_three_distinct_one_diamond() -> None:
    """U24:3 选项 = 8 基础件池不放回(互不重名)+ 恰一带钻槽(均匀
    占位);char 维恒空(补给 = 装备选)。"""
    seen_equips: set[str] = set()
    for seed in range(30):
        opts = supply_options(random.Random(seed))
        assert len(opts) == 3
        assert len({o.equip for o in opts}) == 3
        assert sum(1 for o in opts if o.has_diamond) == 1
        assert all(o.char == '' for o in opts)
        seen_equips.update(o.equip for o in opts)
    assert len(seen_equips) >= 5, '多 seed 下池取样有分散度'


def test_supply_pick_writes_equip_returns_diamond() -> None:
    """选卡入账:装备入装备栏;带钻选项返回 True(引擎宝钻计数消费)。"""
    bs = _bs()
    opts = supply_options(random.Random(7))
    diamond = next(o for o in opts if o.has_diamond)
    plain = next(o for o in opts if not o.has_diamond)
    assert apply_supply_pick(bs, plain) is False
    assert apply_supply_pick(bs, diamond) is True
    assert set(bs.equips.value) >= {plain.equip, diamond.equip}


# ============================================================ M22 overlay

def test_overlay_queue_fifo_and_registry_guard() -> None:
    """队列:入队序呈现(FIFO);集外 kind 入队即炸(防词表漂移);
    peek 不出队。"""
    q = OverlayQueue()
    assert q.peek() is None
    q.push('megastar')
    q.push('partner')
    assert q.peek() == 'megastar'
    assert len(q) == 2
    assert q.pop() == 'megastar'
    assert q.pop() == 'partner'
    try:
        q.push('nope')
        raise AssertionError('集外 kind 应炸错')
    except ValueError:
        pass
    assert {'megastar', 'partner', 'expert', 'fate', 'aha', 'hack',
            'planner'} <= OVERLAY_KINDS


def test_overlay_options_placeholders_distinct() -> None:
    """选项生成占位:expert 五选一(画面档语义)/其余三选一;同屏不
    重名;pending 清单按族过滤。"""
    roster = tuple(f'角色{i}' for i in range(8))
    assert len(sample_options(random.Random(1), 'expert', roster)) == 5
    assert len(sample_options(random.Random(2), 'megastar', roster)) == 3
    assert 'expert_trigger' in pending_disclosure_items('expert')
    assert not pending_disclosure_items('planner'), 'planner 触发有档(M21)'
    assert 'fate_gate_and_rewards' in pending_disclosure_items('fate')


def test_disclosed_pick_chosen_field_mapping() -> None:
    """占位效果应用:在册 chosen 位按族映射写入;无位族(fate/aha)
    不写容器词表外字段。"""
    bs = _bs()
    apply_disclosed_pick(bs, 'megastar', '角色A')
    assert bs.chosen_megastar.value == '角色A'
    apply_disclosed_pick(bs, 'partner', '角色B')
    assert bs.chosen_partner.value == '角色B'
    apply_disclosed_pick(bs, 'hack', '选项X')
    assert bs.chosen_hack.value == '选项X'
    apply_disclosed_pick(bs, 'fate', '选项Y')  # 不炸、不写
    apply_disclosed_pick(bs, 'aha', '选项Z')
    assert bs.chosen_fortune.value is None
