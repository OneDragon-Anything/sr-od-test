"""逐光捡金共享随机选人策略纯函数单测(不连真游戏、零副作用)。

锁设计约定(见 src/sr_od/application/treasures_lightward/random_team.py 模块
docstring 与末日幻影迭代设计稿 §8):无放回抽取、恰抽 行数×4 个、互不相同、
池不足显式报错;换人重选的候选名提取与剔除重选。
"""

from __future__ import annotations

import pytest

from sr_od.application.treasures_lightward.random_team import (
    extract_missing_name,
    pick_random_teams,
    re_pick,
)


def test_抽取数量为行数乘四():
    """双节点 8 人、星启 12 人,与编队填充的构造校验口径对齐。"""
    pool = [f'角色{i}' for i in range(20)]
    assert len(pick_random_teams(pool, 2)) == 8
    assert len(pick_random_teams(pool, 3)) == 12


def test_无放回抽取互不重复():
    """同一名字至多出现一次(末日幻影要求两/三队角色互不相同)。"""
    pool = [f'角色{i}' for i in range(20)]
    picked = pick_random_teams(pool, 3)
    assert len(set(picked)) == len(picked) == 12
    for name in picked:
        assert name in pool


def test_池不足显式报错():
    """人数不足抛 ValueError(调用方转节点失败,消息可直接展示)。"""
    with pytest.raises(ValueError):
        pick_random_teams(['甲', '乙', '丙'], 2)


def test_提取扫不到的候选名():
    """填充失败状态原文提取;非该形态失败返回 None。"""
    assert extract_missing_name('列表到底未找到 三月七') == '三月七'
    assert extract_missing_name('列表到底未找到 开拓者•存护') == '开拓者•存护'
    assert extract_missing_name('战斗失败') is None
    assert extract_missing_name(None) is None


def test_重选剔除后抽取():
    """re_pick 在已过滤池上剔除不可扫名后仍满足数量约定。"""
    pool = [f'角色{i}' for i in range(20)]
    picked = re_pick(pool, {'角色0', '角色1'}, 2)
    assert len(picked) == 8
    assert '角色0' not in picked and '角色1' not in picked
    with pytest.raises(ValueError):
        re_pick(['甲', '乙', '丙'], {'甲'}, 2)
