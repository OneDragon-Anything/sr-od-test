"""T-149 保底金门落码锁(ADR-0603;域③声明 = math_proofs P83;判据
prereg 载体 = ADR-0603 §4,本文件是其行为面/观测载体面/数值复算面)。

锁清单:
- 豁免支花后下界:支A/ALL IN 双支花后 <10 拒(拒因分键
  ``guarantee_floor_defer``)+ 贴线边界(花后恰 10 过/差 1 拒);
- 出辖三支:终局域 ALL IN 花光原语义(``r_remaining`` 单一源查表判定,
  R 含当前节点 ⇒ 末位面末战帧 R_全局=1)/生存域让位(``p1_blood_floor``,
  真花光唯一合法通道)/买断制 cap=0 出辖(p47 A1 息账消解);
- (3a) 非豁免路径零漂移(拒因键不变)+ s≤0 恒可行;
- 三通道花穿显影:defer 分键与量闸拒键分离 + 买入三臂(M2/E_rev/
  funding)归因词汇在册——合法花穿必须可见,禁洗「钱在卡上」
  (ADR-0603 §4 观测项);
- 档边际数值表复算(kernel interest 单一源递推,T∈{7,9}×Ī∈[6,9]×
  g₀∈{0..50};两种息结算时点口径双覆盖,P47 待标定项 ±5 申报见
  用例 docstring)。

变异打红:下界移除(``_guarantee_floor_holds`` 尾行短路恒真)→ 本文件
豁免支行为锁红(已亲跑验证);还原后全绿。
锁结构/回显,不锁分布数值(sr-od-test README 第 11 条)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_game_state import (
    board_state_bridge as _bsb,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    LevelUpShop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    levelup as crit_levelup,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from test.sr_od.app.currency_war._cw_helpers import (
    battle_state as _state,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bs,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_comp as _comp_single_source,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_km as _km_of,
)
from test.sr_od.app.currency_war._cw_helpers import (
    ns_session as _ns_session,
)

_COMP = '列车同行'


def _comp():
    """本文件锚定具名套(``列车同行``;血线族三文件共用锚)。"""
    return _comp_single_source(_COMP)


def _km() -> list[str]:
    return _km_of(_comp())


def _sess():
    return _ns_session(_comp())


def _support_shapes():
    """支A 形态(板满 ∧ bench 2★ 等待件;谓词本体零改动,ADR-0576 锚对)。"""
    km = _km()
    deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km)]
    bench = [_bc('阮·梅', star=2, slot=1)]
    return km, bench, deployed


class TestGuaranteeFloorExemptionBranches:
    """豁免支花后下界(ADR-0603;域③ P83 ⇒ 息通道非退化判等式)。"""

    def test_support_a_below_floor_deferred(self):
        """支A 兑现链就绪但花后 <10:整批推迟,拒因分键
        guarantee_floor_defer(0 金过位面的豁免支通道闭死)。"""
        km, bench, deployed = _support_shapes()
        st = _state(12, 4, bench=bench, deployed=deployed)
        assert crit_levelup._realize_chain_ready(_bsb(st), bench, deployed)
        ok, why = crit_levelup.levelup_budget_gate(
            _bsb(st), None, 12, 5, tuple(km), bench, deployed, 2, 4)
        assert ok is False
        assert why == 'guarantee_floor_defer'

    def test_support_a_boundary_exact_floor_passes(self):
        """贴线边界:花后恰 = 10(1 息档)⇒ 放行;差 1 金 ⇒ 拒
        (下界贴线敏感,变异「下界移除」在本对上翻红)。"""
        km, bench, deployed = _support_shapes()
        st_ok = _state(18, 4, bench=bench, deployed=deployed)   # 18−8=10
        ok, why = crit_levelup.levelup_budget_gate(
            _bsb(st_ok), None, 18, 5, tuple(km), bench, deployed, 2, 4)
        assert ok is True and why == ''
        st_no = _state(17, 4, bench=bench, deployed=deployed)   # 17−8=9
        ok2, why2 = crit_levelup.levelup_budget_gate(
            _bsb(st_no), None, 17, 5, tuple(km), bench, deployed, 2, 4)
        assert ok2 is False and why2 == 'guarantee_floor_defer'

    def test_all_in_nonterminal_below_floor_deferred(self):
        """非末位面位面末 boss 帧 ALL IN 花后 <10:推迟(原「花光放行」
        语义被本门收窄——P2 r7 形,同一场景在旧 ALL IN 锁中曾放行,
        锁重推记录见 test_cw_budget_gate.TestAllInExempt docstring)。"""
        km = tuple(_km())
        st_boss = _state(45, 7, xp=(48, 52))
        st_boss.plane = 2
        st_boss.node_type = 'boss'
        st_boss.round_num = 7
        sess_p2 = SimpleNamespace(plane_node_table=list(range(7)))
        ok, why = crit_levelup.levelup_budget_gate(
            _bsb(st_boss), sess_p2, 45, 5, km, [], [], 10, 4)
        assert ok is False and why == 'guarantee_floor_defer'

    def test_all_in_nonterminal_at_floor_passes(self):
        """同帧花后 ≥10:ALL IN 豁免维持(花至下界合法,不是禁花)。"""
        km = tuple(_km())
        st_boss = _state(55, 7, xp=(48, 52))
        st_boss.plane = 2
        st_boss.node_type = 'boss'
        st_boss.round_num = 7
        sess_p2 = SimpleNamespace(plane_node_table=list(range(7)))
        ok, why = crit_levelup.levelup_budget_gate(
            _bsb(st_boss), sess_p2, 55, 5, km, [], [], 10, 4)
        assert ok is True and why == ''


class TestGuaranteeFloorOutOfScope:
    """出辖三支(让位语义各有在册出处;ADR-0603 §3)。"""

    def _p3_boss(self, gold: int):
        st = _state(gold, 7, xp=(48, 52))
        st.plane = 3
        st.node_type = 'boss'
        st.round_num = 9
        return st

    def test_terminal_zone_allin_keeps_full_spend(self):
        """终局域(末位面末战,R_全局=1):域③前提失效,ALL IN 维持
        花光原语义(花后 5 <10 仍放行;r_remaining 单一源查表判定)。"""
        km = tuple(_km())
        sess_p3 = SimpleNamespace(plane_node_table=list(range(9)),
                                  plane_lengths_seen=[9, 7, 9])
        ok, why = crit_levelup.levelup_budget_gate(
            _bsb(self._p3_boss(45)), sess_p3, 45, 5, km, [], [], 10, 4)
        assert ok is True and why == ''

    def test_nonterminal_plane_end_still_gated(self):
        """对照:P1 boss(非末位面,R_全局=17)同参花后 <10 ⇒ 照拦
        ——终局域判定是位面感知的,非「boss 帧一律放行」。"""
        km = tuple(_km())
        st_p1 = _state(45, 7, xp=(48, 52))
        st_p1.plane = 1
        st_p1.node_type = 'boss'
        st_p1.round_num = 9
        sess = SimpleNamespace(plane_node_table=list(range(9)),
                               plane_lengths_seen=[9, 7, 9])
        ok, why = crit_levelup.levelup_budget_gate(
            _bsb(st_p1), sess, 45, 5, km, [], [], 10, 4)
        assert ok is False and why == 'guarantee_floor_defer'

    def test_blood_floor_support_a_yields(self):
        """生存域(支A 形态 hp=10 ≤15,P1):本门让位——死亡带转化优先,
        真花光唯一合法通道(p1_blood_floor 在册授权)。"""
        km, bench, deployed = _support_shapes()
        st = _state(12, 4, hp=10, bench=bench, deployed=deployed)
        st.plane = 1
        st.hp_readable = True
        ok, why = crit_levelup.levelup_budget_gate(
            _bsb(st), None, 12, 5, tuple(km), bench, deployed, 2, 4)
        assert ok is True and why == ''

    def test_blood_floor_allin_band_yields(self):
        """生存域(ALL IN 形态 hp=13∈(11,15] 血线带,P1 boss):T-165
        类别过滤不命中(13>停升级线 ≈11)⇒ 到保底门 ⇒ 血线让位放行
        (花后 5 <10)——「真花光必须经生存域」的通道核验。"""
        km = tuple(_km())
        st = _state(45, 7, xp=(48, 52), hp=13)
        st.plane = 1
        st.node_type = 'boss'
        st.round_num = 9
        st.hp_readable = True
        sess = SimpleNamespace(plane_node_table=list(range(9)),
                               plane_lengths_seen=[9, 7, 9])
        ok, why = crit_levelup.levelup_budget_gate(
            _bsb(st), sess, 45, 5, km, [], [], 10, 4)
        assert ok is True and why == ''

    def test_buyout_cap_zero_out_of_scope(self):
        """买断制(cap_resolved=0):息账整体消解(p47 A1),下界失去
        推导基座 ⇒ 出辖(花后 4 <10 仍放行,金出口归一般判据)。"""
        km, bench, deployed = _support_shapes()
        st = _state(12, 4, bench=bench, deployed=deployed)
        ok, why = crit_levelup.levelup_budget_gate(
            _bsb(st), None, 12, 0, tuple(km), bench, deployed, 2, 4)
        assert ok is True and why == ''


class TestNonExemptPathZeroDrift:
    """(3a) 非豁免路径零漂移 + s≤0(ADR-0603 §4 判据 #5 行为面)。"""

    def test_73002_form_reject_key_unchanged(self):
        """73002 同参复刻(g=82 批 72 金):仍走 (3a) 量闸拒,键 =
        levelup_budget_gate_blocked(非 defer)——本门只辖豁免支。"""
        st = _state(82, 8, xp=(12, 72))
        ok, why = crit_levelup.levelup_budget_gate(
            _bsb(st), None, 82, 5, tuple(_km()), [], [], 18, 4)
        assert ok is False
        assert why == 'levelup_budget_gate_blocked'

    def test_zero_batch_passes(self):
        """s ≤ 0(无批可发)恒可行:闸辖「升级支出的量」,不制造支出。"""
        st = _state(10, 3)
        ok, why = crit_levelup.levelup_budget_gate(
            _bsb(st), None, 10, 5, tuple(_km()), [], [], 0, 4)
        assert ok is True and why == ''


class TestChannelAttribution:
    """三通道花穿显影(ADR-0603 §4 观测项;禁洗「钱在卡上」)。

    defer/blocked 两键分离断言已删(同文件 test_support_a_below_floor_
    deferred 与 test_73002_form_reject_key_unchanged 各自同参同键,
    分离事实由两条相等断言合取承载)。"""

    def test_buy_arm_attribution_vocabulary_registered(self):
        """三条合法花穿通道的归因分键词汇在册(观测载体锁;sim/checks
        在禁碰面,显影词汇登记于此):M2 线成员义务(骨架义务不走息律
        门,01 §3.1)/E_rev 豁免臂(P46 支出否决域)/funding 兜底
        (P78-5)——买入通道出口金 <10 局占比可按臂分列。本锁辖
        他文件登记门未及的两面:m2 义务值、funding 通道在册;
        ev_buy→press 全量映射闭集单一源 =
        test_cw_sell_window_launch.test_launch_cause_mapping_closed_
        contract(登记门),funding_hold_fallback 行为面 = 同文件
        TestFundingHoldFallback,两处此处不重复。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            sell_gate,
        )
        assert sell_gate.launch_cause_of('m2_line_member') == 'obligation'
        assert 'funding' in sell_gate.SELL_CHANNELS


class TestMustSpendForwarding:
    """必花域发射位新拒因转发(ADR-0603 §3 落地审中-1 修复):shop
    必花域 L3 位对 guarantee_floor_defer 加 must_spend_guarantee_floor_
    defer 独立分键——域内 XP 花穿推迟与 (3a) 量闸拒归因分离,禁混键
    (mandate prep/entry 位原键转发,本位例外已补)。"""

    def test_zone_guarantee_floor_defer_forwards_dedicated_key(self):
        """域内帧(锁线 g=60>g*)支A 形态大批次(lv7 批 52 金,花后
        8 <10)⇒ 闸拒经必花域位转发为 must_spend_guarantee_floor_defer
        (非 budget_gate_must_spend_defer),零 LevelUpShop。"""
        km = _km()
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km)]
        deployed += [_bc(f'垫{j}', star=2, slot=len(km) + j + 1)
                     for j in range(7 - len(km))]
        bench = [_bc('阮·梅', star=2, slot=1)]
        st = _state(60, 7, xp=(0, 52), bench=bench, deployed=deployed)
        assert crit_levelup._realize_chain_ready(_bsb(st), bench, deployed)
        sess = SimpleNamespace(cw4_counters={}, target_comp=_comp(),
                               v3_intention=SimpleNamespace(
                                   locked_comp=_COMP),
                               active_strategies=[])
        act = shop.decide_shop_action(cw4_bs(st, sess), sess,
                                      SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, LevelUpShop)
        counters = state_of(sess).cw4_counters
        assert counters.get('must_spend_guarantee_floor_defer') == 1
        assert 'budget_gate_must_spend_defer' not in counters

    def test_zone_budget_gate_reject_key_unchanged(self):
        """对照:域内 (3a) 量闸拒(非豁免支)仍计 budget_gate_must_spend_
        defer(既有键不迁移,两键分离可归因)。"""
        st = _state(65, 5, xp=(0, 20))
        sess = SimpleNamespace(cw4_counters={}, target_comp=_comp(),
                               v3_intention=SimpleNamespace(
                                   locked_comp=_COMP),
                               active_strategies=[])
        act = shop.decide_shop_action(cw4_bs(st, sess), sess,
                                      SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, LevelUpShop)
        counters = state_of(sess).cw4_counters
        assert counters.get('budget_gate_must_spend_defer') == 1
        assert 'must_spend_guarantee_floor_defer' not in counters


class TestBandMarginRecalc:
    """档边际数值表复算(ADR-0603 §3 推导摘要数值面;P47 命题一
    规范递推,kernel interest 单一源直调)。"""

    @staticmethod
    def _total_interest(g0: int, income: int, rounds: int, cap: int,
                        timing: str) -> int:
        """下位面总息 V(g₀):g' = min(g + Ī + interest(base), 10×cap)。
        timing='pre' = 轮初口径(interest 按轮初金 g 计,方案 §1.3 规范
        递推);timing='post' = 收入后口径(base = g+Ī 夹帽)。"""

        def _interest(base: int) -> int:
            from sr_od.application.currency_war.kernel.cw_economy import (
                interest,
            )
            return interest(min(base, 10 * cap), cap)

        g, total = g0, 0
        for _ in range(rounds):
            base = g if timing == 'pre' else g + income
            step = _interest(base)
            total += step
            g = min(g + income + step, 10 * cap)
        return total

    def test_band1_margin_pre_timing_in_band(self):
        """轮初口径(规范递推,T∈{7,9}×Ī∈[6,9]×g₀∈{0..50}):
        第一档边际 V(10)−V(0) ∈ [6,10] 且轨迹单调不减(V 非降)。
        **实现批勘误(方案 §1.3/§5-A1 声明修正,2026-09-09)**:方案
        曾声称「band1 ∈ 全档最大(并列允许,Ī∈[6,9] 网格核验)」——
        复算反例 Ī=8(T∈{7,9}):band2=8 > band1=6,该声明不成立为
        全网格定理;本门 B=10 的承重不受影响(承重 = 首息非退化判等式
        +最小绑定支配论证,方案 §1.3 第二/四步;「第一档价值最大」系
        叙述面,两度降格如实记录:方案 §5-A1 一次、本批复核二次)。
        实测 T=7 pre:Ī=6..9 → band1 = 10/6/6/9。"""
        for rounds in (7, 9):
            for income in range(6, 10):
                v = [self._total_interest(g0, income, rounds, 5, 'pre')
                     for g0 in range(0, 51, 10)]
                margins = [v[i + 1] - v[i] for i in range(len(v) - 1)]
                assert 6 <= margins[0] <= 10, (rounds, income, margins)
                assert all(m >= 0 for m in margins), \
                    (rounds, income, margins)

    def test_band1_margin_post_timing_shift_declared(self):
        """收入后口径(时点翻转对照,P47 待标定「息结算时点 ±5 金」):
        band1 ∈ [1,15](= [6,10] ± 申报漂移带,方案 §1.6 口径申报)
        且 V 轨迹单调不减在两口径下均成立——口径翻转时网格重核的挂账
        位(R1 低4)。实测 T=7 post:Ī=6..9 → band1 = 9/5/5/6。"""
        for rounds in (7, 9):
            for income in range(6, 10):
                v = [self._total_interest(g0, income, rounds, 5, 'post')
                     for g0 in range(0, 51, 10)]
                margins = [v[i + 1] - v[i] for i in range(len(v) - 1)]
                assert 1 <= margins[0] <= 15, (rounds, income, margins)
                assert all(m >= 0 for m in margins), \
                    (rounds, income, margins)
