"""v6 清理批测试(2026-09-11;IMPL_ADV_R200 症4/症7)。

覆盖:
- 症4:v6 清单行 17(V_GAP 注入态或显式豁免批文)——零刷新事故配置
  复演必红 + 注入/豁免两通道放行 + 豁免批文非空纪律;
- 症4 强制消费:活性守卫豁免快照落档 + prereg manifest 形态;
- 症7:归因域/活性证据辖域限定随守卫产物输出;
- ab_judge v6 自测复跑(判读器迁移);
- 动作族活性下限守卫:饥饿 raise / 升级扫描(救低频活 / 耗尽仍 raise)/
  V_GAP 注入解豁免(2026-09-09 合并批自 test_cw_zero_refresh 迁入,
  原壳退役后本文件为其唯一载体;原壳其余簇去向:r2_budget 纯数锁 →
  test_cw_vgap_frame_horizon,arm1 谓词数学/M3 反面锁 → test_cw_contracts);
- v6 检查单类条款行序锁 + mark 行证据硬化锁(同上迁入);
- 真引擎 levelup 族活性端到端烟测(同上迁入,原 TestZeroRefreshFixSim
  Acceptance,全仓唯一真跑 mandate_v1 的动作族活性断言)。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel.cw_vocab import (
    BuyCard,
    LevelUpShop,
    RefreshShop,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import provisional
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)


def _fake_sim(actions_by_seed):
    """造假 simulate_p1(活性守卫/检查单测试共用的进程内桩;动作对象用
    真实类,计数按 type 名)。"""

    from types import SimpleNamespace

    def _fake(seed, *, strategy=None, **_kw):
        acts = actions_by_seed.get(seed, [])
        return SimpleNamespace(ledger=[{'actions': acts}],
                               pool_fingerprint='fp-test')

    return _fake


class _V6State:
    """v6 检查单易失态的清场/复原(测试纪律:改全局态必须复原;
    evidence 落盘文件重定向到临时目录——测试零真实 .debug 写入)。"""

    def __enter__(self):
        import tempfile
        from pathlib import Path

        from sr_od.application.currency_war.sim import ab_core_swap

        self._mod = ab_core_swap
        self._saved = (dict(ab_core_swap._BATCH_EVENTS),
                       dict(ab_core_swap._V6_LANDINGS),
                       dict(ab_core_swap._FORMAL_AB_EXEMPTIONS),
                       dict(ab_core_swap._LIVENESS_EXEMPT_DISCLOSURE),
                       ab_core_swap._V6_LANDING_FILE_OVERRIDE)
        ab_core_swap._BATCH_EVENTS.clear()
        ab_core_swap._V6_LANDINGS.clear()
        ab_core_swap._FORMAL_AB_EXEMPTIONS.clear()
        ab_core_swap._LIVENESS_EXEMPT_DISCLOSURE.clear()
        self._tmp = Path(tempfile.mkdtemp(prefix='v6_landing_test_'))
        ab_core_swap._V6_LANDING_FILE_OVERRIDE = self._tmp / 'v6_landing.jsonl'
        provisional.reset('V_GAP')
        return ab_core_swap

    def __exit__(self, *exc):
        import shutil

        m = self._mod
        (be, vl, fe, ld, fo) = self._saved
        m._BATCH_EVENTS.clear()
        m._BATCH_EVENTS.update(be)
        m._V6_LANDINGS.clear()
        m._V6_LANDINGS.update(vl)
        m._FORMAL_AB_EXEMPTIONS.clear()
        m._FORMAL_AB_EXEMPTIONS.update(fe)
        m._LIVENESS_EXEMPT_DISCLOSURE.clear()
        m._LIVENESS_EXEMPT_DISCLOSURE.update(ld)
        m._V6_LANDING_FILE_OVERRIDE = fo
        shutil.rmtree(self._tmp, ignore_errors=True)
        provisional.reset('V_GAP')
        return False


def _land_all_other_rows(ab_core_swap, monkeypatch):
    """把行 17 之外的行全部置绿(文本锚 monkeypatch + mark 申报 + 事件序),
    使行 17 成为唯一变量——事故复演判据的最小充分条件形态。"""
    monkeypatch.setattr(
        ab_core_swap, '_text_of',
        lambda rel: 'mandate_v1 ev_arm v6 f7_contingency_armed '
                    'depsilon_advisor_violation f7_exempt_emission')
    for row in (2, 4, 5, 6, 10, 14, 15, 16):
        ab_core_swap.record_v6_landing(row, f'测试申报:{row}')
    for ev in ('theta_calib', 'eta_theta_calib', 'chi_calib',
               'bandwidth_calib', 'switchline_anchor_batch'):
        ab_core_swap.record_batch_event(ev)
    ab_core_swap.record_batch_event('p_open')


class TestRow17IncidentGuard:
    """症4:formal A/B ⟹ V_GAP 注入态(或显式豁免批文落档)。"""

    def test_checklist_has_row_17(self):
        """清单行数=17(行 17=V_GAP 事故防护,IMPL_ADV_R200 症4)。"""

        with _V6State() as m:
            rows = m.v6_checklist()
            assert len(rows) == 17
            assert rows[-1]['row'] == 17

    def test_incident_config_must_be_red(self, monkeypatch):
        """事故复演(V_GAP=None 开 formal A/B,其余行全绿)⇒ 行 17 红、
        require raise——2026-09-03 零刷新事故形态的测试锁(必带)。"""
        with _V6State() as m:
            _land_all_other_rows(m, monkeypatch)
            rows = {r['row']: r for r in m.v6_checklist()}
            assert rows[17]['status'] == '未落地'
            with pytest.raises(RuntimeError, match='行17'):
                m.require_v6_green_for_formal_ab()

    def test_injected_vgap_turns_row_17_green(self, monkeypatch):
        """V_GAP 注入态(apply_core_swap_calibration)⇒ 行 17 绿、require
        放行,且 prereg manifest 落档块携带 vgap_state=injected。"""
        with _V6State() as m:
            _land_all_other_rows(m, monkeypatch)
            m.apply_core_swap_calibration()
            report = m.require_v6_green_for_formal_ab()
            assert report['ok']
            assert report['prereg_manifest']['vgap_state'] == 'injected'
            assert report['prereg_manifest']['v6_ok']

    def test_explicit_exemption_filing_turns_row_17_green(self, monkeypatch):
        """显式豁免批文通道:V_GAP 仍 None,但批文在档 ⇒ 行 17 绿;
        批文随 prereg manifest 落档(强制消费的数据源)。"""
        with _V6State() as m:
            _land_all_other_rows(m, monkeypatch)
            m.record_formal_ab_exemption(
                'V_GAP', '编排者裁定:V1 时点豁免,披露义务=CALIB_REPORT_'
                         'V2 §3.2;解除条件=sell 饥饿立案批结清')
            rows = {r['row']: r for r in m.v6_checklist()}
            assert rows[17]['status'] == '已落地'
            report = m.require_v6_green_for_formal_ab()
            man = report['prereg_manifest']
            assert man['vgap_state'] == 'none'
            assert 'V_GAP' in man['formal_ab_exemptions']

    def test_exemption_requires_nonempty_ruling(self):
        """豁免批文硬化:缺/空/纯空白 = 拒绝(防随意豁免;与 v6 mark 行
        evidence 硬化同纪律)。"""
        with _V6State() as m:
            for bad in ('', '   '):
                with pytest.raises(ValueError, match='批文'):
                    m.record_formal_ab_exemption('V_GAP', bad)
            assert not m._FORMAL_AB_EXEMPTIONS

    def test_exemption_must_bind_vgap_slot(self, monkeypatch):
        """F2 槽位绑定(V6_CLEANUP_REVIEW):对无关槽位(如 U_X)登记
        非空批文不得解锁行 17——判前锁防蓄意误用;ab_judge 侧同判
        (manifest 里仅含非 V_GAP 键 ⇒ 拒读)。"""
        with _V6State() as m:
            _land_all_other_rows(m, monkeypatch)
            m.record_formal_ab_exemption(
                'U_X', '无关槽位的批文:不应解锁 V_GAP 行 17')
            rows = {r['row']: r for r in m.v6_checklist()}
            assert rows[17]['status'] != '已落地'
            assert 'V_GAP' not in m._FORMAL_AB_EXEMPTIONS

    def test_deferred_mark_rows_do_not_block_but_stay_visible(self):
        """deferred_mark(6/14/15/16)= R94-6 类条款镜像(2026-09-03
        编排者裁决,A/B preflight 红行暴露的实现-设计不一致修复):
        未申报 ⇒ 「未到期(类条款,不阻塞)」不拦 require;但 checklist
        可见(判读侧按 PREREG 披露义务消费)。判据本体零改动——
        mark 硬前置行为不受影响(行 2 无 evidence 仍拦)。"""
        with _V6State() as m:
            rows = {r['row']: r for r in m.v6_checklist()}
            for n in (6, 14, 15, 16):
                assert rows[n]['status'] == '未到期(类条款,不阻塞)'
            # 行 2(mark 硬前置)无 evidence ⇒ 未落地,require 仍拦
            assert rows[2]['status'] == '未落地'
            with pytest.raises(RuntimeError, match='行2'):
                m.require_v6_green_for_formal_ab()

    def test_liveness_exemptions_filed_and_consumed(self, monkeypatch):
        """症4 强制消费半边:活性守卫的自动豁免清单随守卫产物落档
        (_LIVENESS_EXEMPT_DISCLOSURE)并进 prereg manifest;症7:守卫
        报告携带 sell 证据辖域限定句。"""
        with _V6State() as m:
            acts = [BuyCard(card=ShopCard(x=1, name='x', cost=1),
                            reason='t'),
                    LevelUpShop(cost=4), SellBench(bench_idx=0, income=1,
                                                   expect='x')]
            monkeypatch.setattr(
                m, 'simulate_p1',
                _fake_sim(dict.fromkeys(range(10), acts)))
            report = m.action_family_liveness_gate(n=10, seed_base=0)
            assert report['ok']
            # V_GAP=None ⇒ refresh 族豁免必须被落档(非静默绿)
            assert m._LIVENESS_EXEMPT_DISCLOSURE
            for arm in m._LIVENESS_EXEMPT_DISCLOSURE.values():
                assert 'refresh' in arm
            # 症7:sell 证据辖域限定随守卫产物输出
            assert 'shop 侧发射位' in report['sell_evidence_scope']

    def test_disclosure_counter_filter(self):
        """预注册①数据源:披露键族过滤(shop_ev_u_unavailable/
        m6_overflow_strand/shop_r1_* 保留,无关键剔除)。"""
        from types import SimpleNamespace

        from sr_od.application.currency_war.sim import ab_core_swap
        from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
            state_of,
        )

        # 策略器状态迁 MandateState:cw4_counters 经 state_of 附着(桩同效)
        sess = SimpleNamespace()
        state_of(sess).cw4_counters = {
            'shop_ev_u_unavailable': 3, 'm6_overflow_strand': 1,
            'shop_r1_ev_unavailable': 7, 'shop_r1_account_over_vgap': 2,
            'shop_wave_idle_gold': 99, 'emitter_conditional_truncated': 5}
        out = ab_core_swap.cw4_disclosure_from_session(sess)
        assert out == {'shop_ev_u_unavailable': 3, 'm6_overflow_strand': 1,
                       'shop_r1_ev_unavailable': 7,
                       'shop_r1_account_over_vgap': 2}


class TestActionFamilyLivenessGate:
    """动作族活性下限守卫(原 test_cw_zero_refresh::TestLivenessGate
    迁入,2026-09-09 合并批;断言零改动,_V6State 承担原文件逐测手写的
    注册表清场与 provisional 复位)。豁免正形(V_GAP=None fail-closed
    落档放行)见上方 test_liveness_exemptions_filed_and_consumed。"""

    def test_starved_family_raises(self, monkeypatch):
        """反例:卖族零发射且无 fail-closed 豁免 ⇒ raise 疑似结构性饥饿。"""
        with _V6State() as m:
            monkeypatch.setattr(
                m, 'simulate_p1',
                _fake_sim({0: [RefreshShop(cost=2), BuyCard(
                    card=ShopCard(x=1, name='x', cost=1), reason='t'),
                    LevelUpShop(cost=4)]}))
            with pytest.raises(RuntimeError, match='结构性饥饿'):
                m.action_family_liveness_gate(n=1, seed_base=0)

    def test_escalation_rescues_rare_alive_family(self, monkeypatch):
        """升级扫描(FIX_REVIEW 复审返工批):首段 n 局零发射的族在追加
        seed 段活过 ⇒ 守卫过(区分「低频活」与「真死路」;sell 族
        4/30 局实证形态)+ escalated_runs 披露。"""
        with _V6State() as m:
            acts = [BuyCard(card=ShopCard(x=1, name='x', cost=1),
                            reason='t'),
                    LevelUpShop(cost=4), RefreshShop(cost=2)]
            by_seed = dict.fromkeys(range(10), acts)
            # 升级段第 3 局(seed=12)出现 sell——低频活
            by_seed[12] = acts + [SellBench(bench_idx=0, income=1,
                                            expect='x')]
            monkeypatch.setattr(m, 'simulate_p1', _fake_sim(by_seed))
            report = m.action_family_liveness_gate(n=10, seed_base=0)
            assert report['ok']
            for arm in report['arms'].values():
                assert not arm['starved']
            assert any(arm['escalated_runs'] > 0
                       for arm in report['arms'].values())

    def test_escalation_exhausted_still_raises(self, monkeypatch):
        """升级段耗尽仍零发射 ⇒ 照 raise(升级只救低频活,不掩盖死路)。"""
        with _V6State() as m:
            monkeypatch.setattr(m, 'LIVENESS_ESCALATION_N', 3)
            acts = [BuyCard(card=ShopCard(x=1, name='x', cost=1),
                            reason='t'),
                    LevelUpShop(cost=4), RefreshShop(cost=2)]
            monkeypatch.setattr(
                m, 'simulate_p1',
                _fake_sim(dict.fromkeys(range(13), acts)))
            with pytest.raises(RuntimeError, match='结构性饥饿'):
                m.action_family_liveness_gate(n=10, seed_base=0)

    def test_opened_slot_removes_exemption(self, monkeypatch):
        """V_GAP 注入后豁免失效:刷新族零发射 ⇒ raise(开闸路径存在
        却零发射=饥饿,豁免只覆盖 fail-closed 降级态)。"""
        with _V6State() as m:
            provisional.inject('V_GAP', provisional.CalibValue(
                value=10.0, injected_form=True))
            acts = [BuyCard(card=ShopCard(x=1, name='x', cost=1),
                            reason='t'),
                    LevelUpShop(cost=4), SellBench(bench_idx=0, income=1,
                                                   expect='x')]
            monkeypatch.setattr(
                m, 'simulate_p1',
                _fake_sim(dict.fromkeys(range(10), acts)))
            with pytest.raises(RuntimeError, match='结构性饥饿'):
                m.action_family_liveness_gate(n=10, seed_base=0)


class TestV6ChecklistRows:
    """v6 检查单行锁(原 test_cw_zero_refresh::TestV6Checklist 迁入,
    2026-09-09 合并批;清场改走 _V6State,断言零改动)。"""

    def test_class_clause_rows_do_not_block(self):
        """类条款行(R94-6:行 3/8/9/12 等):批事件未到期 ⇒ 「未到期」
        不阻塞;到期且序合 ⇒ 已落地。"""
        with _V6State() as m:
            rows = {r['row']: r for r in m.v6_checklist()}
            assert rows[3]['status'].startswith('未到期')
            m.record_batch_event('theta_calib')
            m.record_batch_event('p_open')
            rows = {r['row']: r for r in m.v6_checklist()}
            assert rows[3]['status'] == '已落地'

    def test_mark_row_requires_nonempty_evidence(self):
        """v6 mark 行硬化(FIX_REVIEW_20260903 场景 B 复验):evidence
        缺/空/纯空白 ⇒ record_v6_landing raise;绕过入口直写空证据 ⇒
        checklist 行红(不因「申报过」即绿)。"""
        with _V6State() as m:
            for bad in ('', '   '):
                with pytest.raises(ValueError, match='evidence'):
                    m.record_v6_landing(4, bad)
            # 入口拒绝后未登记
            rows = {r['row']: r for r in m.v6_checklist()}
            assert rows[4]['status'] == '未落地'
            # 绕过入口直写空证据(对抗形态):checklist 独立复验=行红
            m._V6_LANDINGS[4] = '   '
            rows = {r['row']: r for r in m.v6_checklist()}
            assert rows[4]['status'] == '未落地'
            del m._V6_LANDINGS[4]   # 清对抗直写,走正规入口
            # 非空证据:绿 + 证据文本随行输出(可审计)
            m.record_v6_landing(4, '锚批/判读批拆半预注册,档=X')
            rows = {r['row']: r for r in m.v6_checklist()}
            assert rows[4]['status'] == '已落地'
            assert rows[4]['evidence'].startswith('锚批/判读批')


class TestRealEngineLivenessSmoke:
    """真引擎 sim 验收(原 test_cw_zero_refresh::
    TestZeroRefreshFixSimAcceptance 迁入,2026-09-09 合并批;断言零改动)。

    levelup 族活性端到端烟测(2026-09-08 实测 call≈0.35s,远低于 2s
    桶线,快速层回收;引擎后续演进若实测超 2s 再按纪律复测入桶)。"""

    SIM_KW = {'pool': 'snapshot', 'planes': 1, 'use_refresh': True,
              'invest': False, 'p2_combat': None, 'synthesis_chain': False,
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
                **TestRealEngineLivenessSmoke.SIM_KW)
        finally:
            logging.disable(logging.NOTSET)

    @staticmethod
    def _counts(res):
        # ledger 行的 actions 可能是动作对象或已序列化 dict(键 __type__)
        c: dict[str, int] = {}
        for row in (res.ledger or []):
            for a in (row.get('actions') or []):
                t = (a.get('__type__') if isinstance(a, dict)
                     else type(a).__name__)
                c[t] = c.get(t, 0) + 1
        return c

    def test_none_period_levelups_alive(self):
        """真引擎端到端烟测(全仓唯一真跑 mandate_v1 的动作族活性
        断言):V_GAP=None 缺省态真跑 5 seed,levelup 族合计发射
        >0(病灶2 arm1 修复的整合面回归锁;frame 级发射锁归
        test_cw_shop_line)。刷新面按 20 号稿/ADR-0516 已合法化
        (必花域内 r2 硬闸承载),原「验收①零漂移」断言随设计退役,
        不再断言零刷新。"""
        provisional.reset('V_GAP')
        lv_total = 0
        for seed in range(5):
            res = self._run(seed)
            lv_total += sum(v for k, v in self._counts(res).items()
                            if k in ('LevelUp', 'LevelUpShop'))
        assert lv_total > 0


class TestV6LandingPersistence:
    """mark 行 evidence 持久化落盘(外部交叉评审 2026-09-03 首轮建议级
    落地,v6 判前锁清理批增补):落盘/回读复验/缺字段红/首行为准。"""

    def test_evidence_persisted_and_reread_after_memory_clear(self):
        """落盘+回读:申报后清进程内缓存,checklist 仍从落盘文件读到
        evidence(行绿)——持久权威,跨进程可审计。"""
        import json

        with _V6State() as m:
            m.record_v6_landing(4, '锚批/判读批拆半预注册,档=X',
                                context='v6 清理批测试')
            m._V6_LANDINGS.clear()   # 模拟跨进程:进程内缓存归零
            rows = {r['row']: r for r in m.v6_checklist()}
            assert rows[4]['status'] == '已落地'
            assert rows[4]['evidence'].startswith('锚批/判读批拆半')
            lines = [json.loads(x) for x in
                     m._v6_landings_path().read_text(encoding='utf-8')
                     .splitlines() if x.strip()]
            assert len(lines) == 1
            assert lines[0]['row'] == 4
            assert lines[0]['evidence'].startswith('锚批/判读批拆半')
            assert lines[0]['recorded_at']   # 时间戳在档
            assert lines[0]['context'] == 'v6 清理批测试'

    def test_landing_file_missing_evidence_field_is_red(self):
        """测试锁(必带):落盘行缺 evidence 字段 / 纯空白 ⇒ 该 mark 行红
        (回读复验不因「文件里有行」即绿)。"""
        with _V6State() as m:
            p = m._v6_landings_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                '{"row": 4, "recorded_at": "2026-09-11T00:00:00"}\n'
                '{"row": 5, "evidence": "   "}\n', encoding='utf-8')
            rows = {r['row']: r for r in m.v6_checklist()}
            assert rows[4]['status'] == '未落地'
            assert rows[5]['status'] == '未落地'

    def test_duplicate_landing_first_wins(self):
        """重复登记以落盘首行为准:二次申报不同 evidence 不追加、不改写
        (证据不可事后篡改)。"""
        import json

        with _V6State() as m:
            m.record_v6_landing(4, '首份证据')
            m.record_v6_landing(4, '二次不同证据')
            rows = {r['row']: r for r in m.v6_checklist()}
            assert rows[4]['evidence'] == '首份证据'
            lines = [x for x in m._v6_landings_path()
                     .read_text(encoding='utf-8').splitlines() if x.strip()]
            assert len(lines) == 1
            assert json.loads(lines[0])['evidence'] == '首份证据'


class TestJudgeMigration:

    def test_ab_judge_selftest_v6_green(self):
        """判读器迁移自测复跑:W-A 缺 prereg 拒读 / W-B V_GAP=none 无
        豁免拒读(症4 事故形态判读侧复演红)/ W-C 全件判读。"""
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location(
            'ab_judge_under_test',
            Path(__file__).resolve().parents[5] / 'tools/cw/ab_judge.py')
        mod = importlib.util.module_from_spec(spec)
        sys.modules['ab_judge_under_test'] = mod
        spec.loader.exec_module(mod)
        failures = mod.self_test_v6()
        assert failures == [], failures
