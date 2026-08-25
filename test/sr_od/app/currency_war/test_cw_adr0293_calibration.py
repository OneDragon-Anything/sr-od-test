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
    RefreshShop,
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
    """标定五参快照(ADR-0293 标定结果;改动须重标定+更新本锁)。"""
    assert DEFAULT_REGISTRY.refresh_ev == 2.5
    assert DEFAULT_REGISTRY.refresh_max_round == 6
    assert DEFAULT_REGISTRY.refresh_min_gold == 20
    assert DEFAULT_REGISTRY.target_hold_base == 9
    assert DEFAULT_REGISTRY.off_target_sell_bias == 0.5


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


def test_refresh_round_gate() -> None:
    """轮界门:r≤6 按 refresh_ev 计净值;r>6 恒负分不刷。"""
    sess = StrategySession()
    cost = RefreshShop(cost=2).cost
    for rn, expect_pos in ((5, True), (7, False)):
        st = _state(round_num=rn, gold=50,
                    shop=[_card('占位件', faction='公司', cost=1)])
        cand = [c for c in generate_candidates(st, sess,
                                               DEFAULT_REGISTRY)
                if c.tag == 'refresh'][0]
        val, _ = score_candidate(cand, st, sess, DEFAULT_REGISTRY)
        if expect_pos:
            assert val == DEFAULT_REGISTRY.refresh_ev - cost
        else:
            assert val < 0, 'r>refresh_max_round 刷新必须恒负分'


def test_refresh_gold_floor_gate() -> None:
    """金保底门:金<20 不刷(防 re-decide 链抽干金流锁死息引擎)。"""
    st = _state(round_num=2, gold=15,
                shop=[_card('占位件', faction='公司', cost=1)])
    sess = StrategySession()
    cand = [c for c in generate_candidates(st, sess, DEFAULT_REGISTRY)
            if c.tag == 'refresh'][0]
    val, _ = score_candidate(cand, st, sess, DEFAULT_REGISTRY)
    assert val < 0, '金<refresh_min_gold 刷新必须恒负分'


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
    assert s.registry.refresh_ev == 2.5
