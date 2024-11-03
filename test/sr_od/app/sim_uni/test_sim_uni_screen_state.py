from sr_od.app.sim_uni import sim_uni_screen_state
from test import SrTestBase


class TestSimUniScreenState(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    def test_match_next_level_entry(self):
        screen = self.get_test_image('next_level_1.png')
        result_list = sim_uni_screen_state.match_next_level_entry(self.ctx, screen, knn_distance_percent=0.7)
        print(len(result_list))
        self.assertTrue(len(result_list) == 2)
