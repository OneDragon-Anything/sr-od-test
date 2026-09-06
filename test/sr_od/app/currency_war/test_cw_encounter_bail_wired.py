"""遭遇节点纵深防御接线锁(W835 审计+C1 治本配套,2026-08-30):

三防线须同时在场,缺一即回退到局 12/13 形态(遭遇屏挡 deploy/equip 致环内空转):
① 遭遇节点屏在 UPPER_SCREENS(弹窗在场 = 非备战帧,gate 排除链不断);
② cw_loop 引用 CwScreenEncounter(专属 handler 消化二选一难度选择);
③ cw_screen_prep 事件 overlay bail 清单含 encounter 标签(loop 0i 判据 miss 时
   纵深防御:即刻 bail 交外环,禁环内空转)。

背景:遭遇二选一=决策语义交互 overlay,曾被 P0 清场注册表误关(C1,commit
4a2b3f27 修复)且 bail 清单缺遭遇节点(W835/W839 审计实锤,本锁防回归)。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""


def test_encounter_screen_registered_as_upper() -> None:
    """遭遇节点屏在 UPPER_SCREENS:弹窗在场 = 非备战帧(gate 排除链完整)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    assert '货币战争-遭遇节点' in cw_obs_core.UPPER_SCREENS


def test_encounter_bail_and_handler_wired() -> None:
    """bail 清单与专属 handler 双接线:遭遇屏在场即 bail 交 CwScreenEncounter 消化。"""
    import inspect

    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep
    from sr_od.application.currency_war.kernel.cw_overlay_registry import (
        derive_decision,
    )
    from sr_od.application.currency_war.operations import cw_loop
    assert 'CwScreenEncounter' in inspect.getsource(cw_loop)
    # bail 扫描单一源已收拢至 registry(B 面切换):成员判定改为派生集三元组
    assert ('货币战争-遭遇节点', '标识-遭遇节点', 'encounter') in {
        (s.screen_name, s.anchor_area, s.bail_tag) for s in derive_decision()}


def test_encounter_refresh_execution_wired() -> None:
    """分支刷新执行链接线(dd-004):decide_encounter 的 refresh 建议必须有消费端。

    断链史:决策侧 refresh 字段 + 全克换批分支 + 纯逻辑测试锁(P1 起就在),
    handler 从未消费 → 「刷新换批」策略意图被静默丢弃。四件须同时在:
    ① handler 消费 pick.refresh;② session 单次标志(优势布局每局 1 次,跨实例);
    ③ 刷新后 refresh_used=True 重读重决策(防建议→执行死循环);
    ④ reader 读「剩余次数:N」(无次数不刷)。
    """
    import dataclasses
    import inspect

    from sr_od.application.currency_war.kernel.cw_exec_state import ExecState
    from sr_od.application.currency_war.kernel.cw_strategy_session import StrategySession
    from sr_od.application.currency_war.obs import cw_node_obs
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_encounter
    src = inspect.getsource(cw_screen_encounter)
    assert 'pick.refresh' in src, 'handler 未消费 refresh 建议(断链回退)'
    assert '_encounter_refresh_used' in src, 'session 单次标志缺失(重入反复尝试风险)'
    assert 'refresh_used=True' in src, '刷新后未带 refresh_used 重决策(建议→执行死循环风险)'
    assert 'read_encounter_refresh_count' in src, '剩余次数 reader 未接(无次数盲刷风险)'
    assert '剩余次数' in inspect.getsource(cw_node_obs), 'reader 正则单一源缺失'
    # 单次标志迁 ExecState(session 职责分离批):声明面 = ExecState 正式字段
    names = {f.name for f in dataclasses.fields(ExecState)}
    assert '_encounter_refresh_used' in names, '执行层字段未升正式(动态 setattr 面消失)'
