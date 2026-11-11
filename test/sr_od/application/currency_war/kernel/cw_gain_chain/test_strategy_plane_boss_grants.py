"""策略位面-节点合取条件写状态副本发放检查效果条目测试(镜像 src = kernel/cw_gain_chain.py
的 ``check_strategy_plane_boss_grants``;分方法拆目录规范落位,新函数落
拆目录新文件,先例 = 同目录 check_strategy_* 族镜像文件)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§4 锁 2/锁 3
+ 裁决点全部默认案(对抗 2 轮收敛)。卡面官方原文(cw_invest_data.py
352401 行逐字):「进入第二位面的首领节点时，获得一个穿着2个【动能激发剑】
和【列车同行星徽】的【火花】和1个【开拓者】。」

- 触发矩阵锁:P2 boss 窗持卡 → 备战 1★火花(placed)+ 封账恰一笔
  (穿戴效果条目/开拓者效果条目零建模 = 落席仅火花一名);非 boss 窗/P1、P3 boss 窗/
  未持卡 → 零写;已置一次性标志位 → 短路;bench 未观察 → 零写不落一次性标志位;
- 修饰免疫锁:人身意外险修饰局 node_seq_by_plane 场字段下 P2-8 boss 窗
  照常触发(kind 函数内现读,坐标不钉死;同局 (2,7) 已变 supply 位零写)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    STRATEGY_GIFT_LEG_P2_BOSS,
    check_strategy_plane_boss_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    bench_units_of,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    resolve_plane_node_seqs,
)

_CARD = '盗用身份'
_CHAR = '火花'
_LATCH = f'{_CARD}#{STRATEGY_GIFT_LEG_P2_BOSS}'

_SIG_OBS = ChannelSig(family='obs', actor='TestPlaneBossGrants')
_LSIG = ChannelSig(family='logic_action', actor='TestPlaneBossGrants',
                   mode='compute')


def _gs(*, cards: list[str] | None = None,
        bench: list[tuple[str, int]] | None = None,
        seqs: dict[int, tuple[str, ...]] | None = None) -> GameState:
    """直构状态容器(cards=None = 未持卡;bench=None = 保持未观察,供宁缺勿造
    防御支;seqs=None = 场字段未注册,node_sequence_of 回退默认表)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if cards is not None:
        gs.write_logic(gs.active_strategies, list(cards),
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=n, star=s))
                 for n, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9),
                   sig=_SIG_OBS)
    if seqs is not None:
        gs.write_logic(gs.node_seq_by_plane, seqs,
                       produced_by='test-seed', evidence='t:seq',
                       sig=_LSIG)
    return gs


def _units(gs: GameState) -> list[tuple[str, int]]:
    return [(u.char_id, u.star) for u in bench_units_of(gs)]


def test_p2_boss_window_grants_with_latch() -> None:
    """主锁:持卡 + P2-7 boss 窗(默认序列,场字段未注册回退)→ 备战
    1★火花 + 封账恰一笔(星级未标 1★ 先验;穿戴/开拓者两条效果条目零建模 =
    落席仅火花)。"""
    gs = _gs(cards=[_CARD], bench=[])
    got = check_strategy_plane_boss_grants(gs, node_pos=(2, 7), sig=_LSIG)
    assert got == _CHAR, '返回发放角色名'
    assert _units(gs) == [(_CHAR, 1)], '备战恰 1 名 1★火花(placed)'
    assert gs.strategy_grants_done.value == (_LATCH,), '封账恰一笔'


def test_replay_and_latched_zero_write() -> None:
    """幂等:同窗重放零双发(已置一次性标志位短路,零写零追加;板面维持持卡亦不再发)。"""
    gs = _gs(cards=[_CARD], bench=[])
    check_strategy_plane_boss_grants(gs, node_pos=(2, 7), sig=_LSIG)
    seq0 = gs.write_seq
    got = check_strategy_plane_boss_grants(gs, node_pos=(2, 7), sig=_LSIG)
    assert got is None, '一次性标志位后短路'
    assert gs.write_seq == seq0, '重放零写'
    assert _units(gs) == [(_CHAR, 1)], '火花不双发'
    assert gs.strategy_grants_done.value == (_LATCH,), '封账不追加'


def test_non_boss_and_other_plane_windows_zero_write() -> None:
    """合取门控:非 boss 窗(2,3 = supply)/P1 boss 窗 (1,9)/P3 boss 窗
    (3,7) → 零写零一次性标志位(位面-节点类型合取直判,零坐标猜测)。"""
    for pos in ((2, 3), (1, 9), (3, 7)):
        gs = _gs(cards=[_CARD], bench=[])
        seq0 = gs.write_seq
        got = check_strategy_plane_boss_grants(gs, node_pos=pos, sig=_LSIG)
        assert got is None and gs.write_seq == seq0, f'{pos}: 零写'
        assert gs.strategy_grants_done.value in (None, ()), f'{pos}: 不落一次性标志位'


def test_no_card_and_bench_unobserved_zero_write() -> None:
    """负锁:未持卡零写(白名单表外零消费);bench 未观察 → 零写不落一次性标志位
    (宁缺勿造,check_env_boss_grants 同款防御)。"""
    gs = _gs(bench=[])
    seq0 = gs.write_seq
    got = check_strategy_plane_boss_grants(gs, node_pos=(2, 7), sig=_LSIG)
    assert got is None and gs.write_seq == seq0, '未持卡零写'
    assert gs.strategy_grants_done.value in (None,)
    gs2 = _gs(cards=[_CARD])
    seq1 = gs2.write_seq
    got2 = check_strategy_plane_boss_grants(gs2, node_pos=(2, 7), sig=_LSIG)
    assert got2 is None and gs2.write_seq == seq1, 'bench 未观察零写'
    assert gs2.strategy_grants_done.value in (None, ()), '不标一次性标志位'


def test_modified_schedule_plane_immunity() -> None:
    """修饰免疫锁:人身意外险修饰局(P2 = 8 节点,boss 后移至 (2,8))
    场字段现值下 P2-8 boss 窗照常触发;同局 (2,7) = 插入补给位零写
    (默认序列下 (2,7) 恰是 boss——kind 现读而非坐标钉死的正反双证)。"""
    seqs = resolve_plane_node_seqs('人身意外险')
    gs = _gs(cards=[_CARD], bench=[], seqs=seqs)
    got = check_strategy_plane_boss_grants(gs, node_pos=(2, 8), sig=_LSIG)
    assert got == _CHAR, '修饰局 P2-8 boss 窗触发'
    assert _units(gs) == [(_CHAR, 1)], '修饰局发放落席'
    assert gs.strategy_grants_done.value == (_LATCH,), '修饰局封账'
    gs2 = _gs(cards=[_CARD], bench=[], seqs=seqs)
    seq0 = gs2.write_seq
    got2 = check_strategy_plane_boss_grants(gs2, node_pos=(2, 7), sig=_LSIG)
    assert got2 is None and gs2.write_seq == seq0, '修饰局 (2,7)=supply 零写'
    assert gs2.strategy_grants_done.value in (None, ())
