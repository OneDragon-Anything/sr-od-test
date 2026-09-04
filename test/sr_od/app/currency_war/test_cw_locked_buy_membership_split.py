"""锁定帧买面口径拆分批测试(锁定采购集只灌买入义务面)。

背景(实机对局 g_20260905_035710 复盘 + 合并对抗审计):锁线帧
(locked_comp 非空)的买入 line membership 旧按
``predicates.line_members(target_comp)``(comp core∪shared)判,与锁定
采购集(``_line_hoard`` = core∪shared∪替班∪form_tiers/sub_tiers 档位键
命中的阵营∪流派全集成员,W65 口径)双源不一致——锁「列车同行」后同
阵营成员被判 ``non_line``、M2 骨架义务买入被跳过。

修复形态(经审计裁决收窄辖域):锁定采购集**只**灌买入义务消费面
(M2 缺员循环 / M2b 合并完成买入 / 拒因遥测 / EV 排除集);
``k_members`` 保持 comp core∪shared 口径的服务面不切换——
M4 fuel_sell_candidates 与 funding_support_sell 的 zero_overlap 卖免判定
(否则 bench 被 hoard 低星成员塞满后腾席候选空集,滞留换拍复发)、
R1/R2 刷新账合格集(P40 A4「目标阵容件」口径,无数学重推不翻转)。
``transition_pair`` 对件维持二级囤货定位(机会性囤货,不升 M2 骨架
义务,ADR-0367 分层),不进买入义务集。

锁契约(测试纪律第 8 条):锁「口径一致性」——各消费面的成员集判定
必须与声明口径同源;不锁具体买入数与经济面数值。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_intention
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    locked_buy_membership,
    locked_buy_scope,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    SellBench,
    ShopCard,
    simulate,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates,
)

# ===== 基建 =====

_LOCK_COMP = '列车同行'


def _cfg():
    return SimpleNamespace(ev_arm='full')


def _session(target_comp, ist: IntentionState | None) -> StrategySession:
    s = StrategySession()
    s.cw4_counters = {}
    s.target_comp = target_comp
    if ist is not None:
        s.v3_intention = ist
    return s


def _locked_ist(comp_name: str = _LOCK_COMP) -> IntentionState:
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = comp_name
    ist.lock_plane = 2
    return ist


def _state(gold: int, shop_cards: list[ShopCard], plane: int = 2,
           level: int = 7, bench: list[BenchChar] | None = None
           ) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2, hp=60)
    st.plane = plane
    st.shop = shop_cards
    st.bench = bench if bench is not None else []
    st.deployed = []
    return st


def _card(name: str, cost: int, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


# ===== 买入义务面:锁定帧照买 + 拒因同源 =====


class TestLockedBuyFace:
    """锁定帧买入义务面消费锁定采购集(事故形态回归锁)。"""

    def test_incident_frame_faction_member_bought_as_line_member(self):
        """事故形态直译(P2 锁「列车同行」+ 在售丹恒·饮月 2 金):丹恒·饮月
        属列车同行阵营但非该 comp core∪shared——修复前被判 non_line 跳过,
        修复后经 M2 义务买入(不落 non_line 拒因)。"""
        st = _state(gold=30, shop_cards=[_card('丹恒·饮月', 2)])
        sess = _session(get_comp(_LOCK_COMP), _locked_ist())
        act = shop.decide_shop_action(st, sess, _cfg())
        assert isinstance(act, BuyCard), act
        assert act.card.name == '丹恒·饮月'
        assert act.reason == 'm2_line_member'

    def test_locked_faction_member_not_non_line_in_rejects(self):
        """拒因遥测同源:锁定帧在售开拓者·欢愉(列车同行阵营 4★,事故局
        全局最贵拒绝件)不得标 ``non_line``——进线内缺口件分类。"""
        st = _state(gold=30, shop_cards=[
            _card('丹恒·饮月', 2), _card('开拓者·欢愉', 4, star=4)])
        sess = _session(get_comp(_LOCK_COMP), _locked_ist())
        shop.decide_shop_action(st, sess, _cfg())
        rejects = getattr(sess, 'cw4_shop_rejects', {}) or {}
        assert rejects.get('开拓者·欢愉', '').startswith('missing_')

    def test_membership_single_source_matches_locked_buy_scope(self):
        """单一源锚(无过渡对帧):locked_buy_membership == locked_buy_scope,
        且含阵营∪流派全集成员(W65 口径直算对拍)。"""
        ist = _locked_ist()
        scope = locked_buy_scope(ist)
        assert locked_buy_membership(ist) == scope
        assert '丹恒·饮月' in scope
        assert '开拓者·欢愉' in scope


# ===== 卖免面/刷新账:保持 core∪shared 口径(辖域收窄锁)=====


class TestSellFaceAndLedgerUnswitched:
    """锁定采购集不灌入卖免面与刷新账(合并审计裁决的辖域收窄)。"""

    def test_fuel_sell_candidates_keep_core_semantics(self):
        """口径拆分直锁:锁定帧下 M4 燃料集判定集 = comp core∪shared——
        bench 上的 hoard-only 1★ 成员(非 core∪shared)仍是可卖腾席燃料
        (若灌入锁定全集则全域免卖、腾席通道空集)。"""
        comp = get_comp(_LOCK_COMP)
        core = set(predicates.line_members(comp))
        hoard_chars, _eq = cw_intention._line_hoard(comp)
        hoard_only = sorted(hoard_chars - core)
        assert hoard_only, '锁测试前提:锁定采购集须含 core∪shared 外成员'
        bench = [_bc(m, slot=i + 1) for i, m in enumerate(hoard_only)]
        st = _state(gold=30, shop_cards=[], bench=bench)
        fuel = mandate.fuel_sell_candidates(bench, core, state=st)
        assert {b.char_id for b in fuel} >= set(hoard_only[:2]), \
            'hoard-only 1★ 成员须仍是腾席燃料(卖免面未吃锁定全集)'

    def test_bench_full_of_hoard_members_still_frees_seat_and_buys(self):
        """F1 事故形态锁:锁线 hoard 满集塞满 bench + 缺员核心件在店 +
        金足 ⇒ 腾席候选非空、买入不被空集卡死(先卖 hoard 1★ 腾席,
        下一帧 M2 义务买入核心件)。"""
        comp = get_comp(_LOCK_COMP)
        core = list(predicates.line_members(comp))
        missing_core = core[0]
        hoard_chars, _eq = cw_intention._line_hoard(comp)
        hoard_only = sorted(set(hoard_chars) - set(core))
        bench = [_bc(m, slot=i + 1)
                 for i, m in enumerate(hoard_only[:BENCH_CAPACITY])]
        while len(bench) < BENCH_CAPACITY:
            bench.append(_bc(f'填充件{len(bench)}', slot=len(bench) + 1))
        st = _state(gold=30, shop_cards=[_card(missing_core, 3)], bench=bench)
        sess = _session(comp, _locked_ist())
        act = shop.decide_shop_action(st, sess, _cfg())
        assert isinstance(act, SellBench), 'bench 满须先腾席(候选非空)'
        assert (act.expect or '') not in core, '腾席不得卖 core∪shared 成员'
        st2 = simulate(st, act)
        act2 = shop.decide_shop_action(st2, sess, _cfg())
        assert isinstance(act2, BuyCard) and act2.card.name == missing_core
        assert act2.reason == 'm2_line_member'

    def test_r1_ledger_keeps_p40_target_members_semantics(self, monkeypatch):
        """F2 锁:R1 刷新账合格集 = comp core∪shared(P40 A4 目标阵容件
        口径)——锁定全集(hoard 数十人、含 4★ 高费件)不灌入,刷新判据
        行为由既有证明背书,不随锁定口径翻转。"""
        comp = get_comp(_LOCK_COMP)
        core = set(predicates.line_members(comp))
        # 帧构造:店无任何义务面成员(燃料件不在采购集)、EV 无背书
        #(U_X 未标定 fail-closed)⇒ 决策链走到 R1 刷新账。
        st = _state(gold=12, shop_cards=[_card('燃料件X', 1)],
                    bench=[_bc('丹恒·饮月')])
        sess = _session(comp, _locked_ist())
        captured: list[tuple[str, ...]] = []
        real = shop._r1_ledger_terms

        def _spy(k_members, bench, deployed, level):
            captured.append(tuple(k_members))
            return real(k_members, bench, deployed, level)

        monkeypatch.setattr(shop, '_r1_ledger_terms', _spy)
        shop.decide_shop_action(st, sess, _cfg())
        assert captured, '刷新账未达(帧构造失效)'
        for km in captured:
            assert set(km) == core
            assert '丹恒·饮月' not in km


# ===== transition_pair:二级囤货不升骨架义务 =====


class TestTransitionPairNotObligated:
    """P1 comp 锁帧的 transition_pair 对件维持二级囤货(ADR-0367 分层)。"""

    def test_membership_excludes_transition_pair(self):
        """kernel 锁:transition_pair 设定不改变买入义务集(对件不进)。"""
        pair = ('持续伤害', '狼狩')
        tp_members = cw_intention._pair_members(pair)
        ist = _locked_ist()
        ist.transition_pair = pair
        membership = locked_buy_membership(ist)
        assert membership is not None
        extra = tp_members - membership
        assert extra, '锁测试前提:对件集须有采购集外成员'
        assert locked_buy_membership(ist) == locked_buy_membership(_locked_ist()), \
            'transition_pair 不得影响买入义务集(与 locked_buy_scope 的唯一差异)'

    def test_transition_pair_member_still_non_line_in_shop(self):
        """shop 锁:对件(采购集外)在店不进 M2 义务买入,拒因维持
        non_line(机会性囤货走息律/预算辖,EV 排除集不含它)。"""
        pair = ('持续伤害', '狼狩')
        ist = _locked_ist()
        ist.transition_pair = pair
        membership = locked_buy_membership(ist)
        pair_only = sorted(cw_intention._pair_members(pair) - membership)
        comp = get_comp(_LOCK_COMP)
        st = _state(gold=30, shop_cards=[_card(pair_only[0], 3)])
        sess = _session(comp, ist)
        act = shop.decide_shop_action(st, sess, _cfg())
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'm2_line_member')
        rejects = getattr(sess, 'cw4_shop_rejects', {}) or {}
        assert rejects.get(pair_only[0]) == 'non_line'


# ===== P1 无锁态回归锁(行为不变)+ 消费面变异逃生口 =====


class TestUnlockedFrameUnchanged:
    """未锁帧(locked_comp 空,含 P1 配方锁帧):口径维持
    line_members(target_comp),零变化。"""

    def test_p1_unlocked_faction_member_still_non_line(self):
        """同 comp(列车同行)、仅锁标志不同(ist unlocked/locked_comp 空
        = P1 配方锁帧形态):丹恒·饮月不进买入义务集——拒因维持
        non_line,且无 m2_line_member 义务买入(口径锁,非全行为冻结)。"""
        st = _state(gold=30, shop_cards=[_card('丹恒·饮月', 2)], plane=1)
        sess = _session(get_comp(_LOCK_COMP), IntentionState())
        act = shop.decide_shop_action(st, sess, _cfg())
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'm2_line_member')
        rejects = getattr(sess, 'cw4_shop_rejects', {}) or {}
        assert rejects.get('丹恒·饮月') == 'non_line'

    def test_p1_recipe_lock_frame_faction_member_still_non_line(self):
        """F9 消费面形态锁:P1 配方锁帧(p1_pair 非空 ∧ locked_comp 空,
        ADR-0357 后者的恒空形态)——若消费点被换成 locked_buy_scope 直调,
        p1_pair 成员会进买入义务集(行为翻转),本锁抓红。丹恒·饮月属
        配方对两体系(仙舟+列车同行)成员、非 comp core∪shared:
        正确行为 = 仍 non_line / 无义务买入。"""
        ist = IntentionState()
        ist.p1_pair = ('列车同行', '仙舟')
        assert locked_buy_membership(ist) is None   # kernel 边界:membership=None
        assert '丹恒·饮月' in locked_buy_scope(ist)  # 变异体(scope 直调)会翻转
        st = _state(gold=30, shop_cards=[_card('丹恒·饮月', 2)], plane=1)
        sess = _session(get_comp(_LOCK_COMP), ist)
        act = shop.decide_shop_action(st, sess, _cfg())
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'm2_line_member')
        rejects = getattr(sess, 'cw4_shop_rejects', {}) or {}
        assert rejects.get('丹恒·饮月') == 'non_line'

    def test_shop_consumes_membership_not_scope_direct(self):
        """F9 等效源锁:shop 消费点必须经 locked_buy_membership(含
        transition_pair/配方锁帧收窄语义),禁 locked_buy_scope 直调
        (两函数在 p1_pair/transition_pair 非空且 locked_comp 空或对件
        帧上返回值不同,直调 = 义务集扩大变异)。"""
        src = Path(shop.__file__).read_text(encoding='utf-8')
        assert 'cw_intention.locked_buy_membership(' in src
        assert 'locked_buy_scope' not in src, \
            'shop 消费面禁 locked_buy_scope 直调(义务集扩大变异逃生口)'

    def test_membership_none_when_unlocked(self):
        """正典函数边界:unlocked / ist 缺失 / weak ⇒ None(消费方维持
        既有口径的开关锚)。"""
        assert locked_buy_membership(None) is None
        assert locked_buy_membership(IntentionState()) is None
        weak = IntentionState()
        weak.phase = 'weak'
        assert locked_buy_membership(weak) is None
