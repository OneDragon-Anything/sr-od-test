"""上阵规模占用数派生读口测试(``cw_game_state.team_size_used_of`` 族 + 策略帧空位)。

锁的设计约定(契约正文 = ``team_size_used_of`` / ``team_size_over_cap_of`` docstring
与 ``MandateFrame.deploy_vacancy``;来源 = 备战屏团队规模超限态诊断):

- 占用数口径 = **各单位占用之和**:上阵单位数 + 主角光环持有者的额外占用
  (「上阵该角色占用 2 团队规模」——持有者在场才计;不在场 / 无光环 / 代价 1
  → 与旧口径「单位数」逐位相同);
- 判据(诊断报告 §5 状态容器行):高傲巨人 + 5 个单位 + 上限 5 → 占用 6、超限
  真、策略帧空位 0(旧口径空位 = 5 − 5 = 0 但「板满合法」,识别不出超限);
- 观察值字段 ``team_size_used`` 与派生值并存:派生值「可算出来的不存储」,观察值
  是游戏计数器真值(本文件不测写入端,写入端归 obs 读链)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
    max_units_of,
    team_size_over_cap_of,
    team_size_used_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import mandate

_OBS = ChannelSig(family='obs', actor='test', mode='read')


def _unit(name: str) -> Unit:
    return Unit(char_id=name, star=1)


def _gs(chosen_aura: str | None = '高傲巨人', aura_slot: int | None = 2,
        holder_on_board: bool = True, deploy_cap: int = 5,
        level: int = 5) -> GameState:
    """局 43 超限态镜像:前排 2 + 后排 3 = 5 个单位(持有者在前排槽 2),
    Lv5 / cap 5。``holder_on_board=False`` = 槽 2 空、第 5 个单位站槽 3
    (仍 5 个单位,持有者不在场)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    fifth = _unit('灵砂') if holder_on_board else None
    front = [_unit('云璃'), fifth,
             None if holder_on_board else _unit('姬子·启行'), None]
    back = [_unit('三月七'), _unit('长夜月'), _unit('花火')]
    gs.observe(gs.deployed, DeployedView(front_slots=front, back_slots=back),
               sig=_OBS)
    gs.observe(gs.level, level, sig=_OBS)
    gs.observe(gs.deploy_cap, deploy_cap, sig=_OBS)
    if aura_slot is not None:
        gs.observe(gs.aura_slot, aura_slot, sig=_OBS)
    if chosen_aura is not None:
        gs.observe(gs.chosen_aura, chosen_aura, sig=_OBS)
    return gs


def test_proud_giant_holder_on_board_is_over_cap() -> None:
    """高傲巨人 + 5 单位 + 上限 5 → 占用 6、超限真。"""
    gs = _gs()
    assert max_units_of(gs) == 5
    assert team_size_used_of(gs) == 6
    assert team_size_over_cap_of(gs) is True


@pytest.mark.parametrize(('kwargs', 'expected'), [
    ({}, 6),                                              # 基准超限态
    ({'holder_on_board': False}, 5),                      # 持有者槽空 = 不在场,不额外占用
    ({'aura_slot': None}, 5),                             # 归属槽未知
    ({'aura_slot': 3}, 5),                                # 槽 3 为空
    ({'chosen_aura': None}, 5),                           # 无光环
    ({'chosen_aura': '从师'}, 5),                          # 代价 1 的光环
    ({'chosen_aura': '不存在的光环'}, 5),                   # 未知名缺省 1
])
def test_team_size_used_of_variants(kwargs: dict, expected: int) -> None:
    """额外占用只在「持有者在场 ∧ 光环代价 > 1」时计入。"""
    assert team_size_used_of(_gs(**kwargs)) == expected


def test_team_size_over_cap_follows_cap() -> None:
    """上限 6(升级后)→ 同板面 6/6 不超限。"""
    assert team_size_over_cap_of(_gs(deploy_cap=6)) is False
    assert team_size_used_of(_gs(deploy_cap=6)) == 6


def test_frame_vacancy_by_size_sum() -> None:
    """策略帧(生产装配 ``mandate.snapshot_frame``):空位按占用之和。"""
    over = mandate.snapshot_frame(_gs())
    assert over.team_size_used == 6, '帧装配应传派生占用数,不是单位数'
    assert over.deploy_vacancy == 0
    assert over.team_size_over_cap is True
    normal = mandate.snapshot_frame(_gs(chosen_aura=None))
    assert (normal.team_size_used, normal.deploy_vacancy,
            normal.team_size_over_cap) == (5, 0, False)
    room = mandate.snapshot_frame(_gs(chosen_aura=None, deploy_cap=7))
    assert (room.team_size_used, room.deploy_vacancy) == (5, 2)
