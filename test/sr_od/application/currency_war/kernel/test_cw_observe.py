"""货币战争可观测框架留证汇点(``cw_shot`` / ``cw_shot_unique`` / ``obs_conflict``)离线帧分支测试。

锁的设计约定(契约正文 = ``cw_observe`` 三个函数的 docstring):

- 离线帧(``frame_is_live()`` 为假,即 ``SrBackendContext.analyze`` 读图路径传进来的历史图):
  - ``cw_shot`` / ``cw_shot_unique`` 不建目录、不写文件,都返 None;
  - ``obs_conflict`` 传了帧也不调 ``cw_shot_unique``、不调账本 ``note_obs_event``,
    日志行照打但 ``attn=False`` 且带 ``offline=1``;
- 实时帧:三个汇点照常在留证目录落盘 / 入账。

零副作用约定:留证目录 ``_SHOT_DIR`` 指到 ``tmp_path``;账本板 ``obs_event_board()``
打桩记录调用;``cw_log`` 打桩记录调用(框架 logger propagate=False,caplog 收不到)。
"""
from __future__ import annotations

import types

import numpy as np
import pytest

import sr_od.application.currency_war.kernel.cw_observe as mod
from sr_od.context.frame_source import offline_frame

_FRAME: np.ndarray = np.zeros((8, 8, 3), dtype=np.uint8)


@pytest.fixture
def observe_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> tuple:
    """留证汇点夹具:目录指 tmp、账本板与 cw_log 记录调用。返回 (目录, 账本
    调用列表, cw_log 调用列表)。"""
    shot_dir = tmp_path / 'shots'
    board_calls: list = []
    log_calls: list = []
    board = types.SimpleNamespace(
        note_obs_event=lambda *a, **kw: board_calls.append((a, kw)))
    monkeypatch.setattr(mod, '_SHOT_DIR', shot_dir)
    monkeypatch.setattr(mod.cw_telemetry_exit, 'obs_event_board', lambda: board)
    monkeypatch.setattr(mod.cw_telemetry_exit, 'current_run_id', lambda: 'run_x')
    monkeypatch.setattr(mod, 'cw_log', lambda *a, **kw: log_calls.append((a, kw)))
    monkeypatch.setattr(mod, '_conflict_shot_ts', {})
    return shot_dir, board_calls, log_calls


def test_cw_shot_offline_no_file_returns_none(observe_env) -> None:
    """离线帧:cw_shot 不建目录、不写文件、返 None;实时帧照常落盘并返回文件名。"""
    shot_dir, _, _ = observe_env
    with offline_frame():
        assert mod.cw_shot(_FRAME, 'x') is None
    assert not shot_dir.exists()
    assert mod.cw_shot(_FRAME, 'x') == 'x.png'
    assert (shot_dir / 'x.png').is_file()


def test_cw_shot_unique_offline_no_file_returns_none(observe_env) -> None:
    """离线帧:cw_shot_unique 不落盘、返 None(与「已采过」同形);实时帧照常。"""
    shot_dir, _, _ = observe_env
    with offline_frame():
        assert mod.cw_shot_unique(_FRAME, 'lbl') is None
    assert not shot_dir.exists()
    name = mod.cw_shot_unique(_FRAME, 'lbl')
    assert name is not None and name.startswith('lbl__')
    assert (shot_dir / name).is_file()


def test_obs_conflict_offline_no_shot_no_board_non_attn(observe_env) -> None:
    """离线帧:传了帧也不存图、不入账;日志行照打,attn=False 且 offline=1。"""
    shot_dir, board_calls, log_calls = observe_env
    with offline_frame():
        mod.obs_conflict('gold', 3, 98, _FRAME, verdict='采新', source='gold_settle_gate')
    assert not shot_dir.exists()
    assert board_calls == []
    assert len(log_calls) == 1
    args, kwargs = log_calls[0]
    assert args[:3] == ('obs', 'conflict', 'gold')
    assert kwargs['attn'] is False and kwargs['offline'] == 1
    assert kwargs['old'] == 3 and kwargs['new'] == 98
    assert mod._conflict_shot_ts == {}, '离线帧下截图节流字典不得推进'


def test_obs_conflict_live_shot_board_attn(observe_env) -> None:
    """实时帧:存去重截图 + 入账(证据行带 shot)+ 日志行 attn=True 无 offline 键。"""
    shot_dir, board_calls, log_calls = observe_env
    mod.obs_conflict('gold', 3, 98, _FRAME, verdict='采新', source='gold_settle_gate')
    files = list(shot_dir.iterdir())
    assert len(files) == 1 and files[0].name.startswith('obs_conflict_gold__')
    assert len(board_calls) == 1
    (_kind, field, payload), kw = board_calls[0]
    assert field == 'gold' and payload['old'] == 3 and payload['new'] == 98
    assert kw['evidence_refs'] == [{'shot': files[0].name}]
    args, kwargs = log_calls[0]
    assert kwargs['attn'] is True and 'offline' not in kwargs
    assert kwargs['shot'] == files[0].name
