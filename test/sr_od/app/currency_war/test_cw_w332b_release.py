"""W332b 未成型期姿态批单帧锁(泄息通道 release / 预算三方合并 / 换线判据)。

设计=唯一规格:`.debug/temp/currency_war/w328_unformed_posture/DESIGN.md`。
锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① FLIP 谓词边界:辖区 [emergency_hp,∞) 归 FLIP、≤25 归应急;非末窗
  hp<40 持续兑现臂(FORM 辖域)/ 末窗投影臂 hp−boss_tax_p75<25
  (相位无关,保命义务不属成型分期);g>50 前置;假帧守卫=100 兜底帧
  (两个保真位皆 False)不评估,沿用真值帧放行(ADR-0428);
- ② 预算三方合并:FLIP 命中帧 release 覆盖 max(g−50, DP 预算×刷价);
  DP 已有授权不缩水;
- ③ slot 守卫第三路径:末窗 deployed<cap ∧ bench 非空 → rush_level 压掉,
  显式注入泄息预算(纯 level_up 帧取 g−50);非末窗/满员不辖;
- ④ spend_mode 状态机:'release' 为预留档位无生产者(负向网格锁);
  v1 _maybe_sell_for_interest 的 allin/level 跳卖契约保留(adaptive 对照);
- ⑤ cw_horizon 合并语义:level 分支不再丢弃 DP refresh_budget(随
  NodeGoal 下传);fallback NodeGoal refresh_budget=None(不参与合并);
- ⑨ release 活栈消费门(端到端,不再 monkeypatch 直塞):锁A 生产链
  可达(FLIP→decide_prep→session.v3_release/tag);锁B release 帧凑息向
  卖候选抑制(free_bench 腾位卖不受辖——slot 动机非凑息动机;演进替换
  事务卖不经候选生成器);锁D 息 EV 中性(spend_gate_active 判据);
  锁E V_D 的 C_dec 息损项中性(同判据,scoring.vd_refresh_score P2 分支);
- ⑥ release 义务预算的有界放行:累计 ≤ 预算 ∧ 花后 ≥ boss_floor;
- ⑦ latch 单窗:同轮内命中后不回退,跨轮失效;
- ⑧ 换线判据:E_rounds 有限性 / θ 滞回 / D_min 驻留 / 双 inf 维持 /
  末窗辖域门;
- ⑩ 成型帧末窗投影臂义务预算消费定向化:预算保留但只许花在找件
  (店内存在名集件)/升级(不经本门),盲刷拒;未成型帧与第三路径
  注入不辖。
"""
from __future__ import annotations

import dataclasses
import math
from types import SimpleNamespace

from sr_od.application.currency_war.cw_economy import NodeGoal
from sr_od.application.currency_war.cw_horizon import Posture
from sr_od.application.currency_war.cw_line_switch import (
    e_rounds,
    should_switch_e,
    switch_allowed,
)
from sr_od.application.currency_war.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.posture_release import (
    ReleaseDirective,
    authorize_release_refresh,
    evaluate_release,
    flip_hit,
    release_directive,
    slot_guard_blocks_level,
    wrap_posture,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY


def _state(*, gold: int = 60, hp: int = 30, plane: int = 1, r: int = 5,
           node: str = 'battle', level: int = 6,
           deployed_n: int = 5, bench_n: int = 1) -> GameState:
    return GameState(
        plane=plane, round_num=r, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2,
        deployed=[BenchChar(slot=20 + i, char_id=f'杂{i}', faction='公司',
                            star=1) for i in range(deployed_n)],
        bench=[BenchChar(slot=i, char_id=f'席{i}', faction='公司', star=1)
               for i in range(bench_n)]
        + [None] * (BENCH_CAPACITY - bench_n),
        shop=[], node_type=node)


# --- ① FLIP 谓词边界 ----------------------------------------------------------


def test_flip_emergency_zone_ceded() -> None:
    """hp≤25 应急辖区,FLIP 让位(双触发防护;[25,∞) 才归 FLIP)。"""
    s = StrategySession()
    assert not flip_hit(_state(hp=25, gold=60), s, _REG, 'FORM')
    assert flip_hit(_state(hp=26, gold=60), s, _REG, 'FORM')


def test_flip_requires_unformed_and_overflow() -> None:
    """前置:phase=FORM(未成型)∧ g>interest_floor;form_ok 帧不辖。"""
    s = StrategySession()
    assert not flip_hit(_state(gold=60), s, _REG, 'SPEND')   # 已成型满息
    assert not flip_hit(_state(gold=50), s, _REG, 'FORM')    # 无溢余段
    assert flip_hit(_state(gold=51), s, _REG, 'FORM')        # 溢余 1 金即辖


def test_flip_non_boss_arm_continuous() -> None:
    """非末窗持续兑现臂:报警带 hp<40 命中;hp≥40 不命中。"""
    s = StrategySession()
    assert flip_hit(_state(hp=39), s, _REG, 'FORM')
    assert not flip_hit(_state(hp=40), s, _REG, 'FORM')


def test_flip_boss_projection_arm() -> None:
    """末窗投影臂:hp−boss_tax_p75<emergency_hp(34)→ hp<59 命中。"""
    s = StrategySession()
    assert not flip_hit(_state(hp=45, node='battle'), s, _REG, 'FORM')
    assert flip_hit(_state(hp=45, node='boss'), s, _REG, 'FORM')
    assert flip_hit(_state(hp=58, node='boss'), s, _REG, 'FORM')
    assert not flip_hit(_state(hp=59, node='boss'), s, _REG, 'FORM')


def test_flip_unreadable_hp_frame_skipped() -> None:
    """假帧不评估:100 兜底帧(readable=False ∧ trusted=False,hp 为开局
    无真值的假 100)仍拒——ADR-0428 守卫收紧语义的既有锁,防回归。"""
    s = StrategySession()
    st = _state(hp=30, gold=60)
    st.hp_readable = False
    st.hp_trusted = False
    assert not flip_hit(st, s, _REG, 'FORM')


def test_flip_trusted_carried_hp_frame_hits() -> None:
    """ADR-0428 新行为锁:shop 开态帧 hp_readable=False 但 hp_trusted=True
    (hp=沿用的 last_hp_real 真值)→ 守卫放行,末窗投影臂正常命中。
    帧形态=实机局A r9 决策帧的判读字段(phase=FORM/hp=41/gold=75/
    node_type=boss/blood 上行窗):修前恒死于 hp_readable 守卫,导致 FLIP
    在实机商店帧结构性 0 触发(shop 开态血量区物理读不到 → readable 恒
    False);修后该帧必须触发。100 兜底帧仍拒见上锁(两臂在 hp=100 时
    本就不命中,无误触发面)。"""
    s = StrategySession()
    st = _state(hp=41, gold=75, plane=1, r=9, node='boss')
    st.hp_readable = False
    st.hp_trusted = True
    assert flip_hit(st, s, _REG, 'FORM')
    # 可信位是必要条件之一:trusted=False 的同字段兜底帧仍拒(双位齐查)
    st.hp_trusted = False
    assert not flip_hit(st, s, _REG, 'FORM')


def test_flip_scope_p12_only() -> None:
    """辖域 P1/P2 未成型期;P3 不辖(DESIGN §附5)。"""
    s = StrategySession()
    assert not flip_hit(_state(plane=3), s, _REG, 'FORM')


def test_flip_boss_projection_phase_independent() -> None:
    """末窗投影臂相位无关锁:boss 战后必入应急带是保命义务,不属成型
    分期——SPEND 相位(已成型)在 boss 窗帧同样命中。帧形态=实机观察局
    进店帧(phase=SPEND/hp=38/gold=67/r9/node=boss/投影 38−34=4<25),
    修前被 FORM 相位门短路致泄息通道结构性静默;修后必须命中。
    同帧投影不命中的对照(hp−34≥25 → hp=59)仍拒。"""
    s = StrategySession()
    st = _state(gold=67, hp=38, plane=1, r=9, node='boss')
    assert flip_hit(st, s, _REG, 'SPEND')
    st.hp = 59
    assert not flip_hit(st, s, _REG, 'SPEND')


def test_flip_continuous_arm_stays_form_scoped() -> None:
    """非末窗持续兑现臂零漂移锁:相位门只辖持续臂——非 boss 窗的
    SPEND 帧不因重排误入持续臂;FORM 同帧语义不变。"""
    s = StrategySession()
    assert not flip_hit(_state(gold=67, hp=38), s, _REG, 'SPEND')
    assert flip_hit(_state(gold=67, hp=38), s, _REG, 'FORM')   # hp<40 命中


def test_cap_full_flip_frame_keeps_level_up_rule2() -> None:
    """cap 满员第三路径验证(DESIGN §②规则2):相位无关重排后,SPEND
    相位的 cap 满员 boss 窗帧由 FLIP 命中承接——third_path=False
    (非 slot 守卫注入),wrap 后 level_up 保留(追级与泄息并存)。"""
    s = StrategySession()
    st = _state(gold=67, hp=38, plane=1, r=9, node='boss',
                deployed_n=6)
    assert not slot_guard_blocks_level(st)   # 满员:slot 守卫不触发
    posture = Posture(save=False, level_up=True, refresh_budget=6)
    d = release_directive(st, s, _REG, 'SPEND', posture)
    assert d is not None and d.third_path is False
    # 预算合并:max(溢余 17, DP 6×2=12) = 17
    assert d.budget_gold == 17 and d.rolls == 8
    p = wrap_posture(posture, d)
    assert p.tag == 'release' and p.level_up is True
    assert p.refresh_budget == 8


# --- ② 预算三方合并 -----------------------------------------------------------


def test_merge_release_covers_dp_budget() -> None:
    """合并表:FLIP 命中帧 budget = max(g−50, DP 预算×刷价),义务优先。"""
    s = StrategySession()
    st = _state(gold=72, hp=30)
    d = release_directive(st, s, _REG, 'FORM',
                          Posture(save=False, level_up=False, refresh_budget=6))
    assert d is not None
    assert d.budget_gold == 22            # g−50 > DP 6×2=12 → 22
    assert d.rolls == 11                  # 折刷数 ÷ 刷价 2
    assert d.third_path is False


def test_merge_dp_authority_not_shrunk() -> None:
    """DP 已有授权时不缩水:DP 预算 6×2=12 < g−50?反例帧 g=56(溢余 6)
    → max(6, 12)=12,DP 授权保持。"""
    s = StrategySession()
    st = _state(gold=56, hp=30)
    d = release_directive(st, s, _REG, 'FORM',
                          Posture(save=False, level_up=False, refresh_budget=6))
    assert d is not None and d.budget_gold == 12 and d.rolls == 6


def test_wrap_keeps_level_for_parallel() -> None:
    """cap 满员并存裁决:FLIP 帧保留 level_up(追级与泄息同一笔溢余预算)。"""
    d = ReleaseDirective(budget_gold=22, rolls=11)
    p = wrap_posture(Posture(save=True, level_up=True, refresh_budget=0), d)
    assert p.tag == 'release' and p.level_up is True
    assert p.refresh_budget == 11 and p.save is False


# --- ③ slot 守卫第三路径 -------------------------------------------------------


def test_third_path_injects_release_budget() -> None:
    """末窗 deployed<cap ∧ bench 有件:纯 level_up 帧显式注入 g−50,
    level_up 压掉(slot 边际本窗=0),不落 hold。"""
    s = StrategySession()
    st = _state(gold=60, node='boss', deployed_n=5, bench_n=1)
    assert slot_guard_blocks_level(st)
    d = release_directive(st, s, _REG, 'SPEND',   # 已成型也辖(独立于 FLIP)
                          Posture(save=False, level_up=True, refresh_budget=0))
    assert d is not None and d.third_path is True
    assert d.budget_gold == 10 and d.rolls == 5
    p = wrap_posture(Posture(save=False, level_up=True, refresh_budget=0), d)
    assert p.level_up is False and p.tag == 'release' and p.refresh_budget == 5


def test_third_path_not_outside_boss_window() -> None:
    """辖域=末窗:非 boss 窗的 level_up 帧维持原姿态(持续兑现归 FLIP 臂)。"""
    s = StrategySession()
    st = _state(gold=60, node='battle', deployed_n=5, bench_n=1)
    assert release_directive(st, s, _REG, 'SPEND',
                             Posture(save=False, level_up=True,
                                     refresh_budget=0)) is None


def test_third_path_not_when_cap_full() -> None:
    """cap 满员:slot 守卫不触发,第三路径(规则1/3 注入)不辖;末窗
    投影臂命中 → 由 FLIP 承接走规则2 并存裁决(third_path=False,
    level_up 保留,追级与泄息同轮并存)。修前该帧两臂双盲返回 None
    (泄息通道静默),本锁防回归到死区。"""
    s = StrategySession()
    st = _state(gold=60, node='boss', deployed_n=6)
    assert not slot_guard_blocks_level(st)
    posture = Posture(save=False, level_up=True, refresh_budget=6)
    d = release_directive(st, s, _REG, 'SPEND', posture)
    assert d is not None and d.third_path is False
    assert d.budget_gold == 12 and d.rolls == 6   # max(溢余10, DP 6×2=12)
    p = wrap_posture(posture, d)
    assert p.tag == 'release' and p.level_up is True


# --- ⑦ latch 单窗 --------------------------------------------------------------


def test_latch_within_round_no_flip_flop() -> None:
    """同轮命中后不回退(hp 抖动防姿态振荡);轮键变化自然失效。"""
    s = StrategySession()
    st = _state(hp=30, gold=60, r=5)
    p1, d1 = evaluate_release(st, s, _REG, 'FORM',
                              Posture(save=True, refresh_budget=0))
    assert d1 is not None and p1.tag == 'release'
    # 同轮 hp 抖出谓词带 → latch 保持
    st2 = _state(hp=45, gold=60, r=5)
    _p2, d2 = evaluate_release(st2, s, _REG, 'FORM',
                               Posture(save=True, refresh_budget=0))
    assert d2 is d1
    # 轮键变化 → 失效
    st3 = _state(hp=45, gold=60, r=6)
    _p3, d3 = evaluate_release(st3, s, _REG, 'FORM',
                               Posture(save=True, refresh_budget=0))
    assert d3 is None


# --- ⑥ release 义务预算有界放行 ------------------------------------------------


def test_release_budget_bounded_authorization() -> None:
    """累计刷金 ≤ 预算 ∧ 花后 ≥ boss_floor;预算耗尽即拒。"""
    s = StrategySession()
    s.v3_release = ReleaseDirective(budget_gold=22, rolls=11)
    s.v3_release_spent = 0
    assert authorize_release_refresh(s, 60, 2, _REG)
    assert s.v3_release_spent == 2
    s.v3_release_spent = 21
    assert not authorize_release_refresh(s, 60, 2, _REG)   # 21+2 > 22
    s.v3_release_spent = 20
    assert authorize_release_refresh(s, 60, 2, _REG)       # 恰好贴满
    s.v3_release_spent = 0
    assert not authorize_release_refresh(s, 11, 2, _REG)   # 花后 9 < boss_floor 10
    s.v3_release = None
    assert not authorize_release_refresh(s, 60, 2, _REG)


# --- ⑩ 成型帧末窗投影臂义务预算消费定向化 ---------------------------------------


def _form_boss_state(**kw) -> GameState:
    """成型帧末窗投影臂底座:SPEND 相位 + boss 窗 + hp−boss_tax_p75<25
    (hp=38 命中)+ 溢余段;其余同 _state 默认。"""
    return _state(gold=67, hp=38, plane=1, r=9, node='boss', **kw)


def _shop_card(name: str) -> object:
    from sr_od.application.currency_war.cw_state import ShopCard
    return ShopCard(name=name, faction='仙舟罗浮', cost=1, x=0, star=1)


def _target_name() -> str:
    from sr_od.application.currency_war.cw_system_cards import (
        engine_char_names,
    )
    return sorted(engine_char_names())[0]


def test_formed_projection_blind_refresh_denied() -> None:
    """定向化锁(盲刷拒):成型帧(phase=SPEND)末窗投影臂 FLIP 命中 →
    directive.directed_only=True;店内无可找件 → find_ok=False →
    authorize_release_refresh 拒(义务预算保留但盲刷不是合规消费)。"""
    s = StrategySession()
    d = release_directive(_form_boss_state(), s, _REG, 'SPEND',
                          Posture(save=False, level_up=False,
                                  refresh_budget=6))
    assert d is not None and d.third_path is False
    assert d.directed_only is True and d.find_ok is False
    s.v3_release = d
    s.v3_release_spent = 0
    assert not authorize_release_refresh(s, 60, 2, _REG)


def test_formed_projection_find_refresh_allowed() -> None:
    """定向化锁(找件放行):同帧店内出现名集件(目标件)→ find_ok=True →
    预算内有界放行(找件消费合规;升级不经本门不受辖)。"""
    s = StrategySession()
    st = _form_boss_state()
    st.shop = [_shop_card('无关件乙'), _shop_card(_target_name())]
    d = release_directive(st, s, _REG, 'SPEND',
                          Posture(save=False, level_up=False,
                                  refresh_budget=6))
    assert d is not None and d.directed_only is True and d.find_ok is True
    s.v3_release = d
    s.v3_release_spent = 0
    assert authorize_release_refresh(s, 60, 2, _REG)
    assert s.v3_release_spent == 2


def test_unformed_projection_not_directed() -> None:
    """辖域边界:未成型帧(phase=FORM)末窗投影臂命中 → directed_only=False
    → 盲刷照旧放行(定向化只辖成型帧——未成型帧泄息语义由设计承载,
    本批不扩权)。"""
    s = StrategySession()
    st = _state(gold=67, hp=38, plane=1, r=9, node='boss')   # shop=[]
    d = release_directive(st, s, _REG, 'FORM',
                          Posture(save=False, level_up=False,
                                  refresh_budget=6))
    assert d is not None and d.directed_only is False and d.find_ok is True
    s.v3_release = d
    s.v3_release_spent = 0
    assert authorize_release_refresh(s, 60, 2, _REG)


def test_third_path_directive_not_directed() -> None:
    """第三路径(slot 守卫注入)不辖定向化:其语义=防泄息通道静默关闭,
    定向化会重新造出静默面——third_path 帧盲刷照旧放行。"""
    s = StrategySession()
    st = _form_boss_state(deployed_n=5, bench_n=1)   # deployed<cap ∧ bench 有件
    assert slot_guard_blocks_level(st)
    d = release_directive(st, s, _REG, 'SPEND',
                          Posture(save=False, level_up=True,
                                  refresh_budget=0))
    assert d is not None and d.third_path is True
    assert d.directed_only is False and d.find_ok is True
    s.v3_release = d
    s.v3_release_spent = 0
    assert authorize_release_refresh(s, 60, 2, _REG)


# --- ④⑤ spend_mode 状态机与 cw_horizon 合并语义 ---------------------------------


def test_sell_for_interest_skip_list_contract(monkeypatch) -> None:
    """v1 动作消费者跳卖契约保留:allin 档不卖息凑档;adaptive 档同帧照卖
    (对照证明跳过来自档位而非别的门)。'release' 档映射已删(预留档位
    无生产者;活栈消费门=⑨ 锁B)。"""
    from sr_od.application.currency_war import cw_plan
    from sr_od.application.currency_war.cw_chars import CHARACTERS
    st = _state(gold=18, deployed_n=0, bench_n=1)
    _name, _ch = next((n, c) for n, c in CHARACTERS.items() if c.cost == 2)
    st.bench[0] = BenchChar(slot=1, char_id=_name,
                            faction=(_ch.factions or ('?',))[0], star=1)
    monkeypatch.setattr(cw_plan, 'get_node_goal',
                        lambda *a, **k: NodeGoal(6, 'allin'))
    actions: list = []
    cw_plan._maybe_sell_for_interest(st, actions, [], None, None)
    assert not [a for a in actions if type(a).__name__ == 'SellBench']
    monkeypatch.setattr(cw_plan, 'get_node_goal',
                        lambda *a, **k: NodeGoal(6, 'adaptive'))
    actions2: list = []
    cw_plan._maybe_sell_for_interest(st, actions2, [], None, None)
    assert [a for a in actions2 if type(a).__name__ == 'SellBench']


def test_spend_mode_release_has_no_producer() -> None:
    """锁C(负向网格):'release' 为预留档位,生产点 get_node_goal 恒不产。

    若未来有人在 horizon 层造出 release 生产者,本锁报警并把裁决拉回
    重新评估(单一源=decision_v2.posture_release 经 session 通道)。"""
    from sr_od.application.currency_war.cw_economy import get_node_goal
    for plane in (1, 2, 3):
        for r in (1, 5, 9):
            for gold in (8, 30, 55, 80):
                for level in (4, 6, 8):
                    for hp in (30, 80):
                        g = get_node_goal(plane, r, gold=gold, level=level,
                                          hp=hp)
                        assert g.spend_mode != 'release', (plane, r, gold,
                                                           level, hp)


def test_horizon_level_branch_carries_dp_budget() -> None:
    """③生产缺陷修复:level 分支不再即席返回丢弃 DP refresh_budget。"""
    from sr_od.application.currency_war.cw_economy import get_node_goal
    g = get_node_goal(1, 1, gold=8, level=3, hp=80)   # DP 说升(P1 早段便宜)
    assert g.spend_mode == 'level'
    assert isinstance(g.refresh_budget, int) and 0 <= g.refresh_budget <= 6


def test_fallback_node_goal_budget_none() -> None:
    """fallback NodeGoal refresh_budget=None(无 DP 信息,不参与合并)。"""
    from sr_od.application.currency_war.cw_economy import get_node_goal
    g = get_node_goal(1, 1)   # 部分传参 → 先验 fallback
    assert g.spend_mode == 'adaptive' and g.refresh_budget is None


def test_plan_merges_dp_budget_into_refresh_cap(monkeypatch) -> None:
    """三方合并消费侧(许可取交):DP 预算 1 < _refresh_cap 2 → 合并后 1。"""
    from sr_od.application.currency_war import cw_plan
    monkeypatch.setattr(cw_plan, 'get_node_goal',
                        lambda *a, **k: NodeGoal(6, 'adaptive',
                                                 refresh_budget=1))
    st = _state(gold=60, hp=80, deployed_n=0, bench_n=0)
    st.bench = [None] * BENCH_CAPACITY
    acts = cw_plan.plan(st, None, [], rng=None, target_comp=None,
                        reactive=True)
    assert sum(1 for a in acts if isinstance(a, cw_plan.RefreshShop)) <= 1


# --- ⑧ 换线判据 -----------------------------------------------------------------


def _reg(theta: float = 1.0, delta: float = 0.15, dwell: int = 2):
    return dataclasses.replace(DEFAULT_REGISTRY,
                               line_switch_theta=theta,
                               line_switch_debias_delta=delta,
                               line_switch_min_dwell=dwell)


def test_switch_theta_hysteresis() -> None:
    """θ 滞回:去偏后差距不足 θ 不换。e_cur=4.54/e_alt=4.3:k=1.15 →
    4.3×1.15+1=5.945 < 5.221?否 → 保持。"""
    ok, why = should_switch_e(4.54, 4.3, 5, _reg())
    assert not ok and why == 'theta'


def test_switch_margin_passes_with_dwell() -> None:
    """差距跨过 θ 且驻留 ≥D_min → 换。e_alt=3.0/e_cur=4.54:
    3×1.15+1=4.45 < 5.221 → ok。"""
    ok, why = should_switch_e(4.54, 3.0, 2, _reg())
    assert ok and why == 'ok'


def test_switch_dwell_gate() -> None:
    """D_min 驻留门:不足驻留即使大幅占优也不换(压振荡)。"""
    ok, why = should_switch_e(4.54, 1.0, 1, _reg())
    assert not ok and why.startswith('dwell')


def test_switch_both_inf_hold() -> None:
    """退化情形双 inf → 维持原线。"""
    ok, why = should_switch_e(math.inf, math.inf, 5, _reg())
    assert not ok and why == 'alt_inf'


def test_switch_cur_inf_alt_finite() -> None:
    """原线静态不可达(inf)+ 备选有限 + 驻留足 → 换(不等式恒真)。"""
    ok, why = should_switch_e(math.inf, 6.0, 2, _reg())
    assert ok and why == 'ok'


def test_e_rounds_finite_for_transition_faction() -> None:
    """E_rounds 有限性:过渡阵营缺件帧 → 0<E<inf;p̄=0 线 → inf。"""
    comp = SimpleNamespace(form_tiers={'列车同行': 2})
    st = _state(gold=60, hp=80)
    e = e_rounds(comp, st, _REG)
    assert 0.0 < e < math.inf
    ghost = SimpleNamespace(form_tiers={'不存在阵营': 2})
    assert e_rounds(ghost, st, _REG) == math.inf


def test_switch_scope_excludes_window_end() -> None:
    """辖域门:位面前中段可换,末 3 轮禁换(P1 r7-9;设计内辖域声明)。"""
    s = StrategySession()
    assert switch_allowed(_state(r=6), s)
    assert not switch_allowed(_state(r=7), s)


# --- ⑨ release 活栈消费门(端到端;registry.release_spend_gate_enabled) --


def _gate_reg(on: bool):
    return dataclasses.replace(DEFAULT_REGISTRY,
                               release_spend_gate_enabled=on)


def _gate_session() -> StrategySession:
    """带 release 态的 session(判据单一源=session.v3_release,同生产链
    evaluate_release 的写入形态;开关臂对照=registry flag,两臂同带
    release 态)。"""
    s = StrategySession()
    s.v3_release = ReleaseDirective(budget_gold=8, rolls=4)
    return s


def test_release_chain_end_to_end_reachable() -> None:
    """锁A(生产链可达性,端到端):FLIP 命中态直接驱动 decide_prep,
    session 通道活(tag='release' ∧ 义务预算≥g−50 下界)——全程不 mock
    生产者(旧两锁 monkeypatch 直塞只锁映射,不锁可达性,已删)。"""
    from sr_od.application.currency_war.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    s = StrategySession()
    st = _state(gold=58, hp=35, r=5)   # FORM ∧ g>50 ∧ hp<40 持续兑现臂
    DecisionV2Strategy().decide_prep(st, s, None)
    assert getattr(s, 'v3_dp_posture', None) is not None
    assert s.v3_dp_posture.posture.tag == 'release'
    d = getattr(s, 'v3_release', None)
    assert d is not None and d.budget_gold >= 8   # g−50 溢余下界


def test_release_frame_blocks_interest_motivated_sells() -> None:
    """锁B(release 帧不卖息凑档):凑息向卖候选(off_target/for_gold)
    在 release 门开帧不生成;开关关同帧照产(对照证明抑制来自门本身)。
    帧取 hp=80 非应急(FLIP 帧语义由 session.v3_release 承载,与 hp 独立
    ——latch 窗内 hp 重读抖动即此形状)。"""
    from sr_od.application.currency_war.decision_v2.candidates import (
        generate_candidates,
    )
    st = _state(gold=58, hp=80, deployed_n=6)   # 板满:free_bench 不触发
    s_on = _gate_session()
    cands_on = generate_candidates(st, s_on, _gate_reg(True))
    assert not [c for c in cands_on
                if type(c.action).__name__ == 'SellBench']
    s_off = _gate_session()
    cands_off = generate_candidates(st, s_off, _gate_reg(False))
    assert [c for c in cands_off if type(c.action).__name__ == 'SellBench']


def test_release_gate_spares_free_bench_sell() -> None:
    """锁B 辖区边界:free_bench 腾位让位是 slot 动机非凑息动机,release
    门开仍生成(演进替换事务卖不经候选生成器,同条注释在
    candidates._release_sell_gate)。bench 件须为方向件——bench 满时
    非方向件先被 off_target 档截住(优先序),走不到腾位档;方向件用
    session.v3_hoard.char_targets 承载(体系引擎件受 sole_engine 守卫
    ≤2 份拦截,不适合本帧)。"""
    from sr_od.application.currency_war.decision_v2.candidates import (
        generate_candidates,
    )
    st = _state(gold=58, hp=80, deployed_n=6, bench_n=BENCH_CAPACITY)
    st.bench[0] = BenchChar(slot=0, char_id='方向件', faction='公司', star=1)
    s_on = _gate_session()
    s_on.v3_hoard = SimpleNamespace(char_targets=('方向件',))
    cands = generate_candidates(st, s_on, _gate_reg(True))
    assert any(c.tag == 'free_bench'
               and type(c.action).__name__ == 'SellBench' for c in cands)


def test_release_gate_neutralizes_interest_ev() -> None:
    """锁D(息 EV 中性):release 门开帧 score_state 息项计 0(卖出涨息
    加分/跌破平台扣分的计值原料被拆);同 registry 无 release 态照计
    (对照)。ADR-0332 息崖平滑块用同一判据 spend_gate_active 旁路
    (scoring.score_candidate),不在本锁重复搭帧断言。"""
    from sr_od.application.currency_war.decision_v2.scoring import score_state
    st = _state(gold=60, hp=80)
    sc_on = score_state(st, _gate_reg(True), _gate_session())
    assert sc_on['interest'] == 0.0
    sc_off = score_state(st, _gate_reg(True), StrategySession())
    assert sc_off['interest'] > 0.0


def _vd_p2_frame():
    """P2 入场 release 帧(卡芙卡 2费@lv6 j=2,金 80,刷价 5,rb=6):
    金 80 花 E×5 穿息档 → Δinterest≠0,V_D 的 C_dec 息损项有非零原料。"""
    from sr_od.application.currency_war.cw_comps import get_comp
    from sr_od.application.currency_war.cw_intention import IntentionState
    from sr_od.application.currency_war.decision_v2.ev import RoundPosture
    s = StrategySession()
    s.v3_release = ReleaseDirective(budget_gold=8, rolls=4)
    s.v3_intention = IntentionState(phase='locked', locked_comp='DOT队')
    s.target_comp = get_comp('DOT队')
    s.v3_mode = 'economy'
    s.v3_dp_posture = RoundPosture(
        (2, 1), Posture(save=False, level_up=True, refresh_budget=6))
    st = GameState(
        plane=2, round_num=1, gold=80, level=6, hp=69,
        shop_refresh_cost=5,
        deployed=[BenchChar(slot=9 + i, char_id=f'杂件{i}',
                            faction='公司', star=1) for i in range(4)],
        bench=[BenchChar(slot=i, char_id='卡芙卡', faction='公司', star=1)
               for i in range(2)]
        + [None] * (BENCH_CAPACITY - 2),
        shop=[], node_type='battle')
    return st, s


def test_release_gate_neutralizes_vd_c_dec_interest_loss() -> None:
    """锁E(V_D 的 C_dec 息损项中性,同锁D判据):release 门开帧
    vd_refresh_score 的 P2 分支息损项(Δinterest×min(R,recovery))计 0
    ——泄息义务帧的 D 罚分与花钱义务对冲(D 候选被息账让位=泄息意图
    在 D 通道被对冲);流动性成本 ρ·spend(真实刷金代价)不在辖域。
    对照=同 registry 无 release 态(session 判据单一源,v3_release=None)
    息损项照计,两臂分值差=息损项对拍值(测试本地复算,禁从被测函数
    借值)。"""
    from sr_od.application.currency_war.cw_shop_odds import (
        expected_refreshes_for_card,
    )
    from sr_od.application.currency_war.decision_v2.ev import (
        cross_plane_remaining_nodes,
    )
    from sr_od.application.currency_war.decision_v2.scoring import (
        vd_refresh_score,
    )
    st, s_on = _vd_p2_frame()
    vd_on = vd_refresh_score(st, s_on, _gate_reg(True))
    _, s_off = _vd_p2_frame()
    s_off.v3_release = None   # 对照臂:无 release 态(判据单一源关闭)
    vd_off = vd_refresh_score(st, s_off, _gate_reg(True))
    assert vd_on is not None and vd_off is not None
    # 门辖帧息损项=0:ρ=0(缺省)下 C_dec 全项为 0,V_D=benefit^P2
    assert vd_on > vd_off, (vd_on, vd_off)
    e = expected_refreshes_for_card(6, 2, target_star=2, owned=2)
    spend = e * (st.shop_refresh_cost or 2)
    d_int = (min(st.gold // 10, _REG.interest_cap)
             - min(int(st.gold - spend) // 10, _REG.interest_cap))
    r = cross_plane_remaining_nodes(st)
    loss_term = max(0, d_int) * min(r, _REG.vd_p2_recovery_rounds)
    assert loss_term > 0.0
    assert abs((vd_on - vd_off) - loss_term) < 1e-6, (vd_on, vd_off,
                                                      loss_term)
