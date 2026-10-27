"""终局键集标签命中件资格增补测试(排除谓词集合形态/演进降级排除/
组级净非降边界锚)。

被测 = ``kernel/cw_deploy_logic.py`` 收敛不变式族(design 2026-10-26-
swap-channel-unified §2.8;来金侧装配 A 落点测试见 strategies 侧
test_sell_candidates.py 与 test_sell_window_launch.py,发射形态观测锚见
test_emit_swap_bond_gate.py):

- **排除谓词集合形态**(§2.1 标签口径/§2.8 谓词语义钉死):
  ``terminal_key_label_hit_names`` 命中 = 标签∩键集,不看激活档位;
- **演进降级换人排除**(§2.8 堵回降口一):武装释放面不豁免终局键集
  标签件(单帧 + plan 级不入选);
- **组级净非降边界锚**(§2.8 段一):板上标签命中件唯一离场通道 =
  换人且组级支撑数净非降。
"""
from __future__ import annotations

from test.sr_od.application.currency_war.kernel.cw_deploy_logic.test_swap_bond_gate_domain import (
    _FUX,
    _GIL,
    _HUO,
    _JI,
    _QING,
    _RIN,
    _SBR,
    _TING,
    _WALT,
    _YAO,
    _gate_ctx,
)

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    _bond_gate_support_count,
    swap_bond_gate_benefit,
    swap_bond_gate_conservation,
    swap_sell_exclusion_reason,
    terminal_key_label_hit_names,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.deploy_plan import (
    build_swap_group_order,
    select_deployments_reasoned,
)


def _plan(ctx):
    """组计划直驱(序参数 = 生产构建器 ports 注入;与
    test_select_swap_group_plan 同构)。"""
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        select_swap_plan,
    )
    return select_swap_plan(ctx, select_up=select_deployments_reasoned,
                            group_order=build_swap_group_order(ctx))


# ============================================================
# 排除谓词集合形态(design §2.1/§2.8)
# ============================================================

def test_terminal_key_label_hit_names_registry_set() -> None:
    """排除谓词集合形态(design §2.8 谓词语义钉死):命中 = 羁绊标签
    (factions∪flows)∩ 终局键集 ≠ ∅,**不看是否已承载激活档位**——
    键标签件(远坂凛=圣杯+战技点/停云=仙舟+能量)与名单成员一并计入;
    键集零命中件(爻光/青雀)不计入;键集空(未锁定帧无终局键集)恒
    零面。"""
    keys = frozenset(get_comp('双王圣杯').form_tiers)   # {命运圣杯, 能量}
    names = terminal_key_label_hit_names(keys)
    assert {_RIN, _TING} <= names, '键标签件计入(无已达成档也算)'
    assert {_GIL, _SBR, _HUO, _JI} <= names, \
        '名单成员命中亦计入(义务集已保,谓词冗余兜底无害)'
    assert _YAO not in names and _QING not in names, '键集零命中件不计入'
    assert terminal_key_label_hit_names(frozenset()) == frozenset(), \
        '键集空恒空集(未锁定帧谓词零面)'


# ============================================================
# 演进降级换人排除(design §2.8 堵回降口一)
# ============================================================

def test_evolution_armed_release_excludes_terminal_label_piece() -> None:
    """演进降级换人 victim 资格增补排除(单帧):武装释放面(star>1)
    对终局键集标签命中件不豁免,拒因沿用既有键 star_guard(资格族闭集
    不扩);零标签 2★ 件照常获释放(排除面 = 标签命中,非整分支关停);
    非武装帧语义逐位同旧;1★ 标签件资格归转型域门 2 通道 2,不属演进
    分支释放面辖域(不受本排除)。"""
    ctx = _gate_ctx(board=[_GIL, _WALT, _FUX, _JI, _TING],
                    bench=[_SBR], cap=5, stars={_TING: 2})
    ctx.evolution_swap_armed = True
    assert swap_sell_exclusion_reason(_TING, ctx) == 'star_guard', \
        '武装帧标签件不获降级释放(design §2.8 堵回降口一)'
    ctx_free = _gate_ctx(board=[_GIL, _WALT, _FUX, _JI, '椒丘'],
                         bench=[_SBR], cap=5, stars={'椒丘': 2})
    ctx_free.evolution_swap_armed = True
    assert swap_sell_exclusion_reason('椒丘', ctx_free) == '', \
        '零标签 2★ 件照常获武装释放(演进降级语义本体不动)'
    ctx_unarmed = _gate_ctx(board=[_GIL, _WALT, _FUX, _JI, _TING],
                            bench=[_SBR], cap=5, stars={_TING: 2})
    assert swap_sell_exclusion_reason(_TING, ctx_unarmed) == 'star_guard', \
        '非武装帧 star_guard 逐位同旧(star_guard 常规辖域)'
    ctx_1star = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                          bench=[_SBR], cap=5)
    ctx_1star.evolution_swap_armed = True
    assert swap_sell_exclusion_reason(_TING, ctx_1star) == '', \
        '1★ 标签件走门 2 通道 2(演进展辖域只辖 star>1 释放面)'


def test_evolution_armed_label_only_pool_yields_no_plan() -> None:
    """演进降级遇终局键集标签件 → 不入选(plan 级,完成判据 3):全池
    唯一候选 = 2★ 标签件(武装帧原可释放)→ 排除后 victim 池空 =
    零动作(bond_gate_reject 闭集 novictim);对照帧零标签 2★ victim
    照常成组(圣杯 0→1 档 tier 达成)——排除只撤标签件,不撤分支。"""
    ctx = _gate_ctx(board=[_GIL, _WALT, _FUX, _JI, _TING],
                    bench=[_SBR], cap=5, stars={_TING: 2})
    ctx.evolution_swap_armed = True
    plan = _plan(ctx)
    assert not plan.nonempty, '标签件唯一候选被排除 = 零动作'
    assert plan.bond_gate_reject == 'novictim', \
        f'拒绝侧闭集 novictim(victim 池空),实得 {plan.bond_gate_reject}'
    ctx_free = _gate_ctx(board=[_GIL, _WALT, _FUX, _JI, '椒丘'],
                         bench=[_SBR], cap=5, stars={'椒丘': 2})
    ctx_free.evolution_swap_armed = True
    plan_free = _plan(ctx_free)
    assert plan_free.nonempty and plan_free.sell_names == ['椒丘'], \
        f'对照:零标签 2★ 件武装帧照常入选成组,实得 {plan_free.sell_names}'


# ============================================================
# 组级净非降边界锚(design §2.8 段一)
# ============================================================

def test_label_piece_board_exit_via_paired_swap_support_non_decreasing() \
        -> None:
    """板上标签命中件唯一离场通道 = 换人且组级支撑数净非降(边界锚;
    design §2.8 段一,配合 3.1/3.2 既有换人测试):A′ 帧二级标签件
    (停云)换血对(停云→Saber)——支撑数损失(标签件 −1)与换入
    (名单件 +1)相抵 = 净零边界,门 1(圣杯 2→3 二阶激活)与守恒
    (终局档位非降)双过;来金/演进离场通道已由 §2.8 两口排除封死
    (单帧锚见 test_sell_candidates.py 六通道逐一点名与本文件演进
    排除)。"""
    ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                    bench=[_SBR], cap=5)
    before = {d.char_id for d in ctx.deployed if d is not None and d.char_id}
    after = (before - {_TING}) | {_SBR}
    n_before = _bond_gate_support_count(ctx.bond_gate_keys, ctx.k_members,
                                        before)
    n_after = _bond_gate_support_count(ctx.bond_gate_keys, ctx.k_members,
                                       after)
    assert n_after == n_before, \
        f'边界 = 净零(损失标签件与换入支撑件相抵),实得 {n_before}->{n_after}'
    ok, leg = swap_bond_gate_benefit(ctx, victims=[_TING], ups=[_SBR],
                                     pairs=[(_TING, _SBR)],
                                     up_stars={_SBR: 1})
    assert ok is True and leg == 'tier', \
        f'A′ 帧:停云换 Saber 圣杯 2→3 二阶激活归因 ①,实得 {(ok, leg)}'
    assert swap_bond_gate_conservation(ctx, victims=[_TING],
                                       ups=[_SBR]) is True, \
        '守恒:终局档位非降(能量持平、圣杯升档)'
