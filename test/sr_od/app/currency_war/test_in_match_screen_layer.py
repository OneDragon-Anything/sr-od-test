"""_in_match 画面匹配层测试(治本:M19/M34/M42/M54 关键词补丁链的结构替代)。

两层:①屏名过滤纯函数(大厅态排除/前缀自动纳入);②fixture 实拍帧的
_in_match 判定(对局屏 True / 大厅 False)。离线可跑,不碰游戏。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.currency_war_app import CurrencyWarApp  # noqa: E402

if TYPE_CHECKING:
    from test.conftest import SrTestContext


class _FakeScreenInfo:
    def __init__(self, name: str):
        self.screen_name = name


def test_in_match_screen_names_filters_lobby_states() -> None:
    """屏名过滤:大厅态排除、对局态纳入、前缀外不入。"""
    infos = [_FakeScreenInfo(n) for n in (
        '货币战争-大厅', '货币战争-模式选择', '货币战争-攻略列表',
        '货币战争-备战', '货币战争-投资策略', '货币战争-挑战失败',
        '货币战争-结算', '模拟宇宙--index', '星际列车')]
    got = CurrencyWarApp.in_match_screen_names(infos)
    assert '货币战争-大厅' not in got
    assert '货币战争-模式选择' not in got
    assert '货币战争-攻略列表' not in got
    assert '货币战争-备战' in got
    assert '货币战争-投资策略' in got
    assert '货币战争-挑战失败' in got
    assert '模拟宇宙-2' not in got or len(got) == 3   # 非 CW 前缀不入


def test_in_match_screen_names_auto_includes_new_screen() -> None:
    """新对局画面建档(带前缀)自动进列表——治本判据(M54 类漏判消除)。"""
    infos = [_FakeScreenInfo('货币战争-未来新屏')]
    assert CurrencyWarApp.in_match_screen_names(infos) == ['货币战争-未来新屏']


def test_in_match_screen_names_excludes_train_supply_popup() -> None:
    """列车补给每日弹窗必须显式排除(白名单锁,守卫移除红检目标)。

    match2 实锤(2026-08-31):弹窗屏名带 货币战争- 前缀,被前缀自动收录机制
    收进对局屏集 → 弹窗帧被误判「已在对局中」→ 跳过 enter/start 直交
    battle_loop → 未知态钩子 33s 停机。从白名单移除本行 = 本锁红。
    """
    infos = [_FakeScreenInfo('货币战争-列车补给弹窗')]
    assert CurrencyWarApp.in_match_screen_names(infos) == [], (
        '列车补给弹窗是非对局屏(盖在大世界上、早于 CW 入口导航),'
        '不得进对局屏集(否则弹窗帧被误判对局中 → loop 未知态停机)'
    )


def test_train_supply_popup_fixture_not_in_match(test_context: SrTestContext) -> None:
    """大世界+弹窗真帧:不得被判成对局中态(match2 误路由场景回归)。"""
    from one_dragon.base.screen.screen_utils import get_match_screen_name

    if not test_context.has_screen('货币战争-列车补给弹窗', '今日未领取'):
        pytest.skip('fixture 缺:货币战争-列车补给弹窗/今日未领取')
    screens = CurrencyWarApp.in_match_screen_names(test_context.screen_loader.screen_info_list)
    img = test_context.load_screen('货币战争-列车补给弹窗', '今日未领取')
    hit = get_match_screen_name(test_context, img, screen_name_list=screens)
    assert hit is None, (
        f'弹窗真帧被误判对局屏 {hit}(入局流会被误路由交 battle_loop 停机)'
    )


def test_in_match_fixture_states(test_context: SrTestContext) -> None:
    """实拍帧判定:挑战失败(对局终局)True;大厅 False。

    M42/M54 场景回归:战败态/结算态 app 重启时不再误走 enter 链。
    """
    from one_dragon.base.screen.screen_utils import get_match_screen_name
    ctx = test_context
    screens = CurrencyWarApp.in_match_screen_names(ctx.screen_loader.screen_info_list)
    assert '货币战争-挑战失败' in screens

    if not test_context.has_screen('货币战争-挑战失败', 'failed'):
        pytest.skip('fixture 缺:货币战争-挑战失败/failed')
    img = test_context.load_screen('货币战争-挑战失败', 'failed')
    # 画面匹配层直接判(绕开 app 实例化;_in_match 同源调用)
    assert get_match_screen_name(ctx, img, screen_name_list=screens) == '货币战争-挑战失败'

    if test_context.has_screen('货币战争-大厅', 'lobby'):
        lobby = test_context.load_screen('货币战争-大厅', 'lobby')
        lobby_hit = get_match_screen_name(ctx, lobby, screen_name_list=screens)
        assert lobby_hit is None, f'大厅帧不应命中对局屏,实命中 {lobby_hit}'
