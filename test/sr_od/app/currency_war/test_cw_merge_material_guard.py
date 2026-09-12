"""合成素材拒入守卫(G-S1)锁:守卫谓词单帧语义 / 四通道拒入+对照
零漂移 / 单一源守卫(grep+墓碑)/ 案发帧回放 / 滞留显影分键 /
拦截事件口径+接线。

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

from sr_od.application.currency_war.kernel.cw_game_state import (
    board_state_bridge,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    k_empty_window_fallback,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BenchChar,
    CwWorkFrame,
    merge_material_reject_reason,
    merge_material_stale_names,
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
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    count_material_stale,
)

_REPO = Path(__file__).resolve().parents[5]   # 仓库根(currency_war←app←sr_od←test←sr-od-test←根)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _state(bench: list[BenchChar], deployed: list[BenchChar],
           plane: int = 2) -> CwWorkFrame:
    """案发帧形态:P2+(K 空窗回退带)、血线之上(凑息禁令不触发)。"""
    st = CwWorkFrame()
    st.plane = plane
    st.hp = 50
    st.bench = list(bench)
    st.deployed = list(deployed)
    return st


def _fallback_k(state: CwWorkFrame) -> tuple[str, ...]:
    """案发帧真实 k_members——派生单一源 = cw_intention.k_empty_window_
    fallback P2+ 带。P86 落码批重推(证明批 §4.6:p2plus 空集合法):
    回退 = 三臂判据输出,本判死帧(机器门全灭)产**合法空集**(丙臂守息
    帧)——原 R2-1「禁 k_members=() 假设构造」禁的是无出处的假设,现在
    的空集是单一源评估真值,且让守卫锁更锐:zero_overlap 对空集全放,
    燃料候选唯一拦截 = merge 守卫本体。"""
    # W6 波3:k 空窗回退已切容器签名,帧经过渡桥装箱。
    k, token = k_empty_window_fallback(board_state_bridge(state),
                                       IntentionState())
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
    """锁2:素材子谓词单一定义点 + 消费点禁手搓同式(R2-6:共享的是
    子谓词,非整段资格谓词——各通道原资格谓词不动,禁整段谓词上提
    共享给 line_switch 改变现行行为)。四发射位的守卫接线由锁1 各通道
    行为锁覆盖(守卫调用脱落即红),不再保留重复的函数体 grep 烟雾;
    唯一无行为覆盖的接线点 = entry.py EV pass 传参,由锁6 的
    test_line_switch_wiring_in_entry_pass 单点看守。"""

    GUARD_DEF = 'def merge_material_reject_reason'

    def _src(self, rel: str) -> str:
        return (_REPO / rel).read_text(encoding='utf-8')

    def test_single_definition_point(self):
        kernel = self._src('src/sr_od/application/currency_war/kernel/cw_state.py')
        assert kernel.count(self.GUARD_DEF) == 1

    def test_no_hand_rolled_counter_outside_single_source(self):
        """守卫消费点禁手搓 same_star_count 同式(same_star_count
        docstring 明令;全 mandate_v1 策略层禁新增直接调用)。"""
        for rel in ('src/sr_od/application/currency_war/strategies/impl'
                    '/mandate_v1/mandate.py',
                    'src/sr_od/application/currency_war/strategies/impl'
                    '/mandate_v1/criteria/sell.py'):
            assert 'same_star_count(' not in self._src(rel)


# 删测注记(瘦身批):原「锁3 P60 收敛性质保持锁」与「锁4′ P56 投影面」
# 两类已删——P60 锁的断言面(守卫拔除对照)不辖其声明的收敛故障,且
# 素材拒入断言与锁1 重复,accepted-loss 推理由 ADR-0558「配对一致性」
# 节持久承载;P56 锁以测试体自拼投影表达式,生产投影(shop.py 预算段)
# 绕开守卫时该测不红 = 锁不住声明故障,投影值收缩的 decide 级链路锁
# 缺口记 DEBTS.md D21。

# ===== 锁4:案发帧回放锁(离线构造,档案口径)=====

class TestReplayCaseFrames:
    """锁4:三十局(藿藿)P2r1 案发帧注入离线决策,断言 SellBench 不再
    指向素材件。案发帧 k_members = K 空窗回退后的非空集(R2-1:禁
    k_members=() 假设构造,否则测的不是案发机制)——经单一源
    k_empty_window_fallback P2+ 带派生。二十四局(卡芙卡)回放测与本测
    断言面等价(三通道空 + 素材∉k,亲读对账),择一取超集已并删,
    两局案发对账记录见 ADR-0558。"""

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
        assert '藿藿' not in k   # P86 判死帧:回退合法空集,成员资格零豁免
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


# ===== 锁5:滞留素材显影官方键(ADR-0558 §4 G-B1 第四级)=====

class _SessionStub:
    """决策 session 最小桩:count_material_stale 只挂
    ``cw4_stale_seen_rounds`` 一个属性,普通对象即够(零副作用)。"""


class TestMaterialStaleKeys:
    """锁5:``merge_material_stale`` / ``merge_material_stale_ge2``
    官方分键直跑(取代 sim71 验收批「重复对在场行数」代理口径):
    素材对在场逐决策帧计名×帧;跨轮仍滞留加计轮级显影键;合成/卖出
    后键停止增长(轮差分归零);拆对后再组不误计跨轮(记忆离场即清)。
    纯观测键:断言只涉 counters/session 记忆,零行为面。"""

    def test_stale_names_semantics(self):
        # 判定单一源:同名同 1★ 全场计数 ≥2 才滞留;2★ 不辖;字母序去重
        bench = [_bc('卡芙卡', slot=1), _bc('燃料A', slot=2),
                 _bc('卡芙卡', star=2, slot=3)]
        assert merge_material_stale_names(
            bench, [_bc('卡芙卡')]) == ('卡芙卡',)
        assert merge_material_stale_names(
            [_bc('卡芙卡', slot=1)], [_bc('燃料A')]) == ()
        # bench 域内对同样命中(全场域,与守卫同口径)
        assert merge_material_stale_names(
            [_bc('藿藿', slot=1), _bc('藿藿', slot=2)], []) == ('藿藿',)

    def test_fresh_pair_counts_frame_not_cross_round(self):
        sess = _SessionStub()
        ct: dict = {}
        bench = [_bc('卡芙卡', slot=1), _bc('卡芙卡', slot=2)]
        count_material_stale(ct, sess, bench, [], round_num=4)
        assert ct['merge_material_stale'] == 1
        assert 'merge_material_stale_ge2' not in ct   # 首见帧不记跨轮

    def test_pair_persisting_next_round_counts_ge2(self):
        sess = _SessionStub()
        ct: dict = {}
        bench = [_bc('卡芙卡', slot=1), _bc('卡芙卡', slot=2)]
        count_material_stale(ct, sess, bench, [], round_num=4)
        count_material_stale(ct, sess, bench, [], round_num=4)  # 同轮多帧
        count_material_stale(ct, sess, bench, [], round_num=5)
        # 名×帧口径:轮4 两帧 + 轮5 一帧 = 3;跨轮键只在轮5 记 1
        assert ct['merge_material_stale'] == 3
        assert ct['merge_material_stale_ge2'] == 1

    def test_resolved_pair_stops_and_memory_clears(self):
        """合成/卖出后键停止增长;拆对后再组不误计跨轮(记忆离场即清)
        ——滞留时长 = 键差分判读的口径前提。"""
        sess = _SessionStub()
        ct: dict = {}
        pair = [_bc('卡芙卡', slot=1), _bc('卡芙卡', slot=2)]
        count_material_stale(ct, sess, pair, [], round_num=3)
        count_material_stale(ct, sess, pair, [], round_num=4)
        assert ct['merge_material_stale_ge2'] == 1
        # 轮5 对消失(合成 2★):两键零增长,记忆清
        count_material_stale(ct, sess, [_bc('卡芙卡', star=2, slot=1)],
                             [], round_num=5)
        assert ct['merge_material_stale'] == 2
        assert state_of(sess).cw4_stale_seen_rounds == {}
        # 轮6 重新组对:新滞留段,首见帧不记跨轮(同一 counters 累计)
        count_material_stale(ct, sess, pair, [], round_num=6)
        assert ct['merge_material_stale'] == 3
        assert ct['merge_material_stale_ge2'] == 1   # 未增长

    def test_two_stale_names_count_individually(self):
        sess = _SessionStub()
        ct: dict = {}
        bench = [_bc('卡芙卡', slot=1), _bc('卡芙卡', slot=2),
                 _bc('藿藿', slot=3), _bc('藿藿', slot=4)]
        count_material_stale(ct, sess, bench, [], round_num=2)
        assert ct['merge_material_stale'] == 2        # 名×帧粒度

    def test_single_source_lock_counting_via_names_fn(self):
        """分键判定单一源:count_material_stale 必经
        merge_material_stale_names(禁手搓同式);判定函数在 cw_state
        唯一定义。"""
        import inspect
        src = inspect.getsource(count_material_stale)
        assert 'merge_material_stale_names(' in src
        kernel = (_REPO / 'src/sr_od/application/currency_war/kernel'
                  '/cw_state.py').read_text(encoding='utf-8')
        assert kernel.count('def merge_material_stale_names') == 1


# ===== 锁6:拦截事件口径(C1)+ 换线位接线(D1,三审整改)=====

class TestBlockedKeyEventSemantics:
    """锁6:C1 = ``merge_material_guard_blocked`` 是**拦截事件**计数
    (同帧同素材名只计 1,去重载体 = 帧级 ``dedup_names`` 集,单一源 =
    ``cw_state.count_merge_material_blocked``)——同帧重复评估(P56
    liquid_refund 投影读 + M4 真卖评估、腾席环 while 重试)不得重复 +1;
    D1 = 换线塌缩位拒因分键接线(ADR-0558 §3「全发射位显影」按实装
    口径兑现:本位曾静默 continue 无计数)。"""

    BENCH = [_bc('卡芙卡', slot=1), _bc('燃料A', slot=2)]
    DEPLOYED = [_bc('卡芙卡')]
    K = ('线内件',)

    def test_same_frame_repeat_evaluation_counts_once(self):
        st = _state(self.BENCH, self.DEPLOYED)
        ct: dict = {}
        dedup: set[str] = set()
        # 同帧两次触达:投影读(P56)→ 真卖评估(M4)——事件只计 1
        mandate.fuel_sell_candidates(self.BENCH, self.K, state=st,
                                     counters=ct, dedup_names=dedup)
        mandate.fuel_sell_candidates(self.BENCH, self.K, state=st,
                                     counters=ct, dedup_names=dedup)
        assert ct['merge_material_guard_blocked'] == 1
        # 对照:无去重(旧评估次数口径)= 2,证明去重载体生效
        ct2: dict = {}
        mandate.fuel_sell_candidates(self.BENCH, self.K, state=st,
                                     counters=ct2)
        mandate.fuel_sell_candidates(self.BENCH, self.K, state=st,
                                     counters=ct2)
        assert ct2['merge_material_guard_blocked'] == 2

    def test_event_semantics_shared_across_channels(self):
        """同帧跨通道共享去重集:M4 触达后凑息/支付/换线同素材不重复计。"""
        st = _state(self.BENCH, self.DEPLOYED)
        ct: dict = {}
        dedup: set[str] = set()
        mandate.fuel_sell_candidates(self.BENCH, self.K, state=st,
                                     counters=ct, dedup_names=dedup)
        crit_sell.sell_for_interest(44, self.BENCH, 5, self.K, state=st,
                                    counters=ct, dedup_names=dedup)
        crit_sell.funding_support_sell(0, 4, self.BENCH, self.K, state=st,
                                       counters=ct, dedup_names=dedup)
        provisional.inject('U_X', provisional.CalibValue(
            value=1.0, injected_form=True))
        provisional.inject('V_MS', provisional.CalibValue(
            value=1.0, injected_form=True))
        try:
            crit_sell.line_switch_sell(
                ('卡芙卡', '燃料A'), self.K, self.BENCH, self.DEPLOYED,
                st, k_switched=True, counters=ct, dedup_names=dedup)
        finally:
            provisional.reset('U_X')
            provisional.reset('V_MS')
        assert ct['merge_material_guard_blocked'] == 1

    def test_line_switch_wiring_counts_blocked(self):
        """D1:换线位拒因分键接线——素材被拒时计数显影(曾静默)。"""
        st = _state(self.BENCH, self.DEPLOYED)
        ct: dict = {}
        provisional.inject('U_X', provisional.CalibValue(
            value=1.0, injected_form=True))
        provisional.inject('V_MS', provisional.CalibValue(
            value=1.0, injected_form=True))
        try:
            slots, key = crit_sell.line_switch_sell(
                ('卡芙卡', '燃料A'), self.K, self.BENCH, self.DEPLOYED,
                st, k_switched=True, counters=ct, dedup_names=set())
        finally:
            provisional.reset('U_X')
            provisional.reset('V_MS')
        assert key == '' and slots == [2]     # 行为零漂移:仅垫件入塌缩集
        assert ct['merge_material_guard_blocked'] == 1   # 拦截事件显影

    def test_line_switch_wiring_in_entry_pass(self):
        """接线锁:EV pass 的换线调用必须传 counters(生产接线位)。"""
        src = (_REPO / 'src/sr_od/application/currency_war/strategies/impl'
               '/mandate_v1/entry.py').read_text(encoding='utf-8')
        call = src.split('crit_sell.line_switch_sell(', 1)[1]
        assert 'counters=counters' in call.split(')', 1)[0]

    def test_count_helper_single_source(self):
        """计数单一源:四通道计数点全部经
        ``count_merge_material_blocked``,kernel 唯一定义。"""
        ksrc = (_REPO / 'src/sr_od/application/currency_war/kernel'
                '/cw_state.py').read_text(encoding='utf-8')
        assert ksrc.count('def count_merge_material_blocked') == 1
        for rel in ('src/sr_od/application/currency_war/strategies/impl'
                    '/mandate_v1/mandate.py',
                    'src/sr_od/application/currency_war/strategies/impl'
                    '/mandate_v1/criteria/sell.py'):
            body = (_REPO / rel).read_text(encoding='utf-8')
            assert 'count_merge_material_blocked(' in body
            # 旧手搓计数式已清(禁双源回潮)
            assert "counters['merge_material_guard_blocked'] =" not in body


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
