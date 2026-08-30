"""遭遇节点纵深防御接线锁(W835 审计+C1 治本配套,2026-08-30):

三防线须同时在场,缺一即回退到局 12/13 形态(遭遇屏挡 deploy/equip 致环内空转):
① 遭遇节点屏在 UPPER_SCREENS(弹窗在场 = 非备战帧,gate 排除链不断);
② battle_loop 引用 HandleEncounter(专属 handler 消化二选一难度选择);
③ prep_director 事件 overlay bail 清单含 encounter 标签(loop 0i 判据 miss 时
   纵深防御:即刻 bail 交外环,禁环内空转)。

背景:遭遇二选一=决策语义交互 overlay,曾被 P0 清场注册表误关(C1,commit
4a2b3f27 修复)且 bail 清单缺遭遇节点(W835/W839 审计实锤,本锁防回归)。
"""


def test_encounter_screen_registered_as_upper() -> None:
    """遭遇节点屏在 UPPER_SCREENS:弹窗在场 = 非备战帧(gate 排除链完整)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    assert '货币战争-遭遇节点' in cw_obs_core.UPPER_SCREENS


def test_encounter_bail_and_handler_wired() -> None:
    """bail 清单与专属 handler 双接线:遭遇屏在场即 bail 交 HandleEncounter 消化。"""
    import inspect

    from sr_od.application.currency_war import prep_director
    from sr_od.application.currency_war.operations import battle_loop
    assert 'HandleEncounter' in inspect.getsource(battle_loop)
    assert "'encounter'" in inspect.getsource(prep_director)
