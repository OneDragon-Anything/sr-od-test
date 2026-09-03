"""v6 判前锁清理批测试(2026-09-11;IMPL_ADV_R200 症4/症7 + 预注册件)。

覆盖:
- 症4:v6 清单行 17(V_GAP 注入态或显式豁免批文)——零刷新事故配置
  复演必红 + 注入/豁免两通道放行 + 豁免批文非空纪律;
- 症4 强制消费:活性守卫豁免快照落档 + prereg manifest 形态;
- 症7:归因域/活性证据辖域限定随守卫产物输出;
- 预注册件:PREREG v6 节文本锚 + ab_judge v6 自测复跑(判读器迁移)。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sr_od.application.currency_war.decision.cw4.audit import provisional
from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    LevelUpShop,
    SellBench,
    ShopCard,
)

_REPO_ROOT = Path(__file__).resolve().parents[5]
_PREREG = (_REPO_ROOT / '.debug/temp/currency_war/redesign/'
           'PREREG_cw3_vs_legacy_AB.md')


def _fake_sim(actions_by_seed):
    """造假 simulate_p1(与 test_cw_zero_refresh_fix 同款桩)。"""

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

        sess = SimpleNamespace(cw4_counters={
            'shop_ev_u_unavailable': 3, 'm6_overflow_strand': 1,
            'shop_r1_ev_unavailable': 7, 'shop_r1_account_over_vgap': 2,
            'shop_wave_idle_gold': 99, 'emitter_conditional_truncated': 5})
        out = ab_core_swap.cw4_disclosure_from_session(sess)
        assert out == {'shop_ev_u_unavailable': 3, 'm6_overflow_strand': 1,
                       'shop_r1_ev_unavailable': 7,
                       'shop_r1_account_over_vgap': 2}


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


class TestPreregAndJudgeMigration:

    def test_prereg_doc_v6_section_anchor(self):
        """行 2 hint 锚:PREREG 含 v6 变更记录(三臂叙述/预指定主对照/
        强制披露/措辞限定/激活率门预注册)。"""
        text = _PREREG.read_text(encoding='utf-8')
        assert '| v6 |' in text
        for token in ('单被测体两因子', '预指定主对照 ②−①',
                      'shop_ev_u_unavailable', '不得读作全量处理效应',
                      '骨架+EV 臂 sim 首批实测'):
            assert token in text, token

    def test_ab_judge_v6_vocabulary_anchor(self):
        """行 1 落地判据:ab_judge 词表含 mandate_v1/ev_arm(三臂因子词表)。"""
        text = (Path(__file__).resolve().parents[5]
                / 'tools/cw/ab_judge.py').read_text(encoding='utf-8')
        assert 'mandate_v1' in text and 'ev_arm' in text
        assert 'skeleton_only' in text and 'decision_v2' in text

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

    def test_measurement_domain_narrowed_in_ab_core_swap(self):
        """症7 文本锚:预注册声明与门组 docstring 的归因域已收窄到
        shop 决策面(prep 面 sim 不可达)。"""
        text = (Path(__file__).resolve().parents[5] / 'src/sr_od/application/'
                'currency_war/sim/ab_core_swap.py').read_text(
                    encoding='utf-8')
        assert '实际=shop 决策面' in text
        assert 'prep 面 sim' in text
