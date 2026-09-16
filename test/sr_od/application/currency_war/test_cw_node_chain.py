"""链观察载体锁(NodeChain/TokenCell + node_path/baseline 字段 + 查询口)。

出处 = docs/develop/sr_od/application/currency_war/changes/
2026-09-16-chain-observation-landing/landing.md §3.1(载体升级批);
语义正本 = game_state/chain-observation.md §2/§6。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    BS_SCHEMA_VERSION,
    DEFAULT_BS_SCHEMA,
    ChannelSig,
    GameState,
    NodeChain,
    TokenCell,
    chain_node_type,
    register_sig_actors,
)

register_sig_actors('TestChainWriter')
_SIG = ChannelSig(family='obs', actor='TestChainWriter', mode='read')


def _chain(plane: int, *tokens: str | None) -> NodeChain:
    """构造测试链:逐 token 生成 hu 通道格(None → none 通道)。"""
    cells = [TokenCell(token=t, channel=('none' if t is None else 'hu'))
             for t in tokens]
    return NodeChain(plane=plane, seq=cells)


def test_node_chain_fields_default_and_whole_frame_replace():
    """字段缺省 None;现行链整帧覆盖(不按位合并);基线独立不被现行链写触碰。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    assert bs.node_path.value is None
    assert bs.node_path_baseline.value is None
    bs.observe(bs.node_path, _chain(1, 'reward', 'battle'),
               evidence='t', sig=_SIG)
    first = bs.node_path.value
    assert first is not None and first.plane == 1 \
        and first.seq[1].token == 'battle'
    bs.observe(bs.node_path, _chain(1, None, None, 'supply'),
               evidence='t', sig=_SIG)
    second = bs.node_path.value
    assert len(second.seq) == 3 and second.seq[0].token is None, \
        '整帧覆盖:第二帧全量替换,不留旧位'
    assert bs.node_path_baseline.value is None, \
        '现行链写不触基线(两字段独立)'
    bs.observe(bs.node_path_baseline, _chain(1, 'reward'),
               evidence='t', sig=_SIG)
    assert bs.node_path_baseline.value.seq[0].token == 'reward'


def test_chain_node_type_query_states():
    """查询口四态:命中/该格未辨/位越界/位面不匹配,外加链未写与零内建回落。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    assert chain_node_type(bs, 1, 2).token is None, '链未写 = 诚实缺位'
    bs.observe(bs.node_path, _chain(1, 'reward', None, 'battle'),
               evidence='t', sig=_SIG)
    assert chain_node_type(bs, 1, 1).token == 'reward'
    assert chain_node_type(bs, 1, 2).token is None, '该格未辨(None)'
    assert chain_node_type(bs, 1, 4).token is None, '位越界'
    assert chain_node_type(bs, 2, 1).token is None, '位面不匹配'
    bs.observe(bs.node_path_baseline,
               _chain(1, 'encounter', 'encounter', 'encounter'),
               evidence='t', sig=_SIG)
    assert chain_node_type(bs, 1, 2).token is None, \
        '零内建回落:基线在场也不兜底(链正本 §6)'


def test_node_domain_schema_version_bumped():
    """node 域版本 = 2(node_path 值形 NodeChain + baseline 字段,升版注记在册)。"""
    assert DEFAULT_BS_SCHEMA['node'] == 2
    assert BS_SCHEMA_VERSION >= 1
