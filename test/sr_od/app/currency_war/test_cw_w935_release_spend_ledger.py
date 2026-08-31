"""W935 返修:release 帧实花账全渠道入账锁(ADR-0503 确认门②数据源)。

病灶=实机复盘 g_20260831_053546(.debug/temp/currency_war/replay/
matches/reviews/ 同名 md,开臂三查节):sess_release_spent 只在
authorize_release_refresh(刷新授权)逐笔扣账,买牌/升级走各自授权链
不触账——r4P2 实际实花 5(升级 4+买艾丝妲 1)记 0(漏记)、r5P2 买 4
(银狼 3+椒丘 1)记 2(只计刷新,错记)。修法=仲裁收尾
(build_spend_receipt 无条件调用点)对 release 帧(v3_release 非 None)
按采纳动作汇总非刷新渠道实花(_accrue_release_frame_spend);
RefreshShop 不计(授权门已逐笔扣,再计=双记)。

**语义定位(编排者裁决 2026-08-31)**:这是**行为修复**而非纯记账——
入账使买/升消费计入 authorize_release_refresh 预算约束,预算门从失明
(旧形态:预算外继续获刷新授权=超授权滥刷)恢复为如实执行 ADR-0503
设计预算。开臂证据(W933/W939)取得于门失明形态,预算执行后的改善
保持由 armed 态 A/B 实证(w935_budget_enforce_ab/)。

fixture 数据=match 2 真实遥测帧(actions 构造取该帧复盘记录的动作与
金值,不伪造金额)。

锁契约(不锁分布数值,锁单帧记账与授权行为):
- ① r4P2 混合轮(升级+买,无刷新):spent=5(修复前记 0 的洞);
- ② r5P2 刷+买混合轮:刷新经授权门记 2 + 回执汇总买 4 → spent=6
  (修复前记 2 的洞);刷新动作出现在 actions 不双记;
- ③ 非 release 帧(v3_release=None)有买/升动作:不记账(零漂移);
- ④ 回执契约无条件生效(原开关 spend_receipt_gate_enabled 已随除开关批
  删除):记账分支独立于回执契约(release 帧无授权包,回执恒 None,
  记账照常);
- ⑤ 同轮跨段累计:两段各自汇总,spent 为轮内累计(决策帧采样语义);
- ⑥ cost 缺失兜底与空动作;
- ⑦ 预算门全渠道执行:买/升入账侵蚀刷新授权预算(行为修复语义钉)。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.posture import Posture
from sr_od.application.currency_war.decision.decision_v2.posture_release import (
    build_spend_receipt,
    evaluate_release,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    LevelUp,
    RefreshShop,
    ShopCard,
)

_REG_ON = dataclasses.replace(DEFAULT_REGISTRY, crisis_release_enabled=True)


def _state(*, gold: int = 90, hp: int = 25, plane: int = 2, r: int = 4,
           level: int = 6) -> GameState:
    """危机溢余帧构造(r4P2 形态:hp=25 应急带,g=105>R*→溢余)。"""
    return GameState(
        plane=plane, round_num=r, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2,
        deployed=[BenchChar(slot=20 + i, char_id=f'杂{i}', faction='公司',
                            star=1) for i in range(5)],
        bench=[BenchChar(slot=0, char_id='席0', faction='公司', star=1)]
        + [None] * (BENCH_CAPACITY - 1),
        shop=[], node_type='battle')


def _crisis_sess(state: GameState) -> StrategySession:
    """带 crisis 指令的 session(经 evaluate_release 真实通路装配,
    预算=min(溢余, REFRESH_ROLL_CAP×刷价);posture 键对齐)。"""
    from sr_od.application.currency_war.decision.decision_v2.ev import (
        RoundPosture,
    )
    s = StrategySession()
    dp = RoundPosture(
        (state.plane, state.round_num),
        Posture(save=True, level_up=False, refresh_budget=0))
    s.v3_dp_posture = dp
    _, d = evaluate_release(state, s, _REG_ON, 'FORM', dp.posture)
    assert d is not None and d.reason == 'crisis'
    return s


def _card(name: str, cost: int) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


# --- ① r4P2 混合轮(升级+买,无刷新):修复前记 0 的漏记洞 ---------------------


def test_r4p2_levelup_plus_buy_accrued() -> None:
    """match 2 r4P2 真实帧:升级 6→7(4金,static_ev)+买艾丝妲 1★(1金)
    → spent=5(复盘:实际实花 5,修复前记 0)。"""
    st = _state()
    sess = _crisis_sess(st)
    actions = [LevelUp(cost=4, auth_basis='static_ev'),
               BuyCard(card=_card('艾丝妲', 1), reason='board_focus')]
    build_spend_receipt(st, sess, _REG_ON, actions, [])
    assert sess.v3_release_spent == 5


# --- ② r5P2 刷+买混合轮:授权门逐笔 + 回执汇总不双记 ---------------------------


def test_r5p2_refresh_plus_buy_no_double_count() -> None:
    """match 2 r5P2 真实帧:刷新 2 金经 authorize_release_refresh 授权门
    逐笔记 2;随后买银狼(3)+椒丘(1)经回执汇总 → spent=6(复盘:
    实际实花 6,修复前记 2)。刷新动作同时出现在 actions 不双记
    (授权门已逐笔扣,汇总分支只辖买/升)。"""
    from sr_od.application.currency_war.decision.decision_v2.posture_release import (
        authorize_release_refresh,
    )
    st = _state(gold=98)   # 息档截断门放行余量内(98 刷 2 → 96 不跨档)
    sess = _crisis_sess(st)
    assert sess.v3_release.budget_gold >= 2
    assert authorize_release_refresh(sess, st.gold, 2, _REG_ON)
    assert sess.v3_release_spent == 2          # 授权门逐笔(既有口径)
    actions = [BuyCard(card=_card('银狼LV.999', 3), reason='line'),
               BuyCard(card=_card('椒丘', 1), reason='line'),
               RefreshShop(cost=2)]            # 已扣账的刷新不双记
    build_spend_receipt(st, sess, _REG_ON, actions, [])
    assert sess.v3_release_spent == 6


# --- ③ 非 release 帧:零漂移 --------------------------------------------------


def test_non_release_frame_not_accrued() -> None:
    """v3_release=None(非 release 帧)有买/升动作:不记账——记账分支
    辖域=release 帧,常规帧账面零改动(守卫=判据单一址)。"""
    st = _state()
    sess = StrategySession()
    actions = [LevelUp(cost=4), BuyCard(card=_card('艾丝妲', 1))]
    build_spend_receipt(st, sess, _REG_ON, actions, [])
    assert getattr(sess, 'v3_release_spent', 0) == 0


# --- ④ 与回执契约互不辖 -------------------------------------------------------


def test_accrual_independent_of_receipt_gate() -> None:
    """回执契约无条件生效(原开关已除,ADR-0504;release 帧无授权包 →
    回执恒 None)记账照常:记账分支与回执契约互不辖(两契约独立)。"""
    st = _state()
    sess = _crisis_sess(st)
    actions = [LevelUp(cost=4), BuyCard(card=_card('艾丝妲', 1))]
    r = build_spend_receipt(st, sess, _REG_ON, actions, [])
    assert r is None                            # release 帧无授权包(既有语义)
    assert sess.v3_release_spent == 5           # 记账分支独立生效


# --- ⑤ 轮内跨段累计 -----------------------------------------------------------


def test_round_cumulative_across_segments() -> None:
    """同轮多决策段(re-decide):各段汇总自然累计(决策帧采样读到
    「轮内截至采样时点」的运行累计;每轮入口由 strategy 重置清零)。"""
    st = _state()
    sess = _crisis_sess(st)
    build_spend_receipt(st, sess, _REG_ON,
                        [BuyCard(card=_card('艾丝妲', 1))], [])
    build_spend_receipt(st, sess, _REG_ON, [LevelUp(cost=4)], [])
    assert sess.v3_release_spent == 5


# --- ⑥ cost 缺失兜底与空动作 --------------------------------------------------


def test_missing_cost_fallback_and_empty_actions() -> None:
    """cost=None 按 3 兜底(与回执 buy 渠道同口径);空动作/无消费动作
    不触账(账面保持原值,不无谓写入)。"""
    st = _state()
    sess = _crisis_sess(st)
    build_spend_receipt(st, sess, _REG_ON,
                        [BuyCard(card=_card('未知牌', None))], [])
    assert sess.v3_release_spent == 3
    before = sess.v3_release_spent
    build_spend_receipt(st, sess, _REG_ON, [], [])
    assert sess.v3_release_spent is before


# --- ⑦ 预算门全渠道执行锁(行为修复语义;编排者裁决 2026-08-31)-----------------


def test_buys_erode_refresh_budget() -> None:
    """买/升入账后侵蚀刷新授权预算(预算门从失明恢复为执行):
    v3_release_spent 是 authorize_release_refresh 的钳制账,全渠道消费
    共同消耗 budget_gold——旧行为(买/升对门不可见)=超授权滥刷
    (r4P2 实花 5 记 0 即门失明直接证据)。本锁钉住:先花 5 金买/升后,
    预算余量按预算-5 计,刷 2 放行;追加买至贴满预算后下一刷必拒。"""
    from sr_od.application.currency_war.decision.decision_v2.posture_release import (
        authorize_release_refresh,
    )
    st = _state(gold=98)
    sess = _crisis_sess(st)
    budget = sess.v3_release.budget_gold
    assert budget >= 7                        # 满预算前提(12 形态)
    build_spend_receipt(st, sess, _REG_ON,
                        [LevelUp(cost=4), BuyCard(card=_card('艾丝妲', 1))],
                        [])
    assert sess.v3_release_spent == 5
    assert authorize_release_refresh(sess, 98, 2, _REG_ON)  # 5+2 ≤ 预算
    # 追加买至贴满预算,下一刷必拒(全渠道共同消耗的直接证据)
    build_spend_receipt(st, sess, _REG_ON,
                        [BuyCard(card=_card('贴满件', budget - 7))], [])
    assert sess.v3_release_spent == budget
    assert not authorize_release_refresh(sess, 90, 2, _REG_ON)  # 预算耗尽
