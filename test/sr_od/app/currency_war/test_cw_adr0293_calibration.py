"""ADR-0293 标定批回归锁:标定参数快照 + 刷新双门 + 弱件换金偏置。

- 快照锁:标定五参(refresh_ev/refresh_max_round/refresh_min_gold/
  target_hold_base/off_target_sell_bias)逐值锁死 + registry 全字段
  hash 锁(任何漂移——包括未列字段——即红,防静默改参)。
- 行为锁:刷新轮界门(r>max 恒负分)/金保底门(金<min 不刷)/
  溢出件卖出偏置(0 分卖翻正)。
决策见 docs/develop/currency_war/decisions/0293-decision-v2-calibration.md。
"""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    score_candidate,
)
from sr_od.application.currency_war.decision_v2.strategy import (
    DecisionV2Strategy,
)

#: ADR-0293 标定批次 registry 全字段快照 hash
#: (n=100 终验 mean 28.26/团灭 6/配对差 -2.89 的参数组)
#: ADR-0295 形态域结构批更新:新增 bench_form_weight/target_hold_cap_frac
#: 两字段(标定五参值不变);新批次 hash 见下
#: ADR-0297 并存仲裁批更新:新增 refresh_starve_discount/refresh_starve_gold
#: /refresh_game_cap/levelup_reserve_gold 四字段 + constraints 增
#: refresh_budget(标定五参与 0295 两参值不变)
#: ADR-0299 买入面差异解剖批更新:buy_tag_priority 增 engine_seed
#: + 四覆盖态放行标签集增 engine_seed(数值字段全部不变)
#: ADR-0300 copy/pair 通道迁移批更新:buy_tag_priority 增 pair/copy
#: + economy/war/catchup 放行标签集增 pair/copy(数值字段全部不变;
#: emergency 集保持窄——应急态保命优先,v2 应急集设计本就窄于常态)
#: ADR-0301 成型攻坚批更新:新增 engine_frac_unit(=1.0,双窗网格
#: 标定)+ form_refresh_ev(=0.0,双窗否决默认关闭)/form_refresh_
#: max_round/form_refresh_min_gold/form_refresh_engines_target 四
#: 注册字段(既有数值字段全部不变)
#: ADR-0302/0303 危机修复+合流批更新:emergency_tags 并入
#: for_gold/levelup(应急集内容修正)+ 新增 crisis_hoard_gold/
#: crisis_buy_bias/crisis_buy_tags 三字段(值=ADR-0302 暂驻 filters
#: 的原值,纯上移;其余数值字段不变)
#: ADR-0304 回退+战力转化批更新:新增 copy_swap_target_exempt
#: (=False,豁免回退开关;其余字段不变)
#: ADR-0305 金充裕不买诊断批更新:新增 goldrich_buy_bias/goldrich_
#: min_gold/goldrich_buy_tags 三字段(默认 0=通道关,只顶 0 分
#: 差分;既有数值字段不变)。全量清偿时发现 0305 漏更本锁
#: (欠账随 ADR-0306 批的全量补跑暴露),按锁语义补记
#: ADR-0309 载体批(W35)更新:四覆盖态标签集/危机买偏置辖集并入
#: 'plugin'(层1 插件通道,定义节 class5)——纯标签集变更,数值
#: 字段零变化(标定五参快照锁另行核)。
#: ADR-0326 回连机制批(W52)更新:新增 remedy_buy_tags(旧
#: LIQUIDITY_BUY_TAGS 语义迁入,含 'carry_gate')/remedy_min_score/
#: remedy_alarm_refresh 三字段(补偿趟注册表化;既有数值字段不变)。
#: ADR-0327 S5 批(W52)更新:新增 remeet_window_rounds/through_rate/
#: sell_key_weight_scale 三字段(统一卖件弱序表;既有数值字段不变)。
#: ADR-0332 成型评分活性批更新:新增 forming_bias(=5.0,成型补充偏置
#: 顶正)/forming_bias_val_max(=0.5,顶分上沿)两字段(既有数值字段
#: 全部不变;双窗 A/B 验证见 ADR-0332)。
#: ADR-0333 体系集中度批(W72)更新:新增 engine_affinity_enabled(=True,
#: 候选层 engine_seed 配方亲和过滤开关;关闭=回 W70 行为,A/B 通道;
#: 既有数值字段全部不变,验证见 ADR-0333)。
#: W96/ADR-0340 断买修复批更新:新增 merge_progress_unit(=3.0,3合1
#: 中间进度项——目标件第 2 份 1★ 期权显影;未网格标定,sim A/B
#: 方向见 deep_read/W96_报告.md)——有意改参,锁同步更新
_EXPECTED_HASH = '8a7c4ee67326db5cb4d4007abb9ace9'
_EXPECTED_HASH += 'e17440afac0996ec4fa7f7f9e397c22af'
# W88/ADR-0339:新增 core_star_unit=3.0(核心升星价值项,配对 A/B 标定
# n=150:+18/0)——有意改参,锁同步更新
# W107/ADR-0343 成型停手批更新:新增 formed_stop_enabled(=True)/
# formed_stop_min_round(=7)/formed_stop_min_level(=5)三字段
# ([13] 停手线;既有数值字段全部不变)——有意改参,锁同步更新
_EXPECTED_HASH = ('ee7a9c38ca6b9fd2799f64bbc4545ffe'
                  '761e97528a78d075ec279d4adda9a9e3')
# W114/ADR-0346 相位影子观测批更新:新增 phase_form_score_gate(=0.5,
# 兜底局 form_ok 降级门,sim 校准域;影子期零消费)——有意改参,锁同步
# 更新(既有数值字段全部不变)
_EXPECTED_HASH = '117316f74fdbd93413f1937622a1710c6865fd35d0769b399335a74dbd045fe5'
# W119/ADR-0347 切授权批更新:新增 form_floor(=20,Q1 四档 sim 对照
# 待校准)/phase_fallback_min_round(=5,W118 兜底门校准判据)/
# boss_window_fallback_round(=9,boss 窗节点图统一口径的缺读兜底)
# 三字段;删除 formed_stop_min_level(Q2 裁决:等级不作为独立门槛)
# 与 levelup_interest_engine_gate([12] 门收编 EV 总账,E6 latch 退场)
# ——有意改参,锁同步更新(其余数值字段不变)
_EXPECTED_HASH = '837f521098a44ac0f8e81b8febf6208dd320d212f4d5975e29053ca979946679'
# W122 F-01(W120 P8 上限接线)更新:新增 piggy_refresh_round_cap(=1,
# 扑满节点单节点刷新豁免上限——s≤0.277R 采前保守 2 金)——有意改参,
# 锁同步更新(其余数值字段不变)
_EXPECTED_HASH = '3ad13e863c742a386bbfcffcf3d75f72ea01f685fc9cd2ef27e0d1fa8312a519'
# W126/ADR-0349 步③切调度更新:删 refresh 附庸闸十一参(refresh_ev/
# refresh_max_round/refresh_min_gold/refresh_starve_discount/
# refresh_starve_gold/refresh_game_cap/levelup_reserve_gold/
# form_refresh_ev/form_refresh_max_round/form_refresh_min_gold/
# form_refresh_engines_target)+追赶到四参(catchup_tags/
# catchup_forbidden_tags/catchup_min_level/pop_baseline);新增
# piggy_refresh_ev(=2.5,扑满凑伤害 D 专属);war_tags 增 refresh
# (war 滤 refresh 废除);constraints 删 refresh_budget;审计表
# 'catchup' 列改 'mode'——有意改参(D 是一等通道/追赶态退场),
# 锁同步更新(target_hold_base/off_target_sell_bias 两存活标定值不变)
_EXPECTED_HASH = 'fa157543a85e59250753dab71ced739a9cd354564647023d1fdd63f5aa87ca09'
# W132/ADR-0353 兜底门结构判据批更新:删 phase_form_score_gate(=0.5),
# 新增 phase_fallback_min_engines(=2,有效体系数下限——四体系两两组合=
# 过渡成型;run15 实机散板过旧门两证);并存批同期新增
# interest_recovery_rounds(=3.0,W131/ADR-0352 买侧回档折中)——有意
# 改参,锁同步更新(其余数值字段不变)
_EXPECTED_HASH = '4d691245755180dc3ae21c8dfe075d19f941ddc8ef4603b05ac2def6dcc6e5d4'
# W131/ADR-0352 买侧 EV 标定批更新:新增 interest_recovery_rounds(=3.0,
# 买侧 C_interest 回档折中视界:P6 下界 1-3 金与平面 R 上界≈20-23 的
# 折中;只辖 arbiter.interest_rule 的 BuyCard 分支,刷新/升级口径不动)
# ——有意改参(买侧 V/C 量级错档标定),锁同步更新(其余数值不变)
_EXPECTED_HASH = ('4d691245755180dc3ae21c8dfe075d19'
                  'f941ddc8ef4603b05ac2def6dcc6e5d4')
# W150/ADR-0359 买侧通道锁定目标约束批更新:新增 buy_lock_constraint_
# enabled(=True)/off_lock_buy_tags/off_lock_buy_penalty(=3.0)/
# off_lock_final_fence_enabled(=True)四字段(锁定帧非目标件评分降级
# +末轮围栏;既有数值字段全部不变)——有意改参,锁同步更新
_EXPECTED_HASH = ('a3c0989b51b467323e429e1592219198'
                  'dfab74d94ec006cdde9bfff26cc2238c')
# W154/ADR-0361 P2 段 V_D 修法批更新:新增 vd_p2_enabled(=True)/
# vd_p2_loss(=16.0,P2 掉血期望保守中值)/vd_p2_recovery_rounds(=2.31,
# P2 穿 50 段回档上界)/vd_p2_liquidity_rho(=0.0,溢余金影子价起步)
# 四字段(P11/P12 口径;P1 分支零变化)——有意改参,锁同步更新
_EXPECTED_HASH = ('c42f073df31bbecc215857816a7da9a'
                  'ec4f5cd2f6c0684eaa121441aec68481c')
# 并行批(W160/ADR-0363,在飞工作树)新增 evolve_engine_guard_enabled
# (=True)/evolve_final_freeze_enabled(=True)两字段——hash 锁按当前
# registry 现值重算(本批 W157 未触碰 registry;锁值追平并行批字段,
# 该批合流时如再改默认值须随批重锁)
_EXPECTED_HASH = ('3729d4bacdfa8edb41195c1ea386c5d1'
                  '045e4f980db545bd52d827d6952df78d')
# W170/ADR-0369 P1 体系对缺件找牌通道批更新:新增 vd_p1_pair_enabled
# (=True,P1 pair 缺件找牌通道总开关;core 通道/P2 分支不受辖)——
# 有意改参(通道默认开),锁同步更新(其余数值字段不变)
_EXPECTED_HASH = ('b6f56fb72b40183c42b15e81105b28b2'
                  '17f6d162097c61d90ba4fcba52c2a1ca')
# W174/ADR-0371 引擎补完守卫批更新:新增 evolve_engine_completion_enabled
# (=True,own-gap 修法 A/B 通道总开关;关=回 W170 后行为)——有意改参,
# 锁同步更新(其余数值字段不变)
_EXPECTED_HASH = ('b835dcbf8e0c8b9be5fc2e904b219cbe'
                  'c380a2dd2531c9b5dec7c2e435ce849d')
# W179/ADR-0372 P1 早期新件买入门批更新:新增 p1_early_gate_enabled
# (=True)/p1_early_min_missing(=6)/p1_early_round_cap(=1)三字段
# (双条件窗:缺件密度 × 息档口径;关=回 W174 后行为)——有意改参,
# 锁同步更新(其余数值字段不变)
_EXPECTED_HASH = ('dbda54fec1bb165f4a18b2e0cd4dc8ea'
                  'e5710d92a03a36c8285c0b1c697a0b77')
# W184/ADR-0373 卖侧唯一体系引擎守卫批更新:新增 sell_sole_engine_
# guard_enabled(=True,S2 恶化谱系 A/B 通道总开关;关=回 W179 后
# 行为)——有意改参,锁同步更新(其余数值字段不变)
_EXPECTED_HASH = ('fcfa610b0496e5f58975b2a82be1b30d'
                  'd3e11d6bd40dbca9721220f930697c35')
# W192/ADR-0375 希儿系守卫辖域补全批更新:新增 guard_seele_scope_
# enabled(=True,希儿系(单卡判据 tier=1)并入卖侧唯一体系引擎守卫
# 与演进保护集辖域;关=回 W188 后行为)——有意改参,锁同步更新
# (其余数值字段不变)
_EXPECTED_HASH = ('1db429c1050915da537c35e6e9cc047b'
                  '9c75144aa70eed372ea25e3e4921d07f')
# W194/ADR-0378 P2 谱系三件批更新:新增 levelup_multihit_enabled
# (=True,[33] 稳态 LevelUp 多击组——辖域 P2+;关=回 W193 后行为)
# 与 p2_core_firstpiece_enabled(=True,P2 核心件首件同息档门)两
# 字段——有意改参,锁同步更新(其余数值字段不变)
_EXPECTED_HASH = ('49b1c3a170e29543d1b606f610008864'
                  '25cd004bac2f728beec703d7b2957943')
# W197/ADR-0380 卖侧下界守卫执行点补全批更新:新增 sell_floor_exec_
# guard_enabled(=True,arbiter 卖候选采纳点复检 + execute_replacement
# 溢出卖出对 TT 体系件改留场;关=回 W195 后行为)——有意改参,锁同步
# 更新(其余数值字段不变)
_EXPECTED_HASH = ('8314847986466986c65ef285bb456647'
                  '4ddc7e215e87eabfefe3d24c61f9fa9a')
# W201/ADR-0381 补完修法批更新:新增 engine_complete_distinct_owned
# (=True,补完缺口 owned 口径 distinct 名单数;关=回 W174 后全羁绊
# 逐件计数)——有意改参,锁同步更新(其余数值字段不变)
_EXPECTED_HASH = ('86cf1f1d2a7c8016e776b3e90de27977'
                  '0da77f3d22717f4944bccd8c6c9d2b97')
# W202/ADR-0382 补完保护集分级批更新:新增 engine_complete_grade_
# down(=True,undeploy 候选枯竭且缺口持续 ≥4 轮时按分级序降级换血;
# 关=回 ADR-0371/0381 后「不硬拆」)——有意改参,锁同步更新
# (其余数值字段不变)
_EXPECTED_HASH = ('1be534f9571445ac589e4e45b751dcb2'
                  'c2157211ee608c85c95ef52f6f8483f7')
# W227/ADR-0400 P1 末窗承接门批更新:新增 handoff_gate_enabled(=False,
# 承接门总开关;A/B 裁决默认关,见 ADR-0400)/handoff_gate_min_round(=8,
# 末窗下界)/handoff_gate_tier_target(=1,承接达标总档位)/handoff_ev_
# gap_bonus(=5.0,EV 承接缺口项单位值)四字段(设计件 08 §4.2 Phase 1;
# 开=承接门行为)——有意改参,锁同步更新(其余数值字段不变)
_EXPECTED_HASH = ('576fc5520257d7ca53d3c5466677b417'
                  '5cac946c910301fd0f752b43c5767291')
# W232/ADR-0402 产星通道批更新:新增 filler_star_unit(=0.0,填充件
# 升星期权分单位值;默认关=A/B 通道保留,ADR-0305 先例)/pair_copy_
# direction_exempt(=False,同名副本豁免 pair_wants 方向门;与 A 同臂
# 开)两字段——有意改参,锁同步更新(其余数值字段不变)
_EXPECTED_HASH = ('9e19c00dd27a472e62f692166770752d'
                  '449bba586450d4d1bc6a315f9a206702')
# W238/ADR-0403 承接门 hp 维 boss 投影批更新:新增 handoff_boss_project
# (=False,投影总开关,与 handoff_gate_enabled 正交;A/B 裁决默认关,见
# ADR-0403)/handoff_boss_e_damage(=E[boss伤害|板深档] 常数表 {9:29.25,
# 12:30.35,15:17.5},Δ池 plane=1 boss 桶删失剔除均值)/handoff_boss_
# e_damage_default(=27.33,缺桶 fallback 全池未删失均值)/handoff_boss_
# reward_bonus(=2,r8 奖励胜唯一正项)四字段(设计件 09 §3.1 第一步;
# 开=boss 后投影 hp 喂档位切点)——有意改参,锁同步更新(其余字段不变)
_EXPECTED_HASH = ('8aa7396660bb0b72bfc33f31a200e749'
                  '3b2a9daa3b3f5aafce836cdc40dfc5d9')
# W240/ADR-0404 Δ池 boss 桶键改批更新:handoff_boss_e_damage 重标定
# (键域 {9:29.25,12:30.35,15:17.5}→{0:27.57},boss 桶键 Σboard→净星深
# =上场件 Σ(star−1);P1 boss 语料 49 行全落桶 0,旧三桶条件性=键口径
# 伪影)/handoff_boss_e_damage_default(27.33→27.57,全池未删失均值)
# 两字段值变(ADR-0403 已知边界②的修复落地,键口径论证见 ADR-0404)
# ——有意改参,锁同步更新(其余字段不变)
# W242/ADR-0405 末窗星级定向授权批更新:新增 handoff_star_directed=
# False(默认关,与 gate/proj 三 flag 正交;零数值常量)——有意加字段,
# 锁同步更新(其余字段不变)
# W244/编排者裁决批更新:handoff_boss_e_damage {0:27.57}→{0:34.0}/
# _default 27.57→34.0——boss Δ 全分布双峰(W244:低伤簇 13.25±1.04/
# 高伤簇 34.10±1.77,中间零观测),投影口径均值→Q3 保守(防 hp 临界局
# tier 高估一档=重蹈 W234 缺口)——有意改参,锁同步更新
# W251/ADR-0408 假设 A 批更新:新增 early_pace_* 五字段(enabled=False
# 默认关/min 3/max 4/bias 5.0/val_max 0.5)——有意加字段,锁同步更新
# (其余字段不变)
# W252/ADR-0409 M-A 批更新:新增 handoff_refresh_directed(False)/
# directed_refresh_per_round(2)/directed_refresh_game_cap(6)——
# 与 W251 未提交常量**合并重算**(同一工作树口径;W251 收账若改参
# 以其批再同步)
# _EXPECTED_HASH = ('4aed01b80c9fc6445ff3b73cf9af632a204d274dd839cafe0f0a65c1af097443')
# W257/ADR-0411 承接门 flag 家族清理批更新:删除 handoff_gate_enabled/
# handoff_boss_project/handoff_star_directed/handoff_refresh_directed
# 四布尔字段(gate/proj/star 定向/M-A 定向刷新四通道转正为无条件路径,
# 量级常量保留:handoff_gate_min_round/tier_target/ev_gap_bonus/
# boss_e_damage 族/directed_refresh_per_round/game_cap 不变)——有意
# 删字段,锁同步更新(其余字段不变)
# _EXPECTED_HASH = ('475f84c3d7e9ee0a0fadd67b7b248e4976fc08254a004d00205ed0b8cadb5af5')
# W288/ADR-0418 gate_min_round 前移批更新:handoff_gate_min_round 8→6
# (W275 四臂配对 AB 兑换「调常量」映射;core2≥1 进场率 +6.7pt/金面
# 无信号;落地前置核验=回放漂移仅限 P1 r6+、提前窗买质量反升——
# 证据链见 ADR-0418)——有意改参,锁同步更新(其余字段不变)
# _EXPECTED_HASH = ('8233f2820f3a26ed6cfa94cc448b61c4'
#                   '9f77c21fecece50a431be1fabe12c296')
# W332b 未成型期姿态批更新:新增 release/换线判据参数族(release_enabled/
# k_alert/k_linear/k_hp_calibration_grid/blood_margin_low_hp/boss_tax_p75/
# boss_tax_anchor_group/delta_hp_normal/delta_hp_boss/line_switch_enabled/
# line_switch_theta/line_switch_debias_delta/line_switch_min_dwell;
# 符号不稳参数=默认值+标定接口,sim 批网格标定后锁值)——有意加字段,
# 锁同步更新(既有字段默认值不变)
# 连胜 EV 地板标定批更新:新增 streak_floor_loss_damage/streak_floor_
# win_rate 两字段(discipline._streak_floor 标定账,ADR-0356 挂账项;
# 来源=W324 语料 two_state_model/win_rate_table_injected)——有意加
# 字段,锁同步更新(既有字段默认值不变)
# release 活栈消费门批更新:新增 release_spend_gate_enabled 一字段(判据
# 单一源=decision_v2.posture_release.spend_gate_active;开关语义见
# registry 字段注释)——有意加字段,锁同步更新(既有字段默认值不变)
# P2 生存批更新:新增濒死带期望账三字段(dying_band_account_enabled/
# dying_band_next_loss)+存活轮数门三字段(line_switch_survival_gate_
# enabled/line_switch_survival_margin/line_switch_round_loss);标定源=
# .debug/temp/currency_war/w353_p2_survival/w354_calibrate_p2_loss.py
# (P2 损血谱粗档)。两开关默认 False=现行为零漂移(A/B 基线臂)——
# 有意加字段,锁同步更新(既有字段默认值不变)
# W300 press 通道批更新(V-B3 全量 registry 化):新增 press 七字段
# (press_channel_enabled/press_band_cum_threshold/press_channel_max_level
# /press_copy_unit/press_copy_round_cap/press_exempt_round_cap/
# press_core_mirror_bonus;默认全关/中性=零漂移)+ buy_tag_priority 增
# copy_press + economy/war 放行标签集增 copy_press。设计单一源=
# .debug/temp/currency_war/w300_dup_ruling/design.md v3 节——有意加
# 字段,锁同步更新(既有字段默认值不变)。后续 release_spend_gate_enabled
# 默认值翻转(False→True,开臂,行为面=A/B 验证的 gate 生效),锁再同步。
# 再后续 press_channel_enabled 默认翻转(False→True,W368 A/B R2 成立开臂),锁再同步。
# 再后续 P2 损血参数重校批更新:vd_p2_loss 16.0→20.05(P12 收益侧条件败局
# 伤害;标定源=.debug/temp/currency_war/w353_p2_survival/w354_p2_loss_calib.json
# p2|normal 桶均值 n=19,删失 hp≤1→偏低估下界;旧值系实测带拍值无标定依据。
# DP 侧同批重校 cw_horizon.P2_LOSS_SCALE=5.33(无条件口径=条件×(1−p̄),
# 非 registry 字段,锁在
# test_cw_w370_p2_loss_recalib.py)——有意改参(校准直接生效),锁同步更新
# (其余字段不变)。
# C3/C4 重设计落码批更新:删 line_switch_round_loss(等权除数口径退役,
# 由剩余节点逐节点投影取代);新增 line_switch_node_loss(节点损血表,
# 默认暂抄现行三档+reward 零损档)/p_win_p2_by_rung(两态口径占位,
# 空 dict=p=1 退化为常数)/encounter_heal_est(回血期望,默认 0 下界)/
# line_switch_boss_ci_halfwidth(1.53,投影路径含 boss 的不确定性附加费)/
# dying_band_high_cost_floor(4,定向刷新存在性名集的高费下界)五字段;
# dying_band_next_loss 数值不变(重标定值见
# .debug/temp/currency_war/w373_c3c4_redesign/w375_dual_source_calib.json,
# 终值覆写归 M1 定稿)。两开关默认 False=现行为零漂移——有意改字段面,
# 锁同步更新(既有数值字段不变)。
# C1 溢余必花定向优先级批更新:新增 c1_directed_spend_enabled 一字段
# (默认 False=现行为零漂移,A/B 基线臂;辖域=P1 末窗投影安全带
# d≥emergency_hp 的 FLIP 正交补集,设计单一源=
# .debug/temp/currency_war/w382_c1_design/DESIGN.md §2/§3;破息分支
# 不实现,过账判据存档于 registry 注释)——有意加字段,锁同步更新
# (既有字段默认值不变)。
# 损血表合一更新:删 dying_band_next_loss/line_switch_node_loss 两字段,
# 合一为 p2_node_loss_table 单表(C3 桶位查表与 C4 逐节点投影共读;默认值
# =现行生效值零漂移,重标定值指针见 registry 字段注释)——有意改字段面,
# 锁同步更新(存活数值不变;单一源不变量锁在 test_cw_w373_c3c4_redesign
# .test_p2_node_loss_table_single_source)。
_EXPECTED_HASH = ('ba903798c0747e99d3c744d4e9a619232063270ef08fcede010313245aef4ea0')


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


def test_calibration_snapshot_values() -> None:
    """标定存活参快照(refresh 附庸闸十一参已随 W126/ADR-0349 删除;
    改动须重标定+更新本锁)。"""
    assert DEFAULT_REGISTRY.target_hold_base == 9
    assert DEFAULT_REGISTRY.off_target_sell_bias == 0.5
    assert DEFAULT_REGISTRY.piggy_refresh_ev == 2.5   # 扑满凑伤害 D 专属


def _norm(v):
    """可 JSON 化归一(tuple 键/集合→排序字符串;与 hash 计算同源)。"""
    if isinstance(v, dict):
        return {str(k): _norm(x)
                for k, x in sorted(v.items(), key=lambda t: str(t[0]))}
    if isinstance(v, (set, frozenset)):
        return sorted(map(str, v))
    if isinstance(v, tuple):
        return list(map(_norm, v))
    return v


def test_calibration_registry_hash() -> None:
    """registry 全字段 hash 锁:任何字段漂移即红(防静默改参)。"""
    payload = {f: _norm(getattr(DEFAULT_REGISTRY, f))
               for f in DecisionV2Registry.__dataclass_fields__}
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True,
                   ensure_ascii=False).encode('utf-8')).hexdigest()
    assert digest == _EXPECTED_HASH, (
        f'registry 漂移:hash {digest} != {_EXPECTED_HASH};'
        '若是有意改参——重标定(ADR-0293 流程)并更新本锁')


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


def test_strategy_default_uses_calibrated_registry() -> None:
    """默认策略注入标定后 registry(标定参数即生产行为)。"""
    s = DecisionV2Strategy()
    assert s.registry is DEFAULT_REGISTRY
    assert s.registry.target_hold_base == 9
