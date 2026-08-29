"""W611 存息准入门 + O1 备战空位容量 单帧锁。

设计=唯一规格:`.debug/temp/currency_war/w611_econ_cycle/DESIGN.md`
(架构基座=ADR-0445 经济循环总模型;本批只扩通道与姿态准入,不推倒)。
锁契约(不锁分布数值):
- O1 容量:备战空位帧,店内非跨档非合成件计入 C_t(W611 §1.2/§1.3:
  溢余段买 1★ 退全款+息帽截断 → 弱占优、参数无关);跨档件与填补件
  共享同一份槽位账(A-2 不双计);满槽帧填补计 0(A-1/A-2 原样);
- E1 存息准入门:g>R* 帧存息姿态(level_up/D 预算全空)非法 → 零预算
  release 指令(tag='release',局23 型「interest 标签死守」帧消失;
  预算=0=容量不足的合法结转,authorize 恒拒);
- 辖域边界:g≤R* 零漂移(义务/准入门都不辖);应急帧让位(保血域,
  ADR-0426 辖区不相交);DP 行动姿态(升级/D)不经准入门;
- 守息线≡封顶线:R* 的息线分量 = interest_cap×10(息帽同源派生,
  W611 §2.2 恒等式;基参数 5×10=50==interest_floor 零漂移)。
病灶锚:局23(run_20260829_130420)g=100+备战空+spend_mode='interest'
死守 —— 锁 1/锁 4 分别钉「有容量帧义务开工」与「无容量帧标签诚实」。
"""
from __future__ import annotations

from sr_od.application.currency_war.decision_v2.posture import Posture
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
    reserve_cap,
)
from sr_od.application.currency_war.decision_v2.ev import RoundPosture
from sr_od.application.currency_war.decision_v2.posture_release import (
    authorize_release_refresh,
    release_directive,
    wrap_posture,
)
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


def _sc(name: str, cost: int = 2) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


def _sess(state: GameState, *, level_up: bool = False,
          refresh_budget: int = 0) -> StrategySession:
    s = StrategySession()
    s.v3_dp_posture = RoundPosture(
        (state.plane, state.round_num),
        Posture(save=False, level_up=level_up, refresh_budget=refresh_budget))
    return s


def _saving_posture() -> Posture:
    """DP 解出存息的姿态(局23 帧形态:无升级、无 D 预算)。"""
    return Posture(save=True, level_up=False, refresh_budget=0, tag='存息')


def _ch(name: str, slot: int) -> BenchChar:
    from sr_od.application.currency_war.cw_chars import CHARACTERS
    fac = (CHARACTERS[name].factions or ('?',))[0]
    return BenchChar(slot=slot, char_id=name, faction=fac, star=1)


def _full_bench() -> list[BenchChar]:
    return [_ch('阿格莱雅', i) for i in range(BENCH_CAPACITY)]


# --- O1 · 备战空位填补容量(W611 §1.2/§1.3)------------------------------


def test_bench_fill_capacity_unlocks_obligation_in_targetless_frame() -> None:
    """锁 1·局23 型帧(comp 空+备战空):填补件计入容量 → 义务开工。
    病灶机制=无目标帧正 EV 帧空 → C_t=0 → 义务恒 0(三次复发根);
    O1 后 g=100、店有 2 费件 → 填补账=2;容量另含刷新预算分量
    (批 3 预算收权:min(6,⌊50/2⌋)=6 刷×2=12)→ 容量 14;义务=min(50,14)
    =14,flip 预算=max(义务, 排程预算×刷价)=14。"""
    st = _state(gold=100, shop=[_sc('桑博', 2)], board={})
    s = _sess(st)
    assert bench_fill_account(st, _REG) == 2
    assert channel_capacity(st, s, _REG) == 14
    assert obligation(st, s, _REG) == 14
    d = release_directive(st, s, _REG, 'FORM', _saving_posture())
    assert d is not None and d.reason == 'flip' and d.budget_gold == 14
    assert wrap_posture(_saving_posture(), d).tag == 'release'


def test_fill_and_crossing_share_one_slot_account() -> None:
    """锁 2·槽位账单源唯一:跨档件(countable)与填补件(fill)共享
    同一份空槽——2 空槽时两路并计、1 空槽时跨档件占槽后填补计 0
    (A-2 槽位机会成本在两路间不双计)。"""
    st = _state(gold=80, board={'仙舟': 2},
                shop=[_sc('丹恒·饮月', 2), _sc('桑博', 1)])
    s = _sess(st)
    # 容量 15 = 刷新预算 6 刷×2 + 跨档 2 + 填补 1(两空槽;批 3 加刷新分量)
    assert channel_capacity(st, s, _REG) == 15
    st.bench = _full_bench()[:8] + [None]       # 仅 1 空槽(bench 占用数口径)
    assert channel_capacity(st, s, _REG) == 14  # 槽被跨档件占用,填补=0


def test_fill_zero_when_bench_full_a1_a2_preserved() -> None:
    """A-1/A-2 原样:满槽帧非合成件不计容量(期权泵死法 W469 的防线上
    移为「槽位约束」,不是废除——义务不把金推进无槽可放的件)。"""
    st = _state(gold=100, bench=_full_bench(),
                shop=[_sc('桑博', 2)], board={})
    assert bench_fill_account(st, _REG) == 0


# --- E1 · 存息准入门(W611 §2.1)------------------------------------------


def test_admission_zero_capacity_frame_carry_label_honest() -> None:
    """锁 4·无对象结转帧(g>R*,bench 满,店无跨档件):义务=0 但存息
    非法 → 零预算 release 指令,标签诚实(tag='release'),authorize
    恒拒 = 容量不足的合法结转(量=溢余,遥测披露面)。
    批 3 机制口径(W623 D2):刷新预算计入容量后,溢余 ≥ 刷价的帧由
    flip 承接(义务通道有对象);准入门的残余辖域=溢余 < 刷价且无店内
    账的帧——gold 51(溢余 1 < 刷价 2)即此,容量真 0。"""
    st = _state(gold=51, bench=_full_bench(), shop=[_sc('桑博', 1)],
                board={})
    s = _sess(st)
    d = release_directive(st, s, _REG, 'FORM', _saving_posture())
    assert d is not None and d.reason == 'reserve_admission'
    assert d.budget_gold == 0
    assert wrap_posture(_saving_posture(), d).tag == 'release'
    s.v3_release = d
    assert authorize_release_refresh(s, 51, 2, _REG) == ''


def test_action_postures_never_get_admission_reason() -> None:
    """DP 行动姿态(升级)不经准入门——义务只禁存息,不禁 DP 已授权的
    行动;升级帧的溢余花费走 flip 义务预算(reason='flip',升级费已计
    R* 储蓄,溢余段义务=min(溢余,容量)),reason 恒非 'reserve_admission'。"""
    st = _state(gold=100)   # 店空:容量=升级费
    s = _sess(st, level_up=True)
    d = release_directive(st, s, _REG, 'FORM',
                          Posture(save=False, level_up=True,
                                  refresh_budget=0))
    assert d is not None and d.reason == 'flip'
    assert d.budget_gold == obligation(st, s, _REG)


def test_zero_drift_below_reserve_cap() -> None:
    """锁 3·零漂移锚:g≤R* 帧义务=0、准入门不辖(息线以内持有弱占优,
    [2]/[28] 凑息期行为逐字段不变——sim 息基守卫的结构性依据)。"""
    st = _state(gold=30, shop=[_sc('桑博', 2)], board={})
    s = _sess(st)
    assert obligation(st, s, _REG) == 0
    assert release_directive(st, s, _REG, 'FORM', _saving_posture()) is None


def test_emergency_frame_release_yields() -> None:
    """应急帧让位(保血域,辖区不相交):hp≤25 时 flip 与准入门都不辖,
    姿态维持原样(W516 保血域不被义务模型侵入)。"""
    st = _state(gold=100, hp=20, bench=_full_bench(),
                shop=[_sc('桑博', 2)], board={})
    s = _sess(st)
    assert release_directive(st, s, _REG, 'FORM', _saving_posture()) is None


# --- 守息线 ≡ 封顶线(W611 §2.2 恒等式)----------------------------------


def test_reserve_floor_identical_to_interest_cap_line() -> None:
    """锁 6·恒等式:R* 的息线分量 = interest_cap×10(息帽同源派生),
    基参数下 == interest_floor(50)且恒 ≥ 封顶线——「守息线 ≤ 封顶线」
    结构性成立,不依赖两常量手工同步。"""
    st = _state()
    s = _sess(st)
    assert _REG.interest_cap * 10 == _REG.interest_floor()
    assert reserve_cap(st, s, _REG) >= _REG.interest_cap * 10
