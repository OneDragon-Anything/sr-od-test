"""备战席溢出门锁面(2026-09-15,R11 用户定案)。

语义正本 = flow/action-logic-state.md §2.4 溢出条件行 + game_state/fields.md
§3.2.21;实机建档 = docs/game/screens/currency_war_prep.md 告警/溢出节。

锁的三件事:
1. 告警在场 → 决策强收窄为单动作 CwActionSellBenchParam(禁发 CwActionStartBattleParam/开店,
   先卖腾位再出战——出战点击此刻被游戏忽略,launch_dead 三连实证);
2. 告警消失 → 门释放(无强收窄卖出,常规决策接管);
3. 溢出态 CwActionSellBenchParam 逻辑态 = 摘卖件 + 溢出卡入自由槽 + 旗标/身份消亡;
   身份缺读('')= 跳过入位(槽留空等观察),卖出本体不受阻;
4. 溢出腿执行账吸收(原 test_cw_overflow_tracked_sync.py 全文件迁并,
   该文件已删):落地时刻容器 + tracked 两账一测 + 执行器摘除腿先行的
   紧缩重建腿。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)

from test.sr_od.application.currency_war._cw_helpers import cw4_bview

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_sell_bench_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    ChannelSig,
    Unit,
    bench_entries_of,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionSellBenchParam,
    CwActionStartBattleParam,
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
    会话默认身份排除集外的中性位,可入燃料候选)。
    P4 容器形:bench = 占席条目,deployed = 行域 Unit。"""
    base = {'gold': 200, 'level': 7,
            'bench': [BenchSlot(kind='unit',
                                unit=Unit(char_id='椒丘', star=1))],
            'deployed': [Unit( char_id='刃', star=1)],
            'deploy_cap': 7, 'node_type': 'battle',
            'stop_flag': False, 'k_members': ('刃',), 'round_num': 5}
    base.update(kw)
    return MandateFrame(**base)


def _state():
    """容器种子 + 上阵 1 人(免 empty_board_sell_guard:场上无人禁卖守卫,
    守卫读容器上阵域非 frame)。bench 槽表照实观察(生产 heavy 帧恒产出;
    批2b 换算收口后溢出发射位按容器槽位表解析下标,黑板视图与容器同帧
    同源是解析前提)。"""
    gs = game_state_of(None)
    gs.write_logic(gs.bench, cw4_bview(
        [BenchSlot(kind='unit', unit=Unit(char_id='椒丘', star=1))]),
        produced_by='test', sig=_SIG)
    gs.write_logic(gs.deployed, _dvs([Unit( char_id='刃', star=1)], []),
                   produced_by='test', sig=_SIG)
    return gs


def test_overflow_gate_narrows_to_single_sell():
    """告警在场:决策强收窄 = 恰一个 CwActionSellBenchParam,零 CwActionStartBattleParam(先卖再战)。"""
    session = StrategySession()
    out = run_mandate(_frame(overflow_warning=True), session,
                      state=_state())
    assert len(out) == 1
    assert isinstance(out[0].action, CwActionSellBenchParam)
    assert out[0].action.bench_idx == 0   # 唯一冗余位 = 椒丘槽(槽1 → 容器下标0)
    assert not any(isinstance(e.action, CwActionStartBattleParam) for e in out)
    assert state_of(session).cw4_counters.get('overflow_clear_sell') == 1


def test_overflow_gate_releases_when_cleared():
    """告警消失:门释放——无强收窄卖出、门计数零触达,常规决策接管。"""
    session = StrategySession()
    out = run_mandate(_frame(overflow_warning=False), session,
                      state=_state())
    counters = state_of(session).cw4_counters
    assert not counters.get('overflow_clear_sell')
    assert not counters.get('overflow_no_fuel')
    assert not any(isinstance(e.action, CwActionSellBenchParam) for e in out)


def test_sellbench_overflow_logic_state_absorbs_card():
    """溢出态 CwActionSellBenchParam 逻辑态:摘卖件 + 溢出卡入自由槽 + 旗标/身份消亡。"""
    gs = game_state_of(None)
    gs.write_logic(gs.bench, cw4_bview(
        [BenchSlot(kind='unit', unit=Unit(char_id='花火', star=1)),
         BenchSlot(kind='unit', unit=Unit(char_id='刃', star=1))]),
        produced_by='test', sig=_SIG)
    gs.write_logic(gs.gold, 10, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_warning, True, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_card, '不死途', produced_by='test', sig=_SIG)

    report_action_sell_bench_param(gs, CwActionSellBenchParam(bench_idx=0),
                                   sig=_SIG)

    slots = bench_entries_of(gs)
    assert slots[0] is not None and slots[0].unit.char_id == '不死途'
    assert slots[1].unit.char_id == '刃'
    # 退款 = sell_refund(1★, 2费) = cost 全额 = 2(10 → 12)
    assert gs.gold.value == 12
    assert gs.overflow_card.value == ''
    assert gs.overflow_warning.value is False


def test_sellbench_overflow_absorbs_item_as_supply_box():
    """溢出件 = 占席道具(BENCH_ITEM_NAMES 命中):卖牌腾槽入位落
    supply_box 槽件,禁造假角色(道具与角色同款溢出语义,2026-09-24
    用户确认;判据单一源 = cw_investments.BENCH_ITEM_NAMES)。"""
    gs = game_state_of(None)
    gs.write_logic(gs.bench, cw4_bview(
        [BenchSlot(kind='unit', unit=Unit(char_id='花火', star=1)),
         BenchSlot(kind='unit', unit=Unit(char_id='刃', star=1))]),
        produced_by='test', sig=_SIG)
    gs.write_logic(gs.gold, 10, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_warning, True, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_card, '简易武装箱', produced_by='test',
                   sig=_SIG)

    report_action_sell_bench_param(gs, CwActionSellBenchParam(bench_idx=0),
                                   sig=_SIG)

    slots = bench_entries_of(gs)
    assert slots[0] is not None and slots[0].kind == 'supply_box', \
        '道具入位 = supply_box 槽件'
    assert slots[0].unit is None, '无假角色身份'
    assert slots[1].unit.char_id == '刃'
    assert gs.overflow_card.value == ''
    assert gs.overflow_warning.value is False


def test_sellbench_lv999_tiered_refund():
    """银狼LV.999 档感知卖价(口述·权威 2026-09-21:升费后按新费用档
    标准公式计价,无特殊口径):档 = 4 的 1★ LV.999 卖出退款 = 4
    (注册表起始费 3 会被错卖成 3)。"""
    gs = game_state_of(None)
    gs.write_logic(gs.bench, cw4_bview(
        [BenchSlot(kind='unit', unit=Unit(char_id='银狼LV.999', star=1))]),
        produced_by='test', sig=_SIG)
    gs.write_logic(gs.gold, 10, produced_by='test', sig=_SIG)
    gs.write_logic(gs.lv999_cost_tier, 4, produced_by='test', sig=_SIG)

    report_action_sell_bench_param(gs, CwActionSellBenchParam(bench_idx=0),
                                   sig=_SIG)

    assert gs.gold.value == 14, '退款 = sell_refund(1★, 当前档 4) = 4'


def test_sellbench_overflow_missing_identity_skips_absorb():
    """身份缺读(''):容器跳过入位(槽留空等观察覆盖),卖出/退款本体照常;
    溢出态未消费留观察覆盖(单账断言;原 tracked 对称腿随 3.2 退役删)。"""
    session = StrategySession()
    gs = game_state_of(session)
    gs.write_logic(gs.bench, cw4_bview(
        [BenchSlot(kind='unit', unit=Unit(char_id='花火', star=1)),
         BenchSlot(kind='unit', unit=Unit(char_id='刃', star=1))]),
        produced_by='test', sig=_SIG)
    gs.write_logic(gs.gold, 10, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_warning, True, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_card, '', produced_by='test', sig=_SIG)

    report_action_sell_bench_param(gs, CwActionSellBenchParam(bench_idx=0),
                                   sig=_SIG)

    slots = bench_entries_of(gs)
    assert '花火' not in [s.unit.char_id for s in slots]   # 摘卖件槽留空等观察
    assert gs.gold.value == 12
    assert gs.overflow_warning.value is True    # 未消费(未入位),留观察覆盖
    assert gs.overflow_card.value == ''


# ===== 溢出腿吸收(原 test_cw_overflow_tracked_sync.py;3.2 单账化)=====


def test_overflow_absorb_lands_at_sold_slot():
    """溢出腿落地 → 入位卡按被卖槽下标落容器 bench(2026-09-11 实机
    2-4 停机事故本形:溢出腿入位卡未达执行主账 → 商店 visit 入口两账
    结构性分叉粘性不可自愈。overlay-trigger 3.2 单账化后分叉结构性
    不可能:容器 bench 即唯一账,吸收锁 = 入位卡落槽 + 存件不串。"""
    session = StrategySession()
    gs = game_state_of(session)
    gs.write_logic(gs.bench, cw4_bview(
        [BenchSlot(kind='unit', unit=Unit(char_id='花火', star=1)),
         BenchSlot(kind='unit', unit=Unit(char_id='刃', star=1))]),
        produced_by='test', sig=_SIG)
    gs.write_logic(gs.gold, 10, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_warning, True, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_card, '不死途', produced_by='test', sig=_SIG)

    report_action_sell_bench_param(gs, CwActionSellBenchParam(bench_idx=0),
                                   sig=_SIG)

    assert [(b.unit.char_id, b.unit.star) for b in
            bench_entries_of(gs) if b is not None] == [
        ('不死途', 1), ('刃', 1)], '入位卡占被卖槽,存件不丢不串槽'
