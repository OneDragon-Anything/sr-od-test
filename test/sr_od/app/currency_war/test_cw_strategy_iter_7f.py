# -*- coding: utf-8 -*-
"""第 7 局复盘前三高候选修复锁(策略迭代批 iter_7f)。

设计出处:实机局复盘 g_20260904_054904(§八候选 1-3)——
①线重推供给确认加速(PAIR_SUPPLY_CONFIRM_ROUNDS,零新自由参数=
驱逐阈值减半;冻结窗 p1r3-r6 病灶);
②升星合并完成买入(M2b 义务通道,dd-032 merge_completion_exempt
同款判读;P20/P30 星级价值语境);
③危机带经验授权让位(level_spend_blocked = 血预算停升级门 cw4 接线
∪ p2_crisis_band,P21/P48 λ>0 段单一语义族)。
锁的是策略意图(断供证据被供给确认加速/合并件必须有人买/危机带不买
经验),不锁具体发牌。
"""
from __future__ import annotations
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import state_of

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop as cw4_shop
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import mandate
from sr_od.application.currency_war.strategies.impl.cw_strategy import StrategySession
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY, get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    LevelUp,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)


def _bc(name: str, slot: int = 0, star: int = 1) -> BenchChar:
    ch = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name, star=star,
                     faction=(ch.factions or ['?'])[0])


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 3, 'gold': 42, 'level': 4,
            'board': {}, 'bench': [], 'shop': [], 'hp': 75,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


# ===== 候选① 供给计数器(ADR-0519 重锚:断供驱逐已退役)=====================
# 旧「供给确认加速驱逐」族(驱逐门槛减半/加速触发)已随 PAIR_DROUGHT_
# EVICT_ROUNDS 未证阈值整体退役(ADR-0519「未证即退役」);本节锁残存
# 语义:计数器累积/冻结。「断供永不换向(pair_evicted 恒空)」面由
# test_cw_w633_migration_b3.py::test_pair_drought_counters_never_evict
# 承载(超集:另辖锁线门槛 1.0 空窗面),本文件原同型测已删。

class TestSupplyCounters:

    def _pair_ist(self) -> IntentionState:
        ist = IntentionState()
        ist.p1_pair = ('列车同行', '希儿系')
        return ist

    def test_supply_streak_accumulates(self) -> None:
        """方向外体系(仙舟)连续在店 ⇒ shop_supply_streak 逐轮 +1
        (计数器语义保留,决策消费已退役)。"""
        ist = self._pair_ist()
        st3 = _state(round_num=3, bench=[_bc('三月七', slot=1)],
                     shop=[SimpleNamespace(name='爻光')])
        ist = update_intention(st3, ist)
        n1 = ist.shop_supply_streak.get('仙舟', 0)
        assert n1 >= 1, '在店轮 streak 累积'
        st4 = _state(round_num=4, bench=[_bc('三月七', slot=1)],
                     shop=[SimpleNamespace(name='爻光')])
        ist = update_intention(st4, ist)
        assert ist.shop_supply_streak.get('仙舟', 0) > n1

    def test_supply_streak_frozen_on_shopless_round(self) -> None:
        """无商店语境轮(补给绕行)供给 streak 冻结不重置——窗口未开
        既非证据也非反驳(LineTrack 冻结语义同款)。"""
        ist = self._pair_ist()
        st = _state(round_num=3, shop=[SimpleNamespace(name='爻光')])
        ist = update_intention(st, ist)
        n0 = ist.shop_supply_streak.get('仙舟', 0)
        st_empty = _state(round_num=4, shop=[])   # 补给绕行:无商店
        ist = update_intention(st_empty, ist)
        assert ist.shop_supply_streak.get('仙舟', 0) == n0, \
            '无商店轮 streak 必须冻结(清零=把非证据轮当反驳)'


# ===== 候选② 升星合并完成买入(M2b)=====

def _comp():
    names = [c.name for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
    return get_comp(names[0])


def _members(comp) -> list[str]:
    ms = list(comp.core_chars) + list(getattr(comp, 'shared_chars', []) or [])
    return list(dict.fromkeys(ms))


def _shop_session(comp) -> StrategySession:
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = comp
    state_of(s).cw4_line_state = proof.LineState()
    return s


def _shop_state(gold: int = 30, shop=None, bench=None, deployed=None,
                level: int = 3) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2)
    st.shop = shop if shop is not None else []
    st.bench = bench if bench is not None else []
    st.deployed = deployed if deployed is not None else []
    return st


def _decide_shop(state: GameState, session: StrategySession):
    from sr_od.application.currency_war.sim.engine_p1 import (
        sim_decision_registry,
    )
    strat = MandateV1Strategy(registry=sim_decision_registry())
    session.shop_state_frame = state
    return strat.decide_shop_screen(session, SimpleNamespace(ev_arm='full'))


class TestMergeCompletionBuy:

    def test_third_copy_bought_as_merge_completion(self) -> None:
        """已持 2 张同名同星 1★、第三张在店 affordable ⇒ 必须买入
        (reason=m2_merge_completion 可归因)——旧形态 owned 拒后无人买,
        同帧经验支出=优先级倒置(g_20260904_054904 p2r1)。"""
        comp = _comp()
        m = _members(comp)[0]
        st = _shop_state(gold=30, shop=[ShopCard(x=100, name=m, cost=3)],
                         bench=[_bc(m, slot=1), _bc(m, slot=2)])
        acts = _decide_shop(st, _shop_session(comp))
        merge_buys = [a for a in acts if isinstance(a, BuyCard)
                      and a.reason == 'm2_merge_completion']
        assert any(b.card.name == m for b in merge_buys), \
            '合并完成件(第三张)在店 affordable 必须买入'

    def test_merge_buy_skipped_when_two_star_owned(self) -> None:
        """已持 2★ 成件 ⇒ 升星完成,不再买入(出合格集,与 R1 合格集
        同口径)。"""
        comp = _comp()
        m = _members(comp)[0]
        st = _shop_state(gold=30, shop=[ShopCard(x=100, name=m, cost=3)],
                         bench=[_bc(m, slot=1), _bc(m, slot=2, star=2)])
        acts = _decide_shop(st, _shop_session(comp))
        assert not [a for a in acts if isinstance(a, BuyCard)
                    and a.reason == 'm2_merge_completion']

    def test_merge_buy_gold_gated_and_labeled(self) -> None:
        """金不足不买,拒因串必须给 merge_unaffordable(判读可归因,
        禁退回中性 owned)。"""
        comp = _comp()
        m = _members(comp)[0]
        st = _shop_state(gold=1, shop=[ShopCard(x=100, name=m, cost=3)],
                         bench=[_bc(m, slot=1), _bc(m, slot=2)])
        sess = _shop_session(comp)
        acts = _decide_shop(st, sess)
        assert not [a for a in acts if isinstance(a, BuyCard)
                    and a.reason == 'm2_merge_completion']
        rejects = cw4_shop.shop_unbought_reasons(
            st, comp, tuple(_members(comp)), [])
        assert rejects.get(m) == 'merge_unaffordable', \
            f'合并完成件金不足拒因须细分,实得 {rejects.get(m)}'

    def test_merge_buy_bench_full_labeled(self) -> None:
        """席满合并完成买(§3.6 满栏例外对齐后重推导):同名同星 1★ ×2
        + 第三张在店 = 买入即合成帧,免 bench_free 门——满栏直发
        m2_merge_completion,不再有 merge_bench_full 拒因键(机制对齐,
        非行为放宽;14号稿 §3.6)。两份持有件放场上,bench 用其余成员+
        2★ 填充件占满(全员持有 ⇒ M4/funding 不触发,隔离 M2b 单点)。"""
        comp = _comp()
        members = _members(comp)
        m = members[0]
        deployed = [_bc(m, slot=0), _bc(m, slot=1)]
        bench = [_bc(n, slot=i, star=2) for i, n in enumerate(members[1:])]
        j = len(bench)
        while len(bench) < BENCH_CAPACITY:
            bench.append(BenchChar(slot=j, char_id=f'填充件{j}', star=2))
            j += 1
        st = _shop_state(gold=30, shop=[ShopCard(x=100, name=m, cost=3)],
                         bench=bench, deployed=deployed)
        sess = _shop_session(comp)
        acts = _decide_shop(st, sess)
        assert 'merge_bench_full' not in state_of(sess).cw4_counters, \
            '满栏例外后该键不再产生(§3.6)'
        merge_buys = [a for a in acts
                      if isinstance(a, BuyCard)
                      and a.reason == 'm2_merge_completion']
        assert merge_buys, '满栏合成触发帧直发合并完成买(§3.6)'
        rejects = cw4_shop.shop_unbought_reasons(
            st, comp, tuple(members), [])
        # 应-1:拒因与同帧实际动作一致——满栏合成帧直发合并买(§3.6),
        # 静态拒因 = 'merge_ready'(应发语义),非退役的 merge_bench_full
        assert rejects.get(m) == 'merge_ready'


# ===== 候选③ 危机带经验授权让位 =====
# 带内正向面(挂起+计数,生产门 mandate.py M3 块 elif 臂,节点无关)由
# test_cw4_mandate_v1.py::TestRewardNodeSuppress(分键对照腿)与
# test_cw_l3_prep_must_spend_latch.py(fresh/latch-expiry 两测,counter==1)
# 承载且断言更强;本文件原同型测(>=1)已删,留带外零漂移与对账让位两面。

def _m3_state(plane: int, hp: int) -> GameState:
    """arm1 存在态(板满+bench 等待件共享体系)+ 整批经验可负担。"""
    st = GameState(plane=plane, round_num=2, gold=8, level=3, hp=hp)
    st.node_type = 'battle'
    st.xp_progress = (0, 4)
    st.deployed = [_bc('爻光', slot=i) for i in range(10)]
    st.bench = [_bc('爻光', slot=0)]
    return st


def _run_mandate(plane: int, hp: int):
    sess = StrategySession()
    state_of(sess).cw4_counters = {}
    st = _m3_state(plane, hp)
    frame = mandate.MandateFrame(
        gold=st.gold, level=st.level, bench=list(st.bench),
        deployed=[d for d in st.deployed if d is not None],
        deploy_cap=st.max_units(), node_type=st.node_type,
        stop_flag=False, k_members=(), round_num=st.round_num)
    out = mandate.run_mandate(frame, sess, state=st)
    return out, sess


class TestCrisisLevelSpendBlocked:

    def test_zero_drift_outside_crisis_band(self) -> None:
        """带外(hp=100)零漂移:M3 照常发射(本批只挂危机带)。"""
        out, sess = _run_mandate(2, 100)
        assert any(isinstance(e.action, LevelUp) for e in out)
        assert state_of(sess).cw4_counters.get('crisis_level_spend_defer', 0) == 0

    def test_reconcile_declares_crisis_yield(self, monkeypatch) -> None:
        """授权面(spend_mode='level')在危机带被挂起 ⇒ 对账按
        crisis_yield 显式声明(非「未兑现故障」逐门定位)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import entry
        from sr_od.application.currency_war.kernel import cw_economy

        monkeypatch.setattr(
            cw_economy, 'get_node_goal',
            lambda *a, **k: SimpleNamespace(spend_mode='level',
                                            target_level=6))
        st = _m3_state(2, 30)
        obs = SimpleNamespace(
            boxes=(), tomes=(), spheres=(), event_overlay='',
            bench_chars=tuple(b for b in st.bench if b is not None),
            deployed_chars=tuple(d for d in st.deployed if d is not None),
            deploy_vacancy=0, state=st)
        sess = StrategySession()
        state_of(sess).cw4_counters = {}
        state_of(sess).v3_intention = IntentionState()
        out = entry.emit(obs, SimpleNamespace(), sess, None)
        un = state_of(sess).v3_posture_unfulfilled
        assert un is not None and un['reason'] == 'crisis_level_spend_blocked'
        assert un['action'] == 'crisis_yield'
        assert not any(isinstance(e.action, LevelUp) for e in out)


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__]))
