"""T-126 卖出归因枚举与「任意买因类×任意卖出通道」矩阵(单帧锁;批 4 收官)。

出处(锁纪律:新锁必引设计出处):
- ADR-0585(§3 reason 枚举闭集×9 发射位装配键集/发射规则「T3 特化值
  优先于通道名」/funding plain 分键;§5 契约正本首次落档申报 =
  flow/action_exec.md §1 卖出类行);
- docs/develop/currency_war/proofs/math_proofs.md **P78** 行(P78-1 同
  visit 禁卖无条件下成立/P78-2 τ 分类/P78-5′ 四关系表:垫保在凑息
  绝对跳过、在 M4/funding 降序放行转化类);
- 方案 v3(`.debug/temp/currency_war/t126_sell_arbitration/方案.md`)
  §3.4(W8 落地形态与两判定口径:默认值⇒类型消费无感/序列化白名单
  挑字段⇒新字段默认不入 sim 账本)/§5.2(reason 枚举锁两阶段收敛:
  9 位统一断言+prep 双写对齐+枚举闭集常量锁)/§5.3(矩阵测试;
  ev_buy 行同轮-only = V2-07);
- docs/develop/currency_war/decisions/dd-020(序列决策契约;批 4 完成
  权威链重锚,词表落档行 = action_exec.md §1)。

9 位 reason 覆盖地图(重复断言择一保留,本文件补齐缺口位):shop M4
腾席两位(plain+T3 特化)= test_cw_t3_stall_protect.Test2FuelDemotion;
shop funding 主路径 T3 特化 = test_cw_sell_window_launch.
TestFundingHoldFallback.test_main_path_nonempty_skips_fallback;shop
funding 兜底位(funding_hold_liquidated)= 同文件
test_shop_fallback_liquidates_hold_last_resort;**其余 9 位断言与
全量归因面(双写对齐/登记门/序列化等值/消费位清单)由本文件承载**。

红证形态:矩阵格红证 = 「拔除对应装配构件后该件恰入卖出面」的机制
复现(与批 2/批 3 主题文件同款),散布在各格注释与既有文件引用,
不另设重复红证函数。
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_prep_actions import (
    SELL_BENCH_REASONS,
    BailToOuter,
    PrepObservation,
    action_key,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    SellBench as PrepSellBench,
)
from sr_od.application.currency_war.kernel.cw_state import (
    SELL_BENCH_CONVERT_REASONS,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_state import (
    SellBench as ShopSellBench,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    mandate,
    sell_gate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.adapter import (
    action_to_atomop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
    provisional,
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
from sr_od.application.currency_war.telemetry.schema import serialize_action
from test.sr_od.app.currency_war.test_cw_sell_window_launch import (
    _CORE_HOLD,
    _FUEL,
    _TRANS_HOLD,
    _bc,
    _sess,
    _state,
)

_PKG = Path(mandate.__file__).resolve().parent

#: 买因类 → 发射事件对象名(义务=线成员/持有=静态集/压库·垫保=线外燃料)。
_X_BY_CAUSE: dict[str, str] = {
    'obligation': '目标件',
    'hold': _CORE_HOLD,
    'press': _FUEL,
    'stall_protect': _FUEL,
}


def _register(sess, cause: str) -> str:
    """构造「买因类 c 的发射事件」:登记发射 + 返回对象名(账本观测面;
    obligation/hold 类行为面由身份段辖,登记仅供五键闭合断言)。"""
    x = _X_BY_CAUSE[cause]
    assert sell_gate.register_launch(sess, x, cause=cause, round_num=3,
                                     star=1, cost=3)
    return x


def _prep_emit_out(sells: list) -> list:
    return [e for e in sells if isinstance(e.action, PrepSellBench)]


# ===== 枚举闭集登记门(方案 v3 §5.2 阶段 2;ADR-0585 §3)=====


class TestReasonEnumRegistry:
    """卖出归因枚举登记门:增删值红且点名(判别问句:红时登记的语义 =
    新发射位/新特化键入册,非机械跟绿)。"""

    def test_close_set_is_six_channel_values(self):
        """通道枚举闭集登记门:六通道值(T-143/ADR-0594 增
        endgame_liquidation_clear = 域①终局清算腾位发射位,卖出发射
        位第 10 处;victim = 燃料类单一源 + 统一装配 A,P78 通道对价段
        「终局清算」豁免行的落地值)。"""
        assert set(SELL_BENCH_REASONS) == {
            'interest_pullback_prep', 'interest_pullback', 'funding_support',
            'm4_fuel_victim', 'line_switch_collapse',
            'endgame_liquidation_clear',
        }

    def test_convert_set_four_keys_and_intersection_carve_out(self):
        """转化特化集(同轮买卖检查豁免面单一源)钉死四键;与通道枚举
        不相交的唯一例外 = line_switch_collapse(T-141/ADR-0591:该键
        双重身份 = entry 换线塌缩出口通道名 + 商店发射位线账闭合孤儿
        证明标记,两语义同为 P78-2a 账闭合事件)。其余 plain 通道值恒
        不豁免(检查器镜像锁见 TestSerializationEquivalence)。"""
        assert set(SELL_BENCH_CONVERT_REASONS) == {
            'fuel_victim_protect_demoted', 'funding_support_stall_convert',
            'funding_hold_liquidated', 'line_switch_collapse',
        }
        assert {'line_switch_collapse'} == \
            (SELL_BENCH_REASONS & SELL_BENCH_CONVERT_REASONS)


# ===== 序列化等值(方案 v3 §3.4 V2-02 两判定口径的锁面)=====


class TestSerializationEquivalence:
    """「reason 默认值下新旧账本逐位一致」的可观测锚:
    ①决策层幂等键逐字节不变;②decisions 转录面为加法增益(schema 容忍
    新键);③sim 检查器豁免面不因 plain 值扩边;④cw_replay --diff 渲染
    对 reason 结构性免疫(只取 bench_idx)——批 4 纯遥测增益的判定零变
    由此四锚承载。"""

    def test_action_key_ignores_reason_and_matches_pre_batch_format(self):
        """幂等粒度 = 类型 + 行为参数:归因不入键,且键文本与批 4 前逐
        字节一致(字段 metadata 排除,决策层屏蔽/计数粒度零漂移)。"""
        k_default = action_key(PrepSellBench(slot=3))
        k_filled = action_key(PrepSellBench(slot=3, reason='m4_fuel_victim'))
        assert k_default == k_filled == "SellBench({'slot': 3})"
        # 对照:BailToOuter.reason 是载荷(非归因),必须入键。
        assert action_key(BailToOuter(reason='a')) != \
            action_key(BailToOuter())

    def test_decisions_transcription_carries_reason(self):
        """decisions 行动作转录(既有转录面,全字段平铺):reason 键加法
        出现且随值透传;旧读端 .get 容忍缺键(schema 纪律「新字段末尾
        追加且可选」)。"""
        d0 = serialize_action(PrepSellBench(slot=1))
        assert d0 == {'slot': 1, 'reason': '', '__type__': 'SellBench'}
        d1 = serialize_action(PrepSellBench(slot=1, reason='interest_pullback_prep'))
        assert d1['reason'] == 'interest_pullback_prep'

    def test_plain_reason_does_not_extend_convert_exemption_face(self):
        """sim 检查器豁免面收敛(ADR-0585 §3;check_no_same_round_buy_sell
        镜像):plain 通道值与 '' 同罪(同轮买后卖仍报),仅特化集豁免
        ——枚举填充不得悄悄放大豁免面。"""
        from sr_od.application.currency_war.sim.checks.ledger import (
            check_no_same_round_buy_sell,
        )
        row = {'plane': 1, 'round_num': 1,
               'actions': [
                   {'__type__': 'BuyCard',
                    'card': {'name': 'X'}, 'reason': ''},
                   {'__type__': 'SellBench', 'name': 'X',
                    'sell_reason': 'm4_fuel_victim'}]}
        assert check_no_same_round_buy_sell([row]), \
            'plain 枚举值误入豁免面 = 同轮自旋检查被架空'
        row_ok = {'plane': 1, 'round_num': 1,
                  'actions': [
                      {'__type__': 'BuyCard',
                       'card': {'name': 'X'}, 'reason': ''},
                      {'__type__': 'SellBench', 'name': 'X',
                       'sell_reason': 'funding_support_stall_convert'}]}
        assert not check_no_same_round_buy_sell([row_ok]), \
            '特化集豁免边被误收窄(批 3 转化类语义回归)'

    def test_replay_diff_rendering_ignores_reason(self):
        """cw_replay --diff 分歧面对 reason 免疫:新旧两渲染器都只取
        bench_idx/shop 行名——归因填充在回放对比面结构性零漂移。"""
        from sr_od.application.currency_war.sim.cw_replay import _fmt, _fmt_json
        new_row = [ShopSellBench(bench_idx=2, income=1, expect='X',
                                 reason='m4_fuel_victim')]
        old_row = [{'__type__': 'SellBench', 'bench_idx': 2}]
        assert _fmt(new_row) == _fmt_json(old_row) == 'Sell(2)'
        # prep 载体行(slot 域,无 bench_idx)渲染同样不含 reason 面。
        assert _fmt_json([{'__type__': 'SellBench'}]) == 'Sell(None)'

    def test_shadow_adapter_fingerprint_aligned_with_action_key(self):
        """影子适配器指纹面(V2-02 清单 B「需映射」判定点,批 4 已映射):
        action_to_atomop 与 action_key 消费同一 metadata 单一源——归因
        字段不入指纹,默认值下 op_key 与批 4 前逐字节一致
        ('sell_bench:3'),归因填充不再分裂同槽动作的幂等键。红时语义 =
        有人改动了指纹的字段选择规则,先核对 action_key 同规再动。"""
        k0 = action_to_atomop(PrepSellBench(slot=3)).op_key
        k1 = action_to_atomop(
            PrepSellBench(slot=3, reason='funding_support')).op_key
        assert k0 == k1 == 'sell_bench:3'


# ===== 9 位 reason 统一断言(方案 v3 §5.2;ADR-0585 §3 装配键集)=====


class TestNineEmissionSites:
    """归因面缺口位锁(prep 五位 + shop 凑息/funding plain;shop M4 两位
    与 funding 特化/兜底由覆盖地图所指既有锁承载)。prep 位一律断言
    tag==reason 双写对齐(方案 v3 §3.4)。"""

    def test_shop_interest_pullback(self):
        """shop 凑息回拉位(装配键集 shop.py:1716→现 :1799 区):gold<g*
        ∧ 线外燃料 ⇒ SellBench.reason = 'interest_pullback'。"""
        sess = _sess()
        act = decide_shop_action(_state(1, [_bc(_FUEL, slot=1)]), sess,
                                 SimpleNamespace(ev_arm='full'))
        assert isinstance(act, ShopSellBench)
        assert act.reason == 'interest_pullback'
        assert act.expect == _FUEL

    def test_shop_funding_plain_reason_and_counter(self):
        """shop funding 位 plain 分支:买断制覆写(g*=0)令凑息臂
        not_needed、血线不动 ⇒ 凑息让位,筹资卖出线外燃料 =
        'funding_support' + plain 分键(funding 空手率可观测事件,
        方案 v3 §5.4/ADR-0585 §3)。"""
        sess = _sess()
        state_of(sess).cw4_cap_override = 0
        act = decide_shop_action(_state(1, [_bc(_FUEL, slot=1)]), sess,
                                 SimpleNamespace(ev_arm='full'))
        assert isinstance(act, ShopSellBench)
        assert act.reason == 'funding_support'
        ct = state_of(sess).cw4_counters
        assert ct.get('funding_support_plain_sell') == 1
        assert 'funding_support_stall_convert' not in ct

    def test_prep_interest_dual_write(self):
        """prep 凑息位(mandate ②(a) 接线):载体 reason 与 Emitted 标记
        同值 'interest_pullback_prep'(双写对齐);计数键零断链。"""
        sess = _sess()
        bench = [_bc(_FUEL, slot=1)]
        frame = mandate.MandateFrame(
            gold=9, level=3, bench=bench, deployed=[], deploy_cap=4,
            node_type=None, stop_flag=False, k_members=('目标件',),
            round_num=2)
        out = mandate.run_mandate(frame, sess,
                                  state=GameState(gold=9, level=3, hp=80,
                                                  plane=1, round_num=2))
        sells = _prep_emit_out(out)
        assert len(sells) == 1
        assert sells[0].action.reason == 'interest_pullback_prep'
        assert sells[0].reason == sells[0].action.reason
        assert state_of(sess).cw4_counters.get('t1_interest_prep_emit') == 1

    def test_prep_m4_plain_and_t3_specialized_dual_write(self):
        """prep M4 腾席位(mandate M2 重试环):plain victim =
        'm4_fuel_victim';被保垫件为唯一燃料帧 = T3 特化值优先
        ('fuel_victim_protect_demoted');两形态 tag==reason 双写。
        买断制覆写关凑息臂(裸 session g* 高,gold<g* 会让 ②(a) 先于
        M2 清空燃料面,隔离本位的发射臂)。"""
        k = ('目标件',)
        # plain:9 个互异线外 1★ 燃料,victim = 序首。
        sess = _sess()
        state_of(sess).cw4_cap_override = 0
        bench = [_bc(f'燃料{i}', slot=i) for i in range(1, 10)]
        frame = mandate.MandateFrame(
            gold=30, level=3, bench=bench, deployed=[], deploy_cap=4,
            node_type=None, stop_flag=False, k_members=k, round_num=2)
        out = mandate.run_mandate(frame, sess,
                                  state=GameState(gold=30, level=3, hp=80,
                                                  plane=1, round_num=2))
        sells = _prep_emit_out(out)
        assert len(sells) == 1
        assert sells[0].action.reason == 'm4_fuel_victim'
        assert sells[0].reason == sells[0].action.reason
        # T3 特化:8 张 3★ 非燃料 + 唯一被保垫件 ⇒ victim = 垫件。
        sess2 = _sess()
        state_of(sess2).cw4_cap_override = 0
        assert sell_gate.register_launch(sess2, '垫保F',
                                         cause='stall_protect', round_num=2)
        bench2 = [_bc(f'高价{i}', star=3, slot=i) for i in range(1, 9)]
        bench2.append(_bc('垫保F', slot=9))
        frame2 = mandate.MandateFrame(
            gold=30, level=3, bench=bench2, deployed=[], deploy_cap=4,
            node_type=None, stop_flag=False, k_members=k, round_num=2)
        out2 = mandate.run_mandate(frame2, sess2,
                                   state=GameState(gold=30, level=3, hp=80,
                                                   plane=1, round_num=2))
        sells2 = _prep_emit_out(out2)
        assert len(sells2) == 1
        assert sells2[0].action.reason == 'fuel_victim_protect_demoted'
        assert sells2[0].reason == 'fuel_victim_protect_demoted'
        ct2 = state_of(sess2).cw4_counters
        assert ct2.get('fuel_victim_protect_demoted') == 1
        assert ct2.get('close_on_sell') == 1   # 出口①卖出销(转化类)

    def test_prep_skeleton_funding_plain_dual_write(self):
        """prep funding 骨架-only 位(entry.emit skeleton_only 臂):
        买断制覆写关凑息臂后,筹资卖出线外燃料 = 'funding_support' +
        plain 分键;载体与标记双写。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        strat = MandateV1Strategy()
        sess = _sess()
        state_of(sess).cw4_cap_override = 0
        st = _state(0, [_bc('填充燃料F', slot=1)])
        obs = PrepObservation(state=st,
                              bench_chars=[_bc('填充燃料F', slot=1)],
                              deployed_chars=[], deploy_vacancy=0)
        out = entry.emit(obs, SimpleNamespace(), sess, None,
                         ev_arm='skeleton_only', registry=strat.registry)
        sells = _prep_emit_out(out)
        assert [s.action.slot for s in sells] == [1]
        assert sells[0].action.reason == 'funding_support'
        assert sells[0].reason == 'funding_support'
        assert sells[0].funding_support is True
        assert state_of(sess).cw4_counters.get(
            'funding_support_plain_sell') == 1

    def test_prep_skeleton_funding_fallback_channel_reason(self):
        """prep funding 兜底位(骨架-only 臂):唯一 ④件主路径空 → 兜底
        变现;reason = 兜底分键入载体(三审三波 F6 修订:批 3 旧申报
        「走计数不入载体」废止,批 4 载体已带 reason 字段,归因一致性
        面与 shop 兜底位对齐;tag==reason 双写)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        strat = MandateV1Strategy()
        sess = _sess()
        state_of(sess).cw4_cap_override = 0
        st = _state(1, [_bc(_TRANS_HOLD, slot=1)])   # cost=2 → 退 2 ≥ 缺口 3−1
        obs = PrepObservation(state=st, bench_chars=[_bc(_TRANS_HOLD, slot=1)],
                              deployed_chars=[], deploy_vacancy=0)
        out = entry.emit(obs, SimpleNamespace(), sess, None,
                         ev_arm='skeleton_only', registry=strat.registry)
        sells = _prep_emit_out(out)
        assert [s.action.slot for s in sells] == [1]
        assert sells[0].action.reason == 'funding_hold_liquidated'
        assert sells[0].reason == 'funding_hold_liquidated'
        assert state_of(sess).cw4_counters.get('funding_hold_liquidated') == 1

    def test_prep_ev_funding_plain_and_t3_specialized(self):
        """prep funding EV 位(entry._criteria_pass):plain 分支 =
        'funding_support'+plain 分键;被保垫件 = T3 特化值优先;两分支
        tag==reason 双写。"""
        def _run(bench: list, sess) -> tuple[list, dict]:
            st = GameState(gold=1, level=5, round_num=2, hp=40)
            frame = mandate.MandateFrame(
                gold=1, level=5, bench=bench, deployed=[], deploy_cap=6,
                node_type=None, stop_flag=True, k_members=('线内件X',),
                round_num=2)
            out = entry._criteria_pass(frame, sess, st, ('线内件X',),
                                       k_switched=False, old_line_members=())
            return _prep_emit_out(out), state_of(sess).cw4_counters

        sess = _sess()
        sells, ct = _run([_bc('填充燃料F', slot=1)], sess)
        assert [s.action.slot for s in sells] == [1]
        assert sells[0].action.reason == 'funding_support'
        assert sells[0].reason == 'funding_support'
        assert ct.get('funding_support_plain_sell') == 1
        # T3 特化:唯一燃料 = 被保垫件(defer 降序放行,转化类)。
        sess2 = _sess()
        assert sell_gate.register_launch(sess2, '填充燃料F',
                                         cause='stall_protect', round_num=2)
        sells2, ct2 = _run([_bc('填充燃料F', slot=1)], sess2)
        assert [s.action.slot for s in sells2] == [1]
        assert sells2[0].action.reason == 'funding_support_stall_convert'
        assert sells2[0].reason == 'funding_support_stall_convert'
        assert ct2.get('funding_support_stall_convert') == 1

    def test_prep_ev_funding_fallback_channel_reason(self):
        """prep funding EV 兜底位:reason = 兜底分键入载体(F6 修订,
        与骨架-only 兜底位同口径双写)。"""
        sess = _sess()
        st = GameState(gold=1, level=5, round_num=2, hp=40)
        bench = [_bc(_TRANS_HOLD, slot=1)]
        frame = mandate.MandateFrame(
            gold=1, level=5, bench=bench, deployed=[], deploy_cap=6,
            node_type=None, stop_flag=True, k_members=('线内件X',),
            round_num=2)
        out = entry._criteria_pass(frame, sess, st, ('线内件X',),
                                   k_switched=False, old_line_members=())
        sells = _prep_emit_out(out)
        assert [s.action.slot for s in sells] == [1]
        assert sells[0].action.reason == 'funding_hold_liquidated'
        assert sells[0].reason == 'funding_hold_liquidated'
        assert state_of(sess).cw4_counters.get('funding_hold_liquidated') == 1

    def test_prep_line_switch_collapse_dual_write(self):
        """prep 换线塌缩位(entry._criteria_pass):k_switched 帧旧线
        燃料件(U_X/V_MS 注入态保守子集)= 'line_switch_collapse';
        载体与标记双写。"""
        sess = _sess()
        st = GameState(gold=30, level=5, round_num=2, hp=40)
        bench = [_bc(_FUEL, slot=1)]
        frame = mandate.MandateFrame(
            gold=30, level=5, bench=bench, deployed=[], deploy_cap=6,
            node_type=None, stop_flag=True, k_members=('线内件X',),
            round_num=2)
        provisional.inject('U_X', provisional.CalibValue(
            value=1.0, injected_form=True))
        provisional.inject('V_MS', provisional.CalibValue(
            value=1.0, injected_form=True))
        try:
            out = entry._criteria_pass(frame, sess, st, ('线内件X',),
                                       k_switched=True, old_line_members=(_FUEL,))
        finally:
            provisional.reset('U_X')
            provisional.reset('V_MS')
        sells = _prep_emit_out(out)
        assert [s.action.slot for s in sells] == [1]
        assert sells[0].action.reason == 'line_switch_collapse'
        assert sells[0].reason == 'line_switch_collapse'


# ===== seed18 p1r1 端到端首发点锁(T-141;ADR-0591)=====


class TestLineSwitchOrphanSeed18:
    """ci_smoke 慢锁 no_same_round_buy_sell 预存红(seed18 p1r1)的发射侧
    闭合证据:义务买入(青雀,m2_line_member)当轮 K 支持度重排致成员出
    基座 = P78-2a 线账闭合,其后的凑息回拉清算行带
    sell_reason='line_switch_collapse'(引擎转录面),检查器豁免面据此
    分键;决策轨迹逐位不变(reason 不进决策输入,渲染面免疫 =
    TestSerializationEquivalence.test_replay_diff_rendering_ignores_
    reason)。种子锚同责(README 纪律 12):策略行为位移致形态消失时,
    红 = 重选探针种子,非机械跟绿。"""

    def test_seed18_p1r1_orphan_sell_marked(self):
        from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
        res = simulate_p1(18, pool='snapshot')
        sells = [a for row in res.ledger
                 if row.get('plane') == 1 and row.get('round_num') == 1
                 for a in (row.get('actions') or [])
                 if a.get('__type__') == 'SellBench']
        marked = [a for a in sells
                  if a.get('sell_reason') == 'line_switch_collapse']
        assert marked, \
            f'p1r1 卖出行未见孤儿标记(形态消失则重选探针种子): {sells}'
        # 证明随行可辨:卖出名带字段(转录面),豁免键不离证明。
        assert any(a.get('name') for a in marked), '卖出行缺名字段'


# ===== 任意买因类×任意卖出通道矩阵(方案 v3 §5.3;P78 INV)=====

#: 逐格期望判定表(20 格;出处=P78-2 τ 分类+P78-5′ 四关系表):
#: - excluded:名入 A 排除面(义务/持有=身份段,压库=窗口段通道无关,
#:   垫保×projection=T3 活跃集并入,M7);
#: - defer_skip:不入 A 排除面,通道侧资格级绝对跳过(凑息,sell.py:140);
#: - convert:不入 A 排除面,通道侧降序放行(转化类,funding/M4);
#: - struct_self_limit:不入 A 排除面,通道候选域结构自限(换线塌缩
#:   候选 ⊂ 旧线,垫件永不在旧线 = criteria 结构无关声明)。
_EXCLUDED_CAUSES = ('obligation', 'hold', 'press')
_MATRIX: dict[tuple[str, str], str] = {}
for _ch in sorted(sell_gate.SELL_CHANNELS):
    for _cause in _EXCLUDED_CAUSES:
        _MATRIX[(_cause, _ch)] = 'excluded'
_MATRIX[('stall_protect', 'interest')] = 'defer_skip'
_MATRIX[('stall_protect', 'funding')] = 'convert'
_MATRIX[('stall_protect', 'm4_fuel')] = 'convert'
_MATRIX[('stall_protect', 'line_switch')] = 'struct_self_limit'
_MATRIX[('stall_protect', 'projection')] = 'excluded'


class TestCauseChannelMatrix:
    """4 因果类×5 通道视图 = 20 格全枚举(按因果类不按臂;新臂归入某
    因果类才合法、新通道先登记 SELL_CHANNELS——防第 5 通道/第 13 臂
    绕 A 复发,方案 v3 §5.3)。红证散布格注释:拔除对应构件后该件恰入
    卖出面(义务→拔身份段基座/持有→拔静态集/压库→拔窗口段/垫保→
    defer 参数不喂,批 2/批 3 主题文件已有同款红证函数,不重复立)。"""

    @pytest.mark.parametrize('channel', sorted(sell_gate.SELL_CHANNELS))
    @pytest.mark.parametrize('cause',
                             ('obligation', 'hold', 'press', 'stall_protect'))
    def test_matrix_cell(self, cause: str, channel: str):
        sess = _sess()
        x = _register(sess, cause)
        verdict = _MATRIX[(cause, channel)]
        k = ('目标件',) if cause == 'obligation' else ()
        excl = sell_gate.sell_exclusions(sess, k, channel=channel,
                                         current_round=3)
        if verdict == 'excluded':
            assert x in excl, f'{cause}×{channel}:活跃账期件入了资格面'
            return
        # 垫保类:硬排除会杀死转化类放行(P78-5′),A 面恒不含。
        assert x not in excl, f'{cause}×{channel}:垫保被误升 A 排除面'
        bench = [_bc(x, slot=1)]
        st = GameState(gold=1, level=3, hp=80, plane=1, round_num=3)
        t3 = sell_gate.stall_protect_active(sess, 3)
        assert t3 == {x}
        if channel == 'interest':
            slots, key = crit_sell.sell_for_interest(
                1, bench, 5, (), state=st, defer_names=t3)
            assert key == '' and slots == []
        elif channel in ('funding', 'm4_fuel'):
            if channel == 'funding':
                slots, key = crit_sell.funding_support_sell(
                    1, 9, bench, (), state=st, defer_names=t3)
                assert key == '' and slots == [1]
            else:
                cands = mandate.fuel_sell_candidates(
                    bench, (), state=st, defer_names=t3)
                assert [b.char_id for b in cands] == [x]
        else:
            assert channel == 'line_switch'
            provisional.inject('U_X', provisional.CalibValue(
                value=1.0, injected_form=True))
            provisional.inject('V_MS', provisional.CalibValue(
                value=1.0, injected_form=True))
            try:
                slots, key = crit_sell.line_switch_sell(
                    (), (), bench, [], st, k_switched=True)
            finally:
                provisional.reset('U_X')
                provisional.reset('V_MS')
            assert key == '' and slots == []

    def test_press_round_closure_repool_with_five_keys(self):
        """压库类账闭合 = 轮界收入结算(P78-2b):轮进回池 + close_on_
        round/press_window_expired_round 分键显影(闭合事件由分键承载,
        矩阵断言可观测;方案 v3 §5.3/N6)。"""
        sess = _sess()
        x = _register(sess, 'press')
        for ch in sorted(sell_gate.SELL_CHANNELS):
            assert x in sell_gate.sell_exclusions(
                sess, (), channel=ch, current_round=3)
        sell_gate.active_window(sess, 4)
        ct = state_of(sess).cw4_counters
        assert ct.get('close_on_round') == 1
        assert ct.get('press_window_expired_round') == 1
        for ch in sorted(sell_gate.SELL_CHANNELS):
            assert x not in sell_gate.sell_exclusions(
                sess, (), channel=ch, current_round=4), \
                f'{ch} 轮界后未回池 = 过度禁卖无界(P78-2b 违例)'

    def test_stall_round_closure_repool(self):
        """垫保类 τ=同轮(T3 同界):轮界过期分键
        t3_protect_expired_round(键名零断链)+ close_on_round;projection
        视图随 T3 活跃集同步回池(M7 读端同源)。"""
        sess = _sess()
        x = _register(sess, 'stall_protect')
        assert x in sell_gate.sell_exclusions(
            sess, (), channel='projection', current_round=3)
        assert sell_gate.stall_protect_active(sess, 4) == frozenset()
        ct = state_of(sess).cw4_counters
        assert ct.get('t3_protect_expired_round') == 1
        assert ct.get('close_on_round') == 1
        assert x not in sell_gate.sell_exclusions(
            sess, (), channel='projection', current_round=4)

    def test_obligation_deploy_keeps_ban_and_switch_repool(self):
        """义务类账闭合(P78 §2.1)两出口各一场景(五键语义:每个闭合
        事件消费账一次):①件离场(部署销,close_on_deploy)后名仍在
        义务基座 = 保持禁(部署态义务件禁卖);②线账闭合(换线,
        close_on_switch)回池 = 塌缩候选域——τ=∞ 至账闭合事件。"""
        # ①件离场:部署销账后义务件仍被身份段禁卖。
        sess = _sess()
        x = _register(sess, 'obligation')
        k = (x,)
        assert x in sell_gate.identity_exclusions(sess, k)
        assert sell_gate.prune_on_deploy(sess, {x}) == 1
        assert state_of(sess).cw4_counters.get('close_on_deploy') == 1
        assert x in sell_gate.identity_exclusions(sess, k), \
            '部署销后义务件可卖 = 义务换手通道未闭死(P60 病理回流)'
        # ②线账闭合:基座换空(换线)后义务账就地销账,塌缩候选回池。
        sess2 = _sess()
        x2 = _register(sess2, 'obligation')
        assert x2 not in sell_gate.identity_exclusions(sess2, ()), \
            '线账闭合后仍禁卖 = 塌缩候选域被吞(换线闭合缺失)'
        assert state_of(sess2).cw4_counters.get('close_on_switch') == 1

    def test_hold_no_time_closure_keeps_ban(self):
        """持有类 τ=∞ 无时间闭合(P78-2a):件离场/轮界都不回池——
        静态持有集按名恒禁,兜底变现仅 funding 对角格显式豁免
        (P78-5,行为锁 = test_cw_sell_window_launch
        .TestFundingHoldFallback,含两项减法反证格,本文件不重复)。
        部署销按出口②语义消费登记账(件离场闭合),禁卖面由静态集
        独立承载——两载体面分离是本格断言的语义。"""
        sess = _sess()
        x = _register(sess, 'hold')
        assert state_of(sess).cw4_fuel_filler_stall_buys.get(x) == ('hold', 3)
        sell_gate.prune_on_deploy(sess, {x})
        assert state_of(sess).cw4_counters.get('close_on_deploy') == 1
        sell_gate.active_window(sess, 9)
        for ch in sorted(sell_gate.SELL_CHANNELS):
            assert x in sell_gate.sell_exclusions(
                sess, (), channel=ch, current_round=9), \
                f'{ch}:持有件随件离场/轮界回池 = 持有期权清零(P78-2a 违例)'
        assert state_of(sess).cw4_counters.get('close_on_round') is None

    def test_ev_buy_same_round_only_cell(self):
        """ev_buy 行同轮-only(V2-07;方案 v3 §3.1/§5.3):ev_buy→press
        映射在册(M4 补漏修正),同轮禁卖格全通道成立(P78-1 无条件下);
        **跨轮回池格不设断言**——press 类轮界闭合理论不描述 ev_buy 的
        V_opt 期权账,锁它 = 把自陈缺口锁成设计语义,留 P77 缺口面/
        E_rev 装载批对账后补。"""
        assert sell_gate.launch_cause_of('ev_buy') == 'press'
        sess = _sess()
        sell_gate.register_launch(sess, _FUEL, cause='press', round_num=3)
        for ch in sorted(sell_gate.SELL_CHANNELS):
            assert _FUEL in sell_gate.sell_exclusions(
                sess, (), channel=ch, current_round=3), \
                f'{ch}:ev_buy 同轮卖回 = P78-1 违例'


# ===== 防复发双闸①:消费位清单静态锁(方案 v3 §5.3;项目架构裁决)=====


class TestConsumptionSiteManifest:
    """卖出资格排除装配单一源守卫(依赖方向/单一源守卫档,测试纪律
    第 20 条「项目架构裁决」):排除装配只出自 sell_gate 入口——
    exclude_names= 实参调用点集合 == 登记清单;清单外文件出现调用点
    必红(盲区自检:新文件落错位置时守卫能起诉)。红时语义 = 新消费位
    未登记,处置 = 清单加行 + 确认其排除集出自 sell_exclusions/
    funding_hold_fallback,非机械跟绿。"""

    _MANIFEST: dict[str, int] = {'entry.py': 2, 'mandate.py': 2, 'shop.py': 6}
    # shop.py:6 清单增行(T-143/ADR-0594):第 6 位 = 域①终局清算臂腾位
    # 卖出的装配读(exclude_names = sell_exclusions('m4_fuel') ∪ 本
    # visit 买入名减法——P78-1 同 visit 禁卖,funding 兜底减法①同款
    # 消费位减法;排除集本体仍出自 sell_gate 单一入口)。

    def _counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for p in sorted(_PKG.rglob('*.py')):
            n = len(re.findall(r'exclude_names\s*=',
                               p.read_text(encoding='utf-8')))
            if n:
                counts[p.name] = n
        return counts

    def test_exclude_assembly_call_sites_match_manifest(self):
        assert self._counts() == self._MANIFEST

    def test_retired_assembly_forms_absent(self):
        """墓碑扫描(否定式+退役背书):F2 旧形态 exclude_names=buy_members
        手搓装配与兼容再出口 sell_hold_exclusions 的生产调用(定义/再
        出口不辖)已退役(ADR-0585 §2/批 2 渐进迁移收口)。"""
        for name in ('entry.py', 'mandate.py', 'shop.py', 'bridge.py'):
            src = (_PKG / name).read_text(encoding='utf-8')
            assert 'exclude_names=buy_members' not in src
            assert 'sell_hold_exclusions(' not in src, \
                f'{name}:兼容再出口被生产调用 = 渐进迁移倒退'
