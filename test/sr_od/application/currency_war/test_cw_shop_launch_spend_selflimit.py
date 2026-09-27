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
"""
from __future__ import annotations

from types import SimpleNamespace

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
    ShopCard,
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
    test_cw_launch_front);息线/预算闸判定不桩 = 真实单一源判定链。"""
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
