"""CW 升级判据单帧测试(触发单判据三分派 + 资金线门 + 单帧原子发射)。

出处(持久索引):判据正本锚 = strategy-docs/11_shop_decisions.md §2
(升级触发单判据三分派/资金线门/拦截层处置)。判据本体 =
strategies/impl/mandate_v1/criteria/levelup.py,发射位 = entry 备战
第 4 步。测试面组:

1. 带与三分派(prob_band_of_cost 平顶整段/stay_gate-natural 两键/
   P1 与未锁定期零主动升级/板满等待件带内不升——人口位臂删除行为锁);
2. 发射形态(资金线 defer 零购买/血本位不足零购买/血足整批发射/
   等级帽拒发/凑金一卖 → 下一帧整批);
3. 保留语义(资金线门真值表/P21 危机带/金支出出口/凑金域分派)。

构帧纪律:锁定线经 session_scope.write_line_lock(3.1 键,同帧种子后写);
plane2_started 经 node_hist_pos 直赋 + handle_node_boundary 置位(单调
水位驱动,3.1 口径)。

P2 血带节(原 P2 低血带授权域统一件):单一语义权威 = 生产符号
(谓词/授权闩 = statefn.predicates,停付面 = criteria/levelup,
分键写入端 = flow)。校验两类事:①p2_blood_floor 域谓词真值表(信任门/
阈值单一源 = HP_BAND_NEAR_DEATH,位面域互补);②危机带停付面 + 凑息
拒因键域(血线拒因键退役;P21 现为全域判定——危机带帧无论金位一律拦)。
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
    gold_of,
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
#: 低费干扰——停留目标 = 未完成目标中费用档最低者,11 号稿 §2)。
_AUX_DONE = ('花火', '符玄', '缇宝', '刻律德菈')


def _frame(*, level: int, gold: int = 30, plane: int = 2,
           hist: tuple[int, int] | None = (2, 1), bench: tuple = (),
           front_row: tuple = (), hp: int = 60, locked: bool = True,
           actives: tuple = (), deploy_cap: int | None = None,
           round_num: int = 2, node: str = '战斗') -> tuple:
    """判据帧构造(单容器直构 + 锁定键/窗口谓词按 3.1 口径落位)。

    ``hist`` = node_hist_pos 直赋值(None = 不赋——P1 未置位形态经
    (1, n) 表达);返回 (gs, session)——session = gs 同容器实例
    (生产链 emit 的 session 形参即容器,state_of 动态挂载同宿主)。
    ``round_num``/``node`` = 节点轴覆盖(缺省战斗 r2;位面末 boss 帧等
    判据面经此构帧)。
    """
    gs = cw4_gs(None, gold=gold, level=level, round_num=round_num, node=node,
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
    _st.node_boundary_last_pos = (int(plane), int(round_num))
    return gs, gs


def _stay_bench(xili_star: int = 1) -> list:
    """停留目标可控的 bench(辅助达标 + 希儿按参):唯一未完成目标 =
    希儿(3 费 3★)。"""
    return [_bc(n, 1) for n in _AUX_DONE] + [_bc('希儿', xili_star)]


def _mark_handled(gs) -> None:
    """商店会话标记(帧直达第 4 步后不被第 5 步开店截胡)。"""
    node = gs.node.value
    gs.observe(gs.node_pos,
               (int(node.plane), int(node.round_num)) if node else (2, 2),
               sig=ChannelSig(family='obs', actor='cw4_seed',
                              mode='synthesized'))
    _ss.mark_shop_handled(gs)


# ===== 1. 带与三分派(11 号稿 §2 单判据)=====


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


class TestTriggerDispatch:
    def test_three_way_dispatch(self):
        """升级触发单判据三分派(11 号稿 §2;①②③同一等级轴上互斥
        完备):①等级 < 带下界(lv5 < 7)→ 升级触发键 stay_gate(升到
        带内去刷);②等级 ∈ 带(lv7)→ 停留刷新,无键不触发;
        ③等级 > 带上界(lv8 被推过,单调不可降,当前即剩余可达最优)
        → 照样停留,无键不触发。停留目标 = 未完成星级目标中费用档
        最低者(构造 = 辅助达标后唯一目标希儿 3 费)。"""
        gs, s = _frame(level=5, gold=30, bench=_stay_bench())
        assert levelup.upgrade_trigger(gs, s) == (True, 'stay_gate')
        gs7, s7 = _frame(level=7, gold=30, bench=_stay_bench())
        assert levelup.upgrade_trigger(gs7, s7) == (False, ''), \
            '等级 ∈ 带:停留刷新,无键不触发'
        gs8, s8 = _frame(level=8, gold=30, bench=_stay_bench())
        assert levelup.upgrade_trigger(gs8, s8) == (False, ''), \
            '等级被推过带上界:当前即剩余可达最优,照样停留'

    def test_natural_upgrade_without_target(self):
        """分派 ③:无未完成星级目标(全部追完)→ 自然升级不停留,
        键 natural(触发键闭集 = stay_gate/natural 两键,分派 2 无键)。"""
        gs, s = _frame(level=5, gold=30, bench=_stay_bench(xili_star=3))
        assert levelup.unfinished_star_targets(gs) == []
        assert levelup.upgrade_trigger(gs, s) == (True, 'natural')

    def test_p1_and_unlocked_zero_active_upgrade(self):
        """辖域锁(P1 与未锁定期零主动升级,阶段保护):P1 锁定子局
        星级目标存在 ∧ 带下界 7 > 等级 5 → 不触发(P1 不冲级);未锁定
        期(锁定线槽空)同不触发。升级侧排除全靠判据辖域,非刷新层
        拦截。金位 < 息线排除富余语义干扰(旧富余段臂已删,此处只锁
        辖域)。"""
        gs, s = _frame(level=5, gold=30, plane=1, hist=(1, 5),
                       bench=_stay_bench())
        assert levelup.upgrade_trigger(gs, s) == (False, '')
        gs2, s2 = _frame(level=5, gold=30, locked=False,
                         bench=_stay_bench())
        assert levelup.upgrade_trigger(gs2, s2) == (False, '')

    def test_full_board_waiting_piece_in_band_no_upgrade(self):
        """人口位臂删除的行为锁(板满战力义务触发删除,用户裁定
        2026-10-18):板满(cap 2 全占)∧ 备战席同羁绊等待件(知更鸟)
        ∧ 等级 ∈ 带(lv7)→ 仍不升,停留刷新——等待件滞留至带突破为
        接受代价(设计 §3 取舍申报面)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        board = (Unit(char_id='知更鸟', star=1),
                 Unit(char_id='那刻夏', star=1))
        gs, s = _frame(level=7, gold=30,
                       bench=(_bc('知更鸟', 1),),
                       front_row=board, deploy_cap=2)
        assert levelup.upgrade_trigger(gs, s) == (False, ''), \
            '板满 ∧ 等待件 ∧ 带内:人口位臂已删,仍不升'


# ===== 2. 发射形态(单帧原子发射;资金线门)=====


class TestBatchEmission:
    def test_fund_line_defer_no_partial_buy(self):
        """资金线 defer 零购买(现金口径单门,11 号稿 §2):触发帧
        现金 − 整批 < 利息线 ∧ 凑金不可达(无活期可变现)→ 整批推迟
        零动作(levelup_fund_line_defer 拒因键)——禁按闸值截断击数的
        部分买(P48 整买(1) 辖域,「买一半」的对面断言)。"""
        gs, s = _frame(level=5, gold=12, bench=_stay_bench())
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '凑金不可达:整批推迟零动作(不部分买)'
        ct = state_of(s).cw4_counters
        # 资金面拒因统一键(旧 reserve_line/guarantee_floor 分键退役)
        assert ct.get('levelup_fund_line_defer') == 1

    def test_blood_insufficient_zero_buy_blood_sufficient_batch(self):
        """「买一半」缺陷回归测试(血本位局,11 号稿 §2 血本位突变下
        的支付检查):血余额 < 整级血成本 → 零购买(攒血,不置键
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

    def test_fundraise_sell_then_execute_batch(self):
        """凑金一卖 → 下一帧整批发射(单帧原子形态:授权不跨帧携带
        ——「买一半」由发射原子性消解,实付上界 = 发射时授权值):
        帧 1(凑金域:花后破线 ∧ 活期可补)→ 凑金每帧一卖(评估器
        升级凑金场景首位);帧 2(现金 − 批 ≥ 线)→ 整批发射 + 清
        handled 标记(发射完成重开通道)。三帧各一动作(单动作循环),
        帧间零商店域外金动作。"""
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        # lv5 整级批 20 金;现金 68(花后 48 < 线 50)∧ 活期 4 件
        # (c0/c1/c2/c4 各退 3,注册表外散件按保守估——不同名互不构成
        # 合成素材)→ 凑金可达域(68+12−20 = 60 ≥ 50)。
        bench = _stay_bench() + [_bc(n, 1) for n in ('c0', 'c1', 'c2', 'c4')]
        gs, s = _frame(level=5, gold=68, bench=bench,
                       front_row=(Unit(char_id='板上件锚', star=1),))
        _mark_handled(gs)
        # 帧 1(凑金帧):凑金域 → 一卖(评估器升级凑金场景)
        out1 = entry.emit(s, None)
        sells1 = [e for e in out1
                  if type(e.action).__name__ in ('CwActionSellBenchParam',
                                                 'CwActionSellDeployedParam')]
        assert sells1 and sells1[0].action.reason == 'levelup_liquidate', \
            '凑金帧:花后破线 ∧ 活期可补 → 每帧一卖'
        # 帧 2(发射帧):缺口闭合(退金 3 → 71−20 = 51 ≥ 50)→ 单帧
        # 原子整批
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
        assert ups and ups[0].action.clicks >= 1, \
            '发射帧:缺口闭合 → 购买经验整批(单帧原子)'
        assert ups[0].action.auth_basis == 'stay_gate', \
            '触发键随发射装载(资金面拒因与触发键域更新后)'
        assert state_of(s).shop_handled is None, \
            '发射完成清 handled 标记(升级后概率档已变,找牌/刷新需重评)'


# ===== 3. 保留语义(资金线门 / P21 / FM-1 / 凑金域分派)=====


class TestRetainedGates:
    def test_fund_gate_truth_table(self):
        """升级资金线门真值表(现金口径单门,11 号稿 §2):花后金 =
        现金 − 批 ≥ saturation_line(cap_resolved) → 放行;< → 拒;
        出辖两支:终局域末战 ALL IN(判据体内豁免)/ 买断制 cap=0 ⇒
        下界 0 ⇒ 门恒过(无特判分支——下界随 resolved 链自动消解,
        裸金不足批仍拒,凑金分派在资格门层)。"""
        sess = SimpleNamespace(node_type_current='normal')
        gs, _ = _frame(level=5, gold=30)
        # 花后 80-4 = 76 ≥ 50 → 放行;花后 40-4 = 36 < 50 → 拒
        assert levelup.levelup_fund_gate(gs, sess, 80, 1, 4, 5) is True
        assert levelup.levelup_fund_gate(gs, sess, 40, 1, 4, 5) is False
        # 买断制(cap=0)下界 0:花后 5-4 = 1 ≥ 0 → 过(下界消解,
        # 非显式豁免支);花后 3-4 = −1 < 0 → 拒(裸金不够批,归凑金域)
        assert levelup.levelup_fund_gate(gs, sess, 5, 1, 4, 0) is True
        assert levelup.levelup_fund_gate(gs, sess, 3, 1, 4, 0) is False

    def test_p21_crisis_band_retained(self):
        """P21 血预算线保留(拦截层保留件):危机带(hp ≤ p2_crisis_band
        ≈41)帧停付;血线地板解锁让位支已退役(死亡线帧照常停付
        ——濒死响应 = 修经济/阵容本身)。"""
        gs, _ = _frame(level=5, gold=30, hp=10)
        sess = SimpleNamespace(node_type_current='normal')
        assert levelup.level_spend_blocked(gs, sess) is True, \
            'P2 濒死帧(hp 10 ⊂ 危机带 41):停付照常'

    def test_rich_band_lag_frame_emits_gold_exit_open(self):
        """FM-1 金支出出口核对(11 §5 金支出出口要求——持金至死死型
        防线):金充裕带滞后帧(现金 − 批 ≥ 线)升级通道可达——拦截层
        删净后金支出出口不灭(带驱动触发 + 资金门自然命中;触发键 =
        stay_gate,富余金不再是独立触发源)。"""
        gs, s = _frame(level=5, gold=100, bench=_stay_bench())
        _mark_handled(gs)
        out = entry.emit(s, None)
        ups = [e for e in out if isinstance(e.action, CwActionLevelUpParam)]
        assert ups, 'FM-1:金充裕帧升级通道开放(金支出出口)'
        assert ups[0].action.auth_basis == 'stay_gate'

    def test_fund_line_defer_emit_level(self):
        """资金线 defer(emit 级):触发命中 ∧ 花后破线 ∧ 凑金不可达
        → 整批推迟零动作(levelup_fund_line_defer 分键;资金面拒因
        统一键)。"""
        gs, s = _frame(level=5, gold=30, bench=_stay_bench())
        # lv5 批 = 20;花后 30−20 = 10 < 息线 50;活期 0 → 不可达
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '花后破线 ∧ 凑金不可达 → 整批推迟零动作'
        assert state_of(s).cw4_counters.get('levelup_fund_line_defer') == 1

    def test_gold_short_domain_direct(self):
        """凑金可达域直测(判定函数级):花后破线 ∧ 现金 + bench 活期
        − 批 ≥ 线 → GATE_GOLD_SHORT(凑金域,备战侧每帧一卖收敛);
        不可达变体 → GATE_DEFER + levelup_fund_line_defer 在册(触发
        键经计数证:defer 元组不携键)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        # 凑金可达帧:lv5 批 20,现金 68,活期 4 件退 12
        bench = _stay_bench() + [_bc(n, 1) for n in ('c0', 'c1', 'c2', 'c4')]
        gs, s = _frame(level=5, gold=68, bench=bench,
                       front_row=(Unit(char_id='花火', star=1),))
        verdict, _arm, _clicks, _cost = levelup.upgrade_gate_verdict(
            gs, s, counters=state_of(s).cw4_counters)
        assert verdict == levelup.GATE_GOLD_SHORT
        assert state_of(s).cw4_counters.get('levelup_trigger_stay_gate') == 1
        # 不可达变体:同触发 ∧ 无活期 → defer 分键
        gs2, s2 = _frame(level=5, gold=30, bench=_stay_bench())
        verdict2, _a2, _c2, _cc2 = levelup.upgrade_gate_verdict(
            gs2, s2, counters=state_of(s2).cw4_counters)
        assert verdict2 == levelup.GATE_DEFER
        assert state_of(s2).cw4_counters.get('levelup_fund_line_defer') == 1


# ===== 4. P2 低血带授权域(谓词 + 危机带停付面)=====


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
        """危机带停付面:产线在产 p2_crisis_band 对 P2 濒死帧全额管辖
        (P21 全域判定——危机带 ∧ 任意现金位帧均判定,富余段域内让位
        已消亡);凑息不受血线辖(凑息禁令位已随血线地板删除链退役:
        两域帧的拒因键族里血线键不复存在——空板守卫等金位/板面键照常)。"""
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


# ===== 5. 资金门终态行为固化(2026-10-18-levelup-band-gate design §2.7
# ===== 单帧清单 ⑥-⑩ 的 emit 级/域内变体补面;①-⑤ 由本文件上方各类
# ===== 承载,映射见交付报告)=====


class TestFundLineEmissionPins:
    """资金线门发射终态(design §2.7 ⑥⑦⑧⑨⑩)。

    出处(持久索引)= 2026-10-18-levelup-band-gate design.md §2.7 单帧
    清单 / §2.2 资金门统一 / §5.2 边界申报;断言锁语义不锁数值巧合,
    花后金语义断言的线与批成本一律从单一源现算
    (:func:`saturation_line` / 动作装载的 cost×clicks)。
    """

    def test_buyout_cap_zero_gate_auto_passes_emit(self):
        """design §2.7⑥ 买断制 → 门自动过(emit 级):持买断制
        (interest_cap_override=0 注册表派生)⇒ cap_resolved=0 ⇒ 下界
        saturation_line(0)=0 ⇒ 门恒过——现金 25(旧口径线 50 下花后
        5 必 defer 的帧)整批发射;下界随 resolved 链消解,无特判分支。
        锁的是 cap 链接线(active_strategies → cap_resolved_of_session
        → 门),真值表直测(test_fund_gate_truth_table)不覆盖该接线。"""
        from sr_od.application.currency_war.kernel.cw_economy import (
            cap_resolved_of_session,
            saturation_line,
        )
        gs, s = _frame(level=5, gold=25, bench=_stay_bench(),
                       actives=('买断制',))
        _mark_handled(gs)
        out = entry.emit(s, None)
        ups = [e for e in out if isinstance(e.action, CwActionLevelUpParam)]
        assert ups and ups[0].action.auth_basis == 'stay_gate', \
            '买断制帧:门自动过,整批发射(§2.2 下界消解)'
        batch = ups[0].action.cost * ups[0].action.clicks
        assert gold_of(gs) - batch >= saturation_line(
            cap_resolved_of_session(s)), '发射帧花后金 ≥ 买断制下界(0)'

    def test_terminal_all_in_spends_through(self):
        """design §2.7⑦ 位面末 ALL IN → 花光放行(§2.2 豁免):末位面
        末战(P3 r7 boss,r_remaining=1)金 30 < 线+批(旧口径必 defer
        的帧)仍发射——末战后金无任何消费场景,守线前提失效,ALL IN
        维持花光原语义(terminal_all_in 单一源豁免支)。"""
        gs, s = _frame(level=5, gold=30, plane=3, hist=(3, 7),
                       round_num=7, node='boss', bench=_stay_bench())
        # P3 位面长真值(默认表 7 槽;plane_last_battle 判定输入)
        gs.node_books.plane_node_table = [object()] * 7
        gs.node_books.plane_node_table_plane = 3
        _mark_handled(gs)
        out = entry.emit(s, None)
        ups = [e for e in out if isinstance(e.action, CwActionLevelUpParam)]
        assert ups and ups[0].action.auth_basis == 'stay_gate', \
            'ALL IN 帧:花后必破线仍发射(豁免支,非资金门管辖)'

    def test_crisis_band_blocks_even_with_gold_above_line(self):
        """design §2.7⑧ 域内变体行为锁:危机带 ∧ 现金 > 线 → 仍拦
        (富余段域内让位已随出口三层删除消亡,P21 全域判定——拦截在
        资格门④,先于资金门,无论金位)。emit 级 levelup_crisis_defer
        分键 + 判定函数直测同帧真值双锚。"""
        from sr_od.application.currency_war.kernel.cw_registry import (
            DEFAULT_REGISTRY,
        )
        gs, s = _frame(level=5, gold=100, hp=10, bench=_stay_bench())
        assert levelup.level_spend_blocked(gs, s, DEFAULT_REGISTRY) is True, \
            '危机带帧(hp 10)直测:域内变体金 100(> 线 50)仍判拦'
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '危机带 ∧ 现金 > 线:发射链零动作(全域判定)'
        assert state_of(s).cw4_counters.get('levelup_crisis_defer') == 1

    def test_interest_saving_band_never_emits(self):
        """design §2.7⑨ 攒息期行为锁(§5.2 申报:攒息期升级-刷新双滞
        为预期健康态):金 30-60 攒息期带驱动帧(现金 < 线+批)零发射
        ——推迟(凑金穷尽)与凑金(每帧一卖)两处置都不得在该帧发射。
        金 30 支由 test_fund_line_defer_emit_level 承载,本测试扫中高段
        55/65 与凑金可达变体。"""
        # 推迟处置:中高段金位无活期(线内 bench 不可卖)→ defer 零发射
        for gold in (55, 65):
            gs, s = _frame(level=5, gold=gold, bench=_stay_bench())
            _mark_handled(gs)
            out = entry.emit(s, None)
            assert not [e for e in out
                        if isinstance(e.action, CwActionLevelUpParam)], \
                f'攒息带金 {gold}:该帧不发射(整批推迟)'
            assert state_of(s).cw4_counters.get(
                'levelup_fund_line_defer') == 1, \
                f'攒息带金 {gold}:推迟拒因在册'
        # 凑金处置:金 55 + 活期 5 件(退 15,凑金可达域)→ 每帧一卖,
        # 卖出帧零发射(凑至缺口闭合,发射在后续帧——单帧原子不跨帧)。
        # 板上件锚:评估器空板守卫(empty_board_sell_blocked)要求板非空
        # 才出卖出候选(与 test_fundraise_sell_then_execute_batch 同款)。
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        bench = _stay_bench() + [_bc(n, 1)
                                 for n in ('c0', 'c1', 'c2', 'c4', 'c5')]
        gs2, s2 = _frame(level=5, gold=55, bench=bench,
                         front_row=(Unit(char_id='板上件锚', star=1),))
        _mark_handled(gs2)
        out2 = entry.emit(s2, None)
        assert not [e for e in out2
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '攒息带凑金帧:一卖处置,零发射'
        sells = [e for e in out2
                 if isinstance(e.action, CwActionSellBenchParam)]
        assert sells and sells[0].action.reason == 'levelup_liquidate', \
            '凑金可达:走升级凑金场景(非 defer 非发射)'

    def test_natural_upgrade_fund_gate_end_to_end(self):
        """design §2.7⑩ 自然升级 × 资金门端到端:无未完成星级目标 →
        natural 键触发,资金门对 natural 同参管辖——金足帧整批发射
        (花后 ≥ 线,触发键随发射装载),金不足帧推迟零动作(触发计数
        与资金 defer 计数同帧在册,证两链同帧串接)。"""
        from sr_od.application.currency_war.kernel.cw_economy import (
            cap_resolved_of_session,
            saturation_line,
        )
        # 金不足:花后 30−批 < 线 ∧ 无活期 → defer(natural 触发在册)
        gs, s = _frame(level=5, gold=30, bench=_stay_bench(xili_star=3))
        assert levelup.unfinished_star_targets(gs) == []
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '金不足自然升级帧:推迟零动作'
        ct = state_of(s).cw4_counters
        assert ct.get('levelup_trigger_natural') == 1, 'natural 触发在册'
        assert ct.get('levelup_fund_line_defer') == 1, '资金 defer 同帧在册'
        # 金足:花后 ≥ 线 → 整批发射,auth_basis = natural
        gs2, s2 = _frame(level=5, gold=100, bench=_stay_bench(xili_star=3))
        _mark_handled(gs2)
        out2 = entry.emit(s2, None)
        ups = [e for e in out2 if isinstance(e.action, CwActionLevelUpParam)]
        assert ups and ups[0].action.auth_basis == 'natural', \
            '金足自然升级帧:整批发射,触发键随发射装载'
        batch = ups[0].action.cost * ups[0].action.clicks
        assert gold_of(gs2) - batch >= saturation_line(
            cap_resolved_of_session(s2)), '发射帧花后金 ≥ 线(端到端语义)'
