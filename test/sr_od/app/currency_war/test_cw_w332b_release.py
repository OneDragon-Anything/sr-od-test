"""W332b 未成型期姿态批单帧锁(泄息通道 release / 预算三方合并 / 换线判据)。

设计=唯一规格:`.debug/temp/currency_war/w328_unformed_posture/DESIGN.md`;
ADR-0445(经济循环总模型)后 FLIP 谓词简化为溢余判定,相关锁已按新语义
重推重写(旧血量/辖域语义已被取代,见各锁 docstring)。
锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① FLIP 谓词边界(ADR-0445 版):辖区=溢余段 g>R* ∧ C_t>0 ∧ 非应急;
  血量维度退场(hp/可信位不再评估)、全位面辖(P3 并入)、相位无关;
  g≤R*(息线以内)零漂移=不 fire(I-1 锚);
- ② 预算三方合并:FLIP 命中帧 budget = max(义务 min(溢余,C_t),
  DP 预算×刷价);DP 已有授权不缩水;义务被通道容量封顶(A-1 刀法);
- ③ slot 守卫第三路径:末窗 deployed<cap ∧ bench 非空 → rush_level 压掉,
  显式注入泄息预算(溢余基=R*;g≤R* 帧无溢余不注入);非末窗/满员不辖;
- ④ spend_mode 状态机:'release' 为预留档位无生产者(负向网格锁);
  v1 _maybe_sell_for_interest 的 allin/level 跳卖契约保留(adaptive 对照);
- ⑤ DP 合并语义:level 分支不再丢弃 DP refresh_budget(随
  NodeGoal 下传);fallback NodeGoal refresh_budget=None(不参与合并);
- ⑨ release 活栈消费门(端到端):锁A 生产链可达(FLIP→decide_prep→
  session.v3_release/tag);锁B release 帧凑息向卖候选抑制(free_bench
  腾位卖不受辖——slot 动机非凑息动机;演进替换事务卖不经候选生成器);
  锁D 息 EV 中性(spend_gate_active 判据;开关 release_spend_gate_enabled
  已随 ADR-0426 增补 D 删除,消费门恒接线);锁E V_D 的 C_dec 息损项
  中性(同判据,scoring.vd_refresh_score P2 分支);
- ⑥ release 义务预算的有界放行:累计 ≤ 预算 ∧ 花后 ≥ boss_floor
  ∧ g≥0 硬钳制(ADR-0445);
- ⑦ latch 单窗:同轮内命中后不回退,跨轮失效;
- ⑧ 换线判据:E_rounds 有限性 / θ 滞回 / D_min 驻留 / 双 inf 维持 /
  末窗辖域门;
- ⑩ 成型帧末窗义务预算消费定向化:预算保留但只许花在找件(店内存在
  名集件)/升级(不经本门),盲刷拒;未成型帧与第三路径注入不辖。
"""
from __future__ import annotations

import dataclasses
import math
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_economy import NodeGoal
from sr_od.application.currency_war.kernel.cw_plane_table import (
    level_cost,
)
from sr_od.application.currency_war.decision.decision_v2.posture import Posture
from sr_od.application.currency_war.kernel.cw_line_switch import (
    e_rounds,
    should_switch_e,
    switch_allowed,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.ev import RoundPosture
from sr_od.application.currency_war.decision.decision_v2.posture_release import (
    ReleaseDirective,
    authorize_release_refresh,
    evaluate_release,
    flip_hit,
    release_directive,
    slot_guard_blocks_level,
    wrap_posture,
)
from sr_od.application.currency_war.kernel.cw_registry import (
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
    在新语义下合法被截,不再能承载「预算内放行」的断言。"""
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
    from sr_od.application.currency_war.kernel.cw_system_cards import (
        engine_char_names,
    )
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


def test_sell_for_interest_skip_list_contract(monkeypatch) -> None:
    """v1 动作消费者跳卖契约保留:allin 档不卖息凑档;adaptive 档同帧照卖
    (对照证明跳过来自档位而非别的门)。'release' 档映射已删(预留档位
    无生产者;活栈消费门=⑨ 锁B)。"""
    from sr_od.application.currency_war.strategy_v1 import cw_plan
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
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


def test_plan_merges_dp_budget_into_refresh_cap(monkeypatch) -> None:
    """三方合并消费侧(许可取交):DP 预算 1 < _refresh_cap 2 → 合并后 1。"""
    from sr_od.application.currency_war.strategy_v1 import cw_plan
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
    from sr_od.application.currency_war.decision.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    monkeypatch.setattr(cw_economy, 'refresh_ev_budget',
                        lambda *a, **k: 6)
    s = StrategySession()
    st = _state(gold=58, hp=35, r=5)   # FORM ∧ g>R*=50 溢余段
    DecisionV2Strategy().decide_prep(st, s, None)
    assert getattr(s, 'v3_dp_posture', None) is not None
    assert s.v3_dp_posture.posture.tag == 'release'
    d = getattr(s, 'v3_release', None)
    assert d is not None and d.budget_gold >= 8   # 溢余 8 金下界


def test_release_frame_blocks_interest_motivated_sells() -> None:
    """锁B(release 帧不卖息凑档):凑息向卖候选(off_target/for_gold)
    在 release 门开帧不生成;无 release 态同帧照产(对照证明抑制来自门
    本身)。帧取 hp=80 非应急(FLIP 帧语义由 session.v3_release 承载)。"""
    from sr_od.application.currency_war.decision.decision_v2.candidates import (
        generate_candidates,
    )
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
    from sr_od.application.currency_war.decision.decision_v2.candidates import (
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
    from sr_od.application.currency_war.data.cw_shop_odds import (
        expected_refreshes_for_card,
    )
    from sr_od.application.currency_war.decision.decision_v2.ev import (
        cross_plane_remaining_nodes,
    )
    from sr_od.application.currency_war.decision.decision_v2.scoring import (
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
