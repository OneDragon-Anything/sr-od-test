"""进入游戏 op:同意按钮位置测试(旧/新登录画面)。"""
from __future__ import annotations

from pathlib import Path

from one_dragon.utils import cv2_utils
from sr_od.operations.enter_game.enter_game import EnterGame


def test_agree(test_context, test_image_dir: Path) -> None:
    """测试同意按钮的位置。"""
    op = EnterGame(test_context)

    screen = cv2_utils.read_image(str(test_image_dir / 'old_login.png'))
    r1 = op.round_by_find_area(screen, '进入游戏', '文本-同意-旧')
    assert r1.is_success
    r2 = op.round_by_find_area(screen, '进入游戏', '文本-同意-新')
    assert not r2.is_success

    screen = cv2_utils.read_image(str(test_image_dir / 'new_login.png'))
    r1 = op.round_by_find_area(screen, '进入游戏', '文本-同意-旧')
    assert not r1.is_success
    r2 = op.round_by_find_area(screen, '进入游戏', '文本-同意-新')
    assert r2.is_success
