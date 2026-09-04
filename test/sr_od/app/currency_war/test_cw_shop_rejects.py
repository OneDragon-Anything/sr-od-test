"""商店波未买牌拒因串批(shop_rejects 遥测 + g_20260904_031925 形态重放锁)。

出处:第 5 局复盘 g_20260904_031925「锁线期拒买在售核心件」候选定谳批。
定谳结论:在售牌是花火(2费盛会之星,transition_chars 打工件)而非线内
核心件火花(4费星间旅人,绯英欢愉 shared 成员)——花火≠火花,归属正确
不买正确;但当时决策帧无任何 per-card 分类/拒因串,复盘只能猜「哪道门
拒了」,故补 shop_unbought_reasons 拒因遥测(生产端=cw4/shop)。

锁的语义(设计出处=本批 REPORT + predicates.line_members 单一源):
1. 在售线内缺口件 + 金充足 ⇒ M2 义务必买(义务通道回归锁);
2. 在售 transition 件(花火形态)⇒ 不买 + 拒因 'transition_char'
   (归属语义锁,g_20260904_031925 p2r2/p2r4 重放形态);
3. 线内缺口件未买的门序可辨:金不足/席满/异常态三分键。
"""
from __future__ import annotations

from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import predicates
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)

_COMP = get_comp('绯英欢愉')


class _Cfg:
    """决策 config 桩(ev_arm 字段=消费位读法)。"""

    def __init__(self, ev_arm: str = 'full') -> None:
        self.ev_arm = ev_arm


def _session() -> StrategySession:
    s = StrategySession()
    s.cw4_counters = {}
    s.target_comp = _COMP
    return s


def _state(gold: int, shop_cards: list[ShopCard], bench: list | None = None,
           deployed: list | None = None, level: int = 6) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2, node_type='普通战斗')
    st.plane = 2
    st.shop = shop_cards
    st.bench = bench if bench is not None else []
    st.deployed = deployed if deployed is not None else []
    return st


def _card(name: str, cost: int, x: int = 100) -> ShopCard:
    return ShopCard(x=x, name=name, cost=cost, star=1)


def _dep(name: str, slot: int = 1) -> BenchChar:
    # deployed 域复用 BenchChar(cw_state 槽位语义,无独立 DeployedChar 类)
    return BenchChar(slot=slot, char_id=name, star=1)


def _decide(st: GameState, session: StrategySession) -> list:
    from sr_od.application.currency_war.sim.engine_p1 import (
        sim_decision_registry,
    )
    strat = MandateV1Strategy(registry=sim_decision_registry())
    session.shop_state_frame = st
    return strat.decide_shop_screen(session, _Cfg())


def test_line_member_on_sale_gold_ample_must_buy():
    """火花形态重放锁①:线内缺口件在售+金充足 ⇒ M2 义务必买。

    g_20260904_031925 反事实形态:p2r2 若在售的是火花(而非花火),
    金 114 必须成交——义务不走息律门(shop.py M2 段 [41] 语义)。
    """
    st = _state(114, [_card('火花', 4)], deployed=[_dep('绯英')])
    sess = _session()
    acts = _decide(st, sess)
    buys = [a for a in acts if isinstance(a, BuyCard)
            and a.card.name == '火花']
    assert len(buys) == 1
    assert buys[0].reason == 'm2_line_member'
    # 已买件不进拒因串(拒因串只收未买牌)
    assert '火花' not in (sess.cw4_shop_rejects or {})


def test_transition_char_rejected_with_reason_g20260904_replay():
    """花火形态重放锁(=g_20260904_031925 p2r2 实录形态):

    在售=花火(transition 打工件)+金 114+线缺口在线 ⇒ 不买,
    拒因串带 'transition_char'——「未买」在决策帧内可辨归属,
    判读者不再需要猜。同波线外件(银枝)归 'non_line'。
    """
    assert '花火' in (_COMP.transition_chars or [])
    assert '火花' in predicates.line_members(_COMP)
    assert '花火' not in predicates.line_members(_COMP)
    st = _state(114, [_card('花火', 2), _card('银枝', 2)],
                deployed=[_dep('绯英')])
    sess = _session()
    acts = _decide(st, sess)
    assert not [a for a in acts if isinstance(a, BuyCard)
                and a.card.name == '花火']
    rej = sess.cw4_shop_rejects or {}
    assert rej.get('花火') == 'transition_char'
    assert rej.get('银枝') == 'non_line'


def test_missing_unaffordable_reason():
    """门序分键:线内缺口件在售但金不足 ⇒ 'missing_unaffordable'。"""
    st = _state(2, [_card('火花', 4)], deployed=[_dep('绯英')])
    sess = _session()
    _decide(st, sess)
    assert (sess.cw4_shop_rejects or {}).get('火花') == 'missing_unaffordable'


def test_missing_bench_full_reason():
    """门序分键:席满且无可腾燃料件(bench 全线内)⇒ 'missing_bench_full'。"""
    bench = [BenchChar(slot=i + 1, char_id='绯英', star=1)
             for i in range(BENCH_CAPACITY)]
    st = _state(114, [_card('火花', 4)], bench=bench,
                deployed=[_dep('绯英')])
    sess = _session()
    _decide(st, sess)
    assert (sess.cw4_shop_rejects or {}).get('火花') == 'missing_bench_full'


def test_owned_member_not_missing():
    """线内已持有件在售(合成原料再遇)⇒ 'owned',非缺口拒。"""
    st = _state(114, [_card('绯英', 2)], deployed=[_dep('绯英')])
    sess = _session()
    _decide(st, sess)
    assert (sess.cw4_shop_rejects or {}).get('绯英') == 'owned'


def test_pure_function_matches_session_output():
    """生产端函数与 decide 落盘口径一致(同一输入同一映射)。"""
    st = _state(114, [_card('花火', 2)], deployed=[_dep('绯英')])
    out = shop.shop_unbought_reasons(st, _COMP,
                                     predicates.line_members(_COMP), [])
    assert out == {'花火': 'transition_char'}


def test_schema_field_default_empty_dict():
    """schema 追加字段缺省空 dict:旧 decisions 行(无此键)读端兼容。"""
    from sr_od.application.currency_war.telemetry.schema import DecisionTrace
    assert DecisionTrace().shop_rejects == {}


# ===== sim 侧透传(sim 决策帧 → 账本行;实机 DecisionTrace.shop_rejects
# 同键同值枚举,生产端同源 cw4/shop.shop_unbought_reasons)=====

_REJECT_ENUM = frozenset({
    'missing_unaffordable', 'missing_bench_full', 'missing_no_path',
    'owned', 'merge_unaffordable', 'merge_bench_full',
    'transition_char', 'non_line',
})


def test_sim_ledger_rows_carry_shop_rejects():
    """sim 决策帧含拒因字段:每轮账本行带 shop_rejects dict。

    值枚举与实机同键;键 ⊆ 本轮最后在售波牌名(拒因串只收未买牌,
    已买件不进);逐波明细与 sim.shop_waves 对齐(每波带 rejects 键)。
    """
    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
    res = simulate_p1(42, pool='fallback', planes=2)
    non_empty = 0
    for row in res.ledger:
        rej = row.get('shop_rejects')
        assert isinstance(rej, dict)
        assert set(rej.values()) <= _REJECT_ENUM
        waves = (row.get('sim') or {}).get('shop_waves') or []
        assert waves, '每轮至少一条在售波'
        for w in waves:
            assert 'rejects' in w, '逐波明细缺档位(对齐破坏)'
            wr = w.get('rejects')
            if wr is None:
                continue   # None=本波无决策段(8 段上限截断等)
            assert set(wr.values()) <= _REJECT_ENUM
            assert set(wr.keys()) <= {
                c['name'] for c in w.get('cards') or []}
        # 顶层=末决策段 last-wins(段上限截断的尾波 rejects=None 不辖)
        decided = [w for w in waves if w.get('rejects') is not None]
        assert rej == (dict(decided[-1]['rejects']) if decided else {})
        non_empty += bool(rej)
    assert non_empty > 0, '整局全空 = 透传未生效或口径错'


def test_sim_shop_rejects_distinguishes_supply_vs_gate():
    """供给空缺 vs 闸门拒绝可辨:拒因串按牌分键——锁线行的线内成员键
    落 missing_*/owned 系(闸门/持有),线外件落 non_line(供给常态)。

    K 空窗行(target_comp 空 = 生产 k=None 分支)成员名如实归 non_line,
    不辖本断言(与实机 decide_shop_wave 同语义)。真引擎跑局,face-value
    断言,不锁分布数值。
    """
    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
        predicates,
    )
    seen_member_key = False
    for seed in (42, 43):
        res = simulate_p1(seed, pool='fallback', planes=2)
        for row in res.ledger:
            label = row.get('target_comp')
            if not label:
                continue
            members = set(predicates.line_members(get_comp(label)))
            for name, why in (row.get('shop_rejects') or {}).items():
                if name in members:
                    seen_member_key = True
                    assert why not in ('non_line', 'transition_char'), \
                        f'锁线行线内成员 {name} 拒因 {why} 越界(分类失效)'
    assert seen_member_key, '两局未见任何锁线行线内成员键 = 键分类覆盖存疑'


def test_sim_k_empty_window_comp_none_falls_back_non_line():
    """K 空窗(target_comp=None)时 comp=None 分支统一归 non_line
    (与生产端 None 语义同源;sim 引擎经 session 直读,同型)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
        shop_unbought_reasons,
    )
    st = _state(114, [_card('花火', 2)], deployed=[_dep('绯英')])
    out = shop_unbought_reasons(st, None, (), [])
    assert out == {'花火': 'non_line'}
