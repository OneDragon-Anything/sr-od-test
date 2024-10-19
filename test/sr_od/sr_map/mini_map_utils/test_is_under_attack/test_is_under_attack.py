from sr_od.sr_map import mini_map_utils
from test import SrTestBase


class TestIsUnderAttack(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    def test_under_attack(self):
        mm = self.get_test_image('under_1.png')
        self.assertTrue(mini_map_utils.is_under_attack(mm, show=False, strict=False))

        mm = self.get_test_image('under_2.png')
        self.assertTrue(mini_map_utils.is_under_attack(mm, show=False, strict=True))

        mm = self.get_test_image('under_3.png')
        self.assertFalse(mini_map_utils.is_under_attack(mm, show=False))

        mm = self.get_test_image('under_4.png')
        self.assertFalse(mini_map_utils.is_under_attack(mm, show=False, strict=True))

        mm = self.get_test_image('under_5.png')
        self.assertFalse(mini_map_utils.is_under_attack(mm, show=False, strict=True))
