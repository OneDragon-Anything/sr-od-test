from one_dragon.base.screen import screen_utils
from test import SrTestBase


class TestGetMatchScreenName(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    def test_get_match_screen_name(self):
        screen_map = {
            'normal_world_basic': '大世界-普通',
            'bag_upgrade_material': '背包-养成材料',
            'bag_light_cone': '背包-光锥',
            'bag_relic': '背包-遗器',
            'bag_other_material': '背包-其他材料',
            'bag_consumable': '背包-消耗品',
            'bag_mission': '背包-任务',
            'bag_valuable': '背包-贵重物',
            'bag_pet': '背包-随宠',
            'bag_relic_salvage': '背包-遗器分解',
            'bag_relic_salvage_filter': '背包-遗器分解-快速选择'
        }
        for image_name, screen_name in screen_map.items():
            screen = self.get_test_image(image_name)
            result = screen_utils.get_match_screen_name(self.ctx, screen)
            self.assertEqual(screen_name, result)
