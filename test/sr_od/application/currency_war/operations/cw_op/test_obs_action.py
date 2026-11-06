"""重观察动作测试(CwActionObs):策略发射 → 请求新鲜观察,scope 选口径。

出处 = docs/develop/sr_od/application/currency_war/flow/action_exec.md §3
(备战单动作消费·重观察通道)+ screens/prep.md §4(循环形态·读屏点
已登记例外)。零真实 IO:op 级 = 桩宿主(SimpleNamespace,同
test_prep_action_ops harness 形状);环级 = 桩策略 + 实例级重观察桩
(同 test_prep_pipeline 消费端形状)。

测试面清单:
1. 注册表语义:obs 行非终结 + terminal_wait=0(决策环续跑的形状前提;
   终结集等价测试归 test_action_registry,此处校验 obs 自身行);
2. op 行为(in_place 口径):宿主重观察恰一次 + round_success(零点击);
   自上报接入调用(零写函数被桩捕获);
3. overlay bail:重观察回执 event_overlay 非空 → CwObsOverlayBail
   (tag 透传;自上报已在 bail 前完成 = 发出即记账);
4. 域能力守卫:env.op 未接通 reobserve_in_visit → AssertionError 响亮;
   scope 拼错值 → op 内守卫断言(值域闭集 OBS_SCOPES);
5. 环级接入调用:桩策略 [Obs(in_place), Obs(outer_loop)] → in_place 经注册表
   派发执行(重观察恰一次 + 帧代次标 full)+ 循环续跑;outer_loop 在 F3
   之前拦截交回外循环(不进执行器,行为 = 原 HoldFrame 收编,
   用户裁定 2026-09-20)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import run_node

from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PrepObservation,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionObsParam,
)
from sr_od.application.currency_war.operations.cw_op.cw_action_registry import (
    action_op_class_for,
)
from sr_od.application.currency_war.operations.cw_op.cw_obs_action import (
    CwActionObsOp,
    CwObsOverlayBail,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)
from sr_od.application.currency_war.prep_actions import PrepActionExecutor
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CurrencyWarMatch,
)

# ===== 1. 注册表语义(obs 自身行)=====

def test_obs_row_resolves_non_terminal():
    """obs 注册行 = 非终结(terminal=False/terminal_wait=0):终结判定读
    注册表类属性,obs 缺省误标终结会把环内重观察错成交回外循环。"""
    op_cls = action_op_class_for(CwActionObsParam())
    assert op_cls is CwActionObsOp
    assert op_cls.terminal is False
    assert op_cls.terminal_wait == 0.0


# ===== 2/3/4. op 行为(桩宿主)=====

class _ObsHost(SimpleNamespace):
    """桩宿主:reobserve_in_visit 回放脚本(记录调用)。"""

    def __init__(self, returns: list[PrepObservation]) -> None:
        super().__init__(reobserve_calls=[])
        self._returns = returns

    def reobserve_in_visit(self) -> PrepObservation:
        self.reobserve_calls.append(1)
        return self._returns.pop(0)


def _make_env(host: object) -> SimpleNamespace:
    return SimpleNamespace(op=host, match=None, config=None)


def test_obs_op_runs_host_reobserve_once_and_succeeds(monkeypatch):
    """op 行为:宿主重观察恰一次 → round_success(零点击零拖拽);
    自上报接入调用:零写函数恰一次且 param 原样透传(发出即记账统一形态)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_obs_action as mod

    reported: list = []
    monkeypatch.setattr(mod, 'game_state_from_ctx',
                        lambda ctx: SimpleNamespace(sentinel='gs'))
    monkeypatch.setattr(mod, 'report_action_obs_param',
                        lambda gs, param, sig: reported.append(param))
    host = _ObsHost([PrepObservation()])
    op = CwActionObsOp(SimpleNamespace(), CwActionObsParam(reason='probe'),
                       env=_make_env(host))
    rs = op.run()
    assert rs.is_success
    assert len(host.reobserve_calls) == 1
    assert len(reported) == 1 and reported[0].reason == 'probe'


def test_obs_op_bails_on_event_overlay(monkeypatch):
    """overlay bail:重观察回执 event_overlay 非空 → CwObsOverlayBail
    (tag 透传);自上报在 bail 前完成(发出即记账,回执行不因交回丢失)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_obs_action as mod

    monkeypatch.setattr(mod, 'game_state_from_ctx', lambda ctx: None)
    host = _ObsHost([PrepObservation(event_overlay='盛会之星')])
    op = CwActionObsOp(SimpleNamespace(), CwActionObsParam(),
                       env=_make_env(host))
    with pytest.raises(CwObsOverlayBail) as ei:
        op.run()
    assert ei.value.overlay_tag == '盛会之星'
    assert len(host.reobserve_calls) == 1


def test_obs_op_env_without_capability_loud_fails():
    """域能力守卫:env.op 未接通 reobserve_in_visit → AssertionError 响亮
    (obs 现役只在备战决策环可用;非法发射 = 策略器 bug,禁静默)。"""
    host = SimpleNamespace()   # 无 reobserve_in_visit
    op = CwActionObsOp(SimpleNamespace(), CwActionObsParam(),
                       env=_make_env(host))
    with pytest.raises(AssertionError):
        op.run()


def test_obs_scope_invalid_value_guard_assertion():
    """scope 值域守卫(执行器集中式 validate 退役进 op):拼错值 → op 内
    守卫断言 AssertionError(值域闭集单一源 = OBS_SCOPES)。outer_loop
    口径在决策循环入口分支拦截,到不了本 op——此处防线 = 派发路径的
    拼错值。"""
    op = CwActionObsOp(SimpleNamespace(), CwActionObsParam(scope='outter'),
                       env=SimpleNamespace())
    with pytest.raises(AssertionError) as ei:
        op.run()
    assert 'OBS_SCOPES' in str(ei.value), '守卫断言消息带值域单一源'


# ===== 5. 环级接入调用(桩策略 + 实例级重观察桩)=====

def test_prep_loop_obs_reobserves_in_place_and_continues(
        test_context, monkeypatch):
    """环级:策略发射 [Obs(in_place), Obs(outer_loop)] → in_place 经注册表
    派发执行(宿主重观察恰一次)+ 帧代次标 full + 循环续跑;outer_loop 在
    F3 之前拦截交回外循环(不进执行器 → 重观察仍恰一次)。

    判据四件:①重观察恰一次(outer 拦截型不触发重观察,收编自 HoldFrame
    的行为不变量);②decide 恰两次(in_place 后原地续决策,非交回);
    ③frame_class_prep == 'full'(方向重估触发,同入口帧;outer 交回路径
    不写帧代次);④交回语义文案带 outer_loop 标识。红 = outer 误进执行器 /
    in_place 被当终结交回 / 帧代次误标 none / 重观察未触发。"""

    emissions = [CwActionObsParam(reason='loop_probe'),
                 CwActionObsParam(scope='outer_loop')]
    decide_calls: list = []

    class _QueuePrepStrategy:
        """桩策略:按序回放发射队列(obs 交回口径收尾)。"""

        def decide_prep_screen(self):
            decide_calls.append(1)
            return emissions.pop(0)

    session = StrategySession()
    monkeypatch.setattr(test_context, 'cw_match',
                        CurrencyWarMatch(_QueuePrepStrategy(), session),
                        raising=False)
    op = CwScreenPrep(test_context)
    reobserve_calls: list = []

    def _fake_reobserve() -> PrepObservation:
        reobserve_calls.append(1)
        return PrepObservation()

    monkeypatch.setattr(op, 'reobserve_in_visit', _fake_reobserve)
    op._executor = PrepActionExecutor(op, test_context)
    rs = run_node(test_context, op, op.act)
    assert rs.is_success, f'环应经 obs(outer_loop) 正常交回:{rs!r}'
    assert 'outer_loop' in (rs.status or ''), f'交回语义:{rs!r}'
    assert len(reobserve_calls) == 1, f'重观察恰一次:{reobserve_calls!r}'
    assert len(decide_calls) == 2, f'obs 后原地续决策:{decide_calls!r}'
    assert game_state_of(session).frame_class_prep == 'full', (
        '重观察帧代次 = full(方向重估触发)')
