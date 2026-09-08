"""P4R 部署/出战链返工锁(第三局 1-1「前台区域无角色」5h 死循环返工)。

三个修法面:①部署落点验证(源槽变 ≠ 上阵成功,deterministic 拖后验**目标槽**
占用);②StartBattle 弹窗污染判据(备战标识消失但出战被拒弹窗在场 = 失败);
③前台无角色 → 带验证重部署 → 验前排 ≥1 → 再出战(带上限,超限 fail 交兜底链)。
"""
import inspect

from one_dragon.base.geometry.point import Point

# ==================== ① 落点验证 ====================

def _make_deploy_op(monkeypatch, occupied_seq: list[bool]):
    """构 CwOpDeploy 桩(bypass __init__),slot_occupied 按序列出票。"""
    from sr_od.application.currency_war.operations.cw_op import cw_op_deploy as db

    calls = {'n': 0}

    def _fake_occ(scr, x, y):
        idx = min(calls['n'], len(occupied_seq) - 1)
        calls['n'] += 1
        return occupied_seq[idx]

    monkeypatch.setattr(db, 'slot_occupied', _fake_occ)
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)

    class _Op(db.CwOpDeploy):
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
    """落点验证:预算耗尽仍无占用 → False(调用方判无效拖拽)。

    预算取 0.2 而非生产默认 2.0:sleep 已桩空,超时路径纯烧墙钟,
    「耗尽 → False」语义与预算数值无关(合并战役降 n)。"""
    from types import SimpleNamespace
    op, _ = _make_deploy_op(monkeypatch, [False])
    assert op._wait_slot_occupied(SimpleNamespace(x=100, y=200), 0.2) is False


def test_deterministic_landing_verification_wired() -> None:
    """源码锁:deterministic 主路径与「源槽已空(验证滞后)」路径都验落点;
    落点未验出 = 判无效拖拽(不计 placed)+ 存证。"""
    from sr_od.application.currency_war.operations.cw_op import cw_op_deploy as db
    src = inspect.getsource(db.CwOpDeploy._deploy_deterministic)
    assert '_wait_slot_occupied(dst' in src          # 主路径落点验证
    assert src.count('_wait_slot_occupied(dst') >= 2  # 滞后补偿路径同样验
    assert '判无效拖拽' in src
    assert 'deploy_landing_fail_slot' in src          # 失败帧存证
    # 否定墓碑(P4R 面二):主循环禁 `for bi in order` 迭代形态——
    # 旧形态 + remove/insert + continue 会静默跳过被移到已过下标的元素
    # (1-1 事故「3-6 件无尝试日志」)。
    assert 'for bi in order:' not in src


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
    """源码锁(0j 升级):确认关闭 → CwOpDeploy 带验证重部署 → 验前排 ≥1
    → 再出战;超限 round_fail(不再无限 round_wait)。"""
    from sr_od.application.currency_war.operations import cw_loop
    src = inspect.getsource(cw_loop.CwLoop.loop)
    assert 'FRONTLESS_REDEPLOY_LIMIT' in src
    assert 'CwOpDeploy(self.ctx).execute()' in src
    assert '_StartBattle()' in src
    assert '前台仍空' in src                       # 出口判据:前排 ≥1 验证
    assert "round_fail('前台无角色重部署超限(前台仍空)')" in src
    assert cw_loop.CwLoop.FRONTLESS_REDEPLOY_LIMIT == 2
    # 预算复位挂点:正常备战环成功跑完 = 部署链健康 → 复位(预算辖连续失败窗)
    assert 'self._frontless_redeploy = 0' in src


# ==================== ④ deployed 计数双源仲裁(板满门;实机停机局回归)====================
# 事故:备战环后排空槽幻影占用 → CV 计数虚高 ≥ cap → 板满假判合法化
# no-op → RunDeploy 同签名零推进停机(DD-030);paddle X 同帧真值 3。
# 修法:板满门 deployed 计数走双源仲裁(取低值,规则单一源 =
# cw_observation.arbitrate_deployed_count);板满谓词的全部早退分支
# (含 CV 幻影满板的入口早退)统一经仲裁 + 留证。

def _make_gate_op(monkeypatch, *, paddle_x, cv_front_occ=1, cv_back_occ=4):
    """构直驱 _deploy_deterministic 的桩 op:CV 占用按槽序列出票。

    默认事故帧形态:bench 槽 1-4 占用(4 真实 bench 角色)、前排 1/4 占用、
    后排 4/6 「占用」(2 真 + 2 幻影)→ CV 计数 = 1+4 = 5;
    paddle 桩恒返 paddle_x(事故真值 3)。
    ``cv_front_occ``/``cv_back_occ`` = 前排/后排占用槽数(幻影满板形态传 4/6)。"""
    from types import SimpleNamespace

    from sr_od.application.currency_war.operations.cw_op import cw_op_deploy as db

    calls = {'n': 0}

    def _fake_occ(scr, x, y):
        i = calls['n']
        calls['n'] += 1
        if i < 9:                      # bench 9 槽:1-4 占用
            return i < 4
        if i < 13:                     # 前排 4 槽:前 cv_front_occ 个占用
            return i - 9 < cv_front_occ
        if i < 19:                     # 后排 6 槽:前 cv_back_occ 个占用
            return i - 13 < cv_back_occ
        return True                    # 循环内 fresh 复查:恒占用

    monkeypatch.setattr(db, 'slot_occupied', _fake_occ)
    monkeypatch.setattr(db, 'read_deploy_cap_debounced',
                        lambda ctx, scr, level: 5)
    monkeypatch.setattr(db, 'read_deployed_count', lambda ctx, scr: paddle_x)
    from sr_od.application.currency_war.obs import cw_back_layout
    monkeypatch.setattr(cw_back_layout, 'select_back_layout',
                        lambda ctx, scr, level=None, cap=None,
                        level_trusted=None: (6, ''))
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)
    drags = {'n': 0}
    monkeypatch.setattr(db.DragCwChar, 'drag_char',
                        lambda op, src, dst: drags.__setitem__('n', drags['n'] + 1) or True)
    # 分键捕获(留证出口桩:避免真 telemetry 依赖;断言「分歧/退化必留证」)
    notes = []
    from sr_od.application.currency_war.telemetry import defects as _defects
    monkeypatch.setattr(_defects, 'record_deployed_count_2src_divergence',
                        lambda p, c, s: notes.append((p, c, s)))

    class _Op(db.CwOpDeploy):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            pass
        def screenshot(self):
            return object()
        def _wait_slot_occupied(self, pt, budget):
            return True

    op = _Op()
    op.ctx = SimpleNamespace(cw_match=None)
    return op, drags, notes


def test_cap_gate_arbitration_opens_on_cv_phantom_inflation(monkeypatch) -> None:
    """事故帧行为锁:paddle=3 / CV=5(幻影)→ 板满门按仲裁值 3 放行 →
    拖拽真实发射(旧代码在此帧 (0, True) 合法化 no-op = 停机根因);
    分歧必须留证分键(不得静默放行)。T-164 批A 契约扩 3 元组:
    本帧不命中失配闸(gate_fail None)。"""
    op, drags, notes = _make_gate_op(monkeypatch, paddle_x=3)
    bench = [Point(100 + 30 * i, 900) for i in range(9)]
    front = [Point(500 + 30 * i, 400) for i in range(4)]
    back = [Point(500 + 30 * i, 650) for i in range(6)]
    placed, plan_empty, gate_fail = op._deploy_deterministic(
        bench, front, back, None)
    assert drags['n'] >= 1, '板满门应按仲裁值(3<5)放行,至少发射一次拖拽'
    assert placed >= 1
    assert plan_empty is False
    assert gate_fail is None
    assert notes and notes[0] == (3, 5, 'deploy_cap_gate'), \
        f'结构性分歧必须落分键留证,实得 {notes}'


def test_cap_gate_full_board_mismatch_fails_not_noop(monkeypatch) -> None:
    """失配执行断言锁(T-164 批A/D2,锁语义重推:旧锁钉「退化帧按 CV
    向板满侧行动 = 合法 no-op」,新 norm 下计划-现读失配禁伪装 plan_empty
    合法稳态):paddle 双帧失读(None)→ 仲裁语义失效单源 CV(5 ≥ cap=5)
    → 入口板满门命中 = 失配暴露(发射位谓词正常时此门不可达)→ 返回
    (0, False, STATUS_BOARD_FULL_MISMATCH),零拖拽;退化申报分键保留。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        CwOpDeploy,
    )
    op, drags, notes = _make_gate_op(monkeypatch, paddle_x=None)
    bench = [Point(100 + 30 * i, 900) for i in range(9)]
    front = [Point(500 + 30 * i, 400) for i in range(4)]
    back = [Point(500 + 30 * i, 650) for i in range(6)]
    placed, plan_empty, gate_fail = op._deploy_deterministic(
        bench, front, back, None)
    assert (placed, plan_empty) == (0, False)
    assert gate_fail == CwOpDeploy.STATUS_BOARD_FULL_MISMATCH, \
        f'板满失配必须以具名状态 fail 暴露,实得 {gate_fail!r}'
    assert drags['n'] == 0
    assert notes and notes[0][0] is None and notes[0][1] == 5, \
        f'paddle 失读退化帧必须落分键申报,实得 {notes}'


def test_cap_gate_phantom_full_board_fails_not_noop(monkeypatch) -> None:
    """矛盾帧失配断言锁(T-164 批A/D2,锁语义重推:旧锁钉「留证后合法
    no-op」;新 norm 下矛盾帧禁伪装 plan_empty):CV 幻影占满**全部**
    前后排槽(front_empty=[] ∧ back_empty=[],比事故帧更重一档)∧
    paddle=3 → 仲裁分歧先落分键留证,再以 (0, False,
    STATUS_PHANTOM_FULL_BOARD) fail 暴露(零拖拽;持续无进展由分发层
    prep_no_progress 停机留证兜底)。旧代码在此形态零留证直接 no-op =
    r9 同签名复活口。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        CwOpDeploy,
    )
    op, drags, notes = _make_gate_op(monkeypatch, paddle_x=3,
                                     cv_front_occ=4, cv_back_occ=6)
    bench = [Point(100 + 30 * i, 900) for i in range(9)]
    front = [Point(500 + 30 * i, 400) for i in range(4)]
    back = [Point(500 + 30 * i, 650) for i in range(6)]
    placed, plan_empty, gate_fail = op._deploy_deterministic(
        bench, front, back, None)
    assert (placed, plan_empty) == (0, False)
    assert gate_fail == CwOpDeploy.STATUS_PHANTOM_FULL_BOARD, \
        f'幻影满板矛盾帧必须以具名状态 fail 暴露,实得 {gate_fail!r}'
    assert drags['n'] == 0
    assert notes and notes[0] == (3, 10, 'deploy_cap_gate'), \
        f'幻影满板早退前必须先落分歧分键(paddle=3 vs cv=10),实得 {notes}'


def test_cap_gate_arbitration_wired_in_deploy_deterministic() -> None:
    """接线烟雾(容忍档;失守事故=备战环 CV 幻影计数合法化 no-op 的
    实机停机局,留证三连无人消费):_deploy_deterministic 必须
    经 arbitrate_deployed_count 仲裁 + 分歧走分键留证。"""
    from sr_od.application.currency_war.operations.cw_op import cw_op_deploy as db
    src = inspect.getsource(db.CwOpDeploy._deploy_deterministic)
    assert 'arbitrate_deployed_count(' in src
    assert '_note_deployed_count_divergence(' in src


# ==================== ⑤ P24 残余补部署 fill 输入重采样(1-1 事故回归)====================
# 事故:1-1 备战主循环排满 cap 后,P24 残余补部署把 kernel 明确留 bench 的
# 留置件(拒因 'cap')反复往满员板面拖,游戏以人口上限不足拒收。根因 =
# residual_fill_plan 收到的 deployed_count 是入口仲裁快照(_deployed=0)而
# 非主循环后真值(_deployed+placed);连带面 = 主循环「源槽已变+落点未验出」
# 的 insert 回收会把实际已落位槽记成空(幻影空槽)。修法 = 计数传
# _deployed+placed + fill 段前 fresh 帧重采两排真空槽。
# 测试纪律(方案审 ④):必须走调用侧 harness 直驱 _deploy_deterministic
# (纯函数层对本 bug 恒绿=假覆盖);断言行为观测量(拖拽计数/拖拽目标);
# 「真空槽」判据对有状态真值模型断言——对喂入 fe/be 列表断言旧代码也过
# =假锁;覆盖主循环自然排尽与 cap-stop break 两条退出路径。

class _BoardTruth:
    """有状态占用真值模型:按槽位坐标记录占用;拖拽改真值、验证读真值。

    模拟游戏侧真相:拖成 = 源槽清空 + 落点槽占用(与验证是否读出无关)——
    「落点验证漏判 → 幻影空槽」只有靠真值与验证分离才构造得出来。"""

    def __init__(self) -> None:
        self.occ: dict[tuple[int, int], bool] = {}

    def set(self, pts, occupied: bool) -> None:
        for p in pts:
            self.occ[(int(p.x), int(p.y))] = occupied

    def is_occ(self, p) -> bool:
        return self.occ.get((int(p.x), int(p.y)), False)


def _make_fill_op(monkeypatch, *, paddle_x: int, cap: int, bench_n: int = 4,
                  front_occ: int = 0, miss_drag_index: int | None = None):
    """直驱 _deploy_deterministic 的真值模型桩 op(仿 _make_gate_op,
    序列出票改为坐标键真值模型——幻影空槽回归需要「拖成后目标槽真翻
    占用」的有状态语义)。

    场景骨架:bench 9 槽前 bench_n 个有角色、前/后排全空(front_occ 个
    前置占用可选);drag 桩真改真值(源空+落占)并记录拖拽序列
    ``[(src, dst, dst_drag 前是否真空)]``(主循环拖拽在前、fill 在后)。
    ``miss_drag_index`` = 第 N 次(0-based)拖拽「落点验证漏判」:真值已
    落位但 _wait_slot_occupied 返 False(特效/时间窗漏判形态)。"""
    from types import SimpleNamespace

    from sr_od.application.currency_war.operations.cw_op import cw_op_deploy as db

    truth = _BoardTruth()
    bench = [Point(100 + 30 * i, 900) for i in range(9)]
    front = [Point(500 + 30 * i, 400) for i in range(4)]
    back = [Point(500 + 30 * i, 650) for i in range(6)]
    truth.set(bench[:bench_n], True)
    truth.set(bench[bench_n:], False)
    truth.set(front[:front_occ], True)
    truth.set(front[front_occ:], False)
    truth.set(back, False)

    monkeypatch.setattr(db, 'slot_occupied',
                        lambda scr, x, y: truth.occ.get((int(x), int(y)), False))
    monkeypatch.setattr(db, 'read_deploy_cap_debounced',
                        lambda ctx, scr, level: cap)
    monkeypatch.setattr(db, 'read_deployed_count', lambda ctx, scr: paddle_x)
    from sr_od.application.currency_war.obs import cw_back_layout
    monkeypatch.setattr(cw_back_layout, 'select_back_layout',
                        lambda ctx, scr, level=None, cap=None,
                        level_trusted=None: (6, ''))
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)

    drags: list = []      # [(src, dst, dst_drag 前是否真空)]
    waits = {'n': 0}

    def _fake_drag(op, src, dst):
        drags.append((src, dst, not truth.is_occ(dst)))
        truth.set([src], False)   # 源槽变(drag_char 内部验证语义)
        truth.set([dst], True)    # 单位实际落位(游戏侧真值,与验证无关)
        return True

    monkeypatch.setattr(db.DragCwChar, 'drag_char', _fake_drag)
    from sr_od.application.currency_war.telemetry import defects as _defects
    monkeypatch.setattr(_defects, 'record_deployed_count_2src_divergence',
                        lambda p, c, s: None)

    class _Op(db.CwOpDeploy):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            pass
        def screenshot(self):
            return object()
        def save_screenshot(self, prefix=None):
            pass   # 失败存证桩化(零真实落盘)
        def _wait_slot_occupied(self, pt, budget):
            i = waits['n']
            waits['n'] += 1
            if i == miss_drag_index:
                return False   # 验证漏判:真值已落位,验证窗未验出
            return truth.is_occ(pt)

    op = _Op()
    op.ctx = SimpleNamespace(cw_match=None)
    return op, truth, drags, bench, front, back


def test_p24_fill_skipped_when_order_exhausted_at_cap(monkeypatch) -> None:
    """事故形态·自然排尽路径(行为观测锁):board 空 + paddle=0 + cap=3 +
    bench 4 人 → kernel cap 截断 3 上 1 留(拒因 'cap')→ 主循环拖 3 次
    自然排尽 → fill 段零拖拽(整场总拖拽==3),留置件不得被拖出。
    旧代码 fill 门按入口快照 0 恒开 → 总拖拽 4(往满员板白拖)。"""
    op, truth, drags, bench, front, back = _make_fill_op(
        monkeypatch, paddle_x=0, cap=3)
    placed, plan_empty, gate_fail = op._deploy_deterministic(
        bench, front, back, None)
    assert (placed, plan_empty) == (3, False)
    assert gate_fail is None
    assert len(drags) == 3, f'fill 阶段应零拖拽(整场 3),实得 {len(drags)}'
    assert all(src is not bench[3] for src, _, _ in drags), \
        'kernel 留置件(bench 第 4 槽)不得被往满员板拖出'


def test_p24_fill_skipped_on_cap_stop_break(monkeypatch) -> None:
    """事故形态·cap-stop break 路径(行为观测锁):板面已有 1 人(paddle=1
    与 CV 一致)+ cap=3 + bench 4 人 → kernel cap 基(SIFT 集=0)与仲裁基
    (=1)分歧 → order=3 但主循环拖 2 次后动态板满门 break → fill 段零
    拖拽(总拖拽==2)。旧代码 fill 门按入口仲裁快照 1(1+0>=3)恒开 →
    总拖拽 3。"""
    op, truth, drags, bench, front, back = _make_fill_op(
        monkeypatch, paddle_x=1, cap=3, front_occ=1)
    placed, plan_empty, gate_fail = op._deploy_deterministic(
        bench, front, back, None)
    assert (placed, plan_empty) == (2, False)
    assert gate_fail is None
    assert len(drags) == 2, f'cap-stop 后 fill 应零拖拽(整场 2),实得 {len(drags)}'


def test_p24_fill_targets_truth_empty_slots_after_landing_miss(
        monkeypatch) -> None:
    """「真空槽」判据锁(幻影空槽治愈):主循环末件落点验证漏判(真值已
    落位、验证 False → insert 回收成幻影空槽)后,fill 拖拽目标在拖拽
    时刻必须是真值模型真空槽——对真值断言,不对喂入 fe/be 断言(旧代码
    喂别名列表含幻影槽,fill 拖向已占槽=白烧)。cap=4 + bench 5 人:
    主循环 3 验证落地 + 第 4 件真落位但漏判,fill 补第 5 件至真空槽。"""
    op, truth, drags, bench, front, back = _make_fill_op(
        monkeypatch, paddle_x=0, cap=4, bench_n=5, miss_drag_index=3)
    placed, plan_empty, gate_fail = op._deploy_deterministic(
        bench, front, back, None)
    assert (placed, plan_empty) == (4, False)
    assert gate_fail is None
    assert len(drags) == 5, f'主循环 4 + fill 1,实得 {len(drags)}'
    (_, fill_dst, dst_was_truth_empty), = drags[4:]
    assert dst_was_truth_empty, \
        f'fill 拖拽目标必须是真值真空槽,实得 {fill_dst}(拖前已占用=幻影槽)'
    assert fill_dst is not back[2], '漏判回收的幻影槽不得成为 fill 目标'
