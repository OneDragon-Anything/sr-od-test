"""deploy_diff 发出面 back_slot_count 填参测试(纯函数直测)。

锁的设计约定(统一拖动参数面迁移:发出点填参 = back_capacity_of(gs)
生成期快照,读口单一源、None 退 6 基线;op 侧按布局档静态解析拖点消费):
- 种子 back_layout=8 → 产出的 MoveUnit 参数 back_slot_count == 8;
- 未观察(None)→ 6 缺省。

被测单一源 = ``deploy_diff.deploy_diff_actions``(上场分支)。
"""

from sr_od.application.currency_war.kernel.cw_game_state import (
    BENCH_CAPACITY_DEFAULT,
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.deploy_diff import (
    deploy_diff_actions,
)

_OBS = ChannelSig(family='obs', actor='test')


def _seed_gs(back_layout: int | None) -> GameState:
    """测试种子:bench 首槽有单位、板面全空 → place_missing 产一条
    bench→front 拖动(与观察链同写入口 gs.observe;back_layout None =
    字段不写 = 未观察)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id='银狼', star=2, equips=[]))]
    slots += [BenchSlot(kind='empty')] * 8
    gs.observe(gs.bench, BenchView(slots=slots,
                                   capacity=BENCH_CAPACITY_DEFAULT),
               sig=_OBS)
    gs.observe(gs.deployed,
               DeployedView(front_slots=[None] * 4, back_slots=[None] * 6),
               sig=_OBS)
    if back_layout is not None:
        gs.observe(gs.back_layout, back_layout, sig=_OBS)
    return gs


def test_back_slot_count_filled_from_back_layout() -> None:
    """back_layout=8 → 产出动作载荷 back_slot_count == 8(生成期快照)。"""
    actions = deploy_diff_actions(_seed_gs(8), {'银狼': ('front', 2, None)})
    assert len(actions) == 1
    a = actions[0]
    assert a.src_domain == 'bench' and a.dst_domain == 'front'
    assert a.reason == 'deploy_diff_place'
    assert a.back_slot_count == 8


def test_back_slot_count_default_six_when_unobserved() -> None:
    """back_layout 未观察(None)→ back_slot_count == 6(读口基线缺省)。"""
    actions = deploy_diff_actions(_seed_gs(None), {'银狼': ('front', 2, None)})
    assert len(actions) == 1
    assert actions[0].back_slot_count == 6
