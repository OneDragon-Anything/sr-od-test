"""L3 备战消费链修批测试锁(必花域备战期闩 + L3 资格拒分键 + xp 现读
透传 + b_t 实机回退源[form_score 口径替换后延续] + 实机遥测两件接线)。

病灶源 = g_20260906_021859 / g_20260906_034515 两局濒死段门链回放定谳:
「花光」义务在必花域边界上蒸发(商店域首笔消费把金拉回域内后,同备战
期 prep 帧域外被 P2 危机带常态挂起,残金闲置入死战)+ L3 资格拒零分键
不可辨 + prep 侧 xp 现读被丢弃构成 spend_unified 假拒第二静默面。

锁契约 = 结构/回显,不锁分布数值(sr-od-test README 第 8 条)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_prep_actions import LevelUp
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    RefreshShop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


_DEP7 = ['藿藿', '艾丝妲', '丹恒·饮月', '风堇', '爻光', '彦卿', '椒丘']
_BENCH5 = ['千冶·刃', '银狼LV.999', '卡芙卡', '姬子·启行', '三月七']
_KM = ('卡芙卡', '千冶·刃', '银狼LV.999')


def _mk(gold: int, *, hp: int = 1, level: int = 7,
        round_num: int = 5, xp: tuple[int, int] | None = (22, 52),
        click_cost: int = 4):
    """二十二局濒死帧态(复盘 g_20260906_034515 专节1):P2r5 hp1、
    lv7(cap=7 板满七件过渡板)、xp 22/52、单击 4 金、bench 有线成员
    (arm1 命中=进块前提;门链回放脚本 cw_l3_gate_replay.py 同源形态)。"""
    deployed = [_bc(n, star=2 if n == '椒丘' else 1, slot=i + 1)
                for i, n in enumerate(_DEP7)]
    bench = [_bc(n, star=1, slot=i + 1)
             for i, n in enumerate(_BENCH5)]
    frame = mandate.MandateFrame(
        gold=gold, level=level, bench=bench, deployed=deployed,
        deploy_cap=7, node_type='encounter', stop_flag=False,
        k_members=_KM, round_num=round_num)
    st = GameState(gold=gold, level=level, hp=hp, plane=2,
                   round_num=round_num)
    st.level_readable = True
    st.node_type = 'encounter'
    st.xp_progress = xp
    st.level_up_cost = click_cost
    sess = SimpleNamespace(cw4_counters={}, target_comp=None,
                           v3_intention=IntentionState(),
                           cw4_cap_override=None)
    return frame, sess, st


def _lvls(out):
    return [e for e in out if isinstance(e.action, LevelUp)]


class TestPrepMustSpendLatch:
    """必花域备战期闩(g_20260906_034515 濒死段形态逐帧回放锁)。"""

    def test_latch_extends_zone_after_shop_consume(self):
        """帧A(g56 域内)发射后,同备战期帧B(g43 域外残金)经闩延命
        仍发射 LevelUp + must_spend_zone_latch_extend 分键在案——
        「花光」义务不再在域边界上蒸发。"""
        fa, sess, sta = _mk(56)
        out_a = mandate.run_mandate(fa, sess, state=sta)
        assert _lvls(out_a), '帧A 域内应发射'
        assert sess.cw4_counters.get(
            'must_spend_zone_defer_overridden') == 1
        fb, _, stb = _mk(43)   # 商店域消费 13 金后的残金帧
        out_b = mandate.run_mandate(fb, sess, state=stb)
        assert _lvls(out_b), '闩延命帧应保持域豁免并发射'
        assert sess.cw4_counters.get('must_spend_zone_latch_extend') == 1

    def test_fresh_session_still_defers(self):
        """负向:无闩的新备战期帧(g43 域外)⇒ 危机带常态挂起照旧
        (crisis_level_spend_defer),域外语义零变化。"""
        fb, sess, stb = _mk(43)
        out = mandate.run_mandate(fb, sess, state=stb)
        assert not _lvls(out)
        assert sess.cw4_counters.get('crisis_level_spend_defer') == 1
        assert 'must_spend_zone_latch_extend' not in sess.cw4_counters

    def test_latch_expires_next_round(self):
        """闩相位键式 = (plane, round):下一备战期(新键)不继承,
        域外帧回归危机带常态挂起。"""
        fa, sess, sta = _mk(56)
        mandate.run_mandate(fa, sess, state=sta)
        fn, _, stn = _mk(43, round_num=6)
        out = mandate.run_mandate(fn, sess, state=stn)
        assert not _lvls(out)
        assert sess.cw4_counters.get('crisis_level_spend_defer') == 1
        assert 'must_spend_zone_latch_extend' not in sess.cw4_counters


class TestL3RejectKeys:
    """L3 资格拒分键(拒因落盘缺口治疗:「拒因不可辨」复盘主项)。"""

    def test_level_cap_keyed(self):
        """域内满级帧 ⇒ 零发射 + l3_reject_level_cap 分键在案。"""
        f, sess, st = _mk(56, level=9)
        out = mandate.run_mandate(f, sess, state=st)
        assert not _lvls(out)
        assert sess.cw4_counters.get('l3_reject_level_cap') == 1

    def test_batch_unaffordable_keyed(self):
        """域内整批买不齐(单击价 13 金 ×13 击 > 51)⇒ 零发射 +
        l3_reject_batch_unaffordable 分键在案(P48 整买纪律拦截显影)。"""
        f, sess, st = _mk(51, hp=80, xp=(0, 52), click_cost=13)
        out = mandate.run_mandate(f, sess, state=st)
        assert not _lvls(out)
        assert sess.cw4_counters.get('l3_reject_batch_unaffordable') == 1

    def test_xp_readthrough_rescues_residual_band(self):
        """xp 现读透传(第二静默拒因面修复):闩延命残金帧 43 金,
        xp 22/52 现读(真 8击×4=32≤43)⇒ 发射;xp 缺读(旧 0 进度
        兜底,虚 13击×4=52>43)⇒ 整批拒分键可辨——两形态判决相反
        且拒因侧均可归因。"""
        fa, sess2, sta = _mk(56)       # 先以域内帧置闩(同备战期)
        mandate.run_mandate(fa, sess2, state=sta)
        fb, _, stb = _mk(43)
        assert _lvls(mandate.run_mandate(fb, sess2, state=stb))
        fc, _, stc = _mk(43, xp=None)
        out2 = mandate.run_mandate(fc, sess2, state=stc)
        assert not _lvls(out2)
        assert sess2.cw4_counters.get('l3_reject_batch_unaffordable') == 1


class TestBoardTargetLineTrackedFallback:
    """b_t 实机回退源(两局全帧 0.0 实证:商店观察帧 deployed
    恒空 → 写者输入缺;回退 = session.tracked_deployed)。"""

    def _strat(self):
        from sr_od.application.currency_war.sim.engine_p1 import (
            sim_decision_registry,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        return MandateV1Strategy(registry=sim_decision_registry())

    def test_empty_state_deployed_falls_back_to_tracked(self):
        """state.deployed 空 ∧ tracked_deployed 有件 ⇒ b_t > 0
        (实机商店帧形态;青雀=仙舟∈线内集,3 件 = 3)。"""
        from sr_od.application.currency_war.kernel.cw_strategy_session import (
            StrategySession,
        )
        sess = StrategySession()
        st = GameState()
        sess.tracked_deployed = [
            BenchChar(slot=i + 1, char_id='青雀', star=1, faction='仙舟',
                      position_pref='back') for i in range(3)]
        self._strat().write_shop_mirrors(st, sess)
        assert sess.v3_b_t == 3

    def test_truly_empty_board_stays_zero(self):
        """tracked 同空(板面真空事实态)⇒ 恒 0 不虚构。"""
        from sr_od.application.currency_war.kernel.cw_strategy_session import (
            StrategySession,
        )
        sess = StrategySession()
        st = GameState()
        self._strat().write_shop_mirrors(st, sess)
        assert sess.v3_b_t == 0


class TestRecorderObservationWiring:
    """实机遥测两件接线(refresh_trigger 分键 / sess_terminal_release
    透传;g_20260906_021859 起连续零产出的接线缺治疗)。"""

    def _record(self, tmp_path, actions, ctx=None, monkeypatch=None):
        from sr_od.application.currency_war.telemetry import state as _tel
        from sr_od.application.currency_war.telemetry.recorder import (
            TelemetryRecorder,
        )
        if ctx is not None and monkeypatch is not None:
            monkeypatch.setattr(_tel, '_CTX_MATCH_REF', [ctx])
        rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
        rec.record_decision('run_x', 'A8', GameState(), '', {}, {}, actions)
        lines = (tmp_path / 'decisions.jsonl').read_text(
            encoding='utf-8').strip().splitlines()
        import json
        return json.loads(lines[-1])

    def test_refresh_trigger_counted_from_actions(self, tmp_path):
        """决策行 refresh_trigger = 本行 RefreshShop 按 reason 计数
        ('' 归 other 桶);无刷新行为空 dict(非缺写)。"""
        row = self._record(tmp_path, [
            RefreshShop(reason='must_spend_r1_yielded'),
            RefreshShop(reason=''),
        ])
        assert row.get('refresh_trigger') == {
            'must_spend_r1_yielded': 1, 'other': 1}

    def test_no_refresh_rows_empty_dict(self, tmp_path):
        row = self._record(tmp_path, [])
        assert row.get('refresh_trigger') == {}

    def test_terminal_release_passthrough_equals_source(self, tmp_path,
                                                        monkeypatch):
        """sess_terminal_release = terminal_release_bit(sess, last_state)
        原值透传(单一源等值锁,不锁定值——带域口径归该谓词)。"""
        from sr_od.application.currency_war.sim.checks.segments import (
            terminal_release_bit,
        )
        st = GameState(gold=10, level=5, hp=30, plane=1, round_num=7)
        sess_stub = SimpleNamespace(last_state=st, v3_blood_budget_rejects=0,
                                    v3_blood_budget_refresh_rejects=0,
                                    cw4_shop_rejects={})
        row = self._record(tmp_path, [], ctx=SimpleNamespace(session=sess_stub),
                           monkeypatch=monkeypatch)
        assert row.get('sess_terminal_release') == bool(
            terminal_release_bit(sess_stub, st))

    def test_terminal_release_none_without_match(self, tmp_path):
        """无 match 注册(离线/测试)→ 字段缺省 None(旧 schema 不破坏)。"""
        row = self._record(tmp_path, [])
        assert row.get('sess_terminal_release') is None
