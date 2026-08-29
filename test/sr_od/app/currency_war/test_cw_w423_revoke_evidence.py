"""W423 · R3 撤销出口①意图证据单帧锁。

设计=唯一规格:`.debug/temp/currency_war/w396_r2r3_design/DESIGN.md` R3 节
(治 W386 BP1「门放行噪声换线」:拍死计数把核心短时缺货的正常噪声送进撤销)。

锁面:
- C1 三条件合取锁(缺一不开窗):miss 达标+证据齐→开窗;miss 达标+
  无异线资产→不开窗;miss 达标+异线核心不可达→不开窗;miss 未达+证据
  齐→不开窗;
- C2 N_req 推导锁(闭式 N_req=⌈ln ε/ln(1−q)⌉ 代入例:3 费@lv5=
  42;单调性/ε 缩放/未识别角色退化);
- C3 A_min 基线锁(registry 值=冻结池 f0 曲线 5% 点测量值 5.0)与
  厚度边界行为(5.5 开窗 / 4.0 不开窗);
- C4 零漂移锚:缺省 registry 常量=W379 off 臂逐位的结构前提(出口①
  在 sim 结构性零触发 → off 臂全分布不变);证据字段经
  serialize_intention 落遥测(实机判读锚:无证据字段的开窗=守卫失效)。
"""
from __future__ import annotations

import dataclasses
import math

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_intention import (
    CORE_MISS_N,
    IntentionState,
    core_miss_n_required,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState, ShopCard
from sr_od.application.currency_war.kernel.cw_intention import serialize_intention
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

#: 证据组 B 厚度边界夹具(异线「万敌单C」=v2 家族载体,
#: core=[万敌,千冶·刃,长夜月,刻律德菈,缇宝];骨架重叠=千冶·刃/
#: 刻律德菈/缇宝,每件 ×0.5):
#: 4 终局件 → 厚度 4+1.0=5.0 = A_min(开);3 终局件 → 3+0.5=3.5 <5(不开)。
THK_ABOVE = ['万敌', '千冶·刃', '长夜月', '刻律德菈']
THK_BELOW = ['万敌', '长夜月', '刻律德菈']
#: 异线核心不可达夹具:资产够厚(4 终局件+骨架=5.5)但核心万敌不在手,
#: P3 末轮剩余节点 < 再遇窗口 → _core_reachable=False。
THK_UNREACHABLE = ['千冶·刃', '长夜月', '刻律德菈', '缇宝']


def _state(**kw) -> GameState:
    s = GameState()
    s.plane = kw.get('plane', 2)
    s.round_num = kw.get('round_num', 1)
    s.level = kw.get('level', 5)
    for name in kw.get('shop', []):
        ch = CHARACTERS.get(name)
        s.shop.append(ShopCard(x=len(s.shop), name=name,
                               faction=ch.factions[0] if ch and ch.factions
                               else '?',
                               cost=ch.cost if ch else 3))
    for name in kw.get('bench', []):
        ch = CHARACTERS.get(name)
        s.bench.append(BenchChar(slot=len(s.bench), char_id=name,
                                 faction=ch.factions[0] if ch and ch.factions
                                 else '?',
                                 star=kw.get('bench_star', 1)))
    return s


def _locked_xier() -> IntentionState:
    ist = update_intention(_state(shop=['希儿']), IntentionState())
    assert ist.locked_comp == '希儿量子'
    return ist


def _n_req_default(core: str, level: int = 5) -> int:
    return core_miss_n_required(
        core, level, DEFAULT_REGISTRY.revoke_miss_tolerance_eps)


def _drive_to(ist: IntentionState, frame: GameState,
              target_miss: int) -> IntentionState:
    """推 miss 计数到 target_miss(核心缺席帧逐轮驱动;状态机就地改)。"""
    for _ in range(target_miss):
        update_intention(frame, ist)
    return ist


# --- C1 三条件合取锁 -----------------------------------------------------------


def test_c1_miss_threshold_with_evidence_opens() -> None:
    """miss 达 max(CORE_MISS_N, N_req) ∧ 异线资产证据 → 开窗降弱意向。"""
    ist = _locked_xier()
    frame = _state(bench=THK_ABOVE)
    total = max(CORE_MISS_N, _n_req_default('希儿'))
    out = _drive_to(ist, frame, total)
    assert out.phase == 'weak' and out.weak_comp == '希儿量子'
    assert out.last_event.startswith('revoke:miss')
    assert out.revoke_evidence['alt_comp'] == '万敌单C'


def test_c1_miss_threshold_without_alt_asset_stays_locked() -> None:
    """miss 达标 ∧ 无异线在场资产 → 不开窗(缺证据组 B,噪声不进撤销)。"""
    ist = _locked_xier()
    frame = _state()
    total = max(CORE_MISS_N, _n_req_default('希儿'))
    out = _drive_to(ist, frame, total + 3)
    assert out.phase == 'locked'
    assert out.tracks['希儿量子'].miss_count == total + 3   # 计数继续,不弃


def test_c1_miss_threshold_alt_core_unreachable_stays_locked() -> None:
    """miss 达标 ∧ 异线厚但核心不可达(P3 末轮剩余节点 < 再遇窗口)
    → 不开窗(证据组 A 的异线可达半边缺)。"""
    ist = _locked_xier()
    frame = _state(plane=3, round_num=9, bench=THK_UNREACHABLE)
    total = max(CORE_MISS_N, _n_req_default('希儿'))
    out = _drive_to(ist, frame, total + 3)
    assert out.phase == 'locked'


def test_c1_miss_below_threshold_with_evidence_stays_locked() -> None:
    """miss 未达(证据已在场)→ 不开窗:断供强度是必要条件,资产在场
    不单独构成意图。"""
    ist = _locked_xier()
    frame = _state(bench=THK_ABOVE)
    total = max(CORE_MISS_N, _n_req_default('希儿'))
    out = _drive_to(ist, frame, total - 1)
    assert out.phase == 'locked'


# --- C2 N_req 推导锁 -----------------------------------------------------------


def test_c2_n_req_worked_example_cost3_lv5() -> None:
    """闭式代入例(锁定表值,表或公式漂移即碎):3 费@lv5,
    refresh_prob=0.20 → r=0.20/14,q=1−(1−r)^5≈0.0693,
    N_req=⌈ln 0.05/ln(1−q)⌉=⌈41.71⌉=42。"""
    from sr_od.application.currency_war.data.cw_shop_odds import (
        DISTINCT_CARDS_PER_COST,
        refresh_prob,
    )
    p = refresh_prob(5, 3)
    assert p == 0.20
    r = p / DISTINCT_CARDS_PER_COST[3]
    q = 1.0 - (1.0 - r) ** 5
    assert 0.0692 < q < 0.0695
    assert math.ceil(math.log(0.05) / math.log(1.0 - q)) == 42
    assert core_miss_n_required('希儿', 5, 0.05) == 42


def test_c2_n_req_monotone_and_eps_scaling() -> None:
    """方向锁:高概率窗要求更少轮(3 费@lv7=21 < @lv5=42);
    ε 收紧要求更多轮(ε=1% → 65);未识别角色退化=上限保险 CORE_MISS_N。"""
    assert core_miss_n_required('希儿', 7, 0.05) == 21
    assert core_miss_n_required('希儿', 5, 0.01) == 65
    assert core_miss_n_required('不存在角色', 5, 0.05) == CORE_MISS_N


# --- C3 A_min 基线锁 -----------------------------------------------------------


def test_c3_a_min_registry_value_is_measured_baseline() -> None:
    """A_min=冻结池 f0 曲线 5% 点测量值(协议与实测曲线见 registry 注释
    与测量产物 a_min_measurement.json):f0(4)=7.68%>5%,f0(5)=1.27%≤5%
    → 5.0。改值必须重跑测量协议,禁拍值。"""
    assert DEFAULT_REGISTRY.revoke_evidence_min_thickness == 5.0


def test_c3_thickness_boundary_around_a_min() -> None:
    """边界行为:异线厚度 5.5(≥5)→ 开窗;4.0(<5)→ 不开窗。"""
    total = max(CORE_MISS_N, _n_req_default('希儿'))
    ist = _drive_to(_locked_xier(), _state(bench=THK_BELOW), total)
    assert ist.phase == 'locked'
    ist2 = _drive_to(_locked_xier(), _state(bench=THK_ABOVE), total)
    assert ist2.phase == 'weak'


# --- C4 零漂移锚 + 证据字段遥测 -------------------------------------------------


def test_c4_default_registry_off_arm_structural_anchor() -> None:
    """零漂移锚的结构前提:缺省 registry 的 C4 门默认关(W379 off 臂)
    且新常量只收紧出口①(触发集 ⊆ 旧触发集,出口①在 sim 结构性零触发
    → off 臂全分布与 W379 off 臂逐位相等;测量脚本 zero_drift_baseline
    逐位比对为批级证据,此处锁常量前提)。"""
    assert DEFAULT_REGISTRY.line_switch_survival_gate_enabled is False
    assert DEFAULT_REGISTRY.revoke_miss_tolerance_eps == 0.05
    assert dataclasses.replace(
        DEFAULT_REGISTRY, revoke_miss_tolerance_eps=0.01
    ).revoke_miss_tolerance_eps == 0.01   # A/B 注入臂可达(dataclasses.replace)


def test_c4_evidence_fields_reach_telemetry() -> None:
    """开窗证据字段落 serialize_intention(实机判读锚:无证据字段的开窗
    =守卫失效,判读即报警;设计 R3.5)。"""
    total = max(CORE_MISS_N, _n_req_default('希儿'))
    ist = _drive_to(_locked_xier(), _state(bench=THK_ABOVE), total)
    d = serialize_intention(ist)
    assert d is not None
    ev = d['revoke_evidence']
    assert ev['kind'] == 'miss' and ev['n_req'] == total
    assert ev['alt_comp'] == '万敌单C' and ev['q'] > 0
    assert ev['asset_thickness'] >= ev['a_min']

