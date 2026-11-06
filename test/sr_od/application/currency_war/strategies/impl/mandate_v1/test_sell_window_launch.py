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

并段(**轮内新鲜度账状态容器宿主 + 商店访问账本死字段退役**,原
test_cw_round_fresh_buys_host 并入;同 visit 卖回防线第二载体,逐字段
处置表 #18/#19):轮内新鲜度账宿主 = 状态容器 Field ``GameState.round_
fresh_buys``(record_fresh_buy 写 → fresh_buys_of/fresh_buys_sell_face
读同一状态容器,写读唯一入口函数 sim/live 同口;相位失配 = 跨轮整体作废、读取零销
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
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)

# ===== 测试基建 =====

#: 非持有线外 1★ 燃料代表(注册表实名,cost=1;非保护集非核心 = 新身份
#: 口径下的真线外件,穿过判据全部物理谓词,红证由各测试自带直调证明)。
_FUEL = '阿格莱雅'
#: 窗口段双视图代表名(垫保视图基准)。
_STALL = '垫件P'


def _bc(name: str, star: int = 1) -> BenchSlot:
    """状态容器占席条目(直构面)。"""
    return BenchSlot(kind='unit', unit=Unit(char_id=name, star=star))


def _sess() -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = SimpleNamespace(
        name='测试线', core_chars=('目标件',), shared_chars=(),
        members=('目标件',))
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
    """发射登记 API 测试(P78 §2.2 窗口段载体;ADR-0585 §2/§3;
    3.4 修订:hold 类随 C1/囤货臂两买臂退役删除——闭集收敛
    {obligation, press, stall_protect};dominance_buy 行已随通道
    退役删除(富余买入并入 M6 一星兜底带,comp-structure-unification
    3.4);or-reqs-retirement 3.4 增过渡资格臂行——映射表 14 键。"""

    def test_launch_cause_closed_set(self):
        """闭集三个测试并一:
        [枚举拒] LaunchCause 枚举外值拒收(方案 v3 §5.3 防复发
          双闸②;新买入臂必须先归入某因果类才合法;hold 类同为枚举外
          ——3.4 退役后登记被拒);
        [14 臂映射] 买入臂全映射 + 值域 ⊆ LaunchCause 闭集 +
          ev_buy→press(方案 v3 §3.1;新买入臂未分类即登记 = 红,测试红
          时该登记的语义 = 把新臂补进映射表并过对抗审,非机械跟绿)。
          core_single_card_buy 族/protection_hoard 三行已随两买臂退役
          删除(统一让位优先级迭代 3.4);dominance_buy 行已随通道退役
          删除(comp-structure-unification 3.4);
        [双视图] 单载体双视图:press 登记入窗口段排除面(active_window),
          垫保登记只入 T3 视图(stall_protect_active → defer 参数)——
          垫保在凑息是 defer 跳过、在 M4/funding 是降序放行(转化类,
          P78-5′ 四关系表「放行(已登记语义保持)」),硬排除会杀死转化
          类放行;窗口排除面 = press(P78-1 无对价豁免)。两簿合一 =
          载体/生命周期合一(轮界共销账),非排除面合一。"""
        # [枚举拒](hold 类已随两买臂退役 = 枚举外)
        with pytest.raises(ValueError):
            sell_gate.register_launch(_sess(), _FUEL, cause='speculate',
                                      round_num=3)
        with pytest.raises(ValueError):
            sell_gate.register_launch(_sess(), _FUEL, cause='hold',
                                      round_num=3)
        # [14 臂映射](11 号稿 §1 序 1 扩展臂注册 ×3:
        # shelf_qualify_buy/transition_shelf_qualify_buy/cold_start_buy,
        # 义务类;过渡资格臂语义权威版本 = strategy-docs/
        # 12_line_and_intention.md §3)
        arms = ('m2_line_member', 'm2_locked_member', 'm2_stockpile',
                'm2_merge_completion', 'shelf_qualify_buy',
                'transition_shelf_qualify_buy', 'cold_start_buy',
                'm6_stockpile',
                'press_buy_deployable',
                'ev_buy', 'dead_gold_press_buy', 'fuel_filler_stall',
                't3_unlocked_hemostat', 'scene_plugin_buy')
        assert set(sell_gate.LAUNCH_CAUSE_BY_ARM) == set(arms)
        assert 'hold' not in sell_gate.LAUNCH_CAUSES, \
            'hold 类已随 C1/囤货臂退役(3.4)'
        assert set(sell_gate.LAUNCH_CAUSE_BY_ARM.values()) \
            <= sell_gate.LAUNCH_CAUSES
        assert sell_gate.launch_cause_of('ev_buy') == 'press'
        assert sell_gate.launch_cause_of('scene_plugin_buy') == 'press'
        assert sell_gate.launch_cause_of('不存在的臂') is None
        assert sell_gate.launch_cause_of('protection_hoard') is None
        # (P88 收窄集对账段已随 P88 全套退役删除——S_spec 谓词源
        #  PRESS_NARROWED_ARMS/swap_transition_narrow_frame 同批整删,
        #  comp-structure-unification 3.4,press-stockpile §3;闭集
        #  本体对账(上方键集断言)保留。)
        # [双视图]
        sess = _sess()
        assert sell_gate.register_launch(sess, _FUEL, cause='press',
                                         round_num=3)
        assert sell_gate.register_launch(sess, _STALL, cause='stall_protect',
                                         round_num=3)
        assert sell_gate.active_window(sess, 3) == {_FUEL}
        assert sell_gate.stall_protect_active(sess, 3) == {_STALL}


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
        """press τ=同轮:登记轮==当前轮才入排除面,轮进销账。轮进后
        press 销账(登记簿空)。current_round=None ⇒ 窗口段失效(V2-09:
        INV 显式例外,方向 = 放行向;轮不可得帧禁据缺读放大禁卖面,T3
        既有语义继承;身份段已随 3.4 退役——失效面 = 空集 + L1/种子
        豁免自治读面,本帧无新鲜买入登记 = 空集)。"""
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        assert _FUEL in sell_gate.sell_exclusions(
            sess, (), channel='m4_fuel', current_round=3)
        assert _FUEL in sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=3)
        assert _FUEL not in sell_gate.sell_exclusions(
            sess, (), channel='m4_fuel', current_round=4)
        # current_round=None ⇒ 窗口段失效(放行向;身份段退役后排除面
        # = 空集——本帧无 fresh/seed 登记,自治读面恒空)
        assert sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=None) == frozenset()
        sell_gate.active_window(sess, 9)
        assert _FUEL not in _registry(sess)

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
        未接通窗口滞留 ≤1 轮由轮界销兜底)/③换线闭合(P78 §2.1「线账
        闭合」:义务类登记名离基座 ⇒ 销账+close_on_switch;读点原宿主
        = identity_exclusions,已随身份段退役迁入 sell_exclusions——
        3.4;复读幂等零重复计数)。"""
        # ①卖出销
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        mandate.stall_buys_consume(sess, _FUEL)   # shim 同出口①
        assert _FUEL not in _registry(sess)
        assert state_of(sess).cw4_counters.get('close_on_sell') == 1
        # ②部署销
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        sell_gate.register_launch(sess, _STALL, cause='stall_protect',
                                  round_num=3)
        n = sell_gate.prune_on_deploy(sess, {_FUEL})
        assert n == 1 and dict(_registry(sess)) == {
            _STALL: ('stall_protect', 3)}
        assert state_of(sess).cw4_counters.get('close_on_deploy') == 1
        # ②′合成销
        sess = _sess()
        assert sell_gate.consume_on_merge(sess, _FUEL) == 0   # 空账 no-op
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        assert sell_gate.consume_on_merge(sess, _FUEL) == 1
        assert _FUEL not in _registry(sess)
        assert state_of(sess).cw4_counters.get('close_on_merge') == 1
        # ③换线闭合:基座不含登记名(义务账闭)——读 sell_exclusions
        # 即触发对账(闭合读点已迁入装配 A 主入口)
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='obligation',
                                  round_num=3)
        sell_gate.register_launch(sess, 'press件Q', cause='press',
                                  round_num=3)
        sell_gate.sell_exclusions(sess, (), channel='interest',
                                  current_round=9)
        ct = state_of(sess).cw4_counters
        assert ct.get('close_on_switch') == 1
        assert _FUEL not in _registry(sess)
        # 幂等:复读不再计数
        sell_gate.sell_exclusions(sess, (), channel='interest',
                                  current_round=9)
        assert ct.get('close_on_switch') == 1


# (装配 A 身份段测试面〔TestIdentityLabelOverlay 终局键集标签命中分支/
#  TestProtectionIdentityMigration 卖面身份段与兜底池换挂保护集〕已随
#  身份段整段退役删除——统一让位优先级迭代 3.4:identity_exclusions/
#  funding_hold_fallback/hold 登记资格合取随段退役,身份承载改由统一
#  让位序列档位结构承载,负断言锁存 = criteria/test_sell_candidates::
#  TestIdentitySegmentRetired。)


# ===== W1:同 visit 卖回全通道被禁(P78-1;shop_sell 报告 W1)=====


_W1_CHANNEL_CASES = ('funding-e2e', 'm4-candidates')


class TestW1SameVisitBan:
    """W1 测试:②(b) 等 press 类买入登记活跃帧(登记轮==
    当前轮),凑息/funding/M4 全通道资格面均不含该件——「拆窗口段时
    该件恰入卖出槽集」的病理形态由红证直调复现。三通道参数化并一
    (通道无关,P78 INV)。"""

    @pytest.mark.parametrize('channel_case', _W1_CHANNEL_CASES)
    def test_press_active_blocked_channel_agnostic(self, channel_case):
        _W1_CASES[channel_case](self)

    def _case_funding_e2e(self):
        """端到端:press 活跃件在 bench + 缺员 + gold<need ⇒ funding
        主路径不可达(窗口段排除经 sell_exclusions 在资格循环生效)
        ⇒ CwActionCloseShopParam 收尾,零卖出发射。红证:同构帧无窗口
        登记装配 ⇒ 该件恰入 funding 卖出槽集(凑息同面)——本测试绿由
        窗口段承载,非谓词自带拒(身份段已随 3.4 退役,红证对照面 =
        循环防线装配缺席)。"""
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        act = decide_shop_action(
            cw4_gs(sess, **_state(1, [_bc(_FUEL)])),
            sess, SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, CwActionSellBenchParam), \
            'W1:press 登记活跃件被同轮筹资卖出 = 同 visit 卖回未闭死'
        assert isinstance(act, CwActionCloseShopParam)
        # 红证:无窗口登记的新会话,燃料件穿过物理谓词入卖出槽集
        # (P4 状态容器形:直接调用面 = 状态容器占席条目)
        bench = [_bc(_FUEL)]
        slots, key = crit_sell.funding_support_sell(
            1, 3, bench, ('目标件',), state=_bridge(**_state(1, [_bc(_FUEL)])))
        assert key == '' and slots == [0], \
            '红证失效:燃料件未穿过物理谓词(紧缩位键 0 基)'

    def _case_m4_candidates(self):
        """M4 通道同禁(P78 INV 通道无关):press 活跃件不入腾席候选
        (循环防线装配经 exclude_names 位);红证 = 无窗口登记会话
        (循环防线装配为空)该件恰入候选。"""
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        bench = [_bc(_FUEL)]   # P4 状态容器形直构面
        st = _state(30, [_bc(_FUEL)])
        window = sell_gate.sell_exclusions(sess, ('目标件',),
                                           channel='m4_fuel', current_round=3)
        assert not mandate.fuel_sell_candidates(bench, ('目标件',),
                                                state=_bridge(**st),
                                                exclude_names=window)
        # 红证:循环防线装配缺席(无登记的新会话)→ 候选面非空
        cands = mandate.fuel_sell_candidates(bench, ('目标件',),
                                             state=_bridge(**st))
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


# (TestProtectionIdentityMigration 卖面身份段/兜底池换挂保护集测试已随
#  身份段整段退役删除——funding_hold_fallback(P78-5 兜底豁免)随段退役
#  整删,兜底池/达成量化语义无对象;统一让位优先级迭代 3.4。)


# ===== P78-6:projection 视图 = 循环防线全资格面(含 T3 活跃集)=====


class TestProjectionFullFace:
    """读端同源测试(P78-6/M7;3.4 修订:身份段退役后,全资格面 =
    循环防线三构件〔窗口段/L1 同轮禁卖/种子豁免〕,projection 再并 T3
    活跃集——投影漏 T3 则 liquid_refund 高估 → s_reserve 低估 →
    预留被吃,方向链方案 v3 §2.8)。正证+红证并一。"""

    def test_projection_face_union_t3_and_red_proof(self):
        """正证:projection = 循环防线全资格面 ∪ T3 活跃集,interest =
        循环防线全资格面(不含 T3)。红证(独立会话):投影视图漏 T3
        活跃集(T3 垫件缺席排除面)⇒ 垫件被计入可变现投影 =
        liquid_refund 高估形态(修复前新格 B 残余)。"""
        # 正证
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        sell_gate.register_launch(sess, _STALL, cause='stall_protect',
                                  round_num=3)
        k = ('目标件',)
        window = sell_gate.active_window(sess, 3)
        t3 = sell_gate.stall_protect_active(sess, 3)
        want = frozenset(set(window) | set(t3))
        assert sell_gate.sell_exclusions(sess, k, channel='projection',
                                         current_round=3) == want
        assert sell_gate.sell_exclusions(sess, k, channel='interest',
                                         current_round=3) == frozenset(window)
        # 红证(独立会话)
        sess_red = _sess()
        sell_gate.register_launch(sess_red, _STALL, cause='stall_protect',
                                  round_num=3)
        no_t3 = sell_gate.sell_exclusions(sess_red, k, channel='interest',
                                          current_round=3)
        assert _STALL in sell_gate.sell_exclusions(
            sess_red, k, channel='projection', current_round=3)
        assert _STALL not in no_t3, '红证失效:无 T3 并入面仍含垫件'


# ============================================================
# 并段:轮内新鲜度账状态容器宿主 + 商店访问账本死字段退役(原
# test_cw_round_fresh_buys_host 并入;同 visit 卖回防线第二载体)
# ============================================================


def _feed_phase(session: StrategySession, plane: int,
                round_num: int) -> GameState:
    """状态容器节点播种(与 _cw_helpers 种子节点补写同式;kind 空串 =
    帧未识别的忠实镜像,相位读口 plane_of/round_num_of 只读键维)。"""
    gs = game_state_of(session)
    gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num, kind=''),
               evidence='kind_inherited',
               sig=ChannelSig(family='obs',
                              actor='cw4_seed',
                              mode='synthesized'))
    return gs


def test_round_fresh_buys_host_switch_same_container() -> None:
    """宿主切换同口:record 写入状态容器 Field,读端自同状态容器解析(相位内)。"""
    session = StrategySession()
    gs = _feed_phase(session, plane=2, round_num=3)
    record_fresh_buy(session, gs, '三月七')
    # 写端落状态容器 Field(值形状:phase 元组对 + names list,非 set)
    assert gs.round_fresh_buys.value == {'phase': (2, 3),
                                         'names': ['三月七']}
    # 同批发射逐名入集(防批量漏记语义保留)
    record_fresh_buy(session, gs, '丹恒')
    assert gs.round_fresh_buys.value['names'] == ['三月七', '丹恒']
    # 读端 = 同状态容器(同口;换出守卫视角)
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
    """L1 卖侧一次性标志位读端(状态容器宿主):节点未定帧 = fail-closed 排除当前记录
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
