"""动作 op 机械执行规范·执行断言化锁面(ADR-0601:2026-09-08 用户裁定
「动作 op 的规范是机械执行,不能在里面额外做画面判断、失败判断」;
弃执行禁记 round_success;实例号 E2/E3/D1/D2/D3/C3 = ADR-0601 §3/§4
的语义索引)。

整改点与锁面:
- E2/E3(cw_op_equip_all):批内画面漂移闸 break+success → round_fail
  具名状态(STATUS_SCREEN_DRIFTED);哨兵观测保留(stop_reason 串不变,
  分类域锁在 test_cw_opening_tool_semantics 的 TestTelemetryDomainKey)。
- D1(cw_op_deploy):事件 overlay registry 全集锚 success-skip → round_fail
  (STATUS_EVENT_OVERLAY;T-277 registry 化,旧措辞「三锚」= 硬编码三屏
  已扩为 derive_decision() 全集);「op 内 overlay 弹出 = 执行环境失配,重判
  归分发层」;不升 guard_screen(test_cw_popup_dispatch 边界
  申报锁语义不变)。
- D2(cw_op_deploy):入口 cap 门/幻影满板失配 fail 暴露(3 元组契约,
  行为锁在 test_cw_deploy_battle_chain);本文件锁节点 gate_fail
  先于 NOOP 分支上报。
- D3(cw_op_deploy):同签名 placed=0 熔断跳槽删除(符号残留锁已并入
  本文件退役机制双禁表锁);节点 STATUS_LANDED_NONE 如实上报。
- C3(cw_op_tools):op 内 replan 删除,计划失效 round_fail 上报
  (纯函数行为锁在 test_cw_tools_exec_channel)。
- T1(cw_op_deploy):_deploy_deterministic bench 空路径 3 元组行为锁
  (三审 C1:旧 2 元组 return 契约漏改在全部既有锁网之外,调用点
  ValueError;本锁直钉该 return 面堵漏)。

守卫变异打红口径:本文件每个行为锁都可被「round_fail 改回
round_success / fail 分支删除 / bench 空路径回退 2 元组」的单点变异
打红(验收亲测记录见交付报告)。
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

def _mk_equip_op(monkeypatch, *, avatar_templates, plan) -> object:
    """裸 CwOpEquipAll(过入口闸,抵达计划消费循环的最小桩面;T-164 C1
    计划化后 op 由分发段下发计划执行——桩面补 plan 参数,断言面不动:
    锁改桩不改语义,批内漂移执行断言在计划消费循环中原样保留)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_equip_all as ea,
    )

    op = ea.CwOpEquipAll.__new__(ea.CwOpEquipAll)
    op.last_screenshot = object()
    op.plan = list(plan)
    monkeypatch.setattr(op, 'screenshot', lambda: object())
    monkeypatch.setattr(op, '_get_templates', lambda: object())
    monkeypatch.setattr(op, '_get_tm_grays', lambda: object())
    monkeypatch.setattr(ea, '_area_rect',
                        lambda ctx, name, screen: SimpleNamespace(
                            x1=1620, y1=100, x2=1918, y2=900))
    op.ctx = SimpleNamespace(cw_match=None)
    return op


def test_equip_m7_drift_fails_mid_batch(monkeypatch) -> None:
    """E2 行为锁:M7 主循环内画面漂移 → round_fail(具名状态),禁旧
    break+success 把弃批记成「M7 装备 X 件」假成功吞分发。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_equip_all as ea,
    )
    plan = [ea.EquipWearStep(item_name='财富宝钻', char_name='姬子',
                             row='back', slot=1)]
    op = _mk_equip_op(monkeypatch, avatar_templates=object(), plan=plan)
    _screen_seq_stub(op, monkeypatch, [_ACT, _DRIFT])
    monkeypatch.setattr(ea, 'record_zero_wear_defect', lambda *a, **k: None)
    res = op.equip_all()
    assert res.result.name == 'FAIL'
    assert ea.CwOpEquipAll.STATUS_SCREEN_DRIFTED in (res.status or ''), \
        f'批内漂移必须以具名状态 fail,实得 {res.status!r}'


def test_equip_frontonly_drift_fails_mid_batch(monkeypatch) -> None:
    """E3 行为锁:front-only 回退路径批内漂移 → round_fail(同具名状态),
    禁静默 break 后 success 假完成。计划步 char_name='' = 身份读失败的
    回退计划步(与生产分叉条件一致,builder front_only 分支产出形态)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_equip_all as ea,
    )
    plan = [ea.EquipWearStep(item_name='财富宝钻', char_name='',
                             row='front', slot=1)]
    op = _mk_equip_op(monkeypatch, avatar_templates=None, plan=plan)
    _screen_seq_stub(op, monkeypatch, [_ACT, _DRIFT])
    res = op.equip_all()
    assert res.result.name == 'FAIL'
    assert ea.CwOpEquipAll.STATUS_SCREEN_DRIFTED in (res.status or ''), \
        f'回退路径批内漂移必须以具名状态 fail,实得 {res.status!r}'


# ==================== D1:事件 overlay registry 全集 → round_fail ====================

def test_deploy_event_overlay_fails_not_skips(monkeypatch) -> None:
    """D1 行为锁(T-277 registry 化,docstring 措辞随检查集更新):registry
    decision 全集锚任一命中 → round_fail(STATUS_EVENT_OVERLAY 前缀 +
    命中画面名),禁旧 round_success('事件overlay,跳过部署') 把弃执行
    记成成功吞分发。检查集单一源 = kernel cw_overlay_registry.derive_
    decision()(T-268 治本 G3:旧硬编码三屏扩为全集,纯收紧)。"""
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
    """对照臂:registry decision 全集锚全不中 → 越过 overlay 断言继续
    执行(裸实例缺识别面,后续第一步即 AttributeError;若断言误拦,
    round_fail 正常返回 → raises 不触发 = 红,精确证明「放行」而非恒
    fail)。"""
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


# ==================== D2/D3/C3:节点上报接线(源码契约锁,三并一) ====================

def test_node_report_wiring_contract() -> None:
    """D2/D3/C3 接线契约锁(原三条独立接线锁并一:同批同型肯定性烟雾
    锁压密度,单点维护;各断言面精确到字符串,仍可被对应单点变异单独
    打红):
    - deploy 节点先判 gate_fail(round_fail 原样透传具名状态)再进
      dd-037 三分——失配闸命中禁被 STATUS_NOOP 合法稳态分支吞掉;
    - 计划非空 placed=0 = STATUS_LANDED_NONE round_fail 如实上报
      (熔断跳槽删除后,结构性拒绝以失败形态交回,3 环无进展由分发层
      prep_no_progress 停机留证——锁面 test_cw_no_progress_guard.py);
    - tools 节点 plan_stale → STATUS_PLAN_STALE round_fail;
      run_tool_queue 调用不带 replan(纯函数锁在
      test_cw_tools_exec_channel)。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        CwOpDeploy,
    )
    from sr_od.application.currency_war.operations.cw_op.cw_op_tools import (
        CwOpTools,
    )
    deploy_src = inspect.getsource(CwOpDeploy.deploy)
    i_gate = deploy_src.find('if _gate_fail is not None:')
    assert i_gate >= 0, '节点缺 gate_fail 上报分支(D2 失配闸被吞)'
    i_noop = deploy_src.find('round_success(CwOpDeploy.STATUS_NOOP')
    assert i_noop >= 0, 'NOOP 合法稳态出口缺失(dd-037 三分被破坏)'
    assert i_noop > i_gate, 'gate_fail 判定必须在 NOOP 出口之前'
    # gate_fail → round_fail 透传的行为面由 test_cw_front_invariant
    # L4b/L5 经 op.deploy() 端到端辖(BOARD_FULL_MISMATCH/PHANTOM 两形态
    # 均断言具名状态在 res.status),此处不再重复源码字面在场断言。
    assert 'round_fail(CwOpDeploy.STATUS_LANDED_NONE)' in deploy_src, \
        'placed=0 失败上报分支失守(D3 如实报告语义回归)'
    tools_src = inspect.getsource(CwOpTools.tools_consume)
    assert 'round_fail(CwOpTools.STATUS_PLAN_STALE)' in tools_src, \
        '计划失效上报分支失守(C3 语义回归)'
    assert 'run_tool_queue(plans, _exec)' in tools_src, \
        'run_tool_queue 调用形态漂移(不得回带 replan)'


# ==================== T1:bench 空路径 3 元组契约锁 ====================

def test_deploy_deterministic_bench_empty_returns_noop_triple(
        monkeypatch) -> None:
    """bench 空早退 = 合法稳态 NOOP 的输入形态,返回必须满足 3 元组签名
    (placed, plan_empty, gate_fail) = (0, True, None)(ADR-0601 §4;
    三审 C1 实证:旧 2 元组 return 恰在此路径漏过全部既有锁——调用点
    三元解包 ValueError → 框架转 retry 烧尽预算后假失败)。行为锁直钉
    该 return 面:回退 2 元组的单点变异在此以 ValueError 打红。"""

    from sr_od.application.currency_war.obs import cw_back_layout
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_deploy as db,
    )

    op = db.CwOpDeploy.__new__(db.CwOpDeploy)
    monkeypatch.setattr(op, 'screenshot', lambda: object())
    monkeypatch.setattr(op, '_session_level', lambda: None)
    monkeypatch.setattr(op, '_level_trusted', lambda: None)
    monkeypatch.setattr(db, 'read_deploy_cap_debounced',
                        lambda ctx, scr, level: None)
    monkeypatch.setattr(db, 'bench_item_slots',
                        lambda ctx, scr, fuzzy: set())
    monkeypatch.setattr(cw_back_layout, 'select_back_layout',
                        lambda ctx, scr, level=None, cap=None,
                        level_trusted=None: (6, ''))
    op.ctx = SimpleNamespace(cw_match=None,
                             screen_loader=SimpleNamespace(
                                 get_screen=lambda name: None))
    # bench/front/back 全空 = 到达 bench 空早退的最小桩面(空列表不过
    # slot_occupied,无需图像桩);templates=None 同走早退,零拖拽面。
    placed, plan_empty, gate_fail = op._deploy_deterministic(
        [], [], [], None)
    assert (placed, plan_empty, gate_fail) == (0, True, None), \
        f'bench 空 = (0, True, None) 合法稳态 NOOP 输入,实得 ' \
        f'{(placed, plan_empty, gate_fail)!r}'


# ==================== 批A 下线面:退役机制双禁表(单次全树扫描) ====================

def test_retired_mechanism_symbols_stay_offline() -> None:
    """批A 双机制下线墓碑锁(原两把全 src 树扫描锁并一:collect_spheres
    下线与 zero-place 熔断退役载体全同[全树扫描],单次扫描双禁表省一趟
    树读,禁表断言面不变):
    - S1/S2:cw_op_collect_spheres 模块与 CwOpCollectSpheres 类在 src
      全树零引用(模态金 'spheres' 分键断喂缺口登记在
      recorder.record_modality_gold docstring,禁原样复活);
    - D3:熔断签名/计数/跳槽符号零残留(防「省白耗」动机把 op 内第二份
      失败记忆加回来;失败记忆单一源 = 分发层 cw_loop prep_no_progress
      同签名计数,锁面 test_cw_no_progress_guard.py)。"""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[5]
    collect_banned = ('CwOpCollectSpheres', 'cw_op_collect_spheres.py',
                      'operations.cw_op.cw_op_collect_spheres')
    breaker_banned = ('zero_place_sig', 'zero_place_breaker_should_trip',
                      'zero_place_breaker_record', 'note_zero_place_breaker',
                      'ZERO_PLACE_BREAKER_THRESHOLD', 'cw_deploy_zeroplace')
    offenders: list[str] = []
    for p in (repo / 'src').rglob('*.py'):
        text = p.read_text(encoding='utf-8', errors='ignore')
        for sym in collect_banned + breaker_banned:
            if sym in text:
                offenders.append(f'{p.relative_to(repo)}:{sym}')
    assert not offenders, f'退役机制符号残留(下线机制复活): {sorted(offenders)}'
