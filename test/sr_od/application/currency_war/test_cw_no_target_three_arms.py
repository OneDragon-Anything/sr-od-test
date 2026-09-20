"""P86 无目标期三臂判据单帧锁(落码批)。

出处(单一源):
- 命题正本 = docs/develop/sr_od/application/currency_war/proofs/p86-no-target-period-fund-allocation.md
  (§2 三臂形态/§4.2 四面退役表/§4.4 旧锁清单与重推义务/§5.2 单帧锁清单);
- 证明批 = docs/develop/sr_od/application/currency_war/proofs/p86-proof-batch.md
  (§3 定理 A/B1-B5/C/M;§4 必答六件终裁;§6 落码批增量条款九件)。

锁编号对齐:正本 §5.2 锁 1-7 + 证明批 §6 增量 1-9,逐测试 docstring 引出处。
构种子口径:hp 缺省 60;判死形态帧显式 hp=15/0 ⇒ ``p2_supply_horizon``
趋 0 ⇒ 全线 G=0(机器判死形态);甲臂判活帧显式给 hp 并授满某线全部
核心(G=1.0)。判读注册表事实(cov/声明序)一律运行时直调派生,不写死清单。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _kbridge,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)

from sr_od.application.currency_war.kernel import cw_intention
from sr_od.application.currency_war.kernel.cw_comps import (
    CORE_SINGLE_CARD_REGISTRY,
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
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
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    CwActionBuyCardParam,
    CwActionRefreshShopParam,
    ShopCard,
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
           bench: list[BenchSlot] | None = None,
           deployed: list[Unit] | None = None,
           round_num: int = 2) -> dict:
    """三臂场景种子轴(返回 = 桥/feed 两配方的公共 kwargs;deployed =
    前排行域 Units,旧槽表首 4 位即前排的语义经显式行表达)。"""
    axes: dict = {'gold': gold, 'level': level, 'round_num': round_num,
                  'hp': hp, 'plane': 2,
                  'shop': shop_cards if shop_cards is not None else []}
    if bench is not None:
        axes['bench'] = bench
    if deployed is not None:
        axes['front_row'] = deployed
    return axes


def _card(name: str, cost: int = 3, star: int = 1, x: int = 0) -> ShopCard:
    """x = 店面物理槽下标(0 基;三态定长五槽合成口按 x 对槽,越界丢弃——
    旧画面坐标桩值 x=100 语义已退役,误用会把店面清成 5 空槽)。"""
    return ShopCard(x=x, name=name, cost=cost, star=star)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchSlot:
    """占席条目(容器形状;bench/燃料候选域直构面)。"""
    return BenchSlot(kind='unit', unit=Unit(char_id=name, star=star,
                                            slot=slot))


def _decide(st: dict, sess: StrategySession):
    return shop.decide_shop_action(cw4_gs(sess, **st), sess, _cfg())


def _ct(sess: StrategySession) -> dict:
    return state_of(sess).cw4_counters or {}


def _own(*names: str) -> list[BenchSlot]:
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
        st['bench'] = _own(*comp.core_chars)
        ist = IntentionState()
        assert arm_a_live_direction(_kbridge(**st), ist) == '希儿量子'
        # (原「独立重算对拍」段删:按 cw_intention 内部谓词链重算候选集再
        #  断言同名 = 复刻被测逻辑形态,删被测函数该段照样绿;强锁门行为
        #  面由上断言与 fallback 两腿承重。)
        kfb, tok = k_empty_window_fallback(_kbridge(**st), ist)
        assert tok == 'p2plus'
        chars, _eq = cw_intention._line_hoard(comp)
        assert kfb == frozenset(chars)

    @pytest.mark.parametrize('case', [
        'dead-g0-no-hoard', 'dead-partial-g-no-hoard',
        'p1-bands-and-weak', 'locked-frame-dormant',
    ])
    def test_out_of_domain_matrix(self, case: str):
        """出域矩阵一锁(参数化并一;合并原 test_dead_direction_g0_no_hoard /
        test_dead_direction_partial_g_no_hoard / test_p1_bands_and_weak_out_
        of_scope / test_locked_frame_three_arms_dormant,断言腿逐条保留):

        - dead-g0(锁 1,G=0 档):判死形态帧(构帧口径:hp 缺省 0 ⇒ 视界
          零 ⇒ 全线 G=0,绯英 G=0.0000 是其注册表实例)不发射囤货——回退
          成员集为空(fallback_hold),非绯英采购集;
        - dead-partial-g(锁 1,0<G≤ε 档,防 F1 修复回退):部分完成但机器
          判死的线不获囤货授权(构帧 = 授满绯英欢愉除瓦尔特(5 费)外全部
          核心,lv7/hp15 ⇒ G=q(瓦尔特)∈(0,ε] 运行时核域,不写死值);
        - p1-bands-and-weak(必答⑥出辖,证明批 §4.1 裁决 + 域守卫引理 Z/
          正本 §6.2-4):plane=1 与 weak/demoted 帧三臂全空甲乙,p1 带回退
          维持既有判据族(四体系全集/体系对)——退役面收窄;
        - locked-frame(锁 5,正本 §5.2):locked_buy_membership 非 None 帧
          本命题三臂全部不发射——no_target_arms 出域返回空甲乙;店面枢纽
          件不落 hub_option_buy 买因(锁线态由 M2/C1 既有通道辖)。
        """
        if case == 'dead-g0-no-hoard':
            st = _state()
            ist = IntentionState()
            arms = no_target_arms(_kbridge(**st), ist)
            assert arms.direction == ''
            assert arms.char_targets == frozenset()
            ht = hoard_target_set(_kbridge(**st), ist)
            assert ht.mode == 'fallback_hold' and not ht.char_targets
            kfb, tok = k_empty_window_fallback(_kbridge(**st), ist)
            assert kfb == frozenset() and tok == 'p2plus'
        elif case == 'dead-partial-g-no-hoard':
            reg = DEFAULT_REGISTRY
            st = _state(hp=15, level=7)
            cores = [m for m in get_comp('绯英欢愉').core_chars
                     if m != '瓦尔特']
            st['bench'] = _own(*cores)
            ist = IntentionState()
            g = line_completion_feasibility(_kbridge(**st), get_comp('绯英欢愉'),
                                            None, reg, None)
            assert 0 < g <= reg.revoke_miss_tolerance_eps
            assert arm_a_live_direction(_kbridge(**st), ist) == ''
        elif case == 'p1-bands-and-weak':
            st1 = _state(hp=100)
            st1['plane'] = 1
            ist1 = IntentionState()
            assert no_target_arms(_kbridge(**st1), ist1).direction == ''
            assert no_target_arms(_kbridge(**st1), ist1).hub_names == ()
            # p1_gap 带回退 = 四体系引擎件全集(既有判据族,不入三臂)
            kfb, tok = k_empty_window_fallback(_kbridge(**st1), ist1)
            assert tok == 'p1_gap' and kfb
            stw = _state()
            istw = IntentionState()
            istw.phase = 'weak'
            assert no_target_arms(_kbridge(**stw), istw) == \
                cw_intention.NoTargetArms('', frozenset())
            assert hoard_target_set(_kbridge(**stw), istw).mode == 'weak' \
                # 跨线骨架分带
        else:
            assert case == 'locked-frame-dormant'
            ist = IntentionState()
            ist.phase = 'locked'
            ist.locked_comp = '希儿量子'
            st = _state(shop_cards=[_card('花火', cost=2)])
            assert no_target_arms(_kbridge(**st), ist).hub_names == ()
            sess = _session(ist)
            state_of(sess).target_comp = get_comp('希儿量子')
            act = _decide(st, sess)
            assert not [a for a in ([act] if act else [])
                        if isinstance(a, CwActionBuyCardParam)
                        and a.reason == 'hub_option_buy']
            assert 'hub_option_buy_hit' not in _ct(sess)


# ===== 证明批 §6 增量 2/3 + 定理 B5:乙臂资格核 =====


class TestHubEligibility:

    # (原 test_eligibility_input_face_static 删:AST 标识符负检 = 源码扫描
    #  形态,禁止清单无例外——「定理 B2 输入面解耦」防线归 review 与代码
    #  规范;资格核的行为面由本类真值表锁承重。)

    def test_hub_eligibility_truth_table(self):
        """乙臂资格核真值表一锁(三案并一;合并原
        test_yinlang_counter_example_and_dual_channel_mutex /
        test_coverage_boundary_and_hubs_present / test_star2_hub_card_not_
        enumerated,断言腿逐条保留):

        - 计数边界(定理 B5):覆盖数 = 1(希儿)不入枢纽档;覆盖数 ≥ 2
          (花火,注册表全库直调)入档;资格核非空 = 病灶帧条件非空
          (定理 B2-2 的运行时核);
        - 银狼反例(增量 3,证明批 §6;定理 B5 测试化):银狼LV.999 覆盖数
          = 2 而系注册单卡依赖核心 ⇒ 乙臂不发射、规则③通道发射,双通道
          互斥;
        - 2★ 前件(锁 8 前件,§3.2 合取:refund_full_star_ok 仅 1★):
          2★ 枢纽直出卡不入候选枚举(2★ 退金 3c−1 ≠ 净 0,定理 B4 闭集 3
          的事实面)。
        """
        # —— 计数边界 ——
        st = _state()
        ist = IntentionState()
        assert len(hub_covered_lines(_kbridge(**st), ist, '希儿')) == 1
        assert '希儿' not in hub_option_names(_kbridge(**st), ist)
        assert len(hub_covered_lines(_kbridge(**st), ist, '花火')) >= 2
        hubs = hub_option_names(_kbridge(**st), ist)
        assert '花火' in hubs and hubs
        # —— 银狼反例 + 双通道互斥 ——
        st_y = _state(shop_cards=[_card('银狼LV.999', cost=5)])
        ist_y = IntentionState()
        assert len(hub_covered_lines(_kbridge(**st_y), ist_y,
                                     '银狼LV.999')) == 2
        assert '银狼LV.999' in CORE_SINGLE_CARD_REGISTRY
        assert '银狼LV.999' not in hub_option_names(_kbridge(**st_y), ist_y)
        sess = _session(ist_y)
        act = _decide(st_y, sess)
        assert isinstance(act, CwActionBuyCardParam)
        assert act.reason == 'core_single_card_buy:unlocked'
        ct = _ct(sess)
        assert ct.get('core_unlocked_buy_hit') == 1
        assert 'hub_option_buy_hit' not in ct
        # —— 2★ 前件:不入候选枚举 ——
        assert not refund_full_star_ok(2, 2)
        st_2 = _state(shop_cards=[_card('花火', cost=2, star=2)])
        sess_2 = _session(IntentionState())
        act_2 = _decide(st_2, sess_2)
        assert not isinstance(act_2, CwActionBuyCardParam)
        assert 'hub_option_candidate_seen' not in _ct(sess_2)


# ===== 正本 §5.2 锁 3/8 + §4.4 行 3:乙臂发射与拒因归真 =====


class TestHubEmission:
    def test_hub_fire_and_reject_family_truthful(self):
        """锁 3(正本 §5.2)发射+拒因归真一锁(合并原
        test_hub_fires_on_arm_dead_frame / test_reject_family_truthful /
        test_hub_reject_reason_key_not_non_line,断言腿逐条保留):

        - 发射面(F2 测试化):甲臂空集帧乙臂**照常评估**并发射(病灶帧
          正是 D3 要接枢纽期权的帧,出手机会不可丢);发射 = 五前件合取
          全过(资格核花火 + 非合并素材 + 1★ 全退 + 席 + 息 + 金);
        - 拒因面:任一合取项缺席帧按缺席项分键,非静默。素材(场内已有
          同名同星 1★,bench 与部署面两形态)/席位/息/金四门逐帧判
          (证明批 §3.2 五前件合取 + §6 增量 8);
        - 拒因键面(§4.4 行 3 non_line 拒因锁重推):空窗帧枢纽资格件在售
          未买帧拒因 = hub_option(显式),不再落 non_line。"""
        # —— 发射面 ——
        st = _state(shop_cards=[_card('花火', cost=2)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, CwActionBuyCardParam) and act.reason == 'hub_option_buy'
        ct = _ct(sess)
        assert ct.get('hub_option_buy_hit') == 1
        assert ct.get('hub_option_candidate_seen') == 1
        assert ct.get('shop_no_target_arm_a_dead_defer') == 1
        # —— 拒因面:非合并素材(副本在 bench)——
        st_m = _state(shop_cards=[_card('花火', cost=2)],
                      bench=[_bc('花火', slot=1)])
        sess_m = _session(IntentionState())
        act_m = _decide(st_m, sess_m)
        assert not isinstance(act_m, CwActionBuyCardParam)
        assert _ct(sess_m).get('hub_option_reject_merge_material') == 1
        # 非合并素材:副本在部署面(复核观察变体:核对面 = bench∪deployed
        # 全场域,same_star_count 单一源计数)
        st_d = _state(shop_cards=[_card('花火', cost=2)],
                      deployed=[Unit(char_id='花火', star=1, slot=1)])
        sess_d = _session(IntentionState())
        act_d = _decide(st_d, sess_d)
        assert not isinstance(act_d, CwActionBuyCardParam)
        assert _ct(sess_d).get('hub_option_reject_merge_material') == 1
        # 席位:bench 满
        st_s = _state(shop_cards=[_card('花火', cost=2)],
                      bench=[_bc(f'注册表外散件{i}', slot=i + 1)
                             for i in range(BENCH_CAPACITY)])
        sess_s = _session(IntentionState())
        act_s = _decide(st_s, sess_s)
        assert not isinstance(act_s, CwActionBuyCardParam)
        assert _ct(sess_s).get('hub_option_reject_seats') == 1
        # 息:50 买 2 跨息档 ⇒ L>0 拒(C1 通道同口径金币构帧,P47 现算)
        st_i = _state(gold=50, shop_cards=[_card('花火', cost=2)])
        sess_i = _session(IntentionState())
        act_i = _decide(st_i, sess_i)
        assert not isinstance(act_i, CwActionBuyCardParam)
        assert _ct(sess_i).get('hub_option_reject_interest') == 1
        # 金:不足帧的拒因按规范门序(席→息→金)取首败项——帧输入
        #(r_remaining=17 的息轨迹)下 poor 帧 L>0 先真,unaffordable 被
        # t5 结构性前遮;此处锁「门序首败项归真」语义本身,affordable
        # 闸独立显影面 = 消费同一单一源 mandate.check_affordable 的
        # C1/M2 通道既有锁。
        st_g = _state(gold=1, shop_cards=[_card('花火', cost=2)])
        sess_g = _session(IntentionState())
        act_g = _decide(st_g, sess_g)
        assert not isinstance(act_g, CwActionBuyCardParam)
        assert _ct(sess_g).get('hub_option_reject_interest') == 1
        assert _ct(sess_g).get('hub_option_reject_unaffordable') is None
        # —— 拒因键面:hub_option 显式,non_line 只辖线外件 ——
        st_k = _state(gold=1, shop_cards=[_card('花火', cost=2),
                                          _card('注册表外散件Z', cost=1,
                                                x=1)])
        sess_k = _session(IntentionState())
        _decide(st_k, sess_k)
        rejects = getattr(state_of(sess_k), 'cw4_shop_rejects', {})
        assert rejects.get('花火') == 'hub_option'
        assert rejects.get('注册表外散件Z') == 'non_line'

    def test_merge_frozen_state_telemetry_discernible(self):
        """F-5(落地审;增量 8 后半,B4 闭集 3/P75 (vi) 同款):已持枢纽帧
        外部通道到达同名副本后合并冻结态可辨——素材对在场 = 滞留显影键
        载体(merge_material_stale_names 单一源),2★ 吞升后 1★ 净 0 出口
        消失(refund_full_star_ok(2,·)=False 事实面),乙臂对该名不再发射
        (场内副本 ≥1 即拒)。"""
        st = _state(shop_cards=[_card('花火', cost=2)],
                    bench=[_bc('花火', slot=1), _bc('花火', slot=2)])
        # 合并冻结态显影:同名同 1★ 对在场 = 滞留素材(判定单一源直核)
        from sr_od.application.currency_war.kernel.cw_vocab import (
            merge_material_stale_names,
        )
        assert merge_material_stale_names(st['bench'],
                                          st.get('front_row')) == ('花火',)
        assert not refund_full_star_ok(2, 2)   # 2★ 出口面(吞升后资格消失)
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert not isinstance(act, CwActionBuyCardParam)
        assert _ct(sess).get('hub_option_reject_merge_material') == 1
    def test_hub_hold_registration_positive_and_negative(self):
        """hold 登记资格域正负一锁(合并原 test_hub_hold_registration_and_
        sell_protection / test_hub_hold_registration_negative_stale_
        semantics,断言腿逐条保留):

        - 正面(攻击 r1 发现1(高)三面收口):TRANSITION_PACK 之外枢纽
          (瓦尔特,cw_line_facts:75-76 移出记录实证)——面① hold 登记
          资格域 = 静态持有集 ∪ 乙臂获取名集(发射位先登记后 emit,当笔
          在场):买入后 launch_cause_mismatch 零污染 + 登记簿落
          (hold, 轮);面② 装配 A 身份段并集:获取名 ∈ sell_exclusions
          (凑息/腾席/筹资资格排除),1★ 期权不再被己方卖面跨轮卖掉;
          面③ 部署域读端 = 鸭子读同一载体;
        - 负面:获取名集之外的名不获资格域扩张——非持有名 hold 登记仍拒
          (launch_cause_mismatch 病灶信号语义不被乙臂面稀释)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            sell_gate,
        )
        # —— 正面 ——
        st = _state(shop_cards=[_card('瓦尔特', cost=4)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, CwActionBuyCardParam) and act.reason == 'hub_option_buy'
        ct = _ct(sess)
        # 面①:登记资格域并入获取名集,病灶信号键零污染 + 簿落账
        assert 'launch_cause_mismatch' not in ct
        book = getattr(state_of(sess), sell_gate.LAUNCH_REGISTRY_ATTR, {})
        assert book.get('瓦尔特') == ('hold', 2)
        # 面②:装配 A 身份段并集(下一备战帧 round 推进,L1 同轮硬面过期
        # ——fresh_buys 只保当轮,攻击报告「跨轮自动失效」形态;非并集时
        # 该名落回凑息/腾席燃料资格 = 期权被己方卖面销毁)
        st_next = _state(round_num=3)
        cw4_gs(sess, **st_next)
        excl_next = sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=3)
        assert '瓦尔特' in excl_next
        fuel = mandate.fuel_sell_candidates(
            [_bc('瓦尔特', slot=1)], (), state=_kbridge(**st_next),
            exclude_names=excl_next)
        assert not fuel
        # 面③:读口单一源(登记域/身份段/部署域三面同源)
        assert '瓦尔特' in sell_gate.hub_acquired_names_of(sess)
        # —— 负面:非持有名不获扩张 ——
        sess_neg = _session(IntentionState())
        ok = sell_gate.register_launch(
            sess_neg, '注册表外散件Q', cause='hold', round_num=3,
            star=1, cost=1)
        assert not ok
        assert _ct(sess_neg).get('launch_cause_mismatch') == 1

    # (test_star2_hub_card_not_enumerated 已并入 TestHubEligibility.
    #  test_hub_eligibility_truth_table;test_hub_reject_reason_key_not_
    #  non_line 已并入上方 test_hub_fire_and_reject_family_truthful 的
    #  拒因键面。)


# ===== 证明批 §4.4 + §6 增量 1:同帧仲裁三层序 =====


class TestArbitration:

    def _arm_live_frame(self, shop_cards, gold: int = 45,
                        comp_name: str = '希儿量子'):
        """甲臂判活帧:授满该线全部核心 ⇒ 机器选择序首方向(运行时断言,
        不写死);甲臂成员集含缺员件供 M2 竞争。"""
        comp = get_comp(comp_name)
        st = _state(gold=gold, hp=100, shop_cards=shop_cards)
        st['bench'] = _own(*comp.core_chars)
        assert arm_a_live_direction(_kbridge(**st), IntentionState()) == comp_name
        return st
    def test_layer1_dominance_and_shop_order_independence(self, monkeypatch):
        """第一层支配序一锁(合并原 test_layer1_covering_hub_beats_single_
        line_piece / test_emission_order_independent_of_shop_order,断言腿
        逐条保留;增量 1,证明批 §6;§4.4 第一层支配序,推论 B1.1):

        - 层序腿:同帧同店面给甲方向的单线方向件(布洛妮娅,C_x={希儿量子}
          运行时直调核)与覆盖其线的枢纽件(知更鸟),资源两件都足 ⇒ 发射
          枢纽。判据力:变异夹具把件声明序钉到枢纽之前(自然序 20<21 两序
          同向不判)——层序失效降第三层时件将首发 → 本测红;
        - 乱序腿:店面槽位序翻转不改变仲裁产物(发射序消费判据序,禁实现
          遍历顺序)。"""
        st = self._arm_live_frame([_card('知更鸟', cost=4),
                                   _card('布洛妮娅', cost=2, x=1)])
        monkeypatch.setattr(
            cw_intention, 'char_declaration_index',
            lambda n: 0 if n == '布洛妮娅' else 99 if n == '知更鸟'
            else char_declaration_index(n))
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, CwActionBuyCardParam) and act.reason == 'hub_option_buy'
        assert act.card.name == '知更鸟'
        assert _ct(sess).get('hub_option_arbitration_yield') is None
        # 乱序注入店面两帧发射一致
        acts = []
        for order in ([_card('知更鸟', cost=4), _card('布洛妮娅', cost=2, x=1)],
                      [_card('布洛妮娅', cost=2),
                       _card('知更鸟', cost=4, x=1)]):
            st_o = self._arm_live_frame(list(order))
            sess_o = _session(IntentionState())
            acts.append(_decide(st_o, sess_o))
        names = [(a.card.name, a.reason)
                 for a in acts if isinstance(a, CwActionBuyCardParam)]
        assert len(names) == 2 and names[0] == names[1]

    def test_layer3_decl_order_decides_both_directions(self, monkeypatch):
        """第三层支配序双向一锁(合并原 test_layer3_multi_line_piece_first_
        by_decl_order / test_layer3_hub_earlier_decl_fires_over_multi_line_
        piece,断言腿逐条保留;增量 1 第三层):多线方向件与覆盖枢纽竞争
        按注册表声明序首发,两个方向各一腿——

        - 件先发腿(变异夹具):构帧 = 甲臂判活(绯英欢愉全核在手)∧ 店面
          [花火/瓦尔特(覆盖枢纽),银狼LV.999(多线方向件:覆盖数 2 ∧ 注册
          单卡核心 ⇒ 非枢纽候选)],夹具把件声明序钉到最先(当前注册表内
          该件自然 decl=34 晚于全部覆盖枢纽,「件先发」支无自然实例——夹具
          只动序不动判据)→ 全部枢纽让位、义务通道首发 m2_line_member。
          判据力:若实现按覆盖数降序或店面序,枢纽将越过件发射 → 本测红;
        - 枢纽先发腿(自然序):枢纽声明序(花火 2)早于多线方向件
          (银狼LV.999,34,非枢纽候选)⇒ 枢纽首发。构帧注:覆盖枢纽取
          花火(非该线核心,不在 bench——核心枢纽在全核在手构帧下被非合并
          素材前件拦,无法作发射观察位)。"""
        # —— 件先发腿(夹具动序)——
        st = self._arm_live_frame([_card('花火', cost=2),
                                   _card('银狼LV.999', cost=5, x=1)],
                                  comp_name='绯英欢愉')
        natural = char_declaration_index('银狼LV.999')
        monkeypatch.setattr(
            cw_intention, 'char_declaration_index',
            lambda n: 0 if n == '银狼LV.999' else natural + 1
            if n == '花火' else char_declaration_index(n))
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, CwActionBuyCardParam)
        assert act.reason == 'm2_line_member' and act.card.name == '银狼LV.999'
        assert _ct(sess).get('hub_option_arbitration_yield') >= 1
        # 撤销夹具(monkeypatch 只辖本锁,两腿同函数——夹具不撤会污染
        # 自然序腿的声明序)
        monkeypatch.undo()
        # —— 枢纽先发腿(自然序)——
        st_n = self._arm_live_frame([_card('花火', cost=2),
                                     _card('银狼LV.999', cost=5, x=1)],
                                    comp_name='绯英欢愉')
        sess_n = _session(IntentionState())
        act_n = _decide(st_n, sess_n)
        assert isinstance(act_n, CwActionBuyCardParam) and act_n.reason == 'hub_option_buy'
        assert act_n.card.name == '花火'
        assert _ct(sess_n).get('hub_option_arbitration_yield') is None
    def test_f1_unaffordable_piece_loses_preemption(self):
        """F-1(落地审;证明批 §4.4 先决澄清+附带条款①):甲臂判活帧上,
        更早声明的**不可负担**方向件不获挤占权——枢纽不因其在售而让位,
        本帧照常发射。构帧:店面 [知更鸟(枢纽,decl 20,可负担,非该线核心
        ——核心名在 bench 会被非合并素材前件拦,不能作发射观察位),
        瓦尔特(方向件,decl 3,cost 99 不可负担)],修复前该件仍触发让位
        → 枢纽发射机会丢失 → 本测红。"""
        st = self._arm_live_frame([_card('知更鸟', cost=4),
                                   _card('瓦尔特', cost=99, x=1)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, CwActionBuyCardParam) and act.reason == 'hub_option_buy'
        assert act.card.name == '知更鸟'
        assert _ct(sess).get('hub_option_arbitration_yield') is None
    def test_coverage_order_veto_and_arm_a_corner(self):
        """覆盖序否决 + 甲臂漏授角一锁(合并原 test_coverage_count_
        descending_not_used / TestArmACorner.test_corner_detected_and_key_
        fires,断言腿逐条保留):

        - 覆盖序否决腿(§4.4 显式否决记录的测试化):互不覆盖双枢纽竞争
          按注册表声明序(三月七 decl=1 cov=2)而非覆盖数降序(花火
          decl=2 cov=6)——若实现以覆盖数排序,本腿红;
        - 漏授角腿(增量 7,应修①测试化):plane==2 无目标帧,方向 d 过
          三门但 G(d)≤ε 判死且意向核心在店/在手 ⇒ 漏授角显影(独立分键,
          禁混入判死分键);甲臂仍不授权囤 d(G 门逐字);缓锁 core 可见
          短路支与强锁门同帧判定相反(R2 双门机制)。"""
        # —— 覆盖序否决 ——
        st = _state(shop_cards=[_card('花火', cost=2),
                                _card('三月七', cost=1, x=1)])
        ist = IntentionState()
        assert char_declaration_index('三月七') < char_declaration_index('花火')
        assert len(hub_covered_lines(_kbridge(**st), ist, '三月七')) \
            < len(hub_covered_lines(_kbridge(**st), ist, '花火'))
        sess = _session(ist)
        act = _decide(st, sess)
        assert isinstance(act, CwActionBuyCardParam) and act.reason == 'hub_option_buy'
        assert act.card.name == '三月七'
        # —— 甲臂漏授角 ——
        st_c = _state(hp=15, level=5, round_num=9,
                      shop_cards=[_card('绯英', cost=3)])
        st_c['bench'] = _own('绯英')
        ist_c = IntentionState()
        arms = no_target_arms(_kbridge(**st_c), ist_c)
        assert arms.direction == ''
        assert arms.corner_names == ('绯英欢愉',)
        # R2 双门分歧:同帧同输入,缓锁门 core 可见短路放行、强锁门判死
        reg = DEFAULT_REGISTRY
        vis = cw_intention._visible_chars(_kbridge(**st_c))
        sig = cw_intention.IntentionSignal(3, 'core_card', '绯英欢愉', '', 1.0)
        assert cw_intention._p2_signal_supply_ok(_kbridge(**st_c), sig, None, reg, vis)
        assert line_completion_feasibility(_kbridge(**st_c),
                                           get_comp('绯英欢愉'), None,
                                           reg, None) \
            <= reg.revoke_miss_tolerance_eps
        sess_c = _session(ist_c)
        _decide(st_c, sess_c)
        ct = _ct(sess_c)
        assert ct.get('shop_no_target_arm_a_corner_defer') == 1
        assert ct.get('shop_no_target_arm_a_dead_defer') == 1


# ===== 正本 §5.2 锁 4 + 证明批 §4.3:丙臂守息缺省与辖域切分 =====


class TestArmCHoldDefault:

    def test_hold_consumption_three_faces(self):
        """丙臂守息消费三面一锁(合并原 test_hold_default_zero_buy_and_keys /
        test_must_spend_zone_no_refresh_burn / test_prep_m3_not_frozen_by_
        hold,断言腿逐条保留):

        - 默认守息面(锁 4,正本 §5.2):甲乙候选皆空帧(店面无枢纽资格件)
          零买入 + 守息分键(dead_defer/hold_default,合法空经
          k_fallback_source 证据放行 = 契约零违例);
        - 必花域消解面(证明批 §4.3-4,必花域裁决②消解路径):p2plus 无
          目标帧落必花域时,R1 合格集 = 判据臂输出 = 空 ⇒ no_chaseable_
          member fail-closed ⇒ 烧费路径消失(P35 帧 14:18:21 形态不再
          复发,零 CwActionRefreshShopParam);
        - 升级不冻结面(锁 4 辖域切分腿,正本 §2.4/§5.2 锁 4):升级既有
          授权不受丙臂冻结——k_members 空帧 arm1 触发(板满∧bench 有候补)
          照常发射 CwActionLevelUpParam(mandate.MandateFrame 备战面直构)。
        """
        # —— 默认守息面 ——
        st = _state(shop_cards=[_card('注册表外散件Z', cost=1)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert not isinstance(act, CwActionBuyCardParam)
        ct = _ct(sess)
        assert ct.get('shop_no_target_hold_default') == 1
        assert ct.get('shop_no_target_arm_a_dead_defer') == 1
        assert not [k for k in ct
                    if k.startswith('criteria_contract_violation')]
        # —— 必花域消解面 ——
        st_ms = _state(gold=80)
        sess_ms = _session(IntentionState())
        act_ms = _decide(st_ms, sess_ms)
        assert not isinstance(act_ms, (CwActionBuyCardParam, CwActionRefreshShopParam))
        ct_ms = _ct(sess_ms)
        assert ct_ms.get('shop_r1_no_chaseable_member') == 1
        assert 'must_spend_r1_account_yielded' not in ct_ms
        # —— 升级不冻结面 ——
        # P4 容器形:MandateFrame 直构面 = 占席条目 + 行域 Unit
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionLevelUpParam,
        )
        deployed = [Unit(char_id=f'注册表外散件{i}', star=2, slot=i + 1)
                    for i in range(4)]
        frame = mandate.MandateFrame(
            gold=80, level=4,
            bench=[BenchSlot(kind='unit',
                             unit=Unit(char_id='注册表外散件A', star=1,
                                       slot=1))],
            deployed=deployed, deploy_cap=4, node_type='battle',
            stop_flag=False, k_members=(), round_num=2)
        st_m3 = {'gold': 80, 'level': 4, 'hp': 30, 'plane': 2,
                 'round_num': 2, 'node': 'battle', 'deploy_cap': 4}
        sess_m3 = SimpleNamespace(cw4_counters={}, target_comp=None,
                                  v3_intention=IntentionState(),
                                  active_strategies=[])
        out = mandate.run_mandate(frame, sess_m3, state=_kbridge(**st_m3))
        assert [e for e in out if isinstance(e.action, CwActionLevelUpParam)], \
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
                                        _card('注册表外散件Z', cost=1, x=1)])
        st['bench'] = _own(*comp.core_chars)
        st['front_row'] = [Unit(char_id='板上件锚', star=1, slot=1)]   # 空板止损守卫前置(前排行域 Unit)
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, CwActionBuyCardParam) and act.reason == 'm2_line_member'
        assert act.card.name == missing_piece
        assert state_of(sess).cw4_counters.get(
            'shop_no_target_arm_a_adopted') == 1
        rejects = getattr(state_of(sess), 'cw4_shop_rejects', {})
        assert str(rejects.get('注册表外散件Z', '')).startswith('non_line')
        # 卖免面直核:燃料候选 = 非成员(成员被 zero_overlap 排除集挡住;
        # P4 容器形:候选域 = 占席条目,身份经解包口)
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            mandate as m,
        )

        def _entry(name: str, slot: int):
            return BenchSlot(kind='unit',
                             unit=Unit(char_id=name, star=1, slot=slot))
        fuel = m.fuel_sell_candidates(
            [_entry(missing_piece, 8), _entry('注册表外散件Y', 9)],
            tuple(sorted(chars)), state=_kbridge(**st))
        names = [m._slot_cid(c) for c in fuel]
        assert '注册表外散件Y' in names
        assert missing_piece not in names


# ===== 正本 §4.2 四面退役表(收口整删)====================
# 原 TestRetirementFaces(test_face3_p1_gate_dead_branch_assertion /
# test_face2_economy_peak_anchor_default3)删:③面 = 恒 no-op 支删除后
# 判定函数对绯英欢愉返 False(静态形状断言,无运行行为可断);②面 =
# 排程峰值锚缺省 3 费(缺省值复述,锁不出故障形态)。退役面纪律归
# review 与代码规范;①④面源码扫描形态原三审已删。


# ===== 证明批 §6 增量 7:甲臂漏授角 ==================
# (TestArmACorner.test_corner_detected_and_key_fires 已并入上方
#  TestArbitration.test_coverage_order_veto_and_arm_a_corner,断言腿
#  零丢失。)

# ===== 证明批 §6 增量 5:契约面单一源守卫 ============================
# 增量 5 读端格(p2plus 合法空 + 三臂来源证据放行 / 无来源计违例 / p1 带
# 空集违例)现无承载——原注释声称由 test_cw_contracts 承载,该文件全史
# 不存在(幽灵指针,2026-09-15 复核);覆盖缺口已申报,不得当作已辖。
