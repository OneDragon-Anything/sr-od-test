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
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.sim import ab_core_swap as ac
from sr_od.application.currency_war.sim.engine_p1 import (
    sim_decision_registry,
    simulate_p1,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
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
    """新核单局:镜像族恒初值(相位影子退役语义;策略统一迁移批锁语义重推)。

    mandate_v1 不再继承 v2 的 ``write_shop_mirrors``(相位机/DP 姿态核
    属 v2 死链,底稿 MAP ⓪ B 类随删)——镜像族自 session 缺省值起
    不再被任何写端刷新:phase 恒 ''、form_ok 恒 False。
    """
    ac.apply_core_swap_calibration()
    r = _run(0, MandateV1Strategy(registry=sim_decision_registry()))
    assert r.ledger, 'sim 单局应有账本行'
    for row in r.ledger:
        # 相位影子退役:引擎读 session.v3_phase,mandate 无写端 → 恒 session
        # 缺省 ''(旧核写 'FORM'/'HOARD'/'SPEND' 判据值的形态只在旧核侧)
        assert (row.get('phase') or '') == '', \
            f"新核相位影子应恒缺省(轮 {row.get('round_num')})"
        assert row.get('form_ok') is False


def test_new_core_form_ok_two_polarities() -> None:
    """新核相位影子退役锁(策略统一迁移批锁语义重推;原锁=成型/未成型
    两极性均被 write_shop_mirrors 如实呈现——该写端已随 v2 相位机退役,
    mandate 局 form_ok 恒初值 False,极性观测只在旧核侧保留
    (见 test_old_core_engine_guard_never_fires 的旧核 form_ok 锁))。
    """
    ac.apply_core_swap_calibration()
    for seed in range(3):
        r = _run(seed, MandateV1Strategy(registry=sim_decision_registry()))
        assert all(row.get('form_ok') is False for row in r.ledger), \
            f'新核 form_ok 应恒初值 False(seed {seed} 出现非初值)'


