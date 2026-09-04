"""dd-037:部署发射×执行契约接缝修(发射方谓词单一源 + no-op 状态可区分)。

根因(run 20260904_28xx 局11,G3 环级无进展守卫停机):发射方(决策核
`MandateV1Strategy._main_flow_step` 部署段)与执行方(CwOpDeploy)对
「是否还有部署可做」用不同源谓词——执行方按配方底线规则(列车≥2 档 ∧
仙舟<3 → 列车件留 bench)把候选全部留置,发射方不知道仍发射 RunDeploy;
空计划被包装成 ✓「已部署角色」→ 连续 3 环同签名动作批 ['RunDeploy'] 零推进。

修:① 发射门 = kernel `cw_deploy_logic.has_deployable`(与执行方共用
`select_deployments` 单一源),计划空不发射;② 执行器 placed=0/0 时
STATUS_NOOP / round_fail 与 STATUS_DEPLOYED 可区分。出处 =
docs/develop/currency_war/decisions/dd-037-deploy-launch-exec-contract-seam.md。
"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    has_deployable,
    select_deployments,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PrepObservation,
    RunDeploy,
    RunEquip,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
    CwOpDeploy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)


def _fac(cid: str) -> str:
    return CHARACTERS[cid].factions[0]


def _bonds_of(cid: str) -> set[str]:
    ch = CHARACTERS[cid]
    return set(ch.factions) | set(ch.flows)


def _fac_counts(cids: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for cid in cids:
        for f in sorted(_bonds_of(cid)):
            out[f] = out.get(f, 0) + 1
    return out


def _stall_replay_kwargs() -> dict:
    """局11 停机帧的注册表直读重放输入:deployed=[三月七,丹恒·饮月,爻光]
    → 列车 2 档 + 仙舟 2(日志「列车2档+仙舟2→列车件留bench」同源复核);
    bench=[姬子·启行](列车件,非在场);cap=4(deployed 3,缺 1)。"""
    deployed = ['三月七', '丹恒·饮月', '爻光']
    return dict(
        bench=[BenchChar(slot=1, char_id='姬子·启行', faction=_fac('姬子·启行'))],
        deployed_cids=set(deployed),
        deployed_fac=_fac_counts(deployed),
        board=dict(_fac_counts(deployed)),
        cap=4,
    )


def test_r288_recipe_floor_hold_makes_plan_empty() -> None:
    """局11 签名重放锁:配方底线命中 → kernel 单一源判「无部署可做」。

    列车 2 档已达 ∧ 仙舟 2 < 基础线 3 → bench 列车件留 bench,
    select_deployments 上场集为空(has_deployable False)——
    发射门与执行方共用此判据,本形态在发射前即被抑制。
    """
    kw = _stall_replay_kwargs()
    up, held = select_deployments(kw['bench'], **{k: v for k, v in kw.items()
                                                  if k != 'bench'})
    assert up == [], '配方底线:列车件(列车2档∧仙舟<3)必须留 bench'
    assert held == [0], '唯一 bench 件被底线门留置'
    assert has_deployable(**kw) is False, (
        '发射门与执行方同源:该帧「无部署可做」,发射方不得发 RunDeploy(dd-037)')


def test_has_deployable_positive_control() -> None:
    """对照:无底线冲突(板空)时同一 bench 列车件可上 → 谓词 True
    (防发射门退化成恒 False 的假修)。"""
    kw = _stall_replay_kwargs()
    kw2 = dict(kw, deployed_cids=set(), deployed_fac={}, board={})
    assert has_deployable(**kw2) is True


class _Cfg:
    """_main_flow_step 只消费 character_priority(本链路)。"""
    character_priority: list[str] = []


def _stall_obs() -> PrepObservation:
    kw = _stall_replay_kwargs()
    st = GameState()
    st.board = dict(kw['board'])
    st.level = 4
    return PrepObservation(
        state=st,
        bench_chars=list(kw['bench']),
        deployed_chars=[BenchChar(slot=i + 1, char_id=c, faction=_fac(c))
                        for i, c in enumerate(sorted(kw['deployed_cids']))],
        free_bench_slots=8,
        deploy_vacancy=1,
    )


def test_emitter_suppresses_rundeploy_when_plan_empty() -> None:
    """发射门锁:部署段计划空(候选全被配方底线留 bench)→ 不发射
    RunDeploy,直入装备段(RunEquip),bench=1 作为合法稳态交外环。"""
    strat = MandateV1Strategy()
    session = StrategySession()
    session.prep_phase = 1
    step = strat._main_flow_step(_stall_obs(), session, _Cfg())
    assert not isinstance(step, RunDeploy), (
        '计划空的帧不得发射 RunDeploy(局11 三环同签名零推进的形态,'
        'dd-037 发射门在第一步即抑制)')
    assert isinstance(step, RunEquip), '跳过部署后应直入装备段'
    assert session.prep_phase == 3, '阶段位应越过部署段(1)与装备段(2)直达出战前(3)'


def test_emitter_emits_rundeploy_when_plan_nonempty() -> None:
    """对照锁:计划非空(板空、bench 有货)→ 照常发射 RunDeploy
    (发射门只收口空计划,不改变正常部署行为)。"""
    strat = MandateV1Strategy()
    session = StrategySession()
    session.prep_phase = 1
    st = GameState()
    st.board = {}
    st.level = 4
    obs = PrepObservation(
        state=st,
        bench_chars=[BenchChar(slot=1, char_id='姬子·启行',
                               faction=_fac('姬子·启行'))],
        deployed_chars=[],
        free_bench_slots=8,
        deploy_vacancy=4,
    )
    step = strat._main_flow_step(obs, session, _Cfg())
    assert isinstance(step, RunDeploy), '有部署可做时发射行为不变'
    assert session.prep_phase == 2


def test_executor_noop_contract_source_lock() -> None:
    """契约硬化锁(dd-037):执行器 placed=0 时 no-op 与真实部署可区分——
    ① `_deploy_deterministic` 返回 (placed, plan_empty);
    ② plan_empty → STATUS_NOOP(不再是 ✓「已部署角色」);
    ③ 计划非空但 placed=0 → round_fail(交失败链,不蒙混成功);
    ④ P24 补部署不绕过配方底线(fill 段 r288 守卫在位)。"""
    src_det = inspect.getsource(CwOpDeploy._deploy_deterministic)
    assert 'return 0, True' in src_det and 'return placed, not order' in src_det, (
        '_deploy_deterministic 必须返回 (placed, plan_empty)')
    assert '_fill_plan = [' in src_det and '列车同行' in src_det, (
        '补部署段必须有 r288 底线守卫(kernel 留 bench 的列车件不得绕回上板)')
    src_deploy = inspect.getsource(CwOpDeploy.deploy)
    assert 'STATUS_NOOP' in src_deploy, 'no-op 必须用可区分状态'
    assert 'round_fail' in src_deploy, '计划非空 placed=0 必须走失败态'
    assert CwOpDeploy.STATUS_NOOP != CwOpDeploy.STATUS_DEPLOYED
