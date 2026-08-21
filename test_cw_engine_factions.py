"""r242 挂件质量测试:方向期(锁线/桥)只买引擎阵营。"""
from sr_od.application.currency_war.cw_state import (
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(gold: int = 30):
    s = LineStrategy()
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 1, 6, gold, 80
    st.board = {'夜之半神': 1}    # 已有非引擎阵营
    sess = StrategySession()
    sess.v2_state = None
    sess.locked_line = None
    sess.bridge_id = None
    return s, st, sess


def test_locked_line_engine_only():
    """锁线后:夜半(非引擎)同阵营也不买;仙舟(引擎)同持有
    阵营时可买(_pair_wants=与已持有同阵营的语义)。"""
    s, st, sess = _mk(gold=30)
    sess.locked_line = 'jizi_train'
    assert not s._pair_wants(
        ShopCard(x=0, faction='夜之半神', name='赛飞儿', cost=1), st, sess)
    st.board = {'仙舟': 1}    # 持有仙舟 → 引擎阵营凑对可买
    assert s._pair_wants(
        ShopCard(x=1, faction='仙舟', name='藿藿', cost=1), st, sess)


def test_no_direction_all_factions():
    """无锁无桥:全阵营凑对(冷启动止血保留)。"""
    s, st, sess = _mk(gold=30)
    assert s._pair_wants(
        ShopCard(x=0, faction='夜之半神', name='赛飞儿', cost=1), st, sess)


def test_bridge_direction_engine_only():
    """有桥:同引擎门(桥本身就是方向)。"""
    s, st, sess = _mk(gold=30)
    sess.bridge_id = 'xianzhou_dot'
    assert not s._pair_wants(
        ShopCard(x=0, faction='狼狩', name='飞霄', cost=1), st, sess)


def test_engine_faction_pair_still_works():
    """引擎阵营的凑对不受影响(r6 前买的赛飞儿/飞霄类
    夜半/狼狩件不再进,仙舟/列车/DOT 照买)。"""
    s, st, sess = _mk(gold=30)
    sess.locked_line = 'jizi_train'
    st.board = {'列车同行': 1}
    assert s._pair_wants(
        ShopCard(x=0, faction='列车同行', name='三月七', cost=1), st, sess)


def test_engine_gate_uses_full_bonds():
    """r243:引擎判定看注册表全羁绊(factions+flows)——
    艾丝妲 faction=银河学者但 flows=持续伤害(DOT 引擎)
    → 放行;纯学者黑塔 → 拒。"""
    s, st, sess = _mk(gold=30)
    sess.locked_line = 'jizi_train'
    st.board = {'银河学者': 1}
    assert s._pair_wants(
        ShopCard(x=0, faction='银河学者', name='艾丝妲', cost=1), st, sess)
    assert not s._pair_wants(
        ShopCard(x=1, faction='银河学者', name='黑塔', cost=1), st, sess)
