"""受限会话经普通路径集成锁(迭代 changes/2026-09-21-shop-refresh-terminal
详设 §2.10;发射帧仲裁段退役后的行为连续性,run-3 收口)。

链面(生产序逐拍):
①armed ∧ 金超息线 → 前置发射位发**普通**开店动作 CwActionOpenShopParam
 (进出店 = 普通 OpenShop/0n 路径;受限标记字段已随仲裁段退役,前置
 发射位不再携带受限形态);
②普通访问内策略侧自限生效:唯一提案经 kernel ``launch_arbitration_gate``
 谓词检,政策外(花后跌破息线)→ 决策改发 CwActionCloseShopParam 收
 访问(消费终止非改试次优)→ 商店画面 op 统一执行路径真执行关店;
③段内已访(段旗 cw4_launch_spend_visited)→ 前置发射位落
 CwActionStartBattleParam 正常发射。

桩模式沿 run-1 锁(test_cw_shop_launch_spend_selflimit /
test_cw_launch_front):armed 判定核脚本化(kernel 函数桩点),息线/
预算闸判定不桩 = 真实单一源判定链(空容器缺省息帽派生 g*;金锚 51 =
溢出段(严格 >)∧ 政策外(3 费花后跌破),锚值语义见 run-1 锁注释)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_launch_admission
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_launch_arbitrage import (
    KEY_GATE_BLOCKS,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionOpenShopParam,
    CwActionStartBattleParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
    _launch_front_check,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_OBS_SIG = ChannelSig(family='obs', actor='TestLaunchNormalPath', mode='read')

_GREEN = {'armed': True, 'quality': {'defer_by_quality': False},
          'quality_eval_error': False}

_GOLD_NEAR_LINE = 51   # 溢出段(> g*=50)∧ 政策外(3 费花后 48 < 50)


def test_restricted_session_normal_path_chain(monkeypatch, tmp_path):
    """受限会话普通路径全链:普通开店动作 → 访问内自限拒拍 → CloseShop
    真执行收访问 → 段内已访正常发射 StartBattle。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_card, cw4_gs

    import sr_od.application.currency_war.operations.cw_screen.cw_screen_buy_cards as buy_mod
    from sr_od.application.currency_war.operations.cw_op.cw_close_shop_action import (
        CwActionCloseShopOp,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CurrencyWarMatch,
        StrategySession,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        economy_cycle as economy_cycle_mod,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        shop as mandate_shop,
    )
    from sr_od.application.currency_war.telemetry import recorder as rec_mod
    from sr_od.application.currency_war.telemetry import state as tel_state

    # 遥测单例隔离(关店上报链 journal 面;台账行落 tmp_path,零真实副作用)。
    monkeypatch.setattr(tel_state, '_RECORDER',
                        rec_mod.TelemetryRecorder(enabled=True,
                                                  replay_dir=tmp_path))
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 't-normal-path')
    monkeypatch.setattr(tel_state, '_defect_seen', {})
    monkeypatch.setattr(tel_state, '_defect_seen_run', '')
    # armed 判定核脚本化(run-1 桩模式;息线/闸判定不桩 = 真实链)。
    monkeypatch.setattr(cw_launch_admission, 'readiness_launch_decision',
                        lambda gs_, comp, *, line_members,
                        deploy_plan_available_fn: _GREEN)

    session = StrategySession()
    proposal = CwActionBuyCardParam(card=cw4_card('甲', cost=3))
    gs = cw4_gs(session, gold=_GOLD_NEAR_LINE,
                shop=[cw4_card('甲', cost=3)])   # 守卫面:提案牌在期望态店中

    # 生产策略(mandate_v1 真实自限门);决策核替身 = 提案发射机(留咨询
    # 记录锁「消费终止非改试次优」)。
    strategy = MandateV1Strategy(
        game_state_of(session),
        SimpleNamespace(strategy_seed=None))   # 终态契约:构造注入
    monkeypatch.setattr(strategy, '_consume_shop_direction_frame',
                        lambda: None)
    monkeypatch.setattr(strategy, 'write_shop_mirrors',
                        lambda gs_, state: None)
    consults: list = []

    def _core(gs_, sess, config, registry=None):
        consults.append(proposal)
        return proposal

    monkeypatch.setattr(mandate_shop, 'decide_shop_action', _core)

    match = CurrencyWarMatch(strategy, session)
    # 会话状态载体归一:session.strategy_state = 构造接线后的同一状态对象
    # (裸 session 桩的容器附着面不依赖;宿主显式归一,先例 = 未观察流锁
    # 宿主的 strategy_state 显式置位)。
    match.session.strategy_state = state_of(gs)
    state = state_of(game_state_of(session))

    # ① 前置发射位:armed ∧ 溢出段(首访)→ 普通开店动作 + 段旗置位。
    act1 = _launch_front_check(gs)
    assert isinstance(act1, CwActionOpenShopParam), \
        '普通开店形态(进出店 = 普通 OpenShop/0n 路径,零受限字段)'
    assert state.cw4_launch_spend_visited is True, '段旗置位(每武装段至多一次)'

    # ② 普通访问内自限生效:商店画面 op 离线宿主(替身面沿未观察流锁
    # 宿主同式;关店执行位点击桩化)驱动观察 node + 决策动作 node。
    class _Ctl:

        def screenshot(self, *a, **k):
            return (0.0, b'')

        def park_cursor(self, *a, **k) -> None:
            pass

    class _Op:
        ctx = SimpleNamespace(current_instance_idx=1, cw_match=match,
                              controller=_Ctl())

    def _entry_receipt(*a, **k):
        from sr_od.application.currency_war.obs.cw_observation import (
            GameStateReadReceipt,
        )
        return GameStateReadReceipt(gold=_GOLD_NEAR_LINE, gold_readable=True,
                                    hp=100, hp_readable=True, hp_trusted=True,
                                    level=3, plane=1, round_num=2)

    close_clicks: list = []

    def _fake_close_click(self, *a, **k):
        close_clicks.append(1)
        return SimpleNamespace(is_success=True)

    monkeypatch.setattr(CwActionCloseShopOp, 'screenshot', lambda self: None)
    monkeypatch.setattr(CwActionCloseShopOp, 'round_by_find_and_click_area',
                        _fake_close_click)
    monkeypatch.setattr('time.sleep', lambda _s: None)
    monkeypatch.setattr(buy_mod, 'read_game_state', _entry_receipt)
    monkeypatch.setattr(buy_mod, 'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(buy_mod, 'shop_card_click_points', lambda ctx: [])
    monkeypatch.setattr(buy_mod, 'area_center', lambda *a, **k: (0, 0))
    monkeypatch.setattr(buy_mod.time, 'sleep', lambda s: None)
    monkeypatch.setattr(buy_mod, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                                    ev_arm=''))
    monkeypatch.setattr(economy_cycle_mod, 'disclose_budget_at_shop_frame',
                        lambda *a, **k: None)

    shell = buy_mod.CwScreenBuyCards(_Op.ctx)
    assert shell.observe().is_success
    rr = shell.act()
    assert rr.is_success, '政策外提案 → 决策改发 CloseShop 收访问(终结交回)'
    assert close_clicks == [1], '关店经统一执行路径真执行(收起点击)'
    assert consults == [proposal], '消费终止:不重咨询决策核(非改试次优)'
    assert shell.ledger.total_buy == 0, '受限访问零消费落地(提案未执行)'
    counters = state.cw4_counters
    assert counters.get(KEY_GATE_BLOCKS) == 1, '受阻分键落策略器状态(kernel 常量)'

    # ③ 段内已访 → 前置发射位落无条件发射(正常发射,金回线判定归段旗)。
    act2 = _launch_front_check(gs)
    assert isinstance(act2, CwActionStartBattleParam), \
        '段内已访 → StartBattle 正常发射(旧「访问后照发」跨帧等价)'
    assert state.cw4_launch_spend_visited is True, '段旗保持(失武装才复位)'
