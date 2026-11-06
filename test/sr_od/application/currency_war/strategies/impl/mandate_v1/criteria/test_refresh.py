"""刷新链三组件单帧测试固化(迭代 ``2026-10-28-hp-purge-refresh-reform``;
design.md §2.0 第 2/3 条 + details/refresh-chain.md §5 清单)。

清单对照(七条,docstring 引本迭代 design.md):

- ① 带内 + 金够 + 席可腾 → 发射(付费,reason ``star_target``);
- ② 已 2★ 追 3★ 目标帧 ρ = 其卡价(实费档;锁定支单一源
  ``r2_card_reserve``,未锁窗口恒 0);
- ③ 席满 + 可合成 → 发射(合成腿消费现役 ``_merge_pair_names``
  「恰 2 张全 1★」语义——机制全集重写归买面改革批,本批锁现役口径);
- ④ 席满 + 零燃料 + 不可合成 → **付费刷新发射**(统一让位优先级迭代
  3.4:预测门整拆——旧「目标可买三条效果条目」判据删除,拒因
  ``target_unbuyable`` 退役;「刷出后能否买到」不可预测,刷新时点
  信息最少,design §2.10 单帧断言 1 = 2-4 开店帧应触发刷新);
- ⑤ 升级推迟帧刷新维持拒绝(资金序 = 升级优先于刷新,判据①支无
  解锁支);
- ⑥ 免费次数已登记即刷(统一让位优先级迭代 3.2:design §2.2 无条件刷
  【拍】,外层负结果记忆闸照旧);
- ⑦ 死码符号零残留——按本测试仓纪律(源码扫描测试禁写,退役符号
  墓碑不设 pytest)以执行侧残留扫描承载,记录归迭代报告。

帧构造 = 列车同行注册表线(need_star:姬子·启行 3/三月七 2/花火 2/
瓦尔特 1;费档 3/1/2/5 注册表现查),合成腿/拒发射帧均上阵行非空
(空板止损守卫 = 燃料资格面前置门)。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_comp as _comp_of,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_decide as _decide,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_members as _members,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session as _session,
)

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    CwActionRefreshShopParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    session_scope,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    levelup as crit_levelup,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    refresh as crit_refresh,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_COMP_NAME = '列车同行·反震'   # 批 3 拆分后取 A 主形态(测试载体与装备分岔无关)
_LINE = tuple(_members(_comp_of(_COMP_NAME)))
_TARGET = '姬子·启行'   # need_star 3(唯一 3★ 追到底目标)
_LOGIC_SIG = ChannelSig(family='logic_action', actor='cw-refresh-chain',
                        mode='compute')


def _fillers(count: int, exclude: tuple[str, ...] = ()) -> list[str]:
    """非线燃料名(注册表现算防漂移;席位腿测试帧填充——身份保护/
    C1 核心规避面已随统一让位优先级迭代 3.4 退役,非线内即可)。"""
    out = [n for n in CHARACTERS
           if n not in _LINE and n not in exclude]
    assert len(out) >= count, '测试前提:填充名不足'
    return out[:count]


def _locked_frame(*, bench, deployed, gold: int, level: int,
                  round_num: int = 2, node: str = 'reward'):
    """锁定线决策帧(cw4 种子家族 + 状态归一挂载 + 位面 2 边界执行;
    直调判据与 decide 驱动共用同一宿主形态)。"""
    s = _session(_comp_of(_COMP_NAME), plane_lengths=[9, 5, 7])
    axes = {'gold': gold, 'level': level, 'plane': 2,
            'round_num': round_num, 'node': node, 'hp': 100,
            'bench': list(bench), 'front_row': list(deployed)}
    gs = cw4_gs(s, **axes)
    st = state_of(s)
    gs.strategy_state = st   # 宿主归一:判据读口(session_scope 族)同源
    gs.node_hist_pos = (2, 1)
    session_scope.handle_node_boundary(gs)
    st.gold_ledger = gold
    return s, gs, st


def _line_bench_base() -> list:
    """列车同行达标底座(三月七/花火 2★ 达标、瓦尔特 1★ 达标——
    未完成目标收敛到姬子·启行)。"""
    return [_bc('三月七', star=2), _bc('花火', star=2)]


def _assert_band_premise(cost: int, level: int) -> None:
    """带前提守卫(level ∈ 带或被推过;带 = 注册表概率表现算)。"""
    lo, _hi = crit_levelup.prob_band_of_cost(cost)
    assert level >= lo, f'测试前提:level {level} < {cost} 费带下界 {lo}'


class TestRefreshChainSingleFrame:
    """七条清单(⑦ = 执行侧扫描,见模块 docstring)。"""

    def test_1_in_band_gold_enough_seat_free_emits(self):
        """①带内 + 金够 + 席可腾(空位腿)→ 付费刷新发射。"""
        level = 7
        _assert_band_premise(int(CHARACTERS[_TARGET].cost), level)
        bench = [_bc(_TARGET, star=2)] + _line_bench_base() \
            + [_bc(_fillers(2)[0], star=2)]
        deployed = [Unit(char_id='瓦尔特', star=1)]
        s, gs, _st = _locked_frame(bench=bench, deployed=deployed,
                                   gold=100, level=level)
        acts = _decide(s)
        refreshes = [a for a in acts
                     if isinstance(a, CwActionRefreshShopParam)]
        assert refreshes, f'带内金够帧刷新应发射: {acts!r}'
        assert refreshes[0].reason == 'star_target'
        assert refreshes[0].cost > 0, '付费刷新(免费腿未登记)'

    def test_2_rho_stay_target_effective_cost(self):
        """②已 2★ 追 3★ 目标帧 ρ = 其卡价(实费档);未锁窗口恒 0。

        旧「合格集最低费卡价」口径被「无 2★ 成型」过滤排除该目标 →
        漏留卡价;新口径按实费档预留(行为差申报的锁定面)。"""
        bench = [_bc(_TARGET, star=2)] + _line_bench_base()
        deployed = [Unit(char_id='瓦尔特', star=1)]
        s, gs, _st = _locked_frame(bench=bench, deployed=deployed,
                                   gold=50, level=7)
        target = crit_levelup.stay_target_of(gs)
        assert target is not None and target[0] == _TARGET, \
            '测试前提:停留目标 = 姬子·启行'
        assert crit_refresh.r2_card_reserve(gs) \
            == int(CHARACTERS[_TARGET].cost), 'ρ = 停留目标实费档'
        # 未锁窗口分支口径:stay_target 恒空 → ρ = 0。
        s2 = _session(None, plane_lengths=[9, 5, 7])
        gs2 = cw4_gs(s2, gold=50, level=7, plane=2, round_num=2,
                     node='reward', hp=100,
                     bench=[_bc('瓦尔特', star=1)],
                     front_row=[Unit(char_id=_fillers(1)[0], star=2)])
        assert crit_refresh.r2_card_reserve(gs2) == 0, '未锁窗口 ρ = 0'

    def test_3_full_bench_merge_pair_emits(self):
        """③席满 + 可合成 → 发射(合成腿消费机制全集谓词
        ``_merge_pair_names`` 的 1★ 档计数 == 2 子形态——本帧无同名 2★,
        与旧「恰 2 张全 1★」口径同判;扩展形态〔场上 2★ + 备战 1★×2〕
        随谓词全集重写生效,单帧见 shop 域买面改革测试)。"""
        level = 7
        _assert_band_premise(int(CHARACTERS['花火'].cost), level)
        fill = _fillers(5)
        # 花火仅 1★×2(无 2★ 副本——need 2 未完成,停留目标 = 花火);
        # 姬子·启行 3★/三月七 2★/瓦尔特 2★ 达标。
        bench = [_bc('花火', star=1), _bc('花火', star=1),
                 _bc(_TARGET, star=3), _bc('三月七', star=2),
                 _bc('瓦尔特', star=2)] \
            + [_bc(n, star=2) for n in fill[:4]]
        assert len(bench) == BENCH_CAPACITY
        deployed = [Unit(char_id=fill[4], star=2)]
        s, gs, _st = _locked_frame(bench=bench, deployed=deployed,
                                   gold=100, level=level)
        acts = _decide(s)
        refreshes = [a for a in acts
                     if isinstance(a, CwActionRefreshShopParam)]
        assert refreshes, f'席满可合成帧刷新应发射: {acts!r}'
        assert refreshes[0].cost > 0

    def test_4_full_bench_no_legs_emits(self):
        """④席满 + 零燃料 + 不可合成 → 付费刷新发射(统一让位优先级
        迭代 3.4 预测门整拆:旧「目标可买三条效果条目」判据删除,拒因
        ``target_unbuyable`` 退役——刷新时点预测不可算,买不买得到归
        刷出后帧裁决;design §2.10 单帧断言 1)。"""
        level = 7
        _assert_band_premise(int(CHARACTERS[_TARGET].cost), level)
        fill = _fillers(6)
        bench = [_bc(_TARGET, star=2), _bc('三月七', star=2),
                 _bc('花火', star=2), _bc('瓦尔特', star=2)] \
            + [_bc(n, star=2) for n in fill[:5]]
        assert len(bench) == BENCH_CAPACITY
        deployed = [Unit(char_id=fill[5], star=2)]
        s, gs, st = _locked_frame(bench=bench, deployed=deployed,
                                  gold=100, level=level)
        acts = _decide(s)
        refreshes = [a for a in acts
                     if isinstance(a, CwActionRefreshShopParam)]
        assert refreshes, f'预测门拆除后席满帧应触发刷新: {acts!r}'
        assert refreshes[0].cost > 0
        assert st.cw4_counters.get('shop_refresh_target_unbuyable', 0) == 0, \
            'target_unbuyable 拒因键已退役,不得复现'

    def test_5_upgrade_defer_frame_refresh_stays_rejected(self):
        """⑤升级推迟帧刷新维持拒绝(资金序 = 升级优先于刷新;判据①支
        无解锁支——凑金在途帧不放行刷,防「刷新烧凑金 → 升级永久
        defer」饿死环)。"""
        bench = [_bc(_TARGET, star=2)] + _line_bench_base()
        deployed = [Unit(char_id='瓦尔特', star=1)]
        s, gs, _st = _locked_frame(bench=bench, deployed=deployed,
                                   gold=20, level=4)   # 4 < 3 费带下界
        ok, key = crit_refresh.refresh_warranted(gs, s)
        assert (ok, key) == (False, 'stay_gate_upgrade_first'), \
            '升级推迟期刷新维持拒绝(资金序,无解锁支)'

    def test_6_free_refresh_unconditional_when_counted(self):
        """⑥免费次数已登记即刷(统一让位优先级迭代 3.2;design §2.2 免费
        刷新行为声明:分支内零判据门——行为申报 = 唯一变化「目标可买」
        门删除,目标不可买(备战位满)帧从「拦下不耗次数」变「照刷耗
        次数」,免费不耗金、次数每节点重置/概率补给,低价值接受)。"""
        level = 7
        _assert_band_premise(int(CHARACTERS[_TARGET].cost), level)
        fill = _fillers(6)
        bench = [_bc(_TARGET, star=2), _bc('三月七', star=2),
                 _bc('花火', star=2), _bc('瓦尔特', star=2)] \
            + [_bc(n, star=2) for n in fill[:5]]
        assert len(bench) == BENCH_CAPACITY
        deployed = [Unit(char_id=fill[5], star=2)]
        s, gs, st = _locked_frame(bench=bench, deployed=deployed,
                                  gold=100, level=level)
        gs.write_logic(gs.free_refresh_left, 2, produced_by='cw-refresh-chain',
                       sig=_LOGIC_SIG)
        acts = _decide(s)
        refreshes = [a for a in acts
                     if isinstance(a, CwActionRefreshShopParam)]
        assert refreshes, f'免费次数已登记帧无条件刷: {acts!r}'
        assert refreshes[0].cost == 0 \
            and refreshes[0].reason == 'free_refresh', refreshes[0]
        # 外层负结果记忆闸照旧(design §2.2:免费与付费同闸)——记忆
        # 置位帧免费腿同跳,本帧零标记(免费分支不再置位)。
        assert st.refresh_blocked is None
