"""必花域落码锁(20 号稿 v2.1;用户裁定 =「无论什么 hp,金这么多都是
要花的」§1 授权文号)。

覆盖:G_must 判据单一源(§2.1,买断制出辖)/ L2 第二触发源(∨ 合并,
触发源分键)/ L3 升级(停付线域内让位 = ADR-0528,资格硬闸照常,
拒因分键 level_cap/batch_unaffordable)/ R1 域内残形切分线(g*/L 账
降期望核算,可负担性留资格硬闸,合格集空守卫照旧)。
负向锁(物理残量白名单形态,§3.2):店空无垫件 ⇒ fuel_not_on_sale
零消费;等级 cap ⇒ level_cap 零消费;域外帧零变化。
"""
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_economy import (
    in_must_spend_zone,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_prep_actions import LevelUp
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    CloseShop,
    GameState,
    LevelUpShop,
    RefreshShop,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    levelup as _crit_levelup,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)

_COMP = '列车同行'


def _bc(name: str, star: int = 2, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


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
    sess = SimpleNamespace(
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
        (cap=0)出辖恒 False。"""
        sess = SimpleNamespace(cw4_cap_override=None)
        assert in_must_spend_zone(51, sess) is True
        assert in_must_spend_zone(50, sess) is False
        buyout = SimpleNamespace(cw4_cap_override=0)
        assert in_must_spend_zone(999, buyout) is False
        rich = SimpleNamespace(cw4_cap_override=10)
        assert in_must_spend_zone(101, rich) is True
        assert in_must_spend_zone(100, rich) is False


class TestL2SecondTrigger:

    def test_zone_triggers_l2_despite_chaseable(self):
        """L2 第二触发源:必花域帧 A 支不辖(可追成员在场,Φ_stall 不
        成立)⇒ 仍发射垫件买 + must_spend_l2_trigger 分键。"""
        km = list(line_members(get_comp(_COMP)))
        pad = next(n for n, ch in __import__(
            'sr_od.application.currency_war.data.cw_chars',
            fromlist=['CHARACTERS']).CHARACTERS.items()
            if n not in km)
        st, sess = _zone_frame(
            gold=80, cards=[ShopCard(x=100, name=pad, cost=1, star=1)])
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'fuel_filler_stall'
        assert sess.cw4_counters.get('must_spend_l2_trigger') == 1
        assert 'fuel_filler_stall_buy' in sess.cw4_counters

    def test_outside_zone_no_l2(self):
        """负向对照:域外同形态(A 支不成立)⇒ 零发射(域外逐位零变化)。"""
        st, sess = _zone_frame(gold=40)   # gold 40 < 50 出域;店空
        act = _decide(st, sess)
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'fuel_filler_stall')
        assert 'must_spend_l2_trigger' not in sess.cw4_counters

    def test_whitelist_empty_shop_no_consume(self):
        """白名单①:店空无垫件 ⇒ fuel_not_on_sale 分键零消费(不炸)。"""
        st, sess = _zone_frame(gold=80, cards=[])
        act = _decide(st, sess)
        assert sess.cw4_counters.get('fuel_not_on_sale') == 1
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'fuel_filler_stall')


class TestL3MustSpend:

    def test_zone_l3_consumes_when_arms_idle(self):
        """L3:必花域 ∧ M3 三臂空闲 ⇒ LevelUpShop(触发源分键
        auth_basis='m3_batch:must_spend')。"""
        st, sess = _zone_frame(gold=80, cards=[])
        act = _decide(st, sess)
        assert isinstance(act, LevelUpShop)
        assert act.auth_basis == 'm3_batch:must_spend'

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
        st, sess = _zone_frame(gold=80, locked=False)
        st.shop = [ShopCard(x=100, name='燃料件X', cost=2, star=1)]
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'ev_buy'
        assert sess.cw4_counters.get('must_spend_ev_deferred') == 1
        assert 't3_buy' not in sess.cw4_counters

    def test_whitelist_empty_shop_cap_top_zero_consume(self):
        """白名单③④合形负锁(店空 ∧ cap 顶):三消费出口全关
        (CloseShop 收口),分键可辨(level_cap/no_chaseable)。"""
        st, sess = _zone_frame(gold=80, cards=[], level=9, locked=False)
        st.deployed = [_bc(m, star=2, slot=i + 1)
                       for i, m in enumerate(line_members(get_comp(_COMP)))]
        act = _decide(st, sess)
        assert not isinstance(act, (BuyCard, RefreshShop, LevelUpShop))
        assert sess.cw4_counters.get('level_cap') == 1
        assert sess.cw4_counters.get('shop_r1_no_chaseable_member') == 1


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
                               cw4_cap_override=None)
        out = mandate.run_mandate(frame, sess, state=st)
        lv = [e for e in out if isinstance(e.action, LevelUp)]
        assert lv, '备战必花帧停付线让位:LevelUp 仍发射'
        assert lv[0].reason == 'm3_levelup_batch:must_spend'
        assert sess.cw4_counters.get('must_spend_l3_prep_trigger') == 1
        assert sess.cw4_counters.get('crisis_level_spend_defer') is None

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
                               cw4_cap_override=None)
        out = mandate.run_mandate(frame, sess, state=st)
        lv = [e for e in out if isinstance(e.action, LevelUp)]
        assert lv, '域内停付让位:LevelUp 仍发射(停付被域裁压掉)'
        assert lv[0].reason == 'm3_levelup_batch:arm1'
        assert sess.cw4_counters.get(
            'must_spend_zone_defer_overridden') == 1
        assert sess.cw4_counters.get('crisis_level_spend_defer') is None

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
                               cw4_cap_override=None)
        out = mandate.run_mandate(frame, sess, state=st)
        assert not [e for e in out if isinstance(e.action, LevelUp)]
        assert sess.cw4_counters.get('arm0_level_unreadable') == 1
        assert 'must_spend_l3_prep_trigger' not in sess.cw4_counters
        assert 'must_spend_zone_defer_overridden' not in sess.cw4_counters

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
                               cw4_cap_override=None)
        out = mandate.run_mandate(frame, sess, state=st)
        assert not [e for e in out if isinstance(e.action, LevelUp)]
        assert sess.cw4_counters.get('crisis_level_spend_defer') is None
        assert 'must_spend_l3_prep_trigger' not in sess.cw4_counters


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
        sess = SimpleNamespace(cw4_counters={}, target_comp=get_comp(_COMP),
                               v3_intention=SimpleNamespace(
                                   locked_comp=_COMP))
        act = _decide(st, sess)
        # ladder 显影:L2 垫件缺 + L3 等级 cap(vl9 族硬闸)均零消费
        assert sess.cw4_counters.get('fuel_not_on_sale') == 1
        assert sess.cw4_counters.get('level_cap') == 1
        # 应-A 零静默:切分线让位发生 ⇒ yielded 分键在案
        assert sess.cw4_counters.get('must_spend_r1_account_yielded') == 1
        # 切分线生效:核算否决(g*/L 账)未拦 R1(域外同形帧会记该键)
        assert 'shop_r1_account_over_budget' not in sess.cw4_counters
        assert not isinstance(act, RefreshShop)   # 可负担性硬闸仍辖(金 51)
        assert isinstance(act, CloseShop)

    def test_r1_no_chaseable_guard_stays(self):
        """负向:合格集空守卫((ii) fail-closed)必花域内照旧——不因
        切分线放行刷新。帧 = 未锁线(k_members 口径:线成员全 2★ ⇒
        合格集空),R1 不需锁线,L3 被 lv9 cap 硬闸拦。"""
        km = list(line_members(get_comp(_COMP)))
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km)]
        st = GameState(gold=120, level=9, round_num=2, hp=60)
        st.level_readable = True
        st.plane = 2
        st.node_type = 'battle'
        st.shop = []
        st.bench = [_bc('瓦尔特', star=2, slot=1)]
        st.deployed = deployed
        st.refresh_probs = {}
        st.shop_refresh_cost = 2
        sess = SimpleNamespace(cw4_counters={}, target_comp=get_comp(_COMP))
        act = _decide(st, sess)
        assert not isinstance(act, RefreshShop)
        assert sess.cw4_counters.get(
            'shop_r1_no_chaseable_member') == 1

    def test_r1_budget_fail_liveness_key(self):
        """刷新臂 liveness 显影(52 轮 sim 设计输入②):域内刷新尝试被
        可负担性硬闸拦 ⇒ must_spend_r1_budget_fail 显式分键(禁恒零
        盲区,directed_refresh_game_cap_lock 绿灯掩盖恒零教训)。"""
        st, sess = _zone_frame(gold=51, level=9, cards=[])
        act = _decide(st, sess)
        assert not isinstance(act, RefreshShop)
        assert sess.cw4_counters.get('must_spend_r1_budget_fail') == 1


# ===== 实机档案帧单帧锁核(未锁线入域帧出口消费语义核)=====
# 设计出处:20号稿 §3.1-L2(未锁线 fail-closed 设计态)+ §3.5(L3 触发源)+
# ADR-0528(域内让位裁定)。
# 帧源 = .debug/temp/currency_war/replay/matches/ 两局档案的
# slices/decisions.jsonl 决策帧逐字段直读(帧定位符 = ts 字符串;测试值
# 内联,不依赖该文件存在)。
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

    def test_zone_verdicts_by_cap_resolved(self):
        """cap_resolved 实算判域(§2.1):g46/47/50 均未入域(50 等值
        不出,严格大于);51 入域。三帧策略均无 cap override ⇒ 缺省
        G_must=50——「g46/47 入域零消费」的入域判定不成立。"""
        sess = SimpleNamespace(cw4_cap_override=None)
        assert in_must_spend_zone(46, sess) is False
        assert in_must_spend_zone(47, sess) is False
        assert in_must_spend_zone(50, sess) is False
        assert in_must_spend_zone(51, sess) is True

    def test_g19_r5_g46_out_of_zone_zero_mustspend(self):
        """十九局 r5 帧(plane1 r5 gold46 supply,ts≈23:26,策略加油站,
        店空):域外帧 ⇒ 零消费是正确域外语义(非病灶)——无必花域出口
        动作、无 must_spend 分键。"""
        st = _arc_state(gold=46, hp=58, level=5, plane=1, round_num=5,
                        node_type='supply', xp_progress=(10, 20),
                        level_up_cost=4, deploy_cap=5)
        sess = SimpleNamespace(cw4_counters={}, target_comp=None,
                               v3_intention=None, cw4_cap_override=None)
        act = _decide(st, sess)
        assert not isinstance(act, (LevelUpShop, RefreshShop))
        assert not [k for k in sess.cw4_counters
                    if k.startswith('must_spend')]

    def test_g19_r6_g46_offer_consumes_via_t1_not_zone(self):
        """十九局 r6 offer 帧(ts 2026-09-05T23:24:50,gold46,店 5 张全
        non_line):域外消费走既有经济通道(t1 凑息卖),非必花域出口——
        分键面无 must_spend 触发。
        锁语义重推(合成素材拒入守卫批):档案原帧 bench=卡芙卡 1★ ∧
        deployed 卡芙卡 1★ 并存——该帧的凑息卖对象本身是 2/3 合成进度
        素材,与新守卫(拒因键 merge_material_guard,与部署侧同键)恰为
        同一病灶类;本锁语义 =「域外帧经 t1 消费且无 must_spend 分键」,
        不辖「素材可卖」——bench 单位改用非素材垫件(椒丘,deployed 无
        同名)保锁意图,素材拒入语义归 test_cw_merge_material_guard。"""
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
                               v3_intention=None, cw4_cap_override=None)
        act = _decide(st, sess)
        assert isinstance(act, SellBench)
        assert not [k for k in sess.cw4_counters
                    if k.startswith('must_spend')]

    def test_g19_inzone_unlocked_frames_consume_via_l3(self):
        """未锁线入域帧出口消费语义(33 跳精化口径核心锁):r7 帧
        (ts 2026-09-05T23:28:04,gold58)与 r9 帧(ts 23:33:14,gold63)
        ——入域 ∧ 未锁线(v3_intention null)⇒ L2 垫件臂 fail-closed 不
        触发(20 号稿 §3.1-L2 设计态,分键 absent),ladder 末位 L3 消费
        ⇒ LevelUpShop(auth_basis='m3_batch:must_spend')。十九局「入域
        零消费」形态(旧码形 faf09a64,第三触发源缺)在当前码形**不复现**
        ——闭合判读见本类 docstring 判读出处行。"""
        for gold, xp in ((58, (12, 20)), (63, (4, 40))):
            st = _arc_state(gold=gold, hp=47 if gold == 58 else 25,
                            level=5 if gold == 58 else 6, plane=1,
                            round_num=7 if gold == 58 else 9,
                            node_type='encounter' if gold == 58 else 'reward',
                            xp_progress=xp, level_up_cost=4,
                            refresh_probs={'1': 0.45, '2': 0.33, '3': 0.2,
                                           '4': 0.02, '5': 0.0}
                            if gold == 58 else None)
            sess = SimpleNamespace(cw4_counters={}, target_comp=None,
                                   v3_intention=None, cw4_cap_override=None)
            act = _decide(st, sess)
            assert isinstance(act, LevelUpShop), (gold, act)
            assert act.auth_basis == 'm3_batch:must_spend'
            assert 'must_spend_l2_trigger' not in sess.cw4_counters

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
        sess = SimpleNamespace(
            cw4_counters={}, target_comp=get_comp('希儿量子'),
            v3_intention=SimpleNamespace(phase='locked',
                                         locked_comp='希儿量子'),
            cw4_cap_override=None)
        assert in_must_spend_zone(50, sess) is False
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'm2_stockpile'
        assert (act.card.name or '') == '缇宝'

    def test_g20_p3r1_batch_intercept_scalars(self):
        """整买纪律档案标量锁(level 8 / xp 18/72 / 单击 4 金 ⇒ 整批
        56 金):gold 50 < 56 拦(复盘「56>50」实算复现),gold 80 ≥ 56
        放行——P48 判据本身按档案标量逐位正确。"""
        assert _crit_levelup.spend_unified(14, 50, 4) is False
        assert _crit_levelup.spend_unified(14, 80, 4) is True

    def test_g20_p3r1_prep_intercept_keyed_blindspot_pinned(self, monkeypatch):
        """备战栈 P3r1 帧拦截两道分键面(候选 1 观测盲区现状钉):
        ①真帧(hp14)第一道拦截 = 危机带停付让位,分键
        crisis_level_spend_defer 在案可归因;
        ②隔离停付让位(桩化 level_spend_blocked=False)后 spend_unified
        腿拒发 = **零分键静默穿过**(mandate M3 该腿无拒因键)——本锁钉
        现状盲区供观测面补齐批候选 1(域内 L3 整买拦截显影分键)对照,
        修掉盲区后本断言随语义更新,禁机械保绿。"""
        comp = get_comp('希儿量子')
        from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
            line_members,
        )
        km = tuple(line_members(comp))
        deployed = [_arc_bc({'char_id': c, 'star': 1, 'slot': i + 1,
                             'faction': '?', 'position_pref': 'back'})
                    for i, c in enumerate(
                        ('椒丘', '希儿', '爻光', '卡芙卡', '藿藿', '花火',
                         '刻律德菈', '符玄'))]
        bench = [_arc_bc({'char_id': '缇宝', 'star': 1, 'slot': 1,
                          'faction': '昼之半神', 'position_pref': 'back'})]
        frame = mandate.MandateFrame(
            gold=50, level=8, bench=bench, deployed=deployed,
            deploy_cap=8, node_type='battle', stop_flag=False,
            k_members=km, round_num=1)
        st = _arc_state(gold=50, hp=14, level=8, plane=3, round_num=1,
                        xp_progress=(18, 72), level_up_cost=4, deploy_cap=8)
        sess = SimpleNamespace(
            cw4_counters={}, target_comp=comp,
            v3_intention=SimpleNamespace(phase='locked',
                                         locked_comp='希儿量子'),
            cw4_cap_override=None)
        out = mandate.run_mandate(frame, sess, state=st)
        assert not [e for e in out if isinstance(e.action, LevelUp)]
        assert sess.cw4_counters.get('crisis_level_spend_defer') == 1
        # ② 盲区腿(原「钉锁现状」语义已随拒因分键批退役,锁重推):
        # 停付让位桩空后,整买拦截不再静默——l3_reject_batch_unaffordable
        # 分键在案(拒因不可辨盲区的治疗锚;xp 18/72、lv8 ⇒ 14击×4=56>50)。
        monkeypatch.setattr(_crit_levelup, 'level_spend_blocked',
                            lambda state, session, registry=None: False)
        sess2 = SimpleNamespace(
            cw4_counters={}, target_comp=comp,
            v3_intention=SimpleNamespace(phase='locked',
                                         locked_comp='希儿量子'),
            cw4_cap_override=None)
        out2 = mandate.run_mandate(frame, sess2, state=st)
        assert not [e for e in out2 if isinstance(e.action, LevelUp)]
        assert sess2.cw4_counters.get('l3_reject_batch_unaffordable') == 1
        assert not [k for k in sess2.cw4_counters
                    if k.startswith('must_spend')]

    def test_g20_p3r1_derived_inzone_consumes_r1_yielded(self):
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
        sess = SimpleNamespace(
            cw4_counters={}, target_comp=get_comp('希儿量子'),
            v3_intention=SimpleNamespace(phase='locked',
                                         locked_comp='希儿量子'),
            cw4_cap_override=None)
        act = _decide(st, sess)
        assert isinstance(act, RefreshShop)
        assert act.reason == 'must_spend_r1_yielded'
        assert sess.cw4_counters.get('must_spend_r1_account_yielded') == 1
        assert sess.cw4_counters.get('must_spend_l2_trigger') == 1
        assert sess.cw4_counters.get('fuel_filler_stall_fenced') == 4
        assert sess.cw4_counters.get(
            'fuel_filler_stall_fenced_l2_cap') == 2
