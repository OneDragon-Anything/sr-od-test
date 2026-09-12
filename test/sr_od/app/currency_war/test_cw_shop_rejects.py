"""商店波未买牌拒因串批(shop_rejects 遥测 + g_20260904_031925 形态重放锁)。

出处:第 5 局复盘 g_20260904_031925「锁线期拒买在售核心件」候选定谳批。
定谳结论:在售牌是花火(2费盛会之星,transition_chars 打工件)而非线内
核心件火花(4费星间旅人,绯英欢愉 shared 成员)——花火≠火花,归属正确
不买正确;但当时决策帧无任何 per-card 分类/拒因串,复盘只能猜「哪道门
拒了」,故补 shop_unbought_reasons 拒因遥测(生产端=cw4/shop)。

锁的语义(设计出处=本批 REPORT + predicates.line_members 单一源):
1. 在售线内缺口件 + 金充足 ⇒ M2 义务必买(义务通道回归锁);
2. 在售 transition 件(花火形态)⇒ 不买 + 归属拒因可辨(T-115 D7
   键序后交集卡键 = 'transition_component',ADR-0580;纯 trans 件仍
   'transition_char');
3. 线内缺口件未买的门序可辨:金不足/席满/异常态三分键。
"""
from __future__ import annotations

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
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import predicates
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_feed,
    cw4_bs,
)

_COMP = get_comp('绯英欢愉')


class _Cfg:
    """决策 config 桩(ev_arm 字段=消费位读法)。"""

    def __init__(self, ev_arm: str = 'full') -> None:
        self.ev_arm = ev_arm


def _session() -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = _COMP
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
    cw4_feed(session, st)
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
    assert '火花' not in (state_of(sess).cw4_shop_rejects or {})


def test_transition_char_rejected_with_reason_g20260904_replay():
    """花火形态重放锁(=g_20260904_031925 p2r2 实录形态):

    在售=花火(transition 打工件)+金 114+线缺口在线 ⇒ 不买,
    拒因带归属键——「未买」在决策帧内可辨归属,判读者不再需要猜。
    同波线外件(银枝)归 'non_line'。T-115 D7 键序重推(ADR-0580):
    花火 ∈ ④放行集(TRANSITION_PACK carry)∧ _COMP.transition_chars
    (交集卡),键序 = ④放行集先于 trans 分支 ⇒ 键 = 'transition_
    component'(④件被拒才是要盯的信号;旧 'transition_char' 键对交集
    卡不可达,正是 D7 诊断的键序缺陷)。行为面不变:plane=2 已定型,
    ④放行收窄,花火仍不买。
    锁语义重推(泄金阶梯档 0,设计方案 §1.2):旧帧金 114 ∈ 必花域,
    摘旗后 dominance(1★ 全额退零重叠 = 花火属其候选类)会先买花火
    (零净成本可逆持有,[13] 停手线语义由候选集承载)——拒因分类
    锁改用域外帧(gold=40 < g*)钉:分类语义与金带无关,域外帧四臂
    全静,拒因串逐键可辨。
    """
    assert '花火' in (_COMP.transition_chars or [])
    assert '火花' in predicates.line_members(_COMP)
    assert '花火' not in predicates.line_members(_COMP)
    st = _state(40, [_card('花火', 2), _card('银枝', 2)],
                deployed=[_dep('绯英')])
    sess = _session()
    acts = _decide(st, sess)
    assert not [a for a in acts if isinstance(a, BuyCard)
                and a.card.name == '花火']
    rej = state_of(sess).cw4_shop_rejects or {}
    assert rej.get('花火') == 'transition_component'
    assert rej.get('银枝') == 'non_line'


def test_missing_unaffordable_reason():
    """门序分键:线内缺口件在售但金不足 ⇒ 'missing_unaffordable'。"""
    st = _state(2, [_card('火花', 4)], deployed=[_dep('绯英')])
    sess = _session()
    _decide(st, sess)
    assert (state_of(sess).cw4_shop_rejects or {}).get('火花') == 'missing_unaffordable'


def test_missing_bench_full_reason():
    """门序分键:席满且无可腾燃料件(bench 全线内)⇒ 'missing_bench_full'。"""
    bench = [BenchChar(slot=i + 1, char_id='绯英', star=1)
             for i in range(BENCH_CAPACITY)]
    st = _state(114, [_card('火花', 4)], bench=bench,
                deployed=[_dep('绯英')])
    sess = _session()
    _decide(st, sess)
    assert (state_of(sess).cw4_shop_rejects or {}).get('火花') == 'missing_bench_full'


def test_owned_member_not_missing():
    """线内已持有件在售(合成原料再遇)⇒ 锁重推导(14号稿 §3 臂①落码):
    cnt1=1 帧不再落 'owned' 拒——副本由 m2_stockpile 义务囤腿买入
    (§7.3:拒因 owned 命中占比大幅下降,验后趋零锚)。"""
    st = _state(114, [_card('绯英', 2)], deployed=[_dep('绯英')])
    sess = _session()
    acts = _decide(st, sess)
    assert any(isinstance(a, BuyCard) and a.reason == 'm2_stockpile'
               and a.card.name == '绯英' for a in acts)
    assert (state_of(sess).cw4_shop_rejects or {}).get('绯英') is None


def test_schema_old_row_read_path_default_empty_dict():
    """schema 追加字段读端契约:历史 decisions 行(无 shop_rejects 键)
    经回放读端 from_dict 反序列化不炸、缺省空 dict——消费链 =
    cw_replay_reader.from_dict(DecisionTrace, 行)(裸构造透传断言按
    纪律 18「构造透传」档升级为读路径契约锁:值改了,读端消费者坏)。"""
    from sr_od.application.currency_war.telemetry.cw_replay_reader import (
        DecisionTrace,
        from_dict,
    )
    trace = from_dict(DecisionTrace, {'run_id': 'r'})
    assert trace.shop_rejects == {}


# ===== sim 侧透传(sim 决策帧 → 账本行;实机 DecisionTrace.shop_rejects
# 同键同值枚举,生产端同源 cw4/shop.shop_unbought_reasons)=====

_REJECT_ENUM = frozenset({
    'missing_unaffordable', 'missing_bench_full', 'missing_no_path',
    'owned', 'merge_unaffordable', 'merge_bench_full', 'merge_ready',
    'stockpile_bench_full', 'stockpile_unaffordable', 'stockpile_ready',
    'transition_char', 'non_line',
    # C1 拒因拆键(ADR-0569):registry 核心卡在售未买帧,与真 non_line
    # 可辨(设计《直通核心卡信号层入口》§4 意向状态机行;设计稿 =
    # docs/develop/sr_od/application/currency_war/design/设计-C1直通核心入口.md)。
    'core_candidate_rejected',
    # T-115 规则④ 拒因键(ADR-0580,D7 键序 = ④放行集先于 trans):
    # ④放行件在售未买帧可辨(交集卡不再落 transition_char)。
    'transition_component',
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
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
    from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
        predicates,
    )
    seen_member_key = False
    # 种子固化(测试纪律 12 探底后取断言成立最小值):探针记录——
    # plain 配置逐种子扫面(40/44/46/50)线内成员键与臂①动作四种子
    # 全命中,固化 40 单种子;引擎改动位移 RNG 消费致种子失准时本测红,
    # 处理 = 重跑逐种子探针更新,不是机械跟绿。历史:种子集 ADR-0519
    # 重锚(锁线门槛收紧后 42/43 无锁线行,弃 42/43)。
    # 重推导(14号稿 §3 臂①落码):线内成员副本(cnt1=1)帧已由
    # m2_stockpile 义务囤腿买入,拒绝行内线内成员键大幅减少(§7.3
    # 「拒因 owned 命中占比大幅下降」的验收面)——本锁保留不变式断言
    # (凡出现线内成员键,必不落 non_line/transition_char),纯映射面由
    # K 空窗直调锁与 missing_unaffordable/missing_bench_full 两帧锁承载。
    # W6 波 4 种子重锚:黑板容器化后引擎 RNG 消费序列位移,40 失准;
    # 44 为重跑探针首命中(不变式断言在线,非机械跟绿)。
    for seed in (44,):
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
    # 覆盖前提(落地审低-3):键分类不变式须有真实命中面,防空转恒真假绿;
    # 种子 40 探针实测成员键命中,零命中 = 引擎位移致种子失准,重跑探针。
    assert seen_member_key, \
        '种子局无线内成员拒因键 = 键分类覆盖失效(重跑逐种子探针更新种子)'


def test_sim_k_empty_window_comp_none_falls_back_non_line():
    """K 空窗(target_comp=None)时 comp 相关分支不可得:comp 派生的
    transition 分类不可得,真无关件统一归 non_line(与生产端 None 语义
    同源;sim 引擎经 session 直读,同型)。T-115 D7 键序(ADR-0580):
    ④放行集 = 身份分层单一源,knowledge 表对表、与 comp 无关——花火
    在 comp=None 帧仍可辨 'transition_component'(Early 空窗带正是 ④
    活跃域,判读价值即在此)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
        shop_unbought_reasons,
    )
    st = _state(114, [_card('花火', 2), _card('银枝', 2)],
                deployed=[_dep('绯英')])
    # 容器喂入(W6 波 4:shop_unbought_reasons 切容器签名;cw4_bs 助手)
    out = shop_unbought_reasons(cw4_bs(st, _session()), None, (), [])
    assert out == {'花火': 'transition_component', '银枝': 'non_line'}


def test_sim_locked_frame_canonical_members_not_non_line():
    """锁定帧买侧口径与生产同源锁(模拟找问题批 findprob_20260909_083024
    问题②验收):实机 g_20260905_035710 同型事故在 sim 打标点的对齐。

    生产侧拒因遥测传正典 buy_members(锁定帧 = locked_buy_membership,
    单一源 = cw_intention.locked_buy_membership,其 docstring 记载该
    事故修法);sim 引擎打标调用点旧口径传 line_members(target_comp)
    (core∪shared 小集)且不传 hub_names——锁定帧阵营∪流派扩展成员
    (丹恒·饮月/开拓者·欢愉,列车同行阵营但非 comp core∪shared)被误
    标 non_line,污染 sim 复盘归因。修复 = 打标与同帧 obs 段同源消费
    正典口径。

    锁:锁定帧行(v3_intention.phase=='locked')的 shop_rejects 中,
    正典采购集成员拒因 ≠ 'non_line'(不变式,不锁分布数值);驱动 =
    P2 进场态锁线注入(真引擎决策段走打标块)。覆盖前提锚:锁定帧行与
    正典成员拒因键须真实命中,防空转假绿。
    """
    import random

    from sr_od.application.currency_war.kernel import cw_intention
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
    )
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
    from sr_od.application.currency_war.sim.engine_p2 import P2ReplayEntry
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        state_of,
    )

    def _locked_ist() -> IntentionState:
        ist = IntentionState()
        ist.phase = 'locked'
        ist.locked_comp = '列车同行'
        ist.lock_plane = 2
        return ist

    comp = get_comp('列车同行')
    membership = cw_intention.locked_buy_membership(_locked_ist())
    ext = sorted(membership - set(predicates.line_members(comp)))
    assert '丹恒·饮月' in ext and '开拓者·欢愉' in ext, \
        '锁测试前提:锁定采购集须含事故局点名的扩展成员'
    seen_locked_row = False
    seen_member_key = False
    # 种子固化(测试纪律 12):探针记录——逐种子扫面(40/44/46/50)
    # 锁定帧行四种子均在,正典采购集成员键 seed 40 不命中(该局零出现)、
    # 44/46/50 全命中,固化 44 单种子(断言成立最小值);引擎位移 RNG
    # 消费致失准的红 = 重跑探针更新种子,不是机械跟绿。
    for seed in (44,):
        sess = StrategySession(rng=random.Random(f'sim-p2-entry-{seed}'))
        state_of(sess).target_comp = comp
        state_of(sess).v3_intention = _locked_ist()
        state_of(sess).cw4_counters = {}
        entry = P2ReplayEntry(hp=60, gold=25, level=7,
                              locked_comp='列车同行')
        res = simulate_p1(seed, pool='fallback', planes=2, session=sess,
                          _p2_entry=entry)
        for row in res.ledger:
            if (row.get('v3_intention') or {}).get('phase') != 'locked':
                continue
            seen_locked_row = True
            for name, why in (row.get('shop_rejects') or {}).items():
                if name in membership:
                    seen_member_key = True
                    assert why != 'non_line', \
                        f'锁定帧行正典采购集成员 {name} 拒因 {why}:' \
                        f'sim 打标口径与生产分叉(扩展成员被误标 non_line)'
    assert seen_locked_row, '无锁定帧行 = 锁线注入失效,本锁空转'
    assert seen_member_key, \
        '正典采购集成员拒因键零命中 = 覆盖失效,不变式断言空转假绿'


def test_sim_reject_call_site_canonical_source_anchor():
    """sim 打标调用点源码锚(变异逃生口;先例形态 =
    test_cw_locked_buy_membership_split.test_shop_consumes_membership_
    not_scope_direct):打标行必须消费 obs 段正典 membership 变量
    (_obs_bm)并直传 hub_names——回退旧口径 line_members 直传、或
    删除 hub_names 直传的变异均被本锚抓红。"""
    from pathlib import Path

    from sr_od.application.currency_war.sim import engine_p1
    src = Path(engine_p1.__file__).read_text(encoding='utf-8')
    assert '_seg_bs_of(sess), _k_comp, _obs_bm, acts,\n                    hub_names=_seg_hub)' in src, \
        'sim 打标调用点须消费容器(obs 段正典 membership)并直传 hub_names'
