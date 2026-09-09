"""21 号稿「opening 窗口收窄 与 工具件消费语义」落码锁面(ADR-0531)。

设计出处 = docs/develop/currency_war/strategy-docs/
21_opening_window_and_tool_consume.md(v3,对抗零发现收口);锁面分组:
1. O1 战斗前置释放门(§2.3 三门;收编 row3 并前移);
2. O2 自由件即穿门 + 自由件谓词(§2.2/§6 术语;支配性论证零新参数);
3. hold 保留域五条(§2.3;含唯一 key 件扣留 = §2.5 有意行为变化);
4. 求值序(O3 压倒保留域全体;清单外一律释放——含 row1 帧域 key 命中
   件释放锁,v3,L6:实现若把 key 过滤留在 hold 判定内该锁红);
5. 遥测分键(§5:opening(row1) 域分键,row1/row2 预期相反须可判读);
6. 工具件消费判据(全量收编 10 号稿 §2.1,冷启动分支 = 炉准入+扳手闸;
   令牌 R(c) 缺档 fail-closed;特权卡「持有不泄」)+ G1 发射位准入
   (§2.4-2/流程:197,执行通道未建档不发射);
7. sim 注入基建缺省零漂移(§4/§5 最小面)。
row2(committed)语义不回归锁在本文件 test_row2_semantics_unchanged、
test_cw_equip.py「穿戴语义代表行」节与 test_cw_opening_hold.py
(row1 域标记面;第十六局 P2r5-r7 对照,§4 保留域行)。
"""
from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
from sr_od.application.currency_war.data.cw_synthesis import (
    component_demand,
    recycle_qualified,
)
from sr_od.application.currency_war.kernel.cw_comps import Comp
from sr_od.application.currency_war.kernel.cw_equip_env import (
    TOOL_REJECT_COLD_START_LATER,
    TOOL_REJECT_DEST_UNREADY,
    TOOL_REJECT_G1_NOT_ADMITTED,
    TOOL_REJECT_IN_DEMAND,
    TOOL_REJECT_M1_GAP,
    TOOL_REJECT_NO_TARGET,
    TOOL_REJECT_RC_MISSING,
    ZERO_WEAR_EXECUTION,
    ZERO_WEAR_STRATEGY_BY_DESIGN,
    ZERO_WEAR_STRATEGY_BY_DESIGN_OPENING,
    admitted_tool_actions,
    battle_precede_release_active,
    classify_item_hold,
    classify_zero_wear_stop_reason,
    evaluate_tool_actions,
    is_free_item,
    is_unique_equipment,
    resolve_wear_release,
)
from sr_od.application.currency_war.sim.engine_p1 import (
    TOOL_GRANT_INJECT_P,
    TOOL_GRANT_INJECT_POOL,
)

_BATTLE = frozenset({'战斗', 'boss', '遭遇', '精英'})

_ADV = '反重力皮靴'        # 进阶非唯一(注册表直查兜底断言)
_KEY = '火力风暴潮'        # 进阶非唯一
_UNIQUE = '电光履'          # 进阶唯一
_UNIQUE_PRIV = '电光履·特权'  # 特权唯一(特权卡判据用)
_BASE = '轮滑鞋'            # 简易基础件
_TOOL = '冶金炉'


def _mk_comp(cores, keys=None):
    c = Comp(name='测试线', factions=['贝洛伯格'], core_chars=list(cores),
             form_tiers={}, strength=5.0, form_difficulty='hard')
    c.key_equips = list(keys or [])
    return c


def _row1(comp=None, committed=False, next_node=None, node='奖励',
          rust=False, penalty=False):
    """row1 帧域判定(P1 r≤2 非战斗节点;21 号稿收窄后 = 域标记非帧级扣留)。"""
    return resolve_wear_release(
        2, node, True, _BATTLE, comp, 0.2, committed,
        (['库藏生锈'] if rust else []) + (['软弱无力'] if penalty else []),
        True, next_node_type=next_node)


def _assert_real(name: str, want_unique: bool = False) -> str:
    e = EQUIPMENTS.get(name)
    assert e is not None, f'注册表缺 {name},锁面样本名失效须换真名'
    assert ('唯一装备' in e.effect) == want_unique, name
    return name


# ===== 1. O1 战斗前置释放门(§2.3 三门)=====

class TestO1BattlePrecede:
    def test_row1_active_with_battle_next_releases_free_and_key(self):
        """O1:后随战斗 → 自由件+key 命中件释放(备战帧是穿戴唯一发生点,
        扣到战斗帧就晚了;病灶 = run_20260902_195720 r1-r4)。"""
        comp = _mk_comp(['卡芙卡'], keys=[_KEY])
        assert _ADV not in comp.key_equips
        d = _row1(comp, next_node='boss')
        assert d.battle_precede_release is True
        assert classify_item_hold(d, _assert_real(_ADV), comp, True) is False
        assert classify_item_hold(d, _assert_real(_KEY), comp, True) is False

    def test_o1_scoped_to_row1_window(self):
        """O1 只辖 row1 帧域(P1 ∧ r≤2);next_node 缺失 → 门不中(保守)。"""
        assert battle_precede_release_active(2, 'boss', True, _BATTLE) is True
        assert battle_precede_release_active(3, 'boss', True, _BATTLE) is False
        assert battle_precede_release_active(2, None, True, _BATTLE) is False
        assert battle_precede_release_active(2, 'boss', False, _BATTLE) is False
        assert battle_precede_release_active(2, '奖励', True, _BATTLE) is False

    def test_o1_nonbattle_next_no_release(self):
        comp = _mk_comp(['卡芙卡'], keys=[])
        d = _row1(comp, next_node='奖励', node='补给')
        assert d.battle_precede_release is False
        # 非 key 自由件在 O1 不中时走 O2(有空槽)释放
        assert classify_item_hold(d, _ADV, comp, True) is False


# ===== 2. O2 自由件即穿 + 自由件谓词(§2.2/§6)=====

class TestO2FreeItem:
    def test_free_item_released_with_slot(self):
        """O2:自由件 ∧ 有空槽 → 释放(§2.2 支配性论证,零新参数)。"""
        comp = _mk_comp(['卡芙卡'], keys=[])
        d = _row1(comp)
        assert is_free_item(_ADV, comp) is True
        assert classify_item_hold(d, _ADV, comp, True) is False

    def test_free_item_predicate_exclusions(self):
        """自由件 = 非 key ∧ 非 RESERVED ∧ 非工具 ∧ 非唯一(§6 术语)。"""
        comp = _mk_comp(['卡芙卡'], keys=[_ADV])
        assert is_free_item(_ADV, comp) is False          # key 候选
        assert is_free_item(_BASE, comp) is False         # RESERVED_COMPONENT
        assert is_free_item(_UNIQUE, comp) is False       # 唯一件
        assert is_free_item(_UNIQUE, None) is False       # 唯一判不依赖 comp
        assert is_free_item('冶金炉', comp) is False       # 工具
        assert is_free_item(_ADV, None) is True           # target 真空 → 非自由件不成立

    def test_key_hit_released_even_without_o1_o2(self):
        """v3,L6 锁:row1 帧域 key 命中件释放——依赖求值序第 4 级
        「清单外一律释放」兜出(O1 不中 ∧ O2 不适用 key 件);实现若把
        key 过滤留在 hold 判定内,本锁红。"""
        comp = _mk_comp(['卡芙卡'], keys=[_KEY])
        d = _row1(comp, committed=True)   # O1 不中(无后随战斗)、committed 活跃
        assert classify_item_hold(d, _KEY, comp, False) is False


# ===== 3. hold 保留域五条(§2.3)=====

class TestHoldReserveDomain:
    def test_reserved_component_held(self):
        """② RESERVED_COMPONENT(key 未命中)判据面第一道扣留。"""
        comp = _mk_comp(['卡芙卡'], keys=[])
        d = _row1(comp)
        assert classify_item_hold(d, _BASE, comp, True) is True

    def test_unique_held_even_if_key_hit(self):
        """④ 唯一件扣留;唯一 key 件仍扣 = §2.5 有意行为变化(as-built
        row2 会穿它,本例外使其扣留;实测定谳弱解读后随 §2.5 收窄撤销)。"""
        assert is_unique_equipment(_UNIQUE) is True
        comp = _mk_comp(['卡芙卡'], keys=[_UNIQUE])
        d = _row1(comp, next_node='boss')   # O1 活跃也不放唯一件
        assert classify_item_hold(d, _UNIQUE, comp, True) is True

    def test_non_key_committed_held_in_row1_frame(self):
        """① 非 key ∧ 已定型扣留活跃(两行共现帧承接,§2.3 叠加关系)。"""
        comp = _mk_comp(['卡芙卡'], keys=[])
        d = _row1(comp, committed=True)
        assert classify_item_hold(d, _ADV, comp, False) is True

    def test_node_type_unknown_holds_non_key(self):
        """⑤ node_type 缺失维持 hold(ADR-0461 H3 既有;key 命中件不受)。"""
        comp = _mk_comp(['卡芙卡'], keys=[_KEY])
        d = resolve_wear_release(2, None, True, _BATTLE, comp, 0.2, False,
                                 [], True)
        assert d.opening_hold is True and d.node_type_unknown is True
        # 求值序:O2(自由件 ∧ 有空槽)先于保留域⑤ → 有槽仍释放;
        # 无槽时 O2 不中,⑤ 对非 key 件维持 hold
        assert classify_item_hold(d, _ADV, comp, True) is False
        assert classify_item_hold(d, _ADV, comp, False) is True
        assert classify_item_hold(d, _KEY, comp, True) is False

    def test_tool_defensively_held(self):
        """③ 工具件不进表(§3.2);判据面防御性返回扣留。"""
        comp = _mk_comp(['卡芙卡'], keys=[])
        d = _row1(comp, next_node='boss')
        assert classify_item_hold(d, _TOOL, comp, True) is True


# ===== 4. 求值序(§2.3)=====

class TestEvaluationOrder:
    def test_rust_overrides_reserve_domain(self):
        """第 1 级 O3:生锈豁免压倒保留域全体——含「node None ∧ 生锈」
        共现帧(v1 保留域优先的第二答作废)与唯一件。"""
        comp = _mk_comp(['卡芙卡'], keys=[_UNIQUE])
        d = resolve_wear_release(2, None, True, _BATTLE, comp, 0.2, True,
                                 ['库藏生锈'], True)
        assert d.rust_release is True
        assert classify_item_hold(d, _ADV, comp, True) is False
        assert classify_item_hold(d, _BASE, comp, True) is False
        assert classify_item_hold(d, _UNIQUE, comp, True) is False

    def test_row2_semantics_unchanged(self):
        """row2 域(非 row1 帧)语义 = 18 号稿原样:key 随时穿、penalty
        豁免、其余扣(收窄只改 row1 处置,§2.3)。"""
        comp = _mk_comp(['卡芙卡'], keys=[_KEY])
        d = resolve_wear_release(5, '投资', True, _BATTLE, comp, 0.2, True,
                                 [], True)
        assert d.opening_hold is False and d.committed_hold is True
        assert classify_item_hold(d, _KEY, comp, True) is False
        assert classify_item_hold(d, _ADV, comp, True) is True
        d2 = resolve_wear_release(5, '投资', True, _BATTLE, comp, 0.2, True,
                                  ['软弱无力'], True)
        assert classify_item_hold(d2, _ADV, comp, True) is False
        # 唯一件例外不辖 row2(key 命中唯一件按 row2 原样穿)
        cu = _mk_comp(['卡芙卡'], keys=[_UNIQUE])
        assert classify_item_hold(d, _UNIQUE, cu, True) is False


# ===== 5. 遥测分键(§5)=====

class TestTelemetryDomainKey:
    def test_row1_domain_key(self):
        """row1 域分键:新写入端前缀 opening_hold → strategy_by_design_
        opening(§5:row1 帧数趋零锚与 row2 不回归锚预期相反,无分键不可判读)。"""
        assert classify_zero_wear_stop_reason(
            'opening_hold(row1):三门全不中(保留域扣留)') \
            == ZERO_WEAR_STRATEGY_BY_DESIGN_OPENING

    def test_row2_domain_key_legacy(self):
        """row2 旧键分键:旧写入端前缀 '过渡期hold' → ZERO_WEAR_STRATEGY_
        BY_DESIGN(row1/row2 对同一帧族预期相反须分键,§5;样本字面量 =
        _build_equip_wear_plan 空计划写入端 empty_reason 实值,与
        test_cw_equip_plan_builder 空计划锁同源)。"""
        assert classify_zero_wear_stop_reason(
            '过渡期hold:无 key_equips 命中(全攒着)') \
            == ZERO_WEAR_STRATEGY_BY_DESIGN

    def test_tools_plan_stale_execution_domain(self):
        """工具计划失效 → execution(词表精确行;写入端常量经 import
        比对,词表行/写入端任一侧单改字面量即红,防两侧静默漂移)。"""
        from sr_od.application.currency_war.operations.cw_op.cw_op_tools import (
            CwOpTools,
        )
        assert classify_zero_wear_stop_reason(
            CwOpTools.STATUS_PLAN_STALE) == ZERO_WEAR_EXECUTION

    def test_equip_plan_stale_execution_domain(self):
        """装备计划失效 → execution(词表精确行;写入端常量经 import
        比对,词表行/写入端任一侧单改字面量即红,防两侧静默漂移;
        与工具侧锁同形,写入端 = ADR-0601 §3-C1 具名常量)。"""
        from sr_od.application.currency_war.operations.cw_op.cw_op_equip_all import (
            CwOpEquipAll,
        )
        assert classify_zero_wear_stop_reason(
            CwOpEquipAll.STATUS_PLAN_STALE) == ZERO_WEAR_EXECUTION


# ===== 6. 工具件消费判据(10 号稿 §2.1 收编 + 21 号稿 §3 增量)=====

class TestToolCriteria:
    def test_furnace_burns_dead_stock(self):
        """炉准入(门 B/P14 定理 3):死库存(b ∈ recycle_qualified(K))
        → 放行;无目标 → 拒 fail-closed。"""
        comp = _mk_comp(['卡芙卡'], keys=[_KEY])
        rq = recycle_qualified([_KEY])
        assert _BASE in EQUIPMENTS
        dead = _BASE if _BASE in rq else sorted(rq)[0]
        acts = {a.tool: a for a in evaluate_tool_actions([_TOOL, dead], comp)}
        assert acts[_TOOL].usable is True and acts[_TOOL].reason == ''
        # K 空:recycle_qualified(None) 空集 → 一律不动(fail-closed)
        acts0 = {a.tool: a for a in evaluate_tool_actions([_TOOL, dead], None)}
        assert acts0[_TOOL].usable is False
        assert acts0[_TOOL].reason == TOOL_REJECT_NO_TARGET

    def test_furnace_no_entry_without_dead_stock(self):
        """在需求向量内的件不是死库存 → 烧面无条目(非拒因,无操作面)。"""
        comp = _mk_comp(['卡芙卡'], keys=[_KEY])
        demand = [b for b in component_demand([_KEY]) if b in EQUIPMENTS]
        assert demand, '锁样本失效:火力风暴潮 无可判组件需求'
        acts = evaluate_tool_actions([_TOOL] + demand, comp)
        assert all(a.tool != _TOOL for a in acts)

    def test_furnace_m1_gap_reserved(self):
        """m=1 缺件专留喂炉不值得(P14 定理 2):gaps 正份额档恰为 1 → 拒。"""
        comp = _mk_comp(['卡芙卡'], keys=[_KEY])
        demand = [b for b in component_demand([_KEY]) if b in EQUIPMENTS]
        rq = recycle_qualified([_KEY])
        dead = _BASE if _BASE in rq else sorted(rq)[0]
        owned = [_TOOL, dead] + demand[1:]   # 缺 demand[0] 一档 → m=1
        acts = {a.tool: a for a in evaluate_tool_actions(owned, comp)}
        assert acts[_TOOL].usable is False
        assert acts[_TOOL].reason == TOOL_REJECT_M1_GAP

    def test_wrench_and_token_and_projector_fail_closed(self):
        """扳手闸(去向登记制未落地)/令牌(R(c) 缺档)/投影仪(冷启动
        分支外)→ 拒因分键 fail-closed(§3.4)。"""
        comp = _mk_comp(['卡芙卡'], keys=[_KEY])
        acts = {a.tool: a for a in evaluate_tool_actions(
            ['拆装扳手', '精密拆装扳手', '好运令牌', '员工投影仪',
             '完美投影仪'], comp)}
        assert acts['拆装扳手'].reason == TOOL_REJECT_DEST_UNREADY
        assert acts['精密拆装扳手'].reason == TOOL_REJECT_DEST_UNREADY
        assert acts['好运令牌'].reason == TOOL_REJECT_RC_MISSING
        assert acts['员工投影仪'].reason == TOOL_REJECT_COLD_START_LATER
        assert acts['完美投影仪'].reason == TOOL_REJECT_COLD_START_LATER

    def test_privilege_card_hold_not_leak(self):
        """特权卡(门 B):key 显式含特权件 ∧ 对应进阶成品在手 → 放行;
        无特权目标 → 留(「持有不泄」入锁,§3.4)。"""
        comp = _mk_comp(['卡芙卡'], keys=[_UNIQUE_PRIV])
        acts = {a.tool: a for a in evaluate_tool_actions(
            ['特权赋予卡', _UNIQUE], comp)}
        assert acts['特权赋予卡'].usable is True
        acts2 = {a.tool: a for a in evaluate_tool_actions(
            ['特权赋予卡', _ADV], _mk_comp(['卡芙卡'], keys=[_KEY]))}
        assert acts2['特权赋予卡'].usable is False
        assert acts2['特权赋予卡'].reason == TOOL_REJECT_IN_DEMAND

    def test_g1_admission_gates_emission(self, monkeypatch):
        """G1 发射位准入对照锁(流程:197 常驻锁;ADR-0532 开臂批重推):
        开臂后 usable 件原样透传(不产生准入拒)、判据拒因原样透传(两拒
        分键分开可见);通道回关(fail-closed 形态,monkeypatch 生产常量)
        → usable 件转 g1_not_admitted、判据拒仍保留原拒因——开臂前后
        两态同锁对照,防实现把「拒因覆盖」写进透传支。"""
        from sr_od.application.currency_war.kernel import cw_equip_env
        assert cw_equip_env.TOOL_EXEC_CHANNEL_READY is True, (
            '工具执行通道应已开臂(ADR-0532);若回关须随批重推本锁')
        comp = _mk_comp(['卡芙卡'], keys=[_UNIQUE_PRIV])
        usable = [a for a in evaluate_tool_actions(['特权赋予卡', _UNIQUE],
                                                   comp) if a.usable]
        assert usable, '前置失真:判据面应有放行件才能验准入过滤'
        # 开臂态:usable 原样透传
        passed = {a.tool: a for a in admitted_tool_actions(usable)}
        assert passed['特权赋予卡'].usable is True
        assert passed['特权赋予卡'].reason == ''
        # 回关态(对照):usable 件转准入拒,拒因分键可见
        monkeypatch.setattr(cw_equip_env, 'TOOL_EXEC_CHANNEL_READY', False)
        gated = {a.tool: a for a in admitted_tool_actions(usable)}
        assert gated['特权赋予卡'].usable is False
        assert gated['特权赋予卡'].reason == TOOL_REJECT_G1_NOT_ADMITTED
        # 判据拒因原样透传(开臂/回关两态都不被准入拒覆盖,拒因可观测性)
        rejected = evaluate_tool_actions(['好运令牌'], comp)
        assert admitted_tool_actions(rejected)[0].reason == TOOL_REJECT_RC_MISSING


# ===== 7. sim 注入基建缺省零漂移(§4/§5 最小面)=====

class TestSimInjectDefaults:
    def test_injection_off_by_default(self):
        """缺省登记门:注入池常量缺省 = 空池 ∧ P=0(登记门口径——本锁只
        钉常量缺省值防误改,分布与池指纹逐位一致由快速集 sim 全量隐式
        覆盖,非本锁断言面);开注入属显式实验配置(池指纹变化由实验批
        声明)。"""
        assert TOOL_GRANT_INJECT_POOL == []
        assert TOOL_GRANT_INJECT_P == 0.0
