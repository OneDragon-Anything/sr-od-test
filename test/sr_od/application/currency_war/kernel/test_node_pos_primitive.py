"""序列模块键原语 NodePos / sequence_next · 测试面(四态契约)。

设计依据: abolish-node-ordinal 迭代 design.md §2.1(后继原语四态
契约、``seqs`` 缺省 = 默认表与 ``node_sequence_of`` 同参约定、
NodePos 字典序 = 有效序列按位面拼接展平的全序);语义收敛正本 =
``docs/develop/sr_od/application/currency_war/game_state/
node-derivation.md`` §3.3(键原语)。测试面地图:

- 四态:位面内后继 / 位面末跨下一位面首 / pos 位面无表或下位面无表
  → None(超出建模域,调用方按局终处理)/ modeled 位面内越界 →
  ValueError 响亮;
- 两口径:默认表 + T-8 场字段修饰表(``resolve_plane_node_seqs``
  产物,P1=10/P2=8);
- P3 口径对照:后继原语优雅 None vs 序列直查 P3UnobservedError 响亮。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_node_schedule import (
    NodePos,
    P3UnobservedError,
    node_sequence_of,
    resolve_plane_node_seqs,
    sequence_next,
)

_MODIFIED = resolve_plane_node_seqs('人身意外险')


def test_sequence_next_default_table_full_walk() -> None:
    """默认表展平全走:(1,1) 逐位后继到 (1,9) → (2,1) 逐位到
    (2,7);P2 末 (2,7) 位面末且下一位面无表 → None(全程 16 节点
    = 9 + 7)。"""
    pos: NodePos = (1, 1)
    walk: list[NodePos] = [pos]
    while True:
        nxt = sequence_next(pos)
        if nxt is None:
            break
        walk.append(nxt)
        pos = nxt
    expected = ([(1, r) for r in range(1, 10)]
                + [(2, r) for r in range(1, 8)])
    assert walk == expected
    assert sequence_next((2, 7)) is None, 'P2 末无下一位面表 → 局终口径'


def test_sequence_next_modified_table_two_digit_round() -> None:
    """修饰表(T-8 场字段形态 P1=10/P2=8):(1,9) → (1,10) 两位数
    轮次普通后继 → (2,1) 跨位面;(2,8) 位面末 → None;位面内其余
    后继位置语义与默认表同构,仅序列长度随场字段。"""
    mod = _MODIFIED
    assert sequence_next((1, 8), mod) == (1, 9)
    assert sequence_next((1, 9), mod) == (1, 10), '修饰局两位数轮次'
    assert sequence_next((1, 10), mod) == (2, 1)
    assert sequence_next((2, 7), mod) == (2, 8)
    assert sequence_next((2, 8), mod) is None, '修饰局 P2 末 → 局终口径'


def test_sequence_next_unmodeled_none_and_overrun_raises_and_p3_query() \
        -> None:
    """建模域边界三态:(3,1) 位面无表 → None(live 真局进 P3 的锚定
    形态,局终由调用方声明);(1,11) modeled 位面内越界 → ValueError
    响亮,两口径同判(默认 len 9 / 修饰 len 10 均拒 11);同一位面无表
    事实走序列直查 node_sequence_of 仍响亮 P3UnobservedError(直查
    路径拦截现状不变,后继原语按 None 返回)。"""
    assert sequence_next((3, 1)) is None
    assert sequence_next((3, 1), _MODIFIED) is None
    with pytest.raises(ValueError):
        sequence_next((1, 11))
    with pytest.raises(ValueError):
        sequence_next((1, 11), _MODIFIED)
    with pytest.raises(P3UnobservedError):
        node_sequence_of(3)
