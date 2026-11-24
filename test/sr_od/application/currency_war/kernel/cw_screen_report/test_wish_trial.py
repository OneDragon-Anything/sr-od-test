"""祈愿试炼屏观察上报测试(report_screen_wish_trial_obs;权威版本 =
docs/develop/sr_od/application/currency_war/screens/op-layer.md §1.1「选择
坐标观察上报」条款,屏级口径 = screens/wish_trial.md §2 / §3 / §6)。

锁的故障形态(候选名域 ``wish_trial_opts`` 与坐标域 ``wish_trial_opts_xy``
同门双写,动作 op 按 idx 自坐标域取点):
- 错位双写:两域不等长仍写 → idx 指向的卡名与点击坐标错一张(落点错位)。
  写端构造守卫须在任何写入之前响亮暴露,名字域不得先落(防半写)。
- 空桶被剔 / 加空门跳写:归档帧实测 2 张卡、中桶空串(见
  test_cw_screen_wish_trial.py 真实帧用例),空桶照持才保候选下标 =
  画面物理卡位;剔掉空桶 = 策略 idx 落到别的卡。

演法 = 直调 report 函数写一次性局外 GameState,读两域值断言。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
from sr_od.application.currency_war.kernel.cw_screen_report.wish_trial import (
    CwScreenWishTrialObs,
    report_screen_wish_trial_obs,
)

_OPT: str = '命运圣杯星徽 进行一场难度3及以上的遭遇节点战斗'
_PTS: list[tuple[int, int]] = [(660, 340), (960, 340), (1260, 340)]


def test_report_writes_both_domains_verbatim_with_empty_buckets() -> None:
    """同门双写原样落:候选含空桶 ``['', X, '']`` + 3 点 → 两域值与顺序原样、
    长度 3 保留(空桶不剔)、来源 logic。"""
    gs = game_state_of(SimpleNamespace())
    obs = CwScreenWishTrialObs(on_screen=True, options=['', _OPT, ''],
                               option_points=_PTS, screen=object())

    report_screen_wish_trial_obs(gs, obs)

    assert gs.wish_trial_opts.value == ['', _OPT, ''], \
        f'名字域应原样写入(空桶照持),实际 {gs.wish_trial_opts.value!r}'
    assert gs.wish_trial_opts_xy.value == _PTS, \
        f'坐标域应原样写入,实际 {gs.wish_trial_opts_xy.value!r}'
    assert gs.wish_trial_opts.source == 'logic'
    assert gs.wish_trial_opts_xy.source == 'logic'


def test_report_length_mismatch_asserts_before_any_write() -> None:
    """错位双写防线:名字域 2 项 / 坐标域 3 点 → AssertionError,两域都未写
    (名字域不得先落)。"""
    gs = game_state_of(SimpleNamespace())
    obs = CwScreenWishTrialObs(on_screen=True, options=[_OPT, ''],
                               option_points=_PTS, screen=object())

    with pytest.raises(AssertionError, match='不同序等长'):
        report_screen_wish_trial_obs(gs, obs)

    assert gs.wish_trial_opts.value is None, '不等长时名字域不得先落'
    assert gs.wish_trial_opts_xy.value is None
