"""game_config 窗口标题随语言联动单测。

锁的内容（设计约定）：游戏内切文本语言会连窗口标题一起改，控制器按标题
查找窗口 —— ``win_title`` 必须与 ``lang`` 同步（cn/en 两值 + 未知值回退），
不同步的表现是运行结束后窗口失明。
"""

from sr_od.config.game_config import GameConfig


def test_win_title_follows_lang() -> None:
    config = GameConfig(1)
    original = config.lang
    try:
        config.lang = 'cn'
        assert config.win_title == '崩坏：星穹铁道'
        config.lang = 'en'
        assert config.win_title == 'Honkai: Star Rail'
        config.lang = 'unknown'
        assert config.win_title == '崩坏：星穹铁道'
    finally:
        config.lang = original
