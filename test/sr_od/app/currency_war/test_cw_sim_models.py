"""sim 模型族主题锁,五段各辖一个生产面的独家覆盖:

- sim.checks 检查器锁族:ledger/pool/runtime 逐局检查器双向锁 +
  corpus/calib 锚登记披露 + runner 批量集登记门(检查器判据出处
  见各生产函数 docstring);
- 标定口径与注册表登记门(2026-09-09 合并批承三小件并入,断言
  逐条原样迁移):rung 统计口径(原 test_cw_goldrich_rungstat,
  ADR-0305 件2)、boss 税标量墓碑(原 test_cw_boss_tax_p75_by_plane)、
  连胜奖励表守卫(原 test_cw_streak_gold_table,r305);
- cw_evolution 引擎补完通道(ADR-0371):补完事务发射/保护序/
  末窗豁免/冻结轮/希儿系单卡/bench 溢出/观测行格式;
- simulate_p1 补给两步链:decide_supply 在 sim 引擎内的接线行为
  (decide_supply 单元选择行为归 test_cw_decisions.py);
- cw_coarse_battle 战斗粗模型:两态采样/先验收缩/位面维/引擎开关/
  版本披露(结构语义单一源 = 该模块 docstring);
- cw_first_passage 首达生存:P(win)/hp_floor/位面乘子/三区律
  (P2 损血标定面归 test_cw_dp_first_passage.py)。

CUT6 瘦身批(2026-09-09):sim 每晚真局覆盖的披露/锚登记/诊断分键/
采样行为面砍除(endgold 探针/期限分键/条件披露/锚登记工具/CEM 外
机械面等),保留核清单与逐条判据见 reports/_cluster_CUT6.md。
"""
from __future__ import annotations

import json
import random
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel import (
    cw_coarse_battle as cb,
)
from sr_od.application.currency_war.kernel import (
    cw_events,
)
from sr_od.application.currency_war.kernel.cw_battle_calib import (
    _battles_before_engines,
    _board_factions_of,
    _first_engines_round,
)
from sr_od.application.currency_war.kernel.cw_economy import streak_gold
from sr_od.application.currency_war.kernel.cw_evolution import (
    EvolutionState,
    evolution_step,
)
from sr_od.application.currency_war.kernel.cw_first_passage import (
    _loss_dist,
    first_passage_win,
    hp_floor,
    plane_hp_ratio,
    posture_guidance,
    risk_posture,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    CompTransaction,
    GameState,
    _recount_board,
    simulate,
)
from sr_od.application.currency_war.sim import engine_p1 as cw_sim
from sr_od.application.currency_war.sim import pool as sim_pool
from sr_od.application.currency_war.sim import runner as sim_runner
from sr_od.application.currency_war.sim.checks import (
    ledger,
    pool,
    runner,
    runtime,
)
from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
from sr_od.application.currency_war.strategies.impl.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# ==================== sim.checks 检查器锁族 ====================


def _row(rn: int = 1, gold: int = 10, bench: list | None = None,
         deployed: list | None = None, cap: int = 4,
         actions: list | None = None, target_comp: str = '',
         sim: dict | None = None, level: int = 3,
         equipped: list | None = None,
         bf: dict | None = None) -> dict:
    row = {
        'plane': 1, 'round_num': rn, 'gold': gold, 'hp': 50,
        'target_comp': target_comp,
        'state': {
            'board': {}, 'level': level,
            'bench': bench if bench is not None else [],
            'deployed': deployed if deployed is not None else [],
            'cap': cap,
            'equipped': equipped if equipped is not None else [],
            'owned_equips': [],
        },
        'actions': actions or [],
        'sim': sim if sim is not None else {
            'node': 'battle', 'delta': -5, 'gold_before': gold,
            'income': {'base': 5}, 'spend': {'buys': {}, 'levelup': 0,
                                             'refresh': 0},
            'shop_waves': [], 'merges': 0,
        },
    }
    if bf is not None:
        # 成型度面:state.board_factions = 体系计数 dict(_rung_of_row 消费)
        row['state']['board_factions'] = bf
    return row


# --- 账本不变量类(批⑮/⑰/⑧) --------------------------------------

def test_gold_nonneg_bidirectional() -> None:
    bad = [_row(gold=-1)]
    assert ledger.check_gold_nonneg_invariant(bad), '负金未报=静默失效'
    good = [_row(gold=0), _row(gold=5)]
    assert not ledger.check_gold_nonneg_invariant(good)


def test_bench_capacity_bidirectional() -> None:
    bench10 = [{'char_id': f'c{i}', 'faction': 'x'} for i in range(10)]
    assert ledger.check_bench_capacity_invariant(
        [_row(bench=bench10)]), 'bench>9 未报'
    bench9 = bench10[:9]
    assert not ledger.check_bench_capacity_invariant([_row(bench=bench9)])


# --- 动作语义类 ------------------------------------------------------

def test_engine_seed_not_resold_bidirectional() -> None:
    buy = [{'__type__': 'BuyCard',
            'card': {'name': '青雀', 'cost': 1},
            'reason': 'engine_seed'}]
    bad = [
        _row(rn=3, actions=buy),
        _row(rn=4, actions=[{'__type__': 'SellBench', 'name': '青雀'}]),
    ]
    assert pool.check_engine_seed_not_resold(bad), '跨轮即卖未报'
    # 好:≥3 轮后卖(合成消化窗外)
    ok_late = [
        _row(rn=3, actions=buy),
        _row(rn=6, actions=[{'__type__': 'SellBench', 'name': '青雀'}]),
    ]
    assert not pool.check_engine_seed_not_resold(ok_late)
    # 好:同轮收集 ≥2,冗余让位(ADR-0276 同族豁免)
    ok_collect = [
        _row(rn=3, actions=buy + [
            {'__type__': 'BuyCard', 'card': {'name': '青雀', 'cost': 1},
             'reason': 'engine_seed'}]),
        _row(rn=4, actions=[{'__type__': 'SellBench', 'name': '青雀'}]),
    ]
    assert not pool.check_engine_seed_not_resold(ok_collect)


def test_buys_at_full_bench_bidirectional() -> None:
    bench9 = [{'char_id': f'c{i}', 'faction': 'x'} for i in range(9)]
    buy = [{'__type__': 'BuyCard', 'card': {'name': 'a', 'cost': 1},
            'reason': 'line'}]
    bad = [
        _row(rn=1, bench=bench9, sim={'node': 'battle', 'merges': 0,
                                       'shop_waves': []}),
        _row(rn=2, bench=bench9, actions=buy,
             sim={'node': 'battle', 'merges': 0, 'shop_waves': []}),
    ]
    assert ledger.check_buys_at_full_bench(bad), '满仓买未报'
    good = [
        _row(rn=1, bench=bench9,
             sim={'node': 'battle', 'merges': 0, 'shop_waves': []}),
        _row(rn=2, bench=bench9,
             actions=[{'__type__': 'SellBench', 'name': 'c0'}] + buy,
             sim={'node': 'battle', 'merges': 0, 'shop_waves': []}),
    ]
    assert not ledger.check_buys_at_full_bench(good)


def test_oscillation_xp_cap_bidirectional() -> None:
    osc = [{'__type__': 'BuyCard', 'card': {'name': 'a', 'cost': 1},
            'reason': 'line'},
           {'__type__': 'SellBench', 'name': 'a'}]
    # 判别力锚:lv9 need=84 → 8 XP < 30% 不报(见 good);lv5 need=20、
    # 30%=6 → 两次振荡 8 XP 超限报(单次 4 XP 不超,同踩阈值边界)
    osc2 = osc + [
        {'__type__': 'BuyCard', 'card': {'name': 'b', 'cost': 1},
         'reason': 'line'},
        {'__type__': 'SellBench', 'name': 'b'},
    ]
    bad = [_row(rn=1, level=5, actions=osc2,
                sim={'node': 'battle', 'shop_waves': []})]
    assert ledger.check_oscillation_xp_cap(bad), '白拿 XP 超限未报'
    good = [_row(rn=1, level=9, actions=osc2,
                 sim={'node': 'battle', 'shop_waves': []})]
    assert not ledger.check_oscillation_xp_cap(good)


def test_levelup_flat4_lock_bidirectional() -> None:
    """升级支出锁双向(T-240 语义重推:判据 = spend == Σ action.cost,
    无折扣局退化为原字面 4×行数;重推依据 = 锁检查器 docstring)。

    - 无折扣一致(spend 4)/偏离(spend 6):原判据面保持,双向照旧;
    - 折扣局(商业间谍,载体单价 3):spend 3×行数 → 绿——旧字面 4×行数
      在此误报 = 重推动因(在先矛盾);载体 3 实付 4 → 报(执行器弃用
      决策载体回退私价模型回归);
    - cost 缺读行(旧档案形状):按引擎同口径 4 兜(engine_p1
      `getattr(a,'cost',0) or 4`),判据不因档案代际漂移。"""
    _sim = {'node': 'battle', 'merges': 0, 'shop_waves': []}

    def _spend(v: int) -> dict:
        return {'node': 'battle', 'merges': 0, 'shop_waves': [],
                'spend': {'buys': {}, 'levelup': v, 'refresh': 0}}

    good = [_row(actions=[{'__type__': 'LevelUp', 'cost': 4}], sim=_spend(4))]
    assert not ledger.check_levelup_flat4_ledger_lock(good)
    bad = [_row(actions=[{'__type__': 'LevelUp', 'cost': 4}], sim=_spend(6))]
    assert ledger.check_levelup_flat4_ledger_lock(bad), 'flat4 偏离未报'
    # 折扣局:载体 3×2 行实付 6 → 绿(旧字面判据 4×2=8 在此误报)
    spy_ok = [_row(actions=[{'__type__': 'LevelUp', 'cost': 3},
                            {'__type__': 'LevelUp', 'cost': 3}],
                   sim=_spend(6))]
    assert not ledger.check_levelup_flat4_ledger_lock(spy_ok)
    # 折扣局执行偏离:载体 3 实付 4 → 报
    spy_bad = [_row(actions=[{'__type__': 'LevelUp', 'cost': 3}],
                    sim=_spend(4))]
    assert ledger.check_levelup_flat4_ledger_lock(spy_bad), \
        '折扣局执行器偏离决策载体未报'
    # 旧档案行 cost 缺读 → 引擎同口径 4 兜
    legacy = [_row(actions=[{'__type__': 'LevelUp'}], sim=_spend(4))]
    assert not ledger.check_levelup_flat4_ledger_lock(legacy)


def test_degrade_recover_mutex_segment_first_round() -> None:
    """段首轮号语义锁:history 段首 = 配方首次出现轮,段末不覆盖。

    判据表语义无歧义:切线 A→B 后 ≤3 轮内回锁 A = relapse 指纹,
    回锁时点 = A 首次重新出现之轮;r_c - r_b 因此等于 B 段驻留
    轮数(≤3 = 试错回摆,>3 = 合法 pivot 不辖)。缺陷形态(段末
    覆盖):「回锁后保持稳定」的 A 段轮号被推到段末,r_c - r_b
    必然 >3,最常见回摆形态全部漏判(实测摇摆率被低估约一半)。
    """
    a, b = '过渡配方·仙舟+列车同行', '过渡配方·仙舟+希儿系'

    def _seq(rounds: list[tuple[int, str]]) -> list[dict]:
        return [_row(rn=rn, target_comp=comp) for rn, comp in rounds]

    # 回锁后保持稳定 ≥4 轮(最常见试错回摆形态;段末覆盖语义下
    # r_c 取段末 10,r_c - r_b = 10 - 5 = 5 > 3 → 全部漏判):
    # 段首语义 r_c = 6,r_c - r_b = 1 → 恰 1 次命中
    stable = _seq([(1, a), (2, a), (3, a), (4, a), (5, b),
                   (6, a), (7, a), (8, a), (9, a), (10, a)])
    hits = ledger.check_degrade_recover_mutex(stable)
    assert len(hits) == 1, f'回锁后稳定形态漏判: {hits}'
    assert '(r5)' in hits[0] and '(r6)' in hits[0], hits[0]

    # 边界:B 段驻留恰 3 轮后回锁 = 摇摆(检出);驻留 4 轮 =
    # 合法 pivot(不辖;段末覆盖语义下后者反而命中——判据失真)
    edge3 = _seq([(1, a), (2, a), (3, b), (4, b), (5, b),
                  (6, a), (7, a)])
    assert len(ledger.check_degrade_recover_mutex(edge3)) == 1
    pivot4 = _seq([(1, a), (2, a), (3, b), (4, b), (5, b), (6, b),
                   (7, a), (8, a)])
    assert not ledger.check_degrade_recover_mutex(pivot4), \
        'B 段驻留 4 轮的合法 pivot 误报'

    # 连续摇摆逐三元组各记一次(A→B→A→B→A = 3 次)
    multi = _seq([(1, a), (2, b), (3, a), (4, b), (5, a), (6, a)])
    assert len(ledger.check_degrade_recover_mutex(multi)) == 3

    # p2 段与空 target_comp 不进 history(p1 口径):剔除后剩
    # A(r1)→B(r4)→A(r5),恰 1 次命中
    noise = _seq([(1, a), (2, b), (3, ''), (4, b), (5, a)])
    noise[1]['plane'] = 2
    assert len(ledger.check_degrade_recover_mutex(noise)) == 1


def test_degrade_recover_mutex_same_anchor_containment_exempt() -> None:
    """同锚子集/超集转换豁免语义锁(ADR-0616 §3.3 裁决②;T-166 批1)。

    门槛过滤先行落地后,1 元对为在册边缘帧(ADR-0616 §2.1),合法新增
    「{A,B}→{A}→{A,B'}」席位退场/补位链——同锚包含关系转换是席位进出,
    不是方向切线,并入前段延续(段首轮号语义不更新);跨锚转换仍各立段
    照判,守卫意图(A→B→A relapse 指纹 + ≤3 轮辖域)零松动。
    """
    ab = '过渡配方·仙舟+列车同行'
    a1 = '过渡配方·仙舟'                    # 1 元对(锚=仙舟 ⊂ {仙舟,列车同行})
    ab2 = '过渡配方·仙舟+持续伤害'          # 同锚补位(列车退场→DOT 补位)
    cd = '过渡配方·持续伤害+希儿系'         # 跨锚(仙舟系退场)

    def _seq(rounds: list[tuple[int, str]]) -> list[dict]:
        return [_row(rn=rn, target_comp=comp) for rn, comp in rounds]

    # 豁免格:席位退场→回补({A,B}→{A}→{A,B}),方向未切线 → 0 命中
    # (旧语义按三元组误计 1 次 relapse——裁决②的豁免对象)
    seat_cycle = _seq([(1, ab), (2, a1), (3, ab), (4, ab), (5, ab)])
    assert ledger.check_degrade_recover_mutex(seat_cycle) == [], \
        '同锚子集/超集转换被误计为切线摇摆'

    # 豁免链延伸:退场→同锚补位({A,B}→{A}→{A,B'}) → 0 命中
    seat_refill = _seq([(1, ab), (2, a1), (3, ab2), (4, ab2)])
    assert ledger.check_degrade_recover_mutex(seat_refill) == []

    # 跨锚回摆仍照判:A+B→C+D→A+B(方向真切线又回锁)→ 恰 1 命中
    cross = _seq([(1, ab), (2, cd), (3, ab), (4, ab)])
    hits = ledger.check_degrade_recover_mutex(cross)
    assert len(hits) == 1, f'跨锚回摆漏判(守卫意图松动): {hits}'

    # 二席换人({A,B}→{A,B'})非包含关系 → 立段照判:换回 = 1 命中
    seat_swap = _seq([(1, ab), (2, ab2), (3, ab), (4, ab)])
    assert len(ledger.check_degrade_recover_mutex(seat_swap)) == 1

    # 经由 1 元对中转的跨锚回摆:{A,B}→{A}→{C+D}→{A,B}:同锚半段并入
    # 不稀释三元组 → A+B→C+D→A+B 恰 1 命中(豁免不制造漏判盲区)
    mixed = _seq([(1, ab), (2, a1), (3, cd), (4, ab), (5, ab)])
    assert len(ledger.check_degrade_recover_mutex(mixed)) == 1

    # 非过渡配方名(终局 comp 等)无锚集 → 原子段行为不变
    legacy = _seq([(1, '某终局套'), (2, a1), (3, '某终局套')])
    assert len(ledger.check_degrade_recover_mutex(legacy)) == 1


# --- 段级检查器(sim/checks/segments,seg_* 族) ----------------------
# 段级行形状与上面 _row(ledger 批检查器)不同:成型判据读
# state.board_factions(engines_count 单一源),不消费 board/equipped。

def _seg_formed_state() -> dict:
    """成型态 board_factions:仙舟3+列车2 = 两体系达成(engines≥2)。"""
    return {'board_factions': {'仙舟': 3, '列车同行': 2},
            'deployed': [{'char_id': '藿藿'}], 'bench': [],
            'cap': 5, 'level': 5}


def _seg_row(round_num: int, *, gold: int = 30,
             actions: list | None = None,
             state: dict | None = None,
             plane: int = 1, hp: int = 60, node: str = 'battle',
             waves_gold: int | None = None,
             gold_readable: bool | None = None,
             formed_stop: bool = False,
             bench_full_skipped_buys: int = 0,
             sim_extra: dict | None = None) -> dict:
    """合成段级账本行(形状对齐 seg 检查器消费面;shop_waves 单波)。

    可选参按各 seg 检查器消费面扩展(T-196 回补批):P2 面用
    plane/hp/gold_readable;[17]/[6] 豁免面用 formed_stop/
    bench_full_skipped_buys;时点金与末金分离用 waves_gold(g0 取
    首波 gold);node/sim_extra 供奖励帧、连胜 delta、spend 分解等
    sim 子字典覆盖(sim_extra 浅合并,同键整体覆盖)。
    """
    sim: dict = {'node': node,
                 'income': {'base': 5, 'interest': 0, 'streak': 0,
                            'event': 1},
                 'spend': {'buys': {}, 'levelup': 0, 'refresh': 0,
                           'sell_income': 0},
                 'shop_waves': [{'event': 'offer',
                                 'gold': gold if waves_gold is None
                                 else waves_gold,
                                 'cards': []}]}
    if bench_full_skipped_buys:
        sim['bench_full_skipped_buys'] = bench_full_skipped_buys
    if sim_extra:
        sim.update(sim_extra)
    row = {
        'plane': plane, 'round_num': round_num, 'gold': gold,
        'hp': hp, 'formed_stop': formed_stop, 'target_comp': '',
        'state': state if state is not None else {
            'board_factions': {}, 'deployed': [], 'bench': [],
            'cap': 3, 'level': 4},
        'actions': actions or [],
        'sim': sim,
    }
    if gold_readable is not None:
        row['gold_readable'] = gold_readable
    return row


def _seg_buy(name: str, cost: int = 1,
             channel: str = 'engine') -> dict:
    """段级买入动作(身份通道写入 reason/channel,seg 检查器消费面)。"""
    return {'__type__': 'BuyCard', 'card': {'name': name, 'cost': cost},
            'reason': f'd2_{channel}', 'channel': channel}


def test_seg_formed_still_buying_transition_release_arm() -> None:
    """[13] ④ 放行臂例外(两形态构造帧锁)。前身 = 同名锁,原在
    test_cw_sim_suite.py,2026-09-09 测试重组批(f799914)申报性退役,
    T-192 回补至本主题文件——现役具名锁缺失期间该例外臂回潮无人报。

    断言:成型后经 ④ 转线前瞻放行臂(买因 ``transition_component_buy``)
    买入 TRANSITION_PACK carry/partial 成员**不报**。出处 = 策略文档
    12_line_and_intention.md §2「④ 转线前瞻放行臂 = 未定型期转型前瞻
    例外」边界行(用户裁定 2026-09-07);对齐申报 = ADR-0580 §3 规则④
    + §7。纯过渡件仍报,负空间两形态:
    - drop 档带 ④ 买因(写侧误挂形态)照报 = 放行集成员资格闸——
      drop 档在 transition_release_names 数据源处即不入集,负空间
      排除,无需独立 drop 判定;
    - 放行集成员不经 ④ 买因(常规通道买入)照报 = 买因闸——例外
      只辖 ④ 臂买入,不经该臂的过渡件买入仍在 [13] 辖域。
    夹具选名(回补时亲核注册表):姬子·启行 = TRANSITION_PACK carry
    档、BRIDGE_POOL_P2 fixed(P1 检测器 bridge 豁免集只并 BRIDGE_POOL,
    不含 P2 池)、列车阵营(engine 身份档);卡芙卡 = drop 档、P1 桥池
    flex 档(豁免集只收 fixed∪core,不收 flex)——都避开桥池/目标
    名册既有豁免,防既有豁免先行吞掉例外分支(锁假绿)。
    事件轮号 = 买入行 round_num 原值(seg 检查器逐行判定,无跨轮归并;
    与 ledger.check_degrade_recover_mutex 的段首轮号语义互不相干,
    T-194 修正不辖本检查器)。
    """
    from sr_od.application.currency_war.sim.checks.segments import (
        seg_check_formed_still_buying_transition,
    )
    formed = _seg_formed_state()

    def _frame(buy: dict) -> list[dict]:
        # 行1 成型态(engines≥2),行2 携买入动作:成型判定逐行先
        # 更新后检查,行2 落在成型后辖域。
        return [_seg_row(1, state=dict(formed)),
                _seg_row(2, state=dict(formed), actions=[buy])]

    def _buy4(name: str) -> dict:
        return {'__type__': 'BuyCard', 'card': {'name': name, 'cost': 3},
                'reason': 'transition_component_buy', 'channel': 'engine'}

    # ④ 件放行:carry 成员 + ④ 买因 → 不报
    assert not seg_check_formed_still_buying_transition(
        _frame(_buy4('姬子·启行')))
    # drop 档 + ④ 买因(误挂形态)→ 仍报,事件点名声与买因
    evs_drop = seg_check_formed_still_buying_transition(
        _frame(_buy4('卡芙卡')))
    assert evs_drop and evs_drop[0]['round_num'] == 2 \
        and evs_drop[0]['bought'] == '卡芙卡' \
        and evs_drop[0]['reason'] == 'transition_component_buy'
    # 放行集成员非 ④ 买因(常规 engine 通道)→ 仍报
    plain_buy = {'__type__': 'BuyCard',
                 'card': {'name': '姬子·启行', 'cost': 3},
                 'reason': 'd2_engine', 'channel': 'engine'}
    evs_non4 = seg_check_formed_still_buying_transition(
        _frame(plain_buy))
    assert evs_non4 and evs_non4[0]['bought'] == '姬子·启行' \
        and evs_non4[0]['reason'] == 'd2_engine'


def test_seg_overflow_idle_spend_bidirectional() -> None:
    """[17] 溢余即花(P1 段级)双向锁。前身 = 同名锁,原在
    test_cw_sim_suite.py,2026-09-09 测试重组批(f799914)申报性退役,
    T-196 回补至本主题文件(回潮期间该检查器无任何具名锁看守)。

    出处 = user_playstyle.md [17] + ADR-0478(容忍带)+
    ADR-0593 §C5(T-153 迁移:自报停手豁免降级为「自算成型复核通过
    才豁免」,谎报带 suspect 标记)。断言按现行检查器语义重推:
    - 金线与容忍带从单一源现算(interest_floor() = interest_cap×10
      + segments._OVERFLOW_TOLERANCE),不硬编码退役锁时代的 50/52;
    - 成型判据 = engines_count≥2 单一源(夹具 _seg_formed_state);
    - 谎报面断言 suspect 标记在事件上(非旧「自报即豁免」语义);
    - 批版同门检查(check_overflow_gold_zero_buy_streak)的 C5-b 面
      归 test_cw_suspect_review.py,本锁只辖段级版。
    """
    from sr_od.application.currency_war.kernel.cw_registry import (
        DEFAULT_REGISTRY,
    )
    from sr_od.application.currency_war.sim.checks import segments
    floor = DEFAULT_REGISTRY.interest_floor()
    band_top = floor + segments._OVERFLOW_TOLERANCE
    unformed = {'board_factions': {}, 'deployed': [], 'bench': [],
                'cap': 3, 'level': 3}
    # 坏:金>带顶 零花费 未成型 → 必报,事件带时点金与成型度回显
    bad = [_seg_row(1, gold=band_top + 5, waves_gold=band_top + 5,
                    state=dict(unformed))]
    evs = segments.seg_check_overflow_idle_spend(bad)
    assert evs and evs[0]['gold_before'] == band_top + 5 \
        and evs[0]['engines'] == 0, f'[17] 零花费未成型未报: {evs}'
    # 有花费动作 → 不报(时点金取首波,末金无关)
    spent = [_seg_row(1, gold=floor - 2, waves_gold=band_top + 5,
                      state=dict(unformed), actions=[_seg_buy('甲')])]
    assert not segments.seg_check_overflow_idle_spend(spent)
    # 自算成型(engines≥2)→ 攒息合法面,不报
    formed_ok = [_seg_row(1, gold=band_top + 20, waves_gold=band_top + 20,
                          state=_seg_formed_state())]
    assert not segments.seg_check_overflow_idle_spend(formed_ok)
    # 成型谎报(自报停手 ∧ 自算未成型)→ 不豁免 + suspect 标记
    # (ADR-0593 C5:旧「自报即豁免」下谎报形态不可见)
    lie = [_seg_row(1, gold=band_top + 20, waves_gold=band_top + 20,
                    formed_stop=True)]
    lie_evs = segments.seg_check_overflow_idle_spend(lie)
    assert lie_evs and lie_evs[0].get('suspect'), \
        '成型谎报未显形(C5 迁移回归)'
    # 自洽停手(自报停手 ∧ 自算成型)→ 豁免照旧(兼容面)
    honest = [_seg_row(1, gold=band_top + 20, waves_gold=band_top + 20,
                       state=_seg_formed_state(), formed_stop=True)]
    assert not segments.seg_check_overflow_idle_spend(honest)
    # bench 满守卫拦截轮(想买买不了)→ 豁免
    guard = [_seg_row(1, gold=band_top + 5, waves_gold=band_top + 5,
                      bench_full_skipped_buys=2)]
    assert not segments.seg_check_overflow_idle_spend(guard)
    # 息线邻近容忍带(ADR-0478):带顶(≤floor+容忍)不报,带顶+1 起报
    assert not segments.seg_check_overflow_idle_spend(
        [_seg_row(1, gold=band_top, waves_gold=band_top)])
    evs_far = segments.seg_check_overflow_idle_spend(
        [_seg_row(1, gold=band_top + 1, waves_gold=band_top + 1)])
    assert evs_far and evs_far[0]['gold_before'] == band_top + 1, \
        '容忍带边界失守:带顶+1 未报'


def test_seg_p2_bleed_gold_stack_bidirectional() -> None:
    """[17] 位面2 延伸(血线下降段金堆积,ADR-0479)豁免/边界面双向锁。
    前身 = 同名锁(test_cw_sim_suite.py,f799914 申报性退役),T-196 回补。

    分工申报:「溢余∧血降∧≥2 连」报红面、「血线稳定不报」对偶门、
    轮定位与 _SEGMENT_CHECKS 登记在场,已由接线验收锚辖
    (test_cw_telemetry_archive.py::test_p2_bleed_gold_stack_wired /
    _healthy_not_fired,经 run_checks_on_replay 生产 checks 路径)。
    本锁补接线锚不辖的独家豁免面:金在泄/单轮堆积被打断/P1 行不辖/
    容忍带内/金不可读断链(None 与 gold_readable=False 两形态,后者为
    现行检查器「不可信金不猜」新增口径)。
    溢余线从单一源现算(interest_floor() + _OVERFLOW_TOLERANCE)。
    """
    from sr_od.application.currency_war.kernel.cw_registry import (
        DEFAULT_REGISTRY,
    )
    from sr_od.application.currency_war.sim.checks import segments
    floor = DEFAULT_REGISTRY.interest_floor()
    band_top = floor + segments._OVERFLOW_TOLERANCE
    over = band_top + 8   # 溢余在手基准金(>带顶)
    # 金在泄(买入支出盖过收入,溢余在消化)→ 不报
    draining = [_seg_row(1, plane=2, gold=over, hp=50),
                _seg_row(2, plane=2, gold=over - 5, hp=35)]
    assert not segments.seg_check_p2_bleed_gold_stack(draining)
    # 单轮堆积即被非溢余轮打断(灰区)→ 不报
    single = [_seg_row(1, plane=2, gold=over, hp=50),
              _seg_row(2, plane=2, gold=over + 5, hp=45),
              _seg_row(3, plane=2, gold=floor, hp=40)]
    assert not segments.seg_check_p2_bleed_gold_stack(single)
    # P1 行不辖([17] P1 面归 seg_overflow_idle_spend)
    p1 = [_seg_row(1, gold=over, hp=50),
          _seg_row(2, gold=over + 10, hp=35)]
    assert not segments.seg_check_p2_bleed_gold_stack(p1)
    # 容忍带内(g ≤ floor+容忍,ADR-0478 同带宽)→ 不报
    band = [_seg_row(1, plane=2, gold=over, hp=50),
            _seg_row(2, plane=2, gold=band_top, hp=35)]
    assert not segments.seg_check_p2_bleed_gold_stack(band)
    # 金不可读帧断链(不可信金不猜):gold=None 断 streak 链
    broken = [_seg_row(1, plane=2, gold=over, hp=50),
              _seg_row(2, plane=2, gold=None, hp=35),
              _seg_row(3, plane=2, gold=over + 10, hp=20)]
    assert not segments.seg_check_p2_bleed_gold_stack(broken)
    # gold_readable=False 帧断链(现行口径;实机沿用值帧的检查侧镜像)
    unread = [_seg_row(1, plane=2, gold=over, hp=50),
              _seg_row(2, plane=2, gold=over + 10, hp=35,
                       gold_readable=False),
              _seg_row(3, plane=2, gold=over + 20, hp=20)]
    assert not segments.seg_check_p2_bleed_gold_stack(unread)


def test_seg_break_interest_exception_bidirectional() -> None:
    """[6]/[19] 破息例外记账(P1 段级)双向锁。前身 = 同名锁
    (test_cw_sim_suite.py,f799914 申报性退役),T-196 回补。

    出处 = user_playstyle.md [6][19] + ADR-0471/ADR-0580(③奖励节点
    型豁免已退役,升级破息豁免依据 = ④ levelup_spend 通道口径,节点
    无关)+ ADR-0478(boss 窗地板)。断言按现行检查器语义重推:
    - [19] 连胜保 = 进轮重算连胜 ≥2(_combat_streak_by_round 单一源:
      战斗类节点 delta≥0 累积,夹具 battle 行缺 delta = 0 = 胜);
    - ⑤ 刷新找牌通道放行面为现行在册通道,退役锁尚无此面,按现行
      意图补断言;
    - boss 地板与金线从注册表现算(boss_floor / interest_floor()),
      不硬编码退役锁时代的 10/50。
    """
    from sr_od.application.currency_war.kernel.cw_registry import (
        DEFAULT_REGISTRY,
    )
    from sr_od.application.currency_war.sim.checks import segments
    floor = DEFAULT_REGISTRY.interest_floor()
    g0 = floor + 5
    gend = floor - 10
    lv_spend = {'buys': {}, 'levelup': 4, 'refresh': 0, 'sell_income': 0}
    rf_spend = {'buys': {}, 'levelup': 0, 'refresh': 2, 'sell_income': 0}
    off_spend = {'buys': {'d2_off': 15}, 'levelup': 0, 'refresh': 0,
                 'sell_income': 0}
    # 坏:破息买 1 笔 off、无连胜、战斗节点 → 必报,事件回显
    # 时点金/买入通道/最终店面板三件
    bad = [_seg_row(1, gold=gend, waves_gold=g0,
                    actions=[_seg_buy('杂件', cost=15, channel='off')],
                    sim_extra={'spend': dict(off_spend)})]
    evs = segments.seg_check_break_interest_exception(bad)
    assert evs and evs[0]['gold_before'] == g0 \
        and evs[0]['buys'][0]['channel'] == 'off' \
        and isinstance(evs[0]['final_shop_panel'], list), \
        f'[6] 凭空破息未报或回显缺失: {evs}'
    # 例外①店全想要(≥2 笔无一 off)→ 放行
    store_all = [_seg_row(1, gold=gend, waves_gold=g0,
                          actions=[_seg_buy('引擎件'),
                                   _seg_buy('凑对件', channel='pair')])]
    assert not segments.seg_check_break_interest_exception(store_all)
    # 例外②连胜保([19]):前两轮战斗胜(进轮重算 ≥2)→ 放行
    streak_rows = [
        _seg_row(1, gold=floor + 2, waves_gold=floor + 2),
        _seg_row(2, gold=floor + 4, waves_gold=floor + 4),
        _seg_row(3, gold=gend, waves_gold=floor + 8,
                 actions=[_seg_buy('保连件', channel='pair')]),
    ]
    assert not segments.seg_check_break_interest_exception(streak_rows)
    # 例外④追级经验通道:奖励帧 LevelUp 由 levelup_spend 通道豁免
    # (ADR-0580:节点型豁免已退役,豁免依据是通道不是节点)
    reward_lv = [_seg_row(1, gold=gend, waves_gold=floor + 2,
                          node='reward',
                          actions=[{'__type__': 'LevelUp', 'cost': 4}],
                          sim_extra={'spend': dict(lv_spend)})]
    assert not segments.seg_check_break_interest_exception(reward_lv)
    # 例外⑤刷新找牌通道(spend.refresh>0,[3] 预算式授权)→ 放行
    refresh_row = [_seg_row(1, gold=gend, waves_gold=g0,
                            actions=[{'__type__': 'RefreshShop',
                                      'cost': 2}],
                            sim_extra={'spend': dict(rf_spend)})]
    assert not segments.seg_check_break_interest_exception(refresh_row)
    # 非破息(gold_end ≥ floor 或起点 < floor)不管
    calm = [_seg_row(1, gold=floor + 1, waves_gold=floor + 2,
                     actions=[_seg_buy('甲')])]
    assert not segments.seg_check_break_interest_exception(calm)
    # 例外⑥boss 窗地板(ADR-0478):花后 ≥ boss_floor → 豁免
    boss_floor = DEFAULT_REGISTRY.boss_floor
    boss_ok = [_seg_row(1, gold=boss_floor + 2, waves_gold=floor + 1,
                        node='boss',
                        actions=[_seg_buy('线核件', cost=3,
                                          channel='engine')])]
    assert not segments.seg_check_break_interest_exception(boss_ok)
    # 跌破 boss_floor → 越权仍报(detail 带越权标注)
    boss_breach = [_seg_row(1, gold=boss_floor - 4, waves_gold=floor + 1,
                            node='boss',
                            actions=[_seg_buy('线核件', cost=45,
                                              channel='engine')])]
    evs_boss = segments.seg_check_break_interest_exception(boss_breach)
    assert evs_boss and '越权' in evs_boss[0]['detail'], \
        f'boss 窗跌破地板未报越权: {evs_boss}'


def test_seg_formed_still_buying_transition_bidirectional() -> None:
    """[13] 成型停手主条(P1 段级)双向锁。前身 = 同名锁
    (test_cw_sim_suite.py,f799914 申报性退役;T-192 申报主条无现役
    承接并移交本批),T-196 回补。

    与本文件 ④ 放行臂锁的分工:那边辖例外臂双闸(放行集成员资格闸/
    买因闸),这边辖主条四形态——成型后过渡填充件必报、未成型阶段
    同类买入不报、同名在场再买 = 升星副本路径豁免([4] 核心 2★/
    [28] 过渡核心升星)、目标件买入豁免(bridge 框架件名册真实成员;
    target_comp 为空时 bridge 白名单兜底,与检查器 _is_target_piece
    同口径)。成型判据 = engines_count≥2 单一源
    (board_factions 经 cw_deploy_logic.engines_count,夹具
    _seg_formed_state);成型判定逐行先更新后检查,行 2 落成型后辖域。
    """
    from sr_od.application.currency_war.kernel.cw_line_defs import (
        BRIDGE_POOL,
    )
    from sr_od.application.currency_war.sim.checks.segments import (
        seg_check_formed_still_buying_transition,
    )
    formed = _seg_formed_state()
    unformed = {'board_factions': {}, 'deployed': [], 'bench': [],
                'cap': 3, 'level': 3}
    # 坏:成型后新增过渡填充件(engine 通道)→ 必报,回显轮号与件名
    bad = [_seg_row(1, state=dict(formed)),
           _seg_row(2, gold=30, waves_gold=30, state=dict(formed),
                    actions=[_seg_buy('散装过渡件')])]
    evs = seg_check_formed_still_buying_transition(bad)
    assert evs and evs[0]['round_num'] == 2 \
        and evs[0]['bought'] == '散装过渡件', \
        f'[13] 成型后买过渡件未报: {evs}'
    # 未成型阶段的同类买入 → 不报
    early = [_seg_row(1, gold=30, waves_gold=30, state=dict(unformed),
                      actions=[_seg_buy('散装过渡件')])]
    assert not seg_check_formed_still_buying_transition(early)
    # 同名在场再买 = 升星副本路径([4]/[28]) → 豁免
    dup_state = dict(formed)
    dup_state['deployed'] = [{'char_id': '散装过渡件'}]
    dup = [_seg_row(1, state=dict(formed)),
           _seg_row(2, gold=30, waves_gold=30, state=dup_state,
                    actions=[_seg_buy('散装过渡件')])]
    assert not seg_check_formed_still_buying_transition(dup)
    # 目标件买入(bridge 名册内真实成员)→ 豁免
    bridge_member = next(iter({n for combo in BRIDGE_POOL
                               for n in (*combo.fixed, *combo.core)}))
    target = [_seg_row(1, state=dict(formed)),
              _seg_row(2, gold=30, waves_gold=30, state=dict(formed),
                       actions=[_seg_buy(bridge_member)])]
    assert not seg_check_formed_still_buying_transition(target)


def test_seg_unjustified_levelup_bidirectional() -> None:
    """[12]/[33] 凭空追级(P1 段级)双向锁——与在册承接面分工申报:
    授权白名单 m3_batch 分键前缀放行与白名单外计数,由
    test_cw_auth_crossface.py(ledger 批表/segments 段表两侧镜像)辖;
    T-153 前置自算复核的 suspect 标记与金门辖域,由
    test_cw_suspect_review.py::test_c2b_seg_unjustified_review_event 辖。
    本锁补退役锁(f799914 申报性退役,T-196 回补)的其余独家面:
    - 基础违规事件字段回显(level_before/gold_before,段级归因现场);
    - 奖励帧两形态(T-115 对齐 ADR-0580:节点型豁免已退役,授权判定
      节点无关——奖励帧无授权升级 = 违规可见;白名单授权照常放行,
      m3_batch 分键经前置复核 unverifiable 豁免口径)。
    金门从单一源现算(interest_floor()),禁硬编码阈数字(同 C2-b
    红证口径)。
    """
    from sr_od.application.currency_war.kernel.cw_registry import (
        DEFAULT_REGISTRY,
    )
    from sr_od.application.currency_war.sim.checks.segments import (
        seg_check_unjustified_levelup,
    )
    floor = DEFAULT_REGISTRY.interest_floor()
    g0 = floor - 22
    pre = {'board_factions': {}, 'deployed': [], 'bench': [],
           'cap': 5, 'level': 5}
    post = {**pre, 'level': 6}

    def _lv_frame(node: str, auth: str) -> list[dict]:
        return [_seg_row(1, state=dict(pre)),
                _seg_row(2, gold=g0, waves_gold=g0, node=node,
                         state=dict(post),
                         actions=[{'__type__': 'LevelUp', 'cost': 4,
                                   'auth': auth}])]

    # 坏:lv≥5 进追级段、金<金门、无授权 → 必报,回显前轮等级与时点金
    evs = seg_check_unjustified_levelup(_lv_frame('battle', ''))
    assert evs and evs[0]['level_before'] == 5 \
        and evs[0]['gold_before'] == g0, \
        f'[12] 凭空追级未报或回显缺失: {evs}'
    # 奖励帧无授权升级 → 违规可见(节点不再是豁免依据,ADR-0580)
    evs_r = seg_check_unjustified_levelup(_lv_frame('reward', ''))
    assert len(evs_r) == 1 and evs_r[0]['round_num'] == 2, \
        f'奖励帧无授权升级漏报(T-115 回归): {evs_r}'
    # 奖励帧带白名单授权(m3_batch 分键,前置复核 unverifiable 豁免)
    # → 放行
    assert not seg_check_unjustified_levelup(
        _lv_frame('reward', 'm3_batch:arm1'))


def test_seg_gold_identity_bidirectional() -> None:
    """链式金恒等式(段级实现层探针)双向锁。前身 = 同名锁
    (test_cw_sim_suite.py,f799914 申报性退役),T-196 回补。

    与 ledger.check_ledger_consistency(行内 gold_before 单行自洽,
    锁见本文件批检查器小节之外的历史分工声明)的分工:本检查用
    **链式上一行末金**——跨行的记账断裂(轮间丢一笔/收入重复入账)
    只有链式才能暴露。夹具收入合计 = 6(base 5 + event 1),期望金
    从收入/支出现算,不硬编码;违规事件 detail 必须携带末金读数供
    定位(回显契约)。
    """
    from sr_od.application.currency_war.sim.checks import segments
    # 守恒链(6 + 6 = 12)→ 零事件
    good = [_seg_row(1, gold=6), _seg_row(2, gold=12)]
    assert not segments.seg_check_gold_identity(good)
    # 改一行末金 → 必报,detail 带末金读数
    bad = [_seg_row(1, gold=6), _seg_row(2, gold=99)]
    evs = segments.seg_check_gold_identity(bad)
    assert evs and '99' in evs[0]['detail'], \
        f'链式金不守恒未报或回显缺失: {evs}'


# --- 注册表类 --------------------------------------------------------

def test_phantom_equip_no_wear_bidirectional() -> None:
    bad = [_row(equipped=[{'char': 'x', 'equip': '钻石(幻影)'}])]
    assert ledger.check_phantom_equip_no_wear(bad), '幻影装备未报'
    real = next(iter(
        __import__(
            'sr_od.application.currency_war.data.cw_equipment_data',
            fromlist=['EQUIPMENT_ROSTER']).EQUIPMENT_ROSTER))
    good = [_row(equipped=[{'char': 'x', 'equip': real}])]
    assert not ledger.check_phantom_equip_no_wear(good)


# --- 线/供给类 --------------------------------------------------------
# (v1 线库语义检查器族随 ADR-0336 删除、双向锁同步删;余下
# degrade_recover_mutex 为通用 target 切换检查)

# --- 批级聚合披露 ----------------------------------------------------

def test_shop_cost_conformance_bidirectional() -> None:
    # 坏:lv9(level 表 p4=0.30)零 4 费供给,200+ 抽全 1 费
    waves = [{'gold': 50,
              'cards': [{'name': f'c{i}', 'cost': 1, 'faction': 'x'}
                        for i in range(5)]} for _ in range(45)]
    sim = {'node': 'battle', 'merges': 0, 'shop_waves': waves}
    bad = [_row(rn=9, level=9, sim=dict(sim))]
    r = runtime.check_shop_cost_conformance([bad])
    assert r['violations'] >= 1, 'lv9 4费零供给未报'
    # 好:lv3 全 1 费(REFRESH_PROB lv3={1:1.0})
    r2 = runtime.check_shop_cost_conformance(
        [[_row(rn=3, level=3, sim=dict(sim))]])
    assert r2['violations'] == 0


def test_second_engine_deadline_form_split() -> None:
    """second_engine_deadline 形态分键锁:「从未出第二引擎」与「第二
    引擎延迟」两形态各自命中自己的键,互斥且并集完备。

    键语义 = 泛找批报告 F2 的区分定义(报告路径易失产物暂记:
    .debug/temp/currency_war/findprob_20260910_泛找批_20260910_062008/
    report.md):never = 首引擎后至局终仍未凑出次引擎(gap=99 哨兵;
    结构问题形态);delayed = 限期窗(首引擎 F 后 ≤3 轮)过后以
    有限轮差达成(gap>3 且有限;节奏问题形态)。病灶背景:99 缺省进
    avg_gap 混合均值,「从未变多」与「延迟变长」在均值上不可分,
    掩蔽归因——分键即解,avg_gap 旧混合口径零漂移(报告连续性锚,
    语义变更须先重推本锚而非机械跟绿)。分键为归因观测面,零判定
    阈值/零策略行为变更。前身注:CUT6 预算批砍过 T-179 期限 miss
    分键锁(诊断披露工具口径);本锁为形态分键行为锁,合成夹具零
    sim 运行(预算档 <0.5s)。
    """
    e1 = {'仙舟': 3}                  # 一体系达成 = 首引擎(_rung_of_row=1)
    e2 = {'仙舟': 3, '列车同行': 2}   # 两体系达成 = 次引擎(_rung_of_row=2)

    # 形态一(从未):首引擎后再无次引擎直至局终
    never = [[_row(rn=rn, bf=e1) for rn in range(1, 10)]]
    r = runtime.check_second_engine_deadline(never)
    assert r['never_second_engine'] == 1, r
    assert r['never_games'] == [0], r
    assert r['delayed_miss'] == 0 and r['delayed_avg_gap'] is None, r
    assert r['deadline_miss'] == 1, r

    # 形态二(延迟):限期窗后有限轮差达成(gap=4>3)
    delayed = [[_row(rn=1, bf=e1), _row(rn=5, bf=e2)]]
    r2 = runtime.check_second_engine_deadline(delayed)
    assert r2['delayed_miss'] == 1 and r2['delayed_avg_gap'] == 4.0, r2
    assert r2['never_second_engine'] == 0 and r2['never_games'] == [], r2

    # 互斥完备:混合批 never+delayed == deadline_miss;finite 均值
    # 不被 99 缺省稀释(delayed_avg_gap=4.0 ≠ 混合 51.5)
    mixed = never + delayed
    r3 = runtime.check_second_engine_deadline(mixed)
    assert r3['never_second_engine'] + r3['delayed_miss'] \
        == r3['deadline_miss'] == 2, r3
    assert r3['delayed_avg_gap'] == 4.0, r3
    assert r3['avg_gap'] == 51.5, r3   # 旧键连续性:混合均值含 99 哨兵

    # 负空间:限期窗内达成(gap≤3)与无首引擎局,两形态都不计
    fast = [[_row(rn=1, bf=e1), _row(rn=3, bf=e2)]]
    r4 = runtime.check_second_engine_deadline(fast)
    assert r4['never_second_engine'] == 0 \
        and r4['delayed_miss'] == 0 and r4['deadline_miss'] == 0, r4
    nofirst = [[_row(rn=rn) for rn in range(1, 5)]]
    r5 = runtime.check_second_engine_deadline(nofirst)
    assert r5['never_second_engine'] == 0 and r5['delayed_miss'] == 0 \
        and r5['first_engine_games'] == 0, r5

    # 接线烟雾:分键经批聚合出口在场(run_batch_level_checks;消费面
    # = 批报告 checks 段——检查器家族在场烟雾档,至多 1 条纪律)
    s = runner.run_batch_level_checks(mixed)['second_engine_deadline']
    assert s['never_second_engine'] == 1 and s['delayed_miss'] == 1, s


def test_second_engine_deadline_game_end_caliber() -> None:
    """second_engine_deadline 口径声明锁(键↔口径绑定;ADR-0629)。

    口径 = 局终(全账本 P1+P2):「首引擎后至局终仍未凑出次引擎」
    的局终是模拟局真实末轮,而 P2 转型期正是二引擎形成窗;T-211
    归因实锤 P1 段截断口径把 P2 内形成的二引擎记成 never(冻结
    s8550 批:截断 21 vs 全局面 15,「never 21 超带」假警报直接
    成因)。本锁钉两处回退形态:
    ①检查器轴回退——跨段 gap/期限窗用统一局轮轴 ts(P2 round_num
      段内重计 1..7,直接做差会在位面边界回卷/负 gap);
    ②批接线回退——run_batch_level_checks 若把「局终」检查退回
      P1 段视图喂入(full_ledgers 缺席回退 ledgers 对纯 P1 批零
      漂移属合法;对 planes>=2 批则是口径静默截断),③发变红。
    冻结账本实证锚(.debug/temp/currency_war/validate_t212.py 可
    复跑):七批全局面 never 序列 2/0/1/11/12/12/15、P1 截断 3/0/
    1/22/24/20/21,与 T-211 归因批 §2 直算表逐位一致;s8350 冻结↔
    收窄重放配对在局终口径下零翻转保持(never 12→12/delayed 45
    →45),配对结论跨口径换算不失效。
    """
    e1 = {'仙舟': 3}
    e2 = {'仙舟': 3, '列车同行': 2}

    def p1_row(rn: int, bf: dict | None = None) -> dict:
        r = _row(rn=rn, bf=bf)
        r['ts'] = rn            # 账本行写入端语义:P1 段 ts == rn
        return r

    def p2_row(rn: int, bf: dict | None = None) -> dict:
        r = _row(rn=rn, bf=bf)
        r['plane'] = 2
        r['ts'] = 9 + rn        # P2 首轮 ts=10(_Plane1View 切片注释同源)
        return r

    # ① 局终口径:次引擎在 P2 形成 → 不再记 never,按统一轴算 delayed
    #    (首引擎 P1r2,P2r2 = 轴 11 → gap 9 >3)
    game = [p1_row(rn, e1) for rn in range(2, 10)] + [p2_row(2, e2)]
    r = runtime.check_second_engine_deadline([game])
    assert r['never_second_engine'] == 0, r
    assert r['delayed_miss'] == 1 and r['delayed_avg_gap'] == 9.0, r
    assert '局终口径' in (r['caliber_note'] or ''), r   # 输出自描述口径

    # ② 位面边界期限窗:首引擎 P1r8 → 窗 = ts(8,11] 跨 P1r9+P2r1;
    #    P2r1 达成 = gap 2 ≤3,不计 miss(轴回卷回归即此发变红)
    edge = [p1_row(8, e1), p1_row(9, e1), p2_row(1, e2)]
    r2 = runtime.check_second_engine_deadline([edge])
    assert r2['deadline_miss'] == 0 and r2['never_second_engine'] == 0, r2

    # ③ 批接线:full_ledgers 携带全量账本 → 局终口径穿透批出口;
    #    接线回退成 P1 段视图喂入时,同一批的 never 翻成 1 → 红
    p1_views = [[row for row in game if row['plane'] == 1]]
    s = runner.run_batch_level_checks(
        p1_views, full_ledgers=[game])['second_engine_deadline']
    assert s['never_second_engine'] == 0 and s['delayed_miss'] == 1, s

    # ④ planes=1 零漂移锚:纯 P1 账本带/缺 ts 输出逐键相同
    #    (回退轴 rn 恒等 ts)——历史批与既有形态分键锁的连续性依据
    pure = [p1_row(rn, e1) for rn in range(1, 6)] + [p1_row(6, e2)]
    no_ts = [{k: v for k, v in row.items() if k != 'ts'} for row in pure]
    a = runtime.check_second_engine_deadline([pure])
    b = runtime.check_second_engine_deadline([no_ts])
    for k in ('first_engine_games', 'deadline_miss', 'never_second_engine',
              'never_games', 'delayed_miss', 'delayed_avg_gap', 'avg_gap',
              'miss_reasons'):
        assert a[k] == b[k], (k, a[k], b[k])


# --- 语料级 -----------------------------------------------------------

def test_attach_run_detector_bidirectional() -> None:
    bad = [{'run_id': 'r1', 'plane': 1, 'round_num': 5}]
    assert runtime.check_attach_run_detector(bad), '接管段未标'
    good = [{'run_id': 'r2', 'plane': 1, 'round_num': 1},
            {'run_id': 'r2', 'plane': 1, 'round_num': 2}]
    assert not runtime.check_attach_run_detector(good)


def test_hp_monotonic_sentinel_bidirectional() -> None:
    bad = [{'run_id': 'r1', 'hp_after': 70},
           {'run_id': 'r1', 'hp_after': 100}]
    assert runtime.check_hp_monotonic_sentinel(bad), 'hp 上升未报'
    good = [{'run_id': 'r1', 'hp_after': 70},
            {'run_id': 'r1', 'hp_after': 60}]
    assert not runtime.check_hp_monotonic_sentinel(good)


def test_plane_reached_consistency_bidirectional() -> None:
    bad_summary = {'run_id': 'r1', 'plane_reached': 3}
    outcomes = [{'run_id': 'r1', 'plane': 2}]
    assert runtime.check_plane_reached_consistency(
        bad_summary, outcomes), 'summary/outcomes 不一致未报'
    ok = {'run_id': 'r1', 'plane_reached': 2}
    assert not runtime.check_plane_reached_consistency(ok, outcomes)


# --- 批量集登记门(检查器家族在场烟雾,至多 1 条) ----------------------

def test_new_checks_in_batch_set() -> None:
    """清偿批逐局锁进批量集(sim 批次自动扫;ADR-0289)。
    (v1 线库语义检查器随 ADR-0336 删除;degrade_recover_mutex 保留)"""
    for name in ('gold_nonneg', 'bench_capacity',
                 'deployed_schema_filter', 'engine_seed_not_resold',
                 'buys_at_full_bench', 'oscillation_xp_cap',
                 'levelup_flat4_lock', 'phantom_equip_no_wear',
                 'degrade_recover_mutex'):
        assert name in runner._BATCH_CHECKS, name


# ==================== cw_evolution 引擎补完通道(ADR-0371) ====================


def _char(name: str, star: int = 1, row: str = 'back') -> BenchChar:
    c = CHARACTERS[name]
    return BenchChar(slot=0, char_id=name,
                     faction=(c.factions or ['?'])[0],
                     position_pref=row, star=star)


def _sess(pair: tuple[str, ...]) -> StrategySession:
    """p1_pair 配方锁定帧的 session(v3_intention 挂体系对)。"""
    sess = StrategySession()
    state_of(sess).v3_intention = IntentionState(p1_pair=pair)
    return sess


# run42 型(run42 复盘:手握 4 种列车件只上 1):deployed 7 件全为
# 非引擎散件(无 仙舟/持续伤害/列车同行 羁绊),cap 满;bench 4 件列车。
_B_FILLER = ('银枝', '刃', '镜流', '布洛妮娅', '阮·梅', '娜塔莎', '翡翠')
_B_TRAIN = ('丹恒·饮月', '姬子·启行', '姬子', '星期日')


def _state(bench=(), deployed=(), level: int = 7,
           round_num: int = 4) -> GameState:
    st = GameState()
    st.plane = 1
    st.round_num = round_num
    st.level = level
    st.gold = 30
    st.bench = list(bench)
    # 排位平衡:前 3 后 4(front_max=4/back_max=6,守终态排不变量)
    st.deployed = [(_char(n, row='front') if i < 3 else _char(n))
                   for i, n in enumerate(deployed)]
    st.board = _recount_board(st.deployed)
    return st


def _t42_frame() -> GameState:
    """列车 owned 4 ≥2 ∧ 上场 0;deployed 7 件非引擎散件占满 cap。"""
    return _state(bench=[_char(n) for n in _B_TRAIN],
                  deployed=_B_FILLER)


def _completion_txs(actions: list) -> list[CompTransaction]:
    return [a for a in actions if isinstance(a, CompTransaction)
            and 'engine_complete' in (a.reason or '')]


def test_completion_tx_deploys_owned_engine_members():
    """①缺口帧:cap 满局手握≥门槛体系件 → 补完事务换上场(run42 型)。"""
    st = _t42_frame()
    sess = _sess(('列车同行', '仙舟'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert len(txs) == 1
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    # 列车同行 on-board 达门槛(≥2):拥有已够 → 上场补完
    assert _board_factions_of(out.deployed).get('列车同行', 0) >= 2


def test_completion_protects_engine_and_pair_pieces():
    """②保护序:undeploy 只吃非保护散件——pair/引擎贡献件不下场
   (deployed 掺一件仙舟引擎件符玄,保护集辖,不被换下)。"""
    st = _state(bench=[_char(n) for n in _B_TRAIN],
                deployed=(*_B_FILLER[:6], '符玄'))
    sess = _sess(('列车同行', '仙舟'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert txs, '缺口仍在(列车 owned≥2 上场 0)应发补完事务'
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied'
    # 仙舟引擎件(符玄)不被换下;下的全是非保护散件
    assert '符玄' in {d.char_id for d in out.deployed if d is not None}   # ADR-0392
    downed = {st.deployed[i].char_id for i in (txs[0].undeploy or [])}
    assert downed <= set(_B_FILLER)


def test_completion_no_gap_no_tx():
    """③无缺口不发射:owned≥tier∧已上场够 / owned<tier → 无补完事务
   (获取问题不辖——本批边界,归 早期买入门)。"""
    # 已成帧:仙舟 3 上场 + 列车 2 上场 → 无缺口
    st = _state(
        deployed=('丹恒·饮月', '符玄', '藿藿', '姬子·启行', '姬子'),
        bench=(_char('桑博'), _char('卡芙卡')), level=5)
    sess = _sess(('仙舟', '列车同行'))
    assert not _completion_txs(evolution_step(st, sess, EvolutionState()))
    # owned<tier:仙舟仅 1 件在手
    st2 = _state(deployed=('姬子·启行', '姬子'), bench=(_char('藿藿'),),
                 level=5)
    sess2 = _sess(('仙舟', '列车同行'))
    assert not _completion_txs(evolution_step(st2, sess2, EvolutionState()))


def test_completion_frozen_on_encounter_node():
    """⑤b 遭遇/boss 冻结轮不启动补完(与既有演进纪律一致)。"""
    st = _t42_frame()
    st.node_type = 'boss'
    sess = _sess(('列车同行', '仙舟'))
    assert not _completion_txs(evolution_step(st, sess, EvolutionState()))


def test_completion_bench_overflow_sells_unprotected():
    """⑦bench 容量不足:undeploy 落位溢出 → 卖最弱非保护 bench 件腾位
   (保护件不受卖;卖的全是散件)。"""
    st = _t42_frame()
    # bench 塞满 9 槽:4 列车件 + 5 散件(非保护)
    filler = ('银枝', '刃', '镜流', '布洛妮娅', '娜塔莎')
    st.bench = [_char(n) for n in _B_TRAIN + filler]
    sess = _sess(('列车同行', '仙舟'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert txs, 'bench 满仍应有腾位补完(卖散件腾 bench)'
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    # 卖的全是非保护散件;列车件(保护)绝不被卖
    sold = {st.bench[i].char_id for i, src in (txs[0].sell or [])
            if src == 'bench'}
    assert sold <= set(filler)
    assert _board_factions_of(out.deployed).get('列车同行', 0) >= 2


class _LogRecorder:
    """记录 log.info 调用(观测行格式锁用;不触发真实日志链路)。"""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def info(self, msg: str, *args: object) -> None:
        self.lines.append(msg % args if args else msg)


# ==================== simulate_p1 补给两步链(sim 集成) ====================


def test_sim_supply_reroll_chain_and_once_per_game(monkeypatch) -> None:
    """两步链形态 + session 级只刷一次;评分分支(refresh_used=True)
    在 sim 可达——「恒 idx0」伪影回归锚(ADR-0394)。
    (可达性原为独立 12 种子扫描锁,断言面被本测链形态断言严格
    覆盖,已并入:链形态蕴含任意 refresh_used=True。)"""
    # 显式命中种子集(纪律 12 续:实测探底后固化,非命中种子不再付运行成本)。
    # 探针记录(2026-09-03,seed 0-11 逐局 spy 实测):9/12 出现两步链;
    # 取三形态代表——0=[F,T,T] 立即重掷 / 4=[F,F,T] 迟重掷 / 8=[F,F,T,T] 双掷。
    # 引擎改动若位移 RNG 消费致列表失准 → 本测试红,重跑探针更新列表(同校准锚责)。
    _REROLL_SEEDS = (0, 4, 8)
    # 每局的调用轨迹(seed → refresh_used 序列)
    traces: list[list[bool]] = []
    cur: list[bool] = []
    orig = cw_events.decide_supply

    def spy(options, state, target_comp, config, refresh_used=False):
        pick = orig(options, state, target_comp, config, refresh_used)
        cur.append(refresh_used)
        return pick

    monkeypatch.setattr(cw_events, 'decide_supply', spy)
    for seed in _REROLL_SEEDS:
        cur = []
        simulate_p1(seed, planes=2, pool='fallback')
        if cur:
            traces.append(cur)
    assert traces, '显式种子集全空轨迹(引擎 RNG 消费位移?)——重跑探针更新 _REROLL_SEEDS'
    # ② 两步链:某局出现 False…True 序列(首调触发刷新 → 重掷后评分)
    assert any(
        any(not t[i] and t[i + 1] for i in range(len(t) - 1))
        for t in traces), (
        f'无「首掷→重掷评分」两步链(修复前形态): {traces}')
    # ③ session 级一次:refresh_used=True 的调用只出现在轨迹尾部连续段
    #    (首掷 False 若干次 + 至多一段末尾 True)——更严的等价判据:
    #    True 出现后不再出现 False(标志置位后单调)
    for t in traces:
        seen_true = False
        for flag in t:
            if flag:
                seen_true = True
            assert not (seen_true and not flag), (
                f'refresh_used 标志回退(session 级一次被破坏): {t}')


# ==================== 标定口径与注册表登记门(承三小件) ====================
# (2026-09-09 合并批:原 test_cw_goldrich_rungstat / test_cw_boss_tax_p75_by_plane /
#  test_cw_streak_gold_table 按同性质并入——三件均为口径登记门/注册表级守卫,
#  与本文件既有 corpus/calib 锚登记段同性质;断言逐条原样迁移,零砍。)

# --- rung 统计口径(原 test_cw_goldrich_rungstat;ADR-0305 件2)---


def _fake_calib_res() -> SimpleNamespace:
    """最小 ledger/hp_events 载体:r1 仙舟1 → r2 仙舟3 → r4 双体系。"""
    return SimpleNamespace(
        ledger=[
            {'round_num': 1,
             'state': {'board_factions': {'仙舟': 1}, 'deployed': []}},
            {'round_num': 2,
             'state': {'board_factions': {'仙舟': 3}, 'deployed': []}},
            {'round_num': 3,
             'state': {'board_factions': {'仙舟': 3}, 'deployed': []}},
            {'round_num': 4, 'state': {
                'board_factions': {'仙舟': 3, '列车同行': 2},
                'deployed': []}},
        ],
        hp_events=[
            (1, 'battle', -5, False),
            (2, 'reward', 2, False),
            (3, 'encounter', -4, False),
            (4, 'boss', -8, False),
        ],
    )


def test_battles_before_e2_metric_semantics() -> None:
    """e2 首达 r4(仙舟3+列车2):此前战斗类 = r1 battle + r3 encounter
    = 2(r2 reward 不计;r4 当轮不计,< 严格)。

    锁定对象 = cw_battle_calib._battles_before_engines 的 rung 统计口径:
    首达 e2 前的战斗类结算计数,奖励不计;未达 e2 → None——0304
    「30 vs 10」未定义口径误读的防再犯。(件1 金充裕买偏置已被 A/B
    定谳否决,其锁随 ADR-0305 增补清理节删除,清理后语义守卫见
    test_cw_dead_arm_cleanup_locks.py。)"""
    res = _fake_calib_res()
    assert _first_engines_round(res, 2) == 4
    assert _battles_before_engines(res, 2) == 2


def test_battles_before_e2_none_when_never() -> None:
    """未达 e2 → None(与 _first_engines_round 同 None 语义;
    批报告均值只对达成局算)。"""
    res = _fake_calib_res()
    assert _first_engines_round(res, 3) is None
    assert _battles_before_engines(res, 3) is None


# --- boss 税标量墓碑(原 test_cw_boss_tax_p75_by_plane)---


def test_boss_tax_scalar_not_resurrected() -> None:
    """无消费者标量不复活锁:boss_tax_p75 已随旧方案清退批删除
    (清查报告 OLD_MIX_AUDIT §1.3);by_plane 是唯一取值口。

    值面由 test_cw_adr0293_calibration 面册逐值辖死(登记门:
    _EXPECTED_FIELDS['boss_tax_p75_by_plane'],增删改键值=红且点名
    字段);by_plane 结构预埋锚保留因锚组 boss_tax_anchor_group 仍是
    sim 标定接口。"""
    from dataclasses import fields

    from sr_od.application.currency_war.kernel.cw_registry import (
        DEFAULT_REGISTRY,
        DecisionV2Registry,
    )
    names = {f.name for f in fields(DecisionV2Registry)}
    assert 'boss_tax_p75' not in names
    assert not hasattr(DEFAULT_REGISTRY, 'boss_tax_p75')


# --- 连胜奖励表守卫(原 test_cw_streak_gold_table;r305 域)---


def test_streak_gold_table_constant() -> None:
    """ADR-0262:STREAK_GOLD_TABLE 常量与函数逐点一致守卫(防表与实现漂移)。"""
    from sr_od.application.currency_war.kernel.cw_economy import (
        STREAK_GOLD_TABLE,
    )
    for streak in range(0, len(STREAK_GOLD_TABLE) + 3):
        expected = STREAK_GOLD_TABLE[min(streak, len(STREAK_GOLD_TABLE) - 1)]
        assert streak_gold(streak) == expected, f'streak={streak}'


# ==================== cw_coarse_battle 战斗粗模型 ====================

# 拟合产物交付口径(逐单元;粗模型参数的机器可读真值,
# 来源 = 冻结语料拟合,禁与其它口径混写)
_DELIVERY_WIN_P: dict[str, dict[int, float]] = {
    'battle': {0: 0.009, 1: 0.356, 2: 0.315, 3: 0.292},
    'encounter': {0: 0.038, 1: 0.026, 2: 0.264, 3: 0.275},
    'boss': {0: 0.077, 1: 0.027, 2: 0.187, 3: 0.238},
}


# 位面维前 = 拟合交付值(F6 语料治理批重记:伪影档剔除后口径;
# 原值含结算瞬时 hp=0 伪读数拆出的 ±40 量级假档——对局档案真值
# 语料 tools/cw/proofs/p15/(P1 n=290)未删失最大单轮 |Δ|=36)
_DELIVERY_LOSS_HIST: dict[str, dict[int, int]] = {
    'battle': {1: 7, 3: 3, 4: 9, 5: 10, 6: 5, 7: 2, 8: 19, 9: 11,
               10: 6, 11: 18, 12: 6, 13: 74, 14: 1, 15: 9, 17: 3,
               18: 3, 19: 4, 20: 2, 21: 4, 23: 2},
    'encounter': {4: 1, 5: 1, 6: 4, 7: 1, 8: 4, 9: 7, 10: 10, 15: 1,
                  17: 1, 18: 1, 22: 1, 24: 11, 26: 7, 28: 15},
    'boss': {3: 1, 11: 2, 12: 1, 13: 2, 14: 4, 30: 1, 32: 5, 34: 11,
             36: 8},
}
# _LOSS_FIT 重拟合交付口径(dd-012:对局档案真值语料
# tools/cw/proofs/p15/ corpus_battle_loss.jsonl 逐行最小二乘,
# P1 非删失败局行 battle n=82 / encounter n=66;原值系已灭且污染
# 的 w324 语料回归值,锁改理由 = 拟合依据语料不得再为已灭污染源)
_DELIVERY_LOSS_FIT: dict[str, tuple[float, float, float]] = {
    'battle': (11.48, -4.21, 10.45),
    'encounter': (15.06, -3.27, 12.18),
}


class _ScriptRng:
    """脚本化 rng 桩:random() 返回定值;choices 返回定值档。"""

    def __init__(self, uniform: float, pick: int) -> None:
        self._uniform = uniform
        self._pick = pick

    def random(self) -> float:
        return self._uniform

    def choices(self, vals, weights=None, k: int = 1):  # type: ignore[no-untyped-def]
        return [self._pick]


def test_prior_share_hard_caps() -> None:
    """先验份额恒 ≤25%、等效样本恒 ≤12(裸收缩口径禁止)。"""
    for node in cb._WIN_TABLE:
        for rung in (2, 3):
            share = cb.prior_share(node, rung)
            assert 0.0 < share <= cb.PLAZA_SHARE_MAX + 1e-12
            n = cb._WIN_TABLE[node][1][rung][0]
            alpha = share * n / (1 - share)
            assert alpha <= cb.ALPHA_CAP + 1e-9
    # 值锁两例(份额帽在薄/厚单元的两个端型):
    assert cb.prior_share('battle', 2) == pytest.approx(0.203, abs=1e-3)
    assert cb.prior_share('battle', 3) == pytest.approx(0.25, abs=1e-9)


def test_loss_mean_match_and_floor() -> None:
    """败态:battle 直方采样 + rung 均值匹配取整;hp 地板 = max(1,·)。"""
    # rung0:13 + (11.48 − 0 − 10.45) = 14.03 → 14(dd-012 重拟合口径)
    assert cb.sample_battle_delta(
        'battle', 0, 100, _ScriptRng(0.99, 13)) == -14
    # rung3:13 + (11.48 − 12.63 − 10.45) = 1.4 → 1(取整后落伤害地板;
    # rung 梯度方向仍向下,但该档已被地板吸收)
    assert cb.sample_battle_delta(
        'battle', 3, 100, _ScriptRng(0.99, 13)) == -1
    # 地板:伤害越过 HP → hp_after 落吸收态 1(取真值支持域内上限档
    # 36——F6 剔档后直方无 84/88,原取值 = 伪影档)
    assert cb.sample_battle_delta(
        'battle', 0, 5, _ScriptRng(0.99, 36)) == -(5 - 1)
    # 直方支持域:采样结果必落在合法区间(固定种子扫 200 次)
    rng = random.Random(20260901)
    for _ in range(200):
        r = cb.sample_battle_delta('encounter', 1, 200, rng)
        assert r <= -1 or r == cb.WIN_CAP  # 败态伤害 / 胜态回血两态


def test_boss_clamp_conditional_on_hp_before() -> None:
    """boss 钳制按 hp_before 条件化:≤35 门 + 区间内 0.929;>35 不钳。"""
    # ≤35 且区间内抽中钳制 → 归吸收态(不经伤害直方/乘子)
    assert cb.sample_battle_delta(
        'boss', 1, 30, _ScriptRng(0.1, 36)) == -(30 - 1)
    # ≤35 但区间内抽中不钳 → 直方采样 + 地板兜底(结构性双路径)
    assert cb.sample_battle_delta(
        'boss', 1, 20, _ScriptRng(0.999, 14)) == -(20 - 6)
    # >35:钳制分支结构性不可达(即使钳制抽签必中)——0.929 只辖低 HP
    # (uniform 0.5 = 败态且 >35 门直接跳过钳制分支)
    assert cb.sample_battle_delta(
        'boss', 1, 40, _ScriptRng(0.5, 36)) == -36


def test_difficulty_multiplier_off_by_default() -> None:
    """难度乘子未核先验默认关闭:difficulty 取值不影响采样结果。"""
    rng_a = random.Random(7)
    rng_b = random.Random(7)
    for _ in range(50):
        a = cb.sample_battle_delta('boss', 2, 60, rng_a, difficulty=200)
        b = cb.sample_battle_delta('boss', 2, 60, rng_b, difficulty=None)
        assert a == b


def test_coarse_game_smoke_snapshot_fingerprint() -> None:
    """冒烟:coarse 模式整局可跑、hp 轨迹合法、池指纹照常随局携带
    (reward/supply 池消费与基准对拍依赖指纹披露)。"""
    r = cw_sim.simulate_p1(1, pool='snapshot')
    assert r.hp_trail
    assert all(0 <= h <= 100 for h in r.hp_trail)
    # 局指纹 = 池指纹 + 装备发放结构版本位(供给重校准起)
    assert r.pool_fingerprint == (
        sim_pool.pool_fingerprint(sim_pool.resolve_pool('snapshot')[0])
        + f'+eqg{cw_sim.EQUIP_GRANT_CALIB_VERSION}')


# ===== 位面维(P1 先行)锁:结构语义单一源 = cw_coarse_battle 模块头
# 「位面维(P1 先行)」节(P2 别名/口径声明在生产侧) =====


def test_p1_layer_zero_drift_literals() -> None:
    """P1 层逐位 = 拟合交付值(现口径 = F6 语料治理后)。

    位面化只加结构不改数:P1 层是 W346 一阶矩门 + W377 剂量曲线
    三方一致的载体,任何 P1 数值变动必须走显式重校准批(禁止顺手调)
    ——F6 语料治理批即该显式批:剔除结算瞬时 hp=0 伪影档(battle
    {±42,±43,−64,+46,+84,+88}/encounter {+45,+83};真值上限锚=
    tools/cw/proofs/p15/ 对局档案语料 P1 未删失最大单轮 |Δ|=36)。
    """
    for node, hist in _DELIVERY_LOSS_HIST.items():
        assert cb._LOSS_HIST[node][1] == hist
    for node, fit in _DELIVERY_LOSS_FIT.items():
        assert cb._LOSS_FIT[node][1] == fit
    for node, rungs in _DELIVERY_WIN_P.items():
        for rung, p in rungs.items():
            assert cb.injected_win_p(node, rung, plane=1) == \
                pytest.approx(p)


def test_p2_alias_lock() -> None:
    """P2 别名锁:别名表显式指向 plane 1,取表回同一对象(不拷贝)。

    P2 未采样,别名即「已知偏差」的机器可读声明(W357 regate:
    boss +4.57 hp / 钳制率 −38.81 pp / encounter 钳制率 −6.19 pp
    为继承的现状,非本结构引入);未来 P2 语料换表只动 plane 2 槽位。
    """
    assert set(cb._P2_ALIAS) == {'battle', 'encounter', 'boss'}
    for node, aliased in cb._P2_ALIAS.items():
        assert aliased == 1
        assert cb._node_table(cb._LOSS_HIST, node, 2) \
            is cb._LOSS_HIST[node][1]
        assert cb._node_table(cb._WIN_TABLE, node, 2) \
            is cb._WIN_TABLE[node][1]
    # _LOSS_FIT 无 boss 条目(斜率 CI 含 0 退常数,不做均值匹配),
    # 别名断言只辖 battle/encounter
    for node in ('battle', 'encounter'):
        assert cb._node_table(cb._LOSS_FIT, node, 2) \
            is cb._LOSS_FIT[node][1]
    # 钳制参数:P2 别名同值
    assert cb._boss_clamp_params(2) == cb._boss_clamp_params(1) \
        == (cb.BOSS_CLAMP_HP_CUT, cb.BOSS_CLAMP_P_LOW)
    # 未声明位面(如 3)按别名链落到 plane 1,不 KeyError
    assert cb._node_table(cb._LOSS_HIST, 'boss', 3) is cb._LOSS_HIST['boss'][1]
    # 行为面:同 seed 下 plane=2 与 plane=1 采样逐位一致
    for node in ('battle', 'encounter', 'boss'):
        rng_a = random.Random(11)
        rng_b = random.Random(11)
        for _ in range(30):
            a = cb.sample_battle_delta(node, 2, 60, rng_a, plane=1)
            b = cb.sample_battle_delta(node, 2, 60, rng_b, plane=2)
            assert a == b
        assert cb.injected_win_p(node, 2, plane=2) \
            == cb.injected_win_p(node, 2, plane=1)
        assert cb.prior_share(node, 2, plane=2) \
            == cb.prior_share(node, 2, plane=1)


def test_coarse_calib_version_disclosed_in_ledger_manifest(
        monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """版本披露锁:COARSE_CALIB_VERSION=4 且进 sim 台账 manifest。

    DESIGN §验证:局终指纹核对锚——防止「结构改了、披露没跟上」的
    跨版本对比污染;回归批脚本头部按本常量断言版本号。
    2→3 = F6 语料治理(P1 败局直方剔伪影档,pooled_mean 重算);
    3→4 = dd-012 重拟合(P1 _LOSS_FIT 改对局档案真值语料回归值)。
    """
    assert cb.COARSE_CALIB_VERSION == 4
    r = cw_sim.simulate_p1(1, pool='snapshot')
    out = sim_runner.write_batch_ledger([r], tmp_path / 'batch')
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['coarse_calib_version'] == cb.COARSE_CALIB_VERSION


# ==================== cw_first_passage 首达生存 ====================


def test_k1_gamblers_ruin_flip():
    """K1 核心:同均值异方差两线,选择随 hp 翻转(教学校验例)。

    线 A(低方差,板强 3):μ≈0.8 → hp=25 剩 2 节点必活。
    线 B(高方差,板强 0):μ≈14,CV 0.5 → 掉血离散大,hp=15 剩 2 节点均值必死但右尾存活。
    """
    # HP=25 剩 2 节点:A 必活,B 有死亡尾
    pa = first_passage_win(3, 25, 2)
    pb = first_passage_win(0, 25, 2)
    assert pa > pb
    # HP=15 剩 2 节点:A(强板)仍高;弱板 B 的 P(win) 仍有右尾 > 0(首达语义:不是期望判死)
    pb15 = first_passage_win(0, 15, 2)
    assert 0.0 < pb15 < 0.5


def test_three_zones():
    """三区律:强板高血=盈余;中血=临界;弱板低血长程=必死边缘。"""
    assert risk_posture(3, 90, 3) in ('盈余', '临界')
    assert risk_posture(0, 10, 9) == '必死边缘'
    assert posture_guidance('必死边缘').startswith('方差追求')
    assert posture_guidance('临界').startswith('方差回避')


def test_degenerate_cases():
    assert first_passage_win(3, 100, 0) == 1.0   # 无节点剩 = 活
    assert first_passage_win(3, 0, 1) == 0.0     # 无血 = 死


# —— v1(ADR-0176):位面条件化 + hp_floor 反解 + 位面乘子模型导出 ——


def test_plane_scales_loss():
    """位面难度进掉血分布(W443 合一后 μ 方向由标定决定,非单调先验):
    - tier≥1:P2 严劣于 P1(μ_P2(tier)=(1−p(rung))·L_cond_mix > P1 先验 μ
      tier1 7.0 / tier2 2.5)→ P(win) 单调不升(浮点容差 1e-9);
    - tier0 显式例外:P1 先验 μ0=14(弱板粗锚)高于 P2 标定 μ0≈13.2
      ——P2 无条件期望不含「每战全损」悲观注入,方向反转是标定事实,
      本锁固化防回退到「P2 恒更凶」的旧先验。
    (P3 别名 P2:非单调断言对 plane=3 同值成立。)"""
    for tier in (1, 2):
        for hp in (20, 40, 60):
            p1 = first_passage_win(tier, hp, 6, plane=1)
            p2 = first_passage_win(tier, hp, 6, plane=2)
            p3 = first_passage_win(tier, hp, 6, plane=3)
            assert p1 + 1e-9 >= p2 >= p3 - 1e-9, (
                f"tier={tier} hp={hp}: P1≥P2≥P3 违反({p1:.4f}/{p2:.4f}/{p3:.4f})")
    # tier0 反转例外(P3=P2 别名逐位)
    mu1 = _loss_dist(0, 1)[1][0]
    mu2 = _loss_dist(0, 2)[1][0]
    mu3 = _loss_dist(0, 3)[1][0]
    assert mu1 > mu2, f"P1 弱板先验 μ={mu1} 应高于 P2 标定 μ={mu2}"
    assert mu2 == mu3, "P3 别名 P2(标定域声明)"


def test_hp_floor_definition():
    """hp_floor = 最小 hp 使 P(win) ≥ target;单调、且该 hp-1 处不达 target(有解时)。"""
    for (tier, nodes, target) in ((1, 8, 0.6), (2, 4, 0.7), (3, 6, 0.6)):
        fl = hp_floor(tier, nodes, target)
        assert first_passage_win(tier, fl, nodes) >= target, f"floor {fl} 未达 target"
        if 1 < fl < 100:
            assert first_passage_win(tier, fl - 1, nodes) < target, f"floor {fl} 非最小"
    # 强板短程:低血即可达标 → 地板低
    assert hp_floor(3, 2, 0.6) <= 10
    # 弱板长程:hp_cap 内无解 → 返回 cap(模型如实说「无底可保」,决策侧由 ratio 接管)
    assert hp_floor(0, 9, 0.9) == 100


def test_plane_hp_ratio_semantics():
    """位面乘子语义(W443 两态标定合一后的现语义;旧 0176 v1 主张
    「弱板长程 > 强板短程」随 PLANE_LOSS_SCALE 退役——新标定下强板
    P1 分支 μ 极小(0.8)而 P2 μ 由胜率通道给出(≈4.6),比值天然顶
    2.0 夹界,方向反转是标定事实非退化):

    - 弱板长程:ratio > 1(该更早保血);
    - 强板短程:顶 2.0 夹界(P1 分母极小,P2 标定 μ 相对大);
    - 夹界:任意 (tier, nodes) ratio ∈ [1.0, 2.0];
    - P3 别名 P2(标定域声明)逐位相等;
    - 弱板长程扩展 cap:真实血上限内两原均无解时 ratio 仍正确(≠1 假性退化)。
    """
    r2_weak = plane_hp_ratio(1, 9, target_pwin=0.6, plane=2)
    r3_weak = plane_hp_ratio(1, 9, target_pwin=0.6, plane=3)
    assert r2_weak > 1.0, "弱板长程 P2 应上浮"
    assert r2_weak == r3_weak, "P3 别名 P2 → 乘子逐位相等"
    r2_strong = plane_hp_ratio(3, 2, target_pwin=0.6, plane=2)
    assert r2_strong == 2.0, "强板短程顶夹界(P1 分支 μ=0.8 vs P2 标定)"
    for tier in (0, 1, 2, 3):
        for nodes in (2, 6, 9, 18):
            for plane in (2, 3):
                r = plane_hp_ratio(tier, nodes, target_pwin=0.6, plane=plane)
                assert 1.0 <= r <= 2.0, f"ratio 夹界违反:tier={tier} n={nodes} p={plane} → {r}"
    # 扩展 cap:tier0 长程真实 cap 内两原无解,ratio 仍反映位面标定(不退化 1.0)
    r0 = plane_hp_ratio(0, 18, target_pwin=0.6, plane=2)
    assert r0 >= 1.0
