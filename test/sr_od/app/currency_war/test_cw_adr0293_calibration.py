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
