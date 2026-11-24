"""cap 真值防抖门 ``_debounce_cap`` 重读帧剧本测试(域外首读经第二帧确认)。

锁的设计约定(契约正文 = ``cw_observation`` 模块注释「cap 真值防抖门」+
``_debounce_cap`` / ``read_deploy_cap_debounced`` docstring;strategy as-built
``15_observation_multisource_arbitration.md`` deploy_cap 行):

- 域 = ``level ≤ cap ≤ level + DEPLOY_CAP_MAX_DIFF``:域内首读 / 首读不可读 → 原值
  透传,零重读零证据;
- 域外首读 → 重读一帧:重读入域 → 采重读值(零证据);重读与首读**同值**且在绝对
  板面上界内 → 采信 + 留「采信-域外双帧一致」证据(上向真高档 / 下向 cap<level
  两向同判据);其余(不同值 / 同值但超绝对上界 / 重读不可得)→ 拒信 None + 留
  「拒信」证据;
- **重读帧必须真送进读链**:控制器截图口返回 ``(时刻, 帧)`` 元组,读链要收到的
  是帧本身——门把元组当帧传读链时,读链切片异常被门的 ``except Exception`` 吞成
  「重读不可得」,凡需重读的分支全部静默退化成拒信(防抖第二帧从未生效:域外真
  高档永远采信不了,决策退 level 估 → 后排槽位按 6 槽基线在 9 格板上跑)。本文件
  用哨兵帧直证:读链替身记录收到的 ``screen``,断言 == 哨兵帧。

被测 = 纯逻辑门:首读值直接传入,读链 ``read_deploy_cap`` 与截图口打桩成剧本,
不读真图(真实帧的域内读数由 ``test_read_deploy_paddle.py`` 夹具基线锁住)。
"""
from __future__ import annotations

import types

import numpy as np
import pytest

import sr_od.application.currency_war.obs.cw_observation as mod
from sr_od.application.currency_war.obs.cw_observation import _debounce_cap

#: 重读帧哨兵(可切片的帧数组):读链必须收到它本身,不是 ``(时刻, 帧)`` 元组。
_FRAME2: np.ndarray = np.zeros((4, 4, 3), dtype=np.uint8)


def _cap_gate_env(monkeypatch: pytest.MonkeyPatch, shot, cap2: int | None,
                  ) -> tuple[types.SimpleNamespace, list[tuple], list]:
    """cap 防抖门夹具。``shot`` = 截图口剧本(截图返回值,或要抛的异常实例);
    ``cap2`` = 读链替身返回值。返回 (假 ctx, obs_conflict 捕获列表, 读链收到的
    screen 列表)。"""
    calls: list[tuple] = []
    got: list = []

    def fake_screenshot():
        if isinstance(shot, Exception):
            raise shot
        return shot

    def fake_read_cap(ctx, screen, level=None):
        screen[0:1, 0:1]   # 真读链第一步就是切片裁区域:元组在此抛 TypeError(与生产同形)
        got.append(screen)
        return cap2

    def fake_conflict(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(mod, 'read_deploy_cap', fake_read_cap)
    monkeypatch.setattr(mod, 'obs_conflict', fake_conflict)
    ctrl = types.SimpleNamespace(screenshot=fake_screenshot)
    return types.SimpleNamespace(controller=ctrl), calls, got


@pytest.mark.parametrize(('cap', 'level', 'cap2', 'expected', 'verdict_in', 'evidence_n'), [
    (12, 8, 12, 12, '采信-域外双帧一致', 1),   # 上向:真高档 diff=4,重读同值 → 采信
    (4, 5, 4, 4, 'cap<level:对照 level 先验疑毒化', 1),   # 下向:重读同值 → 采信
    (12, 8, 9, 9, None, 0),                   # 重读入域 → 采重读值,零证据
    (12, 8, 11, None, '拒信', 1),             # 重读不同值 → 拒信
    (14, 8, 14, None, '拒信', 1),             # 同值但超绝对板面上界 → 拒信
])
def test_debounce_cap_out_of_domain_reread(monkeypatch: pytest.MonkeyPatch,
                                           cap: int, level: int, cap2: int | None,
                                           expected, verdict_in, evidence_n: int) -> None:
    """域外首读 → 重读帧真送进读链,按判据采信 / 拒信。"""
    ctx, calls, got = _cap_gate_env(monkeypatch, (0.0, _FRAME2), cap2)
    assert _debounce_cap(ctx, object(), cap, level) == expected
    assert got == [_FRAME2], '读链须收到截图口返回的帧本身,不是 (时刻, 帧) 元组'
    assert len(calls) == evidence_n
    if verdict_in is not None:
        (field, _old, _new, _screen), kwargs = calls[0]
        assert field == 'deploy_cap_domain'
        assert verdict_in in kwargs['verdict']


@pytest.mark.parametrize('shot', [RuntimeError('截图链异常'), (0.0, None)],
                         ids=['raise', 'none-frame'])
def test_debounce_cap_reread_unavailable(monkeypatch: pytest.MonkeyPatch, shot) -> None:
    """重读不可得(截图口抛异常 / 帧为 None)→ 拒信 None + 留「拒信」证据;读链
    零调用(不可得按不可得处理,不靠读链异常兜底)。"""
    ctx, calls, got = _cap_gate_env(monkeypatch, shot, 9)
    assert _debounce_cap(ctx, object(), 12, 8) is None
    assert got == []
    assert len(calls) == 1 and '拒信' in calls[0][1]['verdict']


def test_debounce_cap_in_domain_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    """域内首读 / 首读不可读 → 原值透传,零重读零证据。"""
    ctx, calls, got = _cap_gate_env(monkeypatch, AssertionError('不应重读'), 9)
    assert _debounce_cap(ctx, object(), 9, 8) == 9      # 域内 [level, level+2]
    assert _debounce_cap(ctx, object(), 10, 8) == 10    # 域上界
    assert _debounce_cap(ctx, object(), None, 8) is None
    assert calls == [] and got == []
