"""T-126 卖出通道排除仲裁·窗口段与发射登记(单帧锁;批 3)。

出处(锁纪律:新锁必引设计出处):
- ADR-0585(卖出通道排除仲裁单一源;§2 发射登记载体/LaunchCause 闭集
  映射/兜底池定义,§3 四出口生命周期与五键分键,§6 批 3 行);
- docs/develop/currency_war/proofs/math_proofs.md **P78** 行(P78-1 同
  visit 禁卖无条件下成立 / P78-2b 压库·垫保 τ=同轮 / P78-3 锁线定型
  不是账闭合事件 / P78-5 兜底豁免四条件 / P78-6 读端同源);
- docs/develop/currency_war/strategy-docs/11_shop_decisions.md §4.1
  (统一装配 as-built 语义);
- 双攻击报告案号:shop_sell W1(②(b) 买 ↔ funding 同 visit 卖回)/
  W3(F1 锁线清空 → 凑息卖回漏口)/ W5(②(b) prio1 无星过滤,本批只
  承接登记侧断言,发射侧门槛归买面批)。

批 3 辖域声明(方案 v3 §6.1):登记簿合一({名:(买因,轮)})、窗口段
活跃/过期、发射登记四出口 + 五键分键、类资格断言(W5 登记侧,含硬闸
合取)、funding 兜底豁免、projection 全资格视图。「任意买因类 × 任意
卖出通道」全矩阵测试随批 4 落地——本文件只落批 3 声明面的场景锁。

红证形态说明:红证均为「同构帧按修复前装配形态直调判据/装配」的机制
复现(与 test_cw_sell_arbitration 批 2 红证同款),非代码变异测试。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_card_identity import (
    TIER_TRANSITION,
    line_identity_tier,
    sell_hold_exclusion_names,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
)
from sr_od.application.currency_war.kernel.cw_state import (
    SELL_BENCH_CONVERT_REASONS,
    BenchChar,
    BuyCard,
    CloseShop,
    GameState,
    SellBench,
    ShopCard,
    sell_refund,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    mandate,
    sell_gate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    sell as crit_sell,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.vopt import (
    refund_full_star_ok,
)

# ===== 测试基建 =====

#: 非持有线外 1★ 燃料代表(注册表实名,cost=1;穿过判据全部物理谓词,
#: 红证由各锁自带直调证明)。
_FUEL = '青雀'
#: 静态持有两集代表:registry_core 档(希儿)/transition 档(丹恒·饮月、
#: 三月七),档位与费用由注册表现算(红证自证,非手抄)。
_CORE_HOLD = '希儿'
_TRANS_HOLD = '丹恒·饮月'
_TRANS_CHEAP = '三月七'


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _card(name: str, cost: int = 3, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _sess() -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = SimpleNamespace(
        name='测试线', core_chars=('目标件',), shared_chars=())
    state_of(s).v3_intention = IntentionState()
    return s


def _state(gold: int, bench: list[BenchChar], *,
           round_num: int = 3, node: str = 'battle') -> GameState:
    st = GameState(gold=gold, level=7, round_num=round_num, hp=60)
    st.plane = 2
    st.node_type = node
    st.bench = list(bench)
    st.deployed = []
    st.shop = []
    return st


def _registry(sess: StrategySession) -> dict:
    return state_of(sess).cw4_fuel_filler_stall_buys


# ===== 发射登记 API:闭集 / 分类视图 / 类资格断言(W5 登记侧)=====


class TestLaunchRegistry:
    """发射登记 API 锁(P78 §2.2 窗口段载体;ADR-0585 §2/§3)。"""

    def test_cause_closed_set_rejects_unknown(self):
        """登记闭集强制:LaunchCause 枚举外值拒收(方案 v3 §5.3 防复发
        双闸②;新买入臂必须先归入某因果类才合法)。"""
        with pytest.raises(ValueError):
            sell_gate.register_launch(_sess(), _FUEL, cause='speculate',
                                      round_num=3)

    def test_press_and_stall_views_are_disjoint(self):
        """单载体双视图:press 登记入窗口段排除面(active_window),
        垫保登记只入 T3 视图(stall_protect_active → defer 参数)——
        垫保在凑息是 defer 跳过、在 M4/funding 是降序放行(转化类,
        P78-5′ 四关系表「放行(在册语义保持)」),硬排除会杀死转化
        类放行;窗口排除面 = press(P78-1 无对价豁免)。两簿合一 =
        载体/生命周期合一(轮界共销账),非排除面合一。"""
        sess = _sess()
        assert sell_gate.register_launch(sess, _FUEL, cause='press',
                                         round_num=3)
        assert sell_gate.register_launch(sess, '垫件P', cause='stall_protect',
                                         round_num=3)
        assert sell_gate.active_window(sess, 3) == {_FUEL}
        assert sell_gate.stall_protect_active(sess, 3) == {'垫件P'}

    def test_legacy_int_value_tolerated_as_stall(self):
        """旧 T3 轮戳值(int)容读:归一为 stall_protect 类——值升级由
        写端自然完成,读端就地改值会破坏在飞会话的载体观测面。"""
        sess = _sess()
        _registry(sess).update({'垫件P': 3})
        assert sell_gate.stall_protect_active(sess, 3) == {'垫件P'}
        assert sell_gate.stall_protect_active(sess, 4) == frozenset()

    def test_hold_registration_qualification_conjunction(self):
        """类资格断言合取两腿(W5/V2-06):名字腿(名 ∈ 静态持有集)
        ∧ 硬闸腿(transition 层 = refund_full_star_ok;registry_core 层
        = 恒买无星闸,裁定410)。任一腿缺 = 断言失守:非持有名登记被拒
        (名字腿红),2★ 转线直出被拒(硬闸腿红——名字腿必过,红对存在
        性由合取保证,方案 v3 §5.1)。"""
        sess = _sess()
        ct = state_of(sess).cw4_counters
        # 硬闸腿红:2★ 转线直出(名字 ∈ TRANSITION_PACK ⊆ 静态持有集)
        assert _TRANS_HOLD in sell_hold_exclusion_names()
        assert line_identity_tier(_TRANS_HOLD) == TIER_TRANSITION
        assert not refund_full_star_ok(2, 2)
        assert not sell_gate.register_launch(sess, _TRANS_HOLD, cause='hold',
                                             round_num=3, star=2, cost=2)
        assert ct.get('launch_cause_mismatch') == 1
        assert _TRANS_HOLD not in _registry(sess)   # 拒登记(不拦发射归臂)
        # 名字腿红:线外普通燃料登记 hold 被拒
        assert not sell_gate.register_launch(sess, _FUEL, cause='hold',
                                             round_num=3, star=1, cost=1)
        assert ct.get('launch_cause_mismatch') == 2
        # 合取双过:1★ 转线件(refund_full_star_ok(1,2)=True)登记落账
        assert sell_gate.register_launch(sess, _TRANS_HOLD, cause='hold',
                                         round_num=3, star=1, cost=2)
        assert _registry(sess)[_TRANS_HOLD] == ('hold', 3)
        # registry_core 层恒买无星闸:2★ 核心件登记不受星闸拒(裁定410)
        assert refund_full_star_ok(2, 3) is False
        assert sell_gate.register_launch(sess, _CORE_HOLD, cause='hold',
                                         round_num=3, star=2, cost=3)
        assert _registry(sess)[_CORE_HOLD] == ('hold', 3)

    def test_launch_cause_mapping_closed_contract(self):
        """登记门:12 买入臂全映射 + 值域 ⊆ LaunchCause 闭集 + ev_buy→press
        (M4 修正补漏,方案 v3 §3.1;新买入臂未分类即登记 = 红,锁红时
        该登记的语义 = 把新臂补进映射表并过对抗审,非机械跟绿)。"""
        arms = ('m2_line_member', 'm2_locked_member', 'm2_stockpile',
                'm2_merge_completion', 'dominance_buy', 'm6_stockpile',
                'ev_buy', 'core_single_card_buy',
                'core_single_card_buy:unlocked', 'transition_component_buy',
                'dead_gold_press_buy', 'fuel_filler_stall',
                't3_unlocked_hemostat')
        assert set(sell_gate.LAUNCH_CAUSE_BY_ARM) == set(arms)
        assert set(sell_gate.LAUNCH_CAUSE_BY_ARM.values()) \
            <= sell_gate.LAUNCH_CAUSES
        assert sell_gate.launch_cause_of('ev_buy') == 'press'
        assert sell_gate.launch_cause_of('不存在的臂') is None


# ===== 窗口段:活跃 / 轮界过期 / 五键分键 =====


class TestWindowLifecycle:
    """窗口段生命周期锁(P78-2b τ=同轮;P78-3 轮界过期,W3 修法)。"""

    def test_active_only_when_round_matches(self):
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        assert _FUEL in sell_gate.sell_exclusions(
            sess, (), channel='funding', current_round=3)
        assert _FUEL in sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=3)
        assert _FUEL not in sell_gate.sell_exclusions(
            sess, (), channel='funding', current_round=4)
        # obligation/hold 类 τ=∞:不随轮界过期(P78-2a;行为面由身份段
        # 辖,此处锁登记账本身——轮进后 press 销账、hold 留簿)
        sell_gate.register_launch(sess, _TRANS_HOLD, cause='hold',
                                  round_num=3, star=1, cost=2)
        sell_gate.active_window(sess, 9)
        assert _FUEL not in _registry(sess)
        assert _registry(sess).get(_TRANS_HOLD) == ('hold', 3)

    def test_current_round_none_disables_window(self):
        """current_round=None ⇒ 窗口段失效(V2-09:INV 显式例外,方向 =
        放行向;轮不可得帧禁据缺读放大禁卖面,T3 既有语义继承)。"""
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        assert sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=None) \
            == sell_gate.identity_exclusions(sess, ())

    def test_round_expiry_counters_five_keys(self):
        """轮界过期分键:类诊断键(press_window_expired_round /
        t3_protect_expired_round,后者键名零断链)+ 账闭合键
        close_on_round(五键分键承载,方案 v3 §5.3/ADR-0585 §3)。"""
        sess = _sess()
        ct = state_of(sess).cw4_counters
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        sell_gate.register_launch(sess, '垫件P', cause='stall_protect',
                                  round_num=3)
        assert sell_gate.active_window(sess, 4) == frozenset()
        assert ct.get('press_window_expired_round') == 1
        assert ct.get('t3_protect_expired_round') == 1
        assert ct.get('close_on_round') == 2
        # 就地销账后同帧复读幂等(零重复计数)
        assert sell_gate.active_window(sess, 4) == frozenset()
        assert ct.get('close_on_round') == 2

    def test_locked_frame_never_clears_registry(self):
        """W3 反向锁:F1 锁线清空废除(P78-3:锁线定型不是任何买因类
        的账闭合事件)——锁线帧登记照常活跃、簿不清空;同 visit 卖回
        由登记轮==当前轮覆盖,过度禁卖上界 ≤1 轮有界可判读。"""
        sess = _sess()
        ist = state_of(sess).v3_intention
        ist.phase = 'locked'
        ist.locked_comp = '命运圣杯红A'
        ist.lock_plane = 2
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=2)
        assert _FUEL in sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=2)
        assert _FUEL in _registry(sess), \
            '锁线帧清空登记 = F1 错误语义回流(P78-3)'


class TestFourExits:
    """四出口生命周期锁(方案 v3 §3.1;①卖出销/②部署销/②′合成销/
    ③轮界销)+ 换线闭合(五键之 close_on_switch)。"""

    def test_exit1_sell_closes(self):
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        mandate.stall_buys_consume(sess, _FUEL)   # shim 同出口①
        assert _FUEL not in _registry(sess)
        assert state_of(sess).cw4_counters.get('close_on_sell') == 1

    def test_exit2_deploy_closes(self):
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        sell_gate.register_launch(sess, '垫件P', cause='stall_protect',
                                  round_num=3)
        n = sell_gate.prune_on_deploy(sess, {_FUEL})
        assert n == 1 and dict(_registry(sess)) == {
            '垫件P': ('stall_protect', 3)}
        assert state_of(sess).cw4_counters.get('close_on_deploy') == 1

    def test_exit2b_merge_closes_and_counts(self):
        """合成销(V2-05):同名 1★ 三张合成 2★,登记副本离场(件离场
        闭合);未接线窗口滞留 ≤1 轮由轮界销兜底(方案 v3 §3.1 申报)。"""
        sess = _sess()
        assert sell_gate.consume_on_merge(sess, _FUEL) == 0   # 空账 no-op
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        assert sell_gate.consume_on_merge(sess, _FUEL) == 1
        assert _FUEL not in _registry(sess)
        assert state_of(sess).cw4_counters.get('close_on_merge') == 1

    def test_switch_closes_obligation_only(self):
        """换线闭合(P78 §2.1「线账闭合」):义务类登记名离基座 ⇒ 销账
        + close_on_switch;hold 类不受辖(④件 = 候选终局线结构件,线账
        闭合不注销持有账,P78 §2.1「无时间闭合」)。"""
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='obligation',
                                  round_num=3)
        sell_gate.register_launch(sess, _TRANS_HOLD, cause='hold',
                                  round_num=3, star=1, cost=2)
        # 基座不含两登记名(义务账闭、持有账存)——读身份段即触发对账
        sell_gate.identity_exclusions(sess, ())
        ct = state_of(sess).cw4_counters
        assert ct.get('close_on_switch') == 1
        assert _FUEL not in _registry(sess)
        assert _registry(sess) == {_TRANS_HOLD: ('hold', 3)}
        # 幂等:复读不再计数
        sell_gate.identity_exclusions(sess, ())
        assert ct.get('close_on_switch') == 1


# ===== W1:同 visit 卖回全通道被禁(P78-1;shop_sell 报告 W1)=====


class TestW1SameVisitBan:
    """W1 锁:②(b)/dominance 等 press 类买入登记活跃帧(登记轮==
    当前轮),凑息/funding/M4 全通道资格面均不含该件——「拆窗口段时
    该件恰入卖出槽集」的病理形态由红证直调复现。"""

    def test_shop_funding_blocked_end_to_end(self):
        """端到端:press 活跃件在 bench + 缺员 + gold<need ⇒ funding
        主路径与兜底豁免均不可达(fallback 池减法①语义:非持有名不入
        静态持有集)⇒ CloseShop 收尾,零卖出发射。"""
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        act = decide_shop_action(_state(1, [_bc(_FUEL, slot=1)]), sess,
                                 SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, SellBench), \
            'W1:press 登记活跃件被同轮筹资卖出 = 同 visit 卖回未闭死'
        assert isinstance(act, CloseShop)

    def test_shop_funding_red_proof_identity_only(self):
        """红证:同构帧按批 2 形态(仅身份段,无窗口段)装配 ⇒ 该件恰
        入 funding 卖出槽集(凑息同面)——本锁绿由窗口段承载,非谓词
        自带拒。"""
        sess = _sess()
        bench = [_bc(_FUEL, slot=1)]
        excl = sell_gate.identity_exclusions(sess, ('目标件',))
        slots, key = crit_sell.funding_support_sell(
            1, 3, bench, ('目标件',), state=_state(1, bench),
            exclude_names=excl)
        assert key == '' and slots == [1], '红证失效:燃料件未穿过身份段外谓词'

    def test_entry_ev_funding_blocked(self):
        """消费位②(entry EV pass funding):press 活跃件不被 prep
        筹资卖出(方案 v3 §2.9 新格 A 三位同源;登记侧实装后差分闭死)。"""
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            SellBench as PrepSellBench,
        )
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=2)
        bench = [_bc(_FUEL, slot=1)]
        frame = mandate.MandateFrame(
            gold=1, level=5, bench=bench, deployed=[], deploy_cap=6,
            node_type=None, stop_flag=True, k_members=('目标件',),
            round_num=2)
        out = entry._criteria_pass(frame, sess, _state(1, bench, round_num=2),
                                   ('目标件',), k_switched=False,
                                   old_line_members=())
        assert not [e for e in out if isinstance(e.action, PrepSellBench)]

    def test_m4_channel_blocked_assembly_level(self):
        """M4 通道同禁(P78 INV 通道无关):press 活跃件不入腾席候选;
        红证 = 身份段-only 装配下该件恰入候选。"""
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        bench = [_bc(_FUEL, slot=1)]
        st = _state(30, bench)
        window = sell_gate.sell_exclusions(sess, ('目标件',),
                                           channel='m4_fuel', current_round=3)
        assert not mandate.fuel_sell_candidates(bench, ('目标件',),
                                                state=st,
                                                exclude_names=window)
        identity_only = sell_gate.identity_exclusions(sess, ('目标件',))
        cands = mandate.fuel_sell_candidates(bench, ('目标件',), state=st,
                                             exclude_names=identity_only)
        assert [b.char_id for b in cands] == [_FUEL], '红证失效'


# ===== 发射位登记写点:②(b) 三分 / dominance→press / 合成销检出 =====


class TestEmitRegistration:
    """发射位登记写点锁(方案 v3 §3.1;ADR-0585 §2 逐臂落位)。"""

    def test_dead_gold_press_buy_registers_by_prio(self):
        """②(b) prio2(燃料类)→ press:买入即登记(登记轮 = 当前轮,
        载体断言);旧 cw4_dead_gold_bought_names 载体退役并入统一簿。"""
        sess = _sess()
        st = _state(11, [], node='reward')
        st.shop = [_card('高价杂件', cost=5), _card(_FUEL, cost=1)]
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, BuyCard) and act.reason == 'dead_gold_press_buy'
        assert _registry(sess) == {_FUEL: ('press', 3)}

    def test_dominance_buy_registers_press(self):
        """dominance_buy → press 写点(P78 INV 逃逸格封死;gold>g* ∧
        停手态帧的压库买入同受窗口段辖,W1 同源)。"""
        sess = _sess()
        state_of(sess).target_comp = SimpleNamespace(
            name='测试线', core_chars=('目标件',), shared_chars=())
        st = _state(60, [], node='battle')
        st.shop = [_card(_FUEL, cost=1)]
        # 停手态 = 线全员在场(目标件在 bench)⇒ stop_flag=True
        st.bench = [_bc('目标件', slot=1), _bc(_FUEL, slot=2)]
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, BuyCard) and act.reason == 'dominance_buy'
        assert _registry(sess) == {_FUEL: ('press', 3)}

    def test_emit_merge_detection_closes_and_skips_registration(self):
        """合成销检出(V2-05):本笔 1★ 买入补齐同名 1★ 三张 ⇒ 旧登记
        销账(close_on_merge)且不为本笔开账(1★ 即刻合成离场,press 账
        资产对象不存在;接线位与理想位的差异申报见 shop._emit_buy)。"""
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        st = _state(11, [_bc(_FUEL, slot=1), _bc(_FUEL, slot=2)],
                    node='reward')
        st.shop = [_card(_FUEL, cost=1)]
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, BuyCard) and act.reason == 'dead_gold_press_buy'
        assert _FUEL not in _registry(sess), \
            '合成帧旧登记滞留 = 同轮再买同名 1★ 被过禁(V2-05 病理)'
        ct = state_of(sess).cw4_counters
        assert ct.get('close_on_merge') == 1
        assert ct.get('press_window_expired_round', 0) == 0   # 非轮界过期


# ===== W5:②(b) prio1 登记侧断言(2★ 转线直出拒登记不拦发射)=====


class TestW5RegistrationAssertion:
    """W5 登记侧锁(shop_sell 报告 W5;N1 划界 + V2-06 硬闸合取):
    ②(b) prio1 帧店内 2★ 转线直出卡 ⇒ 买入照常发射(买面门槛归臂自身
    批),登记被断言拒(launch_cause_mismatch 计数红 + 名不入簿)。"""

    def test_two_star_transition_buy_emits_but_registration_rejected(self):
        sess = _sess()
        st = _state(12, [], node='reward')
        st.shop = [_card(_TRANS_HOLD, cost=2, star=2)]
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        # 发射不拦(N1:登记侧断言不辖买入)
        assert isinstance(act, BuyCard) and act.reason == 'dead_gold_press_buy'
        ct = state_of(sess).cw4_counters
        assert ct.get('dead_gold_press_buy_hit') == 1
        # 登记侧:硬闸腿红(名字腿必过)→ launch_cause_mismatch + 拒登记
        assert ct.get('launch_cause_mismatch') == 1
        assert _TRANS_HOLD not in _registry(sess)

    def test_one_star_transition_registers_hold(self):
        """红证伴随(合取必要性):1★ 转线件硬闸腿过 ⇒ hold 登记落账
        ——缺硬闸合取时本格与 2★ 格同绿 = 锁恒绿形态(V2-06 红对补齐
        论证,方案 v3 §5.1)。"""
        sess = _sess()
        st = _state(12, [], node='reward')
        st.shop = [_card(_TRANS_HOLD, cost=2, star=1)]
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, BuyCard)
        assert _registry(sess) == {_TRANS_HOLD: ('hold', 3)}
        assert 'launch_cause_mismatch' not in state_of(sess).cw4_counters


# ===== funding 兜底豁免(P78-5 四条件)=====


class TestFundingHoldFallback:
    """兜底豁免锁(P78-5;ADR-0585 §2 兜底池定义):主路径(非持有资格
    面)空 ∧ 仍需筹资 ⇒ 兜底池单笔变现;两项减法与达成量化逐格反证。"""

    def test_shop_fallback_liquidates_hold_last_resort(self):
        """正格:bench 唯一 ③④ 持有件 + 缺员 + gold<need ⇒ 兜底卖出,
        reason 分键 funding_hold_liquidated(入同轮买卖检查豁免面,
        cw_state.SELL_BENCH_CONVERT_REASONS 三键)。"""
        sess = _sess()
        st = _state(0, [_bc(_CORE_HOLD, slot=1)])   # 希儿 cost=3 → 退 3
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, SellBench), \
            '兜底豁免未接线 = ③④件变现出口缺席(ADR-0585 中介窗口未收)'
        assert act.expect == _CORE_HOLD
        assert act.reason == 'funding_hold_liquidated'
        assert act.income == sell_refund(1, 3)
        assert state_of(sess).cw4_counters.get('funding_hold_liquidated') == 1
        assert act.reason in SELL_BENCH_CONVERT_REASONS

    def test_subtraction1_visit_bought_never_in_pool(self):
        """减法①(P78-5 条①/M1):本 visit 买入的持有件禁入兜底——否则
        豁免机制自己制造 P78-1 同 visit 违例(R1 面5 逃逸链)。"""
        sess = _sess()
        state_of(sess).cw4_visit_bought_names = [_CORE_HOLD]
        act = decide_shop_action(_state(0, [_bc(_CORE_HOLD, slot=1)]), sess,
                                 SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, SellBench)
        assert 'funding_hold_liquidated' not in state_of(sess).cw4_counters

    def test_subtraction2_obligation_base_never_in_pool(self):
        """减法②(P78-5 条②/M2):义务基座成员禁入兜底——兜底卖义务件
        → M2 重买换手,击穿义务基座自身(未锁态基座 = k_members)。"""
        sess = _sess()
        # k = ('目标件','希儿'):希儿在场(owned)⇒ 缺口只剩目标件;
        # 希儿 ∈ k = 基座 ⇒ 兜底池减法②排空 ⇒ 零卖出
        state_of(sess).target_comp = SimpleNamespace(
            name='测试线', core_chars=('目标件', '希儿'), shared_chars=())
        act = decide_shop_action(_state(0, [_bc(_CORE_HOLD, slot=1)]), sess,
                                 SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, SellBench)
        assert 'funding_hold_liquidated' not in state_of(sess).cw4_counters

    def test_quantification_refund_must_cover_gap(self):
        """达成量化(P78-5 条③,V3-04 机制授权条款):本笔退金 < need−gold
        ⇒ 不放行——期权损失(P01)已付而义务未达成 = 严格有害;同时封死
        逐帧级联清空兜底池路径。"""
        sess = _sess()
        # 三月七 cost=1 → 退 1 < 缺口 3(need 3 − gold 0)
        act = decide_shop_action(_state(0, [_bc(_TRANS_CHEAP, slot=1)]), sess,
                                 SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, SellBench)
        assert 'funding_hold_liquidated' not in state_of(sess).cw4_counters

    def test_main_path_nonempty_skips_fallback(self):
        """顺序豁免(P78-5 条③):非持有资格面未耗尽 ⇒ 兜底不评估。
        构造:垫保登记的燃料件在凑息侧被绝对跳过(defer)而凑息臂空手,
        funding 主路径经降序放行吃它(转化类)——主路径非空,fallback
        零评估。"""
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='stall_protect',
                                  round_num=3)
        st = _state(0, [_bc(_CORE_HOLD, slot=1), _bc(_FUEL, slot=2)])
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, SellBench)
        assert act.reason == 'funding_support_stall_convert'   # 主路径转化类
        assert 'funding_hold_liquidated' not in state_of(sess).cw4_counters

    def test_entry_ev_fallback_liquidates_prep_carrier(self):
        """消费位②(entry EV pass):兜底经 prep 载体发射(SellBench 无
        reason 字段 ⇒ 分键只落计数,与 T3 转化同口径申报)。"""
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            SellBench as PrepSellBench,
        )
        sess = SimpleNamespace()
        state_of(sess).cw4_counters = {}
        bench = [_bc(_TRANS_HOLD, slot=1)]   # cost=2 → 退 2 ≥ 缺口 3−1
        frame = mandate.MandateFrame(
            gold=1, level=5, bench=bench, deployed=[], deploy_cap=6,
            node_type=None, stop_flag=True, k_members=('目标件',),
            round_num=2)
        out = entry._criteria_pass(frame, sess, _state(1, bench, round_num=2),
                                   ('目标件',), k_switched=False,
                                   old_line_members=())
        sells = [e.action for e in out if isinstance(e.action, PrepSellBench)]
        assert [s.slot for s in sells] == [1]
        assert state_of(sess).cw4_counters.get('funding_hold_liquidated') == 1


# ===== P78-6:projection 视图 = interest 全资格面(含 T3 活跃集)=====


class TestProjectionFullFace:
    """读端同源锁(P78-6/M7):projection 视图 = 身份段 ∪ 窗口段 ∪
    T3 活跃集——投影漏 T3 则 liquid_refund 高估 → s_reserve 低估 →
    预留被吃(方向链方案 v3 §2.8)。"""

    def test_projection_equals_interest_face_union_t3(self):
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        sell_gate.register_launch(sess, '垫件P', cause='stall_protect',
                                  round_num=3)
        k = ('目标件',)
        identity = sell_gate.identity_exclusions(sess, k)
        window = sell_gate.active_window(sess, 3)
        t3 = sell_gate.stall_protect_active(sess, 3)
        want = frozenset(set(identity) | set(window) | set(t3))
        assert sell_gate.sell_exclusions(sess, k, channel='projection',
                                         current_round=3) == want
        assert sell_gate.sell_exclusions(sess, k, channel='interest',
                                         current_round=3) \
            == frozenset(set(identity) | set(window))

    def test_projection_red_proof_without_t3(self):
        """红证:投影视图漏 T3 活跃集(T3 垫件缺席排除面)⇒ 垫件被计入
        可变现投影 = liquid_refund 高估形态(修复前新格 B 残余)。"""
        sess = _sess()
        sell_gate.register_launch(sess, '垫件P', cause='stall_protect',
                                  round_num=3)
        k = ('目标件',)
        no_t3 = frozenset(
            set(sell_gate.identity_exclusions(sess, k))
            | set(sell_gate.active_window(sess, 3)))
        assert '垫件P' in sell_gate.sell_exclusions(
            sess, k, channel='projection', current_round=3)
        assert '垫件P' not in no_t3, '红证失效:无 T3 并入面仍含垫件'
