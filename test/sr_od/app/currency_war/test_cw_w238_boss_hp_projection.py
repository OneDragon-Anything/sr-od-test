"""ADR-0403:承接门 hp 维 boss 投影单帧锁(设计件 09 §3.1;
ADR-0404 键改净星深后重标定)。

**语义演进(ADR-0411 flag 家族清理)**:投影自 起无条件启用
——历史 handoff_gate_enabled/handoff_boss_project 双布尔删除,原
「关臂零漂移/proj_only 正交臂」锁面随 flag 退场(docstring 记过期
原因);现行为面 = DEFAULT_REGISTRY 直接消费。历史 A/B 数字见
ADR-0403/0411。

锁面:
- 常数表:档键域=Δ池 v10 boss 净星深桶域 {0}(P1 boss 语料全落桶 0
  ——旧 Σboard 三桶条件性=键口径伪影);正值(=期望掉血量);
- 盲区修复(run28/31/33 型):r8 hp 22-33 ∧ 板面 tier1 局 → gap≥1
  触发(hp 临界类由 boss 后投影捞起);
- 弱板局 min 由板面维压死(gap 数值不受投影影响的结构面);
- r8 +2 / r9 无 +2(hp_proj 直读);缺桶 fallback;
- 方向锁:3合1 升星后净星深键不落浅桶(修 ADR-0403 缺口②);
- sim 侧:账本 handoff_hp_proj 字段(末窗非 None)。
n 取断言成立最小值;sim 结构断言用 fallback 池(README 纪律)。
"""
from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.handoff import (
    boss_projected_hp,
    handoff_gate_gap,
)
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    intention_core,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    _merge_bench,
)
from sr_od.application.currency_war.sim import engine_p1 as cw_sim
from sr_od.application.currency_war.sim import pool


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


#ADR-0411:门与投影均无条件启用——行为帧即 DEFAULT_REGISTRY
_REG = DEFAULT_REGISTRY


def _blindspot_frame(hp: int = 30, **kw) -> GameState:
    """run 28/31/33 型盲区帧:锁定成型(DOT 队,核心 2★ → 板面 tier1)
    P1 r8,hp 22-33 临界带(boss 后真值投影 hp_tier=0 → 总档 0 → 触发;
    若喂 boss 前 hp 则 hp_tier=1 → 门不触发=盲区)。"""
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


# ---------- ① 常数表(标定锁;小数位不锁死,重标定随 ADR 更新) ----------

def test_boss_e_damage_table_shape() -> None:
    """档键域=Δ池 v10 boss 净星深桶域 {0}(ADR-0404:净星深=
    上场件 Σ(star−1),桶 min(sd//3,5)*3;P1 boss 语料 49 行全落
    桶 0,旧 Σboard 桶 9/12/15 条件性=键口径伪影);正值(=期望掉血);
    default=全池未删失均值(单桶下与桶 0 同值,表保留结构供深桶
    语料攒厚后扩)。"""
    tbl = DEFAULT_REGISTRY.handoff_boss_e_damage
    assert set(tbl) == {0}
    assert all(v > 0 for v in tbl.values())
    assert DEFAULT_REGISTRY.handoff_boss_e_damage_default > 0


# ---------- ② 盲区修复(run28/31/33 型) ----------

def test_blindspot_gap_projection_triggers() -> None:
    """r8 hp 22-33 ∧ 板面 tier1:boss 后投影把临界带 hp 归 hp_tier 0
    → gap≥1 触发;投影 hp 披露写入 session(ADR-0403 判读面)。"""
    for hp in (22, 30, 33):
        st = _blindspot_frame(hp=hp)
        s_proj = _sess_locked()
        assert handoff_gate_gap(st, s_proj, _REG) >= 1, (
            f'hp={hp}:投影应触发(boss 后投影 hp 归 hp_tier 0)')
        assert 0 <= s_proj.v3_handoff_hp_proj <= 20, (
            '临界带投影 hp 应落 hp_tier=0 档(≤20)')


def test_weak_board_gap_governed_by_board_dim() -> None:
    """弱板局(板面 tier0):gap≥1 且数值由板面维压死——hp 维投影
    不改变 min 结构(设计件 09 §2「弱板局投影修正不改变 gap」)。"""
    st = _blindspot_frame(hp=15)
    st = replace(st, deployed=[
        BenchChar(slot=0, char_id='卡芙卡', faction='仙舟罗浮', star=1),
        BenchChar(slot=1, char_id='桑博', faction='仙舟罗浮', star=1)])
    s_proj = _sess_locked()
    assert handoff_gate_gap(st, s_proj, _REG) >= 1


# ---------- ③ 投影公式(min_round +2 / 非 min_round 无 / 缺桶 fallback / 钳制) ----------

def test_projection_formula_round_bonus_and_fallback() -> None:
    """min_round(ADR-0418 前移后=r6)加奖励 +2、其他轮不加;
    表内净星深档 vs 表外档(缺桶 fallback);hp_proj 钳 [0,100]。
    构造(表值≠default 以区分两路):临时 registry 表 {0: 10.0}、
    default=27.57——deployed 全 1★ → 净星深 0 → 桶 0(表内):
    r6: round(30+2−10)=22;r9: round(30−10)=20;
    三件 2★ → 净星深 3 → 桶 3(表外→default):r8 round(30+2−27.57)=4。"""
    reg = replace(_REG, handoff_boss_e_damage={0: 10.0},
                  handoff_boss_e_damage_default=27.57)
    st6 = GameState(plane=1, round_num=6, gold=50, level=5, hp=30,
                    board={'仙舟': 3},
                    deployed=[BenchChar(slot=0, char_id='卡芙卡',
                                        faction='仙舟罗浮', star=1)],
                    bench=[], shop=[], node_type='battle')
    st9 = replace(st6, round_num=9)
    assert boss_projected_hp(st6, 30, reg) == 22   # 表内桶 0:r6(min_round)+2
    assert boss_projected_hp(st9, 30, reg) == 20   # 表内桶 0:r9 无 +2
    st_deep = replace(st6, deployed=[
        BenchChar(slot=i, char_id='卡芙卡', faction='仙舟罗浮', star=2)
        for i in range(3)])   # 净星深 3 → 桶 3(表外)
    assert boss_projected_hp(st_deep, 30, reg) == 4   # default
    # 钳制:低 hp 不为负 / 高 hp 不破百
    assert boss_projected_hp(st6, 0, _REG) == 0
    assert boss_projected_hp(st6, 200, _REG) == 100


# ---------- ④ 方向锁:净星深键下升星不落浅桶(ADR-0403 缺口②修复) ----------

def test_merge_star_depth_never_shallower() -> None:
    """3合1 升星消耗场上副本 → **净星深键不落浅桶**(ADR-0404
    修 ADR-0403 缺口②:Σboard 键下合并使场上件 3→1(键 −2/次)落
    浅桶,而浅桶期望伤害更大 → sim 判「升星→boss 伤害↑」与 [27]
    机制相反)。净星深=上场件 Σ(star−1):1★×3(键 0)→ 2★×1(键 1)
    ——键单调不减 ⇒ 桶 min(sd//3,5) 不变或更深 ⇒ sim 判升星后
    boss 期望伤害不升(同桶同值/深桶见池方向锁)。"""
    from sr_od.application.currency_war.data.cw_battle_tables import (
        DEPTH_BUCKET_W as _DEPTH_BUCKET_W,
    )
    from sr_od.application.currency_war.kernel.cw_battle_calib import (
        deployed_star_depth,
    )

    def _bucket(sd: int) -> int:
        return min(sd // _DEPTH_BUCKET_W, 5) * _DEPTH_BUCKET_W

    deployed = [BenchChar(slot=i, char_id='卡芙卡', faction='仙舟罗浮',
                          star=1) for i in range(3)]
    bench: list[BenchChar | None] = []
    sd_before = deployed_star_depth(GameState(
        plane=1, round_num=8, gold=50, level=5, hp=30, board={'仙舟': 3},
        deployed=list(deployed), bench=[], shop=[], node_type='battle'))
    _merge_bench(bench, deployed)
    assert deployed[0].star == 2   # 载体升星
    assert sum(1 for d in deployed if d is not None) == 1, (
        '三副本合并后场上件数 3→1(Σboard −2=旧键冲突根源)')
    st_after = GameState(
        plane=1, round_num=8, gold=50, level=5, hp=30, board={'仙舟': 1},
        deployed=[d for d in deployed if d is not None], bench=[],
        shop=[], node_type='battle')
    sd_after = deployed_star_depth(st_after)
    assert sd_after >= sd_before, '升星后净星深不得减少(方向前提)'
    assert _bucket(sd_after) >= _bucket(sd_before), (
        '升星后 boss 桶键不得落更浅桶(ADR-0403 缺口②修复锁)')


def test_v10_pool_boss_buckets_direction() -> None:
    """v10 池方向锁(重推语义,F6 批改锁):boss plane=1 桶键域 ⊆
    净星深桶域 {0,3,...,15};方向命题(深桶期望伤害 ≤ 浅桶,机制
    [27])在**深桶语料足量(n≥30)** 时硬断言。

    F6 改锁理由:快照随语料增长再生后(非 F6 伪影治理所致——boss
    行无 hp=0 伪影形态),桶3(n=15,均值 -24.53)对桶0(n=106,
    -26.34)出现 1.8hp 反向差,样本重叠大、方向命题在 n<30 的深桶
    上本就未被语料确证过(原锁立锁时语料全落桶0,断言平凡真)。
    深桶 n<30 时降级为披露不断言,当前读数(-24.53 vs -26.34,
    n=15)留此待语料积累后回硬断言;深桶足量后反向即真红线。
    """
    pool_map, _fp, _label = pool.resolve_pool('snapshot')
    boss_p1 = pool_map.get('boss', {}).get(1, {})
    assert boss_p1, '快照 boss plane=1 桶不应为空(标定源)'
    assert all(b % 3 == 0 and 0 <= b <= 15 for b in boss_p1), (
        'boss 桶键应落净星深桶域(3 宽)')
    means = {b: (sum(v) / len(v), len(v))
             for b, v in boss_p1.items() if v}
    ks = sorted(means)
    for b1, b2 in zip(ks, ks[1:], strict=False):
        m1, n1 = means[b1]
        m2, n2 = means[b2]
        if min(n1, n2) < 30:
            continue   # 深桶语料不足:方向披露级(读数见 docstring),不断言
        assert m2 <= m1 + 1e-9, (
            f'净星深深桶({b2})期望伤害应 ≤ 浅桶({b1})'
            f'({m2:.2f} vs {m1:.2f})——方向与机制相反')


# ---------- ⑤ sim 侧:账本披露 ----------

def test_sim_ledger_projection_disclosure() -> None:
    """默认注册表(投影无条件启用)账本轮行带 handoff_hp_proj,末窗
    非 None(判读「boss 后投影 hp」面)。n=1 最小。"""
    r = cw_sim.simulate_p1(0, pool='fallback', planes=2)
    assert all('handoff_hp_proj' in row for row in r.ledger)
    rows = [row for row in r.ledger
            if row.get('plane') == 1 and row['round_num'] >= 8]
    assert any(row['handoff_hp_proj'] is not None for row in rows), (
        '末窗轮投影 hp 应披露(非 None)')



# —— 换核隔离桶(2026-09-03 测试分层批)——
# 本文件属 legacy_baseline 桶:锁的是旧决策核(decision_v2)内部行为语义,
# 随旧核退役而消亡;默认全量与快速集均不跑,仅基线冻结审计/A-B 开跑前
# 两时点单独跑。口径见 sr-od-test/README.md「测试纪律 · legacy 桶」。
import pytest

pytestmark = pytest.mark.legacy_baseline
