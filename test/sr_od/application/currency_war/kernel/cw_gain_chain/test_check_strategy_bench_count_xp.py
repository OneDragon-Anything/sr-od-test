"""策略卡备战席计数经验检查腿测试(镜像 src = kernel/cw_gain_chain.py 的
check_strategy_bench_count_xp 纯判定 + sim/cw_sim_backend.py 节点窗挂点
唯一调用口)。

测试面依据 = 迭代设计 designs/T-192-rencai-kongdong.md(定稿)§4 锁 2 +
REVIEW-T192 §四④(卡面官方原文:「节点开始时，如果备战席角色小于等于
4名，则获得3经验。」;直构形态先例 = 同目录 check_strategy_* 族镜像):
- 谓词矩阵(锁 2):5 units→0;恰 4→3(≤4 边界);0→3;仅占位件槽无
  unit→3(计数口径 A 锚定判别用例——若翻「占位件计入」读法本锁先红);
  bench None→0;active_strategies None→0;未持卡/表外卡→0;
- 'ge' 分支行为归姊妹人才济济批锁,本卡不建;
- 纯读零写:函数体零容器写(判定无 sig 形参,世界写端归 sim 挂点)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_bench_count_xp,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
)

_CARD = '人才空洞'
_XP = 3

_SIG_OBS = ChannelSig(family='obs', actor='TestBenchCount')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='test-seed',
                        mode='compute')


def _gs(*, card: str | None = _CARD,
        bench: list[BenchSlot] | None = None) -> GameState:
    """直构容器(card=None = 未持卡;'躺平' = 表外卡;bench 传 None =
    保持未观察供 None 防御支;传列表 = 按 9 槽 pad 成 BenchView)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card',
                       sig=_SIG_LOGIC)
    if bench is not None:
        slots = list(bench) + [BenchSlot(kind='empty')] * (9 - len(bench))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9),
                   sig=_SIG_OBS)
    return gs


def _unit(char_id: str = '希儿') -> BenchSlot:
    """备战席单位槽(裸角色,计数只看 kind 不看穿戴)。"""
    return BenchSlot(kind='unit',
                     unit=Unit(char_id=char_id, star=1, equips=[]))


def test_five_units_zero() -> None:
    """超门槛(锁 2):bench 5 units → 0(>4 不满足 ≤4)。"""
    gs = _gs(bench=[_unit() for _ in range(5)])
    assert check_strategy_bench_count_xp(gs) == 0


def test_exactly_four_boundary_grants() -> None:
    """恰 4 边界(锁 2):bench 恰 4 units → 表值(「小于等于4名」边界
    含端点;5→0 与 4→3 两锁夹出比较符方向)。"""
    gs = _gs(bench=[_unit() for _ in range(4)])
    assert check_strategy_bench_count_xp(gs) == _XP


def test_zero_units_grants() -> None:
    """零单位(锁 2):裸 bench → 表值(席空 = 0 ≤4,「备战席角色0名」
    仍小于等于 4,文义直读)。"""
    gs = _gs(bench=[])
    assert check_strategy_bench_count_xp(gs) == _XP


def test_placeholder_slots_only_grants_anchor_a() -> None:
    """仅占位件槽(锁 2,计数口径 A 锚定判别用例):supply_box/bookcard
    槽占席但无 unit → 表值——desc「角色」文义直读 + bench_units_of 读口
    docstring 语义(占位件与空槽不计);若翻读法 B(占席条目计入)本锁
    先红(证伪路径 = 实机持占席道具 + 席内单位 ≤4 局 XP 发放观察)。"""
    gs = _gs(bench=[
        BenchSlot(kind='supply_box', item='简易武装箱'),
        BenchSlot(kind='bookcard', item='专家邀请函'),
    ])
    assert check_strategy_bench_count_xp(gs) == _XP


def test_bench_unobserved_fail_closed() -> None:
    """bench 未观察防御(锁 2 序 1):fail-closed → 0——禁沿
    bench_units_of 的空席缺省([])语义,未观察 = 无法计数,宁可漏发。"""
    assert check_strategy_bench_count_xp(_gs()) == 0


def test_strategies_unobserved_fail_closed() -> None:
    """策略集未观察防御(锁 2 序 1):fail-closed → 0。"""
    gs = _gs(card=None)
    gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty')] * 9,
                                   capacity=9), sig=_SIG_OBS)
    assert check_strategy_bench_count_xp(gs) == 0


def test_no_card_and_off_table_zero() -> None:
    """未持卡/表外卡零命中(锁 2):双空也零发放(白名单表外禁从效果
    原文自动猜装)。"""
    for card in (None, '躺平'):
        gs = _gs(card=card, bench=[_unit()])
        assert check_strategy_bench_count_xp(gs) == 0, f'{card}: 零命中'


def test_pure_read_zero_container_writes() -> None:
    """纯读零写(形态 A):命中路径零容器写(判定无 sig 形参零世界写,
    世界写端 = sim 挂点唯一调用口)。"""
    gs = _gs(bench=[_unit()])
    seq0 = gs.write_seq
    assert check_strategy_bench_count_xp(gs) == _XP
    assert gs.write_seq == seq0, '判定零写'
