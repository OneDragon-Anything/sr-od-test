"""目标可买席位腿锁定测试(刷新链三组件改革批改造;原存在性门席可落
代理测试随该门整门删除而改造)。

出处:迭代 ``2026-10-28-hp-purge-refresh-reform`` design.md §2.0 第 2 条
+ details/refresh-chain.md §1(席位腿 = 备战席燃料 only 口径)。

判定单一源 = ``criteria.refresh.target_buyable`` 席位腿:席位真值 =
``mandate.fuel_sell_candidates`` 资格面非空(同参装配 =
``sell_gate.sell_exclusions(channel='m4_fuel')`` 形态;counters/dedup
由调用方传入)。「席可腾」在目标可买三腿并集中收口,原独立判定包装
已随存在性门退役。

锁定面:
- 判定直调真值表(席满帧——空位腿置零,席位/合成腿单独可辨):有
  可变现 1★ 燃料件 ⇒ True;无可变现件(全 2★)⇒ False;仅占位件帧
  ⇒ False(``fuel_sell_candidates`` 单一源自动继承占位件滤门,不复活
  占位件高估灶面);
- 集成行为:席满 + 唯一可腾件 = 1★ 燃料 → 刷新发射(追星误拦缺陷
  消除的回归锚);同构帧唯一「可腾件」为占位件 → 三腿全无 → 拒
  (关店,拒因 ``target_unbuyable``)。

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
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    refresh as crit_refresh,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)

_COMP_PAIR = ('仙舟', '持续伤害')
_COMP_INTEGRATION = '专家桑博DOT'
_ROUND = 2


def _item() -> BenchSlot:
    """占位件(kind 直种,supply_box 五分类;SIFT 不可读形态)。"""
    return BenchSlot(kind='supply_box', unit=None)


# ===== 判定直调真值表(criteria.refresh.target_buyable 席位腿)=====


class TestTargetBuyableSeatLegDirect:
    """席满帧直调(空位腿置零,席位/合成腿单独可辨)。"""

    def _frame(self, bench: list):
        comp = pair_target_comp(_COMP_PAIR)
        k = tuple(line_members(comp))
        s = _session(comp, plane_lengths=[9, 5, 7])
        axes = {'gold': 100, 'level': 4, 'plane': 1, 'round_num': _ROUND,
                'node': 'reward', 'hp': 100, 'bench': list(bench),
                'front_row': [Unit(char_id='前线', star=1)]}
        gs = _bsb(s, **axes)
        assert len(bench) == BENCH_CAPACITY, '测试前提:席满承载'
        return s, gs, k

    def test_truth_table_fuel_vs_full_2star(self):
        """席满 + 唯一 1★ 非线燃料 ⇒ True;席满全 2★ 非燃料 ⇒ False。

        合成腿前置守卫:帧内无「恰 2 张全 1★」形态(目标名单名)——
        席位腿真值单独可辨。"""
        comp = pair_target_comp(_COMP_PAIR)
        k = tuple(line_members(comp))
        fuel = next(n for n, c in CHARACTERS.items()
                    if n not in k and not getattr(c, 'bench_effect', ''))
        filler2 = next(n for n, c in CHARACTERS.items()
                       if n not in k and n != fuel
                       and not getattr(c, 'bench_effect', ''))
        # 席满 + 末槽 1★ 燃料:席位腿真。
        bench_fuel = [_bc(m, star=2) for m in k[:BENCH_CAPACITY - 2]]
        bench_fuel += [_bc(filler2, star=2), _bc(fuel, star=1)]
        s, gs, _k = self._frame(bench_fuel)
        assert crit_refresh.target_buyable(gs, s, (fuel,),
                                           k_members=k) is True
        # 席满全 2★ 非燃料:三腿全无。
        bench_dead = [_bc(m, star=2) for m in k[:BENCH_CAPACITY - 1]]
        bench_dead += [_bc(filler2, star=2)]
        s2, gs2, k2 = self._frame(bench_dead)
        assert crit_refresh.target_buyable(gs2, s2, (fuel,),
                                           k_members=k2) is False

    def test_placeholder_only_false_filter_inherited(self):
        """席满仅占位件帧 ⇒ False:席位腿经 ``fuel_sell_candidates``
        单一源自动继承占位件滤门(占位件无卖出交互且无金币现值,
        任何星级不可变现)。"""
        comp = pair_target_comp(_COMP_PAIR)
        k = tuple(line_members(comp))
        bench = [_bc(m, star=2) for m in k[:BENCH_CAPACITY - 1]]
        bench += [_item()]
        s, gs, _k = self._frame(bench)
        assert crit_refresh.target_buyable(gs, s, (k[0],),
                                           k_members=k) is False


# ===== 集成行为测试(席位腿经 decide_shop_screen 全链)=====


def _seat_frame(extra_bench_last: BenchSlot):
    """席位腿对照帧(锁定线槽 = 真实注册表线,刷新授权前提 = 锁定后
    星级目标〔stay_target〕)。

    - comp = 专家桑博DOT(真实线,need_star['桑博'] = 3、桑博 1 费):
      全员 owned、桑博 1★ → 停留目标 (桑博, 3★, 1 费);level 4 ≥ 1 费
      带下界 ∧ refresh_prob(4, 1) > 0 ⇒ 三段式判据可刷(目标可买
      可达前提);
    - bench 满 9:唯一「可腾件」= 末槽 ``extra_bench_last``
      (垫保 1★ 燃料或占位件),其余全 2★ 非燃料(线内非燃料);
    - 店面空(买面全通道死,刷新链直达);桑博单副本(合成腿死)。
    """
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    comp = get_comp(_COMP_INTEGRATION)
    members = list(_members(comp))
    w = next(m for m in members if (comp.need_star or {}).get(m, 1) >= 2
             and int(CHARACTERS[m].cost) <= 2)
    assert refresh_prob(4, int(CHARACTERS[w].cost)) > 0.0
    rest = [m for m in members if m != w]
    bench_rest_len = min(len(rest), BENCH_CAPACITY - 3)
    bench_rest = [_bc(m, star=2) for m in rest[:bench_rest_len]]
    last_name = (extra_bench_last.unit.char_id
                 if extra_bench_last.unit is not None else '') or ''
    pool = iter(n for n, c in CHARACTERS.items()
                if n not in members and not getattr(c, 'bench_effect', '')
                and n != last_name)
    fill = BENCH_CAPACITY - 2 - len(bench_rest)
    assert fill >= 1, '测试前提:线成员过多(席面装不下)'
    s = _session(comp, plane_lengths=[9, 5, 7])
    bench = [_bc(w, star=1)]
    bench += bench_rest
    bench += [_bc(next(pool), star=2) for _ in range(fill)]
    bench.append(extra_bench_last)
    assert len(bench) == BENCH_CAPACITY   # 席满 = bench_free 0 的承载前提
    # 上阵行非空(空板止损守卫 = fuel_sell_candidates 前置资格门,
    # 板空帧燃料资格面恒空——席位腿正格要求 deployed 占用 ≥ 1;
    # 非线 2★ 填充件,测试投影种子,只读消费)。
    st_deployed = [Unit(char_id=m, star=2)
                   for m in rest[bench_rest_len:]]
    if not st_deployed:
        st_deployed = [Unit(char_id=next(pool), star=2)]
    axes = {'gold': 100, 'level': 4, 'plane': 2, 'round_num': _ROUND,
            'node': 'reward', 'hp': 100, 'bench': bench,
            'front_row': st_deployed}
    return axes, s, w


def _enter_plane2(s, axes: dict):
    """种子帧入位面 2 稳态(节点水位线 + 边界执行 + 金位账面重锚)。"""
    cw4_gs(s, **axes)
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
    return _gs


class TestSeatLegIntegration:

    def test_full_bench_with_fuel_refresh_emits(self):
        """席满 + 唯一可腾件 = 1★ 燃料 → 刷新发射(追星误拦缺陷消除
        的回归锚:旧存在性门在该帧误拦——满席帧席位腿现为放行腿)。"""
        from sr_od.application.currency_war.kernel.cw_comps import get_comp
        comp = get_comp(_COMP_INTEGRATION)
        fuel = next(n for n, c in CHARACTERS.items()
                    if n not in set(_members(comp))
                    and n not in four_system_guard()
                    and not getattr(c, 'bench_effect', ''))
        axes, s, _w = _seat_frame(_bc(fuel, star=1))
        _enter_plane2(s, axes)
        acts = _decide(s)
        refreshes = [a for a in acts if isinstance(a, CwActionRefreshShopParam)]
        assert refreshes, f'席满可腾帧刷新应发射: {acts!r}'
        assert refreshes[0].cost > 0, '付费刷新(免费腿未在册)'

    def test_placeholder_full_bench_refresh_blocked(self):
        """对照帧:同构帧唯一「可腾件」为占位件 ⇒ 三腿全无 ⇒ 拒
        (关店)+ 拒因 ``target_unbuyable`` 计数在册(占位件滤门经
        ``fuel_sell_candidates`` 单一源继承,不复活占位件高估灶面)。"""
        axes, s, _w = _seat_frame(_item())
        _enter_plane2(s, axes)
        acts = _decide(s)
        # 驱动器契约:关店为收尾终结动作不入序列,拒因计数 = 拒绝路径
        # 在册证据。
        assert not [a for a in acts
                    if isinstance(a, CwActionRefreshShopParam)], acts
        cnt = state_of(s).cw4_counters
        assert cnt.get('shop_refresh_target_unbuyable', 0) >= 1


def four_system_guard() -> frozenset[str]:
    """四体系成员名集(测试帧燃料名守卫;单一源 = protection)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.protection import (
        four_system_members,
    )
    return frozenset(four_system_members())
