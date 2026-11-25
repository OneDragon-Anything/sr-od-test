"""结算屏胜负标识解析(``parse_settlement_verdict`` 三态 + ``parse_settlement_won`` 委托等价)。

锁的设计约定(标定依据见 src cw_settlement_obs.py ``parse_settlement_verdict`` docstring):
- 标题词 → 三态:挑战成功→win / 挑战失败→failed / 挑战结束→ended;三词皆无→None(不冒认)。
- 判定走全等子串不走 LCS 相似:兄弟词(成功/结束/失败 两两共享「挑战」前缀)不得互串——
  这是画面档标题 area 曾因默认 lcs 0.5 放行兄弟词的同一缺陷,识别器侧以子串全等锁死。
- ``parse_settlement_won`` 委托后行为等价:win→True、failed→False、ended→None(非 killed,
  交进度符号分支);标题词全缺时进度符号分支照常。

帧级真 OCR 三态复放住 test_settlement_recognizer.py(area 命中组合 + 识别器 verdict)。

结算屏金存量稳定门(``read_settle_gold_opt``)重读帧剧本测试(同值采信 / 首读失败补采 /
帧间在动取末帧):

锁的设计约定(契约正文 = src cw_settlement_obs.py ``read_settle_gold_opt`` /
``_read_settle_gold_gated`` docstring;docs/develop/sr_od/application/currency_war/screens/
battle_wait.md 结算金读链句):

- 首读失败(渲染未就绪形态)→ 隔 ``SETTLE_GOLD_INTERVAL_S`` 补采一帧;读到 → 继续走帧间
  稳定轮询;仍失败 → None,不再轮询;
- 帧间**同值** → 采信、零告警;帧间在动 → 补采到同值或 ``SETTLE_GOLD_MAX_POLLS`` 上限,
  取**末帧** + warning(不静默)——首读旧值不得被采信;
- **重读帧必须真送进读链,且每次睡都换来一次真读**:控制器截图口返回 ``(时刻, 帧)`` 元组,
  读链要收到帧本身——门把元组当帧传读链时,读链切片异常被门的 ``except Exception`` 吞成
  「补采不可得」:首读失败形态恒返 None(胜局金读数全灭),首读成功形态白睡且门失效。
  本文件用哨兵帧直证 + 睡眠计数对账;
- 重读不可得(截图口抛异常 / 帧为 None)→ 保留已读值,读链只被首读调用,零告警。

金门被测 = 纯逻辑门(经公开入口 ``read_settle_gold_opt``):读链 ``_read_settle_gold_once``
与截图口打桩成剧本,不读真图。
"""
from __future__ import annotations

import types

import numpy as np
import pytest

import sr_od.application.currency_war.obs.cw_settlement_obs as mod
from sr_od.application.currency_war.obs.cw_settlement_obs import (
    SETTLE_VERDICT_ENDED,
    SETTLE_VERDICT_FAILED,
    SETTLE_VERDICT_WIN,
    parse_settlement_verdict,
    parse_settlement_won,
    read_settle_gold_opt,
)


@pytest.mark.parametrize(('texts', 'expected'), [
    (['挑战成功', '1-3X点', '战斗', '继续挑战'], SETTLE_VERDICT_WIN),
    # 标题与节点类型粘连成一个 token(实跑形态)仍按子串命中
    (['挑战成功战斗', '小队生命值82i'], SETTLE_VERDICT_WIN),
    (['挑战失败', '小队生命值0', '下一步'], SETTLE_VERDICT_FAILED),
    (['挑战结束', '1-9', '首领', '小队生命值1i', '继续挑战'], SETTLE_VERDICT_ENDED),
    (['挑战结束', '2-2战斗', '挑战进度', '-22', '前往结算'], SETTLE_VERDICT_ENDED),
    # 标题词全缺 → None(不冒认任何一态)
    ([], None),
    (['小队生命值79i', '获得金币总览', '继续挑战'], None),
])
def test_verdict_three_states(texts: list[str], expected: str | None) -> None:
    """标题词 → 三态 / 全缺 → None。"""
    assert parse_settlement_verdict(texts) == expected


def test_won_delegates_to_verdict_without_changing_killed_semantics() -> None:
    """``parse_settlement_won`` 委托后 killed 语义等价:win→True / failed→False /
    ended→None(非 killed)/ 标题词全缺走进度符号分支。"""
    assert parse_settlement_won(['挑战成功', '继续挑战']) is True
    assert parse_settlement_won(['挑战失败', '下一步']) is False
    # 「挑战结束」含平局式结束,不得判成输(ended → None)
    assert parse_settlement_won(['挑战结束', '继续挑战']) is None
    # 标题词全缺时进度符号分支照常:负 → 输,正 → 赢,无进度 → None
    assert parse_settlement_won(['挑战进度', '-22']) is False
    assert parse_settlement_won(['挑战进度', '+2']) is True
    assert parse_settlement_won(['小队生命值79i']) is None


# ===== 结算屏金存量稳定门 =====

#: 调用方传入的首帧(可切片即可;读链替身对首帧同样做切片)
_FRAME1: np.ndarray = np.ones((4, 4, 3), dtype=np.uint8)
#: 重读帧哨兵(可切片的帧数组):读链必须收到它本身,不是 ``(时刻, 帧)`` 元组。
_FRAME2: np.ndarray = np.zeros((4, 4, 3), dtype=np.uint8)


def _settle_gold_env(monkeypatch: pytest.MonkeyPatch, shot, readings: list[int | None],
                     ) -> tuple[types.SimpleNamespace, list, list, list[float], list]:
    """结算金稳定门夹具。``shot`` = 截图口剧本(截图返回值,或要抛的异常实例);
    ``readings`` = 读链替身按调用序返回的值(首读在内)。返回 (假 ctx, 读链收到的
    screen 列表〔首读在内〕, 睡眠时长列表, warning 捕获列表)。"""
    got: list = []
    sleeps: list[float] = []
    warnings: list = []
    it = iter(readings)

    def fake_screenshot():
        if isinstance(shot, Exception):
            raise shot
        return shot

    def fake_read_once(ctx, screen):
        screen[0:1, 0:1]   # 真读链第一步就是切片裁区域:元组在此抛 TypeError(与生产同形)
        got.append(screen)
        return next(it)

    monkeypatch.setattr(mod, '_read_settle_gold_once', fake_read_once)
    # log.warning(格式串, *插值) 是惰性格式化:替身收全部位置参数,不真格式化
    monkeypatch.setattr(mod, 'log', types.SimpleNamespace(warning=lambda *a: warnings.append(a)))
    # 模块级 ``time`` 引用即全局 time 模块:桩 sleep 为计数,测试零真睡
    monkeypatch.setattr(mod.time, 'sleep', lambda s: sleeps.append(s))
    ctrl = types.SimpleNamespace(screenshot=fake_screenshot)
    return types.SimpleNamespace(controller=ctrl), got, sleeps, warnings


@pytest.mark.parametrize(('readings', 'expected', 'reloads', 'warn_n'), [
    ([None, 11, 11], 11, 2, 0),   # 首读失败 → 补采一帧读到,再轮询同值 → 采信
    ([9, 9], 9, 1, 0),            # 帧间同值 → 采信,零告警
    ([9, 13, 13], 13, 2, 1),      # 帧间在动 → 不采信首读,取末帧 + warning
    ([9, 10, 11], 11, 2, 1),      # 一直在跳 → 补采到上限取末帧 + warning
    ([None, None], None, 1, 0),   # 首读失败补采仍失败 → None,不再轮询
])
def test_settle_gold_gate(monkeypatch: pytest.MonkeyPatch, readings: list,
                          expected: int | None, reloads: int, warn_n: int) -> None:
    """补采帧真送进读链:首读失败补采 / 同值采信 / 在动取末帧告警;每次睡都换来一次真读。"""
    ctx, got, sleeps, warnings = _settle_gold_env(monkeypatch, (0.0, _FRAME2), readings)
    assert read_settle_gold_opt(ctx, _FRAME1) == expected
    assert got[1:] == [_FRAME2] * reloads, '读链须收到截图口返回的帧本身,不是 (时刻, 帧) 元组'
    assert len(sleeps) == reloads, '零白睡:睡一次读链就须真读一次'
    assert len(warnings) == warn_n


@pytest.mark.parametrize('shot', [RuntimeError('截图链异常'), (0.0, None)],
                         ids=['raise', 'none-frame'])
def test_settle_gold_reload_unavailable(monkeypatch: pytest.MonkeyPatch, shot) -> None:
    """重读不可得(截图口抛异常 / 帧为 None)→ 首读可得时保留首读(读链只被首读调用),
    首读失败时维持读失败;均零告警。"""
    ctx, got, sleeps, warnings = _settle_gold_env(monkeypatch, shot, [9])
    assert read_settle_gold_opt(ctx, _FRAME1) == 9
    assert got == [_FRAME1] and warnings == []
    ctx, got, sleeps, warnings = _settle_gold_env(monkeypatch, shot, [None])
    assert read_settle_gold_opt(ctx, _FRAME1) is None
    assert got == [_FRAME1] and warnings == []
