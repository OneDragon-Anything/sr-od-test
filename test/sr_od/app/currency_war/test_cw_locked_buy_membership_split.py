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

来源:文末「容量可行截断」簇自 test_cw_t307_locked_buy_truncation.py 并入
(2026-09-12 归并批,同机制主题文件;语义出处 = T-295 方案 R1/表行 #8-#13,
决策记录 = ADR-0647,原文件 docstring 随簇保留在节内注)。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_intention
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    locked_buy_cap_hold,
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
    sell_gate,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bs,
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
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = target_comp
    if ist is not None:
        state_of(s).v3_intention = ist
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
    # 非空板前置(T-32 空板止损守卫):守卫钉「待卖后 deployed 为空 ⇒
    # 拒卖」,卖出判据/发射位直调环境须 ≥1 上场件,否则 fail-closed 拒帧
    # ——与被测语义无关的红按环境前置补齐,非跟绿。
    st.deployed = [_bc('板上件锚', slot=1)]
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
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
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
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act, BuyCard) and act.card.name == core[0]
        assert act.reason == 'm2_line_member'

    def test_unlocked_frames_never_emit_locked_member_key(self):
        """未锁帧零漂移锁:buy_members == k_members ⇒ M2 买入恒
        m2_line_member,m2_locked_member 不出现(缺省零漂移)。"""
        st = _state(gold=30, shop_cards=[_card('三月七', 2)])
        sess = _session(get_comp(_LOCK_COMP), IntentionState())
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act, BuyCard)
        assert act.reason == 'm2_line_member'

    def test_locked_faction_member_not_non_line_in_rejects(self):
        """拒因遥测同源:锁定帧在售开拓者·欢愉(列车同行阵营 4★,事故局
        全局最贵拒绝件)不得标 ``non_line``——进线内缺口件分类。"""
        st = _state(gold=30, shop_cards=[
            _card('丹恒·饮月', 2), _card('开拓者·欢愉', 4, star=4)])
        sess = _session(get_comp(_LOCK_COMP), _locked_ist())
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        rejects = getattr(state_of(sess), 'cw4_shop_rejects', {}) or {}
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
        """(P60 重推导 + T-307/R1 语义改写,ADR-0647)bench 满且占员全为
        B'(容量可行截断义务集,lv7 下 = 宽集−{杰帕德,彦卿})成员 +
        缺员核心件在店 ⇒ 义务面内换手通道仍闭死——诚实停摆可判读:
        m2_retry_exhausted / bench_full_buy_abandon 计数、零 BuyCard/
        零 SellBench。旧构造语义(hoard-only 按名序前 9,含彦卿)在 R1
        后由本文件 TestSeatDeadlockRelease 承接(2026-09-12 归并批并入;
        被截成员 ∉B' 可卖 = 修复行为,非换手)——本锁改用 B' 内成员构造,
        钉「义务面内禁卖」语义不因截断引入而松动。"""
        comp = get_comp(_LOCK_COMP)
        core = list(predicates.line_members(comp))
        missing_core = core[0]
        hoard_chars, _eq = cw_intention._line_hoard(comp)
        hoard_only = sorted(set(hoard_chars) - set(core))
        st_probe = _state(gold=30, shop_cards=[])
        bp = locked_buy_membership(
            _locked_ist(),
            cap_hold=cw_intention.locked_buy_cap_hold(st_probe))
        in_bp = [m for m in hoard_only if bp and m in bp]
        assert len(in_bp) >= BENCH_CAPACITY, \
            '锁测试前提:B\' 内囤件不足 9(注册表/截断参数漂移)'
        bench = [_bc(m, slot=i + 1)
                 for i, m in enumerate(in_bp[:BENCH_CAPACITY])]
        st = _state(gold=30, shop_cards=[_card(missing_core, 3)], bench=bench)
        sess = _session(comp, _locked_ist())
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not isinstance(act, BuyCard), 'B\' 成员不得被卖出/换手'
        assert not isinstance(act, SellBench)
        assert state_of(sess).cw4_counters.get('m2_retry_exhausted', 0) >= 1
        assert state_of(sess).cw4_counters.get('bench_full_buy_abandon', 0) >= 1

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
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act, SellBench), 'off-line 件腾席候选须非空'
        st2 = simulate(st, act)
        act2 = shop.decide_shop_action(cw4_bs(st2, sess), sess, _cfg())
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
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
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
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'm2_line_member')
        rejects = getattr(state_of(sess), 'cw4_shop_rejects', {}) or {}
        assert rejects.get(pair_only[0]) == 'non_line'


# ===== P1 无锁态回归锁(行为不变)+ 消费面变异逃生口 =====


class TestUnlockedFrameUnchanged:
    """未锁帧(locked_comp 空,含 P1 配方锁帧):口径维持
    line_members(target_comp),零变化。"""

    def test_p1_unlocked_faction_member_released_by_transition_rule(self):
        """同 comp(列车同行)、仅锁标志不同(ist unlocked/locked_comp 空
        = P1 配方锁帧形态):丹恒·饮月不进买入义务集——无 m2_line_member
        义务买入(口径锁,非全行为冻结)。
        T-115 重推(ADR-0580;用户裁定 408②):丹恒·饮月 ∈ TRANSITION_
        PACK carry = ④放行件——「线外件维持 non_line 拒买」对④放行件
        已被取代:未锁双轨帧(P1 + ist 空窗)改由 ④转线放行臂买入
        (本测试件恰为裁定病灶「藿藿=仙舟件被 non_line 一刀切」同型);
        M2 义务口径不变(④买入 reason=transition_component_buy,非义务)。"""
        st = _state(gold=30, shop_cards=[_card('丹恒·饮月', 2)], plane=1)
        sess = _session(get_comp(_LOCK_COMP), IntentionState())
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'm2_line_member')
        assert isinstance(act, BuyCard) and act.reason == 'transition_component_buy' \
            and act.card.name == '丹恒·饮月'
        assert state_of(sess).cw4_counters.get('transition_component_buy_hit') == 1

    def test_p1_recipe_lock_frame_committed_narrows_transition_release(self):
        """F9 消费面形态锁:P1 配方锁帧(p1_pair 非空 ∧ locked_comp 空,
        ADR-0357 后者的恒空形态)——若消费点被换成 locked_buy_scope 直调,
        p1_pair 成员会进买入义务集(行为翻转),本锁抓红。丹恒·饮月属
        配方对两体系(仙舟+列车同行)成员、非 comp core∪shared:
        正确行为 = 无 M2 义务买入。
        T-115 重推(ADR-0580):p1_pair 非空 = committed(定型权威③)
        ⇒ ④放行收窄不放行,丹恒·饮月不被买入;拒因按 D7 键序 =
        'transition_component'(④放行件身份与 comp 无关,可辨「④件因
        定型辖域未买」,判读价值即在此;旧 'non_line' 一刀切键已废)。"""
        ist = IntentionState()
        ist.p1_pair = ('列车同行', '仙舟')
        assert locked_buy_membership(ist) is None   # kernel 边界:membership=None
        assert '丹恒·饮月' in locked_buy_scope(ist)  # 变异体(scope 直调)会翻转
        st = _state(gold=30, shop_cards=[_card('丹恒·饮月', 2)], plane=1)
        sess = _session(get_comp(_LOCK_COMP), ist)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'm2_line_member')
        assert not isinstance(act, BuyCard), \
            '定型帧(p1_pair 非空)④放行收窄:丹恒·饮月不买'
        rejects = getattr(state_of(sess), 'cw4_shop_rejects', {}) or {}
        assert rejects.get('丹恒·饮月') == 'transition_component'

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
        state_of(sess).cw4_line_state = proof.LineState()
        state_of(sess).cw4_line_state.drought = 3
        state_of(sess).cw4_recent_sold_names = [core[0]]
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act, BuyCard) and act.card.name == core[0]
        assert state_of(sess).cw4_counters.get('shop_churn_pair_buy', 0) >= 1
        assert state_of(sess).cw4_counters.get('shop_drought_reset_on_churn_buy', 0) >= 1
        assert 'shop_drought_reset_on_buy' not in state_of(sess).cw4_counters
        # 对照帧:无卖出记认 ⇒ 原键(缺员买入)
        st2 = _state(gold=30, shop_cards=[_card(core[0], 3)])
        sess2 = _session(comp, _locked_ist())
        state_of(sess2).cw4_line_state = proof.LineState()
        state_of(sess2).cw4_line_state.drought = 3
        act2 = shop.decide_shop_action(cw4_bs(st2, sess2), sess2, _cfg())
        assert isinstance(act2, BuyCard)
        assert state_of(sess2).cw4_counters.get('shop_drought_reset_on_buy', 0) >= 1
        assert 'shop_drought_reset_on_churn_buy' not in state_of(sess2).cw4_counters
        assert 'shop_churn_pair_buy' not in state_of(sess2).cw4_counters

    def test_hoard_over_capacity_warning_counter(self):
        """|buy_members| > bench+板容量上界 ⇒ 帧级告警计数(黄泉减益
        |B|=20 > 16,证明 P60 ①出口不可达形态可见)。"""
        comp = get_comp('黄泉减益')
        st = _state(gold=30, shop_cards=[])
        sess = _session(comp, _locked_ist('黄泉减益'))
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert state_of(sess).cw4_counters.get('shop_hoard_over_capacity', 0) >= 1

# ===== 容量可行截断 + P60 修正门 + 基座随 B'(自 test_cw_t307_locked_buy_truncation.py 并入,ADR-0647)=====

# 本簇特有构造器(与文件头部基建同体者已去重;命名区别:文件头 _session=StrategySession 载体,本簇 _sess=SimpleNamespace 桩;_state_lv8 的默认 level=8 是截断语义承重位,勿并入文件头 _state):

_SUB_CAP_COMP = '命运圣杯红A'   # |hoard|=5 ≤ 任意实用容量,截断零触发


def _sess(comp, ist: IntentionState | None) -> SimpleNamespace:
    s = SimpleNamespace(ev_arm='full')
    st = state_of(s)
    st.cw4_counters = {}
    st.target_comp = comp
    if ist is not None:
        st.v3_intention = ist
    return s


def _state_lv8(gold: int, shop_cards: list[ShopCard], level: int = 8,
           bench: list[BenchChar] | None = None) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2, hp=60)
    st.plane = 2
    st.shop = shop_cards
    st.bench = bench if bench is not None else []
    # 非空板前置(T-32 空板止损守卫):与既有锁同构的环境补齐,非语义面。
    st.deployed = [BenchChar(slot=1, char_id='板上件锚', star=1)]
    return st


def _b_prime(ist: IntentionState, st: GameState) -> frozenset[str]:
    """截断义务集 B'(单一源直调;level 现读口径与生产装配一致)。"""
    return locked_buy_membership(
        ist, cap_hold=locked_buy_cap_hold(st)) or frozenset()

# ===== R1 谓词本体:截断序 + 零漂移端 =====


class TestObligationTruncation:
    """容量可行截断谓词锁(T-295 方案 R1 谓词规格;ADR-0647)。"""

    def test_cap_hold_none_keeps_wide_single_source(self):
        """零漂移端:cap_hold=None(缺省)返回宽集,与 locked_buy_scope
        同集(W65 口径不变;T-307 兼容缺省契约,方案表行 #1)。"""
        ist = _locked_ist()
        assert locked_buy_membership(ist) == locked_buy_scope(ist)

    def test_lv8_truncates_to_practical_capacity(self):
        """lv8 实用容量 17(= bench 9 + 上阵 8):|B|=18 → 截断保 17,
        被截集 = 最高费档尾(彦卿 4 费/注册表序最末);core∪shared 全保
        且 B' ⊆ 宽集(方案 R1 级序:core∪shared ≻ 其余同级)。"""
        ist = _locked_ist()
        wide = locked_buy_membership(ist)
        st = _state_lv8(gold=30, shop_cards=[])
        bp = _b_prime(ist, st)
        assert wide is not None and len(wide) == 18
        assert locked_buy_cap_hold(st) == BENCH_CAPACITY + 8 == 17
        assert len(bp) == 17
        assert sorted(wide - bp) == ['彦卿']
        core_shared = set(get_comp(_LOCK_COMP).core_chars) | \
            set(get_comp(_LOCK_COMP).shared_chars)
        assert core_shared <= bp

    def test_tie_break_declaration_order_deterministic(self):
        """同费 tie-break = 注册表声明序(r2 发现 2:声明序单序;
        cap_hold=16 时 cost-4 档保声明序前二(欢愉/记忆),截尾 =
        杰帕德/彦卿(声明序最末)。锁跨进程确定性——从 set 迭代出序
        的实现会因哈希序抖动,本锁抓红。"""
        ist = _locked_ist()
        wide = locked_buy_membership(ist)
        assert wide is not None
        bp16 = locked_buy_membership(ist, cap_hold=16)
        assert set(wide - bp16) == {'杰帕德', '彦卿'}
        # 级内序直读:cost-4 档成员按声明序排列(欢愉 idx49 < 记忆 58
        # < 杰帕德 60 < 彦卿 61,注册表声明序事实)。
        rank = cw_intention._obligation_rank(
            {'彦卿', '杰帕德', '开拓者·记忆', '开拓者·欢愉'})
        assert rank == ['开拓者·欢愉', '开拓者·记忆', '杰帕德', '彦卿']

    def test_cap_hold_helper_fail_closed_keeps_wide(self):
        """缺读 fail-closed 方向 = 保宽(r2 发现 2 裁决:零漂移端)——
        state 缺失/level≤0/容量派生异常帧 cap_hold=None。"""
        assert locked_buy_cap_hold(None) is None
        assert locked_buy_cap_hold(GameState(gold=1, level=0,
                                             round_num=1, hp=60)) is None

    def test_sub_capacity_comp_zero_drift(self):
        """子容量 comp(|B| ≤ cap_hold)截断零触发:B' == 宽集
        (截断是收紧面,未超容帧行为逐位不变)。"""
        ist = _locked_ist(_SUB_CAP_COMP)
        st = _state_lv8(gold=30, shop_cards=[])
        wide = locked_buy_membership(ist)
        assert wide is not None and len(wide) <= locked_buy_cap_hold(st)
        assert _b_prime(ist, st) == wide

    def test_locked_none_contract_intact_with_cap(self):
        """None 契约边界不受截断参数影响:未锁/weak/ist 缺失帧传
        cap_hold 仍返回 None(消费方维持既有口径的开关锚)。"""
        cap = 16
        assert locked_buy_membership(None, cap_hold=cap) is None
        assert locked_buy_membership(IntentionState(),
                                     cap_hold=cap) is None
        weak = IntentionState()
        weak.phase = 'weak'
        assert locked_buy_membership(weak, cap_hold=cap) is None


# ===== 死锁解除单帧行为锁(s10003 p2r1 形态重放)=====


def _bench9_with_truncated() -> list[BenchChar]:
    """bench 满构造:hoard-only 按名序前 9 名——恰含彦卿(lv8 截断集
    B' = 宽集−{彦卿}),其余 8 名 ∈ B'(s10003 p2r1 形态:席满 ∧
    唯一被截成员单张在场)。"""
    comp = get_comp(_LOCK_COMP)
    chars, _eq = cw_intention._line_hoard(comp)
    core = set(comp.core_chars) | set(comp.shared_chars)
    hoard_only = sorted(set(chars) - core)
    assert hoard_only[7] == '彦卿', '锁测试前提漂移:bench[7] 应为彦卿'
    return [_bc(m, slot=i + 1)
            for i, m in enumerate(hoard_only[:BENCH_CAPACITY])]


class TestSeatDeadlockRelease:
    """席满死锁解除单帧锁(T-295-P1 停摆不动点解除主链;ADR-0647)。

    锁前提(方案验证方案节):被截成员须「单张 ∧ 非效果资格件 ∧
    非合成素材(G-S1)」形态;囤货对(1★×2)构造 = 推论边界帧
    (残余停摆,预期仍 abandon),由 test_truncated_pair_form_stays_
    stalled 单独承载,非实现错。
    """

    def test_truncated_member_frees_seat_and_m2_buys(self):
        """p2r1 形态(lv8,bench 满 9 含被截成员,缺员义务件瓦尔特在店):
        M4 卖被截成员(∉B' → 保护必要性消失)腾席 → 下一帧 M2 义务买入。
        卖出 reason 无孤儿标记(孤儿账随 B',被截成员卖出非账闭合事件,
        方案表行 #13 随 B' 裁决)。"""
        comp = get_comp(_LOCK_COMP)
        ist = _locked_ist()
        st = _state_lv8(gold=30, level=8,
                    bench=_bench9_with_truncated(),
                    shop_cards=[_card('瓦尔特', 5)])
        bp = _b_prime(ist, st)
        assert '彦卿' not in bp and '瓦尔特' in bp
        sess = _sess(comp, ist)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act, SellBench), act
        assert not (getattr(act, 'reason', '') or ''), \
            '被截成员卖出不得带孤儿标记(孤儿账随 B\')'
        st2 = simulate(st, act)
        act2 = shop.decide_shop_action(cw4_bs(st2, sess), sess, _cfg())
        assert isinstance(act2, BuyCard) and act2.card.name == '瓦尔特'
        assert act2.reason == 'm2_line_member'   # 瓦尔特 ∈ core∪shared

    def test_bp_members_only_bench_stays_stalled(self):
        """B' 内成员换手闭死语义不变(r2 ③核验通过面):bench 满全为
        B' 成员 + 缺员义务件在店 ⇒ 腾席候选空,诚实停摆可判读
        (m2_retry_exhausted / bench_full_buy_abandon ≥ 1,零买零卖)。"""
        comp = get_comp(_LOCK_COMP)
        ist = _locked_ist()
        st0 = _state_lv8(gold=30, level=8, shop_cards=[])
        bp = _b_prime(ist, st0)
        comp_obj = get_comp(_LOCK_COMP)
        chars, _eq = cw_intention._line_hoard(comp_obj)
        core = set(comp_obj.core_chars) | set(comp_obj.shared_chars)
        in_bp = sorted((set(chars) - core) & set(bp))[:BENCH_CAPACITY]
        assert len(in_bp) == BENCH_CAPACITY, '锁测试前提:B\' 内囤件不足 9'
        st = _state_lv8(gold=30, level=8,
                    bench=[_bc(m, slot=i + 1)
                           for i, m in enumerate(in_bp)],
                    shop_cards=[_card('瓦尔特', 5)])
        sess = _sess(comp, ist)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not isinstance(act, BuyCard)
        assert not isinstance(act, SellBench)
        counters = state_of(sess).cw4_counters
        assert counters.get('m2_retry_exhausted', 0) >= 1
        assert counters.get('bench_full_buy_abandon', 0) >= 1

    def test_truncated_pair_form_stays_stalled(self):
        """推论边界帧(G-S1 收窄,方案 §③ 残余申报):被截成员以
        1★×2 囤货对持有 = 合成素材形态,M4 燃料守卫拒入(mandate.
        merge_material_reject)⇒ 腾席仍空,诚实停摆如实保留——残余
        停摆面申报在案,本锁钉其不因 R1 假性解除。"""
        comp = get_comp(_LOCK_COMP)
        ist = _locked_ist()
        # 构造 1★×2 对:替换两个 B' 内位为彦卿(hoard 对形态),
        # 其余 7 位保持 B' 成员。
        chars, _eq = cw_intention._line_hoard(comp)
        core = set(comp.core_chars) | set(comp.shared_chars)
        in_bp = sorted((set(chars) - core)
                       - {'彦卿', '杰帕德'})[:BENCH_CAPACITY - 2]
        bench = ([_bc('彦卿', slot=1), _bc('彦卿', slot=2)]
                 + [_bc(m, slot=i + 3)
                    for i, m in enumerate(in_bp)])
        assert len(bench) == BENCH_CAPACITY
        st = _state_lv8(gold=30, level=8, bench=bench,
                    shop_cards=[_card('瓦尔特', 5)])
        sess = _sess(comp, ist)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not isinstance(act, SellBench), \
            '囤货对(合成素材)不得入 M4 燃料集(G-S1)'
        assert not isinstance(act, BuyCard)
        assert state_of(sess).cw4_counters.get(
            'm2_retry_exhausted', 0) >= 1


# ===== P60 门修正锁(检查对象 = 截断前宽集,分母 = cap_hold 现读)=====


class TestP60CorrectedGate:
    """P60 容量告警门修正锁(T-295 方案表行 #8;问题 7 死观测面修复;
    ADR-0647):检查对象 = 截断前宽集,分母 = BENCH_CAPACITY +
    max_units(level) 现读。"""

    def test_p60_fires_wide18_at_lv8(self):
        """|宽集|=18 ∧ lv8(cap_hold=17)→ 开火。旧固定分母 9+10=19
        下 18 ≤ 19 不火 = 高估容量掩蔽不可达形态,本锁即修正面。"""
        comp = get_comp(_LOCK_COMP)
        st = _state_lv8(gold=30, level=8, shop_cards=[])
        sess = _sess(comp, _locked_ist())
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert state_of(sess).cw4_counters.get(
            'shop_hoard_over_capacity', 0) >= 1

    def test_p60_no_fire_sub_capacity(self):
        """子容量 comp(|B|=5 ≤ cap_hold)不开火(负对照:门非恒开)。"""
        comp = get_comp(_SUB_CAP_COMP)
        st = _state_lv8(gold=30, level=8, shop_cards=[])
        sess = _sess(comp, _locked_ist(_SUB_CAP_COMP))
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert 'shop_hoard_over_capacity' not in state_of(sess).cw4_counters


# ===== 义务基座随 B'(sell_gate 必改位 + 孤儿账随 B')=====


class TestSellGateBaseFollowsTruncation:
    """M4/凑息/funding 基座截断锁(方案表行 #9/#10/#13;阻断③:
    不改 = 静默半修)。"""

    def test_resolve_base_truncates_with_cap_hold(self):
        """_resolve_base 传 cap_hold → 基座 = B'(被截成员出基座);
        None → 保宽(零漂移端)。"""
        comp = get_comp(_LOCK_COMP)
        core = tuple(sorted(set(comp.core_chars)
                            | set(comp.shared_chars)))
        sess = _sess(comp, _locked_ist())
        st = _state_lv8(gold=30, level=8, shop_cards=[])
        _locked, base = sell_gate._resolve_base(
            sess, core, cap_hold=locked_buy_cap_hold(st))
        assert len(base) == 17 and '彦卿' not in base
        _locked_w, base_w = sell_gate._resolve_base(sess, core)
        assert len(base_w) == 18 and '彦卿' in base_w

    def test_orphan_base_uses_obligation_face(self):
        """孤儿证明集 base 随义务面 B'(表行 #13 装配直证):截断帧
        传入 _line_switch_orphans 的 base = B'(被截成员非义务账,
        设计内卖出不得误标孤儿);子容量帧 = 宽集(零漂移)。"""
        comp = get_comp(_LOCK_COMP)
        captured: list[set[str]] = []
        real = shop._line_switch_orphans

        def _spy(session, base, round_num):
            captured.append(set(base))
            return real(session, base, round_num)

        st = _state_lv8(gold=30, level=8, shop_cards=[])
        sess = _sess(comp, _locked_ist())
        shop._line_switch_orphans = _spy   # 模块级槽位,事后还原
        try:
            shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        finally:
            shop._line_switch_orphans = real
        assert captured, '孤儿装配读点未触达(帧构造失效)'
        bp = _b_prime(_locked_ist(), st)
        assert captured[0] == set(bp)

    def test_channels_default_cap_none_keeps_wide(self):
        """无帧态调用位(兼容再出口/缺省)基座保宽 = 零漂移端
        (cap_hold 参数缺省契约;fail-closed 方向 = 不收紧)。"""
        comp = get_comp(_LOCK_COMP)
        core = tuple(sorted(set(comp.core_chars)
                            | set(comp.shared_chars)))
        sess = _sess(comp, _locked_ist())
        excl = sell_gate.identity_exclusions(sess, core)
        assert '彦卿' in excl
