"""T-190 批B 锁线转型域收窄单帧锁(P88;ADR-0627)。

出处(单一源):
- 命题正本 = docs/develop/sr_od/application/currency_war/proofs/p88.md(§0 辖域/§1 调和
  引理/§3 解封方向式;收窄集 S_spec = {dominance_buy, hub_option_buy},
  豁免 ⇔ reason ∈ LAUNCH_CAUSE_BY_ARM ∖ S_spec 闭集单一源);
- 落码 = shop.py 两 S_spec 发射位辖域前置(分键 press_narrowed_
  transition_domain / press_narrowed_transition_domain_hub)+
  mandate.swap_transition_narrow_frame(域谓词单一源 = kernel
  ``_swap_transition_domain_of``)+ prep OpenShop 位对称观测
  (press_narrowed_transition_domain_prep_seen,仅登记零行为);
- mandate.dominance_buy_eligible docstring 辖域注(双引注:ADR-0616
  命题 4 + P88 调和引理)= 回滚合法依据封堵面。

锁清单(设计 v2 §六 批B 锁面):
- F1  D 帧收窄开火锁(dominance 位):D 帧将发射笔停发 + 分键帧级一次。
- F2  豁免锁(C1 解封):D 帧收窄后 C1 照常发射 = P88「C1 解封是收窄
      收益之一」的行为载体;豁免臂零消费收窄旗。
- F3  豁免锁(m2_locked_member):M2 义务族 D 帧零触碰。
- F4  闭集锁:LAUNCH_CAUSE_BY_ARM 15 键对账 + S_spec ⊆ 闭集 + 豁免 =
      闭集 ∖ S_spec 按 13 键差集断言(新买入臂入映射表即红,防第五臂
      复发同款纪律;对账符号 = mandate.PRESS_NARROWED_ARMS)。
- F5  零漂移锁(域边界三态):成型帧(fp≥1.00)/未锁帧/板未满帧
      dominance 逐位同旧行为(收窄域外零行为面)。
- F6  M6 零触碰锁:D 帧 m6_stockpile 照常发射(P88 §5 回填主体合法
      出口,ADR-0604 档 2 语义不动)。
- F7  单一源锁(域谓词第二源红):monkeypatch kernel 谓词翻转收窄判定
      ——双向(谓词 False ⇒ D 帧照买 / 谓词 True ⇒ 域外帧收窄),证明
      shop/mandate 无第二份合取(第二源 = 与部署域 M1″ 转型域分裂)。
- F8  prep OpenShop 登记对称锁:D 帧 OpenShop 照发(仅登记零行为)+
      prep_seen 键域内 1/域外 0。
- F9  hub 哨兵锁:hub 辖 unlocked 与 locked D 域结构性不相交(设计 v2
      修订 10 空开火面申报)——收窄旗位按 wiring 锁验证(monkeypatch
      旗 True ⇒ hub 停发 + 独立分键;旗缺省 ⇒ hub 照常),判读禁并桶。

变异红证(F1/F8/F9 三落点)= T-190-批B-交付报告.md §变异三连摘录。
构造声明:候选名注册表实名(线外/核心/枢纽,程序化选取与既有锁文件
同款);D 帧构造 = 锁线(ist.locked_comp)∧ fp<1.00(board 空 dict)
∧ 板满(deployed 占满 max_units)∧ armed=常量 True。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_intention
from sr_od.application.currency_war.kernel.cw_board_state import (
    board_state_bridge as _bridge,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    form_progress,
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import OpenShop
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.sell_gate import (
    LAUNCH_CAUSE_BY_ARM,
    WINDOW_LAUNCH_CAUSES,
)
from test.sr_od.app.currency_war.test_cw_leak_ladder import (
    _COMP,
    _tier_cost,
)
from test.sr_od.app.currency_war.test_cw_leak_ladder import (
    _bc as _lad_bc,
)
from test.sr_od.app.currency_war.test_cw_leak_ladder import (
    _card as _lad_card,
)
from test.sr_od.app.currency_war.test_cw_leak_ladder import (
    _km as _lad_km,
)
from test.sr_od.app.currency_war.test_cw_leak_ladder import (
    _off_name as _lad_off_name,
)
from test.sr_od.app.currency_war.test_cw_leak_ladder import (
    _session_stub as _lad_session,
)
from test.sr_od.app.currency_war.test_cw_leak_ladder import (
    _st as _lad_st,
)
from test.sr_od.app.currency_war.test_cw_no_target_three_arms import (
    IntentionState,
)
from test.sr_od.app.currency_war.test_cw_no_target_three_arms import (
    _card as _hub_card,
)
from test.sr_od.app.currency_war.test_cw_no_target_three_arms import (
    _ct as _hub_ct,
)
from test.sr_od.app.currency_war.test_cw_no_target_three_arms import (
    _decide as _hub_decide,
)
from test.sr_od.app.currency_war.test_cw_no_target_three_arms import (
    _session as _hub_session,
)
from test.sr_od.app.currency_war.test_cw_no_target_three_arms import (
    _state as _hub_state,
)

_NARROW_KEY = 'press_narrowed_transition_domain'
_NARROW_HUB_KEY = 'press_narrowed_transition_domain_hub'
_NARROW_PREP_KEY = 'press_narrowed_transition_domain_prep_seen'


def _d_frame_deps(n_km: int = 0) -> tuple[list[BenchChar], frozenset[str]]:
    """板满构造(level 5 ⇒ max_units=5,bench 空):锁线采购集前 n_km 名
    2★ 上板(其余线内名留作缺员),余位线外 2★ 垫件补满。
    返回 (板上件, 板上名集)——候选/缺员选取须 exclude 板上名集。"""
    km = _lad_km()
    names = list(km[:n_km])
    while len(names) < 5:
        names.append(_lad_off_name(exclude=tuple(names)))
    deps = [_lad_bc(m, star=2, slot=i + 1) for i, m in enumerate(names)]
    return deps, frozenset(names)


def _d_frame_st(gold: int, cards: list[ShopCard]) -> GameState:
    """D 帧默认形(n_km=0 纯垫件板):锁线 ∧ fp<1.00(board 空)∧ 板满。"""
    deps, _names = _d_frame_deps(0)
    return _lad_st(gold, cards, locked=True, deployed=deps)


def _decide(st: GameState, sess) -> object:
    return shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))


# ===== F1:dominance 位收窄开火锁 =====


class TestDominanceNarrowFire:

    def test_f1_d_frame_dominance_suppressed_with_key(self):
        """锁 F1:锁线 ∧ fp<1.00 ∧ 板满帧、线外 1★ 候选在售、资格门全过
        (gold>g* ∧ bench_free>0 ∧ 1★ 全额退 ∧ 结算线地板过)⇒ 不发射
        dominance_buy,分键 press_narrowed_transition_domain = 1(帧级,
        将发射笔口径)。前置:本帧确为 D 帧(谓词现读 True)。"""
        _deps, dep_names = _d_frame_deps(0)
        cand = _lad_off_name(exclude=tuple(dep_names))
        st = _d_frame_st(60, [_lad_card(cand, cost=2, star=1)])
        sess = _lad_session(locked=True)
        assert mandate.swap_transition_narrow_frame(st, sess) is True, \
            '前置失效:构帧非 D 帧(谓词现读 False,锁前提断裂)'
        act = _decide(st, sess)
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'dominance_buy'), \
            'D 帧 dominance 照发 = 收窄未生效(P88 辖域前置缺失)'
        ct = state_of(sess).cw4_counters
        assert ct.get(_NARROW_KEY) == 1, \
            f'收窄分键缺席或数值漂移: {ct.get(_NARROW_KEY)!r}'

    def test_f1b_candidate_none_frame_key_silent(self):
        """分键口径 = 将发射笔:同 D 帧但店无 dominance 候选(仅 2★
        线外卡,refund 门先拒)⇒ 无将发射笔,收窄分键零显影(禁把辖域
        机会帧计入开火数,防 §4.1-⑦① 覆盖比畸变)。"""
        _deps, dep_names = _d_frame_deps(0)
        cand = _lad_off_name(exclude=tuple(dep_names))
        st = _d_frame_st(60, [_lad_card(cand, cost=2, star=2)])
        sess = _lad_session(locked=True)
        assert mandate.swap_transition_narrow_frame(st, sess) is True
        _decide(st, sess)
        assert _NARROW_KEY not in state_of(sess).cw4_counters, \
            '无可发射笔帧分键照计 = 口径漂移(帧内无将发射笔)'


# ===== F2/F3:豁免锁 =====


class TestExemptionArms:

    def test_f2_c1_unsealed_in_d_frame(self):
        """锁 F2(C1 解封,P88 收窄收益行为载体):D 帧、名单核心卡
        (希儿,registry_core,线外 1★)在售 ⇒ dominance 被收窄停发后
        C1 照常发射 core_single_card_buy(零消费收窄旗)。"""
        st = _d_frame_st(55, [_lad_card('希儿', cost=3, star=1)])
        sess = _lad_session(locked=True)
        assert mandate.swap_transition_narrow_frame(st, sess) is True
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) \
            and act.reason == 'core_single_card_buy', \
            f'D 帧 C1 被误伤(豁免破面): act={act!r}'
        ct = state_of(sess).cw4_counters
        assert ct.get('core_dominance_buy_hit') == 1
        assert ct.get(_NARROW_KEY) == 1   # 收窄与豁免同帧并存(先抑后解封)

    def test_f3_m2_locked_member_untouched(self):
        """锁 F3(M2 义务族零触碰):D 帧、锁定采购集(hoard 宽集)缺员
        的阵营扩展成员 1★ 在售 ⇒ m2_locked_member 照常发射(义务族不进
        收窄集;序在 dominance 之前天然不受辖)。"""
        km = _lad_km()
        ist = SimpleNamespace(locked_comp=_COMP)
        _bm = cw_intention.locked_buy_membership(ist)
        assert _bm, '锁定采购集解析为空(锁前提失效)'
        _deps, dep_names = _d_frame_deps(2)
        target = next(m for m in sorted(_bm)
                      if m not in km and m not in dep_names)
        st = _d_frame_st(60, [_lad_card(target, cost=2, star=1)])
        sess = _lad_session(locked=True)
        assert mandate.swap_transition_narrow_frame(st, sess) is True
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'm2_locked_member', \
            f'D 帧 M2 义务买入被误伤(豁免破面): act={act!r}'
        assert _NARROW_KEY not in state_of(sess).cw4_counters


# ===== F4:闭集锁 =====


class TestClosedSet:

    def test_f4_launch_cause_closed_set_account(self):
        """锁 F4:LAUNCH_CAUSE_BY_ARM 全集对账(现值 15 键)+ 收窄集 ⊆
        闭集 + 豁免 = 闭集 ∖ S_spec 恰 13 键实名——新买入臂入映射表即
        红(强制分类进收窄/豁免,防绕辖域前置的第五臂)。"""
        keys = set(LAUNCH_CAUSE_BY_ARM)
        assert len(keys) == 15, \
            f'买因闭集漂移: {len(keys)} 键(预期 15;新臂须同步分类)'
        assert keys >= mandate.PRESS_NARROWED_ARMS, \
            f'收窄集越出闭集: {mandate.PRESS_NARROWED_ARMS - keys}'
        exempt = keys - mandate.PRESS_NARROWED_ARMS
        must_exempt = {
            'm2_line_member', 'm2_locked_member', 'm2_stockpile',
            'm2_merge_completion', 'core_single_card_buy',
            'core_single_card_buy:unlocked', 'm6_stockpile',
            'press_buy_deployable', 'ev_buy', 'transition_component_buy',
            'dead_gold_press_buy', 'fuel_filler_stall',
            't3_unlocked_hemostat',
        }
        assert exempt == must_exempt, \
            f'豁免集漂移: 多={exempt - must_exempt} 少={must_exempt - exempt}'
        # press τ=同轮(P88 §0 机制注:同轮拒帧覆盖判定最硬的因果类前提)
        assert LAUNCH_CAUSE_BY_ARM['dominance_buy'] == 'press'
        assert 'press' in WINDOW_LAUNCH_CAUSES
        assert 'hub_option_buy' not in WINDOW_LAUNCH_CAUSES


# ===== F5:零漂移锁(域边界三态)=====


class TestZeroDriftOutsideDomain:

    def test_f5a_formed_frame_dominance_unchanged(self):
        """域边界① 成型帧(fp≥1.00):锁线∧板满但线已成型 ⇒ 收窄域外,
        dominance 逐位同旧行为(分键零显影)。"""
        _deps, dep_names = _d_frame_deps(0)
        cand = _lad_off_name(exclude=tuple(dep_names))
        st = _d_frame_st(60, [_lad_card(cand, cost=2, star=1)])
        comp = get_comp(_COMP)
        tiers = dict(getattr(comp, 'form_tiers', {}) or {})
        assert tiers, '锁线 comp 无 form_tiers(锁前提失效)'
        st.board = dict(tiers)
        assert form_progress(comp, _bridge(st)) >= 1.0, '成型构帧失效(fp<1.0)'
        sess = _lad_session(locked=True)
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'dominance_buy', \
            f'成型帧 dominance 被误收窄(域外破面): act={act!r}'
        assert _NARROW_KEY not in state_of(sess).cw4_counters

    def test_f5b_unlocked_full_board_dominance_unchanged(self):
        """域边界② 未锁帧:板满∧线外 1★ 在售但未锁线 ⇒ D 域外(armed
        ∧ locked 合取),dominance 照发(未锁域零漂移;与 hub 辖 unlocked
        的带不相交声明同源)。"""
        _deps, dep_names = _d_frame_deps(0)
        cand = _lad_off_name(exclude=tuple(dep_names))
        st = _lad_st(60, [_lad_card(cand, cost=2, star=1)],
                     locked=False, deployed=_deps)
        sess = _lad_session(locked=False)
        assert mandate.swap_transition_narrow_frame(st, sess) is False
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'dominance_buy'
        assert _NARROW_KEY not in state_of(sess).cw4_counters

    def test_f5c_locked_unfull_board_dominance_unchanged(self):
        """域边界③ 板未满帧:锁线∧fp<1.00 但板未满(既有 leak_ladder L3
        形态)⇒ D 域外,dominance 照发。"""
        km = _lad_km()
        cand = _lad_off_name(exclude=tuple(km))
        st = _lad_st(60, [_lad_card(cand, cost=2, star=1)], locked=True)
        sess = _lad_session(locked=True)
        assert mandate.swap_transition_narrow_frame(st, sess) is False, \
            '板未满帧误判 D 帧(board_full 输入装配漂移)'
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'dominance_buy'
        assert _NARROW_KEY not in state_of(sess).cw4_counters


# ===== F6:M6 两域零触碰锁 =====


class TestM6ZeroTouch:

    def test_f6_m6_stockpile_fires_in_d_frame(self):
        """锁 F6(shop M6 臂):D 帧、塌缩带档匹配线外件在售 ⇒ dominance
        被收窄后 m6_stockpile 照常发射(P88 §5 溢余出口守恒:压库 = 回填
        主体合法出口;ADR-0604 档 2 语义零改动)。"""
        _deps, dep_names = _d_frame_deps(0)
        cost = _tier_cost()
        cand = _lad_off_name(exclude=tuple(dep_names), min_cost=cost)
        st = _d_frame_st(60, [_lad_card(cand, cost=cost, star=1)])
        sess = _lad_session(locked=True)
        assert mandate.swap_transition_narrow_frame(st, sess) is True
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'm6_stockpile', \
            f'D 帧 M6 被误触/被收窄连坐(零触碰破面): act={act!r}'
        ct = state_of(sess).cw4_counters
        assert ct.get(_NARROW_KEY) == 1
        assert 'm6_stockpile' not in mandate.PRESS_NARROWED_ARMS, \
            'm6_stockpile 混入收窄集(闭集分类破面)'


# ===== F7:单一源锁(域谓词第二源红)=====


class TestPredicateSingleSource:

    def test_f7_predicate_flip_controls_narrowing(self, monkeypatch):
        """锁 F7:kernel 谓词翻转 ⇒ 收窄判定逐位跟随(双向)。若店侧
        内联第二份合取(armed∧locked∧fp<1.00∧板满 手搓),patch 单一源
        不再改变行为 = 本锁红。"""
        _deps, dep_names = _d_frame_deps(0)
        cand = _lad_off_name(exclude=tuple(dep_names))
        # 方向①:D 帧输入 + 谓词强制 False ⇒ 不收窄(dominance 照发)
        st = _d_frame_st(60, [_lad_card(cand, cost=2, star=1)])
        sess = _lad_session(locked=True)
        monkeypatch.setattr(mandate, '_swap_transition_domain_of',
                            lambda *a, **kw: False)
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'dominance_buy', \
            '谓词 False 后 D 帧仍收窄 = 存在第二份合取(单一源破面)'
        # 方向②:域外输入(板未满)+ 谓词强制 True ⇒ 照收窄
        monkeypatch.setattr(mandate, '_swap_transition_domain_of',
                            lambda *a, **kw: True)
        st2 = _lad_st(60, [_lad_card(cand, cost=2, star=1)], locked=True)
        sess2 = _lad_session(locked=True)
        act2 = _decide(st2, sess2)
        assert not (isinstance(act2, BuyCard)
                    and act2.reason == 'dominance_buy'), \
            '谓词 True 后域外帧不收窄 = 域外有独立判定(单一源破面)'
        assert state_of(sess2).cw4_counters.get(_NARROW_KEY) == 1


# ===== F8:prep OpenShop 登记对称锁 =====


def _prep_session() -> StrategySession:
    s = StrategySession()
    st = state_of(s)
    st.cw4_counters = {}
    st.target_comp = get_comp(_COMP)
    # pair/phase 字段缺省 = 备战链 IntentionState 读端零触雷
    #(鸭子桩字段面与 IntentionState 对齐,locked_comp 单判同源)。
    st.v3_intention = SimpleNamespace(locked_comp=_COMP, p1_pair=(),
                                      transition_pair=(), phase='locked')
    return s


def _prep_frame(deployed: list[BenchChar], bench: list[BenchChar]):
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
        MandateFrame,
    )
    return MandateFrame(gold=60, level=3, bench=bench,
                        deployed=deployed, deploy_cap=3, node_type=None,
                        stop_flag=False, k_members=('目标件',), round_num=3)


def _prep_state(deployed: list[BenchChar]) -> GameState:
    st = GameState(gold=60, level=3, round_num=3)
    st.plane = 2
    st.deployed = list(deployed)
    return st


class TestPrepOpenShopSymmetry:

    def test_f8_d_frame_open_shop_emitted_and_keyed(self):
        """锁 F8(设计修订 3:prep 位仅登记对称观测,不挂行为收窄):
        D 帧 prep dominance OpenShop **照发**(行为零变更)+ 对称观测键
        press_narrowed_transition_domain_prep_seen = 1。"""
        dep = [_lad_bc(f'板垫{i}', star=2, slot=i + 1) for i in range(3)]
        bench = [_lad_bc(f'席垫{i}', star=1, slot=i + 1)
                 for i in range(BENCH_CAPACITY - 1)]
        sess = _prep_session()
        out = mandate.run_mandate(_prep_frame(dep, bench), sess,
                                  state=_prep_state(dep))
        st = _prep_state(dep)
        assert mandate.swap_transition_narrow_frame(st, sess) is True, \
            '前置失效:prep 构帧非 D 帧'
        assert any(isinstance(e.action, OpenShop)
                   and e.reason == 'dominance_buy' for e in out), \
            'D 帧 prep dominance OpenShop 被收窄连坐(修订 3 破面)'
        assert state_of(sess).cw4_counters.get(_NARROW_PREP_KEY) == 1

    def test_f8b_out_of_domain_frame_key_silent(self):
        """对称键域外静默:板未满 prep 帧 OpenShop 照发 + 观测键零显影
        (观测域 = D 帧,禁全帧计数)。"""
        dep = [_lad_bc(f'板垫{i}', star=2, slot=i + 1) for i in range(2)]
        bench = [_lad_bc(f'席垫{i}', star=1, slot=i + 1)
                 for i in range(BENCH_CAPACITY - 1)]
        sess = _prep_session()
        out = mandate.run_mandate(_prep_frame(dep, bench), sess,
                                  state=_prep_state(dep))
        assert any(isinstance(e.action, OpenShop)
                   and e.reason == 'dominance_buy' for e in out)
        assert _NARROW_PREP_KEY not in state_of(sess).cw4_counters


# ===== F9:hub 哨兵锁(wiring 面)=====


class TestHubSentinel:

    def test_f9_hub_natural_frame_untouched(self):
        """锁 F9 控制(空开火面申报的常态面):未锁无目标帧(乙臂自然
        辖域)收窄旗恒 False ⇒ hub 照常发射、哨兵键零显影。"""
        st = _hub_state(shop_cards=[_hub_card('花火', cost=2)])
        sess = _hub_session(IntentionState())
        assert mandate.swap_transition_narrow_frame(st, sess) is False
        act = _hub_decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'hub_option_buy'
        ct = _hub_ct(sess)
        assert ct.get('hub_option_buy_hit') == 1
        assert _NARROW_HUB_KEY not in ct

    def test_f9b_flag_true_suppresses_hub_with_dedicated_key(
            self, monkeypatch):
        """锁 F9(wiring 面):收窄旗 True ⇒ hub_option_buy 停发 + 独立
        分键(press_narrowed_transition_domain_hub)帧级一次。结构性
        空开火面(hub 辖 unlocked 与 locked D 域不相交)下生产不可达,
        本锁 = P86 辖域变更哨兵的传动验证(旗位接线有牙,非死码);
        变异(摘 hub 位收窄)⇒ 本锁红。"""
        st = _hub_state(shop_cards=[_hub_card('花火', cost=2)])
        sess = _hub_session(IntentionState())
        monkeypatch.setattr(mandate, 'swap_transition_narrow_frame',
                            lambda *a, **kw: True)
        act = _hub_decide(st, sess)
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'hub_option_buy'), \
            '旗 True 帧 hub 照发 = hub 位辖域前置缺失(哨兵死码)'
        ct = _hub_ct(sess)
        assert ct.get(_NARROW_HUB_KEY) == 1
        assert ct.get('press_narrowed_transition_domain', 0) == 0, \
            'hub 位与 dominance 位分键并桶(判读禁并桶破面)'
