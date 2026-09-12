"""卖出 reason 载体值域与「任意买因类×任意卖出通道」矩阵(单帧锁)。

出处(锁纪律:新锁必引设计出处):
- 2026-09-08 用户归因遥测删除指令(现状载体面):纯归因 reason 填充/
  分键计数整体拆除,SELL_BENCH_REASONS 缩至唯一承重值
  line_switch_collapse(T-141 检查器豁免判别食物,授予须伴随登记簿
  线账闭合证明,ADR-0591 §4);
- ADR-0585(历史设计:§3 reason 枚举闭集原 5 通道值×9 发射位装配/
  funding plain 分键,现状以该 ADR Status/§5 删除批增注为准;§5 契约
  正本落档 = flow/action_exec.md §1 卖出类行);
- docs/develop/sr_od/application/currency_war/proofs/math_proofs.md **P78** 行(P78-1 同
  visit 禁卖无条件下成立/P78-2 τ 分类/P78-5′ 四关系表:垫保在凑息
  绝对跳过、在 M4/funding 降序放行转化类);
- docs/develop/sr_od/application/currency_war/decisions/dd-020-series-decision-contract.md(序列决策契约;词表落档行
  = action_exec.md §1)。

载体面覆盖地图:line_switch_collapse 双写(entry 换线塌缩位)= 本文件
test_prep_line_switch_collapse_dual_write;凑息回拉孤儿打标端到端 =
同文件 TestLineSwitchOrphanSeed18 与 test_cw_sell_window_launch.
test_line_switch_orphan_interest_sell_marked;防洗白三格(缺省 ''/
plain 值/跨轮陈旧)= test_cw_sell_window_launch.
test_stale_obligation_buy_not_marked_next_round + 检查器面
test_cw_stall_protect.Test7CheckerExemption。

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
from test.sr_od.app.currency_war._cw_helpers import cw4_bs
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


def _boarded(gold: int = 1, level: int = 5, round_num: int = 2,
             hp: int = 40) -> GameState:
    """非空板测试环境(T-32 空板止损守卫前置):守卫钉「待卖后
    deployed 为空 ⇒ 拒卖」(单一源 = sell_gate.empty_board_sell_blocked),
    卖出判据/发射位直调环境须 ≥1 上场件,否则守卫 fail-closed 拒帧
    ——与被测语义无关的红按环境前置补齐,非跟绿。"""
    st = GameState(gold=gold, level=level, round_num=round_num, hp=hp)
    st.deployed = [_bc('板上件锚', slot=1)]
    return st


def _boarded_frame(**kw) -> mandate.MandateFrame:
    """MandateFrame 带 1 上场件(与 _boarded 同前置语义)。"""
    kw.setdefault('deployed', [_bc('板上件锚', slot=1)])
    return mandate.MandateFrame(**kw)


# ===== 枚举闭集登记门(方案 v3 §5.2 阶段 2;ADR-0585 §3)=====


class TestReasonEnumRegistry:
    """发射位值域登记门:增删值红且点名(判别问句:红时登记的语义 =
    新承重填充值入册/退役值回流,非机械跟绿)。"""

    def test_close_set_is_single_carrier_value(self):
        """2026-09-08 用户归因遥测删除指令:纯归因通道值填充全撤,
        闭集缩至唯一承重值 line_switch_collapse(T-141 检查器豁免
        判别食物,ADR-0591)。红 = 归因填充回流或新填充值未登记。"""
        assert set(SELL_BENCH_REASONS) == {'line_switch_collapse'}

    def test_convert_set_four_keys_and_intersection_carve_out(self):
        """转化特化集(同轮买卖检查豁免面单一源)钉死四键——键集保留
        非发射面(2026-09-08 删除批:三枚纯归因键的发射位填充已拆,
        键语义/豁免边不变);与发射闭集相交的唯一成员 =
        line_switch_collapse(T-141/ADR-0591:该键双重身份 = entry 换线
        塌缩出口通道名 + 商店发射位线账闭合孤儿证明标记,两语义同为
        P78-2a 账闭合事件)。其余值恒不豁免(检查器镜像锁见
        TestSerializationEquivalence)。"""
        assert set(SELL_BENCH_CONVERT_REASONS) == {
            'fuel_victim_protect_demoted', 'funding_support_stall_convert',
            'funding_hold_liquidated', 'line_switch_collapse',
        }
        overlap = SELL_BENCH_REASONS & SELL_BENCH_CONVERT_REASONS
        assert overlap == {'line_switch_collapse'}

    def test_orphan_exempt_set_independent_from_emission_gate(self, monkeypatch):
        """检查器孤儿豁免键集独立锁(T-180):cw_prep_actions.SELL_BENCH_
        ORPHAN_REASONS = 与发射位登记门 SELL_BENCH_REASONS 分离的独立
        闭集——检查器三消费位(ledger 两检查 + suspects D1)读本集,
        发射登记门新增/删值不放大/不收窄豁免面(豁免面随登记门生长 =
        振荡防空洞,零容忍)。行为面对三消费位逐一注入检测(消费位循环,
        防「只穿机械判违位、复盘位回归借道不可见」):机械判违两检查
        (ledger)行不带 target_comp = 线成员复核不可复核,借道登记门时
        对被豁免静默(报告面消失)即红;复盘面(suspects D1)只复核
        自报的合法分键,行带可解析 target_comp ∧ dec_sell_in_line=False,
        借道登记门时新值被误升格为合法分键→被自算反驳,失配条目
        出现(误报污染复盘面)即红。变异红证 = 三消费位任一借道改回
        登记门,注入新值即见豁免面放大(机械位静默漏报/复盘位误报),
        红有语义。
        叙述重推申报(T-259):断言与检测方向保持 T-180 原样不变(借道
        必红的实测=T-180 核验批落地审变异亲复现),本批仅把复盘位三处
        叙述对齐实测机理——借道在 D1 复盘位的后果是失配条目出现(误报),
        非消失(漏报);「消失」直觉只对机械判违位成立(T-180 核验批
        落地审 R1 实测勘误)。
        红时处置 = 对照 ADR-0591 §4 裁决,非机械跟绿。"""
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            SELL_BENCH_ORPHAN_REASONS,
        )
        assert set(SELL_BENCH_ORPHAN_REASONS) == {'line_switch_collapse'}
        # 行为面:登记门被注入新发射值(模拟未来登记),经 sell_reason
        # 载体的同轮买卖对仍须判违/仍须产复盘条目——豁免面不随登记门
        # 生长,三消费位逐一可见。
        import sr_od.application.currency_war.kernel.cw_prep_actions as _pa
        from sr_od.application.currency_war.sim.checks.ledger import (
            check_no_same_round_buy_sell,
            check_oscillation_xp_cap,
        )
        from sr_od.application.currency_war.sim.checks.suspects import (
            d1_same_round_pair_review,
        )
        monkeypatch.setattr(
            _pa, 'SELL_BENCH_REASONS',
            frozenset({'line_switch_collapse', 'future_emission_tag'}))
        # 机械判违行(不带 target_comp:线成员复核不可复核,正常路径下
        # 同轮买卖对必须判违;借道登记门则被豁免静默)
        row_new_gate_value = {'plane': 1, 'round_num': 1,
                              'actions': [
                                  {'__type__': 'BuyCard',
                                   'card': {'name': 'X'}, 'reason': ''},
                                  {'__type__': 'SellBench', 'name': 'X',
                                   'sell_reason': 'future_emission_tag'}]}
        assert check_no_same_round_buy_sell([row_new_gate_value]), \
            '登记门新值经 sell_reason 误入豁免面 = 独立闭集失守(T-180)'
        assert check_oscillation_xp_cap([dict(row_new_gate_value)]), \
            '登记门新值经 sell_reason 误入豁免面(振荡检查静默) = 失守'
        # 复盘面行(带可解析 target_comp + dec_sell_in_line=False:该值
        # 不在豁免闭集 = 不构成合法分键自报,d1 复核辖域外,正常路径
        # 返空;借道登记门则被误升格为合法分键→自算反驳→失配条目
        # 出现即红)
        row_review_mismatch = {'plane': 1, 'round_num': 1,
                               'target_comp': '列车同行',
                               'actions': [
                                   {'__type__': 'BuyCard',
                                    'card': {'name': 'X'}, 'reason': ''},
                                   {'__type__': 'SellBench', 'name': 'X',
                                    'sell_reason': 'future_emission_tag',
                                    'dec_sell_in_line': False}]}
        assert d1_same_round_pair_review([row_review_mismatch]) == [], \
            '登记门新值被复盘面误升格为合法分键(失配条目出现=误报) = 失守'


# ===== 序列化等值(方案 v3 §3.4 V2-02 两判定口径的锁面)=====


class TestSerializationEquivalence:
    """「reason 值变化不动任何判定面」的可观测锚(2026-09-08 删除批的
    判定零变化契约:填充值→'' 不得移动键/渲染/豁免面):
    ①决策层幂等键逐字节不变;②decisions 转录面为加法增益(schema 容忍
    新键);③sim 检查器豁免面不因非特化值扩边;④cw_replay --diff 渲染
    对 reason 结构性免疫(只取 bench_idx)——删除批判定零变由此四锚
    承载。"""

    def test_action_key_ignores_reason_and_matches_pre_batch_format(self):
        """幂等粒度 = 类型 + 行为参数:reason 不入键,且键文本与批 4 前
        逐字节一致(字段 metadata 排除,决策层屏蔽/计数粒度零漂移)。"""
        k_default = action_key(PrepSellBench(slot=3))
        k_filled = action_key(PrepSellBench(slot=3, reason='line_switch_collapse'))
        assert k_default == k_filled == "SellBench({'slot': 3})"
        # 对照:BailToOuter.reason 是载荷(非归因),必须入键。
        assert action_key(BailToOuter(reason='a')) != \
            action_key(BailToOuter())

    def test_decisions_transcription_carries_reason(self):
        """decisions 行动作转录(既有转录面,全字段平铺):reason 键加法
        出现且随值透传;旧读端 .get 容忍缺键(schema 纪律「新字段末尾
        追加且可选」)。T-159 登记行:PrepAction.route_tag(发射臂路线
        标签,kw_only 载体)同入转录——决策/遥测消费端均为 dict .get
        容忍面,加法增益零判定面。"""
        d0 = serialize_action(PrepSellBench(slot=1))
        assert d0 == {'route_tag': '', 'slot': 1, 'reason': '',
                      '__type__': 'SellBench'}
        d1 = serialize_action(
            PrepSellBench(slot=1, reason='line_switch_collapse'))
        assert d1['reason'] == 'line_switch_collapse'

    def test_plain_reason_does_not_extend_convert_exemption_face(self):
        """sim 检查器豁免面收敛(check_no_same_round_buy_sell 镜像):
        非特化集值(含已退役通道值)与 '' 同罪(同轮买后卖仍报);
        ADR-0611 按键分工(§3-5)后转化类豁免改读 convert_reason 结构化键,
        reason 载体上的特化值同样不豁免(豁免面只收窄不放大)。"""
        from sr_od.application.currency_war.sim.checks.ledger import (
            check_no_same_round_buy_sell,
        )
        row = {'plane': 1, 'round_num': 1,
               'actions': [
                   {'__type__': 'BuyCard',
                    'card': {'name': 'X'}, 'reason': ''},
                   {'__type__': 'SellBench', 'name': 'X',
                    'sell_reason': 'funding_support'}]}
        assert check_no_same_round_buy_sell([row]), \
            '非特化值误入豁免面 = 同轮自旋检查被架空'
        # reason 载体上的特化值(转换键)不再豁免(分工:转化类读
        # convert_reason,零双源);reason 只保留孤儿键 line_switch_
        # collapse 的分支(见 test_cw_stall_protect.Test7)。
        row_reason_carry = {'plane': 1, 'round_num': 1,
                            'actions': [
                                {'__type__': 'BuyCard',
                                 'card': {'name': 'X'}, 'reason': ''},
                                {'__type__': 'SellBench', 'name': 'X',
                                 'sell_reason': 'funding_support_stall_convert'}]}
        assert check_no_same_round_buy_sell([row_reason_carry]), \
            'reason 载体特化值仍豁免 = 按键分工未生效(C3)'
        row_ok = {'plane': 1, 'round_num': 1,
                  'actions': [
                      {'__type__': 'BuyCard',
                       'card': {'name': 'X'}, 'reason': ''},
                      {'__type__': 'SellBench', 'name': 'X',
                       'convert_reason': 'funding_support_stall_convert'}]}
        assert not check_no_same_round_buy_sell([row_ok]), \
            '结构化键豁免边被误收窄(批 3 转化类语义回归)'

    # (test_replay_diff_rendering_ignores_reason 已随面退役(T-122 波 5b;
    #  被测 cw_replay --diff 渲染面 _fmt/_fmt_json 随旧格式回放重建退役
    #  于 T-98 段②删除——锁与所辖面同批退役,test_cw_replay_session_restore
    #  先例;退役背书 = reviews/T-98-r1.md ④#5。))

    def test_shadow_adapter_fingerprint_aligned_with_action_key(self):
        """影子适配器指纹面(V2-02 清单 B「需映射」判定点,批 4 已映射):
        action_to_atomop 与 action_key 消费同一 metadata 单一源——reason
        字段不入指纹,任意值下 op_key 与批 4 前逐字节一致
        ('sell_bench:3'),填充/删除都不分裂同槽动作的幂等键。红时语义 =
        有人改动了指纹的字段选择规则,先核对 action_key 同规再动。"""
        k0 = action_to_atomop(PrepSellBench(slot=3)).op_key
        k1 = action_to_atomop(
            PrepSellBench(slot=3, reason='funding_support')).op_key
        assert k0 == k1 == 'sell_bench:3'


# ===== 发射位载体现状锁(2026-09-08 归因遥测删除批)=====


class TestEmissionFace:
    """发射位 reason 现状锁:纯归因值(通道名/转化特化)填充已全撤
    (缺省 '' 未标),唯一在役填充 = line_switch_collapse 证明载体
    (端到端锁 = TestLineSwitchOrphanSeed18 与 test_cw_sell_window_
    launch.test_line_switch_orphan_interest_sell_marked)。红时语义 =
    归因填充回流或发射行为位移,处置 = 对照删除指令裁决,非机械跟绿。
    销账类行为面(T3 转化类出口①)在本类保留行为断言。"""

    def test_shop_interest_pullback_unmarked(self):
        """shop 凑息回拉位:gold<g* ∧ 线外燃料 ⇒ 卖出发射(行为不变),
        非孤儿帧 reason 缺省 ''('interest_pullback' 已拆;孤儿帧打标
        由 test_cw_sell_window_launch 正格锁辖)。"""
        sess = _sess()
        act = decide_shop_action(
            cw4_bs(_state(1, [_bc(_FUEL, slot=1)]), sess),
            sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, ShopSellBench)
        assert act.reason == ''
        assert act.expect == _FUEL

    def test_shop_funding_plain_emits_unmarked(self):
        """shop funding 位 plain 分支:买断制覆写(g*=0)令凑息臂
        not_needed、血线不动 ⇒ 凑息让位,筹资卖出线外燃料(发射行为
        不变);plain 分键计数与 'funding_support' 填充已拆。"""
        sess = _sess()
        sess.active_strategies = ['买断制']   # ADR-0598 注入面迁移(下同)
        act = decide_shop_action(
            cw4_bs(_state(1, [_bc(_FUEL, slot=1)]), sess),
            sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, ShopSellBench)
        assert act.reason == ''
        ct = state_of(sess).cw4_counters
        assert 'funding_support_plain_sell' not in ct
        assert 'funding_support_stall_convert' not in ct

    def test_prep_interest_emit_unmarked(self):
        """prep 凑息位(mandate ②(a) 接线):卖出发射行为不变,载体字段
        reason(归因面)缺省 ''(归因枚举填充已拆);发射计数键零断链。
        T-159 登记行:Emitted.reason 改载 route_tag = 'interest_prep'
        (发射臂构造事实,S1 清键路由消费,非归因遥测——治理立场 =
        内部路由键非放行证据,§3.3)。"""
        sess = _sess()
        bench = [_bc(_FUEL, slot=1)]
        frame = _boarded_frame(
            gold=9, level=3, bench=bench, deploy_cap=4,
            node_type=None, stop_flag=False, k_members=('目标件',),
            round_num=2)
        out = mandate.run_mandate(frame, sess,
                                  state=_boarded(gold=9, level=3,
                                                 hp=80, round_num=2))
        sells = _prep_emit_out(out)
        assert len(sells) == 1
        assert sells[0].action.reason == ''
        assert sells[0].reason == 'interest_prep'
        assert state_of(sess).cw4_counters.get('t1_interest_prep_emit') == 1

    def test_prep_m4_frees_seat_unmarked(self):
        """prep M4 腾席位(mandate M2 重试环):plain/T3 两形态卖出发射
        不变,载体字段 reason(归因面)缺省 '';T3 帧销账行为保留(出口
        ①)。买断制覆写关凑息臂(裸 session g* 高,gold<g* 会让 ②(a)
        先于 M2 清空燃料面,隔离本位的发射臂)。T-159 登记行:Emitted.
        reason 改载 route_tag = 'm4_fuel_sell'(白名单内,落地经路径
        (i) 清 S1 开店闩)。"""
        k = ('目标件',)
        # plain:9 个互异线外 1★ 燃料,victim = 序首。
        sess = _sess()
        sess.active_strategies = ['买断制']   # ADR-0598 注入面迁移(下同)
        bench = [_bc(f'燃料{i}', slot=i) for i in range(1, 10)]
        frame = _boarded_frame(
            gold=30, level=3, bench=bench, deploy_cap=4,
            node_type=None, stop_flag=False, k_members=k, round_num=2)
        out = mandate.run_mandate(frame, sess,
                                  state=_boarded(gold=30, level=3,
                                                 hp=80, round_num=2))
        sells = _prep_emit_out(out)
        assert len(sells) == 1
        assert sells[0].action.reason == ''
        assert sells[0].reason == 'm4_fuel_sell'
        # T3 特化:8 张 3★ 非燃料 + 唯一被保垫件 ⇒ victim = 垫件。
        sess2 = _sess()
        sess2.active_strategies = ['买断制']   # ADR-0598 注入面迁移(下同)
        assert sell_gate.register_launch(sess2, '垫保F',
                                         cause='stall_protect', round_num=2)
        bench2 = [_bc(f'高价{i}', star=3, slot=i) for i in range(1, 9)]
        bench2.append(_bc('垫保F', slot=9))
        frame2 = _boarded_frame(
            gold=30, level=3, bench=bench2, deploy_cap=4,
            node_type=None, stop_flag=False, k_members=k, round_num=2)
        out2 = mandate.run_mandate(frame2, sess2,
                                   state=_boarded(gold=30, level=3,
                                                  hp=80, round_num=2))
        sells2 = _prep_emit_out(out2)
        assert len(sells2) == 1
        assert sells2[0].action.reason == ''
        assert sells2[0].reason == 'm4_fuel_sell'
        ct2 = state_of(sess2).cw4_counters
        assert ct2.get('close_on_sell') == 1   # 出口①卖出销(转化类)

    def test_prep_skeleton_funding_emit_unmarked(self):
        """prep funding 骨架-only 位(entry.emit skeleton_only 臂):
        买断制覆写关凑息臂后,筹资卖出线外燃料(发射与 funding_support
        标记位不变——发射面标记非归因);plain 分键计数与载体填充已拆。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        strat = MandateV1Strategy()
        sess = _sess()
        sess.active_strategies = ['买断制']   # ADR-0598 注入面迁移(下同)
        st = _state(0, [_bc('填充燃料F', slot=1)])
        obs = PrepObservation(state=st,
                              bench_chars=[_bc('填充燃料F', slot=1)],
                              deployed_chars=[], deploy_vacancy=0)
        out = entry.emit(obs, SimpleNamespace(), sess, None,
                         ev_arm='skeleton_only', registry=strat.registry)
        sells = _prep_emit_out(out)
        assert [s.action.slot for s in sells] == [1]
        assert sells[0].action.reason == ''
        assert sells[0].reason == ''
        assert sells[0].funding_support is True
        assert state_of(sess).cw4_counters.get(
            'funding_support_plain_sell') is None

    def test_prep_skeleton_funding_fallback_emits_unmarked(self):
        """prep funding 兜底位(骨架-only 臂):唯一 ④件主路径空 → 兜底
        变现(发射行为不变);兜底分键计数与载体填充已拆。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        strat = MandateV1Strategy()
        sess = _sess()
        sess.active_strategies = ['买断制']   # ADR-0598 注入面迁移(下同)
        st = _state(1, [_bc(_TRANS_HOLD, slot=1)])   # cost=2 → 退 2 ≥ 缺口 3−1
        obs = PrepObservation(state=st, bench_chars=[_bc(_TRANS_HOLD, slot=1)],
                              deployed_chars=[], deploy_vacancy=0)
        out = entry.emit(obs, SimpleNamespace(), sess, None,
                         ev_arm='skeleton_only', registry=strat.registry)
        sells = _prep_emit_out(out)
        assert [s.action.slot for s in sells] == [1]
        assert sells[0].action.reason == ''
        assert sells[0].reason == ''
        assert state_of(sess).cw4_counters.get('funding_hold_liquidated') \
            is None

    def test_prep_ev_funding_convert_consume_kept(self):
        """prep funding EV 位:T3 被保垫件降序放行行为不变(销账经
        T3 活跃集清空可观测);分键计数与载体填充已拆(reason '')。"""
        def _run(bench: list, sess) -> tuple[list, dict]:
            st = _boarded()
            frame = _boarded_frame(
                gold=1, level=5, bench=bench, deploy_cap=6,
                node_type=None, stop_flag=True, k_members=('线内件X',),
                round_num=2)
            out = entry._criteria_pass(frame, sess, st, ('线内件X',),
                                       k_switched=False, old_line_members=())
            return _prep_emit_out(out), state_of(sess).cw4_counters

        sess = _sess()
        sells, ct = _run([_bc('填充燃料F', slot=1)], sess)
        assert [s.action.slot for s in sells] == [1]
        assert sells[0].action.reason == ''
        assert sells[0].reason == ''
        assert ct.get('funding_support_plain_sell') is None
        # T3 特化:唯一燃料 = 被保垫件(defer 降序放行,转化类),
        # 放行卖出即销账 ⇒ T3 活跃集清空(τ=同轮,须在登记轮现读)。
        sess2 = _sess()
        assert sell_gate.register_launch(sess2, '填充燃料F',
                                         cause='stall_protect', round_num=2)
        sells2, ct2 = _run([_bc('填充燃料F', slot=1)], sess2)
        assert [s.action.slot for s in sells2] == [1]
        assert sells2[0].action.reason == ''
        assert ct2.get('funding_support_stall_convert') is None
        assert sell_gate.stall_protect_active(sess2, 2) == frozenset()

    def test_prep_ev_funding_fallback_emits_unmarked(self):
        """prep funding EV 兜底位:兜底变现发射行为不变;兜底分键计数
        与载体填充已拆。"""
        sess = _sess()
        st = _boarded()
        bench = [_bc(_TRANS_HOLD, slot=1)]
        frame = _boarded_frame(
            gold=1, level=5, bench=bench, deploy_cap=6,
            node_type=None, stop_flag=True, k_members=('线内件X',),
            round_num=2)
        out = entry._criteria_pass(frame, sess, st, ('线内件X',),
                                   k_switched=False, old_line_members=())
        sells = _prep_emit_out(out)
        assert [s.action.slot for s in sells] == [1]
        assert sells[0].action.reason == ''
        assert sells[0].reason == ''
        assert state_of(sess).cw4_counters.get('funding_hold_liquidated') \
            is None

    def test_prep_line_switch_collapse_dual_write(self):
        """prep 换线塌缩位(entry._criteria_pass):k_switched 帧旧线
        燃料件(U_X/V_MS 注入态保守子集)= 'line_switch_collapse';
        载体与标记双写。"""
        sess = _sess()
        st = _boarded(gold=30)
        bench = [_bc(_FUEL, slot=1)]
        frame = _boarded_frame(
            gold=30, level=5, bench=bench, deploy_cap=6,
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

    def test_core_seat_vacate_unmarked(self):
        """C1 恒买腾席发射位(T-115 恒买腾席批,ADR-0580;方案 v2 §5.4):
        席满帧腾席卖出发射行为不变,载体字段 reason 缺省 ''(唯一在役
        填充仍 = 孤儿证明标记),expect = victim。基数(实测口径):
        本类测试方法 HEAD 基数 9 → 本位 10(方案文面「9→10」即实测态;
        对抗审 B8 的「现有 10」系未实测误记,勿沿袭)。"""
        from sr_od.application.currency_war.kernel.cw_state import ShopCard
        sess = _sess()
        bench = [_bc('目标件', slot=1), _bc(_FUEL, slot=2)] + [
            _bc(f'燃料{i}', slot=i + 1) for i in range(3, 10)]
        st = _state(45, bench)
        st.shop = [ShopCard(x=100, name='希儿', cost=3, star=1)]
        act = decide_shop_action(cw4_bs(st, sess), sess,
                                 SimpleNamespace(ev_arm='full'))
        assert isinstance(act, ShopSellBench)
        assert act.reason == ''
        assert act.expect == _FUEL


# ===== 孤儿标记端到端首发点锁(T-141;ADR-0591;种子锚历史见测试 docstring)=====


class TestLineSwitchOrphanSeed18:
    """ci_smoke 慢锁 no_same_round_buy_sell 预存红(seed18 p1r1)的发射侧
    闭合证据:义务买入(青雀,m2_line_member)当轮 K 支持度重排致成员出
    基座 = P78-2a 线账闭合,其后的凑息回拉清算行带
    sell_reason='line_switch_collapse'(引擎转录面),检查器豁免面据此
    分键;决策轨迹逐位不变(reason 不进决策输入,渲染面免疫 =
    TestSerializationEquivalence.test_replay_diff_rendering_ignores_
    reason)。种子锚同责(README 纪律 12):策略行为位移致形态消失时,
    红 = 重选探针种子,非机械跟绿。"""

    def test_seed89_p1r3_orphan_sell_marked(self):
        """no_same_round_buy_sell 预存红的发射侧闭合证据:义务买入当轮
        K 支持度重排致成员出基座 = P78-2a 线账闭合,其后的凑息回拉清算
        行带 sell_reason='line_switch_collapse'(引擎转录面),检查器
        豁免面据此分键;决策轨迹逐位不变(reason 不进决策输入,渲染面
        免疫 = TestSerializationEquivalence.test_replay_diff_rendering_
        ignores_reason)。种子锚同责(README 纪律 12):策略行为位移致
        形态消失时,红 = 重跑探针重选种子,非机械跟绿。
        种子锚历史(T-32 空板止损守卫位移):原 seed18 形态在 p1r1 开局
        空板凑息清算帧——守卫(待卖后 deployed 为空 ⇒ 拒卖)按设计拦截
        空板帧卖出,标记形态移至非空板帧;探针重扫(seed 0-109,守卫
        生效树)命中 {56: p1r2/艾丝妲, 89: p1r3/桑博},取最小 56。
        种子锚历史(W6 波 4 黑板容器化位移):引擎 RNG 消费序列再位移,
        seed 56 p1r2 形态消失;重跑探针(seed 0-199)全局面仅命中
        {89: p1r3/桑博}(不变式在线,非机械跟绿),锚移 89。"""
        from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
        res = simulate_p1(89, pool='snapshot')
        sells = [a for row in res.ledger
                 if row.get('plane') == 1 and row.get('round_num') == 3
                 for a in (row.get('actions') or [])
                 if a.get('__type__') == 'SellBench']
        marked = [a for a in sells
                  if a.get('sell_reason') == 'line_switch_collapse']
        assert marked, \
            f'p1r3 卖出行未见孤儿标记(形态消失则重跑探针重选种子): {sells}'
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
        st = _boarded(gold=1, level=3, round_num=3, hp=80)
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

    _MANIFEST: dict[str, int] = {'entry.py': 3, 'mandate.py': 3, 'shop.py': 7}
    # T-159 加行登记:entry.py +1 = 迁移 B 席满前置谓词的腾席卖(①位
    # spheres 分支,装配 A channel='m4_fuel' 同源);mandate.py +1 =
    # 迁移 A wanted 消费臂腿 2(M4 卖角色,同源候选)。两新消费位排除
    # 集均出自 sell_exclusions 单一入口,非手搓。
    # T-115 加行登记(恒买腾席批,ADR-0580):shop.py +1 = C1/④ 三腿
    # 共享腾席 victim 探测 helper(_core_victim,唯一 exclude_names=
    # 落点;金闸双桶探测与席满腾席共享同一装配,帧内惰性缓存)。排除集
    # 出自 sell_exclusions(channel='m4_fuel')单一入口,与 M2 缺员/
    # m2_stockpile 两腾席位同源,非手搓。
    # T-20 加行登记(P92 席可落收窄批):shop.py +1 = p92_seat_
    # recoverable 席可落判定(exclude_names 出自 sell_exclusions
    #(channel='m4_fuel')单一入口,与腾席臂同参,非手搓;被收窄退役的
    # 旧 P56 投影金额代理不走 exclude_names= 装配,不占本清单口径)。

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
