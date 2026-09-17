# -*- coding: utf-8 -*-
"""P24 残余补部署计划判据锁(kernel 单一源 + op 适配器同判定)。

判据出处 = docs/develop/sr_od/application/currency_war/proofs/
p24-residual-fill-dominance.md:零支出域(C=I=0)下,空 cap 槽上任意
合法单位上阵 ΔEV = Δp·ΣL_c·S ≥ 0 恒成立(结构支配定理,零自由参数)
→ 「合法留置件逐件补上」无 EV 判负路径,实现面的边界锁 = 守卫语义
(同名 dup 剔除 / cap 满停 / 两排皆满停 / cap=None 不设门)。

单一源 = kernel.cw_deploy_logic.residual_fill_plan;op 侧
cw_screen_deploy.residual_fill_plan 是转发适配器(同输入同判定锁,
防适配器漂移成第二实现),同文件 filter_fill_plan_by_floor 是配方
底线门对 fill 段的随行防线(防线等价锁)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    residual_fill_plan as kernel_fill_plan,
)
from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar
from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_deploy as deploy_op,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_deploy import (
    filter_fill_plan_by_floor,
)


def test_fill_legal_held_on_empty_slot():
    # 合法散牌 + 空槽 → 逐件补上(P24 ΔEV≥0 = 补);slot_idx 取自
    # 对应排空槽列表原值(0 基,row_pts[slot_idx] 取拖点)。
    plan = kernel_fill_plan(
        held=[5, 6], front_empty=[1], back_empty=[3, 4],
        bench_pos={5: 'front', 6: 'back'},
        bench_cid={5: '飞霄', 6: '停云'},
        deployed_cids=set(), cap=4, deployed_count=2)
    assert plan == [(5, 'front', 1), (6, 'back', 3)]


def test_fill_dup_name_stays_bench():
    # 同名禁双(5.1.7):dup 是 3合1 素材,游戏拒收同名 → 留 bench 不补。
    plan = kernel_fill_plan(
        held=[2], front_empty=[0, 1], back_empty=[0, 1, 2, 3, 4, 5],
        bench_pos={2: 'front'}, bench_cid={2: '藿藿'},
        deployed_cids={'藿藿'}, cap=6, deployed_count=1)
    assert plan == []


def test_fill_stops_at_cap():
    # cap 满不补;半满 → 只补到 cap 截断。
    rows = dict(front_empty=[0, 1], back_empty=[0, 1, 2, 3, 4, 5])
    plan = kernel_fill_plan(
        held=[3, 4], bench_pos={3: 'back', 4: 'back'},
        bench_cid={3: '停云', 4: '青雀'},
        deployed_cids=set(), cap=3, deployed_count=3, **rows)
    assert plan == []   # 已达 cap → 一件不补
    plan = kernel_fill_plan(
        held=[3, 4], bench_pos={3: 'back', 4: 'back'},
        bench_cid={3: '停云', 4: '青雀'},
        deployed_cids=set(), cap=4, deployed_count=3, **rows)
    assert [p[0] for p in plan] == [3]   # 只补 1 件到 cap


def test_fill_cap_none_means_no_gate():
    # cap=None 不设门(拖到游戏拒即真值,同主循环 5.1.8 口径)。
    plan = kernel_fill_plan(
        held=[3, 4], front_empty=[], back_empty=[0, 1, 2, 3, 4, 5],
        bench_pos={3: 'back', 4: 'back'}, bench_cid={3: '停云', 4: '青雀'},
        deployed_cids=set(), cap=None, deployed_count=10)
    assert [p[0] for p in plan] == [3, 4]


def test_fill_row_pref_fallback_and_both_full():
    # 首选排满 fallback 另一排;两排皆满停;position_pref 缺读默认
    # back(后排槽多,安全缺省)。
    plan = kernel_fill_plan(
        held=[7], front_empty=[], back_empty=[2],
        bench_pos={7: 'front'}, bench_cid={7: '飞霄'},
        deployed_cids=set(), cap=8, deployed_count=3)
    assert plan == [(7, 'back', 2)]
    plan = kernel_fill_plan(
        held=[7], front_empty=[], back_empty=[],
        bench_pos={7: 'front'}, bench_cid={7: '飞霄'},
        deployed_cids=set(), cap=8, deployed_count=3)
    assert plan == []   # 两排皆满
    plan = kernel_fill_plan(
        held=[0], front_empty=[0], back_empty=[1],
        bench_pos={}, bench_cid={0: '飞霄'},
        deployed_cids=set(), cap=8, deployed_count=3)
    assert plan == [(0, 'back', 1)]


def test_op_adapter_same_judgment_as_kernel():
    # op 侧同名片 = 转发适配器(判定单一源纪律):同输入同判定,
    # 漂移成第二实现即红。
    case = dict(
        held=[5, 6], front_empty=[1], back_empty=[3, 4],
        bench_pos={5: 'front', 6: 'back'},
        bench_cid={5: '飞霄', 6: '停云'},
        deployed_cids={'停云'}, cap=4, deployed_count=2)
    expected = [(5, 'front', 1)]   # 停云 dup 留 bench,飞霄补前排空槽
    assert deploy_op.residual_fill_plan(**case) == expected
    assert kernel_fill_plan(**case) == expected


def test_fill_floor_filter_defense_line():
    # 配方底线门对 fill 段同辖(发射契约):kernel 留 bench 的列车件
    # (列车≥2 ∧ 仙舟<3)不得经补部署绕回上板;锁定线豁免语境
    # (∧ 本帧无有效仙舟供给)门让位放行,供给在场时门照拦(供给
    # 保留条款)。防线随迁移保持等价锁。
    fill = [(2, 'back', 0)]
    bench_fac = {2: '列车同行'}
    deployed_fac = {'列车同行': 2, '仙舟': 0}
    # 常规语境:门拦 → 计划剔除
    assert filter_fill_plan_by_floor(
        fill, bench_fac, deployed_fac, set(),
        [BenchChar(slot=3, char_id='停云')], False) == []
    # 锁定线豁免 + 本帧无仙舟供给:门让位 → 放行
    assert filter_fill_plan_by_floor(
        fill, bench_fac, deployed_fac, set(), [], True) == fill
    # 豁免武装但 bench 有有效仙舟供给(停云:仙舟羁绊非列车主阵营)
    # → 门照拦
    assert filter_fill_plan_by_floor(
        fill, bench_fac, deployed_fac, set(),
        [BenchChar(slot=3, char_id='停云')], True) == []
