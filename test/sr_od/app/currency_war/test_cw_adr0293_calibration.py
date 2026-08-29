"""ADR-0293 标定批回归锁:字段面锁 + 模块常量锁 + 刷新双门 + 弱件换金偏置。

- 字段面锁(锁法见 ADR-0293 §标定 + 0293 流程注释):registry 以
  「字段名集合 + 各字段类型注解 + 默认值语义」期望表锁死——新增
  字段=红(强迫显式登记语义与默认值)、删字段=红、改默认值=红、
  改类型=红;注释/措辞/字段顺序/空白=绿(表按名比较,不感知)。
  标定存活参(target_hold_base/off_target_sell_bias/piggy_refresh_ev)
  的逐值锁由本表承载(独立快照锁曾与之重复,已并入,防双源漂移);
  值域演进的正确性由字段面锁 + 各批自己的行为锁管辖,本锁只辖
  「字段面结构」。模块级 hp 对账标定常量(HP_LOSS_CAP_* 等,与
  registry 字段同属标定面)一并入表。
- 行为锁:刷新轮界门(无目标语境恒负分)/弱件换金偏置(0 分卖
  翻正)。默认策略注入标定后 registry 的断言单一源在
  test_cw_strategy.py::test_instantiate_decision_v2_default_registry
  (同一断言曾双文件重复,择一保留)。
决策见 docs/develop/currency_war/decisions/0293-decision-v2-calibration.md。
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.kernel import cw_registry as registry_mod
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import (
    score_candidate,
)

#: 字段面期望表:字段名 → (类型注解串, 归一化默认值)。
#: 归一化口径见 _norm(集合→排序 list;tuple 保序;dict 键转 str 排序)。
#: 生成方式:对 DEFAULT_REGISTRY 现值按本表同法归一后逐字段登记;
#: 任何字段面变化(增/删/改默认/改类型)必须随批显式更新本表条目。
#: 字段语义(为何是这个默认)单一源 = registry 字段注释与各批 ADR,
#: 本表不复制注释,只钉结构与值。
_EXPECTED_FIELDS: dict[str, tuple[str, object]] = {
    # ===== 层1:候选生成 =====
    'buy_tag_priority': ('tuple[str, ...]', [
        'line_carry', 'line_opportunistic', 'bridge_core',
        'engine_seed', 'plugin', 'pair', 'copy', 'copy_press',
        'bond_fallback', 'carry_gate']),
    'sell_tag_priority': ('tuple[str, ...]', [
        'off_target', 'for_gold', 'free_bench']),
    'deploy_top_k': ('int', 3),
    'deploy_sort_key': ('str', 'cw_deploy_logic_fence'),
    'sell_top_k': ('int', 2),
    'copies_cap': ('int', 3),
    'copy_swap_target_exempt': ('bool', True),
    'merge_completion_exempt': ('bool', True),
    'bond_fallback_max_cost': ('int', 2),
    'bond_fallback_min_round': ('int', 3),
    'carry_gate_max_round': ('int', 7),
    # ===== 层4 补偿趟(W52/ADR-0326)=====
    'remedy_buy_tags': ('frozenset[str]', frozenset({
        'line_carry', 'line_opportunistic', 'bridge_core',
        'engine_seed', 'plugin', 'carry_gate'})),
    'remedy_min_score': ('float', 0.5),
    'remedy_alarm_refresh': ('bool', True),
    # ===== S5 统一卖件弱序(W52/ADR-0327)=====
    'remeet_window_rounds': ('dict[int, int]', {
        '1': 11, '2': 25, '3': 40, '4': 60, '5': 120}),
    'through_rate': ('dict[int, float]', {
        '1': 0.2, '2': 0.2, '3': 0.15, '4': 0.12, '5': 0.1}),
    'sell_key_weight_scale': ('float', 1.0),
    # ===== 层2:硬过滤链 =====
    'filter_chain_order': ('tuple[str, ...]', ['emergency', 'mode']),
    'emergency_tags': ('frozenset[str]', frozenset({
        'line_carry', 'line_opportunistic', 'bridge_core',
        'engine_seed', 'plugin', 'carry_gate', 'off_target',
        'free_bench', 'deploy', 'for_gold', 'levelup'})),
    'economy_tags': ('frozenset[str]', frozenset({
        'line_carry', 'line_opportunistic', 'bridge_core',
        'engine_seed', 'plugin', 'pair', 'copy', 'copy_press',
        'carry_gate', 'bond_fallback', 'off_target', 'for_gold',
        'free_bench', 'levelup', 'refresh', 'deploy'})),
    'war_tags': ('frozenset[str]', frozenset({
        'line_carry', 'line_opportunistic', 'bridge_core',
        'engine_seed', 'plugin', 'pair', 'copy', 'copy_press',
        'bond_fallback', 'carry_gate', 'off_target', 'for_gold',
        'free_bench', 'levelup', 'deploy', 'refresh'})),
    'emergency_hp': ('int', 25),
    'crisis_hoard_gold': ('int', 40),
    # ===== 成型停手纪律(ADR-0343)=====
    'formed_stop_enabled': ('bool', True),
    'formed_stop_min_round': ('int', 7),
    # 血预算停手·停升级线(设计件 12 §6;ADR-0448):语义注释落点=
    # registry 字段注释;默认 True=P21 数学定谳恒接线,False=A/B 对照臂
    'blood_budget_stop_enabled': ('bool', True),
    'blood_budget_stop_d': ('int', 1),
    'p1_levelup_stop_rung': ('int', 2),
    # 血预算停手·第二波(设计件 12 §6;ADR-0451):60=期望预算线
    # (W524 充分不必要);两开关默认 True=W516 方向性排除证据恒接线,
    # False=A/B 对照臂(语义注释落点=registry 字段注释)
    'p1_exit_blood_target': ('int', 60),
    'p1_exit_downgrade_enabled': ('bool', True),
    'blood_budget_refresh_stop_enabled': ('bool', True),
    # 概率校准刷新预算(ADR-0475):ω=塌缩带归零线(标定字段,0.1 占位;
    # 比值由 cw_shop_odds 表导出,与分配器 Π_refresh 同源)/q=有望帧帽
    # 真分位(−ln(1−q) 闭式乘数,网格 {0.8,0.9});语义注释落点=
    # registry 字段注释
    'omega_collapse_ratio': ('float', 0.1),
    'refresh_find_quantile': ('float', 0.8),
    # 血预算停手·终止分支(设计 W659 v2;ADR-0469):True=数学定谳
    # 恒接线(金零值引理+EV 对比式),False=A/B 对照臂;0.03=EV 反解
    # 最悲观角 0.0283 的诚实带下沿档(重标定挂账,语义注释落点=
    # registry 字段注释)
    'terminal_release_enabled': ('bool', True),
    'terminal_survival_eps': ('float', 0.03),
    # ===== 相位观测与授权(W119/ADR-0347)=====
    'phase_fallback_min_round': ('int', 5),
    'phase_fallback_min_engines': ('int', 2),
    'form_floor': ('int', 20),
    'boss_window_fallback_round': ('int', 9),
    'piggy_refresh_round_cap': ('int', 1),
    # ===== 层3:板面查表评分 =====
    'rung_value': ('dict[int, float]', {'0': 0.0, '1': 1.4, '2': 3.0}),
    'h3_win_rate': ('dict[int, float]', {
        '0': 0.139, '1': 0.416, '2': 0.778}),
    'rounds_left_est': ('float', 5.0),
    'battles_left_est': ('float', 5.0),
    'expected_battle_loss': ('float', 10.0),
    'hp_to_gold': ('float', 0.5),
    'interest_cap': ('int', 5),
    'interest_rounds': ('float', 5.0),
    'rung_frac_per_recipe_tier': ('float', 0.3),
    'piggy_refresh_ev': ('float', 2.5),
    'interest_recovery_rounds': ('float', 3.0),
    # ===== P2 段 V_D(W154/ADR-0361)=====
    'vd_p2_enabled': ('bool', True),
    'vd_p1_loss_intercept': ('float', 11.32),
    'vd_p1_loss_slope_rung': ('float', -0.37),
    'streak_floor_loss_damage': ('dict[str, tuple[float, float]]', {
        'encounter': [24.32, -4.53], 'boss': [26.71, 0.0]}),
    'streak_floor_win_rate': ('dict[str, dict[int, float]]', {
        'battle': {'0': 0.009, '1': 0.356, '2': 0.315},
        'encounter': {'0': 0.038, '1': 0.026, '2': 0.264},
        'boss': {'0': 0.077, '1': 0.027, '2': 0.187}}),
    'vd_p2_loss': ('float', 20.05),
    'vd_p2_recovery_rounds': ('float', 2.31),
    'vd_p2_liquidity_rho': ('float', 0.0),
    'vd_p1_pair_enabled': ('bool', True),
    'depth_unit_value': ('float', 2.0),
    'level_unit_value': ('float', 1.0),
    'target_hold_value': ('float', 3.0),
    'target_hold_base': ('int', 9),
    'bench_form_weight': ('float', 0.35),
    'target_hold_cap_frac': ('float', 0.8),
    'engine_frac_unit': ('float', 1.0),
    'core_star_unit': ('float', 3.0),
    'merge_progress_unit': ('float', 3.0),
    # (filler_star_unit/pair_copy_direction_exempt/goldrich_buy_bias/
    # goldrich_min_gold/goldrich_buy_tags/early_pace_* 五字段已随
    # ADR-0402/0305/0408 定谳清理删除,字段面锁同步收敛。)
    'off_target_sell_bias': ('float', 0.5),
    'crisis_buy_bias': ('float', 1.0),
    'crisis_buy_tags': ('frozenset[str]', frozenset({
        'line_carry', 'line_opportunistic', 'bridge_core',
        'engine_seed', 'plugin', 'carry_gate'})),
    'forming_bias': ('float', 5.0),
    'forming_bias_val_max': ('float', 0.5),
    'engine_affinity_enabled': ('bool', True),
    # ===== W150/ADR-0359 买侧通道锁定目标约束 =====
    'buy_lock_constraint_enabled': ('bool', True),
    'off_lock_buy_tags': ('frozenset[str]', frozenset({
        'line_opportunistic', 'bond_fallback'})),
    'off_lock_buy_penalty': ('float', 3.0),
    'off_lock_final_fence_enabled': ('bool', True),
    # ===== W155/ADR-0361 evolve 换血保护 =====
    'evolve_lock_constraint_enabled': ('bool', True),
    'evolve_off_lock_penalty': ('float', 3.0),
    # ===== W160/ADR-0363 引擎丢失修法 =====
    'evolve_engine_guard_enabled': ('bool', True),
    'evolve_final_freeze_enabled': ('bool', True),
    # ===== W174/ADR-0371 引擎补完守卫 =====
    'evolve_engine_completion_enabled': ('bool', True),
    'engine_complete_distinct_owned': ('bool', True),
    'engine_complete_grade_down': ('bool', True),
    # ===== W179/ADR-0372 P1 早期新件买入门 =====
    'p1_early_gate_enabled': ('bool', True),
    'p1_early_min_missing': ('int', 6),
    'p1_early_round_cap': ('int', 1),
    # ===== W184/ADR-0373 卖侧唯一体系引擎守卫 =====
    'sell_sole_engine_guard_enabled': ('bool', True),
    # ===== W192/ADR-0375 希儿系守卫辖域 =====
    'guard_seele_scope_enabled': ('bool', True),
    # ===== W197/ADR-0380 卖侧下界守卫执行点 =====
    'sell_floor_exec_guard_enabled': ('bool', True),
    # ===== W194/ADR-0378 多击组 + P2 核心首件门 =====
    'levelup_multihit_enabled': ('bool', True),
    'p2_core_firstpiece_enabled': ('bool', True),
    # ===== W300 press 通道 =====
    'press_channel_enabled': ('bool', True),
    'press_band_cum_threshold': ('float', 0.5),
    'press_channel_max_level': ('int', 6),
    'press_copy_round_cap': ('int', 1),
    'press_exempt_round_cap': ('int', 2),
    # ===== P1 末窗承接门(ADR-0400/0411/0418)=====
    'handoff_gate_min_round': ('int', 6),
    'handoff_gate_tier_target': ('int', 1),
    'handoff_ev_gap_bonus': ('float', 5.0),
    'handoff_boss_e_damage': ('dict[int, float]', {'0': 34.0}),
    'handoff_boss_e_damage_default': ('float', 34.0),
    'handoff_boss_reward_bonus': ('int', 2),
    # ===== W252/ADR-0409 M-A 定向刷新 =====
    'directed_refresh_per_round': ('int', 2),
    'directed_refresh_game_cap': ('int', 6),
    # ===== (early_pace_* 五字段已随 ADR-0408 定谳清理删除)=====
    # ===== W332b 泄息通道与换线判据 =====
    # (release_enabled / release_spend_gate_enabled 已随 ADR-0426 增补 D
    # 第 4 态清理删除,字段面锁同步收敛。)
    'k_alert': ('float', 3.0),
    'k_linear': ('float', 1.0),
    'k_hp_calibration_grid': ('tuple[float, ...]', [
        1.0, 2.0, 3.0, 5.0]),
    'blood_margin_low_hp': ('int', 40),
    'boss_tax_p75': ('float', 34.0),
    'boss_tax_anchor_group': ('tuple[float, float, float]', [
        32.0, 34.0, 36.0]),
    'boss_tax_p75_by_plane': ('dict[int, float]', {
        '1': 34.0, '2': 34.0}),
    'delta_hp_normal': ('float', 1.96),
    'delta_hp_boss': ('float', 4.3),
    'line_switch_enabled': ('bool', True),
    'line_switch_theta': ('float', 1.0),
    'line_switch_debias_delta': ('float', 0.15),
    'line_switch_min_dwell': ('int', 2),
    # ===== P2 生存批(C3/C4)=====
    'p2_node_loss_table': ('dict[str, float]', {
        'normal': 10.16, 'encounter': 12.00, 'boss': 15.50,
        'reward': 0.0}),
    'p2_cond_loss_table': ('dict[str, float]', {
        'normal': 12.77, 'encounter': 13.33, 'boss': 15.50,
        'reward': 0.0}),
    'p2_loss_calib_version': ('int', 1),
    'directed_refresh_high_cost_floor': ('int', 4),
    'line_switch_survival_gate_enabled': ('bool', False),
    'rounds_two_state_enabled': ('bool', False),
    'line_switch_survival_margin': ('float', 1.0),
    'p_win_p2_by_rung': ('dict[int, float]', {
        '0': 0.016, '1': 0.413, '2': 0.657}),
    'encounter_heal_est': ('float', 0.0),
    'line_switch_boss_ci_halfwidth': ('float', 1.53),
    # ===== R3 撤销出口①意图证据 =====
    'revoke_miss_tolerance_eps': ('float', 0.05),
    'revoke_evidence_min_thickness': ('float', 5.0),
    # ===== C1 溢余必花定向优先级 =====
    'c1_directed_spend_enabled': ('bool', False),
    # ===== 形态达标三方向 =====
    'recipe_fence_enabled': ('bool', False),
    'form_break_sell_blocked_enabled': ('bool', False),
    'below_floor_spend_gate_enabled': ('bool', False),
    # (framework_startup_v2_enabled 已随框架启动基建退役删除,ADR-0468)
    # ===== DirectorV2 备战循环(W606 落件;W620 批1升正删开关,仅存影子诊断)=====
    'director_v2_shadow_compare': ('bool', False),
    # ===== 层4:预算仲裁 =====
    'constraints': ('tuple[str, ...]', [
        'gold_floor', 'interest_rule', 'bench_capacity', 'copies_cap',
        'same_round_mutex', 'blood_budget_stop', 'boss_levelup_ban',
        'deploy_cap']),
    # interest_floor 字段已删(W628 D3 双源清偿):息线 = interest_cap×10
    # 派生方法,唯一取值口 registry.interest_floor();override 通道仅纪律
    # 视图 ALL IN 注入用(非标定旋钮,入面锁默认 None)。
    'interest_floor_override': ('int | None', None),
    'war_floor': ('int', 30),
    'rebirth_floor': ('int', 20),
    'boss_floor': ('int', 10),
    'boss_round_node_types': ('frozenset[str]', frozenset({'boss'})),
    'level_max': ('int', 10),
    'bench_capacity': ('int', 9),
    # ===== 完备性审计表 =====
    'audit_matrix': (
        'dict[tuple[str, str], tuple[str, ...] | tuple[str, str]]', {
            "('gold', 'boss')": ['gold_floor', 'interest_rule'],
            "('gold', 'emergency')": ['gold_floor'],
            "('gold', 'mode')": ['gold_floor', 'interest_rule'],
            "('bench', 'boss')": ['bench_capacity'],
            "('bench', 'emergency')": ['bench_capacity'],
            "('bench', 'mode')": ['bench_capacity'],
            "('slot', 'boss')": ['blood_budget_stop', 'boss_levelup_ban'],
            "('slot', 'emergency')": ['blood_budget_stop', 'bench_capacity'],
            "('slot', 'mode')": ['blood_budget_stop', 'deploy_cap'],
            "('round_mutex', 'boss')": ['same_round_mutex'],
            "('round_mutex', 'emergency')": ['same_round_mutex'],
            "('round_mutex', 'mode')": ['same_round_mutex'],
        }),
    'audit_resource_dims': ('tuple[str, ...]', [
        'gold', 'bench', 'slot', 'round_mutex']),
    'audit_round_state_dims': ('tuple[str, ...]', [
        'boss', 'emergency', 'mode']),
    # ===== W607 词缀消费面(ADR-0461;语义注释落点=registry W607 字段块)=====
    # (line_env_gate_enabled 已删:W628 H1 行为无条件化,判据恒在)
    'line_env_lock_min_round': ('int', 1),
    'rust_wear_release_enabled': ('bool', True),
    'opening_hold_battle_gate_enabled': ('bool', True),
    'opening_hold_battle_nodes': ('frozenset[str]', frozenset(
        {'战斗', 'boss', '遭遇', '精英'})),
    # W607 第二波 H2① 数据层(无行为分支,账面单一源;ADR-0461 增补节)
    'rust_hoard_damage_share': ('float', 0.03),
    'rust_hoard_penalty_cap': ('int', 10),
}

#: registry 模块级标定常量期望表(名字 → 归一化值;与字段同属标定面,
#: 语义见各常量注释,消费方 cw_reconcile)。
_EXPECTED_MODULE_CONSTANTS: dict[str, object] = {
    'HP_LOSS_CAP_P100_BY_NODE': {
        '普通战斗': 23, '遭遇': 42, 'boss': 39},
    'HP_ZERO_LOSS_NODE_TYPES': frozenset({'奖励', '补给'}),
    'HP_SUSPECT_CONFIRM_FRAMES': 2,
    'HP_SUSPECT_WINDOW_NODES': 2,
}


def _card(name: str, faction: str = '仙舟罗浮', cost: int = 1) -> object:
    return SimpleNamespace(name=name, faction=faction, cost=cost,
                           x=0, star=1)


def _bench(name: str, faction: str = '仙舟罗浮',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 4, 'gold': 30, 'level': 5,
            'board': {'仙舟罗浮': 1}, 'bench': [], 'shop': [], 'hp': 100}
    base.update(kw)
    return GameState(**base)


def _norm(v):
    """可比较归一(集合→排序 list;tuple 保序;dict 键转 str 后按键排序)。

    期望表条目按同一口径书写,两侧经 _norm 后 == 比较。"""
    if isinstance(v, dict):
        return {str(k): _norm(x)
                for k, x in sorted(v.items(), key=lambda t: str(t[0]))}
    if isinstance(v, (set, frozenset)):
        return sorted(map(str, v))
    if isinstance(v, tuple):
        return [_norm(x) for x in v]
    return v


def test_calibration_registry_field_surface() -> None:
    """registry 字段面锁:字段集合 + 类型注解 + 默认值语义逐字段比对。

    红锁信息直接点名差异字段(新增/缺失/类型/默认值),不再报不可
    读的 hash 差。若是有意改字段面——随批更新 _EXPECTED_FIELDS 对应
    条目(新字段登记语义注释落点=registry 字段注释);若是有意改
    默认值——重标定(ADR-0293 流程)并更新条目值。标定存活参
    (target_hold_base=9/off_target_sell_bias=0.5/piggy_refresh_ev=2.5)
    由本表逐值辖死(原独立快照锁已并入本锁)。"""
    actual = {f.name: f for f in dataclasses.fields(DecisionV2Registry)}
    expected_names = set(_EXPECTED_FIELDS)
    added = actual.keys() - expected_names
    removed = expected_names - actual.keys()
    assert not added and not removed, (
        f'registry 字段面漂移:新增 {sorted(added)} / 删除 {sorted(removed)};'
        '新字段须随批在 _EXPECTED_FIELDS 登记语义,删字段随批移除条目')
    for name, (want_type, want_default) in _EXPECTED_FIELDS.items():
        f = actual[name]
        assert f.type == want_type, (
            f'registry 字段类型漂移:{name}: {f.type} != {want_type}')
        got = _norm(getattr(DEFAULT_REGISTRY, name))
        assert got == _norm(want_default), (
            f'registry 默认值漂移:{name}: {got!r} != {want_default!r};'
            '有意改参须重标定并更新期望表')


def test_calibration_module_constants() -> None:
    """registry 模块级标定常量锁(hp 对账下行守卫标定面,消费方
    cw_reconcile.reconcile_hp)。语义同字段面锁:增删/改值=红。"""
    for name, want in _EXPECTED_MODULE_CONSTANTS.items():
        assert hasattr(registry_mod, name), (
            f'registry 模块常量缺失:{name}(cw_reconcile 消费面)')
        got = _norm(getattr(registry_mod, name))
        assert got == _norm(want), (
            f'registry 模块常量漂移:{name}: {got!r} != {want!r}')


def test_refresh_no_target_context_negative() -> None:
    """W126/ADR-0349 V_D 批口径:无目标语境(未锁线)的刷新恒负分
    ——refresh 附庸闸(轮界/金门/常量 EV)已删,D 让位语义由
    vd_refresh_score 承载([31] 刷新金只用于找目标件)。"""
    for rn, gold in ((5, 50), (7, 50), (2, 15), (8, 60)):
        st = _state(round_num=rn, gold=gold,
                    shop=[_card('占位件', faction='公司', cost=1)])
        sess = StrategySession()
        cand = [c for c in generate_candidates(st, sess,
                                               DEFAULT_REGISTRY)
                if c.tag == 'refresh'][0]
        val, _ = score_candidate(cand, st, sess, DEFAULT_REGISTRY)
        assert val < 0, f'r{rn} g{gold} 无目标语境刷新必须负分(实际 {val})'


def test_off_target_sell_bias_flips_zero_score() -> None:
    """弱件换金:持有域溢出件卖分 0+偏置>0(无偏置被非正分拒)。"""
    # 溢出构造:level 低、bench 远超 cap(depth 饱和)→ 卖不改形态
    st = _state(
        level=3, gold=10,
        shop=[_card('占位件', faction='公司', cost=1)],
        bench=[_bench('囤件甲', slot=1), _bench('囤件乙', slot=2),
               _bench('囤件丙', slot=3), _bench('囤件丁', slot=4)],
    )
    sess = StrategySession()
    sells = [c for c in generate_candidates(st, sess, DEFAULT_REGISTRY)
             if c.tag == 'off_target']
    assert sells, '溢出 bench 应生成 off_target 卖候选'
    val, _bd = score_candidate(sells[0], st, sess, DEFAULT_REGISTRY)
    # 溢出件(持有>cap):基础卖分 0,偏置翻正——「弱件换金」语义
    assert val == DEFAULT_REGISTRY.off_target_sell_bias, (
        f'溢出件卖分应为偏置值(实际 {val})')


# 默认策略注入标定后 registry 的断言(实例缺省持 DEFAULT_REGISTRY + 标定值)
# 单一源在 test_cw_strategy.py::test_instantiate_decision_v2_default_registry;
# 此处原独立锁与之逐字重复,已删留指针(重复构成并/删理由,README 纪律 8)。
