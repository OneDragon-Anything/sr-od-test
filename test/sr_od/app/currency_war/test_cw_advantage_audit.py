"""cw_advantage_audit(42 号决策级优势审计)v0 测试:J0 注入恢复 + 聚合/覆盖语义。"""
import random
import sys
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_advantage_audit import (  # noqa: E402
    CoverageLedger,
    DecisionPoint,
    advantage_one_step,
    audit_decision_class,
)
from sr_od.application.currency_war.cw_state import (  # noqa: E402
    GameState,
    LevelUp,
)


def _st(seed: int = 1, gold: int = 30, level: int = 5, hp: int = 60,
        xp: tuple[int, int] | None = None) -> GameState:
    rng = random.Random(seed)
    st = GameState(gold=gold, round_num=3, level=level, plane=1, hp=hp,
                   bench=[], deployed=[], board={})
    if xp is not None:
        st.xp_progress = xp
    return st


def test_j0_degraded_recovery_positive() -> None:
    """J0 核心:live 持续「该升级不升」(xp 门槛-1,一次点击即跨级)vs 影子点击升级 →
    审计恢复该决策类 positive(影子优势,CI 下界 > 地板)。"""
    pts, states = [], []
    for i in range(15):
        # lv4→5 需 6 XP;设 xp_progress=(2, 6):一次 +4 即跨级(真实机制语义)
        st = _st(seed=i, gold=40, level=4, hp=30 + i * 2, xp=(2, 6))
        states.append(st)
        pts.append(DecisionPoint('r', i + 1, 'level_gate', plane=1, level=4,
                                 hp=st.hp, gold=40,
                                 live_action=None,          # 不升(劣化:等级低 → P(win) 低)
                                 shadow_action=LevelUp(cost=4)))
    rep = audit_decision_class(pts, states, noise_floor=0.003)
    v = rep['level_gate|p1|early']
    assert v['verdict'] == 'positive', f"劣化未恢复: {v}"
    assert v['mean'] > 0.003


def test_j0_clean_noise_floor() -> None:
    """J0 对照:live=影子(同动作)→ 优势全 0 → noise(地板内,零误报)。"""
    pts, states = [], []
    for i in range(10):
        st = _st(seed=i, gold=40, level=4, hp=40 + i)
        states.append(st)
        pts.append(DecisionPoint('r', i + 1, 'level_gate', plane=1, level=4, hp=st.hp,
                                 gold=40, live_action=LevelUp(cost=4),
                                 shadow_action=LevelUp(cost=4)))
    rep = audit_decision_class(pts, states)
    assert rep['level_gate|p1|early']['verdict'] == 'noise'


def test_one_step_none_on_missing_shadow() -> None:
    """shadow 缺失(无备选可评)→ None;live=None=现状不动作(可计分,J0 用例)。"""
    dp = DecisionPoint('r', 1, 'sell', live_action=LevelUp(cost=4), shadow_action=None)
    assert advantage_one_step(dp, _st()) is None


def test_uncovered_small_n() -> None:
    """可计分点 < 5 → uncovered(欠功效如实)。"""
    pts = [DecisionPoint('r', 1, 'deploy', plane=1, level=3,
                         live_action=LevelUp(cost=4), shadow_action=LevelUp(cost=4))]
    states = [_st()]
    rep = audit_decision_class(pts, states)
    assert rep['deploy|p1|early']['verdict'] == 'uncovered'


def test_coverage_ledger_routes() -> None:
    """覆盖记账:不可测原因显式路由(39 探针 / 40 dark / 29 实验)。"""
    led = CoverageLedger()
    led.record(DecisionPoint('r', 1, 'refresh_cap', plane=1, level=4), scored=False,
               reason='no_shadow')
    led.record(DecisionPoint('r', 2, 'refresh_cap', plane=1, level=4), scored=False,
               reason='sim_untrusted')
    led.record(DecisionPoint('r', 3, 'refresh_cap', plane=1, level=4), scored=True)
    gm = led.gap_map()['refresh_cap|p1|early']
    assert gm['n_diff'] == 3 and gm['n_scored'] == 1
    assert 'probe@39(影子重放/实验局)' in gm['routes']
    assert 'dark@40(模型不可信合流)' in gm['routes']


def test_advantage_sign_on_hp_delta() -> None:
    """一步差语义:备选动作升级(xp 门槛-1 即跨)→ 等级 ↑ → P(win) ↑ → 优势 > 0。"""
    st = _st(gold=40, level=4, hp=50, xp=(2, 6))
    dp = DecisionPoint('r', 1, 'level_gate', plane=1, level=4, hp=50, gold=40,
                       live_action=None, shadow_action=LevelUp(cost=4))
    assert advantage_one_step(dp, st) > 0
