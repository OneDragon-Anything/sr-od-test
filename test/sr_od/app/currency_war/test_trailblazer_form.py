"""开拓者形态切换(前后台命途不同)计算正确性(用户 2026-08-16 指示;ADR-0158)。"""
import pytest

from sr_od.application.currency_war.data.cw_chars import (
    is_trailblazer,
    trailblazer_form,
)
from sr_od.application.currency_war.cw_observation import board_from_tracked
from sr_od.application.currency_war.kernel.cw_state import BenchChar, DeployMove, GameState, mutate_bench_deployed, simulate


def test_form_resolution_by_row():
    assert trailblazer_form('开拓者·欢愉', 'front') == '开拓者·记忆'
    assert trailblazer_form('开拓者·记忆', 'back') == '开拓者·欢愉'
    assert trailblazer_form('开拓者·欢愉', 'back') == '开拓者·欢愉'   # 已一致
    assert trailblazer_form('姬子·启行', 'front') == '姬子·启行'       # 非开拓者原样
    assert is_trailblazer('开拓者·记忆') and is_trailblazer('开拓者·欢愉')
    assert not is_trailblazer('姬子·启行')


def test_board_counts_follow_form():
    """羁绊计算按当前排形态:欢愉形态在前排 → 不计「欢愉」羁绊;拖到后排 → 计入。"""
    front_tb = BenchChar(slot=1, char_id='开拓者·欢愉', faction='列车同行', position_pref='front')
    b1 = board_from_tracked([front_tb])
    assert b1 is not None and '欢愉' not in b1   # 前排=记忆形态(列车+能量)
    back_tb = BenchChar(slot=1, char_id='开拓者·记忆', faction='列车同行', position_pref='back')
    b2 = board_from_tracked([back_tb])
    assert b2 is not None and b2.get('欢愉', 0) == 1   # 后排=欢愉形态 → 欢愉 +1


def test_simulate_deploy_switches_form():
    """simulate DeployMove:bench 欢愉形态拖前排 → deployed 变记忆形态(char_id/faction 同步)。"""
    st = GameState(gold=20, round_num=2, level=4, plane=1, hp=90,
                   bench=[BenchChar(slot=1, char_id='开拓者·欢愉', faction='列车同行', position_pref='back')],
                   deployed=[], board={})
    after = simulate(st, DeployMove(bench_idx=0, to_row='front', faction='列车同行'))
    assert after.deployed and after.deployed[0].char_id == '开拓者·记忆'
    assert after.deployed[0].position_pref == 'front'


def test_mutate_deploy_switches_form():
    bench = [BenchChar(slot=1, char_id='开拓者·欢愉', faction='列车同行')]
    deployed: list = []
    mutate_bench_deployed(bench, deployed, DeployMove(bench_idx=0, to_row='front', faction='列车同行'))
    assert deployed and deployed[0].char_id == '开拓者·记忆'
