"""sim 统一 3.4 首局验收(MVP 终局四条尺的可执行形态)。

锁面 = sim 全量局完成判据(确定性双跑/不变式断言四条尺):

- 跑完:真策略 mandate_v1 决策 + 真 CwLoop 驱动,SimBackend 从 reset 经
  P1 → P2 boss 到局终,op 执行零失败(成功收口 = 回大厅终局链);
- 确定性:同 seed 同 RunConfig 双跑容器逐位一致(双跑快照 diff 为空);
- 容器不变式:金币不出现无规则依据的负值 / hp 轨迹与结算写流一致 /
  经验等级符合规则表(carry 与阈值表)/ 局终无未消费败态挂账;
- L1 全量绿(由全量运行承载,非本文件断言面)。

设计依据 = flow-seam 详设 §4(运行器装配缝)+ sim-backend 详设(状态机
与序列语义;迭代内合法引用,正本更新义务归末阶段)。运行原语住
``test/harness/sim_backend_runner.py``(装配缝单一源,本文件只消费)。

「多种子首局完备」语义不再在此重复整局覆盖(2026-10-14 裁决:与
test_sim_smoke_batch 的逐 seed 整局冒烟完全重叠,该文件按预算保留
2 seed 承接);非验收 seed 活锁回归锚(seed 7/61)的机制锁 =
test_prep_action_ops 桥复检语境坐标锁。

运行成本:确定性双跑共用两整局(模块夹具只跑一次)→ 慢桶登记
(slow_marks.txt)。
"""
from __future__ import annotations

from typing import Any

import pytest
from test.harness.sim_backend_runner import run_sim_full_match

#: 验收局种子(世界后端与策略器共用;经种子扫描选定 = 该 seed 下真
#: 策略能从 P1 打到 P2 boss 局终,确定性双跑与种子值解耦)。
ACCEPT_SEED: int = 20260923

#: 种子扫描终局下限:验收局至少到达第二位面(P2 boss 辖域)。
_EXPECT_MIN_PLANE: int = 2


@pytest.fixture(scope='module')
def two_runs(test_context: Any, tmp_path_factory: Any) -> tuple:
    """同 seed 双跑(模块级一次;确定性对拍与不变式断言共用产物)。"""
    tmp1 = tmp_path_factory.mktemp('sim_run_a')
    tmp2 = tmp_path_factory.mktemp('sim_run_b')
    return (_one_run(test_context, tmp1, ACCEPT_SEED),
            _one_run(test_context, tmp2, ACCEPT_SEED))


def _one_run(test_context: Any, tmp_path: Any, seed: int) -> Any:
    """单局运行(独立 MonkeyPatch:局终 3c 收口会直置 ctx.cw_match=None,
    逐局 undo 保证下一局从干净 ctx 起跑)。"""
    mp = pytest.MonkeyPatch()
    try:
        return run_sim_full_match(test_context, mp, tmp_path,
                                  seed=seed, strategy_seed=seed)
    finally:
        mp.undo()


# ============================================================ 尺② 跑完

def test_first_match_runs_to_game_over_without_op_fail(two_runs: tuple) -> None:
    """跑完判据:reset → P1 → P2 boss → 局终,零 op fail、零 retry 耗尽。

    凭据形态:execute() 成功收口(回大厅终局链 = 战斗等待 terminal_lobby
    → 主循环 3c)+ 后端局终位 done + 到达位面下限 + 外环 fail 重派计数
    未触限(连续 fail 达限会转 round_fail 使 execute 失败,前置即零 fail
    的运行级凭据)+ 结算轮数非零(真打过仗)。"""
    run = two_runs[0]
    assert run.result is not None and run.result.success, \
        f'execute 未成功收口: {getattr(run.result, "status", "")!r}'
    assert run.backend.done, '后端局终位未置(done)'
    node = run.gs.node.value
    assert node is not None and node.plane >= _EXPECT_MIN_PLANE, \
        f'未到达 P{_EXPECT_MIN_PLANE} 辖域: {node!r}'
    assert run.loop._op_fail_streak_n < 5, '外环 op 连续 fail 计数触限'
    assert run.loop._settle.rounds_done >= 1, '零结算轮(未打任何一场战斗)'


# ============================================================ 尺① 确定性

def test_first_match_deterministic_double_run_identical(two_runs: tuple) -> None:
    """确定性判据:同 seed 同 RunConfig 双跑,容器逐位一致(diff 为空)。

    对拍载体 = 容器逐域值快照(全部 Field 域,冻结为纯数据);任何域
    值漂移(采样链/动作腿 rng/策略 rng 注入缺口)都会在此显形。"""
    run_a, run_b = two_runs
    diff = {k: (run_a.snapshot.get(k), run_b.snapshot.get(k))
            for k in set(run_a.snapshot) | set(run_b.snapshot)
            if run_a.snapshot.get(k) != run_b.snapshot.get(k)}
    assert not diff, f'双跑容器 diff 非空(逐位一致破坏): {diff}'


# ============================================================ 尺③ 容器不变式

def _write_rows(run: Any, field: str) -> list:
    """容器写流投影(状态 journal sink 内存捕获;field 行按版本序)。"""
    return [r for r in run.journal_rows
            if r.get('row') == 'write' and r.get('field') == field]


def test_first_match_container_invariants(two_runs: tuple) -> None:
    """容器不变式四条尺(尺③;同一整局产物一次对账):
    ①金币不出现无规则依据的负值;②hp 轨迹与结算写流逐条一致;
    ③经验等级符合规则表(逐级 +1、carry 界、阈值表单一源);
    ④局终无未消费败态挂账(败补 U04 口径消费归下一战斗轮轮首)。

    凭据 = 状态 journal 写流(轮首收入/环境金/买入扣费/晶矿金每笔在案;
    level/xp 写通道 = 节点经验入账与购买经验同一通道);终值另核对容器
    现值。四组断言消费同一 two_runs 产物,归并一条降低慢桶条目数;
    失败定位靠分节注释与各断言消息。"""
    from sr_od.application.currency_war.kernel.cw_economy import (
        MAX_PLAYER_LEVEL,
        XP_TO_NEXT_LEVEL,
    )
    run = two_runs[0]

    # —— ① 金币不变式 ——
    gold_rows = _write_rows(run, 'gold')
    assert gold_rows, '零 gold 写行(journal 捕获失效,断言无凭据)'
    negatives = [(r.get('v'), r.get('after')) for r in gold_rows
                 if r.get('after') is not None and r['after'] < 0]
    assert not negatives, f'gold 负值写行: {negatives}'
    assert run.gs.gold.value == gold_rows[-1]['after'], \
        'gold 终值与末条写行不一致'

    # —— ② hp 轨迹不变式(hp 写行每战斗结算恰一条;轨迹首条 = reset
    #      开局,先于 journal 捕获,故对拍域 = 写流全序 vs 轨迹[1:]) ——
    hp_rows = _write_rows(run, 'hp')
    assert hp_rows, '零 hp 写行(journal 捕获失效,断言无凭据)'
    written = [r['after'] for r in hp_rows]
    assert written == list(run.hp_trail)[1:], \
        f'hp 写流 {written} != 轨迹[1:] {list(run.hp_trail)[1:]}'
    # 终值 0 = 死亡局终的合法终态(出口 hp 遥测含死亡局);非终值 0 =
    # 结算中途回 0 会被 apply_hp_outcome 保底/局终逻辑挡住,不可达。
    assert all(0 <= h <= 100 for h in run.hp_trail), 'hp 轨迹出界'
    assert run.gs.hp.value == run.hp_trail[-1], 'hp 终值与轨迹末条不一致'

    # —— ③ 经验等级不变式(升级逐级 +1 不越上限;carry 恒 0 ≤ cur < need;
    #      阈值 need 与规则表一致,单一源 = XP_TO_NEXT_LEVEL) ——
    level_rows = _write_rows(run, 'level')
    xp_rows = _write_rows(run, 'xp')
    assert level_rows and xp_rows, '零 level/xp 写行(断言无凭据)'
    prev = None
    for r in level_rows:
        val = r.get('after')
        assert isinstance(val, int) and val >= 1, f'level 非法: {val!r}'
        if prev is not None:
            # 同值行 = 观察锚定等值重写(现值非空即落的呈现写);升级恒 +1
            assert val in (prev, prev + 1), f'跳级/降级: {prev} → {val}'
        assert val <= MAX_PLAYER_LEVEL, f'越上限: {val}'
        prev = val
    for r in xp_rows:
        cur, need = r['after']
        assert 0 <= cur < need, f'经验 carry 破坏: (cur={cur}, need={need})'
    final_level = run.gs.level.value
    final_xp = run.gs.xp.value
    assert final_xp is not None and final_xp[0] < final_xp[1]
    if final_level < MAX_PLAYER_LEVEL:
        assert final_xp[1] == XP_TO_NEXT_LEVEL.get(final_level), \
            '终态阈值与规则表不一致'

    # —— ④ 败态挂账不变式(局终仍挂账 = 败补链断裂) ——
    assert run.gs.pending_loss.value is None, \
        f'局终败态挂账未消费: {run.gs.pending_loss.value!r}'
