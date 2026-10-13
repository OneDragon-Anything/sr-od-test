"""sim 节点事件面(M16 遭遇/M17 晶矿·扑满·箱/M18 补给/M22 overlay)
回归锁(sim 后端规则件)。

锁面 = U22 遭遇档位结构/U23 晶矿面板单例锚/扑满替换单一源/U24·T-9 补给
3 选 1 基础件放回均匀 + 带钻占位 + 环境每列件数表(ENV_SUPPLY_EQUIP_
COUNT)/M22 overlay 队列框架与占位披露。pick 动作
入账腿退役(锁面迁 test_cw_sim_backend.py:选卡走 op → 上报函数族获得
链,与实机同构);遭遇加成真值表归宿 = cw_sim_enemy(难度账域)。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel import cw_investments
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

def test_supply_options_replacement_sampling_and_env_driven() -> None:
    """U24/T-9:3 选项 = 8 基础件池**逐槽独立均匀有放回**(裁定 3:单纯
    随机可重复——「随机到一样就一样」;既有 distinct 断言锁旧设计约定,
    随裁定退役)+ 带钻槽 equip 级均匀占位(恰一选项带钻);默认环境每列
    1 件、'过剩经费' 每列 2 件(ENV_SUPPLY_EQUIP_COUNT 查表);char 维
    恒空(补给 = 装备选)。带钻授予腿 = 后端列表派生(锁面 =
    test_cw_sim_backend.py 补给窗)。同 seed 采样值随采样式变更漂移 =
    分布假设变更(设计披露 9),非回归破坏。"""
    # 默认环境:同 seed 逐值确定(回归可重跑)+ 结构恒定
    for seed in (0, 7, 42):
        a = supply_options(random.Random(seed))
        assert a == supply_options(random.Random(seed)), '同 seed 逐值确定'
        assert len(a) == 3
        assert sum(1 for o in a if o.has_diamond) == 1, '恰一带钻选项'
        assert all(o.char == '' for o in a)
        assert all(o.extra_equips == () for o in a), '默认环境每列 1 件'
    # 放回采样可重复:多 seed 扫描必存在同 offer 重复样本(逐槽独立
    # choice 的直接后果;跨列/同列重复同源,归档帧证跨列真实游戏可重)
    dup = any(len({o.equip for o in supply_options(random.Random(s))}) < 3
              for s in range(200))
    assert dup, '放回采样存在重复样本(不重名断言已随裁定退役)'

    # 过剩经费:每列 2 件(equip + extra_equips 恰 1 件)、恰一选项带钻
    env = cw_investments.normalize_invest_name('过剩经费')
    assert env == '过剩经费'
    opts = supply_options(random.Random(11), env)
    assert len(opts) == 3
    for o in opts:
        assert o.equip and len(o.extra_equips) == 1, '每列 2 件(首件+附加件)'
    assert sum(1 for o in opts if o.has_diamond) == 1, '恰一选项带钻(选项级布尔)'
    # 同列重复合法:锁定一个同列重复样本(逐槽独立放回的直接允许态;
    # 探针记录 = seed 22 首个命中)
    same_col = [(s, os_) for s in range(500)
                for os_ in [supply_options(random.Random(s), env)]
                if any(o.extra_equips and o.extra_equips[0] == o.equip
                       for o in os_)]
    assert same_col, '放回采样在同列也产出重复(1/8 每列,设计披露 9)'
    seed_hit, opts_hit = same_col[0]
    assert supply_options(random.Random(seed_hit), env) == opts_hit, \
        '同列重复样本同 seed 可重放'


def test_env_supply_equip_count_registry_and_validation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ENV_SUPPLY_EQUIP_COUNT 登记表构建校验(import 即炸语义,注入 +
    直调,沿 ENV_STREAK_GRANTS 测试惯用法):孤儿环境键 / 值形(<2 或
    非 int 与默认 1 件无差 = 登记笔误);现表默认通过(与卡面 id 108
    同源)。"""
    assert cw_investments.ENV_SUPPLY_EQUIP_COUNT == {'过剩经费': 2}
    cw_investments._validate_env_supply_equip_count()

    # ① 孤儿环境键(版本更新改名/移除后静默失联 → 构建期炸)
    bad = dict(cw_investments.ENV_SUPPLY_EQUIP_COUNT)
    bad['不存在环境'] = 2
    monkeypatch.setattr(cw_investments, 'ENV_SUPPLY_EQUIP_COUNT', bad)
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_env_supply_equip_count()
    monkeypatch.undo()

    # ② 值形:<2 与默认 1 件无差 / 非 int(bool 排除)/ 0 = 登记笔误
    for bad_val in (1, 0, -1, True, 1.5):
        bad = dict(cw_investments.ENV_SUPPLY_EQUIP_COUNT)
        bad['过剩经费'] = bad_val
        monkeypatch.setattr(cw_investments, 'ENV_SUPPLY_EQUIP_COUNT', bad)
        with pytest.raises(ValueError, match='值形'):
            cw_investments._validate_env_supply_equip_count()
        monkeypatch.undo()


# ============================================================ M22 overlay
# (统一队列 FIFO/词表守卫测试已随  队列
#  退役删除:呈现数据源 = 容器登记,kind 词表守卫 =
#  register 口封闭集,锁在 test_cw_overlay_trigger。)
# (overlay 选项生成占位测试已随占位框架退役删除:选项效果建模候实机补档按需重建,呈现数据源 = 容器登记。)
# (占位效果应用测试已随占位框架退役删除:选中值写容器归选卡上报链,chosen 位映射见 kernel 词表。)
