"""经济循环总模型(ADR-0445)单帧锁:储备制 R*/义务/通道容量。

设计=唯一规格:`.debug/temp/currency_war/w471_economy_cycle/DESIGN.md`
(W481 审计修复项 A-1/A-2 内建)。锁契约(不锁分布数值):
- A·R*:无排程=息线;窗口(≤3 轮)内排程升级帧=息线+升级费(费用表
  本地复算);h=0(位面末)不储蓄;
- A·义务:义务=min(溢余, C_t),溢余>容量被容量封顶(结转语义);
- A·C_t(A-1/A-2):未跨档期权件不计容量;当帧跨档件(买入后四体系
  达成数 +1,结构性判定)计入;3合1 合成件计入;bench 满槽时非合成
  件不计(A-2 槽位机会成本)。
(原同文件 B 侧锁已随 ADR-0446 退回删除:合并 A/B 实测 B 在义务帧
辖域内结构性零活性,裁决与归因见该 ADR rejected 版与
.debug/temp/currency_war/w482_merged_ab/REPORT.md。)
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_horizon import (
    Posture,
    level_cost,
)
from sr_od.application.currency_war.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.economy_cycle import (
    channel_capacity,
    obligation,
    reserve_cap,
)
from sr_od.application.currency_war.decision_v2.ev import RoundPosture
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY


def _state(*, gold: int = 80, plane: int = 1, r: int = 3, level: int = 6,
           deployed: list[BenchChar] | None = None,
           bench: list[BenchChar | None] | None = None,
           shop: list[ShopCard] | None = None,
           board: dict | None = None,
           hp: int = 80) -> GameState:
    return GameState(
        plane=plane, round_num=r, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2,
        deployed=deployed if deployed is not None else [],
        bench=bench if bench is not None else [None] * BENCH_CAPACITY,
        shop=shop if shop is not None else [], node_type='battle',
        board=board or {})


def _ch(name: str, slot: int, star: int = 1) -> BenchChar:
    from sr_od.application.currency_war.cw_chars import CHARACTERS
    fac = (CHARACTERS[name].factions or ('?',))[0]
    return BenchChar(slot=slot, char_id=name, faction=fac, star=star)


def _sc(name: str, cost: int = 2) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


#: 非过渡体系填充件名(真实注册表名;杂名会 KeyError)
_FILLERS = ('阿格莱雅', '乱破', '大丽花', '黑塔', '飞霄', '加拉赫',
            '娜塔莎', '赛飞儿', '翡翠', '刃', '貊泽')


def _filler(i: int, slot: int | None = None) -> BenchChar:
    return _ch(_FILLERS[i % len(_FILLERS)],
               slot if slot is not None else i)


def _sess(state: GameState, *, level_up: bool = False,
          refresh_budget: int = 0) -> StrategySession:
    s = StrategySession()
    s.v3_dp_posture = RoundPosture(
        (state.plane, state.round_num),
        Posture(save=False, level_up=level_up, refresh_budget=refresh_budget))
    return s


# --- A·R* 储备线 ---------------------------------------------------------------


def test_reserve_cap_no_schedule_equals_interest_floor() -> None:
    """无排程升级帧:R* = 息线 50(息线以内持有弱占优,储备主体)。"""
    st = _state()
    assert reserve_cap(st, _sess(st), _REG) == 50


def test_reserve_cap_schedules_upgrade_fee_in_window() -> None:
    """窗口内排程升级帧:R* = 息线 + 下一级升级费(费用=clicks×单价,
    期望值=level_cost 常量表本地复算;排程储蓄不是死钱,设计 §1.3)。"""
    st = _state(r=5)
    assert reserve_cap(st, _sess(st, level_up=True), _REG) \
        == 50 + level_cost(6)


def test_reserve_cap_no_saving_at_plane_end() -> None:
    """h=0(位面末窗):排程升级不储蓄——>3 轮外的升级应即时执行而非
    长期储蓄(窗口上界=结构界)。"""
    st = _state(r=9)
    assert reserve_cap(st, _sess(st, level_up=True), _REG) == 50


# --- A·义务与容量 --------------------------------------------------------------


def test_obligation_capped_by_capacity() -> None:
    """义务=min(溢余, C_t):溢余 30 > 容量 → 义务=容量(结转余量;
    容量外余量进评估罚项,不一步到位假达标,设计 §1.4-3)。"""
    st = _state(gold=80)   # 溢余 30
    s = _sess(st, refresh_budget=3)   # 容量=3×2=6(店空)
    assert channel_capacity(st, s, _REG) == 6
    assert obligation(st, s, _REG) == 6


def test_obligation_full_within_capacity() -> None:
    """(g−R*)+ ≤ C_t:义务=溢余全额,本轮清零死钱。"""
    st = _state(gold=56)
    s = _sess(st, refresh_budget=6)   # 容量 12 ≥ 溢余 6
    assert obligation(st, s, _REG) == 6


def test_capacity_excludes_option_pieces() -> None:
    """A-1 修复锁(W611 重推):未跨档期权件的容量禁令辖域=满槽帧——
    期权泵死法(W469:义务泵把死钱流向无槽可放的期权件)的防线是
    「槽位约束」;备战有空位帧,未跨档件改按 O1 填补通道计入
    (bench_fill_account,用户 directive:无目标也填满备战;
    .debug/temp/currency_war/w611_econ_cycle/DESIGN.md §4 判据 6)。
    当帧跨档件(买入后四体系达成数 +1,结构性判定)照旧计入。"""
    st = _state(board={})                       # 无体系进度:任何件不跨档
    st.shop = [_sc('桑博', 1)]
    s = _sess(st)
    assert channel_capacity(st, s, _REG) == 1    # 空槽帧:O1 填补通道计入
    st.bench = [_filler(i) for i in range(BENCH_CAPACITY)]   # 满槽
    assert channel_capacity(st, s, _REG) == 0    # A-1/A-2:满槽 → 0
    st.bench = [None] * BENCH_CAPACITY           # 恢复空槽
    st.shop = [_sc('丹恒·饮月', 2)]              # board 仙舟=2,买入跨档
    st.board = {'仙舟': 2}
    assert channel_capacity(st, s, _REG) == 2


def test_capacity_charges_bench_slot_opportunity_cost() -> None:
    """A-2 修复锁:bench 满槽时非合成件不计容量(槽位是下一轮跨档件的
    物理前置)。"""
    st = _state(board={'仙舟': 2},
                bench=[_filler(i) for i in range(BENCH_CAPACITY)])
    st.shop = [_sc('丹恒·饮月', 2)]   # 买入跨档但 bench 满
    s = _sess(st)
    assert channel_capacity(st, s, _REG) == 0   # 满槽 → 0


def test_capacity_counts_merge_completion() -> None:
    """3合1 合成件(买入即 2★ 完成)计入容量且不受 bench 槽约束。"""
    bench = [_ch('桑博', 0), _ch('桑博', 1)] \
        + [_filler(i) for i in range(2, BENCH_CAPACITY)]
    st = _state(bench=bench)   # bench 满
    st.shop = [_sc('桑博', 1)]   # 第三张:合成 2★
    s = _sess(st)
    assert channel_capacity(st, s, _REG) == 1
