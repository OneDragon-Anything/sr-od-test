"""段级检查表 _SEGMENT_CHECKS 回归锁(sim 段级短跑批)。

锁防锁纪律(与 test_cw_sim_ledger_checks 同款):合成账本双向断言——
坏账本必报(防静默失效/空转)、好账本必过(防误报);例外条件
([6] 店全想要/[19] 连胜保/[16] 奖励节点)逐条构造放行臂。
窗口接线(max_rounds)= 前缀一致性锁(截断切片 ≡ 真跑到第 K 轮)。
真实批次的违规率不在此锁(分布数值 = change-detector 陷阱,
报告按「量级说明」读)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.sim.checks import segments as chk

from sr_od.application.currency_war.sim.runner import simulate_p1_batch


def _row(round_num: int = 1, *, plane: int = 1, gold: int = 30,
         node: str = 'battle', waves_gold: int | None = None,
         cards: list[dict] | None = None, actions: list | None = None,
         state: dict | None = None, formed_stop: bool = False,
         bench_full_skipped_buys: int = 0, hp: int = 60) -> dict:
    """合成账本行(形状对齐真 ledger;shop_waves 单波)。"""
    return {
        'plane': plane, 'round_num': round_num, 'gold': gold,
        'hp': hp, 'formed_stop': formed_stop,
        'state': state or {'board_factions': {}, 'deployed': [],
                           'bench': [], 'cap': 3, 'level': 4},
        'target_comp': '',
        'actions': actions or [],
        'sim': {'node': node,
                'income': {'base': 5, 'interest': 0, 'streak': 0,
                           'event': 1},
                'spend': {'buys': {}, 'levelup': 0, 'refresh': 0,
                          'sell_income': 0},
                'bench_full_skipped_buys': bench_full_skipped_buys,
                'shop_waves': [{'event': 'offer',
                                'gold': gold if waves_gold is None
                                else waves_gold,
                                'cards': cards or []}]},
    }


def _buy(name: str = '甲', cost: int = 1, channel: str = 'engine') -> dict:
    return {'__type__': 'BuyCard', 'card': {'name': name, 'cost': cost},
            'reason': f'd2_{channel}', 'channel': channel}


def _formed_state(level: int = 5) -> dict:
    """成型态 board_factions:仙舟3+列车2 = 两体系达成(engines≥2)。"""
    return {'board_factions': {'仙舟': 3, '列车同行': 2},
            'deployed': [{'char_id': '藿藿'}], 'bench': [],
            'cap': level, 'level': level}


# ---------------------------------------------------------------- [17]
def test_seg_overflow_idle_spend_bidirectional() -> None:
    """[17] 溢余即花:金>50 零花未成型必报;成型停手/bench 满豁免。"""
    bad = [_row(gold=55, waves_gold=55, node='battle')]
    evs = chk.seg_check_overflow_idle_spend(bad)
    assert evs and evs[0]['gold_before'] == 55
    # 有花费 → 过
    spent = [_row(gold=48, waves_gold=55, actions=[_buy()])]
    assert not chk.seg_check_overflow_idle_spend(spent)
    # 成型(engines≥2)→ 攒息合法面
    formed = [_row(gold=70, waves_gold=70, state=_formed_state())]
    assert not chk.seg_check_overflow_idle_spend(formed)
    # formed_stop 行 → 豁免
    stop = [_row(gold=70, waves_gold=70, formed_stop=True)]
    assert not chk.seg_check_overflow_idle_spend(stop)
    # bench 满守卫拦截轮 → 想买买不了,豁免
    guard = [_row(gold=55, waves_gold=55, bench_full_skipped_buys=2)]
    assert not chk.seg_check_overflow_idle_spend(guard)
    # 息线邻近容忍带(ADR-0478):g0=51/52 浮动态不报;≥53 仍报
    near1 = [_row(gold=51, waves_gold=51, node='battle')]
    near2 = [_row(gold=52, waves_gold=52, node='battle')]
    assert not chk.seg_check_overflow_idle_spend(near1)
    assert not chk.seg_check_overflow_idle_spend(near2)
    evs_far = chk.seg_check_overflow_idle_spend(
        [_row(gold=53, waves_gold=53, node='battle')])
    assert evs_far and evs_far[0]['gold_before'] == 53


# ------------------------------------------------- [17] P2 位面延伸
def test_seg_p2_bleed_gold_stack_bidirectional() -> None:
    """P2 血线下降段金堆积(ADR-0479):hp 掉∧金未泄∧溢余,≥2 连必报;
    血线稳定/金在泄/单轮/P1 段/容忍带内均不报。"""
    # 坏形态:局2/局3 型(P2 金逐轮堆积,hp 逐轮连败;首轮无上轮只
    # 立基,第 2 连轮起报)
    bad = [_row(1, plane=2, gold=55, hp=50),
           _row(2, plane=2, gold=65, hp=40),
           _row(3, plane=2, gold=75, hp=25)]
    evs = chk.seg_check_p2_bleed_gold_stack(bad)
    assert evs and evs[0]['streak'] == 2 and evs[0]['round_num'] == 3
    # 血线稳定(胜局攒息合法面)→ 不报
    stable = [_row(1, plane=2, gold=60, hp=50),
              _row(2, plane=2, gold=70, hp=50)]
    assert not chk.seg_check_p2_bleed_gold_stack(stable)
    # 金在泄(买入盖过收入,溢余在消化)→ 不报
    draining = [_row(1, plane=2, gold=70, hp=50),
                _row(2, plane=2, gold=60, hp=35)]
    assert not chk.seg_check_p2_bleed_gold_stack(draining)
    # 单轮堆积即被非溢余轮打断(灰区)→ 不报
    single = [_row(1, plane=2, gold=70, hp=50),
              _row(2, plane=2, gold=75, hp=45),
              _row(3, plane=2, gold=50, hp=40)]
    assert not chk.seg_check_p2_bleed_gold_stack(single)
    # P1 行不辖([17] P1 面归 seg_overflow_idle_spend)
    p1 = [_row(1, plane=1, gold=60, hp=50),
          _row(2, plane=1, gold=70, hp=35)]
    assert not chk.seg_check_p2_bleed_gold_stack(p1)
    # 息线邻近容忍带内(g≤52,ADR-0478 同带宽)→ 不报
    band = [_row(1, plane=2, gold=50, hp=50),
            _row(2, plane=2, gold=52, hp=35)]
    assert not chk.seg_check_p2_bleed_gold_stack(band)
    # 金不可读帧断链(不可信金不猜)
    broken = [_row(1, plane=2, gold=60, hp=50),
              _row(2, plane=2, gold=None, hp=35),
              _row(3, plane=2, gold=70, hp=20)]
    assert not chk.seg_check_p2_bleed_gold_stack(broken)
    # 新检查已入段级表(sim 批顺路扫,回灌纪律①)
    assert 'seg_p2_bleed_gold_stack' in chk._SEGMENT_CHECKS


# ---------------------------------------------------------------- [11]
def test_seg_lossless_buy_missed_bidirectional() -> None:
    """[11] 无损购买:金<20 同息档有过渡带件未买必报;跨档/成型豁免。"""
    # 注册表内找一个真实的过渡带 1 费件(阵营 ∈ ENGINE_FACTIONS),
    # 不硬编码角色名防注册表演进碎测。
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_line_defs import (
        ENGINE_FACTIONS,
    )
    name = next(n for n, c in CHARACTERS.items()
                if c.cost == 1 and set(c.factions or ()) & set(
                    ENGINE_FACTIONS))
    bad = [_row(gold=13, waves_gold=13,
                cards=[{'name': name, 'cost': 1, 'faction': '?'}])]
    evs = chk.seg_check_lossless_buy_missed(bad)
    assert evs and evs[0]['candidate'] == name
    # 同费跨档(13-3=10 桶 1 ≠ 桶 0?13//10=1,10//10=1 同桶;
    # 用 gold=21>20 的镜像:直接换 gold=11+cost 2 → 9 仍同桶,跨档构造成
    # gold=12,cost=3 超 1-2 带 → 不辖;真正的跨档豁免用金 20 边界:
    # g0=21 ≥20 直接出局,同档判据单测:cost 2 金 11 → 9 同桶仍会报,
    # 所以跨档形态由「带内 cost≤2 且 g-c 不同桶」构造:g0=10,cost=… 无解
    # (10//10=1 与 8//10=0 差一档?10//10=1 —— g0=10 属档1,cost2→8 档0,
    # 跨档!此处应豁免,不报。)
    cross = [_row(gold=10, waves_gold=10,
                  cards=[{'name': name, 'cost': 2, 'faction': '?'}],
                  state={'board_factions': {}, 'deployed': [],
                         'bench': [], 'cap': 3, 'level': 3})]
    assert not chk.seg_check_lossless_buy_missed(cross), \
        '跨档购买有息损,[11] 只锁零息损形态'
    # 成型 → 合法攒息
    formed = [_row(gold=13, waves_gold=13, state=_formed_state(),
                   cards=[{'name': name, 'cost': 1, 'faction': '?'}])]
    assert not chk.seg_check_lossless_buy_missed(formed)


# ------------------------------------------------------------ [6]/[19]
def test_seg_break_interest_exception_bidirectional() -> None:
    """破息记账:无依据破息必报;三例面(店全想要/连胜保/奖励节点)放行。"""
    # 违规:破息买 1 笔 off、无连胜、战斗节点
    bad = [_row(gold=40, waves_gold=55, node='battle',
                actions=[_buy('杂件', channel='off')]),
           ]
    bad[0]['sim']['spend']['buys'] = {'d2_off': 15}
    evs = chk.seg_check_break_interest_exception(bad)
    assert evs and evs[0]['gold_before'] == 55 \
        and evs[0]['buys'][0]['channel'] == 'off' \
        and isinstance(evs[0]['final_shop_panel'], list)
    # 例外①店全想要(≥2 笔无一 off)
    store_all = [_row(gold=40, waves_gold=55, node='battle',
                      actions=[_buy('引擎件'), _buy('凑对件', channel='pair')])]
    assert not chk.seg_check_break_interest_exception(store_all)
    # 例外②连胜保([19]):进轮重算连胜 ≥2(前两轮战斗胜 delta≥0)
    streak_rows = [
        _row(1, gold=52, waves_gold=52, node='battle'),
        _row(2, gold=54, waves_gold=54, node='battle'),
        _row(3, gold=40, waves_gold=58, node='battle',
             actions=[_buy('保连件', channel='pair')]),
    ]
    assert not chk.seg_check_break_interest_exception(streak_rows)
    # 例外③奖励节点升级买经验([16]②)
    reward_lv = [{**_row(gold=45, waves_gold=52, node='reward'),
                  'actions': [{'__type__': 'LevelUp', 'cost': 4}]}]
    reward_lv[0]['sim']['spend']['levelup'] = 4
    assert not chk.seg_check_break_interest_exception(reward_lv)
    # 不破息(gold_end≥50 或起点<50)不管(买后仍 ≥50)
    calm = [_row(gold=51, waves_gold=52, actions=[_buy()])]
    assert not chk.seg_check_break_interest_exception(calm)
    # 例外⑥boss 窗地板授权(ADR-0478):boss 节点破息但花后 ≥ boss_floor(10)
    # → 豁免;跌破地板 → 越权仍报(detail 带越权标注)
    boss_ok = [_row(gold=48, waves_gold=51, node='boss',
                    actions=[_buy('线核件', cost=3, channel='engine')])]
    boss_ok[0]['sim']['spend']['buys'] = {'d2_line_carry': 3}
    assert not chk.seg_check_break_interest_exception(boss_ok)
    boss_breach = [_row(gold=6, waves_gold=51, node='boss',
                        actions=[_buy('线核件', cost=45, channel='engine')])]
    boss_breach[0]['sim']['spend']['buys'] = {'d2_line_carry': 45}
    evs_boss = chk.seg_check_break_interest_exception(boss_breach)
    assert evs_boss and '越权' in evs_boss[0]['detail']


# --------------------------------------------------------------- [13]
def test_seg_formed_still_buying_transition_bidirectional() -> None:
    """[13] 成型停手:成型后新增过渡填充件必报;目标件/同名副本豁免。"""
    base = {'state': _formed_state()}
    bad = [_row(1, **dict(base)),
           _row(2, gold=30, waves_gold=30, actions=[
               _buy('散装过渡件', channel='engine')], state=_formed_state()),
           ]
    evs = chk.seg_check_formed_still_buying_transition(bad)
    assert evs and evs[0]['round_num'] == 2 \
        and evs[0]['bought'] == '散装过渡件'
    # 未成型阶段的同类买入 → 不报
    early = [_row(1, gold=30, waves_gold=30, actions=[_buy('散装过渡件')],
                  state={'board_factions': {}, 'deployed': [],
                         'bench': [], 'cap': 3, 'level': 3})]
    assert not chk.seg_check_formed_still_buying_transition(early)
    # 同名在场再买 = 升星副本路径([4]/[28]) → 豁免
    dup_state = _formed_state()
    dup_state['deployed'] = [{'char_id': '散装过渡件'}]
    dup = [_row(1, **base), _row(2, gold=30, waves_gold=30,
                                 state=dup_state,
                                 actions=[_buy('散装过渡件')])]
    assert not chk.seg_check_formed_still_buying_transition(dup)
    # 目标件买入(bridge 名册内身份/目标 comp 名册)→ 豁免:用真实
    # bridge_pool 组件名查一个名单成员
    from sr_od.application.currency_war.kernel.cw_line_defs import BRIDGE_POOL
    bridge_member = next(iter({n for combo in BRIDGE_POOL
                               for n in (*combo.fixed, *combo.core)}))
    target = [_row(1, **base),
              _row(2, gold=30, waves_gold=30, state=_formed_state(),
                   actions=[_buy(bridge_member, channel='engine')])]
    assert not chk.seg_check_formed_still_buying_transition(target)


# ---------------------------------------------------------- [12]/[33]
def test_seg_unjustified_levelup_bidirectional() -> None:
    """凭空追级:lv≥5 金<50 无授权必报;pop_slot/dp/static_ev 与奖励
    节点豁免。"""
    pre = {'board_factions': {}, 'deployed': [], 'bench': [],
           'cap': 5, 'level': 5}
    post = {**pre, 'level': 6}
    bad = [_row(1, state=pre),
           _row(2, gold=28, waves_gold=28, node='battle', state=post,
                actions=[{'__type__': 'LevelUp', 'cost': 4, 'auth': ''}])]
    evs = chk.seg_check_unjustified_levelup(bad)
    assert evs and evs[0]['level_before'] == 5 and evs[0]['gold_before'] == 28
    # 授权白名单(pop_slot=[33] 人口位)→ 放行
    ok_auth = [bad[0], {**bad[1],
                        'actions': [{'__type__': 'LevelUp', 'cost': 4,
                                     'auth': 'pop_slot'}]}]
    assert not chk.seg_check_unjustified_levelup(ok_auth)
    # 奖励节点买经验([16]②)→ 放行
    ok_reward = [bad[0], {**bad[1], 'sim':
                          {**bad[1]['sim'], 'node': 'reward'}}]
    assert not chk.seg_check_unjustified_levelup(ok_reward)


# ------------------------------------------------------------ 恒等式
def test_seg_gold_identity_bidirectional() -> None:
    """链式金恒等式:改一行末金必报;守恒账本零事件。"""
    good = [_row(1, gold=6), _row(2, gold=12)]
    assert not chk.seg_check_gold_identity(good)
    bad = [_row(1, gold=6), _row(2, gold=99)]
    evs = chk.seg_check_gold_identity(bad)
    assert evs and '99' in evs[0]['detail']


# ------------------------------------------------------- 批入口/接线
def test_run_segment_counts_and_caps() -> None:
    """批量入口:计数=真值、events 截断披露、seed 定位字段齐。"""
    ledgers = [[_row(1, gold=55, waves_gold=55)]
               for _ in range(chk._SEGMENT_EVENTS_CAP + 3)]
    rep = chk.run_segment_checks(ledgers, seed_base=100)
    seg = rep['seg_overflow_idle_spend']
    assert seg['count'] == len(ledgers)   # 全部触发
    assert len(seg['events']) == chk._SEGMENT_EVENTS_CAP
    assert seg['truncated'] is True
    assert seg['events'][0]['seed'] == 100 and \
        seg['events'][0]['game_idx'] == 0


@pytest.mark.parametrize('max_rounds', [None, 4])
def test_batch_wiring_window(max_rounds: int | None) -> None:
    """batch 内嵌接线(最小 n;n 小不是统计口径,只验管线):
    segment_checks 键在(独立于 checks 开关)、max_rounds 披露、
    窗口语义=前缀切片(全量跑的前 K 轮金轨迹 ≡ 窗口口径下应为
    同段——这里间接锁 max_rounds=None 时键仍存在且为 None)。"""
    rep = simulate_p1_batch(2, pool='snapshot', ledger=False,
                            checks=False, seed_base=3100,
                            max_rounds=max_rounds)
    assert rep['max_rounds'] == max_rounds
    sc = rep['segment_checks']
    assert set(sc) >= set(chk._SEGMENT_CHECKS) | {'_summary'}
    for row in sc.get('seg_gold_identity', {}).get('events', []):
        assert row['round_num'] <= (max_rounds or 99)


def test_batch_zero_drift_when_no_window(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """零漂移门:不传窗口参数时,checks_violations 与 headline 键集
    与改动前的契约一致(增量键=max_rounds/segment_checks 只增不改)。

    逐字节对拍的基线快照在开发机 .debug/temp(不入仓);测试仓
    锁的是**结构**:既有 top-level 键仍在且 checks_violations 各项
    形状不变(sim-testing checklist 步骤②的机读版)。
    """
    rep = simulate_p1_batch(2, pool='snapshot', ledger=False,
                            seed_base=3200)
    for k in ('n', 'pool_fingerprint', 'pool_source', 'hp_ge_60',
              'avg_final_hp', 'battle_losses_le_2', 'dir_by_r2',
              'avg_refreshes'):
        assert k in rep, f'headline 键缺失: {k}'
    assert rep['max_rounds'] is None
    cv = rep['checks_violations']
    for name, r in cv.items():
        assert 'violations' in r and 'seed_base' in r, f'{name}: {r}'


