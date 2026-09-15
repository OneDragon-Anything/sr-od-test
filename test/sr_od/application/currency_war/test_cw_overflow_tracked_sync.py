"""T-227 溢出腿执行账吸收回归锁(2026-09-11 实机 2-4 停机事故)。

事故形态:T-226 溢出腿(apply_prep_action_logic)把入位卡写进容器 bench,
执行侧 tracked 主账未吸收 → 商店 visit 入口两账结构性分叉粘性不可自愈
(店开 0n 分发路径(visit_open_shop→run_buy_waves)不经过 director
heavy 观察,reconcile_tracking 唯一生产写点;read_game_state 漏斗
prep_shop_open 阶段设计上不读 bench 身份)→ 崩溃循环停机。
(原「种子守卫 AssertionError」表述随 T-268 守卫退役改写:分叉检出
现归观察边界 reconcile 纠漂,本锁锁的吸收行为本体不变。)

锁的四件事:
1. 溢出腿落地(session 在场):tracked 主账同帧吸收入位卡,槽位/身份
   与容器腿同源;
2. 执行器摘除腿先行的生产时序(tracked 已缺卖件、形态紧缩)同样成立
   (吸收按槽号重建槽位表,对紧缩/缺件输入鲁棒);
3. session 缺席(旧调用形态)= tracked 零写(离线/兼容行为零变化);
4. 身份缺读('')= 容器跳过入位,tracked 同样零写(对称跳过)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_exec_state import (
    BenchChar,
    bench_from_compact,
    exec_state_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    apply_prep_action_logic,
    bench_slots_of,
    bench_view_of_slots,
    board_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    SellBench,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')


def _seed(session, tracked, *, ov_id: str = '不死途'):
    """容器 bench=[花火@1, 刃@2] + 溢出态写入 + tracked 初始账。"""
    bs = board_state_of(session)
    bs.write_logic(bs.bench, bench_view_of_slots(
        [BenchChar(slot=1, char_id='花火', star=1),
         BenchChar(slot=2, char_id='刃', star=1)]),
        produced_by='test', sig=_SIG)
    bs.write_logic(bs.gold, 10, produced_by='test', sig=_SIG)
    bs.write_logic(bs.overflow_warning, True, produced_by='test', sig=_SIG)
    bs.write_logic(bs.overflow_card, ov_id, produced_by='test', sig=_SIG)
    exec_state_of(session).tracked_bench_chars = tracked
    return bs


def test_overflow_absorb_syncs_tracked():
    """溢出腿落地 → tracked 吸收入位卡,槽位/身份与容器腿同源。"""
    session = StrategySession()
    bs = _seed(session, bench_from_compact([
        BenchChar(slot=1, char_id='花火', star=1),
        BenchChar(slot=2, char_id='刃', star=1)]))

    apply_prep_action_logic(bs, SellBench(bench_idx=0), produced_by='test',
                            sig=_SIG, session=session)

    tracked = exec_state_of(session).tracked_bench_chars
    assert [(b.char_id, b.star) for b in tracked if b is not None] == [
        ('不死途', 1), ('刃', 1)]
    assert tracked[0] is not None and tracked[0].slot == 1   # 被卖槽回占
    # 吸收锁(事故本形):容器腿与 tracked 腿同槽同身份。
    assert [(b.char_id, b.star) for b in
            bench_slots_of(bs) if b is not None] == [
        ('不死途', 1), ('刃', 1)]


def test_overflow_absorb_after_executor_removal_compact_shape():
    """生产时序:执行器摘除腿先行(tracked 紧缩缺卖件)→ 吸收按槽号
    重建槽位表,存件不丢、不串槽。"""
    session = StrategySession()
    bs = _seed(session, [BenchChar(slot=2, char_id='刃', star=1)])  # 花火已被摘

    apply_prep_action_logic(bs, SellBench(bench_idx=0), produced_by='test',
                            sig=_SIG, session=session)

    tracked = exec_state_of(session).tracked_bench_chars
    assert [(b.char_id, b.star) for b in tracked if b is not None] == [
        ('不死途', 1), ('刃', 1)]
    assert tracked[1] is not None and tracked[1].char_id == '刃'   # 刃 仍在槽 2


def test_overflow_no_session_keeps_tracked_untouched():
    """session 缺席(旧调用形态)= tracked 零写(兼容行为零变化)。"""
    session = StrategySession()
    bs = _seed(session, bench_from_compact([
        BenchChar(slot=1, char_id='花火', star=1),
        BenchChar(slot=2, char_id='刃', star=1)]))

    apply_prep_action_logic(bs, SellBench(bench_idx=0), produced_by='test',
                            sig=_SIG)

    after = exec_state_of(session).tracked_bench_chars
    assert [(b.char_id, b.star) for b in after if b is not None] == [
        ('花火', 1), ('刃', 1)]


def test_overflow_missing_identity_skips_tracked_absorb():
    """身份缺读('')= 容器跳过入位,tracked 同样零写(对称跳过)。"""
    session = StrategySession()
    bs = _seed(session, bench_from_compact([
        BenchChar(slot=1, char_id='花火', star=1),
        BenchChar(slot=2, char_id='刃', star=1)]), ov_id='')

    apply_prep_action_logic(bs, SellBench(bench_idx=0), produced_by='test',
                            sig=_SIG, session=session)

    after = exec_state_of(session).tracked_bench_chars
    assert [(b.char_id, b.star) for b in after if b is not None] == [
        ('花火', 1), ('刃', 1)]
