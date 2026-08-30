"""W917 危机金出口臂单帧锁(ADR-0503)。

病灶=W907(907288 r5/r7,907106 r7/r8):hp≤emergency_hp 帧应急让位使
release 恒 None → reserve_overflow 爬升而 release_budget 恒 0,存息
posture 在死亡门口不降级。修法=存息准入门应急让位分支在
crisis_release_open(开关∧应急带∧溢余)时产 reason='crisis' 指令
(预算=min(溢余, REFRESH_ROLL_CAP×刷价)),posture 经既有 wrap 降级
tag='release'。设计出处=ADR-0503 + 本批 REPORT
(.debug/temp/currency_war/w917_crisis_release/REPORT.md §1-§2)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 开关关零漂移:危机溢余帧(默认 registry)指令 None,姿态原样;
- ② 开臂形态:crisis 指令预算式/rolls/姿态降级(save=True→False,
  tag='release')/session 写面(v3_release 经 evaluate_release);
- ③ 辖域边界:息线以内(无溢余)不触发;非应急帧不劫持 flip 臂
  (reason='flip' 原语义);flip_hit 在应急带仍让位(辖区结构保留);
- ④ 放行门:危机预算内刷新放行/越预算拒/boss_floor 地板拒;
- ⑤ registry 字段面:默认 False。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.ev import RoundPosture
from sr_od.application.currency_war.decision.decision_v2.posture import Posture
from sr_od.application.currency_war.decision.decision_v2.posture_release import (
    authorize_release_refresh,
    evaluate_release,
    flip_hit,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    REFRESH_ROLL_CAP,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
)

_REG_ON = dataclasses.replace(DEFAULT_REGISTRY, crisis_release_enabled=True)


def _state(*, gold: int = 90, hp: int = 1, plane: int = 1, r: int = 5,
           level: int = 6) -> GameState:
    """危机溢余帧基准构造:r=5 无排程姿态缓存 → R*=50,溢余=40。"""
    return GameState(
        plane=plane, round_num=r, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2,
        deployed=[BenchChar(slot=20 + i, char_id=f'杂{i}', faction='公司',
                            star=1) for i in range(5)],
        bench=[BenchChar(slot=0, char_id='席0', faction='公司', star=1)]
        + [None] * (BENCH_CAPACITY - 1),
        shop=[], node_type='battle')


def _sess(state: GameState, *, save: bool = True) -> StrategySession:
    """带确定性 DP 姿态缓存的 session(缺省=存息姿态,W907 病灶帧形)。"""
    s = StrategySession()
    s.v3_dp_posture = RoundPosture(
        (state.plane, state.round_num),
        Posture(save=save, level_up=False, refresh_budget=0))
    return s


# --- ① 开关关零漂移 -----------------------------------------------------------


def test_crisis_off_zero_drift() -> None:
    """默认 registry(关)危机溢余帧:指令 None、姿态原样、session 无
    release(W907 病灶行为原样保留=零漂移锚)。"""
    st = _state()
    wrapped, d = evaluate_release(st, _sess(st), DEFAULT_REGISTRY, 'FORM',
                                  _sess(st).v3_dp_posture.posture)
    assert d is None
    assert wrapped.tag != 'release'
    assert wrapped.save is True


# --- ② 开臂形态 ---------------------------------------------------------------


def test_crisis_arm_budget_and_downgrade() -> None:
    """开臂危机溢余帧:预算=min(40, 6×2)=12、rolls=6;存息姿态降级
    tag='release' 且 save=False;session.v3_release 同源写入。"""
    st = _state()
    sess = _sess(st)
    dp = sess.v3_dp_posture.posture
    wrapped, d = evaluate_release(st, sess, _REG_ON, 'FORM', dp)
    assert d is not None and d.reason == 'crisis'
    assert d.budget_gold == min(90 - 50, REFRESH_ROLL_CAP * 2) == 12
    assert d.rolls == 6
    assert wrapped.tag == 'release'
    assert wrapped.save is False
    assert sess.v3_release is d


def test_crisis_arm_no_overflow_stays_none() -> None:
    """息线以内(g=R*≤)危机帧:无溢余不触发(息线以内零漂移,I-1 锚同族)。"""
    st = _state(gold=50)
    _, d = evaluate_release(st, _sess(st), _REG_ON, 'FORM',
                            _sess(st).v3_dp_posture.posture)
    assert d is None


def test_crisis_arm_latch_within_round() -> None:
    """latch 语义:指令每轮入口重算为等值指令(纯函数,轮键内不因 hp
    抖动翻转为 None);session 持有最新指令(判据单一址)。"""
    st = _state()
    sess = _sess(st)
    _, d1 = evaluate_release(st, sess, _REG_ON, 'FORM',
                             sess.v3_dp_posture.posture)
    assert d1 is not None
    _, d2 = evaluate_release(st, sess, _REG_ON, 'FORM',
                             sess.v3_dp_posture.posture)
    assert d2 == d1 and sess.v3_release is d2


# --- ③ 辖域边界 ---------------------------------------------------------------


def test_non_emergency_frames_untouched() -> None:
    """非应急帧开臂不劫持 flip 臂:hp>30 溢余帧仍 reason='flip'
    (crisis 臂只辖应急让位分支,正常 flip 辖区零漂移)。"""
    st = _state(hp=30)
    sess = _sess(st, save=False)
    _, d = evaluate_release(st, sess, _REG_ON, 'FORM',
                            sess.v3_dp_posture.posture)
    assert d is not None and d.reason == 'flip'


def test_flip_hit_still_cedes_emergency() -> None:
    """flip_hit 应急让位结构保留(ADR-0426 辖区不相交不动;危机臂是
    存息准入门层的独立第三臂)。"""
    st = _state(hp=25, gold=90)
    assert not flip_hit(st, _sess(st), _REG_ON, 'FORM')


# --- ④ 放行门 -----------------------------------------------------------------


def test_crisis_budget_bounded_release() -> None:
    """危机预算有界放行:direct budget=2 下 cost=1 第 1/2 笔放行,
    第 3 笔累计越预算拒(累计 ≤ 预算语义,与 flip 臂同一消费门)。"""
    from sr_od.application.currency_war.decision.decision_v2.posture_release import (
        ReleaseDirective,
    )
    st = _state(gold=99)
    sess = _sess(st)
    sess.v3_release = ReleaseDirective(budget_gold=2, rolls=2,
                                       reason='crisis')
    assert authorize_release_refresh(sess, 99, 1, _REG_ON)
    assert authorize_release_refresh(sess, 98, 1, _REG_ON)
    assert authorize_release_refresh(sess, 97, 1, _REG_ON) == ''


def test_crisis_tier_truncation_gate() -> None:
    """息档截断门在危机臂照常辖:gold=98(档内余量 8)逐笔 2 金放行至
    90,跨档帧拒(花后不跨息档,essential=False 车道不因危机豁免)。"""
    st = _state(gold=98)
    sess = _sess(st)
    evaluate_release(st, sess, _REG_ON, 'FORM', sess.v3_dp_posture.posture)
    gold = 98
    spent = 0
    for _ in range(6):
        if not authorize_release_refresh(sess, gold, 2, _REG_ON):
            break
        gold -= 2
        spent += 2
    assert spent == 8 and gold == 90
    assert authorize_release_refresh(sess, gold, 2, _REG_ON) == ''


def test_crisis_boss_floor_guard() -> None:
    """花后金低于 boss_floor:危机臂不放行(g≥0 硬钳制/地板语义与
    flip 臂同一消费门,不因危机豁免)。"""
    st = _state(gold=11)
    sess = _sess(st)
    evaluate_release(st, sess, _REG_ON, 'FORM', sess.v3_dp_posture.posture)
    assert authorize_release_refresh(sess, 11, 2, _REG_ON) == ''


# --- ⑤ registry 字段面 --------------------------------------------------------


def test_registry_field_default_off() -> None:
    """字段面:crisis_release_enabled 默认 False(开关生命周期第 1 态)。"""
    assert DEFAULT_REGISTRY.crisis_release_enabled is False
