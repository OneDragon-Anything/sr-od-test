"""CwScreenBattleWait 收编锁(W971 05-battle §1,P4)。

结构变化:战斗/结算窗口(原 cw_loop 分支 1f/2/3/3b/5/6)收编进
``cw_screen.cw_screen_battle_wait.CwScreenBattleWait``;本文件锁新结构的**行为语义锚**
(源码弱锁,风格同 test_cw_telemetry_collect.test_branch_wiring_in_source):
三段式出口/终局分叉/M39 长按/#25 读点延迟/点空白加速/委托接线/状态机随迁。
"""
import inspect


def _bwo():
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_battle_wait
    return cw_screen_battle_wait


def _loop_src() -> str:
    from sr_od.application.currency_war.operations import cw_loop
    return inspect.getsource(cw_loop.CwLoop.loop)


def test_wait_node_three_exits() -> None:
    """三出口:白名单完成(back_to_loop)/团灭终局(terminal_lobby)/bail。"""
    src = inspect.getsource(_bwo().CwScreenBattleWait.wait)
    assert "self.round_success('terminal_lobby')" in src
    assert "self.round_success('back_to_loop')" in src
    assert 'round_fail' in src   # 超时兜底 bail 交主循环


def test_completion_whitelist_anchors() -> None:
    """完成判据白名单 = 05-battle §1 裁决集:备战/补给/遭遇/投资策略/强敌来袭
    + 位面过渡锚(点击空白处继续);位面简报不列(仅入场出现,用户裁决)。"""
    anchors = _bwo().CwScreenBattleWait.COMPLETION_ANCHORS
    names = ' '.join(a[1] for a in anchors)
    for token in ('备战标识-购买经验', '标识-补给阶段', '标识-遭遇节点',
                  '标识-请选择投资策略', '标识-强敌来袭'):
        assert token in names, token
    src = inspect.getsource(_bwo().CwScreenBattleWait._hit_completion_anchor)
    assert '点击空白处继续' in src
    # 位面简报不列:白名单锚集与判定函数源码内均无其锚(「标识-位面简报」)
    assert '标识-位面简报' not in names
    assert '标识-位面简报' not in inspect.getsource(
        _bwo().CwScreenBattleWait._hit_completion_anchor)


def test_read_point_delay_and_long_press() -> None:
    """②段时序锚:#25 读点前等 1.5s;M39 停留 ≥3 轮长按 (960,898) 兜底。"""
    src = inspect.getsource(_bwo().CwScreenBattleWait.wait)
    assert 'time.sleep(1.5)' in src
    assert 'press_time=0.5' in src
    assert _bwo().CwScreenBattleWait.SETTLE_STAY_LONG_PRESS == 3
    assert _bwo().CwScreenBattleWait.SETTLEMENT_NEXT.x == 960
    assert _bwo().CwScreenBattleWait.SETTLEMENT_NEXT.y == 898


def test_blank_accel_and_defeat_state_machine() -> None:
    """点空白加速在场;败局状态机(_saw_defeat_settlement/hp=0 补录)随迁。"""
    src = inspect.getsource(_bwo().CwScreenBattleWait.wait)
    assert '点击空白加速' in src
    assert 'BLANK.center' in src
    assert 'saw_defeat_settlement = True' in src
    assert 'last_outcome_hp = 0' in src


def test_loop_delegation_wiring() -> None:
    """loop 委托接线:战斗窗口 → CwScreenBattleWait.execute;3c 收口不随迁(遥测
    连续性红线:runs summary/分配器/存档写端留在主循环)。"""
    src = _loop_src()
    assert '_battle_wait.execute()' in src
    assert '_battle_wait_active' in src
    assert '_frame_in_battle_window' in src
    assert "record_run_summary(" in src   # 3c 收口仍在 loop
    assert 'match_archive' in inspect.getsource(
        __import__('sr_od.application.currency_war.operations.cw_loop',
                   fromlist=['x']).CwLoop)
    # 旧内联分支已移除(收编完成判据:不再双写)
    assert '前往结算", lcs_percent=0.8' not in src


def test_settlement_state_defaults() -> None:
    """SettlementState 生命周期默认:局级零值起步(残留判定/防重指纹干净)。"""
    st = _bwo().SettlementState()
    assert st.last_outcome_hp is None
    assert st.saw_defeat_settlement is False
    assert st.rounds_done == 0
    assert st.last_settle_fp is None
    assert st.last_loss_fp is None
    assert st.saw_settlement is False
