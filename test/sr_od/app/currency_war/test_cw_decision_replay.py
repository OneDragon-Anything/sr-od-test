"""cw_decision_replay(46 号 J0 确定性体检)测试:自洽护栏 + state 复原 roundtrip。"""
import random
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_decision_replay import (  # noqa: E402
    replay_config,
    state_from_row,
)
from sr_od.application.currency_war.cw_plan import plan  # noqa: E402
from sr_od.application.currency_war.cw_state import (  # noqa: E402
    BenchChar,
    GameState,
    ShopCard,
)


def _types(actions) -> list[str]:
    return [type(a).__name__ for a in actions]


def _syn_state(seed: int = 1) -> GameState:
    rng = random.Random(seed)
    return GameState(
        gold=30, round_num=3, level=5, plane=1, hp=70,
        shop=[ShopCard(x=i + 1, faction=rng.choice(['贝洛伯格', '仙舟', '巡海游侠']),
                       name='', cost=rng.randint(1, 3)) for i in range(5)],
        bench=[BenchChar(slot=i, faction='贝洛伯格', star=1) for i in range(2)],
        deployed=[BenchChar(slot=0, faction='仙舟', star=1)],
        board={'仙舟': 1},
    )


def test_plan_self_consistency_guard() -> None:
    """J0 硬判据 CI 护栏:同 state + 同种子 → 决策序列逐次一致(46 号 ADR-0180)。

    三个合成局面(健康/血危/晚期)× 各两次同种子调用;任一不一致 = 确定性违纪。
    """
    cfg = replay_config()
    cases = [
        _syn_state(1),
        _syn_state(2).__class__(**{**_syn_state(2).__dict__, 'hp': 15, 'gold': 12}),
        _syn_state(3).__class__(**{**_syn_state(3).__dict__, 'plane': 3, 'level': 9, 'gold': 60}),
    ]
    for st in cases:
        a1 = plan(st.copy(), cfg, cfg.faction_priority, rng=random.Random(42))
        a2 = plan(st.copy(), cfg, cfg.faction_priority, rng=random.Random(42))
        assert _types(a1) == _types(a2), f'确定性违纪: {st.plane}/{st.hp}'


def test_state_from_row_roundtrip() -> None:
    """state dict(jsonl 行)→ GameState 复原:嵌套 shop/bench/deployed 类型正确、未知键剔除。"""
    row = {'run_id': 'r', 'target_comp': '',
           'state': {'gold': 20, 'round_num': 2, 'level': 4, 'plane': 1, 'hp': 55,
                     'unknown_future_field': 1,
                     'shop': [{'x': 1, 'faction': '仙舟', 'name': '', 'cost': 2, 'star': 1}],
                     'bench': [{'slot': 0, 'char_id': '', 'faction': '仙舟', 'star': 1,
                                'position_pref': 'back', 'equips': []}],
                     'deployed': []},
           'actions': []}
    st = state_from_row(row)
    assert st.gold == 20 and st.level == 4
    assert isinstance(st.shop[0], ShopCard) and st.shop[0].cost == 2
    assert isinstance(st.bench[0], BenchChar) and st.bench[0].faction == '仙舟'
    assert not hasattr(st, 'unknown_future_field')


def test_plan_replay_deterministic_across_fresh_calls() -> None:
    """跨「进程」等价(独立调用栈):模拟 46 号跨进程验收的 CI 近似(同解释器内两次全链路)。"""
    cfg = replay_config()
    st = _syn_state(9)
    outs = [_types(plan(st.copy(), cfg, cfg.faction_priority, rng=random.Random(7)))
            for _ in range(3)]
    assert outs[0] == outs[1] == outs[2]
