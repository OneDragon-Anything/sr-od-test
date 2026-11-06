"""策略卡备战席条件离场金检查腿测试(镜像 src = kernel/cw_gain_chain.py 的
check_strategy_bench_leave_gold 纯判定 + sim/cw_sim_backend.py 节点窗调用点
唯一调用口)。

测试面依据 = 迭代设计 designs/T-292-yuzhe-ezuoju.md(定稿)§4 锁 2 +
REVIEW-T292 §四④(卡面官方原文:「进入新节点时，备战席的1星【花火】/
【火花】会留下2/4金币并去别处找乐子。」;直构形态先例 = 同目录
test_check_strategy_bench_count_xp.py):
- 计划矩阵(锁 2):持卡+1星花火→[(槽,花火,2)];+1星火花→[(槽,火花,4)];
  双匹配→两条;2星花火/火花→空(星轴豁免);上阵位花火→空(desc「备战席」
  文义);未持卡/表外卡→空;bench 未观察(None)→空;占位件槽→空
  (辖域判别用例——占位件非「角色」);
- 槽位序 = BenchView.slots 0 基下标(离场写端定位坐标系);
- 纯读零写:函数体零容器写(判定无 sig 形参,世界写端归 sim 调用点)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_bench_leave_gold,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)

_CARD = '愚者恶作剧'

_SIG_OBS = ChannelSig(family='obs', actor='TestBenchLeave')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='test-seed',
                        mode='compute')


def _gs(*, card: str | None = _CARD,
        bench: list[BenchSlot] | None = None,
        deployed: DeployedView | None = None) -> GameState:
    """直构容器(card=None = 未持卡;'躺平' = 表外卡;bench 传 None =
    保持未观察供 None 防御支;传列表 = pad 成 9 槽 BenchView)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card',
                       sig=_SIG_LOGIC)
    if bench is not None:
        slots = list(bench) + [BenchSlot(kind='empty')] * (9 - len(bench))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9),
                   sig=_SIG_OBS)
    if deployed is not None:
        gs.observe(gs.deployed, deployed, sig=_SIG_OBS)
    return gs


def _unit(char_id: str, star: int = 1) -> BenchSlot:
    """备战席单位槽。"""
    return BenchSlot(kind='unit',
                     unit=Unit(char_id=char_id, star=star, equips=[]))


def test_one_star_huohuo_leaves_two_gold() -> None:
    """1星花火(锁 2 主条):持卡+席内 1星花火 → [(槽位序,'花火',2)]
    (desc「1星【花火】会留下2金币」)。"""
    gs = _gs(bench=[_unit('花火')])
    assert check_strategy_bench_leave_gold(gs) == [(0, '花火', 2)]


def test_one_star_huohua_leaves_four_gold() -> None:
    """1星火花(锁 2):持卡+席内 1星火花 → [(槽位序,'火花',4)]
    (金与费用档平行)。"""
    gs = _gs(bench=[_unit('火花')])
    assert check_strategy_bench_leave_gold(gs) == [(0, '火花', 4)]


def test_both_matched_two_rows_slot_index_kept() -> None:
    """双匹配(锁 2):花火+火花同席 → 两条计划,各带各自槽位序与金额
    (中间空槽不打断下标——计划下标 = BenchView.slots 物理位,非紧缩序)。"""
    gs = _gs(bench=[
        _unit('花火'),
        BenchSlot(kind='empty'),
        _unit('火花'),
    ])
    assert check_strategy_bench_leave_gold(gs) == [
        (0, '花火', 2), (2, '火花', 4)]


def test_two_star_exempt() -> None:
    """2星豁免(锁 2):2星花火/2星火花 → 空(仅 star==1 触发,desc 明写;
    2星单位永久在场)。"""
    gs = _gs(bench=[_unit('花火', star=2), _unit('火花', star=2)])
    assert check_strategy_bench_leave_gold(gs) == []


def test_deployed_huohuo_not_in_scope() -> None:
    """上阵位不辖(锁 2,裁决点 4 判别):deployed 前排 1星花火 + bench 空
    → 空(desc「备战席」文义直读,上阵位不在离场域)。"""
    gs = _gs(
        bench=[],
        deployed=DeployedView(
            front_slots=[Unit(char_id='花火', star=1, equips=[]),
                         None, None, None],
            back_slots=[None] * 6))
    assert check_strategy_bench_leave_gold(gs) == []


def test_placeholder_slots_only_empty() -> None:
    """仅占位件槽(锁 2,辖域判别用例):supply_box/bookcard 槽占席但非
    「角色」→ 空(占位件不计,若翻「占席条目计入」读法本锁先红)。"""
    gs = _gs(bench=[
        BenchSlot(kind='supply_box', item='简易武装箱'),
        BenchSlot(kind='bookcard', item='专家邀请函'),
    ])
    assert check_strategy_bench_leave_gold(gs) == []


def test_bench_unobserved_fail_closed() -> None:
    """bench 未观察防御(锁 2 序 1):fail-closed → [](禁沿 bench_units_of
    空席缺省语义误判「席空恒无匹配」——未观察 = 无法判定,宁可漏发)。"""
    assert check_strategy_bench_leave_gold(_gs()) == []


def test_strategies_unobserved_fail_closed() -> None:
    """策略集未观察防御(锁 2 序 1):fail-closed → []。"""
    gs = _gs(card=None, bench=[_unit('花火')])
    assert check_strategy_bench_leave_gold(gs) == []


def test_no_card_and_off_table_empty() -> None:
    """未持卡/表外卡零命中(锁 2 序 2):双空也零计划(白名单表外禁从效果
    原文自动猜装)。"""
    for card in (None, '躺平'):
        gs = _gs(card=card, bench=[_unit('花火')])
        assert check_strategy_bench_leave_gold(gs) == [], f'{card}: 零命中'


def test_pure_read_zero_container_writes() -> None:
    """纯读零写(形态 A):命中路径零容器写(判定无 sig 形参零世界写,
    世界写端 = sim 唯一调用点)。"""
    gs = _gs(bench=[_unit('花火')])
    seq0 = gs.write_seq
    assert check_strategy_bench_leave_gold(gs) == [(0, '花火', 2)]
    assert gs.write_seq == seq0, '判定零写'
