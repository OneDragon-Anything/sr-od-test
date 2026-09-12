"""模拟宇宙 楼层/子态识别测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from one_dragon.utils import cv2_utils
from sr_od.application.sim_universe import sim_uni_screen_state
from sr_od.application.sim_universe.sim_uni_data import SimUniLevelTypeEnum


def test_match_next_level_entry(test_context, test_image_dir: Path) -> None:
    screen = cv2_utils.read_image(str(test_image_dir / 'next_level_1.png'))
    result_list = sim_uni_screen_state.match_next_level_entry(
        test_context, screen, knn_distance_percent=0.7,
    )
    print(len(result_list))
    assert len(result_list) == 2


@pytest.mark.parametrize('img, expected', [
    ('sim_uni_combat', SimUniLevelTypeEnum.COMBAT.value),
    ('sim_uni_elite', SimUniLevelTypeEnum.ELITE.value),
    ('sim_uni_respite', SimUniLevelTypeEnum.RESPITE.value),
])
def test_get_level_type(test_context, test_image_dir: Path, img: str, expected) -> None:
    """楼层类型判定:区域-战斗/精英/休整 → COMBAT/ELITE/RESPITE。"""
    screen = cv2_utils.read_image(str(test_image_dir / f'{img}.png'))
    result = sim_uni_screen_state.get_level_type(test_context, screen)
    assert result == expected, f'{img} 应为 {expected.type_name} 实际 {result}'


@pytest.mark.parametrize('img, expected', [
    ('sim_uni_choose_bless', sim_uni_screen_state.ScreenState.SIM_BLESS.value),
    ('sim_uni_choose_curio', sim_uni_screen_state.ScreenState.SIM_CURIOS.value),
    ('sim_uni_event', sim_uni_screen_state.ScreenState.SIM_EVENT.value),
    ('sim_uni_reward', sim_uni_screen_state.ScreenState.SIM_REWARD.value),
])
def test_get_sim_uni_screen_state(test_context, test_image_dir: Path, img: str, expected) -> None:
    """子态判定:选择祝福/奇物/事件/沉浸奖励 → SIM_BLESS/CURIOS/EVENT/REWARD。"""
    screen = cv2_utils.read_image(str(test_image_dir / f'{img}.png'))
    result = sim_uni_screen_state.get_sim_uni_screen_state(
        test_context, screen, bless=True, curio=True, event=True, reward=True,
    )
    assert result == expected, f'{img} 应为 {expected} 实际 {result}'
