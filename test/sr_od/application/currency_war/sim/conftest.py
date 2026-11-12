"""sim 包级共享夹具:整局批跑只算一次(冒烟批与预注册判据批共用产物)。

背景:冒烟批(test_sim_smoke_batch)与预注册五判据批(test_sim_levelup_
cycle)此前各自独立跑同一批整局(同种子同装配同运行原语),40 局里一半
是重复计算。本夹具把批跑收敛为会话级一次,两批测试按 seed 取各自的运行
记录(sr-od-test README 纪律 2「慢计算只算一次」;2026-10-24 用户裁定:
全量测试压到 ~3 分钟,种子集 20 连号 → 8 个代表号)。

全量普查:修复批后的 20 连号普查(依据 = 带病树同 20 seed 普查 13 崩 3 挂
的修复复扫)不进常跑——临时把 :data:`BATCH_SEEDS` 的内容换成
:data:`FULL_SWEEP_SEEDS` 跑一轮,改完还原,不进提交。
"""
from __future__ import annotations

import time
from typing import Any, NamedTuple

import pytest
from test.harness.sim_backend_runner import SimFullRun, run_sim_full_match

#: 批跑默认种子集 = 2026-10-12 起 20 连号的 8 个代表号(均匀取样,跨
#: 全程覆盖;完成判据 = 全部跑通),与首局验收已登记固定 seed〔20260923/7/61〕
#: 零重叠。选号依据 = 修复后 20 连号全扫实测(2026-10-24,20/20 跑通):
#: 转场形态唯一实例 = 20261015 必须在集(预注册判据批的批级前提
#: 「转场在批内有实例」),其余跨全程均匀取样。
BATCH_SEEDS: tuple[int, ...] = (
    20261012, 20261014, 20261015, 20261018,
    20261021, 20261024, 20261027, 20261031,
)

#: 全量普查种子集(2026-10-12 起 20 连号;仅修复批后专项普查时临时替换
#: BATCH_SEEDS 用,平时不跑)。
FULL_SWEEP_SEEDS: tuple[int, ...] = tuple(range(20261012, 20261032))


class SimBatchEntry(NamedTuple):
    """单 seed 批跑记录。

    ``run``:整局产物(SimFullRun);崩溃局为 None。
    ``error``:该 seed 崩溃时存的异常,消费侧 re-raise —— 保留逐 seed
    失败隔离(批跑在夹具里只跑一次,不隔离会把一个崩局放大成全部
    参数化用例集体红)。 ``duration_s``:整局耗时(统计行产出面)。
    """
    seed: int
    run: SimFullRun | None
    duration_s: float
    error: Exception | None


@pytest.fixture(scope='session')
def sim_batch_runs(test_context: Any, tmp_path_factory: Any) -> dict[int, SimBatchEntry]:
    """逐 seed 一整局(会话级一次;冒烟批与预注册批共享,贵计算只算一次)。

    逐局独立 MonkeyPatch:实机采集停机钩子桩掉(sim 局无实机画面可采,
    语义澄清非绕过验证面)+ 局终 3c 收尾会直置 ctx.cw_match=None,逐局
    undo 保证下一局从干净 ctx 起跑(与首局验收 ``_one_run`` 同款)。
    """
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        CwScreenPrep,
    )

    entries: dict[int, SimBatchEntry] = {}
    for seed in BATCH_SEEDS:
        mp = pytest.MonkeyPatch()
        started = time.perf_counter()
        try:
            mp.setattr(CwScreenPrep, '_spec_invest_shop_stop_hook',
                       lambda self: None)
            run = run_sim_full_match(
                test_context, mp, tmp_path_factory.mktemp(f'sim_batch_{seed}'),
                seed=seed, strategy_seed=seed)
            entries[seed] = SimBatchEntry(seed, run,
                                          time.perf_counter() - started, None)
        except Exception as exc:  # 崩溃局留档,消费侧 re-raise(失败隔离)
            entries[seed] = SimBatchEntry(seed, None,
                                          time.perf_counter() - started, exc)
        finally:
            mp.undo()
    return entries
