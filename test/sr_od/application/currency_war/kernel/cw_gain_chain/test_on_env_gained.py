"""on_env_gained 持续伤害契约分支测试:即时腿回归 + 锚键腿(镜像 src =
kernel/cw_gain_chain.py 的该被测函数,按拆目录规范落位;同函数兄弟测试 =
kernel/test_gain_chain.py ENV_GIFTS 分道段〔超限只读复用〕)。

测试面依据 = T-28 设计稿(迭代 2026-09-23-invest-effects-calc,
designs/T-28-chixu-shanghai-qiyue.md)§2.1/§2.4 + §4.3:
- **即时腿回归**:获得环境当刻 gain_character 发椒丘+卡芙卡(desc 无
  数量/星级词,单数缺省 1★ 先验族)——本批零改动,回归锁;
- **锚键腿**:'dot_anchor#<位面>-<轮>' 纯登记件非门控,获得刻与即时腿
  同窗相邻 write_logic 直写(同 evidence 同 sig);节点未知不写且须显式
  判 node——``_node_frame`` 未观察返回空串,照抄会产出 'dot_anchor#-'
  畸形键;开局三选一获取时 sim 节点未进窗 → 缺锚 = 预期形态。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_env_grants import (
    DOT_CONTRACT_ENV,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    GAIN_CHAIN_PRODUCER,
    on_env_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    NodeKey,
)

_ENV = DOT_CONTRACT_ENV
_SIG = ChannelSig(family='logic_action', actor='CwGainChain', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_EVIDENCE = f'on_env_gained:{_ENV}'


def _make_gs(*, node: bool = False) -> GameState:
    """直构容器(bench = 开局种子底座 9 空槽);``node`` = 节点窗已开。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty')] * 9,
                                   capacity=9), sig=_SIG_OBS)
    if node:
        gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='battle'),
                   sig=_SIG_OBS)
    return gs


def _bench_units(gs: GameState) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def _record_writes(gs: GameState,
                   monkeypatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道,
    sig, produced_by) 写行(先例 = kernel/test_gain_chain.py 同族 helper)。"""
    calls: list[tuple[str, str | None, str, ChannelSig, str]] = []

    def _wrap(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((gs._field_name(target), evidence, channel, sig,
                          produced_by))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'write_logic', _wrap(gs.write_logic, 'logic'))
    return calls


def test_immediate_leg_and_anchor_same_window(
        monkeypatch) -> None:
    """即时腿 + 锚键腿同窗(设计稿 §2.4/§2.1):节点窗已开时获得环境 →
    bench 增椒丘+卡芙卡(1★ 确定发放,即时腿零改动回归)+ done 追加锚键
    'dot_anchor#1-3'(纯登记非门控,与即时腿同 evidence 同 sig 相邻,
    write_logic 直写登记事实)。"""
    gs = _make_gs(node=True)
    calls = _record_writes(gs, monkeypatch)
    effects = on_env_gained(gs, None, _ENV, rand=False, sig=_SIG)
    assert effects == ('env_gift:椒丘', 'env_gift:卡芙卡'), '即时腿效果串'
    assert _bench_units(gs) == [('椒丘', 1), ('卡芙卡', 1)], '两名 1★ 入席'
    assert gs.env_grants_done.value == ((_ENV, 'dot_anchor#1-3'),), \
        '锚键纯登记(帧 = 位面-轮)'
    done_rows = [(c[0], c[1], c[2], c[4]) for c in calls
                 if c[0] == 'env_grants_done']
    assert done_rows == [('env_grants_done', _EVIDENCE, 'logic',
                          GAIN_CHAIN_PRODUCER)], f'锚键单笔直写: {done_rows}'
    assert calls[-1][3] == _SIG, '锚键与即时腿同 sig(同窗相邻)'


def test_anchor_skipped_when_node_not_in_window(monkeypatch) -> None:
    """节点未知不写(设计稿 §2.1 显式判 node + §4.1⑥ 缺锚形态):开局
    三选一获取时 sim 节点尚未进窗(node None)→ 即时腿照常、零锚键零
    畸形键(缺锚不影响猜测写/计数/证实,check_env_dot_grants 门控 =
    active_env)。"""
    gs = _make_gs(node=False)
    calls = _record_writes(gs, monkeypatch)
    effects = on_env_gained(gs, None, _ENV, rand=False, sig=_SIG)
    assert effects == ('env_gift:椒丘', 'env_gift:卡芙卡'), '即时腿照常'
    assert not gs.env_grants_done.value, '零锚键(开局形态预期)'
    assert all('dot_anchor' not in (c[1] or '') for c in calls), \
        '无畸形键痕迹(禁 dot_anchor#- 形态)'


def test_skill_point_contract_immediate_leg_regression(monkeypatch) -> None:
    """战技点契约即时腿回归(T-29 设计 §1/§4 锁 8):获得环境当刻
    chars_immediate 逐名确定发放(1★,desc 无数量/星级词单数缺省)→
    bench 增丹恒·饮月+花火各 1——现役通道逐位不变,锁不被晶矿开启
    条件腿批次扰动;获得刻零晶矿触发 done(条件腿归
    check_env_ore_open_grants,打开晶矿计数达标才发,获得刻零预登记)。"""
    gs = _make_gs()
    calls = _record_writes(gs, monkeypatch)
    effects = on_env_gained(gs, None, '战技点契约', rand=False, sig=_SIG)
    assert effects == ('env_gift:丹恒·饮月', 'env_gift:花火'), '即时腿效果串'
    assert _bench_units(gs) == [('丹恒·饮月', 1), ('花火', 1)], \
        '两名 1★ 入席(确定发放)'
    assert gs.env_grants_done.value is None, '获得刻零晶矿触发 done'
    assert all('ore_open' not in (c[1] or '') for c in calls), \
        '零 ore_open 写行痕迹(条件腿不随获得刻触发)'
