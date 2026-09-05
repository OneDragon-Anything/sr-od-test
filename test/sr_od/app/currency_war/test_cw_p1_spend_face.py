"""14号稿 P1 消费臂落码批·检查点 1 锁组(§7.2)。

设计出处 = docs/develop/currency_war/strategy-docs/14_p1_consume_arms.md
(v4.2.2)§3(臂①囤腿)/§4(arm0 升级授权回补)/§7.1/§7.2。覆盖:
- 臂① m2_stockpile:j=1 发射(M2 后、M2b 前)/ j=2 帧不判(M2b 独占)/
  cnt2>0 帧路径排除(N2:臂①不制造死库存)/ star_mismatch_skip 分键
  (W4)/ bench 满先 M4 腾席(Y5)/ stockpile_unaffordable;
- M2b:候选 star==1 过滤(Y4)+ 席位门满栏例外(§3.6,合成触发帧免
  bench_free 门,理由键不变);
- arm0 v2:need (名,星) 现量口径(Y3)/ level_readable 消费端 fail 向
  (C4/W6)/ pop_slot 前置放宽(§4.3)。

锁契约:docstring 引本篇章节为设计出处;不锁分布数值(测试纪律第 8 条)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    LevelUpShop,
    SellBench,
    ShopCard,
    simulate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    arm0_level_lag,
    arm0_need,
)

_LOCK_COMP = '列车同行'


def _cfg():
    return SimpleNamespace(ev_arm='full')


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _card(name: str, cost: int = 3, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _comp():
    return get_comp(_LOCK_COMP)


def _members() -> list[str]:
    comp = _comp()
    return list(dict.fromkeys(
        list(comp.core_chars) + list(getattr(comp, 'shared_chars', []) or [])))


def _shop_session(comp) -> SimpleNamespace:
    s = SimpleNamespace(cw4_counters={}, target_comp=comp)
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
        经臂①义务买入(reason='m2_stockpile',不走息律门);j=0 帧仍由
        M2 主通道承载(发射序覆盖链 M2→臂①→M2b)。"""
        m = _members()[0]
        st = _st(gold=30, shop_cards=[_card(m, 3)],
                 bench=[_bc(m, slot=1)])
        sess = _shop_session(_comp())
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'm2_stockpile'
        # j=0 对照:未持有时仍走 M2 主通道(覆盖链不缺口)
        st0 = _st(gold=30, shop_cards=[_card(m, 3)])
        sess0 = _shop_session(_comp())
        act0 = _decide(st0, sess0)
        assert isinstance(act0, BuyCard) and act0.reason == 'm2_line_member'

    def test_j2_frame_not_judged_by_arm1(self):
        """j=2 帧(同名同星 1★ ×2 ∧ 无 2★):臂①不判不发,M2b 独占完成段
        (发射序覆盖链互斥,A1 三处矛盾消除)。"""
        m = _members()[0]
        st = _st(gold=30, shop_cards=[_card(m, 3)],
                 bench=[_bc(m, slot=1), _bc(m, slot=2)])
        sess = _shop_session(_comp())
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'm2_merge_completion'

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
        assert sess.cw4_counters.get('m2_stockpile_star_mismatch', 0) >= 1
        assert 'm2b_star_mismatch' not in sess.cw4_counters

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
        assert sess.cw4_counters.get('bench_full', 0) >= 1
        assert 'merge_bench_full' not in sess.cw4_counters

    def test_unaffordable_counted(self):
        """金不足 ⇒ stockpile_unaffordable 分键(义务面拒因零静默)。"""
        m = _members()[0]
        st = _st(gold=1, shop_cards=[_card(m, 3)], bench=[_bc(m, slot=1)])
        sess = _shop_session(_comp())
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        assert sess.cw4_counters.get('stockpile_unaffordable', 0) >= 1


# ===== M2b:Y4 星过滤 + §3.6 满栏例外 =====


class TestM2bSeatGateAndStarFilter:

    def test_merge_buy_at_full_bench(self):
        """§3.6 满栏例外:同名同星 1★ ×2 ∧ 第三张 1★ 在店 ⇒ 满栏也买
        (买入即合成,机制对齐);理由键 'm2_merge_completion' 不变。
        (隔离:M2 主/M4 先行臂以「全 owned 帧灭 missing」排除——填充件
        2★ 非 1★ 燃料、非 k 成员,不构成缺员也不入燃料集。)"""
        m = _members()[0]
        fill = [_bc(f'填充件{i}', slot=i + 1, star=2) for i in range(1, 8)]
        bench = [_bc(m, slot=8), _bc(m, slot=9)] + fill
        st = _st(gold=30, shop_cards=[_card(m, 3)], bench=bench)
        sess = _shop_session(_comp())
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'm2_merge_completion'

    def test_merge_star_filter_only_2star_card(self):
        """Y4:完成段(cnt=2∧无2★)但店内仅 2★ 直出卡 ⇒ 不买
        (+m2b_star_mismatch 分键,与臂①同型过滤三消费面记全,低-1)。"""
        m = _members()[0]
        bench = [_bc(m, slot=1), _bc(m, slot=2)]
        st = _st(gold=30, shop_cards=[_card(m, 3, star=2)], bench=bench)
        sess = _shop_session(_comp())
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        assert sess.cw4_counters.get('m2b_star_mismatch', 0) >= 1
        assert 'm2_stockpile_star_mismatch' not in sess.cw4_counters


# ===== arm0 v2(§4.2 Y3/C4/W6)=====


class TestArm0LevelLag:

    def test_need_name_star_semantics(self):
        """Y3:need 排除谓词按 (名,星)——同名异星 bench 件计入 need,
        同名同星 deployed 件排除。"""
        k = ('甲', '乙', '甲2星名')
        deployed = [_bc('甲', star=1, slot=1)]
        bench = [_bc('甲', star=2, slot=1),   # 同名异星:计入 need
                 _bc('甲', star=1, slot=2),   # 同名同星:排除
                 _bc('丙', slot=3)]           # 非 k:不计
        need = arm0_need(deployed, bench, k)
        assert need == 1 + 1, 'deployed 1 + bench(甲2★) 1'

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
        sess.cw4_counters = {}
        out = mandate.run_mandate(frame, sess, state=state)
        assert any(e.reason.startswith('m3_levelup_batch') for e in out), \
            'arm0 触发须经 M3 判据链发射批经验授权'
        # C4/W6:不可信帧 fail 向
        state.level_readable = False
        sess2 = StrategySession()
        sess2.cw4_counters = {}
        out2 = mandate.run_mandate(frame, sess2, state=state)
        assert not any(e.reason.startswith('m3_levelup_batch')
                       for e in out2)
        assert sess2.cw4_counters.get('arm0_level_unreadable', 0) >= 1


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
        ok2, why2 = pop_slot(5, 5, 60, 0, 0)   # 无任何候选:显式理由
        assert ok2 is False and why2 == 'no_bench_candidate'
        # 买不起(金低于地板 floor_gold)仍拒
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
        """落地审应-A:P2 帧 hp≤15 不得开 P1 解锁包(授权族 = P1 血线
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
        sess.cw4_counters = {}
        out = mandate.run_mandate(frame, sess, state=state)
        assert any(e.reason.startswith('m3_levelup_batch') for e in out)


class TestF1LedgerBuyMembersAlignment:

    def test_r1_ledger_uses_buy_members_single_source(self):
        """F1 口径对齐(§6.2 输入②):R1 合格集/Σ卡费单源 = buy_members
        ——锁定帧全 core∪shared 已 2★ 成型而 hoard 其余成员可追时,
        k_members 口径给 inf(旧口径=刷新恒闭)而 buy_members 口径给
        有限账(臂①落地后「买满三张」费用口径与行为一致)。"""
        comp = _comp()
        hoard = cw_intention_hoard(comp)
        core = _members()
        # 全 core∪shared 2★ 成型(出 k 口径合格集)
        bench = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(core)]
        level = 7   # 该级 cost-3 档可追(低位面全不可追会使两口径同为 inf)
        e_k, _ = shop_ledger_terms(core, bench, [], level)
        assert e_k == float('inf'), '锁前提:core∪shared 口径合格集空'
        e_b, fees_b = shop_ledger_terms(tuple(sorted(hoard)), bench, [],
                                        level)
        assert e_b != float('inf'), 'buy_members 口径:hoard 其余成员可追'
        assert fees_b > 0, 'Σ卡费 =(3−j)×cost 完成档口径随对齐生效'

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
        assert sess.cw4_counters.get('shop_r1_no_chaseable_member', 0) >= 1
        assert sess.cw4_counters.get('r1_idle_gold_no_chaseable', 0) >= 1


def shop_ledger_terms(buy_members, bench, deployed, level):
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
    return shop._r1_ledger_terms(buy_members, bench, deployed, level)


# ===== 落地审阻-1/应-2:商店栈 M3 三臂并联(arm1/arm0/pop_slot)=====


class TestShopM3TripleArm:

    def _decide_sess(self, comp):
        from sr_od.application.currency_war.strategies.impl.cw_strategy import (
            StrategySession,
        )
        s = StrategySession()
        s.cw4_counters = {}
        s.target_comp = comp
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
            'auth_basis 三臂分键(可归因,落地审三低项)'

    def test_mandate_pop_slot_wired(self, monkeypatch):
        """应-B:mandate 备战栈 M3 接入 pop_slot(满编+富金+bench 有线内
        候补 = 备战帧触发域;备战帧店面不可读 ⇒ buyable 腿只在商店栈,
        双栈分域声明);否向理由留决策迹(session.cw4_pop_slot_why)。"""
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
        sess.cw4_counters = {}
        out = mandate.run_mandate(frame, sess, state=state)
        assert calls, 'mandate 栈 pop_slot 必须被消费(阻-1 同型,禁假活)'
        args, kwargs = calls[0]
        assert len(args) == 5 and not kwargs.get('buyable_candidate'), \
            '备战帧店面不可读:buyable 腿不传/恒 False(分域)'
        assert any(e.reason.startswith('m3_levelup_batch') for e in out)
        assert hasattr(sess, 'cw4_pop_slot_why')


# ===== 落地审应-1:拒因串与同帧实际动作一致 =====


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


def shop_rejects(st, comp):
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
    from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
        line_members,
    )
    return shop.shop_unbought_reasons(st, comp, line_members(comp), [])


# ===== 辅助 =====


def cw_intention_hoard(comp) -> set[str]:
    from sr_od.application.currency_war.kernel import cw_intention
    chars, _eq = cw_intention._line_hoard(comp)
    return chars


def _all_chars() -> dict:
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    return CHARACTERS
