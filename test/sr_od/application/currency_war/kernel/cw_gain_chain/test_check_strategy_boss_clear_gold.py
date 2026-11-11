"""搜打撤 boss 通关价值金币效果条目 kernel 面测试(镜像 src = cw_gain_chain.py
board_bench_char_value_sum / check_strategy_boss_clear_gold;直构形态
先例 = 同目录 test_check_strategy_boss_completion_grants.py 的状态容器直置,
禁经战斗链假绿)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 2/锁 5:
- 锁 2(价值口径对拍):economy.md §9 详情面板三点实测定案(2026-09-15,
  2 费线:1★花火 +2 / 2★不死途 +5 / 3★不死途 +17,禁从他稿平移数值)+
  1★1费豁免无手续费 +1——与 sell_refund 单一源对拍,「费用合计 Σcost」
  读法(读法 B)在 2★/3★ 与实测分叉即红;
- 锁 5(求和域):场上前/后排 + bench unit 槽计入;bench 占位件
  (tome/bookcard/supply_box)不计(「角色」域文义);空场空席 =
  「所有角色价值」为 0 的结构可达态——0 金笔照发且 0 值仍消费一次性标志位
  (一次性标志位与金笔同窗 = 卡面「下一个」恰一次的载体,0 值短路不落一次性标志位会让后继
  boss 重触发)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_economy import sell_refund
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    board_bench_char_value_sum,
    check_strategy_boss_clear_gold,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')
_SIM_SIG = ChannelSig(family='obs', actor='SimEngineV2', mode='synthesized',
                      group_id='sim:strategy')

_CARD = '搜打撤'
_EVIDENCE = 'sim:engine:strategy:boss_clear_value'


def _unit(char_id: str, star: int = 1) -> Unit:
    return Unit(char_id=char_id, star=star, equips=[])


def _gs(*, card: str | None = _CARD,
        deployed: DeployedView | None = None,
        bench: list[BenchSlot] | None = None,
        gold: int = 50) -> GameState:
    """直构 gs(gold/equips 观察定金笔承载;card=None = 未持卡;
    bench 列表 pad 成 9 槽 BenchView,先例 =
    test_check_strategy_bench_leave_gold._gs 同形)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, gold, sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    if deployed is not None:
        gs.observe(gs.deployed, deployed, sig=_SIG_OBS)
    if bench is not None:
        slots = list(bench) + [BenchSlot(kind='empty')] * (9 - len(bench))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9),
                   sig=_SIG_OBS)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    return gs


def test_value_sum_matches_sell_refund_measured_points() -> None:
    """锁 2(价值口径对拍):economy.md §9 三点实测逐点直测 + 与
    sell_refund 单一源对拍;读法 B(费用合计)在 2★/3★ 与实测分叉。"""
    assert CHARACTERS['花火'].cost == 2, '前置:花火应为 2 费'
    assert CHARACTERS['不死途'].cost == 2, '前置:不死途应为 2 费'
    for char_id, star, expected in (('花火', 1, 2),
                                    ('不死途', 2, 5),
                                    ('不死途', 3, 17)):
        gs = _gs(deployed=DeployedView(
            front_slots=[_unit(char_id, star), None, None, None],
            back_slots=[]))
        got = board_bench_char_value_sum(gs)
        assert got == expected, \
            f'{star}★{char_id}求和漂移: got={got} 实测定案={expected}'
        assert got == sell_refund(star, CHARACTERS[char_id].cost), \
            '求和应与 sell_refund 单一源对拍等值(禁第二份公式)'


def test_value_sum_one_star_one_cost_full_refund() -> None:
    """锁 2 补面(1★1费豁免):无合成无手续费全额退 = 1(sell_refund
    cost=1 exempt 分支,2026-08-13 live 实测口径)。"""
    assert CHARACTERS['青雀'].cost == 1, '前置:青雀应为 1 费'
    gs = _gs(deployed=DeployedView(
        front_slots=[_unit('青雀', 1), None, None, None], back_slots=[]))
    assert board_bench_char_value_sum(gs) == 1 == sell_refund(1, 1), \
        '1★1费应全额退 1(无手续费)'


def test_value_sum_domain_front_back_bench_excludes_placeholders() -> None:
    """锁 5(求和域):前/后排 + bench unit 槽计入;bench 占位件
    (tome/bookcard/supply_box)不计;空场空席 = 0(结构可达态)。"""
    # 三域各 1★2费(2 金)= 6;占位件三形零贡献。
    gs = _gs(
        deployed=DeployedView(
            front_slots=[_unit('花火', 1), None, None, None],
            back_slots=[_unit('花火', 1), None, None, None, None, None]),
        bench=[BenchSlot(kind='unit',
                         unit=Unit(char_id='花火', star=1, equips=[])),
               BenchSlot(kind='tome', item='星徽典籍'),
               BenchSlot(kind='bookcard', item='专家邀请函'),
               BenchSlot(kind='supply_box', item='简易武装箱')])
    assert board_bench_char_value_sum(gs) == 6, \
        f'求和域漂移(前/后排+bench unit 计入,占位件不计): ' \
        f'{board_bench_char_value_sum(gs)}'
    # 空场空席 = 0(状态容器未观察按空行/空席零计,纯读派生口径)。
    assert board_bench_char_value_sum(_gs()) == 0, '空场空席应 0'


def test_zero_value_grant_still_latches() -> None:
    """锁 5 附注(0 值仍消费一次性标志位):空场空席局调触发函数 → 金笔 +0
    (gold 值不变、evidence 笔落)+ 落一次性标志位(「下一个」恰一次的载体,
    防后继 boss 重触发);直构窗无 node → evidence 退化无时点段。"""
    gs = _gs()
    before = gs.write_seq
    check_strategy_boss_clear_gold(gs, _SIM_SIG)
    assert gs.gold.value == 50, '空场空席金笔 +0(值不变)'
    assert gs.gold.evidence == _EVIDENCE, \
        f'evidence 退化形漂移: {gs.gold.evidence!r}'
    assert gs.gold.source == 'observation', '金笔 = 观察通道(状态副本数值面)'
    assert gs.strategy_conditional_done.value == (_CARD,), '0 值未落一次性标志位'
    assert gs.strategy_conditional_done.source == 'logic', '一次性标志位 = 逻辑态'
    assert gs.write_seq == before + 2, '同窗两笔(金 observe + 一次性标志位 logic)'
