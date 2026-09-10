"""T-164 C1 装备计划随指令下发·新锁五件(ADR-0601 §3-C1;v2 方案 §5.2 +
轻复审 R1/R2 修正版)。

结构批语义:C1 修复 = 防御闸上提为「计划随指令下发」——
- 计划产出位 = 分发段 ``prep_actions._build_equip_wear_plan``(对执行帧
  现读后由 kernel 判据单一源求值),静态计划(EquipWearStep 列表)随
  ``CwOpEquipAll.__init__(ctx, plan)`` 构造下发;
- 空计划 = 合法稳态具名 NOOP(dd-037 形态):分发段短路发出事实 True,
  闩写点唯一仍在 ``PrepActionExecutor.execute`` 执行位(批3a 发出即置,
  T-223 回执退役后原「只看 ok」改「发出事实」)——hold 期闭环不变量
  「每期 RunEquip 恰一次发出收敛」= dd-027 活锁不返场的直接断言面(锁②);
- op 侧四 kernel 判据(resolve_wear_release/classify_item_hold/
  apply_equip_env_variants/resolve_affix_priority_order)零引用(锁③,
  Q6 红线「不得残留为 op 调用的 helper」的执行断言);
- 计划步件两次现读不可定位 → 装备版 STATUS_PLAN_STALE round_fail,闩不置,
  下帧重派重算(tools C3 同形;锁④含对偶面);
- 门①谓词与产出位过滤同源对读(锁⑤;本批不做 kernel 收编,以锁承担
  漂移守卫,显式声明见 v2 §5.2-5)。

先红后绿口径:锁③/锁②在实现前跑 = 旧 op 内求值残留/直调 _execute_dispatch
绕闩写点时红;本文件随实现批交付时全绿。
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

_ACT = '货币战争-备战'


# ==================== 公共桩面 ====================

def _mk_comp(*, key_equips: list[str] | None = None,
             core_chars: list[str] | None = None,
             form_tiers: dict | None = None) -> SimpleNamespace:
    """comp 鸭型桩(form_progress 契约面:form_tiers/or_legs/required_deployed)。"""
    return SimpleNamespace(key_equips=key_equips or [], core_chars=core_chars or [],
                           form_tiers=form_tiers or {}, or_legs=None,
                           required_deployed=None)


def _mk_builder_env(monkeypatch, *, owned_hits: list, deployed: list,
                    comp=None, state=None, row_equipped: dict | None = None):
    """``_build_equip_wear_plan`` 黑盒直调环境桩。

    全部读点打在**源模块属性**(builder 函数内延迟导入,每次从源模块取):
    read_equips=cw_equipment / read_row_equipped+read_deployed_chars=
    cw_identity_obs / select_back_layout=cw_back_layout / _area_rect=prep_actions。
    模板资源走 ctx 缓存命中(cw_equip_templates 等预置 object()),不触真实 assets。
    """
    import sr_od.application.currency_war.prep_actions as pa_mod
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.obs import (
        cw_back_layout,
        cw_equipment,
        cw_identity_obs,
    )

    sess = StrategySession()
    sess.last_state = state or SimpleNamespace(
        plane=3, round_num=5, node_type='奖励', enemy_affixes=[],
        board={}, deployed=[])
    sess.strategy_state = SimpleNamespace(target_comp=comp)
    match = SimpleNamespace(session=sess,
                            exec_state=SimpleNamespace(equip_drag_fail_counts={}))
    ctx = SimpleNamespace(
        cw_equip_templates=object(),   # get_equip_templates_cached 缓存命中
        cw_equip_tm_grays=object(),    # get_equip_tm_grays_cached 缓存命中
        cw_portrait_templates=object(),   # get_avatar_templates_cached 缓存命中
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        cw_match=match)
    monkeypatch.setattr(pa_mod, '_area_rect',
                        lambda c, name, screen: SimpleNamespace(
                            x1=1620, y1=100, x2=1918, y2=900))
    monkeypatch.setattr(cw_equipment, 'read_equips',
                        lambda scr, tpl, equip_rect=None: owned_hits)
    monkeypatch.setattr(cw_identity_obs, 'read_row_equipped',
                        lambda c, scr, grays, prefix, n: (row_equipped or {}))
    monkeypatch.setattr(cw_identity_obs, 'read_deployed_chars',
                        lambda c, scr, tpl: deployed)
    monkeypatch.setattr(cw_back_layout, 'select_back_layout',
                        lambda c, scr, level=None, cap=None,
                        level_trusted=None: (6, ''))
    host = SimpleNamespace(screenshot=lambda: object())
    return ctx, host, sess


def _hit(name: str, x: int = 1800, y: int = 200) -> tuple:
    """read_equips 命中三元组桩(名, (cx, cy), score)。"""
    return (name, (x, y), 0.9)


# ==================== 锁①:产出位接线(hold 两形态 + 资源前置) ====================

def test_builder_hold_row1_yields_empty_plan_with_verbatim_reason(monkeypatch) -> None:
    """锁①-①:row1 三门不中(hold 活跃)→ steps==[] 且 empty_reason 与
    现行 op 停手归因字面量**逐字相等**(分类器 startswith('opening_hold')
    与分键锁 test_cw_opening_tool_semantics::TestTelemetryDomainKey 的
    词表消费口径零漂移锚)。"""
    from sr_od.application.currency_war.prep_actions import _build_equip_wear_plan

    state = SimpleNamespace(plane=1, round_num=1, node_type='奖励',
                            enemy_affixes=[], board={}, deployed=[])
    deployed = [SimpleNamespace(char_id='姬子', position_pref='front', slot=1)]
    ctx, host, _sess = _mk_builder_env(
        monkeypatch, owned_hits=[_hit('轮滑鞋')], deployed=deployed, state=state)
    build = _build_equip_wear_plan(ctx, host)
    assert build.steps == [], f'hold 活跃必须空计划,实得 {build.steps!r}'
    assert build.empty_reason == 'opening_hold(row1):三门全不中(保留域扣留)', \
        f'empty_reason 字面量漂移:{build.empty_reason!r}'
    assert build.branch == 'm7'
    # 哨兵输入(计划面挂点):可穿名单非空 = hold 期哨兵仍可见 owned 滞留
    assert build.owned_wearable_names == ['轮滑鞋']


def test_builder_hold_row2_yields_empty_plan_with_verbatim_reason(monkeypatch) -> None:
    """锁①-②:row2 已定型扣留(committed 活跃 ∧ 0<form<COMMIT_FRAC ∧
    候选全非 key)→ steps==[] 且 empty_reason 逐字 = 现行 '过渡期hold:无
    key_equips 命中(全攒着)'(分类器 startswith('过渡期hold') 消费口径)。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMMIT_FRAC
    from sr_od.application.currency_war.prep_actions import _build_equip_wear_plan

    assert 0.0 < COMMIT_FRAC < 1.0
    comp = _mk_comp(key_equips=['以牙还牙甲'], core_chars=['姬子'],
                    form_tiers={'量': 4})
    state = SimpleNamespace(plane=2, round_num=3, node_type='奖励',
                            enemy_affixes=[], board={'量': 1}, deployed=[])
    deployed = [SimpleNamespace(char_id='姬子', position_pref='front', slot=1)]
    ctx, host, _sess = _mk_builder_env(
        monkeypatch, owned_hits=[_hit('垃圾袋')], deployed=deployed,
        comp=comp, state=state)
    build = _build_equip_wear_plan(ctx, host)
    assert build.steps == [], f'committed hold 必须空计划,实得 {build.steps!r}'
    assert build.empty_reason == '过渡期hold:无 key_equips 命中(全攒着)', \
        f'empty_reason 字面量漂移:{build.empty_reason!r}'


def test_builder_release_plan_matches_equip_allocation_same_args(monkeypatch) -> None:
    """锁①-③:release 帧(无 hold)非空计划 → steps 的 (char,item,row,slot)
    ≡ **同参直调** ``equip_allocation`` 输出 + 逐对 (row,slot) 戳记(deployed
    首个同名角色)——「builder 与 sim 消费同一 kernel 单一源、参数面同构」
    声明(v2 §6-9)的执行断言。"""
    from sr_od.application.currency_war.kernel.cw_comps import equip_allocation
    from sr_od.application.currency_war.prep_actions import _build_equip_wear_plan

    deployed = [
        SimpleNamespace(char_id='姬子', position_pref='front', slot=1),
        SimpleNamespace(char_id='卡芙卡', position_pref='front', slot=2),
        SimpleNamespace(char_id='黑塔', position_pref='back', slot=3),
    ]
    ctx, host, _sess = _mk_builder_env(
        monkeypatch,
        owned_hits=[_hit('财富宝钻'), _hit('垃圾袋', x=1700, y=300)],
        deployed=deployed)
    build = _build_equip_wear_plan(ctx, host)
    assert build.fail_reason == ''
    assert build.steps, 'release 帧必须产出非空计划'
    # 同参 = builder 现场参数面(comp=None/deployed 桩/owned 可穿序/occupied 空/
    # priority_order=None[enemy_affixes 空 → 词缀层不启用,resolve 返 None])。
    alloc_ref = equip_allocation(
        None, deployed, ['财富宝钻', '垃圾袋'], {}, priority_order=None)
    assert [(s.char_name, s.item_name) for s in build.steps] == alloc_ref, \
        f'计划步序列 ≡ 同参 equip_allocation 输出(单一源对拍),实得 ' \
        f'{[(s.char_name, s.item_name) for s in build.steps]!r} vs {alloc_ref!r}'
    for s in build.steps:
        d = next(d for d in deployed if d.char_id == s.char_name)
        assert (s.row, s.slot) == (d.position_pref, int(d.slot)), \
            f'(row,slot) 戳记须与 deployed 物理槽位一致:{s!r}'
    assert build.owned_wearable_names == ['财富宝钻', '垃圾袋']
    # 产出期快照(step 不可变):防执行中途改计划
    import dataclasses
    assert all(dataclasses.is_dataclass(s) for s in build.steps)


def _bare_builder_env(monkeypatch, *, deployed) -> tuple:
    """资源前置子场景的独立桩面(与 _mk_builder_env 解耦:模板/grays 走
    ea 模块级 helper 桩,便于逐场景单独 patch 成缺失态而不串扰)。"""
    import sr_od.application.currency_war.prep_actions as pa_mod
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.obs import (
        cw_back_layout,
        cw_equipment,
        cw_identity_obs,
    )

    sess = StrategySession()
    sess.last_state = SimpleNamespace(plane=3, round_num=5, node_type='奖励',
                                      enemy_affixes=[], board={}, deployed=[])
    sess.strategy_state = SimpleNamespace(target_comp=None)
    ctx = SimpleNamespace(
        cw_equip_templates=object(), cw_equip_tm_grays=object(),
        cw_portrait_templates=object(),
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        cw_match=SimpleNamespace(
            session=sess,
            exec_state=SimpleNamespace(equip_drag_fail_counts={})))
    monkeypatch.setattr(pa_mod, '_area_rect',
                        lambda c, name, screen: SimpleNamespace(
                            x1=1620, y1=100, x2=1918, y2=900))
    monkeypatch.setattr(cw_equipment, 'read_equips',
                        lambda scr, tpl, equip_rect=None: [])
    monkeypatch.setattr(cw_identity_obs, 'read_row_equipped',
                        lambda c, scr, grays, prefix, n: {})
    monkeypatch.setattr(cw_identity_obs, 'read_deployed_chars',
                        lambda c, scr, tpl: deployed)
    monkeypatch.setattr(cw_back_layout, 'select_back_layout',
                        lambda c, scr, level=None, cap=None,
                        level_trusted=None: (6, ''))
    host = SimpleNamespace(screenshot=lambda: object())
    return ctx, host


def test_builder_missing_templates_fails_not_empty_plan(monkeypatch) -> None:
    """资源前置①:模板缺失 → fail_reason 通道(ok=False 闩不置,同今日
    op round_fail 同形),**不产空计划**(空计划 = 合法稳态,资源缺失 =
    失败,两通道禁混)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_op_equip_all as ea
    from sr_od.application.currency_war.prep_actions import _build_equip_wear_plan

    ctx, host = _bare_builder_env(
        monkeypatch, deployed=[SimpleNamespace(char_id='姬子',
                                               position_pref='front', slot=1)])
    monkeypatch.setattr(ea, 'get_equip_templates_cached', lambda c: None)
    build = _build_equip_wear_plan(ctx, host)
    assert build.steps == [] and build.fail_reason == 'cw_equip 模板库未加载'
    assert build.empty_reason == '', 'fail_reason 与 empty_reason 禁并用'


def test_builder_missing_rect_fails_not_empty_plan(monkeypatch) -> None:
    """资源前置②:区域 rect 缺失 → fail_reason 通道。"""
    import sr_od.application.currency_war.prep_actions as pa_mod
    from sr_od.application.currency_war.prep_actions import _build_equip_wear_plan

    ctx, host = _bare_builder_env(
        monkeypatch, deployed=[SimpleNamespace(char_id='姬子',
                                               position_pref='front', slot=1)])
    monkeypatch.setattr(pa_mod, '_area_rect', lambda c, name, screen: None)
    build = _build_equip_wear_plan(ctx, host)
    assert build.fail_reason == 'screen_info 区域-道具装备 缺失'
    assert build.empty_reason == ''


def test_builder_missing_tm_grays_fails_not_empty_plan(monkeypatch) -> None:
    """资源前置③:TM grays 缺失 → fail_reason 通道。"""
    import sr_od.application.currency_war.operations.cw_op.cw_op_equip_all as ea
    from sr_od.application.currency_war.prep_actions import _build_equip_wear_plan

    ctx, host = _bare_builder_env(
        monkeypatch, deployed=[SimpleNamespace(char_id='姬子',
                                               position_pref='front', slot=1)])
    monkeypatch.setattr(ea, 'get_equip_tm_grays_cached', lambda c: None)
    build = _build_equip_wear_plan(ctx, host)
    assert build.fail_reason == 'cw_equip TM grays 未加载(无法读槽位占位)'
    assert build.empty_reason == ''


# ==================== 锁②:空计划闩闭合(dd-027 场景;R1 修正锚) ====================

def test_empty_plan_noop_sets_equip_latch_and_keeps_shopped(monkeypatch) -> None:
    """锁②(R1 修正:断言入口 = **公共入口 execute(RunEquip())**,置闩在
    execute 不在 _execute_dispatch——直调分派绕过闩写点该锁必假红):
    executor 级空计划场景 →
    ①机械摘要含具名原因(发出事实 True = NOOP 合法稳态;批3a:T-223
      端口无返回,摘要经 last_detail 旁路);
    ②``state.cw4_m7_equipped_phase == (plane, round)``(**闩照置 = dd-027
      活锁不返场的直接断言**:hold 期门①恒真时,门②因闩置位挡同期重发;
      批3a 置位判据 = 发出事实,原 ok 门随 T-223 退役);
    ③预置 ``cw4_shopped_phase`` 后未被清(S1 清键门被调但 RunEquip 不命中
      mark_s1_route_check 三路径封闭枚举——landed=False 行为中性,R2);
    ④哨兵计划面挂点在场(equipped=0 + 具名原因,经 record_zero_wear_defect)。"""
    import sr_od.application.currency_war.prep_actions as pa_mod
    from sr_od.application.currency_war.kernel.cw_prep_actions import RunEquip
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_equip_all as ea,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        state_of,
    )

    sess = StrategySession()
    sess.last_state = SimpleNamespace(plane=1, round_num=5, node_type='奖励',
                                      enemy_affixes=[])
    match = SimpleNamespace(session=sess,
                            exec_state=SimpleNamespace(equip_drag_fail_counts={}))
    ctx = SimpleNamespace(screen_loader=SimpleNamespace(get_screen=lambda name: None),
                          run_context=None, cw_match=match)
    host = SimpleNamespace(
        screenshot=lambda: object(),
        check_and_update_current_screen=lambda screen, screen_name_list: _ACT)
    build = pa_mod.EquipPlanBuild(
        steps=[], empty_reason='opening_hold(row1):三门全不中(保留域扣留)',
        fail_reason='', branch='m7', owned_wearable_names=['财富宝钻'])
    monkeypatch.setattr(pa_mod, '_build_equip_wear_plan', lambda c, o: build)
    sentinel_calls: list = []
    monkeypatch.setattr(ea, 'record_zero_wear_defect',
                        lambda c, eq, names, reason:
                        sentinel_calls.append((eq, tuple(names), reason)))
    ex = pa_mod.PrepActionExecutor(host, ctx)
    st = state_of(sess)
    st.cw4_shopped_phase = (1, 5)   # 预置 S1 闩(第三断言的对照基线)
    ex.execute(RunEquip())   # 批3a:机械执行无返回
    detail = ex.last_detail
    assert '计划空' in detail, f'NOOP 形态漂移:{detail!r}'
    assert 'opening_hold(row1):三门全不中(保留域扣留)' in detail, \
        f'具名原因必须逐字透传进 detail:{detail!r}'
    assert st.cw4_m7_equipped_phase == (1, 5), \
        f'闩未照置(dd-027 活锁病返场信号):{st.cw4_m7_equipped_phase!r}'
    assert st.cw4_shopped_phase == (1, 5), \
        'S1 清键闩被清(RunEquip 不应命中任何清键路径)'
    assert sentinel_calls == [(0, ('财富宝钻',),
                               'opening_hold(row1):三门全不中(保留域扣留)')], \
        f'哨兵计划面挂点失守:{sentinel_calls!r}'


# ==================== 锁③:op 机械消费(四判据零引用 grep) ====================

def test_equip_op_kernel_criteria_free() -> None:
    """锁③:全 cw_op_equip_all.py 源码对四 kernel 判据**零字面引用**
    (与退役墓碑锁同型;Q6 红线「产出位不得残留为 op 调用的 helper」的
    执行断言——换皮 = 违规照旧)。禁表含 N1 加固面(equip_alloc_empty_
    reason/build_equip_env_signals/form_progress/committed_from,求值块
    搬迁件残留 = 迁移不全信号);classify_zero_wear_stop_reason 正确豁免
    (遥测分类器非判据,哨兵保留面)。"""
    from pathlib import Path

    banned = ('resolve_wear_release', 'classify_item_hold',
              'apply_equip_env_variants', 'resolve_affix_priority_order',
              'equip_alloc_empty_reason', 'build_equip_env_signals',
              'form_progress', 'committed_from')
    op_path = (Path(__file__).resolve().parents[5] / 'src'
               / 'sr_od/application/currency_war/operations/cw_op'
               / 'cw_op_equip_all.py')
    text = op_path.read_text(encoding='utf-8')
    offenders = [sym for sym in banned if sym in text]
    assert not offenders, f'op 源码残留判据函数引用(求值块迁移不全): {offenders}'
    assert 'classify_zero_wear_stop_reason' in text, \
        '哨兵归域分类器应在场(禁表豁免面,勿误删)'


# ==================== 锁④:计划失效具名上报(STALE 三面) ====================

def test_plan_stale_fail_on_double_miss(monkeypatch) -> None:
    """锁④-①(op 级行为):计划步件首读+一次机械现读重试均 miss →
    round_fail 且 STATUS_PLAN_STALE 具名状态在场(禁散字符串/禁 success
    吞失效;fail-fast 闩不置 = 下帧重派重算)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_equip_all as ea,
    )

    op = ea.CwOpEquipAll.__new__(ea.CwOpEquipAll)
    op.plan = [ea.EquipWearStep(item_name='幻影件', char_name='姬子',
                                row='front', slot=1)]
    op.last_screenshot = object()
    monkeypatch.setattr(op, 'screenshot', lambda: object())
    monkeypatch.setattr(op, 'check_and_update_current_screen',
                        lambda screen, screen_name_list: _ACT)
    monkeypatch.setattr(op, '_get_templates', lambda: object())
    monkeypatch.setattr(op, '_get_tm_grays', lambda: object())
    monkeypatch.setattr(ea, '_area_rect',
                        lambda ctx, name, screen: SimpleNamespace(
                            x1=1620, y1=100, x2=1918, y2=900))
    monkeypatch.setattr(ea, 'read_equips',
                        lambda scr, tpl, equip_rect=None: [])   # 两次现读均 miss
    monkeypatch.setattr(ea, 'record_zero_wear_defect', lambda *a, **k: None)
    op.ctx = SimpleNamespace(cw_match=None)
    res = op.equip_all()
    assert res.result.name == 'FAIL'
    assert ea.CwOpEquipAll.STATUS_PLAN_STALE in (res.status or ''), \
        f'计划失效必须以具名状态 fail,实得 {res.status!r}'


def test_plan_stale_source_wiring() -> None:
    """锁④-②(源码契约,同 test_node_report_wiring_contract 形态):
    equip_all 节点内 round_fail(CwOpEquipAll.STATUS_PLAN_STALE) 在场。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_equip_all import (
        CwOpEquipAll,
    )
    src = inspect.getsource(CwOpEquipAll.equip_all)
    assert 'round_fail(CwOpEquipAll.STATUS_PLAN_STALE)' in src, \
        '计划失效上报分支失守(STATUS_PLAN_STALE 语义回归)'


def test_plan_stale_executor_status_flows_through(monkeypatch) -> None:
    """锁④-③(executor 级,与锁②对偶;批3a 重推):plan_stale 形态
    (组合 op 返回 STATUS_PLAN_STALE)经公共入口 execute → op 级结果仅作
    摘要透传(STATUS_PLAN_STALE 显影进 detail = 观察侧对账供给面)、
    **闩照置**(批3a 发出即置:原「ok=False 闩不置、下帧重派」消费成败
    回执,随 T-223 退役——失败面改由装备期望态对账族在下一入口暴露,
    纠偏/缺陷台账;「闩改观察侧事实驱动」的重推挂账批5)。op 内真行为面
    (两次现读 miss → round_fail(STALE))由锁④①辖;本锁在执行器边界以
    桩 op 呈现该形态(真 op 构造走 SrOperation 框架初始化链,桩法同
    test_cw_mandate_lifecycle 的 _StubDeploy 先例)。"""
    import sr_od.application.currency_war.prep_actions as pa_mod
    from sr_od.application.currency_war.kernel.cw_prep_actions import RunEquip
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_equip_all as ea,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        state_of,
    )

    class _StubEquip:
        STATUS_PLAN_STALE = ea.CwOpEquipAll.STATUS_PLAN_STALE

        def __init__(self, ctx, plan) -> None:
            self.plan = list(plan)

        def execute(self):
            return SimpleNamespace(success=False, status=self.STATUS_PLAN_STALE)

    monkeypatch.setattr(ea, 'CwOpEquipAll', _StubEquip)
    sess = StrategySession()
    sess.last_state = SimpleNamespace(plane=1, round_num=5, node_type='奖励',
                                      enemy_affixes=[])
    match = SimpleNamespace(session=sess,
                            exec_state=SimpleNamespace(equip_drag_fail_counts={}))
    ctx = SimpleNamespace(screen_loader=SimpleNamespace(get_screen=lambda name: None),
                          run_context=None, cw_match=match)
    host = SimpleNamespace(
        screenshot=lambda: object(),
        check_and_update_current_screen=lambda screen, screen_name_list: _ACT)
    build = pa_mod.EquipPlanBuild(
        steps=[ea.EquipWearStep(item_name='幻影件', char_name='姬子',
                                row='front', slot=1)],
        fail_reason='', branch='m7', owned_wearable_names=['财富宝钻'])
    monkeypatch.setattr(pa_mod, '_build_equip_wear_plan', lambda c, o: build)
    ex = pa_mod.PrepActionExecutor(host, ctx)
    st = state_of(sess)
    assert st.cw4_m7_equipped_phase is None   # 清白起点
    ex.execute(RunEquip())   # 批3a:机械执行无返回
    detail = ex.last_detail
    assert ea.CwOpEquipAll.STATUS_PLAN_STALE in detail, \
        f'op 级 STATUS 必须显影透传(观察侧对账供给面):{detail!r}'
    assert st.cw4_m7_equipped_phase == (1, 5), \
        (f'批3a 发出即置:组合 op 已派发 = 闩照置(失败面改观察侧期望态'
         f'对账暴露;原「闩不置重派」随 ok 回执退役):{st.cw4_m7_equipped_phase!r}')


# ==================== 锁⑤:门①谓词与产出位同源对读 ====================

def test_m7_gate_predicate_matches_builder_wearable_filter() -> None:
    """锁⑤:门① ``m7_wearable_exists`` 真值 ≡ 产出位可穿过滤列表非空
    (对语料:注册表穿戴件/工具件/未登记名/空串)——防发射面门①与
    分发段过滤面双谓词漂移。显式声明:本批不做 kernel 级单一源收编
    (v2 §5.2-5),以本锁承担漂移守卫。"""
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIP_TOOL_CATEGORY,
    )
    from sr_od.application.currency_war.obs.cw_equipment import EQUIPMENTS
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
        m7_wearable_exists,
    )

    def builder_filter(names: list[str]) -> list[str]:
        # 与 _build_equip_wear_plan 求值块同口径(逐字;双源对读的另一源)
        return [n for n in names
                if EQUIPMENTS.get(n) is not None
                and EQUIPMENTS[n].category != EQUIP_TOOL_CATEGORY]

    corpus = ['财富宝钻', '垃圾袋', '冶金炉', '拆装扳手', '轮滑鞋',
              '不存在件X', '']
    assert m7_wearable_exists(corpus) == bool(builder_filter(corpus))
    # 单点对照:纯工具/未知名 → 门① False(变换面存在性,非「owned 非空」)
    assert m7_wearable_exists(['冶金炉', '不存在件X']) is False
    assert builder_filter(['冶金炉', '不存在件X']) == []
    assert m7_wearable_exists(['财富宝钻']) is True
    assert builder_filter(['冶金炉', '财富宝钻']) == ['财富宝钻']
