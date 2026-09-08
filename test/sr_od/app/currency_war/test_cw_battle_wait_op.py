"""CwScreenBattleWait 收编锁(W971 05-battle §1,P4)。

结构变化:战斗/结算窗口(原 cw_loop 分支 1f/2/3/3b/5/6)收编进
``cw_screen.cw_screen_battle_wait.CwScreenBattleWait``。本文件以**真实
wait() 行为锁**为主:出口分叉/时序锚/defer 复位均经桩面驱动真实节点方法
(源码字面断言只保留跨文件无超集者);loop 侧闭包守卫的位置限定超集锁在
test_cw_dispatch_wrapper.test_battle_window_guard_hooks_in_closure,
本文件不再重复其断言面。
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


def _battle_wait_op(hit_areas: frozenset):
    """构真实 wait() 可驱动的 CwScreenBattleWait 桩(bypass __init__):
    round_by_find_area 按 hit_areas 程序化回命中;OCR 恒空;controller 录
    点击。依赖面桩法同 test_cw_round_flow.test_loop_outcome_carries_damage。
    返回 (op, clicks)——clicks 录 (point, kwargs) 供 M39 长按断言;
    执行态经 op.ctx.cw_match.exec_state 取(同对象)。"""

    from sr_od.application.currency_war.kernel.cw_exec_state import ExecState
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    es = ExecState()
    clicks: list = []
    controller = SimpleNamespace(
        click=lambda point, **kw: clicks.append((point, kw)),
        mouse_move=lambda *a, **k: None,
        park_cursor=lambda *a, **k: None)

    class _Op(_bwo().CwScreenBattleWait):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            self._st = _bwo().SettlementState(
                run_start_ts=time.monotonic(), is_new_match=True)
            self._unknown_streak = 0
            self._cw_config = None
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=StrategySession(),
                    exec_state=es,
                    strategy=SimpleNamespace()),
                ocr_service=SimpleNamespace(
                    get_ocr_result_list=lambda image, rect=None,
                    color_range=None, crop_first=False: []),
                controller=controller)

        def screenshot(self, *a, **k):
            return None

        def round_by_find_area(self, screen, screen_name, area_name, **kw):
            return SimpleNamespace(is_success=(
                (screen_name, area_name) in hit_areas))

        def round_by_find_and_click_area(self, screen, screen_name,
                                         area_name, **kw):
            return SimpleNamespace(is_success=True)

        def round_by_ocr(self, *a, **k):
            return SimpleNamespace(is_success=False)

        def _record_round_outcome(self, screen, telemetry_only=False):
            pass   # 结算遥测链另有专锁(test_cw_round_flow),本文件不辖

        def save_screenshot(self, prefix=None):
            return ''   # bail 留证截图不落盘(flag 落点由测试重定向 tmp_path)

    return _Op(), clicks


def test_wait_success_exits_fire_on_frames() -> None:
    """成功双出口经真实 wait() 触发(升级自源码在场锁):大厅帧 →
    terminal_lobby(交整局 3c 收口)、白名单帧 → back_to_loop(交循环
    分发)。状态串 = journal 判读词汇;出口与帧错接/丢失即红。"""
    op_t, _ = _battle_wait_op(frozenset({('货币战争-大厅', '标识-创业指南')}))
    op_t.last_screenshot = None
    assert op_t.wait().status == 'terminal_lobby'
    op_b, _ = _battle_wait_op(frozenset({('货币战争-备战', '备战标识-购买经验')}))
    op_b.last_screenshot = None
    assert op_b.wait().status == 'back_to_loop'


def test_unknown_frames_bail_after_budget(tmp_path, monkeypatch) -> None:
    """未知帧达 UNKNOWN_BAIL_N(10)→ round_fail 交主循环兜底链 + flag
    留证(升级自 'round_fail' 在场锁:bail 预算/出口/留证三半环经真实
    路径)。get_project_root 重定向 tmp_path:留证不落真实 .debug(纪律 2);
    轮间 round_wait 切片睡眠由 sleep 桩吸收(墙钟不走 → _interruptible_sleep
    按加速环境语义直返)。"""
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait as bwo
    monkeypatch.setattr(bwo, 'get_project_root', lambda: tmp_path)
    monkeypatch.setattr(time, 'sleep', lambda *_: None)
    op, _ = _battle_wait_op(frozenset())
    op.last_screenshot = None
    res = None
    for _ in range(_bwo().CwScreenBattleWait.UNKNOWN_BAIL_N):
        res = op.wait()
    from one_dragon.base.operation.operation_round_result import (
        OperationRoundResultEnum,
    )
    assert res.result == OperationRoundResultEnum.FAIL
    assert (tmp_path / '.debug' / 'temp' / 'currency_war'
            / 'battle_wait_bail.flag').exists()


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


def test_read_point_delay_and_long_press(monkeypatch) -> None:
    """②段时序行为锁(升级自源码字面锁,常量提取/重排不再假红):
    #25 读点前等 1.5s(结算数据渲染完才读);M39 停留第 3 轮(点击未生效)
    → 长按 (960,898) press_time=0.5 兜底推进,停留计数归零。"""
    sleeps: list = []

    def _rec_sleep(seconds, *_):
        sleeps.append(seconds)

    monkeypatch.setattr(time, 'sleep', _rec_sleep)
    op, clicks = _battle_wait_op(frozenset({('货币战争-结算', '按钮-继续挑战')}))
    op.last_screenshot = None
    for _ in range(2):
        op.wait()
    assert clicks == []   # 停留 1-2 轮未达长按线(= SETTLE_STAY_LONG_PRESS 3)
    op.wait()
    assert len(clicks) == 1   # 第 3 轮恰触发长按兜底
    (point, kw), = clicks
    assert (point.x, point.y) == (960, 898)   # SETTLEMENT_NEXT(经真实点击观测)
    assert kw == {'press_time': 0.5}
    assert op._st.settle_stay == 0   # 长按兜底后停留计数归零
    assert 1.5 in sleeps   # #25 读点延迟在真实路径发生


def test_loop_delegation_wiring() -> None:
    """loop 委托接线最小面(跨文件去重后余量):
    - 帧锚双入口 _frame_in_battle_window 仍在 loop(驻留闩外的第二入口);
      驻留闩与闭包守卫由 dispatch_wrapper 的位置限定超集锁辖,不重复;
    - 3c 收口红线(W971 05-battle §1 遥测连续性红线):runs summary 与
      对局档案装配的调用仍在主循环,不随 op 化迁移;
    - 墓碑:旧内联结算分支(「前往结算」lcs 0.8 点名)不再双写。"""
    src = _loop_src()
    assert '_frame_in_battle_window' in src
    assert 'record_run_summary(' in src
    assert 'match_archive.assemble_pending(' in src
    assert '前往结算", lcs_percent=0.8' not in src


def test_settle_defer_reset_reads_exec_state(monkeypatch) -> None:
    """结算点 defer 复位宿主 = 执行侧载体 ExecState(session 职责分离批锁)。

    defer_count 已随 ADR-0563 迁 ExecState(session 上无该字段);复位端若
    仍读 session 形态 = 「继续挑战」点击后必 AttributeError,备战 defer
    复位防线(结算点 = 新备战轮入口)每次触发即失效。本锁走**真实 wait()
    结算分支**,锁「复位生效于 ctx.cw_match.exec_state」。"""
    monkeypatch.setattr(time, 'sleep', lambda *_: None)   # #25 读点延迟/步进等待不实等

    op, _ = _battle_wait_op(frozenset({('货币战争-结算', '按钮-继续挑战')}))
    es = op.ctx.cw_match.exec_state
    es.defer_count = 2   # 门=2 防空转环在途:结算点应复位归零
    op.last_screenshot = None
    op.wait()

    assert es.defer_count == 0, '结算点 defer 计数须复位(宿主 = cw_match.exec_state)'
    assert op._st.settle_stay == 1, '复位段后续流程(停留计数)应继续执行到 round_wait'
    assert op._st.rounds_done == 1, 'C-1 新结算帧计数应正常累加(复位段在结算链内)'
