"""序列模块键原语 NodePos / sequence_next · 测试面(四态契约)。

设计依据: abolish-node-ordinal 迭代 design.md §2.1(后继原语四态
契约、``seqs`` 缺省 = 默认表与 ``node_sequence_of`` 同参约定、
NodePos 字典序 = 有效序列按位面拼接展平的全序);语义收敛正本 =
``docs/develop/sr_od/application/currency_war/game_state/
node-derivation.md`` §3.3(键原语)。测试面地图:

- 四态:位面内后继 / 位面末跨下一位面首 / pos 位面无表或下位面无表
  → None(超出序列表,调用方按局终处理——现役 = 位面 3 末之后 =
  对局胜利终局)/ modeled 位面内越界 → ValueError 响亮;
- 两口径:默认表(P1+P2+P3 全在表)+ 场字段修饰表
  (``resolve_plane_node_seqs`` 产物,P1=10/P2=8/P3=8);
- 直查/后继两口径对照:缺键直查 PlaneSeqMissingError 响亮 vs 后继
  原语优雅 None(表外位面(≥4)防御形态)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_node_schedule import (
    P3_NODE_SEQUENCE,
    NodePos,
    PlaneSeqMissingError,
    node_sequence_of,
    resolve_plane_node_seqs,
    sequence_next,
)

_MODIFIED = resolve_plane_node_seqs('人身意外险')


def test_sequence_next_default_table_full_walk() -> None:
    """默认表展平全走:(1,1) 逐位后继到 (1,9) → (2,1) 逐位到 (2,7)
    → (3,1) 逐位到 (3,7);P3 末 (3,7) 位面末且下一位面无表 → None
    (全程 23 节点 = 9 + 7 + 7,超位面 3 = 胜利终局口径)。"""
    pos: NodePos = (1, 1)
    walk: list[NodePos] = [pos]
    while True:
        nxt = sequence_next(pos)
        if nxt is None:
            break
        walk.append(nxt)
        pos = nxt
    expected = ([(1, r) for r in range(1, 10)]
                + [(2, r) for r in range(1, 8)]
                + [(3, r) for r in range(1, 8)])
    assert walk == expected
    assert sequence_next((3, 7)) is None, 'P3 末无下一位面表 → 局终口径'


def test_sequence_next_modified_table_two_digit_round() -> None:
    """修饰表(场字段形态 P1=10/P2=8/P3=8):(1,9) → (1,10) 两位数
    轮次普通后继 → (2,1) 跨位面;(2,8) → (3,1);(3,8) 位面末 →
    None;位面内其余后继位置语义与默认表同构,仅序列长度随场字段。"""
    mod = _MODIFIED
    assert sequence_next((1, 8), mod) == (1, 9)
    assert sequence_next((1, 9), mod) == (1, 10), '修饰局两位数轮次'
    assert sequence_next((1, 10), mod) == (2, 1)
    assert sequence_next((2, 7), mod) == (2, 8)
    assert sequence_next((2, 8), mod) == (3, 1), 'P2 末跨入 P3'
    assert sequence_next((3, 7), mod) == (3, 8), '修饰 P3 末槽 = boss'
    assert sequence_next((3, 8), mod) is None, '修饰局 P3 末 → 局终口径'


def test_sequence_next_out_of_domain_none_and_overrun_raises() -> None:
    """建模域边界三态:(4,1) 位面无表 → None(表外位面防御形态,局终
    由调用方声明);(1,11) modeled 位面内越界 → ValueError 响亮,两
    口径同判(默认 len 9 / 修饰 len 10 均拒 11)、P3 默认 len 7 拒 8;
    表外位面事实走序列直查 node_sequence_of 仍响亮
    PlaneSeqMissingError(直查缺键禁静默,后继原语按 None 返回)。"""
    assert sequence_next((4, 1)) is None
    assert sequence_next((4, 1), _MODIFIED) is None
    with pytest.raises(ValueError):
        sequence_next((1, 11))
    with pytest.raises(ValueError):
        sequence_next((1, 11), _MODIFIED)
    with pytest.raises(ValueError):
        sequence_next((3, 8))
    with pytest.raises(ValueError):
        sequence_next((3, 9), _MODIFIED)
    with pytest.raises(PlaneSeqMissingError):
        node_sequence_of(4)
    assert node_sequence_of(3) == P3_NODE_SEQUENCE, 'P3 直查已在表'
