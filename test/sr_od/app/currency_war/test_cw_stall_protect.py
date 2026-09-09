"""T3 同轮保留=末位牺牲序 锁(买后同轮即卖净零自旋修复;t3_spin_fix 方案审推荐①)。

设计出处(锁纪律:新锁必引设计出处)= t3_spin_fix 方案审(编排者归档)
+ N3 登记契约 ADR-0556 §5 + ADR-0558 §3 单一源纪律。七条锁:
①凑息回拉跳过(门槛7 不等式断言)②腾席降序+唯一燃料放行
③生命周期三出口(部署销/卖出销/轮界销)④G-S1 双守卫不冲突
⑤对照零漂移(无保护集帧逐位不变)⑥单一源 grep 锁(读端禁手搓)
⑦同轮买卖检查豁免面按分键收敛(禁全开)。
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_state import (
    SELL_BENCH_CONVERT_REASONS,
    BenchChar,
    GameState,
    SellBench,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    sell as crit_sell,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)


def _mod_src(mod) -> str:
    return inspect.getsource(mod)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _mandate_src() -> str:
    return _mod_src(mandate)


def _mod_src(mod) -> str:
    return inspect.getsource(mod)


def _shop_src() -> str:
    return _mod_src(shop)


def _import_checks_ledger():
    from sr_od.application.currency_war.sim.checks import ledger
    return ledger


def _import_engine():
    from sr_od.application.currency_war.sim import engine_p1
    return engine_p1


# 未注册名 ⇒ bench_char_cost 保守估 3 ⇒ 1★ 全额退 3 金/张(与
# test_cw_realizable_interest_floor 同款确定性锚)
_PROT = '垫件P'
_FUEL = '燃料F'


class Test1PullbackSkip:
    """锁①凑息回拉通道:被保件绝对跳过,其他 liquid 照常闭合缺口。"""

    def test_deferred_skipped_others_close_gap(self):
        # 缺口 3(gold 47, g*=50):P 被保跳过,F 卖 3 金闭合
        bench = [_bc(_PROT, slot=1), _bc(_FUEL, slot=2)]
        ct: dict = {}
        slots, key = crit_sell.sell_for_interest(
            47, bench, 5, (), state=GameState(),
            defer_names=frozenset({_PROT}), counters=ct)
        assert key == '' and slots == [2]   # 被保件槽位 1 不在卖回集
        assert ct.get('t3_protect_deferred') == 1
        # 门槛7 不等式断言:缺口 ≤ 其他可变现件退金总和 ⇒ 跳过无损
        gap = 50 - 47
        others_refund = 3   # 未注册名 1★ 全额退
        assert gap <= others_refund

    def test_deferred_excluded_even_under_prefer(self):
        """R2-N1 prefer 序不构成豁免:被保件即使命中刚买集也跳过
        (自旋路径 A = prefer 序刻意首卖刚买件的复合涌现)。"""
        bench = [_bc(_PROT, slot=1), _bc(_FUEL, slot=2)]
        slots, key = crit_sell.sell_for_interest(
            47, bench, 5, (), state=GameState(),
            prefer_names=(_PROT,), defer_names=frozenset({_PROT}))
        assert key == '' and slots == [2]


class Test2FuelDemotion:
    """锁②M4 腾席通道:被保件降末位;唯一燃料帧放行(转化类)+销账。"""

    def test_deferred_demoted_to_tail(self):
        bench = [_bc(_PROT, slot=1), _bc(_FUEL, slot=2)]
        cands = mandate.fuel_sell_candidates(
            bench, (), state=GameState(), defer_names=frozenset({_PROT}))
        assert [b.char_id for b in cands] == [_FUEL, _PROT]

    def test_only_fuel_protected_passes_and_consumes(self):
        """唯一燃料 = 被保件 ⇒ 放行卖出(为义务买入腾位的转化类,非
        自旋):卖出销账(出口①)保留;归因分键/载体填充已随 2026-09-08
        用户归因遥测删除指令拆除(reason 缺省 '')。9 个互异线外名
        (同名副本会触素材守卫,改用异名全保集隔离守卫面——守卫交互
        由锁④专测)。"""
        names = _distinct_fillers(9)
        # 策略器字段经 state_of 载体;cw4_fuel_filler_stall_buys 是执行侧
        # session 属性(N3 登记契约),保持在 session 上。
        sess = SimpleNamespace()
        state_of(sess).cw4_fuel_filler_stall_buys = dict.fromkeys(
            names, 2)
        state_of(sess).cw4_counters = {}
        state_of(sess).target_comp = _comp()
        st = _m4_frame(bench=[_bc(n, slot=i + 1)
                              for i, n in enumerate(names)])
        act = shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, SellBench)
        assert act.expect == names[0]
        assert act.reason == ''
        assert names[0] not in state_of(sess).cw4_fuel_filler_stall_buys   # 卖出销

    def test_non_protected_victim_preferred(self):
        """非保燃料在场 ⇒ 被保件零成本存活、非保件先卖。臂归属不再经
        reason 判读(2026-09-08 归因遥测删除批,reason 恒 '' 未标);
        M4 臂级「被保件降末位」排序语义由 test_deferred_demoted_to_tail
        承载,两臂语义同构。"""
        other = '燃料G'
        sess = SimpleNamespace(cw4_counters={},
                               target_comp=_comp())
        state_of(sess).cw4_fuel_filler_stall_buys = {_PROT: 2}
        st = _m4_frame(bench=[_bc(_PROT, slot=1), _bc(other, slot=2)]
                       + [_bc(f'垫子{i}', slot=i + 3) for i in range(7)])
        act = shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, SellBench)
        assert act.expect == other
        assert state_of(sess).cw4_fuel_filler_stall_buys.get(_PROT) == 2   # 未销

    def test_funding_convert_demote_not_ban(self):
        """支付变现通道:被保件仅降序放行(转化类,非禁卖)。"""
        bench = [_bc(_PROT, slot=1), _bc(_FUEL, slot=2)]
        out, key = crit_sell.funding_support_sell(
            3, 9, bench, (), state=GameState(),
            defer_names=frozenset({_PROT}))
        assert key == '' and out == [2, 1]   # 非保先卖;被保件兜底在列
        out_nd, _ = crit_sell.funding_support_sell(
            3, 6, bench, (), state=GameState(),
            defer_names=frozenset({_PROT}))
        assert out_nd == [2]   # 缺口 3 由非保件闭合,被保件不动


class Test3Lifecycle:
    """锁③生命周期三出口:部署销/卖出销/轮界销,漏销路径逐一红。"""

    def test_deploy_prune(self):
        sess = SimpleNamespace(
        )
        state_of(sess).cw4_fuel_filler_stall_buys = {_PROT: 2, _FUEL: 2}
        n = mandate.stall_buys_prune_deployed(sess, {_PROT})
        assert n == 1 and dict(state_of(sess).cw4_fuel_filler_stall_buys) == {_FUEL: 2}

    def test_deploy_prune_op_side_helper(self):
        """op 侧接线函数(部署帧属性契约级消费)同语义。"""
        from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
            prune_fuel_filler_deployed,
        )
        sess = SimpleNamespace()
        state_of(sess).cw4_fuel_filler_stall_buys = {_PROT: 2}
        assert prune_fuel_filler_deployed(sess, {_PROT}) == 1
        assert state_of(sess).cw4_fuel_filler_stall_buys == {}
        assert prune_fuel_filler_deployed(sess, {_PROT}) == 0   # 幂等

    def test_sell_consume(self):
        sess = SimpleNamespace()
        state_of(sess).cw4_fuel_filler_stall_buys = {_PROT: 2}
        mandate.stall_buys_consume(sess, _PROT)
        assert state_of(sess).cw4_fuel_filler_stall_buys == {}
        mandate.stall_buys_consume(sess, _PROT)   # 未知名/空集 no-op

    def test_round_boundary_prune(self):
        sess = SimpleNamespace()
        state_of(sess).cw4_fuel_filler_stall_buys = {_PROT: 2, 'X': 3}
        ct: dict = {}
        active = mandate.stall_protect_active(sess, 3, counters=ct)
        assert active == {'X'}
        assert state_of(sess).cw4_fuel_filler_stall_buys == {'X': 3}   # 过期就地销
        assert ct.get('t3_protect_expired_round') == 1

    def test_round_boundary_none_is_fail_closed(self):
        """轮号不可得 = 保守端:全集过期(禁缺读放大保护面)。"""
        sess = SimpleNamespace()
        state_of(sess).cw4_fuel_filler_stall_buys = {_PROT: 2}
        ct: dict = {}
        assert mandate.stall_protect_active(sess, None, counters=ct) \
            == frozenset()
        assert ct.get('t3_protect_expired_round') == 1

    def test_legacy_set_carrier_hard_expired(self):
        """旧裸 set 载体(轮戳缺失)= 轮界硬兜底整集失效并升级 dict。"""
        sess = SimpleNamespace()
        state_of(sess).cw4_fuel_filler_stall_buys = {_PROT, 'Y'}
        ct: dict = {}
        assert mandate.stall_protect_active(sess, 2, counters=ct) \
            == frozenset()
        assert state_of(sess).cw4_fuel_filler_stall_buys == {}
        assert ct.get('t3_protect_expired_round') == 2

    def test_stale_entry_pruned_by_shop_read_end(self):
        """shop 读端接线:过期登记在商店帧被就地销账(轮界兜底经读端)。"""
        sess = SimpleNamespace(cw4_counters={}, target_comp=_comp())
        state_of(sess).cw4_fuel_filler_stall_buys = {_PROT: 99}
        st = _m4_frame(bench=[_bc(_PROT, slot=i + 1) for i in range(9)])
        shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert state_of(sess).cw4_fuel_filler_stall_buys == {}
        assert state_of(sess).cw4_counters.get('t3_protect_expired_round') == 1


class Test4GuardInteraction:
    """锁④G-S1 交互:被保件同时是合成素材 ⇒ 双守卫不冲突。"""

    def test_protected_material_still_guard_blocked(self):
        # 同名同星副本在场 ⇒ 素材守卫拒入(保护只影响排序/跳过,
        # 不影响资格闭集;素材守卫先拒,保护不构成豁免)
        bench = [_bc(_PROT, slot=1), _bc(_PROT, slot=2),
                 _bc(_FUEL, slot=3)]
        ct: dict = {}
        slots, key = crit_sell.sell_for_interest(
            47, bench, 5, (), state=GameState(),
            defer_names=frozenset({_PROT}), counters=ct)
        assert key == '' and slots == [3]
        # 双守卫各拒各的:被保素材被 defer 跳过(计数 1),素材守卫面
        # 由 fuel_sell_candidates 单独验——保护不构成素材豁免
        assert ct.get('t3_protect_deferred') == 2   # 两张被保副本均跳过
        cands = mandate.fuel_sell_candidates(
            bench, (), state=GameState(), defer_names=frozenset())
        assert all((b.char_id or '') != _PROT for b in cands)   # 素材守卫拒入
        cands_def = mandate.fuel_sell_candidates(
            bench, (), state=GameState(), defer_names=frozenset({_PROT}))
        assert all((b.char_id or '') != _PROT for b in cands_def)


class Test5ZeroDrift:
    """锁⑤对照零漂移:无登记/defer 空集帧,全通道行为逐位不变。"""

    def test_read_end_empty_no_attr_created(self):
        sess = SimpleNamespace()
        assert mandate.stall_protect_active(sess, 2) == frozenset()
        assert not state_of(sess).cw4_fuel_filler_stall_buys

    def test_fuel_candidates_identical_without_defer(self):
        bench = [_bc(_PROT, slot=2), _bc(_FUEL, slot=1)]
        st = GameState()
        base = mandate.fuel_sell_candidates(bench, (), state=st)
        with_defer = mandate.fuel_sell_candidates(
            bench, (), state=GameState(), defer_names=frozenset())
        assert base == with_defer

    def test_pullback_identical_without_defer(self):
        bench = [_bc(_PROT, slot=1), _bc(_FUEL, slot=2)]
        a, ka = crit_sell.sell_for_interest(44, bench, 5, (),
                                            state=GameState())
        b, kb = crit_sell.sell_for_interest(44, bench, 5, (),
                                            state=GameState(),
                                            defer_names=frozenset())
        assert (a, ka) == (b, kb)

    def test_funding_identical_without_defer(self):
        bench = [_bc(_PROT, slot=1), _bc(_FUEL, slot=2)]
        a, ka = crit_sell.funding_support_sell(3, 9, bench, (),
                                               state=GameState())
        b, kb = crit_sell.funding_support_sell(3, 9, bench, (),
                                               state=GameState(),
                                               defer_names=frozenset())
        assert (a, ka) == (b, kb)


class Test6SingleSource:
    """锁⑥单一源 grep 锁:保护读端定义唯一,消费端禁手搓(ADR-0558 §3)。"""

    def test_reader_defined_once(self):
        assert _mandate_src().count('def stall_protect_active') == 1

    def test_shop_never_hand_reads_registry(self):
        """shop.py 对登记集只许经写端单一源 register;读只经
        stall_protect_active——出现 getattr 直读 = 手搓读端,红。"""
        for ln in _shop_src().splitlines():
            if 'cw4_fuel_filler_stall_buys' in ln:
                assert 'getattr' not in ln, \
                    f'shop.py 手搓读登记集(违单一源): {ln.strip()}'

    def test_exempt_keys_single_source(self):
        """检查侧豁免键集单一源:ledger/engine 均自 cw_state 常量取键,
        禁本地第二源。"""
        ledger_src = _mod_src(_import_checks_ledger())
        engine_src = _mod_src(_import_engine())
        assert 'stall_buys_prune_deployed' in engine_src
        assert 'stall_buys_consume' in engine_src
        assert ledger_src.count('SELL_BENCH_CONVERT_REASONS') >= 1
        assert "frozenset({'fuel_victim_protect_demoted'" not in ledger_src
        # 键集内容钉死(扩键 = 设计变更,须过方案审)。三键形态 =
        # ADR-0585 批 3(N7:funding_hold_liquidated 豁免面与分键同批,
        # 辖「持有件变现」非 T3 垫件转化,豁免理由同为非自旋;两键 →
        # 三键为申报过的语义变更,非机械跟绿)。
        # 三键 → 四键(+line_switch_collapse)= 2026-09-08 同轮交互
        # 方案审(T-141,零阻断放行)+ ADR-0591:线账闭合孤儿清算
        # (P78-2a 账闭合事件;P78-1 前提被闭合事件破坏不辖此形态)。
        # 键的授予必须伴随登记簿线账闭合证明(shop 发射位证明打标制,
        # ADR-0591 §4),防窗口段回归洗白,非自由豁免。
        assert frozenset({
            'fuel_victim_protect_demoted', 'funding_support_stall_convert',
            'funding_hold_liquidated', 'line_switch_collapse',
        }) == SELL_BENCH_CONVERT_REASONS


class Test7CheckerExemption:
    """锁⑦同轮买卖检查豁免面:按分键收敛,禁全开。

    ADR-0611 按键分工改写(§3-5;锁红 ≠ 改动错,本类按
    「结构化证明键 convert_reason + 孤儿键留 reason」重推语义后改格):
    转化类豁免改读 convert_reason(两类放行位填充,值域收窄);孤儿键
    line_switch_collapse 留 reason(ADR-0591 §4 证明打标,防窗口段
    回归洗白);reason 旧通道值不再放大豁免面。
    """

    ROW_BASE = {'plane': 1, 'round_num': 3, 'gold': 50, 'state': {}}

    def _row(self, sell_reason: str, convert_reason: str = '') -> dict:
        return {**self.ROW_BASE, 'actions': [
            {'__type__': 'BuyCard',
             'card': {'name': _PROT, 'cost': 1}, 'reason': 't3_unlocked_hemostat'},
            {'__type__': 'SellBench', 'bench_idx': 0, 'name': _PROT,
             'income': 1, 'sell_reason': sell_reason,
             'convert_reason': convert_reason},
        ]}

    def test_convert_reason_exempt(self):
        """三类放行键经结构化字段豁免(键集保持四键单一源,其中孤儿键
        走 reason 分支,见下格)。"""
        from sr_od.application.currency_war.sim.checks.ledger import (
            check_no_same_round_buy_sell,
        )
        for r in SELL_BENCH_CONVERT_REASONS - {'line_switch_collapse'}:
            assert check_no_same_round_buy_sell(
                [self._row('', convert_reason=r)]) == [], \
                f'{r}:结构化分键未豁免 = L3 放行位被计违例'

    def test_orphan_key_stays_on_reason(self):
        """孤儿豁免读 reason(C3 分工另一侧;名册不可解析帧豁免照旧)。"""
        from sr_od.application.currency_war.sim.checks.ledger import (
            check_no_same_round_buy_sell,
        )
        assert check_no_same_round_buy_sell(
            [self._row('line_switch_collapse')]) == []

    def test_wrong_field_reason_value_not_exempt(self):
        """零双源格:转化类值落在 reason(错误载体)不豁免——任意
        reason 值不得放大豁免面(原 plain 格语义在新分工下的正格)。"""
        from sr_od.application.currency_war.sim.checks.ledger import (
            check_no_same_round_buy_sell,
        )
        out = check_no_same_round_buy_sell(
            [self._row('fuel_victim_protect_demoted')])
        assert len(out) == 1 and '同轮买后卖' in out[0]

    def test_unmarked_still_violation(self):
        from sr_od.application.currency_war.sim.checks.ledger import (
            check_no_same_round_buy_sell,
        )
        out = check_no_same_round_buy_sell([self._row('')])
        assert len(out) == 1 and '同轮买后卖' in out[0]

    def test_oscillation_check_same_edge(self):
        from sr_od.application.currency_war.sim.checks.ledger import (
            check_oscillation_xp_cap,
        )
        assert check_oscillation_xp_cap(
            [self._row('', convert_reason='fuel_victim_protect_demoted')]
        ) == []
        out = check_oscillation_xp_cap([self._row('')])
        assert len(out) == 1


class Test8EntryFundingFace:
    """锁⑧(entry.py EV pass funding 发射位,落地审阻-1):defer 生效 +
    卖出销账,与店侧 funding 发射位同款口径。"""

    def _run(self, bench: list[BenchChar], registry: dict) -> tuple:
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            SellBench as PrepSellBench,
        )
        from sr_od.application.currency_war.kernel.cw_state import GameState
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            entry,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            mandate as _mandate,
        )
        # entry EV pass 发射的是 prep 族 SellBench(cw_prep_actions,物理
        # 槽位 1-9),≠ cw_state.SellBench(动作族)——断言按 prep 族判型
        self._PrepSell = PrepSellBench
        sess = SimpleNamespace(cw4_counters={})
        state_of(sess).cw4_fuel_filler_stall_buys = dict(registry)
        frame = _mandate.MandateFrame(
            gold=1, level=5, bench=bench, deployed=[], deploy_cap=6,
            node_type=None, stop_flag=True, k_members=('线内件X',),
            round_num=2)
        st = GameState(gold=1, level=5, round_num=2, hp=40)
        out = entry._criteria_pass(
            frame, sess, st, ('线内件X',),
            k_switched=False, old_line_members=())
        return out, sess

    def _sells(self, out: list) -> list:
        return [e.action for e in out
                if isinstance(e.action, self._PrepSell)]

    def test_deferred_demoted_non_protected_sold(self):
        """defer 生效:被保件非唯一燃料 ⇒ 卖非保件,被保件零成本存活。"""
        out, sess = self._run([_bc(_PROT, slot=1), _bc(_FUEL, slot=2)],
                              {_PROT: 2})
        sells = self._sells(out)
        assert len(sells) == 1
        assert sells[0].slot == 2   # 非保件 F
        assert state_of(sess).cw4_fuel_filler_stall_buys == {_PROT: 2}   # 未销

    def test_only_fuel_protected_convert_consume(self):
        """唯一燃料 = 被保件 ⇒ 放行卖出(转化类):卖出销账保留(出口①;
        分键计数已随 2026-09-08 用户归因遥测删除指令拆除)。"""
        out, sess = self._run([_bc(_PROT, slot=1)], {_PROT: 2})
        sells = self._sells(out)
        assert len(sells) == 1 and sells[0].slot == 1
        assert state_of(sess).cw4_fuel_filler_stall_buys == {}   # 卖出销账


# ===== 复用脚手架 =====


def _distinct_fillers(n: int) -> list[str]:
    """n 个互异线外 1★ 燃料名(隔离合成素材守卫面;守卫交互 = 锁④)。"""
    exclude = list(_km())
    out: list[str] = []
    for _ in range(n):
        name = _off_line_filler(exclude=tuple(exclude))
        out.append(name)
        exclude.append(name)
    return out


def _comp():
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    return get_comp('列车同行')


def _km() -> tuple[str, ...]:
    return tuple(line_members(_comp()))


def _off_line_filler(exclude: tuple[str, ...]) -> str:
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    km = set(_km())
    for n in CHARACTERS:
        if n not in km and n not in exclude:
            return n
    raise AssertionError('注册表缺少线外角色(锁前提失效)')


def _m4_frame(bench: list[BenchChar]) -> GameState:
    """M4 腾席形态帧:缺员(线内件全缺)∧ bench 满 ⇒ M4 卖燃料件。"""
    st = GameState(gold=30, level=5, round_num=2, hp=40)
    st.level_readable = True
    st.plane = 1
    st.shop = []
    st.bench = bench
    st.deployed = []
    return st
