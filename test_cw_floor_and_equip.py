"""r237 回归锁:经济地板三档 + 装备轮转(用户三局反馈
「要么凑息要么买完,结果买一张/装备都给前台1」)。"""
from sr_od.application.currency_war.cw_comps import equip_allocation
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(gold: int, plane: int = 1):
    s = LineStrategy()
    st = GameState()
    st.plane, st.level, st.gold, st.hp = plane, 5, gold, 80
    sess = StrategySession()
    sess.v2_state = None
    sess.locked_line = None
    sess.bridge_id = None
    return s, st, sess


# ===== 地板三档(r236)=====

def test_floor_low_gold_spends_all():
    """金 3(g<10,零息):两张 1 费种子全买——花到 1,
    「买一张就停」回归锁。"""
    s, st, sess = _mk(gold=3)
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1),
               ShopCard(x=1, faction='仙舟', name='爻光', cost=1)]
    buys = [a for a in s.decide_prep(st, sess, None)
            if isinstance(a, BuyCard)]
    assert len(buys) == 2


def test_floor_mid_gold_keeps_tier():
    """金 23(10≤g<50):floor=g%10=3 → 20 预算,档内全花
    (「凑息」语义:保住 20 金息档,档内零息不攒)。"""
    s, st, sess = _mk(gold=23)
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1),
               ShopCard(x=1, faction='仙舟', name='爻光', cost=1),
               ShopCard(x=2, faction='仙舟', name='丹恒·饮月', cost=1)]
    buys = [a for a in s.decide_prep(st, sess, None)
            if isinstance(a, BuyCard)]
    assert len(buys) == 3    # 23-3=20 可花 20:三张 1 费


def test_floor_mid_gold_buys_multiple():
    """金 22(floor=2,预算 20):三张 1 费种子全买
    (「同价连续买不因首张扣减而停」——r236 修的语义;
    砂金/杰帕德不在 P1 桥名单,原测试场景用错件)。"""
    s, st, sess = _mk(gold=22)
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1),
               ShopCard(x=1, faction='仙舟', name='爻光', cost=1),
               ShopCard(x=2, faction='仙舟', name='丹恒·饮月', cost=1)]
    buys = [a for a in s.decide_prep(st, sess, None)
            if isinstance(a, BuyCard)]
    assert len(buys) == 3
    # 金 4(<10 零息):同样全买
    s2, st2, sess2 = _mk(gold=4)
    st2.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1),
                ShopCard(x=1, faction='仙舟', name='爻光', cost=1),
                ShopCard(x=2, faction='仙舟', name='椒丘', cost=1)]
    buys2 = [a for a in s2.decide_prep(st2, sess2, None)
             if isinstance(a, BuyCard)]
    assert len(buys2) == 3


def test_floor_full_gold_conserves():
    """金 50(满息):floor=50,种子也不买(息律)。"""
    s, st, sess = _mk(gold=50)
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1)]
    assert not [a for a in s.decide_prep(st, sess, None)
                if isinstance(a, BuyCard)]


def test_p2_locked_buys_line_pieces():
    """P2 锁线场景:姬子(3费)+砂金(2费)同店金 22 →
    都买(22-5=17≥floor;「结果就买了一个」回归锁)。"""
    s, st, sess = _mk(gold=22, plane=2)
    st.bench = [BenchChar(slot=0, char_id='三月七', faction='列车同行')]
    st.deployed = [BenchChar(slot=1, char_id='三月七',
                             faction='列车同行')]
    st.shop = [ShopCard(x=0, faction='列车同行', name='姬子·启行',
                        cost=3),
               ShopCard(x=1, faction='护盾', name='砂金', cost=2)]
    s.update_target(st, sess, None)    # 姬子在店+买得起 → 锁线
    buys = [a for a in s.decide_prep(st, sess, None)
            if isinstance(a, BuyCard)]
    names = [b.card.name for b in buys]
    assert '姬子·启行' in names and '砂金' in names


# ===== 装备轮转(r232)=====

def test_equip_rotation_no_comp():
    """comp=None:3 角色 5 件 → 轮转(每人 1 件一圈),
    不灌满前排第一人(用户「装备都给了前台1」回归锁)。
    ADR-0265 语义修正:owned 原含 光能电池/以太钻头/折叠小刀
    (合成保留组件,P1 现不入穿戴池)——轮转语义与组件无关,
    换非组件名保持原断言;组件保留行为另测(test_cw_r4xx)。"""
    dep = [BenchChar(slot=1, char_id='飞霄', position_pref='front'),
           BenchChar(slot=2, char_id='真理医生', position_pref='front'),
           BenchChar(slot=3, char_id='翡翠', position_pref='back')]
    owned = ['蓄能帆', '拆装扳手', '永动机', '冷笑话引擎', '垃圾袋']
    alloc = equip_allocation(None, dep, owned)
    first = [a[0] for a in alloc[:3]]
    assert len(set(first)) == 3        # 前三件给三个人(轮转)
    assert alloc[0][0] == '飞霄'       # 前排先(顺序保留)


def test_equip_rotation_caps_at_capacity():
    """轮转不超容量:每人 3 件上限,5 件×3 人 → 全分完但
    单人不连续吃 3 件。"""
    dep = [BenchChar(slot=1, char_id='飞霄', position_pref='front'),
           BenchChar(slot=2, char_id='翡翠', position_pref='back')]
    owned = ['a', 'b', 'c', 'd']
    alloc = equip_allocation(None, dep, owned)
    got = dict.fromkeys(('飞霄', '翡翠'), 0)
    for n, _ in alloc:
        got[n] += 1
    assert got['飞霄'] <= 3 and got['翡翠'] <= 3
    assert sum(got.values()) == 4
