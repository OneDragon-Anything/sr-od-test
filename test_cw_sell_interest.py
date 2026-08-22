"""r238 卖散凑息测试(用户「节点4没卖出凑30金」)。"""
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    SellBench,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(gold: int = 28):
    s = LineStrategy()
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 1, 5, gold, 90
    sess = StrategySession()
    sess.v2_state = None
    sess.locked_line = None
    sess.bridge_id = None
    return s, st, sess


def test_sells_to_cross_interest_tier():
    """金 28 + bench 散牌(退款 1+1)→ 卖散凑 30(组合退款跨档)。
    (用户实跑场景:bench 7 张,差 2 到 30 档。)
    (原用例飞霄 r353[8add6d5e]入 hunt3 fixed → 保护名单不可卖,
    余黑塔退款 1 不跨档——换非保护散件黑塔+翡翠锁跨档语义。)"""
    s, st, sess = _mk(gold=28)
    st.bench = [BenchChar(slot=0, char_id='黑塔', faction='银河学者', star=1),
                BenchChar(slot=1, char_id='翡翠', faction='公司', star=1)]
    st.board = {'仙舟': 1}    # 在场阵营保护
    st.shop = []              # 无可买(纯卖凑息场景)
    acts = s.decide_prep(st, sess, None)
    sells = [a for a in acts if isinstance(a, SellBench)]
    assert len(sells) >= 1    # 至少卖 1 张(28+1+1=30 跨档)


def test_no_sell_when_protected():
    """保护名单(桥 fixed/core+锁线名单)不卖。"""
    s, st, sess = _mk(gold=28)
    st.bench = [BenchChar(slot=0, char_id='藿藿', faction='仙舟', star=1),
                BenchChar(slot=1, char_id='三月七', faction='列车同行', star=1)]
    st.shop = []
    acts = s.decide_prep(st, sess, None)
    assert not [a for a in acts if isinstance(a, SellBench)]


def test_no_sell_above_floor():
    """金 ≥50:满息不卖(息已封顶)。"""
    s, st, sess = _mk(gold=50)
    st.bench = [BenchChar(slot=0, char_id='飞霄', faction='狼狩', star=1)]
    acts = s.decide_prep(st, sess, None)
    assert not [a for a in acts if isinstance(a, SellBench)]


def test_no_sell_on_board_faction():
    """在场阵营的 bench 牌不卖(不拆在场羁绊)。"""
    s, st, sess = _mk(gold=28)
    st.bench = [BenchChar(slot=0, char_id='飞霄', faction='狼狩', star=1)]
    st.board = {'狼狩': 1}
    acts = s.decide_prep(st, sess, None)
    assert not [a for a in acts if isinstance(a, SellBench)]
