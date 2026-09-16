"""链 diff 纯函数与触发面锁(链观察落地批 landing.md §3.4;语义正本 =
game_state/chain-observation.md §4/§5)。

chain_diff = 数学单一源(实机与 sim 共用);maybe_emit_chain_diff = 触发面
(两帧门/离场豁免/变异窗豁免;发射走 note_obs_event,journal sink 缺省关
= 零副作用,测试以实例方法捕获断言)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    BS_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeChain,
    TokenCell,
    chain_diff,
    maybe_emit_chain_diff,
    register_sig_actors,
)

register_sig_actors('TestChainWriter')
_SIG = ChannelSig(family='obs', actor='TestChainWriter', mode='read')


def _chain(*tokens: str | None, channels: tuple[str, ...] | None = None,
           plane: int = 1) -> NodeChain:
    chs = channels or ('hu',) * len(tokens)
    cells = [TokenCell(token=t, channel=ch)
             for t, ch in zip(tokens, chs, strict=True)]
    return NodeChain(plane=plane, seq=cells)


def test_chain_diff_rewrite_and_channel_limited():
    """改写位(双 token 非 None 且不等)与通道受限差(基线 hu/现行 label 且
    仅标签 token)分流;first_diff_pos = 首个 token 差异位。"""
    baseline = _chain('battle', 'battle', 'supply')
    current = NodeChain(plane=1, seq=[
        TokenCell('encounter', 'hu'),    # 改写:hu vs hu 且不等
        TokenCell('elite', 'label'),     # 通道受限差(基线 hu/现行 label/仅标签)
        TokenCell('supply', 'hu'),       # 无差
    ])
    diff = chain_diff(baseline, current)
    assert diff.rewrites == (0,) and diff.channel_limited == (1,)
    assert diff.first_diff_pos == 0 and not diff.length_changed
    assert diff.baseline_coverage == ()


def test_chain_diff_length_and_coverage():
    """长度差(增节点)与基线 None 洞位集(基线未辨位显影)。"""
    baseline = _chain('battle', None, 'supply')          # 槽 1 = 基线未辨
    current = _chain('battle', 'battle', 'supply', 'reward')
    diff = chain_diff(baseline, current)
    assert diff.length_changed is True
    assert diff.baseline_coverage == (1,)
    assert diff.rewrites == () and diff.first_diff_pos is None


def test_chain_diff_no_diff_empty():
    diff = chain_diff(_chain('battle', 'supply'), _chain('battle', 'supply'))
    assert not (diff.rewrites or diff.channel_limited
                or diff.length_changed or diff.baseline_coverage)


def test_maybe_emit_two_frame_gate_and_snapshot_exempt():
    """两帧门:首见候选不落行,连续两帧一致才落;离场快照单帧即落。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.node_path_baseline, _chain('battle', 'battle'),
               evidence='t', sig=_SIG)
    emitted: list[dict] = []
    bs.note_obs_event = (  # 实例级捕获(链正本 §5:发射走 note_obs_event)
        lambda event, field, payload, verdict=None, sig=None:
        emitted.append(payload))

    cur = _chain('battle', 'reward')   # 槽 1 改写
    bs.observe(bs.node_path, cur, evidence='t', sig=_SIG)
    assert maybe_emit_chain_diff(bs, snapshot=False,
                                 in_mutation_window=False,
                                 sig=_SIG) is False, '首见候选不落行'
    assert maybe_emit_chain_diff(bs, snapshot=False,
                                 in_mutation_window=False,
                                 sig=_SIG) is True, '连续两帧一致 → 落行'
    assert len(emitted) == 1 and emitted[0]['rewrites'] == [1]
    assert emitted[0]['baseline']['seq'][0]['token'] == 'battle'

    # 离场快照豁免两帧门(单帧即终审)
    cur2 = _chain('reward', 'reward')
    bs.observe(bs.node_path, cur2, evidence='t', sig=_SIG)
    assert maybe_emit_chain_diff(bs, snapshot=True,
                                 in_mutation_window=False,
                                 sig=_SIG) is True
    assert len(emitted) == 2 and emitted[1]['snapshot'] is True


def test_maybe_emit_window_and_no_diff_and_no_baseline():
    """变异窗豁免清候选;无差异清候选不落行;基线缺 → False。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    emitted: list[dict] = []
    bs.note_obs_event = (
        lambda event, field, payload, verdict=None, sig=None:
        emitted.append(payload))
    # 基线缺
    bs.observe(bs.node_path, _chain('battle'), evidence='t', sig=_SIG)
    assert maybe_emit_chain_diff(bs, snapshot=False,
                                 in_mutation_window=False,
                                 sig=_SIG) is False
    # 无差异
    bs.observe(bs.node_path_baseline, _chain('battle'), evidence='t',
               sig=_SIG)
    assert maybe_emit_chain_diff(bs, snapshot=False,
                                 in_mutation_window=False,
                                 sig=_SIG) is False
    # 变异窗:候选被清
    bs.observe(bs.node_path_baseline, _chain('battle', 'battle'),
               evidence='t', sig=_SIG)
    bs.observe(bs.node_path, _chain('battle', 'reward'), evidence='t',
               sig=_SIG)
    assert maybe_emit_chain_diff(bs, snapshot=False,
                                 in_mutation_window=True,
                                 sig=_SIG) is False
    assert bs.node_path_diff_pending is None, '窗内豁免清候选'
    assert emitted == []
