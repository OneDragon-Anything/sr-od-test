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

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.decision.cw4 import shop as cw4_shop
from sr_od.application.currency_war.decision.cw4.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.decision.cw4 import mandate
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY, get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    LevelUp,
    OpenShop,
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


# ===== 候选① 供给确认加速(线重推对在店供给证据加权)=====

class TestSupplyConfirmAccel:

    def _pair_ist(self) -> IntentionState:
        ist = IntentionState()
        ist.p1_pair = ('列车同行', '希儿系')
        return ist

    def test_accel_evicts_at_half_threshold_on_supply_evidence(self) -> None:
        """现任方向(列车同行+希儿系)断供期间,方向外体系(仙舟)连续
        K=⌊5/2⌋=2 轮在店 ⇒ 断供证据确认,驱逐门槛减半:第 2 轮即驱逐
        (旧形态需等满 5 轮,g_20260904_054904 r4-r6 冻结窗病灶)。
        事件标签带 :accel 可归因。"""
        ist = self._pair_ist()
        st3 = _state(round_num=3, bench=[_bc('三月七', slot=1)],
                     shop=[SimpleNamespace(name='爻光')])
        ist = update_intention(st3, ist)
        assert '列车同行' not in ist.pair_evicted, \
            '确认证据仅 1 轮(<K)不得加速:门槛仍为驱逐阈值'
        st4 = _state(round_num=4, bench=[_bc('三月七', slot=1)],
                     shop=[SimpleNamespace(name='爻光')])
        ist = update_intention(st4, ist)
        assert '列车同行' in ist.pair_evicted, \
            '方向外体系供给连续 K 轮 ⇒ 断供驱逐门槛减半(提前重推)'
        # (第 4 轮即驱逐本身即加速证据:旧形态门槛 5,断供 2 轮绝不驱逐。
        #  last_event 的 :accel 标签可能被同轮 pair 派生事件覆写——与既有
        #  逐轮单事件语义一致,锁钉行为不钉单事件字符串。)
        assert ist.shop_supply_streak.get('仙舟', 0) >= 2, '夹具前提'

    def test_no_accel_without_supply_evidence(self) -> None:
        """负例:店上无任何体系件在售(非四体系件占店)⇒ 无确认证据,
        断供 2 轮不得驱逐(门槛维持原值,防噪声加速)。"""
        ist = self._pair_ist()
        for r in (3, 4):
            st = _state(round_num=r, bench=[_bc('三月七', slot=1)],
                        shop=[SimpleNamespace(name='黑塔')])
            ist = update_intention(st, ist)
        assert ist.pair_evicted == set(), \
            '无供给确认证据时断供 2 轮不得驱逐(门槛=驱逐阈值)'

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
    from sr_od.application.currency_war.decision.cw4 import proof
    s = StrategySession()
    s.cw4_counters = {}
    s.target_comp = comp
    s.cw4_line_state = proof.LineState()
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
        """席满不买,拒因串给 merge_bench_full(保守不腾席:合并买入
        非缺口义务,席满优先级归 M4 缺口面)。两份持有件放场上,
        bench 用其余成员+填充件占满(全员持有 ⇒ M4/funding 不触发)。"""
        comp = _comp()
        members = _members(comp)
        m = members[0]
        deployed = [_bc(m, slot=0), _bc(m, slot=1)]
        bench = [_bc(n, slot=i) for i, n in enumerate(members[1:])]
        j = len(bench)
        while len(bench) < BENCH_CAPACITY:
            bench.append(BenchChar(slot=j, char_id=f'填充件{j}', star=1))
            j += 1
        st = _shop_state(gold=30, shop=[ShopCard(x=100, name=m, cost=3)],
                         bench=bench, deployed=deployed)
        sess = _shop_session(comp)
        acts = _decide_shop(st, sess)
        assert not [a for a in acts if isinstance(a, BuyCard)
                    and a.reason == 'm2_merge_completion']
        assert sess.cw4_counters.get('merge_bench_full', 0) >= 1
        rejects = cw4_shop.shop_unbought_reasons(
            st, comp, tuple(members), [])
        assert rejects.get(m) == 'merge_bench_full'


# ===== 候选③ 危机带经验授权让位 =====

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
    sess.cw4_counters = {}
    st = _m3_state(plane, hp)
    frame = mandate.MandateFrame(
        gold=st.gold, level=st.level, bench=list(st.bench),
        deployed=[d for d in st.deployed if d is not None],
        deploy_cap=st.max_units(), node_type=st.node_type,
        stop_flag=False, k_members=(), round_num=st.round_num)
    out = mandate.run_mandate(frame, sess, state=st)
    return out, sess


class TestCrisisLevelSpendBlocked:

    def test_crisis_band_suspends_levelup_batch(self) -> None:
        """P2 危机带(hp≤41)内 M3 整批经验挂起+计数——授权让位保命面
        (P48 λ>0 段转化优先;g_20260904_054904 p2r1 hp=1 帧 36g 经验
        病灶)。"""
        out, sess = _run_mandate(2, 30)
        assert not [e for e in out
                    if isinstance(e.action, LevelUp)], \
            '危机带内不得发射整批经验(让位保命转化面)'
        assert sess.cw4_counters.get('crisis_level_spend_defer', 0) >= 1

    def test_zero_drift_outside_crisis_band(self) -> None:
        """带外(hp=100)零漂移:M3 照常发射(本批只挂危机带)。"""
        out, sess = _run_mandate(2, 100)
        assert any(isinstance(e.action, LevelUp) for e in out)
        assert sess.cw4_counters.get('crisis_level_spend_defer', 0) == 0

    def test_reconcile_declares_crisis_yield(self, monkeypatch) -> None:
        """授权面(spend_mode='level')在危机带被挂起 ⇒ 对账按
        crisis_yield 显式声明(非「未兑现故障」逐门定位)。"""
        from sr_od.application.currency_war.decision.cw4 import entry
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
        sess.cw4_counters = {}
        sess.v3_intention = IntentionState()
        out = entry.emit(obs, SimpleNamespace(), sess, None)
        un = sess.v3_posture_unfulfilled
        assert un is not None and un['reason'] == 'crisis_level_spend_blocked'
        assert un['action'] == 'crisis_yield'
        assert not any(isinstance(e.action, LevelUp) for e in out)


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__]))
