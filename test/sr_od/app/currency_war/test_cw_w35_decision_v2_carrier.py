"""W35 载体批锁(decision_v2 唯一策略载体 + 纪律族移植 + registry 双注册)。

W51 语义修复批(R1 审查 leader 裁决):报警分支位面末 ALL IN 语义锁
(两向)/三臂窗口单位(战斗节点计数器,跨位面重置)/处置梯度①时限+
[19] 血边际/carry_gate 种子死锁豁免+absent_mergeable 弱序/
on_match_start 跨局残留清零——原「锁实现字面」的测试改语义锁。

锁定对象(ADR-0309):
① 继承解耦:DecisionV2Strategy 独立实现(继承 DefaultCwStrategy;
   decision_v2 包不 import line_strategy——旧件已随 ADR-0336 删);
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
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision_v2.candidates import Candidate
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
    """DecisionV2Strategy 独立实现:MRO 无 LineStrategy(旧件已随
    ADR-0336 删除)且无 DefaultCwStrategy(继承塔已解体——本体退役批后
    dv 直接继承 CwStrategy,执行性钩子平移自持)。"""
    from sr_od.application.currency_war.cw_strategy import CwStrategy
    assert DecisionV2Strategy.__bases__ == (CwStrategy,)
    assert not any(
        c.__name__ == 'DefaultCwStrategy' for c in DecisionV2Strategy.__mro__)
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
    写入(target_comp=COMP_LIBRARY v2 真 Comp,属性面兼容 deploy 消费)。
    (锁线场景设 P2:W145/ADR-0357 起 P1 ③不锁 comp、落配方方向。)"""
    strat = DecisionV2Strategy()
    sess = _sess()
    st = _state(plane=2, shop=[_card('姬子·启行', faction='列车同行', cost=4)])
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
    # 锁定一条核心不可见的线(构造:先锁定后撤走核心;P2——W145 起 P1 ③不锁)
    st = _state(plane=2, shop=[_card('姬子·启行', faction='列车同行', cost=4)])
    strat.update_target(st, sess, None)
    assert sess.v3_intention.phase == 'locked'
    st2 = _state(plane=2, shop=[], level=8)   # 高等级:刷新窗开,核心不可见
    for _ in range(8):               # 同轮 8 段重入
        strat.update_target(st2, sess, None)
    assert sess.v3_intention.phase == 'locked', \
        '同轮重入不得把 miss 计到撤销阈值(CORE_MISS_N=6)'


# --- ③ 纪律族逐条 ------------------------------------------------------------


def _alarm_tracker() -> BloodAlarmTracker:
    """臂①激活且处置梯度已升级到②的 tracker(连续 3 场战斗净掉血
    ≥10;生产节点值「普通战斗」——报警激活后第 2 个战斗节点窗耗尽)。"""
    tracker = BloodAlarmTracker()
    tracker.record('普通战斗', 80, 60, 1)   # 单场 -20(打输代理)
    tracker.record('普通战斗', 60, 38, 2)   # 连续第 2 场(臂①)→ 报警激活
    tracker.record('普通战斗', 38, 16, 3)   # ①自然窗耗尽未达标 → ②升级
    return tracker


def test_blood_alarm_semantics_allin_only_plane_last() -> None:
    """hp 报警语义(点4/[18],W51 语义锁):报警激活 → 处置梯度,
    **报警不是 ALL IN 的触发**——非位面末 allin=False 且地板保持;
    位面末最后一战(boss+轮=位面节点数)→ allin=True(地板清零,
    [18]/点4 授权的报警处置梯度③终点,与 emergency/boss_breaker 同式)。"""
    sess = _sess(v3_alarm=_alarm_tracker(),
                 node_type_current='boss')
    # 正向:报警 + 位面末 boss → ALL IN 通
    disc = assess_discipline(_state(round_num=9, gold=55, hp=80),
                             sess, _REG)
    assert disc.coverage == 'blood_alarm'   # 覆盖序:报警 > boss_breaker
    assert disc.allin is True, '报警态位面末必须开通 ALL IN([18] 授权)'
    assert disc.arbiter_registry(_REG).war_floor == 0
    # 反向:报警 + 非位面末 → 不 ALL IN,地板保持
    sess_nb = _sess(v3_alarm=_alarm_tracker(),
                    node_type_current='battle')
    disc2 = assess_discipline(_state(round_num=5, gold=55, hp=80),
                              sess_nb, _REG)
    assert disc2.coverage == 'blood_alarm'
    assert disc2.allin is False, '报警不得单独触发 ALL IN(点4 报警语义)'
    reg_view = disc2.arbiter_registry(_REG)
    assert reg_view.interest_floor() == _REG.interest_floor() != 0


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
    """保血通道(点12):报警已升级(②弃息 D)+遭遇/boss 节点 → war 态
    放行 refresh(弃息 D 保血);非硬节点不放行。"""
    sess = _sess(v3_alarm=_alarm_tracker(), node_type_current='encounter')
    disc = assess_discipline(_state(round_num=5, hp=80), sess, _REG)
    assert disc.allow_refresh_in_war is True
    assert 'refresh' in disc.arbiter_registry(_REG).war_tags
    sess2 = _sess(v3_alarm=_alarm_tracker(), node_type_current='奖励')
    disc2 = assess_discipline(_state(round_num=5, hp=80), sess2, _REG)
    assert disc2.allow_refresh_in_war is False


# --- ③b W51 语义修复锁(三臂窗口单位/处置梯度时限/血边际) -------------------


def test_blood_alarm_non_battle_nodes_not_counted_nor_reset() -> None:
    """战斗语义(点4 冻结):非战斗节点不入窗、不清臂——臂①连续计数
    跨非战斗节点保持(战斗失败 → 奖励关 → 战斗失败 → 仍臂①触发)。"""
    t = BloodAlarmTracker()
    t.record('普通战斗', 80, 68, 1)          # loss 12 → consec 1
    t.record('奖励', 0, 0, 2)                # 非战斗:不计入不重置
    assert t.consec_battle_fails == 1
    assert len(t.recent_losses) == 1
    t.record('普通战斗', 68, 50, 3)          # loss 18 → consec 2
    assert t.alarm_active()


def test_blood_alarm_plane_crossing_resets_arms() -> None:
    """窗口单位=连续战斗节点计数器,**跨位面重置**(W51:慢性臂不再
    按轮漂移横跨整个位面——新位面不带旧位面掉血趋势)。"""
    t = BloodAlarmTracker()
    t.record('普通战斗', 80, 60, 1, plane=1)   # consec 1
    t.record('普通战斗', 60, 38, 2, plane=1)   # consec 2 → 报警激活
    assert t.alarm_active()
    t.record('普通战斗', 38, 20, 10, plane=2)  # 位面变更 → 三臂全清后计本节点
    assert t.consec_battle_fails == 1
    assert len(t.recent_losses) == 1
    assert not t.alarm_active()
    assert t.alarm_battles == 0   # 梯度计时一并重置


def test_blood_alarm_gradient_natural_window_then_escalate() -> None:
    """处置梯度①时限(S4 上界 1 个战斗节点,W51 补):报警激活后首个
    战斗节点窗内 = ①自然补强(mode=economy,不弃息、硬节点也不放行
    refresh);窗耗尽未达标(下一战斗节点后报警仍在)→ ②弃息 D 保血
    (war+硬节点放行 refresh)。"""
    t = BloodAlarmTracker()
    t.record('普通战斗', 80, 60, 1)          # consec 1
    t.record('普通战斗', 60, 38, 2)          # consec 2 → 报警,alarm_battles=1
    sess = _sess(v3_alarm=t, node_type_current='遭遇')
    disc = assess_discipline(_state(round_num=5, hp=80), sess, _REG)
    assert disc.coverage == 'blood_alarm' and disc.mode == 'economy', \
        '①自然补强窗内不弃息'
    assert disc.allow_refresh_in_war is False
    t.record('普通战斗', 38, 16, 3)          # 窗耗尽仍未达标,alarm_battles=2
    disc2 = assess_discipline(_state(round_num=6, hp=60), sess, _REG)
    assert disc2.mode == 'war' and disc2.allow_refresh_in_war is True, \
        '① 1 个战斗节点未达标 → 直入②弃息 D(血边际 60≥40,纯计时器升级)'


def test_blood_alarm_low_hp_margin_skips_natural_window() -> None:
    """[19]② 血边际变量(W51 接):hp<BLOOD_MARGIN_LOW_HP(40)时处置
    梯度本就生效——跳过①自然补强窗直入②(war+保血通道)。"""
    from sr_od.application.currency_war.decision_v2.discipline import (
        BLOOD_MARGIN_LOW_HP,
    )
    t = BloodAlarmTracker()
    t.record('普通战斗', 80, 60, 1)
    t.record('普通战斗', 60, 38, 2)          # alarm_battles=1(①窗内)
    sess = _sess(v3_alarm=t, node_type_current='遭遇')
    disc = assess_discipline(
        _state(round_num=5, hp=BLOOD_MARGIN_LOW_HP - 1), sess, _REG)
    assert disc.mode == 'war', '血边际低 → 不等①自然窗,梯度直接生效'
    assert disc.allow_refresh_in_war is True


def test_carry_gate_demotes_protection_and_buys_core() -> None:
    """carry 腾位门(v1 r416 移植;W52/ADR-0327 适配):bench 满(全保护
    件,各 1 份)+意向核心在店+金足 → [SellBench(最弱保护件), BuyCard
    (核心, reason=carry_gate)];卖出件入同轮已卖集(r408 对称臂)。

    构造注:9 槽满员且 bench 不得含 carry(②门「未持有」);用 7 个互异
    保护件 + 2 重复(重复份加权≥2 是 3合1 素材,被 AD9-2-3 统一挡,
    不进卖序——其余 1 份保护件可卖)。
    """
    sess = _locked_sess()
    sess.v2_round_key = (1, 4)
    bench = [_bench(n, faction='列车同行', slot=i)
             for i, n in enumerate(['三月七', '花火', '瓦尔特',
                                    '丹恒·饮月', '希儿', '爻光',
                                    '藿藿', '花火', '三月七'])]
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
    assert sold_name not in ('花火', '三月七'), \
        '重复份(加权≥2)是 3合1 素材,不得卖(AD9-2-3)'


def test_carry_gate_noop_when_bench_not_full() -> None:
    """bench 未满 → 常规买通道可达,不腾位(收益域限定)。"""
    sess = _locked_sess()
    st = _state(round_num=4, gold=50,
                shop=[_card('姬子·启行', faction='列车同行', cost=4)],
                bench=[_bench('杂件0', faction='公司')])
    assert carry_gate_actions(st, sess, _REG) == []


# --- ③c W51 语义修复锁(carry_gate 种子死锁豁免/absent_mergeable 弱序) ------


def test_carry_gate_seed_deadlock_exemption() -> None:
    """种子窗口绝对不让位(W88/ADR-0339 件3 语义重写;原 W51「死锁豁免」
    已裁决移除):bench 满+全保护件+唯一可卖=种子(ADR-0289 §5 年龄窗)
    → 本轮**不腾位**(carry 延后,窗口 ≤2 轮自然解锁,死锁有界)——
    旧豁免=买侧见即买 engine_seed 与卖侧 carry_gate 互踩(seed16
    姬子·启行 r4 买 r6 卖 r7 再买,engine_seed_not_resold 0 容忍与
    设计豁免矛盾);有非种子直接可卖件时走直接通道不降保护集。"""
    # 场景 1:全 bench 为种子(保护件,2 轮窗内 cnt=1)→ 不腾(carry 让位)
    from sr_od.application.currency_war.cw_system_cards import (
        engine_char_names,
    )
    _names = (['花火', '花火', '三月七', '三月七', '瓦尔特', '瓦尔特']
              + sorted(n for n in engine_char_names()
                       if n not in ('姬子·启行', '三月七', '花火', '瓦尔特'))[:3])
    assert len(_names) >= 9
    sess = _locked_sess()
    sess.v2_round_key = (1, 4)
    sess.v2_seed_bought = dict.fromkeys(set(_names), ((1, 3), 1))
    bench = [_bench(n, faction='欢愉', slot=i)
             for i, n in enumerate(_names[:9])]
    st = _state(round_num=4, gold=50,
                shop=[_card('姬子·启行', faction='列车同行', cost=4)],
                bench=bench)
    assert carry_gate_actions(st, sess, _REG) == [], \
        '窗口内种子不让位给 carry 腾位(互踩裁决:carry 延后有界)'
    # 场景 2(对照):存在非种子、非保护、非板面阵营的可卖件 → 直接
    # 卖通道已解,不走降保护集
    sess2 = _locked_sess()
    sess2.v2_round_key = (1, 4)
    sess2.v2_seed_bought = {'花火': ((1, 3), 1)}
    bench2 = ([_bench('杂件', faction='公司', slot=0)]
              + [_bench('花火', faction='欢愉', slot=i)
                 for i in range(1, 9)])
    st2 = _state(round_num=4, gold=50,
                 shop=[_card('姬子·启行', faction='列车同行', cost=4)],
                 bench=bench2)
    assert carry_gate_actions(st2, sess2, _REG) == []


def test_carry_gate_merge_material_not_sold() -> None:
    """AD9-2-3 适配(W52/ADR-0327):3合1 进行中素材(加权副本≥2,如
    2★ 件)不可卖——carry 腾位时跳过素材件,改卖 1 份保护件。

    旧行为(absent_mergeable 最弱级先卖)已按指挥官裁决反转:拆合成
    进度防于腾位通道之前;原锁语义重写(锁语义不锁旧行为)。"""
    sess = _locked_sess()
    sess.v2_round_key = (1, 4)
    # 瓦尔特 2★(加权副本 2=进行中素材)→ 不可卖;其余 1 份保护件可卖
    # (W192/ADR-0375 适配:原 fixture 的希儿(唯一种子)与花火(希儿在
    # 手时量子放大 ≤2)现被卖守卫辖——本锁域意图是素材件不卖,换冗余
    # 仙舟件符玄并置 board 含仙舟(③ 直接卖通道判定按 faction∈board
    # 跳过),保持「全保护/无直接可卖 → 降保护集」前置成立)
    bench = ([_bench('瓦尔特', faction='列车同行', slot=0, star=2)]
             + [_bench(n, faction='列车同行', slot=i)
                for i, n in enumerate(['三月七', '花火', '丹恒·饮月',
                                       '希儿', '爻光', '藿藿', '三月七'])
                ] + [_bench('符玄', faction='仙舟', slot=8)])
    st = _state(round_num=4, gold=50, board={'仙舟': 1},
                shop=[_card('姬子·启行', faction='列车同行', cost=4)],
                bench=bench)
    acts = carry_gate_actions(st, sess, _REG)
    assert len(acts) == 2
    sell = acts[0]
    sold_name = st.bench[sell.bench_idx].char_id
    assert sold_name != '瓦尔特', \
        '2★ 素材(加权副本 2)不可卖(AD9-2-3 拆合成进度防御)'
    assert sold_name in sess.v2_round_sold


# --- ③d 金不足补偿(回连机制收编;W52/ADR-0326) ------------------------------
# 旧 liquidity_actions 已删,语义收编进 decision_v2/remediation.py 的
# _compensate_gold(层4 末段补偿趟,触发源=实际拒绝事件)。本组锁按
# 「锁语义不锁函数名」重写:同构造断言 decide_prep/arbitrate 产出。


def _comp_reg():
    """补偿锁视口注册表(boss_breaker war 地板 10;与 decide_prep
    assess_discipline 同通路)。"""
    from dataclasses import replace
    return replace(_REG, war_floor=10)


def _comp_state(gold: int, bench_names: list[str], cost: int = 4,
                round_num: int = 5, board: dict | None = None,
                node_type: str = 'boss',
                ) -> GameState:
    """补偿场景状态:锁定意向(列车同行)+boss 节点(boss_breaker war;
    W119/ADR-0347 构造适配:boss 窗改节点图口径,node_type='boss' 显式
    命中——旧 r≥5 轮数口径已退场)+满员上阵 5/5(防 deploy 干扰
    bench)+指定 bench 压库件 + 店目标件。"""
    return _state(round_num=round_num, gold=gold, hp=80,
                  node_type=node_type,
                  bench=[_bench(n, faction='公司', slot=i)
                         for i, n in enumerate(bench_names)],
                  shop=[ShopCard(x=0, name='姬子·启行', faction='列车同行',
                                 cost=cost)],
                  deployed=[_bench(f'D{i}', faction='公司', slot=i)
                            for i in range(5)],
                  board=board or {})


def test_remedy_gold_sells_to_fund_priority_buy() -> None:
    """①金不足+目标件在店+bench 有非保护压库件 → decide_prep 产出
    [Sell≥1, Buy] 组,卖先于买;买 reason=d2_line_carry;卖出件入同轮
    已卖集(r408 对称臂)。

    W67/ADR-0328 构造适配:exec_state 执行域对齐后,演进事务先于
    arbitrate 落地(见 decide_prep ⑤ 注释)——压库件须选演进不消费的
    件(阮·梅/星期日非体系候选,COMP 不 deploy 它们;卡芙卡/千冶·刃
    是千冶减益目标,会被演进抢先上场致补偿无可卖件)。锁语义不变:
    金不足+可卖压库件 → 补偿卖凑金买目标件。"""
    strat = DecisionV2Strategy()
    sess = _locked_sess()
    st = _comp_state(gold=13, bench_names=['阮·梅', '星期日'])
    acts = strat.decide_prep(st, sess, None)
    sells = [a for a in acts if isinstance(a, SellBench)]
    buys = [a for a in acts if isinstance(a, BuyCard)]
    assert sells and buys, f'金不足应补偿 [Sell, Buy] 组:{acts}'
    assert acts.index(sells[0]) < acts.index(buys[0]), '卖先于买'
    assert buys[0].card.name == '姬子·启行'
    assert buys[0].reason == 'd2_line_carry'
    for s in sells:
        assert st.bench[s.bench_idx].char_id in sess.v2_round_sold


def test_remedy_gold_noop_when_gold_enough() -> None:
    """②金足时不卖:金 20(war 地板 10)买 4 费后 16≥10 → 常规通道
    可达,零补偿(无拒绝事件)。"""
    sess = _locked_sess()
    sess.v3_mode = 'war'
    st = _comp_state(gold=20, bench_names=['卡芙卡', '千冶·刃'])
    cand = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                     source='test')
    res = arbitrate([(cand, 5.0, {})], st, sess, _comp_reg())
    assert any(isinstance(a, BuyCard) for a in res.actions)
    assert res.rejections == []
    assert res.remediation_log == []
    assert sess.v2_round_sold == set()


def test_remedy_gold_not_for_low_priority_buy() -> None:
    """③守卫:不为低优先级购买变现——凑数/凑对类(pair/copy/
    bond_fallback)的金不足买不触发补偿(压库资产只服务 remedy_buy_tags
    辖域的目标件/引擎件/插件)。"""
    for tag in ('bond_fallback', 'pair', 'copy'):
        sess = _locked_sess()
        sess.v3_mode = 'war'
        st = _comp_state(gold=13, bench_names=['卡芙卡'])
        cand = Candidate(action=BuyCard(st.shop[0]), tag=tag,
                         source='test')
        res = arbitrate([(cand, 5.0, {})], st, sess, _comp_reg())
        assert res.rejections, f'{tag} 金不足应产生拒绝事件'
        assert res.remediation_log == [], \
            f'{tag} 不得触发补偿(不在 remedy_buy_tags)'
        assert not any(isinstance(a, SellBench) for a in res.actions)


def test_remedy_gold_guards_protect_and_shortfall() -> None:
    """守卫补充:保护集(意向线正料+引擎件)不卖——全 bench 正料时
    金不足也不补偿;可变现不足额时整组放弃(零动作,不卖一半)。"""
    # 全意向线正料(列车同行 shared)→ 保护集挡住 → 无补偿
    sess = _locked_sess()
    sess.v3_mode = 'war'
    st = _comp_state(gold=13, bench_names=['花火', '三月七', '瓦尔特'])
    cand = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                     source='test')
    res = arbitrate([(cand, 5.0, {})], st, sess, _comp_reg())
    assert res.rejections
    assert res.remediation_log == [], '保护集件不得进补偿卖序'
    assert sess.v2_round_sold == set()
    # 不足额:金 5 地板 10 费 4 → 缺口 9;唯一可变现件回 2 → 整组放弃
    sess2 = _locked_sess()
    sess2.v3_mode = 'war'
    st2 = _comp_state(gold=5, bench_names=['卡芙卡'])
    cand2 = Candidate(action=BuyCard(st2.shop[0]), tag='line_carry',
                      source='test')
    res2 = arbitrate([(cand2, 5.0, {})], st2, sess2, _comp_reg())
    assert res2.remediation_log == [], '变现不足额 → 整组放弃(不卖一半)'
    assert not any(isinstance(a, SellBench) for a in res2.actions)
    assert getattr(sess2, 'v3_remedy_abandoned', 0) >= 0


def test_remedy_gold_sell_emission_slot_stability() -> None:
    """补偿卖件发射槽位稳定(ADR-0316;旧 liquidity 降序 hack 收编后
    语义):卖 [槽1, 槽4] → 恰这两槽 None,其余槽逐槽不变;买入落首
    个空槽;占用数守恒。"""
    from sr_od.application.currency_war.cw_state import (
        bench_occupied,
        simulate,
    )
    sess = _locked_sess()
    sess.v3_mode = 'war'
    st = _comp_state(gold=10, bench_names=['花火', '阿格莱雅', '三月七',
                                           '瓦尔特', '娜塔莎'])
    assert st.bench[1].char_id == '阿格莱雅'   # 1费净0
    assert st.bench[4].char_id == '娜塔莎'     # 3费
    cand = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                     source='test')
    res = arbitrate([(cand, 5.0, {})], st, sess, _comp_reg())
    assert res.remediation_log, '缺口 4 → 应有补偿'
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    assert {s.bench_idx for s in sells} == {1, 4}
    assert any(isinstance(a, BuyCard) for a in res.actions)
    working = st
    for a in res.actions:
        working = simulate(working, a)
    assert working.bench[4] is None
    assert working.bench[5] is None   # 紧缩模型下会被误删的对照槽
    assert working.bench[1].char_id == '姬子·启行'   # 买入落首个空槽
    assert working.bench[0].char_id == '花火'
    assert working.bench[2].char_id == '三月七'
    assert working.bench[3].char_id == '瓦尔特'
    assert bench_occupied(working.bench) == 4


# --- ⑥b W51 语义修复锁(on_match_start 跨局残留清零) -------------------------


def test_on_match_start_clears_cross_match_keys() -> None:
    """W51:on_match_start 补清 v3_intention_key/v3_prev_hp——session
    跨局复用时两局键不串:新局 (1,1) 首轮意向必须驱动(不被旧局同键
    吞);三臂首 record 的 hp_before 不带旧局终值。"""
    strat = DecisionV2Strategy()
    sess = _sess()
    # 旧局残留:轮键停在 (2,1)、prev_hp 带旧局终值、事件去重串旧局
    # (锁线场景设 P2——W145/ADR-0357 起 P1 ③不锁 comp;同键撞键语义不变)
    sess.v3_intention_key = (2, 1)
    sess.v3_prev_hp = 45
    sess.v3_last_intention_event = 'lock'
    strat.on_match_start(_state(), sess, None)
    assert sess.v3_intention_key is None
    assert sess.v3_prev_hp is None
    assert sess.v3_last_intention_event == ''
    # 行为面 1:新局 (2,1) 首轮意向必须驱动——核心在店 → 锁定
    # (若旧键 (2,1) 残留,段级守卫误吞 → phase 停留初始态)
    st = _state(plane=2, round_num=1,
                shop=[_card('姬子·启行', faction='列车同行', cost=4)])
    strat.update_target(st, sess, None)
    assert sess.v3_intention.phase == 'locked'
    assert sess.v3_intention_key == (2, 1)
    # 行为面 2:新局首结算的掉血不入窗(prev_hp 从本局首结算起算)
    from sr_od.application.currency_war.cw_performance import RoundOutcome
    sess2 = _sess()
    strat.on_match_start(_state(), sess2, None)
    obs = RoundOutcome(round_num=1, plane=1, node_type='普通战斗',
                       comp_tag='?', hp_after=80, streak=0)
    strat.on_round_end(_state(round_num=1), sess2, None, obs)
    assert len(sess2.v3_alarm.recent_losses) == 0, \
        '首结算无 hp_before(旧局终值已清)→ 不入窗'
    assert sess2.v3_prev_hp == 80


# --- ④ 演进引擎进决策循环 ----------------------------------------------------


def test_evolution_step_wired_into_decide_prep(monkeypatch) -> None:
    """evolution_step 显式动作前置 decide_prep(点6 统一入口;载体批
    接线——引擎自身语义由 W33 锁覆盖,此处锁接线)。"""
    strat = DecisionV2Strategy()
    sess = _locked_sess()
    sentinel = SimpleNamespace(__class__=type('FakeTx', (), {}),
                               reason='evolve:test')
    seen: dict = {}

    def _fake_evo(state, session, memory, off_lock_penalty=0.0,
                  engine_guard=True, final_freeze=True,
                  engine_completion=True, complete_distinct=True,
                  seele_scope=True, sell_floor=True, grade_down=True):
        # W155/ADR-0360:evolution_step 增 off_lock_penalty 关键字
        # (锁定帧 off-lock 提案降级分,registry 注入)——桩同步收参;
        # 同款 registry 注入——桩同步收参(接线锁,语义归 W160 锁);
        # W174/ADR-0371:引擎补完守卫同款注入——桩同步收参(语义归
        # test_cw_w174_engine_completion);W201/ADR-0381:补完缺口
        # owned 口径同款注入(语义归 test_cw_w201_completion_dedup);
        # W192/ADR-0375:希儿系守卫辖域同款注入——桩同步收参(语义归
        # test_cw_w192_seele_scope);W197/ADR-0380:溢出卖出下界守卫
        # 同款注入(语义归 test_cw_w197);W202/ADR-0382:补完保护集
        # 分级同款注入(语义归 test_cw_w202_grade_down)
        seen['memory'] = memory
        seen['off_lock_penalty'] = off_lock_penalty
        seen['engine_guard'] = engine_guard
        seen['final_freeze'] = final_freeze
        seen['engine_completion'] = engine_completion
        seen['complete_distinct'] = complete_distinct
        seen['seele_scope'] = seele_scope
        seen['sell_floor'] = sell_floor
        seen['grade_down'] = grade_down
        return [sentinel]

    import sr_od.application.currency_war.decision_v2.strategy as m
    monkeypatch.setattr(m, 'evolution_step', _fake_evo)
    st = _state(round_num=4, gold=30, shop=[], bench=[],
                node_type='battle')
    acts = strat.decide_prep(st, sess, None)
    assert acts and acts[0] is sentinel, '演进动作必须前置决策循环'
    assert seen['memory'] is sess.v3_evolution
    # W155:registry 的 off-lock 降级分从接线传入(默认 registry 开=3.0)
    assert seen['off_lock_penalty'] == 3.0
    # W160:两开关默认 True 从 registry 注入
    assert seen['engine_guard'] is True
    assert seen['final_freeze'] is True
    # W174/ADR-0371:引擎补完守卫开关默认 True 从 registry 注入
    assert seen['engine_completion'] is True
    # W201/ADR-0381:补完缺口 owned 口径开关默认 True 从 registry 注入
    assert seen['complete_distinct'] is True
    # W192/ADR-0375:希儿系守卫辖域开关默认 True 从 registry 注入
    assert seen['seele_scope'] is True
    # W197/ADR-0380:溢出卖出下界守卫开关默认 True 从 registry 注入
    assert seen['sell_floor'] is True
    # W202/ADR-0382:补完保护集分级开关默认 True 从 registry 注入
    assert seen['grade_down'] is True


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
    """唯一载体:registry 可发现 decision_v2(default 栈退役后唯一注册;
    回退路径=git revert)。"""
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
    assert ids == ['decision_v2'], f'注册集应为唯一 decision_v2:{ids}'
    # 桥到的真身是独立实现
    strat = mgr.instantiate('decision_v2')
    assert isinstance(strat, DecisionV2Strategy)


def test_config_switch_field_exists() -> None:
    """C5 开关:CurrencyWarConfig 源码含 strategy_id 装载(切 line_v2/
    decision_v2;默认 default 不变——切换验收归步 5)。"""
    import inspect

    from sr_od.application.currency_war.currency_war_config import (
        CurrencyWarConfig,
    )
    assert "strategy_id" in inspect.getsource(CurrencyWarConfig)


# --- ⑦ F2 跨源共存锁(ADR-0316 槽位语义;W51 扩面批)--------------------------


def test_cross_source_mixed_actions_slot_stability() -> None:
    """F2(索引坐标系审查):decide_prep 五源拼装(演进/rollback/carry_gate/
    liquidity/arbiter 采纳集)的所有 bench_idx 都基于同一原始 state.bench
    生成,执行层按序消费——ADR-0316 槽位语义下任意发射序零漂移。

    本锁模拟真实跨源混合动作组(卖集合覆盖 carry_gate/liquidity/arbiter
    三个发射点,索引互不重叠、含夹层正料对照),逐动作 simulate 断言:
    ① 每个 SellBench 执行时命中的恰是生成期指向的槽(名字比对);
    ② 未卖槽内容逐槽不变(含紧缩模型下会被误删的对照槽);
    ③ 买入落首个空槽(= 最早被卖空的槽);占用数守恒。
    """
    from sr_od.application.currency_war.cw_state import (
        SellBench,
        bench_occupied,
        simulate,
    )
    # idx0 正料(保护,不卖);idx1 净0 散件(费1);idx2/idx3 正料夹层
    # (不卖——跨源卖集合互不重叠的对照);idx4 低费散件(费3);
    # idx5 引擎件(保护,不卖);idx6/idx7 压库散件(费2,arbiter 采纳卖)。
    st = GameState(
        round_num=4, gold=30, hp=80, level=5, plane=1,
        bench=[
            _bench('花火', faction='列车同行', slot=0),   # 正料
            _bench('阿格莱雅', faction='公司', slot=1, star=1),  # 净0 费1
            _bench('三月七', faction='列车同行', slot=2),   # 正料夹层
            _bench('瓦尔特', faction='列车同行', slot=3),   # 正料夹层
            _bench('娜塔莎', faction='公司', slot=4, star=1),  # 费3
            _bench('姬子·启行', faction='列车同行', slot=5),  # 引擎件
            _bench('千冶·刃', faction='公司', slot=6, star=1),  # 费2
            _bench('绯英', faction='公司', slot=7, star=1),  # 费2
        ],
        shop=[ShopCard(x=0, name='卡芙卡', faction='公司', cost=4)],
        board={},
    )
    _expected = [b.char_id if b is not None else None
                 for b in st.bench]
    # 跨源混合动作组(发射序 = 非降序乱序,模拟 liquidity 弱序选择序
    # [1,4] + carry_gate [0→最低] + arbiter 采纳 [6,7] 拼装后的原样序;
    # 槽位语义下发射序无语义负载——乱序也不漂移)
    acts = [
        SellBench(bench_idx=6, income=2),   # 源1(carry_gate 降保护集)
        SellBench(bench_idx=1, income=1),   # 源2(liquidity 净0 先)
        SellBench(bench_idx=4, income=3),   # 源2(liquidity)
        SellBench(bench_idx=7, income=2),   # 源3(arbiter 采纳 off_target)
        BuyCard(ShopCard(x=0, name='卡芙卡', faction='公司', cost=4),
                reason='d2_line_carry'),
    ]
    # ① 逐动作:每个 SellBench 执行时 bench[bench_idx] 仍是生成期那件
    working = st
    for a in acts:
        if isinstance(a, SellBench):
            cur = working.bench[a.bench_idx]
            assert cur is not None and cur.char_id == _expected[a.bench_idx], \
                (f'执行时 bench[{a.bench_idx}] 应是生成期指向的'
                 f'{_expected[a.bench_idx]},实得 {cur.char_id if cur else None}'
                 f'——索引漂移(F2)')
        working = simulate(working, a)
    # ② 未卖槽逐槽不变(含夹层正料/引擎件对照);卖槽中最早被卖空的
    # slot1 被买入占据(落首个空槽),其余卖槽(4/6/7)保持 None
    for i, e in enumerate(_expected):
        if i == 1:
            continue   # 首个空槽 = 买入落位(下方单独断言)
        if i in (4, 6, 7):
            assert working.bench[i] is None, f'槽 {i} 应已卖出置 None'
        elif e is None:
            assert working.bench[i] is None, f'原空槽 {i} 不应被占用'
        else:
            cur = working.bench[i]
            assert cur is not None and cur.char_id == e, \
                f'未卖槽 {i} 内容被移位({e} vs {cur.char_id if cur else None})'
    # ③ 买入落首个空槽(最早被卖空的槽 1);占用数守恒(8 卖 4 + 买 1)
    assert working.bench[1].char_id == '卡芙卡'
    assert bench_occupied(working.bench) == 5
    assert len(working.bench) == 9, '槽位表定长不变量'


def test_cross_source_index_drift_guard_arbiter_aligned() -> None:
    """arbiter index_drift 守卫(ADR-0316 对齐):working 态槽位被前序
    动作清空(置 None)时,后续候选同 idx 判定为 drift 拒绝——槽位
    语义下索引恒稳,守卫保「目标名与现槽名不一致仍拒」语义。"""
    from sr_od.application.currency_war.cw_state import SellBench
    from sr_od.application.currency_war.decision_v2.arbiter import (
        arbitrate,
    )
    from sr_od.application.currency_war.decision_v2.candidates import (
        Candidate,
    )
    st = GameState(
        round_num=4, gold=30, hp=80, level=5, plane=1,
        bench=[_bench('花火', faction='列车同行', slot=0),
               _bench('阿格莱雅', faction='公司', slot=1)],
        shop=[ShopCard(x=0, name='卡芙卡', faction='公司', cost=4)],
        board={},
    )
    sess = _locked_sess()
    sess.v2_round_key = (1, 4)
    # 两个候选引用同一槽 1(一个 off_target 卖一个 for_gold 卖),
    # 模拟前序源已把槽 1 清空后的陈旧提案——arbiter 应按 drift 拒
    cands = [
        (Candidate(action=SellBench(bench_idx=1), tag='off_target',
                   source='bench', breakdown_hint={'name': '阿格莱雅'}),
         1.0, {}),
        (Candidate(action=SellBench(bench_idx=1), tag='for_gold',
                   source='bench', breakdown_hint={'name': '阿格莱雅'}),
         1.0, {}),
    ]
    res = arbitrate(cands, st, sess, _REG)
    # 第一个候选接受并清空槽 1(working 置 None);第二个同 idx 被
    # index_drift 拒(working 槽已空→cur=None≠intended)
    sells = [r for r in res.log if r['tag'] in ('off_target', 'for_gold')]
    assert any(r['accepted'] for r in sells)
    assert any('index_drift' in (r['reject'] or '') for r in sells), \
        f'陈旧提案应被 index_drift 拒:{list(sells)}'
