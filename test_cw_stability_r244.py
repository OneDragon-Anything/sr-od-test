"""r244 稳定性修复测试:D 牌判据 + P2 桥可达。"""
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(gold: int = 40, plane: int = 1):
    s = LineStrategy()
    st = GameState()
    st.plane, st.level, st.gold, st.hp = plane, 6, gold, 80
    sess = StrategySession()
    sess.v2_state = None
    sess.locked_line = None
    sess.bridge_id = None
    return s, st, sess


def test_refresh_triggers_without_line_cards():
    """r244 风险3:shop 全是非线内件(有名+买得起)→ 必须刷
    (旧判据任何有名卡都拦刷新=D 通道死码)。"""
    s, st, sess = _mk(gold=40)
    st.shop = [ShopCard(x=0, faction='夜之半神', name='万敌', cost=1),
               ShopCard(x=1, faction='银河学者', name='黑塔', cost=1)]
    out = s._maybe_refresh(st, sess, rem=40)
    assert any(isinstance(a, RefreshShop) for a in out)


def test_refresh_blocked_with_line_card():
    """shop 有线内件(桥 fixed 藿藿)→ 不刷(省钱买件)。"""
    s, st, sess = _mk(gold=40)
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1)]
    out = s._maybe_refresh(st, sess, rem=40)
    assert not out


def test_p2_bridge_not_stomped_by_fallback():
    """r244 风险1:P2 有 CARRY(fixed 齐)→ 不被兜底吞。
    ⚠ 姬子在手时锁线信号先触发(可负担门:owned 即锁)——
    所以「P2 桥不被吞」的真实场景=姬子刚买还没锁(同一
    update_target 内先桥后锁的顺序)或 P2 池扩容后。
    本测试锁 pick_bridge 直调语义(P2 桥可达性),池设计
    缺陷(单桥+fixed 全含才成立)记 Phase B 扩池。"""
    from sr_od.application.currency_war.cw_bridge_pool import pick_bridge
    b = pick_bridge(['姬子·启行', '三月七'], 'P2')
    assert b is not None and b.bridge_id == 'train4_shield3'
    # update_target 侧:无 CARRY 的 P2 不落兜底(前半程等待)
    s, st, sess = _mk(gold=40, plane=2)
    st.round_num = 2
    st.bench = [BenchChar(slot=0, char_id='三月七',
                          faction='列车同行')]
    s.update_target(st, sess, None)
    assert sess.locked_line is None    # 不被兜底吞(等信号)


def test_p2_late_no_direction_falls_back():
    """P2 后半程(r>=4)无桥无信号 → DOT 兜底(可达性保留)。"""
    s, st, sess = _mk(gold=40, plane=2)
    st.round_num = 5
    st.bench = [BenchChar(slot=0, char_id='黑塔', faction='银河学者')]
    s.update_target(st, sess, None)
    assert sess.locked_line == 'dot_fallback'


def test_p2_early_no_direction_waits():
    """P2 前半程(r<4)无桥无信号 → 不急着落兜底(还有时间)。"""
    s, st, sess = _mk(gold=40, plane=2)
    st.round_num = 2
    st.bench = [BenchChar(slot=0, char_id='黑塔', faction='银河学者')]
    s.update_target(st, sess, None)
    assert sess.locked_line is None
    assert sess.bridge_id is None
