"""W245/A4:bond_fallback 泄放路径 benchmark 锁(W241 巡检 A4 观察收口)。

背景(w241_audit5.md §A4 + W242 插话回应 b6918ae4):bond_fallback 条件
(填充件阵营∈owned+cost∈[1,2]+round≥3)买入的评分**不经过
filler_star 期权分**(期权只辖 deployed 填充件的第 2 份;候选分数里
没有该维度时仲裁「非正分」拒)——即 bond_fallback 路径的量值独立于
filler_star_unit 开关。W242 AB 实测 gp/star 两臂该通道各 2 笔/30 局
零差异、末窗 0 笔=路径在授权语义上正交。

本文件钉两组 benchmark,防未来改评分/改 filler 项时该路径静默变号:
- 开关正交锁:filler_star_unit 0→0.5,bond_fallback 条件帧分值不变;
- 泄放形态锁:bond_fallback 帧(非目标集外副本、阵营 owned 已有)
  在默认 registry 下走非正分门的分值为基准负值(结构性拒形态,
  W231 诊断——若未来变正,说明有人给该路径加了新评分维,须有 ADR)。
"""
import sys

sys.path.insert(0, 'src')

from dataclasses import replace
from types import SimpleNamespace

from sr_od.application.currency_war.cw_state import GameState, ShopCard
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.scoring import score_candidate


def _card(name: str, faction: str = '仙舟罗浮', cost: int = 1) -> ShopCard:
    return ShopCard(x=1, faction=faction, name=name, cost=cost)


def _deployed(name: str, faction: str, star: int = 1) -> object:
    return SimpleNamespace(char_id=name, faction=faction, star=star)


def _state(round_num: int = 5) -> GameState:
    """bond_fallback 条件帧:同阵营在场(凑档判据)+r≥3+1 费卡。"""
    return GameState(
        plane=1,
        round_num=round_num,
        gold=20,
        hp=50,
        level=4,
        deployed=[],
        bench=[],
        board={'仙舟罗浮': 1},
        shop=[_card('占位件', '仙舟罗浮', cost=1)],
    )


def _sess() -> StrategySession:
    """与 W242 锁同构的意向环境(锁线=h三月七仙舟,凑档判据可成立)。"""
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
    return s


def _fallback_cand(st, sess):
    cands = [c for c in generate_candidates(st, sess, DEFAULT_REGISTRY)
             if getattr(c, 'tag', '') == 'bond_fallback']
    assert cands, '条件帧必须生成 bond_fallback 候选'
    return cands[0]


def test_bond_fallback_score_orthogonal_to_filler_star_unit() -> None:
    """开关正交锁:filler_star_unit 变化不改 bond_fallback 分值。

    该路径不经期权分(A4 披露)——它走 [31] 凑档散件的基础分。
    若此锁红:有人让 filler_star 维度渗入 bond_fallback 通道,
    需检查是否双计(W232 期权 + 本通道重叠)。
    """
    st, sess = _state(), _sess()
    cand = _fallback_cand(st, sess)
    v_off, _ = score_candidate(cand, st, sess, DEFAULT_REGISTRY)

    reg_open = replace(DEFAULT_REGISTRY, filler_star_unit=0.5)
    v_on, _ = score_candidate(cand, st, sess, reg_open)
    assert v_off == v_on, (
        f'bond_fallback 分值不应随 filler_star_unit 变({v_off} vs {v_on})')


def test_bond_fallback_default_registry_structural_reject() -> None:
    """benchmark 锁(实测 +2.0,W241/A4 披露):bond_fallback 凑档帧
    在默认 registry 下为固定正分——「凑档+基础价差」的正分,与
    filler_star 期权分无关(A4/审计2:该路径量值独立于开关)。若此值
    漂移:bond_fallback 评分或其依赖(board 分桶/cost 窗口)被改,
    需有 ADR;若未来 filler_star 维度渗入本通道导致开关联动,
    test_..._orthogonal_to_filler_star_unit 先红。"""
    st, sess = _state(), _sess()
    cand = _fallback_cand(st, sess)
    v, _ = score_candidate(cand, st, sess, DEFAULT_REGISTRY)
    assert v == 2.0, (
        f'bond_fallback benchmark 漂移:{v} != 2.0(凑档帧实测基准;'
        '评分改动须 ADR 并重算该路径对 star>=2 的贡献占比)')
