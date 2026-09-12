"""发射帧受限消费仲裁锁面(出口 B 溢出段;金出口族 DESIGN v1.1 §3.2,
落码裁决 = ADR-0566)。

收缩注记(CUT9 二次收缩:原 15 测试→8 测试;同分支变体砍,git 可复活):
- 区判:全域等价单一源锁(g > 息线公式,49/50/51 边界点在扫描列);
- 预算闸:开门/关门两向 + 升级刷新按批成本(金钱闸核心);
  花后恰落 g* 边界/零成本换手放行/卡价缺失保守估三变体砍;
- 单一源锁 + 生产位次契约(浮层闸→仲裁→发射核)静态两面留;
  预检 _prep_anchors_hit 单一源变体砍(位次锁已锚仲裁函数体);
- 生产仲裁段:带内不开店(fail-closed)+ 溢出受限访问全链(入口
  smoke)两代表留;闸闭包消费/访问失败 abort/后验跌破三变体砍。

锁面结构:
1. 判定核锁:``in_launch_spend_zone`` 区判(与必花域共享 g* 单一源)+
   ``launch_arbitration_gate`` 单动作预算闸(P70 Δ息=0 形)两向;
2. 消费面单一源锁:engine_p1/cw_loop 源内 ``launch_arbitrage_`` 分键
   全部经 kernel 常量消费(禁字面量散写第二源);
3. 生产位次契约锁(v1.1 I-2 钉死):cw_loop 源内仲裁调用点 = 浮层在场
   闸之后、发射核调用之前;
4. 生产仲裁段行为锁:带内不开店 / 溢出开店→受限访问→关店。

CUT6 瘦身批(2026-09-09):区判边界点、g* 共享推论、弃射分键辖域、
预检未过/开店失败/关店失败变体砍除——对应行为面由 op_boundary
journal 行流锁与 sim_launch_sink 形态锁互补承载。

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
    saturation_line,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BuyCard,
    LevelUpShop,
    RefreshShop,
    ShopCard,
)


def _session(gold_frame: int, *, cap_override: int | None = None):
    """最小 session 桩:策略状态(计数器)+ 息帽覆写注入 + 期望态黑板。

    注入通道 = session.active_strategies 注册表名(ADR-0598 单一源迁移;
    registry 可达值域 = 未持卡/买断制 0)。cap_override=5(=缺省档语义)
    由空持卡承载,与注册表不可达的裸 5 注入等值。"""
    strategies = {0: ['买断制']}.get(cap_override, [])
    sess = SimpleNamespace(active_strategies=list(strategies),
                           strategy_state=SimpleNamespace(cw4_counters={}),
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

    # (CUT9 收缩:原 test_boundary_spend_to_exact_g_star_allowed(花后恰
    #  落 g* 边界,开门支数据变体)/ test_zero_cost_actions_always_allowed
    #  (零成本换手不辖支)/ test_buy_cost_fallback_conservative(卡价缺失
    #  保守估支)删,2026-09-09,git 可复活。)

    def test_levelup_and_refresh_gated_by_batch_cost(self):
        """升级(整批单击金 = cost 属性)与刷新按各自成本闸。"""
        sess = _session(0, cap_override=5)
        lv = LevelUpShop(cost=4, auth_basis='test')
        assert cw_launch_arbitrage.launch_arbitration_gate(lv, 54, sess)[0]
        assert not cw_launch_arbitrage.launch_arbitration_gate(lv, 53, sess)[0]
        rf = RefreshShop(cost=2, reason='r1')
        assert cw_launch_arbitrage.launch_arbitration_gate(rf, 52, sess)[0]
        assert not cw_launch_arbitrage.launch_arbitration_gate(rf, 51, sess)[0]


class TestSingleSourceLocks:
    """单一源锁:分键名/判定式禁字面量散写。"""

    def test_counter_keys_reference_kernel_constants_only(self):
        """engine_p1/cw_loop 源内 ``launch_arbitrage_`` 字面量只允许出现在
        常量定义(kernel)——两消费面全部经 cw_launch_arbitrage 常量
        消费(分键名单一源;判读按常量名族对账)。引号前缀扫描兼辖拒因键
        launch_arbitrage_budget_blocked 等全部分键字面量(原单键窄扫描
        test_gate_blocked_reason_single_literal 为其真子集,已删)。"""
        from one_dragon.utils.file_utils import get_project_root
        root = get_project_root()
        for rel in ('src/sr_od/application/currency_war/sim/engine_p1.py',
                    'src/sr_od/application/currency_war/operations/cw_loop.py',
                    'src/sr_od/application/currency_war/sim/checks/launch.py'):
            src = (root / rel).read_text(encoding='utf-8')
            assert "'launch_arbitrage_" not in src \
                and '"launch_arbitrage_' not in src, (
                f'{rel} 残留 launch_arbitrage_* 字面量分键(单一源锁)')


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


# (CUT9 收缩:原 test_precheck_uses_prep_anchors_single_source 删
#  (2026-09-09)——预检单一源面,位次契约锁已锚仲裁函数调用点,
#  本测为其同函数体的第二静态面,git 可复活。)


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
        from sr_od.application.currency_war.obs import cw_observation
        from sr_od.application.currency_war.operations.cw_op import (
            cw_op_buy_cards,
            cw_op_close_shop,
            cw_op_open_shop,
        )

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


# (CUT9 收缩(2026-09-09,git 可复活):
#  - 原 test_spend_gate_closure_blocks_crossing_spend(闸闭包消费面:
#    kernel 判定核两向已由 TestLaunchArbitrationGate 单元锁承载);
#  - 原 test_waves_failure_aborts_without_close(访问失败 abort 保画面);
#  - 原 test_cross_line_counter_on_overshoot(后验跌破分键检测)——
#    生产段全分支三变体,代表行由带内/溢出两面承载。)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
