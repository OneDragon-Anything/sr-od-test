"""r23 空板出战守卫测试。"""
import sys
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.strategies.default_strategy import DefaultCwStrategy  # noqa: E402


def _obs(dep=0, bench=0):
    return SimpleNamespace(
        box_overlay_open=False, tomes=[], boxes=[], spheres=[],
        free_bench_slots=9 - bench, shop_open=False,
        bench_chars=[SimpleNamespace(char_id=f'c{i}') for i in range(bench)],
        deployed_chars=[SimpleNamespace(char_id=f'd{i}') for i in range(dep)],
        front_occupied=set(), back_occupied=set(), front_size=4, back_size=6,
        state=None, state_gold_trusted=False)


def _cfg():
    return SimpleNamespace()


def test_empty_board_guard_redirects_to_deploy() -> None:
    """板上 0 人 bench 3 人:不出战,回 RunDeploy。"""
    strat = DefaultCwStrategy()
    obs = _obs(dep=0, bench=3)
    sess = SimpleNamespace(defer_count=0, memory={}, target_comp=None,
                           tracked_bench_chars=[], pending_deploys=[], prep_phase=3,
                           prep_phase_retry=0, tracked_deployed=[], bail_reason_counts={})
    act = strat.decide_prep_action(obs, sess, _cfg())
    assert type(act).__name__ == 'RunDeploy', f'应回部署段,实得 {type(act).__name__}'
    assert sess.prep_phase == 1


def test_empty_board_guard_gives_up_after_two() -> None:
    """重试 2 次后放行(部署持续失败交 Director stall 兜底,防 phase 死循环)。"""
    strat = DefaultCwStrategy()
    obs = _obs(dep=0, bench=3)
    sess = SimpleNamespace(defer_count=0, memory={}, target_comp=None,
                           tracked_bench_chars=[], pending_deploys=[], prep_phase=3,
                           prep_phase_retry=2, tracked_deployed=[], bail_reason_counts={})
    act = strat.decide_prep_action(obs, sess, _cfg())
    assert type(act).__name__ == 'StartBattle'


def test_deployed_board_battles_normally() -> None:
    """板上有人不拦截(正常出战)。"""
    strat = DefaultCwStrategy()
    obs = _obs(dep=4, bench=2)
    sess = SimpleNamespace(defer_count=0, memory={}, target_comp=None,
                           tracked_bench_chars=[], pending_deploys=[], prep_phase=3,
                           prep_phase_retry=0, tracked_deployed=[], bail_reason_counts={})
    act = strat.decide_prep_action(obs, sess, _cfg())
    assert type(act).__name__ == 'StartBattle'
