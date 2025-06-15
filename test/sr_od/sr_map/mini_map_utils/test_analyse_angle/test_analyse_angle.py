from sr_od.sr_map import mini_map_utils
from test import SrTestBase


class TestAnalyseAngle(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    def test_analyse_angle(self):
        mini_map = self.get_test_image('0.png')
        angle = mini_map_utils.analyse_angle(mini_map)
        if angle > 180:
            angle = 360 - angle
        self.assertTrue(abs(angle) <= 2)