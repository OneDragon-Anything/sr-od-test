"""test_cw_grail_collect_hooks:圣杯任务采集钩子(方案 B,B1 钉屏停机 + B2 被动哈希采集)。

覆盖钩子逻辑本身(sentinel 三要素落盘 / 停机调用 / best-effort / 哈希去重 / 节流);
钩子未接线(激活批一行接线),零真实副作用(flag/截图路径全部 monkeypatch 到 tmp_path)。
"""
from __future__ import annotations

import numpy as np
import pytest

import sr_od.application.currency_war.kernel.cw_observe as cw_observe
import sr_od.application.currency_war.operations.grail_collect_hooks as hooks


def _img(v: int = 128, h: int = 1080, w: int = 1920) -> np.ndarray:
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = v
    return img


class _FakeRunContext:
    def __init__(self):
        self.stop_calls: list[str] = []

    def stop_running(self, reason: str = '') -> None:
        self.stop_calls.append(reason)


class _FakeController:
    def __init__(self):
        self.frames: list[np.ndarray] = [_img(64)]

    def screenshot(self, independent: bool = False):
        return (0.0, self.frames.pop(0) if self.frames else None)


class _FakeCtx:
    def __init__(self):
        self.run_context = _FakeRunContext()
        self.controller = _FakeController()


class _FakeOp:
    """离线 op 桩:B1 只用 save_screenshot / ctx / round_wait。"""

    def __init__(self, fail_snap: bool = False):
        self.ctx = _FakeCtx()
        self.snap_calls: list[str] = []
        self._fail_snap = fail_snap
        self.wait_status: str | None = None

    def save_screenshot(self, prefix: str = '') -> str:
        if self._fail_snap:
            raise RuntimeError('snap failed')
        self.snap_calls.append(prefix)
        return f'{prefix}_main.png'

    def round_wait(self, status: str = '', wait: float = 0):
        self.wait_status = status
        return ('wait', status)


@pytest.fixture(autouse=True)
def _isolate_paths(monkeypatch, tmp_path):
    """隔离两处落盘点:flag 路径与 cw_shot_unique 的 shots 目录均指 tmp_path。"""
    monkeypatch.setattr(hooks, '_FLAG_PATH', tmp_path / 'grail_pin.flag')
    monkeypatch.setattr(cw_observe, '_SHOT_DIR', tmp_path / 'shots')
    hooks._LAST_SHOT_TS.clear()
    yield
    hooks._LAST_SHOT_TS.clear()


# ==================== B1 钉屏停机钩子 ====================

def test_b1_writes_sentinel_flag_with_three_elements(tmp_path):
    """flag 三要素齐备:HOOK-STOP 定位 + 可执行处理步骤 + 删除条件。"""
    op = _FakeOp()
    out = hooks.grail_pin_stop_hook(op)
    flag_text = (tmp_path / 'grail_pin.flag').read_text(encoding='utf-8')
    assert '[HOOK-STOP]' in flag_text
    assert 'grail_pin_stop_hook' in flag_text          # 触发定位(钩子位置)
    assert '处理步骤' in flag_text                       # 要素②:可执行处理步骤
    assert '删除条件' in flag_text                       # 要素③:删除条件
    assert '标识-祈愿试炼' in flag_text                  # 触发态
    assert op.snap_calls == ['cw_grail_pin']            # sentinel 主帧已存
    assert out == ('wait', op.wait_status)              # 返回 round_wait(不点击保画面)


def test_b1_stops_run_and_parks_screen():
    """直调 stop_running(不经 MCP)且不派发 handler:桩上无 click 通道可被调用。"""
    op = _FakeOp()
    hooks.grail_pin_stop_hook(op)
    assert op.ctx.run_context.stop_calls == ['hook:cw_grail_pin']
    assert op.ctx.controller.frames == []               # 补帧被消费,再无动作


def test_b1_best_effort_still_stops_on_snap_failure():
    """sentinel 落盘失败不拦停机(保画面优先)。"""
    op = _FakeOp(fail_snap=True)
    out = hooks.grail_pin_stop_hook(op)
    assert op.ctx.run_context.stop_calls == ['hook:cw_grail_pin']
    assert out[0] == 'wait'


def test_b1_second_frame_best_effort_missing_frame():
    """补帧源耗尽(controller 无帧)不抛异常,主流程照常停机。"""
    op = _FakeOp()
    op.ctx.controller.frames = []
    hooks.grail_pin_stop_hook(op)
    assert op.ctx.run_context.stop_calls == ['hook:cw_grail_pin']


# ==================== B2 被动哈希采集钩子 ====================

def test_b2_dedup_same_content_saved_once(tmp_path):
    """内容哈希去重:同一视觉内容只落盘一次,第二次返 None。"""
    fn1 = hooks.grail_passive_collect(_img(128))
    fn2 = hooks.grail_passive_collect(_img(128))
    assert fn1 is not None and fn1.startswith('grail_obs__')
    assert fn2 is None
    assert len(list((tmp_path / 'shots').glob('*.png'))) == 1


def test_b2_throttle_blocks_within_window(tmp_path):
    """节流窗内(即使内容不同)不落盘;状态清零后恢复采集。"""
    assert hooks.grail_passive_collect(_img(10)) is not None
    assert hooks.grail_passive_collect(_img(20)) is None    # 窗内跳过
    hooks._LAST_SHOT_TS.clear()                              # 模拟窗过期
    assert hooks.grail_passive_collect(_img(20)) is not None


def test_b2_none_screen_skipped():
    assert hooks.grail_passive_collect(None) is None
