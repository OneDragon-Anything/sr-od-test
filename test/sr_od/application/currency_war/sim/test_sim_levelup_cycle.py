"""升级-刷新-随机态闭环预注册判据批跑(迭代 2026-10-17-levelup-shop-
transition T-5;landing §3.5 验收凭据,design §2.6 五判据)。

判据与断言对照(逐条数字面落批跑报告,报告路径 = 迭代目录 reports/
T-5-r1.md,由本测试 ``-s`` 输出收割):

- ①富余帧:商店转场帧(``levelup_transition_close`` = 资格门命中可发射
  的转场出口)发生的局,备战升级批必落地(``levelup_batch_emitted`` >
  0)∧ 刷新判据可达(刷新动作 receipts > 0 ∨ 显式拒因计数已登记——
  ``shop_refresh_*`` 拒因族 + r2 预算拦下键);
- ②人口位不饿死:等级(cap 解锁地板,``max_units_of`` 经读口跟随)
  journal 轨迹逐写单调不回退;
- ③随机态闭环:商业间谍升级次数(后端披露 ``spy_deal_count``,每次
  升级回调恰一次状态副本分支)= 随机态重开触发次数(``shop_randomized_
  reopen`` 计数键);偷取入席 + 席满溢出 = 3×升级数(EffectSpec 300201
  ``steal_on_level_up``);入席 > 0 局须有备战席观察写行(spy_steal
  证据);
- ④判据面禁 hp/胜率:本文件断言面零 hp/胜率消费(sim-testing 边界;
  逐局统计行的终局源分类沿用冒烟形态,属运行收尾分类非判据输入);
- ⑤同 seed 重放确定性:全跑双跑容器逐位一致 =
  ``test_sim_first_run.py::test_first_match_deterministic_double_run_
  identical`` 承载(全跑快照对拍,本批不重复建设)。

驱动 = 现役运行原语 ``run_sim_full_match`` 的共享批跑夹具(sim/conftest.py,
与冒烟批同款装配缝、同种子集,会话级只跑一次——2026-10-24 用户裁定全量
压到 ~3 分钟,此前两批各跑一遍属重复计算;实机采集停机钩子桩掉语义同
冒烟批)。种子集 = BATCH_SEEDS 8 个代表号(全量普查临时换
FULL_SWEEP_SEEDS,见 conftest)。运行成本:批跑产物由冒烟批共享,本文件
自身只做断言,秒级;慢桶登记(slow_marks.txt)。
"""
from __future__ import annotations

from typing import Any

import pytest
from test.harness.sim_backend_runner import run_sim_full_match
from test.sr_od.application.currency_war.sim.conftest import BATCH_SEEDS

#: 刷新判据可达的显式拒因键族(计数已登记 = 判据运行到拒;除 receipts 外
#: 的第二可达证据面;存在性门时代两键随门删除退役,拒因观测归
#: ``shop_refresh_*`` 前缀族)。
_REFRESH_REJECT_KEYS: tuple[str, ...] = (
    'must_spend_r1_budget_fail',
)


def _refresh_rejects(counters: dict) -> int:
    """刷新判据显式拒因合计(前缀族 shop_refresh_* + 预算拦下键)。"""
    n = sum(int(v or 0) for k, v in counters.items()
            if k.startswith('shop_refresh_'))
    return n + sum(int(counters.get(k) or 0) for k in _REFRESH_REJECT_KEYS)


def _refresh_receipts(journal_rows: list) -> int:
    """刷新动作 receipts 累积峰值(receipts 域 = 行为窗口累积快照,
    峰值 = 窗末计数,跨窗刷新因重开重新入窗按峰值保守取)。"""
    peak = 0
    for r in journal_rows:
        if r.get('row') != 'write' or r.get('field') != 'receipts':
            continue
        after = r.get('after')
        if not isinstance(after, list):
            continue
        n = sum(1 for it in after
                if isinstance(it, dict)
                and str(it.get('op') or '') == 'CwActionRefreshShopParam')
        peak = max(peak, n)
    return peak


def _level_trail_monotonic(journal_rows: list) -> tuple[bool, list[int]]:
    """等级 journal 轨迹单调性(②人口位不饿死;cap = 等级解锁地板,
    等级不回退 ⟺ 部署席位上限不回退)。返回 (是否单调, 轨迹样本)。"""
    trail: list[int] = []
    for r in journal_rows:
        if r.get('row') != 'write' or r.get('field') != 'level':
            continue
        after = r.get('after')
        if isinstance(after, (int, float)):
            trail.append(int(after))
    # 轨迹 0/1 长平凡单调(zip 非严格配对:尾元素无后继可比)
    return all(b >= a for a, b in zip(trail, trail[1:], strict=False)), trail


@pytest.mark.timeout(1200)
def test_prereg_upgrade_cycle_batch(
        sim_batch_runs: dict[int, Any]) -> None:
    """五判据批跑(逐 seed 断言;数字对照落批跑报告)。

    整局由 sim/conftest.py 共享夹具会话级跑一次,本测试逐 seed 取记录做
    断言(某 seed 崩溃时 re-raise 夹具留档异常)。种子集内逐局断言:

    断言面:①转场局升级批落地 ∧ 刷新可达;②等级轨迹单调(全 seed);
    ③间谍升级次数 = 重开次数 ∧ 入席+溢出 = 3×升级数;批级:转场形态
    在种子集内至少一局出现(①的可达性前提在批内有实例)。
    """
    total_transitions = 0
    total_upgrades = 0
    total_spy_deals = 0
    for seed in BATCH_SEEDS:
        entry = sim_batch_runs[seed]
        if entry.error is not None:
            raise entry.error
        run = entry.run
        counters = getattr(run.gs, 'strategy_state', None)
        counters = getattr(counters, 'cw4_counters', None) or {}
        disc = run.backend.disclosures

        def _n(key: str, _ct: dict = counters) -> int:
            return int(_ct.get(key) or 0)

        transitions = _n('levelup_transition_close')
        upgrades = _n('levelup_batch_emitted')
        reopens = _n('shop_randomized_reopen')
        spy_deals = int(disc.get('spy_deal_count') or 0)
        placed = int(disc.get('spy_steal_placed_count') or 0)
        overflow = int(disc.get('spy_steal_overflow_count') or 0)
        refresh_seen = _refresh_receipts(run.journal_rows)
        refresh_rejects = _refresh_rejects(counters)
        mono, trail = _level_trail_monotonic(run.journal_rows)

        # ①富余帧:转场局升级批落地 ∧ 刷新判据可达。
        if transitions > 0:
            assert upgrades > 0, \
                f'seed={seed} 转场 {transitions} 次但备战升级批零发射'
            assert refresh_seen > 0 or refresh_rejects > 0, \
                f'seed={seed} 转场局刷新判据不可达(零动作零拒因)'
        # ②人口位不饿死:等级轨迹单调。
        assert mono, f'seed={seed} 等级轨迹回退: {trail}'
        # ③随机态闭环:间谍升级次数 = 重开次数;入席+溢出 = 3×升级数。
        assert spy_deals == reopens, \
            f'seed={seed} 闭环破:间谍升级 {spy_deals} ≠ 重开 {reopens}'
        assert placed + overflow == 3 * spy_deals, \
            f'seed={seed} 偷取张数守恒破: 入席{placed}+溢出{overflow}' \
            f' ≠ 3×{spy_deals}'
        if placed > 0:
            assert any(r.get('row') == 'write'
                       and 'spy_steal' in str(r.get('evidence') or '')
                       for r in run.journal_rows), \
                f'seed={seed} 入席 {placed} 张但无备战席观察写行'
        total_transitions += transitions
        total_upgrades += upgrades
        total_spy_deals += spy_deals
        print(f'[prereg] seed={seed} trans={transitions} up={upgrades} '
              f'reopen={reopens} spy={spy_deals} placed={placed} '
              f'ovf={overflow} refresh={refresh_seen} '
              f'rej={refresh_rejects} lvl_mono={mono}')
    # 批级:升级转场形态在种子集内有实例(①的前提可达性),且转场与
    # 发射全批守恒(每次转场后继 = 备战批发射)。
    assert total_transitions > 0, '批内零升级转场(①无实例,换种子集)'
    assert total_upgrades >= total_transitions, \
        f'全批守恒破: 转场 {total_transitions} > 发射 {total_upgrades}'
    print(f'[prereg] TOTAL seeds={len(BATCH_SEEDS)} '
          f'trans={total_transitions} up={total_upgrades} '
          f'spy_deals={total_spy_deals}')


@pytest.mark.timeout(600)
def test_prereg_spy_closure_full_match(test_context: Any,
                                       monkeypatch: pytest.MonkeyPatch,
                                       tmp_path: Any) -> None:
    """③随机态闭环全跑实证(间谍供奉变体):策略 offer 候选桩化为单候选
    商业间谍(必选;真实 pick 判据在环),一整局内商业间谍升级回调与
    备战重开位逐次配对,偷取 3 张/次入席+溢出张数守恒可断言。

    批跑(上测)种子集内间谍零被选(0=0 恒等平凡成立),确定性闭环的
    单帧证据 = T-3 sim 闭环用例;本测试补全跑域的真实闭环实例。

    入席实例判据演变(T-432/T-434 连带,定向改期望):入席机制有无的
    精确锁 = test_sim_spy_levelup 具体牌断言(单帧域);全跑域「至少一次
    真实入席」原为种子实例快照(旧轨迹下唯一升级落店中拍、席有空位),
    T-432 把分支执行定案为结算时点(进窗拍)后本 seed 唯一升级恰逢席满
    全溢出(placed=0/ovf=3,实测),种子实例断言随已申报的轨迹位移失效
    ——判据改为与批跑同形的条件式(入席 > 0 局须有 spy_steal 观察写行),
    不钉轨迹统计值。信号来源代次(迭代 2026-09-23-invest-effects-calc
    T-434)恢复重开腿对节点时点源成立,守恒式 spy_deals == reopens 本
    seed 实测 1 == 1。"""
    from sr_od.application.currency_war.sim import cw_sim_backend

    def _forced_spy_offer(rng, excluded, forced_quality='', forced_slots=()):
        # forced_slots = 生产调用点(质量改写槽位)形参,本桩语义 = 单候选
        # 间谍强制,忽略之(T-427/T-35 批加参时本桩漏更,补形参消 TypeError)。
        return ('商业间谍',)

    monkeypatch.setattr(cw_sim_backend, 'sample_strategy_offer',
                        _forced_spy_offer)
    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.cw_screen.cw_screen_prep.'
        'CwScreenPrep._spec_invest_shop_stop_hook', lambda self: None)
    run = run_sim_full_match(test_context, monkeypatch, tmp_path,
                             seed=20261012, strategy_seed=20261012)
    disc = run.backend.disclosures
    counters = getattr(run.gs, 'strategy_state', None)
    counters = getattr(counters, 'cw4_counters', None) or {}
    spy_deals = int(disc.get('spy_deal_count') or 0)
    reopens = int(counters.get('shop_randomized_reopen') or 0)
    placed = int(disc.get('spy_steal_placed_count') or 0)
    overflow = int(disc.get('spy_steal_overflow_count') or 0)
    print(f'[prereg-spy] spy_deals={spy_deals} reopen={reopens} '
          f'placed={placed} ovf={overflow}')
    assert run.result is not None and run.result.success, '局未跑完'
    assert spy_deals >= 1, '供奉局零间谍升级(offer 桩未生效或策略弃选)'
    assert spy_deals == reopens, \
        f'闭环破:间谍升级 {spy_deals} ≠ 重开 {reopens}'
    assert placed + overflow == 3 * spy_deals, '偷取张数守恒破'
    if placed > 0:
        assert any(r.get('row') == 'write'
                   and 'spy_steal' in str(r.get('evidence') or '')
                   for r in run.journal_rows), \
            f'入席 {placed} 张但无备战席观察写行(spy_steal 证据)'
