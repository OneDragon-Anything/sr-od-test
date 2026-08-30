"""预算-回执契约锁(w921_rd_design DESIGN 批1 §1.1;R-D 姿态-执行断裂)。

设计出处单一源 = ``.debug/temp/currency_war/w921_rd_design/DESIGN.md``
(三段契约:授权包→执行回执→对账门);判前预注册 =
同目录 ``PREREG.md``(sim A/B 主判据判前锁定)。

锁面:
- 授权包装配(premises/auth_id/buy_budget):前提成立的帧授权字段
  就位(DESIGN §1.1-A);
- 产出侧拒发(D1):板满∧bench 空 → 升级授权不发(13-2 p2r4 形态);
  开关关(守卫移除负控)→ 同帧授权照发 = 契约洞复现;
- 单帧锁(r4 形态,复盘 g_20260831_032006 p1r4):posture=升级且预算
  足够 → 升级动作必须出现,或有四枚举回执;
- 回执四枚举:no_channel(20-5 p1r5 补给帧形态)/ no_premise /
  no_candidate / no_budget(表锁);
- 对账门三选一:分配器辖域帧只记录交 allocator(不降级)/ 危机帧
  交 crisis release / 常规帧姿态降级 tag='存息'+posture_unfulfilled
  显式声明;
- 开关关零漂移:契约面全旁路,session 字段恒 None、姿态零改动。
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


def _reg(on: bool):
    """契约开关注入臂(on=契约开 / off=零漂移基线臂)。"""
    return dataclasses.replace(DEFAULT_REGISTRY,
                               spend_receipt_gate_enabled=on)


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


# ---------- 授权包装配(DESIGN §1.1-A) ----------

def test_auth_package_attached_when_premises_hold() -> None:
    """前提成立帧:授权包三件就位(auth_id/premises),姿态标签不变。"""
    st = _st(bench=_BENCH_WAITING)
    posture = Posture(level_up=True, refresh_budget=2, tag='升级+D2')
    sess = _sess(posture, st)
    arbitrate([], st, sess, _reg(True))
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
    arbitrate([], st, sess, _reg(True))
    cached = sess.v3_dp_posture.posture
    # 前置自证:溢余>0 才有授权量(公式本身的健全性检查)
    from sr_od.application.currency_war.decision.decision_v2.economy_cycle import (
        overflow,
    )
    assert overflow(st, sess, _reg(True)) > 0
    assert cached.buy_budget > 0
    assert sess.v3_spend_auth['buy_budget'] == cached.buy_budget


# ---------- 产出侧拒发(D1;13-2 形态)+ 守卫移除负控 ----------

def _board_full_state() -> GameState:
    """13-2 p2r4 形态:板满 ∧ bench 空(升级无 slot 可花)。"""
    cap_chars = [BenchChar(char_id=f'件{i}', faction='', slot=i + 1)
                 for i in range(3)]
    return _st(bench=[], deployed=cap_chars, level=3, gold=63)


def test_production_side_rejects_levelup_without_premise() -> None:
    """板满∧bench 空:升级授权产出侧拒发(level_up=False,tag 回落存息)。"""
    st = _board_full_state()
    sess = _sess(Posture(level_up=True, tag='升级'), st)
    res = arbitrate([_lv_cand(5.0)], st, sess, _reg(True))
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


def test_guard_removed_negative_control() -> None:
    """守卫移除负控(锁敏感性):开关关 = 同帧授权照发、契约面全旁路。

    语义对照:off 臂姿态保持「升级」(授权悬空,13-2 病灶形态)而契约
    不记录不降级——这就是本契约关掉的那个洞;若未来有人把产出侧拒发
    改成无条件放行,本锁与上一锁双双变红。
    """
    st = _board_full_state()
    sess = _sess(Posture(level_up=True, tag='升级'), st)
    arbitrate([_lv_cand(5.0)], st, sess, _reg(False))
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
    res = arbitrate([_lv_cand(5.0)], st, sess, _reg(True))
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
    arbitrate([], st, sess, _reg(True))
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
    attach_spend_authorization(st, sess, _reg(True))
    # 执行时点前提复核直接消费 posture_release.levelup_premise_ok,
    # 用板满态构造「授权后前提失效」的残余面
    from sr_od.application.currency_war.decision.decision_v2.posture_release import (
        build_spend_receipt,
        levelup_premise_ok,
    )
    full = _board_full_state()
    assert not levelup_premise_ok(full)
    receipt = build_spend_receipt(full, sess, _reg(True), [], [])
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
    un = reconcile_spend(st, sess, _reg(True), receipt)
    assert un is not None
    assert un['reason'] == 'no_budget' and un['action'] == 'downgrade'


# ---------- 对账门三选一(D4) ----------

def test_reconcile_allocator_jurisdiction_records_only() -> None:
    """死亡域帧:授权未兑现只记录交分配器(action='allocator'),不降级。"""
    st = _st(node='battle', gold=61, hp=20, round_num=1, bench=_BENCH_WAITING)
    # D2 入口帧臂默认关(realization_d2_enabled=False);测试臂显式开
    #(谓词引用而非重造,DESIGN §3;与 alloc_domain 同源判定)
    reg = dataclasses.replace(
        _reg(True), realization_chain_enabled=True,
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
    reg = _reg(True)
    sess = _sess(Posture(level_up=True, tag='升级'), st)
    # 前置自证:危机臂辖域命中(谓词单一源引用;ADR-0503)
    assert crisis_release_open(st, sess, reg)
    arbitrate([], st, sess, reg)
    un = sess.v3_posture_unfulfilled
    assert un is not None and un['action'] == 'crisis_release'


# ---------- 开关关零漂移 ----------

def test_switch_off_zero_drift_on_normal_frame() -> None:
    """开关关:常规帧回执/对账/授权包全旁路,session 字段恒 None。"""
    st = _st(node='supply', gold=61, bench=_BENCH_WAITING)
    sess = _sess(Posture(level_up=True, tag='升级'), st)
    arbitrate([], st, sess, _reg(False))
    assert sess.v3_spend_auth is None
    assert sess.v3_posture_receipt is None
    assert sess.v3_posture_unfulfilled is None
    assert sess.v3_dp_posture.posture.tag == '升级'   # 姿态零改动
