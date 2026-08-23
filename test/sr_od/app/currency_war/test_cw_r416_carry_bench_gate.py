# -*- coding: utf-8 -*-
"""r416(ADR-0280,批⑯ F3/F4 裁决):carry 腾位门锁测试。

根因(批⑯ F3):miss 18.7% 的 93% 撞容量墙——_protect_set(双桥池
全名单+锁线名单)把 bench 变成只进不出的仓库(137/148 事件 bench=9
且零可卖件);「金够必买」已证零效应(批⑱ F4 统计零)→ 正解 =
**降保护集卖最弱件再买**。收益域 r8 以前(r8-r9 miss 无差异)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_sim_checks import (
    _BATCH_CHECKS,
    check_carry_gate_bench_deadlock,
    check_protect_set_bench_share,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(round_num: int = 7) -> tuple[LineStrategy, GameState, StrategySession]:
    """死锁形态:锁 feiying_线(carry=绯英)+ bench 9 全保护件。

    bench:爻光×2/藿藿×2(线件+桥 fixed)、银狼LV.999×3(完整
    3合1 份,保护不动)、丹恒·饮月×2(桥 core 非 feiying 线件
    =保护集内 off-line 价值最低 → 腾位首选)。店有 carry 绯英,
    金 30(boss 窗地板 10,30-2≥10 金足)。"""
    s = LineStrategy()
    st = GameState(gold=30, round_num=round_num, plane=1, level=5,
                   hp=100, level_up_cost=60)   # 高单击价排除 LevelUp
    st.board = {'欢愉': 2}
    st.deployed = [BenchChar(slot=0, char_id='飞霄', faction='仙舟')]
    prot = ['爻光', '藿藿', '银狼LV.999', '银狼LV.999', '银狼LV.999',
            '爻光', '藿藿', '丹恒·饮月', '丹恒·饮月']
    st.bench = [BenchChar(slot=i, char_id=n,
                          faction='仙舟' if '饮月' in n else '欢愉')
                for i, n in enumerate(prot)]
    st.shop = [ShopCard(x=100, faction='欢愉', name='绯英', cost=2)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'feiying_joy'
    return s, st, sess


def test_gate_sells_weakest_then_buys_carry() -> None:
    """① bench 满+carry 在店+金足+零可卖 → 腾位买成(卖最弱件)。"""
    s, st, sess = _mk()
    acts = s.decide_prep(st, sess, None)
    gate_buys = [a for a in acts if isinstance(a, BuyCard)
                 and a.reason == 'carry_gate']
    assert gate_buys and gate_buys[0].card.name == '绯英', \
        f'应腾位买 carry: {[(type(a).__name__, getattr(a, "reason", "")) for a in acts]}'
    sells = [a for a in acts if isinstance(a, SellBench)]
    assert sells, '腾位买必须有前置卖出(卖→买序)'
    sold = st.bench[sells[0].bench_idx].char_id
    # 最弱=保护集内非线件(丹恒·饮月:桥 core 但不在 feiying 线)
    assert sold == '丹恒·饮月', \
        f'最弱件应是非线桥件,实卖 {sold}'
    # 卖出件入同轮已卖集(r408 对称臂)
    assert '丹恒·饮月' in sess.v2_round_sold


def test_gate_skips_when_offtarget_sellable() -> None:
    """② bench 有可卖件(off-target)→ 直接卖买,不走保护集降级。"""
    s, st, sess = _mk()
    st.bench[8] = BenchChar(slot=8, char_id='停云', faction='仙舟')
    acts = s.decide_prep(st, sess, None)
    assert not [a for a in acts if isinstance(a, BuyCard)
                and a.reason == 'carry_gate'], \
        f'有 off-target 可卖不得降保护集: {acts}'
    sells = [a for a in acts if isinstance(a, SellBench)]
    assert sells and st.bench[sells[0].bench_idx].char_id == '停云', \
        f'直接卖通道应卖 off-target 件: {sells}'
    buys = [a for a in acts if isinstance(a, BuyCard)
            and a.card.name == '绯英']
    assert buys and buys[0].reason == 'line', \
        f'腾位后走常规买通道(reason=line): {acts}'


def test_gate_keeps_31_merge_set() -> None:
    """③ 3合1 副本不被腾:完整合成份(星级加权 copies==3)排除。"""
    s, st, sess = _mk()
    acts = s.decide_prep(st, sess, None)
    sells = [a for a in acts if isinstance(a, SellBench)]
    assert sells, '死锁形态应腾位'
    sold_names = [st.bench[a.bench_idx].char_id for a in sells]
    assert all(n != '银狼LV.999' for n in sold_names), \
        f'3合1 完整份(×3)不得被腾: {sold_names}'


def test_gate_not_past_r7() -> None:
    """④ r8+ 不触发(收益域 r≤7;r9 boss 轮同族禁令一并覆盖)。"""
    for rn in (8, 9):
        s, st, sess = _mk(round_num=rn)
        acts = s.decide_prep(st, sess, None)
        assert not [a for a in acts if isinstance(a, BuyCard)
                    and a.reason == 'carry_gate'], \
            f'r{rn} 不得触发腾位门: {acts}'


def test_gate_sold_not_rebought_same_round() -> None:
    """⑤ 卖出件同轮不回买(r408 对称臂,挂同一集合)。"""
    s, st, sess = _mk()
    acts = s.decide_prep(st, sess, None)
    sells = [a for a in acts if isinstance(a, SellBench)]
    assert sells, '前置:腾位应发生'
    # 模拟执行(卖+买落地),同轮再决策
    idx = sells[0].bench_idx
    sold = st.bench.pop(idx).char_id
    st.gold += 3
    st.gold -= 2
    st.shop = []
    st.bench.append(BenchChar(slot=9, char_id='绯英', faction='欢愉'))
    acts2 = s.decide_prep(st, sess, None)
    assert sold in sess.v2_round_sold
    # 同轮已卖名不回买(哪怕店再刷出来)
    st.shop = [ShopCard(x=100, faction='仙舟', name=sold, cost=1)]
    acts3 = s.decide_prep(st, sess, None)
    rebuy = [a for a in acts2 + acts3 if isinstance(a, BuyCard)
             and a.card.name == sold]
    assert not rebuy, f'同轮刚卖件不得回买: {rebuy}'


# ---- 检查项双向锁(批⑯设计表;变异自检纪律) ------------------------


def _deadlock_row(rn: int = 7) -> dict:
    return {
        'plane': 1, 'round_num': rn, 'gold': 30,
        'target_comp': 'feiying_joy',
        'state': {'bench': [{'char_id': '爻光', 'faction': '欢愉'}] * 9,
                  'deployed': [], 'cap': 5},
        'actions': [],   # 零买零卖 = 死锁指纹
        'sim': {'shop_waves': [
            {'event': 'offer', 'gold': 30,
             'cards': [{'name': '绯英', 'faction': '欢愉', 'cost': 2}]}]},
    }


def test_check_carry_gate_bench_deadlock() -> None:
    """死锁形态报;腾位动作在/收益域外/未锁线 不报。"""
    assert check_carry_gate_bench_deadlock([_deadlock_row()]), \
        '死锁指纹应报(基线 18.7% 形态)'
    # 修复后:腾位门产出卖+买 → 非零买零卖 → 不报
    fixed = _deadlock_row()
    fixed['actions'] = [
        {'__type__': 'SellBench', 'bench_idx': 8, 'name': '丹恒·饮月'},
        {'__type__': 'BuyCard', 'reason': 'carry_gate',
         'card': {'name': '绯英', 'cost': 2, 'faction': '欢愉'}}]
    assert not check_carry_gate_bench_deadlock([fixed]), \
        '附腾位动作的行不是死锁(修复后归 0 路径)'
    # r8+ 收益域外不辖
    assert not check_carry_gate_bench_deadlock([_deadlock_row(rn=8)])
    # 未锁线(桥期)不辖
    unlocked = _deadlock_row()
    unlocked['target_comp'] = 'xianzhou_dot'
    assert not check_carry_gate_bench_deadlock([unlocked])
    # 登记进批量检查(防接线漂移)
    assert 'carry_gate_bench_deadlock' in _BATCH_CHECKS


def test_check_protect_set_bench_share() -> None:
    """披露级:锁线 r6+ 保护件 ≥7/9 计数;violations 恒 0。"""
    row = _deadlock_row(rn=6)
    row['state']['bench'] = [
        {'char_id': n, 'faction': '欢愉'} for n in
        ['爻光', '藿藿', '银狼LV.999', '银狼LV.999', '银狼LV.999',
         '爻光', '藿藿', '丹恒·饮月', '丹恒·饮月']]
    rep = check_protect_set_bench_share([[row]])
    assert rep['violations'] == 0, '披露级检查不构成违规'
    assert rep['rows'] == 1 and rep['ge_7_of_9_rows'] == 1, rep
    assert rep['avg_share'] == 1.0, rep
    # r6 以前/未锁线行不计
    early = _deadlock_row(rn=4)
    early['state']['bench'] = row['state']['bench']
    rep2 = check_protect_set_bench_share([[early]])
    assert rep2['rows'] == 0, rep2
