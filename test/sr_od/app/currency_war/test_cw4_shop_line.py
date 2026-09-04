"""cw4 步4b 商店线批测试(decide_shop_screen 接线验收全项)。

覆盖:criteria 七面商店形态单测(每面判据式行为锚)/ 词表+截断契约锁
(契约 v2 §3.1 逐类+§3.3 fail-closed)/ 修复池商店面检查点核销
(D-FM1/D-D/D-P2idle/D-F9·A45/D-BUYNOTE)/ ev_arm 臂形态(注入形态开闸
差异锚)/ 基线臂零漂移复跑 + 双臂相异实证(慢桶,sim 实跑)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY, get_comp
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    CloseShop,
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
from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof, shop
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import provisional
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
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
           level: int = 3, node=None, xp=None, hp: int = 100) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2, node_type=node,
                   hp=hp)
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
        """升级面:D-BUYNOTE 整买纪律——整批够升级才放行(散买拦截)。
        (夹具补 hp=100:候选③批起 M3 消费血预算停升级门,门对 hp 无真值
        帧 fail-closed 拒升级——旧夹具在门未接线的栈上写就,真值帧才是
        本锁要钉的语义。)"""
        # arm1_existence 需板满(10)+ bench 等待件共享阵营/流派:
        # 板/bench 同名件(爻光)必然共享 ⇒ 谓词真
        deployed = [_bc('爻光') for _ in range(10)]
        bench = [_bc('爻光')]
        # 整批不够:金 3 < clicks×cost
        st = _state(gold=3, bench=bench, deployed=deployed, level=3,
                    xp=(0, 4), hp=100)
        acts = _decide(st, _session(_comp()))
        assert not [a for a in acts if isinstance(a, LevelUpShop)]
        # 整批够:金 8 ≥ 1 click × 4(LEVEL up xp(0,4) → 1 click)
        st2 = _state(gold=8, bench=bench, deployed=deployed, level=3,
                     xp=(0, 4), hp=100)
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
        """刷新面:r1 可负担性不过(该帧合格集空:lv3 高费线成员不可追)
        ⇒ 不刷 + ``shop_r1_no_chaseable_member`` 分键(ADR-0516 形式二;
        旧 V_GAP None 期 fail-closed 语义随 V̄ 链退役,由判据结构承载)。"""
        comp = _comp()
        bench = [_bc(m) for m in _members(comp)]
        st = _state(gold=60, bench=bench)
        sess = _session(comp)
        _decide(st, sess)
        assert sess.cw4_counters.get('shop_r1_no_chaseable_member', 0) >= 1
        assert not [a for a in _decide(st, _session(comp))
                    if isinstance(a, RefreshShop)]

    def test_stockpile_face_m6_opens_with_frame_window(self):
        """压库面:T1 短路径后 M6 消费位窗口=帧级现算(塌缩带锚,
        ADR-0516 重锚),T_SEARCH_A 布尔门退役(设计 13_buy_face_design
        §2.3)——窗口非空帧正常买入。旧锁「T_SEARCH_A None ⇒ 溢余滞留」
        锁的是布尔门语义,已被 T1 取代(改锁重推:出处=13_buy_face_design
        §2.3「槽位布尔门退役」;滞留新语义=真无窗口帧,由
        test_cw_p56_t1 的 stub-registry 锁承载)。店牌=线成员副本:
        dominance 零重叠不过不抢,M6(不排线成员)独占评估。"""
        comp = _comp()
        members = _members(comp)
        bench = [_bc(m) for m in members]
        st = _state(gold=60, shop=[_card(members[0], cost=1)], bench=bench,
                    level=4)
        sess = _session(comp)
        acts = _decide(st, sess)
        assert any(isinstance(a, BuyCard) and a.reason == 'm6_stockpile'
                   for a in acts)

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


# ===== ② 终结 op 契约锁(ADR-0517 迁移批重锚;前身 = 截断契约锁)=====
# 锁语义重推:旧锁钉截断器行为(可续/条件续/截断点/fail-closed 截断),
# 截断器已随波批退役(截断点语义被终结 op 吸收,ADR-0517 §3)——本组
# 改锁单动作架构的对应不变量:终结集成员资格 / 词表外动作 fail-closed
# (shop_action_op_for 断言炸出)/ 合成触发买不再截断(投影承载)。

class TestShopTerminatorContract:

    def test_vocab_all_classes_covered(self):
        """词表锁:商店线动作 op 词表 = {BuyCard, LevelUpShop(is-a
        LevelUp), SellBench, RefreshShop, CloseShop, CompTransaction}
        (ADR-0517 迁移后可执行集;SellDeployed/DeployMove/SwapDeploy
        现行商店决策不发射——旧波批执行侧同样无分支,词表声明辖外)。
        PickEvent = pick 决策返回载体,词表外 fail-closed。"""
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            LevelUpOp,
            _OP_TABLE,
            shop_action_op_for,
        )
        classified = set(_OP_TABLE)
        union = (BuyCard, LevelUp, RefreshShop, SellBench, CloseShop,
                 CompTransaction)
        assert set(union) <= classified
        assert isinstance(shop_action_op_for(LevelUpShop(cost=4)), LevelUpOp)
        assert PickEvent not in classified          # 词表外(fail-closed)
        assert SellDeployed not in classified       # 不发射(辖外声明)
        assert DeployMove not in classified
        assert SwapDeploy not in classified
        assert issubclass(LevelUpShop, LevelUp)     # 升级意图商店屏子类

    def test_terminator_set_membership(self):
        """终结集锁(ADR-0517 决策 4/6):RefreshShop/CompTransaction/
        CloseShop = 终结动作 op(执行即本画面访问结束);买/升/卖 = 非
        终结(循环内投影续走)。"""
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            BuyCardOp,
            CloseShopOp,
            CompTransactionOp,
            LevelUpOp,
            RefreshShopOp,
            SellBenchOp,
            shop_action_op_for,
        )
        assert RefreshShopOp.terminal is True
        assert CompTransactionOp.terminal is True   # 终结邻接 fallback
        assert CloseShopOp.terminal is True         # 恒可用终结
        assert BuyCardOp.terminal is False
        assert LevelUpOp.terminal is False
        assert SellBenchOp.terminal is False
        # 工厂对终结成员的判定与类声明一致
        assert shop_action_op_for(RefreshShop(cost=2)).terminal
        assert shop_action_op_for(CloseShop()).terminal

    def test_word_table_violation_fail_closed(self):
        """词表外动作(PickEvent/任意类型)⇒ shop_action_op_for 断言炸出
        (ADR-0517 决策 9:非法返回 = 策略器 bug 响亮暴露,禁静默跳过——
        旧 §3.3 截断 fail-closed 的单动作继任形态)。"""
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            shop_action_op_for,
        )
        with pytest.raises(AssertionError, match='词表外'):
            shop_action_op_for(PickEvent(option_idx=0))
        with pytest.raises(AssertionError, match='词表外'):
            shop_action_op_for(object())   # type: ignore[arg-type]

    def test_proposal_guard_stale_slot_raises(self):
        """proposal-vs-expected 守卫(ADR-0517 §守卫两属 (i)):SellBench
        提案指向空槽/越界/名不符 ⇒ 断言炸出(旧「名-槽复检截断」的
        守卫继任形态——控制流跳过退役,防 bug 路栏保留)。"""
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            guard_proposal_vs_expected,
        )
        st = _state(bench=[_bc('甲'), _bc('乙')])
        with pytest.raises(AssertionError, match='名-槽不一致'):
            guard_proposal_vs_expected(
                SellBench(bench_idx=0, income=3, expect='乙'), st)
        with pytest.raises(AssertionError, match='空槽/越界'):
            guard_proposal_vs_expected(
                SellBench(bench_idx=5, income=3, expect='甲'), st)

    def test_expected_vs_tracked_guard_detects_drift(self):
        """expected-vs-tracked 双账断言(§守卫两属 (ii),投影建模 bug 的
        唯一在环检测器):期望态 bench 与 tracked 账分叉 ⇒ 炸出;一致 ⇒
        静默通过。"""
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            guard_expected_vs_tracked,
        )
        sess = _session()
        sess.tracked_bench_chars = [_bc('甲'), _bc('乙')]
        st = _state(bench=[_bc('甲'), _bc('乙')])
        guard_expected_vs_tracked(st, sess)      # 一致:静默
        st2 = _state(bench=[_bc('甲'), _bc('丙')])
        with pytest.raises(AssertionError, match='双账分离'):
            guard_expected_vs_tracked(st2, sess)

    def test_guard_attribution_seed_vs_project(self):
        """守卫两属消息分离(ADR-0517 §守卫两属 (ii) 迁移补裁):同一双账
        分叉按出现时点归因——首动作前(stage='seed')报「播种/入口账分叉」,
        投影后(默认 stage='project')报「project/mutate 模型分叉」。2026-09-05
        OpenShop 事故:播种层双源分叉曾被投影消息误标,误导排查方向。"""
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            guard_expected_vs_tracked,
        )
        sess = _session()
        sess.tracked_bench_chars = [_bc('甲')]
        st = _state(bench=[_bc('乙')])
        with pytest.raises(AssertionError, match='播种/入口账'):
            guard_expected_vs_tracked(st, sess, stage='seed')
        with pytest.raises(AssertionError, match='project/mutate'):
            guard_expected_vs_tracked(st, sess)

    def test_openshop_incident_frame_seed_rebuild_semantics(self):
        """OpenShop 事故帧锁(回归):tracked_bench_chars=[] + 残账
        tracked_bench 含陈旧名(2026-09-05 两起同型 HIT 实录:
        ①02:13 单笔——藿藿 02:11 买入进旧名账、RunDeploy 上场后主账被
        入口对账纠成真空,旧名账无人清理存活到开店被回退播种复活 →
        守卫首帧炸出 expected=[('藿藿',1)] tracked=[];
        ②02:26 双笔——买牌-部署循环两轮累积 ['藿藿','丹恒·饮月'],
        同签名分叉面扩大。复发频率 ≈ 每轮买牌-部署循环一次,残账
        随循环笔数线性累积,故事故帧覆盖单笔与多笔两形态)。

        锁形态选「缺席锁 + 入口重建语义锁」而非「播种后两账签名相等」:
        退役后事故帧构造本身消失(tracked_bench 字段已从 StrategySession
        删除),签名相等断言失去被测对象;更能拦回归的是两条——
        ①缺席锁(下一用例):全 src 无任何 tracked_bench 符号残留,
        回退播种在结构上不可能复活;
        ②入口重建语义:主账真空(bench 真空=全部署的事实正确态)时,
        播种结果必须为空、残账属性即使被人为挂回 session 也零影响,
        守卫静默、LevelUp 投影后仍静默——若未来任何代码重新读残账
        播种,state.bench 将出现陈旧名签名而本锁在 seed/project 两点
        响亮炸出。
        设计出处:docs/develop/currency_war/flow/screen_op.md §守卫两属;
        ADR-0517 决策 8(入口观察即对账,唯一真值源=入口读屏)。
        """
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            LevelUpOp,
            guard_expected_vs_tracked,
        )
        from sr_od.application.currency_war.kernel.cw_state import (
            LevelUp,
            bench_from_compact,
        )
        aop = LevelUpOp(LevelUp(cost=4))
        # 两形态:单笔(02:13 HIT)与多笔累积(02:26 HIT,两轮买-部署循环)
        for stale in (['藿藿'], ['藿藿', '丹恒·饮月']):
            sess = _session()
            sess.tracked_bench_chars = []      # 主账真空(入口对账纠成空=事实正确)
            sess.tracked_bench = stale         # 残账(退役后仅属性残留;任何回退读取=回归)
            sess.tracked_deployed = [_bc('藿藿'), _bc('艾丝妲'), _bc('银枝'), _bc('缇宝')]
            # 入口重建语义:真空主账 → 期望态 bench 必须为空(陈旧名不复活)
            st = _state(bench=bench_from_compact([]))
            guard_expected_vs_tracked(st, sess, stage='seed')   # 播种期:静默
            # 首动作 LevelUp 投影(bench 恒等变换)后:仍静默
            proj = aop.project(st)
            guard_expected_vs_tracked(proj, sess)               # project 期:静默
            assert all(b is None for b in proj.bench), \
                f'陈旧名被复活进期望态(残账={stale})'


    def test_tracked_bench_tombstone_scan(self):
        """缺席锁(墓碑扫描,测试纪律第 8 条合法源码扫描①):tracked_bench
        旧名账在 src 的 currency_war 子树零**代码级读写点**(词边界排除
        tracked_bench_chars;点号锚定属性访问,排除退役注释与同名局部变量
        ——两者不构成回退播种载体)。带变异自检:先证正则确实能命中属性
        访问形态,防正则失效的恒绿。事故背景 = 2026-09-05 OpenShop 双账
        分叉(残账回退播种复活陈旧名)。
        """
        import re
        from pathlib import Path
        import sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops as _mod
        cw_root = Path(_mod.__file__).parents[2]   # .../currency_war
        pat = re.compile(r'\.tracked_bench\b')
        # 变异自检:对属性访问命中;对合法同前缀名/注释/局部变量不命中
        assert pat.search('session.tracked_bench.append')
        assert not pat.search('session.tracked_bench_chars')
        assert not pat.search('# 旧 tracked_bench 回退分支已退役')
        assert not pat.search("tracked_bench = getattr(session, 'tracked_bench_chars')")
        hits = [str(p) for p in cw_root.rglob('*.py')
                if p.is_file() and pat.search(p.read_text(encoding='utf-8',
                                                       errors='replace'))]
        assert not hits, f'tracked_bench 旧名账读写点残留(回退播种载体未清):{hits}'

    def test_buy_and_levelup_continue_via_projection(self):
        """可续语义重锚:BuyCard/LevelUpShop 不终结循环——驱动器输出含
        后续动作且期望态推进(旧「可续不截断」的单动作继任形态:循环
        由投影续走,不存在截断点)。"""
        comp = _comp()
        m = _members(comp)[0]
        st = _state(gold=30, shop=[_card(m, cost=3), _card('燃料件X')])
        acts = _decide(st, _session(comp))
        assert acts and isinstance(acts[0], BuyCard)
        assert not isinstance(acts[-1], RefreshShop)   # 无截断性终结

    def test_merge_trigger_no_longer_truncates(self):
        """合成触发重锚:买同名同星第 3 张不再截断(旧
        shop_merge_trigger_truncate 计数随截断器退役)——投影(simulate
        内含合成连锁)承载期望态更新,驱动器循环继续至终结。"""
        comp = _comp()
        m = _members(comp)[0]
        st = _state(gold=30, shop=[_card(m, cost=3)],
                    bench=[_bc(m), _bc(m)])
        sess = _session(comp)
        acts = _decide(st, sess)
        # M2b 合并完成买入发生,且其后循环继续(CloseShop 收尾不产生
        # 额外动作;截断形态下该买会是末位——两者输出同形,语义差异由
        # 「投影后无停滞」承载:合成已入 bench,owned 集含该成员)
        assert any(isinstance(a, BuyCard) and a.card.name == m for a in acts)
        assert 'shop_merge_trigger_truncate' not in sess.cw4_counters

    def test_blackboard_missing_raises(self):
        """黑板契约:shop_state_frame 缺失 ⇒ 抛错(禁静默按空态决策)。"""
        from sr_od.application.currency_war.sim.engine_p1 import (
            sim_decision_registry,
        )
        strat = MandateV1Strategy(registry=sim_decision_registry())
        with pytest.raises(ValueError, match='shop_state_frame'):
            strat.decide_shop_screen(_session(), _Cfg())
        with pytest.raises(ValueError, match='shop_state_frame'):
            strat.decide_shop_action(_session(), _Cfg())


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
        """D-P2idle:带金零动作 visit 计数(gold≥10 且无发射)——键
        ``shop_visit_idle_gold``(单动作迁移批改名;语义 = CloseShop 收尾
        且金 ≥10 的 visit,旧 shop_wave_idle_gold 波计数不可对拍)。"""
        comp = _comp()
        bench = [_bc(m) for m in _members(comp)]   # 线成型,金低于 g*
        st = _state(gold=12, bench=bench)
        sess = _session(comp)
        _decide(st, sess)
        assert sess.cw4_counters.get('shop_visit_idle_gold', 0) == 1

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
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
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
            # 金 50(=g*):dominance 通道关(50>50 不成立)⇒ 店面该件归
            # EV 买面独占;P56 后 EV 金约束=可变现下界(g*−Σ活期退金),
            # bench 带 1 张燃料件(退 3)⇒ s_reserve=47,50−1=49≥47 过
            # (P56 批场景适配:旧 gold=30 在可变现下界下被 P56 正确拦截)
            bench = [_bc(m) for m in members] + [_bc('燃料件Y')]
            full = _decide(_state(gold=50, shop=[_card(outsider, cost=1)],
                                  bench=bench),
                           _session(comp), _Cfg('full'))
            skel = _decide(_state(gold=50, shop=[_card(outsider, cost=1)],
                                  bench=bench),
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


# ===== R197 同槽防线重锚(ADR-0517 迁移批)=====

class TestR197SameSlotGuard:
    """症3防线语义重推:旧锁钉「波内同 bench_idx 双卖先到先得丢弃 +
    ev_conflict_dropped 计数」——防线存在前提 = 波批多动作共享同一帧
    快照;单动作下第一笔卖出后期望态已更新,第二笔提案自然不指向已卖
    槽(ADR-0517 §消灭的 bug 类·同槽去重防线),发射侧丢弃通道退役。
    继任不变量:驱动器输出对同一 bench_idx 至多一笔卖出(结构性保证,
    非运行时丢弃);ev_conflict_dropped 键不再由商店线产生。"""

    def test_no_same_slot_double_sell_structurally(self):
        """R197 场景(金 0 + 满席 + 缺件):驱动器全部卖出对同一
        bench_idx 至多一笔——单动作结构保证,无丢弃计数参与。"""
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
        assert sells, 'M4 腾席卖出应存在'
        idxs = [s.bench_idx for s in sells]
        assert len(idxs) == len(set(idxs)), idxs   # 无同 idx 双卖
        assert 'ev_conflict_dropped' not in sess.cw4_counters


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
        """②P1 锁线过渡带(ADR-0519 重锚:锁线门槛 = 羁绊满员当量 1.0,
        旧 0.5「单件即锁」已退役):bench 支持度 1.0(DOT 满员=桑博+卡芙卡)
        ⇒ 回退走 p1_early_pair top-2 方向(``shop_k_fallback_p1_lock_band``
        计数,非 gap 键),店面方向件经 M2 发射;方向单一源对拍=与
        p1_early_pair_members 独立直算一致。"""
        from sr_od.application.currency_war.kernel import cw_intention
        st = _state(gold=30, bench=[_bc('桑博', slot=1), _bc('卡芙卡', slot=2)])
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
        st = _state(gold=30, bench=[_bc('桑博', slot=1), _bc('卡芙卡', slot=2)])
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


# ===== ⑦ 对抗修复批:F1 满栏 EV 买收敛(席位门)=====

class TestEvBuySeatGate:
    """满栏 + EV 候选在场 ⇒ EV 买不提案(shop.py EV pass 席位门,与
    dominance_buy 的 check_seats 同款);决策循环有限步收敛。

    根因形态(对抗发现):EV 候选非义务面、无 M4 腾席前置;满栏帧
    BuyCard 的 simulate 投影走「bench_full 整动作 no-op」分支(不合成
    即金不扣、牌不下架、bench 不减员)⇒ 下一帧同提案同候选 = 无限循环。
    候选生成经 monkeypatch 钉非空(锁「席位门」这一控制流,不锁候选
    生成的数值面——后者归 criteria 各自的判据锁)。
    """

    @staticmethod
    def _full_bench(comp):
        bench = [_bc(m) for m in _members(comp)]
        while len(bench) < BENCH_CAPACITY:
            bench.append(_bc(f'填充件{len(bench)}'))
        return bench

    def test_ev_buy_bench_full_not_proposed(self, monkeypatch):
        """满栏帧 EV 买不提案 + ``shop_ev_bench_wait`` 分键计数
        (帧级断言:满栏帧的首提案不是 ev_buy;席被其它通道腾出后
        EV 买合法恢复,归帧级不变量测试辖)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
            buy as crit_buy,
        )
        comp = _comp()
        fuel = '燃料件X'
        st = _state(gold=30, shop=[_card(fuel, cost=1, star=1)],
                    bench=self._full_bench(comp))
        monkeypatch.setattr(
            crit_buy, 'ev_buy_candidates',
            lambda gold, s_reserve, shop_cards, k_members, **kw:
            ([crit_buy.BuyCandidate(fuel, 1, 1, 0)], ''))
        monkeypatch.setattr(crit_buy, 'ev_buy_veto',
                            lambda cand, gold: (False, ''))
        sess = _session(comp)
        a = self._decide_one(st, sess)
        assert not (isinstance(a, BuyCard) and a.reason == 'ev_buy')
        assert sess.cw4_counters.get('shop_ev_bench_wait', 0) >= 1

    @staticmethod
    def _decide_one(state, session):
        from sr_od.application.currency_war.sim.engine_p1 import (
            sim_decision_registry,
        )
        strat = MandateV1Strategy(registry=sim_decision_registry())
        session.shop_state_frame = state
        return strat.decide_shop_action(session, _Cfg('full'))

    def test_ev_buy_bench_full_segment_converges(self, monkeypatch):
        """生产段循环同构驱动:满栏 + 恒非空 EV 候选下,单动作循环按
        帧推进有限步到达终结(CloseShop/RefreshShop),不触发执行侧
        帧帽(cw_op_buy_cards.SHOP_SEGMENT_ACTION_CAP);帧级不变量 =
        EV 买提案只发生在 bench 有空席的帧(席位门语义)。"""
        from sr_od.application.currency_war.kernel.cw_state import simulate
        from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
            SHOP_SEGMENT_ACTION_CAP,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
            buy as crit_buy,
        )
        comp = _comp()
        fuel = '燃料件X'
        st = _state(gold=30, shop=[_card(fuel, cost=1, star=1)],
                    bench=self._full_bench(comp))
        monkeypatch.setattr(
            crit_buy, 'ev_buy_candidates',
            lambda gold, s_reserve, shop_cards, k_members, **kw:
            ([crit_buy.BuyCandidate(fuel, 1, 1, 0)], ''))
        monkeypatch.setattr(crit_buy, 'ev_buy_veto',
                            lambda cand, gold: (False, ''))
        sess = _session(comp)
        sess.shop_state_frame = st
        terminated = False
        for _frame in range(SHOP_SEGMENT_ACTION_CAP):
            cur = sess.shop_state_frame
            _free = BENCH_CAPACITY - len(
                [b for b in (cur.bench or []) if b is not None])
            a = self._decide_one(cur, sess)
            if isinstance(a, BuyCard) and a.reason == 'ev_buy':
                assert _free > 0, 'EV 买提案帧 bench 须有空席(席位门)'
            if isinstance(a, (CloseShop, RefreshShop)):
                terminated = True
                break
            sess.shop_state_frame = simulate(cur, a)
        assert terminated, '满栏 + EV 候选在场:段循环须有限步到达终结'


# ===== ⑤⑥ sim 实跑门(慢桶)=====

@pytest.mark.slow
class TestSimGates:

    # (基线自配对门/双臂相异探针已随基线臂退役删除——统一迁移批 ② A9;
    #  单臂确定性自检 = 下方 new_core 自配对门。)
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
