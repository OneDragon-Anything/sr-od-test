"""溢出腿三账同帧锁面(容器版,阶段 3.5 宿主迁移)。

三账 = 容器 bench(写口回占)/执行账 tracked(kernel 直调已锁
test_cw_overflow_tracked_sync.py)/调用点 session 透传线。原黑板帧镜像腿
(`_project_prep_obs`)随黑板退役——镜像语义现由卖备战上报函数
report_action_sell_bench_param 溢出分支全量承载(入位卡回占 + tracked
吸收 + 旗标清,单点单一源):

1. 溢出腿落地:入位卡回占卖出槽(容器 bench),席空数派生自然不 +1
   (缺回占 = 决策面假空席,席满拒落类门被假象绕过);同帧断言执行账
   吸收 = 锁调用点 session 透传这根线;
2. 镜像不误发:陈旧提案(卖出槽容器已空)→ 写口零写、旗标不清。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from test.sr_od.application.currency_war._cw_helpers import cw4_bview

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_sell_bench_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    ChannelSig,
    Unit,
    bench_free_slots,
    bench_view_slots_of,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionSellBenchParam,
)

if TYPE_CHECKING:
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        CwScreenPrep,
    )

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')
_LOGIC_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')


def _seed(session, *, ov_id: str = '不死途'):
    """容器 bench=[花火@1, 刃@2] + 溢出态(3.2 单账化:主域即唯一账)。"""
    gs = game_state_of(session)
    gs.write_logic(gs.bench, cw4_bview(
        [BenchSlot(kind='unit', unit=Unit(char_id='花火', star=1)),
         BenchSlot(kind='unit', unit=Unit(char_id='刃', star=1))]),
        produced_by='test', sig=_SIG)
    gs.write_logic(gs.gold, 10, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_warning, True, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_card, ov_id, produced_by='test', sig=_SIG)
    return gs


def _stub(session) -> CwScreenPrep:
    """无框架状态的桩宿主(零 IO;_session 供 session 透传线)。"""
    stub = CwScreenPrep.__new__(CwScreenPrep)
    stub._session = lambda: session
    return stub


def test_prep_mirror_backfills_card_and_keeps_free_count():
    """溢出腿落地(容器版,阶段 3.5):入位卡回占卖出槽(容器 bench 槽
    回占,席空数派生自然不 +1;3.2 单账化后容器即唯一账)。原黑板帧
    镜像断言随 _project_prep_obs 退役。"""
    session = StrategySession()
    gs = _seed(session)

    report_action_sell_bench_param(gs, CwActionSellBenchParam(bench_idx=0),
                                   sig=_LOGIC_SIG, session=session)

    dep = bench_view_slots_of(gs)
    assert dep[0] is not None and dep[0].kind == 'unit' \
        and dep[0].unit.char_id == '不死途'   # 入位卡回占槽 1
    assert dep[1] is not None and dep[1].kind == 'unit' \
        and dep[1].unit.char_id == '刃'
    assert bench_free_slots(gs) == 7       # 回占 → 不 +1(缺镜像 = 假空席绕过席满门)
    # (3.2 单账化:原 tracked 同帧吸收断言随第二账退役删,容器即唯一账)


def test_prep_mirror_needs_leg_landed_not_flag_alone():
    """镜像不误发:陈旧提案(卖出槽容器已空)→ 写口零写、旗标不清 →
    镜像判定不触发,主域零写(席空数派生自容器,零写即零变化)。"""
    session = StrategySession()
    gs = _seed(session)
    # 陈旧提案:卖出槽 1 容器已空(提案与容器失配,写口守卫零写)
    gs.write_logic(gs.bench, cw4_bview(
        [None, BenchSlot(kind='unit', unit=Unit(char_id='刃', star=1))]),
        produced_by='test', sig=_SIG)

    report_action_sell_bench_param(gs, CwActionSellBenchParam(bench_idx=0),
                                   sig=_LOGIC_SIG)

    dep = bench_view_slots_of(gs)
    assert (dep[0] is None or dep[0].kind == 'empty') \
        and dep[1].kind == 'unit' and dep[1].unit.char_id == '刃'   # 容器零写
    assert gs.overflow_warning.value is True    # 旗标未消费(写口零写)
    assert bench_free_slots(gs) == 8            # 零写 → 席空数不变
    # (3.2 单账化:原 tracked 零写断言随第二账退役删,容器即唯一账)
