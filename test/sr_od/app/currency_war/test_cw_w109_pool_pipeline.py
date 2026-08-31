# -*- coding: utf-8 -*-
"""W109(ADR-0344)Δ池语料管线锁——退役收编后仅存两条守卫。

管线已冻结停更(ADR-0424 Δ池退役,生成机制本体随清理批删除),本文件只保:
- 冻结守卫:regenerate_snapshot 缺省一律 raise(防误解冻停更管线);
- 局终钩子安全:再生失败不外传(每局收尾不被遥测基建故障打断)。
管线本体的行为锁(产物写入/新鲜度三态/收尾接线)随退役清理批一并移除
(2026-08-31 测试瘦身批裁决,详见 .debug/temp/test_audit/batch3_verdicts.md)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.sim import cw_delta_pool_gen
from sr_od.application.currency_war.sim import ledger_hooks


def test_regenerate_frozen_by_default() -> None:
    """退役第一步:池冻结——regenerate_snapshot 一律 raise(管线停跑)。"""
    with pytest.raises(cw_delta_pool_gen.DeltaPoolFrozen):
        cw_delta_pool_gen.regenerate_snapshot(quiet=True)


def test_hook_swallows_regeneration_failure(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """局终钩子 best-effort:再生抛异常不外传(局终收尾不被打断)。"""
    def _boom(**kwargs):
        raise RuntimeError('sim_runs 回灌守卫误触发(构造)')

    monkeypatch.setattr(cw_delta_pool_gen, 'regenerate_snapshot', _boom)
    # 不抛即过(返回 None;warning 已由 log 记)
    assert ledger_hooks._regenerate_delta_pool_after_run() is None
