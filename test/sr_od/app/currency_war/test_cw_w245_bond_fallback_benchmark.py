"""A4:bond_fallback 泄放路径 benchmark 锁(巡检 A4 观察收口)。

背景(w241_audit5.md §A4 + 插话回应 b6918ae4):bond_fallback 条件
(填充件阵营∈owned+cost∈[1,2]+round≥3)买入的评分走 [31] 凑档
散件的基础分,量值独立于副本期权类评分维度。AB 实测 gp/star 两臂
该通道各 2 笔/30 局零差异、末窗 0 笔=路径在授权语义上正交。

本文件钉泄放形态锁,防未来改评分时该路径静默变号:
- 泄放形态锁:bond_fallback 帧(非目标集外副本、阵营 owned 已有)
  在默认 registry 下的分值基准为 +2.0 正分(凑档帧实测,A4 披露;
  存在叠加评分维)——防该基准静默漂移:漂移即红,红须对照 ADR
  判新评分维合法性。
(filler_star 期权分开关联动正交锁已随 ADR-0402 定谳清理删除——
该开关不复存在,基准锁的语义前提见上。)
"""
import sys

sys.path.insert(0, 'src')

from types import SimpleNamespace

from sr_od.application.currency_war.cw_state import GameState, ShopCard
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
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
    """与 test_cw_w242 锁同构的意向环境(锁线=h三月七仙舟,凑档判据可成立)。"""
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


def test_bond_fallback_default_registry_structural_reject() -> None:
    """benchmark 锁(实测 +2.0,A4 披露):bond_fallback 凑档帧
    在默认 registry 下为固定正分——「凑档+基础价差」的正分,与
    副本期权类评分维无关(A4/审计2)。若此值漂移:bond_fallback
    评分或其依赖(board 分桶/cost 窗口)被改,需有 ADR。"""
    st, sess = _state(), _sess()
    cand = _fallback_cand(st, sess)
    v, _ = score_candidate(cand, st, sess, DEFAULT_REGISTRY)
    assert v == 2.0, (
        f'bond_fallback benchmark 漂移:{v} != 2.0(凑档帧实测基准;'
        '评分改动须 ADR 并重算该路径对 star>=2 的贡献占比)')
