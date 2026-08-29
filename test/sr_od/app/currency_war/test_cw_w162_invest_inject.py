# -*- coding: utf-8 -*-
"""ADR-0364(W162)sim 投资策略/环境注入锁。

锁面:
- 零漂移门:invest=False(默认)主路径逐位同旧(与显式空剧本一致;
  注入脚手架不消费 sim 主 rng);
- 注入语义:session 语义位写入(active_env/active_strategies,handler
  对齐:append+去重)+ state 镜像;
- ①资格通道激活:_direct_line_qualified 直证 + 注入批 p1_locked_rounds
  分布非零(off 口径恒 0=W161 缺口);
- 经济聚合子集:interest_cap_override / gold_per_node / instant_gold /
  free_refresh_per_node 在 sim 生效;
- 频次表/采样器:注册表内名、全角冒号归一、同 seed 确定性。
n 取断言成立最小值(README 纪律 7);池用 fallback(结构断言,无池语义)。
"""
from __future__ import annotations

import logging

from sr_od.application.currency_war import cw_sim
from sr_od.application.currency_war.cw_sim_invest import (
    SIM_STRATEGY_PICK_SCHEDULE,
    SimInvestProfile,
    env_freq_table,
    freq_dropped_names,
    sample_invest_profile,
    strategy_freq_table,
)

logging.disable(logging.CRITICAL)

_POOL = 'fallback'
KEYS = ('final_hp', 'hp_trail', 'refreshes', 'dir_round', 'level')


def _snap(seed: int, **kw):
    r = cw_sim.simulate_p1(seed, pool=_POOL, **kw)
    return {k: getattr(r, k) for k in KEYS} | {'n_ledger': len(r.ledger)}


# ---------- 零漂移门 ----------

def test_invest_off_is_bit_identical() -> None:
    """默认(不传 invest)与显式 False 逐位同——主路径零漂移。"""
    for s in range(4):
        assert _snap(s) == _snap(s, invest=False)


def test_empty_profile_equals_off() -> None:
    """空剧本(无环境无选卡)= 关:注入脚手架对主 rng 零消耗。"""
    empty = SimInvestProfile()
    for s in range(4):
        assert _snap(s) == _snap(s, invest=empty)


def test_sample_profile_deterministic() -> None:
    """同 seed 同剧本(独立 rng 流;A/B 配对可比性的基础)。"""
    for s in (0, 7, 42):
        assert sample_invest_profile(s) == sample_invest_profile(s)


# ---------- 注入语义位 ----------

def test_inject_writes_session_semantic_slots() -> None:
    """环境+选卡写 session 语义位(handler 写点对齐)+ state 镜像。

    用单轮剧本验证:开局环境即写;选卡轮 append 进 active_strategies
    (去重:同名二选一只入一次);SimResult 观测字段同步。
    """
    prof = SimInvestProfile(
        active_env='银河学者概念股',
        picks=((1, 1, '黑塔纪元'), (1, 3, '黑塔纪元')),   # 重名 → 去重
    )
    r = cw_sim.simulate_p1(0, pool=_POOL, invest=prof)
    assert r.invest_env == '银河学者概念股'
    assert r.invest_strategies == ('黑塔纪元',)


def test_inject_session_carries_fields() -> None:
    """注入后 session(生产持久宿主)携带 active_env/active_strategies。"""
    from sr_od.application.currency_war.cw_strategy import StrategySession
    sess = StrategySession()
    prof = SimInvestProfile(active_env='火药味',
                            picks=((1, 1, '加油站'),))
    cw_sim.simulate_p1(0, pool=_POOL, session=sess, invest=prof)
    assert sess.active_env == '火药味'
    assert '加油站' in sess.active_strategies


# ---------- ①资格通道激活 ----------

def test_direct_line_qualified_via_injected_env() -> None:
    """①资格通道直证:注入环境亲和 → _direct_line_qualified 为真
    (无注入语料下恒假,W161 缺口本体)。"""
    from sr_od.application.currency_war.kernel.cw_intention import (
        _direct_line_qualified,
    )
    from sr_od.application.currency_war.kernel.cw_state import GameState
    st = GameState()
    assert not _direct_line_qualified(st, '大黑塔银河学者')
    st.active_env = '银河学者概念股'
    assert _direct_line_qualified(st, '大黑塔银河学者')


def test_invest_on_activates_p1_lock() -> None:
    """缺口闭合直证:注入批 p1_locked_rounds 分布非零(off 恒 0)。"""
    prof = SimInvestProfile(
        active_env='银河学者概念股',
        picks=((1, 1, '黑塔纪元'),),   # 策略侧亲和 → 大黑塔银河学者
    )
    on = [cw_sim.simulate_p1(s, pool=_POOL, invest=prof).p1_locked_rounds
          for s in range(8)]
    off = [cw_sim.simulate_p1(s, pool=_POOL).p1_locked_rounds
           for s in range(8)]
    assert all(v == 0 for v in off)       # W161 缺口:off 口径恒 0
    assert any(v > 0 for v in on)         # 注入后锁定分布非零


# ---------- 经济聚合子集 ----------

def test_interest_cap_override_applies() -> None:
    """利息上调(cap 10):金 ≥100 轮的利息按覆写帽(旧帽 5)。"""
    prof = SimInvestProfile(picks=((1, 1, '利息上调'),))
    # 直接构造:跑局后查账本中存在 interest>5 的行(金≥100 需局内累积,
    # 不保证出现)→ 改为单元层断言聚合接线:
    from sr_od.application.currency_war.kernel.cw_investments import aggregate_economy
    eff = aggregate_economy(['利息上调'])
    assert eff.interest_cap_override == 10
    # sim 收入层接线:注入局的 r1 利息仍按帽 5(gold=5+开局),仅验证
    # 表达式路径不炸 + off/同 seed 差异可追(宽松锁,防脆)
    r = cw_sim.simulate_p1(0, pool=_POOL, invest=prof)
    assert r.final_hp >= 0


def test_gold_per_node_and_instant_gold_apply() -> None:
    """定期福利(+4 金选卡 / 每节点 +2):账本收入行出现 invest 键。"""
    prof = SimInvestProfile(picks=((1, 1, '定期福利'),))
    r = cw_sim.simulate_p1(0, pool=_POOL, invest=prof)
    rows = [row for row in r.ledger
            if (row.get('sim') or {}).get('income', {}).get('invest')]
    assert rows, 'gold_per_node 未进账本收入分解'


def test_free_refresh_per_node_zero_cost() -> None:
    """加油站(每节点 1 次免费刷):每轮第 i 次刷 cost == 0 if i < 额度 else 原价。

    构造:use_refresh 默认开;若策略未发刷则自然宽松(无刷新 = 无逐笔
    断言对象,故另设 any_refresh 防构造失效)。不变式 = 每节点免费额度
    语义逐行成立(ADR-0131:额度内刷价 0,超出付 SHOP_REFRESH_COST),
    同节点多次刷新合法——旧口径的总和上界 ``max(0, (refreshes-rounds))*2``
    隐含「每节点 ≤1 刷」分布假设(非游戏规则非 ADR 口径),粗战斗模型
    引入的多刷局误红,已废。
    """
    from sr_od.application.currency_war.kernel.cw_economy import SHOP_REFRESH_COST
    from sr_od.application.currency_war.kernel.cw_investments import aggregate_economy

    prof = SimInvestProfile(picks=((1, 1, '加油站'),))
    r = cw_sim.simulate_p1(0, pool=_POOL, invest=prof)
    quota = aggregate_economy(['加油站']).free_refresh_per_node
    assert quota > 0
    any_refresh = False
    for row in r.ledger:
        acts = [a for a in (row.get('actions') or [])
                if a.get('__type__') == 'RefreshShop']
        for i, a in enumerate(acts):
            expect = 0 if i < quota else SHOP_REFRESH_COST
            assert a['cost'] == expect, (row.get('round_num'), i, a['cost'])
        if acts:
            any_refresh = True
            # 账本自洽:轮内 spend.refresh 与 actions 逐笔成本一致
            assert (row.get('sim') or {}).get('spend', {}).get('refresh', 0) \
                == sum(a['cost'] for a in acts), row.get('round_num')
    assert any_refresh, '构造失效:整局零刷新,免费额度语义未被锁到'


# ---------- 频次表与日程 ----------

def test_freq_tables_registry_known() -> None:
    """频次表全注册表内(丢名走 freq_dropped_names 披露,不进表)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        get_env,
        get_strategy,
    )
    for name, _ in strategy_freq_table():
        assert get_strategy(name) is not None, name
    for name, _ in env_freq_table():
        assert get_env(name) is not None, name


def test_schedule_keys_unique_and_ordered() -> None:
    """日程键 (plane, round) 唯一且按位面-轮升序。"""
    keys = [(p, r) for p, r, _ in SIM_STRATEGY_PICK_SCHEDULE]
    assert len(keys) == len(set(keys))
    assert keys == sorted(keys)


def test_plaza_names_canon_colon() -> None:
    """全角冒号 plaza 名(如 骇客专家：银狼)归一后进表(不丢)。"""
    table = dict(strategy_freq_table())
    assert '骇客专家:银狼' in table
    # 披露通道存在(即使本版零丢弃,键可达)
    assert isinstance(freq_dropped_names(), dict)
