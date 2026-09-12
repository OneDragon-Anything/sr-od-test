"""cw4_counters 键全集封闭性锁(R5 W4 键收编落码段验收门;T-311)。

正本链:r5-migration-plan.md §2 W4 列「键全集封闭性锁(写点全集对齐,
禁凭概念断格)」→ W4 审计交付报告 v3(.debug/temp/currency_war/
W4-审计-交付报告.md)§2.2 逐键底稿 + §2.3 勾稽 + §2.6 七类清点方法 +
§三.5/§三.16 移交条。

锁什么:策略行为观测计数容器 ``MandateState.cw4_counters`` 的**写点
全集**对齐本登记——
- 字面键层:全仓扫出的字面键 ∈ 字面登记集(257;W4 审计 v3 §2.2 底稿
  256 + N1 增量 1,T-3 核验版三分清单 §3.3);
- 参数化层:模板/常量/变量产键表达式 ∈ 表达式登记(17 闭族 + 9 开放族;
  新产出表达式未登记即红);
- 漏斗层:容器别名上的变量下标写(helper 漏斗体)逐点登记,新漏斗未
  登记即红;
- 豁免面反向锁:7 名声明面/值场面键(审计 §2.4)零写点申报——扫出
  即红(防「声明面键被顺手落成计数键」假红源);
- 反向对齐:登记字面集 ⊆ 扫出全集(登记漂移防:键已删而登记残留);
- 效果域空转申报(W4 验收门 D1 锚):效果域 0 键定谳的机器面——
  效果域容器(cw_effect_inventory)内零本容器写点,且两容器键域零交集。

扫描方法 = 审计 §2.6 七类写模式 + 第 8 类(T-3 核验版三分清单 N4 增补)
的机器化(第 6 类别名赋值→别名下标写、第 7 类 helper 实参常量键→模块
常量表解析、第 8 类跨行隐式串接→解析期归并单节点,自检锁双管:
synthetic 三形态 + 真树 N1 写点正向捕获;纯字面量正则不封闭,r2 复核
逃逸实证 mandate.py deploy_emit_floor_exempt_open)。

为什么登记住测试侧:键集唯一消费方 = 本锁与判读面,src 侧无运行时
读键集的代码(禁造第二源);新增键 = 先过登记(本文件)再落写点,
锁红即登记缺口。

载体面(W4 收编):容器键 stays 策略 state(retirement.md §3 定谳:
策略行为键→策略侧决策行 strategy state 载体);局终级全键聚合可见性 =
局终域行载荷 ``MatchFinal.cw4_counters``(旧流 cw4_counters.jsonl 已随
W4 流删退役,ADR-0650),行为锁在 test_cw_match_final /
test_cw_telemetry_archive。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

# ================= 登记面(W4 审计 v3 §2.2/§2.3 底稿誊录) =================

#: 字面键全集(256)。出处 = 审计 §2.2 逐族表(A-P;按族分行只为可读,
#: 集合无序)。族实例(闭族 80)不在此层——它们归参数化层登记。
_LITERAL_KEYS_BY_FAMILY: dict[str, tuple[str, ...]] = {
    # 族A kernel 观测件(17)
    'A_kernel': (
        'weakplane_exempt_eval', 'weakplane_exempt_eval_hit',
        'weakplane_exempt_eval_fail_thickness',
        'weakplane_exempt_eval_fail_visible', 'p2_supply_gate_cull',
        'neardeath_direction_obs_frame',
        'neardeath_direction_obs_supply_cull', 'p2_handoff_frame',
        'neardeath_direction_obs_handoff_frame', 'promote_candidate_frame',
        'promote_candidate_nonempty', 'p2_handoff_cand_empty',
        'neardeath_direction_obs_handoff_empty',
        'lock_gen_feasibility_obs_lock_open_total',
        'lock_gen_feasibility_obs_lock_open_lowband',
        'lock_gen_feasibility_obs_boss_neardeath_p1',
        'lock_gen_feasibility_obs_boss_neardeath_p2'),
    # 族B 发射仲裁(8;KEY_* 属性常量写点,常量表解析后同字面)
    'B_launch_arb': (
        'launch_arbitrage_precheck_skip', 'launch_arbitrage_inband_closed',
        'launch_arbitrage_frames', 'launch_arbitrage_open_failed',
        'launch_arbitrage_gate_blocked', 'launch_arbitrage_zero_consume',
        'launch_arbitrage_cross_line', 'launch_arbitrage_abandoned_launch'),
    # 族C 发射质量闸(2)
    'C_launch_quality': ('launch_quality_eval_error',
                         'launch_quality_defer_frames'),
    # 族D cw_loop 发射执行面(9)
    'D_exec': (
        'readiness_stale_screen', 'deploy_swap_no_victim',
        'branch_shop_open_hit', 'branch_shop_open_visit_ok',
        'branch_shop_open_visit_fail', 'readiness_overlay_hold',
        'readiness_launch_fail', 'readiness_launch_giveup',
        'launch_frame_idle_gold'),
    # 族E 收益耗尽臂(5)
    'E_exhaustion': (
        'exhaustion_launch_total_giveup', 'exhaustion_battle_launch',
        'exhaustion_launch_stale_giveup', 'exhaustion_launch_fail',
        'exhaustion_launch_giveup'),
    # 族F 部署执行面字面(7)
    'F_deploy': (
        'fuel_filler_stall_held_postbuy', 'deploy_exec_r288_skip_ctx_open',
        'deploy_exec_r288_skip_ctx_closed', 'deployed_from_hub',
        'board_full_front_empty_rowfix', 'rowfix_skip_front_invariant',
        'sell_offtarget_regular'),
    # 族G 执行侧杂项(3)
    'G_misc': ('s1_reset_mischannel', 'buy_click_verify_skipped',
               'merge_material_guard_blocked'),
    # 族H mandate 骨架字面(52)
    'H_mandate': (
        'shop_wanted_deferred', 'wanted_circuit_break', 'wanted_precond_hold',
        'wanted_reopen', 'wanted_leg_deploy', 'wanted_leg_fuel_sell',
        'wanted_abandon', 't1_interest_prep_contract_abstain',
        't1_interest_prep_emit', 'press_narrowed_transition_domain_prep_seen',
        'dominance_bench_wait', 'm2_stall_cache_hit', 'm2_stall_repeat_frame',
        'm2_stall_cache_rederive', 'm2_retry_exhausted',
        'bench_full_buy_abandon', 'arm0_level_unreadable',
        'arm0_cap_unreadable', 'must_spend_zone_latch_extend',
        'reward_node_defer', 'l3_pregate_targetless_neardeath_p1',
        'l3_pregate_targetless_neardeath_p2', 'blood_xp_gate_defer',
        'crisis_level_spend_defer', 'must_spend_zone_defer_overridden',
        'l3_reject_level_cap', 'must_spend_l3_prep_trigger',
        'l3_reject_batch_unaffordable',
        # m1p 拒因 7 裸名(闭集在 mandate.py;键本身=字面)
        'engines_guard', 'star_guard', 'merge_material_guard',
        'post_sell_offline', 'fp_unreadable', 'target_keep', 'buy_membership',
        'm1p_cap_unreadable', 'm1p_membership_unreadable',
        'm1p_input_missing', 'm1p_no_direction', 'm1p_no_bench_target',
        'm1p_defer_levelup', 'm1p_input_seam_pending',
        'redeploy_cost_gate_defer', 'm1p_fired',
        'swap_arm_transition_trigger', 'swap_arm_formed_trigger',
        'm1p_plan_empty', 'm6_bench_full', 'm6_overflow_strand',
        'equip_latch_skip_m7', 'deploy_emit_floor_ctx_open',
        'deploy_emit_floor_exempt_open'),
    # 族I entry 字面(24)
    'I_entry': (
        'emitter_post_truncation_dropped', 'emitter_unknown_action_truncated',
        'emitter_conditional_truncated', 'sphere_defer_streak',
        'sphere_defer_progress_sig', 'sphere_defer_yield',
        'sphere_blocked_bench_full', 'signal_arm_direct', 'switchline_event',
        'ev_conflict_dropped', 'posture_reward_node_defer',
        'posture_crisis_level_defer', 'posture_blood_xp_gate_defer',
        'posture_unfulfilled_level', 'm7_5_evaluated',
        'm7_5_reject_g1_not_admitted', 'm7_5_reject_none',
        'tools_latch_skip', 'advisor_lambda_shadow_armed',
        'advisor_lambda_armed', 'advisor_bloodline_shadow_armed',
        'advisor_bloodline_armed', 'neardeath_unlock',
        'terminal_targetless_idle'),
    # 族J proof 字面(9)
    'J_proof': (
        'evidence_gate_evaluated', 'evidence_gate_unavailable',
        'switchline_skipped', 'theta_unavailable', 'switchline_exit_blocked',
        'switchline_no_target', 'switchline_e_cur_undefined',
        'switchline_no_alt', 'switchline_relock_window'),
    # 族K encounter(10)
    'K_encounter': (
        'encounter_ev_fail_low', 'encounter_ev_reward_gold',
        'encounter_ev_reward_4fee', 'encounter_ev_fail_low_reward_unmodeled',
        'encounter_ev_lambda_direction_note',
        'encounter_ev_fail_low_lambda_undecidable',
        'encounter_ev_fail_low_tie', 'encounter_ev_pick',
        'encounter_ev_undecidable_band_flip',
        'encounter_ev_refresh_suggested'),
    # 族L shop 字面(92)
    'L_shop': (
        'merge_material_stale', 'merge_material_stale_ge2',
        'p90_front_window_buy', 'p90_front_buy_cost3p',
        'p90_front_buy_cross_tier', 'p90_front_buy_over_bound',
        'p90_zerostack_advancing_buy', 'p90_front_table_missing',
        'p90_zerostack_frame_armed', 'p94_no_activatable',
        'p94_exemption_refuse', 'shop_no_target_arm_a_adopted',
        'shop_no_target_arm_a_dead_defer', 'shop_no_target_arm_a_corner_defer',
        'shop_no_target_hold_default', 'shop_hoard_over_capacity',
        'shop_churn_pair_buy', 'shop_drought_reset_on_churn_buy',
        'shop_drought_reset_on_buy', 'hub_option_candidate_seen',
        'hub_option_arbitration_yield', 'hub_option_reject_merge_material',
        'hub_option_reject_seats', 'hub_option_reject_interest',
        'hub_option_reject_unaffordable', 'hub_option_buy_hit',
        'press_narrowed_transition_domain',
        'press_narrowed_transition_domain_hub',
        'dominance_settlement_floor_reject',
        'shop_reopen_discretionary_actions', 'm2_stockpile_star_mismatch',
        'stockpile_unaffordable', 'bench_full', 'm2_stockpile_spot2_buy',
        'm2b_star_mismatch', 'press_buy_deployable_cap_unreadable',
        'press_buy_deployable_no_vacancy',
        'press_buy_deployable_budget_suspend',
        'press_buy_deployable_below_floor',
        'press_buy_deployable_filler_excluded',
        'press_buy_deployable_unaffordable', 'press_buy_deployable_hit',
        'press_buy_deployable_fenced', 'dead_gold_press_buy_hit',
        'dead_gold_press_bench_full_gate', 'm6_budget_gate_suspend',
        'm6_line_member_excluded', 'm6_s_reserve_reject',
        'm6_s_reserve_remeet_frames_sum', 'p91_active_band_frame',
        'p91_m6_same_axis_hit', 'p91_m6_off_axis_hit',
        'p91_refresh_up_switch', 'must_spend_l2_trigger',
        'fuel_not_on_sale', 'below_reserve', 'fuel_filler_stall_buy',
        'fuel_filler_stall_fenced', 't3_no_candidate',
        't3_precheck_bench_full', 't3_precheck_unavailable',
        't3_precheck_no_vacancy', 't3_p1_true_blocked', 't3_available',
        't3_unaffordable', 't3_below_reserve', 't3_buy', 't3_fenced',
        'shop_ev_bench_wait', 'must_spend_ev_deferred', 'shop_ev_all_vetoed',
        'shop_ev_no_candidate', 'ev_buy_round_sold_excluded',
        'must_spend_r1_account_yielded', 'must_spend_r1_yielded_no_target',
        'r1_idle_gold_no_chaseable', 'p92_no_buy_refresh_blocked',
        'must_spend_r1_no_buy_blocked', 'must_spend_r1_budget_fail',
        'shop_hard_node_gate_open', 'shop_visit_idle_gold',
        'reward_node_must_spend_defer', 'level_cap', 'batch_unaffordable',
        'must_spend_guarantee_floor_defer', 'budget_gate_must_spend_defer',
        'budget_gate_must_spend_deadend', 'core_candidate_seen',
        'core_unlocked_buy_hit', 'core_dominance_buy_hit',
        'core_numeric_fail_closed', 'transition_component_buy_hit',
        # 封闭锁捕获的审计后增量(T-313 在飞 shop 批新增写点;shop.py
        # fuel 预检不可得分键,原 §2.2 v3 底稿无此键——锁红后补登记)
        'fuel_filler_stall_precheck_unavailable'),
    # 族M criteria sell/buy(6)
    'M_criteria': (
        't3_protect_deferred', 't1_interest_emit_frames',
        't1_interest_gap_total', 't1_interest_sellback_total',
        't1_pullback_gold_ge_gstar', 'ev_buy_s_reserve_reject'),
    # 族N sell_gate(10)
    'N_sell_gate': (
        'launch_cause_mismatch', 'close_on_sell', 'close_on_deploy',
        'close_on_merge', 'close_on_round', 't3_protect_expired_round',
        'press_window_expired_round', 'close_on_switch', 'seed_acquired',
        'empty_board_sell_guard'),
    # 族P sim 引擎直写(2;W6 收编面,键登记在本层)
    'P_sim': ('sell_buyback_count', 'sell_buyback_net_gold'),
}

LITERAL_KEYS: frozenset[str] = frozenset(
    k for keys in _LITERAL_KEYS_BY_FAMILY.values() for k in keys)

#: 闭域参数化族(17;审计 §2.3 闭族列名 + T-3 核验版 N2 补登)。shape =
#: 产出表达式的静态形状(f 模板头/尾,或变量漏斗声明);instances = 闭域
#: 实例全集(域单一源注明;l2_ 族登记 None,实例经 _family_instances 从
#: kernel 现算派生;上界和 = 86,与 T-3 核验版三分清单勾稽:16 族 80 +
#: l2_ 族 kernel 拒因闭集)。
CLOSED_FAMILIES: tuple[dict[str, Any], ...] = (
    {'name': 'intention_frame_{plane}', 'shape': ('intention_frame_', ''),
     'instances': ('intention_frame_p1', 'intention_frame_p2'),
     'domain': '位面闭集(cw_intention 写点)'},
    {'name': 'intention_locked_frame_{plane}', 'shape': ('intention_locked_frame_', ''),
     'instances': ('intention_locked_frame_p1', 'intention_locked_frame_p2'),
     'domain': '位面闭集(cw_intention 写点)'},
    {'name': 'deploy_exec_held_{reason}', 'shape': ('deploy_exec_held_', ''),
     'instances': ('deploy_exec_held_item_slot', 'deploy_exec_held_scatter_fence',
                   'deploy_exec_held_rest_capacity', 'deploy_exec_held_cap',
                   'deploy_exec_held_name_dup', 'deploy_exec_held_recipe_floor',
                   'deploy_exec_held_post_sell_held',
                   'deploy_exec_held_post_sell_offline'),
     'domain': 'cw_deploy_logic 计划拒因产出(单一源)'},
    {'name': 'deploy_swap_sell_excluded_{why}', 'shape': ('deploy_swap_sell_excluded_', ''),
     'instances': ('deploy_swap_sell_excluded_buy_membership',
                   'deploy_swap_sell_excluded_fresh_buy',
                   'deploy_swap_sell_excluded_membership_unreadable'),
     'domain': 'swap 卖出资格排除三值(cw_op_deploy)'},
    {'name': 'sell_offtarget_arm_{arm}', 'shape': ('sell_offtarget_arm_', ''),
     'instances': ('sell_offtarget_arm_transition', 'sell_offtarget_arm_formed',
                   'sell_offtarget_arm_base'),
     'domain': 'cw4_m1p_arm_pending 计划臂(cw_op_deploy)'},
    {'name': 'shop_latch_skip_{tag}', 'shape': ('shop_latch_skip_', ''),
     'instances': ('shop_latch_skip_dominance_buy', 'shop_latch_skip_m2_buy',
                   'shop_latch_skip_m6_stock'),
     'domain': '闩跳 tag 三值(mandate)'},
    {'name': 's1_reset_by_{route}', 'shape': ('s1_reset_by_', ''),
     'instances': ('s1_reset_by_deploy_launch', 's1_reset_by_bench_flip_untagged',
                   's1_reset_by_bench_flip_m4_fuel_sell',
                   's1_reset_by_bench_flip_equip_transfer_sell'),
     'domain': 'route_tag_of+S1_RESET_ROUTE_TAGS(mandate,ADR-0596 对面'
               '=族G s1_reset_mischannel,收编保持成对)'},
    {'name': 'levelup_budget_gate_拒因(裸名闭集)', 'shape': None,
     'instances': ('all_in_xp_category_filtered', 'guarantee_floor_defer',
                   'levelup_budget_gate_blocked'),
     'domain': 'criteria/levelup 拒因返回域(mandate _gate_why 漏斗;'
               'guarantee_floor_defer 与族L 字面 must_spend_guarantee_floor_defer'
               ' 同源异键,写入经同一漏斗)'},
    {'name': 'deploy_emit_held_{reason}', 'shape': ('deploy_emit_held_', ''),
     'instances': ('deploy_emit_held_item_slot', 'deploy_emit_held_scatter_fence',
                   'deploy_emit_held_rest_capacity', 'deploy_emit_held_cap',
                   'deploy_emit_held_name_dup', 'deploy_emit_held_recipe_floor',
                   'deploy_emit_held_post_sell_held',
                   'deploy_emit_held_post_sell_offline'),
     'domain': '与 deploy_exec_held 共域(mandate 发射位;帧级去重载体'
               ' cw4_deploy_emit_frame,三件套整组禁拆,审计 §三.15)'},
    {'name': 'prep_k_fallback_{band}', 'shape': ('prep_k_fallback_', ''),
     'instances': ('prep_k_fallback_p1_gap', 'prep_k_fallback_p1_lock_band',
                   'prep_k_fallback_p2plus'),
     'domain': 'k_empty_window_fallback token(entry)'},
    {'name': 'm7_5_reject_{action}', 'shape': ('m7_5_reject_', ''),
     'instances': ('m7_5_reject_furnace_single', 'm7_5_reject_wrench_detach',
                   'm7_5_reject_projector_copy', 'm7_5_reject_lucky_token_pick',
                   'm7_5_reject_privilege_upgrade',
                   'm7_5_reject_unknown_tool_action'),
     'domain': 'cw_equip_env ToolAction.action(entry)'},
    {'name': '{arm}_round_sold_excluded', 'shape': ('', '_round_sold_excluded'),
     'instances': None,   # 域=LAUNCH_CAUSE_BY_ARM 臂全集(≤15),实例=调用点子集
     'domain': 'LAUNCH_CAUSE_BY_ARM(sell_gate;臂全集,上界 15)'},
    {'name': 'shop_k_fallback_{band}', 'shape': ('shop_k_fallback_', ''),
     'instances': ('shop_k_fallback_p1_gap', 'shop_k_fallback_p1_lock_band',
                   'shop_k_fallback_p2plus'),
     'domain': 'k_empty_window_fallback token(shop,与族I prep_k_fallback 同域)'},
    {'name': 'shop_ev_{ckey}', 'shape': ('shop_ev_', ''),
     'instances': ('shop_ev_shop_domain', 'shop_ev_u_unavailable'),
     'domain': 'shop EV 闭集;u_unavailable=预注册披露集(④专)'},
    {'name': 'shop_r1_{rkey}', 'shape': ('shop_r1_', ''),
     'instances': ('shop_r1_no_chaseable_member',
                   'shop_r1_account_over_budget',
                   'shop_r1_contract_abstain'),
     'domain': 'r1 拒因闭集;前缀族全量披露(④专)'},
    {'name': 'core 腿 prefix×4 后缀', 'shape': ('', '_core_leg'),
     'instances': None,   # 12 生成实例;域=前缀三值×后缀四值
     'domain': '_core_seat_vacate/_core_gold_bucket prefix 参数'
               '(core_unlocked/core_locked/transition × no_fuel/seat_swap/'
               'unaffordable_strict/unaffordable_fundable;判红闭集单一源'
               '=sim/checks/ledger._CORE_EXIT_KEYS)'},
    {'name': 'fuel_filler_stall_fenced_l2_{why}', 'shape':
        ('fuel_filler_stall_fenced_l2_', ''),
     'instances': None,   # 实例 = kernel 拒因闭集现算派生(_family_instances,
      # 单一源 = cw_deploy_logic;上界随单一源自动扩缩,禁手抄)
     'domain': 'kernel 部署拒因闭集(scatter_fence/rest_capacity/cap/'
               'name_dup/recipe_floor/item_slot;单一源 = cw_deploy_logic '
               'select_deployments 返回拒因注,_kernel_deploy_reject_'
               'reasons 现算)+ 闭集外动态后缀零静默(shop 写点注);触发'
               '源对照分列键(④专,shop 写点预注册裁决协议:先写死后看数'
               '防挪线;与同名 fenced_ 开放族是两个族形,分别登记,N2)'},
)

#: 开放域参数化族(9;域=判据产物/拒因串解析/名单,不设上界,逐族申报)。
OPEN_FAMILY_PREFIXES: tuple[str, ...] = (
    'deploy_swap_sell_rejected_',      # swap 卖出资格族拒因(返回值域)
    'redeploy_transition_victim_',     # 当轮 sell_names[0] 阵容名,按件显影
    'evidence_gate_unavailable_',      # sandwich_unavailable 后缀槽位名
    'evidence_gate_',                  # 证据门拒因主键(reason.split 解析)
    'theta_unavailable_',              # switch_param_missing 槽位集
    'press_buy_deployable_fenced_',    # 部署可放门拒因
    'fuel_filler_stall_fenced_',       # 围栏拒因
    't3_fenced_',                      # t3 围栏拒因
    'criteria_contract_violation:',    # CONTRACTS 登记集(半封闭申报)
)

#: 豁免清单(7;审计 §2.4——声明面/值场面,非计数键,零容器写点)。
#: 反向锁:任一名被扫出写点 = 红(防声明面键被落成计数键)。
EXEMPT_KEYS: frozenset[str] = frozenset({
    'launch_arbitrage_budget_blocked',   # 常量拒因串,零容器写点
    'funding_support_stall_convert',     # SellBench.convert_reason 值域成员
    'funding_hold_liquidated',           # 同上
    'f7_contingency_armed',              # schema.py 判读面键名声明(4 键族)
    'depsilon_advisor_violation',
    'f7_exempt_emission',
    'f7_uncovered_interest_sell',
})

#: 效果域另一容器(排除扫描;W4 定谳:效果域 0 键,D1 门空转申报面)。
_EFFECT_INVENTORY_MODULE = 'kernel/cw_effect_inventory.py'

#: helper 漏斗实参白名单:这些裸名是载体/上下文传参,不是键。
_FUNNEL_CONTEXT_ARGS: frozenset[str] = frozenset({
    'session', 'sess', '_sess', 'match', 'op', 'counters', 'ist', 'st',
    'self', 'ctx', 'state', 'key', 'k', 'tag', 'name',
})

_SRC_ROOT: Path = (Path(__file__).resolve().parents[5] / 'src' / 'sr_od'
                   / 'application' / 'currency_war')

_CONTAINER_TOKEN = 'cw4_counters'

# helper 漏斗函数名(各模块闭包计数 helper;写模式类 1-4/7 的载体的
# 调用面)。新 helper = 漏斗层登记,不在册的漏斗写点由别名变量下标写
# 分支拦截。
_HELPER_NAMES: tuple[str, ...] = (
    '_count', '_bump', '_bump_obs', '_bump_cw4_counter',
    '_launch_arb_counter', '_r', '_gate_why',
)

# ===== 扫描引擎(AST;审计 §2.6 七类写模式的机器化)=====
# 说明:正则逐行法在文档串/续行/跨行调用上不封闭(实测文档串被并成
# 伪逻辑行、跨行调用漏检),改走 ast 解析——写点判定按语法节点:
# Subscript 赋值(类 5/6)/ helper 调用实参(类 1-4/7)/ 常量表解析
# (第 7 类,r2 逃逸补丁)/ 漏斗变量来源面(键经局部变量中转的形态)。


def _const_table_of(tree: ast.Module) -> dict[str, str]:
    """常量表(第 7 类;UPPER 名 → 字符串字面值,含类属性)。"""
    table: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        target = (node.targets[0] if isinstance(node, ast.Assign)
                  else node.target)
        if not isinstance(target, ast.Name):
            continue
        if not re.fullmatch(r'[A-Z_][A-Z0-9_]*', target.id):
            continue
        val = node.value
        if isinstance(val, ast.Constant) and isinstance(val.value, str):
            table.setdefault(target.id, val.value)
    return table


def _container_aliases(tree: ast.Module) -> set[str]:
    """第 6 类:容器别名(ASSIGN 右值引用容器的直引用;dict() 包裹 =
    快照副本只读排除)。另恒含 ``counters``(类 3 形参穿线载体名:
    criteria/buy·sell·contracts、proof 等以形参自调用点接收容器)。"""
    alias_pairs: list[tuple[str, ast.expr]] = []
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if name == _CONTAINER_TOKEN:
            continue
        alias_pairs.append((name, node.value))
    aliases.add('counters')

    def _refs_container(node: ast.expr) -> bool:
        """右值子树是否引用容器(IfExp/元组等复合右值递归;顶层 dict()
        包裹 = 快照副本只读排除;.get('cw4_counters') 读形天然不命中
        ——getattr 判据只认裸 getattr 调用)。"""
        if isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Name)
                    and node.func.id == 'dict'):
                return False   # 快照副本,写之不触容器
            if (isinstance(node.func, ast.Name)
                    and node.func.id == 'getattr'
                    and any(isinstance(a, ast.Constant)
                            and a.value == _CONTAINER_TOKEN
                            for a in node.args)):
                return True
        if isinstance(node, ast.Attribute):
            return node.attr == _CONTAINER_TOKEN
        return any(_refs_container(c) for c
                   in ast.iter_child_nodes(node))

    def _refs_alias(node: ast.expr, known: set[str]) -> bool:
        """右值子树是否引用已知别名(传递别名 chase:
        ``_ex_c = _ex_counters if isinstance(...) else None`` 形态)。"""
        if isinstance(node, ast.Name):
            return node.id in known
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'dict':
            return False
        return any(_refs_alias(c, known) for c in ast.iter_child_nodes(node))

    changed = True
    while changed:
        changed = False
        for name, value in alias_pairs:
            if name in aliases:
                continue
            if _refs_container(value) or _refs_alias(value, aliases):
                aliases.add(name)
                changed = True
    return aliases


def _joined_template(node: ast.JoinedStr) -> str:
    """f-string 节点 → 模板串(常量段原样,插值段记 ``{}``)。"""
    parts: list[str] = []
    for v in node.values:
        parts.append(v.value if isinstance(v, ast.Constant) else '{}')
    return ''.join(parts)


def _keys_in_expr(node: ast.expr, consts: dict[str, str],
                  ) -> list[tuple[str, str]]:
    """表达式子树 → 键 token 流(lit/tmpl/const/var;常量拼接
    ``PREFIX + 'suffix'`` 直接求值为完整字面——flow _k_* 三键形态)。"""
    out: list[tuple[str, str]] = []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [('lit', node.value)]
    if isinstance(node, ast.JoinedStr):
        return [('tmpl', _joined_template(node))]
    if isinstance(node, ast.Name):
        if re.fullmatch(r'[A-Z_][A-Z0-9_]*', node.id):
            return [('const', node.id)]
        return [('var', node.id)]
    if isinstance(node, ast.Attribute):
        # 模块限定常量(cw_launch_arbitrage.KEY_X 形态):常量名在 attr 位
        if re.fullmatch(r'[A-Z_][A-Z0-9_]*', node.attr):
            return [('const', node.attr)]
        return []
    if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add)):
        left = _keys_in_expr(node.left, consts)
        right = _keys_in_expr(node.right, consts)
        lit_l = [v for k, v in left if k == 'lit'] or [
            consts.get(v, '') for k, v in left if k == 'const']
        lit_r = [v for k, v in right if k == 'lit'] or [
            consts.get(v, '') for k, v in right if k == 'const']
        if lit_l and lit_r:
            merged = lit_l[0] + lit_r[0]
            return [('lit', merged)]
        return left + right
    for child in ast.iter_child_nodes(node):
        out.extend(_keys_in_expr(child, consts))
    return out


def scan_write_points() -> dict[str, Any]:
    """七类写模式扫描 → 结构化发现(锁断言与人工对账共用)。

    返回 ``{'literals': {key: [file:line...]}, 'templates':
    {(file, 模板): [line...]}, 'const_unresolved': [...], 'funnels':
    {(file, alias, var): [line...]}, 'helper_var_args': {(file, helper,
    var): [line...]}}``。
    """
    literals: dict[str, list[str]] = {}
    templates: dict[tuple[str, str], list[int]] = {}
    const_unresolved: list[str] = []
    funnels: dict[tuple[str, str, str], list[int]] = {}
    helper_var_args: dict[tuple[str, str, str], list[int]] = {}
    file_trees: dict[str, ast.Module] = {}
    global_consts: dict[str, str] = {}
    for py in sorted(_SRC_ROOT.rglob('*.py')):
        rel = py.relative_to(_SRC_ROOT).as_posix()
        if rel == _EFFECT_INVENTORY_MODULE:
            continue   # 效果域另一容器(W4 定谳:零交集;D1 空转申报面)
        tree = ast.parse(py.read_text(encoding='utf-8'), filename=rel)
        file_trees[rel] = tree
        for name, val in _const_table_of(tree).items():
            global_consts.setdefault(name, val)

    def _const_hit(name: str, where: str, rel: str, line: int) -> None:
        """常量实参/下标解析(第 7 类):值=完整键 → 字面;值=参数化
        前缀(尾随 ``_``)→ 模板表达式归族(deploy_emit_held_ 形态)。"""
        val = global_consts.get(name)
        if val is None:
            const_unresolved.append(f'{where} {name}')
        elif val.endswith('_'):
            templates.setdefault((rel, val + '{}'), []).append(line)
        else:
            literals.setdefault(val, []).append(f'{where}({name})')

    # 逐函数作用域索引(漏斗变量的绑定来源只在**同一函数内**找——
    # 泛文件搜同名普通变量名(key/k/tag)会把无关字符串绑定误当键源)
    func_index: dict[str, list[ast.FunctionDef]] = {}
    for rel, tree in file_trees.items():
        func_index[rel] = [node for node in ast.walk(tree)
                           if isinstance(node, (ast.FunctionDef,
                                                ast.AsyncFunctionDef))]

    def _enclosing_func(rel: str, line: int) -> ast.AST | None:
        """行号 → 最内层包含函数(绑定搜索作用域)。"""
        best = None
        best_span: tuple[int, int] | None = None
        for fn in func_index.get(rel, []):
            start = getattr(fn, 'lineno', 0)
            end = getattr(fn, 'end_lineno', start)
            if start <= line <= end:
                span = (start, end)
                if best_span is None or (span[1] - span[0]) \
                        < (best_span[1] - best_span[0]):
                    best, best_span = fn, span
        return best

    for rel, tree in file_trees.items():
        aliases = _container_aliases(tree) | {_CONTAINER_TOKEN}
        for node in ast.walk(tree):
            line = getattr(node, 'lineno', 0)
            # —— 类 5/6:别名/容器下标写(含 AugAssign)——
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = (node.targets if isinstance(node, ast.Assign)
                           else [node.target])
                for tgt in targets:
                    if not isinstance(tgt, ast.Subscript):
                        continue
                    val_node = tgt.value
                    alias: str | None = None
                    if isinstance(val_node, ast.Name) \
                            and val_node.id in aliases:
                        alias = val_node.id
                    elif (isinstance(val_node, ast.Attribute)
                          and val_node.attr == _CONTAINER_TOKEN):
                        alias = _CONTAINER_TOKEN
                    if alias is None:
                        continue
                    where = f'{rel}:{line}'
                    slice_node = tgt.slice
                    if isinstance(slice_node, ast.JoinedStr):
                        templates.setdefault(
                            (rel, _joined_template(slice_node)),
                            []).append(line)
                    elif isinstance(slice_node, ast.Constant) \
                            and isinstance(slice_node.value, str):
                        literals.setdefault(slice_node.value,
                                            []).append(where)
                    elif isinstance(slice_node, ast.Name):
                        if re.fullmatch(r'[A-Z_][A-Z0-9_]*', slice_node.id):
                            _const_hit(slice_node.id, where, rel, line)
                        else:
                            funnels.setdefault(
                                (rel, alias, slice_node.id), []).append(line)
                    else:
                        for kind, val in _keys_in_expr(slice_node,
                                                       global_consts):
                            if kind == 'lit':
                                literals.setdefault(val, []).append(where)
                            elif kind == 'tmpl':
                                templates.setdefault(
                                    (rel, val), []).append(line)
                            elif kind == 'const':
                                _const_hit(val, where, rel, line)
                        if isinstance(slice_node, ast.BinOp):
                            var_names = [v for k, v in
                                         _keys_in_expr(slice_node,
                                                       global_consts)
                                         if k == 'var']
                            for vn in var_names:
                                funnels.setdefault(
                                    (rel, alias, vn), []).append(line)
                continue
            # —— 类 1-4/7:helper 调用实参(键槽位 = 首个非调用实参;
            #     载体名/载体 getter 调用跳过,其后实参是计数/金额位,
            #     子树字符串不是键——``_bump(counters,'x',
            #     expired.count('press'))`` 的 'press' 是值域词非键)——
            if isinstance(node, ast.Call) \
                    and ((isinstance(node.func, ast.Name)
                          and node.func.id in _HELPER_NAMES)
                         or (isinstance(node.func, ast.Attribute)
                             and node.func.attr in _HELPER_NAMES)):
                _helper_name = (node.func.id if isinstance(node.func, ast.Name)
                                else node.func.attr)
                _kws = [kw.value for kw in node.keywords]
                key_arg: ast.expr | None = None
                for arg in (*node.args, *_kws):
                    if key_arg is None:
                        if isinstance(arg, ast.Call):
                            continue   # 载体 getter/金额计算调用位
                        if (isinstance(arg, ast.Name)
                                and arg.id in _FUNNEL_CONTEXT_ARGS):
                            continue   # 载体名传参位
                        key_arg = arg
                if key_arg is None:
                    continue
                if isinstance(key_arg, ast.Name):
                    val = key_arg.id
                    if re.fullmatch(r'[A-Z_][A-Z0-9_]*', val):
                        _const_hit(val, f'{rel}:{line}', rel, line)
                    elif val not in _FUNNEL_CONTEXT_ARGS:
                        # 裸名实参 = 漏斗调用面(键经该变量中转)
                        helper_var_args.setdefault(
                            (rel, _helper_name, val), []).append(line)
                else:
                    for kind, val in _keys_in_expr(key_arg, global_consts):
                        if kind == 'lit':
                            literals.setdefault(val, []).append(f'{rel}:{line}')
                        elif kind == 'tmpl':
                            templates.setdefault(
                                (rel, val), []).append(line)
                        elif kind == 'const':
                            _const_hit(val, f'{rel}:{line}', rel, line)
        # —— 第 2 遍:漏斗变量来源面(var = 'lit' / for var in {..} /
        #     var = PREFIX + 'suffix',**限同函数作用域**——键经局部变量
        #     中转:mandate m1p 拒因集、cw_op_deploy _sell_key、flow
        #     _k_*、cw_loop _k)——
        merged_sites: dict[tuple[str, str, str], list[int]] = dict(funnels)
        merged_sites.update(helper_var_args)
        for (frel, _falias, fvar), lns in sorted(merged_sites.items()):
            if frel != rel:
                continue
            scope = _enclosing_func(frel, lns[0])
            if scope is None:
                continue
            var = fvar
            for node in ast.walk(scope):
                if isinstance(node, ast.Assign) \
                        and len(node.targets) == 1 \
                        and isinstance(node.targets[0], ast.Name) \
                        and node.targets[0].id == var:
                    exprs = [node.value]
                elif isinstance(node, ast.For) \
                        and isinstance(node.target, ast.Name) \
                        and node.target.id == var:
                    exprs = [node.iter]
                else:
                    continue
                for expr in exprs:
                    for kind, val in _keys_in_expr(expr, global_consts):
                        if kind == 'lit':
                            literals.setdefault(val, []).append(
                                f'{rel}:{node.lineno}(via {var})')
                        elif kind == 'tmpl':
                            templates.setdefault(
                                (rel, val), []).append(node.lineno)
                        elif kind == 'const':
                            _const_hit(val, f'{rel}:{node.lineno}(via {var})',
                                       rel, node.lineno)
    return {'literals': literals, 'templates': templates,
            'const_unresolved': const_unresolved, 'funnels': funnels,
            'helper_var_args': helper_var_args}


# ================= l2_ 族闭集机器锚定(kernel 单一源现算) =================

#: l2_ 族登记名与键前缀(_family_instances 派生与 census 勾稽共用)。
_L2_FAMILY_NAME: str = 'fuel_filler_stall_fenced_l2_{why}'
_L2_KEY_PREFIX: str = 'fuel_filler_stall_fenced_l2_'
_KERNEL_DEPLOY_LOGIC: str = 'kernel/cw_deploy_logic.py'
_KERNEL_REJECT_FN: str = 'select_deployments'

#: 现算结果缓存(多条断言共享一次 AST 解析;懒加载避免收集期付 kernel 源)。
_KERNEL_REASONS: frozenset[str] | None = None


def _kernel_deploy_reject_reasons() -> frozenset[str]:
    """kernel 部署拒因闭集现算(纪律 9:期望值从单一源推导,禁手抄常数)。

    单一源 = ``cw_deploy_logic.select_deployments`` 的 held 拒因赋值点
    (``reasons[<下标>] = '<字面>'``;N2 规格单一源,17 号稿 §7.1)。
    kernel 新增第 7 拒因 → 本集现算扩容 → census 上界勾稽红(登记门:
    核对新增拒因入 cw4 计数域后同步勾稽锚)。只扫该函数:同模块
    ``select_swap_plan`` 也有 ``reasons`` 字典,属 deploy_exec_held 域
    (post_sell_* 两键,族形不同,分别登记)。推导退化(空集)= kernel
    重构了赋值形态、现算器失明——fail-closed 炸错指引同步,禁静默放行。
    """
    global _KERNEL_REASONS
    if _KERNEL_REASONS is None:
        src = _SRC_ROOT / _KERNEL_DEPLOY_LOGIC
        tree = ast.parse(src.read_text(encoding='utf-8'), filename=str(src))
        reasons: set[str] = set()
        for fn in ast.walk(tree):
            if not (isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and fn.name == _KERNEL_REJECT_FN):
                continue
            for node in ast.walk(fn):
                if not isinstance(node, ast.Assign):
                    continue
                for tgt in node.targets:
                    if (isinstance(tgt, ast.Subscript)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == 'reasons'
                            and isinstance(node.value, ast.Constant)
                            and isinstance(node.value.value, str)):
                        reasons.add(str(node.value.value))
        assert reasons, (
            f'kernel 拒因闭集现算退化:{_KERNEL_DEPLOY_LOGIC}::'
            f'{_KERNEL_REJECT_FN} 未扫出任何 reasons[*] = <字面> 赋值点'
            '(拒因赋值形态变更,须同步本现算器,禁手抄回退)')
        _KERNEL_REASONS = frozenset(reasons)
    return _KERNEL_REASONS


def _family_instances(fam: dict[str, Any]) -> tuple[str, ...]:
    """族实例全集解析(登记 ``instances``;l2_ 族 = kernel 拒因闭集现算
    派生全键,上界随单一源自动扩缩)。族校验(census 勾稽/字面键归属)
    一律经本函数,禁绕行直读 ``instances``。"""
    if fam['name'] == _L2_FAMILY_NAME:
        return tuple(sorted(_L2_KEY_PREFIX + r
                            for r in _kernel_deploy_reject_reasons()))
    return fam['instances'] or ()


def _family_instance_owner(key: str) -> str | None:
    """字面键 → 所属闭族名(键=已登记闭族实例时;用于直写形态的
    族实例,如 shop_latch_skip_m2_buy 直写 mandate:1134)。l2_ 族实例
    为现算派生,kernel 闭集外字面后缀不属族 → 封闭性主门红。"""
    for fam in CLOSED_FAMILIES:
        if key in _family_instances(fam):
            return str(fam['name'])
    return None


def _template_family(rel: str, tmpl: str) -> str | None:
    """模板 → 族名(闭族形状/开放前缀;未登记 = None → 锁红)。"""
    for fam in CLOSED_FAMILIES:
        shape = fam['shape']
        if shape is None:
            continue
        head, tail = shape
        if tail == '_core_leg':
            # core 腿:尾 ∈ 四后缀(head 为变量占位 {} 的尾形状)
            if any(tmpl.endswith('_' + s) for s in (
                    'no_fuel', 'seat_swap', 'unaffordable_strict',
                    'unaffordable_fundable')):
                return str(fam['name'])
            continue
        if tmpl.startswith(head) and tmpl.endswith(tail):
            return str(fam['name'])
    for pref in OPEN_FAMILY_PREFIXES:
        if tmpl.startswith(pref):
            return f'开放族 {pref}*'
    return None


#: 反向对齐豁免:只经漏斗变量产出、源域在别处的登记键(levelup 拒因
#: 三值由 criteria/levelup 返回域产出,扫描器不追跨模块返回值)。
_INDIRECT_LITERAL_KEYS: frozenset[str] = frozenset({
    'all_in_xp_category_filtered', 'guarantee_floor_defer',
    'levelup_budget_gate_blocked',
})

# 扫描结果模块级缓存(多条断言共享一次扫描;锁定单跑 ~2s)
_SCAN: dict[str, Any] | None = None


def _scan() -> dict[str, Any]:
    global _SCAN
    if _SCAN is None:
        _SCAN = scan_write_points()
    return _SCAN


# ================= 锁断言 =================


def test_literal_keys_within_registry():
    """字面键层:全仓扫出的字面写键 ∈ 登记字面集 ∪ 已登记闭族实例。

    红向 = 新增未登记键写点(封闭性主门);族实例直写(如
    shop_latch_skip_m2_buy)落在闭族登记内,合法。"""
    r = _scan()
    violations = {}
    for key, sites in r['literals'].items():
        if key in LITERAL_KEYS or _family_instance_owner(key) is not None:
            continue
        violations[key] = sites[:3]
    assert not violations, (
        '未登记键写点(先过登记面再落写点,封闭性锁拦截):\n'
        + '\n'.join(f'  {k}: {v}' for k, v in sorted(violations.items())))


def test_parameterized_expressions_within_registered_families():
    """参数化层:模板/常量前缀产出表达式 ∈ 已登记族(17 闭族+9 开放族)。

    新产出表达式(新 f 模板/新前缀常量)未登记即红——审计 §三.16
    「禁纯字面量正则断格」的参数化面承接。"""
    r = _scan()
    violations = {}
    for (rel, tmpl), lines in r['templates'].items():
        fam = _template_family(rel, tmpl)
        if fam is None:
            violations[f'{rel} f\'{tmpl}\''] = lines[:3]
    assert not violations, (
        '未登记参数化产出表达式(新 f 模板/前缀常量须先过族登记):\n'
        + '\n'.join(f'  {k}: {v}' for k, v in sorted(violations.items())))


def test_constant_resolution_closed():
    """第 7 类补丁自检:helper 实参/下标上的 UPPER 名必须能从常量表
    解析出值(未解析 = 出现了表外常量键形态 → 锁红待人工归族)。"""
    r = _scan()
    assert not r['const_unresolved'], (
        '未解析常量键形态(常量表外 UPPER 实参/下标,禁放行):\n'
        + '\n'.join(f'  {x}' for x in sorted(set(r['const_unresolved']))))


def test_reverse_alignment_registry_not_stale():
    """反向对齐:登记字面集 ⊆ 扫出全集(键已删而登记残留 = 登记漂移
    防护)。豁免 = 只经漏斗变量产出、源域在别处的登记键(_INDIRECT_
    LITERAL_KEYS 三值)。"""
    r = _scan()
    found = set(r['literals'])
    stale = sorted(LITERAL_KEYS - found - _INDIRECT_LITERAL_KEYS)
    assert not stale, (
        '登记残留(登记有而全仓无写点,键删除后须同步销登记):\n'
        + '\n'.join(f'  {k}' for k in stale))


def test_exempt_keys_have_zero_write_points():
    """豁免面反向锁:7 名声明面/值场面键(审计 §2.4)零容器写点——
    扫出即红(防「声明面键被顺手落成计数键」的假红源)。"""
    r = _scan()
    hit = {k: v for k, v in r['literals'].items() if k in EXEMPT_KEYS}
    hit_tmpl = {t for t in r['templates'] if t[1] in EXEMPT_KEYS}
    assert not hit and not hit_tmpl, (
        f'豁免清单键出现写点(应保持声明面/值场面零计数): {hit} {hit_tmpl}')


def test_funnel_funnels_bound_to_declared_context():
    """漏斗层存在性:helper 漏斗(变量键槽)与别名变量下标写已被扫描
    捕捉(锁面结构自检——两层为空 = 扫描器退化失明,封闭性承诺失效)。"""
    r = _scan()
    assert r['funnels'], '漏斗捕捉为空(扫描器失明自查失败)'
    assert r['helper_var_args'], 'helper 裸名漏斗捕捉为空(扫描器失明)'


def test_census_accounts_consistent():
    """登记账目自洽(与审计 §2.3 勾稽同构,T-3 核验版口径):字面集非空、
    闭族 17 个、闭族实例加和(上界口径)= 86(臂族域 = LAUNCH_CAUSE_BY_
    ARM 全集 15,core 腿 = 3 前缀 ×4 后缀,l2_ 族 = kernel 拒因闭集现算)、
    豁免面 7 名。l2_ 上界从 cw_deploy_logic 现算(纪律 9,禁手抄):kernel
    新增/删减拒因 → 本锁红 = 登记门,核对闭集变更入 cw4 域后同步勾稽锚。"""
    assert len(LITERAL_KEYS) == 257, (
        f'字面登记 {len(LITERAL_KEYS)} ≠ 257(审计 256 + 增量 1)')
    assert len(EXEMPT_KEYS) == 7
    assert len(CLOSED_FAMILIES) == 17, (
        f'闭族登记 {len(CLOSED_FAMILIES)} ≠ 17(16 族 + N2 l2_ 族)')
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        sell_gate as _sell_gate,
    )
    assert len(_sell_gate.LAUNCH_CAUSE_BY_ARM) == 15
    inst_sum = 0
    for fam in CLOSED_FAMILIES:
        if fam['name'].startswith('{arm}'):
            inst_sum += len(_sell_gate.LAUNCH_CAUSE_BY_ARM)
        elif fam['name'].startswith('core'):
            inst_sum += 12
        else:
            inst_sum += len(_family_instances(fam))
    assert inst_sum == 86, (
        f'闭族实例加和(上界) {inst_sum} ≠ 86(16 族 80 + l2_ 族 kernel '
        f'拒因闭集现算 {len(_kernel_deploy_reject_reasons())})——l2_ 项'
        '漂移 = kernel 拒因闭集增删(cw_deploy_logic.select_deployments),'
        '核对新增拒因入 cw4 计数域后同步本勾稽锚')


def test_effect_domain_zero_keys_d1_idle_declaration():
    """效果域空转申报(W4 验收门 D1 锚的机器面):效果域 0 键定谳 = ①
    效果域容器模块零本容器写点;②效果域键域(CounterKey 登记面)与本
    登记零交集。两件成立则「效果域写点经 inventory 方法域」门按审计
    定谳空转(无键可落,候裁 8 不依赖)。"""
    inv = _SRC_ROOT / 'kernel/cw_effect_inventory.py'
    assert inv.exists(), '效果域容器模块在位(D1 锚载体)'
    tree = ast.parse(inv.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        assert not (isinstance(node, ast.Attribute)
                    and node.attr == _CONTAINER_TOKEN), (
            '效果域模块出现本容器属性访问(效果域 0 键定谳被打破)')
        assert not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == 'getattr'
                    and any(isinstance(a, ast.Constant)
                            and a.value == _CONTAINER_TOKEN
                            for a in node.args)), (
            '效果域模块出现本容器 getattr(效果域 0 键定谳被打破)')
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            key = node.value
            assert key not in LITERAL_KEYS, (
                f'效果域模块出现登记键字面 {key}(两容器键域须零交集)')
            assert key not in EXEMPT_KEYS, (
                f'效果域模块出现豁免面键字面 {key}')


def test_class8_cross_line_concat_forms_resolved():
    """第 8 类自检(T-3 核验版三分清单 N4 移交落码):跨行隐式串接的
    三种 AST 形态都解析为完整键——①隐式邻接字符串(解析期归并成单
    Constant,helper 实参/下标两写位同源);②BinOp 加串(lit+lit 合并
    求值);③相邻 f-string(JoinedStr 解析期归并,常量段拼接)。任一
    形态漏捕 = 扫描器键域失明,封闭性承诺失效。"""
    # ① 隐式邻接:解析期已是单 Constant(N1 实证写点形态)
    tree = ast.parse("_count('k8_a_'\n       'b')\n")
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call))
    assert isinstance(call.args[0], ast.Constant), '邻接串须解析期归并'
    assert call.args[0].value == 'k8_a_b'
    assert _keys_in_expr(call.args[0], {}) == [('lit', 'k8_a_b')]
    # ② BinOp 加串(lit+lit → 合并字面;flow _k_* 形态同源)
    tree2 = ast.parse("cw4_counters['k8_c_' + 'd'] = 1\n")
    sub = next(n for n in ast.walk(tree2) if isinstance(n, ast.Subscript))
    assert _keys_in_expr(sub.slice, {}) == [('lit', 'k8_c_d')]
    # ③ 相邻 f-string 归并(N2 实证写点形态):常量段拼接+插值占位
    tree3 = ast.parse("cw4_counters[f'k8_e_'\n          f'f_{w}'] = 1\n")
    sub3 = next(n for n in ast.walk(tree3) if isinstance(n, ast.Subscript))
    assert isinstance(sub3.slice, ast.JoinedStr), '相邻 f-string 须解析期归并'
    assert _joined_template(sub3.slice) == 'k8_e_f_{}'


def test_class8_live_write_site_discovered():
    """第 8 类正向锁:真树 N1 写点(fuel 预检不可得分键,跨行隐式串接
    形态,逐行 grep 不可见)被扫描器以完整字面捕获于 shop.py 写点——
    登记面与扫描面双覆盖(红 = 扫描器第 8 类解析退化,非登记缺口)。"""
    sites = _scan()['literals'].get(
        'fuel_filler_stall_precheck_unavailable', [])
    assert sites and any('shop.py' in s for s in sites), (
        f'跨行隐式串接写点未被扫描器捕获(第 8 类失明): {sites}')


def test_n2_l2_family_template_discovered_and_registered():
    """N2 族形正向锁:触发源对照分列键(l2_ 前缀,相邻 f-string 归并
    形态)以模板表达式被扫描器捕获,且归入本登记闭族;与同名 fenced_
    开放族两族形并存互不吞并(N2:开放族域不含 l2_ 实例,分别登记)。"""
    r = _scan()
    l2_hits = [(rel, tmpl) for rel, tmpl in r['templates']
               if rel.endswith('shop.py')
               and tmpl == 'fuel_filler_stall_fenced_l2_{}']
    assert l2_hits, (
        f'l2_ 族模板未被扫描器捕获: {sorted(r["templates"])}')
    for rel, tmpl in l2_hits:
        owner = _template_family(rel, tmpl)
        assert owner is not None and 'l2_' in owner, (
            f'l2_ 族模板须归入闭族登记,现归: {owner}')
    open_hits = [(rel, tmpl) for rel, tmpl in r['templates']
                 if rel.endswith('shop.py')
                 and tmpl == 'fuel_filler_stall_fenced_{}']
    assert open_hits, 'fenced_ 开放族模板未被捕获'
    for rel, tmpl in open_hits:
        owner = _template_family(rel, tmpl)
        assert owner is not None and '开放族' in owner, (
            f'fenced_ 开放族归属漂移: {owner}')
