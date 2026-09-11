"""sim71 批观测键锁面(form_ok 死镜像处置 + 发射帧滞留金 + 卖→买回分键)。

背景 = 进度树 sim71 批判读行(观测键合并小批,纯遥测零语义):
1. form_ok 死镜像处置:写端接 ``cw_launch_admission.readiness_form_ok``
   板面现读(与发射 armed 判据同式同源,零第二实现);
2. 发射帧滞留金观测键 ``launch_frame_idle_gold``:发射帧短路备战动作链
   → 既有金出口键全不计发射帧金,双层披露 = launch 行内 idle_gold
   (逐帧)+ cw4_counters 累计键(经 obs.cw4_counters 轮差分入账本);
3. 同轮卖→买回分键投影:实例级 obs.sell_buyback_loops + 局级
   cw4_counters 两键(sell_buyback_count / sell_buyback_net_gold)。

锁口径 = 各键正确性 + 缺省零漂移(容器/comp 缺席静默,不炸不虚构)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_board_state import (
    board_state_bridge as _bridge,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.sim.engine_p1 import (
    project_sell_buyback,
    sim_decision_registry,
    simulate_p1,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

SIM_KW = {'pool': 'snapshot', 'planes': 2, 'use_refresh': True,
          'invest': False, 'p2_combat': None, 'synthesis_chain': False,
          'equip_wear_effect': 0.0}
CFG_SKEL = SimpleNamespace(ev_arm='skeleton_only')

_SEED_CACHE: dict[int, object] = {}

# 发射单锚(README 纪律#12):奖励帧抑制生效(2026-09-08 奖励帧策略审查
# ·可见性批)后旧锚 seed 0 零发射事件(发射时点位移,采样缺陷非机制
# 回归)。探针窗口 seed 0-39 命中 23/40;取 seed 5(发射行 5、溢出帧 4)。
_LAUNCH_SEED: int = 5


def _seeded_result(seed: int):
    if seed not in _SEED_CACHE:
        _SEED_CACHE[seed] = simulate_p1(seed, pool='snapshot')
    return _SEED_CACHE[seed]


def _run(seed: int, sess: StrategySession):
    return simulate_p1(seed, strategy=MandateV1Strategy(
        registry=sim_decision_registry()), session=sess,
        config=CFG_SKEL, **SIM_KW)


def _fake_strat():
    """write_shop_mirrors 直调载体(抽象基类不可实例化,用 mandate 桥)。"""
    return MandateV1Strategy(registry=sim_decision_registry())


class _FakeComp:
    """最小 Comp 形状(form_progress 只读 form_tiers)。"""

    def __init__(self, tiers: dict[str, int]):
        self.form_tiers = tiers
        self.core_chars: list[str] = []
        self.shared_chars: list[str] = []


class TestFormOkPresentReadWriter:
    """锁①:form_ok 写端正确性 + 缺省零漂移(直调写端,确定性)。"""

    def _write(self, board: dict[str, int], comp):
        from sr_od.application.currency_war.kernel.cw_launch_admission import (
            readiness_form_ok,
        )
        sess = StrategySession()
        state_of(sess).target_comp = comp
        # 镜像键缺省恒 False(ADR-0583 后无生命周期钩子写初值;直调语境先补)
        state_of(sess).v3_form_ok = False
        st = SimpleNamespace(board=board, bench=[None] * 9,
                             deployed=[None] * 10, plane=1, round_num=1)
        assert state_of(sess).v3_form_ok is False
        _fake_strat().write_shop_mirrors(st, sess)
        return sess, readiness_form_ok(_bridge(st), comp)

    def test_writer_matches_kernel_present_read(self):
        """写端输出 ≡ readiness_form_ok 直调(同式同源锁;满/缺两侧)。"""
        comp3 = _FakeComp({'仙舟': 3})
        sess, expected = self._write({'仙舟': 3}, comp3)
        assert state_of(sess).v3_form_ok is True and expected is True
        sess, expected = self._write({'仙舟': 2}, comp3)
        assert state_of(sess).v3_form_ok is False and expected is False

    def test_writer_none_comp_default_false(self):
        """缺省零漂移:target_comp None(未锁线)→ 现读 False,不炸。"""
        sess, expected = self._write({'仙舟': 3}, None)
        assert state_of(sess).v3_form_ok is False and expected is False


class TestLaunchFrameIdleGold:
    """锁②:发射帧滞留金键——逐帧回显 + 累计计数器一致性 + 缺省零漂移。"""

    def test_launch_rows_carry_idle_gold(self):
        """回显锁:每个发射行带 idle_gold(非负 int;缺键 = 观测位断线)。"""
        seen = False
        for seed in range(6):
            for row in _seeded_result(seed).ledger:
                lg = row.get('launch')
                if lg is None:
                    continue
                seen = True
                assert isinstance(lg.get('idle_gold'), int) \
                    and lg['idle_gold'] >= 0, row['round_num']
        assert seen, '采样 6 seed 零发射帧(采样缺陷,需换窗口)'

    def test_counter_accumulates_launch_gold(self, monkeypatch):
        """累计键一致性:强制武装下,cw4_counters.launch_frame_idle_gold
        ≡ Σ 发射帧 idle_gold(经 obs.cw4_counters 差分同路)。"""
        from sr_od.application.currency_war.kernel import cw_launch_admission
        real = cw_launch_admission.readiness_launch_decision

        def _force_armed(state, comp, *, line_members):
            out = real(state, comp, line_members=line_members)
            if comp is not None and state is not None:
                out['armed'] = True
            return out

        monkeypatch.setattr(cw_launch_admission,
                            'readiness_launch_decision', _force_armed)
        sess = StrategySession()
        state_of(sess).cw4_counters = {}
        r = _run(0, sess)
        launch_gold = sum((row.get('launch') or {}).get('idle_gold', 0)
                          for row in r.ledger if row.get('launch'))
        assert launch_gold > 0, '强制武装后零发射金(接线断)'
        assert state_of(sess).cw4_counters.get('launch_frame_idle_gold') == launch_gold

    def test_no_counters_container_no_crash(self):
        """缺省零漂移:引擎守卫对容器缺席静默(默认路径无 mandate 桥
        建容器,发射观测块不炸、账本正常产出)。"""
        r = simulate_p1(_LAUNCH_SEED, pool='snapshot')
        assert any(row.get('launch') for row in r.ledger), \
            '默认路径零发射帧(发射锚漂移,重跑探针更新 _LAUNCH_SEED)'
        for row in r.ledger:
            assert isinstance(
                (row.get('launch') or {}).get('idle_gold', 0), int)


class TestSellBuybackProjection:
    """锁③:卖→买回投影正确性(纯函数)+ 缺省零漂移。"""

    @staticmethod
    def _sell(name, income):
        return {'__type__': 'SellBench', 'name': name, 'income': income}

    @staticmethod
    def _buy(name, cost, count=None):
        a = {'__type__': 'BuyCard', 'card': {'name': name, 'cost': cost}}
        if count is not None:
            a['count'] = count
        return a

    def test_loop_detected_net_gold(self):
        """卖 3 → 买 5 = 一笔回环,net = +2(Σ买价−卖返口径)。"""
        loops = project_sell_buyback(
            [self._sell('甲', 3), self._buy('甲', 5)])
        assert loops == [{'name': '甲', 'sell_income': 3,
                          'buy_cost': 5, 'net_gold': 2}]

    def test_buy_before_sell_not_loop(self):
        """买先于卖不构成回环(登记序保证)。"""
        assert project_sell_buyback(
            [self._buy('甲', 5), self._sell('甲', 3)]) == []

    def test_merge_buy_counts_k_cost(self):
        """合并买 count=k:买价 = 单价×k(金真实流出口径)。"""
        loops = project_sell_buyback(
            [self._sell('甲', 3), self._buy('甲', 3, count=2)])
        assert loops[0]['buy_cost'] == 6 and loops[0]['net_gold'] == 3

    def test_resell_rebuy_each_counted(self):
        """再卖再买各记各笔(第一笔回环后登记清空)。"""
        loops = project_sell_buyback(
            [self._sell('甲', 1), self._buy('甲', 4),
             self._sell('甲', 2), self._buy('甲', 5)])
        assert [lp['net_gold'] for lp in loops] == [3, 3]
        assert loops[1]['sell_income'] == 2

    def test_empty_and_unrelated(self):
        """空动作 / 无回环动作流 → 空投影(不占判读视野)。"""
        assert project_sell_buyback([]) == []
        assert project_sell_buyback(
            [self._buy('甲', 5), self._sell('乙', 3)]) == []
        assert project_sell_buyback(None) == []

    def test_engine_counters_and_obs_projection(self, monkeypatch):
        """引擎接线(写点真链,engine_p1 逐轮投影非空即累计):obs.sell_buyback
        _loops 带引擎补全明细(round/node);cw4_counters 差分两键值精确
        (count=笔数 / net=Σnet_gold)。投影函数本体替换为剧本回环(纯函数
        正确性由上五锁承),写点链全真——写点被删或绕过时本锁红。"""
        from sr_od.application.currency_war.sim import engine_p1
        loop = {'name': '甲', 'sell_income': 3, 'buy_cost': 5, 'net_gold': 2}
        calls = {'n': 0}

        def _scripted(_acts):
            calls['n'] += 1
            return [dict(loop)] if calls['n'] == 1 else []

        monkeypatch.setattr(engine_p1, 'project_sell_buyback', _scripted)

        sess = StrategySession()
        state_of(sess).cw4_counters = {}
        r = _run(0, sess)
        hit = [row for row in r.ledger
               if (row.get('obs') or {}).get('sell_buyback_loops')]
        assert len(hit) == 1, f'剧本回环恰一轮入账本: 实际 {len(hit)} 轮带明细'
        (lp,) = hit[0]['obs']['sell_buyback_loops']
        assert {'name', 'round', 'node', 'sell_income', 'buy_cost',
                'net_gold'} <= set(lp)
        assert lp['net_gold'] == 2
        ct = state_of(sess).cw4_counters
        assert ct.get('sell_buyback_count') == 1
        assert ct.get('sell_buyback_net_gold') == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
