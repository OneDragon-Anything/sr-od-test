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
    """r350(cacb7362,局38 boss -34 根因):锁线后挂件门**只认
    线形态羁绊**(jizi=列车+护盾)——引擎阵营(仙舟)不再是线内
    需求的替代品,即使同持有阵营也不买;线形态羁绊同持有可买。"""
    s, st, sess = _mk(gold=30)
    sess.locked_line = 'jizi_train'
    assert not s._pair_wants(
        ShopCard(x=0, faction='夜之半神', name='赛飞儿', cost=1), st, sess)
    st.board = {'仙舟': 1}    # 持有仙舟:引擎阵营,非 jizi 线形态 → r350 拒
    assert not s._pair_wants(
        ShopCard(x=1, faction='仙舟', name='藿藿', cost=1), st, sess)
    st.board = {'列车同行': 1}   # 线形态羁绊 + 同持有 → 买
    assert s._pair_wants(
        ShopCard(x=0, faction='列车同行', name='三月七', cost=1), st, sess)


def test_no_direction_all_factions():
    """无锁无桥的凑对语义保留在**非冷启动轮**:ADR-0240(r368,
    1c9b5903)+ r371b(e6ad685c)后,开局轮(P1 r≤2)只放行
    桥名单∪引擎阵营;夜半凑对在冷启动窗外(r5)仍放行。"""
    s, st, sess = _mk(gold=30)
    st.round_num = 1
    assert not s._pair_wants(
        ShopCard(x=0, faction='夜之半神', name='赛飞儿', cost=1), st, sess)
    st.round_num = 5
    assert s._pair_wants(
        ShopCard(x=0, faction='夜之半神', name='赛飞儿', cost=1), st, sess)


def test_bridge_direction_engine_only():
    """有桥:同引擎门(桥本身就是方向)。r353(8add6d5e)V4.0
    口径对齐起 hunt3 入桥池 → 狼狩属引擎阵营(ADR-0243 桥映射
    补全 hunt3),桥方向期飞霄放行;非引擎阵营(公司)仍拒。"""
    s, st, sess = _mk(gold=30)
    sess.bridge_id = 'xianzhou_dot'
    assert s._pair_wants(
        ShopCard(x=0, faction='狼狩', name='飞霄', cost=1), st, sess)
    assert not s._pair_wants(
        ShopCard(x=1, faction='公司', name='翡翠', cost=1), st, sess)


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
    **桥方向期(未锁线)**艾丝妲 faction=银河学者但 flows=
    持续伤害(DOT 引擎)→ 放行;纯学者黑塔 → 拒。
    (原锁线版被 r350(cacb7362)推翻:锁线只认线形态——艾丝妲
    flows=DOT 被引擎门收进 jizi 局占部署位正是局38 实锤根因;
    全羁绊判据保留在桥方向期。)"""
    s, st, sess = _mk(gold=30)
    st.round_num = 5
    sess.bridge_id = 'xianzhou_dot'
    st.board = {'银河学者': 1}
    assert s._pair_wants(
        ShopCard(x=0, faction='银河学者', name='艾丝妲', cost=1), st, sess)
    assert not s._pair_wants(
        ShopCard(x=1, faction='银河学者', name='黑塔', cost=1), st, sess)
