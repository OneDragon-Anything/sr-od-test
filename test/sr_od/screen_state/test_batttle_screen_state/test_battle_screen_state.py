from sr_od.screen_state import battle_screen_state
from test import SrTestBase


class TestBattleScreenState(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    def test_is_battle_fail(self):
        screen = self.get_test_image('normal_world_battle_fail.png')
        self.assertTrue(battle_screen_state.is_battle_fail(self.ctx, screen))