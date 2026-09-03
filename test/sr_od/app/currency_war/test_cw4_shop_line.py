"""cw4 步4b 商店线批测试(decide_shop_screen 接线验收全项)。

覆盖:criteria 七面商店形态单测(每面判据式行为锚)/ 词表+截断契约锁
(契约 v2 §3.1 逐类+§3.3 fail-closed)/ 修复池商店面检查点核销
(D-FM1/D-D/D-P2idle/D-F9·A45/D-BUYNOTE)/ ev_arm 臂形态(注入形态开闸
差异锚)/ 基线臂零漂移复跑 + 双臂相异实证(慢桶,sim 实跑)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.decision.cw4 import proof, shop
from sr_od.application.currency_war.decision.cw4.audit import provisional
from sr_od.application.currency_war.decision.cw4.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY, get_comp
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    CompTransaction,
    DeployMove,
    GameState,
    LevelUp,
    LevelUpShop,
    PickEvent,
    RefreshShop,
    SellBench,
    SellDeployed,
    ShopCard,
    SwapDeploy,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)

# ===== 测试基建 =====

class _Cfg:
    """决策 config 桩(ev_arm 字段=R1-1 实验因子)。"""

    def __init__(self, ev_arm: str = 'full') -> None:
        self.ev_arm = ev_arm


def _comp():
    names = [c.name for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
    return get_comp(names[0])


def _members(comp) -> list[str]:
    ms = list(comp.core_chars) + list(getattr(comp, 'shared_chars', []) or [])
    return list(dict.fromkeys(ms))


def _session(comp=None) -> StrategySession:
    s = StrategySession()
    s.cw4_counters = {}
    s.target_comp = comp
    s.cw4_line_state = proof.LineState()
    return s


def _state(gold: int = 30, shop=None, bench=None, deployed=None,
           level: int = 3, node=None, xp=None) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2, node_type=node)
    st.shop = shop if shop is not None else []
    st.bench = bench if bench is not None else []
    st.deployed = deployed if deployed is not None else []
    if xp is not None:
        st.xp_progress = xp
    return st


def _card(name: str, cost: int = 3, star: int = 1, x: int = 100) -> ShopCard:
    return ShopCard(x=x, name=name, cost=cost, star=star)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _decide(state: GameState, session: StrategySession,
            cfg: _Cfg | None = None):
    from sr_od.application.currency_war.sim.engine_p1 import (
        sim_decision_registry,
    )
    strat = MandateV1Strategy(registry=sim_decision_registry())
    session.shop_state_frame = state
    return strat.decide_shop_screen(session, cfg or _Cfg())


# ===== ① criteria 七面商店形态(每面判据式行为锚)=====

class TestCriteriaShopFaces:

    def test_buy_face_m2_line_member(self):
        """买面:M2 线成员义务买入(黑板店面 → BuyCard,reason 可归因)。"""
        comp = _comp()
        m = _members(comp)[0]
        st = _state(gold=30, shop=[_card(m, cost=3)])
        acts = _decide(st, _session(comp))
        buys = [a for a in acts if isinstance(a, BuyCard)]
        assert any(b.card.name == m for b in buys)
        assert all(b.reason == 'm2_line_member' for b in buys
                   if b.card.name == m)

    def test_buy_face_m2_gold_gated(self):
        """买面:硬约束①——金不足不买(可逆面缺输入默认不做侧镜像)。"""
        comp = _comp()
        m = _members(comp)[0]
        st = _state(gold=2, shop=[_card(m, cost=3)])
        acts = _decide(st, _session(comp))
        assert not [a for a in acts if isinstance(a, BuyCard)]

    def test_buy_face_dominance_sink(self):
        """D-FM1 sink:金>g* ∧ stop_flag(线成型)⇒ 支配买全额可退 1★ 件。"""
        comp = _comp()
        members = _members(comp)
        # 线成型:全部成员已在 bench ⇒ stop_flag=1
        bench = [_bc(m) for m in members]
        fuel = '燃料件X'          # 注册表外名=零重叠可判(类级默认低费)
        st = _state(gold=60, shop=[_card(fuel, cost=1, star=1)], bench=bench)
        acts = _decide(st, _session(comp))
        buys = [a for a in acts if isinstance(a, BuyCard)]
        assert any(b.reason == 'dominance_buy' for b in buys)

    def test_buy_face_dominance_not_refundable(self):
        """支配背书仅 1★(refund_full_star_ok;2★+ 无 EV/支配背书)。"""
        comp = _comp()
        bench = [_bc(m) for m in _members(comp)]
        st = _state(gold=60, shop=[_card('燃料件X', cost=3, star=2)],
                    bench=bench)
        acts = _decide(st, _session(comp))
        assert not [a for a in acts if isinstance(a, BuyCard)]

    def test_sell_face_m4_fuel_sell_when_bench_full(self):
        """卖面:M4 腾席——bench 满 ∧ 有线成员可买 ⇒ 卖 1★ 零重叠件。"""
        comp = _comp()
        members = _members(comp)
        m0 = members[0]
        bench = [_bc(m) for m in members[1:]]     # 缺 m0,其余占满
        while len(bench) < BENCH_CAPACITY:
            bench.append(_bc(f'填充件{len(bench)}'))
        st = _state(gold=30, shop=[_card(m0, cost=3)], bench=bench)
        acts = _decide(st, _session(comp))
        sells = [a for a in acts if isinstance(a, SellBench)]
        buys = [a for a in acts if isinstance(a, BuyCard)]
        assert sells and buys          # 先腾席后买入,单帧闭环

    def test_sell_face_funding_support_both_arms(self):
        """卖面:支付支撑通道两臂同开(R13-5)——金不足 ⇒ 筹资变现。
        (R197 症6 连带:need 改注册表派生后,该 comp 含 1 费成员 ⇒
        gold=1 已覆盖最廉价成本、筹资正确不触发——旧 gold=1 与字面量
        need=3 耦合,锁语义=「金不足」,金改 0 使任意正 need 均不足。)"""
        comp = _comp()
        m = _members(comp)[0]
        bench = [_bc('燃料件Y', star=1), _bc(m)]
        st = _state(gold=0, shop=[_card(_members(comp)[1], cost=3)],
                    bench=bench)
        for arm in ('skeleton_only', 'full'):
            acts = _decide(st, _session(comp), _Cfg(arm))
            assert any(isinstance(a, SellBench) for a in acts), arm

    def test_levelup_face_batch_discipline(self):
        """升级面:D-BUYNOTE 整买纪律——整批够升级才放行(散买拦截)。"""
        # arm1_existence 需板满(10)+ bench 等待件共享阵营/流派:
        # 板/bench 同名件(爻光)必然共享 ⇒ 谓词真
        deployed = [_bc('爻光') for _ in range(10)]
        bench = [_bc('爻光')]
        # 整批不够:金 3 < clicks×cost
        st = _state(gold=3, bench=bench, deployed=deployed, level=3,
                    xp=(0, 4))
        acts = _decide(st, _session(_comp()))
        assert not [a for a in acts if isinstance(a, LevelUpShop)]
        # 整批够:金 8 ≥ 1 click × 4(LEVEL up xp(0,4) → 1 click)
        st2 = _state(gold=8, bench=bench, deployed=deployed, level=3,
                     xp=(0, 4))
        acts2 = _decide(st2, _session(_comp()))
        lv = [a for a in acts2 if isinstance(a, LevelUpShop)]
        assert lv and all(a.auth_basis == 'm3_batch' for a in lv)

    def test_levelup_face_lv9_stop(self):
        """升级面:满级停(lv9_stop,LEVEL_CAP)。"""
        deployed = [_bc(f'板件{i}') for i in range(10)]
        bench = [_bc('等待件W')]
        st = _state(gold=50, bench=bench, deployed=deployed, level=9)
        acts = _decide(st, _session(_comp()))
        assert not [a for a in acts if isinstance(a, LevelUpShop)]

    def test_refresh_face_fail_closed(self):
        """刷新面:r1 EV 未标定(None)⇒ fail-closed 不刷 + 分键计数。"""
        comp = _comp()
        bench = [_bc(m) for m in _members(comp)]
        st = _state(gold=60, bench=bench)
        sess = _session(comp)
        _decide(st, sess)
        assert sess.cw4_counters.get('shop_r1_ev_unavailable', 0) >= 1
        assert not [a for a in _decide(st, _session(comp))
                    if isinstance(a, RefreshShop)]

    def test_stockpile_face_m6_strand(self):
        """压库面:M6 存在性成立 ∧ T_SEARCH🔴 ⇒ 不买 + 溢余滞留计数。"""
        comp = _comp()
        bench = [_bc(m) for m in _members(comp)]
        st = _state(gold=60, shop=[_card('燃料件X', cost=1)], bench=bench)
        sess = _session(comp)
        _decide(st, sess)
        assert sess.cw4_counters.get('m6_overflow_strand', 0) >= 1

    def test_equipment_face_no_shop_emission(self):
        """装备面:商店线辖域申报——装备发射位在 prep 域,商店波零装备动作
        (词表本身无装备类,断言=输出全在商店词表内)。"""
        comp = _comp()
        st = _state(gold=30, shop=[_card(_members(comp)[0])])
        acts = _decide(st, _session(comp))
        vocab = (BuyCard, LevelUpShop, LevelUp, SellBench, SellDeployed,
                 DeployMove, SwapDeploy, RefreshShop, CompTransaction)
        assert all(isinstance(a, vocab) for a in acts)

    def test_proof_face_stop_flag_gates_dominance(self):
        """证明面投影:stop_flag=0(线未成型)⇒ dominance 通道关。"""
        comp = _comp()
        members = _members(comp)
        bench = [_bc(m) for m in members[:-1]]   # 缺一件 ⇒ 未成型
        st = _state(gold=60, shop=[_card('燃料件X', cost=1)], bench=bench)
        acts = _decide(st, _session(comp))
        assert not [a for a in acts if isinstance(a, BuyCard)
                    and a.reason == 'dominance_buy']


# ===== ② 词表+截断契约锁(契约 v2 §3.1 逐类 + §3.3)=====

class TestShopTruncationContract:

    def test_vocab_all_classes_covered(self):
        """词表锁:cw_state.Action 联合 9 类中商店线辖 8 类逐类有分类
        (PickEvent=pick 返回载体,§3.1 词表源对账声明辖外)。"""
        classified = (BuyCard, LevelUpShop, LevelUp, SellBench,
                      SellDeployed, DeployMove, SwapDeploy, RefreshShop,
                      CompTransaction)
        union = (BuyCard, SellBench, LevelUp, DeployMove, RefreshShop,
                 PickEvent, SellDeployed, SwapDeploy, CompTransaction)
        assert (set(union) - {PickEvent}) <= set(classified)
        assert PickEvent not in classified          # 词表外(§3.3 兜底)
        assert issubclass(LevelUpShop, LevelUp)     # 升级意图商店屏子类

    def test_buy_continue_and_levelup_continue(self):
        """BuyCard/LevelUpShop = 可续(多动作序列不截断)。"""
        st = _state()
        seq = [BuyCard(card=_card('甲')), LevelUpShop(cost=4),
               BuyCard(card=_card('乙'))]
        out = shop.truncate_shop_frame_stable(seq, st)
        assert out == seq

    def test_drag_family_conditional_continue(self):
        """拖拽族名-槽一致性复检(R197 症4① 重写为判据语义锁,契约
        §3.1 行「逐动作语义防线=名-槽一致性复检;前序动作累积静态推出,
        推不出即截断」;旧测试锁的是「无条件放行」实现回声):

        - 名-槽一致 + 前序卖出累积投影成立 ⇒ 可续;
        - 同槽二次引用(卖出后槽已从投影集移除)⇒ 截断 + 计数;
        - ``expect`` 名不符(跨代际提案)⇒ 截断 + 计数;
        - 引用越界/空槽 ⇒ 截断 + 计数。
        """
        st = _state(bench=[_bc('甲'), _bc('乙')])
        # 一致拖拽族可续(卖出 idx0 后,DeployMove 引用另一占用槽 idx1)
        seq = [SellBench(bench_idx=0, income=3, expect='甲'),
               DeployMove(bench_idx=1, to_row='back', faction='仙舟')]
        out = shop.truncate_shop_frame_stable(seq, st)
        assert out == seq
        # 同槽二次引用:卖出后槽位从投影集移除 ⇒ 截断 + 计数
        sess = _session()
        seq2 = [SellBench(bench_idx=0, income=3, expect='甲'),
                SellBench(bench_idx=0, income=3, expect='甲')]
        out2 = shop.truncate_shop_frame_stable(seq2, st, sess)
        assert len(out2) == 1
        assert sess.cw4_counters['emitter_conditional_truncated'] == 1
        assert sess.cw4_counters['emitter_post_truncation_dropped'] == 1
        # 名不符(跨代际提案)⇒ 截断
        sess2 = _session()
        out3 = shop.truncate_shop_frame_stable(
            [SellBench(bench_idx=0, income=3, expect='乙')], st, sess2)
        assert out3 == []
        assert sess2.cw4_counters['emitter_conditional_truncated'] == 1
        # 引用越界槽 ⇒ 截断
        sess3 = _session()
        out4 = shop.truncate_shop_frame_stable(
            [DeployMove(bench_idx=5, to_row='back', faction='仙舟')],
            st, sess3)
        assert out4 == []
        assert sess3.cw4_counters['emitter_conditional_truncated'] == 1

    def test_levelup_normalized_to_levelupshop(self):
        """R197 症4②:裸 LevelUp 发射侧归一化为 LevelUpShop(is-a
        LevelUp,契约表既有行;字段保留)——商店波发射一律 LevelUpShop,
        词表收紧为契约 8 类(契约正文零改动)。"""
        st = _state()
        seq = [LevelUp(cost=4, auth_basis='legacy'),
               BuyCard(card=_card('甲'))]
        out = shop.truncate_shop_frame_stable(seq, st)
        assert [type(a) for a in out] == [LevelUpShop, BuyCard]
        assert out[0].cost == 4 and out[0].auth_basis == 'legacy'
        # 词表锁:可续类 = 契约 8 类口径(裸 LevelUp 不在商店词表)
        assert (BuyCard, LevelUpShop) == shop._SHOP_CONTINUE
        assert LevelUp not in shop._SHOP_CONTINUE

    def test_refresh_shop_truncation_point(self):
        """RefreshShop = 截断点:其后动作丢弃,自身保留为末位。"""
        st = _state()
        seq = [BuyCard(card=_card('甲')), RefreshShop(cost=2),
               BuyCard(card=_card('乙'))]
        out = shop.truncate_shop_frame_stable(seq, st)
        assert out == seq[:2]
        assert isinstance(out[-1], RefreshShop)

    def test_comp_transaction_truncation_point(self):
        """CompTransaction = 截断点(fill 消费店槽 ⇒ 重决策)。"""
        st = _state()
        seq = [CompTransaction(deploy=[], undeploy=[], sell=[]),
               BuyCard(card=_card('甲'))]
        out = shop.truncate_shop_frame_stable(seq, st)
        assert out == seq[:1]

    def test_merge_trigger_truncates(self):
        """合成触发:买同名同星第 3 张 ⇒ 该买牌后截断 + 计数披露。"""
        st = _state(bench=[_bc('甲'), _bc('甲')])
        seq = [BuyCard(card=_card('甲')), BuyCard(card=_card('乙'))]
        sess = _session()
        out = shop.truncate_shop_frame_stable(seq, st, sess)
        assert len(out) == 1 and isinstance(out[0], BuyCard)
        assert sess.cw4_counters['shop_merge_trigger_truncate'] == 1

    def test_merge_counts_deployed_copies(self):
        """合成保守域:场上同名同星副本并入计数(bench1+deployed1+买1=3)。"""
        st = _state(bench=[_bc('甲')],
                    deployed=[_bc('甲')] + [None] * 9)
        seq = [BuyCard(card=_card('甲'))]
        sess = _session()
        out = shop.truncate_shop_frame_stable(seq, st, sess)
        assert len(out) == 1
        assert sess.cw4_counters['shop_merge_trigger_truncate'] == 1

    def test_pick_event_fail_closed(self):
        """§3.3:PickEvent(pick 返回载体,词表外)⇒ 截断 + 计数披露。"""
        st = _state()
        seq = [BuyCard(card=_card('甲')), PickEvent(option_idx=0),
               BuyCard(card=_card('乙'))]
        sess = _session()
        out = shop.truncate_shop_frame_stable(seq, st, sess)
        assert len(out) == 1
        assert sess.cw4_counters['emitter_unknown_action_truncated'] == 1

    def test_rogue_action_fail_closed(self):
        """§3.3:词表外任意类型 ⇒ 截断 + 计数(禁静默丢弃)。"""
        st = _state()
        seq = [BuyCard(card=_card('甲')), object()]
        sess = _session()
        out = shop.truncate_shop_frame_stable(seq, st, sess)  # type: ignore[arg-type]
        assert len(out) == 1
        assert sess.cw4_counters['emitter_unknown_action_truncated'] == 1

    def test_blackboard_missing_raises(self):
        """黑板契约:shop_state_frame 缺失 ⇒ 抛错(禁静默按空态决策)。"""
        from sr_od.application.currency_war.sim.engine_p1 import (
            sim_decision_registry,
        )
        strat = MandateV1Strategy(registry=sim_decision_registry())
        with pytest.raises(ValueError, match='shop_state_frame'):
            strat.decide_shop_screen(_session(), _Cfg())


# ===== ③ 修复池商店面检查点核销 =====

class TestFixpoolShopCheckpoints:

    def test_d_fm1_sink_channel_open(self):
        """D-FM1:金>g* ∧ 线成型 ⇒ 存在可达战力投资出口(支配买通道)。"""
        comp = _comp()
        bench = [_bc(m) for m in _members(comp)]
        st = _state(gold=60, shop=[_card('燃料件X', cost=1)], bench=bench)
        acts = _decide(st, _session(comp))
        assert any(isinstance(a, BuyCard) for a in acts)

    def test_d_p2idle_no_candidate_vs_all_vetoed(self):
        """D-P2idle:「无候选」vs「全拒」分键可辨(u_unavailable 独立分键)。"""
        comp = _comp()
        bench = [_bc(m) for m in _members(comp)]
        outsider = '燃料件Z'
        st = _state(gold=20, shop=[_card(outsider, cost=1)], bench=bench)
        sess = _session(comp)
        _decide(st, sess)
        # None 期:U_X🔴 ⇒ 候选生成 fail-closed(u_unavailable 分键;
        # 店面非空才进 u 判,空店=shop_domain 分键)
        assert sess.cw4_counters.get('shop_ev_u_unavailable', 0) >= 1

    def test_d_p2idle_idle_gold_counter(self):
        """D-P2idle:带金零动作波计数(gold≥10 且无发射)。"""
        comp = _comp()
        bench = [_bc(m) for m in _members(comp)]   # 线成型,金低于 g*
        st = _state(gold=12, bench=bench)
        sess = _session(comp)
        _decide(st, sess)
        assert sess.cw4_counters.get('shop_wave_idle_gold', 0) == 1

    def test_d_hard_node_gate_consumed(self):
        """D-D:硬节点(遭遇/boss)备战补强门被消费(观察级接线+计数)。"""
        comp = _comp()
        bench = [_bc(m) for m in _members(comp)]
        st = _state(gold=60, bench=bench, node='boss')
        sess = _session(comp)
        _decide(st, sess)
        assert sess.cw4_counters.get('shop_hard_node_gate_open', 0) >= 1
        # 非硬节点不触发
        st2 = _state(gold=60, bench=bench, node='reward')
        sess2 = _session(comp)
        _decide(st2, sess2)
        assert sess2.cw4_counters.get('shop_hard_node_gate_open', 0) == 0

    def test_d_a45_drought_reset_on_target_buy(self):
        """D-A45 商店侧半边:买入目标件 ⇒ 干旱计数器重置 + 事件计数。"""
        comp = _comp()
        m = _members(comp)[0]
        sess = _session(comp)
        sess.cw4_line_state.drought = 4
        st = _state(gold=30, shop=[_card(m, cost=3)])
        _decide(st, sess)
        assert sess.cw4_line_state.drought == 0
        assert sess.cw4_counters.get('shop_drought_reset_on_buy', 0) == 1

    def test_d_f9_drought_no_reset_without_target_buy(self):
        """D-F9/D-A45 反例:未买目标件 ⇒ 干旱不重置(计数器事件语义)。"""
        comp = _comp()
        sess = _session(comp)
        sess.cw4_line_state.drought = 3
        st = _state(gold=30, shop=[])         # 店面无目标件
        _decide(st, sess)
        assert sess.cw4_line_state.drought == 3
        assert sess.cw4_counters.get('shop_drought_reset_on_buy', 0) == 0

    def test_d_buynote_embedded(self):
        """D-BUYNOTE:P48 整买纪律作为常量判据内嵌(spend_unified 直测)。"""
        from sr_od.application.currency_war.decision.cw4.criteria import (
            levelup as crit_levelup,
        )
        assert not crit_levelup.spend_unified(2, 4, 4)   # 散买拦截
        assert crit_levelup.spend_unified(2, 8, 4)       # 整批放行


# ===== ④ ev_arm 臂形态(注入形态开闸差异锚)=====

class TestEvArmBypass:

    def test_skeleton_only_bypasses_ev_buy_face(self):
        """臂①旁路:U_X+T_SEARCH+V_MS 注入形态下,full 臂发 EV 买、
        skeleton 臂不发(§4.2.1 ev_buy_candidates 发射面一体旁路)。
        (锁语义重推,IMPL_ADV_R200 症5①:旧锁钉「注入即全放行
        {1,2,3}」占位窗口——CALIB_REPORT_V2 §2.3 定谳常数窗口不可
        推导,窗口改运行时查表(读法乙,等级+V_MS 现读);本锁随改注入
        V_MS=24.7 并取 cost=1@L3(读法乙窗口 {1})为发射对象。)"""
        comp = _comp()
        members = _members(comp)
        bench = [_bc(m) for m in members]
        outsider = '爻光'                # 非线内件(线成员外)
        if outsider in members:
            outsider = '银枝'
        _state(gold=30, shop=[_card(outsider, cost=1)],
                    bench=bench)
        try:
            provisional.inject('U_X', provisional.CalibValue(
                value=1.0, injected_form=True))
            provisional.inject('T_SEARCH_A', provisional.CalibValue(
                value=1.0, injected_form=True))
            provisional.inject('V_MS', provisional.CalibValue(
                value=24.7, ci_lo=16.7, ci_hi=24.7, injected_form=True))
            # 金 30 < g*(50):dominance 通道关 ⇒ 店面该件归 EV 买面独占
            full = _decide(_state(gold=30, shop=[_card(outsider, cost=1)],
                                  bench=[_bc(m) for m in members]),
                           _session(comp), _Cfg('full'))
            skel = _decide(_state(gold=30, shop=[_card(outsider, cost=1)],
                                  bench=[_bc(m) for m in members]),
                           _session(comp), _Cfg('skeleton_only'))
        finally:
            provisional.reset('U_X')
            provisional.reset('T_SEARCH_A')
            provisional.reset('V_MS')
        assert any(isinstance(a, BuyCard) and a.reason == 'ev_buy'
                   for a in full)
        assert not any(isinstance(a, BuyCard) and a.reason == 'ev_buy'
                       for a in skel)

    def test_invalid_ev_arm_falls_back_full(self):
        """ev_arm 非法值回落 full(R1-1 值域护栏)。"""
        comp = _comp()
        m = _members(comp)[0]
        st = _state(gold=30, shop=[_card(m)])
        acts = _decide(st, _session(comp), _Cfg('bogus'))
        assert any(isinstance(a, BuyCard) for a in acts)

    def test_rng_neutral(self):
        """rng 中立:商店波决策不消费局内 rng(会话 rng 状态零推进)。"""
        comp = _comp()
        m = _members(comp)[0]
        sess = _session(comp)
        rng = sess.rng
        before = rng.getstate() if rng is not None else None
        st = _state(gold=30, shop=[_card(m)])
        _decide(st, sess)
        assert (rng.getstate() if rng is not None else None) == before

    def test_rng_neutral_static_lock(self):
        """R197 症5:rng 中立从注释契约升为测试锁——cw4 决策包源码零
        ``random`` 消费(静态扫描;运行期守卫不可行申报见
        sim/ab_core_swap.py docstring:局内 session rng 在引擎内按 seed
        派生,臂侧不可达,同 seed 自配对对「消费 rng」构造性不敏感)。"""
        import re
        from pathlib import Path

        pkg = Path(shop.__file__).parent
        pat = re.compile(r'\bimport random\b|\brandom\.')
        for py in sorted(pkg.rglob('*.py')):
            if '__pycache__' in py.parts:
                continue
            hits = [ln for ln in
                    py.read_text(encoding='utf-8').splitlines()
                    if pat.search(ln) and not ln.strip().startswith('#')]
            assert not hits, (py.name, hits)


# ===== R197 修复批行为测试(商店波同槽去重防线)=====

class TestR197SameSlotGuard:
    """症3:商店波卖面同槽冲突——先到先得丢弃 + 计数(与 prep 侧
    sold_slots/ev_conflict_dropped 同型),非 fail-stop 重发。"""

    def test_same_wave_double_sell_dropped_not_failstop(self):
        """同波同 bench_idx 双卖:M4 腾席已卖燃料槽 vs 支付支撑通道同
        槽提案 ⇒ 丢弃 + ``ev_conflict_dropped`` 计数,输出对同一
        bench_idx 至多一笔(执行侧 progressed=False fail-stop 不可达)。"""
        comp = _comp()
        members = _members(comp)
        m0 = members[0]
        bench = [_bc(m, slot=i + 1) for i, m in enumerate(members[1:])]
        while len(bench) < BENCH_CAPACITY:
            bench.append(_bc(f'填充件{len(bench)}', slot=len(bench) + 1))
        st = _state(gold=0, shop=[_card(m0, cost=3)], bench=bench)
        sess = _session(comp)
        acts = _decide(st, sess)
        sells = [a for a in acts if isinstance(a, SellBench)]
        # M4 卖首个填充件(唯一最低槽燃料);funding 提案同槽被丢弃
        assert sells, 'M4 腾席卖出应存在'
        idxs = [s.bench_idx for s in sells]
        assert len(idxs) == len(set(idxs)), idxs   # 无同 idx 双卖
        assert sess.cw4_counters.get('ev_conflict_dropped', 0) >= 1


# ===== K 空窗回退修复批行为锁(2026-09-03 第三病灶)=====

class TestKGapFallback:
    """K 空窗回退(方向 pass K 投影域覆盖 None;SEEDS_EMPTY_LEDGER_DIAG
    §4 第一案/IMPL_DESIGN §4.2.2 规格补注)——空窗死锁场景 K 回退
    非空 + M2 有候选发射;非空窗行为不变;契约正反见 contracts 测试件。"""

    def _gap_session(self) -> StrategySession:
        """空窗语境 session:target_comp=None + 意向供给在(v3_intention
        缺省态,update_target 未跑的首帧同款保守语义由 K 回退消费位
        gate 承载——本用例给齐供给帧,锁回退本体)。"""
        from sr_od.application.currency_war.kernel.cw_intention import (
            IntentionState,
        )
        s = _session(None)
        s.v3_intention = IntentionState()
        return s

    def test_gap_window_fallback_nonempty_and_m2_emits(self):
        """①空窗死锁场景:bench 支持度 <0.5(注册表外散件板面)⇒
        K 回退非空(hoard_target_set 单一源)+ 店面引擎件经 M2 发射
        + ``shop_k_fallback_p1_gap`` 计数。"""
        from sr_od.application.currency_war.kernel import cw_intention
        members = cw_intention._pair_members(cw_intention._P1_PAIR_PREF)
        engine_piece = sorted(members)[0]
        st = _state(gold=30,
                    shop=[_card(engine_piece, cost=3)],
                    bench=[_bc('注册表外散件Z', slot=1)])
        sess = self._gap_session()
        acts = _decide(st, sess)
        buys = [a for a in acts if isinstance(a, BuyCard)]
        assert any(b.card.name == engine_piece
                   and b.reason == 'm2_line_member' for b in buys)
        assert sess.cw4_counters.get('shop_k_fallback_p1_gap', 0) >= 1

    def test_gap_fallback_matches_hoard_single_source(self):
        """回退单一源:空窗帧 K 投影 == hoard_target_set().char_targets
        (禁复制四体系全集逻辑的行为锚;hoard 侧独立直算对拍)。"""
        from sr_od.application.currency_war.kernel import cw_intention
        st = _state(gold=30, bench=[_bc('注册表外散件Z', slot=1)])
        sess = self._gap_session()
        _decide(st, sess)
        expect = cw_intention.hoard_target_set(
            st, sess.v3_intention).char_targets
        assert expect                       # 空窗回退非空(四体系引擎件全集)
        assert sess.cw4_counters.get('shop_k_fallback_p1_gap', 0) >= 1

    def test_non_gap_support_at_threshold_lock_band_fallback(self):
        """②P1 锁线过渡带(FIX_REVIEW R3①,锁语义重推:原锁钉「≥门槛
        不回退」系值域覆盖半边形态,FIX_REVIEW ②缺口2 定谳为死带,本批
        扩域取代):bench 支持度 ≥0.5(桑博单件=DOT 1/2)⇒ 回退走
        p1_early_pair top-2 方向(``shop_k_fallback_p1_lock_band`` 计数,
        非 gap 键),店面方向件经 M2 发射;方向单一源对拍=与
        p1_early_pair_members 独立直算一致。"""
        from sr_od.application.currency_war.kernel import cw_intention
        st = _state(gold=30, bench=[_bc('桑博', slot=1)])
        assert not cw_intention.p1_gap_window(st)
        sess = self._gap_session()
        acts = _decide(st, sess)
        assert sess.cw4_counters.get(
            'shop_k_fallback_p1_lock_band', 0) >= 1
        assert 'shop_k_fallback_p1_gap' not in sess.cw4_counters
        expect = cw_intention.p1_early_pair_members(
            st, sess.v3_intention)
        assert expect            # 过渡带方向非空(支持度 ≥门槛)
        bought = {a.card.name for a in acts
                  if isinstance(a, BuyCard)
                  and a.reason == 'm2_line_member'}
        if bought:
            assert bought <= expect   # 只买方向件(与 top-2 单一源一致)

    def test_lock_band_matches_p1_early_pair_single_source(self):
        """过渡带单一源行为锚:回退成员集 == p1_early_pair_members
        (hoard_target_set 空窗全集仅在 pair 派生空时兜底,本帧不辖)。"""
        from sr_od.application.currency_war.kernel import cw_intention
        st = _state(gold=30, bench=[_bc('桑博', slot=1)])
        sess = self._gap_session()
        _decide(st, sess)
        assert cw_intention.p1_early_pair_members(
            st, sess.v3_intention) != cw_intention.hoard_target_set(
            st, sess.v3_intention).char_targets   # 两带集合确异(锁锚有效)

    def test_p2plus_unlocked_fallback_hoard_fifth(self):
        """③P2+ 带(FIX_REVIEW R3②,场景 D 复验):plane=2、
        target_comp=None ⇒ 回退走 hoard_target_set 分带(unlocked=
        绯英⑤兜底采购集),``shop_k_fallback_p2plus`` 计数,兜底线成员
        (爻光 ∈ 绯英欢愉 core)经 M2 发射;不再零买入。"""
        st = _state(gold=80, level=5)
        st.round_num = 10
        st.plane = 2
        st.shop = [_card('爻光', cost=3)]
        sess = self._gap_session()
        sess.v3_intention.phase = 'unlocked'
        acts = _decide(st, sess)
        assert sess.cw4_counters.get('shop_k_fallback_p2plus', 0) >= 1
        assert 'shop_k_fallback_p1_gap' not in sess.cw4_counters
        assert any(isinstance(a, BuyCard) and a.card.name == '爻光'
                   and a.reason == 'm2_line_member' for a in acts)

    def test_locked_line_unchanged(self):
        """②非空窗行为不变(锁线后):target_comp 非 None ⇒ K 投影=
        line_members(comp) 原样,回退分支不辖(既有 M2 用例全量覆盖
        本面,此处锁回退计数零)。"""
        comp = _comp()
        m = _members(comp)[0]
        sess = _session(comp)
        _decide(_state(gold=30, shop=[_card(m, cost=3)]), sess)
        assert 'shop_k_fallback_p1_gap' not in sess.cw4_counters

    def test_missing_intention_supply_no_fallback(self):
        """边界:v3_intention 缺失(意向供给缺帧)⇒ 保守侧不回退
        (现行 () 行为,与 committed_authority 缺供给保守侧同款)。"""
        from sr_od.application.currency_war.kernel import cw_intention
        members = cw_intention._pair_members(cw_intention._P1_PAIR_PREF)
        engine_piece = sorted(members)[0]
        sess = _session(None)     # 无 v3_intention
        st = _state(gold=30, shop=[_card(engine_piece, cost=3)],
                    bench=[_bc('注册表外散件Z', slot=1)])
        acts = _decide(st, sess)
        assert not [a for a in acts if isinstance(a, BuyCard)
                    and a.reason == 'm2_line_member']
        assert 'shop_k_fallback_p1_gap' not in sess.cw4_counters


# ===== ⑤⑥ sim 实跑门(慢桶)=====

@pytest.mark.slow
class TestSimGates:

    def test_baseline_self_pairing_zero_drift_n20(self):
        """⑤ 基线臂零漂移复跑:decision_v2 自配对 n≥20 ledger 逐位相等
        (透传拆除后证明本批没污染基线臂)。"""
        from sr_od.application.currency_war.sim.ab_core_swap import (
            baseline_self_pairing_gate,
        )
        report = baseline_self_pairing_gate(n=20, seed_base=0,
                                            pool='snapshot')
        assert report['ok'], report

    def test_arm_diff_existence_n6(self):
        """④ 双臂相异实证:小 n 配对 diff>0 且 ledger 可读
        (A/B 有测量对象的存在性证明,非正式 A/B)。"""
        from sr_od.application.currency_war.sim.ab_core_swap import (
            arm_diff_probe,
        )
        report = arm_diff_probe(n=6, seed_base=0, pool='snapshot')
        assert report['ok'], report
        probe = report['ledger_probe']
        assert probe is not None
        assert probe['baseline']['rows'] > 0
        assert probe['new_core']['rows'] > 0

    def test_new_core_self_pairing_n10(self):
        """R197 症5:新臂(mandate_v1)零漂移自配对门——同工厂双臂
        同 seed 同池 ledger 逐位相等(n≥10;确定性自检,与基线门对称;
        含池指纹守卫:指纹集非单元素 ⇒ raise)。"""
        from sr_od.application.currency_war.sim.ab_core_swap import (
            new_core_self_pairing_gate,
        )
        report = new_core_self_pairing_gate(n=10, seed_base=0,
                                            pool='snapshot')
        assert report['n'] == 10
        assert report['ok'], report
        assert report['pool_fingerprint']
