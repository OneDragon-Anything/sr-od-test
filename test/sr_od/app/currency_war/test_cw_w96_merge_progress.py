"""W96 断买修复锁(ADR-0340;溢出金断买评分层最小件 + 检查网回灌)。

锁定对象(W93 诊断根因,deep_read/W93_报告.md):
1. 评分层份数显影:score_state 3合1 中间进度项(merge_progress)——
   目标件第 2 份 1★ 的期权显影(第 3 份 merge 后 core_star 承接,
   star≥2 让位不双计;deployed 全额/纯 bench 折减 ADR-0295 同式);
   unit=0 关闭(A/B 通道)。
2. r9 病灶帧单帧锁:deployed 目标核心 1★ + 店内同名 → 买入候选
   正分(W93:候选生成但全维度零 delta 被「非正分」拒)。
3. r7 病灶帧生成层不变式:r410 守卫(copy_swap_useless)未动——
   deployed 非核心目标件的第 2 份仍不生成候选(ADR-0303/0304
   豁免默认关;生成层重估=设计建议,见 W96_报告.md)。
4. 检查器回灌:溢出金断买(P1 金>50 连续 ≥2 轮零买零升级)进
   _BATCH_CHECKS;W93 病灶形态(3 连)必须报,升级滴漏/金≤50/
   P2 轮不误报。
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.cw_sim_checks import (
    check_overflow_gold_zero_buy_streak,
)
from sr_od.application.currency_war.cw_state import BenchChar, GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    score_candidate,
    score_state,
)

_REG = DEFAULT_REGISTRY
_CARRY = '姬子·启行'          # 核心件(v3_core_names;line_carry)
_TARGET_FILLER = '花火'        # 目标件(锁线视窗内,非核心)
_FACTIONS = ('列车同行',)


def _bench(name: str, faction: str = '仙舟罗浮',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _deployed(name: str, faction: str = '列车同行',
              star: int = 1, slot: int = 0) -> SimpleNamespace:
    return SimpleNamespace(char_id=name, faction=faction, star=star,
                           position_pref='back', equips=(), slot=slot)


def _shop_card(name: str, faction: str = '列车同行',
               cost: int = 4) -> SimpleNamespace:
    return SimpleNamespace(name=name, faction=faction, cost=cost,
                           x=0, star=1)


def _sess() -> StrategySession:
    from sr_od.application.currency_war.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {'姬子·启行'}
    # r410 守卫的 core 豁免面(target_comp;W93 r9 帧吉尔伽美什=line_carry
    # 生成即此路径:core 显式保留 → 买副本合法)
    s.target_comp = SimpleNamespace(factions=_FACTIONS,
                                    core_chars=(_CARRY,))
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 9, 'gold': 60, 'level': 5,
            'board': {'列车同行': 2}, 'bench': [], 'shop': [], 'hp': 100}
    base.update(kw)
    return GameState(**base)


# --- 件1:merge_progress 项值 -------------------------------------------------


def test_merge_progress_term_values() -> None:
    """第 2 份显影、第 1 份不显影、star≥2 让位 core_star、非目标不显影。"""
    sess = _sess()
    # 1 份(bench):爬坡未开始
    st1 = _state(bench=[_bench(_TARGET_FILLER, slot=0)])
    assert score_state(st1, _REG, sess)['merge_progress'] == 0.0
    # 2 份纯 bench:折减权重
    st2b = _state(bench=[_bench(_TARGET_FILLER, slot=0),
                         _bench(_TARGET_FILLER, slot=1)])
    assert score_state(st2b, _REG, sess)['merge_progress'] == \
        pytest.approx(_REG.merge_progress_unit * _REG.bench_form_weight)
    # 2 份含 deployed:全额
    st2d = _state(deployed=[_deployed(_TARGET_FILLER,
                                      faction='仙舟罗浮')],
                  bench=[_bench(_TARGET_FILLER, slot=0)])
    assert score_state(st2d, _REG, sess)['merge_progress'] == \
        pytest.approx(_REG.merge_progress_unit)
    # star≥2 持有:core_star 承接,本项让位(不双计)
    st_star2 = _state(bench=[_bench(_TARGET_FILLER, slot=0, star=2),
                             _bench(_TARGET_FILLER, slot=1)])
    assert score_state(st_star2, _REG, sess)['merge_progress'] == 0.0
    assert score_state(st_star2, _REG, sess)['core_star'] > 0.0
    # 非目标件副本不显影([31] 反散件)
    st_off = _state(bench=[_bench('星期日', faction='盛会之星', slot=0),
                           _bench('星期日', faction='盛会之星', slot=1)])
    assert score_state(st_off, _REG, sess)['merge_progress'] == 0.0
    # unit=0 关闭(A/B 基线臂)
    reg_off = DecisionV2Registry(merge_progress_unit=0.0)
    assert score_state(st2d, reg_off, sess)['merge_progress'] == 0.0


def test_merge_progress_per_name_cap_second_copy_only() -> None:
    """每名只计一次(第 2 份,第 1 份不计);多名目标各计各的(不跨名合并)。"""
    sess = _sess()
    st = _state(deployed=[_deployed(_CARRY), _deployed(_TARGET_FILLER,
                                                      faction='仙舟罗浮')],
                bench=[_bench(_CARRY, faction='列车同行', slot=0),
                       _bench(_TARGET_FILLER, slot=1)])
    assert score_state(st, _REG, sess)['merge_progress'] == \
        pytest.approx(_REG.merge_progress_unit * 2)


# --- 件2:r9 病灶帧单帧锁(该买则买)-----------------------------------------


def test_r9_frame_second_copy_buy_scores_positive() -> None:
    """W93 r9 帧形态锁:deployed 核心件 1★ + 店内同名 1★ → 买入候选
    评分 >0(修前:候选生成但全维度零 delta,「非正分」拒——金 86
    溢出零买)。"""
    sess = _sess()
    st = _state(deployed=[_deployed(_CARRY)],
                shop=[_shop_card(_CARRY, cost=4)])
    cands = generate_candidates(st, sess, _REG)
    buy = [c for c in cands
           if c.action.__class__.__name__ == 'BuyCard'
           and c.action.card.name == _CARRY]
    assert buy, '核心件第 2 份候选应生成(r410 core 豁免面)'
    val, bd = score_candidate(buy[0], st, sess, _REG)
    assert val > 0, \
        f'第 2 份买入应正分(实际 {val},delta={bd["after"]})'
    assert bd['after']['merge_progress'] > bd['base']['merge_progress'], (
        '份数显影应构成 delta(基线 '
        f'{bd["base"]["merge_progress"]}'
        ' → 买后 '
        f'{bd["after"]["merge_progress"]})')


def test_r7_frame_generation_guard_unchanged() -> None:
    """W93 r7 帧形态锁(生成层不变式):deployed 非核心目标件的第 2 份
    在**授权窗外**仍不生成候选——r410 守卫未动(ADR-0303/0304 豁免默认
    关);生成层重估只写设计建议(W96_报告.md),归后续批。
    (语义演进史,W257/ADR-0411:末窗承接缺口 gap>0 时同名副本候选经
    C 项定向授权放行——原构造帧恰落末窗缺口内,随 flag 家族清理转正
    后改用 r7 帧钉守卫基线;末窗放行行为由 test_cw_w242_star_directed
    锁。W288/ADR-0418 gate_min_round 前移 8→6 后 r7 落进新授权窗
    {r6..r9},本锁用 replace 把 min_round 钉回 8 保住「非末窗守卫
    不动」的原边界意图——C 臂窗内放行行为另由 W313 新窗锁覆盖。)"""
    reg = replace(DEFAULT_REGISTRY, handoff_gate_min_round=8)
    sess = _sess()
    st = _state(round_num=7,
                deployed=[_deployed(_TARGET_FILLER,
                                    faction='仙舟罗浮')],
                shop=[_shop_card(_TARGET_FILLER, faction='仙舟罗浮',
                                 cost=5)])
    cands = generate_candidates(st, sess, reg)
    names = {c.action.card.name for c in cands
             if c.action.__class__.__name__ == 'BuyCard'}
    assert _TARGET_FILLER not in names, \
        'r410 守卫行为不得被本批评分层改动波及(守卫未动)'


# --- 件3:溢出金断买检查器 ----------------------------------------------------


def _row(rn: int, gold: int, actions: list[dict],
         plane: int = 1, rid: str = 'r_test') -> dict:
    return {'plane': plane, 'round_num': rn, 'gold': gold,
            'actions': actions, 'state': {}, 'run_id': rid}


def _buy_row(name: str = '花火') -> dict:
    return {'__type__': 'BuyCard', 'reason': 'd2_line_carry',
            'card': {'name': name, 'cost': 5}}


def _lv_row() -> dict:
    return {'__type__': 'LevelUp'}


def test_checker_catches_w93_streak() -> None:
    """W93 病灶形态(r7-r9 金 59/70/86 三连零买)必须报。"""
    rows = [_row(7, 59, []), _row(8, 70, []), _row(9, 86, [])]
    v = check_overflow_gold_zero_buy_streak(rows)
    assert len(v) == 1 and '3 连' in v[0], f'三连断买未报(实际 {v})'


def test_checker_streak_requires_two_rounds() -> None:
    """单轮零买不报(金 51 单轮过线合法);金 ≤50 不计数。"""
    assert check_overflow_gold_zero_buy_streak(
        [_row(7, 55, [])]) == []
    assert check_overflow_gold_zero_buy_streak(
        [_row(7, 50, []), _row(8, 50, []), _row(9, 50, [])]) == []


def test_checker_spend_breaks_streak() -> None:
    """买入/升级都算花金([17] 滴漏不算冻结);P2 轮不辖。"""
    rows = [_row(7, 60, [_buy_row()]), _row(8, 70, [_lv_row()]),
            _row(9, 86, [])]
    assert check_overflow_gold_zero_buy_streak(rows) == []
    # P2 语义另裁:plane=2 的断买不计入 streak
    rows_p2 = [_row(7, 60, [], plane=2), _row(8, 70, [], plane=2)]
    assert check_overflow_gold_zero_buy_streak(rows_p2) == []


def test_checker_registered_in_batch_checks() -> None:
    """接线锁:检查器进 _BATCH_CHECKS(sim 批次 checks_violations 覆盖)。"""
    from sr_od.application.currency_war.cw_sim_checks import _BATCH_CHECKS
    assert _BATCH_CHECKS.get('overflow_gold_zero_buy_streak') \
        is check_overflow_gold_zero_buy_streak
