from sr_od.operations.enter_game.enter_game import EnterGame
from test import SrTestBase


class TestBattleScreenState(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    def test_agree(self) -> None:
        """
        测试同意按钮的位置
        """
        op = EnterGame(self.ctx)

        screen = self.get_test_image('old_login.png')
        r1 = op.round_by_find_area(screen, '进入游戏', '文本-同意-旧')
        self.assertTrue(r1.is_success)
        r2 = op.round_by_find_area(screen, '进入游戏', '文本-同意-新')
        self.assertFalse(r2.is_success)

        screen = self.get_test_image('new_login.png')
        r1 = op.round_by_find_area(screen, '进入游戏', '文本-同意-旧')
        self.assertFalse(r1.is_success)
        r2 = op.round_by_find_area(screen, '进入游戏', '文本-同意-新')
        self.assertTrue(r2.is_success)
