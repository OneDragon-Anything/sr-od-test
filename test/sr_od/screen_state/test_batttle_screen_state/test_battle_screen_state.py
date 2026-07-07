import os
import pytest

pytestmark = __import__('pytest').mark.skipif(bool(__import__('os').environ.get('CI')), reason='需完整 SR 数据栈（screen 配置/模板/OCR），CI clean checkout 无；本地有数据则跑')

from sr_od.screen_state import battle_screen_state
from test import SrTestBase


class TestBattleScreenState(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    def test_is_battle_fail(self):
        screen = self.get_test_image('normal_world_battle_fail.png')
        self.assertTrue(battle_screen_state.is_battle_fail(self.ctx, screen))