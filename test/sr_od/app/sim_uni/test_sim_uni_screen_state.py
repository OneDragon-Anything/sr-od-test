from sr_od.application.sim_universe import sim_uni_screen_state
from sr_od.application.sim_universe.sim_uni_data import SimUniLevelTypeEnum
from test import SrTestBase


class TestSimUniScreenState(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    def test_match_next_level_entry(self):
        screen = self.get_test_image('next_level_1.png')
        result_list = sim_uni_screen_state.match_next_level_entry(self.ctx, screen, knn_distance_percent=0.7)
        print(len(result_list))
        self.assertTrue(len(result_list) == 2)

    def test_get_level_type(self):
        """楼层类型判定:区域-战斗/精英/休整 → COMBAT/ELITE/RESPITE"""
        cases = [
            ('sim_uni_combat', SimUniLevelTypeEnum.COMBAT.value),
            ('sim_uni_elite', SimUniLevelTypeEnum.ELITE.value),
            ('sim_uni_respite', SimUniLevelTypeEnum.RESPITE.value),
        ]
        for img, expected in cases:
            with self.subTest(img=img):
                screen = self.get_test_image(img)
                result = sim_uni_screen_state.get_level_type(self.ctx, screen)
                self.assertEqual(result, expected, f'{img} 应为 {expected.type_name} 实际 {result}')

    def test_get_sim_uni_screen_state(self):
        """子态判定:选择祝福/奇物/事件/沉浸奖励 → SIM_BLESS/CURIOS/EVENT/REWARD"""
        cases = [
            ('sim_uni_choose_bless', sim_uni_screen_state.ScreenState.SIM_BLESS.value),
            ('sim_uni_choose_curio', sim_uni_screen_state.ScreenState.SIM_CURIOS.value),
            ('sim_uni_event', sim_uni_screen_state.ScreenState.SIM_EVENT.value),
            ('sim_uni_reward', sim_uni_screen_state.ScreenState.SIM_REWARD.value),
        ]
        for img, expected in cases:
            with self.subTest(img=img):
                screen = self.get_test_image(img)
                result = sim_uni_screen_state.get_sim_uni_screen_state(
                    self.ctx, screen, bless=True, curio=True, event=True, reward=True
                )
                self.assertEqual(result, expected, f'{img} 应为 {expected} 实际 {result}')
