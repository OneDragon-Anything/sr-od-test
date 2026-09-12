"""P92 席可落代理收窄锁(T-20;旧账 T-316/详设 IC-1 单源)。

出处:迭代详设「腾席资格面与代理收窄」T-20 节。旧装配 =
``seat_recoverable=(liquid_refund>0)``(P56 投影金额代理);其申报的
偏宽面(占位件当可变现候选)已随投影读单一源化(T-18 燃料滤门)闭合,
残余失真 = 口径错配双向漂:①排除集——投影视图并 T3 活跃集
(sell_gate channel='projection' 支),而腾席臂(M2 缺员/囤腿腾席位、
恒买腾席支)对垫保是 defer 转化类放行非排除(channel='m4_fuel')
⇒ T3 活跃帧投影读 0、席实际可腾 ⇒ 旧代理误判不可达 ⇒ P92 误拦;
②布尔化——「Σ退金>0」非席可落能力布尔。

收窄后:``shop.p92_seat_recoverable`` 直引腾席臂同参资格面
(``fuel_sell_candidates`` ∩ m4_fuel 排除集 ∪ defer 垫保)非空。
行为差方向 = P92 在 T3 活跃帧少拦(差帧 ② 通道真实可达,旧拦为误拦
——白刷病灶面不回归:占位件帧两视图同空,拦刷行为不变)。

锁三层:
- 判定直调真值表(含垫保前提对:同名同轮帧 T3 名 ∈ 投影排除集 ∧
  ∉ m4_fuel 排除集——两排除集差 = T3 活跃集,收窄差的存在性地基);
- 集成行为差锁:席满 + 囤腿候选可刷可负担 + 唯一可腾件为 T3 活跃帧
  → 刷新放行(旧代理该帧必拦;缺员置空隔离 M2 缺员腾席臂的先卖
  后刷掩蔽效应);
- 对照锁:同构帧唯一「可腾件」为占位件 → 拦刷 + 分键开火
  (收窄不复活占位件高估,T-18 灶面回归网)。

fixture 说明:角色名/费档注册表现查(CHARACTERS/refresh_prob),帧
构造前提以断言守卫;垫保登记走发射登记单一入口
``sell_gate.register_launch(cause='stall_protect')``(同轮活跃 =
τ=同轮,P78 §2.2)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_shop_odds import refresh_prob
from sr_od.application.currency_war.kernel import cw_intention
from sr_od.application.currency_war.kernel.cw_intention import (
    pair_target_comp,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    BenchChar,
    CwWorkFrame,
    RefreshShop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    sell_gate,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_decide as _decide,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_members as _members,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_session as _session,
)

_COMP_PAIR = ('仙舟', '持续伤害')
_ROUND = 2


def _item(slot: int = 1) -> BenchChar:
    """占位件(T-216 假环境同款形态):SIFT 不可读 → char_id=''、1★。"""
    return BenchChar(slot=slot, char_id='', star=1, is_item_slot=True)


def _t3_name(session, k: tuple[str, ...]) -> str:
    """垫保登记名:线外、无后台效果、非 m4_fuel 排除集成员(前提守卫,
    注册表/持有集变动时本文件红在前提而非行为断言)。"""
    km = set(k)
    for n, c in CHARACTERS.items():
        if n in km or getattr(c, 'bench_effect', ''):
            continue
        return n
    raise AssertionError('注册表缺少线外无效果角色(锁前提失效)')


def _t3_premise(session, state: CwWorkFrame, k: tuple[str, ...],
                t3: str) -> None:
    """收窄差的存在性地基:T3 活跃名 ∈ 投影排除集(旧代理视角不可变现)
    ∧ ∉ m4_fuel 排除集(腾席臂视角可转化放行)。两集合差 = T3 活跃集,
    任何一侧前提失效 = sell_gate 通道语义变更,本文件红在前提。"""
    cap_hold = cw_intention.locked_buy_cap_hold(state)
    excl_m4 = sell_gate.sell_exclusions(session, k, channel='m4_fuel',
                                        cap_hold=cap_hold,
                                        current_round=_ROUND)
    excl_proj = sell_gate.sell_exclusions(session, k, channel='projection',
                                          cap_hold=cap_hold,
                                          current_round=_ROUND)
    assert t3 in excl_proj, '前提失效:T3 活跃名不在投影视图(旧代理差面消失)'
    assert t3 not in excl_m4, '前提失效:T3 活跃名被 m4_fuel 排除(腾席臂不可腾?)'


# ===== 判定直调真值表(shop.p92_seat_recoverable)=====


class TestP92SeatRecoverableDirect:

    def _frame(self, bench: list[BenchChar]):
        comp = pair_target_comp(_COMP_PAIR)
        k = tuple(line_members(comp))
        s = _session(comp, plane_lengths=[9, 5, 7], line_state=False)
        st = CwWorkFrame(gold=100, level=4, plane=1, round_num=_ROUND,
                       node_type='reward', hp=100)
        st.bench = list(bench)
        st.deployed = [_bc('前线', slot=1)]
        return s, st, k

    def test_truth_table_fuel_vs_empty(self):
        """有可变现 1★ 燃料件 ⇒ True;无可变现件(全 2★)⇒ False。"""
        comp = pair_target_comp(_COMP_PAIR)
        k = tuple(line_members(comp))
        fuel = next(n for n, c in CHARACTERS.items()
                    if n not in k and not getattr(c, 'bench_effect', ''))
        filler2 = next(n for n, c in CHARACTERS.items()
                       if n not in k and n != fuel
                       and not getattr(c, 'bench_effect', ''))
        s, st, k = self._frame([_bc(fuel, star=1, slot=1)])
        assert shop.p92_seat_recoverable(
            s, st.bench, k, st, cap_hold=None, current_round=_ROUND,
            defer_names=frozenset()) is True
        s2, st2, k2 = self._frame([_bc(filler2, star=2, slot=1)])
        assert shop.p92_seat_recoverable(
            s2, st2.bench, k2, st2, cap_hold=None, current_round=_ROUND,
            defer_names=frozenset()) is False

    def test_placeholder_only_false_t18_gate_inherited(self):
        """仅占位件帧 ⇒ False:收窄判定经 fuel_sell_candidates 单一源
        自动继承 T-18 占位件滤门(收窄不复活占位件高估灶面)。"""
        s, st, k = self._frame([_item(slot=1)])
        assert shop.p92_seat_recoverable(
            s, st.bench, k, st, cap_hold=None, current_round=_ROUND,
            defer_names=frozenset()) is False

    def test_t3_active_only_fuel_true(self):
        """行为差帧(直调):唯一可腾件为 T3 活跃垫保件 ⇒ True。
        旧代理同帧 = 投影读排除 T3 ⇒ liquid_refund=0 ⇒ False ⇒ P92
        误拦;收窄后腾席臂 defer 转化放行语义如实建模。"""
        comp = pair_target_comp(_COMP_PAIR)
        k = tuple(line_members(comp))
        s = _session(comp, plane_lengths=[9, 5, 7], line_state=False)
        t3 = _t3_name(s, k)
        assert sell_gate.register_launch(
            s, t3, cause='stall_protect', round_num=_ROUND)
        st = CwWorkFrame(gold=100, level=4, plane=1, round_num=_ROUND,
                       node_type='reward', hp=100)
        st.bench = [_bc(t3, star=1, slot=1)]
        st.deployed = [_bc('前线', slot=1)]
        _t3_premise(s, st, k, t3)
        assert shop.p92_seat_recoverable(
            s, st.bench, k, st, cap_hold=cw_intention.locked_buy_cap_hold(st),
            current_round=_ROUND, defer_names=frozenset({t3})) is True


# ===== 集成行为差锁(P92 门经 decide_shop_screen)=====


def _p92_frame(extra_bench_last: BenchChar) -> tuple[CwWorkFrame, object, str]:
    """P92 集成帧(直达构造;缺员腾席臂隔离声明):

    - gold=100 > g*=50 过 r1 账/r2 预算门直达 P92 位;店空 ⇒ 其余
      买入臂全死;
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
    bench_rest_len = min(len(rest), BENCH_CAPACITY - 3)
    bench_rest = [_bc(m, star=2, slot=1) for m in rest[:bench_rest_len]]
    # 全员 owned:主力超出席面的成员入 deployed(测试投影帧,只读消费)
    st_deployed = [_bc(m, star=2, slot=i + 1)
                   for i, m in enumerate(rest[bench_rest_len:])]
    assert st_deployed, '锁前提:线成员规模变动(全员 owned 需要上阵位)'
    pool = iter(n for n, c in CHARACTERS.items()
                if n not in members and not getattr(c, 'bench_effect', '')
                and n != (extra_bench_last.char_id or ''))
    fill = BENCH_CAPACITY - 2 - len(bench_rest)
    assert fill >= 1, '锁前提:线成员过多(席面装不下)'
    s = _session(comp, plane_lengths=[9, 5, 7], line_state=False)
    st = CwWorkFrame(gold=100, level=4, plane=1, round_num=_ROUND,
                   node_type='reward', hp=100)
    st.deployed = st_deployed
    bench = [_bc(w, star=1, slot=1)]
    bench += bench_rest
    bench += [_bc(next(pool), star=2, slot=1) for _ in range(fill)]
    bench.append(extra_bench_last)
    assert len(bench) == BENCH_CAPACITY   # 席满 = bench_free 0 的承载前提
    st.bench = bench
    st.shop = []
    return st, s, w


class TestP92AssemblyBehaviorDiff:

    def test_t3_active_full_bench_refresh_proceeds(self):
        """行为差锁(集成):唯一可腾件 = T3 活跃垫保件 ⇒ 席可落收窄
        判定 True ⇒ ②(囤腿)通道可达 ⇒ 刷新放行、拦键恒零。旧代理
        同帧 = 投影读 0 ⇒ 全通道死 ⇒ 误拦(修复前行为,变异回装应红)。"""
        comp = pair_target_comp(_COMP_PAIR)
        k = tuple(line_members(comp))
        s = _session(comp, plane_lengths=[9, 5, 7], line_state=False)
        t3 = _t3_name(s, k)
        assert sell_gate.register_launch(
            s, t3, cause='stall_protect', round_num=_ROUND)
        st, _s2, _w = _p92_frame(_bc(t3, star=1, slot=1))
        _t3_premise(s, st, k, t3)
        acts = _decide(st, s)
        assert [a for a in acts if isinstance(a, RefreshShop)], acts
        cnt = state_of(s).cw4_counters
        assert cnt.get('p92_no_buy_refresh_blocked', 0) == 0

    def test_placeholder_full_bench_refresh_blocked(self):
        """对照锁:同构帧唯一「可腾件」为占位件 ⇒ 两视图同空 ⇒ 席不可落
        ⇒ 全通道死 ⇒ 拦刷 + 分键开火(收窄不复活 T-18 占位件高估灶面;
        旧代理与收窄判定在该帧同判,零行为差)。"""
        st, s, _w = _p92_frame(_item(slot=BENCH_CAPACITY))
        acts = _decide(st, s)
        assert not [a for a in acts if isinstance(a, RefreshShop)], acts
        cnt = state_of(s).cw4_counters
        assert cnt.get('p92_no_buy_refresh_blocked', 0) >= 1
