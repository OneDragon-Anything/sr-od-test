"""sim 冒烟批(全流程逐 seed 跑通判据;用户裁定 2026-10-13:冒烟只验
「能跑完不崩」,不设基线与 A/B 对照)。

锁面 = 「改后策略能跑完不崩」的批次级判据,**非行为正确性**(行为面由
各批单帧锁承载;用户裁定 2026-10-13 本迭代冒烟不设基线与 A/B 对照):

- 逐 seed 一整局:真 mandate_v1 策略 + 真 CwLoop 驱动 SimBackend,从
  reset 经 P1 → P2 到局终,op 执行零失败收口(死循环由看门狗轮限转
  execute 失败承载,崩溃由异常传播承载——两者都让本测试红);
- 终局合法形态 = 死亡(hp 归零且保底已用)/ P2 末完成进 P3(sim 建模
  域 = P1+P2,P3 未观测进场即局终),两源都算「跑完」;
- 逐局统计行(复跑加 ``-s`` 可收):seed/终局源/终点/结算轮/驱动步/
  节点写数/末金/末级/hp 低点/耗时——冒烟报告的产出面,不作断言
  (统计数值随策略正常调整变动,断言即过时)。

运行原语 = ``test/harness/sim_backend_runner.py::run_sim_full_match``
(装配缝单一源:端口槽/容器绑定/时间冻结/journal 内存捕获/留证重定向);
崩点上下文(node/画面/步数)由运行原语以异常 note 注入。

种子集 = :data:`SMOKE_SEEDS`(代表性子集 2 连号;含慢桶全量 ≤180s 裁决
2026-10-14,smoke 预算 ≤70s)。原注册批 = 2026-10-12 起 20 连号,极致
压缩轮逐 seed 实测普查(2026-10-14,在飞 strategies/operations 改动
工作树):曾跑通 4 seed = 20261016/20261023/20261024/20261025(逐进程
计时 10.2/12.1/13.0/12.3s),保留最快两个;其余 16 seed 该树状态下
13 崩(补给/备战节点 op 异常或 fail 重派触限)3 挂(备战动作日志
flush 阻死,pytest-timeout 不可杀)——非测试面问题,修复责任在被测
侧,修后可按本判据扩回样本。**失败重派环分支放弃整局覆盖**(普查中
带重派环的局全部触限失败,无一整局跑通),该分支由 test_cw_loop.py
「op-fail 重派防线上限」锁单独承压。

运行成本:单局实测 ~8-13s(含进程启动;健康树注册时 ~21-45s)× 2 →
慢桶登记(slow_marks.txt 逐 seed 条目);复跑带 ``-s`` 可收逐局统计行;
单条 timeout 放宽 300s(看门狗 1200 轮触顶局需要余量,真挂死仍被兜住)。
"""
from __future__ import annotations

import time
from typing import Any

import pytest
from test.harness.sim_backend_runner import run_sim_full_match

#: 冒烟批种子集(代表性子集 2 个,内置常量;完成判据 = 全部跑通)。
#: 取值 = 曾跑通 4 seed 中逐进程实测最快两个(计时见模块 docstring 探针
#: 记录),与首局验收在册固定 seed〔20260923/7/61〕零重叠。
SMOKE_SEEDS: tuple[int, ...] = (20261016, 20261023)


def _stats_line(seed: int, run: Any, duration_s: float) -> str:
    """逐局统计行(冒烟报告产出面;字段取现值快照,不做断言)。

    字段口径:终局源 = 死亡(``final_hp == 0``,保底已用归零)/ 存活进
    P3(建模域尽头)/ abandoned(局未收口即停——execute 失败/崩溃局,
    终点字段仅记录崩点位置);节点写数 = 状态 journal ``node`` 域写行数
    (每进一节点恰一写);驱动步 = 后端端口驱动计数(advance + click
    合计)。
    """
    node = run.gs.node.value
    if not run.backend.done:
        terminal = 'abandoned'
    elif int(run.gs.hp.value or -1) == 0:
        terminal = 'death'
    else:
        terminal = 'p3_enter'
    node_writes = sum(1 for r in run.journal_rows
                      if r.get('row') == 'write' and r.get('field') == 'node')
    hp_trail = run.hp_trail or (0,)
    return (
        f'[smoke] seed={seed} terminal={terminal} '
        f'end=P{node.plane}r{node.round_num}({node.kind}) '
        f'settled={run.loop._settle.rounds_done} steps={run.backend._steps} '
        f'nodes={node_writes} gold={int(run.gs.gold.value or 0)} '
        f'level={int(run.gs.level.value or 0)} hp_min={min(hp_trail)} '
        f'fail_streak={run.loop._op_fail_streak_n} dur={duration_s:.1f}s')


@pytest.mark.timeout(300)
@pytest.mark.parametrize('seed', SMOKE_SEEDS)
def test_smoke_match_completes(seed: int, test_context: Any,
                               monkeypatch: pytest.MonkeyPatch,
                               tmp_path: Any) -> None:
    """冒烟判据:该 seed 一整局跑完——收口成功 ∧ 局终位 ∧ 无 op fail
    连发 ∧ 真打过仗(结算轮 ≥ 1)。

    失败形态三源各自可见:崩溃 = 异常传播(traceback + 运行原语注入的
    崩点 note〔node/画面/步数〕);死循环 = 看门狗轮限使 execute 收口
    失败;未到局终 = done 假。op fail streak 触限虽被框架重派掩盖,也
    以计数暴露(连续 fail 达限即软死循环)。
    """
    started = time.perf_counter()
    try:
        run = run_sim_full_match(test_context, monkeypatch, tmp_path,
                                 seed=seed, strategy_seed=seed)
    except Exception:
        # 崩溃局统计行(异常传播前留批档证据;崩点上下文由运行原语注入
        # 异常 note,原 traceback 承载「哪动作」)。
        print(f'[smoke] seed={seed} terminal=CRASH-exc '
              f'dur={time.perf_counter() - started:.1f}s')
        raise
    duration_s = time.perf_counter() - started
    print(_stats_line(seed, run, duration_s))
    assert run.result is not None and run.result.success, \
        f'execute 未成功收口: {getattr(run.result, "status", "")!r}'
    assert run.backend.done, '后端局终位未置(done)'
    assert run.loop._op_fail_streak_n < 5, '外环 op 连续 fail 计数触限'
    assert run.loop._settle.rounds_done >= 1, '零结算轮(未打任何一场战斗)'
