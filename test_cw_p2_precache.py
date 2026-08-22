"""r247 P2 预囤测试(第九轮对抗审查的 11 条矩阵核心项)。"""
from sr_od.application.currency_war.cw_line_library_v1 import line_of
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


def _mk(plane: int = 1, round_num: int = 8, gold: int = 55,
        hp: int = 70, bench_n: int = 5):
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num = plane, round_num
    st.level, st.gold, st.hp = 7, gold, hp
    st.bench = [BenchChar(slot=i, char_id='件', faction='仙舟')
                for i in range(bench_n)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'jizi_train'
    sess.bridge_id = None
    return s, st, sess


def test_p1_late_buys_p2_core():
    """P1r8 金55:预囤砂金(P2 桥 core)——解法 A 主场景。"""
    s, st, sess = _mk(round_num=8, gold=55)
    st.shop = [ShopCard(x=0, faction='公司', name='砂金', cost=2)]
    assert s._line_wants(st.shop[0], st, sess)


def test_p1_early_no_precache():
    """P1r5(早于门 7):不囤(P1 前中期该专注当前形态)。"""
    s, st, sess = _mk(round_num=5, gold=55)
    st.shop = [ShopCard(x=0, faction='公司', name='砂金', cost=2)]
    assert not s._line_wants(st.shop[0], st, sess)


def test_emergency_no_precache():
    """应急(HP≤25):不囤(保命优先)。"""
    s, st, sess = _mk(round_num=8, gold=55, hp=20)
    sess.v2_state = ('economy', True, False, 0, 0, 0, 0, 0)
    st.shop = [ShopCard(x=0, faction='公司', name='砂金', cost=2)]
    assert not s._line_wants(st.shop[0], st, sess)


def test_bench_full_no_precache():
    """bench 8(>7):不囤(留 3合1 空间)。"""
    s, st, sess = _mk(round_num=8, gold=55, bench_n=8)
    st.shop = [ShopCard(x=0, faction='公司', name='砂金', cost=2)]
    assert not s._line_wants(st.shop[0], st, sess)


def test_dot_line_no_precache():
    """锁 dot_fallback(P2 键持续伤害系,与列车桥不同向):
    不囤列车桥件(方向错配防死库存)——r249b 集合相交判据
    (严于字符串包含)。"""
    s, st, sess = _mk(round_num=8, gold=55)
    sess.locked_line = 'dot_fallback'
    st.shop = [ShopCard(x=0, faction='公司', name='砂金', cost=2)]
    assert not s._line_wants(st.shop[0], st, sess)


def test_precache_not_deployed():
    """R7(语义修订):囤件**可以上场**——from_line(plane=1)
    回退 P2 键(jizi 无 P1 键)→ 伪 comp factions 含护盾 →
    砂金(护盾 flow)命中 deploy 判据。这不是缺陷:P1 末
    多 1-2 个 2 费 body 是增益(r4 局 P1 HP75 过 boss 就有
    砂金在场);「囤件」语义=进 P2 立即可上,不是死囤 bench。
    本测试锁该语义(防未来误改「囤件强制留 bench」)。"""
    from sr_od.application.currency_war.strategies.line_strategy import (
        _LinePseudoComp,
    )
    line = line_of('jizi_train')
    comp = _LinePseudoComp.from_line(line, plane=1)
    # P1 期伪 comp 即含护盾(桥件在 P1 末上场合法)
    assert '护盾' in comp.factions


def test_p2_precache_respects_floor():
    """金 55(满息):floor=50 → 55-2=53 ≥50 可囤(只动溢出金)。"""
    s, st, sess = _mk(round_num=8, gold=55)
    st.shop = [ShopCard(x=0, faction='公司', name='砂金', cost=2)]
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, BuyCard) and a.card.name == '砂金'
               for a in acts)


def test_p2_precache_below_floor_rejected():
    """r8 处于 boss 破息窗(r278 f556e8c0 破息投资;r285 e2864a71
    前移 r5):地板 = _BOSS_BREAKER_FLOOR(10),非满息 50——金 51
    买砂金是意图内(破息投资;满息上界由 respects_floor 锁)。
    本测试锁守卫下界:金 11(11-2=9 <10)不囤(boss 地板仍守)。"""
    s, st, sess = _mk(round_num=8, gold=11)
    # bench 全用保护件(仙舟桥 core 名单内)→ 无可卖
    st.bench = [BenchChar(slot=i, char_id='藿藿', faction='仙舟')
                for i in range(5)]
    st.shop = [ShopCard(x=0, faction='公司', name='砂金', cost=2)]
    acts = s.decide_prep(st, sess, None)
    assert not [a for a in acts
                if isinstance(a, BuyCard) and a.card.name == '砂金']
    # 破息窗内(51-2=49 ≥10)放行——锁窗语义
    st.gold = 51
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, BuyCard) and a.card.name == '砂金'
               for a in acts)
