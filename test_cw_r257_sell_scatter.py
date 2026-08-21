"""r257 P1 末卖散腾囤位测试。"""
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    SellBench,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(plane=1, round_num=8, bench_ids=None):
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num = plane, round_num
    st.level, st.gold, st.hp = 7, 55, 70
    st.bench = [BenchChar(slot=i + 1, char_id=cid, faction='散')
                for i, cid in enumerate(bench_ids or [])]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'jizi_train'
    sess.bridge_id = None
    return s, st, sess


def test_p1_late_bench_full_sells_scatter():
    """P1r8 bench 8 满:卖 1 个散件(万敌)腾到 7。"""
    s, st, sess = _mk(round_num=8,
                     bench_ids=['万敌', '银枝', '银狼', '娜塔莎',
                                '赛飞儿', '飞霄', '黑塔', '乱破'])
    sells = s._sell_scatter_for_precache(st, sess)
    assert len(sells) == 1 and isinstance(sells[0], SellBench)


def test_protected_not_sold():
    """保护件(三月七=jizi opportunistic/砂金=桥 core)不卖。"""
    s, st, sess = _mk(round_num=8,
                     bench_ids=['三月七', '砂金', '万敌', '银枝',
                                '银狼', '娜塔莎', '赛飞儿', '黑塔'])
    sells = s._sell_scatter_for_precache(st, sess)
    sold_idx = {sl.bench_idx for sl in sells}
    # 前两个(保护件)绝不被卖
    assert 0 not in sold_idx and 1 not in sold_idx


def test_p1_early_no_sell():
    """P1 早期(r<7)不触发。"""
    s, st, sess = _mk(round_num=5,
                     bench_ids=['万敌'] * 9)
    assert s._sell_scatter_for_precache(st, sess) == []


def test_bench_ok_no_sell():
    """bench ≤7(门内)不卖。"""
    s, st, sess = _mk(round_num=8,
                     bench_ids=['万敌', '银枝', '银狼', '娜塔莎',
                                '赛飞儿', '黑塔', '乱破'])
    assert s._sell_scatter_for_precache(st, sess) == []
