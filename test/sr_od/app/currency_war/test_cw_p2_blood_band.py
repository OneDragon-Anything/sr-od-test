"""P2 低血带授权域统一件落码锁组(fail-closed 落码;T-35)。

设计出处 = p2_blood_band_unified_design/DESIGN.md v2
(.debug/temp/currency_war/_archive_20260908/p2_blood_band_unified_design/)
§1.2(统一授权域单点 + 判定面/消费面分层正交合成)/§2.1(面①消费让位 +
解锁包三件同构移植 + fail-closed 只落观测分键)/§2.3-5(a)(面③出辖观察件
lock_gen_feasibility_obs_* 族)/§4-8(分键族零交集对账);裁定条目定稿 =
supply_arbitration_design/DESIGN.md §15.2「P2 低血带授权域统一裁定」
(覆①消费让位 + 覆②濒死定向豁免 + 覆③出辖注记位,唯一权威);
l3_pregate 分键四元合取与位面维分列 = 同稿 §15.1 R3-低3 兑付。

锁三类事:
1. 判据结构——p2_blood_floor 域谓词真值表(plane≥2 域/信任门/阈值单一源)
   + p2_blood_floor_unlock 授权闩合成(闩 False 恒 False = fail-closed 单点);
2. fail-closed 零行为——授权闩缺省 False 时 P2 濒死帧行为与落码前逐位一致
   (M3 停付照常/保底金门照常/凑息照常);闩 True(授权事件模拟,monkeypatch)
   时解锁包三件让位按设计激活(结构锁,不锁分布数值);
3. 观测分键——形态⑥两键(terminal_targetless_idle / l3_pregate_targetless_
   neardeath_p1|p2 分域)+ 面③ lock_gen_feasibility_obs_*(锁开率分子/分母
   + boss 濒死死区)只计数零行为。

纪律:锁结构/回显不锁分布数值;授权闩翻转测试用 monkeypatch,生产翻转
只能经授权批落码(设计稿 §1.2 闩语义)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_intention as ci
from sr_od.application.currency_war.kernel.cw_comps import (
    SEELE_CARRY_CHAR as _COMPS_SEELE_CARRY_CHAR,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    SEELE_OR_LEGS as _COMPS_SEELE_OR_LEGS,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwWorkFrame,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates as preds,
)


def _st2(hp: int = 10, plane: int = 2, gold: int = 30,
         round_num: int = 2, level: int = 7) -> CwWorkFrame:
    """P2 濒死带构造帧(信任门真值位显式置位;hp 缺省 10 ⊂ ≤15 带)。"""
    st = CwWorkFrame(gold=gold, level=level, round_num=round_num, hp=hp)
    st.plane = plane
    st.hp_readable = True
    st.hp_trusted = False
    st.level_readable = True
    return st


# ===== 1. 判据结构:域谓词 + 授权闩合成 =====


class TestP2BloodFloorPredicate:

    def test_domain_truth_table(self):
        """p2_blood_floor 真值表:plane≥2 ∧ hp≤15 ∧ 可信 ⇒ True;
        hp>15 / hp None / 不可信帧 fail 向 ⇒ False(与 p1_blood_floor
        逐行同构,设计稿 §2.1;阈值单一源 = HP_BAND_NEAR_DEATH)。"""
        st = _st2(hp=10)
        assert preds.p2_blood_floor(st) is True
        st.hp = 16
        assert preds.p2_blood_floor(st) is False
        st.hp = 15   # ≤15 族含边界(p1_blood_floor 同款)
        assert preds.p2_blood_floor(st) is True
        st.hp = None
        assert preds.p2_blood_floor(st) is False
        st.hp = 10
        st.hp_readable = False   # P1 hp 读链毒化史口径:不可信帧 fail 向
        assert preds.p2_blood_floor(st) is False

    def test_plane_domain_complementary_with_p1(self):
        """位面域互补且不交(设计稿 §2.1「同构不同域,禁搭车」):P1 帧
        不得开 P2 域谓词(P1 半边 = p1_blood_floor 在册授权,零改);
        P3 帧属 P2+ 域(谓词 plane≥2 口径)。"""
        st = _st2(hp=10, plane=1)
        assert preds.p1_blood_floor(st) is True
        assert preds.p2_blood_floor(st) is False, 'P1 帧禁开 P2 域谓词'
        st3 = _st2(hp=10, plane=3)
        assert preds.p2_blood_floor(st3) is True

    def test_threshold_single_source(self):
        """阈值常量单一源锁(设计稿 §1.1「禁任何第二份字面量 15」):
        谓词边界 = HP_BAND_NEAR_DEATH 读数(≤15 族含边界),非本地第二份
        ——常量与谓词边界同源即结构锁(改常量即改边界,无第二值可漂)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.lambda_death import (
            HP_BAND_NEAR_DEATH,
        )
        st = _st2(hp=HP_BAND_NEAR_DEATH)
        assert preds.p2_blood_floor(st) is True, '边界=常量(≤15 族)'
        assert preds.p2_blood_floor(_st2(hp=HP_BAND_NEAR_DEATH + 1)) is False


class TestP2AuthorityLatchComposite:

    def test_latch_default_false_fails_closed(self):
        """fail-closed 单点:闩缺省 False ⇒ p2_blood_floor_unlock 恒 False,
        即使帧在域内(设计稿 §1.2「收口前恒 False ⇒ 两面全部 P2 行为支
        fail-closed」;§3.2-3 未裁未证前全局 fail-closed)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            BS_SCHEMA_VERSION,
            GameState,
            ChannelSig,
            NodeKey,
        )
        from sr_od.application.currency_war.kernel.cw_discipline_rules import (
            hp_decision_trusted,
        )
        # 可信位前提锚(波 2 起容器形态:真读帧 = observation 源 → 可信)
        bs = GameState(schema_version=BS_SCHEMA_VERSION)
        sig = ChannelSig(family='obs', actor='cw_observation', mode='read')
        bs.observe(bs.hp, 10, sig=sig)
        bs.observe(bs.node, NodeKey(plane=2, round_num=2, kind='battle'),
                   sig=sig)
        assert hp_decision_trusted(bs) is True   # 前提锚:帧在域内且可信
        st = _st2(hp=10)
        assert preds.p2_blood_floor(st) is True
        assert preds.P2_BLOOD_BAND_AUTHORITY_OPEN is False
        assert preds.p2_blood_floor_unlock(st) is False

    def test_latch_flip_activates_composite(self, monkeypatch):
        """授权事件模拟(仅测试面;生产翻转 = 授权批落码):闩 True ∧
        帧在域内 ⇒ 合成 True;闩 True ∧ 帧域外(P1 帧/hp>15)⇒ 仍 False
        ——合成 = 闩 ∧ 谓词,任一门单独不构成判据(设计稿 §1.2)。"""
        monkeypatch.setattr(preds, 'P2_BLOOD_BAND_AUTHORITY_OPEN', True)
        assert preds.p2_blood_floor_unlock(_st2(hp=10)) is True
        assert preds.p2_blood_floor_unlock(_st2(hp=10, plane=1)) is False
        assert preds.p2_blood_floor_unlock(_st2(hp=40)) is False
        assert preds.p2_blood_floor_unlock(None) is False


# ===== 2. fail-closed 零行为 + 解锁包三件结构 =====


class TestUnlockPackageFailClosed:

    def test_m3_spend_still_blocked_while_latch_off(self):
        """解锁包件① fail-closed 面:闩缺省 False 时 P2 濒死帧(hp≤15 ⊂
        危机带 41)M3 停付照常(p2_crisis_band 未收口前全额管辖,设计稿
        §1.3-4)——与落码前行为逐位一致。"""
        from sr_od.application.currency_war.kernel.cw_registry import (
            DEFAULT_REGISTRY,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.levelup import (
            level_spend_blocked,
        )
        sess = SimpleNamespace(node_type_current='normal')
        assert level_spend_blocked(_st2(hp=10), sess,
                                   DEFAULT_REGISTRY) is True, (
            '闩关:P2 濒死帧停付照常(零行为)')

    def test_m3_spend_yields_when_authorized(self, monkeypatch):
        """解锁包件①结构(P2 半边):闩开 ⇒ M3 停付让位(转化优先,
        与 P1 死亡线支同构;设计稿 §2.1 解锁包三件同构移植)。"""
        from sr_od.application.currency_war.kernel.cw_registry import (
            DEFAULT_REGISTRY,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.levelup import (
            level_spend_blocked,
        )
        monkeypatch.setattr(preds, 'P2_BLOOD_BAND_AUTHORITY_OPEN', True)
        assert level_spend_blocked(
            _st2(hp=10), SimpleNamespace(node_type_current='normal'),
            DEFAULT_REGISTRY) is False, '闩开:停付族让位(件①激活)'

    def test_guarantee_floor_survival_domain(self, monkeypatch):
        """保底金门生存域(P1 半边同款让位面):闩关 ⇒ P2 濒死帧不保底
        (花后下界照查);闩开 ⇒ 本门让位(True)。出辖次序 = 终局域之后
        (非末位面末战帧构造,终局域不触)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.levelup import (
            _guarantee_floor_holds,
        )
        sess = SimpleNamespace(node_type_current='normal')
        st = _st2(hp=10)
        assert _guarantee_floor_holds(st, sess, 5, 1, 4, 5) is False, (
            '闩关:保底金门照常(零行为)')
        monkeypatch.setattr(preds, 'P2_BLOOD_BAND_AUTHORITY_OPEN', True)
        assert _guarantee_floor_holds(st, sess, 5, 1, 4, 5) is True, (
            '闩开:生存域让位(真花光合法通道 P2 半边)')

    def test_interest_ban_yields_when_authorized(self, monkeypatch):
        """解锁包件②凑息禁令(P2 半边直移植):闩关 ⇒ P2 濒死帧凑息照常
        (不进禁令支,拒因键非 p2_blood_floor);闩开 ⇒ ([], 'p2_blood_floor')
        分键与 P1 域 'blood_floor' 分键禁并(设计稿 §4-8 键族零交集)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.sell import (
            sell_for_interest,
        )
        slots, key = sell_for_interest(30, [], 4, (), state=_st2(hp=10))
        assert slots == [] and key != 'p2_blood_floor', (
            '闩关:P2 帧凑息行为零变更')
        monkeypatch.setattr(preds, 'P2_BLOOD_BAND_AUTHORITY_OPEN', True)
        slots2, key2 = sell_for_interest(30, [], 4, (), state=_st2(hp=10))
        assert slots2 == [] and key2 == 'p2_blood_floor', (
            '闩开:凑息禁令 P2 半边激活,分键独立')
        # P1 域对照:禁令在册语义零改('blood_floor' 原键)
        _slots_p1, key_p1 = sell_for_interest(30, [], 4, (),
                                              state=_st2(hp=10, plane=1))
        assert key_p1 == 'blood_floor'


# ===== 3. 观测分键(纯观测零行为)=====


class TestNearDeathObservationKeys:

    def _run_mandate(self, state: CwWorkFrame) -> StrategySession:
        frame = mandate.MandateFrame(
            gold=state.gold, level=state.level, bench=[], deployed=[],
            deploy_cap=6, node_type=None, stop_flag=False,
            k_members=(), round_num=state.round_num)
        sess = StrategySession()
        state_of(sess).cw4_counters = {}
        out = mandate.run_mandate(frame, sess, state=state)
        assert not any(e.reason.startswith('m3_levelup_batch') for e in out)
        return sess

    def test_l3_pregate_shortcircuit_keyed_p2(self):
        """l3_pregate_targetless_neardeath_p2:四元合取 = 濒死带(P2 域
        谓词)∧ 轴 B 空(target_comp None)∧ 域外(g≤g*)∧ ¬(arms∨zone)
        ——M3 前置短路帧显影(241 §15.1 R3-低3 兑付形态;域后缀 _p2)。"""
        sess = self._run_mandate(_st2(hp=10, gold=30))
        ct = state_of(sess).cw4_counters
        assert ct.get('l3_pregate_targetless_neardeath_p2') == 1
        assert 'l3_pregate_targetless_neardeath_p1' not in ct

    def test_l3_pregate_shortcircuit_keyed_p1(self):
        """P1 域对照帧:同形态落 _p1 分键(位面维分列,防 P1/P2 授权域
        不同混键重演 fenced/precheck 教训;241 §15.1 R3-低3)。"""
        sess = self._run_mandate(_st2(hp=10, plane=1, gold=30))
        ct = state_of(sess).cw4_counters
        assert ct.get('l3_pregate_targetless_neardeath_p1') == 1
        assert 'l3_pregate_targetless_neardeath_p2' not in ct

    def test_l3_pregate_not_keyed_out_of_zone(self):
        """负对照:必花域内帧(g>g* = 50)不合取「域外」项,分键零计数
        (R3-低3「防宽化为一切前置短路帧」——域内帧不入键)。"""
        sess = self._run_mandate(_st2(hp=10, gold=80))
        ct = state_of(sess).cw4_counters
        assert 'l3_pregate_targetless_neardeath_p2' not in ct
        assert 'l3_pregate_targetless_neardeath_p1' not in ct

    def test_terminal_targetless_idle_keyed(self, monkeypatch):
        """形态⑥帧显影:target 空窗 ∧ 濒死带 ∧ 域外 ∧ 持金 ∧ 本帧零金
        消费 ⇒ terminal_targetless_idle 计 1(241 §5.1 键名,不分位面);
        有金消费发射(LevelUp)帧不计。纯观测:计数不改发射序列。"""
        monkeypatch.setattr(mandate, 'run_mandate',
                            lambda frame, session, **kw: [])

        def _obs(st: SimpleNamespace) -> SimpleNamespace:
            return SimpleNamespace(
                box_overlay_open=False, boxes=(), tomes=(), spheres=(),
                event_overlay='', bench_chars=(), deployed_chars=(),
                deploy_vacancy=0, state=st)

        st = SimpleNamespace(
            gold=40, level=6, round_num=2, hp=10, plane=2,
            node_type='战斗', shop=[], bench=[], deployed=[],
            max_units=lambda: 6, level_readable=True,
            hp_readable=True, hp_trusted=False,
            enemy_difficulty=None, refresh_probs=None, shop_refresh_cost=2)
        sess = SimpleNamespace(cw4_counters={}, v3_intention=IntentionState())
        out = entry.emit(_obs(st), SimpleNamespace(), sess, None)
        assert state_of(sess).cw4_counters.get('terminal_targetless_idle') == 1
        assert not any(isinstance(e.action, mandate.LevelUp) for e in out), (
            '观测零行为:形态⑥帧发射序列不变(无动作 ⇒ 出战路径)')
        # 对照:同帧域外不成立(g>g* 且必花域判定真)⇒ 不计
        st_z = SimpleNamespace(
            gold=80, level=6, round_num=2, hp=10, plane=2,
            node_type='战斗', shop=[], bench=[], deployed=[],
            max_units=lambda: 6, level_readable=True,
            hp_readable=True, hp_trusted=False,
            enemy_difficulty=None, refresh_probs=None, shop_refresh_cost=2)
        sess_z = SimpleNamespace(cw4_counters={}, v3_intention=IntentionState())
        entry.emit(_obs(st_z), SimpleNamespace(), sess_z, None)
        assert 'terminal_targetless_idle' not in state_of(sess_z).cw4_counters

    def test_terminal_idle_not_keyed_healthy_hp(self, monkeypatch):
        """负对照:非濒死帧(hp=60)不计(键只辖濒死带形态,与既有
        advisor 计数面零交集)。"""
        monkeypatch.setattr(mandate, 'run_mandate',
                            lambda frame, session, **kw: [])
        st = SimpleNamespace(
            gold=40, level=6, round_num=2, hp=60, plane=2,
            node_type='战斗', shop=[], bench=[], deployed=[],
            max_units=lambda: 6, level_readable=True,
            hp_readable=True, hp_trusted=False,
            enemy_difficulty=None, refresh_probs=None, shop_refresh_cost=2)
        sess = SimpleNamespace(cw4_counters={}, v3_intention=IntentionState())
        entry.emit(SimpleNamespace(
            box_overlay_open=False, boxes=(), tomes=(), spheres=(),
            event_overlay='', bench_chars=(), deployed_chars=(),
            deploy_vacancy=0, state=st), SimpleNamespace(), sess, None)
        assert 'terminal_targetless_idle' not in state_of(sess).cw4_counters


class TestLockGenFeasibilityObsKeys:
    """面③出辖观察件(载体 = flow.bump_lock_gen_feasibility_obs,strategies
    侧消费位;kernel 观察位禁反向 import strategies,布局依赖矩阵)。

    「切阵后 N 轮内亡率」(771014 型)不在本载体:策略层结构性不可见 hp0
    (结算 drain 跳过 hp_after=0 帧 + hp0 即局终),归档案层离线派生,
    申报义务在案(helper docstring 与交付报告承载)。
    """

    def _sess(self) -> SimpleNamespace:
        return SimpleNamespace(cw4_counters={}, plane_node_table=[1] * 7)

    def _flow(self):
        from sr_od.application.currency_war.strategies.impl.flow import (
            CwFlowStrategy,
        )
        # abstract 桩子类(CwFlowStrategy 的 decide_prep_screen 为 abstract;
        # 本组只驱动方向节拍 _refresh_direction,备战主流程不触达)
        class _Flow(CwFlowStrategy):
            def decide_prep_screen(self, *a, **kw):
                raise NotImplementedError

        return _Flow()

    def test_lock_open_rate_numerator_denominator(self, monkeypatch):
        """低血带新开 lock 开启率载体(wiring 锁:经 _refresh_direction
        生产驱动面触发):分母 = 锁开事件总数,分子 = λ 低血带帧锁开
        (带判定 = 血带结构锚单一源,统一设计稿 §5-F4);率由读端按两键
        比值派生,禁写进计数(只记不判)。非低血带帧只进分母。"""
        monkeypatch.setattr(ci, 'detect_signals', lambda s: [])
        monkeypatch.setattr(ci, 'line_completion_feasibility',
                            lambda *a, **k: 0.5)   # 移交候选可行 → 帧即锁
        strategy = self._flow()
        sess_lo = self._sess()
        strategy._refresh_direction(_st2(hp=10, gold=0), sess_lo)
        ct_lo = state_of(sess_lo).cw4_counters
        assert ct_lo.get('lock_gen_feasibility_obs_lock_open_total') == 1
        assert ct_lo.get('lock_gen_feasibility_obs_lock_open_lowband') == 1
        sess_hi = self._sess()
        strategy._refresh_direction(_st2(hp=40, gold=0), sess_hi)
        ct_hi = state_of(sess_hi).cw4_counters
        assert ct_hi.get('lock_gen_feasibility_obs_lock_open_total') == 1
        assert 'lock_gen_feasibility_obs_lock_open_lowband' not in ct_hi

    def test_no_lock_frame_counts_nothing(self, monkeypatch):
        """分母只辖锁开事件(last_event 转移入锁类前缀):无锁开帧
        (保持锁)零计数——率读数不被保持帧稀释。"""
        monkeypatch.setattr(ci, 'detect_signals', lambda s: [])
        monkeypatch.setattr(ci, 'line_completion_feasibility',
                            lambda *a, **k: 0.5)
        strategy = self._flow()
        sess = self._sess()
        strategy._refresh_direction(_st2(hp=40, gold=0), sess)   # 帧1:移交锁
        strategy._refresh_direction(_st2(hp=40, gold=0, round_num=2), sess)
        ct = state_of(sess).cw4_counters
        assert ct.get('lock_gen_feasibility_obs_lock_open_total') == 1, (
            '帧2保持锁非锁开事件,分母不重复计')

    def test_boss_neardeath_deadzone_keyed_by_domain(self):
        """死区面计数(R1 存疑-1 兑付:boss 窗濒死帧恒闭死区不留白):
        boss 节点 ∧ 濒死带域内帧按授权域分列(_p1/_p2);域外帧不入键。
        直调 helper(帧级观测,不依赖锁开)。"""
        from sr_od.application.currency_war.strategies.impl.flow import (
            bump_lock_gen_feasibility_obs,
        )
        sess = self._sess()
        sess.node_type_current = 'boss'
        bump_lock_gen_feasibility_obs(sess, _st2(hp=10, gold=0),
                                      IntentionState(), 'lock:旧事件')
        assert state_of(sess).cw4_counters.get(
            'lock_gen_feasibility_obs_boss_neardeath_p2') == 1
        assert 'lock_gen_feasibility_obs_lock_open_total' \
            not in state_of(sess).cw4_counters, '无锁开转移 ⇒ 分母不计'
        # 域外对照(hp=40):零计数
        sess2 = self._sess()
        sess2.node_type_current = 'boss'
        bump_lock_gen_feasibility_obs(sess2, _st2(hp=40, gold=0),
                                      IntentionState(), 'lock:旧事件')
        assert 'lock_gen_feasibility_obs_boss_neardeath_p2' \
            not in state_of(sess2).cw4_counters

    def test_new_keys_prefix_registered_no_family_intersection(self):
        """分键登记锁:观察件键族前缀单一源 = flow.LOCK_GEN_FEASIBILITY_
        OBS_PREFIX(设计稿 §4-8 零交集);kernel LOCK_PATH_OBS_KEY_PREFIXES
        不含本前缀(键族分治,载体落位 = flow 侧)。"""
        from sr_od.application.currency_war.strategies.impl.flow import (
            LOCK_GEN_FEASIBILITY_OBS_PREFIX,
        )
        assert LOCK_GEN_FEASIBILITY_OBS_PREFIX == 'lock_gen_feasibility_obs_'
        assert all(not p.startswith(LOCK_GEN_FEASIBILITY_OBS_PREFIX)
                   for p in ci.LOCK_PATH_OBS_KEY_PREFIXES), (
            '键族零交集:kernel 观察前缀族不含本前缀')

    def test_observation_zero_behavior_on_state_machine(self, monkeypatch):
        """只观测零行为守卫:带/不带计数容器的同输入驱动,IntentionState
        终态逐位相等(观测计数不回写状态机;设计稿 §2.3-5(a) 零行为)。"""
        monkeypatch.setattr(ci, 'detect_signals', lambda s: [])
        monkeypatch.setattr(ci, 'line_completion_feasibility',
                            lambda *a, **k: 0.5)
        strategy = self._flow()
        base = None
        for sess in (self._sess(), self._sess()):
            strategy._refresh_direction(_st2(hp=10, gold=0), sess)
            ist = state_of(sess).v3_intention
            snap = {f.name: getattr(ist, f.name)
                    for f in ist.__dataclass_fields__.values()}
            if base is None:
                base = snap
            assert snap == base, '观测计数改变了状态机终态:零行为破线'

    def test_seele_constants_single_source_rider(self):
        """搭车件(T-171 批序 4 挂账兑现):cw_intention 侧 SEELE_OR_LEGS/
        SEELE_CARRY_CHAR 改指 cw_comps 真源(ADR-0621
        0621-seele-static-form-or-fold),双定义恒等态收敛为单一源——
        同对象断言(比恒等值更强的同一性锁)。"""
        assert ci.SEELE_OR_LEGS is _COMPS_SEELE_OR_LEGS
        assert ci.SEELE_CARRY_CHAR is _COMPS_SEELE_CARRY_CHAR
