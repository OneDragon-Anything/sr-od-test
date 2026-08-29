# -*- coding: utf-8 -*-
"""W109(ADR-0344)锁:Δ池语料管线治本三件。

件1:regenerate_snapshot 可调用入口(守卫头注/META runs 覆盖/空池 raise);
件2:check_pool_freshness 三态(新鲜 lag≤1 过 / 滞后 ≥2 违规 / 无本机
    replay 跳过;META.runs 空违规);
件3:局终钩子 best-effort(再生失败不传播异常)+ record_run_summary 接线。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.sim import cw_delta_pool_gen
from sr_od.application.currency_war.sim import cw_sim_checks

from sr_od.application.currency_war.sim.pool import pool_fingerprint
from sr_od.application.currency_war.telemetry import ledger_hooks, state


def _fixture_replay(root: Path, run_id: str, *, r2_node: str = '普通战斗') -> None:
    """最小可配对语料:2 轮 outcomes(相邻差分)+ 2 轮 decisions 板深。"""
    d = root / 'replay'
    d.mkdir(parents=True, exist_ok=True)
    with (d / 'outcomes.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps({'run_id': run_id, 'plane': 1, 'round_num': 1,
                            'node_type': '', 'hp_after': 80}) + '\n')
        f.write(json.dumps({'run_id': run_id, 'plane': 1, 'round_num': 2,
                            'node_type': r2_node, 'hp_after': 74,
                            'board_before': {'仙舟': 2}}) + '\n')
    with (d / 'decisions.jsonl').open('a', encoding='utf-8') as f:
        for rn in (1, 2):
            f.write(json.dumps({'run_id': run_id, 'plane': 1,
                                'round_num': rn,
                                'state': {'board': {'仙舟': 2},
                                          'deployed': []}}) + '\n')


@pytest.fixture()
def guarded_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把生成器写目标指到 tmp(白名单同步——生产签名零测试参数)。

    同步撤销池冻结标志:池已退役停更(退役第一步),但生成机制
    本体的回归覆盖仍要能单测——测试内解冻,不改生产默认。
    """
    target = tmp_path / 'cw_delta_pool_data.py'
    monkeypatch.setattr(cw_delta_pool_gen, 'DATA_PY', target)
    monkeypatch.setattr(cw_delta_pool_gen, 'WRITABLE_TARGETS', (target,))
    monkeypatch.setattr(cw_delta_pool_gen, '_DELTA_POOL_FROZEN', False)
    return target


def test_regenerate_frozen_by_default() -> None:
    """退役第一步:池冻结——regenerate_snapshot 一律 raise(管线停跑)。"""
    with pytest.raises(cw_delta_pool_gen.DeltaPoolFrozen):
        cw_delta_pool_gen.regenerate_snapshot(quiet=True)


def test_regenerate_writes_guarded_artifact(
        tmp_path: Path, guarded_target: Path) -> None:
    """件1:产物头注带勿手编警告+指纹与池内容一致+META runs 覆盖。"""
    _fixture_replay(tmp_path, 'run_20990101_000001')
    _fixture_replay(tmp_path, 'run_20990101_000002', r2_node='遭遇')
    fp = cw_delta_pool_gen.regenerate_snapshot(
        src_dir=tmp_path / 'replay', quiet=True)
    text = guarded_target.read_text(encoding='utf-8')
    assert '勿手编' in text and 'cw_delta_pool_gen' in text
    # 动态加载产物:META/快照可解析,指纹=池内容指纹(与 resolve_pool
    # 校验同一不变量)。
    spec = importlib.util.spec_from_file_location('w109_snap', guarded_target)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    assert set(mod.META['runs']) == {'run_20990101_000001',
                                     'run_20990101_000002'}
    assert mod.META['fingerprint'] == fp
    assert fp == pool_fingerprint(mod.SNAPSHOT)
    assert 'battle' in mod.SNAPSHOT and 'encounter' in mod.SNAPSHOT


def test_regenerate_empty_pool_raises(tmp_path: Path,
                                      guarded_target: Path) -> None:
    """件1:无可配对样本 raise(局终钩子捕获记账,不静默写空池)。"""
    (tmp_path / 'replay').mkdir()
    with pytest.raises(RuntimeError, match='池为空'):
        cw_delta_pool_gen.regenerate_snapshot(
            src_dir=tmp_path / 'replay', quiet=True)


def _patch_pool_meta(monkeypatch: pytest.MonkeyPatch, runs: dict) -> None:
    from sr_od.application.currency_war.data import cw_delta_pool_data as dpd
    monkeypatch.setattr(dpd, 'META', {'runs': runs})


def _unfreeze_freshness(monkeypatch: pytest.MonkeyPatch) -> None:
    """池冻结态下新鲜度检查整体跳过(停更=预期);测三态逻辑先解冻。"""
    from sr_od.application.currency_war.kernel import cw_coarse_battle
    monkeypatch.setattr(cw_coarse_battle, 'BATTLE_ENGINE_MODE', 'delta')


def test_freshness_frozen_skips(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """退役第一步:coarse 引擎默认下新鲜度检查跳过(停更非断裂)。"""
    replay = tmp_path / 'replay'
    replay.mkdir()
    (replay / 'runs.jsonl').write_text(
        json.dumps({'run_id': 'run_20990101_000009'}) + '\n',
        encoding='utf-8')
    _patch_pool_meta(monkeypatch, {'run_20990101_000001': 9})
    res = cw_sim_checks.check_pool_freshness(replay)
    assert res['violations'] == 0 and res.get('skipped')


def test_freshness_fresh_and_stale(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """件2:lag=1 瞬态过;lag≥2 违规(管线断);detail 带重跑指引。"""
    _unfreeze_freshness(monkeypatch)
    replay = tmp_path / 'replay'
    replay.mkdir()
    with (replay / 'runs.jsonl').open('w', encoding='utf-8') as f:
        for rid in ('run_20990101_000001', 'run_20990101_000002',
                    'run_20990101_000003'):
            f.write(json.dumps({'run_id': rid}) + '\n')
    _patch_pool_meta(monkeypatch, {'run_20990101_000002': 9})
    ok = cw_sim_checks.check_pool_freshness(replay)
    assert ok['violations'] == 0 and ok['lag'] == 1
    _patch_pool_meta(monkeypatch, {'run_20990101_000001': 9})
    bad = cw_sim_checks.check_pool_freshness(replay)
    assert bad['violations'] == 1 and bad['lag'] == 2
    assert 'gen_delta_pool_snapshot' in bad['detail'][0]


def test_freshness_skip_and_empty_pool(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """件2:无本机 replay 跳过不辖;META.runs 空=违规。"""
    _unfreeze_freshness(monkeypatch)
    empty_dir = tmp_path / 'nowhere'
    res = cw_sim_checks.check_pool_freshness(empty_dir)
    assert res['violations'] == 0 and res.get('skipped')
    replay = tmp_path / 'replay2'
    replay.mkdir()
    (replay / 'runs.jsonl').write_text(
        json.dumps({'run_id': 'run_20990101_000001'}) + '\n',
        encoding='utf-8')
    _patch_pool_meta(monkeypatch, {})
    res2 = cw_sim_checks.check_pool_freshness(replay)
    assert res2['violations'] == 1


def test_hook_swallows_regeneration_failure(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """件3:再生抛异常不外传(局终收尾不被遥测基建故障打断)。"""
    def _boom(**kwargs):
        raise RuntimeError('sim_runs 回灌守卫误触发(构造)')
    monkeypatch.setattr(cw_delta_pool_gen, 'regenerate_snapshot', _boom)
    # 不抛即过(返回 None;warning 已由 log 记)
    assert ledger_hooks._regenerate_delta_pool_after_run() is None


def test_record_run_summary_wires_hook(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """件3:record_run_summary 尾部接线(正常局终→再生触发一次)。"""
    calls: list[str] = []

    def _fake_regenerate(**kwargs):
        calls.append('regen')
        return 'fp0000'

    monkeypatch.setattr(cw_delta_pool_gen, 'regenerate_snapshot',
                        _fake_regenerate)
    cls = type(state.get_recorder())
    rec = object.__new__(cls)
    rec._comms = {}
    rec._gold_trajectory = {}
    rec._difficulty = {}
    appended: list[tuple] = []

    def _fake_append(name, row):
        appended.append((name, row))

    rec._append = _fake_append  # type: ignore[attr-defined]
    rec.record_run_summary('run_20990101_000009', 'loss', 2, 2, 0)
    assert appended and appended[0][0] == 'runs.jsonl'
    assert appended[0][1]['run_id'] == 'run_20990101_000009'
    assert calls == ['regen']
    # 内存累积已清(防跨 run 泄漏语义保持)
    assert 'run_20990101_000009' not in rec._comms
