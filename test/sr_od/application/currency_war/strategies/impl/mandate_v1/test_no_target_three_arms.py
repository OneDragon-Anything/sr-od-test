"""P86 无目标期判据退役对照测试(统一让位优先级迭代 3.4;总纲 §2.7)。

三臂判据的甲臂(方向囤货)与乙臂(枢纽期权)已随本迭代退役——本文件
改断言退役后的目标形态(退役完成判据 = 本文件,禁静默失活/复活):

- **甲臂**(方向囤货):kernel 判活路径退役(``no_target_arms`` 判据件
  整删),K 目标未锁期源切换 = 策略层「候选快照三线成员并集 ∪ 配方
  成员」(R5-01 方向②)——候选线成员经序 1 义务面照常买入(m2_* 买因),
  机器判活方向不再兜底;行为申报(收窄侧)= 弱势局未锁无目标帧从
  「按机器方向囤」变「保利息缺省」;
- **乙臂**(枢纽期权):发射位已并入序 1 候选集(12 号篇 §4 收编),
  hub_option_buy 买因与 hub_option_* 拒因族不得复现;持有段
  (hub_acquired_names_of)随装配 A 身份段退役删除;
- **丙臂**(无目标期守息缺省):p2plus 带唯一形态——kernel
  ``k_empty_window_fallback`` 该带恒合法空集(保利息缺省,零买入零
  付费刷新),p1 两带(p1_gap/p1_lock_band)回退保留(在役,防
  「K 空→零买入→支持度永不涨」死锁环)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _kbridge,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)

from sr_od.application.currency_war.kernel import cw_intention
from sr_od.application.currency_war.kernel.cw_comps import (
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    ChannelSig,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    k_empty_window_fallback,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    CwActionRefreshShopParam,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# ===== 基建 =====


def _cfg():
    return SimpleNamespace(ev_arm='full')


def _card(name: str, cost: int, star: int = 1, x: int = 0) -> ShopCard:
    return ShopCard(name=name, faction='', cost=cost, star=star, x=x)


def _bc(name: str, star: int = 1) -> BenchSlot:
    return BenchSlot(kind='unit', unit=Unit(char_id=name, star=star))


def _state(gold: int = 45, level: int = 5, plane: int = 2,
           shop_cards=(), bench=(), deployed=(), hp: int = 60,
           round_num: int = 2, node_kw: str = '') -> dict:
    """无目标帧(P2+ 位面辖域)通用种子轴(口径沿旧三臂测试:gold=45/
    level=5/round=2;target/ist 皆空 = 空窗),店面/持有按参。
    ``node_kw`` 直填节点 kind('reward' = 升级抑制帧,翻转行为差隔离)。"""
    st = {'gold': gold, 'level': level, 'plane': plane,
          'round_num': round_num,
          'hp': hp, 'node': node_kw or 'battle',
          'shop': list(shop_cards), 'bench': list(bench),
          'front_row': list(deployed), 'active_strategies': []}
    return st


def _session(ist=None, candidates: tuple[str, ...] = ()) -> StrategySession:
    sess = StrategySession()
    st = state_of(sess)
    st.cw4_counters = {}
    if ist is not None:
        st.v3_intention = ist
    if candidates:
        st.line_candidates = candidates
    return sess


def _decide(st: dict, sess: StrategySession):
    """商店单动作决策直调(会话循环;账面稳态钉位随种子 +
    node_hist_pos 位面水位线按种子平面落位——plane2_started 窗口谓词
    的单调历史输入,P2+ 帧须显式置位)。"""
    gs = cw4_gs(sess, **st)
    gs.node_hist_pos = (int(st.get('plane', 2)), int(st.get('round_num', 2)))
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        session_scope as _ss,
    )
    _ss.handle_node_boundary(gs)
    state_of(gs).gold_ledger = int(st.get('gold', 45))
    act = shop.decide_shop_action(
        gs, sess, _cfg(), registry=DEFAULT_REGISTRY)
    return act


def _ct(sess) -> dict:
    return state_of(sess).cw4_counters


# ===== kernel 判据真值面(空窗回退单一源;纯函数直测)=====


class TestFallbackKernelTruth:
    def test_p1_gap_band_falls_back_to_buy_now_union(self):
        """空窗带回退 = 过渡库见即买并集(换轴:p2plus 位面带废除,
        未终局锁定帧过渡层照常活跃——死循环防线 §3:见即买 → 持有 →
        计分 > 0 → 候选形成)。"""
        gs = _kbridge(**_state(hp=100))
        sess = _session(IntentionState())
        fb, band = k_empty_window_fallback(
            gs, state_of(sess).v3_intention, session=sess)
        from sr_od.application.currency_war.kernel.cw_intention import (
            transition_library_buy_now_union,
        )
        assert fb == transition_library_buy_now_union(), \
            '空窗带回退集 = 过渡库见即买并集(构造性非空)'
        assert band == 'p1_gap'

    def test_p1_bands_retained_nonempty(self):
        """p1 两带回退保留(在役;防「K 空→零买入→支持度永不涨」死锁环):
        位面 1 空窗帧回退集注册表派生构造性非空。"""
        comp = get_comp('希儿量子')
        st = _state(plane=1, hp=100,
                    bench=[_bc(m) for m in comp.core_chars],
                    deployed=[Unit(char_id='板上件锚', star=1)])
        gs = _kbridge(**st)
        sess = _session(IntentionState())
        fb, band = k_empty_window_fallback(gs, state_of(sess).v3_intention)
        assert fb, 'p1 空窗帧回退集为空(p1 带在役面失效)'
        assert band in ('p1_gap', 'p1_lock_band')


# ===== K 源切换(R5-01 方向②):候选快照三线并集承载序 1 =====


class TestKSourceCandidateUnion:
    def test_candidate_union_reaches_m2(self):
        """候选线成员在店 → 序 1 义务买(m2_* 买因):未锁无目标帧的
        K 源 = 候选快照三线成员并集 ∪ 配方成员——与优先级成员档族档
        2/3/4/5/7 名单同源(core∪shared;旧八档档 2/3/5 口径,十档 =
        完成品保护迭代 design §2.2),买面与优先级面统一(行为申报:
        宽放侧)。"""
        comp = get_comp('希儿量子')
        held = sorted(comp.core_chars)[:-1]
        missing_piece = sorted(set(comp.core_chars) - set(held))[0]
        st = _state(hp=100, shop_cards=[_card(missing_piece, cost=1)])
        st['bench'] = [_bc(m) for m in held]
        st['front_row'] = [Unit(char_id='板上件锚', star=1)]
        sess = _session(IntentionState(), candidates=('希儿量子',))
        act = _decide(st, sess)
        assert isinstance(act, CwActionBuyCardParam), \
            f'候选线成员未买: {act!r}'
        assert act.reason.startswith('m2_'), act.reason
        assert act.card.name == missing_piece

    def test_machine_direction_no_longer_hoarded(self):
        """甲臂退役申报(收窄侧):无候选帧(候选快照空)的未锁无目标
        帧不再按机器判活方向囤货——缺失的机器方向成员不买,收工关店
        (保利息缺省;旧 fallback 方向采购集承接行为退役)。"""
        comp = get_comp('希儿量子')
        chars, _eq = cw_intention._line_hoard(comp)
        # 探针须避开两张货架资格面(or-reqs-retirement 3.4 后买面双资格
        # 臂在役):①终局资格面(carry_set)——被货架资格臂
        # 合法买入;②过渡资格面(五块计分域并集)——手持希儿量子 core
        # 时贝键展开件(杰帕德)在 希儿贝2 混合块计分域内,会被过渡资格
        # 臂按虚拟 top3 合法买入(语义权威版本 = strategy-docs/
        # 12_line_and_intention.md §3),
        # 污染「机器方向不囤」断言。加拉赫 = 治疗 bonus 档键展开件
        # (盛会之星/治疗/击破面全库无羁绊块归属,探针判据静态可查)。
        missing_piece = '加拉赫'
        assert missing_piece in chars \
            and missing_piece not in comp.core_chars, '探针须在采购集非 core 面'
        from sr_od.application.currency_war.kernel.cw_comps import (
            COMP_LIBRARY,
            TRANSITION_BONDS,
            bond_score_members,
            carry_set,
        )
        assert missing_piece not in {
            m for b in TRANSITION_BONDS for m in bond_score_members(b)}, \
            '探针落在过渡计分域内(过渡资格臂会合法买入)'
        assert missing_piece not in {
            m for c in COMP_LIBRARY for m in carry_set(c)}, \
            '探针落在终局资格域内(货架资格臂会合法买入)'
        st = _state(hp=100, shop_cards=[_card(missing_piece, cost=1)])
        st['bench'] = [_bc(m) for m in comp.core_chars]
        st['front_row'] = [Unit(char_id='板上件锚', star=1)]
        sess = _session(IntentionState(), candidates=())   # 候选快照空
        act = _decide(st, sess)
        assert not (isinstance(act, CwActionBuyCardParam)
                    and act.card.name == missing_piece), \
            '无候选帧按机器方向囤货(甲臂退役失效)'


# ===== 乙臂退役:hub 死链与买因/拒因族不复现 =====


class TestHubRetired:
    def test_wildcard_no_auto_buy(self):
        """万金油退出义务买入面(总纲 §2.7 申报②;3.4):空窗帧的万金油
        件(花火,非候选线成员)不买——手里持有的未到两星前受万金油层
        档 8 保护(旧八档档 6,十档口径 design §2.2),
        无自动补货通道;hub_option_buy 买因不得复现。"""
        st = _state(gold=60, plane=2, node_kw='reward',
                    shop_cards=[_card('花火', cost=2)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert not (isinstance(act, CwActionBuyCardParam)
                    and act.card.name == '花火'
                    and act.reason.startswith('m2_')), \
            '万金油件经义务面买入(万金油退出义务买入面失效)'
        assert not [k for k in _ct(sess) if k.startswith('hub_option_')], \
            'hub_option_* 键族不得复现(乙臂退役)'

    def test_hub_reject_family_retired_not_silent(self):
        """乙臂拒因族退役后,席位/金不足形态照常拦截(非静默放行):
        席满帧非义务面件不买,拒因不再以 hub_option_* 分键显影。"""
        st = _state(gold=60, plane=2, shop_cards=[_card('花火', cost=2)],
                    bench=[_bc(f'注册表外高价值件{i}', star=2)
                           for i in range(BENCH_CAPACITY)],
                    deployed=[Unit(char_id='板上件锚', star=1)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert not isinstance(act, CwActionBuyCardParam) or act.card.name \
            != '花火', \
            '席满帧非义务面件不得无门放行'
        assert not [k for k in _ct(sess) if k.startswith('hub_option_')]


# ===== 丙臂收编:守息缺省并入统一金约束门 =====


class TestArmCHoldDefault:

    def test_no_candidate_frame_zero_buy_zero_paid_refresh(self):
        """丙臂守息缺省:无候选帧(p2plus 无目标、店面无资格件)零买入
        + 零付费刷新(三段式刷新判据在无合格缺口帧 fail-closed);收工
        关店(合法空帧)。"""
        st = _state(gold=45, plane=2,
                    shop_cards=[_card('注册表外散件Z', cost=1)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert not isinstance(act, (CwActionBuyCardParam,
                                    CwActionRefreshShopParam)), act
        assert isinstance(act, CwActionCloseShopParam)
        ct = _ct(sess)
        assert 'shop_no_target_hold_default' not in ct, \
            '丙臂独立守息分支键已收编(统一金约束门)'
        assert 'shop_r1_no_chaseable_member' not in ct, \
            'R1 判据键随路径总账退役'

    def test_upgrade_not_frozen_by_hold_default(self):
        """空窗帧升级语义(升级触发统一批重锚,11 号稿 §2):未锁定期
        零主动升级——触发辖域 = 锁定后 ∧ plane2_started,升级授权本体
        在空窗帧不存在(非守息冻结形态;原「板满等战力义务触发」臂
        已删,用户裁定 2026-10-18)。发展优先不变量的升级面载体 =
        锁定后无目标帧自然升级(键 natural,行为锁 =
        test_levelup_prob_axis::TestTriggerDispatch::
        test_natural_upgrade_without_target)。"""
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionLevelUpParam,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            entry,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            session_scope as _ss3,
        )
        sess_m3 = _session(IntentionState())
        cw4_gs(sess_m3, gold=80, level=4, round_num=2, node='battle',
               bench=[BenchSlot(kind='unit',
                                unit=Unit(char_id='注册表外散件A', star=1))],
               front_row=[Unit(char_id=f'注册表外散件{i}', star=2)
                          for i in range(4)], deploy_cap=4)
        cw4_gs(sess_m3).observe(
            cw4_gs(sess_m3).node_pos, (2, 2),
            sig=ChannelSig(family='obs', actor='cw4_seed',
                           mode='synthesized'))
        _ss3.mark_shop_handled(cw4_gs(sess_m3))
        out = entry.emit(sess_m3, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '未锁定期零主动升级(板满等战力义务触发删除,非守息冻结)'
