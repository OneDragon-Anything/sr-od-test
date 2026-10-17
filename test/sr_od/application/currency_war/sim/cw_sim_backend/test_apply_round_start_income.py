"""sim 常规轮首利息接线测试(镜像 src = sim/cw_sim_backend.py 的
apply_round_start_income 接线;同文件兄弟扑满结算腿测试 =
本目录 test_resolve_battle.py,按被测方法拆目录规范落位)。

测试面依据 = 迭代 T-27 公司契约利息累计触发设计(v2.3 定稿)§2.4 + §4.4 + §4.6:
- **常规轮首接线**(须经 sim 引擎窗口路径落写,设计 §4.4——record 无
  内建幂等,幂等守卫住 ``_begin_node_window``,函数级直调会双加):
  逐节点窗口累计、同节点窗重放零双加、跨阈发放一次不重发;
- **cap/flat 修饰**(设计 §4.6):利息上调局计数按 resolved cap
  (注册表直调 10);买断制(cap 0)+ 狸财经狸(flat 2)局每节点
  +2——cap 0 被 ``or`` 真值折叠回缺省 5 的最高危陷阱由此显影
  (期望现算自 kernel 公式单一源,禁手抄)。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py(在册超限
拆分债文件,禁追加,只 import 复用不改;先例 = 本目录
test_reward_ore_panel.py)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import cw4_box
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _drive_env_grant_step,
    _drive_until,
)

from sr_od.application.currency_war.kernel.cw_economy import (
    interest,
    interest_cap_resolved,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    aggregate_economy,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_ENV,
    SimBackend,
    apply_round_start_income,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_ENV = '公司契约'
_CHAR = '托帕&账账'
_INTEREST_KEY = 'interest_threshold'


def _interest_backend(seed: int = 23) -> SimBackend:
    """开局选公司契约环境的装配后端(调用方负责 uninstall;装配形态
    先例 = test_sim_backend._env_grant_backend)。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_invest_env_param,
    )
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     [_ENV, '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return b


def _topa_count(gs) -> int:
    """备战席托帕&账账 1★ 计数(发放/重发断言面)。"""
    return sum(1 for s in gs.bench.value.slots
               if s is not None and s.kind == 'unit' and s.unit is not None
               and s.unit.char_id == _CHAR and s.unit.star == 1)


def test_interest_account_via_engine_window_and_threshold_grant(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """常规轮首接线真窗口路径(T-27 设计 §4.4):逐节点窗开累计息账;
    同节点窗重放(``_begin_node_window`` 二次调用)零双加——幂等守卫
    住窗口收口,不在收入函数内;跨阈节点窗发放恰一次(托帕&账账 1★
    入席 + done 封账),后续窗口不再重发。金库经容器直写抬到利息满档区
    (测试缝:引擎轮首收入读容器现值算息,抬金使每节点息 = 满档 5,
    阈值 40 在 P1 内可达,免跨位面推进)。"""
    b = _interest_backend()
    try:
        gs = b.gs
        assert gs.effects.interest_earned == 0, '开局零基线'
        gs.write_logic(gs.gold, 200, produced_by='Test',
                       evidence='t:gold', sig=_SIG)
        # 推进至累计息入 35+ 档(每窗 +5;窗口路径落写的存在性由此显影)
        _drive_until(b, lambda: gs.effects.interest_earned >= 35)
        # 窗口重放:同节点窗二次打开零双加(幂等守卫住窗口)
        before = gs.effects.interest_earned
        b._begin_node_window()
        assert gs.effects.interest_earned == before, \
            f'同节点窗重放零双加: {before} -> {gs.effects.interest_earned}'
        # 跨阈节点:计数达 40 → 发放一次(bench +1 个 1★ 托帕&账账 +
        # done 封账);后续窗口不再重发
        _drive_until(b, lambda: gs.env_grants_done.value is not None
                     and (_ENV, _INTEREST_KEY) in gs.env_grants_done.value)
        assert gs.effects.interest_earned >= 40, '跨阈即发(不欠账)'
        assert _topa_count(gs) == 1, '发放恰一次 1★ 入席'
        # 后续窗口不重发(done 封账;计数继续累计不触发第二笔)
        _drive_env_grant_step(b)
        _drive_env_grant_step(b)
        assert _topa_count(gs) == 1, '后续窗口不重发(done 封账)'
    finally:
        uninstall_backend()


@pytest.mark.parametrize('strategies,expected_fn', [
    # 利息上调:cap 覆写 10(注册表直调),金 100 → 息 = min(100//10,10)
    (('利息上调',), lambda: interest(100, interest_cap_resolved(
        aggregate_economy(['利息上调']).interest_cap_override))),
    # 买断制(cap 0)+ 狸财经狸(flat 2):息通道关,仅 flat 计息
    # ——cap 0 若被 or 折叠回缺省 5,期望 2 vs 实算 7 显影
    (('买断制', '狸财经狸'), lambda: interest(100, interest_cap_resolved(
        aggregate_economy(['买断制', '狸财经狸']).interest_cap_override))
     + aggregate_economy(['买断制', '狸财经狸']).interest_flat_per_node),
])
def test_interest_account_cap_and_flat_modifiers(
        strategies: tuple[str, ...], expected_fn) -> None:
    """cap/flat 修饰经收入函数入账(T-27 设计 §4.6,直调收入应用点:
    修饰面单元锁,幂等面归引擎窗口锁):利息上调局计数按 resolved cap;
    买断制+狸财经狸局每节点 +2。期望现算自 kernel 公式单一源
    (aggregate_economy ← active_strategies,live 推算支同源)。"""
    gs = cw4_box(gold=100, active_env=_ENV, active_strategies=strategies)
    expected = expected_fn()
    applied = apply_round_start_income(gs, plane=1, round_num=2,
                                       node_type='reward', streak=0)
    assert applied.row.interest == expected, '息分量 = 公式现算'
    assert gs.effects.interest_earned == expected, '计数 = 息分量入账'
