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


def _sell_bonds(name: str) -> set[str]:
    """角色全羁绊(factions∪flows;注册表直读,判 off-line/fenced 用)。"""
    from sr_od.application.currency_war.data.cw_chars import get_char
    ch = get_char(name)
    return set(ch.factions) | set(ch.flows)


def hoard_all(comp) -> set[str]:
    """comp 锁定采购集角色全集(单一源 = cw_intention._line_hoard)。"""
    chars, _eq = cw_intention._line_hoard(comp)
    return chars


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

    def test_incident_frame_faction_member_bought_as_locked_member(self):
        """事故形态直译(P2 锁「列车同行」+ 在售丹恒·饮月 2 金):丹恒·饮月
        属列车同行阵营但非该 comp core∪shared——修复前被判 non_line 跳过,
        修复后经 M2 义务买入(不落 non_line 拒因)。买因分键(局21 复盘
        候选3,g_20260906_021859:锁定采购集扩展成员曾与真线成员共用
        m2_line_member,同名异源买因不可辨)→ 扩展成员记
        m2_locked_member,与线成员键分离。"""
        st = _state(gold=30, shop_cards=[_card('丹恒·饮月', 2)])
        sess = _session(get_comp(_LOCK_COMP), _locked_ist())
        act = shop.decide_shop_action(st, sess, _cfg())
        assert isinstance(act, BuyCard), act
        assert act.card.name == '丹恒·饮月'
        assert act.reason == 'm2_locked_member'

    def test_true_line_member_keeps_m2_line_member_key(self):
        """线成员键保持锁(局21 候选3 对照面):锁线帧缺员 core∪shared
        成员买入仍记 m2_line_member(分键只拆扩展成员,不污染原键)。"""
        comp = get_comp(_LOCK_COMP)
        core = list(predicates.line_members(comp))
        st = _state(gold=30, shop_cards=[_card(core[0], 3)])
        sess = _session(comp, _locked_ist())
        act = shop.decide_shop_action(st, sess, _cfg())
        assert isinstance(act, BuyCard) and act.card.name == core[0]
        assert act.reason == 'm2_line_member'

    def test_unlocked_frames_never_emit_locked_member_key(self):
        """未锁帧零漂移锁:buy_members == k_members ⇒ M2 买入恒
        m2_line_member,m2_locked_member 不出现(缺省零漂移)。"""
        st = _state(gold=30, shop_cards=[_card('三月七', 2)])
        sess = _session(get_comp(_LOCK_COMP), IntentionState())
        act = shop.decide_shop_action(st, sess, _cfg())
        assert isinstance(act, BuyCard)
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
        """口径拆分直锁(P60 后重推导):不注入排除集时 M4 燃料集判定集 =
        comp core∪shared(hoard-only 1★ 成员仍是燃料——默认口径零变化,
        与卖免面收窄前一致);注入 exclude_names=buy_members 后 hoard-only
        成员出燃料集(P60 换手通道闭死)。"""
        comp = get_comp(_LOCK_COMP)
        core = set(predicates.line_members(comp))
        hoard_chars, _eq = cw_intention._line_hoard(comp)
        hoard_only = sorted(hoard_chars - core)
        assert hoard_only, '锁测试前提:锁定采购集须含 core∪shared 外成员'
        bench = [_bc(m, slot=i + 1) for i, m in enumerate(hoard_only)]
        st = _state(gold=30, shop_cards=[], bench=bench)
        fuel_default = mandate.fuel_sell_candidates(bench, core, state=st)
        assert {b.char_id for b in fuel_default} >= set(hoard_only[:2]), \
            '默认口径(未注入排除集)零变化:hoard-only 1★ 仍是燃料'
        fuel_ex = mandate.fuel_sell_candidates(bench, core, state=st,
                                               exclude_names=set(hoard_chars))
        assert not fuel_ex, 'P60:义务集成员禁入燃料集(Fuel∩B=∅,Φ 单调)'

    def test_bench_full_of_hoard_members_still_frees_seat_and_buys(self):
        """(P60 重推导,锁语义按证伪结论改写)bench 满且占员全为 B(锁定
        采购集)成员 + 缺员核心件在店 ⇒ 不再有可卖腾席(卖 B 成员 = 义务
        换手,P60 已闭死)——诚实停摆可判读:m2_retry_exhausted /
        bench_full_buy_abandon 计数、零 BuyCard/零 SellBench。真实死锁帧
        的 bench 占员是旧线 off-line 件(非 B),腾席由其承载(下条)。"""
        comp = get_comp(_LOCK_COMP)
        core = list(predicates.line_members(comp))
        missing_core = core[0]
        hoard_chars, _eq = cw_intention._line_hoard(comp)
        hoard_only = sorted(set(hoard_chars) - set(core))
        bench = [_bc(m, slot=i + 1)
                 for i, m in enumerate(hoard_only[:BENCH_CAPACITY])]
        st = _state(gold=30, shop_cards=[_card(missing_core, 3)], bench=bench)
        sess = _session(comp, _locked_ist())
        act = shop.decide_shop_action(st, sess, _cfg())
        assert not isinstance(act, BuyCard), 'B 成员不得被卖出/换手'
        assert not isinstance(act, SellBench)
        assert sess.cw4_counters.get('m2_retry_exhausted', 0) >= 1
        assert sess.cw4_counters.get('bench_full_buy_abandon', 0) >= 1

    def test_bench_full_of_offline_fenced_members_frees_and_buys(self):
        """真实死锁帧形态(P60 修复后的腾席保底):bench 满为 off-line
        fenced 件(旧线成员,∉ 新线 buy_members)+ 缺员核心件在店 ⇒
        腾席候选非空、卖出后 M2 义务买入核心件(换手通道闭死不妨碍
        旧线件腾位)。"""
        comp = get_comp(_LOCK_COMP)
        core = list(predicates.line_members(comp))
        missing_core = core[0]
        all_fac = set(comp.all_factions)
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        offline = [n for n, ch in CHARACTERS.items()
                   if n not in hoard_all(comp)
                   and not _sell_bonds(n) & all_fac]
        assert len(offline) >= 3, '锁测试前提:off-line 件不足'
        bench = [_bc(m, slot=i + 1)
                 for i, m in enumerate(offline[:BENCH_CAPACITY - 1])]
        while len(bench) < BENCH_CAPACITY:
            bench.append(_bc(f'填充件{len(bench)}', slot=len(bench) + 1))
        st = _state(gold=30, shop_cards=[_card(missing_core, 3)], bench=bench)
        sess = _session(comp, _locked_ist())
        act = shop.decide_shop_action(st, sess, _cfg())
        assert isinstance(act, SellBench), 'off-line 件腾席候选须非空'
        st2 = simulate(st, act)
        act2 = shop.decide_shop_action(st2, sess, _cfg())
        assert isinstance(act2, BuyCard) and act2.card.name == missing_core
        assert act2.reason == 'm2_line_member'

    def test_r1_ledger_keeps_p40_target_members_semantics(self, monkeypatch):
        """F1 口径对齐后重推导(编排者裁定;出处 = 14号稿 §6.2 输入②):
        R1 刷新账合格集单源 = buy_members(锁定帧 ⊇ core∪shared,禁与
        买入义务面成员集分叉)。F2 拆分原保护的「卖免面不随采购集翻转」
        语义不变:腾席/凑息/支付卖出通道仍 core∪shared 口径
        (fuel_sell_candidates 排除集锁组承载)。"""
        comp = get_comp(_LOCK_COMP)
        core = set(predicates.line_members(comp))
        # 帧构造:店无任何义务面成员(燃料件不在采购集)、EV 无背书
        #(U_X 未标定 fail-closed)⇒ 决策链走到 R1 刷新账。
        st = _state(gold=12, shop_cards=[_card('燃料件X', 1)],
                    bench=[_bc('丹恒·饮月')])
        sess = _session(comp, _locked_ist())
        captured: list[tuple[str, ...]] = []
        real = shop._r1_ledger_terms

        def _spy(buy_members, bench, deployed, level):
            captured.append(tuple(buy_members))
            return real(buy_members, bench, deployed, level)

        monkeypatch.setattr(shop, '_r1_ledger_terms', _spy)
        shop.decide_shop_action(st, sess, _cfg())
        assert captured, '刷新账未达(帧构造失效)'
        # F1 口径对齐后重推导(编排者裁定;出处 = 14号稿 §6.2 输入②):
        # R1 刷新账合格集单源 = buy_members(锁定帧 = locked_buy_membership
        # 采购集 ⊇ core∪shared)——臂①囤腿落地后「买满三张」费用口径与
        # 行为(0→1→2→3 全链义务化)一致。F2 拆分原保护的「卖免面不随
        # 采购集翻转」语义不变:腾席/凑息/支付卖出通道仍 core∪shared 口径
        # (fuel_sell_candidates 排除集锁组承载),本锁钉「刷新账 ⊇ core
        # ∧ 卖出面未翻转」两面。
        for km in captured:
            assert core <= set(km), '刷新账须含 core∪shared 全集(单源对齐)'
            assert set(km) == set(locked_buy_membership(_locked_ist())), \
                '刷新账成员集 = 买入义务集逐元素一致(单源,禁复制漂移)'


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


# ===== P60 伪装进展观测面:换手对计数 / drought 重置分键 / 容量告警 =====

class TestP60DisguisedProgressTelemetry:
    """换手循环的观测面锁(证明 P60 ③):买回近期卖出成员 = 义务换手对,
    drought 重置按买入来源分键——换手买动作不得与真实缺员买入共用同一
    「进展」信号;|B|>容量上界帧级告警计数。"""

    def test_churn_pair_buy_counter_and_drought_split(self):
        """买回近期卖出成员 ⇒ shop_churn_pair_buy 计数 + drought 重置走
        churn 分键(不走缺员买入键);无卖出记认的普通缺员买行走原键。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            proof,
        )
        comp = get_comp(_LOCK_COMP)
        core = list(predicates.line_members(comp))
        # churn 帧:符玄(core 成员)在近期卖出记认中
        st = _state(gold=30, shop_cards=[_card(core[0], 3)])
        sess = _session(comp, _locked_ist())
        sess.cw4_line_state = proof.LineState()
        sess.cw4_line_state.drought = 3
        sess.cw4_recent_sold_names = [core[0]]
        act = shop.decide_shop_action(st, sess, _cfg())
        assert isinstance(act, BuyCard) and act.card.name == core[0]
        assert sess.cw4_counters.get('shop_churn_pair_buy', 0) >= 1
        assert sess.cw4_counters.get('shop_drought_reset_on_churn_buy', 0) >= 1
        assert 'shop_drought_reset_on_buy' not in sess.cw4_counters
        # 对照帧:无卖出记认 ⇒ 原键(缺员买入)
        st2 = _state(gold=30, shop_cards=[_card(core[0], 3)])
        sess2 = _session(comp, _locked_ist())
        sess2.cw4_line_state = proof.LineState()
        sess2.cw4_line_state.drought = 3
        act2 = shop.decide_shop_action(st2, sess2, _cfg())
        assert isinstance(act2, BuyCard)
        assert sess2.cw4_counters.get('shop_drought_reset_on_buy', 0) >= 1
        assert 'shop_drought_reset_on_churn_buy' not in sess2.cw4_counters
        assert 'shop_churn_pair_buy' not in sess2.cw4_counters

    def test_hoard_over_capacity_warning_counter(self):
        """|buy_members| > bench+板容量上界 ⇒ 帧级告警计数(黄泉减益
        |B|=20 > 16,证明 P60 ①出口不可达形态可见)。"""
        comp = get_comp('黄泉减益')
        st = _state(gold=30, shop_cards=[])
        sess = _session(comp, _locked_ist('黄泉减益'))
        shop.decide_shop_action(st, sess, _cfg())
        assert sess.cw4_counters.get('shop_hoard_over_capacity', 0) >= 1
