"""必花域落码锁(20 号稿 v2.1;用户裁定 =「无论什么 hp,金这么多都是
要花的」§1 授权文号)。

覆盖:G_must 判据单一源(§2.1,买断制出辖)/ L2 第二触发源(∨ 合并,
触发源分键)/ L3 升级(停付线域内让位 = ADR-0528,资格硬闸照常,
拒因分键 level_cap/batch_unaffordable)/ R1 域内残形切分线(g*/L 账
降期望核算,可负担性留资格硬闸,合格集空守卫照旧)。
负向锁(物理残量白名单形态,§3.2):等级 cap ⇒ level_cap 零消费;
域外帧零变化。「店空无垫件 ⇒ fuel_not_on_sale 零消费」由
test_cw_exit3_fuel_filler.test_fuel_not_on_sale 承载(域内同形帧,
等价断言已并)。

prep 段(2026-09-09 CUT2 合并批②,自 test_cw_l3_prep_must_spend_latch
整体并入,断言双留原样迁入——簇R 裁定 shop 侧/prep 侧分键不同,容器级
合并不裁任何断言):必花域备战期闩 + L3 资格拒分键 + xp 现读透传 +
b_t 实机回退源 + 实机遥测两件接线。病灶源 = g_20260906_021859 /
g_20260906_034515 两局濒死段门链回放定谳:「花光」义务在必花域边界上
蒸发(商店域首笔消费把金拉回域内后,同备战期 prep 帧域外被 P2 危机带
常态挂起,残金闲置入死战)+ L3 资格拒零分键不可辨 + prep 侧 xp 现读
被丢弃构成 spend_unified 假拒第二静默面。锁契约 = 结构/回显,不锁
分布数值(sr-od-test README 第 8 条)。
"""
from dataclasses import replace
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_economy import (
    in_must_spend_zone,
)
from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_prep_actions import LevelUp
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    CloseShop,
    GameState,
    LevelUpShop,
    RefreshShop,
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
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    ns_session as _ns_session,
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


def _zone_frame(gold: int, *, cards=None, level: int = 5,
                locked: bool = True) -> tuple[GameState, SimpleNamespace]:
    """必花域帧:锁线列车同行、level=level、gold 必入域(g > 50)。"""
    comp = get_comp(_COMP)
    km = list(line_members(comp))
    chaseable = [m for m in km if m != '瓦尔特']
    deployed = [_bc(m, star=2, slot=i + 1)
                for i, m in enumerate(chaseable)]
    st = GameState(gold=gold, level=level, round_num=2, hp=60)
    st.level_readable = True
    st.plane = 2
    st.node_type = 'battle'
    st.shop = list(cards) if cards is not None else []
    st.bench = []
    st.deployed = deployed
    st.refresh_probs = {5: 0}
    sess = _ns_with_state(
        cw4_counters={},
        target_comp=comp,
        v3_intention=SimpleNamespace(
            locked_comp=(_COMP if locked else '')))
    return st, sess


def _decide(st, sess):
    return shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))


class TestZonePredicate:

    def test_zone_predicate_bounds(self):
        """G_must = 10×cap_resolved:g 越线 True/等值 False;买断制
        (cap=0)出辖恒 False。注入通道 = session.active_strategies
        注册表名(ADR-0598 单一源迁移,原 cw4_cap_override 死通道退役)。"""
        sess = _ns_with_state()
        assert in_must_spend_zone(51, sess) is True
        assert in_must_spend_zone(50, sess) is False
        buyout = _ns_with_state()
        buyout.active_strategies = ['买断制']
        assert in_must_spend_zone(999, buyout) is False
        rich = _ns_with_state()
        rich.active_strategies = ['利息上调']
        assert in_must_spend_zone(101, rich) is True
        assert in_must_spend_zone(100, rich) is False


class TestL2SecondTrigger:

    def test_zone_triggers_l2_despite_chaseable(self, monkeypatch):
        """锁语义重推(泄金阶梯档 0,设计方案 §1.2 发射序申报):旧锁钉
        「域内 L2 第二触发 → 出口③ 买垫件」——摘旗后垫件类(1★ 零重叠
        全额退)同属 dominance 候选,支配性优先序先于带参臂,域内帧由
        dominance 先吃(同帧断言①);L2 触发语义本体不变,以 dominance
        猴补关的隔离帧钉住(断言②,构造声明见泄金阶梯锁文件头)。"""
        km = list(line_members(get_comp(_COMP)))
        pad = next(n for n, ch in __import__(
            'sr_od.application.currency_war.data.cw_chars',
            fromlist=['CHARACTERS']).CHARACTERS.items()
            if n not in km)
        st, sess = _zone_frame(
            gold=80, cards=[ShopCard(x=100, name=pad, cost=1, star=1)])
        act = _decide(st, sess)
        # ① 新序:dominance(档 0)先于带参臂吃同候选类
        assert isinstance(act, BuyCard) and act.reason == 'dominance_buy'
        # ② L2 触发语义本体(dominance+M6 隔离帧:两臂摘旗后同候选类
        # 先行,见①;本断言只辖出口③ L2 触发源语义)
        monkeypatch.setattr(mandate, 'dominance_buy_eligible',
                            lambda *a, **kw: False)
        monkeypatch.setattr(shop.crit_stockpile, 'stockpile_buy',
                            lambda *a, **kw: (False, 'not_in_tier'))
        st2, sess2 = _zone_frame(
            gold=80, cards=[ShopCard(x=100, name=pad, cost=1, star=1)])
        act2 = _decide(st2, sess2)
        assert isinstance(act2, BuyCard) and act2.reason == 'fuel_filler_stall'
        assert state_of(sess2).cw4_counters.get('must_spend_l2_trigger') == 1
        assert 'fuel_filler_stall_buy' in state_of(sess2).cw4_counters

    def test_outside_zone_no_l2(self):
        """负向对照:域外同形态(A 支不成立)⇒ 零发射(域外逐位零变化)。"""
        st, sess = _zone_frame(gold=40)   # gold 40 < 50 出域;店空
        act = _decide(st, sess)
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'fuel_filler_stall')
        assert 'must_spend_l2_trigger' not in state_of(sess).cw4_counters


class TestL3MustSpend:

    def test_l3_skeleton_only_mode_applies(self):
        """C1 模式无关锁:skeleton_only(骨架 only)帧 ⇒ L3 照样适用
        (金量级裁定与模式无关,ADR-0528 模式无关声明)。"""
        st, sess = _zone_frame(gold=80, cards=[])
        act = shop.decide_shop_action(st, sess,
                                      SimpleNamespace(ev_arm='skeleton_only'))
        assert isinstance(act, LevelUpShop)
        assert act.auth_basis == 'm3_batch:must_spend'

    def test_ev_deferred_consume_keyed(self, monkeypatch):
        """C5 归因分键:EV veto 候选域内降排序末位消费 ⇒
        must_spend_ev_deferred 分键在案(§3.5 归因纪律)。帧 = 未锁线
        (L2 垫件臂不劫),candidates/veto 桩化定向。垫件取 2 费:未锁线
        cost-1 零重叠帧属 T5 未锁线止血买触发域(垫底级先于 EV 消费,
        未锁线转换通道设计稿 §4),本锁只辖 EV 降排序语义,须出 T5 域。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
            buy as crit_buy,
        )
        monkeypatch.setattr(
            crit_buy, 'ev_buy_candidates',
            lambda gold, s_reserve, shop_cards, k_members, **kw:
            ([crit_buy.BuyCandidate('燃料件X', 2, 1, 0)], ''))
        monkeypatch.setattr(crit_buy, 'ev_buy_veto',
                            lambda cand, gold: (True, 'expectation'))
        # dominance 猴补关(泄金阶梯档 0 后,域内 1★ 全额退零重叠候选被
        # 支配臂先吃——本锁辖 EV 降排序语义,隔离档 0/档 2 两臂(同为
        # 摘旗扩域,候选类同),构造声明同前)。
        monkeypatch.setattr(mandate, 'dominance_buy_eligible',
                            lambda *a, **kw: False)
        monkeypatch.setattr(shop.crit_stockpile, 'stockpile_buy',
                            lambda *a, **kw: (False, 'not_in_tier'))
        st, sess = _zone_frame(gold=80, locked=False)
        st.shop = [ShopCard(x=100, name='燃料件X', cost=2, star=1)]
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'ev_buy'
        assert state_of(sess).cw4_counters.get('must_spend_ev_deferred') == 1
        assert 't3_buy' not in state_of(sess).cw4_counters

    def test_whitelist_empty_shop_cap_top_zero_consume(self):
        """白名单③④合形负锁(店空 ∧ 等级帽拦):三消费出口全关
        (CloseShop 收口),分键可辨(no_chaseable)。帧等级语义重推
        (ADR-0565):旧帧 lv9 在 LEVEL_CAP=9 旧语义下即 cap 顶,现
        live 真值 cap=10、lv9 是正常付费档 ⇒ 等级帽过、L3 拒因改落
        P48 整买拦截(批 84 金 > 80),``level_cap`` 分键不再产生——
        真满级帧的 level_cap 显影归 prep 侧锁
        (本文件 prep 段 test_level_cap_keyed)与商店单一源三帧锁
        (test_cw_shop_line)承载。"""
        st, sess = _zone_frame(gold=80, cards=[], level=9, locked=False)
        st.deployed = [_bc(m, star=2, slot=i + 1)
                       for i, m in enumerate(line_members(get_comp(_COMP)))]
        act = _decide(st, sess)
        assert not isinstance(act, (BuyCard, RefreshShop, LevelUpShop))
        assert state_of(sess).cw4_counters.get('batch_unaffordable') == 1
        assert 'level_cap' not in state_of(sess).cw4_counters
        assert state_of(sess).cw4_counters.get('shop_r1_no_chaseable_member') == 1


class TestPrepL3Zone:

    def test_prep_zone_l3_emits_despite_stop_hp(self):
        """应-C(双栈断层第三犯根修):备战 M3 面接入必花域——必花帧
        (M3 三臂空闲 ∧ level_spend_blocked 在场)⇒ 停付线域内让位,
        LevelUp 仍发射(auth_basis m3_batch:must_spend)+ 触发源分键。"""
        comp = get_comp(_COMP)
        km = list(line_members(comp))
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km[:3])]
        frame = mandate.MandateFrame(
            gold=80, level=5, bench=[], deployed=deployed,
            deploy_cap=5, node_type='battle', stop_flag=False,
            k_members=tuple(km), round_num=2)
        st = GameState(gold=80, level=5, hp=30, plane=2, round_num=2)
        st.level_readable = True
        st.node_type = 'battle'
        sess = SimpleNamespace(cw4_counters={}, target_comp=comp,
                               v3_intention=IntentionState(),
                               active_strategies=[])
        out = mandate.run_mandate(frame, sess, state=st)
        lv = [e for e in out if isinstance(e.action, LevelUp)]
        assert lv, '备战必花帧停付线让位:LevelUp 仍发射'
        assert lv[0].reason == 'm3_levelup_batch:must_spend'
        assert state_of(sess).cw4_counters.get('must_spend_l3_prep_trigger') == 1
        assert state_of(sess).cw4_counters.get('crisis_level_spend_defer') is None

    def test_prep_zone_defer_overridden_keyed_on_arm1(self):
        """域内停付让位显影(与 shop 侧 must_spend_r1_account_yielded
        对称):arm1 命中(板满+bench 有线成员)∧ 必花域 ∧
        level_spend_blocked 真的帧 ⇒ 升级仍发射(让位生效),新分键
        must_spend_zone_defer_overridden 在案,crisis_level_spend_defer
        不落(域外语义零变化,ADR-0528 域辖裁定)。"""
        comp = get_comp(_COMP)
        km = list(line_members(comp))
        # 线成员恰 4 人 ⇒ cap 口径取 4(state.deploy_cap=4 ∧ level=4,
        # max_units=min(cap,front+back)=4)凑板满 = arm1 第一腿。
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km)]
        bench = [_bc('姬子', star=1, slot=1)]   # 与板上姬子·启行同源阵营
        frame = mandate.MandateFrame(
            gold=80, level=4, bench=bench, deployed=deployed,
            deploy_cap=4, node_type='battle', stop_flag=False,
            k_members=tuple(km), round_num=2)
        st = GameState(gold=80, level=4, hp=30, plane=2, round_num=2)
        st.level_readable = True
        st.deploy_cap = 4
        st.node_type = 'battle'
        sess = SimpleNamespace(cw4_counters={}, target_comp=comp,
                               v3_intention=IntentionState(),
                               active_strategies=[])
        out = mandate.run_mandate(frame, sess, state=st)
        lv = [e for e in out if isinstance(e.action, LevelUp)]
        assert lv, '域内停付让位:LevelUp 仍发射(停付被域裁压掉)'
        assert lv[0].reason == 'm3_levelup_batch:arm1'
        assert state_of(sess).cw4_counters.get(
            'must_spend_zone_defer_overridden') == 1
        assert state_of(sess).cw4_counters.get('crisis_level_spend_defer') is None

    def test_prep_level_unreadable_fails_closed(self):
        """fail 向锁(资格硬闸,mandate getattr 链):等级不可信帧
        (level_readable=False)⇒ 零升级发射 + 无 must_spend 分键
        (fail 向不静默触发;arm0 侧 arm0_level_unreadable 分键在案
        证明 fail 向路径被走)。"""
        comp = get_comp(_COMP)
        km = list(line_members(comp))
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km[:3])]
        frame = mandate.MandateFrame(
            gold=80, level=5, bench=[], deployed=deployed,
            deploy_cap=5, node_type='battle', stop_flag=False,
            k_members=tuple(km), round_num=2)
        st = GameState(gold=80, level=5, hp=30, plane=2, round_num=2)
        st.level_readable = False
        st.node_type = 'battle'
        sess = SimpleNamespace(cw4_counters={}, target_comp=comp,
                               v3_intention=IntentionState(),
                               active_strategies=[])
        out = mandate.run_mandate(frame, sess, state=st)
        assert not [e for e in out if isinstance(e.action, LevelUp)]
        assert state_of(sess).cw4_counters.get('arm0_level_unreadable') == 1
        assert 'must_spend_l3_prep_trigger' not in state_of(sess).cw4_counters
        assert 'must_spend_zone_defer_overridden' not in state_of(sess).cw4_counters

    def test_prep_outside_zone_arms_idle_zero_consume(self):
        """域外对照:同形态 gold=40(出域)且三臂空闲 ⇒ 域外零变化——
        不触发升级、无 must_spend 分键(停付线 defer 分键辖「臂命中帧」,
        由既有危机锁承载)。"""
        comp = get_comp(_COMP)
        km = list(line_members(comp))
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km[:3])]
        frame = mandate.MandateFrame(
            gold=40, level=5, bench=[], deployed=deployed,
            deploy_cap=5, node_type='battle', stop_flag=False,
            k_members=tuple(km), round_num=2)
        st = GameState(gold=40, level=5, hp=30, plane=2, round_num=2)
        st.level_readable = True
        st.node_type = 'battle'
        sess = SimpleNamespace(cw4_counters={}, target_comp=comp,
                               v3_intention=IntentionState(),
                               active_strategies=[])
        out = mandate.run_mandate(frame, sess, state=st)
        assert not [e for e in out if isinstance(e.action, LevelUp)]
        assert state_of(sess).cw4_counters.get('crisis_level_spend_defer') is None
        assert 'must_spend_l3_prep_trigger' not in state_of(sess).cw4_counters


class TestR1ZoneSplit:

    def test_r1_account_veto_demoted_in_zone(self):
        """R1 切分线:必花域内 account_over_budget 核算否决降排序——
        分层全 ladder 走完后零消费以 CloseShop 收口,且核算否决分键
        不在案(域外同形帧会记 account_over_budget)。"""
        km = list(line_members(get_comp(_COMP)))
        chaseable1 = km[0]   # 可追成员留 1★ ⇒ 合格集非空(D≠∅ 过)
        deployed = [_bc(m, star=2, slot=i + 1)
                    for i, m in enumerate(km) if m != chaseable1]
        bench = [_bc(chaseable1, star=1, slot=1)]
        st = GameState(gold=51, level=9, round_num=2, hp=60)
        st.level_readable = True
        st.plane = 2
        st.node_type = 'battle'
        st.shop = []
        st.bench = bench
        st.deployed = deployed
        st.refresh_probs = {}
        st.shop_refresh_cost = 2
        sess = _ns_with_state(cw4_counters={}, target_comp=get_comp(_COMP),
                              v3_intention=SimpleNamespace(
                                  locked_comp=_COMP))
        act = _decide(st, sess)
        # ladder 显影:L2 垫件缺 + L3 整批拒均零消费——L3 拒因语义重推
        # (ADR-0565):lv9 非 live cap(cap=10),等级帽过、批 84 金 > 51
        # ⇒ 拒因落 batch_unaffordable(P48 整买拦截),level_cap 不再产生
        assert state_of(sess).cw4_counters.get('fuel_not_on_sale') == 1
        assert state_of(sess).cw4_counters.get('batch_unaffordable') == 1
        assert 'level_cap' not in state_of(sess).cw4_counters
        # 应-A 零静默:切分线让位发生 ⇒ yielded 分键在案
        assert state_of(sess).cw4_counters.get('must_spend_r1_account_yielded') == 1
        # 切分线生效:核算否决(g*/L 账)未拦 R1(域外同形帧会记该键)
        assert 'shop_r1_account_over_budget' not in state_of(sess).cw4_counters
        assert not isinstance(act, RefreshShop)   # 可负担性硬闸仍辖(金 51)
        assert isinstance(act, CloseShop)

    def test_r1_budget_fail_liveness_key(self):
        """刷新臂 liveness 显影(52 轮 sim 设计输入②):域内刷新尝试被
        可负担性硬闸拦 ⇒ must_spend_r1_budget_fail 显式分键(禁恒零
        盲区,directed_refresh_game_cap_lock 绿灯掩盖恒零教训)。"""
        st, sess = _zone_frame(gold=51, level=9, cards=[])
        act = _decide(st, sess)
        assert not isinstance(act, RefreshShop)
        assert state_of(sess).cw4_counters.get('must_spend_r1_budget_fail') == 1


# ===== 实机档案帧单帧锁核(未锁线入域帧出口消费语义核)=====
# 设计出处:20号稿 §3.1-L2(未锁线 fail-closed 设计态)+ §3.5(L3 触发源)+
# ADR-0528(域内让位裁定)。
# 帧源 = 实机对局档案(生产流根单一源 kernel/cw_observe.DEFAULT_REPLAY_DIR
# = telemetry/live,对局档案在其 matches/ 下)的 slices/decisions.jsonl
# 决策帧逐字段直读(帧定位符 = ts 字符串;测试值内联,不依赖档案存在)。
#
# cap_resolved 实算定谳:三帧涉及策略(加油站/量子力学/榜样的力量•彩)
# 均无 interest_cap_override ⇒ cap_resolved = DEFAULT_INTEREST_CAP = 5,
# G_must = 50。档案判读中的「g46/47 入域」「P3r1 g50 域内帧」按 §2.1
# 严格大于语义均**未入域**(50 等值不出),真正入域帧 = g58/62/63/76/87。
#
# 重建缺口(如实声明):十九局 P1 帧档案 target_comp =「过渡配方·仙舟+
# 持续伤害」不在 comp 注册表(P1 过渡线由 p1_pair 运行时物化,成员集
# 不可离线重建)——未锁线帧以 k=None 重建,k 派生面(拒因/EV 买面)
# 不在锁面,只锁必花域出口消费语义。二十局 P3r1 帧(希儿量子)全输入
# 可重建,档案动作逐位复现。


def _arc_bc(d: dict, i: int = 0) -> BenchChar:
    """档案帧单位重建(bench/deployed 槽位按档案原值)。"""
    return BenchChar(slot=d.get('slot', i + 1), char_id=d['char_id'],
                     star=d.get('star', 1), faction=d.get('faction', ''),
                     position_pref=d.get('position_pref', 'back'))


def _arc_state(**kw) -> GameState:
    """档案帧 GameState 重建(必填标量直传;可信位按档案 true)。"""
    st = GameState(gold=kw['gold'], hp=kw['hp'], level=kw['level'],
                   plane=kw['plane'], round_num=kw['round_num'])
    st.node_type = kw.get('node_type', 'battle')
    st.xp_progress = tuple(kw['xp_progress'])
    st.level_up_cost = kw.get('level_up_cost') or 0
    st.shop_refresh_cost = kw.get('shop_refresh_cost') or 2
    st.deploy_cap = kw.get('deploy_cap') or 0
    st.level_readable = True
    st.hp_trusted = True
    st.gold_readable = True
    st.refresh_probs = kw.get('refresh_probs')
    st.shop = list(kw.get('shop') or [])
    st.bench = list(kw.get('bench') or [])
    st.deployed = list(kw.get('deployed') or [])
    return st


class TestArchiveFrameReplay:
    """两局档案真实帧在当前代码(必花域紧随批 03b145a7 载)下的出口消费
    语义锁:触发源分键/层命中/让位显影/拒因分键各自落点(20 号稿
    §3/§3.5)。"""

    def test_g19_r6_g46_offer_consumes_via_t1_not_zone(self):
        """十九局 r6 offer 帧(ts 2026-09-05T23:24:50,gold46,店 5 张全
        non_line):域外帧无必花域出口——分键面无 must_spend 触发。
        锁语义重推(T-115 规则③,ADR-0580):店中希儿 = registry 核心
        卡,未锁线恒买放行(裁定 410:「1-3 未锁线不触发」即病灶本体)
        ⇒ 本帧出口从「t1 凑息卖」改为「core_single_card_buy:unlocked」
        ——单动作契约下凑息卖下帧再评,域外无 must_spend 分键的锁意图
        不变;t1 消费语义由息线族主题文件
        test_cw_interest_floor 锁组与 r5 帧锁承载。"""
        st = _arc_state(gold=46, hp=47, level=5, plane=1, round_num=6,
                        node_type='普通战斗', xp_progress=(10, 20),
                        level_up_cost=4, deploy_cap=5,
                        bench=[_arc_bc({'char_id': '椒丘', 'star': 1,
                                        'slot': 2, 'faction': '狼狩',
                                        'position_pref': 'back'}, 1)],
                        deployed=[_arc_bc({'char_id': '爻光', 'star': 1,
                                           'slot': 1, 'faction': '仙舟',
                                           'position_pref': 'front'}),
                                  _arc_bc({'char_id': '藿藿', 'star': 1,
                                           'slot': 1, 'faction': '仙舟',
                                           'position_pref': 'back'}),
                                  _arc_bc({'char_id': '卡芙卡', 'star': 1,
                                           'slot': 2,
                                           'faction': '星核猎手',
                                           'position_pref': 'back'})],
                        shop=[ShopCard(x=501, name='飞霄', cost=1, star=1),
                              ShopCard(x=754, name='风堇', cost=2, star=1),
                              ShopCard(x=1007, name='希儿', cost=3, star=1),
                              ShopCard(x=1260, name='乱破', cost=1, star=1),
                              ShopCard(x=1514, name='阮·梅', cost=2, star=1)])
        sess = SimpleNamespace(cw4_counters={}, target_comp=None,
                               v3_intention=None)
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.card.name == '希儿'
        assert act.reason == 'core_single_card_buy:unlocked'
        assert not [k for k in state_of(sess).cw4_counters
                    if k.startswith('must_spend')]

    def test_g19_r7_inzone_unlocked_frame_consumes_via_l3(self):
        """未锁线入域帧出口消费语义(33 跳精化口径核心锁):r7 帧
        (ts 2026-09-05T23:28:04,gold58,xp 12/20 ⇒ 批 s=8,花后 50 贴
        g* 闸过)经 ladder 末位 L3 消费 ⇒ LevelUpShop(auth_basis=
        'm3_batch:must_spend')——十九局「入域零消费」形态(旧码形
        faf09a64,第三触发源缺)在当前码形不复现,闸上线后由本帧承载
        L3 消费语义锁。r9 帧(奖励关,原第二腿)断言面 =
        reward_node_defer/reward_node_must_spend_defer 双分键,由
        test_cw_mandate_v1.TestRewardNodeSuppress 超集承载,已并。"""
        gold, xp = 58, (12, 20)
        st = _arc_state(gold=gold, hp=47, level=5, plane=1,
                        round_num=7, node_type='encounter',
                        xp_progress=xp, level_up_cost=4,
                        refresh_probs={'1': 0.45, '2': 0.33, '3': 0.2,
                                       '4': 0.02, '5': 0.0})
        sess = SimpleNamespace(cw4_counters={}, target_comp=None,
                               v3_intention=None)
        act = _decide(st, sess)
        assert isinstance(act, LevelUpShop), (gold, act)
        assert act.auth_basis == 'm3_batch:must_spend'
        assert 'must_spend_l2_trigger' not in state_of(sess).cw4_counters

    def test_g20_p3r1_g50_locked_replays_archive_buy(self):
        """二十局 P3r1 g50 帧(ts 2026-09-06T01:38:38,希儿量子锁定,全
        输入可重建):档案动作 BuyCard 缇宝(reason m2_stockpile)逐位
        复现——「域内帧被 spend_unified 拦截」的帧前提不成立:该帧未入域
        且消费实际发生(M2 义务买入)。"""
        km_units = [
            {'char_id': '椒丘', 'star': 1, 'slot': 1, 'faction': '狼狩',
             'position_pref': 'front'},
            {'char_id': '希儿', 'star': 2, 'slot': 2, 'faction': '贝洛伯格',
             'position_pref': 'front'},
            {'char_id': '爻光', 'star': 1, 'slot': 1, 'faction': '仙舟',
             'position_pref': 'back'},
            {'char_id': '卡芙卡', 'star': 1, 'slot': 2,
             'faction': '星核猎手', 'position_pref': 'back'},
            {'char_id': '藿藿', 'star': 2, 'slot': 3, 'faction': '仙舟',
             'position_pref': 'back'},
            {'char_id': '花火', 'star': 2, 'slot': 4, 'faction': '盛会之星',
             'position_pref': 'back'},
            {'char_id': '刻律德菈', 'star': 1, 'slot': 5,
             'faction': '夜之半神', 'position_pref': 'back'},
            {'char_id': '符玄', 'star': 1, 'slot': 6, 'faction': '仙舟',
             'position_pref': 'back'},
        ]
        bench_units = [
            {'char_id': '娜塔莎', 'star': 1, 'slot': 1,
             'faction': '贝洛伯格', 'position_pref': 'back'},
            {'char_id': '缇宝', 'star': 1, 'slot': 2, 'faction': '昼之半神',
             'position_pref': 'back'},
            {'char_id': '真理医生', 'star': 2, 'slot': 3,
             'faction': '银河学者', 'position_pref': 'front'},
            {'char_id': 'Saber', 'star': 1, 'slot': 4,
             'faction': '命运圣杯', 'position_pref': 'back'},
            {'char_id': 'Saber', 'star': 1, 'slot': 5,
             'faction': '命运圣杯', 'position_pref': 'back'},
        ]
        st = _arc_state(
            gold=50, hp=14, level=8, plane=3, round_num=1,
            node_type='battle', xp_progress=(18, 72), level_up_cost=4,
            deploy_cap=8, refresh_probs={'1': 0.18, '2': 0.25, '3': 0.32,
                                         '4': 0.22, '5': 0.03},
            bench=[_arc_bc(b, i) for i, b in enumerate(bench_units)],
            deployed=[_arc_bc(d, i) for i, d in enumerate(km_units)],
            shop=[ShopCard(x=501, name='银枝', cost=2, star=1),
                  ShopCard(x=754, name='星期日', cost=3, star=1),
                  ShopCard(x=1007, name='长夜月', cost=4, star=1),
                  ShopCard(x=1260, name='缇宝', cost=2, star=1),
                  ShopCard(x=1514, name='银枝', cost=2, star=1)])
        sess = _ns_with_state(
            cw4_counters={}, target_comp=get_comp('希儿量子'),
            v3_intention=SimpleNamespace(phase='locked',
                                         locked_comp='希儿量子'))
        assert in_must_spend_zone(50, sess) is False
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'm2_stockpile'
        assert (act.card.name or '') == '缇宝'

    def test_g20_p3r1_derived_inzone_consumes_r1_yielded(self, monkeypatch):
        """域内对照帧(派生,声明:g50 帧金 50→54 入域带内,店/bench 摘
        缇宝消 M2 义务面,其余档案原值):入域帧消费路径 = R1 域内残形
        切分线——RefreshShop(reason='must_spend_r1_yielded' 触发源记录)
        + yielded 分键/L2 触发源分键/围栏拆键全在案,拒因逐键可辨
        (§3.5 归因纪律,域内无静默)。"""
        st = _arc_state(
            gold=54, hp=14, level=8, plane=3, round_num=1,
            xp_progress=(18, 72), level_up_cost=4, deploy_cap=8,
            refresh_probs={'1': 0.18, '2': 0.25, '3': 0.32, '4': 0.22,
                           '5': 0.03},
            bench=[_arc_bc({'char_id': '娜塔莎', 'star': 1, 'slot': 1,
                            'faction': '贝洛伯格', 'position_pref': 'back'}),
                   _arc_bc({'char_id': '真理医生', 'star': 2, 'slot': 3,
                            'faction': '银河学者', 'position_pref': 'front'}),
                   _arc_bc({'char_id': 'Saber', 'star': 1, 'slot': 4,
                            'faction': '命运圣杯', 'position_pref': 'back'})],
            deployed=[_arc_bc(d, i) for i, d in enumerate([
                {'char_id': '椒丘', 'star': 1, 'slot': 1, 'faction': '狼狩',
                 'position_pref': 'front'},
                {'char_id': '希儿', 'star': 2, 'slot': 2,
                 'faction': '贝洛伯格', 'position_pref': 'front'},
                {'char_id': '爻光', 'star': 1, 'slot': 1, 'faction': '仙舟',
                 'position_pref': 'back'},
                {'char_id': '卡芙卡', 'star': 1, 'slot': 2,
                 'faction': '星核猎手', 'position_pref': 'back'},
                {'char_id': '藿藿', 'star': 2, 'slot': 3, 'faction': '仙舟',
                 'position_pref': 'back'},
                {'char_id': '花火', 'star': 2, 'slot': 4,
                 'faction': '盛会之星', 'position_pref': 'back'},
                {'char_id': '刻律德菈', 'star': 1, 'slot': 5,
                 'faction': '夜之半神', 'position_pref': 'back'},
                {'char_id': '符玄', 'star': 1, 'slot': 6, 'faction': '仙舟',
                 'position_pref': 'back'}])],
            shop=[ShopCard(x=501, name='银枝', cost=2, star=1),
                  ShopCard(x=754, name='星期日', cost=3, star=1),
                  ShopCard(x=1007, name='长夜月', cost=4, star=1),
                  ShopCard(x=1514, name='银枝', cost=2, star=1)])
        sess = _ns_with_state(
            cw4_counters={}, target_comp=get_comp('希儿量子'),
            v3_intention=SimpleNamespace(phase='locked',
                                         locked_comp='希儿量子'))
        # dominance/M6 猴补关(锁语义重推注,泄金阶梯档 0+档 2):域内
        # 1★ 店牌(银枝/星期日/长夜月 全 1★ 全额退零重叠)摘旗后被
        # 支配/压库臂先买,R1-yielded 消费路径不可达——本锁辖 R1 切分线
        # 语义,隔离档 0/档 2(构造声明 = 泄金阶梯锁文件头同款),隔离
        # 后档案帧路径原样。
        monkeypatch.setattr(mandate, 'dominance_buy_eligible',
                            lambda *a, **kw: False)
        monkeypatch.setattr(shop.crit_stockpile, 'stockpile_buy',
                            lambda *a, **kw: (False, 'not_in_tier'))
        act = _decide(st, sess)
        assert isinstance(act, RefreshShop)
        assert act.reason == 'must_spend_r1_yielded'
        assert state_of(sess).cw4_counters.get('must_spend_r1_account_yielded') == 1
        assert state_of(sess).cw4_counters.get('must_spend_l2_trigger') == 1
        assert state_of(sess).cw4_counters.get('fuel_filler_stall_fenced') == 4
        assert state_of(sess).cw4_counters.get(
            'fuel_filler_stall_fenced_l2_cap') == 2


# ===== prep 段(合并批②自 test_cw_l3_prep_must_spend_latch 迁入,断言双留)=====

_DEP7 = ['藿藿', '艾丝妲', '丹恒·饮月', '风堇', '爻光', '彦卿', '椒丘']
_BENCH5 = ['千冶·刃', '银狼LV.999', '卡芙卡', '姬子·启行', '三月七']
_KM = ('卡芙卡', '千冶·刃', '银狼LV.999')


def _mk(gold: int, *, hp: int = 1, level: int = 7,
        round_num: int = 5, xp: tuple[int, int] | None = (22, 52),
        click_cost: int = 4):
    """二十二局濒死帧态(复盘 g_20260906_034515 专节1):P2r5 hp1、
    lv7(cap=7 板满七件过渡板)、xp 22/52、单击 4 金、bench 有线成员
    (arm1 命中=进块前提;门链回放脚本 cw_l3_gate_replay.py 同源形态)。"""
    deployed = [_bc(n, star=2 if n == '椒丘' else 1, slot=i + 1)
                for i, n in enumerate(_DEP7)]
    bench = [_bc(n, star=1, slot=i + 1)
             for i, n in enumerate(_BENCH5)]
    frame = mandate.MandateFrame(
        gold=gold, level=level, bench=bench, deployed=deployed,
        deploy_cap=7, node_type='encounter', stop_flag=False,
        k_members=_KM, round_num=round_num)
    st = GameState(gold=gold, level=level, hp=hp, plane=2,
                   round_num=round_num)
    st.level_readable = True
    st.node_type = 'encounter'
    st.xp_progress = xp
    st.level_up_cost = click_cost
    sess = _ns_session(None)
    return frame, sess, st


def _lvls(out):
    return [e for e in out if isinstance(e.action, LevelUp)]


class TestPrepMustSpendLatch:
    """必花域备战期闩(g_20260906_034515 濒死段形态逐帧回放锁)。"""

    def test_latch_extends_zone_after_shop_consume(self):
        """域内停付让位显影面与闩延命计数面保持(ADR-0528 机制不变),
        与 P72 全段预算闸(ADR-0576)的分域交互:帧A(g56 入域,批
        s=32,τ=5 花后 24 不容)被预算闸整批推迟(闸在域内生效);
        帧B(闩延命残金 43 ≤ g*)——旧锁此处钉 ADR-0560 §4「非溢余段
        vacuous 放行 ⇒ 残金帧发射保持」,该辖域语义已被 P72 全段化
        **取代**(锁重推:τ(43)=4,floor=40+2ρ,批 32 花后 11 = 息损
        3 档,恰是签名 A 潜行形态,闸拒=整批推迟);闩延命显影分键
        (帧绑定,非发射绑定)原样在案。"""
        fa, sess, sta = _mk(56)
        out_a = mandate.run_mandate(fa, sess, state=sta)
        assert not _lvls(out_a), '入域帧穿线批:预算闸整批推迟'
        assert state_of(sess).cw4_counters.get(
            'must_spend_zone_defer_overridden') == 1   # 停付让位显影面仍在
        assert state_of(sess).cw4_counters.get('levelup_budget_gate_blocked') == 1
        fb, _, stb = _mk(43)   # 商店域消费 13 金后的残金帧
        out_b = mandate.run_mandate(fb, sess, state=stb)
        assert not _lvls(out_b), '残金帧中间段由 P72 全段闸管账(拒=推迟)'
        assert state_of(sess).cw4_counters.get('must_spend_zone_latch_extend') == 1
        assert state_of(sess).cw4_counters.get('levelup_budget_gate_blocked') == 2

    # 「无闩帧危机带常态挂起」对照面由 test_latch_expires_next_round 承载
    # (过帧同走 _zone_latched=False 同一生产分支,断言对逐位相同:
    # crisis_level_spend_defer==1 ∧ 无 latch_extend;过期测多钉键式
    # (plane, round) 不继承语义,为超集,不另立 virgin 副本)。

    def test_latch_expires_next_round(self):
        """闩相位键式 = (plane, round):下一备战期(新键)不继承,
        域外帧回归危机带常态挂起。"""
        fa, sess, sta = _mk(56)
        mandate.run_mandate(fa, sess, state=sta)
        fn, _, stn = _mk(43, round_num=6)
        out = mandate.run_mandate(fn, sess, state=stn)
        assert not _lvls(out)
        assert state_of(sess).cw4_counters.get('crisis_level_spend_defer') == 1
        assert 'must_spend_zone_latch_extend' not in state_of(sess).cw4_counters


class TestL3RejectKeys:
    """L3 资格拒分键(拒因落盘缺口治疗:「拒因不可辨」复盘主项)。"""

    def test_level_cap_keyed(self):
        """域内满级帧 ⇒ 零发射 + l3_reject_level_cap 分键在案。
        帧等级语义重推(ADR-0565):旧锁 _mk(56, level=9) 钉
        LEVEL_CAP=9 旧语义,已被注册表真值证伪(live cap=10,lv9 是
        正常付费档)——满级帧改 lv10;lv9 帧改由分键否定面钉(不再
        因等级帽拒)。"""
        f, sess, st = _mk(56, level=10)
        out = mandate.run_mandate(f, sess, state=st)
        assert not _lvls(out)
        assert state_of(sess).cw4_counters.get('l3_reject_level_cap') == 1
        # lv9 帧:等级帽过(非 live cap)⇒ l3_reject_level_cap 不产生
        # (该帧后续由 P71-b 预算闸接手,闸语义归 ADR-0560 锁辖)
        f9, sess9, st9 = _mk(56, level=9)
        out9 = mandate.run_mandate(f9, sess9, state=st9)
        assert 'l3_reject_level_cap' not in state_of(sess9).cw4_counters
        assert not _lvls(out9)

    def test_batch_unaffordable_keyed(self):
        """域内整批买不齐(单击价 13 金 ×13 击 > 51)⇒ 零发射 +
        l3_reject_batch_unaffordable 分键在案(P48 整买纪律拦截显影)。"""
        f, sess, st = _mk(51, hp=80, xp=(0, 52), click_cost=13)
        out = mandate.run_mandate(f, sess, state=st)
        assert not _lvls(out)
        assert state_of(sess).cw4_counters.get('l3_reject_batch_unaffordable') == 1

    def test_xp_readthrough_rescues_residual_band(self):
        """xp 现读透传(第二静默拒因面修复)——拒因可辨面保持,发射面
        随 P72 全段化重推(ADR-0576):旧锁「xp 现读 ⇒ 残金帧发射保持
        (ADR-0528 原语义)」钉的空过辖域已取代;现两形态**都拒但拒因
        分键可辨**——xp 22/52 现读(真 8击×4=32 ≤ 43)⇒ 过 spend_
        unified 后落在闸的中间段辖域(τ(43)=4,花后 11 < floor)⇒
        levelup_budget_gate_blocked;xp 缺读(虚 13击×4=52>43)⇒
        spend_unified 拒 l3_reject_batch_unaffordable——判决不同源、
        归因不混桶(xp 透传的治疗目标就是拒因可辨)。"""
        fa, sess2, sta = _mk(56)       # 先以域内帧置闩(同备战期)
        mandate.run_mandate(fa, sess2, state=sta)
        fb, _, stb = _mk(43)
        out_b = mandate.run_mandate(fb, sess2, state=stb)
        assert not _lvls(out_b)
        assert state_of(sess2).cw4_counters.get(
            'levelup_budget_gate_blocked') == 2
        fc, _, stc = _mk(43, xp=None)
        out2 = mandate.run_mandate(fc, sess2, state=stc)
        assert not _lvls(out2)
        assert state_of(sess2).cw4_counters.get('l3_reject_batch_unaffordable') == 1


class TestL3RegistryInjection:
    """注册表注入变异锁(ADR-0565 第 4 消费位挂账收口 = ADR-0606):
    备战 M3 链的等级帽/停付让位消费位必须消费**注入注册表**。锁的
    形态 = 同帧换注入表判定必翻转(拆接线回读缺省表 → 判定落回缺省
    口径 → 本组红),锁行为不锁回显。

    帧态基座 = 本文件 prep 段 ``_mk``(arm1 命中 = 进块前提,既有键测
    同源):gold=56(> G_must=50,域内)/gold=40(域外)两档分流让位
    与判据链。"""

    def test_level_cap_follows_injected_registry(self):
        """等级帽注入变异锁:注入 level_max=9 视图 ⇒ lv9 帧因等级帽拒
        (l3_reject_level_cap 分键);换 level_max=11 同帧过帽(分键不落,
        链条到预算闸接手证明非静默)。拆接线回读缺省表(=10)⇒ lv9 帧
        过帽 ⇒ 首断言红。"""
        cap9 = replace(DEFAULT_REGISTRY, level_max=9)
        f9, sess9, st9 = _mk(56, level=9)
        out9 = mandate.run_mandate(f9, sess9, state=st9, registry=cap9)
        assert not _lvls(out9)
        assert state_of(sess9).cw4_counters.get('l3_reject_level_cap') == 1
        assert 'l3_reject_batch_unaffordable' not in \
            state_of(sess9).cw4_counters
        cap11 = replace(DEFAULT_REGISTRY, level_max=11)
        f11, sess11, st11 = _mk(56, level=9)
        out11 = mandate.run_mandate(f11, sess11, state=st11, registry=cap11)
        assert not _lvls(out11)
        assert 'l3_reject_level_cap' not in state_of(sess11).cw4_counters
        # 过帽后续门接手:xp 22/52 现读真 8 击×4=32 ≤ 56 整买过,落在
        # P72 全段闸中间段 ⇒ levelup_budget_gate_blocked(与既有 lv9
        # 否定面锁同口径:帽外帧由预算闸接手,分键翻转源于注入表)。
        assert state_of(sess11).cw4_counters.get(
            'levelup_budget_gate_blocked') == 1

    def test_level_spend_blocked_follows_injected_registry(self):
        """停付让位注入变异锁:注入 vd_p2_loss=30(P2 危机带线 41→60,
        ``p2_crisis_stop_hp`` 同源派生)⇒ hp=50 帧落 crisis_level_spend_
        defer;缺省表(线 41)同帧不停付,链条到预算闸接手。拆接线回读
        缺省表 ⇒ 首断言红。"""
        wide = replace(DEFAULT_REGISTRY, vd_p2_loss=30.0)
        fw, sessw, stw = _mk(40, hp=50)
        outw = mandate.run_mandate(fw, sessw, state=stw, registry=wide)
        assert not _lvls(outw)
        assert state_of(sessw).cw4_counters.get(
            'crisis_level_spend_defer') == 1
        fd, sessd, std = _mk(40, hp=50)
        outd = mandate.run_mandate(fd, sessd, state=std,
                                   registry=DEFAULT_REGISTRY)
        assert not _lvls(outd)
        assert 'crisis_level_spend_defer' not in state_of(sessd).cw4_counters
        # 停付未触发面:整买 8 击×4=32 ≤ 40 过,预算闸中间段接手(同帧
        # 异表分键翻转,证明停付判定消费的是注入表)。
        assert state_of(sessd).cw4_counters.get(
            'levelup_budget_gate_blocked') == 1


class TestBoardTargetLineTrackedFallback:
    """b_t 实机回退源(两局全帧 0.0 实证:商店观察帧 deployed
    恒空 → 写者输入缺;回退 = exec_state_of(session).tracked_deployed)。

    空板 = 0 面由 test_cw_obs_face_keys.py::TestBoardTargetLineWriter::
    test_empty_board_zero_and_stamp 承载(同输入 GameState() 直调同一
    写者,超集另锁轮键戳章),此处只留回退路径独家面。
    """

    def _strat(self):
        from sr_od.application.currency_war.sim.engine_p1 import (
            sim_decision_registry,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        return MandateV1Strategy(registry=sim_decision_registry())

    def test_empty_state_deployed_falls_back_to_tracked(self):
        """state.deployed 空 ∧ tracked_deployed 有件 ⇒ b_t > 0
        (实机商店帧形态;青雀=仙舟∈线内集,3 件 = 3)。"""
        from sr_od.application.currency_war.kernel.cw_strategy_session import (
            StrategySession,
        )
        sess = StrategySession()
        st = GameState()
        exec_state_of(sess).tracked_deployed = [
            BenchChar(slot=i + 1, char_id='青雀', star=1, faction='仙舟',
                      position_pref='back') for i in range(3)]
        self._strat().write_shop_mirrors(st, sess)
        assert state_of(sess).v3_b_t == 3


class TestRecorderObservationWiring:
    """实机遥测两件接线(refresh_trigger 分键 / sess_terminal_release
    透传;g_20260906_021859 起连续零产出的接线缺治疗)。"""

    def _record(self, tmp_path, actions, ctx=None, monkeypatch=None):
        from sr_od.application.currency_war.telemetry import state as _tel
        from sr_od.application.currency_war.telemetry.recorder import (
            TelemetryRecorder,
        )
        if ctx is not None and monkeypatch is not None:
            monkeypatch.setattr(_tel, '_CTX_MATCH_REF', [ctx])
        rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
        rec.record_decision('run_x', 'A8', GameState(), '', {}, {}, actions)
        lines = (tmp_path / 'decisions.jsonl').read_text(
            encoding='utf-8').strip().splitlines()
        import json
        return json.loads(lines[-1])

    def test_refresh_trigger_counted_from_actions(self, tmp_path):
        """决策行 refresh_trigger = 本行 RefreshShop 按 reason 计数
        ('' 归 other 桶);无刷新行为空 dict(非缺写)。"""
        row = self._record(tmp_path, [
            RefreshShop(reason='must_spend_r1_yielded'),
            RefreshShop(reason=''),
        ])
        assert row.get('refresh_trigger') == {
            'must_spend_r1_yielded': 1, 'other': 1}

    def test_no_refresh_rows_empty_dict(self, tmp_path):
        row = self._record(tmp_path, [])
        assert row.get('refresh_trigger') == {}

    def test_terminal_release_passthrough_equals_source(self, tmp_path,
                                                        monkeypatch):
        """sess_terminal_release = terminal_release_bit(sess, last_state)
        原值透传(单一源等值锁,不锁定值——带域口径归该谓词)。"""
        from sr_od.application.currency_war.sim.checks.segments import (
            terminal_release_bit,
        )
        st = GameState(gold=10, level=5, hp=30, plane=1, round_num=7)
        sess_stub = SimpleNamespace(last_state=st, v3_blood_budget_rejects=0,
                                    v3_blood_budget_refresh_rejects=0,
                                    cw4_shop_rejects={})
        row = self._record(tmp_path, [], ctx=SimpleNamespace(session=sess_stub),
                           monkeypatch=monkeypatch)
        assert row.get('sess_terminal_release') == bool(
            terminal_release_bit(sess_stub, st))

    def test_terminal_release_none_without_match(self, tmp_path):
        """无 match 注册(离线/测试)→ 字段缺省 None(旧 schema 不破坏)。"""
        row = self._record(tmp_path, [])
        assert row.get('sess_terminal_release') is None
