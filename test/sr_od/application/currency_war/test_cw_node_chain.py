"""链观察载体锁(NodeChain/TokenCell + node_path/baseline 字段 + 查询口)。

出处 = docs/develop/sr_od/application/currency_war/changes/
2026-09-16-chain-observation-landing/landing.md §3.1(载体升级批);
语义正本 = game_state/chain-observation.md §2/§6。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_game_state import (
    DEFAULT_GS_SCHEMA,
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeChain,
    NodeKey,
    TokenCell,
    chain_node_type,
    game_state_of,
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
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert gs.node_path.value is None
    assert gs.node_path_baseline.value is None
    gs.observe(gs.node_path, _chain(1, 'reward', 'battle'),
               evidence='t', sig=_SIG)
    first = gs.node_path.value
    assert first is not None and first.plane == 1 \
        and first.seq[1].token == 'battle'
    gs.observe(gs.node_path, _chain(1, None, None, 'supply'),
               evidence='t', sig=_SIG)
    second = gs.node_path.value
    assert len(second.seq) == 3 and second.seq[0].token is None, \
        '整帧覆盖:第二帧全量替换,不留旧位'
    assert gs.node_path_baseline.value is None, \
        '现行链写不触基线(两字段独立)'
    gs.observe(gs.node_path_baseline, _chain(1, 'reward'),
               evidence='t', sig=_SIG)
    assert gs.node_path_baseline.value.seq[0].token == 'reward'


def test_chain_node_type_query_states():
    """查询口四态:命中/该格未辨/位越界/位面不匹配,外加链未写与零内建回落。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert chain_node_type(gs, 1, 2).token is None, '链未写 = 诚实缺位'
    gs.observe(gs.node_path, _chain(1, 'reward', None, 'battle'),
               evidence='t', sig=_SIG)
    assert chain_node_type(gs, 1, 1).token == 'reward'
    assert chain_node_type(gs, 1, 2).token is None, '该格未辨(None)'
    assert chain_node_type(gs, 1, 4).token is None, '位越界'
    assert chain_node_type(gs, 2, 1).token is None, '位面不匹配'
    gs.observe(gs.node_path_baseline,
               _chain(1, 'encounter', 'encounter', 'encounter'),
               evidence='t', sig=_SIG)
    assert chain_node_type(gs, 1, 2).token is None, \
        '零内建回落:基线在场也不兜底(链正本 §6)'


def test_node_domain_schema_version_bumped():
    """node 域版本 = 2(node_path 值形 NodeChain + baseline 字段,升版注记在册)。"""
    assert DEFAULT_GS_SCHEMA['node'] == 2
    assert GAME_STATE_SCHEMA_VERSION >= 1


def test_derivation_shop_panel_chain_query_writes_kind():
    """类型派生四②商店查现行链(landing §3.5 消费接线):店开上下文写入
    → node.kind = 查链直定值(目标 = hist 反解位);生产时序等价形态 =
    N-1 帧 upcoming Hu 在 N 帧进店时在位。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node_path, NodeChain(plane=1, seq=[
        TokenCell('reward', 'hu'), TokenCell('supply', 'hu', 1.1),
        TokenCell('battle', 'hu', 0.7),
    ]), evidence='t', sig=_SIG)
    gs.node_hist_ord = 2   # P1 r2(商店弹在 r2)
    gs.observe_screen_context('货币战争-备战-开商店', sig=_SIG)
    assert gs.node.value is not None, '直定写经节点域(node.kind)'
    assert (gs.node.value.plane, gs.node.value.round_num,
            gs.node.value.kind) == (1, 2, 'supply'), '查链直定 = hist 反解位类型'


def test_derivation_shop_panel_chain_missing_zero_write():
    """链缺位(未写)→ 零写(禁猜,kind 保持缺省);hist 未推进亦零写。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe_screen_context('货币战争-备战-开商店', sig=_SIG)
    assert gs.node.value is None, '链缺位零写(零内建回落)'
    # hist 未推进:链在位亦零写(目标位不可知)
    gs.observe(gs.node_path, NodeChain(plane=1, seq=[
        TokenCell('supply', 'hu'), TokenCell('battle', 'hu'),
    ]), evidence='t', sig=_SIG)
    gs.observe_screen_context('货币战争-备战-开商店', sig=_SIG)
    assert gs.node.value is None, 'hist 未推进 = 目标位不可知零写'


def test_derivation_non_shop_screen_no_chain_query():
    """非商店画面零查链零写:备战画面不触发四②(kind 不被链值污染)。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node_path, NodeChain(plane=1, seq=[
        TokenCell('supply', 'hu'), TokenCell('battle', 'hu'),
    ]), evidence='t', sig=_SIG)
    gs.node_hist_ord = 2
    gs.observe_screen_context('货币战争-备战', sig=_SIG)
    assert gs.node.value is None, '非商店画面零查链零写'


_HOOK_SIG = ChannelSig(family='logic_hook', actor='TestChainWriter',
                       mode='compute')


def _seed_watermark(gs, ord_val: int) -> None:
    """推进水位播种(备战腿等价形态:node_ord 逻辑层 + hist 双写)。"""
    gs.write_logic(gs.node_ord, ord_val, produced_by='TestChainWriter',
                   sig=_HOOK_SIG)
    gs.node_hist_ord = ord_val


def test_derivation_shop_panel_targets_observed_node_not_stale_hist():
    """查链目标 = 生效序与观察镜像的最新者(20260918-reconcile 第 11 例
    事故形态回归锁,run_20260918_074040)。

    病理:镜像已被读链写到 r3(店开帧 votes 读,(1,3,reward),观察源),
    推进水位仍 r2(备战帧未过,备战腿未计数);旧写法按 hist 反解查链
    (1,2) 并把 logic 回写 (1,2,reward)——后续备战帧真读 (1,3,battle)
    对 logic 旧键类型失配 → 统一观察对账安灯停局。修法:目标取
    max(生效序, 镜像序) = r3,查链 (1,3) 直定 battle,失配不发生。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node_path, NodeChain(plane=1, seq=[
        TokenCell('reward', 'hu'), TokenCell('reward', 'hu', 0.1),
        TokenCell('battle', 'hu', 0.7),
    ]), evidence='t', sig=_SIG)
    _seed_watermark(gs, 2)
    gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='reward'),
               evidence='votes', sig=_SIG)

    gs.observe_screen_context('货币战争-备战-开商店', sig=_SIG)

    assert (gs.node.value.plane, gs.node.value.round_num,
            gs.node.value.kind) == (1, 3, 'battle'), \
        '查链目标 = 镜像序 r3(不回写 r2),类型 = 链值 battle'


def test_derivation_shop_panel_popup_advanced_hist_wins_over_stale_mirror():
    """max 取向的推进优先腿:弹窗腿先推进(hist=3)而镜像仍滞留 r2 时,
    查链目标 = hist(shop 弹在刚进入的节点上,与旧 hist 单源行为一致)。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node_path, NodeChain(plane=1, seq=[
        TokenCell('reward', 'hu'), TokenCell('supply', 'hu'),
        TokenCell('battle', 'hu', 0.7),
    ]), evidence='t', sig=_SIG)
    _seed_watermark(gs, 3)
    gs.observe(gs.node, NodeKey(plane=1, round_num=2, kind='reward'),
               evidence='votes', sig=_SIG)

    gs.observe_screen_context('货币战争-备战-开商店', sig=_SIG)

    assert (gs.node.value.plane, gs.node.value.round_num,
            gs.node.value.kind) == (1, 3, 'battle'), \
        '镜像滞留时目标 = 推进水位 r3(推进腿已计数的新节点)'


def test_derived_node_type_regression_write_dropped_with_event():
    """类型直定倒退免疫锁(R3 规则三同簇):目标序 < 镜像序 → 丢弃留证
    不写(镜像比派生目标鲜活,直定旧节点 = 把新节点回写旧键);镜像值
    保持,arbitrate obs_event 在案。走弹窗直定屏路径(投资策略 ∈ 直定
    映射,目标 = hist)。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='reward'),
               evidence='votes', sig=_SIG)
    _seed_watermark(gs, 2)
    events = []
    gs.note_obs_event = (  # 实例级捕获(obs_event 发射面)
        lambda event, field, payload, verdict='', sig=None:
        events.append((event, field, payload)))

    gs.observe_screen_context('货币战争-投资策略', sig=_SIG)

    assert (gs.node.value.plane, gs.node.value.round_num,
            gs.node.value.kind) == (1, 3, 'reward'), \
        '倒退直定丢弃:镜像 (1,3) 不被 (1,2,invest) 回写'
    assert events and events[0][0] == 'arbitrate' and events[0][1] == 'node'
    assert events[0][2]['target_ord'] == 2, '留证行携带被拒目标'
