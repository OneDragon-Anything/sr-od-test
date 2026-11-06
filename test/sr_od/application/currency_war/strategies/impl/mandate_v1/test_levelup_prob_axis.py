"""CW 升级判据单帧测试(触发单判据三分派 + 资金线门 + 单帧原子发射)。

出处(持久索引):判据正本锚 = strategy-docs/11_shop_decisions.md §2
(升级触发单判据三分派/资金线门/拦截层处置)。判据本体 =
strategies/impl/mandate_v1/criteria/levelup.py,发射位 = entry 备战
第 4 步。测试面组:

1. 带与三分派(prob_band_of_cost 平顶整段/stay_gate-natural 两键/
   P1 与未锁定期零主动升级/板满等待件带内不升——人口位臂删除行为锁);
2. 发射形态(资金线 defer 零购买/血本位不足零购买/血足整批发射/
   等级帽拒发/金不足帧恒 defer 零卖出——凑金链整删,用户裁定
   2026-10-30:不存在升级卖牌凑金,保持最大压牌库,钱够了再升);
3. 保留语义(资金线门真值表/「无 hp 支」负向守卫/金支出出口/
   花后破线恒 defer——原凑金可达域与不可达域同形)；
4. 升级不发射帧的节末凑息恢复运行(凑息抑制谓词已随凑金链整删——
   用户裁定 2026-10-30 选 A:等钱帧凑息照常)。

构帧纪律:锁定线经 session_scope.write_line_lock(3.1 键,同帧种子后写);
plane2_started 经 node_hist_pos 直赋 + handle_node_boundary 置位(单调
水位驱动,3.1 口径)。

P2 血带节(原 P2 低血带授权域统一件):单一语义权威 = 生产符号
(谓词 = statefn.predicates,分键写入端 = flow)。校验两类事:
①p2_blood_floor 域谓词真值表(信任门/阈值单一源 = HP_BAND_NEAR_DEATH,
位面域互补——R-7 保留的纯观测面);②凑息拒因键域(血线拒因键退役;
hp 判据面已随 hp-purge 迭代 3.1 删除——危机帧不再拦升级,升级发射
门序 6 道、无 hp 支,语义锚 = changes/2026-10-28-hp-purge-refresh-reform/design.md)。
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
        现金 − 整批 < 利息线 → 整批推迟零动作(levelup_fund_line_defer
        拒因键)——禁按闸值截断击数的部分买(P48 整买(1) 辖域,
        「买一半」的对面断言;凑金链已整删,活期资产不进推迟/发射
        任何一侧的算术)。"""
        gs, s = _frame(level=5, gold=12, bench=_stay_bench())
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '凑金不可达:整批推迟零动作(不部分买)'
        ct = state_of(s).cw4_counters
        # 资金面拒因统一键(旧 reserve_line/guarantee_floor 分键退役)
        assert ct.get('levelup_fund_line_defer') >= 1

    def test_blood_insufficient_zero_buy_blood_sufficient_batch(self):
        """「买一半」缺陷回归测试(血本位局,R-1 经验批支付门——币种
        通式:支付币余额 ≥ 整批成本 = 支付能力检查,非 hp 判据):
        血余额 < 整级血成本 → 零购买(攒血,不置键不发射);血余额 ≥
        整级血成本 → 整批发射(clicks = 门槛表差值折击数,一次买齐)。
        发射粒度整批化后无逐帧重闸复发面。"""
        # 血不足:奋斗协议(每击血价注册表)∧ hp 低于整级血成本
        gs, s = _frame(level=5, gold=30, hp=5, bench=_stay_bench(),
                       actives=('奋斗协议',))
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '血本位局血不足整级:零购买(经验批支付门 defer)'
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

    def test_gold_short_frame_defers_zero_sell(self):
        """金不足帧恒 defer 零卖出(凑金链整删行为锁,用户裁定
        2026-10-30:不存在升级卖牌凑金——保持最大压牌库,钱够了再升):
        花后破线 ∧ 备战席活期充足(原「凑金可达域」形态:68+12−20 =
        60 ≥ 线 50)→ 不再卖牌凑金——零卖出动作、零升级发射,整批
        推迟拒因键 levelup_fund_line_defer 已登记;对照金位升至线+批
        (现金 80:80−20 = 60 ≥ 50)→ 整批发射(「钱够了再升」的
        正向锚:发射只由资金线支配,不由变现加速)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        # lv5 整级批 20 金;现金 68(花后 48 < 线 50)∧ 活期 4 件
        # (c0/c1/c2/c4 各退 3,注册表外散件按保守估——不同名互不构成
        # 合成素材)——修复前 = 凑金可达域(gold_short),现在恒 defer。
        bench = _stay_bench() + [_bc(n, 1) for n in ('c0', 'c1', 'c2', 'c4')]
        gs, s = _frame(level=5, gold=68, bench=bench,
                       front_row=(Unit(char_id='板上件锚', star=1),))
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if type(e.action).__name__ in ('CwActionSellBenchParam',
                                                   'CwActionSellDeployedParam')], \
            '金不足帧零卖出动作(凑金链已整删,活期资产不再被升级变现回抽)'
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)]
        assert state_of(s).cw4_counters.get('levelup_fund_line_defer') == 1, \
            '整批推迟拒因键已登记(原凑金可达帧与不可达帧同键同形)'
        # 对照:金位 ≥ 线+批(现金 80,花后 60 ≥ 50)→ 整批发射。
        gs2, s2 = _frame(level=5, gold=80, bench=_stay_bench())
        _mark_handled(gs2)
        out2 = entry.emit(s2, None)
        ups = [e for e in out2 if isinstance(e.action, CwActionLevelUpParam)]
        assert ups and ups[0].action.auth_basis == 'stay_gate', \
            '金够帧整批发射(发射只由资金线支配,不由变现加速)'


# ===== 3. 保留语义(资金线门 / 无 hp 支负向守卫 / FM-1 / 凑金域分派)=====


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

    def test_crisis_frame_no_hp_block_negative_guard(self):
        """「无 hp 支」负向守卫(hp-purge 迭代 3.1;hp 是对局结果不是
        决策输入,2026-10-28 用户裁定):P2 濒死帧(hp 10,原危机带域内)
        升级判据不再有 hp 拦截支——该帧 defer 唯一来源 = 资金线门
        (金 30 花后破线,恒 defer 等钱),拒因键域闭集断言(键域 =
        触发 + 资金线 defer;发射门序 6 道无 hp 支)。判定函数级直测 +
        emit 级双锚。"""
        from sr_od.application.currency_war.kernel.cw_registry import (
            DEFAULT_REGISTRY,
        )
        # 判定函数级:P2 濒死帧 defer 拒因键域闭集(hp 族键已删,不得复现)
        gs0, s0 = _frame(level=5, gold=30, hp=10, bench=_stay_bench())
        verdict0, _arm0, _c0, _cc0 = levelup.upgrade_gate_verdict(
            gs0, s0, registry=DEFAULT_REGISTRY,
            counters=state_of(s0).cw4_counters)
        assert verdict0 == levelup.GATE_DEFER
        ct0 = state_of(s0).cw4_counters
        assert ct0.get('levelup_trigger_stay_gate') == 1
        assert set(ct0) == {'levelup_trigger_stay_gate',
                            'levelup_fund_line_defer'}, \
            f'濒死帧拒因键域闭集(无 hp 支,门序 6 道):{sorted(ct0)}'
        # emit 级:同帧走备战发射链,拒因同源零外溢。
        gs, s = _frame(level=5, gold=30, hp=10, bench=_stay_bench())
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)]
        ct = state_of(s).cw4_counters
        assert ct.get('levelup_trigger_stay_gate') == 1
        assert ct.get('levelup_fund_line_defer') >= 1

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
        """资金线 defer(emit 级):触发命中 ∧ 花后破线 → 整批推迟
        零动作零卖出(levelup_fund_line_defer 分键;资金面拒因统一键
        ——凑金链整删后金不足帧恒此形态)。"""
        gs, s = _frame(level=5, gold=30, bench=_stay_bench())
        # lv5 批 = 20;花后 30−20 = 10 < 息线 50
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '花后破线 → 整批推迟零动作'
        assert not [e for e in out
                    if isinstance(e.action, CwActionSellBenchParam)], \
            '金不足帧零卖出(凑金链已整删)'
        assert state_of(s).cw4_counters.get('levelup_fund_line_defer') == 1

    def test_fund_line_break_always_defers(self):
        """花后破线恒 defer(判定函数级;凑金域分派臂整删行为锁):
        原凑金可达帧(花后破线 ∧ 现金 + bench 活期 − 批 ≥ 线)与
        凑金不可达帧(宽池可卖也守不住线)verdict 同形 GATE_DEFER
        ——值域闭集 = miss/defer/emit 三值,金不足帧拒因键
        levelup_fund_line_defer 已登记(触发键经计数证:defer 元组不
        携键)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        # 原凑金可达帧:lv5 批 20,现金 68,活期 4 件退 12(68+12−20
        # = 60 ≥ 50)→ 现与不可达帧同形 defer。
        bench = _stay_bench() + [_bc(n, 1) for n in ('c0', 'c1', 'c2', 'c4')]
        gs, s = _frame(level=5, gold=68, bench=bench,
                       front_row=(Unit(char_id='花火', star=1),))
        verdict, _arm, _clicks, _cost = levelup.upgrade_gate_verdict(
            gs, s, counters=state_of(s).cw4_counters)
        assert verdict == levelup.GATE_DEFER
        ct = state_of(s).cw4_counters
        assert ct.get('levelup_trigger_stay_gate') == 1
        assert ct.get('levelup_fund_line_defer') >= 1
        # 不可达变体:同触发 ∧ 无活期 → 同键同形 defer。
        gs2, s2 = _frame(level=5, gold=30, bench=_stay_bench())
        verdict2, _a2, _c2, _cc2 = levelup.upgrade_gate_verdict(
            gs2, s2, counters=state_of(s2).cw4_counters)
        assert verdict2 == levelup.GATE_DEFER
        assert state_of(s2).cw4_counters.get('levelup_fund_line_defer') == 1


# ===== 3b. 升级不发射帧节末凑息恢复运行(凑息抑制谓词随凑金链整删)=====


class TestDeferFrameInterestRuns:
    """升级不发射帧(等钱/等级帽/奖励)的节末凑息恢复运行(用户裁定
    2026-10-30 选 A:等钱帧凑息照常——卖垫牌跨档增金正助「钱够了再
    升」)。修复前形态 = 升级判据命中帧(verdict ≠ miss)节末凑息步
    零发出(同池候选竞争凑金优先);凑金链整删后凑息触发不再咨询升级
    判据,三类 defer 帧同形恢复凑息。"""

    _AUX = _AUX_DONE   # 板上辅助达标件(need 1 持有即完成)

    def _defer_frame(self, *, level: int, gold: int, node: str = '战斗',
                     fillers: tuple = (), deploy_cap: int | None = None):
        """defer 形态帧:板上 = 辅助达标件 + 希儿(need 3 唯一未完成
        目标)+ 等级帽变体的中性填充;bench = c0 散件(1★ 退 3 ≥
        凑息缺口 2 的跨档候选);gold 48 → 下一利息档缺口 2。node 取
        值 = NodeKey kind 词表('战斗'/'reward'/'boss')。"""
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        front = tuple(Unit(char_id=n, star=1) for n in self._AUX) \
            + (Unit(char_id='希儿', star=1),) + tuple(
                Unit(char_id=n, star=1) for n in fillers)
        bench = [_bc('c0', 1)]
        return _frame(level=level, gold=gold, node=node, bench=bench,
                      front_row=front, deploy_cap=deploy_cap)

    def _run_to_interest_sell(self, gs, s, *, max_frames: int = 8):
        """逐帧推进到节末凑息卖出(阶段 5/6:第 6 步部署差分可能先行
        发排修正拖动——单动作循环下逐帧消化,拖动经上报函数落地后
        下帧重扫;凑息 SellBench(interest_prep) 到达即返回)。"""
        from sr_od.application.currency_war.kernel.cw_action_report.move_unit import (
            report_action_move_unit_param,
        )
        from sr_od.application.currency_war.kernel.cw_game_state import (
            ChannelSig,
        )
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionMoveUnitParam,
            CwActionSellBenchParam,
        )
        sig = ChannelSig(family='logic_action', actor='levelup-test',
                         mode='compute')
        for _ in range(max_frames):
            out = entry.emit(s, None)
            sells = [e.action for e in out
                     if isinstance(e.action, CwActionSellBenchParam)]
            if sells:
                return sells
            moves = [e.action for e in out
                     if isinstance(e.action, CwActionMoveUnitParam)]
            if not moves:
                return None
            for m in moves:
                report_action_move_unit_param(gs, m, sig)
        return None

    def test_fund_defer_frame_interest_runs(self):
        """等钱帧(触发命中 ∧ 花后破线 → levelup_fund_line_defer):
        lv5 批 20,金 48 花后 28 < 线 50 → 第 4 步整批推迟零动作;
        凑息缺口 2(gold 48 → 下一档 50)∧ bench 散件退 3 跨档 →
        第 8 步照常卖出(interest_prep)——同帧双键已登记(资金 defer +
        凑息取用),证明两步互不抑制。"""
        gs, s = self._defer_frame(level=5, gold=48, deploy_cap=5)
        _mark_handled(gs)
        out = self._run_to_interest_sell(gs, s)
        ct = state_of(s).cw4_counters
        assert ct.get('levelup_fund_line_defer') >= 1
        assert out is not None, '等钱帧节末凑息照常(裁定 A:抑制谓词已随凑金链整删)'
        assert ct.get('node_end_interest_sell') == 1

    def test_level_cap_defer_frame_interest_runs(self):
        """等级帽帧(levelup_reject_level_cap):满级帧第 4 步拒发
        零动作;同帧节末凑息照常(修复前等级帽帧属判据命中帧,凑息被
        抑制)。板满 10/10(辅助 + 希儿 + 5 中性填充),凑息缺口 2。"""
        fillers = ('镜流', 'Saber', 'Archer', '杰帕德', '停云')
        gs, s = self._defer_frame(level=10, gold=48, fillers=fillers,
                                  deploy_cap=10)
        _mark_handled(gs)
        out = self._run_to_interest_sell(gs, s)
        ct = state_of(s).cw4_counters
        assert ct.get('levelup_reject_level_cap') >= 1
        assert out is not None, '等级帽帧节末凑息照常(升级不发射帧不再抑制凑息)'

    def test_reward_frame_interest_runs(self):
        """奖励帧(levelup_reward_node_defer,抑制先于触发判定):
        第 4 步拒发零动作;同帧节末凑息照常。"""
        gs, s = self._defer_frame(level=5, gold=48, node='reward',
                                  deploy_cap=5)
        _mark_handled(gs)
        out = self._run_to_interest_sell(gs, s)
        ct = state_of(s).cw4_counters
        assert ct.get('levelup_reward_node_defer') >= 1
        assert out is not None, '奖励帧节末凑息照常(升级不发射帧不再抑制凑息)'


# ===== 4. P2 低血带观测域(谓词真值表 + 凑息键域)=====


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

    def test_interest_reject_key_domain_no_blood_keys(self):
        """凑息拒因键域(血线键退役):两域帧(濒死带/域外)凑息判定
        同判——拒因键族里血线键不复存在(空板守卫等金位/板面键照常;
        hp 判据面删除后观测/判读面零血线键)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.sell import (
            sell_for_interest,
        )
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
        锁的是 cap 链接入调用(active_strategies → cap_resolved_of_session
        → 门),真值表直测(test_fund_gate_truth_table)不覆盖该接入调用。"""
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

    def test_crisis_band_frame_emits_with_gold_above_line(self):
        """「无 hp 支」emit 级固化(原 §2.7⑧ 域内变体的负向重锚;hp-purge
        迭代 3.1):濒死帧(hp 10)∧ 现金 > 线 → 正常发射——危机带拦截门
        已删,发射门序 6 道无 hp 支,金充裕濒死帧升级通道开放(FM-1
        金支出出口同语义)。发射帧拒因键域闭集 = 触发键(全链通过,
        零门拒零 hp 族键)。"""
        gs, s = _frame(level=5, gold=100, hp=10, bench=_stay_bench())
        _mark_handled(gs)
        out = entry.emit(s, None)
        ups = [e for e in out if isinstance(e.action, CwActionLevelUpParam)]
        assert ups, '濒死帧金充裕:hp 拦截支已删,正常发射'
        assert ups[0].action.auth_basis == 'stay_gate'
        ct = state_of(s).cw4_counters
        _lv_keys = {k for k in ct if k.startswith('levelup_')}
        assert ct.get('levelup_trigger_stay_gate') == 1
        assert _lv_keys == {'levelup_trigger_stay_gate',
                            'levelup_batch_emitted'}, \
            f'发射帧 levelup 键域闭集(全链通过,无 hp 支):{sorted(_lv_keys)}'

    def test_interest_saving_band_never_emits(self):
        """design §2.7⑨ 攒息期行为锁(§5.2 申报:攒息期升级-刷新双滞
        为预期健康态):金 30-60 攒息期带驱动帧(现金 < 线+批)零发射
        ——整批推迟(凑金链整删后的唯一处置,零卖出)不得在该帧发射。
        金 30 支由 test_fund_line_defer_emit_level 承载,本测试扫中高段
        55/65 与活期充足变体(原凑金可达帧)。"""
        # 整批推迟:中高段金位无活期(线内 bench 不可卖)→ defer 零发射
        for gold in (55, 65):
            gs, s = _frame(level=5, gold=gold, bench=_stay_bench())
            _mark_handled(gs)
            out = entry.emit(s, None)
            assert not [e for e in out
                        if isinstance(e.action, CwActionLevelUpParam)], \
                f'攒息带金 {gold}:该帧不发射(整批推迟)'
            assert state_of(s).cw4_counters.get(
                'levelup_fund_line_defer') == 1, \
                f'攒息带金 {gold}:推迟拒因已登记'
        # 活期充足变体:金 55 + 活期 5 件(退 15,原凑金可达域)→ 恒
        # defer,零发射零卖出(压牌库资产不再被升级变现回抽——用户
        # 裁定 2026-10-30:不存在升级卖牌凑金,钱够了再升)。
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        bench = _stay_bench() + [_bc(n, 1)
                                 for n in ('c0', 'c1', 'c2', 'c4', 'c5')]
        gs2, s2 = _frame(level=5, gold=55, bench=bench,
                         front_row=(Unit(char_id='板上件锚', star=1),))
        _mark_handled(gs2)
        out2 = entry.emit(s2, None)
        assert not [e for e in out2
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '攒息带活期充足帧:恒 defer,零发射'
        assert not [e for e in out2
                    if isinstance(e.action, CwActionSellBenchParam)], \
            '活期充足金不足帧零卖出(凑金链已整删)'
        assert state_of(s2).cw4_counters.get(
            'levelup_fund_line_defer') == 1, '推迟拒因已登记'

    def test_natural_upgrade_fund_gate_end_to_end(self):
        """design §2.7⑩ 自然升级 × 资金门端到端:无未完成星级目标 →
        natural 键触发,资金门对 natural 同参管辖——金足帧整批发射
        (花后 ≥ 线,触发键随发射装载),金不足帧推迟零动作(触发计数
        与资金 defer 计数同帧已登记,证两链同帧串接)。"""
        from sr_od.application.currency_war.kernel.cw_economy import (
            cap_resolved_of_session,
            saturation_line,
        )
        # 金不足:花后 30−批 < 线 ∧ 无活期 → defer(natural 触发已登记)
        gs, s = _frame(level=5, gold=30, bench=_stay_bench(xili_star=3))
        assert levelup.unfinished_star_targets(gs) == []
        _mark_handled(gs)
        out = entry.emit(s, None)
        assert not [e for e in out
                    if isinstance(e.action, CwActionLevelUpParam)], \
            '金不足自然升级帧:推迟零动作'
        ct = state_of(s).cw4_counters
        assert ct.get('levelup_trigger_natural') == 1, 'natural 触发已登记'
        assert ct.get('levelup_fund_line_defer') >= 1, '资金 defer 同帧已登记'
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
