# -*- coding: utf-8 -*-
"""test_cw_early_kernel 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w35_decision_v2_carrier: test_cw_w35_decision_v2_carrier.py
- w47_unification: test_cw_w47_unification.py
- w48_guards: test_cw_w48_guards.py
- w50_board_caliber: test_cw_w50_board_caliber.py
- w68_stall_root_fix: test_cw_w68_stall_root_fix.py
- w69_sell_channel: test_cw_w69_sell_channel.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== w35_decision_v2_carrier ====================

from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_intention import HoardTarget

from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
from sr_od.application.currency_war.kernel.cw_state import BenchChar, BuyCard, GameState, SellBench, ShopCard
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision.decision_v2.discipline import BloodAlarmTracker, assess_discipline, carry_gate_actions
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.decision.decision_v2.strategy import DecisionV2Strategy

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
    from sr_od.application.currency_war.kernel.cw_intention import IntentionState
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
    from sr_od.application.currency_war.decision.cw_strategy import CwStrategy
    assert DecisionV2Strategy.__bases__ == (CwStrategy,)
    assert not any(
        c.__name__ == 'DefaultCwStrategy' for c in DecisionV2Strategy.__mro__)
    assert DecisionV2Strategy.STRATEGY_ID == 'decision_v2'


def test_decision_v2_modules_do_not_import_line_strategy() -> None:
    """decision_v2 包源码零 line_strategy **import**(载体独立;文档性
    提及不算——正则只匹配 import 语句)。"""
    import re

    import sr_od.application.currency_war.decision.decision_v2.candidates as m_cand
    import sr_od.application.currency_war.decision.decision_v2.discipline as m_disc
    import sr_od.application.currency_war.decision.decision_v2.strategy as m_strat
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
    from sr_od.application.currency_war.decision.decision_v2.arbiter import _active_floor
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
    from sr_od.application.currency_war.decision.decision_v2.discipline import BLOOD_MARGIN_LOW_HP
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
    from sr_od.application.currency_war.kernel.cw_system_cards import engine_char_names
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
    from sr_od.application.currency_war.kernel.cw_state import bench_occupied, simulate
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
    from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
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

    import sr_od.application.currency_war.decision.decision_v2.strategy as m
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
    import sr_od.application.currency_war.decision.cw_strategy as _cw_mod
    from one_dragon.base.operation.application.plugin_info import PluginSource
    from sr_od.application.currency_war.decision.cw_strategy_manager import StrategyManager
    builtin = Path(_cw_mod.__file__).parents[1] / 'strategies'
    mgr = StrategyManager(ctx=None,
                          plugin_dirs=[(builtin, PluginSource.BUILTIN)])
    ids = [i.strategy_id for i in mgr.strategies]
    assert ids == ['decision_v2'], f'注册集应为唯一 decision_v2:{ids}'
    # 桥到的真身是独立实现
    strat = mgr.instantiate('decision_v2')
    assert isinstance(strat, DecisionV2Strategy)


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
    from sr_od.application.currency_war.kernel.cw_state import SellBench, bench_occupied, simulate
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
    from sr_od.application.currency_war.kernel.cw_state import SellBench
    from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate
    from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate
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


# ==================== w47_unification ====================

from types import SimpleNamespace as _w47_unification_SimpleNamespace

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY, V2_FAMILIES
from sr_od.application.currency_war.kernel.cw_deploy_logic import TRANSITION_TRAITS
from sr_od.application.currency_war.kernel.cw_evolution import _CARD_FACTION_TIER
from sr_od.application.currency_war.kernel.cw_intention import FAMILY_BOND_SIGNALS
from sr_od.application.currency_war.kernel.cw_line_defs import _CORE_TRIO
from sr_od.application.currency_war.kernel.cw_state import GameState as _w47_unification_GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w47_unification_StrategySession
from sr_od.application.currency_war.kernel.cw_system_cards import SYSTEM_CARDS, _card_factions, engine_char_names, system_judge_factions
from sr_od.application.currency_war.telemetry.cw_win_model import _DOT_POOL, _SEELE, _TRIO
from sr_od.application.currency_war.decision.decision_v2 import discipline
from sr_od.application.currency_war.decision.decision_v2.candidates import _buy_tag
from sr_od.application.currency_war.decision.decision_v2.scoring import _shop_has_engine_card
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY as _w47_unification_DEFAULT_REGISTRY

# --- ① judge_factions 字段(三处重复消除的单一源) --------------------------


def test_judge_factions_field_values() -> None:
    """卡→判据阵营映射的字段真值(希儿系双元组,首位=演进目标锚=量子侧)。"""
    assert SYSTEM_CARDS['xianzhou3'].judge_factions == ('仙舟',)
    assert SYSTEM_CARDS['dot2'].judge_factions == ('持续伤害',)
    assert SYSTEM_CARDS['train2'].judge_factions == ('列车同行',)
    assert SYSTEM_CARDS['seele'].judge_factions == ('量子同频', '贝洛伯格')
    # 兼容视图 _card_factions = 原样返回字段(不再有第二份映射)
    assert all(_card_factions(c) == c.judge_factions
               for c in SYSTEM_CARDS.values())


def test_evolution_card_faction_tier_derived() -> None:
    """cw_evolution._CARD_FACTION_TIER 从字段+FACTIONS 派生,值=原手编表
    (tier 阈值仍经注册表;第五张体系卡加入自动传导,无需改本表)。"""
    assert _CARD_FACTION_TIER == {
        'xianzhou3': ('仙舟', 3),
        'dot2': ('持续伤害', 2),
        'train2': ('列车同行', 2),
        'seele': ('量子同频', 2),
    }


# --- ② 引擎阵营/引擎名 helper(scoring 改读) ------------------------------


def test_engine_helpers_single_source() -> None:
    """阵营并集=五家(仙舟/列车/DOT/量子/贝);引擎名=铁三角+希儿;
    discipline.engine_char_names 与 cw_system_cards 同一函数(单一源)。"""
    assert system_judge_factions() == frozenset(
        {'仙舟', '列车同行', '持续伤害', '量子同频', '贝洛伯格'})
    assert engine_char_names() == frozenset(
        {'藿藿', '丹恒·饮月', '爻光', '希儿'})
    assert discipline.engine_char_names is engine_char_names


def _shop_state(names: list[str]) -> _w47_unification_GameState:
    return _w47_unification_GameState(
        plane=1, round_num=4, gold=30, level=5, board={}, bench=[],
        shop=[_w47_unification_SimpleNamespace(name=n, faction='', cost=2, x=0, star=1)
              for n in names], hp=100)


def test_shop_has_engine_card_reads_registry() -> None:
    """_shop_has_engine_card 经 helper 判:引擎名/判据阵营件命中,线外不命中。"""
    assert _shop_has_engine_card(_shop_state(['希儿']))            # 引擎名单卡
    assert _shop_has_engine_card(_shop_state(['卡芙卡']))          # DOT flow 件
    assert _shop_has_engine_card(_shop_state(['景元']))            # 仙舟件
    assert _shop_has_engine_card(_shop_state(['杰帕德']))          # 贝洛伯格件(希儿系判据阵营)
    assert not _shop_has_engine_card(_shop_state(['银枝']))        # 线外(星间旅人/群攻)
    assert not _shop_has_engine_card(_shop_state(['凑数散件']))    # 未注册名


# --- ③ cw_win_model 三字面量单一源 -----------------------------------------


def test_win_model_literals_derived() -> None:
    """_TRIO=注册表铁三角;_DOT_POOL=FACTIONS['持续伤害'] ≤2 费成员;
    _SEELE=seele 卡 engine_required(无第三处名字字面量)。"""
    assert set(_TRIO) == set(_CORE_TRIO) == {'藿藿', '丹恒·饮月', '爻光'}
    assert set(_DOT_POOL) == {'艾丝妲', '椒丘', '卡芙卡', '桑博'}
    assert _SEELE == '希儿'


# --- ④ Comp.bond_signal + FAMILY_BOND_SIGNALS 派生 -------------------------


def test_family_bond_signals_derived_from_comps() -> None:
    """crosswalk 值锁:7 家族→专属羁绊(与原手编表逐项一致)。"""
    assert FAMILY_BOND_SIGNALS == {
        '姬子列车': '列车同行',
        '圣杯双C': '命运圣杯',
        '欢愉族': '欢愉',
        '黄泉减益': '减益',
        '大黑塔群攻': '银河学者',
        '万敌燃血': '夜之半神',
        'DOT卡芙卡': '持续伤害',
    }


def test_bond_signal_field_consistency() -> None:
    """字段一致性:同家族各套 bond_signal 相同;希儿量子/白厄反甲=None
    (设计缺席:放大器不是独立伤害源 / 独立羁绊绑死单卡)。"""
    for comp in COMP_LIBRARY:
        if comp.family not in V2_FAMILIES:
            continue
        if comp.family in FAMILY_BOND_SIGNALS:
            assert comp.bond_signal == FAMILY_BOND_SIGNALS[comp.family], \
                f'{comp.name} 的 bond_signal 与家族表不一致'
        else:
            assert comp.bond_signal is None, \
                f'{comp.family} 不在信号表但 {comp.name}.bond_signal 非 None'
    assert next(c for c in COMP_LIBRARY
                if c.family == '希儿量子').bond_signal is None
    assert next(c for c in COMP_LIBRARY
                if c.family == '白厄反甲').bond_signal is None


# --- ⑤ TRANSITION_TRAITS 派生 + cw_sim alias -------------------------------


def test_transition_traits_derived_from_system_cards() -> None:
    """三羁绊对值锁(=SYSTEM_CARDS 排除 seele 后的(阵营,tiers[0]));
    cw_sim._TRANSITION_TRAITS 是同一对象(alias import,常量对双源消除)。"""
    assert set(TRANSITION_TRAITS) == {
        ('仙舟', 3), ('持续伤害', 2), ('列车同行', 2)}
    from sr_od.application.currency_war.sim import engine_p1 as cw_sim
    assert cw_sim.__dict__.get('_TRANSITION_TRAITS') is None, ('期 0b 锁改判(N7):alias 已随聚合族下沉删除,单一源=cw_deploy_logic 本体')


# --- ⑥ 顺手件:bond_fallback 门死条件清理(无行为变化) ---------------------


def _bf_card() -> _w47_unification_SimpleNamespace:
    """bond_fallback 合法件:1 费 + 与已有阵营同阵营 + 不在任何目标集。"""
    return _w47_unification_SimpleNamespace(name='凑档件', faction='仙舟罗浮', cost=1,
                           x=0, star=1)


def _bf_state() -> _w47_unification_GameState:
    # bench 留空(放同名件会先命中 copy 通道,污染 bond_fallback 断言)
    return _w47_unification_GameState(
        plane=1, round_num=4, gold=30, level=5,
        board={'仙舟罗浮': 1}, bench=[], shop=[], hp=100)


def test_bond_fallback_tag_without_direction_unchanged() -> None:
    """死条件清理后:无方向态同阵营件的标签裁决不变——bond_fallback 门
    在 ``_buy_tag`` 序中位于 pair 之后,无方向时同阵营件先被 pair 接管
    (原恒真条件的删除不改变标签优先序;有方向时方向阵营门把 pair
    拒掉,bond_fallback 才独占——见下一条)。"""
    sess = _w47_unification_StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    tag = _buy_tag(_bf_card(), _bf_state(), sess, _w47_unification_DEFAULT_REGISTRY)
    assert tag == 'pair'


def test_bond_fallback_fires_with_direction() -> None:
    """有方向(v3_hoard 锁线)时 bond_fallback 正常触发(方向阵营门拒 pair
    后的独占通道——与 ADR-0291 锁线用例同口径,此处直查 _buy_tag)。"""
    from sr_od.application.currency_war.kernel.cw_intention import HoardTarget, IntentionState
    sess = _w47_unification_StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    sess.v3_intention = ist
    sess.v3_hoard = HoardTarget(
        frozenset({'姬子·启行'}), frozenset(), 'locked')
    tag = _buy_tag(_bf_card(), _bf_state(), sess, _w47_unification_DEFAULT_REGISTRY)
    assert tag == 'bond_fallback'


# ==================== w48_guards ====================

from types import SimpleNamespace as _w48_guards_SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS

from sr_od.application.currency_war.kernel.cw_battle_calib import _target_comp_label

from sr_od.application.currency_war.sim.engine_p1 import simulate_p1 as _w48_guards_simulate_p1

from sr_od.application.currency_war.sim.checks.pool import check_engine_seed_not_resold

from sr_od.application.currency_war.sim.checks.ledger import check_no_same_round_buy_sell, check_oscillation_xp_cap
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w48_guards_BenchChar, BuyCard as _w48_guards_BuyCard, CompTransaction, DeployMove, FillSpec, GameState as _w48_guards_GameState, SellDeployed, ShopCard as _w48_guards_ShopCard, SwapDeploy, _recount_board, bench_occupied, deployed_occupied, iter_occupied_deployed, board_unique_key, mutate_bench_deployed, simulate


def _char(name: str, slot: int = 0, row: str = 'back') -> _w48_guards_BenchChar:
    """注册表真值构造 BenchChar(faction 单一源)。"""
    c = CHARACTERS[name]
    return _w48_guards_BenchChar(slot=slot, char_id=name,
                     faction=(c.factions or ['?'])[0],
                     position_pref=row)


def _dup_fixture() -> _w48_guards_GameState:
    """旧档 3 人在场 + bench 含「已上场同名副本」+ 异名件的单帧。"""
    names = [n for n, c in CHARACTERS.items()
             if (c.factions or [''])[0] == '贝洛伯格'][:3]
    assert len(names) == 3, '测试假设:贝洛伯格系 ≥3 人(注册表)'
    # ADR-0392:构造器入参 → __post_init__ pad 槽位表(与 simulate 出态同形)
    st = _w48_guards_GameState(gold=30, level=8,
                   deployed=[_char(nm, slot=i) for i, nm in enumerate(names)],
                   bench=[_char(names[0], slot=10), _char('青雀', slot=11)])
    st.board = _recount_board(st.deployed)
    return st


# ---------- 裁决 1:同名唯一性守卫(正反例) ----------

def test_tx_duplicate_on_board_rejected_whole():
    """【阻塞·反例】提案含「已上场同名」→ 整事务拒绝,状态零残留。"""
    st = _dup_fixture()
    dup_name = st.deployed[0].char_id
    tx = CompTransaction(deploy=[(0, 'back')], undeploy=[], sell=[],
                         reason='evolve')
    out = simulate(st, tx)
    log = out.action_log[-1]
    assert log['action'] == 'CompTransaction'
    assert log['result'] == 'rejected'
    assert 'duplicate_on_board' in log['reason']
    assert dup_name in log['reason']
    # 原子:无部分应用痕迹(拒绝记录本身除外)
    out.action_log = []
    st.action_log = []
    # ADR-0316:simulate 入口 pad bench 到定长 9,原子性对照只看占用内容
    assert bench_occupied(out.bench) == bench_occupied(st.bench)
    assert [c.char_id for c in out.bench if c] \
        == [c.char_id for c in st.bench if c]
    assert out.deployed == st.deployed and out.gold == st.gold


def test_tx_duplicate_via_undeploy_swap_ok():
    """【正例】先下再上同名(换血)不是重复——终态名单唯一即过。"""
    st = _dup_fixture()
    dup_name = st.deployed[0].char_id
    tx = CompTransaction(deploy=[(0, 'back')], undeploy=[0], sell=[],
                         reason='swap_same_name')
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'applied'
    names = [c.char_id for c in iter_occupied_deployed(out.deployed)]
    assert names.count(dup_name) == 1


def test_tx_fill_bench_duplicate_rejected():
    """【反例】fill bench 源指向已上场同名 → 整事务拒绝。"""
    st = _dup_fixture()
    dup_name = st.deployed[0].char_id
    tx = CompTransaction(deploy=[(1, 'back')], undeploy=[], sell=[],
                         fill=[FillSpec(source='bench', idx=0, row='back')],
                         reason='fill_dup')
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'duplicate_on_board' in out.action_log[-1]['reason']
    # 原子:fill/deploy 均未应用
    assert deployed_occupied(out.deployed) == 3 and dup_name in \
        {c.char_id for c in iter_occupied_deployed(out.deployed)}


def test_tx_fill_shop_duplicate_rejected():
    """【反例】shop 填位买后即上,与场上留任者同名 → 整事务拒绝。"""
    st = _dup_fixture()
    dup_name = st.deployed[0].char_id
    st.shop = [_w48_guards_ShopCard(x=0, faction='贝洛伯格', name=dup_name, cost=2)]
    tx = CompTransaction(deploy=[(1, 'back')], undeploy=[], sell=[],
                         fill=[FillSpec(source='shop', idx=0, row='back')],
                         reason='shop_dup')
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'duplicate_on_board' in out.action_log[-1]['reason']
    assert out.gold == 30 and len(out.shop) == 1   # 金/店槽均未消费


def test_swap_deploy_duplicate_rejected():
    """【反例】SwapDeploy 上场者与场上其余单位同名 → 拒绝(显式通道不旁路)。"""
    st = _dup_fixture()
    dup_name = st.deployed[0].char_id
    # bench[0] = deployed[0] 同名;换掉 deployed[1] → 场上会出现 dup_name×2
    out = simulate(st, SwapDeploy(1, 0, reason='swap'))
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'duplicate_on_board' in out.action_log[-1]['reason']
    assert dup_name in out.action_log[-1]['reason']
    # 【正例】换掉同名本尊(1 换 1)合法
    out2 = simulate(st, SwapDeploy(0, 0, reason='swap'))
    assert out2.action_log[-1]['result'] == 'applied'
    assert [c.char_id for c in iter_occupied_deployed(out2.deployed)]\
        .count(dup_name) == 1


def test_deploy_move_duplicate_rejected_and_logged():
    """【反例】单卡上场(DeployMove)同理拒绝 + 进 action_log。"""
    st = _dup_fixture()
    dup_name = st.deployed[0].char_id
    out = simulate(st, DeployMove(bench_idx=0, to_row='front',
                                  faction=st.bench[0].faction))
    log = out.action_log[-1]
    assert log == {'action': 'DeployMove', 'result': 'rejected',
                   'reason': f'duplicate_on_board:{dup_name}'}
    assert deployed_occupied(out.deployed) == 3 \
        and bench_occupied(out.bench) == 2   # 零残留(ADR-0392 占用数)
    # 【正例】异名上场照常
    out2 = simulate(st, DeployMove(bench_idx=1, to_row='back',
                                   faction=st.bench[1].faction))
    assert deployed_occupied(out2.deployed) == 4   # ADR-0392 占用数
    assert any(c.char_id == '青雀'
               for c in iter_occupied_deployed(out2.deployed))


def test_board_unique_key_trailblazer_and_unknown():
    """唯一性键:开拓者各形态归一;空 char_id(未知身份)不参与查重。"""
    tb_names = [n for n in CHARACTERS
                if n.startswith('开拓者')][:2]
    if len(tb_names) >= 2:
        assert board_unique_key(_char(tb_names[0])) == \
            board_unique_key(_char(tb_names[1]))
    assert board_unique_key(_w48_guards_BenchChar(slot=0, char_id='')) is None
    assert board_unique_key(_char('青雀')) == '青雀'


def test_mutate_bench_deployed_parity_guards():
    """运行时跟踪侧(mutate)与 simulate 同源守卫:重复/stale 均 no-op。"""
    bench = [_char('青雀', slot=0)]
    deployed = [_char('青雀', slot=1, row='front'),
                _char('符玄', slot=2, row='back')]
    # DeployMove 同名 → no-op
    mutate_bench_deployed(bench, deployed,
                          DeployMove(0, 'back', '量子同频'))
    assert bench_occupied(bench) == 1 \
        and deployed_occupied(deployed) == 2   # ADR-0392 占用数
    # SwapDeploy 上场者与场上其余同名 → no-op
    mutate_bench_deployed(bench, deployed, SwapDeploy(1, 0))
    assert deployed[1].char_id == '符玄' and bench[0].char_id == '青雀'
    # SellDeployed 代际不符 → no-op(相符 → 正常执行)
    mutate_bench_deployed(bench, deployed, SellDeployed(1, expect='别人'))
    assert deployed_occupied(deployed) == 2
    mutate_bench_deployed(bench, deployed, SellDeployed(1, expect='符玄'))
    assert deployed_occupied(deployed) == 1 \
        and deployed[0].char_id == '青雀'   # ADR-0392:置 None 计占用


# ---------- 裁决 2:代际校验(提案生成→应用之间 idx 已变) ----------

def test_tx_stale_fill_bench_expect_rejected():
    """fill bench 源 idx 指向内容与提案不符 → stale_proposal 整事务拒绝。"""
    st = _dup_fixture()
    tx = CompTransaction(deploy=[], undeploy=[], sell=[],
                         fill=[FillSpec(source='bench', idx=0, row='back',
                                        expect='符玄')],   # 实际指向 deployed[0] 同名
                         reason='stale')
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'stale_proposal' in out.action_log[-1]['reason']
    # 【正例】expect 与内容一致 → 通过(bench[1]=青雀;后置 bench 未迁移)
    tx2 = CompTransaction(deploy=[], undeploy=[],
                          sell=[(1, 'deployed')],
                          fill=[FillSpec(source='bench', idx=1, row='back',
                                         expect='青雀')],
                          reason='fresh')
    out2 = simulate(st, tx2)
    assert out2.action_log[-1]['result'] == 'applied'


def test_tx_stale_fill_shop_expect_rejected():
    """fill shop 源 idx 指向的卡与提案不符 → stale_proposal 拒绝。"""
    st = _dup_fixture()
    st.shop = [_w48_guards_ShopCard(x=0, faction='仙舟', name='符玄', cost=3)]
    tx = CompTransaction(deploy=[], undeploy=[], sell=[],
                         fill=[FillSpec(source='shop', idx=0, row='back',
                                        expect='白露')],
                         reason='stale_shop')
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'stale_proposal:fill_shop' in out.action_log[-1]['reason']
    assert out.gold == 30 and len(out.shop) == 1   # 金/槽不消费


def test_tx_stale_deploy_undeploy_sell_expect_rejected():
    """deploy/undeploy/sell 的 expect 序列与索引同序对齐,不符即拒绝。"""
    st = _dup_fixture()
    # deploy expect 不符
    tx = CompTransaction(deploy=[(1, 'back')], undeploy=[], sell=[],
                         expect_deploy=['符玄'], reason='stale_dep')
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'stale_proposal:deploy_bench' in out.action_log[-1]['reason']
    # undeploy expect 不符
    tx2 = CompTransaction(deploy=[(1, 'back')], undeploy=[1], sell=[],
                          expect_undeploy=['别人'], reason='stale_und')
    out2 = simulate(st, tx2)
    assert 'stale_proposal:undeploy' in out2.action_log[-1]['reason']
    # sell expect 不符
    tx3 = CompTransaction(deploy=[], undeploy=[], sell=[(1, 'bench')],
                          expect_sell=['别人'], reason='stale_sell')
    out3 = simulate(st, tx3)
    assert 'stale_proposal:sell_bench' in out3.action_log[-1]['reason']
    # 长度不对齐 → 拒绝(防半配对静默跳过)
    tx4 = CompTransaction(deploy=[(1, 'back')], undeploy=[], sell=[],
                          expect_deploy=[], reason='len')
    assert 'expect_deploy_len' in simulate(st, tx4).action_log[-1]['reason']


def test_swap_and_sell_stale_expect_rejected():
    """SwapDeploy/SellDeployed 的跨轮登记提案(谷底回滚)代际不符 → 拒绝。"""
    st = _dup_fixture()
    out = simulate(st, SwapDeploy(0, 0, reason='valley_rollback',
                                  expect_deployed='别人',
                                  expect_bench=st.bench[0].char_id))
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'stale_proposal' in out.action_log[-1]['reason']
    out2 = simulate(st, SellDeployed(0, reason='valley_rollback',
                                     expect='别人'))
    assert out2.action_log[-1]['result'] == 'rejected'
    assert 'stale_proposal' in out2.action_log[-1]['reason']
    # 【正例】expect 相符照常执行
    out3 = simulate(st, SellDeployed(0, reason='valley_rollback',
                                     expect=st.deployed[0].char_id))
    assert out3.action_log[-1]['result'] == 'applied'


def test_sim_redecide_after_shop_fill_tx_no_phantom():
    """裁决 2 根治面:事务 fill 消费店槽后同批陈旧 BuyCard 作废并重决策。

    桩:首批返回 [shop-fill 事务, 同卡 BuyCard](旧代码 = 幻影再买,
    phantom_rebuys 披露);修复后 break 重决策 → 幻影 0、同批买不执行。
    """

    class _TxFillStub:
        def __init__(self) -> None:
            self.fired = False

        def update_target(self, st, sess, screen) -> None:   # noqa: ARG002
            pass

        def decide_shop_screen(self, sess, screen):   # noqa: ARG002
            st = sess.shop_state_frame
            if not self.fired and st.shop:
                self.fired = True
                card = st.shop[0]
                tx = CompTransaction(
                    deploy=[], undeploy=[], sell=[],
                    fill=[FillSpec('shop', 0, 'back', expect=card.name)],
                    reason='probe_tx')
                return [tx, _w48_guards_BuyCard(card, reason='probe_phantom')]
            return []

    stub = _TxFillStub()
    res = _w48_guards_simulate_p1(11, strategy=stub, pool='fallback')
    assert stub.fired, '桩应在首轮点火'
    assert res.phantom_rebuys == 0, '店槽消费后陈旧买提案应作废重生成'
    # 事务确实 applied(重决策不是把事务也丢了)
    tx_rows = [row for row in res.ledger
               if any(a.get('__type__') == 'CompTransaction'
                      and a.get('result') == 'applied'
                      for a in row.get('actions') or [])]
    assert len(tx_rows) == 1


# ---------- 裁决 3:账本 target_comp 补 v3 意向 ----------

def test_target_comp_label_v3_fallback_and_v2_priority():
    """账本 target_comp = v3_intention.locked_comp(ADR-0336 后唯一
    源;旧 locked_line/bridge_id 优先分支随 LineStrategy 删除)。"""
    sess = _w48_guards_SimpleNamespace(locked_line=None, bridge_id=None,
                           v3_intention=_w48_guards_SimpleNamespace(locked_comp='仙舟3'))
    assert _target_comp_label(sess) == '仙舟3'
    # 旧 v1 字段不再被读(ADR-0336);意向缺失 → 空
    sess2 = _w48_guards_SimpleNamespace(locked_line='DOT2', bridge_id=None,
                            v3_intention=_w48_guards_SimpleNamespace(locked_comp='仙舟3'))
    assert _target_comp_label(sess2) == '仙舟3'
    sess3 = _w48_guards_SimpleNamespace(locked_line=None, bridge_id='列车2',
                            v3_intention=None)
    assert _target_comp_label(sess3) == ''
    sess4 = _w48_guards_SimpleNamespace(locked_line=None, bridge_id=None,
                            v3_intention=None)
    assert _target_comp_label(sess4) == ''


def test_sim_ledger_target_comp_reads_v3_intention():
    """sim 集成:decision_v2 型会话(v3 意向)的决策轮账本 target_comp 可读。"""

    class _V3Stub:
        def update_target(self, st, sess, screen) -> None:   # noqa: ARG002
            sess.v3_intention = _w48_guards_SimpleNamespace(phase='locked',
                                                locked_comp='仙舟3')

        def decide_shop_screen(self, sess, screen):   # noqa: ARG002
            return []

    res = _w48_guards_simulate_p1(3, strategy=_V3Stub(), pool='fallback')
    assert res.ledger, 'P1 至少 1 轮账本'
    assert all(row['target_comp'] == '仙舟3' for row in res.ledger)


# ---------- 裁决 4:三检查器 d2_ reason 归一化(误报+失明同修) ----------

def _row(actions: list[dict], rn: int = 1, level: int = 3) -> dict:
    return {'plane': 1, 'round_num': rn,
            'state': {'board': {}, 'level': level, 'bench': [],
                      'deployed': []},
            'actions': actions, 'sim': {}}


def _buy(name: str, reason: str) -> dict:
    return {'__type__': 'BuyCard', 'card': {'name': name, 'cost': 1},
            'reason': reason}


def _sell(name: str) -> dict:
    return {'__type__': 'SellBench', 'name': name}


def test_no_same_round_buy_sell_d2_normalization():
    """d2_ 前缀归一化:d2_engine_seed×2 同轮让位不报(误报修复);
    d2_pair 买后卖仍报(失明不引入);d2_copy 让位不报。"""
    # 误报修复:旧代码裸匹配 'engine_seed' 匹配不上 d2_engine_seed → 误报
    ok_seed = _row([_buy('青雀', 'd2_engine_seed'),
                    _buy('青雀', 'd2_engine_seed'),
                    _sell('青雀')])
    assert check_no_same_round_buy_sell([ok_seed]) == []
    # 豁免语境外的真实同轮买卖(d2_ 前缀)仍 0 容忍报出
    bad_pair = _row([_buy('青雀', 'd2_pair'), _sell('青雀')])
    v = check_no_same_round_buy_sell([bad_pair])
    assert v and '青雀' in v[0]
    # copy 让位豁免在 d2_ 前缀下同样生效
    ok_copy = _row([_buy('青雀', 'd2_copy_merge'), _sell('青雀')])
    assert check_no_same_round_buy_sell([ok_copy]) == []
    # 单张 d2_engine_seed 买后即卖(振荡主通道)仍报
    bad_seed = _row([_buy('青雀', 'd2_engine_seed'), _sell('青雀')])
    assert check_no_same_round_buy_sell([bad_seed])


def test_engine_seed_not_resold_d2_no_longer_blind():
    """失明修复:d2_engine_seed 买入 ≤2 轮内回卖此前裸匹配不上 → 恒 0;
    归一化后必须报出。"""
    rows = [
        _row([_buy('青雀', 'd2_engine_seed')], rn=1),
        _row([_sell('青雀')], rn=2),
    ]
    v = check_engine_seed_not_resold(rows)
    assert v and '青雀' in v[0]
    # 收集语境(同轮 ≥2)+ 次轮让位 → 不报
    rows_ok = [
        _row([_buy('青雀', 'd2_engine_seed'),
              _buy('青雀', 'd2_engine_seed')], rn=1),
        _row([_sell('青雀')], rn=2),
    ]
    assert check_engine_seed_not_resold(rows_ok) == []
    # >2 轮后卖出 → 窗口外不报
    rows_late = [
        _row([_buy('青雀', 'engine_seed')], rn=1),
        _row([_sell('青雀')], rn=4),
    ]
    assert check_engine_seed_not_resold(rows_late) == []


def test_oscillation_xp_cap_d2_normalization():
    """d2_engine_seed 收集语境不计振荡;d2_pair 振荡照计。"""
    # lv3:升级需 4 XP,30% = 1.2 → 1 次振荡(4 XP)即报
    ok = _row([_buy('青雀', 'd2_engine_seed'),
               _buy('青雀', 'd2_engine_seed'),
               _sell('青雀')])
    assert check_oscillation_xp_cap([ok]) == []
    bad = _row([_buy('青雀', 'd2_pair'), _sell('青雀')])
    v = check_oscillation_xp_cap([bad])
    assert v and '振荡' in v[0]


# ==================== w50_board_caliber ====================

from sr_od.application.currency_war.kernel.cw_bond_equips import equip_bond_grants, unit_bond_tags
from sr_od.application.currency_war.data.cw_chars import CHARACTERS as _w50_board_caliber_CHARACTERS
from sr_od.application.currency_war.kernel.cw_intention import CROSS_LINE_SKELETON
from sr_od.application.currency_war.obs.cw_observation import board_from_tracked
from sr_od.application.currency_war.kernel.cw_plugins import PLUGIN_LIBRARY, W16_MAJORITY_LINES, cross_line_skeleton

from sr_od.application.currency_war.kernel.cw_battle_calib import _deployable_depth
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w50_board_caliber_BenchChar, GameState as _w50_board_caliber_GameState, _recount_board as _w50_board_caliber_recount_board


def _w50_board_caliber_char(name: str, slot: int = 0, row: str = 'back',
          equips: list[str] | None = None) -> _w50_board_caliber_BenchChar:
    c = _w50_board_caliber_CHARACTERS[name]
    return _w50_board_caliber_BenchChar(slot=slot, char_id=name,
                     faction=(c.factions or ['?'])[0],
                     position_pref=row, equips=list(equips or []))


# ---------- 1. 装备羁绊贡献解析 ----------

def test_equip_bond_grants_registry_derived() -> None:
    """星徽/卡带贡献从注册表 effect 派生;普通装备零贡献。"""
    assert equip_bond_grants('列车同行星徽') == ('列车同行',)
    assert equip_bond_grants('仙舟星徽') == ('仙舟',)
    assert equip_bond_grants('欢愉星徽') == ('欢愉',)
    # 卡带系(骇客):欢愉卡带加入+成员计数+1;星核猎手卡带纯计数+1
    assert equip_bond_grants('欢愉卡带') == ('欢愉',)
    assert equip_bond_grants('欢愉卡带Max') == ('欢愉',)
    assert equip_bond_grants('星核猎手卡带') == ('星核猎手',)
    assert equip_bond_grants('星核猎手卡带Max') == ('星核猎手',)
    # 非羁绊装备
    assert equip_bond_grants('轮滑鞋') == ()
    assert equip_bond_grants('火力风暴潮') == ()
    assert equip_bond_grants('不存在装备') == ()


def test_equip_bond_grants_cover_all_badges() -> None:
    """22 张星徽全解析成功(注册表 category='星徽' 逐张非空)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
    badges = [e for e in EQUIPMENTS.values() if e.category == '星徽']
    assert len(badges) == 22
    for e in badges:
        assert equip_bond_grants(e.name), f'星徽 {e.name} 未解析出羁绊贡献'


# ---------- 2. unit_bond_tags(L1 全集 + L2 星徽)----------

def test_unit_bond_tags_fullset() -> None:
    """L1 全集:factions+flows+independent 都进标签(多羁绊每系都计)。"""
    # 布洛妮娅:factions 空 + flows 燃血 + independent 大守护者
    assert unit_bond_tags(_w50_board_caliber_char('布洛妮娅')) == ('燃血', '大守护者')
    # 白厄:仅独立羁绊救世主(复制效果不计人数,官方 trait 3005)
    assert unit_bond_tags(_w50_board_caliber_char('白厄')) == ('救世主',)
    # 银狼LV.999:阵营+流派+独立三层
    assert unit_bond_tags(_w50_board_caliber_char('银狼LV.999')) == ('星核猎手', '欢愉', '头号玩家')


def test_unit_bond_tags_unknown_and_trailblazer() -> None:
    """身份未知 → 空元组;开拓者按排归一(前排=记忆/后排=欢愉)。"""
    assert unit_bond_tags(_w50_board_caliber_BenchChar(slot=1, char_id='')) == ()
    assert unit_bond_tags(_w50_board_caliber_BenchChar(slot=1, char_id='?')) == ()
    assert unit_bond_tags(_w50_board_caliber_BenchChar(slot=1, char_id='不存在角色')) == ()
    assert unit_bond_tags(_w50_board_caliber_BenchChar(slot=1, char_id='', faction='量子同频')) == ()
    tb_names = [n for n in _w50_board_caliber_CHARACTERS
                if n.startswith('开拓者') and n != '开拓者·欢愉']
    assert tb_names   # 注册表有开拓者形态
    # 形态归一按 position_pref(欢愉形态 flows 欢愉;记忆形态另计)
    back = unit_bond_tags(_w50_board_caliber_char('开拓者·欢愉', row='back'))
    front = unit_bond_tags(_w50_board_caliber_char('开拓者·欢愉', row='front'))
    assert back and front and back != front


def test_unit_bond_tags_equip_grants() -> None:
    """L2 装备贡献:**星徽=额外增加一个羁绊(add-if-absent,成员穿不重复)**;
    卡带=计数+1(可双计)。用户口述 2026-08-28 分流语义。"""
    # 姬子·启行(列车+领航员)+ 列车同行星徽 → 列车计数 1(已是成员,星徽不重复)
    tags = unit_bond_tags(_w50_board_caliber_char('姬子·启行', equips=['列车同行星徽']))
    assert tags.count('列车同行') == 1
    assert tags.count('领航员') == 1
    # 非成员 + 星徽 → 变成员(+1)
    tags_nonmember = unit_bond_tags(_w50_board_caliber_char('佩拉', equips=['列车同行星徽']))
    assert tags_nonmember.count('列车同行') == 1
    # 银狼LV.999(欢愉 flow 成员)+ 欢愉卡带 → 欢愉 2(卡带可双计)
    tags2 = unit_bond_tags(_w50_board_caliber_char('银狼LV.999', equips=['欢愉卡带']))
    assert tags2.count('欢愉') == 2
    # 非成员佩戴欢愉卡带:加入即 +1(欢愉 1)
    tags3 = unit_bond_tags(_w50_board_caliber_char('符玄', equips=['欢愉卡带']))
    assert tags3.count('欢愉') == 1
    # 组合「卡带X+星徽X」(非成员):卡带授 X 后即「已有」,星徽 X 不再重复 → 仍 1
    tags_combo = unit_bond_tags(_w50_board_caliber_char('符玄', equips=['欢愉卡带', '欢愉星徽']))
    assert tags_combo.count('欢愉') == 1
    # 反序(星徽在前)同判:计数与穿戴顺序无关(P19 幂等性)
    tags_combo_rev = unit_bond_tags(_w50_board_caliber_char('符玄', equips=['欢愉星徽', '欢愉卡带']))
    assert tags_combo_rev.count('欢愉') == 1
    # 卡带自身可双计不受影响:成员两件欢愉系卡带 → 欢愉 3(自报 1 + 卡带 2)
    tags_tape2 = unit_bond_tags(_w50_board_caliber_char('银狼LV.999', equips=['欢愉卡带', '欢愉卡带Max']))
    assert tags_tape2.count('欢愉') == 3
    # 符玄(仙舟自报)+ 仙舟星徽:成员穿同羁绊星徽不重复(仍 1);不影响自报标签
    tags4 = unit_bond_tags(_w50_board_caliber_char('符玄', equips=['仙舟星徽']))
    assert tags4.count('仙舟') == 1
    # 星核猎手卡带:无条件 +1
    assert unit_bond_tags(
        _w50_board_caliber_char('姬子·启行', equips=['星核猎手卡带'])).count('星核猎手') == 1


# ---------- 3. 三侧同函数(实机/派生/检查)----------

def _three_sides_agree(dep: list[_w50_board_caliber_BenchChar]) -> None:

    from sr_od.application.currency_war.sim.checks.ledger import _board_agg_of_deployed_row
    row = {'state': {'deployed': [
        {'char_id': d.char_id, 'faction': d.faction, 'slot': d.slot,
         'position_pref': d.position_pref, 'equips': list(d.equips)}
        for d in dep]}}
    assert _w50_board_caliber_recount_board(dep) == board_from_tracked(dep) \
        == _board_agg_of_deployed_row(row)


def test_three_sides_same_function_fullset_with_equips() -> None:
    """实机 board_from_tracked / _recount_board / checks 镜像三处一致
    (同一 deployed——含星徽/卡带/独立羁绊/flows 构造)。"""
    dep = [
        _w50_board_caliber_char('银狼LV.999', slot=1, equips=['欢愉卡带']),
        _w50_board_caliber_char('姬子·启行', slot=2, equips=['列车同行星徽']),
        _w50_board_caliber_char('布洛妮娅', slot=3),
        _w50_board_caliber_char('白厄', slot=4),
        _w50_board_caliber_char('符玄', slot=5, equips=['仙舟星徽']),
    ]
    _three_sides_agree(dep)
    b = _w50_board_caliber_recount_board(dep)
    assert b['欢愉'] == 2          # 银狼999 flow 1 + 卡带 1(卡带可双计)
    assert b['列车同行'] == 1      # 姬子启行自报 1;成员穿星徽不重复
    assert b['仙舟'] == 1          # 符玄自报 1;成员穿星徽不重复
    assert b['救世主'] == 1        # 白厄独立羁绊
    assert b['燃血'] == 1 and b['大守护者'] == 1


def test_recount_unknown_fallback_and_deploymove_recount() -> None:
    """未识别身份回退 faction 单标签(空/'?' 不计);DeployMove 后
    board 走 _recount_board(不再 faction+=1 单标签)。"""
    dep = [_w50_board_caliber_char('希儿', slot=1), _w50_board_caliber_BenchChar(slot=2, char_id='', faction='量子同频'),
           _w50_board_caliber_BenchChar(slot=3, char_id='', faction='?')]
    b = _w50_board_caliber_recount_board(dep)
    assert b['量子同频'] >= 2      # 希儿全集 + 未识别兜底;? 不计
    from sr_od.application.currency_war.kernel.cw_state import DeployMove, simulate
    st = _w50_board_caliber_GameState()
    st.bench = [_w50_board_caliber_char('布洛妮娅')]
    st.deployed = []
    out = simulate(st, DeployMove(bench_idx=0, to_row='front', faction='燃血'))
    assert out.deployed[0].char_id == '布洛妮娅'
    assert out.board == {'燃血': 1, '大守护者': 1}   # 全集,非 {'燃血': 1}


def test_board_counts_of_is_recount_single_source() -> None:
    """cw_sim._board_counts_of = _recount_board(全集单一源,alias 语义)。"""

    from sr_od.application.currency_war.kernel.cw_battle_calib import _board_counts_of
    dep = [_w50_board_caliber_char('银狼LV.999', equips=['欢愉卡带'])]
    assert _board_counts_of(dep) == _w50_board_caliber_recount_board(dep)


# ---------- 4. Δ池桶键:Σboard 全集口径 ----------

def test_deployable_depth_is_sum_board() -> None:
    """_deployable_depth = Σboard(池语料同口径;双标签角色贡献 ≥2)。"""
    st = _w50_board_caliber_GameState()
    st.level = 4
    st.deployed = [_w50_board_caliber_char('银狼LV.999', slot=1), _w50_board_caliber_char('符玄', slot=2)]
    st.board = _w50_board_caliber_recount_board(st.deployed)
    assert _deployable_depth(st) == sum(st.board.values())
    assert _deployable_depth(st) >= len(st.deployed)   # 双标签放大
    st2 = _w50_board_caliber_GameState()
    st2.board = {}
    assert _deployable_depth(st2) == 0


# ---------- 5. W47 条2:W16 过半统计 + CROSS_LINE_SKELETON 派生 ----------

def test_w16_majority_lines_values() -> None:
    """W16 统计表值锁(数据搬运自 W16 报告 A2;家族键 ⊆ V2_FAMILIES)。"""
    from sr_od.application.currency_war.kernel.cw_comps import V2_FAMILIES
    for name, fams in W16_MAJORITY_LINES.items():
        assert fams and fams <= set(V2_FAMILIES), f'{name} 域外家族'
    assert W16_MAJORITY_LINES['瓦尔特'] == frozenset(
        {'姬子列车', '黄泉减益', 'DOT卡芙卡', '欢愉族', '希儿量子', '圣杯双C'})
    assert W16_MAJORITY_LINES['千冶·刃'] == frozenset(
        {'万敌燃血', '黄泉减益', 'DOT卡芙卡', '白厄反甲', '希儿量子',
         '姬子列车', '欢愉族', '圣杯双C'})
    assert W16_MAJORITY_LINES['缇宝'] == frozenset(
        {'大黑塔群攻', '万敌燃血', '希儿量子', '黄泉减益'})


def test_cross_line_skeleton_derived_matches_original_10() -> None:
    """派生名单 == 原 10 名快照(手写名单废弃;不等 = W16 数据错)。"""
    original = {
        '瓦尔特', '千冶·刃', '符玄', '星期日', '开拓者·记忆',
        '花火', '缇宝', '刻律德菈', '三月七', '藿藿',
    }
    assert set(cross_line_skeleton()) == original
    assert set(CROSS_LINE_SKELETON) == original
    # 排除项:姬子·启行(2 家族但= 姬子线 carry)、开拓者·欢愉(两线同族 1 键)
    assert '姬子·启行' not in CROSS_LINE_SKELETON
    assert '开拓者·欢愉' not in CROSS_LINE_SKELETON


def test_plugin_majority_lines_synced_with_w16() -> None:
    """插件库单卡条目 majority_lines 与 W16 表程序同步(单一写入口)。"""
    for name, fams in W16_MAJORITY_LINES.items():
        entry = PLUGIN_LIBRARY.get(name)
        if entry is not None:   # 千冶·刃/开拓者·记忆等骨架件不在插件池
            assert entry.majority_lines == fams, name
    # 原部分标注(瓦尔特只 {姬子列车})已被 W16 全集覆盖
    assert PLUGIN_LIBRARY['瓦尔特'].majority_lines == \
        W16_MAJORITY_LINES['瓦尔特']
    # 小羁绊条目不受同步(三C 手注口径)
    from sr_od.application.currency_war.kernel.cw_plugins import PLUGIN_DISABLE_MATRIX
    assert ('护盾2', '万敌燃血') in PLUGIN_DISABLE_MATRIX


# ==================== w68_stall_root_fix ====================

from types import SimpleNamespace as _w68_stall_root_fix_SimpleNamespace

from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_tracking
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w68_stall_root_fix_BenchChar
from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w68_stall_root_fix_StrategySession


def _padded_tracked() -> _w68_stall_root_fix_StrategySession:
    """构造 W68 现场形态:买牌后 pad_bench 污染 tracked 含 None。"""
    sess = _w68_stall_root_fix_StrategySession()
    sess.tracked_bench_chars = [
        _w68_stall_root_fix_BenchChar(slot=1, char_id='阿格莱雅', faction='昼之半神'),
        _w68_stall_root_fix_BenchChar(slot=2, char_id='飞霄', faction='狼狩'),
        None, None, None, None, None, None, None,   # pad 到定长 9
    ]
    sess.tracked_deployed = []
    return sess


def test_reconcile_survives_padded_tracked_bench() -> None:
    """W68 ①:tracked 含 None(槽位表 pad 态)→ reconcile 不崩且语义正确。

    SIFT 读到 bench 上 2 人(与 tracked 非 None 项一致)→ 无漂移写回;
    修复前此处 AttributeError(listcomp 撞 None)。
    """
    sess = _padded_tracked()
    bench = [_w68_stall_root_fix_BenchChar(slot=1, char_id='阿格莱雅', faction='昼之半神'),
             _w68_stall_root_fix_BenchChar(slot=2, char_id='飞霄', faction='狼狩')]
    # 不得 raise —— 修复点
    reconcile_tracking(sess, bench=bench, deployed=[], screen=None,
                       source='w68-lock')


def test_reconcile_drift_detected_with_padded_tracked() -> None:
    """W68 ①语义面:污染态下漂移检测仍工作(SIFT 读到 tracked 外的新人)。"""
    sess = _padded_tracked()
    bench = [_w68_stall_root_fix_BenchChar(slot=1, char_id='阿格莱雅', faction='昼之半神'),
             _w68_stall_root_fix_BenchChar(slot=2, char_id='飞霄', faction='狼狩'),
             _w68_stall_root_fix_BenchChar(slot=3, char_id='桑博', faction='虚无')]
    reconcile_tracking(sess, bench=bench, deployed=[], screen=None,
                       source='w68-lock')
    assert any(bc is not None and bc.char_id == '桑博'
               for bc in sess.tracked_bench_chars), '新人应被写回 tracking'


def test_operation_result_bool_pitfall_guard() -> None:
    """W68 ②:钉死 `OperationResult` 无 __bool__ 的坑——bool(FAIL) is True。

    这是cw_loop:925 守卫曾成死码的语言级根因;锁此事实防未来
    有人「简化」回 `if not result:`(同型坑在仓内 3 处正确范式都是
    `.execute().success`)。
    """
    from one_dragon.base.operation.operation_base import OperationResult
    fail = OperationResult(success=False, status='x')
    assert bool(fail) is True, \
        'OperationResult 无 __bool__:bool(FAIL)=True——失败判据必须用 .success'
    assert fail.success is False


# ==================== w69_sell_channel ====================

from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w69_sell_channel_BenchChar, SellBench as _w69_sell_channel_SellBench, bench_occupied as _w69_sell_channel_bench_occupied, mutate_bench_deployed as _w69_sell_channel_mutate_bench_deployed
from sr_od.application.currency_war.operations.prep.buy_cards import sell_guard_ok


def _mk_bench(names: list[str | None]) -> list[_w69_sell_channel_BenchChar | None]:
    """按槽位语义构造定长 9 槽表(下标=槽位;None=空槽)。"""
    out: list[_w69_sell_channel_BenchChar | None] = [None] * 9
    for i, n in enumerate(names):
        if n:
            out[i] = _w69_sell_channel_BenchChar(slot=i + 1, char_id=n, faction='散')
    return out


def test_sell_guard_ok_blocks_stale_slot():
    """锁 1(守卫,设计章2.5):生成期期望名 vs 执行期现槽名——不符=槽位已被
    前序动作消费(3合1 merge/前笔卖出)→ 拦截。"""
    assert sell_guard_ok('万敌', '万敌') is True      # 一致 → 放行
    assert sell_guard_ok('万敌', '银枝') is False     # 现槽已换人 → 拦截
    assert sell_guard_ok('万敌', None) is False       # 现槽已空(被消费)→ 拦截
    assert sell_guard_ok(None, '万敌') is False       # 生成期本就空 → 拦截
    assert sell_guard_ok('', '万敌') is False         # 生成期空名 → 拦截


def test_mutate_sell_bench_slot_semantics_no_shift():
    """锁 2(槽位语义执行,ADR-0316):乱序多笔 SellBench 置 None 不紧缩——
    其余槽位不动(无左移),任意发射序零漂移。"""
    bench = _mk_bench(['万敌', '银枝', '银狼', '娜塔莎', '赛飞儿', '飞霄'])
    deployed: list[_w69_sell_channel_BenchChar] = []
    # 乱序发射 [Sell(4), Sell(2)]:先卖 idx4(赛飞儿)→ 再卖 idx2(银狼)
    _w69_sell_channel_mutate_bench_deployed(bench, deployed, _w69_sell_channel_SellBench(bench_idx=4))
    _w69_sell_channel_mutate_bench_deployed(bench, deployed, _w69_sell_channel_SellBench(bench_idx=2))
    assert bench[4] is None, 'idx4 卖后置 None'
    assert bench[2] is None, 'idx2 卖后置 None'
    assert [c.char_id for c in bench if c is not None] == ['万敌', '银枝', '娜塔莎', '飞霄'], (
        '其余槽位不动(无左移)')
    assert _w69_sell_channel_bench_occupied(bench) == 4
