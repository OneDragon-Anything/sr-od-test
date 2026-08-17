"""cw_action_ontology(26 号动作本体)v0 测试:J1 审计 + 投影语义。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_action_ontology import (  # noqa: E402
    _ONTOLOGY,
    completeness_audit,
    legal_actions,
)
from sr_od.application.currency_war.cw_state import (  # noqa: E402
    BenchChar,
    GameState,
)


def test_j1_audit_finds_unowned_actions() -> None:
    """J1:完备性审计报出 2 个无主动作(特选填格/池操纵)—— 盲区一等输出。"""
    rep = completeness_audit()
    assert rep['verdict'] == 'gaps_found'
    assert 'FillBladeSlots特选填格' in rep['unowned_registered']
    assert 'PoolManipulation池操纵' in rep['unowned_registered']
    assert rep['unregistered'] == []


def test_ontology_six_fields_complete() -> None:
    """六元语义完整:每动作前置/效应/成本/可逆性/随机性/观测验证非空;证据状态词汇封闭。"""
    for a in _ONTOLOGY.values():
        assert a.precondition and a.effect and a.cost
        assert a.reversibility in ('reversible', 'compensable', 'irreversible')
        assert a.randomness in ('none', 'shop_face', 'upgrade_branch')
        assert a.observation_verify
        assert a.evidence in ('unverified', 'bracketed', 'verified', 'refuted', 'stale')


def test_legal_actions_projection() -> None:
    """状态 → 合法动作投影:金 0 只剩 bench 类;有金有 bench 全类;bench 满挡买。"""
    empty = GameState(gold=0, level=3, plane=1, bench=[], deployed=[])
    assert legal_actions(empty) == []
    rich = GameState(gold=30, level=3, plane=1,
                     bench=[BenchChar(slot=0, faction='仙舟')], deployed=[])
    acts = legal_actions(rich)
    assert {'BuyCard', 'SellBench', 'DeployMove', 'LevelUp', 'RefreshShop'} <= set(acts)
    full_bench = GameState(gold=30, level=3, plane=1,
                           bench=[BenchChar(slot=i, faction='仙舟') for i in range(9)],
                           deployed=[])
    acts2 = legal_actions(full_bench)
    assert 'BuyCard' not in acts2 and 'RefreshShop' in acts2
