"""r100i 测试:ready 但切换被拦(死线/断供)时保持双轨(信号1/2 关)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.cw_state import GameState, ShopCard
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.default_strategy import DefaultCwStrategy


class _Cfg:
    faction_priority: list[str] = []
    character_priority: list[str] = []


def _mk(lead_scores, excluded, shop_factions):
    strat = DefaultCwStrategy()
    sess = strat.create_session(_Cfg())
    from sr_od.application.currency_war.cw_transition import CommitSignals
    cs = CommitSignals()
    for src, m in lead_scores.items():
        cs.add(src, m)
    sess.commit_signals = cs
    sess.drought_excluded = list(excluded)
    sess.target_comp = next(c for c in COMP_LIBRARY if c.name == '专家桑博DOT')
    st = GameState(gold=41, hp=90, level=5, round_num=7, plane=1,
                   board={'持续伤害': 2},
                   shop=[ShopCard(x=1, faction=f, name='', cost=1) for f in shop_factions])
    return strat, sess, st


def test_ready_blocked_keeps_dual_track():
    """ready 但 leader(≠target)被排除名单拦 → 保持双轨(局22 r7 泄漏修复)。

    注:leader==target 时 committed=True 是正确语义(定型到现线)——测试里
    target=专家桑博DOT、leader 也构造为专家桑博DOT 会走那条;要测泄漏窗口
    必须让 leader 是**另一条**被排除的线(如 万敌单C 在排除名单,target=专家桑博DOT)。
    """
    strat, sess, st = _mk(
        {'briefing_affix': {'万敌单C': 0.9}, 'invest_strategy': {'万敌单C': 1.0},
         'invest_env': {'万敌单C': 0.9}, 'shop_supply': {'万敌单C': 1.0}},
        excluded=['万敌单C'], shop_factions=['减益'])
    strat.update_target(st, sess, _Cfg())
    assert st.dual_track_phase is True, 'leader 被拦(≠target)时必须保持双轨——否则信号1 全开=泄漏窗口'
    assert sess.target_comp.name == '专家桑博DOT', 'target 不被信号1 摇走'


def test_ready_switchable_commits():
    """ready 且 leader 可切 → 定型(双轨结束,target 切到 leader)。"""
    strat, sess, st = _mk(
        {'briefing_affix': {'万敌单C': 0.9}, 'invest_strategy': {'万敌单C': 1.0},
         'invest_env': {'万敌单C': 0.9}, 'shop_supply': {'万敌单C': 1.0}},
        excluded=[], shop_factions=['夜之半神'])
    strat.update_target(st, sess, _Cfg())
    assert st.dual_track_phase is False
    assert sess.target_comp.name == '万敌单C'


def test_not_ready_stays_dual():
    """未 ready → 双轨(原语义)。"""
    strat, sess, st = _mk({'briefing_affix': {'万敌单C': 0.5}}, excluded=[], shop_factions=['夜之半神'])
    strat.update_target(st, sess, _Cfg())
    assert st.dual_track_phase is True
