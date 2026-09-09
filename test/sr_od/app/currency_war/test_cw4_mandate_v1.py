"""cw4 步3+4 批测试(§6.4-R 步4 验收行全项)。

覆盖:四硬约束检查点各一例 / 臂①旁路集函数级枚举对拍(§4.2.1)/
发射器帧稳定截断契约锁(契约 v2 §3.2 逐类+§3.3 fail-closed)/
fail-closed None 槽位(θ_unavailable 分键等)/修复池 OPEN 检查点核销
(P7/D-lv7/F4 落点)/ mandate 行为(M2→M4 重试环/fuel_sell/stop_flag/
D-A45 干旱重置)/ 冒烟(探针语料跑 _emit 无异常+截断判符合 v2)/
R196 修复批(换线活/回锁窗/冲突丢弃/截断逐类/影子键/常数单源)/
R200 三卖面通道语境+塌缩出口保守子集 / RunDeploy 提案抑制(实机
守卫停机事故回归)/ 备战期开店闩(访问位置闩)/ 奖励帧升级抑制
四消费位。头部旧列「零漂移门(商店线透传零污染,n≥20)」已随基线臂
退役删除(见下方「基线臂零漂移复跑」墓碑注),不再入覆盖面。
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.decision_assembly import snapshot_from_obs
from sr_od.application.currency_war.kernel import cw_line_switch
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PREP_ACTION_TYPES,
    BailToOuter,
    ClickSpheres,
    DeferSpheres,
    DeployMove,
    EnsureShopClosed,
    EnsureShopOpen,
    LevelUp,
    OpenBox,
    OpenShop,
    OpenTome,
    PickBoxCard,
    PrepAction,
    PrepObservation,
    RunBuyPhase,
    RunDeploy,
    RunEquip,
    SellBench,
    SellDeployed,
    StartBattle,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    REFRESH_COST_BASE,
    BenchChar,
    GameState,
    LevelUpShop,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    mandate,
    proof,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.assembly import (
    assemble as assemble_turn,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import provisional
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
    decide_from_turn,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    BYPASS_TABLE,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    equipment as crit_equip,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    levelup as crit_levelup,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    sell as crit_sell,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.sell import (
    line_switch_sell,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)
from sr_od.application.currency_war.strategies.mandate_v1_strategy import (
    MandateV1Live,
)

# ===== 测试基建 =====

def _bench(slot: int, name: str, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


class _Pt:
    """探针点(spheres/boxes/tomes 元素坐标载体;snapshot_from_obs 消费)。"""

    def __init__(self, x: int = 100, y: int = 100) -> None:
        self.x, self.y = x, y


def _frame(gold: int = 20, bench=None, deployed=None, cap: int = 4,
           node=None, stop: bool = False, k=(), level: int = 3,
           round_num: int = 3) -> mandate.MandateFrame:
    return mandate.MandateFrame(
        gold=gold, level=level, bench=bench or [], deployed=deployed or [],
        deploy_cap=cap, node_type=node, stop_flag=stop, k_members=k,
        round_num=round_num)


def _session() -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    return s


def _obs(state: GameState | None = None, bench=None, deployed=None,
         spheres=(), boxes=(), tomes=(), vacancy: int = 4) -> PrepObservation:
    return PrepObservation(
        state=state or GameState(gold=20),
        bench_chars=bench or [], deployed_chars=deployed or [],
        spheres=list(spheres), boxes=list(boxes), tomes=list(tomes),
        deploy_vacancy=vacancy)

# ===== ① 四硬约束检查点(§3.2 唯一合法拦截集)=====

class TestHardConstraints:

    def test_checkpoint1_affordable(self):
        ok, why = mandate.check_affordable(3, 5)
        assert not ok and 'gold' in why
        ok, _ = mandate.check_affordable(5, 5)
        assert ok
        # 整批成本按 M3 批量合计
        ok, _ = mandate.check_affordable(9, 0, batch_cost=12)
        assert not ok

    def test_checkpoint2_seats(self):
        ok, why = mandate.check_seats(0, 2, needs_bench=True, needs_board=False,
                                      name='', deployed_names=[])
        assert not ok and why == 'bench_full'
        ok, why = mandate.check_seats(2, 0, needs_bench=False, needs_board=True,
                                      name='x', deployed_names=[])
        assert not ok and why == 'board_full'
        # 同名同星≤1(②对象列穷举:M1/M2/M3/M5/M6/dominance)
        ok, why = mandate.check_seats(2, 2, needs_bench=False, needs_board=True,
                                      name='dup_name',
                                      deployed_names=['dup_name'])
        assert not ok and why == 'same_name_on_board'

    def test_checkpoint3_s_reserve(self):
        # 10−4=6 ≥5 ⇒ 过;10−4=6 <7 ⇒ 拦(检查点③辖 EV 买入面+M6+dominance)
        ok, _ = mandate.check_s_reserve(10, 4, s_reserve=5)
        assert ok
        ok, _ = mandate.check_s_reserve(10, 4, s_reserve=7)
        assert not ok

    def test_checkpoint4_irreversible(self):
        ok, why = mandate.check_irreversible('线内件', ('线内件',))
        assert not ok and why == 'line_member'
        ok, _ = mandate.check_irreversible('燃料件', ('线内件',))
        assert ok


# ===== ② 臂①旁路集函数级枚举对拍(§4.2.1)=====

class TestBypassEnumeration:
    """逐函数全表对拍:criteria/* 全部公开函数位必有 BYPASS_TABLE 行
    (二分全称成立);类别列合法;谓词/状态函数不得标旁路。"""

    def test_criteria_functions_all_enumerated(self):
        pkg_dir = Path(mandate.__file__).parent / 'criteria'
        for py in sorted(pkg_dir.glob('*.py')):
            if py.stem == '__init__':
                continue
            tree = ast.parse(py.read_text(encoding='utf-8'))
            funcs = [n.name for n in tree.body
                     if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')]
            for fn in funcs:
                assert (py.stem, fn) in BYPASS_TABLE, \
                    f'criteria/{py.stem}.{fn} 缺旁路枚举行(R9-1 缺行病)'

    def test_categories_legal(self):
        legal_cat = {'发射位', '门', '谓词', '状态函数', '发射面',
                     '支付支撑通道', '判据/闭式', '结构不变式'}
        legal_arm1 = {'不旁路', '旁路', '旁路=门关闭', '不旁路(两臂同开)'}
        for key, (cat, arm1, _basis) in BYPASS_TABLE.items():
            assert cat in legal_cat, (key, cat)
            assert arm1 in legal_arm1, (key, arm1)
            if cat in ('谓词', '状态函数', '判据/闭式', '结构不变式'):
                assert arm1.startswith('不旁路'), \
                    f'{key}:谓词/状态函数/义务侧判据不得入旁路集(R2-2/F4)'

    #: 零调用面墓碑行(函数已物理删除、登记行保留枚举完备性)。唯一在册
    #: 成员 = equipment.affix_allocation(判据出处纠错批删除的孤儿第二
    #: 实现,生产单一源 = cw_equip_env.resolve_affix_priority_order),
    #: 口径同 test_cw4_contracts.TestRegistryCompleteness._TOMBSTONED_KEYS,
    #: 禁为保绿恢复死代码。
    _TOMBSTONED_KEYS: frozenset[tuple[str, str]] = frozenset({
        ('equipment', 'affix_allocation'),
    })

    def test_bypass_rows_reference_existing_functions(self):
        """反向对拍(行→函数;P25 占位接管批补齐,ADR-0569):BYPASS_TABLE
        每行(墓碑豁免)必须对应 criteria 包内现存公开函数——删函数不删行
        = 红。出处 = 设计《直通核心卡信号层入口》§6 P25 行「全表对拍双向
        强制」(docs/develop/currency_war/design/设计-C1直通核心入口.md)
        + spotcheck δ1 勘误(原稿声称的双向强制在落码前实为单向,
        本测试把设计声称的不变量落成真)。"""
        pkg_dir = Path(mandate.__file__).parent / 'criteria'
        present: dict[str, set[str]] = {}
        for py in sorted(pkg_dir.glob('*.py')):
            if py.stem == '__init__':
                continue
            tree = ast.parse(py.read_text(encoding='utf-8'))
            present[py.stem] = {
                n.name for n in tree.body
                if isinstance(n, ast.FunctionDef)
                and not n.name.startswith('_')}
        orphan = [key for key in BYPASS_TABLE
                  if key not in self._TOMBSTONED_KEYS
                  and key[1] not in present.get(key[0], ())]
        assert not orphan, f'旁路枚举行无对应函数(孤儿行): {orphan}'


# ===== ③ 发射器帧稳定截断契约锁(契约 v2 §3.2 逐类+§3.3)=====

class TestTruncateFrameStable:

    def _classify(self, action) -> str:
        return entry.classify_frame_stability(action)

    def test_17_classes_each_classified(self):
        """17 具体类逐类断言判型(§3.2 备战线域表逐行;R196 症5 对齐:
        ClickSpheres=条件[常态可续/末批可能掉箱后截断]、BailToOuter=
        退役·终点)。"""
        cases = [
            (LevelUp(), 'continue'),
            (DeferSpheres(), 'continue'),
            (SellBench(slot=3), 'conditional'),
            (SellDeployed(row='front', slot=2), 'conditional'),
            (DeployMove(from_slot=1, to_row='back', to_slot=2), 'conditional'),
            (RunDeploy(), 'conditional'),
            (RunEquip(), 'conditional'),
            (StartBattle(), 'terminal'),
            (ClickSpheres(max_k=2), 'conditional'),  # 条件:常态可续/末批截断
            (OpenBox(slot=1), 'truncation'),
            (OpenTome(slot=1), 'truncation'),
            (PickBoxCard(card_idx=0), 'truncation'),
            (EnsureShopOpen(), 'truncation'),        # 退役类兼容面保守判
            (EnsureShopClosed(), 'truncation'),      # 退役类兼容面保守判
            (OpenShop(), 'truncation'),
            (RunBuyPhase(), 'truncation'),           # 退役类兼容面保守判
            (BailToOuter(reason='x'), 'terminal'),   # 退役·终点(契约 §3.2)
        ]
        assert len(cases) == 17
        for action, expect in cases:
            assert self._classify(action) == expect, \
                f'{type(action).__name__}: 期望 {expect}'

    def test_word_list_exhaustive(self):
        """17 具体类(PREP_ACTION_TYPES)全部有分类(§3.3「词表内但无分类」
        不存在)。参数化动作用代表实例。"""
        reps = {SellBench: SellBench(slot=1),
                SellDeployed: SellDeployed(row='front', slot=1),
                DeployMove: DeployMove(from_slot=1, to_row='back', to_slot=1),
                ClickSpheres: ClickSpheres(max_k=1),
                OpenBox: OpenBox(slot=1), OpenTome: OpenTome(slot=1),
                PickBoxCard: PickBoxCard(card_idx=0),
                BailToOuter: BailToOuter(reason='')}
        for cls in PREP_ACTION_TYPES:
            inst = reps[cls] if cls in reps else cls()
            assert entry.classify_frame_stability(inst) != 'unknown', cls

    def test_truncation_point_cuts_tail(self):
        out = entry.truncate_frame_stable(
            [LevelUp(), OpenBox(slot=1), LevelUp(), LevelUp()])
        assert [type(a) for a in out] == [LevelUp, OpenBox]

    def test_terminal_must_be_last(self):
        out = entry.truncate_frame_stable(
            [LevelUp(), StartBattle(), LevelUp()])
        assert [type(a) for a in out] == [LevelUp, StartBattle]

    def test_section_3_3_fail_closed_unknown(self):
        """词表外动作:截断+计数披露(禁静默丢弃)。"""
        class Rogue(PrepAction):
            pass

        session = _session()
        out = entry.truncate_frame_stable(
            [LevelUp(), Rogue(), LevelUp()], session)
        assert [type(a) for a in out] == [LevelUp]
        assert state_of(session).cw4_counters['emitter_unknown_action_truncated'] == 1


# ===== ④ fail-closed None 槽位(每个【拟】槽位 None 行为)=====

class TestFailClosedNoneSlots:

    def setup_method(self):
        provisional.reset()

    def teardown_method(self):
        provisional.reset()

    def _state(self):
        return GameState(gold=20)

    def test_theta_none_no_evaluation_with_split_key(self):
        """θ/D_min/δ 任一 None ⇒ should_switch 不评估 + theta_unavailable
        分键(R24-2:禁复用 switchline_skipped / switchline_exit_blocked)。"""
        session = _session()
        state_of(session).target_comp = COMP_LIBRARY[0]
        out = proof.should_switch(self._state(), session, None, None)
        assert not out.event
        assert out.key == 'theta_unavailable'
        assert 'theta_unavailable' in state_of(session).cw4_counters
        assert 'switchline_skipped' not in state_of(session).cw4_counters
        assert 'switchline_exit_blocked' not in state_of(session).cw4_counters

    def test_arm1_bypass_records_switchline_skipped(self):
        session = _session()
        out = proof.should_switch(self._state(), session, None, None,
                                  skeleton_only=True)
        assert not out.event and out.key == 'switchline_skipped'
        assert 'switchline_skipped' in state_of(session).cw4_counters

    def test_exit_blocked_when_u_vms_none(self):
        """u/V_ms None ⇒ 出口不可用前置 ⇒ switchline_exit_blocked(K 冻结)。"""
        provisional.inject('THETA', provisional.CalibValue(1.0))
        provisional.inject('D_MIN', provisional.CalibValue(2))
        provisional.inject('DELTA_HYST', provisional.CalibValue(0.15))
        session = _session()
        state_of(session).target_comp = COMP_LIBRARY[0]
        out = proof.should_switch(self._state(), session, None, None)
        assert not out.event and out.key == 'switchline_exit_blocked'

    def test_t_search_none_m6_fail_closed(self):
        frame = _frame(gold=99, stop=True, k=())
        session = _session()
        out = mandate.run_mandate(frame, session)
        assert not any(e.reason == 'm6_stock' for e in out)
        assert state_of(session).cw4_counters.get('m6_overflow_strand', 0) >= 1

    def test_ev_buy_candidates_u_none(self):
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
            buy,
        )
        out, key = buy.ev_buy_candidates(50, 0, ['fake'], ('K',))
        assert out == [] and key == 'u_unavailable'


# ===== ⑤ 修复池 OPEN 检查点核销(R189-5 表)=====

class TestFixpoolCheckpoints:

    def test_d_b_wear_release_three_states(self):
        """D-B 三态门:简易件即穿/里程碑收窄释放/强敌节点释放。"""
        ok, why = crit_equip.wear_release(False, None, simple_item=True)
        assert ok and why == 'simple_item'
        ok, why = crit_equip.wear_release(True, None, simple_item=False)
        assert ok and why == 'opening_achieved'
        ok, why = crit_equip.wear_release(False, 'boss', simple_item=False)
        assert ok and why == 'hard_node'
        ok, why = crit_equip.wear_release(False, None, simple_item=False)
        assert not ok and why == 'saving_for_core'

    def test_d_lv7_pop_slot_explicit_reasons(self):
        """D-lv7(OPEN 检查点):pop_slot 对「满编+富金+bench 有候补」覆盖,
        不触发须显式理由进决策迹。"""
        ok, why = crit_levelup.pop_slot(3, 4, 99, 2, 50)
        assert not ok and why == 'not_full'
        ok, why = crit_levelup.pop_slot(4, 4, 99, 0, 50)
        assert not ok and why == 'no_bench_candidate'
        ok, why = crit_levelup.pop_slot(4, 4, 10, 2, 50)
        assert not ok and why == 'gold_below_floor'
        ok, why = crit_levelup.pop_slot(4, 4, 99, 2, 50)
        assert ok and why == 'full_rich_with_candidate'

    def test_d_a45_drought_reset_on_holding(self):
        """D-A45:干旱计数器买入重置语义(存量 ≥1 ⇒ 不累计更不撤线)。"""
        session = _session()
        comp = COMP_LIBRARY[0]
        k = proof.predicates.line_members(comp)
        if not k:
            pytest.skip('COMP_LIBRARY[0] 无成员')
        held = [k[0]]
        proof.update_line_state(session, comp, held, [])
        assert state_of(session).cw4_line_state.drought == 0
        proof.update_line_state(session, comp, [], [])
        proof.update_line_state(session, comp, [], [])
        assert state_of(session).cw4_line_state.drought == 2
        proof.update_line_state(session, comp, held, [])
        assert state_of(session).cw4_line_state.drought == 0

    def test_d_dup_not_deployable(self):
        frame = _frame(bench=[_bench(1, '场上dup')], deployed=[_bench(1, '场上dup')])
        assert not mandate._deployable(frame, _session())

    def test_f4_metric_with_indicator_set(self):
        """F4 度量随指标集呈报:成型判定在新核=stop_buy 位面语义(谓词),
        非单一 form_ok 门(D-FM4 落点);本测试锁谓词形态。"""
        comp = COMP_LIBRARY[0]
        k = proof.predicates.line_members(comp)
        if not k:
            pytest.skip('COMP_LIBRARY[0] 无成员')
        assert proof.stop_buy(comp, list(k), []) is True
        assert proof.stop_buy(comp, list(k)[:-1], []) is False

    def test_d_c44_fresh_read_frame(self):
        """D-C44:骨架输入=黑板全量现读——bench_free 是活派生属性
        (mandate.MandateFrame.bench_free = max(0, BENCH_CAPACITY-len)),
        构造后 bench 变动即时反映;若退化为构造期缓存字段本锁即红。"""
        frame = _frame(bench=[_bench(1, 'a'), _bench(2, 'b')])
        assert frame.bench_free == 7
        frame.bench.append(_bench(3, 'c'))
        assert frame.bench_free == 6


# ===== mandate 行为 =====

class TestMandateBehavior:

    def test_m2_m4_retry_frees_seat(self):
        """M2→M4 重试环:bench 满 ∧ 线内缺件 ⇒ 现场腾席(燃料件卖出)
        后再买(R8-8 单帧闭环)。发射载体 reason 归因面已随 2026-09-08
        用户归因遥测删除指令拆除(缺省 '' 未标;腾席卖出发射行为由
        PrepSellBench 判型断言承载)。"""
        k = ('目标件',)
        bench = [_bench(i, '燃料' + str(i)) for i in range(1, 10)]
        frame = _frame(gold=30, bench=bench, k=k)
        session = _session()
        out = mandate.run_mandate(frame, session)
        reasons = [e.reason for e in out]
        assert any(isinstance(e.action, SellBench) for e in out), \
            '腾席卖出发射缺席'
        assert 'm2_buy' in reasons
        # 席满无燃料可腾(全 3★)⇒ 放弃:耗竭帧零买入意图
        #(m2_retry_exhausted / bench_full_buy_abandon 计数由
        # test_cw_m2_stall_cache.TestPrepStallCache 同帧形 ==1 强断言辖)
        bench2 = [_bench(i, '高价', star=3) for i in range(1, 10)]
        out2 = mandate.run_mandate(_frame(gold=30, bench=bench2, k=k),
                                   _session())
        assert not any(e.reason == 'm2_buy' for e in out2)

    def test_fuel_sell_predicate(self):
        k = ('线内件',)
        bench = [_bench(1, '线内件'), _bench(2, '燃料件'),
                 _bench(3, '高价件', star=3)]
        cands = mandate.fuel_sell_candidates(bench, k)
        assert [c.char_id for c in cands] == ['燃料件']

    def test_stop_flag_classification_not_gate(self):
        """R5-6:stop_flag=分类谓词非拦截门。断言面两腿:①线成型帧
        (stop=True)M1 照常发射——stop 不拦部署(「拦截门」回归即红);
        ②线成型 ⇒ 零买入意图(M2 辖域,与缺件门同向双保险)。"""
        k = ('目标件',)
        frame = _frame(gold=30, bench=[_bench(1, '目标件')], k=k, stop=True)
        session = _session()
        out = mandate.run_mandate(frame, session)
        assert any(e.reason == 'm1_deploy' for e in out)   # stop 不拦 M1
        assert not any(e.reason == 'm2_buy' for e in out)  # 成型 ⇒ 零买入

    # m1_deploy 基础发射由 TestRunDeployProposalSuppression
    # .test_plan_nonempty_frame_run_deploy_emitted 对照臂辖(同发射位同
    # 断言面;M5 开局帧的空板 RunDeploy 发射由 test_m5_opening_only_round1 辖)。
    def test_m5_opening_only_round1(self):
        k = ('目标件',)
        frame = _frame(gold=20, bench=[_bench(1, '目标件')], k=k, round_num=1)
        session = _session()
        out = mandate.run_mandate(frame, session)
        assert any(e.reason == 'm5_opening_board' for e in out)
        assert not any(e.reason == 'm1_deploy' for e in out)

    def test_dominance_gate_param_gold(self):
        """R70-1:金位阈值 g*=10×cap_resolved 参数化(字面 50 实现即红)。
        (stop_flag 形参已随泄金阶梯档 0 摘除:线成型旗不再是支配臂
        触发前置,设计方案 §1.2 档 0/对抗审 F6;本锁只辖金带参数化。)"""
        assert mandate.dominance_buy_eligible(51, 1, cap_resolved=5)
        assert not mandate.dominance_buy_eligible(50, 1, cap_resolved=5)
        assert mandate.dominance_buy_eligible(91, 1, cap_resolved=9)

    def test_signal_arm(self):
        session = _session()
        assert proof.signal_arm(session) is None
        session.active_strategies = ['黑塔纪元']
        assert proof.signal_arm(session) == '黑塔纪元'


# ===== ⑥ 冒烟:探针语料跑 _emit + 零漂移门 =====

class TestEmitSmoke:

    def _run_emit_raw(self, ev_arm: str) -> list:
        strat = MandateV1Strategy()
        session = _session()
        state_of(session).target_comp = COMP_LIBRARY[0]
        cases = [
            _obs(bench=[_bench(1, '燃料件')]),
            _obs(bench=[_bench(i, '燃料' + str(i)) for i in range(1, 10)],
                 vacancy=0),
            _obs(state=GameState(gold=99), bench=[_bench(1, '目标件')],
                 vacancy=0),
            _obs(spheres=[('red', _Pt(), 3)]),
            _obs(boxes=[(2, _Pt())]),
            _obs(),
        ]
        outs = []
        for obs in cases:
            session.prep_obs_frame = obs
            turn = assemble_turn(
                snapshot_from_obs(obs, session), session,
                registry=strat.registry)
            outs.append(entry.emit(obs, turn, session, None, ev_arm=ev_arm,
                                   registry=strat.registry))
        return outs

    def test_emit_full_no_exception_and_contract_conform(self):
        outs = self._run_emit_raw('full')
        trunc_session = _session()
        for emitted in outs:
            actions = entry.truncate_frame_stable(
                [e.action for e in emitted], trunc_session)
            assert isinstance(actions, list)
            for a in actions:
                assert isinstance(a, PrepAction)
            # 截断判符合 v2:若含截断点/终点,必在末位
            for i, a in enumerate(actions):
                kind = entry.classify_frame_stability(a)
                assert kind != 'unknown'
                if kind in ('truncation', 'terminal'):
                    assert i == len(actions) - 1

    def test_emit_skeleton_only_no_exception_and_bypass(self):
        """臂①:EV 发射面旁路 ⇒ 非支撑通道的 mandate=False 发射为零
        (L-B5(a) 哨兵核读:臂①出现 mandate=False 序 3-5 发射 ⇒ 旁路不完整)。"""
        for emitted in self._run_emit_raw('skeleton_only'):
            for e in emitted:
                if not e.mandate:
                    assert e.funding_support, \
                        f'臂①出现非支撑通道 EV 发射:{e.reason}'

    def test_bridge_decide_prep_screen_none_frame_raises(self):
        strat = MandateV1Strategy()
        session = _session()
        with pytest.raises(ValueError, match='prep_obs_frame'):
            strat.decide_prep_screen(session, None)

    def test_bridge_decide_prep_screen_smoke(self):
        """接线烟雾(README 纪律 8 容忍档,MandateV1Live 装配缝唯一载体):
        注册桥壳经真实 registry 注入态走 snapshot→assemble→emit→truncate
        全链产动作列表;形状断言即可,抛错臂/纯层缺省臂各有专测。
        (本缝无逐分支具体断言的子集宿主,删除即 Live 注入半环裸奔。)"""
        strat = MandateV1Live()   # 注册桥壳:装配缝(snapshot_from_obs→assemble)注入态
        session = _session()
        state_of(session).target_comp = COMP_LIBRARY[0]

        class _Cfg:
            ev_arm = 'full'

        obs = _obs(bench=[_bench(1, '燃料件')], vacancy=2)
        session.prep_obs_frame = obs
        out = strat.decide_prep_screen(session, _Cfg())
        assert isinstance(out, list)
        for a in out:
            assert isinstance(a, PrepAction)

    def test_bridge_pure_layer_needs_injection(self):
        """decision 桶纯层(MandateV1Strategy)装配缝缺省=显式抛错
        (依赖矩阵:obs→Snapshot 装配半部在 app 桶;禁 decision→app)。"""
        strat = MandateV1Strategy()
        session = _session()
        session.prep_obs_frame = _obs()
        with pytest.raises(NotImplementedError, match='装配缝'):
            strat.decide_prep_screen(session, None)


# ===== R196 修复批行为测试(换线活/回锁窗/冲突丢弃/截断逐类/影子键)=====

class TestR196Wiring:
    """症1:换线接线修活——alt 供给 + k_switched 实值化 + 分键遥测。"""

    def setup_method(self):
        provisional.reset()

    def teardown_method(self):
        provisional.reset()

    def _inject_switch_params(self):
        provisional.inject('THETA', provisional.CalibValue(1.0))
        provisional.inject('D_MIN', provisional.CalibValue(2))
        provisional.inject('DELTA_HYST', provisional.CalibValue(0.15))
        provisional.inject('U_X', provisional.CalibValue(1.0))
        provisional.inject('V_MS', provisional.CalibValue(1.0))

    def test_should_switch_event_with_alt_supply(self, monkeypatch):
        """换线活:参数齐备 + 候选更优 ⇒ 事件真 + alt_comp 非空(entry 不再
        构造性恒 no_alt)。"""
        self._inject_switch_params()
        comps = [c for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
        session = _session()
        state_of(session).target_comp = comps[0]
        for _ in range(3):
            proof.update_line_state(session, comps[0], [], [])   # dwell=2 ≥ D_min

        def _fake_e(comp, state, registry=None, session=None):
            return 20.0 if comp.name == comps[0].name else 1.0
        monkeypatch.setattr(cw_line_switch, 'e_rounds', _fake_e)
        out = proof.should_switch(GameState(gold=30), session, None, None)
        assert out.event and out.alt_comp is not None
        assert out.alt_comp.name != comps[0].name

    def test_no_alt_and_no_target_split_keys(self, monkeypatch):
        self._inject_switch_params()
        monkeypatch.setattr(proof, 'best_alt_comp', lambda *a, **k: None)
        session = _session()
        state_of(session).target_comp = COMP_LIBRARY[0]
        proof.should_switch(GameState(gold=30), session, None, None)
        assert state_of(session).cw4_counters.get('switchline_no_alt', 0) == 1
        session2 = _session()
        state_of(session2).target_comp = None
        proof.should_switch(GameState(gold=30), session2, None, None)
        assert state_of(session2).cw4_counters.get('switchline_no_target', 0) == 1

    def test_e_cur_undefined_counted(self, monkeypatch):
        def _boom(comp, state, registry=None, session=None):
            raise RuntimeError('degenerate')
        monkeypatch.setattr(cw_line_switch, 'e_rounds', _boom)
        self._inject_switch_params()
        session = _session()
        state_of(session).target_comp = COMP_LIBRARY[0]
        out = proof.should_switch(GameState(gold=30), session, None, None)
        assert not out.event and out.key == 'e_cur_undefined'
        assert state_of(session).cw4_counters.get('switchline_e_cur_undefined', 0) == 1

    def test_relock_window_blocks_within_dmin(self, monkeypatch):
        """D-P4 回锁窗行为锁:构造切换(撤线登记)→ 窗口内回锁请求被拒。"""
        self._inject_switch_params()
        comps = [c for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
        assert len(comps) >= 2
        cur, alt = comps[0], comps[1]
        session = _session()
        state_of(session).target_comp = cur
        # 驻留 ≥ D_min(dwell=2)
        for _ in range(3):
            proof.update_line_state(session, cur, [], [])
        e_map = {cur.name: 20.0, alt.name: 1.0}

        def _fake_e(comp, state, registry=None, session=None):
            return e_map[comp.name]
        monkeypatch.setattr(cw_line_switch, 'e_rounds', _fake_e)
        # 构造切换:alt 显著更优 ⇒ 事件真
        out = proof.should_switch(GameState(gold=30), session, None, None,
                                  alt_comp=alt)
        assert out.event
        proof.register_eviction(session, cur.name)   # entry 采纳时登记
        # K 翻到 alt 后,窗口内(dwell of evicted=0 < D_min=2)请求切回
        # cur(=撤线线)⇒ 回锁窗拦截
        state_of(session).target_comp = alt
        e_map[cur.name], e_map[alt.name] = 1.0, 20.0
        back = proof.should_switch(GameState(gold=30), session, None, None,
                                   alt_comp=cur)
        assert not back.event and back.key == 'relock_window'
        assert state_of(session).cw4_counters.get('switchline_relock_window', 0) == 1
        # 窗口步出(≥ D_min)后回锁解禁
        for _ in range(3):
            proof.update_line_state(session, alt, [], [])
        back2 = proof.should_switch(GameState(gold=30), session, None, None,
                                    alt_comp=cur)
        assert back2.event

    def test_entry_k_switched_real_value(self):
        """k_switched 实值化 + 塌缩出口可达(R197 症1③ 重写:经组装点
        decide_from_turn 全链含截断器,不再直调 entry.emit / 不再 monkeypatch
        判据本体)。

        换线生效帧(K 已翻为 K′、新线有缺口 ⇒ 骨架 M2 发 OpenShop 截断
        点)的 protected_sell 发射经依赖拓扑合并插到截断点之前——不被
        截断器静默丢弃(IMPL_ADV_R197 症1 主场景:EV pass 追加在截断点
        之后 ⇒ 塌缩出口永久错过且零计数)。"""
        class _Cfg:
            def __init__(self, ev_arm: str) -> None:
                self.ev_arm = ev_arm

        # U_X/V_MS 注入形态:line_switch_sell 出口开闸(k_switched 帧
        # 塌缩出口可评估)
        provisional.inject('U_X', provisional.CalibValue(1.0))
        provisional.inject('V_MS', provisional.CalibValue(1.0))
        # 选一对线:old 有独占成员(塌缩出口对象),new ≠ old
        comps = [c for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
        pair = None
        for a in comps:
            for b in comps:
                if a is b:
                    continue
                old_ms = set(proof.predicates.line_members(a))
                new_ms = set(proof.predicates.line_members(b))
                if old_ms - new_ms:
                    pair = (a, b, sorted(old_ms - new_ms)[0])
                    break
            if pair:
                break
        assert pair is not None, 'COMP_LIBRARY 无可构造换线对'
        old_comp, new_comp, old_only = pair
        strat = MandateV1Strategy()
        session = _session()
        state_of(session).target_comp = old_comp
        bench = [_bench(1, old_only)]

        def _decide(round_num: int = 1) -> list[PrepAction]:
            obs = _obs(state=GameState(gold=30, round_num=round_num),
                       bench=bench, vacancy=4)
            turn = assemble_turn(
                snapshot_from_obs(obs, session), session,
                registry=strat.registry)
            return decide_from_turn(
                obs, turn, session, _Cfg('full'), registry=strat.registry)

        _decide(round_num=1)                      # 帧1:登记 prev 线名
        assert state_of(session).cw4_prev_line_name == old_comp.name
        state_of(session).target_comp = new_comp           # K 翻转(基线意向机形态)
        # 帧2:换线生效帧=新备战期(R1-3:K 翻转跨备战期经方向重估
        # 生效,ADR-0583;备战期开店闩按 (位面,轮次) 键,新期自动失效)——夹具按此
        # 建模 round_num+1,锁断言(塌缩出口可达+先于截断点)不变。
        out = _decide(round_num=2)               # 帧2:k_switched=True
        # 塌缩出口发射可达且先于截断点(EV 卖面依赖拓扑合并,症1 修复面)
        sells = [a for a in out if isinstance(a, SellBench)]
        assert [a.slot for a in sells] == [1]
        assert out.index(sells[0]) < len(out) - 1
        assert isinstance(out[-1], OpenShop)      # 新线缺口 ⇒ M2 开店截断点


class TestR196EvConflictDrop:
    """症2:EV 冲突先到先得丢弃 + ev_conflict_dropped 计数。
    (R197 症1③ 重写:两用例均经组装点 decide_from_turn 全链含截断器,
    构造支付支撑帧验证丢弃非重发。)"""

    @staticmethod
    def _decide_full(bench, comp, gold: int = 1,
                     stall_names: tuple = ()) -> tuple[list, StrategySession]:
        class _Cfg:
            ev_arm = 'skeleton_only'

        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            mandate as _mandate,
        )
        strat = MandateV1Strategy()
        session = _session()
        state_of(session).target_comp = comp
        # 差分承载(T-126 批 3 重推,ADR-0585;P78-5′ 四关系表):垫保
        # 登记(T3 单类视图)在凑息是绝对跳过(defer)、在 M4/funding 是
        # 降序放行(转化类)——批 2 用的 ②(b) press 登记随窗口段落地后
        # 全通道硬禁,差分格消失,改 T3 登记承载同款差分。登记轮 1 =
        # obs 帧轮(GameState 缺省 round_num=1),活跃判据 = 登记轮==当前轮。
        for _n in stall_names:
            _mandate.stall_buys_register(session, _n, 1)
        obs = _obs(state=GameState(gold=gold), bench=bench, vacancy=4)
        turn = assemble_turn(
            snapshot_from_obs(obs, session), session, registry=strat.registry)
        out = decide_from_turn(
            obs, turn, session, _Cfg, registry=strat.registry)
        return out, session

    def test_same_slot_dropped_not_resent(self):
        """骨架 M4 已卖槽 vs 支付支撑同槽提案 ⇒ 丢弃 + 计数(全链):
        bench 满 + 缺件 + 金不足 ⇒ M4 卖唯一燃料槽 ⇒ funding 同槽提案
        被丢弃 ⇒ 输出单笔(非重发,非 fail-stop)。
        差分承载(ADR-0585 批 3 重推):凑息臂不抢跑 = T3 垫保登记件
        被凑息绝对跳过(defer);M4/funding 降序放行(转化类,P78-5′
        四关系表「放行(在册语义保持)」)——批 2 的 ②(b) press 登记差分
        随窗口段落地消失(P78 INV 全通道硬禁),本适配按新语义重推。"""
        comp = SimpleNamespace(name='测试线', core_chars=('目标件',),
                               shared_chars=())
        bench = ([_bench(2, '燃料件X')]
                 + [_bench(i, '高价', star=3)
                    for i in (1, 3, 4, 5, 6, 7, 8, 9)])
        out, session = self._decide_full(bench, comp,
                                         stall_names=('燃料件X',))
        sells = [a for a in out if isinstance(a, SellBench)]
        # M4 卖槽 2(唯一燃料);funding 同槽提案丢弃 ⇒ 单笔 + 计数
        assert [a.slot for a in sells] == [2]
        assert state_of(session).cw4_counters.get('ev_conflict_dropped', 0) == 1

    def test_distinct_slot_kept(self):
        """同帧异槽提案保留(全链):缺件注册价 ≥4 ⇒ funding 需两件燃料
        ——低槽与 M4 冲突丢弃,高槽保留 ⇒ 输出两笔异槽卖出。
        差分承载(ADR-0585 批 3 重推,与上锁同源):两燃料件均为 T3 垫保
        登记名(凑息臂绝对跳过不抢跑;M4/funding defer 降序放行,P78-5′
        四关系表)。"""
        m = next(n for n, ch in CHARACTERS.items()
                 if ch.cost and ch.cost >= 5)   # need-金 > 单件燃料回金 3
        comp = SimpleNamespace(name='测试线', core_chars=(m,), shared_chars=())
        bench = ([_bench(2, '燃料件X'), _bench(3, '燃料件Y')]
                 + [_bench(i, '高价', star=3)
                    for i in (1, 4, 5, 6, 7, 8, 9)])
        out, session = self._decide_full(
            bench, comp, stall_names=('燃料件X', '燃料件Y'))
        sells = [a for a in out if isinstance(a, SellBench)]
        # M4 卖槽 2;funding 提案 [2(冲突丢弃), 3(保留)]
        assert sorted(a.slot for a in sells) == [2, 3]
        assert state_of(session).cw4_counters.get('ev_conflict_dropped', 0) == 1


class TestR196TruncationBehavior:
    """症5:截断逐类行为(ClickSpheres 条件/conditional 复检/终点)。"""

    def test_click_spheres_normal_continue_and_last_batch_truncates(self):
        # 非末批(后续还有批次)⇒ 可续
        out = entry.truncate_frame_stable(
            [ClickSpheres(max_k=2), ClickSpheres(max_k=3), LevelUp()])
        assert [type(a) for a in out] == [ClickSpheres, ClickSpheres]
        # 末批(序列内最后一个 ClickSpheres,可能掉箱)⇒ 其后截断
        out2 = entry.truncate_frame_stable(
            [LevelUp(), ClickSpheres(max_k=2), LevelUp()])
        assert [type(a) for a in out2] == [LevelUp, ClickSpheres]

    def test_sellbench_name_slot_recheck(self):
        session = _session()
        # 引用空槽(名-槽一致性复检失败)⇒ 推不出即截断 + 计数
        out = entry.truncate_frame_stable([SellBench(slot=5)], session,
                                          bench_slots={1, 2})
        assert out == []
        assert state_of(session).cw4_counters['emitter_conditional_truncated'] == 1

    def test_sellbench_in_sequence_projection(self):
        """前序累积静态推出:同序列已卖槽位不再在投影集内,二次引用截断。"""
        session = _session()
        out = entry.truncate_frame_stable(
            [SellBench(slot=1), SellBench(slot=1), LevelUp()], session,
            bench_slots={1})
        assert [type(a) for a in out] == [SellBench]
        assert state_of(session).cw4_counters['emitter_conditional_truncated'] == 1

    def test_deploymove_from_slot_recheck(self):
        session = _session()
        out = entry.truncate_frame_stable(
            [DeployMove(from_slot=9, to_row='back', to_slot=1)], session,
            bench_slots={1})
        assert out == []
        assert state_of(session).cw4_counters['emitter_conditional_truncated'] == 1

    def test_composite_conditional_continue(self):
        """组合类(SellDeployed/RunDeploy/RunEquip):按计划静态推出成立可续。"""
        out = entry.truncate_frame_stable(
            [RunDeploy(), LevelUp(), RunEquip()])
        assert [type(a) for a in out] == [RunDeploy, LevelUp, RunEquip]

    def test_no_context_conditional_continues(self):
        """复检语境缺省(None)⇒ 按条件成立续发(生产路径 bridge 总供给)。"""
        out = entry.truncate_frame_stable(
            [SellBench(slot=5), OpenShop(), LevelUp()])
        assert [type(a) for a in out] == [SellBench, OpenShop]

    def test_post_truncation_drop_counted(self):
        """R197 症1②:截断点/终点/词表外丢弃的尾动作逐个计数
        (``emitter_post_truncation_dropped``)——禁零计数静默;全程
        无截断 ⇒ 键不出现。"""
        session = _session()
        out = entry.truncate_frame_stable(
            [LevelUp(), OpenShop(), SellBench(slot=1), LevelUp()], session,
            bench_slots={1})
        assert [type(a) for a in out] == [LevelUp, OpenShop]
        assert state_of(session).cw4_counters['emitter_post_truncation_dropped'] == 2
        # 终点尾丢弃同计
        session2 = _session()
        out2 = entry.truncate_frame_stable(
            [StartBattle(), SellBench(slot=1)], session2, bench_slots={1})
        assert [type(a) for a in out2] == [StartBattle]
        assert state_of(session2).cw4_counters['emitter_post_truncation_dropped'] == 1
        # 词表外:未发射动作(含该动作自身)计入
        session3 = _session()
        out3 = entry.truncate_frame_stable(
            [SellBench(slot=1), OpenShop(), LevelUp(), LevelUp()], session3,
            bench_slots={1})
        assert [type(a) for a in out3] == [SellBench, OpenShop]
        assert state_of(session3).cw4_counters['emitter_post_truncation_dropped'] == 2
        # 无截断全通过 ⇒ 零计数(键不存在)
        session4 = _session()
        out4 = entry.truncate_frame_stable(
            [LevelUp(), SellBench(slot=1)], session4, bench_slots={1})
        assert len(out4) == 2
        assert 'emitter_post_truncation_dropped' not in state_of(session4).cw4_counters


class TestR196ShadowKeys:
    """症3:λ 影子=相对分位求值后计数;真键/血线影子载体落地(零新键)。"""

    def setup_method(self):
        provisional.reset()

    def teardown_method(self):
        provisional.reset()

    def _top_danger_state(self) -> GameState:
        """构造落 λ_U 降序全序首位的 PL 键帧(可消费格)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
            lambda_death,
        )
        order = lambda_death.lambda_u_order()
        target = order[0]
        for key, c in lambda_death._LAMBDA_TABLE.items():
            if c.label == '可消费' and c.ci_hi == target:
                d, hp, _pl, node = key.split('|')
                return GameState(
                    gold=20,
                    enemy_difficulty=100 if d == 'D0' else 120,
                    hp=10 if hp == 'hp<=15' else (30 if hp == 'hp15-40' else 50),
                    plane=1 if _pl == 'P1' else 2, node_type=node)
        pytest.fail('无可消费格')

    def test_lambda_none_period_no_keys(self):
        sig = entry._upgrader_evaluate(_session(), self._top_danger_state(),
                                       20, 10)
        assert not sig.lambda_shadow_armed and not sig.lambda_armed

    def test_lambda_inject_arms_true_key_with_shadow_control(self):
        """λ 顾问注入即武装(R28-1;R196 症3 载体):真键 + 影子对照键
        同置(对照键保留,禁删)。生产 _upgrader_evaluate 不读
        CalibValue.injected_form(全仓零消费,判别力检验法),注入形态
        与标定形态同一断言面,合并单锁。"""
        provisional.inject('P_LAMBDA_QUANTILE', provisional.CalibValue(0.15))
        st = self._top_danger_state()
        sig = entry._upgrader_evaluate(_session(), st, 20, st.hp)
        assert sig.lambda_armed and sig.lambda_shadow_armed   # 对照键保留
        # 健康帧(高血带)不触发:谓词求值结果非 True(触发/域外不求值均合)
        st2 = GameState(gold=20, enemy_difficulty=100, hp=50, plane=1,
                        node_type='reward')
        assert entry._lambda_quantile_armed(st2, 50, 0.15) is not True

    def test_bloodline_none_period_shadow(self):
        """血线阈值 None 期:注入形态结构锚 hp15 照测影子键(行为无关)。"""
        sig = entry._upgrader_evaluate(_session(), GameState(gold=20), 20, 10)
        assert sig.bloodline_shadow_armed
        assert sig.neardeath_unlock and sig.f7_ban_armed  # 标定落地:武装
        sig2 = entry._upgrader_evaluate(_session(), GameState(gold=20), 20, 30)
        assert not sig2.bloodline_shadow_armed
        assert not sig2.neardeath_unlock and not sig2.f7_ban_armed


class TestR196Constants:
    """症6:常数单源(症4 的 bench_full_buy_abandon 事件计数由
    test_cw_m2_stall_cache.TestPrepStallCache 同帧形 ==1 强断言辖)。"""

    def test_bench_capacity_single_source(self):
        from sr_od.application.currency_war.kernel.cw_state import (
            BENCH_CAPACITY as KERNEL_BENCH_CAPACITY,
        )
        assert mandate.BENCH_CAPACITY == KERNEL_BENCH_CAPACITY
        src = Path(mandate.__file__).read_text(encoding='utf-8')
        assert 'BENCH_CAPACITY: int = 9' not in src   # 本地重定义已删

    def test_cheapest_member_cost_registry_derived(self):
        comps = [c for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
        comp = comps[0]
        members = proof.predicates.line_members(comp)
        frame = _frame(k=members)
        expect = min((CHARACTERS[m].cost for m in members
                      if CHARACTERS.get(m) and CHARACTERS[m].cost),
                     default=3)
        assert mandate.cheapest_member_cost(frame) == expect

    def test_s_reserve_s_line_assembly(self):
        """S 预留 = s_line 组装(非恒 0):默认局 = 0+saturation(cap)+0
        +2×刷费基价(E[刷费]×2 分量,期望值自 REFRESH_COST_BASE 现算)。"""
        frame = _frame()
        session = _session()
        assert mandate._s_reserve(frame, session) == \
            mandate.saturation_line(mandate._cap_of(session)) \
            + 2 * REFRESH_COST_BASE

    def test_funding_refund_registry_derived(self):
        from sr_od.application.currency_war.kernel.cw_state import sell_refund
        # 注册名:sell_refund(1, 注册表 cost) 派生
        name = next(n for n, ch in CHARACTERS.items() if ch.cost)
        cost = CHARACTERS[name].cost
        slots, _ = crit_sell.funding_support_sell(
            0, sell_refund(1, cost), [_bench(1, name, star=1)], ('K',))
        assert slots == [1]
        # 未注册探针名:保守估 3(与旧字面量行为同构)
        slots2, _ = crit_sell.funding_support_sell(
            0, 3, [_bench(1, '燃料件X', star=1)], ('K',))
        assert slots2 == [1]


# ===== 基线臂零漂移复跑(步4b 透传拆除后;慢桶)=====
# (基线臂零漂移门已随基线臂退役删除——统一迁移批 ② A9:sim 被测体=
#  mandate_v1 单臂,自配对门 = ab_core_swap.new_core_self_pairing_gate。)

# ===== ⑦ R200 修复批:三卖面通道语境接线 + 塌缩出口保守子集(IMPL_ADV_R200)=====

class TestR200BenchEffectChannels:
    """症3:三卖面通道(fuel_sell/sell_for_interest/funding_support)统一
    消费共享装配的语境(黑塔例外件按语境保护,语境缺场回归燃料);
    症5③:line_switch_sell 注入态保守子集(仅燃料类放行)。"""

    def test_fuel_sell_protects_herta_in_context(self):
        """黑塔例外:语境在场(augment 局)⇒ 不入燃料集;语境缺场 ⇒
        回归燃料(星级供强无承载对象);state=None ⇒ 缺省保守保护。"""
        k = ('线内件',)
        bench = [_bench(1, '黑塔'), _bench(2, '燃料件')]
        # 语境缺场(空 state):黑塔回归燃料
        st_off = GameState()
        cands = mandate.fuel_sell_candidates(bench, k, state=st_off)
        assert [c.char_id for c in cands] == ['黑塔', '燃料件']
        # 语境在场(黑塔纪元 augment 局):黑塔受保护
        st_on = GameState()
        st_on.active_strategies = ['黑塔纪元']
        cands2 = mandate.fuel_sell_candidates(bench, k, state=st_on)
        assert [c.char_id for c in cands2] == ['燃料件']
        # 缺读保守端:state=None ⇒ 保护(黑塔不入燃料)
        cands3 = mandate.fuel_sell_candidates(bench, k)
        assert [c.char_id for c in cands3] == ['燃料件']

    def test_funding_support_channel_uses_context(self):
        """支付支撑通道同资格:语境在场 ⇒ 例外件不作为筹资燃料。"""
        cost = CHARACTERS['黑塔'].cost
        bench = [_bench(1, '黑塔'), _bench(2, '阿格莱雅')]
        st_on = GameState(gold=0)
        st_on.active_strategies = ['黑塔纪元']
        slots, _ = crit_sell.funding_support_sell(
            0, 2 + cost, bench, ('线内件',), state=st_on)
        assert slots == [2]     # 黑塔被保护,由无载体件筹资
        # 缺省(state=None)保守端同款保护
        slots2, _ = crit_sell.funding_support_sell(
            0, 2 + cost, bench, ('线内件',))
        assert slots2 == [2]

    def test_sell_for_interest_channel_uses_context(self):
        """凑息卖 T1 语义重写(设计 13_buy_face_design §2.2;旧锁
        「T_SEARCH_A 注入态资格全集无差别全发」语义已被取代——T1 三项:
        金位触发+目标量止盈+布尔门退役)。资格谓词不变:语境在场
        (黑塔纪元)⇒ 例外件受保护;语境缺场回归资格集。"""
        bench = [_bench(1, '黑塔'), _bench(2, '阿格莱雅')]
        st_on = GameState()
        st_on.active_strategies = ['黑塔纪元']
        # 非缺口帧零发射(gold ≥ g*=saturation_line(5)=50 ⇒ 不卖)
        slots, key = crit_sell.sell_for_interest(
            50, bench, 5, ('线内件',), state=st_on)
        assert key == 'not_needed' and slots == []
        # 缺口帧:语境保护(黑塔不入),资格集内卖到缺口覆盖为止
        # (黑塔+阿格莱雅退金合计 < 缺口 20 ⇒ 贪心尽头卖 1 张资格件)
        slots, key = crit_sell.sell_for_interest(
            30, bench, 5, ('线内件',), state=st_on)
        assert key == '' and slots == [2]
        # 缺省语境缺场:资格集全体入桶(贪心尽头,Σrefund < 缺口)
        slots2, _ = crit_sell.sell_for_interest(
            30, bench, 5, ('线内件',), state=GameState())
        assert slots2 == [1, 2]


class TestR200LineSwitchConservativeSubset:
    """症5③:U_X/V_MS 注入且全式未落位期间,塌缩出口返回保守子集
    (燃料类:1★ 全额可退,p41 支配性论证「卖错代价≈0」)而非全集。"""

    def test_injected_state_returns_fuel_subset_only(self):
        provisional.inject('U_X', provisional.CalibValue(1.0))
        provisional.inject('V_MS', provisional.CalibValue(24.7))
        try:
            bench = [_bench(1, '旧A', star=1),        # 1★ 全额退 → 放行
                     _bench(2, '旧B', star=2),        # 2★ → 保留(保守)
                     _bench(3, '新线共用'), _bench(4, '无关件')]
            slots, key = line_switch_sell(
                ('旧A', '旧B', '新线共用'), ('新线共用',), bench, [],
                GameState(), k_switched=True)
            assert key == ''
            assert slots == [1]       # 全集悬崖已消:2★ 旧线件保留
        finally:
            provisional.reset('U_X')
            provisional.reset('V_MS')

    def test_none_period_still_blocked(self):
        slots, key = line_switch_sell(
            ('旧件',), ('新件',), [_bench(1, '旧件')], [], None,
            k_switched=True)
        assert slots == [] and key == 'switchline_exit_blocked'


# ===== RunDeploy 提案侧抑制谓词(ADR-0517 决策2/dd-037 接线)=====

class TestRunDeployProposalSuppression:
    """RunDeploy 计划空 ⇒ 不提案(序内下一动作)。

    事件语义回归:2026-09-06 实机首局(单动作架构,ADR-0518)00:08:25
    备战环无进展守卫以「连续 3 环同签名动作批 ['RunDeploy'] ∧ 零推进」
    停机留证——决策核每轮提案 RunDeploy,执行方 cw_op_deploy 计划空
    (候选全被配方底线规则留 bench)报 no-op 成功,RunDeploy 投影未
    建模保守回退交回外循环,重进再提案,3 环零推进。修复 = 发射位
    (M1/M1′/M5)接入 kernel.cw_deploy_logic.has_deployable 同源判空谓词。
    """

    def _floor_gate_frame(self) -> mandate.MandateFrame:
        """计划空帧:板 2 列车同行(档满)∧ 仙舟<3 基础线 ∧ bench 第 3
        张列车件 ⇒ kernel 配方底线门留 bench(select_deployments up 空)。
        旧 _deployable(持有面:bench 有货非 dup)对该帧判 True。"""
        return _frame(
            gold=20, cap=8,
            bench=[_bench(1, '开拓者·欢愉')],
            deployed=[_bench(1, '三月七'), _bench(2, '姬子')],
            k=('目标件',), round_num=3)

    def test_plan_empty_frame_not_deployable(self):
        assert not mandate._deployable(self._floor_gate_frame(), _session())

    def test_plan_empty_frame_no_run_deploy_proposal(self):
        """计划空帧 ⇒ 不提案 RunDeploy(序内下一动作 = 开店意图/终点
        StartBattle)——旧形态每轮提案 RunDeploy 空转即守卫停机的直接
        机制腿。"""
        out = mandate.run_mandate(self._floor_gate_frame(), _session())
        assert not any(isinstance(e.action, RunDeploy) for e in out)

    def test_plan_nonempty_frame_run_deploy_emitted(self):
        """对照:计划非空(仙舟件不受列车底线门辖)⇒ M1 照常提案。"""
        frame = _frame(
            gold=20, cap=8,
            bench=[_bench(1, '彦卿')],
            deployed=[_bench(1, '三月七'), _bench(2, '姬子')],
            k=('目标件',), round_num=3)
        out = mandate.run_mandate(frame, _session())
        assert any(e.reason == 'm1_deploy' for e in out)


# ===== 备战期开店闩(闩置位时机=商店决策访问位;2026-09-05 实机回归)=====

_COMP_LINE = next(c for c in COMP_LIBRARY if c.name == '列车同行')


def _visit_state(round_num: int) -> GameState:
    """商店访问帧:线成型(列车同行全员 2★ 上场 ⇒ stop_buy 成立)+ 店面空
    ⇒ decide_shop_action 以 CloseShop 终结——构造「OpenShop 已执行成功、
    商店域决策访问已发生」的最小真时点(与实机开店→店内决策循环同构)。"""
    return GameState(
        plane=1, round_num=round_num, gold=100, level=6, hp=80,
        shop_refresh_cost=2,
        deployed=[BenchChar(slot=20 + i, char_id=m, faction='仙舟罗浮',
                            star=2)
                  for i, m in enumerate(line_members(_COMP_LINE))],
        bench=[None] * BENCH_CAPACITY,
        shop=[],
        node_type='battle', board={})


class TestShopPhaseLatch:
    """备战期开店闩:闩置位在商店决策访问位(mandate_v1/shop.
    decide_shop_action 入口),不在 mandate 发射位。

    语义演进:旧实现「发射即置闩」在单动作备战环下漏烧——同发射列表里
    dd-027 回排后的 RunEquip(可续类)先执行即投影未建模终结本环,其后
    的 OpenShop 意图未执行而闩已烧,后续环 mandate 重跑被闩挡死 ⇒ 空批
    StartBattle(2026-09-05 实机局 run_20260905_024059 备战环连续三轮
    经济冻结,诊断归档
    .debug/temp/currency_war/20260905_noprogress_stop_diag/report.md C3)。
    修法 = 置位时机移到访问发生位:闩未烧时发射位照常重发(下帧重试);
    访问发生(开店动作真执行)后同期不再重发——「期内重开无信息量」的
    防重燃论证保持不变。发射永不落地的残值活锁由 DD-030 环级无进展守卫
    兜底,不在本闩职责内。
    """

    def _stuck_frame(self, round_num: int = 1) -> mandate.MandateFrame:
        """M2 开店帧:线缺成员∧金足(4≥未注册名保守价3)∧
        板 3/4 有 vacancy ∧ bench 有可部署件。"""
        return _frame(gold=4, level=4,
                      bench=[_bench(4, '乱破')],
                      deployed=[_bench(1, '甲'), _bench(2, '乙'),
                                _bench(3, '丙')],
                      k=('缺件一', '缺件二'), round_num=round_num)

    def test_emit_does_not_set_latch_and_rerun_reemits(self):
        """回归锁①(事故形态):同帧发射 [RunEquip, OpenShop](dd-027
        回排序),单动作环 RunEquip 先执行终结本环、OpenShop 未执行——
        下一环 mandate 重跑:开店闩未烧 ⇒ OpenShop 重新发射(旧实现
        此处闩已烧 ⇒ 空批);装备闩同为执行位、亦未烧 ⇒ RunEquip 同帧
        重发(实机下环 RunEquip 真执行、执行位置闩,再下环 OpenShop
        独占发射面即达商店)。"""
        s = _session()
        s.last_owned_equips = ['和平手枪']       # 可穿件 ⇒ 同帧 M7 发射
        f = self._stuck_frame()
        out1 = mandate.run_mandate(f, s)
        kinds = [type(e.action) for e in out1]
        assert RunEquip in kinds and OpenShop in kinds
        assert kinds.index(RunEquip) < kinds.index(OpenShop)   # dd-027 回排
        assert getattr(s, 'cw4_shopped_phase', None) is None   # 发射不置闩
        out2 = mandate.run_mandate(f, s)
        assert any(isinstance(e.action, OpenShop)
                   and not e.action.read_only for e in out2)   # 闩未烧,重发
        assert any(isinstance(e.action, RunEquip) for e in out2)
        assert state_of(s).cw4_counters.get('shop_latch_skip_m2_buy', 0) == 0

    def test_shop_visit_sets_latch(self):
        """回归锁②:开店执行成功(商店域决策访问已发生)后闩置位——
        同期后续帧不再发开店意图、分站计数跳过;M1 部署不受闩影响照常
        发射。"""
        st = _visit_state(round_num=3)
        s = _session()
        state_of(s).target_comp = _COMP_LINE
        act = decide_shop_action(st, s, SimpleNamespace(ev_arm='full'))
        # gold=100 为必花域帧(20 号稿 L3 落码):店面空 ⇒ 分层末位 L3
        # 升级消费(LevelUpShop),不再以 CloseShop 终结;闩语义不变。
        assert isinstance(act, LevelUpShop)
        assert act.auth_basis == 'm3_batch:must_spend'
        assert state_of(s).cw4_shopped_phase == (1, 3)       # 闩置位=访问位
        f = self._stuck_frame(round_num=3)
        out = mandate.run_mandate(f, s, state=st)
        assert not any(isinstance(e.action, OpenShop) for e in out)
        assert any(e.reason == 'm1_deploy' for e in out)
        assert state_of(s).cw4_counters.get('shop_latch_skip_m2_buy', 0) == 1

    def test_phase_advance_reopens_shop(self):
        """换备战期(轮次推进=新店内容)闩失效,M2 重新决策开店。"""
        s = _session()
        state_of(s).target_comp = _COMP_LINE
        decide_shop_action(_visit_state(round_num=1), s,
                           SimpleNamespace(ev_arm='full'))
        out = mandate.run_mandate(self._stuck_frame(round_num=2), s,
                                  state=_visit_state(round_num=2))
        assert any(e.reason == 'm2_buy' for e in out)

    def test_failed_visit_no_latch(self):
        """店未开成(bench 满∧无燃料=本帧零 OpenShop 发射)不置闩,
        同会话下帧席位可得时照常重试(决策权保留)。"""
        s = _session()
        bench = [_bench(i, '高价', star=3) for i in range(1, 10)]
        out1 = mandate.run_mandate(
            _frame(gold=30, bench=bench, k=('目标件',)), s)
        assert not any(isinstance(e.action, OpenShop) for e in out1)
        assert state_of(s).cw4_counters.get('m2_retry_exhausted', 0) >= 1
        out2 = mandate.run_mandate(
            _frame(gold=30, bench=[_bench(1, '随意件')], k=('目标件',)), s)
        assert any(e.reason == 'm2_buy' for e in out2)




# ===== T-115 规则① 奖励帧升级抑制(ADR-0580;四消费位 + 扑满守卫)=====

def _m3_shop_state(gold, node, deployed=None, bench=None):
    """M3 消费位帧构造:默认空板(三臂未触发形态,必花域变体辖);
    传 deployed/bench 构造 arm1 形态(cap7 板满 + bench 仙舟候补);
    xp 贴线 1 击保预算闸可过。"""
    st = GameState(gold=gold, level=7, hp=80, plane=1, round_num=3)
    st.node_type = node
    st.xp_progress = (48, 52)
    st.level_up_cost = 4
    st.deployed = list(deployed or [])
    st.bench = list(bench or [])
    st.shop = []
    return st


def _arm1_board():
    """arm1 命中板面:cap7 板满(丹恒·饮月=仙舟供羁绊,花火 2★ 压 ρ
    合格集)+ bench 仙舟候补藿藿;不抑制时必发 m3_batch:arm1。"""
    deployed = [_bench(1, '丹恒·饮月', star=1), _bench(2, '花火', star=2)]
    deployed += [_bench(i, '高价', star=3) for i in range(3, 8)]
    return deployed, [_bench(1, '藿藿', star=1)]


class TestRewardNodeSuppress:
    """奖励帧抑制四消费位锁(判据单一源 = kernel.cw_reward_node)。

    裁定权威 = 用户账本 408 行(「1-1/1-2 等奖励关不需要战力:升级抑制、
    买卡压牌库优先」)。分键判读契约:reward_node_defer(奖励帧抑制)≠
    blood_xp_gate_defer(血闸拒)≠ crisis_level_spend_defer(停付线拒),
    抑制先行 = 结构性无授权时支付能力检查不求值,同帧不混桶。
    """

    def test_shop_m3_suppressed_on_reward_frame(self):
        """消费位1(shop M3):奖励帧三臂被抑制短路 ⇒ 零 LevelUpShop +
        reward_node_defer 分键;红证 = 同帧形 combat 节点照发
        m3_batch:arm1(发射缺席的承载原因 = 抑制,非闸链拒)。"""
        deployed, bench = _arm1_board()
        s = _session()
        act = decide_shop_action(_m3_shop_state(70, 'reward', deployed, bench),
                                 s, SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, LevelUpShop)
        assert state_of(s).cw4_counters.get('reward_node_defer') == 1
        s2 = _session()
        act2 = decide_shop_action(_m3_shop_state(70, 'battle', deployed, bench),
                                  s2, SimpleNamespace(ev_arm='full'))
        assert isinstance(act2, LevelUpShop)
        assert act2.auth_basis == 'm3_batch:arm1'

    def test_shop_must_spend_variant_suppressed(self):
        """消费位2(shop 必花域变体):大金奖励帧(gold>G_must,三臂未
        触发)⇒ 变体显式拒,分键 reward_node_must_spend_defer;红证 =
        combat 帧同形照发 m3_batch:must_spend(绕行面补守卫的承载)。"""
        s = _session()
        st = _m3_shop_state(60, 'reward')
        act = decide_shop_action(st, s, SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, LevelUpShop)
        ct = state_of(s).cw4_counters
        assert ct.get('reward_node_must_spend_defer') == 1
        assert ct.get('reward_node_defer') == 1   # 帧级抑制判据恒触达
        s2 = _session()
        st2 = _m3_shop_state(60, 'battle')
        act2 = decide_shop_action(st2, s2, SimpleNamespace(ev_arm='full'))
        assert isinstance(act2, LevelUpShop)
        assert act2.auth_basis == 'm3_batch:must_spend'

    def test_prep_m3_suppressed_before_blood_gate(self):
        """消费位3(mandate M3):hp=1 濒死奖励帧——抑制先于危机/血闸
        求值:仅 reward_node_defer,crisis/blood 分键零产生(同帧双闸
        不混桶);红证 = 同帧形 encounter 节点走危机带挂起分键。"""
        f, sess, st = _mk_prep_reward_frame('reward')
        out = mandate.run_mandate(f, sess, state=st)
        assert not [e for e in out if isinstance(e.action, LevelUp)]
        ct = state_of(sess).cw4_counters
        assert ct.get('reward_node_defer') == 1
        assert 'crisis_level_spend_defer' not in ct
        assert 'blood_xp_gate_defer' not in ct
        f2, sess2, st2 = _mk_prep_reward_frame('encounter')
        out2 = mandate.run_mandate(f2, sess2, state=st2)
        assert not [e for e in out2 if isinstance(e.action, LevelUp)]
        assert state_of(sess2).cw4_counters.get(
            'crisis_level_spend_defer') == 1

    def test_entry_posture_yield_first_in_chain(self, monkeypatch):
        """消费位4(entry posture):奖励帧授权面让位 = reward_node_yield
        (分键 posture_reward_node_defer);D2 位次钉死:奖励帧在血闸拒
        语境(金本位闸恒直通,patch 闸拒载体钉位次)下 reason 仍是奖励
        让位而非 blood_xp_gate_blocked——让位居授权链首位,置于血闸
        之后则本分键永不可达。"""
        un = _posture_unfulfilled_for(
            GameState(gold=60, level=7, hp=80, plane=1, round_num=3,
                      node_type='reward'), monkeypatch)
        assert un is not None
        assert un['reason'] == 'reward_node_no_power_need'
        assert un['action'] == 'reward_node_yield'
        monkeypatch.setattr(entry, 'blood_xp_gate_for',
                            lambda state, session: False)
        un_blood = _posture_unfulfilled_for(
            GameState(gold=8, level=7, hp=5, plane=1, round_num=3,
                      node_type='battle', hp_readable=True, hp_trusted=True),
            monkeypatch)
        assert un_blood is not None
        assert un_blood['reason'] == 'blood_xp_gate_blocked'
        un_reward_blood = _posture_unfulfilled_for(
            GameState(gold=8, level=7, hp=5, plane=1, round_num=3,
                      node_type='reward', hp_readable=True, hp_trusted=True),
            monkeypatch)
        assert un_reward_blood is not None
        assert un_reward_blood['reason'] == 'reward_node_no_power_need'

    def test_piggy_env_lifts_suppression_and_revives_telemetry(self):
        """扑满守卫(环境名单判据):过热环境帧(经济过热,PLAZA_PORTALS
        id105 派生名单)抑制解除,M3 照常评估;v3_piggy_reward 死字段
        复活为真写点(ADR-0348 ↺)。非过热奖励帧标记保持 False。"""
        s = _session()
        st = _m3_shop_state(60, 'reward')
        st.active_env = '经济过热'
        decide_shop_action(st, s, SimpleNamespace(ev_arm='full'))
        assert state_of(s).cw4_counters.get('reward_node_defer') is None
        assert state_of(s).v3_piggy_reward is True
        s2 = _session()
        st2 = _m3_shop_state(60, 'reward')
        decide_shop_action(st2, s2, SimpleNamespace(ev_arm='full'))
        assert state_of(s2).cw4_counters.get('reward_node_defer') == 1
        assert state_of(s2).v3_piggy_reward is False

    def test_node_type_none_fail_open(self):
        """None fail-open(失效方向①):节点行被遮帧不抑制
        (reward_node_defer 零产生),与规则① None 方向声明一致。"""
        s = _session()
        st = _m3_shop_state(60, None)
        decide_shop_action(st, s, SimpleNamespace(ev_arm='full'))
        assert state_of(s).cw4_counters.get('reward_node_defer') is None


def _mk_prep_reward_frame(node):
    """消费位3 共用帧形(hp=1 濒死 arm1 帧;形态同
    test_cw_l3_prep_must_spend_latch harness,最小独立构造防跨文件夹具
    漂移)。"""
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
    )
    deployed = [_bench(i + 1, n, star=2 if n == '椒丘' else 1)
                for i, n in enumerate(['藿藿', '艾丝妲', '丹恒·饮月',
                                       '风堇', '爻光', '彦卿', '椒丘'])]
    bench = [_bench(i + 1, n, star=1)
             for i, n in enumerate(['千冶·刃', '银狼LV.999', '卡芙卡'])]
    frame = mandate.MandateFrame(
        gold=43, level=7, bench=bench, deployed=deployed,
        deploy_cap=7, node_type=node, stop_flag=False,
        k_members=('卡芙卡', '千冶·刃', '银狼LV.999'), round_num=5)
    st = GameState(gold=43, level=7, hp=1, plane=2, round_num=5)
    st.level_readable = True
    st.node_type = node
    st.xp_progress = (22, 52)
    st.level_up_cost = 4
    sess = SimpleNamespace(cw4_counters={}, target_comp=None,
                           v3_intention=IntentionState(),
                           active_strategies=[])
    return frame, sess, st


def _posture_unfulfilled_for(state, monkeypatch):
    """entry 授权面让位求值(monkeypatch get_node_goal 恒 level 授权)。"""
    from sr_od.application.currency_war.kernel import cw_economy
    monkeypatch.setattr(
        cw_economy, 'get_node_goal',
        lambda *a, **k: SimpleNamespace(spend_mode='level'))
    sess = _session()
    state_of(sess).cw4_counters = {}
    return entry._reconcile_posture_authorization(sess, state, [], ())
