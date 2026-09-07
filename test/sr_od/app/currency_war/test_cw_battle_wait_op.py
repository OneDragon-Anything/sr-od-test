"""CwScreenBattleWait 收编锁(W971 05-battle §1,P4)。

结构变化:战斗/结算窗口(原 cw_loop 分支 1f/2/3/3b/5/6)收编进
``cw_screen.cw_screen_battle_wait.CwScreenBattleWait``;本文件锁新结构的**行为语义锚**
(源码弱锁,风格同 test_cw_telemetry_collect.test_branch_wiring_in_source):
三段式出口/终局分叉/M39 长按/#25 读点延迟/点空白加速/委托接线/状态机随迁
+ 结算点 defer 复位宿主(执行侧载体,session 职责分离批)。
"""
import inspect
import time
from types import SimpleNamespace


def _bwo():
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait,
    )
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


def test_loop_delegation_wiring() -> None:
    """loop 委托接线:战斗窗口 → CwScreenBattleWait(经 dispatch 包装,
    ADR-0584 改写:原字面 ``_battle_wait.execute()`` 随包装上收);3c 收口
    不随迁(遥测连续性红线:runs summary/分配器/存档写端留在主循环)。"""
    src = _loop_src()
    assert '_dispatch_screen_op(' in src
    assert 'self._battle_wait,' in src   # 战斗窗经包装分发(journal=战斗等待)
    assert '_battle_wait_active' in src
    assert '_frame_in_battle_window' in src
    assert "record_run_summary(" in src   # 3c 收口仍在 loop
    assert 'match_archive' in inspect.getsource(
        __import__('sr_od.application.currency_war.operations.cw_loop',
                   fromlist=['x']).CwLoop)
    # 旧内联分支已移除(收编完成判据:不再双写)
    assert '前往结算", lcs_percent=0.8' not in src


def test_settle_defer_reset_reads_exec_state(monkeypatch) -> None:
    """结算点 defer 复位宿主 = 执行侧载体 ExecState(session 职责分离批锁)。

    defer_count 已随 ADR-0563 迁 ExecState(session 上无该字段);复位端若
    仍读 session 形态 = 「继续挑战」点击后必 AttributeError,备战 defer
    复位防线(结算点 = 新备战轮入口)每次触发即失效。本锁走**真实 wait()
    结算分支**(只桩截图/画面判定/框架返回;依赖面桩法同
    test_cw_round_flow.test_loop_outcome_carries_damage),锁「复位生效于
    ctx.cw_match.exec_state」。"""
    monkeypatch.setattr(time, 'sleep', lambda *_: None)   # #25 读点延迟/步进等待不实等

    from sr_od.application.currency_war.kernel.cw_exec_state import ExecState
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    class _Op(_bwo().CwScreenBattleWait):
        def __init__(self, exec_state: ExecState):  # noqa: D107  桩:bypass SrOperation.__init__
            self._st = _bwo().SettlementState(
                run_start_ts=time.monotonic(), is_new_match=True)
            self._unknown_streak = 0
            self._cw_config = None
            self._es = exec_state
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=StrategySession(),
                    exec_state=exec_state,
                    strategy=SimpleNamespace(),
                ),
                ocr_service=SimpleNamespace(
                    get_ocr_result_list=lambda image, rect=None,
                    color_range=None, crop_first=False: []),
            )

        def screenshot(self, *a, **k):
            return None

        def round_by_find_area(self, screen, screen_name, area_name, **kw):
            # 只有「继续挑战」命中 → 走 ②段结算分支;大厅/白名单锚全不命中
            return SimpleNamespace(is_success=(
                screen_name == '货币战争-结算' and area_name == '按钮-继续挑战'))

        def round_by_find_and_click_area(self, screen, screen_name, area_name, **kw):
            return SimpleNamespace(is_success=True)   # 「继续挑战」点击成功 → 复位段

        def round_by_ocr(self, *a, **k):
            return SimpleNamespace(is_success=False)

        def _record_round_outcome(self, screen, telemetry_only=False):
            pass   # 结算遥测链另有专锁(test_cw_round_flow),本锁只辖 defer 复位

    es = ExecState()
    es.defer_count = 2   # 门=2 防空转环在途:结算点应复位归零
    op = _Op(es)
    op.last_screenshot = None
    op.wait()

    assert es.defer_count == 0, '结算点 defer 计数须复位(宿主 = cw_match.exec_state)'
    assert op._st.settle_stay == 1, '复位段后续流程(停留计数)应继续执行到 round_wait'
    assert op._st.rounds_done == 1, 'C-1 新结算帧计数应正常累加(复位段在结算链内)'
