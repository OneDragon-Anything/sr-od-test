"""T-231 溢出腿黑板帧镜像锁面(T-227 三账同帧的镜像半补粒度)。

T-227 修法 = 三账同帧(容器腿/执行账 tracked/黑板帧):kernel 写口的
tracked 吸收半已锁(test_cw_overflow_tracked_sync.py);本文件锁第三半
——CwScreenPrep._project_prep_obs 的 SellBench 黑板帧镜像腿(纯计算零
读屏,桩宿主 __new__ 绕道直调,模式同 test_cw_unified_action_2a.py):

1. 溢出腿落地:入位卡补进黑板 bench 回占卖出槽、free_bench_slots 不 +1
   (缺镜像 = 决策面假空席,席满拒落类门被假象绕过);同帧断言执行账
   吸收 = 锁调用点 session 透传这根线(kernel 直调测试覆盖不到);
2. 镜像不误发:陈旧提案(卖出槽容器已空)→ 写口零写、旗标不清 →
   镜像判定(写前旗标 ∧ 写后旗标已清)不触发,free 照常 +1。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_exec_state import (
    BenchChar,
    bench_from_compact,
    exec_state_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    board_state_of,
    bench_view_of_slots,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PrepObservation,
    SellBench,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')


def _seed(session, *, ov_id: str = '不死途'):
    """容器 bench=[花火@1, 刃@2] + 溢出态 + tracked 初始账(三账同基)。"""
    bs = board_state_of(session)
    bs.write_logic(bs.bench, bench_view_of_slots(
        [BenchChar(slot=1, char_id='花火', star=1),
         BenchChar(slot=2, char_id='刃', star=1)]),
        produced_by='test', sig=_SIG)
    bs.write_logic(bs.gold, 10, produced_by='test', sig=_SIG)
    bs.write_logic(bs.overflow_warning, True, produced_by='test', sig=_SIG)
    bs.write_logic(bs.overflow_card, ov_id, produced_by='test', sig=_SIG)
    exec_state_of(session).tracked_bench_chars = bench_from_compact([
        BenchChar(slot=1, char_id='花火', star=1),
        BenchChar(slot=2, char_id='刃', star=1)])
    return bs


def _stub(session) -> CwScreenPrep:
    """无框架状态的桩宿主(零 IO;_session 供 session 透传线)。"""
    stub = CwScreenPrep.__new__(CwScreenPrep)
    stub._session = lambda: session
    return stub


def test_prep_mirror_backfills_card_and_keeps_free_count():
    """溢出腿落地:黑板帧入位卡回占卖出槽、free 不 +1;调用点 session
    透传 → 执行账 tracked 同帧吸收。"""
    session = StrategySession()
    _seed(session)
    obs = PrepObservation(
        bench_chars=[BenchChar(slot=1, char_id='花火', star=1),
                     BenchChar(slot=2, char_id='刃', star=1)],
        free_bench_slots=7)

    out = CwScreenPrep._project_prep_obs(
        _stub(session), SellBench(slot=1), obs)

    assert sorted((b.slot, b.char_id)
                  for b in out.bench_chars if b is not None) == [
        (1, '不死途'), (2, '刃')]          # 卖出件离席 + 入位卡回占槽 1
    assert out.free_bench_slots == 7       # 不 +1(缺镜像 = 假空席绕过席满门)
    tracked = exec_state_of(session).tracked_bench_chars
    assert [(b.char_id, b.star) for b in tracked if b is not None] == [
        ('不死途', 1), ('刃', 1)]          # 写口调用点透传 session = 执行账吸收


def test_prep_mirror_needs_leg_landed_not_flag_alone():
    """镜像不误发:陈旧提案(卖出槽容器已空)→ 写口零写、旗标不清 →
    镜像判定不触发,free 照常 +1,tracked 零写。"""
    session = StrategySession()
    bs = _seed(session)
    # 陈旧提案:卖出槽 1 容器已空(提案与容器失配,写口守卫零写)
    bs.write_logic(bs.bench, bench_view_of_slots(
        [None, BenchChar(slot=2, char_id='刃', star=1)]),
        produced_by='test', sig=_SIG)
    obs = PrepObservation(
        bench_chars=[BenchChar(slot=2, char_id='刃', star=1)],
        free_bench_slots=7)

    out = CwScreenPrep._project_prep_obs(
        _stub(session), SellBench(slot=1), obs)

    assert [(b.slot, b.char_id) for b in out.bench_chars] == [(2, '刃')]
    assert out.free_bench_slots == 8       # 腿未落地 → 常规腿 +1(镜像不误发)
    assert bs.overflow_warning.value is True    # 旗标未消费(写口零写)
    tracked = exec_state_of(session).tracked_bench_chars
    assert [(b.char_id, b.star) for b in tracked if b is not None] == [
        ('花火', 1), ('刃', 1)]            # 执行账零写
