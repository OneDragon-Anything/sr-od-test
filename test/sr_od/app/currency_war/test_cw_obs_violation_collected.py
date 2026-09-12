"""观察纪律违规收编防复发锁(T-176)。

四件收编(违规详情单一源 = 进度迭代目录 reports/obs-violation-sweep-r1.md;
判定标尺 = docs/develop/sr_od/application/currency_war/design/
统一观察架构-画面op基类设计.md §1.1 op 外读屏白名单制/§2 观察端口契约
「识别机制不出端口」/§5.1 v11 禁验证裁定 + flow/screen_op.md §1「读屏点
只剩两个」/§4「决策循环内不读屏」):

- V-1 cw_loop._frontless_recovery_step 分发段像素判效读拆除(slot_occupied
  判前排 ≥1:分发段判效 + 锁外,与「动作 op 只管机械执行,落地判定归观察
  侧」裁定冲突)——失败信号改由 deploy 侧落点验证 + 出战链
  POST_LAUNCH_BLOCKERS 弹窗守卫(游戏承载)承接。
- V-2 cw_loop 备战分支派发前清场识别+点击(find_trial_reveal_cards/
  find_bookcards)迁 CwScreenPrep._clear_prep_cards——识别机制住画面 op
  观察链,外循环只保留分派(设计 §3.4 过渡相位件收编挂账兑现)。
- V-3 cw_screen_encounter 决策分支内现读 read_encounter_refresh_count 改
  入口观察一次读(payload.refresh_left 携带语义事实)——决策循环只消费
  观察产物,不再现读识别函数。
- G-13 kernel/cw_reconcile._star_stop_hook 的 cv2 截图留证迁注入槽
  (set_star_evidence_saver,实现住 decision_assembly 装配模块)——共用
  中段禁摸像素,kernel 保持纯逻辑;先例 = set_merge_effect_gate 装配缝。

各锁 = 收编后形态的负锚(违规形态不得回归)+ 关键接线正锚。红 = 违规
形态回潮,处置 = 重走收编方向,禁删断言跟绿。
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from dataclasses import fields as dataclass_fields


def _src(obj) -> str:
    return inspect.getsource(obj)


def _ast(obj):
    """dedent 后 parse(类方法 getsource 带缩进,裸 parse 报 IndentationError)。"""
    return ast.parse(textwrap.dedent(_src(obj)))


def _ast_names(obj) -> set[str]:
    """源码 AST 的调用名(Name/Attribute)与 import 绑定名集合。

    注释与 docstring 不入面(B4 锁同口径:文本匹配会把「禁 import cv2」
    这类说明性注释误伤成红)。调用名取 ``Name`` 调用与 ``Attribute`` 尾名;
    import 名取绑定名(asname/根名)。"""
    tree = _ast(obj)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                names.add(a.asname or a.name.split('.')[0])
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                names.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                names.add(fn.attr)
    return names


def _count_calls(obj, name: str) -> int:
    """源码 AST 中对 ``name`` 的调用次数(注释与引用不入面,只数 Call)。"""
    tree = _ast(obj)
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if ((isinstance(fn, ast.Name) and fn.id == name)
                    or (isinstance(fn, ast.Attribute) and fn.attr == name)):
                n += 1
    return n


# ==================== V-1:分发段像素判效读拆除 ====================

def test_v1_loop_dispatch_band_free_of_cv_occupancy_probe() -> None:
    """V-1 负锚:cw_loop 全模块零 slot_occupied 调用/import(AST 面)。

    cw_loop 是外循环分发层——其合法读屏面只有 F1 白名单豁免三点
    (read_game_state 族)与画面分派锚(round_by_*),像素判占原语
    slot_occupied 在其中无任何合法宿主;0j 出口判据 = 游戏弹窗信号
    (POST_LAUNCH_BLOCKERS 守卫)+ 重试预算,回归像素判效 = 收编倒退。"""
    from sr_od.application.currency_war.operations import cw_loop

    assert 'slot_occupied' not in _ast_names(cw_loop), (
        'cw_loop 分发层出现 slot_occupied 像素判占(分发段判效回潮;'
        '判效归观察侧对账/游戏弹窗信号,禁回外循环)')


def test_v1_frontless_recovery_signals_via_game_popup() -> None:
    """V-1 正锚:0j 恢复链失败信号 = 出战链弹窗守卫(游戏承载)接线在场。

    deploy 后直接再出战;前排仍空时游戏弹「前台无角色」→ 出战链
    POST_LAUNCH_BLOCKERS 白名单(含该弹窗)判 False → round_retry 回
    0j 计重试——守卫白名单缺「前台无角色」成员 = 失败信号断链。"""
    from sr_od.application.currency_war.prep_actions import PrepActionExecutor

    assert ('货币战争-提示-前台无角色', '标识-无角色提示') \
        in PrepActionExecutor.POST_LAUNCH_BLOCKERS, (
        'POST_LAUNCH_BLOCKERS 缺「前台无角色」成员(0j 失败信号断链)')
    loop_src = _src(PrepActionExecutor._launch_attempt)
    assert 'POST_LAUNCH_BLOCKERS' in loop_src


# ==================== V-2:清场识别+点击迁画面 op ====================

def test_v2_loop_free_of_prep_card_clearance_identify() -> None:
    """V-2 负锚:cw_loop 零揭示卡/书册卡清场识别与帧类预筛调用(AST 面)。

    外循环只保留画面识别分派(round_by_* 锚族);清场识别+点击住
    CwScreenPrep 环入口(画面 op 观察链合法面)。三函数在 cw_loop 的
    任何形式回归 = 分发层识别回潮。"""
    from sr_od.application.currency_war.operations import cw_loop

    names = _ast_names(cw_loop)
    for banned in ('find_trial_reveal_cards', 'find_bookcards',
                   'is_prep_like_frame'):
        assert banned not in names, (
            f'cw_loop 分发层出现 {banned}(清场识别回潮;收编落点 = '
            f'CwScreenPrep._clear_prep_cards)')


def test_v2_prep_entry_paths_wire_card_clearance() -> None:
    """V-2 正锚:清场接线在备战 op 的两个入口路径(旧 run/五段
    lifecycle_observe)都在场——单路径接线会让另一路径漏清场(书册卡
    占席毒化部署/合成槽位计算)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        CwScreenPrep,
    )

    assert '_clear_prep_cards()' in _src(CwScreenPrep.run), \
        'run() 入口缺清场接线'
    assert '_clear_prep_cards()' in _src(CwScreenPrep.lifecycle_observe), \
        'lifecycle_observe() 入口缺清场接线'


# ==================== V-3:刷新次数归入口观察 payload ====================

def test_v3_encounter_payload_carries_refresh_left() -> None:
    """V-3 正锚:EncounterObservation 携带 refresh_left(入口稳定帧读数;
    None = 读缺失败安全)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_encounter import (
        EncounterObservation,
    )

    names = {f.name for f in dataclass_fields(EncounterObservation)}
    assert 'refresh_left' in names, (
        'EncounterObservation 缺 refresh_left(刷新前置闸的观察产物载体消失)')


def test_v3_encounter_decision_cycles_consume_payload_only() -> None:
    """V-3 负锚+正锚:决策循环零现读识别函数,只消费观察产物。

    读点分布封闭(AST 调用计数):决策循环(lifecycle_decision_cycle)
    零调用;实机适配器①封口(_observe_frame)恰一次;旧路径 handle 恰
    一次(入口观察段,与 options 读同位——决策分支内的第二次现读 = 违规
    回潮)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_encounter import (
        CwScreenEncounter,
    )

    cycle_names = _ast_names(CwScreenEncounter.lifecycle_decision_cycle)
    assert 'read_encounter_refresh_count' not in cycle_names, (
        '五段决策循环现读刷新次数(V-3 回潮;消费 payload.refresh_left)')
    assert '_try_refresh(payload.screen)' in _src(
        CwScreenEncounter.lifecycle_decision_cycle), (
        '刷新执行半部未从 payload 帧取文本锚(坐标入参形态回归)')
    assert _count_calls(CwScreenEncounter._observe_frame,
                        'read_encounter_refresh_count') == 1, (
        '适配器①封口读点数漂移(应恰一次,同帧读)')
    assert _count_calls(CwScreenEncounter.handle,
                        'read_encounter_refresh_count') == 1, (
        '旧路径 handle 读点数漂移(应恰一次且在入口观察段;决策分支内'
        '现读 = V-3 违规回潮)')


# ==================== G-13:kernel 纯逻辑,留证走注入槽 ====================

def test_g13_kernel_reconcile_touches_no_pixels() -> None:
    """G-13 负锚:kernel/cw_reconcile 全模块零 cv2 import 绑定(AST 面;
    共用中段禁摸像素的字面纪律——截图留证经 set_star_evidence_saver
    注入槽,实现住 app 装配模块)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile

    assert 'cv2' not in _ast_names(cw_reconcile), (
        'kernel/cw_reconcile 出现 cv2 import(共用中段摸像素回潮;'
        '留证走注入槽,先例 = set_merge_effect_gate 装配缝)')
    assert hasattr(cw_reconcile, 'set_star_evidence_saver'), (
        'star 截图留证注入槽消失(留证通道断链)')


def test_g13_evidence_saver_wired_at_assembly_point() -> None:
    """G-13 正锚:留证 saver 在生产装配点接通(install_obs_ports;
    缺省关 = 只写 flag 不落截图,生产武装点缺接线 = 截图留证静默消失)。"""
    from sr_od.application.currency_war import decision_assembly

    install_src = _src(decision_assembly.install_obs_ports)
    assert 'set_star_evidence_saver' in install_src, (
        'install_obs_ports 未接通 star 截图留证 saver(G-13 收编装配缺失)')
