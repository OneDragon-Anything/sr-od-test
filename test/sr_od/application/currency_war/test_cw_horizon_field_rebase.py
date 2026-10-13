"""视界族场字段重基 · 锁 10(设计 §2.11 锁 10;详设 = 迭代
abolish-node-ordinal details/horizon-cleanup.md,下称 details)。

锁面地图(判据 = details §3 门面契约 / §6 boss kind 化 / §8 行为变化申报):

- 门面默认表逐值对拍:statefn/horizon r_remaining/r_global 场字段求和
  与退役公式(同真值源的 对拍参照,败局闩对拍先例同款)逐帧一致;
- 修饰表封顶对拍:P1=10 不被 [1,9] 夹取(details §8.1 少 1 偏差消除);
- None 回退默认表(未注册态;P2 先验 9→7 = details §8.5 真值修正);
- 位面 ∉ 序列表键集(含 P3)契约:返回 0(details §3,禁 KeyError);
- boss 计数 kind 化变化申报面(P1 段 3→2、P2 起 2→1,details §8.3;
  通道级判别锁在 test_cw_invest_strategy.py,本文件锁策略值通道);
- hp_safe 阈 nodes_left 封顶变化(默认局 P2 r1 18→7,details §8.4);
- total_remaining_nodes 修正后与门面同值(P3 段不再虚构,details §8.7);
- 标定域 18:E2_DOMAIN_R_REMAIN_MAX 27→18(details §8.6/§7)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_economy import (
    HP_SAFE_THRESHOLD,
    effective_hp_threshold,
)
from sr_od.application.currency_war.kernel.cw_first_passage import (
    board_tier_of,
    plane_hp_ratio,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    GameState,
    NodeKey,
    game_state_of,
    level_of,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    total_remaining_nodes,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    P1_NODE_SEQUENCE,
    P2_NODE_SEQUENCE,
    resolve_plane_node_seqs,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
    calibration,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.horizon import (
    r_global,
    r_remaining,
)

_MODIFIED = resolve_plane_node_seqs('人身意外险')

_SIG_OBS = ChannelSig(family='obs', actor='TestHorizonRebase', mode='read')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='TestHorizonRebase',
                        mode='compute')


def _gs_at(plane: int, round_num: int,
           node_seqs: dict[int, tuple[str, ...]] | None = None) -> GameState:
    """帧构造(可选写节点序列场字段;None = 未注册态,与生产消费读法
    同通道 write_logic)。"""
    gs = game_state_of(SimpleNamespace())
    if node_seqs is not None:
        gs.write_logic(gs.node_seq_by_plane, node_seqs,
                       produced_by='TestHorizonRebase',
                       evidence='node_seq:env', sig=_SIG_LOGIC)
    gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num, kind=''),
               evidence='test', sig=_SIG_OBS)
    return gs


# ===== 对拍参照(退役公式逐值复刻;唯一合法用途 = 对拍,非活代码)=====

def _legacy_r_global(seq_lengths: dict[int, int], plane: int,
                     node_in_plane: int) -> int:
    """退役 kernel r_global 的逐值对拍参照(同真值源长度表入参;
    含当前节点 + 到局终,长度源由调用方给定 = 对拍公平性)。"""
    in_plane = max(0, seq_lengths[plane] - (node_in_plane - 1))
    return in_plane + sum(v for k, v in seq_lengths.items() if k > plane)


# ===== 门面默认表逐值对拍 =====

def test_facade_default_table_matches_legacy_formula_frame_by_frame():
    """默认表(None 回退)全 modeled 帧逐值对拍:门面场字段求和 =
    退役公式(同真值源),含当前节点、到局终、封顶 modeled planes
    (默认局总视界 16,旧 27 制不再出现)。"""
    lengths = {1: len(P1_NODE_SEQUENCE), 2: len(P2_NODE_SEQUENCE)}
    for plane in (1, 2):
        for rnd in range(1, lengths[plane] + 1):
            gs = _gs_at(plane, rnd)
            expect = _legacy_r_global(lengths, plane, rnd)
            assert r_global(gs, plane, rnd) == expect, (plane, rnd)
            assert r_remaining(gs, plane, rnd) == expect, (plane, rnd)


def test_facade_none_fallback_default_table():
    """None(未注册态)回退默认表:P1R1 = 16(默认表 P1+P2,零 P3
    虚拟);P2R1 = 7(旧 schedule_of 先验回退给 9 → 7,details §8.5
    真值修正方向)。"""
    gs = _gs_at(1, 1)
    assert r_global(gs, 1, 1) == 16
    assert r_global(gs, 2, 1) == 7


def test_facade_modified_table_unclamped_truth():
    """修饰表(P1=10/P2=8)封顶对拍:[1,9] 夹取不存在的真值——
    (1,10) 在位面内仍余 1(旧夹取归 0,details §8.1 少 1 偏差消除);
    (1,9) 余 2;(1,1) = 10+8 = 18(details §8.2 修饰局总视界);
    位面末 (2,8) = 1。"""
    assert r_global(_gs_at(1, 1, _MODIFIED), 1, 1) == 18
    assert r_global(_gs_at(1, 9, _MODIFIED), 1, 9) == 10
    assert r_global(_gs_at(1, 10, _MODIFIED), 1, 10) == 9
    assert r_global(_gs_at(2, 8, _MODIFIED), 2, 8) == 1


def test_facade_plane_outside_key_set_returns_zero():
    """位面 ∉ 序列表键集(含 P3)契约 = 返回 0(details §3:局终后无
    剩余轮;禁 KeyError/异常形态;P3 = 建模域外 = 运行终局)。"""
    for seqs in (None, _MODIFIED):
        gs = _gs_at(3, 1, seqs)
        assert r_global(gs, 3, 1) == 0
        assert r_remaining(gs, 3, 7) == 0


# ===== strategy_economy boss 计数(变化申报面,details §8.3)=====

def test_strategy_economy_boss_count_declared_shift():
    """boss 计数默认局申报面对拍:P1 段 3→2、P2 起 2→1(P3 虚拟末槽
    移除;gold_per_boss_node 通道现金分随 7/节点)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
        strategy_economy_value,
    )
    # P1R1:默认表每位面恰 1 个 kind boss,位面末(旧几何把 P3 虚拟末槽
    # 计入 → 3)→ 2
    assert strategy_economy_value('特战资金', _gs_at(1, 1)) == (14.0, True)
    # P2R1:当前位面 1 个(旧几何含 P3 虚拟 → 2)→ 1
    assert strategy_economy_value('特战资金', _gs_at(2, 1)) == (7.0, True)


# ===== hp_safe 阈 nodes_left 封顶变化(details §8.4)=====

def test_hp_safe_nodes_left_capped_at_modeled_planes():
    """hp_safe 阈对拍:默认局 P2R1 nodes_left 27 制闭式 18 → 场字段
    modeled 总长 7(期望值用生产 plane_hp_ratio 按 7 重算,单测对象 =
    nodes_left 接线,非生存模型;帧取 lv7 = 板强档 2——该档 7/18 节点
    两口径比值分叉 1.75 vs 1.851,接线错接旧闭式即红);P1 分支同式
    不变(直接返 base);P3 帧(位面 ∉ 键集 → 0)→ 零未来掉血节点 →
    阈回落 base。"""
    p2r1 = _gs_at(2, 1)
    p2r1.observe(p2r1.level, 7, evidence='test', sig=_SIG_OBS)
    tier = board_tier_of(level_of(p2r1))
    assert tier == 2, '前置:该档下 nodes_left 两口径可判别'
    assert plane_hp_ratio(tier, 7, plane=2) != plane_hp_ratio(tier, 18, plane=2)
    expect = min(100, int(HP_SAFE_THRESHOLD * plane_hp_ratio(tier, 7, plane=2)))
    assert effective_hp_threshold(p2r1) == expect
    # P1 分支:plane <= 1 直接返 base(difficulty 缺省 → HP_SAFE_THRESHOLD)
    assert effective_hp_threshold(_gs_at(1, 5)) == HP_SAFE_THRESHOLD
    # P3 帧:nodes_left = 0 → ratio 1.0 → base
    assert effective_hp_threshold(_gs_at(3, 1)) == HP_SAFE_THRESHOLD


# ===== total_remaining_nodes 修正对拍(details §8.7)=====

def test_total_remaining_nodes_matches_facade_in_modeled_planes():
    """修正后默认局 P1/P2 段与门面同值(逐帧);P3 段不再虚构(旧 27
    制闭式在 P3 仍给正余量,新 = 0)。"""
    lengths = {1: len(P1_NODE_SEQUENCE), 2: len(P2_NODE_SEQUENCE)}
    for plane in (1, 2):
        for rnd in range(1, lengths[plane] + 1):
            gs = _gs_at(plane, rnd)
            assert total_remaining_nodes(gs) == r_global(gs, plane, rnd), \
                (plane, rnd)
    assert total_remaining_nodes(_gs_at(3, 1)) == 0


# ===== 标定域 18(details §7/§8.6)=====

def test_calibration_domain_r_remain_max_is_18():
    """标定域收紧:E2_DOMAIN_R_REMAIN_MAX = 18(场字段 modeled 总长
    上界 = 修饰 P1+P2 = 10+8);域边界:18 在域内、19 出域 fail-closed。"""
    assert calibration.E2_DOMAIN_R_REMAIN_MAX == 18
    assert calibration.band_in_domain(6, 18) is True
    assert calibration.band_in_domain(6, 19) is False
