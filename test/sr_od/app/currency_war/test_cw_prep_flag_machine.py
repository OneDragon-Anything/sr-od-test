"""备战决策环旗标状态机锁面(T-159;设计出处 = ADR-0596,用户裁定
2026-09-08;猎点编号沿 T-159 方案 v2.1 §4,方案 why 已由 ADR-0596
持久收编)。

三旗标:S1 = 备战期开店闩(cw4_shopped_phase,现行)重置白名单化;
S2 = 商店 wanted 残差旗标(cw4_shop_wanted_pending,新增);
S3 = 升级检查逻辑旗标不立变量(单向上位,本文件墓碑行看守)。

锁面分组(方案 §7.2 轨 1 同号节,ADR-0596 收编;出处列见各 docstring):
1. test_s1_reset_whitelist——S1 清键三路径封闭枚举之 (i)(ii) 逐行
   (§3.3,审 D1);路径 (iii) 消费臂门 1 由同文件 test_s2_lifecycle 的
   test_gate1_reopens_before_legs 承载(断言面并测,不重复立锁);
2. S1 置位纪律(发射不置闩/访问位置闩)由 test_cw_mandate_v1 既有锁
   承载(TestEmit 附近「发射不置闩」与「闩置位=访问位」两断言),本
   文件按锁纪律第 7 条不重复立锁,仅挂指针;
3. test_s2_lifecycle——S2 置位/门 0 镜像/门 1 席空闲先重进/腿序/
   超安全阀/放弃态/节点推进键失配(§5.2 迁移 A);
4. test_route_tag_whitelist——route_tag 映射表逐 tag + 桥透传不丢
   (§3.3 通道载体主案);
5. test_runtools_emit_position——RunTools 发射于 ②③ 之间 + run_mandate
   无 M7.5 块(防双发射)+ 同帧执行序 RunTools 先于 LevelUp(§4 猎点 12
   v2.1 更正口径;闩语义细锁归 test_cw_tools_exec_channel);
6. test_sphere_bench_full_predicate——席满前置谓词(§5.2 迁移 B;
   2026-09-02 席满球裁定 screen_flow_timing #16 覆盖留痕见猎点 13);
7. test_s3_no_variable——不存在独立 S3 变量字段(墓碑,防双源回归)
   + M3 判据纯函数输入翻转(§1.4)。
8. test_wanted_precondition——S2 门 0′ 前件五态(T-161 F2:不在店/
   不可负担 hold 保留、∃在店∧可负担照常开环、late-flip 翻真、节点
   推进过期不变;出处 = ADR-0599 + T161方案审.md §1.2/§1.4/§4)。
9. test_run_deploy_dispatch_landing_is_structural——F1b 落地判定 =
   执行器分派位具名常量结构化比对(真 _run_composite 形态构造,
   防字符串反推复辟;T-167 事故修法)。
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import Comp
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    ClickSpheres,
    LevelUp,
    OpenShop,
    PrepObservation,
    RunDeploy,
    RunEquip,
    RunTools,
    SellBench,
    StartBattle,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    decide_from_turn,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    MandateState,
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates,
)

_PHASE = (1, 3)


def _sess() -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    return s


def _state(plane: int = 1, round_num: int = 3, gold: int = 2,
           ) -> GameState:
    return GameState(plane=plane, round_num=round_num, gold=gold, hp=100)


def _bc(name: str, slot: int, star: int = 1) -> BenchChar:
    """bench 件构造:注册表内名带阵营(部署谓词消费面),未登记名作
    燃料/填充(谓词经注册表缺读异常走保守放行,与生产同判据)。"""
    ch = CHARACTERS.get(name)
    return BenchChar(slot=slot, char_id=name, star=star,
                     faction=(ch.factions or ['?'])[0] if ch else '?')


def _set_s2(sess: StrategySession, state: GameState,
            missing: tuple[str, ...] = ('目标件',),
            in_shop: tuple[tuple[str, int], ...] | None = None) -> None:
    """经生产唯一写点 mandate.shop_wanted_defer 置 S2(禁直写字段:
    供给半环锁面纪律,README 测试纪律 13)。

    T-161 F2 起写点要求在店快照(「在店缺员 (名, 费用)」子集;T-161
    方案审 F2-1/F2-6,ADR-0599):缺省种「缺员在店且可负担」形态
    (名, 1)——cost 1 ≤ 缺省帧 gold 2,前件放行,既有用例聚焦各自
    原锁面。旧用例不种快照时被门 0′ 前件 hold 拦截属预期锁红(方案审
    §3 波及预估),按锁纪律改 helper 种快照,禁绕过前件保绿;前件拦截
    形态的锁面见 TestWantedPrecondition(显式传 in_shop=()/高费用)。
    """
    mandate.shop_wanted_defer(
        sess, state, list(missing),
        in_shop_snapshot=in_shop if in_shop is not None
        else tuple((m, 1) for m in missing if m))


# ===== 1. S1 清键三路径封闭枚举(§3.3,审 D1)=====

class TestS1ResetWhitelist:
    """路径 (i) 白名单 tag 落地 / (ii) S2 在册 ∧ 腾席翻正(任意 tag);
    路径 (iii) 消费臂门 1(臂内提前收敛形态)由同文件
    TestS2Lifecycle.test_gate1_reopens_before_legs 承载(含 wanted_reopen
    记账面),本类不重复立锁。三路径均未命中一律不清;纯金变更永不清
    (B3 裁决唯一绝对项)。写点 = mark_s1_route_check(备战域执行器
    progressed 返回,迁移 D);此处直调写点锁枚举本体,执行器挂钩接线
    由 prep_actions 挂钩位同源消费(生产链单一)。"""

    def _mk(self, s1: bool = True, s2: bool = True):
        sess = _sess()
        st = state_of(sess)
        if s1:
            st.cw4_shopped_phase = _PHASE
        if s2:
            _set_s2(sess, _state())
        return sess, st

    def cleared(self, st: MandateState) -> bool:
        return getattr(st, 'cw4_shopped_phase', None) is None

    def test_i_deploy_launch_landing_clears(self):
        """(i) 部署类:RunDeploy 落地 → 清键,遥测分键
        s1_reset_by_deploy_launch(route 类由动作类型承载,§5.1 M1 行)。"""
        sess, st = self._mk()
        mandate.mark_s1_route_check(sess, _state(), RunDeploy(),
                                    pre_bench_count=9, post_bench_count=8,
                                    landed=True)
        assert self.cleared(st)
        assert st.cw4_counters.get('s1_reset_by_deploy_launch') == 1

    def test_i_deploy_noop_landing_keeps_latch(self):
        """F1b(T-167):RunDeploy progressed 但零落地(landed=False,执行器
        对 STATUS_NOOP 合法稳态的结构化判定)→ 不清闩、零遥测——no-op
        部署清闩 = 凭空再武装一次开店意图,交替活锁引擎本体(事故实证:
        25 次无信息量重开店)。landed 必传(落地审低②:删缺省防静默
        沿用旧「progressed 即落地」口径)。"""
        sess, st = self._mk()
        mandate.mark_s1_route_check(sess, _state(), RunDeploy(),
                                    pre_bench_count=9, post_bench_count=8,
                                    landed=False)
        assert not self.cleared(st), 'no-op RunDeploy 必须保持开店闩(F1b)'
        assert not [k for k in st.cw4_counters
                    if k.startswith('s1_reset_by')], '零落地形态零清键遥测'

    def test_i_m4_fuel_sell_landing_clears(self):
        """(i) 卖出类:m4_fuel_sell 落地 → 清键(腾席臂/wanted 卖腿
        同路线类,§5.2 腿 2)。"""
        sess, st = self._mk()
        act = SellBench(slot=1)
        act.route_tag = 'm4_fuel_sell'
        mandate.mark_s1_route_check(sess, _state(), act,
                                    pre_bench_count=9, post_bench_count=8,
                                    landed=True)
        assert self.cleared(st)
        assert st.cw4_counters.get('s1_reset_by_m4_fuel_sell') == 1

    def test_ii_interest_sell_flip_with_s2_clears(self):
        """(ii) 正例:凑息 tag 落地腾席 ∧ S2 在册 → 清键(义务优先,
        猎点 14;tag 不豁免)。遥测 = bench_flip_<tag> 交叉对账位。"""
        sess, st = self._mk()
        act = SellBench(slot=1)
        act.route_tag = 'interest_prep'
        mandate.mark_s1_route_check(sess, _state(), act,
                                    pre_bench_count=9, post_bench_count=8,
                                    landed=True)
        assert self.cleared(st)
        assert st.cw4_counters.get(
            's1_reset_by_bench_flip_interest_prep') == 1

    def test_ii_interest_sell_flip_without_s2_keeps(self):
        """(ii) 负例:S2 未在册 → 凑息腾席落地不清键(编者③边界:
        凑息不凭自身触发重进,§3.3 B4 段)。"""
        sess, st = self._mk(s2=False)
        act = SellBench(slot=1)
        act.route_tag = 'interest_prep'
        mandate.mark_s1_route_check(sess, _state(), act,
                                    pre_bench_count=9, post_bench_count=8,
                                    landed=True)
        assert not self.cleared(st)
        assert not [k for k in st.cw4_counters
                    if k.startswith('s1_reset_by')]

    def test_ii_interest_sell_without_flip_keeps(self):
        """(ii) 负例:S2 在册但落地未腾席(9→9,纯金型)→ 不清
        (约束未解除,重开无信息量,B3 理由①)。landed=True = 新契约
        (F1b 分派位结构化比对)下卖出类 progressed 即落地——卖出类
        完成验证 = 源槽变,fail-closed 无 no-op success 形态,本负例的
        不清来自席位未翻正,与落地位正交(登记 = ADR-0534「修订
        (T-167)」节 + mark_s1_route_check docstring F1b 段)。"""
        sess, st = self._mk()
        act = SellBench(slot=1)
        act.route_tag = 'interest_prep'
        mandate.mark_s1_route_check(sess, _state(), act,
                                    pre_bench_count=9, post_bench_count=9,
                                    landed=True)
        assert not self.cleared(st)

    def test_ii_untagged_flip_with_s2_clears(self):
        """(ii) 任意 tag 含空标:支付支撑/换线卖(未标 tag)腾席 ∧
        S2 在册 → 清键(封闭枚举不限 tag 词面)。"""
        sess, st = self._mk()
        mandate.mark_s1_route_check(sess, _state(), SellBench(slot=2),
                                    pre_bench_count=9, post_bench_count=8,
                                    landed=True)
        assert self.cleared(st)
        assert st.cw4_counters.get(
            's1_reset_by_bench_flip_untagged') == 1

    def test_pure_gold_change_never_clears(self):
        """纯金变更永不清(B3 唯一绝对项):无席变动落地(S2 在册与
        未在册两形态)均不清——封锁原因是席满,金增多不解除。"""
        for s2 in (True, False):
            sess, st = self._mk(s2=s2)
            mandate.mark_s1_route_check(sess, _state(), LevelUp(),
                                        pre_bench_count=5, post_bench_count=5,
                                        landed=True)
            assert not self.cleared(st), f'S2 在册={s2} 形态被误清'

    def test_latch_of_other_phase_not_touched(self):
        """闩不在本节点(未置/他节点键)时白名单落地零清零遥测——清键
        只消费「本节点闩实清」事件,跨节点零污染(§3.2 键式推论)。"""
        sess, st = self._mk(s1=False)
        mandate.mark_s1_route_check(sess, _state(), RunDeploy(),
                                    pre_bench_count=9, post_bench_count=8,
                                    landed=True)
        assert not [k for k in st.cw4_counters
                    if k.startswith('s1_reset_by')]


# ===== 2. S2 生命周期(§5.2 迁移 A)=====

class TestS2Lifecycle:

    def _comp(self) -> Comp:
        from sr_od.application.currency_war.kernel.cw_comps import (
            COMP_LIBRARY,
        )
        names = [c.name for c in COMP_LIBRARY
                 if getattr(c, 'core_chars', None)]
        return next(c for c in COMP_LIBRARY if c.name == names[0])

    def _members(self, comp: Comp) -> list[str]:
        ms = list(comp.core_chars) + list(getattr(comp, 'shared_chars',
                                                  []) or [])
        return list(dict.fromkeys(ms))

    def test_registration_at_shop_residual(self):
        """置位经生产链:decide_shop_action 席满残差点(m2_retry_exhausted/
        bench_full_buy_abandon 同点,猎点 10)→ S2 = (phase, obligation,
        残差名单, 在店快照) + shop_wanted_deferred 计数。bench 满用 2★
        填充件(非燃料 ⇒ 腾席候选空,诚实停摆形态)。T-161 F2 起 S2 扩
        四元(ADR-0599):快照由写点同帧经 _shop_candidates 同源闭包计算
        (方案审 F2-6),本锁经生产链钉快照内容 = 在店缺员最便宜卡费用。"""
        from types import SimpleNamespace as _NS

        from sr_od.application.currency_war.kernel.cw_state import ShopCard
        comp = self._comp()
        missing = self._members(comp)[0]
        bench = [_bc(f'填充件{i}', slot=i, star=2)
                 for i in range(1, BENCH_CAPACITY + 1)]
        st = _state()
        st.gold = 2
        st.bench = bench
        # 店面播缺员 1★ 卡(cost 2)+ 一张无关卡:快照应只收缺员且取
        # 同名最便宜卡(M2 语义,不滤星)。
        st.shop = [ShopCard(x=1, faction='?', name=missing, cost=2, star=1),
                   ShopCard(x=2, faction='?', name='填充件1', cost=1, star=1)]
        sess = _sess()
        state_of(sess).target_comp = comp
        sess.active_strategies = ['买断制']   # ADR-0598 注入面迁移
        decide_shop_action(st, sess, _NS(ev_arm='skeleton_only'))
        s2 = state_of(sess).cw4_shop_wanted_pending
        assert s2 is not None and s2[0] == (st.plane, st.round_num) \
            and s2[1] == 'obligation' and missing in s2[2], \
            f'席满残差未置 S2:{s2}'
        assert len(s2) == 4, f'S2 载体形态漂移(应为四元):{s2}'
        assert s2[3] == ((missing, 2),), \
            f'在店快照与店面牌面不符(F2-6 同源口径):{s2[3]}'
        assert state_of(sess).cw4_counters.get('shop_wanted_deferred', 0) >= 1

    def test_gate0_missing_satisfied_clears_without_emission(self):
        """门 0(残差有效性镜像):线名单已补齐 → S2 清、零发射(审 B1)。"""
        sess = _sess()
        state = _state()
        _set_s2(sess, state)
        out = mandate.wanted_closure_emit(
            sess, state, [_bc('目标件', 1)], [], 4, 3)
        assert out == []
        assert state_of(sess).cw4_shop_wanted_pending is None

    def test_gate0_stop_line_clears(self, monkeypatch):
        """门 0 另一腿:停手线生效 → S2 清([13] 成型后不为残留
        discretionary wanted 重开,精确化注对齐)。判据消费位镜像 =
        monkeypatch proof.stop_buy(臂经同一模块属性消费)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            proof,
        )
        monkeypatch.setattr(proof, 'stop_buy',
                            lambda *a, **k: True)
        sess = _sess()
        state = _state()
        _set_s2(sess, state)
        out = mandate.wanted_closure_emit(
            sess, state, [_bc('填充件', 1)], [], 4, 3)
        assert out == []
        assert state_of(sess).cw4_shop_wanted_pending is None

    def test_gate1_reopens_before_legs(self):
        """门 1:席已空闲先重进——不发腾席腿(其他臂已腾过席不重复腾),
        S1 实清记一次重进预算(wanted_reopen 计数;S1 清键三路径枚举的
        (iii) 臂内提前收敛形态亦由本锁承载);闩已清帧不重复记账
        (路径 (ii) 已清形态)。"""
        sess = _sess()
        state = _state()
        _set_s2(sess, state)
        state_of(sess).cw4_shopped_phase = _PHASE
        out1 = mandate.wanted_closure_emit(sess, state, [_bc('填充件', 1)],
                                           [], 4, 3)
        assert out1 == []   # 零发射:下帧(实际=本帧④)M2 重评发 OpenShop
        assert state_of(sess).cw4_shopped_phase is None
        assert state_of(sess).cw4_wanted_reopens == (_PHASE, 1)
        assert state_of(sess).cw4_counters.get('wanted_reopen') == 1
        # 第二帧:闩已被别人清(如路径 (ii))→ 门 1 直落常规序,不双计
        out2 = mandate.wanted_closure_emit(sess, state, [_bc('填充件', 1)],
                                           [], 4, 3)
        assert out2 == []
        assert state_of(sess).cw4_wanted_reopens == (_PHASE, 1)

    def test_leg1_deploy_preferred_over_sell(self):
        """腿序:板面有空位 ∧ 部署门过 → 发 RunDeploy(wanted_close 填充,
        路线类 deploy_launch)——无损优先于卖出([22]);燃料同时在册
        也不卖(部署优先,§5.2 腿 1)。"""
        sess = _sess()
        state = _state()
        _set_s2(sess, state)
        bench = [_bc(f'填充件{i}', slot=i) for i in range(1, 10)]
        out = mandate.wanted_closure_emit(sess, state, bench, [], 4, 3)
        assert [type(e.action) for e in out] == [RunDeploy]
        assert out[0].reason == 'wanted_close'
        assert state_of(sess).cw4_counters.get('wanted_leg_deploy') == 1
        assert state_of(sess).cw4_counters.get('wanted_leg_fuel_sell') is None

    def test_leg2_fuel_sell_when_board_full(self):
        """腿 2:板满(cap=0 ⇒ vacancy 0)∧ bench 1★ 燃料 → 发
        SellBench(m4_fuel_sell;§5.2 腿 2 同源候选同路线类)。"""
        sess = _sess()
        state = _state()
        _set_s2(sess, state)
        bench = [_bc(f'填充件{i}', slot=i) for i in range(1, 10)]
        out = mandate.wanted_closure_emit(sess, state, bench, [], 0, 3)
        assert [type(e.action) for e in out] == [SellBench]
        assert out[0].reason == 'm4_fuel_sell'
        assert out[0].action.slot == 1
        assert state_of(sess).cw4_counters.get('wanted_leg_fuel_sell') == 1

    def test_both_legs_infeasible_abandons_node(self):
        """两腿皆不可行 = 裁决放弃态 + wanted_abandon;放弃态短路后续帧
        (不重复评估不重复计数);S2 键式保留至节点推进。"""
        sess = _sess()
        state = _state()
        _set_s2(sess, state)
        bench = [_bc(f'填充件{i}', slot=i, star=2)
                 for i in range(1, 10)]   # 2★ = 非燃料
        out = mandate.wanted_closure_emit(sess, state, bench, [], 0, 3)
        assert out == []
        st = state_of(sess)
        assert st.cw4_wanted_abandon_phase == _PHASE
        assert st.cw4_counters.get('wanted_abandon') == 1
        # 放弃态短路:同节点再入零新增计数
        mandate.wanted_closure_emit(sess, state, bench, [], 0, 3)
        assert st.cw4_counters.get('wanted_abandon') == 1

    def test_reopen_cap_circuit_breaks(self):
        """超安全阀 = wanted_circuit_break + 裁决放弃态(§6.2 纵深防御;
        终止性由三支柱独立保证,阀只保护落地事件病态重复)。记账点 =
        门 1 实清,循环至 WANTED_REOPEN_CAP 后下一帧熔断。"""
        sess = _sess()
        state = _state()
        _set_s2(sess, state)
        for _ in range(mandate.WANTED_REOPEN_CAP):
            state_of(sess).cw4_shopped_phase = _PHASE
            out = mandate.wanted_closure_emit(sess, state,
                                              [_bc('填充件', 1)], [], 4, 3)
            assert out == []
        state_of(sess).cw4_shopped_phase = _PHASE
        mandate.wanted_closure_emit(sess, state, [_bc('填充件', 1)], [], 4, 3)
        st = state_of(sess)
        assert st.cw4_counters.get('wanted_circuit_break') == 1
        assert st.cw4_wanted_abandon_phase == _PHASE

    def test_node_advance_key_mismatch_cleans(self):
        """节点推进 → 键失配:S2/放弃态/闩全部自动干净,臂零特判零发射
        (§3.2 键式形态的实现形态)。"""
        sess = _sess()
        state3 = _state(round_num=3)
        _set_s2(sess, state3)
        bench = [_bc(f'填充件{i}', slot=i, star=2) for i in range(1, 10)]
        mandate.wanted_closure_emit(sess, state3, bench, [], 0, 3)
        assert state_of(sess).cw4_wanted_abandon_phase == _PHASE
        # 下一节点(r4):全部旗标失配,臂零动作
        out = mandate.wanted_closure_emit(sess, _state(round_num=4),
                                          bench, [], 0, 4)
        assert out == []
        assert state_of(sess).cw4_counters.get('wanted_abandon') == 1


# ===== 2′. S2 门 0′ 前件五态(T-161 F2,ADR-0599)=====

class TestWantedPrecondition:
    """前件 = ∃m∈still_missing:m 在店快照 ∧ check_affordable(①号本体,
    金臂时点现读;方案审 T-161 §1.2/§1.3)。五态 = 方案审 §4 F2 验收
    件 1 逐件:hold 形态(①②)零发射且 S2 保留(禁早清——可负担腿可
    随节点内金入账翻真,§1.4)、放行形态腿序不变(③)、同节点 late-flip
    (④)、节点推进过期语义不受前件影响(⑤)。快照经 _set_s2 显式传
    in_shop 构造拦截/放行两形态,禁为保绿绕过前件。"""

    def _bench_full(self, star: int = 1) -> list[BenchChar]:
        return [_bc(f'填充件{i}', slot=i, star=star)
                for i in range(1, 10)]

    def test_not_in_shop_holds_and_keeps_s2(self):
        """① 不在店(空快照)→ hold:零发射(腾席腿不再为买不成的买入
        付出不可逆代价 = F2 缺陷关闭面)、S2 保留、不置放弃态、
        wanted_precond_hold 计 1。"""
        sess = _sess()
        state = _state()
        _set_s2(sess, state, in_shop=())
        out = mandate.wanted_closure_emit(sess, state, self._bench_full(),
                                          [], 0, 3)
        assert out == []
        st = state_of(sess)
        assert st.cw4_shop_wanted_pending is not None, '前件 hold 不得早清 S2'
        assert st.cw4_wanted_abandon_phase is None, 'hold 非放弃态'
        assert st.cw4_counters.get('wanted_precond_hold') == 1
        assert st.cw4_counters.get('wanted_leg_fuel_sell') is None

    def test_in_shop_unaffordable_holds(self):
        """② 在店但金不足(gold 2 < cost 5)→ hold:S2 保留等金,零发射。"""
        sess = _sess()
        state = _state()   # 缺省 gold=2
        _set_s2(sess, state, in_shop=(('目标件', 5),))
        out = mandate.wanted_closure_emit(sess, state, self._bench_full(),
                                          [], 0, 3)
        assert out == []
        st = state_of(sess)
        assert st.cw4_shop_wanted_pending is not None
        assert st.cw4_counters.get('wanted_precond_hold') == 1

    def test_affordable_member_activates_legs_unchanged(self):
        """③ ∃在店∧可负担(成员粒度:集内高费用件不拖累,目标件 cost 2
        ≤ gold 2)→ 照常开环,腿序不变(板有空位先部署),不计 hold。"""
        sess = _sess()
        state = _state()
        _set_s2(sess, state,
                in_shop=(('目标件', 2), ('不在集成员', 9)))
        out = mandate.wanted_closure_emit(sess, state, self._bench_full(),
                                          [], 4, 3)
        assert [type(e.action) for e in out] == [RunDeploy]
        st = state_of(sess)
        assert st.cw4_counters.get('wanted_leg_deploy') == 1
        assert st.cw4_counters.get('wanted_precond_hold') is None

    def test_gold_inflow_late_flip_activates_next_frame(self):
        """④ late-flip:帧 1 金不足 hold(S2 保留);同节点金入账(gold
        2→9,奖励球/他臂退金形态)后帧 2 翻真激活——快照只钉费用不钉
        金,金必须臂时点现读(方案审 §1.2 修正级 F2-2 的行为面)。"""
        sess = _sess()
        state = _state()   # gold=2
        _set_s2(sess, state, in_shop=(('目标件', 5),))
        bench = self._bench_full()
        out1 = mandate.wanted_closure_emit(sess, state, bench, [], 0, 3)
        assert out1 == []
        st = state_of(sess)
        assert st.cw4_counters.get('wanted_precond_hold') == 1
        assert st.cw4_shop_wanted_pending is not None, 'late-flip 前提:S2 未被早清'
        state.gold = 9   # 同节点金入账
        out2 = mandate.wanted_closure_emit(sess, state, bench, [], 4, 3)
        assert [type(e.action) for e in out2] == [RunDeploy]
        assert st.cw4_counters.get('wanted_precond_hold') == 1   # 翻真帧不计

    def test_node_advance_expiry_unaffected_by_precondition(self):
        """⑤ 节点推进键失配 → 过期不变:前件 hold 形态置场后推进节点,
        照常键失配零动作,hold 不跨节点累计、放弃态不受前件影响(过期
        规则单一 = 键失配,§3.2 既有语义;方案审 §4 ⑤)。"""
        sess = _sess()
        state3 = _state(round_num=3)
        _set_s2(sess, state3, in_shop=())
        bench = self._bench_full(star=2)
        assert mandate.wanted_closure_emit(sess, state3, bench, [], 0, 3) == []
        out = mandate.wanted_closure_emit(sess, _state(round_num=4),
                                          bench, [], 0, 4)
        assert out == []
        st = state_of(sess)
        assert st.cw4_counters.get('wanted_precond_hold') == 1   # 失配帧不计数
        assert st.cw4_wanted_abandon_phase is None


# ===== 3. route_tag 映射表与桥透传(§3.3 通道载体)=====

class TestRouteTagWhitelist:
    """映射表逐 tag 断言(发射位填值 → 执行侧清键路由);deploy_launch
    类 = RunDeploy 动作本体;白名单闭集不含凑息/压库(其重开仅经路径
    (ii));预留 tag equip_transfer_sell 无现役发射位(审 D3,枚举
    完备性)。"""

    def test_whitelist_closed_set(self):
        assert frozenset({
            'm4_fuel_sell', 'equip_transfer_sell'}) == mandate.S1_RESET_ROUTE_TAGS

    def test_route_tag_of_mapping_rows(self):
        assert mandate.route_tag_of(RunDeploy()) == 'deploy_launch'
        assert mandate.route_tag_of(RunEquip()) == ''   # 穿戴非清键路线
        sell_fuel = SellBench(slot=1)
        sell_fuel.route_tag = 'm4_fuel_sell'
        assert mandate.route_tag_of(sell_fuel) == 'm4_fuel_sell'
        sell_int = SellBench(slot=1)
        sell_int.route_tag = 'interest_prep'
        assert mandate.route_tag_of(sell_int) == 'interest_prep'
        assert mandate.route_tag_of(SellBench(slot=1)) == ''   # 未标缺省
        assert mandate.route_tag_of(StartBattle()) == ''

    def test_bridge_transfers_reason_without_loss(self):
        """桥透传不丢 tag:decide_from_turn 全链输出动作自带 route_tag =
        发射位 Emitted.reason(截断器幸存动作同样携带)。开局板帧
        (M5 RunDeploy)+ 空帧(StartBattle)两形态代表可续/终点两类。"""
        sess = _sess()
        obs = PrepObservation(
            state=_state(round_num=1, gold=20),
            bench_chars=[_bc('目标件', 1)], deployed_chars=[],
            free_bench_slots=8)
        actions = decide_from_turn(obs, SimpleNamespace(), sess, None)
        deploys = [a for a in actions if isinstance(a, RunDeploy)]
        assert deploys and deploys[0].route_tag == 'm5_opening_board', \
            f'透传丢失:M5 部署 route_tag 实得 ' \
            f'{[a.route_tag for a in deploys]}'
        obs_empty = PrepObservation(state=_state(round_num=2),
                                    bench_chars=[], deployed_chars=[],
                                    free_bench_slots=9)
        actions2 = decide_from_turn(obs_empty, SimpleNamespace(), sess, None)
        battles = [a for a in actions2 if isinstance(a, StartBattle)]
        assert battles and battles[0].route_tag == 'battle'


# ===== 4. RunTools 发射位(迁移 C,审 A1 主案)=====

_TOOL_KEY = '火力风暴潮'


def _tool_session(owned: list[str]) -> StrategySession:
    comp = Comp(name='测试线', factions=['贝洛伯格'], core_chars=['卡芙卡'],
                form_tiers={}, strength=5.0, form_difficulty='hard')
    comp.key_equips = [_TOOL_KEY]
    s = _sess()
    s.last_owned_equips = list(owned)
    state_of(s).target_comp = comp
    return s


def _dead_stock() -> str:
    from sr_od.application.currency_war.data.cw_synthesis import (
        recycle_qualified,
    )
    return sorted(recycle_qualified([_TOOL_KEY]))[0]


class TestRuntoolsEmitPosition:
    """发射位 = entry.emit ②证明 pass 与③升档器求值位之间(物理移出自
    run_mandate,审 A1 主案:dd-027 回排对 run_mandate 内任何 RunTools
    无条件重排到首个截断点之前 ⇒ 同帧 LevelUp+OpenShop 常态形态下
    RunTools 必被重排到 LevelUp 之后,LevelUp 先执行投影未建模终结本
    visit,RunTools 本帧从未执行);同批删 M7.5 原发射块防双发射。"""

    def _emit(self, s: StrategySession, st: GameState) -> list:
        # 黑板契约 = 紧缩型(仅已识别件);GameState.bench 是 pad 态。
        obs = PrepObservation(
            state=st,
            bench_chars=[b for b in getattr(st, 'bench', [])
                         if b is not None],
            deployed_chars=[d for d in getattr(st, 'deployed', [])
                            if d is not None],
            free_bench_slots=9)
        return entry.emit(obs, SimpleNamespace(), s, None)

    def test_run_mandate_no_longer_emits_runtools(self):
        """防双发射:run_mandate 直调(工具就绪会话)零 RunTools——发射
        面唯一在 entry.emit ②③ 之间。"""
        s = _tool_session(['冶金炉', _dead_stock()])
        out = mandate.run_mandate(
            mandate.MandateFrame(gold=20, level=3, bench=[], deployed=[],
                                 deploy_cap=4, node_type=None,
                                 stop_flag=False, k_members=(),
                                 round_num=3),
            s, state=_state(gold=20))
        assert not any(isinstance(e.action, RunTools) for e in out)

    def test_runtools_leads_same_frame_levelup(self):
        """同帧 LevelUp+RunTools 形态执行序 = RunTools 先于 LevelUp
        (迁移 C 行为锚):消耗品给的经验/金经下一 visit 入口 heavy 进
        M3,前移消除「旧输入升级照发」面(猎点 12 v2.1 收益路径口径);
        发射恰一次(②③ 之间单发射位)。"""
        s = _tool_session(['冶金炉', _dead_stock()])
        st = _state(gold=8)
        st.node_type = 'battle'
        st.xp_progress = (0, 4)
        st.deployed = [_bc('爻光', slot=i) for i in range(10)]
        st.bench = [_bc('爻光', slot=0)]
        out = self._emit(s, st)
        kinds = [type(e.action) for e in out]
        assert kinds.count(RunTools) == 1, f'RunTools 发射数漂移:{kinds}'
        assert kinds.index(RunTools) < kinds.index(LevelUp), \
            f'执行序错:RunTools 必须先于 LevelUp(实发 {kinds})'

    def test_runtools_leads_truncation_point(self):
        """同帧开店意图:工具先于截断点(截断点后动作被截断器丢弃,
        工具落后 = 本帧从未执行的旧病灶同型)。开店发射供给 = dominance
        溢余买面:线成型(k=['卡芙卡'] 全持有)+ 溢余金 → stop_flag=True
        经 ② 证明 pass 供给(emit 链内无手摆帧)。"""
        s = _tool_session(['冶金炉', _dead_stock()])
        obs = PrepObservation(state=_state(gold=999),
                              bench_chars=[_bc('卡芙卡', 1)],
                              deployed_chars=[], free_bench_slots=8)
        out = entry.emit(obs, SimpleNamespace(), s, None)
        kinds = [type(e.action) for e in out]
        assert OpenShop in kinds and RunTools in kinds, \
            f'前置失真:同帧应发 RunTools+OpenShop,实发 {kinds}'
        assert kinds.index(RunTools) < kinds.index(OpenShop)


# ===== 5. 席满前置谓词(迁移 B;猎点 13;两腿形态 ADR-0596 §4.9③)=====

class TestSphereBenchFullPredicate:
    """谓词两腿 =「bench_free>0 ∨ 球均不占席」。第二腿按占席颜色集判定:
    现役缺省 = 空集(宁多收球不误卖,与 adapter free_bench_slots
    None→BENCH_CAPACITY 在库裁决同向;落地审 M1 再裁反转候裁 4 缺省,
    颜色→占席机制面待实机实证后登记收紧)。腾席先于点球与残留跳过为
    占席集登记后的激活形态,占席球面的损失由 2026-09-02 席满球裁定
    screen_flow_timing #16「部分没点开自然回补」容忍语义承载(裁定辖
    点击验证容忍度,非禁止为球腾席;覆盖留痕 = 方案 §4 猎点 13 +
    进度账本)。"""

    _SPHERE = [('blue', SimpleNamespace(x=100, y=100), 3)]

    def _emit(self, sess, st, bench, free, spheres=None):
        obs = PrepObservation(
            state=st, bench_chars=bench, deployed_chars=[],
            spheres=list(self._SPHERE if spheres is None else spheres),
            free_bench_slots=free)
        return entry.emit(obs, SimpleNamespace(), sess, None)

    def test_bench_full_default_collects_spheres(self):
        """席满 + 占席集现役空(球均按不占席缺省)→ 照常点球不卖
        (宁多收球:金球等不占席内容可点成功,占席球由执行器侧「部分
        没点开自然回补」容忍承载;席满+无燃料帧回归可点 = 落地审 M1
        行为子集损失修复锚)。"""
        sess = _sess()
        out = self._emit(sess, _state(),
                         [_bc(f'填充件{i}', slot=i, star=2)
                          for i in range(1, 10)],
                         free=0)
        assert len(out) == 1
        assert isinstance(out[0].action, ClickSpheres)
        assert out[0].reason == 'prep_spheres'
        assert state_of(sess).cw4_counters.get(
            'sphere_blocked_bench_full') is None

    def test_bench_full_occupying_color_sells_fuel_first(self, monkeypatch):
        """激活形态(占席集登记后):席满 ∧ 球判占席 → 先单次腾席不发
        ClickSpheres(白名单 tag 落地经路径 (i) 清 S1)。"""
        monkeypatch.setattr(entry, 'SPHERE_OCCUPYING_COLORS',
                            frozenset({'blue'}))
        sess = _sess()
        out = self._emit(sess, _state(),
                         [_bc(f'填充件{i}', slot=i) for i in range(1, 10)],
                         free=0)
        assert len(out) == 1
        assert isinstance(out[0].action, SellBench)
        assert out[0].reason == 'm4_fuel_sell'
        assert not any(isinstance(e.action, ClickSpheres) for e in out)

    def test_occupying_leg_requires_all_spheres_clean(self, monkeypatch):
        """「球均」语义:仅一枚占席色即腿假(混合帧不放弃占席球的腾席
        机会,其余球下帧回补)。"""
        monkeypatch.setattr(entry, 'SPHERE_OCCUPYING_COLORS',
                            frozenset({'blue'}))
        sess = _sess()
        mixed = [('gold', SimpleNamespace(x=100, y=100), 3),
                 ('blue', SimpleNamespace(x=140, y=100), 3)]
        out = self._emit(sess, _state(),
                         [_bc(f'填充件{i}', slot=i) for i in range(1, 10)],
                         free=0, spheres=mixed)
        assert len(out) == 1
        assert isinstance(out[0].action, SellBench)
        assert not any(isinstance(e.action, ClickSpheres) for e in out)

    def test_bench_full_blocked_fallthrough_when_occupied_no_fuel(
            self, monkeypatch):
        """激活形态:席满 ∧ 球判占席 ∧ 腾不出 → 球残留跳过:零点击、
        sphere_blocked_bench_full 计数、落入常规步骤序(不停机)。"""
        monkeypatch.setattr(entry, 'SPHERE_OCCUPYING_COLORS',
                            frozenset({'blue'}))
        sess = _sess()
        out = self._emit(sess, _state(),
                         [_bc(f'填充件{i}', slot=i, star=2)
                          for i in range(1, 10)],
                         free=0)
        assert not any(isinstance(e.action, ClickSpheres) for e in out)
        assert not any(isinstance(e.action, SellBench) for e in out)
        assert state_of(sess).cw4_counters.get(
            'sphere_blocked_bench_full') == 1

    def test_bench_free_clicks_unchanged(self):
        """对照(第一腿):席有空 → 照常 ClickSpheres(现行行为零回退)。"""
        sess = _sess()
        out = self._emit(sess, _state(), [], free=2)
        assert len(out) == 1
        assert isinstance(out[0].action, ClickSpheres)
        assert out[0].reason == 'prep_spheres'

    def test_unreadable_occupancy_defaults_to_collect(self):
        """N3 缺省方向对齐:free_bench_slots 缺读(None)→ 按
        BENCH_CAPACITY(全空)处理 → 点球不卖(adapter 在库裁决同向:
        宁多收球,SellBench 不可逆)。"""
        sess = _sess()
        out = self._emit(sess, _state(),
                         [_bc(f'填充件{i}', slot=i, star=2)
                          for i in range(1, 10)],
                         free=None)
        assert len(out) == 1
        assert isinstance(out[0].action, ClickSpheres)


# ===== 6. S3 不立变量(墓碑)+ M3 纯函数翻转(§1.4)=====

class TestS3NoVariable:
    """S3 = 升级检查逻辑旗标:物理载体 = 期望态新鲜度(纯函数每帧幂等
    求值,重评触发集 ⊇ 任何输入变更,单向上位);独立旗标变量与期望态
    构成双源,失步即错裁决 → 墓碑扫描防回流(README 测试纪律 8 合法
    墓碑形态:否定式 + 退役背书 = 方案 §1.4 裁决)。"""

    def test_no_independent_s3_field(self):
        banned = [f.name for f in dataclasses.fields(MandateState)
                  if 's3' in f.name.lower() or f.name.startswith('cw4_m3')]
        assert banned == [], \
            f'出现独立 S3/升级检查变量字段(双源回归):{banned}'

    def test_m3_predicate_flips_with_input(self):
        """纯函数语义:输入变 → 结论翻转(幂等求值即脏标记,零变量)。
        场景 = 注册表真名(阵营共享谓词消费面):板面三月七(列车同行)
        ∧ bench 丹恒·饮月(列车同行)板满(cap=4)→ True;cap 输入变 5
        (板不再满)→ False。"""
        board_full = predicates.arm1_existence(
            4, ['丹恒·饮月'],
            ['三月七', '三月七', '三月七', '三月七'], 4)
        cap_expanded = predicates.arm1_existence(
            4, ['丹恒·饮月'],
            ['三月七', '三月七', '三月七', '三月七'], 5)
        assert board_full is True and cap_expanded is False


# ===== 7. F1b 分派位结构化落地判定(T-167)=====

def test_run_deploy_dispatch_landing_is_structural(monkeypatch):
    """F1b 锁(T-167 事故修法;真执行器分派位):部署组合的 landed 由
    执行器具名常量 STATUS_DEPLOYED **结构化比对**产生——STATUS_NOOP
    (计划空合法稳态)→ landed=False;STATUS_DEPLOYED(真部署)→
    landed=True。修法红线:禁由 detail 字符串反推(detail =
    f'{name} {status}' 带前缀显影文本,裸比对恒 False 会让 landed 恒
    True、修复静默失效)——本锁用真 _run_composite 返回形态构造,复辟
    字符串比对时本锁红。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_deploy as deploy_mod,
    )
    from sr_od.application.currency_war.prep_actions import PrepActionExecutor

    statuses = {'next': deploy_mod.CwOpDeploy.STATUS_NOOP}

    class _StubDeploy:
        STATUS_DEPLOYED = deploy_mod.CwOpDeploy.STATUS_DEPLOYED
        STATUS_NOOP = deploy_mod.CwOpDeploy.STATUS_NOOP

        def __init__(self, ctx) -> None:
            pass

        def execute(self):
            return SimpleNamespace(success=True,
                                   status=statuses['next'])

    monkeypatch.setattr(deploy_mod, 'CwOpDeploy', _StubDeploy)
    ctx = SimpleNamespace(
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        run_context=None, cw_match=None)
    ex = PrepActionExecutor(SimpleNamespace(screenshot=lambda: object()), ctx)
    # no-op 稳态:progressed=True 但零落地
    ok, detail, landed = ex._execute_dispatch(RunDeploy())
    assert ok is True and landed is False, (
        f'STATUS_NOOP 必须 landed=False(零落地),实得 ok={ok} landed={landed}')
    assert '部署' in detail and _StubDeploy.STATUS_NOOP in detail, (
        f'detail 仍为带前缀显影文本(禁改语义):{detail!r}')
    # 真部署:landed=True
    statuses['next'] = deploy_mod.CwOpDeploy.STATUS_DEPLOYED
    ok2, _detail2, landed2 = ex._execute_dispatch(RunDeploy())
    assert ok2 is True and landed2 is True, '真部署落地 landed=True'
    # 执行器具名常量缺失 = fail-closed 按未落地(宁该清不清,不乱清)
    class _BrokenDeploy:
        STATUS_NOOP = deploy_mod.CwOpDeploy.STATUS_NOOP

        def __init__(self, ctx) -> None:
            pass

        def execute(self):
            return SimpleNamespace(success=True,
                                   status=statuses['next'])

    monkeypatch.setattr(deploy_mod, 'CwOpDeploy', _BrokenDeploy)
    statuses['next'] = '任意状态'
    _ok3, _d3, landed3 = ex._execute_dispatch(RunDeploy())
    assert landed3 is False, '常量解析缺失必须 fail-closed 按未落地'
