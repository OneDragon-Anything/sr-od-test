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

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_sell_bench_param,
)
from sr_od.application.currency_war.kernel.cw_exec_state import (
    BenchChar,
    bench_from_compact,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    ChannelSig,
    Unit,
    bench_slots_of,
    bench_view_of_slots,
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
    gs = game_state_of(None)
    gs.write_logic(gs.bench, bench_view_of_slots(
        [BenchChar(slot=1, char_id='椒丘', star=1)]),
        produced_by='test', sig=_SIG)
    gs.write_logic(gs.front_row, [Unit(slot=1, char_id='刃', star=1)],
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
    gs.write_logic(gs.bench, bench_view_of_slots(
        [BenchChar(slot=1, char_id='花火', star=1),
         BenchChar(slot=2, char_id='刃', star=1)]),
        produced_by='test', sig=_SIG)
    gs.write_logic(gs.gold, 10, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_warning, True, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_card, '不死途', produced_by='test', sig=_SIG)

    report_action_sell_bench_param(gs, CwActionSellBenchParam(bench_idx=0),
                                   sig=_SIG)

    slots = bench_slots_of(gs)
    assert slots[0] is not None and slots[0].char_id == '不死途'
    assert slots[1].char_id == '刃'
    # 退款 = sell_refund(1★, 2费) = cost 全额 = 2(10 → 12)
    assert gs.gold.value == 12
    assert gs.overflow_card.value == ''
    assert gs.overflow_warning.value is False


def test_sellbench_overflow_missing_identity_skips_absorb():
    """身份缺读(''):容器跳过入位(槽留空等观察覆盖),卖出/退款本体照常;
    tracked 主账对称零写(容器/tracked 两侧一测,原 sync 文件腿并入)。"""
    session = StrategySession()
    gs = game_state_of(session)
    gs.write_logic(gs.bench, bench_view_of_slots(
        [BenchChar(slot=1, char_id='花火', star=1),
         BenchChar(slot=2, char_id='刃', star=1)]),
        produced_by='test', sig=_SIG)
    gs.write_logic(gs.gold, 10, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_warning, True, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_card, '', produced_by='test', sig=_SIG)
    gs.tracked_books.bench = bench_from_compact([
        BenchChar(slot=1, char_id='花火', star=1),
        BenchChar(slot=2, char_id='刃', star=1)])

    report_action_sell_bench_param(gs, CwActionSellBenchParam(bench_idx=0),
                                   sig=_SIG, session=session)

    slots = bench_slots_of(gs)
    assert slots[0] is None
    assert gs.gold.value == 12
    assert gs.overflow_warning.value is True    # 未消费(未入位),留观察覆盖
    assert gs.overflow_card.value == ''
    # tracked 对称零写(身份缺读不吸收,两侧同测;P1 tracked 形状 = 内嵌
    # Unit 身份)
    after = game_state_of(session).tracked_books.bench
    assert [(b.unit.char_id, b.unit.star) for b in after if b is not None] == [
        ('花火', 1), ('刃', 1)]


# ===== 溢出腿执行账(tracked)吸收(原 test_cw_overflow_tracked_sync.py)===


def _seed(session, tracked, *, ov_id: str = '不死途'):
    """容器 bench=[花火@1, 刃@2] + 溢出态写入 + tracked 初始账。"""
    gs = game_state_of(session)
    gs.write_logic(gs.bench, bench_view_of_slots(
        [BenchChar(slot=1, char_id='花火', star=1),
         BenchChar(slot=2, char_id='刃', star=1)]),
        produced_by='test', sig=_SIG)
    gs.write_logic(gs.gold, 10, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_warning, True, produced_by='test', sig=_SIG)
    gs.write_logic(gs.overflow_card, ov_id, produced_by='test', sig=_SIG)
    game_state_of(session).tracked_books.bench = tracked
    return gs


def test_overflow_absorb_syncs_tracked():
    """溢出腿落地 → 同一落地时刻容器 + tracked 两账一测:tracked 吸收
    入位卡,槽位/身份与容器腿同源(2026-09-11 实机 2-4 停机事故本形:
    溢出腿把入位卡写进容器 bench 而执行侧 tracked 主账未吸收 → 商店
    visit 入口两账结构性分叉粘性不可自愈——店开 0n 分发路径
    (visit_open_shop→run_buy_waves)不经过 director heavy 观察,
    reconcile_tracking 唯一生产写点;read_game_state 漏斗 prep_shop_open
    阶段设计上不读 bench 身份——→ 崩溃循环停机。原「种子守卫
    AssertionError」表述随批退役改写:分叉检出现归观察边界 reconcile
    纠漂,本锁锁的吸收行为本体不变。)"""
    session = StrategySession()
    gs = _seed(session, bench_from_compact([
        BenchChar(slot=1, char_id='花火', star=1),
        BenchChar(slot=2, char_id='刃', star=1)]))

    report_action_sell_bench_param(gs, CwActionSellBenchParam(bench_idx=0),
                                   sig=_SIG, session=session)

    tracked = game_state_of(session).tracked_books.bench
    assert [(b.unit.char_id, b.unit.star) for b in tracked if b is not None] == [
        ('不死途', 1), ('刃', 1)]
    assert tracked[0] is not None and tracked[0].unit.slot == 1   # 被卖槽回占
    # 吸收锁(事故本形):容器腿与 tracked 腿同槽同身份。
    assert [(b.char_id, b.star) for b in
            bench_slots_of(gs) if b is not None] == [
        ('不死途', 1), ('刃', 1)]


def test_overflow_absorb_after_executor_removal_compact_shape():
    """生产时序:执行器摘除腿先行(tracked 缺卖件、保洞缺页)→ 吸收按
    下标直写,存件不丢、不串槽。
    (分诊随迁:原「session 缺席零写」兼容腿删——生产 CwActionSellBenchParam 调用点
    唯一且恒传 session,无消费者形态不留测试;「身份缺读对称跳过」腿
    并入上方缺读锁,两侧一测。载体 = P1 tracked 新形状:
    摘除腿后 tracked[0] = None 洞、刃在下标 1。)"""
    session = StrategySession()
    gs = _seed(session, [None, BenchSlot(kind='unit', unit=Unit(
        char_id='刃', star=1, slot=2))])   # 花火已被摘

    report_action_sell_bench_param(gs, CwActionSellBenchParam(bench_idx=0),
                                   sig=_SIG, session=session)

    tracked = game_state_of(session).tracked_books.bench
    assert [(b.unit.char_id, b.unit.star) for b in tracked if b is not None] == [
        ('不死途', 1), ('刃', 1)]
    assert tracked[1] is not None \
        and tracked[1].unit.char_id == '刃'   # 刃 仍在槽 2
