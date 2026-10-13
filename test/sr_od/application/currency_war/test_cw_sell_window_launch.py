"""卖出通道排除仲裁·窗口段与发射登记(单帧锁;批 3)。

出处(锁纪律:新锁必引设计出处):
- ADR-0585(卖出通道排除仲裁单一源;§2 发射登记载体/LaunchCause 闭集
  映射/兜底池定义,§3 四出口生命周期与五键分键,§6 批 3 行);
- docs/develop/sr_od/application/currency_war/proofs/math_proofs.md **P78** 行(P78-1 同
  visit 禁卖无条件下成立 / P78-2b 压库·垫保 τ=同轮 / P78-3 锁线定型
  不是账闭合事件 / P78-5 兜底豁免四条件 / P78-6 读端同源);
- docs/develop/sr_od/application/currency_war/strategy-docs/11_shop_decisions.md §4.1
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

锁面组织(极限合并):闭集三锁(枚举拒/15 臂映射/press-stall 双视图)
并一;生命周期三锁(τ 同轮/锁线不清登记/四出口)表驱动并一;通道无关
阻断三锁(funding e2e/entry EV/M4)参数化并一;投影正证+红证并一;
资格合取与 fallback 发射独立保留。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bridge,
)
from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel.cw_card_identity import (
    TIER_TRANSITION,
    line_identity_tier,
    sell_hold_exclusion_names,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionCloseShopParam,
    CwActionSellBenchParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
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


def _bc(name: str, star: int = 1) -> BenchSlot:
    """容器占席条目(直构面)。"""
    return BenchSlot(kind='unit', unit=Unit(char_id=name, star=star))


def _sess() -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = SimpleNamespace(
        name='测试线', core_chars=('目标件',), shared_chars=())
    state_of(s).v3_intention = IntentionState()
    return s


def _state(gold: int, bench: list, *,
           round_num: int = 3, node: str = 'battle') -> dict:
    """发射窗口场景种子轴(返回 = 桥/feed 两配方公共 kwargs)。"""
    axes: dict = {'gold': gold, 'level': 7, 'round_num': round_num,
                  'hp': 60, 'plane': 2, 'node': node, 'bench': list(bench)}
    # 非空板前置(空板止损守卫):守卫钉「待卖后 deployed 为空 ⇒
    # 拒卖」(单一源 = sell_gate.empty_board_sell_blocked),卖出判据/
    # 发射位的直调环境须 ≥1 上场件,否则守卫 fail-closed 拒帧——与被
    # 测语义无关的红按环境前置补齐,非跟绿。
    axes['front_row'] = [Unit(char_id='板上件锚', star=1)]
    return axes


def _registry(sess: StrategySession) -> dict:
    return state_of(sess).cw4_fuel_filler_stall_buys


# ===== 发射登记 API:闭集 / 分类视图 / 类资格断言(W5 登记侧)=====


class TestLaunchRegistry:
    """发射登记 API 锁(P78 §2.2 窗口段载体;ADR-0585 §2/§3)。"""

    def test_launch_cause_closed_set(self):
        """闭集三锁并一:
        [枚举拒] LaunchCause 枚举外值拒收(方案 v3 §5.3 防复发
          双闸②;新买入臂必须先归入某因果类才合法);
        [15 臂映射] 15 买入臂全映射 + 值域 ⊆ LaunchCause 闭集 +
          ev_buy→press(M4 修正补漏,方案 v3 §3.1;新买入臂未分类即登记
          = 红,锁红时该登记的语义 = 把新臂补进映射表并过对抗审,非
          机械跟绿)。press_buy_deployable = 泄金阶梯档 1 新臂(溢余
          discretionary 面,因果类 press 同 M6/dominance;设计方案 §1.2
          档 1)。P86 重推:+hub_option_buy(乙臂枢纽期权,hold 类,出处
          = p86-proof-batch.md §3.2/§4.2;映射行随批登记)。P88 迁并腿
          (原锁线转型域 F4 闭集锁):收窄集 S_spec ⊆ 闭集 + 豁免 =
          闭集 ∖ S_spec 恰 13 键实名;
        [双视图] 单载体双视图:press 登记入窗口段排除面(active_window),
          垫保登记只入 T3 视图(stall_protect_active → defer 参数)——
          垫保在凑息是 defer 跳过、在 M4/funding 是降序放行(转化类,
          P78-5′ 四关系表「放行(在册语义保持)」),硬排除会杀死转化
          类放行;窗口排除面 = press(P78-1 无对价豁免)。两簿合一 =
          载体/生命周期合一(轮界共销账),非排除面合一。"""
        # [枚举拒]
        with pytest.raises(ValueError):
            sell_gate.register_launch(_sess(), _FUEL, cause='speculate',
                                      round_num=3)
        # [15 臂映射]
        arms = ('m2_line_member', 'm2_locked_member', 'm2_stockpile',
                'm2_merge_completion', 'dominance_buy', 'm6_stockpile',
                'press_buy_deployable',
                'ev_buy', 'core_single_card_buy',
                'core_single_card_buy:unlocked', 'transition_component_buy',
                'dead_gold_press_buy', 'fuel_filler_stall',
                't3_unlocked_hemostat', 'hub_option_buy')
        assert set(sell_gate.LAUNCH_CAUSE_BY_ARM) == set(arms)
        assert set(sell_gate.LAUNCH_CAUSE_BY_ARM.values()) \
            <= sell_gate.LAUNCH_CAUSES
        assert sell_gate.launch_cause_of('ev_buy') == 'press'
        assert sell_gate.launch_cause_of('hub_option_buy') == 'hold'
        assert sell_gate.launch_cause_of('不存在的臂') is None
        # P88 迁并腿:收窄集 ⊆ 闭集;豁免集恰 13 键——新买入臂入映射表
        # 即红(强制分类进收窄/豁免,防绕辖域前置的第五臂;对账符号 =
        # mandate.PRESS_NARROWED_ARMS)
        assert set(sell_gate.LAUNCH_CAUSE_BY_ARM) \
            >= mandate.PRESS_NARROWED_ARMS, \
            f'收窄集越出闭集: ' \
            f'{mandate.PRESS_NARROWED_ARMS - set(sell_gate.LAUNCH_CAUSE_BY_ARM)}'
        exempt = set(sell_gate.LAUNCH_CAUSE_BY_ARM) \
            - mandate.PRESS_NARROWED_ARMS
        must_exempt = {
            'm2_line_member', 'm2_locked_member', 'm2_stockpile',
            'm2_merge_completion', 'core_single_card_buy',
            'core_single_card_buy:unlocked', 'm6_stockpile',
            'press_buy_deployable', 'ev_buy', 'transition_component_buy',
            'dead_gold_press_buy', 'fuel_filler_stall',
            't3_unlocked_hemostat',
        }
        assert exempt == must_exempt, \
            f'豁免集漂移: 多={exempt - must_exempt} 少={must_exempt - exempt}'
        # [双视图]
        sess = _sess()
        assert sell_gate.register_launch(sess, _FUEL, cause='press',
                                         round_num=3)
        assert sell_gate.register_launch(sess, '垫件P', cause='stall_protect',
                                         round_num=3)
        assert sell_gate.active_window(sess, 3) == {_FUEL}
        assert sell_gate.stall_protect_active(sess, 3) == {'垫件P'}

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


# ===== 窗口段:活跃 / 轮界过期 / 五键分键 =====


class TestWindowLifecycle:
    """窗口段生命周期锁(P78-2b τ=同轮;P78-3 轮界过期,W3 修法;
    四出口方案 v3 §3.1)——三场景表驱动并一,场景间独立会话互不复用。"""

    def test_window_lifecycle_table(self):
        cases = (
            ('press_tau_same_round', self._case_press_tau_same_round),
            ('locked_frame_keeps_registry',
             self._case_locked_frame_keeps_registry),
            ('four_exits_close_and_count',
             self._case_four_exits_close_and_count),
        )
        for _name, case in cases:
            case()

    def _case_press_tau_same_round(self):
        """press τ=同轮:登记轮==当前轮才入排除面,轮进销账(hold 类
        τ=∞ 留簿,P78-2a;行为面由身份段辖,此处锁登记账本身——轮进后
        press 销账、hold 留簿)。current_round=None ⇒ 窗口段失效(V2-09:
        INV 显式例外,方向 = 放行向;轮不可得帧禁据缺读放大禁卖面,T3
        既有语义继承)。"""
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        assert _FUEL in sell_gate.sell_exclusions(
            sess, (), channel='funding', current_round=3)
        assert _FUEL in sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=3)
        assert _FUEL not in sell_gate.sell_exclusions(
            sess, (), channel='funding', current_round=4)
        # current_round=None ⇒ 窗口段失效(退化为身份段)
        assert sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=None) \
            == sell_gate.identity_exclusions(sess, ())
        sell_gate.register_launch(sess, _TRANS_HOLD, cause='hold',
                                  round_num=3, star=1, cost=2)
        sell_gate.active_window(sess, 9)
        assert _FUEL not in _registry(sess)
        assert _registry(sess).get(_TRANS_HOLD) == ('hold', 3)

    def _case_locked_frame_keeps_registry(self):
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

    def _case_four_exits_close_and_count(self):
        """四出口生命周期(方案 v3 §3.1):①卖出销(shim 同出口)/
        ②部署销(只销部署名,垫保账存)/②′合成销(V2-05;空账 no-op;
        未接线窗口滞留 ≤1 轮由轮界销兜底)/③换线闭合(P78 §2.1「线账
        闭合」:义务类登记名离基座 ⇒ 销账+close_on_switch,hold 类不受辖
        ——④件 = 候选终局线结构件,线账闭合不注销持有账「无时间闭合」;
        复读幂等零重复计数)。"""
        # ①卖出销
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        mandate.stall_buys_consume(sess, _FUEL)   # shim 同出口①
        assert _FUEL not in _registry(sess)
        assert state_of(sess).cw4_counters.get('close_on_sell') == 1
        # ②部署销
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        sell_gate.register_launch(sess, '垫件P', cause='stall_protect',
                                  round_num=3)
        n = sell_gate.prune_on_deploy(sess, {_FUEL})
        assert n == 1 and dict(_registry(sess)) == {
            '垫件P': ('stall_protect', 3)}
        assert state_of(sess).cw4_counters.get('close_on_deploy') == 1
        # ②′合成销
        sess = _sess()
        assert sell_gate.consume_on_merge(sess, _FUEL) == 0   # 空账 no-op
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        assert sell_gate.consume_on_merge(sess, _FUEL) == 1
        assert _FUEL not in _registry(sess)
        assert state_of(sess).cw4_counters.get('close_on_merge') == 1
        # ③换线闭合:基座不含两登记名(义务账闭、持有账存)——读身份段
        # 即触发对账
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='obligation',
                                  round_num=3)
        sell_gate.register_launch(sess, _TRANS_HOLD, cause='hold',
                                  round_num=3, star=1, cost=2)
        sell_gate.identity_exclusions(sess, ())
        ct = state_of(sess).cw4_counters
        assert ct.get('close_on_switch') == 1
        assert _FUEL not in _registry(sess)
        assert _registry(sess) == {_TRANS_HOLD: ('hold', 3)}
        # 幂等:复读不再计数
        sell_gate.identity_exclusions(sess, ())
        assert ct.get('close_on_switch') == 1


# ===== W1:同 visit 卖回全通道被禁(P78-1;shop_sell 报告 W1)=====


_W1_CHANNEL_CASES = ('funding-e2e', 'm4-candidates')


class TestW1SameVisitBan:
    """W1 锁:②(b)/dominance 等 press 类买入登记活跃帧(登记轮==
    当前轮),凑息/funding/M4 全通道资格面均不含该件——「拆窗口段时
    该件恰入卖出槽集」的病理形态由红证直调复现。三通道参数化并一
    (通道无关,P78 INV)。"""

    @pytest.mark.parametrize('channel_case', _W1_CHANNEL_CASES)
    def test_press_active_blocked_channel_agnostic(self, channel_case):
        _W1_CASES[channel_case](self)

    def _case_funding_e2e(self):
        """端到端:press 活跃件在 bench + 缺员 + gold<need ⇒ funding
        主路径与兜底豁免均不可达(fallback 池减法①语义:非持有名不入
        静态持有集)⇒ CwActionCloseShopParam 收尾,零卖出发射。红证:同构帧按批 2
        形态(仅身份段,无窗口段)装配 ⇒ 该件恰入 funding 卖出槽集
        (凑息同面)——本锁绿由窗口段承载,非谓词自带拒。"""
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        act = decide_shop_action(
            cw4_gs(sess, **_state(1, [_bc(_FUEL)])),
            sess, SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, CwActionSellBenchParam), \
            'W1:press 登记活跃件被同轮筹资卖出 = 同 visit 卖回未闭死'
        assert isinstance(act, CwActionCloseShopParam)
        # 红证:仅身份段装配下燃料件穿过身份段外谓词入卖出槽集
        # (P4 容器形:直接调用面 = 容器占席条目)
        bench = [_bc(_FUEL)]
        excl = sell_gate.identity_exclusions(sess, ('目标件',))
        slots, key = crit_sell.funding_support_sell(
            1, 3, bench, ('目标件',), state=_bridge(**_state(1, [_bc(_FUEL)])),
            exclude_names=excl)
        assert key == '' and slots == [0], \
            '红证失效:燃料件未穿过身份段外谓词(紧缩位键 0 基)'

    def _case_m4_candidates(self):
        """M4 通道同禁(P78 INV 通道无关):press 活跃件不入腾席候选;
        红证 = 身份段-only 装配下该件恰入候选。"""
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        bench = [_bc(_FUEL)]   # P4 容器形直构面
        st = _state(30, [_bc(_FUEL)])
        window = sell_gate.sell_exclusions(sess, ('目标件',),
                                           channel='m4_fuel', current_round=3)
        assert not mandate.fuel_sell_candidates(bench, ('目标件',),
                                                state=_bridge(**st),
                                                exclude_names=window)
        identity_only = sell_gate.identity_exclusions(sess, ('目标件',))
        cands = mandate.fuel_sell_candidates(bench, ('目标件',),
                                             state=_bridge(**st),
                                             exclude_names=identity_only)
        assert [mandate._slot_cid(b) for b in cands] == [_FUEL], '红证失效'


# (W1 'entry-ev' 消费位锁退役〔2026-10-12 迭代批 3.3〕:entry EV pass 随
#  备战九段全扫重写删除,备战域筹资发射位消亡——press 活跃件不被筹资
#  卖出的同面语义仍由本文件 funding-e2e(店内 decide_shop_action)与
#  评估器资格面测试〔test_cw_sell_candidates〕承载;店内筹资消费位
#  随 3.6 会话重排接续。)
_W1_CASES = {
    'funding-e2e': TestW1SameVisitBan._case_funding_e2e,
    'm4-candidates': TestW1SameVisitBan._case_m4_candidates,
}


# ===== funding 兜底豁免(P78-5 四条件)=====

# (原 TestFundingHoldFallback 店侧五锁随商店期筹资形态收缩退役:
#  店内兜底变现发射面删除,筹资形态 = 关店交回(锁 =
#  test_cw_shop_action_face_contraction::test_funding_form_closes_with_
#  defer_counter);原 entry 侧消费位锁〔TestFundingFallbackEntryConsumer,
#  经 entry._criteria_pass 发射〕随 2026-10-12 迭代批 3.3 备战九段全扫
#  重写退役——EV pass 删除,备战域兜底发射位消亡;兜底池定义单一源
#  〔sell_gate.funding_hold_fallback〕与达成量化语义由 3.6 会话内筹资
#  消费循环接线时新锁承载。)


# ===== P78-6:projection 视图 = interest 全资格面(含 T3 活跃集)=====


class TestProjectionFullFace:
    """读端同源锁(P78-6/M7):projection 视图 = 身份段 ∪ 窗口段 ∪
    T3 活跃集——投影漏 T3 则 liquid_refund 高估 → s_reserve 低估 →
    预留被吃(方向链方案 v3 §2.8)。正证+红证并一。"""

    def test_projection_face_union_t3_and_red_proof(self):
        """正证:projection = 身份段 ∪ 窗口段 ∪ T3 活跃集,interest =
        身份段 ∪ 窗口段(不含 T3)。红证(独立会话):投影视图漏 T3
        活跃集(T3 垫件缺席排除面)⇒ 垫件被计入可变现投影 =
        liquid_refund 高估形态(修复前新格 B 残余)。"""
        # 正证
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
        # 红证(独立会话)
        sess_red = _sess()
        sell_gate.register_launch(sess_red, '垫件P', cause='stall_protect',
                                  round_num=3)
        no_t3 = frozenset(
            set(sell_gate.identity_exclusions(sess_red, k))
            | set(sell_gate.active_window(sess_red, 3)))
        assert '垫件P' in sell_gate.sell_exclusions(
            sess_red, k, channel='projection', current_round=3)
        assert '垫件P' not in no_t3, '红证失效:无 T3 并入面仍含垫件'
