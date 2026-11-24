"""备战读金稳定门 ``read_gold_settled`` 重读帧剧本测试(同值采信 / 帧间在动取末帧)。

锁的设计约定(契约正文 = ``cw_observation.read_gold_settled`` docstring;strategy as-built
``15_observation_multisource_arbitration.md`` gold 行「单源+帧间稳定门(取末帧)」):

- 首读不可读 → None,零重读零睡;
- 首读可得 → 隔 ``GOLD_SETTLE_INTERVAL_S`` 补采重读:与上一帧**同值** → 采信、零证据;
  帧间在动 → 继续补采到同值或 ``GOLD_SETTLE_MAX_POLLS`` 上限,取**末帧**(入账计数器
  单调向上,末帧 = 入账后真值)+ ``obs_conflict('gold', 首帧, 末帧, source=
  'gold_settle_gate')`` 保留证据——首读旧值不得被采信;
- **重读帧必须真送进读链,且每次睡都换来一次真读**:控制器截图口返回 ``(时刻, 帧)``
  元组,读链要收到帧本身——门把元组当帧传读链时,读链切片异常被门的 ``except Exception``
  吞成「补采不可得」,稳定门静默退化成单帧读(入账计数器在跳时旧值照样喂 plan),且每次
  首读成功都白付一次睡眠。本文件用哨兵帧直证 + 睡眠计数对账;
- 重读不可得(截图口抛异常 / 帧为 None)→ 保留已读值,读链只被首读调用,零证据
  (不可得按不可得处理,不靠读链异常兜底)。

被测 = 纯逻辑门:读链 ``read_gold_opt`` 与截图口打桩成剧本,不读真图。
"""
from __future__ import annotations

import types

import numpy as np
import pytest

import sr_od.application.currency_war.obs.cw_observation as mod
from sr_od.application.currency_war.obs.cw_observation import read_gold_settled

#: 调用方传入的首帧(可切片即可;读链替身对首帧同样做切片)
_FRAME1: np.ndarray = np.ones((4, 4, 3), dtype=np.uint8)
#: 重读帧哨兵(可切片的帧数组):读链必须收到它本身,不是 ``(时刻, 帧)`` 元组。
_FRAME2: np.ndarray = np.zeros((4, 4, 3), dtype=np.uint8)


def _gold_gate_env(monkeypatch: pytest.MonkeyPatch, shot, readings: list[int | None],
                   ) -> tuple[types.SimpleNamespace, list[tuple], list, list[float]]:
    """读金稳定门夹具。``shot`` = 截图口剧本(截图返回值,或要抛的异常实例);
    ``readings`` = 读链替身按调用序返回的值(首读在内)。返回 (假 ctx, obs_conflict
    捕获列表, 读链收到的 screen 列表〔首读在内〕, 睡眠时长列表)。"""
    calls: list[tuple] = []
    got: list = []
    sleeps: list[float] = []
    it = iter(readings)

    def fake_screenshot():
        if isinstance(shot, Exception):
            raise shot
        return shot

    def fake_read_gold(ctx, screen):
        screen[0:1, 0:1]   # 真读链第一步就是切片裁区域:元组在此抛 TypeError(与生产同形)
        got.append(screen)
        return next(it)

    def fake_conflict(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(mod, 'read_gold_opt', fake_read_gold)
    monkeypatch.setattr(mod, 'obs_conflict', fake_conflict)
    # 模块级 ``time`` 引用即全局 time 模块:桩 sleep 为计数,测试零真睡
    monkeypatch.setattr(mod.time, 'sleep', lambda s: sleeps.append(s))
    ctrl = types.SimpleNamespace(screenshot=fake_screenshot)
    return types.SimpleNamespace(controller=ctrl), calls, got, sleeps


@pytest.mark.parametrize(('readings', 'expected', 'reloads', 'evidence_n'), [
    ([73, 73], 73, 1, 0),          # 同值 → 采信首读,零证据
    ([73, 75, 75], 75, 2, 1),      # 帧间在动 → 不采信首读,取末帧 + 留证
    ([73, 74, 75, 76], 76, 3, 1),  # 一直在跳 → 补采到上限取末帧 + 留证
    ([None], None, 0, 0),          # 首读不可读 → None,零重读零睡
])
def test_read_gold_settled_gate(monkeypatch: pytest.MonkeyPatch, readings: list,
                                expected: int | None, reloads: int, evidence_n: int) -> None:
    """补采帧真送进读链:同值采信 / 在动取末帧留证;每次睡都换来一次真读(零白睡)。"""
    ctx, calls, got, sleeps = _gold_gate_env(monkeypatch, (0.0, _FRAME2), readings)
    assert read_gold_settled(ctx, _FRAME1) == expected
    assert got[1:] == [_FRAME2] * reloads, '读链须收到截图口返回的帧本身,不是 (时刻, 帧) 元组'
    assert len(sleeps) == reloads, '零白睡:睡一次读链就须真读一次'
    assert len(calls) == evidence_n
    if evidence_n:
        (field, old, new, _screen), kwargs = calls[0]
        assert field == 'gold' and (old, new) == (readings[0], expected)
        assert kwargs['source'] == 'gold_settle_gate'


@pytest.mark.parametrize('shot', [RuntimeError('截图链异常'), (0.0, None)],
                         ids=['raise', 'none-frame'])
def test_read_gold_settled_reload_unavailable(monkeypatch: pytest.MonkeyPatch, shot) -> None:
    """重读不可得(截图口抛异常 / 帧为 None)→ 保留首读,读链只被首读调用一次,零证据。"""
    ctx, calls, got, sleeps = _gold_gate_env(monkeypatch, shot, [73])
    assert read_gold_settled(ctx, _FRAME1) == 73
    assert got == [_FRAME1] and calls == []
