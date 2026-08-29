# -*- coding: utf-8 -*-
"""⓪ Δ池快照化契约锁(sim 判读同构基建第一块)。

对抗审查一轮#1(blocker)+二轮#1/#5 定谳后的不变量:
- 主仓提交快照可加载且指纹自洽(池内容+桶宽+采样器版本);
- 三态解析语义:snapshot 命中提交快照 / fallback 显式退旧模型
  并打标 / auto 缺源 raise(禁止隐式静默回退——实测同 seed
  有池/无池可翻转 hp_ge_60 判定);
- SimResult 带池指纹(裸 seed 不构成重放承诺)。
锁的是**链路与语义**,不锁分布数值(change-detector 陷阱)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.data import cw_delta_pool_data
from sr_od.application.currency_war.sim import engine_p1 as _sim
from sr_od.application.currency_war.sim import pool
from sr_od.application.currency_war.sim import runner
def test_snapshot_module_loads_and_fingerprint_selfconsistent() -> None:
    """提交快照可加载;META 指纹与重算一致(手改会被发现)。"""
    fp = pool.pool_fingerprint(cw_delta_pool_data.SNAPSHOT)
    assert fp == cw_delta_pool_data.META['fingerprint']
    # 可信标签口径:丢弃计数已披露(2026-08-22 retrofix 后死链
    # 历史标签置 None,不入池)
    assert 'unlabeled_dropped' in cw_delta_pool_data.META


def test_resolve_pool_snapshot_and_fallback() -> None:
    """snapshot 命中提交快照(归一 int 桶键);fallback 显式空池+打标。"""
    m, fp, src = pool.resolve_pool('snapshot')
    assert src == 'snapshot'
    assert fp == cw_delta_pool_data.META['fingerprint']
    # 归一化后语义等价(int 桶键;json round-trip 的 str 键会让
    # live_delta_for 的 int 查询全 miss = 快照静默失效)
    # ADR-0362:位面层同样归一 int 键
    assert m == pool._normalize_pool(cw_delta_pool_data.SNAPSHOT)
    assert all(isinstance(b, int)
               for planes in m.values() for b in planes)
    assert all(isinstance(b, int)
               for planes in m.values()
               for buckets in planes.values() for b in buckets)
    assert m.get('battle')

    m2, fp2, src2 = pool.resolve_pool('fallback')
    assert src2 == 'fallback'
    assert m2 == {}
    assert fp2 == pool.pool_fingerprint({})


def test_resolve_pool_auto_missing_raises_loudly(tmp_path: None | Path) -> None:
    """auto 缺源 raise(不静默回退空池)——blocker 修复的核心语义。"""
    with pytest.raises(pool.DeltaPoolUnavailable):
        pool.resolve_pool('auto', auto_dir=tmp_path / 'nonexistent')


def test_resolve_pool_path_json_snapshot(tmp_path: Path) -> None:
    """Path 模式:JSON 快照文件(生成器 --export-json 产物;
    ADR-0362 起形状 {节点:{位面:{桶:[Δ]}}})。"""
    p = tmp_path / 'snap.json'
    p.write_text(json.dumps(
        {'meta': {}, 'snapshot': {'battle': {1: {6: [-4]}}}},
        ensure_ascii=False), encoding='utf-8')
    m, fp, src = pool.resolve_pool(p)
    assert src == f'path:{p.name}'
    assert m == {'battle': {1: {6: [-4]}}}
    assert fp == pool.pool_fingerprint({'battle': {1: {6: [-4]}}})


def test_simulate_p1_records_pool_identity() -> None:
    """SimResult 带池指纹+来源(跨日基线对照须核指纹一致)。

    供给重校准起指纹含装备发放结构版本位(``+eqgN``)——发放结构是
    行为语义的一部分,新旧结构不可比,跨版本对照必须显式失败。
    """
    r = _sim.simulate_p1(42, pool='fallback')
    assert r.pool_source == 'fallback'
    assert r.pool_fingerprint == (
        pool.pool_fingerprint({})
        + f'+eqg{_sim.EQUIP_GRANT_CALIB_VERSION}')
    r2 = _sim.simulate_p1(42, pool='snapshot')
    assert r2.pool_source == 'snapshot'
    assert r2.pool_fingerprint == (
        cw_delta_pool_data.META['fingerprint']
        + f'+eqg{_sim.EQUIP_GRANT_CALIB_VERSION}')


def test_batch_report_carries_pool_fingerprint() -> None:
    """批量结果携带池指纹(基线数字可追溯其校准地基)。"""
    s = runner.simulate_p1_batch(10, pool='fallback')
    assert s['pool_source'] == 'fallback'
    assert s['pool_fingerprint'] == (
        pool.pool_fingerprint({})
        + f'+eqg{_sim.EQUIP_GRANT_CALIB_VERSION}')


def test_snapshot_pool_is_live_in_sim() -> None:
    """金丝雀:快照池采样真实命中(防 str 桶键/归一化缺失类静默失效)。

    曾发:json round-trip 把桶键变 '9'(str),live_delta_for 用
    int 查询全 miss → snapshot 模式静默退旧模型而所有结构测试
    仍绿。本锁遍历快照桶,断言至少一次真实采样命中。
    """
    import random

    m, _, _ = pool.resolve_pool('snapshot')
    hit = False
    # ADR-0362:桶在 plane=1 层下
    for node in ('battle', 'boss', 'encounter'):
        for bucket in (m.get(node, {}).get(1) or {}):
            v = pool.live_delta_for(node, bucket, random.Random(1),
                                    pool_map=m)
            if v is not None:
                hit = True
                break
        if hit:
            break
    assert hit, '快照全桶采样 miss = 池静默失效(查 _normalize_pool)'


def test_generator_data_file_discipline() -> None:
    """生成器纪律:数据文件头部带勿手编标记 + 重生成命令。"""
    head = Path(cw_delta_pool_data.__file__).read_text(
        encoding='utf-8')[:600]
    assert '勿手编' in head
    assert 'gen_delta_pool_snapshot.py' in head

