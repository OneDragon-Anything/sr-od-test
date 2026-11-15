"""pick_random_teams 随机选人策略纯函数单测(不连真游戏、零副作用)。

锁设计约定(见 src/sr_od/application/apocalyptic_shadow/strategy.py 模块 docstring
与迭代设计稿 §8):无放回抽取、恰抽 行数×4 个、互不相同、池不足显式报错。
"""

from __future__ import annotations

import pytest

from sr_od.application.apocalyptic_shadow.strategy import pick_random_teams


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
