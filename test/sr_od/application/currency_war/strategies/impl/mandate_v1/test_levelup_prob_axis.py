"""CW 升级判据重轴单帧测试(迭代 2026-10-12-prep-shop-workflow-redesign 批 3.4)
+ P2 低血带授权域(fail-closed 落码)。

出处(持久索引):details/line_and_upgrade.md §2(触发五臂/支出形态/
拦截层处置)与 §2.3 处置表;design.md 条 4(升级判据重轴)。判据本体 =
strategies/impl/mandate_v1/criteria/levelup.py,发射位 = entry 备战第
3 步。测试面组:

1. 带与停留门(prob_band_of_cost 平顶整段/三支分派/P1 硬锁子局断言);
2. 概率账(触发/不触发/辖域双条件);
3. 发射形态(凑金一卖 → 下一帧整批——「买一半」由发射原子性消解,
   2026-10-17 迭代 design §2.2;授权不跨帧携带,键已退役;
   血本位不足零购买/血足整批发射;金不足攒钱模式;等级帽拒发);
4. 保留语义(P72(3a) 保底金门/P21 危机带/FM-1 金支出出口);
5. 【拟】槽与兜底(缺件集聚合口径 provisional 登记;P78-5 兜底豁免
   消费循环拼装对拍)。

构帧纪律:锁定线经 session_scope.write_line_lock(3.1 键,同帧种子后写);
plane2_started 经 node_hist_pos 直赋 + handle_node_boundary 置位(单调
水位驱动,3.1 口径)。

P2 血带节(原 P2 低血带授权域统一件):单一语义权威 = 生产符号
(谓词/授权闩 = statefn.predicates,停付面 = criteria/levelup,
分键写入端 = flow)。校验两类事:①p2_blood_floor 域谓词真值表(信任门/
阈值单一源 = HP_BAND_NEAR_DEATH,位面域互补);②危机带停付面 + 凑息
拒因键域(血线拒因键退役)。保底金门真值表 = 本文件
TestRetainedGates::test_guarantee_floor_gate_truth_table 承载,不重复。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bsb,
)
from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionLevelUpParam,
    CwActionSellBenchParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    session_scope as _ss,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    levelup,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

#: 锁定线样本(希儿量子):need_star = 希儿 3★(3 费,带 (7,7))+
#: 花火/符玄/缇宝/刻律德菈辅助 1★(持有即完成)——停留目标可控构帧
#: 的最小线(唯一 3★ 目标 = 希儿)。
_LOCK_LINE = '希儿量子'
#: 辅助达标集(need_star=1 持有即完成;构帧排除辅助缺件对停留目标的
#: 低费干扰——停留目标 = 未完成目标中费用档最低者,line_and_upgrade
#: §2.1)。
_AUX_DONE = ('花火', '符玄', '缇宝', '刻律德菈')


def _frame(*, level: int, gold: int = 30, plane: int = 2,
           hist: tuple[int, int] | None = (2, 1), bench: tuple = (),
           front_row: tuple = (), hp: int = 60, locked: bool = True,
           actives: tuple = (), deploy_cap: int | None = None) -> tuple:
    """判据帧构造(单容器直构 + 锁定键/窗口谓词按 3.1 口径落位)。

    ``hist`` = node_hist_pos 直赋值(None = 不赋——P1 未置位形态经
    (1, n) 表达);返回 (gs, session)——session = gs 同容器实例
    (生产链 emit 的 session 形参即容器,state_of 动态挂载同宿主)。
    """
    gs = cw4_gs(None, gold=gold, level=level, round_num=2, node='战斗',
                hp=hp, plane=plane, bench=list(bench),
                front_row=list(front_row), active_strategies=list(actives),
                deploy_cap=deploy_cap)
    if hist is not None:
        gs.node_hist_pos = hist
    _ss.handle_node_boundary(gs)   # 窗口谓词置位(node_hist_pos 水位驱动)
    if locked:
        _ss.write_line_lock(gs, _LOCK_LINE)
    # 边界处理按重置表清金位账面(读数协议失效语义,3.6);测试帧 =
    # 边界后稳态,重新锚定账面并钉位判重键(失效行为测试显式置 None)。
    _st = state_of(gs)
    _st.gold_ledger = int(gold)
    _st.node_boundary_last_pos = (int(plane), 2)
    return gs, gs


def _stay_bench(xili_star: int = 1) -> list:
    """停留目标可控的 bench(辅助达标 + 希儿按参):唯一未完成目标 =
    希儿(3 费 3★)。"""
    return [_bc(n, 1) for n in _AUX_DONE] + [_bc('希儿', xili_star)]


def _mark_handled(gs) -> None:
    """商店会话标记(帧直达第 3 步后不被第 4 步开店截胡)。"""
    node = gs.node.value
    gs.observe(gs.node_pos,
               (int(node.plane), int(node.round_num)) if node else (2, 2),
               sig=ChannelSig(family='obs', actor='cw4_seed',
                              mode='synthesized'))
    _ss.mark_shop_handled(gs)


# ===== 1. 带与停留门(line_and_upgrade §2.1)=====


class TestProbBand:
    def test_band_plateau_and_domain_peak(self):
        """带 = 搜索域 1..9 内 REFRESH_PROB 峰值区间(平顶整段):1 费
        带 (1,3)(平顶)、3 费 (7,7)、4/5 费 (9,9)(全域峰在 lv10 取域内
        峰——禁「全域最高值区间 ∩ ≤9」写法,4/5 费会得空集);带上界
        与 peak_refresh_level 在产表同值(单点峰形态 = 带上界,域上限
        校验非带定义本体)。"""
        from sr_od.application.currency_war.data.cw_shop_odds import (
            refresh_prob,
        )
        from sr_od.application.currency_war.kernel.cw_plane_table import (
            peak_refresh_level,
        )
        for cost in (1, 2, 3, 4, 5):
            lo, hi = levelup.prob_band_of_cost(cost)
            assert 1 <= lo <= hi <= 9, f'{cost} 费带出域'
            assert hi == peak_refresh_level(cost), \
                f'{cost} 费带上界 ≠ peak_refresh_level(域上限校验断裂)'
            peak = max(refresh_prob(lv, cost) for lv in range(1, 10))
            for lv in range(lo, hi + 1):
                assert refresh_prob(lv, cost) == peak, \
                    f'{cost} 费带成员 lv{lv} 非峰值(带成员由 REFRESH_PROB 直算)'


class TestStayGate:
    def test_three_way_dispatch(self):
        """停留门三支分派(①②③同一等级轴上互斥完备;shop_session
        §2.4 主式 = ②∨③ 支为真时停留刷新,①支 = 升级优先):
        ①等级 < 带下界(lv5 < 7)→ 升级臂触发(升到带内去刷);
        ②等级 ∈ 带(lv7)→ 停留刷新,升级臂不触发;
        ③等级 > 带上界(lv8 被推过,单调不可降,当前即剩余可达最优)
        → 照样停留刷新,升级臂不触发。停留目标 = 未完成星级目标中
        费用档最低者(构造 = 辅助达标后唯一目标希儿 3 费)。"""
        gs, s = _frame(level=5, gold=30, bench=_stay_bench())
        assert levelup.stay_gate_upgrade_first(gs, s) is True
        assert levelup.upgrade_trigger(gs, s) == (True, levelup.ARM_STAY_GATE)
        gs7, s7 = _frame(level=7, gold=30, bench=_stay_bench())
        assert levelup.stay_gate_upgrade_first(gs7, s7) is False, \
            '等级 ∈ 带:停留刷新,延迟升级'
        gs8, s8 = _frame(level=8, gold=30, bench=_stay_bench())
        assert levelup.stay_gate_upgrade_first(gs8, s8) is False, \
            '等级被硬需求推过带上界:当前即剩余可达最优,照样停留刷'

    def test_p1_hard_lock_subgame_zero_rush(self):
        """P1 硬规则锁定子局断言(line_and_upgrade §2.1 双条件判据位):
        锁定 ∧ plane2 未启动(P1)∧ 星级目标存在(希儿 3★ 未完成)∧
        带下界 7 > 等级 5——停留门臂与概率账均**不触发**(P1 不冲级:
        概率账收益 = P2 起未来刷新期望改善,P1 视界内不消费;升级侧
        排除全靠判据位,非刷新层拦截)。金位 < 息线排除溢余臂干扰。"""
        gs, s = _frame(level=5, gold=30, plane=1, hist=(1, 5),
                       bench=_stay_bench())
        assert levelup.stay_gate_upgrade_first(gs, s) is False
        assert levelup.prob_account_ok(gs, s) is False
        assert levelup.upgrade_trigger(gs, s) == (False, '')

    def test_unlocked_or_done_targets_inert(self):
        """辖域负控:未锁定期(锁定线槽空)停留门/概率账不辖(双条件
        判据位);锁定后停留目标全部完成(need_star 达标)→ 停留刷
        完成,升级臂不触发(停刷存钱升下一目标或人口位)。"""
        gs, s = _frame(level=5, gold=30, locked=False, bench=_stay_bench())
        assert levelup.stay_gate_upgrade_first(gs, s) is False
        assert levelup.prob_account_ok(gs, s) is False
        gs2, s2 = _frame(level=7, gold=30,
                         bench=_stay_bench(xili_star=3))
        assert levelup.unfinished_star_targets(gs2) == []
        assert levelup.stay_gate_upgrade_first(gs2, s2) is False


# ===== 2. 概率账(line_and_upgrade §2.1 主判据)=====


class TestProbAccount:
    def test_trigger_and_non_trigger(self):
        """概率账触发/不触发:锁定后 ∧ plane2 ∧ 单核代表(希儿 3 费,
        lv5→6 概率 0.20→0.25 上行,E 下降量 × c_eff > 整级成本+息损)
        → True;等级 ∈ 峰值带(lv7→8 概率 0.40→0.32 回落,benefit ≤ 0)
        → False。缺件集聚合 = 单核代表【拟】(provisional 槽
        LEVELUP_MISSING_SET_AGG,None = 单核;求和/瓶颈切换候选未决前
        一律单核,line_and_upgrade §2.1/§4 两处同口径)。"""
        gs, s = _frame(level=5, gold=30, bench=_stay_bench())
        assert levelup.prob_account_ok(gs, s) is True
        gs7, s7 = _frame(level=7, gold=30, bench=_stay_bench())
        assert levelup.prob_account_ok(gs7, s7) is False, \
            '带内回落段无收益面(benefit ≤ 0 拒)'

    def test_missing_set_agg_slot_registered(self):
        """缺件集聚合口径【拟】槽登记对拍(audit/provisional.py):
        LEVELUP_MISSING_SET_AGG 在槽位表(fail-closed None = 单核代表
        在产保守形态);切换口径未落消费面——注入非单核值时判据回单核
        (fail-closed 禁未决口径混用)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
            provisional,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.audit.provisional import (
            CalibValue,
        )
        assert 'LEVELUP_MISSING_SET_AGG' in provisional.slot_names()
        gs, s = _frame(level=5, gold=30, bench=_stay_bench())
        try:
            provisional.inject('LEVELUP_MISSING_SET_AGG',
                               CalibValue(value=1.0, injected_form=True))
            assert levelup.prob_account_ok(gs, s) is True, \
                '切换口径未落消费:fail-closed 回单核代表,判据不变'
        finally:
            provisional.reset('LEVELUP_MISSING_SET_AGG')


# ===== 3. 发射形态(单帧原子发射;「买一半」回归测试)=====


class TestBatchEmission:
    def test_gold_short_full_batch_no_partial_buy(self):
        """金不足整批不买(line_and_upgrade §2.2 攒批资金口径):触发帧
        裸金与活期合计 < 整级批成本 + 花后金下界 → 一击不买(攒钱模式,
        零升级动作)——禁按闸值截断击数的部分买(P48 整买
        (1) 辖域,「买一半」的对面断言)。"""
        gs, s = _frame(level=5, gold=12, bench=_stay_bench())
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '攒批不足:零购买(攒钱模式)'
        ct = state_of(s).cw4_counters
        # 优化臂(stay_gate)语境:攒批不足先撞息线差额保留
        # (levelup_reserve_line_defer——攒批目标 = 整级成本 + 息线差额,
        # 保守侧);义务臂语境对照 = FM-1 溢余帧照发
        assert ct.get('levelup_reserve_line_defer') == 1

    def test_blood_insufficient_zero_buy_blood_sufficient_batch(self):
        """「买一半」缺陷回归测试(血本位局,line_and_upgrade §2.2 血本位
        突变下的支付检查):血余额 < 整级血成本 → 零购买(攒血,不置键
        不发射);血余额 ≥ 整级血成本 → 整批发射(clicks = 门槛表差值
        折击数,一次买齐)。发射粒度整批化后无逐帧重闸复发面。"""
        # 血不足:奋斗协议(每击血价注册表)∧ hp 低于整级血成本
        gs, s = _frame(level=5, gold=30, hp=5, bench=_stay_bench(),
                       actives=('奋斗协议',))
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '血本位局血不足整级:零购买([40]② 血闸)'
        # 血足:整批发射
        gs2, s2 = _frame(level=5, gold=30, hp=100, bench=_stay_bench(),
                         actives=('奋斗协议',))
        _mark_handled(gs2)
        out2 = entry.emit(s2, None)
        ups = [e for e in out2 if isinstance(e.action, CwActionLevelUpParam)]
        assert ups and ups[0].action.clicks >= 1, \
            '血足整级:整批发射(实付上界 = 发射时血成本;无变现步,授权帧即执行帧)'

    def test_level_cap_rejects(self):
        """等级帽拒发(注册表 level_max 单一源):满级帧零购买 +
        levelup_reject_level_cap 分键。"""
        gs, s = _frame(level=10, gold=80, bench=_stay_bench())
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)]
        assert state_of(s).cw4_counters.get('levelup_reject_level_cap') == 1

    def test_authorize_liquidate_then_execute_batch(self):
        """凑金一卖 → 下一帧整批发射(2026-10-17 迭代 T-2 单帧原子形态,
        design §2.2:授权不再跨帧携带——「买一半」由发射原子性消解,
        实付上界 = 发射时授权值):帧 1(命中 ∧ 资金门金量不足,花后
        下界已过)→ 凑金每帧一卖(评估器升级凑金场景首位);帧 2(裸金
        足)→ 整批发射 + 清 handled 标记(发射完成重开通道,design
        §2.2 第 1 条)。三帧各一动作(单动作循环),帧间零商店域外金动作。"""
        # lv7 整级批 = ⌈52/4⌉×4 = 52 金;裸金 51(< 52)+ 活期散件
        # ×4(c0/c1/c2/c4 各退 3,注册表外散件按保守估——不同名互不
        # 构成合成素材)→ 攒批 63 ≥ 52;花后 11 ≥ 保底金门 10;
        # 溢余段 51 > 息线 50 → must_spend 臂辖。
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        bench = _stay_bench() + [_bc(n, 1) for n in ('c0', 'c1', 'c2', 'c4')]
        gs, s = _frame(level=7, gold=51, bench=bench,
                       front_row=(Unit(char_id='板上件锚', star=1),))
        _mark_handled(gs)
        # 帧 1(凑金帧):命中 ∧ 裸金不足 → 一卖(评估器升级凑金场景)
        out1 = entry.emit(s, None)
        sells1 = [e for e in out1
                  if type(e.action).__name__ in ('CwActionSellBenchParam',
                                                 'CwActionSellDeployedParam')]
        assert sells1 and sells1[0].action.reason == 'levelup_liquidate', \
            '凑金帧:裸金不足 → 每帧一卖(评估器升级凑金场景)'
        # 帧 2(发射帧):缺口闭合(退金 3 → 54 ≥ 52)→ 单帧原子整批
        if isinstance(sells1[0].action, CwActionSellBenchParam):
            from sr_od.application.currency_war.kernel.cw_action_report.sell_bench import (
                report_action_sell_bench_param,
            )
            report_action_sell_bench_param(
                gs, sells1[0].action,
                sig=ChannelSig(family='logic_action', actor='CwScreenPrep'))
        else:
            from sr_od.application.currency_war.kernel.cw_action_report.sell_deployed import (
                report_action_sell_deployed_param,
            )
            report_action_sell_deployed_param(
                gs, sells1[0].action,
                sig=ChannelSig(family='logic_action', actor='CwScreenPrep'))
        out2 = entry.emit(s, None)
        ups = [e for e in out2 if isinstance(e.action, CwActionLevelUpParam)]
        assert ups and ups[0].action.clicks == 13, \
            '发射帧:缺口闭合 → 购买经验整批(13 击 = ⌈52/4⌉,单帧原子)'
        assert state_of(s).shop_handled is None, \
            '发射完成清 handled 标记(升级后概率档已变,找牌/刷新需重评)'


# ===== 4. 保留语义(P72(3a) floor / P21 / FM-1)=====


class TestRetainedGates:
    def test_guarantee_floor_gate_truth_table(self):
        """P72(3a) 内保底金门保留(line_and_upgrade §2.3 单一裁决):
        花后金 ≥ 1 息档(boss_floor)→ 放行;< → 拒;出辖两支(终局域
        末战 ALL IN / 买断制)→ 不设下界。血线让位支已随血线地板删除
        链退役(hp 不再豁免下界)。"""
        sess = SimpleNamespace(node_type_current='normal')
        gs, _ = _frame(level=5, gold=30)
        # 花后 30-4 = 26 ≥ 10 → 放行;花后 5-4 = 1 < 10 → 拒
        assert levelup.guarantee_floor_gate(gs, sess, 30, 1, 4, 5) is True
        assert levelup.guarantee_floor_gate(gs, sess, 5, 1, 4, 5) is False
        # hp 不可再豁免(血线让位支退役)
        gs_hp, _ = _frame(level=5, gold=5, hp=1)
        assert levelup.guarantee_floor_gate(gs_hp, sess, 5, 1, 4, 5) is False
        # 买断制(cap=0)出辖
        assert levelup.guarantee_floor_gate(gs, sess, 1, 1, 4, 0) is True

    def test_p21_crisis_band_retained(self):
        """P21 血预算线保留(§2.3 保留件):危机带(hp ≤ p2_crisis_band
        ≈41)域外帧停付;血线地板解锁让位支已退役(死亡线帧照常停付
        ——濒死响应 = 修经济/阵容本身)。"""
        gs, _ = _frame(level=5, gold=30, hp=10)
        sess = SimpleNamespace(node_type_current='normal')
        assert levelup.level_spend_blocked(gs, sess) is True, \
            'P2 濒死帧(hp 10 ⊂ 危机带 41):停付照常(血线让位支退役)'

    def test_fm1_gold_exit_open_in_surplus(self):
        """FM-1 金支出出口核对(11 §5 金支出出口要求——持金至死死型
        防线):溢余帧(gold 100 > 息线 50)升级通道可达——拦截层删净
        后金支出出口不灭(溢余段-L3 臂触发 + 整批发射;守息门/量闸
        已删,金位单调段不闷死)。"""
        gs, s = _frame(level=5, gold=100, bench=_stay_bench())
        _mark_handled(gs)
        out = entry.emit(s, None)
        ups = [e for e in out if isinstance(e.action, CwActionLevelUpParam)]
        assert ups, 'FM-1:溢余金帧升级通道开放(金支出出口)'
        assert ups[0].action.auth_basis == levelup.ARM_MUST_SPEND

    def test_optimization_arm_reserve_line_defer(self):
        """优化臂息线差额保留(差分节确认前 fail 态):停留门臂触发 ∧
        花后金 < 息线(保守侧,「花完仍守 50」)→ 整批推迟零动作
        (levelup_reserve_line_defer 分键;义务臂不受攒息约束对照 =
        上例溢余帧照发)。"""
        gs, s = _frame(level=5, gold=30, bench=_stay_bench())
        # lv5 批 = ⌈20/4⌉×4 = 20;花后 30+0-20 = 10 < 息线 50 → 推迟
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '停留门臂:花后金 < 息线差额保留 → 整批推迟(保守侧)'
        assert state_of(s).cw4_counters.get(
            'levelup_reserve_line_defer') == 1

    def test_guarantee_floor_defer_counter(self):
        """花后下界 defer 分键(义务臂 = 保底金门口径;七道资格门拒因
        计数补全,2026-10-17 迭代 T-4):富余段臂命中 ∧ 花后金 < 保底
        → defer 在册(levelup_guarantee_floor_defer,与优化臂的
        levelup_reserve_line_defer 分键区分)。判定函数直测(计数写点 =
        判定函数;emit 级同帧会被部署步发射截断,非本断言面)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        # must_spend 臂(51 > 息线 50);lv7 批 52,活期 3 件退 9 →
        # 花后 51+9−52 = 8 < 10 → 保底金门拒。
        bench = [_bc('c0', 1), _bc('c1', 1), _bc('c2', 1)]
        gs, s = _frame(level=7, gold=51, bench=bench,
                       front_row=(Unit(char_id='花火', star=1),))
        verdict, arm, _clicks, _cost = levelup.upgrade_gate_verdict(
            gs, s, counters=state_of(s).cw4_counters)
        assert verdict == levelup.GATE_DEFER
        assert state_of(s).cw4_counters.get('levelup_trigger_must_spend') \
            == 1, '富余段臂触发在册(defer 元组不携臂,臂经触发计数证)'
        assert state_of(s).cw4_counters.get(
            'levelup_guarantee_floor_defer') == 1, '保底金门分键在册'


# ===== 5. P78-5 兜底豁免消费循环拼装(design 契约 D 升级变现行)=====


class TestFundingHoldFallback:
    def test_fallback_leg1_duty_arm_emits_core(self):
        """P78-5′ 腿①(义务血统臂,验臂):arm0 触发的升级,兜底全量
        消费——凑金语境(命中 ∧ 金量不足,花后下界已过)下主路径尽
        (线内/保护/合成对全排除)∧ hold 核心件(三月七,非锁定线成员)
        经 funding_hold_fallback 放行、单笔即止(levelup_funding_
        fallback_sell 分键;单一源 = sell_gate.funding_hold_fallback,
        消费循环只拼装)。design 契约 D 升级变现行豁免构成 = 义务账 ∨
        对象无损;义务账腿候选 = 人口位/arm0 骨架义务血统(review-34
        F1 落码)。臂身份 = 本帧资格门判定臂(键退役后无跨帧携带)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        # arm0 构帧:level 3 < deploy_cap 5 ∧ 上阵需求 5 > 3(部署 1 希儿
        # + 备战 4 线内未上);lv3 批 = 4 金,裸金 3 < 4;合成对 ×2(各退
        # 3)供花后下界(3+12−4 = 11 ≥ 10)且被素材守卫逐出主路径 →
        # 主路径尽,兜底池唯三月七(贯穿件,腿①义务臂全量放行)。
        bench = [_bc(n, 1) for n in ('花火', '符玄', '缇宝', '刻律德菈')]
        bench += [_bc('三月七', 1), _bc('c0', 1), _bc('c0', 1),
                  _bc('c1', 1), _bc('c1', 1)]
        gs, s = _frame(level=3, gold=3, deploy_cap=5, bench=bench,
                       front_row=(Unit(char_id='希儿', star=1),))
        _mark_handled(gs)
        out = entry.emit(s, None)
        sells = [e for e in out
                 if isinstance(e.action, CwActionSellBenchParam)]
        assert sells and sells[0].action.reason == 'levelup_liquidate', \
            '腿①:义务臂兜底全量(主路径尽 → 核心件放行)'
        assert state_of(s).cw4_counters.get(
            'levelup_funding_fallback_sell') == 1

    def test_fallback_leg2_preference_arm_rejects_core(self):
        """P78-5′ 腿②(对象级无损维,验对象非验触发臂):偏好账臂
        (停留门/概率账/溢余段-L3——P78-5′ 账性判别上零息损不构成
        「不做会输」= 偏好账)触发的升级,兜底变卖核心/④件被拒——
        被放行对象须持有账 ≈ 0(非核心/非④件 ∧ 非种子);funding_
        hold_fallback 兜底池 ⊆ hold 核心集(池条件 = holds ∩ A 排除),
        偏好臂下结构性恒拒(levelup_fallback_leg_reject 分键 + 零动作;
        review-34 F1:校验两腿分派语义)。凑金语境构帧 = must_spend 臂
        (偏好账):溢余段触发 ∧ 裸金差一口 ∧ 合成对撑花后下界且主路径
        尽。臂分派真值表经判定函数直测补全(臂身份 = 本帧判定臂,键退役
        后无跨帧携带;stay/prob 臂的金量不足域受息线差额保留结构性
        收窄,emit 级构帧不可达,直测承载)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        # must_spend 臂:lv7 批 52,裸金 51(> 息线 50 触发富余段臂);
        # 合成对 ×3(退 18)撑花后 51+18−52 = 17 ≥ 10 且被逐出主路径;
        # 兜底池唯三月七(贯穿件)→ 腿②拒(持有账 > 0)。
        bench = [_bc('三月七', 1), _bc('c0', 1), _bc('c0', 1),
                 _bc('c1', 1), _bc('c1', 1), _bc('c2', 1), _bc('c2', 1)]
        gs, s = _frame(level=7, gold=51, bench=bench,
                       front_row=(Unit(char_id='花火', star=1),))
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionSellBenchParam)], \
            '腿②:偏好臂兜底核心件被拒(零动作)'
        assert state_of(s).cw4_counters.get('levelup_fallback_leg_reject') \
            == 1, '腿拒分键'
        assert state_of(s).cw4_counters.get('levelup_liquidate_exhausted') \
            == 1, '候选穷尽分键(腿拒后凑金穷尽,零动作等节点收入)'
        # 两腿分派真值表(判定函数直测;义务臂全量 / 偏好账与缺省保守侧
        # 对 hold 核心恒拒):
        for arm, ok in ((levelup.ARM_POPULATION, True),
                        (levelup.ARM_ARM0, True),
                        (levelup.ARM_MUST_SPEND, False),
                        (levelup.ARM_STAY_GATE, False),
                        (levelup.ARM_PROB_ACCOUNT, False),
                        ('', False)):
            assert entry._fallback_legs_ok(s, gs, arm, '三月七') is ok, arm


    def test_population_arm_triggers(self):
        """人口位三元触发(line_and_upgrade §2.1 三元谓词完整保留:
        板满 ∧ 阵营相关等待件不限星级 ∧ 边际贡献 > 0 由结构承载):
        cap 满帧 + bench 同羁绊等待件 → pop_slot 臂触发。"""
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        # 板满构帧:cap 2 = 板上两人;bench 等待件与板共享羁绊(知更鸟/
        # 那刻夏同属追击系,阵营经注册表派生)
        board = (Unit(char_id='知更鸟', star=1),
                 Unit(char_id='那刻夏', star=1))
        gs, s = _frame(level=1, gold=30,
                       bench=(_bc('知更鸟', 1),),
                       front_row=board, deploy_cap=2)
        trig, key = levelup.upgrade_trigger(gs, s)
        assert trig and key == levelup.ARM_POPULATION, \
            '板满 ∧ 同羁绊等待件:人口位三元触发'


# ===== 6. P2 低血带授权域(谓词 + 危机带停付面)=====


class TestP2BloodBand:

    def _st2(self, hp: int | None = 10, plane: int = 2, gold: int = 30,
             round_num: int = 2, level: int = 7,
             node_type: str | None = None) -> dict:
        """P2 濒死带场景种子轴(hp 缺省 10 ⊂ ≤15 带;返回 = ``_bsb``
        kwargs,hp=None = 域未观察)。"""
        axes: dict = {'hp': hp, 'plane': plane, 'gold': gold,
                      'round_num': round_num, 'level': level}
        if node_type is not None:
            axes['node'] = node_type   # 终态契约 §A′:node 单一源 = gs
        return axes

    def test_domain_truth_table_and_p1_complement(self):
        """域真值表 + 位面域互补并一。
        [真值表] p2_blood_floor:plane≥2 ∧ hp≤15 ∧ 可信 ⇒ True;
        hp>15 / hp None / 不可信帧 fail 向 ⇒ False(与 p1_blood_floor
        逐行同构)。阈值单一源(「禁任何第二份字面量 15」):谓词边界 =
        HP_BAND_NEAR_DEATH 读数(≤15 族含边界),非本地第二份——改常量
        即改边界,无第二值可漂。
        [互补] 位面域互补且不交(「同构不同域,禁搭车」):P1 帧不得开
        P2 域谓词;P3 帧属 P2+ 域(谓词 plane≥2 口径)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
            predicates as preds,
        )
        # [真值表]
        st = self._st2(hp=10)
        assert preds.p2_blood_floor(_bsb(**st)) is True
        st['hp'] = 16
        assert preds.p2_blood_floor(_bsb(**st)) is False
        st['hp'] = 15   # ≤15 族含边界(p1_blood_floor 同款)
        assert preds.p2_blood_floor(_bsb(**st)) is True
        st['hp'] = None
        assert preds.p2_blood_floor(_bsb(**st)) is False
        st['hp'] = None   # 不可读 = 域未观察(无可信值可桥,fail 向)
        assert preds.p2_blood_floor(_bsb(**st)) is False
        # 阈值单一源:边界随常量走
        from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.lambda_death import (
            HP_BAND_NEAR_DEATH,
        )
        assert preds.p2_blood_floor(
            _bsb(**self._st2(hp=HP_BAND_NEAR_DEATH))) is True
        assert preds.p2_blood_floor(
            _bsb(**self._st2(hp=HP_BAND_NEAR_DEATH + 1))) is False
        # [互补]
        st = self._st2(hp=10, plane=1)
        assert preds.p1_blood_floor(_bsb(**st)) is True
        assert preds.p2_blood_floor(_bsb(**st)) is False, 'P1 帧禁开 P2 域谓词'
        st3 = self._st2(hp=10, plane=3)
        assert preds.p2_blood_floor(_bsb(**st3)) is True

    def test_crisis_band_blocks_spend_and_interest_key_domain(self):
        """危机带停付面:产线在产 p2_crisis_band 对 P2 濒死帧全额管辖——
        停付照常(P2/P1 域同判);凑息不受血线辖(凑息禁令位已随血线地板
        删除链退役:两域帧的拒因键族里血线键不复存在——空板守卫等金位/
        板面键照常)。(保底金门真值表含出辖两支 =
        TestRetainedGates::test_guarantee_floor_gate_truth_table,不重复。)"""
        from sr_od.application.currency_war.kernel.cw_registry import (
            DEFAULT_REGISTRY,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.levelup import (
            level_spend_blocked,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.sell import (
            sell_for_interest,
        )
        sess = SimpleNamespace(node_type_current='normal')
        assert level_spend_blocked(_bsb(**self._st2(hp=10)), sess,
                                   DEFAULT_REGISTRY) is True, (
            'P2 濒死帧停付照常(危机带管辖)')
        # 凑息不受血线辖(血线拒因键退役:两域帧同判)
        for _st in (self._st2(hp=10), self._st2(hp=10, plane=1)):
            slots_k, key_k = sell_for_interest(
                30, [], 4, (), state=_bsb(**_st))
            assert slots_k == []
            assert key_k not in ('blood_floor', 'p2_blood_floor'), (
                '血线拒因键已随凑息禁令位退役')
