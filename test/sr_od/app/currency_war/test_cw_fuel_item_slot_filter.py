"""腾席资格面占位件滤除锁(T-18;旧账 T-294)。

出处:迭代详设「腾席资格面与代理收窄」T-18 节(定谳判据 =「箱不可卖 +
无金币现值面,在上游滤除」)+ 知识锚 docs/game/currency_war/research/
board_structure.md §备战栏「备战槽可被非角色物品占据」。占位件 = bench 上
``BenchChar.is_item_slot=True`` 的非角色占席物品(补给箱/星徽秘典/典籍
书册等;识别防线 = 部署装配点 assemble_bench_list 显式标记)。

缺陷(修复前):``mandate.fuel_sell_candidates`` 对空名占位件四门全放行
(排除集/星级/合成素材/零重叠 + bench_effect 注册表查无此名缺省可判),
占位件入燃料集 → 腾席通道对不可卖对象发射 SellBench——实机 = 白耗动作
(T-15 实机采证:同参数拖拽出售,角色 9 连全卖、箱零效果;宝箱面 4 选 1
装备面板,无金币现值、无出售项),假环境 = 幽灵登记源(T-216 对账点的
上游病灶)。本批 = 生产资格面上游滤除,锁两层:

- **资格面锁**:占位件恒不入 ``fuel_sell_candidates``(先于其余资格门,
  任何星级);真燃料件照卖 + 无占位件帧零漂移(滤门零误伤)。
- **发射位锁**(逐动作 sink 一致性):席满帧腾席臂面对「仅占位件可腾」
  诚实停摆(``bench_full`` 分键),不向卖出 sink 发射占位件动作——
  修复前该帧形态 = 对占位件 ``SellBench(expect='')`` 合法发射(T-209
  案发动作形)。
"""
from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS, get_char
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)

_COMP = '列车同行'
_K = ('线内件',)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _item(slot: int = 1, star: int = 1) -> BenchChar:
    """占位件(T-216 假环境同款形态):SIFT 不可读 → char_id=''、默认 1★。"""
    return BenchChar(slot=slot, char_id='', star=star, is_item_slot=True)


def _state(bench: list[BenchChar],
           deployed: list[BenchChar] | None = None) -> GameState:
    st = GameState()
    st.plane = 2
    st.hp = 50
    st.bench = list(bench)
    st.deployed = list(deployed or [])
    return st


# ===== 资格面锁:占位件恒不入燃料集 =====


class TestFuelItemSlotGate:
    """``fuel_sell_candidates`` 占位件物理门(先于其余资格门)。"""

    def test_placeholder_excluded_real_fuel_kept(self):
        """占位件不入清单,同帧真燃料件照卖(修复前形态 = [1, 2] 双入)。"""
        bench = [_item(slot=1), _bc('燃料A', slot=2)]
        cands = mandate.fuel_sell_candidates(bench, _K, state=_state(bench))
        assert [b.slot for b in cands] == [2]

    def test_placeholder_only_bench_empty_candidates(self):
        """仅占位件可「腾」的帧 = 诚实空集(消费位走无候选停摆路径)。"""
        bench = [_item(slot=1)]
        assert mandate.fuel_sell_candidates(
            bench, (), state=_state(bench)) == []

    def test_gate_precedes_star_gate(self):
        """门序锁:占位件判读先于星级门——物品语义与星级无关(任何星级
        不可变现);star=2 占位件非真实帧形,钉的是门序而非游戏形态。"""
        bench = [_item(slot=1, star=2)]
        assert mandate.fuel_sell_candidates(
            bench, (), state=_state(bench)) == []

    def test_order_preserved_with_placeholder_in_middle(self):
        """占位件夹层不改真件相对序(slot 升序确定性保持)。"""
        bench = [_bc('燃料A', slot=1), _item(slot=2), _bc('燃料B', slot=3)]
        cands = mandate.fuel_sell_candidates(bench, (), state=_state(bench))
        assert [b.slot for b in cands] == [1, 3]

    def test_control_zero_drift_without_placeholder(self):
        """零误伤对照:无占位件帧输出与旧语义逐位一致(两件全入,序不变)。"""
        bench = [_bc('燃料A', slot=1), _bc('燃料B', slot=2)]
        cands = mandate.fuel_sell_candidates(bench, _K, state=_state(bench))
        assert [b.slot for b in cands] == [1, 2]

    def test_other_gates_intact(self):
        """其余资格门未被稀释:线内件仍被 zero_overlap 拒(zero-drift 面)。"""
        bench = [_bc('线内件', slot=1)]
        assert mandate.fuel_sell_candidates(
            bench, _K, state=_state(bench)) == []


# ===== 发射位锁:逐动作 sink 不收占位件 =====


def _ns_with_state(**state_fields) -> SimpleNamespace:
    """桩 session(策略器字段经 state_of 载体设置,exit3 锁同款)。"""
    s = SimpleNamespace()
    st = state_of(s)
    for k, v in state_fields.items():
        setattr(st, k, v)
    return s


def _card(name: str, cost: int = 2, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _causal() -> str:
    """不可追支成员:瓦尔特(5 费,level≤6 表概率 0;exit3 bench_full 帧
    同款前提)。"""
    return '瓦尔特'


def _off_line(exclude: tuple[str, ...] = ()) -> str:
    """线外垫件名(与列车同行零重叠的注册表角色)。"""
    km = set(line_members(get_comp(_COMP)))
    for n in CHARACTERS:
        if n in km or n in exclude:
            continue
        return n
    raise AssertionError('注册表缺少线外角色(锁前提失效)')


class TestSinkConsistencyBenchFull:
    """席满帧腾席臂 sink 一致性(M2 stockpile 腾席位,shop.py M4 段)。

    帧形 = exit3 ``test_bench_full_key`` 同基座(锁线列车同行 + 席满 +
    垫件在售),末槽换占位件:修复前腾席 victim = 占位件 →
    ``SellBench(expect='')`` 发射(案发动作形),``bench_full`` 分键不可达;
    修复后 = 诚实停摆分键。
    """

    def test_bench_full_stop_not_placeholder_sell(self):
        from sr_od.application.currency_war.kernel import cw_intention
        km = list(line_members(get_comp(_COMP)))
        ist = SimpleNamespace(locked_comp=_COMP)
        _cap = cw_intention.locked_buy_cap_hold(
            GameState(gold=0, level=5, round_num=2, hp=60))
        purchase = sorted(cw_intention.locked_buy_membership(
            ist, cap_hold=_cap) or frozenset())
        chaseable = [m for m in km if m != _causal()]
        deployed = [_bc(m, star=2, slot=i + 1)
                    for i, m in enumerate(chaseable)]
        pool = [n for n in purchase
                if n not in chaseable and n != _causal()]
        assert pool, '锁前提:锁定采购集无 Bench 可占成员'
        bench = [_bc(_causal(), slot=1)]
        bench.extend(_bc(pool[i % len(pool)], slot=len(bench) + 1)
                     for i in range(BENCH_CAPACITY - len(bench)))
        # 末槽换占位件(腾席资格面唯一非排除成员)
        bench[-1] = _item(slot=bench[-1].slot)
        filler = _off_line(exclude=tuple(km))
        pad = _off_line(exclude=(filler,))
        st = GameState(gold=51, level=5, round_num=2, hp=10)
        st.level_readable = True
        st.plane = 1   # 血线硬地板域(plane 1 专属;压掉 arm0 升级抢先)
        st.hp_decision_trusted = True
        st.shop = [_card(pad, cost=1)]
        st.bench = bench
        st.deployed = deployed
        st.refresh_probs = {(get_char(_causal()).cost or 5): 0}
        sess = _ns_with_state(cw4_counters={}, target_comp=get_comp(_COMP),
                              v3_intention=ist)
        act = shop.decide_shop_action(st, sess,
                                      SimpleNamespace(ev_arm='full'))
        assert state_of(sess).cw4_counters.get('bench_full') == 1
        assert not isinstance(act, SellBench), (
            '卖出 sink 收到占位件动作(资格面滤除失效,T-18 回潮)')
