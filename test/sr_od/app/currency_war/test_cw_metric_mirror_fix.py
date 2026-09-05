"""新核(mandate_v1)镜像族语义锁:phase/form_ok 恒退役缺省,form_score 有写者。

现行语义(sim 观测面补齐批任务④后):镜像族写端原属 v2 相位机/
DP 姿态核,已随 v2 底稿退役;mandate_v1 的 ``write_shop_mirrors``
恢复后**只辖 ``v3_form_score`` 一个键**(ADR-0346 deployed 连续量
口径,纯遥测)——``v3_phase``/``v3_form_ok`` 无写端的退役语义保持
不变:sim 账本读到的 phase 恒 ''(引擎读 session 缺省)、form_ok 恒
False。form_score 数值面锁 = test_cw_obs_face_batch2(直调写者,
确定性断言)。锁口径 = 结构/回显,不锁分布数值。
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
SIM_KW = {'pool': 'snapshot', 'planes': 2, 'use_refresh': True,
          'invest': False, 'p2_combat': None, 'synthesis_chain': False,
          'equip_wear_effect': 0.0}
CFG_SKEL = SimpleNamespace(ev_arm='skeleton_only')


def _mk_session(seed: int) -> StrategySession:
    """与 A/B 跑批注入通道同式(rng 派生口径一致)。"""
    return StrategySession(rng=random.Random(f'sim-p1-{seed}'))


def _run(seed: int, strat):
    return simulate_p1(seed, strategy=strat, session=_mk_session(seed),
                       config=(CFG_SKEL if isinstance(strat, MandateV1Strategy)
                               else None), **SIM_KW)


def test_new_core_mirror_family_written() -> None:
    """镜像族语义锁(多 seed):phase 恒 ''/form_ok 恒 False(退役面
    保持);form_score 为 [0,1] 浮点(写者恢复后的结构面;数值口径
    锁 = test_cw_obs_face_batch2 直调写者)。
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
            # form_score 写者恢复(任务④):每轮行应为 [0,1] 浮点
            # (恒 0 = 写者又缺位的回归信号)
            fs = row.get('form_score')
            assert isinstance(fs, (int, float)) and 0.0 <= fs <= 1.0, \
                f'form_score 应为 [0,1] 数值(seed {seed} 轮 ' \
                f"{row.get('round_num')} got {fs!r})"


