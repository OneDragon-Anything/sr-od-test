# -*- coding: utf-8 -*-
"""test_cw_economy 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- economy_cycle: test_cw_economy_cycle.py
- w440_economy_income: test_cw_w440_economy_income.py
- w493_income_calib: test_cw_w493_income_calib.py
- w494_spend_ledger: test_cw_w494_spend_ledger.py
- w695_economy_seam: test_cw_w695_economy_seam.py
- w829_spend_gate: test_cw_w829_spend_gate.py
- w935_release_spend_ledger: test_cw_w935_release_spend_ledger.py
- spend_receipt: test_cw_spend_receipt.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== economy_cycle ====================

from sr_od.application.currency_war.kernel.cw_economy import  reserve_cap
from sr_od.application.currency_war.kernel.cw_plane_table import level_cost
from sr_od.application.currency_war.kernel.cw_state import  BENCH_CAPACITY, BenchChar, GameState, ShopCard
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.economy_cycle import  bench_fill_account, channel_capacity, obligation
from sr_od.application.currency_war.kernel.cw_registry import  DEFAULT_REGISTRY

_REG = DEFAULT_REGISTRY


def _state(*, gold: int = 80, plane: int = 1, r: int = 3, level: int = 6,
           deployed: list[BenchChar] | None = None,
           bench: list[BenchChar | None] | None = None,
           shop: list[ShopCard] | None = None,
           board: dict | None = None,
           hp: int = 80) -> GameState:
    return GameState(
        plane=plane, round_num=r, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2,
        deployed=deployed if deployed is not None else [],
        bench=bench if bench is not None else [None] * BENCH_CAPACITY,
        shop=shop if shop is not None else [], node_type='battle',
        board=board or {})


def _ch(name: str, slot: int, star: int = 1) -> BenchChar:
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    fac = (CHARACTERS[name].factions or ('?',))[0]
    return BenchChar(slot=slot, char_id=name, faction=fac, star=star)


def _sc(name: str, cost: int = 2) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


#: 非过渡体系填充件名(真实注册表名;杂名会 KeyError)
_FILLERS = ('阿格莱雅', '乱破', '大丽花', '黑塔', '飞霄', '加拉赫',
            '娜塔莎', '赛飞儿', '翡翠', '刃', '貊泽')


def _filler(i: int, slot: int | None = None) -> BenchChar:
    return _ch(_FILLERS[i % len(_FILLERS)],
               slot if slot is not None else i)


def _sess(state: GameState) -> StrategySession:
    """裸 session(排程/预算 = 确定性核按 state 现算;注入面退役)。

    注:裸 session 无位面表 → nodes_of_plane 先验 9(一次性告警即
    记档通道);默认 level=6 已达兜底核心(绯英 2 费)峰值级 → 无排程。
    """
    return StrategySession()


# --- A·R* 储备线 ---------------------------------------------------------------


def test_reserve_cap_no_schedule_equals_interest_floor() -> None:
    """无排程升级帧:R* = 息线 50(息线以内持有弱占优,储备主体;
    默认帧 level=6 = 兜底核心峰值级 → 排程判据 False,预告态不虚触发)。"""
    st = _state()
    assert reserve_cap(st, _sess(st), _REG) == 50


def test_reserve_cap_schedules_upgrade_fee_in_window() -> None:
    """窗口内排程升级帧:R* = 息线 + 下一级升级费(费用=clicks×单价,
    期望值=level_cost 常量表本地复算;排程储蓄不是死钱,设计 §1.3)。
    level=5 < 峰值级 6(绯英 2 费)∧ 息引擎已立(gold 80≥50)→ 排程。"""
    st = _state(r=5, level=5)
    assert reserve_cap(st, _sess(st), _REG) \
        == 50 + level_cost(5)


def test_reserve_cap_no_saving_at_plane_end() -> None:
    """h=0(位面末窗):排程升级不储蓄——>3 轮外的升级应即时执行而非
    长期储蓄(窗口上界=结构界)。"""
    st = _state(r=9, level=5)
    assert reserve_cap(st, _sess(st), _REG) == 50


def test_reserve_cap_predictive_below_fee_affordability() -> None:
    """批 3 预告态契约锁(W623 D1):排程不以当帧可负担为前置——
    gold=55(远不够升级费)∧ 峰值级未达 → 排程照发、R* 计入升级费。
    「付不起就不排」会造成 R* 塌缩→义务花光→更排不上的贫穷循环;
    付不付得起是执行层(ev.levelup_ev_basis 可负担性入口门)的事。"""
    st = _state(gold=55, r=5, level=5)
    assert reserve_cap(st, _sess(st), _REG) == 50 + level_cost(5)


# --- A·义务与容量 --------------------------------------------------------------


def test_obligation_capped_by_capacity() -> None:
    """义务=min(溢余, C_t):溢余 30 > 容量 → 义务=容量(结转余量;
    容量外余量进评估罚项,不一步到位假达标,设计 §1.4-3)。
    容量 = 刷新预算分量 min(6, 30//2)=6 刷 ×2 金 =12(店空)。"""
    st = _state(gold=80)   # 溢余 30
    s = _sess(st)
    assert channel_capacity(st, s, _REG) == 12
    assert obligation(st, s, _REG) == 12


def test_obligation_full_within_capacity() -> None:
    """(g−R*)+ ≤ C_t:义务=溢余全额,本轮清零死钱。
    gold 56 → 溢余 6 → 预算 3 刷=容量 6 ≥ 溢余。"""
    st = _state(gold=56)
    s = _sess(st)
    assert obligation(st, s, _REG) == 6


def test_capacity_excludes_option_pieces() -> None:
    """A-1 修复锁(W611 重推):未跨档期权件的容量禁令辖域=满槽帧——
    期权泵死法(W469:义务泵把死钱流向无槽可放的期权件)的防线是
    「槽位约束」;备战有空位帧,未跨档件改按 O1 填补通道计入
    (bench_fill_account,用户 directive:无目标也填满备战;
    .debug/temp/currency_war/w611_econ_cycle/DESIGN.md §4 判据 6)。
    当帧跨档件(买入后四体系达成数 +1,结构性判定)照旧计入。
    gold=50(g=R*):溢余 0 → 刷新分量 0,容量只剩店内账(隔离槽位逻辑)。"""
    st = _state(gold=50, board={})              # 无体系进度:任何件不跨档
    st.shop = [_sc('桑博', 1)]
    s = _sess(st)
    assert channel_capacity(st, s, _REG) == 1    # 空槽帧:O1 填补通道计入
    st.bench = [_filler(i) for i in range(BENCH_CAPACITY)]   # 满槽
    assert channel_capacity(st, s, _REG) == 0    # A-1/A-2:满槽 → 0
    st.bench = [None] * BENCH_CAPACITY           # 恢复空槽
    st.shop = [_sc('丹恒·饮月', 2)]              # board 仙舟=2,买入跨档
    st.board = {'仙舟': 2}
    assert channel_capacity(st, s, _REG) == 2


def test_capacity_charges_bench_slot_opportunity_cost() -> None:
    """A-2 修复锁:bench 满槽时非合成件不计容量(槽位是下一轮跨档件的
    物理前置)。gold=50 同上隔离刷新分量。"""
    st = _state(gold=50, board={'仙舟': 2},
                bench=[_filler(i) for i in range(BENCH_CAPACITY)])
    st.shop = [_sc('丹恒·饮月', 2)]   # 买入跨档但 bench 满
    s = _sess(st)
    assert bench_fill_account(st, _REG) == 0
    assert channel_capacity(st, s, _REG) == 0   # 满槽 → 0


def test_capacity_counts_merge_completion() -> None:
    """3合1 合成件(买入即 2★ 完成)计入容量且不受 bench 槽约束。
    gold=50 隔离刷新分量。"""
    bench = [_ch('桑博', 0), _ch('桑博', 1)] \
        + [_filler(i) for i in range(2, BENCH_CAPACITY)]
    st = _state(gold=50, bench=bench)   # bench 满
    st.shop = [_sc('桑博', 1)]   # 第三张:合成 2★
    s = _sess(st)
    assert channel_capacity(st, s, _REG) == 1


# ==================== w440_economy_income ====================

import json

from sr_od.application.currency_war.sim import engine_p1 as cw_sim
from sr_od.application.currency_war.sim.checks import runner
from sr_od.application.currency_war.kernel import cw_economy
from sr_od.application.currency_war.kernel.cw_economy import  BASE_INCOME, LOSS_GOLD_BY_NODE, REWARD_BASE_GOLD_BY_ROUND, STREAK_GOLD_TABLE, streak_gold

# 路径锁扫描的 seed 数(断言成立的最小覆盖:9 轮/局,败轮高频)
_PATH_SEEDS = 8


def test_loss_gold_by_node_values() -> None:
    """败轮节点金值锁(实机差分众数;独立常量,不动胜轮真值表)。"""
    assert LOSS_GOLD_BY_NODE == {'battle': 2, 'encounter': 4, 'boss': 4}
    # 胜轮表零触碰(ADR-0262):败轮修正不得外溢到 streak_gold 域
    assert STREAK_GOLD_TABLE == (1, 1, 2, 2, 2, 3, 4)
    assert streak_gold(0) == 1 and streak_gold(1) == 1
    assert BASE_INCOME == 5   # 统一近似常量不动(非奖励节点仍 5)


def test_loss_round_income_path_in_sim_ledger() -> None:
    """败轮收入路径锁:生产账本中,败掉的战斗类节点 → 下一轮收入
    streak 分量 = LOSS_GOLD_BY_NODE[败掉节点的类型](奖励轮照发表/
    补给轮恒 0 的分支不受败态影响,与 cw_sim 收入段分支一致)。
    """
    loss_seen = 0
    for seed in range(_PATH_SEEDS):
        r = cw_sim.simulate_p1(seed, pool='fallback')
        rows = r.ledger
        for i, row in enumerate(rows[:-1]):
            s = row['sim']
            if (s['node'] not in LOSS_GOLD_BY_NODE
                    or (s.get('delta') or 0) > 0):
                continue
            loss_seen += 1
            nxt = rows[i + 1]['sim']
            got = nxt['income']['streak']
            if nxt['node'] == 'supply':
                assert got == 0, f'seed{seed}: 败后补给轮不得带 streak'
            elif nxt['node'] == 'reward':
                assert got == streak_gold(0), \
                    f'seed{seed}: 败后奖励轮照发表[0]=1'
            else:
                assert got == LOSS_GOLD_BY_NODE[s['node']], \
                    f'seed{seed} r{row["round_num"]}: 败轮金路径断'
    assert loss_seen > 0, '扫描窗口内无败局样本,锁空转(扩 seed 数)'


def test_reward_round_pair_income_in_sim_ledger() -> None:
    """奖励轮成对锁:base 查表(r1=3/r2=4/其余 5)+ streak 照发表,
    两分量同轮成立——单改 streak 的回归会在此红(净多发 1)。
    """
    reward_seen = 0
    for seed in range(_PATH_SEEDS):
        streak = 0   # 进轮连胜重放(战斗轮 delta>0 计胜,同 sim 结算段)
        for row in cw_sim.simulate_p1(seed, pool='fallback').ledger:
            s = row['sim']
            if s['node'] == 'reward':
                reward_seen += 1
                rn = row['round_num']
                inc = s['income']
                assert inc['base'] == REWARD_BASE_GOLD_BY_ROUND.get(
                    rn, BASE_INCOME), \
                    f'seed{seed} r{rn}: 奖励轮 base 未成对查表'
                assert inc['streak'] == streak_gold(streak), \
                    f'seed{seed} r{rn}: 奖励轮 streak 未照发表'
            elif s['node'] in LOSS_GOLD_BY_NODE:
                streak = streak + 1 if (s.get('delta') or 0) > 0 else 0
    assert reward_seen > 0, '扫描窗口内无奖励轮样本,锁空转'


def test_economy_calib_version_disclosed_in_manifest(tmp_path) -> None:
    """版本披露锁:收入口径版本独立进 sim 台账 manifest,
    与粗模型版本(coarse_calib_version)分键、互不占用。
    """
    assert cw_economy.ECONOMY_CALIB_VERSION == 2   # ADR-0443 事件金重整定
    r = cw_sim.simulate_p1(1, pool='fallback')
    out = runner.write_batch_ledger([r], tmp_path / 'batch')
    manifest = json.loads(
        (out / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['economy_calib_version'] == \
        cw_economy.ECONOMY_CALIB_VERSION
    assert 'coarse_calib_version' in manifest   # 粗模型键原样保留


from sr_od.application.currency_war.sim import runner


# ==================== w493_income_calib ====================

import pytest

from sr_od.application.currency_war.sim import engine_p1 as _w493_income_calib_cw_sim
from sr_od.application.currency_war.kernel import cw_economy as _w493_income_calib_cw_economy
from sr_od.application.currency_war.kernel import cw_coarse_battle as cb

from sr_od.application.currency_war.sim.checks.calib import check_gold_dist_calib, check_shop_cost_curve


def test_event_gold_table_v2_lock() -> None:
    """事件金 v2 值锁(整定产物;重整定须同步递增 economy 版本)。"""
    assert _w493_income_calib_cw_economy.ECONOMY_CALIB_VERSION == 2
    assert _w493_income_calib_cw_sim.EVENT_GOLD_BY_ROUND == {
        1: (0.0,), 2: (6.41,), 3: (13.95,), 4: (14.47,), 5: (23.11,),
        6: (19.41,), 7: (21.15,), 8: (35.05,), 9: (32.0,),
    }


def test_delta_arm_fallback_routes_to_coarse(monkeypatch) -> None:
    """delta 臂桶缺回退:纯 fallback 池(池恒 None)下战斗类结算全部
    落粗模型——胜 delta 恒 WIN_CAP(签名)、负 delta 走节点直方(≤0),
    高成型胜率随 rung 查表(可达性,B3 的单元域锚)。
    """
    monkeypatch.setattr(cb, 'BATTLE_ENGINE_MODE', 'delta')
    wins = 0
    combat = 0
    for seed in range(8):
        for row in _w493_income_calib_cw_sim.simulate_p1(seed, pool='fallback').ledger:
            s = row['sim']
            if s['node'] not in ('battle', 'encounter', 'boss'):
                continue
            combat += 1
            d = s['delta']
            if d > 0:
                assert d == cb.WIN_CAP, \
                    f'seed{seed} r{row["round_num"]}: 对照臂胜态签名断裂(+{d})'
                wins += 1
    assert combat > 0 and wins > 0, '扫描窗口无战斗/无胜,锁空转'


def test_default_arm_unaffected_by_fallback_change() -> None:
    """默认 coarse 臂不进回退分支:同 seed 重放与 monkeypatch 前后逐位同
    (BATTLE_ENGINE_MODE='coarse' 恒默认;本锁防未来把默认臂误接回退)。
    """
    rows_a = [(x['ts'], x['hp'], x['gold'], x['sim']['delta'])
              for x in _w493_income_calib_cw_sim.simulate_p1(5, pool='snapshot').ledger]
    rows_b = [(x['ts'], x['hp'], x['gold'], x['sim']['delta'])
              for x in _w493_income_calib_cw_sim.simulate_p1(5, pool='snapshot').ledger]
    assert rows_a == rows_b


def _led(golds: list[int]) -> list[dict]:
    return [{'plane': 1, 'round_num': i + 1, 'gold': g, 'sim': {'node': 'reward'}}
            for i, g in enumerate(golds)]


def test_gold_dist_calib_band_alarm() -> None:
    """金均值越出实机带软告警;n<100 不判(数据边界)。"""
    poor = [_led([10] * 150)]          # 均值 10 < 25 → 告警
    assert check_gold_dist_calib(poor)['violations'] == 1
    rich = [_led([40] * 150)]          # 均值 40 > 35 → 同样告警
    assert check_gold_dist_calib(rich)['violations'] == 1
    inband = [_led([30] * 150)]        # 带内(30±5)→ 不告警
    assert check_gold_dist_calib(inband)['violations'] == 0
    assert check_gold_dist_calib([_led([30, 31])])['n'] == 2
    assert 'note' in check_gold_dist_calib([_led([30, 31])])


def test_shop_cost_curve_disclosure() -> None:
    """费用曲线纯披露:share 计算正确、空账本给 note、恒 0 违规。"""
    ledger = [{'plane': 1, 'round_num': 1, 'gold': 5,
               'sim': {'node': 'reward', 'shop_waves': [
                   {'event': 'offer',
                    'cards': [{'cost': 1}, {'cost': 1}, {'cost': 3}]},
                   {'event': 'refresh',
                    'cards': [{'cost': 4}]},   # 非 offer 波不入统计
               ]}}]
    out = check_shop_cost_curve([ledger])
    assert out['violations'] == 0 and out['n'] == 3
    assert out['sim_cost_share']['1'] == round(2 / 3, 4)
    assert out['sim_cost_share']['3'] == round(1 / 3, 4)
    empty_row = {'plane': 1, 'round_num': 1, 'gold': 5,
                 'sim': {'node': 'reward'}}
    empty = check_shop_cost_curve([[empty_row]])
    assert empty['violations'] == 0 and 'note' in empty



# ==================== w494_spend_ledger ====================

import json as _w494_spend_ledger_json
from pathlib import Path
from sr_od.application.currency_war.telemetry import query, recorder, schema, state
from sr_od.application.currency_war.telemetry import state as cw_telemetry


# ===== plan_gold_flow(逐项期望金流)=====

def test_flow_mixed_plan():
    """买+升+刷(无cost退2)+卖入混合;DeployMove 零金流不入 items。"""
    plan = [
        {'__type__': 'BuyCard', 'card': {'x': 300, 'name': '卡芙卡', 'cost': 2}},
        {'__type__': 'BuyCard', 'card': {'x': 500, 'name': '', 'cost': 1}},
        {'__type__': 'LevelUp', 'cost': 4},
        {'__type__': 'RefreshShop', 'cost': 0},
        {'__type__': 'SellBench', 'bench_idx': 2, 'income': 3},
        {'__type__': 'DeployMove', 'bench_idx': 0, 'to_row': 'front', 'to_slot': 1},
    ]
    f = query.plan_gold_flow(plan)
    assert f['planned_spend'] == 2 + 1 + 4 + 2
    assert f['planned_income'] == 3
    assert f['net'] == 3 - 9
    assert f['has_refresh'] is True
    assert f['income_unknown'] is False
    assert len(f['items']) == 5   # DeployMove 零金流不计
    assert f['items'][0] == {'type': 'BuyCard', 'target': '卡芙卡', 'cost': 2,
                             'direction': 'spend'}


def test_flow_sell_income_unknown_flag():
    """income=None 记 0 并标 income_unknown(读数缺失不硬猜)。"""
    f = query.plan_gold_flow([{'__type__': 'SellBench', 'bench_idx': 0,
                                      'income': None}])
    assert f['planned_income'] == 0
    assert f['income_unknown'] is True


def test_flow_refresh_explicit_cost_and_fallback():
    """RefreshShop 有 cost 用 cost;缺省退 refresh_cost 参数(=审计 or 2 口径)。"""
    a = query.plan_gold_flow([{'__type__': 'RefreshShop', 'cost': 1}])
    b = query.plan_gold_flow([{'__type__': 'RefreshShop', 'cost': 0}],
                                    refresh_cost=3)
    assert a['planned_spend'] == 1
    assert b['planned_spend'] == 3


# ===== classify_spend_unit(三态判定+边界)=====

def _buy(cost=5):
    return [{'__type__': 'BuyCard', 'card': {'x': 300, 'name': 'X', 'cost': cost}}]


def test_classify_effective():
    """planned_spent & 金按计划移动 = 生效。"""
    r = query.classify_spend_unit(_buy(5), 50, 45)
    assert r['verdict'] == 'effective'
    assert (r['actual_delta'], r['gap']) == (-5, 0)


def test_classify_effective_within_tolerance():
    """差值恰在 ±2 容差内(与 shop 审计同源)→ 生效。"""
    assert query.classify_spend_unit(_buy(5), 50, 47)['verdict'] == 'effective'


def test_classify_not_effective_gold_frozen():
    """planned_spent & 金零下降(W489 病灶形态)= 执行未生效。"""
    r = query.classify_spend_unit(_buy(5), 125, 125)
    assert r['verdict'] == 'not_effective'
    assert r['gap'] == 5


def test_classify_partial_mismatch():
    """金动了但对不上账(部分成交/口径差/未观收入)≠ 全灭,单列一格。"""
    r = query.classify_spend_unit(_buy(5), 50, 20)
    assert r['verdict'] == 'partial_mismatch'


def test_classify_unplanned_spend():
    """no_plan & gold_moved = 计划外花销。"""
    r = query.classify_spend_unit([], 50, 30)
    assert r['verdict'] == 'unplanned_spend'


def test_classify_no_spend_quiet():
    """无计划且金未动 = 健康静默单元。"""
    assert query.classify_spend_unit([], 50, 51)['verdict'] == 'no_spend_quiet'


def test_classify_unknown_missing_close_reading():
    """关店金读数缺失 → unknown 不猜(无冲突行 ≠ 对拍通过,read 失败也不写行)。"""
    r = query.classify_spend_unit(_buy(5), 50, None)
    assert r['verdict'] == 'unknown'
    assert 'gold_reading_missing' in r['reason']


def test_classify_unknown_half_unit_boundary():
    """半单元/中断单元(aborted)即使读数齐也不判——执行链不完整。"""
    r = query.classify_spend_unit(_buy(5), 50, 45, boundary='aborted')
    assert r['verdict'] == 'unknown'
    assert 'boundary' in r['reason']


# ===== query_spend_ledger(读端 join)=====

def _append(rec: Path, name: str, row: dict) -> None:
    schema.append_jsonl(rec / name, row)


def _seed_three_stream(rec: Path) -> None:
    """三流样本:1 个生效单元 + 1 个中断单元 + 1 个大额失配单元。"""
    _append(rec, 'spend_ledger.jsonl', {
        'schema_version': 1, 'ts': '2026-08-28T12:00:00', 'run_id': 'w494t',
        'plane': 1, 'round_num': 1, 'unit_seq': 1, 'boundary': 'closed',
        'progressed': True, 'duration_s': 8.0, 'detail': 'ok',
        'gold_before': None, 'gold_before_trusted': False,
        'gold_close': None, 'gold_close_trusted': False})
    _append(rec, 'spend_ledger.jsonl', {
        'schema_version': 1, 'ts': '2026-08-28T12:05:00', 'run_id': 'w494t',
        'plane': 1, 'round_num': 2, 'unit_seq': 2, 'boundary': 'aborted',
        'progressed': False, 'duration_s': 2.0, 'detail': '执行异常',
        'gold_close': None, 'gold_close_trusted': False})
    _append(rec, 'spend_ledger.jsonl', {
        'schema_version': 1, 'ts': '2026-08-28T12:10:00', 'run_id': 'w494t',
        'plane': 1, 'round_num': 3, 'unit_seq': 3, 'boundary': 'closed',
        'progressed': True, 'duration_s': 9.0, 'detail': 'ok',
        'gold_close': None, 'gold_close_trusted': False})
    # shop plan 行(eval_breakdown 无 prep_step 判别式)+ director 步进行(带 prep_step,不作 plan)
    _append(rec, 'decisions.jsonl', {
        'run_id': 'w494t', 'ts': '2026-08-28T12:00:05', 'plane': 1, 'round_num': 1,
        'gold': 50, 'gold_readable': True, 'eval_breakdown': {},
        'actions': [{'__type__': 'BuyCard', 'card': {'x': 300, 'name': '卡芙卡', 'cost': 5}}]})
    _append(rec, 'decisions.jsonl', {
        'run_id': 'w494t', 'ts': '2026-08-28T11:59:00', 'plane': 1, 'round_num': 1,
        'gold': 48, 'gold_readable': False, 'eval_breakdown': {'prep_step': 1.0},
        'actions': [{'__type__': 'LevelUp', 'cost': 4}]})
    _append(rec, 'decisions.jsonl', {
        'run_id': 'w494t', 'ts': '2026-08-28T12:05:05', 'plane': 1, 'round_num': 2,
        'gold': 60, 'gold_readable': True, 'eval_breakdown': {},
        'actions': [{'__type__': 'BuyCard', 'card': {'x': 300, 'name': '乱破', 'cost': 3}}]})
    _append(rec, 'decisions.jsonl', {
        'run_id': 'w494t', 'ts': '2026-08-28T12:10:05', 'plane': 1, 'round_num': 3,
        'gold': 50, 'gold_readable': True, 'eval_breakdown': {},
        'actions': [{'__type__': 'BuyCard', 'card': {'x': 300, 'name': '椒丘', 'cost': 5}}]})
    # 关店实读金冲突行(仅 r1 对拍通过形态:old=45 new=45;r3 大额失配 20)
    _append(rec, 'obs_conflicts.jsonl', {
        'ts': '2026-08-28T12:00:20', 'field': 'gold_delta', 'old': 45, 'new': 45,
        'verdict': '留证', 'source': 'shop_spend_audit', 'plane': 1, 'round_num': 1,
        'spend': 5})
    _append(rec, 'obs_conflicts.jsonl', {
        'ts': '2026-08-28T12:10:20', 'field': 'gold_delta', 'old': 45, 'new': 20,
        'verdict': '留证', 'source': 'shop_spend_audit', 'plane': 1, 'round_num': 3,
        'spend': 5})


def test_query_spend_ledger_counts_and_large_gap(tmp_path: Path):
    _seed_three_stream(tmp_path)
    lines = query.query_spend_ledger(tmp_path, 'w494t')
    text = '\n'.join(lines)
    assert '共3' in text
    assert 'effective×1' in text
    assert 'unknown×1' in text           # aborted 中断单元:boundary 门 → unknown
    # r3:开金50(plan 行)关金20(冲突行)Δ=-30,计划花5 → 金动了但对不上账
    # (partial_mismatch),差 25 > 10 → 必入大额失配清单
    assert 'partial_mismatch×1' in text
    assert '大额失配' in text
    assert 'p1r3' in text


def test_query_spend_ledger_plan_row_discriminates_prep_step(tmp_path: Path):
    """同轮 shop plan 行与 director 步进行并存:plan 取无 prep_step 的行(金50 非 48)。"""
    _seed_three_stream(tmp_path)
    lines = query.query_spend_ledger(tmp_path, 'w494t')
    r1 = next(ln for ln in lines if 'u1 p1r1' in ln)
    assert '开金=50' in r1
    assert '花费=5' in r1


def test_query_spend_ledger_fallback_pseudo_units(tmp_path: Path):
    """无 ledger 行(历史局):按 shop plan 行重建伪单元,判定恒 unknown。"""
    _append(tmp_path, 'decisions.jsonl', {
        'run_id': 'old', 'ts': '2026-08-28T09:00:00', 'plane': 1, 'round_num': 5,
        'gold': 125, 'gold_readable': True, 'eval_breakdown': {},
        'actions': [{'__type__': 'BuyCard', 'card': {'x': 300, 'name': '卡芙卡', 'cost': 2}}]})
    lines = query.query_spend_ledger(tmp_path, 'old')
    text = '\n'.join(lines)
    assert 'unknown×1' in text
    assert '(伪单元)' in text
    assert '花费=2' in text


def test_record_spend_unit_noop_without_run_id(tmp_path: Path, monkeypatch):
    """run_id 空 → no-op(与 record_exogenous 同门控)。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', '')
    recorder.record_spend_unit(1, 1, 1, 'closed', True, 1.0)
    assert not (tmp_path / 'spend_ledger.jsonl').exists()


def test_record_spend_unit_appends(tmp_path: Path, monkeypatch):
    """有 run_id → 落一行且 schema 字段齐(gold_close 预留恒 None)。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'w494t')
    recorder.record_spend_unit(2, 7, 3, 'failed', False, 12.345,
                                   detail='x' * 500, gold_before=88)
    row = _w494_spend_ledger_json.loads((tmp_path / 'spend_ledger.jsonl').read_text(encoding='utf-8').splitlines()[0])
    assert row['run_id'] == 'w494t'
    assert (row['plane'], row['round_num'], row['unit_seq']) == (2, 7, 3)
    assert row['boundary'] == 'failed'
    assert row['duration_s'] == 12.35
    assert len(row['detail']) == 240   # 截断防刷屏
    assert row['gold_before'] == 88 and row['gold_before_trusted'] is False
    assert row['gold_close'] is None


# ===== 安灯式执行失败停机钩子(临时采证;W494 续)=====

def test_exec_fail_predicate_mismatch_stops():
    """mismatch(计划花费>0 且金差≈0)→ 停(W489 执行未生效病灶形态)。"""

    from sr_od.application.currency_war.run_state import exec_fail_should_stop
    assert exec_fail_should_stop(_buy(5), 125, 125) is True


def test_exec_fail_predicate_partial_and_quiet_and_unknown_dont_stop():
    """partial(金动了但对不上)/静默/unknown(读数缺失、半单元)一律不停。"""

    from sr_od.application.currency_war.run_state import exec_fail_should_stop
    assert exec_fail_should_stop(_buy(5), 50, 20) is False          # partial
    assert exec_fail_should_stop([], 50, 51) is False               # no_spend_quiet
    assert exec_fail_should_stop(_buy(5), 50, None) is False        # unknown:读数缺
    assert exec_fail_should_stop(_buy(5), 125, 125,
                                 boundary='aborted') is False       # unknown:半单元
    assert exec_fail_should_stop(None, None, None) is False         # 全缺不猜


def test_exec_fail_flag_content_lock(tmp_path: Path):
    """flag 三要素内容锁:HOOK-STOP 定位(run_id/轮/unit_seq/plan/gold)+
    可执行处理步骤 + 删除条件(临时捕获类)。"""

    from sr_od.application.currency_war.run_state import write_exec_fail_flag
    fp = tmp_path / 'flag' / 'cw_exec_fail_hook.flag'
    content = write_exec_fail_flag(
        fp, run_id='run_x', plane=2, round_num=5, unit_seq=3,
        plan_summary='BuyCard:卡芙卡:2;LevelUp:level_up:4',
        gold_open=125, gold_close=125)
    assert fp.exists()
    for frag in ('[HOOK-STOP]', 'run_id=run_x', 'p2r5', 'unit_seq=3',
                 'BuyCard:卡芙卡:2', 'gold:开=125 关=125',
                 '处理步骤', '删除条件', '删整段'):
        assert frag in content, frag


def test_exec_fail_flag_path_shape():
    """flag 路径契约锁:固定落在仓根 .debug/temp/cw_exec_fail_hook.flag。"""

    from sr_od.application.currency_war.run_state import _EXEC_FAIL_FLAG_RELPATH, exec_fail_flag_path
    assert str(_EXEC_FAIL_FLAG_RELPATH).replace('\\', '/') == \
        '.debug/temp/cw_exec_fail_hook.flag'
    assert exec_fail_flag_path().name == 'cw_exec_fail_hook.flag'


# ===== W577「计划≠尝试」分流(ADR-0456:局22 误停根因——硬墙静默跳过被
# 当「点击落空」误停;修法=执行侧可见化 + 分类器三态扩展,三新形态锁用
# 局20 r9 / 局22 u1 真实序列作 fixture 数据)=====

def _plan_ju22_u1():
    """局22 p1r9 u1 真实 plan 形态:DeployMove(零金流)+ RefreshShop(cost
    是旧徽标读数 5;W577 后实付恒基价,flow 按显式 cost 计)。"""
    return [
        {'__type__': 'DeployMove', 'bench_idx': 0, 'to_row': 'front', 'to_slot': 1},
        {'__type__': 'RefreshShop', 'cost': 5},
    ]


def _plan_ju20_r9():
    """局20 r9 刷新波真实形态:LevelUp(4)+ RefreshShop(干净对账对,实付 2)。"""
    return [
        {'__type__': 'LevelUp', 'cost': 4},
        {'__type__': 'RefreshShop', 'cost': 0},
    ]


def test_classify_plan_truncated_hard_wall_skips():
    """①硬墙跳过(plan 有动作未尝试)→ plan_truncated,**不停**(局22 u1:
    r9 已刷 4 次达 MAX_REFRESH,plan RefreshShop 被 continue,金 50→50——
    旧分类器误判 not_effective 停线的根因形态)。"""
    r = query.classify_spend_unit(
        _plan_ju22_u1(), 50, 50,
        executed={'plan_truncated': True, 'refresh_skipped': 'max_cap',
                  'refresh_attempted': False})
    assert r['verdict'] == 'plan_truncated'
    assert r['plan_truncated'] is True


def test_classify_free_refresh_proc_board_changed():
    """②刷新已尝试+牌面已变+Δgold=0 → free_refresh_proc,**不停**(免费
    刷新 proc 正证据形态:点击发生、牌面变了、金没扣)。"""
    r = query.classify_spend_unit(
        _plan_ju20_r9(), 68, 68,
        executed={'refresh_attempted': True, 'refresh_board_changed': True})
    assert r['verdict'] == 'free_refresh_proc'


def test_classify_not_effective_attempted_board_unchanged():
    """③刷新已尝试+牌面未变+Δgold=0 → not_effective,**停**(真点击落空)。"""
    r = query.classify_spend_unit(
        _plan_ju20_r9(), 68, 68,
        executed={'refresh_attempted': True, 'refresh_board_changed': False})
    assert r['verdict'] == 'not_effective'


def test_classify_executed_none_backward_compat():
    """executed=None(历史局/未挂钩)→ 判定退回 W494 原语义(金冻结+计划
    花费>0 = not_effective),不因新参数引入行为漂移。"""
    assert query.classify_spend_unit(_buy(5), 125, 125)['verdict'] == 'not_effective'
    assert query.classify_spend_unit(_buy(5), 125, 125,
                                            executed=None)['verdict'] == 'not_effective'


def test_classify_unjudgeable_board_not_treated_as_changed():
    """牌面不可判(None)不得当「已变」——真落空不能被洗成免费(安灯停线面
    不可静默变窄)。"""
    r = query.classify_spend_unit(
        _plan_ju20_r9(), 68, 68,
        executed={'refresh_attempted': True, 'refresh_board_changed': None})
    assert r['verdict'] == 'not_effective'


def test_exec_fail_predicate_exempts_new_verdicts():
    """安灯谓词:plan_truncated / free_refresh_proc → 不停;not_effective → 停。"""

    from sr_od.application.currency_war.run_state import exec_fail_should_stop
    assert exec_fail_should_stop(_plan_ju22_u1(), 50, 50,
                                 executed={'plan_truncated': True,
                                           'refresh_skipped': 'max_cap'}) is False
    assert exec_fail_should_stop(_plan_ju20_r9(), 68, 68,
                                 executed={'refresh_attempted': True,
                                           'refresh_board_changed': True}) is False
    assert exec_fail_should_stop(_plan_ju20_r9(), 68, 68,
                                 executed={'refresh_attempted': True,
                                           'refresh_board_changed': False}) is True


def test_exec_facts_slot_fills_spend_ledger(tmp_path: Path, monkeypatch):
    """shop 执行事实暂存槽 → 单元落账行新字段充实;消费即清(下一单元恒缺省)。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'w577t')
    state.set_unit_exec_facts(
        plan_truncated=True, refresh_skipped='max_cap',
        refresh_attempted=False, refresh_board_changed=None)
    recorder.record_spend_unit(1, 9, 1, 'closed', True, 1.0)
    recorder.record_spend_unit(1, 10, 2, 'closed', True, 1.0)
    rows = [_w494_spend_ledger_json.loads(ln) for ln in
            (tmp_path / 'spend_ledger.jsonl').read_text(encoding='utf-8').splitlines()]
    assert (rows[0]['plan_truncated'], rows[0]['refresh_skipped']) == (True, 'max_cap')
    assert (rows[0]['refresh_attempted'], rows[0]['refresh_board_changed']) == (False, None)
    assert (rows[1]['plan_truncated'], rows[1]['refresh_skipped'],
            rows[1]['refresh_attempted']) == (False, None, False)


def test_spend_unit_row_reader_and_hook_join(tmp_path: Path):
    """_spend_unit_row 按 (run, plane, round, unit_seq) 取最新行;钩子据此
    构造 executed 喂分类器(与 plan/gold_delta 同一 replay join 面)。"""
    _append(tmp_path, 'spend_ledger.jsonl', {
        'ts': '2026-08-29T05:05:30', 'run_id': 'ju22', 'plane': 1,
        'round_num': 9, 'unit_seq': 1, 'boundary': 'closed',
        'plan_truncated': True, 'refresh_skipped': 'max_cap',
        'refresh_attempted': False, 'refresh_board_changed': None})
    _append(tmp_path, 'spend_ledger.jsonl', {
        'ts': '2026-08-29T05:06:30', 'run_id': 'ju22', 'plane': 1,
        'round_num': 9, 'unit_seq': 2, 'boundary': 'closed',
        'plan_truncated': False, 'refresh_skipped': None,
        'refresh_attempted': True, 'refresh_board_changed': True})
    row = query._spend_unit_row(tmp_path, 'ju22', 1, 9, 2)
    assert row is not None and row['refresh_attempted'] is True
    assert query._spend_unit_row(tmp_path, 'ju22', 1, 9, 9) is None
    assert query._spend_unit_row(tmp_path, 'other', 1, 9, 1) is None
    assert query._spend_unit_row(tmp_path, 'ju22', 2, 9, 1) is None


from sr_od.application.currency_war.telemetry import state


# ==================== w695_economy_seam ====================

import inspect

from sr_od.application.currency_war.kernel import cw_economy as _w695_economy_seam_cw_economy
from sr_od.application.currency_war.kernel.cw_state import GameState as _w695_economy_seam_GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w695_economy_seam_StrategySession
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY as _w695_economy_seam_DEFAULT_REGISTRY

_w695_economy_seam_REG = _w695_economy_seam_DEFAULT_REGISTRY


def _st(gold: int, hp: int = 80, level: int = 6, plane: int = 1,
        round_num: int = 5) -> _w695_economy_seam_GameState:
    st = _w695_economy_seam_GameState(gold=gold, level=level, plane=plane,
                   round_num=round_num, hp=hp)
    st.active_strategies = []
    return st


def test_is_emergency_single_source_identity() -> None:
    """单一源锁:filters.is_emergency 本体 = _w695_economy_seam_cw_economy.is_emergency。"""
    import sr_od.application.currency_war.decision.decision_v2.filters as _f
    src = inspect.getsource(_f.is_emergency)
    assert 'cw_economy import is_emergency' in src, \
        'filters 侧必须保持 kernel 重定向(禁本地复刻谓词)'
    # 边界逐位:hp == emergency_hp 恰为 True(≤ 语义)
    assert _w695_economy_seam_cw_economy.is_emergency(_st(50, hp=_w695_economy_seam_REG.emergency_hp), _w695_economy_seam_REG)
    assert not _w695_economy_seam_cw_economy.is_emergency(
        _st(50, hp=_w695_economy_seam_REG.emergency_hp + 1), _w695_economy_seam_REG)


def test_refresh_ev_budget_bitwise_contract() -> None:
    """单元等价锁:下沉后输出与重构前公式逐位一致(帧矩阵全覆盖)。

    契约(`w615_rules_advocacy/` §2-R3 + `w623_batch3_pre-mortem/` D2):
    应急帧 → 0;g ≤ R* → 0;溢余帧 → min(6, ⌊(g−R*)/刷价⌋)。"""
    sess = _w695_economy_seam_StrategySession()
    # 应急帧(hp=emergency_hp)→ 0
    assert _w695_economy_seam_cw_economy.refresh_ev_budget(
        _st(80, hp=_w695_economy_seam_REG.emergency_hp), sess, _w695_economy_seam_REG) == 0
    # 常态帧 g ≤ R*(息线 50,无排程)→ 0
    assert _w695_economy_seam_cw_economy.refresh_ev_budget(_st(50), sess, _w695_economy_seam_REG) == 0
    # 溢余帧:g−R* = 30,刷价缺省 2 → 15 刷 → 6 刷帽
    assert _w695_economy_seam_cw_economy.refresh_ev_budget(_st(80), sess, _w695_economy_seam_REG) == 6
    # 溢余小帧:over=6/刷价2 → 3 刷
    assert _w695_economy_seam_cw_economy.refresh_ev_budget(_st(56), sess, _w695_economy_seam_REG) == 3
    # 刷价现读优先:shop_refresh_cost=3 → over=30//3=10 → 6 刷帽
    st3 = _st(80)
    st3.shop_refresh_cost = 3
    assert _w695_economy_seam_cw_economy.refresh_ev_budget(st3, sess, _w695_economy_seam_REG) == 6
    # 溢余 5/刷价3 → 1 刷
    st4 = _st(55)
    st4.shop_refresh_cost = 3
    assert _w695_economy_seam_cw_economy.refresh_ev_budget(st4, sess, _w695_economy_seam_REG) == 1


# ---- 已退役 2 条(失去保护注记,w729 残差收尾批)----
# test_get_node_goal_projection_uses_local_seam(断环锁 _w695_economy_seam_cw_economy 零
#   decision 依赖):上层覆盖复核成立——test_cw_package_layout::
#   test_bucket_dependency_matrix 对 kernel→decision 全桶禁边(含函数级
#   import),严格强于本锁的单文件 AST 检查。
# test_seam_injection_contract_registry_override(P6 注入契约:显式
#   registry 优先):上层覆盖复核成立——test_cw_w633_migration_b3
#   「注入一致性锁(W636 A)」对三接缝含 refresh_ev_budget 做同型
#   reg2 vs 缺省表对照,行域更宽,本锁无独占行。


# ==================== w829_spend_gate ====================

import dataclasses

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w829_spend_gate_StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import  _check_constraint, arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import  Candidate
from sr_od.application.currency_war.decision.decision_v2.realization import  p29_priority_term
from sr_od.application.currency_war.decision.decision_v2.spend_gate import  bench_front_full, register_press_buy, spend_gate_verdict
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_registry import  DEFAULT_REGISTRY as _w829_spend_gate_DEFAULT_REGISTRY, DecisionV2Registry
from sr_od.application.currency_war.kernel.cw_state import  BenchChar as _w829_spend_gate_BenchChar, BuyCard, GameState as _w829_spend_gate_GameState, ShopCard as _w829_spend_gate_ShopCard

_CORE = '姬子·启行'   # 列车同行 3 费成员(断言走语义不锁牌面)


def _reg(**kw) -> DecisionV2Registry:
    base = {
        'spend_gate_enabled': True,
        'spend_gate_interest_enabled': True,
        'spend_gate_bench_enabled': True,
    }
    base.update(kw)
    return dataclasses.replace(_w829_spend_gate_DEFAULT_REGISTRY, **base)


_REG_ON = _reg()
_REG_OFF = _w829_spend_gate_DEFAULT_REGISTRY


def _scatter_names() -> list[str]:
    """线外对照组:3 费非列车同行成员(注册表派生,非牌面锁定)。"""
    return sorted(
        n for n, c in CHARACTERS.items()
        if c.cost == 3
        and '列车同行' not in (c.factions + c.flows))


def _w829_spend_gate_sess() -> _w829_spend_gate_StrategySession:
    s = _w829_spend_gate_StrategySession()
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '列车同行'
    s.v3_intention = ist
    return s


def _fill_deployed(cap: int) -> list[_w829_spend_gate_BenchChar]:
    return [_w829_spend_gate_BenchChar(slot=i, char_id=f'填充{i}', star=1, faction='公司')
            for i in range(cap)]


def _w829_spend_gate_st(**kw) -> _w829_spend_gate_GameState:
    base = {'plane': 2, 'round_num': 3, 'node_type': '战斗', 'gold': 60,
            'hp': 80, 'hp_readable': True, 'level': 7, 'streak': None,
            'board': {}, 'bench': [], 'shop': []}
    base.update(kw)
    st = _w829_spend_gate_GameState(**base)
    if 'deployed' not in kw:
        # 默认上阵满编(D2「当轮可上场」豁免关闭,锁血带判据本身)
        st.deployed = _fill_deployed(st.max_units())
    return st


def _cand(name: str, cost: int, merge: bool = False,
          needs_slot: bool = False) -> Candidate:
    return Candidate(action=BuyCard(_w829_spend_gate_ShopCard(x=0, name=name, cost=cost)),
                     tag='line_opportunistic', source='test',
                     merge=merge, needs_slot=needs_slot)


def _bench(n: int) -> list[_w829_spend_gate_BenchChar]:
    return [_w829_spend_gate_BenchChar(slot=i, char_id=f'囤件{i}', star=1, faction='公司')
            for i in range(n)]


# ===== 锁 0:开关组缺省态 + 链序(守卫先到先记的结构前提)=====

def test_lock0_defaults_off_and_chain_order() -> None:
    """伞+两子旗标默认全关(生命周期第 1 态);spend_gate 链尾。
    锁语义重推记录(W927 删码批):件价值硬门 pv_bench_reserve 已随
    整机制删除(ADR-0497),旧断言「spend_gate < pv_bench_reserve 邻接
    序」的被锁对象不复存在,spend_gate 恢复链尾——本锁回归「守卫序 +
    链尾」原语义。"""
    for f in ('spend_gate_enabled', 'spend_gate_interest_enabled',
              'spend_gate_bench_enabled'):
        assert getattr(_w829_spend_gate_DEFAULT_REGISTRY, f) is False
    cons = _w829_spend_gate_DEFAULT_REGISTRY.constraints
    assert cons[-1] == 'spend_gate'
    for guard in ('gold_floor', 'copies_cap', 'bench_capacity'):
        assert cons.index(guard) < cons.index('spend_gate')


# ===== 锁 1:D1 息线臂(真破息/零息损/off 臂)=====

def test_lock1_d1_true_interest_break_rejects() -> None:
    """真破息(花后 < 息线 ∧ ⌊g/10⌋ 下降)散件买入拒;off 臂恒放行。"""
    plug = _scatter_names()[0]
    st = _w829_spend_gate_st(gold=20)   # 花后 17:破 50 息线 ∧ 2→1 档
    r = spend_gate_verdict(_cand(plug, 3), st, st, _w829_spend_gate_sess(), _REG_ON)
    assert r is not None and 'd1_interest' in r.describe
    assert spend_gate_verdict(_cand(plug, 3), st, st, _w829_spend_gate_sess(),
                              _REG_OFF) is None   # off 零漂移


def test_lock1b_d1_zero_loss_not_blocked() -> None:
    """零息损(⌊g/10⌋ 不变)买入不拦(E3 同款语义)。"""
    plug = _scatter_names()[0]
    st = _w829_spend_gate_st(gold=23)   # 花后 20:同 2 档
    assert spend_gate_verdict(_cand(plug, 3), st, st, _w829_spend_gate_sess(),
                              _REG_ON) is None


# ===== 锁 2:E-b 内联解耦 + 镜像修复(W830-G 攻击 B 修)=====

def test_lock2_eb_inline_decoupled_mirror_fix() -> None:
    """①线内缺档成员 hp>25 破息放行(E-b 内联判据,不借 P29 项);
    ②预警带(25<hp<40)线内缺档件放行(镜像修复锁——循环豁免若在,
    本断言红);③应急带(hp≤25)E-b 死,破息拒。"""
    sess = _w829_spend_gate_sess()
    st_open = _w829_spend_gate_st(gold=20, board={'列车同行': 1}, hp=80)
    # ① hp=80 破息帧线内缺档件放行
    assert spend_gate_verdict(_cand(_CORE, 3), st_open, st_open, sess,
                              _REG_ON) is None
    # ② 预警带放行(镜像修复)
    st_warn = _w829_spend_gate_st(gold=20, board={'列车同行': 1}, hp=30)
    assert spend_gate_verdict(_cand(_CORE, 3), st_warn, st_warn, sess,
                              _REG_ON) is None
    # ③ 应急带收窄:线内缺档件破息拒
    st_em = _w829_spend_gate_st(gold=20, board={'列车同行': 1}, hp=20)
    r = spend_gate_verdict(_cand(_CORE, 3), st_em, st_em, sess, _REG_ON)
    assert r is not None and 'd1_interest' in r.describe


# ===== 锁 3:D2 血线臂(预警/应急豁免面 + 压库谓词)=====

def test_lock3_d2_warning_band_faces() -> None:
    """预警带(hp 25-40):非转化∧非压库∧非线内缺档件拒(d2_blood);
    线内缺档件放行(转化语义,与锁 2② 同源)。"""
    plug = _scatter_names()[0]
    st = _w829_spend_gate_st(gold=60, hp=35)   # 不破息,纯血带辖域
    r = spend_gate_verdict(_cand(plug, 3), st, st, _w829_spend_gate_sess(), _REG_ON)
    assert r is not None and 'd2_blood' in r.describe
    assert spend_gate_verdict(_cand(plug, 3), st, st, _w829_spend_gate_sess(),
                              _REG_OFF) is None   # off 零漂移


def test_lock3b_d2_press_exempt_and_frame_cap() -> None:
    """压库豁免(ADR-0494 操作化单一源):≤2 费∧非线内成员∧帧 <2 张
    → 放行;第 3 张拒;needs_slot 不获豁免。"""
    low = sorted(n for n, c in CHARACTERS.items()
                 if c.cost == 1
                 and '列车同行' not in (c.factions + c.flows))[0]
    st = _w829_spend_gate_st(gold=60, hp=35)
    sess = _w829_spend_gate_sess()
    auth: dict = {}
    assert spend_gate_verdict(_cand(low, 1), st, st, sess, _REG_ON,
                              auth=auth) is None
    assert auth.get('sg_press') is True   # 豁免 trace → 采纳处计数
    register_press_buy(st, sess)
    register_press_buy(st, sess)
    r = spend_gate_verdict(_cand(low, 1), st, st, sess, _REG_ON)
    assert r is not None and 'd2_blood' in r.describe   # 帧 ≤2 张上限
    # needs_slot(需先腾位)不获豁免:重置预算后仍拒
    sess2 = _w829_spend_gate_sess()
    r2 = spend_gate_verdict(_cand(low, 1, needs_slot=True), st, st,
                            sess2, _REG_ON)
    assert r2 is not None and 'd2_blood' in r2.describe


def test_lock3c_d2_emergency_band_press_banned() -> None:
    """应急带(hp≤25)豁免面收窄:压库禁——1 费散件也拒。"""
    low = sorted(n for n, c in CHARACTERS.items()
                 if c.cost == 1
                 and '列车同行' not in (c.factions + c.flows))[0]
    st = _w829_spend_gate_st(gold=60, hp=20)
    r = spend_gate_verdict(_cand(low, 1), st, st, _w829_spend_gate_sess(), _REG_ON)
    assert r is not None and 'd2_blood' in r.describe


def test_lock3d_d2_conversion_exempt_when_deploy_free() -> None:
    """转化性豁免:有空上阵位(当轮可上场)→ 血带放行。"""
    plug = _scatter_names()[0]
    st = _w829_spend_gate_st(gold=60, hp=35, deployed=[])
    assert spend_gate_verdict(_cand(plug, 3), st, st, _w829_spend_gate_sess(),
                              _REG_ON) is None


# ===== 锁 4:D3 位置臂(bench 前瞻挤占)=====

def test_lock4_d3_bench_front_full() -> None:
    """占用 ≥ 容量−1:非合成∧非当轮可部署拒(d3_bench);merge 豁免
    (E-a)与当轮可部署放行;off 臂恒放行。"""
    st = _w829_spend_gate_st(gold=60, bench=_bench(_w829_spend_gate_DEFAULT_REGISTRY.bench_capacity - 1))
    plug = _scatter_names()[0]
    r = spend_gate_verdict(_cand(plug, 3), st, st, _w829_spend_gate_sess(), _REG_ON)
    assert r is not None and 'd3_bench' in r.describe
    # E-a:merge 候选门让位
    assert spend_gate_verdict(_cand(plug, 3, merge=True), st, st,
                              _w829_spend_gate_sess(), _REG_ON) is None
    # 当轮可部署(有空上阵位)放行
    st_free = _w829_spend_gate_st(gold=60, bench=_bench(_w829_spend_gate_DEFAULT_REGISTRY.bench_capacity - 1),
                  deployed=[])
    assert spend_gate_verdict(_cand(plug, 3), st_free, st_free,
                              _w829_spend_gate_sess(), _REG_ON) is None
    assert spend_gate_verdict(_cand(plug, 3), st, st, _w829_spend_gate_sess(),
                              _REG_OFF) is None   # off 零漂移


def test_lock4b_p29_consumes_shared_predicate() -> None:
    """单一实现上提:P29 囤牌加项临近满栏禁囤仍生效(消费
    bench_front_full 同一函数,禁第二处的行为面回归锁)。"""
    sess = _w829_spend_gate_sess()
    reg = dataclasses.replace(_REG_ON, realization_chain_enabled=True,
                              realization_buy_enabled=True)
    st_open = _w829_spend_gate_st(board={'列车同行': 1})
    assert p29_priority_term(_cand(_CORE, 3), st_open, sess, reg) > 0.0
    st_full = _w829_spend_gate_st(board={'列车同行': 1},
                  bench=_bench(_w829_spend_gate_DEFAULT_REGISTRY.bench_capacity - 1))
    assert bench_front_full(st_full, reg)
    assert p29_priority_term(_cand(_CORE, 3), st_full, sess, reg) == 0.0


# ===== 锁 5:守卫先到先记(arbitrate 链级去重)=====

def test_lock5_guard_first_wins_dedup() -> None:
    """bench 全满候选:bench_capacity 守卫先拒,门不再求值——log 行
    拒因含守卫、不含 spend_gate(d3_bench 与守卫计数零混账)。"""
    st = _w829_spend_gate_st(gold=60, bench=_bench(_w829_spend_gate_DEFAULT_REGISTRY.bench_capacity))
    plug = _scatter_names()[0]
    res = arbitrate([(_cand(plug, 3), 1.0, {})], st, _w829_spend_gate_sess(), _REG_ON)
    row = res.log[0]
    assert not row['accepted']
    assert 'bench_capacity' in row['reject']
    assert 'spend_gate' not in row['reject']


def test_lock5b_d3_fires_only_in_front_full_frame() -> None:
    """未满栏但前瞻挤占帧:d3_bench 经链级裁决显影。"""
    st = _w829_spend_gate_st(gold=60, bench=_bench(_w829_spend_gate_DEFAULT_REGISTRY.bench_capacity - 1))
    plug = _scatter_names()[0]
    res = arbitrate([(_cand(plug, 3), 1.0, {})], st, _w829_spend_gate_sess(), _REG_ON)
    row = res.log[0]
    assert not row['accepted'] and 'd3_bench' in row['reject']


# ===== 锁 6:让位序(alloc 接管帧 / merge 通道 / 末窗不新增放行)=====

def test_lock6_alloc_takeover_frame_yields() -> None:
    """ADR-0474 分配器接管帧(d2_entry_frame 单一源)门整体让位;
    关分配器旗标(=gate-only 臂,无接管帧)同帧恢复血带辖域。"""
    reg = _reg(realization_chain_enabled=True, realization_d2_enabled=True)
    st = _w829_spend_gate_st(plane=2, round_num=1, hp=20, gold=60)
    plug = _scatter_names()[0]
    assert spend_gate_verdict(_cand(plug, 3), st, st, _w829_spend_gate_sess(), reg) is None
    reg_no_alloc = _reg()
    r = spend_gate_verdict(_cand(plug, 3), st, st, _w829_spend_gate_sess(), reg_no_alloc)
    assert r is not None and 'd2_blood' in r.describe


def test_lock6b_endgame_no_new_pass() -> None:
    """末窗(ADR-0451 降格独占帧)门不新增放行:非豁免破息买入照拒。"""
    plug = _scatter_names()[0]
    st = _w829_spend_gate_st(gold=20, round_num=_w829_spend_gate_DEFAULT_REGISTRY.handoff_gate_min_round)
    r = spend_gate_verdict(_cand(plug, 3), st, st, _w829_spend_gate_sess(), _REG_ON)
    assert r is not None and 'd1_interest' in r.describe


# ===== 锁 7:遥测计数 + 压库采纳计数 =====

def test_lock7_block_telemetry_counter() -> None:
    """拒因枚举进 session.v3_sg_block(帧级计数,轮键惰性重置;
    recorder 透传 sess_spend_gate_block 的写入面)。"""
    plug = _scatter_names()[0]
    st = _w829_spend_gate_st(gold=20)
    sess = _w829_spend_gate_sess()
    spend_gate_verdict(_cand(plug, 3), st, st, sess, _REG_ON)
    spend_gate_verdict(_cand(plug, 3), st, st, sess, _REG_ON)
    assert getattr(sess, 'v3_sg_block', None) == {'d1_interest': 2}


# ===== 锁 8:gate-only 选择性恒等 + arbitrate 零漂移 =====

def test_lock8_gate_only_selective_identity() -> None:
    """选择性恒等(v3 修正,替旧「gate-only ≡ off 逐位」):门谓词
    零命中帧(不破息∧非血带∧非前瞻挤占)上门恒放行;off/on 两臂
    arbitrate 动作序列逐位一致(零命中帧位集)。"""
    plug = _scatter_names()[0]
    st = _w829_spend_gate_st(gold=60, hp=80)   # 零命中帧
    assert spend_gate_verdict(_cand(plug, 3), st, st, _w829_spend_gate_sess(),
                              _REG_ON) is None
    off = arbitrate([(_cand(plug, 3), 1.0, {})], st, _w829_spend_gate_sess(), _REG_OFF)
    on = arbitrate([(_cand(plug, 3), 1.0, {})], st, _w829_spend_gate_sess(), _REG_ON)
    assert [type(a).__name__ for a in off.actions] \
        == [type(a).__name__ for a in on.actions]


def test_lock8b_off_arm_verdict_neutral() -> None:
    """off 臂:门函数对任意帧恒 None(约束链在链,行为零漂移)。"""
    plug = _scatter_names()[0]
    for st in (_w829_spend_gate_st(gold=20), _w829_spend_gate_st(gold=60, hp=35),
               _w829_spend_gate_st(gold=60, bench=_bench(8))):
        assert spend_gate_verdict(_cand(plug, 3), st, st, _w829_spend_gate_sess(),
                                  _REG_OFF) is None


# ===== 锁 9:子旗标消融面 =====

def test_lock9_subflag_ablation() -> None:
    """单开息线臂:D3/D2 不辖(D3 判据帧放行);单开位置臂:D1 不辖。"""
    plug = _scatter_names()[0]
    st_front = _w829_spend_gate_st(gold=60, bench=_bench(8))
    reg_i = _reg(spend_gate_bench_enabled=False)
    assert spend_gate_verdict(_cand(plug, 3), st_front, st_front,
                              _w829_spend_gate_sess(), reg_i) is None
    st_broke = _w829_spend_gate_st(gold=20)
    reg_b = _reg(spend_gate_interest_enabled=False)
    assert spend_gate_verdict(_cand(plug, 3), st_broke, st_broke,
                              _w829_spend_gate_sess(), reg_b) is None


# ===== 锁 10:伞关下 _check_constraint 中性(链上节但零行为)=====

def test_lock10_check_constraint_neutral_when_off() -> None:
    """约束链新增一节的缺省中性:_check_constraint('spend_gate',…)
    在伞关时对破息帧返回 None(审计矩阵锁名存在 ≠ 行为变更)。"""
    plug = _scatter_names()[0]
    st = _w829_spend_gate_st(gold=20)
    assert _check_constraint('spend_gate', _cand(plug, 3), st, st,
                             _w829_spend_gate_sess(), _REG_OFF) is None


# ==================== w935_release_spend_ledger ====================

import dataclasses as _w935_release_spend_ledger_dataclasses

from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w935_release_spend_ledger_StrategySession
from sr_od.application.currency_war.decision.decision_v2.posture import Posture
from sr_od.application.currency_war.decision.decision_v2.posture_release import  build_spend_receipt, evaluate_release
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY as _w935_release_spend_ledger_DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import  BENCH_CAPACITY as _w935_release_spend_ledger_BENCH_CAPACITY, BenchChar as _w935_release_spend_ledger_BenchChar, BuyCard as _w935_release_spend_ledger_BuyCard, GameState as _w935_release_spend_ledger_GameState, LevelUp, RefreshShop, ShopCard as _w935_release_spend_ledger_ShopCard

_w935_release_spend_ledger_REG_ON = _w935_release_spend_ledger_dataclasses.replace(_w935_release_spend_ledger_DEFAULT_REGISTRY, crisis_release_enabled=True)


def _w935_release_spend_ledger_state(*, gold: int = 90, hp: int = 25, plane: int = 2, r: int = 4,
           level: int = 6) -> _w935_release_spend_ledger_GameState:
    """危机溢余帧构造(r4P2 形态:hp=25 应急带,g=105>R*→溢余)。"""
    return _w935_release_spend_ledger_GameState(
        plane=plane, round_num=r, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2,
        deployed=[_w935_release_spend_ledger_BenchChar(slot=20 + i, char_id=f'杂{i}', faction='公司',
                            star=1) for i in range(5)],
        bench=[_w935_release_spend_ledger_BenchChar(slot=0, char_id='席0', faction='公司', star=1)]
        + [None] * (_w935_release_spend_ledger_BENCH_CAPACITY - 1),
        shop=[], node_type='battle')


def _crisis_sess(state: _w935_release_spend_ledger_GameState) -> _w935_release_spend_ledger_StrategySession:
    """带 crisis 指令的 session(经 evaluate_release 真实通路装配,
    预算=min(溢余, REFRESH_ROLL_CAP×刷价);posture 键对齐)。"""
    from sr_od.application.currency_war.decision.decision_v2.ev import  RoundPosture
    s = _w935_release_spend_ledger_StrategySession()
    dp = RoundPosture(
        (state.plane, state.round_num),
        Posture(save=True, level_up=False, refresh_budget=0))
    s.v3_dp_posture = dp
    _, d = evaluate_release(state, s, _w935_release_spend_ledger_REG_ON, 'FORM', dp.posture)
    assert d is not None and d.reason == 'crisis'
    return s


def _card(name: str, cost: int) -> _w935_release_spend_ledger_ShopCard:
    return _w935_release_spend_ledger_ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


# --- ① r4P2 混合轮(升级+买,无刷新):修复前记 0 的漏记洞 ---------------------


def test_r4p2_levelup_plus_buy_accrued() -> None:
    """match 2 r4P2 真实帧:升级 6→7(4金,static_ev)+买艾丝妲 1★(1金)
    → spent=5(复盘:实际实花 5,修复前记 0)。"""
    st = _w935_release_spend_ledger_state()
    sess = _crisis_sess(st)
    actions = [LevelUp(cost=4, auth_basis='static_ev'),
               _w935_release_spend_ledger_BuyCard(card=_card('艾丝妲', 1), reason='board_focus')]
    build_spend_receipt(st, sess, _w935_release_spend_ledger_REG_ON, actions, [])
    assert sess.v3_release_spent == 5


# --- ② r5P2 刷+买混合轮:授权门逐笔 + 回执汇总不双记 ---------------------------


def test_r5p2_refresh_plus_buy_no_double_count() -> None:
    """match 2 r5P2 真实帧:刷新 2 金经 authorize_release_refresh 授权门
    逐笔记 2;随后买银狼(3)+椒丘(1)经回执汇总 → spent=6(复盘:
    实际实花 6,修复前记 2)。刷新动作同时出现在 actions 不双记
    (授权门已逐笔扣,汇总分支只辖买/升)。"""
    from sr_od.application.currency_war.decision.decision_v2.posture_release import  authorize_release_refresh
    st = _w935_release_spend_ledger_state(gold=98)   # 息档截断门放行余量内(98 刷 2 → 96 不跨档)
    sess = _crisis_sess(st)
    assert sess.v3_release.budget_gold >= 2
    assert authorize_release_refresh(sess, st.gold, 2, _w935_release_spend_ledger_REG_ON)
    assert sess.v3_release_spent == 2          # 授权门逐笔(既有口径)
    actions = [_w935_release_spend_ledger_BuyCard(card=_card('银狼LV.999', 3), reason='line'),
               _w935_release_spend_ledger_BuyCard(card=_card('椒丘', 1), reason='line'),
               RefreshShop(cost=2)]            # 已扣账的刷新不双记
    build_spend_receipt(st, sess, _w935_release_spend_ledger_REG_ON, actions, [])
    assert sess.v3_release_spent == 6


# --- ③ 非 release 帧:零漂移 --------------------------------------------------


def test_non_release_frame_not_accrued() -> None:
    """v3_release=None(非 release 帧)有买/升动作:不记账——记账分支
    辖域=release 帧,常规帧账面零改动(守卫=判据单一址)。"""
    st = _w935_release_spend_ledger_state()
    sess = _w935_release_spend_ledger_StrategySession()
    actions = [LevelUp(cost=4), _w935_release_spend_ledger_BuyCard(card=_card('艾丝妲', 1))]
    build_spend_receipt(st, sess, _w935_release_spend_ledger_REG_ON, actions, [])
    assert getattr(sess, 'v3_release_spent', 0) == 0


# --- ④ 与回执契约互不辖 -------------------------------------------------------


def test_accrual_independent_of_receipt_gate() -> None:
    """回执契约无条件生效(原开关已除,ADR-0504;release 帧无授权包 →
    回执恒 None)记账照常:记账分支与回执契约互不辖(两契约独立)。"""
    st = _w935_release_spend_ledger_state()
    sess = _crisis_sess(st)
    actions = [LevelUp(cost=4), _w935_release_spend_ledger_BuyCard(card=_card('艾丝妲', 1))]
    r = build_spend_receipt(st, sess, _w935_release_spend_ledger_REG_ON, actions, [])
    assert r is None                            # release 帧无授权包(既有语义)
    assert sess.v3_release_spent == 5           # 记账分支独立生效


# --- ⑤ 轮内跨段累计 -----------------------------------------------------------


def test_round_cumulative_across_segments() -> None:
    """同轮多决策段(re-decide):各段汇总自然累计(决策帧采样读到
    「轮内截至采样时点」的运行累计;每轮入口由 strategy 重置清零)。"""
    st = _w935_release_spend_ledger_state()
    sess = _crisis_sess(st)
    build_spend_receipt(st, sess, _w935_release_spend_ledger_REG_ON,
                        [_w935_release_spend_ledger_BuyCard(card=_card('艾丝妲', 1))], [])
    build_spend_receipt(st, sess, _w935_release_spend_ledger_REG_ON, [LevelUp(cost=4)], [])
    assert sess.v3_release_spent == 5


# --- ⑥ cost 缺失兜底与空动作 --------------------------------------------------


def test_missing_cost_fallback_and_empty_actions() -> None:
    """cost=None 按 3 兜底(与回执 buy 渠道同口径);空动作/无消费动作
    不触账(账面保持原值,不无谓写入)。"""
    st = _w935_release_spend_ledger_state()
    sess = _crisis_sess(st)
    build_spend_receipt(st, sess, _w935_release_spend_ledger_REG_ON,
                        [_w935_release_spend_ledger_BuyCard(card=_card('未知牌', None))], [])
    assert sess.v3_release_spent == 3
    before = sess.v3_release_spent
    build_spend_receipt(st, sess, _w935_release_spend_ledger_REG_ON, [], [])
    assert sess.v3_release_spent is before


# --- ⑦ 预算门全渠道执行锁(行为修复语义;编排者裁决 2026-08-31)-----------------


def test_buys_erode_refresh_budget() -> None:
    """买/升入账后侵蚀刷新授权预算(预算门从失明恢复为执行):
    v3_release_spent 是 authorize_release_refresh 的钳制账,全渠道消费
    共同消耗 budget_gold——旧行为(买/升对门不可见)=超授权滥刷
    (r4P2 实花 5 记 0 即门失明直接证据)。本锁钉住:先花 5 金买/升后,
    预算余量按预算-5 计,刷 2 放行;追加买至贴满预算后下一刷必拒。"""
    from sr_od.application.currency_war.decision.decision_v2.posture_release import  authorize_release_refresh
    st = _w935_release_spend_ledger_state(gold=98)
    sess = _crisis_sess(st)
    budget = sess.v3_release.budget_gold
    assert budget >= 7                        # 满预算前提(12 形态)
    build_spend_receipt(st, sess, _w935_release_spend_ledger_REG_ON,
                        [LevelUp(cost=4), _w935_release_spend_ledger_BuyCard(card=_card('艾丝妲', 1))],
                        [])
    assert sess.v3_release_spent == 5
    assert authorize_release_refresh(sess, 98, 2, _w935_release_spend_ledger_REG_ON)  # 5+2 ≤ 预算
    # 追加买至贴满预算,下一刷必拒(全渠道共同消耗的直接证据)
    build_spend_receipt(st, sess, _w935_release_spend_ledger_REG_ON,
                        [_w935_release_spend_ledger_BuyCard(card=_card('贴满件', budget - 7))], [])
    assert sess.v3_release_spent == budget
    assert not authorize_release_refresh(sess, 90, 2, _w935_release_spend_ledger_REG_ON)  # 预算耗尽


# ==================== spend_receipt ====================

import dataclasses as _spend_receipt_dataclasses
import logging

import pytest as _spend_receipt_pytest

from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _spend_receipt_StrategySession
from sr_od.application.currency_war.decision.decision_v2.allocator import  alloc_domain
from sr_od.application.currency_war.decision.decision_v2.arbiter import  arbitrate as _spend_receipt_arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import  Candidate as _spend_receipt_Candidate
from sr_od.application.currency_war.decision.decision_v2.ev import  RoundPosture
from sr_od.application.currency_war.decision.decision_v2.posture import  Posture as _spend_receipt_Posture, SpendReceipt
from sr_od.application.currency_war.decision.decision_v2.posture_release import  attach_spend_authorization, crisis_release_open, reconcile_spend
from sr_od.application.currency_war.kernel.cw_registry import  DEFAULT_REGISTRY as _spend_receipt_DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import  BenchChar as _spend_receipt_BenchChar, GameState as _spend_receipt_GameState, LevelUp as _spend_receipt_LevelUp

_FOUR_REASONS = {'no_premise', 'no_channel', 'no_candidate', 'no_budget'}


@_spend_receipt_pytest.fixture(autouse=True)
def _quiet_logging():
    """测试域收口静音(本仓测试惯例;全局 logging.disable 随 fixture 还原)。"""
    prev = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(prev)


def _spend_receipt_st(node: str = 'battle', gold: int = 52, hp: int = 62,
        plane: int = 1, round_num: int = 4,
        bench: list[_spend_receipt_BenchChar] | None = None,
        deployed: list[_spend_receipt_BenchChar] | None = None,
        level: int = 4) -> _spend_receipt_GameState:
    st = _spend_receipt_GameState()
    st.plane, st.level, st.gold, st.hp = plane, level, gold, hp
    st.round_num = round_num
    st.node_type = node
    st.bench = list(bench or [])
    st.deployed = list(deployed or [])
    st.hp_readable = True
    st.hp_trusted = True
    return st


def _spend_receipt_sess(posture: _spend_receipt_Posture, st: _spend_receipt_GameState) -> _spend_receipt_StrategySession:
    """把被测姿态写入轮缓存(主链装配位;attach 的授权输入)。"""
    s = _spend_receipt_StrategySession()
    s.v3_dp_posture = RoundPosture((st.plane, st.round_num), posture)
    return s


_BENCH_WAITING = [_spend_receipt_BenchChar(char_id='爻光', faction='仙舟', slot=1)]


# ---------- 授权包装配(§1.1-A) ----------

def test_auth_package_attached_when_premises_hold() -> None:
    """前提成立帧:授权包三件就位(auth_id/premises),姿态标签不变。"""
    st = _spend_receipt_st(bench=_BENCH_WAITING)
    posture = _spend_receipt_Posture(level_up=True, refresh_budget=2, tag='升级+D2')
    sess = _spend_receipt_sess(posture, st)
    _spend_receipt_arbitrate([], st, sess, _spend_receipt_DEFAULT_REGISTRY)
    cached = sess.v3_dp_posture.posture
    assert cached.auth_id == f'{st.plane}-{st.round_num}'
    assert cached.premises == ('pop_slot', 'spend_channel')
    assert cached.level_up and cached.refresh_budget == 2
    # 空候选帧授权未兑现 → 对账门常规帧降级合法(对账语义在专锁覆盖);
    # 本锁只辖授权包装配面本身
    assert cached.tag in ('升级+D2', '存息')
    assert sess.v3_posture_unfulfilled is not None
    auth = sess.v3_spend_auth
    assert auth is not None and auth['level_up'] and not auth['suppressed']


def test_reward_frame_carries_buy_budget() -> None:
    """奖励帧买侧扩张预算 = 溢余段(g−R*;D2 雏形,[1]/[15] 压库授权面)。"""
    st = _spend_receipt_st(node='reward', gold=60, bench=_BENCH_WAITING)
    sess = _spend_receipt_sess(_spend_receipt_Posture(tag='存息'), st)
    _spend_receipt_arbitrate([], st, sess, _spend_receipt_DEFAULT_REGISTRY)
    cached = sess.v3_dp_posture.posture
    # 前置自证:溢余>0 才有授权量(公式本身的健全性检查)
    from sr_od.application.currency_war.decision.decision_v2.economy_cycle import  overflow
    assert overflow(st, sess, _spend_receipt_DEFAULT_REGISTRY) > 0
    assert cached.buy_budget > 0
    assert sess.v3_spend_auth['buy_budget'] == cached.buy_budget


# ---------- 产出侧拒发(D1;13-2 形态)+ 守卫移除红检 ----------

def _board_full_state() -> _spend_receipt_GameState:
    """13-2 p2r4 形态:板满 ∧ bench 空(升级无 slot 可花)。"""
    cap_chars = [_spend_receipt_BenchChar(char_id=f'件{i}', faction='', slot=i + 1)
                 for i in range(3)]
    return _spend_receipt_st(bench=[], deployed=cap_chars, level=3, gold=63)


def test_production_side_rejects_levelup_without_premise() -> None:
    """板满∧bench 空:升级授权产出侧拒发(level_up=False,tag 回落存息)。"""
    st = _board_full_state()
    sess = _spend_receipt_sess(_spend_receipt_Posture(level_up=True, tag='升级'), st)
    res = _spend_receipt_arbitrate([_lv_cand(5.0)], st, sess, _spend_receipt_DEFAULT_REGISTRY)
    cached = sess.v3_dp_posture.posture
    assert cached.level_up is False
    assert cached.tag == '存息'
    assert sess.v3_spend_auth['suppressed'] == ('pop_slot',)
    # 授权未发出 → 无对账义务(不是「授权未兑现」,是「未授权」)
    assert sess.v3_posture_receipt is not None
    assert 'levelup_reason' not in sess.v3_posture_receipt
    assert sess.v3_posture_unfulfilled is None
    # 执行侧纵深防线:升级候选仍被拒付(前序动作演化残余面)
    assert not [a for a in res.actions if isinstance(a, _spend_receipt_LevelUp)]
    assert any('升级前提不成立' in (row.get('reject') or '')
               for row in res.log)


def test_guard_bypass_negative_control(monkeypatch) -> None:
    """守卫移除红检(锁敏感性):旁路授权包装配(旧关臂形态)→ 同帧

    授权照发、契约面全旁路。原 gate 判据已随开关删除;本锁以 monkeypatch
    三函数为「契约被旁路」的等价形态——若未来有人把装配改成可被旁路
    (或恢复条件化),本锁与上一锁双双变红。
    """
    st = _board_full_state()
    sess = _spend_receipt_sess(_spend_receipt_Posture(level_up=True, tag='升级'), st)
    import sr_od.application.currency_war.decision.decision_v2.arbiter as _arb
    monkeypatch.setattr(_arb, 'attach_spend_authorization',
                        lambda *a, **k: None)
    monkeypatch.setattr(_arb, 'build_spend_receipt', lambda *a, **k: None)
    _spend_receipt_arbitrate([_lv_cand(5.0)], st, sess, _spend_receipt_DEFAULT_REGISTRY)
    cached = sess.v3_dp_posture.posture
    assert cached.level_up is True          # 授权照发(授权悬空)
    assert cached.tag == '升级'
    assert cached.auth_id == ''             # 授权包未装配
    assert sess.v3_spend_auth is None
    assert sess.v3_posture_receipt is None
    assert sess.v3_posture_unfulfilled is None


def _lv_cand(val: float) -> tuple[_spend_receipt_Candidate, float, dict]:
    return (_spend_receipt_Candidate(action=_spend_receipt_LevelUp(cost=4), tag='levelup',
                      source='shop'), val, {})


# ---------- r4 形态单帧锁(任务判据) ----------

def test_r4_form_upgrade_action_or_receipt() -> None:
    """r4 形态(g_20260831_032006 p1r4):posture=升级且预算足够 →

    升级动作必须出现,或有四枚举回执(「钱变不成板」无归因态消除)。
    """
    st = _spend_receipt_st(gold=52, bench=_BENCH_WAITING)   # premise ok,budget 足够
    sess = _spend_receipt_sess(_spend_receipt_Posture(level_up=True, tag='升级'), st)
    res = _spend_receipt_arbitrate([_lv_cand(5.0)], st, sess, _spend_receipt_DEFAULT_REGISTRY)
    has_levelup = any(isinstance(a, _spend_receipt_LevelUp) for a in res.actions)
    receipt = sess.v3_posture_receipt or {}
    assert has_levelup or receipt.get('levelup_reason') in _FOUR_REASONS


# ---------- 回执四枚举(D3;三reject面合一,≤2 层收敛) ----------

def test_receipt_reject_enums() -> None:
    """回执 reject 枚举三面(no_channel/no_premise/no_budget):
    - no_channel:20-5 p1r5 形态,升级授权在无商店通道节点 → 回执
      no_channel + 常规帧降级(tag='存息')+ posture_unfulfilled 显式声明;
    - no_premise:执行时点前提失效残余面——授权帧 premise 成立、执行侧
      复核(板满∧bench 空)不成立 → 回执 no_premise;
    - no_budget:授权面存在但预算 0 → 回执枚举 no_budget + 降级。
    """
    # --- no_channel(supply 帧无通道)---
    st = _spend_receipt_st(node='supply', gold=61, bench=_BENCH_WAITING)
    sess = _spend_receipt_sess(_spend_receipt_Posture(level_up=True, tag='升级'), st)
    _spend_receipt_arbitrate([], st, sess, _spend_receipt_DEFAULT_REGISTRY)
    receipt = sess.v3_posture_receipt
    assert receipt is not None
    assert receipt['levelup_reason'] == 'no_channel'
    un = sess.v3_posture_unfulfilled
    assert un is not None
    assert un['channel'] == 'levelup' and un['reason'] == 'no_channel'
    assert un['action'] == 'downgrade'
    assert sess.v3_dp_posture.posture.tag == '存息'

    # --- no_premise(执行时点复核)---
    st2 = _spend_receipt_st(gold=60, bench=_BENCH_WAITING)   # 产出时 premise ok
    sess2 = _spend_receipt_sess(_spend_receipt_Posture(level_up=True, tag='升级'), st2)
    attach_spend_authorization(st2, sess2, _spend_receipt_DEFAULT_REGISTRY)
    from sr_od.application.currency_war.decision.decision_v2.posture_release import  build_spend_receipt, levelup_premise_ok
    full = _board_full_state()
    assert not levelup_premise_ok(full)
    receipt2 = build_spend_receipt(full, sess2, _spend_receipt_DEFAULT_REGISTRY, [], [])
    assert receipt2 is not None
    assert receipt2.levelup_reason == 'no_premise'

    # --- no_budget(预算 0 表锁)---
    st3 = _spend_receipt_st(gold=30, bench=_BENCH_WAITING)
    sess3 = _spend_receipt_sess(_spend_receipt_Posture(tag='存息'), st3)
    sess3.v3_spend_auth = {'auth_id': '1-4', 'level_up': False,
                           'refresh_budget': 0, 'buy_budget': 0,
                           'premises': (), 'suppressed': ()}
    receipt3 = SpendReceipt(buy_reason='no_budget')
    un3 = reconcile_spend(st3, sess3, _spend_receipt_DEFAULT_REGISTRY, receipt3)
    assert un3 is not None
    assert un3['reason'] == 'no_budget' and un3['action'] == 'downgrade'


# ---------- 对账门三选一(D4) ----------

def test_reconcile_allocator_jurisdiction_records_only() -> None:
    """死亡域帧:授权未兑现只记录交分配器(action='allocator'),不降级。"""
    st = _spend_receipt_st(node='battle', gold=61, hp=20, round_num=1, bench=_BENCH_WAITING)
    # D2 入口帧臂默认关(realization_d2_enabled=False);测试臂显式开
    #(谓词引用而非重造,ADR-0504 §引用不重造;与 alloc_domain 同源判定)
    reg = _spend_receipt_dataclasses.replace(
        _spend_receipt_DEFAULT_REGISTRY, realization_chain_enabled=True,
        realization_d2_enabled=True)
    sess = _spend_receipt_sess(_spend_receipt_Posture(level_up=True, tag='升级'), st)
    assert alloc_domain(st, sess, reg) is not None
    _spend_receipt_arbitrate([], st, sess, reg)
    un = sess.v3_posture_unfulfilled
    assert un is not None and un['action'] == 'allocator'
    assert un['reason'] in _FOUR_REASONS
    # 辖域帧不降级:替代消费由 allocator_run 既有接管承担
    assert sess.v3_dp_posture.posture.tag == '升级'


def test_reconcile_crisis_frame_hands_to_release_arm() -> None:
    """危机帧(应急带∧溢余):授权未兑现交 crisis release 既有臂,只记录。"""
    st = _spend_receipt_st(node='battle', gold=100, hp=20, bench=_BENCH_WAITING)
    sess = _spend_receipt_sess(_spend_receipt_Posture(level_up=True, tag='升级'), st)
    # 前置自证:危机臂辖域命中(谓词单一源引用;ADR-0503)
    assert crisis_release_open(st, sess, _spend_receipt_DEFAULT_REGISTRY)
    _spend_receipt_arbitrate([], st, sess, _spend_receipt_DEFAULT_REGISTRY)
    un = sess.v3_posture_unfulfilled
    assert un is not None and un['action'] == 'crisis_release'


# ---------- 返修批(w943_audit5):复位/义务豁免/通道辖域/免费计数 ----------

def test_unfulfilled_reset_per_frame() -> None:
    """复位锁(P1-1):未兑现帧后随「授权被拒发殆尽」的常规段 → 声明清

    None——条件写滞留(跨轮/跨帧误归属)根除,schema「None=无未兑现帧」
    逐帧成立。
    """
    st1 = _spend_receipt_st(node='supply', gold=61, bench=_BENCH_WAITING)
    sess = _spend_receipt_sess(_spend_receipt_Posture(level_up=True, tag='升级'), st1)
    _spend_receipt_arbitrate([], st1, sess, _spend_receipt_DEFAULT_REGISTRY)
    assert sess.v3_posture_unfulfilled is not None   # 未兑现声明已写
    # 下一帧:仅刷新授权且被通道前提产出侧拒发 → 无有效授权 → 无声明
    st2 = _spend_receipt_st(node='supply', gold=61, bench=_BENCH_WAITING, round_num=5)
    sess.v3_dp_posture = RoundPosture((st2.plane, st2.round_num),
                                      _spend_receipt_Posture(refresh_budget=2, tag='+D2'))
    _spend_receipt_arbitrate([], st2, sess, _spend_receipt_DEFAULT_REGISTRY)
    auth = sess.v3_spend_auth
    assert auth is not None and not auth['level_up'] \
        and auth['refresh_budget'] == 0   # 授权被拒发殆尽
    assert sess.v3_posture_unfulfilled is None   # 复位:不携带上帧声明


def test_reward_frame_legal_hoarding_not_unfulfilled() -> None:
    """奖励帧豁免锁(P2-2):授权≠义务——奖励帧 0 买(合法攒息)不记

    未兑现、不触发降级;义务型标记(buy_obligation=True)才入对账。
    """
    st = _spend_receipt_st(node='reward', gold=60, bench=_BENCH_WAITING)
    sess = _spend_receipt_sess(_spend_receipt_Posture(tag='存息'), st)
    _spend_receipt_arbitrate([], st, sess, _spend_receipt_DEFAULT_REGISTRY)
    assert sess.v3_spend_auth['buy_budget'] > 0   # 前置:授权面已发
    assert 'buy_reason' not in (sess.v3_posture_receipt or {})
    assert sess.v3_posture_unfulfilled is None    # 攒息≠病灶
    # 义务型保留位:置 True 后 0 买恢复入对账(降级路径语义不灭)
    from sr_od.application.currency_war.decision.decision_v2.posture_release import  build_spend_receipt
    sess.v3_spend_auth['buy_obligation'] = True
    receipt = build_spend_receipt(st, sess, _spend_receipt_DEFAULT_REGISTRY, [], [])
    assert receipt is not None and receipt.buy_reason == 'no_candidate'


def test_reward_node_has_spend_channel() -> None:
    """reward 通道锁(P2-3):奖励节点有商店执行通道(实机复盘 r1/r2/r8

    买牌执行落地为证),不在无通道集——防未来误补 token 的语义反转。"""
    from sr_od.application.currency_war.decision.decision_v2.posture_release import  spend_channel_ok
    assert spend_channel_ok(_spend_receipt_st(node='reward'))
    assert spend_channel_ok(_spend_receipt_st(node='battle'))
    assert not spend_channel_ok(_spend_receipt_st(node='supply'))   # 20-5 形态保持


def test_free_refresh_counts_fulfilled() -> None:
    """免费计数锁(P3-2):0 金刷新(免费额度)是渠道兑现,支出=0 不虚记。"""
    from sr_od.application.currency_war.decision.decision_v2.posture_release import  build_spend_receipt
    from sr_od.application.currency_war.kernel.cw_state import RefreshShop
    st = _spend_receipt_st(node='battle', bench=_BENCH_WAITING)
    sess = _spend_receipt_sess(_spend_receipt_Posture(refresh_budget=2, tag='+D2'), st)
    attach_spend_authorization(st, sess, _spend_receipt_DEFAULT_REGISTRY)
    receipt = build_spend_receipt(st, sess, _spend_receipt_DEFAULT_REGISTRY,
                                  [RefreshShop(cost=0)], [])
    assert receipt is not None
    assert receipt.refresh_spent == 0        # 实付 0 金,不按缺省虚记 2
    assert receipt.refresh_reason == ''      # 动作发生 = 渠道已兑现
