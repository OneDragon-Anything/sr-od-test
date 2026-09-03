# -*- coding: utf-8 -*-
"""test_cw_release_endgame 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w332b_release: test_cw_w332b_release.py
- p1_terminal_release: test_cw_p1_terminal_release.py
- w361_press_channel: test_cw_w361_press_channel.py
- w653_c7_zero_drift: test_cw_w653_c7_zero_drift.py
- w645_tier_truncation: test_cw_w645_tier_truncation.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== w332b_release ====================

import dataclasses
import math
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_economy import NodeGoal
from sr_od.application.currency_war.kernel.cw_plane_table import  level_cost
from sr_od.application.currency_war.decision.decision_v2.posture import Posture
from sr_od.application.currency_war.kernel.cw_line_switch import  e_rounds, should_switch_e, switch_allowed
from sr_od.application.currency_war.kernel.cw_state import  BENCH_CAPACITY, BenchChar, GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.ev import RoundPosture
from sr_od.application.currency_war.decision.decision_v2.posture_release import  ReleaseDirective, authorize_release_refresh, evaluate_release, flip_hit, release_directive, slot_guard_blocks_level, wrap_posture
from sr_od.application.currency_war.kernel.cw_registry import  DEFAULT_REGISTRY

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


def _sess(state: GameState, *, level_up: bool = False,
          refresh_budget: int = 6) -> StrategySession:
    """带确定性 DP 姿态缓存的 session(round_posture 轮键命中即直回,
    测试不真解 DP——R*/容量的期望值由常量表本地复算)。"""
    s = StrategySession()
    s.v3_dp_posture = RoundPosture(
        (state.plane, state.round_num),
        Posture(save=False, level_up=level_up,
                refresh_budget=refresh_budget))
    return s


def _reserve(level: int, level_up: bool, plane: int = 1, r: int = 5) -> int:
    """R* 期望值本地复算(常量表:息线 50 + 窗口内排程升级费;费用表
    单一源=原 DP level_cost 公式,不借被测函数)。"""
    floor = 50
    h = min(3, 9 - r)
    if h <= 0 or not level_up:
        return floor
    return floor + level_cost(level)


# --- ① FLIP 谓词边界(ADR-0445 溢余判定版)-------------------------------------


def test_flip_emergency_zone_ceded() -> None:
    """hp≤25 应急辖区,FLIP 让位(双触发防护;辖区不相交结构保留)。"""
    st = _state(hp=25, gold=90)
    assert not flip_hit(st, _sess(st), _REG, 'FORM')
    st = _state(hp=26, gold=90)
    assert flip_hit(st, _sess(st), _REG, 'FORM')


def test_flip_requires_overflow_and_capacity() -> None:
    """前置:g>R*(溢余段;息线以内零漂移,I-1 锚)∧ C_t>0(存在正 EV
    转化帧——义务不能废 EV 过滤)。相位无关:SPEND 帧同样辖(旧 FORM
    辖域已被 ADR-0445 取代——已成型 SPEND 帧是旧谓词的死钱盲区)。"""
    st = _state(gold=50)
    assert not flip_hit(st, _sess(st), _REG, 'FORM')     # 无溢余段
    # 批 3 预算口径:溢余 1 金(< 刷价 2)→ 刷新预算 0 ∧ 店空 → C_t=0,
    # flip 不辖(该帧由存息准入门接管:存息非法零预算指令);溢余 ≥ 刷价
    # 帧刷新预算>0 → C_t>0,flip 辖。
    st = _state(gold=51)
    assert not flip_hit(st, _sess(st), _REG, 'FORM')
    st = _state(gold=52)
    assert flip_hit(st, _sess(st), _REG, 'FORM')         # 溢余 2 金=刷价即辖
    assert flip_hit(st, _sess(st), _REG, 'SPEND')        # 相位无关
    st = _state(gold=90)
    # 店空帧预算确定性:溢余 40 → 预算 6 刷帽 ×2 =12 > 0 → C_t>0,
    # flip 辖(原锁前提「无 DP 授权 → C_t=0」随 DP 退役;预算口径下
    # 店空帧的刷新预算仍计入容量,锁面重推出处=W615 §2-R3 预算式
    # 只花溢余、刷新本身即合法消费形式)
    assert flip_hit(st, _sess(st), _REG, 'FORM')


def test_flip_hp_dimension_exited() -> None:
    """血量维度退场锁(ADR-0426 增补 D):同溢余帧 hp=39/hp=40/hp=100
    行为逐位一致;hp 可信位(hp_readable/hp_trusted)不再评估——100 兜底
    假帧也照常辖(旧 ADR-0428 守卫辖的是血量判据,血量判据退场后无辖域)。"""
    for hp in (39, 40, 100):
        st = _state(hp=hp, gold=60)
        st.hp_readable = False
        st.hp_trusted = False
        assert flip_hit(st, _sess(st), _REG, 'FORM'), hp


def test_flip_boss_frame_overflow_scoped() -> None:
    """末窗帧辖域=溢余段(旧末窗投影臂 hp−boss 税<25 已随血量维度退场):
    boss 窗帧 g>R* 命中、g≤R* 不命中,hp 高低无关。"""
    st = _state(gold=67, hp=45, node='boss')
    assert flip_hit(st, _sess(st), _REG, 'FORM')
    st = _state(gold=67, hp=59, node='boss')
    assert flip_hit(st, _sess(st), _REG, 'FORM')    # hp 维度退场:59 也辖
    st = _state(gold=40, hp=45, node='boss')
    assert not flip_hit(st, _sess(st), _REG, 'FORM')    # g<R* 零漂移


def test_flip_scope_p3_included() -> None:
    """辖域全位面(P3 并入;ADR-0445:P3 同有收入/息帽结构,溢余段
    弱占优论证不依赖位面,旧 P3 排除无数学理由)。"""
    st = _state(plane=3, gold=60)
    assert flip_hit(st, _sess(st), _REG, 'FORM')


def test_reserve_cap_narrows_overflow_basis(monkeypatch) -> None:
    """R* 储备线锁:排程升级帧的 R*=息线+窗口内升级费,溢余基收窄——
    g 在 [息线, R*] 段是排程储蓄不是死钱,不 fire(设计 §1.3/§4 豁免行;
    升级费期望值=level_cost 常量表本地复算)。
    批 3 预算收权:排程判据 = 确定性核(cw_economy.schedule_upgrade
    单一址),本锁以 monkeypatch 钉排程真值注入消费方契约(消费方注入式
    锁语义保留,D3 处置表);生产者规则锁在 test_cw_w633_migration_b3。"""
    from sr_od.application.currency_war.kernel import cw_economy
    monkeypatch.setattr(cw_economy, 'schedule_upgrade',
                        lambda *a, **k: True)
    st = _state(gold=50 + level_cost(6) + 5, r=5)
    assert flip_hit(st, _sess(st), _REG, 'FORM')   # >R* 溢余段
    st = _state(gold=50 + level_cost(6) - 5, r=5)
    assert not flip_hit(st, _sess(st),
                        _REG, 'FORM')    # ∈[50, R*] 排程储蓄
    # 无排程(核返回 False)同帧金位不再豁免:照常溢余
    monkeypatch.setattr(cw_economy, 'schedule_upgrade',
                        lambda *a, **k: False)
    assert flip_hit(st, _sess(st), _REG, 'FORM')


def test_cap_full_flip_frame_keeps_level_up_rule2(monkeypatch) -> None:
    """cap 满员并存裁决(DESIGN §②规则2 保留):SPEND 相位的 cap 满员
    boss 窗帧由 FLIP 命中承接——third_path=False,wrap 后 level_up 保留
    (追级与泄息并存);预算= max(义务, 排程预算 6×2=12),义务=min(溢余, C_t)。
    排程真值 monkeypatch 钉住(消费方注入式锁,同上锁面重推)。"""
    from sr_od.application.currency_war.kernel import cw_economy
    monkeypatch.setattr(cw_economy, 'schedule_upgrade',
                        lambda *a, **k: True)
    st = _state(gold=67, hp=38, plane=1, r=9, node='boss', deployed_n=6)
    s = _sess(st)
    assert not slot_guard_blocks_level(st)   # 满员:slot 守卫不触发
    posture = Posture(save=False, level_up=True, refresh_budget=6)
    d = release_directive(st, s, _REG, 'SPEND', posture)
    assert d is not None and d.third_path is False
    overflow = 67 - _reserve(6, True, 1, 9)   # r9:h=0 → R*=50(窗口外不储蓄)
    cap = level_cost(6) + 12                  # 升级计划费 + 刷新分量 6×2
    expected = max(min(overflow, cap), 12)
    assert d.budget_gold == expected
    p = wrap_posture(posture, d)
    assert p.tag == 'release' and p.level_up is True


# --- ② 预算三方合并 -----------------------------------------------------------


def test_merge_release_covers_dp_budget() -> None:
    """合并表(ADR-0445 §1.4):budget = max(义务 min(溢余,C_t),
    DP 预算×刷价)。溢余 22 > 容量 12 → 义务被容量封顶(A-1 刀法:
    义务不能把金推进负 EV 件)。"""
    st = _state(gold=72, hp=30)
    d = release_directive(st, _sess(st), _REG, 'FORM',
                          Posture(save=False, level_up=False, refresh_budget=6))
    assert d is not None
    assert d.budget_gold == 12            # min(溢余22, C_t12) = 12
    assert d.rolls == 6
    assert d.third_path is False


def test_merge_dp_authority_not_shrunk() -> None:
    """DP 已有授权时不缩水:溢余 6 < DP 6×2=12 → max(6, 12)=12。"""
    st = _state(gold=56, hp=30)
    d = release_directive(st, _sess(st), _REG, 'FORM',
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
    """末窗 deployed<cap ∧ bench 有件:纯 level_up 帧显式注入溢余
    (溢余基=R*;无排程升级帧 R*=息线 50),level_up 压掉(slot 边际
    本窗=0),不落 hold。"""
    st = _state(gold=60, node='boss', deployed_n=5, bench_n=1)
    s = _sess(st)
    assert slot_guard_blocks_level(st)
    d = release_directive(st, s, _REG, 'SPEND',   # 已成型也辖(独立于 FLIP)
                          Posture(save=False, level_up=True, refresh_budget=0))
    assert d is not None and d.third_path is True
    assert d.budget_gold == 10 and d.rolls == 5
    p = wrap_posture(Posture(save=False, level_up=True, refresh_budget=0), d)
    assert p.level_up is False and p.tag == 'release' and p.refresh_budget == 5


def test_third_path_reserve_scope(monkeypatch) -> None:
    """第三路径溢余基=R* 锁:排程升级帧(R*=50+升级费)的 g≤R* 段无溢余
    → 不注入(储备线内的金是排程储蓄不是死钱,注入会击穿息线;
    ADR-0445 §1.3 豁免行)。排程真值 monkeypatch 钉住(同上重推)。"""
    from sr_od.application.currency_war.kernel import cw_economy
    monkeypatch.setattr(cw_economy, 'schedule_upgrade',
                        lambda *a, **k: True)
    st = _state(gold=50 + level_cost(6) - 1, node='boss',
                deployed_n=5, bench_n=1)
    d = release_directive(st, _sess(st), _REG, 'SPEND',
                          Posture(save=False, level_up=True, refresh_budget=0))
    assert d is None


def test_third_path_not_outside_boss_window() -> None:
    """辖域=末窗:非 boss 窗的 level_up 帧不走第三路径注入(slot 压制
    语义属末窗);溢余段的泄息由 FLIP 臂承接(third_path=False)。"""
    st = _state(gold=60, node='battle', deployed_n=5, bench_n=1)
    d = release_directive(st, _sess(st), _REG, 'SPEND',
                          Posture(save=False, level_up=True,
                                  refresh_budget=0))
    assert d is None or d.third_path is False


def test_third_path_not_when_cap_full() -> None:
    """cap 满员:slot 守卫不触发,第三路径(规则1/3 注入)不辖;末窗
    FLIP 命中 → 规则2 并存裁决(third_path=False,level_up 保留)。
    修前该帧两臂双盲返回 None(泄息通道静默),本锁防回归到死区。"""
    st = _state(gold=60, node='boss', deployed_n=6)
    s = _sess(st)
    assert not slot_guard_blocks_level(st)
    posture = Posture(save=False, level_up=True, refresh_budget=6)
    d = release_directive(st, s, _REG, 'SPEND', posture)
    assert d is not None and d.third_path is False
    assert d.budget_gold == 12 and d.rolls == 6   # max(min(溢余10,C_t12),12)=12
    p = wrap_posture(posture, d)
    assert p.tag == 'release' and p.level_up is True


# --- ⑦ latch 单窗 --------------------------------------------------------------


def test_third_path_trusted_carried_hp_frame_blocks_level() -> None:
    """第三路径注入锁(boss 窗 deployed<cap ∧ bench 有件):slot 压制
    照常生效、third_path 注入溢余预算。hp 可信位已随血量维度退场
    (ADR-0426 增补 D),本帧不再查 readable/trusted(旧「放宽 vs 兜底」
    语义辖的是血量判据,判据退场后无辖域)。"""
    st = _state(gold=60, hp=38, plane=1, r=9, node='boss',
                deployed_n=5, bench_n=1)
    st.hp_readable = False
    st.hp_trusted = True
    s = _sess(st)
    assert slot_guard_blocks_level(st)
    d = release_directive(st, s, _REG, 'SPEND',
                          Posture(save=False, level_up=True,
                                  refresh_budget=0))
    assert d is not None and d.third_path is True
    assert d.budget_gold == 10 and d.rolls == 5   # 溢余 g−50(r9 窗外不储蓄)
    p = wrap_posture(Posture(save=False, level_up=True, refresh_budget=0), d)
    assert p.level_up is False and p.tag == 'release'


def test_latch_within_round_no_flip_flop() -> None:
    """同轮命中后不回退(防姿态振荡;新谓词下抖动源=金/店重读——
    溢余抖没时 latch 保持泄息意图);轮键变化自然失效。"""
    st = _state(gold=60, r=5)
    s = _sess(st, refresh_budget=3)   # C_t=3×2=6>0
    p1, d1 = evaluate_release(st, s, _REG, 'FORM',
                              Posture(save=True, refresh_budget=3))
    assert d1 is not None and p1.tag == 'release'
    # 同轮溢余抖没(金重读 g≤R* → 谓词假)→ latch 保持
    st2 = _state(gold=45, r=5)
    _p2, d2 = evaluate_release(st2, s, _REG, 'FORM',
                               Posture(save=True, refresh_budget=3))
    assert d2 is d1
    # 轮键变化 → 失效
    st3 = _state(gold=45, r=6)
    _p3, d3 = evaluate_release(st3, s, _REG, 'FORM',
                               Posture(save=True, refresh_budget=3))
    assert d3 is None


# --- ⑥ release 义务预算有界放行 ------------------------------------------------


def test_release_budget_bounded_authorization() -> None:
    """累计刷金 ≤ 预算 ∧ 花后 ≥ boss_floor ∧ g≥0 硬钳制(ADR-0445,
    W477 执行层透支修复);预算耗尽即拒。
    W645 提案 E 后 authorize 增息档截断门(花后不跨 10 的倍数档):金位
    取档内值(62,余 2 ≥ 刷价)以隔离预算语义——旧值 60 是档界(余 0),
    在新语义下合法被截,不再能承载「预算内放行」的断言。
    W935 返修语义重推(锁红≠改动错;编排者裁决 2026-08-31):钳制账
    v3_release_spent 现为**全渠道共享**(买/升经 _accrue_release_frame_spend
    入账)——预算门从失明恢复为如实执行 ADR-0503 设计预算,危机帧全部
    渠道消费共同消耗 budget_gold;本锁的种子直接种共享账,语义
    「累计消费 ≤ 预算」与旧「累计刷金 ≤ 预算」在纯刷新帧等值。"""
    s = StrategySession()
    s.v3_release = ReleaseDirective(budget_gold=22, rolls=11)
    s.v3_release_spent = 0
    assert authorize_release_refresh(s, 62, 2, _REG)
    assert s.v3_release_spent == 2
    s.v3_release_spent = 21
    assert not authorize_release_refresh(s, 62, 2, _REG)   # 21+2 > 22
    s.v3_release_spent = 20
    assert authorize_release_refresh(s, 62, 2, _REG)       # 恰好贴满
    s.v3_release_spent = 0
    # boss_floor 独立生效:抬高 boss_floor 至 20,金 13(余 3 ≥ 刷价,
    # 不触截断门)花后 11 < 20 → 拒(旧值 11 在截断门下与地板门混叠)。
    import dataclasses as _dc
    _reg20 = _dc.replace(_REG, boss_floor=20)
    assert not authorize_release_refresh(s, 13, 2, _reg20)
    # g≥0 硬钳制:截断门落地后,「金 < 刷价」帧恒被截断门先拒
    # (gold<cost ≤10 ⇒ gold%10=gold<cost),钳制在本门成为纵深防御;
    # 断言保留拒绝事实,拒因如实标注为截断门(E 语义叠加,钳制仍在码)。
    _reg0 = _dc.replace(_REG, boss_floor=0)
    assert not authorize_release_refresh(s, 1, 2, _reg0)
    s.v3_release = None
    assert not authorize_release_refresh(s, 62, 2, _REG)


# --- ⑩ 成型帧末窗投影臂义务预算消费定向化 ---------------------------------------


def _form_boss_state(**kw) -> GameState:
    """成型帧末窗定向臂底座:SPEND 相位 + boss 窗 + 溢余段;其余同
    _state 默认(hp 不再入谓词,数值仅作判读语境)。"""
    return _state(gold=67, hp=38, plane=1, r=9, node='boss', **kw)


def _shop_card(name: str) -> object:
    from sr_od.application.currency_war.kernel.cw_state import ShopCard
    return ShopCard(name=name, faction='仙舟罗浮', cost=1, x=0, star=1)


def _target_name() -> str:
    from sr_od.application.currency_war.kernel.cw_system_cards import  engine_char_names
    return sorted(engine_char_names())[0]


def test_formed_projection_blind_refresh_denied() -> None:
    """定向化锁(盲刷拒):成型帧(phase=SPEND)末窗 FLIP 命中 →
    directive.directed_only=True;店内无可找件 → find_ok=False →
    authorize_release_refresh 拒(义务预算保留但盲刷不是合规消费)。"""
    st = _form_boss_state()
    s = _sess(st)
    d = release_directive(st, s, _REG, 'SPEND',
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
    st = _form_boss_state()
    st.shop = [_shop_card('无关件乙'), _shop_card(_target_name())]
    s = _sess(st)
    d = release_directive(st, s, _REG, 'SPEND',
                          Posture(save=False, level_up=False,
                                  refresh_budget=6))
    assert d is not None and d.directed_only is True and d.find_ok is True
    s.v3_release = d
    s.v3_release_spent = 0
    assert authorize_release_refresh(s, 62, 2, _REG)    # 档内金位(W645 E 截断门)
    assert s.v3_release_spent == 2


def test_unformed_projection_not_directed() -> None:
    """辖域边界:未成型帧(phase=FORM)末窗投影臂命中 → directed_only=False
    → 盲刷照旧放行(定向化只辖成型帧——未成型帧泄息语义由设计承载,
    本批不扩权)。"""
    st = _state(gold=67, hp=38, plane=1, r=9, node='boss')   # shop=[]
    s = _sess(st)
    d = release_directive(st, s, _REG, 'FORM',
                          Posture(save=False, level_up=False,
                                  refresh_budget=6))
    assert d is not None and d.directed_only is False and d.find_ok is True
    s.v3_release = d
    s.v3_release_spent = 0
    assert authorize_release_refresh(s, 62, 2, _REG)    # 档内金位(W645 E 截断门)


def test_third_path_directive_not_directed() -> None:
    """第三路径(slot 守卫注入)不辖定向化:其语义=防泄息通道静默关闭,
    定向化会重新造出静默面——third_path 帧盲刷照旧放行。"""
    st = _form_boss_state(deployed_n=5, bench_n=1)   # deployed<cap ∧ bench 有件
    assert slot_guard_blocks_level(st)
    s = _sess(st)
    d = release_directive(st, s, _REG, 'SPEND',
                          Posture(save=False, level_up=True,
                                  refresh_budget=0))
    assert d is not None and d.third_path is True
    assert d.directed_only is False and d.find_ok is True
    s.v3_release = d
    s.v3_release_spent = 0
    assert authorize_release_refresh(s, 62, 2, _REG)    # 档内金位(W645 E 截断门)


# --- ④⑤ spend_mode 状态机与 DP 合并语义 ---------------------------------


def test_spend_mode_release_has_no_producer() -> None:
    """锁C(负向网格):'release' 为预留档位,生产点 get_node_goal 恒不产。

    若未来有人在 horizon 层造出 release 生产者,本锁报警并把裁决拉回
    重新评估(单一源=decision_v2.posture_release 经 session 通道)。"""
    from sr_od.application.currency_war.kernel.cw_economy import get_node_goal
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
    """③生产缺陷修复(批 3 重推):level 分支不丢弃刷新预算——预算核下,
    息引擎已立(gold≥50)∧ 峰值级未达 → level 档且 refresh_budget 合法;
    息引擎未立(gold 8<50)→ interest 档([12] 息引擎前置,W615 R4 禁升①;
    旧锁钉的「DP 说升」前瞻行为随 DP 退役)。"""
    from sr_od.application.currency_war.kernel.cw_economy import get_node_goal
    g = get_node_goal(1, 1, gold=8, level=3, hp=80)
    assert g.spend_mode == 'interest'    # 息引擎未立:不排程不刷新
    g2 = get_node_goal(1, 1, gold=60, level=3, hp=80)
    assert g2.spend_mode == 'level'      # 息引擎立+峰值级(6)未达 → 排程
    assert isinstance(g2.refresh_budget, int) and 0 <= g2.refresh_budget <= 6


def test_fallback_node_goal_budget_none() -> None:
    """fallback NodeGoal refresh_budget=None(无 DP 信息,不参与合并)。"""
    from sr_od.application.currency_war.kernel.cw_economy import get_node_goal
    g = get_node_goal(1, 1)   # 部分传参 → 先验 fallback
    assert g.spend_mode == 'adaptive' and g.refresh_budget is None


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


# --- ⑨ release 活栈消费门(端到端;判据单一源=session.v3_release) --


def _gate_reg(_on: bool = True):
    """消费门恒接线(开关 release_spend_gate_enabled 已随 ADR-0426 增补 D
    第 4 态删除);保留参数形态兼容旧调用点,on/off 对照由
    session.v3_release 有无承载。"""
    return DEFAULT_REGISTRY


def _gate_session() -> StrategySession:
    """带 release 态的 session(判据单一源=session.v3_release,同生产链
    evaluate_release 的写入形态;开关臂对照=registry flag,两臂同带
    release 态)。"""
    s = StrategySession()
    s.v3_release = ReleaseDirective(budget_gold=8, rolls=4)
    return s


def test_release_chain_end_to_end_reachable(monkeypatch) -> None:
    """锁A(生产链可达性,端到端):FLIP 命中态直接驱动 decide_prep,
    session 通道活(tag='release' ∧ 义务预算≥溢余下界)——全程不 mock
    生产链本体(仅把刷新预算核钉为确定性授权 6 刷,预算期望本地复算;
    排程保持默认 level=6=False,R*=50)。"""
    from sr_od.application.currency_war.kernel import cw_economy
    from sr_od.application.currency_war.decision.decision_v2.strategy import  DecisionV2Strategy
    monkeypatch.setattr(cw_economy, 'refresh_ev_budget',
                        lambda *a, **k: 6)
    s = StrategySession()
    st = _state(gold=58, hp=35, r=5)   # FORM ∧ g>R*=50 溢余段
    s.shop_state_frame = st
    DecisionV2Strategy().decide_shop_screen(s, None)
    assert getattr(s, 'v3_dp_posture', None) is not None
    assert s.v3_dp_posture.posture.tag == 'release'
    d = getattr(s, 'v3_release', None)
    assert d is not None and d.budget_gold >= 8   # 溢余 8 金下界


def test_release_frame_blocks_interest_motivated_sells() -> None:
    """锁B(release 帧不卖息凑档):凑息向卖候选(off_target/for_gold)
    在 release 门开帧不生成;无 release 态同帧照产(对照证明抑制来自门
    本身)。帧取 hp=80 非应急(FLIP 帧语义由 session.v3_release 承载)。"""
    from sr_od.application.currency_war.decision.decision_v2.candidates import  generate_candidates
    st = _state(gold=58, hp=80, deployed_n=6)   # 板满:free_bench 不触发
    s_on = _gate_session()
    cands_on = generate_candidates(st, s_on, _gate_reg(True))
    assert not [c for c in cands_on
                if type(c.action).__name__ == 'SellBench']
    s_off = _gate_session()
    s_off.v3_release = None
    cands_off = generate_candidates(st, s_off, _gate_reg(True))
    assert [c for c in cands_off if type(c.action).__name__ == 'SellBench']


def test_release_gate_spares_free_bench_sell() -> None:
    """锁B 辖区边界:free_bench 腾位让位是 slot 动机非凑息动机,release
    门开仍生成(演进替换事务卖不经候选生成器,同条注释在
    candidates._release_sell_gate)。bench 件须为方向件——bench 满时
    非方向件先被 off_target 档截住(优先序),走不到腾位档;方向件用
    session.v3_hoard.char_targets 承载(体系引擎件受 sole_engine 守卫
    ≤2 份拦截,不适合本帧)。"""
    from sr_od.application.currency_war.decision.decision_v2.candidates import  generate_candidates
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
    from sr_od.application.currency_war.decision.decision_v2.scoring import score_state
    st = _state(gold=60, hp=80)
    sc_on = score_state(st, _gate_reg(True), _gate_session())
    assert sc_on['interest'] == 0.0
    sc_off = score_state(st, _gate_reg(True), StrategySession())
    assert sc_off['interest'] > 0.0


def _vd_p2_frame():
    """P2 入场 release 帧(卡芙卡 2费@lv6 j=2,金 80,刷价 5,rb=6):
    金 80 花 E×5 穿息档 → Δinterest≠0,V_D 的 C_dec 息损项有非零原料。"""
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    from sr_od.application.currency_war.kernel.cw_intention import IntentionState
    from sr_od.application.currency_war.decision.decision_v2.ev import RoundPosture
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
    from sr_od.application.currency_war.data.cw_shop_odds import  expected_refreshes_for_card
    from sr_od.application.currency_war.decision.decision_v2.ev import  cross_plane_remaining_nodes
    from sr_od.application.currency_war.decision.decision_v2.scoring import  vd_refresh_score
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


# ==================== p1_terminal_release ====================

import dataclasses as _p1_terminal_release_dataclasses
import logging

import pytest

from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _p1_terminal_release_StrategySession
from sr_od.application.currency_war.decision.decision_v2.discipline import  blood_budget_levelup_blocked, blood_budget_refresh_blocked, p1_directed_downgrade_active, terminal_release, terminal_release_bit, terminal_round_conversion_open, terminal_survival_upper_bound
from sr_od.application.currency_war.kernel.cw_registry import  DEFAULT_REGISTRY as _p1_terminal_release_DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import  BENCH_CAPACITY as _p1_terminal_release_BENCH_CAPACITY, BenchChar as _p1_terminal_release_BenchChar, GameState as _p1_terminal_release_GameState
from sr_od.application.currency_war.sim.checks.segments import  seg_check_p1_blood_budget_refresh, seg_terminal_release_ledger


@pytest.fixture(autouse=True)
def _quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 logging.disable 是全局态:pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(prev)


#: 闭式对拍基准值(=registry.streak_floor_win_rate 注入表直读,本表
#: 是 p_i 单一源;此处只做乘法,禁复制数值——漂移由表本身锁辖)


def _p1_state(hp: int = 10, round_num: int = 7, node: str = 'battle',
              gold: int = 120) -> _p1_terminal_release_GameState:
    st = _p1_terminal_release_GameState()
    st.plane, st.level, st.gold, st.hp = 1, 6, gold, hp
    st.round_num = round_num
    st.node_type = node
    return st


def _p1_terminal_release_sess(table: list[str] | None = None) -> _p1_terminal_release_StrategySession:
    s = _p1_terminal_release_StrategySession()
    s.plane_node_table = table if table is not None else ['battle'] * 9
    return s


def _board(state: _p1_terminal_release_GameState, names: list[str], star: int = 1) -> _p1_terminal_release_GameState:
    state.deployed = [_p1_terminal_release_BenchChar(slot=i + 1, char_id=n, faction='仙舟',
                                star=star)
                      for i, n in enumerate(names)]
    return state


# ---------- §5.2-4:S0 闭式对拍(公式正确性唯一承载面) ----------

def test_s0_empty_chain_is_one() -> None:
    """K=∅ → S0=1(hp=40 > 全档 L,无「一败即死」场;设计 §2.3 行进带
    上沿用例)——不触发语义的数学承载。"""
    s0 = terminal_survival_upper_bound(_p1_state(hp=40), _p1_terminal_release_sess(),
                                       _p1_terminal_release_DEFAULT_REGISTRY)
    assert s0 == pytest.approx(1.0)


def test_s0_single_boss_penetration() -> None:
    """单场穿透:hp=10、末轮仅剩 boss → K={boss},S0=p_boss(rung0)=0.077
    (table[8:9];r9 单场构造避开 ALL IN 语义只用于 S0 纯函数)。"""
    sess = _p1_terminal_release_sess(['battle'] * 8 + ['boss'])
    s0 = terminal_survival_upper_bound(_p1_state(hp=10, round_num=9), sess,
                                       _p1_terminal_release_DEFAULT_REGISTRY)
    assert s0 == pytest.approx(
        _p1_terminal_release_DEFAULT_REGISTRY.streak_floor_win_rate['boss'][0])


def test_s0_double_battle_chain() -> None:
    """两场穿透:hp=10、剩 2 场普通战斗(rung0)→ S0=0.009²(设计 §2.3
    弱板两链用例)。"""
    sess = _p1_terminal_release_sess(['battle'] * 7 + ['battle', 'battle'])
    s0 = terminal_survival_upper_bound(_p1_state(hp=10, round_num=8), sess,
                                       _p1_terminal_release_DEFAULT_REGISTRY)
    wr = _p1_terminal_release_DEFAULT_REGISTRY.streak_floor_win_rate['battle'][0]
    assert s0 == pytest.approx(wr * wr)


def test_s0_encounter_boss_chain_rung1() -> None:
    """双节点链(rung1,遭遇+boss 双穿透):S0=p_enc(rung1)×p_boss(rung1)
    ——非同质链逐节点取各自 p_i 的闭式对拍。"""
    sess = _p1_terminal_release_sess(['battle'] * 7 + ['encounter', 'boss'])
    st = _board(_p1_state(hp=10, round_num=8), ['艾丝妲', '椒丘'])
    s0 = terminal_survival_upper_bound(st, sess, _p1_terminal_release_DEFAULT_REGISTRY)
    wr = _p1_terminal_release_DEFAULT_REGISTRY.streak_floor_win_rate
    assert s0 == pytest.approx(wr['encounter'][1] * wr['boss'][1])


# ---------- §5.2-1:终止帧三断言一体(防释放扩散,FM-3) ----------

def test_terminal_frame_three_assertions() -> None:
    """行进带终止帧(hp=26 ∈ boss 单链域,rung1)→ refresh_blocked=False
    ∧ downgrade inactive;升级门该帧本就线外(hp>11)——停升级门不受
    终止豁免影响的深终止帧用例见下(hp=10)。"""
    sess = _p1_terminal_release_sess(['battle'] * 7 + ['encounter', 'boss'])
    st = _board(_p1_state(hp=26, round_num=8), ['艾丝妲', '椒丘'])
    assert terminal_release(st, sess, _p1_terminal_release_DEFAULT_REGISTRY)
    assert not blood_budget_refresh_blocked(st, sess, _p1_terminal_release_DEFAULT_REGISTRY)
    assert not p1_directed_downgrade_active(st, _p1_terminal_release_DEFAULT_REGISTRY,
                                            session=sess)


def test_deep_terminal_frame_levelup_still_blocked() -> None:
    """深终止帧(hp=10,弱板,K≥2)三断言一体(设计 §5.2-1):refresh_
    blocked=False ∧ downgrade inactive ∧ **levelup_blocked 仍 True**
    (hp=10≤P1 线 11;停升级门不在终止豁免辖内——P21 数学:濒死升级
    EV=−C−I 严格为负,与金是否零价值无关;FM-3 释放扩散回归锚)。"""
    sess = _p1_terminal_release_sess()
    st = _p1_state(hp=10)
    assert terminal_release(st, sess, _p1_terminal_release_DEFAULT_REGISTRY)
    assert not p1_directed_downgrade_active(st, _p1_terminal_release_DEFAULT_REGISTRY,
                                            session=sess)
    assert blood_budget_levelup_blocked(st, sess, _p1_terminal_release_DEFAULT_REGISTRY)


# ---------- §5.2-2:非终止帧零漂移 ----------

def test_nonterminal_frame_unchanged() -> None:
    """hp=40 强板(rung2,encounter L=19.79/boss L=26.71 均 <40 → K=∅)
    三门与现状逐位一致:刷新停付在、降格在、升级门不辖(线外)。"""
    sess = _p1_terminal_release_sess(['battle'] * 7 + ['encounter', 'boss'])
    st = _board(_p1_state(hp=40, round_num=8),
                ['艾丝妲', '椒丘', '三月七', '姬子'])
    assert not terminal_release(st, sess, _p1_terminal_release_DEFAULT_REGISTRY)
    assert blood_budget_refresh_blocked(st, sess, _p1_terminal_release_DEFAULT_REGISTRY)
    assert p1_directed_downgrade_active(st, _p1_terminal_release_DEFAULT_REGISTRY, session=sess)
    assert not blood_budget_levelup_blocked(st, sess, _p1_terminal_release_DEFAULT_REGISTRY)


# ---------- §5.2-3:不可信 hp 帧 fail-closed ----------

def test_untrusted_hp_fail_closed() -> None:
    """幽灵帧((False,False),镜像 hp_decision_trusted)→ 终止分支不
    触发,血预算带帧停付照旧(误放代价 > 误拦;设计 §2.1)。帧取
    hp=26 行进带 boss 单链域 + 双门开——若误判可信,该帧本应释放。"""
    sess = _p1_terminal_release_sess(['battle'] * 7 + ['encounter', 'boss'])
    st = _board(_p1_state(hp=26, round_num=8), ['艾丝妲', '椒丘'])
    st.hp_readable = False
    st.hp_trusted = False
    assert not terminal_release(st, sess, _p1_terminal_release_DEFAULT_REGISTRY)
    assert blood_budget_refresh_blocked(st, sess, _p1_terminal_release_DEFAULT_REGISTRY)
    assert p1_directed_downgrade_active(st, _p1_terminal_release_DEFAULT_REGISTRY, session=sess)


# ---------- 当轮转化双门(v2 R2) ----------

def test_conversion_dual_gate_matrix() -> None:
    """双门四象限:bench 空槽 ∧(deploy 空位 ∨ 1★ 垫底)才开;
    bench 满 / 板满全 2★ 关(板满帧不进释放辖域,维持停付)。"""
    reg = _p1_terminal_release_DEFAULT_REGISTRY
    empty_bench = _p1_state()
    assert terminal_round_conversion_open(empty_bench, reg)  # deploy 空位
    full_1star = _board(_p1_state(), ['a', 'b', 'c', 'd', 'e', 'f'], star=1)
    assert terminal_round_conversion_open(full_1star, reg)   # 1★ 垫底可换
    full_2star = _board(_p1_state(), ['a', 'b', 'c', 'd', 'e', 'f'], star=2)
    assert not terminal_round_conversion_open(full_2star, reg)
    bench_full = _board(_p1_state(), ['a', 'b', 'c', 'd', 'e', 'f'])
    bench_full.bench = [_p1_terminal_release_BenchChar(slot=i + 1, char_id=f'x{i}')
                        for i in range(_p1_terminal_release_BENCH_CAPACITY)]
    assert not terminal_round_conversion_open(bench_full, reg)


def test_dual_gate_holds_refresh_in_band() -> None:
    """血预算带帧(hp=26>应急线,rung1 boss 单链)双门关 → 刷新停付
    保持;双门开 → 终止豁免放行。关臂板面=满 6 人全 2★(rung1 由
    持续伤害对贡献,星级只影响垫底判据不影响引擎计数)。"""
    sess = _p1_terminal_release_sess(['battle'] * 7 + ['encounter', 'boss'])
    reg = _p1_terminal_release_DEFAULT_REGISTRY
    open_st = _board(_p1_state(hp=26, round_num=8), ['艾丝妲', '椒丘'])
    assert terminal_release(open_st, sess, reg)
    assert not blood_budget_refresh_blocked(open_st, sess, reg)
    closed_st = _board(_p1_state(hp=26, round_num=8),
                       ['艾丝妲', '椒丘', 'x1', 'x2', 'x3', 'x4'], star=2)
    assert terminal_release(closed_st, sess, reg)   # 谓词闩置位(触发域)
    assert blood_budget_refresh_blocked(closed_st, sess, reg)  # 双门关


# ---------- §5.2-6:滞回闩 + P2 硬门 ----------

def test_plane_latch_hysteresis_and_reset() -> None:
    """同位面 S0 跨 ε 抖动:hp=25 单 boss 链 rach1 触发(0.027≤ε)→
    闩置位;升板 rung2(S0=0.187>ε)同位面仍释放(不回退);切 P2 清零
    (P2 硬门恒 False,R6);回 P1 非 triggering 帧不再释放。"""
    sess = _p1_terminal_release_sess(['battle'] * 7 + ['encounter', 'boss'])
    reg = _p1_terminal_release_DEFAULT_REGISTRY
    weak = _board(_p1_state(hp=25, round_num=8), ['艾丝妲', '椒丘'])
    assert terminal_release(weak, sess, reg)
    strong = _board(_p1_state(hp=25, round_num=8),
                    ['艾丝妲', '椒丘', '三月七', '姬子'])
    assert terminal_survival_upper_bound(strong, sess, reg) > 0.03
    assert terminal_release(strong, sess, reg)   # 闩:邻域抖动不回退(R7)
    # 位面切换语义 = 闩按位面键控:P1 闩不辖 P2 帧;P2 帧被硬门(R6)
    # 恒拒且不置闩(位面 2 读位恒假)——不消费 P2 参数的第二判定源被
    # 门死。P1→P2 单向推进下「清零」即旧位面闩失效。
    p2 = _p1_state(hp=1, round_num=2)
    p2.plane = 2
    assert not terminal_release(p2, sess, reg)
    assert not terminal_release_bit(sess, 2)
    assert terminal_release_bit(sess, 1)   # P1 闩原样(只辖本位面)


def test_p2_hard_gate_zero_scope() -> None:
    """P2 帧(含极低 hp)恒不触发(R6:防不消费 P2 参数的第二判定源);
    开关 off=零辖域(两态注入面)。"""
    sess = _p1_terminal_release_sess()
    st = _p1_state(hp=1, round_num=2)
    st.plane = 2
    assert not terminal_release(st, sess, _p1_terminal_release_DEFAULT_REGISTRY)
    reg_off = _p1_terminal_release_dataclasses.replace(_p1_terminal_release_DEFAULT_REGISTRY,
                                  terminal_release_enabled=False)
    assert not terminal_release(_p1_state(hp=9), sess, reg_off)


def test_terminal_release_bit_single_source() -> None:
    """账本决策位单一址:闩位与 terminal_release_bit(plane) 逐位一致;
    异位面读位=假。"""
    sess = _p1_terminal_release_sess()
    assert not terminal_release_bit(sess, 1)
    assert terminal_release(_p1_state(hp=9), sess, _p1_terminal_release_DEFAULT_REGISTRY)
    assert terminal_release_bit(sess, 1)
    assert not terminal_release_bit(sess, 2)


# ---------- §5.2-5:一致性检查器两构造反例 ----------

def _ledger_row(rn: int, *, terminal: bool, refreshes: int = 0,
                rejects: int = 0, bench_n: int = 0,
                deployed: list[dict] | None = None) -> dict:
    return {
        'plane': 1, 'round_num': rn, 'hp': 30,
        'terminal_release': terminal,
        'sim': {'node': 'battle', 'blood_budget_refresh_rejects': rejects},
        'actions': ([{'__type__': 'RefreshShop', 'cost': 2}] * refreshes),
        'state': {'bench': [{'char_id': f'x{i}'} for i in range(bench_n)],
                  'cap': 6, 'deployed': deployed or []},
    }


def test_seg_refresh_uses_ledger_bit() -> None:
    """非终止位帧刷新 → 违规事件;终止位帧刷新 → 豁免不出(R4:检查器
    只验位,不复算 S0)。"""
    rows = [
        _ledger_row(6, terminal=False),
        _ledger_row(7, terminal=False, refreshes=1),   # 违规
        _ledger_row(8, terminal=True, refreshes=1),    # 终止豁免辖内
        _ledger_row(9, terminal=True, refreshes=0),
    ]
    ev = seg_check_p1_blood_budget_refresh(rows)
    assert [e['round_num'] for e in ev] == [7]


def test_seg_terminal_ledger_mismatch_both_directions() -> None:
    """一致性检查器:①终止位帧 + 刷新拒付 + 双门按行内快照可开 →
    账本错位事件;②双门关(板满全 2★)同构造 → 不出(合法辖内拒付);
    ③拒付=0 帧 → 不出。"""
    rows = [
        # 双门开(bench 空 ∧ deploy 空位)+ 位真 + 拒付 → 矛盾
        _ledger_row(7, terminal=True, rejects=1),
        # 双门关(板满全 2★)+ 位真 + 拒付 → 合法辖内拒付
        _ledger_row(8, terminal=True, rejects=2,
                    deployed=[{'star': 2}] * 6),
        # 位真无拒付 → 不出
        _ledger_row(9, terminal=True),
    ]
    ev = seg_terminal_release_ledger(rows)
    assert [e['round_num'] for e in ev] == [7]
    # bench 满同样构成双门关
    rows_bench_full = [
        _ledger_row(7, terminal=True, rejects=1, bench_n=_p1_terminal_release_BENCH_CAPACITY),
    ]
    assert seg_terminal_release_ledger(rows_bench_full) == []


# ---------- sim 账本披露键(单局冒烟,不锁分布) ----------

def test_sim_ledger_discloses_terminal_bit() -> None:
    """账本行 'terminal_release' 键存在(R4 记账面数据源;单局冒烟,
    pool='fallback' 免快照依赖)。"""
    from sr_od.application.currency_war.sim import engine_p1 as cw_sim
    r = cw_sim.simulate_p1(0, pool='fallback', planes=2)
    assert r.ledger
    for row in r.ledger:
        assert 'terminal_release' in row
        assert isinstance(row['terminal_release'], bool)


# ==================== w361_press_channel ====================

from dataclasses import replace
from types import SimpleNamespace as _w361_press_channel_SimpleNamespace

from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w361_press_channel_StrategySession
from sr_od.application.currency_war.decision.decision_v2 import candidates as _cands
from sr_od.application.currency_war.decision.decision_v2.arbiter import  _press_floor_exempt, arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import  _buy_tag, _copy_swap_blocked, generate_candidates
from sr_od.application.currency_war.decision.decision_v2.discipline import  observed_probs, press_band, press_channel_max_band, press_channel_open
from sr_od.application.currency_war.decision.decision_v2.scoring import  score_all, score_candidate
from sr_od.application.currency_war.kernel.cw_registry import  DEFAULT_REGISTRY as _w361_press_channel_DEFAULT_REGISTRY, DecisionV2Registry
from sr_od.application.currency_war.kernel.cw_state import  BenchChar as _w361_press_channel_BenchChar, BuyCard, GameState as _w361_press_channel_GameState, ShopCard

# armA 注入(V-B3:总闸;量控 cap 走各自字段默认值)
_ARMA = replace(_w361_press_channel_DEFAULT_REGISTRY, press_channel_enabled=True)

# 注入关臂:press 通道已正式开臂(默认 True,commit cb7688d4——W368
# A/B R2 验收);「通道关」行为锁改为显式注入,不再依赖默认值。
_ARM0 = replace(_w361_press_channel_DEFAULT_REGISTRY, press_channel_enabled=False)

# 方向外低费件(CW 注册表真值:刃=星核猎手/燃血,黑塔=群攻/银河学者;
# 均 ∉ 姬子列车方向 {仙舟,列车同行,持续伤害},∉ 插件库/引擎名单)
_FILLER = '刃'
_FILLER_FAC = '星核猎手'
_FILLER2 = '黑塔'
_FILLER2_FAC = '银河学者'


def _dep(name: str, faction: str, slot: int = 0) -> _w361_press_channel_SimpleNamespace:
    return _w361_press_channel_SimpleNamespace(char_id=name, faction=faction, star=1,
                           slot=slot, position_pref='back', equips=())


def _w361_press_channel_sess() -> _w361_press_channel_StrategySession:
    """锁线帧(方向=姬子列车,不含仙舟):生产路径形态——'copy'/'pair'
    既有豁免通道语义先于 press 臂(V-B2.1 放序),只有方向门拦下的
    目标外副本才落 'copy_press';裸 session 冷启动会让 pair_wants
    (同阵营/冷启动副本口)先命中。"""
    from sr_od.application.currency_war.kernel.cw_intention import  HoardTarget, IntentionState
    s = _w361_press_channel_StrategySession()
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {'姬子·启行'}
    s.target_comp = _w361_press_channel_SimpleNamespace(factions=('列车同行',),
                                    core_chars=('姬子·启行',))
    return s


def _w361_press_channel_state(**kw) -> _w361_press_channel_GameState:
    base = {'plane': 1, 'round_num': 2, 'gold': 15, 'level': 3,
            'board': {}, 'deployed': [_dep(_FILLER, _FILLER_FAC)],
            'bench': [], 'shop': [], 'hp': 80}
    base.update(kw)
    return _w361_press_channel_GameState(**base)


def _w361_press_channel_shop_card(name: str = _FILLER, cost: int = 1, x: int = 1) -> ShopCard:
    return ShopCard(x=x, faction=_FILLER_FAC, name=name, cost=cost)


# ------------------------------------------------------- V-B1 守卫收拢


def test_guard_synth_point_single_source() -> None:
    """V-B1:收拢后生成层与守卫合成点对探针态逐位一致——
    arm0 守卫拦=无候选;armA 豁免臂开=守卫放行且候选产出
    (V-B1.5「探针态必须产出候选」空臂红线)。"""
    sess = _w361_press_channel_sess()
    st = _w361_press_channel_state(shop=[_w361_press_channel_shop_card()])
    assert _copy_swap_blocked(st.shop[0], st, sess, _ARM0)
    assert _FILLER not in {c.action.card.name
                           for c in generate_candidates(st, sess,
                                                        _ARM0)
                           if isinstance(c.action, BuyCard)}
    assert not _copy_swap_blocked(st.shop[0], st, sess, _ARMA)
    got = [c for c in generate_candidates(st, sess, _ARMA)
           if isinstance(c.action, BuyCard)
           and c.action.card.name == _FILLER]
    assert got, '探针态下 armA 必须产出 press-band 副本候选(空臂红线)'
    assert got[0].tag == 'copy_press'


def test_guard_zero_drift_arms_unchanged() -> None:
    """V-B1 收拢是行为保持重构:①target 豁免臂语义不变(关=直通拦);
    ②C 臂(末窗 gap>0)放行不变;通道默认关下 press 臂不参与。
    (原 ② A 臂=filler_star_unit>0 放行,已随 ADR-0402 定谳清理删除,
    deployed 名副本放行现由 C 臂/press 臂承载。)
    """
    sess = _w361_press_channel_sess()
    st = _w361_press_channel_state(shop=[_w361_press_channel_shop_card()])
    # ① target 豁免(青雀非目标件,开关无效,守卫仍拦)——注入关臂
    # 隔离 press 豁免臂(开臂后默认注册表已带 press 臂)
    assert _copy_swap_blocked(st.shop[0], st, sess,
                              replace(_ARM0,
                                      copy_swap_target_exempt=True)) is True
    # ② C 臂:r≥handoff_gate_min_round 且 gap>0 → 放行(锁线帧 gap)
    s2 = _w361_press_channel_sess()
    st_c = _w361_press_channel_state(round_num=7, shop=[_w361_press_channel_shop_card()])
    reg_c = replace(_ARM0, handoff_gate_min_round=6)
    assert not _copy_swap_blocked(st_c.shop[0], st_c, s2, reg_c)


# ------------------------------------------------- V-B2 tag/评分路由


def test_tag_registration_and_priority_position() -> None:
    """V-B2.1/V-B3:'copy_press' 进 buy_tag_priority(置于 'copy' 之后)
    band 外/通道关不产生标签。"""
    prio = _w361_press_channel_DEFAULT_REGISTRY.buy_tag_priority
    assert 'copy_press' in prio
    assert prio.index('copy_press') == prio.index('copy') + 1
    st = _w361_press_channel_state(shop=[_w361_press_channel_shop_card()])
    sess = _w361_press_channel_sess()
    # 通道关(注入):无标签(开臂后默认注册表通道开,copy_press 激活)
    assert _buy_tag(st.shop[0], st, sess, _ARM0) is None
    # 通道开:copy_press
    assert _buy_tag(st.shop[0], st, sess, _ARMA) == 'copy_press'
    # bench 满:E03 门字面(〔W300 口述〕「囤满备战席→没位置」)
    st_full = _w361_press_channel_state(shop=[_w361_press_channel_shop_card()],
                     bench=[_w361_press_channel_BenchChar(slot=i, char_id=f'杂{i}',
                                      faction=_FILLER_FAC)
                            for i in range(_w361_press_channel_DEFAULT_REGISTRY.bench_capacity)])
    assert _buy_tag(st.shop[0], st_full, sess, _ARMA) is None
    # 同轮已卖守卫:r408 不回买
    s2 = _w361_press_channel_sess()
    s2.v2_round_key = (1, 2)
    s2.v2_round_sold = {_FILLER}
    assert _buy_tag(st.shop[0], st, s2, _ARMA) is None


def test_press_scoring_route_cleaned_hygiene() -> None:
    """定谳清理卫生锁(ADR-0427 增补节,策略开关生命周期第 4 态):
    ① 评分路由两字段已删(not hasattr);② 通道价值主体健在——
    总闸/双 cap 字段/[11] 豁免臂谓词;③ 删除后 copy_press 候选与
    删除前默认态(press_copy_unit=0.0)行为一致——探针态下正分可达
    (板面 depth 维自带 +2,与已删路由无关),通道行为面零漂移。"""
    assert not hasattr(DecisionV2Registry, 'press_copy_unit')
    assert not hasattr(DecisionV2Registry, 'press_core_mirror_bonus')
    assert _w361_press_channel_DEFAULT_REGISTRY.press_channel_enabled is True
    assert _w361_press_channel_DEFAULT_REGISTRY.press_copy_round_cap == 1
    assert _w361_press_channel_DEFAULT_REGISTRY.press_exempt_round_cap == 2
    sess = _w361_press_channel_sess()
    st = _w361_press_channel_state(shop=[_w361_press_channel_shop_card()])
    cands = [c for c in generate_candidates(st, sess, _ARMA)
             if isinstance(c.action, BuyCard)
             and c.action.card.name == _FILLER]
    assert cands and cands[0].tag == 'copy_press'
    val, _bd = score_candidate(cands[0], st, sess, _ARMA)
    assert val > 0


def test_observable_reject_reason_never_guard_or_zero_score() -> None:
    """V-B2.3 可观测行为断言:armA 探针态下该卡产生买候选;若被拒,
    拒因 ∉ {copy_swap 守卫(候选不存在), 非正分}。评分路由删除
    (ADR-0427 增补节)不改本面:板面 depth 维自带正分,非正分拒
    仍是异常信号。"""
    sess = _w361_press_channel_sess()
    st = _w361_press_channel_state(shop=[_w361_press_channel_shop_card()])
    cands = generate_candidates(st, sess, _ARMA)
    got = [c for c in cands if isinstance(c.action, BuyCard)
           and c.action.card.name == _FILLER]
    assert got, 'V-B2.3:该卡必须产生买候选'
    scored = score_all(cands, st, sess, _ARMA)
    res = arbitrate(scored, st, sess, _ARMA)
    row = next(r for r in res.log if r['desc'].startswith(f'买 {_FILLER}'))
    if not row['accepted']:
        assert '非正分' not in (row['reject'] or ''), \
            f'拒因=非正分(异常,depth 维应给正分): {row}'
    assert got[0].tag == 'copy_press'


# ------------------------------------------- V-B3/V-B5 band 推导与停机


def test_band_derivation_and_authority_override() -> None:
    """V-B5.2:[30] 开域覆盖(lv1-6 band={1,2},lv4 不再是推导孤值);
    lv≥7 纯推导(lv7={1,2,3});自洽闸参照系 press_band(6)={1,2}。"""
    reg = _w361_press_channel_DEFAULT_REGISTRY
    for lv in (1, 2, 3, 4, 5, 6):
        assert press_band(lv, None, reg) == {1, 2}, f'lv{lv}'
    assert press_channel_max_band(reg) == {1, 2}
    assert press_band(7, None, reg) == {1, 2, 3}
    assert press_band(8, None, reg) == {1, 2, 3}


def test_band_observed_probs_priority() -> None:
    """V-B5.3 轮岗盲区:observed 概率条优先于基线行(签名
    press_band(level, probs));取不到退 REFRESH_PROB 基线。"""
    reg = _w361_press_channel_DEFAULT_REGISTRY
    # lv5 轮岗翻 2 费(2 费 p≈0.56 单档即过半):observed band 自动含 2 费
    rotation = {1: 0.15, 2: 0.56, 3: 0.22, 4: 0.05, 5: 0.02}
    assert 2 in press_band(5, rotation, reg)
    # observed 优先:翻 1 费时 1 费单档过半,band 截断含 {1,2}(开域覆盖)
    rot1 = {1: 0.60, 2: 0.22, 3: 0.15, 4: 0.02, 5: 0.01}
    assert press_band(5, rot1, reg) == {1, 2}
    # state.refresh_probs 披露域 → observed_probs 读取
    st = _w361_press_channel_state()
    assert observed_probs(st) is None
    st.refresh_probs = rotation
    assert observed_probs(st) == rotation


def test_channel_shutdown_conditions() -> None:
    """V-A2/V-B5 停机:plane≠1 关;lv>max 关;带自洽闸破(lv7)关;
    轮岗 observed 推出 3 费进带时保守关。"""
    reg = _w361_press_channel_DEFAULT_REGISTRY
    st = _w361_press_channel_state()
    assert press_channel_open(st, reg)
    assert not press_channel_open(_w361_press_channel_state(plane=2), reg)
    assert not press_channel_open(_w361_press_channel_state(level=7), reg)
    # observed 使推导带破 {1,2}(3 费累计过半)→ 自洽闸保守关
    st_rot = _w361_press_channel_state()
    st_rot.refresh_probs = {1: 0.10, 2: 0.20, 3: 0.55, 4: 0.10, 5: 0.05}
    assert not press_channel_open(st_rot, reg)


def test_registry_press_defaults_zero_drift() -> None:
    """V-B3 默认值锁:press_channel_enabled 已正式开臂(默认 True,
    commit cb7688d4——W368 A/B R2 验收;「默认全关零漂移」旧锁随开臂
    失效,通道关行为改由 _ARM0 注入锁);其余参保持中性值。评分偏置
    两字段的删除锁在 test_press_scoring_route_cleaned_hygiene。"""
    assert _w361_press_channel_DEFAULT_REGISTRY.press_channel_enabled is True
    assert _w361_press_channel_DEFAULT_REGISTRY.press_band_cum_threshold == 0.50
    assert _w361_press_channel_DEFAULT_REGISTRY.press_channel_max_level == 6
    assert _w361_press_channel_DEFAULT_REGISTRY.press_copy_round_cap == 1
    assert _w361_press_channel_DEFAULT_REGISTRY.press_exempt_round_cap == 2


# ------------------------------------------------- V-B6 插件臂撤销


def test_out_of_band_grayout_both_arms() -> None:
    """V-B6:E05/E07 band 外副本(cost=3)两臂都不产出候选
    (V-A3 插件臂已撤销,「才考虑」不实现为购买分支)。"""
    sess = _w361_press_channel_sess()
    st = _w361_press_channel_state(deployed=[_dep(_FILLER2, _FILLER2_FAC)],
                shop=[_w361_press_channel_shop_card(_FILLER2, 3, x=1)])
    for reg in (_w361_press_channel_DEFAULT_REGISTRY, _ARMA):
        assert _copy_swap_blocked(st.shop[0], st, sess, reg)
        assert _FILLER2 not in {c.action.card.name
                                for c in generate_candidates(st, sess, reg)
                                if isinstance(c.action, BuyCard)}
    # V-B7:第二序不存在——registry 无 COPY_PRIORITY 字段
    assert not [f for f in DecisionV2Registry.__dataclass_fields__
                if 'priority' in f and f != 'buy_tag_priority'
                and f != 'sell_tag_priority']


# ------------------------------------------------------- V-B8 逐轮 cap


def test_press_floor_exempt_cap_and_ruling() -> None:
    """V-B8:[11] 三相位前置臂——同档/1费放行(保息档线不保
    form_floor 本金,gold=19/cost=9 击穿地板亦放行);逐轮 cap 超限
    失效;通道关/跨档/应急态不放行。"""
    reg_on = replace(_w361_press_channel_DEFAULT_REGISTRY, press_channel_enabled=True)
    sess = _w361_press_channel_sess()
    st = _w361_press_channel_state(gold=19)
    working = st
    cand = BuyCard(_w361_press_channel_shop_card(_FILLER, 9), reason='')
    probe = _cands.Candidate(action=cand, tag='bridge_core', source='shop')
    # 9 费跨档?19//10=1,10//10=1 → 同档;cost=1 恒放。同档账:
    # (19-9)//10=1 >= 19//10=1 → 放行(击穿 20 地板至息档线,V-B8.2)
    auth: dict = {}
    assert _press_floor_exempt(probe, working, st, sess, reg_on, auth)
    assert 'press_floor_exempt' in auth
    # 通道关(注入 _ARM0):不放行(开臂后默认注册表通道开)
    assert not _press_floor_exempt(probe, working, st, sess,
                                   _ARM0)
    # 跨档有息损:不放行(gold=19, cost=19 → 0//10=0 < 1)
    cand_cross = BuyCard(_w361_press_channel_shop_card(_FILLER, 19), reason='')
    probe_cross = _cands.Candidate(action=cand_cross, tag='bridge_core',
                                   source='shop')
    assert not _press_floor_exempt(probe_cross, working, st, sess, reg_on)
    # 逐轮 cap:超 press_exempt_round_cap 后豁免失效
    sess.v2_round_press_exempt = reg_on.press_exempt_round_cap
    assert not _press_floor_exempt(probe, working, st, sess, reg_on)


def test_press_copy_round_cap_in_arbitration() -> None:
    """V-B8.1:press 候选逐轮采纳 ≤ press_copy_round_cap(默认 1)。
    评分以定值正分手工注入(与评分维解耦——cap 量控语义的独立锁
    不依赖任何评分偏置通道;原 filler_star_unit 注入已随 ADR-0402
    定谳清理删除)。"""
    reg = _ARMA
    sess = _w361_press_channel_sess()
    st = _w361_press_channel_state(deployed=[_dep(_FILLER, _FILLER_FAC),
                          _dep(_FILLER2, _FILLER2_FAC, slot=1)],
                shop=[_w361_press_channel_shop_card(_FILLER, 1, x=1),
                      _w361_press_channel_shop_card(_FILLER2, 1, x=2)])
    cands = [c for c in generate_candidates(st, sess, reg)
             if isinstance(c.action, BuyCard)]
    assert len(cands) == 2, '两笔 press 候选都应生成'
    scored = [(c, 5.0,
               {'cost': getattr(getattr(c.action, 'card', None),
                                'cost', 2) or 2})
              for c in cands]
    res = arbitrate(scored, st, sess, reg)
    accepted = [r for r in res.log if r['tag'] == 'copy_press'
                and r['accepted']]
    rejected = [r for r in res.log if r['tag'] == 'copy_press'
                and not r['accepted']]
    assert len(accepted) == reg.press_copy_round_cap
    assert any('press_copy_cap' in (r['reject'] or '') for r in rejected)


# ------------------------------------------- V-B9 检查器 is_dup 双域


def _seg_row(cards: list[dict], deployed: list[dict],
             bench: list[dict] | None = None) -> dict:
    """合成段级账本行(g0=13<20 同息档,未成型,未停手)。"""
    return {
        'plane': 1, 'round_num': 1, 'gold': 13, 'hp': 60,
        'formed_stop': False,
        'state': {'board_factions': {}, 'deployed': deployed,
                  'bench': bench or [], 'cap': 4, 'level': 4},
        'target_comp': '',
        'actions': [],
        'sim': {'node': 'battle',
                'income': {'base': 5, 'interest': 0, 'streak': 0,
                           'event': 1},
                'spend': {'buys': {}, 'levelup': 0, 'refresh': 0,
                          'sell_income': 0},
                'bench_full_skipped_buys': 0,
                'shop_waves': [{'event': 'offer', 'gold': 13,
                                'cards': cards}]},
    }


def test_checker_dup_dual_domain() -> None:
    """V-B9:deployed 同名压库副本未买 → 通道关非违规(披露
    copy_press_channel_closed);bench-only 同名 → 披露
    copy_bench_only_skipped 不进真拦;非重复散件(C-D)照报真拦。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_line_defs import  ENGINE_FACTIONS
    # 分包期 6 八切:检查段 corpus/decision_v2/segments 归 sim.checks 子包
    from sr_od.application.currency_war.sim.checks import  corpus, decision_v2, segments
    name = next(n for n, c in CHARACTERS.items()
                if c.cost == 1
                and set(c.factions or ()) & set(ENGINE_FACTIONS))
    cards = [{'name': name, 'cost': 1, 'faction': '?'}]
    # deployed 同名(通道开=新默认,commit cb7688d4):未买=C-B 真拦
    # (通道开转正=买家被授权买;旧「通道关转披露 copy_press_channel_
    # closed」语义由 seg_copy_press_disclosure 在通道关注册表下保留)
    row_dep = _seg_row(cards, deployed=[{'char_id': name}])
    evs_dep = segments.seg_check_lossless_buy_missed([row_dep])
    assert evs_dep and evs_dep[0]['class'] == 'C-B', evs_dep
    assert not segments.seg_copy_press_disclosure([row_dep])
    # bench-only 同名:披露不进真拦(V-B9.3)
    row_bench = _seg_row(cards, deployed=[],
                         bench=[{'char_id': name}])
    assert not segments.seg_check_lossless_buy_missed([row_bench])
    disc = segments.seg_copy_press_disclosure([row_bench])
    assert disc and disc[0]['kind'] == 'copy_bench_only_skipped'
    # 非重复散件(C-D):真拦语义保持
    row_plain = _seg_row(cards, deployed=[])
    evs = segments.seg_check_lossless_buy_missed([row_plain])
    assert evs and evs[0]['class'] == 'C-D'
    assert not segments.seg_copy_press_disclosure([row_plain])


def test_transition_cost_max_single_source() -> None:
    """V-A2:检查器成本带上限 import 买家侧单一源
    press_channel_max_band()(={1,2} 的 max=2,无数值漂移)。"""

    from sr_od.application.currency_war.sim.checks.segments import _seg_transition_cost_max
    assert _seg_transition_cost_max() == 2
    assert _seg_transition_cost_max() == max(
        press_channel_max_band(_w361_press_channel_DEFAULT_REGISTRY))


# ------------------------------------------------- 供给一致性探针接线


def test_supply_consistency_probe_includes_w300() -> None:
    """V-B1.3:检查网总表含 press 通道探针;供给一致性探针与
    check_w300_press_channel_probe 均零违规(现行为回归面)。"""
    # 分包期 6 八切:检查段归 sim.checks 子包(同 test_checker_dup_dual_domain)
    from sr_od.application.currency_war.sim.checks import  corpus, decision_v2, segments
    r1 = decision_v2.check_decision_v2_supply_label_consistency()
    assert r1['violations'] == 0, r1['detail']
    r2 = corpus.check_w300_press_channel_probe()
    assert r2['violations'] == 0, r2['detail']


# ==================== w653_c7_zero_drift ====================

import inspect

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_recipe import decision_target
from sr_od.application.currency_war.kernel.cw_state import GameState as _w653_c7_zero_drift_GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w653_c7_zero_drift_StrategySession


def _w653_c7_zero_drift_sess() -> _w653_c7_zero_drift_StrategySession:
    s = _w653_c7_zero_drift_StrategySession()
    s.target_comp = next(c for c in COMP_LIBRARY if c.name == '专家桑博DOT')
    return s


def test_fw_empty_returns_target_regardless_of_dual_flag():
    """零漂移主锁:fw≡''(v2 生产恒态)→ 两分支同返回 target_comp,
    与 state.dual_track_phase 取值无关(dual flag 任意塞值不改变结果)。"""
    sess = _w653_c7_zero_drift_sess()
    for flag in (False, True):
        st = _w653_c7_zero_drift_GameState(plane=1, round_num=3, dual_track_phase=flag)
        assert decision_target(sess, st) is sess.target_comp


def test_fw_set_not_committed_returns_recipe():
    """双轨语义保留(fw 已定 + 未定型 → 配方伪 comp;sim/决策链消费)。"""
    sess = _w653_c7_zero_drift_sess()
    sess.transition_framework = '仙舟'
    st = _w653_c7_zero_drift_GameState(plane=1, round_num=3)
    assert decision_target(sess, st).name == '过渡·仙舟配方'


def test_fw_set_committed_returns_final_comp():
    """定型(plane≥2 权威派生)→ 终局 comp,即使 fw 字段残留非空。"""
    sess = _w653_c7_zero_drift_sess()
    sess.transition_framework = '仙舟'
    st = _w653_c7_zero_drift_GameState(plane=2, round_num=1)
    assert decision_target(sess, st) is sess.target_comp


def test_no_intention_supply_defaults_not_committed():
    """变异锁:拔掉意向供给(无 v3_intention,P1)→ committed_from 落
    保守 False → 配方分支可达(禁缺省 True=恒按定型=配方静默丢失)。"""
    sess = _w653_c7_zero_drift_sess()
    sess.transition_framework = '列车'
    st = _w653_c7_zero_drift_GameState(plane=1, round_num=3)
    assert decision_target(sess, st).name == '过渡·列车配方'


def test_decision_target_no_longer_reads_dual_track_phase():
    """源级守卫:decision_target 不再直读 state.dual_track_phase
    (换源后读点归零,回滑即红)。"""
    import re

    import sr_od.application.currency_war.kernel.cw_recipe as m
    src = inspect.getsource(m.decision_target)
    assert not re.search(r"state\s*\.\s*dual_track_phase|"
                         r"getattr\(\s*state\s*,\s*'dual_track_phase'", src)


# ==================== w645_tier_truncation ====================

from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w645_tier_truncation_StrategySession
from sr_od.application.currency_war.decision.decision_v2.economy_cycle import  tier_truncated_spend
from sr_od.application.currency_war.decision.decision_v2.posture_release import  ReleaseDirective as _w645_tier_truncation_ReleaseDirective, authorize_release_refresh as _w645_tier_truncation_authorize_release_refresh
from sr_od.application.currency_war.kernel.cw_registry import  DEFAULT_REGISTRY as _w645_tier_truncation_DEFAULT_REGISTRY

_w645_tier_truncation_REG = _w645_tier_truncation_DEFAULT_REGISTRY
_COST = 2    # 刷价(与 _state.shop_refresh_cost 同值)


def _directive(budget: int, *, find_ok: bool = True) -> _w645_tier_truncation_ReleaseDirective:
    return _w645_tier_truncation_ReleaseDirective(budget_gold=budget, rolls=budget // _COST,
                            third_path=False, reason='flip',
                            directed_only=False, find_ok=find_ok)


def _sess_with_directive(budget: int) -> _w645_tier_truncation_StrategySession:
    s = _w645_tier_truncation_StrategySession()
    s.v3_release = _directive(budget)
    s.v3_release_spent = 0
    return s


# --- ①②③ 纯函数 tier_truncated_spend ------------------------------------------


def test_tier_trunc_in_tier_no_cut() -> None:
    """① 档内不截断:gold%10 ≥ want 时原额放行(62 金余 12→2?不,62%10=2;
    取 gold=68 余 8 ≥ want=5 → 5)。"""
    assert tier_truncated_spend(68, 5, essential=False) == 5
    assert tier_truncated_spend(67, 6, essential=False) == 6


def test_tier_trunc_cross_tier_cut_and_carry() -> None:
    """② 跨档截断+结转:gold=63(余 3),want=5(一刷 2 金可刷两次多一档)
    → 截断返回 3 < 5 = 本笔不放行,3 金余量结转下轮。"""
    got = tier_truncated_spend(63, 5, essential=False)
    assert got == 3
    assert got < 5    # 调用契约:返回值 < want = 不放行


def test_tier_trunc_essential_both_branches_uncut() -> None:
    """③ essential=True 两枝不截断:正账件(买牌)与 M-A 定向刷新车道
    同为原额——gold%10=0 也不截(截断=定向搜索永久丢失/弃购,不在辖内)。"""
    assert tier_truncated_spend(60, 5, essential=True) == 5
    assert tier_truncated_spend(60, 5, essential=False) == 0    # 对照枝
    assert tier_truncated_spend(0, 9, essential=True) == 9


# --- ④⑤ _w645_tier_truncation_authorize_release_refresh 截断门组合 -----------------------------------


def test_release_gate_residual_below_cost_rejected() -> None:
    """④ 残差不足一刷停止收尾:预算 10、金 63(余 3 ≥ 刷价?不,刷价 2
    ≤ 3 可刷)→ 改用金 61(余 1 < 刷价 2):预算内仍拒=截断门收口。"""
    s = _sess_with_directive(10)
    assert _w645_tier_truncation_authorize_release_refresh(s, 61, _COST, _w645_tier_truncation_REG) == ''


def test_release_gate_residual_sufficient_passes() -> None:
    """④ 对照:预算 10、金 68(余 8 ≥ 刷价 2)→ 放行,累计扣账=刷价。"""
    s = _sess_with_directive(10)
    note = _w645_tier_truncation_authorize_release_refresh(s, 68, _COST, _w645_tier_truncation_REG)
    assert note != ''
    assert s.v3_release_spent == _COST


def test_release_gate_budget_semantics_unchanged() -> None:
    """⑤ 与既有预算语义组合不回归:预算耗尽(spent+cost > budget)仍拒,
    截断门不放松预算界。"""
    s = _sess_with_directive(4)
    s.v3_release_spent = 4
    assert _w645_tier_truncation_authorize_release_refresh(s, 68, _COST, _w645_tier_truncation_REG) == ''


def test_release_gate_boss_floor_semantics_unchanged() -> None:
    """⑤ 花后 ≥ boss_floor 下限仍在截断门之后独立生效:金 61(余 1)、
    预算充足,即使残差门若被绕过,地板门照拒——三门各自独立,次序
    预算→截断→地板。"""
    s = _sess_with_directive(10)
    # 金 51:余 1 < 刷价 → 截断门先拒(地板也拒,断言拒绝事实即可)
    assert _w645_tier_truncation_authorize_release_refresh(s, 51, _COST, _w645_tier_truncation_REG) == ''
    # 同金位提高刷价余量对比:金 58(余 8 ≥ 2)但花后 56 ≥ boss_floor
    # (registry.p1_boss_floor=20)→ 放行,证明地板门不是本用例拒因。
    s2 = _sess_with_directive(10)
    assert _w645_tier_truncation_authorize_release_refresh(s2, 58, _COST, _w645_tier_truncation_REG) != ''


def test_release_gate_directed_only_still_rejects_blind() -> None:
    """⑤ 定向化拒盲刷语义不回归(directed_only ∧ find_ok=False):截断门
    追加不改变既有定向化判定次序。"""
    s = _w645_tier_truncation_StrategySession()
    s.v3_release = _directive(10, find_ok=False)
    s.v3_release_spent = 0
    d = _w645_tier_truncation_ReleaseDirective(budget_gold=10, rolls=5, third_path=False,
                         reason='flip', directed_only=True, find_ok=False)
    s.v3_release = d
    assert _w645_tier_truncation_authorize_release_refresh(s, 68, _COST, _w645_tier_truncation_REG) == ''
