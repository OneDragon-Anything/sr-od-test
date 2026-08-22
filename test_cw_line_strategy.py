"""LineStrategy 测试(Phase A Day 9;评审修正后扩充:
四象限全覆盖+状态迁移+中文节点类型回归)。"""
from sr_od.application.currency_war.cw_performance import RoundOutcome
from sr_od.application.currency_war.cw_phase_machine import (
    MODE_ECONOMY,
    MODE_WAR,
    initial_state,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    LevelUp,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(hp: int = 100, gold: int = 50, plane: int = 1) -> (
        tuple[LineStrategy, GameState, StrategySession]):
    s = LineStrategy()
    st = GameState()
    st.plane, st.level, st.gold, st.hp = plane, 5, gold, hp
    sess = StrategySession()
    sess.v2_state = initial_state()
    sess.locked_line = None
    sess.bridge_id = None
    return s, st, sess


def _card(name: str, cost: int = 1, faction: str = '?') -> ShopCard:
    return ShopCard(x=0, faction=faction, name=name, cost=cost)


def test_registered_metadata():
    assert LineStrategy.STRATEGY_ID == 'line_v2'


def test_session_fields_formal():
    """B-bg 回归:扩展态是正式字段(未走 on_match_start 也不崩)。"""
    sess = StrategySession()
    assert sess.v2_state is None    # B1:default 局 None(非假 economy)
    assert sess.locked_line is None
    assert sess.bridge_id is None


def test_update_target_locks_on_core():
    s, st, sess = _mk()
    st.shop = [_card('姬子·启行', 3, '列车同行')]
    s.update_target(st, sess, None)
    assert sess.locked_line == 'jizi_train'
    assert sess.bridge_id is None    # N4:锁线清桥
    # S4:锁线写伪 comp(部署桥接——名字带 v2: 前缀)
    assert sess.target_comp is not None
    assert sess.target_comp.name == 'v2:jizi_train'
    assert '姬子·启行' in sess.target_comp.core_chars


def test_update_target_bridge_when_unlocked():
    """桥线看 owned(bench+deployed);商店卡不算 owned。"""
    s, st, sess = _mk()
    st.shop = [_card('爻光'), _card('藿藿')]
    s.update_target(st, sess, None)
    assert sess.locked_line is None and sess.bridge_id is None
    st.bench = [BenchChar(slot=0, char_id='爻光'),
                BenchChar(slot=1, char_id='藿藿')]
    s.update_target(st, sess, None)
    assert sess.bridge_id == 'xianzhou_dot'


def test_economy_buys_line_cards():
    """经济:买线内件,不买线外件。
    (原用例卡芙卡 r353 起入 dot_belog core → _line_wants 的
    桥 core 通道(r245)放行——换真线外件黑塔锁原语义。)"""
    s, st, sess = _mk(gold=60)
    st.shop = [_card('瓦尔特', 3), _card('黑塔', 3)]
    sess.locked_line = 'jizi_train'
    acts = s.decide_prep(st, sess, None)
    names = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert '瓦尔特' in names and '黑塔' not in names


def test_economy_respects_interest_floor():
    s, st, sess = _mk(gold=50)
    st.shop = [_card('瓦尔特', 3)]
    sess.locked_line = 'jizi_train'
    assert not [a for a in s.decide_prep(st, sess, None)
                if isinstance(a, BuyCard)]


def test_economy_buys_carry():
    """经济模式也买 carry(「卡30利息慢D」——carry 购买
    不是战力模式专属,评审 S4)。"""
    s, st, sess = _mk(gold=60)
    st.shop = [_card('姬子·启行', 3)]
    sess.locked_line = 'jizi_train'
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, BuyCard) for a in acts)


def test_war_mode_buys_up_to_2_with_floor():
    """战力:最多 2 张,地板 30(战力≠panic 保息)。"""
    s, st, sess = _mk(gold=60)
    sess.v2_state = (MODE_WAR, False, False, 0, 0, 0, 0, 0)
    st.shop = [_card('瓦尔特', 3), _card('符玄', 3), _card('星期日', 3)]
    sess.locked_line = 'jizi_train'
    acts = s.decide_prep(st, sess, None)
    buys = [a for a in acts if isinstance(a, BuyCard)]
    assert len(buys) == 2
    assert st.gold - sum(b.card.cost for b in buys) >= 30


def test_catchup_mode_level_up():
    """追赶:升人口置顶(金够时)。"""
    s, st, sess = _mk(gold=40)
    sess.v2_state = (MODE_ECONOMY, False, True, 0, 0, 0, 0, 0)
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, LevelUp) for a in acts)


def test_emergency_buys_with_rebirth_floor():
    s, st, sess = _mk(hp=20, gold=25)
    st.shop = [_card('瓦尔特', 3)]
    sess.locked_line = 'jizi_train'
    acts = s.decide_prep(st, sess, None)
    buys = [a for a in acts if isinstance(a, BuyCard)]
    assert buys and st.gold - buys[0].card.cost >= 20


def test_deck_compression_1cost():
    """压缩:1费净0——线内件或冷启动凑对(同阵营)。"""
    s, st, sess = _mk(gold=55)
    st.shop = [_card('椒丘', 1, faction='持续伤害')]
    sess.bridge_id = None
    # 冷启动:board 有同阵营 → 凑对可买
    st.board = {'持续伤害': 1}
    assert any(isinstance(a, BuyCard) and a.card.name == '椒丘'
               for a in s.decide_prep(st, sess, None))


def test_state_transition_miss_to_war():
    """状态迁移:连续 miss×2 → war(滞回进入)。"""
    s = LineStrategy()
    sess = StrategySession()
    sess.v2_state = initial_state()
    s._feed(sess, 'E1_miss')
    assert sess.v2_state[0] == MODE_ECONOMY   # 1 次不够
    s._feed(sess, 'E1_miss')
    assert sess.v2_state[0] == MODE_WAR       # 2 次切


def test_state_transition_pass_to_economy():
    s = LineStrategy()
    sess = StrategySession()
    sess.v2_state = (MODE_WAR, False, False, 0, 0, 0, 0, 0)
    for _ in range(3):
        s._feed(sess, 'node_pass')
    assert sess.v2_state[0] == MODE_ECONOMY


def test_on_round_end_chinese_node_type():
    """B1 回归:遭遇节点用中文 '遭遇'(英文死码修复锁);
    姬子 P1 无形态键(p2p3 只有 P2/P3)→ node_pass 不炸。"""
    s, st, sess = _mk()
    sess.locked_line = 'jizi_train'
    obs = RoundOutcome(round_num=1, plane=1, node_type='遭遇',
                       comp_tag='jizi')
    s.on_round_end(st, sess, None, obs)
    assert sess.v2_state[0] == MODE_ECONOMY


def test_lock_preserves_mode_economy():
    """S1 回归:E7_lock 解包保留当前 mode(锁线不切战力——
    开局锁线应攒钱,与「卡30利息慢D」对齐)。"""
    s = LineStrategy()
    sess = StrategySession()
    sess.v2_state = initial_state()   # economy
    s._feed(sess, 'E7_lock')
    assert sess.v2_state[0] == MODE_ECONOMY


def test_ensure_state_none_guard():
    """终审 B1 回归:v2_state=None 的 session 首次喂事件
    不炸(续跑路径守卫)。"""
    s = LineStrategy()
    sess = StrategySession()
    assert sess.v2_state is None
    s._feed(sess, 'node_pass')        # 之前:None 解包 TypeError
    assert sess.v2_state is not None
    assert sess.v2_state[0] == MODE_ECONOMY


def test_drive_of_dot_fallback_unknown():
    """B3 回归:兜底线查表用 unknown(最保守 ×2.0)。"""
    sess = StrategySession()
    sess.locked_line = 'dot_fallback'
    assert LineStrategy._drive_of(sess) == 'unknown'
