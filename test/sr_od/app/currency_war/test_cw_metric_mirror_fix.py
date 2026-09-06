"""新核(mandate_v1)镜像族语义锁:phase 恒退役缺省,form_ok/b_t 有写端。

现行语义:镜像族写端原属 v2 相位机/DP 姿态核,已随 v2 底稿退役;
mandate_v1 的 ``write_shop_mirrors`` 写 ``v3_b_t``(板面目标线承重计数)
与 ``v3_form_ok``(sim71 批死镜像处置:写端接
``cw_launch_admission.readiness_form_ok`` 板面现读,与发射 armed 判据
同式同源)——``v3_phase`` 无现读语义可接,无写端退役缺省恒 ''。
旧 ``v3_form_score`` 已退役不再有写者。b_t 数值面锁 =
test_cw_obs_face_batch2(直调写者,确定性断言) +
test_cw_board_target_line_weight(kernel 计数正确性);form_ok 正确性
细锁 = test_cw_obs_keys_sim71。锁口径 = 结构/回显,不锁分布数值。
"""
from __future__ import annotations
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import state_of

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
_SEEN_FORM_OK: list[bool] = []   # 跨 seed 聚合(死镜像回归信号判据)


def _mk_session(seed: int) -> StrategySession:
    """与 A/B 跑批注入通道同式(rng 派生口径一致)。"""
    return StrategySession(rng=random.Random(f'sim-p1-{seed}'))


def _run(seed: int, strat):
    return simulate_p1(seed, strategy=strat, session=_mk_session(seed),
                       config=(CFG_SKEL if isinstance(strat, MandateV1Strategy)
                               else None), **SIM_KW)


def test_new_core_mirror_family_written() -> None:
    """镜像族语义锁(多 seed):phase 恒 ''(无写端退役缺省);
    form_ok 为 bool 且 True 局存在(写端已接现读——恒 False =
    死镜像回归信号,恰为本批消除的缺陷形态);b_t 为非负整数。
    旧 form_score 已退役:新行不应有该键(历史账本旧文件仍带,只读)。"""
    ac.apply_core_swap_calibration()
    for seed in range(3):
        r = _run(seed, MandateV1Strategy(registry=sim_decision_registry()))
        assert r.ledger, 'sim 单局应有账本行'
        for row in r.ledger:
            # 相位影子退役:引擎读 state_of(session).v3_phase,mandate 无写端 → 恒 session
            # 缺省 ''(旧核写 'FORM'/'HOARD'/'SPEND' 判据值的形态只在旧核侧)
            assert (row.get('phase') or '') == '', \
                f"新核相位影子应恒缺省(seed {seed} 轮 {row.get('round_num')})"
            assert isinstance(row.get('form_ok'), bool), \
                f'form_ok 应为 bool 回显(seed {seed} 轮 {row.get("round_num")})'
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
        # form_ok 写端接现读的死镜像回归信号:采样局内应至少出现一次
        # True(线成型帧存在;恒 False = 写端又断回死镜像形态)
        _SEEN_FORM_OK.append(any(row.get('form_ok') for row in r.ledger))
    assert any(_SEEN_FORM_OK), \
        f'3 seed 全局 form_ok 恒 False = 死镜像回归信号({_SEEN_FORM_OK})'


