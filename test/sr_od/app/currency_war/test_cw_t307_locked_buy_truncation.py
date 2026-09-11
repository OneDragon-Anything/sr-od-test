"""T-307 锁定采购集容量可行截断 + P60 门修正 + 基座随 B' + R3-a 发射帧盲窗显影 锁面。

语义出处(锁的存在性纪律:每锁 docstring 引出处):
- 方案正本 = T-295-交付报告.md v2 §③ R1(传参表 14 行:谓词本体/
  装配两口径拆分/missing/M4 基座必改位 B'/P60 检查对象=截断前宽集/
  孤儿账随 B'/C1 前提位保宽声明)+ R3-a(发射帧盲窗显影 = 独立行内键
  ``m1p_obs_skipped``,否决哨兵 dict 注入 m1p 的形态);
- 重审凭据 = reviews/T-295-方案对抗审-r2.md(发现 1 补表三消费位:
  cw_deploy_logic 部署面随 B'/孤儿账随 B'/C1 保宽;发现 2 tie-break
  注册表声明序单序 + cap_hold 缺读保宽 fail-closed);
- 决策记录 = docs/develop/currency_war/decisions/0647(ADR-0647)。

锁契约(测试纪律第 8 条):锁结构语义(集合构成/截断序/门开火条件/
键显影),不锁分布数值。既有锁 test_cw_locked_buy_membership_split.
TestSellFaceAndLedgerUnswitched 的 bench9 构造语义已随 R1 修订
(B' 内成员诚实停摆由彼处承载;被截成员腾席解锁由本文件承载)。
"""
from __future__ import annotations

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
from sr_od.application.currency_war.sim.checks.t190_c import (
    _c2_plan_point,
    check_t190_c2_new_buy_swap_coverage,
)
from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    sell_gate,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# ===== 基建(与 test_cw_locked_buy_membership_split 同构)=====

_LOCK_COMP = '列车同行'
_SUB_CAP_COMP = '命运圣杯红A'   # |hoard|=5 ≤ 任意实用容量,截断零触发


def _cfg():
    return SimpleNamespace(ev_arm='full')


def _locked_ist(comp_name: str = _LOCK_COMP) -> IntentionState:
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = comp_name
    ist.lock_plane = 2
    return ist


def _sess(comp, ist: IntentionState | None) -> SimpleNamespace:
    s = SimpleNamespace(ev_arm='full')
    st = state_of(s)
    st.cw4_counters = {}
    st.target_comp = comp
    if ist is not None:
        st.v3_intention = ist
    return s


def _state(gold: int, shop_cards: list[ShopCard], level: int = 8,
           bench: list[BenchChar] | None = None) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2, hp=60)
    st.plane = 2
    st.shop = shop_cards
    st.bench = bench if bench is not None else []
    # 非空板前置(T-32 空板止损守卫):与既有锁同构的环境补齐,非语义面。
    st.deployed = [BenchChar(slot=1, char_id='板上件锚', star=1)]
    return st


def _card(name: str, cost: int, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


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
        st = _state(gold=30, shop_cards=[])
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
        st = _state(gold=30, shop_cards=[])
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
        st = _state(gold=30, level=8,
                    bench=_bench9_with_truncated(),
                    shop_cards=[_card('瓦尔特', 5)])
        bp = _b_prime(ist, st)
        assert '彦卿' not in bp and '瓦尔特' in bp
        sess = _sess(comp, ist)
        act = shop.decide_shop_action(st, sess, _cfg())
        assert isinstance(act, SellBench), act
        assert not (getattr(act, 'reason', '') or ''), \
            '被截成员卖出不得带孤儿标记(孤儿账随 B\')'
        st2 = simulate(st, act)
        act2 = shop.decide_shop_action(st2, sess, _cfg())
        assert isinstance(act2, BuyCard) and act2.card.name == '瓦尔特'
        assert act2.reason == 'm2_line_member'   # 瓦尔特 ∈ core∪shared

    def test_bp_members_only_bench_stays_stalled(self):
        """B' 内成员换手闭死语义不变(r2 ③核验通过面):bench 满全为
        B' 成员 + 缺员义务件在店 ⇒ 腾席候选空,诚实停摆可判读
        (m2_retry_exhausted / bench_full_buy_abandon ≥ 1,零买零卖)。"""
        comp = get_comp(_LOCK_COMP)
        ist = _locked_ist()
        st0 = _state(gold=30, level=8, shop_cards=[])
        bp = _b_prime(ist, st0)
        comp_obj = get_comp(_LOCK_COMP)
        chars, _eq = cw_intention._line_hoard(comp_obj)
        core = set(comp_obj.core_chars) | set(comp_obj.shared_chars)
        in_bp = sorted((set(chars) - core) & set(bp))[:BENCH_CAPACITY]
        assert len(in_bp) == BENCH_CAPACITY, '锁测试前提:B\' 内囤件不足 9'
        st = _state(gold=30, level=8,
                    bench=[_bc(m, slot=i + 1)
                           for i, m in enumerate(in_bp)],
                    shop_cards=[_card('瓦尔特', 5)])
        sess = _sess(comp, ist)
        act = shop.decide_shop_action(st, sess, _cfg())
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
        st = _state(gold=30, level=8, bench=bench,
                    shop_cards=[_card('瓦尔特', 5)])
        sess = _sess(comp, ist)
        act = shop.decide_shop_action(st, sess, _cfg())
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
        st = _state(gold=30, level=8, shop_cards=[])
        sess = _sess(comp, _locked_ist())
        shop.decide_shop_action(st, sess, _cfg())
        assert state_of(sess).cw4_counters.get(
            'shop_hoard_over_capacity', 0) >= 1

    def test_p60_no_fire_sub_capacity(self):
        """子容量 comp(|B|=5 ≤ cap_hold)不开火(负对照:门非恒开)。"""
        comp = get_comp(_SUB_CAP_COMP)
        st = _state(gold=30, level=8, shop_cards=[])
        sess = _sess(comp, _locked_ist(_SUB_CAP_COMP))
        shop.decide_shop_action(st, sess, _cfg())
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
        st = _state(gold=30, level=8, shop_cards=[])
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

        st = _state(gold=30, level=8, shop_cards=[])
        sess = _sess(comp, _locked_ist())
        shop._line_switch_orphans = _spy   # 模块级槽位,事后还原
        try:
            shop.decide_shop_action(st, sess, _cfg())
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


# ===== R3-a 发射帧盲窗显影(独立行内键)=====


class TestR3aLaunchBlindWindowKey:
    """发射帧盲窗显影锁(T-295 方案 R3-a 终定形态;ADR-0647):
    发射帧 m1p 恒 None 的成因由独立行内键显影,判读面不再混桶。"""

    def test_launch_rows_carry_skip_key(self):
        """发射帧(launch 非 None):m1p_obs_skipped ==
        'launch_short_circuit' ∧ m1p is None(观测面盲窗成因显影;
        采样窗口内至少一局含发射帧,否则观测失明需换 seed)。"""
        seen = 0
        for seed in range(3):
            for row in simulate_p1(seed, pool='snapshot').ledger:
                if row.get('launch') is None:
                    continue
                seen += 1
                assert row.get('m1p_obs_skipped') == 'launch_short_circuit'
                assert row.get('m1p') is None
        assert seen, '采样 3 seed 零发射帧(观测面失明,需换 seed 窗口)'

    def test_non_launch_rows_key_none(self):
        """非发射帧:显影键恒 None(m1p 在场或观测异常帧均不误标)。"""
        checked = 0
        for seed in range(2):
            for row in simulate_p1(seed, pool='snapshot').ledger:
                if row.get('launch') is not None:
                    continue
                checked += 1
                if row.get('m1p') is not None:
                    assert row.get('m1p_obs_skipped') is None
        assert checked, '非发射帧采样为空(锁测试前提失效)'


# ===== R3-a C-A2 桶内分键 =====


class TestCA2LaunchShortCircuitBucket:
    """C-A2 no_plan_carrier 桶内分键锁(T-295 方案「C-A2 分键随批」;
    ADR-0647):申报桶非缺口语义不变,成因可辨非混桶。"""

    @staticmethod
    def _row(plane: int, **extra) -> dict:
        row = {'plane': plane, 'actions': [], 'state': {}, 'm1p': None}
        row.update(extra)
        return row

    def test_plan_point_reports_skip_reason(self):
        """_c2_plan_point 第三返回值 = 扫描路径上的盲窗显影键;
        计划载体在场帧恒 ''(定位语义零变)。"""
        buy_row = self._row(2, m1p_obs_skipped='launch_short_circuit')
        pt, tag, skip = _c2_plan_point([buy_row], 0)
        assert pt is None and tag == ''
        assert skip == 'launch_short_circuit'
        carrier = self._row(2, m1p={'nonempty': False})
        pt2, tag2, skip2 = _c2_plan_point([carrier], 0)
        assert pt2 is carrier and tag2 == 'same_row' and skip2 == ''

    def test_c2_counts_launch_short_circuit_subkey(self):
        """无载体 + 显影键在场 → no_plan_carrier_launch_short_circuit
        分键(非缺口桶);无键(旧档案)→ 原 no_plan_carrier 零漂移。"""
        skipped_buy = {
            'plane': 2,
            'actions': [{'__type__': 'BuyCard',
                         'reason': 'm2_line_member',
                         'card': {'name': '砂金'}}],
            'state': {'bench': [], 'deployed': []},
            'm1p': None,
            'm1p_obs_skipped': 'launch_short_circuit',
        }
        plain_buy = {
            'plane': 2,
            'actions': [{'__type__': 'BuyCard',
                         'reason': 'm2_locked_member',
                         'card': {'name': '瓦尔特'}}],
            'state': {'bench': [], 'deployed': []},
            'm1p': None,
        }
        res = check_t190_c2_new_buy_swap_coverage(
            [[skipped_buy, plain_buy]])
        shapes = res['shapes']
        assert shapes.get('no_plan_carrier_launch_short_circuit') == 1
        assert shapes.get('no_plan_carrier') == 1
        assert res['gaps_plan_active'] == 0
