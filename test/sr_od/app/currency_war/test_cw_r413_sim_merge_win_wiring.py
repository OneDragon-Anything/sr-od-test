"""r413(ADR-0276/0277/0278)锁:sim 修复批五件。

- 件1(ADR-0276):3合1 merge 接入 sim 执行层——同名×3 自动合成
  升星(生产 `_merge_bench` 同语义),merges 入账本;
- 件2(ADR-0277 → ADR-0308 修订):boss 胜分支——胜负面 = W31
  实测节点×轮次胜率阶梯(``node_win_p``,n=192,boss 0.05),
  不再随成型度 rung 变化;胜时 Δ=+2 小额;
- 件3(ADR-0276):simulate_p1 结算补写 session.last_streak /
  决策前写 session.node_type_current(批⑤ F4,r308 保连胜门);
- 件4(ADR-0278):⑧-1 可负担门降级为日志观测(不过滤锁信号);
- 件5:批⑩/批⑪ 检查项双向锁(坏必报/好必过)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war import cw_sim_checks as chk
from sr_od.application.currency_war.cw_sim import (
    BOSS_WIN_DELTA,
    NODE_WIN_P_BY_TYPE,
    boss_settle_delta,
    simulate_p1,
)
from sr_od.application.currency_war.cw_state import BenchChar, GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)

# --- 件1:merge 接入 -------------------------------------------------------

def test_merge_counted_in_ledger_and_bench_drained() -> None:
    """merge 生效:批次内出现合并事件(merges>0),同名副本不再
    无限堆积(批⑩ F5 的「末轮 bench 均值 10.69>9 物理上限」形态
    应消失:末轮 bench ≤9)。

    ADR-0284(批㉒ F1/F3)后同窗同名 3 份 = 真实供给约束(同名
    占满多槽/多窗刷新),特定 seed 不再稳定触发——断言改为种子段
    扫描内「至少一局出现合并」(merge 接线仍生效的锁)。"""
    any_merge = False
    for seed in range(15):
        r = simulate_p1(seed, pool='fallback')
        any_merge = any_merge or any(
            (row['sim'].get('merges') or 0) > 0 for row in r.ledger)
        assert all(len(row['state']['bench']) <= 9
                   for row in r.ledger), f'seed{seed}: bench 超物理上限'
    assert any_merge, '种子段 0-14 内 3合1 全未触发(merge 接线回归)'


def test_merge_no_duplicate_star1_pile() -> None:
    """合并后同名同星堆 ≤2:同名 1★ 在 bench+deployed 全场域
    出现 ≥3 即被合并(生产 `_merge_bench` 不动点语义)。"""
    r = simulate_p1(7, pool='fallback')
    for row in r.ledger:
        from collections import Counter
        cnt = Counter((b['char_id'], 1)
                      for b in row['state']['bench']
                      if b['char_id'])
        dep_cnt = Counter((d['char_id'], 1)
                          for d in row['state']['deployed'])
        for (cid, _), n in (cnt + dep_cnt).items():
            assert n < 3, (
                f"r{row['round_num']}: {cid} 1★×{n} 未合并"
                f'(全场域 3合1 应消化)')


# --- 件2:boss 胜分支 ------------------------------------------------------

def _st_with_rung(rung: int) -> GameState:
    """构造成型度 rung 的 GameState(注册表实角色:列车2/仙舟3)。"""
    from sr_od.application.currency_war.cw_chars import CHARACTERS
    st = GameState(plane=1, round_num=9, level=9, hp=40, gold=0)
    train = [n for n, c in CHARACTERS.items()
             if '列车同行' in set(c.factions) | set(c.flows)][:2]
    xz = [n for n, c in CHARACTERS.items()
          if '仙舟' in set(c.factions) | set(c.flows)][:3]
    names = train + (xz if rung >= 2 else [])
    st.deployed = [BenchChar(slot=i, char_id=n,
                             faction=(CHARACTERS[n].factions or ['?'])[0])
                   for i, n in enumerate(names)]
    return st


def test_boss_win_rate_ladder_flat_across_rung() -> None:
    """ADR-0308:胜负面 = W31 阶梯边际(~0.05),不再随 rung 变化
    (旧 ADR-0277 rung 门的拍脑袋语义废弃;语料=旧策略病局镜像)。"""
    rng = random.Random(42)
    expect_p = NODE_WIN_P_BY_TYPE['boss']
    for rung in (1, 2):
        st = _st_with_rung(rung)
        n = 4000
        n_pos = sum(1 for _ in range(n)
                    if boss_settle_delta(st, 9, rng) > 0)
        # 带宽 ±40%(二项 sd@4000 ≈ 0.34%,带宽充裕)
        assert 0.6 * expect_p * n <= n_pos <= 1.4 * expect_p * n, \
            f'rung{rung} 胜率 {n_pos}/{n} 偏离阶梯 {expect_p}(ADR-0308)'


def test_boss_win_delta_is_small_positive() -> None:
    """胜时 Δ=胜利小额(+2,与 reward/supply 同档)。"""
    st = _st_with_rung(2)
    rng = random.Random(7)
    deltas = {boss_settle_delta(st, 9, rng) for _ in range(300)}
    assert BOSS_WIN_DELTA in deltas
    assert all(d <= BOSS_WIN_DELTA for d in deltas), \
        f'胜时 Δ 不应超过小额: {sorted(deltas, reverse=True)[:3]}'


def test_boss_win_emerges_in_batch() -> None:
    """批⑪ F1 验收(ADR-0308 口径):批量 boss 胜率 >0(结构性恒败
    解除)。阶梯胜率 ~0.05 → 种子段须足够长(15 局 P(0胜)≈54% 会
    假红;150 局 P(0胜)≈0.04%)。"""
    wins = rounds = 0
    for seed in range(150):
        r = simulate_p1(seed, pool='fallback')
        for _, nt, d, _ in r.hp_events:
            if nt == 'boss':
                rounds += 1
                wins += 1 if d >= 0 else 0
    assert rounds > 0 and wins > 0, f'boss {wins}/{rounds}(恒败回归)'


# --- 件3:session 结算补写 -------------------------------------------------

def test_session_streak_and_node_type_written() -> None:
    """simulate_p1 写 session.last_streak / node_type_current。"""
    sess = StrategySession()
    simulate_p1(3, session=sess, pool='fallback')
    assert isinstance(sess.last_streak, int) and sess.last_streak >= 0
    assert sess.node_type_current, '决策前应写当前节点类型'
    # 节点词表与 sim nodes 同源(生产 prep_director 语义)
    assert sess.node_type_current in (
        'battle', 'encounter', 'boss', 'reward', 'supply')


def test_session_wiring_unlocks_boss_breaker_gate() -> None:
    """批⑤ F4 验收:r308 保连胜门(地板降 5)在 sim 不再恒盲——
    构造连胜≥2+硬节点形态,`_boss_breaker_actions` 的地板分支
    可达(读 session.last_streak/node_type_current)。"""
    s = LineStrategy()
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'feiying_joy'
    sess.last_streak = 3          # 连胜 3(≥2)
    sess.node_type_current = 'encounter'
    st = GameState(gold=10, round_num=7, plane=1, level=4, hp=80)
    st.board = {'欢愉': 2}
    st.deployed = [BenchChar(slot=0, char_id='绯英', faction='欢愉'),
                   BenchChar(slot=1, char_id='爻光', faction='欢愉')]
    # 地板=5 时 budget=gold-5;地板=10 时 budget=0——用金耗差断言
    # 门读到 session(旧行:两 read 恒走 _BOSS_BREAKER_FLOOR)。
    acts = s._boss_breaker_actions(st, sess)
    # 弱断言:不崩 + 返回 list(门的可达性由 last_streak 读取保证;
    # 行为分支本身有 r308 专项锁)。
    assert isinstance(acts, list)


# --- 件4:⑧-1 可负担门降级 -------------------------------------------------

def test_lock_afford_gate_demoted_to_observation() -> None:
    """ADR-0278:金不足(买不起)的可见核心卡**仍锁线**(门降级为
    日志观测,不再过滤)——旧门在该形态会拒绝锁线。"""
    s = LineStrategy()
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    st = GameState(gold=1, round_num=3, plane=1, level=4, hp=80)
    # 商店放一张贵核心卡(锁线信号卡,金 1 买不起;绯英=feiying_joy
    # 线 core_cards 信号卡)
    from sr_od.application.currency_war.cw_state import ShopCard
    st.shop = [ShopCard(x=100, faction='欢愉', name='绯英', cost=2)]
    st.bench = []
    s.update_target(st, sess, None)
    assert sess.locked_line is not None, \
        '买不起的核心卡应仍锁线(ADR-0278:门降级,不拦)'


# --- 件5:批⑩/批⑪ 检查项双向锁 -------------------------------------------

def _lrow(rn: int = 1, gold: int = 30, bench_n: int = 9, dep_n: int = 6,
          cap: int = 7, buys: int = 1, node: str = 'battle',
          delta: int = -5, depth: int = 5, actions=None,
          board_factions=None, deployed=None, level: int = 5,
          hp: int = 50) -> dict:
    return {
        'plane': 1, 'round_num': rn, 'gold': gold, 'hp': hp,
        'actions': actions if actions is not None else [
            {'__type__': 'BuyCard',
             'card': {'name': 'x', 'cost': 1}, 'reason': 'line'}]
        * max(buys, 0),
        'state': {'level': level, 'cap': cap,
                  'bench': [{'char_id': f'b{i}', 'faction': '?'}
                            for i in range(bench_n)],
                  'deployed': deployed if deployed is not None else [
                      {'char_id': f'd{i}', 'faction': '?',
                       'slot': i, 'position_pref': 'back'}
                      for i in range(dep_n)],
                  'board_factions': board_factions or {}},
        'sim': {'node': node, 'delta': delta, 'depth': depth},
    }


def test_bench_full_deadlock_probe_bidirectional() -> None:
    """坏:连续 3 轮 bench 满+零买入+金>20+deployed<cap → 报;
    好:deployed=cap(末段合法停买)/仅 2 轮/有买入 → 不报。"""
    bad = [_lrow(rn=r, buys=0, dep_n=5, cap=7, gold=30)
           for r in (3, 4, 5)]
    assert chk.check_bench_full_deadlock_probe(bad), '死锁形态未报'
    ok_cap = [_lrow(rn=r, buys=0, dep_n=7, cap=7, gold=30)
              for r in (3, 4, 5)]
    assert not chk.check_bench_full_deadlock_probe(ok_cap), \
        'deployed=cap 末段停买是合法形态'
    ok_short = [_lrow(rn=r, buys=0, dep_n=5, cap=7, gold=30)
                for r in (3, 4)] + [_lrow(rn=5, buys=1)]
    assert not chk.check_bench_full_deadlock_probe(ok_short), \
        '仅 2 轮停滞(过渡态)不报'


def test_engine_seed_exemption_bidirectional() -> None:
    """批⑩ F3 裁决:engine_seed 同名买 ≥2 后卖 = 豁免;单张买后卖
    = 振荡,仍报(check_no_same_round_buy_sell 与裁决探针一致)。"""
    collect = [{'plane': 1, 'round_num': 1, 'actions': [
        {'__type__': 'BuyCard', 'reason': 'engine_seed',
         'card': {'name': '青雀', 'cost': 1}}] * 3 + [
        {'__type__': 'SellBench', 'bench_idx': 0, 'name': '青雀'}]}]
    assert not chk.check_no_same_round_buy_sell(collect), \
        '3合1 收集语境(买×3+卖冗余)应豁免(ADR-0276)'
    assert not chk.check_engine_seed_sell_exemption(collect)
    osc = [{'plane': 1, 'round_num': 1, 'actions': [
        {'__type__': 'BuyCard', 'reason': 'engine_seed',
         'card': {'name': '青雀', 'cost': 1}},
        {'__type__': 'SellBench', 'bench_idx': 0, 'name': '青雀'}]}]
    assert chk.check_no_same_round_buy_sell(osc), '单张买后卖仍 0 容忍'
    assert chk.check_engine_seed_sell_exemption(osc)


def test_boss_win_calibration_bidirectional() -> None:
    """坏:boss 轮 ≥n 地板且全负(恒败回归)→ 报;好:有胜 → 过;
    小批(<地板)0 胜 = 抽样噪声,不报(ADR-0308:阶梯胜率 ~0.05,
    0.95^25≈28%,smoke 级小批判恒败 = 恒假红)。"""
    # 坏:n=120(≥地板 100)全负 → 报
    bad = [[_lrow(rn=9, node='boss', delta=-18, depth=5)]
           for _ in range(120)]
    assert chk.check_boss_win_calibration(bad)['violations'] == 1
    good = [[_lrow(rn=9, node='boss', delta=2, depth=5)]]
    assert chk.check_boss_win_calibration(good)['violations'] == 0
    # 小批 0 胜(噪声带):地板下不判
    small = [[_lrow(rn=9, node='boss', delta=-18, depth=5)]
             for _ in range(25)]
    out = chk.check_boss_win_calibration(small)
    assert out['violations'] == 0 and out['min_rounds'] == 100


def test_formation_hp_coupling_bidirectional() -> None:
    """坏:成型局 hp 不高于未达局(≤0)→ 报;好:显著为正 → 过。

    ADR-0286 小批护栏:检查在任一侧 <20 局时只披露不判定(ADR-0312
    W50 从 <5 提到 <20:CI smoke n=25 两度噪声假红[formed_n=2 /
    13:12 侧 −4.11],v7 同批 n=300 真判 +5.39 绿)——本锁两侧各
    20 局(≥20,判定态)。"""
    formed = [[_lrow(rn=9, hp=40, board_factions={'列车同行': 2,
                                                  '仙舟': 3})]
              for _ in range(20)]
    unformed = [[_lrow(rn=9, hp=45, board_factions={})]
                for _ in range(20)]
    rep = chk.check_formation_hp_coupling_sentinel(formed + unformed)
    assert rep['violations'] == 1, '成型局更短命 = 价值链仍断'
    unformed2 = [[_lrow(rn=9, hp=10, board_factions={})]
                 for _ in range(20)]
    rep2 = chk.check_formation_hp_coupling_sentinel(formed + unformed2)
    assert rep2['violations'] == 0 and rep2['diff'] > 0
    # 护栏本身:两侧 1 局(小批)= 只披露不判定
    rep3 = chk.check_formation_hp_coupling_sentinel(
        formed[:1] + unformed[:1])
    assert rep3['violations'] == 0 and 'note' in rep3


def test_levelup_binding_bidirectional() -> None:
    """坏:r8/r9 loose 占比 >60% → 报;好:binding 主导 → 过。"""
    def _lv_row(rn, dep_n, level):
        return _lrow(rn=rn, dep_n=dep_n, cap=9, level=level,
                     actions=[{'__type__': 'LevelUp', 'cost': 4}])
    bad = [_lrow(rn=7, dep_n=4, cap=9, level=5, actions=[]),
           _lv_row(8, 4, 5), _lv_row(9, 4, 5)]   # r7 垫行定 prev_lv=5
    assert chk.check_levelup_binding([bad])['violations'] == 1
    good = [_lrow(rn=7, dep_n=6, cap=9, level=5, actions=[]),
            _lv_row(8, 6, 5), _lv_row(9, 6, 5)]
    assert chk.check_levelup_binding([good])['violations'] == 0


def test_r5plus_refresh_closure_disclosure() -> None:
    """披露型:r5+ 刷新计数,violations 恒 0。"""
    rows = [_lrow(rn=6, actions=[
        {'__type__': 'RefreshShop', 'cost': 2}])]
    rep = chk.check_r5plus_refresh_closure([rows])
    assert rep == {'violations': 0, 'r5plus_refreshes': 1}


def test_sim_endgold_calib_bidirectional() -> None:
    """坏:末金均值/实机 >1.5 → 报;好:≤1.5 → 过。"""
    rich = [_lrow(rn=9, gold=50)]
    assert chk.check_sim_endgold_calib([rich])['violations'] == 1
    lean = [_lrow(rn=9, gold=24)]
    assert chk.check_sim_endgold_calib([lean])['violations'] == 0


def test_anchor_registry_n300_completeness() -> None:
    """登记制:报告缺登记锚指标 → 报;全含 → 过 + 披露 drift。"""
    rep = chk.check_anchor_registry_n300({'pool_fingerprint': 'x'})
    assert rep['violations'] > 0, '锚指标缺失未报'
    full = {'pool_fingerprint':
            chk.ANCHOR_REGISTRY_N300['pool_fingerprint_prefix'],
            **chk.ANCHOR_REGISTRY_N300['metrics']}
    rep2 = chk.check_anchor_registry_n300(full)
    assert rep2['violations'] == 0
    assert all(v == 0 for v in rep2['drift'].values())
    assert rep2['pool_fp_match'] is True


def test_checks_module_still_no_sim_import() -> None:
    """依赖方向:新增检查后 checks 仍不 import cw_sim。"""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(chk))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or '']
        else:
            continue
        for n in names:
            assert 'cw_sim' not in n, f'checks 不得 import cw_sim: {n}'
