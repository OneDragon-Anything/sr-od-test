"""T-164 动作 op 规范整改·批A 锁面(2026-09-08 用户裁定:动作 op 的规范
是机械执行,不能在里面额外做画面判断、失败判断;弃执行禁记 round_success)。

整改点与清查实例号(清查/方案审 = .debug/temp/currency_war/attacks/
action_op_compliance/;实例号为语义索引):
- E2/E3(cw_op_equip_all):批内画面漂移闸 break+success → round_fail
  具名状态(STATUS_SCREEN_DRIFTED);哨兵观测保留(stop_reason 串不变,
  分类域锁仍在 test_cw_equip_wear_semantics_18)。
- D1(cw_op_deploy):事件 overlay 三锚 success-skip → round_fail
  (STATUS_EVENT_OVERLAY);「op 内 overlay 弹出 = 执行环境失配,重判
  归分发层」;不升 guard_screen(T-163 边界申报锁语义不变)。
- D2(cw_op_deploy):入口 cap 门/幻影满板失配 fail 暴露(3 元组契约,
  行为锁在 test_cw_p4r_deploy_battle_chain);本文件锁节点 gate_fail
  先于 NOOP 分支上报。
- D3(cw_op_deploy):同签名 placed=0 熔断跳槽删除(符号残留锁在
  test_cw_deploy_pseudo_slot);节点 STATUS_LANDED_NONE 如实上报。
- C3(cw_op_tools):op 内 replan 删除,计划失效 round_fail 上报
  (纯函数行为锁在 test_cw_tools_exec_channel)。

守卫变异打红口径:本文件每个行为锁都可被「round_fail 改回 round_success /
fail 分支删除」的单点变异打红(验收亲测记录见交付报告)。
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

_ACT = '货币战争-备战'
_DRIFT = '货币战争-商店卡牌详情'


def _screen_seq_stub(op, monkeypatch, seq: list[str]) -> None:
    """check_and_update_current_screen 序列替身:第 n 次调用返 seq[n],
    超长取末值(入口过闸 + 批内漂移两段式场景)。"""
    calls = {'n': 0}

    def _check(screen, screen_name_list):
        i = min(calls['n'], len(seq) - 1)
        calls['n'] += 1
        return seq[i]

    monkeypatch.setattr(op, 'check_and_update_current_screen', _check)


# ==================== E2:M7 主循环批内漂移 → round_fail ====================

def _mk_equip_op(monkeypatch, *, avatar_templates) -> object:
    """裸 CwOpEquipAll(过入口闸,抵达 M7/front-only 分叉前的最小桩面)。"""
    from sr_od.application.currency_war.obs import cw_back_layout
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_equip_all as ea,
    )

    op = ea.CwOpEquipAll.__new__(ea.CwOpEquipAll)
    op.last_screenshot = object()
    monkeypatch.setattr(op, 'screenshot', lambda: object())
    monkeypatch.setattr(op, '_get_templates', lambda: object())
    monkeypatch.setattr(op, '_get_tm_grays', lambda: object())
    monkeypatch.setattr(op, '_get_avatar_templates',
                        lambda: avatar_templates)
    monkeypatch.setattr(ea, '_area_rect',
                        lambda ctx, name, screen: SimpleNamespace(
                            x1=1620, y1=100, x2=1918, y2=900))
    monkeypatch.setattr(cw_back_layout, 'select_back_layout',
                        lambda ctx, scr, level=None, cap=None,
                        level_trusted=None: (6, ''))
    op.ctx = SimpleNamespace(cw_match=None)
    return op


def test_equip_m7_drift_fails_mid_batch(monkeypatch) -> None:
    """E2 行为锁:M7 主循环内画面漂移 → round_fail(具名状态),禁旧
    break+success 把弃批记成「M7 装备 X 件」假成功吞分发。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_equip_all as ea,
    )
    op = _mk_equip_op(monkeypatch, avatar_templates=object())
    _screen_seq_stub(op, monkeypatch, [_ACT, _DRIFT])
    monkeypatch.setattr(ea, 'read_deployed_chars',
                        lambda ctx, scr, tpl: [SimpleNamespace(
                            char_id='姬子', position_pref='back', slot=1)])
    monkeypatch.setattr(ea, 'read_row_equipped', lambda *a, **k: {})
    res = op.equip_all()
    assert res.result.name == 'FAIL'
    assert ea.CwOpEquipAll.STATUS_SCREEN_DRIFTED in (res.status or ''), \
        f'批内漂移必须以具名状态 fail,实得 {res.status!r}'


def test_equip_frontonly_drift_fails_mid_batch(monkeypatch) -> None:
    """E3 行为锁:front-only 回退路径批内漂移 → round_fail(同具名状态),
    禁静默 break 后 success 假完成。avatar_templates=None = 身份读失败
    → 走回退路径(与生产分叉条件一致)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_equip_all as ea,
    )
    op = _mk_equip_op(monkeypatch, avatar_templates=None)
    _screen_seq_stub(op, monkeypatch, [_ACT, _DRIFT])
    monkeypatch.setattr(ea, 'read_row_equipped', lambda *a, **k: {})
    res = op.equip_all()
    assert res.result.name == 'FAIL'
    assert ea.CwOpEquipAll.STATUS_SCREEN_DRIFTED in (res.status or ''), \
        f'回退路径批内漂移必须以具名状态 fail,实得 {res.status!r}'


# ==================== D1:事件 overlay 三锚 → round_fail ====================

def test_deploy_event_overlay_fails_not_skips(monkeypatch) -> None:
    """D1 行为锁:overlay 三锚任一命中 → round_fail(STATUS_EVENT_OVERLAY
    前缀 + 命中画面名),禁旧 round_success('事件overlay,跳过部署') 把
    弃执行记成成功吞分发。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        CwOpDeploy,
    )
    op = CwOpDeploy.__new__(CwOpDeploy)
    op.last_screenshot = object()
    op.ctx = SimpleNamespace(
        screen_loader=SimpleNamespace(get_screen=lambda name: object()))
    monkeypatch.setattr(
        op, 'round_by_find_area',
        lambda screen, s1, s2, **kw: SimpleNamespace(is_success=True))
    res = op.deploy()
    assert res.result.name == 'FAIL'
    assert CwOpDeploy.STATUS_EVENT_OVERLAY in (res.status or ''), \
        f'overlay 在场必须执行断言 fail,实得 {res.status!r}'


def test_deploy_clean_screen_reaches_past_overlay(monkeypatch) -> None:
    """对照臂:三锚全不中 → 越过 overlay 断言继续执行(裸实例缺识别面,
    后续第一步即 AttributeError;若断言误拦,round_fail 正常返回 →
    raises 不触发 = 红,精确证明「放行」而非恒 fail)。"""
    import pytest

    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        CwOpDeploy,
    )

    op = CwOpDeploy.__new__(CwOpDeploy)
    op.last_screenshot = object()
    op.ctx = SimpleNamespace(
        screen_loader=SimpleNamespace(get_screen=lambda name: object()))
    monkeypatch.setattr(
        op, 'round_by_find_area',
        lambda screen, s1, s2, **kw: SimpleNamespace(is_success=False))
    with pytest.raises(AttributeError):
        op.deploy()


# ==================== D2/D3:节点上报接线(源码锁) ====================

def test_deploy_node_reports_gate_fail_before_noop() -> None:
    """D2 接线锁:节点先判 gate_fail(round_fail 原样透传具名状态)再进
    dd-037 三分——失配闸命中禁被 STATUS_NOOP 合法稳态分支吞掉。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        CwOpDeploy,
    )
    src = inspect.getsource(CwOpDeploy.deploy)
    i_gate = src.find('if _gate_fail is not None:')
    assert i_gate >= 0, '节点缺 gate_fail 上报分支(D2 失配闸被吞)'
    i_noop = src.find('round_success(CwOpDeploy.STATUS_NOOP')
    assert i_noop >= 0, 'NOOP 合法稳态出口缺失(dd-037 三分被破坏)'
    assert i_noop > i_gate, 'gate_fail 判定必须在 NOOP 出口之前'
    assert 'round_fail(_gate_fail)' in src


def test_deploy_node_placed_zero_reports_fail() -> None:
    """D3 接线锁:计划非空 placed=0 = STATUS_LANDED_NONE round_fail 如实
    上报(熔断跳槽删除后,结构性拒绝以失败形态交回,3 环无进展由分发层
    prep_no_progress 停机留证——锁面 test_cw_no_progress_guard.py)。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        CwOpDeploy,
    )
    src = inspect.getsource(CwOpDeploy.deploy)
    assert 'round_fail(CwOpDeploy.STATUS_LANDED_NONE)' in src, \
        'placed=0 失败上报分支失守(D3 如实报告语义回归)'


def test_tools_node_reports_plan_stale_fail() -> None:
    """C3 接线锁:plan_stale → STATUS_PLAN_STALE round_fail(计划失效
    上报交回分发层重算);run_tool_queue 调用不带 replan(纯函数锁在
    test_cw_tools_exec_channel)。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_tools import (
        CwOpTools,
    )
    src = inspect.getsource(CwOpTools.tools_consume)
    assert 'round_fail(CwOpTools.STATUS_PLAN_STALE)' in src, \
        '计划失效上报分支失守(C3 语义回归)'
    assert 'run_tool_queue(plans, _exec)' in src, \
        'run_tool_queue 调用形态漂移(不得回带 replan)'


# ==================== 批A 下线面:collect_spheres 零复活 ====================

def test_collect_spheres_stays_offline() -> None:
    """S1/S2 下线锁:cw_op_collect_spheres 模块与 CwOpCollectSpheres 类在
    src 全树零引用(唯一历史喂点已随下线删除;模态金 'spheres' 分键断喂
    缺口登记在 recorder.record_modality_gold docstring,禁原样复活)。"""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[5]
    offenders: list[str] = []
    for p in (repo / 'src').rglob('*.py'):
        text = p.read_text(encoding='utf-8', errors='ignore')
        if ('CwOpCollectSpheres' in text
                or 'cw_op_collect_spheres.py' in text
                or 'operations.cw_op.cw_op_collect_spheres' in text):
            offenders.append(str(p.relative_to(repo)))
    assert not offenders, f'collect_spheres 引用残留(下线 op 复活): {offenders}'
