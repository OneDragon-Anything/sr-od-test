"""P92 席可落代理收窄锁(详设 IC-1 单源)。

出处:迭代详设「腾席资格面与代理收窄」节。旧装配 =
``seat_recoverable=(liquid_refund>0)``(P56 投影金额代理);其申报的
偏宽面(占位件当可变现候选)已随投影读单一源化(燃料滤门)闭合,
残余失真 = 口径错配双向漂:①排除集——投影视图并 T3 活跃集
(sell_gate channel='projection' 支),而腾席臂(M2 缺员/囤腿腾席位、
恒买腾席支)对垫保是 defer 转化类放行非排除(channel='m4_fuel')
⇒ T3 活跃帧投影读 0、席实际可腾 ⇒ 旧代理误判不可达 ⇒ P92 误拦;
②布尔化——「Σ退金>0」非席可落能力布尔。

收窄后:``shop.p92_seat_recoverable`` 直引腾席臂同参资格面
(``fuel_sell_candidates`` ∩ m4_fuel 排除集 ∪ defer 垫保)非空。
行为差方向 = P92 在 T3 活跃帧少拦(差帧 ② 通道真实可达,旧拦为误拦
——白刷病灶面不回归:占位件帧两视图同空,拦刷行为不变)。

锁三层(存续面):
- 判定直调真值表(含占位件负腿:仅占位件帧 ⇒ False,收窄判定经
  fuel_sell_candidates 单一源自动继承占位件滤门);
- 对照锁:同构帧唯一「可腾件」为占位件 → 拦刷 + 分键开火
  (收窄不复活占位件高估灶面)。
(T3 活跃垫保正格的直调锁与集成行为差锁已退役——该正格依赖 T3
活跃帧构造,现行形态下两视图判据同源,行为差面归 falsifiable 复检。)

fixture 说明:角色名/费档注册表现查(CHARACTERS/refresh_prob),帧
构造前提以断言守卫。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bsb,
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
from sr_od.application.currency_war.data.cw_shop_odds import refresh_prob
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    pair_target_comp,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    CwActionRefreshShopParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)

_COMP_PAIR = ('仙舟', '持续伤害')
_ROUND = 2


def _item(slot: int = 1) -> BenchSlot:
    """占位件(kind 直种,supply_box 五分类;SIFT 不可读形态)。"""
    return BenchSlot(kind='supply_box', unit=None)


# ===== 判定直调真值表(shop.p92_seat_recoverable)=====


class TestP92SeatRecoverableDirect:

    def _frame(self, bench: list):
        comp = pair_target_comp(_COMP_PAIR)
        k = tuple(line_members(comp))
        s = _session(comp, plane_lengths=[9, 5, 7], line_state=False)
        axes = {'gold': 100, 'level': 4, 'plane': 1, 'round_num': _ROUND,
                'node': 'reward', 'hp': 100, 'bench': list(bench),
                'front_row': [Unit(char_id='前线', star=1)]}
        return s, axes, k

    def test_truth_table_fuel_vs_empty(self):
        """有可变现 1★ 燃料件 ⇒ True;无可变现件(全 2★)⇒ False。"""
        comp = pair_target_comp(_COMP_PAIR)
        k = tuple(line_members(comp))
        fuel = next(n for n, c in CHARACTERS.items()
                    if n not in k and not getattr(c, 'bench_effect', ''))
        filler2 = next(n for n, c in CHARACTERS.items()
                       if n not in k and n != fuel
                       and not getattr(c, 'bench_effect', ''))
        s, axes, k = self._frame([_bc(fuel, star=1)])
        assert shop.p92_seat_recoverable(
            s, axes['bench'], k, _bsb(**axes), cap_hold=None,
            current_round=_ROUND, defer_names=frozenset()) is True
        s2, axes2, k2 = self._frame([_bc(filler2, star=2)])
        assert shop.p92_seat_recoverable(
            s2, axes2['bench'], k2, _bsb(**axes2), cap_hold=None,
            current_round=_ROUND, defer_names=frozenset()) is False

    def test_placeholder_only_false_t18_gate_inherited(self):
        """仅占位件帧 ⇒ False:收窄判定经 fuel_sell_candidates 单一源
        自动继承占位件滤门(收窄不复活占位件高估灶面)。"""
        s, axes, k = self._frame([_item(slot=1)])
        assert shop.p92_seat_recoverable(
            s, axes['bench'], k, _bsb(**axes), cap_hold=None,
            current_round=_ROUND, defer_names=frozenset()) is False


# ===== 集成行为差锁(P92 门经 decide_shop_screen)=====


def _p92_frame(extra_bench_last: BenchSlot) -> tuple[dict, object, str]:
    """P92 集成种子轴(直达构造;缺员腾席臂隔离声明):

    - gold=100 > g*=50 过 r1 账/r2 预算门直达 P92 位;店空 ⇒ 其余
      买入臂全死(feed 配方在屏空牌面);
    - **全员 owned(缺员 = ∅)**:w 以 1★×1 在席 = 臂①囤腿候选
      (_cnt(m,1)==1 ∧ _cnt(m,2)==0,lv4 可刷 0.65 ∧ 可负担)——② 的
      活性只取决于席可落。缺员置空是隔离关键:缺员 ∧ 席满帧会先触发
      M2 缺员腾席位(shop.py ``missing and bench_free <= 0`` 支)卖件
      腾席、下轮经 bench_free 合法放行,代理差被腾席臂掩蔽;
    - bench 满 9:唯一「可腾件」= 末槽 ``extra_bench_last``
      (垫保 1★ 或占位件),其余全 2★ 非燃料(w 线内非燃料);
    - ①dominance 死(席满)/③EV 生产 fail-closed 死/④无 1★ 同名对死
      (w 单张不成对)。
    """
    comp = pair_target_comp(_COMP_PAIR)
    members = list(_members(comp))
    w = next(m for m in members if CHARACTERS[m].cost == 1)
    assert refresh_prob(4, 1) > 0.0   # 囤腿费档该级可刷(② 活性前提)
    rest = [m for m in members if m != w]
    # 3.6:三段式刷新判据的授权前提——留一名低成本线成员缺员(刷新
    # 有目标可追;级 4 在其概率带内可刷),P92 门可达性保持。
    from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
        levelup as _crit_levelup,
    )
    _miss = next(m for m in rest
                 if _crit_levelup.prob_band_of_cost(
                     int(CHARACTERS[m].cost))[0] <= 4
                 and refresh_prob(4, int(CHARACTERS[m].cost)) > 0.0)
    rest = [m for m in rest if m != _miss]
    bench_rest_len = min(len(rest), BENCH_CAPACITY - 3)
    bench_rest = [_bc(m, star=2) for m in rest[:bench_rest_len]]
    # 全员 owned:主力超出席面的成员入上阵行(测试投影种子,只读消费)
    st_deployed = [Unit(char_id=m, star=2)
                   for i, m in enumerate(rest[bench_rest_len:])]
    assert st_deployed, '锁前提:线成员规模变动(全员 owned 需要上阵位)'
    last_name = (extra_bench_last.unit.char_id
                 if extra_bench_last.unit is not None else '') or ''
    pool = iter(n for n, c in CHARACTERS.items()
                if n not in members and not getattr(c, 'bench_effect', '')
                and n != last_name)
    fill = BENCH_CAPACITY - 2 - len(bench_rest)
    assert fill >= 1, '锁前提:线成员过多(席面装不下)'
    s = _session(comp, plane_lengths=[9, 5, 7], line_state=False)
    bench = [_bc(w, star=1)]
    bench += bench_rest
    bench += [_bc(next(pool), star=2) for _ in range(fill)]
    bench.append(extra_bench_last)
    assert len(bench) == BENCH_CAPACITY   # 席满 = bench_free 0 的承载前提
    axes = {'gold': 100, 'level': 4, 'plane': 2, 'round_num': _ROUND,
            'node': 'reward', 'hp': 100, 'bench': bench,
            'front_row': st_deployed}
    return axes, s, w


class TestP92AssemblyBehaviorDiff:

    def test_placeholder_full_bench_refresh_blocked(self):
        """对照锁:同构帧唯一「可腾件」为占位件 ⇒ 两视图同空 ⇒ 席不可落
        ⇒ 全通道死 ⇒ 拦刷 + 分键开火(收窄不复活占位件高估灶面;
        旧代理与收窄判定在该帧同判,零行为差)。"""
        axes, s, _w = _p92_frame(_item(slot=BENCH_CAPACITY))
        cw4_gs(s, **axes)
        # 3.6:P2 段边界 + 金位账面稳态(三段式刷新判据的授权前提;
        # 边界处理清账面后重锚)。
        from sr_od.application.currency_war.kernel.cw_game_state import (
            game_state_of as _gso2,
        )
        _gs = _gso2(s)
        _gs.node_hist_pos = (2, 1)
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            session_scope as _ss,
        )
        _ss.handle_node_boundary(_gs)
        state_of(s).gold_ledger = axes['gold']
        acts = _decide(s)
        assert not [a for a in acts if isinstance(a, CwActionRefreshShopParam)], acts
        cnt = state_of(s).cw4_counters
        assert cnt.get('p92_no_buy_refresh_blocked', 0) >= 1
