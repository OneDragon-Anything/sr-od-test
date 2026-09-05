"""新核(mandate_v1)镜像族语义锁:phase/form_ok 恒退役缺省,b_t 有写者。

现行语义(form_score→B_t 口径替换后):镜像族写端原属 v2 相位机/
DP 姿态核,已随 v2 底稿退役;mandate_v1 的 ``write_shop_mirrors``
**只写 ``v3_b_t`` 一个键**(板面目标线承重计数,纯遥测;旧
``v3_form_score`` 已退役不再有写者)——``v3_phase``/``v3_form_ok``
无写端的退役语义保持不变:sim 账本读到的 phase 恒 ''(引擎读
session 缺省)、form_ok 恒 False。b_t 数值面锁 =
test_cw_obs_face_batch2(直调写者,确定性断言)+ 
test_cw_board_target_line_weight(kernel 计数正确性)。锁口径 =
结构/回显,不锁分布数值。
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
    保持);b_t 为非负整数(写者恢复后的结构面;数值口径锁 =
    test_cw_obs_face_batch2 直调写者)。旧 form_score 已退役:新行
    不应有该键(历史账本旧文件仍带,只读)。"""
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
            # b_t 写者(口径替换):每轮行应为非负整数
            bt = row.get('b_t')
            assert isinstance(bt, int) and bt >= 0, \
                f"b_t 应为非负整数(seed {seed} 轮 " \
                f"{row.get('round_num')} got {bt!r})"
            assert row.get('form_score') is None, \
                f"退役字段 form_score 不应再出现在新账本行(seed {seed} 轮 {row.get('round_num')})"
        # 局内至少一轮 b_t > 0(sim 有上场件的轮承重必非零;
        # 恒 0 = 写者又缺位的回归信号)
        assert any((row.get('b_t') or 0) > 0 for row in r.ledger), \
            f'seed {seed} 全局 b_t 恒 0 = 写者缺位回归信号'


