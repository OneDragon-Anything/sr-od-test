"""P4R 部署/出战链返工锁(第三局 1-1「前台区域无角色」5h 死循环返工)。

三个修法面:①部署落点验证(源槽变 ≠ 上阵成功,deterministic 拖后验**目标槽**
占用);②StartBattle 弹窗污染判据(备战标识消失但出战被拒弹窗在场 = 失败);
③前台无角色 → 带验证重部署 → 验前排 ≥1 → 再出战(带上限,超限 fail 交兜底链)。
"""
import inspect

# ==================== ① 落点验证 ====================

def _make_deploy_op(monkeypatch, occupied_seq: list[bool]):
    """构 DeployBench 桩(bypass __init__),slot_occupied 按序列出票。"""
    from sr_od.application.currency_war.operations.prep import deploy_bench as db

    calls = {'n': 0}

    def _fake_occ(scr, x, y):
        idx = min(calls['n'], len(occupied_seq) - 1)
        calls['n'] += 1
        return occupied_seq[idx]

    monkeypatch.setattr(db, 'slot_occupied', _fake_occ)
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)

    class _Op(db.DeployBench):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            pass
        def screenshot(self):
            return object()

    return _Op(), calls


def test_wait_slot_occupied_hits_within_budget(monkeypatch) -> None:
    """落点验证:目标槽在预算内出现占用 → True(事件驱动轮询,命中即返)。"""
    from types import SimpleNamespace
    op, calls = _make_deploy_op(monkeypatch, [False, False, True])
    pt = SimpleNamespace(x=100, y=200)
    assert op._wait_slot_occupied(pt, 2.0) is True
    assert calls['n'] == 3   # 第三帧才占用


def test_wait_slot_occupied_timeout_false(monkeypatch) -> None:
    """落点验证:预算耗尽仍无占用 → False(调用方判无效拖拽)。"""
    from types import SimpleNamespace
    op, _ = _make_deploy_op(monkeypatch, [False])
    assert op._wait_slot_occupied(SimpleNamespace(x=100, y=200), 2.0) is False


def test_deterministic_landing_verification_wired() -> None:
    """源码锁:deterministic 主路径与「源槽已空(验证滞后)」路径都验落点;
    落点未验出 = 判无效拖拽(不计 placed)+ 存证。"""
    from sr_od.application.currency_war.operations.prep import deploy_bench as db
    src = inspect.getsource(db.DeployBench._deploy_deterministic)
    assert '_wait_slot_occupied(dst' in src          # 主路径落点验证
    assert src.count('_wait_slot_occupied(dst') >= 2  # 滞后补偿路径同样验
    assert '判无效拖拽' in src
    assert 'deploy_landing_fail_slot' in src          # 失败帧存证


def test_deterministic_no_silent_exits() -> None:
    """源码锁(P4R 面二):①主循环为下标显式推进(迭代中重排不再依赖
    for 迭代器语义——旧 `for bi in order` + remove/insert + continue 会
    静默跳过被移到已过下标的元素,1-1 事故「3-6 件无尝试日志」形态);
    ②两排皆满 break 带证据日志。"""
    from sr_od.application.currency_war.operations.prep import deploy_bench as db
    src = inspect.getsource(db.DeployBench._deploy_deterministic)
    assert 'while _oi < len(_pending)' in src
    assert 'for bi in order:' not in src
    assert '两排皆满,无槽可拖 → 终止' in src


# ==================== ② StartBattle 弹窗污染判据 ====================

class _FakeArea:
    def __init__(self, ok: bool): self.is_success = ok


def _make_launch_op(monkeypatch, *, blocker_seen: bool, prep_gone_round: int = 1):
    """构 PrepActionExecutor 桩:备战标识第 prep_gone_round 轮消失;
    blocker_seen = 标识消失帧是否弹出「前台无角色」拦截弹窗。"""
    import sr_od.application.currency_war.prep_actions as pa
    st = {'round': 0}

    class _Dir:
        def screenshot(self):
            st['round'] += 1
            return object()
        def round_by_find_area(self, scr, screen, area, **k):
            if area == '按钮-出战':
                return _FakeArea(True)
            if area == '标识-未达上限警告':
                return _FakeArea(False)
            if area == '备战标识-购买经验':
                return _FakeArea(st['round'] < prep_gone_round)
            if area == '标识-无角色提示':
                return _FakeArea(blocker_seen and st['round'] >= prep_gone_round)
            return _FakeArea(False)
        def save_screenshot(self, prefix=None): pass
        def park_cursor(self, **k): pass

    class _Ctrl:
        def mouse_move(self, p): pass
        def click(self, p, press_time: float = 0.1): pass
        class game_win:
            is_win_active = True
            @staticmethod
            def active(): pass

    monkeypatch.setattr(pa.time, 'sleep', lambda s: None)
    # 出战按钮 area_center 桩化(None → 执行器 fallback 常量;免 screen_loader)
    monkeypatch.setattr(pa, 'area_center', lambda ctx, name, screen=None: None)
    ex = pa.PrepActionExecutor.__new__(pa.PrepActionExecutor)
    ex._op = _Dir()
    ex._ctx = type('C', (), {'controller': _Ctrl()})()
    return ex


def test_startbattle_popup_pollution_rejected(monkeypatch) -> None:
    """备战标识消失 + 「前台无角色」弹窗在场 = 出战失败(非成功)——
    1-1 事故假成功判据收紧。"""
    ex = _make_launch_op(monkeypatch, blocker_seen=True)
    ok, detail = ex._launch_attempt()
    assert ok is False
    assert '出战被拒' in detail and '标识-无角色提示' in detail


def test_startbattle_clean_transition_succeeds(monkeypatch) -> None:
    """备战标识消失 + 无拦截弹窗 = 出战成功(回归:正常转移不误杀)。"""
    ex = _make_launch_op(monkeypatch, blocker_seen=False)
    ok, detail = ex._launch_attempt()
    assert ok is True and detail == '出战成功'


def test_post_launch_blockers_registry() -> None:
    """拦截弹窗白名单含「前台无角色」(已建档 id_mark;新弹窗建档后追加)。"""
    from sr_od.application.currency_war.prep_actions import PrepActionExecutor
    assert ('货币战争-提示-前台无角色', '标识-无角色提示') \
        in PrepActionExecutor.POST_LAUNCH_BLOCKERS


# ==================== ③ 前台无角色 → 验证重部署 → 出战链 ====================

def test_frontless_recovery_chain_wired() -> None:
    """源码锁(0j 升级):确认关闭 → DeployBench 带验证重部署 → 验前排 ≥1
    → 再出战;超限 round_fail(不再无限 round_wait)。"""
    from sr_od.application.currency_war.operations import battle_loop
    src = inspect.getsource(battle_loop.CurrencyWarRunLoop.loop)
    assert 'FRONTLESS_REDEPLOY_LIMIT' in src
    assert 'DeployBench(self.ctx).execute()' in src
    assert '_StartBattle()' in src
    assert '前台仍空' in src                       # 出口判据:前排 ≥1 验证
    assert "round_fail('前台无角色重部署超限(前台仍空)')" in src
    assert battle_loop.CurrencyWarRunLoop.FRONTLESS_REDEPLOY_LIMIT == 2
    # 预算复位挂点:正常备战环成功跑完 = 部署链健康 → 复位(预算辖连续失败窗)
    assert 'self._frontless_redeploy = 0' in src
