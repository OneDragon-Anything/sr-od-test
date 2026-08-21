"""r255 P2 装备流策略加分测试。"""

from sr_od.application.currency_war.cw_events import decide_event
from sr_od.application.currency_war.cw_state import GameState


class _Cfg:
    strategy_priority: list = []
    strategy_forbid: list = []
    env_priority: list = []
    env_forbid: list = []


def _st(plane: int = 2, hp: int = 60):
    s = GameState()
    s.plane, s.hp = plane, hp
    s.level, s.gold = 7, 50
    return s


def test_p2_equip_flow_boosted():
    """P2 期军火类策略 +25(选它而不是常规同等分)。"""
    st = _st(plane=2)
    opts = ['三三三', '公司军火更新·金']
    r = decide_event(opts, _Cfg(), st)
    assert opts[r.option_idx] == '公司军火更新·金'


def test_p1_no_equip_boost():
    """P1 期不加(P1 板面成型优先;军火银低分 vs
    黑塔纪元定义型 120——P1 无加分时定义型胜)。"""
    st = _st(plane=1)
    opts = ['黑塔纪元', '公司军火更新·银']
    r = decide_event(opts, _Cfg(), st)
    assert opts[r.option_idx] == '黑塔纪元'


def test_survival_picks_untouched():
    """低血生存钩子与装备流叠加兼容(不同策略类)。"""
    st = _st(plane=2, hp=30)
    opts = ['免战牌', '白衣伙伴']
    r = decide_event(opts, _Cfg(), st)
    assert opts[r.option_idx] == '免战牌'
