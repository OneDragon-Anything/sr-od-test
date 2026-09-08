"""零刷新修复批测试(2026-09-03 立档;2026-09-08 瘦身批覆盖对账后重锚)。

原批主治零刷新两病灶 + A/B 量具加固。瘦身批对账后本文件保留:
- r2_budget 纯数锁(全仓唯一直调;P40 R2 原语义,ADR-0516 保留声明)
  ——r1 门行为面(判据本体/门形态/必花域切分线/档案帧)归
  test_cw_vgap_frame_horizon、test_cw_must_spend_zone、
  test_cw_r1_refresh_ledger(亲读证实同断言面覆盖);
- 病灶2 arm1_existence 板满 cap 口径:谓词数学正反锁(全仓唯一直调)
  + M3「板未满不发射」反面锁——M3 发射正形归 test_cw4_shop_line
  (升级面主题文件)与 test_cw4_contracts(cap 喂入契约,prep/shop 两栈);
- A/B 量具:活性守卫饥饿 raise / 升级扫描(救低频活 / 耗尽仍 raise)/
  注入解豁免——豁免正形与 v6 缺省拦截 / 全绿放行归 test_cw_v6_cleanup;
  本文件另留 v6 类条款行(order)序锁与 mark 行证据硬化锁;
- 真引擎 sim 验收(慢桶):levelup 族活性端到端烟测。

退役指针(ADR-0516):V̄ 槽位比较项退役后注入不再影响行为——原
test_injected_vgap_refresh_chain_alive 已删,「刷新链活性」行为锁由
test_cw_vgap_frame_horizon::test_large_surplus_opens 承载;旧 V_GAP
None 期 fail-closed 语义由预算比较结构 + 必花域切分线(20 号稿)承载。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY, get_comp
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    LevelUpShop,
    RefreshShop,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import provisional
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import predicates

# ===== 测试基建(与 test_cw4_shop_line 同款桩)=====

class _Cfg:

    def __init__(self, ev_arm: str = 'full') -> None:
        self.ev_arm = ev_arm


def _comp():
    names = [c.name for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
    return get_comp(names[0])


def _session(comp=None):
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof

    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = comp
    state_of(s).cw4_line_state = proof.LineState()
    return s


def _state(gold: int = 30, shop=None, bench=None, deployed=None,
           level: int = 3, deploy_cap: int | None = None,
           xp: tuple[int, int] | None = None, hp: int = 100) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2, hp=hp)
    st.shop = shop if shop is not None else []
    st.bench = bench if bench is not None else []
    st.deployed = deployed if deployed is not None else []
    if deploy_cap is not None:
        st.deploy_cap = deploy_cap
    if xp is not None:
        st.xp_progress = xp
    return st


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _decide(state: GameState, session, cfg: _Cfg | None = None):
    from sr_od.application.currency_war.sim.engine_p1 import (
        sim_decision_registry,
    )

    strat = MandateV1Strategy(registry=sim_decision_registry())
    session.shop_state_frame = state
    return strat.decide_shop_screen(session, cfg or _Cfg())


# ===== r2 预算门纯数锁(P40 R2 原语义,ADR-0516 保留声明)=====

class TestR2BudgetGate:

    def test_gold_minus_reserve_gates_refresh_cost(self):
        """r2 预算门两向:金−预留 ≥ 刷价才批(全仓唯一直调锁)。
        门形态端到端面归 test_cw_vgap_frame_horizon(gold=40/50 关门)
        与 test_cw_must_spend_zone(域内可负担性硬闸仍辖)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
            refresh as crit_refresh,
        )

        assert not crit_refresh.r2_budget(1, 51, 2)
        assert crit_refresh.r2_budget(60, 51, 2)


# ===== 病灶2:arm1_existence 板满 cap 口径(谓词数学;全仓唯一直调)=====

class TestArm1CapSemantics:

    def test_board_full_at_level_cap_triggers(self):
        """板满=当前 cap(等级驱动)而非固定槽表 10:deployed==cap(5)
        + bench 等待件共享阵营/流派 ⇒ 真(修复点:旧语义此帧恒 False)。"""
        board = [_bc('爻光') for _ in range(5)]
        bench = [_bc('爻光')]
        assert predicates.arm1_existence(
            5, [b.char_id for b in bench],
            [d.char_id for d in board], deploy_cap=5) is True

    def test_board_not_full_below_cap_no_trigger(self):
        """板未满(deployed < cap)⇒ 假——升级前应先部署(M1 优先)。"""
        board = [_bc('爻光') for _ in range(3)]
        bench = [_bc('爻光')]
        assert predicates.arm1_existence(
            3, [b.char_id for b in bench],
            [d.char_id for d in board], deploy_cap=5) is False

    def test_m3_silent_when_board_below_cap(self):
        """反面:板未满(deployed=3/cap=5)同 bench/金 ⇒ M3 不发射
        (升级价值以「有等待件上不了场」为前提)。"""
        comp = _comp()
        deployed = [_bc('爻光', slot=i + 1) for i in range(3)]
        bench = [_bc('爻光', slot=1)]
        st = _state(gold=8, bench=bench, deployed=deployed,
                    level=3, deploy_cap=5, xp=(0, 4))
        acts = _decide(st, _session(comp))
        assert not [a for a in acts if isinstance(a, LevelUpShop)]


# ===== A/B 量具:动作族活性下限守卫(豁免正形/缺省拦截归
# test_cw_v6_cleanup)+ 判前锁 v6 检查单(order 序锁/证据硬化)=====

def _fake_sim(actions_by_seed):
    """造假 simulate_p1(返回 SimpleNamespace ledger/pool_fingerprint)。

    actions_by_seed: {seed: [动作对象,...]}——动作对象用真实类,
    计数按 type 名。
    """
    def _fake(seed, *, strategy=None, **_kw):
        acts = actions_by_seed.get(seed, [])
        return SimpleNamespace(ledger=[{'actions': acts}],
                               pool_fingerprint='fp-test')
    return _fake


class TestLivenessGate:

    def test_starved_family_raises(self, monkeypatch):
        """反例:卖族零发射且无 fail-closed 豁免 ⇒ raise 疑似结构性饥饿。"""
        from sr_od.application.currency_war.sim import ab_core_swap

        provisional.reset('V_GAP')
        monkeypatch.setattr(
            ab_core_swap, 'simulate_p1',
            _fake_sim({0: [RefreshShop(cost=2), BuyCard(
                card=ShopCard(x=1, name='x', cost=1), reason='t'),
                LevelUpShop(cost=4)]}))
        with pytest.raises(RuntimeError, match='结构性饥饿'):
            ab_core_swap.action_family_liveness_gate(n=1, seed_base=0)

    def test_escalation_rescues_rare_alive_family(self, monkeypatch):
        """升级扫描(FIX_REVIEW 复审返工批):首段 n 局零发射的族在追加
        seed 段活过 ⇒ 守卫过(区分「低频活」与「真死路」;sell 族
        4/30 局实证形态)+ escalated_runs 披露。"""
        from sr_od.application.currency_war.sim import ab_core_swap

        provisional.reset('V_GAP')
        acts = [BuyCard(card=ShopCard(x=1, name='x', cost=1), reason='t'),
                LevelUpShop(cost=4), RefreshShop(cost=2)]
        by_seed = dict.fromkeys(range(10), acts)
        # 升级段第 3 局(seed=12)出现 sell——低频活
        by_seed[12] = acts + [SellBench(bench_idx=0, income=1, expect='x')]
        monkeypatch.setattr(ab_core_swap, 'simulate_p1', _fake_sim(by_seed))
        report = ab_core_swap.action_family_liveness_gate(n=10, seed_base=0)
        assert report['ok']
        for arm in report['arms'].values():
            assert not arm['starved']
        assert any(arm['escalated_runs'] > 0
                   for arm in report['arms'].values())

    def test_escalation_exhausted_still_raises(self, monkeypatch):
        """升级段耗尽仍零发射 ⇒ 照 raise(升级只救低频活,不掩盖死路)。"""
        from sr_od.application.currency_war.sim import ab_core_swap

        provisional.reset('V_GAP')
        monkeypatch.setattr(ab_core_swap, 'LIVENESS_ESCALATION_N', 3)
        acts = [BuyCard(card=ShopCard(x=1, name='x', cost=1), reason='t'),
                LevelUpShop(cost=4), RefreshShop(cost=2)]
        monkeypatch.setattr(
            ab_core_swap, 'simulate_p1',
            _fake_sim(dict.fromkeys(range(13), acts)))
        with pytest.raises(RuntimeError, match='结构性饥饿'):
            ab_core_swap.action_family_liveness_gate(n=10, seed_base=0)

    def test_opened_slot_removes_exemption(self, monkeypatch):
        """V_GAP 注入后豁免失效:刷新族零发射 ⇒ raise(开闸路径存在
        却零发射=饥饿,豁免只覆盖 fail-closed 降级态)。"""
        from sr_od.application.currency_war.sim import ab_core_swap

        provisional.reset('V_GAP')
        try:
            provisional.inject('V_GAP', provisional.CalibValue(
                value=10.0, injected_form=True))
            acts = [BuyCard(card=ShopCard(x=1, name='x', cost=1),
                            reason='t'),
                    LevelUpShop(cost=4), SellBench(bench_idx=0, income=1,
                                                   expect='x')]
            monkeypatch.setattr(
                ab_core_swap, 'simulate_p1',
                _fake_sim(dict.fromkeys(range(10), acts)))
            with pytest.raises(RuntimeError, match='结构性饥饿'):
                ab_core_swap.action_family_liveness_gate(n=10, seed_base=0)
        finally:
            provisional.reset('V_GAP')


class TestV6Checklist:

    @staticmethod
    def _clear_registries(monkeypatch=None, tmp_path=None):
        """隔离:v6 检查单的批事件/申报登记系模块级易失态,逐测试清场
        (测试纪律:改全局态必须复原)。v6 清理批(2026-09-11)扩:豁免
        批文/活性豁免快照同辖;evidence 持久化落盘(v6 清理批增补)⇒
        传 monkeypatch+tmp_path 时把落盘文件重定向到临时目录(测试零
        真实 .debug 写入,且隔离真实落盘档的回读串扰)。"""
        from sr_od.application.currency_war.sim import ab_core_swap

        ab_core_swap._BATCH_EVENTS.clear()
        ab_core_swap._V6_LANDINGS.clear()
        ab_core_swap._FORMAL_AB_EXEMPTIONS.clear()
        ab_core_swap._LIVENESS_EXEMPT_DISCLOSURE.clear()
        if monkeypatch is not None and tmp_path is not None:
            monkeypatch.setattr(ab_core_swap, '_V6_LANDING_FILE_OVERRIDE',
                                tmp_path / 'v6_landing.jsonl')

    def test_class_clause_rows_do_not_block(self, monkeypatch, tmp_path):
        """类条款行(R94-6:行 3/8/9/12 等):批事件未到期 ⇒ 「未到期」
        不阻塞;到期且序合 ⇒ 已落地。"""
        from sr_od.application.currency_war.sim import ab_core_swap

        self._clear_registries(monkeypatch, tmp_path)
        rows = {r['row']: r for r in ab_core_swap.v6_checklist()}
        assert rows[3]['status'].startswith('未到期')
        ab_core_swap.record_batch_event('theta_calib')
        ab_core_swap.record_batch_event('p_open')
        rows = {r['row']: r for r in ab_core_swap.v6_checklist()}
        assert rows[3]['status'] == '已落地'

    def test_mark_row_requires_nonempty_evidence(self, monkeypatch, tmp_path):
        """v6 mark 行硬化(FIX_REVIEW_20260903 场景 B 复验):evidence
        缺/空/纯空白 ⇒ record_v6_landing raise;绕过入口直写空证据 ⇒
        checklist 行红(不因「申报过」即绿)。"""
        from sr_od.application.currency_war.sim import ab_core_swap

        self._clear_registries(monkeypatch, tmp_path)
        for bad in ('', '   '):
            with pytest.raises(ValueError, match='evidence'):
                ab_core_swap.record_v6_landing(4, bad)
        # 入口拒绝后未登记
        rows = {r['row']: r for r in ab_core_swap.v6_checklist()}
        assert rows[4]['status'] == '未落地'
        # 绕过入口直写空证据(对抗形态):checklist 独立复验=行红
        ab_core_swap._V6_LANDINGS[4] = '   '
        rows = {r['row']: r for r in ab_core_swap.v6_checklist()}
        assert rows[4]['status'] == '未落地'
        del ab_core_swap._V6_LANDINGS[4]   # 清对抗直写,走正规入口
        # 非空证据:绿 + 证据文本随行输出(可审计)
        ab_core_swap.record_v6_landing(4, '锚批/判读批拆半预注册,档=X')
        rows = {r['row']: r for r in ab_core_swap.v6_checklist()}
        assert rows[4]['status'] == '已落地'
        assert rows[4]['evidence'].startswith('锚批/判读批')


# ===== 真引擎 sim 验收(levelup 族活性端到端烟测;2026-09-08 实测
# call≈0.35s,原类级 slow 标记已摘——远低于 2s 桶线,快速层回收;
# 引擎后续演进若实测超 2s 再按纪律复测入桶)=====

class TestZeroRefreshFixSimAcceptance:

    SIM_KW = {'pool': 'snapshot', 'planes': 1, 'use_refresh': True, 'invest': False,
                  'p2_combat': None, 'synthesis_chain': False,
                  'equip_wear_effect': 0.0}

    @staticmethod
    def _run(seed: int):
        import logging

        from sr_od.application.currency_war.sim.engine_p1 import (
            sim_decision_registry,
            simulate_p1,
        )

        logging.disable(logging.CRITICAL)
        try:
            return simulate_p1(
                seed, strategy=MandateV1Strategy(
                    registry=sim_decision_registry()),
                **TestZeroRefreshFixSimAcceptance.SIM_KW)
        finally:
            logging.disable(logging.NOTSET)

    def _counts(self, res):
        # ledger 行的 actions 可能是动作对象或已序列化 dict(键 __type__)
        c: dict[str, int] = {}
        for row in (res.ledger or []):
            for a in (row.get('actions') or []):
                t = (a.get('__type__') if isinstance(a, dict)
                     else type(a).__name__)
                c[t] = c.get(t, 0) + 1
        return c

    def test_none_period_levelups_alive(self):
        """真引擎端到端烟测(慢桶;全仓唯一真跑 mandate_v1 的动作族
        活性断言):V_GAP=None 缺省态真跑 5 seed,levelup 族合计发射
        >0(病灶2 arm1 修复的整合面回归锁;frame 级发射锁归
        test_cw4_shop_line)。刷新面按 20 号稿/ADR-0516 已合法化
        (必花域内 r2 硬闸承载),原「验收①零漂移」断言随设计退役,
        不再断言零刷新。"""
        provisional.reset('V_GAP')
        lv_total = 0
        for seed in range(5):
            res = self._run(seed)
            lv_total += sum(v for k, v in self._counts(res).items()
                            if k in ('LevelUp', 'LevelUpShop'))
        assert lv_total > 0
