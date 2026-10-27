"""卖出通道排除仲裁·窗口段与发射登记(单帧测试;批 3)。

出处(测试纪律:新增测试必引设计出处):
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
卖出通道」全矩阵测试随批 4 落地——本文件只落批 3 声明面的场景测试。

红证形态说明:红证均为「同构帧按修复前装配形态直调判据/装配」的机制
复现(与 test_cw_sell_arbitration 批 2 红证同款),非代码变异测试。

测试面组织(极限合并):闭集三个测试(枚举拒/15 臂映射/press-stall 双视图)
并一;生命周期三个测试(τ 同轮/锁线不清登记/四出口)表驱动并一;通道无关
阻断三个测试(funding e2e/M4)参数化并一;投影正证+红证并一;
资格合取与 fallback 发射独立保留。

并段(**轮内新鲜度账容器宿主 + 商店访问账本死字段退役**,原
test_cw_round_fresh_buys_host 并入;同 visit 卖回防线第二载体,逐字段
处置表 #18/#19):轮内新鲜度账宿主 = 容器 Field ``GameState.round_
fresh_buys``(record_fresh_buy 写 → fresh_buys_of/fresh_buys_sell_face
读同一容器,写读单口 sim/live 同口;相位失配 = 跨轮整体作废、读取零销
账;值形状 names = list);商店访问账本的四死基座字段(期望态残留,
全为写端无读端)不再在场——对象面运行时检查,非源码扫描。(原卖出
落地测试随商店域 SellBenchOp 退役移除:动作 op 重组批③,备战域卖出由
CwActionSellBenchOp 承接。)
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bridge,
)
from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel.cw_comps import (
    CORE_SINGLE_CARD_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    fresh_buys_of,
    fresh_buys_sell_face,
    record_fresh_buy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    ChannelSig,
    GameState,
    NodeKey,
    Unit,
    game_state_of,
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
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    ShopVisitLedger,
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
from sr_od.application.currency_war.strategies.impl.mandate_v1.protection import (
    four_system_members,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.vopt import (
    refund_full_star_ok,
)

# ===== 测试基建 =====

#: 非持有线外 1★ 燃料代表(注册表实名,cost=1;非保护集非核心 = 新身份
#: 口径下的真线外件,穿过判据全部物理谓词,红证由各测试自带直调证明)。
_FUEL = '阿格莱雅'
#: 登记资格面代表:registry_core 档(希儿)/保护集档(丹恒·饮月,
#: 仙舟系四体系成员),档位与费用由注册表现算(红证自证,非手抄)。
_CORE_HOLD = '希儿'
_TRANS_HOLD = '丹恒·饮月'


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
    """发射登记 API 测试(P78 §2.2 窗口段载体;ADR-0585 §2/§3)。"""

    def test_launch_cause_closed_set(self):
        """闭集三个测试并一:
        [枚举拒] LaunchCause 枚举外值拒收(方案 v3 §5.3 防复发
          双闸②;新买入臂必须先归入某因果类才合法);
        [15 臂映射] 15 买入臂全映射 + 值域 ⊆ LaunchCause 闭集 +
          ev_buy→press(M4 修正补漏,方案 v3 §3.1;新买入臂未分类即登记
          = 红,测试红时该登记的语义 = 把新臂补进映射表并过对抗审,非
          机械跟绿)。press_buy_deployable = 泄金阶梯档 1 新臂(溢余
          discretionary 面,因果类 press 同 M6/dominance;设计方案 §1.2
          档 1)。P86 重推:+hub_option_buy(乙臂枢纽期权,hold 类,出处
          = p86-proof-batch.md §3.2/§4.2;映射行随批登记)。P88 迁并腿
          (原锁线转型域 F4 闭集测试):收窄集 S_spec ⊆ 闭集 + 豁免 =
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
                'core_single_card_buy:unlocked', 'protection_hoard',
                'dead_gold_press_buy', 'fuel_filler_stall',
                't3_unlocked_hemostat', 'scene_plugin_buy')
        assert set(sell_gate.LAUNCH_CAUSE_BY_ARM) == set(arms)
        assert set(sell_gate.LAUNCH_CAUSE_BY_ARM.values()) \
            <= sell_gate.LAUNCH_CAUSES
        assert sell_gate.launch_cause_of('ev_buy') == 'press'
        assert sell_gate.launch_cause_of('scene_plugin_buy') == 'press'
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
            'press_buy_deployable', 'ev_buy', 'protection_hoard',
            'dead_gold_press_buy', 'fuel_filler_stall',
            't3_unlocked_hemostat', 'scene_plugin_buy',
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
        """类资格断言合取两腿(W5/V2-06;统一保护集迭代 design.md §2.3
        hold 腿行 + §2.4 档位表迁移后语义):名字腿(名 ∈ 保护集 ∪
        registry 核心——hold 类买入 = C1 核心 + protection_hoard 两类的
        登记资格面)∧ 硬闸腿(保护档 = refund_full_star_ok 1★ 全额退,
        与囤臂同门;core 档 = 恒买无星闸)。任一腿缺 = 断言失守:非保护
        非核心名登记被拒(名字腿红),2★ 保护件直出被拒(硬闸腿红——
        名字腿必过,红对存在性由合取保证)。"""
        sess = _sess()
        ct = state_of(sess).cw4_counters
        # 硬闸腿红:2★ 保护件直出(名 ∈ 保护集四体系,protection 档闸拒)
        assert _TRANS_HOLD in four_system_members()
        assert not refund_full_star_ok(2, 2)
        assert not sell_gate.register_launch(sess, _TRANS_HOLD, cause='hold',
                                             round_num=3, star=2, cost=2)
        assert ct.get('launch_cause_mismatch') == 1
        assert _TRANS_HOLD not in _registry(sess)   # 拒登记(不拦发射归臂)
        # 名字腿红:非保护非核心普通燃料登记 hold 被拒
        assert _FUEL not in four_system_members()
        assert _FUEL not in CORE_SINGLE_CARD_REGISTRY
        assert not sell_gate.register_launch(sess, _FUEL, cause='hold',
                                             round_num=3, star=1, cost=1)
        assert ct.get('launch_cause_mismatch') == 2
        # 合取双过:1★ 保护件(refund_full_star_ok(1,2)=True)登记落账
        assert sell_gate.register_launch(sess, _TRANS_HOLD, cause='hold',
                                         round_num=3, star=1, cost=2)
        assert _registry(sess)[_TRANS_HOLD] == ('hold', 3)
        # core 档恒买无星闸:2★ 核心件登记不受星闸拒
        assert refund_full_star_ok(2, 3) is False
        assert sell_gate.register_launch(sess, _CORE_HOLD, cause='hold',
                                         round_num=3, star=2, cost=3)
        assert _registry(sess)[_CORE_HOLD] == ('hold', 3)


# ===== 窗口段:活跃 / 轮界过期 / 五键分键 =====


class TestWindowLifecycle:
    """窗口段生命周期测试(P78-2b τ=同轮;P78-3 轮界过期,W3 修法;
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
        τ=∞ 留簿,P78-2a;行为面由身份段辖,此处校验登记账本身——轮进后
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
        """W3 反向测试:F1 锁线清空废除(P78-3:锁线定型不是任何买因类
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


# ===== 装配 A 身份段·终局键集标签命中腿(design 2026-10-26-swap-channel-
# unified §2.8 堵回降口二,落点钉死 = identity_exclusions)=====


class TestIdentityLabelOverlay:
    """终局键集标签命中腿机制面:锁定帧键集标签件入身份段(不看激活
    档位),未锁定帧键集空 = 谓词零面(候选面行为锚另见 criteria/
    test_sell_candidates.py 六通道逐一点名)。"""

    def test_overlay_present_when_locked_absent_when_unlocked(self):
        """落点钉死锚:锁定双王圣杯(键集 = form_tiers 键{命运圣杯,
        能量})帧,键标签件(停云/远坂凛)入 ``identity_exclusions``——
        经 sell_exclusions 为全部常规通道共用;未锁定帧(P2 无锁态,
        保护集不含键标签件)同件不入集 = 排除谓词零面(无终局键集即无
        保护对象,§2.8 谓词辖域随锁定态)。"""
        from sr_od.application.currency_war.kernel.cw_comps import get_comp
        comp = get_comp('双王圣杯')
        locked = StrategySession()
        st = state_of(locked)
        st.cw4_counters = {}
        st.target_comp = comp
        st.v3_intention = IntentionState(locked_comp=comp.name)
        # 保护集域轴挂容器宿主态(session_scope.plane2_started_of 读域);
        # P2 域关闭四体系全体腿,键标签件(停云=仙舟)不被保护集掩蔽。
        state_of(game_state_of(locked)).plane2_started = True
        excl = sell_gate.identity_exclusions(locked, ())
        assert {'停云', '远坂凛'} <= excl, \
            '锁定帧键集标签件入身份段(不看激活档位,bench 侧含内)'
        unlocked = StrategySession()
        st2 = state_of(unlocked)
        st2.cw4_counters = {}
        state_of(game_state_of(unlocked)).plane2_started = True
        excl2 = sell_gate.identity_exclusions(unlocked, ())
        assert '停云' not in excl2 and '远坂凛' not in excl2, \
            '未锁定帧无终局键集 = 标签排除零面(不越辖域保护)'


# ===== W1:同 visit 卖回全通道被禁(P78-1;shop_sell 报告 W1)=====


_W1_CHANNEL_CASES = ('funding-e2e', 'm4-candidates')


class TestW1SameVisitBan:
    """W1 测试:②(b)/dominance 等 press 类买入登记活跃帧(登记轮==
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
        (凑息同面)——本测试绿由窗口段承载,非谓词自带拒。"""
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


# (W1 'entry-ev' 消费位测试退役〔2026-10-12 迭代批 3.3〕:entry EV pass 随
#  备战九段全扫重写删除,备战域筹资发射位消亡——press 活跃件不被筹资
#  卖出的同面语义仍由本文件 funding-e2e(店内 decide_shop_action)与
#  评估器资格面测试〔test_sell_candidates〕承载;店内筹资消费位
#  随 3.6 会话重排接续。)
_W1_CASES = {
    'funding-e2e': TestW1SameVisitBan._case_funding_e2e,
    'm4-candidates': TestW1SameVisitBan._case_m4_candidates,
}


# ===== funding 兜底豁免(P78-5 四条件)=====

# (原 TestFundingHoldFallback 店侧五个测试随商店期筹资形态收缩退役:
#  店内兜底变现发射面删除,筹资形态 = 关店交回(测试 =
#  test_shop_session_loop::test_funding_hold_fallback_records_
#  opportunity,原文件名 test_cw_shop_action_face_contraction 已并入);
#  原 entry 侧消费位测试〔TestFundingFallbackEntryConsumer,
#  经 entry._criteria_pass 发射〕随 2026-10-12 迭代批 3.3 备战九段全扫
#  重写退役——EV pass 删除,备战域兜底发射位消亡;兜底池定义单一源
#  〔sell_gate.funding_hold_fallback〕与达成量化语义由 3.6 会话内筹资
#  消费循环接线时新测试承载。)


class TestProtectionIdentityMigration:
    """卖面身份段/兜底池换挂保护集(统一保护集 changes/2026-10-15-
    unified-protection-set design.md §2.3;landing 3.3 兜底对账判据)。

    成员锚(注册表事实,机械重推):椒丘 = 持续伤害系 drop 档四体系件
    (旧策展静态集**外**——档位过滤不收 drop,新保护集**内**);银狼
    LV.999 = registry 核心(星核猎手+欢愉,非四体系——核心保留理由
    本体);万敌/阿格莱雅 = 非四体系非核心。
    """

    def test_identity_segment_is_protection_union_core(self):
        """装配 A 身份段构成 = 义务基座 ∪ 保护集 ∪ registry 核心:
        保护集成员(椒丘)与 registry 核心(银狼LV.999)入排除集,
        非保护非核心件(阿格莱雅 = _FUEL 红证锚)不入——④ 策展静态集
        口径(档位过滤)由保护集全域取代的直接验证。"""
        excl = sell_gate.identity_exclusions(_sess(), ())
        assert '椒丘' in excl, '保护集成员未入身份段(常规通道禁卖失守)'
        assert '银狼LV.999' in excl, 'registry 核心保留腿失守'
        assert '希儿' in excl
        assert _FUEL not in excl, \
            '非保护非核心件被误排除(身份段超扩,凑息燃料面被掏空)'

    def test_funding_fallback_pool_admits_protection_member(self):
        """兜底对账断言(landing 3.3):全场保护档帧(椒丘构造),P78-5
        兜底池 = 「保护集 ∪ registry 核心」的直接验证——①椒丘(旧静态
        集 drop 档外)入兜底池可放行(退金 ≥ 缺口,达成量化腿);②
        银狼LV.999 经核心腿入池(非四体系仍受兜底辖);③万敌(非保护
        非核心)不入池(兜底 = 持有件最后手段,非一般燃料通道)。"""
        # ①椒丘:1★ 1费 退 1 ≥ 缺口 1(gold 9 / need 10)
        sess = _sess()
        cw4_gs(sess, plane=1, round_num=2, node='prep',
               bench=[_bc('椒丘')], front_row=[Unit(char_id='万敌',
                                                    star=1)])
        out = sell_gate.funding_hold_fallback(
            sess, (), [_bc('椒丘')], gold=9, need=10,
            a_exclusions=sell_gate.identity_exclusions(sess, ()),
            deployed=[Unit(char_id='万敌', star=1)])
        assert [mandate._slot_cid(b) for b in out] == ['椒丘'], \
            '保护档成员未入兜底池(兜底 = 唯一可卖保护件通道失守)'
        # ②银狼LV.999:registry 核心,bench_char_cost 档感知退 3 ≥ 缺口 3
        sess2 = _sess()
        cw4_gs(sess2, plane=1, round_num=2, node='prep',
               bench=[_bc('银狼LV.999')],
               front_row=[Unit(char_id='万敌', star=1)])
        out2 = sell_gate.funding_hold_fallback(
            sess2, (), [_bc('银狼LV.999')], gold=7, need=10,
            a_exclusions=sell_gate.identity_exclusions(sess2, ()),
            deployed=[Unit(char_id='万敌', star=1)])
        assert [mandate._slot_cid(b) for b in out2] == ['银狼LV.999']
        # ③万敌:非保护非核心,退金再高也不入兜底池
        sess3 = _sess()
        cw4_gs(sess3, plane=1, round_num=2, node='prep',
               bench=[_bc('万敌')],
               front_row=[Unit(char_id='刃', star=1)])
        out3 = sell_gate.funding_hold_fallback(
            sess3, (), [_bc('万敌')], gold=9, need=10,
            a_exclusions=sell_gate.identity_exclusions(sess3, ()),
            deployed=[Unit(char_id='刃', star=1)])
        assert out3 == [], '非持有件混入兜底池(兜底 ≠ 一般燃料通道)'


# ===== P78-6:projection 视图 = interest 全资格面(含 T3 活跃集)=====


class TestProjectionFullFace:
    """读端同源测试(P78-6/M7):projection 视图 = 身份段 ∪ 窗口段 ∪
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


# ============================================================
# 并段:轮内新鲜度账容器宿主 + 商店访问账本死字段退役(原
# test_cw_round_fresh_buys_host 并入;同 visit 卖回防线第二载体)
# ============================================================


def _feed_phase(session: StrategySession, plane: int,
                round_num: int) -> GameState:
    """容器节点播种(与 _cw_helpers 种子节点补写同式;kind 空串 =
    帧未识别的忠实镜像,相位读口 plane_of/round_num_of 只读键维)。"""
    gs = game_state_of(session)
    gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num, kind=''),
               evidence='kind_inherited',
               sig=ChannelSig(family='obs',
                              actor='cw4_seed',
                              mode='synthesized'))
    return gs


def test_round_fresh_buys_host_switch_same_container() -> None:
    """宿主切换同口:record 写入容器 Field,读端自同容器解析(相位内)。"""
    session = StrategySession()
    gs = _feed_phase(session, plane=2, round_num=3)
    record_fresh_buy(session, gs, '三月七')
    # 写端落容器 Field(值形状:phase 元组对 + names list,非 set)
    assert gs.round_fresh_buys.value == {'phase': (2, 3),
                                         'names': ['三月七']}
    # 同批发射逐名入集(防批量漏记语义保留)
    record_fresh_buy(session, gs, '丹恒')
    assert gs.round_fresh_buys.value['names'] == ['三月七', '丹恒']
    # 读端 = 同容器(同口;换出守卫视角)
    assert fresh_buys_of(session, gs) == frozenset({'三月七', '丹恒'})


def test_round_fresh_buys_phase_mismatch_invalidates_whole_record() -> None:
    """相位失配 = 跨轮整体作废(读取零销账,无逐名生命周期面);新相位
    写入 = 换记录,旧相位名不泄入。"""
    session = StrategySession()
    gs = _feed_phase(session, plane=2, round_num=3)
    record_fresh_buy(session, gs, '三月七')
    assert fresh_buys_of(session, gs) == frozenset({'三月七'})
    # 轮次推进:旧记录整体作废,且记录本体未被读端销账(零销账)
    gs = _feed_phase(session, plane=2, round_num=4)
    assert fresh_buys_of(session, gs) == frozenset()
    assert gs.round_fresh_buys.value['names'] == ['三月七']
    record_fresh_buy(session, gs, '丹恒')
    assert gs.round_fresh_buys.value == {'phase': (2, 4), 'names': ['丹恒']}


def test_fresh_buys_sell_face_failclosed_and_phase_gate() -> None:
    """L1 卖侧闩读端(容器宿主):节点未定帧 = fail-closed 排除当前记录
    全集(方向安全,上界单轮);节点已定帧相位失配 = 整体作废。"""
    session = StrategySession()
    gs = game_state_of(session)   # node 未定:相位键 = 缺省 (1, 1)
    record_fresh_buy(session, gs, '三月七')
    assert fresh_buys_sell_face(session) == frozenset({'三月七'})
    # 节点已定且相位失配 = 跨轮,整体作废
    _feed_phase(session, plane=2, round_num=3)
    assert fresh_buys_sell_face(session) == frozenset()
    # 同相位重录后硬面恢复可见
    record_fresh_buy(session, gs, '丹恒')
    assert fresh_buys_sell_face(session) == frozenset({'丹恒'})


def test_buy_ledger_dead_base_fields_retired() -> None:
    """四死基座字段不再在场(期望态残留,全为写端无读端,对象面运行时
    检查);存活面 buy_purchases 保留。"""
    ledger = ShopVisitLedger()
    for _dead in ('buy_pre_bench', 'buy_pre_deployed', 'buy_has_sell',
                  'buy_unidentified'):
        assert not hasattr(ledger, _dead)
    assert ledger.buy_purchases == []
