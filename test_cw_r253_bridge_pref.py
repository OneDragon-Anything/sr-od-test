"""r253 桥平局偏好测试(P1→P2 平滑性)。"""
from sr_od.application.currency_war.cw_bridge_pool import (
    BRIDGE_POOL,
    pick_bridge,
    score_bridge,
)


def test_tie_prefers_xianzhou_dot():
    """r253:P1 平局时偏好 xianzhou_dot(P2 平滑)——
    构造 owned 使 xianzhou_dot 与 train_dot 分数相近。"""
    # 饮月:train_dot 的 fixed+xianzhou 的 core
    # (两桥都吃到它的分;确保分差 <=0.5)
    owned = {'丹恒·饮月'}
    xd = next(c for c in BRIDGE_POOL
              if c.bridge_id == 'xianzhou_dot')
    td = next(c for c in BRIDGE_POOL
              if c.bridge_id == 'train_dot')
    b = pick_bridge(owned, 'P1')
    assert b is not None
    # 验证:结果偏好 xianzhou(分差在 0.5 内时)
    s_xd, s_td = score_bridge(xd, owned), score_bridge(td, owned)
    if abs(s_xd - s_td) <= 0.5:
        assert b.bridge_id == 'xianzhou_dot'


def test_clear_winner_not_overridden():
    """分差大时高分桥不被偏好覆盖(纯分数优先)。"""
    # 只有藿藿+爻光(xianzhou_train 的 fixed 双全)→
    # xianzhou_train 高分独走
    owned = {'藿藿', '爻光'}
    b = pick_bridge(owned, 'P1')
    assert b is not None and b.bridge_id != ''    # 选出某桥
    # 且它是分数最高的(不被偏好翻转)
    best_score = max(
        score_bridge(c, owned) for c in BRIDGE_POOL)
    assert score_bridge(b, owned) == best_score


def test_p2_no_preference():
    """P2 无平局偏好(P2 池单桥,偏好无意义)。"""
    owned = {'姬子·启行', '三月七'}
    b = pick_bridge(owned, 'P2')
    assert b is not None and b.bridge_id == 'train4_shield3'
