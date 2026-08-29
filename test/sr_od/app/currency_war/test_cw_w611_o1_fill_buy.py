"""W611 O1 散件买入放行 单帧锁(candidates/scoring/arbiter 三面)。

设计=唯一规格:`.debug/temp/currency_war/w611_econ_cycle/DESIGN.md`
§1.1/§1.2/§4 判据 6(ADR-0463)。锁契约(不锁分布数值):
- 放行域命中:g≥R* ∧ 备战有空位 ∧ 非应急 ∧ 非目标件 → tag=
  'o1_bench_fill' 生成、评 0 中性(义务证明背书)、非正分门豁免语义;
- 逐笔金可行性:花后 <R*(吃排程升级储蓄)被 gold_floor 的 o1 地板
  加深拒;花后 ≥R* 过;
- 其余域原样([31] 限域取代的边界):g≤R* 凑息期 / bench 满 /
  应急帧 / 引擎种子散买断(ADR-0333)——散件一律不生成。
质量序锁:bond_fallback(凑羁绊填充)命中帧不产 o1 标签(填充件
优先于散件,O1 末位语义)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_plane_table import (
    level_cost,
)
from sr_od.application.currency_war.decision.decision_v2.posture import Posture
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import (
    _check_constraint,
)
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.ev import RoundPosture
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import (
    score_candidate,
)

_REG = DEFAULT_REGISTRY


def _state(*, gold: int = 100, plane: int = 1, r: int = 3, level: int = 6,
           bench: list[BenchChar | None] | None = None,
           shop: list[ShopCard] | None = None,
           board: dict | None = None,
           hp: int = 80) -> GameState:
    return GameState(
        plane=plane, round_num=r, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2,
        deployed=[], bench=bench if bench is not None else [None] * BENCH_CAPACITY,
        shop=shop if shop is not None else [], node_type='battle',
        board=board or {})


def _sc(name: str, cost: int = 2) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


def _full_bench() -> list[BenchChar]:
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS

    def _ch(name: str, slot: int) -> BenchChar:
        fac = (CHARACTERS[name].factions or ('?',))[0]
        return BenchChar(slot=slot, char_id=name, faction=fac, star=1)
    return [_ch('阿格莱雅', i) for i in range(BENCH_CAPACITY)]


def _sess(state: GameState, *, level_up: bool = False) -> StrategySession:
    s = StrategySession()
    s.v3_dp_posture = RoundPosture(
        (state.plane, state.round_num),
        Posture(save=False, level_up=level_up, refresh_budget=0))
    return s


def _o1_cands(state: GameState, session: StrategySession) -> list:
    return [c for c in generate_candidates(state, session, _REG)
            if c.tag == 'o1_bench_fill']


# --- 放行域命中 ---------------------------------------------------------------


def test_o1_fill_generated_in_overflow_free_bench_frame() -> None:
    """局23 型帧(g=100+备战空+非目标件):散件生成 o1 标签、评 0 中性
    (义务证明背书,bd 带通道标记)。"""
    st = _state(gold=100, shop=[_sc('乱破', 2)], board={})
    s = _sess(st)
    cands = _o1_cands(st, s)
    assert len(cands) == 1
    val, bd = score_candidate(cands[0], st, s, _REG)
    assert val == 0.0 and bd.get('o1_bench_fill') is True
    assert bd.get('int_emb') == 0.0    # 无息分量可剥离(EV 剥离单一源)


def test_o1_buy_allowed_above_reserve_cap() -> None:
    """逐笔可行性(放行侧):花后 ≥R*(常态无排程 R*=息线)→ gold_floor
    不拒(散件 2 费,100→58 ≥50)。"""
    st = _state(gold=100, shop=[_sc('乱破', 2)], board={})
    s = _sess(st)
    cand = _o1_cands(st, s)[0]
    assert _check_constraint('gold_floor', cand, st.copy(), st, s,
                             _REG, val=0.0, bd={}, auth=None) is None


def test_o1_buy_rejected_below_reserve_cap() -> None:
    """逐笔可行性(拒侧):排程升级帧(R*=息线+升级费)花后吃储蓄 →
    gold_floor 的 o1 地板加深拒(g=50+level_cost(5)+3,买 6 费 →
    花后 <R*)。level=5 < 峰值级 6 → 排程预告态成立(批 3 确定性核)。"""
    st = _state(gold=50 + level_cost(5) + 3, r=5, level=5,
                shop=[_sc('乱破', 6)], board={})
    s = _sess(st)
    cand = _o1_cands(st, s)[0]
    reason = _check_constraint('gold_floor', cand, st.copy(), st, s,
                               _REG, val=0.0, bd={}, auth=None)
    assert reason is not None and reason.constraint == 'gold_floor'


# --- 其余域原样([31] 限域取代的边界)----------------------------------------


def test_no_o1_below_reserve_cap() -> None:
    """凑息期(g≤R*):散件不生成([2]/[28] 凑息优先,零漂移锚)。"""
    st = _state(gold=30, shop=[_sc('乱破', 2)], board={})
    assert _o1_cands(st, _sess(st)) == []


def test_no_o1_when_bench_full() -> None:
    """满槽帧:散件不生成(A-1/A-2 槽位约束原样)。"""
    st = _state(gold=100, bench=_full_bench(),
                shop=[_sc('乱破', 2)], board={})
    assert _o1_cands(st, _sess(st)) == []


def test_no_o1_in_emergency() -> None:
    """应急帧让位(保血域,辖区不相交)。"""
    st = _state(gold=100, hp=20, shop=[_sc('乱破', 2)], board={})
    assert _o1_cands(st, _sess(st)) == []


def test_bond_fallback_beats_o1_quality_order() -> None:
    """质量序(直查 _buy_tag,W47 锁同口径):锁线帧同阵营 1 费件 →
    bond_fallback(凑羁绊填充,O1 前置);不同阵营非引擎件 → o1 标签
    (散件末位)。O1 只兜 bond_fallback 之后的尾。"""
    from types import SimpleNamespace
    from sr_od.application.currency_war.kernel.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    from sr_od.application.currency_war.decision.decision_v2.candidates import _buy_tag
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    sess.v3_intention = ist
    sess.v3_hoard = HoardTarget(
        frozenset({'姬子·启行'}), frozenset(), 'locked')
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    fac = (CHARACTERS['桑博'].factions or ('?',))[0]
    st = _state(gold=100, board={},
                bench=[BenchChar(slot=0, char_id='桑博', faction=fac,
                                 star=1)] + [None] * (BENCH_CAPACITY - 1))
    fill_card = SimpleNamespace(name='凑档件', faction=fac, cost=1,
                                x=0, star=1)
    loose_card = SimpleNamespace(name='乱破', faction='巡海游侠', cost=2,
                                 x=0, star=1)
    assert _buy_tag(fill_card, st, sess, _REG) == 'bond_fallback'
    assert _buy_tag(loose_card, st, sess, _REG) == 'o1_bench_fill'


def test_engine_seed_rejection_not_bypassed_by_o1() -> None:
    """引擎种子散买断(ADR-0333)先于 O1:板面已有未成型体系时新体系
    引擎件仍不生成(O1 不绕开既有方向门)。"""
    st = _state(gold=100, board={'仙舟': 1}, shop=[_sc('卡芙卡', 4)])
    assert _o1_cands(st, _sess(st)) == []

