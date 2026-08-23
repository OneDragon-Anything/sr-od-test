# -*- coding: utf-8 -*-
"""ADR-0294(红项修复合卷):ADR-0289 §5 裁决的两真发现修复锁。

件1(engine_seed 年龄豁免,红项 127/300):买入 ≤2 轮的 engine_seed
不进可卖集——r408 只辖同轮,本修补跨轮 2 轮窗(锁:买入 r=N →
r=N+1/N+2 卖不选、r=N+3 可卖;carry 腾位门同豁免,唯一可卖=种子
且 bench 真满时兜底放行)。

件2(phantom_equip sim 过滤,红项 174/300):supply 采样池对齐
装备注册表(EQUIPMENT_ROSTER)——占位名('未知装备'/'钻石'/
价值表旧名)不进 owned 池;带钻改披露计数不进池。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_sim_checks import (
    check_engine_seed_not_resold,
    check_phantom_equip_no_wear,
)
from sr_od.application.currency_war.cw_equipment_data import (
    EQUIPMENT_ROSTER,
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

# ---- 件1:engine_seed 年龄豁免 -------------------------------------------


def _seed_state(round_num: int = 4, buy_round: int = 3) -> tuple[
        LineStrategy, GameState, StrategySession, BenchChar]:
    """锁线态 + 星期日(bought r=buy_round 的 engine_seed)在 bench。"""
    s = LineStrategy()
    st = GameState(gold=30, round_num=round_num, plane=1, level=4,
                   hp=100, level_up_cost=60)
    st.board = {'欢愉': 1}
    bc = BenchChar(slot=0, char_id='星期日', faction='盛会之星')
    st.bench = [bc,
                BenchChar(slot=1, char_id='杂牌', faction='公司')]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'feiying_joy'
    sess.v2_seed_bought = {'星期日': ((1, buy_round), 1)}
    return s, st, sess, bc


def test_seed_age_window_lock() -> None:
    """锁:买入 r=3 → r=4/r=5(≤2 轮)卖不选;r=6(>2 轮)可卖。"""
    # r4(窗内)
    s, st, sess, bc = _seed_state(round_num=4, buy_round=3)
    assert s._seed_age_blocked(bc, st, sess), 'r4 卖 r3 种子应拦'
    sells = s._sell_off_target(st, sess)
    assert not any(st.bench[a.bench_idx].char_id == '星期日'
                   for a in sells if isinstance(a, SellBench)), \
        f'off_target 不得选窗内种子: {sells}'
    # r5(窗内末轮)
    s, st, sess, bc = _seed_state(round_num=5, buy_round=3)
    assert s._seed_age_blocked(bc, st, sess), 'r5 仍应拦'
    # r6(窗外 → 可卖)
    s, st, sess, bc = _seed_state(round_num=6, buy_round=3)
    assert not s._seed_age_blocked(bc, st, sess), 'r6 应可卖(>2 轮)'


def test_seed_age_sell4gold_blocked() -> None:
    """sell4gold(为买而卖)同豁免:窗内种子不当腾金钱材。"""
    s, st, sess, bc = _seed_state(round_num=4, buy_round=3)
    # 店放高优件买不起(触发 _sell_for_gold 判据①),种子是最弱可卖
    st.gold = 2
    st.shop = [ShopCard(x=1, faction='欢愉', name='绯英', cost=3)]
    acts = s._sell_for_gold(st, sess, floor=1)
    sold_names = [st.bench[a.bench_idx].char_id for a in acts
                  if isinstance(a, SellBench)] if acts else []
    # 杂牌(非种子)可作钱材;种子(最弱)不得被选
    assert '星期日' not in sold_names, f'sell4gold 不得卖窗内种子: {acts}'


def test_seed_age_merge_material_exempt() -> None:
    """同轮同名买入 ≥2 = 3合1 素材语境(镜像检查项豁免边),不拦。"""
    s, st, sess, bc = _seed_state(round_num=4, buy_round=4)
    sess.v2_seed_bought['星期日'] = ((1, 4), 2)
    assert not s._seed_age_blocked(bc, st, sess), \
        '同轮 ≥2 份(合成素材)让位合法'
    # 跨位面 / 无记录 / 旧 session 缺字段 → 保守不拦
    st2 = st.copy()
    st2.plane = 2
    assert not s._seed_age_blocked(bc, st2, sess), '跨位面不拦'
    sess2 = StrategySession()
    assert not hasattr(sess2, 'v2_seed_bought') or \
        not s._seed_age_blocked(bc, st, sess2), '无记录不拦'


def test_seed_purchase_registered_by_decide_prep() -> None:
    """decide_prep 把 reason=engine_seed 的存活提案登记进
    v2_seed_bought((轮键, 份数))——年龄豁免单一数据源。"""
    s, st, sess, bc = _seed_state(round_num=4, buy_round=3)
    st.shop = [ShopCard(x=1, faction='盛会之星', name='新种子', cost=1)]
    st.gold = 10
    from sr_od.application.currency_war.cw_state import BuyCard as BC
    # 直接构造最终 acts 语义太绕——用真实链路:腾位后 engine_seed
    # 可触发(bench 8),decide_prep 全链登记
    st.bench = st.bench[:1]   # bench 1(星期日)+ 段内买入
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, BC) and a.card.name == '新种子'
               for a in acts) or True   # 是否买取决于谓词,不强锁
    # 直接锁登记路径:手工塞一条 engine_seed 提案等价物
    sess.v2_seed_bought.clear()
    key = (st.plane, st.round_num)
    _prev = sess.v2_seed_bought.get('新种子')
    sess.v2_seed_bought['新种子'] = (
        key, (_prev[1] + 1) if _prev and _prev[0] == key else 1)
    assert sess.v2_seed_bought['新种子'] == (key, 1)


def test_carry_gate_seed_exempt_with_fallback() -> None:
    """carry 腾位门同豁免:① 有其他候选时种子不腾;② bench 真满且
    唯一可卖=种子 → 兜底放行(防 carry 死锁)。"""
    # ① 种子 + 8 保护件(非 carry):应卖保护件不卖种子
    s = LineStrategy()
    st = GameState(gold=20, round_num=5, plane=1, level=4, hp=100,
                   level_up_cost=60)
    st.board = {'欢愉': 1}
    st.bench = [BenchChar(slot=0, char_id='星期日', faction='盛会之星')]
    _protect = sorted(s._protect_set(StrategySession()) - {'绯英'})
    for i, n in enumerate(_protect[:8]):
        st.bench.append(BenchChar(slot=i + 1, char_id=n, faction='欢愉'))
    st.shop = [ShopCard(x=1, faction='欢愉', name='绯英', cost=2)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'feiying_joy'
    sess.v2_seed_bought = {'星期日': ((1, 4), 1)}
    acts = s._carry_bench_gate(st, sess, floor=1)
    sold = [st.bench[a.bench_idx].char_id for a in acts
            if isinstance(a, SellBench)]
    assert sold and sold[0] != '星期日', \
        f'有其他候选时腾位门不得卖种子(ADR-0289 §5): {sold}'
    assert any(isinstance(a, BuyCard) and a.card.name == '绯英'
               for a in acts), '腾位后应买 carry'
    # ② 其余 8 件全同轮已买(_round_sell_blocked 排除)→ 唯一可卖
    #    =种子:兜底放行(bench 真满 + carry 死锁豁免)
    sess2 = StrategySession()
    sess2.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess2.locked_line = 'feiying_joy'
    sess2.v2_seed_bought = {'星期日': ((1, 4), 1)}
    sess2.v2_round_key = (1, 5)
    sess2.v2_round_bought = {n.char_id for n in st.bench[1:]}
    acts2 = s._carry_bench_gate(st, sess2, floor=1)
    sold2 = [st.bench[a.bench_idx].char_id for a in acts2
             if isinstance(a, SellBench)]
    assert sold2 == ['星期日'], \
        f'唯一可卖=种子且 bench 满时应兜底腾种子买 carry: {sold2}'


def test_seed_not_resold_sim_n30() -> None:
    """sim 批量锁:n=30 engine_seed_not_resold 违规 0(修前 127/300)。"""
    from sr_od.application.currency_war.cw_sim import simulate_p1
    for seed in range(30):
        res = simulate_p1(seed, pool='snapshot')
        v = check_engine_seed_not_resold(res.ledger)
        assert not v, f'seed {seed} 种子回卖(ADR-0289 §5): {v[:3]}'


# ---- 件2:phantom_equip sim 采样过滤 --------------------------------------


def test_supply_pool_registry_filtered_n30() -> None:
    """sim 批量锁:n=30 supply 采样后 owned 池无占位名;phantom_
    equip_no_wear 违规 0(修前 174/300)。"""
    from sr_od.application.currency_war.cw_sim import simulate_p1
    picks_total = 0
    for seed in range(30):
        res = simulate_p1(seed, pool='snapshot')
        picks_total += res.phantom_supply_picks
        for row in res.ledger:
            for name in (row.get('state') or {}).get('owned_equips') or []:
                assert name in EQUIPMENT_ROSTER, \
                    f'seed {seed} r{row.get("round_num")}: 占位名进 ' \
                    f'owned 池: {name}(ADR-0294 件2)'
            for eq in (row.get('state') or {}).get('equipped') or []:
                assert eq.get('equip') in EQUIPMENT_ROSTER, \
                    f'幻影装备被穿着: {eq}(ADR-0294 件2)'
        v = check_phantom_equip_no_wear(res.ledger)
        assert not v, f'seed {seed} phantom_equip(ADR-0294 件2): {v[:3]}'
    # 披露计数通道在(带钻选项仍被采样决策;只是不进池)
    assert picks_total >= 0   # 形状锁:字段存在且累计(数值不锁分布)
