"""货币战争 overlay 两段式判定/识别对账行/兜底清空(overlay-trigger 3.4)
实机外循环面行为锁。

锁面(3.4 评审 M2 裁定:锁**真实现** ``CwLoop._resolve_frame_identity``/
``_fallback_clear_pending``——loop 大方法零桩整跑成本高,身份判定段已
提取为纯函数,测试锁函数本体而非复刻表达式):

- B1 回归:对账行路径(含 contextlib 模块级 import)任意轮次可入,
  不再依赖 iter%10 块的函数局部名;
- B2 回归:aha 类底屏锚条目(screen_name = 备战 ∉ 分发候选集)不参与
  两段式——两段式只考虑 screen_name ∈ CW_DISPATCH_SCREENS 的条目,
  防命中备战名落入无备战臂的身份分发死循环;
- 两段式:pending 首中优先 / 未中落全扫描(反应式兜底不变)/ 命中
  预测屏时零对账行、未中时 arbitrate 对账行;
- 兜底清空:清 pending 不清簿记、pending 空零副作用、sim 态直跳;
- M1 回归(sim):settle_confirm 登记 fortune → 节点窗起点先落底层屏
  (battle → 备战)再查呈现门——fortune 在备战底层收口消费,节点屏
  不被吞、resume 不悬挂(评审复现形态)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.operations.cw_loop as loop_mod
from sr_od.application.currency_war.kernel.cw_game_state import (
    consume_defect_sink,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_overlay_register import (
    KIND_SCREEN_NAMES,
    register_screen_change,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.operations.cw_loop import CwLoop


@pytest.fixture(autouse=True)
def _drain_defect_buffer():
    consume_defect_sink()
    yield
    consume_defect_sink()


def _loop_shell(test_context) -> CwLoop:
    """CwLoop 最小壳(身份判定函数只消费 ctx.cw_match.session;
    __new__ 绕过重型构造,round 基建不入桩面)。"""
    shell = CwLoop.__new__(CwLoop)
    shell.ctx = test_context
    return shell


@pytest.fixture
def live_loop(test_context, monkeypatch):
    """实机态(is_target_screen/get_match_screen_name 可桩)+ 挂局。"""
    session = StrategySession()
    gs = game_state_of(session)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    shell = _loop_shell(test_context)
    return shell, gs


class TestTwoStageRealImpl:
    """两段式 + 对账行:锁 ``_resolve_frame_identity`` 真实现。"""

    def test_pending_first_hit_takes_priority(self, live_loop, monkeypatch):
        """pending 候选屏 is_target_screen 命中 → 取该名(预测优先);
        同帧全扫描不跑(提速本义)。"""
        shell, gs = live_loop
        register_screen_change(
            gs, 'megastar', KIND_SCREEN_NAMES['megastar'], 't')
        monkeypatch.setattr(
            loop_mod, 'is_target_screen',
            lambda ctx, screen, screen_name=None, **kw:
            screen_name == KIND_SCREEN_NAMES['megastar'])
        full_scans: list = []
        monkeypatch.setattr(
            loop_mod, 'get_match_screen_name',
            lambda *a, **k: full_scans.append(1) or '货币战争-补给')
        name, pred = shell._resolve_frame_identity(object())
        assert name == KIND_SCREEN_NAMES['megastar'], 'pending 首中优先'
        assert [p.kind for p in pred] == ['megastar'], '预测子集随行'
        assert full_scans == [], '首中即返,全扫描不跑'

    def test_miss_falls_back_to_full_scan_with_drift_row(
            self, live_loop, monkeypatch):
        """未中 → 全扫描兜底(反应式不变)+ arbitrate 对账行留证
        (B1 回归:对账行路径任意轮次可入,contextlib 模块级)。"""
        shell, gs = live_loop
        register_screen_change(
            gs, 'megastar', KIND_SCREEN_NAMES['megastar'], 't')
        monkeypatch.setattr(loop_mod, 'is_target_screen',
                            lambda *a, **k: False)
        monkeypatch.setattr(loop_mod, 'get_match_screen_name',
                            lambda *a, **k: '货币战争-补给')
        # 连续两次(B1 形态:原实现 iter%10 内函数局部 import 在非 10
        # 倍数轮 UnboundLocalError;提取函数 + 模块级 import 后任意次可入)。
        name1, _ = shell._resolve_frame_identity(object())
        name2, _ = shell._resolve_frame_identity(object())
        assert name1 == name2 == '货币战争-补给', '未中 → 全扫描兜底'

    def test_hit_prediction_no_drift_row(self, live_loop, monkeypatch):
        """实扫命中预测屏(全扫描路径同屏)= 静默,零对账行。"""
        shell, gs = live_loop
        register_screen_change(
            gs, 'megastar', KIND_SCREEN_NAMES['megastar'], 't')
        monkeypatch.setattr(loop_mod, 'is_target_screen',
                            lambda *a, **k: False)
        monkeypatch.setattr(
            loop_mod, 'get_match_screen_name',
            lambda *a, **k: KIND_SCREEN_NAMES['megastar'])
        name, _ = shell._resolve_frame_identity(object())
        assert name == KIND_SCREEN_NAMES['megastar']
        seq = gs.write_seq   # 零对账行:note_obs_event 不占新版本
        shell._resolve_frame_identity(object())
        assert gs.write_seq == seq, '命中预测 = 静默零行'

    def test_aha_base_screen_entry_excluded_from_two_stage(
            self, live_loop, monkeypatch):
        """B2 回归:aha 条目 screen_name = 备战(底屏锚)∉ 分发候选集
        → 不参与两段式(is_target_screen 零调用该名)、预测子集排除;
        与 megastar 并存时只试 megastar。"""
        shell, gs = live_loop
        register_screen_change(gs, 'aha', KIND_SCREEN_NAMES['aha'], 't')
        register_screen_change(
            gs, 'megastar', KIND_SCREEN_NAMES['megastar'], 't')
        tried: list = []

        def _fake_target(ctx, screen, screen_name=None, **kw):
            tried.append(screen_name)
            return screen_name == KIND_SCREEN_NAMES['megastar']

        monkeypatch.setattr(loop_mod, 'is_target_screen', _fake_target)
        monkeypatch.setattr(
            loop_mod, 'get_match_screen_name',
            lambda *a, **k: KIND_SCREEN_NAMES['megastar'])
        name, pred = shell._resolve_frame_identity(object())
        assert KIND_SCREEN_NAMES['aha'] not in tried, \
            '底屏锚条目不进两段式(防备战名死循环)'
        assert [p.kind for p in pred] == ['megastar'], '候选过滤在册'
        assert name == KIND_SCREEN_NAMES['megastar']


class TestFallbackClearRealImpl:
    """兜底清空:锁 ``_fallback_clear_pending`` 真实现。"""

    def test_clears_pending_keeps_bookkeeping(self, live_loop):
        shell, gs = live_loop
        gs.screen_changes.wish_tiers_fired.add(2)
        register_screen_change(
            gs, 'fortune', KIND_SCREEN_NAMES['fortune'], 't')
        shell._fallback_clear_pending()
        assert gs.screen_changes.pending == []
        assert gs.screen_changes.wish_tiers_fired == {2}, '簿记生命周期 = 局'

    def test_empty_pending_noop(self, live_loop):
        shell, _gs = live_loop
        shell._fallback_clear_pending()   # 空 = 直跳零异常

    def test_sim_state_skips(self, test_context, monkeypatch):
        """sim 装配态(mechanical_io_allowed False)直跳:呈现即消费
        由后端收口,实机兜底清不辖。"""
        from sr_od.application.currency_war.sim import cw_sim_ports
        monkeypatch.setattr(test_context, 'cw_match',
                            SimpleNamespace(session=StrategySession()),
                            raising=False)
        shell = _loop_shell(test_context)
        monkeypatch.setattr(cw_sim_ports, '_BACKEND', object())
        try:
            shell._fallback_clear_pending()   # sim 态直跳零异常
        finally:
            monkeypatch.undo()


class TestFortuneNodeWindowM1:
    """M1 回归(sim):settle_confirm 登记 fortune → 节点窗起点先落底层
    再查呈现门(评审复现形态:原序 fortune 门对旧结算屏恒 continue,
    吞节点屏呈现 + resume='offer' 悬挂)。"""

    def test_fortune_registered_at_settle_consumed_at_battle_window(self):
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_start_battle_param,
        )
        from sr_od.application.currency_war.kernel.cw_game_state import (
            ChannelSig,
            report_node_advance,
        )
        from sr_od.application.currency_war.sim import cw_sim_ports
        from sr_od.application.currency_war.sim.cw_sim_backend import (
            SCREEN_BRIEFING,
            SCREEN_PREP,
            SCREEN_SETTLE,
            SimBackend,
            install_backend,
            uninstall_backend,
        )
        from sr_od.application.currency_war.sim.cw_sim_run_config import (
            RunConfig,
        )
        _sig = ChannelSig(family='logic_action', actor='t', mode='compute')
        b = SimBackend(seed=7, cfg=RunConfig(selected_difficulty='A8',
                                             enemy_difficulty=108))
        install_backend(b)
        try:
            b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
            b._maybe_finish_wait()
            gs = b.gs
            # P1r1(奖励)→ 出战 → 结算;黑天鹅在场使 settle_confirm 登记
            # fortune(S4 判据)——构造最小形态:直接登记(判据链另有锁)。
            out = report_action_start_battle_param(gs, SimpleNamespace(),
                                                   _sig)
            cw_sim_ports.declare_world(out.world_decl)
            b._resolve_battle()
            assert b.screen_identity() == SCREEN_SETTLE
            register_screen_change(
                gs, 'fortune', KIND_SCREEN_NAMES['fortune'],
                's4_battle_count@settle_confirm')
            # settle_confirm 推进 → P1r2(battle)节点窗起点:先落底层
            #(battle → 备战档)再查呈现门 → fortune 收口消费,节点屏不被吞。
            adv = report_node_advance(gs, trigger='settle_confirm')
            assert adv.applied
            cw_sim_ports.declare_world(adv.world_decl)
            assert b.screen_identity() == SCREEN_PREP, \
                '节点窗底层照常呈现(battle → 备战),不被 fortune 门吞'
            assert gs.screen_changes.pending == [], \
                'fortune 在备战底层收口消费(逐 kind 呈现门)'
            assert any('fortune' in str(k) and 'unmodeled' in str(v)
                       for k, v in b.disclosures.items()), '消费披露在册'
        finally:
            uninstall_backend()
