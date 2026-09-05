"""sim_runs 滚动清理·锚定保留锁。

锚定批(A/B 对照批/测量基线批等复现链锚点,带 anchored.json 标记)
免滚动清理;非锚定批照常滚动删除。背景:keep=20 滚动清理曾把冻结池
与 A/B 对照批一起删掉,A/B 复现链断裂(评估表相位 2a 报告 §6)。
"""

from pathlib import Path

import pytest

from sr_od.application.currency_war.sim import runner as sim_runner


@pytest.fixture()
def sim_runs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """SIM_RUNS_DIR 重定向到 tmp_path(测试零真实副作用)。"""
    root = tmp_path / 'sim_runs'
    root.mkdir()
    monkeypatch.setattr(sim_runner, 'SIM_RUNS_DIR', root)
    monkeypatch.setattr(sim_runner, '_SIM_RUNS_KEEP', 2)
    return root


def _mk_batch(root: Path, name: str, *, anchored: bool = False) -> Path:
    d = root / name
    d.mkdir()
    (d / 'decisions.jsonl').write_text('', encoding='utf-8')
    if anchored:
        sim_runner.anchor_batch(d, f'锁测试:{name}')
    return d


def test_prune_deletes_non_anchored_out_of_window(sim_runs_root: Path) -> None:
    """窗口外的非锚定批照常滚动删除。"""
    root = sim_runs_root
    _mk_batch(root, 'sim_001_aaaa')
    _mk_batch(root, 'sim_002_aaaa')
    _mk_batch(root, 'sim_003_aaaa')
    sim_runner._prune_sim_runs()
    assert (root / 'sim_001_aaaa').exists() is False
    assert (root / 'sim_002_aaaa').exists()
    assert (root / 'sim_003_aaaa').exists()


def test_prune_skips_anchored_batch_out_of_window(sim_runs_root: Path) -> None:
    """窗口外的锚定批免清理(锚定保留核心语义)。"""
    root = sim_runs_root
    _mk_batch(root, 'sim_001_aaaa', anchored=True)
    _mk_batch(root, 'sim_002_aaaa')
    _mk_batch(root, 'sim_003_aaaa')
    sim_runner._prune_sim_runs()
    assert (root / 'sim_001_aaaa').exists(), \
        '锚定批即使滑出窗口也必须保留'


def test_prune_anchor_survives_when_all_anchored(sim_runs_root: Path) -> None:
    """全部锚定时一个都不删(锚定优先于 keep 窗口)。"""
    root = sim_runs_root
    for i in range(4):
        _mk_batch(root, f'sim_{i:03d}_aaaa', anchored=True)
    sim_runner._prune_sim_runs()
    assert len(list(root.iterdir())) == 4


def test_prune_only_touches_sim_prefixed_dirs(sim_runs_root: Path) -> None:
    """非 sim_ 前缀目录(用户显式目录/冻结池)不清理。"""
    root = sim_runs_root
    frozen = root / 'freeze_before'
    frozen.mkdir()
    _mk_batch(root, 'sim_001_aaaa')
    _mk_batch(root, 'sim_002_aaaa')
    _mk_batch(root, 'sim_003_aaaa')
    sim_runner._prune_sim_runs()
    assert frozen.exists()


def test_anchor_batch_marker_roundtrip(sim_runs_root: Path) -> None:
    """anchor_batch 写标记 → is_anchored 命中;标记含 reason 可审计。"""
    import json

    d = _mk_batch(sim_runs_root, 'sim_001_aaaa')
    assert sim_runner.is_anchored(d) is False
    sim_runner.anchor_batch(d, 'A/B 对照批')
    assert sim_runner.is_anchored(d) is True
    payload = json.loads((d / 'anchored.json').read_text(encoding='utf-8'))
    assert payload['reason'] == 'A/B 对照批'
