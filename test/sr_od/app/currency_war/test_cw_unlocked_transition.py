"""T5 未锁线止血买·结构判据锁(ADR-0556 §2/§5/§8)。

锁面(结构判据锁,发射位守卫移除即红):
- 开火:P1 假帧(loss_exact 现算 == 0,锚 g=47/Ī=5/R=13 ADR-0556 §4)
  ⇒ BuyCard('t3_unlocked_hemostat') + t3_available/t3_buy 分键;
- 熄火:P1 真帧(锚 g=23,L=1)⇒ t3_p1_true_blocked 显影,零发射;
- 熄火:预检拒(vacancy 不足/bench 满/fenced/precheck_unavailable)各分键;
- 出辖:锁线帧(locked_comp 非空)T5 零分键——锁线布尔单一源 =
  cw_intention.locked_buy_membership(未锁帧返回 None);
- 谓词单帧:t5_p1_false 现算(不按帧集清单,ADR-0556 §2 约定)。
不锁卡名(ADR-0556 §8):垫件名均取自注册表运行时解析。
"""
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_economy import loss_exact
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
    t5_p1_false,
)

_ROUNDS = 13          # 病灶窗 R_全局代表值(ADR-0556 §4;发射位经
                      # horizon.r_remaining 现算,测试侧统一桩为此值)
_G_OPEN = 47          # 开火锚:L(47,1,13,5)=0(实测;ADR-0556 §4)
_G_BLOCK = 23         # 熄火锚:L(23,1,13,5)=1(实测;ADR-0556 §4)
_COMP = '列车同行'


def _ns_with_state(**state_fields) -> SimpleNamespace:
    """桩 session:策略器字段经 state_of 载体设置(session 职责分离迁移后
    生产唯一读面;对 SimpleNamespace 桩同样生效)。"""
    s = SimpleNamespace()
    st = state_of(s)
    for k, v in state_fields.items():
        setattr(st, k, v)
    return s


def _fuel_name(exclude: tuple[str, ...] = (), min_cost: int = 5) -> str:
    """燃料件名:注册表线外角色(与列车同行零重叠;不锁具体卡名)。"""
    km = set(line_members(get_comp(_COMP)))
    for n, ch in CHARACTERS.items():
        if n in km or n in exclude or (ch.cost or 0) < min_cost:
            continue
        return n
    raise AssertionError('注册表缺少线外角色(锁前提失效)')


def _filler_name(exclude: tuple[str, ...] = ()) -> str:
    """cost-1 垫件名:T5 候选(cost-1 1★ 零重叠,注册表解析)。"""
    return _fuel_name(exclude=exclude, min_cost=1)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _card(name: str, cost: int = 1, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _frame(gold: int, *, fuel_pieces: int = 1, fuel_cost: int = 5,
           fuel_exclude: tuple[str, ...] = (),
           deployed=(), bench_extra=(), cards=None, locked: bool = False,
           target_comp: bool = True, level: int = 3, plane: int = 1,
           round_num: int = 2):
    """未锁线 T5 域帧:target_comp 恒置伪 comp(flow.py 物化段——伪 comp
    在场 ≠ 锁线;K 空窗回退不触发,ist 缺帧属性不进读);bench 无线内件
    ⇒ 可部署 bench 件数恒 0;fuel_pieces × cost 档 1★ 燃料件垫低
    s_reserve(=g*−Σ退金)使金位门在开火锚可满足;locked=True 置
    locked_comp(出辖对照帧)。"""
    bench = [_bc(_fuel_name(min_cost=fuel_cost, exclude=fuel_exclude),
                 slot=i + 1)
             for i in range(fuel_pieces)]
    bench.extend(bench_extra)
    st = GameState(gold=gold, level=level, round_num=round_num, hp=60)
    st.level_readable = True
    st.plane = plane
    st.shop = list(cards) if cards is not None else []
    st.bench = bench
    st.deployed = list(deployed)
    sess = _ns_with_state(
        cw4_counters={},
        target_comp=(get_comp(_COMP) if target_comp else None),
        v3_intention=SimpleNamespace(
            locked_comp=(_COMP if locked else '')))
    return st, sess


@pytest.fixture(autouse=True)
def _pin_rounds(monkeypatch):
    """R_全局桩:horizon.r_remaining → 病灶窗代表值(单一源为生产
    schedule_of;本锁只辖判据结构,不辖日程真值)。"""
    monkeypatch.setattr(shop.horizon, 'r_remaining',
                        lambda *a, **kw: _ROUNDS)


def _decide(st, sess):
    return shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))


class TestT5StructurePredicate:
    """t5_p1_false 谓词单帧锁(现算口径,不按帧集清单)。"""

    def test_p1_false_open_anchor(self):
        """开火锚 g=47:L=0 ⇒ P1 假(ADR-0556 §4,实测自洽)。"""
        assert t5_p1_false(_G_OPEN, 1, _ROUNDS, 5, 5) is True

    def test_p1_true_block_anchor(self):
        """熄火锚 g=23:L=1 ⇒ P1 真(ADR-0556 §4,实测自洽)。"""
        assert t5_p1_false(_G_BLOCK, 1, _ROUNDS, 5, 5) is False

    def test_cap_zero_all_false_safe_direction(self):
        """cap=0(买断制)L≡0 ⇒ 全帧 P1 假,T5 全开方向安全(R3 S-2)。"""
        assert t5_p1_false(_G_BLOCK, 1, _ROUNDS, 5, 0) is True


class TestT5Emission:
    """开火形态锁:守卫移除(触发分支删除)即红——帧落 CloseShop/
    既有序,不再产出 t3 买动作。"""

    def test_p1_false_frame_buys_hemostat(self):
        """P1 假帧 ∧ cost-1 垫件在售 ∧ vacancy 余存 ∧ 金位过 s_reserve
        ⇒ 买 + t3_available/t3_buy 分键。"""
        filler = _filler_name()
        st, sess = _frame(_G_OPEN, cards=[_card(filler, cost=1)])
        act = _decide(st, sess)
        assert isinstance(act, BuyCard)
        assert act.reason == 't3_unlocked_hemostat'
        assert state_of(sess).cw4_counters.get('t3_available') == 1
        assert state_of(sess).cw4_counters.get('t3_buy') == 1
        # N3 闭环登记(出口③同款单一载体;登记守卫移除 = 名集缺,
        # 下一条部署侧 held 显影锁随之红)
        assert filler in state_of(sess).cw4_fuel_filler_stall_buys

    def test_held_postbuy_closed_loop(self):
        """部署侧 held 显影锁(阻-1 方案①:N3 登记 → 执行侧现读重建 →
        fuel_filler_stall_held_postbuy 计数;T5 held 并入 fuel_ 键口径,
        不设独立 t3_held_postbuy——发射位登记守卫移除 ⇒ 计数 0 本锁红)。"""
        from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
            record_fuel_filler_held_postbuy,
        )
        filler = _filler_name()
        st, sess = _frame(_G_OPEN, cards=[_card(filler, cost=1)])
        act = _decide(st, sess)
        assert isinstance(act, BuyCard)
        assert act.reason == 't3_unlocked_hemostat'
        n = record_fuel_filler_held_postbuy(sess, [(filler, 'scatter_fence')])
        assert n == 1
        assert state_of(sess).cw4_counters.get(
            'fuel_filler_stall_held_postbuy') == 1

    def test_p1_true_frame_blocked_visible(self):
        """熄火:P1 真帧(g=23)⇒ t3_p1_true_blocked 显影,零发射。"""
        filler = _filler_name()
        st, sess = _frame(_G_BLOCK, cards=[_card(filler, cost=1)])
        act = _decide(st, sess)
        assert state_of(sess).cw4_counters.get('t3_p1_true_blocked') == 1
        assert 't3_buy' not in state_of(sess).cw4_counters
        assert not (isinstance(act, BuyCard)
                    and act.reason == 't3_unlocked_hemostat')

    def test_p1_true_premise(self):
        """锁前提自检:熄火锚帧生产净收入(net_income(2,0)=5,streak_pre=0
        近似口径)下现算 L>0——若收入日程真值变动致前提失效,本测试红,
        须换锚重推。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.income import (
            net_income,
        )
        income_now = net_income(2, 0)
        assert loss_exact(_G_BLOCK, 1, _ROUNDS, income_now, 5) > 0
        assert loss_exact(_G_OPEN, 1, _ROUNDS, income_now, 5) == 0


class TestT5RejectionKeys:
    """熄火/拒因分键零静默锁(ADR-0556 §5:分键显影全)。"""

    def test_no_cost1_filler_keyed(self):
        """店无 cost-1 垫件(仅 2 费):T5 域不开,t3_no_candidate 归因
        显影(有意收窄,零静默),零发射。"""
        pad = _fuel_name(min_cost=2, exclude=(_filler_name(),))
        st, sess = _frame(_G_OPEN, cards=[_card(pad, cost=2)])
        _decide(st, sess)
        assert state_of(sess).cw4_counters.get('t3_no_candidate') == 1
        assert 't3_buy' not in state_of(sess).cw4_counters

    def test_bench_full_key(self):
        """bench 满 ⇒ t3_precheck_bench_full,零发射。

        帧构造:线内 4 成员全在册(2★ 上板 ×2 + 1★ 留 bench ×2 ⇒
        missing=∅,M4 腾席不抢跑),bench 余槽垫线外燃料件至满;
        level=6(cap 6,deployed 2 < cap ⇒ arm1 关;need=2+2=4 ≤ 6
        ⇒ arm0 关)。"""
        km = list(line_members(get_comp(_COMP)))
        filler = _filler_name(exclude=tuple(km))
        deployed = [_bc(km[0], star=2, slot=1), _bc(km[1], star=2, slot=2)]
        bench_extra = [_bc(km[2], star=1, slot=1),
                       _bc(km[3], star=1, slot=2)]
        bench_extra.extend(_bc(_fuel_name(min_cost=2,
                                          exclude=(filler,) + tuple(km)),
                               slot=len(bench_extra) + i + 1)
                           for i in range(BENCH_CAPACITY
                                          - len(bench_extra)))
        st, sess = _frame(_G_OPEN, fuel_pieces=0, bench_extra=bench_extra,
                          deployed=deployed, level=6,
                          cards=[_card(filler, cost=1)],
                          target_comp=True)
        act = _decide(st, sess)
        assert state_of(sess).cw4_counters.get('t3_precheck_bench_full') == 1
        assert 't3_buy' not in state_of(sess).cw4_counters
        assert not (isinstance(act, BuyCard)
                    and act.reason == 't3_unlocked_hemostat')

    def test_vacancy_not_beyond_deployable_bench(self):
        """vacancy ≤ 可部署 bench 件数 ⇒ 买后无空槽可落,t3_precheck_
        no_vacancy 分键(与 bench 满拆键,两因判读可辨)。

        帧构造:target_comp 在场(伪 comp 未锁,k_members 非空)——bench
        一件线内 1★ 未上板(可部署 1)、板面 2 件占 3 cap(空位 1):
        1 ≤ 1 ⇒ t3_precheck_no_vacancy。"""
        km = list(line_members(get_comp(_COMP)))
        filler = _filler_name(exclude=tuple(km))
        bench_line = _bc(km[0], star=1, slot=1)
        deployed = [_bc(km[1], star=2, slot=1), _bc(km[2], star=2, slot=2)]
        st, sess = _frame(_G_OPEN, fuel_pieces=0, bench_extra=[bench_line],
                          deployed=deployed,
                          cards=[_card(filler, cost=1)],
                          target_comp=True)
        act = _decide(st, sess)
        assert state_of(sess).cw4_counters.get('t3_precheck_no_vacancy') == 1
        assert state_of(sess).cw4_counters.get('t3_precheck_bench_full') is None
        assert 't3_buy' not in state_of(sess).cw4_counters
        assert not (isinstance(act, BuyCard)
                    and act.reason == 't3_unlocked_hemostat')

    def test_below_reserve_key(self):
        """金−卡价 < s_reserve(无燃料件垫底,s_reserve=g*=50,g=46)
        ⇒ t3_below_reserve,零发射。"""
        filler = _filler_name()
        st, sess = _frame(46, fuel_pieces=0, cards=[_card(filler, cost=1)])
        act = _decide(st, sess)
        assert state_of(sess).cw4_counters.get('t3_below_reserve') == 1
        assert 't3_buy' not in state_of(sess).cw4_counters
        assert not (isinstance(act, BuyCard)
                    and act.reason == 't3_unlocked_hemostat')

    def test_fenced_key_with_reason_suffix(self, monkeypatch):
        """围栏拒(kernel 单一源)⇒ t3_fenced + 拒因动态后缀,零发射。"""
        monkeypatch.setattr(shop, 'can_deploy_single',
                            lambda *a, **kw: (False, 'scatter_fence'))
        filler = _filler_name()
        st, sess = _frame(_G_OPEN, cards=[_card(filler, cost=1)])
        act = _decide(st, sess)
        assert state_of(sess).cw4_counters.get('t3_fenced') == 1
        assert state_of(sess).cw4_counters.get('t3_fenced_scatter_fence') == 1
        assert 't3_buy' not in state_of(sess).cw4_counters
        assert not (isinstance(act, BuyCard)
                    and act.reason == 't3_unlocked_hemostat')

    def test_precheck_unavailable_key(self, monkeypatch):
        """查询不可得(与围栏拒分键,禁混)⇒ t3_precheck_unavailable。"""
        def _boom(*a, **kw):
            raise RuntimeError('快照缺失')
        monkeypatch.setattr(shop, 'can_deploy_single', _boom)
        filler = _filler_name()
        st, sess = _frame(_G_OPEN, cards=[_card(filler, cost=1)])
        act = _decide(st, sess)
        assert state_of(sess).cw4_counters.get('t3_precheck_unavailable') == 1
        assert 't3_buy' not in state_of(sess).cw4_counters
        assert not (isinstance(act, BuyCard)
                    and act.reason == 't3_unlocked_hemostat')


class TestT5OutOfScope:
    """出辖锁:锁线帧 T5 零分键(锁线布尔单一源;锁线辖域归出口③)。"""

    def test_locked_frame_no_t3_keys(self):
        filler = _filler_name()
        st, sess = _frame(_G_OPEN, cards=[_card(filler, cost=1)],
                          locked=True)
        act = _decide(st, sess)
        assert not any(k.startswith('t3_') for k in state_of(sess).cw4_counters)
        assert not (isinstance(act, BuyCard)
                    and act.reason == 't3_unlocked_hemostat')


class TestT5RecipeFloorExemptWiring:
    """豁免武装布尔接线锁(ADR-0564 候补批;T5 can_deploy_single 调用位):
    帧属性同帧同值契约——预检实参必须携带 recipe_floor_lock_exempt 且
    与 cw_intention.locked_line_recipe_floor_conflict(同一 _ist)同值;
    去掉豁免参 = spy 缺键 = 红。

    辖域边界:武装帧 T5 结构性出辖(armed ⇒ locked_buy_membership 非空
    ⇒ T5 门关),故本锁在「未锁线开火帧」钉 helper(空 locked_comp)
    = False 同值、在「边缘双开帧」(ADR-0556 §3:locked_comp 脏名致
    采购集解析为空,T5 照常开火)钉 helper(不可解析)= False 同值;
    armed=True 的行为语义锁在 kernel 侧(test_cw_recipe_floor_lock_
    exempt 家族穿参)与出口③接线锁。
    """

    def _spy_can_deploy(self, monkeypatch) -> list[dict]:
        recorded: list[dict] = []
        real = shop.can_deploy_single

        def _spy(*a, **kw):
            recorded.append(kw)
            return real(*a, **kw)

        monkeypatch.setattr(shop, 'can_deploy_single', _spy)
        return recorded

    def test_unlocked_frame_carries_frame_value(self, monkeypatch):
        from sr_od.application.currency_war.kernel.cw_intention import (
            locked_line_recipe_floor_conflict,
        )
        recorded = self._spy_can_deploy(monkeypatch)
        filler = _filler_name()
        st, sess = _frame(_G_OPEN, cards=[_card(filler, cost=1)])
        act = _decide(st, sess)
        # 接线不破坏既有发射语义(预检放行路径回归)
        assert isinstance(act, BuyCard)
        assert act.reason == 't3_unlocked_hemostat'
        assert len(recorded) == 1, f'预检调用数漂移:{len(recorded)}'
        assert 'recipe_floor_lock_exempt' in recorded[0], \
            '豁免实参缺失(接线缺失形态)'
        assert locked_line_recipe_floor_conflict(
            state_of(sess).v3_intention) is False
        assert recorded[0]['recipe_floor_lock_exempt'] is False

    def test_dual_open_frame_carries_helper_value(self, monkeypatch):
        from sr_od.application.currency_war.kernel.cw_intention import (
            locked_line_recipe_floor_conflict,
        )
        recorded = self._spy_can_deploy(monkeypatch)
        filler = _filler_name()
        st, sess = _frame(_G_OPEN, cards=[_card(filler, cost=1)])
        # 边缘双开形态(ADR-0556 §3):locked_comp 非空而采购集解析为空
        # (get_comp 注册表缺项脏态)⇒ T5 照常开火;helper 对不可解析
        # 脏名 = False(fail-closed)
        state_of(sess).v3_intention = SimpleNamespace(
            locked_comp='未注册comp脏名')
        act = _decide(st, sess)
        assert isinstance(act, BuyCard)
        assert act.reason == 't3_unlocked_hemostat'
        assert len(recorded) == 1
        assert locked_line_recipe_floor_conflict(
            state_of(sess).v3_intention) is False
        assert recorded[0]['recipe_floor_lock_exempt'] is False
