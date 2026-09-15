"""T-226 备战席溢出门锁面(2026-09-15,R11 用户定案)。

语义正本 = flow/action-logic-state.md §2.4 溢出条件行 + game_state/fields.md
§3.2.21;实机建档 = docs/game/screens/currency_war_prep.md 告警/溢出节。

锁的三件事:
1. 告警在场 → 决策强收窄为单动作 SellBench(禁发 StartBattle/开店,
   先卖腾位再出战——出战点击此刻被游戏忽略,launch_dead 三连实证);
2. 告警消失 → 门释放(无强收窄卖出,常规决策接管);
3. 溢出态 SellBench 逻辑态 = 摘卖件 + 溢出卡入自由槽 + 旗标/身份消亡;
   身份缺读('')= 跳过入位(槽留空等观察),卖出本体不受阻。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    Unit,
    apply_prep_action_logic,
    bench_slots_of,
    bench_view_of_slots,
    board_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    SellBench,
    StartBattle,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
    MandateFrame,
    run_mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')


def _frame(**kw) -> MandateFrame:
    """最小骨架帧:round>1 免 M5;gold 充裕免凑息/买面;上阵 1 人免
    empty_board_sell_guard(场上无人禁卖守卫);单 1★ 备战件(椒丘 = 新
    会话默认身份排除集外的中性位,可入燃料候选)。"""
    base = {'gold': 200, 'level': 7,
            'bench': [BenchChar(slot=1, char_id='椒丘', star=1)],
            'deployed': [BenchChar(slot=1, char_id='刃', star=1,
                                   position_pref='front')],
            'deploy_cap': 7, 'node_type': 'battle',
            'stop_flag': False, 'k_members': ('刃',), 'round_num': 5}
    base.update(kw)
    return MandateFrame(**base)


def _state():
    """容器种子 + 上阵 1 人(免 empty_board_sell_guard:场上无人禁卖守卫,
    守卫读容器上阵域非 frame)。bench 槽表照实观察(生产 heavy 帧恒产出;
    批2b 换算收口后溢出发射位按容器槽位表解析下标,黑板视图与容器同帧
    同源是解析前提)。"""
    bs = board_state_of(None)
    bs.write_logic(bs.bench, bench_view_of_slots(
        [BenchChar(slot=1, char_id='椒丘', star=1)]),
        produced_by='test', sig=_SIG)
    bs.write_logic(bs.front_row, [Unit(slot=1, char_id='刃', star=1)],
                   produced_by='test', sig=_SIG)
    return bs


def test_overflow_gate_narrows_to_single_sell():
    """告警在场:决策强收窄 = 恰一个 SellBench,零 StartBattle(先卖再战)。"""
    session = StrategySession()
    out = run_mandate(_frame(overflow_warning=True), session,
                      state=_state())
    assert len(out) == 1
    assert isinstance(out[0].action, SellBench)
    assert out[0].action.bench_idx == 0   # 唯一冗余位 = 椒丘槽(槽1 → 容器下标0)
    assert not any(isinstance(e.action, StartBattle) for e in out)
    assert state_of(session).cw4_counters.get('overflow_clear_sell') == 1


def test_overflow_gate_releases_when_cleared():
    """告警消失:门释放——无强收窄卖出、门计数零触达,常规决策接管。"""
    session = StrategySession()
    out = run_mandate(_frame(overflow_warning=False), session,
                      state=_state())
    counters = state_of(session).cw4_counters
    assert not counters.get('overflow_clear_sell')
    assert not counters.get('overflow_no_fuel')
    assert not any(isinstance(e.action, SellBench) for e in out)


def test_sellbench_overflow_logic_state_absorbs_card():
    """溢出态 SellBench 逻辑态:摘卖件 + 溢出卡入自由槽 + 旗标/身份消亡。"""
    bs = board_state_of(None)
    bs.write_logic(bs.bench, bench_view_of_slots(
        [BenchChar(slot=1, char_id='花火', star=1),
         BenchChar(slot=2, char_id='刃', star=1)]),
        produced_by='test', sig=_SIG)
    bs.write_logic(bs.gold, 10, produced_by='test', sig=_SIG)
    bs.write_logic(bs.overflow_warning, True, produced_by='test', sig=_SIG)
    bs.write_logic(bs.overflow_card, '不死途', produced_by='test', sig=_SIG)

    apply_prep_action_logic(bs, SellBench(bench_idx=0), produced_by='test',
                            sig=_SIG)

    slots = bench_slots_of(bs)
    assert slots[0] is not None and slots[0].char_id == '不死途'
    assert slots[1].char_id == '刃'
    # 退款 = sell_refund(1★, 2费) = cost 全额 = 2(10 → 12)
    assert bs.gold.value == 12
    assert bs.overflow_card.value == ''
    assert bs.overflow_warning.value is False


def test_sellbench_overflow_missing_identity_skips_absorb():
    """身份缺读(''):容器跳过入位(槽留空等观察覆盖),卖出/退款本体照常;
    tracked 主账对称零写(容器/tracked 两侧一测,原 sync 文件腿并入)。"""
    session = StrategySession()
    bs = board_state_of(session)
    bs.write_logic(bs.bench, bench_view_of_slots(
        [BenchChar(slot=1, char_id='花火', star=1),
         BenchChar(slot=2, char_id='刃', star=1)]),
        produced_by='test', sig=_SIG)
    bs.write_logic(bs.gold, 10, produced_by='test', sig=_SIG)
    bs.write_logic(bs.overflow_warning, True, produced_by='test', sig=_SIG)
    bs.write_logic(bs.overflow_card, '', produced_by='test', sig=_SIG)
    from sr_od.application.currency_war.kernel.cw_exec_state import (
        bench_from_compact,
        exec_state_of,
    )
    exec_state_of(session).tracked_bench_chars = bench_from_compact([
        BenchChar(slot=1, char_id='花火', star=1),
        BenchChar(slot=2, char_id='刃', star=1)])

    apply_prep_action_logic(bs, SellBench(bench_idx=0), produced_by='test',
                            sig=_SIG, session=session)

    slots = bench_slots_of(bs)
    assert slots[0] is None
    assert bs.gold.value == 12
    assert bs.overflow_warning.value is True    # 未消费(未入位),留观察覆盖
    assert bs.overflow_card.value == ''
    # tracked 对称零写(身份缺读不吸收,两侧同测)
    after = exec_state_of(session).tracked_bench_chars
    assert [(b.char_id, b.star) for b in after if b is not None] == [
        ('花火', 1), ('刃', 1)]
