"""预算-回执契约锁(ADR-0504;R-D 姿态-执行断裂,无条件生效)。

设计出处单一源 = ADR-0504(决策 why)+ 判前预注册 =
`docs/develop/currency_war/prereg/w937_spend_receipt/PREREG.md` v2。
原开关 spend_receipt_gate_enabled 已随除开关批删除(W951 同形态:
A/B v1+v2 两轮判正+生产写入端已接线 → 契约无条件生效,关臂零漂移锚
随开关消亡)。

锁面:
- 授权包装配(premises/auth_id/buy_budget):前提成立的帧授权字段
  就位(§1.1-A);
- 产出侧拒发(D1):板满∧bench 空 → 升级授权不发(13-2 p2r4 形态);
  守卫移除红检 = monkeypatch 旁路 attach(旧关臂形态)→ 同帧授权照发
  = 契约洞复现(锁敏感性证明);
- 单帧锁(r4 形态,复盘 g_20260831_032006 p1r4):posture=升级且预算
  足够 → 升级动作必须出现,或有四枚举回执;
- 回执四枚举:no_channel(20-5 p1r5 补给帧形态)/ no_premise /
  no_candidate / no_budget(表锁);
- 对账门三选一:分配器辖域帧只记录交 allocator(不降级)/ 危机帧
  交 crisis release / 常规帧姿态降级 tag='存息'+posture_unfulfilled
  显式声明;
- 帧级复位/奖励帧义务豁免/reward 通道辖域/免费消费计数(返修批)。
"""
from __future__ import annotations

import dataclasses
import logging

import pytest

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.allocator import (
    alloc_domain,
)
from sr_od.application.currency_war.decision.decision_v2.arbiter import (
    arbitrate,
)
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
)
from sr_od.application.currency_war.decision.decision_v2.ev import (
    RoundPosture,
)
from sr_od.application.currency_war.decision.decision_v2.posture import (
    Posture,
    SpendReceipt,
)
from sr_od.application.currency_war.decision.decision_v2.posture_release import (
    attach_spend_authorization,
    crisis_release_open,
    reconcile_spend,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    LevelUp,
)

_FOUR_REASONS = {'no_premise', 'no_channel', 'no_candidate', 'no_budget'}


@pytest.fixture(autouse=True)
def _quiet_logging():
    """测试域收口静音(本仓测试惯例;全局 logging.disable 随 fixture 还原)。"""
    prev = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(prev)


def _st(node: str = 'battle', gold: int = 52, hp: int = 62,
        plane: int = 1, round_num: int = 4,
        bench: list[BenchChar] | None = None,
        deployed: list[BenchChar] | None = None,
        level: int = 4) -> GameState:
    st = GameState()
    st.plane, st.level, st.gold, st.hp = plane, level, gold, hp
    st.round_num = round_num
    st.node_type = node
    st.bench = list(bench or [])
    st.deployed = list(deployed or [])
    st.hp_readable = True
    st.hp_trusted = True
    return st


def _sess(posture: Posture, st: GameState) -> StrategySession:
    """把被测姿态写入轮缓存(主链装配位;attach 的授权输入)。"""
    s = StrategySession()
    s.v3_dp_posture = RoundPosture((st.plane, st.round_num), posture)
    return s


_BENCH_WAITING = [BenchChar(char_id='爻光', faction='仙舟', slot=1)]


# ---------- 授权包装配(§1.1-A) ----------

def test_auth_package_attached_when_premises_hold() -> None:
    """前提成立帧:授权包三件就位(auth_id/premises),姿态标签不变。"""
    st = _st(bench=_BENCH_WAITING)
    posture = Posture(level_up=True, refresh_budget=2, tag='升级+D2')
    sess = _sess(posture, st)
    arbitrate([], st, sess, DEFAULT_REGISTRY)
    cached = sess.v3_dp_posture.posture
    assert cached.auth_id == f'{st.plane}-{st.round_num}'
    assert cached.premises == ('pop_slot', 'spend_channel')
    assert cached.level_up and cached.refresh_budget == 2
    # 空候选帧授权未兑现 → 对账门常规帧降级合法(对账语义在专锁覆盖);
    # 本锁只辖授权包装配面本身
    assert cached.tag in ('升级+D2', '存息')
    assert sess.v3_posture_unfulfilled is not None
    auth = sess.v3_spend_auth
    assert auth is not None and auth['level_up'] and not auth['suppressed']


def test_reward_frame_carries_buy_budget() -> None:
    """奖励帧买侧扩张预算 = 溢余段(g−R*;D2 雏形,[1]/[15] 压库授权面)。"""
    st = _st(node='reward', gold=60, bench=_BENCH_WAITING)
    sess = _sess(Posture(tag='存息'), st)
    arbitrate([], st, sess, DEFAULT_REGISTRY)
    cached = sess.v3_dp_posture.posture
    # 前置自证:溢余>0 才有授权量(公式本身的健全性检查)
    from sr_od.application.currency_war.decision.decision_v2.economy_cycle import (
        overflow,
    )
    assert overflow(st, sess, DEFAULT_REGISTRY) > 0
    assert cached.buy_budget > 0
    assert sess.v3_spend_auth['buy_budget'] == cached.buy_budget


# ---------- 产出侧拒发(D1;13-2 形态)+ 守卫移除红检 ----------

def _board_full_state() -> GameState:
    """13-2 p2r4 形态:板满 ∧ bench 空(升级无 slot 可花)。"""
    cap_chars = [BenchChar(char_id=f'件{i}', faction='', slot=i + 1)
                 for i in range(3)]
    return _st(bench=[], deployed=cap_chars, level=3, gold=63)


def test_production_side_rejects_levelup_without_premise() -> None:
    """板满∧bench 空:升级授权产出侧拒发(level_up=False,tag 回落存息)。"""
    st = _board_full_state()
    sess = _sess(Posture(level_up=True, tag='升级'), st)
    res = arbitrate([_lv_cand(5.0)], st, sess, DEFAULT_REGISTRY)
    cached = sess.v3_dp_posture.posture
    assert cached.level_up is False
    assert cached.tag == '存息'
    assert sess.v3_spend_auth['suppressed'] == ('pop_slot',)
    # 授权未发出 → 无对账义务(不是「授权未兑现」,是「未授权」)
    assert sess.v3_posture_receipt is not None
    assert 'levelup_reason' not in sess.v3_posture_receipt
    assert sess.v3_posture_unfulfilled is None
    # 执行侧纵深防线:升级候选仍被拒付(前序动作演化残余面)
    assert not [a for a in res.actions if isinstance(a, LevelUp)]
    assert any('升级前提不成立' in (row.get('reject') or '')
               for row in res.log)


def test_guard_bypass_negative_control(monkeypatch) -> None:
    """守卫移除红检(锁敏感性):旁路授权包装配(旧关臂形态)→ 同帧

    授权照发、契约面全旁路。原 gate 判据已随开关删除;本锁以 monkeypatch
    三函数为「契约被旁路」的等价形态——若未来有人把装配改成可被旁路
    (或恢复条件化),本锁与上一锁双双变红。
    """
    st = _board_full_state()
    sess = _sess(Posture(level_up=True, tag='升级'), st)
    import sr_od.application.currency_war.decision.decision_v2.arbiter as _arb
    monkeypatch.setattr(_arb, 'attach_spend_authorization',
                        lambda *a, **k: None)
    monkeypatch.setattr(_arb, 'build_spend_receipt', lambda *a, **k: None)
    arbitrate([_lv_cand(5.0)], st, sess, DEFAULT_REGISTRY)
    cached = sess.v3_dp_posture.posture
    assert cached.level_up is True          # 授权照发(授权悬空)
    assert cached.tag == '升级'
    assert cached.auth_id == ''             # 授权包未装配
    assert sess.v3_spend_auth is None
    assert sess.v3_posture_receipt is None
    assert sess.v3_posture_unfulfilled is None


def _lv_cand(val: float) -> tuple[Candidate, float, dict]:
    return (Candidate(action=LevelUp(cost=4), tag='levelup',
                      source='shop'), val, {})


# ---------- r4 形态单帧锁(任务判据) ----------

def test_r4_form_upgrade_action_or_receipt() -> None:
    """r4 形态(g_20260831_032006 p1r4):posture=升级且预算足够 →

    升级动作必须出现,或有四枚举回执(「钱变不成板」无归因态消除)。
    """
    st = _st(gold=52, bench=_BENCH_WAITING)   # premise ok,budget 足够
    sess = _sess(Posture(level_up=True, tag='升级'), st)
    res = arbitrate([_lv_cand(5.0)], st, sess, DEFAULT_REGISTRY)
    has_levelup = any(isinstance(a, LevelUp) for a in res.actions)
    receipt = sess.v3_posture_receipt or {}
    assert has_levelup or receipt.get('levelup_reason') in _FOUR_REASONS


# ---------- 回执四枚举(D3) ----------

def test_receipt_no_channel_supply_frame() -> None:
    """20-5 p1r5 形态:升级授权在无商店通道节点 → 回执 no_channel +

    常规帧降级(tag='存息')+ posture_unfulfilled 显式声明。
    """
    st = _st(node='supply', gold=61, bench=_BENCH_WAITING)
    sess = _sess(Posture(level_up=True, tag='升级'), st)
    arbitrate([], st, sess, DEFAULT_REGISTRY)
    receipt = sess.v3_posture_receipt
    assert receipt is not None
    assert receipt['levelup_reason'] == 'no_channel'
    un = sess.v3_posture_unfulfilled
    assert un is not None
    assert un['channel'] == 'levelup' and un['reason'] == 'no_channel'
    assert un['action'] == 'downgrade'
    assert sess.v3_dp_posture.posture.tag == '存息'


def test_receipt_no_premise_exec_time() -> None:
    """执行时点前提失效残余面:授权帧 working 态板满∧bench 空 →

    回执 no_premise(产出侧 premise 成立、执行侧复核不成立的纵深面)。
    """
    st = _st(gold=60, bench=_BENCH_WAITING)   # 产出时 premise ok
    sess = _sess(Posture(level_up=True, tag='升级'), st)
    attach_spend_authorization(st, sess, DEFAULT_REGISTRY)
    # 执行时点前提复核直接消费 posture_release.levelup_premise_ok,
    # 用板满态构造「授权后前提失效」的残余面
    from sr_od.application.currency_war.decision.decision_v2.posture_release import (
        build_spend_receipt,
        levelup_premise_ok,
    )
    full = _board_full_state()
    assert not levelup_premise_ok(full)
    receipt = build_spend_receipt(full, sess, DEFAULT_REGISTRY, [], [])
    assert receipt is not None
    assert receipt.levelup_reason == 'no_premise'


def test_receipt_no_budget_table_lock() -> None:
    """no_budget 表锁:授权面存在但预算 0 → 回执枚举 no_budget + 降级。"""
    st = _st(gold=30, bench=_BENCH_WAITING)
    sess = _sess(Posture(tag='存息'), st)
    sess.v3_spend_auth = {'auth_id': '1-4', 'level_up': False,
                          'refresh_budget': 0, 'buy_budget': 0,
                          'premises': (), 'suppressed': ()}
    receipt = SpendReceipt(buy_reason='no_budget')
    un = reconcile_spend(st, sess, DEFAULT_REGISTRY, receipt)
    assert un is not None
    assert un['reason'] == 'no_budget' and un['action'] == 'downgrade'


# ---------- 对账门三选一(D4) ----------

def test_reconcile_allocator_jurisdiction_records_only() -> None:
    """死亡域帧:授权未兑现只记录交分配器(action='allocator'),不降级。"""
    st = _st(node='battle', gold=61, hp=20, round_num=1, bench=_BENCH_WAITING)
    # D2 入口帧臂默认关(realization_d2_enabled=False);测试臂显式开
    #(谓词引用而非重造,ADR-0504 §引用不重造;与 alloc_domain 同源判定)
    reg = dataclasses.replace(
        DEFAULT_REGISTRY, realization_chain_enabled=True,
        realization_d2_enabled=True)
    sess = _sess(Posture(level_up=True, tag='升级'), st)
    assert alloc_domain(st, sess, reg) is not None
    arbitrate([], st, sess, reg)
    un = sess.v3_posture_unfulfilled
    assert un is not None and un['action'] == 'allocator'
    assert un['reason'] in _FOUR_REASONS
    # 辖域帧不降级:替代消费由 allocator_run 既有接管承担
    assert sess.v3_dp_posture.posture.tag == '升级'


def test_reconcile_crisis_frame_hands_to_release_arm() -> None:
    """危机帧(应急带∧溢余):授权未兑现交 crisis release 既有臂,只记录。"""
    st = _st(node='battle', gold=100, hp=20, bench=_BENCH_WAITING)
    sess = _sess(Posture(level_up=True, tag='升级'), st)
    # 前置自证:危机臂辖域命中(谓词单一源引用;ADR-0503)
    assert crisis_release_open(st, sess, DEFAULT_REGISTRY)
    arbitrate([], st, sess, DEFAULT_REGISTRY)
    un = sess.v3_posture_unfulfilled
    assert un is not None and un['action'] == 'crisis_release'


# ---------- 返修批(w943_audit5):复位/义务豁免/通道辖域/免费计数 ----------

def test_unfulfilled_reset_per_frame() -> None:
    """复位锁(P1-1):未兑现帧后随「授权被拒发殆尽」的常规段 → 声明清

    None——条件写滞留(跨轮/跨帧误归属)根除,schema「None=无未兑现帧」
    逐帧成立。
    """
    st1 = _st(node='supply', gold=61, bench=_BENCH_WAITING)
    sess = _sess(Posture(level_up=True, tag='升级'), st1)
    arbitrate([], st1, sess, DEFAULT_REGISTRY)
    assert sess.v3_posture_unfulfilled is not None   # 未兑现声明已写
    # 下一帧:仅刷新授权且被通道前提产出侧拒发 → 无有效授权 → 无声明
    st2 = _st(node='supply', gold=61, bench=_BENCH_WAITING, round_num=5)
    sess.v3_dp_posture = RoundPosture((st2.plane, st2.round_num),
                                      Posture(refresh_budget=2, tag='+D2'))
    arbitrate([], st2, sess, DEFAULT_REGISTRY)
    auth = sess.v3_spend_auth
    assert auth is not None and not auth['level_up'] \
        and auth['refresh_budget'] == 0   # 授权被拒发殆尽
    assert sess.v3_posture_unfulfilled is None   # 复位:不携带上帧声明


def test_reward_frame_legal_hoarding_not_unfulfilled() -> None:
    """奖励帧豁免锁(P2-2):授权≠义务——奖励帧 0 买(合法攒息)不记

    未兑现、不触发降级;义务型标记(buy_obligation=True)才入对账。
    """
    st = _st(node='reward', gold=60, bench=_BENCH_WAITING)
    sess = _sess(Posture(tag='存息'), st)
    arbitrate([], st, sess, DEFAULT_REGISTRY)
    assert sess.v3_spend_auth['buy_budget'] > 0   # 前置:授权面已发
    assert 'buy_reason' not in (sess.v3_posture_receipt or {})
    assert sess.v3_posture_unfulfilled is None    # 攒息≠病灶
    # 义务型保留位:置 True 后 0 买恢复入对账(降级路径语义不灭)
    from sr_od.application.currency_war.decision.decision_v2.posture_release import (
        build_spend_receipt,
    )
    sess.v3_spend_auth['buy_obligation'] = True
    receipt = build_spend_receipt(st, sess, DEFAULT_REGISTRY, [], [])
    assert receipt is not None and receipt.buy_reason == 'no_candidate'


def test_reward_node_has_spend_channel() -> None:
    """reward 通道锁(P2-3):奖励节点有商店执行通道(实机复盘 r1/r2/r8

    买牌执行落地为证),不在无通道集——防未来误补 token 的语义反转。"""
    from sr_od.application.currency_war.decision.decision_v2.posture_release import (
        spend_channel_ok,
    )
    assert spend_channel_ok(_st(node='reward'))
    assert spend_channel_ok(_st(node='battle'))
    assert not spend_channel_ok(_st(node='supply'))   # 20-5 形态保持


def test_free_refresh_counts_fulfilled() -> None:
    """免费计数锁(P3-2):0 金刷新(免费额度)是渠道兑现,支出=0 不虚记。"""
    from sr_od.application.currency_war.decision.decision_v2.posture_release import (
        build_spend_receipt,
    )
    from sr_od.application.currency_war.kernel.cw_state import RefreshShop
    st = _st(node='battle', bench=_BENCH_WAITING)
    sess = _sess(Posture(refresh_budget=2, tag='+D2'), st)
    attach_spend_authorization(st, sess, DEFAULT_REGISTRY)
    receipt = build_spend_receipt(st, sess, DEFAULT_REGISTRY,
                                  [RefreshShop(cost=0)], [])
    assert receipt is not None
    assert receipt.refresh_spent == 0        # 实付 0 金,不按缺省虚记 2
    assert receipt.refresh_reason == ''      # 动作发生 = 渠道已兑现
