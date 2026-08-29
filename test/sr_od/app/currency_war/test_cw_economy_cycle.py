"""经济循环总模型(ADR-0445)单帧锁:储备制 R*/义务/通道容量。

设计=唯一规格:`.debug/temp/currency_war/w471_economy_cycle/DESIGN.md`
(W481 审计修复项 A-1/A-2 内建)。批 3 预算收权重推:排程/刷新预算
供给换确定性核(schedule_upgrade/refresh_ev_budget 单一址),注入式
posture 锁面退役——排程语义 = 意向核心峰值级(绯英 2 费峰值 6)+ 息
引擎前置;刷新预算 = min(6, ⌊(g−R*)/刷价⌋)(只花溢余)。锁契约
(不锁分布数值):
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

from sr_od.application.currency_war.cw_economy import (
    reserve_cap,
)
from sr_od.application.currency_war.cw_plane_table import level_cost
from sr_od.application.currency_war.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.economy_cycle import (
    bench_fill_account,
    channel_capacity,
    obligation,
)
from sr_od.application.currency_war.kernel.cw_registry import (
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


def _sess(state: GameState) -> StrategySession:
    """裸 session(排程/预算 = 确定性核按 state 现算;注入面退役)。

    注:裸 session 无位面表 → nodes_of_plane 先验 9(一次性告警即
    记档通道);默认 level=6 已达兜底核心(绯英 2 费)峰值级 → 无排程。
    """
    return StrategySession()


# --- A·R* 储备线 ---------------------------------------------------------------


def test_reserve_cap_no_schedule_equals_interest_floor() -> None:
    """无排程升级帧:R* = 息线 50(息线以内持有弱占优,储备主体;
    默认帧 level=6 = 兜底核心峰值级 → 排程判据 False,预告态不虚触发)。"""
    st = _state()
    assert reserve_cap(st, _sess(st), _REG) == 50


def test_reserve_cap_schedules_upgrade_fee_in_window() -> None:
    """窗口内排程升级帧:R* = 息线 + 下一级升级费(费用=clicks×单价,
    期望值=level_cost 常量表本地复算;排程储蓄不是死钱,设计 §1.3)。
    level=5 < 峰值级 6(绯英 2 费)∧ 息引擎已立(gold 80≥50)→ 排程。"""
    st = _state(r=5, level=5)
    assert reserve_cap(st, _sess(st), _REG) \
        == 50 + level_cost(5)


def test_reserve_cap_no_saving_at_plane_end() -> None:
    """h=0(位面末窗):排程升级不储蓄——>3 轮外的升级应即时执行而非
    长期储蓄(窗口上界=结构界)。"""
    st = _state(r=9, level=5)
    assert reserve_cap(st, _sess(st), _REG) == 50


def test_reserve_cap_predictive_below_fee_affordability() -> None:
    """批 3 预告态契约锁(W623 D1):排程不以当帧可负担为前置——
    gold=55(远不够升级费)∧ 峰值级未达 → 排程照发、R* 计入升级费。
    「付不起就不排」会造成 R* 塌缩→义务花光→更排不上的贫穷循环;
    付不付得起是执行层(ev.levelup_ev_basis 可负担性入口门)的事。"""
    st = _state(gold=55, r=5, level=5)
    assert reserve_cap(st, _sess(st), _REG) == 50 + level_cost(5)


# --- A·义务与容量 --------------------------------------------------------------


def test_obligation_capped_by_capacity() -> None:
    """义务=min(溢余, C_t):溢余 30 > 容量 → 义务=容量(结转余量;
    容量外余量进评估罚项,不一步到位假达标,设计 §1.4-3)。
    容量 = 刷新预算分量 min(6, 30//2)=6 刷 ×2 金 =12(店空)。"""
    st = _state(gold=80)   # 溢余 30
    s = _sess(st)
    assert channel_capacity(st, s, _REG) == 12
    assert obligation(st, s, _REG) == 12


def test_obligation_full_within_capacity() -> None:
    """(g−R*)+ ≤ C_t:义务=溢余全额,本轮清零死钱。
    gold 56 → 溢余 6 → 预算 3 刷=容量 6 ≥ 溢余。"""
    st = _state(gold=56)
    s = _sess(st)
    assert obligation(st, s, _REG) == 6


def test_capacity_excludes_option_pieces() -> None:
    """A-1 修复锁(W611 重推):未跨档期权件的容量禁令辖域=满槽帧——
    期权泵死法(W469:义务泵把死钱流向无槽可放的期权件)的防线是
    「槽位约束」;备战有空位帧,未跨档件改按 O1 填补通道计入
    (bench_fill_account,用户 directive:无目标也填满备战;
    .debug/temp/currency_war/w611_econ_cycle/DESIGN.md §4 判据 6)。
    当帧跨档件(买入后四体系达成数 +1,结构性判定)照旧计入。
    gold=50(g=R*):溢余 0 → 刷新分量 0,容量只剩店内账(隔离槽位逻辑)。"""
    st = _state(gold=50, board={})              # 无体系进度:任何件不跨档
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
    物理前置)。gold=50 同上隔离刷新分量。"""
    st = _state(gold=50, board={'仙舟': 2},
                bench=[_filler(i) for i in range(BENCH_CAPACITY)])
    st.shop = [_sc('丹恒·饮月', 2)]   # 买入跨档但 bench 满
    s = _sess(st)
    assert bench_fill_account(st, _REG) == 0
    assert channel_capacity(st, s, _REG) == 0   # 满槽 → 0


def test_capacity_counts_merge_completion() -> None:
    """3合1 合成件(买入即 2★ 完成)计入容量且不受 bench 槽约束。
    gold=50 隔离刷新分量。"""
    bench = [_ch('桑博', 0), _ch('桑博', 1)] \
        + [_filler(i) for i in range(2, BENCH_CAPACITY)]
    st = _state(gold=50, bench=bench)   # bench 满
    st.shop = [_sc('桑博', 1)]   # 第三张:合成 2★
    s = _sess(st)
    assert channel_capacity(st, s, _REG) == 1
