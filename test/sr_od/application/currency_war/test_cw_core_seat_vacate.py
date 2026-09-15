"""C1/④ 三腿席满交回支锁(T-271 收缩形态;前身 = T-115 恒买腾席发射锁)。

出处(锁纪律:新锁必引设计出处):
- 用户裁定 T-271(判例 = screens-actions-capability §5):卖备战收缩至
  备战期,商店期动作面 = 买牌/刷新/关店——三腿(未锁线恒买/锁线支配支
  /④转线)席满帧不再腾席卖,表达 = **关店交回**(腾位链:关店→备战卖
  →重开,节点内牌面持久,research/economy.md §2.1),重开后原臂原判据
  买入;
- 出口键闭集(sim 判红检测器判据,单一源 = sim/checks/ledger.py::
  _CORE_EXIT_KEYS):no_fuel 桶现辖席满停摆全形态(原「有/无 victim」
  子判随卖射退役并入);seen 帧必落 ≥1 出口键的红域判据由 no_fuel 桶
  承接,seat_swap 键随卖射退役不再发射(检测器镜像集不动,集内残留 =
  退役键,判读面按此口径);
- A4 金闸双桶(显影不动作)与判红检测器三锁沿用原锁面。

权限模型语义(§5.5 沿革):商店域不评估「该卖谁」——victim 资格面只剩
金闸双桶的遥测消费;腾位决策归备战期(策略侧)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bs,
)

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    locked_buy_membership,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    CloseShop,
    CwSimFrame,
    ShopCard,
)
from sr_od.application.currency_war.sim.checks import ledger, runner
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# ===== 测试基建(idiom 同 test_cw_core_single_card_channel)=====

_UNLOCK_COMP = '列车同行'      # k_members = core 4,missing∅ 可物理构造
_LOCK_COMP_SMALL = '命运圣杯红A'  # 锁定宽集仅 5 名(wide 集 = 阵营全集),
# 宽集可整体持有 ⇒ M2 缺员形态跳过,锁线腿席满交回支可达——锁定帧
# missing∅ 是锁线腿席满的结构性可达域。

_FUEL = '青雀'   # 注册表实名 1★ 1费线外燃料(同 test_cw_sell_window_launch)


def _cfg():
    return SimpleNamespace(ev_arm='full')


def _sess(target_comp, ist: IntentionState | None) -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = target_comp
    if ist is not None:
        state_of(s).v3_intention = ist
    return s


def _locked_ist(comp_name: str) -> IntentionState:
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = comp_name
    ist.lock_plane = 2
    return ist


def _state(gold: int, shop_cards: list[ShopCard],
           bench: list[BenchChar] | None = None,
           level: int = 7, plane: int = 2) -> CwSimFrame:
    st = CwSimFrame(gold=gold, level=level, round_num=2, hp=60)
    st.plane = plane
    st.shop = shop_cards
    st.bench = bench if bench is not None else []
    st.deployed = [_bc('板上件锚', slot=1)]
    return st


def _card(name: str, cost: int = 3, star: int = 1, x: int = 0) -> ShopCard:
    """x = 抽牌序 = 物理槽-1(桥装箱按 x 对槽,0..4 越界即丢卡——用户
    三态定长槽裁定 2026-09-13;本文件单卡帧恒 x=0)。"""
    return ShopCard(x=x, name=name, cost=cost, star=star)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _counters(sess) -> dict:
    return state_of(sess).cw4_counters or {}


def _core_buys(actions) -> list[BuyCard]:
    return [a for a in actions if isinstance(a, BuyCard)
            and (a.reason == 'core_single_card_buy'
                 or a.reason == 'core_single_card_buy:unlocked')]


def _unlocked_members_filled(fuel_names: list[str]) -> list[BenchChar]:
    """解锁帧 bench:core 4 全持有(missing∅ ⇒ 缺员形态跳过)+ 线外件
    填满。"""
    comp = get_comp(_UNLOCK_COMP)
    members = list(comp.core_chars)
    rest = BENCH_CAPACITY - len(members) - len(fuel_names)
    fillers = [f'囤料{i}' for i in range(rest)]
    return [_bc(n, slot=i + 1)
            for i, n in enumerate(fuel_names + members + fillers)]


# ===== 席满交回支(三腿;T-271 收缩形态)==============================


class TestCoreSeatFullClose:
    """席满交回锁(T-271):三腿席满帧 = CloseShop 交回 + {prefix}_
    no_fuel 出口键(现辖席满停摆全形态;seen 帧必落 ≥1 出口键的红域
    由本桶承接)。"""

    def test_unlocked_leg_full_bench_closes(self):
        sess = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        bench = _unlocked_members_filled([_FUEL])
        st = _state(45, [_card('希儿', 3)], bench=bench)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act, CloseShop)
        ct = _counters(sess)
        assert ct.get('core_candidate_seen') == 1
        assert ct.get('core_unlocked_no_fuel') == 1

    def test_locked_leg_full_bench_closes(self):
        """锁线支配支腿:锁定宽集全持有(missing∅)席满帧 → 星→息→金
        三门过 → 席门交回支。"""
        ist = _locked_ist(_LOCK_COMP_SMALL)
        wide = sorted(locked_buy_membership(ist))
        bench = [_bc(_FUEL, slot=1)]
        bench += [_bc(n, slot=i + 2) for i, n in enumerate(wide)]
        bench += [_bc(f'囤料{j}', slot=j + 7) for j in range(3)]
        assert len(bench) == BENCH_CAPACITY
        sess = _sess(get_comp(_LOCK_COMP_SMALL), ist)
        st = _state(45, [_card('希儿', 3)], bench=bench)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act, CloseShop)
        ct = _counters(sess)
        assert ct.get('core_locked_no_fuel') == 1

    def test_transition_leg_full_bench_closes(self):
        """④转线腿:席满帧 ④件在售(未定型期 plane1)→ 席门交回支。"""
        sess = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        bench = _unlocked_members_filled([_FUEL])
        st = _state(45, [_card('丹恒·饮月', 3)], bench=bench, plane=1)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act, CloseShop)
        ct = _counters(sess)
        assert 'core_candidate_seen' not in ct   # 转线件非 registry 核,seen 不落
        assert ct.get('transition_no_fuel') == 1


# ===== 腾位链(交回→备战腾席→重开→原臂原判据买入)====================


class TestVacateChainReopen:
    def test_buy_fires_next_visit_after_prep_vacate(self):
        """链锁(收缩形态):席满帧关店交回 → 备战腾席(victim 离席,
        其余输入不变)→ 重开重判,恒买腿原判据买入,买因不变
        (core_single_card_buy:unlocked,与席空帧直买路径同因)。"""
        sess = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        bench = _unlocked_members_filled([_FUEL])
        st = _state(45, [_card('希儿', 3)], bench=bench)
        act1 = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act1, CloseShop)
        # 备战腾席:victim 离席(语义级建模,与收缩文件牌面持久锁同型)
        bench2 = [b for b in bench if (b.char_id or '') != _FUEL]
        for i, b in enumerate(bench2):
            b.slot = i + 1
        st2 = _state(45, [_card('希儿', 3)], bench=bench2)
        act2 = shop.decide_shop_action(cw4_bs(st2, sess), sess, _cfg())
        buys = _core_buys([act2])
        assert len(buys) == 1 and buys[0].card.name == '希儿'
        assert buys[0].reason == 'core_single_card_buy:unlocked'
        assert _counters(sess).get('core_unlocked_buy_hit') == 1


# ===== 尾键收窄(for-else 语义边界)===================================


def _nonfuel_full_bench(comp_name: str) -> list[BenchChar]:
    """全 2★ 填充满栏 bench(core 全持有 ⇒ missing∅;2★ 过 1★ 星过滤
    ⇒ 金闸双桶 victim 面空)。"""
    comp = get_comp(comp_name)
    names = list(comp.core_chars) \
        + [f'重装{i}' for i in range(BENCH_CAPACITY - len(comp.core_chars))]
    return [_bc(n, star=2, slot=i + 1) for i, n in enumerate(names)]


class TestTailKeyBoundary:

    def test_locked_star_fail_precedes_seat_gate_tail_key_fires(self):
        """for-else 语义边界:席满帧唯一候补 2★ 直出 ⇒ 星级门先于席门
        continue,循环无 break/return 自然走完 ⇒ 尾键
        core_numeric_fail_closed 照落;no_fuel 不落(未触席门)。与席满
        交回帧(return 跳过尾键)合起来钉死收窄语义。帧 = 小宽集线全
        持有(missing∅,不触 M2 缺员交回形态;大宽集线缺员结构性在,
        该域现归 M2 席满交回形态前置承接)。"""
        ist = _locked_ist(_LOCK_COMP_SMALL)
        wide = sorted(locked_buy_membership(ist))
        bench = [_bc(n, star=2, slot=i + 1) for i, n in enumerate(wide)]
        bench += [_bc(f'重装{i}', star=2, slot=i + 6) for i in range(4)]
        sess = _sess(get_comp(_LOCK_COMP_SMALL), ist)
        st = _state(45, [_card('希儿', 3, star=2)], bench=bench)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not _core_buys([act])
        ct = _counters(sess)
        assert ct.get('core_candidate_seen') == 1
        assert ct.get('core_numeric_fail_closed') == 1
        assert 'core_locked_no_fuel' not in ct


# ===== 门序零漂移(席空帧逐位一致)====================================


class TestGateReorderZeroDrift:

    def test_seat_free_frames_still_buy_all_three_legs(self):
        """席空帧零漂移:三腿席空帧照常直买,买因不变(④腿席空直买 +
        未锁线恒买直买;锁线腿席空直买由
        test_cw_core_single_card_channel.
        test_locked_frame_core_candidate_bought_as_free_option 钉)。"""
        # ④腿席空直买(plane1 未定型期)
        sess = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        st = _state(30, [_card('丹恒·饮月', 2)], plane=1)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act, BuyCard)
        assert act.reason == 'transition_component_buy'
        assert _counters(sess).get('transition_component_buy_hit') == 1
        # 未锁线恒买席空直买
        sess2 = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        st2 = _state(45, [_card('希儿', 3)])
        act2 = shop.decide_shop_action(cw4_bs(st2, sess2), sess2, _cfg())
        buys = _core_buys([act2])
        assert len(buys) == 1
        assert buys[0].reason == 'core_single_card_buy:unlocked'


# ===== A4 金闸双桶(显影不动作)=======================================


class TestAffordableDoubleBucket:

    def test_unlocked_strict_when_no_fundable_victim(self):
        """strict 形:金不足(g=2 < c=3)且无可筹 victim(全 2★ 席面,
        victim 面空)⇒ *_unaffordable_strict,不买。"""
        sess = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        bench = _nonfuel_full_bench(_UNLOCK_COMP)
        st = _state(2, [_card('希儿', 3)], bench=bench)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not _core_buys([act])
        ct = _counters(sess)
        assert ct.get('core_unlocked_unaffordable_strict') == 1
        assert 'core_unlocked_unaffordable_fundable' not in ct

    def test_unlocked_fundable_when_victim_covers_gap(self):
        """fundable 形(A4 判读面):金不足但 gold+refund(victim)
        ≥ cost(2+1 ≥ 3)⇒ *_unaffordable_fundable 显影;C1 腿不买
        (恒买「金物理约束」按现读金,卖后可足也不在店内卖筹——筹资
        形态 = 关店交回备战)。"""
        sess = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        bench = _unlocked_members_filled([_FUEL])
        st = _state(2, [_card('希儿', 3)], bench=bench)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not _core_buys([act])
        ct = _counters(sess)
        assert ct.get('core_unlocked_unaffordable_fundable') == 1
        assert 'core_unlocked_unaffordable_strict' not in ct

    def test_locked_unaffordable_keys_t5_shadowed(self):
        """锁线腿金闸双桶近不可达申报(收口复审残扫在案):息门先于金门
        (星→息→金),金不足帧 loss_exact > 0 恒被息门 continue 截先
        (实测 gold=2/c=3 L=1),双桶键不可达;帧出口完备性由尾键承载
        (numeric_fail_closed 落)。"""
        ist = _locked_ist(_LOCK_COMP_SMALL)
        wide = sorted(locked_buy_membership(ist))
        bench = [_bc(n, star=2, slot=i + 1) for i, n in enumerate(wide)]
        bench += [_bc(f'重装{i}', star=2, slot=i + 6) for i in range(4)]
        sess = _sess(get_comp(_LOCK_COMP_SMALL), ist)
        st = _state(2, [_card('希儿', 3)], bench=bench)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not _core_buys([act])
        ct = _counters(sess)
        assert ct.get('core_candidate_seen') == 1
        assert 'core_locked_unaffordable_strict' not in ct
        assert 'core_locked_unaffordable_fundable' not in ct
        assert ct.get('core_numeric_fail_closed') == 1   # 出口键由尾键承载


# ===== 判红检测器三锁 + 出口键完备性 =================================


def _row(counters: dict, plane: int = 1, round_num: int = 5) -> dict:
    return {'plane': plane, 'round_num': round_num,
            'obs': {'cw4_counters': dict(counters)}}


class TestRedDetector:

    def test_seen_without_exit_key_is_red(self):
        """seen 落键而出口键全空(静默违合成行)→ 红。"""
        rows = [_row({'core_candidate_seen': 1})]
        out = ledger.check_core_ruling_seat_violation(rows)
        assert len(out) == 1 and '静默违' in out[0]

    @pytest.mark.parametrize('exit_key', [
        'core_unlocked_no_fuel', 'core_unlocked_buy_hit'],
        ids=['no-fuel-honest-stall', 'buy-hit'])
    def test_exit_key_row_bucket_not_red(self, exit_key):
        """合法出口键(no_fuel 席满停摆桶 / buy_hit 买中)→ 桶非红,
        零输出。(原两条独立测试同行为变体,参数化合并。)"""
        rows = [_row({'core_candidate_seen': 1, exit_key: 1})]
        assert ledger.check_core_ruling_seat_violation(rows) == []

    def test_counting_form_mixed_frames(self):
        """残注①计数式红则:Σseen > Σ出口键 → 红(本轮存在零出口帧);
        Σ出口 ≥ Σseen → 不假红。"""
        red = ledger.check_core_ruling_seat_violation(
            [_row({'core_candidate_seen': 2, 'core_unlocked_buy_hit': 1})])
        assert len(red) == 1
        green = ledger.check_core_ruling_seat_violation(
            [_row({'core_candidate_seen': 2,
                   'core_unlocked_buy_hit': 1,
                   'core_locked_no_fuel': 1})])
        assert green == []

    def test_rows_without_carrier_skipped(self):
        """无 obs.cw4_counters 载体(旧账本)行 = 无判红载体,跳过不报
        (ADR-0589 无键回退先例)。"""
        assert ledger.check_core_ruling_seat_violation(
            [{'plane': 1, 'round_num': 3}]) == []
        assert ledger.check_core_ruling_seat_violation(
            [_row({}, plane=2)]) == []

    def test_registered_in_batch_checks(self):
        assert 'core_ruling_seat_violation' in runner._BATCH_CHECKS

    def test_batch_disclosure_face(self):
        """批级披露面:seen 开火性 × 出口键分布 × 观察桶分键,violations
        恒 0。(seat_swap 键随卖射退役不再发射,镜像集内残留按退役键
        判读;披露面以仍可发射的键构造。)"""
        ledgers = [[_row({'core_candidate_seen': 1,
                          'core_unlocked_no_fuel': 1})],
                   [_row({'core_candidate_seen': 1,
                          'core_locked_unaffordable_strict': 1})]]
        face = ledger.core_ruling_seat_bucket_disclosure(ledgers)
        assert face['violations'] == 0
        assert face['seen'] == 2 and face['games_with_seen'] == 2
        assert face['exits'] == {'core_unlocked_no_fuel': 1,
                                 'core_locked_unaffordable_strict': 1}
        assert face['observation_buckets'] == \
            {'core_unlocked_no_fuel': 1,
             'core_locked_unaffordable_strict': 1}


class TestExitKeyCompleteness:
    def test_all_fired_keys_within_closed_set(self):
        """镜像双向锁的生产侧半:三腿交回/直买/双桶帧实测落键全部 ∈
        检测器镜像闭集 ledger._CORE_EXIT_KEYS——生产键集外溢(新键忘
        入镜像)即红。(原「闭集 16 键无死键面」申报随卖射退役废止:
        seat_swap 三键不再有生产发射位,镜像集按退役键保留。)"""
        fired: set[str] = set()

        def sweep(sess, st):
            state_of(sess).cw4_counters = {}
            shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
            fired.update(k for k in _counters(sess)
                         if k.startswith(('core_', 'transition_')))

        comp = get_comp(_UNLOCK_COMP)
        # 直买/席满交回/双桶(未锁线)
        sweep(_sess(comp, IntentionState()), _state(45, [_card('希儿', 3)]))
        sweep(_sess(comp, IntentionState()),
              _state(45, [_card('希儿', 3)],
                     bench=_unlocked_members_filled([_FUEL])))
        sweep(_sess(comp, IntentionState()),
              _state(45, [_card('希儿', 3)],
                     bench=_nonfuel_full_bench(_UNLOCK_COMP)))
        sweep(_sess(comp, IntentionState()),
              _state(2, [_card('希儿', 3)],
                     bench=_nonfuel_full_bench(_UNLOCK_COMP)))
        sweep(_sess(comp, IntentionState()),
              _state(2, [_card('希儿', 3)],
                     bench=_unlocked_members_filled([_FUEL])))
        # ④腿直买/席满交回(plane1 未定型期 = ④腿时间辖域)
        sweep(_sess(comp, IntentionState()),
              _state(30, [_card('丹恒·饮月', 2)], plane=1))
        sweep(_sess(comp, IntentionState()),
              _state(30, [_card('丹恒·饮月', 2)],
                     bench=_unlocked_members_filled([_FUEL]), plane=1))
        # 锁线腿:直买/星级弃帧/席满交回/双桶(小宽集线)
        sweep(_sess(get_comp(_LOCK_COMP_SMALL), _locked_ist(_LOCK_COMP_SMALL)),
              _state(45, [_card('希儿', 3)]))
        sweep(_sess(get_comp(_LOCK_COMP_SMALL), _locked_ist(_LOCK_COMP_SMALL)),
              _state(45, [_card('希儿', 3, star=2)]))
        ist = _locked_ist(_LOCK_COMP_SMALL)
        wide = sorted(locked_buy_membership(ist))
        bench_locked = [_bc(_FUEL, slot=1)]
        bench_locked += [_bc(n, slot=i + 2) for i, n in enumerate(wide)]
        bench_locked += [_bc(f'囤料{j}', slot=j + 7) for j in range(3)]
        sweep(_sess(get_comp(_LOCK_COMP_SMALL), _locked_ist(_LOCK_COMP_SMALL)),
              _state(45, [_card('希儿', 3)], bench=bench_locked))
        sweep(_sess(get_comp(_LOCK_COMP_SMALL), _locked_ist(_LOCK_COMP_SMALL)),
              _state(2, [_card('希儿', 3)],
                     bench=[_bc(n, star=2, slot=i + 1)
                            for i, n in enumerate(wide)]
                     + [_bc(f'重装{i}', star=2, slot=i + 6)
                        for i in range(4)]))
        sweep(_sess(get_comp(_LOCK_COMP_SMALL), _locked_ist(_LOCK_COMP_SMALL)),
              _state(2, [_card('希儿', 3)], bench=bench_locked))
        # 数值域尾键(星级/息档弃帧)
        sweep(_sess(comp, _locked_ist(_UNLOCK_COMP)),
              _state(50, [_card('希儿', 3)],
                     bench=[_bc('三月七', slot=i + 1)
                            for i in range(4)]))
        assert fired, '扫帧未落任何出口键(输入死)'
        stray = fired - set(ledger._CORE_EXIT_KEYS) - {'core_candidate_seen'}
        assert not stray, f'生产落键超出检测器镜像闭集: {sorted(stray)}'


if __name__ == '__main__':
    import pytest
    pytest.main([__file__])
