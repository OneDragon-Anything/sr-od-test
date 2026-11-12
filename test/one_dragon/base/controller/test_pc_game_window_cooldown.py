"""PcGameWindow 窗口查找冷却测试(节点级 mock)。

覆盖(2026-09-26 实证):游戏关闭后 win_rect 的失效重试触发 init_win 全桌面
窗口枚举,pygetwindow 在 hung 窗口场景挂起 40+ 分钟,同步调用堵死 MCP 事件
循环,所有请求超时。修复 = ① 句柄失效直接返回 None 不再枚举;② 查找失败进
冷却期,冷却期内 get_win 直接返回 None。
"""
from unittest.mock import MagicMock, patch

from one_dragon.base.controller.pc_game_window import PcGameWindow


def _make_window(win_title: str = '崩坏：星穹铁道') -> PcGameWindow:
    w = PcGameWindow(standard_width=1920, standard_height=1080)
    w.win_title = win_title
    return w


def test_init_fail_enters_cooldown_no_reenum() -> None:
    """找不到窗口 → 进入冷却期,冷却期内 get_win 不再触发枚举。"""
    w = _make_window()
    with patch('pyautogui.getWindowsWithTitle', return_value=[]) as enum_fn:
        assert w.get_win() is None
        assert enum_fn.call_count == 1
        assert w.get_win() is None
        assert w.get_win() is None
        assert enum_fn.call_count == 1  # 冷却期内不再枚举


def test_cooldown_expiry_allows_reenum() -> None:
    """冷却期过后 → 允许重新枚举(手动把冷却截止拨到过去模拟时间流逝)。"""
    w = _make_window()
    with patch('pyautogui.getWindowsWithTitle', return_value=[]) as enum_fn:
        w.get_win()
        assert enum_fn.call_count == 1
        w._init_fail_cooldown_until = 0.0  # 冷却已过期
        w.get_win()
        assert enum_fn.call_count == 2


def test_clear_cached_window_resets_cooldown() -> None:
    """主动刷新(标题变更/refresh_win)清冷却:允许立刻重新枚举。"""
    w = _make_window()
    with patch('pyautogui.getWindowsWithTitle', return_value=[]) as enum_fn:
        w.get_win()
        assert enum_fn.call_count == 1
        w._clear_cached_window()
        w.get_win()
        assert enum_fn.call_count == 2


def test_win_rect_dead_handle_returns_none_without_enum() -> None:
    """缓存句柄失效(IsWindow=0) → win_rect 直接返回 None,不触发全量枚举。"""
    w = _make_window()
    w._win = MagicMock()
    w._hWnd = 0x123456  # 假死句柄
    with patch('pyautogui.getWindowsWithTitle', return_value=[]) as enum_fn, \
         patch('ctypes.windll.user32.IsWindow', return_value=0), \
         patch.object(PcGameWindow, '_try_get_client_rect', return_value=(False, None)):
        assert w.win_rect is None
        assert enum_fn.call_count == 0  # 失效路径不枚举
