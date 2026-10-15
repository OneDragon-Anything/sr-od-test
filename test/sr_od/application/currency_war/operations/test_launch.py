"""出战发射链行为测试(前置发射决策 + 统一执行器)。

两部分(同一条「备战 → 出战」发射链的两半):

- **前置发射位**(mandate_v1 ``bridge._launch_front_check`` 单帧测试,迭代
  前置发射位判据面 14_p1 §7.2 达标臂测试组 W2 随迁新载体——发射决策宿主
  = mandate_v1 前置发射位)。测试的语义(零调参纪律:金判定直调 kernel
  单一源,断言经调用记录非手写阈值):
  - armed 绿帧 → CwActionStartBattleParam 终点意图;
  - armed ∧ 溢出段命中(首访) → 受限商店访问意图 CwActionOpenShopParam
    (普通开店形态;进出店 = 普通 OpenShop/0n 路径,访问内消费 = 策略侧
    自限,详设 §2.10——受限标记字段已随仲裁段退役)
    + 段旗置位;段内已访 → CwActionStartBattleParam(旧「访问后照发」
    跨帧等价);
  - 非 armed → None + 段旗复位(非 armed 帧零变化);
  - 质量推迟帧 → None + defer 分键;评估异常帧 → 照常发射 + eval 分键。
- **出战统一执行器**(``launch_battle_unified`` 直测,迭代统一发射判据面;
  出战执行路径现存测试 = 零(audit-executor.md §2.4 实证),本文件为首批):
  - armed 全绿 → 事实返回,无调用面私有记账(失败语义分轨);
  - stale(非备战屏) → (False, 'readiness_stale_screen') + 分键;
  - 浮层命中(遭遇 OCR 兜底路径) → (False, 'readiness_overlay_hold:…')
    + 分键;
  - resume 闩:首调部署原子序 + 置闩,次调跳过部署;
  - 非法 face 拒绝;
  - readiness_battle_launch 抽取 helper 后等价守卫(stale 形态同返回)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war import prep_actions
from sr_od.application.currency_war.kernel import cw_economy, cw_launch_admission
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionOpenShopParam,
    CwActionStartBattleParam,
)
from sr_od.application.currency_war.operations import cw_loop
from sr_od.application.currency_war.operations.cw_loop import (
    launch_battle_unified,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    _launch_front_check,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# ==================== 前置发射位(bridge._launch_front_check)====================

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


def _mk_session_base() -> SimpleNamespace:
    session = SimpleNamespace(last_streak=0, active_strategies=[])
    gs = game_state_of(session)
    gs.observe(gs.gold, 50, sig=_sig())
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


def test_front_zone_first_visit_emits_restricted_open_shop(monkeypatch) -> None:
    """armed ∧ 溢出段命中(首访)→ 受限访问意图(普通开店形态)+ 段旗
    置位。受限标记字段随仲裁段退役(详设 §2.10):发射 =
    普通 OpenShop 动作,访问内消费由策略侧自限接管(测试面 =
    test_shop_launch_spend_selflimit)。"""
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


# ==================== 出战统一执行器(launch_battle_unified)====================

PREP_HITS = {('货币战争-备战', '备战标识-购买经验'),
             ('货币战争-备战', '按钮-出战')}


class _Frame:
    """一帧截图的桩:hits = 命中的 (画面名, 区名) 集合;ocr_hit = 遭遇 OCR。"""

    def __init__(self, hits=(), ocr_hit: bool = False) -> None:
        self.hits = set(hits)
        self.ocr_hit = ocr_hit


class _StubOp:
    """op 桩:脚本化帧序列 + 锚/OCR 应答(实现执行路径零真实点击)。"""

    def __init__(self, frames: list[_Frame]) -> None:
        self._frames = list(frames)

    def screenshot(self):
        return self._frames.pop(0)

    def round_by_find_area(self, screen, screen_name, area, crop_first=False):
        return SimpleNamespace(is_success=(screen_name, area) in screen.hits)

    def round_by_ocr(self, screen, text, lcs_percent=0.5):
        return SimpleNamespace(is_success=screen.ocr_hit)


class _StubExecutor:
    """PrepActionExecutor 替身:记录执行序列,CwActionStartBattleParam 置发射事实。"""

    instances: list[_StubExecutor] = []

    def __init__(self, op, ctx) -> None:
        self.executed: list[object] = []
        self.last_launch_ok = False
        self.last_detail = ''
        _StubExecutor.instances.append(self)

    def execute(self, action) -> None:
        self.executed.append(action)
        if isinstance(action, CwActionStartBattleParam):
            self.last_launch_ok = True
            self.last_detail = 'stub 出战已点击'


@pytest.fixture()
def launch_env(monkeypatch):
    """公共桩:分键容器 + 部署计划桩 + 执行器替身 + 身份分发桩(逐测重置)。"""
    counters: dict[str, int] = {}
    state = SimpleNamespace(cw4_counters=counters, target_comp=None)
    monkeypatch.setattr(cw_loop, 'strategy_state_of', lambda s: state)
    monkeypatch.setattr(cw_loop, 'get_match_screen_name',
                        lambda ctx, screen, screen_name_list: None)
    deploy_calls: list[int] = []

    def _moves(session):
        deploy_calls.append(1)
        return [object(), object()]

    monkeypatch.setattr(cw_loop, '_battle_chain_deploy_moves', _moves)
    monkeypatch.setattr(prep_actions, 'PrepActionExecutor', _StubExecutor)
    _StubExecutor.instances = []
    ctx = SimpleNamespace(cw_match=SimpleNamespace(session=object()))
    return SimpleNamespace(counters=counters, ctx=ctx, deploy_calls=deploy_calls)


def test_unified_armed_green_and_fail_track_split(launch_env, monkeypatch) -> None:
    """armed 全绿:复验→浮层→部署原子序→CwActionStartBattleParam;失败记账不入执行器
    (readiness_launch_fail 归调用方,分轨判据)。"""
    monkeypatch.setattr(cw_loop, '_prep_anchors_hit',
                        lambda op, screen: PREP_HITS.issubset(screen.hits))
    op = _StubOp([_Frame(hits=PREP_HITS)])
    ok, detail = launch_battle_unified(op, launch_env.ctx, face='armed')
    assert ok is True and '出战' in detail
    assert len(_StubExecutor.instances) == 1
    assert any(isinstance(a, CwActionStartBattleParam)
               for a in _StubExecutor.instances[0].executed)
    assert 'readiness_launch_fail' not in launch_env.counters, '分轨:记账归调用方'


def test_unified_stale_rejects(launch_env) -> None:
    """stale:非备战屏 → (False, 'readiness_stale_screen') + 分键,零执行。"""
    op = _StubOp([_Frame(hits=set())])
    ok, detail = launch_battle_unified(op, launch_env.ctx, face='armed')
    assert (ok, detail) == (False, 'readiness_stale_screen')
    assert launch_env.counters['readiness_stale_screen'] == 1
    assert _StubExecutor.instances == [], 'stale 帧零执行'


def test_unified_overlay_hold_rejects(launch_env) -> None:
    """浮层命中(遭遇 OCR 兜底路径)→ (False, 'readiness_overlay_hold:…')
    + 分键,零执行——误触防护载体内嵌验证。"""
    op = _StubOp([_Frame(hits=PREP_HITS, ocr_hit=True)])
    ok, detail = launch_battle_unified(op, launch_env.ctx, face='armed')
    assert ok is False
    assert detail.startswith('readiness_overlay_hold:'), detail
    assert '遭遇选择面板' in detail
    assert launch_env.counters['readiness_overlay_hold'] == 1
    assert _StubExecutor.instances == [], '浮层帧零执行'


def test_unified_resume_latch(launch_env) -> None:
    """resume 闩:首调部署原子序 + 置闩;次调跳过部署、CwActionStartBattleParam 照发。"""
    op = _StubOp([_Frame(hits=PREP_HITS), _Frame(hits=PREP_HITS)])
    ok1, _ = launch_battle_unified(op, launch_env.ctx, face='resume')
    assert ok1 is True
    assert op._cw_locked_sync_done is True, '首调置闩'
    assert launch_env.deploy_calls == [1], '首调部署原子序一次'
    ok2, _ = launch_battle_unified(op, launch_env.ctx, face='resume')
    assert ok2 is True
    assert launch_env.deploy_calls == [1], '闩后部署原子序不再现算'
    assert len(_StubExecutor.instances) == 2, '两调各一次 CwActionStartBattleParam 执行'


def test_unified_invalid_face_rejected(launch_env) -> None:
    """非法 face = 参数错误拒绝(禁静默兜底成某一面)。"""
    with pytest.raises(ValueError):
        launch_battle_unified(_StubOp([_Frame()]), launch_env.ctx, face='x')
