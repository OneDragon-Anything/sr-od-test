"""策略失活探针判据锁 —— 整文件退役(W3,2026-09-11)。

[退役墓碑,W3]本文件全部测试随策略失活判据链退役拆除:r5-migration-plan.md
§2 W3 删旧读面(checks 子命令 + ledger_hooks 读侧检查族)+ 删除波 1 已删
cw_loop 运行探针消费面与 decisions 流写端——被测生产面(telemetry/query 的
_row_heartbeat / strategy_round_live / check_strategy_live_streak、
sim/ledger_hooks.run_checks_on_replay、cw_loop 失活检查接线)已全部消亡。
现役失活防线 = 哨兵脚本组 journal 面(T-257 切换,cw_early_stop)与策略侧
决策行(两文件之二,落地时重立锁面)。git 历史可复活本文件(dd-031 判据
正文与误杀局实证记录保留于 ADR-0342/ADR-0630 引用链)。
"""
from __future__ import annotations