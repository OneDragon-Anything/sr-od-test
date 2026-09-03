"""W951 P36-a 危机帧刷新通道不变式单帧锁。

命题出处=w945 DESIGN P-新1-a「通道不变式 B>0⟹n≥1」(结构已证零参数)
+ w946 标定实据(实机 crisis 帧 RefreshShop p50=0、哑火帧 12/30、p_hit
宽口径 ≥0.94)。机制定位(.debug/temp/currency_war/w951_p36a_impl/
REPORT.md §1):ADR-0468 息档截断门把危机刷新按 essential=False 裁,
arbiter 预截断门在 gold%10<刷价时先拒、authorize_release_refresh 的
预算门未触达(实机哑火帧重放实证)。修法=预算>0 危机帧首刷走 essential
车道(判据单一址=crisis_invariant_lane,消费点两处同址分类:arbiter
预门 + authorize 内门)。

**无条件生效**(ADR-0506 升格裁决:P36-a 数学单篇已证,prereg A/B 仅作
确认 off 16.21%→on 0.71%;crisis_refresh_invariant_enabled 开关已整删,
不留注入面)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 不变式执行保证:gold%10=0 的危机帧(预算 12 在册)首刷经 arbitrate
  全链采纳(actions 含 RefreshShop);
- ② 车道谓词边界:reason≠crisis/预算 0/预算耗尽/首刷已兑现
  (v2_round_refreshes>0)→ 非 essential 车道;
- ③ 豁免面不外溢:首刷兑现后恢复常态截断;
- ④ 协同核对:W944 血预算刷新停付门在危机帧本就急救豁免(blood_budget_
  refresh_blocked=False),不变式与之正交不冲突。
(原「关臂零漂移锚」随开关删除消亡:无条件语义下不存在关臂态,被取代
的锁语义见 ADR-0506;守卫移除红检=临时注释 lane 判据时本文件 ①③ 即红,
实施记录在 REPORT §9。)
"""
from __future__ import annotations

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import (
    arbitrate,
)
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
)
from sr_od.application.currency_war.decision.decision_v2.discipline import (
    blood_budget_refresh_blocked,
)
from sr_od.application.currency_war.decision.decision_v2.ev import RoundPosture
from sr_od.application.currency_war.decision.decision_v2.posture import Posture
from sr_od.application.currency_war.decision.decision_v2.posture_release import (
    ReleaseDirective,
    attach_spend_authorization,
    authorize_release_refresh,
    crisis_invariant_lane,
    crisis_overflow,
    crisis_release_open,
    evaluate_release,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
    RefreshShop,
)


def _state(*, gold: int = 90, hp: int = 1) -> GameState:
    """危机溢余帧基准构造(gold%10=0 哑火帧形;R*=50,预算=min(40,12)=12)。"""
    return GameState(
        plane=1, round_num=5, gold=gold, level=6, hp=hp,
        shop_refresh_cost=2,
        deployed=[BenchChar(slot=20 + i, char_id=f'杂{i}', faction='公司',
                            star=1) for i in range(5)],
        bench=[BenchChar(slot=0, char_id='席0', faction='公司', star=1)]
        + [None] * (BENCH_CAPACITY - 1),
        shop=[], node_type='battle')


def _sess(state: GameState) -> StrategySession:
    """带 crisis 指令的 session(evaluate_release 真实通路装配,同 w935 法)。"""
    s = StrategySession()
    s.v3_dp_posture = RoundPosture(
        (state.plane, state.round_num),
        Posture(save=True, level_up=False, refresh_budget=0))
    _, d = evaluate_release(state, s, DEFAULT_REGISTRY, 'FORM',
                            s.v3_dp_posture.posture)
    assert d is not None and d.reason == 'crisis', '基准帧应产 crisis 指令'
    return s


def _refresh_cand() -> Candidate:
    return Candidate(action=RefreshShop(cost=2), tag='refresh', source='shop')


# --- ① 不变式执行保证(无条件)--------------------------------------------------


def test_invariant_first_refresh_executes() -> None:
    """gold%10=0 危机帧(预算 12 在册)首刷经 arbitrate 全链采纳——
    B>0⟹n≥1 无条件落地(修前同帧预截断门拒、预算门未触达)。"""
    st = _state(gold=90)
    sess = _sess(st)
    res = arbitrate([(_refresh_cand(), -2.0, {})], st, sess, DEFAULT_REGISTRY)
    assert any(isinstance(a, RefreshShop) for a in res.actions), res.log


def test_invariant_authorize_note() -> None:
    """授权门放行且扣账累计(金位 91%10=1 修前同样被预门拒)。"""
    st = _state(gold=91)
    sess = _sess(st)
    note = authorize_release_refresh(sess, 91, 2, DEFAULT_REGISTRY)
    assert note != ''
    assert sess.v3_release_spent == 2


# --- ② 车道谓词边界 ------------------------------------------------------------


def test_lane_predicate_boundaries() -> None:
    """谓词边界逐项:reason≠crisis/预算 0/预算耗尽/首刷已兑现
    (v2_round_refreshes>0)→ 全 False(essential 车道只在「预算>0 且
    付得起一刷且首刷未兑现」)。"""
    st = _state(gold=90)
    sess = _sess(st)
    assert crisis_invariant_lane(sess, 2) is True       # 基准成立
    sess.v3_release = ReleaseDirective(budget_gold=12, rolls=6,
                                       reason='flip')
    assert crisis_invariant_lane(sess, 2) is False      # 非 crisis
    sess.v3_release = ReleaseDirective(budget_gold=0, rolls=0,
                                       reason='crisis')
    assert crisis_invariant_lane(sess, 2) is False      # 预算 0
    sess.v3_release = ReleaseDirective(budget_gold=2, rolls=1,
                                       reason='crisis')
    sess.v3_release_spent = 2
    assert crisis_invariant_lane(sess, 2) is False      # 预算耗尽


def test_invariant_scoped_to_first_refresh_only() -> None:
    """豁免面不外溢:gold%10=1 的帧,首刷凭车道放行;同帧
    v2_round_refreshes=1 后同金位被截断门拒(不变式只保 n≥1,后续刷新
    走常态门)。"""
    st = _state(gold=91)
    sess = _sess(st)
    assert authorize_release_refresh(sess, 91, 2, DEFAULT_REGISTRY) != ''
    sess.v2_round_refreshes = 1
    sess.v3_release_spent = 0
    assert authorize_release_refresh(sess, 91, 2, DEFAULT_REGISTRY) == ''


# --- ④ 溢余基降档(P36-a′)----------------------------------------------------


def test_overflow_basis_downgraded_to_gold() -> None:
    """P36-a′:危机臂溢余基=g 本身(R*_crisis≡0),储备线高低不再辖危机臂
    ——match4 病灶帧形(hp3/金89/排程升级费抬 R*→90)自此开火,预算
    min(89, 6×2)=12(帽形态不变,只改可达性);金 0 仍静默(合法残余,
    非执行缺位)。"""
    st = _state(gold=89, hp=3)
    assert crisis_overflow(st) == 89
    assert crisis_release_open(st, _sess(st), DEFAULT_REGISTRY) is True
    sess = _sess(st)
    _, d = evaluate_release(st, sess, DEFAULT_REGISTRY, 'FORM',
                            sess.v3_dp_posture.posture)
    assert d is not None and d.reason == 'crisis' and d.budget_gold == 12
    st0 = _state(gold=0, hp=3)
    s0 = StrategySession()
    s0.v3_dp_posture = RoundPosture(
        (st0.plane, st0.round_num),
        Posture(save=True, level_up=False, refresh_budget=0))
    _, d0 = evaluate_release(st0, s0, DEFAULT_REGISTRY, 'FORM',
                             s0.v3_dp_posture.posture)
    assert d0 is None    # 金 0:危机溢余基=0,臂静默(合法残余,非执行缺位)


# --- ⑤ 路由面后果钉护(P36-a′ 意图内漂移,W958 审计;ADR-0508 §路由面后果)----


def test_reward_frame_emergency_buy_budget_short_circuit() -> None:
    """奖励帧应急带被 crisis 指令接管 → 常规授权包短路(buy_budget 不发):
    g=30<R* 的应急奖励帧,降档后 crisis_release_open=True → posture 被
    wrap 成 tag='release' → attach_spend_authorization 对 release 帧返回
    None 且 v3_spend_auth 清空(ADR-0508 §路由面后果-路由面;意图内=
    死亡带金零价值⇒压库买授权无意义,搜索占优)。非应急对照帧常规授权
    照发(buy_budget=溢余段),证明短路只由危机接管面触发。"""
    st = _state(gold=30, hp=3)
    st.node_type = 'reward'
    sess = _sess(st)
    wrapped, _ = evaluate_release(st, sess, DEFAULT_REGISTRY, 'FORM',
                                  sess.v3_dp_posture.posture)
    sess.v3_dp_posture = RoundPosture((st.plane, st.round_num), wrapped)
    assert wrapped.tag == 'release'
    assert attach_spend_authorization(st, sess, DEFAULT_REGISTRY) is None
    assert sess.v3_spend_auth is None
    # 非应急对照(hp=62):危机臂不接管,奖励帧常规授权含 buy_budget
    st_ok = _state(gold=60, hp=62)
    st_ok.node_type = 'reward'
    sess_ok = StrategySession()
    sess_ok.v3_dp_posture = RoundPosture(
        (st_ok.plane, st_ok.round_num),
        Posture(save=True, level_up=False, refresh_budget=0))
    auth = attach_spend_authorization(st_ok, sess_ok, DEFAULT_REGISTRY)
    assert auth is not None and auth['buy_budget'] == 10    # 60−R*=10


def test_reconcile_downgraded_band_hands_to_crisis() -> None:
    """对账分类改道(P36-a′ 路由面后果):应急带 g<R*(降档新增接管域,
    旧口径溢余=0 → downgrade '存息')的未兑现对账现交 crisis_release
    只记录——crisis_release_open 是 reconcile 第二分支判据(第三消费点,
    ADR-0508 §路由面后果-对账面)。非应急帧 downgrade 语义不变
    (test_receipt_no_budget_table_lock 既有锁辖)。"""
    st = _state(gold=10, hp=20)
    assert crisis_release_open(st, StrategySession(), DEFAULT_REGISTRY) is True
    sess = StrategySession()
    sess.v3_dp_posture = RoundPosture((st.plane, st.round_num),
                                      Posture(level_up=True, tag='升级'))
    arbitrate([], st, sess, DEFAULT_REGISTRY)
    un = sess.v3_posture_unfulfilled
    assert un is not None and un['action'] == 'crisis_release'


# --- ⑤ 协同核对(W944 血预算门)------------------------------------------------


def test_w944_blood_gate_coexistence() -> None:
    """协同核对:危机帧(hp≤emergency_hp)血预算刷新停付门本就急救豁免
    (return False),不变式车道与之正交——不存在「不变式放行被血门拦截」
    的冲突面(门辖域=非应急 P1 末窗血预算不足帧)。"""
    st = _state(gold=90, hp=1)
    sess = _sess(st)
    assert blood_budget_refresh_blocked(st, sess, DEFAULT_REGISTRY) is False
    assert crisis_invariant_lane(sess, 2) is True

# —— 换核隔离桶(2026-09-03 测试分层批)——
# 本文件属 legacy_baseline 桶:锁的是旧决策核(decision_v2)内部行为语义,
# 随旧核退役而消亡;默认全量与快速集均不跑,仅基线冻结审计/A-B 开跑前
# 两时点单独跑。口径见 sr-od-test/README.md「测试纪律 · legacy 桶」。
import pytest

pytestmark = pytest.mark.legacy_baseline
