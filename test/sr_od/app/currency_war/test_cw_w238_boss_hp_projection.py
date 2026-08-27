"""W238/ADR-0403:承接门 hp 维 boss 投影单帧锁(设计件 09 §3.1 第一步)。

锁面(结构面;分布面=A/B sim 批):
- 常数表:档键域/正值/深板方向(桶 15 期望伤害 < 桶 12——板深效应
  方向锁,不锁标定小数位);
- 盲区修复(run28/31/33 型):r8 hp 22-33 ∧ 板面 tier1 局 → 投影臂
  gap≥1 / 现投影(gate 无投影)臂 gap=0——设计件 09 §2 盲区类的
  行为差证据行;
- 弱板局两臂同值(min 由板面维压死,投影不改变 gap 数值);
- r8 +2 / r9 无 +2(hp_proj 直读);缺桶 fallback;
- 正交性:仅投影开(门关)= 零行为(gap 恒 0);
- sim 侧:账本 handoff_hp_proj 字段(投影开非 None/关 None);A/B
  proj_only 臂整局逐位=基线臂(两 flag 正交);非末窗零漂移。
n 取断言成立最小值;sim 结构断言用 fallback 池(README 纪律)。
"""
from __future__ import annotations

import json
import logging
from dataclasses import replace

from sr_od.application.currency_war import cw_sim
from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_intention import (
    IntentionState,
    intention_core,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    _merge_bench,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.handoff import (
    boss_projected_hp,
    handoff_gate_gap,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

logging.disable(logging.CRITICAL)

_GATE_OFF = DEFAULT_REGISTRY
_GATE_ON = replace(DEFAULT_REGISTRY, handoff_gate_enabled=True)
_PROJ_ON = replace(_GATE_ON, handoff_boss_project=True)
_PROJ_ONLY = replace(DEFAULT_REGISTRY, handoff_boss_project=True)


def _blindspot_frame(hp: int = 30, **kw) -> GameState:
    """run 28/31/33 型盲区帧:锁定成型(DOT 队,核心 2★ → 板面 tier1)
    P1 r8,hp 22-33 临界带(现投影 hp_tier=1 → 总档 1 → 门不触发;
    boss 后真值投影 hp_tier=0 → 总档 0 → 触发)。"""
    comp = get_comp('DOT队')
    core = intention_core(comp)
    base = {
        'plane': 1, 'round_num': 8, 'gold': 55, 'level': 5, 'hp': hp,
        'board': dict(comp.form_tiers),
        'deployed': [BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                               star=2),
                     BenchChar(slot=1, char_id='桑博', faction='仙舟罗浮',
                               star=1)],
        'bench': [], 'shop': [], 'node_type': 'battle',
    }
    base.update(kw)
    return GameState(**base)


def _sess_locked() -> StrategySession:
    s = StrategySession()
    s.v3_intention = IntentionState(phase='locked', locked_comp='DOT队')
    s.v3_mode = 'economy'
    return s


# ---------- ① 常数表(标定方向锁;小数位不锁,重标定随 ADR 更新) ----------

def test_boss_e_damage_table_shape() -> None:
    """档键域=Δ池 boss 板深桶域 {9,12,15};正值(=期望掉血量);
    深板方向:桶 15 < 桶 12(板面输出越高 boss 伤越小,run 26 型)。"""
    tbl = DEFAULT_REGISTRY.handoff_boss_e_damage
    assert set(tbl) == {9, 12, 15}
    assert all(v > 0 for v in tbl.values())
    assert tbl[15] < tbl[12], '深板桶期望伤害应更小(设计件 09 §1.1)'
    assert DEFAULT_REGISTRY.handoff_boss_e_damage_default > 0


# ---------- ② 盲区修复(run28/31/33 型行为差) ----------

def test_blindspot_gap_projection_triggers() -> None:
    """r8 hp 22-33 ∧ 板面 tier1:现投影臂 gap=0(盲区)/投影臂 gap≥1
    (触发);投影 hp 披露写入 session(ADR-0403 判读面)。"""
    for hp in (22, 30, 33):
        st = _blindspot_frame(hp=hp)
        s_gate, s_proj = _sess_locked(), _sess_locked()
        assert handoff_gate_gap(st, s_gate, _GATE_ON) == 0, (
            f'hp={hp}:现投影臂不应触发(盲区类——hp_tier=1∧板面 tier1)')
        assert handoff_gate_gap(st, s_proj, _PROJ_ON) >= 1, (
            f'hp={hp}:投影臂应触发(boss 后投影 hp 归 hp_tier 0)')
        assert 0 <= s_proj.v3_handoff_hp_proj <= 20, (
            '临界带投影 hp 应落 hp_tier=0 档(≤20)')


def test_weak_board_both_arms_same_gap() -> None:
    """弱板局(板面 tier0):两臂 gap 同值——min 由板面维压死,投影
    不改变 gap 数值(设计件 09 §2「弱板局投影修正不改变 gap」)。"""
    st = _blindspot_frame(hp=15)
    st = replace(st, deployed=[
        BenchChar(slot=0, char_id='卡芙卡', faction='仙舟罗浮', star=1),
        BenchChar(slot=1, char_id='桑博', faction='仙舟罗浮', star=1)])
    s_gate, s_proj = _sess_locked(), _sess_locked()
    g_gate = handoff_gate_gap(st, s_gate, _GATE_ON)
    g_proj = handoff_gate_gap(st, s_proj, _PROJ_ON)
    assert g_gate == g_proj >= 1


# ---------- ③ 投影公式(r8 +2 / r9 无 / 缺桶 fallback / 钳制) ----------

def test_projection_formula_round_bonus_and_fallback() -> None:
    """r8 加奖励 +2、r9 不加;表外板深档走 default;hp_proj 钳 [0,100]。
    构造:Σboard 落表外桶(如 3→桶 3)→ dmg=default(27.33):
    r8: round(30+2−27.33)=5;r9: round(30−27.33)=3。"""
    st8 = GameState(plane=1, round_num=8, gold=50, level=5, hp=30,
                    board={'仙舟': 3}, deployed=[], bench=[], shop=[],
                    node_type='battle')
    st9 = replace(st8, round_num=9)
    assert boss_projected_hp(st8, 30, _PROJ_ON) == 5
    assert boss_projected_hp(st9, 30, _PROJ_ON) == 3
    # 表内桶(Σboard 12 → 桶 12,dmg=30.35):r8 round(30+2−30.35)=2
    st12 = replace(st8, board={'仙舟': 12})
    assert boss_projected_hp(st12, 30, _PROJ_ON) == 2
    # 钳制:低 hp 不为负 / 高 hp 不破百
    assert boss_projected_hp(st8, 0, _PROJ_ON) == 0
    assert boss_projected_hp(st8, 200, _PROJ_ON) == 100


def test_projection_flag_off_zero_drift() -> None:
    """正交性:仅投影开(门关)恒 0;两 flag 全关恒 0(=基线逐位的
    结构前提);投影 hp 披露不写。"""
    st = _blindspot_frame(hp=30)
    s = _sess_locked()
    assert handoff_gate_gap(st, s, _GATE_OFF) == 0
    assert handoff_gate_gap(st, s, _PROJ_ONLY) == 0
    assert getattr(s, 'v3_handoff_hp_proj', None) is None


# ---------- ④ 缺口②实证:Σboard 键 vs 升星方向(声明边界的证据锁) ----------

def test_merge_reduces_board_sum_direction_gap() -> None:
    """3合1 升星消耗场上副本 → Σboard 下移(ADR-0403 已知边界实证):
    Δ池 boss 桶键=Σboard,升星使键落更浅桶,而浅桶期望伤害更大
    (test ① 方向锁)→ sim 判「升星→boss 伤害↑」与 [27] 机制相反。
    本锁钉死机制面:合并后 Σboard 必减(表更浅桶的方向前提)。"""
    deployed = [BenchChar(slot=i, char_id='卡芙卡', faction='仙舟罗浮',
                          star=1) for i in range(3)]
    bench: list[BenchChar | None] = []
    _merge_bench(bench, deployed)
    assert deployed[0].star == 2   # 载体升星
    board_after = sum(1 for d in deployed if d is not None)
    assert board_after == 1, '三副本合并后场上件数 3→1(Σboard −2)'
    # 池桶方向对照:快照 boss plane=1 桶均值浅桶 > 深桶(迁移=更痛)
    pool_map, _fp, _label = cw_sim.resolve_pool('snapshot')
    boss_p1 = pool_map.get('boss', {}).get(1, {})
    means = {b: sum(v) / len(v) for b, v in boss_p1.items() if v}
    assert means, '快照 boss plane=1 桶不应为空(标定源)'
    assert min(means) < max(means), '桶间应有差异(方向可判)'


# ---------- ⑤ sim 侧:账本披露 + proj_only 整局正交 + 非末窗零漂移 ----------

def test_sim_ledger_projection_disclosure() -> None:
    """投影开臂账本轮行带 handoff_hp_proj(末窗非 None);关臂恒 None
    (零漂移披露面)。"""
    from sr_od.application.currency_war.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    on = cw_sim.simulate_p1(0, pool='fallback', planes=2,
                            strategy=DecisionV2Strategy(registry=_PROJ_ON))
    off = cw_sim.simulate_p1(0, pool='fallback', planes=2)
    assert all('handoff_hp_proj' in row for row in on.ledger)
    on_rows = [row for row in on.ledger
               if row.get('plane') == 1 and row['round_num'] >= 8]
    assert any(row['handoff_hp_proj'] is not None for row in on_rows), (
        '末窗轮投影 hp 应披露(非 None)')
    assert all(row.get('handoff_hp_proj') is None for row in off.ledger)


def test_ab_proj_only_full_identity_and_zero_drift() -> None:
    """A/B(n=4 最小):proj_only(仅投影开)整局 ledger 与基线臂逐位
    一致(两 flag 正交结构证据);gate/proj 臂 P1 非末窗零漂移。"""
    rep = cw_sim.simulate_handoff_ab(4, pool='fallback', seed_base=0)
    assert rep['proj_only_orthogonality']['ok']
    assert rep['p1_zero_drift']['ok']
    assert 'blindspot' in rep and rep['blindspot']['rounds'] >= 0
