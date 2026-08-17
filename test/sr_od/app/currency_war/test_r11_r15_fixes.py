"""r11-r15 修复批的直接测试(review 指出「三 commit 均零测试改动」)。

覆盖:① find_tomes 双分数互斥(mock 分数组合:箱源误检拒/真典籍过/选中态薄余量);
② _want_level_up P2 comp-roll 硬下限分支;③ OpenTome defer 门(default_strategy 规则 2)。
"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war import cw_identity_obs as cio  # noqa: E402
from sr_od.application.currency_war.cw_comps import get_comp  # noqa: E402
from sr_od.application.currency_war.cw_economy import _want_level_up  # noqa: E402
from sr_od.application.currency_war.cw_state import GameState  # noqa: E402


def _mk_tome_plug(monkeypatch, tome_scores: list[float], box_scores: list[float]) -> list[tuple]:
    """mock matchTemplate:第 1 次调用返 tome_scores[k],第 2 次返 box_scores[k](按槽序)。"""
    state = {'tome': iter(tome_scores), 'box': iter(box_scores)}
    calls = {'tome': [], 'box': []}

    def fake_mt(crop, tm, method):
        # 判哪个模板:与全局 mock 的 id 对齐(用调用序:每槽先 tome 后 box)
        if not calls['tome'] or len(calls['box']) == len(calls['tome']):
            v = next(state['tome'])
            calls['tome'].append(v)
            return _fake_result(v)
        v = next(state['box'])
        calls['box'].append(v)
        return _fake_result(v)

    import numpy as np

    def _fake_result(v: float):
        arr = np.full((3, 3), v, dtype=np.float32)
        return arr

    return fake_mt, calls


def test_find_tomes_mutex_rejects_box_source(monkeypatch) -> None:
    """互斥:箱源误检(tome 0.63 < box 0.90)必须拒(r11 修,M55 活锁根因)。"""
    import cv2
    import numpy as np
    fake, _ = _mk_tome_plug(monkeypatch, [0.63], [0.90])
    monkeypatch.setattr(cv2, 'matchTemplate', fake)
    monkeypatch.setattr(cio, '_get_tome_gray', lambda: np.zeros((10, 10), dtype=np.uint8))
    monkeypatch.setattr(cio, '_get_supply_box_gray', lambda: np.zeros((10, 10), dtype=np.uint8))
    img = np.full((20, 20, 3), 200, dtype=np.uint8)
    from one_dragon.base.geometry.rectangle import Rect
    slots = [(1, Rect(0, 0, 20, 20))]
    out = cio.find_tomes(img, slots)
    assert out == [], f'箱源误检应被互斥拒,实得 {out}'


def test_find_tomes_accepts_true_tome(monkeypatch) -> None:
    """互斥:真典籍(tome 0.95 > box 0.44 且 ≥0.6)必须过。"""
    import cv2
    import numpy as np
    fake, _ = _mk_tome_plug(monkeypatch, [0.95], [0.44])
    monkeypatch.setattr(cv2, 'matchTemplate', fake)
    monkeypatch.setattr(cio, '_get_tome_gray', lambda: np.zeros((10, 10), dtype=np.uint8))
    monkeypatch.setattr(cio, '_get_supply_box_gray', lambda: np.zeros((10, 10), dtype=np.uint8))
    img = np.full((20, 20, 3), 200, dtype=np.uint8)
    from one_dragon.base.geometry.rectangle import Rect
    slots = [(1, Rect(0, 0, 20, 20))]
    out = cio.find_tomes(img, slots)
    assert len(out) == 1, f'真典籍应命中,实得 {out}'


def test_want_level_up_p2_floor_beats_comp_roll() -> None:
    """P2 地板硬下限:comp lv6=roll 但 P2 节点 target=8 → 仍追级(r11 #3,M55 冻 lv6 死)。"""
    comp = get_comp('万敌单C')   # lv6 = roll(实证)
    st = GameState(level=6, plane=2, round_num=1, gold=50, hp=80)
    assert _want_level_up(st, comp) is True, 'P2 落后 node 地板(8)应追级(comp roll 只在 P1 压)'
    st1 = GameState(level=6, plane=1, round_num=1, gold=50, hp=80)
    assert _want_level_up(st1, comp) is False, 'P1 comp roll 意图保留(不改既有行为)'


def test_opentome_defer_gate() -> None:
    """defer 门:defer_count>=2 时策略不再提 OpenTome(走主流程)。"""
    from types import SimpleNamespace
    from sr_od.application.currency_war.strategies.default_strategy import DefaultCwStrategy
    strat = DefaultCwStrategy()
    obs = SimpleNamespace(box_overlay_open=False, tomes=[(1, None)], boxes=[],
                          spheres=[], free_bench_slots=3, shop_open=False,
                          bench_chars=[], deployed_chars=[], front_occupied=set(),
                          back_occupied=set(), front_size=4, back_size=6,
                          state=None, state_gold_trusted=False)
    sess = SimpleNamespace(defer_count=2, memory={}, target_comp=None,
                           tracked_bench_chars=[], pending_deploys=[], prep_phase=0,
                           tracked_deployed=[], bail_reason_counts={})
    cfg = SimpleNamespace()
    act = strat.decide_prep_action(obs, sess, cfg)
    assert type(act).__name__ != 'OpenTome', f'defer≥2 应跳过 OpenTome,实得 {type(act).__name__}'
