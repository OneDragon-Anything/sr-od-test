"""货币战争 overlay 触发登记消费面行为锁。

锁面(消费面完成判据):
- 宿主交回:备战/商店两宿主每动作后 pending 非空 → round_success 交回;
- 两段式:pending 画面首中(实机专属;未中落全扫描兜底不变);
- 识别对账行:pending 预测 vs 实扫不一致 → journal 留证;
- 兜底清空:识别回备战底屏整列清;识别到弹窗屏不清;
- pick 上报 consume:八选卡上报消费同 kind(两世界同一行代码);
- sim 呈现:数据源 = 容器登记(pending),逐 kind 呈现门(fortune
  仅底层=备战)、aha/无模型 kind 消费披露、S6 声明改底层屏;
- 对账豁免:overlay_pending 改读容器登记。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    consume_defect_sink,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_overlay_register import (
    KIND_SCREEN_NAMES,
    clear_screen_changes,
    consume_screen_change,
    register_screen_change,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_overlay import (
    OVERLAY_PARAM_PENDING,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl

_SIG = ChannelSig(family='logic_action', actor='test', mode='compute')


@pytest.fixture(autouse=True)
def _drain_defect_buffer():
    """测试卫生:登记/呈现全程零 Field 写时无缓冲行,前后双清保持纪律。"""
    consume_defect_sink()
    yield
    consume_defect_sink()


def _backend(seed: int = 7) -> SimBackend:
    b = SimBackend(seed=seed, cfg=_CFG)
    install_backend(b)
    return b


# ============================================================ 登记消费(精确消费生命周期①)


class TestPickReportsConsume:
    """八选卡上报 consume(两世界同一行代码)。"""

    def test_eight_picks_consume_own_kind(self):
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_pick_box_card_param,
            report_action_pick_expert_invite_param,
            report_action_pick_fortune_param,
            report_action_pick_megastar_param,
            report_action_pick_partner_param,
            report_action_pick_star_tome_param,
            report_action_pick_wish_trial_param,
        )
        from sr_od.application.currency_war.kernel.cw_action_report.pick_planner import (
            report_action_pick_planner_param,
        )
        calls = [
            ('partner', report_action_pick_partner_param),
            ('megastar', report_action_pick_megastar_param),
            ('wish_trial', report_action_pick_wish_trial_param),
            ('fortune', report_action_pick_fortune_param),
            ('star_tome', report_action_pick_star_tome_param),
            ('box_card', report_action_pick_box_card_param),
            ('expert_invite', report_action_pick_expert_invite_param),
        ]
        gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        for kind, _fn in calls:
            register_screen_change(gs, kind, KIND_SCREEN_NAMES[kind], 't')
        for i, (kind, fn) in enumerate(calls):
            fn(gs, SimpleNamespace(), _SIG)
            left = [p.kind for p in gs.screen_changes.pending]
            assert kind not in left, f'{kind} 上报消费同 kind'
            assert len(left) == len(calls) - i - 1, '消费不误伤他条目'
        # planner 上报:效果腿拒出口(未路由腿型)也先 consume(消费先于
        # 腿型分派——弹窗处理事实与选择内容独立)。
        gs_p = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        register_screen_change(gs_p, 'planner',
                               KIND_SCREEN_NAMES['planner'], 't')
        report_action_pick_planner_param(
            gs_p, SimpleNamespace(leg_type=''), _SIG)
        assert gs_p.screen_changes.pending == [], 'planner 上报消费同 kind'


# ============================================================ sim 呈现面


class TestSimPresentationFromPending:
    """sim 呈现数据源 = 容器登记(逐 kind 呈现门/消费披露)。"""

    def test_megastar_and_planner_present_from_pending(self):
        """megastar/planner:登记即呈现(megastar 附候选写容器——候选源
        = 场上盛会之星成员,种子经逻辑写判据自动登记)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            Unit,
            deployed_view_sequential as _dvs,
        )
        b = _backend()
        try:
            b.gs.write_logic(
                b.gs.deployed,
                _dvs([Unit(char_id='大丽花', star=1),
                      Unit(char_id='加拉赫', star=1)], []),
                produced_by='t', evidence='t', sig=_SIG)
            assert any(p.kind == 'megastar'
                       for p in b.gs.screen_changes.pending), '判据自动登记'
            b._present_pending_overlay()
            assert b.screen_identity() == '货币战争-盛会之星'
            assert b.gs.megastar_opts.value, '候选写容器槽(呈现写点)'
            consume_screen_change(b.gs, 'megastar')
            b._dismiss_modal()
            register_screen_change(
                b.gs, 'planner', KIND_SCREEN_NAMES['planner'], 't')
            b._present_pending_overlay()
            assert b.screen_identity() == '货币战争-银狼升星'
        finally:
            uninstall_backend()

    def test_partner_consumed_with_disclosure(self):
        """partner 无 sim 观察腿(呈现即卡 observe 重试)→ 消费 + 披露;
        判据登记链经逻辑写自动触发(姬子·启行 + 三月七 上场)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            Unit,
            deployed_view_sequential as _dvs,
        )
        b = _backend()
        try:
            b.gs.write_logic(
                b.gs.deployed,
                _dvs([Unit(char_id='三月七', star=1),
                      Unit(char_id='姬子·启行', star=1)], []),
                produced_by='t', evidence='t', sig=_SIG)
            assert any(p.kind == 'partner'
                       for p in b.gs.screen_changes.pending), '判据自动登记'
            b._present_pending_overlay()
            assert b.gs.screen_changes.pending == [], '消费(不呈现)'
            assert f'{OVERLAY_PARAM_PENDING}:partner' in b.disclosures, '披露标记'
        finally:
            uninstall_backend()

    def test_fortune_gate_only_on_prep_base(self):
        """fortune 逐 kind 呈现门:底层非备战不呈现、条目存活;底层 =
        备战时呈现(用户确认口径)。"""
        b = _backend()
        try:
            b._screen = '货币战争-补给'
            register_screen_change(
                b.gs, 'fortune', KIND_SCREEN_NAMES['fortune'], 't')
            b._present_pending_overlay()
            assert b.screen_identity() == '货币战争-补给', '非备战底层不呈现'
            assert any(p.kind == 'fortune'
                       for p in b.gs.screen_changes.pending), '条目存活等待'
            b._screen = '货币战争-备战'
            b._present_pending_overlay()
            assert b.gs.screen_changes.pending == [], '底层备战时收口消费'
            assert f'{OVERLAY_PARAM_PENDING}:fortune' in b.disclosures, '呈现门收口披露'
        finally:
            uninstall_backend()

    def test_unmodeled_kinds_consumed_with_disclosure(self):
        """aha/wish_trial/star_tome 无 sim 呈现面 → 消费 + 披露(不呈现,
        防策略读空选项卡死;aha 实机 = 备战锚特殊规则,sim 近似申报)。"""
        b = _backend()
        try:
            b._screen = '货币战争-备战'
            for kind in ('aha', 'wish_trial', 'star_tome'):
                register_screen_change(
                    b.gs, kind, KIND_SCREEN_NAMES[kind], 't')
            b._present_pending_overlay()
            assert b.screen_identity() == '货币战争-备战', '零呈现'
            assert b.gs.screen_changes.pending == [], '三 kind 全消费'
            assert all(f'{OVERLAY_PARAM_PENDING}:{k}' in b.disclosures
                       for k in ('aha', 'wish_trial', 'star_tome')), \
                '逐 kind 披露留痕(aha/wish_trial/star_tome 各自键)'
        finally:
            uninstall_backend()

    def test_advance_pure_transfer_presents_expert_from_pending(self):
        """S6 声明消费:open_bookcard 纯转移声明(备战底屏)→ advance 末
        呈现检查自 pending 呈现专家邀请函(原声明特判退役)。"""
        b = _backend()
        try:
            register_screen_change(
                b.gs, 'expert_invite', KIND_SCREEN_NAMES['expert_invite'],
                'open_bookcard')
            b.advance(WorldDecl(next_screen='货币战争-备战', trigger=''))
            assert b.screen_identity() == '货币战争-备战-专家邀请函'
        finally:
            uninstall_backend()

    def test_reconcile_exempt_reads_pending(self):
        """对账豁免 overlay_pending 改读容器登记(队列呈现面退役)。"""
        b = _backend()
        try:
            assert b._reconcile_exempt_reason() != 'overlay_pending'
            register_screen_change(
                b.gs, 'planner', KIND_SCREEN_NAMES['planner'], 't')
            assert b._reconcile_exempt_reason() == 'overlay_pending'
            consume_screen_change(b.gs, 'planner')
            assert b._reconcile_exempt_reason() != 'overlay_pending'
        finally:
            uninstall_backend()


# ============================================================ 宿主交回


class TestHostHandback:
    """宿主动作后交回(确定性提前交回,取代等重观察发现)。"""

    def test_shop_act_hands_back_on_pending(self, test_context, monkeypatch):
        """商店宿主:非终结动作后 pending 非空 → round_success 交回
        (原 round_wait 让位);文案带登记事实。"""
        from one_dragon.base.geometry.point import Point
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionBuyCardParam,
            ShopCard,
        )
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            ShopVisitLedger,
        )
        from sr_od.application.currency_war.operations.cw_screen import (
            cw_screen_shop as shop_mod,
        )
        from sr_od.application.currency_war.operations.cw_screen.cw_screen_shop import (
            CwScreenShop,
        )
        session = StrategySession()
        gs = game_state_of(session)
        card = ShopCard(x=0, slot=1, name='花火', faction='?', cost=3, star=1)
        monkeypatch.setattr(shop_mod, 'note_shop_action_receipt',
                            lambda *a, **k: None)   # 回执留证不入桩面
        monkeypatch.setattr(shop_mod, 'apply_action_outcome',
                            lambda *a, **k: None)   # 访问侧账不入桩面(交回判据独立)
        monkeypatch.setattr('time.sleep', lambda _s: None)
        from sr_od.application.currency_war.kernel.cw_game_state import (
            ShopPayload,
            ShopSlot,
        )
        gs.write_logic(
            gs.shop,
            ShopPayload(cards=[ShopSlot(kind='content', card=card)]
                        + [ShopSlot(kind='empty')] * 4, refresh_probs={}),
            produced_by='t', sig=_SIG)

        class _Ctl:
            def click(self, pt) -> None:
                pass

        match = SimpleNamespace(
            session=session,
            strategy=SimpleNamespace(
                decide_shop_action=lambda: CwActionBuyCardParam(card=card)))
        ctx = SimpleNamespace(cw_match=match, controller=_Ctl())
        shell = CwScreenShop.__new__(CwScreenShop)
        shell.ctx = ctx
        shell.op_name = 'test-shop'
        shell._config = SimpleNamespace(strategy_id='mandate_v1', ev_arm='')
        shell._click_pts = [Point(50, 50)] * 5
        shell._level_btn = None
        shell._refresh_btn = None
        shell.ledger = ShopVisitLedger()
        shell._entry = SimpleNamespace(shop=None)
        shell._visit_actions = []
        shell._obs = None
        register_screen_change(
            gs, 'planner', KIND_SCREEN_NAMES['planner'], 't')
        from test.sr_od.application.currency_war._cw_helpers import (
            run_node,
        )
        rr = run_node(test_context, shell, lambda: CwScreenShop.act(shell))
        assert rr.is_success and 'overlay 登记' in (rr.status or ''), \
            'pending 非空 → round_success 交回(文案带登记事实)'
        assert gs.screen_changes.pending, '交回不清条目(消费归选卡上报)'

    def test_prep_act_hands_back_on_pending(self, test_context, monkeypatch):
        """备战宿主:非终结动作执行后 pending 非空 → round_success 交回
        外循环分发(执行器/校验桩化,锁交回判定位)。"""
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionSellBenchParam,
        )
        from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
            CwScreenPrep,
        )
        session = StrategySession()
        gs = game_state_of(session)
        monkeypatch.setattr(test_context, 'cw_match',
                            SimpleNamespace(
                                session=session,
                                strategy=SimpleNamespace(
                                    decide_prep_screen=lambda:
                                    CwActionSellBenchParam(bench_idx=0))),
                            raising=False)
        shell = CwScreenPrep.__new__(CwScreenPrep)
        shell.ctx = test_context
        shell.op_name = 'test-prep'
        from sr_od.application.currency_war.prep_actions import (
            PrepActionExecutor,
        )
        shell._executor = PrepActionExecutor(shell, test_context)
        monkeypatch.setattr(shell, '_act_execute_default',
                            lambda a: None)
        register_screen_change(
            gs, 'megastar', KIND_SCREEN_NAMES['megastar'], 't')
        from test.sr_od.application.currency_war._cw_helpers import (
            run_node,
        )
        rr = run_node(test_context, shell, lambda: CwScreenPrep.act(shell))
        assert rr.is_success and 'overlay 登记' in (rr.status or ''), \
            '备战宿主 pending 非空 → 交回外循环分发'


# ============================================================ 兜底清空


class TestPrepBaseFallbackClear:
    """识别回备战底屏兜底清空(overlay 生命周期契约(兜底清空腿))。"""

    def test_clear_drops_all_pending(self):
        gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        for kind in ('partner', 'fortune'):
            register_screen_change(gs, kind, KIND_SCREEN_NAMES[kind], 't')
        clear_screen_changes(gs)
        assert gs.screen_changes.pending == []
        assert gs.screen_changes.wish_tiers_fired == set(), \
            '兜底清只清 pending,簿记生命周期 = 局'
