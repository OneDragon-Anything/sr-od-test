"""W666 · B3 deploy_after_buy 重放语境冻结锁(W652 §5 处置①)。

背景:sim 轮末先跑「真部署趟」(cw_deploy_logic.select_deployments)
再跑「重放趟」产出账本 sim.deploy_lag_units。修前重放趟吃真趟部署
后的 board/deployed——本轮自身部署改变 board 阵营计数,围栏「成对」
判据(board∪bench 计数)随之翻转,把行动语境下被围栏合法 held 的件
过判为「可上未上」(W652 取证:seed 630027/630035 r6 各 lag=2)。

修法(重放语境冻结):重放趟的成对/点火判据改用真趟行动前快照
board/deployed_fac(cw_sim 部署块 _snap_*);占位(vacancy/cap)用
部署后真实 deployed_cids。残余语义 = 「行动语境下仍有围栏认可件
未上」。
"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war.kernel import cw_deploy_logic

from sr_od.application.currency_war.sim.engine_p1 import simulate_p1

# W652 取证的两帧所在局(修前 HEAD 版重放对这两局 r6 各判 lag=2)
_SEEDS = (630027, 630035)


def _lag_frames(seed: int) -> list[tuple[int, int]]:
    """跑一局,返回逐轮 (round_num, deploy_lag_units)。"""
    res = simulate_p1(seed, pool='snapshot', planes=1)
    return [(int(row.get('round_num') or 0),
             int((row.get('sim') or {}).get('deploy_lag_units') or 0))
            for row in res.ledger]


def test_replay_context_freezed_lag_zero() -> None:
    """修后绿锁:取证两局全部轮 deploy_lag_units 恒 0。

    冻结后重放趟与真趟行动语境同判据——真趟围栏已认可的件已上场,
    残余件在行动语境下是合法 held,不再产生口径过判红。
    """
    for seed in _SEEDS:
        frames = _lag_frames(seed)
        assert all(n == 0 for _, n in frames), (seed, frames)


def test_not_deploying_mutation_still_red(monkeypatch) -> None:
    """变异锁:注入「真部署趟不部署」,检查必须仍能抓出(防修成恒 0)。

    注意:decision_v2(candidates/scoring)也调 select_deployments,
    变异只对来自 cw_sim 的调用生效,且真趟吞掉后紧随的同轮重放趟
    放行原逻辑(重放趟在冻结语境下会把真趟本应上场的件判为残留)。
    """
    orig = cw_deploy_logic.select_deployments
    state = {'replay_next': False}

    def wrapped(bench, **kw):
        caller = inspect.currentframe().f_back
        from_cw_sim = (caller is not None
                       and caller.f_globals.get('__name__', '').endswith('engine_p1'))
        if from_cw_sim:
            if state['replay_next']:
                state['replay_next'] = False
                return orig(bench, **kw)
            state['replay_next'] = True
            return [], list(range(len(bench)))
        return orig(bench, **kw)

    monkeypatch.setattr(cw_deploy_logic, 'select_deployments', wrapped)
    for seed in _SEEDS:
        state['replay_next'] = False
        frames = _lag_frames(seed)
        assert any(n > 0 for _, n in frames), (seed, frames)

