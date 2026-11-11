"""终身学习(id 330901)行为锁(镜像 src = STRATEGY_PLANE_START_GRANTS
位面开始专表 + check_strategy_plane_start_grants 窗检查函数 +
apply_strategy_plane_refire_item 选卡拍补发效果条目;先例 = 节点条件晶矿发放
三件套锁形 + 位面段补发族[固定理财族同判])。

测试面依据 = 设计稿(原件已退役)T-367 对应稿
(已退役评审稿 无需用户决定 10/10;卡面官方原文:「获得1个【星徽秘典】。每个位面
开始时,获得1个【星徽秘典】。」;位面段补发 = 用户裁定 2026-11-01 B 案
补发·当前位面全额族级口径,裁定注释点名终身学习共享):

- 表锁:登记行 id/item/count 现值 + KINDS['星徽秘典']=='tome' 正例;
- 行为锁:持卡局位面首窗(r==1)入席 +1 效果串恰 1 条;r=2 短路零写;
  未持卡零写;未注册卡持卡零写;席满溢出 overflow_card 身份;
- 补发效果条目锁:中途拿卡局 gs.node 在场 → 补发 +1;node None 保守零补发。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_plane_start_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    BENCH_ITEM_KINDS,
    STRATEGY_GRANTS,
    STRATEGY_PLANE_START_GRANTS,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPre')
_SIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                  mode='compute')


def _make_gs(held: tuple[str, ...], bench_full: bool = False) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots = [BenchSlot(kind='full')] * 9 if bench_full \
        else [BenchSlot(kind='empty')] * 9
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.active_strategies, list(held), sig=_SIG_OBS)
    return gs


def test_table_registration() -> None:
    """表锁:登记行现值 + KINDS 类别正例 + GRANTS 即时效果条目已登记。"""
    grant = STRATEGY_PLANE_START_GRANTS['终身学习']
    assert grant.id == '330901', f'id 漂移: {grant.id!r}'
    assert grant.item == '星徽秘典', f'item 漂移: {grant.item!r}'
    assert grant.count == 1, f'count 漂移: {grant.count!r}'
    assert BENCH_ITEM_KINDS['星徽秘典'] == 'tome', 'KINDS 类别漂移'
    assert '终身学习' in STRATEGY_GRANTS, '即时效果条目 GRANTS 行缺席'
    assert STRATEGY_GRANTS['终身学习'].items_immediate == ('星徽秘典',)


def test_plane_first_window_grants() -> None:
    """行为锁:持卡局位面首窗(r==1)入席 +1,效果串恰 1 条前缀。"""
    gs = _make_gs(('终身学习',))
    seq = check_strategy_plane_start_grants(gs, node_pos=(2, 1), sig=_SIG)
    assert len(seq) == 1 and seq[0].startswith('plane_start_grant:'), \
        f'效果串形: {seq!r}'
    assert '星徽秘典' in seq[0], f'发放物缺席: {seq!r}'


def test_non_first_window_short_circuit() -> None:
    """行为锁:r=2 短路零写(窗谓词单边,非位面首窗不发)。"""
    gs = _make_gs(('终身学习',))
    seq_before = gs.write_seq
    seq = check_strategy_plane_start_grants(gs, node_pos=(2, 2), sig=_SIG)
    assert seq == [], f'r=2 应零条目: {seq!r}'
    assert gs.write_seq == seq_before, 'r=2 零写'


def test_not_held_no_writes() -> None:
    """行为锁:未持卡零写(持卡谓词单边)。"""
    gs = _make_gs(())
    seq_before = gs.write_seq
    seq = check_strategy_plane_start_grants(gs, node_pos=(2, 1), sig=_SIG)
    assert seq == [], f'未持卡应零条目: {seq!r}'
    assert gs.write_seq == seq_before, '未持卡零写'


def test_bench_full_overflow_identity() -> None:
    """行为锁:席满溢出 overflow_card 身份 = 星徽秘典。"""
    gs = _make_gs(('终身学习',), bench_full=True)
    check_strategy_plane_start_grants(gs, node_pos=(2, 1), sig=_SIG)
    assert gs.overflow_card.value == '星徽秘典', '溢出位身份 = 道具名'


def test_refire_item_leg() -> None:
    """补发效果条目锁:中途拿卡局 gs.node 在场 → 补发入席;None 保守零补发。"""
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        apply_strategy_plane_refire_item,
    )
    gs = _make_gs(('终身学习',))
    # 中途拿卡 = 已在节点窗内(node 在场 = 位面已开始判据;None = 保守零补发)
    gs.observe(gs.node, (2, 1), sig=_SIG_OBS)
    n = apply_strategy_plane_refire_item(gs, ['终身学习'])
    assert n == 1, f'补发件数: {n!r}'
    gs2 = _make_gs(('终身学习',))
    # node 未观察(None)= 保守零补发(禁猜)
    n2 = apply_strategy_plane_refire_item(gs2, ['终身学习'])
    assert n2 == 0, f'node None 应零补发: {n2!r}'
