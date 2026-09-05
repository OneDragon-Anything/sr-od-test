"""零刷新修复批测试(2026-09-03,ZERO_REFRESH_DIAG 两病灶+A/B 量具加固)。

覆盖:
- 病灶1:r1 发射位 V_GAP 槽位接线——None 期零漂移 fail-closed(计数键
  ``shop_r1_ev_unavailable`` 不变)+ 注入形态刷新链通(r1→r2);
- 病灶2:arm1_existence 板满 cap 口径(等级驱动 max_units,非固定槽表
  常数 10)——谓词单测 + 商店波 M3 发射行为锁;
- A/B 量具:动作族活性下限守卫正反测(饥饿 raise / 豁免过)+
  判前锁 v6 检查单(未全绿 raise / 全绿放行 / 类条款行不阻塞)。
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
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import predicates

# ===== 测试基建(与 test_cw4_shop_line 同款桩)=====

class _Cfg:

    def __init__(self, ev_arm: str = 'full') -> None:
        self.ev_arm = ev_arm


def _comp():
    names = [c.name for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
    return get_comp(names[0])


def _members(comp) -> list[str]:
    ms = list(comp.core_chars) + list(getattr(comp, 'shared_chars', []) or [])
    return list(dict.fromkeys(ms))


def _session(comp=None):
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof

    s = StrategySession()
    s.cw4_counters = {}
    s.target_comp = comp
    s.cw4_line_state = proof.LineState()
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


def _card(name: str, cost: int = 3, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _decide(state: GameState, session, cfg: _Cfg | None = None):
    from sr_od.application.currency_war.sim.engine_p1 import (
        sim_decision_registry,
    )

    strat = MandateV1Strategy(registry=sim_decision_registry())
    session.shop_state_frame = state
    return strat.decide_shop_screen(session, cfg or _Cfg())


def _afford_frame(gold: int, target_copies: int):
    """R1 可负担性行为锁帧(lv6,列车同行):合格集收缩到单目标成员
    (其余线成员 2★ 成型出域),目标 = 该级可追成员中期望刷次最小者;
    target_copies 控制缺口深浅(j=2 差 1 张 = 浅,j=0 差 3 张 = 深)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.data.cw_shop_odds import (
        expected_refreshes_for_card,
    )

    comp = _comp()
    members = _members(comp)
    target = min(
        (m for m in members
         if CHARACTERS[m].cost
         and 0.0 < expected_refreshes_for_card(
             6, CHARACTERS[m].cost, 2, 2) < float('inf')),
        key=lambda m: expected_refreshes_for_card(
            6, CHARACTERS[m].cost, 2, 2))
    others = [m for m in members if m != target]
    bench = ([_bc(target, slot=i + 1) for i in range(target_copies)]
             + [_bc(m, star=2, slot=i + target_copies + 1)
                for i, m in enumerate(others)])
    st = _state(gold=gold, bench=bench, level=6, hp=100)
    sess = _session(comp)
    sess.plane_lengths_seen = [9, 5, 7]
    return st, sess


# ===== :r1 发射位(ADR-0516 形式二可负担性重锚;V̄/V_GAP 槽位
# 比较项退役,槽位注入不再影响行为——锁重写为预算三档行为锁) =====

class TestR1VGapWiring:

    def test_near_interest_line_closed(self):
        """息线附近帧(gold=60,预算 10)不刷:总账(期望刷费+卡费+息损)
        > 10 ⇒ ``shop_r1_account_over_budget`` 分键(ADR-0516 修正③:
        刷新只花息线之上的溢余;旧 V_GAP None 期 fail-closed 语义随
        槽位比较项退役,由预算比较结构承载)。"""
        st, sess = _afford_frame(gold=60, target_copies=2)
        acts = _decide(st, sess)
        assert not [a for a in acts if isinstance(a, RefreshShop)]
        assert sess.cw4_counters.get('shop_r1_account_over_budget', 0) >= 1

    def test_large_surplus_opens_r1_into_r2(self):
        """大溢余开闸(gold=80,预算 30)+ 浅缺口成员(1费 j=2,lv3 账
        ≈ 11)⇒ r1 可负担性过、r2 预算门可批 ⇒ RefreshShop 发射
        (ADR-0516 形式二;槽位注入与否不影响行为——判据输入全为游戏
        定义量)。"""
        st, sess = _afford_frame(gold=80, target_copies=2)
        acts = _decide(st, sess)
        assert any(isinstance(a, RefreshShop) for a in acts)

    def test_r1_commitment_account_binds_deep_gap(self):
        """R1 总账约束力:深缺口帧(lv5 线成员含高费不可追件,留级账
        inf、升级账含 U_L 与大 E)总账远超预算 11 金:不刷 +
        `shop_r1_account_over_budget` 分键——EV 门有约束力的结构承载
        (ADR-0516;旧 V̄_net 比较项锁随链退役重锚)。"""
        st, sess = _afford_frame(gold=61, target_copies=0)
        acts = _decide(st, sess)
        assert not [a for a in acts if isinstance(a, RefreshShop)]
        assert sess.cw4_counters.get('shop_r1_account_over_budget', 0) >= 1

    def test_r2_budget_still_gates_low_gold(self):
        """防线分层:r2 预算门对低金帧独立拦截(金 < 预留 g*+rho + 刷价
        则不批;行为面 gold=1 不刷)——接线不等于旁路预算门(P40 R2 原语义,
        ADR-0516 保留声明)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
            refresh as crit_refresh,
        )

        assert not crit_refresh.r2_budget(1, 51, 2)
        assert crit_refresh.r2_budget(60, 51, 2)
        comp = _comp()
        bench = [_bc(m) for m in _members(comp)]
        st = _state(gold=1, bench=bench)   # 刷价 2,金 1 不足
        acts = _decide(st, _session(comp))
        assert not [a for a in acts if isinstance(a, RefreshShop)]


# ===== 病灶2:arm1_existence 板满 cap 口径 =====

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

    def test_cap_none_falls_back_to_fixed_capacity(self):
        """cap 缺读兜底固定槽表常数(保守端:宁漏不多)。"""
        board = [_bc('爻光') for _ in range(10)]
        bench = [_bc('爻光')]
        assert predicates.arm1_existence(
            10, [b.char_id for b in bench],
            [d.char_id for d in board], deploy_cap=None) is True
        assert predicates.arm1_existence(
            5, [b.char_id for b in bench],
            [d.char_id for d in board], deploy_cap=None) is False

    def test_m3_emits_when_board_full_at_cap(self):
        """商店波行为锁:板满于 cap(deployed=5/cap=5)+ bench 同阵营
        等待件 + 金够整批 ⇒ M3 LevelUpShop 发射(构造板面应触发场景)。
        (夹具补 hp=100:候选③批起 M3 消费血预算停升级门,hp 无真值帧
        fail-closed 拒升级——真值帧才是本锁要钉的语义。)"""
        comp = _comp()
        deployed = [_bc('爻光', slot=i + 1) for i in range(5)]
        bench = [_bc('爻光', slot=1)]
        st = _state(gold=8, bench=bench, deployed=deployed,
                    level=3, deploy_cap=5, xp=(0, 4), hp=100)
        acts = _decide(st, _session(comp))
        lv = [a for a in acts if isinstance(a, LevelUpShop)]
        assert lv and all(a.auth_basis.startswith('m3_batch:')
                          for a in lv)   # 三臂分键后带臂后缀(可归因)

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


# ===== A/B 量具:动作族活性下限守卫 + 判前锁 v6 检查单 =====

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

    def test_failclosed_family_exempt_passes(self, monkeypatch):
        """正例:V_GAP None 期刷新族零发射 ⇒ 豁免(fail-closed 降级)
        + 其余族齐全 ⇒ 守卫过。"""
        from sr_od.application.currency_war.sim import ab_core_swap

        provisional.reset('V_GAP')
        acts = [BuyCard(card=ShopCard(x=1, name='x', cost=1), reason='t'),
                LevelUpShop(cost=4), SellBench(bench_idx=0, income=1,
                                               expect='x')]
        monkeypatch.setattr(
            ab_core_swap, 'simulate_p1',
            _fake_sim(dict.fromkeys(range(10), acts)))
        report = ab_core_swap.action_family_liveness_gate(n=10, seed_base=0)
        assert report['ok']
        for arm in report['arms'].values():
            assert 'refresh' in arm['exempt']
            assert not arm['starved']

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

    def test_default_state_blocks_formal_ab(self, monkeypatch, tmp_path):
        """缺省态(词表/schema/申报全缺)⇒ 检查单未全绿,正式 A/B raise
        ——2026-09-03 零刷新事故的排程层防线(硬前置代码化)。"""
        from sr_od.application.currency_war.sim import ab_core_swap

        self._clear_registries(monkeypatch, tmp_path)
        provisional.reset('V_GAP')
        rows = ab_core_swap.v6_checklist()
        # 锁值 16→17(v6 判前锁清理批):行 17=V_GAP 事故防护
        # (IMPL_ADV_R200 症4 落地,清单单一源=IMPL_DESIGN §5.1 表+行 17);
        # 按锁纪律重推:清单新增判据行属设计演进,锁值随行数更新。
        assert len(rows) == 17
        with pytest.raises(RuntimeError, match='v6 检查单未全绿'):
            ab_core_swap.require_v6_green_for_formal_ab()

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

    def test_green_path_releases_formal_ab(self, monkeypatch, tmp_path):
        """全绿放行:文本锚(monkeypatch 仓库读)+ 全部 mark 行申报后
        ``require_v6_green_for_formal_ab`` 不 raise(类条款行已到期)。"""
        from sr_od.application.currency_war.sim import ab_core_swap

        self._clear_registries(monkeypatch, tmp_path)
        monkeypatch.setattr(
            ab_core_swap, '_text_of',
            lambda rel: 'mandate_v1 ev_arm v6 f7_contingency_armed '
                        'depsilon_advisor_violation f7_exempt_emission')
        for row in (2, 4, 5, 6, 10, 14, 15, 16):
            ab_core_swap.record_v6_landing(row, f'测试申报:{row}')
        # 行 17(症4,V_GAP 事故防护):走显式豁免批文通道放行——
        # 本测试的对象是「其余行全绿后 require 放行」的机械形态,
        # 注入通道的覆盖归 test_cw_v6_cleanup.py。
        ab_core_swap.record_formal_ab_exemption(
            'V_GAP', '测试豁免批文:v6 清理批锁值更新配套')
        ab_core_swap.record_batch_event('theta_calib')
        ab_core_swap.record_batch_event('eta_theta_calib')
        ab_core_swap.record_batch_event('chi_calib')
        ab_core_swap.record_batch_event('bandwidth_calib')
        ab_core_swap.record_batch_event('p_open')
        ab_core_swap.record_batch_event('switchline_anchor_batch')
        report = ab_core_swap.require_v6_green_for_formal_ab()
        assert report['ok']


# ===== sim 实跑验收(慢桶;全实测验收 ①②)=====

@pytest.mark.slow
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

    def test_none_period_zero_refresh_but_levelups_alive(self):
        """验收①:V_GAP=None 期刷新仍零(零漂移)+ arm1 修复后升级>0
        (池化口径;逐 seed 量级不对齐旧臂——seeds1-3 新核 ledger 空系
        修复前既有形态,见修复批报告的呈报项)。"""
        provisional.reset('V_GAP')
        lv_total = 0
        for seed in range(5):
            res = self._run(seed)
            assert res.refreshes == 0, seed
            lv_total += sum(v for k, v in self._counts(res).items()
                            if k in ('LevelUp', 'LevelUpShop'))
        assert lv_total > 0

    # (test_injected_vgap_refresh_chain_alive 已随 ADR-0516 退役删除:其前提
    #  = V_GAP 槽位注入开闸刷新链,V̄ 槽位比较项退役后注入不再影响行为;
    #  「刷新链活性」的行为锁重锚为帧级 test_large_surplus_opens_r1_into_r2
    #  ——大溢余 + 可追缺件 ⇒ r1 过 r2 批 ⇒ RefreshShop 发射。)
