"""14号稿 P1 消费臂落码批·检查点 1 锁组(§7.2)。

设计出处 = docs/develop/currency_war/strategy-docs/14_p1_consume_arms.md
(v4.2.2)§3(臂①囤腿)/§4(arm0 升级授权回补)/§7.1/§7.2。覆盖:
- 臂① m2_stockpile:j=1 发射(M2 后、M2b 前)/ cnt2>0 帧路径排除
  (N2:臂①不制造死库存)/ star_mismatch_skip 分键(W4)/ bench 满
  先 M4 腾席(Y5)/ stockpile_unaffordable。j=2 帧归 M2b 独占的互斥面
  与 §3.6 满栏例外发射面由 test_cw_supply_merge_crisis.py::
  TestMergeCompletionBuy 承载(跨文件择一,2026-09-08 瘦身批);
- M2b:候选 star==1 过滤(Y4,m2b_star_mismatch 分键);
- arm0 v2:need 现量口径(Y3)/ level_readable 消费端 fail 向(C4/W6)
  / pop_slot 前置放宽(§4.3,只辖放宽腿;基础三态理由面在
  test_cw_mandate_v1.py::test_d_lv7_pop_slot_explicit_reasons)。

锁契约:docstring 引本篇章节为设计出处;不锁分布数值(测试纪律第 8 条)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BuyCard,
    GameState,
    LevelUpShop,
    SellBench,
    simulate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    arm0_level_lag,
    arm0_need,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_comp as _comp_single_source,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_members as _members_of,
)

_LOCK_COMP = '列车同行'


def _comp():
    """本文件锚定具名套(``列车同行``;六件套缺省锚 = 首个 core 套)。"""
    return _comp_single_source(_LOCK_COMP)


def _members() -> list[str]:
    return _members_of(_comp())


def _shop_session(comp) -> SimpleNamespace:
    # 策略器字段(target_comp/cw4_counters)经 state_of 载体(session 职责
    # 分离迁移后生产唯一读面;对 SimpleNamespace 桩同样生效)。
    s = SimpleNamespace()
    st = state_of(s)
    st.cw4_counters = {}
    st.target_comp = comp
    return s


def _st(gold: int = 30, shop_cards=None, bench=None, deployed=None,
        level: int = 7, readable: bool = True) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2, hp=60)
    st.level_readable = readable
    st.plane = 2
    st.shop = shop_cards if shop_cards is not None else []
    st.bench = bench if bench is not None else []
    st.deployed = deployed if deployed is not None else []
    return st


def _decide(st, sess):
    return shop_decide(st, sess, SimpleNamespace(ev_arm='full'))


def shop_decide(st, sess, cfg):
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
    return shop.decide_shop_action(st, sess, cfg)


# ===== 臂① m2_stockpile(§3.2-3.4)=====


class TestM2StockpileArm1:

    def test_j1_second_copy_bought_as_stockpile(self):
        """§3.2 触发域:cnt1(m)=1 ∧ cnt2=0 ∧ 店内 1★ 在售 ⇒ 第 2 张
        经臂①义务买入(reason='m2_stockpile',不走息律门)。j=0 帧
        (未持有)走 M2 主通道的覆盖面由 test_cw_shop_line.py::
        test_buy_face_m2_line_member 承载(跨文件择一,不双锁)。"""
        m = _members()[0]
        st = _st(gold=30, shop_cards=[_card(m, 3)],
                 bench=[_bc(m, slot=1)])
        sess = _shop_session(_comp())
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'm2_stockpile'

    def test_cnt2_positive_frame_arm1_excluded(self):
        """cnt2>0 帧:臂①路径排除(N2 措辞收窄——锁「臂①不制造死库存」:
        cnt1=1∧cnt2=1 时臂①/M2b 双双不判,不买第 2 张 1★ 制造
        cnt1=2∧有2★ 死库存)。"""
        m = _members()[0]
        st = _st(gold=30, shop_cards=[_card(m, 3)],
                 bench=[_bc(m, slot=1), _bc(m, slot=2, star=2)])
        sess = _shop_session(_comp())
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard), 'cnt2>0 帧臂①不得买入'

    def test_star_mismatch_shop_card_counted_not_silent(self):
        """W4:cnt1 达标 ∧ 店内仅同名 2★ 直出卡 ⇒ m2_stockpile_star_mismatch
        分键跳过而非静默(×3 价买 2★ 不成链,§3.4 Y4;与 M2b 分键,低-1)。"""
        m = _members()[0]
        st = _st(gold=30, shop_cards=[_card(m, 3, star=2)],
                 bench=[_bc(m, slot=1)])
        sess = _shop_session(_comp())
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        assert state_of(sess).cw4_counters.get('m2_stockpile_star_mismatch', 0) >= 1
        assert 'm2b_star_mismatch' not in state_of(sess).cw4_counters

    def test_bench_full_m4_frees_seat_then_buys(self):
        """Y5:bench 满时先 M4 腾席(非 B 燃料件)再买入——满栏例外只辖
        合成语境,j=1 帧走 M4;拒因 bench_full 仅记腾席后仍满帧。"""
        m = _members()[0]
        comp = _comp()
        all_fac = set(comp.all_factions)
        hoard = cw_intention_hoard(comp)
        offline = [n for n, ch in _all_chars().items()
                   if n not in hoard
                   and not (set(ch.factions) | set(ch.flows)) & all_fac]
        assert offline, '锁前提:存在 off-line 非 B 燃料件'
        bench = [_bc(n, slot=i + 1)
                 for i, n in enumerate(offline[:BENCH_CAPACITY - 1])]
        bench.append(_bc(m, slot=BENCH_CAPACITY))   # cnt1=1 的成员在 bench
        st = _st(gold=30, shop_cards=[_card(m, 3)], bench=bench)
        sess = _shop_session(comp)
        act = _decide(st, sess)
        assert isinstance(act, SellBench), '满栏先 M4 腾席(off-line 燃料件)'
        assert (act.expect or '') != m, '腾席不得卖囤腿目标本身'
        st2 = simulate(st, act)
        act2 = _decide(st2, sess)
        assert isinstance(act2, BuyCard) and act2.reason == 'm2_stockpile'

    def test_bench_full_no_fuel_honest_bench_full_key(self):
        """腾席后仍满(无可卖燃料:B 成员免卖 + 填充件非 1★)⇒
        'bench_full' 普通席闸键(非 merge_bench_full,j=1 无合成语义键名
        不得混用,§3.2 拒因分键)。

        确定性构造注:样本集用 sorted(集合直list切片跨进程随哈希随机化,
        PYTHONHASHSEED 敏感——曾致本锁非确定性红:随机样本混入 m 的 2★
        副本时 cnt2>0,臂①正确跳过、bench_full 不计数);m 从样本剔除,
        保 cnt1=1∧cnt2=0 恒成立。"""
        m = _members()[0]
        sample = sorted(cw_intention_hoard(_comp()) - {m})
        bench = [_bc(n, slot=i + 1, star=2) for i, n in
                 enumerate(sample[:BENCH_CAPACITY - 1])]
        bench.append(_bc(m, slot=BENCH_CAPACITY))   # cnt1=1 成员占末席
        st = _st(gold=30, shop_cards=[_card(m, 3)], bench=bench)
        sess = _shop_session(_comp())
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        assert state_of(sess).cw4_counters.get('bench_full', 0) >= 1
        assert 'merge_bench_full' not in state_of(sess).cw4_counters

    def test_unaffordable_counted(self):
        """金不足 ⇒ stockpile_unaffordable 分键(义务面拒因零静默)。"""
        m = _members()[0]
        st = _st(gold=1, shop_cards=[_card(m, 3)], bench=[_bc(m, slot=1)])
        sess = _shop_session(_comp())
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        assert state_of(sess).cw4_counters.get('stockpile_unaffordable', 0) >= 1


# ===== M2b:Y4 星过滤(§3.6 满栏例外发射面在
# test_cw_supply_merge_crisis.py::TestMergeCompletionBuy)=====


class TestM2bStarFilter:

    def test_merge_star_filter_only_2star_card(self):
        """Y4:完成段(cnt=2∧无2★)但店内仅 2★ 直出卡 ⇒ 不买
        (+m2b_star_mismatch 分键,与臂①同型过滤三消费面记全,低-1)。"""
        m = _members()[0]
        bench = [_bc(m, slot=1), _bc(m, slot=2)]
        st = _st(gold=30, shop_cards=[_card(m, 3, star=2)], bench=bench)
        sess = _shop_session(_comp())
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        assert state_of(sess).cw4_counters.get('m2b_star_mismatch', 0) >= 1
        assert 'm2_stockpile_star_mismatch' not in state_of(sess).cw4_counters


# ===== arm0 v2(§4.2 Y3/C4/W6)=====


class TestArm0LevelLag:

    def test_need_name_dedup_semantics(self):
        """排除口径 = 纯 name(与 check_seats/cw_deploy_logic
        部署去重真实语义对齐):同名异星 bench 件**不计**(部署按 name
        去重,同名异星永不可上阵——旧 (名,星) 口径会虚计 need);
        bench 同名 ×2 去重计 1(双计消除)。"""
        k = ('甲', '乙')
        deployed = [_bc('甲', star=1, slot=1)]
        bench = [_bc('甲', star=2, slot=1),   # 同名(bench):去重不计
                 _bc('乙', star=1, slot=2),   # 计 1
                 _bc('乙', star=1, slot=3),   # 同名 ×2:去重不计
                 _bc('丙', slot=3)]           # 非 k:不计
        need = arm0_need(deployed, bench, k)
        assert need == 1 + 1, 'deployed 1 + bench 独名(乙) 1(双计消除)'
        assert arm0_need([], [_bc('乙', slot=1), _bc('乙', slot=2)],
                         ('乙',)) == 1

    def test_need_no_false_trigger_for_same_name_diff_star(self):
        """虚触发形态锁:场上已有甲,bench 仅同名异星甲′ ⇒ need 不含
        (不可上阵的件不买等级)。"""
        k = ('甲',)
        deployed = [_bc('甲', star=1, slot=1)]
        bench = [_bc('甲', star=2, slot=1)]
        trig, _ = arm0_level_lag(1, True, deployed, bench, k, 5)
        assert trig is False, '同名异星形态不得虚触发升级'
        # level=1 不触发已蕴含 need≤1(need 含同名异星件则 trig=True),
        # need 的排除口径由 test_need_name_dedup_semantics 单独辖。

    def test_level_lag_triggers(self):
        k = ('甲', '乙', '丙', '丁')
        deployed = [_bc('甲', slot=1), _bc('乙', slot=2)]
        bench = [_bc('丙', slot=1), _bc('丁', slot=2)]
        # need=4 > level=3 ⇒ 触发
        trig, key = arm0_level_lag(3, True, deployed, bench, k, 5)
        assert trig is True and key == ''

    def test_level_readable_false_fails_closed(self):
        """C4/W6:level 不可信帧 fail 向不触发,分键 'level_unreadable'。"""
        k = ('甲', '乙', '丙', '丁')
        deployed = [_bc('甲', slot=1)]
        bench = [_bc('丙', slot=1), _bc('丁', slot=2)]
        trig, key = arm0_level_lag(3, False, deployed, bench, k, 5)
        assert trig is False and key == 'level_unreadable'

    def test_level_at_cap_no_trigger(self):
        k = ('甲',)
        deployed = [_bc('甲', slot=1)]
        trig, key = arm0_level_lag(5, True, deployed, [], k, 5)
        assert trig is False and key == 'level_at_cap'

    def test_mandate_arm0_emits_levelup_and_unreadable_fails_closed(self):
        """消费端(§7.1 mandate.py 行):arm0 触发 ⇒ M3 批经验授权发射;
        level_readable=False ⇒ 不发射 + arm0_level_unreadable 分键(W6)。"""
        from sr_od.application.currency_war.strategies.impl.cw_strategy import (
            StrategySession,
        )
        k = ('甲', '乙', '丙', '丁')
        deployed = [_bc('甲', slot=1), _bc('乙', slot=2)]
        bench = [_bc('丙', slot=1), _bc('丁', slot=2)]
        frame = mandate.MandateFrame(
            gold=60, level=2, bench=bench, deployed=deployed,
            deploy_cap=5, node_type=None, stop_flag=False, k_members=k,
            round_num=3)
        # state.hp/hp_readable=健康真值(危机门放行;血线判据不在本批辖域);
        # level=2 < max_units()=3 且 < need=4(arm0 触发域)
        state = GameState(gold=60, level=2, round_num=3)
        state.hp = 100
        state.hp_readable = True
        state.level_readable = True
        state.deploy_cap = 5   # 宝钻叠加口径(max_units=5),arm0 非满级
        sess = StrategySession()
        state_of(sess).cw4_counters = {}
        out = mandate.run_mandate(frame, sess, state=state)
        assert any(e.reason.startswith('m3_levelup_batch') for e in out), \
            'arm0 触发须经 M3 判据链发射批经验授权'
        # C4/W6:不可信帧 fail 向
        state.level_readable = False
        sess2 = StrategySession()
        state_of(sess2).cw4_counters = {}
        out2 = mandate.run_mandate(frame, sess2, state=state)
        assert not any(e.reason.startswith('m3_levelup_batch')
                       for e in out2)
        assert state_of(sess2).cw4_counters.get('arm0_level_unreadable', 0) >= 1


# ===== pop_slot 前置放宽(§4.3)=====


class TestPopSlotRelaxation:

    def test_relaxed_to_buyable_candidate(self):
        """§4.3:「bench 有候选 ∨ 买得起候选」——满编+空 bench+富金帧,
        买入面有可即时买入线内候选(affordable ∧ bench_free≥1)⇒ 发射。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.levelup import (
            pop_slot,
        )
        ok, why = pop_slot(5, 5, 60, 0, 0, buyable_candidate=True,
                           bench_free=2)
        assert ok is True and why == 'full_rich_with_candidate'
        # 买不起(金低于地板 floor_gold)仍拒(放宽腿过候选门后金闸独立生效)
        ok3, why3 = pop_slot(5, 5, 5, 0, 10, buyable_candidate=True,
                             bench_free=2)
        assert ok3 is False and why3 == 'gold_below_floor'


# ===== 检查点 2:λ_death 死亡线(血线硬地板 ≤15 族)+ F1 刷新账对齐 =====


class TestP1BloodFloorPredicate:

    def test_floor_predicate_four_states(self):
        """判据本体(p1_blood_floor,单一源 λ_death.HP_BAND_NEAR_DEATH):
        P1 hp≤15 ∧ 可信 ⇒ True;hp>15 ⇒ False;不可信/hp 无值 fail 向
        ⇒ False(各消费面维持既有语义)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
            p1_blood_floor,
        )
        st = _st(gold=30)
        st.plane = 1
        st.hp = 10
        st.hp_readable = True
        st.hp_trusted = False
        assert p1_blood_floor(st) is True
        st.hp = 20
        assert p1_blood_floor(st) is False
        st.hp = 10
        st.hp_readable = False   # 不可信帧 fail 向(P1 hp 毒化史口径)
        assert p1_blood_floor(st) is False
        st.hp_readable = True
        st.hp = None
        assert p1_blood_floor(st) is False

    def test_floor_plane2_excluded(self):
        """落地审清单应-A():P2 帧 hp≤15 不得开 P1 解锁包(授权族 = P1 血线
        硬地板;P2 深血线有在产 p2_crisis_band 更宽域介入)——判据 False
        ∧ M3 停付照常(P2 危机带 41 辖),无授权域外搭车。"""
        from sr_od.application.currency_war.kernel.cw_registry import (
            DEFAULT_REGISTRY,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.levelup import (
            level_spend_blocked,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
            p1_blood_floor,
        )
        st = _st(gold=30)
        st.plane = 2
        st.hp = 10
        st.hp_readable = True
        assert p1_blood_floor(st) is False
        assert level_spend_blocked(
            st, SimpleNamespace(node_type_current='normal'),
            DEFAULT_REGISTRY) is True, 'P2 深血线帧不得经 P1 地板解锁'

    def test_interest_ban_on_floor(self):
        """凑息禁令(解锁包件②):死亡线帧 sell_for_interest 不发射,
        ([], 'blood_floor') 零静默;非死亡线帧语义零变化;state=None
        语境缺失按保守端照禁(fail-closed 防御补口)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.sell import (
            sell_for_interest,
        )
        st_floor = _st(gold=30)
        st_floor.plane = 1
        st_floor.hp = 10
        slots, key = sell_for_interest(30, [], 4, (), state=st_floor)
        assert slots == [] and key == 'blood_floor'
        slots_n, key_n = sell_for_interest(30, [], 4, (), state=None)
        assert slots_n == [] and key_n == 'blood_floor'
        st_ok = _st(gold=30)
        st_ok.plane = 1
        st_ok.hp = 60
        slots2, key2 = sell_for_interest(30, [], 4, (), state=st_ok)
        assert key2 != 'blood_floor'

    def test_m3_spend_unblocked_on_floor(self):
        """M3 破息(解锁包件①):死亡线帧停付线让位——hp=8(⊂ 停付线
        ≈11)与 hp=13(停付线与地板之间)均不 block;非死亡线帧(位面2
        hp=25 ⊂ 危机带 41)停付照常(P21 语义在地板域外不松动)。"""
        from sr_od.application.currency_war.kernel.cw_registry import (
            DEFAULT_REGISTRY,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.levelup import (
            level_spend_blocked,
        )
        for hp in (8, 13):
            st = _st(gold=30)
            st.hp = hp
            st.hp_readable = True
            st.plane = 1
            assert level_spend_blocked(
                st, SimpleNamespace(node_type_current='normal'),
                DEFAULT_REGISTRY) is False, f'hp={hp} 死亡线帧须解锁'
        st_ctrl = _st(gold=30)
        st_ctrl.hp = 25
        st_ctrl.hp_readable = True
        st_ctrl.plane = 2
        assert level_spend_blocked(
            st_ctrl, SimpleNamespace(node_type_current='normal'),
            DEFAULT_REGISTRY) is True, '非死亡线危机帧行为零变化'

    def test_floor_does_not_break_arm0_chain(self):
        """发展主线不受影响(死亡线定位声明):floor 帧经 arm0 触发的
        M3 批经验授权照常发射(解锁不是堵塞)。"""
        from sr_od.application.currency_war.strategies.impl.cw_strategy import (
            StrategySession,
        )
        frame = mandate.MandateFrame(
            gold=60, level=2,
            bench=[_bc('丙', slot=1), _bc('丁', slot=2)],
            deployed=[_bc('甲', slot=1), _bc('乙', slot=2)],
            deploy_cap=5, node_type=None, stop_flag=False,
            k_members=('甲', '乙', '丙', '丁'), round_num=3)
        state = GameState(gold=60, level=2, round_num=3)
        state.hp = 10
        state.hp_readable = True
        state.level_readable = True
        state.deploy_cap = 5
        state.plane = 1
        sess = StrategySession()
        state_of(sess).cw4_counters = {}
        out = mandate.run_mandate(frame, sess, state=state)
        assert any(e.reason.startswith('m3_levelup_batch') for e in out)


class TestF1LedgerBuyMembersAlignment:

    def test_r1_idle_gold_no_chaseable_key(self):
        """金过剩 ∧ 合格集空 ⇒ r1_idle_gold_no_chaseable 语境分键
        (刷新让位显影;(b)3 永久挂空后该帧无承重件,只观测禁调参)。"""
        comp = _comp()
        core = _members()
        bench = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(core)]
        i = len(bench)
        while len(bench) < BENCH_CAPACITY:
            bench.append(_bc(f'填充件{i}', star=2, slot=i + 1))
            i += 1
        st = _st(gold=100, level=9, shop_cards=[], bench=bench)
        st.hp = 60
        st.hp_readable = True
        sess = _shop_session(comp)
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        assert state_of(sess).cw4_counters.get('shop_r1_no_chaseable_member', 0) >= 1
        assert state_of(sess).cw4_counters.get('r1_idle_gold_no_chaseable', 0) >= 1


# ===== 升级授权三臂并联(P1消费臂批落地审阻-1/应-2)=====


class TestShopM3TripleArm:

    def _decide_sess(self, comp):
        from sr_od.application.currency_war.strategies.impl.cw_strategy import (
            StrategySession,
        )
        s = StrategySession()
        state_of(s).cw4_counters = {}
        state_of(s).target_comp = comp
        return s

    def test_full_board_empty_bench_rich_gold_gets_levelup(self):
        """病灶场景锁(阻-1):板满(deployed=cap)+bench 空+富金+店内
        线内候选可即时买入 ⇒ 商店帧升级授权直发(pop_slot 承载:满编+
        富金+买得起候选;arm1 在 bench 空形态恒 False)。店内候选用 2★
        同名卡(臂①只囤 1★,star_mismatch 分键),隔离 M2 面抢占。"""
        comp = _comp()
        k = _members()
        deployed = [_bc(n, slot=i + 1) for i, n in enumerate(k[:3])]
        st = _st(gold=100, level=3, shop_cards=[_card(k[0], 2, star=2)],
                 bench=[], deployed=deployed)
        st.hp = 100
        st.hp_readable = True
        sess = self._decide_sess(comp)
        act = _decide(st, sess)
        assert isinstance(act, LevelUpShop), \
            '板满+bench 空+富金帧商店栈须有升级授权(pop_slot 承载)'
        assert act.auth_basis.startswith('m3_batch:pop'), \
            'pop_slot 承载帧 auth_basis 须带臂分键(可归因)'

    def test_shop_arm0_level_lag_triggers(self):
        """应-2 商店栈 arm0 接线:等级落后于上阵需求(level 3 < need 4,
        cap=5)⇒ 商店帧发批经验授权(双栈同义面,与 mandate M3 一致)。"""
        comp = _comp()
        k = _members()
        st = _st(gold=60, level=3, shop_cards=[],
                 deployed=[_bc(k[0], slot=1), _bc(k[1], slot=2)],
                 bench=[_bc(k[2], slot=1), _bc(k[3], slot=2)])
        st.hp = 60
        st.hp_readable = True
        st.level_readable = True
        st.deploy_cap = 5
        sess = self._decide_sess(comp)
        act = _decide(st, sess)
        assert isinstance(act, LevelUpShop), \
            'arm0 触发形态商店帧须发升级授权(应-2 双栈断层修复)'
        assert act.auth_basis.startswith('m3_batch:arm0'), \
            'auth_basis 三臂分键(可归因,P1消费臂批落地审三低项)'

    def test_mandate_pop_slot_wired(self, monkeypatch):
        """应-B:mandate 备战栈 M3 接入 pop_slot(满编+富金+bench 有线内
        候补 = 备战帧触发域;备战帧店面不可读 ⇒ buyable 腿只在商店栈,
        双栈分域声明);否向理由留决策迹(state_of(session).cw4_pop_slot_why)。"""
        from sr_od.application.currency_war.strategies.impl.cw_strategy import (
            StrategySession,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
            levelup as crit_levelup_mod,
        )
        calls: list[tuple] = []
        real = crit_levelup_mod.pop_slot

        def _spy(*a, **kw):
            calls.append((a, kw))
            return real(*a, **kw)

        monkeypatch.setattr(crit_levelup_mod, 'pop_slot', _spy)
        # 板满(deployed=cap 3)+ bench 有线内候补 + 富金(gold ≥ g*)
        frame = mandate.MandateFrame(
            gold=100, level=3,
            bench=[_bc('丙', slot=1)],
            deployed=[_bc('甲', slot=1), _bc('乙', slot=2),
                      _bc('戊', slot=3)],
            deploy_cap=3, node_type=None, stop_flag=False,
            k_members=('甲', '乙', '丙', '丁'), round_num=3)
        state = GameState(gold=100, level=3, round_num=3)
        state.hp = 100
        state.hp_readable = True
        state.level_readable = True
        sess = StrategySession()
        state_of(sess).cw4_counters = {}
        out = mandate.run_mandate(frame, sess, state=state)
        assert calls, 'mandate 栈 pop_slot 必须被消费(阻-1 同型,禁假活)'
        args, kwargs = calls[0]
        assert len(args) == 5 and not kwargs.get('buyable_candidate'), \
            '备战帧店面不可读:buyable 腿不传/恒 False(分域)'
        assert any(e.reason.startswith('m3_levelup_batch') for e in out)
        assert state_of(sess).cw4_pop_slot_why


# ===== 拒因一致性(P1消费臂批落地审应-1)=====
# (下同:本节「落地审」均指该清单)


class TestShopRejectsArm1Semantics:

    def test_stockpile_frames_reject_keys(self):
        """cnt1=1 帧拒因按臂①门序细分(中性 'owned' 退役):金席俱足 =
        stockpile_ready;金不足 = stockpile_unaffordable;满栏 =
        stockpile_bench_full。"""
        comp = _comp()
        m = _members()[0]
        fill = [_bc(f'填充件{i}', star=2, slot=i + 1) for i in range(1, 9)]
        cases = [
            (_st(gold=30, shop_cards=[_card(m, 3)],
                 bench=[_bc(m, slot=1)]), 'stockpile_ready'),
            (_st(gold=1, shop_cards=[_card(m, 3)],
                 bench=[_bc(m, slot=1)]), 'stockpile_unaffordable'),
            (_st(gold=30, shop_cards=[_card(m, 3)],
                 bench=[_bc(m, slot=9)] + fill), 'stockpile_bench_full'),
        ]
        for st, want in cases:
            out = shop_rejects(st, comp)
            assert out.get(m) == want, f'{want}: 实得 {out.get(m)}'

    def test_cnt2_positive_still_owned(self):
        """cnt2>0 让渡死库存帧(§3.7)维持中性 'owned'(臂①不辖)。"""
        m = _members()[0]
        st = _st(gold=30, shop_cards=[_card(m, 3)],
                 bench=[_bc(m, slot=1), _bc(m, slot=2, star=2)])
        out = shop_rejects(st, comp=_comp())
        assert out.get(m) == 'owned'

    def test_m6_stockpile_excludes_line_members(self):
        """落地审清单存疑收口(N2/§3.7):cnt1=1∧cnt2=1 形态帧,M6 压库
        不得买线内 1★ 副本(绕过臂① cnt2==0 守卫制造死库存)⇒
        m6_line_member_excluded 分键;压库域收窄为非线内件。"""
        m = _members()[0]
        bench = [_bc(m, slot=1), _bc(m, slot=2, star=2)]
        bench += [_bc(n, star=2, slot=i + 3) for i, n in
                  enumerate([x for x in _members() if x != m])]
        st = _st(gold=60, level=4, shop_cards=[_card(m, 1)], bench=bench)
        sess = _shop_session(_comp())
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard), \
            'M6 不得买线内副本(死库存防守权归臂①)'
        assert state_of(sess).cw4_counters.get('m6_line_member_excluded', 0) >= 1


def shop_rejects(st, comp):
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
    from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
        line_members,
    )
    return shop.shop_unbought_reasons(st, comp, line_members(comp), [])


# ===== 检查点 3:达标即出战臂(W2 锁组,§9.6/C1)=====


def _mk_loop():
    from types import SimpleNamespace as _NS

    from sr_od.application.currency_war.operations import cw_loop

    class _Loop(cw_loop.CwLoop):
        def __init__(self):  # noqa: D107 桩:bypass SrOperation.__init__
            self.ctx = _NS(cw_match=_NS(session=None))
            self._cw_locked_sync_done = True   # 恢复局闩已置位形态
            self._cw_locked_sync_fails = 0

    return _Loop()


def _make_prep_loop_cls(overlay_anchor: tuple[str, str] | None = None,
                        ocr_hits: tuple[str, ...] = ()):
    """备战帧行为锁的环路桩类:仅备战双锚命中,其余画面判定全不命中;
    overlay_anchor 给定时该锚恒命中(浮层在场形态);ocr_hits = 恒命中的
    OCR 词(遭遇面板等 OCR 锚形态);「返回投资策略选择」
    OCR 命中 = 非达标帧在守卫计数后干净退出。"""
    from sr_od.application.currency_war.operations import cw_loop

    class _Hit:
        is_success = True

    class _Miss:
        is_success = False

    class _PrepLoop(cw_loop.CwLoop):
        _iter = 2
        _is_new_match = False
        _cw_locked_resume = False
        _cw_back_btn_count = 0
        _battle_ts = None

        def __init__(self):  # noqa: D107 桩:bypass SrOperation.__init__
            pass

        @property
        def last_screenshot(self):
            return self._screen

        @last_screenshot.setter
        def last_screenshot(self, v):
            pass

        def _stall_watch_tick(self, screen):
            pass

        def screenshot(self):
            return self._screen

        def round_by_find_area(self, screen, s1, s2, **kw):
            if s1 == '货币战争-备战' and s2 == '备战标识-购买经验':
                self._prep_seen = True   # 时序建模:浮层在 0 系清场后弹出
            if (s1 == '货币战争-备战'
                    and s2 in ('备战标识-购买经验', '按钮-出战')):
                return _Hit()
            if (overlay_anchor is not None and getattr(self, '_prep_seen', False)
                    and (s1, s2) == overlay_anchor):
                return _Hit()   # 浮层只对备战分支之后的探测可见(复现实机时序)
            return _Miss()

        def round_by_ocr_and_click(self, screen, target_cn=None, *a, **kw):
            if target_cn == '返回投资策略选择':
                return _Hit()
            return _Miss()

        def round_by_ocr(self, screen, target_cn=None, *a, **kw):
            # 前缀语义:ocr_hits = 画面上实际存在的完整词(如「遭遇其二」),
            # 探测词为其前缀(「遭遇其」)即命中(玩法文档 encounter.md:22)
            if ocr_hits and any(w.startswith(target_cn or '')
                                for w in ocr_hits):
                return _Hit()
            return _Miss()

        def round_by_find(self, *a, **kw):
            return _Miss()

        def round_by_find_and_click_area(self, *a, **kw):
            return _Miss()

        def round_wait(self, wait=1.0, status=''):
            return ('wait', status)

        def round_fail(self, *a, **kw):
            return ('fail',)

    return _PrepLoop


class TestReadinessBattleArm:

    def test_launch_fires_every_readiness_frame(self, monkeypatch):
        """锁②(C1 闩分域):达标臂发射**不读不置** _cw_locked_sync_done
        闩——同形态连续两次达标均完整发射(RunDeploy+StartBattle),
        不被「每锁定局恰一次」恢复局闩吞。"""
        import sr_od.application.currency_war.prep_actions as _pa
        from sr_od.application.currency_war.operations import cw_loop
        calls: list[str] = []

        class _FakeExecutor:
            def __init__(self, op, ctx):
                pass

            def execute(self, action):
                calls.append(type(action).__name__)
                return True, 'ok'

        monkeypatch.setattr(_pa, 'PrepActionExecutor', _FakeExecutor)
        op = _mk_loop()
        cw_loop.readiness_battle_launch(op, op.ctx)
        cw_loop.readiness_battle_launch(op, op.ctx)
        assert calls == ['RunDeploy', 'StartBattle'] * 2, calls
        assert op._cw_locked_sync_done is True   # 闩值不被达标臂触碰

    # 恢复局面面(sync_once=True)的闩置位/二次调用只 StartBattle 对照面
    # = test_cw_strategy_live_probe.py::test_locked_resume_sync_and_battle
    # (闩值+progressed 断言更全,跨文件择一,2026-09-08 瘦身批删除本侧
    # 等价副本 test_resume_face_still_latched)。

    def test_readiness_position_before_guard_chain(self, monkeypatch):
        """锁①③(行为面,落地审轮二:替代 getsource 半锁):达标帧
        (fp≥1.00)→ 达标臂发射(哨兵)且守卫计数零触达;非达标帧 →
        守卫链照常可达(零重排,§7.3 锚③;守卫规格零改动)。"""
        import pytest as _pt

        from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
        from sr_od.application.currency_war.operations import cw_loop

        class _ArmFired(Exception):
            pass
        state_calls = {'launch': 0, 'guard': 0}

        def _fake_launch(op, ctx):
            state_calls['launch'] += 1
            raise _ArmFired()

        def _fake_tick(prev, count, prev_actions, sig, actions):
            state_calls['guard'] += 1
            return (prev, count, prev_actions or frozenset())

        def _form_progress_probe(tc, st):
            # 诚实桩:校验 st 真是带 board 的对局态而非错绑模块(第十五局
            # 实测:模块级 state 名遮蔽曾致生产 AttributeError,行为锁
            # 常量桩未触 st 故漏;此桩防回归)
            if not hasattr(st, 'board'):
                raise AssertionError(
                    'form_progress 收到非对局态(疑似模块级 state 错绑)')
            return 1.0

        # 判据核单一源(两小批①):armed 判定经 kernel,patch 落 kernel 侧
        monkeypatch.setattr(
            'sr_od.application.currency_war.kernel.cw_comps.form_progress',
            _form_progress_probe)
        monkeypatch.setattr(cw_loop, 'readiness_battle_launch', _fake_launch)
        monkeypatch.setattr(cw_loop, 'prep_no_progress_tick', _fake_tick)
        # BOSS 简报 OCR 判别(分支 0p 无条件调 OCR)桩空 → False,免真 OCR
        monkeypatch.setattr(
            'sr_od.application.currency_war.operations.cw_screen.'
            'cw_screen_boss_briefing.read_ocr_texts',
            lambda ctx, screen: [])
        from types import SimpleNamespace as _NS

        def _mk_wired_op():
            """桩环构造统一走 _make_prep_loop_cls()(无 overlay/ocr_hits
            参与本测用不到;工厂与旧内联 _PrepLoop 逐行为等价,2026-09-08
            瘦身批去复制)。类属性已置 _iter/_cw_locked_resume 等初值。"""
            op = _make_prep_loop_cls()()
            op._screen = object()
            return op

        # 达标帧:达标臂发射(哨兵)且守卫计数零触达
        op = _mk_wired_op()
        sess = _NS(last_state=_st(gold=30, level=3))
        state_of(sess).cw4_counters = {}
        state_of(sess).target_comp = _comp()
        # last_prep_action_sig 迁 ExecState(session 职责分离批):经
        # exec_state_of 附着——裸 session 直挂 attr 已不被 cw_loop 读
        exec_state_of(sess).last_prep_action_sig = ('m2',)
        op.ctx = _NS(cw_match=_NS(session=sess))
        with _pt.raises(_ArmFired):
            op.loop()
        assert state_calls['launch'] == 1
        assert state_calls['guard'] == 0, '达标帧守卫计数零触达(锚③)'
        # 非达标帧:守卫链照常可达(零重排);判据核单一源,patch 落 kernel 侧
        monkeypatch.setattr(
            'sr_od.application.currency_war.kernel.cw_comps.form_progress',
            lambda tc, st: 0.5)
        state_calls.update(launch=0, guard=0)
        op2 = _mk_wired_op()
        op2.ctx = _NS(cw_match=_NS(session=_NS(
                last_state=_st(gold=30, level=3))))
        # 非达标帧的签名同迁 ExecState(经 exec_state_of 附着)
        exec_state_of(op2.ctx.cw_match.session).last_prep_action_sig = ('m2',)
        op2.loop()
        assert state_calls['guard'] == 1, '非达标帧守卫链照常可达'
        assert state_calls['launch'] == 0

    def test_readiness_launch_failure_falls_back_to_guard(self, monkeypatch):
        """C1 防线锁(P1消费臂批落地审):达标帧
        发射持续失败(连续 3 次)→ 放弃短路回落守卫链(守卫计数触达 +
        readiness_launch_giveup 分键);成功复位计数,复位后短窗口失败仍
        短路(窗口 = 连续失败,非累计)。"""
        import sr_od.application.currency_war.operations.cw_screen.cw_screen_boss_briefing as _bb
        from sr_od.application.currency_war.operations import cw_loop
        results = [(False, 'f1'), (False, 'f2'), (False, 'f3'),
                   (True, 'ok'), (False, 'f4'), (False, 'f5')]

        def _flaky_launch(op, ctx):
            ok, det = results.pop(0) if results else (True, 'ok')
            return ok, det

        guard = {'n': 0}

        def _fake_tick(prev, count, prev_actions, sig, actions):
            guard['n'] += 1
            return (prev, count, prev_actions or frozenset())
        from types import SimpleNamespace as _NS

        # 判据核单一源(sim 决策下沉两小批①):armed 判定经 kernel
        # readiness_launch_decision,force 成型须 patch kernel 侧
        # form_progress(cw_loop 已无内联判据可 patch)
        monkeypatch.setattr(
            'sr_od.application.currency_war.kernel.cw_comps.form_progress',
            lambda tc, st: 1.0)
        monkeypatch.setattr(cw_loop, 'readiness_battle_launch', _flaky_launch)
        monkeypatch.setattr(cw_loop, 'prep_no_progress_tick', _fake_tick)
        monkeypatch.setattr(_bb, 'read_ocr_texts', lambda ctx, screen: [])
        cls = _make_prep_loop_cls()
        op = cls()
        op._iter = 2
        op._is_new_match = False
        op._cw_locked_resume = False
        op._cw_back_btn_count = 0
        op._battle_ts = None
        op.last_screenshot = object()  # type: ignore[attr-defined]
        op._screen = object()
        comp = _comp()
        from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
        sess = _NS(last_state=_st(gold=30, level=3))
        state_of(sess).cw4_counters = {}
        state_of(sess).target_comp = comp
        # last_prep_action_sig 迁 ExecState(session 职责分离批):经
        # exec_state_of 附着——裸 session 直挂 attr 已不被 cw_loop 读
        exec_state_of(sess).last_prep_action_sig = ('m2',)
        op.ctx = _NS(cw_match=_NS(session=sess))
        for _ in range(3):   # 连续 3 次发射失败
            op.loop()
        assert state_of(sess).cw4_counters.get('readiness_launch_giveup', 0) == 1
        assert guard['n'] == 1, '第 3 次失败放弃短路,守卫链触达(防线 C1)'
        # 成功复位:随后的 2 次失败仍在窗口内,保持短路(不回落)
        for _ in range(2):
            op.loop()
        assert state_of(sess).cw4_counters.get('readiness_launch_giveup', 0) == 1
        assert guard['n'] == 1, '成功复位后短窗口失败保持短路'

    def test_readiness_holds_on_overlay_present(self, monkeypatch):
        """浮层在场排除锁(N5 后分层口径):投资策略浮层盖备战(双锚穿透
        形态)→ 0e 稳定路由分发接管(CwScreenInvestStrategy),达标臂零
        发射(盲射防);readiness_overlay_hold 分键兜 0e 双探测皆 miss 的
        残余窗口(防御分层:分发层路由 ↔ 消费点兜底,禁合并谓词)。"""
        from types import SimpleNamespace as _NS

        import sr_od.application.currency_war.operations.cw_screen.cw_screen_boss_briefing as _bb
        from sr_od.application.currency_war.operations import cw_loop
        launches: list[int] = []
        guard = {'n': 0}
        handler_executes: list[int] = []

        class _FakeInvest:
            def __init__(self, ctx):
                pass

            def execute(self):
                handler_executes.append(1)
                return None

        def _spy_launch(op, ctx):
            launches.append(1)
            return True, 'ok'

        def _fake_tick(prev, count, prev_actions, sig, actions):
            guard['n'] += 1
            return (prev, count, prev_actions or frozenset())

        # 判据核单一源(sim 决策下沉两小批①):armed 判定经 kernel
        # readiness_launch_decision,force 成型须 patch kernel 侧
        # form_progress(cw_loop 已无内联判据可 patch)
        monkeypatch.setattr(
            'sr_od.application.currency_war.kernel.cw_comps.form_progress',
            lambda tc, st: 1.0)
        monkeypatch.setattr(cw_loop, 'readiness_battle_launch', _spy_launch)
        monkeypatch.setattr(cw_loop, 'prep_no_progress_tick', _fake_tick)
        monkeypatch.setattr(cw_loop, 'CwScreenInvestStrategy', _FakeInvest)
        monkeypatch.setattr(_bb, 'read_ocr_texts', lambda ctx, screen: [])
        cls = _make_prep_loop_cls(
            overlay_anchor=('货币战争-投资策略', '标识-请选择投资策略'))
        op = cls()
        op._iter = 2
        op._is_new_match = False
        op._cw_locked_resume = False
        op._cw_back_btn_count = 0
        op._battle_ts = None
        op.last_screenshot = object()  # type: ignore[attr-defined]
        op._screen = object()
        comp = _comp()
        sess = _NS(                   last_state=_st(gold=30, level=3),
                   last_prep_action_sig=('m2',))
        state_of(sess).cw4_counters = {}
        state_of(sess).target_comp = comp
        op.ctx = _NS(cw_match=_NS(session=sess))
        op.loop()
        assert launches == [], '浮层在场帧达标臂不得发射(盲射防)'
        assert handler_executes, '浮层帧经 0e 稳定路由交投资策略接管面'
        assert guard['n'] == 0, 'N5 后浮层帧在 0e 分发层接管并提前返回(不过守卫链)'

    def test_readiness_holds_on_encounter_panel(self, monkeypatch):
        """遭遇面板排除锁(切屏竞态实测病例·遭遇面板形态):遭遇选择面板是备战屏上的
        面板(非独立屏),双锚穿透仍合法——OCR 词「遭遇其*」(其X 视遭遇
        池而定,前缀探测,currency_war_encounter.md:22)在场 ⇒ 达标臂
        不发射(readiness_overlay_hold 分键),交遭遇接管面。本锁用其二+
        其四两词覆盖「其X 不固定」形态。"""
        from types import SimpleNamespace as _NS

        import sr_od.application.currency_war.operations.cw_screen.cw_screen_boss_briefing as _bb
        from sr_od.application.currency_war.operations import cw_loop
        launches: list[int] = []
        guard = {'n': 0}

        def _spy_launch(op, ctx):
            launches.append(1)
            return True, 'ok'

        def _fake_tick(prev, count, prev_actions, sig, actions):
            guard['n'] += 1
            return (prev, count, prev_actions or frozenset())

        # 判据核单一源(sim 决策下沉两小批①):armed 判定经 kernel
        # readiness_launch_decision,force 成型须 patch kernel 侧
        # form_progress(cw_loop 已无内联判据可 patch)
        monkeypatch.setattr(
            'sr_od.application.currency_war.kernel.cw_comps.form_progress',
            lambda tc, st: 1.0)
        monkeypatch.setattr(cw_loop, 'readiness_battle_launch', _spy_launch)
        monkeypatch.setattr(cw_loop, 'prep_no_progress_tick', _fake_tick)
        monkeypatch.setattr(_bb, 'read_ocr_texts', lambda ctx, screen: [])
        cls = _make_prep_loop_cls(ocr_hits=('遭遇其二', '遭遇其四'))
        op = cls()
        op._iter = 2
        op._is_new_match = False
        op._cw_locked_resume = False
        op._cw_back_btn_count = 0
        op._battle_ts = None
        op.last_screenshot = object()  # type: ignore[attr-defined]
        op._screen = object()
        comp = _comp()
        from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
        sess = _NS(last_state=_st(gold=30, level=3))
        state_of(sess).cw4_counters = {}
        state_of(sess).target_comp = comp
        # last_prep_action_sig 迁 ExecState(session 职责分离批):经
        # exec_state_of 附着——裸 session 直挂 attr 已不被 cw_loop 读
        exec_state_of(sess).last_prep_action_sig = ('m2',)
        op.ctx = _NS(cw_match=_NS(session=sess))
        op.loop()
        assert launches == [], '遭遇面板在场帧达标臂不得发射(双锚穿透形态)'
        assert state_of(sess).cw4_counters.get('readiness_overlay_hold', 0) >= 1
        assert guard['n'] == 1, '面板帧交遭遇接管面,守卫链照常可达'

    def _stale_probe_loop(self, prep_visible: bool):
        """发射面新鲜屏态复验的桩环:prep_visible = 复验时备战屏锚是否
        命中(切屏后 = False)。"""
        base = _mk_loop()

        class _Hit:
            is_success = True

        class _Miss:
            is_success = False

        class _Probe(type(base)):
            def __init__(self):
                super().__init__()
                self.shots = 0

            def screenshot(self):
                self.shots += 1
                return object()

            def round_by_find_area(self, screen, s1, s2, **kw):
                ok = (prep_visible and s1 == '货币战争-备战'
                      and s2 in ('备战标识-购买经验', '按钮-出战'))
                return _Hit() if ok else _Miss()

        return _Probe()

    def test_stale_screen_aborts_launch_zero_drag(self, monkeypatch):
        """锁①(切屏竞态形态):执行时刻非备战屏(切屏后锚失)→ 放弃发射,
        readiness_stale_screen 分键 + **零 RunDeploy/StartBattle**(9 拖
        空挥不可再发)。"""
        from types import SimpleNamespace as _NS

        import sr_od.application.currency_war.prep_actions as _pa
        from sr_od.application.currency_war.operations import cw_loop
        calls: list[str] = []

        class _FakeExecutor:
            def __init__(self, op, ctx):
                pass

            def execute(self, action):
                calls.append(type(action).__name__)
                return True, 'ok'

        monkeypatch.setattr(_pa, 'PrepActionExecutor', _FakeExecutor)
        op = self._stale_probe_loop(prep_visible=False)
        sess = _NS(last_state=None)
        state_of(sess).cw4_counters = {}
        state_of(sess).target_comp = None
        op.ctx = _NS(cw_match=_NS(session=sess))
        ok, detail = cw_loop.readiness_battle_launch(op, op.ctx)
        assert ok is False and detail == 'readiness_stale_screen'
        assert calls == [], '切屏后发射请求必须零拖拽(placed=0 根修)'
        assert state_of(sess).cw4_counters.get('readiness_stale_screen', 0) == 1

    def test_prep_screen_present_launches_normally(self, monkeypatch):
        """锁②(对照):复验备战屏在 ⇒ 照常发射(RunDeploy+StartBattle),
        stale 分键不计数(锚命中形态零行为差)。"""
        from types import SimpleNamespace as _NS

        import sr_od.application.currency_war.prep_actions as _pa
        from sr_od.application.currency_war.operations import cw_loop
        calls: list[str] = []

        class _FakeExecutor:
            def __init__(self, op, ctx):
                pass

            def execute(self, action):
                calls.append(type(action).__name__)
                return True, 'ok'

        monkeypatch.setattr(_pa, 'PrepActionExecutor', _FakeExecutor)
        op = self._stale_probe_loop(prep_visible=True)
        sess = _NS(last_state=None)
        state_of(sess).cw4_counters = {}
        state_of(sess).target_comp = None
        op.ctx = _NS(cw_match=_NS(session=sess))
        ok, detail = cw_loop.readiness_battle_launch(op, op.ctx)
        assert ok is True and detail == 'ok'
        assert calls == ['RunDeploy', 'StartBattle']
        assert 'readiness_stale_screen' not in state_of(sess).cw4_counters


# ===== 检查点 3:G1 准入锁(§9.2 三元+victim 收口,发射面显影)=====


class TestG1ReadinessAdmission:

    def _admission(self, st, comp):
        from sr_od.application.currency_war.operations.cw_loop import (
            readiness_admission_report,
        )
        return readiness_admission_report(st, comp)

    def _g1_frames(self):
        """G1 帧构造(ADR-0590 决策8 口径:板满 = 占用部署数 ≥
        state.max_units(),与 swap 臂同裁决禁物理门;victim =
        off-line∧fenced∧非保护域)。full 帧 10 占用 ≥ 任意 level 驱动
        cap ⇒ 板满恒真(构造性,不依赖具体 level)。"""
        from sr_od.application.currency_war.kernel.cw_state import (
            DEPLOYED_CAPACITY,
        )
        comp = _comp()
        k = _members()
        hoard = sorted(cw_intention_hoard(comp))   # 保护域成员(非 victim)
        all_fac = set(comp.all_factions)
        victim = next(n for n, ch in _all_chars().items()
                      if n not in cw_intention_hoard(comp)
                      and not (set(ch.factions) | set(ch.flows)) & all_fac)
        full = [_bc(n, slot=i + 1) for i, n in
                enumerate(list(tuple(k) + tuple(hoard))[:DEPLOYED_CAPACITY])]
        with_victim = [_bc(n, slot=i + 1) for i, n in
                       enumerate(list(tuple(k) + (victim,)
                                 + tuple(hoard))[:DEPLOYED_CAPACITY])]
        return comp, k, victim, full, with_victim

    def test_admission_triple_shapes(self):
        """准入三元(ADR-0590 决策8 口径对齐:板满 = 占用数 vs
        max_units——旧物理槽位口径下 level 驱动 cap<10 ⇒ 分键结构性
        不显影,方案 v3.1 §2.2/§7 #11 顺手修;bench 待上 = 线内 ∨
        阵营交集;victim 无 1★ 全退门)。"""
        comp, k, victim, full, with_victim = self._g1_frames()
        st = _st(gold=30, level=3, deployed=full,
                 bench=[_bc('填充件X', slot=1)])
        rep = self._admission(st, comp)
        assert rep['board_full'] is True
        assert rep['bench_core_waiting'] is False
        assert rep['victim_missing'] is True
        st2 = _st(gold=30, level=3, deployed=with_victim, bench=[])
        rep2 = self._admission(st2, comp)
        assert rep2['board_full'] is True
        assert rep2['victim_missing'] is False, 'victim 在板不得误显影'
        # 未满板:三元①不成立(占用 4 < max_units(7)=7,占用数口径)
        st3 = _st(gold=30, level=7,
                  deployed=[_bc(n, slot=i + 1) for i, n in enumerate(k)],
                  bench=[])
        assert self._admission(st3, comp)['board_full'] is False

    def test_g1_launch_counts_victim_missing_and_still_fires(
            self, monkeypatch):
        """G1 行为锁:板满∧bench core∧victim 缺失形态 → deploy_swap_no_
        victim 分键显影 + 出战照发(准入只显影不拦截)。"""
        from types import SimpleNamespace as _NS

        import sr_od.application.currency_war.prep_actions as _pa
        from sr_od.application.currency_war.operations import cw_loop
        calls: list[str] = []

        class _FakeExecutor:
            def __init__(self, op, ctx):
                pass

            def execute(self, action):
                calls.append(type(action).__name__)
                return True, 'ok'

        monkeypatch.setattr(_pa, 'PrepActionExecutor', _FakeExecutor)
        comp, k, victim, full, with_victim = self._g1_frames()
        st = _st(gold=30, level=3, shop_cards=[], deployed=full,
                 bench=[_bc(k[3], slot=1)])   # bench 线内待上(三元②)
        sess = _NS(target_comp=comp, last_state=st)
        _gst = state_of(sess)
        _gst.cw4_counters = {}
        _gst.target_comp = comp
        op = _mk_loop()
        op.ctx = _NS(cw_match=_NS(session=sess))
        cw_loop.readiness_battle_launch(op, op.ctx)
        assert calls == ['RunDeploy', 'StartBattle'], calls
        assert state_of(sess).cw4_counters.get('deploy_swap_no_victim', 0) >= 1

    def test_g1_victim_present_no_counter(self, monkeypatch):
        """对照:存在合格 victim(off-line∧fenced∧非保护域,应-D:无
        1★ 全退门)⇒ deploy_swap_no_victim 不计数(分键只钉缺失形态)。"""
        from types import SimpleNamespace as _NS

        import sr_od.application.currency_war.prep_actions as _pa
        from sr_od.application.currency_war.operations import cw_loop
        comp = _comp()
        all_fac = set(comp.all_factions)
        victim = next(n for n, ch in _all_chars().items()
                      if n not in cw_intention_hoard(comp)
                      and not (set(ch.factions) | set(ch.flows)) & all_fac)
        _c2, _k2, victim, full, _wv = self._g1_frames()
        st = _st(gold=30, level=3, shop_cards=[],
                 deployed=full[:9] + [_bc(victim, slot=10)],
                 bench=[_bc('填充件X', slot=1)])
        sess = _NS(target_comp=comp, last_state=st)
        _gst = state_of(sess)
        _gst.cw4_counters = {}
        _gst.target_comp = comp
        op = _mk_loop()
        op.ctx = _NS(cw_match=_NS(session=sess))

        class _FakeExecutor:
            def __init__(self, op, ctx):
                pass

            def execute(self, action):
                return True, 'ok'

        monkeypatch.setattr(_pa, 'PrepActionExecutor', _FakeExecutor)
        cw_loop.readiness_battle_launch(op, op.ctx)
        assert 'deploy_swap_no_victim' not in state_of(sess).cw4_counters


# ===== 辅助 =====


def cw_intention_hoard(comp) -> set[str]:
    from sr_od.application.currency_war.kernel import cw_intention
    chars, _eq = cw_intention._line_hoard(comp)
    return chars


def _all_chars() -> dict:
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    return CHARACTERS
