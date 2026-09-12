"""P86 无目标期三臂判据单帧锁(T-177 落码批)。

出处(单一源):
- 命题正本 = docs/develop/sr_od/application/currency_war/proofs/p86-no-target-period-fund-allocation.md
  (§2 三臂形态/§4.2 四面退役表/§4.4 旧锁清单与重推义务/§5.2 单帧锁清单);
- 证明批 = docs/develop/sr_od/application/currency_war/proofs/p86-proof-batch.md
  (§3 定理 A/B1-B5/C/M;§4 必答六件终裁;§6 落码批增量条款九件)。

锁编号对齐:正本 §5.2 锁 1-7 + 证明批 §6 增量 1-9,逐测试 docstring 引出处。
构帧口径:GameState 缺省 hp=0 ⇒ ``p2_supply_horizon``=0 ⇒ 全线 G=0(机器
判死形态的自然构帧);甲臂判活帧显式给 hp 并授满某线全部核心(G=1.0)。
判读注册表事实(cov/声明序)一律运行时直调派生,不写死清单。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_intention
from sr_od.application.currency_war.kernel.cw_board_state import (
    board_state_bridge as _kbridge,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    CORE_SINGLE_CARD_REGISTRY,
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    _p1_transition_eligible,
    arm_a_live_direction,
    char_declaration_index,
    hoard_target_set,
    hub_covered_lines,
    hub_option_names,
    k_empty_window_fallback,
    line_completion_feasibility,
    no_target_arms,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import mandate, shop
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.vopt import (
    refund_full_star_ok,
)

# ===== 基建 =====


def _cfg():
    return SimpleNamespace(ev_arm='full')


def _session(ist: IntentionState | None = None) -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = None
    if ist is not None:
        state_of(s).v3_intention = ist
    return s


def _state(gold: int = 45, level: int = 5, hp: int = 60,
           shop_cards: list[ShopCard] | None = None,
           bench: list[BenchChar] | None = None,
           deployed: list[BenchChar] | None = None,
           round_num: int = 2) -> GameState:
    st = GameState(gold=gold, level=level, round_num=round_num, hp=hp)
    st.plane = 2
    st.shop = shop_cards if shop_cards is not None else []
    st.bench = bench if bench is not None else []
    st.deployed = deployed if deployed is not None else []
    return st


def _card(name: str, cost: int = 3, star: int = 1, x: int = 100) -> ShopCard:
    return ShopCard(x=x, name=name, cost=cost, star=star)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _decide(st: GameState, sess: StrategySession):
    return shop.decide_shop_action(st, sess, _cfg())


def _ct(sess: StrategySession) -> dict:
    return state_of(sess).cw4_counters or {}


def _own(*names: str) -> list[BenchChar]:
    return [_bc(n, slot=i + 1) for i, n in enumerate(names)]


# ===== 正本 §5.2 锁 1/2:甲臂强锁门逐字 + 判死出辖 =====


class TestArmAStrongGate:

    def test_strong_gate_same_source_and_machine_order(self):
        """锁 2(正本 §5.2)+ F11 测试化:同帧同输入下,甲臂方向 =
        独立重算强锁候选集(同一谓词 line_completion_feasibility + 同一常量
        revoke_miss_tolerance_eps + 同一 plane 条件 + 同一机器选择序)的
        首方向;promote_candidates 禁入调用链(静态负检 =
        TestHubEligibility.test_eligibility_input_face_static 的
        arm_a_live_direction 扫描支,F-4 指针修正后落位)。"""
        comp = get_comp('希儿量子')
        st = _state(hp=100)
        st.bench = _own(*comp.core_chars)
        ist = IntentionState()
        assert arm_a_live_direction(_kbridge(st), ist) == '希儿量子'
        # 独立重算(锁 2 的同源对拍;与意向层移交候选同一谓词链)
        vis = cw_intention._visible_chars(_kbridge(st))
        reg = DEFAULT_REGISTRY
        cands = [c for c in cw_intention._v2_comps()
                 if c.name not in ist.evicted
                 and st.plane not in (c.weak_planes or ())
                 and cw_intention._core_reachable(c, _kbridge(st), vis)
                 and (st.plane != 2
                      or line_completion_feasibility(_kbridge(st), c, None, reg, vis)
                      > reg.revoke_miss_tolerance_eps)]
        best = sorted(cands,
                      key=lambda c: (-cw_intention._asset_thickness(c, _kbridge(st)),
                                     cw_intention.encounter_window_rounds(
                                         cw_intention.intention_core(c),
                                         st.level)))[0]
        assert best.name == '希儿量子'
        kfb, tok = k_empty_window_fallback(_kbridge(st), ist)
        assert tok == 'p2plus'
        chars, _eq = cw_intention._line_hoard(comp)
        assert kfb == frozenset(chars)

    def test_dead_direction_g0_no_hoard(self):
        """锁 1(正本 §5.2)G=0 档:判死形态帧(构帧口径:hp 缺省 0 ⇒
        视界零 ⇒ 全线 G=0,绯英 G=0.0000 是其注册表实例)不发射该方向
        囤货——回退成员集为空(fallback_hold),非绯英采购集。"""
        st = _state()
        ist = IntentionState()
        arms = no_target_arms(_kbridge(st), ist)
        assert arms.direction == ''
        assert arms.char_targets == frozenset()
        ht = hoard_target_set(_kbridge(st), ist)
        assert ht.mode == 'fallback_hold' and not ht.char_targets
        kfb, tok = k_empty_window_fallback(_kbridge(st), ist)
        assert kfb == frozenset() and tok == 'p2plus'

    def test_dead_direction_partial_g_no_hoard(self):
        """锁 1(正本 §5.2)0<G≤ε 档(防 F1 修复回退):部分完成但
        机器判死的线不获囤货授权。构帧 = 授满绯英欢愉除瓦尔特(5 费)外
        全部核心,lv7/hp15 ⇒ G=q(瓦尔特)∈(0,ε](运行时核域,不写死值)。"""
        reg = DEFAULT_REGISTRY
        st = _state(hp=15, level=7)
        cores = [m for m in get_comp('绯英欢愉').core_chars if m != '瓦尔特']
        st.bench = _own(*cores)
        ist = IntentionState()
        g = line_completion_feasibility(_kbridge(st), get_comp('绯英欢愉'), None, reg,
                                        None)
        assert 0 < g <= reg.revoke_miss_tolerance_eps
        assert arm_a_live_direction(_kbridge(st), ist) == ''

    def test_p1_bands_and_weak_out_of_scope(self):
        """必答⑥出辖(证明批 §4.1 裁决:p1 两带显式出辖)+ 域守卫
        (引理 Z/正本 §6.2-4):plane=1 与 weak/demoted 帧三臂全空甲乙,
        p1 带回退维持既有判据族(四体系全集/体系对)——退役面收窄。"""
        st1 = _state(hp=100)
        st1.plane = 1
        ist1 = IntentionState()
        assert no_target_arms(_kbridge(st1), ist1).direction == ''
        assert no_target_arms(_kbridge(st1), ist1).hub_names == ()
        # p1_gap 带回退 = 四体系引擎件全集(既有判据族,不入三臂)
        kfb, tok = k_empty_window_fallback(_kbridge(st1), ist1)
        assert tok == 'p1_gap' and kfb
        stw = _state()
        istw = IntentionState()
        istw.phase = 'weak'
        assert no_target_arms(_kbridge(stw), istw) == cw_intention.NoTargetArms(
            '', frozenset())
        assert hoard_target_set(_kbridge(stw), istw).mode == 'weak'   # 跨线骨架分带

    def test_locked_frame_three_arms_dormant(self):
        """锁 5(正本 §5.2):locked_buy_membership 非 None 帧本命题三臂
        全部不发射——no_target_arms 出域返回空甲乙;店面枢纽件不落
        hub_option_buy 买因(锁线态由 M2/C1 既有通道辖)。"""
        ist = IntentionState()
        ist.phase = 'locked'
        ist.locked_comp = '希儿量子'
        st = _state(shop_cards=[_card('花火', cost=2)])
        assert no_target_arms(_kbridge(st), ist).hub_names == ()
        sess = _session(ist)
        state_of(sess).target_comp = get_comp('希儿量子')
        act = _decide(st, sess)
        assert not [a for a in ([act] if act else [])
                    if isinstance(a, BuyCard) and a.reason == 'hub_option_buy']
        assert 'hub_option_buy_hit' not in _ct(sess)


# ===== 证明批 §6 增量 2/3 + 定理 B5:乙臂资格核 =====


class TestHubEligibility:

    def test_eligibility_input_face_static(self):
        """增量 2(证明批 §6;定理 B2 实现守卫):乙臂资格核源码扫描——
        输入面只含 (COMP_LIBRARY, evicted, weak_planes,
        CORE_SINGLE_CARD_REGISTRY);G/_core_reachable/p2_supply_horizon/
        promote_candidates 出现即红。扫描 = AST 标识符级(docstring/注释
        的「禁入」声明不构成消费,不误伤);变异自检 = 同一扫描器对甲臂
        函数命中合法 banned 符号(防恒绿)。"""
        import ast
        src = Path(cw_intention.__file__).read_text(encoding='utf-8')
        tree = ast.parse(src)

        def identifiers_of(fn_name: str) -> set[str]:
            node = next(n for n in tree.body
                        if isinstance(n, ast.FunctionDef) and n.name == fn_name)
            return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}

        for fn in ('hub_option_names', 'structural_candidate_lines',
                   'hub_covered_lines'):
            ids = identifiers_of(fn)
            for banned in ('line_completion_feasibility', '_core_reachable',
                           'p2_supply_horizon', 'promote_candidates',
                           'e_rounds'):
                assert banned not in ids, \
                    f'{fn} 输入面混入 {banned}(定理 B2 解耦被破坏)'
        # 变异自检:同一扫描器对甲臂函数命中 banned 符号(扫描器有效)
        assert 'line_completion_feasibility' in identifiers_of(
            'arm_a_live_direction')
        # F-4(F11 落位):甲臂禁消费 promote_candidates(G8 观测载体,
        # 码内明文禁入任何行为消费点)——同扫描器负检。
        assert 'promote_candidates' not in identifiers_of(
            'arm_a_live_direction')

    def test_yinlang_counter_example_and_dual_channel_mutex(self):
        """增量 3(证明批 §6;定理 B5 测试化):银狼LV.999 覆盖数 = 2 而系
        注册单卡依赖核心 ⇒ 乙臂不发射、规则③通道发射,双通道互斥。"""
        st = _state(shop_cards=[_card('银狼LV.999', cost=5)])
        ist = IntentionState()
        assert len(hub_covered_lines(_kbridge(st), ist, '银狼LV.999')) == 2
        assert '银狼LV.999' in CORE_SINGLE_CARD_REGISTRY
        assert '银狼LV.999' not in hub_option_names(_kbridge(st), ist)
        sess = _session(ist)
        act = _decide(st, sess)
        assert isinstance(act, BuyCard)
        assert act.reason == 'core_single_card_buy:unlocked'
        ct = _ct(sess)
        assert ct.get('core_unlocked_buy_hit') == 1
        assert 'hub_option_buy_hit' not in ct

    def test_coverage_boundary_and_hubs_present(self):
        """定理 B5 计数边界:覆盖数 = 1(希儿)不入枢纽档;覆盖数 ≥ 2
        (花火,注册表全库直调)入档;资格核非空 = 病灶帧条件非空
        (定理 B2-2 的运行时核)。"""
        st = _state()
        ist = IntentionState()
        assert len(hub_covered_lines(_kbridge(st), ist, '希儿')) == 1
        assert '希儿' not in hub_option_names(_kbridge(st), ist)
        assert len(hub_covered_lines(_kbridge(st), ist, '花火')) >= 2
        hubs = hub_option_names(_kbridge(st), ist)
        assert '花火' in hubs and hubs


# ===== 正本 §5.2 锁 3/8 + §4.4 行 3:乙臂发射与拒因归真 =====


class TestHubEmission:

    def test_hub_fires_on_arm_dead_frame(self):
        """锁 3(正本 §5.2)F2 测试化:甲臂空集帧乙臂**照常评估**并发射
        (病灶帧正是 D3 要接枢纽期权的帧,出手机会不可丢);发射 = 五前件
        合取全过(资格核花火 + 非合并素材 + 1★ 全退 + 席 + 息 + 金)。"""
        st = _state(shop_cards=[_card('花火', cost=2)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'hub_option_buy'
        ct = _ct(sess)
        assert ct.get('hub_option_buy_hit') == 1
        assert ct.get('hub_option_candidate_seen') == 1
        assert ct.get('shop_no_target_arm_a_dead_defer') == 1

    def test_reject_family_truthful(self):
        """锁 3 拒因归真:任一合取项缺席帧按缺席项分键,非静默。
        素材(场内已有同名同星 1★,bench 与部署面两形态)/席位/息/金
        四门逐帧判(证明批 §3.2 五前件合取 + §6 增量 8)。"""
        # 非合并素材:副本在 bench
        st = _state(shop_cards=[_card('花火', cost=2)],
                    bench=[_bc('花火', slot=1)])
        ct = _ct(_session(IntentionState()))
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        assert _ct(sess).get('hub_option_reject_merge_material') == 1
        # 非合并素材:副本在部署面(复核观察变体:核对面 = bench∪deployed
        # 全场域,same_star_count 单一源计数)
        st2 = _state(shop_cards=[_card('花火', cost=2)],
                     deployed=[_bc('花火', star=1, slot=1)])
        sess2 = _session(IntentionState())
        act2 = _decide(st2, sess2)
        assert not isinstance(act2, BuyCard)
        assert _ct(sess2).get('hub_option_reject_merge_material') == 1
        # 席位:bench 满
        st3 = _state(shop_cards=[_card('花火', cost=2)],
                     bench=[_bc(f'注册表外散件{i}', slot=i + 1)
                            for i in range(BENCH_CAPACITY)])
        sess3 = _session(IntentionState())
        act3 = _decide(st3, sess3)
        assert not isinstance(act3, BuyCard)
        assert _ct(sess3).get('hub_option_reject_seats') == 1
        # 息:50 买 2 跨息档 ⇒ L>0 拒(C1 通道同口径金币构帧,P47 现算)
        st4 = _state(gold=50, shop_cards=[_card('花火', cost=2)])
        sess4 = _session(IntentionState())
        act4 = _decide(st4, sess4)
        assert not isinstance(act4, BuyCard)
        assert _ct(sess4).get('hub_option_reject_interest') == 1
        # 金:不足帧的拒因按规范门序(席→息→金)取首败项——帧输入
        #(r_remaining=17 的息轨迹)下 poor 帧 L>0 先真,unaffordable 被
        # t5 结构性前遮;此处锁「门序首败项归真」语义本身,affordable
        # 闸独立显影面 = 消费同一单一源 mandate.check_affordable 的
        # C1/M2 通道既有锁。
        st5 = _state(gold=1, shop_cards=[_card('花火', cost=2)])
        sess5 = _session(IntentionState())
        act5 = _decide(st5, sess5)
        assert not isinstance(act5, BuyCard)
        assert _ct(sess5).get('hub_option_reject_interest') == 1
        assert _ct(sess5).get('hub_option_reject_unaffordable') is None

    def test_merge_frozen_state_telemetry_discernible(self):
        """F-5(落地审;增量 8 后半,B4 闭集 3/P75 (vi) 同款):已持枢纽帧
        外部通道到达同名副本后合并冻结态可辨——素材对在场 = 滞留显影键
        载体(merge_material_stale_names 单一源),2★ 吞升后 1★ 净 0 出口
        消失(refund_full_star_ok(2,·)=False 事实面),乙臂对该名不再发射
        (场内副本 ≥1 即拒)。"""
        st = _state(shop_cards=[_card('花火', cost=2)],
                    bench=[_bc('花火', slot=1), _bc('花火', slot=2)])
        # 合并冻结态显影:同名同 1★ 对在场 = 滞留素材(判定单一源直核)
        from sr_od.application.currency_war.kernel.cw_state import (
            merge_material_stale_names,
        )
        assert merge_material_stale_names(st.bench, st.deployed) == ('花火',)
        assert not refund_full_star_ok(2, 2)   # 2★ 出口面(吞升后资格消失)
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        assert _ct(sess).get('hub_option_reject_merge_material') == 1

    def test_hub_hold_registration_and_sell_protection(self):
        """攻击 r1 发现1(高)三面收口锁:TRANSITION_PACK 之外枢纽
        (瓦尔特,cw_line_facts:75-76 移出记录实证)——面① hold 登记资格
        域 = 静态持有集 ∪ 乙臂获取名集(发射位先登记后 emit,当笔在场):
        买入后 launch_cause_mismatch 零污染 + 登记簿落 (hold, 轮);
        面② 装配 A 身份段并集:获取名 ∈ sell_exclusions(凑息/腾席/筹资
        资格排除),1★ 期权不再被己方卖面跨轮卖掉;面③ 部署域读端 =
        鸭子读同一载体(静态扫描锁见下)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            sell_gate,
        )
        st = _state(shop_cards=[_card('瓦尔特', cost=4)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'hub_option_buy'
        ct = _ct(sess)
        # 面①:登记资格域并入获取名集,病灶信号键零污染 + 簿落账
        assert 'launch_cause_mismatch' not in ct
        book = getattr(state_of(sess), sell_gate.LAUNCH_REGISTRY_ATTR, {})
        assert book.get('瓦尔特') == ('hold', 2)
        # 面②:装配 A 身份段并集(下一备战帧 round 推进,L1 同轮硬面过期
        # ——fresh_buys 只保当轮,攻击报告「跨轮自动失效」形态;非并集时
        # 该名落回凑息/腾席燃料资格 = 期权被己方卖面销毁)
        st_next = _state(round_num=3)
        sess.shop_state_frame = st_next
        excl_next = sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=3)
        assert '瓦尔特' in excl_next
        fuel = mandate.fuel_sell_candidates(
            [_bc('瓦尔特', slot=1)], (), state=st_next,
            exclude_names=excl_next)
        assert not fuel
        # 面③:读口单一源(登记域/身份段/部署域三面同源)
        assert '瓦尔特' in sell_gate.hub_acquired_names_of(sess)

    def test_deploy_domain_hub_read_static(self):
        """攻击 r1 发现1 面③部署域消费接线锁:静态扫描 cw_op_deploy 的
        deployed_from_hub 读端与载体属性名(鸭子读属性契约,同
        cw4_fuel_filler_stall_buys 先例)。带变异自检。"""
        import sr_od.application.currency_war.operations.cw_op.cw_op_deploy as _dep
        src = Path(_dep.__file__).read_text(encoding='utf-8')
        assert 'deployed_from_hub' in src
        assert "'cw4_hub_acquired_names'" in src
        # 变异自检:扫描器对注入形态能命中
        assert 'deployed_from_hub' in "counters['deployed_from_hub'] = 1"

    def test_hub_hold_registration_negative_stale_semantics(self):
        """面①②负锁:获取名集之外的名不获资格域扩张——非持有名 hold
        登记仍拒(launch_cause_mismatch 病灶信号语义不被乙臂面稀释)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            sell_gate,
        )
        sess = _session(IntentionState())
        ok = sell_gate.register_launch(
            sess, '注册表外散件Q', cause='hold', round_num=3,
            star=1, cost=1)
        assert not ok
        assert _ct(sess).get('launch_cause_mismatch') == 1

    def test_star2_hub_card_not_enumerated(self):
        """锁 8 前件(§3.2 合取:refund_full_star_ok 仅 1★):2★ 枢纽直出卡
        不入候选枚举(2★ 退金 3c−1 ≠ 净 0,定理 B4 闭集 3 的事实面)。"""
        assert not refund_full_star_ok(2, 2)
        st = _state(shop_cards=[_card('花火', cost=2, star=2)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        assert 'hub_option_candidate_seen' not in _ct(sess)

    def test_hub_reject_reason_key_not_non_line(self):
        """§4.4 行 3(non_line 拒因锁重推):空窗帧枢纽资格件在售未买帧
        拒因 = hub_option(显式),不再落 non_line。"""
        st = _state(gold=1, shop_cards=[_card('花火', cost=2),
                                        _card('注册表外散件Z', cost=1)])
        sess = _session(IntentionState())
        _decide(st, sess)
        rejects = getattr(state_of(sess), 'cw4_shop_rejects', {})
        assert rejects.get('花火') == 'hub_option'
        assert rejects.get('注册表外散件Z') == 'non_line'


# ===== 证明批 §4.4 + §6 增量 1:同帧仲裁三层序 =====


class TestArbitration:

    def _arm_live_frame(self, shop_cards, gold: int = 45,
                        comp_name: str = '希儿量子'):
        """甲臂判活帧:授满该线全部核心 ⇒ 机器选择序首方向(运行时断言,
        不写死);甲臂成员集含缺员件供 M2 竞争。"""
        comp = get_comp(comp_name)
        st = _state(gold=gold, hp=100, shop_cards=shop_cards)
        st.bench = _own(*comp.core_chars)
        assert arm_a_live_direction(_kbridge(st), IntentionState()) == comp_name
        return st

    def test_layer1_covering_hub_beats_single_line_piece(self, monkeypatch):
        """增量 1(证明批 §6;§4.4 第一层支配序,推论 B1.1):同帧同店面给
        甲方向的单线方向件(布洛妮娅,C_x={希儿量子} 运行时直调核)与覆盖
        其线的枢纽件(知更鸟),资源两件都足 ⇒ 发射枢纽。判据力:变异夹具
        把件声明序钉到枢纽之前(自然序 20<21 两序同向不判)——层序失效
        降第三层时件将首发 → 本测红。"""
        st = self._arm_live_frame([_card('知更鸟', cost=4),
                                   _card('布洛妮娅', cost=2)])
        monkeypatch.setattr(
            cw_intention, 'char_declaration_index',
            lambda n: 0 if n == '布洛妮娅' else 99 if n == '知更鸟'
            else char_declaration_index(n))
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'hub_option_buy'
        assert act.card.name == '知更鸟'
        assert _ct(sess).get('hub_option_arbitration_yield') is None

    def test_layer3_multi_line_piece_first_by_decl_order(self, monkeypatch):
        """增量 1 第三层:多线方向件对枢纽竞争按注册表声明序首发。
        构帧 = 甲臂判活(绯英欢愉全核在手)∧ 店面 [花火/瓦尔特(覆盖枢纽),
        银狼LV.999(多线方向件:覆盖数 2 ∧ 注册单卡核心 ⇒ 非枢纽候选)],
        变异夹具把件声明序钉到最先(当前注册表内该件自然 decl=34 晚于
        全部覆盖枢纽,「件先发」支无自然实例——夹具只动序不动判据)→
        全部枢纽让位、义务通道首发 m2_line_member。判据力:若实现按覆盖
        数降序或店面序,枢纽将越过件发射 → 本测红。"""
        comp = get_comp('绯英欢愉')
        st = self._arm_live_frame([_card('花火', cost=2),
                                   _card('银狼LV.999', cost=5)],
                                  comp_name='绯英欢愉')
        natural = char_declaration_index('银狼LV.999')
        monkeypatch.setattr(
            cw_intention, 'char_declaration_index',
            lambda n: 0 if n == '银狼LV.999' else natural + 1
            if n == '花火' else char_declaration_index(n))
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, BuyCard)
        assert act.reason == 'm2_line_member' and act.card.name == '银狼LV.999'
        assert _ct(sess).get('hub_option_arbitration_yield') >= 1

    def test_layer3_hub_earlier_decl_fires_over_multi_line_piece(self):
        """增量 1 第三层(自然序):枢纽声明序(花火 2)早于多线方向件
        (银狼LV.999,34,非枢纽候选)⇒ 枢纽首发。构帧注:覆盖枢纽取
        花火(非该线核心,不在 bench——核心枢纽在全核在手构帧下被非合并
        素材前件拦,无法作发射观察位)。"""
        st = self._arm_live_frame([_card('花火', cost=2),
                                   _card('银狼LV.999', cost=5)],
                                  comp_name='绯英欢愉')
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'hub_option_buy'
        assert act.card.name == '花火'
        assert _ct(sess).get('hub_option_arbitration_yield') is None

    def test_emission_order_independent_of_shop_order(self):
        """增量 1(乱序注入店面两帧发射一致):店面槽位序翻转不改变仲裁
        产物(发射序消费判据序,禁实现遍历顺序)。"""
        acts = []
        for order in ([_card('知更鸟', cost=4), _card('布洛妮娅', cost=2)],
                      [_card('布洛妮娅', cost=2, x=200),
                       _card('知更鸟', cost=4, x=201)]):
            st = self._arm_live_frame(list(order))
            sess = _session(IntentionState())
            acts.append(_decide(st, sess))
        names = [(a.card.name, a.reason)
                 for a in acts if isinstance(a, BuyCard)]
        assert len(names) == 2 and names[0] == names[1]

    def test_f1_unaffordable_piece_loses_preemption(self):
        """F-1(落地审;证明批 §4.4 先决澄清+附带条款①):甲臂判活帧上,
        更早声明的**不可负担**方向件不获挤占权——枢纽不因其在售而让位,
        本帧照常发射。构帧:店面 [知更鸟(枢纽,decl 20,可负担,非该线核心
        ——核心名在 bench 会被非合并素材前件拦,不能作发射观察位),
        瓦尔特(方向件,decl 3,cost 99 不可负担)],修复前该件仍触发让位
        → 枢纽发射机会丢失 → 本测红。"""
        st = self._arm_live_frame([_card('知更鸟', cost=4),
                                   _card('瓦尔特', cost=99)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'hub_option_buy'
        assert act.card.name == '知更鸟'
        assert _ct(sess).get('hub_option_arbitration_yield') is None

    def test_coverage_count_descending_not_used(self):
        """§4.4 显式否决记录的测试化:互不覆盖双枢纽竞争按注册表声明序
        (三月七 decl=1 cov=2)而非覆盖数降序(花火 decl=2 cov=6)——
        若实现以覆盖数排序,本测红。"""
        st = _state(shop_cards=[_card('花火', cost=2, x=100),
                                _card('三月七', cost=1, x=101)])
        ist = IntentionState()
        assert char_declaration_index('三月七') < char_declaration_index('花火')
        assert len(hub_covered_lines(_kbridge(st), ist, '三月七')) \
            < len(hub_covered_lines(_kbridge(st), ist, '花火'))
        sess = _session(ist)
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'hub_option_buy'
        assert act.card.name == '三月七'


# ===== 正本 §5.2 锁 4 + 证明批 §4.3:丙臂守息缺省与辖域切分 =====


class TestArmCHoldDefault:

    def test_hold_default_zero_buy_and_keys(self):
        """锁 4(正本 §5.2):甲乙候选皆空帧(店面无枢纽资格件)零买入
        + 守息分键(dead_defer/hold_default,合法空经 k_fallback_source
        证据放行 = 契约零违例)。"""
        st = _state(shop_cards=[_card('注册表外散件Z', cost=1)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        ct = _ct(sess)
        assert ct.get('shop_no_target_hold_default') == 1
        assert ct.get('shop_no_target_arm_a_dead_defer') == 1
        assert not [k for k in ct if k.startswith('criteria_contract_violation')]

    def test_must_spend_zone_no_refresh_burn(self):
        """证明批 §4.3-4(必花域裁决②消解路径):p2plus 无目标帧落必花域
        时,R1 合格集 = 判据臂输出 = 空 ⇒ no_chaseable_member fail-closed
        ⇒ 烧费路径消失(P35 帧 14:18:21 形态不再复发,零 RefreshShop)。"""
        st = _state(gold=80)
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert not isinstance(act, (BuyCard, RefreshShop))
        ct = _ct(sess)
        assert ct.get('shop_r1_no_chaseable_member') == 1
        assert 'must_spend_r1_account_yielded' not in ct

    def test_prep_m3_not_frozen_by_hold(self):
        """锁 4 辖域切分腿(正本 §2.4/§5.2 锁 4):升级既有授权不受丙臂
        冻结——k_members 空帧 arm1 触发(板满∧bench 有候补)照常发射
        LevelUp(mandate.MandateFrame 备战面直构)。"""
        deployed = [_bc(f'注册表外散件{i}', star=2, slot=i + 1)
                    for i in range(4)]
        frame = mandate.MandateFrame(
            gold=80, level=4, bench=[_bc('注册表外散件A', slot=1)],
            deployed=deployed, deploy_cap=4, node_type='battle',
            stop_flag=False, k_members=(), round_num=2)
        st = GameState(gold=80, level=4, hp=30, plane=2, round_num=2)
        st.level_readable = True
        st.deploy_cap = 4
        st.node_type = 'battle'
        sess = SimpleNamespace(cw4_counters={}, target_comp=None,
                               v3_intention=IntentionState(),
                               active_strategies=[])
        out = mandate.run_mandate(frame, sess, state=st)
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            LevelUp,
        )
        assert [e for e in out if isinstance(e.action, LevelUp)], \
            '丙臂守息不得冻结升级既有授权(发展优先不变量,01 §8-2)'


# ===== 正本 §4.6 k_members 三下游(锁 6):甲臂换源同源断言 =====


class TestKMembersDownstream:

    def test_arm_a_members_reach_m2_and_rejects(self):
        """锁 6(正本 §5.2;§4.6 换源申报):甲臂判活帧 k_members 整体 =
        甲臂方向采购集——M2 义务买甲臂缺员成员(m2_line_member 买因);
        拒因遥测对线外件维持 non_line;卖免面:M4 燃料候选排除甲臂成员
        (zero_overlap 排除集换源——成员在 bench 不出燃料候选,非成员照出)。"""
        comp = get_comp('希儿量子')
        chars, _eq = cw_intention._line_hoard(comp)
        missing_piece = sorted(m for m in chars
                               if m not in comp.core_chars)[0]
        st = _state(hp=100, shop_cards=[_card(missing_piece, cost=1),
                                        _card('注册表外散件Z', cost=1)])
        st.bench = _own(*comp.core_chars)
        st.deployed = [_bc('板上件锚', slot=1)]   # T-32 守卫非空板前置
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'm2_line_member'
        assert act.card.name == missing_piece
        assert state_of(sess).cw4_counters.get(
            'shop_no_target_arm_a_adopted') == 1
        rejects = getattr(state_of(sess), 'cw4_shop_rejects', {})
        assert str(rejects.get('注册表外散件Z', '')).startswith('non_line')
        # 卖免面直核:燃料候选 = 非成员(成员被 zero_overlap 排除集挡住)
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            mandate as m,
        )
        fuel = m.fuel_sell_candidates(
            [_bc(missing_piece, slot=8), _bc('注册表外散件Y', slot=9)],
            tuple(sorted(chars)), state=st)
        names = [c.char_id or '' for c in fuel]
        assert '注册表外散件Y' in names
        assert missing_piece not in names


# ===== 正本 §4.2 四面退役表 =====


class TestRetirementFaces:

    def test_face123_constant_absent_from_src(self):
        """四面退役完整性(正本 §4.2;墓碑注留注不留码):FALLBACK_COMP_NAME
        在 src 的 currency_war 子树零**代码级**符号(AST Name/Attribute
        标识符扫描——墓碑注/退役注是注释与 docstring 文本,不构成代码
        引用,不误伤)。带变异自检(扫描器对注入代码形态能命中)。"""
        import ast
        root = Path(cw_intention.__file__).parents[1]
        hits: list[str] = []
        for py in root.rglob('*.py'):
            text = py.read_text(encoding='utf-8', errors='replace')
            if 'FALLBACK_COMP_NAME' not in text:
                continue   # 预滤:AST 标识符命中必含裸串,免全树逐文件解析(纪律 15)
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id == 'FALLBACK_COMP_NAME':
                    hits.append(f'{py}:{node.lineno}')
                if (isinstance(node, ast.Attribute)
                        and node.attr == 'FALLBACK_COMP_NAME'):
                    hits.append(f'{py}:{node.lineno}')
        assert not hits, f'FALLBACK_COMP_NAME 代码引用残留: {hits}'
        # 变异自检:同一扫描器对代码形态能命中
        probe = ast.parse('x = FALLBACK_COMP_NAME\ny = m.FALLBACK_COMP_NAME')
        found = [n for n in ast.walk(probe)
                 if (isinstance(n, ast.Name) and n.id == 'FALLBACK_COMP_NAME')
                 or (isinstance(n, ast.Attribute)
                     and n.attr == 'FALLBACK_COMP_NAME')]
        assert len(found) == 2

    def test_face4_direction_view_field_removed(self):
        """④面:DirectionView.fallback_comp 投影字段整体删除(单一写端、
        grep 无读端准死字段);契约注记 = 模块 docstring 退役注。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.turn_state import (
            DirectionView,
        )
        assert 'fallback_comp' not in DirectionView.__dataclass_fields__

    def test_face3_p1_gate_dead_branch_assertion(self):
        """③面(正本 §4.2 行 ③;删前死分支断言的测试化):恒 no-op 支
        删除后 _p1_transition_eligible(绯英欢愉) 由剩余分支判 False;
        P1 信号路径行为零差锚 = 未资格信号被 update_intention 配方锁段
        _direct_line_qualified 过滤(门后无消费)。"""
        feiying = get_comp('绯英欢愉')
        assert _p1_transition_eligible(feiying) is False
        assert '欢愉' in (set(feiying.form_tiers) | set(feiying.sub_tiers))
        assert '欢愉' not in cw_intention._ENGINE_BOND_KEYS

    def test_face2_economy_peak_anchor_default3(self):
        """②面(正本 §4.1-1 选项「维持缺省 3 费」):未锁帧排程峰值锚
        回落 3 费缺省(概率校准分量,方向语义中性);_schedule_target_core
        未锁帧返回 ''。"""
        from sr_od.application.currency_war.kernel.cw_economy import (
            _schedule_target_core,
            _target_core_cost,
            _target_peak_level,
        )
        from sr_od.application.currency_war.kernel.cw_plane_table import (
            peak_refresh_level,
        )
        sess = StrategySession()
        assert _schedule_target_core(sess) == ''
        assert _target_peak_level(GameState(), sess) == peak_refresh_level(3)
        assert _target_core_cost(sess) == ('', 3)


# ===== 证明批 §6 增量 7:甲臂漏授角 =====


class TestArmACorner:

    def test_corner_detected_and_key_fires(self):
        """增量 7(应修①测试化):plane==2 无目标帧,方向 d 过三门但
        G(d)≤ε 判死且意向核心在店/在手 ⇒ 漏授角显影(独立分键,禁混入
        判死分键);甲臂仍不授权囤 d(G 门逐字);缓锁 core 可见短路支
        与强锁门同帧判定相反(R2 双门机制)。"""
        st = _state(hp=15, level=5, round_num=9,
                    shop_cards=[_card('绯英', cost=3)])
        st.bench = _own('绯英')
        ist = IntentionState()
        arms = no_target_arms(_kbridge(st), ist)
        assert arms.direction == ''
        assert arms.corner_names == ('绯英欢愉',)
        # R2 双门分歧:同帧同输入,缓锁门 core 可见短路放行、强锁门判死
        reg = DEFAULT_REGISTRY
        vis = cw_intention._visible_chars(_kbridge(st))
        sig = cw_intention.IntentionSignal(3, 'core_card', '绯英欢愉', '', 1.0)
        assert cw_intention._p2_signal_supply_ok(st, sig, None, reg, vis)
        assert line_completion_feasibility(_kbridge(st), get_comp('绯英欢愉'), None,
                                           reg, None) \
            <= reg.revoke_miss_tolerance_eps
        sess = _session(ist)
        _decide(st, sess)
        ct = _ct(sess)
        assert ct.get('shop_no_target_arm_a_corner_defer') == 1
        assert ct.get('shop_no_target_arm_a_dead_defer') == 1


# ===== 证明批 §6 增量 5:契约面单一源守卫 ============================
# 增量 5 读端格(p2plus 合法空 + 三臂来源证据放行 / 无来源计违例 / p1 带
# 空集违例)= test_cw_contracts.test_k_projection_domain_covered_
# derivable ⑤⑥(2026-09-09 瘦身批逐格亲读等价;p1_gap 显式带格与该测④
# 同判违支,差异落在无判别力分支)——单一承载于契约主题位,此处不重复。


class TestContractSourceToken:

    def test_source_token_single_source(self):
        """来源证据 token 单一源:契约面消费与 kernel 产出同值(禁第二
        字面量)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
            contracts,
        )
        src = Path(contracts.__file__).read_text(encoding='utf-8')
        assert src.count("'three_arm'") == 0, \
            '契约面不得内联 source 字面量(单一源 = K_FALLBACK_SOURCE_THREE_ARM)'
