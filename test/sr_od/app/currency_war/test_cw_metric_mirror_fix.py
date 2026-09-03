"""度量修复批测试:form_ok 镜像族写点上移(新核假阴性修复)+ 旧核零漂。

背景(修复依据):镜像族(``v3_phase``/``v3_form_ok``/``v3_form_score``/
``v3_dp_posture``/储备披露)写点原内联于 ``DecisionV2Strategy._decide_shop_plan``,
``MandateV1Strategy`` 覆写 ``decide_shop_screen`` 绕过该路径 ⇒ 新核 sim
账本恒读 ``on_match_start`` 初值(form_ok 假阴性)。修复 = 写点抽为
``DecisionV2Strategy.write_shop_mirrors`` 单一源,旧核入口调用 + sim 引擎
轮首决策段按键戳(``v3_mirror_key``)判缺写补写(engine_p1 缺写守卫)。

锁(结构/回显,不锁分布数值):
- 新核 sim 单局镜像族真值写入(修复前恒初值的字段非初值);
- 可判成型/不可成型两态均被镜像如实呈现(多 seed 扫描找两极性——
  「写入」锁,不钉具体 seed/率);
- 旧核零漂:守卫对旧核不触发(engine 来源调用数=0,镜像仍由
  ``_decide_shop_plan`` 每决策段自写)。
"""
from __future__ import annotations

import random
import sys
from types import SimpleNamespace

from sr_od.application.currency_war.decision.cw4.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.decision.decision_v2.strategy import (
    DecisionV2Strategy,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.sim import ab_core_swap as ac
from sr_od.application.currency_war.sim.engine_p1 import (
    sim_decision_registry,
    simulate_p1,
)

# 与换核 A/B 正式跑批同款 sim 参数(池/位面/刷新/投资口径)
SIM_KW = dict(pool='snapshot', planes=2, use_refresh=True, invest=False,
              p2_combat=None, synthesis_chain=False, equip_wear_effect=0.0)
CFG_SKEL = SimpleNamespace(ev_arm='skeleton_only')


def _mk_session(seed: int) -> StrategySession:
    """与 A/B 跑批注入通道同式(rng 派生口径一致)。"""
    return StrategySession(rng=random.Random(f'sim-p1-{seed}'))


def _run(seed: int, strat):
    return simulate_p1(seed, strategy=strat, session=_mk_session(seed),
                       config=(CFG_SKEL if isinstance(strat, MandateV1Strategy)
                               else None), **SIM_KW)


def test_new_core_mirror_family_written() -> None:
    """新核单局:镜像族真值写入(修复前 phase 恒 ''、form_score 恒 0.0)。"""
    ac.apply_core_swap_calibration()
    r = _run(0, MandateV1Strategy(registry=sim_decision_registry()))
    assert r.ledger, 'sim 单局应有账本行'
    for row in r.ledger:
        # 修复断链点:phase 由 write_shop_mirrors 写非空判据值
        # ('FORM'/'HOARD'/'SPEND' 等),初值场景已不可能出现在轮快照
        assert row.get('phase') not in ('', None), \
            f"新核镜像 phase 未写入(轮 {row.get('round_num')})"
        assert isinstance(row.get('form_score'), float)


def test_new_core_form_ok_two_polarities() -> None:
    """可判成型/不可成型两态:多 seed 扫描,镜像两极性都能出现。

    锁「写入」不锁分布:成型与否由谓词(锁线三件套/兜底门)与板面
    真值决定,这里只断言两态在扫描窗内均被如实呈现(修复前新核
    恒 False,不可成型态是唯一可观察极性)。
    """
    ac.apply_core_swap_calibration()
    formed = unformed = 0
    for seed in range(12):
        r = _run(seed, MandateV1Strategy(registry=sim_decision_registry()))
        if any(row.get('form_ok') is True for row in r.ledger):
            formed += 1
        else:
            unformed += 1
        if formed and unformed:
            break
    assert formed >= 1 and unformed >= 1, \
        f'两态未齐(成型 {formed}/未成型 {unformed} 于 12 seed 扫描窗)'


def test_old_core_engine_guard_never_fires() -> None:
    """旧核零漂:engine 缺写守卫不触发(镜像由旧核决策核每段自写)。

    守卫只在轮键戳与当前轮不符时补写;旧核 ``_decide_shop_plan`` 在
    decide_shop_screen 内先写键戳 ⇒ engine 来源调用数恒 0(本测试
    instrument 调用来源实证),旧核行为不受引擎改动影响。
    """
    ac.apply_core_swap_calibration()
    orig = DecisionV2Strategy.write_shop_mirrors
    calls = {'engine': 0, 'strategy': 0}

    def _probe(self, state, session):
        frame = sys._getframe(1)
        src = 'engine' if frame.f_code.co_filename.endswith(
            'engine_p1.py') else 'strategy'
        calls[src] += 1
        return orig(self, state, session)

    DecisionV2Strategy.write_shop_mirrors = _probe
    try:
        r = _run(0, DecisionV2Strategy(registry=sim_decision_registry()))
    finally:
        DecisionV2Strategy.write_shop_mirrors = orig
    assert calls['engine'] == 0, \
        f"守卫对旧核触发 {calls['engine']} 次(应为 0=零漂移破坏)"
    assert calls['strategy'] > 0, '旧核决策核应每决策段自写镜像'
    assert any(row.get('form_ok') is True for row in r.ledger), \
        '旧核 seed0 应为成型局(镜像谓词与决策核同源)'
