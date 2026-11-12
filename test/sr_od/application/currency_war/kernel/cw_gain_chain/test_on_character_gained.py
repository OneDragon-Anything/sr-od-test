"""on_character_gained 条件形态转发测试(镜像 src =
kernel/cw_gain_chain.py 的该被测函数,按拆目录规范落位)。

测试面依据 = T-42 设计(原稿锁面
原稿锁面)§4 锁 2(获得链渠道,收敛点行为锁):
active_env=特邀专家:银狼 局直调 gain_character('银狼LV.999') → 解锁;
直调 gain_character('银狼')(顾问本身)→ 不触发(名不命中,无自触发
循环锁);银狼LV.999 合成升星产物重触发 → 幂等零写。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_character,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
)

_SIG = ChannelSig(family='logic_action', actor='CwGainChain', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_ENV = '特邀专家:银狼'


def _make_gs(bench: list[tuple[str, int]]) -> GameState:
    """直构状态容器 + active_env 注册写(本卡);置一次性标志位 = 确定面通道断言
    (未落一次性标志位链写走随机态通道属既定通道规则,与本锁焦点无关)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
             for c, s in bench]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.write_logic(gs.active_env, _ENV, produced_by='TestWriter',
                   evidence='t', sig=_SIG)
    gs.prep_anchored = True
    return gs


def _record_unlock_writes(gs: GameState, monkeypatch) -> list[str]:
    """包装两写通道记录 unlocked_experts 行 evidence(先例 =
    kernel/cw_gain_chain/test_on_env_gained.py 同族 helper)。"""
    calls: list[str] = []

    def _wrap(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            if gs._field_name(target) == 'unlocked_experts':
                calls.append(f'{channel}:{evidence}')
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic_rand', _wrap(gs.write_logic_rand,
                                                      'rand'))
    monkeypatch.setattr(gs, 'write_logic', _wrap(gs.write_logic, 'logic'))
    return calls


def _bench_units(gs: GameState) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def test_gain_lv999_unlocks_expert(monkeypatch) -> None:
    """收敛点行为锁(设计 §4 锁 2 主分支):本卡局获得银狼LV.999 → 解锁
    银狼入商店 + 效果串 expert_unlock:银狼(经 GainOutcome.effects 对外);
    解锁写恰一行。"""
    gs = _make_gs(bench=[])
    calls = _record_unlock_writes(gs, monkeypatch)
    out = gain_character(gs, '银狼LV.999', 1, rand=False, sig=_SIG,
                         evidence='g', producer='T')
    assert out.placed is True, '落位正常'
    assert 'expert_unlock:银狼' in out.effects, \
        f'效果串经收敛点对外: {out.effects}'
    assert gs.unlocked_experts.value == ('银狼',), '解锁写入'
    assert calls == ['logic:on_character_gained#expert_unlock'], \
        f'解锁写恰一行 + evidence 族后缀: {calls}'


def test_gain_advisor_itself_no_trigger() -> None:
    """无自触发循环锁(设计 §4 锁 2 条 2):获得顾问本身(银狼)名不
    命中条件① → 零解锁写零效果串(解锁与获得不同名,效果文事件 =
    「获得银狼LV.999」)。"""
    gs = _make_gs(bench=[])
    out = gain_character(gs, '银狼', 1, rand=False, sig=_SIG,
                         evidence='g', producer='T')
    assert out.placed is True and out.effects == (), '落位正常零效果串'
    assert gs.unlocked_experts.value in (None, ()), '零解锁写'


def test_starup_product_retrigger_idempotent(monkeypatch) -> None:
    """升星产物重触发幂等(设计 §4 锁 2 条 3):2×1★银狼LV.999 在席,
    获得第三只 → 首次获得解锁 + 合成 2★ 产物递归重进收敛点 → 判据条件③
    短路 → 解锁写全场恰一行(防重发不立第二账本)。"""
    gs = _make_gs(bench=[('银狼LV.999', 1), ('银狼LV.999', 1)])
    calls = _record_unlock_writes(gs, monkeypatch)
    out = gain_character(gs, '银狼LV.999', 1, rand=False, sig=_SIG,
                         evidence='g', producer='T')
    assert out.placed is True and out.merge_levels == 1, \
        f'落位 + 一级合成: {out}'
    assert gs.unlocked_experts.value == ('银狼',), '解锁写入(去重单份)'
    assert len(calls) == 1, f'解锁写恰一行(产物重进幂等零写): {calls}'
    assert _bench_units(gs) == [('银狼LV.999', 2)], '合成产物终态'
