"""sim 节点事件面(M16 遭遇/M17 晶矿·扑满·箱/M18 补给/M22 overlay)
回归锁(sim 后端规则件)。

锁面 = U22 遭遇档位结构/U23 晶矿面板单例锚/扑满替换单一源/U24 补给
3 选 1 基础件均匀 + 带钻占位/M22 overlay 队列框架与占位披露。pick 动作
入账腿退役(锁面迁 test_cw_sim_backend.py:选卡走 op → 上报函数族获得
链,与实机同构);遭遇加成真值表归宿 = cw_sim_enemy(难度账域)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    BOX_CANDIDATES,
    box_options,
    encounter_options,
    is_piggy_node,
    supply_options,
)
from sr_od.application.currency_war.sim.cw_sim_enemy import (
    ENCOUNTER_TIER_BONUS,
)


def _gs(node_kind: str = 'reward') -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    sig = ChannelSig(family='obs', actor='TestSigWriter')
    gs.observe(gs.node, NodeKey(plane=1, round_num=7, kind=node_kind), sig=sig)
    return gs


# ============================================================ M16 遭遇

def test_encounter_options_structure_and_tier_bonus_truth() -> None:
    """U22:档位集 = 四档序结构;遭遇等级加成四档 0/10/20/30 = 定谳
    真值(economy.md §9,唯一有档数值;表住 cw_sim_enemy 难度账域)。"""
    opts = encounter_options()
    assert len(opts) == 4
    assert [o.difficulty for o in opts] == [1, 2, 3, 4]
    assert [o.idx for o in opts] == [0, 1, 2, 3]
    assert ENCOUNTER_TIER_BONUS == (0, 10, 20, 30)


# ============================================================ M17 晶矿/扑满/箱

def test_piggy_env_replacement_single_source() -> None:
    """扑满替换守卫:经济过热族环境 + reward 节点 → True;其它环境/
    其它节点型恒 False(单一源 = PIGGY_ENV_NAMES × active_env)。"""
    gs = _gs('reward')
    gs.observe(gs.active_env, '经济过热', sig=ChannelSig(family='obs', actor='TestSigWriter'))
    assert is_piggy_node(gs)
    gs.observe(gs.active_env, '轮岗', sig=ChannelSig(family='obs', actor='TestSigWriter'))
    assert not is_piggy_node(gs)
    assert not is_piggy_node(_gs('battle')), '非奖励节点恒 False'


def test_box_candidates_four_choices() -> None:
    """补给箱 4 选 1 装备:候选 = 4(U23);入栏腿走获得链(锁面 =
    test_cw_sim_backend.py 箱腿)。"""
    assert len(box_options()) == BOX_CANDIDATES == 4


# ============================================================ M18 补给

def test_supply_options_three_distinct_one_diamond() -> None:
    """U24:3 选项 = 8 基础件池不放回(互不重名)+ 恰一带钻槽(均匀
    占位);char 维恒空(补给 = 装备选)。带钻授予腿 = 后端
    diamond_count 写端(锁面 = test_cw_sim_backend.py 补给窗)。"""
    seen_equips: set[str] = set()
    for seed in range(30):
        opts = supply_options(random.Random(seed))
        assert len(opts) == 3
        assert len({o.equip for o in opts}) == 3
        assert sum(1 for o in opts if o.has_diamond) == 1
        assert all(o.char == '' for o in opts)
        seen_equips.update(o.equip for o in opts)
    assert len(seen_equips) >= 5, '多 seed 下池取样有分散度'


# ============================================================ M22 overlay
# (统一队列 FIFO/词表守卫测试已随  队列
#  退役删除:呈现数据源 = 容器登记,kind 词表守卫 =
#  register 口封闭集,锁在 test_cw_overlay_trigger。)
# (overlay 选项生成占位测试已随占位框架退役删除:选项效果建模候实机补档按需重建,呈现数据源 = 容器登记。)
# (占位效果应用测试已随占位框架退役删除:选中值写容器归选卡上报链,chosen 位映射见 kernel 词表。)
