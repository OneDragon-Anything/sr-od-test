# -*- coding: utf-8 -*-
"""r406(ADR-0266,压测经济批 [12]/①残差):升级门息引擎前置。

LevelUp 资格(lv≥5 追级段)= 时点金过门 **且** 息引擎已立
(本局曾达满息 或 本笔升级花完后金仍 ≥50)——消灭「每轮 40-50
徘徊反复够升级门槛、50 永远攒不满」的追级局(压测 25.9% 局终局
未满 50,14/15 从未攒到 50)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import (
    GameState,
    LevelUp,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)
from sr_od.application.currency_war.cw_sim_checks import (
    check_levelup_interest_engine_gate,
)


def _mk(rnd, gold, level=6):
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level, st.gold, st.hp = 1, rnd, level, gold, 80
    st.bench = []
    st.board = {'仙舟': 2, '列车同行': 2}
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'feiying_joy'
    return s, st, sess


def test_boss_breaker_rejects_lvup_engine_not_established() -> None:
    """r6 金 46 lv6 从未满息:总成本门过(budget=36≥20)但息引擎
    未立(46-20=26<50 且本局未曾 ≥50)→ 拒 LevelUp,金攒息
    (压测追级局形态:每轮 40-50 徘徊反复够升级门槛)。"""
    s, st, sess = _mk(rnd=6, gold=46)
    st.xp_progress = (0, 20)   # 需 5 击 = 20 金(总成本门过)
    assert not sess.v2_ever_full_interest
    acts = s.decide_prep(st, sess, None)
    lvs = [a for a in acts if isinstance(a, LevelUp)]
    assert not lvs, f'息引擎未立(花完<50)不得追级: {[type(a).__name__ for a in acts]}'


def test_boss_breaker_allows_lvup_post_cost_ge_50() -> None:
    """从未满息但花完仍 ≥50(富余升级,[17] 满息即花)→ 放行。"""
    s, st, sess = _mk(rnd=6, gold=56)
    st.xp_progress = (0, 20)   # 56-20=36 <50 → 拒
    acts = s.decide_prep(st, sess, None)
    assert not [a for a in acts if isinstance(a, LevelUp)]
    s2, st2, sess2 = _mk(rnd=6, gold=72)
    st2.xp_progress = (0, 20)  # 72-20=52 ≥50 → 放行
    acts2 = s2.decide_prep(st2, sess2, None)
    assert any(isinstance(a, LevelUp) for a in acts2), \
        '花完仍 ≥50 的富余升级应放行'


def test_boss_breaker_allows_lvup_when_engine_established() -> None:
    """息引擎已立的两条放行道:
    ① 曾满息(latch)→ 放行(旧总成本门语义保持);
    ② 从未满息但花完仍 ≥50(富余升级,[17] 满息即花)→ 放行。
    首次到 56 的当轮(36<50)→ 拒——采样在分发后,自家不解锁。"""
    # ① latch 道
    s, st, sess = _mk(rnd=6, gold=46)
    st.xp_progress = (0, 20)
    sess.v2_ever_full_interest = True   # 本局曾满息
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, LevelUp) for a in acts), \
        '息引擎已立(曾满息)应放行追级'
    # ② 富余道:72-20=52 ≥50
    s2, st2, sess2 = _mk(rnd=6, gold=72)
    st2.xp_progress = (0, 20)
    acts2 = s2.decide_prep(st2, sess2, None)
    assert any(isinstance(a, LevelUp) for a in acts2), \
        '花完仍 ≥50 的富余升级应放行'
    # 首次 56(36<50,从未满息)→ 拒;且采样后 latch 置位(下轮放行)
    s3, st3, sess3 = _mk(rnd=6, gold=56)
    st3.xp_progress = (0, 20)
    acts3 = s3.decide_prep(st3, sess3, None)
    assert not [a for a in acts3 if isinstance(a, LevelUp)], \
        '首次达 56 的当轮自家采样不解锁(分发后采样)'
    assert sess3.v2_ever_full_interest, '分发后采样应置 latch'


def test_lv4_relaxed_gate_exempt() -> None:
    """lv<5(r263 过渡成型基线)不受息引擎门辖:金 30 照升。"""
    s, st, sess = _mk(rnd=4, gold=30, level=4)
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, LevelUp) for a in acts), \
        'lv<5 宽松门保留([13] lv5 基线;ADR-0266 豁免边界)'


def test_ever_full_sampling_in_decide_prep() -> None:
    """时点金 ≥50 → session.v2_ever_full_interest 置位(局内单调)。"""
    s, st, sess = _mk(rnd=3, gold=55, level=6)
    s.decide_prep(st, sess, None)
    assert sess.v2_ever_full_interest, '时点金 55 应采样为曾满息'


def test_catchup_engine_gate() -> None:
    """追赶升人口同辖:从未满息且花完 <50 → 不升(buys 照跑)。"""
    s, st, sess = _mk(rnd=6, gold=40)
    sess.v2_state = ('economy', False, True, 0, 0, 0, 0, 0)  # cat=True
    acts = s.decide_prep(st, sess, None)
    assert not [a for a in acts if isinstance(a, LevelUp)], \
        '追赶息引擎未立不升'


def test_check_levelup_interest_engine_gate() -> None:
    """检查项双向锁:追级违规账本报、合法账本不报。"""
    bad = [{'plane': 1, 'round_num': 4, 'gold': 35,
            'state': {'level': 6}, 'actions': [],
            'sim': {'shop_waves': [{'gold': 38}]}},
           {'plane': 1, 'round_num': 5, 'gold': 42,
            'state': {'level': 6},
            'actions': [{'__type__': 'LevelUp', 'cost': 4}],
            'sim': {'shop_waves': [{'gold': 46}]}},
           {'plane': 1, 'round_num': 6, 'gold': 30,
            'state': {'level': 6}, 'actions': [],
            'sim': {'shop_waves': [{'gold': 32}]}}]
    assert check_levelup_interest_engine_gate(bad), '追级违规应报'

    ok_ever_full = [{'plane': 1, 'round_num': 3, 'gold': 55,
                     'state': {'level': 5}, 'actions': [],
                     'sim': {'shop_waves': [{'gold': 55}]}},
                    {'plane': 1, 'round_num': 5, 'gold': 42,
                     'state': {'level': 6},
                     'actions': [{'__type__': 'LevelUp', 'cost': 4}],
                     'sim': {'shop_waves': [{'gold': 46}]}}]
    assert not check_levelup_interest_engine_gate(ok_ever_full), \
        '曾满息(r3 达 55)后的追级合法'

    ok_low_level = [{'plane': 1, 'round_num': 3, 'gold': 20,
                     'state': {'level': 4},
                     'actions': [{'__type__': 'LevelUp', 'cost': 4}],
                     'sim': {'shop_waves': [{'gold': 24}]}}]
    assert not check_levelup_interest_engine_gate(ok_low_level), \
        'lv<5 宽松门不辖'
