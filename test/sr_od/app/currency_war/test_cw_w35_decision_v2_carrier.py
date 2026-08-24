"""W35 载体批锁(decision_v2 唯一策略载体 + 纪律族移植 + registry 双注册)。

锁定对象(ADR-0309):
① 继承解耦:DecisionV2Strategy 不再继承 LineStrategy(独立
   DefaultCwStrategy 实现;decision_v2 包不 import line_strategy);
② 意向接线:update_target 驱动 cw_intention 锁线,写 v3_hoard/
   target_comp(COMP_LIBRARY v2 真 Comp);
③ 纪律族逐条(strategy_v4 点4/点7/点12):
   - hp 报警不触发 ALL IN(报警=处置梯度,非触发);
   - 位面末 ALL IN 限定(唯一清零地板的路径);
   - 应急绝对档/保血通道(报警+硬节点放行 refresh)/boss_breaker
     破息地板/carry 腾位门;
④ 演进引擎进决策循环(evolution_step 显式动作前置);
⑤ 冒烟:P1 一轮 sim 决策不炸;
⑥ 双注册(C5):line_v2 与 decision_v2 同 registry 可发现,config
   开关字段在。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.cw_intention import HoardTarget
from sr_od.application.currency_war.cw_sim import simulate_p1
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.discipline import (
    BloodAlarmTracker,
    assess_discipline,
    carry_gate_actions,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.strategy import (
    DecisionV2Strategy,
)
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)

_REG = DEFAULT_REGISTRY


def _card(name: str, faction: str = '仙舟', cost: int = 1) -> ShopCard:
    return ShopCard(x=0, name=name, faction=faction, cost=cost)


def _bench(name: str, faction: str = '仙舟', slot: int = 0,
           star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 4, 'gold': 30, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _sess(**kw) -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def _locked_sess() -> StrategySession:
    """意向锁定 session(锁定套=列车同行;hoard=意向线采购集子样)。"""
    from sr_od.application.currency_war.cw_intention import IntentionState
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '列车同行'   # COMP_LIBRARY v2 套名(姬子列车家族)
    s = _sess(v3_intention=ist)
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {'姬子·启行'}
    return s


# --- ① 继承解耦 --------------------------------------------------------------


def test_no_linestrategy_inheritance() -> None:
    """DecisionV2Strategy 独立实现:MRO 无 LineStrategy(执行钩子继承
    DefaultCwStrategy——战略/备战决策自持,ADR-0309 载体批)。"""
    assert LineStrategy not in DecisionV2Strategy.__mro__
    assert DecisionV2Strategy.STRATEGY_ID == 'decision_v2'


def test_decision_v2_modules_do_not_import_line_strategy() -> None:
    """decision_v2 包源码零 line_strategy **import**(载体独立;文档性
    提及不算——正则只匹配 import 语句)。"""
    import re

    import sr_od.application.currency_war.decision_v2.candidates as m_cand
    import sr_od.application.currency_war.decision_v2.discipline as m_disc
    import sr_od.application.currency_war.decision_v2.strategy as m_strat
    pat = re.compile(r'(from\s+\S*line_strategy\s+import|'
                     r'^\s*import\s+\S*line_strategy)', re.M)
    for mod in (m_strat, m_cand, m_disc):
        src = Path(mod.__file__).read_text(encoding='utf-8')
        assert not pat.search(src), \
            f'{Path(mod.__file__).name} 残留 line_strategy import'


# --- ② 意向接线 --------------------------------------------------------------


def test_update_target_locks_intention_and_writes_hoard() -> None:
    """③核心卡信号(姬子·启行在店)→ 意向锁定;v3_hoard/target_comp
    写入(target_comp=COMP_LIBRARY v2 真 Comp,属性面兼容 deploy 消费)。"""
    strat = DecisionV2Strategy()
    sess = _sess()
    st = _state(shop=[_card('姬子·启行', faction='列车同行', cost=4)])
    strat.update_target(st, sess, None)
    ist = sess.v3_intention
    assert ist.phase == 'locked' and ist.locked_comp == '列车同行'
    assert sess.v3_hoard is not None
    assert sess.v3_hoard.mode == 'locked'
    assert '姬子·启行' in sess.v3_hoard.char_targets
    assert sess.target_comp is not None
    assert '姬子·启行' in (sess.target_comp.core_chars or [])
    assert '列车同行' in (sess.target_comp.factions or [])


def test_update_target_round_guard_no_miss_inflation() -> None:
    """段级重入守卫:同轮多次 update_target 不重复驱动 miss 计数
    (sim 每轮最多 8 段重入——撤销出口①的分母=轮)。"""
    strat = DecisionV2Strategy()
    sess = _sess()
    # 锁定一条核心不可见的线(构造:先锁定后撤走核心)
    st = _state(shop=[_card('姬子·启行', faction='列车同行', cost=4)])
    strat.update_target(st, sess, None)
    assert sess.v3_intention.phase == 'locked'
    st2 = _state(shop=[], level=8)   # 高等级:刷新窗开,核心不可见
    for _ in range(8):               # 同轮 8 段重入
        strat.update_target(st2, sess, None)
    assert sess.v3_intention.phase == 'locked', \
        '同轮重入不得把 miss 计到撤销阈值(CORE_MISS_N=6)'


# --- ③ 纪律族逐条 ------------------------------------------------------------


def test_blood_alarm_does_not_trigger_allin() -> None:
    """hp 报警语义(点4):三臂报警激活 → 处置梯度(war+保血通道),
    **不触发 ALL IN**——地板保持(allin=False;仲裁地板非零)。"""
    tracker = BloodAlarmTracker()
    tracker.record('battle', 80, 60, 1)   # 单场 -20(打输)
    tracker.record('battle', 60, 38, 2)   # 连续第 2 场打输(臂①)
    assert tracker.alarm_active()
    sess = _sess(v3_alarm=tracker, node_type_current='battle')
    st = _state(round_num=5, gold=55)
    disc = assess_discipline(st, sess, _REG)
    assert disc.coverage == 'blood_alarm'
    assert disc.allin is False, 'hp 报警不得触发 ALL IN(点4 报警语义)'
    reg_view = disc.arbiter_registry(_REG)
    assert reg_view.interest_floor == _REG.interest_floor != 0


def test_allin_only_plane_last_battle() -> None:
    """位面末 ALL IN 限定(点7/[18]):boss 节点+轮=位面节点数 →
    地板清零;位面末非 boss / boss 非位面末均不 ALL IN。"""
    sess = _sess(node_type_current='boss')
    st = _state(round_num=9, gold=55)
    disc = assess_discipline(st, sess, _REG)
    assert disc.coverage == 'boss_breaker'
    assert disc.allin is True
    assert disc.arbiter_registry(_REG).war_floor == 0
    # 反例 1:boss 但非位面末(r6)
    disc2 = assess_discipline(_state(round_num=6), sess, _REG)
    assert disc2.allin is False
    assert disc2.war_floor_override == _REG.boss_floor   # 破息地板 10
    # 反例 2:位面末但非 boss(奖励关)
    sess2 = _sess(node_type_current='奖励')
    disc3 = assess_discipline(_state(round_num=9), sess2, _REG)
    assert disc3.allin is False


def test_emergency_coverage_and_floor() -> None:
    """应急绝对档:hp≤emergency_hp → coverage=emergency,rebirth
    地板由层4分派([18] 保留重生基数)。"""
    sess = _sess()
    disc = assess_discipline(_state(hp=20, gold=55), sess, _REG)
    assert disc.coverage == 'emergency'
    from sr_od.application.currency_war.decision_v2.arbiter import (
        _active_floor,
    )
    assert _active_floor(_state(hp=20, gold=55), sess,
                         _REG) == _REG.rebirth_floor


def test_blood_alarm_hard_node_allows_refresh() -> None:
    """保血通道(点12):报警+遭遇/boss 节点 → war 态放行 refresh
    (弃息 D 保血);非硬节点不放行。"""
    tracker = BloodAlarmTracker()
    tracker.record('battle', 80, 60, 1)
    tracker.record('battle', 60, 38, 2)
    sess = _sess(v3_alarm=tracker, node_type_current='encounter')
    disc = assess_discipline(_state(round_num=5), sess, _REG)
    assert disc.allow_refresh_in_war is True
    assert 'refresh' in disc.arbiter_registry(_REG).war_tags
    sess2 = _sess(v3_alarm=tracker, node_type_current='奖励')
    disc2 = assess_discipline(_state(round_num=5), sess2, _REG)
    assert disc2.allow_refresh_in_war is False


def test_carry_gate_demotes_protection_and_buys_core() -> None:
    """carry 腾位门(v1 r416 移植):bench 满(全保护件)+意向核心在店+
    金足 → [SellBench(最弱), BuyCard(核心, reason=carry_gate)];
    卖出件入同轮已卖集(r408 对称臂)。"""
    sess = _locked_sess()
    sess.v2_round_key = (1, 4)
    bench = [_bench('花火', faction='欢愉', slot=i)
             for i in range(_REG.bench_capacity)]   # 全保护件(shared)
    st = _state(round_num=4, gold=50,
                shop=[_card('姬子·启行', faction='列车同行', cost=4)],
                bench=bench)
    acts = carry_gate_actions(st, sess, _REG)
    assert len(acts) == 2
    sell, buy = acts
    assert sell.__class__.__name__ == 'SellBench'
    assert isinstance(buy, BuyCard) and buy.card.name == '姬子·启行'
    assert buy.reason == 'carry_gate'
    sold_name = st.bench[sell.bench_idx].char_id
    assert sold_name in sess.v2_round_sold


def test_carry_gate_noop_when_bench_not_full() -> None:
    """bench 未满 → 常规买通道可达,不腾位(收益域限定)。"""
    sess = _locked_sess()
    st = _state(round_num=4, gold=50,
                shop=[_card('姬子·启行', faction='列车同行', cost=4)],
                bench=[_bench('杂件0', faction='公司')])
    assert carry_gate_actions(st, sess, _REG) == []


def test_catchup_coverage_level_gate() -> None:
    """追赶(r232 等级门):等级≥6+人口<基线-1 → catchup;P1 早期
    (低等级)人口低不算追赶。"""
    from sr_od.application.currency_war.decision_v2.filters import (
        is_catchup,
    )
    sess = _sess()
    st = _state(plane=2, level=6, deployed=[_bench('甲'), _bench('乙')])
    disc = assess_discipline(st, sess, _REG)
    assert disc.coverage == 'catchup' and disc.mode == 'economy'
    assert is_catchup(_state(plane=1, level=3,
                             deployed=[_bench('甲')]), sess, _REG) is False


# --- ④ 演进引擎进决策循环 ----------------------------------------------------


def test_evolution_step_wired_into_decide_prep(monkeypatch) -> None:
    """evolution_step 显式动作前置 decide_prep(点6 统一入口;载体批
    接线——引擎自身语义由 W33 锁覆盖,此处锁接线)。"""
    strat = DecisionV2Strategy()
    sess = _locked_sess()
    sentinel = SimpleNamespace(__class__=type('FakeTx', (), {}),
                               reason='evolve:test')
    seen: dict = {}

    def _fake_evo(state, session, memory):
        seen['memory'] = memory
        return [sentinel]

    import sr_od.application.currency_war.decision_v2.strategy as m
    monkeypatch.setattr(m, 'evolution_step', _fake_evo)
    st = _state(round_num=4, gold=30, shop=[], bench=[],
                node_type='battle')
    acts = strat.decide_prep(st, sess, None)
    assert acts and acts[0] is sentinel, '演进动作必须前置决策循环'
    assert seen['memory'] is sess.v3_evolution


# --- ⑤ 冒烟:P1 一轮 sim 决策不炸 --------------------------------------------


def test_smoke_one_sim_game_new_carrier() -> None:
    """新载体冒烟:P1 一局 sim(fallback 池)跑通无崩、有决策活性。"""
    strat = DecisionV2Strategy()
    res = simulate_p1(424242, pool='fallback', strategy=strat)
    assert res.final_hp >= 0
    # 方向建立率/分布归 A/B 验收(步5);冒烟只锁「不炸 + 账本非空」:
    assert res.ledger


# --- ⑥ 双注册(C5)------------------------------------------------------------


def test_dual_registration_both_strategies_discoverable() -> None:
    """双注册:line_v2 与 decision_v2 同 registry 可发现(回退开关
    前提;C5——test_cw_strategy 同款发现面,此处锁载体批后仍成立)。"""
    import sr_od.application.currency_war.cw_strategy as _cw_mod
    from one_dragon.base.operation.application.plugin_info import (
        PluginSource,
    )
    from sr_od.application.currency_war.cw_strategy_manager import (
        StrategyManager,
    )
    builtin = Path(_cw_mod.__file__).parent / 'strategies'
    mgr = StrategyManager(ctx=None,
                          plugin_dirs=[(builtin, PluginSource.BUILTIN)])
    ids = [i.strategy_id for i in mgr.strategies]
    assert 'line_v2' in ids, f'旧策略未注册(回退开关失效):{ids}'
    assert 'decision_v2' in ids, f'新策略未注册:{ids}'
    # 载体批后桥到的真身是独立实现(非 LineStrategy 子类)
    strat = mgr.instantiate('decision_v2')
    assert isinstance(strat, DecisionV2Strategy)
    assert LineStrategy not in strat.__class__.__mro__


def test_config_switch_field_exists() -> None:
    """C5 开关:CurrencyWarConfig 源码含 strategy_id 装载(切 line_v2/
    decision_v2;默认 default 不变——切换验收归步 5)。"""
    import inspect

    from sr_od.application.currency_war.currency_war_config import (
        CurrencyWarConfig,
    )
    assert "strategy_id" in inspect.getsource(CurrencyWarConfig)
