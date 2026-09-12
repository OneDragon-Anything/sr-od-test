"""T-165 振荡回归热修·同轮买卖互斥统一闩锁面(单帧锁)。

设计出处(锁纪律:新锁必引设计出处;持久归档载体 = ADR-0611,
docs/develop/sr_od/application/currency_war/decisions/0611-t165-round-mutex-unified-latch.md):
- **ADR-0611**(决策本体 §3 已实施架构/§4 申报边界/§5 落地审处置):
  L1 读源定谳 fresh_buys(§3-1)/垫保与换线孤儿双 carve-out(§3-1/§3-7)/
  L2 统一过滤位 + A4 抛错(§3-3/§3-4)/L3 convert_reason 分键(§3-5)/
  义务镜像簿载体定谳(§3-7)/C2 读端自治 fail-closed(§3-2)/
  B2② P60 换手承重声明与 L1/L2 权威序(§4);
- 方案对抗审裁决记录(A1 硬面={obligation, hold, press} 保 defer/
  A2 hold 资格拒收形态/A3 fresh_buys 考古定谳/A4 未映射臂抛错+14 键/
  B1 换线孤儿 carve/B2① 同轮孤儿买回被禁/C2 fail-closed 三分支/
  C3 按键分工零双源/C5 捷径断言删除/C6 逐臂分键显影)已收编入
  ADR-0611 §2 Considered Options 与 §5;
- ADR-0267/0328(r408 同轮互斥本体)/ ADR-0585(装配 A)/ ADR-0591 §4
  (孤儿证明打标)/ P78(math_proofs.md:INV/P78-1/P78-2/P78-5′)。

红证形态:各锁 docstring 自带「拔除对应构件后该形态复发」的机制描述,
与 ADR-0611 §5 六条变异一一对应(变异 1→L1 硬面族 / 变异 2→读源完备
性族 / 变异 3→fail-closed 族 / 变异 4→L2 全臂族 / 变异 5→豁免分键族
[宿主 = test_cw_stall_protect.Test7CheckerExemption 读端五格 +
test_cw_suspect_review.C4 复核两格;本文件 L3 只留写端值域与 D1 复盘
独家面,见 TestL3KeyingWriteEnd 类注] / 变异 6→A4 抛错族;红对全列 =
判读留痕档,持久结论以 ADR-0611 §5 为准),不另设重复红证函数。
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    fresh_buys_of,
    fresh_buys_sell_face,
    record_fresh_buy,
)
from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_state import (
    SELL_BENCH_CONVERT_REASONS,
    BuyCard,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_state import (
    SellBench as ShopSellBench,
)
from sr_od.application.currency_war.sim.checks.suspects import (
    d1_same_round_pair_review,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
    sell_gate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)
from test.sr_od.app.currency_war.test_cw_sell_window_launch import (
    _CORE_HOLD,
    _FUEL,
    _bc,
    _card,
    _sess,
    _state,
)
from test.sr_od.app.currency_war.test_cw_suspect_review import (
    _locked_target,
)

_PKG = Path(mandate.__file__).resolve().parent

#: 转化类放行键(T-165 起经 convert_reason 结构化字段填充的值域;
#: line_switch_collapse 留在 reason,C3 分工)。
_CONVERT_KEYS = SELL_BENCH_CONVERT_REASONS - {'line_switch_collapse'}


def _registry(sess) -> dict:
    return state_of(sess).cw4_fuel_filler_stall_buys


def _with_frame(sess, state) -> None:
    """黑板帧挂载(生产 last_state 写点同形;sim 用 shop_state_frame)。"""
    sess.last_state = state


def _merged_fixture() -> tuple:
    """M2b 合并完成买入帧:青雀×2 在席(1★)、第三张在店、可负担。"""
    sess = _sess()
    state_of(sess).target_comp = SimpleNamespace(
        name='测试线', core_chars=(_FUEL,), shared_chars=())
    st = GameState(gold=30, level=7, round_num=3, hp=60)
    st.plane = 2
    st.bench = [_bc(_FUEL, slot=1), _bc(_FUEL, slot=2)]
    st.deployed = []
    st.shop = [_card(_FUEL, cost=1, star=1)]
    return sess, st


# ===== L1:同轮硬面(读源 = kernel fresh_buys,全因类完备) ==========


class TestL1HardFace:
    """L1 买后禁卖硬面(ADR-0611 §3-1;读源定谳;变异 1/2 的
    红证宿主:拔 record_fresh_buy 写点或回退登记簿 press-only 读源,
    本组全红)。"""

    def test_fresh_buys_excluded_across_channels(self):
        """三因类同轮硬禁(ADR-0611 §3-1;全通道抽四):fresh_buys 名集并入
        sell_exclusions,与发射登记簿无关(独立读源,A3)——press 窗口
        未登记、身份段不含的名字,本帧买入后同轮禁卖。"""
        sess = _sess()
        st = _state(30, [], round_num=3)
        record_fresh_buy(sess, st, _FUEL)
        assert _FUEL not in sell_gate.identity_exclusions(sess, ())
        for ch in ('interest', 'funding', 'm4_fuel', 'projection'):
            assert _FUEL in sell_gate.sell_exclusions(
                sess, (), channel=ch, current_round=3), \
                f'{ch}:同轮买入可卖 = r408「买后禁卖」破面(ADR-0267)'

    def test_hold_registration_rejection_shape_covered(self):
        """hold 资格拒收形态(A2 裸奔洞,ADR-0611 §2):资格断言拒登记
        (登记簿不可见)但发射位 fresh_buys 无条件写入——L1 对拒收形
        态仍可见。红证:回退登记簿读源(变异 2)则本锁红。"""
        sess = _sess()
        st = _state(30, [], round_num=3)
        # 青雀非持有集:hold 类登记被拒(不拦发射,W5 在册语义)
        assert not sell_gate.register_launch(
            sess, _FUEL, cause='hold', round_num=3, star=1, cost=1)
        assert _FUEL not in _registry(sess)
        record_fresh_buy(sess, st, _FUEL)
        assert _FUEL in sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=3)

    def test_merge_shortcut_shape_covered(self):
        """合并捷径形态(A2/C5,ADR-0611 §2:读源换 fresh_buys 后自动闭合):
        1★ 买入补齐合成在登记之前 return——fresh_buys 写点先于捷径分支
        (考古锚,ADR-0611 §3-1),捷径形态照样入硬面;发射登记簿不开账
        (捷径语义)。红证:变异 1(拔写点)则本锁红。"""
        sess, st = _merged_fixture()
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, BuyCard) and act.reason == 'm2_merge_completion'
        assert _FUEL not in _registry(sess), \
            '合成销语义漂移:捷径买入不应开登记账(V2-05)'
        assert _FUEL in fresh_buys_of(sess, st)
        assert _FUEL in sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=3)

    def test_line_switch_orphan_carve_out(self):
        """换线孤儿 carve-out(ADR-0611 §3-7;P78-2a 账闭合事件):
        义务类登记 ∧ 已出基座 = 线账闭合,孤儿清算卖不经 L1 硬面
        (检查器 line_switch_collapse 豁免键兜住)。证据载体 = 义务镜像
        簿(轮戳跨销账存活;登记簿会被同帧更早装配 A 读点销账,禁作
        证据)。对照格:hold 类出基座不适用本 carve-out(P78 §2.1 持有
        类无时间闭合)。"""
        sess = _sess()
        st = _state(30, [], round_num=3)
        # 义务类:发射登记 + 镜像簿同步落(写点 = shop._emit_buy 义务
        # 落账同步写,单测直写同形);名不在基座(基座 = ('目标件',))。
        assert sell_gate.register_launch(sess, _FUEL, cause='obligation',
                                         round_num=3)
        sell_gate.obligation_book_of(sess)[_FUEL] = 3
        record_fresh_buy(sess, st, _FUEL)
        assert _FUEL not in sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=3), \
            '孤儿清算被 L1 硬禁 = 合法换线形态被杀(B1 破面)'
        # 对照:hold 类出基座仍硬禁(线账闭合不注销持有账)
        sess2 = _sess()
        assert sell_gate.register_launch(sess2, _CORE_HOLD, cause='hold',
                                         round_num=3, star=1, cost=3)
        record_fresh_buy(sess2, st, _CORE_HOLD)
        assert _CORE_HOLD in sell_gate.sell_exclusions(
            sess2, (), channel='interest', current_round=3)


class TestL1CarveOutAndFailClosed:
    """垫保 carve-out(A1)与 fail-closed 轮号自治(C2)。"""

    def test_stall_protect_names_carved_out_hard_face(self):
        """垫保 defer 放行保持(ADR-0611 §3-1;硬排除杀转化类 = 在册
        语义破面):stall_protect 登记活跃名即使 fresh_bought 也从硬面
        剔除,继续走 defer 视图(凑息绝对跳过/M4·funding 降序放行)。"""
        sess = _sess()
        st = _state(30, [], round_num=3)
        assert sell_gate.register_launch(sess, '垫件P', cause='stall_protect',
                                         round_num=3)
        record_fresh_buy(sess, st, '垫件P')
        for ch in ('interest', 'funding', 'm4_fuel'):
            assert '垫件P' not in sell_gate.sell_exclusions(
                sess, (), channel=ch, current_round=3), \
                f'{ch}:垫保被升硬面 = 转化类放行被杀(P78-5′ 违例)'
        assert sell_gate.stall_protect_active(sess, 3) == {'垫件P'}, \
            'defer 视图必须保持供给(降序放行判据消费端)'
        # 对照:press 登记名无 carve-out(P78-1 无对价豁免),仍硬禁。
        sess2 = _sess()
        assert sell_gate.register_launch(sess2, _FUEL, cause='press',
                                         round_num=3)
        record_fresh_buy(sess2, st, _FUEL)
        assert _FUEL in sell_gate.sell_exclusions(
            sess2, (), channel='interest', current_round=3)

    def test_round_autonomy_fail_closed_on_none(self):
        """读端轮号自治(ADR-0611 §3-2;对 V2-09 的显式翻转):黑板帧在
        而消费位漏传轮号(current_round=None)⇒ 硬面照常生效——漏接线
        不再构成静默放行。红证:变异 3(恢复 None 放行)则本锁红。"""
        sess = _sess()
        st = _state(30, [], round_num=3)
        _with_frame(sess, st)
        record_fresh_buy(sess, st, _FUEL)
        assert _FUEL in sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=None)

    def test_blackboard_missing_wholesale_fail_closed(self):
        """黑板帧不可得帧 = 排除登记当前记录 names 全集(C2 fail-closed
        分支;单记录载体,历史轮名不泄入,过度排除上界 = 单轮)。"""
        sess = _sess()   # last_state/shop_state_frame 均缺(冷会话)
        st = _state(30, [], round_num=3)
        record_fresh_buy(sess, st, _FUEL)
        assert fresh_buys_sell_face(sess) == {_FUEL}
        assert _FUEL in sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=None)
        assert _FUEL in sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=3)

    def test_phase_mismatch_expires_wholesale_zero_writeoff(self):
        """轮界自动过期 + 读取零销账(C2/§4.4 过度排除上界):黑板帧
        相位推进 = 空集(放行回池),登记记录原样保留(过期由相位失配
        整体作废,无逐名生命周期面)。"""
        sess = _sess()
        st3 = _state(30, [], round_num=3)
        record_fresh_buy(sess, st3, _FUEL)
        st4 = _state(30, [], round_num=4)
        _with_frame(sess, st4)
        assert fresh_buys_sell_face(sess) == frozenset()
        assert _FUEL not in sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=4)
        # 载体迁 ExecState(session 职责分离批同款):经访问口抽读登记记录
        reg = exec_state_of(sess).cw4_swap_fresh_buys
        assert reg['names'] == {_FUEL} and reg['phase'] == (2, 3), \
            '读端不得销账(零销账语义,与档 2 载体同形态)'

    def test_projection_view_includes_hard_face(self):
        """P78-6 读端同源随 L1 扩面:projection 视图含 L1 硬面(投影漏
        刚买件则 liquid_refund 高估 → s_reserve 低估 → 预留被吃)。"""
        sess = _sess()
        st = _state(30, [], round_num=3)
        _with_frame(sess, st)
        record_fresh_buy(sess, st, _FUEL)
        assert _FUEL in sell_gate.sell_exclusions(
            sess, (), channel='projection', current_round=3)


# ===== L2:卖后禁买全臂(统一过滤位 + 分键显影 + A4 抛错) =============


def _dominance_fixture():
    """dominance 臂可发射帧:gold>g*(60>50)、席空、青雀在店
    (线外 1★ 全额退,registry 判据自证)。"""
    sess = _sess()
    st = _state(60, [], round_num=3)
    st.shop = [_card(_FUEL, cost=1)]
    return sess, st


class TestL2AllArmsSoldFace:
    """L2 全买入臂「本轮已卖名集」消费(ADR-0611 §3-3;变异 4/6 的
    红证宿主)。行为锚 = s108 净零泵:卖 X 后同轮买回 X。"""

    def test_dominance_buy_back_blocked(self):
        """同轮卖 X → dominance 买回 X 被禁(ADR-0611 §3-3;B2① 行为锚:
        孤儿买回 = 意图内行为变更)。红证:拔 dominance 臂的统一过滤位
        (变异 4)则对照格与本格同态 = 锁红。"""
        sess, st = _dominance_fixture()
        mandate.record_round_sold(sess, st, _FUEL)
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, BuyCard) or act.reason != 'dominance_buy'
        ct = state_of(sess).cw4_counters
        assert ct.get('dominance_buy_round_sold_excluded') == 1, \
            '逐臂分键显影缺席(C6/ADR-0604 §3-5 扩域候观测键)'
        # 对照:未卖帧照常发射(过滤位只辖「本轮已卖」,不过度扩面)
        p_sess, p_st = _dominance_fixture()
        plain_act = decide_shop_action(p_st, p_sess,
                                       SimpleNamespace(ev_arm='full'))
        assert isinstance(plain_act, BuyCard) \
            and plain_act.reason == 'dominance_buy'

    def test_m2_missing_member_buy_back_blocked(self):
        """M2 义务臂同轮买回被禁(全臂 = 含义务类;按名查店内卡路径经
        _shop_candidates 同一过滤闭包,T-161 F2 单点声明)。"""
        sess = _sess()
        st = _state(30, [], round_num=3)
        st.shop = [_card('目标件', cost=1)]
        mandate.record_round_sold(sess, st, '目标件')
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, BuyCard) \
            or act.reason not in ('m2_line_member', 'm2_locked_member')
        assert state_of(sess).cw4_counters.get('m2_round_sold_excluded') == 1

    def test_unmapped_arm_raises_a4(self):
        """A4 硬闸(ADR-0611 §3-4):未登记 LAUNCH_CAUSE_BY_ARM
        的买入臂发射 = 抛错——静默跳过登记 = 新臂绕过登记与一切以字典
        为臂全集的穷举断言。演练 = 摘除一条映射模拟「新臂忘配」,端到
        端发射必须响亮报错。红证:回退 A4(恢复静默跳过)则本锁红。"""
        sess, st = _dominance_fixture()
        monkey = pytest.MonkeyPatch()
        monkey.delitem(sell_gate.LAUNCH_CAUSE_BY_ARM, 'dominance_buy')
        try:
            with pytest.raises(ValueError, match='LAUNCH_CAUSE_BY_ARM'):
                decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        finally:
            monkey.undo()

    def test_launch_map_exhaustive_over_emission_sites(self):
        """发射位穷举扫描(ADR-0611 §3-4 后半的源扫描半边):shop 域
        全部 _emit_buy 发射位的 reason 字面量 ∈ LAUNCH_CAUSE_BY_ARM
        ——新臂发射未映射 = 发射位红。映射闭集/键数/值域登记门 =
        test_cw_sell_window_launch.test_launch_cause_mapping_closed_
        contract(单一承载,2026-09-09 瘦身批亲读等价后本锁不重复)。
        P86 重推(T-177):+hub_option_buy(乙臂枢纽期权,hold 类,
        出处 = p86-proof-batch.md §3.2/§4.2;映射行随批登记)。"""
        src = (_PKG / 'shop.py').read_text(encoding='utf-8')
        calls = re.findall(r"_emit_buy\((?:[^()']|'[^']*')*\)", src)
        reasons: set[str] = set()
        for call in calls:
            reasons |= set(re.findall(r"'([a-z_0-9:]+)'", call))
        reasons.discard('card')   # 防御:位置实参变量名不入字面量集
        assert reasons <= set(sell_gate.LAUNCH_CAUSE_BY_ARM), \
            f'发射位存在未映射 reason: {sorted(reasons - set(sell_gate.LAUNCH_CAUSE_BY_ARM))}'


# ===== L3:写端分键值域 + D1 复盘独家面(读端格归主题位) =============


def _pair_row(sell_extra: dict) -> dict:
    """同轮买后卖对账本行(青雀买→卖;'target' 缺 = 名册不可解析帧)。"""
    return {'plane': 1, 'round_num': 3,
            'state': {'bench': [], 'deployed': []},
            'actions': [
                {'__type__': 'BuyCard',
                 'card': {'name': _FUEL, 'faction': '量子', 'cost': 1},
                 'reason': 'line'},
                dict({'__type__': 'SellBench', 'name': _FUEL, 'income': 1},
                     **sell_extra)]}


class TestL3KeyingWriteEnd:
    """按键分工的写端与复盘独家面(ADR-0611 §3-5)。读端豁免格由主题
    位单一承载(2026-09-09 瘦身批逐格亲读等价后收拢,禁双点维护):
    键豁免 / 缺省零容忍 / 孤儿 reason / 错误载体不豁免 / XP 同边 =
    test_cw_stall_protect.Test7CheckerExemption 五格;复核失配两
    载体(convert/孤儿)与错误载体零复核支 = test_cw_suspect_review
    .C4a/C4b。本类只留全仓无第二载体的两面(见下)。"""

    def test_emission_fill_value_domain(self):
        """发射位 convert_reason 填充值域 = 两类放行键(写端值域锁;
        line_switch_collapse 留 reason,其「双重身份」成员在检查器键集
        保留 = 单一源不拆,分工由「每键一分支、不并读」承载)。"""
        src = (_PKG / 'shop.py').read_text(encoding='utf-8')
        fills = set(re.findall(r"convert_reason=(?:\(\s*)?'([a-z_]+)'", src))
        assert fills <= set(_CONVERT_KEYS), \
            f'convert_reason 发射位填充越域: {sorted(fills - set(_CONVERT_KEYS))}'
        assert fills == {'fuel_victim_protect_demoted',
                         'funding_support_stall_convert',
                         'funding_hold_liquidated'}

    def test_d1_suspect_review_same_division(self):
        """复盘面 D1 与检查器同构:convert_reason 自报失配产可疑条目;
        evidence 带结构化键。"""
        label, _member = _locked_target()
        bad = _pair_row({'convert_reason': 'fuel_victim_protect_demoted',
                         'dec_sell_in_line': False})
        bad['target_comp'] = label
        evs = d1_same_round_pair_review([bad])
        assert len(evs) == 1 and '自报转化分键' in evs[0]['detail']
        assert evs[0]['evidence']['convert_reason'] \
            == 'fuel_victim_protect_demoted'


class TestL3EmissionAndTranscription:
    """发射位填充 + sim 账本转录面(C4;ADR-0611 §3-5/§3-6)。"""

    def test_m4_protected_victim_fills_convert_reason(self):
        """M4 腾席被保垫件末位牺牲 = T3 转化类放行位,分键恒带
        fuel_victim_protect_demoted;reason 仍为孤儿证明载体('')。"""
        from test.sr_od.app.currency_war.test_cw_sell_window_launch import (
            _bc as _bc_helper,
        )
        sess = _sess()
        assert sell_gate.register_launch(sess, '垫件P', cause='stall_protect',
                                         round_num=3)
        bench = [_bc_helper(f'高价{i}', star=3, slot=i) for i in range(1, 9)]
        bench.append(_bc_helper('垫件P', slot=9))
        st = _state(30, bench, round_num=3)
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, ShopSellBench) and act.expect == '垫件P'
        assert act.convert_reason == 'fuel_victim_protect_demoted'
        assert act.reason == ''
        assert state_of(sess).cw4_counters.get('close_on_sell') == 1, \
            '出口①卖出销行为面保留(转化类)'

    def test_plain_positions_leave_convert_reason_empty(self):
        """非放行位(凑息回拉 plain 帧)convert_reason 缺省 ''——值域
        收窄申报的发射面核查格。"""
        sess = _sess()
        bench = [_bc(_FUEL, slot=1)]
        st = _state(1, bench, round_num=3)   # gold<g*:凑息臂卖燃料
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, ShopSellBench)
        assert act.convert_reason == '' and act.reason == ''

    def test_engine_transcribes_convert_reason(self):
        """账本转录面(C4):sim 引擎 SellBench 行带 convert_reason 键,
        旧读端 .get 容忍(加法增益零判定面)。"""
        from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
        fired = {'done': False}

        class _Stub:
            def decide_shop_screen(self, sess, screen):  # noqa: ARG002
                st = sess.shop_state_frame
                idx = None
                if st is not None:
                    idx = next((i for i, b in enumerate(st.bench or [])
                                if b is not None), None)
                if not fired['done'] and idx is not None:
                    fired['done'] = True
                    return [ShopSellBench(
                        bench_idx=idx, expect='',
                        convert_reason='fuel_victim_protect_demoted')]
                return []

        res = simulate_p1(7, strategy=_Stub(), pool='fallback')
        assert fired['done'], '桩卖出未执行(形态不可达,换 seed)'
        rows = [a for row in res.ledger
                for a in (row.get('actions') or [])
                if a.get('__type__') == 'SellBench']
        assert rows and all('convert_reason' in a for a in rows), \
            '账本行缺 convert_reason 键 = 转录面断裂(C4)'
        assert any(a.get('convert_reason') == 'fuel_victim_protect_demoted'
                   for a in rows)
