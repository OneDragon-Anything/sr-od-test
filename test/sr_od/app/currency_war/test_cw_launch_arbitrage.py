"""发射帧受限消费仲裁锁面(出口 B 溢出段;金出口族 DESIGN v1.1 §3.2,
落码裁决 = ADR-0566)。

锁面结构:
1. 判定核锁:``in_launch_spend_zone`` 区判(与必花域共享 g* 单一源,
   买断制出辖)+ 等价扫描;``launch_arbitration_gate`` 单动作预算闸
   (P70 Δ息=0 形:花后金位 ≥ g*,花穿息线部分出辖 = p70 边界 1);
2. 消费面单一源锁:engine_p1/cw_loop 源内 ``launch_arbitrage_`` 分键
   全部经 kernel 常量消费(禁字面量散写第二源);
3. 生产位次契约锁(v1.1 I-2 钉死):cw_loop 源内仲裁调用点 = 浮层在场
   闸之后、发射核调用之前(「确将发射」路径独占),弃射 defect 分键
   挂 stale 分支内;
4. 生产仲裁段行为锁:``_launch_frame_arbitration`` 全分支(预检未过/
   带内不开店/溢出开店→受限访问→关店/开店失败/访问失败 abort/预算闸
   闭包接线/后验跌破检测)。

真 sim 账本的仲裁行为形态锁 = test_cw_sim_launch_sink.py(锁 3/4,同
批重推),本文件不重复。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel import cw_launch_arbitrage
from sr_od.application.currency_war.kernel.cw_economy import (
    cap_resolved_of_session,
    in_launch_spend_zone,
    in_must_spend_zone,
    saturation_line,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    CloseShop,
    LevelUpShop,
    RefreshShop,
    SellBench,
    ShopCard,
)


def _session(gold_frame: int, *, cap_override: int | None = None):
    """最小 session 桩:策略状态(计数器 + cap 覆写)+ 期望态黑板。"""
    st = SimpleNamespace(cw4_cap_override=cap_override, cw4_counters={})
    sess = SimpleNamespace(strategy_state=st,
                           shop_state_frame=SimpleNamespace(gold=gold_frame))
    return sess


def _card(cost: int | None = 3) -> BuyCard:
    return BuyCard(card=ShopCard(x=0, faction='?', name='某件', cost=cost,
                                 star=1), reason='test')


class TestLaunchSpendZone:
    """判定锁:发射帧溢出段区判(出口 B 触发面)。"""

    def test_zone_sweep_equals_saturation_formula(self):
        """全域等价:in_launch_spend_zone(g, s) ≡ g > saturation_line(
        cap_resolved_of_session(s))(单一源内聚,禁第二套判式)。"""
        sess = _session(0, cap_override=5)
        for gold in (0, 1, 49, 50, 51, 100, 10 ** 6):
            assert in_launch_spend_zone(gold, sess) == \
                (gold > saturation_line(cap_resolved_of_session(sess))), gold

    def test_zone_boundary_and_buyout_scope(self):
        """边界:恰 g* 不入域(溢出 = 严格大于);买断制(cap=0)出辖
        恒 False(与必花域 §2.1 同口径)。"""
        assert in_launch_spend_zone(50, _session(50, cap_override=5)) is False
        assert in_launch_spend_zone(51, _session(51, cap_override=5)) is True
        assert in_launch_spend_zone(10 ** 6, _session(0, cap_override=0)) \
            is False

    def test_zone_shares_g_star_with_must_spend(self):
        """与必花域同 g* 同帧同值(共享 saturation_line 链;两域辖域不同
        禁并键,但判定值恒等是单一源的直接推论)。"""
        sess = _session(0, cap_override=5)
        for gold in (49, 50, 51, 200):
            assert in_launch_spend_zone(gold, sess) == \
                in_must_spend_zone(gold, sess), gold


class TestLaunchArbitrationGate:
    """判定锁:单动作预算闸(P70 Δ息=0 形)。"""

    def test_buy_keeping_gold_above_g_star_allowed(self):
        sess = _session(0, cap_override=5)   # g* = 50
        ok, why = cw_launch_arbitrage.launch_arbitration_gate(
            _card(3), 53, sess)
        assert ok is True and why == ''

    def test_buy_crossing_g_star_blocked(self):
        """花后跌破 g* ⇒ 拒(花穿息线部分出辖,p70 边界 1)。"""
        sess = _session(0, cap_override=5)
        ok, why = cw_launch_arbitrage.launch_arbitration_gate(
            _card(3), 52, sess)
        assert ok is False
        assert why == cw_launch_arbitrage.GATE_BLOCKED_REASON

    def test_boundary_spend_to_exact_g_star_allowed(self):
        """花后恰落 g* 仍在域内(Δ息=0;息账以 min(g,10·cap) 计,50 全额
        生息,非跌破)。"""
        sess = _session(0, cap_override=5)
        ok, _ = cw_launch_arbitrage.launch_arbitration_gate(_card(2), 52, sess)
        assert ok is True

    def test_levelup_and_refresh_gated_by_batch_cost(self):
        """升级(整批单击金 = cost 属性)与刷新按各自成本闸。"""
        sess = _session(0, cap_override=5)
        lv = LevelUpShop(cost=4, auth_basis='test')
        assert cw_launch_arbitrage.launch_arbitration_gate(lv, 54, sess)[0]
        assert not cw_launch_arbitrage.launch_arbitration_gate(lv, 53, sess)[0]
        rf = RefreshShop(cost=2, reason='r1')
        assert cw_launch_arbitrage.launch_arbitration_gate(rf, 52, sess)[0]
        assert not cw_launch_arbitrage.launch_arbitration_gate(rf, 51, sess)[0]

    def test_zero_cost_actions_always_allowed(self):
        """卖出/部署事务族(零成本动作)恒放行——闸辖「花」不辖「换手」;
        CloseShop 终结动作亦不辖。"""
        sess = _session(0, cap_override=5)
        sell = SellBench(bench_idx=0, income=2, expect='某件')
        for act in (sell, CloseShop()):
            ok, why = cw_launch_arbitrage.launch_arbitration_gate(act, 3, sess)
            assert ok is True and why == ''

    def test_buy_cost_fallback_conservative(self):
        """卡价缺失(None/0)⇒ 3 中费保守估(与评估栈 check_affordable
        同口径):按 3 闸,金不足 3+g* 即拒。"""
        sess = _session(0, cap_override=5)
        assert not cw_launch_arbitrage.launch_arbitration_gate(
            _card(None), 52, sess)[0]
        assert cw_launch_arbitrage.launch_arbitration_gate(
            _card(None), 53, sess)[0]


class TestSingleSourceLocks:
    """单一源锁:分键名/判定式禁字面量散写。"""

    def test_counter_keys_reference_kernel_constants_only(self):
        """engine_p1/cw_loop 源内 ``launch_arbitrage_`` 字面量只允许出现在
        常量定义(kernel)——两消费面全部经 cw_launch_arbitrage 常量
        消费(分键名单一源;判读按常量名族对账)。"""
        from one_dragon.utils.file_utils import get_project_root
        root = get_project_root()
        for rel in ('src/sr_od/application/currency_war/sim/engine_p1.py',
                    'src/sr_od/application/currency_war/operations/cw_loop.py',
                    'src/sr_od/application/currency_war/sim/checks/launch.py'):
            src = (root / rel).read_text(encoding='utf-8')
            assert "'launch_arbitrage_" not in src \
                and '"launch_arbitrage_' not in src, (
                f'{rel} 残留 launch_arbitrage_* 字面量分键(单一源锁)')

    def test_gate_blocked_reason_single_literal(self):
        """拒因键字面量只在 kernel 定义;消费面经 GATE_BLOCKED_REASON。"""
        from one_dragon.utils.file_utils import get_project_root
        root = get_project_root()
        for rel in ('src/sr_od/application/currency_war/sim/engine_p1.py',
                    'src/sr_od/application/currency_war/operations/cw_loop.py'):
            src = (root / rel).read_text(encoding='utf-8')
            assert 'launch_arbitrage_budget_blocked' not in src, (
                f'{rel} 残留拒因键字面量(单一源锁)')


class TestProductionPositionContract:
    """生产位次契约锁(v1.1 I-2 钉死;DESIGN §3.2 载体)。

    仲裁调用点 = 「确将发射」路径独占:armed 判定 → 浮层在场闸
    (readiness_overlay_hold 计数写)→ 仲裁段 → 发射核
    readiness_battle_launch。结构锚用源序断言(与既有源级锁同法)。
    """

    @staticmethod
    def _src() -> str:
        from one_dragon.utils.file_utils import get_project_root
        return (get_project_root()
                / 'src/sr_od/application/currency_war/operations/cw_loop.py'
                ).read_text(encoding='utf-8')

    def test_arbitration_sits_between_overlay_gate_and_launch(self):
        src = self._src()
        i_hold = src.index("counters['readiness_overlay_hold']")
        i_arb = src.index('_arb = _launch_frame_arbitration(self)')
        i_launch = src.index('readiness_battle_launch(self, self.ctx)')
        assert i_hold < i_arb < i_launch, (
            '仲裁调用点必须在浮层闸之后、发射核之前(位次契约)')

    def test_abandoned_launch_key_inside_stale_branch(self):
        """弃射 defect 分键 = stale 分支辖域(仲裁切屏 ∧ 屏态复验未过的
        可辨识残量),且分键经 kernel 常量消费。"""
        src = self._src()
        i_arb = src.index('_arb = _launch_frame_arbitration(self)')
        i_stale = src.index("if _detail_r == 'readiness_stale_screen':",
                            i_arb)
        i_end = src.index("else:", i_stale)
        seg = src[i_stale:i_end]
        assert 'KEY_ABANDONED_LAUNCH' in seg, (
            '弃射分键须在 stale 分支内(defect 残量禁静默)')
        assert '_arb.get' in seg or '_arb' in seg, (
            '弃射判定须消费仲裁报告(entered 位)')

    def test_precheck_uses_prep_anchors_single_source(self):
        """仲裁预检 = `_prep_anchors_hit`(C3 备战双锚单一源,零新参数),
        只作仲裁段的门;函数体(去 docstring)不得调用发射核。"""
        src = self._src()
        i_def = src.index('def _launch_frame_arbitration(')
        i_def_end = src.index('\ndef ', i_def + 10)
        seg = src[i_def:i_def_end]
        assert '_prep_anchors_hit(op' in seg
        # 去掉 docstring(契约文本会提到发射核名字),只查代码体
        code = seg[seg.index('"""', seg.index('"""') + 3) + 3:]
        assert 'readiness_battle_launch' not in code, (
            '仲裁段不得内联发射核(发射链零改动契约)')


class _StubRoundResult:
    def __init__(self, ok: bool):
        self.is_success = ok


class TestProductionArbitrationBehavior:
    """生产仲裁段行为锁(_launch_frame_arbitration 全分支)。"""

    def _make_op(self, monkeypatch, *, prep_hit=True, open_ok=True,
                 gold=80, hp=42, waves='ok', close_ok=True):
        """组装宿主 op 桩 + 模块缝替身(懒 import 缝 = 模块属性替换)。

        waves:'ok'=正常产出(买 1 刷 1,末金 gold−5);'fail'=waves 失败
        路径(_rr 非 None,无产出)。"""
        from sr_od.application.currency_war.operations.cw_op import (
            cw_op_buy_cards,
            cw_op_close_shop,
            cw_op_open_shop,
        )
        from sr_od.application.currency_war.obs import cw_observation

        sess = _session(gold)
        calls = {'open': 0, 'close': 0, 'waves': 0, 'gate_arg': None}

        def _find_area(screen, screen_name, area_name, **kw):
            hit = prep_hit or (screen_name, area_name) != (
                '货币战争-备战', '备战标识-购买经验')
            return SimpleNamespace(is_success=hit)

        def _fake_open(op):
            calls['open'] += 1
            return _StubRoundResult(open_ok)

        def _fake_close(op):
            calls['close'] += 1
            return _StubRoundResult(close_ok)

        def _fake_waves(op, match, hp_value, hp_readable, hp_trusted, *,
                        spend_gate=None):
            calls['waves'] += 1
            calls['gate_arg'] = spend_gate
            if waves == 'fail':
                return 'FAIL', None
            outcome = SimpleNamespace(
                total_buy=1, total_level=0, total_refresh=1,
                state=SimpleNamespace(gold=gold - 5))
            return None, outcome

        monkeypatch.setattr(
            cw_observation, 'read_game_state',
            lambda *a, **k: SimpleNamespace(gold=gold, hp=hp,
                                            hp_readable=True, hp_trusted=True))
        monkeypatch.setattr(cw_op_open_shop, 'open_shop', _fake_open)
        monkeypatch.setattr(cw_op_close_shop, 'close_shop', _fake_close)
        monkeypatch.setattr(cw_op_buy_cards, 'run_buy_waves', _fake_waves)

        from sr_od.application.currency_war.operations import cw_loop
        op = SimpleNamespace(
            screenshot=lambda: object(),
            round_by_find_area=_find_area,
            ctx=SimpleNamespace(cw_match=SimpleNamespace(session=sess)),
        )
        return cw_loop, op, sess, calls

    def test_precheck_fail_skips_arbitration(self, monkeypatch):
        cw_loop, op, sess, calls = self._make_op(monkeypatch, prep_hit=False)
        report = cw_loop._launch_frame_arbitration(op)
        assert report['entered'] is False
        assert calls['open'] == 0 and calls['waves'] == 0
        assert sess.strategy_state.cw4_counters[
            cw_launch_arbitrage.KEY_PRECHECK_SKIP] == 1

    def test_inband_frame_fails_closed_without_opening_shop(self, monkeypatch):
        """带内帧(g ≤ g*)不开店不花(fail-closed;L1' 挂账),分键显影。"""
        cw_loop, op, sess, calls = self._make_op(monkeypatch, gold=40)
        report = cw_loop._launch_frame_arbitration(op)
        assert report['zone'] == 'inband' and report['entered'] is False
        assert calls['open'] == 0 and calls['waves'] == 0
        assert sess.strategy_state.cw4_counters[
            cw_launch_arbitrage.KEY_INBAND_CLOSED] == 1

    def test_overflow_frame_bounded_visit_runs(self, monkeypatch):
        """溢出帧 = 开店 → 受限访问(spend_gate 接线)→ 关店;报告与
        分键对账。"""
        cw_loop, op, sess, calls = self._make_op(monkeypatch, gold=80)
        report = cw_loop._launch_frame_arbitration(op)
        assert report['entered'] is True
        assert calls['open'] == 1 and calls['waves'] == 1 and calls['close'] == 1
        assert calls['gate_arg'] is not None, 'spend_gate 未接线'
        assert report['executed'] == 2   # total_buy + total_level + total_refresh
        assert sess.strategy_state.cw4_counters[
            cw_launch_arbitrage.KEY_ZONE_FRAMES] == 1

    def test_spend_gate_closure_blocks_crossing_spend(self, monkeypatch):
        """闸闭包消费 kernel 判定核:跨线买拒、带内买放行(读期望态黑板
        现值,闸拒计 gate_blocks + 分键)。"""
        cw_loop, op, sess, calls = self._make_op(monkeypatch, gold=80)
        cw_loop._launch_frame_arbitration(op)
        gate = calls['gate_arg']
        sess.shop_state_frame = SimpleNamespace(gold=52)
        assert gate(_card(3)) == (False,
                                  cw_launch_arbitrage.GATE_BLOCKED_REASON)
        assert sess.strategy_state.cw4_counters[
            cw_launch_arbitrage.KEY_GATE_BLOCKS] == 1
        assert gate(_card(1)) == (True, '')
        assert gate(SellBench(bench_idx=0, income=2, expect='某件')) == \
            (True, '')

    def test_open_failure_counts_and_skips(self, monkeypatch):
        cw_loop, op, sess, calls = self._make_op(monkeypatch, gold=80,
                                                 open_ok=False)
        report = cw_loop._launch_frame_arbitration(op)
        assert report['entered'] is False and calls['waves'] == 0
        assert sess.strategy_state.cw4_counters[
            cw_launch_arbitrage.KEY_OPEN_FAILED] == 1

    def test_waves_failure_aborts_without_close(self, monkeypatch):
        """访问失败路径(未识别卡停机钩子等):abort 旗置位、不关店
        (保画面交停机接管,禁发射摧毁现场)。"""
        cw_loop, op, sess, calls = self._make_op(monkeypatch, gold=80,
                                                 waves='fail')
        report = cw_loop._launch_frame_arbitration(op)
        assert report.get('abort') is True
        assert calls['close'] == 0

    def test_close_failure_reported_not_raised(self, monkeypatch):
        """关店未生效 = 交发射核屏态复验裁定的残量路径,不抛异常。"""
        cw_loop, op, sess, calls = self._make_op(monkeypatch, gold=80,
                                                 close_ok=False)
        report = cw_loop._launch_frame_arbitration(op)
        assert report['entered'] is True

    def test_cross_line_counter_on_overshoot(self, monkeypatch):
        """后验跌破检测:执行侧末金 < g*(投影外成本)⇒ cross_line 分键
        响亮暴露(正常恒 0)。"""
        cw_loop, op, sess, calls = self._make_op(monkeypatch, gold=80)
        # 末金 30 < g*=50:outcome.state.gold 直接给跌破形态
        calls_holder = calls

        def _fake_waves(op, match, hp_value, hp_readable, hp_trusted, *,
                        spend_gate=None):
            calls_holder['waves'] += 1
            return None, SimpleNamespace(
                total_buy=1, total_level=0, total_refresh=0,
                state=SimpleNamespace(gold=30))

        from sr_od.application.currency_war.operations.cw_op import (
            cw_op_buy_cards,
        )
        monkeypatch.setattr(cw_op_buy_cards, 'run_buy_waves', _fake_waves)
        cw_loop._launch_frame_arbitration(op)
        assert sess.strategy_state.cw4_counters[
            cw_launch_arbitrage.KEY_CROSS_LINE] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
