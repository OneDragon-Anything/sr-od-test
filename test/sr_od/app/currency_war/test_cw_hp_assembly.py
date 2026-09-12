"""test_cw_hp_assembly.py —— 整文件退役(W3,2026-09-11)。

[退役墓碑,W3]本文件全部测试随档案装配派生面的旧流切片拆除退役
(r5-migration-plan.md §2 W3:_SLICE_FILES 旧流键删除;派生列的旧流帧源
= decisions/exogenous 切片,已停写+已拆)。装配器对缺流键宽容退化(空
派生列),读侧宽容契约由 test_cw_w3_journal_only_reads 承锁;派生列的
journal 侧等价重建候后续批(journal 行间差分可重建同一语义)。
git 历史可复活本文件。
"""
from __future__ import annotations
