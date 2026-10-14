"""发射帧受限消费·策略侧自限(flow.decide_shop_action 提案后谓词检)单帧锁:
 详设 §2.10(用户裁定:策略的
事情不进流程框架,规范正本 = flow/README §1 决策控制分层铁律;受限消费
政策单一面 = 决策入口自限,flow 闸已退役)。

锁的语义(判定数学零复制:armed 核、息线判定、预算闸谓词全部 kernel
单一源直调,断言走真实判定链非桩值——金位经缺省息帽链派生 g*):
- 受限会话帧(armed ∧ 金达息线,派生标记每帧现算;恰落线帧 = 受限,
  与 kernel 闸带内拒域对齐)政策内动作 → 提案原样发射,零受阻遥测;
- 受限会话政策外提案 → 谓词拒 → 决策改发 CwActionCloseShopParam(消费
  终止:不重咨询决策核,非改试次优,金出口族红线 5)+ 受阻遥测分键
  launch_arbitrage_gate_blocked 落 strategy_state.cw4_counters(kernel
  常量);
- 金回线内(严格低于息线)/ 非武装帧 → 现行为逐位不变(提案透传、
  零检零遥测);
- 段旗 cw4_launch_spend_visited 与派生标记互不消费:自限拒拍前后段旗值
  不变(留守语义不回退;写端单一源仍 = bridge._launch_front_check)。

并段(**受限会话经普通路径集成链**,原 test_cw_shop_launch_normal_path
并入;详设 §2.10,发射帧仲裁段退役后的行为连续性):①armed ∧ 金超息线
→ 前置发射位发普通开店动作;②普通访问内策略侧自限拒拍 → CloseShop 经
商店画面 op 统一执行路径真执行收访问;③段内已访 → 前置发射位落
CwActionStartBattleParam 正常发射。桩模式沿本文件自限锁(armed 判定核
脚本化,息线/预算闸判定不桩 = 真实单一源判定链)。
"""
from __future__ import annotations

from types import SimpleNamespace

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel import cw_launch_admission
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopPayload,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_launch_arbitrage import (
    KEY_GATE_BLOCKS,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    CwActionOpenShopParam,
    CwActionStartBattleParam,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
    _launch_front_check,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_OBS_SIG = ChannelSig(family='obs', actor='TestShopSpendSelfLimit', mode='read')
_LOGIC_SIG = ChannelSig(family='logic_action', actor='TestShopSpendSelfLimit')

# 真实判定链金位锚(空容器 active_strategies 缺省 → cap_resolved = 缺省息
# 帽档 = 息封顶金位/10 → g* = 10×cap;值源 = kernel 派生链,断言只锁金位
# 形态对应的放行/拒拍/带内三域,不引常量进断言式):
_GOLD_OVER = 60    # 溢出段;3 费买入花后在线上 → 政策内(放行域)
_GOLD_NEAR = 51    # 溢出段;同动作花后跌破息线 → 政策外(拒拍域)
_GOLD_AT_LINE = 50  # 恰落线(派生标记燃,>= 放宽;3 费买入花后跌破 → 拒拍域)
_GOLD_INBAND = 49  # 金回线内(严格低于息线,派生标记灭 = 非受限会话)

_GREEN = {'armed': True, 'quality': {'defer_by_quality': False},
          'quality_eval_error': False}
_DISARM = {'armed': False, 'quality': None, 'quality_eval_error': False}


def _proposal() -> CwActionBuyCardParam:
    """政策外形态的提案替身(3 费买入;cost 经 kernel launch_spend_cost
    口径计账)。"""
    return CwActionBuyCardParam(card=ShopCard(x=0, name='甲', cost=3))


def _write_shop_payload(session, gold: int) -> None:
    """容器在屏空牌面 + 金位观察(决策在屏前置与金读口径的满足面)。"""
    gs = game_state_of(session)
    gs.write_logic(gs.shop, ShopPayload(cards=[], refresh_probs={}),
                   produced_by='test', sig=_LOGIC_SIG)
    gs.observe(gs.gold, gold, sig=_OBS_SIG)


def _stub_core(monkeypatch, proposal):
    """决策核替身(提案发射机;留咨询记录锁「恰咨询一次 = 消费终止非
    改试次优」)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        shop as mandate_shop,
    )
    seen: list = []

    def _core(gs, sess, config, registry=None):
        seen.append(proposal)
        return proposal

    monkeypatch.setattr(mandate_shop, 'decide_shop_action', _core)
    return seen


def _strategy(monkeypatch, session, decision: dict):
    """生产策略实例(mandate_v1.bridge;decide_shop_action 不被覆写,走
    flow.py 门)。armed 判定核脚本化(kernel 函数桩点,先例 =
    test_cw_launch);息线/预算闸判定不桩 = 真实单一源判定链。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
        MandateV1Strategy,
    )
    strategy = MandateV1Strategy(
        game_state_of(session),
        SimpleNamespace(strategy_seed=None))   # 终态契约:构造注入
    # 门后内务(方向帧消费/镜像遥测)与本锁无关,桩成 no-op 保单测面窄。
    monkeypatch.setattr(strategy, '_consume_shop_direction_frame',
                        lambda: None)
    monkeypatch.setattr(strategy, 'write_shop_mirrors',
                        lambda gs, state: None)
    monkeypatch.setattr(cw_launch_admission, 'readiness_launch_decision',
                        lambda gs_, comp, *, line_members,
                        deploy_plan_available_fn: decision)
    return strategy


def test_restricted_in_policy_proposal_emitted(monkeypatch):
    """受限会话 ∧ 政策内动作(花后金位在线上)→ 提案原样发射,零受阻
    遥测(自限只拦政策外,政策内发射面零扰动)。"""
    session = StrategySession()
    _write_shop_payload(session, _GOLD_OVER)
    proposal = _proposal()
    seen = _stub_core(monkeypatch, proposal)
    strategy = _strategy(monkeypatch, session, _GREEN)

    act = strategy.decide_shop_action()

    assert act is proposal
    assert seen == [proposal], '决策核恰咨询一次'
    assert KEY_GATE_BLOCKS not in state_of(
        game_state_of(session)).cw4_counters


def test_restricted_out_of_policy_proposal_converts_to_close_shop(monkeypatch):
    """受限会话 ∧ 政策外提案(花后跌破息线)→ 谓词拒 → 决策改发
    CwActionCloseShopParam(消费终止:不重咨询决策核,非改试次优,
    红线 5)+ 受阻遥测分键落 strategy_state(kernel 常量,与 flow 闸
    同键)。"""
    session = StrategySession()
    _write_shop_payload(session, _GOLD_NEAR)
    proposal = _proposal()
    seen = _stub_core(monkeypatch, proposal)
    strategy = _strategy(monkeypatch, session, _GREEN)

    act = strategy.decide_shop_action()

    assert isinstance(act, CwActionCloseShopParam)
    assert seen == [proposal], '拒拍后不重咨询决策核(消费终止非改试次优)'
    counters = state_of(game_state_of(session)).cw4_counters
    assert counters.get(KEY_GATE_BLOCKS) == 1


def test_at_line_frame_treated_restricted(monkeypatch):
    """恰落线帧(金 == g*)→ 派生标记燃(>= 放宽)→ 谓词检生效:3 费
    提案花后跌破息线 → 拒 → CwActionCloseShopParam + 受阻分键。与旧闸
    带内拒域对齐(闸在 gold == g* 帧拒一切正成本动作),闸退役后同边界
    不失守;入段判定(前置发射位严格 >)不动。"""
    session = StrategySession()
    _write_shop_payload(session, _GOLD_AT_LINE)
    proposal = _proposal()
    seen = _stub_core(monkeypatch, proposal)
    strategy = _strategy(monkeypatch, session, _GREEN)

    act = strategy.decide_shop_action()

    assert isinstance(act, CwActionCloseShopParam)
    assert seen == [proposal], '拒拍后不重咨询决策核(消费终止非改试次优)'
    counters = state_of(game_state_of(session)).cw4_counters
    assert counters.get(KEY_GATE_BLOCKS) == 1


def test_inband_frame_behavior_unchanged(monkeypatch):
    """金回线内(严格低于息线,派生标记灭)→ 提案透传(即便花后会跌破
    息线),零检零遥测 = 非受限会话现行为逐位不变(闸辖域外禁咨询)。"""
    session = StrategySession()
    _write_shop_payload(session, _GOLD_INBAND)
    proposal = _proposal()
    seen = _stub_core(monkeypatch, proposal)
    strategy = _strategy(monkeypatch, session, _GREEN)

    act = strategy.decide_shop_action()

    assert act is proposal
    assert seen == [proposal]
    assert KEY_GATE_BLOCKS not in state_of(
        game_state_of(session)).cw4_counters


def test_disarmed_frame_behavior_unchanged(monkeypatch):
    """非武装帧(armed=False,即便金超息线)→ 提案透传,零检零遥测
    (受限标记 = armed ∧ 金超息线合取,非单条件)。"""
    session = StrategySession()
    _write_shop_payload(session, _GOLD_NEAR)
    proposal = _proposal()
    seen = _stub_core(monkeypatch, proposal)
    strategy = _strategy(monkeypatch, session, _DISARM)

    act = strategy.decide_shop_action()

    assert act is proposal
    assert seen == [proposal]
    assert KEY_GATE_BLOCKS not in state_of(
        game_state_of(session)).cw4_counters


def test_segment_flag_untouched_by_selflimit(monkeypatch):
    """段旗留守:派生标记每帧现算不消费段旗——受限会话内「段内已访」
    形态(cw4_launch_spend_visited=True)自限照常拒拍,段旗值前后不变
    (写端单一源仍 = bridge._launch_front_check,留守语义不回退)。"""
    session = StrategySession()
    _write_shop_payload(session, _GOLD_NEAR)
    state = state_of(game_state_of(session))
    state.cw4_launch_spend_visited = True   # 段内已访(前置发射位形态)
    proposal = _proposal()
    _stub_core(monkeypatch, proposal)
    strategy = _strategy(monkeypatch, session, _GREEN)

    act = strategy.decide_shop_action()

    assert isinstance(act, CwActionCloseShopParam)
    assert state.cw4_launch_spend_visited is True, '段旗留守(自限零触碰)'


# ============================================================
# 并段:受限会话经普通路径集成链(原 test_cw_shop_launch_normal_path)
# ============================================================

_GOLD_NEAR_LINE = 51   # 溢出段(> g*=50)∧ 政策外(3 费花后 48 < 50)


def test_restricted_session_normal_path_chain(monkeypatch, tmp_path):
    """受限会话普通路径全链:普通开店动作 → 访问内自限拒拍 → CloseShop
    真执行收访问 → 段内已访正常发射 StartBattle。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_card, cw4_gs

    import sr_od.application.currency_war.operations.cw_screen.cw_screen_shop as buy_mod
    from sr_od.application.currency_war.operations.cw_op.cw_close_shop_action import (
        CwActionCloseShopOp,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CurrencyWarMatch,
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
    # armed 判定核脚本化(本文件桩模式;息线/闸判定不桩 = 真实链)。
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
    monkeypatch.setattr(buy_mod, 'shop_card_click_points',
                        lambda ctx: [Point(50, 50)] * 5)   # 定长 5 槽(段首全 5 槽门)
    monkeypatch.setattr(buy_mod, 'area_center', lambda *a, **k: (0, 0))
    monkeypatch.setattr(buy_mod.time, 'sleep', lambda s: None)
    monkeypatch.setattr(buy_mod, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                                    ev_arm=''))
    monkeypatch.setattr(economy_cycle_mod, 'disclose_budget_at_shop_frame',
                        lambda *a, **k: None)

    shell = buy_mod.CwScreenShop(_Op.ctx)
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
