"""链观察载体锁(NodeChain/TokenCell + node_path/baseline 字段 + 查询口)。

出处 = docs/develop/sr_od/application/currency_war/changes/
2026-09-16-chain-observation-landing/landing.md §3.1(载体升级批);
语义正本 = game_state/chain-observation.md §2/§6。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_game_state import (
    BS_SCHEMA_VERSION,
    DEFAULT_BS_SCHEMA,
    ChannelSig,
    GameState,
    NodeChain,
    TokenCell,
    board_state_of,
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


def test_derivation_shop_panel_chain_query_writes_kind():
    """类型派生四②商店查现行链(landing §3.5 消费接线):店开上下文写入
    → node.kind = 查链直定值(目标 = hist 反解位);生产时序等价形态 =
    N-1 帧 upcoming Hu 在 N 帧进店时在位。"""
    session = SimpleNamespace()
    bs = board_state_of(session)
    bs.observe(bs.node_path, NodeChain(plane=1, seq=[
        TokenCell('reward', 'hu'), TokenCell('supply', 'hu', 1.1),
        TokenCell('battle', 'hu', 0.7),
    ]), evidence='t', sig=_SIG)
    bs.node_hist_ord = 2   # P1 r2(商店弹在 r2)
    bs.observe_screen_context('货币战争-备战-开商店', sig=_SIG)
    assert bs.node.value is not None, '直定写经节点域(node.kind)'
    assert (bs.node.value.plane, bs.node.value.round_num,
            bs.node.value.kind) == (1, 2, 'supply'), '查链直定 = hist 反解位类型'


def test_derivation_shop_panel_chain_missing_zero_write():
    """链缺位(未写)→ 零写(禁猜,kind 保持缺省);hist 未推进亦零写。"""
    session = SimpleNamespace()
    bs = board_state_of(session)
    bs.observe_screen_context('货币战争-备战-开商店', sig=_SIG)
    assert bs.node.value is None, '链缺位零写(零内建回落)'
    # hist 未推进:链在位亦零写(目标位不可知)
    bs.observe(bs.node_path, NodeChain(plane=1, seq=[
        TokenCell('supply', 'hu'), TokenCell('battle', 'hu'),
    ]), evidence='t', sig=_SIG)
    bs.observe_screen_context('货币战争-备战-开商店', sig=_SIG)
    assert bs.node.value is None, 'hist 未推进 = 目标位不可知零写'


def test_derivation_non_shop_screen_no_chain_query():
    """非商店画面零查链零写:备战画面不触发四②(kind 不被链值污染)。"""
    session = SimpleNamespace()
    bs = board_state_of(session)
    bs.observe(bs.node_path, NodeChain(plane=1, seq=[
        TokenCell('supply', 'hu'), TokenCell('battle', 'hu'),
    ]), evidence='t', sig=_SIG)
    bs.node_hist_ord = 2
    bs.observe_screen_context('货币战争-备战', sig=_SIG)
    assert bs.node.value is None, '非商店画面零查链零写'
