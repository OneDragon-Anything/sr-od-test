"""合成素材拒入守卫(G-S1)锁:单帧锁×4通道 / 单一源 grep 锁 /
P60 收敛性质保持锁 / 两局案发帧回放锁。

出处(锁纪律:新锁必引设计出处)= ADR-0558(合成素材拒入守卫,与部署侧
``cw_deploy_logic.merge_material_guard`` 同键单一源):bench 四卖出
通道(M4 燃料 / 凑息卖 / 支付变现 / 换线塌缩)原资格谓词不读场上
(deployed∪bench)同名同星计数,2/3 合成进度素材与普通垫件在判据层
不可区分而被卖断。案发局:g_20260906_081836 P2r1 resume(卡芙卡,
bench 1★ + 板上 1★ 并存被 2g 卖断)/ g_20260906_095111 P2r1 hp7
濒死帧(藿藿,bench_idx=1 卖 +1g)。

判据:c_excl = same_star_count(name, 1, bench∪deployed) − 1 ≥ 1
⇒ 拒入资格集,拒因键 merge_material_guard;守卫生效域恒为 c_excl=1
(同名同星满 3 即自动升星,c_excl≥2 稳态不可达,merge_mechanics.md
§1/§2)。

分期声明(G1-only):守卫只护不增值——素材滞留 bench 是该期预期形态;
「2★ 合成完成数↑」不作本期验收判据(归 G-B1 二期)。G-S2 翻转比较式
不在本批:W_2★ 无在册标定来源 ⇒ 比较式无载 fail-closed 不卖
(PREREG 申报:G-S2 落地前守卫恒拦,禁无 CI 值静默进闸门,P41 五门
先例同构)。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    k_empty_window_fallback,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    bench_char_cost,
    merge_material_reject_reason,
    sell_refund,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
    provisional,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    sell as crit_sell,
)

_REPO = Path(__file__).resolve().parents[5]   # 仓库根(currency_war←app←sr_od←test←sr-od-test←根)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _state(bench: list[BenchChar], deployed: list[BenchChar],
           plane: int = 2) -> GameState:
    """案发帧形态:P2+(K 空窗回退带)、血线之上(凑息禁令不触发)。"""
    st = GameState()
    st.plane = plane
    st.hp = 50
    st.bench = list(bench)
    st.deployed = list(deployed)
    return st


def _fallback_k(state: GameState) -> tuple[str, ...]:
    """案发帧真实 k_members(K 空窗回退非空集,R2-1):禁用 k_members=()
    假设构造——派生单一源 = cw_intention.k_empty_window_fallback P2+
    带(FALLBACK_COMP_NAME 采购集)。"""
    k, token = k_empty_window_fallback(state, IntentionState())
    assert token == 'p2plus'
    return tuple(sorted(k))


# ===== 守卫谓词本体(单帧语义)=====

class TestGuardPredicate:
    """c_excl 判据语义(含自身全场域计数再扣自身)。"""

    def test_reject_when_pair_exists(self):
        # 案发形态:bench 1★ + 板上 1★ 并存 = 2/3 进度素材
        assert merge_material_reject_reason(
            '卡芙卡', 1, [_bc('卡芙卡', slot=1)],
            [_bc('卡芙卡')]) == 'merge_material_guard'

    def test_allow_single_copy(self):
        # 对照:全场仅自身一份 ⇒ c_excl=0 可卖(守卫零误伤垫件)
        assert merge_material_reject_reason(
            '燃料A', 1, [_bc('燃料A', slot=1)], []) == ''

    def test_allow_star2_out_of_scope(self):
        # 辖域:守卫只辖 1★(升星链语义不在辖域;2★ 成件全场唯一)
        assert merge_material_reject_reason(
            '卡芙卡', 2, [_bc('卡芙卡', star=2, slot=1)],
            [_bc('卡芙卡', star=2)]) == ''

    def test_counts_across_both_domains(self):
        # 副本在 bench 域另一槽同样命中(全场域计数,非只看 deployed)
        bench = [_bc('藿藿', slot=1), _bc('藿藿', slot=2)]
        assert merge_material_reject_reason(
            '藿藿', 1, bench, []) == 'merge_material_guard'


# ===== 锁1:五发射位拒入 + 对照帧零漂移 =====

class TestGuardBlocksAllSellChannels:
    """锁1:四通道 + 换线帧——素材入候选集必拦;对照帧(无同名副本)
    行为零漂移(守卫只加过滤,不改序、不改既有资格谓词)。"""

    # 案发帧泛化形:bench 素材 + 一张普通垫件;deployed 同名素材
    BENCH = [_bc('卡芙卡', slot=1), _bc('燃料A', slot=2)]
    DEPLOYED = [_bc('卡芙卡')]
    K = ('线内件',)

    def test_m4_fuel_candidates_exclude_material(self):
        st = _state(self.BENCH, self.DEPLOYED)
        cands = mandate.fuel_sell_candidates(self.BENCH, self.K, state=st)
        assert [b.slot for b in cands] == [2]      # 仅普通垫件入燃料集

    def test_sell_for_interest_excludes_material(self):
        st = _state(self.BENCH, self.DEPLOYED)
        ct: dict = {}
        slots, key = crit_sell.sell_for_interest(
            44, self.BENCH, 5, self.K, state=st, counters=ct)
        assert key == '' and 1 not in slots        # 素材不入凑息卖回集
        assert ct['merge_material_guard_blocked'] == 1   # 拒因同键计数显影

    def test_funding_support_sell_excludes_material(self):
        st = _state(self.BENCH, self.DEPLOYED)
        ct: dict = {}
        slots, key = crit_sell.funding_support_sell(
            0, 4, self.BENCH, self.K, state=st, counters=ct)
        assert key == '' and 1 not in slots
        assert ct['merge_material_guard_blocked'] == 1

    def test_line_switch_sell_excludes_material(self):
        # 换线帧语境:k_switched ∧ 旧线含素材 ∧ 新线不含——注入态保守
        # 子集(1★ 全额可退)本会放行卡芙卡,守卫照拦(B-1:换线不豁免)
        st = _state(self.BENCH, self.DEPLOYED)
        provisional.inject('U_X', provisional.CalibValue(
            value=1.0, injected_form=True))
        provisional.inject('V_MS', provisional.CalibValue(
            value=1.0, injected_form=True))
        try:
            slots, key = crit_sell.line_switch_sell(
                ('卡芙卡', '燃料A'), self.K, self.BENCH, self.DEPLOYED,
                st, k_switched=True)
        finally:
            provisional.reset('U_X')
            provisional.reset('V_MS')
        assert key == '' and slots == [2]          # 仅垫件入塌缩集

    def test_control_frame_zero_drift(self):
        """对照帧(场上无同名副本):守卫不改变任何通道输出(零漂移)。"""
        bench = [_bc('卡芙卡', slot=1), _bc('燃料A', slot=2)]
        st = _state(bench, [_bc('万敌')])
        # M4:两张都入燃料集,序不变(slot 升序)
        cands = mandate.fuel_sell_candidates(bench, self.K, state=st)
        assert [b.slot for b in cands] == [1, 2]
        # 凑息:缺口 6 → 恰卖两张(与守卫前语义逐字节同)
        slots, key = crit_sell.sell_for_interest(
            44, bench, 5, self.K, state=st)
        assert key == '' and slots == [1, 2]
        # 支付变现:同资格序 (star, slot)
        fslots, fkey = crit_sell.funding_support_sell(
            0, 7, bench, self.K, state=st)
        assert fkey == '' and fslots == [1, 2]
        # 换线塌缩:旧线两件全卖(注入态保守子集语义不变)
        provisional.inject('U_X', provisional.CalibValue(
            value=1.0, injected_form=True))
        provisional.inject('V_MS', provisional.CalibValue(
            value=1.0, injected_form=True))
        try:
            lslots, lkey = crit_sell.line_switch_sell(
                ('卡芙卡', '燃料A'), self.K, bench,
                [_bc('万敌')], st, k_switched=True)
        finally:
            provisional.reset('U_X')
            provisional.reset('V_MS')
        assert lkey == '' and lslots == [1, 2]


# ===== 锁2:单一源 grep 锁 =====

class TestSingleSourceLock:
    """锁2:素材子谓词单一定义点 + 各发射位各自引用(R2-6:共享的是
    子谓词,非整段资格谓词——各通道原资格谓词不动,禁整段谓词上提
    共享给 line_switch 改变现行行为)。"""

    GUARD_DEF = 'def merge_material_reject_reason'

    def _src(self, rel: str) -> str:
        return (_REPO / rel).read_text(encoding='utf-8')

    def test_single_definition_point(self):
        kernel = self._src('src/sr_od/application/currency_war/kernel/cw_state.py')
        assert kernel.count(self.GUARD_DEF) == 1

    def test_each_emission_site_calls_guard(self):
        mandate_src = self._src(
            'src/sr_od/application/currency_war/strategies/impl/mandate_v1'
            '/mandate.py')
        sell_src = self._src(
            'src/sr_od/application/currency_war/strategies/impl/mandate_v1'
            '/criteria/sell.py')
        # M4 燃料通道(mandate.fuel_sell_candidates 函数体内)
        fn = mandate_src.split('def fuel_sell_candidates', 1)[1]
        assert 'merge_material_reject_reason(' in fn.split('\ndef ', 1)[0]
        # 凑息/支付/换线三通道(criteria/sell.py 各函数体内)
        for fn_name in ('line_switch_sell', 'sell_for_interest',
                        'funding_support_sell'):
            body = sell_src.split(f'def {fn_name}', 1)[1]
            assert 'merge_material_reject_reason(' in body.split('\ndef ', 1)[0]

    def test_no_hand_rolled_counter_outside_single_source(self):
        """守卫消费点禁手搓 same_star_count 同式(same_star_count
        docstring 明令;全 mandate_v1 策略层禁新增直接调用)。"""
        for rel in ('src/sr_od/application/currency_war/strategies/impl'
                    '/mandate_v1/mandate.py',
                    'src/sr_od/application/currency_war/strategies/impl'
                    '/mandate_v1/criteria/sell.py'):
            assert 'same_star_count(' not in self._src(rel)


# ===== 锁3:P60 收敛性质保持锁 =====

class TestP60ConvergencePropertyPreserved:
    """锁3:P60 现有性质「排除后 Fuel∩B=∅ ⇒ 换手收敛 Φ=|owned∩B|
    单调不减」在新守卫下保持——守卫只扩大排除集(候选集单调收缩),
    收敛证明的辖域前提不弱化。推理边界(锁语):守卫只护 bench 侧,
    deployed 侧 swap 路径存在不经过 merge_material_guard 的出口
    (cw_deploy_logic offtarget_sell_allowed 放行早退先于守卫)——
    本批声明 accepted loss:deployed 副本经该出口被卖则 c_excl 归 0,
    bench 守卫下帧放行,素材保护实际强度 = 两侧保护窗交集、退化形态
    = 延迟一帧;deployed 侧同辖收口归 cw_launch_admission 决策下沉面
    另批,不在本批辖域。"""

    def test_guard_only_shrinks_candidate_set(self, monkeypatch):
        bench = [_bc('卡芙卡', slot=1), _bc('燃料A', slot=2),
                 _bc('燃料B', slot=3)]
        st = _state(bench, [_bc('卡芙卡')])
        guarded = [b.slot for b in mandate.fuel_sell_candidates(
            bench, (), state=st)]
        # 拔掉守卫(模拟守卫删除):候选集只能变大
        monkeypatch.setattr(mandate, 'merge_material_reject_reason',
                            lambda *a, **k: '')
        unguarded = [b.slot for b in mandate.fuel_sell_candidates(
            bench, (), state=st)]
        assert set(guarded) <= set(unguarded)
        assert 1 in unguarded and 1 not in guarded


# ===== 锁4′:P56 活期投影第五消费面(F-2 显式钉方向)=====

class TestP56LiquidProjectionFace:
    """F-2 申报锁:fuel_sell_candidates 同时是 P56 活期投影单一源
    (s_reserve := g* − Σ活期退金投影,dd-032)——守卫使投影收缩:
    素材在场帧 liquid_refund 不含素材退款 ⇒ s_reserve↑ ⇒ 买面判据
    变保守。方向正确(投影口径 = 可执行卖出集,守卫后更真),锁其
    显式性防后人把收缩误读为回归。"""

    def test_liquid_refund_excludes_material(self):
        bench = [_bc('卡芙卡', slot=1), _bc('燃料A', slot=2)]

        def _liquid(b: list[BenchChar], deployed: list[BenchChar]) -> int:
            st2 = _state(b, deployed)
            return sum(sell_refund(1, bench_char_cost(x))
                       for x in mandate.fuel_sell_candidates(
                           b, (), state=st2))

        assert _liquid(bench, [_bc('卡芙卡')]) == 3    # 仅垫件入投影
        assert _liquid(bench, [_bc('万敌')]) == 5      # 无守卫帧两张全入(2+3)


# ===== 锁4:两局案发帧回放锁(离线构造,档案口径)=====

class TestReplayCaseFrames:
    """锁4:二十四局(卡芙卡)/ 三十局(藿藿)P2r1 案发帧注入离线决策,
    断言 SellBench 不再指向素材件。案发帧 k_members = K 空窗回退后的
    非空集(R2-1:禁 k_members=() 假设构造,否则测的不是案发机制)
    ——经单一源 k_empty_window_fallback P2+ 带派生。"""

    def test_game24_kafka_p2r1_no_material_sell(self):
        # 案发局 g_20260906_081836 P2r1 resume:bench 卡芙卡 1★ +
        # 板上卡芙卡 1★ 并存(复盘逐节点表「板上卡芙卡+bench 卡芙卡
        # 应合成 2★」帧);tgt 空 → K 空窗回退集,卡芙卡不在集内。
        bench = [_bc('卡芙卡', slot=1)]
        deployed = [_bc('卡芙卡', slot=1), _bc('砂金', slot=2),
                    _bc('椒丘', slot=3)]
        st = _state(bench, deployed)
        k = _fallback_k(st)
        assert k and '卡芙卡' not in k
        assert mandate.fuel_sell_candidates(bench, k, state=st) == []
        slots, _ = crit_sell.sell_for_interest(44, bench, 5, k, state=st)
        assert slots == []
        fslots, _ = crit_sell.funding_support_sell(0, 9, bench, k, state=st)
        assert fslots == []

    def test_game30_huohuo_p2r1_no_material_sell(self):
        # 案发局 g_20260906_095111 P2r1(档案 match_g_20260906_095111
        # .json rounds plane=2 round=1 直读):bench=[藿藿1★ slot2],
        # deployed 含藿藿 1★(P1r3 首买)+ 六件;案发动作 = SellBench
        # bench_idx=1 藿藿 +1g。K 空窗回退集(p2plus)不含藿藿。
        bench = [_bc('藿藿', slot=2)]
        deployed = [_bc('椒丘', star=2, slot=1),
                    _bc('丹恒·饮月', slot=2),
                    _bc('灵砂', slot=3),
                    _bc('藿藿', slot=1),
                    _bc('爻光', slot=2),
                    _bc('远坂凛', star=2, slot=3),
                    _bc('刻律德菈', slot=4)]
        st = _state(bench, deployed)
        k = _fallback_k(st)
        assert k and '藿藿' not in k
        assert mandate.fuel_sell_candidates(bench, k, state=st) == []
        slots, _ = crit_sell.sell_for_interest(24, bench, 5, k, state=st)
        assert slots == []                          # 不再指向 bench_idx=1
        # F-1 修正:gold < need_gold 才真辖资格循环(gold=24 ≥ need=4
        # 会走 'not_needed' 早退,断言空转不辖守卫语义)
        fslots, fkey = crit_sell.funding_support_sell(2, 9, bench, k, state=st)
        assert fkey == '' and fslots == []

    def test_replay_control_frame_still_sells_fodder(self):
        """回放对照:同一局形态去掉 deployed 同名副本(藿藿未首买的
        反事实帧)——垫件照常可卖,守卫未扩大到误伤普通件。"""
        bench = [_bc('藿藿', slot=2)]
        deployed = [_bc('椒丘', star=2, slot=1),
                    _bc('丹恒·饮月', slot=2),
                    _bc('灵砂', slot=3)]
        st = _state(bench, deployed)
        k = _fallback_k(st)
        assert [b.slot for b in mandate.fuel_sell_candidates(
            bench, k, state=st)] == [2]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
