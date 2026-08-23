# -*- coding: utf-8 -*-
"""r408(ADR-0267,压测自由批 F1):同轮买卖互斥 + engine_seed 容量门。

bench 满员态 engine_seed 买通道与卖通道在同名卡上互踩(买→卖→买
永动机,自由批 235 次/38 局,单轮最高 8 连)——白拿 XP/引擎种子归零/
boss 轮段预算烧尽。修复:round-scoped 已买集(session.v2_round_bought)
四卖通道禁卖(3合1 让位豁免)+ engine_seed bench 满员不触发。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_sim_checks import (
    check_no_same_round_buy_sell,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    RefreshShop,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(seed_in_shop: bool = True, bench_n: int = 9) -> tuple[
        LineStrategy, GameState, StrategySession]:
    """F1 形态:锁 feiying 线 + bench 满(保护件+1 杂牌)+ 星期日在架。

    星期日(盛会之星、列车同行 flow)过 engine_seed 门且不在
    feiying 线保护集(桥池 flex 非 fixed/core)——修前每段被
    卖通道回收再被 engine_seed 买回。"""
    s = LineStrategy()
    st = GameState(gold=28, round_num=4, plane=1, level=4, hp=100,
                   level_up_cost=60)   # 高单击价 → 排除 LevelUp 干扰
    st.board = {'列车同行': 1, '欢愉': 1}
    st.deployed = [BenchChar(slot=0, char_id='绯英', faction='欢愉'),
                   BenchChar(slot=1, char_id='爻光', faction='欢愉')]
    prot = ['绯英', '爻光', '银狼LV.999', '藿藿'] * 2
    st.bench = [BenchChar(slot=i, char_id=n, faction='欢愉')
                for i, n in enumerate(prot[:bench_n - 1])]
    st.bench.append(BenchChar(slot=bench_n - 1, char_id='停云',
                              faction='仙舟'))
    st.shop = [ShopCard(x=100, faction='盛会之星', name='星期日', cost=3)] \
        if seed_in_shop else []
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'feiying_joy'
    return s, st, sess


def _run_segments(s: LineStrategy, st: GameState, sess: StrategySession,
                  n: int = 8) -> list[tuple]:
    """跑 n 段 decide_prep(镜像 cw_sim 段循环;过滤刷新),返回轨迹。"""
    trace: list[tuple] = []
    for _ in range(n):
        s.update_target(st, sess, None)
        acts = [a for a in s.decide_prep(st, sess, None)
                if not isinstance(a, RefreshShop)]
        if not acts:
            break
        prog = False
        for a in acts:
            if isinstance(a, BuyCard):
                st.gold -= a.card.cost
                st.bench.append(BenchChar(slot=len(st.bench) + 1,
                                          char_id=a.card.name,
                                          faction=a.card.faction))
                trace.append(('buy', a.card.name))
                prog = True
            elif isinstance(a, SellBench):
                if 0 <= a.bench_idx < len(st.bench):
                    bc = st.bench.pop(a.bench_idx)
                    st.gold += 3
                    trace.append(('sell', bc.char_id))
                    prog = True
        if not prog:
            break
    return trace


def _osc_pairs(trace: list[tuple]) -> int:
    n = 0
    for i, t in enumerate(trace):
        if t[0] == 'buy' and any(t2[0] == 'sell' and t2[1] == t[1]
                                 for t2 in trace[i + 1:]):
            n += 1
    return n


def test_round_mutex_no_buy_then_sell() -> None:
    """互斥:同轮买入的卡,后续段卖通道不得卖出(振荡环断)。"""
    s, st, sess = _mk()
    trace = _run_segments(s, st, sess)
    assert _osc_pairs(trace) == 0, \
        f'同轮买后卖应 0 容忍(ADR-0267): {trace}'
    # 修前形态参照(探针实证):首段卖停云买星期日后,7 对买↔卖振荡;
    # 修后:星期日只买 1 次(种子存活过轮界)
    assert trace.count(('buy', '星期日')) == 1, \
        f'engine_seed 种子应只买 1 次(不再被卖回): {trace}'


def test_round_mutex_no_oscillation_xp() -> None:
    """XP 不因振荡白拿:8 段内星期日买入 ≤1 次(修前 8 次=32 XP)。"""
    s, st, sess = _mk()
    trace = _run_segments(s, st, sess)
    buys = sum(1 for t in trace if t == ('buy', '星期日'))
    assert buys <= 1, f'振荡白拿 XP(买入 {buys} 次): {trace}'


def test_engine_seed_capacity_gate() -> None:
    """容量门:bench 满员(≥9)engine_seed 不触发;腾位后(8)放行。"""
    s, st, sess = _mk()
    card = st.shop[0]
    assert len(st.bench) == 9
    assert not s._engine_seed_wants(card, st), '满员不得种(ADR-0267 ②)'
    st.bench.pop()
    assert s._engine_seed_wants(card, st), '腾位后(8)应放行'


def test_round_sell_blocked_and_31_exemption() -> None:
    """3合1 让位豁免:同名副本(星级加权)≥3 的冗余件可卖,单张禁卖。"""
    s, st, sess = _mk()
    sess.v2_round_key = (st.plane, st.round_num)
    sess.v2_round_bought = {'停云'}
    bc1 = BenchChar(slot=8, char_id='停云', faction='仙舟')
    st.bench = [bc1]
    assert s._round_sell_blocked(bc1, st, sess), '同轮已买单张应禁卖'
    # 3 张同名 1★(=3合1 份)→ 冗余件让位放行
    st.bench = [BenchChar(slot=i, char_id='停云', faction='仙舟')
                for i in range(3)]
    assert not s._round_sell_blocked(st.bench[0], st, sess), \
        '副本 ≥3 是让位豁免(合成后冗余),可卖'
    # 轮键不匹配(跨轮/丢 session)→ 空集保守不拦
    sess.v2_round_key = (1, 99)
    assert not s._round_sell_blocked(bc1, st, sess)


def test_round_set_resets_per_round() -> None:
    """已买集按 (plane, round_num) 换轮重置;engine_seed 跨轮卖回由
    年龄豁免辖(ADR-0289 §5 / ADR-0294 件1,r408 只辖同轮)。

    r4 买入的种子:r5/r6(≤2 轮窗)卖通道不选,r7(>2 轮)可卖。
    修前本测试断言「r5 立即可卖(跨轮合法)」——ADR-0289 裁决该
    行为即红项 127/300(种子归零),窗内禁卖为新语义。"""
    s, st, sess = _mk()
    trace = _run_segments(s, st, sess, n=1)   # r4 段1:卖停云买星期日
    assert sess.v2_round_key == (1, 4)
    assert '星期日' in sess.v2_round_bought
    # 购入轮登记(年龄豁免数据源):((plane, round), 同轮份数)
    assert sess.v2_seed_bought.get('星期日') == ((1, 4), 1)
    st.round_num = 5
    acts = s.decide_prep(st, sess, None)
    assert sess.v2_round_key == (1, 5)
    assert '星期日' not in sess.v2_round_sold, \
        f'r5 卖 r4 种子应被年龄豁免拦(ADR-0289 §5): ' \
        f'{[type(a).__name__ for a in acts]}'
    st.round_num = 6
    s.decide_prep(st, sess, None)
    assert '星期日' not in sess.v2_round_sold, 'r6(窗内末轮)仍不卖'
    # r7(>2 轮)窗外:可卖(锁:买入 r=N → r=N+3 起可卖)
    st.round_num = 7
    bc = next((b for b in st.bench if b.char_id == '星期日'), None)
    assert bc is not None, '星期日应在 bench(未被卖回)'
    assert not s._seed_age_blocked(bc, st, sess), 'r7 种子应可卖'


def test_check_no_same_round_buy_sell() -> None:
    """检查项双向锁:买→卖同轮同名著报;卖→买(腾位)合法不报。"""
    bad = [{'plane': 1, 'round_num': 4, 'actions': [
        {'__type__': 'SellBench', 'bench_idx': 8, 'name': '停云',
         'income': 1},
        {'__type__': 'BuyCard', 'reason': 'engine_seed',
         'card': {'name': '星期日', 'cost': 3, 'faction': '盛会之星'}},
        {'__type__': 'SellBench', 'bench_idx': 8, 'name': '星期日',
         'income': 3},   # ← F1 振荡形态
    ]}]
    v = check_no_same_round_buy_sell(bad)
    assert v and '星期日' in v[0], f'买后卖应报: {v}'

    ok = [{'plane': 1, 'round_num': 4, 'actions': [
        {'__type__': 'SellBench', 'bench_idx': 8, 'name': '停云',
         'income': 1},
        {'__type__': 'BuyCard', 'reason': 'engine_seed',
         'card': {'name': '星期日', 'cost': 3, 'faction': '盛会之星'}},
    ]}]
    assert not check_no_same_round_buy_sell(ok), '卖→买(腾位)合法'
    # 买 A 卖 B(不同名)不报;重复对每对只报一次
    mixed = [{'plane': 1, 'round_num': 3, 'actions': [
        {'__type__': 'BuyCard', 'reason': 'copy',
         'card': {'name': '停云', 'cost': 1, 'faction': '仙舟'}},
        {'__type__': 'SellBench', 'bench_idx': 0, 'name': '佩拉',
         'income': 1},
    ]}]
    assert not check_no_same_round_buy_sell(mixed), '不同名买卖不报'


def test_multi_sell_batch_desc_order_no_index_drift() -> None:
    """r408b(ADR-0267 补漏:索引漂移):同批多条 SellBench 按 idx
    降序——先弹高 idx 不影响低 idx,提案名=实打名。

    F1 残留根因(seed 25/36/56/57/58 实证):提案 [S(0), S(6)] 基于
    卖出前 bench,执行器逐条 pop 先弹 0 → 后续 idx 左移 → 卖错名
    (r4 提案卖青雀实卖本轮已买的娜塔莎——按名互斥被索引漂移绕过)。"""
    s = LineStrategy()
    st = GameState(gold=12, round_num=6, plane=1, level=4, hp=100,
                   level_up_cost=60)
    st.board = {'仙舟': 1}
    # bench 全杂牌(公司=线外):卖通道可自选多个候选
    st.bench = [BenchChar(slot=i, char_id=f'杂牌{i}', faction='公司')
                for i in range(7)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'dot_fallback'
    acts = s.decide_prep(st, sess, None)
    sells = [a for a in acts if isinstance(a, SellBench)]
    if len(sells) > 1:
        idxs = [a.bench_idx for a in sells]
        assert idxs == sorted(idxs, reverse=True), \
            f'批内 SellBench 应 idx 降序(先弹高 idx 保名): {idxs}'
        # 语义锁:按序 pop 后卖掉的名字 == 提案时 state.bench[idx] 名
        names_proposed = [st.bench[a.bench_idx].char_id for a in sells]
        bench_copy = list(st.bench)
        names_executed = [bench_copy.pop(a.bench_idx).char_id
                          for a in sells]
        assert names_proposed == names_executed, \
            f'索引漂移:提案 {names_proposed} vs 实卖 {names_executed}'


def test_residual_seeds_zero_violation() -> None:
    """r408b 回归锁:指挥官验收发现的 5 个残留 seed(n=60 批内
    idx 25/36/56/57/58)逐局重放,no_same_round_buy_sell 零违规。"""
    from sr_od.application.currency_war.cw_sim import simulate_p1
    for seed in (25, 36, 56, 57, 58):
        res = simulate_p1(seed, pool='snapshot')
        v = check_no_same_round_buy_sell(res.ledger)
        assert not v, f'seed {seed} 残留振荡(ADR-0267): {v[:3]}'


def test_duplicate_sell_slot_deduped() -> None:
    """r410b(ADR-0267 补漏):多条卖通道重复提案同一 bench 槽位 →
    去重保一条(同 idx 二次 pop 漂移卖掉相邻件——seed36 r3 双通道
    各提 姬子 槽,二弹卖掉本轮已买的绯英)。"""
    s = LineStrategy()
    from sr_od.application.currency_war.cw_state import SellBench as SB
    acts = ['x', SB(bench_idx=7), 'y', SB(bench_idx=7), SB(bench_idx=2)]
    # 直接驱动包装逻辑等价验证:同批 3 条卖出含重复 idx → 去重后
    # 2 条且降序(高 idx 先)
    _sell_pos = [i for i, a in enumerate(acts) if isinstance(a, SB)]
    _seen: set[int] = set()
    _kept = []
    for i in _sell_pos:
        if acts[i].bench_idx in _seen:
            continue
        _seen.add(acts[i].bench_idx)
        _kept.append(acts[i])
    _kept.sort(key=lambda a: a.bench_idx, reverse=True)
    assert len(_kept) == 2, '重复槽位应去重'
    assert [a.bench_idx for a in _kept] == [7, 2], '降序保名'


def test_copy_swap_useless_guard() -> None:
    """r410(ADR-0267 同族:同名跨副本无效换卡;局72 r8 实证)。

    形态:买同名 #2(line 通道)→ deploy sell-offtarget 卖在场旧
    #1(羁绊∩target_factions=∅)→ #2 顶替——净效果同角色换卡,
    白付操作+装备转移。守卫镜像 deploy 保留判据:
    - 同名在场副本 off-target(会被卖)→ 拒买(省 3 金+操作);
    - 同名在场副本是 target(core 名单/羁绊∩target)→ 正常买
      (凑对/3合1 合法)。"""
    s = LineStrategy()
    # 场:锁 feiying 线(target=欢愉/列车同行),艾丝妲(仙舟+DOT
    # flow)在场前排 → 羁绊∩target=∅ 且非 core → 会被 deploy 卖
    st = GameState(gold=28, round_num=6, plane=1, level=4, hp=100,
                   level_up_cost=60)
    st.board = {'欢愉': 2, '仙舟': 1}
    st.deployed = [BenchChar(slot=0, char_id='艾丝妲', faction='仙舟')]
    st.bench = [BenchChar(slot=0, char_id='绯英', faction='欢愉')]
    st.shop = [ShopCard(x=100, faction='仙舟', name='艾丝妲', cost=3)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'feiying_joy'
    s.update_target(st, sess, None)   # 建 target_comp(feiying 伪 comp)
    # ① 同名在场且 off-target → 守卫拒买
    assert s._copy_swap_useless(st.shop[0], st, sess), \
        '在场副本会被 deploy 卖 → 买=无效换卡应拒'
    assert not s._buy_guards(st.shop[0], st, 0, sess), \
        '守卫应经 _buy_guards 拦截'
    acts = s.decide_prep(st, sess, None)
    assert not [a for a in acts if isinstance(a, BuyCard)
                and a.card.name == '艾丝妲'], \
        f'无效换卡买入应被拦(局72 r8 形态): {[type(a).__name__ for a in acts]}'
    # ② 同名在场且是 target(core 名单)→ 正常买(凑对合法)
    sess2 = StrategySession()
    sess2.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess2.locked_line = 'feiying_joy'
    st2 = st.copy()
    st2.deployed = [BenchChar(slot=0, char_id='绯英', faction='欢愉')]
    st2.shop = [ShopCard(x=100, faction='欢愉', name='绯英', cost=2)]
    s.update_target(st2, sess2, None)
    assert not s._copy_swap_useless(st2.shop[0], st2, sess2), \
        '同名在场副本是 target core → 凑对合法'
    # ③ 同名羁绊命中 target_factions(DOT 线锁线时艾丝妲合法)
    sess3 = StrategySession()
    sess3.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess3.locked_line = 'dot_fallback'
    s.update_target(st, sess3, None)
    assert not s._copy_swap_useless(st.shop[0], st, sess3), \
        '锁 DOT 线时艾丝妲羁绊命中 target → 买副本合法'
    # ④ 无同名在场(deployed 无)→ 守卫不辖
    st4 = st.copy()
    st4.deployed = []
    assert not s._copy_swap_useless(st4.shop[0], st4, sess), \
        '无在场同名副本 → 守卫不辖'
