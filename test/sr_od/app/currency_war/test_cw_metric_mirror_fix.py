"""新核(mandate_v1)镜像族退役语义锁:相位影子/form_ok 恒 session 缺省。

现行语义:镜像族(``v3_phase``/``v3_form_ok`` 等字段)原写端
``DecisionV2Strategy.write_shop_mirrors`` 属 v2 相位机/DP 姿态核,已随 v2
底稿退役;mandate_v1 不继承任何镜像写端,sim 账本读到的 phase 恒 ''
(引擎读 session 缺省)、form_ok 恒 False。极性观测(成型/未成型两态)
只在旧核侧保留(见 test_old_core_engine_guard_never_fires 的旧核
form_ok 锁)。锁口径 = 结构/回显,不锁分布数值。
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
    """新核相位影子退役锁(多 seed;并入原两极性测试的断言面——该测试
    验证 mandate 局 form_ok 恒初值 False,与本测试同断言面)。

    mandate_v1 不再继承 v2 的 ``write_shop_mirrors``(相位机/DP 姿态核
    属 v2 死链,底稿 MAP ⓪ B 类随删)——镜像族自 session 缺省值起
    不再被任何写端刷新:phase 恒 ''、form_ok 恒 False。
    """
    ac.apply_core_swap_calibration()
    for seed in range(3):
        r = _run(seed, MandateV1Strategy(registry=sim_decision_registry()))
        assert r.ledger, 'sim 单局应有账本行'
        for row in r.ledger:
            # 相位影子退役:引擎读 session.v3_phase,mandate 无写端 → 恒 session
            # 缺省 ''(旧核写 'FORM'/'HOARD'/'SPEND' 判据值的形态只在旧核侧)
            assert (row.get('phase') or '') == '', \
                f"新核相位影子应恒缺省(seed {seed} 轮 {row.get('round_num')})"
            assert row.get('form_ok') is False, \
                f'新核 form_ok 应恒初值 False(seed {seed} 出现非初值)'


