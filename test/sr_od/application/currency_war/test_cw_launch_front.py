"""发射决策前置发射位(bridge._launch_front_check)单帧锁:迭代
前置发射位判据面(14_p1 §7.2 达标臂锁组
W2 随迁新载体——发射决策宿主 = mandate_v1 前置发射位)。

锁的语义(零调参纪律:金判定直调 kernel 单一源,断言经调用记录非手写阈值):
- armed 绿帧 → CwActionStartBattleParam 终点意图;
- armed ∧ 溢出段命中(首访) → 受限商店访问意图 CwActionOpenShopParam
  (普通开店形态;进出店 = 普通 OpenShop/0n 路径,访问内消费 = 策略侧
  自限,详设 §2.10——受限标记字段已随仲裁段退役)
  + 段旗置位;段内已访 → CwActionStartBattleParam(旧「访问后照发」跨帧等价);
- 非 armed → None + 段旗复位(非 armed 帧零变化);
- 质量推迟帧 → None + defer 分键;评估异常帧 → 照常发射 + eval 分键。
"""

from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_economy, cw_launch_admission
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionOpenShopParam,
    CwActionStartBattleParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    _launch_front_check,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_GREEN = {'armed': True, 'quality': {'defer_by_quality': False},
          'quality_eval_error': False}
_DEFER = {'armed': True, 'quality': {'defer_by_quality': True},
          'quality_eval_error': False}
_EVAL_ERR = {'armed': True, 'quality': None, 'quality_eval_error': True}
_DISARM = {'armed': False, 'quality': None, 'quality_eval_error': False}


def _sig():
    return ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _launch_host(session):
    """gs 宿主(终态管线形态):strategy_state 同源接线后返回容器——
    前置发射位已改收容器,_launch_front_check(gs)。"""
    gs = game_state_of(session)
    gs.strategy_state = state_of(session)
    return gs


def _mk_session(monkeypatch, *, decision: dict, zone: bool) -> SimpleNamespace:
    """桩 session:容器单例(金 50)+ 判定核/溢出段判定脚本化。"""
    session = SimpleNamespace(last_streak=0, active_strategies=[])
    gs = game_state_of(session)
    gs.observe(gs.gold, 50, sig=_sig())
    monkeypatch.setattr(cw_launch_admission, 'readiness_launch_decision',
                        lambda gs_, comp, *, line_members,
                        deploy_plan_available_fn: decision)
    zone_calls: list[int] = []

    def _zone(gold: int, session_) -> bool:
        zone_calls.append(gold)
        return zone

    monkeypatch.setattr(cw_economy, 'in_launch_spend_zone', _zone)
    return session


def test_front_armed_green_emits_start_battle(monkeypatch) -> None:
    """armed ∧ 金未超息线 → CwActionStartBattleParam 终点意图;金判定经 kernel 读口
    (调用记录非手写阈值——零调参纪律)。"""
    zone_calls: list[int] = []
    monkeypatch.setattr(cw_launch_admission, 'readiness_launch_decision',
                        lambda gs_, comp, *, line_members,
                        deploy_plan_available_fn: _GREEN)
    monkeypatch.setattr(cw_economy, 'in_launch_spend_zone',
                        lambda gold, session_: zone_calls.append(gold) or False)
    session = _mk_session_base()
    action = _launch_front_check(_launch_host(session))
    assert isinstance(action, CwActionStartBattleParam)
    assert zone_calls == [50], '帧级金判定直调 kernel(值源 = 容器金现读)'
    assert state_of(session).cw4_launch_spend_visited is False


def _mk_session_base() -> SimpleNamespace:
    session = SimpleNamespace(last_streak=0, active_strategies=[])
    gs = game_state_of(session)
    gs.observe(gs.gold, 50, sig=_sig())
    return session


def test_front_zone_first_visit_emits_restricted_open_shop(monkeypatch) -> None:
    """armed ∧ 溢出段命中(首访)→ 受限访问意图(普通开店形态)+ 段旗
    置位。受限标记字段随仲裁段退役(详设 §2.10):发射 =
    普通 OpenShop 动作,访问内消费由策略侧自限接管(锁面 =
    test_cw_shop_launch_normal_path)。"""
    session = _mk_session(monkeypatch, decision=_GREEN, zone=True)
    action = _launch_front_check(_launch_host(session))
    assert isinstance(action, CwActionOpenShopParam), \
        '普通开店形态(受限访问意图,零受限字段)'
    assert state_of(session).cw4_launch_spend_visited is True, '段旗置位'


def test_front_zone_second_visit_emits_start_battle(monkeypatch) -> None:
    """段内已访 → CwActionStartBattleParam(旧形态「访问后照发、无金复条件」跨帧等价;
    金不回落无死循环)。"""
    session = _mk_session(monkeypatch, decision=_GREEN, zone=True)
    state = state_of(session)
    state.cw4_launch_spend_visited = True   # 段内已访
    action = _launch_front_check(_launch_host(session))
    assert isinstance(action, CwActionStartBattleParam)
    assert state.cw4_launch_spend_visited is True


def test_front_disarm_resets_flag(monkeypatch) -> None:
    """非 armed → None(原三遍编排接管)+ 段旗复位(复位后再武装允许新段
    再访——合法形态:访问内升级抬息帽)。"""
    session = _mk_session(monkeypatch, decision=_DISARM, zone=False)
    state = state_of(session)
    state.cw4_launch_spend_visited = True   # 上一武装段遗留
    assert _launch_front_check(_launch_host(session)) is None
    assert state.cw4_launch_spend_visited is False, '失武装复位'


def test_front_quality_defer_holds(monkeypatch) -> None:
    """质量推迟帧:armed 但推迟 → None 不发射 + defer 分键(防死锁语义
    kernel 单一源,键单一源 = cw_launch_admission 常量)。"""
    session = _mk_session(monkeypatch, decision=_DEFER, zone=False)
    assert _launch_front_check(_launch_host(session)) is None
    counters = state_of(session).cw4_counters
    assert counters.get('launch_quality_defer_frames') == 1


def test_front_quality_eval_error_still_launches(monkeypatch) -> None:
    """评估异常帧:fail-open 照常发射 + eval 分键(残量禁静默,ADR-0570
    分界;与「配方不完备」常态帧单义区分)。"""
    session = _mk_session(monkeypatch, decision=_EVAL_ERR, zone=False)
    assert isinstance(_launch_front_check(_launch_host(session)), CwActionStartBattleParam)
    counters = state_of(session).cw4_counters
    assert counters.get('launch_quality_eval_error') == 1


def test_front_non_armed_chain_untouched(monkeypatch) -> None:
    """非 armed 帧返回 None = 原三遍编排接管(决定函数对非 armed 帧
    零触碰,行为与迁移前逐项一致)。"""
    session = _mk_session(monkeypatch, decision=_DISARM, zone=False)
    assert _launch_front_check(_launch_host(session)) is None
