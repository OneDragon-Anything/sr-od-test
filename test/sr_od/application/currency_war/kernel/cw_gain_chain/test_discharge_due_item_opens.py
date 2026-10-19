"""discharge_due_item_opens 倒计时件到点开盒原语测试(镜像 src =
kernel/cw_gain_chain.py 的该被测函数,按拆目录规范落位;同模块兄弟
测试 = test_on_env_gained.py / test_gain_character.py)。

测试面依据 = 迭代 T-34 命运礼物设计(.debug/progress/2026-09-23-
invest-effects-calc/designs/T-34-mingyun-liwu.md)§2.4 + §4 锁 4/5/9:
- **到点矩阵**:eff < unlock 零写零弹;eff = unlock 弹除;eff > unlock
  照常命中(「到了及以后都算」,错过不悬空);eff None 零写;命中集空
  零写;
- **零席位写**(战利品区件锁):开盒 = 队列弹除零消耗腿,bench/
  overflow/equips 逐位不变——防实现批按 v1 占席惯性加消耗腿;
- **独立弹除**:重复获得的两条队列条目按各自解锁位独立命中。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    discharge_due_item_opens,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
)

_SIG = ChannelSig(family='logic_action', actor='SimBackend', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='T')
_SIG_SEED = ChannelSig(family='logic_action', actor='test-seed',
                       mode='compute')


def _make_gs(*, node_pos: tuple[int, int] | None,
             queue: tuple = ()) -> GameState:
    """直构容器:生效序位观察锚定(sim 进节点收口时点 = 新序位已锚定);
    bench/equips 观察播种(零席位写断言的逐位对照基座);队列经 logic
    直写播种(测试自造输入)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if node_pos is not None:
        gs.observe(gs.node_pos, node_pos, sig=_SIG_OBS)
    gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty')] * 9,
                                   capacity=9), sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    if queue:
        gs.write_logic(gs.pending_item_opens, tuple(queue),
                       produced_by='test-seed', evidence='t:queue',
                       sig=_SIG_SEED)
    return gs


def _record_writes(gs: GameState, monkeypatch) -> list[str]:
    """包装 write_logic/write_logic_rand 两通道记录写字段名(通道选择 =
    _select_write 按锚定态现选,断言面只看字段与笔数,通道不作断言)。"""
    calls: list[str] = []

    def _wrap(real):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append(gs._field_name(target))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic', _wrap(gs.write_logic))
    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand))
    return calls


def test_due_matrix_zero_write_on_miss_or_unanchored(
        monkeypatch) -> None:
    """到点矩阵零写半边(T-34 设计 §4 锁 4):eff < unlock(未到点)/
    eff None(生效序位缺读,宁缺勿造)/ 命中集空(队列非空但全未到点)
    → 零效果串零容器写(write_seq 逐位不变),队列原样。"""
    for label, node_pos, queue in (
            ('未到点', (1, 2), (('惊喜盒', (2, 4)),)),
            ('eff None', None, (('惊喜盒', (1, 2)),)),
            ('命中集空', (1, 5), (('惊喜盒', (2, 4)), ('惊喜盒', (3, 1)))),
    ):
        gs = _make_gs(node_pos=node_pos, queue=queue)
        seq_before = gs.write_seq
        effects = discharge_due_item_opens(gs, rand=False, sig=_SIG)
        assert effects == (), f'{label} 零效果串'
        assert gs.write_seq == seq_before, f'{label} 零容器写'
        assert gs.pending_item_opens.value == queue, f'{label} 队列原样'


def test_due_at_and_after_unlock_discharges(monkeypatch) -> None:
    """到点命中半边(T-34 设计 §4 锁 4):eff = unlock 弹除 + 效果串
    item_opened:惊喜盒 + 一次 write 回写保留队列;eff > unlock 照常命中
    (到了及以后都算)。"""
    for label, node_pos in (('eff = unlock', (2, 4)),
                            ('eff > unlock', (2, 6))):
        gs = _make_gs(node_pos=node_pos, queue=(('惊喜盒', (2, 4)),))
        calls = _record_writes(gs, monkeypatch)
        effects = discharge_due_item_opens(gs, rand=False, sig=_SIG)
        assert effects == ('item_opened:惊喜盒',), f'{label} 效果串'
        assert gs.pending_item_opens.value == (), f'{label} 弹除清空'
        assert calls == ['pending_item_opens'], \
            f'{label} 恰一次保留队列回写: {calls}'


def test_discharge_zero_seat_write_and_independent_entries(
        monkeypatch) -> None:
    """零消耗腿 + 独立弹除(T-34 设计 §4 锁 5 + 锁 9 弹除半边):开盒
    前后 bench/overflow/equips 逐位不变(战利品区件锁——无席位槽可消耗,
    开出的奖励若落席由现役观察自然捕捉);重复获得两条条目按各自解锁位
    独立命中,未到点条目保留。"""
    gs = _make_gs(node_pos=(1, 3),
                  queue=(('惊喜盒', (1, 3)), ('惊喜盒', (2, 4))))
    bench_before = gs.bench.value
    calls = _record_writes(gs, monkeypatch)
    effects = discharge_due_item_opens(gs, rand=False, sig=_SIG)
    assert effects == ('item_opened:惊喜盒',), '仅到点条目命中'
    assert gs.pending_item_opens.value == (('惊喜盒', (2, 4)),), \
        '未到点条目保留(独立弹除)'
    assert gs.bench.value == bench_before, 'bench 逐位不变(零消耗腿)'
    assert gs.overflow_warning.value is None, 'overflow_warning 零写'
    assert gs.overflow_card.value is None, 'overflow_card 零写'
    assert gs.equips.value == [], 'equips 逐位不变'
    assert calls == ['pending_item_opens'], f'唯一写域 = 队列: {calls}'
