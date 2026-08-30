"""W780 · P1→P2 接口机制 v2 单帧锁组(六锁;W774 v2 设计落码)。

设计出处:.debug/temp/currency_war/w774_p1_interface_design/REPORT.md(v2)
§2 五项 + 同目录 SIM_AB_PREREGISTRATION.md(v2)§6 单帧锁清单;
攻击复核 = ../w777_p1_iface_attack/REPORT_v2.md(总评「可进实施」)。

锁语义不锁牌面:体系成员名从 ``_pair_members`` 注册表派生(换发牌不碎);
开关默认关 = 零漂移锚(每锁带 off 臂对照或 frame-None 等价断言)。

锁清单(协议 §6 → 本文件):
- 锁①(p1_iface_lockline_update):摇摆代价门(degrade≥2 ∨ 连败≥2)
  触发 ∧ 板面交叠 ≥2 → 锁交叠最大线;交叠全不达 → 不锁;贯穿件信号
  在手(comp 已锁)→ FALLBACK 不辖;off 臂逐位 HEAD。
- 锁②(p1_iface_carry_duty_active / 卸装禁令):硬节点帧核心裸装 ∧
  有简易非组件 → 义务成立(hold 豁免消费位);「无接收者的卸装」拒
  (卖带装角色且无合格接收者=0 例);转移给合格接收者放行。
- 锁③(p1_iface_spend_authorized):水位判据真 ∧ 花后金 ≥ rebirth_
  floor → 授权放行(金地板破息臂);花后金 < rebirth_floor → 不授权;
  水位足帧不授权。
- 锁④(p1_iface_gate_blocked):触发帧买序列含体系件(授权放行),
  纯散件不在序列(拒);本线目标件囤买放行(v1 禁囤行为撤除)。
- 锁⑤(p1_iface_gate_blocked):预警带(<40)非转化∧非压库∧非本线
  目标件买入拒;压库买入放行([34]①);应急带(≤25)非转化拒(压库
  不豁免=显式取舍);boss 帧 ALL IN 窗既有行为零触碰(豁免)。
- 锁⑥(协议 §6-6 门零泄漏):一致性验证失败帧 ②③④动作序列与 off
  臂逐位一致(frame 无触发面 / 门恒 None)。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
)
from sr_od.application.currency_war.decision.decision_v2 import p1_iface
from sr_od.application.currency_war.decision.decision_v2.p1_iface import (
    P1IfaceAuth,
    board_consistency_ok,
    p1_iface_carry_duty_active,
    p1_iface_frame,
    p1_iface_gate_blocked,
    p1_iface_intercept,
    p1_iface_lockline_update,
    p1_iface_spend_authorized,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    _pair_members,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    LevelUp,
    RefreshShop,
    SellBench,
    ShopCard,
)

_PAIR = ('仙舟', '列车同行')
_MEMBERS = sorted(_pair_members(_PAIR))          # 体系成员(注册表派生)
_SYS_PIECE = _MEMBERS[0]                          # 体系件(围栏内)
_SCATTER = '无注册散件'                            # 纯散件(不在注册表)

_REG_OFF = DEFAULT_REGISTRY


def _reg(**kw):
    return dataclasses.replace(
        _REG_OFF,
        p1_iface_lockline_v2_enabled=True,
        p1_iface_carry_equip_enabled=True,
        p1_iface_hardnode_prep_enabled=True,
        p1_iface_lossstreak_flow_enabled=True,
        p1_iface_blood_bands_enabled=True,
        **kw)


_REG_ON = _reg()


def _sess(pair: tuple = _PAIR) -> StrategySession:
    s = StrategySession()
    ist = IntentionState()
    if pair:
        ist.p1_pair = tuple(pair)   # P1 配方锁帧(测试直设终态)
    s.v3_intention = ist
    return s


def _st(**kw) -> GameState:
    """P1 备战基帧:非血线(80)/无连败/金 53/遭遇前一节点。"""
    base = {'plane': 1, 'round_num': 3, 'node_type': '战斗', 'gold': 53,
            'hp': 80, 'level': 6, 'streak': None, 'board': {},
            'bench': [], 'shop': [], 'deployed': [], 'hp_readable': True}
    base.update(kw)
    return GameState(**base)


def _owned_bench(names: list[str]) -> list[BenchChar]:
    return [BenchChar(slot=i + 1, char_id=n) for i, n in enumerate(names)]


def _buy(name: str, gold_cost: int = 3, score: float = 0.0,
         tag: str = 'line_carry') -> tuple[Candidate, float, dict]:
    cand = Candidate(action=BuyCard(ShopCard(x=0, name=name,
                                             cost=gold_cost)),
                     tag=tag, source='test')
    return cand, score, {}


# ===== 锁① 摇摆代价门 + FALLBACK 板面一致性 =====

def test_lock1_swing_gate_consistent_pair_locks() -> None:
    """锁①(协议 §6-1):代价门触发(连败≥2)∧ 板面交叠 ≥2 → 锁交叠
    最大候选对(latch 持久,ist.p1_pair 覆写);未触发帧不锁(off 臂
    同帧零漂移=派生对原样)。断言按语义不锁牌面:锁定对 ∈ 候选集
    (派生对 ∪ 兜底对)且板面交叠 ≥2。"""
    sess_on, sess_off = _sess(pair=()), _sess(pair=())
    st = _st(streak=-2, bench=_owned_bench(_MEMBERS[:2]))
    p1_iface_lockline_update(st, sess_on.v3_intention, sess_on, _REG_ON)
    locked = tuple(sess_on.v3_intention.p1_pair)
    from sr_od.application.currency_war.kernel.cw_intention import (
        _P1_PAIR_PREF,
        p1_early_pair,
    )
    assert locked in {tuple(p1_early_pair(st, sess_on.v3_intention) or ()),
                      tuple(_P1_PAIR_PREF[:2])} and locked
    assert len(set(_pair_members(locked)) & set(_MEMBERS[:2])) \
        >= _REG_ON.p1_iface_board_match_min, locked
    # off 臂:零漂移(派生对原样,函数不写任何状态)
    p1_iface_lockline_update(st, sess_off.v3_intention, sess_off, _REG_OFF)
    assert tuple(sess_off.v3_intention.p1_pair) == ()
    # 锁存续:下一轮未锁分支重派生不翻锁(闩覆写)
    st2 = _st(streak=-2, bench=_owned_bench(_MEMBERS[:2]))
    p1_iface_lockline_update(st2, sess_on.v3_intention, sess_on, _REG_ON)
    assert tuple(sess_on.v3_intention.p1_pair) == locked


def test_lock1_no_board_match_never_locks() -> None:
    """锁①(锁错不如不锁):代价门触发但板面交叠全不达(≥2 失败)→
    不锁(方向集空,P2 不被误导);intercept 记 no_match 事件。"""
    sess = _sess(pair=())
    st = _st(streak=-2, bench=[])   # 板面空:交叠 0
    p1_iface_lockline_update(st, sess.v3_intention, sess, _REG_ON)
    assert tuple(sess.v3_intention.p1_pair) == ()
    assert sess.v3_intention.last_event == 'p1_iface_lockline:no_match'


def test_lock1_comp_lock_and_gate_thresholds() -> None:
    """锁①([23] 锚优先 + 阈值粒度):comp 已锁帧 FALLBACK 不辖(latch
    清);连败 1(<2)且无降格事件 → 门不触发;降格事件 ≥2 触发。"""
    sess = _sess(pair=())
    sess.v3_intention.phase = 'locked'
    sess.v3_intention.locked_comp = '列车同行'
    st = _st(streak=-2, bench=_owned_bench(_MEMBERS[:2]))
    p1_iface_lockline_update(st, sess.v3_intention, sess, _REG_ON)
    assert getattr(sess, 'v3_p1_iface_lock_pair', ()) in ((), None)
    # 阈值下不触发(连败 1)
    sess2 = _sess(pair=())
    p1_iface_lockline_update(_st(streak=-1), sess2.v3_intention, sess2,
                             _REG_ON)
    assert tuple(sess2.v3_intention.p1_pair) == ()
    # 降格事件 ≥2 触发(位面内 False→True 转移计数:r6 触发/r5 退出/
    # r6 再触发 = 两次事件)
    sess3 = _sess(pair=())
    reg_low = dataclasses.replace(_REG_ON, p1_exit_blood_target=90)
    for rnd in (6, 5, 6):
        p1_iface_lockline_update(
            _st(round_num=rnd, bench=_owned_bench(_MEMBERS[:2])),
            sess3.v3_intention, sess3, reg_low)
    assert getattr(sess3, 'v3_p1_iface_deg_count', 0) >= 2
    locked3 = tuple(sess3.v3_intention.p1_pair)
    assert locked3 and len(set(_pair_members(locked3))
                           & set(_MEMBERS[:2])) >= 2, locked3


# ===== 锁② carry 装备义务 + 禁无接收者的卸装 =====

def test_lock2_carry_duty_and_unequip_ban() -> None:
    """锁②(协议 §6-2):硬节点帧 ∧ 意向核心上场 ∧ 0 装备 ∧ owned 有
    可穿件 → 义务成立(equip_all hold 豁免消费位);核心已穿/供给空 →
    义务不成立。卸装禁令:卖带装备 bench 件且无合格接收者 → 拒;有
    合格接收者(在场星数 ≥ 被卸者)→ 放行([24] 转移语义)。"""
    core = _MEMBERS[0]
    duty_st = _st(node_type='遭遇', bench=_owned_bench([core]))
    deployed = [BenchChar(slot=1, char_id=core, position_pref='back')]
    sess = _sess()
    sess.v3_core_names = {core}
    assert p1_iface_carry_duty_active(
        _REG_ON, duty_st, sess, deployed,
        {('back', 1): []}, ['火力风暴潮']) is True
    # 核心已穿 → 义务已兑现(不成立)
    assert p1_iface_carry_duty_active(
        _REG_ON, duty_st, sess, deployed,
        {('back', 1): ['火力风暴潮']}, ['火力风暴潮']) is False
    # 供给面空 → 合法空转(False)
    assert p1_iface_carry_duty_active(
        _REG_ON, duty_st, sess, deployed, {('back', 1): []}, []) is False
    # 卸装禁令:卖带装件(无接收者:deployed 空)→ 拒;有高星在场者 → 放行
    # (卸装禁令辖域=②硬节点帧 ∧ ①一致性门:遭遇帧 + 双成员板面)
    seller = BenchChar(slot=1, char_id=_MEMBERS[5], star=1,
                       equips=['火力风暴潮'])
    st_sell = _st(node_type='遭遇',
                  bench=[seller, BenchChar(slot=2, char_id=_MEMBERS[1])])
    sell = Candidate(action=SellBench(bench_idx=0), tag='sell',
                     source='test')
    assert p1_iface_gate_blocked(sell, st_sell, st_sell, sess, _REG_ON)
    st_recv = _st(node_type='遭遇',
                  bench=[seller, BenchChar(slot=2, char_id=_MEMBERS[1])],
                  deployed=[BenchChar(slot=1, char_id=_MEMBERS[1], star=2,
                                      position_pref='back')])
    assert p1_iface_gate_blocked(sell, st_recv, st_recv, sess,
                                 _REG_ON) is None


# ===== 锁③ 遭遇备战授权(金下限 + 水位判据)=====

def test_lock3_hardnode_prep_authorization_gold_floor() -> None:
    """锁③(协议 §6-3):硬节点帧 hp−L_node<25 ∧ 花后金 ≥ rebirth_
    floor → 破息授权放行(off 臂同帧被既有 HOARD 门拒=开门净效应);
    花后金 < rebirth_floor → 不授权;水位足帧(hp 高)不授权。"""
    # L_node(遭遇, rung0)=streak_floor_loss_damage['encounter'] 截距
    enc = DEFAULT_REGISTRY.streak_floor_loss_damage['encounter']
    l_node = max(0.0, enc[0])
    st = _st(node_type='遭遇', hp=int(l_node) + 10, gold=40,
             bench=_owned_bench(_MEMBERS[:2]))
    sess = _sess()
    auth, why = p1_iface_frame(st, sess, _REG_ON)
    assert auth is not None and auth.hardnode_prep, why
    cand, score, bd = _buy(_SYS_PIECE, gold_cost=8, score=-1.0)
    assert p1_iface_spend_authorized(cand, st, st, sess, _REG_ON)
    # 仲裁面开门净效应:金 53 破息买(gold_floor 过,息线 EV 拒;
    # on 授权放行 / off 臂拒)。刻度 53-6=47 ≥ rebirth_floor。
    st_spill = _st(node_type='遭遇', hp=int(l_node) + 10, gold=53,
                   bench=_owned_bench(_MEMBERS[:2]))
    cand_spill, s_spill, b_spill = _buy(_SYS_PIECE, gold_cost=6, score=0.5)
    res_on = arbitrate([(cand_spill, s_spill, b_spill)], st_spill, sess,
                       _REG_ON)
    res_off = arbitrate([(cand_spill, s_spill, b_spill)], st_spill, sess,
                         _REG_OFF)
    assert [a for a in res_on.actions if isinstance(a, BuyCard)], res_on.log
    assert not [a for a in res_off.actions if isinstance(a, BuyCard)]
    # 金下限:花后 40-32=8 < rebirth_floor 20 → 不授权(花 32 的笔)
    cand32, s32, b32 = _buy(_SYS_PIECE, gold_cost=32, score=5.0)
    assert not p1_iface_spend_authorized(cand32, st, st, sess, _REG_ON)
    # 水位足帧:hp 高 → frame 无 ③ 触发面,授权恒 False
    st_safe = _st(node_type='遭遇', hp=80, gold=40,
                  bench=_owned_bench(_MEMBERS[:2]))
    assert p1_iface_spend_authorized(cand, st_safe, st_safe, sess,
                                     _REG_ON) is False


# ===== 锁④ 连败金流(体系件授权 / 纯散件不买)=====

def test_lock4_lossstreak_flow_system_piece_only() -> None:
    """锁④(协议 §6-4):连败≥2∧金>息线∧form 缺口帧 → 当场可上场
    体系件授权放行(破息臂);纯散件不在序列(gate 拒);本线目标件
    (体系成员囤买)不被禁(v1 禁囤行为锁撤除,[21]/[13] 正常行为)。"""
    st = _st(streak=-2, gold=53, bench=_owned_bench(_MEMBERS[:2]))
    sess = _sess()
    auth, _ = p1_iface_frame(st, sess, _REG_ON)
    assert auth is not None and auth.lossstreak_flow
    # 体系件:授权可达(当场可上场:deployed 空);仲裁面破息放行
    # (金 53 → 49 跨息档;off 臂 EV≤0 拒,on 臂授权放行=净效应)
    sys_cand, s1, b1 = _buy(_SYS_PIECE, gold_cost=4, score=0.5)
    assert p1_iface_spend_authorized(sys_cand, st, st, sess, _REG_ON)
    res = arbitrate([(sys_cand, s1, b1)], st, sess, _REG_ON)
    assert [a for a in res.actions if isinstance(a, BuyCard)], res.log
    # 纯散件:不放行且收门拒(负分候选零动作=不在序列)
    sc_cand, s2, b2 = _buy(_SCATTER, gold_cost=1, score=-1.0,
                           tag='off_target')
    assert not p1_iface_spend_authorized(sc_cand, st, st, sess, _REG_ON)
    assert p1_iface_gate_blocked(sc_cand, st, st, sess, _REG_ON)
    res2 = arbitrate([(sc_cand, s2, b2)], st, sess, _REG_ON)
    assert not [a for a in res2.actions if isinstance(a, BuyCard)], res2.log
    # 本线目标件(体系成员 bench 囤)不被 gate 禁(禁囤行为已撤除)
    hoard_st = _st(streak=-2, gold=53, bench=_owned_bench(_MEMBERS[:2]),
                   deployed=[BenchChar(slot=i, char_id=_MEMBERS[j],
                                       position_pref='back')
                             for i, j in zip(range(1, 7), range(6))])
    hoard_cand = Candidate(action=BuyCard(ShopCard(x=0, name=_MEMBERS[7],
                                                   cost=1)),
                           tag='o1_bench_fill', source='test')
    assert p1_iface_gate_blocked(hoard_cand, hoard_st, hoard_st, sess,
                                 _REG_ON) is None


# ===== 锁⑤ 血线三带 =====

def test_lock5_blood_bands_warn_and_emergency() -> None:
    """锁⑤(协议 §6-5):预警带(<40)非转化∧非压库∧非本线目标件
    买入拒;压库(tag=copy_press)放行;应急带(≤25)非转化拒且压库
    不豁免(显式取舍);boss 帧 ALL IN 窗豁免(gate 恒 None)。"""
    # 非转化构造:deployed 满 cap(6/6)→ 买不可上场;散件名不可合成
    full_dep = [BenchChar(slot=i, char_id=_MEMBERS[j], position_pref='back')
                for i, j in zip(range(1, 7), range(6))]
    st_warn = _st(hp=35, bench=_owned_bench(_MEMBERS[:2]),
                  deployed=full_dep)
    sess = _sess()
    auth, _ = p1_iface_frame(st_warn, sess, _REG_ON)
    assert auth is not None and auth.blood_band == 'warn'
    hoard_cand, _, _ = _buy(_SCATTER, gold_cost=1, score=5.0,
                            tag='off_target')
    assert p1_iface_gate_blocked(hoard_cand, st_warn, st_warn, sess,
                                 _REG_ON)
    press_cand, _, _ = _buy(_SCATTER, gold_cost=1, score=5.0,
                            tag='copy_press')
    assert p1_iface_gate_blocked(press_cand, st_warn, st_warn, sess,
                                 _REG_ON) is None
    # 应急带:非转化拒;压库同样拒(显式取舍)
    st_emg = _st(hp=20, bench=_owned_bench(_MEMBERS[:2]),
                 deployed=full_dep)
    auth_e, _ = p1_iface_frame(st_emg, sess, _REG_ON)
    assert auth_e is not None and auth_e.blood_band == 'emergency'
    assert p1_iface_gate_blocked(hoard_cand, st_emg, st_emg, sess, _REG_ON)
    assert p1_iface_gate_blocked(press_cand, st_emg, st_emg, sess, _REG_ON)
    # boss/ALL IN 窗豁免
    st_boss = _st(hp=35, node_type='boss', round_num=9,
                  bench=_owned_bench(_MEMBERS[:2]), deployed=full_dep)
    assert p1_iface_gate_blocked(hoard_cand, st_boss, st_boss, sess,
                                 _REG_ON) is None


# ===== 锁⑥ 一致性门零泄漏 + off 臂零漂移 =====

def test_lock6_consistency_gate_zero_leak() -> None:
    """锁⑥(协议 §6-6):①一致性验证失败的帧(板面交叠 <2),②③④
    触发面全空(frame None,intercept=no_consistency)——on 臂动作序列
    与 off 臂逐位一致(门语义零泄漏);全开关关时 intercept 恒 ''。"""
    st = _st(node_type='遭遇', hp=80, streak=-2, bench=[])   # 交叠 0;无血带
    sess = _sess()
    auth, why = p1_iface_frame(st, sess, _REG_ON)
    assert auth is None and why == 'no_consistency'
    assert p1_iface_intercept(st, sess, _REG_ON) == 'no_consistency'
    assert p1_iface_spend_authorized(
        Candidate(action=RefreshShop(cost=2), tag='refresh', source='test'),
        st, st, sess, _REG_ON) is False
    # off 臂逐位一致(frame None / intercept '')
    auth_off, why_off = p1_iface_frame(st, sess, _REG_OFF)
    assert auth_off is None and why_off == ''
    assert p1_iface_intercept(st, sess, _REG_OFF) == ''
    # 决策面零漂移:授权帧同候选 on/off 同输出(负分刷新拒,HEAD 行为)
    rc = Candidate(action=RefreshShop(cost=2), tag='refresh', source='test')
    st_ok = _st(node_type='遭遇', hp=30, bench=_owned_bench(_MEMBERS[:2]))
    res_on = arbitrate([(rc, -2.0, {})], st_ok, sess, _REG_ON)
    res_off = arbitrate([(rc, -2.0, {})], st_ok, sess, _REG_OFF)
    assert (not any(isinstance(a, RefreshShop) for a in res_on.actions))
    assert (not any(isinstance(a, RefreshShop) for a in res_off.actions))


# ===== 开关合规(生命周期第 1 态:默认关零行为)=====

def test_switches_default_off_zero_drift() -> None:
    """开关合规(协议 §7):五开关默认全关;默认表帧判定恒 None、
    gate 恒 None、授权恒 False、锁线后处理零写入(零行为变更锚)。"""
    for name in ('p1_iface_lockline_v2_enabled',
                 'p1_iface_carry_equip_enabled',
                 'p1_iface_hardnode_prep_enabled',
                 'p1_iface_lossstreak_flow_enabled',
                 'p1_iface_blood_bands_enabled'):
        assert getattr(DEFAULT_REGISTRY, name) is False, name
    st = _st(node_type='遭遇', hp=20, streak=-2,
             bench=_owned_bench(_MEMBERS[:2]))
    sess = _sess()
    assert p1_iface_frame(st, sess, _REG_OFF) == (None, '')
    assert p1_iface_gate_blocked(
        Candidate(action=BuyCard(ShopCard(x=0, name=_SCATTER, cost=1)),
                  tag='off_target', source='test'),
        st, st, sess, _REG_OFF) is None
    assert p1_iface_spend_authorized(
        Candidate(action=LevelUp(cost=4), tag='levelup', source='test'),
        st, st, sess, _REG_ON) is False   # 升级恒不辖(④ [33] 例外语义)
    sess2 = _sess(pair=())
    p1_iface_lockline_update(st, sess2.v3_intention, sess2, _REG_OFF)
    assert tuple(sess2.v3_intention.p1_pair) == ()
    assert 'v3_p1_iface_lock_pair' not in sess2.__dict__
