"""P0-1 锁线购买口径切换修复批测试(双源对齐)。

根因(实机 g_20260905_035710 复盘 §6 候选 1 + 策略审查 20260905-0520
定性 = 实现断裂非设计缺口):锁定帧(locked_comp 非空)的买入 line
membership 旧按 ``predicates.line_members(target_comp)``
(comp core∪shared)判,与锁定口径采购集(``locked_buy_scope`` = 含
form_tiers∪sub_tiers 档位键阵营∪流派成员)双源不一致——锁「列车同行」
后同阵营成员(丹恒·饮月/开拓者·欢愉,非该 comp core∪shared)被判
``non_line``、M2 骨架义务买入被跳过。

修复 = 锁定帧买入判定消费 ``cw_intention.locked_buy_membership()``
(单一源,内部委托 ``locked_buy_scope``);未锁帧(含 P1 配方锁帧,
locked_comp 恒空,ADR-0357)维持既有口径,P1 无锁态行为零变化。

锁契约(测试纪律第 8 条):本文件锁「口径一致性」——锁定帧的拒因
与义务买入集合必须与锁定采购集同源;不锁具体买入数与经济面数值。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    locked_buy_membership,
    locked_buy_scope,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop

# ===== 基建 =====


def _cfg():
    return SimpleNamespace(ev_arm='full')


def _session(target_comp, ist: IntentionState | None) -> StrategySession:
    s = StrategySession()
    s.cw4_counters = {}
    s.target_comp = target_comp
    if ist is not None:
        s.v3_intention = ist
    return s


def _state(gold: int, shop_cards: list[ShopCard], plane: int = 2,
           level: int = 7) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2, hp=60)
    st.plane = plane
    st.shop = shop_cards
    st.bench = []
    st.deployed = []
    return st


def _card(name: str, cost: int, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _locked_ist(comp_name: str = '列车同行') -> IntentionState:
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = comp_name
    ist.lock_plane = 2
    return ist


# ===== 事故帧锁:P2 锁线列车同行 + 锁内阵营成员在售 =====


class TestLockedFrameBuyMembership:
    """锁定帧(locked_comp 非空):买入判定消费锁定口径(单一源)。"""

    def test_incident_frame_dan_heng_bought_as_line_member(self):
        """事故帧直译(P2 锁「列车同行」+ 在售丹恒·饮月 2 金):丹恒·饮月
        属列车同行阵营但非该 comp core∪shared——修复前被判 non_line 跳过,
        修复后经 M2 义务买入(reason=m2_line_member,不落 non_line 拒因)。"""
        st = _state(gold=30, shop_cards=[_card('丹恒·饮月', 2)])
        sess = _session(get_comp('列车同行'), _locked_ist())
        act = shop.decide_shop_action(st, sess, _cfg())
        assert isinstance(act, BuyCard), act
        assert act.card.name == '丹恒·饮月'
        assert act.reason == 'm2_line_member'

    def test_locked_faction_member_not_non_line_in_rejects(self):
        """拒因遥测同源:锁定帧在售开拓者·欢愉(列车同行阵营 4★,复盘
        p2r4 全局最贵拒绝件)不得标 ``non_line``——进入线内缺口件分类
        (missing_*,金席俱足未发射才允许 missing_no_path)。"""
        st = _state(gold=30, shop_cards=[
            _card('丹恒·饮月', 2), _card('开拓者·欢愉', 4, star=4)])
        sess = _session(get_comp('列车同行'), _locked_ist())
        shop.decide_shop_action(st, sess, _cfg())
        rejects = getattr(sess, 'cw4_shop_rejects', {}) or {}
        assert '开拓者·欢愉' in rejects
        assert rejects['开拓者·欢愉'] != 'non_line'
        assert rejects['开拓者·欢愉'].startswith('missing_')

    def test_membership_single_source_matches_locked_buy_scope(self):
        """单一源锚:locked_buy_membership(锁定帧) == locked_buy_scope
        (禁第二份采购集派生;含阵营∪流派全集成员的直算对拍)。"""
        ist = _locked_ist()
        scope = locked_buy_scope(ist)
        assert locked_buy_membership(ist) == scope
        assert '丹恒·饮月' in scope       # 阵营成员在采购集(W65 全集口径)
        assert '开拓者·欢愉' in scope


# ===== P1 无锁态回归锁(行为不变)=====


class TestUnlockedFrameUnchanged:
    """未锁帧(locked_comp 空,含 P1 配方锁帧):口径维持
    line_members(target_comp)=core∪shared,零变化。"""

    def test_p1_unlocked_faction_member_still_non_line(self):
        """同 comp(列车同行)、仅锁标志不同(ist unlocked/locked_comp 空
        = P1 配方锁帧形态,ADR-0357):丹恒·饮月不进线内采购集——拒因
        维持 ``non_line``,且无 m2_line_member 义务买入(口径锁,非全行为
        冻结;EV 面是否买属 EV 判据辖域)。"""
        st = _state(gold=30, shop_cards=[_card('丹恒·饮月', 2)], plane=1)
        ist = IntentionState()          # unlocked,locked_comp=''
        sess = _session(get_comp('列车同行'), ist)
        act = shop.decide_shop_action(st, sess, _cfg())
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'm2_line_member')
        rejects = getattr(sess, 'cw4_shop_rejects', {}) or {}
        assert rejects.get('丹恒·饮月') == 'non_line'

    def test_membership_none_when_unlocked(self):
        """正典函数边界:unlocked / p1_pair-only(locked_comp 恒空)/
        ist 缺失 ⇒ None(消费方维持既有口径的开关锚)。"""
        assert locked_buy_membership(None) is None
        assert locked_buy_membership(IntentionState()) is None
        pair_only = IntentionState()
        pair_only.p1_pair = ('仙舟', '持续伤害')   # P1 配方锁帧
        assert locked_buy_membership(pair_only) is None

    def test_membership_none_when_ist_lacks_locked_comp(self):
        """weak/降格等 locked_comp 空态 ⇒ None(约束基准不存在的口径,
        与 locked_buy_scope docstring 弱意向语义一致)。"""
        ist = IntentionState()
        ist.phase = 'weak'
        assert locked_buy_membership(ist) is None
