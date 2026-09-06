"""出口③发射位锁(17 号稿 §2.3/§7.3-§7.5;Φ_stall 过渡件垫件出口)。

覆盖:Φ_stall 全形态发射(授权条件四支+垫件在售+bench_free+净成本界+
围栏预检)、各分键拒因(fuel_not_on_sale/bench_full/below_reserve/
fenced/precheck_unavailable)、垫件买入→部署 held 闭环端到端(发射位
登记 state_of(session).cw4_fuel_filler_stall_buys → 执行侧
record_fuel_filler_held_postbuy 计数)。
"""
from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS, get_char
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
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

_COMP = '列车同行'


def _ns_with_state(**state_fields) -> SimpleNamespace:
    """桩 session:策略器字段经 state_of 载体设置(session 职责分离迁移后
    生产唯一读面;对 SimpleNamespace 桩同样生效)。"""
    s = SimpleNamespace()
    st = state_of(s)
    for k, v in state_fields.items():
        setattr(st, k, v)
    return s


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _card(name: str, cost: int = 2, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _off_line_name(exclude: tuple[str, ...] = (),
                   min_cost: int = 1) -> str:
    """垫件名:与列车同行线零重叠的注册表角色。"""
    km = set(line_members(get_comp(_COMP)))
    for n, ch in CHARACTERS.items():
        if n in km or n in exclude or (ch.cost or 0) < min_cost:
            continue
        return n
    raise AssertionError('注册表缺少线外角色(锁前提失效)')


def _causal_name() -> str:
    """不可追支成员:瓦尔特(5 费,level≤6 表概率 0,锁前提)。"""
    return '瓦尔特'


def _stall_frame(gold: int, fuel_pieces: int = 0, extra_bench=(),
                 deployed=None, cards=None, fuel_min_cost: int = 1,
                 chaseable_starred: bool = True, refresh_probs='default',
                 locked: bool = True):
    """Φ_stall 帧:锁线(列车同行)∧ 2★ 成件占满可追成员(合格集空)∧
    瓦尔特 cnt2=0(不可追成因)∧ bench 燃料件垫起可变现线。
    chaseable_starred=False ⇒ 可追成员不留 2★(A 支可追支成立 → fail 向);
    refresh_probs 传 None/dict 覆盖对账源(缺省 = {瓦尔特费档: 0});
    locked=False = 未锁线帧(D 支 fail 向;伪 comp 仍在场——伪 comp 在场
    ≠ 锁线,D 支门的阻断形态)。"""
    comp = get_comp(_COMP)
    km = list(line_members(comp))
    chaseable = [m for m in km if m != _causal_name()]
    if deployed is None:
        starred = chaseable if chaseable_starred else []
        deployed = [_bc(m, star=2, slot=i + 1)
                    for i, m in enumerate(starred)]
        deployed.extend(_bc(m, star=1, slot=len(starred) + j + 1)
                        for j, m in enumerate(chaseable)
                        if m not in starred)
    bench = [_bc(_off_line_name(exclude=tuple(km),
                                min_cost=fuel_min_cost), slot=i + 1)
             for i in range(fuel_pieces)]
    bench.extend(extra_bench)
    st = GameState(gold=gold, level=5, round_num=2, hp=60)
    st.level_readable = True
    st.plane = 2
    st.shop = list(cards) if cards is not None else []
    st.bench = bench
    st.deployed = deployed
    st.refresh_probs = ({(get_char(_causal_name()).cost or 5): 0}
                        if refresh_probs == 'default' else refresh_probs)
    sess = _ns_with_state(
        cw4_counters={},
        target_comp=comp,
        v3_intention=SimpleNamespace(locked_comp=(_COMP if locked else '')))
    return st, sess


def _decide(st, sess):
    return shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))


class TestExit3Emission:
    """正向形态锁:Φ_stall 四支全真 → 垫件买入 + 登记闭环。"""

    def test_phistall_frame_buys_fuel_filler(self):
        """全形态发射锁:Φ_stall 四支 ∧ 垫件在售 ∧ bench 空位 ∧ 净成本
        ≤1 金界 ∧ 预检放行 ⇒ BuyCard('fuel_filler_stall') + 买入登记。"""
        filler = _off_line_name()
        pad = _off_line_name(exclude=(filler,))
        # bench 一件 5 费燃料件压低 s_reserve(=g*−5=45),gold=46 落
        # (s_reserve, g*] 区间(B 支成立且 M6 金闸关闭,排除 m6_stockpile
        # 抢发射);垫件 cost=1 ⇒ gold−cost=45 ≥ s_reserve(净成本 ≤1 金界)
        st, sess = _stall_frame(gold=46, fuel_pieces=1, fuel_min_cost=5,
                                cards=[_card(pad, cost=1)])
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'fuel_filler_stall'
        assert state_of(sess).cw4_counters.get('fuel_filler_stall_buy') == 1
        assert pad in state_of(sess).cw4_fuel_filler_stall_buys

    def test_fuel_not_on_sale(self):
        """Φ_stall 成立而店内无垫件(仅线内卡)⇒ fuel_not_on_sale 分键。"""
        km = list(line_members(get_comp(_COMP)))
        st, sess = _stall_frame(gold=55, cards=[_card(km[0], cost=1)])
        _decide(st, sess)
        assert state_of(sess).cw4_counters.get('fuel_not_on_sale') == 1

    def test_below_reserve_rejects(self):
        """金位 fail 向:gold − cost < s_reserve ⇒ below_reserve 分键,
        不发射。"""
        pad = _off_line_name(min_cost=3)
        st, sess = _stall_frame(gold=46, fuel_pieces=1, fuel_min_cost=5,
                                cards=[_card(pad, cost=3)])
        _decide(st, sess)
        assert state_of(sess).cw4_counters.get('below_reserve') == 1

    def test_fenced_reject_key(self, monkeypatch):
        """预检围栏拒(kernel 单一源返回拒因)⇒ fuel_filler_stall_fenced
        分键,不发射。"""
        monkeypatch.setattr(shop, 'can_deploy_single',
                            lambda *a, **kw: (False, 'scatter_fence'))
        filler = _off_line_name()
        pad = _off_line_name(exclude=(filler,))
        st, sess = _stall_frame(gold=46, fuel_pieces=1, fuel_min_cost=5,
                                cards=[_card(pad, cost=1)])
        _decide(st, sess)
        assert state_of(sess).cw4_counters.get('fuel_filler_stall_fenced') == 1
        assert not state_of(sess).cw4_fuel_filler_stall_buys

    def test_precheck_unavailable_key(self, monkeypatch):
        """查询不可得(与围栏拒分键,禁混)⇒ precheck_unavailable
        分键,不发射。"""
        def _boom(*a, **kw):
            raise RuntimeError('快照缺失')
        monkeypatch.setattr(shop, 'can_deploy_single', _boom)
        filler = _off_line_name()
        pad = _off_line_name(exclude=(filler,))
        st, sess = _stall_frame(gold=46, fuel_pieces=1, fuel_min_cost=5,
                                cards=[_card(pad, cost=1)])
        _decide(st, sess)
        assert state_of(sess).cw4_counters.get(
            'fuel_filler_stall_precheck_unavailable') == 1
        assert not state_of(sess).cw4_fuel_filler_stall_buys

    def test_bench_full_key(self):
        """Φ_stall ∧ 垫件在售 ∧ bench 满(采购集件占位)⇒ bench_full 分键。

        帧构造:全部 bench 槽用锁定采购集成员占位(fuel_sell_candidates
        排除 buy_members ⇒ M4 腾席候选空,免抢跑);M3 经血线硬地板
        破息停付(hp 授权在册,出口③谓词零 hp 消费不冲突)压掉 arm0
        升级抢先。"""
        from sr_od.application.currency_war.kernel import cw_intention
        km = list(line_members(get_comp(_COMP)))
        ist = SimpleNamespace(locked_comp=_COMP)
        purchase = sorted(cw_intention.locked_buy_membership(ist))
        chaseable = [m for m in km if m != _causal_name()]
        deployed = [_bc(m, star=2, slot=i + 1)
                    for i, m in enumerate(chaseable)]
        pool = [n for n in purchase if n not in chaseable
                and n != _causal_name()]
        bench = [_bc(_causal_name(), slot=1)]
        bench.extend(_bc(pool[i % len(pool)], slot=len(bench) + 1)
                     for i in range(BENCH_CAPACITY - len(bench)))
        filler = _off_line_name(exclude=tuple(km))
        pad = _off_line_name(exclude=(filler,))
        st = GameState(gold=51, level=5, round_num=2, hp=10)
        st.level_readable = True
        st.plane = 1   # 血线硬地板域(plane 1 专属)
        st.hp_decision_trusted = True
        st.shop = [_card(pad, cost=1)]
        st.bench = bench
        st.deployed = deployed
        st.refresh_probs = {(get_char(_causal_name()).cost or 5): 0}
        sess = _ns_with_state(cw4_counters={}, target_comp=get_comp(_COMP),
                              v3_intention=ist)
        _decide(st, sess)
        assert state_of(sess).cw4_counters.get('bench_full') == 1

    def test_bench_to_held_closed_loop(self):
        """端到端:发射位买入登记 → 执行侧 held 现读重建 → held_postbuy
        计数(同 session 传递,消费 N3 消费口)。"""
        from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
            record_fuel_filler_held_postbuy,
        )
        filler = _off_line_name()
        pad = _off_line_name(exclude=(filler,))
        st, sess = _stall_frame(gold=46, fuel_pieces=1, fuel_min_cost=5,
                                cards=[_card(pad, cost=1)])
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'fuel_filler_stall'
        # 部署帧:垫件被围栏 held(kernel 单一源拒因)→ 执行侧闭环计数
        n = record_fuel_filler_held_postbuy(sess, [(pad, 'scatter_fence')])
        assert n == 1
        assert state_of(sess).cw4_counters.get('fuel_filler_stall_held_postbuy') == 1


class TestExit3NegativeBranches:
    """负向形态锁:任一支不成立 ⇒ 零发射零分键。
    正向形态锁 = test_phistall_frame_buys_fuel_filler(在库回执)。"""

    _PAD_KW = {"gold": 46, "fuel_pieces": 1, "fuel_min_cost": 5}

    def _no_emission(self, st, sess):
        act = _decide(st, sess)
        is_ff = isinstance(act, BuyCard) and act.reason == 'fuel_filler_stall'
        assert not is_ff
        assert 'fuel_filler_stall_buy' not in state_of(sess).cw4_counters
        assert not state_of(sess).cw4_fuel_filler_stall_buys

    def test_branch_A_chaseable_present_fails(self):
        """A 支可追支:可追成员无 2★ 成件(cnt2=0 ∧ 表概率>0)⇒ 合格集
        非空,非 Φ_stall,零发射。"""
        st, sess = _stall_frame(chaseable_starred=False, **self._PAD_KW)
        self._no_emission(st, sess)

    def test_branch_B_gold_not_above_reserve_silent(self):
        """B 支:g = s_reserve(等值不大于)⇒ fail 向静默(非病灶帧,
        不计 below_reserve——该键只辖「垫件在售后的金位拒」)。"""
        # bench 1×5 费燃料件 ⇒ s_reserve = g*−5 = 45;gold=45 等值
        st, sess = _stall_frame(gold=45, fuel_pieces=1, fuel_min_cost=5,
                                cards=[_card(_off_line_name(min_cost=1),
                                             cost=1)])
        self._no_emission(st, sess)
        assert 'below_reserve' not in state_of(sess).cw4_counters

    def test_branch_C_no_board_deficit_fails(self):
        """C 支:deployed == level(δ_board=0)⇒ 板深赤字不成立,零发射。"""
        km = list(line_members(get_comp(_COMP)))
        chaseable = [m for m in km if m != _causal_name()]
        deployed = [_bc(m, star=2, slot=i + 1)
                    for i, m in enumerate(chaseable)]
        deployed.extend([_bc(_causal_name(), star=1, slot=4),
                         _bc(_off_line_name(exclude=tuple(km)), star=1,
                             slot=5)])
        st, sess = _stall_frame(gold=46, fuel_pieces=0, fuel_min_cost=5,
                                deployed=deployed,
                                cards=[_card(_off_line_name(
                                    exclude=tuple(km)), cost=1)])
        self._no_emission(st, sess)

    def test_branch_D_unlocked_pseudo_comp_fails(self):
        """D 支:未锁线但伪 comp 在场(locked_comp 空)⇒ fail-closed
        零发射——锁线布尔单一源 = _ist.locked_comp,target_comp 非 None
        不构成锁线(伪 comp 形态,flow.py 物化段实证)。"""
        st, sess = _stall_frame(locked=False, **self._PAD_KW)
        self._no_emission(st, sess)


class TestExit3ProbBarSemantics:
    """A 支概率缺键/零值语义统一(单一源 =
    cw_economy.effective_refresh_prob,与 roll 可负担性门同消费语义):
    parse_prob_bar 契约 = 全 5 键或 None——None = 不可得 fail 向;
    结构内缺键 = 表值回退(因果支表值 0 ⇒ 回退即确证零,照常发射);
    键在且 ≤0 = 轮岗只翻倍不归零,采样不可信回退表值(机制出处 =
    注册表 cw_invest_data.py PlazaPortal 114「轮岗」);键在且 >0 但与
    表值冲突 = 对账不一致 fail 向。"""

    def test_missing_key_falls_back_to_table_zero(self):
        """缺键形态:对账源为空 dict(全缺)→ 表值回退(0)⇒ 照常发射
        (缺键 ≠ 条读非零,禁当对账不一致)。"""
        st, sess = _stall_frame(gold=46, fuel_pieces=1, fuel_min_cost=5,
                                cards=[_card(_off_line_name(), cost=1)],
                                refresh_probs={})
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'fuel_filler_stall'

    def test_prob_bar_none_fails_closed(self):
        """None = 概率条不可得 ⇒ fail 向不判 A,零发射。"""
        st, sess = _stall_frame(gold=46, fuel_pieces=1, fuel_min_cost=5,
                                cards=[_card(_off_line_name(), cost=1)],
                                refresh_probs=None)
        act = _decide(st, sess)
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'fuel_filler_stall')
        assert 'fuel_filler_stall_buy' not in state_of(sess).cw4_counters

    def test_bar_conflicting_with_table_fails(self):
        """对账不一致:表 0 而概率条 >0 ⇒ fail 向不判 A,零发射。"""
        st, sess = _stall_frame(gold=46, fuel_pieces=1, fuel_min_cost=5,
                                cards=[_card(_off_line_name(), cost=1)],
                                refresh_probs={5: 0.02})
        act = _decide(st, sess)
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'fuel_filler_stall')

    def test_bar_zero_on_positive_table_cost_stays_chaseable(self):
        """bar=0 ∧ 表值>0 形态:概率条 0 = 采样不可信回退表值 ⇒ 表值
        非零继续消费(与 cw_economy 同语义),合格集非空 → 非 Φ_stall,
        零发射。"""
        km = list(line_members(get_comp(_COMP)))
        chaseable3 = next(m for m in km if m != _causal_name()
                          and (get_char(m).cost or 0) == 3)
        # 该成员 1★ 留 bench(cnt2=0 可追),不进 2★ deployed
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in
                    enumerate(m for m in km
                              if m != _causal_name() and m != chaseable3)]
        st, sess = _stall_frame(gold=46, fuel_pieces=0, fuel_min_cost=5,
                                deployed=deployed,
                                cards=[_card(_off_line_name(
                                    exclude=tuple(km)), cost=1)],
                                refresh_probs={3: 0.0})
        act = _decide(st, sess)
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'fuel_filler_stall')


class TestExit3RecipeFloorExemptWiring:
    """豁免武装布尔接线锁(ADR-0564 候补批;出口③ can_deploy_single
    调用位):spy 按调用实参归因——武装帧(locked_comp='列车同行')
    预检实参必须携带 recipe_floor_lock_exempt 且与
    cw_intention.locked_line_recipe_floor_conflict(同一 _ist)同帧
    同值;去掉豁免参 = spy 缺键 = 红。

    辖域边界:武装帧垫件资格排除集 ≡ locked_buy_membership(⊃ 列车
    同行键全成员)⇒ 列车主籍垫件结构性缺席,豁免参当前不可达行为面
    ——本锁钉「帧属性同帧同值」接线契约;豁免 armed 的行为语义锁在
    kernel 侧(test_cw_recipe_floor_lock_exempt 家族穿参)。
    """

    def test_armed_frame_precheck_carries_frame_exemption(
            self, monkeypatch):
        from sr_od.application.currency_war.kernel.cw_intention import (
            locked_line_recipe_floor_conflict,
        )
        recorded: list[dict] = []
        real = shop.can_deploy_single

        def _spy(*a, **kw):
            recorded.append(kw)
            return real(*a, **kw)

        monkeypatch.setattr(shop, 'can_deploy_single', _spy)
        filler = _off_line_name()
        pad = _off_line_name(exclude=(filler,))
        st, sess = _stall_frame(gold=46, fuel_pieces=1, fuel_min_cost=5,
                                cards=[_card(pad, cost=1)])
        act = _decide(st, sess)
        # 接线不破坏既有发射语义(预检放行路径回归)
        assert isinstance(act, BuyCard) and act.reason == 'fuel_filler_stall'
        assert len(recorded) == 1, f'预检调用数漂移:{len(recorded)}'
        _ist = state_of(sess).v3_intention
        assert locked_line_recipe_floor_conflict(_ist) is True, \
            '锁前提失效:本帧应为武装帧'
        assert recorded[0].get('recipe_floor_lock_exempt') is True, (
            f'豁免实参缺失或非同帧武装值: {recorded[0]}')
