"""恒买腾席支单帧锁(T-115;ADR-0580 席满转化;方案 v2 §5/§10 新锁清单)。

出处(锁纪律:新锁必引设计出处):
- 用户裁定 T-115 规则③/④(ADR-0580):registry 核心卡恒买(不问锁线/
  息档/星级,只受席/金物理约束);席满帧卖 1 张燃料件释放 1 席(腾席),
  卖 1 张即止,下一决策迭代原臂原判据买入;
- `.debug/temp/currency_war/恒买腾席-方案v2.md`(A1 实码级三步/A4 双桶/
  §5.6 出口键闭集/§10 新锁清单①-⑨);
- math_proofs **P76 甲**(1★ 全额退往返净 0 ⇒ 腾席增量金成本 ≡ 0)、
  **P78-1**(同 visit 禁卖无条件下成立 ⇒ 本 visit 刚买件不被腾席卖);
- 判红检测器 = sim/checks/ledger.check_core_ruling_seat_violation
  (写端位出口键完备性;计数式轮级回退红则 = 收口复审残注①钉死)。

权限模型语义(§5.5):无合法 victim = 诚实停摆——骨架义务(M2 族)>
裁定族买,禁卖义务件凑恒买;*_no_fuel 显影非红(观察桶)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    locked_buy_membership,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.sim.checks import ledger, runner
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    sell_gate,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bs,
)

# ===== 测试基建(idiom 同 test_cw_core_single_card_channel)=====

_UNLOCK_COMP = '列车同行'      # k_members = core 4,missing∅ 可物理构造
_LOCK_COMP_SMALL = '命运圣杯红A'  # 锁定宽集仅 5 名(wide 集 = 阵营全集),
# 宽集可整体持有 ⇒ M2 缺员腾席(M4)跳过,锁线腿腾席支可达——锁定帧
# missing∅ 是锁线腿席满腾席的结构性可达域(宽集全持有;宽集 > 容量的
# 线该域移到 M4 义务腾席,权限序一致,方案 v2 §3.4/攻过未破⑦)。

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
           level: int = 7, plane: int = 2) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2, hp=60)
    st.plane = plane
    st.shop = shop_cards
    st.bench = bench if bench is not None else []
    # 非空板前置(T-32 空板止损守卫):守卫钉「待卖后 deployed 为空 ⇒
    # 拒卖」,腾席发射位直调环境须 ≥1 上场件,否则 fail-closed 拒帧
    # ——与被测语义无关的红按环境前置补齐,非跟绿。
    st.deployed = [_bc('板上件锚', slot=1)]
    return st


def _card(name: str, cost: int = 3, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _counters(sess) -> dict:
    return state_of(sess).cw4_counters or {}


def _core_buys(actions) -> list[BuyCard]:
    return [a for a in actions if isinstance(a, BuyCard)
            and (a.reason == 'core_single_card_buy'
                 or a.reason == 'core_single_card_buy:unlocked')]


def _unlocked_members_filled(fuel_names: list[str]) -> list[BenchChar]:
    """解锁帧 bench:core 4 全持有(missing∅ ⇒ M4 缺员腾席跳过)+ 线外件
    填满。fuel_names[0] 为腾席 victim(候选序 = bench 序)。"""
    comp = get_comp(_UNLOCK_COMP)
    members = list(comp.core_chars)
    rest = BENCH_CAPACITY - len(members) - len(fuel_names)
    fillers = [f'囤料{i}' for i in range(rest)]
    return [_bc(n, slot=i + 1)
            for i, n in enumerate(fuel_names + members + fillers)]


# ===== 新锁①:腾席支发射(三腿;expect=victim,reason='')============


class TestSeatVacateEmission:
    """腾席支发射锁(方案 v2 §10 新锁①):席满 + 合法燃料 victim ⇒
    SellBench(expect=victim,reason='' 缺省形态;income = 1★ 全额退)。
    发射契约与 M2 缺员/m2_stockpile 两既有腾席位逐字段一致(§5.2.3)。"""

    def test_unlocked_leg_vacates_seat(self):
        """未锁线恒买腿(病灶本体):席满帧金闸过 → 席门走腾席支,卖 1
        燃料件即止(单动作)。"""
        sess = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        bench = _unlocked_members_filled([_FUEL])
        st = _state(45, [_card('希儿', 3)], bench=bench)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act, SellBench)
        assert act.expect == _FUEL
        assert act.reason == ''
        assert act.bench_idx == 0
        ct = _counters(sess)
        assert ct.get('core_candidate_seen') == 1
        assert ct.get('core_unlocked_seat_swap') == 1

    def test_locked_leg_vacates_seat_when_wide_set_owned(self):
        """锁线支配支腿(A1 帧门席维下放后可达域):锁定宽集全持有
        (missing∅ ⇒ M2 缺员腾席不抢)席满帧 → 星→息→金三门过 → 席门
        腾席。victim = 首燃料候选(青雀)。"""
        ist = _locked_ist(_LOCK_COMP_SMALL)
        wide = sorted(locked_buy_membership(ist))
        bench = [_bc(_FUEL, slot=1)]
        bench += [_bc(n, slot=i + 2) for i, n in enumerate(wide)]
        bench += [_bc(f'囤料{j}', slot=j + 7) for j in range(3)]
        assert len(bench) == BENCH_CAPACITY
        sess = _sess(get_comp(_LOCK_COMP_SMALL), ist)
        st = _state(45, [_card('希儿', 3)], bench=bench)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act, SellBench)
        assert act.expect == _FUEL
        assert act.reason == ''
        ct = _counters(sess)
        assert ct.get('core_locked_seat_swap') == 1

    def test_transition_leg_vacates_seat(self):
        """④转线腿(候裁3 随批):席满帧 ④件在售 → 席门腾席。④腿时间
        辖域 = 未定型期(plane1;committed_from 唯一读端),帧构造同
        test_cw_locked_buy_membership_split.TestUnlockedFrameUnchanged
        的 ④放行帧形。"""
        sess = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        bench = _unlocked_members_filled([_FUEL])
        st = _state(45, [_card('丹恒·饮月', 3)], bench=bench, plane=1)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act, SellBench)
        assert act.expect == _FUEL
        assert act.reason == ''
        ct = _counters(sess)
        assert 'core_candidate_seen' not in ct   # 转线件非 registry 核,seen 不落
        assert ct.get('transition_seat_swap') == 1


# ===== 新锁②:转化闭环(卖后下一迭代原臂原判据买入)==================


class TestSeatVacateConversion:

    def test_buy_fires_next_iteration_with_unchanged_reason(self):
        """转化锁(新锁②):腾席卖 1 张即止;下一决策迭代席空,恒买腿
        原判据买入,买因不变(core_single_card_buy:unlocked,与席空帧
        直买路径同因)。金轨迹 = 卖先收 1★ 全额退(P76 甲:增量 0)。"""
        sess = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        bench = _unlocked_members_filled([_FUEL])
        st = _state(45, [_card('希儿', 3)], bench=bench)
        act1 = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act1, SellBench) and act1.expect == _FUEL
        # 下一迭代:victim 离席(引擎卖出应用),其余输入不变
        bench2 = [b for b in bench if (b.char_id or '') != _FUEL]
        for i, b in enumerate(bench2):
            b.slot = i + 1
        st2 = _state(45 + (act1.income or 0), [_card('希儿', 3)],
                     bench=bench2)
        act2 = shop.decide_shop_action(cw4_bs(st2, sess), sess, _cfg())
        buys = _core_buys([act2])
        assert len(buys) == 1 and buys[0].card.name == '希儿'
        assert buys[0].reason == 'core_single_card_buy:unlocked'
        assert _counters(sess).get('core_unlocked_buy_hit') == 1


# ===== 新锁③/⑥:诚实停摆与 for-else 尾键收窄 ========================


def _nonfuel_full_bench(comp_name: str) -> list[BenchChar]:
    """全 2★ 填充满栏 bench(core 全持有 ⇒ missing∅,M4 缺员腾席跳过;
    2★ 过 1★ 星过滤 ⇒ 燃料候选集结构性空,无 victim)。"""
    comp = get_comp(comp_name)
    names = list(comp.core_chars) \
        + [f'重装{i}' for i in range(BENCH_CAPACITY - len(comp.core_chars))]
    return [_bc(n, star=2, slot=i + 1) for i, n in enumerate(names)]


class TestHonestStallAndTailKey:

    def test_unlocked_no_fuel_honest_stall(self):
        """新锁③(未锁线形态):席满且无合法 victim(全 2★ 非燃料)
        ⇒ 不卖不买,core_unlocked_no_fuel 显影(观察桶,权限模型:禁卖
        义务/持有件凑恒买,§5.5)。"""
        sess = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        bench = _nonfuel_full_bench(_UNLOCK_COMP)
        st = _state(45, [_card('希儿', 3)], bench=bench)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not isinstance(act, SellBench)
        assert not _core_buys([act])
        ct = _counters(sess)
        assert ct.get('core_candidate_seen') == 1
        assert ct.get('core_unlocked_no_fuel') == 1

    def test_locked_star_fail_precedes_seat_gate_tail_key_fires(self):
        """新锁⑥ 后半(for-else 语义边界):席满帧唯一候补 2★ 直出
        ⇒ 星级门先于席门 continue,循环无 break 自然走完 ⇒ 尾键
        core_numeric_fail_closed 照落(席满不豁免走完帧);no_fuel 不落
        (未触席门)。与 test_bench_full_frame_gate_blocks(no_fuel break
        不落尾键)合起来钉死 for-else 收窄语义。"""
        ist = _locked_ist(_UNLOCK_COMP)
        bench = [_bc('三月七', slot=i + 1) for i in range(BENCH_CAPACITY)]
        sess = _sess(get_comp(_UNLOCK_COMP), ist)
        st = _state(45, [_card('希儿', 3, star=2)], bench=bench)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not _core_buys([act])
        ct = _counters(sess)
        assert ct.get('core_candidate_seen') == 1
        assert ct.get('core_numeric_fail_closed') == 1
        assert 'core_locked_no_fuel' not in ct


# ===== 新锁④:P78-1 本 visit 刚买件不被腾席卖 ========================


class TestSameVisitWindowBoundary:

    def test_press_active_fuel_not_vacated(self):
        """新锁④(P78-1 边界):本 visit 刚买的燃料(press 窗口段活跃)
        经 sell_exclusions 单一入口排除 ⇒ 腾席支无合法 victim ⇒ no_fuel
        诚实停摆,不绕开窗口(方案 v2 §5.5;P78-1 同 visit 禁卖)。"""
        sess = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        fills = [_FUEL] + [f'囤料{i}' for i in range(2, 6)]
        for n in fills:
            assert sell_gate.register_launch(sess, n, cause='press',
                                             round_num=2)
        bench = _unlocked_members_filled(fills)
        st = _state(45, [_card('希儿', 3)], bench=bench)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not isinstance(act, SellBench)
        assert not _core_buys([act])
        ct = _counters(sess)
        assert ct.get('core_unlocked_no_fuel') == 1


# ===== 新锁⑤:门序重排零漂移(席空帧逐位一致)========================


class TestGateReorderZeroDrift:

    def test_seat_free_frames_still_buy_all_three_legs(self):
        """新锁⑤(§5.3):金→席合取重排对席空帧零漂移——三腿席空帧
        照常直买,买因与重排前一致(④腿席空直买 + 未锁线恒买直买;
        锁线腿席空直买由 test_cw_core_single_card_channel.
        test_locked_frame_core_candidate_bought_as_free_option 钉)。"""
        # ④腿席空直买(重排前序 = 星→席→金,现 = 星→金→席;帧形同
        # TestUnlockedFrameUnchanged 的 ④放行帧:plane1 未定型期)
        sess = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        st = _state(30, [_card('丹恒·饮月', 2)], plane=1)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act, BuyCard)
        assert act.reason == 'transition_component_buy'
        assert _counters(sess).get('transition_component_buy_hit') == 1
        # 未锁线恒买席空直买(重排前序 = 席→金,现 = 金→席)
        sess2 = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        st2 = _state(45, [_card('希儿', 3)])
        act2 = shop.decide_shop_action(cw4_bs(st2, sess2), sess2, _cfg())
        buys = _core_buys([act2])
        assert len(buys) == 1
        assert buys[0].reason == 'core_single_card_buy:unlocked'


# ===== 新锁⑨:A4 金闸双桶(显影不动作;候裁4 卖前金读)================


class TestAffordableDoubleBucket:

    def test_unlocked_strict_when_no_fundable_victim(self):
        """新锁⑨ strict 形:金不足(g=2 < c=3)且无可筹 victim(全 2★
        席面,燃料候选空)⇒ *_unaffordable_strict,不卖不买。"""
        sess = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        bench = _nonfuel_full_bench(_UNLOCK_COMP)
        st = _state(2, [_card('希儿', 3)], bench=bench)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not isinstance(act, SellBench)
        assert not _core_buys([act])
        ct = _counters(sess)
        assert ct.get('core_unlocked_unaffordable_strict') == 1
        assert 'core_unlocked_unaffordable_fundable' not in ct

    def test_unlocked_fundable_when_victim_covers_gap(self):
        """新锁⑨ fundable 形(A4 判读面):金不足但 gold+refund(victim)
        ≥ cost(2+1 ≥ 3)⇒ *_unaffordable_fundable 显影;**C1 腿不卖不买**
        (无 seat_swap/无核心买——候裁4 默认案 = 恒买「金物理约束」按卖前
        金读,卖后可足也不卖筹;扩展案须 P78-5′ 通道对价段显式立项,本批
        禁夹带)。申报:本帧后续凑息回拉臂(t1_interest,既有行为,非本批
        面)可对同一燃料做筹资卖出,与 C1 腿双桶显影并存不互斥。"""
        sess = _sess(get_comp(_UNLOCK_COMP), IntentionState())
        bench = _unlocked_members_filled([_FUEL])
        st = _state(2, [_card('希儿', 3)], bench=bench)
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not _core_buys([act])
        ct = _counters(sess)
        assert ct.get('core_unlocked_unaffordable_fundable') == 1
        assert 'core_unlocked_unaffordable_strict' not in ct
        assert 'core_unlocked_seat_swap' not in ct   # C1 腿未腾席

    def test_locked_unaffordable_keys_t5_shadowed(self):
        """锁线腿金闸双桶近不可达申报(收口复审残扫在案):息门先于金门
        (星→息→金),金不足帧 loss_exact > 0 恒被息门 continue 截先
        (实测 gold=2/c=3 L=1),双桶键不可达;帧出口完备性由尾键承载
        (numeric_fail_closed 落)。本锁钉该申报形态,键集完备性无害。"""
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


# ===== 新锁⑦/⑧:判红检测器三锁 + 出口键完备性 =======================


def _row(counters: dict, plane: int = 1, round_num: int = 5) -> dict:
    return {'plane': plane, 'round_num': round_num,
            'obs': {'cw4_counters': dict(counters)}}


class TestRedDetector:

    def test_seen_without_exit_key_is_red(self):
        """新锁⑦a:seen 落键而出口键全空(静默违合成行)→ 红。"""
        rows = [_row({'core_candidate_seen': 1})]
        out = ledger.check_core_ruling_seat_violation(rows)
        assert len(out) == 1 and '静默违' in out[0]

    def test_no_fuel_row_bucket_not_red(self):
        """新锁⑦b:出口键 = no_fuel(诚实停摆桶)→ 桶非红,零输出。"""
        rows = [_row({'core_candidate_seen': 1,
                      'core_unlocked_no_fuel': 1})]
        assert ledger.check_core_ruling_seat_violation(rows) == []

    def test_buy_hit_row_zero_output(self):
        """新锁⑦c:出口键 = buy_hit → 零输出。"""
        rows = [_row({'core_candidate_seen': 1,
                      'core_unlocked_buy_hit': 1})]
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
        """批级披露面:seen 开火性 × 出口键分布 × 观察桶分键(v2 §11.2
        种子批验收线的数据源),violations 恒 0。"""
        ledgers = [[_row({'core_candidate_seen': 1,
                          'core_unlocked_seat_swap': 1})],
                   [_row({'core_candidate_seen': 1,
                          'core_locked_unaffordable_strict': 1})]]
        face = ledger.core_ruling_seat_bucket_disclosure(ledgers)
        assert face['violations'] == 0
        assert face['seen'] == 2 and face['games_with_seen'] == 2
        assert face['exits'] == {'core_unlocked_seat_swap': 1,
                                 'core_locked_unaffordable_strict': 1}
        assert face['observation_buckets'] == \
            {'core_locked_unaffordable_strict': 1}


class TestExitKeyCompleteness:

    def test_all_fired_keys_within_closed_set(self):
        """新锁⑧(镜像双向锁的生产侧半):三腿发射/停摆/双桶帧实测
        落键全部 ∈ 检测器镜像闭集 ledger._CORE_EXIT_KEYS——生产键集
        外溢(新键忘入镜像)即红。core_unlocked/core_locked/transition
        三族可发射键由本文件与通道锁逐一发射(锁线腿 unaffordable 双键
        息门截先近不可达,TestAffordableDoubleBucket 申报锁在案,镜像集
        仍按 §5.6 闭集全量收录)。"""
        fired: set[str] = set()

        def sweep(sess, st):
            state_of(sess).cw4_counters = {}
            shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
            fired.update(k for k in _counters(sess)
                         if k.startswith(('core_', 'transition_')))

        comp = get_comp(_UNLOCK_COMP)
        # 直买/腾席/停摆/双桶(未锁线)
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
        # ④腿直买/腾席(plane1 未定型期 = ④腿时间辖域)
        sweep(_sess(comp, IntentionState()),
              _state(30, [_card('丹恒·饮月', 2)], plane=1))
        sweep(_sess(comp, IntentionState()),
              _state(30, [_card('丹恒·饮月', 2)],
                     bench=_unlocked_members_filled([_FUEL]), plane=1))
        # 锁线腿:直买/星级弃帧/腾席/双桶(小宽集线)
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
        # 闭集 16 键无死键面:三腿各键在本仓锁面均有发射(结构申报,
        # 键级死键 = 静默显影回归,死键纪律)
        assert len(ledger._CORE_EXIT_KEYS) == 16


if __name__ == '__main__':
    import pytest
    pytest.main([__file__])
